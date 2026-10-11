"""Provider-neutral output contract v2, shared by final results and streams."""

from dataclasses import dataclass, field
from enum import StrEnum
from typing import TypeAlias

from ygo74.agent_runtime.domains.contracts.error_envelope import ErrorEnvelope
from ygo74.agent_runtime.domains.contracts.json_value import JsonValue
from ygo74.agent_runtime.domains.contracts.media_content import AudioFormat, MediaSource


class ToolExecution(StrEnum):
    """Identify whether a tool call runs inside the agent or is delegated to the client.
    """
    INTERNAL = "internal"
    CLIENT = "client"


class TerminationStatus(StrEnum):
    """Describe whether an invocation succeeded, stopped with incomplete output, or failed.
    """
    SUCCESS = "success"
    INCOMPLETE = "incomplete"
    FAILED = "failed"


@dataclass(frozen=True, slots=True)
class UrlCitation:
    """Reference a source and the text range to which it applies.

    Args:
        url (str): Absolute HTTP(S) source URL for the citation.
        title (str): Human-readable citation title.
        start_index (int): Inclusive start offset in the associated text.
        end_index (int): Exclusive end offset in the associated text.
    """
    url: str
    title: str
    start_index: int
    end_index: int


@dataclass(frozen=True, slots=True)
class TextContent:
    """Carry assistant text and citations anchored to spans within that text.

    Args:
        text (str): Assistant text or notification text carried by this item.
        annotations (tuple[UrlCitation, ...]): Citations whose offsets refer to this text.
    """
    text: str
    annotations: tuple[UrlCitation, ...] = ()


@dataclass(frozen=True, slots=True)
class Notification:
    """Carry informational text for streaming without adding it to the final business result.

    Args:
        text (str): Assistant text or notification text carried by this item.
    """
    text: str


@dataclass(frozen=True, slots=True)
class ReasoningContent:
    """Carry reasoning text with an explicit flag controlling whether it may be exposed.

    Args:
        text (str): Assistant text or notification text carried by this item.
        exposable (bool): Whether the selected protocol may include this reasoning in client-visible output.
    """
    text: str
    exposable: bool = False


@dataclass(frozen=True, slots=True)
class ToolCallContent:
    """Describe a tool invocation, its JSON arguments, and who is responsible for executing it.

    Args:
        call_id (str): Stable identity correlating a tool invocation with its result.
        name (str): Name of the requested tool or function.
        arguments (JsonValue): JSON arguments supplied to the tool.
        execution (ToolExecution): Whether execution is internal or delegated to the client.
    """
    call_id: str
    name: str
    arguments: JsonValue = field(default_factory=dict)
    execution: ToolExecution = ToolExecution.CLIENT


@dataclass(frozen=True, slots=True)
class ToolResultContent:
    """Carry a tool result correlated with the invocation that produced it.

    Args:
        call_id (str): Stable identity correlating a tool invocation with its result.
        name (str): Name of the requested tool or function.
        result (JsonValue): JSON-compatible output returned by the tool.
        execution (ToolExecution): Whether execution is internal or delegated to the client.
    """
    call_id: str
    name: str
    result: JsonValue
    execution: ToolExecution = ToolExecution.INTERNAL


@dataclass(frozen=True, slots=True)
class ImageContent:
    """Reference or carry image data without fetching or transcoding the media.

    Args:
        source (MediaSource): URI or encoded media data with its MIME type.
    """
    source: MediaSource


@dataclass(frozen=True, slots=True)
class AudioContent:
    """Reference or carry audio data together with correlation, transcript, format, and expiry metadata.

    Args:
        source (MediaSource): URI or encoded media data with its MIME type.
        audio_id (str): Stable identity used to correlate audio events and deltas.
        transcript (str | None): Optional text associated with the audio.
        format (AudioFormat): Declared audio format.
        expires_at (int | None): Optional Unix expiry timestamp for generated or referenced media.
    """
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
    """Carry token counters while preserving whether optional provider counts are known.

    Args:
        input_tokens (int): Number of input tokens consumed.
        output_tokens (int): Number of output tokens generated.
        total_tokens (int | None): Total count when supplied by the framework or provider.
        cached_input_tokens (int | None): Input tokens served from cache, when known.
        reasoning_output_tokens (int | None): Output tokens attributed to reasoning, when known.
        cache_write_input_tokens (int | None): Input tokens written to cache, when known.
    """
    input_tokens: int
    output_tokens: int
    total_tokens: int | None = None
    cached_input_tokens: int | None = None
    reasoning_output_tokens: int | None = None
    cache_write_input_tokens: int | None = None


@dataclass(frozen=True, slots=True)
class Termination:
    """Describe the terminal status and optional reason or structured failure.

    Args:
        status (TerminationStatus): Success, incomplete output, or failure.
        reason (str | None): Optional provider-neutral explanation of the termination.
        error (ErrorEnvelope | None): Structured error details when the invocation failed.
    """
    status: TerminationStatus = TerminationStatus.SUCCESS
    reason: str | None = None
    error: ErrorEnvelope | None = None


@dataclass(frozen=True, slots=True)
class AgentOutput:
    """Return a complete typed result independent of the provider response format.

    Args:
        contents (tuple[AgentContent, ...]): Ordered text, tool, reasoning, or media items produced by the agent.
        usage (TokenUsage | None): Token counters reported for this invocation, when available.
        termination (Termination): Explicit completion status and optional error details.
    """
    contents: tuple[AgentContent, ...] = ()
    usage: TokenUsage | None = None
    termination: Termination = field(default_factory=Termination)
