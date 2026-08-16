"""Initialization-time validation of declared capabilities against real configuration."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

from ygo74.agent_runtime.domains.configuration.models import EndpointConfiguration
from ygo74.agent_runtime.domains.discovery.agent_descriptor import AgentDescriptor
from ygo74.agent_runtime.domains.discovery.discovery_errors import DiscoveryErrors


@dataclass(slots=True)
class CapabilityValidator:
    """Rejects descriptors whose claims contradict the effective endpoint configuration.

    Discovery is only trustworthy if an advertised capability is actually
    reachable, so a contradiction fails initialization instead of degrading
    silently at request time.
    """

    configurations_by_route_key: Mapping[str, EndpointConfiguration]

    def validate(self, descriptor: AgentDescriptor) -> None:
        configuration = self.configurations_by_route_key.get(descriptor.route_key)
        if configuration is None:
            raise DiscoveryErrors.unresolved_route_key(descriptor.agent_id, descriptor.route_key)

        if descriptor.capabilities.streaming and not configuration.enable_streaming:
            raise DiscoveryErrors.capability_contradiction(
                descriptor.agent_id,
                "streaming",
                f"streaming is disabled for route '{descriptor.route_key}'",
            )

        if not _has_enabled_surface(configuration):
            raise DiscoveryErrors.capability_contradiction(
                descriptor.agent_id,
                "endpointExposure",
                f"route '{descriptor.route_key}' exposes no invocation endpoint",
            )

    def validate_all(self, descriptors: tuple[AgentDescriptor, ...]) -> None:
        for descriptor in descriptors:
            self.validate(descriptor)


def _has_enabled_surface(configuration: EndpointConfiguration) -> bool:
    return (
        configuration.enable_chat_completions
        or configuration.enable_responses
        or configuration.enable_anthropic_messages
    )
