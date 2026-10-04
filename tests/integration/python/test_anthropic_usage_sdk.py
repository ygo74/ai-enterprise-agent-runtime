import asyncio
import json
from collections.abc import AsyncIterator

import pytest
from fastapi import FastAPI
from ygo74.agent_runtime.domains.contracts import (
    AgentOutput,
    AgentStreamEvent,
    ContentEnd,
    ContentEvent,
    ContentStart,
    ErrorEnvelope,
    TerminalEvent,
    Termination,
    TerminationStatus,
    TextContent,
    TokenUsage,
    ToolArgumentsDelta,
    ToolCallContent,
    UsageEvent,
)
from ygo74.agent_runtime.domains.endpoints.fastapi_endpoints import add_ai_endpoints
from ygo74.agent_runtime.domains.mapping.output_projector import (
    OutputProjectionError,
    OutputProtocol,
    ProjectionContext,
)
from ygo74.agent_runtime.domains.mapping.response_mapper import ResponseMapper
from ygo74.agent_runtime.domains.streaming.stream_processor import StreamProcessor

anthropic = pytest.importorskip("anthropic", minversion="1.11.0")
from anthropic import _base_client
from anthropic.types import Message, RawMessageDeltaEvent, RawMessageStartEvent

sdk_httpx = getattr(_base_client, "httpx2", getattr(_base_client, "httpx", None))
CONTEXT = ProjectionContext(
    OutputProtocol.ANTHROPIC_MESSAGES, "request", "route", "model"
)


@pytest.mark.parametrize("cache_known", [False, True])
def test_final_message_requires_known_usage_and_matches_sdk(cache_known: bool) -> None:
    mapper = ResponseMapper()
    with pytest.raises(
        OutputProjectionError, match="requires known input/output token usage"
    ):
        mapper.project(AgentOutput((TextContent("answer"),)), CONTEXT)
    wire = mapper.project(
        AgentOutput(
            (TextContent("answer"),),
            TokenUsage(
                7,
                2,
                cached_input_tokens=3 if cache_known else None,
                cache_write_input_tokens=1 if cache_known else None,
            ),
        ),
        CONTEXT,
    )
    parsed = Message.model_validate(wire)
    assert parsed.usage.input_tokens == 7
    assert parsed.usage.output_tokens == 2
    assert parsed.usage.cache_read_input_tokens == (3 if cache_known else None)
    assert parsed.usage.cache_creation_input_tokens == (1 if cache_known else None)


@pytest.mark.parametrize("completed_output", [False, True])
def test_stream_start_and_delta_have_real_sdk_usage(completed_output: bool) -> None:
    async def producer() -> AsyncIterator[AgentStreamEvent]:
        yield UsageEvent(TokenUsage(0, 0, 0))
        yield ContentEvent("answer", TextContent("answer"))
        yield UsageEvent(TokenUsage(7, 2))
        yield TerminalEvent()

    async def consume() -> str:
        source = (
            AgentOutput((TextContent("answer"),), TokenUsage(7, 2))
            if completed_output
            else producer()
        )
        return "".join(
            [frame async for frame in StreamProcessor().stream(source, CONTEXT)]
        )

    frames = [
        json.loads(line[6:])
        for line in asyncio.run(consume()).splitlines()
        if line.startswith("data: {")
    ]
    start = RawMessageStartEvent.model_validate(frames[0])
    delta = RawMessageDeltaEvent.model_validate(frames[-2])
    assert start.message.usage.input_tokens == (7 if completed_output else 0)
    assert start.message.usage.output_tokens == (2 if completed_output else 0)
    assert delta.usage.input_tokens == 7
    assert delta.usage.output_tokens == 2
    assert frames[-1]["type"] == "message_stop"


@pytest.mark.parametrize("late_usage", [False, True])
def test_missing_initial_usage_fails_and_closes_without_invalid_start(
    late_usage: bool,
) -> None:
    closed: list[bool] = []
    advanced: list[bool] = []

    async def producer() -> AsyncIterator[AgentStreamEvent]:
        try:
            yield ContentEvent("answer", TextContent("answer"))
            advanced.append(True)
            if late_usage:
                yield UsageEvent(TokenUsage(7, 2))
            yield TerminalEvent()
        finally:
            closed.append(True)

    async def consume() -> list[str]:
        frames = []
        async for frame in StreamProcessor().stream(producer(), CONTEXT):
            assert closed == [True]
            frames.append(frame)
        return frames

    wire = "".join(asyncio.run(consume()))
    assert "unsupported_output_projection" in wire
    assert "usage" in wire
    assert "message_start" not in wire and "message_stop" not in wire
    assert "answer" not in wire
    assert advanced == []
    assert closed == [True]


