import json

from ygo74.agent_runtime.domains.contracts.agent_output import (
    AgentOutput,
    AudioContent,
    ToolCallContent,
)
from ygo74.agent_runtime.domains.contracts.json_value import JsonValue
from ygo74.agent_runtime.domains.contracts.media_content import EncodedMedia
from ygo74.agent_runtime.domains.mapping.output_projector import (
    ContentSupport,
    OutputWireValues,
    ProjectionContext,
)


class ChatCompletionsOutputProjector:
    def project(
        self, output: AgentOutput, context: ProjectionContext
    ) -> dict[str, JsonValue]:
        error = OutputWireValues.error(output, context)
        if error is not None:
            return error
        contents = ContentSupport().filter(output, context)
        calls: list[JsonValue] = [
            {
                "id": content.call_id,
                "type": "function",
                "function": {
                    "name": content.name,
                    "arguments": json.dumps(content.arguments, ensure_ascii=True),
                },
            }
            for content in contents
            if isinstance(content, ToolCallContent)
        ]
        message: dict[str, JsonValue] = {
            "role": "assistant",
            "content": OutputWireValues.text(contents),
        }
        if calls:
            message["tool_calls"] = calls
        audio = [content for content in contents if isinstance(content, AudioContent)]
        if audio:
            content = audio[0]
            if isinstance(content.source, EncodedMedia):
                message["audio"] = {
                    "id": content.audio_id,
                    "data": content.source.data,
                    "expires_at": content.expires_at,
                    "transcript": content.transcript or "",
                }
        finish = OutputWireValues.finish_reason(
            output.termination, context, has_tools=bool(calls)
        )
        response: dict[str, JsonValue] = {
            "id": context.request_id,
            "object": "chat.completion",
            "created": context.created_at,
            "model": context.model,
            "choices": [{"index": 0, "message": message, "finish_reason": finish}],
        }
        if output.usage is not None:
            usage = OutputWireValues.usage(output.usage, context)
            if usage is not None:
                response["usage"] = usage
        return response
