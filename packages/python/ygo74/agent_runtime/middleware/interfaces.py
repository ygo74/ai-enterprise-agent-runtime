from collections.abc import Callable
from typing import Protocol

from ygo74.agent_runtime.domains.contracts.exchange_models import StandardExchangeResponse


class MessagePipelineContext(Protocol):
    request: object
    response: object | None


class Middleware(Protocol):
    def __call__(self, context: MessagePipelineContext, next_handler: Callable[[MessagePipelineContext], StandardExchangeResponse]) -> StandardExchangeResponse:
        ...
