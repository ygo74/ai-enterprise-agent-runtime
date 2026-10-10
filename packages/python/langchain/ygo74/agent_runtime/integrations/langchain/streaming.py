"""Per-invocation conversion of SDK chunks and astream_events(version='v2')."""

from dataclasses import dataclass, field
from enum import StrEnum
from typing import cast

from langchain_core.messages import (
    AIMessage,
    AIMessageChunk,
    ToolMessage,
    message_chunk_to_message,
)
from langchain_core.messages.content import (
    ContentBlock,
    ServerToolCallChunk,
    ToolCallChunk,
)
from langchain_core.runnables.schema import StreamEvent
from ygo74.agent_runtime.domains.contracts.agent_output import (
    AgentContent,
    Notification,
    ReasoningContent,
    Termination,
    TerminationStatus,
    TextContent,
    TokenUsage,
    ToolCallContent,
    ToolExecution,
    ToolResultContent,
)
from ygo74.agent_runtime.domains.contracts.stream_events import (
    AgentStreamEvent,
    ContentEnd,
    ContentEvent,
    ContentStart,
    TerminalEvent,
    TextDelta,
    ToolArgumentsDelta,
    UsageEvent,
)

from .content import BlockKind, JsonBoundary
from .conversion import (
    ConversionDiagnostic,
    ConversionOutcome,
    ConversionStatus,
    LangChainConversionError,
)
from .results import LangChainResultAdapter


class NativeEvent(StrEnum):
    """Names LangChain event types consumed by the stream adapter.
    """
    CHAT_STREAM = "on_chat_model_stream"
    CHAT_END = "on_chat_model_end"
    CHAT_START = "on_chat_model_start"
    TOOL_START = "on_tool_start"
    TOOL_END = "on_tool_end"
    CHAIN_START = "on_chain_start"
    CHAIN_STREAM = "on_chain_stream"
    CHAIN_END = "on_chain_end"
    PROMPT_START = "on_prompt_start"
    PROMPT_END = "on_prompt_end"
    RETRIEVER_START = "on_retriever_start"
    RETRIEVER_END = "on_retriever_end"
    CUSTOM = "on_custom_event"


@dataclass(slots=True)
class _ContentState:
    """Accumulates content fragments and correlation metadata for one item within a LangChain run.

    Args:
        content_id (str): Stable identity correlating one content item across start, delta, and end events.
        content (AgentContent | None): The content item being interpreted or projected.
        tool_id (str | None): Framework tool-call identifier used for correlation.
        tool_name (str | None): Name of the tool whose declaration or invocation is being resolved.
        arguments (list[str]): JSON arguments associated with a tool call.
        started (bool): Whether the corresponding content start event has been emitted.
    """
    content_id: str
    content: AgentContent | None = None
    tool_id: str | None = None
    tool_name: str | None = None
    arguments: list[str] = field(default_factory=list)
    started: bool = False


@dataclass(slots=True)
class _RunState:
    """Tracks content items, usage, and closure for one independently correlated LangChain run.

    Args:
        contents (dict[str, _ContentState]): Ordered typed content items associated with the agent output.
        usage (TokenUsage | None): Token counters supplied by the framework or provider.
        closed (bool): Whether the content or run has already emitted its terminal event.
    """
    contents: dict[str, _ContentState] = field(default_factory=dict)
    usage: TokenUsage | None = None
    closed: bool = False


@dataclass(frozen=True, slots=True)
class _ToolRun:
    """Accumulates a tool invocation identity and argument fragments until the call can be emitted as typed events.

    Args:
        call_id (str): Stable tool invocation identity used to correlate its result.
        name (str): The name used to locate or label the value.
    """
    call_id: str
    name: str


