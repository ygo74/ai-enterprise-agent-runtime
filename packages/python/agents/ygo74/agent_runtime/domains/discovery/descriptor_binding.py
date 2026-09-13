"""Binding validation between descriptors and the dispatch route registry."""

from __future__ import annotations

from dataclasses import dataclass

from ygo74.agent_runtime.domains.discovery.agent_descriptor import AgentDescriptor
from ygo74.agent_runtime.domains.discovery.descriptor_registry import DescriptorRegistry
from ygo74.agent_runtime.domains.discovery.discovery_errors import DiscoveryErrors
from ygo74.agent_runtime.routing.route_registry import RouteRegistry


@dataclass(slots=True)
class DescriptorBinding:
    """Verifies every descriptor resolves to a registered handler.

    This is what makes the discovery-to-invocation round trip a guarantee rather
    than a hope: an advertised identifier is rejected at startup unless its route
    is dispatchable.
    """

    route_registry: RouteRegistry

    def validate(self, descriptor: AgentDescriptor) -> None:
        try:
            self.route_registry.resolve(descriptor.route_key)
        except KeyError as exc:
            raise DiscoveryErrors.unresolved_route_key(descriptor.agent_id, descriptor.route_key) from exc

    def validate_registry(self, descriptor_registry: DescriptorRegistry) -> None:
        for descriptor in descriptor_registry.list_all():
            self.validate(descriptor)
