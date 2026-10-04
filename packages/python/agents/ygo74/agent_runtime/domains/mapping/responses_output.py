import json

from ygo74.agent_runtime.domains.contracts.agent_output import (
    AgentContent,
    AgentOutput,
    ReasoningContent,
    TerminationStatus,
    TextContent,
    ToolCallContent,
)
from ygo74.agent_runtime.domains.contracts.json_value import JsonValue
from ygo74.agent_runtime.domains.mapping.output_projector import (
    ContentSupport,
    OutputWireValues,
    ProjectionContext,
)


class ResponsesOutputProjector:
    def item(
        self, content: AgentContent, item_id: str, *, in_progress: bool = False
    ) -> dict[str, JsonValue]:
        status = "in_progress" if in_progress else "completed"
        if isinstance(content, ToolCallContent):
            return {
                "id": item_id,
                "type": "function_call",
                "status": status,
                "call_id": content.call_id,
                "name": content.name,
                "arguments": json.dumps(content.arguments, ensure_ascii=True),
            }
        if isinstance(content, ReasoningContent):
            return {
                "id": item_id,
                "type": "reasoning",
                "summary": [{"type": "summary_text", "text": content.text}],
            }
        if isinstance(content, TextContent):
            return {
                "id": item_id,
                "type": "message",
                "role": "assistant",
                "status": status,
                "content": [
                    {
                        "type": "output_text",
                        "text": content.text,
                        "annotations": OutputWireValues.citations(content),
                    }
                ],
            }
        raise ValueError("Responses item must be a supported content")

    def project(
        self, output: AgentOutput, context: ProjectionContext
    ) -> dict[str, JsonValue]:
        error = OutputWireValues.error(output, context)
        if error is not None:
            return error
        contents = ContentSupport().filter(output, context)
        response: dict[str, JsonValue] = dict(context.provider_options)
        response.update(
            {
                "id": context.response_id,
                "object": "response",
                "created_at": context.created_at,
                "model": context.model,
                "status": "incomplete"
                if output.termination.status == TerminationStatus.INCOMPLETE
                else "completed",
                "output": [
                    self.item(content, f"{context.response_id}_{index}")
                    for index, content in enumerate(contents)
                ],
                "output_text": OutputWireValues.text(contents),
                "error": None,
                "incomplete_details": OutputWireValues.incomplete_details(
                    output.termination, context
                ),
            }
        )
        response.pop("stream", None)
        response["usage"] = None
        response.setdefault("parallel_tool_calls", True)
        response.setdefault("tool_choice", "auto")
        response.setdefault("tools", [])
        response["metadata"] = dict(context.request_metadata)
        if output.usage is not None:
            response["usage"] = OutputWireValues.usage(output.usage, context)
        return response
