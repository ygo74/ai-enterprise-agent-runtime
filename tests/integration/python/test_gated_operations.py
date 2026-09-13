"""Tests of the runner that guards every state-changing operation.

What matters here is that the four outcomes are distinguishable and that none of
them is silent. An audit trail that recorded only successes would answer none of
the questions it is read for, and one that conflated "nobody was asked" with
"somebody said no" would answer the most important one wrongly.
"""

from __future__ import annotations

import asyncio
from enum import StrEnum

import pytest

from ygo74.agent_runtime.domains.humanapproval.approval_errors import (
    ConfirmationRejectedError,
    ConfirmationRequiredError,
)
from ygo74.agent_runtime.domains.humanapproval.confirmation import (
    ConfiguredConfirmationPolicy,
    ConfirmationDecision,
    ConfirmationDetail,
    ConfirmationGate,
    ConfirmationPreferences,
    InMemoryConfirmationPreferenceStore,
)
from ygo74.agent_runtime.domains.humanapproval.gated_operations import (
    GatedOperationRunner,
    OperationCatalogue,
)
from ygo74.agent_runtime.domains.security.audit import AuditOutcome, InMemoryAuditTrail
from ygo74.agent_runtime.domains.security.floor import SecurityFloor
from ygo74.agent_runtime.domains.security.operations import (
    OperationType,
    RiskLevel,
    ToolOperationDescriptor,
)
from ygo74.agent_runtime.domains.security.permissions import Permission
from ygo74.agent_runtime.domains.security.security_errors import PermissionDeniedError
from ygo74.agent_runtime.domains.security.user_context import UserContext

SEND = Permission("mail", "send")
SEARCH = Permission("mail", "read")


class Tool(StrEnum):
    """An application's own tool names - the runner never interprets them."""

    SEND = "send_mail"
    SEARCH = "search_mail"


class Catalogue:
    """The single source of posture this deployment reads."""

    def descriptor(self, name: Tool) -> ToolOperationDescriptor:
        if name is Tool.SEND:
            return ToolOperationDescriptor(
                tool_name=Tool.SEND.value,
                operation_type=OperationType.WRITE,
                risk_level=RiskLevel.HIGH,
                required_permission=SEND,
                confirmation_required_by_default=True,
            )
        return ToolOperationDescriptor(
            tool_name=Tool.SEARCH.value,
            operation_type=OperationType.READ,
            risk_level=RiskLevel.LOW,
            required_permission=SEARCH,
            confirmation_required_by_default=False,
        )


ADA = UserContext(user_id="ada", session_id="conv-1", permissions=frozenset({SEND, SEARCH}))
READER = UserContext(user_id="ada", session_id="conv-1", permissions=frozenset({SEARCH}))


def _build(
    *, preferences: ConfirmationPreferences | None = None
) -> tuple[GatedOperationRunner[Tool], InMemoryAuditTrail]:
    store = InMemoryConfirmationPreferenceStore({"ada": preferences} if preferences else None)
    policy = ConfiguredConfirmationPolicy(store, SecurityFloor(()))
    audit = InMemoryAuditTrail()
    catalogue: OperationCatalogue[Tool] = Catalogue()
    return GatedOperationRunner(catalogue, policy, ConfirmationGate(policy), audit), audit


async def _succeeds() -> str:
    return "done"


async def _raises() -> str:
    raise RuntimeError("the downstream system refused")


def test_a_caller_without_the_permission_is_blocked_and_recorded() -> None:
    runner, audit = _build()

    with pytest.raises(PermissionDeniedError):
        asyncio.run(runner.execute(Tool.SEND, READER, _succeeds))

    assert [record.outcome for record in audit.records] == [AuditOutcome.BLOCKED]
    assert audit.records[0].error_type == "PermissionDeniedError"


def test_a_gated_operation_without_an_answer_is_blocked_and_recorded() -> None:
    runner, audit = _build()

    with pytest.raises(ConfirmationRequiredError):
        asyncio.run(runner.execute(Tool.SEND, ADA, _succeeds))

    assert [record.outcome for record in audit.records] == [AuditOutcome.BLOCKED]


