"""Tests for agent-scoped MCP server reuse and skill-specific tool views."""

from __future__ import annotations

import os
from collections.abc import Mapping
from enum import StrEnum
from pathlib import Path

import pytest
from ygo74.agent_runtime.domains.auth.tokens import AccessToken, DelegatedTokenRequest
from ygo74.agent_runtime.domains.configuration.directory import ConfigurationDirectory
from ygo74.agent_runtime.domains.contracts.manifests import AgentManifest, SkillManifest
from ygo74.agent_runtime.domains.mcp.mcp_errors import McpBindingError
from ygo74.agent_runtime.domains.mcp.registry import McpAgentRegistryLoader
from ygo74.agent_runtime.domains.security.operations import (
    OperationType,
    RiskLevel,
    ToolOperationDescriptor,
)
from ygo74.agent_runtime.domains.security.permissions import Permission


class Capability(StrEnum):
    """Logical tool aliases declared by server configurations."""

    SEARCH = "search_mail"
    SEND = "send_mail"


def _skill(tool_name: str, server: str, tools: tuple[str, ...]) -> SkillManifest:
    """Build one skill manifest with a typed MCP reference."""
    return SkillManifest(
        tool_name=tool_name,
        implementation=f"mail.{tool_name}",
        description=f"Run {tool_name}.",
        operation=ToolOperationDescriptor(
            tool_name=tool_name,
            operation_type=OperationType.READ,
            risk_level=RiskLevel.LOW,
            required_permission=Permission("mail", "read"),
            confirmation_required_by_default=False,
        ),
        mcp_server=server,
        mcp_tools=tools,
    )


def _agent(*skills: SkillManifest) -> AgentManifest:
    """Build one agent manifest from ordered skills."""
    return AgentManifest(
        name="mail",
        description="Mail agent",
        instructions="Use tools safely.",
        skills=skills,
    )


def _write_server(config_root: Path, name: str, *, server: str | None = None) -> None:
    """Write a valid MCP HTTP server YAML file under the delivered config root."""
    folder = config_root / "mcp"
    folder.mkdir(parents=True, exist_ok=True)
    server_name = server or name
    (folder / f"{name}.yaml").write_text(
        f"server: {server_name}\n"
        "transport: http\n"
        f"url: https://{name}.example.test/mcp\n"
        "capabilities: [search_mail, send_mail]\n"
        "tools:\n"
        "  search_mail: remote_search\n"
        "  send_mail: remote_send\n",
        encoding="utf-8",
    )


def test_registry_reuses_one_connection_for_skills_sharing_a_server(
    tmp_path: Path,
) -> None:
    """Two skills share one lazy connection and receive separate allowed tools."""
    config_root = tmp_path / "config"
    _write_server(config_root, "gmail-http")
    _write_server(config_root, "archive-http")
    loader = McpAgentRegistryLoader(
        ConfigurationDirectory(config_root), Capability, environment={}
    )

    registry = loader.load(
        _agent(
            _skill("lookup", "gmail-http", ("search_mail",)),
            _skill("archive", "gmail-http", ("send_mail",)),
            _skill("history", "archive-http", ("search_mail",)),
        )
    )

    lookup = registry.for_skill("lookup")
    archive = registry.for_skill("archive")
    history = registry.for_skill("history")
    assert lookup.connection is archive.connection
    assert lookup.connection is not history.connection
    assert lookup.tools == {"search_mail": "remote_search"}
    assert archive.tools == {"send_mail": "remote_send"}
    assert history.server_name == "archive-http"


def test_registry_requires_and_injects_the_delegated_token_source(
    tmp_path: Path,
) -> None:
    """OBO configuration fails closed without a host source and wires one when supplied."""
    config_root = tmp_path / "config"
    server_directory = config_root / "mcp"
    server_directory.mkdir(parents=True)
    (server_directory / "delegated.yaml").write_text(
        "server: delegated\n"
        "transport: http\n"
        "url: https://mcp.example.test/mcp\n"
        "capabilities: [search_mail]\n"
        "tools: {search_mail: search}\n"
        "authentication_mode: oauth_on_behalf_of\n"
        "authentication_oauth_on_behalf_of:\n"
        "  audience: https://mcp.example.test\n"
        "  scopes: [mail.read]\n",
        encoding="utf-8",
    )
    agent = _agent(_skill("lookup", "delegated", ("search_mail",)))

    with pytest.raises(McpBindingError, match="delegated token source"):
        McpAgentRegistryLoader(
            ConfigurationDirectory(config_root), Capability, environment={}
        ).load(agent)

    class FakeOAuthOnBehalfOfTokenSource:
        """Return an MCP token for a future request without making network calls."""

        async def token_for(self, request: DelegatedTokenRequest) -> AccessToken:
            return AccessToken("mcp-token", audience=request.audience)

    source = FakeOAuthOnBehalfOfTokenSource()
    registry = McpAgentRegistryLoader(
        ConfigurationDirectory(config_root),
        Capability,
        environment={},
        delegated_token_source=source,
    ).load(agent)

    assert registry.for_skill("lookup").connection._delegated_token_source is source


def test_skill_view_rejects_an_alias_outside_its_allow_list(tmp_path: Path) -> None:
    """A sibling skill's additional server tools are hidden from this skill."""
    config_root = tmp_path / "config"
    _write_server(config_root, "gmail-http")
    registry = McpAgentRegistryLoader(
        ConfigurationDirectory(config_root), Capability, environment={}
    ).load(_agent(_skill("lookup", "gmail-http", ("search_mail",))))

    view = registry.for_skill("lookup")

    assert view.remote_tool("search_mail") == "remote_search"
    with pytest.raises(McpBindingError, match="does not allow"):
        view.remote_tool("send_mail")


