"""Host a MAF tool behind the runtime's conversation-scoped approval tickets."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from agent_framework import Agent, ToolApprovalMiddleware, tool
from agent_framework.openai import OpenAIChatClient
from ygo74.agent_runtime.domains.auth.agent_principal import AgentPrincipal
from ygo74.agent_runtime.domains.auth.apikey_authenticator import StaticApiKeyUserResolver
from ygo74.agent_runtime.domains.auth.auth_context import ResolvedUser
from ygo74.agent_runtime.domains.auth.authentication_policy import AuthenticationPolicy
from ygo74.agent_runtime.domains.contracts.agent_definition import AgentDefinition
from ygo74.agent_runtime.domains.contracts.manifests import AgentManifest, SkillManifest
from ygo74.agent_runtime.domains.discovery.discovery_configuration import DiscoveryConfiguration
from ygo74.agent_runtime.domains.discovery.manifest_descriptor import (
    AdvertisedSecurity,
    AgentDescriptorFactory,
)
from ygo74.agent_runtime.domains.endpoints.hosting_factory import EndpointSurface
from ygo74.agent_runtime.domains.endpoints.managed_worker import ManagedAgentWorker, WorkerSettings
from ygo74.agent_runtime.domains.humanapproval.commands import ConfirmationCommand
from ygo74.agent_runtime.domains.humanapproval.confirmation import ConfirmationDetail, ConfirmationRequest
from ygo74.agent_runtime.domains.humanapproval.pending_renderer import PendingConfirmationRenderer
from ygo74.agent_runtime.domains.humanapproval.tickets import (
    ConfirmationTicket,
    InMemoryPendingConfirmationStore,
)
from ygo74.agent_runtime.domains.security.operations import (
    OperationType,
    RiskLevel,
    ToolOperationDescriptor,
)
from ygo74.agent_runtime.domains.security.permissions import Permission
from ygo74.agent_runtime.domains.security.user_context import UserContext
from ygo74.agent_runtime.domains.sessions.agent_conversation import AgentConversation, ConversationPort
from ygo74.agent_runtime.integrations.agentframework.approval import (
    ApprovalRound,
    PendingToolApproval,
)
from ygo74.agent_runtime.integrations.agentframework.binding import AgentFrameworkSession

_TOOL_NAME = "record_local_note"
_API_KEY = "local-demo-key"
_OPERATION = ToolOperationDescriptor(
    tool_name=_TOOL_NAME,
    operation_type=OperationType.WRITE,
    risk_level=RiskLevel.MEDIUM,
    required_permission=Permission("notes", "create"),
    confirmation_required_by_default=True,
)
_RECORDED_NOTES: list[str] = []
_MANIFEST = AgentManifest(
    name="MAF approval example",
    description="Records a local note after explicit confirmation.",
    instructions="Ask before recording any note.",
    skills=(SkillManifest(
        tool_name=_TOOL_NAME,
        implementation=_TOOL_NAME,
        description="Record a local note after explicit human confirmation.",
        operation=_OPERATION,
    ),),
)


@tool(approval_mode="always_require")
def record_local_note(text: str) -> str:
    """Append one note to this demo process after MAF approval.

    Args:
        text: Note content that the user is asked to review.
    """
    _RECORDED_NOTES.append(text)
    return "The note was recorded."


def create_approved_agent() -> Agent:
    """Build the native MAF agent with its approved local-note tool.

    Returns:
        Agent: Agent configured with native tool approval middleware.
    """
    return Agent(
        OpenAIChatClient(model="gpt-4o-mini"),
        name="maf-approval-demo",
        instructions=_MANIFEST.instructions,
        tools=[record_local_note],
        middleware=[ToolApprovalMiddleware()],
    )


class TicketApprovalResolver:
    """Turn MAF approval requests into exact, conversation-owned tickets."""

    def __init__(self, store: InMemoryPendingConfirmationStore, user: UserContext,
                 conversation_id: str) -> None:
        """Keep ticket creation within one authenticated conversation.

        Args:
            store: Store that owns pending confirmation tickets.
            user: Verified user and operation permissions.
            conversation_id: Conversation partition for the ticket.
        """
        self._store = store
        self._user = user
        self._conversation_id = conversation_id

    def will_question(self, pending: tuple[PendingToolApproval, ...]) -> bool:
        """Return false because the app presents a ticket without blocking this turn.

        Args:
            pending: Native MAF approval requests for the current sub-run.
        """
        del pending
        return False

    async def resolve(self, pending: tuple[PendingToolApproval, ...]) -> ApprovalRound:
        """Store each exact tool request, then decline execution to MAF.

        Args:
            pending: Native MAF approval requests for the current sub-run.
        """
        answers = []
        for approval in pending:
            if approval.tool_name != _TOOL_NAME:
                raise ValueError("MAF requested a tool outside the admitted sample")
            text = str(approval.arguments.get("text", ""))
            self._store.issue(ConfirmationTicket.issue(
                subject=self._user.user_id,
                conversation_id=self._conversation_id,
                tool_name=_TOOL_NAME,
                request=ConfirmationRequest(
                    request_id=f"request-{uuid4().hex}",
                    operation=_OPERATION,
                    requested_for=self._user.user_id,
                    title="Record this local note",
                    target="In-memory demo note list",
                    details=(ConfirmationDetail(label="Note", value=text),),
                ),
                arguments={"text": text},
            ))
            answers.append(approval.answer(approved=False))
        return ApprovalRound(tuple(answers), questioned_user=False)


class TicketRunner:
    """Claim a ticket and apply its saved note after explicit confirmation."""

    def __init__(self, store: InMemoryPendingConfirmationStore, user: UserContext,
                 conversation_id: str) -> None:
        """Bind ticket claims to the verified user and conversation.

        Args:
            store: Store containing the ticket to claim.
            user: Verified user whose permission is checked before execution.
            conversation_id: Conversation partition for the ticket.
        """
        self._store = store
        self._user = user
        self._conversation_id = conversation_id

    async def run(self, command: ConfirmationCommand) -> str:
        """Apply only the exact operation and arguments saved in the ticket.

        Args:
            command: Parsed CONFIRM or CANCEL command.
        """
        ticket = self._store.claim(
            command.ticket_id,
            subject=self._user.user_id,
            conversation_id=self._conversation_id,
        )
        if not command.approves:
            return "Cancelled. Nothing was recorded."
        if ticket.tool_name != _TOOL_NAME:
            raise ValueError("ticket names an operation outside this sample")
        self._user.require_permission(_OPERATION.required_permission)
        note = str(ticket.arguments["text"])
        _RECORDED_NOTES.append(note)
        return "The approved note was recorded."


class ConversationRuntime:
    """Own resources for one authenticated sample conversation."""

    def __init__(self, user: UserContext) -> None:
        """Retain the identity associated with this conversation.

        Args:
            user: Verified user and conversation context.
        """
        self.user = user

    async def aclose(self) -> None:
        """Release the sample's in-memory conversation resources."""


