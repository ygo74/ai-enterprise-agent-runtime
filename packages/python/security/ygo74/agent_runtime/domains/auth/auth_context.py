from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class UserIdentity:
    """Normalized identity of the authenticated caller."""

    user_id: str
    subject: str | None = None
    username: str | None = None
    name: str | None = None
    given_name: str | None = None
    family_name: str | None = None
    email: str | None = None
    email_verified: bool | None = None

    def to_dict(self) -> dict[str, Any]:
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
        return self.identity.user_id

    def has_role(self, role: str) -> bool:
        return role in self.roles

    def has_scope(self, scope: str) -> bool:
        return scope in self.scopes

    def to_dict(self) -> dict[str, Any]:
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