def test_a_refusal_by_the_person_is_recorded_as_a_refusal() -> None:
    """Distinguished from BLOCKED: somebody was asked, and said no."""
    runner, audit = _build()
    request = runner.build_confirmation_request(Tool.SEND, ADA, "Send it")
    decision = ConfirmationDecision(request_id=request.request_id, approved=False, decided_by="ada")

    with pytest.raises(ConfirmationRejectedError):
        asyncio.run(runner.execute(Tool.SEND, ADA, _succeeds, request=request, decision=decision))

    assert [record.outcome for record in audit.records] == [AuditOutcome.DECLINED]


def test_an_approved_operation_runs_and_is_recorded() -> None:
    runner, audit = _build()
    request = runner.build_confirmation_request(Tool.SEND, ADA, "Send it", target="msg-1")
    decision = ConfirmationDecision(request_id=request.request_id, approved=True, decided_by="ada")

    result = asyncio.run(
        runner.execute(Tool.SEND, ADA, _succeeds, target_id="msg-1", request=request, decision=decision)
    )

    assert result == "done"
    record = audit.records[0]
    assert record.outcome is AuditOutcome.EXECUTED
    assert record.target_id == "msg-1"
    assert record.confirmation_request_id == request.request_id


def test_an_operation_that_raises_is_recorded_as_a_failure_and_re_raised() -> None:
    """A failure must not be reported to the model as a success."""
    runner, audit = _build()
    request = runner.build_confirmation_request(Tool.SEND, ADA, "Send it")
    decision = ConfirmationDecision(request_id=request.request_id, approved=True, decided_by="ada")

    with pytest.raises(RuntimeError):
        asyncio.run(runner.execute(Tool.SEND, ADA, _raises, request=request, decision=decision))

    assert [record.outcome for record in audit.records] == [AuditOutcome.FAILED]
    assert audit.records[0].error_type == "RuntimeError"


def test_an_ungated_operation_needs_no_answer() -> None:
    runner, audit = _build()

    assert asyncio.run(runner.execute(Tool.SEARCH, ADA, _succeeds)) == "done"
    assert [record.outcome for record in audit.records] == [AuditOutcome.EXECUTED]


def test_the_runner_reports_what_the_policy_decided() -> None:
    runner, _ = _build()

    assert runner.requires_confirmation(Tool.SEND, ADA)
    assert not runner.requires_confirmation(Tool.SEARCH, ADA)


def test_a_pre_approval_removes_the_confirmation() -> None:
    runner, _ = _build(preferences=ConfirmationPreferences(auto_approved_tools=frozenset({Tool.SEND.value})))

    assert not runner.requires_confirmation(Tool.SEND, ADA)
    assert asyncio.run(runner.execute(Tool.SEND, ADA, _succeeds)) == "done"


def test_a_built_request_carries_the_posture_and_the_caller() -> None:
    runner, _ = _build()

    request = runner.build_confirmation_request(
        Tool.SEND,
        ADA,
        "Send to the board",
        target="msg-1",
        details=(ConfirmationDetail(label="To", value="board@example.com"),),
    )

    assert request.operation.tool_name == Tool.SEND.value
    assert request.requested_for == "ada"
    assert request.target == "msg-1"
    assert request.details[0].value == "board@example.com"
    assert request.request_id.startswith("cfm-")


def test_an_audit_record_carries_no_message_of_its_own() -> None:
    """Only the type of an error: a message can carry the content itself."""
    runner, audit = _build()
    request = runner.build_confirmation_request(Tool.SEND, ADA, "Send it")
    decision = ConfirmationDecision(request_id=request.request_id, approved=True, decided_by="ada")

    with pytest.raises(RuntimeError):
        asyncio.run(runner.execute(Tool.SEND, ADA, _raises, request=request, decision=decision))

    serialised = audit.records[0].model_dump_json()
    assert "the downstream system refused" not in serialised
