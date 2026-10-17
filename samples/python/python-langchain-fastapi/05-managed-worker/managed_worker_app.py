"""Use the framework-neutral managed worker with a LangGraph composition."""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime

from native_agent import build_graph
from ygo74.agent_runtime.domains.auth.agent_principal import AgentPrincipal
from ygo74.agent_runtime.domains.auth.apikey_authenticator import StaticApiKeyUserResolver
from ygo74.agent_runtime.domains.auth.auth_context import ResolvedUser
from ygo74.agent_runtime.domains.auth.authentication_policy import AuthenticationPolicy
from ygo74.agent_runtime.domains.contracts.agent_definition import (
    AgentDefinition,
    AgentFactoryContext,
)
from ygo74.agent_runtime.domains.contracts.manifests import AgentManifest
from ygo74.agent_runtime.domains.discovery.discovery_configuration import DiscoveryConfiguration
from ygo74.agent_runtime.domains.discovery.manifest_descriptor import (
    AdvertisedSecurity,
    AgentDescriptorFactory,
)
from ygo74.agent_runtime.domains.endpoints.hosting_factory import EndpointSurface
from ygo74.agent_runtime.domains.endpoints.managed_worker import (
    ManagedAgentWorker,
    WorkerSettings,
)
from ygo74.agent_runtime.domains.humanapproval.commands import ConfirmationCommand
from ygo74.agent_runtime.domains.humanapproval.pending_renderer import PendingConfirmationRenderer
from ygo74.agent_runtime.domains.humanapproval.tickets import (
    InMemoryPendingConfirmationStore,
    UnknownTicketError,
)
from ygo74.agent_runtime.domains.security.user_context import UserContext
from ygo74.agent_runtime.domains.sessions.agent_conversation import (
    AgentConversation,
    ConversationPort,
)
from ygo74.agent_runtime.integrations.langchain import LangGraphSession

DEPLOYMENT_ID = "managed-langgraph-demo"
IDENTITY_NAMESPACE = "local-demo"
API_KEY = "local-demo-key"

api_key_resolver = StaticApiKeyUserResolver(
    {API_KEY: ResolvedUser(user_id="local-demo")}
)
manifest = AgentManifest(
    name="Managed LangGraph demo",
    description="A deterministic, tool-free graph hosted by ManagedAgentWorker.",
    instructions="Answer briefly using the available context.",
)
descriptor = AgentDescriptorFactory(
    manifest,
    agent_id=DEPLOYMENT_ID,
    tags=("langgraph", "managed-worker", "offline"),
    created_at=datetime.now(UTC),
    security=AdvertisedSecurity.of(jwt_validation=None, api_key_resolver=api_key_resolver),
).build()
definition = AgentDefinition(descriptor, "native_agent:build_graph")
settings = WorkerSettings(
    deployment_id=DEPLOYMENT_ID,
    identity_namespace=IDENTITY_NAMESPACE,
    authentication=AuthenticationPolicy.api_key(api_key_resolver),
    surfaces=(EndpointSurface.OPENAI_CHAT_COMPLETIONS,),
    discovery=DiscoveryConfiguration(enable_openai_models=True, require_authentication=True),
)


class ConversationRuntime:
    """Own the verified user context for one conversation."""

    def __init__(self, user: UserContext) -> None:
        self.user = user

    async def aclose(self) -> None:
        """Release conversation-scoped resources; this sample owns none."""


class NoTicketRunner:
    """Reject confirmation commands because this tool-free sample issues no tickets."""

    async def run(self, command: ConfirmationCommand) -> str:
        """Report that a requested ticket is unknown."""
        ticket_id = getattr(command, "ticket_id", "")
        raise UnknownTicketError(str(ticket_id))


async def build_conversation(principal: AgentPrincipal, conversation_id: str) -> ConversationPort:
    """Bind an existing LangGraph to the generic worker's conversation ports."""
    context = AgentFactoryContext(
        principal=principal,
        conversation_id=conversation_id,
        deployment_id=settings.deployment_id,
        identity_namespace=settings.identity_namespace,
    )
    user = UserContext(user_id=principal.subject, session_id=conversation_id)
    runtime = ConversationRuntime(user)
    session = LangGraphSession(build_graph(context), thread_id=_thread_id(context))
    return AgentConversation(
        runtime=runtime,
        session=session,
        store=InMemoryPendingConfirmationStore(),
        runner=NoTicketRunner(),
        conversation_id=conversation_id,
        renderer=PendingConfirmationRenderer(),
    )


def _thread_id(context: AgentFactoryContext) -> str:
    """Create a private checkpoint key partitioned by deployment, identity and conversation."""
    parts = (
        context.deployment_id,
        context.identity_namespace,
        context.principal.subject,
        context.conversation_id,
    )
    material = "".join(f"{len(part)}:{part}" for part in parts)
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


app = ManagedAgentWorker(
    definition,
    settings,
    conversation_factory=build_conversation,
).build_app()
