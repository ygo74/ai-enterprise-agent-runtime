from __future__ import annotations

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
    / "app.py"
)


def _load_example() -> ModuleType:
    spec = importlib.util.spec_from_file_location("quickstart_app", EXAMPLE_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load example module at {EXAMPLE_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_quickstart_streams_responses_text_as_incremental_deltas() -> None:
    example = _load_example()
    response = asyncio.run(_post_stream(example.app, "hello"))

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    events = _parse_sse_events(response.text)
    deltas = [event["delta"] for event in events if event["type"] == "response.output_text.delta"]

    assert deltas == ["Echo: ", "hello"]
    assert events[-1]["type"] == "response.completed"
    assert events[-1]["response"]["output_text"] == "Echo: hello"


async def _post_stream(app: Any, input_text: str) -> httpx.Response:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        return await client.post(
            "/v1/responses",
            json={"model": "echo-agent", "input": input_text, "stream": True},
        )


def _parse_sse_events(value: str) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    for frame in value.strip().split("\n\n"):
        data = next((line.removeprefix("data: ") for line in frame.splitlines() if line.startswith("data: ")), None)
        if data is not None:
            events.append(json.loads(data))
    return events