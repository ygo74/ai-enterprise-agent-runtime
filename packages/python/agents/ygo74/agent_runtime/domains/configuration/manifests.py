"""Load and validate the files in delivered agent and skill packages."""

from __future__ import annotations

from pathlib import Path
from typing import Any, TypeVar

import yaml
from pydantic import BaseModel, ValidationError
from ygo74.agent_runtime.domains.configuration.directory import ConfigurationDirectory
from ygo74.agent_runtime.domains.configuration.manifest_inputs import (
    AgentManifestInput,
    SkillManifestInput,
)
from ygo74.agent_runtime.domains.contracts.manifests import AgentManifest, SkillManifest
from ygo74.agent_runtime.domains.errors import DomainError
from ygo74.agent_runtime.domains.security.floor import SecurityFloor
from ygo74.agent_runtime.domains.security.operations import ToolOperationDescriptor
from ygo74.agent_runtime.domains.security.permissions import PermissionRegistry

SKILL_MANIFEST = "skill.yaml"
SKILL_PROMPT = "SKILL.md"
AGENT_MANIFEST = "agent.yaml"
AGENT_INSTRUCTIONS = "AGENT.md"

_SKILLS = "skills"
_AGENTS = "agents"
ManifestInputT = TypeVar("ManifestInputT", bound=BaseModel)


class ConfigurationError(DomainError):
    """Raised when delivered configuration cannot be turned into a manifest."""


class YamlDocument:
    """One YAML mapping read from disk.

    Args:
        path (Path): Dotted claim path or filesystem path being resolved, as indicated by this API.
    """
    def __init__(self, path: Path) -> None:
        """Initialize the instance runtime data with the supplied collaborators and configuration.

        Args:
            path (Path): Dotted claim path or filesystem path being resolved, as indicated by this API.
        """
        self._path = path
        self._data = self._read(path)

    @staticmethod
    def _read(path: Path) -> dict[str, Any]:
        """Parse a YAML mapping, refusing anything else.

        Args:
            path (Path): Dotted claim path or filesystem path being resolved, as indicated by this API.
        """
        try:
            loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
        except (OSError, yaml.YAMLError) as error:
            raise ConfigurationError(f"could not read {path}: {error}") from error
        if not isinstance(loaded, dict):
            raise ConfigurationError(f"{path} must contain a mapping")
        return loaded

    def validate(self, model: type[ManifestInputT]) -> ManifestInputT:
        """Validate this raw YAML mapping against its typed input contract.

        Args:
            model (type[ManifestInputT]): Provider-visible model or agent identifier.
        """
        try:
            return model.model_validate(self._data)
        except ValidationError as error:
            issues = "; ".join(
                f"{'.'.join(str(part) for part in detail['loc'])}: {detail['msg']}"
                for detail in error.errors(include_input=False, include_url=False)
            )
            raise ConfigurationError(f"{self._path} does not match its manifest schema: {issues}") from error

    def text(self, key: str) -> str:
        """Return a mandatory text field.

        Args:
            key (str): The identifier or key used to locate the corresponding registered value.
        """
        value = self._data.get(key)
        if not isinstance(value, str) or not value.strip():
            raise ConfigurationError(f"{self._path}: field {key!r} must be a non-empty string")
        return value.strip()

    def flag(self, key: str) -> bool:
        """Return a mandatory boolean field.

        Args:
            key (str): The identifier or key used to locate the corresponding registered value.
        """
        value = self._data.get(key)
        if not isinstance(value, bool):
            raise ConfigurationError(f"{self._path}: field {key!r} must be true or false")
        return value

    def texts(self, key: str) -> tuple[str, ...]:
        """Return an optional list of text values.

        Args:
            key (str): The identifier or key used to locate the corresponding registered value.
        """
        value = self._data.get(key, [])
        if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
            raise ConfigurationError(f"{self._path}: field {key!r} must be a list of strings")
        return tuple(item.strip() for item in value)

    def section(self, key: str) -> YamlSection:
        """Return a mandatory nested mapping.

        Args:
            key (str): The identifier or key used to locate the corresponding registered value.
        """
        value = self._data.get(key)
        if not isinstance(value, dict):
            raise ConfigurationError(f"{self._path}: field {key!r} must be a mapping")
        return YamlSection(self._path, key, value)


class YamlSection:
    """A nested mapping of a YAML document.

    Args:
        path (Path): Dotted claim path or filesystem path being resolved, as indicated by this API.
        name (str): The name used to locate or label the value being processed.
        data (dict[str, Any]): The structured input whose fields are being read or validated.
    """
    def __init__(self, path: Path, name: str, data: dict[str, Any]) -> None:
        """Initialize the instance runtime data with the supplied collaborators and configuration.

        Args:
            path (Path): Dotted claim path or filesystem path being resolved, as indicated by this API.
            name (str): The name used to locate or label the value being processed.
            data (dict[str, Any]): The structured input whose fields are being read or validated.
        """
        self._path = path
        self._name = name
        self._data = data

    def text(self, key: str) -> str:
        """Return a mandatory text field of the section.

        Args:
            key (str): The identifier or key used to locate the corresponding registered value.
        """
        value = self._data.get(key)
        if not isinstance(value, str) or not value.strip():
            raise ConfigurationError(f"{self._path}: {self._name}.{key} must be a non-empty string")
        return value.strip()

    def flag(self, key: str) -> bool:
        """Return a mandatory boolean field of the section.

        Args:
            key (str): The identifier or key used to locate the corresponding registered value.
        """
        value = self._data.get(key)
        if not isinstance(value, bool):
            raise ConfigurationError(f"{self._path}: {self._name}.{key} must be true or false")
        return value


