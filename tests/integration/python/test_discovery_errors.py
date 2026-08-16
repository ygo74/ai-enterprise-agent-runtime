from __future__ import annotations

from discovery_fixtures import ANTHROPIC_HEADERS, DiscoveryHarness, make_descriptor

from ygo74.agent_runtime.domains.discovery.agent_descriptor import DiscoveryVisibility
from ygo74.agent_runtime.domains.discovery.dialect_selector import DialectSelection
from ygo74.agent_runtime.domains.discovery.discovery_configuration import DiscoveryConfiguration


def _error_code(payload: object) -> str:
    assert isinstance(payload, dict)
    detail = payload.get("detail", payload)
    assert isinstance(detail, dict)
    error = detail.get("error", detail)
    assert isinstance(error, dict)
    code = error.get("code")
    assert isinstance(code, str)
    return code


def test_an_unknown_identifier_returns_a_not_found_error() -> None:
    harness = DiscoveryHarness.build([make_descriptor("support")])

    response = harness.get("/v1/models/ghost")

    assert response.status_code == 404
    assert _error_code(response.json()) == "agent_not_found"


def test_a_hidden_agent_is_indistinguishable_from_an_unknown_one() -> None:
    harness = DiscoveryHarness.build(
        [make_descriptor("internal", visibility=DiscoveryVisibility.HIDDEN)]
    )

    hidden = harness.get("/v1/models/internal")
    unknown = harness.get("/v1/models/ghost")

    assert hidden.status_code == unknown.status_code == 404
    assert _error_code(hidden.json()) == _error_code(unknown.json())


def test_an_unsupported_provider_version_is_a_client_error() -> None:
    harness = DiscoveryHarness.build([make_descriptor("support")])

    response = harness.get("/v1/models", {"anthropic-version": "1999-01-01"})

    assert response.status_code == 400
    assert _error_code(response.json()) == "unsupported_provider_version"


def test_invalid_pagination_arguments_are_a_client_error() -> None:
    harness = DiscoveryHarness.build(
        [make_descriptor("support")],
        DiscoveryConfiguration(
            enable_openai_models=True,
            enable_anthropic_models=True,
            default_page_size=5,
            max_page_size=5,
        ),
    )

    response = harness.get("/v1/models?limit=500", ANTHROPIC_HEADERS)

    assert response.status_code == 400
    assert _error_code(response.json()) == "invalid_pagination"


def test_requesting_a_disabled_dialect_reports_the_surface_as_unavailable() -> None:
    harness = DiscoveryHarness.build(
        [make_descriptor("support")],
        DiscoveryConfiguration(enable_openai_models=True),
    )

    response = harness.get("/v1/models", ANTHROPIC_HEADERS)

    assert response.status_code == 404
    assert _error_code(response.json()) == "discovery_surface_disabled"


def test_no_discovery_routes_exist_when_every_surface_is_disabled() -> None:
    harness = DiscoveryHarness.build([make_descriptor("support")], DiscoveryConfiguration())

    assert harness.get("/v1/models").status_code == 404
    assert harness.get("/v1/models/support").status_code == 404


def test_error_payloads_never_disclose_the_internal_route_key() -> None:
    harness = DiscoveryHarness.build([make_descriptor("support")])

    payload = harness.get("/v1/models/ghost").text

    assert "route-support" not in payload


def test_a_pinned_dialect_still_refuses_a_disabled_surface() -> None:
    harness = DiscoveryHarness.build(
        [make_descriptor("support")],
        DiscoveryConfiguration(
            enable_openai_models=True,
            dialect_selection=DialectSelection.ANTHROPIC_ONLY,
        ),
    )

    response = harness.get("/v1/models")

    assert response.status_code == 404
    assert _error_code(response.json()) == "discovery_surface_disabled"
