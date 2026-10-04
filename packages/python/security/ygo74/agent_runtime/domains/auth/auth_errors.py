from __future__ import annotations

from dataclasses import dataclass
from typing import Any


def auth_error(code: str, message: str, category: str, details: Any | None = None) -> dict[str, Any]:
    """Create a structured authentication error with a safe message and protocol status.

    Args:
        code (str): Stable error or diagnostic code returned to the caller.
        message (str): Framework message or protocol message being converted.
        category (str): Content or error category used to select the applicable mapping.
        details (Any | None): Framework-provided token counters to validate and aggregate.
    """
    err: dict[str, Any] = {"code": code, "category": category, "message": message}
    if details is not None:
        err["details"] = details
    return err


@dataclass(slots=True)
class AuthenticationError(Exception):
    """Represent a structured AuthenticationError failure so callers can handle the condition consistently.

    Args:
        code (str): Stable error or diagnostic code returned to the caller.
        message (str): Framework message or protocol message being converted.
        category (str): Content or error category used to select the applicable mapping.
        details (Any | None): Framework-provided token counters to validate and aggregate.
    """
    code: str
    message: str
    category: str = "authentication"
    details: Any | None = None

    def to_dict(self) -> dict[str, Any]:
        """Serialize the instance runtime data into its documented dictionary representation.
        """
        return auth_error(self.code, self.message, self.category, self.details)


@dataclass(slots=True)
class AuthorizationError(Exception):
    """Raised by developer-owned authorization logic to deny an authenticated request.

    The runtime never raises this itself: authorization decisions belong to the
    handler. When raised, the runtime short-circuits handler execution and maps
    it to an HTTP 403 with a structured error envelope.

    Args:
        code (str): Stable error or diagnostic code returned to the caller.
        message (str): Framework message or protocol message being converted.
        category (str): Content or error category used to select the applicable mapping.
        details (Any | None): Framework-provided token counters to validate and aggregate.
    """
    code: str = "forbidden"
    message: str = "Access denied"
    category: str = "authorization"
    details: Any | None = None

    def to_dict(self) -> dict[str, Any]:
        """Serialize the instance runtime data into its documented dictionary representation.
        """
        return auth_error(self.code, self.message, self.category, self.details)