def test_registry_ignores_unreferenced_server_files(tmp_path: Path) -> None:
    """Unreferenced server YAML is not opened while an agent is loaded."""
    config_root = tmp_path / "config"
    _write_server(config_root, "gmail-http")
    (config_root / "mcp" / "unused.yaml").write_text("invalid: [", encoding="utf-8")

    registry = McpAgentRegistryLoader(
        ConfigurationDirectory(config_root), Capability, environment={}
    ).load(_agent(_skill("lookup", "gmail-http", ("search_mail",))))

    assert registry.server_names == ("gmail-http",)


@pytest.mark.parametrize("name", ["absent", "../secret", "/tmp/secret"])
def test_registry_refuses_missing_or_unsafe_server_names(
    tmp_path: Path, name: str
) -> None:
    """Server references cannot escape the MCP configuration directory."""
    config_root = tmp_path / "config"
    config_root.mkdir()
    loader = McpAgentRegistryLoader(
        ConfigurationDirectory(config_root), Capability, environment={}
    )

    with pytest.raises(McpBindingError):
        loader.load(_agent(_skill("lookup", name, ("search_mail",))))


def test_registry_refuses_duplicate_skill_identities(tmp_path: Path) -> None:
    """Two entries with the same skill name cannot shadow each other."""
    config_root = tmp_path / "config"
    _write_server(config_root, "gmail-http")
    loader = McpAgentRegistryLoader(
        ConfigurationDirectory(config_root), Capability, environment={}
    )

    with pytest.raises(McpBindingError, match="duplicate skill"):
        loader.load(
            _agent(
                _skill("lookup", "gmail-http", ("search_mail",)),
                _skill("lookup", "gmail-http", ("send_mail",)),
            )
        )


def test_registry_refuses_a_skill_tool_missing_from_the_server_mapping(
    tmp_path: Path,
) -> None:
    """A skill's allow-list must be satisfied before the agent starts."""
    config_root = tmp_path / "config"
    _write_server(config_root, "gmail-http")
    loader = McpAgentRegistryLoader(
        ConfigurationDirectory(config_root), Capability, environment={}
    )

    with pytest.raises(McpBindingError, match="missing MCP tools"):
        loader.load(_agent(_skill("lookup", "gmail-http", ("missing_tool",))))


def test_registry_loads_delivered_env_without_overriding_process_values(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """The adjacent .env supplies secrets while process values retain precedence."""
    config_root = tmp_path / "config"
    _write_server(config_root, "gmail-http")
    (config_root / "mcp" / "gmail-http.yaml").write_text(
        "server: gmail-http\n"
        "transport: http\n"
        "url: https://gmail.example.test/mcp\n"
        "capabilities: [search_mail]\n"
        "tools: {search_mail: remote_search}\n"
        "authentication_mode: api_key\n"
        "authentication_api_key:\n"
        "  header_name: X-Key\n"
        "  value: ${MAIL_KEY}\n",
        encoding="utf-8",
    )
    (tmp_path / ".env").write_text(
        "MAIL_KEY=from-dotenv\nDOTENV_ONLY=loaded-from-dotenv\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("MAIL_KEY", "from-process")
    monkeypatch.delenv("DOTENV_ONLY", raising=False)
    resolved_headers: dict[str, str] = {}

    class CapturingConnection:
        """Capture configured headers without opening a remote transport."""

        def __init__(self, binding: object, **kwargs: object) -> None:
            """Record configured headers for the environment-precedence assertion.

            Args:
                binding (object): Validated server binding unused by this fake.
                **kwargs (object): Connection options supplied by the registry.
            """
            headers = kwargs.get("headers", {})
            assert isinstance(headers, Mapping)
            resolved_headers.update(dict(headers))

        async def aclose(self) -> None:
            """Satisfy the connection lifecycle without opening resources."""

    from ygo74.agent_runtime.domains.mcp import registry as registry_module

    monkeypatch.setattr(registry_module, "McpConnection", CapturingConnection)
    registry = McpAgentRegistryLoader(
        ConfigurationDirectory(config_root), Capability
    ).load(_agent(_skill("lookup", "gmail-http", ("search_mail",))))

    assert registry.server_names == ("gmail-http",)
    assert resolved_headers == {"X-Key": "from-process"}
    assert os.environ["DOTENV_ONLY"] == "loaded-from-dotenv"


def test_registry_closes_each_unique_connection_once(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Closing the agent registry closes each shared server connection once."""
    from ygo74.agent_runtime.domains.mcp import registry as registry_module

    closed: list[str] = []

    class FakeConnection:
        def __init__(self, binding: object, **kwargs: object) -> None:
            self._server = binding.server

        async def aclose(self) -> None:
            closed.append(self._server)

    monkeypatch.setattr(registry_module, "McpConnection", FakeConnection)
    config_root = tmp_path / "config"
    _write_server(config_root, "gmail-http")
    _write_server(config_root, "archive-http")
    registry = McpAgentRegistryLoader(
        ConfigurationDirectory(config_root), Capability, environment={}
    ).load(
        _agent(
            _skill("lookup", "gmail-http", ("search_mail",)),
            _skill("archive", "gmail-http", ("send_mail",)),
            _skill("history", "archive-http", ("search_mail",)),
        )
    )

    async def scenario() -> None:
        await registry.aclose()
        await registry.aclose()
        with pytest.raises(McpBindingError, match="closed"):
            registry.for_skill("lookup")

    import asyncio

    asyncio.run(scenario())

    assert sorted(closed) == ["archive-http", "gmail-http"]