@pytest.mark.parametrize("known_usage", [False, True])
def test_real_anthropic_client_consumes_known_usage_or_projection_error(
    known_usage: bool,
) -> None:
    closed: list[bool] = []

    async def producer() -> AsyncIterator[AgentStreamEvent]:
        try:
            if known_usage:
                yield UsageEvent(TokenUsage(0, 0, 0))
            yield ContentEvent("answer", TextContent("answer"))
            yield UsageEvent(TokenUsage(7, 2))
            yield TerminalEvent()
        finally:
            closed.append(True)

    async def scenario() -> None:
        app = FastAPI()
        add_ai_endpoints(
            app,
            lambda _: producer(),
            default_route_key="route",
            enable_anthropic_messages=True,
        )
        async with (
            sdk_httpx.AsyncClient(
                transport=sdk_httpx.ASGITransport(app=app), base_url="http://runtime"
            ) as http_client,
            anthropic.AsyncAnthropic(
                api_key="test-key", base_url="http://runtime", http_client=http_client
            ) as client,
        ):

            async def consume() -> Message:
                async with client.messages.stream(
                    model="model",
                    max_tokens=10,
                    messages=[{"role": "user", "content": "question"}],
                ) as stream:
                    assert (
                        "".join([text async for text in stream.text_stream]) == "answer"
                    )
                    return await stream.get_final_message()

            if known_usage:
                final = await consume()
                assert final.usage.input_tokens == 7
                assert final.usage.output_tokens == 2
                assert final.stop_reason == "end_turn"
            else:
                with pytest.raises(
                    anthropic.APIError, match="known input/output token usage"
                ):
                    await consume()
            assert closed == [True]

    asyncio.run(scenario())


def test_nonstream_unknown_usage_returns_explicit_http_failure() -> None:
    async def scenario() -> None:
        app = FastAPI()
        add_ai_endpoints(
            app,
            lambda _: AgentOutput((TextContent("private answer"),)),
            default_route_key="route",
            enable_anthropic_messages=True,
        )
        async with sdk_httpx.AsyncClient(
            transport=sdk_httpx.ASGITransport(app=app), base_url="http://runtime"
        ) as client:
            response = await client.post(
                "/v1/messages", json={"model": "model", "messages": []}
            )
        assert response.status_code == 500
        error = response.json()["detail"]["error"]
        assert error["code"] == "unsupported_output_projection"
        assert error["category"] == "projection"
        assert "known input/output token usage" in error["message"]
        assert "private answer" not in response.text

    asyncio.run(scenario())


@pytest.mark.parametrize("failed", [False, True])
def test_usage_free_terminal_closes_once_and_never_emits_invalid_success(
    failed: bool,
) -> None:
    class Producer:
        def __init__(self) -> None:
            self.closes = 0

        def __aiter__(self) -> "Producer":
            return self

        async def __anext__(self) -> AgentStreamEvent:
            return TerminalEvent(
                Termination(
                    TerminationStatus.FAILED,
                    error=ErrorEnvelope(
                        "native_failure", "handler_execution", "Failed"
                    ),
                )
                if failed
                else Termination()
            )

        async def aclose(self) -> None:
            self.closes += 1

    async def scenario() -> None:
        producer = Producer()
        frames = [frame async for frame in StreamProcessor().stream(producer, CONTEXT)]
        assert producer.closes == 1
        assert len(frames) == 1
        assert (
            "native_failure" in frames[0]
            if failed
            else ("unsupported_output_projection" in frames[0])
        )
        assert "message_start" not in frames[0] and "message_stop" not in frames[0]

    asyncio.run(scenario())


def test_completed_failed_output_preserves_original_error_without_usage() -> None:
    async def scenario() -> None:
        output = AgentOutput(
            (TextContent("private partial answer"),),
            termination=Termination(
                TerminationStatus.FAILED,
                error=ErrorEnvelope("native_failure", "handler_execution", "Failed"),
            ),
        )
        frames = [frame async for frame in StreamProcessor().stream(output, CONTEXT)]
        assert len(frames) == 1
        assert "native_failure" in frames[0]
        assert "unsupported_output_projection" not in frames[0]
        assert "private partial answer" not in frames[0]
        assert "message_start" not in frames[0]

    asyncio.run(scenario())


