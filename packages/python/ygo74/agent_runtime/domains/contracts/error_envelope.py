from dataclasses import dataclass
from typing import Any


@dataclass(slots=True)
class ErrorEnvelope:
    code: str
    category: str
    message: str
    details: Any | None = None
    request_id: str | None = None
    retryable: bool | None = None
