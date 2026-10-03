import asyncio
import json

import httpx
from fastapi import FastAPI
from ygo74.agent_runtime.domains.contracts.stream_events import (
    OpenAIResponsesStreamEvent,
    OpenAIResponsesStreamEventType,
)
from ygo74.agent_runtime.domains.endpoints.adapters import normalize_request
from ygo74.agent_runtime.domains.endpoints.fastapi_endpoints import add_ai_endpoints
from ygo74.agent_runtime.domains.mapping.response_mapper import map_response


def test_responses_request_keeps_input_and_all_provider_options() -> None:
    request_input = [
        {"role": "user", "content": [{"type": "input_text", "text": "Describe this"},
                                       {"type": "input_image", "image_url": "https://example.test/image.png"}]}
    ]
    options = {
        "instructions": "Be concise",
        "tools": [{"type": "function", "name": "lookup", "parameters": {"type": "object"}}],
        "tool_choice": "auto",
        "previous_response_id": "resp_previous",
        "stream_options": {"include_obfuscation": False},
        "future_option": {"nested": [1, 2]},
    }
    payload = {
        "request_id": "req-1",
        "route_key": "support",
        "endpoint_type": "openai.responses",
        "model": "support-agent",
        "input": request_input,
        "stream": True,
        "metadata": {"tenant": "alpha"},
        **options,
    }

    request = normalize_request("openai.responses", payload)

    assert request.input == request_input
    assert request.provider_options == options
    assert request.metadata == {"tenant": "alpha", "model": "support-agent"}
    assert request.stream is True


def test_responses_mapper_preserves_structured_output_and_response_fields() -> None:
    output = [
        {
            "id": "msg_1",
            "type": "message",
            "role": "assistant",
            "status": "completed",
            "content": [{"type": "output_text", "text": "Hello", "annotations": []}],
        },
        {
            "id": "fc_1",
            "type": "function_call",
            "call_id": "call_1",
            "name": "lookup",
            "arguments": "{}",
            "status": "completed",
        },
    ]
    provider_options = {
        "parallel_tool_calls": False,
        "tool_choice": "required",
        "tools": [{"type": "function", "name": "lookup", "parameters": {"type": "object"}}],
        "instructions": "Answer the user",
    }

    response = map_response(
        "openai.responses",
        {"request_id": "req-2", "status": "success", "output": output},
        model="support-agent",
        provider_options=provider_options,
    )

    assert response["object"] == "response"
    assert response["status"] == "completed"
    assert response["output"] == output
    assert response["output_text"] == "Hello"
    assert response["parallel_tool_calls"] is False
    assert response["tool_choice"] == "required"
    assert response["tools"] == provider_options["tools"]
    assert response["instructions"] == "Answer the user"


def test_responses_route_forwards_all_provider_options_to_handler() -> None:
    captured: dict[str, object] = {}

    async def entrypoint(payload: dict[str, object]) -> dict[str, object]:
        captured.update(payload)
        return {"status": "success", "output": "ok"}

    app = FastAPI()
    add_ai_endpoints(app, entrypoint, default_route_key="support", enable_openai_chat_completions=False)
    payload = {
        "model": "support-agent",
        "input": [{"role": "user", "content": [{"type": "input_text", "text": "hi"}]}],
        "metadata": {"tenant": "alpha"},
        "instructions": "Use the tenant context",
        "tools": [{"type": "function", "name": "lookup", "parameters": {"type": "object"}}],
        "previous_response_id": "resp_previous",
    }

    response = asyncio.run(_post_json(app, payload))

    assert response.status_code == 200
    assert captured["input"] == payload["input"]
    assert captured["metadata"]["tenant"] == "alpha"
    assert captured["metadata"]["model"] == "support-agent"
    assert captured["metadata"]["headers"] == {}
    assert captured["provider_options"] == {
        "instructions": "Use the tenant context",
        "tools": payload["tools"],
        "previous_response_id": "resp_previous",
    }
    response_body = response.json()
    assert response_body["instructions"] == "Use the tenant context"
    assert response_body["tools"] == payload["tools"]
    assert response_body["previous_response_id"] == "resp_previous"
    assert response_body["metadata"] == payload["metadata"]


