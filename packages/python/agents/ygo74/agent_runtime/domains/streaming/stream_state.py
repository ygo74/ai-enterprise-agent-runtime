"""Per-invocation lifecycle validation and only necessary output accumulation."""

import base64
import json
from dataclasses import dataclass, field, replace

from ygo74.agent_runtime.domains.contracts.agent_output import (
    AgentContent,
    AgentOutput,
    AudioContent,
    Notification,
    ReasoningContent,
    Termination,
    TerminationStatus,
    TextContent,
    TokenUsage,
    ToolCallContent,
)
from ygo74.agent_runtime.domains.contracts.media_content import EncodedMedia
from ygo74.agent_runtime.domains.contracts.stream_events import (
    AgentStreamEvent,
    AudioDelta,
    AudioTranscriptDelta,
    ContentEnd,
    ContentStart,
    TerminalEvent,
    TextDelta,
    ToolArgumentsDelta,
    UsageEvent,
)
from ygo74.agent_runtime.domains.mapping.output_normalizer import (
    OutputNormalizer,
    OutputValidationError,
)
from ygo74.agent_runtime.domains.mapping.output_projector import (
    ContentSupport,
    FilterReason,
    ProjectionContext,
    ProjectionDecision,
)


@dataclass(slots=True)
class ContentState:
    """Track stream lifecycle state across the operation lifecycle and enforce valid state transitions.

    Args:
        content (AgentContent): The content item being interpreted or projected.
        supported (bool): Whether the provider or framework can represent this value.
        index (int): Position used to correlate an item within its message or stream.
        closed (bool): Whether the content or run has already emitted its terminal event.
        text (list[str]): Text value or fragment carried by this content item.
        arguments (list[str]): JSON arguments associated with a tool call.
        audio (list[bytes]): Audio fragments accumulated for one correlated audio item.
        transcript (list[str]): Audio transcript fragments accumulated for this content item.
        next_audio_sequence (int): Next sequence number to assign to an audio fragment.
    """
    content: AgentContent
    supported: bool
    index: int
    closed: bool = False
    text: list[str] = field(default_factory=list)
    arguments: list[str] = field(default_factory=list)
    audio: list[bytes] = field(default_factory=list)
    transcript: list[str] = field(default_factory=list)
    next_audio_sequence: int = 0


