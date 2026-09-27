"""Framework-neutral approval loop budgets and abandonment behavior."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass

from ygo74.agent_runtime.domains.humanapproval.approval_loop import ApprovalLoop


@dataclass(frozen=True, slots=True)
class FakeState:
    pending_rounds: int
    text: str = "completed"


class FakeAdapter:
    def __init__(self, *, fail_decline: bool = False) -> None:
        self.resumed = 0
        self.declined = 0
        self.discards = 0
        self.fail_decline = fail_decline

    def pending(self, state: FakeState) -> tuple[str, ...]:
        return (f"call-{state.pending_rounds}",) if state.pending_rounds else ()

    def will_question(self, pending: tuple[str, ...]) -> bool:
        return bool(pending)

    async def resume(self, pending: tuple[str, ...]) -> FakeState:
        self.resumed += 1
        return FakeState(int(pending[0].split("-")[-1]) - 1)

    async def decline(self, pending: tuple[str, ...]) -> FakeState:
        self.declined += 1
        if self.fail_decline:
            raise RuntimeError("framework failed")
        return FakeState(int(pending[0].split("-")[-1]) - 1)

    def discard_authorizations(self) -> None:
        self.discards += 1

    def final_text(self, state: FakeState) -> str:
        return state.text


def test_a_turn_without_pending_approvals_returns_framework_text() -> None:
    adapter = FakeAdapter()

    result = asyncio.run(ApprovalLoop(adapter).run(FakeState(0, "answer")))

    assert result == "answer"
    assert adapter.resumed == 0


def test_an_approval_sequence_resumes_until_the_framework_completes() -> None:
    adapter = FakeAdapter()

    result = asyncio.run(ApprovalLoop(adapter).run(FakeState(3)))

    assert result == "completed"
    assert adapter.resumed == 3


def test_exceeding_question_budget_discards_grants_and_declines_every_pending_batch() -> None:
    adapter = FakeAdapter()
    loop = ApprovalLoop(adapter, max_approval_rounds=1)

    result = asyncio.run(loop.run(FakeState(4)))

    assert "too many approvals" in result
    assert adapter.resumed == 1
    assert adapter.declined == 3
    assert adapter.discards == 4


def test_exceeding_total_round_budget_abandons_with_bounded_refusal() -> None:
    adapter = FakeAdapter()
    loop = ApprovalLoop(adapter, max_total_rounds=2)

    result = asyncio.run(loop.run(FakeState(10)))

    assert "more tool calls" in result
    assert adapter.resumed == 2
    assert adapter.declined == 8


def test_failed_abandon_cleanup_does_not_restore_grants_or_escape() -> None:
    adapter = FakeAdapter(fail_decline=True)
    loop = ApprovalLoop(adapter, max_approval_rounds=0)

    result = asyncio.run(loop.run(FakeState(1)))

    assert "too many approvals" in result
    assert adapter.discards == 2
