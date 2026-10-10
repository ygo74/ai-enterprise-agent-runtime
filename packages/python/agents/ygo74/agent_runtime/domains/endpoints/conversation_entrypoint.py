"""Generic transport binding for typed conversation engines."""

from collections.abc import AsyncGenerator, AsyncIterator, Mapping
from contextlib import aclosing
from typing import Any, Protocol
from uuid import uuid4

from ygo74.agent_runtime.domains.contracts.conversation import (
    AgentReply,
    ConversationTurn,
)
from ygo74.agent_runtime.domains.contracts.exchange_models import (
    StandardExchangeResponse,
)
from ygo74.agent_runtime.domains.contracts.stream_events import AgentStreamEvent
from ygo74.agent_runtime.domains.endpoints.conversation_payloads import (
    DEFAULT_CONVERSATION,
    AgentReplyRenderer,
    ConversationPayloadReader,
)
from ygo74.agent_runtime.domains.sessions.continuity_diagnostics import (
    ContinuityDiagnostics,
)


class StreamingConversationEngine(Protocol):
    """Framework-independent transport capabilities."""

    async def respond(self, turn: ConversationTurn) -> AgentReply:
        """Return a non-stream reply.

        Args:
            turn: Verified typed turn.
        """
        ...

    def stream(self, turn: ConversationTurn) -> AsyncGenerator[AgentStreamEvent]:
        """Produce native streaming output.

        Args:
            turn: Verified typed turn.
        """
        ...


class ConversationEntrypoint:
    """Select response mode only at the transport boundary.

    Args:
        engine: Typed conversation orchestration.
        require_email: Identity requirement declared by the agent.
        default_conversation: Fallback handle within the verified caller.
    """

    def __init__(self, engine: StreamingConversationEngine, *, require_email: bool = False,
                 default_conversation: str = DEFAULT_CONVERSATION) -> None:
        """Retain the engine and shared payload adapters.

        Args:
            engine: Conversation implementation.
            require_email: Declarative verified identity requirement.
            default_conversation: Default caller-scoped handle.
        """
        self._engine = engine
        self._reader = ConversationPayloadReader(require_email=require_email, default_conversation=default_conversation)
        self._renderer = AgentReplyRenderer()

    async def __call__(self, payload: Mapping[str, Any]) -> StandardExchangeResponse | AsyncIterator[AgentStreamEvent]:
        """Invoke the actual native mode requested by the transport.

        Args:
            payload: Normalized transport payload containing verified auth_context.
        """
        turn = self.to_turn(payload)
        correlation = str(payload.get("request_id") or uuid4().hex)
        if payload.get("stream") is True:
            return self._correlated_stream(turn, correlation)
        with ContinuityDiagnostics.request(correlation):
            return self.to_payload(payload, await self._engine.respond(turn))

    async def _correlated_stream(self, turn: ConversationTurn, correlation: str) -> AsyncGenerator[AgentStreamEvent]:
        """Scope each pull and cleanup, never leaking context across consumer yields.

        Args:
            turn: Verified latest-user turn.
            correlation: Transport request correlation, fingerprinted before use.
        """
        producer = self._engine.stream(turn)
        try:
            while True:
                with ContinuityDiagnostics.request(correlation):
                    try:
                        event = await anext(producer)
                    except StopAsyncIteration:
                        return
                yield event
        finally:
            with ContinuityDiagnostics.request(correlation):
                async with aclosing(producer):
                    pass

    def to_turn(self, payload: Mapping[str, Any]) -> ConversationTurn:
        """Translate transport input once.

        Args:
            payload: Normalized request from the authenticated endpoint.
        """
        return self._reader.to_turn(payload)

    def to_payload(self, payload: Mapping[str, Any], reply: AgentReply) -> StandardExchangeResponse:
        """Render a typed reply without losing native usage or errors.

        Args:
            payload: Request correlation and route metadata.
            reply: Completed conversation reply.
        """
        return self._renderer.to_payload(payload, reply)
