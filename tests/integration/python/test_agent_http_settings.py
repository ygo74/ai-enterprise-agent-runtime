"""Tests of how an agent's HTTP posture is configured and discovered.

The interesting part is the key set. Deriving its URL by appending a path to the
issuer worked for exactly one provider and failed silently for the rest, which is
why discovery replaced it - and why an explicit override still has to win.
"""

from __future__ import annotations

from typing import Any

import pytest

from ygo74.agent_runtime.domains.auth.auth_errors import AuthenticationError
from ygo74.agent_runtime.domains.auth.oidc_discovery import DISCOVERY_PATH, OidcDiscovery
from ygo74.agent_runtime.domains.configuration.agent_http_settings import AgentHttpSettings

ISSUER = "https://realm.example/auth/realms/agents"
KEYS = "https://realm.example/auth/realms/agents/protocol/openid-connect/certs"


class FakeDiscovery(OidcDiscovery):
    """Answers without a network, and records what it was asked."""

    def __init__(self, jwks_uri: str | None = KEYS) -> None:
        super().__init__()
        self.asked: list[str] = []
        self._jwks_uri = jwks_uri

    def _fetch(self, url: str) -> dict[str, Any]:
        self.asked.append(url)
        if self._jwks_uri is None:
            return {"issuer": ISSUER}
        return {"issuer": ISSUER, "jwks_uri": self._jwks_uri}


def env(**values: str) -> dict[str, str]:
    return {f"MAIL_AGENT_HTTP_{name}": value for name, value in values.items()}


def test_the_defaults_identify_nobody() -> None:
    """Stated rather than assumed: a host has to notice and refuse to start."""
    settings = AgentHttpSettings()

    assert not settings.identifies_a_caller
    assert not settings.uses_oidc


def test_settings_are_read_by_prefix() -> None:
    settings = AgentHttpSettings.from_env(
        "MAIL_AGENT_HTTP_",
        default_audience="mail-agent",
        environment=env(API_KEY="demo", MAX_CONVERSATIONS="7", IDLE_MINUTES="5"),
    )

    assert settings.api_key == "demo"
    assert settings.oidc_audience == "mail-agent"
    assert settings.max_conversations == 7
    assert settings.idle_lifetime().total_seconds() == 300


def test_another_agents_prefix_is_not_read() -> None:
    """Two agents in one process must not read each other's posture."""
    settings = AgentHttpSettings.from_env(
        "WIKI_AGENT_HTTP_",
        environment=env(API_KEY="demo", OIDC_ISSUER=ISSUER),
    )

    assert settings.api_key == ""
    assert not settings.uses_oidc


def test_an_api_key_alone_identifies_a_caller() -> None:
    settings = AgentHttpSettings.from_env("MAIL_AGENT_HTTP_", environment=env(API_KEY="demo"))

    assert settings.identifies_a_caller
    assert not settings.uses_oidc


def test_an_issuer_alone_identifies_a_caller() -> None:
    settings = AgentHttpSettings.from_env("MAIL_AGENT_HTTP_", environment=env(OIDC_ISSUER=ISSUER))

    assert settings.identifies_a_caller
    assert settings.uses_oidc


def test_the_key_set_is_discovered_from_the_issuer() -> None:
    """Asking the issuer works for every provider; appending a path worked for one."""
    settings = AgentHttpSettings(oidc_issuer=ISSUER)
    discovery = FakeDiscovery()

    assert settings.jwks_url(discovery) == KEYS
    assert discovery.asked == [f"{ISSUER}{DISCOVERY_PATH}"]


def test_a_trailing_slash_on_the_issuer_is_tolerated() -> None:
    discovery = FakeDiscovery()

    AgentHttpSettings(oidc_issuer=f"{ISSUER}/").jwks_url(discovery)

    assert discovery.asked == [f"{ISSUER}{DISCOVERY_PATH}"]


def test_an_explicit_override_wins_over_discovery() -> None:
    """An operator who names a URL has a reason; do not ask the network instead."""
    settings = AgentHttpSettings(oidc_issuer=ISSUER, jwks_url_override="https://elsewhere/keys")
    discovery = FakeDiscovery()

    assert settings.jwks_url(discovery) == "https://elsewhere/keys"
    assert discovery.asked == []


def test_the_override_is_accepted_under_the_name_an_operator_would_guess() -> None:
    settings = AgentHttpSettings.from_env(
        "MAIL_AGENT_HTTP_",
        environment=env(OIDC_ISSUER=ISSUER, JWKS_URL="https://elsewhere/keys"),
    )

    assert settings.jwks_url_override == "https://elsewhere/keys"


def test_discovery_is_asked_once_per_issuer() -> None:
    discovery = FakeDiscovery()
    settings = AgentHttpSettings(oidc_issuer=ISSUER)

    settings.jwks_url(discovery)
    settings.jwks_url(discovery)

    assert len(discovery.asked) == 1


def test_a_missing_issuer_is_refused_rather_than_guessed() -> None:
    with pytest.raises(AuthenticationError) as refusal:
        AgentHttpSettings().jwks_url(FakeDiscovery())

    assert refusal.value.code == "issuer_not_configured"


def test_a_document_declaring_no_key_set_is_refused() -> None:
    with pytest.raises(AuthenticationError) as refusal:
        AgentHttpSettings(oidc_issuer=ISSUER).jwks_url(FakeDiscovery(jwks_uri=None))

    assert refusal.value.code == "jwks_uri_missing"


def test_an_unreachable_issuer_is_reported_clearly() -> None:
    """The message must point at the server, not at the token."""

    class Unreachable(OidcDiscovery):
        def _fetch(self, url: str) -> dict[str, Any]:
            raise AuthenticationError(code="discovery_unavailable", message=f"could not read {url}")

    with pytest.raises(AuthenticationError) as refusal:
        AgentHttpSettings(oidc_issuer=ISSUER).jwks_url(Unreachable())

    assert refusal.value.code == "discovery_unavailable"


def test_settings_are_immutable() -> None:
    settings = AgentHttpSettings(api_key="demo")

    with pytest.raises(ValueError, match="frozen"):
        settings.api_key = "another"  # type: ignore[misc]


def test_a_bound_of_zero_conversations_is_refused() -> None:
    with pytest.raises(ValueError):
        AgentHttpSettings(max_conversations=0)


def test_a_malformed_discovery_document_is_refused() -> None:
    """The guard sits where the document is consumed, not only where it is read."""

    class NotAnObject(OidcDiscovery):
        def _fetch(self, url: str) -> Any:
            return ["not", "an", "object"]

    with pytest.raises(AuthenticationError) as refusal:
        AgentHttpSettings(oidc_issuer=ISSUER).jwks_url(NotAnObject())

    assert refusal.value.code == "discovery_malformed"
