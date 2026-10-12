"""Access the versioned JSON Schema documents shipped with this distribution."""

from __future__ import annotations

import json
from collections.abc import Mapping
from functools import lru_cache
from importlib.resources import files
from pathlib import Path
from typing import Any, ClassVar


class ManifestSchemas:
    """Read the stable Draft 2020-12 schemas for delivered YAML manifests."""
    _SCHEMAS: ClassVar[dict[str, str]] = {
        "agent": "agent.schema.json",
        "skill": "skill.schema.json",
        "mcp_server": "mcp-server.schema.json",
    }

    @classmethod
    def read(cls, name: str) -> str:
        """Return a schema document as UTF-8 JSON text.

        Args:
            name (str): The name used to locate or label the value being processed.
        """
        filename = cls._SCHEMAS.get(name)
        if filename is None:
            accepted = ", ".join(sorted(cls._SCHEMAS))
            raise ValueError(f"unknown manifest schema {name!r}; expected one of {accepted}")
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

    @classmethod
    def mcp_server(cls) -> str:
        """Return the schema for MCP server configuration YAML."""
        return cls.read("mcp_server")


class JsonSchemaValidator:
    """Validate parsed YAML mappings against the packaged Draft 2020-12 schemas."""

    @staticmethod
    def validate(document: Mapping[str, object], schema_text: str, *, path: Path) -> None:
        """Validate a document and report only field names and constraint kinds.

        Args:
            document (Mapping[str, object]): Parsed YAML mapping at the untrusted input boundary.
            schema_text (str): Versioned JSON Schema document used by editor tooling.
            path (Path): Source YAML file shown in validation diagnostics.
        """
        try:
            validator = JsonSchemaValidator._compiled_validator(schema_text)
        except ImportError as error:
            raise ValueError("JSON Schema validation requires the optional configuration dependencies") from error
        errors = tuple(
            leaf
            for error in validator.iter_errors(document)
            for leaf in _leaf_errors(error)
        )
        if errors:
            issues = "; ".join(_describe_error(error) for error in errors)
            raise ValueError(f"{path} does not match its JSON Schema: {issues}")

    @staticmethod
    @lru_cache(maxsize=32)
    def _compiled_validator(schema_text: str) -> Any:
        """Parse and check one packaged schema once, then reuse its validator.

        Args:
            schema_text (str): Versioned JSON Schema document used by editor tooling.
        """
        from jsonschema import Draft202012Validator
        from jsonschema.exceptions import SchemaError

        try:
            schema = json.loads(schema_text)
            Draft202012Validator.check_schema(schema)
        except (json.JSONDecodeError, SchemaError) as error:
            raise ValueError("packaged JSON Schema could not be read") from error
        return Draft202012Validator(schema)


def _leaf_errors(error: object) -> tuple[object, ...]:
    """Return leaf JSON Schema errors, omitting composite allOf messages.

    Args:
        error (object): Validation error returned by the JSON Schema validator.
    """
    context = getattr(error, "context", ())
    if not context:
        return (error,)
    return tuple(leaf for child in context for leaf in _leaf_errors(child))


def _describe_error(error: object) -> str:
    """Describe a schema failure without rendering the YAML value.

    Args:
        error (object): Leaf validation error returned by the JSON Schema validator.
    """
    location = ".".join(str(part) for part in getattr(error, "absolute_path", ())) or "<root>"
    validator = getattr(error, "validator", None)
    if validator == "required":
        instance = getattr(error, "instance", {})
        required = getattr(error, "validator_value", ())
        missing = sorted(set(required) - set(instance)) if isinstance(instance, Mapping) else []
        if missing:
            if len(missing) == 1:
                return f"{location} requires '{missing[0]}'"
            return f"{location} is missing required field(s) {', '.join(missing)}"
    if validator == "additionalProperties":
        instance = getattr(error, "instance", {})
        schema = getattr(error, "schema", {})
        allowed = schema.get("properties", {}) if isinstance(schema, Mapping) else {}
        if isinstance(instance, Mapping) and isinstance(allowed, Mapping):
            unknown = sorted(str(key) for key in instance if key not in allowed)
            if unknown:
                return f"field {location} has unknown field(s) {', '.join(unknown)}"
    if validator == "not":
        return f"field {location} has conflicting authentication settings"
    if validator == "enum":
        allowed = getattr(error, "validator_value", ())
        return f"field {location} must be one of {', '.join(str(value) for value in allowed)}"
    if validator == "minItems" and location == "capabilities":
        return "capabilities must list at least one capability"
    if validator == "minItems":
        return f"field {location} must contain at least {getattr(error, 'validator_value', 1)} item(s)"
    return f"field {location} violates the {validator or 'schema'} constraint"
