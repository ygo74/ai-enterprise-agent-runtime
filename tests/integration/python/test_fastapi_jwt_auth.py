from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime, timedelta

import httpx
import jwt
from fastapi import FastAPI
from ygo74.agent_runtime.domains.auth.jwt_authenticator import (
    JwtValidationConfig,
    StaticSymmetricKeyResolver,
)
from ygo74.agent_runtime.domains.contracts import AgentOutput, TextContent
from ygo74.agent_runtime.domains.endpoints.fastapi_endpoints import add_ai_endpoints
from ygo74.agent_runtime.domains.mcp.request_context import McpRequestContextScope


async def _entrypoint(payload: dict) -> AgentOutput:
    return AgentOutput(
        (TextContent(json.dumps({"auth_context": payload["auth_context"]})),)
    )


def _config() -> JwtValidationConfig:
    return JwtValidationConfig(
        allowed_algorithms=("HS256",),
        required_claims=("sub", "exp", "nbf", "iss", "aud"),
        issuer="https://issuer.example.com",
        audience="runtime",
        key_resolver=StaticSymmetricKeyResolver("secret"),
    )


def _valid_token() -> str:
    now = datetime.now(tz=UTC)
    claims = {
        "sub": "user-abc",
        "iss": "https://issuer.example.com",
        "aud": "runtime",
        "nbf": int((now - timedelta(seconds=1)).timestamp()),
        "exp": int((now + timedelta(minutes=5)).timestamp()),
    }
    return jwt.encode(claims, "secret", algorithm="HS256")


def test_fastapi_rejects_missing_authorization_header_when_required() -> None:
    app = FastAPI()
    add_ai_endpoints(
        app,
        _entrypoint,
        default_route_key="demo-route",
        jwt_validation=_config(),
        require_bearer_token=True,
    )

    response = asyncio.run(
        _post_json(
            app,
            "/v1/responses",
            {"model": "gpt-5-chat", "input": "hello"},
        )
    )

    assert response.status_code == 401
    error = response.json()["error"]
    assert error["type"] == "authentication_error"
    assert error["code"] == "authorization_header_missing"


def test_fastapi_rejects_non_bearer_authorization_header() -> None:
    app = FastAPI()
    add_ai_endpoints(
        app,
        _entrypoint,
        default_route_key="demo-route",
        jwt_validation=_config(),
    )

    response = asyncio.run(
        _post_json(
            app,
            "/v1/responses",
            {"model": "gpt-5-chat", "input": "hello"},
            headers={"Authorization": "Basic aaa"},
        )
    )

    assert response.status_code == 401
    error = response.json()["error"]
    assert error["type"] == "authentication_error"
    assert error["code"] == "authorization_scheme_invalid"


def test_fastapi_authenticates_bearer_and_normalizes_auth_context() -> None:
    app = FastAPI()
    add_ai_endpoints(
        app,
        _entrypoint,
        default_route_key="demo-route",
        jwt_validation=_config(),
    )

    response = asyncio.run(
        _post_json(
            app,
            "/v1/responses",
            {"model": "gpt-5-chat", "input": "hello"},
            headers={"Authorization": f"Bearer {_valid_token()}"},
        )
    )

    assert response.status_code == 200
    body = response.json()
    assert body["object"] == "response"
    auth_context = json.loads(body["output_text"])["auth_context"]
    assert auth_context["authType"] == "jwt"
    assert auth_context["identity"]["userId"] == "user-abc"


def test_fastapi_keeps_verified_token_internal_and_scopes_it_to_agent_execution() -> (
    None
):
    """The normalized callback payload stays credential-free while MCP code can exchange the token."""
    app = FastAPI()
    observed: dict[str, object] = {}

    async def entrypoint(payload: dict) -> AgentOutput:
        """Observe internal MCP context without changing the standard exchange payload."""
        context = McpRequestContextScope.current()
        observed["request_id"] = payload["request_id"]
        observed["principal"] = None if context is None else context.principal
        observed["conversation_id"] = (
            None if context is None else context.conversation_id
        )
        observed["subject_token"] = None if context is None else context.subject_token
        observed["payload"] = payload
        return AgentOutput((TextContent("ok"),))

    add_ai_endpoints(
        app,
        entrypoint,
        default_route_key="demo-route",
        jwt_validation=_config(),
    )
    token = _valid_token()

    response = asyncio.run(
        _post_json(
            app,
            "/v1/responses",
            {
                "model": "gpt-5-chat",
                "input": "hello",
                "metadata": {"request_id": "req-1"},
            },
            headers={
                "Authorization": f"Bearer {token}",
                "X-Conversation-Id": "session-42",
            },
        )
    )

    assert response.status_code == 200
    assert observed["principal"].subject == "user-abc"
    assert observed["conversation_id"] == "session-42"
    assert observed["subject_token"].expose() == token
    assert "subject_token" not in observed["payload"]
    assert token not in repr(observed["payload"])
    assert token not in response.text
    assert McpRequestContextScope.current() is None


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
