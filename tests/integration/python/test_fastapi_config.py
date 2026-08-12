from ygo74.agent_runtime.domains.configuration.models import EndpointConfiguration
from ygo74.agent_runtime.domains.configuration.validator import validate_configuration


def test_configuration_valid() -> None:
    cfg = EndpointConfiguration(route_key="demo", enable_chat_completions=True)
    validate_configuration(cfg)
