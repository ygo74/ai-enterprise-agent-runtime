"""Security posture a configuration may not go below.

Descriptions, prompts and confirmation defaults are configuration. The fact that
delivering an e-mail is irreversible is not: it is a property of the operation
itself, and it stays in code.

A configuration that would weaken such an operation is refused at load time
rather than silently corrected. A security control that repairs itself in
silence teaches nobody that the configuration was wrong.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from ygo74.agent_runtime.domains.security.operations import (
    RiskLevel,
    ToolOperationDescriptor,
)
from ygo74.agent_runtime.domains.security.security_errors import SecurityError

_SEVERITY = {RiskLevel.LOW: 0, RiskLevel.MEDIUM: 1, RiskLevel.HIGH: 2}


class SecurityFloorViolationError(SecurityError):
    """Raised when a configuration declares less protection than the code requires.

    Args:
        tool_name (str): Name of the tool whose declaration or invocation is being resolved.
        reason (str): Reason code or message associated with this decision or failure.
    """
    def __init__(self, tool_name: str, reason: str) -> None:
        """Initialize the instance runtime data with supplied collaborators and configuration.

        Args:
            tool_name (str): Name of the tool whose declaration or invocation is being resolved.
            reason (str): Reason code or message associated with this decision or failure.
        """
        super().__init__(f"configuration of {tool_name!r} is refused: {reason}")
        self.tool_name = tool_name


@dataclass(frozen=True, slots=True)
class OperationFloor:
    """The weakest posture an operation is allowed to be configured with.

    Args:
        tool_name (str): Name of the tool whose declaration or invocation is being resolved.
        minimum_risk (RiskLevel): Risk threshold above which approval is required.
        confirmation_always_required (bool): Whether this operation always requires explicit confirmation.
    """
    tool_name: str
    minimum_risk: RiskLevel
    confirmation_always_required: bool = True


class SecurityFloor:
    """Checks declared operations against the floors the code imposes.

    Args:
        floors (Iterable[OperationFloor]): Operation-specific authorization floors evaluated by the policy.
    """
    def __init__(self, floors: Iterable[OperationFloor]) -> None:
        """Initialize the instance runtime data with supplied collaborators and configuration.

        Args:
            floors (Iterable[OperationFloor]): Operation-specific authorization floors evaluated by the policy.
        """
        self._by_tool = {floor.tool_name: floor for floor in floors}

    def confirmation_is_mandatory(self, tool_name: str) -> bool:
        """Whether no configuration may remove the confirmation of an operation.

        This is the single answer to "may a deployment, or a person, decide
        otherwise". Asking the risk level instead would conflate how much an
        operation costs with who is allowed to choose.

        Args:
            tool_name (str): Name of the tool whose declaration or invocation is being resolved.
        """
        floor = self._by_tool.get(tool_name)
        return floor is not None and floor.confirmation_always_required

    def enforce(self, descriptor: ToolOperationDescriptor) -> None:
        """Refuse a descriptor that sits below the floor of its operation.

        Args:
            descriptor (ToolOperationDescriptor): The canonical agent descriptor whose identity and capabilities are used.
        """
        floor = self._by_tool.get(descriptor.tool_name)
        if floor is None:
            return
        self._check_risk(descriptor, floor)
        self._check_confirmation(descriptor, floor)

    @staticmethod
    def _check_risk(descriptor: ToolOperationDescriptor, floor: OperationFloor) -> None:
        """Refuse a risk level lower than the floor.

        Args:
            descriptor (ToolOperationDescriptor): The canonical agent descriptor whose identity and capabilities are used.
            floor (OperationFloor): Configured approval or authorization threshold for the operation.
        """
        if _SEVERITY[descriptor.risk_level] >= _SEVERITY[floor.minimum_risk]:
            return
        raise SecurityFloorViolationError(
            descriptor.tool_name,
            f"risk {descriptor.risk_level.value} is below the required {floor.minimum_risk.value}",
        )

    @staticmethod
    def _check_confirmation(descriptor: ToolOperationDescriptor, floor: OperationFloor) -> None:
        """Refuse a configuration disarming a mandatory confirmation.

        Args:
            descriptor (ToolOperationDescriptor): The canonical agent descriptor whose identity and capabilities are used.
            floor (OperationFloor): Configured approval or authorization threshold for the operation.
        """
        if not floor.confirmation_always_required or descriptor.confirmation_required_by_default:
            return
        raise SecurityFloorViolationError(
            descriptor.tool_name,
            "this operation always requires a confirmation",
        )
