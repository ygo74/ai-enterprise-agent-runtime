from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone

import httpx
import jwt
import pytest
from fastapi import FastAPI, HTTPException

from ygo74.agent_runtime.domains.auth.auth_errors import AuthorizationError, auth_error
from ygo74.agent_runtime.domains.auth.jwt_authenticator import JwtValidationConfig, StaticSymmetricKeyResolver
from ygo74.agent_runtime.domains.endpoints.fastapi_endpoints import add_ai_endpoints


def _config() -> JwtValidationConfig:
    return JwtValidationConfig(
        allowed_algorithms=("HS256",),
        required_claims=("sub", "exp", "iss", "aud"),
        issuer="https://issuer.example.com",
        audience="runtime",
        key_resolver=StaticSymmetricKeyResolver("secret"),
        roles_claim_path="realm_access.roles",
    )


def _token(roles: list[str]) -> str:
    now = datetime.now(tz=timezone.utc)
    claims = {
        "sub": "user-abc",
        "iss": "https://issuer.example.com",
        "aud": "runtime",
        "exp": int((now + timedelta(minutes=5)).timestamp()),
        "realm_access": {"roles": roles},
    }
    return jwt.encode(claims, "secret", algorithm="HS256")


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


def _build_app(entrypoint) -> FastAPI:
    app = FastAPI()
    add_ai_endpoints(
        app,
        entrypoint,
        default_route_key="demo-route",
        jwt_validation=_config(),
        require_bearer_token=True,
    )
    return app


def test_authorization_denial_error_shape() -> None:
    err = auth_error("forbidden", "access denied", "authorization")
    assert err["code"] == "forbidden"
    assert err["category"] == "authorization"


def test_raising_authorization_error_returns_403_and_skips_business_logic() -> None:
    executed: list[str] = []

    async def entrypoint(payload: dict) -> dict:
        if "admin" not in (payload["auth_context"] or {}).get("roles", []):
            raise AuthorizationError(
                code="role_required",
                message="admin role is required",
                details={"required_role": "admin"},
            )

        executed.append(payload["request_id"])
        return {"request_id": payload["request_id"], "status": "success", "output": "secret"}

    response = asyncio.run(
        _post_json(
            _build_app(entrypoint),
            "/v1/responses",
            {"model": "gpt-5-chat", "input": "hello"},
            headers={"Authorization": f"Bearer {_token(['viewer'])}"},
        )
    )

    assert response.status_code == 403
    detail = response.json()["detail"]
    assert detail["status"] == "error"
    assert detail["error"]["category"] == "authorization"
    assert detail["error"]["code"] == "role_required"
    assert detail["error"]["details"] == {"required_role": "admin"}
    assert executed == []


def test_returning_authorization_error_envelope_returns_403() -> None:
    async def entrypoint(payload: dict) -> dict:
        return {
            "request_id": payload["request_id"],
            "status": "error",
            "error": auth_error("forbidden", "access denied", "authorization"),
        }

    response = asyncio.run(
        _post_json(
            _build_app(entrypoint),
            "/v1/responses",
            {"model": "gpt-5-chat", "input": "hello"},
            headers={"Authorization": f"Bearer {_token(['viewer'])}"},
        )
    )

    assert response.status_code == 403
    assert response.json()["detail"]["error"]["code"] == "forbidden"


def test_developer_http_exception_is_not_swallowed_into_500() -> None:
    async def entrypoint(payload: dict) -> dict:
        raise HTTPException(status_code=403, detail={"error": "custom-denial"})

    response = asyncio.run(
        _post_json(
            _build_app(entrypoint),
            "/v1/responses",
            {"model": "gpt-5-chat", "input": "hello"},
            headers={"Authorization": f"Bearer {_token(['viewer'])}"},
        )
    )

    assert response.status_code == 403
    assert response.json()["detail"] == {"error": "custom-denial"}


def test_authorized_request_executes_business_logic() -> None:
    async def entrypoint(payload: dict) -> dict:
        if "admin" not in (payload["auth_context"] or {}).get("roles", []):
            raise AuthorizationError()

        return {"request_id": payload["request_id"], "status": "success", "output": "secret"}

    response = asyncio.run(
        _post_json(
            _build_app(entrypoint),
            "/v1/responses",
            {"model": "gpt-5-chat", "input": "hello"},
            headers={"Authorization": f"Bearer {_token(['admin'])}"},
        )
    )

    assert response.status_code == 200
    assert response.json()["status"] == "success"


def test_handler_exception_still_maps_to_500() -> None:
    async def entrypoint(payload: dict) -> dict:
        raise RuntimeError("boom")

    response = asyncio.run(
        _post_json(
            _build_app(entrypoint),
            "/v1/responses",
            {"model": "gpt-5-chat", "input": "hello"},
            headers={"Authorization": f"Bearer {_token(['admin'])}"},
        )
    )

    assert response.status_code == 500
    assert response.json()["detail"]["error"]["category"] == "handler_execution"


@pytest.mark.parametrize(
    ("category", "expected_status"),
    [
        ("authorization", 403),
        ("authentication", 401),
        ("validation", 400),
        ("routing", 404),
        ("handler_execution", 500),
    ],
)
def test_error_category_maps_to_http_status(category: str, expected_status: int) -> None:
    async def entrypoint(payload: dict) -> dict:
        return {
            "request_id": payload["request_id"],
            "status": "error",
            "error": {"code": "denied", "category": category, "message": "nope"},
        }

    response = asyncio.run(
        _post_json(
            _build_app(entrypoint),
            "/v1/responses",
            {"model": "gpt-5-chat", "input": "hello"},
            headers={"Authorization": f"Bearer {_token(['admin'])}"},
        )
    )

    assert response.status_code == expected_status
