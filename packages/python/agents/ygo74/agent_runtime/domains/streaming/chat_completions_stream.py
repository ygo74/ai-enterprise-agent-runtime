import json

from ygo74.agent_runtime.domains.contracts.agent_output import (
    Notification,
    Termination,
    TerminationStatus,
    TextContent,
    ToolCallContent,
)
from ygo74.agent_runtime.domains.contracts.json_value import JsonValue
from ygo74.agent_runtime.domains.contracts.stream_events import (
    AgentStreamEvent,
    ContentEnd,
    ContentStart,
    TextDelta,
    ToolArgumentsDelta,
    UsageEvent,
)
from ygo74.agent_runtime.domains.mapping.output_projector import OutputWireValues
from ygo74.agent_runtime.domains.streaming.sse_encoder import WireEvent
from ygo74.agent_runtime.domains.streaming.stream_state import StreamState


class ChatCompletionsStreamProjector:
    done_marker = True

    def __init__(self) -> None:
        self._tool_indices: dict[str, int] = {}

    def _chunk(
        self,
        state: StreamState,
        delta: dict[str, JsonValue],
        finish: str | None = None,
        usage: dict[str, JsonValue] | None = None,
    ) -> WireEvent:
        context = state.context
        payload: dict[str, JsonValue] = {
            "id": context.request_id,
            "object": "chat.completion.chunk",
            "model": context.model,
            "created": context.created_at,
            "choices": [{"index": 0, "delta": delta, "finish_reason": finish}],
        }
        if usage is not None:
            payload["usage"] = usage
        return WireEvent(payload)

    def start(self, state: StreamState) -> list[WireEvent]:
        return [self._chunk(state, {"role": "assistant", "content": ""})]

    def project(self, event: AgentStreamEvent, state: StreamState) -> list[WireEvent]:
        if isinstance(event, UsageEvent):
            return []
        if not isinstance(
            event, (ContentStart, ContentEnd, TextDelta, ToolArgumentsDelta)
        ):
            return []
        entry = state.contents[event.content_id]
        if not entry.supported:
            return []
        if isinstance(event, ContentStart):
            content = event.content
            if isinstance(content, (TextContent, Notification)):
                return (
                    [self._chunk(state, {"content": content.text})]
                    if content.text
                    else []
                )
            if isinstance(content, ToolCallContent):
                index = len(self._tool_indices)
                self._tool_indices[event.content_id] = index
                return [
                    self._chunk(
                        state,
                        {
                            "tool_calls": [
                                {
                                    "index": index,
                                    "id": content.call_id,
                                    "type": "function",
                                    "function": {"name": content.name, "arguments": ""},
                                },
                            ]
                        },
                    )
                ]
        if isinstance(event, TextDelta):
            return [self._chunk(state, {"content": event.text})]
        if isinstance(event, ToolArgumentsDelta):
            return [self._tool_delta(state, event.content_id, event.delta)]
        if (
            isinstance(event, ContentEnd)
            and isinstance(entry.content, ToolCallContent)
            and not entry.arguments
        ):
            return [
                self._tool_delta(
                    state,
                    event.content_id,
                    json.dumps(entry.content.arguments, ensure_ascii=True),
                )
            ]
        return []

    def _tool_delta(self, state: StreamState, content_id: str, delta: str) -> WireEvent:
        return self._chunk(
            state,
            {
                "tool_calls": [
                    {
                        "index": self._tool_indices[content_id],
                        "function": {"arguments": delta},
                    },
                ]
            },
        )

    def finish(self, termination: Termination, state: StreamState) -> list[WireEvent]:
        if termination.status == TerminationStatus.FAILED:
            error = termination.error
            return [
                WireEvent(
                    {
                        "error": {
                            "code": error.code if error else "agent_execution_error",
                            "type": "server_error",
                            "message": error.message if error else "Agent failed",
                        }
                    }
                )
            ]
        finish = OutputWireValues.finish_reason(
            termination, state.context, has_tools=bool(self._tool_indices)
        )
        return [
            self._chunk(
                state,
                {},
                finish,
                OutputWireValues.usage(state.usage, state.context)
                if state.usage
                else None,
            )
        ]
