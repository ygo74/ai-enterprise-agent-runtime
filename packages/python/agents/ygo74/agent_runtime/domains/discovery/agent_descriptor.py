"""Canonical agent descriptor model.

The descriptor is the only source of agent identity and capability metadata. Every
discovery surface is a pure projection of this record, so nothing here may depend
on a provider dialect or on transport concerns.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import StrEnum
from typing import Any, Mapping, Sequence

from ygo74.agent_runtime.domains.discovery.discovery_errors import DiscoveryErrors

AGENT_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]*$")
AGENT_ID_MAX_LENGTH = 128


class DiscoveryVisibility(StrEnum):
    """Whether an agent appears in discovery listings."""

    LISTED = "listed"
    HIDDEN = "hidden"


class CapabilitySizeUnit(StrEnum):
    """Unit in which declared input and output size limits are expressed."""

    TOKENS = "tokens"
    CHARACTERS = "characters"
    BYTES = "bytes"


class Modality(StrEnum):
    """Well-known modality names. Custom modalities remain expressible as plain strings."""

    TEXT = "text"
    IMAGE = "image"
    AUDIO = "audio"
    VIDEO = "video"
    FILE = "file"


DEFAULT_MODALITIES: tuple[str, ...] = (str(Modality.TEXT),)


@dataclass(slots=True, frozen=True)
class AgentSkill:
    """Named unit of agent competence surfaced in the agent card and extension sections."""

    skill_id: str
    name: str
    description: str
    tags: tuple[str, ...] = ()
    examples: tuple[str, ...] = ()
    input_modalities: tuple[str, ...] | None = None
    output_modalities: tuple[str, ...] | None = None

    def __post_init__(self) -> None:
        _require_non_empty("skillId", self.skill_id)
        _require_non_empty("name", self.name)
        _require_non_empty("description", self.description)

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "skillId": self.skill_id,
            "name": self.name,
            "description": self.description,
            "tags": list(self.tags),
            "examples": list(self.examples),
        }
        if self.input_modalities is not None:
            payload["inputModalities"] = list(self.input_modalities)
        if self.output_modalities is not None:
            payload["outputModalities"] = list(self.output_modalities)
        return payload

    @classmethod
    def from_dict(cls, source: Mapping[str, Any]) -> AgentSkill:
        return cls(
            skill_id=_read_str(source, "skillId"),
            name=_read_str(source, "name"),
            description=_read_str(source, "description"),
            tags=_read_str_tuple(source, "tags"),
            examples=_read_str_tuple(source, "examples"),
            input_modalities=_read_optional_str_tuple(source, "inputModalities"),
            output_modalities=_read_optional_str_tuple(source, "outputModalities"),
        )


@dataclass(slots=True, frozen=True)
class AgentCapabilitySet:
    """Declared behavioral characteristics, validated at initialization against configuration."""

    streaming: bool = False
    input_modalities: tuple[str, ...] = DEFAULT_MODALITIES
    output_modalities: tuple[str, ...] = DEFAULT_MODALITIES
    tool_invocation: bool = False
    structured_output: bool = False
    size_unit: CapabilitySizeUnit = CapabilitySizeUnit.TOKENS
    max_input_size: int | None = None
    max_output_size: int | None = None
    extensions: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.input_modalities:
            raise DiscoveryErrors.invalid_descriptor("capabilities.inputModalities", "must not be empty")
        if not self.output_modalities:
            raise DiscoveryErrors.invalid_descriptor("capabilities.outputModalities", "must not be empty")
        if self.max_input_size is not None and self.max_input_size < 1:
            raise DiscoveryErrors.invalid_descriptor("capabilities.maxInputSize", "must be positive")
        if self.max_output_size is not None and self.max_output_size < 1:
            raise DiscoveryErrors.invalid_descriptor("capabilities.maxOutputSize", "must be positive")

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "streaming": self.streaming,
            "inputModalities": list(self.input_modalities),
            "outputModalities": list(self.output_modalities),
            "toolInvocation": self.tool_invocation,
            "structuredOutput": self.structured_output,
            "extensions": dict(self.extensions),
        }
        if self.max_input_size is not None or self.max_output_size is not None:
            payload["sizeUnit"] = str(self.size_unit)
        if self.max_input_size is not None:
            payload["maxInputSize"] = self.max_input_size
        if self.max_output_size is not None:
            payload["maxOutputSize"] = self.max_output_size
        return payload

    @classmethod
    def from_dict(cls, source: Mapping[str, Any]) -> AgentCapabilitySet:
        raw_unit = source.get("sizeUnit")
        return cls(
            streaming=bool(source.get("streaming", False)),
            input_modalities=_read_str_tuple(source, "inputModalities") or DEFAULT_MODALITIES,
            output_modalities=_read_str_tuple(source, "outputModalities") or DEFAULT_MODALITIES,
            tool_invocation=bool(source.get("toolInvocation", False)),
            structured_output=bool(source.get("structuredOutput", False)),
            size_unit=CapabilitySizeUnit(str(raw_unit)) if raw_unit is not None else CapabilitySizeUnit.TOKENS,
            max_input_size=_read_optional_int(source, "maxInputSize"),
            max_output_size=_read_optional_int(source, "maxOutputSize"),
            extensions=dict(source.get("extensions") or {}),
        )


@dataclass(slots=True, frozen=True)
class AgentDescriptor:
    """Provider-neutral description of one exposed agent. Immutable after initialization."""

    agent_id: str
    route_key: str
    display_name: str
    description: str
    version: str
    owner: str
    created_at_utc: datetime
    capabilities: AgentCapabilitySet
    documentation_url: str | None = None
    tags: tuple[str, ...] = ()
    skills: tuple[AgentSkill, ...] = ()
    security_schemes: tuple[str, ...] = ()
    discovery_visibility: DiscoveryVisibility = DiscoveryVisibility.LISTED
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self._validate_agent_id()
        _require_non_empty("routeKey", self.route_key)
        _require_non_empty("displayName", self.display_name)
        _require_non_empty("description", self.description)
        _require_non_empty("version", self.version)
        _require_non_empty("owner", self.owner)
        self._validate_skills()

    @property
    def is_listed(self) -> bool:
        return self.discovery_visibility is DiscoveryVisibility.LISTED

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "agentId": self.agent_id,
            "routeKey": self.route_key,
            "displayName": self.display_name,
            "description": self.description,
            "version": self.version,
            "owner": self.owner,
            "createdAtUtc": _format_timestamp(self.created_at_utc),
            "tags": list(self.tags),
            "capabilities": self.capabilities.to_dict(),
            "skills": [skill.to_dict() for skill in self.skills],
            "securitySchemes": list(self.security_schemes),
            "discoveryVisibility": str(self.discovery_visibility),
            "metadata": dict(self.metadata),
        }
        if self.documentation_url is not None:
            payload["documentationUrl"] = self.documentation_url
        return payload

    @classmethod
    def from_dict(cls, source: Mapping[str, Any]) -> AgentDescriptor:
        raw_visibility = source.get("discoveryVisibility")
        raw_capabilities = source.get("capabilities")
        if not isinstance(raw_capabilities, Mapping):
            raise DiscoveryErrors.invalid_descriptor("capabilities", "is required")

        return cls(
            agent_id=_read_str(source, "agentId"),
            route_key=_read_str(source, "routeKey"),
            display_name=_read_str(source, "displayName"),
            description=_read_str(source, "description"),
            version=_read_str(source, "version"),
            owner=_read_str(source, "owner"),
            created_at_utc=_parse_timestamp(_read_str(source, "createdAtUtc")),
            capabilities=AgentCapabilitySet.from_dict(raw_capabilities),
            documentation_url=_read_optional_str(source, "documentationUrl"),
            tags=_read_str_tuple(source, "tags"),
            skills=tuple(AgentSkill.from_dict(item) for item in _read_mappings(source, "skills")),
            security_schemes=_read_str_tuple(source, "securitySchemes"),
            discovery_visibility=(
                DiscoveryVisibility(str(raw_visibility)) if raw_visibility is not None else DiscoveryVisibility.LISTED
            ),
            metadata=dict(source.get("metadata") or {}),
        )

    def _validate_agent_id(self) -> None:
        _require_non_empty("agentId", self.agent_id)
        if len(self.agent_id) > AGENT_ID_MAX_LENGTH:
            raise DiscoveryErrors.invalid_descriptor(
                "agentId", f"must not exceed {AGENT_ID_MAX_LENGTH} characters"
            )
        if AGENT_ID_PATTERN.match(self.agent_id) is None:
            raise DiscoveryErrors.invalid_descriptor(
                "agentId",
                "must be safe for a path segment and a model field "
                "(letters, digits, dot, underscore, colon, hyphen)",
            )

    def _validate_skills(self) -> None:
        seen: set[str] = set()
        allowed_input = set(self.capabilities.input_modalities)
        allowed_output = set(self.capabilities.output_modalities)

        for skill in self.skills:
            if skill.skill_id in seen:
                raise DiscoveryErrors.invalid_descriptor(
                    "skills.skillId", f"'{skill.skill_id}' is declared more than once"
                )
            seen.add(skill.skill_id)

            if skill.input_modalities is not None and not set(skill.input_modalities) <= allowed_input:
                raise DiscoveryErrors.invalid_descriptor(
                    "skills.inputModalities",
                    f"of skill '{skill.skill_id}' must be a subset of the descriptor input modalities",
                )
            if skill.output_modalities is not None and not set(skill.output_modalities) <= allowed_output:
                raise DiscoveryErrors.invalid_descriptor(
                    "skills.outputModalities",
                    f"of skill '{skill.skill_id}' must be a subset of the descriptor output modalities",
                )


def _require_non_empty(field_name: str, value: str) -> None:
    if not value or not value.strip():
        raise DiscoveryErrors.invalid_descriptor(field_name, "must be a non-empty string")


def _read_str(source: Mapping[str, Any], key: str) -> str:
    value = source.get(key)
    if not isinstance(value, str):
        raise DiscoveryErrors.invalid_descriptor(key, "is required and must be a string")
    return value


def _read_optional_str(source: Mapping[str, Any], key: str) -> str | None:
    value = source.get(key)
    return value if isinstance(value, str) else None


def _read_optional_int(source: Mapping[str, Any], key: str) -> int | None:
    value = source.get(key)
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def _read_str_tuple(source: Mapping[str, Any], key: str) -> tuple[str, ...]:
    return _read_optional_str_tuple(source, key) or ()


def _read_optional_str_tuple(source: Mapping[str, Any], key: str) -> tuple[str, ...] | None:
    value = source.get(key)
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        return None
    return tuple(str(item) for item in value)


def _read_mappings(source: Mapping[str, Any], key: str) -> tuple[Mapping[str, Any], ...]:
    value = source.get(key)
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        return ()
    return tuple(item for item in value if isinstance(item, Mapping))


def _format_timestamp(value: datetime) -> str:
    normalized = value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)
    return normalized.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _parse_timestamp(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise DiscoveryErrors.invalid_descriptor("createdAtUtc", "must be an ISO-8601 date-time") from exc
    return parsed if parsed.tzinfo is not None else parsed.replace(tzinfo=timezone.utc)
