"""Exercise one managed HTTP pool against a deterministic local MCP server."""

from __future__ import annotations

import asyncio
import json
from enum import StrEnum
from typing import Any

import httpx
import pytest
from mcp.server.fastmcp import FastMCP
from ygo74.agent_runtime.domains.auth.agent_principal import AgentPrincipal
from ygo74.agent_runtime.domains.auth.oauth_token_exchange import (
    OAuthTokenExchangeSettings,
)
from ygo74.agent_runtime.domains.auth.tokens import (
    AccessToken,
    DelegatedTokenRequest,
)
from ygo74.agent_runtime.domains.http.resilience import (
    CircuitBreakerSettings,
    CircuitOpenError,
    RetrySettings,
    ServiceCircuitBreakerRegistry,
)
from ygo74.agent_runtime.domains.mcp.binding import (
    McpConnection,
    McpNetworkSettings,
    McpServerBinding,
    McpTransport,
    _McpResilientTransport,
)
from ygo74.agent_runtime.domains.mcp.request_context import (
    McpRequestContext,
    McpRequestContextScope,
)


class Capability(StrEnum):
    """Capabilities declared by the local fixture server."""

    TEST = "test"


@pytest.mark.asyncio
async def test_http_pool_uses_per_server_proxy_and_limits(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The lazy client receives this MCP server's proxy and pool limits."""
    transport_arguments: dict[str, Any] = {}

    class CapturingTransport(httpx.AsyncBaseTransport):
        """Record transport construction and report its cleanup."""

        closed = False

        async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
            """Reject accidental network calls in this construction-only test."""
            raise AssertionError(f"unexpected request to {request.url}")

        async def aclose(self) -> None:
            """Record pool shutdown requested by the MCP connection owner."""
            self.closed = True

    transport = CapturingTransport()

    def create_transport(**kwargs: Any) -> CapturingTransport:
        """Capture HTTPX transport settings without opening network sockets."""
        transport_arguments.update(kwargs)
        return transport

    monkeypatch.setattr(httpx, "AsyncHTTPTransport", create_transport)
    connection = McpConnection(
        McpServerBinding(
            server="configured-pool",
            transport=McpTransport.HTTP,
            capabilities=(Capability.TEST,),
            tools={"test": "echo"},
            url="https://mcp.example.test/mcp",
        ),
        network=McpNetworkSettings(
            proxy_url="http://proxy.example.test:8080",
            max_connections=7,
            max_keepalive_connections=3,
        ),
    )

    client = connection._get_http_client()
    assert client is connection._get_http_client()
    limits = transport_arguments["limits"]
    assert limits.max_connections == 7
    assert limits.max_keepalive_connections == 3
    assert transport_arguments["proxy"] == "http://proxy.example.test:8080"
    assert transport_arguments["verify"] is True
    await connection.aclose()
    assert transport.closed


@pytest.mark.asyncio
async def test_shared_http_client_preserves_mcp_result_variants(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """One lazy pool serves a local server's success, error, empty, and structured results."""
    server = FastMCP("local-fixture")

    @server.tool()
    def success() -> str:
        """Return ordinary text content."""
        return "hello"

    @server.tool()
    def failure() -> str:
        """Return an MCP tool error result."""
        raise RuntimeError("intentional fixture failure")

    @server.tool()
    def empty() -> str:
        """Return a successful empty text result."""
        return ""

    @server.tool(structured_output=True)
    def structured() -> dict[str, str]:
        """Return structured content without flattening its fields."""
        return {"status": "ready"}

    app = server.streamable_http_app()
    pool_ids: list[int] = []

    def asgi_transport(**_kwargs: Any) -> httpx.ASGITransport:
        """Route the runtime HTTPX pool into the in-process MCP app."""
        return httpx.ASGITransport(app=app)

    monkeypatch.setattr(httpx, "AsyncHTTPTransport", asgi_transport)
    binding = McpServerBinding(
        server="local-fixture",
        transport=McpTransport.HTTP,
        capabilities=(Capability.TEST,),
        tools={"test": "success"},
        url="http://127.0.0.1:8000/mcp",
    )
    connection = McpConnection(binding)

    async with app.router.lifespan_context(app):
        session = await connection.session()
        managed_client = connection._get_http_client()
        pool_ids.append(id(managed_client))
        successful = await session.call_tool("success", {})
        failed = await session.call_tool("failure", {})
        empty_result = await session.call_tool("empty", {})
        structured_result = await session.call_tool("structured", {})
        pool_ids.append(id(connection._get_http_client()))
        await connection.aclose()

    assert successful.isError is False
    assert [item.text for item in successful.content] == ["hello"]
    assert failed.isError is True
    assert empty_result.isError is False
    assert [item.text for item in empty_result.content] == [""]
    assert structured_result.isError is False
    assert structured_result.structuredContent == {"status": "ready"}
    assert pool_ids[0] == pool_ids[1]
    assert managed_client.is_closed


@pytest.mark.asyncio
async def test_mcp_transport_retries_only_safe_setup_requests() -> None:
    """Initialize may retry a transient failure; tool execution never replays."""
    safe_attempts = 0

    def transient_then_ready(request: httpx.Request) -> httpx.Response:
        nonlocal safe_attempts
        safe_attempts += 1
        status = 503 if safe_attempts == 1 else 200
        return httpx.Response(status, request=request)

    settings = RetrySettings(
        max_attempts=2,
        initial_delay_seconds=0.001,
        maximum_delay_seconds=0.002,
    )
    safe_transport = _McpResilientTransport(
        httpx.MockTransport(transient_then_ready),
        service_identity="https://setup.example.test/mcp",
        retry_settings=settings,
        breaker_settings=CircuitBreakerSettings(),
        breaker_registry=ServiceCircuitBreakerRegistry(),
        timeout_seconds=1.0,
    )
    initialize = httpx.Request(
        "POST",
        "https://setup.example.test/mcp",
        json={"jsonrpc": "2.0", "id": 0, "method": "initialize"},
    )

    response = await safe_transport.handle_async_request(initialize)

    assert response.status_code == 200
    assert safe_attempts == 2
    await response.aclose()
    await safe_transport.aclose()

    tool_attempts = 0

    def unavailable(request: httpx.Request) -> httpx.Response:
        nonlocal tool_attempts
        tool_attempts += 1
        return httpx.Response(503, request=request)

    tool_breakers = ServiceCircuitBreakerRegistry()
    tool_transport = _McpResilientTransport(
        httpx.MockTransport(unavailable),
        service_identity="https://tool.example.test/mcp",
        retry_settings=settings,
        breaker_settings=CircuitBreakerSettings(failure_threshold=1, open_seconds=30),
        breaker_registry=tool_breakers,
        timeout_seconds=1.0,
    )
    tool_call = httpx.Request(
        "POST",
        "https://tool.example.test/mcp",
        json={"jsonrpc": "2.0", "id": 1, "method": "tools/call"},
    )

    response = await tool_transport.handle_async_request(tool_call)
    assert response.status_code == 503
    assert tool_attempts == 1
    await response.aclose()
    with pytest.raises(CircuitOpenError):
        await tool_transport.handle_async_request(tool_call)
    assert tool_attempts == 1
    await tool_transport.aclose()


@pytest.mark.asyncio
async def test_obo_sessions_share_pool_without_sharing_caller_tokens(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Separate principal sessions keep their OBO headers while sharing one HTTPX client."""
    server = FastMCP("obo-fixture")

    @server.tool()
    def echo(value: str) -> str:
        """Return the supplied value to correlate each tool request."""
        return value

    server_app = server.streamable_http_app()
    observed: list[tuple[str, str | None]] = []

    async def recording_app(scope: Any, receive: Any, send: Any) -> None:
        """Record request body and bearer header after the MCP app handles it."""
        if scope["type"] != "http" or scope.get("method") != "POST":
            await server_app(scope, receive, send)
            return
        body = bytearray()

        async def recording_receive() -> dict[str, Any]:
            message = await receive()
            body.extend(message.get("body", b""))
            return message

        await server_app(scope, recording_receive, send)
        try:
            request = json.loads(body)
        except (UnicodeDecodeError, ValueError):
            return
        if isinstance(request, dict) and request.get("method") == "tools/call":
            arguments = request.get("params", {}).get("arguments", {})
            value = arguments.get("value") if isinstance(arguments, dict) else None
            headers = dict(scope.get("headers", ()))
            authorization = headers.get(b"authorization")
            observed.append(
                (str(value), None if authorization is None else authorization.decode())
            )

    def asgi_transport(**_kwargs: Any) -> httpx.ASGITransport:
        """Route the managed pool to the in-process OBO fixture."""
        return httpx.ASGITransport(app=recording_app)

    monkeypatch.setattr(httpx, "AsyncHTTPTransport", asgi_transport)

    class TokenSource:
        """Return a distinct downstream token for each verified subject token."""

        async def token_for(self, request: DelegatedTokenRequest) -> AccessToken:
            return AccessToken(
                f"mcp-{request.subject_token.expose()}",
                audience=request.audience,
            )

    binding = McpServerBinding(
        server="obo-fixture",
        transport=McpTransport.HTTP,
        capabilities=(Capability.TEST,),
        tools={"test": "echo"},
        url="http://127.0.0.1:8001/mcp",
    )
    connection = McpConnection(
        binding,
        delegated_oauth=OAuthTokenExchangeSettings("https://mcp.example.test"),
        delegated_token_source=TokenSource(),
    )
    client_ids: list[int] = []

    async with server_app.router.lifespan_context(server_app):
        async def call_as(subject: str) -> None:
            """Open the principal's isolated session and call through shared pool."""
            context = McpRequestContext(
                principal=AgentPrincipal(subject=subject),
                subject_token=AccessToken(f"subject-{subject}", audience="agent-api"),
                request_id=f"request-{subject}",
            )
            with McpRequestContextScope.bind(context):
                session = await connection.session()
                client_ids.append(id(connection._get_http_client()))
                await session.call_tool("echo", {"value": subject})

        await asyncio.gather(call_as("ada"), call_as("lin"))
        await connection.aclose()

    assert sorted(observed) == [
        ("ada", "Bearer mcp-subject-ada"),
        ("lin", "Bearer mcp-subject-lin"),
    ]
    assert len(set(client_ids)) == 1
