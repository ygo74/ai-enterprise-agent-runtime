from __future__ import annotations

from dataclasses import dataclass
from typing import Any


def auth_error(code: str, message: str, category: str, details: Any | None = None) -> dict[str, Any]:
    err: dict[str, Any] = {"code": code, "category": category, "message": message}
    if details is not None:
        err["details"] = details
    return err


@dataclass(slots=True)
class AuthenticationError(Exception):
    code: str
    message: str
    category: str = "authentication"
    details: Any | None = None

    def to_dict(self) -> dict[str, Any]:
        return auth_error(self.code, self.message, self.category, self.details)
