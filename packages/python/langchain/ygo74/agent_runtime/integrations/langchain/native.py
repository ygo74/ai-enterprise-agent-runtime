"""Native LangGraph session binding for neutral result and stream contracts."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncGenerator, AsyncIterator, Callable, Mapping, Sequence
from contextlib import aclosing
from typing import Any, Protocol
from uuid import uuid4

from langchain_core.messages import AIMessage
from langchain_core.runnables.schema import StreamEvent
from ygo74.agent_runtime.domains.contracts.agent_output import (
    AgentOutput,
    Termination,
    TerminationStatus,
    TextContent,
    TokenUsage,
    ToolCallContent,
    ToolResultContent,
)
from ygo74.agent_runtime.domains.contracts.error_envelope import ErrorEnvelope
from ygo74.agent_runtime.domains.contracts.stream_events import (
    AgentStreamEvent,
    ContentEvent,
    TerminalEvent,
    ToolArgumentsDelta,
    UsageEvent,
)
from ygo74.agent_runtime.domains.humanapproval.approval_loop import (
    DEFAULT_EXHAUSTED_MESSAGE,
    DEFAULT_INTERRUPTED_MESSAGE,
    ApprovalBudget,
    ApprovalLoop,
)

from .approval import (
    LangGraphApprovalDecision,
    LangGraphApprovalTranslator,
    LangGraphPendingApproval,
)
from .conversion import ConversionOutcome, ConversionStatus
from .results import LangChainResultAdapter
from .streaming import LangChainStreamAdapter

_logger = logging.getLogger(__name__)


class LangGraphRunnable(Protocol):
    """Public async operations required from a compiled LangGraph."""

    async def ainvoke(self, value: object, *, config: Mapping[str, Any]) -> object:
        """Execute one native graph sub-run."""
        ...

    def astream_events(
        self, value: object, *, config: Mapping[str, Any], version: str,
    ) -> AsyncIterator[StreamEvent]:
        """Stream public LangChain events for one native graph sub-run."""
        ...


class ApprovalResolver(Protocol):
    """Domain policy for suspended actions, such as Wiki ticket creation."""

    def will_question(self, pending: tuple[LangGraphPendingApproval, ...]) -> bool:
        """Report whether resolving this batch asks a person now."""
        ...

    async def resolve(
        self, pending: tuple[LangGraphPendingApproval, ...],
    ) -> Sequence[LangGraphApprovalDecision | Mapping[str, Any]]:
        """Return one ordered native decision per suspended action."""
        ...


class LangGraphBindingError(RuntimeError):
    """Raised when a graph result cannot safely satisfy the runtime contract."""


class _RejectingResolver:
    """Safely reject interrupted actions when no domain bridge is configured."""

    def will_question(self, pending: tuple[LangGraphPendingApproval, ...]) -> bool:
        """Avoid charging a human-question budget for automatic rejection."""
        del pending
        return False

    async def resolve(
        self, pending: tuple[LangGraphPendingApproval, ...],
    ) -> Sequence[LangGraphApprovalDecision]:
        """Reject every action without executing domain authorization policy."""
        return tuple(LangGraphApprovalDecision.for_approval(approved=False) for _ in pending)


class _UsageAccumulator:
    """Keep a complete usage total, or mark it unknown after any missing sub-run."""

    def __init__(self) -> None:
        """Start a native invocation with no provider usage reported."""
        self.value: TokenUsage | None = None
        self._missing = False

    def add(self, incoming: TokenUsage | None) -> TokenUsage | None:
        """Add one graph sub-run without publishing a partial total."""
        if incoming is None:
            self._missing = True
            self.value = None
            return None
        if self._missing:
            return None
        self.value = _add_usage(self.value, incoming)
        return self.value


class LangGraphSession:
    """Run an existing compiled graph as one server-managed conversation.

    Args:
        graph: Prebuilt LangGraph; the binding never reconstructs its agent.
        thread_id: Server-derived checkpoint partition for this conversation.
        resolver: Optional domain approval bridge. Without one, interruptions are rejected.
        max_approval_rounds: Maximum batches that ask a person during one invocation.
        max_total_rounds: Maximum graph approval batches during one invocation.
        expose_reasoning: Whether the result adapters may project reasoning content.
    """

    def __init__(
        self,
        graph: LangGraphRunnable,
        *,
        thread_id: str,
        resolver: ApprovalResolver | None = None,
        discard_authorizations: Callable[[], None] | None = None,
        max_approval_rounds: int = 25,
        max_total_rounds: int = 200,
        expose_reasoning: bool = False,
    ) -> None:
        """Bind one native graph and establish its isolated thread configuration."""
        if not thread_id:
            raise ValueError("LangGraph session requires a nonempty thread identifier")
        self._graph = graph
        self.thread_id = thread_id
        self._resolver = resolver or _RejectingResolver()
        self._discard = discard_authorizations
        self._translator = LangGraphApprovalTranslator()
        self._result_adapter = LangChainResultAdapter(expose_reasoning=expose_reasoning)
        self._max_approval_rounds = max_approval_rounds
        self._max_total_rounds = max_total_rounds
        self._broken = False
        self._stream_state: object | None = None
        self._stream_incomplete = False
        self._cleanup_failed = False
        self._cleanup_still_pending = False
        self._cleanup_usage: list[TokenUsage | None] = []

    async def ask(self, message: str) -> str:
        """Answer with the text from one latest-user-message invocation."""
        output = await self.ask_output(message)
        if output.termination.status is TerminationStatus.FAILED:
            raise LangGraphBindingError("LangGraph execution failed")
        return "".join(item.text for item in output.contents if isinstance(item, TextContent))

    async def ask_output(self, message: str) -> AgentOutput:
        """Execute native graph calls and return the final typed assistant result."""
        self._ensure_usable()
        budget = ApprovalBudget()
        usage = _UsageAccumulator()
        self._cleanup_usage.clear()
        self._cleanup_failed = False
        self._cleanup_still_pending = False
        value: object = {"messages": [{"role": "user", "content": message}]}
        try:
            while True:
                result = await self._graph.ainvoke(value, config=self._config())
                usage.add(self._latest_usage(result))
                step = await self._approval_loop().advance(result, budget)
                if step.interruption is not None:
                    for item in self._cleanup_usage:
                        usage.add(item)
                    if self._cleanup_failed or self._cleanup_still_pending:
                        return AgentOutput((), usage.value, _failed_termination())
                    return AgentOutput(
                        (TextContent(step.interruption),), usage.value,
                        Termination(TerminationStatus.INCOMPLETE, "approval_budget"),
                    )
                if not step.pending:
                    output = self._output(result, usage.value)
                    if output.termination.status is TerminationStatus.FAILED:
                        self._broken = True
                    return output
                decisions = await self._resolver.resolve(step.pending)
                value = self._translator.resume_command(decisions, expected_count=len(step.pending))
        except asyncio.CancelledError:
            self._broken = True
            self._discard_safely()
            raise
        except Exception as error:  # noqa: BLE001 — graph/provider failures cross this adapter boundary.
            self._broken = True
            self._discard_safely()
            _logger.error("LangGraph execution failed (%s)", type(error).__name__)
            return AgentOutput((), usage.value, _failed_termination())

    async def ask_stream(self, message: str) -> AsyncIterator[AgentStreamEvent]:
        """Stream native LangChain events, close producers and terminate once."""
        self._ensure_usable()
        budget = ApprovalBudget()
        usage = _UsageAccumulator()
        self._cleanup_usage.clear()
        self._stream_incomplete = False
        self._cleanup_failed = False
        self._cleanup_still_pending = False
        value: object = {"messages": [{"role": "user", "content": message}]}
        completed = False
        try:
            while True:
                round_usage: TokenUsage | None = None
                async with aclosing(self._stream_attempt(value)) as attempt:
                    async for event in attempt:
                        if isinstance(event, UsageEvent):
                            round_usage = event.usage
                        else:
                            yield event
                result = self._stream_state
                if result is None:
                    raise LangGraphBindingError("LangGraph stream ended without a root state")
                usage.add(round_usage or self._latest_usage(result))
                if usage.value is not None:
                    yield UsageEvent(usage.value)
                step = await self._approval_loop().advance(result, budget)
                if step.interruption is not None:
                    for item in self._cleanup_usage:
                        usage.add(item)
                    if usage.value is not None:
                        yield UsageEvent(usage.value)
                    if self._cleanup_failed or self._cleanup_still_pending:
                        yield TerminalEvent(_failed_termination())
                    else:
                        yield ContentEvent(uuid4().hex, TextContent(step.interruption))
                        yield TerminalEvent(Termination(TerminationStatus.INCOMPLETE, "approval_budget"))
                    completed = True
                    return
                if not step.pending:
                    terminal = self._stream_terminal(result)
                    if self._stream_incomplete:
                        terminal = Termination(TerminationStatus.INCOMPLETE, "unsupported_stream_content")
                    yield TerminalEvent(terminal)
                    completed = True
                    return
                decisions = await self._resolver.resolve(step.pending)
                value = self._translator.resume_command(decisions, expected_count=len(step.pending))
        except asyncio.CancelledError:
            self._broken = True
            self._discard_safely()
            raise
        except Exception as error:  # noqa: BLE001 — graph/provider failures cross this adapter boundary.
            self._broken = True
            self._discard_safely()
            _logger.error("LangGraph stream failed (%s)", type(error).__name__)
            yield TerminalEvent(_failed_termination())
            completed = True
        finally:
            if not completed:
                # GeneratorExit means the client abandoned the response; the
                # persisted thread may contain an unfinished turn and is unsafe to reuse.
                self._broken = True
                self._discard_safely()

    def pending(self, result: object) -> tuple[LangGraphPendingApproval, ...]:
        """Expose framework interruptions through the shared approval-loop port."""
        return self._translator.pending(result)

    def will_question(self, pending: tuple[LangGraphPendingApproval, ...]) -> bool:
        """Delegate human-question accounting to the domain resolver."""
        return self._resolver.will_question(pending)

    async def resume(self, pending: tuple[LangGraphPendingApproval, ...]) -> object:
        """Resolve and resume a pending action batch in original order."""
        decisions = await self._resolver.resolve(pending)
        command = self._translator.resume_command(decisions, expected_count=len(pending))
        return await self._graph.ainvoke(command, config=self._config())

    async def decline(self, pending: tuple[LangGraphPendingApproval, ...]) -> object:
        """Reject all actions remaining during bounded abandonment cleanup."""
        decisions = tuple(
            LangGraphApprovalDecision.for_approval(approved=False) for _ in pending
        )
        command = self._translator.resume_command(decisions, expected_count=len(pending))
        try:
            result = await self._graph.ainvoke(command, config=self._config())
        except Exception:
            self._broken = True
            self._cleanup_failed = True
            raise
        usage = self._latest_usage(result)
        self._cleanup_usage.append(usage)
        try:
            self._cleanup_still_pending = bool(self.pending(result))
        except Exception:
            self._cleanup_failed = True
            raise
        return result

    def discard_authorizations(self) -> None:
        """Invoke an optional domain cleanup hook without exposing its payload."""
        if self._discard is not None:
            self._discard()
            return
        self._translator.discard_authorizations(self._resolver)

    def _discard_safely(self) -> None:
        """Attempt grant cleanup while retaining the original execution outcome."""
        try:
            self.discard_authorizations()
        except Exception as error:  # noqa: BLE001 — grant cleanup must fail closed for arbitrary domain errors.
            self._cleanup_failed = True
            _logger.error("LangGraph authorization cleanup failed (%s)", type(error).__name__)

    def final_text(self, result: object) -> str:
        """Return the assistant text selected from a completed graph state."""
        return "".join(item.text for item in self._output(result, None).contents if isinstance(item, TextContent))

    def _approval_loop(self) -> ApprovalLoop[object, LangGraphPendingApproval]:
        """Create a per-invocation loop using this session as its native adapter."""
        return ApprovalLoop(
            self,
            max_approval_rounds=self._max_approval_rounds,
            max_total_rounds=self._max_total_rounds,
            interrupted_message=DEFAULT_INTERRUPTED_MESSAGE,
            exhausted_message=DEFAULT_EXHAUSTED_MESSAGE,
        )

    async def _stream_attempt(self, value: object) -> AsyncGenerator[AgentStreamEvent | UsageEvent, None]:
        """Convert one graph sub-run and retain its root state for approval inspection."""
        adapter = LangChainStreamAdapter()
        self._stream_state = None
        producer = self._graph.astream_events(value, config=self._config(), version="v2")
        close = getattr(producer, "aclose", None)
        terminal: Termination | None = None
        try:
            async for raw_event in producer:
                root_state = _root_state(raw_event)
                if root_state is not None:
                    self._stream_state = root_state
                outcome = adapter.convert(raw_event)
                self._log_diagnostics(outcome)
                if outcome.status is ConversionStatus.UNSUPPORTED:
                    self._stream_incomplete = True
                for event in outcome.events:
                    if isinstance(event, TerminalEvent):
                        terminal = event.termination
                        continue
                    if isinstance(event, UsageEvent):
                        yield event
                        continue
                    if _is_private_tool_event(event):
                        continue
                    yield event
            if self._stream_state is None:
                raise LangGraphBindingError("LangGraph stream omitted the root chain result")
            if terminal is None:
                outcome = adapter.finish()
                terminal = next(
                    (event.termination for event in outcome.events if isinstance(event, TerminalEvent)),
                    Termination(),
                )
            if terminal.status is TerminationStatus.FAILED:
                raise LangGraphBindingError("LangGraph stream reported failed termination")
        finally:
            if close is not None:
                await close()

    def _output(self, result: object, usage: TokenUsage | None) -> AgentOutput:
        """Convert only the latest assistant message and remove internal tool data."""
        message = _latest_assistant(result)
        if message is None:
            raise LangGraphBindingError("LangGraph result has no final assistant message")
        outcome = self._result_adapter.convert(message)
        self._log_diagnostics(outcome)
        if outcome.status is ConversionStatus.UNSUPPORTED or outcome.output is None:
            raise LangGraphBindingError("LangGraph assistant output is not fully representable")
        output = outcome.output
        contents = tuple(
            item for item in output.contents
            if not isinstance(item, ToolCallContent | ToolResultContent)
        )
        return AgentOutput(contents, usage, output.termination)

    def _latest_usage(self, result: object) -> TokenUsage | None:
        """Read usage only from the latest assistant message in this sub-run."""
        message = _latest_assistant(result)
        return self._result_adapter.usage(message) if message is not None else None

    def _stream_terminal(self, result: object) -> Termination:
        """Use the selected final assistant's explicit finish reason."""
        message = _latest_assistant(result)
        if message is None:
            raise LangGraphBindingError("LangGraph result has no final assistant message")
        outcome = self._result_adapter.convert(message)
        self._log_diagnostics(outcome)
        if outcome.status is ConversionStatus.UNSUPPORTED or outcome.output is None:
            raise LangGraphBindingError("LangGraph assistant output is not fully representable")
        return outcome.output.termination

    def _config(self) -> dict[str, dict[str, str]]:
        """Build the server-controlled config that isolates this graph thread."""
        return {"configurable": {"thread_id": self.thread_id}}

    def _ensure_usable(self) -> None:
        """Refuse reuse after a failed, cancelled, or abandoned native turn."""
        if self._broken:
            raise LangGraphBindingError("LangGraph session was invalidated; create a fresh conversation")

    @staticmethod
    def _log_diagnostics(outcome: ConversionOutcome) -> None:
        """Record safe conversion codes without logging native payloads."""
        for diagnostic in outcome.diagnostics:
            _logger.warning("LangChain conversion diagnostic code=%s", diagnostic.code)


