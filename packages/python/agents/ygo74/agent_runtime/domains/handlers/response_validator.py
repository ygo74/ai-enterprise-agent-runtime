from ygo74.agent_runtime.domains.contracts.exchange_models import (
    StandardExchangeResponse,
)
from ygo74.agent_runtime.domains.mapping.output_normalizer import OutputNormalizer


def validate_response(response: StandardExchangeResponse) -> None:
    """Validate response and raise a domain-specific error when its constraints are not met.

    Args:
        response (StandardExchangeResponse): The response value to validate, transform, or return.
    """
    OutputNormalizer().normalize(response)
