"""Application-owned synchronous HTTPX client for authentication lookups."""

from __future__ import annotations

from importlib import import_module
from typing import TYPE_CHECKING, Any

from ygo74.agent_runtime.domains.http.resilience import (
    DEFAULT_CIRCUIT_BREAKERS,
    CircuitBreakerSettings,
    RetryExecutor,
    RetrySettings,
    ServiceCircuitBreakerRegistry,
)

if TYPE_CHECKING:
    from httpx import Client
else:
    Client = Any


class RetryableHttpStatusError(RuntimeError):
    """Identify a transient response status without retaining provider content."""

    def __init__(self, status_code: int) -> None:
        """Store only the numeric upstream status for safe retry diagnostics."""
        self.status_code = status_code
        super().__init__(f"transient upstream HTTP status {status_code}")


class HttpxTransportFailureClassifier:
    """Select HTTPX failures that can reasonably recover on a bounded retry."""

    @staticmethod
    def retryable_exception_types(httpx: Any) -> tuple[type[Exception], ...]:
        """Return transient connection, request-timeout, and remote-protocol errors.

        Pool-acquisition timeouts and local protocol/configuration failures are
        excluded because they do not show that the remote service is unavailable.

        Args:
            httpx (Any): Loaded HTTPX module supplying the exception classes.
        """
        return (
            httpx.ConnectError,
            httpx.ConnectTimeout,
            httpx.ReadTimeout,
            httpx.WriteTimeout,
            httpx.ReadError,
            httpx.WriteError,
            httpx.RemoteProtocolError,
            httpx.ProxyError,
        )


class SyncHttpClientOwner:
    """Create, reuse, and close one synchronous HTTPX pool for authentication.

    The owner accepts an optional caller-owned client for composition and tests.
    The default client is constructed lazily with TLS verification enabled and
    remains open until :meth:`close` is called by its application owner.

    Args:
        client (Client | None): Optional injected HTTPX client. The caller owns it.
        retry_settings (RetrySettings): Bounded retry policy for safe GET reads.
        breaker_registry (ServiceCircuitBreakerRegistry): Shared per-service breaker state.
    """

    def __init__(
        self,
        client: Client | None = None,
        *,
        retry_settings: RetrySettings | None = None,
        breaker_registry: ServiceCircuitBreakerRegistry = DEFAULT_CIRCUIT_BREAKERS,
    ) -> None:
        """Retain the injected client or defer creation of an owned client."""
        self._httpx: Any | None = None
        self._client = client
        self._owns_client = client is None
        self._closed = False
        self.retry_settings = retry_settings or RetrySettings()
        self.breaker_registry = breaker_registry

    def get_json(
        self,
        url: str,
        *,
        service_identity: str,
        timeout_seconds: float,
        retry_settings: RetrySettings | None = None,
        breaker_settings: CircuitBreakerSettings | None = None,
    ) -> Any:
        """GET and decode one safe JSON document under retry and breaker policy.

        Args:
            url (str): HTTP URL of an OIDC metadata or JWKS document.
            service_identity (str): Stable issuer identity shared by its lookups.
            timeout_seconds (float): Total deadline for attempts and backoff.
            retry_settings (RetrySettings | None): Optional operation-specific policy.
            breaker_settings (CircuitBreakerSettings | None): Optional service override.

        Raises:
            CircuitOpenError: The upstream circuit is open.
            RuntimeError: HTTPX is unavailable or the owner has been closed.
            Exception: HTTPX transport/status or JSON decoding failures are preserved
                for the domain caller to translate.
        """
        httpx = self._load_httpx()
        client = self._get_client(httpx)
        breaker = self.breaker_registry.for_service(
            service_identity, breaker_settings
        )
        breaker.before_call()
        selected_retry = retry_settings or self.retry_settings

        def fetch(remaining: float) -> Any:
            response = client.get(url, timeout=remaining)
            if response.status_code in {500, 502, 503, 504}:
                status = response.status_code
                response.close()
                raise RetryableHttpStatusError(status)
            try:
                response.raise_for_status()
                return response.json()
            finally:
                response.close()

        retryable = (
            *HttpxTransportFailureClassifier.retryable_exception_types(httpx),
            RetryableHttpStatusError,
        )
        try:
            payload = RetryExecutor.run_sync(
                fetch,
                settings=selected_retry,
                timeout_seconds=timeout_seconds,
                retryable_exceptions=retryable,
            )
        except Exception as error:
            if self._is_service_failure(error, httpx):
                breaker.record_failure()
            else:
                breaker.record_success()
            raise
        breaker.record_success()
        return payload

    def close(self) -> None:
        """Close the owned HTTPX client once; injected clients remain caller-owned."""
        if self._closed:
            return
        self._closed = True
        if self._owns_client and self._client is not None:
            self._client.close()
        self._client = None if self._owns_client else self._client

    def _get_client(self, httpx: Any) -> Client:
        """Return the live shared client or construct it on first use."""
        if self._closed:
            raise RuntimeError("authentication HTTP client owner is closed")
        if self._client is None:
            self._client = httpx.Client(timeout=5.0, verify=True)
        return self._client

    def _load_httpx(self) -> Any:
        """Load HTTPX only when remote authentication lookups are used."""
        if self._httpx is not None:
            return self._httpx
        try:
            self._httpx = import_module("httpx")
        except ImportError as error:
            raise RuntimeError(
                "remote OIDC/JWKS lookup requires the optional security[oidc-http] extra"
            ) from error
        return self._httpx

    @staticmethod
    def _is_service_failure(error: Exception, httpx: Any) -> bool:
        """Count only network, timeout, transient HTTP, and server failures."""
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
