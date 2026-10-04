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
    """Protocol for resolving a route and invoking the use-case handler registered for it.
    """
    def dispatch(
        self,
        request: StandardExchangeRequest,
        resolver: Callable[[str], UseCaseHandler],
    ) -> AgentInvocation:
        """Dispatch runtime data to the handler registered for the resolved route.

        Args:
            request (StandardExchangeRequest): The request received at this layer, with its protocol-specific or normalized fields.
            resolver (Callable[[str], UseCaseHandler]): Callback that resolves a route key to its registered handler.
        """
        ...
