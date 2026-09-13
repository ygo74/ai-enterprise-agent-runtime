"""Translation between LangGraph interrupts and the runtime's approval domain.

LangChain's human-in-the-loop middleware suspends a tool call listed in
``interrupt_on`` and reports it through the graph's ``__interrupt__`` payload. The
host answers with ``Command(resume={"decisions": [...]})``.

This module converts those framework payloads into the vocabulary
``ygo74-agent-runtime`` already speaks, so the policy, the ticket and the audit
trail all talk about the same thing.

It lives in the example rather than in the library on purpose. The library owns
*whether* an operation needs an approval and *what* a person is shown; how a
particular framework suspends a call is that framework's business, and a library
that knew would have to know all of them.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from langchain.agents.middleware import InterruptOnConfig
from langgraph.types import Command

from ygo74.agent_runtime.domains.humanapproval.confirmation import ConfirmationPolicy
from ygo74.agent_runtime.domains.security.operations import ToolOperationDescriptor
from ygo74.agent_runtime.domains.security.user_context import UserContext

# The only two answers a gated capability accepts.
#
# `edit` is excluded on purpose. It lets the human change the arguments *after*
# the confirmation was granted, while the approval is recorded against the exact
# request the person was shown. Accepting an edit would run arguments nobody
# confirmed, which is a confirmation bypass wearing the costume of a feature.
#
# `respond` is excluded for a different reason: its message is delivered to the
# model as a *successful* tool result. On an operation with side effects, a
# refusal would then be indistinguishable from the operation having happened.
ALLOWED_DECISIONS = ("approve", "reject")

APPROVE = "approve"
REJECT = "reject"


class PendingToolApproval:
    """One suspended tool call waiting for the user's answer."""

    def __init__(self, action: Mapping[str, Any]) -> None:
        self._action = action

    @property
    def tool_name(self) -> str:
        """Name of the capability the model wants to run."""
        return str(self._action.get("name", ""))

    @property
    def arguments(self) -> Mapping[str, Any]:
        """Arguments the model proposed, always a mapping.

        These are what gets stored on the ticket, and what is replayed on
        approval. They never travel back through the model.
        """
        raw = self._action.get("args")
        return dict(raw) if isinstance(raw, Mapping) else {}

    def answer(self, *, approved: bool) -> dict[str, Any]:
        """Build the framework decision carrying the user's answer."""
        if approved:
            return {"type": APPROVE}
        return {"type": REJECT, "message": "The user declined this operation."}


class LangGraphApprovalBridge:
    """Builds the interrupt policy, reads interrupts and answers them."""

    def interrupt_on(
        self,
        operations: Sequence[ToolOperationDescriptor],
        policy: ConfirmationPolicy,
        user: UserContext,
    ) -> dict[str, bool | InterruptOnConfig]:
        """Map the confirmation policy onto the middleware configuration.

        Every capability is named explicitly, including the ungated ones. A
        capability missing from this mapping is simply not interrupted, so
        listing only the gated ones would let a typo silently ungate an
        operation instead of failing.
        """
        return {
            operation.tool_name: self._entry(policy.requires_confirmation(operation, user))
            for operation in operations
        }

    @staticmethod
    def _entry(gated: bool) -> bool | InterruptOnConfig:
        """Return the middleware entry of one capability."""
        if not gated:
            return False
        return InterruptOnConfig(allowed_decisions=list(ALLOWED_DECISIONS))

    def pending_approvals(self, interrupts: Sequence[Any]) -> tuple[PendingToolApproval, ...]:
        """Every tool call the framework suspended in this response."""
        return tuple(
            PendingToolApproval(action) for interrupt in interrupts for action in self._action_requests(interrupt)
        )

    @staticmethod
    def _action_requests(interrupt: Any) -> tuple[Mapping[str, Any], ...]:
        """Read the actions carried by one interrupt, tolerating another shape.

        An interrupt raised by something other than this middleware carries a
        payload of its own. It is not an approval request and is skipped rather
        than guessed at.
        """
        value = getattr(interrupt, "value", interrupt)
        if not isinstance(value, Mapping):
            return ()
        requests = value.get("action_requests")
        if not isinstance(requests, Sequence) or isinstance(requests, (str, bytes)):
            return ()
        return tuple(request for request in requests if isinstance(request, Mapping))

    def resume_command(self, decisions: Sequence[Mapping[str, Any]]) -> Command[Any]:
        """Build the command that resumes the suspended calls.

        The framework matches decisions to actions by position, so the order the
        approvals were read in is the order they must be answered in.
        """
        return Command(resume={"decisions": list(decisions)})
