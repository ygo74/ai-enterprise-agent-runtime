"""Measure the local FastAPI overhead added by optional in-memory quotas."""

from __future__ import annotations

import asyncio
import statistics
import time
import warnings

import httpx
from fastapi import FastAPI
from ygo74.agent_runtime.domains.contracts import AgentOutput, TextContent
from ygo74.agent_runtime.domains.endpoints.fastapi_endpoints import add_ai_endpoints
from ygo74.agent_runtime.domains.endpoints.rate_limiting import RateLimitSettings

_SAMPLE_COUNT = 150


async def _entrypoint(payload: dict[str, object]) -> AgentOutput:
    """Return a constant response so the measurement excludes model time."""
    _ = payload
    return AgentOutput((TextContent("ok"),))


def _application(rate_limit: bool) -> FastAPI:
    """Build the same runtime route with or without the optional memory limiter."""
    app = FastAPI()
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        add_ai_endpoints(
            app,
            _entrypoint,
            default_route_key="benchmark",
            enable_openai_responses=False,
            enable_openai_chat_completions=True,
            enable_anthropic_messages=False,
            rate_limit_settings=(
                RateLimitSettings(("1000/minute",)) if rate_limit else None
            ),
        )
    return app


async def _measure(app: FastAPI) -> list[float]:
    """Collect per-request local ASGI latency while reusing one client connection."""
    elapsed: list[float] = []
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        for _ in range(_SAMPLE_COUNT):
            started = time.perf_counter()
            response = await client.post(
                "/v1/chat/completions",
                json={"messages": [{"role": "user", "content": "hello"}]},
            )
            elapsed.append((time.perf_counter() - started) * 1000)
            assert response.status_code == 200
    return elapsed


def test_memory_rate_limit_adds_at_most_five_milliseconds_at_p95() -> None:
    """The rate-check overhead stays within the approved local-path budget."""

    async def scenario() -> None:
        baseline = await _measure(_application(rate_limit=False))
        limited = await _measure(_application(rate_limit=True))
        baseline_p95 = statistics.quantiles(baseline, n=100)[94]
        limited_p95 = statistics.quantiles(limited, n=100)[94]

        assert limited_p95 - baseline_p95 < 5

    asyncio.run(scenario())
