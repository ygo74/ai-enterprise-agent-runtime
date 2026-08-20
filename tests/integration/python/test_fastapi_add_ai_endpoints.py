from __future__ import annotations

import asyncio

import httpx
from fastapi import FastAPI

from ygo74.agent_runtime.domains.endpoints.fastapi_endpoints import add_ai_endpoints


async def _entrypoint(payload: dict) -> dict:
    return {
        "request_id": payload["request_id"],
        "status": "success",
        "output": {
            "echo": payload["input"],
            "endpoint_type": payload["endpoint_type"],
            "route_key": payload["route_key"],
        },
    }


def test_add_ai_endpoints_registers_and_uniformizes_responses() -> None:
    app = FastAPI()
    add_ai_endpoints(
        app,
        _entrypoint,
        default_route_key="demo-route",
        enable_openai_responses=True,
        enable_openai_chat_completions=True,
        enable_anthropic_messages=False,
    )

    response = asyncio.run(
        _post_json(
            app,
            "/v1/responses",
            {
                "model": "gpt-5-chat",
                "input": "hello",
                "metadata": {"request_id": "r-1"},
            },
        )
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "success"
    assert body["endpoint_type"] == "openai.responses"
    assert body["output"]["endpoint_type"] == "openai.responses"
    assert body["output"]["route_key"] == "demo-route"


def test_add_ai_endpoints_registers_chat_completions_without_custom_models() -> None:
    app = FastAPI()
    add_ai_endpoints(
        app,
        _entrypoint,
        default_route_key="demo-route",
        enable_openai_responses=False,
        enable_openai_chat_completions=True,
        enable_anthropic_messages=False,
    )

    response = asyncio.run(
        _post_json(
            app,
            "/v1/chat/completions",
            {
                "messages": [{"role": "user", "content": "hello"}],
            },
        )
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "success"
    assert body["endpoint_type"] == "openai.chat_completions"
    assert isinstance(body["output"]["echo"], list)


def test_add_ai_endpoints_ignores_bearer_token_when_no_auth_configured() -> None:
    """A host that never configured JWT/API-key/authenticators must stay unprotected.

    Regression test: build_request_authenticator used to always add a default
    JwtAuthenticator to the chain, so any client sending an unrelated
    `Authorization: Bearer ...` header (e.g. its own upstream token) would be
    rejected trying to validate it as a JWT, even though the developer never
    asked for authentication.
    """

    app = FastAPI()
    add_ai_endpoints(app, _entrypoint, default_route_key="demo-route")

    response = asyncio.run(
        _post_json(
            app,
            "/v1/responses",
            {"model": "gpt-5-chat", "input": "hello"},
            headers={"Authorization": "Bearer not-a-jwt-and-not-meant-to-be-validated"},
        )
    )

    assert response.status_code == 200
    assert response.json()["status"] == "success"


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
