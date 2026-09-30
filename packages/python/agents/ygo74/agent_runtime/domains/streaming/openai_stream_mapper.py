import json
from typing import Any

from ygo74.agent_runtime.domains.contracts.stream_events import (
    OpenAIResponsesStreamEvent,
    OpenAIResponsesStreamEventType,
)


def map_openai_chunk(request_id: str, sequence: int, delta: Any) -> dict[str, Any]:
    return {
        "request_id": request_id,
        "sequence": sequence,
        "event_type": "chunk",
        "delta": delta,
    }


class OpenAIResponsesStreamEncoder:
    """Encodes Responses event values as Server-Sent Events."""

    def create_event(self, payload: dict[str, Any]) -> OpenAIResponsesStreamEvent:
        event_name = payload.get("type")
        event_type = OpenAIResponsesStreamEventType(event_name)
        return OpenAIResponsesStreamEvent(event_type=event_type, payload=dict(payload))

    def encode(self, event: OpenAIResponsesStreamEvent) -> str:
        payload_type = event.payload.get("type")
        if payload_type != event.event_type.value:
            raise ValueError("Responses event type must match the payload type")

        data = json.dumps(event.payload, ensure_ascii=True)
        return f"event: {event.event_type.value}\ndata: {data}\n\n"
