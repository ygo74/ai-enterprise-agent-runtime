from ygo74.agent_runtime.domains.configuration.models import EndpointConfiguration


def validate_configuration(config: EndpointConfiguration) -> None:
    if not config.route_key:
        raise ValueError("route_key is required")

    if not (config.enable_chat_completions or config.enable_responses or config.enable_anthropic_messages):
        raise ValueError("At least one endpoint surface must be enabled")

    if config.enable_streaming and not (config.enable_chat_completions or config.enable_responses or config.enable_anthropic_messages):
        raise ValueError("Streaming requires at least one enabled endpoint")
