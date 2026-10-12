"""The distributed manifest schemas stay aligned with their typed inputs."""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator
from pydantic import BaseModel
from ygo74.agent_runtime.domains.configuration.directory import ConfigurationDirectory
from ygo74.agent_runtime.domains.configuration.manifest_inputs import (
    AgentManifestInput,
    SkillManifestInput,
)
from ygo74.agent_runtime.domains.configuration.manifest_schemas import ManifestSchemas
from ygo74.agent_runtime.domains.configuration.manifests import (
    AgentManifestLoader,
    ConfigurationError,
    SkillManifestLoader,
    YamlDocument,
)
from ygo74.agent_runtime.domains.mcp.configuration import McpServerConfigurationInput
from ygo74.agent_runtime.domains.security.floor import SecurityFloor
from ygo74.agent_runtime.domains.security.permissions import (
    Permission,
    PermissionRegistry,
)


@pytest.mark.parametrize(
    ("read_schema", "input_model", "schema_id"),
    [
        (
            ManifestSchemas.agent,
            AgentManifestInput,
            "urn:ygo74:agent-runtime:agent-manifest:1",
        ),
        (
            ManifestSchemas.skill,
            SkillManifestInput,
            "urn:ygo74:agent-runtime:skill-manifest:1",
        ),
        (
            ManifestSchemas.mcp_server,
            McpServerConfigurationInput,
            "urn:ygo74:agent-runtime:mcp-server-configuration:1",
        ),
    ],
)
def test_packaged_schema_matches_its_typed_input(
    read_schema: Callable[[], str],
    input_model: type[BaseModel],
    schema_id: str,
) -> None:
    schema = json.loads(read_schema())

    assert schema["$schema"] == "https://json-schema.org/draft/2020-12/schema"
    assert schema["$id"] == schema_id
    del schema["$schema"]
    del schema["$id"]
    assert schema == input_model.model_json_schema()


def test_skill_schema_accepts_mcp_tools_without_local_server() -> None:
    """The containing agent may supply the server for these MCP tools."""
    schema = json.loads(ManifestSchemas.skill())
    validator = Draft202012Validator(schema)
    manifest = _skill_manifest(mcp_tools=["search_mail"])

    errors = tuple(validator.iter_errors(manifest))

    assert not errors
    assert SkillManifestInput.model_validate(manifest).mcp_server is None


def test_agent_schema_accepts_an_optional_default_mcp_server() -> None:
    """The agent-level server remains optional for agents with or without MCP."""
    schema = Draft202012Validator(json.loads(ManifestSchemas.agent()))
    base = {
        "name": "mail-agent",
        "description": "Mail agent.",
        "skills": ["lookup"],
    }
    with_default = {**base, "mcp_server": "mail"}

    assert not tuple(schema.iter_errors(base))
    assert not tuple(schema.iter_errors(with_default))
    assert AgentManifestInput.model_validate(base).mcp_server is None
    assert AgentManifestInput.model_validate(with_default).mcp_server == "mail"


def test_skill_schema_accepts_a_named_server_for_its_mcp_tools() -> None:
    """A skill with MCP tools is valid when it names the server to use."""
    schema = json.loads(ManifestSchemas.skill())
    validator = Draft202012Validator(schema)

    errors = tuple(
        validator.iter_errors(
            _skill_manifest(mcp_tools=["search_mail"], mcp_server="gmail-http")
        )
    )

    assert not errors
    assert (
        SkillManifestInput.model_validate(
            _skill_manifest(mcp_tools=["search_mail"], mcp_server="gmail-http")
        ).mcp_server
        == "gmail-http"
    )


def test_skill_schema_requires_tools_when_a_server_is_declared() -> None:
    """A server reference without an allow-list is not a usable MCP skill."""
    manifest = _skill_manifest(mcp_tools=[], mcp_server="gmail-http")
    validator = Draft202012Validator(json.loads(ManifestSchemas.skill()))

    assert tuple(validator.iter_errors(manifest))
    with pytest.raises(ValueError, match="mcp_tools"):
        SkillManifestInput.model_validate(manifest)


def test_skill_yaml_is_validated_against_the_packaged_schema_at_runtime(
    tmp_path: Path,
) -> None:
    """Runtime loading applies the same schema used by editor tooling."""
    path = tmp_path / "skill.yaml"
    path.write_text(
        "tool_name: lookup\n"
        "implementation: mail.lookup\n"
        "description: Search messages.\n"
        "operation:\n"
        "  type: READ\n"
        "  risk: LOW\n"
        "  permission: mail:read\n"
        "  confirmation_required: false\n"
        "unexpected_field: rejected\n",
        encoding="utf-8",
    )

    with pytest.raises(ConfigurationError, match="unexpected_field"):
        YamlDocument(path).validate(SkillManifestInput, schema=ManifestSchemas.skill())


def test_agent_loader_retains_default_server_for_skill_level_resolution(
    tmp_path: Path,
) -> None:
    """The assembled agent carries its default alongside unresolved skill references."""
    config_root = tmp_path / "config"
    agent_directory = config_root / "agents" / "mail"
    skill_directory = config_root / "skills" / "mail" / "lookup"
    agent_directory.mkdir(parents=True)
    skill_directory.mkdir(parents=True)
    (agent_directory / "agent.yaml").write_text(
        "name: mail\ndescription: Mail agent.\nmcp_server: mail\nskills: [lookup]\n",
        encoding="utf-8",
    )
    (agent_directory / "AGENT.md").write_text("Use mail tools.\n", encoding="utf-8")
    (skill_directory / "skill.yaml").write_text(
        "tool_name: lookup\n"
        "implementation: mail.lookup\n"
        "description: Search mail.\n"
        "operation:\n"
        "  type: READ\n"
        "  risk: LOW\n"
        "  permission: mail:read\n"
        "  confirmation_required: false\n"
        "mcp_tools: [search_mail]\n",
        encoding="utf-8",
    )
    skill_loader = SkillManifestLoader(
        PermissionRegistry([Permission("mail", "read")]), SecurityFloor(())
    )

    agent = AgentManifestLoader(ConfigurationDirectory(config_root), skill_loader).load(
        "mail"
    )

    assert agent.mcp_server == "mail"
    assert agent.skill("lookup").mcp_server is None
    assert agent.skill("lookup").mcp_tools == ("search_mail",)

    (agent_directory / "agent.yaml").write_text(
        "name: mail\ndescription: Mail agent.\nskills: [lookup]\n",
        encoding="utf-8",
    )
    with pytest.raises(ConfigurationError, match="without a skill or agent MCP server"):
        AgentManifestLoader(ConfigurationDirectory(config_root), skill_loader).load(
            "mail"
        )


def _skill_manifest(
    *, mcp_tools: list[str], mcp_server: str | None = None
) -> dict[str, object]:
    """Return a valid skill declaration with the supplied MCP tool list."""
    manifest: dict[str, object] = {
        "tool_name": "lookup",
        "implementation": "mail.lookup",
        "description": "Search messages.",
        "operation": {
            "type": "READ",
            "risk": "LOW",
            "permission": "mail:read",
            "confirmation_required": False,
        },
        "mcp_tools": mcp_tools,
    }
    if mcp_server is not None:
        manifest["mcp_server"] = mcp_server
    return manifest
