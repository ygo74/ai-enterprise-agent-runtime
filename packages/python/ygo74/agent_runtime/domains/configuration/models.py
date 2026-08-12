from dataclasses import dataclass


@dataclass(slots=True)
class EndpointConfiguration:
    route_key: str
    enable_chat_completions: bool = False
    enable_responses: bool = False
    enable_anthropic_messages: bool = False
    enable_streaming: bool = False
