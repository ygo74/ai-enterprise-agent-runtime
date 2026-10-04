"""Bounded orchestration for framework-owned approval state."""

from __future__ import annotations

import logging
from typing import Generic, Protocol, TypeVar

_MAX_APPROVAL_ROUNDS = 25
_MAX_TOTAL_ROUNDS = 200
_MAX_DECLINE_ROUNDS = 25

_INTERRUPTED = (
    "The request asked for too many approvals in a row, so it was interrupted. "
    "Everything still pending was declined and nothing was changed."
)
_EXHAUSTED = (
    "The request needed more tool calls than one turn allows, so it was interrupted. "
    "Everything still pending was declined and nothing was changed. Ask for a smaller batch."
)

_logger = logging.getLogger(__name__)

StateT = TypeVar("StateT")
PendingT = TypeVar("PendingT")


class ApprovalTurnAdapter(Protocol[StateT, PendingT]):
    """Framework-specific view and operations for one approval turn."""
    def pending(self, state: StateT) -> tuple[PendingT, ...]:
        """Inspect framework state and return its suspended calls.

        Args:
            state (StateT): The state that tracks the current operation lifecycle.
        """
        ...

    def will_question(self, pending: tuple[PendingT, ...]) -> bool:
        """Whether resolving this batch will ask the user a question.

        Args:
            pending (tuple[PendingT, ...]): Approval requests or content items that still require handling.
        """
        ...

    async def resume(self, pending: tuple[PendingT, ...]) -> StateT:
        """Resolve a batch and resume the framework with its decisions.

        Args:
            pending (tuple[PendingT, ...]): Approval requests or content items that still require handling.
        """
        ...

    async def decline(self, pending: tuple[PendingT, ...]) -> StateT:
        """Refuse a batch of suspended calls and return the new state.

        Args:
            pending (tuple[PendingT, ...]): Approval requests or content items that still require handling.
        """
        ...

    def discard_authorizations(self) -> None:
        """Clear decisions that could otherwise authorize later operations."""
        ...

    def final_text(self, state: StateT) -> str:
        """Extract the final user-facing response from framework state.

        Args:
            state (StateT): The state that tracks the current operation lifecycle.
        """
        ...


class ApprovalLoop(Generic[StateT, PendingT]):
    """Apply shared turn limits and fail-closed cleanup to an adapter.

    Args:
        adapter (ApprovalTurnAdapter[StateT, PendingT]): Framework adapter converting native values to the neutral contract.
        max_approval_rounds (int): Maximum approval-question rounds before abandoning the invocation.
        max_total_rounds (int): Maximum total framework resume rounds for this invocation.
        max_decline_rounds (int): Maximum consecutive approval declines before ending the interaction.
        interrupted_message (str): Text returned when the approval sequence is interrupted.
        exhausted_message (str): Text returned when the total resume-round limit is exhausted.
    """
    def __init__(
        self,
        adapter: ApprovalTurnAdapter[StateT, PendingT],
        *,
        max_approval_rounds: int = _MAX_APPROVAL_ROUNDS,
        max_total_rounds: int = _MAX_TOTAL_ROUNDS,
        max_decline_rounds: int = _MAX_DECLINE_ROUNDS,
        interrupted_message: str = _INTERRUPTED,
        exhausted_message: str = _EXHAUSTED,
    ) -> None:
        """Initialize the instance runtime data with supplied collaborators and configuration.

        Args:
            adapter (ApprovalTurnAdapter[StateT, PendingT]): Framework adapter converting native values to the neutral contract.
            max_approval_rounds (int): Maximum approval-question rounds before abandoning the invocation.
            max_total_rounds (int): Maximum total framework resume rounds for this invocation.
            max_decline_rounds (int): Maximum consecutive approval declines before ending the interaction.
            interrupted_message (str): Text returned when the approval sequence is interrupted.
            exhausted_message (str): Text returned when the total resume-round limit is exhausted.
        """
        if max_approval_rounds < 0 or max_total_rounds < 1 or max_decline_rounds < 1:
            raise ValueError("approval loop limits must allow a bounded turn and cleanup")
        self._adapter = adapter
        self._max_approval_rounds = max_approval_rounds
        self._max_total_rounds = max_total_rounds
        self._max_decline_rounds = max_decline_rounds
        self._interrupted_message = interrupted_message
        self._exhausted_message = exhausted_message

    async def run(self, state: StateT) -> str:
        """Resolve a bounded approval sequence and return the framework text.

        Args:
            state (StateT): The state that tracks the current operation lifecycle.
        """
        # Bound both total resume attempts and approval questions so repeated framework handoffs cannot keep the invocation open indefinitely.
        asked = 0
        for _ in range(self._max_total_rounds):
            pending = self._adapter.pending(state)
            if not pending:
                return self._adapter.final_text(state)

            if self._adapter.will_question(pending):
                asked += 1
                if asked > self._max_approval_rounds:
                    return await self._abandon(state, self._interrupted_message)

            state = await self._adapter.resume(pending)

        return await self._abandon(state, self._exhausted_message)

    async def _abandon(self, state: StateT, message: str) -> str:
        """Purge grants before best-effort bounded refusal of suspended calls.

        Args:
            state (StateT): The state that tracks the current operation lifecycle.
            message (str): Framework message or protocol message being converted.
        """
        self._adapter.discard_authorizations()
        current = state
        for _ in range(self._max_decline_rounds):
            pending = self._adapter.pending(current)
            if not pending:
                return message
            try:
                current = await self._adapter.decline(pending)
            except Exception as error:  # noqa: BLE001 - grants are already discarded
                _logger.warning("could not finish declining an abandoned turn: %s", type(error).__name__)
                return message
            finally:
                self._adapter.discard_authorizations()
        return message
