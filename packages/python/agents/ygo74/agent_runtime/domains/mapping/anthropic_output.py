from ygo74.agent_runtime.domains.contracts.agent_output import (
    AgentOutput,
    TextContent,
    ToolCallContent,
)
from ygo74.agent_runtime.domains.contracts.json_value import JsonValue
from ygo74.agent_runtime.domains.mapping.output_projector import (
    ContentSupport,
    OutputWireValues,
    ProjectionContext,
)


class AnthropicOutputProjector:
    """Translate typed runtime values into the Anthropic responses representation using protocol-specific mapping rules.
    """
    def project(
        self, output: AgentOutput, context: ProjectionContext
    ) -> dict[str, JsonValue]:
        """Project neutral output into an Anthropic Messages response.

        Filter unsupported items first, then map text and client-facing tool calls
        into content blocks. Derive the stop reason from termination and whether a
        tool-use block remains.

        Args:
            output (AgentOutput): Typed agent output being validated, filtered, or projected.
            context (ProjectionContext): The execution context carrying identity and correlated metadata.
        """
        # Filter unsupported content before projection, then map the surviving text and tool calls and derive the stop reason from whether a tool call remains.
        error = OutputWireValues.error(output, context)
        if error is not None:
            return error
        usage = OutputWireValues.anthropic_usage(output.usage, context)
        contents = ContentSupport().filter(output, context)
        blocks: list[JsonValue] = []
        has_tool = False
        for content in contents:
            if isinstance(content, TextContent):
                blocks.append({"type": "text", "text": content.text})
            elif isinstance(content, ToolCallContent):
                blocks.append(
                    {
                        "type": "tool_use",
                        "id": content.call_id,
                        "name": content.name,
                        "input": content.arguments,
                    }
                )
                has_tool = True
        response: dict[str, JsonValue] = {
            "id": context.request_id,
            "type": "message",
            "role": "assistant",
            "model": context.model,
            "content": blocks,
            "stop_reason": OutputWireValues.finish_reason(
                output.termination, context, has_tools=has_tool
            ),
            "stop_sequence": None,
        }
        response["usage"] = usage
        return response