class LangChainStreamAdapter:
    """Create a fresh instance per invocation, not one shared across requests.

    Args:
        expose_reasoning (bool): Whether reasoning content may be included in client-visible output.
        tool_execution (ToolExecution): Whether tool calls are internal or delegated to the client.
    """
    def __init__(
        self, *, expose_reasoning: bool = False,
        tool_execution: ToolExecution = ToolExecution.INTERNAL,
    ) -> None:
        """Initialize the instance framework stream events with supplied collaborators and configuration.

        Args:
            expose_reasoning (bool): Whether reasoning content may be included in client-visible output.
            tool_execution (ToolExecution): Whether tool calls are internal or delegated to the client.
        """
        self.result_adapter = LangChainResultAdapter(
            expose_reasoning=expose_reasoning, tool_execution=tool_execution,
        )
        self._runs: dict[str, _RunState] = {}
        self._tools: dict[str, _ToolRun] = {}
        self._finished = False
        self._termination = Termination()

    def convert(self, event: StreamEvent, *, tool_call_id: str | None = None) -> ConversionOutcome:
        """Convert framework stream events into the typed representation consumed by the runtime.

        Args:
            event (StreamEvent): The typed event whose content or lifecycle effect is processed.
            tool_call_id (str | None): Identifier of the tool call associated with this result.
        """
        if self._finished:
            return self._excluded("stream_finished", "The invocation is already terminal.")
        kind = event["event"]
        run_id = event["run_id"]
        if not run_id:
            raise LangChainConversionError("The SDK event must have a run identity.")
        if kind == NativeEvent.CHAT_STREAM:
            chunk = event["data"].get("chunk")
            if not isinstance(chunk, AIMessageChunk):
                return self.result_adapter.unsupported("unsupported_chunk", "The chat stream event must contain an SDK AIMessageChunk.")
            return self.convert_chunk(chunk, run_id=run_id)
        if kind == NativeEvent.CHAT_END:
            output = event["data"].get("output")
            if not isinstance(output, AIMessage):
                return self.result_adapter.unsupported("unsupported_model_snapshot", "The chat end event must contain an SDK AIMessage.")
            if isinstance(output, AIMessageChunk):
                output = cast(AIMessage, message_chunk_to_message(output))
            converted = self._end_model(output, run_id)
            if not event["parent_ids"]:
                finished = self.finish()
                return ConversionOutcome(
                    converted.status, converted.events + finished.events, diagnostics=converted.diagnostics,
                )
            return converted
        if kind == NativeEvent.TOOL_START:
            return self._tool_start(event, tool_call_id)
        if kind == NativeEvent.TOOL_END:
            converted = self._tool_end(event)
            if not event["parent_ids"]:
                finished = self.finish()
                return ConversionOutcome(
                    converted.status, converted.events + finished.events, diagnostics=converted.diagnostics,
                )
            return converted
        if kind == NativeEvent.CHAIN_END and not event["parent_ids"]:
            return self.finish()
        if kind in (
            NativeEvent.CHAT_START, NativeEvent.CHAIN_START, NativeEvent.CHAIN_STREAM,
            NativeEvent.CHAIN_END, NativeEvent.PROMPT_START, NativeEvent.PROMPT_END,
            NativeEvent.RETRIEVER_START, NativeEvent.RETRIEVER_END,
        ):
            return self._excluded("snapshot_or_input_event", "Inputs and chain state snapshots are not incremental model output.")
        return self.result_adapter.unsupported(
            "unsupported_event", "The SDK event has no built-in mapping; the developer may select a notification.",
        )

    def convert_chunk(self, chunk: AIMessageChunk, *, run_id: str) -> ConversionOutcome:
        """Convert an SDK chunk into correlated typed stream events and per-run usage.

        Args:
            chunk (AIMessageChunk): Partial SDK message containing new content or tool-call arguments.
            run_id (str): SDK run identity used to keep interleaved model output correlated.
        """
        # Chunks are grouped by SDK run identity so interleaved model runs retain separate content state, diagnostics, and cumulative usage.
        if self._finished:
            return self._excluded("stream_finished", "The invocation is already terminal.")
        if not run_id:
            raise LangChainConversionError("The SDK chunk must have a run identity.")
        state = self._runs.setdefault(run_id, _RunState())
        if state.closed:
            raise LangChainConversionError("A model chunk followed its completed SDK run.")
        events: list[AgentStreamEvent] = []
        diagnostics: list[ConversionDiagnostic] = []
        unsupported = False
        for index, block in enumerate(chunk.content_blocks):
            kind = block["type"]
            if kind in (BlockKind.TOOL_CALL_CHUNK.value, BlockKind.SERVER_TOOL_CALL_CHUNK.value):
                events.extend(self._tool_chunk(cast(ToolCallChunk | ServerToolCallChunk, block), run_id, state))
                continue
            converted = self.result_adapter.content_adapter.convert(block, fallback_id=f"{run_id}:audio:{index}")
            if converted.diagnostic is not None:
                diagnostics.append(converted.diagnostic)
            unsupported |= converted.unsupported
            if isinstance(converted.content, (TextContent, ReasoningContent)):
                block_id = f"{run_id}:{kind}:{block.get('index', index)}"
                if isinstance(converted.content, TextContent) and self._late_citation(converted.content, block_id, state):
                    unsupported = True
                    diagnostics.append(self._citation_diagnostic())
                events.extend(self._text_chunk(converted.content, block_id, state))
            elif converted.content is not None:
                unsupported = True
                diagnostics.append(ConversionDiagnostic(
                    "non_delta_content_in_chunk", "Complete tools/media in chunks require a final SDK snapshot or explicit content conversion.",
                ))
        usage = self.result_adapter.usage(chunk)
        if usage is not None:
            state.usage = self._combine_usage(state.usage, usage)
            events.insert(0, UsageEvent(self._total_usage()))
        return ConversionOutcome(
            ConversionStatus.UNSUPPORTED if unsupported else ConversionStatus.CONVERTED,
            tuple(events), diagnostics=tuple(diagnostics),
        )

    def _text_chunk(
        self, content: TextContent | ReasoningContent, content_id: str, state: _RunState,
    ) -> tuple[AgentStreamEvent, ...]:
        """Emit a content start once and append the new text or reasoning fragment to that run item.

        Args:
            content (TextContent | ReasoningContent): The content item being interpreted or projected.
            content_id (str): Stable identity correlating one content item across start, delta, and end events.
            state (_RunState): The state that tracks the current operation lifecycle.
        """
        if not content.text and not (isinstance(content, TextContent) and content.annotations):
            return ()
        events: list[AgentStreamEvent] = []
        existing = state.contents.get(content_id)
        if existing is None:
            initial: AgentContent = (
                ReasoningContent("", exposable=True) if isinstance(content, ReasoningContent)
                else TextContent("", content.annotations)
            )
            state.contents[content_id] = _ContentState(content_id, initial, started=True)
            events.append(ContentStart(content_id, initial))
        if content.text:
            events.append(TextDelta(content_id, content.text))
        return tuple(events)

    @staticmethod
    def _late_citation(content: TextContent, content_id: str, state: _RunState) -> bool:
        """Detect citations that arrive after text streaming began and report that the prior text cannot be retracted.

        Args:
            content (TextContent): The content item being interpreted or projected.
            content_id (str): Stable identity correlating one content item across start, delta, and end events.
            state (_RunState): The state that tracks the current operation lifecycle.
        """
        existing = state.contents.get(content_id)
        if existing is None or not isinstance(existing.content, TextContent):
            return False
        return any(annotation not in existing.content.annotations for annotation in content.annotations)

    @staticmethod
    def _citation_diagnostic() -> ConversionDiagnostic:
        """Create the safe diagnostic used when citation metadata arrives too late to attach reliably.
        """
        return ConversionDiagnostic(
            "late_citation", "Citation metadata arrived after content start; the neutral stream has no annotation amendment event.",
        )

    def _tool_chunk(
        self, chunk: ToolCallChunk | ServerToolCallChunk, run_id: str, state: _RunState,
    ) -> tuple[AgentStreamEvent, ...]:
        """Accumulate indexed tool fragments until their identity is complete, then emit the call and arguments.

        Args:
            chunk (ToolCallChunk | ServerToolCallChunk): Partial SDK message containing new content or tool-call arguments.
            run_id (str): SDK run identity used to keep interleaved model output correlated.
            state (_RunState): The state that tracks the current operation lifecycle.
        """
        # An indexed tool call may arrive before its ID or name, so accumulate fragments until correlation is complete and emit its start event only once.
        index = chunk.get("index")
        if index is None:
            raise LangChainConversionError("Tool argument chunks require an SDK index for parallel correlation.")
        server = chunk["type"] == BlockKind.SERVER_TOOL_CALL_CHUNK.value
        category = "server_tool" if server else "tool"
        content_id = f"{run_id}:{category}:{index}"
        existing = state.contents.setdefault(content_id, _ContentState(content_id))
        for value, previous in ((chunk.get("id"), existing.tool_id), (chunk.get("name"), existing.tool_name)):
            if value and previous and value != previous:
                raise LangChainConversionError("SDK tool identity or name changed within one indexed call.")
        existing.tool_id = chunk.get("id") or existing.tool_id
        existing.tool_name = chunk.get("name") or existing.tool_name
        arguments = chunk.get("args")
        if arguments:
            existing.arguments.append(arguments)
        events: list[AgentStreamEvent] = []
        if not existing.tool_id or not existing.tool_name:
            return ()
        if not existing.tool_id.strip() or not existing.tool_name.strip():
            raise LangChainConversionError("SDK tool identity and name must be nonempty.")
        if not existing.started:
            content = ToolCallContent(
                existing.tool_id, existing.tool_name,
                execution=ToolExecution.INTERNAL if server else self.result_adapter.content_adapter.tool_execution,
            )
            existing.content = content
            existing.started = True
            events.append(ContentStart(content_id, content))
        events.extend(ToolArgumentsDelta(content_id, argument) for argument in existing.arguments)
        existing.arguments.clear()
        return tuple(events)

    def _end_model(self, message: AIMessage, run_id: str) -> ConversionOutcome:
        """Reconcile the final SDK message with chunks already emitted for this model run.

        Args:
            message (AIMessage): Framework message or protocol message being converted.
            run_id (str): SDK run identity used to keep interleaved model output correlated.
        """
        # The final SDK snapshot can repeat content already emitted as chunks; reconcile it against run state so streamed content is not emitted twice.
        state = self._runs.setdefault(run_id, _RunState())
        if state.closed:
            return self._excluded("model_already_closed", "This SDK model snapshot was already processed.")
        events: list[AgentStreamEvent] = list(self._close_run(state))
        diagnostics: list[ConversionDiagnostic] = []
        unsupported = False
        blocks = message.content_blocks
        names = self.result_adapter.content_adapter.tool_names(blocks)
        for content in state.contents.values():
            if content.tool_id and content.tool_name:
                self.result_adapter.content_adapter.register_tool_name(names, content.tool_id, content.tool_name)
        for index, block in enumerate(blocks):
            converted = self.result_adapter.content_adapter.convert(
                block, fallback_id=f"{run_id}:audio:{index}", tool_names=names,
            )
            if converted.diagnostic is not None:
                diagnostics.append(converted.diagnostic)
            unsupported |= converted.unsupported
            if self._was_streamed(block, index, run_id, state):
                content_id = f"{run_id}:{block['type']}:{block.get('index', index)}"
                if isinstance(converted.content, TextContent) and self._late_citation(converted.content, content_id, state):
                    unsupported = True
                    diagnostics.append(self._citation_diagnostic())
                continue
            if converted.content is not None:
                events.append(ContentEvent(f"{run_id}:final:{index}", converted.content))
        if message.invalid_tool_calls:
            unsupported = True
            diagnostics.append(ConversionDiagnostic("invalid_tool_calls", "SDK tool calls contain invalid arguments."))
        usage = self.result_adapter.usage(message)
        if usage is not None and usage != state.usage:
            state.usage = usage
            events.insert(0, UsageEvent(self._total_usage()))
        reason = message.response_metadata.get("finish_reason")
        self._termination = self.result_adapter.termination(reason if isinstance(reason, str) else None)
        return ConversionOutcome(
            ConversionStatus.UNSUPPORTED if unsupported else ConversionStatus.CONVERTED,
            tuple(events), diagnostics=tuple(diagnostics),
        )

    @staticmethod
    def _was_streamed(block: ContentBlock, index: int, run_id: str, state: _RunState) -> bool:
        """Determine whether a final SDK block was already represented by emitted run events.

        Args:
            block (ContentBlock): Framework content block being converted into the neutral contract.
            index (int): Position used to correlate an item within its message or stream.
            run_id (str): SDK run identity used to keep interleaved model output correlated.
            state (_RunState): The state that tracks the current operation lifecycle.
        """
        if block["type"] in (BlockKind.TOOL_CALL.value, BlockKind.SERVER_TOOL_CALL.value):
            return any(content.tool_id == block.get("id") and content.started for content in state.contents.values())
        return f"{run_id}:{block['type']}:{block.get('index', index)}" in state.contents

    @staticmethod
    def _close_run(state: _RunState) -> tuple[AgentStreamEvent, ...]:
        """Close all started content items owned by one SDK run and clear its pending fragments.

        Args:
            state (_RunState): The state that tracks the current operation lifecycle.
        """
        if state.closed:
            return ()
        if any(not content.started for content in state.contents.values()):
            raise LangChainConversionError("The SDK run ended before providing a tool identity and name.")
        state.closed = True
        return tuple(ContentEnd(content.content_id) for content in state.contents.values())

    def _tool_start(self, event: StreamEvent, call_id: str | None) -> ConversionOutcome:
        """Create the neutral start event for a fully identified tool invocation.

        Args:
            event (StreamEvent): The typed event whose content or lifecycle effect is processed.
            call_id (str | None): Stable tool invocation identity used to correlate its result.
        """
        run_id = event["run_id"]
        if run_id in self._tools:
            raise LangChainConversionError("A tool invocation started twice.")
        invocation = _ToolRun(call_id or run_id, event["name"])
        self._tools[run_id] = invocation
        arguments = JsonBoundary.convert(event["data"].get("input"))
        content = ToolCallContent(invocation.call_id, invocation.name, arguments, ToolExecution.INTERNAL)
        return ConversionOutcome(ConversionStatus.CONVERTED, (ContentEvent(f"{run_id}:invocation", content),))

    def _tool_end(self, event: StreamEvent) -> ConversionOutcome:
        """Close the tool invocation after its correlated result has been emitted.

        Args:
            event (StreamEvent): The typed event whose content or lifecycle effect is processed.
        """
        run_id = event["run_id"]
        invocation = self._tools.get(run_id)
        if invocation is None:
            return self.result_adapter.unsupported("unselected_tool_start", "Select both tool lifecycle events to expose a correlated observation.")
        output = event["data"].get("output")
        if isinstance(output, ToolMessage):
            result = JsonBoundary.convert(output.content)
        else:
            try:
                result = JsonBoundary.convert(output)
            except LangChainConversionError:
                return self.result_adapter.unsupported("unsupported_tool_output", "The native tool output is not a JSON value or SDK ToolMessage.")
        del self._tools[run_id]
        content = ToolResultContent(invocation.call_id, invocation.name, result, ToolExecution.INTERNAL)
        diagnostics: tuple[ConversionDiagnostic, ...] = ()
        status = ConversionStatus.CONVERTED
        if isinstance(output, ToolMessage) and output.status == "error":
            status = ConversionStatus.UNSUPPORTED
            diagnostics = (ConversionDiagnostic(
                "tool_result_status_unrepresentable", "The neutral tool result has no per-tool failure status.",
            ),)
        return ConversionOutcome(status, (ContentEvent(f"{run_id}:result", content),), diagnostics=diagnostics)

    def finish(self, termination: Termination | None = None) -> ConversionOutcome:
        """Close active content and emit the invocation’s single terminal event.

        Args:
            termination (Termination | None): Terminal outcome used to complete the result or stream.
        """
        # Failed runs close their started items without treating incomplete fragments as successful content; other runs use normal closure before the terminal event.
        if self._finished:
            return self._excluded("stream_finished", "The invocation is already terminal.")
        events: list[AgentStreamEvent] = []
        final = termination or self._termination
        for state in self._runs.values():
            if final.status is TerminationStatus.FAILED and not state.closed:
                events.extend(ContentEnd(content.content_id) for content in state.contents.values() if content.started)
                state.closed = True
            else:
                events.extend(self._close_run(state))
        events.append(TerminalEvent(final))
        self._finished = True
        return ConversionOutcome(ConversionStatus.CONVERTED, tuple(events))

    def _total_usage(self) -> TokenUsage:
        """Sum available usage snapshots across SDK runs and fail when no counts were supplied.
        """
        # Aggregate only counts actually supplied by each run and fail when there is no usage data instead of fabricating zero totals.
        total: TokenUsage | None = None
        for state in self._runs.values():
            if state.usage is not None:
                total = self._combine_usage(total, state.usage)
        if total is None:
            raise LangChainConversionError("No SDK token counts are available to aggregate.")
        return total

    @classmethod
    def _combine_usage(cls, current: TokenUsage | None, incoming: TokenUsage) -> TokenUsage:
        """Combine compatible usage snapshots while preserving unknown optional counters.

        Args:
            current (TokenUsage | None): Current state or value compared with an incoming update.
            incoming (TokenUsage): New state or value being merged with the current one.
        """
        if current is None:
            return incoming
        return TokenUsage(
            current.input_tokens + incoming.input_tokens,
            current.output_tokens + incoming.output_tokens,
            cls._sum_optional(current.total_tokens, incoming.total_tokens),
            cached_input_tokens=cls._sum_optional(current.cached_input_tokens, incoming.cached_input_tokens),
            reasoning_output_tokens=cls._sum_optional(current.reasoning_output_tokens, incoming.reasoning_output_tokens),
            cache_write_input_tokens=cls._sum_optional(current.cache_write_input_tokens, incoming.cache_write_input_tokens),
        )

    @staticmethod
    def _sum_optional(current: int | None, incoming: int | None) -> int | None:
        """Add optional token counters only when both values are known.

        Args:
            current (int | None): Current state or value compared with an incoming update.
            incoming (int | None): New state or value being merged with the current one.
        """
        if current is None or incoming is None:
            return None
        return current + incoming

    @staticmethod
    def notification(text: str, *, content_id: str) -> ConversionOutcome:
        """Only developer code decides whether a native event becomes a notice.

        Args:
            text (str): Text value or fragment carried by this content item.
            content_id (str): Stable identity correlating one content item across start, delta, and end events.
        """
        return ConversionOutcome(ConversionStatus.CONVERTED, (ContentEvent(content_id, Notification(text)),))

    @staticmethod
    def _excluded(code: str, reason: str) -> ConversionOutcome:
        """Return an excluded conversion outcome with a stable reason and diagnostic.

        Args:
            code (str): Stable error or diagnostic code returned to the caller.
            reason (str): Reason code or message associated with this decision or failure.
        """
        return ConversionOutcome(ConversionStatus.EXCLUDED, diagnostics=(ConversionDiagnostic(code, reason),))
