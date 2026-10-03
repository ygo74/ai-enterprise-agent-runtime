import asyncio
import importlib.util
import json
from pathlib import Path
from types import ModuleType
from typing import Any

import httpx

EXAMPLE_PATH = (
    Path(__file__).resolve().parents[3]
    / "docs"
    / "examples"
    / "python-fastapi-quickstart"
    / "responses_structured_app.py"
)


def _load_example() -> ModuleType:
    spec = importlib.util.spec_from_file_location("responses_structured_app", EXAMPLE_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load example module at {EXAMPLE_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_rag_scenario_has_indexed_url_citation_annotations() -> None:
    example = _load_example()
    response = asyncio.run(_post_json(example.app, "test:rag"))
    assert response.status_code == 200

    content = response.json()["output"][0]["content"]
    assert len(content) == 1
    text_part = content[0]
    assert text_part["type"] == "output_text"
    assert len(text_part["annotations"]) == 2
    for index, annotation in enumerate(text_part["annotations"], start=1):
        assert annotation["type"] == "url_citation"
        assert text_part["text"][annotation["start_index"] : annotation["end_index"]] == f"[{index}]"


def test_content_scenario_keeps_separate_output_text_parts() -> None:
    example = _load_example()
    response = asyncio.run(
        _post_json(
            example.app,
            [{"role": "user", "content": [{"type": "input_text", "text": "test:content"}]}],
        )
    )
    assert response.status_code == 200

    content = response.json()["output"][0]["content"]
    assert len(content) == 3
    assert [part["type"] for part in content] == ["output_text", "output_text", "output_text"]
    assert content[1]["annotations"][0]["type"] == "url_citation"
    assert content[2]["annotations"][0]["type"] == "url_citation"


def test_mcp_scenario_returns_call_output_and_assistant_message() -> None:
    example = _load_example()
    response = asyncio.run(_post_json(example.app, "test:mcp"))
    assert response.status_code == 200

    call, message = response.json()["output"]
    assert call["type"] == "mcp_call"
    assert call["status"] == "completed"
    assert json.loads(call["arguments"]) == {"query": "journal retention"}
    assert json.loads(call["output"])["isError"] is False
    assert message["type"] == "message"
    assert message["content"][0]["type"] == "output_text"


def test_streamed_rag_and_mcp_scenarios_include_client_visible_events() -> None:
    example = _load_example()
    rag_events = asyncio.run(_post_and_parse_events(example.app, "test:rag"))
    mcp_events = asyncio.run(_post_and_parse_events(example.app, "test:mcp"))

    annotation_event = next(event for event in rag_events if event["type"] == "response.output_text.annotation.added")
    annotation = annotation_event["annotation"]
    assert annotation["type"] == "url_citation"
    assert annotation_event["annotation_index"] == 0
    assert rag_events[-1]["type"] == "response.completed"
    assert [event["sequence_number"] for event in rag_events] == list(range(len(rag_events)))

    mcp_event_types = [event["type"] for event in mcp_events]
    assert "response.mcp_call.in_progress" in mcp_event_types
    assert "response.mcp_call_arguments.delta" in mcp_event_types
    assert "response.mcp_call_arguments.done" in mcp_event_types
    assert "response.mcp_call.completed" in mcp_event_types
    final_output = mcp_events[-1]["response"]["output"]
    assert final_output[0]["type"] == "mcp_call"
    assert json.loads(final_output[0]["output"])["isError"] is False
    assert [event["sequence_number"] for event in mcp_events] == list(range(len(mcp_events)))


def test_default_stream_preserves_the_function_call_lifecycle() -> None:
    example = _load_example()
    events = asyncio.run(_post_and_parse_events(example.app, "ordinary request"))

    event_types = [event["type"] for event in events]
    assert "response.function_call_arguments.delta" in event_types
    assert "response.function_call_arguments.done" in event_types
    assert events[-1]["type"] == "response.completed"
    assert events[-1]["response"]["output"][1]["type"] == "function_call"


async def _post_and_parse_events(app: Any, input_text: str) -> list[dict[str, Any]]:
    response = await _post_json(app, input_text, stream=True)
    assert response.status_code == 200
    events: list[dict[str, Any]] = []
    for frame in response.text.strip().split("\n\n"):
        data = next((line.removeprefix("data: ") for line in frame.splitlines() if line.startswith("data: ")), None)
        if data is not None:
            events.append(json.loads(data))
    return events


async def _post_json(app: Any, input_value: Any, *, stream: bool = False) -> httpx.Response:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/v1/responses",
            json={"model": "structured-agent", "input": input_value, "stream": stream},
        )
    return response
