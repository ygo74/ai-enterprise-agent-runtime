from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import Any

from fastapi import FastAPI
from ygo74.agent_runtime.domains.auth.authentication_policy import AuthenticationPolicy
from ygo74.agent_runtime.domains.contracts.agent_output import (
    AgentOutput,
    TextContent,
    TokenUsage,
)
from ygo74.agent_runtime.domains.contracts.stream_events import (
    AgentStreamEvent,
    ContentEnd,
    ContentStart,
    TerminalEvent,
    TextDelta,
    UsageEvent,
)
from ygo74.agent_runtime.domains.discovery.agent_descriptor import (
    AgentCapabilitySet,
    AgentDescriptor,
)
from ygo74.agent_runtime.domains.discovery.discovery_configuration import (
    DiscoveryConfiguration,
)
from ygo74.agent_runtime.domains.endpoints.conversation_payloads import latest_message
from ygo74.agent_runtime.domains.endpoints.hosting_factory import (
    EndpointSurface,
    HostingFactory,
)

app = FastAPI(title="Agent Runtime Python Quickstart")

# Echo invokes no model, so every model token counter is known to be zero.
# This producer-owned snapshot is never a fallback for unknown model usage.
ECHO_MODEL_USAGE: TokenUsage = TokenUsage(
    input_tokens=0,
    output_tokens=0,
    total_tokens=0,
    cached_input_tokens=0,
    reasoning_output_tokens=0,
    cache_write_input_tokens=0,
)


async def _stream_echo(text: str) -> AsyncIterator[AgentStreamEvent]:
    yield UsageEvent(ECHO_MODEL_USAGE)
    yield ContentStart("echo", TextContent(""))
    yield TextDelta("echo", "Echo: ")
    yield TextDelta("echo", text)
    yield ContentEnd("echo")
    yield TerminalEvent()


async def echo_agent(
    payload: dict[str, Any],
) -> AgentOutput | AsyncIterator[AgentStreamEvent]:
    """Return the normalized input as typed content or incremental events."""
    incoming = payload["input"]
    text = incoming if isinstance(incoming, str) else latest_message(incoming)
    if payload.get("stream") is True:
        return _stream_echo(text)

    return AgentOutput((TextContent(f"Echo: {text}"),), usage=ECHO_MODEL_USAGE)


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
