from __future__ import annotations

import pytest
from discovery_fixtures import ANTHROPIC_HEADERS, DiscoveryHarness, make_descriptor

from ygo74.agent_runtime.domains.discovery.agent_descriptor import DiscoveryVisibility


def test_an_advertised_identifier_is_accepted_verbatim() -> None:
    harness = DiscoveryHarness.build([make_descriptor("Support.Billing_v2")])

    advertised = harness.get("/v1/models").json()["data"][0]["id"]

    assert advertised == "Support.Billing_v2"
    assert harness.get(f"/v1/models/{advertised}").status_code == 200


@pytest.mark.parametrize("variant", ["SUPPORT", "Support", "sUpPoRt"])
def test_case_variants_of_an_advertised_identifier_are_rejected(variant: str) -> None:
    harness = DiscoveryHarness.build([make_descriptor("support")])

    assert harness.get(f"/v1/models/{variant}").status_code == 404


@pytest.mark.parametrize("variant", ["%20support", "support%20", "%20support%20"])
def test_whitespace_padded_identifiers_are_rejected_rather_than_trimmed(variant: str) -> None:
    harness = DiscoveryHarness.build([make_descriptor("support")])

    assert harness.get(f"/v1/models/{variant}").status_code == 404


def test_two_agents_differing_only_by_case_remain_independently_addressable() -> None:
    harness = DiscoveryHarness.build([make_descriptor("Support"), make_descriptor("support")])

    listed = [entry["id"] for entry in harness.get("/v1/models").json()["data"]]

    assert listed == ["Support", "support"]
    assert harness.get("/v1/models/Support").json()["id"] == "Support"
    assert harness.get("/v1/models/support").json()["id"] == "support"


def test_an_empty_catalogue_lists_successfully_in_the_openai_dialect() -> None:
    harness = DiscoveryHarness.build([])

    response = harness.get("/v1/models")

    assert response.status_code == 200
    assert response.json() == {"object": "list", "data": []}


def test_an_empty_catalogue_lists_successfully_in_the_anthropic_dialect() -> None:
    harness = DiscoveryHarness.build([])

    body = harness.get("/v1/models", ANTHROPIC_HEADERS).json()

    assert body["data"] == []
    assert body["first_id"] is None
    assert body["last_id"] is None
    assert body["has_more"] is False


def test_a_catalogue_of_only_hidden_agents_lists_successfully_as_empty() -> None:
    harness = DiscoveryHarness.build(
        [make_descriptor("internal", visibility=DiscoveryVisibility.HIDDEN)]
    )

    response = harness.get("/v1/models")

    assert response.status_code == 200
    assert response.json()["data"] == []


def test_the_identifier_is_stable_across_both_dialects() -> None:
    harness = DiscoveryHarness.build([make_descriptor("support")])

    openai_id = harness.get("/v1/models").json()["data"][0]["id"]
    anthropic_id = harness.get("/v1/models", ANTHROPIC_HEADERS).json()["data"][0]["id"]

    assert openai_id == anthropic_id
