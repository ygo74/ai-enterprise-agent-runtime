from ygo74.agent_runtime.domains.contracts.exchange_models import StandardExchangeRequest, StandardExchangeResponse
from ygo74.agent_runtime.domains.handlers.response_validator import validate_response


def test_handler_response_validator_accepts_success() -> None:
    _ = StandardExchangeRequest(request_id="r1", route_key="demo", endpoint_type="openai.responses", input="hi")
    response = StandardExchangeResponse(request_id="r1", status="success", output={"ok": True})
    validate_response(response)
