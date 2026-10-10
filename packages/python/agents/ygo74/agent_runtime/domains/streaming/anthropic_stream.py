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
    UsageEvent,
)
from ygo74.agent_runtime.domains.mapping.output_projector import OutputWireValues
from ygo74.agent_runtime.domains.streaming.sse_encoder import WireEvent
from ygo74.agent_runtime.domains.streaming.stream_state import StreamState


class AnthropicStreamProjector:
    """Translate typed runtime values into the framework stream events representation using protocol-specific mapping rules.
    """
    done_marker = False

    def __init__(self) -> None:
        """Initialize the instance framework stream events with supplied collaborators and configuration.
        """
        self._indices: dict[str, int] = {}
        self._has_tools = False
        self._started = False
        self._pending: list[WireEvent] = []

    @staticmethod
    def _event(name: str, payload: dict[str, JsonValue]) -> WireEvent:
        """Build one Anthropic server-sent event with the supplied event name and payload.

        Args:
            name (str): The name used to locate or label the value.
            payload (dict[str, JsonValue]): The payload being translated at the protocol boundary.
        """
        return WireEvent({"type": name, **payload}, name)

    def start(self, state: StreamState) -> list[WireEvent]:
        """Start framework stream events the current content or operation in the target protocol.

        Args:
            state (StreamState): The state that tracks the current operation lifecycle.
        """
        if self._started or state.usage is None:
            return []
        usage = OutputWireValues.anthropic_usage(state.usage, state.context)
        self._started = True
        return [
            self._event(
                "message_start",
                {
                    "message": {
                        "id": state.context.request_id,
                        "type": "message",
                        "role": "assistant",
                        "model": state.context.model,
                        "content": [],
                        "stop_reason": None,
                        "stop_sequence": None,
                        "usage": usage,
                    }
                },
            )
        ]

    def project(self, event: AgentStreamEvent, state: StreamState) -> list[WireEvent]:
        """Project framework stream events into the response shape required by the selected protocol.

        Args:
            event (AgentStreamEvent): The typed event whose content or lifecycle effect is processed.
            state (StreamState): The state that tracks the current operation lifecycle.
        """
        if isinstance(event, UsageEvent):
            frames = self.start(state) + self._pending
            self._pending = []
            return frames
        if not isinstance(event, (ContentStart, ContentEnd, TextDelta)):
            return []
        entry = state.contents[event.content_id]
        if not entry.supported:
            return []
        frames = self._content(event, state)
        if not frames:
            return []
        if state.usage is None:
            # Native SDKs may report real usage late. Preserve ordered frames
            # until then; never invent zero counters to start the message.
            self._pending.extend(frames)
            return []
        return self.start(state) + frames

    def _content(
        self, event: ContentStart | ContentEnd | TextDelta, state: StreamState
    ) -> list[WireEvent]:
        """Map neutral content to an Anthropic block and its start/stop lifecycle events.

        Args:
            event (ContentStart | ContentEnd | TextDelta): The typed event whose content or lifecycle effect is processed.
            state (StreamState): The state that tracks the current operation lifecycle.
        """
        entry = state.contents[event.content_id]
        content = entry.content
        if isinstance(content, ToolCallContent):
            # Delay tool blocks until arguments are validated; arrays are legal pivot JSON
            # but not legal Anthropic tool inputs, and must not leave orphan wire blocks.
            if not isinstance(event, ContentEnd):
                return []
            index = len(self._indices)
            self._indices[event.content_id] = index
            self._has_tools = True
            return [
                self._event(
                    "content_block_start",
                    {
                        "index": index,
                        "content_block": {
                            "type": "tool_use",
                            "id": content.call_id,
                            "name": content.name,
                            "input": {},
                        },
                    },
                ),
                self._event(
                    "content_block_delta",
                    {
                        "index": index,
                        "delta": {
                            "type": "input_json_delta",
                            "partial_json": json.dumps(
                                content.arguments, ensure_ascii=True
                            ),
                        },
                    },
                ),
                self._event("content_block_stop", {"index": index}),
            ]
        if not isinstance(content, (TextContent, Notification)):
            return []
        if isinstance(event, ContentStart):
            index = len(self._indices)
            self._indices[event.content_id] = index
            frames = [
                self._event(
                    "content_block_start",
                    {"index": index, "content_block": {"type": "text", "text": ""}},
                )
            ]
            if content.text:
                frames.append(self._text_delta(index, content.text))
            return frames
        index = self._indices[event.content_id]
        if isinstance(event, TextDelta):
            return [self._text_delta(index, event.text)]
        return [self._event("content_block_stop", {"index": index})]

    def _text_delta(self, index: int, text: str) -> WireEvent:
        """Encode one text delta in the Anthropic content-block delta shape.

        Args:
            index (int): Position used to correlate an item within its message or stream.
            text (str): Text value or fragment carried by this content item.
        """
        return self._event(
            "content_block_delta",
            {"index": index, "delta": {"type": "text_delta", "text": text}},
        )

    def finish(self, termination: Termination, state: StreamState) -> list[WireEvent]:
        """Finalize framework stream events the operation and emit its terminal representation.

        Args:
            termination (Termination): Terminal outcome used to complete the result or stream.
            state (StreamState): The state that tracks the current operation lifecycle.
        """
        if termination.status == TerminationStatus.FAILED:
            error = termination.error
            return [
                self._event(
                    "error",
                    {
                        "error": {
                            "type": "api_error",
                            "code": error.code if error else "agent_execution_error",
                            "message": error.message if error else "Agent failed",
                        }
                    },
                )
            ]
        stop = OutputWireValues.finish_reason(
            termination, state.context, has_tools=self._has_tools
        )
        payload: dict[str, JsonValue] = {
            "delta": {"stop_reason": stop, "stop_sequence": None},
            "usage": OutputWireValues.anthropic_usage(state.usage, state.context),
        }
        return self.start(state) + [
            self._event("message_delta", payload),
            self._event("message_stop", {}),
        ]
