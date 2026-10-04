from __future__ import annotations

import logging
from collections.abc import AsyncIterator, Awaitable
from datetime import datetime, timezone
from typing import Any

from agent_solution_architect import (
    run_solution_architect_agent,
    run_solution_architect_agent_stream,
)
from env_loader import ensure_env_loaded
from fastapi import FastAPI
from ygo74.agent_runtime.domains.auth.authentication_policy import AuthenticationPolicy
from ygo74.agent_runtime.domains.contracts.agent_output import AgentOutput
from ygo74.agent_runtime.domains.contracts.stream_events import AgentStreamEvent
from ygo74.agent_runtime.domains.discovery.agent_descriptor import (
    AgentCapabilitySet,
    AgentDescriptor,
    AgentSkill,
    Modality,
)
from ygo74.agent_runtime.domains.discovery.discovery_configuration import (
    DiscoveryConfiguration,
)
from ygo74.agent_runtime.domains.endpoints.hosting_factory import (
    EndpointSurface,
    HostingFactory,
)

ensure_env_loaded()

# Ensure agent execution errors (including MCP tool failures) print full tracebacks
# to the console instead of being silently reduced to a short message.
logging.basicConfig(level=logging.INFO)
logging.getLogger("ygo74.agent_runtime").setLevel(logging.DEBUG)


app = FastAPI(title="AI Solution Architect - OpenAI Responses Example")


def _extract_user_input(payload: dict[str, Any]) -> str:
    incoming = payload.get("input")

    if isinstance(incoming, list):
        return "\n".join(str(item) for item in incoming)

    return str(incoming)


async def _solution_architect_once(payload: dict[str, Any]) -> AgentOutput:
    user_input = _extract_user_input(payload)
    return await run_solution_architect_agent(user_input)


def _solution_architect_stream(payload: dict[str, Any]) -> AsyncIterator[AgentStreamEvent]:
    user_input = _extract_user_input(payload)
    return run_solution_architect_agent_stream(user_input)


def solution_architect_entrypoint(
    payload: dict[str, Any],
) -> Awaitable[AgentOutput] | AsyncIterator[AgentStreamEvent]:
    """Return either a single-shot coroutine or a real streaming async generator.

    The runtime awaits the returned coroutine for a single response or iterates the async
    generator for token-by-token Server-Sent Events based on the client's `stream` flag.
    """

    if payload.get("stream"):
        return _solution_architect_stream(payload)

    return _solution_architect_once(payload)


# Declaring an identity is what makes this agent discoverable via GET /v1/models.
# `agent_id` is the identifier clients see and send back as `model`; `route_key`
# stays internal to dispatch. See ../agent-descriptor.md for the full guide.
AGENT_ID = "ai-solution-architect"

agent_descriptor = AgentDescriptor(
    agent_id=AGENT_ID,
    route_key=AGENT_ID,
    display_name="AI Solution Architect",
    description=(
        "Answers Azure and Microsoft Learn solution-architecture questions, backed "
        "by an MCP research tool."
    ),
    version="1.0.0",
    owner="ai-enterprise-agent-runtime",
    created_at_utc=datetime(2026, 8, 16, tzinfo=timezone.utc),
    capabilities=AgentCapabilitySet(
        streaming=True,
        input_modalities=(Modality.TEXT,),
        output_modalities=(Modality.TEXT,),
    ),
    tags=("solution-architecture", "azure"),
    skills=(
        AgentSkill(
            skill_id="solution-architecture-qa",
            name="Solution architecture Q&A",
            description="Answers Azure architecture questions, citing Microsoft Learn content.",
            examples=("What's the best way to expose a private AKS cluster to partners?",),
        ),
    ),
)

(
    HostingFactory(app)
    .add_agent(solution_architect_entrypoint, agent_descriptor)
    .add_ai_endpoints(
        EndpointSurface.OPENAI_RESPONSES,
        EndpointSurface.OPENAI_CHAT_COMPLETIONS,
    )
    .add_security(AuthenticationPolicy.anonymous())
    .add_discovery(DiscoveryConfiguration(enable_openai_models=True, enable_anthropic_models=True))
    .register()
)
