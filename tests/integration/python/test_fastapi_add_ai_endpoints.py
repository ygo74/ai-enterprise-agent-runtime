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


async def _post_json(app: FastAPI, url: str, payload: dict) -> httpx.Response:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        return await client.post(url, json=payload)
