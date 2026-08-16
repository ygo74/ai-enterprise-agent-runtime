from __future__ import annotations

import asyncio
from typing import Any

import httpx
import pytest
from discovery_fixtures import ANTHROPIC_HEADERS, both_dialects_enabled, make_descriptor
from fastapi import FastAPI

from ygo74.agent_runtime.domains.discovery.descriptor_registry import DescriptorRegistry
from ygo74.agent_runtime.domains.endpoints.fastapi_endpoints import add_ai_endpoints

DESCRIPTORS = [make_descriptor("billing"), make_descriptor("support")]


def build_app() -> tuple[FastAPI, list[dict[str, Any]]]:
    """An app exposing both the discovery surfaces and the invocation surfaces."""

    seen: list[dict[str, Any]] = []

    def entrypoint(payload: dict[str, Any]) -> dict[str, Any]:
        seen.append(payload)
        return {"output": f"handled by {payload['route_key']}"}

    app = FastAPI()
    add_ai_endpoints(
        app,
        entrypoint,
        default_route_key="fallback",
        enable_anthropic_messages=True,
        descriptor_registry=DescriptorRegistry(DESCRIPTORS),
        discovery=both_dialects_enabled(),
    )
    return app, seen


def call(app: FastAPI, method: str, path: str, **kwargs: Any) -> httpx.Response:
    async def _call() -> httpx.Response:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            return await client.request(method, path, **kwargs)

    return asyncio.run(_call())


def advertised_ids(app: FastAPI, headers: dict[str, str] | None = None) -> list[str]:
    body = call(app, "GET", "/v1/models", headers=headers).json()
    return [entry["id"] for entry in body["data"]]


@pytest.mark.parametrize(
    ("path", "body_factory"),
    [
        ("/v1/responses", lambda model: {"model": model, "input": "hello"}),
        (
            "/v1/chat/completions",
            lambda model: {"model": model, "messages": [{"role": "user", "content": "hello"}]},
        ),
        (
            "/v1/messages",
            lambda model: {"model": model, "messages": [{"role": "user", "content": "hello"}]},
        ),
    ],
)
def test_every_advertised_identifier_is_accepted_on_every_invocation_surface(
    path: str, body_factory: Any
) -> None:
    app, seen = build_app()

    for model in advertised_ids(app):
        response = call(app, "POST", path, json=body_factory(model))
        assert response.status_code == 200, response.text

    assert [payload["route_key"] for payload in seen] == ["route-billing", "route-support"]


def test_the_identifier_routes_to_the_agent_that_advertised_it() -> None:
    app, seen = build_app()

    call(app, "POST", "/v1/responses", json={"model": "support", "input": "hello"})

    assert seen[0]["route_key"] == "route-support"


def test_identifiers_advertised_by_the_anthropic_dialect_round_trip_identically() -> None:
    app, seen = build_app()

    for model in advertised_ids(app, ANTHROPIC_HEADERS):
        call(app, "POST", "/v1/messages", json={"model": model, "messages": []})

    assert [payload["route_key"] for payload in seen] == ["route-billing", "route-support"]


def test_an_explicit_route_key_still_takes_precedence_over_the_model() -> None:
    app, seen = build_app()

    call(
        app,
        "POST",
        "/v1/responses",
        json={"model": "support", "input": "hello", "metadata": {"route_key": "route-billing"}},
    )

    assert seen[0]["route_key"] == "route-billing"


def test_an_unknown_model_falls_back_to_the_default_route_key() -> None:
    app, seen = build_app()

    call(app, "POST", "/v1/responses", json={"model": "ghost", "input": "hello"})

    assert seen[0]["route_key"] == "fallback"


def test_a_case_variant_of_an_advertised_identifier_does_not_route_to_that_agent() -> None:
    app, seen = build_app()

    call(app, "POST", "/v1/responses", json={"model": "SUPPORT", "input": "hello"})

    assert seen[0]["route_key"] == "fallback"


def test_discovery_and_invocation_coexist_on_the_same_application() -> None:
    app, _ = build_app()

    assert call(app, "GET", "/v1/models").status_code == 200
    assert call(app, "POST", "/v1/responses", json={"model": "support", "input": "x"}).status_code == 200
