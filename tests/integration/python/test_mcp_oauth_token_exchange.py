"""Tests for the runtime's standard OAuth RFC 8693 token source."""

from __future__ import annotations

import base64
import json
import logging
from typing import Self
from urllib.parse import parse_qs

import httpx
import pytest
from pydantic import SecretStr
from ygo74.agent_runtime.domains.auth.agent_principal import AgentPrincipal
from ygo74.agent_runtime.domains.auth.oauth_token_exchange import (
    OAuthTokenExchangeSettings,
    Rfc8693OAuthOnBehalfOfTokenSource,
)
from ygo74.agent_runtime.domains.auth.tokens import (
    AccessToken,
    DelegatedTokenRequest,
    TokenExchangeError,
)

SUBJECT_TOKEN = "verified-inbound-token-fixture"
CLIENT_SECRET = "fixture-client-secret-not-real"
TOKEN_ENDPOINT = "https://identity.example.test/token"


def _settings(audience: str = "mail-mcp") -> OAuthTokenExchangeSettings:
    """Build fully resolved token-exchange settings for a test source."""
    return OAuthTokenExchangeSettings(
        audience=audience,
        scopes=("mail.read", "mail.send"),
        token_url=TOKEN_ENDPOINT,
        client_id="mail-agent",
        client_secret=SecretStr(CLIENT_SECRET),
    )


def _jwt_with_audience(audience: str) -> str:
    """Build an unsigned test token whose payload has the supplied audience."""
    payload = (
        base64.urlsafe_b64encode(json.dumps({"aud": audience}).encode())
        .decode()
        .rstrip("=")
    )
    return f"e30.{payload}.signature"


def _request(
    audience: str = "mail-mcp",
    scopes: tuple[str, ...] = ("mail.read", "mail.send"),
) -> DelegatedTokenRequest:
    """Build a token request from a verified test caller."""
    return DelegatedTokenRequest(
        principal=AgentPrincipal(subject="user-123", email="user@example.test"),
        subject_token=AccessToken(SUBJECT_TOKEN, audience="mail-agent"),
        audience=audience,
        scopes=scopes,
    )


