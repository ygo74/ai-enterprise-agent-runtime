import asyncio
import json
from collections.abc import AsyncIterator

import pytest
from ygo74.agent_runtime.domains.contracts import (
    ContentEvent,
    TerminalEvent,
    TextContent,
    TokenUsage,
    UsageEvent,
)
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
