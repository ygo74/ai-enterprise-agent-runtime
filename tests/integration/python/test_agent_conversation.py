"""Generic HTTP conversation behavior independent of agent frameworks."""

from __future__ import annotations

import asyncio
from dataclasses import replace
from datetime import UTC, datetime, timedelta

import pytest
from ygo74.agent_runtime.domains.auth.agent_principal import AgentPrincipal
from ygo74.agent_runtime.domains.contracts.agent_output import (
    Termination,
    TerminationStatus,
    TextContent,
)
from ygo74.agent_runtime.domains.contracts.conversation import ConversationTurn
from ygo74.agent_runtime.domains.contracts.stream_events import (
    ContentEvent,
    TerminalEvent,
)
from ygo74.agent_runtime.domains.humanapproval.commands import ConfirmationCommand
from ygo74.agent_runtime.domains.humanapproval.confirmation import ConfirmationRequest
from ygo74.agent_runtime.domains.humanapproval.pending_renderer import (
    PendingConfirmationRenderer,
)
from ygo74.agent_runtime.domains.humanapproval.tickets import (
    ConfirmationTicket,
    InMemoryPendingConfirmationStore,
    UnknownTicketError,
)
from ygo74.agent_runtime.domains.security.operations import (
    OperationType,
    RiskLevel,
    ToolOperationDescriptor,
)
from ygo74.agent_runtime.domains.security.permissions import Permission
from ygo74.agent_runtime.domains.security.user_context import UserContext
from ygo74.agent_runtime.domains.sessions.agent_conversation import (
    AgentConversation,
    HttpConversationEngine,
)
from ygo74.agent_runtime.domains.sessions.conversation_cache import (
    ConversationRuntimeCache,
)

ADA = AgentPrincipal(subject="ada", email="ada@example.test")


class FakeRuntime:
    def __init__(self, subject: str, session_id: str) -> None:
        self.user = UserContext(user_id=subject, session_id=session_id)
        self.closed = False

    async def aclose(self) -> None:
        self.closed = True


class FakeSession:
    def __init__(self) -> None:
        self.messages: list[str] = []

    async def ask(self, message: str) -> str:
        self.messages.append(message)
        return f"answered: {message}"


class FakeRunner:
    def __init__(self) -> None:
        self.commands: list[ConfirmationCommand] = []

    async def run(self, command: ConfirmationCommand) -> str:
        self.commands.append(command)
        if command.ticket_id != "cfm-abcdef":
            raise UnknownTicketError(command.ticket_id)
        return "confirmed operation ran"


class ConversationFactory:
    def __init__(self) -> None:
        self.built: list[AgentConversation[FakeRuntime, FakeSession]] = []
        self.runners: list[FakeRunner] = []

    async def build(self, principal: AgentPrincipal, conversation_id: str) -> AgentConversation[FakeRuntime, FakeSession]:
        runtime = FakeRuntime(principal.subject, conversation_id)
        runner = FakeRunner()
        conversation = AgentConversation(
            runtime=runtime,
            session=FakeSession(),
            store=InMemoryPendingConfirmationStore(),
            runner=runner,
            conversation_id=conversation_id,
            renderer=PendingConfirmationRenderer(),
        )
        self.built.append(conversation)
        self.runners.append(runner)
        return conversation

    async def close(self, conversation: AgentConversation[FakeRuntime, FakeSession]) -> None:
        await conversation.aclose()


class StreamingSession(FakeSession):
    """Script neutral stream validation and finalization.

    Args:
        mode: Controlled normal, malformed or failed scenario.
    """

    def __init__(self, mode):
        """Retain the scenario.

        Args:
            mode: Controlled stream behavior.
        """
        super().__init__()
        self.mode = mode

    async def ask_stream(self, message):
        """Offer controlled neutral events.

        Args:
            message: Controlled latest user input.
        """
        self.messages.append(message)
        yield ContentEvent("text", TextContent("controlled"))
        if self.mode == "missing":
            return
        status = TerminationStatus.FAILED if self.mode == "failed" else TerminationStatus.SUCCESS
        yield TerminalEvent(Termination(status))
        if self.mode == "duplicate":
            yield TerminalEvent()
        if self.mode == "after":
            yield ContentEvent("late", TextContent("invalid late content"))


class StreamingFactory(ConversationFactory):
    """Compose the same neutral resources with a scripted stream session.

    Args:
        mode: Controlled stream scenario.
    """

    def __init__(self, mode):
        """Initialize the scenario builder.

        Args:
            mode: Controlled stream behavior.
        """
        super().__init__()
        self.mode = mode

    async def build(self, principal, conversation_id):
        """Replace only the neutral test session.

        Args:
            principal: Controlled verified caller.
            conversation_id: Caller-scoped handle.
        """
        conversation = await super().build(principal, conversation_id)
        conversation = replace(conversation, session=StreamingSession(self.mode))
        self.built[-1] = conversation
        return conversation


