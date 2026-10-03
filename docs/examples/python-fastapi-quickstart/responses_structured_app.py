"""Runnable example for structured Responses output and typed SSE events."""

from __future__ import annotations

import json
import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any, Protocol

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


class DemoScenario(StrEnum):
    DEFAULT = "default"
    RAG = "rag"
    CONTENT_COLLECTION = "content_collection"
    MCP_TOOL = "mcp_tool"


_SCENARIO_TRIGGERS = (
    ("test:rag", DemoScenario.RAG),
    ("test:content", DemoScenario.CONTENT_COLLECTION),
    ("test:mcp", DemoScenario.MCP_TOOL),
)


class EventFactory(Protocol):
    def __call__(
        self,
        event_type: OpenAIResponsesStreamEventType,
        **payload: Any,
    ) -> OpenAIResponsesStreamEvent: ...


async def structured_agent(
    payload: dict[str, Any],
) -> dict[str, Any] | AsyncIterator[OpenAIResponsesStreamEvent]:
    """Return a keyword-selected Responses scenario without an LLM dependency."""
    scenario = _select_scenario(payload.get("input"))
    if payload["stream"]:
        return _stream_response(scenario)

    return {
        "request_id": payload["request_id"],
        "status": "success",
        "output": _scenario_output(scenario),
    }


def _select_scenario(input_value: Any) -> DemoScenario:
    request_text = _input_text(input_value).casefold()
    for trigger, scenario in _SCENARIO_TRIGGERS:
        if trigger in request_text:
            return scenario
    return DemoScenario.DEFAULT


def _input_text(value: Any) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        return " ".join(part for item in value if (part := _input_text(item)))
    if isinstance(value, dict):
        text = value.get("text")
        if isinstance(text, str):
            return text
        return " ".join(
            part
            for key in ("content", "input", "output")
            if (part := _input_text(value.get(key)))
        )
    return ""


def _scenario_output(scenario: DemoScenario) -> list[dict[str, Any]]:
    if scenario is DemoScenario.RAG:
        text = (
            "La politique conserve les journaux pendant 30 jours [1]. "
            "La suppression automatique s'applique ensuite à toutes les copies [2]."
        )
        annotations = [
            _url_citation(text, "[1]", "Politique de conservation", "https://docs.example.test/retention"),
            _url_citation(text, "[2]", "Guide de suppression", "https://docs.example.test/deletion"),
        ]
        return [_message([_output_text_part(text, annotations)])]

    if scenario is DemoScenario.CONTENT_COLLECTION:
        return [
            _message(
                [
                    _output_text_part("Résumé de la recherche.\n"),
                    _output_text_part("Le premier passage confirme le délai de conservation [1].", [
                        _url_citation(
                            "Le premier passage confirme le délai de conservation [1].",
                            "[1]",
                            "Politique de conservation",
                            "https://docs.example.test/retention",
                        )
                    ]),
                    _output_text_part("Le second précise la procédure de suppression [2].", [
                        _url_citation(
                            "Le second précise la procédure de suppression [2].",
                            "[2]",
                            "Guide de suppression",
                            "https://docs.example.test/deletion",
                        )
                    ]),
                ]
            )
        ]

    if scenario is DemoScenario.MCP_TOOL:
        tool_output = {
            "content": [
                {
                    "type": "text",
                    "text": "La politique conserve les journaux pendant 30 jours.",
                }
            ],
            "isError": False,
        }
        return [
            {
                "id": f"mcp_{uuid.uuid4().hex}",
                "type": "mcp_call",
                "server_label": "knowledge-base",
                "name": "search_retention_policy",
                "arguments": json.dumps({"query": "journal retention"}),
                "output": json.dumps(tool_output, ensure_ascii=False),
                "status": "completed",
            },
            _message(
                [
                    _output_text_part(
                        "La base documentaire indique une durée de conservation de 30 jours."
                    )
                ]
            ),
        ]

    return [
        _message([_output_text_part("The request has been received.")]),
        {
            "id": f"fc_{uuid.uuid4().hex}",
            "type": "function_call",
            "call_id": f"call_{uuid.uuid4().hex}",
            "name": "record_request",
            "arguments": '{"received":true}',
            "status": "completed",
        },
    ]


def _message(content: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "id": f"msg_{uuid.uuid4().hex}",
        "type": "message",
        "role": "assistant",
        "status": "completed",
        "content": content,
    }


