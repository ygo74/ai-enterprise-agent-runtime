from collections.abc import Callable

from ygo74.agent_runtime.domains.contracts.exchange_models import (
    StandardExchangeRequest,
)
from ygo74.agent_runtime.domains.handlers.handler_protocol import AgentInvocation
from ygo74.agent_runtime.routing.dispatcher import Dispatcher, UseCaseHandler


class DispatcherImpl(Dispatcher):
    def dispatch(
        self,
        request: StandardExchangeRequest,
        resolver: Callable[[str], UseCaseHandler],
    ) -> AgentInvocation:
        handler = resolver(request.route_key)
        return handler(request)
