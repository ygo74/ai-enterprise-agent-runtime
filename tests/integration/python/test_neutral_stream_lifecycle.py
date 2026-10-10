import asyncio
import json
from collections.abc import AsyncIterator

import pytest
from ygo74.agent_runtime.domains.contracts import (
    AgentOutput,
    AgentStreamEvent,
    AudioContent,
    AudioDelta,
    AudioTranscriptDelta,
    ContentEnd,
    ContentEvent,
    ContentStart,
    EncodedMedia,
    ImageContent,
    MediaUri,
    Notification,
    ReasoningContent,
    TerminalEvent,
    Termination,
    TerminationStatus,
    TextContent,
    TextDelta,
    TokenUsage,
    ToolArgumentsDelta,
    ToolCallContent,
    ToolExecution,
    ToolResultContent,
    UsageEvent,
)
from ygo74.agent_runtime.domains.contracts.error_envelope import ErrorEnvelope
from ygo74.agent_runtime.domains.contracts.exchange_models import (
    StandardExchangeResponse,
)
from ygo74.agent_runtime.domains.mapping.output_projector import (
    OutputProtocol,
    ProjectionContext,
)
from ygo74.agent_runtime.domains.mapping.response_mapper import map_response
from ygo74.agent_runtime.domains.streaming.stream_processor import StreamProcessor


async def _events(events: tuple[object, ...]) -> AsyncIterator[object]:
    for event in events:
        yield event


async def _wire(events: tuple[object, ...], protocol: OutputProtocol) -> str:
    return "".join(
        [
            frame
            async for frame in StreamProcessor().stream(
                _events((UsageEvent(TokenUsage(1, 2)), *events)),
                ProjectionContext(protocol, "req", "route"),
            )
        ]
    )


@pytest.mark.parametrize("protocol", list(OutputProtocol))
@pytest.mark.parametrize(
    "events",
    [
        (),
        (ContentStart("open", TextContent("")), TerminalEvent()),
        (ContentEnd("unknown"),),
        (ContentEvent("dup", TextContent("")), ContentEvent("dup", TextContent(""))),
        ("legacy string",),
        ({"delta": "legacy map"},),
        (
            ContentStart("tool", ToolCallContent("c", "tool")),
            ToolArgumentsDelta("tool", "{"),
            ContentEnd("tool"),
        ),
        (ContentStart("text", TextContent("")), ToolArgumentsDelta("text", "{}")),
        (
            ContentStart("audio", AudioContent(EncodedMedia("", "audio/wav"), "a")),
            AudioDelta("audio", "YQ==", 1),
        ),
    ],
)
def test_invalid_order_and_missing_terminal_are_failures(
    protocol: OutputProtocol, events: tuple[object, ...]
) -> None:
    wire = asyncio.run(_wire(events, protocol))
    assert "invalid_agent_output" in wire
    assert "response.completed" not in wire
    assert '"finish_reason": "stop"' not in wire


@pytest.mark.parametrize("protocol", list(OutputProtocol))
def test_filtered_content_has_no_orphan_lifecycle_or_sensitive_logs(
    protocol: OutputProtocol, caplog: pytest.LogCaptureFixture
) -> None:
    events = (
        ContentEvent(
            "image1",
            ImageContent(MediaUri("https://secret.example/token", "image/png")),
        ),
        ContentEvent("image2", ImageContent(EncodedMedia("c2VjcmV0", "image/png"))),
        ContentStart("audio", AudioContent(EncodedMedia("", "audio/wav"), "audio")),
        AudioDelta("audio", "c2VjcmV0", 0),
        AudioTranscriptDelta("audio", "secret transcript"),
        ContentEnd("audio"),
        ContentStart(
            "tool",
            ToolCallContent(
                "internal-call", "private", execution=ToolExecution.INTERNAL
            ),
        ),
        ToolArgumentsDelta("tool", '{"secret":true}'),
        ContentEnd("tool"),
        ContentEvent(
            "result",
            ToolResultContent("internal-call", "private", {"secret": "result"}),
        ),
        ContentEvent("reasoning", ReasoningContent("secret reasoning")),
        TerminalEvent(),
    )
    with caplog.at_level("INFO"):
        wire = asyncio.run(_wire(events, protocol))
    assert "secret" not in caplog.text + wire
    assert "c2VjcmV0" not in caplog.text + wire
    assert "internal-call" not in wire
    assert "output_item.added" not in wire and "content_block_start" not in wire
    assert (
        "req" in caplog.text
        and "route" in caplog.text
        and "all_contents_filtered" in caplog.text
    )


@pytest.mark.parametrize("protocol", list(OutputProtocol))
@pytest.mark.parametrize("status", list(TerminationStatus))
def test_terminal_is_unique_and_producer_closed_before_terminal_is_visible(
    protocol: OutputProtocol, status: TerminationStatus
) -> None:
    closed: list[bool] = []
    advanced: list[bool] = []
    termination = Termination(
        status,
        "max_output_tokens" if status == TerminationStatus.INCOMPLETE else None,
        ErrorEnvelope("failed", "handler_execution", "Execution failed")
        if status == TerminationStatus.FAILED
        else None,
    )

    async def producer() -> AsyncIterator[AgentStreamEvent]:
        try:
            yield UsageEvent(TokenUsage(1, 2))
            yield ContentEvent("answer", TextContent("hello"))
            yield TerminalEvent(termination)
            advanced.append(True)
            yield TerminalEvent()
        finally:
            closed.append(True)

    async def consume() -> str:
        frames: list[str] = []
        async for frame in StreamProcessor().stream(
            producer(), ProjectionContext(protocol, "req")
        ):
            frames.append(frame)
            if any(
                marker in frame
                for marker in (
                    "response.completed",
                    "response.failed",
                    "response.incomplete",
                    '"finish_reason": "stop"',
                    '"finish_reason": "length"',
                    '"type": "error"',
                    '"type": "message_stop"',
                )
            ):
                assert closed == [True]
        return "".join(frames)

    wire = asyncio.run(consume())
    assert closed == [True]
    assert advanced == []
    if protocol == OutputProtocol.RESPONSES:
        assert (
            wire.count(
                f"event: response.{status.value if status != TerminationStatus.SUCCESS else 'completed'}\n"
            )
            == 1
        )
    if status == TerminationStatus.FAILED:
        assert (
            "response.completed" not in wire and '"finish_reason": "stop"' not in wire
        )


