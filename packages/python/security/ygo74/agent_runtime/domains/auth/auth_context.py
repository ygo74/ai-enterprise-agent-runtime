from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class UserIdentity:
    """Normalized identity of the authenticated caller.

    Args:
        user_id (str): Stable identifier of the authenticated user.
        subject (str | None): JWT subject claim identifying the authenticated principal.
        username (str | None): Optional username projected from authenticated claims.
        name (str | None): The name used to locate or label the value.
        given_name (str | None): Optional given name projected from authenticated claims.
        family_name (str | None): Optional family name projected from authenticated claims.
        email (str | None): Email claim associated with the authenticated principal.
        email_verified (bool | None): Whether the identity provider verified the email claim.
    """
    user_id: str
    subject: str | None = None
    username: str | None = None
    name: str | None = None
    given_name: str | None = None
    family_name: str | None = None
    email: str | None = None
    email_verified: bool | None = None

    def to_dict(self) -> dict[str, Any]:
        """Serialize the instance runtime data into its documented dictionary representation.
        """
        return {
            "userId": self.user_id,
            "subject": self.subject or self.user_id,
            "username": self.username,
            "name": self.name,
            "givenName": self.given_name,
            "familyName": self.family_name,
            "email": self.email,
            "emailVerified": self.email_verified,
        }


@dataclass(slots=True)
class ResolvedUser:
    """Return schema of an API key user-resolution hook.

    This is the contract a developer must satisfy when mapping an API key to a
    user: whatever is populated here is what the handler will find in its
    ``auth_context``.

    Args:
        user_id (str): Stable identifier of the authenticated user.
        username (str | None): Optional username projected from authenticated claims.
        name (str | None): The name used to locate or label the value.
        given_name (str | None): Optional given name projected from authenticated claims.
        family_name (str | None): Optional family name projected from authenticated claims.
        email (str | None): Email claim associated with the authenticated principal.
        email_verified (bool | None): Whether the identity provider verified the email claim.
        roles (list[str]): Role values projected from authenticated identity claims.
        groups (list[str]): Group memberships projected from authenticated claims.
        scopes (list[str]): OAuth scopes projected from the authenticated claims.
        tenant_id (str | None): Optional tenant identifier projected from the identity.
        claims (dict[str, Any]): The validated identity claims to project into runtime context.
    """
    user_id: str
    username: str | None = None
    name: str | None = None
    given_name: str | None = None
    family_name: str | None = None
    email: str | None = None
    email_verified: bool | None = None
    roles: list[str] = field(default_factory=list)
    groups: list[str] = field(default_factory=list)
    scopes: list[str] = field(default_factory=list)
    tenant_id: str | None = None
    claims: dict[str, Any] = field(default_factory=dict)

    def to_identity(self) -> UserIdentity:
        """Project an authenticated user context into the identity fields consumed by authorization.
        """
        return UserIdentity(
            user_id=self.user_id,
            subject=self.user_id,
            username=self.username,
            name=self.name,
            given_name=self.given_name,
            family_name=self.family_name,
            email=self.email,
            email_verified=self.email_verified,
        )


@dataclass(slots=True)
class AuthenticatedUserContext:
    """Normalized authentication context handed to the handler.

    ``to_dict`` produces the wire shape required by the Standard Exchange
    contract (``userId`` and ``authType`` at the top level).

    Args:
        auth_type (str): Name of the authentication mechanism that established this context, such as JWT or API key authentication.
        identity (UserIdentity): Identifier required to correlate a route, content item, tool call, or user.
        roles (list[str]): Role values projected from authenticated identity claims.
        groups (list[str]): Group memberships projected from authenticated claims.
        scopes (list[str]): OAuth scopes projected from the authenticated claims.
        claims (dict[str, Any]): The validated identity claims to project into runtime context.
        tenant_id (str | None): Optional tenant identifier projected from the identity.
    """
    auth_type: str
    identity: UserIdentity
    roles: list[str] = field(default_factory=list)
    groups: list[str] = field(default_factory=list)
    scopes: list[str] = field(default_factory=list)
    claims: dict[str, Any] = field(default_factory=dict)
    tenant_id: str | None = None

    @property
    def user_id(self) -> str:
        """Return the stable user identifier runtime data from authenticated identity context.
        """
        return self.identity.user_id

    def has_role(self, role: str) -> bool:
        """Determine whether the identity has the requested role runtime data using projected role claims.

        Args:
            role (str): Message role used to decide whether content is assistant output.
        """
        return role in self.roles

    def has_scope(self, scope: str) -> bool:
        """Determine whether the identity has the requested scope runtime data using projected scope claims.

        Args:
            scope (str): OAuth scope checked against the authenticated user context.
        """
        return scope in self.scopes

    def to_dict(self) -> dict[str, Any]:
        """Serialize the instance runtime data into its documented dictionary representation.
        """
        context: dict[str, Any] = {
            "authType": self.auth_type,
            "userId": self.identity.user_id,
            "identity": self.identity.to_dict(),
            "roles": list(self.roles),
            "groups": list(self.groups),
            "scopes": list(self.scopes),
            "claims": dict(self.claims),
        }

        if self.tenant_id is not None:
            context["tenantId"] = self.tenant_id

        return context
