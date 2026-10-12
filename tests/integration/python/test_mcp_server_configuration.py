"""Tests for MCP server YAML, schema validation, and secret resolution."""

from __future__ import annotations

from enum import StrEnum
from pathlib import Path

import pytest
from ygo74.agent_runtime.domains.mcp.configuration import (
    McpAuthenticationMode,
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


def test_server_loader_resolves_api_key_and_keeps_non_secret_settings_in_yaml(tmp_path: Path) -> None:
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

    config = McpServerConfigurationLoader(Capability, environment={"MAIL_MCP_API_KEY": "do-not-log"}).load(path)

    assert config.binding.server == "gmail-http"
    assert config.authentication_mode is McpAuthenticationMode.API_KEY
    assert dict(config.headers) == {"X-API-Key": "do-not-log"}
    assert "do-not-log" not in repr(config.headers)
    assert config.request_timeout_seconds == 17
    assert config.network.proxy_url == "http://proxy.example.test:8080"
    assert "do-not-log" not in repr(config)


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


def test_server_loader_rejects_authentication_fields_that_conflict_with_mode(tmp_path: Path) -> None:
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
        McpServerConfigurationLoader(Capability, environment={"MAIL_MCP_API_KEY": "secret"}).load(path)


def test_server_loader_rejects_unknown_yaml_fields_with_file_and_field(tmp_path: Path) -> None:
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

    config = McpServerConfigurationLoader(Capability, environment={"MAIL_OAUTH_SECRET": "oauth-secret"}).load(path)

    assert config.authentication_mode is McpAuthenticationMode.OAUTH
    assert config.oauth is not None
    assert config.oauth.client_id == "mail-client"
    assert config.oauth.client_secret.get_secret_value() == "oauth-secret"
    assert config.oauth.scopes == ("mail.read", "mail.compose")
    assert "oauth-secret" not in repr(config)


def test_oauth_token_file_is_relative_to_the_delivered_configuration_root(tmp_path: Path) -> None:
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

    config = McpServerConfigurationLoader(Capability, environment={"MAIL_OAUTH_SECRET": "secret"}).load(path)

    assert config.oauth is not None
    assert config.oauth.token_file == tmp_path / ".secrets" / "mail-mcp-token.json"


@pytest.mark.asyncio
async def test_oauth_provider_uses_configured_client_and_pinned_scopes(tmp_path: Path) -> None:
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
    config = McpServerConfigurationLoader(Capability, environment={"MAIL_OAUTH_SECRET": "oauth-secret"}).load(path)
    assert config.oauth is not None

    provider = McpOAuthProviderFactory().build(config.binding.url, config.oauth)
    client_info = await provider.context.storage.get_client_info()

    assert provider.context.client_metadata.scope == "mail.read mail.compose"
    assert client_info.client_id == "mail-client"
    assert client_info.client_secret == "oauth-secret"
