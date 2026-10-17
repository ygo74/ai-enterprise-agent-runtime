"""Tests for MCP server YAML, schema validation, and secret resolution."""

from __future__ import annotations

import json
from enum import StrEnum
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator
from ygo74.agent_runtime.domains.auth.oauth_token_exchange import (
    OAuthTokenExchangeSettings,
)
from ygo74.agent_runtime.domains.configuration.manifest_schemas import ManifestSchemas
from ygo74.agent_runtime.domains.mcp.configuration import (
    McpAuthenticationMode,
    McpDelegatedOAuthSettings,
    McpServerConfigurationLoader,
)
from ygo74.agent_runtime.domains.mcp.mcp_errors import McpBindingError
from ygo74.agent_runtime.domains.mcp.oauth import McpOAuthProviderFactory


class Capability(StrEnum):
    """Logical tool names the application knows how to offer."""

    SEARCH = "search_mail"
    SEND = "send_mail"


def _write(tmp_path: Path, content: str) -> Path:
    """Write server YAML to a temporary configuration file."""
    path = tmp_path / "gmail.yaml"
    path.write_text(content, encoding="utf-8")
    return path


def _http_yaml(authentication: str = "authentication_mode: none\n") -> str:
    """Return an HTTP server configuration using the supplied authentication block."""
    return (
        "server: gmail-http\n"
        "transport: http\n"
        "url: https://example.test/mcp\n"
        "capabilities: [search_mail]\n"
        "tools:\n"
        "  search_mail: remote_search\n"
        "request_timeout_seconds: 17\n"
        "network:\n"
        "  proxy_url: http://proxy.example.test:8080\n"
        f"{authentication}"
    )


def test_legacy_delegated_settings_name_aliases_generic_exchange_settings() -> None:
    """The previous settings import remains compatible with the generic contract."""
    assert McpDelegatedOAuthSettings is OAuthTokenExchangeSettings


def test_server_loader_resolves_api_key_and_keeps_non_secret_settings_in_yaml(
    tmp_path: Path,
) -> None:
    """Load API-key credentials and HTTP settings from their declared sources."""
    path = _write(
        tmp_path,
        _http_yaml(
            "authentication_mode: api_key\n"
            "authentication_api_key:\n"
            "  header_name: X-API-Key\n"
            "  value: ${MAIL_MCP_API_KEY}\n"
        ),
    )

    config = McpServerConfigurationLoader(
        Capability, environment={"MAIL_MCP_API_KEY": "do-not-log"}
    ).load(path)

    assert config.binding.server == "gmail-http"
    assert config.authentication_mode is McpAuthenticationMode.API_KEY
    assert dict(config.headers) == {"X-API-Key": "do-not-log"}
    assert "do-not-log" not in repr(config.headers)
    assert config.request_timeout_seconds == 17
    assert config.network.proxy_url == "http://proxy.example.test:8080"
    assert "do-not-log" not in repr(config)


def test_server_loader_resolves_literal_environment_and_context_headers(
    tmp_path: Path,
) -> None:
    """Configured HTTP headers retain context templates and redact resolved values."""
    path = _write(
        tmp_path,
        _http_yaml().replace(
            "request_timeout_seconds: 17\n",
            "request_timeout_seconds: 17\n"
            "headers:\n"
            "  Content-Type: application/json\n"
            "  X-User-ID: '{{USER_ID}}'\n"
            "  X-Request-ID: 'request={{REQUEST_ID}}'\n"
            "  X-Proxy-Key: ${PROXY_KEY}\n",
        ),
    )

    config = McpServerConfigurationLoader(
        Capability, environment={"PROXY_KEY": "proxy-secret"}
    ).load(path)

    assert dict(config.headers) == {
        "Content-Type": "application/json",
        "X-User-ID": "{{USER_ID}}",
        "X-Request-ID": "request={{REQUEST_ID}}",
        "X-Proxy-Key": "proxy-secret",
    }
    assert "proxy-secret" not in repr(config.headers)
    assert "proxy-secret" not in repr(config)


