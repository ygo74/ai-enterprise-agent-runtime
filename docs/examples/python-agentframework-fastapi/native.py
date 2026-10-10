"""Native factory and declaration; no skill registry, handlers or event loop."""

from datetime import datetime, timezone

from agent_framework import Agent
from echo_client import EchoClient
from ygo74.agent_runtime.domains.contracts.agent_definition import (
    AgentDefinition,
    AgentFactoryContext,
)
from ygo74.agent_runtime.domains.discovery.agent_descriptor import (
    AgentCapabilitySet,
    AgentDescriptor,
)


def create_agent(context: AgentFactoryContext) -> Agent:
    """Return a normal MAF agent; context supplies verified caller dependencies."""
    return Agent(EchoClient(), name="native-echo", instructions="Echo the user's text.")


definition = AgentDefinition(
    AgentDescriptor(
        agent_id="agentframework-echo", route_key="agentframework-echo", display_name="Native Echo",
        description="Offline native agent, with server-managed conversation history.",
        version="1.0.0", owner="example", created_at_utc=datetime(2026, 1, 1, tzinfo=timezone.utc),
        capabilities=AgentCapabilitySet(streaming=True),
    ),
    factory="native:create_agent",
)
