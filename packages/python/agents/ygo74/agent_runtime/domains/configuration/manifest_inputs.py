"""Typed YAML input contracts for agent and skill manifests."""

from __future__ import annotations

from typing import Annotated

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StrictBool,
    StrictStr,
    StringConstraints,
)
from ygo74.agent_runtime.domains.security.operations import OperationType, RiskLevel

ManifestText = Annotated[StrictStr, StringConstraints(strip_whitespace=True, min_length=1, pattern=r"\S")]


class OperationManifestInput(BaseModel):
    """The fixed YAML shape of a skill's operation declaration."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    type: OperationType
    risk: RiskLevel
    permission: ManifestText
    confirmation_required: StrictBool


class SkillManifestInput(BaseModel):
    """The fixed YAML fields accepted for one skill package."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    tool_name: ManifestText
    implementation: ManifestText
    description: ManifestText
    operation: OperationManifestInput
    mcp_tools: tuple[ManifestText, ...] = ()


class AgentManifestInput(BaseModel):
    """The fixed YAML fields accepted for one agent."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    name: ManifestText
    description: ManifestText
    skills: tuple[ManifestText, ...] = Field(min_length=1)
