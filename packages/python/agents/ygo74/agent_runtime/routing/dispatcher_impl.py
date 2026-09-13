from collections.abc import Callable

from ygo74.agent_runtime.domains.contracts.exchange_models import StandardExchangeRequest, StandardExchangeResponse


class DispatcherImpl:
    def dispatch(self, request: StandardExchangeRequest, resolver: Callable[[str], Callable[[StandardExchangeRequest], StandardExchangeResponse]]) -> StandardExchangeResponse:
        handler = resolver(request.route_key)
        return handler(request)