@pytest.mark.parametrize("protocol", list(OutputProtocol))
def test_final_results_are_supported_directly_awaited_and_in_exchange(
    protocol: OutputProtocol,
) -> None:
    output = AgentOutput(
        (TextContent("answer"), Notification("progress")), TokenUsage(2, 3, 5)
    )

    async def consume(result: object) -> str:
        return "".join(
            [
                frame
                async for frame in StreamProcessor().stream(
                    result, ProjectionContext(protocol, "req")
                )
            ]
        )

    async def awaited() -> AgentOutput:
        return output

    async def scenario() -> None:
        for result in (
            output,
            awaited(),
            StandardExchangeResponse("req", "success", output),
        ):
            wire = await consume(result)
            assert (
                "answer" in wire
                and "progress" in wire
                and "invalid_agent_output" not in wire
            )

    asyncio.run(scenario())
    business = map_response(protocol, output, request_id="req")
    assert "progress" not in json.dumps(business)


@pytest.mark.parametrize("protocol", list(OutputProtocol))
def test_usage_and_exposable_reasoning(protocol: OutputProtocol) -> None:
    wire = asyncio.run(
        _wire(
            (
                ContentStart("reasoning", ReasoningContent("", True)),
                TextDelta("reasoning", "summary"),
                ContentEnd("reasoning"),
                UsageEvent(
                    TokenUsage(
                        4,
                        6,
                        10,
                        cached_input_tokens=0,
                        reasoning_output_tokens=0,
                        cache_write_input_tokens=0,
                    )
                ),
                TerminalEvent(),
            ),
            protocol,
        )
    )
    assert ("summary" in wire) == (protocol == OutputProtocol.RESPONSES)
    assert '"output_tokens": 6' in wire or '"completion_tokens": 6' in wire


def test_cancellation_and_consumer_disconnect_close_the_producer() -> None:
    async def scenario() -> None:
        closed: list[bool] = []
        waiting = asyncio.Event()

        async def producer() -> AsyncIterator[AgentStreamEvent]:
            try:
                yield ContentStart("answer", TextContent(""))
                yield TextDelta("answer", "first")
                waiting.set()
                await asyncio.Event().wait()
            finally:
                closed.append(True)

        stream = StreamProcessor().stream(
            producer(), ProjectionContext(OutputProtocol.RESPONSES, "req")
        )
        while '"delta": "first"' not in await anext(stream):
            pass
        task = asyncio.create_task(anext(stream))
        await waiting.wait()
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert closed == [True]
        await stream.aclose()

        closed.clear()
        stream = StreamProcessor().stream(
            producer(), ProjectionContext(OutputProtocol.RESPONSES, "req2")
        )
        while '"delta": "first"' not in await anext(stream):
            pass
        await stream.aclose()
        assert closed == [True]

    asyncio.run(scenario())


def test_concurrent_invocations_have_independent_response_ids_and_state() -> None:
    async def scenario() -> list[str]:
        return await asyncio.gather(
            *[
                _wire(
                    (
                        ContentEvent("same-content-id", TextContent(f"answer-{index}")),
                        TerminalEvent(),
                    ),
                    OutputProtocol.RESPONSES,
                )
                for index in range(5)
            ]
        )

    wires = asyncio.run(scenario())
    ids = []
    for index, wire in enumerate(wires):
        events = [
            json.loads(line[6:])
            for line in wire.splitlines()
            if line.startswith("data: {")
        ]
        ids.append(events[-1]["response"]["id"])
        assert events[-1]["response"]["output_text"] == f"answer-{index}"
    assert len(set(ids)) == 5


def test_valid_anthropic_unrepresentable_tool_arguments_are_filtered_without_orphans() -> (
    None
):
    wire = asyncio.run(
        _wire(
            (
                ContentStart("tool", ToolCallContent("call", "lookup")),
                ToolArgumentsDelta("tool", "[1,2]"),
                ContentEnd("tool"),
                TerminalEvent(),
            ),
            OutputProtocol.ANTHROPIC_MESSAGES,
        )
    )
    assert "content_block_start" not in wire
    assert "invalid_agent_output" not in wire


@pytest.mark.parametrize("protocol", list(OutputProtocol))
def test_empty_tool_argument_delta_is_a_noop(protocol: OutputProtocol) -> None:
    wire = asyncio.run(
        _wire(
            (
                ContentStart("tool", ToolCallContent("call", "lookup")),
                ToolArgumentsDelta("tool", ""),
                ContentEnd("tool"),
                TerminalEvent(),
            ),
            protocol,
        )
    )
    assert "lookup" in wire
    assert "invalid_agent_output" not in wire
