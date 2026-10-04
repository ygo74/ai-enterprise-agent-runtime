"""Per-invocation incremental SDK conversion, independent of HTTP protocols."""

from __future__ import annotations

import json

from agent_framework import AgentResponseUpdate, Content
from ygo74.agent_runtime.domains.contracts.agent_output import (
    ReasoningContent,
    Termination,
    TerminationStatus,
    TextContent,
    ToolCallContent,
    ToolExecution,
)
from ygo74.agent_runtime.domains.contracts.stream_events import (
    AgentStreamEvent,
    ContentEnd,
    ContentEvent,
    ContentStart,
    TerminalEvent,
    TextDelta,
    ToolArgumentsDelta,
    UsageEvent,
)

from .conversion import (
    ConversionDecision,
    ConversionReason,
    ConversionStatus,
    UpdateConversion,
)
from .output_adapter import NativeContentType, NativeFinishReason, _ContentMapper


class AgentFrameworkStreamAdapter:
    """Create one adapter per SDK invocation; call finish only after exhaustion.

    Native finish reasons can terminate intermediate tool rounds, so updates
    never emit a terminal event. The caller owns producer completion and policy.
    """

    def __init__(
        self, *, expose_reasoning: bool = False,
        tool_execution: ToolExecution = ToolExecution.INTERNAL,
    ) -> None:
        self._mapper = _ContentMapper(expose_reasoning=expose_reasoning, tool_execution=tool_execution)
        self._active: dict[str, None] = {}
        self._counter = 0
        self._closed = False
        self._termination = Termination()

    def convert_update(self, update: AgentResponseUpdate) -> UpdateConversion:
        if self._closed:
            raise ValueError("cannot convert updates after finish")
        if not isinstance(update, AgentResponseUpdate):
            raise TypeError("update must be an AgentResponseUpdate")
        if update.finish_reason is not None and self._termination.status is not TerminationStatus.FAILED:
            self._termination = self._mapper.termination(update.finish_reason)
        events: list[AgentStreamEvent] = []
        decisions: list[ConversionDecision] = []
        for index, content in enumerate(update.contents):
            identity = content.id or f"{update.message_id or 'message'}:{content.type}:{index}"
            if content.type == NativeContentType.CALL.value and content.call_id:
                identity = f"tool:{content.call_id}"
            if update.role is not None and update.role not in ("assistant", "tool"):
                decisions.append(ConversionDecision(
                    identity, content.type, ConversionStatus.EXCLUDED, ConversionReason.NON_OUTPUT_ROLE,
                ))
                continue
            if content.type == NativeContentType.CALL.value:
                self._call(content, identity, events, decisions)
                continue
            mapped = self._mapper.map(content, identity)
            decisions.append(mapped.decision)
            annotation_decision = self._mapper.annotation_decision(content, identity)
            if annotation_decision is not None:
                decisions.append(annotation_decision)
            if mapped.usage is not None:
                events.append(UsageEvent(mapped.usage))
            if mapped.termination is not None:
                self._termination = mapped.termination
            if mapped.content is None:
                continue
            if isinstance(mapped.content, (TextContent, ReasoningContent)):
                if identity not in self._active:
                    initial = (ReasoningContent("", exposable=True)
                               if isinstance(mapped.content, ReasoningContent) else TextContent(""))
                    events.append(ContentStart(identity, initial))
                    self._active[identity] = None
                events.append(TextDelta(identity, mapped.content.text))
                continue
            if content.type == NativeContentType.RESULT.value:
                call_identity = f"tool:{content.call_id}"
                if call_identity in self._active:
                    events.append(ContentEnd(call_identity))
                    del self._active[call_identity]
            self._counter += 1
            events.append(ContentEvent(f"{identity}:complete-{self._counter}", mapped.content))
        if update.finish_reason is not None and update.finish_reason not in NativeFinishReason:
            decisions.append(ConversionDecision(
                "update:finish", "finish_reason", ConversionStatus.UNSUPPORTED, ConversionReason.UNKNOWN_FINISH_REASON,
            ))
        return UpdateConversion(tuple(events), tuple(decisions))

    def _call(
        self, content: Content, identity: str,
        events: list[AgentStreamEvent], decisions: list[ConversionDecision],
    ) -> None:
        name = content.name or self._mapper.tool_names.get(content.call_id or "")
        if not content.call_id or not name or content.exception:
            reason = ConversionReason.TOOL_ERROR if content.exception else ConversionReason.MISSING_TOOL_IDENTITY
            decisions.append(ConversionDecision(identity, content.type, ConversionStatus.UNSUPPORTED, reason))
            return
        try:
            arguments = (content.arguments if isinstance(content.arguments, str)
                         else self._json_arguments(content.arguments))
        except (ValueError, TypeError):
            decisions.append(ConversionDecision(
                identity, content.type, ConversionStatus.UNSUPPORTED, ConversionReason.INVALID_JSON,
            ))
            return
        self._mapper.tool_names[content.call_id] = name
        decisions.append(ConversionDecision(
            identity, content.type, ConversionStatus.CONVERTED, ConversionReason.SUPPORTED,
        ))
        annotation_decision = self._mapper.annotation_decision(content, identity)
        if annotation_decision is not None:
            decisions.append(annotation_decision)
        if identity not in self._active:
            events.append(ContentStart(identity, ToolCallContent(
                content.call_id, name, execution=self._mapper.tool_execution,
            )))
            self._active[identity] = None
        if arguments:
            events.append(ToolArgumentsDelta(identity, arguments))

    @staticmethod
    def _json_arguments(value: object) -> str:
        if value is None:
            return ""
        return json.dumps(_ContentMapper.json_value(value), separators=(",", ":"), allow_nan=False)

    def finish(self, termination: Termination | None = None) -> tuple[AgentStreamEvent, ...]:
        """Close active contents and emit exactly one caller-owned terminal.

        Exceptions/cancellation are not success: propagate them or provide an
        explicit failed/incomplete Termination rather than calling this on abort.
        """
        if self._closed:
            return ()
        self._closed = True
        events: list[AgentStreamEvent] = [ContentEnd(identity) for identity in self._active]
        self._active.clear()
        final = self._termination
        if termination is not None and final.status is not TerminationStatus.FAILED:
            final = termination
        events.append(TerminalEvent(final))
        return tuple(events)
