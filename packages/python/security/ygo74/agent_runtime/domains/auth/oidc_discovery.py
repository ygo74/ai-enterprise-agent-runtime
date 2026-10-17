"""Finding where an issuer publishes its signing keys.

A JWKS URL used to be derived by appending a path to the issuer. That path -
``/protocol/openid-connect/certs`` - is Keycloak's layout, not a standard, and the
derivation silently produced a wrong URL for every other provider. The failure
then surfaced as "signing key unavailable" on a correctly configured realm, which
points at the token rather than at the guess that was made about the server.

OpenID Connect already answers the question. ``/.well-known/openid-configuration``
is part of the specification, every compliant provider serves it, and its
``jwks_uri`` is authoritative. Asking is both shorter and correct.

Remote metadata is retrieved by the security package's optional HTTPX client
owner. The same owner can be shared with JWKS resolution so the application
reuses one synchronous pool for an issuer.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ygo74.agent_runtime.domains.auth.auth_errors import AuthenticationError
from ygo74.agent_runtime.domains.http.client_lifecycle import SyncHttpClientOwner

DISCOVERY_PATH = "/.well-known/openid-configuration"
DEFAULT_TIMEOUT_SECONDS = 5


@dataclass(slots=True)
class OidcDiscovery:
    """Resolves an issuer to the URL of its key set.

    Args:
        timeout_seconds: How long to wait for the discovery document. Short on
            purpose: this runs while a service is starting, and a provider that
            cannot answer quickly is a configuration problem to report rather
            than a delay to absorb.
        _cache (dict[str, str]): Cached discovery or token values keyed by their lookup identity.
        http_client_owner (SyncHttpClientOwner | None): Optional application-owned
            synchronous HTTPX client lifecycle shared with JWKS resolution.
    """
    timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS
    _cache: dict[str, str] = field(default_factory=dict, init=False, repr=False)
    http_client_owner: SyncHttpClientOwner | None = field(default=None, repr=False)
    _owns_http_client_owner: bool = field(default=False, init=False, repr=False)

    def __post_init__(self) -> None:
        """Create a private lazy owner unless the application supplied one."""
        if self.timeout_seconds <= 0:
            raise ValueError("OIDC discovery timeout must be positive")
        if self.http_client_owner is None:
            self.http_client_owner = SyncHttpClientOwner()
            self._owns_http_client_owner = True

    def close(self) -> None:
        """Close the internally owned HTTP client after its authenticators stop."""
        if self._owns_http_client_owner and self.http_client_owner is not None:
            self.http_client_owner.close()

    def jwks_url(self, issuer: str) -> str:
        """Return the ``jwks_uri`` the issuer advertises.

        Raises:
            AuthenticationError: the issuer is empty, unreachable, or serves a
                document that declares no key set.

        Args:
            issuer (str): Expected JWT or OIDC issuer.
        """
        trimmed = issuer.strip().rstrip("/")
        if not trimmed:
            raise AuthenticationError(
                code="issuer_not_configured",
                message="an issuer is required to discover its signing keys",
            )
        if trimmed in self._cache:
            return self._cache[trimmed]

        document = self._fetch(f"{trimmed}{DISCOVERY_PATH}")
        if not isinstance(document, dict):
            # Checked here rather than only where the document is read, so the
            # guard holds however a subclass chose to obtain it.
            raise AuthenticationError(
                code="discovery_malformed",
                message=f"the OpenID configuration of {trimmed!r} is not an object",
            )
        jwks_uri = document.get("jwks_uri")
        if not isinstance(jwks_uri, str) or not jwks_uri:
            raise AuthenticationError(
                code="jwks_uri_missing",
                message=f"the discovery document of {trimmed!r} declares no jwks_uri",
            )
        self._cache[trimmed] = jwks_uri
        return jwks_uri

    def _fetch(self, url: str) -> dict[str, Any]:
        """Read one discovery document.

        Args:
            url (str): Absolute URL associated with a citation or remote resource.
        """
        try:
            if self.http_client_owner is None:
                raise RuntimeError("OIDC HTTP client owner is unavailable")
            payload = self.http_client_owner.get_json(
                url,
                service_identity=url.removesuffix(DISCOVERY_PATH),
                timeout_seconds=self.timeout_seconds,
            )
        except Exception:  # noqa: BLE001 - Hide untrusted provider error details.
            raise AuthenticationError(
                code="discovery_unavailable",
                message=f"could not read the OpenID configuration at {url!r}",
            ) from None

        if not isinstance(payload, dict):
            raise AuthenticationError(
                code="discovery_malformed",
                message=f"the OpenID configuration at {url!r} is not an object",
            )
        return payload
