"""Reusable state and HTTP turn handling for an agent conversation."""

from __future__ import annotations

from collections.abc import AsyncGenerator
from contextlib import aclosing
from dataclasses import dataclass, replace
from typing import Generic, Protocol, TypeVar, runtime_checkable
from uuid import uuid4

from ygo74.agent_runtime.domains.contracts.agent_output import (
    AgentOutput,
    TerminationStatus,
    TextContent,
)
from ygo74.agent_runtime.domains.contracts.conversation import (
    AgentReply,
    ConversationTurn,
)
from ygo74.agent_runtime.domains.contracts.stream_events import (
    AgentStreamEvent,
    ContentEvent,
    TerminalEvent,
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
        """Answer one user message.

        Args:
            message (str): Framework message or protocol message being converted.
        """
        ...


class ConfirmationRunnerPort(Protocol):
    """Executes a confirmation ticket claimed from the conversation."""
    async def run(self, command: ConfirmationCommand) -> str:
        """Execute the operation represented by a confirmed ticket.

        Args:
            command (ConfirmationCommand): Requested operation that must pass the authorization gate.
        """
        ...


@runtime_checkable
class StreamingSessionPort(Protocol):
    """Optional native streaming capability of a conversation session."""

    def ask_stream(self, message: str) -> AsyncGenerator[AgentStreamEvent]:
        """Start a native streamed invocation.

        Args:
            message: Latest user text.
        """
        ...


@runtime_checkable
class OutputSessionPort(Protocol):
    """Optional typed output capability preserving usage and termination."""

    async def ask_output(self, message: str) -> AgentOutput:
        """Start a native non-stream invocation.

        Args:
            message: Latest user text.
        """
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
    """Framework-neutral state and resources for one caller's conversation.

    Args:
        runtime (RuntimeT): Agent runtime instance used to handle the conversation.
        session (SessionT): Conversation session associated with the runtime instance.
        store (PendingConfirmationStore): Persistence service used to retain state across requests.
        runner (ConfirmationRunnerPort): Port that resumes a framework run after an approval decision.
        conversation_id (str): Conversation identity used to select session state for this caller.
        renderer (PendingConfirmationRenderer): Component that formats approval state for the user.
    """
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
    """Run a conversation turn with shared confirmation and reply handling.

    Args:
        conversations (ConversationRuntimeCache[ConversationT]): Cache of conversation runtimes indexed by caller and conversation ID.
        parser (ConfirmationCommandParser | None): Optional parser for approval commands in user messages.
        unknown_ticket_message (str): Text returned when the requested approval ticket is unknown.
    """
    def __init__(
        self,
        conversations: ConversationRuntimeCache[ConversationT],
        parser: ConfirmationCommandParser | None = None,
        *,
        unknown_ticket_message: str = _UNKNOWN_TICKET,
    ) -> None:
        """Initialize the instance runtime data with supplied collaborators and configuration.

        Args:
            conversations (ConversationRuntimeCache[ConversationT]): Cache of conversation runtimes indexed by caller and conversation ID.
            parser (ConfirmationCommandParser | None): Optional parser for approval commands in user messages.
            unknown_ticket_message (str): Text returned when the requested approval ticket is unknown.
        """
        self._conversations = conversations
        self._parser = parser or ConfirmationCommandParser()
        self._unknown_ticket_message = unknown_ticket_message

    async def respond(self, turn: ConversationTurn) -> AgentReply:
        """Answer one turn, handling confirmation commands before the agent.

        Args:
            turn (ConversationTurn): Conversation turn whose request and response are added to session history.
        """
        async with self._conversations.turn(turn.principal, turn.conversation_id) as conversation:
            command = self._parser.parse(turn.message)
            if command is not None:
                return await self._honour(conversation, command)

            if isinstance(conversation.session, OutputSessionPort):
                output = await conversation.session.ask_output(turn.message)
                if output.termination.status is TerminationStatus.FAILED:
                    await self._conversations.invalidate(turn.principal, turn.conversation_id)
                text = "".join(item.text for item in output.contents if isinstance(item, TextContent))
                reply = self._reply(conversation, text)
                suffix = conversation.describe_pending()
                contents = output.contents + ((TextContent(suffix),) if suffix else ())
                return replace(reply, output=replace(output, contents=contents))
            return self._reply(conversation, await conversation.session.ask(turn.message))

    async def stream(self, turn: ConversationTurn) -> AsyncGenerator[AgentStreamEvent]:
        """Release a completed turn before exposing its terminal to the transport.

        Args:
            turn: Typed verified caller, conversation and latest text.
        """
        terminal: TerminalEvent | None = None
        async with (
            self._conversations.turn(turn.principal, turn.conversation_id) as conversation,
            aclosing(self._stream_turn(conversation, turn)) as stream,
        ):
            async for event in stream:
                if isinstance(event, TerminalEvent):
                    terminal = event
                else:
                    yield event
        if terminal is None:
            raise ValueError("session stream ended without a terminal")
        # Transports close their source immediately after a terminal. Yielding
        # inside cache.turn would inject GeneratorExit and invalidate valid history.
        yield terminal

    async def _stream_turn(self, conversation: ConversationT, turn: ConversationTurn) -> AsyncGenerator[AgentStreamEvent]:
        """Finish native execution and pending rendering while the turn is leased.

        Args:
            conversation: Pinned caller-scoped resources.
            turn: Verified latest-user turn.
        """
        command = self._parser.parse(turn.message)
        if command is not None:
            reply = await self._honour(conversation, command)
            if reply.text:
                yield ContentEvent(uuid4().hex, TextContent(reply.text))
            yield TerminalEvent()
            return
        if not isinstance(conversation.session, StreamingSessionPort):
            raise TypeError("conversation session does not support native streaming")
        terminal: TerminalEvent | None = None
        async with aclosing(conversation.session.ask_stream(turn.message)) as stream:
            async for event in stream:
                if isinstance(event, TerminalEvent):
                    if terminal is not None:
                        raise ValueError("session emitted multiple terminals")
                    terminal = event
                else:
                    if terminal is not None:
                        raise ValueError("session emitted content after terminal")
                    yield event
        if terminal is None:
            raise ValueError("session stream ended without a terminal")
        pending = conversation.describe_pending()
        if pending:
            yield ContentEvent(uuid4().hex, TextContent(pending))
        if terminal.termination.status is TerminationStatus.FAILED:
            await self._conversations.invalidate(turn.principal, turn.conversation_id)
        yield terminal

    async def _honour(self, conversation: ConversationT, command: ConfirmationCommand) -> AgentReply:
        """Run a claimed ticket or safely report that it is no longer pending.

        Args:
            conversation (ConversationT): Conversation instance whose state is being updated.
            command (ConfirmationCommand): Requested operation that must pass the authorization gate.
        """
        try:
            text = await conversation.runner.run(command)
        except UnknownTicketError:
            text = self._unknown_ticket_message
        return self._reply(conversation, text)

    @staticmethod
    def _reply(conversation: ConversationPort, text: str) -> AgentReply:
        """Attach the pending confirmations to the agent's answer.

        Args:
            conversation (ConversationPort): Conversation instance whose state is being updated.
            text (str): Text value or fragment carried by this content item.
        """
        return AgentReply(
            text=text + conversation.describe_pending(),
            pending_confirmations=conversation.waiting(),
        )
