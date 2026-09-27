"""Generic HTTP conversation behavior independent of agent frameworks."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta

from ygo74.agent_runtime.domains.auth.agent_principal import AgentPrincipal
from ygo74.agent_runtime.domains.contracts.conversation import ConversationTurn
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
