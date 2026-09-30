"""Runnable example for structured Responses output and typed SSE events."""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import Any

from fastapi import FastAPI
from ygo74.agent_runtime.domains.auth.authentication_policy import AuthenticationPolicy
from ygo74.agent_runtime.domains.contracts.stream_events import (
    OpenAIResponsesStreamEvent,
    OpenAIResponsesStreamEventType,
)
from ygo74.agent_runtime.domains.discovery.agent_descriptor import (
    AgentCapabilitySet,
    AgentDescriptor,
)
from ygo74.agent_runtime.domains.endpoints.hosting_factory import (
    EndpointSurface,
    HostingFactory,
)

app = FastAPI(title="Structured OpenAI Responses Example")


async def structured_agent(
    payload: dict[str, Any],
) -> dict[str, Any] | AsyncIterator[OpenAIResponsesStreamEvent]:
    """Return structured output items or a typed Responses event stream."""
    if payload["stream"]:
        return _stream_response()

    return {
        "request_id": payload["request_id"],
        "status": "success",
        "output": [
            {
                "id": f"msg_{uuid.uuid4().hex}",
                "type": "message",
                "role": "assistant",
                "status": "completed",
                "content": [
                    {
                        "type": "output_text",
                        "text": "The request has been received.",
                        "annotations": [],
                    }
                ],
            },
            {
                "id": f"fc_{uuid.uuid4().hex}",
                "type": "function_call",
                "call_id": f"call_{uuid.uuid4().hex}",
                "name": "record_request",
                "arguments": '{"received":true}',
                "status": "completed",
            },
        ],
    }


def _stream_response() -> AsyncIterator[OpenAIResponsesStreamEvent]:
    response_id = f"resp_{uuid.uuid4().hex}"
    item_id = f"msg_{uuid.uuid4().hex}"
    created_at = int(datetime.now(UTC).timestamp())
    response = _response(response_id, created_at, "in_progress", [])

    async def events() -> AsyncIterator[OpenAIResponsesStreamEvent]:
        yield _event(OpenAIResponsesStreamEventType.CREATED, 0, response=response)
        yield _event(OpenAIResponsesStreamEventType.IN_PROGRESS, 1, response=response)
        yield _event(
            OpenAIResponsesStreamEventType.OUTPUT_ITEM_ADDED,
            2,
            output_index=0,
            item={"id": item_id, "type": "message", "role": "assistant", "status": "in_progress", "content": []},
        )
        part = {"type": "output_text", "text": "", "annotations": []}
        yield _event(
            OpenAIResponsesStreamEventType.CONTENT_PART_ADDED,
            3,
            output_index=0,
            content_index=0,
            item_id=item_id,
            part=part,
        )
        text = "Structured streaming works."
        yield _event(
            OpenAIResponsesStreamEventType.OUTPUT_TEXT_DELTA,
            4,
            output_index=0,
            content_index=0,
            item_id=item_id,
            delta=text,
            logprobs=[],
        )
        part = {"type": "output_text", "text": text, "annotations": []}
        message = {
            "id": item_id,
            "type": "message",
            "role": "assistant",
            "status": "completed",
            "content": [part],
        }
        yield _event(
            OpenAIResponsesStreamEventType.OUTPUT_TEXT_DONE,
            5,
            output_index=0,
            content_index=0,
            item_id=item_id,
            text=text,
            logprobs=[],
        )
        yield _event(
            OpenAIResponsesStreamEventType.CONTENT_PART_DONE,
            6,
            output_index=0,
            content_index=0,
            item_id=item_id,
            part=part,
        )
        yield _event(OpenAIResponsesStreamEventType.OUTPUT_ITEM_DONE, 7, output_index=0, item=message)
        yield _event(
            OpenAIResponsesStreamEventType.COMPLETED,
            8,
            response=_response(response_id, created_at, "completed", [message]),
        )

    return events()


def _event(
    event_type: OpenAIResponsesStreamEventType,
    sequence_number: int,
    **payload: Any,
) -> OpenAIResponsesStreamEvent:
    return OpenAIResponsesStreamEvent(
        event_type=event_type,
        payload={"type": event_type.value, "sequence_number": sequence_number, **payload},
    )


def _response(response_id: str, created_at: int, status: str, output: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "id": response_id,
        "object": "response",
        "created_at": created_at,
        "model": "structured-agent",
        "status": status,
        "output": output,
        "parallel_tool_calls": True,
        "tool_choice": "auto",
        "tools": [],
    }


descriptor = AgentDescriptor(
    agent_id="structured-agent",
    route_key="structured-agent",
    display_name="Structured Agent",
    description="Returns a structured Responses output and typed SSE events.",
    version="1.0.0",
    owner="quickstart",
    created_at_utc=datetime.now(UTC),
    capabilities=AgentCapabilitySet(streaming=True),
)

(
    HostingFactory(app)
    .add_agent(structured_agent, descriptor)
    .add_ai_endpoints(EndpointSurface.OPENAI_RESPONSES)
    .add_security(AuthenticationPolicy.anonymous())
    .register()
)
