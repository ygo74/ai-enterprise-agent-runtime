from __future__ import annotations

import os
from typing import Any

from fastapi import FastAPI

from ygo74.agent_runtime import add_ai_endpoints
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
        os.getenv("JWT_HS256_SECRET", "change-me-in-local-env")
    ),
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
