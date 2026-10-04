import asyncio
import importlib.util
import json
from pathlib import Path
from types import ModuleType
from typing import Any

import httpx
import pytest
from ygo74.agent_runtime.domains.contracts.agent_output import (
    AgentOutput,
    ImageContent,
    Notification,
    TextContent,
    ToolCallContent,
    ToolExecution,
    ToolResultContent,
)
from ygo74.agent_runtime.domains.contracts.media_content import EncodedMedia
from ygo74.agent_runtime.domains.contracts.stream_events import (
    ContentEnd,
    ContentEvent,
    ContentStart,
    TerminalEvent,
    ToolArgumentsDelta,
)
from ygo74.agent_runtime.domains.discovery.agent_descriptor import Modality

EXAMPLE_PATH = (
    Path(__file__).resolve().parents[3]
    / "docs"
    / "examples"
    / "python-fastapi-quickstart"
    / "responses_structured_app.py"
)


def _load_example() -> ModuleType:
    spec = importlib.util.spec_from_file_location("responses_structured_app", EXAMPLE_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_tools_are_neutral_internal_observations_not_fabricated_mcp_calls() -> None:
    example = _load_example()
    result = asyncio.run(example.structured_agent({"input": "test:tools"}))
    assert isinstance(result, AgentOutput)
    call, tool_result, text = result.contents
    assert isinstance(call, ToolCallContent)
    assert isinstance(tool_result, ToolResultContent)
    assert call.call_id == tool_result.call_id
    assert call.execution is ToolExecution.INTERNAL
    assert call.arguments == {"query": "journal retention"}
    assert tool_result.result == {"retention_days": 30}
    assert isinstance(text, TextContent)


def test_latest_user_message_selects_scenario_instead_of_history() -> None:
    example = _load_example()
    result = asyncio.run(example.structured_agent({"input": [
        {"role": "user", "content": [{"type": "input_text", "text": "test:rag"}]},
        {"role": "assistant", "content": [{"type": "output_text", "text": "RAG response"}]},
        {"role": "user", "content": [{"type": "input_text", "text": "test:tools"}]},
    ]}))
    assert isinstance(result.contents[0], ToolCallContent)


def test_content_scenario_preserves_separate_text_contents() -> None:
    example = _load_example()
    result = asyncio.run(example.structured_agent({"input": "test:content"}))
    assert len(result.contents) == 3
    assert all(isinstance(content, TextContent) for content in result.contents)


def test_notification_stream_does_not_contaminate_final_result() -> None:
    example = _load_example()

    async def collect() -> list[Any]:
        stream = await example.structured_agent({"input": "test:notifications", "stream": True})
        return [event async for event in stream]

    events = asyncio.run(collect())
    notices = [event.content for event in events if isinstance(event, ContentEvent)
               and isinstance(event.content, Notification)]
    assert [notice.text for notice in notices] == ["Checking the local fixture."]
    assert isinstance(events[-1], TerminalEvent)
    result = asyncio.run(example.structured_agent({"input": "test:notifications"}))
    assert not any(isinstance(content, Notification) for content in result.contents)


def test_tool_stream_preserves_fragment_lifecycle_and_result_correlation() -> None:
    example = _load_example()

    async def collect() -> list[Any]:
        stream = await example.structured_agent({"input": "test:tools", "stream": True})
        return [event async for event in stream]

    events = asyncio.run(collect())
    start = next(event for event in events if isinstance(event, ContentStart)
                 and isinstance(event.content, ToolCallContent))
    fragments = [event.delta for event in events if isinstance(event, ToolArgumentsDelta)]
    assert fragments == ['{"query":', '"journal retention"}']
    assert json.loads("".join(fragments)) == {"query": "journal retention"}
    assert any(isinstance(event, ContentEnd) and event.content_id == start.content_id for event in events)
    result = next(event.content for event in events if isinstance(event, ContentEvent)
                  and isinstance(event.content, ToolResultContent))
    assert result.call_id == start.content.call_id
    assert isinstance(events[-1], TerminalEvent)


def test_media_demo_is_typed_encoded_content_without_fetching() -> None:
    example = _load_example()
    output = asyncio.run(example.structured_agent({"input": "test:media"}))
    image = output.contents[1]
    assert isinstance(image, ImageContent)
    assert isinstance(image.source, EncodedMedia)
    assert image.source.mime_type == "image/png"
    assert image.source.data.startswith("iVBOR")


def test_demo_only_advertises_projected_output_modalities() -> None:
    example = _load_example()
    assert example.descriptor.capabilities.output_modalities == (Modality.TEXT,)
    assert "unsupported image pivot fixture" in example.descriptor.description

    async def discover() -> httpx.Response:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=example.app), base_url="http://test",
        ) as client:
            return await client.get("/v1/models")

    response = asyncio.run(discover())
    assert response.status_code == 200
    assert response.json()["data"][0]["id"] == "structured-agent"


@pytest.mark.parametrize("surface", ["/v1/responses", "/v1/chat/completions"])
@pytest.mark.parametrize("scenario", ["test:tools", "test:media"])
def test_supported_text_remains_when_internal_tools_and_images_are_filtered(
    surface: str, scenario: str,
) -> None:
    example = _load_example()

    async def post() -> httpx.Response:
        body: dict[str, Any] = {"model": "structured-agent", "stream": False}
        if surface == "/v1/responses":
            body["input"] = scenario
        else:
            body["messages"] = [{"role": "user", "content": scenario}]
            body["max_tokens"] = 128
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=example.app), base_url="http://test",
        ) as client:
            return await client.post(surface, json=body)

    response = asyncio.run(post())
    assert response.status_code == 200
    wire = response.text
    assert "function_call" not in wire
    assert "mcp_call" not in wire
    assert "journal retention" not in wire
    assert "iVBOR" not in wire
    assert ("retains journals for 30 days" if scenario == "test:tools" else "one-pixel PNG fixture") in wire


@pytest.mark.parametrize("stream", [False, True])
@pytest.mark.parametrize("scenario", ["test:tools", "test:media"])
def test_anthropic_demo_does_not_invent_missing_token_usage(scenario: str, stream: bool) -> None:
    example = _load_example()

    async def post() -> httpx.Response:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=example.app), base_url="http://test",
        ) as client:
            return await client.post("/v1/messages", json={
                "model": "structured-agent", "max_tokens": 128,
                "messages": [{"role": "user", "content": scenario}], "stream": stream,
            })

    response = asyncio.run(post())
    if not stream:
        assert response.status_code >= 400
    assert "unsupported_output_projection" in response.text
    assert '"message_start"' not in response.text
    assert '"input_tokens"' not in response.text
    assert '"output_tokens"' not in response.text


@pytest.mark.parametrize("scenario", ["ordinary request", "test:content", "test:tools", "test:notifications"])
def test_responses_projection_finishes_with_consistent_sequence(scenario: str) -> None:
    example = _load_example()
    response = asyncio.run(_post_json(example.app, scenario, stream=True))
    assert response.status_code == 200
    events = [
        json.loads(line.removeprefix("data: "))
        for line in response.text.splitlines()
        if line.startswith("data: ") and line != "data: [DONE]"
    ]
    assert events[-1]["type"] == "response.completed"
    assert [event["sequence_number"] for event in events] == list(range(len(events)))
    assert not any("mcp_call" in event["type"] for event in events)


async def _post_json(app: Any, input_value: Any, *, stream: bool = False) -> httpx.Response:
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        return await client.post(
            "/v1/responses",
            json={"model": "structured-agent", "input": input_value, "stream": stream},
        )
