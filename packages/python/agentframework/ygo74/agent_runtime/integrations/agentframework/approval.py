"""Optional MAF approval-to-ticket bridge; domain gates remain injected."""

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Protocol

from agent_framework import AgentResponse, Content, Message
from ygo74.agent_runtime.domains.errors import DomainError
from ygo74.agent_runtime.domains.humanapproval.confirmation import (
    ConfirmationDecision,
    ConfirmationRequest,
)
from ygo74.agent_runtime.domains.humanapproval.confirmed_operations import (
    ConfirmationPresenter,
)
from ygo74.agent_runtime.domains.humanapproval.tickets import (
    ConfirmationTicket,
    PendingConfirmationStore,
)
from ygo74.agent_runtime.domains.security.security_errors import SecurityError
from ygo74.agent_runtime.domains.security.user_context import UserContext

APPROVAL_REQUEST_TYPE = "function_approval_request"


class PendingToolApproval:
    """A suspended native call with exact proposed arguments.

    Args:
        content: MAF function approval request; malformed arguments are rejected.
    """

    def __init__(self, content: Content) -> None:
        """Retain the request.

        Args:
            content: Native request to answer.
        """
        self._content = content

    @property
    def content(self) -> Content:
        """Return the original native request."""
        return self._content

    @property
    def tool_name(self) -> str:
        """Return the requested native tool name."""
        call = self._content.function_call
        return "" if call is None else call.name or ""

    @property
    def arguments(self) -> Mapping[str, Any]:
        """Decode exact wire arguments, refusing malformed JSON rather than guessing."""
        call = self._content.function_call
        raw = None if call is None else call.arguments
        if raw is None:
            return {}
        decoded = json.loads(raw) if isinstance(raw, str) else raw
        if not isinstance(decoded, Mapping):
            raise TypeError("approval arguments must be a JSON object")
        return dict(decoded)

    def answer(self, *, approved: bool) -> Content:
        """Answer this specific request.

        Args:
            approved: Deterministic resolver decision, never inferred from text.
        """
        return self._content.to_function_approval_response(approved=approved)


class MafApprovalTranslator:
    """Translate native approval state without interpreting authorization."""

    def pending_approvals(self, response: AgentResponse[Any]) -> tuple[PendingToolApproval, ...]:
        """Read suspended calls.

        Args:
            response: Completed native sub-run.
        """
        return tuple(PendingToolApproval(item) for item in response.user_input_requests
                     if item.type == APPROVAL_REQUEST_TYPE)

    def answer_message(self, answers: Sequence[Content]) -> Message:
        """Produce MAF's complete batch response.

        Args:
            answers: One native answer per suspended request.
        """
        return Message(role="user", contents=list(answers))

    def decision_for(self, request: ConfirmationRequest, user: UserContext, *, approved: bool) -> ConfirmationDecision:
        """Produce the corresponding deterministic domain decision.

        Args:
            request: Domain confirmation being answered.
            user: Acting user supplied by the host.
            approved: Explicit decision.
        """
        return ConfirmationDecision(request_id=request.request_id, approved=approved, decided_by=user.user_id)


@dataclass(frozen=True, slots=True)
class ApprovalRound:
    """Answers for a complete native batch.

    Args:
        answers: Native responses in request order.
        questioned_user: Whether a person was actually prompted.
    """

    answers: tuple[Content, ...]
    questioned_user: bool


class ApprovalResolver(Protocol):
    """Optional domain or console resolver; not required for simple agents."""

    def will_question(self, pending: Sequence[PendingToolApproval]) -> bool:
        """Classify a batch before charging the prompt budget.

        Args:
            pending: Suspended calls.
        """
        ...

    async def resolve(self, pending: Sequence[PendingToolApproval]) -> ApprovalRound:
        """Resolve every suspended call using deterministic policy.

        Args:
            pending: Suspended calls.
        """
        ...


class TicketApprovalResolver:
    """Decline native execution and retain tickets for later explicit commands.

    Args:
        presenter: Domain-owned authorization and confirmation description.
        store: Conversation-scoped ticket storage.
        user: Explicit acting identity.
        conversation_id: Ticket partition within the identity.
    """

    def __init__(self, presenter: ConfirmationPresenter, store: PendingConfirmationStore,
                 user: UserContext, *, conversation_id: str) -> None:
        """Retain injected domain collaborators.

        Args:
            presenter: Domain-owned authorization and description.
            store: Ticket persistence.
            user: Explicit identity.
            conversation_id: Ticket partition.
        """
        self._presenter, self._store, self._user = presenter, store, user
        self._conversation_id = conversation_id

    def will_question(self, pending: Sequence[PendingToolApproval]) -> bool:
        """Never block the HTTP turn for a human.

        Args:
            pending: Calls to defer.
        """
        return False

    async def resolve(self, pending: Sequence[PendingToolApproval]) -> ApprovalRound:
        """Store readable, authorized tickets and decline all calls to MAF.

        Args:
            pending: Complete suspended batch.
        """
        for approval in pending:
            await self._raise_ticket(approval)
        return ApprovalRound(tuple(approval.answer(approved=False) for approval in pending), False)

    async def _raise_ticket(self, approval: PendingToolApproval) -> None:
        """Only offer confirmations passing the injected domain presenter.

        Args:
            approval: Suspended call whose exact arguments must be preserved.
        """
        try:
            arguments = approval.arguments
            request = await self._presenter.present(approval.tool_name, arguments, self._user)
        except (DomainError, SecurityError, ValueError, TypeError):
            return
        self._store.issue(ConfirmationTicket.issue(
            subject=self._user.user_id, conversation_id=self._conversation_id,
            tool_name=approval.tool_name, request=request, arguments=arguments,
        ))
