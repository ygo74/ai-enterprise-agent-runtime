from __future__ import annotations

from collections.abc import Callable
from typing import Any

from ygo74.agent_runtime.domains.auth.auth_errors import AuthenticationError

ApiKeyUserResolver = Callable[[str], dict[str, Any] | None]


def authenticate_api_key(api_key: str, resolver: ApiKeyUserResolver) -> dict[str, Any]:
    """Resolve an API key to a normalized auth context via a developer-supplied hook.

    The raw API key is never propagated into the returned context: only the
    resolved user identity is exposed to the handler.
    """

    if not api_key:
        raise AuthenticationError(code="token_missing", message="API key is missing")

    try:
        user = resolver(api_key)
    except AuthenticationError:
        raise
    except Exception as ex:
        raise AuthenticationError(
            code="user_resolution_failed",
            message="API key user-resolution hook raised an error",
        ) from ex

    if not user:
        raise AuthenticationError(code="api_key_invalid", message="API key is not recognized")

    if not isinstance(user, dict):
        raise AuthenticationError(
            code="user_context_malformed",
            message="API key user-resolution hook must return a mapping",
        )

    context: dict[str, Any] = dict(user)
    context["authType"] = "api_key"

    raw_identity = context.get("identity")
    identity: dict[str, Any] = dict(raw_identity) if isinstance(raw_identity, dict) else {}
    user_id = identity.get("userId") or context.get("userId") or identity.get("subject")
    if not isinstance(user_id, str) or not user_id.strip():
        raise AuthenticationError(
            code="user_context_malformed",
            message="API key user-resolution hook must provide a userId",
        )

    identity.setdefault("userId", user_id)
    identity.setdefault("subject", user_id)
    context["identity"] = identity
    context["userId"] = user_id
    context.setdefault("roles", [])
    context.setdefault("groups", [])
    context.setdefault("claims", {})

    return context