@pytest.mark.parametrize(
    "header_value", ["{{UNKNOWN}}", "prefix-${SECRET}", "{{USER_ID"]
)
def test_server_loader_rejects_unknown_malformed_and_partial_environment_header_templates(
    tmp_path: Path,
    header_value: str,
) -> None:
    """Header interpolation accepts only documented tokens and exact env references."""
    path = _write(
        tmp_path,
        _http_yaml().replace(
            "request_timeout_seconds: 17\n",
            f"request_timeout_seconds: 17\nheaders:\n  X-Test: '{header_value}'\n",
        ),
    )

    with pytest.raises(McpBindingError):
        McpServerConfigurationLoader(Capability, environment={"SECRET": "hidden"}).load(
            path
        )


def test_packaged_server_schema_validates_header_names_and_template_syntax() -> None:
    """Editor tooling rejects unknown context templates and invalid header names."""
    schema = Draft202012Validator(json.loads(ManifestSchemas.mcp_server()))
    base = {
        "transport": "http",
        "url": "https://example.test/mcp",
        "capabilities": ["search_mail"],
    }

    accepted = {
        **base,
        "headers": {"X-User": "{{USER_ID}}", "X-Key": "${DEPLOYMENT_KEY}"},
    }
    unknown_token = {**base, "headers": {"X-User": "{{UNKNOWN}}"}}
    invalid_name = {**base, "headers": {"Bad Header": "literal"}}

    assert not tuple(schema.iter_errors(accepted))
    assert tuple(schema.iter_errors(unknown_token))
    assert tuple(schema.iter_errors(invalid_name))


def test_server_loader_reports_missing_header_environment_variable_without_value(
    tmp_path: Path,
) -> None:
    """Unresolved header references name the missing variable without echoing content."""
    path = _write(
        tmp_path,
        _http_yaml().replace(
            "request_timeout_seconds: 17\n",
            "request_timeout_seconds: 17\nheaders: {X-Key: '${MISSING_GATEWAY_KEY}'}\n",
        ),
    )

    with pytest.raises(McpBindingError) as error:
        McpServerConfigurationLoader(Capability, environment={}).load(path)

    assert "MISSING_GATEWAY_KEY" in str(error.value)
    assert "${MISSING_GATEWAY_KEY}" not in str(error.value)


def test_server_loader_rejects_custom_headers_for_stdio(tmp_path: Path) -> None:
    """HTTP headers cannot be configured for a stdio transport."""
    path = _write(
        tmp_path,
        "transport: stdio\n"
        "command: python\n"
        "capabilities: [search_mail]\n"
        "headers: {X-User-ID: '{{USER_ID}}'}\n",
    )

    with pytest.raises(McpBindingError):
        McpServerConfigurationLoader(Capability).load(path)


def test_server_loader_accepts_stdio_without_optional_http_settings(
    tmp_path: Path,
) -> None:
    """The packaged schema permits a stdio server with omitted HTTP-only fields."""
    document = {
        "transport": "stdio",
        "command": "python",
        "capabilities": ["search_mail"],
    }
    schema = Draft202012Validator(json.loads(ManifestSchemas.mcp_server()))
    path = _write(
        tmp_path,
        "transport: stdio\ncommand: python\ncapabilities: [search_mail]\n",
    )

    config = McpServerConfigurationLoader(Capability).load(path)

    assert not tuple(schema.iter_errors(document))
    assert config.binding.command == "python"
    assert config.authentication_mode is McpAuthenticationMode.NONE
    assert config.network.proxy_url is None


