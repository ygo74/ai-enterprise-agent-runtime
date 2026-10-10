import asyncio
import json
from collections.abc import AsyncIterator

import pytest
from ygo74.agent_runtime.domains.contracts import (
    AgentOutput,
    AgentStreamEvent,
    ContentEnd,
    ContentStart,
    TerminalEvent,
    TextContent,
    TextDelta,
    TokenUsage,
    UrlCitation,
)
from ygo74.agent_runtime.domains.mapping.output_normalizer import (
    OutputNormalizer,
    OutputValidationError,
)
from ygo74.agent_runtime.domains.mapping.output_projector import (
    OutputProtocol,
    ProjectionContext,
)
from ygo74.agent_runtime.domains.mapping.response_mapper import map_response
from ygo74.agent_runtime.domains.streaming.stream_processor import StreamProcessor


@pytest.mark.parametrize("protocol", list(OutputProtocol))
def test_typed_citations_keep_text_and_project_only_when_supported(
    protocol: OutputProtocol, caplog: pytest.LogCaptureFixture
) -> None:
    output = AgentOutput(
        (
            TextContent(
                "Answer",
                (UrlCitation("https://secret.example/source", "Source", 0, 6),),
            ),
        ),
        TokenUsage(1, 2),
    )
    with caplog.at_level("INFO"):
        wire = map_response(protocol, output, request_id="request", route_key="route")
    assert "Answer" in json.dumps(wire)
    if protocol == OutputProtocol.RESPONSES:
        assert wire["output"][0]["content"][0]["annotations"] == [
            {
                "type": "url_citation",
                "url": "https://secret.example/source",
                "title": "Source",
                "start_index": 0,
                "end_index": 6,
            }
        ]
    else:
        assert "unsupported_citation" in caplog.text
        assert "secret" not in caplog.text + json.dumps(wire)


def test_streamed_citations_use_shared_content_and_runtime_annotation_events() -> None:
    citation = UrlCitation("https://example.test/source", "Source", 0, 6)

    async def scenario() -> str:
        async def producer() -> AsyncIterator[AgentStreamEvent]:
            yield ContentStart("answer", TextContent("", (citation,)))
            yield TextDelta("answer", "Answer")
            yield ContentEnd("answer")
            yield TerminalEvent()

        return "".join(
            [
                frame
                async for frame in StreamProcessor().stream(
                    producer(), ProjectionContext(OutputProtocol.RESPONSES, "request")
                )
            ]
        )

    wire = asyncio.run(scenario())
    events = [
        json.loads(line[6:]) for line in wire.splitlines() if line.startswith("data: {")
    ]
    added = [
        event
        for event in events
        if event["type"] == "response.output_text.annotation.added"
    ]
    assert len(added) == 1
    assert added[0]["annotation"]["url"] == citation.url
    assert events[-1]["response"]["output"][0]["content"][0]["annotations"] == [
        added[0]["annotation"]
    ]
    assert "mcp_call" not in wire


@pytest.mark.parametrize(
    "citation",
    [
        UrlCitation("relative", "Source", 0, 6),
        UrlCitation("https://example.test", "Source", -1, 6),
        UrlCitation("https://example.test", "Source", 6, 0),
        UrlCitation("https://example.test", "Source", 0, 7),
    ],
)
def test_invalid_final_citations_are_not_hidden_by_protocol_filter(
    citation: UrlCitation,
) -> None:
    with pytest.raises(OutputValidationError):
        OutputNormalizer().normalize(AgentOutput((TextContent("Answer", (citation,)),)))
