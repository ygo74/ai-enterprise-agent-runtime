from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class StandardExchangeRequest:
    request_id: str
    route_key: str
    endpoint_type: str
    input: Any
    stream: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)
    auth_context: dict[str, Any] | None = None


@dataclass(slots=True)
class StandardExchangeResponse:
    request_id: str
    status: str
    output: Any | None = None
    error: "ErrorEnvelope | None" = None
    metadata: dict[str, Any] = field(default_factory=dict)
