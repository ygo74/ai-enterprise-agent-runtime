"""Regression budgets for declarative MCP registry setup and skill lookup."""

from __future__ import annotations

import asyncio
import json
import statistics
import time
from enum import StrEnum
from pathlib import Path

from ygo74.agent_runtime.domains.auth.agent_principal import AgentPrincipal
from ygo74.agent_runtime.domains.configuration.directory import ConfigurationDirectory
from ygo74.agent_runtime.domains.contracts.manifests import AgentManifest, SkillManifest
from ygo74.agent_runtime.domains.mcp.registry import (
    McpAgentRegistry,
    McpAgentRegistryLoader,
)
from ygo74.agent_runtime.domains.mcp.request_context import (
    McpOutboundHeaderResolver,
    McpRequestContext,
    McpRequestContextRegistry,
)
from ygo74.agent_runtime.domains.security.operations import (
    OperationType,
    RiskLevel,
    ToolOperationDescriptor,
)
from ygo74.agent_runtime.domains.security.permissions import Permission


class Capability(StrEnum):
    """Application capability mapped by every benchmark server."""

    SEARCH = "search_mail"


def _skill(tool_name: str, server_name: str) -> SkillManifest:
    """Create one MCP-enabled benchmark skill.

    Args:
        tool_name (str): Unique skill identity within the benchmark agent.
        server_name (str): One of the ten shared server configuration names.
    """
    return SkillManifest(
        tool_name=tool_name,
        implementation=f"mail.{tool_name}",
        description="Search configured mail sources.",
        operation=ToolOperationDescriptor(
            tool_name=tool_name,
            operation_type=OperationType.READ,
            risk_level=RiskLevel.LOW,
            required_permission=Permission("mail", "read"),
            confirmation_required_by_default=False,
        ),
        mcp_server=server_name,
        mcp_tools=("search_mail",),
    )


def _budget(name: str) -> float:
    """Read one p95 threshold from the shared repository baseline.

    Args:
        name (str): Performance threshold key.
    """
    baseline = Path("tests/performance/baselines/performance_thresholds.json")
    return float(json.loads(baseline.read_text(encoding="utf-8"))[name])


def test_mcp_registry_construction_stays_within_p95_budget(tmp_path: Path) -> None:
    """Twenty skills and ten YAML servers load without network setup under budget."""
    config_root = tmp_path / "config"
    server_directory = config_root / "mcp"
    server_directory.mkdir(parents=True)
    for index in range(10):
        (server_directory / f"server-{index}.yaml").write_text(
            f"server: server-{index}\n"
            "transport: http\n"
            f"url: https://server-{index}.example.test/mcp\n"
            "capabilities: [search_mail]\n"
            "tools: {search_mail: remote_search}\n",
            encoding="utf-8",
        )
    skills = tuple(
        _skill(f"search_{index}", f"server-{index // 2}") for index in range(20)
    )
    agent = AgentManifest(
        name="benchmark",
        description="MCP registry benchmark.",
        instructions="Search the configured sources.",
        skills=skills,
    )
    loader = McpAgentRegistryLoader(
        ConfigurationDirectory(config_root), Capability, environment={}
    )
    elapsed_ms: list[float] = []
    registries: list[McpAgentRegistry[Capability]] = []

    for _ in range(100):
        started = time.perf_counter()
        registry = loader.load(agent)
        elapsed_ms.append((time.perf_counter() - started) * 1000)
        registries.append(registry)

    async def close_registries() -> None:
        """Close the lazy benchmark connections after timed construction."""
        for registry in registries:
            await registry.aclose()

    asyncio.run(close_registries())
    p95 = statistics.quantiles(elapsed_ms, n=100)[94]
    assert p95 < _budget("mcp_registry_construction_p95_ms")


def test_mcp_skill_view_lookup_stays_within_p95_budget(tmp_path: Path) -> None:
    """Resolving an existing skill and allowed tool alias stays below one ms."""
    config_root = tmp_path / "config"
    server_directory = config_root / "mcp"
    server_directory.mkdir(parents=True)
    (server_directory / "mail.yaml").write_text(
        "server: mail\n"
        "transport: http\n"
        "url: https://mail.example.test/mcp\n"
        "capabilities: [search_mail]\n"
        "tools: {search_mail: remote_search}\n",
        encoding="utf-8",
    )
    agent = AgentManifest(
        name="benchmark",
        description="MCP lookup benchmark.",
        instructions="Search mail.",
        skills=(_skill("search_mail", "mail"),),
    )
    registry = McpAgentRegistryLoader(
        ConfigurationDirectory(config_root), Capability, environment={}
    ).load(agent)
    elapsed_ms: list[float] = []
    for _ in range(1000):
        started = time.perf_counter()
        view = registry.for_skill("search_mail")
        view.remote_tool("search_mail")
        elapsed_ms.append((time.perf_counter() - started) * 1000)

    asyncio.run(registry.aclose())
    p95 = statistics.quantiles(elapsed_ms, n=100)[94]
    assert p95 < _budget("mcp_skill_tool_lookup_p95_ms")


def test_mcp_context_header_rendering_stays_within_p95_budget() -> None:
    """Rendering identity and correlation templates stays under the per-request budget."""
    contexts = McpRequestContextRegistry()
    principal = AgentPrincipal(
        subject="benchmark-user",
        email="benchmark@example.test",
        display_name="Benchmark User",
        roles=frozenset({"reader", "writer"}),
    )
    for request_id in range(1000):
        contexts.register(
            request_id,
            McpRequestContext(
                principal=principal,
                request_id=f"req-{request_id}",
                conversation_id=f"conversation-{request_id}",
            ),
        )
    resolver = McpOutboundHeaderResolver(
        {
            "X-User-ID": "{{USER_ID}}",
            "X-User-Roles": "{{USER_ROLES}}",
            "X-Request-ID": "{{REQUEST_ID}}",
            "X-Conversation-ID": "{{CONVERSATION_ID}}",
        },
        contexts,
    )
    elapsed_ms: list[float] = []

    async def measure() -> None:
        """Resolve a unique context for each timed header-render operation."""
        for request_id in range(1000):
            started = time.perf_counter()
            await resolver.for_request(request_id)
            elapsed_ms.append((time.perf_counter() - started) * 1000)

    asyncio.run(measure())
    p95 = statistics.quantiles(elapsed_ms, n=100)[94]
    assert p95 < _budget("mcp_header_rendering_p95_ms")
