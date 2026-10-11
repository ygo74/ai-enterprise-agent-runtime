from collections.abc import Callable

from ygo74.agent_runtime.domains.contracts.exchange_models import (
    StandardExchangeRequest,
)
from ygo74.agent_runtime.domains.handlers.handler_protocol import AgentInvocation
from ygo74.agent_runtime.routing.dispatcher import Dispatcher, UseCaseHandler


class DispatcherImpl(Dispatcher):
    """Dispatches normalized exchange requests to the registered handler and validates the handler result.
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
        handler = resolver(request.route_key)
        return handler(request)
