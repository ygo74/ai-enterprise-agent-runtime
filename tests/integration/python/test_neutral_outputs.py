import json
from collections.abc import AsyncIterator

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from ygo74.agent_runtime.domains.contracts import (
    AgentOutput,
    AudioContent,
    AudioFormat,
    ContentEnd,
    ContentEvent,
    ContentStart,
    EncodedMedia,
    ImageContent,
    MediaUri,
    Notification,
    ReasoningContent,
    TerminalEvent,
    TextContent,
    TextDelta,
    TokenUsage,
    ToolArgumentsDelta,
    ToolCallContent,
    ToolExecution,
    UsageEvent,
)
from ygo74.agent_runtime.domains.endpoints.fastapi_endpoints import add_ai_endpoints
from ygo74.agent_runtime.domains.mapping.output_projector import OutputProtocol
from ygo74.agent_runtime.domains.mapping.response_mapper import map_response

PROTOCOLS = list(OutputProtocol)
PATHS = {
    OutputProtocol.CHAT_COMPLETIONS: "/v1/chat/completions",
    OutputProtocol.RESPONSES: "/v1/responses",
    OutputProtocol.ANTHROPIC_MESSAGES: "/v1/messages",
}


@pytest.mark.parametrize("protocol", PROTOCOLS)
def test_incomplete_usage_is_filtered_only_where_protocol_requires_more_counts(
    protocol: OutputProtocol,
    caplog: pytest.LogCaptureFixture,
) -> None:
    with caplog.at_level("INFO"):
        wire = map_response(
            protocol,
            AgentOutput((TextContent("answer"),), TokenUsage(1, 2)),
            request_id="request",
            route_key="route",
        )
    if protocol == OutputProtocol.CHAT_COMPLETIONS:
        assert "usage" not in wire
        assert "incomplete_usage" in caplog.text
    elif protocol == OutputProtocol.RESPONSES:
        assert wire["usage"] is None
        assert "incomplete_usage" in caplog.text
    else:
        assert wire["usage"] == {"input_tokens": 1, "output_tokens": 2}
        assert "incomplete_usage" not in caplog.text


def test_known_zero_usage_breakdowns_are_preserved_not_fabricated() -> None:
    wire = map_response(
        "openai.responses",
        AgentOutput(
            usage=TokenUsage(
                1,
                2,
                3,
                cached_input_tokens=0,
                reasoning_output_tokens=0,
                cache_write_input_tokens=0,
            )
        ),
    )
    assert wire["usage"] == {
        "input_tokens": 1,
        "output_tokens": 2,
        "total_tokens": 3,
        "input_tokens_details": {"cached_tokens": 0, "cache_write_tokens": 0},
        "output_tokens_details": {"reasoning_tokens": 0},
    }


@pytest.mark.parametrize("protocol", PROTOCOLS)
def test_business_output_filters_notifications_and_media_safely(
    protocol: OutputProtocol, caplog: pytest.LogCaptureFixture
) -> None:
    output = AgentOutput(
        (
            TextContent("answer"),
            Notification("secret-notice"),
            ImageContent(
                MediaUri("https://secret.example/image?token=secret", "image/png")
            ),
            ToolCallContent(
                "internal", "search", {"secret": "value"}, ToolExecution.INTERNAL
            ),
        ),
        usage=TokenUsage(2, 3, 5),
    )
    with caplog.at_level("INFO"):
        wire = map_response(protocol, output, request_id="req", route_key="route")
    assert "answer" in json.dumps(wire)
    assert "secret" not in json.dumps(wire) + caplog.text
    assert "req" in caplog.text and "route" in caplog.text
    assert "notification_nonstream" in caplog.text
    assert "unsupported_assistant_image" in caplog.text


@pytest.mark.parametrize("protocol", PROTOCOLS)
def test_client_tools_and_reasoning_are_honest(protocol: OutputProtocol) -> None:
    output = AgentOutput(
        (
            ToolCallContent("call", "lookup", {"city": "Paris"}),
            ReasoningContent("public summary", exposable=True),
        ),
        TokenUsage(1, 2),
    )
    wire = map_response(protocol, output, request_id="req")
    assert "lookup" in json.dumps(wire) and "Paris" in json.dumps(wire)
    assert ("public summary" in json.dumps(wire)) == (
        protocol == OutputProtocol.RESPONSES
    )


