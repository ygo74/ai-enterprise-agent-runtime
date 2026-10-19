"""Contracts and host conversion for HTTP settings declared in agent.yaml."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError
from ygo74.agent_runtime.domains.auth.apikey_authenticator import ApiKeyAuthenticator
from ygo74.agent_runtime.domains.auth.authentication_policy import AuthenticationMode
from ygo74.agent_runtime.domains.auth.jwt_authenticator import (
    DiscoveredJwksKeyResolver,
    JwksKeyResolver,
    JwtAuthenticator,
    StaticPublicKeyResolver,
    StaticSymmetricKeyResolver,
)
from ygo74.agent_runtime.domains.configuration.agent_http_configuration import (
    AgentHttpSettingsBuilder,
    HttpEndpoint,
)
from ygo74.agent_runtime.domains.configuration.directory import (
    ConfigurationDirectory,
)
from ygo74.agent_runtime.domains.configuration.manifest_inputs import (
    AgentManifestInput,
)
from ygo74.agent_runtime.domains.configuration.manifests import (
    AgentManifestLoader,
    SkillManifestLoader,
)
from ygo74.agent_runtime.domains.security.floor import SecurityFloor
from ygo74.agent_runtime.domains.security.permissions import (
    Permission,
    PermissionRegistry,
)


def _api_key_manifest_value() -> dict[str, object]:
    """Return a valid manifest with a service API key and an explicit identity."""
    return {
        "name": "mail-agent",
        "description": "Mail agent.",
        "skills": ["search"],
        "http": {
            "endpoints": ["chat_completions", "responses"],
            "security": {
                "mode": "api_key",
                "api_key": {
                    "value": "${MAIL_HTTP_API_KEY}",
                    "header_name": "X-API-Key",
                    "user": {"subject": "mail-service", "email": "mail@example.test"},
                },
            },
        },
    }


def test_http_settings_are_optional_and_secret_references_are_redacted() -> None:
    """A non-HTTP agent needs no credentials and loaded references stay inert."""
    base = {"name": "cli-agent", "description": "CLI agent.", "skills": ["search"]}
    loaded = AgentManifestInput.model_validate(_api_key_manifest_value())

    assert AgentManifestInput.model_validate(base).http is None
    assert loaded.http is not None
    assert loaded.http.security.api_key is not None
    assert str(loaded.http.security.api_key.value) == "**********"
    assert "MAIL_HTTP_API_KEY" not in repr(loaded.http.security.api_key.value)


def test_agent_manifest_loader_does_not_resolve_http_secrets(tmp_path: Path) -> None:
    """CLI and MCP manifest loading retains HTTP references without requiring their variables."""
    config_root = tmp_path / "config"
    agent_directory = config_root / "agents" / "mail-agent"
    skill_directory = config_root / "skills" / "mail-agent" / "search"
    agent_directory.mkdir(parents=True)
    skill_directory.mkdir(parents=True)
    (agent_directory / "agent.yaml").write_text(
        "name: mail-agent\n"
        "description: Mail agent.\n"
        "skills: [search]\n"
        "http:\n"
        "  endpoints: [chat_completions]\n"
        "  security:\n"
        "    mode: api_key\n"
        "    api_key:\n"
        "      value: ${MAIL_HTTP_API_KEY}\n"
        "      user:\n"
        "        subject: mail-service\n",
        encoding="utf-8",
    )
    (agent_directory / "AGENT.md").write_text("Use the search skill.\n", encoding="utf-8")
    (skill_directory / "skill.yaml").write_text(
        "tool_name: search\n"
        "implementation: mail.search\n"
        "description: Search messages.\n"
        "operation:\n"
        "  type: READ\n"
        "  risk: LOW\n"
        "  permission: mail:read\n"
        "  confirmation_required: false\n",
        encoding="utf-8",
    )
    skills = SkillManifestLoader(
        PermissionRegistry([Permission("mail", "read")]), SecurityFloor(())
    )

    manifest = AgentManifestLoader(ConfigurationDirectory(config_root), skills).load(
        "mail-agent"
    )

    assert manifest.http is not None
    assert str(manifest.http.security.api_key.value) == "**********"


@pytest.mark.parametrize(
    "security",
    [
        {"mode": "api_key", "api_key": {"value": "literal", "user": {"subject": "svc"}}},
        {"mode": "jwt", "jwt": {"allowed_algorithms": ["HS256"]}},
        {"mode": "unknown", "api_key": {"value": "${KEY}", "user": {"subject": "svc"}}},
    ],
)
def test_security_mode_rejects_missing_or_incompatible_settings(
    security: dict[str, object],
) -> None:
    """Security configuration is complete, explicit, and mutually exclusive."""
    value = _api_key_manifest_value()
    http = value["http"]
    assert isinstance(http, dict)
    http["security"] = security

    with pytest.raises(ValidationError):
        AgentManifestInput.model_validate(value)


def test_api_key_configuration_builds_existing_authentication_policy() -> None:
    """The manifest adapter delegates identity projection to the shared security package."""
    manifest = AgentManifestInput.model_validate(_api_key_manifest_value())
    assert manifest.http is not None

    settings = AgentHttpSettingsBuilder({"MAIL_HTTP_API_KEY": "resolved-key"}).build(
        manifest.http
    )
    authenticator = settings.authentication.authenticators[0]

    assert settings.endpoints == (HttpEndpoint.CHAT_COMPLETIONS, HttpEndpoint.RESPONSES)
    assert settings.authentication.mode is AuthenticationMode.API_KEY
    assert isinstance(authenticator, ApiKeyAuthenticator)
    context = authenticator.authenticate({"x-api-key": "resolved-key"})
    assert context.identity.user_id == "mail-service"
    assert context.identity.email == "mail@example.test"
    assert "resolved-key" not in repr(authenticator._resolver)


@pytest.mark.parametrize(
    ("jwt", "resolver_type"),
    [
        (
            {"issuer": "https://issuer.example.test", "allowed_algorithms": ["RS256"]},
            DiscoveredJwksKeyResolver,
        ),
        (
            {"jwks_url": "https://issuer.example.test/keys", "allowed_algorithms": ["RS256"]},
            JwksKeyResolver,
        ),
        (
            {"secret": "${JWT_SECRET}", "allowed_algorithms": ["HS256"]},
            StaticSymmetricKeyResolver,
        ),
        (
            {"public_key": "${JWT_PUBLIC_KEY}", "allowed_algorithms": ["RS256"]},
            StaticPublicKeyResolver,
        ),
    ],
)
def test_jwt_configuration_builds_supported_key_resolver(
    jwt: dict[str, object], resolver_type: type[object]
) -> None:
    """JWT settings retain all supported validation values in the existing validator."""
    value = _api_key_manifest_value()
    http = value["http"]
    assert isinstance(http, dict)
    http["security"] = {"mode": "jwt", "jwt": jwt}
    manifest = AgentManifestInput.model_validate(value)
    assert manifest.http is not None

    environment = {"JWT_SECRET": "sensitive-key", "JWT_PUBLIC_KEY": "public-key"}
    settings = AgentHttpSettingsBuilder(environment).build(manifest.http)
    authenticator = settings.authentication.authenticators[0]

    assert settings.authentication.mode is AuthenticationMode.JWT
    assert isinstance(authenticator, JwtAuthenticator)
    assert isinstance(authenticator.config.key_resolver, resolver_type)
    if isinstance(authenticator.config.key_resolver, StaticSymmetricKeyResolver):
        assert "sensitive-key" not in repr(authenticator.config.key_resolver)


def test_secret_resolution_fails_without_echoing_the_configured_value() -> None:
    """Missing required references fail at host composition without leaking secrets."""
    manifest = AgentManifestInput.model_validate(_api_key_manifest_value())
    assert manifest.http is not None

    with pytest.raises(ValueError, match="MAIL_HTTP_API_KEY") as error:
        AgentHttpSettingsBuilder({}).build(manifest.http)
    assert "resolved-key" not in str(error.value)


def test_rate_limit_storage_reference_is_resolved_and_redacted() -> None:
    """The optional storage backend stays lazy until a host settings object is built."""
    value = _api_key_manifest_value()
    http = value["http"]
    assert isinstance(http, dict)
    http["rate_limit"] = {
        "limits": ["60/minute", "500/day"],
        "storage_uri": "${HTTP_LIMIT_STORAGE_URI}",
    }
    manifest = AgentManifestInput.model_validate(value)
    assert manifest.http is not None

    settings = AgentHttpSettingsBuilder(
        {
            "MAIL_HTTP_API_KEY": "resolved-key",
            "HTTP_LIMIT_STORAGE_URI": "redis://cache.example.test:6379/3",
        }
    ).build(manifest.http)

    assert settings.rate_limit is not None
    assert settings.rate_limit.limits == ("60/minute", "500/day")
    assert "cache.example.test" not in repr(settings.rate_limit)


def test_http_configuration_rejects_bad_urls_and_duplicate_surfaces() -> None:
    """URL and endpoint errors are detected before route registration."""
    value = _api_key_manifest_value()
    http = value["http"]
    assert isinstance(http, dict)
    http["endpoints"] = ["responses", "responses"]
    with pytest.raises(ValidationError, match="endpoints"):
        AgentManifestInput.model_validate(value)

    http["endpoints"] = ["responses"]
    http["security"] = {
        "mode": "jwt",
        "jwt": {"jwks_url": "http://issuer.example.test/keys"},
    }
    with pytest.raises(ValidationError, match="https"):
        AgentManifestInput.model_validate(value)


def test_rate_limit_rejects_units_unsupported_by_slowapi() -> None:
    """Manifest validation rejects periods the selected backend cannot parse."""
    value = _api_key_manifest_value()
    http = value["http"]
    assert isinstance(http, dict)
    http["rate_limit"] = {"limits": ["60/week"]}

    with pytest.raises(ValidationError, match="limits"):
        AgentManifestInput.model_validate(value)


def test_rate_limit_rejects_storage_backends_without_an_http_extra_driver() -> None:
    """Only in-memory and Redis storage are accepted by the installed HTTP extra."""
    value = _api_key_manifest_value()
    http = value["http"]
    assert isinstance(http, dict)
    http["rate_limit"] = {"limits": ["60/minute"], "storage_uri": "memcached://cache:11211"}

    with pytest.raises(ValidationError, match="supported backend URI"):
        AgentManifestInput.model_validate(value)


@pytest.mark.parametrize(
    "jwt",
    [
        {"issuer": "https://issuer.example.test"},
        {"jwks_url": "https://issuer.example.test/keys"},
    ],
)
def test_remote_jwks_requires_asymmetric_signing_algorithms(
    jwt: dict[str, object],
) -> None:
    """Remote signing-key sources cannot be paired with a symmetric HMAC policy."""
    value = _api_key_manifest_value()
    http = value["http"]
    assert isinstance(http, dict)
    http["security"] = {"mode": "jwt", "jwt": jwt}

    with pytest.raises(ValidationError, match="asymmetric"):
        AgentManifestInput.model_validate(value)
