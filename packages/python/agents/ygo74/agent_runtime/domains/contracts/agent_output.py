"""Provider-neutral output contract v2, shared by final results and streams."""

from dataclasses import dataclass, field
from enum import StrEnum
from typing import TypeAlias

from ygo74.agent_runtime.domains.contracts.error_envelope import ErrorEnvelope
from ygo74.agent_runtime.domains.contracts.json_value import JsonValue
from ygo74.agent_runtime.domains.contracts.media_content import AudioFormat, MediaSource


class ToolExecution(StrEnum):
    INTERNAL = "internal"
    CLIENT = "client"


class TerminationStatus(StrEnum):
    SUCCESS = "success"
    INCOMPLETE = "incomplete"
    FAILED = "failed"


@dataclass(frozen=True, slots=True)
class UrlCitation:
    url: str
    title: str
    start_index: int
    end_index: int


@dataclass(frozen=True, slots=True)
class TextContent:
    text: str
    annotations: tuple[UrlCitation, ...] = ()


@dataclass(frozen=True, slots=True)
class Notification:
    text: str


@dataclass(frozen=True, slots=True)
class ReasoningContent:
    text: str
    exposable: bool = False


@dataclass(frozen=True, slots=True)
class ToolCallContent:
    call_id: str
    name: str
    arguments: JsonValue = field(default_factory=dict)
    execution: ToolExecution = ToolExecution.CLIENT


@dataclass(frozen=True, slots=True)
class ToolResultContent:
    call_id: str
    name: str
    result: JsonValue
    execution: ToolExecution = ToolExecution.INTERNAL


@dataclass(frozen=True, slots=True)
class ImageContent:
    source: MediaSource


@dataclass(frozen=True, slots=True)
class AudioContent:
    source: MediaSource
    audio_id: str
    transcript: str | None = None
    format: AudioFormat = AudioFormat.WAV
    expires_at: int | None = None


AgentContent: TypeAlias = (
    TextContent
    | Notification
    | ReasoningContent
    | ToolCallContent
    | ToolResultContent
    | ImageContent
    | AudioContent
)


@dataclass(frozen=True, slots=True)
class TokenUsage:
    input_tokens: int
    output_tokens: int
    total_tokens: int | None = None
    cached_input_tokens: int | None = None
    reasoning_output_tokens: int | None = None
    cache_write_input_tokens: int | None = None


@dataclass(frozen=True, slots=True)
class Termination:
    status: TerminationStatus = TerminationStatus.SUCCESS
    reason: str | None = None
    error: ErrorEnvelope | None = None


@dataclass(frozen=True, slots=True)
class AgentOutput:
    contents: tuple[AgentContent, ...] = ()
    usage: TokenUsage | None = None
    termination: Termination = field(default_factory=Termination)
