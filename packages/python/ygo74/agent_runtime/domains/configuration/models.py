from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

from ygo74.agent_runtime.domains.discovery.agent_descriptor import AgentDescriptor


@dataclass(slots=True)
class EndpointConfiguration:
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
    """Aggregate of every configured route, keyed for descriptor validation."""

    endpoints: tuple[EndpointConfiguration, ...] = field(default_factory=tuple)

    @property
    def by_route_key(self) -> dict[str, EndpointConfiguration]:
        return {endpoint.route_key: endpoint for endpoint in self.endpoints}

    @property
    def declared_descriptors(self) -> tuple[AgentDescriptor, ...]:
        return tuple(
            endpoint.agent_descriptor for endpoint in self.endpoints if endpoint.agent_descriptor is not None
        )
