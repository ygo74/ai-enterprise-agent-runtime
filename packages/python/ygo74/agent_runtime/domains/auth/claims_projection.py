from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, cast

from ygo74.agent_runtime.domains.auth.auth_context import UserIdentity

_PROJECTED_CLAIM_KEYS = (
    "iss",
    "aud",
    "exp",
    "nbf",
    "iat",
    "jti",
    "scope",
    "roles",
    "name",
    "given_name",
    "family_name",
    "preferred_username",
    "email",
    "email_verified",
    "groups",
    "realm_access",
    "resource_access",
)


@dataclass(slots=True)
class ClaimsProjector:
    """Projects raw OIDC claims into the normalized authentication context.

    ``roles_claim_path`` and ``groups_claim_path`` are dot-separated paths into
    the decoded claims (for example ``realm_access.roles`` or
    ``resource_access.<client>.roles``), mirroring the
    ``OPENID_REQUIRED_ROLE_PARAMETER_PATH`` style of configuration used by OIDC
    providers such as Keycloak.
    """

    roles_claim_path: str | None = None
    groups_claim_path: str | None = None

    def identity(self, claims: Mapping[str, Any], subject: str) -> UserIdentity:
        email_verified = claims.get("email_verified")

        return UserIdentity(
            user_id=subject,
            subject=subject,
            username=self._optional_str(claims.get("preferred_username")),
            name=self._optional_str(claims.get("name")),
            given_name=self._optional_str(claims.get("given_name")),
            family_name=self._optional_str(claims.get("family_name")),
            email=self._optional_str(claims.get("email")),
            email_verified=email_verified if isinstance(email_verified, bool) else None,
        )

    def roles(self, claims: Mapping[str, Any]) -> list[str]:
        return self.values_at(claims, self.roles_claim_path)

    def groups(self, claims: Mapping[str, Any]) -> list[str]:
        return self.values_at(claims, self.groups_claim_path)

    def scopes(self, claims: Mapping[str, Any]) -> list[str]:
        scope = claims.get("scope")
        if isinstance(scope, str):
            return scope.split()

        return self._as_string_list(scope)

    def context_claims(self, claims: Mapping[str, Any]) -> dict[str, Any]:
        return {key: claims[key] for key in _PROJECTED_CLAIM_KEYS if key in claims}

    def values_at(self, claims: Mapping[str, Any], path: str | None) -> list[str]:
        if not path:
            return []

        return self._as_string_list(self.resolve_path(claims, path))

    @staticmethod
    def resolve_path(claims: Mapping[str, Any], path: str) -> Any:
        value: Any = claims
        for part in path.split("."):
            if not isinstance(value, Mapping):
                return None

            current = cast("Mapping[str, Any]", value)
            if part not in current:
                return None

            value = current[part]

        return value

    @staticmethod
    def _as_string_list(value: Any) -> list[str]:
        if isinstance(value, str):
            return [value]

        if isinstance(value, (list, tuple)):
            items = cast("list[Any] | tuple[Any, ...]", value)
            return [str(item) for item in items]

        return []

    @staticmethod
    def _optional_str(value: Any) -> str | None:
        return value if isinstance(value, str) else None
