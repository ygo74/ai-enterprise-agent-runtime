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
    def __call__(self, request: StandardExchangeRequest) -> AgentInvocation: ...
