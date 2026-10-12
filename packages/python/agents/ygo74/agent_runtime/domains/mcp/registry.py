"""Load one agent's referenced MCP servers and expose skill-scoped tool views."""

from __future__ import annotations

import os
import re
from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from types import MappingProxyType
from typing import Generic, TypeVar

from ygo74.agent_runtime.domains.auth.tokens import OAuthOnBehalfOfTokenSource
from ygo74.agent_runtime.domains.configuration.directory import ConfigurationDirectory
from ygo74.agent_runtime.domains.configuration.environment import EnvironmentFile
from ygo74.agent_runtime.domains.contracts.manifests import AgentManifest, SkillManifest
from ygo74.agent_runtime.domains.mcp.binding import ErrorFactory, McpConnection
from ygo74.agent_runtime.domains.mcp.configuration import (
    McpAuthenticationMode,
    McpServerConfiguration,
    McpServerConfigurationLoader,
)
from ygo74.agent_runtime.domains.mcp.mcp_errors import McpBindingError
from ygo74.agent_runtime.domains.mcp.oauth import McpOAuthProviderFactory

CapabilityT = TypeVar("CapabilityT", bound=StrEnum)
_SERVER_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")


@dataclass(slots=True)
class _RegistryState:
    """Track whether all views owned by one registry remain usable.

    Args:
        closed (bool): Whether the registry has released all its connections.
    """

    closed: bool = False


class McpSkillServerView:
    """Expose one shared server connection with a skill's restricted tool map.

    Args:
        tool_name (str): Manifest identity of the skill receiving this view.
        server_name (str): Configuration name selected by the skill.
        connection (McpConnection): Agent-owned lazy connection shared by sibling skills.
        tools (Mapping[str, str]): Alias-to-remote-name mappings allowed for this skill.
        state (_RegistryState): Lifecycle state shared with the owning registry.
        error_factory (ErrorFactory): Callback that builds the domain error for this failure path.
    """

    def __init__(
        self,
        *,
        tool_name: str,
        server_name: str,
        connection: McpConnection,
        tools: Mapping[str, str],
        state: _RegistryState,
        error_factory: ErrorFactory,
    ) -> None:
        """Store a restricted view over the agent-owned connection.

        Args:
            tool_name (str): Manifest identity of the skill receiving this view.
            server_name (str): Configuration name selected by the skill.
            connection (McpConnection): Agent-owned lazy connection shared by sibling skills.
            tools (Mapping[str, str]): Alias-to-remote-name mappings allowed for this skill.
            state (_RegistryState): Lifecycle state shared with the owning registry.
            error_factory (ErrorFactory): Callback that builds the domain error for this failure path.
        """
        self._tool_name = tool_name
        self._server_name = server_name
        self._connection = connection
        self._tools = MappingProxyType(dict(tools))
        self._state = state
        self._error_factory = error_factory

    @property
    def tool_name(self) -> str:
        """Return the manifest identity associated with this view."""
        return self._tool_name

    @property
    def server_name(self) -> str:
        """Return the configured server name selected by this skill."""
        return self._server_name

    @property
    def connection(self) -> McpConnection:
        """Return the shared lazy connection while the registry remains open."""
        self._ensure_open()
        return self._connection

    @property
    def tools(self) -> Mapping[str, str]:
        """Return a read-only alias map containing only this skill's allowed tools."""
        self._ensure_open()
        return self._tools

    def remote_tool(self, alias: str) -> str:
        """Resolve an allowed logical alias to its remote MCP tool name.

        Args:
            alias (str): Skill-level alias to resolve.
        """
        self._ensure_open()
        remote = self._tools.get(alias)
        if remote is None:
            raise self._error_factory(
                f"skill {self._tool_name!r} does not allow MCP tool alias {alias!r}"
            )
        return remote

    def _ensure_open(self) -> None:
        """Reject use of a view after its owner has closed all connections."""
        if self._state.closed:
            raise self._error_factory(
                f"MCP registry is closed; skill {self._tool_name!r} is unavailable"
            )