@pytest.mark.asyncio
@pytest.mark.parametrize("command", [False, True])
async def test_closing_at_completed_terminal_keeps_cached_conversation(command):
    """Transport-style close at terminal is normal, including confirmation commands.

    Args:
        command: Whether to exercise deterministic command routing.
    """
    factory = StreamingFactory("normal")
    cache = ConversationRuntimeCache(factory.build, factory.close)
    engine = HttpConversationEngine(cache)
    message = "CONFIRM cfm-abcdef" if command else "controlled"
    stream = engine.stream(ConversationTurn(ADA, "one", message))
    async for event in stream:
        if isinstance(event, TerminalEvent):
            break
    await stream.aclose()
    assert cache.live_conversations == 1
    async with cache.lease(ADA, "one") as conversation:
        assert conversation is factory.built[0]
        assert not conversation.runtime.closed
    await cache.aclose()


@pytest.mark.asyncio
@pytest.mark.parametrize("mode", ["missing", "duplicate", "after"])
async def test_malformed_stream_never_succeeds_or_keeps_state(mode):
    """Malformed termination invalidates the lease, never emits a success terminal.

    Args:
        mode: Controlled malformed event sequence.
    """
    factory = StreamingFactory(mode)
    cache = ConversationRuntimeCache(factory.build, factory.close)
    engine = HttpConversationEngine(cache)
    events = []
    with pytest.raises(ValueError):
        async for event in engine.stream(ConversationTurn(ADA, "one", "controlled")):
            events.append(event)
    assert not any(isinstance(event, TerminalEvent) for event in events)
    assert cache.live_conversations == 0 and factory.built[0].runtime.closed
    await cache.aclose()


@pytest.mark.asyncio
async def test_cancel_before_terminal_invalidates_but_native_failure_stays_failed():
    """Early close and failed terminals still retire unsafe state."""
    for mode in ("normal", "failed"):
        factory = StreamingFactory(mode)
        cache = ConversationRuntimeCache(factory.build, factory.close)
        engine = HttpConversationEngine(cache)
        stream = engine.stream(ConversationTurn(ADA, "one", "controlled"))
        await anext(stream)
        if mode == "failed":
            terminal = await anext(stream)
            assert isinstance(terminal, TerminalEvent)
            assert terminal.termination.status is TerminationStatus.FAILED
        await stream.aclose()
        assert cache.live_conversations == 0 and factory.built[0].runtime.closed
        await cache.aclose()


def _engine(factory: ConversationFactory) -> HttpConversationEngine[AgentConversation[FakeRuntime, FakeSession]]:
    cache = ConversationRuntimeCache(factory.build, factory.close)
    return HttpConversationEngine(cache)


def test_confirmation_command_is_handled_before_the_framework_session() -> None:
    async def scenario() -> None:
        factory = ConversationFactory()
        engine = _engine(factory)

        reply = await engine.respond(ConversationTurn(ADA, "thread-1", "CONFIRM cfm-abcdef"))

        conversation = factory.built[0]
        assert reply.text == "confirmed operation ran"
        assert not conversation.session.messages
        assert len(factory.runners[0].commands) == 1

    asyncio.run(scenario())


def test_an_unknown_confirmation_ticket_returns_a_safe_message() -> None:
    async def scenario() -> None:
        factory = ConversationFactory()
        engine = _engine(factory)

        reply = await engine.respond(ConversationTurn(ADA, "thread-1", "CONFIRM cfm-123456"))

        assert "not awaiting an answer" in reply.text
        assert not factory.built[0].session.messages

    asyncio.run(scenario())


def test_ordinary_turn_uses_the_framework_session_and_reuses_conversation() -> None:
    async def scenario() -> None:
        factory = ConversationFactory()
        engine = _engine(factory)

        first = await engine.respond(ConversationTurn(ADA, "thread-1", "hello"))
        second = await engine.respond(ConversationTurn(ADA, "thread-1", "again"))

        assert first.text == "answered: hello"
        assert second.text == "answered: again"
        assert len(factory.built) == 1
        assert factory.built[0].session.messages == ["hello", "again"]

    asyncio.run(scenario())


def test_conversation_carries_pending_ticket_ids_and_rendering() -> None:
    async def scenario() -> None:
        factory = ConversationFactory()
        engine = _engine(factory)
        await engine.respond(ConversationTurn(ADA, "thread-1", "hello"))
        conversation = factory.built[0]
        request = ConfirmationRequest(
            request_id="request-1",
            operation=ToolOperationDescriptor(
                tool_name="send_mail",
                operation_type=OperationType.WRITE,
                risk_level=RiskLevel.HIGH,
                required_permission=Permission("mail", "send"),
                confirmation_required_by_default=True,
            ),
            requested_for="ada",
            title="Send a message",
        )
        conversation.store.issue(
            ConfirmationTicket(
                ticket_id="cfm-fedcba",
                subject="ada",
                conversation_id="thread-1",
                tool_name="send_mail",
                request=request,
                arguments={},
                expires_at=datetime.now(UTC) + timedelta(minutes=5),
            )
        )

        reply = await engine.respond(ConversationTurn(ADA, "thread-1", "next"))

        assert reply.pending_confirmations == ("cfm-fedcba",)
        assert "Send a message" in reply.text
        assert "CONFIRM cfm-fedcba" in reply.text

    asyncio.run(scenario())
