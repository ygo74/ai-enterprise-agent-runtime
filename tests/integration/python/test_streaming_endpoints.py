import asyncio
import json
from collections.abc import AsyncIterator

import anyio
import httpx
import pytest
from fastapi import FastAPI
from ygo74.agent_runtime.domains.auth.tokens import TokenExchangeError
from ygo74.agent_runtime.domains.contracts import (
    AgentStreamEvent,
    ContentEvent,
    TerminalEvent,
    TextContent,
    TokenUsage,
    UsageEvent,
)
from ygo74.agent_runtime.domains.endpoints.fastapi_endpoints import add_ai_endpoints
from ygo74.agent_runtime.domains.mapping.output_projector import (
    OutputProtocol,
    ProjectionContext,
)
from ygo74.agent_runtime.domains.streaming.stream_processor import StreamProcessor


@pytest.mark.parametrize("protocol", list(OutputProtocol))
def test_stream_completion_event_shape(protocol: OutputProtocol) -> None:
    async def producer() -> AsyncIterator[object]:
        yield UsageEvent(TokenUsage(1, 2))
        yield ContentEvent("answer", TextContent("done"))
        yield TerminalEvent()

    async def consume() -> list[str]:
        return [
            frame
            async for frame in StreamProcessor().stream(
                producer(), ProjectionContext(protocol, "r1")
            )
        ]

    frames = asyncio.run(consume())
    data = [
        json.loads(line[6:])
        for frame in frames
        for line in frame.splitlines()
        if line.startswith("data: {")
    ]
    assert "done" in json.dumps(data)
    terminal_name = {
        OutputProtocol.RESPONSES: "response.completed",
        OutputProtocol.ANTHROPIC_MESSAGES: "message_stop",
    }
    if protocol in terminal_name:
        assert sum(event.get("type") == terminal_name[protocol] for event in data) == 1
    else:
        assert (
            sum(event["choices"][0]["finish_reason"] == "stop" for event in data) == 1
        )


@pytest.mark.parametrize(
    "path",
    ["/v1/responses", "/v1/chat/completions", "/v1/messages"],
)
@pytest.mark.parametrize("before_events", [True, False])
@pytest.mark.parametrize("background_failure", [False, True])
def test_token_exchange_failure_completes_http_stream(
    path: str,
    before_events: bool,
    background_failure: bool,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Terminate tool failures without exposing credentials or reporting success.

    Args:
        path: Provider-compatible invocation route.
        before_events: Whether token exchange fails before any neutral events.
        background_failure: Whether nested MCP-style task groups wrap the failure.
        caplog: Captured runtime diagnostics checked for credential leakage.
    """
    closed: list[bool] = []

    async def reject_token() -> None:
        """Fail a background exchange and cancel its waiting sibling task."""
        await asyncio.sleep(0)
        raise TokenExchangeError("subject_token=private-token client_secret=private-secret")

    async def transport_tasks() -> None:
        """Wrap the exchange failure like nested SSE transport task groups."""
        async with anyio.create_task_group() as tasks:
            tasks.start_soon(reject_token)
            await anyio.sleep_forever()

    async def producer(payload: dict[str, object]) -> AsyncIterator[AgentStreamEvent]:
        """Simulate a tool-side OBO failure without contacting an identity provider.

        Args:
            payload: Normalized endpoint request.
        """
        try:
            if not before_events:
                yield UsageEvent(TokenUsage(1, 2))
                yield ContentEvent("answer", TextContent("partial"))
            if background_failure:
                async with anyio.create_task_group() as tasks:
                    tasks.start_soon(transport_tasks)
                    await anyio.sleep_forever()
            raise TokenExchangeError("subject_token=private-token client_secret=private-secret")
        finally:
            closed.append(True)

    app = FastAPI()
    add_ai_endpoints(
        app, producer, default_route_key="mail", enable_anthropic_messages=True
    )

    async def invoke() -> httpx.Response:
        """Consume through ASGITransport, which rejects an incomplete HTTP response."""
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            return await client.post(
                path,
                json={
                    "model": "mail",
                    "input": "read mail",
                    "messages": [{"role": "user", "content": "read mail"}],
                    "max_tokens": 100,
                    "stream": True,
                },
            )

    response = asyncio.run(invoke())
    assert response.status_code == 200
    assert closed == [True]
    wire = response.text
    assert "agent_execution_error" in wire
    assert "private-token" not in wire + caplog.text
    assert "private-secret" not in wire + caplog.text
    assert "response.completed" not in wire
    assert '"finish_reason": "stop"' not in wire
    assert "message_stop" not in wire
    if path == "/v1/responses":
        assert wire.count("event: response.failed\n") == 1
    elif path == "/v1/chat/completions":
        assert wire.count("data: [DONE]") == 1
    else:
        assert wire.count("event: error\n") == 1


@pytest.mark.parametrize(
    "path",
    ["/v1/responses", "/v1/chat/completions", "/v1/messages"],
)
def test_async_stream_setup_failure_is_reported_before_response_start(
    path: str, caplog: pytest.LogCaptureFixture
) -> None:
    """Reject failed tool initialization before committing streaming HTTP headers.

    Args:
        path: Provider-compatible invocation route.
        caplog: Captured runtime diagnostics checked for credential leakage.
    """
    async def entrypoint(payload: dict[str, object]) -> AsyncIterator[AgentStreamEvent]:
        """Fail OBO setup instead of returning a producer that could emit events.

        Args:
            payload: Normalized endpoint request.
        """
        await asyncio.sleep(0)
        raise TokenExchangeError("subject_token=private-token client_secret=private-secret")

    app = FastAPI()
    add_ai_endpoints(
        app, entrypoint, default_route_key="mail", enable_anthropic_messages=True
    )

    async def invoke() -> httpx.Response:
        """Request streaming while retaining the pre-response HTTP failure."""
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            return await client.post(
                path,
                json={
                    "model": "mail",
                    "input": "read mail",
                    "messages": [{"role": "user", "content": "read mail"}],
                    "max_tokens": 100,
                    "stream": True,
                },
            )

    response = asyncio.run(invoke())
    assert response.status_code == 500
    assert response.headers["content-type"] == "application/json"
    assert "agent_execution_error" in response.text
    assert "private-token" not in response.text + caplog.text
    assert "private-secret" not in response.text + caplog.text
    assert "response.created" not in response.text
    assert "response.completed" not in response.text
