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
    """

    def __init__(
        self,
        descriptors: Iterable[AgentDescriptor] | None = None,
        *,
        ordering: DescriptorOrdering = DescriptorOrdering.AGENT_ID_ASCENDING,
    ) -> None:
        self._descriptors: dict[str, AgentDescriptor] = {}
        self._by_route_key: dict[str, AgentDescriptor] = {}
        self._ordering = ordering
        for descriptor in descriptors or ():
            self.register(descriptor)

    @property
    def ordering(self) -> DescriptorOrdering:
        return self._ordering

    def __len__(self) -> int:
        return len(self._descriptors)

    def __iter__(self) -> Iterator[AgentDescriptor]:
        return iter(self.list_all())

    def __contains__(self, agent_id: object) -> bool:
        return isinstance(agent_id, str) and agent_id in self._descriptors

    def register(self, descriptor: AgentDescriptor) -> None:
        """Add a descriptor, failing fast on a duplicate public identifier."""

        if descriptor.agent_id in self._descriptors:
            raise DiscoveryErrors.duplicate_agent_id(descriptor.agent_id)
        self._descriptors[descriptor.agent_id] = descriptor
        self._by_route_key[descriptor.route_key] = descriptor

    def register_all(self, descriptors: Iterable[AgentDescriptor]) -> None:
        for descriptor in descriptors:
            self.register(descriptor)

    def find(self, agent_id: str) -> AgentDescriptor | None:
        """Exact, case-sensitive, O(1) lookup. Returns ``None`` when absent."""

        return self._descriptors.get(agent_id)

    def find_by_route_key(self, route_key: str) -> AgentDescriptor | None:
        """Exact lookup by internal route key, used to gate invocation by descriptor.

        If two descriptors were registered with the same ``route_key`` (unusual,
        and not otherwise validated), the most recently registered one wins.
        """

        return self._by_route_key.get(route_key)

    def get(self, agent_id: str) -> AgentDescriptor:
        """Exact, case-sensitive lookup raising a structured not-found error."""

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