def _latest_assistant(result: object) -> AIMessage | None:
    """Find the most recent assistant message in a LangGraph state envelope."""
    state = getattr(result, "value", result)
    if not isinstance(state, Mapping):
        return None
    messages = state.get("messages", ())
    if not isinstance(messages, Sequence) or isinstance(messages, str | bytes):
        return None
    return next((message for message in reversed(messages) if isinstance(message, AIMessage)), None)


def _root_state(event: StreamEvent) -> object | None:
    """Select the root chain output without retaining nested tool snapshots."""
    if event.get("event") != "on_chain_end" or event.get("parent_ids"):
        return None
    output = event.get("data", {}).get("output")
    return output


def _is_private_tool_event(event: AgentStreamEvent) -> bool:
    """Keep internal tool arguments and results out of client-visible activity."""
    if isinstance(event, ContentEvent):
        return isinstance(event.content, ToolCallContent | ToolResultContent)
    return isinstance(event, ToolArgumentsDelta)


def _add_usage(current: TokenUsage | None, incoming: TokenUsage | None) -> TokenUsage | None:
    """Sum sub-run usage while preserving unknown optional counters."""
    if incoming is None:
        return current
    if current is None:
        return incoming

    def add_optional(name: str) -> int | None:
        left, right = getattr(current, name), getattr(incoming, name)
        return left + right if left is not None and right is not None else None

    return TokenUsage(
        current.input_tokens + incoming.input_tokens,
        current.output_tokens + incoming.output_tokens,
        add_optional("total_tokens"),
        cached_input_tokens=add_optional("cached_input_tokens"),
        reasoning_output_tokens=add_optional("reasoning_output_tokens"),
        cache_write_input_tokens=add_optional("cache_write_input_tokens"),
    )


def _failed_termination() -> Termination:
    """Create a safe failure envelope without including provider exception text."""
    return Termination(
        TerminationStatus.FAILED,
        "native_execution_failed",
        ErrorEnvelope("native_execution_failed", "handler_execution", "LangGraph execution failed"),
    )
