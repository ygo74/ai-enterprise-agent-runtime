"""Access the versioned JSON Schema documents shipped with this distribution."""

from __future__ import annotations

from importlib.resources import files
from typing import ClassVar


class ManifestSchemas:
    """Read the stable Draft 2020-12 schemas for delivered YAML manifests."""

    _SCHEMAS: ClassVar[dict[str, str]] = {
        "agent": "agent.schema.json",
        "skill": "skill.schema.json",
    }

    @classmethod
    def read(cls, name: str) -> str:
        """Return a schema document as UTF-8 JSON text."""
        filename = cls._SCHEMAS.get(name)
        if filename is None:
            raise ValueError(f"unknown manifest schema {name!r}; expected 'agent' or 'skill'")
        return files("ygo74.agent_runtime.domains.configuration.manifest_schemas").joinpath(
            "schemas", filename
        ).read_text(encoding="utf-8")

    @classmethod
    def agent(cls) -> str:
        """Return the schema for ``agent.yaml``."""
        return cls.read("agent")

    @classmethod
    def skill(cls) -> str:
        """Return the schema for ``skill.yaml``."""
        return cls.read("skill")
