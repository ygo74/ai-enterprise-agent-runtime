from collections.abc import Callable
from typing import Protocol

from ygo74.agent_runtime.domains.contracts.exchange_models import (
    StandardExchangeResponse,
)


class MessagePipelineContext(Protocol):
    """Middleware context that carries the endpoint request and the response produced so far through the request pipeline.
    """
    request: object
    response: object | None


class Middleware(Protocol):
    """Protocol for a component that can inspect or update the message context before and after calling the next pipeline component.
    """
    def __call__(self, context: MessagePipelineContext, next_handler: Callable[[MessagePipelineContext], StandardExchangeResponse]) -> StandardExchangeResponse:
        """Implement the callable contract runtime data for the supplied input and execution context.

        Args:
            context (MessagePipelineContext): The execution context carrying identity and correlated metadata.
            next_handler (Callable[[MessagePipelineContext], StandardExchangeResponse]): Next middleware or handler in the execution pipeline.
        """
        ...
