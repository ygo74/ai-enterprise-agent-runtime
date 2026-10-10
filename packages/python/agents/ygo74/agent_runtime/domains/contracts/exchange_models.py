from dataclasses import dataclass, field
from typing import Any

from ygo74.agent_runtime.domains.contracts.agent_output import AgentOutput
from ygo74.agent_runtime.domains.contracts.error_envelope import ErrorEnvelope


@dataclass(slots=True)
class StandardExchangeRequest:
    """Provider-neutral request passed from endpoint routing to a use-case handler.

    Args:
        request_id (str): Identifier correlating the request with its handler result and response.
        route_key (str): Configured route selecting the target agent or use case.
        endpoint_type (str): Protocol surface through which the request arrived.
        input (Any): Normalized conversation input for the handler.
        stream (bool): Whether the client requested incremental output events.
        metadata (dict[str, Any]): Safe request metadata preserved across the exchange.
        auth_context (dict[str, Any] | None): Authenticated user identity and claims, when configured.
        provider_options (dict[str, Any] | None): Provider-specific options retained for response projection.
    """
    request_id: str
    route_key: str
    endpoint_type: str
    input: Any
    stream: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)
    auth_context: dict[str, Any] | None = None
    provider_options: dict[str, Any] | None = None


@dataclass(slots=True)
class StandardExchangeResponse:
    """Provider-neutral handler outcome returned to endpoint response projection.

    Args:
        request_id (str): Identifier correlating this result with its invocation.
        status (str): Success or failure status for the handler outcome.
        output (AgentOutput | None): Typed agent result when the handler succeeds.
        error (ErrorEnvelope | None): Structured error when the handler reports failure.
        metadata (dict[str, Any]): Safe response metadata preserved across the exchange.
    """
    request_id: str
    status: str
    output: AgentOutput | None = None
    error: ErrorEnvelope | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
