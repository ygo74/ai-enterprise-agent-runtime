"""Compose a native MAF session with the framework-neutral managed worker."""

from datetime import UTC, datetime

from ygo74.agent_runtime.domains.auth.agent_principal import AgentPrincipal
from ygo74.agent_runtime.domains.auth.apikey_authenticator import StaticApiKeyUserResolver
from ygo74.agent_runtime.domains.auth.auth_context import ResolvedUser
from ygo74.agent_runtime.domains.auth.authentication_policy import AuthenticationPolicy
from ygo74.agent_runtime.domains.contracts.agent_definition import AgentDefinition
from ygo74.agent_runtime.domains.discovery.agent_descriptor import AgentCapabilitySet, AgentDescriptor
from ygo74.agent_runtime.domains.discovery.discovery_configuration import DiscoveryConfiguration
from ygo74.agent_runtime.domains.endpoints.hosting_factory import EndpointSurface
from ygo74.agent_runtime.domains.endpoints.managed_worker import ManagedAgentWorker, WorkerSettings
from ygo74.agent_runtime.domains.humanapproval.commands import ConfirmationCommand
from ygo74.agent_runtime.domains.humanapproval.pending_renderer import PendingConfirmationRenderer
from ygo74.agent_runtime.domains.humanapproval.tickets import InMemoryPendingConfirmationStore, UnknownTicketError
from ygo74.agent_runtime.domains.security.user_context import UserContext
from ygo74.agent_runtime.domains.sessions.agent_conversation import AgentConversation, ConversationPort
from ygo74.agent_runtime.integrations.agentframework.binding import AgentFrameworkSession

from native_agent import create_agent

_API_KEY = "managed-demo-key"
_RESOLVER = StaticApiKeyUserResolver({_API_KEY: ResolvedUser(user_id="managed-demo-user")})
_DEFINITION = AgentDefinition(
    AgentDescriptor(
        agent_id="managed-maf-echo",
        route_key="managed-maf-echo",
        display_name="Managed MAF Echo",
        description="A deterministic native MAF agent composed with ManagedAgentWorker.",
        version="1.0.0",
        owner="example",
        created_at_utc=datetime(2026, 1, 1, tzinfo=UTC),
        capabilities=AgentCapabilitySet(streaming=True),
    ),
    factory="native_agent:create_agent",
)
_SETTINGS = WorkerSettings(
    deployment_id="managed-maf-echo",
    identity_namespace="local-demo",
    authentication=AuthenticationPolicy.api_key(_RESOLVER),
    surfaces=(EndpointSurface.OPENAI_CHAT_COMPLETIONS,),
    discovery=DiscoveryConfiguration(enable_openai_models=True, require_authentication=True),
)


class ConversationRuntime:
    """Own the verified user context for one cached conversation."""

    def __init__(self, user: UserContext) -> None:
        """Retain the identity and conversation scope.

        Args:
            user: Verified user context owned by the worker.
        """
        self.user = user

    async def aclose(self) -> None:
        """Release resources; the deterministic sample owns none."""


class NoTicketRunner:
    """Reject approval commands because this sample declares no tools."""

    async def run(self, command: ConfirmationCommand) -> str:
        """Raise the standard error for a ticket that was never issued.

        Args:
            command: Parsed confirmation command.

        Raises:
            UnknownTicketError: Every ticket is unknown in this tool-free sample.
        """
        raise UnknownTicketError(command.ticket_id)


async def build_conversation(principal: AgentPrincipal, conversation_id: str) -> ConversationPort:
    """Bind the native MAF agent to the generic worker's conversation ports.

    Args:
        principal: Verified caller associated with this conversation.
        conversation_id: Caller-provided conversation handle within the identity.

    Returns:
        ConversationPort: Cached conversation with a native MAF session.
    """
    user = UserContext(user_id=principal.subject, session_id=conversation_id)
    return AgentConversation(
        runtime=ConversationRuntime(user),
        session=AgentFrameworkSession(create_agent(), session_id=conversation_id),
        store=InMemoryPendingConfirmationStore(),
        runner=NoTicketRunner(),
        conversation_id=conversation_id,
        renderer=PendingConfirmationRenderer(),
    )


app = ManagedAgentWorker(_DEFINITION, _SETTINGS, build_conversation).build_app()
