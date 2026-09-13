from typing import Any


def map_openai_chunk(request_id: str, sequence: int, delta: Any) -> dict[str, Any]:
    return {
        "request_id": request_id,
        "sequence": sequence,
        "event_type": "chunk",
        "delta": delta,
    }
