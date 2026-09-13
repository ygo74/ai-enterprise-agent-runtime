"""Finding where an issuer publishes its signing keys.

A JWKS URL used to be derived by appending a path to the issuer. That path -
``/protocol/openid-connect/certs`` - is Keycloak's layout, not a standard, and the
derivation silently produced a wrong URL for every other provider. The failure
then surfaced as "signing key unavailable" on a correctly configured realm, which
points at the token rather than at the guess that was made about the server.

OpenID Connect already answers the question. ``/.well-known/openid-configuration``
is part of the specification, every compliant provider serves it, and its
``jwks_uri`` is authoritative. Asking is both shorter and correct.

Only the standard library is used, so this adds no dependency: ``PyJWT`` already
fetches the key set itself once given the URL.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from typing import Any

from ygo74.agent_runtime.domains.auth.auth_errors import AuthenticationError

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
    """

    timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS
    _cache: dict[str, str] = field(default_factory=dict, init=False, repr=False)

    def jwks_url(self, issuer: str) -> str:
        """Return the ``jwks_uri`` the issuer advertises.

        Raises:
            AuthenticationError: the issuer is empty, unreachable, or serves a
                document that declares no key set.
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
        """Read one discovery document."""
        try:
            with urllib.request.urlopen(url, timeout=self.timeout_seconds) as response:  # noqa: S310 - https URL from configuration
                payload = json.loads(response.read())
        except (urllib.error.URLError, TimeoutError, ValueError) as error:
            raise AuthenticationError(
                code="discovery_unavailable",
                message=f"could not read the OpenID configuration at {url!r}",
            ) from error

        if not isinstance(payload, dict):
            raise AuthenticationError(
                code="discovery_malformed",
                message=f"the OpenID configuration at {url!r} is not an object",
            )
        return payload
