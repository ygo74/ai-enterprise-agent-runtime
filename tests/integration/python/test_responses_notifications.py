import asyncio
import json
from collections.abc import AsyncIterator

import pytest
from ygo74.agent_runtime.domains.contracts import (
    AgentOutput,
    AgentStreamEvent,
    ContentEvent,
    ContentStart,
    ErrorEnvelope,
    Notification,
    TerminalEvent,
    Termination,
    TerminationStatus,
    TextContent,
)
from ygo74.agent_runtime.domains.mapping.output_projector import (
    OutputProtocol,
    ProjectionContext,
)
from ygo74.agent_runtime.domains.mapping.response_mapper import map_response
from ygo74.agent_runtime.domains.streaming.stream_processor import StreamProcessor


@pytest.mark.parametrize("answer", [True, False])
def test_responses_notice_wire_snapshot_preserves_emitted_indices_and_text(
    answer: bool,
) -> None:
    async def producer() -> AsyncIterator[AgentStreamEvent]:
        yield ContentEvent("notice", Notification("Working. "))
        if answer:
            yield ContentEvent("answer", TextContent("Answer."))
        yield TerminalEvent()

    async def consume() -> str:
        return "".join(
            [
                frame
                async for frame in StreamProcessor().stream(
                    producer(), ProjectionContext(OutputProtocol.RESPONSES, "request")
                )
            ]
        )

    events = [
        json.loads(line[6:])
        for line in asyncio.run(consume()).splitlines()
        if line.startswith("data: {")
    ]
    response = events[-1]["response"]
    items = response["output"]
    added = [event for event in events if event["type"] == "response.output_item.added"]
    done = [event for event in events if event["type"] == "response.output_item.done"]
    assert len(items) == len(added) == len(done) == (2 if answer else 1)
    for event in added + done:
        assert items[event["output_index"]]["id"] == event["item"]["id"]
    for event in events:
        if "item_id" in event and "output_index" in event:
            assert items[event["output_index"]]["id"] == event["item_id"]
    streamed_text = "".join(
        event["delta"]
        for event in events
        if event["type"] == "response.output_text.delta"
    )
    assert (
        response["output_text"]
        == streamed_text
        == ("Working. Answer." if answer else "Working. ")
    )
    assert items[0]["content"][0]["text"] == "Working. "


@pytest.mark.parametrize("answer", [True, False])
def test_nonstream_still_excludes_and_logs_notifications(
    answer: bool, caplog: pytest.LogCaptureFixture
) -> None:
    contents = (
        (Notification("Working. "), TextContent("Answer."))
        if answer
        else (Notification("Working. "),)
    )
    with caplog.at_level("INFO"):
        response = map_response(
            "openai.responses", AgentOutput(contents), request_id="request"
        )
    assert response["output_text"] == ("Answer." if answer else "")
    assert len(response["output"]) == (1 if answer else 0)
    assert "Working." not in json.dumps(response)
    assert "notification_nonstream" in caplog.text


def test_failed_snapshot_does_not_shift_closed_notice_after_open_answer() -> None:
    async def producer() -> AsyncIterator[AgentStreamEvent]:
        yield ContentStart("answer", TextContent("Partial. "))
        yield ContentEvent("notice", Notification("Working."))
        yield TerminalEvent(
            Termination(
                TerminationStatus.FAILED,
                error=ErrorEnvelope("failed", "handler_execution", "Failed"),
            )
        )

    async def consume() -> str:
        return "".join(
            [
                frame
                async for frame in StreamProcessor().stream(
                    producer(), ProjectionContext(OutputProtocol.RESPONSES, "request")
                )
            ]
        )

    events = [
        json.loads(line[6:])
        for line in asyncio.run(consume()).splitlines()
        if line.startswith("data: {")
    ]
    response = events[-1]["response"]
    assert response["status"] == "failed"
    assert response["output"][0]["status"] == "in_progress"
    notice_done = next(
        event for event in events if event["type"] == "response.output_item.done"
    )
    assert notice_done["output_index"] == 1
    assert response["output"][1]["id"] == notice_done["item"]["id"]
    assert response["output_text"] == "Partial. Working."
