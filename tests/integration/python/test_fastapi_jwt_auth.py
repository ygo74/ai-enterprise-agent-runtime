from __future__ import annotations

from datetime import datetime, timedelta, timezone
import asyncio

import httpx
import jwt
from fastapi import FastAPI

from ygo74.agent_runtime.domains.auth.jwt_authenticator import JwtValidationConfig, StaticSymmetricKeyResolver
from ygo74.agent_runtime.domains.endpoints.fastapi_endpoints import add_ai_endpoints


async def _entrypoint(payload: dict) -> dict:
    return {
        "request_id": payload["request_id"],
        "status": "success",
        "output": {
            "auth_context": payload["auth_context"],
        },
    }


def _config() -> JwtValidationConfig:
    return JwtValidationConfig(
        allowed_algorithms=("HS256",),
        required_claims=("sub", "exp", "nbf", "iss", "aud"),
        issuer="https://issuer.example.com",
        audience="runtime",
        key_resolver=StaticSymmetricKeyResolver("secret"),
    )


def _valid_token() -> str:
    now = datetime.now(tz=timezone.utc)
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
    detail = response.json()["detail"]
    assert detail["status"] == "error"
    assert detail["error"]["code"] == "authorization_header_missing"


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
    detail = response.json()["detail"]
    assert detail["error"]["code"] == "authorization_scheme_invalid"


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
    assert body["status"] == "success"
    auth_context = body["output"]["auth_context"]
    assert auth_context["authType"] == "jwt"
    assert auth_context["identity"]["userId"] == "user-abc"


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
