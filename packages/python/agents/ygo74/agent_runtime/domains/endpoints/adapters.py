from ygo74.agent_runtime.domains.contracts.exchange_models import (
    StandardExchangeRequest,
)
from ygo74.agent_runtime.domains.endpoints.openai_responses import (
    OpenAIResponsesCreateRequest,
)

_SUPPORTED = {"openai.chat_completions", "openai.responses", "anthropic.messages"}


def normalize_request(endpoint_type: str, payload: dict) -> StandardExchangeRequest:
    """Convert a protocol payload into the standard exchange request while preserving safe request metadata.

    Args:
        endpoint_type (str): Protocol surface through which the request arrived.
        payload (dict): The input or output payload being translated at the protocol boundary.
    """
    if endpoint_type not in _SUPPORTED:
        raise ValueError(f"Unsupported endpoint type: {endpoint_type}")

    metadata = dict(payload.get("metadata") or {})
    if "model" in payload:
        metadata.setdefault("model", payload["model"])

    responses_request = OpenAIResponsesCreateRequest.from_payload(payload) if endpoint_type == "openai.responses" else None

    return StandardExchangeRequest(
        request_id=payload.get("request_id", ""),
        route_key=payload.get("route_key", ""),
        endpoint_type=endpoint_type,
        input=responses_request.input if responses_request is not None else payload.get("input"),
        stream=bool(payload.get("stream", False)),
        metadata=metadata,
        auth_context=payload.get("auth_context"),
        provider_options=responses_request.provider_options if responses_request is not None else None,
    )
