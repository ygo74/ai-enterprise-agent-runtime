from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient


def _example_app() -> FastAPI:
    spec = importlib.util.spec_from_file_location("agentframework_offline_example", Path(__file__).with_name("app.py"))
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    app: FastAPI = module.create_app()
    return app


@pytest.mark.parametrize(("path", "body"), [
    ("/v1/chat/completions", {"model": "agentframework-echo", "messages": [{"role": "user", "content": "hello"}]}),
    ("/v1/responses", {"model": "agentframework-echo", "input": "hello"}),
    ("/v1/messages", {
        "model": "agentframework-echo", "max_tokens": 32, "messages": [{"role": "user", "content": "hello"}],
    }),
])
@pytest.mark.parametrize("stream", [False, True])
def test_agentframework_offline_example_serves_all_surfaces(
    path: str, body: dict[str, object], stream: bool,
) -> None:
    with TestClient(_example_app()) as client:
        response = client.post(path, json={**body, "stream": stream})
    assert response.status_code == 200, response.text
    if stream:
        assert response.headers["content-type"].startswith("text/event-stream")
        assert "Echo: " in response.text and "hello" in response.text
        if path == "/v1/messages":
            events = [json.loads(line.removeprefix("data: "))
                      for line in response.text.splitlines() if line.startswith("data: ")]
            start = next(event for event in events if event["type"] == "message_start")
            assert start["message"]["usage"] == {"input_tokens": 0, "output_tokens": 0}
            assert events.index(start) < next(index for index, event in enumerate(events)
                                             if event["type"] == "content_block_start")
    else:
        assert "Echo: hello" in response.text
        if path == "/v1/messages":
            assert response.json()["usage"] == {"input_tokens": 0, "output_tokens": 0}


def test_agentframework_offline_example_discovery() -> None:
    with TestClient(_example_app()) as client:
        response = client.get("/v1/models")
    assert response.status_code == 200
    assert response.json()["data"][0]["id"] == "agentframework-echo"
