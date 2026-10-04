import json
from dataclasses import dataclass

from ygo74.agent_runtime.domains.contracts.json_value import JsonValue


@dataclass(frozen=True, slots=True)
class WireEvent:
    payload: dict[str, JsonValue]
    event: str | None = None


class SseEncoder:
    def encode(self, event: WireEvent) -> str:
        prefix = f"event: {event.event}\n" if event.event is not None else ""
        return f"{prefix}data: {json.dumps(event.payload, ensure_ascii=True, allow_nan=False)}\n\n"

    @staticmethod
    def done() -> str:
        return "data: [DONE]\n\n"
