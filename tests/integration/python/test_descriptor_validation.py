from __future__ import annotations

from datetime import datetime, timezone

import pytest

from ygo74.agent_runtime.domains.configuration.models import EndpointConfiguration
from ygo74.agent_runtime.domains.discovery.agent_descriptor import (
    AgentCapabilitySet,
    AgentDescriptor,
    AgentSkill,
)
from ygo74.agent_runtime.domains.discovery.capability_validator import CapabilityValidator
from ygo74.agent_runtime.domains.discovery.descriptor_binding import DescriptorBinding
from ygo74.agent_runtime.domains.discovery.descriptor_registry import DescriptorRegistry
from ygo74.agent_runtime.domains.discovery.discovery_errors import DiscoveryError, DiscoveryErrorCode
from ygo74.agent_runtime.routing.route_registry import RouteRegistry


def _descriptor(
    agent_id: str = "support",
    *,
    route_key: str = "support",
    capabilities: AgentCapabilitySet | None = None,
    skills: tuple[AgentSkill, ...] = (),
) -> AgentDescriptor:
    return AgentDescriptor(
        agent_id=agent_id,
        route_key=route_key,
        display_name="Support",
        description="Answers support questions.",
        version="1.0.0",
        owner="platform-team",
        created_at_utc=datetime(2026, 8, 16, tzinfo=timezone.utc),
        capabilities=capabilities or AgentCapabilitySet(),
        skills=skills,
    )


def test_duplicate_agent_id_fails_fast_and_names_the_duplicate() -> None:
    registry = DescriptorRegistry([_descriptor("support")])

    with pytest.raises(DiscoveryError) as excinfo:
        registry.register(_descriptor("support", route_key="other"))

    assert excinfo.value.code is DiscoveryErrorCode.DUPLICATE_AGENT_ID
    assert "support" in excinfo.value.message


def test_unresolved_route_key_fails_binding_validation() -> None:
    route_registry = RouteRegistry()
    route_registry.register("known", lambda req: req)
    binding = DescriptorBinding(route_registry)

    with pytest.raises(DiscoveryError) as excinfo:
        binding.validate(_descriptor("support", route_key="unknown"))

    assert excinfo.value.code is DiscoveryErrorCode.UNRESOLVED_ROUTE_KEY


def test_bound_route_key_passes_binding_validation() -> None:
    route_registry = RouteRegistry()
    route_registry.register("support", lambda req: req)

    DescriptorBinding(route_registry).validate(_descriptor())


def test_streaming_claim_contradicting_configuration_fails_fast() -> None:
    validator = CapabilityValidator(
        {"support": EndpointConfiguration(route_key="support", enable_responses=True, enable_streaming=False)}
    )

    with pytest.raises(DiscoveryError) as excinfo:
        validator.validate(_descriptor(capabilities=AgentCapabilitySet(streaming=True)))

    assert excinfo.value.code is DiscoveryErrorCode.CAPABILITY_CONTRADICTION


def test_streaming_claim_matching_configuration_is_accepted() -> None:
    validator = CapabilityValidator(
        {"support": EndpointConfiguration(route_key="support", enable_responses=True, enable_streaming=True)}
    )

    validator.validate(_descriptor(capabilities=AgentCapabilitySet(streaming=True)))


def test_descriptor_on_route_without_any_endpoint_fails_fast() -> None:
    validator = CapabilityValidator({"support": EndpointConfiguration(route_key="support")})

    with pytest.raises(DiscoveryError) as excinfo:
        validator.validate(_descriptor())

    assert excinfo.value.code is DiscoveryErrorCode.CAPABILITY_CONTRADICTION


def test_agent_id_unsafe_for_a_path_segment_is_rejected() -> None:
    with pytest.raises(DiscoveryError) as excinfo:
        _descriptor("has space")

    assert excinfo.value.code is DiscoveryErrorCode.INVALID_DESCRIPTOR


def test_empty_modality_list_is_rejected() -> None:
    with pytest.raises(DiscoveryError):
        AgentCapabilitySet(input_modalities=())


def test_non_positive_size_limit_is_rejected() -> None:
    with pytest.raises(DiscoveryError):
        AgentCapabilitySet(max_input_size=0)


def test_duplicate_skill_id_within_a_descriptor_is_rejected() -> None:
    skill = AgentSkill(skill_id="faq", name="FAQ", description="Answers questions.")

    with pytest.raises(DiscoveryError):
        _descriptor(skills=(skill, skill))


def test_skill_modality_outside_descriptor_capabilities_is_rejected() -> None:
    skill = AgentSkill(
        skill_id="vision",
        name="Vision",
        description="Reads images.",
        input_modalities=("image",),
    )

    with pytest.raises(DiscoveryError):
        _descriptor(skills=(skill,))
