from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any

from fastapi import FastAPI

from ygo74.agent_runtime import (
    AgentCapabilitySet,
    AgentDescriptor,
    AgentSkill,
    DescriptorRegistry,
    DiscoveryConfiguration,
    Modality,
    add_ai_endpoints,
)
from ygo74.agent_runtime.domains.auth.jwt_authenticator import JwtValidationConfig, StaticSymmetricKeyResolver


app = FastAPI(title="OpenAI Responses + JWT Authentication Example")


async def _entrypoint(payload: dict[str, Any]) -> dict[str, Any]:
    auth_context = payload.get("auth_context") or {}
    identity = auth_context.get("identity") or {}

    return {
        "request_id": payload["request_id"],
        "status": "success",
        "output": {
            "message": "JWT authenticated request accepted",
            "subject": identity.get("subject"),
            "claims": auth_context.get("claims", {}),
            "input": payload.get("input"),
        },
        "metadata": {"route_key": payload["route_key"]},
    }


jwt_config = JwtValidationConfig(
    allowed_algorithms=("HS256",),
    required_claims=("sub", "exp", "nbf", "iss", "aud"),
    issuer=os.getenv("JWT_ISSUER", "https://issuer.example.com"),
    audience=os.getenv("JWT_AUDIENCE", "runtime"),
    leeway_seconds=int(os.getenv("JWT_LEEWAY_SECONDS", "0")),
    key_resolver=StaticSymmetricKeyResolver(
        os.getenv("JWT_HS256_SECRET", "change-me-in-local-env-please-32bytes")
    ),
)


# Declaring an identity is what makes this agent discoverable via GET /v1/models.
# See ../agent-descriptor.md for the full guide.
AGENT_ID = "jwt-protected-agent"

agent_descriptor = AgentDescriptor(
    agent_id=AGENT_ID,
    route_key=AGENT_ID,
    display_name="JWT Protected Agent",
    description="Echoes the authenticated caller's identity and claims after JWT validation.",
    version="1.0.0",
    owner="ai-enterprise-agent-runtime",
    created_at_utc=datetime(2026, 8, 16, tzinfo=timezone.utc),
    capabilities=AgentCapabilitySet(
        streaming=False,
        input_modalities=(Modality.TEXT,),
        output_modalities=(Modality.TEXT,),
    ),
    tags=("authentication", "jwt"),
    security_schemes=("jwt",),
    skills=(
        AgentSkill(
            skill_id="whoami",
            name="Who am I",
            description="Returns the authenticated subject and claims extracted from the bearer token.",
        ),
    ),
)

add_ai_endpoints(
    app,
    _entrypoint,
    default_route_key=AGENT_ID,
    enable_openai_responses=True,
    enable_openai_chat_completions=True,
    enable_anthropic_messages=False,
    jwt_validation=jwt_config,
    require_bearer_token=True,
    descriptor_registry=DescriptorRegistry([agent_descriptor]),
    discovery=DiscoveryConfiguration(enable_openai_models=True, enable_anthropic_models=True),
)