class McpAgentRegistry(Generic[CapabilityT]):
    """Own one set of shared connections and the views declared by an agent.

    Args:
        views (Mapping[str, McpSkillServerView]): Skill names mapped to their scoped server views.
        connections (Mapping[str, McpConnection]): Unique configured server connections owned by this registry.
        state (_RegistryState): Lifecycle state shared with skill views.
        error_factory (ErrorFactory): Callback that builds the domain error for this failure path.
    """

    def __init__(
        self,
        views: Mapping[str, McpSkillServerView],
        connections: Mapping[str, McpConnection],
        state: _RegistryState,
        error_factory: ErrorFactory,
    ) -> None:
        """Initialize the registry with prevalidated connections and skill views.

        Args:
            views (Mapping[str, McpSkillServerView]): Skill names mapped to their scoped server views.
            connections (Mapping[str, McpConnection]): Unique configured server connections owned by this registry.
            state (_RegistryState): Lifecycle state shared with skill views.
            error_factory (ErrorFactory): Callback that builds the domain error for this failure path.
        """
        self._views = MappingProxyType(dict(views))
        self._connections = MappingProxyType(dict(connections))
        self._state = state
        self._error_factory = error_factory

    @property
    def server_names(self) -> tuple[str, ...]:
        """Return referenced server names in first-use order."""
        return tuple(self._connections)

    def for_skill(self, tool_name: str) -> McpSkillServerView:
        """Return the constrained MCP view declared for one skill.

        Args:
            tool_name (str): Name of a skill declared by this agent.
        """
        if self._state.closed:
            raise self._error_factory("MCP registry is closed")
        view = self._views.get(tool_name)
        if view is None:
            raise self._error_factory(
                f"agent declares no MCP-enabled skill named {tool_name!r}"
            )
        return view

    async def aclose(self) -> None:
        """Close each unique connection once, continuing if one close fails."""
        if self._state.closed:
            return
        self._state.closed = True
        failures: list[Exception] = []
        for connection in self._connections.values():
            try:
                await connection.aclose()
            except Exception as error:  # noqa: BLE001  # Preserve cleanup of later unique servers.
                failures.append(error)
        if failures:
            raise failures[0]


