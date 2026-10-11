"""Incremental output contract v2. Content identities are not provider indices."""

from dataclasses import dataclass, field
from typing import TypeAlias

from ygo74.agent_runtime.domains.contracts.agent_output import (
    AgentContent,
    Termination,
    TokenUsage,
)


@dataclass(frozen=True, slots=True)
class ContentEvent:
    """Emit one complete typed content item without later deltas for its identity.

    Args:
        content_id (str): Stable identity for this complete item.
        content (AgentContent): Complete typed content emitted by the agent.
    """
    content_id: str
    content: AgentContent


@dataclass(frozen=True, slots=True)
class ContentStart:
    """Start a content item that will receive zero or more deltas and one end event.

    Args:
        content_id (str): Stable identity shared by the item’s later events.
        content (AgentContent): Initial typed content used to choose projection and lifecycle handling.
    """
    content_id: str
    content: AgentContent


@dataclass(frozen=True, slots=True)
class TextDelta:
    """Carry the next text fragment for an already-started content item.

    Args:
        content_id (str): Stable identity of the item receiving this fragment.
        text (str): New text fragment, appended in event order.
    """
    content_id: str
    text: str


@dataclass(frozen=True, slots=True)
class ToolArgumentsDelta:
    """Carry the next JSON-text fragment for a correlated tool invocation.

    Args:
        content_id (str): Stable identity of the tool call receiving this fragment.
        delta (str): New serialized argument fragment, appended in event order.
    """
    content_id: str
    delta: str


@dataclass(frozen=True, slots=True)
class AudioDelta:
    """Carry one base64 audio fragment in sequence for an audio content item.

    Args:
        content_id (str): Stable identity of the audio item receiving this fragment.
        data (str): Base64-encoded audio bytes for this fragment.
        sequence (int): Zero-based sequence number preserving fragment order.
    """
    content_id: str
    data: str
    sequence: int


@dataclass(frozen=True, slots=True)
class AudioTranscriptDelta:
    """Carry the next transcript fragment for a correlated audio item.

    Args:
        content_id (str): Stable identity of the audio item receiving this fragment.
        text (str): New transcript text appended in event order.
    """
    content_id: str
    text: str


@dataclass(frozen=True, slots=True)
class ContentEnd:
    """Close a previously started content item after its final delta.

    Args:
        content_id (str): Stable identity of the item being closed.
    """
    content_id: str


@dataclass(frozen=True, slots=True)
class UsageEvent:
    """Carry the latest cumulative usage snapshot available for the stream.

    Args:
        usage (TokenUsage): Input, output, and any known optional token counters.
    """
    usage: TokenUsage


@dataclass(frozen=True, slots=True)
class TerminalEvent:
    """End the stream with its final completion status.

    Args:
        termination (Termination): Success, incomplete output, or failure and its optional details.
    """
    termination: Termination = field(default_factory=Termination)


AgentStreamEvent: TypeAlias = (
    ContentEvent
    | ContentStart
    | TextDelta
    | ToolArgumentsDelta
    | AudioDelta
    | AudioTranscriptDelta
    | ContentEnd
    | UsageEvent
    | TerminalEvent
)
