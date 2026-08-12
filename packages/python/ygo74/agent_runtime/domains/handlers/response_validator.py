from ygo74.agent_runtime.domains.contracts.exchange_models import StandardExchangeResponse


def validate_response(response: StandardExchangeResponse) -> None:
    if response.status not in {"success", "error"}:
        raise ValueError("status must be success or error")
    if response.status == "success" and response.output is None:
        raise ValueError("success response must include output")
    if response.status == "error" and response.error is None:
        raise ValueError("error response must include error")
