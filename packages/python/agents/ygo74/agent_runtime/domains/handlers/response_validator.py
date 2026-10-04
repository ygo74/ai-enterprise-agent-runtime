from ygo74.agent_runtime.domains.contracts.exchange_models import (
    StandardExchangeResponse,
)
from ygo74.agent_runtime.domains.mapping.output_normalizer import OutputNormalizer


def validate_response(response: StandardExchangeResponse) -> None:
    OutputNormalizer().normalize(response)
