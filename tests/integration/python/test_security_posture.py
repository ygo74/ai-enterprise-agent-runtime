"""Tests of the security posture model.

The properties asserted here are the ones the model exists for: a caller without
a permission is refused rather than served, and a configuration may not declare
less protection than the code requires.
"""

from __future__ import annotations

import pytest
from ygo74.agent_runtime.domains.security.audit import (
    AuditOutcome,
    AuditRecord,
    AuditTrail,
    InMemoryAuditTrail,
    LoggingAuditTrail,
)
from ygo74.agent_runtime.domains.security.floor import (
    OperationFloor,
    SecurityFloor,
    SecurityFloorViolationError,
)
from ygo74.agent_runtime.domains.security.operations import (
    OperationType,
    RiskLevel,
    ToolOperationDescriptor,
)
from ygo74.agent_runtime.domains.security.permissions import Permission
from ygo74.agent_runtime.domains.security.security_errors import PermissionDeniedError
from ygo74.agent_runtime.domains.security.user_context import UserContext

SEND = Permission("mail", "send")
READ = Permission("mail", "read")


def _descriptor(
    *,
    tool_name: str = "send_mail",
    operation_type: OperationType = OperationType.WRITE,
    risk_level: RiskLevel = RiskLevel.HIGH,
    confirmation_required_by_default: bool = True,
) -> ToolOperationDescriptor:
    return ToolOperationDescriptor(
        tool_name=tool_name,
        operation_type=operation_type,
        risk_level=risk_level,
        required_permission=SEND,
        confirmation_required_by_default=confirmation_required_by_default,
    )


def test_user_context_grants_a_held_permission() -> None:
    user = UserContext(user_id="alice", session_id="s-1", permissions=frozenset({SEND}))

    assert user.has_permission(SEND)
    user.require_permission(SEND)


def test_user_context_refuses_a_permission_it_does_not_hold() -> None:
    user = UserContext(user_id="alice", session_id="s-1", permissions=frozenset({READ}))

    with pytest.raises(PermissionDeniedError) as refusal:
        user.require_permission(SEND)

    assert refusal.value.user_id == "alice"
    assert refusal.value.required_permission == "mail:send"


def test_user_context_is_immutable() -> None:
    user = UserContext(user_id="alice", session_id="s-1")

    with pytest.raises(ValueError, match="frozen"):
        user.user_id = "bob"  # type: ignore[misc]


def test_a_write_descriptor_says_so() -> None:
    assert _descriptor().is_write
    assert not _descriptor(operation_type=OperationType.READ).is_write


def test_a_floor_accepts_a_configuration_at_or_above_it() -> None:
    floor = SecurityFloor([OperationFloor("send_mail", RiskLevel.HIGH)])

    floor.enforce(_descriptor())


def test_a_floor_refuses_a_risk_level_below_it() -> None:
    floor = SecurityFloor([OperationFloor("send_mail", RiskLevel.HIGH)])

    with pytest.raises(SecurityFloorViolationError, match="below the required HIGH"):
        floor.enforce(_descriptor(risk_level=RiskLevel.LOW))


def test_a_floor_refuses_a_disarmed_confirmation() -> None:
    floor = SecurityFloor([OperationFloor("send_mail", RiskLevel.LOW)])

    with pytest.raises(SecurityFloorViolationError, match="always requires a confirmation"):
        floor.enforce(_descriptor(risk_level=RiskLevel.LOW, confirmation_required_by_default=False))


def test_a_floor_ignores_an_operation_it_does_not_cover() -> None:
    floor = SecurityFloor([OperationFloor("send_mail", RiskLevel.HIGH)])

    floor.enforce(_descriptor(tool_name="search_mail", risk_level=RiskLevel.LOW))


def test_a_mandatory_confirmation_is_reported_independently_of_risk() -> None:
    floor = SecurityFloor([OperationFloor("send_mail", RiskLevel.LOW)])

    assert floor.confirmation_is_mandatory("send_mail")
    assert not floor.confirmation_is_mandatory("search_mail")


def test_an_audit_trail_keeps_what_it_is_given() -> None:
    trail = InMemoryAuditTrail()

    trail.record(
        AuditRecord(
            tool_name="send_mail",
            operation_type=OperationType.WRITE,
            risk_level=RiskLevel.HIGH,
            outcome=AuditOutcome.EXECUTED,
            user_id="alice",
            session_id="s-1",
        )
    )

    assert len(trail.records) == 1
    assert trail.records_for("send_mail")[0].outcome is AuditOutcome.EXECUTED
    assert trail.records_for("search_mail") == ()


def test_the_logging_trail_forwards_to_its_delegate() -> None:
    captured = InMemoryAuditTrail()
    trail: AuditTrail = LoggingAuditTrail(captured)

    trail.record(
        AuditRecord(
            tool_name="send_mail",
            operation_type=OperationType.WRITE,
            risk_level=RiskLevel.HIGH,
            outcome=AuditOutcome.DECLINED,
            user_id="alice",
            session_id="s-1",
        )
    )

    assert captured.records[0].outcome is AuditOutcome.DECLINED


def test_an_audit_record_is_timezone_aware() -> None:
    record = AuditRecord(
        tool_name="send_mail",
        operation_type=OperationType.WRITE,
        risk_level=RiskLevel.HIGH,
        outcome=AuditOutcome.FAILED,
        user_id="alice",
        session_id="s-1",
    )

    assert record.occurred_at.tzinfo is not None
