from dataclasses import dataclass
from typing import Any, Callable


@dataclass(slots=True)
class RegisteredMiddleware:
    middleware_id: str
    callable_ref: Callable[[Any, Callable[[Any], Any]], Any]
    order: int


class MiddlewareRegistry:
    def __init__(self) -> None:
        self._middlewares: list[RegisteredMiddleware] = []

    def register(self, middleware_id: str, callable_ref: Callable[[Any, Callable[[Any], Any]], Any], order: int) -> None:
        self._middlewares.append(RegisteredMiddleware(middleware_id, callable_ref, order))

    def ordered(self) -> list[RegisteredMiddleware]:
        return sorted(self._middlewares, key=lambda m: m.order)
