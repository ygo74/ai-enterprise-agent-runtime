"""LangGraph's interrupt and resume shapes for the shared approval loop."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from langgraph.types import Command


class LangGraphDecisionType(StrEnum):
    """Answers accepted by LangGraph's human-in-the-loop middleware."""

    APPROVE = "approve"
    REJECT = "reject"


@dataclass(frozen=True, slots=True)
class LangGraphApprovalDecision:
    """One validated decision for a suspended tool call.

    Args:
        type: Whether the suspended call is approved or rejected.
        message: Optional rejection explanation shown to the graph.
    """

    type: LangGraphDecisionType
    message: str | None = None

    @staticmethod
    def for_approval(*, approved: bool) -> LangGraphApprovalDecision:
        """Create the built-in explicit approval or rejection decision."""
        decision = LangGraphDecisionType.APPROVE if approved else LangGraphDecisionType.REJECT
        message = None if approved else "The user declined this operation."
        return LangGraphApprovalDecision(decision, message)

    def to_wire(self) -> dict[str, str]:
        """Return LangGraph's public resume payload for this decision."""
        value = {"type": self.type.value}
        if self.message is not None:
            value["message"] = self.message
        return value


class LangGraphPendingApproval:
    """A safely typed view of one LangGraph action request.

    Args:
        action: Raw interrupt action request at the framework boundary.
    """

    def __init__(self, action: Mapping[str, Any]) -> None:
        """Retain the framework request and validate its public shape."""
        name = action.get("name")
        if not isinstance(name, str):
            raise TypeError("LangGraph approval action requires a tool name")
        arguments = action.get("args", {})
        if not isinstance(arguments, Mapping):
            raise TypeError("LangGraph approval arguments must be an object")
        self._tool_name = name
        self._arguments = dict(arguments)

    @property
    def tool_name(self) -> str:
        """Return the requested tool name for trusted domain resolution."""
        return self._tool_name

    @property
    def arguments(self) -> Mapping[str, Any]:
        """Return a defensive copy of proposed arguments to a trusted resolver."""
        return dict(self._arguments)

    def answer(self, *, approved: bool) -> dict[str, str]:
        """Build an explicit approve or reject response for this request."""
        decision = LangGraphDecisionType.APPROVE if approved else LangGraphDecisionType.REJECT
        message = None if approved else "The user declined this operation."
        return LangGraphApprovalDecision(decision, message).to_wire()


class LangGraphApprovalTranslator:
    """Translate LangGraph interrupt actions and resume commands."""

    def pending(self, result: object) -> tuple[LangGraphPendingApproval, ...]:
        """Extract every action request, preserving its framework order."""
        interrupts = self._interrupts(result)
        pending: list[LangGraphPendingApproval] = []
        for interrupt in interrupts:
            value = getattr(interrupt, "value", None)
            if not isinstance(value, Mapping):
                continue
            actions = value.get("action_requests", ())
            if not isinstance(actions, Sequence) or isinstance(actions, str | bytes):
                continue
            pending.extend(LangGraphPendingApproval(item) for item in actions if isinstance(item, Mapping))
        if interrupts and not pending:
            raise ValueError("LangGraph returned an interrupt without action requests")
        return tuple(pending)

    @staticmethod
    def _interrupts(result: object) -> tuple[object, ...]:
        """Read interrupts from current LangGraph result wrappers or mappings."""
        carried = getattr(result, "interrupts", None)
        if carried:
            return tuple(carried)
        state = getattr(result, "value", result)
        if isinstance(state, Mapping):
            return tuple(state.get("__interrupt__") or ())
        return ()

    @staticmethod
    def resume_command(
        decisions: Sequence[LangGraphApprovalDecision | Mapping[str, Any]],
        *,
        expected_count: int,
    ) -> Command[Any]:
        """Build a position-matched command after validating every decision."""
        if len(decisions) != expected_count:
            raise ValueError("LangGraph requires one decision per suspended action")
        wire: list[dict[str, str]] = []
        for decision in decisions:
            if isinstance(decision, LangGraphApprovalDecision):
                wire.append(decision.to_wire())
                continue
            if not isinstance(decision, Mapping):
                raise TypeError("LangGraph approval resolver returned an invalid decision")
            raw_type = decision.get("type")
            if not isinstance(raw_type, str):
                raise TypeError("LangGraph approval decision type must be text")
            try:
                decision_type = LangGraphDecisionType(raw_type)
            except (TypeError, ValueError) as error:
                raise ValueError("LangGraph approval resolver returned an unknown decision") from error
            message = decision.get("message")
            if message is not None and not isinstance(message, str):
                raise TypeError("LangGraph decision message must be text")
            wire.append(LangGraphApprovalDecision(decision_type, message).to_wire())
        return Command(resume={"decisions": wire})

    @staticmethod
    def discard_authorizations(resolver: object) -> None:
        """Call an optional domain grant cleanup hook when one is provided."""
        discard = getattr(resolver, "discard_authorizations", None)
        if callable(discard):
            discard()
