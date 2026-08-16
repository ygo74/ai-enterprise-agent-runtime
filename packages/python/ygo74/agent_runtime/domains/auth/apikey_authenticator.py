from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Protocol

from ygo74.agent_runtime.domains.auth.auth_context import AuthenticatedUserContext, ResolvedUser
from ygo74.agent_runtime.domains.auth.auth_errors import AuthenticationError


class ApiKeyUserResolver(Protocol):
    """Contract a developer implements to map an API key to a user.

    Returning ``None`` means the key is unknown and the request is rejected with
    ``api_key_invalid``. The returned :class:`ResolvedUser` defines exactly which
    user information is loaded into the handler's ``auth_context``.
    """

    def resolve_user(self, api_key: str) -> ResolvedUser | None:
        ...


@dataclass(slots=True)
class StaticApiKeyUserResolver:
    """In-memory resolver, mostly useful for local development and tests."""

    users_by_key: dict[str, ResolvedUser]

    def resolve_user(self, api_key: str) -> ResolvedUser | None:
        return self.users_by_key.get(api_key)


class ApiKeyAuthenticator:
    """Authenticates callers presenting an API key header.

    The raw key is never propagated into the resulting context: only the user
    information returned by the resolver is exposed to the handler.
    """

    DEFAULT_HEADER_NAME = "x-api-key"

    def __init__(self, resolver: ApiKeyUserResolver, *, header_name: str = DEFAULT_HEADER_NAME) -> None:
        self._resolver = resolver
        self._header_name = header_name.lower()

    @property
    def auth_type(self) -> str:
        return "api_key"

    @property
    def header_name(self) -> str:
        return self._header_name

    def can_authenticate(self, headers: Mapping[str, Any]) -> bool:
        return bool(headers.get(self._header_name))

    def missing_credential_error(self) -> AuthenticationError:
        return AuthenticationError(
            code="api_key_header_missing",
            message=f"Missing {self._header_name} header",
        )

    def authenticate(self, headers: Mapping[str, Any]) -> AuthenticatedUserContext:
        api_key = headers.get(self._header_name)
        if not isinstance(api_key, str) or not api_key.strip():
            raise self.missing_credential_error()

        return self.authenticate_key(api_key)

    def authenticate_key(self, api_key: str) -> AuthenticatedUserContext:
        if not api_key:
            raise self.missing_credential_error()

        user = self._resolve(api_key)

        return AuthenticatedUserContext(
            auth_type=self.auth_type,
            identity=user.to_identity(),
            roles=list(user.roles),
            groups=list(user.groups),
            scopes=list(user.scopes),
            claims=dict(user.claims),
            tenant_id=user.tenant_id,
        )

    def _resolve(self, api_key: str) -> ResolvedUser:
        try:
            resolved: object = self._resolver.resolve_user(api_key)
        except AuthenticationError:
            raise
        except Exception as ex:
            raise AuthenticationError(
                code="user_resolution_failed",
                message="API key user-resolution hook raised an error",
            ) from ex

        if resolved is None:
            raise AuthenticationError(code="api_key_invalid", message="API key is not recognized")

        if not isinstance(resolved, ResolvedUser):
            raise AuthenticationError(
                code="user_context_malformed",
                message="API key user-resolution hook must return a ResolvedUser",
            )

        if not resolved.user_id or not resolved.user_id.strip():
            raise AuthenticationError(
                code="user_context_malformed",
                message="API key user-resolution hook must provide a user_id",
            )

        return resolved
