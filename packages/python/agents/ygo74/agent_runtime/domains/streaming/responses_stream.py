import json
from dataclasses import replace

from ygo74.agent_runtime.domains.contracts.agent_output import (
    AgentContent,
    AgentOutput,
    Notification,
    ReasoningContent,
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
)
from ygo74.agent_runtime.domains.mapping.output_projector import OutputWireValues
from ygo74.agent_runtime.domains.mapping.responses_output import (
    ResponsesOutputProjector,
)
from ygo74.agent_runtime.domains.streaming.sse_encoder import WireEvent
from ygo74.agent_runtime.domains.streaming.stream_state import ContentState, StreamState


class ResponsesStreamProjector:
    done_marker = False

    def __init__(self) -> None:
        self._sequence = 0
        self._output = ResponsesOutputProjector()

    def _event(self, name: str, payload: dict[str, JsonValue]) -> WireEvent:
        event = WireEvent(
            {"type": name, "sequence_number": self._sequence, **payload}, name
        )
        self._sequence += 1
        return event

    def _response(self, state: StreamState, status: str) -> dict[str, JsonValue]:
        # Terminal status and items are owned by the runtime, never supplied by a provider.
        entries = [entry for entry in state.contents.values() if entry.supported]
        contents = tuple(self._snapshot_content(entry) for entry in entries)
        response = self._output.project(
            AgentOutput(contents, state.usage), state.context
        )
        response["status"] = status
        items: list[JsonValue] = []
        for entry, content in zip(entries, contents, strict=True):
            item = self._output.item(
                content,
                f"{state.context.response_id}_{entry.index}",
                in_progress=not entry.closed,
            )
            if not entry.closed and isinstance(content, ToolCallContent):
                item["arguments"] = "".join(entry.arguments)
            items.append(item)
        response["output"] = items
        return response

    @staticmethod
    def _wire_content(content: AgentContent) -> AgentContent:
        return (
            TextContent(content.text) if isinstance(content, Notification) else content
        )

    def _snapshot_content(self, entry: ContentState) -> AgentContent:
        content = self._wire_content(entry.content)
        if entry.closed:
            return content
        if isinstance(content, TextContent):
            return replace(content, text="".join(entry.text), annotations=())
        if isinstance(content, ReasoningContent):
            return replace(content, text="".join(entry.text))
        return content

    def start(self, state: StreamState) -> list[WireEvent]:
        response = self._response(state, "in_progress")
        return [
            self._event(name, {"response": response})
            for name in ("response.created", "response.in_progress")
        ]

    def project(self, event: AgentStreamEvent, state: StreamState) -> list[WireEvent]:
        if not isinstance(
            event, (ContentStart, ContentEnd, TextDelta, ToolArgumentsDelta)
        ):
            return []
        entry = state.contents[event.content_id]
        if not entry.supported:
            return []
        content = entry.content
        wire_content = self._wire_content(content)
        item_id = f"{state.context.response_id}_{entry.index}"
        coords: dict[str, JsonValue] = {"item_id": item_id, "output_index": entry.index}
        if isinstance(event, ContentStart):
            return self._start_content(wire_content, item_id, coords)
        if isinstance(event, ToolArgumentsDelta):
            return [
                self._event(
                    "response.function_call_arguments.delta",
                    {**coords, "delta": event.delta},
                )
            ]
        if isinstance(event, TextDelta):
            return [self._text_delta(content, coords, event.text)]
        item = self._output.item(wire_content, item_id)
        frames: list[WireEvent] = []
        if isinstance(content, ToolCallContent):
            frames.append(
                self._event(
                    "response.function_call_arguments.done",
                    {
                        **coords,
                        "name": content.name,
                        "arguments": json.dumps(content.arguments, ensure_ascii=True),
                    },
                )
            )
        elif isinstance(content, ReasoningContent):
            frames.extend(
                [
                    self._event(
                        "response.reasoning_summary_text.done",
                        {**coords, "summary_index": 0, "text": content.text},
                    ),
                    self._event(
                        "response.reasoning_summary_part.done",
                        {
                            **coords,
                            "summary_index": 0,
                            "part": {"type": "summary_text", "text": content.text},
                        },
                    ),
                ]
            )
        elif isinstance(content, (TextContent, Notification)):
            annotations = (
                OutputWireValues.citations(content)
                if isinstance(content, TextContent)
                else []
            )
            part: dict[str, JsonValue] = {
                "type": "output_text",
                "text": content.text,
                "annotations": annotations,
            }
            for index, annotation in enumerate(annotations):
                frames.append(
                    self._event(
                        "response.output_text.annotation.added",
                        {
                            **coords,
                            "content_index": 0,
                            "annotation_index": index,
                            "annotation": annotation,
                        },
                    )
                )
            frames.extend(
                [
                    self._event(
                        "response.output_text.done",
                        {
                            **coords,
                            "content_index": 0,
                            "text": content.text,
                            "logprobs": [],
                        },
                    ),
                    self._event(
                        "response.content_part.done",
                        {**coords, "content_index": 0, "part": part},
                    ),
                ]
            )
        frames.append(
            self._event(
                "response.output_item.done", {"output_index": entry.index, "item": item}
            )
        )
        return frames

    def _start_content(
        self,
        content: TextContent | ReasoningContent | ToolCallContent | object,
        item_id: str,
        coords: dict[str, JsonValue],
    ) -> list[WireEvent]:
        if not isinstance(content, (TextContent, ReasoningContent, ToolCallContent)):
            return []
        item = self._output.item(content, item_id, in_progress=True)
        if isinstance(content, ToolCallContent):
            item["arguments"] = ""
        else:
            item["summary" if isinstance(content, ReasoningContent) else "content"] = []
        frames = [
            self._event(
                "response.output_item.added",
                {"output_index": coords["output_index"], "item": item},
            )
        ]
        if isinstance(content, ToolCallContent):
            return frames
        if isinstance(content, ReasoningContent):
            frames.append(
                self._event(
                    "response.reasoning_summary_part.added",
                    {
                        **coords,
                        "summary_index": 0,
                        "part": {"type": "summary_text", "text": ""},
                    },
                )
            )
        else:
            frames.append(
                self._event(
                    "response.content_part.added",
                    {
                        **coords,
                        "content_index": 0,
                        "part": {"type": "output_text", "text": "", "annotations": []},
                    },
                )
            )
        if content.text:
            frames.append(self._text_delta(content, coords, content.text))
        return frames

    def _text_delta(
        self, content: object, coords: dict[str, JsonValue], text: str
    ) -> WireEvent:
        if isinstance(content, ReasoningContent):
            return self._event(
                "response.reasoning_summary_text.delta",
                {**coords, "summary_index": 0, "delta": text},
            )
        return self._event(
            "response.output_text.delta",
            {**coords, "content_index": 0, "delta": text, "logprobs": []},
        )

    def finish(self, termination: Termination, state: StreamState) -> list[WireEvent]:
        status = {
            TerminationStatus.SUCCESS: "completed",
            TerminationStatus.INCOMPLETE: "incomplete",
            TerminationStatus.FAILED: "failed",
        }[termination.status]
        response = self._response(state, status)
        if termination.error is not None:
            response["error"] = {
                "code": termination.error.code,
                "message": termination.error.message,
            }
        if termination.status == TerminationStatus.INCOMPLETE:
            response["incomplete_details"] = OutputWireValues.incomplete_details(
                termination, state.context
            )
        return [self._event(f"response.{status}", {"response": response})]
