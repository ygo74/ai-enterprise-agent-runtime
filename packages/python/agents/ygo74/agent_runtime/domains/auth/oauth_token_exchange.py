"""Generic OAuth token-exchange settings and RFC 8693 source implementation."""

from __future__ import annotations

import base64
import binascii
import json
import logging
from collections.abc import Callable
from dataclasses import dataclass
from importlib import import_module
from typing import TYPE_CHECKING, Any
from urllib.parse import urlsplit

from pydantic import SecretStr
from ygo74.agent_runtime.domains.auth.tokens import (
    AccessToken,
    DelegatedTokenRequest,
    TokenExchangeError,
)
from ygo74.agent_runtime.domains.http.client_lifecycle import (
    HttpxTransportFailureClassifier,
    RetryableHttpStatusError,
)
from ygo74.agent_runtime.domains.http.resilience import (
    DEFAULT_CIRCUIT_BREAKERS,
    CircuitBreakerSettings,
    CircuitOpenError,
    RetryExecutor,
    RetrySettings,
    ServiceCircuitBreakerRegistry,
)

if TYPE_CHECKING:
    from httpx import AsyncClient
else:
    AsyncClient = Any

_GRANT_TYPE = "urn:ietf:params:oauth:grant-type:token-exchange"
_ACCESS_TOKEN_TYPE = "urn:ietf:params:oauth:token-type:access_token"
_logger = logging.getLogger(__name__)
_SAFE_OAUTH_ERRORS = frozenset({
    "invalid_request",
    "invalid_client",
    "invalid_grant",
    "invalid_scope",
    "invalid_target",
    "invalid_token",
    "unauthorized_client",
    "unsupported_grant_type",
    "access_denied",
    "server_error",
    "temporarily_unavailable",
})


@dataclass(frozen=True, slots=True)
class OAuthTokenExchangeSettings:
    """Resolved OAuth token-exchange target and client settings.

    Args:
        token_url (str | None): HTTPS token endpoint for the exchange.
        client_id (str | None): OAuth client identity for the exchange.
        client_secret (SecretStr | None): Resolved credential, hidden in representations.
        audience (str): Downstream resource identifier.
        scopes (tuple[str, ...]): Requested scopes for the exchanged access token.

    Client fields remain optional as a group for callers that inject their own
    ``OAuthOnBehalfOfTokenSource`` and only need the target audience and scopes.
    """

    audience: str
    scopes: tuple[str, ...] = ()
    token_url: str | None = None
    client_id: str | None = None
    client_secret: SecretStr | None = None