@pytest.mark.parametrize("protocol", PROTOCOLS)
@pytest.mark.parametrize("audio_format", list(AudioFormat))
def test_encoded_audio_only_when_protocol_can_represent_it(
    protocol: OutputProtocol,
    audio_format: AudioFormat,
) -> None:
    mime_types = {
        AudioFormat.WAV: "audio/wav",
        AudioFormat.MP3: "audio/mpeg",
        AudioFormat.PCM16: "audio/L16",
        AudioFormat.FLAC: "audio/flac",
        AudioFormat.OPUS: "audio/opus",
        AudioFormat.AAC: "audio/aac",
    }
    output = AgentOutput(
        (
            AudioContent(
                EncodedMedia("YQ==", mime_types[audio_format]),
                "audio",
                format=audio_format,
                expires_at=12345,
            ),
        ),
        TokenUsage(1, 2),
    )
    wire = map_response(protocol, output, request_id="req")
    assert ("YQ==" in json.dumps(wire)) == (protocol == OutputProtocol.CHAT_COMPLETIONS)


@pytest.mark.parametrize("protocol", PROTOCOLS)
def test_incremental_typed_stream_and_correlated_tools(
    protocol: OutputProtocol,
) -> None:
    async def stream(_: dict[str, object]) -> AsyncIterator[object]:
        yield UsageEvent(TokenUsage(1, 2))
        yield ContentEvent("notice", Notification("working"))
        yield ContentStart("answer", TextContent(""))
        yield TextDelta("answer", "hello")
        yield ContentStart("tool1", ToolCallContent("c1", "one"))
        yield ContentStart("tool2", ToolCallContent("c2", "two"))
        yield ToolArgumentsDelta("tool1", '{"a":')
        yield ToolArgumentsDelta("tool2", '{"b":2}')
        yield TextDelta("answer", " world")
        yield ToolArgumentsDelta("tool1", "1}")
        yield ContentEnd("tool2")
        yield ContentEnd("tool1")
        yield ContentEnd("answer")
        yield TerminalEvent()

    app = FastAPI()
    add_ai_endpoints(
        app, stream, default_route_key="demo", enable_anthropic_messages=True
    )
    with TestClient(app) as client:
        response = client.post(
            PATHS[protocol], json={"model": "demo", "input": "hi", "stream": True}
        )
    assert response.status_code == 200
    assert (
        "working" in response.text
        and "hello" in response.text
        and "world" in response.text
    )
    assert "c1" in response.text and "c2" in response.text
    assert "invalid_agent_output" not in response.text
    if protocol == OutputProtocol.RESPONSES:
        events = [
            json.loads(line[6:])
            for line in response.text.splitlines()
            if line.startswith("data: {")
        ]
        terminal = [event for event in events if event["type"] == "response.completed"]
        assert len(terminal) == 1
        assert terminal[0]["response"]["output_text"] == "workinghello world"
        assert terminal[0]["response"]["output"][0]["content"][0]["text"] == "working"


@pytest.mark.parametrize("protocol", PROTOCOLS)
def test_invalid_stream_is_error_not_success_and_closes_producer(
    protocol: OutputProtocol,
) -> None:
    closed: list[bool] = []

    async def stream(_: dict[str, object]) -> AsyncIterator[object]:
        try:
            yield TextDelta("missing", "secret")
            yield TerminalEvent()
        finally:
            closed.append(True)

    app = FastAPI()
    add_ai_endpoints(
        app, stream, default_route_key="demo", enable_anthropic_messages=True
    )
    with TestClient(app) as client:
        response = client.post(PATHS[protocol], json={"input": "hi", "stream": True})
    assert closed == [True]
    assert "invalid_agent_output" in response.text
    assert "response.completed" not in response.text
    assert '"finish_reason": "stop"' not in response.text
