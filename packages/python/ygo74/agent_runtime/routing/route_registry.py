from collections.abc import Callable

from ygo74.agent_runtime.domains.contracts.exchange_models import StandardExchangeRequest, StandardExchangeResponse


class RouteRegistry:
    def __init__(self) -> None:
        self._handlers: dict[str, Callable[[StandardExchangeRequest], StandardExchangeResponse]] = {}

    def register(self, route_key: str, handler: Callable[[StandardExchangeRequest], StandardExchangeResponse]) -> None:
        if route_key in self._handlers:
            raise ValueError("route already registered")
        self._handlers[route_key] = handler

    def resolve(self, route_key: str) -> Callable[[StandardExchangeRequest], StandardExchangeResponse]:
        if route_key not in self._handlers:
            raise KeyError(route_key)
        return self._handlers[route_key]