class Rfc8693OAuthOnBehalfOfTokenSource:
    """Exchange a verified user token for a bearer token for one resource.

    The exchange uses OAuth client-secret Basic authentication and the standard
    RFC 8693 subject-token fields. A caller-provided HTTPX client remains owned
    by its caller; otherwise one bounded, certificate-validating client is
    created and closed for each exchange.

    Args:
        settings (OAuthTokenExchangeSettings): Resolved endpoint and client values.
        client (AsyncClient | None): Optional caller-owned HTTP client.
        client_provider (Callable[[], AsyncClient] | None): Optional lazy provider
            for an application-owned per-server client.
        timeout_seconds (float): Maximum duration of an exchange request.
        retry_settings (RetrySettings): Bounded retry policy for token exchange.
        breaker_settings (CircuitBreakerSettings): Per-token-service breaker policy.
        breaker_registry (ServiceCircuitBreakerRegistry): Shared service breaker state.
    """

    def __init__(
        self,
        settings: OAuthTokenExchangeSettings,
        *,
        client: AsyncClient | None = None,
        client_provider: Callable[[], AsyncClient] | None = None,
        timeout_seconds: float = 10.0,
        retry_settings: RetrySettings | None = None,
        breaker_settings: CircuitBreakerSettings | None = None,
        breaker_registry: ServiceCircuitBreakerRegistry = DEFAULT_CIRCUIT_BREAKERS,
    ) -> None:
        """Validate settings and retain the optional caller-owned HTTP client.

        Args:
            settings (OAuthTokenExchangeSettings): Resolved endpoint and client values.
            client (AsyncClient | None): Optional caller-owned HTTP client.
            client_provider (Callable[[], AsyncClient] | None): Optional lazy provider for an application-owned client.
            timeout_seconds (float): Maximum duration of an exchange request.
            retry_settings (RetrySettings | None): Bounded retry settings.
            breaker_settings (CircuitBreakerSettings | None): Optional service breaker override.
            breaker_registry (ServiceCircuitBreakerRegistry): Shared upstream breaker registry.

        Raises:
            ValueError: The client settings are incomplete or the endpoint is not HTTPS.
            RuntimeError: HTTPX is not installed.
        """
        self._httpx: Any = _load_httpx()
        if (
            settings.token_url is None
            or settings.client_id is None
            or settings.client_secret is None
        ):
            raise ValueError(
                "RFC 8693 token exchange requires complete OAuth client settings"
            )
        parsed_url = urlsplit(settings.token_url)
        if (
            parsed_url.scheme.casefold() != "https"
            or not parsed_url.hostname
            or parsed_url.username is not None
            or parsed_url.password is not None
        ):
            raise ValueError(
                "the OAuth token endpoint must be an HTTPS URL without embedded credentials"
            )
        if timeout_seconds <= 0:
            raise ValueError("the OAuth token-exchange timeout must be positive")
        if client is not None and client_provider is not None:
            raise ValueError("provide either a client or a client provider, not both")
        self._settings = settings
        self._token_url = settings.token_url
        self._client_id = settings.client_id
        self._client_secret = settings.client_secret
        self._client = client
        self._client_provider = client_provider
        self._timeout_seconds = timeout_seconds
        self._retry_settings = retry_settings or RetrySettings()
        self._breaker_settings = breaker_settings
        self._breaker_registry = breaker_registry

    async def token_for(self, request: DelegatedTokenRequest) -> AccessToken:
        """Exchange the verified subject token and validate the returned audience.

        Args:
            request (DelegatedTokenRequest): Verified subject token and target resource.

        Raises:
            TokenExchangeError: Exchange failed or the result is not a bearer token
                for the configured audience.
        """
        if (
            request.audience != self._settings.audience
            or request.scopes != self._settings.scopes
        ):
            raise TokenExchangeError(
                "OAuth token-exchange request does not match its configured audience or scopes"
            )
        form = {
            "grant_type": _GRANT_TYPE,
            "subject_token": request.subject_token.expose(),
            "subject_token_type": _ACCESS_TOKEN_TYPE,
            "requested_token_type": _ACCESS_TOKEN_TYPE,
            "audience": request.audience,
        }
        if request.scopes:
            form["scope"] = " ".join(request.scopes)
        auth = self._httpx.BasicAuth(
            self._client_id,
            self._client_secret.get_secret_value(),
        )
        breaker = self._breaker_registry.for_service(
            self._token_url, self._breaker_settings
        )
        try:
            breaker.before_call()
        except CircuitOpenError:
            raise TokenExchangeError(
                "OAuth on-behalf-of token exchange is temporarily unavailable"
            ) from None

        try:
            payload = await self._exchange(form, auth)
        except Exception as error:  # noqa: BLE001 - Provider errors can contain credentials.
            if self._is_service_failure(error):
                breaker.record_failure()
            else:
                breaker.record_success()
            self._log_exchange_failure(error)
            raise TokenExchangeError(
                "OAuth on-behalf-of token exchange failed"
            ) from None
        breaker.record_success()
        if not isinstance(payload, dict):
            raise TokenExchangeError(
                "OAuth provider returned an invalid token response"
            )
        access_token = payload.get("access_token")
        token_type = payload.get("token_type")
        if (
            not isinstance(access_token, str)
            or not access_token
            or not isinstance(token_type, str)
            or token_type.casefold() != "bearer"
        ):
            raise TokenExchangeError("OAuth provider returned no bearer access token")
        if not _has_audience(access_token, request.audience):
            raise TokenExchangeError(
                "OAuth provider returned a token for another audience"
            )
        return AccessToken(access_token, audience=request.audience)

    def _log_exchange_failure(self, error: Exception) -> None:
        """Report bounded diagnostics without provider descriptions or credentials."""
        status: int | None = None
        oauth_error = "unavailable"
        if isinstance(error, self._httpx.HTTPStatusError):
            status = error.response.status_code
            try:
                document = error.response.json()
            except ValueError:
                document = None
            candidate = document.get("error") if isinstance(document, dict) else None
            if isinstance(candidate, str) and candidate in _SAFE_OAUTH_ERRORS:
                oauth_error = candidate
        _logger.warning(
            "OAuth token exchange failed status=%s oauth_error=%s exception_type=%s",
            status,
            oauth_error,
            type(error).__name__,
        )

    async def _exchange(self, form: dict[str, str], auth: Any) -> Any:
        """POST the RFC 8693 form under a bounded retry policy.

        Args:
            form (dict[str, str]): Token-exchange form fields containing the subject credential.
            auth (Any): HTTPX Basic authentication for the configured client.
        """
        httpx = self._httpx
        retryable = (
            *HttpxTransportFailureClassifier.retryable_exception_types(httpx),
            RetryableHttpStatusError,
        )

        async def exchange_with(client: Any) -> Any:
            async def attempt(remaining: float) -> Any:
                response = await client.post(
                    self._token_url,
                    data=form,
                    auth=auth,
                    timeout=remaining,
                    extensions={
                        "ygo74_skip_mcp_context": True,
                        "ygo74_skip_runtime_resilience": True,
                    },
                )
                try:
                    if response.status_code in {500, 502, 503, 504}:
                        raise RetryableHttpStatusError(response.status_code)
                    response.raise_for_status()
                    return response.json()
                finally:
                    await response.aclose()

            return await RetryExecutor.run_async(
                attempt,
                settings=self._retry_settings,
                timeout_seconds=self._timeout_seconds,
                retryable_exceptions=retryable,
            )

        if self._client is not None:
            return await exchange_with(self._client)
        if self._client_provider is not None:
            return await exchange_with(self._client_provider())
        async with self._httpx.AsyncClient(
            timeout=self._timeout_seconds
        ) as temporary_client:
            return await exchange_with(temporary_client)

    def _is_service_failure(self, error: Exception) -> bool:
        """Classify only transport and upstream server failures for breaker state."""
        httpx = self._httpx
        if isinstance(
            error,
            (
                *HttpxTransportFailureClassifier.retryable_exception_types(httpx),
                RetryableHttpStatusError,
            ),
        ):
            return True
        if isinstance(error, TimeoutError):
            return True
        return isinstance(error, httpx.HTTPStatusError) and error.response.status_code >= 500


def _load_httpx() -> Any:
    """Load the optional HTTP client only when the standard source is used."""
    try:
        return import_module("httpx")
    except ImportError as error:
        raise RuntimeError(
            "RFC 8693 token exchange requires the optional HTTPX dependency"
        ) from error


def _has_audience(access_token: str, expected: str) -> bool:
    """Check a returned JWT audience claim before sending it downstream.

    Signature and issuer validation remain the resource server's responsibility.

    Args:
        access_token (str): Token returned by the configured OAuth provider.
        expected (str): Resource audience requested by the agent.
    """
    segments = access_token.split(".")
    if len(segments) != 3:
        return False
    payload_segment = segments[1]
    payload_segment += "=" * (-len(payload_segment) % 4)
    try:
        payload = json.loads(base64.urlsafe_b64decode(payload_segment))
    except (binascii.Error, UnicodeDecodeError, ValueError):
        return False
    if not isinstance(payload, dict):
        return False
    audience = payload.get("aud")
    if isinstance(audience, str):
        return audience == expected
    return isinstance(audience, list) and expected in audience
