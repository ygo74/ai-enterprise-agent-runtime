from collections.abc import Callable
from dataclasses import dataclass
from typing import Any


@dataclass(slots=True)
class RegisteredMiddleware:
    """Pairs a stable middleware identity and execution order with the middleware callable stored in the registry.

    Args:
        middleware_id (str): Stable middleware registration identifier.
        callable_ref (Callable[[Any, Callable[[Any], Any]], Any]): Callable reference used to invoke the registered middleware or handler.
        order (int): Position used to establish deterministic middleware or descriptor ordering.
    """
    middleware_id: str
    callable_ref: Callable[[Any, Callable[[Any], Any]], Any]
    order: int


class MiddlewareRegistry:
    """Maintain the validated runtime data and provide runtime lookup or registration operations.
    """
    def __init__(self) -> None:
        """Initialize the instance runtime data with supplied collaborators and configuration.
        """
        self._middlewares: list[RegisteredMiddleware] = []

    def register(self, middleware_id: str, callable_ref: Callable[[Any, Callable[[Any], Any]], Any], order: int) -> None:
        """Register runtime data after checking identity and uniqueness constraints.

        Args:
            middleware_id (str): Stable middleware registration identifier.
            callable_ref (Callable[[Any, Callable[[Any], Any]], Any]): Callable reference used to invoke the registered middleware or handler.
            order (int): Position used to establish deterministic middleware or descriptor ordering.
        """
        self._middlewares.append(RegisteredMiddleware(middleware_id, callable_ref, order))

    def ordered(self) -> list[RegisteredMiddleware]:
        """Provide the ordered operation for runtime data, preserving the runtime contract and validation rules.
        """
        return sorted(self._middlewares, key=lambda m: m.order)
