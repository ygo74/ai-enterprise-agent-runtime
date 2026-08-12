from dataclasses import dataclass
from typing import Any


@dataclass(slots=True)
class StandardStreamingExchangeEvent:
    request_id: str
    sequence: int
    event_type: str
    delta: Any | None = None
    final_output: Any | None = None
    error: dict[str, Any] | None = None
