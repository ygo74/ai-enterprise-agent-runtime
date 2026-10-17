"""Contract tests for shared HTTP clients and outbound resilience policies."""

from __future__ import annotations

import base64
import time

import httpx
import pytest
from ygo74.agent_runtime.domains.auth.jwt_authenticator import JwksKeyResolver
from ygo74.agent_runtime.domains.auth.oidc_discovery import OidcDiscovery
from ygo74.agent_runtime.domains.http.client_lifecycle import SyncHttpClientOwner
from ygo74.agent_runtime.domains.http.resilience import (
    CircuitBreakerSettings,
    CircuitOpenError,
    CircuitState,
    RetryExecutor,
    RetrySettings,
    ServiceCircuitBreakerRegistry,
)
from ygo74.agent_runtime.domains.mcp.configuration import (
    McpServerConfigurationInput,
)


def test_retry_executor_retries_only_the_declared_exception() -> None:
    """A bounded sync retry can recover without retrying other exception types."""
    attempts = 0

    def flaky(_remaining: float) -> str:
        nonlocal attempts
        attempts += 1
        if attempts < 3:
            raise ConnectionError("temporary")
        return "ready"

    result = RetryExecutor.run_sync(
        flaky,
        settings=RetrySettings(max_attempts=3, initial_delay_seconds=0.001, maximum_delay_seconds=0.002),
        timeout_seconds=1.0,
        retryable_exceptions=(ConnectionError,),
    )

    assert result == "ready"
    assert attempts == 3


@pytest.mark.asyncio
async def test_retry_executor_async_is_bounded_by_total_deadline() -> None:
    """The async adapter retries transient transport errors within its deadline."""
    attempts = 0

    async def flaky(remaining: float) -> str:
        nonlocal attempts
        assert remaining > 0
        attempts += 1
        if attempts < 2:
            raise ConnectionError("temporary")
        return "ready"

    result = await RetryExecutor.run_async(
        flaky,
        settings=RetrySettings(max_attempts=3, initial_delay_seconds=0.001, maximum_delay_seconds=0.002),
        timeout_seconds=0.5,
        retryable_exceptions=(ConnectionError,),
    )

    assert result == "ready"
    assert attempts == 2


def test_circuit_breaker_opens_then_allows_one_recovery_probe() -> None:
    """Calls share service state, while a successful half-open probe closes it."""
    registry = ServiceCircuitBreakerRegistry()
    settings = CircuitBreakerSettings(failure_threshold=2, open_seconds=0.01)
    breaker = registry.for_service("service-a", settings)

    breaker.before_call()
    breaker.record_failure()
    breaker.before_call()
    breaker.record_failure()
    assert breaker.state is CircuitState.OPEN
    with pytest.raises(CircuitOpenError):
        registry.for_service("service-a", settings).before_call()

    time.sleep(0.02)
    breaker.before_call()
    assert breaker.state is CircuitState.HALF_OPEN
    with pytest.raises(CircuitOpenError):
        breaker.before_call()
    breaker.record_success()

    assert breaker.state is CircuitState.CLOSED
    registry.for_service("service-b", settings).before_call()


def test_circuit_breaker_rejects_conflicting_settings_for_one_service() -> None:
    """One upstream cannot acquire fragmented state under conflicting policies."""
    registry = ServiceCircuitBreakerRegistry()
    registry.for_service("service-a", CircuitBreakerSettings(3, 10))

    with pytest.raises(ValueError, match="conflicting circuit breaker settings"):
        registry.for_service("service-a", CircuitBreakerSettings(4, 10))


def test_resilience_settings_reject_unbounded_values() -> None:
    """Retry attempts and circuit cooldowns remain finite for direct callers."""
    with pytest.raises(ValueError, match="between 1 and 10"):
        RetrySettings(max_attempts=11)
    with pytest.raises(ValueError, match="must be finite"):
        RetrySettings(maximum_delay_seconds=float("inf"))
    with pytest.raises(ValueError, match="must be finite"):
        CircuitBreakerSettings(open_seconds=float("inf"))


