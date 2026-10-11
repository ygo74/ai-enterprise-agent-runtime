import asyncio
import json
from collections.abc import AsyncIterator

import httpx
from fastapi import FastAPI
from ygo74.agent_runtime.domains.contracts import (
    AgentOutput,
    ContentEnd,
    ContentStart,
    TerminalEvent,
    TextContent,
    TextDelta,
    ToolArgumentsDelta,
    ToolCallContent,
)
from ygo74.agent_runtime.domains.contracts.error_envelope import ErrorEnvelope
from ygo74.agent_runtime.domains.contracts.exchange_models import (
    StandardExchangeResponse,
)
from ygo74.agent_runtime.domains.endpoints.adapters import normalize_request
from ygo74.agent_runtime.domains.endpoints.fastapi_endpoints import add_ai_endpoints
from ygo74.agent_runtime.domains.mapping.response_mapper import map_response


def test_responses_request_keeps_input_and_all_provider_options() -> None:
    request_input = [
        {
            "role": "user",
            "content": [
                {"type": "input_text", "text": "Describe this"},
                {"type": "input_image", "image_url": "https://example.test/image.png"},
            ],
        }
    ]
    options = {
        "instructions": "Be concise",
        "tools": [
            {"type": "function", "name": "lookup", "parameters": {"type": "object"}}
        ],
        "tool_choice": "auto",
        "previous_response_id": "resp_previous",
        "stream_options": {"include_obfuscation": False},
        "future_option": {"nested": [1, 2]},
    }
    request = normalize_request(
        "openai.responses",
        {
            "request_id": "req-1",
            "route_key": "support",
            "model": "support-agent",
            "input": request_input,
            "stream": True,
            "metadata": {"tenant": "alpha"},
            **options,
        },
    )
    assert request.input == request_input
    assert request.provider_options == options
    assert request.metadata == {"tenant": "alpha", "model": "support-agent"}
    assert request.stream is True


def test_responses_mapper_projects_structured_output_and_preserves_options() -> None:
    options = {
        "parallel_tool_calls": False,
        "tool_choice": "required",
        "instructions": "Answer",
        "future_option": [1],
    }
    response = map_response(
        "openai.responses",
        AgentOutput((TextContent("Hello"), ToolCallContent("call_1", "lookup"))),
        model="support-agent",
        provider_options=options,
    )
    assert response["object"] == "response"
    assert response["status"] == "completed"
    assert response["output_text"] == "Hello"
    assert response["output"][1]["type"] == "function_call"
    assert response["output"][1]["arguments"] == "{}"
    for key, value in options.items():
        assert response[key] == value


def test_responses_route_forwards_all_provider_options_to_handler() -> None:
    captured: dict[str, object] = {}

    async def entrypoint(payload: dict[str, object]) -> AgentOutput:
        captured.update(payload)
        return AgentOutput((TextContent("ok"),))

    app = FastAPI()
    add_ai_endpoints(
        app,
        entrypoint,
        default_route_key="support",
        enable_openai_chat_completions=False,
    )
    payload = {
        "model": "support-agent",
        "input": [{"role": "user", "content": [{"type": "input_text", "text": "hi"}]}],
        "metadata": {"tenant": "alpha"},
        "instructions": "Use the tenant context",
        "tools": [
            {"type": "function", "name": "lookup", "parameters": {"type": "object"}}
        ],
        "previous_response_id": "resp_previous",
    }
    response = asyncio.run(_post_json(app, payload))
    assert response.status_code == 200
    assert captured["input"] == payload["input"]
    assert captured["metadata"] == {
        "tenant": "alpha",
        "model": "support-agent",
        "headers": {},
    }
    assert captured["provider_options"] == {
        "instructions": payload["instructions"],
        "tools": payload["tools"],
        "previous_response_id": "resp_previous",
    }
    body = response.json()
    assert body["instructions"] == payload["instructions"]
    assert body["tools"] == payload["tools"]
    assert body["previous_response_id"] == "resp_previous"
    assert body["metadata"] == payload["metadata"]