def test_deferred_tool_can_supply_known_usage_before_its_first_wire_block() -> None:
    async def producer() -> AsyncIterator[AgentStreamEvent]:
        yield ContentStart("tool", ToolCallContent("call", "lookup"))
        yield ToolArgumentsDelta("tool", '{"city":"Paris"}')
        yield UsageEvent(TokenUsage(7, 2))
        yield ContentEnd("tool")
        yield TerminalEvent()

    async def scenario() -> None:
        wire = "".join(
            [frame async for frame in StreamProcessor().stream(producer(), CONTEXT)]
        )
        frames = [
            json.loads(line[6:])
            for line in wire.splitlines()
            if line.startswith("data: {")
        ]
        RawMessageStartEvent.model_validate(frames[0])
        assert frames[1]["content_block"]["type"] == "tool_use"
        assert frames[2]["delta"]["partial_json"] == '{"city": "Paris"}'
        assert (
            RawMessageDeltaEvent.model_validate(frames[-2]).delta.stop_reason
            == "tool_use"
        )
        assert "unsupported_output_projection" not in wire

    asyncio.run(scenario())


def test_cancellation_waiting_for_initial_usage_closes_producer() -> None:
    async def scenario() -> None:
        waiting = asyncio.Event()
        closed: list[bool] = []

        async def producer() -> AsyncIterator[AgentStreamEvent]:
            try:
                waiting.set()
                await asyncio.Event().wait()
                yield UsageEvent(TokenUsage(7, 2))
            finally:
                closed.append(True)

        stream = StreamProcessor().stream(producer(), CONTEXT)
        task = asyncio.create_task(anext(stream))
        await waiting.wait()
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        await stream.aclose()
        assert closed == [True]

    asyncio.run(scenario())


def test_developer_empty_baseline_precedes_backend_execution_and_updates_both_counts() -> (
    None
):
    async def scenario() -> None:
        backend_started = False

        async def producer() -> AsyncIterator[AgentStreamEvent]:
            nonlocal backend_started
            yield UsageEvent(TokenUsage(0, 0, 0))
            backend_started = True
            yield ContentEvent("answer", TextContent("answer"))
            yield UsageEvent(TokenUsage(7, 2))
            yield TerminalEvent()

        stream = StreamProcessor().stream(producer(), CONTEXT)
        first = await anext(stream)
        assert not backend_started
        start = RawMessageStartEvent.model_validate(
            json.loads(
                next(
                    line[6:] for line in first.splitlines() if line.startswith("data: ")
                )
            )
        )
        assert start.message.usage.input_tokens == 0
        assert start.message.usage.output_tokens == 0
        rest = "".join([frame async for frame in stream])
        frames = [
            json.loads(line[6:])
            for line in rest.splitlines()
            if line.startswith("data: {")
        ]
        delta = RawMessageDeltaEvent.model_validate(frames[-2])
        assert backend_started
        assert delta.usage.input_tokens == 7
        assert delta.usage.output_tokens == 2
        assert frames[-1]["type"] == "message_stop"

    asyncio.run(scenario())


@pytest.mark.parametrize("streaming", [False, True])
@pytest.mark.parametrize(
    "reason",
    [
        "length",
        "max_tokens",
        "max_output_tokens",
        "content_filter",
        "private-unknown",
        None,
    ],
)
def test_anthropic_incomplete_reason_never_fabricates_token_limit_for_filter(
    streaming: bool, reason: str | None, caplog: pytest.LogCaptureFixture
) -> None:
    output = AgentOutput(
        (TextContent("answer"),),
        TokenUsage(7, 2),
        Termination(TerminationStatus.INCOMPLETE, reason),
    )

    async def consume() -> list[dict[str, object]]:
        return [
            json.loads(line[6:])
            for frame in [
                frame async for frame in StreamProcessor().stream(output, CONTEXT)
            ]
            for line in frame.splitlines()
            if line.startswith("data: {")
        ]

    with caplog.at_level("INFO"):
        if streaming:
            frames = asyncio.run(consume())
            RawMessageStartEvent.model_validate(frames[0])
            native_reason = RawMessageDeltaEvent.model_validate(
                frames[-2]
            ).delta.stop_reason
            assert frames[-1]["type"] == "message_stop"
        else:
            native_reason = Message.model_validate(
                ResponseMapper().project(output, CONTEXT)
            ).stop_reason
    if reason in ("content_filter", "private-unknown", None):
        assert native_reason is None
        if reason is not None:
            assert "unsupported_termination_reason" in caplog.text
    else:
        assert native_reason == "max_tokens"
    assert "private-unknown" not in caplog.text
