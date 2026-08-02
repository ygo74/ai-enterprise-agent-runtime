from ygo74.agent_runtime.domains.contracts.exchange_models import StandardExchangeRequest, StandardExchangeResponse


def basic_handler(request: StandardExchangeRequest) -> StandardExchangeResponse:
    return StandardExchangeResponse(request_id=request.request_id, status="success", output={"message": "ok"})
