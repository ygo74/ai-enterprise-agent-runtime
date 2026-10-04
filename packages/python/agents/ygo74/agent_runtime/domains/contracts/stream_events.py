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
    """One complete content; no subsequent deltas for this identity."""

    content_id: str
    content: AgentContent


@dataclass(frozen=True, slots=True)
class ContentStart:
    """Initial content followed by zero or more deltas and ContentEnd."""

    content_id: str
    content: AgentContent


@dataclass(frozen=True, slots=True)
class TextDelta:
    content_id: str
    text: str


@dataclass(frozen=True, slots=True)
class ToolArgumentsDelta:
    content_id: str
    delta: str


@dataclass(frozen=True, slots=True)
class AudioDelta:
    """Independently base64-encoded audio bytes, ordered within one audio content."""

    content_id: str
    data: str
    sequence: int


@dataclass(frozen=True, slots=True)
class AudioTranscriptDelta:
    content_id: str
    text: str


@dataclass(frozen=True, slots=True)
class ContentEnd:
    content_id: str


@dataclass(frozen=True, slots=True)
class UsageEvent:
    usage: TokenUsage


@dataclass(frozen=True, slots=True)
class TerminalEvent:
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
