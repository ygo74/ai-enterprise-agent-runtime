"""Native MAF execution with one lifecycle driver for both response modes."""

import logging
from collections.abc import AsyncGenerator, Callable
from contextlib import aclosing
from dataclasses import dataclass, replace
from typing import Any
from uuid import uuid4

from agent_framework import (
    Agent,
    AgentResponse,
    AgentSession,
    BaseChatClient,
    Message,
    SupportsAgentRun,
)
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
    ContentEnd,
    ContentEvent,
    ContentStart,
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
from ygo74.agent_runtime.domains.sessions.continuity_diagnostics import (
    ContinuationReference,
    ContinuityDiagnostics,
)

from .approval import ApprovalResolver, MafApprovalTranslator, PendingToolApproval
from .output_adapter import AgentFrameworkOutputAdapter
from .progress import ConversionDiagnostics, NativeStreamScope, ToolProgressPolicy
from .stream_adapter import AgentFrameworkStreamAdapter

_logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class _Round:
    """One native sub-run result.

    Args:
        response: Native state used by the optional approval bridge.
        output: Converted safe output and real reported usage.
        local_approval: SDK-only approval dispatch with no provider invocation.
    """

    response: AgentResponse[Any]
    output: AgentOutput
    local_approval: bool


class UsageAccumulator:
    """Sum real sub-run counts, preserving unknown optional counters."""

    def __init__(self) -> None:
        """Initialize an invocation with no reported usage."""
        self.usage: TokenUsage | None = None
        self._unreported = False

    def add(self, usage: TokenUsage | None) -> None:
        """Add each sub-run exactly once.

        Args:
            usage: Final native snapshot, or last update snapshot if absent.
        """
        if usage is None:
            if self.usage is not None:
                raise RuntimeError("Native sub-runs must report usage consistently")
            self._unreported = True
            return
        if self._unreported:
            raise RuntimeError("Native sub-runs must report usage consistently")
        if self.usage is None:
            self.usage = usage
            return
        previous = self.usage
        optional = (
            "total_tokens", "cached_input_tokens", "reasoning_output_tokens", "cache_write_input_tokens",
        )
        counts = [None if getattr(previous, key) is None or getattr(usage, key) is None
                  else getattr(previous, key) + getattr(usage, key) for key in optional]
        self.usage = TokenUsage(previous.input_tokens + usage.input_tokens,
                                previous.output_tokens + usage.output_tokens, *counts)


