"""Platform-owned local worker; the agent package has no HTTP implementation."""

from deployment import settings
from native import definition
from ygo74.agent_runtime.integrations.agentframework.worker import AgentFrameworkWorker

app = AgentFrameworkWorker(definition, settings).build_app()
