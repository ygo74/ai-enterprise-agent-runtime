"""Tests of the permission model.

A permission is declared by the domain that owns it, never by a central list in
this library. What matters here is that a host can add a second domain without
touching the first, and that configuration naming a permission in text can never
invent one.
"""

from __future__ import annotations

import pytest

from ygo74.agent_runtime.domains.security.permissions import (
    Permission,
    PermissionRegistry,
    UnknownPermissionError,
)

MAIL_READ = Permission("mail", "read")
MAIL_SEND = Permission("mail", "send")
JIRA_READ = Permission("jira", "read")


def test_permission_renders_as_domain_and_action() -> None:
    assert MAIL_SEND.value == "mail:send"
    assert str(MAIL_SEND) == "mail:send"


def test_two_declarations_of_the_same_permission_are_equal() -> None:
    assert Permission("mail", "read") == MAIL_READ
    assert len({Permission("mail", "read"), MAIL_READ}) == 1


def test_permissions_of_two_domains_never_collide() -> None:
    assert JIRA_READ != MAIL_READ


@pytest.mark.parametrize(("domain", "action"), [("", "read"), ("mail", ""), ("ma:il", "read")])
def test_a_malformed_permission_is_refused(domain: str, action: str) -> None:
    with pytest.raises(ValueError, match="invalid permission part"):
        Permission(domain, action)


def test_registry_resolves_a_declared_permission() -> None:
    registry = PermissionRegistry({MAIL_READ, MAIL_SEND})

    assert registry.resolve("mail:send") == MAIL_SEND


def test_registry_refuses_a_permission_no_domain_declared() -> None:
    registry = PermissionRegistry({MAIL_READ, MAIL_SEND})

    with pytest.raises(UnknownPermissionError, match="mail:delete"):
        registry.resolve("mail:delete")


def test_a_second_domain_extends_the_registry_without_touching_the_first() -> None:
    registry = PermissionRegistry({MAIL_READ, MAIL_SEND, JIRA_READ})

    assert registry.resolve("jira:read").domain == "jira"
    assert registry.resolve("mail:read") == MAIL_READ


def test_registry_reports_what_it_knows() -> None:
    registry = PermissionRegistry({MAIL_READ, JIRA_READ})

    assert registry.declared() == frozenset({MAIL_READ, JIRA_READ})
