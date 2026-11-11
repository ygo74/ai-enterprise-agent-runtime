"""Run a deterministic FastAPI host with the sample manifest's MCP surface."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from fastapi import FastAPI
from ygo74.agent_runtime.domains.configuration.agent_http_configuration import (
    AgentHttpSettingsBuilder,
)
from ygo74.agent_runtime.domains.configuration.directory import ConfigurationDirectory
from ygo74.agent_runtime.domains.configuration.environment import EnvironmentFile
from ygo74.agent_runtime.domains.configuration.manifests import (
    AgentManifestLoader,
    SkillManifestLoader,
)
from ygo74.agent_runtime.domains.contracts import AgentOutput, TextContent
from ygo74.agent_runtime.domains.discovery.manifest_descriptor import (
    AdvertisedSecurity,
    AgentDescriptorFactory,
)
from ygo74.agent_runtime.domains.endpoints.hosting_factory import HostingFactory
from ygo74.agent_runtime.domains.security.floor import SecurityFloor
from ygo74.agent_runtime.domains.security.permissions import (
    Permission,
    PermissionRegistry,
)

ROOT = Path(__file__).resolve().parent


def build_app() -> FastAPI:
    """Build the sample's manifest-backed API and inbound MCP tool."""
    EnvironmentFile(ROOT / ".env").load()
    configuration = ConfigurationDirectory(ROOT / "config")
    permissions = PermissionRegistry(
        [Permission("mail", "read"), Permission("mail", "send")]
    )
    manifest = AgentManifestLoader(
        configuration,
        SkillManifestLoader(permissions, SecurityFloor(())),
    ).load("mail-assistant")
    if manifest.http is None:
        raise RuntimeError("mail-assistant must declare HTTP settings")

    settings = AgentHttpSettingsBuilder().build(manifest.http)
    descriptor = AgentDescriptorFactory(
        manifest,
        agent_id=manifest.name,
        tags=("sample",),
        created_at=datetime.now(UTC),
        security=AdvertisedSecurity.of(
            jwt_validation=None,
            api_key_resolver=None,
            authenticators=settings.authentication.authenticators,
        ),
    ).build()
    app = FastAPI(title="Agent MCP hosting smoke")

    @app.get("/health/ready")
    async def ready() -> dict[str, bool]:
        """Report local host availability without returning configuration."""
        return {"ready": True}

    async def invoke(payload: dict[str, Any]) -> AgentOutput:
        """Echo one normalized agent message through the MCP adapter."""
        return AgentOutput((TextContent(f"Echo: {payload['input']}"),))

    HostingFactory(app).add_agent(invoke, descriptor).add_http_settings(
        settings
    ).register()
    return app


app = build_app()
