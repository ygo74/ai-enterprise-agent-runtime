from collections.abc import Callable

from ygo74.agent_runtime.domains.contracts.exchange_models import (
    StandardExchangeRequest,
    StandardExchangeResponse,
)


class RouteRegistry:
    """Maintain the validated agent routes and provide runtime lookup or registration operations.
    """
    def __init__(self) -> None:
        """Initialize the instance agent routes with supplied collaborators and configuration.
        """
        self._handlers: dict[str, Callable[[StandardExchangeRequest], StandardExchangeResponse]] = {}

    def register(self, route_key: str, handler: Callable[[StandardExchangeRequest], StandardExchangeResponse]) -> None:
        """Register agent routes after checking identity and uniqueness constraints.

        Args:
            route_key (str): The registered route key identifying the target agent or handler.
            handler (Callable[[StandardExchangeRequest], StandardExchangeResponse]): The registered application handler to invoke.
        """
        if route_key in self._handlers:
            raise ValueError("route already registered")
        self._handlers[route_key] = handler

    def resolve(self, route_key: str) -> Callable[[StandardExchangeRequest], StandardExchangeResponse]:
        """Resolve agent routes using configuration and registered candidates.

        Args:
            route_key (str): The registered route key identifying the target agent or handler.
        """
        if route_key not in self._handlers:
            raise KeyError(route_key)
        return self._handlers[route_key]
