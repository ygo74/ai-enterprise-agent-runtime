"""Running an operation that changes external state, under the approval policy.

Reading is harmless; writing is not. Everything a state-changing operation shares
- permission check, confirmation policy, audit record - lives here so that no
capability can forget a step, and so that adding a new one cannot introduce a
different, weaker path.

That argument is usually made inside one agent. It holds one level up as well,
and more strongly: two agents each carrying their own copy of this runner are one
copy away from one of them being weaker, and the divergence would be invisible
because both would still pass their own tests.

The runner is generic over whatever an application uses to name its tools - a
``StrEnum``, a string, anything hashable - because the name is only ever handed
straight back to the catalogue. What the runner actually consults is the
:class:`ToolOperationDescriptor` the catalogue returns, and that is shared.

Four outcomes reach the audit trail, and the distinction between them is the
point of writing one at all:

``BLOCKED``
    the caller lacked the permission, or no approval was supplied for a gated
    operation;
``DECLINED``
    a person was asked and said no;
``FAILED``
    the operation ran and raised;
``EXECUTED``
    it ran and returned.
"""

from __future__ import annotations

import logging
import uuid
from collections.abc import Awaitable, Callable, Sequence
from typing import Generic, Protocol, TypeVar

from ygo74.agent_runtime.domains.humanapproval.approval_errors import (
    ConfirmationRejectedError,
)
from ygo74.agent_runtime.domains.humanapproval.confirmation import (
    ConfirmationDecision,
    ConfirmationDetail,
    ConfirmationGate,
    ConfirmationPolicy,
    ConfirmationRequest,
)
from ygo74.agent_runtime.domains.security.audit import (
    AuditOutcome,
    AuditRecord,
    AuditTrail,
)
from ygo74.agent_runtime.domains.security.operations import ToolOperationDescriptor
from ygo74.agent_runtime.domains.security.security_errors import SecurityError
from ygo74.agent_runtime.domains.security.user_context import UserContext

ToolT = TypeVar("ToolT")
ResultT = TypeVar("ResultT")

_logger = logging.getLogger(__name__)


class OperationCatalogue(Protocol[ToolT]):
    """Where the security posture of an operation is read from.

    There must be exactly one answer per deployment. A framework decides whether
    to suspend a call, and the capability decides whether to run it; if those two
    consulted different sources, an operation could be one the framework never
    asks about and the capability always refuses. It would then be impossible to
    perform, and the model would report that the system had refused.
    """

    def descriptor(self, name: ToolT) -> ToolOperationDescriptor:
        """Return the security metadata of a tool."""
        ...


class GatedOperationRunner(Generic[ToolT]):
    """Authorises, runs and audits one state-changing operation.

    Args:
        operations: Where the posture of each tool is read from. The same source
            a framework adapter reads, never a second one.
        policy: Decides whether an operation needs an explicit human approval.
        gate: Enforces that decision again at the point of execution, so the
            guarantee survives being called from a script or another framework.
        audit: Where the outcome is recorded, whatever it was.
    """

    def __init__(
        self,
        operations: OperationCatalogue[ToolT],
        policy: ConfirmationPolicy,
        gate: ConfirmationGate,
        audit: AuditTrail,
    ) -> None:
        _logger.info("Initializing gated operation runner")
        _logger.debug(
            "GatedOperationRunner.__init__ arguments: operations_type=%s, policy_type=%s, "
            "gate_type=%s, audit_type=%s",
            type(operations).__name__,
            type(policy).__name__,
            type(gate).__name__,
            type(audit).__name__,
        )
        self._operations = operations
        self._policy = policy
        self._gate = gate
        self._audit = audit

    def requires_confirmation(self, tool: ToolT, user: UserContext) -> bool:
        """Whether the caller must approve this operation before it runs."""
        _logger.debug(
            "GatedOperationRunner.requires_confirmation arguments: tool=%s, user_id=%s",
            tool,
            user.user_id,
        )
        return self._policy.requires_confirmation(self._operations.descriptor(tool), user)

    def build_confirmation_request(
        self,
        tool: ToolT,
        user: UserContext,
        title: str,
        *,
        target: str = "",
        details: Sequence[ConfirmationDetail] = (),
    ) -> ConfirmationRequest:
        """Build the request shown to the caller before they decide."""
        _logger.debug(
            "GatedOperationRunner.build_confirmation_request arguments: tool=%s, user_id=%s, "
            "title_length=%d, target=%s, details=%d",
            tool,
            user.user_id,
            len(title),
            target,
            len(details),
        )
        return ConfirmationRequest(
            request_id=f"cfm-{uuid.uuid4().hex[:12]}",
            operation=self._operations.descriptor(tool),
            requested_for=user.user_id,
            title=title,
            target=target,
            details=tuple(details),
        )

    async def execute(
        self,
        tool: ToolT,
        user: UserContext,
        operation: Callable[[], Awaitable[ResultT]],
        *,
        target_id: str | None = None,
        request: ConfirmationRequest | None = None,
        decision: ConfirmationDecision | None = None,
    ) -> ResultT:
        """Authorise, run and audit one state-changing operation."""
        _logger.info("Executing gated operation")
        _logger.debug(
            "GatedOperationRunner.execute arguments: tool=%s, user_id=%s, session_id=%s, "
            "target_id=%s, request_id=%s, decision_present=%s",
            tool,
            user.user_id,
            user.session_id,
            target_id,
            None if request is None else request.request_id,
            decision is not None,
        )
        descriptor = self._operations.descriptor(tool)
        try:
            self._gate.ensure_approved(descriptor, user, request, decision)
        except SecurityError as error:
            # A refusal by the person and a refusal by the policy are different
            # events, and an audit trail that conflated them would not answer the
            # one question it is read for: did somebody say no, or was nobody
            # ever asked?
            outcome = AuditOutcome.DECLINED if isinstance(error, ConfirmationRejectedError) else AuditOutcome.BLOCKED
            self._write(descriptor, user, outcome, target_id, request, error)
            raise

        try:
            result = await operation()
        except Exception as error:
            self._write(descriptor, user, AuditOutcome.FAILED, target_id, request, error)
            raise

        self._write(descriptor, user, AuditOutcome.EXECUTED, target_id, request, None)
        return result

    def _write(
        self,
        descriptor: ToolOperationDescriptor,
        user: UserContext,
        outcome: AuditOutcome,
        target_id: str | None,
        request: ConfirmationRequest | None,
        error: Exception | None,
    ) -> None:
        """Append one record to the audit trail.

        Only the type of an error is recorded, never its message: a message can
        carry the very content the audit trail is written to stay clear of.
        """
        _logger.debug(
            "GatedOperationRunner._write arguments: tool_name=%s, user_id=%s, session_id=%s, "
            "outcome=%s, target_id=%s, request_id=%s, error_type=%s",
            descriptor.tool_name,
            user.user_id,
            user.session_id,
            outcome.value,
            target_id,
            None if request is None else request.request_id,
            None if error is None else type(error).__name__,
        )
        self._audit.record(
            AuditRecord(
                tool_name=descriptor.tool_name,
                operation_type=descriptor.operation_type,
                risk_level=descriptor.risk_level,
                outcome=outcome,
                user_id=user.user_id,
                session_id=user.session_id,
                target_id=target_id,
                confirmation_request_id=None if request is None else request.request_id,
                error_type=None if error is None else type(error).__name__,
            )
        )
