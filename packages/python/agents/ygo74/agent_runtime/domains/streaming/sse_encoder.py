import json
from dataclasses import dataclass

from ygo74.agent_runtime.domains.contracts.json_value import JsonValue


@dataclass(frozen=True, slots=True)
class WireEvent:
    """Represent a typed framework stream events event and the data required to process it safely.

    Args:
        payload (dict[str, JsonValue]): The payload being translated at the protocol boundary.
        event (str | None): The typed event whose content or lifecycle effect is processed.
    """
    payload: dict[str, JsonValue]
    event: str | None = None


class SseEncoder:
    """Encodes typed provider events as server-sent event frames and emits the stream completion marker.
    """
    def encode(self, event: WireEvent) -> str:
        """Encode framework stream events as a server-sent event or protocol wire value.

        Args:
            event (WireEvent): The typed event whose content or lifecycle effect is processed.
        """
        prefix = f"event: {event.event}\n" if event.event is not None else ""
        return f"{prefix}data: {json.dumps(event.payload, ensure_ascii=True, allow_nan=False)}\n\n"

    @staticmethod
    def done() -> str:
        """Encode the terminal SSE marker used to tell clients that the stream is complete.
        """
        return "data: [DONE]\n\n"
