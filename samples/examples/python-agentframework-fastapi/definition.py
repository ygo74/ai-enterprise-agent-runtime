"""Runtime identity and trusted factory path for the native MAF agent."""

from datetime import UTC, datetime

from ygo74.agent_runtime.domains.contracts.agent_definition import AgentDefinition
from ygo74.agent_runtime.domains.discovery.agent_descriptor import (
    AgentCapabilitySet,
    AgentDescriptor,
)

definition = AgentDefinition(
    AgentDescriptor(
        agent_id="agentframework-echo",
        route_key="agentframework-echo",
        display_name="Native Echo",
        description="Offline native agent, with server-managed conversation history.",
        version="1.0.0",
        owner="example",
        created_at_utc=datetime(2026, 1, 1, tzinfo=UTC),
        capabilities=AgentCapabilitySet(streaming=True),
    ),
    factory="native:create_agent",
)
