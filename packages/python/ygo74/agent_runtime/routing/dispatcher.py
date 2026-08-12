from collections.abc import Callable
from typing import Protocol

from ygo74.agent_runtime.domains.contracts.exchange_models import StandardExchangeRequest, StandardExchangeResponse


class UseCaseHandler(Protocol):
    def __call__(self, request: StandardExchangeRequest) -> StandardExchangeResponse:
        ...


class Dispatcher(Protocol):
    def dispatch(self, request: StandardExchangeRequest, resolver: Callable[[str], UseCaseHandler]) -> StandardExchangeResponse:
        ...
