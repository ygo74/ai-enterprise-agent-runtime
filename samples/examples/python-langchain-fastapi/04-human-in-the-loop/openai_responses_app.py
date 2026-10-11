"""Run the developer-owned LangGraph through the managed runtime worker."""

from __future__ import annotations

import logging
from datetime import UTC, datetime

from env_loader import ensure_env_loaded
from conversation import ArchitectConversationFactory
from solution_architect_agent import OPERATIONS
from ygo74.agent_runtime.domains.auth.apikey_authenticator import StaticApiKeyUserResolver
from ygo74.agent_runtime.domains.auth.auth_context import ResolvedUser
from ygo74.agent_runtime.domains.auth.authentication_policy import AuthenticationPolicy
from ygo74.agent_runtime.domains.contracts.agent_definition import AgentDefinition
from ygo74.agent_runtime.domains.contracts.manifests import AgentManifest, SkillManifest
from ygo74.agent_runtime.domains.discovery.discovery_configuration import DiscoveryConfiguration
from ygo74.agent_runtime.domains.endpoints.hosting_factory import EndpointSurface
from ygo74.agent_runtime.domains.endpoints.managed_worker import WorkerSettings
from ygo74.agent_runtime.domains.discovery.manifest_descriptor import (
    AdvertisedSecurity,
    AgentDescriptorFactory,
)
from ygo74.agent_runtime.domains.humanapproval.confirmation import (
    ConfiguredConfirmationPolicy,
    InMemoryConfirmationPreferenceStore,
)
from ygo74.agent_runtime.domains.security.floor import SecurityFloor
from ygo74.agent_runtime.integrations.langchain.worker import LangGraphWorker

ensure_env_loaded()
logging.basicConfig(level=logging.INFO)

AGENT_ID = "ai-solution-architect-hitl"
API_KEY = "demo-key"

manifest = AgentManifest(
    name="AI Solution Architect (human in the loop)",
    description="Answers Azure architecture questions, asking before it queries Microsoft Learn.",
    instructions="Ask before sending a question outside the organisation.",
    skills=(
        SkillManifest(
            tool_name="mslearn_mcp_search",
            implementation="mslearn_mcp_search",
            description="Searches Microsoft Learn. Requires an explicit approval before each call.",
            operation=OPERATIONS[0],
        ),
    ),
)
api_key_resolver = StaticApiKeyUserResolver(
    {API_KEY: ResolvedUser(user_id="demo-user", name="Demo User")}
)
descriptor = AgentDescriptorFactory(
    manifest,
    agent_id=AGENT_ID,
    tags=("solution-architecture", "human-in-the-loop"),
    created_at=datetime(2026, 9, 13, tzinfo=UTC),
    security=AdvertisedSecurity.of(jwt_validation=None, api_key_resolver=api_key_resolver),
    streaming=True,
    owner="ai-enterprise-agent-runtime",
).build()
definition = AgentDefinition(
    descriptor=descriptor,
    factory="solution_architect_agent:build_graph",
    tools=OPERATIONS,
    control_point="approval-ticket-store",
)
policy = ConfiguredConfirmationPolicy(InMemoryConfirmationPreferenceStore(), SecurityFloor(()))
conversation_factory = ArchitectConversationFactory(policy)

app = LangGraphWorker(
    definition,
    WorkerSettings(
        deployment_id=AGENT_ID,
        identity_namespace="local-demo",
        authentication=AuthenticationPolicy.api_key(api_key_resolver),
        surfaces=(EndpointSurface.OPENAI_CHAT_COMPLETIONS, EndpointSurface.OPENAI_RESPONSES),
        discovery=DiscoveryConfiguration(
            enable_openai_models=True,
            require_authentication=True,
        ),
    ),
    conversation_factory=conversation_factory.build,
).build_app()
