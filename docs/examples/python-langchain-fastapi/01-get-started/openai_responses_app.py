from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, AsyncIterator

from fastapi import FastAPI

from agent_solution_architect import run_solution_architect_agent, run_solution_architect_agent_stream
from env_loader import ensure_env_loaded
from ygo74.agent_runtime import (
    AgentCapabilitySet,
    AgentDescriptor,
    AgentSkill,
    DescriptorRegistry,
    DiscoveryConfiguration,
    Modality,
    add_ai_endpoints,
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


async def _solution_architect_once(payload: dict[str, Any]) -> dict[str, Any]:
    user_input = _extract_user_input(payload)
    architect_output = await run_solution_architect_agent(user_input)
    return {
        "request_id": payload["request_id"],
        "status": "success",
        "output": architect_output,
        "metadata": {"route_key": payload["route_key"]},
    }


async def _solution_architect_stream(payload: dict[str, Any]) -> AsyncIterator[str]:
    user_input = _extract_user_input(payload)
    async for delta in run_solution_architect_agent_stream(user_input):
        yield delta


def solution_architect_entrypoint(payload: dict[str, Any]) -> Any:
    """Return either a single-shot coroutine or a real streaming async generator.

    add_ai_endpoints detects which one was returned (a coroutine is awaited for a single
    JSON response, an async generator is iterated for token-by-token Server-Sent Events)
    based on payload["stream"], which reflects the client's requested `stream` flag.
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

add_ai_endpoints(
    app,
    solution_architect_entrypoint,
    default_route_key=AGENT_ID,
    enable_openai_responses=True,
    enable_openai_chat_completions=True,
    enable_anthropic_messages=False,
    descriptor_registry=DescriptorRegistry([agent_descriptor]),
    discovery=DiscoveryConfiguration(enable_openai_models=True, enable_anthropic_models=True),
)
