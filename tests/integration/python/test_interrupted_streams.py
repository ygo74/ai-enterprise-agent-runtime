import asyncio
from collections.abc import AsyncIterator

import pytest
from ygo74.agent_runtime.domains.contracts import (
    ContentEvent,
    TextContent,
    TokenUsage,
    UsageEvent,
)
from ygo74.agent_runtime.domains.errors import DomainError
from ygo74.agent_runtime.domains.mapping.output_projector import (
    OutputProtocol,
    ProjectionContext,
)
from ygo74.agent_runtime.domains.mcp.mcp_errors import McpBindingError
from ygo74.agent_runtime.domains.streaming.stream_processor import (
    StreamProcessor,
    safe_diagnostic_detail,
)


@pytest.mark.parametrize("protocol", list(OutputProtocol))
def test_interrupted_stream_maps_to_error_event(protocol: OutputProtocol) -> None:
    closed: list[bool] = []

    async def producer() -> AsyncIterator[object]:
        try:
            yield UsageEvent(TokenUsage(1, 2))
            yield ContentEvent("answer", TextContent("partial"))
            raise RuntimeError("sensitive producer internals")
        finally:
            closed.append(True)

    async def consume() -> str:
        return "".join(
            [
                frame
                async for frame in StreamProcessor().stream(
                    producer(), ProjectionContext(protocol, "r1")
                )
            ]
        )

    wire = asyncio.run(consume())
    assert closed == [True]
    assert "agent_execution_error" in wire
    assert "sensitive producer internals" not in wire
    assert "response.completed" not in wire
    assert '"finish_reason": "stop"' not in wire
    if protocol == OutputProtocol.RESPONSES:
        # A failed lifecycle event alone may be silently accumulated by clients.
        assert '"type": "error"' in wire
        assert wire.index('"type": "error"') < wire.index('"type": "response.failed"')


@pytest.mark.parametrize("protocol", list(OutputProtocol))
@pytest.mark.parametrize("error_type", [RuntimeError, DomainError, McpBindingError])
def test_streaming_failure_logs_safe_diagnostics_without_raw_message(
    protocol: OutputProtocol,
    error_type: type[Exception],
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A streaming failure must log an exception type and raising origin.

    These are the only safe, useful diagnostics an operator can act on: they
    pinpoint which component failed without ever logging the raw exception
    message, which may carry credentials, tokens, or upstream response
    bodies from a developer-supplied producer or handler.
    """

    async def producer() -> AsyncIterator[object]:
        yield UsageEvent(TokenUsage(1, 2))
        raise error_type(
            "api_key=sk-super-secret response_body={'leak': true}"
        )

    async def consume() -> str:
        return "".join(
            [
                frame
                async for frame in StreamProcessor().stream(
                    producer(), ProjectionContext(protocol, "r2", "mail-agent")
                )
            ]
        )

    with caplog.at_level("WARNING"):
        wire = asyncio.run(consume())

    assert "agent_execution_error" in wire
    assert "api_key=sk-super-secret" not in wire + caplog.text
    assert "response_body" not in wire + caplog.text
    assert error_type.__name__ in caplog.text
    assert "exception_type=" in caplog.text
    assert "origin=" in caplog.text
    assert "test_interrupted_streams.py" in caplog.text
    assert "req=r2" not in caplog.text  # request id is logged unprefixed
    assert "r2" in caplog.text
    assert "mail-agent" in caplog.text


@pytest.mark.parametrize("protocol", list(OutputProtocol))
def test_streaming_domain_error_logs_its_safe_message_detail(
    protocol: OutputProtocol, caplog: pytest.LogCaptureFixture
) -> None:
    """Explicit safe metadata is logged, but even a domain error's message is private."""

    class _McpBindingError(DomainError):
        pass

    async def producer() -> AsyncIterator[object]:
        yield UsageEvent(TokenUsage(1, 2))
        error = _McpBindingError("private provider token and retrieved mail")
        error.safe_diagnostic_detail = (
            "gmail-http.yaml: oauth.client_secret references "
            "environment variable 'MCP_MAIL_OBO_CLIENT_SECRET', which is not set"
        )
        raise error

    async def consume() -> str:
        return "".join(
            [
                frame
                async for frame in StreamProcessor().stream(
                    producer(), ProjectionContext(protocol, "r3", "mail-agent")
                )
            ]
        )

    with caplog.at_level("WARNING"):
        wire = asyncio.run(consume())

    assert "_McpBindingError" in caplog.text
    assert "MCP_MAIL_OBO_CLIENT_SECRET" in caplog.text
    assert "MCP_MAIL_OBO_CLIENT_SECRET" not in wire
    assert "private provider token and retrieved mail" not in wire + caplog.text
    assert "detail=" in caplog.text


def test_safe_diagnostic_metadata_is_single_line_and_bounded() -> None:
    error = DomainError("private message")
    assert safe_diagnostic_detail(error) is None
    error.safe_diagnostic_detail = "field\n\r\tname " + "x" * 2048
    detail = safe_diagnostic_detail(error)
    assert detail is not None
    assert detail.startswith("field name ")
    assert len(detail) == 1024
    assert "\n" not in detail
    assert "\r" not in detail

