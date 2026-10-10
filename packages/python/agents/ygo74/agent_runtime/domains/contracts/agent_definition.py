"""Framework-neutral admission and factory context for the Python BYOA pilot."""

import re
from dataclasses import dataclass
from enum import StrEnum

from ygo74.agent_runtime.domains.auth.agent_principal import AgentPrincipal
from ygo74.agent_runtime.domains.discovery.agent_descriptor import AgentDescriptor
from ygo74.agent_runtime.domains.security.operations import (
    OperationType,
    RiskLevel,
    ToolOperationDescriptor,
)


class InputProfile(StrEnum):
    """Supported server-managed conversation input profiles."""

    LATEST_USER_TEXT = "latest_user_text"


@dataclass(frozen=True, slots=True)
class AgentFactoryContext:
    """Verified identity and operator partition supplied to a native factory.

    Args:
        principal: Caller established by authentication, not request contents.
        conversation_id: Caller-controlled handle within their identity partition.
        deployment_id: Operator-selected deployment identifier.
        identity_namespace: Operator-selected issuer/tenant namespace.
    """

    principal: AgentPrincipal
    conversation_id: str
    deployment_id: str
    identity_namespace: str


@dataclass(frozen=True, slots=True)
class AgentDefinition:
    """Trusted deployment definition reusing the canonical discovery descriptor.

    Args:
        descriptor: Existing identity/version/description/capability contract.
        factory: Trusted module:export, never selected from incoming requests.
        require_email: Require an authenticated email for agents such as Mail.
        input_profile: Supported input behavior; other profiles are not admitted.
        tools: Native tool security declarations, not permissions.
        control_point: Admission identifier for an operator-verified deterministic gate.
    """

    descriptor: AgentDescriptor
    factory: str
    require_email: bool = False
    input_profile: InputProfile = InputProfile.LATEST_USER_TEXT
    tools: tuple[ToolOperationDescriptor, ...] = ()
    control_point: str | None = None

    def __post_init__(self) -> None:
        """Reject invalid exports, unsupported capabilities and unenforceable tools."""
        if not re.fullmatch(r"[A-Za-z_]\w*(?:\.[A-Za-z_]\w*)*:[A-Za-z_]\w*", self.factory):
            raise ValueError("factory must be a trusted module:export")
        if not isinstance(self.input_profile, InputProfile):
            raise TypeError("unsupported input profile")
        if len({tool.tool_name for tool in self.tools}) != len(self.tools):
            raise ValueError("tool declarations must be unique")
        for tool in self.tools:
            if not re.fullmatch(r"[A-Za-z0-9_.-]+", tool.tool_name):
                raise ValueError("tool name must be a safe identifier")
            if (tool.operation_type is OperationType.WRITE and tool.risk_level is RiskLevel.HIGH
                    and not tool.confirmation_required_by_default):
                raise ValueError("high-impact WRITE tools require confirmation")
        if self.tools and not self.control_point:
            raise ValueError("native tools require an enforceable control point")
        capabilities = self.descriptor.capabilities
        if capabilities.input_modalities != ("text",) or capabilities.structured_output:
            raise ValueError("unsupported native input or structured-output capability")
        if capabilities.tool_invocation != bool(self.tools):
            raise ValueError("native tool capability must match the declared tools")
