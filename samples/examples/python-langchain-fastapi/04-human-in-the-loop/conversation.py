"""BYOA conversation composition for the managed LangGraph worker."""

from __future__ import annotations

import hashlib
from collections.abc import AsyncIterator, Sequence
from typing import Any
from uuid import uuid4

from ygo74.agent_runtime.domains.auth.agent_principal import AgentPrincipal
from ygo74.agent_runtime.domains.contracts.agent_output import AgentOutput
from ygo74.agent_runtime.domains.contracts.stream_events import AgentStreamEvent
from ygo74.agent_runtime.domains.humanapproval.commands import ConfirmationCommand
from ygo74.agent_runtime.domains.humanapproval.confirmation import (
    ConfirmationDetail,
    ConfirmationPolicy,
    ConfirmationRequest,
)
from ygo74.agent_runtime.domains.humanapproval.pending_renderer import PendingConfirmationRenderer
from ygo74.agent_runtime.domains.humanapproval.tickets import (
    ConfirmationTicket,
    InMemoryPendingConfirmationStore,
)
from ygo74.agent_runtime.domains.security.user_context import UserContext
from ygo74.agent_runtime.domains.sessions.agent_conversation import (
    AgentConversation,
    ConversationPort,
)
from ygo74.agent_runtime.integrations.langchain import (
    LangGraphPendingApproval,
    LangGraphSession,
)

from mcp_mslearn_tool import mslearn_mcp_search
from solution_architect_agent import OPERATIONS, build_agent


class ArchitectRuntime:
    """Own the LangGraph agent and caller identity for one conversation."""

    user: UserContext
    agent: Any

    def __init__(self, user: UserContext, agent: Any) -> None:
        """Store the graph and authenticated user used by the conversation."""
        self.user = user
        self.agent = agent

    async def aclose(self) -> None:
        """Release conversation-owned resources; this sample has no external scope."""


class TicketApprovalResolver:
    """Turn graph interrupts into shared runtime tickets, then decline the graph call."""

    _store: InMemoryPendingConfirmationStore
    _user: UserContext
    _conversation_id: str

    def __init__(
        self,
        store: InMemoryPendingConfirmationStore,
        user: UserContext,
        *,
        conversation_id: str,
    ) -> None:
        """Bind ticket creation to one verified user and conversation."""
        self._store = store
        self._user = user
        self._conversation_id = conversation_id

    def will_question(self, pending: tuple[LangGraphPendingApproval, ...]) -> bool:
        """Report that tickets are returned in the response without holding the turn."""
        del pending
        return False

    async def resolve(
        self,
        pending: tuple[LangGraphPendingApproval, ...],
    ) -> Sequence[dict[str, str]]:
        """Issue one ticket per action and decline all calls in their original order."""
        decisions: list[dict[str, str]] = []
        for approval in pending:
            if approval.tool_name != OPERATIONS[0].tool_name:
                raise ValueError("the graph requested an operation outside its admitted tool surface")
            self._store.issue(
                ConfirmationTicket.issue(
                    subject=self._user.user_id,
                    conversation_id=self._conversation_id,
                    tool_name=approval.tool_name,
                    request=self._request_for(approval),
                    arguments=approval.arguments,
                )
            )
            decisions.append(approval.answer(approved=False))
        return decisions

    def _request_for(self, approval: LangGraphPendingApproval) -> ConfirmationRequest:
        """Describe the exact search question stored on the confirmation ticket."""
        query = str(approval.arguments.get("query", "")).strip()
        return ConfirmationRequest(
            request_id=f"req-{uuid4().hex}",
            operation=OPERATIONS[0],
            requested_for=self._user.user_id,
            title="Send this question to Microsoft Learn",
            target=approval.tool_name,
            details=(ConfirmationDetail(label="Query", value=query),) if query else (),
        )


class TicketRunner:
    """Run a confirmed search from the exact arguments retained by its ticket."""

    _store: InMemoryPendingConfirmationStore
    _user: UserContext
    _conversation_id: str

    def __init__(
        self,
        store: InMemoryPendingConfirmationStore,
        user: UserContext,
        *,
        conversation_id: str,
    ) -> None:
        """Bind ticket claims and tool invocation to one user conversation."""
        self._store = store
        self._user = user
        self._conversation_id = conversation_id

    async def run(self, command: ConfirmationCommand) -> str:
        """Consume a ticket and run its stored search only after explicit confirmation."""
        ticket = self._store.claim(
            command.ticket_id,
            subject=self._user.user_id,
            conversation_id=self._conversation_id,
        )
        if not command.approves:
            return "Cancelled. Nothing was sent."
        if ticket.tool_name != OPERATIONS[0].tool_name:
            raise ValueError("the confirmation ticket names an operation outside this runner's tool surface")
        self._user.require_permission(OPERATIONS[0].required_permission)
        result = await mslearn_mcp_search.ainvoke(dict(ticket.arguments))
        return result if isinstance(result, str) else str(result)


class ArchitectSession:
    """Adapt the existing graph to the runtime's native LangGraph session contract."""

    _binding: LangGraphSession

    def __init__(self, runtime: ArchitectRuntime, resolver: TicketApprovalResolver, thread_id: str) -> None:
        """Bind the graph, approval resolver and server-derived checkpoint partition."""
        self._binding = LangGraphSession(runtime.agent, thread_id=thread_id, resolver=resolver)

    async def ask(self, message: str) -> str:
        """Answer one user message through the native LangGraph binding."""
        return await self._binding.ask(message)

    async def ask_output(self, message: str) -> AgentOutput:
        """Return typed output for the runtime conversation engine."""
        return await self._binding.ask_output(message)

    def ask_stream(self, message: str) -> AsyncIterator[AgentStreamEvent]:
        """Return the native typed event stream for this agent turn."""
        return self._binding.ask_stream(message)


ArchitectConversation = AgentConversation[ArchitectRuntime, ArchitectSession]


class ArchitectConversationFactory:
    """Compose a graph session, ticket store and runner for each verified conversation."""

    _policy: ConfirmationPolicy

    def __init__(self, policy: ConfirmationPolicy) -> None:
        """Store the application-owned policy used to build each caller's graph."""
        self._policy = policy

    async def build(self, principal: AgentPrincipal, conversation_id: str) -> ConversationPort:
        """Build one runtime conversation scoped to an authenticated principal."""
        user = UserContext(
            user_id=principal.subject,
            session_id=conversation_id,
            permissions=frozenset({OPERATIONS[0].required_permission}),
        )
        runtime = ArchitectRuntime(user, build_agent(self._policy, user))
        store = InMemoryPendingConfirmationStore()
        resolver = TicketApprovalResolver(store, user, conversation_id=conversation_id)
        session = ArchitectSession(runtime, resolver, _thread_id(principal, conversation_id))
        runner = TicketRunner(store, user, conversation_id=conversation_id)
        return AgentConversation(
            runtime=runtime,
            session=session,
            store=store,
            runner=runner,
            conversation_id=conversation_id,
            renderer=PendingConfirmationRenderer(),
        )


def _thread_id(principal: AgentPrincipal, conversation_id: str) -> str:
    """Hash caller and conversation fields into a stable private checkpoint key."""
    parts = (principal.subject, conversation_id)
    material = "".join(f"{len(part)}:{part}" for part in parts)
    return hashlib.sha256(material.encode("utf-8")).hexdigest()
