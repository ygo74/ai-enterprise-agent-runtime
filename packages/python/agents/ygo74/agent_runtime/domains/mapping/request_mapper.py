from ygo74.agent_runtime.domains.contracts.exchange_models import (
    StandardExchangeRequest,
)


def map_to_exchange(endpoint_type: str, payload: dict) -> StandardExchangeRequest:
    """Map to exchange between the source representation and the target contract.

    Args:
        endpoint_type (str): Protocol surface through which the request arrived.
        payload (dict): The payload being translated at the protocol boundary.
    """
    from ygo74.agent_runtime.domains.endpoints.adapters import normalize_request

    return normalize_request(endpoint_type, payload)