def test_responses_text_stream_emits_full_sse_lifecycle() -> None:
    async def entrypoint(_: dict[str, object]) -> AsyncIterator[object]:
        yield ContentStart("text", TextContent(""))
        yield TextDelta("text", "hello ")
        yield TextDelta("text", "world")
        yield ContentEnd("text")
        yield TerminalEvent()

    app = FastAPI()
    add_ai_endpoints(
        app,
        entrypoint,
        default_route_key="support",
        enable_openai_chat_completions=False,
    )
    response = asyncio.run(
        _post_json(app, {"model": "support-agent", "input": "hi", "stream": True})
    )
    events = _parse_sse_events(response.text)
    assert [event["type"] for event in events] == [
        "response.created",
        "response.in_progress",
        "response.output_item.added",
        "response.content_part.added",
        "response.output_text.delta",
        "response.output_text.delta",
        "response.output_text.done",
        "response.content_part.done",
        "response.output_item.done",
        "response.completed",
    ]
    assert [event["sequence_number"] for event in events] == list(range(len(events)))
    assert events[-1]["response"]["output"][0]["content"][0]["text"] == "hello world"
    assert "[DONE]" not in response.text


def test_responses_route_projects_tool_argument_fragments_without_parsing_early() -> (
    None
):
    async def entrypoint(_: dict[str, object]) -> AsyncIterator[object]:
        yield ContentStart("tool", ToolCallContent("call_1", "lookup"))
        yield ToolArgumentsDelta("tool", '{"city":')
        yield ToolArgumentsDelta("tool", '"Paris"}')
        yield ContentEnd("tool")
        yield TerminalEvent()

    app = FastAPI()
    add_ai_endpoints(
        app,
        entrypoint,
        default_route_key="support",
        enable_openai_chat_completions=False,
    )
    response = asyncio.run(
        _post_json(app, {"model": "support-agent", "input": "hi", "stream": True})
    )
    events = _parse_sse_events(response.text)
    deltas = [
        event
        for event in events
        if event["type"] == "response.function_call_arguments.delta"
    ]
    assert [event["delta"] for event in deltas] == ['{"city":', '"Paris"}']
    assert deltas[0]["item_id"] == deltas[1]["item_id"]
    assert events[-1]["response"]["output"][0]["arguments"] == '{"city": "Paris"}'
    assert events[-1]["response"]["output"][0]["call_id"] == "call_1"


def test_responses_stream_failure_ends_with_failed_event_not_success() -> None:
    async def entrypoint(_: dict[str, object]) -> AsyncIterator[object]:
        yield ContentStart("text", TextContent("partial"))
        raise RuntimeError("stream broke")

    app = FastAPI()
    add_ai_endpoints(
        app,
        entrypoint,
        default_route_key="support",
        enable_openai_chat_completions=False,
    )
    response = asyncio.run(
        _post_json(app, {"model": "support-agent", "input": "hi", "stream": True})
    )
    events = _parse_sse_events(response.text)
    assert events[-1]["type"] == "response.failed"
    assert events[-1]["response"]["error"]["code"] == "agent_execution_error"
    assert all(event["type"] != "response.completed" for event in events)
    assert "[DONE]" not in response.text


def test_responses_errors_use_openai_error_envelope() -> None:
    response = map_response(
        "openai.responses",
        StandardExchangeResponse(
            "req-error",
            "error",
            error=ErrorEnvelope(
                "agent_access_denied", "authorization", "Access denied"
            ),
        ),
    )
    assert response == {
        "error": {
            "message": "Access denied",
            "type": "permission_error",
            "param": None,
            "code": "agent_access_denied",
        }
    }


async def _post_json(app: FastAPI, payload: dict[str, object]) -> httpx.Response:
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        return await client.post("/v1/responses", json=payload)


def _parse_sse_events(value: str) -> list[dict[str, object]]:
    return [
        json.loads(line[6:])
        for line in value.splitlines()
        if line.startswith("data: {")
    ]
