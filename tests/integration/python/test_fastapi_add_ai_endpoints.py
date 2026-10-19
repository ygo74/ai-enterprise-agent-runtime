from __future__ import annotations

import asyncio
import json

import httpx
import pytest
from fastapi import FastAPI
from ygo74.agent_runtime.domains.contracts import AgentOutput, TextContent
from ygo74.agent_runtime.domains.endpoints.fastapi_endpoints import add_ai_endpoints
from ygo74.agent_runtime.domains.endpoints.rate_limiting import RateLimitSettings


async def _entrypoint(payload: dict) -> AgentOutput:
    return AgentOutput(
        (
            TextContent(
                json.dumps(
                    {
                        "echo": payload["input"],
                        "endpoint_type": payload["endpoint_type"],
                        "route_key": payload["route_key"],
                    }
                )
            ),
        )
    )


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
    # The route is published as an OpenAI Responses endpoint, so it answers with
    # a Responses object. What the use case returned is rendered as its text.
    assert body["object"] == "response"
    assert body["status"] == "completed"
    assert body["model"] == "gpt-5-chat"
    assert "openai.responses" in body["output_text"]
    assert "demo-route" in body["output_text"]


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
    assert body["object"] == "chat.completion"
    assert body["choices"][0]["message"]["role"] == "assistant"
    assert "hello" in body["choices"][0]["message"]["content"]


def test_add_ai_endpoints_warns_that_hosting_factory_is_preferred() -> None:
    app = FastAPI()

    with pytest.warns(DeprecationWarning, match="HostingFactory"):
        add_ai_endpoints(app, _entrypoint, default_route_key="demo-route")


def test_rate_limit_returns_429_without_invoking_the_agent_again() -> None:
    """Only the first request under the configured per-IP limit reaches the handler."""
    calls = 0

    async def entrypoint(payload: dict) -> AgentOutput:
        """Count an invocation and return a valid agent response."""
        nonlocal calls
        calls += 1
        return await _entrypoint(payload)

    app = FastAPI()
    add_ai_endpoints(
        app,
        entrypoint,
        default_route_key="demo-route",
        enable_openai_responses=False,
        enable_openai_chat_completions=True,
        enable_anthropic_messages=False,
        rate_limit_settings=RateLimitSettings(("1/minute",)),
    )
    payload = {"messages": [{"role": "user", "content": "hello"}]}

    first, second = asyncio.run(
        _post_twice(app, "/v1/chat/completions", payload)
    )

    assert first.status_code == 200
    assert second.status_code == 429
    assert calls == 1


async def _post_json(app: FastAPI, url: str, payload: dict) -> httpx.Response:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        return await client.post(url, json=payload)


async def _post_twice(
    app: FastAPI, url: str, payload: dict
) -> tuple[httpx.Response, httpx.Response]:
    """Send two calls from the same ASGI client to exercise one caller's quota."""
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport, base_url="http://test", timeout=3
    ) as client:
        first = await client.post(url, json=payload)
        second = await client.post(url, json=payload)
    return first, second
