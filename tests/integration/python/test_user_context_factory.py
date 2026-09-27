"""Tests for creating an operation context from an authenticated principal."""

from __future__ import annotations

from ygo74.agent_runtime.domains.auth.agent_principal import AgentPrincipal
from ygo74.agent_runtime.domains.security.permissions import Permission
from ygo74.agent_runtime.domains.security.user_context_factory import UserContextFactory


def test_factory_uses_supplied_permissions_and_preserves_attribution() -> None:
    principal = AgentPrincipal(subject="user-17", email="user@example.com", roles=frozenset({"admin"}))
    permissions = iter((Permission("mail", "read"), Permission("mail", "draft")))

    context = UserContextFactory().for_principal(
        principal,
        session_id="conversation-4",
        permissions=permissions,
    )

    assert context.user_id == "user-17"
    assert context.session_id == "conversation-4"
    assert context.permissions == frozenset({Permission("mail", "read"), Permission("mail", "draft")})


def test_factory_does_not_translate_principal_roles_into_permissions() -> None:
    principal = AgentPrincipal(subject="user-17", roles=frozenset({"admin"}))

    context = UserContextFactory().for_principal(principal, session_id="conversation-4", permissions=())

    assert context.permissions == frozenset()
