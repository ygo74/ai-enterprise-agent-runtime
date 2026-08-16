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
    RoleRequiredAccessPolicy,
    add_ai_endpoints,
)
from ygo74.agent_runtime.domains.auth.jwt_authenticator import JwksKeyResolver, JwtValidationConfig


app = FastAPI(title="OpenAI Responses + JWT (OIDC/Keycloak) Authentication Example")

# Authorization is owned by the developer, but the rule is now defined once and
# invoked consistently by the runtime on every agent-scoped route: an
# unauthorized caller neither sees the agent in GET /v1/models nor can invoke
# it. Leave REQUIRED_ROLE empty to allow any authenticated caller.
required_role = os.getenv("REQUIRED_ROLE", "")
authorization_policy = RoleRequiredAccessPolicy(required_role=required_role)


async def _entrypoint(payload: dict[str, Any]) -> dict[str, Any]:
    auth_context = payload.get("auth_context") or {}
    identity = auth_context.get("identity") or {}
    roles = auth_context.get("roles", [])

    return {
        "request_id": payload["request_id"],
        "status": "success",
        "output": {
            "message": "OIDC-authenticated request accepted",
            "subject": identity.get("subject"),
            "name": identity.get("name"),
            "email": identity.get("email"),
            "roles": roles,
            "groups": auth_context.get("groups", []),
            "claims": auth_context.get("claims", {}),
            "input": payload.get("input"),
        },
        "metadata": {"route_key": payload["route_key"]},
    }


keycloak_base_url = os.getenv("KEYCLOAK_BASE_URL", "http://localhost:8080")
keycloak_realm = os.getenv("KEYCLOAK_REALM", "agent-runtime-demo")
issuer = f"{keycloak_base_url}/realms/{keycloak_realm}"
jwks_url = f"{issuer}/protocol/openid-connect/certs"

jwt_config = JwtValidationConfig(
    allowed_algorithms=("RS256",),
    # Keycloak access tokens do not include "nbf" by default, unlike the static
    # HS256 tokens generated in the 02-jwt-authentication example.
    required_claims=("sub", "exp", "iss", "aud"),
    issuer=os.getenv("JWT_ISSUER", issuer),
    audience=os.getenv("JWT_AUDIENCE", "runtime"),
    leeway_seconds=int(os.getenv("JWT_LEEWAY_SECONDS", "0")),
    key_resolver=JwksKeyResolver(
        jwks_url=os.getenv("JWKS_URL", jwks_url),
        cache_ttl_seconds=int(os.getenv("JWKS_CACHE_TTL_SECONDS", "300")),
    ),
    # Dot-separated path into the decoded claims used to project roles, mirroring
    # LibreChat's OPENID_REQUIRED_ROLE_PARAMETER_PATH. Examples for Keycloak:
    #   "realm_access.roles"                    -> realm-wide roles
    #   "resource_access.librechat.roles"       -> client-scoped roles
    roles_claim_path=os.getenv("JWT_ROLES_CLAIM_PATH", "realm_access.roles"),
    groups_claim_path=os.getenv("JWT_GROUPS_CLAIM_PATH"),
)


# Declaring an identity is what makes this agent discoverable via GET /v1/models.
# See ../agent-descriptor.md for the full guide.
AGENT_ID = "jwt-protected-agent"

agent_descriptor = AgentDescriptor(
    agent_id=AGENT_ID,
    route_key=AGENT_ID,
    display_name="OIDC Protected Agent",
    description=(
        "Echoes the authenticated caller's identity, roles, and groups resolved "
        "from a Keycloak-issued token."
    ),
    version="1.0.0",
    owner="ai-enterprise-agent-runtime",
    created_at_utc=datetime(2026, 8, 16, tzinfo=timezone.utc),
    capabilities=AgentCapabilitySet(
        streaming=False,
        input_modalities=(Modality.TEXT,),
        output_modalities=(Modality.TEXT,),
    ),
    tags=("authentication", "oidc", "keycloak"),
    security_schemes=("jwt", "oidc"),
    skills=(
        AgentSkill(
            skill_id="whoami",
            name="Who am I",
            description="Returns the authenticated subject, roles, and groups resolved from the OIDC token.",
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
    authorization_policy=authorization_policy,
)