@pytest.mark.asyncio
async def test_source_sends_rfc8693_request_and_validates_returned_audience() -> None:
    """The runtime sends the verified subject token to the configured endpoint."""
    captured: dict[str, object] = {}

    def respond(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["authorization"] = request.headers.get("authorization")
        captured["form"] = parse_qs(request.content.decode("ascii"))
        return httpx.Response(
            200,
            json={
                "access_token": _jwt_with_audience("mail-mcp"),
                "token_type": "Bearer",
            },
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
        source = Rfc8693OAuthOnBehalfOfTokenSource(_settings(), client=client)
        result = await source.token_for(_request())
        assert not client.is_closed

    assert result == AccessToken(_jwt_with_audience("mail-mcp"), audience="mail-mcp")
    assert captured["url"] == TOKEN_ENDPOINT
    expected_credentials = base64.b64encode(
        f"mail-agent:{CLIENT_SECRET}".encode()
    ).decode()
    assert captured["authorization"] == f"Basic {expected_credentials}"
    assert captured["form"] == {
        "grant_type": ["urn:ietf:params:oauth:grant-type:token-exchange"],
        "subject_token": [SUBJECT_TOKEN],
        "subject_token_type": ["urn:ietf:params:oauth:token-type:access_token"],
        "requested_token_type": ["urn:ietf:params:oauth:token-type:access_token"],
        "audience": ["mail-mcp"],
        "scope": ["mail.read mail.send"],
    }


@pytest.mark.asyncio
async def test_source_redacts_provider_errors_and_rejects_wrong_audience() -> None:
    """Provider responses cannot leak the inbound token or relabel another audience."""

    def provider_error(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            400,
            json={
                "error_description": f"{SUBJECT_TOKEN} {CLIENT_SECRET}",
            },
        )

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(provider_error)
    ) as client:
        source = Rfc8693OAuthOnBehalfOfTokenSource(_settings(), client=client)
        with pytest.raises(TokenExchangeError) as failure:
            await source.token_for(_request())

    assert SUBJECT_TOKEN not in str(failure.value)
    assert CLIENT_SECRET not in str(failure.value)

    def wrong_audience(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "access_token": _jwt_with_audience("another-resource"),
                "token_type": "Bearer",
            },
        )

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(wrong_audience)
    ) as client:
        source = Rfc8693OAuthOnBehalfOfTokenSource(_settings(), client=client)
        with pytest.raises(TokenExchangeError, match="another audience"):
            await source.token_for(_request())


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("payload", "expected_code"),
    [
        ({"error": "invalid_token"}, "invalid_token"),
        ({"error": "invalid_client"}, "invalid_client"),
        ({"error": "invalid_request"}, "invalid_request"),
        ({"error": SUBJECT_TOKEN}, "unavailable"),
        ({"error": {"token": SUBJECT_TOKEN}}, "unavailable"),
        (["invalid_token", SUBJECT_TOKEN], "unavailable"),
    ],
)
async def test_source_logs_only_allowlisted_oauth_error_codes(
    caplog: pytest.LogCaptureFixture,
    payload: object,
    expected_code: str,
) -> None:
    """An operator can distinguish a rejected subject token without leaking a provider body."""
    attempts = 0

    def respond(_request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        document = (
            {**payload, "error_description": f"{SUBJECT_TOKEN} {CLIENT_SECRET}"}
            if isinstance(payload, dict)
            else payload
        )
        return httpx.Response(400, json=document)

    with caplog.at_level(logging.WARNING):
        async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
            source = Rfc8693OAuthOnBehalfOfTokenSource(_settings(), client=client)
            with pytest.raises(TokenExchangeError):
                await source.token_for(_request())
    assert attempts == 1
    assert f"status=400 oauth_error={expected_code}" in caplog.text
    assert SUBJECT_TOKEN not in caplog.text
    assert CLIENT_SECRET not in caplog.text


@pytest.mark.asyncio
async def test_source_redacts_non_json_provider_failure(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Proxy and HTML failures do not expose raw response text in diagnostics."""
    def respond(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(400, text=f"{SUBJECT_TOKEN} {CLIENT_SECRET}")

    with caplog.at_level(logging.WARNING):
        async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
            source = Rfc8693OAuthOnBehalfOfTokenSource(_settings(), client=client)
            with pytest.raises(TokenExchangeError):
                await source.token_for(_request())
    assert "status=400 oauth_error=unavailable" in caplog.text
    assert SUBJECT_TOKEN not in caplog.text
    assert CLIENT_SECRET not in caplog.text


@pytest.mark.asyncio
async def test_source_rejects_incomplete_settings_and_audience_mismatch() -> None:
    """A source requires complete settings and will not exchange for another target."""
    with pytest.raises(ValueError, match="complete OAuth client settings"):
        Rfc8693OAuthOnBehalfOfTokenSource(
            OAuthTokenExchangeSettings(audience="mail-mcp")
        )

    async with httpx.AsyncClient() as client:
        source = Rfc8693OAuthOnBehalfOfTokenSource(_settings(), client=client)
        with pytest.raises(TokenExchangeError, match="configured audience"):
            await source.token_for(_request("another-resource"))
        with pytest.raises(TokenExchangeError, match="configured audience or scopes"):
            await source.token_for(_request(scopes=("mail.read",)))


@pytest.mark.asyncio
async def test_source_closes_the_http_client_it_creates(monkeypatch) -> None:
    """A source-owned bounded client closes after its exchange completes."""
    state = {"timeout": 0.0, "closed": False}

    class SourceOwnedClient:
        """Stand in for HTTPX while recording the source-owned lifecycle."""

        def __init__(self, *, timeout: float) -> None:
            state["timeout"] = timeout

        async def __aenter__(self) -> Self:
            return self

        async def __aexit__(self, *_: object) -> None:
            state["closed"] = True

        async def post(self, *_: object, **__: object) -> httpx.Response:
            return httpx.Response(
                200,
                request=httpx.Request("POST", TOKEN_ENDPOINT),
                json={
                    "access_token": _jwt_with_audience("mail-mcp"),
                    "token_type": "Bearer",
                },
            )

    monkeypatch.setattr(httpx, "AsyncClient", SourceOwnedClient)
    source = Rfc8693OAuthOnBehalfOfTokenSource(_settings(), timeout_seconds=3.0)

    await source.token_for(_request())

    assert state == {"timeout": 3.0, "closed": True}


def test_settings_redact_client_secret_and_source_rejects_non_https_endpoint() -> None:
    """Representations mask credentials and the source refuses cleartext endpoints."""
    settings = _settings()
    assert CLIENT_SECRET not in repr(settings)

    with pytest.raises(ValueError, match="HTTPS URL"):
        Rfc8693OAuthOnBehalfOfTokenSource(
            OAuthTokenExchangeSettings(
                audience="mail-mcp",
                token_url="http://identity.example.test/token",
                client_id="mail-agent",
                client_secret=SecretStr(CLIENT_SECRET),
            )
        )
