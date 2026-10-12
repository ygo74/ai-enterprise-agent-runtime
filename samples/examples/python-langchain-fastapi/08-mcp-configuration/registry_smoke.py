"""Load the declarative MCP configuration example without network access."""

from __future__ import annotations

import asyncio
from enum import StrEnum
from pathlib import Path

from ygo74.agent_runtime.domains.auth.tokens import AccessToken, DelegatedTokenRequest
from ygo74.agent_runtime.domains.configuration.directory import ConfigurationDirectory
from ygo74.agent_runtime.domains.configuration.manifests import (
    AgentManifestLoader,
    SkillManifestLoader,
)
from ygo74.agent_runtime.domains.mcp.registry import McpAgentRegistryLoader
from ygo74.agent_runtime.domains.security.floor import SecurityFloor
from ygo74.agent_runtime.domains.security.permissions import (
    Permission,
    PermissionRegistry,
)


class MailCapability(StrEnum):
    """Logical capability aliases recognized by these MCP server files."""

    SEARCH = "search_mail"
    SEND = "send_mail"


class OfflineOAuthOnBehalfOfTokenSource:
    """Provide a fake audience-specific token without contacting an identity provider.

    This source is used only to prove the registry accepts the application's
    OBO integration point. The smoke path never invokes it or opens a connection.
    """

    async def token_for(self, request: DelegatedTokenRequest) -> AccessToken:
        """Return an offline token for the configured audience.

        Args:
            request (DelegatedTokenRequest): Subject token and target settings from the runtime.
        """
        return AccessToken("offline-token", audience=request.audience)


async def main() -> None:
    """Load, display, and close the registry without opening any MCP session."""
    root = Path(__file__).resolve().parent
    configuration_directory = ConfigurationDirectory(root / "config")
    permissions = PermissionRegistry(
        [Permission("mail", "read"), Permission("mail", "send")]
    )
    manifest_loader = AgentManifestLoader(
        configuration_directory,
        SkillManifestLoader(permissions, SecurityFloor(())),
    )
    registry = McpAgentRegistryLoader(
        configuration_directory,
        MailCapability,
        delegated_token_source=OfflineOAuthOnBehalfOfTokenSource(),
    ).load(manifest_loader.load("mail-assistant"))
    try:
        expected_servers = {
            "find_mail": "mail",
            "send_mail": "mail",
            "search_archive": "archive",
            "delegated_lookup": "delegated",
        }
        for tool_name, expected_server in expected_servers.items():
            view = registry.for_skill(tool_name)
            if view.server_name != expected_server:
                raise AssertionError(
                    f"{tool_name} resolved to {view.server_name!r}, "
                    f"expected {expected_server!r}"
                )
            print(f"{tool_name}: server={view.server_name}, tools={dict(view.tools)}")
        print(f"loaded servers: {', '.join(registry.server_names)}")
    finally:
        await registry.aclose()


if __name__ == "__main__":
    asyncio.run(main())
