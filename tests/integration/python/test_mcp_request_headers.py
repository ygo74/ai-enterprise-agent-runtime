"""Request-scoped MCP header rendering and OAuth delegation contracts."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace

import anyio
import httpx
import pytest
from ygo74.agent_runtime.domains.auth.agent_principal import AgentPrincipal
from ygo74.agent_runtime.domains.auth.tokens import (
    AccessToken,
    DelegatedTokenRequest,
    TokenExchangeError,
)
from ygo74.agent_runtime.domains.mcp.binding import (
    McpNetworkSettings,
    _ContextualMcpWriteStream,
    _McpHttpClientFactory,
)
from ygo74.agent_runtime.domains.mcp.configuration import McpDelegatedOAuthSettings
from ygo74.agent_runtime.domains.mcp.request_context import (
    McpOutboundHeaderResolver,
    McpRequestContext,
    McpRequestContextRegistry,
    McpRequestContextScope,
    json_rpc_request_id,
)


def _context(
    subject: str,
    request_id: str,
    conversation_id: str,
    token: str = "",
) -> McpRequestContext:
    """Create one immutable MCP request context for the header contract tests."""
    principal = AgentPrincipal(
        subject=subject,
        email=f"{subject}@example.test",
        display_name=subject.title(),
        roles=frozenset({"reader", "writer"}),
    )
    return McpRequestContext(
        principal=principal,
        request_id=request_id,
        conversation_id=conversation_id,
        subject_token=AccessToken(token, audience="agent-api") if token else None,
    )


def test_header_resolver_renders_current_identity_request_and_session_values() -> None:
    """Headers use the values belonging to the JSON-RPC request being sent."""
    contexts = McpRequestContextRegistry()
    contexts.register(14, _context("ada", "req-ada", "chat-1"))
    resolver = McpOutboundHeaderResolver(
        {
            "X-User": "{{USER_ID}}/{{USER_EMAIL}}/{{USER_NAME}}",
            "X-Roles": "{{USER_ROLES}}",
            "X-Trace": "trace={{REQUEST_ID}}",
            "X-Conversation": "{{CONVERSATION_ID}}",
            "X-Session": "{{SESSION_ID}}",
        },
        contexts,
    )

    headers = asyncio.run(resolver.for_request(14))

    assert headers == {
        "X-User": "ada/ada@example.test/Ada",
        "X-Roles": "reader,writer",
        "X-Trace": "trace=req-ada",
        "X-Conversation": "chat-1",
        "X-Session": "chat-1",
    }


def test_header_resolver_keeps_concurrent_json_rpc_contexts_isolated() -> None:
    """An out-of-order HTTP send cannot pick another caller's identity or cache key."""
    contexts = McpRequestContextRegistry()
    contexts.register(1, _context("ada", "req-ada", "chat-ada"))
    contexts.register(2, _context("lin", "req-lin", "chat-lin"))
    resolver = McpOutboundHeaderResolver(
        {
            "X-User": "{{USER_ID}}",
            "X-Request": "{{REQUEST_ID}}",
            "X-Session": "{{SESSION_ID}}",
        },
        contexts,
    )

    async def scenario() -> tuple[dict[str, str], dict[str, str]]:
        return await asyncio.gather(resolver.for_request(2), resolver.for_request(1))

    lin_headers, ada_headers = asyncio.run(scenario())

    assert lin_headers == {
        "X-User": "lin",
        "X-Request": "req-lin",
        "X-Session": "chat-lin",
    }
    assert ada_headers == {
        "X-User": "ada",
        "X-Request": "req-ada",
        "X-Session": "chat-ada",
    }


def test_persistent_writer_correlates_each_message_before_the_http_hook_runs() -> None:
    """The SDK writer task may send requests out of order without swapping callers."""
    contexts = McpRequestContextRegistry()
    sent: list[object] = []

    class FakeWriteStream:
        """Capture SDK messages without starting a transport task."""

        async def send(self, message: object) -> None:
            sent.append(message)

    stream = _ContextualMcpWriteStream(
        FakeWriteStream(), contexts, McpRequestContextScope.current, json_rpc_request_id
    )

    async def enqueue(request_id: int, context: McpRequestContext) -> None:
        message = SimpleNamespace(
            message=SimpleNamespace(root=SimpleNamespace(id=request_id))
        )
        with McpRequestContextScope.bind(context):
            await stream.send(message)

    async def scenario() -> tuple[str, str]:
        await asyncio.gather(
            enqueue(31, _context("ada", "req-ada", "chat-ada")),
            enqueue(32, _context("lin", "req-lin", "chat-lin")),
        )
        resolver = McpOutboundHeaderResolver(
            {"X-User": "{{USER_ID}}", "X-Request": "{{REQUEST_ID}}"}, contexts
        )
        factory = _McpHttpClientFactory(McpNetworkSettings(), resolver)
        request_lin = httpx.Request("POST", "https://mcp.example.test", json={"id": 32})
        request_ada = httpx.Request("POST", "https://mcp.example.test", json={"id": 31})
        await factory._apply_request_headers(request_lin)
        await factory._apply_request_headers(request_ada)
        return request_lin.headers["x-user"], request_ada.headers["x-user"]

    lin_user, ada_user = asyncio.run(scenario())

    assert len(sent) == 2
    assert (lin_user, ada_user) == ("lin", "ada")