def _output_text_part(text: str, annotations: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    return {"type": "output_text", "text": text, "annotations": annotations or []}


def _url_citation(text: str, marker: str, title: str, url: str) -> dict[str, Any]:
    start_index = text.index(marker)
    return {
        "type": "url_citation",
        "start_index": start_index,
        "end_index": start_index + len(marker),
        "title": title,
        "url": url,
    }


def _stream_response(scenario: DemoScenario) -> AsyncIterator[OpenAIResponsesStreamEvent]:
    response_id = f"resp_{uuid.uuid4().hex}"
    created_at = int(datetime.now(UTC).timestamp())
    response = _response(response_id, created_at, "in_progress", [])
    output = _scenario_output(scenario)

    async def events() -> AsyncIterator[OpenAIResponsesStreamEvent]:
        sequence_number = 0

        def make_event(
            event_type: OpenAIResponsesStreamEventType,
            **payload: Any,
        ) -> OpenAIResponsesStreamEvent:
            nonlocal sequence_number
            event = _event(event_type, sequence_number, **payload)
            sequence_number += 1
            return event

        yield make_event(OpenAIResponsesStreamEventType.CREATED, response=response)
        yield make_event(OpenAIResponsesStreamEventType.IN_PROGRESS, response=response)

        for output_index, item in enumerate(output):
            if item["type"] == "mcp_call":
                async for event in _stream_mcp_call(item, output_index, make_event):
                    yield event
                continue

            if item["type"] == "function_call":
                async for event in _stream_function_call(item, output_index, make_event):
                    yield event
                continue

            async for event in _stream_message(item, output_index, make_event):
                yield event

        yield _event(
            OpenAIResponsesStreamEventType.COMPLETED,
            sequence_number,
            response=_response(response_id, created_at, "completed", output),
        )

    return events()


async def _stream_message(
    item: dict[str, Any],
    output_index: int,
    make_event: EventFactory,
) -> AsyncIterator[OpenAIResponsesStreamEvent]:
    item_id = item["id"]
    in_progress = {**item, "status": "in_progress", "content": []}
    yield make_event(OpenAIResponsesStreamEventType.OUTPUT_ITEM_ADDED, output_index=output_index, item=in_progress)

    for content_index, part in enumerate(item["content"]):
        item_part = {**part, "text": "", "annotations": []}
        yield make_event(
            OpenAIResponsesStreamEventType.CONTENT_PART_ADDED,
            output_index=output_index,
            content_index=content_index,
            item_id=item_id,
            part=item_part,
        )
        text = part["text"]
        yield make_event(
            OpenAIResponsesStreamEventType.OUTPUT_TEXT_DELTA,
            output_index=output_index,
            content_index=content_index,
            item_id=item_id,
            delta=text,
            logprobs=[],
        )
        for annotation_index, annotation in enumerate(part["annotations"]):
            yield make_event(
                OpenAIResponsesStreamEventType.OUTPUT_TEXT_ANNOTATION_ADDED,
                output_index=output_index,
                content_index=content_index,
                item_id=item_id,
                annotation_index=annotation_index,
                annotation=annotation,
            )
        yield make_event(
            OpenAIResponsesStreamEventType.OUTPUT_TEXT_DONE,
            output_index=output_index,
            content_index=content_index,
            item_id=item_id,
            text=text,
            logprobs=[],
        )
        yield make_event(
            OpenAIResponsesStreamEventType.CONTENT_PART_DONE,
            output_index=output_index,
            content_index=content_index,
            item_id=item_id,
            part=part,
        )

    yield make_event(OpenAIResponsesStreamEventType.OUTPUT_ITEM_DONE, output_index=output_index, item=item)


async def _stream_function_call(
    item: dict[str, Any],
    output_index: int,
    make_event: EventFactory,
) -> AsyncIterator[OpenAIResponsesStreamEvent]:
    item_id = item["id"]
    in_progress = {**item, "arguments": "", "status": "in_progress"}
    yield make_event(OpenAIResponsesStreamEventType.OUTPUT_ITEM_ADDED, output_index=output_index, item=in_progress)
    yield make_event(
        OpenAIResponsesStreamEventType.FUNCTION_CALL_ARGUMENTS_DELTA,
        item_id=item_id,
        output_index=output_index,
        delta=item["arguments"],
    )
    yield make_event(
        OpenAIResponsesStreamEventType.FUNCTION_CALL_ARGUMENTS_DONE,
        item_id=item_id,
        output_index=output_index,
        arguments=item["arguments"],
    )
    yield make_event(OpenAIResponsesStreamEventType.OUTPUT_ITEM_DONE, output_index=output_index, item=item)


async def _stream_mcp_call(
    item: dict[str, Any],
    output_index: int,
    make_event: EventFactory,
) -> AsyncIterator[OpenAIResponsesStreamEvent]:
    item_id = item["id"]
    in_progress = {key: item[key] for key in ("id", "type", "server_label", "name")}
    in_progress.update({"arguments": "", "status": "in_progress"})
    yield make_event(OpenAIResponsesStreamEventType.OUTPUT_ITEM_ADDED, output_index=output_index, item=in_progress)
    yield make_event(OpenAIResponsesStreamEventType.MCP_CALL_IN_PROGRESS, item_id=item_id, output_index=output_index)
    yield make_event(
        OpenAIResponsesStreamEventType.MCP_CALL_ARGUMENTS_DELTA,
        item_id=item_id,
        output_index=output_index,
        delta=item["arguments"],
    )
    yield make_event(
        OpenAIResponsesStreamEventType.MCP_CALL_ARGUMENTS_DONE,
        item_id=item_id,
        output_index=output_index,
        arguments=item["arguments"],
    )
    yield make_event(OpenAIResponsesStreamEventType.MCP_CALL_COMPLETED, item_id=item_id, output_index=output_index)
    yield make_event(OpenAIResponsesStreamEventType.OUTPUT_ITEM_DONE, output_index=output_index, item=item)


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