class McpAgentRegistryLoader(Generic[CapabilityT]):
    """Load referenced MCP YAML once and share its lazy connection by server name.

    Args:
        configuration_directory (ConfigurationDirectory): Delivered ``config/`` root.
        capabilities (type[CapabilityT]): Application capabilities valid in server declarations.
        environment (Mapping[str, str] | None): Optional deterministic secret source; absent uses process values and ``.env``.
        delegated_token_source (OAuthOnBehalfOfTokenSource | None): Application-owned OAuth on-behalf-of exchange port.
        error_factory (ErrorFactory): Callback that builds the domain error for this failure path.
    """

    def __init__(
        self,
        configuration_directory: ConfigurationDirectory,
        capabilities: type[CapabilityT],
        *,
        environment: Mapping[str, str] | None = None,
        delegated_token_source: OAuthOnBehalfOfTokenSource | None = None,
        error_factory: ErrorFactory = McpBindingError,
    ) -> None:
        """Keep the configuration root and typed server loader inputs.

        Args:
            configuration_directory (ConfigurationDirectory): Delivered ``config/`` root.
            capabilities (type[CapabilityT]): Application capabilities valid in server declarations.
            environment (Mapping[str, str] | None): Optional deterministic source for secret references.
            delegated_token_source (OAuthOnBehalfOfTokenSource | None): Application-owned OAuth on-behalf-of exchange port.
            error_factory (ErrorFactory): Callback that builds the domain error for this failure path.
        """
        self._directory = configuration_directory
        self._capabilities = capabilities
        self._environment = environment
        self._delegated_token_source = delegated_token_source
        self._error_factory = error_factory

    def load(self, agent: AgentManifest) -> McpAgentRegistry[CapabilityT]:
        """Build an agent registry without opening network or OAuth sessions.

        Args:
            agent (AgentManifest): Validated agent and its ordered skill declarations.
        """
        skills = self._validate_skills(agent)
        server_skills = self._skills_by_server(skills)
        if not server_skills:
            return McpAgentRegistry({}, {}, _RegistryState(), self._error_factory)

        if self._environment is None:
            # The delivered environment file sits beside config/, and dotenv keeps
            # already-present process values authoritative.
            EnvironmentFile(self._directory.path.parent / ".env").load()
        environment = self._environment if self._environment is not None else os.environ
        loader = McpServerConfigurationLoader(
            self._capabilities,
            environment=environment,
            error_factory=self._error_factory,
        )

        configurations: dict[str, McpServerConfiguration[CapabilityT]] = {}
        for server_name, selected_skills in server_skills.items():
            path = self._server_path(server_name)
            configuration = loader.load(path, name=server_name)
            for skill in selected_skills:
                try:
                    configuration.binding.require_aliases(skill.mcp_tools)
                except Exception as error:
                    raise self._error_factory(
                        f"skill {skill.tool_name!r} references server {server_name!r} with missing MCP tools"
                    ) from error
            configurations[server_name] = configuration

        connections = {
            server_name: self._create_connection(configuration)
            for server_name, configuration in configurations.items()
        }
        state = _RegistryState()
        views = {
            skill.tool_name: McpSkillServerView(
                tool_name=skill.tool_name,
                server_name=server_name,
                connection=connections[server_name],
                tools={
                    alias: configurations[server_name].binding.remote(alias)
                    for alias in skill.mcp_tools
                },
                state=state,
                error_factory=self._error_factory,
            )
            for server_name, selected_skills in server_skills.items()
            for skill in selected_skills
        }
        return McpAgentRegistry(views, connections, state, self._error_factory)

    def _validate_skills(self, agent: AgentManifest) -> tuple[SkillManifest, ...]:
        """Reject ambiguous skill identities and incomplete MCP declarations.

        Args:
            agent (AgentManifest): Agent whose skill identities and MCP declarations are checked.
        """
        seen: set[str] = set()
        for skill in agent.skills:
            if skill.tool_name in seen:
                raise self._error_factory(
                    f"agent {agent.name!r} has duplicate skill {skill.tool_name!r}"
                )
            seen.add(skill.tool_name)
            if skill.mcp_server is None and skill.mcp_tools:
                raise self._error_factory(
                    f"skill {skill.tool_name!r} declares MCP tools without a server"
                )
            if skill.mcp_server is not None and not skill.mcp_tools:
                raise self._error_factory(
                    f"skill {skill.tool_name!r} must declare at least one MCP tool"
                )
        return agent.skills

    def _skills_by_server(
        self, skills: tuple[SkillManifest, ...]
    ) -> dict[str, tuple[SkillManifest, ...]]:
        """Group MCP-enabled skills while preserving first-reference order.

        Args:
            skills (tuple[SkillManifest, ...]): Ordered agent skills to group.
        """
        grouped: dict[str, list[SkillManifest]] = {}
        for skill in skills:
            if skill.mcp_server is None:
                continue
            grouped.setdefault(skill.mcp_server, []).append(skill)
        return {name: tuple(server_skills) for name, server_skills in grouped.items()}

    def _server_path(self, name: str) -> Path:
        """Resolve a single YAML filename beneath ``config/mcp`` safely.

        Args:
            name (str): Manifest server reference, excluding a file extension.
        """
        if not _SERVER_NAME.fullmatch(name) or ".." in name or name.endswith("."):
            raise self._error_factory(f"unsafe MCP server configuration name {name!r}")
        directory = self._directory.path / "mcp"
        candidate = directory / f"{name}.yaml"
        try:
            resolved_directory = directory.resolve(strict=True)
            resolved_candidate = candidate.resolve(strict=True)
            resolved_candidate.relative_to(resolved_directory)
        except (OSError, ValueError) as error:
            raise self._error_factory(
                f"MCP server configuration {name!r} is missing or outside config/mcp"
            ) from error
        if not resolved_candidate.is_file():
            raise self._error_factory(
                f"MCP server configuration {name!r} is not a file"
            )
        return resolved_candidate

    def _create_connection(
        self,
        configuration: McpServerConfiguration[CapabilityT],
    ) -> McpConnection:
        """Construct the existing lazy connection with typed timeout and auth settings.

        Args:
            configuration (McpServerConfiguration[CapabilityT]): Validated endpoint and connection options.
        """
        auth = None
        if configuration.authentication_mode is McpAuthenticationMode.OAUTH:
            if configuration.oauth is None:
                raise self._error_factory(
                    f"server {configuration.binding.server!r} is missing OAuth settings"
                )
            auth = McpOAuthProviderFactory().build(
                configuration.binding.url, configuration.oauth
            )
        if (
            configuration.authentication_mode
            is McpAuthenticationMode.OAUTH_ON_BEHALF_OF
        ):
            if configuration.delegated_oauth is None:
                raise self._error_factory(
                    f"server {configuration.binding.server!r} is missing delegated OAuth settings"
                )
            if self._delegated_token_source is None:
                raise self._error_factory(
                    f"server {configuration.binding.server!r} requires an injected delegated token source"
                )
        return McpConnection(
            configuration.binding,
            timeout_seconds=configuration.request_timeout_seconds,
            auth=auth,
            headers=configuration.headers,
            network=configuration.network,
            delegated_oauth=configuration.delegated_oauth,
            delegated_token_source=self._delegated_token_source,
        )
