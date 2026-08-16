"""The same AgentAccessPolicy gates discovery listing/retrieval and invocation.

A caller denied access to an agent must never see it in ``GET /v1/models``,
must get a not-found (not a 403) from ``GET /v1/models/{id}``, and must be
denied with a 403 on every invocation surface -- all from one policy object,
so the developer no longer duplicates the check inside each entrypoint.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any

import httpx
import pytest
from discovery_fixtures import FIXED_CREATED_AT, make_descriptor
from fastapi import FastAPI

from ygo74.agent_runtime import ApiKeyUserResolver, ResolvedUser
from ygo74.agent_runtime.domains.auth.auth_context import AuthenticatedUserContext, UserIdentity
from ygo74.agent_runtime.domains.discovery.agent_access_policy import AgentAccessPolicy, RoleRequiredAccessPolicy
from ygo74.agent_runtime.domains.discovery.agent_descriptor import AgentCapabilitySet, AgentDescriptor, AgentSkill
from ygo74.agent_runtime.domains.discovery.descriptor_registry import DescriptorRegistry
from ygo74.agent_runtime.domains.discovery.discovery_configuration import DiscoveryConfiguration
from ygo74.agent_runtime.domains.endpoints.fastapi_endpoints import add_ai_endpoints

ADMIN_KEY = "admin-key"
GUEST_KEY = "guest-key"


class _StaticResolver(ApiKeyUserResolver):
    def __init__(self, users: dict[str, ResolvedUser]) -> None:
        self._users = users

    def resolve_user(self, api_key: str) -> ResolvedUser | None:
        return self._users.get(api_key)


@dataclass(slots=True)
class _RaisingPolicy:
    """A policy that always raises, used to prove failures fail closed."""

    def is_authorized(self, descriptor: AgentDescriptor, auth_context: AuthenticatedUserContext | None) -> bool:
        raise RuntimeError("boom")


@dataclass(slots=True)
class _AdminOnlyTagPolicy:
    """Denies access to any descriptor tagged ``admin-only`` unless the caller has the admin role."""

    def is_authorized(self, descriptor: AgentDescriptor, auth_context: AuthenticatedUserContext | None) -> bool:
        if "admin-only" not in descriptor.tags:
            return True
        return auth_context is not None and auth_context.has_role("admin")


def _admin_only_descriptor() -> AgentDescriptor:
    return AgentDescriptor(
        agent_id="billing",
        route_key="route-billing",
        display_name="billing display",
        description="Agent billing.",
        version="1.0.0",
        owner="platform-team",
        created_at_utc=FIXED_CREATED_AT,
        capabilities=AgentCapabilitySet(streaming=False),
        tags=("admin-only",),
        skills=(AgentSkill(skill_id="faq", name="FAQ", description="Answers questions."),),
        security_schemes=("jwt",),
    )


def _headers(api_key: str | None) -> dict[str, str] | None:
    return {"x-api-key": api_key} if api_key else None


def _call(app: FastAPI, method: str, path: str, **kwargs: Any) -> httpx.Response:
    async def _do() -> httpx.Response:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            return await client.request(method, path, **kwargs)

    return asyncio.run(_do())


@pytest.fixture
def app_and_seen() -> tuple[FastAPI, list[dict[str, Any]]]:
    seen: list[dict[str, Any]] = []

    def entrypoint(payload: dict[str, Any]) -> dict[str, Any]:
        seen.append(payload)
        return {"output": f"handled by {payload['route_key']}"}

    resolver = _StaticResolver(
        {
            ADMIN_KEY: ResolvedUser(user_id="admin-1", roles=["admin"]),
            GUEST_KEY: ResolvedUser(user_id="guest-1", roles=[]),
        }
    )

    app = FastAPI()
    add_ai_endpoints(
        app,
        entrypoint,
        default_route_key="fallback",
        api_key_resolver=resolver,
        descriptor_registry=DescriptorRegistry([_admin_only_descriptor(), make_descriptor("support")]),
        discovery=DiscoveryConfiguration(enable_openai_models=True, enable_anthropic_models=True),
        authorization_policy=_AdminOnlyTagPolicy(),
    )
    return app, seen


def test_a_denied_agent_is_absent_from_the_listing_for_an_unauthorized_caller(
    app_and_seen: tuple[FastAPI, list[dict[str, Any]]],
) -> None:
    app, _ = app_and_seen

    response = _call(app, "GET", "/v1/models", headers=_headers(GUEST_KEY))

    ids = [entry["id"] for entry in response.json()["data"]]
    assert ids == ["support"]


def test_an_authorized_caller_sees_the_full_listing(
    app_and_seen: tuple[FastAPI, list[dict[str, Any]]],
) -> None:
    app, _ = app_and_seen

    response = _call(app, "GET", "/v1/models", headers=_headers(ADMIN_KEY))

    ids = sorted(entry["id"] for entry in response.json()["data"])
    assert ids == ["billing", "support"]


def test_an_anonymous_caller_only_sees_the_public_agent(
    app_and_seen: tuple[FastAPI, list[dict[str, Any]]],
) -> None:
    app, _ = app_and_seen

    response = _call(app, "GET", "/v1/models", headers=None)

    ids = [entry["id"] for entry in response.json()["data"]]
    assert ids == ["support"]


def test_direct_retrieval_of_a_denied_agent_is_not_found_not_forbidden(
    app_and_seen: tuple[FastAPI, list[dict[str, Any]]],
) -> None:
    app, _ = app_and_seen

    response = _call(app, "GET", "/v1/models/billing", headers=_headers(GUEST_KEY))

    assert response.status_code == 404


def test_invocation_of_a_denied_agent_is_forbidden_and_never_reaches_the_entrypoint(
    app_and_seen: tuple[FastAPI, list[dict[str, Any]]],
) -> None:
    app, seen = app_and_seen

    response = _call(
        app,
        "POST",
        "/v1/responses",
        json={"model": "billing", "input": "hello"},
        headers=_headers(GUEST_KEY),
    )

    assert response.status_code == 403
    assert response.json()["detail"]["error"]["code"] == "agent_access_denied"
    assert seen == []


def test_invocation_of_an_authorized_agent_succeeds(
    app_and_seen: tuple[FastAPI, list[dict[str, Any]]],
) -> None:
    app, seen = app_and_seen

    response = _call(
        app,
        "POST",
        "/v1/responses",
        json={"model": "billing", "input": "hello"},
        headers=_headers(ADMIN_KEY),
    )

    assert response.status_code == 200
    assert seen[0]["route_key"] == "route-billing"


def test_role_required_access_policy_denies_callers_missing_the_role() -> None:
    policy: AgentAccessPolicy = RoleRequiredAccessPolicy(required_role="admin")
    descriptor = make_descriptor("any-agent")

    assert policy.is_authorized(descriptor, None) is False
    assert (
        policy.is_authorized(
            descriptor,
            AuthenticatedUserContext(auth_type="api_key", identity=UserIdentity(user_id="u1"), roles=["viewer"]),
        )
        is False
    )
    assert (
        policy.is_authorized(
            descriptor,
            AuthenticatedUserContext(auth_type="api_key", identity=UserIdentity(user_id="u1"), roles=["admin"]),
        )
        is True
    )


def test_role_required_access_policy_allows_everyone_when_no_role_is_configured() -> None:
    policy: AgentAccessPolicy = RoleRequiredAccessPolicy(required_role="")
    descriptor = make_descriptor("any-agent")

    assert policy.is_authorized(descriptor, None) is True


# A raising policy fails closed: an unevaluated agent must never be exposed
# (listed, retrieved, or invoked) as if it had been authorized.


def _raising_policy_app() -> FastAPI:
    def entrypoint(payload: dict[str, Any]) -> dict[str, Any]:
        return {"output": f"handled by {payload['route_key']}"}

    app = FastAPI()
    add_ai_endpoints(
        app,
        entrypoint,
        default_route_key="fallback",
        descriptor_registry=DescriptorRegistry([make_descriptor("support")]),
        discovery=DiscoveryConfiguration(enable_openai_models=True, enable_anthropic_models=True),
        authorization_policy=_RaisingPolicy(),
    )
    return app


def test_a_raising_policy_excludes_the_agent_from_the_listing() -> None:
    app = _raising_policy_app()

    response = _call(app, "GET", "/v1/models")

    assert response.json()["data"] == []


def test_a_raising_policy_reports_direct_retrieval_as_not_found() -> None:
    app = _raising_policy_app()

    response = _call(app, "GET", "/v1/models/support")

    assert response.status_code == 404


def test_a_raising_policy_denies_invocation_with_403_not_500() -> None:
    app = _raising_policy_app()

    response = _call(app, "POST", "/v1/responses", json={"model": "support", "input": "hello"})

    assert response.status_code == 403
    assert response.json()["detail"]["error"]["code"] == "agent_access_denied"
