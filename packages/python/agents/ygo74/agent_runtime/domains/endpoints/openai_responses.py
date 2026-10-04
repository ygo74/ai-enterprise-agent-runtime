"""Typed request boundary for the OpenAI Responses create operation."""

from collections.abc import Mapping
from dataclasses import dataclass
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
    def from_payload(
        cls, payload: Mapping[str, JsonValue]
    ) -> "OpenAIResponsesCreateRequest":
        """Keep input intact and retain request options not represented by exchange fields."""
        supplied_options = payload.get("provider_options")
        if isinstance(supplied_options, dict):
            options = dict(supplied_options)
        else:
            options = {
                key: value
                for key, value in payload.items()
                if key not in _RUNTIME_FIELDS
            }

        return cls(input=payload.get("input"), provider_options=options)


class OpenAIResponsesStatus(StrEnum):
    COMPLETED = "completed"
    FAILED = "failed"
    IN_PROGRESS = "in_progress"
    CANCELLED = "cancelled"
    QUEUED = "queued"
    INCOMPLETE = "incomplete"