def test_sync_http_owner_retries_a_transient_status_and_reuses_injected_client() -> None:
    """OIDC and JWKS callers can reuse an injected sync pool without owning it."""
    statuses = iter((503, 200))
    requests: list[httpx.Request] = []

    def respond(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        status = next(statuses)
        return httpx.Response(status, json={"ready": True}, request=request)

    client = httpx.Client(transport=httpx.MockTransport(respond))
    owner = SyncHttpClientOwner(
        client,
        retry_settings=RetrySettings(
            max_attempts=2,
            initial_delay_seconds=0.001,
            maximum_delay_seconds=0.002,
        ),
        breaker_registry=ServiceCircuitBreakerRegistry(),
    )

    assert owner.get_json(
        "https://issuer.example.test/metadata",
        service_identity="issuer-a",
        timeout_seconds=1.0,
    ) == {"ready": True}
    owner.close()

    assert len(requests) == 2
    assert not client.is_closed
    client.close()


def test_sync_http_owner_retries_transient_read_errors() -> None:
    """A dropped response body is a transport failure eligible for safe GET retry."""
    attempts = 0

    def respond(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise httpx.ReadError("connection dropped", request=request)
        return httpx.Response(200, json={"ready": True}, request=request)

    client = httpx.Client(transport=httpx.MockTransport(respond))
    owner = SyncHttpClientOwner(
        client,
        retry_settings=RetrySettings(
            max_attempts=2,
            initial_delay_seconds=0.001,
            maximum_delay_seconds=0.002,
        ),
        breaker_registry=ServiceCircuitBreakerRegistry(),
    )

    assert owner.get_json(
        "https://issuer.example.test/keys",
        service_identity="issuer-a",
        timeout_seconds=1.0,
    ) == {"ready": True}
    assert attempts == 2
    owner.close()
    assert not client.is_closed
    client.close()


def test_sync_http_owner_does_not_retry_local_protocol_errors() -> None:
    """A local protocol/configuration error is not classified as transient."""
    attempts = 0

    def respond(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        raise httpx.UnsupportedProtocol("unsupported request protocol", request=request)

    client = httpx.Client(transport=httpx.MockTransport(respond))
    owner = SyncHttpClientOwner(
        client,
        retry_settings=RetrySettings(
            max_attempts=3,
            initial_delay_seconds=0.001,
            maximum_delay_seconds=0.002,
        ),
        breaker_registry=ServiceCircuitBreakerRegistry(),
    )

    with pytest.raises(httpx.UnsupportedProtocol):
        owner.get_json(
            "https://issuer.example.test/metadata",
            service_identity="issuer-a",
            timeout_seconds=1.0,
        )

    assert attempts == 1
    owner.close()
    client.close()


def test_sync_http_owner_closes_its_created_client_once(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The application owner closes a lazy client it created, and only once."""
    client = httpx.Client(
        transport=httpx.MockTransport(
            lambda request: httpx.Response(200, json={"ready": True}, request=request)
        )
    )
    monkeypatch.setattr(httpx, "Client", lambda **_kwargs: client)
    owner = SyncHttpClientOwner(breaker_registry=ServiceCircuitBreakerRegistry())

    assert owner.get_json(
        "https://issuer.example.test/metadata",
        service_identity="issuer-a",
        timeout_seconds=1.0,
    ) == {"ready": True}
    owner.close()
    owner.close()

    assert client.is_closed


def test_oidc_discovery_and_jwks_share_the_injected_sync_client() -> None:
    """Discovery and key lookup use the same application-owned HTTPX client."""
    secret = base64.urlsafe_b64encode(b"a sufficiently long jwt test secret").rstrip(b"=").decode()
    encryption_secret = (
        base64.urlsafe_b64encode(b"an encryption-only test secret").rstrip(b"=").decode()
    )
    requests: list[str] = []
    issuer = "https://issuer.example.test"
    jwks_url = f"{issuer}/keys"

    def respond(request: httpx.Request) -> httpx.Response:
        requests.append(str(request.url))
        if request.url.path.endswith("openid-configuration"):
            return httpx.Response(200, json={"jwks_uri": jwks_url}, request=request)
        return httpx.Response(
            200,
            json={
                "keys": [
                    {
                        "kty": "oct",
                        "k": encryption_secret,
                        "kid": "key-1",
                        "alg": "HS256",
                        "use": "enc",
                    },
                    {
                        "kty": "oct",
                        "k": secret,
                        "kid": "key-1",
                        "alg": "HS256",
                        "use": "sig",
                    },
                ]
            },
            request=request,
        )

    client = httpx.Client(transport=httpx.MockTransport(respond))
    owner = SyncHttpClientOwner(client, breaker_registry=ServiceCircuitBreakerRegistry())
    discovery = OidcDiscovery(http_client_owner=owner)
    resolver = JwksKeyResolver(
        jwks_url,
        http_client_owner=discovery.http_client_owner,
    )

    assert discovery.jwks_url(issuer) == jwks_url
    assert resolver.resolve_key("unused-token", {"kid": "key-1"}) == base64.urlsafe_b64decode(secret + "==")
    assert len(requests) == 2

    owner.close()
    client.close()


def test_mcp_yaml_has_typed_retry_and_circuit_breaker_defaults() -> None:
    """Per-server policy settings are typed and HTTP-only, with safe defaults."""
    source = McpServerConfigurationInput.model_validate(
        {
            "transport": "http",
            "url": "https://mcp.example.test/mcp",
            "capabilities": ["search"],
            "retry": {"max_attempts": 2, "initial_delay_seconds": 0.05},
            "circuit_breaker": {"failure_threshold": 4, "open_seconds": 20},
        }
    )

    assert source.retry.settings() == RetrySettings(
        max_attempts=2,
        initial_delay_seconds=0.05,
        maximum_delay_seconds=0.5,
    )
    assert source.circuit_breaker.settings() == CircuitBreakerSettings(4, 20)

    defaulted = McpServerConfigurationInput.model_validate(
        {
            "transport": "http",
            "url": "https://mcp.example.test/mcp",
            "capabilities": ["search"],
        }
    )
    assert defaulted.retry.settings() == RetrySettings()
    assert defaulted.circuit_breaker.settings() == CircuitBreakerSettings()

    with pytest.raises(ValueError, match="require HTTP transport"):
        McpServerConfigurationInput.model_validate(
            {
                "transport": "stdio",
                "command": "mcp-server",
                "capabilities": ["search"],
                "retry": {"max_attempts": 2},
            }
        )
