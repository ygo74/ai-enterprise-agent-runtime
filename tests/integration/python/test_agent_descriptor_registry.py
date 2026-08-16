from __future__ import annotations

from datetime import datetime, timezone

import pytest

from ygo74.agent_runtime.domains.discovery.agent_descriptor import (
    AgentCapabilitySet,
    AgentDescriptor,
    DiscoveryVisibility,
)
from ygo74.agent_runtime.domains.discovery.descriptor_registry import (
    DescriptorOrdering,
    DescriptorRegistry,
)
from ygo74.agent_runtime.domains.discovery.discovery_errors import DiscoveryError, DiscoveryErrorCode


def _descriptor(agent_id: str, *, visibility: DiscoveryVisibility = DiscoveryVisibility.LISTED) -> AgentDescriptor:
    return AgentDescriptor(
        agent_id=agent_id,
        route_key=f"route-{agent_id}",
        display_name=agent_id.title(),
        description=f"Agent {agent_id}.",
        version="1.0.0",
        owner="platform-team",
        created_at_utc=datetime(2026, 8, 16, tzinfo=timezone.utc),
        capabilities=AgentCapabilitySet(),
        discovery_visibility=visibility,
    )


def test_registry_defaults_to_agent_id_ascending_ordering() -> None:
    registry = DescriptorRegistry()
    assert registry.ordering is DescriptorOrdering.AGENT_ID_ASCENDING


def test_registry_lists_descriptors_in_code_point_ascending_order() -> None:
    registry = DescriptorRegistry([_descriptor("zeta"), _descriptor("Alpha"), _descriptor("beta")])

    assert [item.agent_id for item in registry.list_all()] == ["Alpha", "beta", "zeta"]


def test_registry_ordering_is_stable_across_repeated_reads() -> None:
    registry = DescriptorRegistry([_descriptor("b"), _descriptor("a"), _descriptor("c")])

    first = [item.agent_id for item in registry.list_all()]
    second = [item.agent_id for item in registry.list_all()]

    assert first == second == ["a", "b", "c"]


def test_registry_lookup_is_exact_and_case_sensitive() -> None:
    registry = DescriptorRegistry([_descriptor("Support")])

    assert registry.find("Support") is not None
    assert registry.find("support") is None
    assert registry.find("SUPPORT") is None


def test_registry_get_raises_structured_not_found() -> None:
    registry = DescriptorRegistry([_descriptor("support")])

    with pytest.raises(DiscoveryError) as excinfo:
        registry.get("missing")

    assert excinfo.value.code is DiscoveryErrorCode.AGENT_NOT_FOUND


def test_registry_excludes_hidden_agents_from_listings_but_keeps_them_resolvable() -> None:
    registry = DescriptorRegistry(
        [_descriptor("public"), _descriptor("internal", visibility=DiscoveryVisibility.HIDDEN)]
    )

    assert [item.agent_id for item in registry.list_discoverable()] == ["public"]
    assert registry.find("internal") is not None


def test_registry_membership_and_length_reflect_registrations() -> None:
    registry = DescriptorRegistry([_descriptor("a"), _descriptor("b")])

    assert len(registry) == 2
    assert "a" in registry
    assert "missing" not in registry