def test_server_loader_rejects_authorization_header_conflicts(tmp_path: Path) -> None:
    """Explicit Authorization headers cannot shadow runtime authentication."""
    path = _write(
        tmp_path,
        _http_yaml(
            "authentication_mode: api_key\n"
            "authentication_api_key:\n"
            "  header_name: X-API-Key\n"
            "  value: ${MAIL_MCP_API_KEY}\n"
        ).replace(
            "request_timeout_seconds: 17\n",
            "request_timeout_seconds: 17\nheaders: {authorization: bearer-overridden}\n",
        ),
    )

    with pytest.raises(McpBindingError, match="Authorization"):
        McpServerConfigurationLoader(
            Capability, environment={"MAIL_MCP_API_KEY": "api-secret"}
        ).load(path)


def test_server_loader_accepts_delegated_oauth_audience_and_scopes(
    tmp_path: Path,
) -> None:
    """On-behalf-of settings describe the downstream audience without storing tokens."""
    path = _write(
        tmp_path,
        _http_yaml(
            "authentication_mode: oauth_on_behalf_of\n"
            "authentication_oauth_on_behalf_of:\n"
            "  audience: https://mail.example.test\n"
            "  scopes: [mail.read, mail.send]\n"
        ),
    )

    config = McpServerConfigurationLoader(Capability).load(path)

    assert config.authentication_mode.value == "oauth_on_behalf_of"
    assert config.delegated_oauth is not None
    assert config.delegated_oauth.audience == "https://mail.example.test"
    assert config.delegated_oauth.scopes == ("mail.read", "mail.send")


def test_server_loader_resolves_delegated_oauth_client_settings_from_yaml_and_environment(
    tmp_path: Path,
) -> None:
    """Resolve the OBO client secret while keeping endpoint and identity in YAML."""
    path = _write(
        tmp_path,
        _http_yaml(
            "authentication_mode: oauth_on_behalf_of\n"
            "authentication_oauth_on_behalf_of:\n"
            "  token_url: https://identity.example.test/realms/agents/token\n"
            "  client_id: mail-agent\n"
            "  client_secret: ${MCP_MAIL_OBO_CLIENT_SECRET}\n"
            "  audience: mail-mcp\n"
            "  scopes: [mail.read]\n"
        ),
    )

    config = McpServerConfigurationLoader(
        Capability,
        environment={"MCP_MAIL_OBO_CLIENT_SECRET": "private-client-secret"},
    ).load(path)

    assert config.delegated_oauth is not None
    assert (
        config.delegated_oauth.token_url
        == "https://identity.example.test/realms/agents/token"
    )
    assert config.delegated_oauth.client_id == "mail-agent"
    assert config.delegated_oauth.client_secret is not None
    assert (
        config.delegated_oauth.client_secret.get_secret_value()
        == "private-client-secret"
    )
    assert config.delegated_oauth.audience == "mail-mcp"
    assert config.delegated_oauth.scopes == ("mail.read",)
    assert "private-client-secret" not in repr(config)
    assert "private-client-secret" not in repr(config.delegated_oauth)


def test_server_loader_reports_missing_delegated_oauth_secret_without_echoing_value(
    tmp_path: Path,
) -> None:
    """A missing OBO credential names its environment variable but not its value."""
    path = _write(
        tmp_path,
        _http_yaml(
            "authentication_mode: oauth_on_behalf_of\n"
            "authentication_oauth_on_behalf_of:\n"
            "  token_url: https://identity.example.test/token\n"
            "  client_id: mail-agent\n"
            "  client_secret: ${MCP_MAIL_OBO_CLIENT_SECRET}\n"
            "  audience: mail-mcp\n"
        ),
    )

    with pytest.raises(McpBindingError) as error:
        McpServerConfigurationLoader(Capability, environment={}).load(path)

    assert "MCP_MAIL_OBO_CLIENT_SECRET" in str(error.value)
    assert "private-client-secret" not in str(error.value)


