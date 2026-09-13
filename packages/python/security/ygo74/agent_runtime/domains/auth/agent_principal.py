"""Who the agent is acting for, established outside the application.

A serving surface authenticates a caller; the application must be *told* who that
is rather than configured with it. :class:`AgentPrincipal` is the result of that
authentication - a subject, an optional address, a display name and the roles the
identity provider asserted.

It is deliberately *not* a token. It carries no credential, so it may reach a log,
an audit record or a prompt without leaking anything, and it is immutable, so the
identity a piece of state is keyed by cannot be changed after the fact.

Two things this model deliberately does not do:

* It does not build an authorisation. Turning roles into permissions is an
  application decision, and an identity that knew how to grant itself rights
  would be the wrong shape.
* It does not read a claim it has not modelled. What an application receives is
  exactly what is declared here, so it cannot grow a dependency on a token's
  internals by accident.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Final

from pydantic import BaseModel, ConfigDict, Field

from ygo74.agent_runtime.domains.auth.auth_context import AuthenticatedUserContext
from ygo74.agent_runtime.domains.security.security_errors import SecurityError

_IDENTITY: Final = "identity"
_SUBJECT: Final = "subject"
_USER_ID: Final = "userId"
_EMAIL: Final = "email"
_NAME: Final = "name"
_USERNAME: Final = "username"
_ROLES: Final = "roles"


class PrincipalError(SecurityError):
    """Raised when an authenticated caller cannot be turned into a principal.

    Failing here is a refusal to serve, never a fallback to an anonymous or
    default identity: acting for "somebody" is how one caller's data ends up
    answering for another.
    """


class AgentPrincipal(BaseModel):
    """An authenticated caller, without any credential.

    Attributes:
        subject: Stable identifier of the person, as asserted by the identity
            provider. This is what conversation state, ledgers and audit entries
            are partitioned by, so it must never be derived from client-supplied
            data.
        email: Address of the person, when the identity provider asserts one.
            Optional because it is an attribute of an identity rather than a
            requirement of every agent: a mailbox is addressed by e-mail, a wiki
            account is not. An agent that needs one says so itself, through
            ``require_email``, and fails loudly when it is absent, rather than
            this model demanding it of agents that do not.
        display_name: Human-readable name, for prompts and confirmations.
        roles: Roles asserted by the identity provider. They are claims about the
            caller, not permissions: mapping them to permissions is a decision of
            the application.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    subject: str = Field(min_length=1)
    email: str = ""
    display_name: str = ""
    roles: frozenset[str] = frozenset()

    @classmethod
    def from_context(
        cls,
        context: AuthenticatedUserContext,
        *,
        require_email: bool = True,
    ) -> AgentPrincipal:
        """Build a principal from the context the authenticator produced.

        This is the typed path, and the one to prefer: it needs no dictionary and
        cannot misread a key.
        """
        identity = context.identity
        return cls._build(
            subject=_text(identity.subject) or _text(identity.user_id),
            email=_text(identity.email),
            display_name=_text(identity.name) or _text(identity.username),
            roles=frozenset(_text(role) for role in context.roles if _text(role)),
            require_email=require_email,
        )

    @classmethod
    def from_auth_context(
        cls,
        context: Mapping[str, object] | None,
        *,
        require_email: bool = True,
    ) -> AgentPrincipal:
        """Build a principal from the wire-shaped authentication context.

        This is the shape an endpoint hands to a handler: loosely typed, because
        it crossed a transport boundary. This is the single place allowed to read
        it, so the rest of an application keeps working with a typed model.

        The subject is taken from the verified authentication context and never
        from the request body: a caller must not be able to name themselves.

        Args:
            context: The authentication context the transport established.
            require_email: Whether a caller without an address is refused. An
                agent that addresses its subject by e-mail leaves this at its
                default; an agent whose accounts are not e-mail addresses passes
                ``False`` rather than inventing an address to satisfy this model.
        """
        if not context:
            raise PrincipalError("the request carried no authenticated caller")

        identity = context.get(_IDENTITY)
        identity_map: Mapping[str, object] = identity if isinstance(identity, Mapping) else {}

        return cls._build(
            subject=(
                _text(identity_map.get(_SUBJECT))
                or _text(identity_map.get(_USER_ID))
                or _text(context.get(_USER_ID))
            ),
            email=_text(identity_map.get(_EMAIL)),
            display_name=_text(identity_map.get(_NAME)) or _text(identity_map.get(_USERNAME)),
            roles=_texts(context.get(_ROLES)),
            require_email=require_email,
        )

    @classmethod
    def _build(
        cls,
        *,
        subject: str,
        email: str,
        display_name: str,
        roles: frozenset[str],
        require_email: bool,
    ) -> AgentPrincipal:
        """Apply the two refusals both entry points share."""
        if not subject:
            raise PrincipalError("the authenticated caller carries no subject")
        if require_email and not email:
            raise PrincipalError(f"the authenticated caller {subject!r} carries no email address")
        return cls(subject=subject, email=email, display_name=display_name, roles=roles)

    def has_role(self, role: str) -> bool:
        """Whether the identity provider asserted a role for this caller."""
        return role in self.roles


def _text(value: object) -> str:
    """Return a non-empty stripped string, or nothing at all."""
    if not isinstance(value, str):
        return ""
    return value.strip()


def _texts(value: object) -> frozenset[str]:
    """Return the non-empty strings of a wire-shaped list, ignoring the rest."""
    if not isinstance(value, (list, tuple, set, frozenset)):
        return frozenset()
    return frozenset(text for item in value if (text := _text(item)))
