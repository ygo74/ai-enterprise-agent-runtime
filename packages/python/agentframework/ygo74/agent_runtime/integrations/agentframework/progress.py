"""Safe native tool activity and producer cleanup for the pinned SDK."""

import inspect
import logging
from collections.abc import AsyncIterator, Awaitable, Callable, Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Any
from uuid import uuid4

from agent_framework import AgentResponseUpdate, BaseChatClient, ResponseStream
from ygo74.agent_runtime.domains.contracts.agent_output import Notification
from ygo74.agent_runtime.domains.contracts.stream_events import ContentEvent
from ygo74.agent_runtime.domains.sessions.continuity_diagnostics import (
    ContinuationReference,
    ContinuityDiagnostics,
)

from .conversion import ConversionDecision, ConversionStatus

_logger = logging.getLogger(__name__)
_active_scope: ContextVar["NativeStreamScope | None"] = ContextVar("native_stream_scope", default=None)
_PROVIDER_RESPONSE_METHOD = "_inner_get_response"


class _ProviderResponseCapture:
    """Keep provider streams reachable without inspecting SDK generator frames.

    Args:
        get_response: Bound SDK 1.18 provider method, preserving native options.
    """

    def __init__(self, get_response: Callable[..., Any]) -> None:
        """Wrap one provider method once.

        Args:
            get_response: Original bound provider implementation.
        """
        self._get_response = get_response

    def __call__(self, *args: Any, **kwargs: Any) -> Any:
        """Capture the provider response in the current invocation only.

        Args:
            args: Native positional arguments, forwarded unchanged.
            kwargs: Native provider-specific arguments, forwarded unchanged.
        """
        scope = _active_scope.get()
        call = scope.provider_call(kwargs) if scope is not None else 0
        result = self._get_response(*args, **kwargs)
        if scope is None:
            return result
        if isinstance(result, ResponseStream):
            scope.track(result)
            result.with_result_hook(lambda response: scope.provider_result(response, call))
            return result
        if inspect.isawaitable(result):
            return self._capture_awaited(result, scope, call)
        return result

    @staticmethod
    async def _capture_awaited(result: Awaitable[Any], scope: "NativeStreamScope", call: int) -> Any:
        """Support providers that resolve their response asynchronously.

        Args:
            result: Original provider awaitable.
            scope: Invocation owning any stream it resolves.
            call: Provider call index within the sub-run.
        """
        response = await result
        if isinstance(response, ResponseStream):
            scope.track(response)
            response.with_result_hook(lambda final: scope.provider_result(final, call))
        else:
            scope.provider_result(response, call)
        return response


class NativeStreamScope:
    """Own SDK provider streams hidden inside the function-invocation loop.

    SDK 1.18 lacks a public ResponseStream.aclose and the function loop does not
    close its local inner_stream on abandonment. A per-client provider-boundary
    wrapper captures those streams during pulls. Context-local ownership avoids
    mixing parallel sessions sharing a client; no agent is rebuilt.
    """

    def __init__(self, *, session_instance: str | None = None, turn: int = 0,
                 subrun: int = 0, storage_default: bool = False) -> None:
        """Initialize provider ownership and structural correlation.

        Args:
            session_instance: Runtime-generated binding instance.
            turn: User invocation number.
            subrun: Approval sub-run number.
            storage_default: Native client default storage behavior.
        """
        self._streams: list[object] = []
        self._session_instance = session_instance
        self._turn, self._subrun = turn, subrun
        self._storage_default = storage_default
        self._calls = 0
        self.missing_continuation = False
        self.last_continuation: ContinuationReference | None = None

    @property
    def provider_called(self) -> bool:
        """Whether this sub-run reached the instrumented native provider."""
        return self._calls > 0

    def provider_call(self, kwargs: dict[str, Any]) -> int:
        """Observe effective SDK options without changing the request.

        Args:
            kwargs: Original SDK boundary arguments; content is never logged.
        """
        self._calls += 1
        options = kwargs.get("options") or {}
        ref = ContinuationReference.of(options.get("conversation_id"))
        messages = kwargs.get("messages") or ()
        self._record("request", self._calls, ref,
                     provider_storage=options.get("store") if options.get("store") is not None else self._storage_default,
                     stream=kwargs.get("stream", False), message_count=len(messages),
                     user_message_count=sum(message.role == "user" for message in messages),
                     assistant_message_count=sum(message.role == "assistant" for message in messages))
        return self._calls

    def provider_result(self, response: Any, call: int) -> None:
        """Observe only successfully finalized provider responses.

        Args:
            response: SDK ChatResponse; payloads and raw provider IDs stay unread.
            call: Provider call index.
        """
        ref = ContinuationReference.of(getattr(response, "conversation_id", None))
        self.last_continuation = ref
        self.missing_continuation = self.missing_continuation or ref.fingerprint is None
        self._record("response", call, ref)

    def _record(self, phase: str, call: int, ref: ContinuationReference,
                **fields: str | int | bool | None) -> None:
        """Emit safe subcall links.

        Args:
            phase: Request or finalized response.
            call: Subcall index.
            ref: Safe continuation metadata.
            fields: Structural request counters/options.
        """
        ContinuityDiagnostics.record(
            _logger, "native provider continuity", session_instance=self._session_instance,
            turn=self._turn, subrun=self._subrun, provider_call=call, phase=phase,
            provider_continuation_kind=ref.kind, provider_continuation_fingerprint=ref.fingerprint, **fields,
        )

    @staticmethod
    def attach(client: object) -> None:
        """Install an idempotent SDK 1.18 provider-boundary wrapper.

        Args:
            client: Existing native client; custom non-SDK clients are unchanged.
        """
        if isinstance(client, BaseChatClient):
            original = getattr(client, _PROVIDER_RESPONSE_METHOD)
            if not isinstance(original, _ProviderResponseCapture):
                setattr(client, _PROVIDER_RESPONSE_METHOD, _ProviderResponseCapture(original))

    def track(self, stream: object) -> None:
        """Retain a provider until native sub-run cleanup.

        Args:
            stream: Provider ResponseStream created during this invocation.
        """
        self._streams.append(stream)

    @contextmanager
    def activate(self) -> Iterator[None]:
        """Capture only a synchronous creation or an awaited native pull."""
        token = _active_scope.set(self)
        try:
            yield
        finally:
            _active_scope.reset(token)

    async def updates(self, producer: AsyncIterator[AgentResponseUpdate]) -> AsyncIterator[AgentResponseUpdate]:
        """Capture provider creation while pulling, never across consumer yields.

        Args:
            producer: Native stream being consumed.
        """
        while True:
            with self.activate():
                try:
                    update = await anext(producer)
                except StopAsyncIteration:
                    return
            yield update

    async def close(self, producer: object) -> None:
        """Close all captured providers even when outer SDK cleanup fails.

        Args:
            producer: Outermost native response stream.
        """
        try:
            await NativeStreamCloser.close(producer)
        finally:
            try:
                for stream in reversed(self._streams):
                    await NativeStreamCloser.close(stream)
            finally:
                self._streams.clear()


