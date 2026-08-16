from __future__ import annotations

import asyncio

import httpx
import pytest
from fastapi import FastAPI

from ygo74.agent_runtime.domains.auth.auth_context import ResolvedUser
from ygo74.agent_runtime.domains.auth.auth_errors import AuthenticationError
from ygo74.agent_runtime.domains.auth.apikey_authenticator import (
    ApiKeyAuthenticator,
    StaticApiKeyUserResolver,
)
from ygo74.agent_runtime.domains.endpoints.fastapi_endpoints import add_ai_endpoints


def _resolver() -> StaticApiKeyUserResolver:
    return StaticApiKeyUserResolver(
        {
            "key-admin": ResolvedUser(
                user_id="svc-admin",
                name="Service Admin",
                email="svc@example.com",
                roles=["admin"],
                scopes=["agents.invoke"],
                tenant_id="tenant-1",
            )
        }
    )


async def _entrypoint(payload: dict) -> dict:
    return {
        "request_id": payload["request_id"],
        "status": "success",
        "output": {"auth_context": payload["auth_context"]},
    }


async def _post_json(
    app: FastAPI,
    url: str,
    payload: dict,
    *,
    headers: dict[str, str] | None = None,
) -> httpx.Response:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        return await client.post(url, json=payload, headers=headers)


def _build_app() -> FastAPI:
    app = FastAPI()
    add_ai_endpoints(
        app,
        _entrypoint,
        default_route_key="demo-route",
        api_key_resolver=_resolver(),
    )
    return app


def test_api_key_authenticator_normalizes_user_context() -> None:
    context = ApiKeyAuthenticator(_resolver()).authenticate_key("key-admin")

    assert context.auth_type == "api_key"
    assert context.user_id == "svc-admin"
    assert context.identity.subject == "svc-admin"
    assert context.identity.email == "svc@example.com"
    assert context.roles == ["admin"]
    assert context.scopes == ["agents.invoke"]
    assert context.tenant_id == "tenant-1"


def test_api_key_authenticator_rejects_unknown_key() -> None:
    with pytest.raises(AuthenticationError) as exc:
        ApiKeyAuthenticator(_resolver()).authenticate_key("nope")

    assert exc.value.code == "api_key_invalid"


def test_api_key_authenticator_rejects_user_without_user_id() -> None:
    resolver = StaticApiKeyUserResolver({"key-x": ResolvedUser(user_id="  ")})

    with pytest.raises(AuthenticationError) as exc:
        ApiKeyAuthenticator(resolver).authenticate_key("key-x")

    assert exc.value.code == "user_context_malformed"


def test_api_key_authenticator_claims_only_its_own_header() -> None:
    authenticator = ApiKeyAuthenticator(_resolver())

    assert authenticator.can_authenticate({"x-api-key": "key-admin"}) is True
    assert authenticator.can_authenticate({"authorization": "Bearer abc"}) is False


def test_endpoint_invokes_resolver_and_never_leaks_raw_key() -> None:
    response = asyncio.run(
        _post_json(
            _build_app(),
            "/v1/responses",
            {"model": "gpt-5-chat", "input": "hello"},
            headers={"x-api-key": "key-admin"},
        )
    )

    assert response.status_code == 200
    auth_context = response.json()["output"]["auth_context"]
    assert auth_context["authType"] == "api_key"
    assert auth_context["userId"] == "svc-admin"
    assert auth_context["roles"] == ["admin"]
    assert "key-admin" not in str(auth_context)


def test_endpoint_rejects_unknown_api_key() -> None:
    response = asyncio.run(
        _post_json(
            _build_app(),
            "/v1/responses",
            {"model": "gpt-5-chat", "input": "hello"},
            headers={"x-api-key": "unknown"},
        )
    )

    assert response.status_code == 401
    assert response.json()["detail"]["error"]["code"] == "api_key_invalid"


def test_api_key_header_ignored_when_no_resolver_configured() -> None:
    app = FastAPI()
    add_ai_endpoints(app, _entrypoint, default_route_key="demo-route")

    response = asyncio.run(
        _post_json(
            app,
            "/v1/responses",
            {"model": "gpt-5-chat", "input": "hello"},
            headers={"x-api-key": "key-admin"},
        )
    )

    assert response.status_code == 200
    assert response.json()["output"]["auth_context"] is None