@pytest.mark.parametrize(
    "client_settings",
    [
        "  token_url: https://identity.example.test/token\n",
        "  client_id: mail-agent\n",
        "  client_secret: ${MCP_MAIL_OBO_CLIENT_SECRET}\n",
    ],
)
def test_server_loader_rejects_partial_delegated_oauth_client_settings(
    tmp_path: Path,
    client_settings: str,
) -> None:
    """OBO endpoint, client identity, and secret are configured as one group."""
    path = _write(
        tmp_path,
        _http_yaml(
            "authentication_mode: oauth_on_behalf_of\n"
            "authentication_oauth_on_behalf_of:\n"
            "  audience: mail-mcp\n"
            f"{client_settings}"
        ),
    )

    with pytest.raises(McpBindingError, match="missing required field"):
        McpServerConfigurationLoader(
            Capability, environment={"MCP_MAIL_OBO_CLIENT_SECRET": "secret"}
        ).load(path)


def test_server_loader_rejects_non_https_delegated_oauth_token_endpoint(
    tmp_path: Path,
) -> None:
    """The verified caller token can only be sent to a TLS-protected endpoint."""
    path = _write(
        tmp_path,
        _http_yaml(
            "authentication_mode: oauth_on_behalf_of\n"
            "authentication_oauth_on_behalf_of:\n"
            "  token_url: http://identity.example.test/token\n"
            "  client_id: mail-agent\n"
            "  client_secret: ${MCP_MAIL_OBO_CLIENT_SECRET}\n"
            "  audience: mail-mcp\n"
        ),
    )

    with pytest.raises(McpBindingError, match="must be an HTTPS URL"):
        McpServerConfigurationLoader(
            Capability, environment={"MCP_MAIL_OBO_CLIENT_SECRET": "secret"}
        ).load(path)


def test_packaged_server_schema_accepts_delegated_oauth_secret_references() -> None:
    """The editor schema accepts configured OBO clients and rejects literal secrets."""
    schema = Draft202012Validator(json.loads(ManifestSchemas.mcp_server()))
    base = {
        "transport": "http",
        "url": "https://mcp.example.test",
        "capabilities": ["search_mail"],
        "authentication_mode": "oauth_on_behalf_of",
    }
    accepted = {
        **base,
        "authentication_oauth_on_behalf_of": {
            "token_url": "https://identity.example.test/token",
            "client_id": "mail-agent",
            "client_secret": "${MCP_MAIL_OBO_CLIENT_SECRET}",
            "audience": "mail-mcp",
            "scopes": [],
        },
    }
    literal_secret = {
        **accepted,
        "authentication_oauth_on_behalf_of": {
            **accepted["authentication_oauth_on_behalf_of"],
            "client_secret": "literal-secret",
        },
    }

    assert not tuple(schema.iter_errors(accepted))
    assert tuple(schema.iter_errors(literal_secret))


@pytest.mark.parametrize("reference", ["${MISSING_KEY}", "${}", "literal-secret"])
def test_server_loader_rejects_unresolved_or_literal_api_key_without_echoing_it(
    tmp_path: Path,
    reference: str,
) -> None:
    """Credential references must resolve and their contents stay out of errors."""
    path = _write(
        tmp_path,
        _http_yaml(
            "authentication_mode: api_key\n"
            "authentication_api_key:\n"
            "  header_name: X-API-Key\n"
            f"  value: {reference}\n"
        ),
    )

    with pytest.raises(McpBindingError) as error:
        McpServerConfigurationLoader(Capability, environment={}).load(path)

    assert "literal-secret" not in str(error.value)


def test_server_loader_rejects_authentication_fields_that_conflict_with_mode(
    tmp_path: Path,
) -> None:
    """Authentication mode and its settings form one valid configuration."""
    path = _write(
        tmp_path,
        _http_yaml(
            "authentication_mode: none\n"
            "authentication_api_key:\n"
            "  header_name: X-API-Key\n"
            "  value: ${MAIL_MCP_API_KEY}\n"
        ),
    )

    with pytest.raises(McpBindingError, match="authentication"):
        McpServerConfigurationLoader(
            Capability, environment={"MAIL_MCP_API_KEY": "secret"}
        ).load(path)


