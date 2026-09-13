from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, Protocol, runtime_checkable

from ygo74.agent_runtime.domains.auth.auth_context import AuthenticatedUserContext
from ygo74.agent_runtime.domains.auth.auth_errors import AuthenticationError


@runtime_checkable
class Authenticator(Protocol):
    """Contract implemented by every authentication scheme.

    ``RequestAuthenticator`` inspects the incoming headers and delegates to the
    first authenticator that claims them, so adding a scheme means adding a
    class implementing this protocol.
    """

    @property
    def auth_type(self) -> str:
        """Stable identifier projected as ``authContext.authType``."""
        ...

    def can_authenticate(self, headers: Mapping[str, Any]) -> bool:
        """Return True when the request carries a credential for this scheme."""
        ...

    def authenticate(self, headers: Mapping[str, Any]) -> AuthenticatedUserContext:
        """Validate the credential and project a normalized user context."""
        ...

    def missing_credential_error(self) -> AuthenticationError:
        """Error raised when authentication is required but no credential was sent."""
        ...


@dataclass(slots=True)
class RequestAuthenticator:
    """Selects and runs the authenticator matching the incoming request headers.

    Authenticators are evaluated in order and the first one claiming the request
    wins, so ordering expresses precedence (JWT before API key by convention).
    """

    authenticators: list[Authenticator] = field(default_factory=list)
    require_authentication: bool = False

    def authenticate(self, headers: Mapping[str, Any] | None) -> AuthenticatedUserContext | None:
        if headers is None:
            if self.require_authentication:
                raise self._missing_credential_error()
            return None

        for authenticator in self.authenticators:
            if authenticator.can_authenticate(headers):
                return authenticator.authenticate(headers)

        if self.require_authentication:
            raise self._missing_credential_error()

        return None

    def _missing_credential_error(self) -> AuthenticationError:
        if self.authenticators:
            return self.authenticators[0].missing_credential_error()

        return AuthenticationError(
            code="authentication_not_configured",
            message="Authentication is required but no authenticator is configured",
        )
