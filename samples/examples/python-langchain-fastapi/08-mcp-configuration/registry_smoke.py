"""Load the declarative MCP configuration example without network access."""

from __future__ import annotations

import asyncio
from enum import StrEnum
from pathlib import Path

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


async def main() -> None:
    """Load, display, and close the registry without opening any MCP session."""
    root = Path(__file__).resolve().parent
    configuration_directory = ConfigurationDirectory(root / "config")
    permissions = PermissionRegistry([Permission("mail", "read"), Permission("mail", "send")])
    manifest_loader = AgentManifestLoader(
        configuration_directory,
        SkillManifestLoader(permissions, SecurityFloor(())),
    )
    registry = McpAgentRegistryLoader(
        configuration_directory,
        MailCapability,
    ).load(manifest_loader.load("mail-assistant"))
    try:
        for tool_name in ("find_mail", "send_mail", "search_archive"):
            view = registry.for_skill(tool_name)
            print(f"{tool_name}: server={view.server_name}, tools={dict(view.tools)}")
        print(f"loaded servers: {', '.join(registry.server_names)}")
    finally:
        await registry.aclose()


if __name__ == "__main__":
    asyncio.run(main())
