from __future__ import annotations

import os
from typing import Any

from fastapi import FastAPI

from ygo74.agent_runtime import AuthorizationError, add_ai_endpoints
from ygo74.agent_runtime.domains.auth.jwt_authenticator import JwksKeyResolver, JwtValidationConfig


app = FastAPI(title="OpenAI Responses + JWT (OIDC/Keycloak) Authentication Example")

# Authorization is owned by the developer: the runtime only authenticates and
# projects the user context. Leave empty to allow any authenticated caller.
required_role = os.getenv("REQUIRED_ROLE", "")


async def _entrypoint(payload: dict[str, Any]) -> dict[str, Any]:
    auth_context = payload.get("auth_context") or {}
    identity = auth_context.get("identity") or {}
    roles = auth_context.get("roles", [])

    if required_role and required_role not in roles:
        raise AuthorizationError(
            code="role_required",
            message=f"Role '{required_role}' is required",
            details={"required_role": required_role, "granted_roles": roles},
        )

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


add_ai_endpoints(
    app,
    _entrypoint,
    default_route_key="jwt-protected-agent",
    enable_openai_responses=True,
    enable_openai_chat_completions=True,
    enable_anthropic_messages=False,
    jwt_validation=jwt_config,
    require_bearer_token=True,
)
