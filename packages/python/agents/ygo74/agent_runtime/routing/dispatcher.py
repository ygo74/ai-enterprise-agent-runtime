from collections.abc import Callable
from typing import Protocol

from ygo74.agent_runtime.domains.contracts.exchange_models import (
    StandardExchangeRequest,
)
from ygo74.agent_runtime.domains.handlers.handler_protocol import (
    AgentInvocation,
    UseCaseHandler,
)

__all__ = ["Dispatcher", "UseCaseHandler"]


class Dispatcher(Protocol):
    def dispatch(
        self,
        request: StandardExchangeRequest,
        resolver: Callable[[str], UseCaseHandler],
    ) -> AgentInvocation: ...
