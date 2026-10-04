from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Protocol

from ygo74.agent_runtime.domains.auth.auth_context import (
    AuthenticatedUserContext,
    ResolvedUser,
)
from ygo74.agent_runtime.domains.auth.auth_errors import AuthenticationError
from ygo74.agent_runtime.domains.auth.authenticator import Authenticator


class ApiKeyUserResolver(Protocol):
    """Contract a developer implements to map an API key to a user.

    Returning ``None`` means the key is unknown and the request is rejected with
    ``api_key_invalid``. The returned :class:`ResolvedUser` defines exactly which
    user information is loaded into the handler's ``auth_context``.
    """
    def resolve_user(self, api_key: str) -> ResolvedUser | None:
        """Resolve user using configuration and registered candidates.

        Args:
            api_key (str): API key presented by the caller; it is not copied into user-facing diagnostics.
        """
        ...


@dataclass(slots=True)
class StaticApiKeyUserResolver(ApiKeyUserResolver):
    """In-memory resolver, mostly useful for local development and tests.

    Args:
        users_by_key (dict[str, ResolvedUser]): API key lookup table mapping credentials to resolved users.
    """
    users_by_key: dict[str, ResolvedUser]

    def resolve_user(self, api_key: str) -> ResolvedUser | None:
        """Resolve user using configuration and registered candidates.

        Args:
            api_key (str): API key presented by the caller; it is not copied into user-facing diagnostics.
        """
        return self.users_by_key.get(api_key)


class ApiKeyAuthenticator(Authenticator):
    """Authenticates callers presenting an API key header.

    The raw key is never propagated into the resulting context: only the user
    information returned by the resolver is exposed to the handler.

    ``scheme`` exists because not every deployment carries its key in a header of
    its own. A server reached at ``Authorization: Bearer <secret>`` is presenting an
    API key wearing a scheme, and reading the raw header value there would resolve
    the literal string ``Bearer <secret>`` as the key. When a scheme is named, a
    header that does not carry it is not claimed at all - so this authenticator
    cannot swallow a credential meant for another one sharing the same header.

    Args:
        resolver (ApiKeyUserResolver): Callback that resolves a route key to its registered handler.
        header_name (str): Credential header accepted by the authentication scheme.
        scheme (str): Authentication scheme inspected for credentials or metadata.
    """
    DEFAULT_HEADER_NAME = "x-api-key"

    def __init__(
        self,
        resolver: ApiKeyUserResolver,
        *,
        header_name: str = DEFAULT_HEADER_NAME,
        scheme: str = "",
    ) -> None:
        """Initialize the instance API key credentials with supplied collaborators and configuration.

        Args:
            resolver (ApiKeyUserResolver): Callback that resolves a route key to its registered handler.
            header_name (str): Credential header accepted by the authentication scheme.
            scheme (str): Authentication scheme inspected for credentials or metadata.
        """
        self._resolver = resolver
        self._header_name = header_name.lower()
        self._scheme = scheme.strip().lower()

    @property
    def auth_type(self) -> str:
        """Return the authentication mechanism name API key credentials used for diagnostics and policy decisions.
        """
        return "api_key"

    @property
    def header_name(self) -> str:
        """Return the credential header name API key credentials accepted by this authenticator.
        """
        return self._header_name

    def can_authenticate(self, headers: Mapping[str, Any]) -> bool:
        """Determine whether the authenticator accepts this credential form API key credentials before verification.

        Args:
            headers (Mapping[str, Any]): The request headers used for protocol selection, forwarding, or authentication.
        """
        return bool(self._presented(headers))

    def missing_credential_error(self) -> AuthenticationError:
        """Create the missing-credential error API key credentials with scheme-specific response details.
        """
        return AuthenticationError(
            code="api_key_header_missing",
            message=f"Missing {self._header_name} header",
        )

    def _presented(self, headers: Mapping[str, Any]) -> str:
        """Return the key the request carries, or the empty string.

        The empty string means "not for me", which is what keeps a chain of
        authenticators sharing one header from stealing each other's requests.

        Args:
            headers (Mapping[str, Any]): The request headers used for protocol selection, forwarding, or authentication.
        """
        header = headers.get(self._header_name)
        if not isinstance(header, str) or not header.strip():
            return ""

        value = header.strip()
        if not self._scheme:
            return value

        name, separator, credential = value.partition(" ")
        if not separator or name.lower() != self._scheme:
            return ""
        return credential.strip()

    def authenticate(self, headers: Mapping[str, Any]) -> AuthenticatedUserContext:
        """Authenticate API key credentials and return identity context or a structured failure.

        Args:
            headers (Mapping[str, Any]): The request headers used for protocol selection, forwarding, or authentication.
        """
        api_key = self._presented(headers)
        if not api_key:
            raise self.missing_credential_error()

        return self.authenticate_key(api_key)

    def authenticate_key(self, api_key: str) -> AuthenticatedUserContext:
        """Authenticate key and return identity context or a structured failure.

        Args:
            api_key (str): API key presented by the caller; it is not copied into user-facing diagnostics.
        """
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
        """Resolve the presented API key through the application callback and validate its returned identity context.

        Args:
            api_key (str): API key presented by the caller; it is not copied into user-facing diagnostics.
        """
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
