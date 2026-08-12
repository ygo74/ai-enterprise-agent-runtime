from ygo74.agent_runtime.domains.contracts.exchange_models import StandardExchangeRequest

_SUPPORTED = {"openai.chat_completions", "openai.responses", "anthropic.messages"}


def normalize_request(endpoint_type: str, payload: dict) -> StandardExchangeRequest:
    if endpoint_type not in _SUPPORTED:
        raise ValueError(f"Unsupported endpoint type: {endpoint_type}")

    metadata = dict(payload.get("metadata") or {})
    if "model" in payload:
        metadata.setdefault("model", payload["model"])

    return StandardExchangeRequest(
        request_id=payload.get("request_id", ""),
        route_key=payload.get("route_key", ""),
        endpoint_type=endpoint_type,
        input=payload.get("input"),
        stream=bool(payload.get("stream", False)),
        metadata=metadata,
        auth_context=payload.get("auth_context"),
    )
