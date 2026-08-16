from __future__ import annotations

from datetime import datetime, timezone

import pytest

from ygo74.agent_runtime.domains.configuration.models import EndpointConfiguration, RuntimeConfiguration
from ygo74.agent_runtime.domains.discovery.agent_descriptor import AgentCapabilitySet, DiscoveryVisibility
from ygo74.agent_runtime.domains.discovery.descriptor_defaults import DescriptorDefaults
from ygo74.agent_runtime.domains.discovery.descriptor_registry import DescriptorRegistry
from ygo74.agent_runtime.domains.discovery.discovery_errors import DiscoveryError


def _defaults() -> DescriptorDefaults:
    return DescriptorDefaults(created_at_utc=datetime(2026, 8, 16, tzinfo=timezone.utc))


def test_handler_without_a_descriptor_receives_a_minimal_derived_descriptor() -> None:
    descriptor = _defaults().derive("support")

    assert descriptor.agent_id == "support"
    assert descriptor.route_key == "support"
    # Verbatim, not title-cased: Unicode casing rules differ between Python,
    # .NET and Java, so any casing here would break cross-language parity.
    assert descriptor.display_name == "support"
    assert descriptor.description
    assert descriptor.version == "1.0.0"
    assert descriptor.owner == "agent-runtime"
    assert descriptor.discovery_visibility is DiscoveryVisibility.LISTED


def test_derived_descriptor_defaults_to_non_streaming_text_capabilities() -> None:
    capabilities = _defaults().derive("support").capabilities

    assert capabilities.streaming is False
    assert capabilities.input_modalities == ("text",)
    assert capabilities.output_modalities == ("text",)


def test_derived_descriptor_carries_explicit_capabilities_when_supplied() -> None:
    descriptor = _defaults().derive("support", capabilities=AgentCapabilitySet(streaming=True))

    assert descriptor.capabilities.streaming is True


def test_route_key_is_projected_onto_a_path_safe_agent_id() -> None:
    assert DescriptorDefaults.agent_id_for("support/billing agent") == "support-billing-agent"
    assert DescriptorDefaults.agent_id_for("--internal--") == "internal--"


def test_route_key_that_cannot_produce_an_identifier_is_rejected() -> None:
    with pytest.raises(DiscoveryError):
        DescriptorDefaults.agent_id_for("///")


def test_derived_descriptors_are_registrable_and_discoverable() -> None:
    defaults = _defaults()
    registry = DescriptorRegistry([defaults.derive("billing"), defaults.derive("support")])

    assert [item.agent_id for item in registry.list_discoverable()] == ["billing", "support"]


def test_declared_descriptor_is_bound_from_native_configuration() -> None:
    endpoint = EndpointConfiguration.from_dict(
        {
            "routeKey": "support",
            "enableResponses": True,
            "enableStreaming": True,
            "agentDescriptor": {
                "agentId": "support-agent",
                "routeKey": "support",
                "displayName": "Support Agent",
                "description": "Answers support questions.",
                "version": "2.1.0",
                "owner": "platform-team",
                "createdAtUtc": "2026-08-16T00:00:00Z",
                "capabilities": {"streaming": True, "inputModalities": ["text"], "outputModalities": ["text"]},
            },
        }
    )

    assert endpoint.agent_descriptor is not None
    assert endpoint.agent_descriptor.agent_id == "support-agent"
    assert endpoint.agent_descriptor.capabilities.streaming is True


def test_configuration_without_a_descriptor_section_leaves_it_undeclared() -> None:
    endpoint = EndpointConfiguration.from_dict({"routeKey": "support", "enableResponses": True})

    assert endpoint.agent_descriptor is None


def test_runtime_configuration_exposes_routes_and_declared_descriptors() -> None:
    declared = EndpointConfiguration.from_dict(
        {
            "routeKey": "support",
            "enableResponses": True,
            "agentDescriptor": {
                "agentId": "support-agent",
                "routeKey": "support",
                "displayName": "Support Agent",
                "description": "Answers support questions.",
                "version": "1.0.0",
                "owner": "platform-team",
                "createdAtUtc": "2026-08-16T00:00:00Z",
                "capabilities": {"streaming": False, "inputModalities": ["text"], "outputModalities": ["text"]},
            },
        }
    )
    bare = EndpointConfiguration(route_key="billing", enable_responses=True)
    configuration = RuntimeConfiguration(endpoints=(declared, bare))

    assert set(configuration.by_route_key) == {"support", "billing"}
    assert [item.agent_id for item in configuration.declared_descriptors] == ["support-agent"]
