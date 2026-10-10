"""Final result conversion using concrete LangChain SDK result types."""

from collections.abc import Sequence

from langchain_core.messages import AIMessage, AIMessageChunk, BaseMessage, ToolMessage
from langchain_core.outputs import ChatGeneration, ChatResult, Generation, LLMResult
from ygo74.agent_runtime.domains.contracts.agent_output import (
    AgentContent,
    AgentOutput,
    Termination,
    TerminationStatus,
    TokenUsage,
    ToolExecution,
    ToolResultContent,
)

from .content import JsonBoundary, LangChainContentAdapter
from .conversion import (
    ConversionDiagnostic,
    ConversionOutcome,
    ConversionStatus,
    LangChainConversionError,
)


class LangChainResultAdapter:
    """Choose one generation explicitly; do not expose prompts or tool artifacts.

    Args:
        expose_reasoning (bool): Whether reasoning content may be included in client-visible output.
        tool_execution (ToolExecution): Whether tool calls are internal or delegated to the client.
    """
    def __init__(
        self, *, expose_reasoning: bool = False,
        tool_execution: ToolExecution = ToolExecution.INTERNAL,
    ) -> None:
        """Initialize the instance framework results with supplied collaborators and configuration.

        Args:
            expose_reasoning (bool): Whether reasoning content may be included in client-visible output.
            tool_execution (ToolExecution): Whether tool calls are internal or delegated to the client.
        """
        self.content_adapter = LangChainContentAdapter(
            expose_reasoning=expose_reasoning, tool_execution=tool_execution,
        )

    def convert(
        self, value: BaseMessage | ChatGeneration | ChatResult | LLMResult,
        *, generation_index: int = 0,
    ) -> ConversionOutcome:
        """Convert framework results into the typed representation consumed by the runtime.

        Args:
            value (BaseMessage | ChatGeneration | ChatResult | LLMResult): The value being converted, checked, or serialized.
            generation_index (int): Index selecting the generation returned to the caller.
        """
        if isinstance(value, AIMessageChunk):
            return self.unsupported("chunk_not_final", "Use the stream adapter for incremental SDK chunks.")
        if isinstance(value, ToolMessage):
            return self._tool(value)
        if isinstance(value, AIMessage):
            return self._assistant(value)
        if isinstance(value, BaseMessage):
            return ConversionOutcome(ConversionStatus.EXCLUDED, diagnostics=(
                ConversionDiagnostic("non_output_message", "User, system and other input messages are not agent outputs."),
            ))
        if isinstance(value, ChatGeneration):
            converted = self.convert(value.message)
            reason = (value.generation_info or {}).get("finish_reason")
            if converted.output is not None and isinstance(reason, str):
                output = converted.output
                return ConversionOutcome(
                    converted.status, output=AgentOutput(output.contents, output.usage, self.termination(reason)),
                    diagnostics=converted.diagnostics,
                )
            return converted
        if isinstance(value, ChatResult):
            return self._generation(value.generations, generation_index)
        if isinstance(value, LLMResult):
            if len(value.generations) != 1:
                return self.unsupported("batch_result", "Select one SDK prompt result before conversion.")
            return self._generation(value.generations[0], generation_index)
        return self.unsupported("unsupported_result", "Expected an SDK message or chat result, not an agent state snapshot.")

    def _generation(self, generations: Sequence[Generation], index: int) -> ConversionOutcome:
        """Select the requested generation explicitly and convert only its assistant output.

        Args:
            generations (Sequence[Generation]): Framework generations converted into a single agent result.
            index (int): Position used to correlate an item within its message or stream.
        """
        if not generations:
            return ConversionOutcome(ConversionStatus.CONVERTED, output=AgentOutput())
        if index < 0 or index >= len(generations):
            raise LangChainConversionError("Selected generation index is outside the SDK result.")
        generation = generations[index]
        if not isinstance(generation, ChatGeneration):
            return self.unsupported("non_chat_generation", "Only SDK chat generations provide typed output contents.")
        return self.convert(generation)

    def _assistant(self, message: AIMessage) -> ConversionOutcome:
        """Convert assistant message blocks in order and retain diagnostics for unsupported content.

        Args:
            message (AIMessage): Framework message or protocol message being converted.
        """
        # Convert blocks in their original order and retain diagnostics for unsupported blocks and invalid tool calls in the overall outcome.
        contents: list[AgentContent] = []
        diagnostics: list[ConversionDiagnostic] = []
        unsupported = False
        blocks = message.content_blocks
        names = self.content_adapter.tool_names(blocks)
        for index, block in enumerate(blocks):
            converted = self.content_adapter.convert(
                block, fallback_id=f"{message.id or 'message'}:audio:{index}", tool_names=names,
            )
            if converted.content is not None:
                contents.append(converted.content)
            if converted.diagnostic is not None:
                diagnostics.append(converted.diagnostic)
            unsupported |= converted.unsupported
        if message.invalid_tool_calls:
            unsupported = True
            diagnostics.append(ConversionDiagnostic("invalid_tool_calls", "SDK tool calls contain invalid arguments."))
        reason = message.response_metadata.get("finish_reason")
        return ConversionOutcome(
            ConversionStatus.UNSUPPORTED if unsupported else ConversionStatus.CONVERTED,
            output=AgentOutput(tuple(contents), self.usage(message), self.termination(reason if isinstance(reason, str) else None)),
            diagnostics=tuple(diagnostics),
        )

    def _tool(self, message: ToolMessage) -> ConversionOutcome:
        """Convert a tool message result with its original call identity.

        Args:
            message (ToolMessage): Framework message or protocol message being converted.
        """
        if message.name is None or not message.name.strip():
            return self.unsupported("missing_tool_name", "A standalone SDK tool result requires its genuine nonempty name.")
        if not message.tool_call_id.strip():
            return self.unsupported("missing_tool_call_id", "A tool result must have an SDK correlation identity.")
        output = AgentOutput((ToolResultContent(
            message.tool_call_id, message.name, JsonBoundary.convert(message.content), ToolExecution.INTERNAL,
        ),))
        if message.status == "error":
            return ConversionOutcome(ConversionStatus.UNSUPPORTED, output=output, diagnostics=(
                ConversionDiagnostic("tool_result_status_unrepresentable", "The neutral tool result has no per-tool failure status."),
            ))
        return ConversionOutcome(ConversionStatus.CONVERTED, output=output)

    @staticmethod
    def usage(message: AIMessage) -> TokenUsage | None:
        """Project usage information framework results into the typed usage contract or provider-specific counters.

        Args:
            message (AIMessage): Framework message or protocol message being converted.
        """
        usage = message.usage_metadata
        if usage is None:
            return None
        input_details = usage.get("input_token_details")
        output_details = usage.get("output_token_details")
        return TokenUsage(
            usage["input_tokens"], usage["output_tokens"], usage["total_tokens"],
            cached_input_tokens=input_details.get("cache_read") if input_details is not None else None,
            reasoning_output_tokens=output_details.get("reasoning") if output_details is not None else None,
            cache_write_input_tokens=input_details.get("cache_creation") if input_details is not None else None,
        )

    @staticmethod
    def termination(reason: str | None = None) -> Termination:
        """Project termination status framework results into the provider or framework representation.

        Args:
            reason (str | None): Reason code or message associated with this decision or failure.
        """
        incomplete = reason in ("length", "max_tokens", "content_filter")
        return Termination(TerminationStatus.INCOMPLETE if incomplete else TerminationStatus.SUCCESS, reason)

    @staticmethod
    def unsupported(code: str, reason: str) -> ConversionOutcome:
        """Return the conversion outcome for a native value the neutral contract cannot represent.

        Args:
            code (str): Stable error or diagnostic code returned to the caller.
            reason (str): Reason code or message associated with this decision or failure.
        """
        return ConversionOutcome(ConversionStatus.UNSUPPORTED, diagnostics=(ConversionDiagnostic(code, reason),))
