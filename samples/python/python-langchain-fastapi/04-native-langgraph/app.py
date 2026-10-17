"""Authenticated local FastAPI host for the offline LangGraph example."""

from datetime import UTC, datetime

from native_agent import build_graph
from ygo74.agent_runtime.domains.auth.apikey_authenticator import (
    StaticApiKeyUserResolver,
)
from ygo74.agent_runtime.domains.auth.auth_context import ResolvedUser
from ygo74.agent_runtime.domains.auth.authentication_policy import AuthenticationPolicy
from ygo74.agent_runtime.domains.contracts.agent_definition import AgentDefinition
from ygo74.agent_runtime.domains.contracts.manifests import AgentManifest
from ygo74.agent_runtime.domains.discovery.discovery_configuration import (
    DiscoveryConfiguration,
)
from ygo74.agent_runtime.domains.discovery.manifest_descriptor import (
    AdvertisedSecurity,
    AgentDescriptorFactory,
)
from ygo74.agent_runtime.domains.endpoints.hosting_factory import EndpointSurface
from ygo74.agent_runtime.domains.endpoints.managed_worker import WorkerSettings
from ygo74.agent_runtime.integrations.langchain.worker import LangGraphWorker

LOCAL_KEY = "local-demo-key"
users = StaticApiKeyUserResolver({LOCAL_KEY: ResolvedUser(user_id="local-demo")})
manifest = AgentManifest(
    name="Offline LangGraph demo",
    description="A deterministic, tool-free native graph example.",
    instructions="Answer brief questions locally.",
)
descriptor = AgentDescriptorFactory(
    manifest,
    agent_id="offline-langgraph-demo",
    tags=("langgraph", "offline"),
    created_at=datetime.now(UTC),
    security=AdvertisedSecurity.of(jwt_validation=None, api_key_resolver=users),
).build()
definition = AgentDefinition(descriptor, "native_agent:build_graph")
settings = WorkerSettings(
    deployment_id="offline-demo",
    identity_namespace="local",
    authentication=AuthenticationPolicy.api_key(users),
    surfaces=(EndpointSurface.OPENAI_CHAT_COMPLETIONS,),
    discovery=DiscoveryConfiguration(enable_openai_models=True, require_authentication=True),
)
app = LangGraphWorker(definition, settings, factory=build_graph).build_app()