def test_server_loader_rejects_unknown_yaml_fields_with_file_and_field(
    tmp_path: Path,
) -> None:
    """The runtime schema rejects misspelled configuration keys."""
    path = _write(tmp_path, _http_yaml().replace("proxy_url:", "proxy: "))

    with pytest.raises(McpBindingError) as error:
        McpServerConfigurationLoader(Capability).load(path)

    assert str(path) in str(error.value)
    assert "proxy" in str(error.value)


def test_server_loader_resolves_oauth_client_secret_and_scopes(tmp_path: Path) -> None:
    """OAuth values remain typed while client secrets are resolved and redacted."""
    path = _write(
        tmp_path,
        _http_yaml(
            "authentication_mode: oauth\n"
            "authentication_oauth:\n"
            "  client_id: mail-client\n"
            "  client_secret: ${MAIL_OAUTH_SECRET}\n"
            "  callback_port: 8765\n"
            "  scopes: [mail.read, mail.compose]\n"
            "  token_file: .secrets/mail-mcp-token.json\n"
            "  client_name: Mail agent\n"
        ),
    )

    config = McpServerConfigurationLoader(
        Capability, environment={"MAIL_OAUTH_SECRET": "oauth-secret"}
    ).load(path)

    assert config.authentication_mode is McpAuthenticationMode.OAUTH
    assert config.oauth is not None
    assert config.oauth.client_id == "mail-client"
    assert config.oauth.client_secret.get_secret_value() == "oauth-secret"
    assert config.oauth.scopes == ("mail.read", "mail.compose")
    assert "oauth-secret" not in repr(config)


def test_oauth_token_file_is_relative_to_the_delivered_configuration_root(
    tmp_path: Path,
) -> None:
    """A canonical config/mcp file resolves token storage beside config/."""
    config_root = tmp_path / "config"
    server_directory = config_root / "mcp"
    server_directory.mkdir(parents=True)
    path = server_directory / "gmail.yaml"
    path.write_text(
        _http_yaml(
            "authentication_mode: oauth\n"
            "authentication_oauth:\n"
            "  client_id: mail-client\n"
            "  client_secret: ${MAIL_OAUTH_SECRET}\n"
            "  scopes: [mail.read]\n"
            "  token_file: .secrets/mail-mcp-token.json\n"
        ),
        encoding="utf-8",
    )

    config = McpServerConfigurationLoader(
        Capability, environment={"MAIL_OAUTH_SECRET": "secret"}
    ).load(path)

    assert config.oauth is not None
    assert config.oauth.token_file == tmp_path / ".secrets" / "mail-mcp-token.json"


@pytest.mark.asyncio
async def test_oauth_provider_uses_configured_client_and_pinned_scopes(
    tmp_path: Path,
) -> None:
    """The runtime assembles its existing pinned-scope OAuth helper from YAML."""
    path = _write(
        tmp_path,
        _http_yaml(
            "authentication_mode: oauth\n"
            "authentication_oauth:\n"
            "  client_id: mail-client\n"
            "  client_secret: ${MAIL_OAUTH_SECRET}\n"
            "  scopes: [mail.read, mail.compose]\n"
        ),
    )
    config = McpServerConfigurationLoader(
        Capability, environment={"MAIL_OAUTH_SECRET": "oauth-secret"}
    ).load(path)
    assert config.oauth is not None

    provider = McpOAuthProviderFactory().build(config.binding.url, config.oauth)
    client_info = await provider.context.storage.get_client_info()

    assert provider.context.client_metadata.scope == "mail.read mail.compose"
    assert client_info.client_id == "mail-client"
    assert client_info.client_secret == "oauth-secret"