@pytest.mark.parametrize("raise_inside", [False, True])
def test_contextual_writer_preserves_the_sdk_async_context_lifecycle(
    raise_inside: bool,
) -> None:
    """The MCP session can enter and close its wrapped write stream.

    Args:
        raise_inside (bool): Whether session cleanup must propagate an error.
    """
    async def scenario() -> None:
        """Verify SDK stream cleanup on normal exit and session failure."""
        sender, receiver = anyio.create_memory_object_stream[object](1)
        wrapper = _ContextualMcpWriteStream(
            sender, McpRequestContextRegistry(), lambda: None, lambda message: None
        )
        try:
            async with wrapper as entered:
                assert entered is wrapper
                await entered.send("message")
                if raise_inside:
                    raise ValueError("session failure")
        except ValueError as error:
            assert raise_inside
            assert str(error) == "session failure"
        with pytest.raises(anyio.ClosedResourceError):
            await sender.send("after cleanup")
        await receiver.aclose()

    asyncio.run(scenario())


def test_obo_exchanges_the_verified_subject_and_sends_only_the_downstream_token() -> (
    None
):
    """The incoming bearer token is an exchange input and never an outbound header."""
    contexts = McpRequestContextRegistry()
    contexts.register(9, _context("ada", "req-ada", "chat-1", "incoming-subject-token"))

    class FakeOAuthOnBehalfOfTokenSource:
        """Return a token explicitly minted for the configured MCP audience."""

        def __init__(self) -> None:
            self.requests: list[DelegatedTokenRequest] = []

        async def token_for(self, request: DelegatedTokenRequest) -> AccessToken:
            self.requests.append(request)
            return AccessToken("mcp-audience-token", audience=request.audience)

    source = FakeOAuthOnBehalfOfTokenSource()
    resolver = McpOutboundHeaderResolver(
        {"X-User": "{{USER_ID}}"},
        contexts,
        delegated_oauth=McpDelegatedOAuthSettings(
            audience="https://mcp.example.test", scopes=("mail.read",)
        ),
        delegated_token_source=source,
    )

    http_request = httpx.Request(
        "POST", "https://mcp.example.test/mcp", json={"jsonrpc": "2.0", "id": 9}
    )
    factory = _McpHttpClientFactory(McpNetworkSettings(), resolver)
    asyncio.run(factory._apply_request_headers(http_request))
    headers = dict(http_request.headers)

    assert source.requests[0].principal.subject == "ada"
    assert source.requests[0].subject_token.expose() == "incoming-subject-token"
    assert source.requests[0].audience == "https://mcp.example.test"
    assert source.requests[0].scopes == ("mail.read",)
    assert headers["x-user"] == "ada"
    assert headers["authorization"] == "Bearer mcp-audience-token"
    assert "incoming-subject-token" not in headers.values()
    assert "incoming-subject-token" not in repr(source.requests[0])


def test_obo_rejects_missing_subject_token_without_falling_back() -> None:
    """A tokenless caller cannot use OBO or silently reuse a client token."""
    contexts = McpRequestContextRegistry()
    contexts.register(4, _context("ada", "req-ada", "chat-1"))

    class UnusedOAuthOnBehalfOfTokenSource:
        """Fail if the runtime attempts an exchange without a verified subject token."""

        async def token_for(self, request: DelegatedTokenRequest) -> AccessToken:
            raise AssertionError("token source must not be called")

    resolver = McpOutboundHeaderResolver(
        {},
        contexts,
        delegated_oauth=McpDelegatedOAuthSettings("https://mcp.example.test"),
        delegated_token_source=UnusedOAuthOnBehalfOfTokenSource(),
    )

    with pytest.raises(TokenExchangeError):
        asyncio.run(resolver.for_request(4))


def test_obo_rejects_wrong_audience_and_provider_failures() -> None:
    """Exchange failures and tokens minted for another resource fail closed."""
    contexts = McpRequestContextRegistry()
    contexts.register(5, _context("ada", "req-ada", "chat-1", "incoming-subject-token"))

    class WrongAudienceSource:
        """Return an otherwise valid token for the wrong resource."""

        async def token_for(self, request: DelegatedTokenRequest) -> AccessToken:
            return AccessToken("wrong-audience-token", audience="another-resource")

    wrong_audience = McpOutboundHeaderResolver(
        {},
        contexts,
        delegated_oauth=McpDelegatedOAuthSettings("https://mcp.example.test"),
        delegated_token_source=WrongAudienceSource(),
    )
    with pytest.raises(TokenExchangeError):
        asyncio.run(wrong_audience.for_request(5))

    class FailedSource:
        """Surface the provider's refusal without exposing the subject token."""

        async def token_for(self, request: DelegatedTokenRequest) -> AccessToken:
            raise TokenExchangeError("exchange rejected")

    failed_exchange = McpOutboundHeaderResolver(
        {},
        contexts,
        delegated_oauth=McpDelegatedOAuthSettings("https://mcp.example.test"),
        delegated_token_source=FailedSource(),
    )
    with pytest.raises(TokenExchangeError) as failure:
        asyncio.run(failed_exchange.for_request(5))

    assert "incoming-subject-token" not in str(failure.value)
    assert failure.value.__cause__ is None
