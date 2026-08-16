from __future__ import annotations

from discovery_fixtures import ANTHROPIC_HEADERS, DiscoveryHarness, make_descriptor

from ygo74.agent_runtime.domains.discovery.agent_descriptor import DiscoveryVisibility
from ygo74.agent_runtime.domains.discovery.capability_extensions import EXTENSION_KEY
from ygo74.agent_runtime.domains.discovery.discovery_configuration import DiscoveryConfiguration


def test_openai_listing_returns_one_entry_per_discoverable_agent() -> None:
    harness = DiscoveryHarness.build([make_descriptor("billing"), make_descriptor("support")])

    body = harness.get("/v1/models").json()

    assert body["object"] == "list"
    assert [entry["id"] for entry in body["data"]] == ["billing", "support"]
    assert all(entry["object"] == "model" for entry in body["data"])
    assert all(entry["owned_by"] == "platform-team" for entry in body["data"])


def test_openai_listing_is_ordered_by_ascending_agent_id() -> None:
    harness = DiscoveryHarness.build(
        [make_descriptor("zeta"), make_descriptor("Alpha"), make_descriptor("beta")]
    )

    body = harness.get("/v1/models").json()

    assert [entry["id"] for entry in body["data"]] == ["Alpha", "beta", "zeta"]


def test_anthropic_listing_uses_the_anthropic_envelope() -> None:
    harness = DiscoveryHarness.build([make_descriptor("billing"), make_descriptor("support")])

    body = harness.get("/v1/models", ANTHROPIC_HEADERS).json()

    assert [entry["id"] for entry in body["data"]] == ["billing", "support"]
    assert all(entry["type"] == "model" for entry in body["data"])
    assert body["first_id"] == "billing"
    assert body["last_id"] == "support"
    assert body["has_more"] is False


def test_single_model_retrieval_returns_the_requested_entry_per_dialect() -> None:
    harness = DiscoveryHarness.build([make_descriptor("support")])

    openai_entry = harness.get("/v1/models/support").json()
    anthropic_entry = harness.get("/v1/models/support", ANTHROPIC_HEADERS).json()

    assert openai_entry["id"] == "support"
    assert anthropic_entry["id"] == "support"
    assert anthropic_entry["display_name"] == "support display"


def test_non_native_attributes_are_confined_to_the_additive_extension_section() -> None:
    harness = DiscoveryHarness.build([make_descriptor("support", streaming=True)])

    entry = harness.get("/v1/models/support").json()

    assert set(entry) == {"id", "object", "created", "owned_by", EXTENSION_KEY}
    extension = entry[EXTENSION_KEY]
    assert extension["version"] == "1.0.0"
    assert extension["capabilities"]["streaming"] is True
    assert extension["skills"][0]["skillId"] == "faq"
    assert extension["securitySchemes"] == ["jwt"]


def test_shared_attributes_are_identical_across_both_dialects() -> None:
    harness = DiscoveryHarness.build([make_descriptor("support", streaming=True)])

    openai_entry = harness.get("/v1/models/support").json()
    anthropic_entry = harness.get("/v1/models/support", ANTHROPIC_HEADERS).json()

    assert openai_entry["id"] == anthropic_entry["id"]
    assert openai_entry[EXTENSION_KEY] == anthropic_entry[EXTENSION_KEY]


def test_hidden_agents_are_absent_from_listings_and_from_retrieval() -> None:
    harness = DiscoveryHarness.build(
        [make_descriptor("public"), make_descriptor("internal", visibility=DiscoveryVisibility.HIDDEN)]
    )

    body = harness.get("/v1/models").json()
    assert [entry["id"] for entry in body["data"]] == ["public"]

    assert harness.get("/v1/models/internal").status_code == 404


def test_no_projection_leaks_the_internal_route_key() -> None:
    harness = DiscoveryHarness.build([make_descriptor("support")])

    payload = harness.get("/v1/models/support").text

    assert "route-support" not in payload
    assert "routeKey" not in payload


def test_explicit_dialect_paths_are_registered_when_both_surfaces_are_enabled() -> None:
    harness = DiscoveryHarness.build([make_descriptor("support")])

    assert harness.get("/openai/v1/models").json()["object"] == "list"
    assert "has_more" in harness.get("/anthropic/v1/models").json()
    assert harness.get("/openai/v1/models/support").json()["object"] == "model"
    assert harness.get("/anthropic/v1/models/support").json()["type"] == "model"


def test_explicit_dialect_paths_are_absent_when_only_one_surface_is_enabled() -> None:
    harness = DiscoveryHarness.build(
        [make_descriptor("support")],
        DiscoveryConfiguration(enable_openai_models=True),
    )

    assert harness.get("/v1/models").status_code == 200
    assert harness.get("/openai/v1/models").status_code == 404


def test_route_prefix_relocates_the_model_paths() -> None:
    harness = DiscoveryHarness.build(
        [make_descriptor("support")],
        DiscoveryConfiguration(enable_openai_models=True, route_prefix="/runtime"),
    )

    assert harness.get("/runtime/v1/models").status_code == 200
    assert harness.get("/v1/models").status_code == 404
