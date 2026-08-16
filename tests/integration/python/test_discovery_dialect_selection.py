from __future__ import annotations

import pytest
from discovery_fixtures import ANTHROPIC_HEADERS, both_dialects_enabled, make_descriptor

from ygo74.agent_runtime.domains.discovery.descriptor_registry import DescriptorRegistry
from ygo74.agent_runtime.domains.discovery.dialect_selector import (
    DialectSelection,
    DialectSelector,
    ProviderDialect,
)
from ygo74.agent_runtime.domains.discovery.discovery_configuration import (
    DiscoveryConfiguration,
    DiscoveryService,
)
from ygo74.agent_runtime.domains.discovery.discovery_errors import DiscoveryError, DiscoveryErrorCode


def _service(configuration: DiscoveryConfiguration | None = None) -> DiscoveryService:
    return DiscoveryService(
        DescriptorRegistry([make_descriptor("support")]),
        configuration or both_dialects_enabled(),
    )


def test_anthropic_version_header_selects_the_anthropic_dialect() -> None:
    assert DialectSelector().select(ANTHROPIC_HEADERS) is ProviderDialect.ANTHROPIC


def test_absent_header_defaults_to_the_openai_dialect() -> None:
    assert DialectSelector().select({}) is ProviderDialect.OPENAI
    assert DialectSelector().select(None) is ProviderDialect.OPENAI


def test_header_lookup_is_case_insensitive() -> None:
    assert DialectSelector().select({"Anthropic-Version": "2023-06-01"}) is ProviderDialect.ANTHROPIC


def test_blank_header_value_falls_back_to_the_openai_dialect() -> None:
    assert DialectSelector().select({"anthropic-version": "   "}) is ProviderDialect.OPENAI


def test_configuration_override_pins_the_openai_dialect_despite_the_header() -> None:
    selector = DialectSelector(DialectSelection.OPENAI_ONLY)

    assert selector.select(ANTHROPIC_HEADERS) is ProviderDialect.OPENAI


def test_configuration_override_pins_the_anthropic_dialect_without_the_header() -> None:
    selector = DialectSelector(DialectSelection.ANTHROPIC_ONLY)

    assert selector.select({}) is ProviderDialect.ANTHROPIC


def test_unsupported_provider_version_is_a_structured_error() -> None:
    with pytest.raises(DiscoveryError) as excinfo:
        DialectSelector().select({"anthropic-version": "1999-01-01"})

    assert excinfo.value.code is DiscoveryErrorCode.UNSUPPORTED_PROVIDER_VERSION


def test_service_renders_the_dialect_selected_by_the_header() -> None:
    service = _service()

    assert service.list_models(headers={})["object"] == "list"
    assert "has_more" in service.list_models(headers=ANTHROPIC_HEADERS)


def test_service_honors_the_configured_dialect_override() -> None:
    service = _service(
        DiscoveryConfiguration(
            enable_openai_models=True,
            enable_anthropic_models=True,
            dialect_selection=DialectSelection.ANTHROPIC_ONLY,
        )
    )

    assert "has_more" in service.list_models(headers={})