class ToolProgressPolicy:
    """Expose only admitted tool names and non-sensitive lifecycle states.

    Args:
        tool_names: Trusted declarations; unrecognized names are never exposed.
    """

    def __init__(self, tool_names: tuple[str, ...] = ()) -> None:
        """Initialize per-sub-run activity correlation.

        Args:
            tool_names: Tool names from trusted configuration.
        """
        self._allowed = frozenset(tool_names)
        self._calls: dict[str, str] = {}
        self._completed: set[str] = set()

    def observe(self, update: AgentResponseUpdate) -> tuple[ContentEvent, ...]:
        """Return safe notices, deduplicating partial/parallel tool updates.

        Args:
            update: Native update; arguments and results are deliberately unread.
        """
        events = []
        for content in update.contents:
            call_id = content.call_id
            if not call_id:
                continue
            if content.type == "function_call" and content.name in self._allowed and call_id not in self._calls:
                self._calls[call_id] = content.name
                events.append(ContentEvent(uuid4().hex, Notification(f"Calling {content.name}…")))
            elif content.type == "function_result" and call_id in self._calls and call_id not in self._completed:
                self._completed.add(call_id)
                state = "Failed" if content.exception else "Completed"
                events.append(ContentEvent(uuid4().hex, Notification(f"{state} {self._calls[call_id]}.")))
        return tuple(events)


class ConversionDiagnostics:
    """Log reason codes with caller-generated correlation, never native payloads."""

    @staticmethod
    def record(decisions: tuple[ConversionDecision, ...], invocation_id: str) -> None:
        """Record only structural conversion outcomes.

        Args:
            decisions: Adapter decisions without raw content.
            invocation_id: Runtime-generated correlation identifier.
        """
        for decision in decisions:
            if decision.status is not ConversionStatus.CONVERTED:
                _logger.debug("native conversion", extra={
                    "invocation_id": invocation_id,
                    "conversion_status": decision.status.value,
                    "conversion_reason": decision.reason.value,
                })


class NativeStreamCloser:
    """Close SDK 1.18 producers on early exit.

    SDK 1.18 ResponseStream has no public aclose. The compatibility shim walks
    only its documented-in-source ownership fields and runs idempotent cleanup
    hooks; it does not finalize an incomplete response as success.
    """

    @classmethod
    async def close(cls, stream: object) -> None:
        """Release nested ResponseStreams and their underlying async generators.

        Args:
            stream: Native producer owned by the binding.
        """
        seen: set[int] = set()
        await cls._close(stream, seen)

    @classmethod
    async def _close(cls, stream: object, seen: set[int]) -> None:
        """Visit each producer once, closing inner generators before hooks.

        Args:
            stream: Producer node.
            seen: Identities already processed.
        """
        if id(stream) in seen:
            return
        seen.add(id(stream))
        for name in ("_iterator", "_inner_stream", "_stream_source", "_inner_stream_source"):
            child = getattr(stream, name, None)
            if child is not None:
                await cls._close(child, seen)
        if inspect.iscoroutine(stream):
            stream.close()
        close: Callable[[], Any] | None = getattr(stream, "aclose", None)
        if close is not None:
            await close()
        cleanup: Callable[[], Any] | None = getattr(stream, "_run_cleanup_hooks", None)
        if cleanup is not None:
            await cleanup()
