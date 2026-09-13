"""Confirmation authority for a framework that collects approvals up front.

Agentic frameworks typically suspend a gated tool call and ask the host *before*
they invoke the tool function: Microsoft Agent Framework through
``approval_mode="always_require"``, LangGraph through the human-in-the-loop
middleware and an interrupt. In both cases the host records the answer, together
with the exact request the user saw, in the confirmation ledger. By the time the
capability runs, the broker finds that answer and never reaches an authority at
all.

Reaching this authority therefore means something went wrong: a capability was
gated by the policy but was not suspended by the framework, or its confirmation
was consumed by a different call. Rather than approve on the framework's behalf,
it refuses. Failing closed keeps a registration mistake from turning into an
unattended side effect.

It ships here rather than in each adapter because it holds no framework knowledge
whatsoever, and because every adapter needs exactly this behaviour. A copy per
framework would be one copy away from one of them quietly approving.
"""

from __future__ import annotations

from ygo74.agent_runtime.domains.security.user_context import UserContext

from ygo74.agent_runtime.domains.humanapproval.confirmation import ConfirmationDecision, ConfirmationRequest
from ygo74.agent_runtime.domains.humanapproval.approval_errors import ConfirmationRequiredError


class UnattendedApprovalAuthority:
    """Refuses to answer on behalf of an absent user."""

    async def obtain(self, request: ConfirmationRequest, user: UserContext) -> ConfirmationDecision:
        """Never approve: no human answered this request.

        Raises:
            ConfirmationRequiredError: always.
        """
        del user
        raise ConfirmationRequiredError(request.operation.tool_name)
