"""Tests of the authenticated caller a handler acts for.

One property matters above the rest, and it is a security property rather than a
convenience: a principal must never be invented when authentication produced
nothing, because acting for "somebody" is how one caller's data ends up answering
for another.
"""

from __future__ import annotations

from typing import Any

import pytest
from ygo74.agent_runtime.domains.auth.agent_principal import (
    AgentPrincipal,
    PrincipalError,
)
from ygo74.agent_runtime.domains.auth.auth_context import (
    AuthenticatedUserContext,
    UserIdentity,
)


def auth_context(**overrides: Any) -> dict[str, Any]:
    """Build the wire shape an endpoint hands to a handler."""
    identity: dict[str, Any] = {
        "subject": "3f9a-user",
        "userId": "3f9a-user",
        "email": "ada@example.com",
        "name": "Ada Lovelace",
    }
    identity.update(overrides.pop("identity", {}))
    context: dict[str, Any] = {
        "authType": "jwt",
        "userId": "3f9a-user",
        "identity": identity,
        "roles": ["agent-user"],
    }
    context.update(overrides)
    return context


def test_it_reads_the_subject_the_address_and_the_name() -> None:
    principal = AgentPrincipal.from_auth_context(auth_context())

    assert principal.subject == "3f9a-user"
    assert principal.email == "ada@example.com"
    assert principal.display_name == "Ada Lovelace"


def test_it_keeps_the_roles_the_provider_asserted() -> None:
    principal = AgentPrincipal.from_auth_context(auth_context(roles=["agent-user", "auditor"]))

    assert principal.has_role("auditor")
    assert not principal.has_role("admin")


def test_it_falls_back_to_the_username_for_display() -> None:
    principal = AgentPrincipal.from_auth_context(auth_context(identity={"name": None, "username": "ada"}))

    assert principal.display_name == "ada"


def test_it_ignores_roles_that_are_not_text() -> None:
    """A wire payload is third-party data: it may contain anything."""
    principal = AgentPrincipal.from_auth_context(auth_context(roles=["agent-user", 7, None, "  "]))

    assert principal.roles == frozenset({"agent-user"})


def test_it_accepts_a_subject_carried_only_at_the_top_level() -> None:
    context = auth_context(identity={"subject": None, "userId": None})

    assert AgentPrincipal.from_auth_context(context).subject == "3f9a-user"


@pytest.mark.parametrize("context", [None, {}])
def test_an_absent_authentication_is_refused(context: dict[str, Any] | None) -> None:
    with pytest.raises(PrincipalError, match="no authenticated caller"):
        AgentPrincipal.from_auth_context(context)


def test_a_caller_without_a_subject_is_refused() -> None:
    with pytest.raises(PrincipalError, match="no subject"):
        AgentPrincipal.from_auth_context(auth_context(userId=None, identity={"subject": None, "userId": None}))


def test_a_caller_without_an_address_is_refused_by_default() -> None:
    """An agent addressing its subject by e-mail cannot be made to guess one."""
    with pytest.raises(PrincipalError, match="no email"):
        AgentPrincipal.from_auth_context(auth_context(identity={"email": None}))


def test_a_principal_cannot_be_mutated_after_authentication() -> None:
    principal = AgentPrincipal.from_auth_context(auth_context())

    with pytest.raises(ValueError, match="frozen"):
        principal.subject = "somebody-else"  # type: ignore[misc]


def test_an_agent_that_does_not_address_by_email_accepts_a_caller_without_one() -> None:
    principal = AgentPrincipal.from_auth_context(
        auth_context(identity={"email": None}),
        require_email=False,
    )

    assert principal.subject == "3f9a-user"
    assert principal.email == ""


def test_an_address_is_still_kept_when_the_provider_asserts_one() -> None:
    principal = AgentPrincipal.from_auth_context(auth_context(), require_email=False)

    assert principal.email == "ada@example.com"


def test_the_subject_is_mandatory_even_without_an_address() -> None:
    """The subject is what state is partitioned by, so it is never optional."""
    with pytest.raises(PrincipalError, match="no subject"):
        AgentPrincipal.from_auth_context(
            auth_context(userId=None, identity={"subject": None, "userId": None}),
            require_email=False,
        )


def test_relaxing_the_address_never_relaxes_the_need_for_a_caller() -> None:
    with pytest.raises(PrincipalError, match="no authenticated caller"):
        AgentPrincipal.from_auth_context(None, require_email=False)


def test_the_typed_path_reads_the_same_identity_as_the_wire_path() -> None:
    """``from_context`` exists so a host never has to serialise and re-parse."""
    context = AuthenticatedUserContext(
        auth_type="jwt",
        identity=UserIdentity(
            user_id="3f9a-user",
            subject="3f9a-user",
            email="ada@example.com",
            name="Ada Lovelace",
        ),
        roles=["agent-user"],
    )

    assert AgentPrincipal.from_context(context) == AgentPrincipal.from_auth_context(context.to_dict())


def test_the_typed_path_refuses_an_identity_without_a_subject() -> None:
    context = AuthenticatedUserContext(auth_type="apiKey", identity=UserIdentity(user_id=""))

    with pytest.raises(PrincipalError, match="no subject"):
        AgentPrincipal.from_context(context, require_email=False)
