from __future__ import annotations

import asyncio
from typing import Any

import httpx
import pytest
from fastapi import FastAPI

from ygo74.agent_runtime.domains.auth.apikey_authenticator import (
    ApiKeyAuthenticator,
    StaticApiKeyUserResolver,
)
from ygo74.agent_runtime.domains.auth.auth_context import ResolvedUser
from ygo74.agent_runtime.domains.endpoints.fastapi_endpoints import add_ai_endpoints
from ygo74.agent_runtime.domains.endpoints.header_forwarding import (
    DEFAULT_CONVERSATION_HEADER,
    RequestHeaderForwarder,
)


def _capturing_app(seen: list[dict[str, Any]], **options: Any) -> FastAPI:
    """An app whose handler records the uniform payload it was given."""

    async def entrypoint(payload: dict[str, Any]) -> dict[str, Any]:
        seen.append(payload)
        return {"request_id": payload["request_id"], "status": "success", "output": "ok"}

    app = FastAPI()
    add_ai_endpoints(app, entrypoint, default_route_key="demo-route", **options)
    return app


async def _post_json(
    app: FastAPI,
    payload: dict[str, Any],
    *,
    headers: dict[str, str] | None = None,
) -> httpx.Response:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        return await client.post("/v1/chat/completions", json=payload, headers=headers)


def _invoke(
    payload: dict[str, Any],
    *,
    headers: dict[str, str] | None = None,
    **options: Any,
) -> dict[str, Any]:
    """Post one request and return the metadata the handler received."""

    seen: list[dict[str, Any]] = []
    response = asyncio.run(_post_json(_capturing_app(seen, **options), payload, headers=headers))

    assert response.status_code == 200
    return seen[0]["metadata"]


def _message(text: str = "hello") -> dict[str, Any]:
    return {"messages": [{"role": "user", "content": text}]}


def test_conversation_header_reaches_the_handler() -> None:
    metadata = _invoke(_message(), headers={"X-Conversation-Id": "conv-42"})

    assert metadata["conversation_id"] == "conv-42"
    assert metadata["headers"][DEFAULT_CONVERSATION_HEADER] == "conv-42"


def test_conversation_id_in_the_body_wins_over_the_header() -> None:
    metadata = _invoke(
        {**_message(), "metadata": {"conversation_id": "from-body"}},
        headers={"X-Conversation-Id": "from-header"},
    )

    assert metadata["conversation_id"] == "from-body"


def test_a_body_cannot_forge_transport_headers() -> None:
    metadata = _invoke(
        {**_message(), "metadata": {"headers": {DEFAULT_CONVERSATION_HEADER: "spoofed"}}},
        headers={"X-Conversation-Id": "conv-42"},
    )

    assert metadata["headers"] == {DEFAULT_CONVERSATION_HEADER: "conv-42"}
    assert metadata["conversation_id"] == "conv-42"


def test_headers_outside_the_allowlist_are_not_forwarded() -> None:
    metadata = _invoke(_message(), headers={"X-Tenant-Secret": "shh"})

    assert metadata["headers"] == {}
    assert "conversation_id" not in metadata


def test_credential_headers_are_never_forwarded() -> None:
    resolver = StaticApiKeyUserResolver({"key-admin": ResolvedUser(user_id="svc-admin")})
    metadata = _invoke(
        _message(),
        headers={"x-api-key": "key-admin", "X-Conversation-Id": "conv-42"},
        api_key_resolver=resolver,
    )

    assert metadata["headers"] == {DEFAULT_CONVERSATION_HEADER: "conv-42"}
    assert "key-admin" not in str(metadata)


def test_an_extra_header_is_forwarded_when_allowlisted() -> None:
    metadata = _invoke(
        _message(),
        headers={"X-Tenant-Id": "acme"},
        forwarded_headers=("x-tenant-id",),
    )

    assert metadata["headers"] == {"x-tenant-id": "acme"}


def test_the_conversation_header_can_be_renamed() -> None:
    metadata = _invoke(
        _message(),
        headers={"X-Chat-Id": "conv-42", "X-Conversation-Id": "ignored"},
        conversation_header="x-chat-id",
    )

    assert metadata["conversation_id"] == "conv-42"


def test_forwarding_is_refused_for_a_standard_credential_header() -> None:
    with pytest.raises(ValueError, match="authorization"):
        _capturing_app([], forwarded_headers=("authorization",))


def test_forwarding_is_refused_for_a_renamed_api_key_header() -> None:
    resolver = StaticApiKeyUserResolver({"key-admin": ResolvedUser(user_id="svc-admin")})

    with pytest.raises(ValueError, match="x-house-key"):
        _capturing_app(
            [],
            authenticators=[ApiKeyAuthenticator(resolver, header_name="x-house-key")],
            forwarded_headers=("x-house-key",),
        )


def test_forwarder_reads_a_header_whatever_its_case() -> None:
    forwarder = RequestHeaderForwarder.create(forwarded=("x-conversation-id",))

    metadata = forwarder.apply({}, {"X-Conversation-Id": "  conv-42  "})

    assert metadata["conversation_id"] == "conv-42"


def test_forwarder_tolerates_a_request_without_headers() -> None:
    forwarder = RequestHeaderForwarder.create(forwarded=("x-conversation-id",))

    assert forwarder.apply({"tenant": "acme"}, None) == {"tenant": "acme", "headers": {}}
