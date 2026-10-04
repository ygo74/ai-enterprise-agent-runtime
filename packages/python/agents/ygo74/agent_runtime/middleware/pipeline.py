from collections.abc import Callable
from typing import Any


def execute_pipeline(context: Any, middlewares: list[Callable[[Any, Callable[[Any], Any]], Any]], handler: Callable[[Any], Any]) -> Any:
    """Execute pipeline through the configured handler or middleware chain.

    Args:
        context (Any): The execution context carrying identity and correlated metadata.
        middlewares (list[Callable[[Any, Callable[[Any], Any]], Any]]): Middleware callables executed in their registered order.
        handler (Callable[[Any], Any]): The registered application handler to invoke.
    """
    def chain(index: int, ctx: Any) -> Any:
        """Provide the chain operation for runtime data, preserving the runtime contract and validation rules.

        Args:
            index (int): Position used to correlate an item within its message or stream.
            ctx (Any): Message context passed from one middleware to the next.
        """
        if index >= len(middlewares):
            return handler(ctx)

        return middlewares[index](ctx, lambda next_ctx: chain(index + 1, next_ctx))

    return chain(0, context)