def test_responses_text_stream_emits_full_sse_lifecycle() -> None:
    async def entrypoint(payload: dict[str, object]) -> object:
        async def chunks():
            yield "hello "
            yield "world"

        return chunks()

    app = FastAPI()
    add_ai_endpoints(app, entrypoint, default_route_key="support", enable_openai_chat_completions=False)
    response = asyncio.run(_post_json(app, {"model": "support-agent", "input": "hi", "stream": True}))

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
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
    completed = events[-1]["response"]
    assert completed["output"][0]["content"][0]["text"] == "hello world"
    assert "[DONE]" not in response.text


def test_responses_route_forwards_typed_events_without_flattening() -> None:
    event_payload = {
        "type": "response.function_call_arguments.delta",
        "sequence_number": 0,
        "item_id": "fc_1",
        "output_index": 0,
        "delta": "{\"city\":",
    }
    response_in_progress = {
        "id": "resp_1",
        "created_at": 1700000000,
        "model": "support-agent",
        "object": "response",
        "status": "in_progress",
        "output": [],
        "parallel_tool_calls": True,
        "tool_choice": "auto",
        "tools": [],
    }
    response_completed = {**response_in_progress, "status": "completed"}

    async def entrypoint(payload: dict[str, object]) -> object:
        async def events():
            yield OpenAIResponsesStreamEvent(
                OpenAIResponsesStreamEventType.CREATED,
                {"type": "response.created", "sequence_number": 0, "response": response_in_progress},
            )
            yield OpenAIResponsesStreamEvent(
                OpenAIResponsesStreamEventType.IN_PROGRESS,
                {"type": "response.in_progress", "sequence_number": 1, "response": response_in_progress},
            )
            yield OpenAIResponsesStreamEvent(
                OpenAIResponsesStreamEventType.FUNCTION_CALL_ARGUMENTS_DELTA,
                {**event_payload, "sequence_number": 2},
            )
            yield OpenAIResponsesStreamEvent(
                OpenAIResponsesStreamEventType.COMPLETED,
                {
                    "type": "response.completed",
                    "sequence_number": 3,
                    "response": response_completed,
                },
            )

        return events()

    app = FastAPI()
    add_ai_endpoints(app, entrypoint, default_route_key="support", enable_openai_chat_completions=False)
    response = asyncio.run(_post_json(app, {"model": "support-agent", "input": "hi", "stream": True}))

    events = _parse_sse_events(response.text)
    assert events == [
        {"type": "response.created", "sequence_number": 0, "response": response_in_progress},
        {"type": "response.in_progress", "sequence_number": 1, "response": response_in_progress},
        {**event_payload, "sequence_number": 2},
        {"type": "response.completed", "sequence_number": 3, "response": response_completed},
    ]


def test_responses_stream_failure_ends_with_failed_event_not_success() -> None:
    def entrypoint(payload: dict[str, object]) -> object:
        async def chunks():
            yield "partial"
            raise RuntimeError("stream broke")

        return chunks()

    app = FastAPI()
    add_ai_endpoints(app, entrypoint, default_route_key="support", enable_openai_chat_completions=False)
    response = asyncio.run(_post_json(app, {"model": "support-agent", "input": "hi", "stream": True}))

    events = _parse_sse_events(response.text)
    assert events[-1]["type"] == "response.failed"
    assert events[-1]["response"]["error"]["message"] == "stream broke"
    assert all(event["type"] != "response.completed" for event in events)
    assert "[DONE]" not in response.text


def test_responses_errors_use_openai_error_envelope() -> None:
    response = map_response(
        "openai.responses",
        {
            "request_id": "req-error",
            "status": "error",
            "error": {
                "code": "agent_access_denied",
                "category": "authorization",
                "message": "Access denied",
            },
        },
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
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        return await client.post("/v1/responses", json=payload)


def _parse_sse_events(value: str) -> list[dict[str, object]]:
    events: list[dict[str, object]] = []
    for frame in value.strip().split("\n\n"):
        data_lines = [line.removeprefix("data: ") for line in frame.splitlines() if line.startswith("data: ")]
        if data_lines:
            events.append(json.loads("\n".join(data_lines)))
    return events
