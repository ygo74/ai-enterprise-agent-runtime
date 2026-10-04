"""Reusable state and HTTP turn handling for an agent conversation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Generic, Protocol, TypeVar

from ygo74.agent_runtime.domains.contracts.conversation import (
    AgentReply,
    ConversationTurn,
)
from ygo74.agent_runtime.domains.humanapproval.commands import (
    ConfirmationCommand,
    ConfirmationCommandParser,
)
from ygo74.agent_runtime.domains.humanapproval.pending_renderer import (
    PendingConfirmationRenderer,
)
from ygo74.agent_runtime.domains.humanapproval.tickets import (
    ConfirmationTicket,
    PendingConfirmationStore,
    UnknownTicketError,
)
from ygo74.agent_runtime.domains.security.user_context import UserContext
from ygo74.agent_runtime.domains.sessions.conversation_cache import (
    ConversationRuntimeCache,
)

_UNKNOWN_TICKET = (
    "That confirmation is not awaiting an answer. It may have been answered "
    "already, or it may have expired. Ask again and a new one will be offered."
)


class AgentRuntimePort(Protocol):
    """The application runtime resources a conversation container needs."""

    @property
    def user(self) -> UserContext:
        """Identity associated with this conversation."""
        ...

    async def aclose(self) -> None:
        """Release resources held for this conversation."""
        ...


class AgentSessionPort(Protocol):
    """The framework adapter operation used to answer a turn."""

    async def ask(self, message: str) -> str:
        """Answer one user message."""
        ...


class ConfirmationRunnerPort(Protocol):
    """Executes a confirmation ticket claimed from the conversation."""

    async def run(self, command: ConfirmationCommand) -> str:
        """Execute the operation represented by a confirmed ticket."""
        ...


class ConversationPort(Protocol):
    """Operations the generic HTTP engine needs from a conversation."""

    @property
    def runtime(self) -> AgentRuntimePort:
        """Application runtime associated with this conversation."""
        ...

    @property
    def session(self) -> AgentSessionPort:
        """Framework adapter that answers an ordinary turn."""
        ...

    @property
    def runner(self) -> ConfirmationRunnerPort:
        """Runner that executes a claimed confirmation ticket."""
        ...

    @property
    def conversation_id(self) -> str:
        """Identifier used to scope pending confirmations."""
        ...

    async def aclose(self) -> None:
        """Release resources held by the conversation."""
        ...

    def waiting(self) -> tuple[str, ...]:
        """Return confirmation identifiers waiting for an answer."""
        ...

    def describe_pending(self) -> str:
        """Render the confirmations waiting for an answer."""
        ...


RuntimeT = TypeVar("RuntimeT", bound=AgentRuntimePort)
SessionT = TypeVar("SessionT", bound=AgentSessionPort)
ConversationT = TypeVar("ConversationT", bound=ConversationPort)


@dataclass(frozen=True, slots=True)
class AgentConversation(Generic[RuntimeT, SessionT]):
    """Framework-neutral state and resources for one caller's conversation."""

    runtime: RuntimeT
    session: SessionT
    store: PendingConfirmationStore
    runner: ConfirmationRunnerPort
    conversation_id: str
    renderer: PendingConfirmationRenderer

    async def aclose(self) -> None:
        """Release the application runtime and its open connections."""
        await self.runtime.aclose()

    def waiting(self) -> tuple[str, ...]:
        """Return identifiers of operations described but not performed."""
        return tuple(ticket.ticket_id for ticket in self._pending())

    def describe_pending(self) -> str:
        """Render the tickets from application-owned confirmation details."""
        return self.renderer.render(self._pending())

    def _pending(self) -> tuple[ConfirmationTicket, ...]:
        """Return pending tickets scoped to this caller and conversation."""
        return self.store.pending(
            subject=self.runtime.user.user_id,
            conversation_id=self.conversation_id,
        )


class HttpConversationEngine(Generic[ConversationT]):
    """Run a conversation turn with shared confirmation and reply handling."""

    def __init__(
        self,
        conversations: ConversationRuntimeCache[ConversationT],
        parser: ConfirmationCommandParser | None = None,
        *,
        unknown_ticket_message: str = _UNKNOWN_TICKET,
    ) -> None:
        self._conversations = conversations
        self._parser = parser or ConfirmationCommandParser()
        self._unknown_ticket_message = unknown_ticket_message

    async def respond(self, turn: ConversationTurn) -> AgentReply:
        """Answer one turn, handling confirmation commands before the agent."""
        async with self._conversations.lease(turn.principal, turn.conversation_id) as conversation:
            command = self._parser.parse(turn.message)
            if command is not None:
                return await self._honour(conversation, command)

            return self._reply(conversation, await conversation.session.ask(turn.message))

    async def _honour(self, conversation: ConversationT, command: ConfirmationCommand) -> AgentReply:
        """Run a claimed ticket or safely report that it is no longer pending."""
        try:
            text = await conversation.runner.run(command)
        except UnknownTicketError:
            text = self._unknown_ticket_message
        return self._reply(conversation, text)

    @staticmethod
    def _reply(conversation: ConversationPort, text: str) -> AgentReply:
        """Attach the pending confirmations to the agent's answer."""
        return AgentReply(
            text=text + conversation.describe_pending(),
            pending_confirmations=conversation.waiting(),
        )
