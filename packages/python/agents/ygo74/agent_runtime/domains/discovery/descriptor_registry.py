"""Descriptor registry: uniqueness, exact lookup, and deterministic ordering."""

from __future__ import annotations

from collections.abc import Iterable, Iterator
from enum import StrEnum

from ygo74.agent_runtime.domains.discovery.agent_descriptor import AgentDescriptor
from ygo74.agent_runtime.domains.discovery.discovery_errors import DiscoveryErrors


class DescriptorOrdering(StrEnum):
    """Defined listing orders. Ascending agentId is the only cross-language guarantee."""
    AGENT_ID_ASCENDING = "agent_id_ascending"


class DescriptorRegistry:
    """Initialization-time collection of every agent descriptor.

    Ordering uses ascending ``agent_id`` with case-sensitive Unicode code-point
    comparison, which is Python's default string ordering. This is the only
    defined order and must match the .NET and Java implementations.

    Args:
        descriptors (Iterable[AgentDescriptor] | None): Agent descriptors to validate, order, or register.
        ordering (DescriptorOrdering): Strategy that determines stable registry iteration order.
    """
    def __init__(
        self,
        descriptors: Iterable[AgentDescriptor] | None = None,
        *,
        ordering: DescriptorOrdering = DescriptorOrdering.AGENT_ID_ASCENDING,
    ) -> None:
        """Initialize the instance agent descriptors with the supplied collaborators and configuration.

        Args:
            descriptors (Iterable[AgentDescriptor] | None): Agent descriptors to validate, order, or register.
            ordering (DescriptorOrdering): Strategy that determines stable registry iteration order.
        """
        self._descriptors: dict[str, AgentDescriptor] = {}
        self._by_route_key: dict[str, AgentDescriptor] = {}
        self._ordering = ordering
        for descriptor in descriptors or ():
            self.register(descriptor)

    @property
    def ordering(self) -> DescriptorOrdering:
        """Return descriptors in stable public-identifier order for repeatable discovery pages.
        """
        return self._ordering

    def __len__(self) -> int:
        """Return the number of registered entries agent descriptors without exposing the backing collection.
        """
        return len(self._descriptors)

    def __iter__(self) -> Iterator[AgentDescriptor]:
        """Iterate over the registered entries agent descriptors in their documented deterministic order.
        """
        return iter(self.list_all())

    def __contains__(self, agent_id: object) -> bool:
        """Check whether the requested entry is registered agent descriptors using the registry identity rules.

        Args:
            agent_id (object): Public identifier of the agent being registered or discovered.
        """
        return isinstance(agent_id, str) and agent_id in self._descriptors

    def register(self, descriptor: AgentDescriptor) -> None:
        """Add a descriptor, failing fast on a duplicate public identifier.

        Args:
            descriptor (AgentDescriptor): The canonical agent descriptor whose identity and capabilities are used.
        """
        if descriptor.agent_id in self._descriptors:
            raise DiscoveryErrors.duplicate_agent_id(descriptor.agent_id)
        self._descriptors[descriptor.agent_id] = descriptor
        self._by_route_key[descriptor.route_key] = descriptor

    def register_all(self, descriptors: Iterable[AgentDescriptor]) -> None:
        """Register all after checking the identity and uniqueness constraints.

        Args:
            descriptors (Iterable[AgentDescriptor]): Agent descriptors to validate, order, or register.
        """
        for descriptor in descriptors:
            self.register(descriptor)

    def find(self, agent_id: str) -> AgentDescriptor | None:
        """Exact, case-sensitive, O(1) lookup. Returns ``None`` when absent.

        Args:
            agent_id (str): Public identifier of the agent being registered or discovered.
        """
        return self._descriptors.get(agent_id)

    def find_by_route_key(self, route_key: str) -> AgentDescriptor | None:
        """Exact lookup by internal route key, used to gate invocation by descriptor.

        If two descriptors were registered with the same ``route_key`` (unusual,
        and not otherwise validated), the most recently registered one wins.

        Args:
            route_key (str): The registered route key that identifies the target agent or handler.
        """
        return self._by_route_key.get(route_key)

    def get(self, agent_id: str) -> AgentDescriptor:
        """Exact, case-sensitive lookup raising a structured not-found error.

        Args:
            agent_id (str): Public identifier of the agent being registered or discovered.
        """
        descriptor = self._descriptors.get(agent_id)
        if descriptor is None:
            raise DiscoveryErrors.agent_not_found(agent_id)
        return descriptor

    def list_all(self) -> tuple[AgentDescriptor, ...]:
        """Every descriptor, including hidden ones, in the defined order."""
        return tuple(sorted(self._descriptors.values(), key=lambda item: item.agent_id))

    def list_discoverable(self) -> tuple[AgentDescriptor, ...]:
        """Descriptors eligible for listings, in the defined order.

        Hidden agents are excluded here but remain resolvable through
        :meth:`find` so they stay invocable.
        """
        return tuple(descriptor for descriptor in self.list_all() if descriptor.is_listed)
