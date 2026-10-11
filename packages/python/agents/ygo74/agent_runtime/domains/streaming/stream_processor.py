"""Provider-independent consumption, lifecycle validation, cancellation and closure."""

import inspect
import logging
from collections.abc import AsyncIterable, AsyncIterator, Awaitable, Callable
from typing import Protocol, cast

from ygo74.agent_runtime.domains.contracts.agent_output import (
    AgentOutput,
    Termination,
    TerminationStatus,
)
from ygo74.agent_runtime.domains.contracts.error_envelope import ErrorEnvelope
from ygo74.agent_runtime.domains.contracts.stream_events import (
    AgentStreamEvent,
    ContentEnd,
    ContentEvent,
    ContentStart,
    TerminalEvent,
    UsageEvent,
)
from ygo74.agent_runtime.domains.handlers.handler_protocol import (
    AgentInvocation,
    AgentResult,
)
from ygo74.agent_runtime.domains.mapping.output_normalizer import (
    OutputNormalizer,
    OutputValidationError,
)
from ygo74.agent_runtime.domains.mapping.output_projector import (
    ContentSupport,
    FilterReason,
    OutputProjectionError,
    OutputProtocol,
    ProjectionContext,
)
from ygo74.agent_runtime.domains.streaming.anthropic_stream import (
    AnthropicStreamProjector,
)
from ygo74.agent_runtime.domains.streaming.chat_completions_stream import (
    ChatCompletionsStreamProjector,
)
from ygo74.agent_runtime.domains.streaming.responses_stream import (
    ResponsesStreamProjector,
)
from ygo74.agent_runtime.domains.streaming.sse_encoder import SseEncoder
from ygo74.agent_runtime.domains.streaming.stream_projector import StreamProjector
from ygo74.agent_runtime.domains.streaming.stream_state import StreamState

logger = logging.getLogger(__name__)
__all__ = ["AgentInvocation", "AgentResult", "StreamProcessor"]


class AsyncCloseable(Protocol):
    """Protocol for asynchronous event sources that must be closed on completion, cancellation, or failure.
    """
    def aclose(self) -> Awaitable[None]:
        """Close asynchronously typed stream events and release resources owned by the operation.
        """
        ...


class StreamProcessor:
    """Validates a neutral event sequence, projects events for the selected protocol, and closes its producer on every terminal path.
    """
    async def stream(
        self, result: object, context: ProjectionContext
    ) -> AsyncIterator[str]:
        """Stream typed stream events validated events while preserving lifecycle and cleanup guarantees.

        Args:
            result (object): The operation result to validate, project, or return.
            context (ProjectionContext): The execution context carrying identity and correlated metadata.
        """
        state = StreamState(context)
        projector = self._projector(context.protocol)
        encoder = SseEncoder()
        iterator: AsyncIterator[AgentStreamEvent] | None = None
        source: object = result
        closed = False
        try:
            for wire in projector.start(state):
                yield encoder.encode(wire)
            if inspect.isawaitable(source):
                source = await source
            if isinstance(source, AsyncIterable):
                iterator = cast(AsyncIterable[AgentStreamEvent], source).__aiter__()
            else:
                output = OutputNormalizer().normalize(
                    source, request_id=context.request_id
                )
                iterator = self._events(output, context.protocol)
            async for event in iterator:
                if isinstance(event, ContentEvent):
                    events: tuple[AgentStreamEvent, ...] = (
                        ContentStart(event.content_id, event.content),
                        ContentEnd(event.content_id),
                    )
                else:
                    events = (event,)
                for normalized in events:
                    state.apply(normalized)
                    if isinstance(normalized, TerminalEvent):
                        await self._close(iterator, context)
                        if source is not iterator:
                            await self._close(source, context)
                        closed = True
                        if state.contents and all(
                            not entry.supported for entry in state.contents.values()
                        ):
                            ContentSupport.log(
                                context, state.output(), FilterReason.EMPTY_OUTPUT
                            )
                        for wire in projector.finish(normalized.termination, state):
                            yield encoder.encode(wire)
                        if projector.done_marker:
                            yield encoder.done()
                        return
                    for wire in projector.project(normalized, state):
                        yield encoder.encode(wire)
            raise OutputValidationError("Agent stream ended without TerminalEvent")
        except Exception as exc:  # noqa: BLE001 - the producer is a developer-supplied execution boundary
            if not closed:
                await self._close(iterator, context)
                if source is not iterator:
                    await self._close(source, context)
                closed = True
            invalid = isinstance(exc, OutputValidationError)
            error = ErrorEnvelope(
                code="invalid_agent_output"
                if invalid
                else getattr(exc, "code", "agent_execution_error"),
                category="validation"
                if invalid
                else getattr(exc, "category", "handler_execution"),
                message=str(exc)
                if invalid or isinstance(exc, OutputProjectionError)
                else "Agent stream execution failed",
            )
            logger.warning(
                "Agent stream failed request_id=%s route_key=%s protocol=%s code=%s",
                context.request_id,
                context.route_key,
                context.protocol,
                error.code,
            )
            for wire in projector.finish(
                Termination(TerminationStatus.FAILED, error=error), state
            ):
                yield encoder.encode(wire)
            if projector.done_marker:
                yield encoder.done()
        finally:
            if not closed:
                await self._close(iterator, context)
                if source is not iterator:
                    await self._close(source, context)

    @staticmethod
    async def _events(
        output: AgentOutput, protocol: OutputProtocol
    ) -> AsyncIterator[AgentStreamEvent]:
        """Validate and project source events while guaranteeing producer closure on every exit path.

        Args:
            output (AgentOutput): Typed agent output being validated, filtered, or projected.
            protocol (OutputProtocol): Target provider protocol used to select projection rules.
        """
        if (
            protocol == OutputProtocol.ANTHROPIC_MESSAGES
            and output.usage is None
            and output.termination.status == TerminationStatus.FAILED
        ):
            yield TerminalEvent(output.termination)
            return
        if output.usage is not None:
            yield UsageEvent(output.usage)
        for index, content in enumerate(output.contents):
            yield ContentEvent(f"content-{index}", content)
        yield TerminalEvent(output.termination)

    @staticmethod
    async def _close(source: object, context: ProjectionContext) -> None:
        """Close an async producer when it supports explicit cleanup, suppressing cleanup errors only after preserving the primary outcome.

        Args:
            source (object): The source value being read, validated, or converted.
            context (ProjectionContext): The execution context carrying identity and correlated metadata.
        """
        if inspect.iscoroutine(source):
            source.close()
            return
        if not callable(getattr(source, "aclose", None)):
            return
        try:
            await cast(AsyncCloseable, source).aclose()
        except Exception:  # noqa: BLE001 - cleanup must not replace the original terminal/cancellation
            logger.warning(
                "Agent producer close failed request_id=%s route_key=%s",
                context.request_id,
                context.route_key,
            )

    @staticmethod
    def _projector(protocol: OutputProtocol) -> StreamProjector:
        """Select the provider projector matching the response protocol.

        Args:
            protocol (OutputProtocol): Target provider protocol used to select projection rules.
        """
        projectors: dict[OutputProtocol, Callable[[], StreamProjector]] = {
            OutputProtocol.CHAT_COMPLETIONS: ChatCompletionsStreamProjector,
            OutputProtocol.RESPONSES: ResponsesStreamProjector,
            OutputProtocol.ANTHROPIC_MESSAGES: AnthropicStreamProjector,
        }
        return projectors[protocol]()
