"""Explicit tagged JSON boundary for neutral output snapshots, never handler inference."""

import math
from dataclasses import Field, fields
from enum import StrEnum
from typing import ClassVar, Protocol, TypeAlias, cast

from .agent_output import (
    AgentContent,
    AgentOutput,
    AudioContent,
    ImageContent,
    Notification,
    ReasoningContent,
    Termination,
    TextContent,
    TokenUsage,
    ToolCallContent,
    ToolResultContent,
    UrlCitation,
)
from .error_envelope import ErrorEnvelope
from .exchange_models import StandardExchangeResponse
from .json_value import JsonValue
from .media_content import EncodedMedia, MediaSource, MediaUri
from .stream_events import (
    AgentStreamEvent,
    AudioDelta,
    AudioTranscriptDelta,
    ContentEnd,
    ContentEvent,
    ContentStart,
    TerminalEvent,
    TextDelta,
    ToolArgumentsDelta,
    UsageEvent,
)


class OutputValueType(StrEnum):
    AGENT_OUTPUT = "agent_output"
    EXCHANGE_RESPONSE = "exchange_response"
    TEXT = "text"
    NOTIFICATION = "notification"
    REASONING = "reasoning"
    TOOL_CALL = "tool_call"
    TOOL_RESULT = "tool_result"
    IMAGE = "image"
    AUDIO = "audio"
    MEDIA_URI = "media_uri"
    ENCODED_MEDIA = "encoded_media"
    CONTENT_EVENT = "content_event"
    CONTENT_START = "content_start"
    TEXT_DELTA = "text_delta"
    TOOL_ARGUMENTS_DELTA = "tool_arguments_delta"
    AUDIO_DELTA = "audio_delta"
    AUDIO_TRANSCRIPT_DELTA = "audio_transcript_delta"
    CONTENT_END = "content_end"
    USAGE_EVENT = "usage_event"
    TERMINAL_EVENT = "terminal_event"


class OutputSerializationError(ValueError):
    """A value cannot be represented by the explicit neutral JSON boundary."""


class _DataclassInstance(Protocol):
    __dataclass_fields__: ClassVar[dict[str, Field[object]]]


OutputSerializable: TypeAlias = (
    AgentOutput
    | StandardExchangeResponse
    | AgentContent
    | MediaSource
    | AgentStreamEvent
)


class AgentOutputSerializer:
    """Render typed values as {type, value}, recursively preserving union identities.

    The result is a neutral JSON snapshot, not a provider payload or accepted raw
    handler result. Non-union records retain their ordinary field representation.
    """

    _tags: ClassVar[dict[type[object], OutputValueType]] = {
        AgentOutput: OutputValueType.AGENT_OUTPUT,
        StandardExchangeResponse: OutputValueType.EXCHANGE_RESPONSE,
        TextContent: OutputValueType.TEXT,
        Notification: OutputValueType.NOTIFICATION,
        ReasoningContent: OutputValueType.REASONING,
        ToolCallContent: OutputValueType.TOOL_CALL,
        ToolResultContent: OutputValueType.TOOL_RESULT,
        ImageContent: OutputValueType.IMAGE,
        AudioContent: OutputValueType.AUDIO,
        MediaUri: OutputValueType.MEDIA_URI,
        EncodedMedia: OutputValueType.ENCODED_MEDIA,
        ContentEvent: OutputValueType.CONTENT_EVENT,
        ContentStart: OutputValueType.CONTENT_START,
        TextDelta: OutputValueType.TEXT_DELTA,
        ToolArgumentsDelta: OutputValueType.TOOL_ARGUMENTS_DELTA,
        AudioDelta: OutputValueType.AUDIO_DELTA,
        AudioTranscriptDelta: OutputValueType.AUDIO_TRANSCRIPT_DELTA,
        ContentEnd: OutputValueType.CONTENT_END,
        UsageEvent: OutputValueType.USAGE_EVENT,
        TerminalEvent: OutputValueType.TERMINAL_EVENT,
    }

    def serialize(self, value: OutputSerializable) -> dict[str, JsonValue]:
        try:
            return self._tag(value)
        except RecursionError as exc:
            raise OutputSerializationError(
                "Neutral snapshots cannot contain cycles or excessively deep values"
            ) from exc

    def _tag(self, value: object) -> dict[str, JsonValue]:
        tag = self._tags.get(type(value))
        if tag is None:
            raise OutputSerializationError(
                "Neutral serialization requires an explicitly supported typed value"
            )
        return {"type": tag.value, "value": self._record(value)}

    def _record(self, value: object) -> dict[str, JsonValue]:
        return {
            field.name: self._json(cast(object, getattr(value, field.name)))
            for field in fields(cast(_DataclassInstance, value))
        }

    def _json(self, value: object) -> JsonValue:
        if type(value) in self._tags:
            return self._tag(value)
        if isinstance(value, (TokenUsage, Termination, ErrorEnvelope, UrlCitation)):
            return self._record(value)
        if isinstance(value, StrEnum):
            return value.value
        if value is None or isinstance(value, (str, bool, int)):
            return value
        if isinstance(value, float):
            if not math.isfinite(value):
                raise OutputSerializationError("Neutral JSON numbers must be finite")
            return value
        if isinstance(value, (tuple, list)):
            return [
                self._json(item)
                for item in cast(tuple[object, ...] | list[object], value)
            ]
        if isinstance(value, dict) and all(isinstance(key, str) for key in value):
            return {
                key: self._json(item)
                for key, item in cast(dict[str, object], value).items()
            }
        raise OutputSerializationError(
            "Neutral snapshots must contain JSON-compatible values"
        )
