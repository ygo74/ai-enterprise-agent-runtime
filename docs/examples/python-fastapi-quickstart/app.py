from __future__ import annotations

from typing import Any

from fastapi import FastAPI

from ygo74.agent_runtime.domains.endpoints.fastapi_endpoints import add_ai_endpoints

app = FastAPI(title="Agent Runtime Python Quickstart")


async def echo_agent(payload: dict[str, Any]) -> dict[str, Any]:
    """Return the normalized input as a simple response."""
    return {
        "request_id": payload["request_id"],
        "status": "success",
        "output": {"content": f"Echo: {payload['input']}"},
    }


add_ai_endpoints(
    app,
    echo_agent,
    default_route_key="echo-agent",
    enable_openai_responses=True,
    enable_openai_chat_completions=True,
    enable_anthropic_messages=True,
)
