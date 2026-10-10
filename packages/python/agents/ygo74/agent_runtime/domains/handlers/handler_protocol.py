from collections.abc import AsyncIterable, Awaitable
from typing import Protocol

from ygo74.agent_runtime.domains.contracts.agent_output import AgentOutput
from ygo74.agent_runtime.domains.contracts.exchange_models import (
    StandardExchangeRequest,
    StandardExchangeResponse,
)
from ygo74.agent_runtime.domains.contracts.stream_events import AgentStreamEvent

AgentResult = AgentOutput | StandardExchangeResponse | AsyncIterable[AgentStreamEvent]
AgentInvocation = AgentResult | Awaitable[AgentResult]


class UseCaseHandler(Protocol):
    """Callable contract for application handlers that receive a normalized request and return typed output or a stream.
    """
    def __call__(self, request: StandardExchangeRequest) -> AgentInvocation:
        """Implement the callable contract runtime data for the supplied input and execution context.

        Args:
            request (StandardExchangeRequest): The request received at this layer, with its protocol-specific or normalized fields.
        """
        ...
