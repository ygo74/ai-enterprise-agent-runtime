import asyncio
import json
from collections.abc import AsyncIterator

import pytest
from ygo74.agent_runtime.domains.contracts import (
    AgentOutput,
    AgentStreamEvent,
    ContentEvent,
    TerminalEvent,
    Termination,
    TerminationStatus,
    TextContent,
    TokenUsage,
    UsageEvent,
)
from ygo74.agent_runtime.domains.mapping.output_projector import (
    OutputProtocol,
    ProjectionContext,
)
from ygo74.agent_runtime.domains.mapping.response_mapper import ResponseMapper
from ygo74.agent_runtime.domains.streaming.stream_processor import StreamProcessor

pytest.importorskip(
    "openai",
    minversion="3.24.0",
    reason="Optional wire validation requires OpenAI SDK 3.24+",
)
from openai.types.chat import ChatCompletion, ChatCompletionChunk
from openai.types.responses import Response


@pytest.mark.parametrize(
    "total,cached,reasoning,cache_write",
    [
        (None, None, None, None),
        (3, None, None, None),
        (3, 0, None, None),
        (3, None, 0, None),
        (None, 0, 0, 0),
        (3, 0, 0, None),
        (3, 0, 0, 0),
        (3, 1, 1, 1),
    ],
)
def test_known_usage_is_schema_valid_and_incomplete_usage_is_safely_filtered(
    total: int | None,
    cached: int | None,
    reasoning: int | None,
    cache_write: int | None,
    caplog: pytest.LogCaptureFixture,
) -> None:
    usage = TokenUsage(
        1,
        2,
        total,
        cached_input_tokens=cached,
        reasoning_output_tokens=reasoning,
        cache_write_input_tokens=cache_write,
    )
    mapper = ResponseMapper()
    output = AgentOutput((TextContent("answer"),), usage)
    for protocol in OutputProtocol:
        with caplog.at_level("INFO"):
            wire = mapper.project(
                output, ProjectionContext(protocol, "request", "route", "model")
            )
        if protocol == OutputProtocol.CHAT_COMPLETIONS:
            parsed = ChatCompletion.model_validate(wire)
            assert (parsed.usage is not None) == (total is not None)
            assert ("usage" in wire) == (total is not None)
            if parsed.usage is not None:
                assert parsed.usage.total_tokens == total
                if cached is not None:
                    assert parsed.usage.prompt_tokens_details.cached_tokens == cached
                if cache_write is not None:
                    assert (
                        parsed.usage.prompt_tokens_details.cache_write_tokens
                        == cache_write
                    )
                if reasoning is not None:
                    assert (
                        parsed.usage.completion_tokens_details.reasoning_tokens
                        == reasoning
                    )
        elif protocol == OutputProtocol.RESPONSES:
            parsed = Response.model_validate(wire)
            complete = (
                total is not None
                and cached is not None
                and reasoning is not None
                and cache_write is not None
            )
            assert (parsed.usage is not None) == complete
            if complete:
                assert parsed.usage.input_tokens_details.cached_tokens == cached
                assert (
                    parsed.usage.input_tokens_details.cache_write_tokens == cache_write
                )
                assert parsed.usage.output_tokens_details.reasoning_tokens == reasoning
                assert parsed.usage.total_tokens == total
            else:
                assert wire["usage"] is None
        else:
            assert wire["usage"]["input_tokens"] == 1
            assert wire["usage"]["output_tokens"] == 2
    if total is None or cached is None or reasoning is None or cache_write is None:
        assert "incomplete_usage" in caplog.text
        assert "request" in caplog.text and "route" in caplog.text
        assert "input_tokens" not in caplog.text and "output_tokens" not in caplog.text


@pytest.mark.parametrize(
    "protocol", [OutputProtocol.CHAT_COMPLETIONS, OutputProtocol.RESPONSES]
)
@pytest.mark.parametrize("complete", [True, False])
def test_stream_terminal_usage_matches_real_sdk_schema(
    protocol: OutputProtocol, complete: bool
) -> None:
    async def producer() -> AsyncIterator[AgentStreamEvent]:
        yield ContentEvent("answer", TextContent("answer"))
        yield UsageEvent(
            TokenUsage(
                1,
                2,
                3,
                cached_input_tokens=0,
                reasoning_output_tokens=0,
                cache_write_input_tokens=0,
            )
            if complete
            else TokenUsage(1, 2)
        )
        yield TerminalEvent()

    async def consume() -> str:
        return "".join(
            [
                frame
                async for frame in StreamProcessor().stream(
                    producer(), ProjectionContext(protocol, "request", "route", "model")
                )
            ]
        )

    frames = [
        json.loads(line[6:])
        for line in asyncio.run(consume()).splitlines()
        if line.startswith("data: {")
    ]
    if protocol == OutputProtocol.RESPONSES:
        parsed = Response.model_validate(frames[-1]["response"])
    else:
        for frame in frames:
            ChatCompletionChunk.model_validate(frame)
        parsed = ChatCompletionChunk.model_validate(frames[-1])
    assert (parsed.usage is not None) == complete


@pytest.mark.parametrize(
    "protocol", [OutputProtocol.CHAT_COMPLETIONS, OutputProtocol.RESPONSES]
)
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
def test_incomplete_source_reasons_are_translated_to_native_sdk_literals(
    protocol: OutputProtocol,
    streaming: bool,
    reason: str | None,
    caplog: pytest.LogCaptureFixture,
) -> None:
    context = ProjectionContext(protocol, "request", "route", "model")
    output = AgentOutput(
        (TextContent("answer"),),
        termination=Termination(TerminationStatus.INCOMPLETE, reason),
    )

    async def consume() -> list[dict[str, object]]:
        frames = "".join(
            [frame async for frame in StreamProcessor().stream(output, context)]
        )
        return [
            json.loads(line[6:])
            for line in frames.splitlines()
            if line.startswith("data: {")
        ]

    with caplog.at_level("INFO"):
        if streaming:
            frames = asyncio.run(consume())
            if protocol == OutputProtocol.RESPONSES:
                parsed = Response.model_validate(frames[-1]["response"])
            else:
                parsed = ChatCompletionChunk.model_validate(frames[-1])
        else:
            wire = ResponseMapper().project(output, context)
            parsed = (
                Response.model_validate(wire)
                if protocol == OutputProtocol.RESPONSES
                else ChatCompletion.model_validate(wire)
            )
    if protocol == OutputProtocol.RESPONSES:
        if reason in ("private-unknown", None):
            assert parsed.incomplete_details is None
            if reason is not None:
                assert "unsupported_termination_reason" in caplog.text
        else:
            assert parsed.incomplete_details.reason == (
                "content_filter" if reason == "content_filter" else "max_output_tokens"
            )
    else:
        assert parsed.choices[0].finish_reason == (
            "content_filter" if reason == "content_filter" else "length"
        )
    assert "private-unknown" not in caplog.text
