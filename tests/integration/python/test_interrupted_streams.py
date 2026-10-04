import asyncio
from collections.abc import AsyncIterator

import pytest
from ygo74.agent_runtime.domains.contracts import (
    ContentEvent,
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
