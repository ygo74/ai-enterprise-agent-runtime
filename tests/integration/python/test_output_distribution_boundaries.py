from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest
import tomllib

ROOT = Path(__file__).resolve().parents[3]
PYTHON_PACKAGES = ROOT / "packages" / "python"
FRAMEWORK_MODULES = frozenset({"langchain", "langchain_core", "agent_framework", "crewai"})
FRAMEWORK_DISTRIBUTIONS = frozenset(
    {"langchain", "langchain-core", "agent-framework", "agent-framework-core", "crewai"}
)


def _dependencies(project: str) -> set[str]:
    with (PYTHON_PACKAGES / project / "pyproject.toml").open("rb") as manifest:
        metadata = tomllib.load(manifest)
    return {
        re.split(r"[\s\[<>=!~;]", dependency, maxsplit=1)[0].lower().replace("_", "-")
        for dependency in metadata["project"].get("dependencies", [])
    }


@pytest.mark.parametrize("project", ["security", "agents", "mcpserver", "meta"])
def test_core_distribution_has_no_framework_dependency(project: str) -> None:
    dependencies = _dependencies(project)
    assert not dependencies.intersection(FRAMEWORK_DISTRIBUTIONS)
    assert not dependencies.intersection(
        {"ygo74-agent-runtime-langchain", "ygo74-agent-runtime-agentframework"}
    )


def test_agents_core_has_no_framework_import() -> None:
    core = PYTHON_PACKAGES / "agents" / "ygo74"
    for module in core.rglob("*.py"):
        tree = ast.parse(module.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports = [alias.name.split(".")[0] for alias in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module:
                imports = [node.module.split(".")[0]]
            else:
                continue
            assert not FRAMEWORK_MODULES.intersection(imports), module


@pytest.mark.parametrize("project", ["langchain", "agentframework"])
def test_integration_owns_only_its_namespace(project: str) -> None:
    package = PYTHON_PACKAGES / project
    owned = package / "ygo74" / "agent_runtime" / "integrations" / project
    assert owned.is_dir()
    assert (owned / "py.typed").is_file()
    assert (owned / "__init__.py").is_file()
    assert not (package / "ygo74" / "__init__.py").exists()
    assert not (package / "ygo74" / "agent_runtime" / "__init__.py").exists()
    assert not (package / "ygo74" / "agent_runtime" / "integrations" / "__init__.py").exists()
    for source in (package / "ygo74").rglob("*"):
        if source.is_file() and source.suffix in {".py", ".typed"}:
            assert source.is_relative_to(owned), source


def test_integration_dependency_graph_is_one_way() -> None:
    langchain = _dependencies("langchain")
    agentframework = _dependencies("agentframework")
    assert "ygo74-agent-runtime-agents" in langchain
    assert "ygo74-agent-runtime-agents" in agentframework
    assert langchain.intersection({"langchain", "langchain-core"})
    assert agentframework.intersection({"agent-framework", "agent-framework-core"})
    assert not langchain.intersection({"agent-framework", "agent-framework-core"})
    assert not agentframework.intersection({"langchain", "langchain-core"})
