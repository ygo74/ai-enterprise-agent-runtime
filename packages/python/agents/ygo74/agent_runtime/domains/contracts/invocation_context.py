"""Carry trusted identity and correlation through one agent invocation."""

from __future__ import annotations

from collections.abc import AsyncIterator, Iterator
from contextlib import aclosing, contextmanager
from contextvars import ContextVar, Token
from dataclasses import dataclass, field, replace
from typing import TypeVar

from ygo74.agent_runtime.domains.auth.agent_principal import AgentPrincipal
from ygo74.agent_runtime.domains.auth.tokens import AccessToken
from ygo74.agent_runtime.domains.contracts.conversation import ConversationTurn

_ItemT = TypeVar("_ItemT")
_current_invocation: ContextVar[AgentInvocationContext | None] = ContextVar(
    "agent_runtime_invocation_context", default=None
)


@dataclass(frozen=True, slots=True, repr=False)
class AgentInvocationContext:
    """Trusted identity and correlation values available during one invocation.

    Args:
        principal (AgentPrincipal | None): Authenticated, credential-free caller identity.
        request_id (str): Runtime correlation identifier for the current turn.
        conversation_id (str): Caller-scoped conversation or session identifier.
        subject_token (AccessToken | None): Verified inbound token retained for delegated authentication.
    """

    principal: AgentPrincipal | None = None
    request_id: str = ""
    conversation_id: str = ""
    subject_token: AccessToken | None = field(default=None, repr=False, compare=False)

    @classmethod
    def for_turn(
        cls,
        turn: ConversationTurn,
        request_id: str,
        subject_token: AccessToken | None = None,
    ) -> AgentInvocationContext:
        """Create invocation context from a verified conversation turn.

        Args:
            turn (ConversationTurn): Typed turn produced by the authenticated payload reader.
            request_id (str): Correlation identifier assigned by the endpoint.
            subject_token (AccessToken | None): Verified inbound token, when JWT auth was used.
        """
        return cls(
            principal=turn.principal,
            request_id=request_id,
            conversation_id=turn.conversation_id,
            subject_token=subject_token,
        )

    def with_turn(
        self, turn: ConversationTurn, request_id: str
    ) -> AgentInvocationContext:
        """Enrich existing context with typed identity and conversation routing.

        Args:
            turn (ConversationTurn): Typed turn produced by the authenticated payload reader.
            request_id (str): Correlation identifier assigned by the endpoint.
        """
        return replace(
            self,
            principal=turn.principal,
            request_id=request_id,
            conversation_id=turn.conversation_id,
        )

    def __repr__(self) -> str:
        """Describe available context without exposing identity or token values."""
        return (
            f"{type(self).__name__}(principal_present={self.principal is not None}, "
            f"request_id_present={bool(self.request_id)}, conversation_id_present={bool(self.conversation_id)}, "
            f"subject_token_present={self.subject_token is not None})"
        )


class AgentInvocationContextScope:
    """Bind an invocation context to the current asynchronous execution."""

    @staticmethod
    def current() -> AgentInvocationContext | None:
        """Return the context inherited by the current async task."""
        return _current_invocation.get()

    @staticmethod
    @contextmanager
    def bind(context: AgentInvocationContext) -> Iterator[None]:
        """Set and restore the current invocation context around one operation.

        Args:
            context (AgentInvocationContext): Trusted identity and correlation values for an invocation.
        """
        token: Token[AgentInvocationContext | None] = _current_invocation.set(context)
        try:
            yield
        finally:
            _current_invocation.reset(token)

    @staticmethod
    async def iterate(
        source: AsyncIterator[_ItemT],
        context: AgentInvocationContext,
    ) -> AsyncIterator[_ItemT]:
        """Pull and close a stream under its context without crossing yields.

        Args:
            source (AsyncIterator[_ItemT]): Stream whose work must inherit invocation context.
            context (AgentInvocationContext): Trusted identity and correlation values for the invocation.
        """
        try:
            while True:
                with AgentInvocationContextScope.bind(context):
                    try:
                        item = await anext(source)
                    except StopAsyncIteration:
                        return
                yield item
        finally:
            with AgentInvocationContextScope.bind(context):
                async with aclosing(source):
                    pass
