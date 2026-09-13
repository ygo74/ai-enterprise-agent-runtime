from typing import Protocol

from ygo74.agent_runtime.domains.contracts.exchange_models import StandardExchangeRequest, StandardExchangeResponse


class UseCaseHandler(Protocol):
    def __call__(self, request: StandardExchangeRequest) -> StandardExchangeResponse:
        ...
