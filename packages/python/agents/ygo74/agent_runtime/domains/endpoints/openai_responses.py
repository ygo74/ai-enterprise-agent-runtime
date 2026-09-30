"""Typed request boundary for the OpenAI Responses create operation."""

import json
from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import StrEnum

from ygo74.agent_runtime.domains.contracts.json_value import JsonValue

_RUNTIME_FIELDS = frozenset(
    {
        "auth_context",
        "endpoint_type",
        "input",
        "metadata",
        "model",
        "provider_options",
        "request_id",
        "route_key",
        "stream",
    }
)


@dataclass(slots=True, frozen=True)
class OpenAIResponsesCreateRequest:
    """The Responses request's raw JSON input and unnormalized provider options."""

    input: JsonValue
    provider_options: dict[str, JsonValue]

    @classmethod
    def from_payload(cls, payload: Mapping[str, JsonValue]) -> "OpenAIResponsesCreateRequest":
        """Keep input intact and retain request options not represented by exchange fields."""
        supplied_options = payload.get("provider_options")
        if isinstance(supplied_options, dict):
            options = dict(supplied_options)
        else:
            options = {key: value for key, value in payload.items() if key not in _RUNTIME_FIELDS}

        return cls(input=payload.get("input"), provider_options=options)


class OpenAIResponsesStatus(StrEnum):
    COMPLETED = "completed"
    FAILED = "failed"
    IN_PROGRESS = "in_progress"
    CANCELLED = "cancelled"
    QUEUED = "queued"
    INCOMPLETE = "incomplete"


_RESPONSE_FIELDS = frozenset(
    {
        "access_programs",
        "background",
        "completed_at",
        "conversation",
        "created_at",
        "error",
        "id",
        "incomplete_details",
        "instructions",
        "max_output_tokens",
        "max_tool_calls",
        "metadata",
        "model",
        "moderation",
        "parallel_tool_calls",
        "previous_response_id",
        "prompt",
        "prompt_cache_diagnostics",
        "prompt_cache_key",
        "prompt_cache_options",
        "prompt_cache_retention",
        "reasoning",
        "safety_identifier",
        "service_tier",
        "status",
        "temperature",
        "text",
        "tool_choice",
        "tools",
        "top_logprobs",
        "top_p",
        "truncation",
        "usage",
        "user",
    }
)


@dataclass(slots=True, frozen=True)
class OpenAIResponsesResult:
    """Typed wrapper for the output items and response fields returned by a handler."""

    output: list[JsonValue]
    fields: dict[str, JsonValue] = field(default_factory=dict)

    @classmethod
    def from_handler_output(cls, output: JsonValue) -> "OpenAIResponsesResult":
        if isinstance(output, cls):
            return output

        if isinstance(output, list) and _is_output_items(output):
            return cls(output=output)

        if isinstance(output, dict):
            supplied_items = output.get("output")
            if isinstance(supplied_items, list):
                return cls(
                    output=supplied_items,
                    fields={key: value for key, value in output.items() if key in _RESPONSE_FIELDS},
                )

            if output.get("object") == "response" and isinstance(output.get("output"), list):
                return cls(
                    output=output["output"],
                    fields={key: value for key, value in output.items() if key in _RESPONSE_FIELDS},
                )

        return cls(
            output=[
                {
                    "id": "",
                    "type": "message",
                    "role": "assistant",
                    "status": "completed",
                    "content": [
                        {
                            "type": "output_text",
                            "text": _output_text(output),
                            "annotations": [],
                        }
                    ],
                }
            ]
        )


def _output_text(output: JsonValue) -> str:
    if isinstance(output, str):
        return output
    if isinstance(output, dict):
        content = output.get("content")
        if isinstance(content, str):
            return content
        text = output.get("text")
        if isinstance(text, str):
            return text
    if output is None:
        return ""
    if isinstance(output, (dict, list)):
        return json.dumps(output, ensure_ascii=True)
    return str(output)


def _is_output_items(value: list[JsonValue]) -> bool:
    return all(isinstance(item, dict) and isinstance(item.get("type"), str) for item in value)
