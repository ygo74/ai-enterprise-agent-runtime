from ygo74.agent_runtime.domains.contracts.exchange_models import StandardExchangeRequest


def map_to_exchange(endpoint_type: str, payload: dict) -> StandardExchangeRequest:
    from ygo74.agent_runtime.domains.endpoints.adapters import normalize_request

    return normalize_request(endpoint_type, payload)