class SkillManifestLoader:
    """Turn one delivered skill package into a validated manifest.

    Args:
        permissions (PermissionRegistry): Permissions granted to the user or required by the operation.
        floor (SecurityFloor): Configured approval or authorization threshold for the operation.
    """
    def __init__(self, permissions: PermissionRegistry, floor: SecurityFloor) -> None:
        """Initialize the instance runtime data with the supplied collaborators and configuration.

        Args:
            permissions (PermissionRegistry): Permissions granted to the user or required by the operation.
            floor (SecurityFloor): Configured approval or authorization threshold for the operation.
        """
        self._permissions = permissions
        self._floor = floor

    def load(self, package: Path) -> SkillManifest:
        """Read and validate one package, then enforce its code-owned security floor.

        Args:
            package (Path): Python package root containing the manifest and its declared resources.
        """
        path = self._manifest_path(package)
        source = YamlDocument(path).validate(SkillManifestInput)
        operation = ToolOperationDescriptor(
            tool_name=source.tool_name,
            operation_type=source.operation.type,
            risk_level=source.operation.risk,
            required_permission=self._permissions.resolve(source.operation.permission),
            confirmation_required_by_default=source.operation.confirmation_required,
        )
        self._floor.enforce(operation)
        return SkillManifest(
            tool_name=source.tool_name,
            implementation=source.implementation,
            description=source.description,
            operation=operation,
            mcp_tools=source.mcp_tools,
            prompt=self._prompt(package),
        )

    @staticmethod
    def _manifest_path(package: Path) -> Path:
        """Return the manifest file of a package, or fail.

        Args:
            package (Path): Python package root containing the manifest and its declared resources.
        """
        path = package / SKILL_MANIFEST
        if not path.is_file():
            raise ConfigurationError(f"skill package {package.name!r} has no {SKILL_MANIFEST}")
        return path

    @staticmethod
    def _prompt(package: Path) -> str:
        """Return the reasoning instructions, empty for a deterministic skill.

        Args:
            package (Path): Python package root containing the manifest and its declared resources.
        """
        path = package / SKILL_PROMPT
        if not path.is_file():
            return ""
        try:
            return path.read_text(encoding="utf-8").strip()
        except OSError as error:
            raise ConfigurationError(f"could not read {path}: {error}") from error


class AgentManifestLoader:
    """Assemble an agent manifest from its delivered configuration.

    Args:
        directory (ConfigurationDirectory): Repository-backed configuration directory used to load agent manifests.
        skills (SkillManifestLoader): Declared agent skills checked against descriptor capabilities.
    """
    def __init__(self, directory: ConfigurationDirectory, skills: SkillManifestLoader) -> None:
        """Initialize the instance runtime data with the supplied collaborators and configuration.

        Args:
            directory (ConfigurationDirectory): Repository-backed configuration directory used to load agent manifests.
            skills (SkillManifestLoader): Declared agent skills checked against descriptor capabilities.
        """
        self._directory = directory
        self._skills = skills

    def load(self, agent: str) -> AgentManifest:
        """Read the identity, instructions and declared capabilities of an agent.

        Args:
            agent (str): The agent configuration or descriptor being processed.
        """
        folder = self._directory.require(_AGENTS, agent)
        document = YamlDocument(folder / AGENT_MANIFEST)
        source = document.validate(AgentManifestInput)
        return AgentManifest(
            name=source.name,
            description=source.description,
            instructions=self._instructions(folder),
            skills=self._declared_skills(agent, source.skills),
        )

    @staticmethod
    def _instructions(folder: Path) -> str:
        """Return the system instructions delivered with the agent.

        Args:
            folder (Path): Directory inspected for agent instructions or package-local metadata.
        """
        path = folder / AGENT_INSTRUCTIONS
        if not path.is_file():
            raise ConfigurationError(f"{folder} has no {AGENT_INSTRUCTIONS}")
        try:
            instructions = path.read_text(encoding="utf-8").strip()
        except OSError as error:
            raise ConfigurationError(f"could not read {path}: {error}") from error
        if not instructions:
            raise ConfigurationError(f"{path} is empty")
        return instructions

    def _declared_skills(self, agent: str, names: tuple[str, ...]) -> tuple[SkillManifest, ...]:
        """Load the packages declared by the agent, in their declared order.

        Args:
            agent (str): The agent configuration or descriptor being processed.
            names (tuple[str, ...]): Tool call IDs and names used to correlate related blocks.
        """
        available = {package.name: package for package in self._directory.children(_SKILLS, agent)}
        return tuple(self._declared_skill(agent, name, available) for name in names)

    def _declared_skill(self, agent: str, name: str, available: dict[str, Path]) -> SkillManifest:
        """Load a declared package, or report which packages are available.

        Args:
            agent (str): The agent configuration or descriptor being processed.
            name (str): The name used to locate or label the value being processed.
            available (dict[str, Path]): Declared skill files indexed by tool name for resolution.
        """
        package = available.get(name)
        if package is None:
            known = ", ".join(sorted(available)) or "none"
            raise ConfigurationError(f"agent {agent!r} declares skill {name!r}; delivered packages: {known}")
        return self._skills.load(package)