class AgentFrameworkSession:
    """Bind an existing native Agent; no skills, registry or HTTP knowledge needed.

    Args:
        agent: Existing MAF agent, never reconstructed by the binding.
        session_id: Conversation history identifier.
        resolver: Optional advanced approval resolver.
        translator: Optional native approval translator.
        discard_authorizations: Domain grant cleanup for error/cancellation.
        tool_names: Admitted tool names eligible for safe activity.
        max_approval_rounds: Maximum actual human-question batches.
        max_total_rounds: Maximum approval batches.
        interrupted_message: Optional domain wording for a question-budget stop.
        exhausted_message: Optional domain wording for a total-budget stop.
        require_provider_continuation: Fail closed when provider-only history is unavailable.
    """

    def __init__(
        self, agent: SupportsAgentRun, *, session_id: str | None = None,
        resolver: ApprovalResolver | None = None, translator: MafApprovalTranslator | None = None,
        discard_authorizations: Callable[[], None] | None = None, tool_names: tuple[str, ...] = (),
        max_approval_rounds: int = 25, max_total_rounds: int = 200,
        interrupted_message: str | None = None, exhausted_message: str | None = None,
        require_provider_continuation: bool = False,
    ) -> None:
        """Create a native session and the shared approval driver.

        Args:
            agent: Native agent to execute.
            session_id: Native conversation identifier.
            resolver: Optional advanced resolver.
            translator: Optional bridge translator.
            discard_authorizations: Deterministic fail-closed grant cleanup.
            tool_names: Trusted public activity names.
            max_approval_rounds: Prompt bound.
            max_total_rounds: Resume bound.
            interrupted_message: Optional prompt-limit explanation.
            exhausted_message: Optional resume-limit explanation.
            require_provider_continuation: Explicit provider-only history profile; never enables local fallback.
        """
        self._agent = agent
        self._require_provider_continuation = require_provider_continuation
        if require_provider_continuation and isinstance(agent, Agent) and agent.default_options.get("store") is False:
            raise ValueError("Provider history profile conflicts with local storage")
        self._instance = uuid4().hex
        self._turn = 0
        self._subrun = 0
        if isinstance(agent, Agent):
            NativeStreamScope.attach(agent.client)
        self._session: AgentSession = agent.create_session(session_id=session_id)
        self._diagnose("create")
        self._resolver = resolver
        self._translator = translator or MafApprovalTranslator()
        self._discard = discard_authorizations
        self._tool_names = tool_names
        self._broken = False
        self._cleanup_usage: list[TokenUsage | None] = []
        self._cleanup_failure: Termination | None = None
        self._loop = ApprovalLoop(self, max_approval_rounds=max_approval_rounds,
                                  max_total_rounds=max_total_rounds,
                                  interrupted_message=interrupted_message or DEFAULT_INTERRUPTED_MESSAGE,
                                  exhausted_message=exhausted_message or DEFAULT_EXHAUSTED_MESSAGE)

    async def ask(self, message: str) -> str:
        """Answer a normal native run.

        Args:
            message: Latest user text; history remains server-managed.
        """
        output = await self.ask_output(message)
        if output.termination.status is TerminationStatus.FAILED:
            raise RuntimeError("Native agent execution failed")
        return "".join(item.text for item in output.contents if isinstance(item, TextContent))

    async def ask_output(self, message: str) -> AgentOutput:
        """Return typed output, preserving native termination and usage.

        Args:
            message: Latest user text.
        """
        async with aclosing(self._execute(message, stream=False)) as execution:
            async for item in execution:
                if isinstance(item, AgentOutput):
                    return item
        raise RuntimeError("native execution produced no output")

    async def ask_stream(self, message: str) -> AsyncGenerator[AgentStreamEvent]:
        """Stream real native updates through existing adapters.

        Args:
            message: Latest user text.
        """
        async with aclosing(self._execute(message, stream=True)) as execution:
            async for item in execution:
                if not isinstance(item, AgentOutput):
                    yield item

    async def _execute(self, message: str, *, stream: bool) -> AsyncGenerator[AgentStreamEvent | AgentOutput]:
        """Own native sub-runs and exactly one invocation terminal.

        Args:
            message: Initial user text.
            stream: Native response mode, not an output simulation flag.
        """
        if self._broken:
            raise RuntimeError("native session was invalidated; create a fresh conversation")
        budget, usage = ApprovalBudget(), UsageAccumulator()
        self._turn += 1
        self._subrun = 0
        self._cleanup_usage.clear()
        self._cleanup_failure = None
        current: str | Message = message
        completed = False
        last_usage: TokenUsage | None = None
        try:
            while True:
                result: _Round | None = None
                async with aclosing(self._round(current, stream=stream, previous_usage=usage.usage)) as round_stream:
                    async for item in round_stream:
                        if isinstance(item, _Round):
                            result = item
                        else:
                            if isinstance(item, UsageEvent):
                                last_usage = item.usage
                            yield item
                if result is None:
                    raise RuntimeError("native sub-run produced no response")
                if not result.local_approval:
                    usage.add(result.output.usage)
                output = replace(result.output, usage=usage.usage)
                if output.termination.status is TerminationStatus.FAILED:
                    self.discard_authorizations()
                    self._broken = True
                    self._diagnose("invalidate", reason="native_failed")
                    break
                step = await self._loop.advance(result.response, budget)
                if step.interruption is not None:
                    try:
                        for cleanup_usage in self._cleanup_usage:
                            usage.add(cleanup_usage)
                    except RuntimeError:
                        if self._cleanup_failure is None:
                            raise
                        # Missing refusal counts cannot replace a native failure
                        # with a usage error or make a partial total authoritative.
                        usage = UsageAccumulator()
                    if self._cleanup_failure is not None:
                        output = AgentOutput((), usage.usage, self._cleanup_failure)
                        break
                    # An interrupted CLI conversation may continue, but must never
                    # reuse unresolved SDK approval state after best-effort cleanup.
                    self._session = self._agent.create_session(session_id=self._session.session_id)
                    self._diagnose("recreate", reason="approval_budget")
                    output = AgentOutput((TextContent(step.interruption),), usage.usage,
                                         Termination(TerminationStatus.INCOMPLETE, "approval_budget"))
                    if stream:
                        yield ContentEvent(uuid4().hex, TextContent(step.interruption))
                    break
                if not step.pending:
                    break
                if self._resolver is None:
                    raise RuntimeError("native approvals require an explicit approval bridge")
                answers = await self._resolver.resolve(step.pending)
                current = self._translator.answer_message(answers.answers)
            if stream:
                if usage.usage is not None and usage.usage != last_usage:
                    yield UsageEvent(usage.usage)
                completed = True
                yield TerminalEvent(output.termination)
            else:
                completed = True
                yield output
        finally:
            if not completed:
                self._broken = True
                self._diagnose("invalidate", reason="error_or_cancel")
                self.discard_authorizations()

    async def _round(
        self, message: str | Message, *, stream: bool, previous_usage: TokenUsage | None,
    ) -> AsyncGenerator[AgentStreamEvent | _Round]:
        """Convert one sub-run and close producer/content lifecycle on exit.

        Args:
            message: User text or native approval answers.
            stream: Whether to invoke native streaming.
            previous_usage: Completed sub-run counters, for cumulative snapshots.
        """
        invocation_id = uuid4().hex
        self._subrun += 1
        self._diagnose("before", stream=stream)
        adapter = AgentFrameworkStreamAdapter()
        progress = ToolProgressPolicy(self._tool_names)
        snapshot: TokenUsage | None = None
        hidden: set[str] = set()
        terminal: Termination | None = None
        scope = NativeStreamScope(
            session_instance=self._instance, turn=self._turn, subrun=self._subrun,
            storage_default=bool(getattr(getattr(self._agent, "client", None), "STORES_BY_DEFAULT", False)),
        )
        if stream:
            with scope.activate():
                producer = self._agent.run(message, stream=True, session=self._session)
            try:
                async for update in scope.updates(producer):
                    for progress_event in progress.observe(update):
                        yield progress_event
                    conversion = adapter.convert_update(update)
                    ConversionDiagnostics.record(conversion.decisions, invocation_id)
                    for event in conversion.events:
                        if isinstance(event, UsageEvent):
                            snapshot = event.usage
                            cumulative = UsageAccumulator()
                            if previous_usage is not None:
                                cumulative.add(previous_usage)
                            cumulative.add(snapshot)
                            if cumulative.usage is not None:
                                yield UsageEvent(cumulative.usage)
                        elif self._visible(event, hidden):
                            yield self._namespace(event, invocation_id)
                with scope.activate():
                    response = await producer.get_final_response()
                for event in adapter.finish():
                    if isinstance(event, TerminalEvent):
                        terminal = event.termination
                    elif self._visible(event, hidden):
                        yield self._namespace(event, invocation_id)
            except Exception as error:  # Translate the native execution boundary without exposing provider messages.
                raise RuntimeError("Native agent execution failed") from error
            finally:
                await scope.close(producer)
        else:
            try:
                with scope.activate():
                    response = await self._agent.run(message, session=self._session)
            except Exception as error:  # Translate the native execution boundary without exposing provider messages.
                raise RuntimeError("Native agent execution failed") from error
        self._diagnose("after", stream=stream)
        self._validate_continuity(scope)
        conversion_output = AgentFrameworkOutputAdapter().convert(response)
        ConversionDiagnostics.record(conversion_output.decisions, invocation_id)
        output = conversion_output.output
        termination = output.termination
        if terminal is not None and terminal.status is not TerminationStatus.SUCCESS:
            termination = terminal
        if termination.error is not None:
            termination = replace(termination, error=ErrorEnvelope(
                code="native_execution_failed", category="handler_execution", message="Native agent execution failed",
            ))
        contents = tuple(item for item in output.contents if not isinstance(item, (ToolCallContent, ToolResultContent)))
        local_approval = (
            isinstance(getattr(self._agent, "client", None), BaseChatClient)
            and not scope.provider_called and output.usage is None and snapshot is None
            and bool(response.messages)
            and all(message.contents for message in response.messages)
            and all(content.type == "function_approval_request"
                    for message in response.messages for content in message.contents)
        )
        # SDK middleware dispatches parallel approvals one at a time without
        # inference. These rounds have no missing provider usage to accumulate.
        yield _Round(response, AgentOutput(contents, output.usage or snapshot, termination), local_approval)

    def _validate_continuity(self, scope: NativeStreamScope) -> None:
        """Fail closed only for the explicitly selected provider-history profile.

        Args:
            scope: Finalized provider subcall observations; missing handles cannot reuse stale state.
        """
        if not self._require_provider_continuation:
            return
        ref = ContinuationReference.of(self._session.service_session_id)
        if scope.missing_continuation or ref.fingerprint is None:
            self._diagnose("missing_continuation")
            raise RuntimeError("Provider history continuation is unavailable; create a fresh conversation")
        if scope.last_continuation is not None and scope.last_continuation != ref:
            self._diagnose("continuation_mismatch")
            raise RuntimeError("Provider history continuation was not retained; create a fresh conversation")

    def _diagnose(self, phase: str, *, stream: bool | None = None, reason: str | None = None) -> None:
        """Record session continuity without exposing IDs or native state.

        Args:
            phase: Lifecycle stage.
            stream: Native response mode when known.
            reason: Trusted lifecycle reason.
        """
        ref = ContinuationReference.of(self._session.service_session_id)
        ContinuityDiagnostics.record(
            _logger, "native session continuity", phase=phase, reason=reason,
            session_instance=self._instance, turn=self._turn, subrun=self._subrun, stream=stream,
            conversation_fingerprint=ContinuityDiagnostics.fingerprint(self._session.session_id),
            service_continuation_kind=ref.kind, service_continuation_fingerprint=ref.fingerprint,
            require_provider_continuation=self._require_provider_continuation,
            storage_explicit=(self._agent.default_options.get("store") if isinstance(self._agent, Agent) else None),
            storage_default=bool(getattr(getattr(self._agent, "client", None), "STORES_BY_DEFAULT", False)),
        )

    @staticmethod
    def _namespace(event: AgentStreamEvent, run_id: str) -> AgentStreamEvent:
        """Prevent SDK-default content IDs from colliding across approval sub-runs.

        Args:
            event: Visible content/lifecycle event.
            run_id: Unique native sub-run identifier, also used in diagnostics.
        """
        if isinstance(event, (UsageEvent, TerminalEvent)):
            return event
        return replace(event, content_id=f"{run_id}:{event.content_id}")

    @staticmethod
    def _visible(event: AgentStreamEvent, hidden: set[str]) -> bool:
        """Filter entire internal tool lifecycles rather than leaking payloads.

        Args:
            event: Converted native event.
            hidden: Tool content identities suppressed in this sub-run.
        """
        if isinstance(event, (ContentStart, ContentEvent)) and isinstance(event.content, (ToolCallContent, ToolResultContent)):
            hidden.add(event.content_id)
            return False
        if isinstance(event, ToolArgumentsDelta):
            return False
        return not (isinstance(event, ContentEnd) and event.content_id in hidden)

    def pending(self, state: AgentResponse[Any]) -> tuple[PendingToolApproval, ...]:
        """Inspect native suspended calls.

        Args:
            state: Completed native response.
        """
        return self._translator.pending_approvals(state)

    def will_question(self, pending: tuple[PendingToolApproval, ...]) -> bool:
        """Classify human prompts using the injected resolver.

        Args:
            pending: Suspended batch.
        """
        return self._resolver is not None and self._resolver.will_question(pending)

    async def resume(self, pending: tuple[PendingToolApproval, ...]) -> AgentResponse[Any]:
        """Support the existing neutral normal-mode ApprovalLoop port.

        Args:
            pending: Suspended calls.
        """
        if self._resolver is None:
            raise RuntimeError("native approvals require an explicit approval bridge")
        answers = await self._resolver.resolve(pending)
        return await self._agent.run(self._translator.answer_message(answers.answers), session=self._session)

    async def decline(self, pending: tuple[PendingToolApproval, ...]) -> AgentResponse[Any]:
        """Explicitly decline outstanding calls during bounded abandonment.

        Args:
            pending: Calls that must never execute.
        """
        answers = tuple(item.answer(approved=False) for item in pending)
        try:
            async with aclosing(self._round(
                self._translator.answer_message(answers), stream=False, previous_usage=None,
            )) as execution:
                async for item in execution:
                    if isinstance(item, _Round):
                        if not item.local_approval:
                            self._cleanup_usage.append(item.output.usage)
                        if item.output.termination.status is TerminationStatus.FAILED:
                            self._cleanup_failure = item.output.termination
                            self._broken = True
                            raise RuntimeError("Native agent execution failed")
                        return item.response
            raise RuntimeError("native decline produced no response")
        except Exception:
            # ApprovalLoop's best-effort cleanup catches errors; retain failure so
            # it cannot turn this native failure into an approval-budget result.
            self._broken = True
            self._cleanup_failure = self._cleanup_failure or Termination(
                TerminationStatus.FAILED, error=ErrorEnvelope(
                    code="native_execution_failed", category="handler_execution", message="Native agent execution failed",
                ),
            )
            raise

    def discard_authorizations(self) -> None:
        """Clear domain grants on abandonment, error or cancellation."""
        if self._discard is not None:
            self._discard()

    def final_text(self, state: AgentResponse[Any]) -> str:
        """Extract normal-mode framework text.

        Args:
            state: Completed native response.
        """
        return state.text
