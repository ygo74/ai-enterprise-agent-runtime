"""Running the operation a claimed ticket describes, and nothing else.

An OpenAI-compatible API answers every request, so a turn cannot hold while a
person decides. The turn therefore ends having changed nothing: each suspended
call is declined *to the framework* and kept as a ticket, and the reply says what
is waiting.

The answer arrives in a later request as plain text. It is read by a literal
parser before the model sees it, the ticket is claimed, and the capability is
re-invoked from the arguments stored in that ticket. This is the property worth
stating twice: the model describes the operation, then plays no part in running
it. It cannot alter the arguments between the two, because they never come back
through it.

Nothing here names an agentic framework. Which calls get suspended is a framework
concern and lives in each agent's resolver; what happens once a person answers is
the same question whatever suspended the call, so it is answered once.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Protocol, runtime_checkable

from ygo74.agent_runtime.domains.contracts.capability_registry import (
    ResultRenderer,
    SkillRegistry,
)
from ygo74.agent_runtime.domains.humanapproval.commands import ConfirmationCommand
from ygo74.agent_runtime.domains.humanapproval.confirmation import (
    ConfirmationDecision,
    ConfirmationLedger,
    ConfirmationOutcome,
    ConfirmationRequest,
)
from ygo74.agent_runtime.domains.humanapproval.tickets import (
    ConfirmationTicket,
    PendingConfirmationStore,
)
from ygo74.agent_runtime.domains.security.user_context import UserContext


@runtime_checkable
class ConfirmationPresenter(Protocol):
    """Turns a suspended tool call into something a human can judge.

    The arguments a model proposes are rarely enough for an informed decision: a
    draft reference says nothing about what would be published, and an
    identifier says nothing about which thing is about to disappear. An
    implementation resolves them into the very request that will authorise the
    operation, so what the person reads is what gets enforced and audited.
    """
    async def present(
        self,
        tool_name: str,
        arguments: Mapping[str, Any],
        user: UserContext,
    ) -> ConfirmationRequest:
        """Build the confirmation request shown for a suspended tool call.

        Raises:
            DomainError: the capability cannot be described. Failing is
                deliberate - approving an operation nobody can explain would be
                worse than interrupting the conversation.

        Args:
            tool_name (str): Name of the tool whose declaration or invocation is being resolved.
            arguments (Mapping[str, Any]): JSON arguments associated with a tool call.
            user (UserContext): The authenticated user whose identity or permissions govern this operation.
        """
        ...


class ConfirmedOperationRunner:
    """Runs the operation a claimed ticket describes, and nothing else.

    Args:
        registry (SkillRegistry): The registry that supplies entries for this operation.
        store (PendingConfirmationStore): Persistence service used to retain state across requests.
        ledger (ConfirmationLedger): Approval ledger used to persist confirmation state.
        renderer (ResultRenderer): Component that formats approval state for the user.
        user (UserContext): The authenticated user whose identity or permissions govern this operation.
        conversation_id (str): Conversation identity used to select session state for this caller.
    """
    def __init__(
        self,
        registry: SkillRegistry,
        store: PendingConfirmationStore,
        ledger: ConfirmationLedger,
        renderer: ResultRenderer,
        user: UserContext,
        *,
        conversation_id: str,
    ) -> None:
        """Initialize the instance runtime data with supplied collaborators and configuration.

        Args:
            registry (SkillRegistry): The registry that supplies entries for this operation.
            store (PendingConfirmationStore): Persistence service used to retain state across requests.
            ledger (ConfirmationLedger): Approval ledger used to persist confirmation state.
            renderer (ResultRenderer): Component that formats approval state for the user.
            user (UserContext): The authenticated user whose identity or permissions govern this operation.
            conversation_id (str): Conversation identity used to select session state for this caller.
        """
        self._registry = registry
        self._store = store
        self._ledger = ledger
        self._renderer = renderer
        self._user = user
        self._conversation_id = conversation_id

    async def run(self, command: ConfirmationCommand) -> str:
        """Claim the ticket the command names, then honour the answer.

        Claiming first is deliberate: a refusal must consume the ticket too, so
        a declined operation cannot be confirmed a moment later by repeating the
        identifier.

        Args:
            command (ConfirmationCommand): Requested operation that must pass the authorization gate.
        """
        ticket = self._store.claim(
            command.ticket_id,
            subject=self._user.user_id,
            conversation_id=self._conversation_id,
        )
        if not command.approves:
            return f"Cancelled {ticket.tool_name}. Nothing was changed."

        self._record(ticket)
        descriptor = self._registry.skill(ticket.tool_name)
        payload = descriptor.input_model.model_validate(dict(ticket.arguments))
        return self._renderer.render(await descriptor.invoke(payload, self._user))

    def _record(self, ticket: ConfirmationTicket) -> None:
        """Store the decision so the domain gate enforces this very request.

        Args:
            ticket (ConfirmationTicket): Pending approval record being confirmed, declined, or expired.
        """
        self._ledger.record(
            ConfirmationOutcome(
                request=ticket.request,
                decision=ConfirmationDecision(
                    request_id=ticket.request.request_id,
                    approved=True,
                    decided_by=self._user.user_id,
                ),
            ),
            self._user,
        )
