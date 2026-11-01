"""Resolve the sample agent's declarative HTTP settings without opening a server."""

from __future__ import annotations

from pathlib import Path

from ygo74.agent_runtime.domains.configuration.agent_http_configuration import (
    AgentHttpSettingsBuilder,
)
from ygo74.agent_runtime.domains.configuration.directory import (
    ConfigurationDirectory,
)
from ygo74.agent_runtime.domains.configuration.environment import EnvironmentFile
from ygo74.agent_runtime.domains.configuration.manifests import (
    AgentManifestLoader,
    SkillManifestLoader,
)
from ygo74.agent_runtime.domains.security.floor import SecurityFloor
from ygo74.agent_runtime.domains.security.permissions import (
    Permission,
    PermissionRegistry,
)


def main() -> None:
    """Load the HTTP declaration and print only non-secret hosting settings."""
    root = Path(__file__).resolve().parent
    EnvironmentFile(root / ".env").load()
    configuration = ConfigurationDirectory(root / "config")
    permissions = PermissionRegistry(
        [Permission("mail", "read"), Permission("mail", "send")]
    )
    manifest = AgentManifestLoader(
        configuration, SkillManifestLoader(permissions, SecurityFloor(()))
    ).load("mail-assistant")
    if manifest.http is None:
        raise RuntimeError("mail-assistant must declare HTTP settings")

    settings = AgentHttpSettingsBuilder().build(manifest.http)
    endpoints = ", ".join(endpoint.value for endpoint in settings.endpoints)
    limits = ", ".join(settings.rate_limit.limits) if settings.rate_limit else "disabled"
    print(f"endpoints: {endpoints}")
    print(f"authentication: {settings.authentication.mode.value}")
    print(f"rate limits: {limits}")


if __name__ == "__main__":
    main()
