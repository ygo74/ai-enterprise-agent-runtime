from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import Any

from fastapi import FastAPI
from ygo74.agent_runtime.domains.auth.authentication_policy import AuthenticationPolicy
from ygo74.agent_runtime.domains.discovery.agent_descriptor import (
    AgentCapabilitySet,
    AgentDescriptor,
)
from ygo74.agent_runtime.domains.discovery.discovery_configuration import (
    DiscoveryConfiguration,
)
from ygo74.agent_runtime.domains.endpoints.hosting_factory import (
    EndpointSurface,
    HostingFactory,
)

app = FastAPI(title="Agent Runtime Python Quickstart")


async def _stream_echo(text: str) -> AsyncIterator[str]:
    yield "Echo: "
    yield text


async def echo_agent(
    payload: dict[str, Any],
) -> dict[str, Any] | AsyncIterator[str]:
    """Return the normalized input as a response or a text stream."""
    if payload.get("stream") is True:
        return _stream_echo(str(payload["input"]))

    return {
        "request_id": payload["request_id"],
        "status": "success",
        "output": {"content": f"Echo: {payload['input']}"},
    }


echo_agent_descriptor = AgentDescriptor(
    agent_id="echo-agent",
    route_key="echo-agent",
    display_name="Echo Agent",
    description="Echoes the latest input text.",
    version="1.0.0",
    owner="quickstart",
    created_at_utc=datetime.now(UTC),
    capabilities=AgentCapabilitySet(streaming=True),
)

(
    HostingFactory(app)
    .add_agent(echo_agent, echo_agent_descriptor)
    .add_ai_endpoints(
        EndpointSurface.OPENAI_RESPONSES,
        EndpointSurface.OPENAI_CHAT_COMPLETIONS,
        EndpointSurface.ANTHROPIC_MESSAGES,
    )
    .add_security(AuthenticationPolicy.anonymous())
    .add_discovery(DiscoveryConfiguration(enable_openai_models=True))
    .register()
)