class StreamState:
    """Track stream lifecycle state across the operation lifecycle and enforce valid state transitions.

    Args:
        context (ProjectionContext): The execution context carrying identity and correlated metadata.
    """
    def __init__(self, context: ProjectionContext) -> None:
        """Initialize the instance stream lifecycle state with supplied collaborators and configuration.

        Args:
            context (ProjectionContext): The execution context carrying identity and correlated metadata.
        """
        self.context = context
        self.contents: dict[str, ContentState] = {}
        self.usage: TokenUsage | None = None
        self.termination: Termination | None = None
        self._normalizer = OutputNormalizer()
        self._support = ContentSupport()
        self._next_index = 0
        self._call_ids: set[str] = set()
        self._audio_ids: set[str] = set()
        self._has_projected_audio = False

    def apply(self, event: AgentStreamEvent) -> None:
        """Apply stream lifecycle state to current state while enforcing event sequence invariants.

        Args:
            event (AgentStreamEvent): The typed event whose content or lifecycle effect is processed.
        """
        if self.termination is not None:
            raise OutputValidationError("No events may follow terminal")
        if isinstance(event, ContentStart):
            self._start(event)
            return
        if isinstance(event, UsageEvent):
            self._normalizer.validate_usage(event.usage)
            self.usage = event.usage
            return
        if isinstance(event, TerminalEvent):
            self._normalizer.validate_termination(event.termination)
            if event.termination.status != TerminationStatus.FAILED and any(
                not entry.closed for entry in self.contents.values()
            ):
                raise OutputValidationError(
                    "Successful or incomplete terminal requires all content to be closed"
                )
            self.termination = event.termination
            return
        if not isinstance(
            event,
            (
                TextDelta,
                ToolArgumentsDelta,
                AudioDelta,
                AudioTranscriptDelta,
                ContentEnd,
            ),
        ):
            raise OutputValidationError(
                "Streams must yield typed AgentStreamEvent values"
            )
        self._normalizer.identity(event.content_id)
        entry = self.contents.get(event.content_id)
        if entry is None or entry.closed:
            raise OutputValidationError(
                "Delta/end must refer to an open content identity"
            )
        self._update(entry, event)

    def _start(self, event: ContentStart) -> None:
        """Validate a content start and initialize state for its later deltas.

        Reject duplicate content, tool-call, or audio identities before storing
        the entry. Unsupported content stays tracked for correlation, while only
        supported content consumes an output index and accumulates projected data.

        Args:
            event (ContentStart): The typed event whose content or lifecycle effect is processed.
        """
        # Validate identity and content before allocating a stable output index; filtered content remains tracked for correlation but does not consume a provider index.
        self._normalizer.identity(event.content_id)
        self._normalizer.validate_content(event.content)
        if event.content_id in self.contents:
            raise OutputValidationError("Content identities must be unique")
        content = event.content
        if isinstance(content, ToolCallContent):
            if content.call_id in self._call_ids:
                raise OutputValidationError("Tool call identities must be unique")
            self._call_ids.add(content.call_id)
        if isinstance(content, AudioContent):
            if content.audio_id in self._audio_ids:
                raise OutputValidationError("Audio identities must be unique")
            self._audio_ids.add(content.audio_id)
        decision = self._support.decide(content, self.context, streaming=True)
        if isinstance(content, AudioContent) and decision.supported:
            if self._has_projected_audio:
                decision = ProjectionDecision(False, FilterReason.MULTIPLE_AUDIO)
            self._has_projected_audio = True
        if not decision.supported and decision.reason is not None:
            self._support.log(self.context, content, decision.reason)
        entry = ContentState(content, decision.supported, self._next_index)
        if decision.supported:
            self._next_index += 1
            if isinstance(content, TextContent):
                self._support.annotations(content, self.context)
            if isinstance(content, (TextContent, Notification, ReasoningContent)):
                entry.text.append(content.text)
            if isinstance(content, AudioContent):
                if isinstance(content.source, EncodedMedia):
                    entry.audio.append(base64.b64decode(content.source.data))
                entry.transcript.append(content.transcript or "")
        self.contents[event.content_id] = entry

    def _update(
        self,
        entry: ContentState,
        event: TextDelta
        | ToolArgumentsDelta
        | AudioDelta
        | AudioTranscriptDelta
        | ContentEnd,
    ) -> None:
        """Apply a content delta to its correlated state and reject updates after closure or before start.

        Args:
            entry (ContentState): State or registry entry currently being processed.
            event (TextDelta | ToolArgumentsDelta | AudioDelta | AudioTranscriptDelta | ContentEnd): The typed event whose content or lifecycle effect is processed.
        """
        content = entry.content
        if isinstance(event, TextDelta):
            self._normalizer.text(event.text)
            if not isinstance(content, (TextContent, Notification, ReasoningContent)):
                raise OutputValidationError(
                    "TextDelta requires text, notification, or reasoning content"
                )
            if entry.supported:
                entry.text.append(event.text)
            return
        if isinstance(event, ToolArgumentsDelta):
            self._normalizer.text(event.delta)
            if not isinstance(content, ToolCallContent):
                raise OutputValidationError("ToolArgumentsDelta requires a tool call")
            if content.arguments != {}:
                raise OutputValidationError(
                    "Incremental tool arguments require an empty initial arguments object"
                )
            if event.delta:
                entry.arguments.append(event.delta)
            return
        if isinstance(event, AudioDelta):
            self._normalizer.base64(event.data)
            self._normalizer.counter(event.sequence)
            if not isinstance(content, AudioContent) or not isinstance(
                content.source, EncodedMedia
            ):
                raise OutputValidationError("AudioDelta requires encoded audio content")
            if event.sequence != entry.next_audio_sequence:
                raise OutputValidationError(
                    "Audio deltas must be contiguous and start at sequence zero"
                )
            entry.next_audio_sequence += 1
            if entry.supported:
                entry.audio.append(base64.b64decode(event.data))
            return
        if isinstance(event, AudioTranscriptDelta):
            self._normalizer.text(event.text)
            if not isinstance(content, AudioContent):
                raise OutputValidationError("Transcript deltas require audio content")
            if entry.supported:
                entry.transcript.append(event.text)
            return
        self._finish(entry)

    def _finish(self, entry: ContentState) -> None:
        """Reassemble a content item from its deltas and mark it closed.

        Parse and validate completed tool arguments, join text fragments, or rebuild
        encoded audio and its transcript. Citation bounds are checked once all text
        fragments are available.

        Args:
            entry (ContentState): State or registry entry currently being processed.
        """
        # Rebuild fragmented tool, text, and encoded audio values before closing the entry, then validate data that could only be checked after all deltas arrived.
        content = entry.content
        if isinstance(content, ToolCallContent) and entry.arguments:
            try:
                arguments = json.loads("".join(entry.arguments))
            except ValueError as exc:
                raise OutputValidationError(
                    "Completed tool arguments must be valid JSON"
                ) from exc
            self._normalizer.json_value(arguments)
            content = replace(content, arguments=arguments)
            if entry.supported:
                decision = self._support.decide(content, self.context, streaming=True)
                if not decision.supported:
                    entry.supported = False
                    if decision.reason is not None:
                        self._support.log(self.context, content, decision.reason)
        elif entry.supported and isinstance(
            content, (TextContent, Notification, ReasoningContent)
        ):
            content = replace(content, text="".join(entry.text))
        elif (
            entry.supported
            and isinstance(content, AudioContent)
            and isinstance(content.source, EncodedMedia)
        ):
            content = replace(
                content,
                source=replace(
                    content.source,
                    data=base64.b64encode(b"".join(entry.audio)).decode("ascii"),
                ),
                transcript="".join(entry.transcript),
            )
        if isinstance(content, TextContent):
            self._normalizer.validate_citation_bounds(content)
        entry.content = content
        entry.closed = True

    def output(self) -> AgentOutput:
        """Return the current neutral output stream lifecycle state from accumulated and validated stream state.
        """
        return AgentOutput(
            tuple(
                entry.content
                for entry in self.contents.values()
                if entry.supported
                and entry.closed
                and not isinstance(entry.content, Notification)
            ),
            self.usage,
            self.termination or Termination(),
        )
