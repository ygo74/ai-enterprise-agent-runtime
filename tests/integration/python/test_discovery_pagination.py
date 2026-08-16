from __future__ import annotations

import pytest
from discovery_fixtures import ANTHROPIC_HEADERS, DiscoveryHarness, make_descriptor

from ygo74.agent_runtime.domains.discovery.discovery_configuration import DiscoveryConfiguration
from ygo74.agent_runtime.domains.discovery.discovery_errors import DiscoveryError, DiscoveryErrorCode
from ygo74.agent_runtime.domains.discovery.pagination import (
    DiscoveryPagination,
    PaginationRequest,
)

CATALOGUE = ["agent-a", "agent-b", "agent-c", "agent-d", "agent-e"]


def _harness(*, default_page_size: int = 2, max_page_size: int = 3) -> DiscoveryHarness:
    return DiscoveryHarness.build(
        [make_descriptor(agent_id) for agent_id in CATALOGUE],
        DiscoveryConfiguration(
            enable_openai_models=True,
            enable_anthropic_models=True,
            default_page_size=default_page_size,
            max_page_size=max_page_size,
        ),
    )


def _paginator() -> DiscoveryPagination:
    return DiscoveryPagination(default_page_size=2, max_page_size=3)


def test_limit_truncates_the_page_and_flags_more_results() -> None:
    page = _paginator().paginate(CATALOGUE, PaginationRequest(limit=2), lambda item: item)

    assert page.items == ("agent-a", "agent-b")
    assert page.first_id == "agent-a"
    assert page.last_id == "agent-b"
    assert page.has_more is True


def test_the_final_page_does_not_flag_more_results() -> None:
    page = _paginator().paginate(CATALOGUE[-2:], PaginationRequest(limit=3), lambda item: item)

    assert page.items == ("agent-d", "agent-e")
    assert page.has_more is False


def test_after_id_resumes_strictly_after_the_named_identifier() -> None:
    page = _paginator().paginate(CATALOGUE, PaginationRequest(limit=2, after_id="agent-b"), lambda i: i)

    assert page.items == ("agent-c", "agent-d")
    assert page.has_more is True


def test_before_id_returns_the_window_ending_at_the_named_identifier() -> None:
    page = _paginator().paginate(CATALOGUE, PaginationRequest(limit=2, before_id="agent-d"), lambda i: i)

    assert page.items == ("agent-b", "agent-c")


def test_an_absent_cursor_identifier_is_a_structured_error() -> None:
    with pytest.raises(DiscoveryError) as excinfo:
        _paginator().paginate(CATALOGUE, PaginationRequest(after_id="ghost"), lambda item: item)

    assert excinfo.value.code is DiscoveryErrorCode.INVALID_PAGINATION


def test_a_limit_above_the_configured_maximum_is_rejected() -> None:
    with pytest.raises(DiscoveryError) as excinfo:
        _paginator().paginate(CATALOGUE, PaginationRequest(limit=99), lambda item: item)

    assert excinfo.value.code is DiscoveryErrorCode.INVALID_PAGINATION


def test_a_non_positive_limit_is_rejected() -> None:
    with pytest.raises(DiscoveryError) as excinfo:
        _paginator().paginate(CATALOGUE, PaginationRequest(limit=0), lambda item: item)

    assert excinfo.value.code is DiscoveryErrorCode.INVALID_PAGINATION


def test_the_default_page_size_applies_when_no_limit_is_requested() -> None:
    page = _paginator().paginate(CATALOGUE, PaginationRequest(), lambda item: item)

    assert len(page.items) == 2


def test_the_anthropic_listing_exposes_the_page_cursors() -> None:
    harness = _harness(default_page_size=2, max_page_size=3)

    body = harness.get("/v1/models?limit=2", ANTHROPIC_HEADERS).json()

    assert [entry["id"] for entry in body["data"]] == ["agent-a", "agent-b"]
    assert body["first_id"] == "agent-a"
    assert body["last_id"] == "agent-b"
    assert body["has_more"] is True


def test_walking_the_cursors_visits_every_agent_exactly_once() -> None:
    harness = _harness(default_page_size=2, max_page_size=3)

    seen: list[str] = []
    cursor: str | None = None
    while True:
        path = "/v1/models?limit=2" + (f"&after_id={cursor}" if cursor else "")
        body = harness.get(path, ANTHROPIC_HEADERS).json()
        seen.extend(entry["id"] for entry in body["data"])
        if not body["has_more"]:
            break
        cursor = body["last_id"]

    assert seen == CATALOGUE


def test_an_invalid_limit_on_the_endpoint_is_a_client_error() -> None:
    harness = _harness(default_page_size=2, max_page_size=3)

    assert harness.get("/v1/models?limit=99", ANTHROPIC_HEADERS).status_code == 400
