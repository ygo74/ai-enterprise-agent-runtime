from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

from ygo74.agent_runtime.domains.discovery.agent_descriptor import AgentDescriptor


@dataclass(slots=True)
class EndpointConfiguration:
    """Groups endpoint settings, handlers, route keys, discovery descriptors, and authentication options for one runtime.

    Args:
        route_key (str): The registered route key that identifies the target agent or handler.
        enable_chat_completions (bool): Whether the OpenAI Chat Completions route is exposed.
        enable_responses (bool): Whether the OpenAI Responses route is exposed.
        enable_anthropic_messages (bool): Whether the Anthropic Messages route is exposed.
        enable_streaming (bool): Whether streaming responses are permitted for this agent.
        agent_descriptor (AgentDescriptor | None): Optional canonical identity and capability descriptor for discovery.
    """
    route_key: str
    enable_chat_completions: bool = False
    enable_responses: bool = False
    enable_anthropic_messages: bool = False
    enable_streaming: bool = False
    agent_descriptor: AgentDescriptor | None = None

    @classmethod
    def from_dict(cls, source: Mapping[str, Any]) -> EndpointConfiguration:
        """Bind from a framework-native configuration section.

        The optional ``agentDescriptor`` section is the declarative form of the
        discovery single source of truth, so a host declares identity and
        capabilities in the same settings block that enables the endpoints.

        Args:
            source (Mapping[str, Any]): The source value being read, validated, or converted.
        """
        raw_descriptor = source.get("agentDescriptor")
        return cls(
            route_key=str(source["routeKey"]),
            enable_chat_completions=bool(source.get("enableChatCompletions", False)),
            enable_responses=bool(source.get("enableResponses", False)),
            enable_anthropic_messages=bool(source.get("enableAnthropicMessages", False)),
            enable_streaming=bool(source.get("enableStreaming", False)),
            agent_descriptor=(
                AgentDescriptor.from_dict(raw_descriptor) if isinstance(raw_descriptor, Mapping) else None
            ),
        )


@dataclass(slots=True)
class RuntimeConfiguration:
    """Aggregate of every configured route, keyed for descriptor validation.

    Args:
        endpoints (tuple[EndpointConfiguration, ...]): Endpoint configurations registered in this runtime.
    """
    endpoints: tuple[EndpointConfiguration, ...] = field(default_factory=tuple)

    @property
    def by_route_key(self) -> dict[str, EndpointConfiguration]:
        """Look up the endpoint configuration associated with a route key.
        """
        return {endpoint.route_key: endpoint for endpoint in self.endpoints}

    @property
    def declared_descriptors(self) -> tuple[AgentDescriptor, ...]:
        """Return the explicitly declared agent descriptors without deriving defaults.
        """
        return tuple(
            endpoint.agent_descriptor for endpoint in self.endpoints if endpoint.agent_descriptor is not None
        )
