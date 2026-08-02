from collections.abc import Callable
from typing import Any


def execute_pipeline(context: Any, middlewares: list[Callable[[Any, Callable[[Any], Any]], Any]], handler: Callable[[Any], Any]) -> Any:
    def chain(index: int, ctx: Any) -> Any:
        if index >= len(middlewares):
            return handler(ctx)

        return middlewares[index](ctx, lambda next_ctx: chain(index + 1, next_ctx))

    return chain(0, context)
