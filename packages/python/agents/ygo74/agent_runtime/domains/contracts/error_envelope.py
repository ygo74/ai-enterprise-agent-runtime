from dataclasses import dataclass
from typing import Any


@dataclass(slots=True)
class ErrorEnvelope:
    """Represent a structured ErrorEnvelope failure so callers can handle the condition consistently.

    Args:
        code (str): Stable error or diagnostic code returned to the caller.
        category (str): Content or error category used to select the applicable mapping.
        message (str): Framework message or protocol message being converted.
        details (Any | None): Framework-provided token counters to validate and aggregate.
        request_id (str | None): Correlation identifier for the incoming request and its response.
        retryable (bool | None): Whether the reported error may succeed if the client retries.
    """
    code: str
    category: str
    message: str
    details: Any | None = None
    request_id: str | None = None
    retryable: bool | None = None