class ConversationFactory:
    """Build the MAF session and ticket flow for one verified conversation."""

    async def build(self, principal: AgentPrincipal, conversation_id: str) -> ConversationPort:
        """Compose the native agent session, ticket store, and runner.

        Args:
            principal: Identity verified by the worker's API-key authenticator.
            conversation_id: Conversation partition selected by the caller.
        """
        user = UserContext(
            user_id=principal.subject,
            session_id=conversation_id,
            permissions=frozenset({_OPERATION.required_permission}),
        )
        store = InMemoryPendingConfirmationStore()
        session = AgentFrameworkSession(
            create_approved_agent(),
            session_id=conversation_id,
            resolver=TicketApprovalResolver(store, user, conversation_id),
            tool_names=(_TOOL_NAME,),
        )
        return AgentConversation(
            runtime=ConversationRuntime(user),
            session=session,
            store=store,
            runner=TicketRunner(store, user, conversation_id),
            conversation_id=conversation_id,
            renderer=PendingConfirmationRenderer(),
        )


_RESOLVER = StaticApiKeyUserResolver({_API_KEY: ResolvedUser(user_id="local-demo-user")})
_DESCRIPTOR = AgentDescriptorFactory(
    _MANIFEST,
    agent_id="maf-approval-demo",
    tags=("agent-framework", "human-approval", "offline-side-effect"),
    created_at=datetime(2026, 1, 1, tzinfo=UTC),
    security=AdvertisedSecurity.of(jwt_validation=None, api_key_resolver=_RESOLVER),
    streaming=True,
    owner="ai-enterprise-agent-runtime",
).build()
_DEFINITION = AgentDefinition(
    descriptor=_DESCRIPTOR,
    factory="approval_worker:create_approved_agent",
    tools=(_OPERATION,),
    control_point="conversation-scoped-ticket-ledger",
)
_SETTINGS = WorkerSettings(
    deployment_id="maf-approval-demo",
    identity_namespace="local-demo",
    authentication=AuthenticationPolicy.api_key(_RESOLVER),
    surfaces=(EndpointSurface.OPENAI_RESPONSES,),
    discovery=DiscoveryConfiguration(enable_openai_models=True, require_authentication=True),
)
app = ManagedAgentWorker(_DEFINITION, _SETTINGS, ConversationFactory().build).build_app()
