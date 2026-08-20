from __future__ import annotations

import asyncio
import logging
import os
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from langchain.agents import create_agent
from langchain.agents.middleware import HumanInTheLoopMiddleware
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command

from env_loader import ensure_env_loaded
from mcp_mslearn_tool import mslearn_mcp_search

ensure_env_loaded()

logger = logging.getLogger(__name__)


SYSTEM_PROMPT = (
    "You are a Senior AI Solution Architect. "
    "Design production-ready AI architectures, justify tradeoffs, cite Microsoft Learn references, "
    "and provide clear migration and operations guidance. "
    "When documentation is needed, call the mslearn_mcp_search tool first."
)

# Name of the tool gated behind human approval. Kept as a constant so the
# middleware configuration and any UI/logging code referring to it stay in sync.
GATED_TOOL_NAME = "mslearn_mcp_search"

# Tool argument a reviewer is allowed to rewrite when editing a gated call.
EDITABLE_ARGUMENT = "query"


class AgentTurnStatus(StrEnum):
    """Outcome of one conversation turn."""

    COMPLETED = "completed"
    AWAITING_APPROVAL = "awaiting_approval"


class HumanDecisionType(StrEnum):
    """Decision a reviewer can take on a paused tool call."""

    APPROVE = "approve"
    EDIT = "edit"
    REJECT = "reject"


@dataclass(slots=True, frozen=True)
class PendingToolAction:
    """A tool call the agent proposed but that is paused for human review."""

    name: str
    arguments: dict[str, Any]
    description: str


@dataclass(slots=True, frozen=True)
class HumanDecision:
    """Reviewer decision, expressed as a chat reply and mapped to the HITL schema."""

    decision_type: HumanDecisionType
    edited_arguments: dict[str, Any] | None = None
    message: str | None = None

    def to_payload(self, action: PendingToolAction) -> dict[str, Any]:
        """Project this decision into LangChain's `Decision` wire shape."""

        if self.decision_type is HumanDecisionType.EDIT:
            arguments = dict(action.arguments)
            arguments.update(self.edited_arguments or {})
            return {
                "type": HumanDecisionType.EDIT.value,
                "edited_action": {"name": action.name, "args": arguments},
            }

        if self.decision_type is HumanDecisionType.REJECT:
            payload: dict[str, Any] = {"type": HumanDecisionType.REJECT.value}
            if self.message:
                payload["message"] = self.message
            return payload

        return {"type": HumanDecisionType.APPROVE.value}


@dataclass(slots=True, frozen=True)
class AgentTurnResult:
    """Result of running one turn of the solution architect agent."""

    status: AgentTurnStatus
    thread_id: str
    output: str
    pending_actions: tuple[PendingToolAction, ...] = ()


class ChatApprovalParser:
    """Maps a free-text chat reply into a tool-approval decision.

    The reviewer never calls a dedicated approval API: they answer in the chat
    like they would answer any other agent question, and this parser turns that
    answer into an `approve`, `edit`, or `reject` decision.
    """

    APPROVALS = frozenset(
        {
            "oui",
            "ok",
            "okay",
            "yes",
            "y",
            "approve",
            "approved",
            "approuve",
            "approuver",
            "autorise",
            "autoriser",
            "accepte",
            "accepter",
            "confirme",
            "valide",
            "valider",
            "go",
            "vas-y",
            "d'accord",
            "daccord",
        }
    )
    REJECTIONS = frozenset(
        {
            "non",
            "no",
            "n",
            "nope",
            "reject",
            "rejette",
            "refuse",
            "refuser",
            "annule",
            "annuler",
            "stop",
        }
    )
    EDIT_PREFIXES = ("edit:", "modifie:", "modifier:")

    # Punctuation and markdown decorations a chat UI (or a user) may wrap the
    # answer with, stripped before keyword matching.
    _NOISE = "\"'`*_-«»“”.,!?;:()[]{}"

    def parse(self, reply: str) -> HumanDecision | None:
        """Return the decision expressed by `reply`, or `None` when it is ambiguous."""

        stripped = reply.strip()
        if not stripped:
            return None

        normalized = stripped.lower()

        for prefix in self.EDIT_PREFIXES:
            if normalized.startswith(prefix):
                edited_query = stripped[len(prefix) :].strip()
                if not edited_query:
                    return None
                return HumanDecision(
                    decision_type=HumanDecisionType.EDIT,
                    edited_arguments={EDITABLE_ARGUMENT: edited_query},
                )

        keyword = self._first_keyword(normalized)

        if keyword in self.APPROVALS:
            return HumanDecision(decision_type=HumanDecisionType.APPROVE)

        if keyword in self.REJECTIONS:
            return HumanDecision(decision_type=HumanDecisionType.REJECT, message=stripped)

        return None

    def _first_keyword(self, normalized: str) -> str:
        for token in normalized.split():
            keyword = token.strip(self._NOISE)
            if keyword:
                return keyword

        return ""


class ApprovalPrompt:
    """Renders the end-of-turn approval question displayed in the chat UI."""

    INSTRUCTIONS = (
        "Repondez `oui` pour approuver, `non` pour refuser, "
        "ou `modifie: <nouvelle requete>` pour ajuster les arguments."
    )

    def render(self, actions: Sequence[PendingToolAction]) -> str:
        lines = ["Je dois utiliser un outil avant de continuer. Autorisez-vous cet appel ?", ""]
        lines.extend(f"- `{action.name}` avec {action.arguments}" for action in actions)
        lines.extend(["", self.INSTRUCTIONS])
        return "\n".join(lines)

    def render_retry(self, actions: Sequence[PendingToolAction]) -> str:
        return "\n".join(["Je n'ai pas compris votre decision.", "", self.render(actions)])


def _extract_final_message_text(state: Any) -> str:
    if isinstance(state, Mapping):
        messages = state.get("messages")
        if isinstance(messages, list) and messages:
            last = messages[-1]
            content = getattr(last, "content", last)
            if isinstance(content, str):
                return content
            if isinstance(content, list):
                parts: list[str] = []
                for item in content:
                    if isinstance(item, Mapping) and item.get("type") == "text":
                        parts.append(str(item.get("text", "")))
                    else:
                        parts.append(str(item))
                return "\n".join(part for part in parts if part)
            return str(content)

    return str(state)


class ThreadLockRegistry:
    """Serializes the turns of a single conversation thread.

    LangGraph checkpoints are linear per `thread_id`: each turn appends a new
    checkpoint and `aget_state` returns the latest one. Two turns running
    concurrently on the same thread therefore race, and the one finishing last
    hides whatever the other saved — including a paused tool call waiting for
    approval. Holding a per-thread lock keeps turns strictly sequential.
    """

    def __init__(self) -> None:
        self._locks: dict[str, asyncio.Lock] = {}

    def acquire(self, thread_id: str) -> asyncio.Lock:
        lock = self._locks.get(thread_id)
        if lock is None:
            lock = asyncio.Lock()
            self._locks[thread_id] = lock
        return lock


class SolutionArchitectAgent:
    """LangChain agent whose research tool is gated by in-chat human approval.

    Every call to `mslearn_mcp_search` pauses execution through LangGraph's
    `HumanInTheLoopMiddleware`. Instead of exposing a separate approval API, the
    agent ends its turn by asking for authorization as a normal assistant
    message. The reviewer answers in the chat, and the next request on the same
    conversation resumes the paused graph with that decision.

    Conversation state is keyed by `thread_id` (the caller passes the chat
    conversation id). Use a persistent checkpointer (e.g. `AsyncPostgresSaver`)
    instead of `InMemorySaver` in production, since in-memory state is lost on
    process restart.
    """

    def __init__(
        self,
        approval_parser: ChatApprovalParser | None = None,
        approval_prompt: ApprovalPrompt | None = None,
    ) -> None:
        self._checkpointer = InMemorySaver()
        self._agent = self._build_agent()
        self._approval_parser = approval_parser or ChatApprovalParser()
        self._approval_prompt = approval_prompt or ApprovalPrompt()
        self._thread_locks = ThreadLockRegistry()

    def _build_agent(self) -> Any:
        model_name = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
        llm = ChatOpenAI(model=model_name, temperature=1)

        return create_agent(
            model=llm,
            tools=[mslearn_mcp_search],
            system_prompt=SYSTEM_PROMPT,
            middleware=[
                HumanInTheLoopMiddleware(
                    interrupt_on={
                        GATED_TOOL_NAME: {"allowed_decisions": ["approve", "edit", "reject"]},
                    },
                    description_prefix="Tool execution pending approval",
                ),
            ],
            checkpointer=self._checkpointer,
        )

    async def run_turn(self, thread_id: str, user_input: str) -> AgentTurnResult:
        """Run one conversation turn, resuming a paused tool call when one is waiting."""

        logger.info(
            "run_turn: thread_id=%r reply_preview=%r",
            thread_id,
            user_input[:120],
        )

        lock = self._thread_locks.acquire(thread_id)
        if lock.locked():
            logger.info(
                "run_turn: thread_id=%r already has a turn in flight; waiting for it to finish before "
                "reading the checkpoint",
                thread_id,
            )

        async with lock:
            return await self._run_turn(thread_id, user_input)

    async def _run_turn(self, thread_id: str, user_input: str) -> AgentTurnResult:
        pending = await self._pending_actions(thread_id)
        if pending:
            logger.info(
                "_run_turn: thread_id=%r has %d pending action(s); resuming instead of starting a new turn",
                thread_id,
                len(pending),
            )
            return await self._resume_turn(thread_id, user_input, pending)

        logger.info("_run_turn: thread_id=%r has no pending action; starting a new turn", thread_id)
        result = await self._agent.ainvoke(
            {"messages": [{"role": "user", "content": user_input}]},
            config=self._config(thread_id),
        )
        return await self._to_turn_result(thread_id, result)

    async def _resume_turn(
        self,
        thread_id: str,
        reply: str,
        pending: tuple[PendingToolAction, ...],
    ) -> AgentTurnResult:
        decision = self._approval_parser.parse(reply)
        logger.info(
            "_resume_turn: thread_id=%r reply=%r parsed_decision=%s",
            thread_id,
            reply,
            decision.decision_type.value if decision else None,
        )
        if decision is None:
            logger.warning(
                "_resume_turn: thread_id=%r reply=%r did not match any known decision keyword; re-asking",
                thread_id,
                reply,
            )
            return AgentTurnResult(
                status=AgentTurnStatus.AWAITING_APPROVAL,
                thread_id=thread_id,
                output=self._approval_prompt.render_retry(pending),
                pending_actions=pending,
            )

        decisions = [decision.to_payload(action) for action in pending]
        logger.info("_resume_turn: thread_id=%r resuming with decisions=%s", thread_id, decisions)
        result = await self._agent.ainvoke(
            Command(resume={"decisions": decisions}),
            config=self._config(thread_id),
        )
        return await self._to_turn_result(thread_id, result)

    async def _to_turn_result(self, thread_id: str, result: Any) -> AgentTurnResult:
        pending = await self._pending_actions(thread_id)
        if pending:
            logger.info(
                "_to_turn_result: thread_id=%r ended the turn with %d pending action(s): %s",
                thread_id,
                len(pending),
                [action.name for action in pending],
            )
            return AgentTurnResult(
                status=AgentTurnStatus.AWAITING_APPROVAL,
                thread_id=thread_id,
                output=self._approval_prompt.render(pending),
                pending_actions=pending,
            )

        logger.info("_to_turn_result: thread_id=%r completed with no pending action", thread_id)
        return AgentTurnResult(
            status=AgentTurnStatus.COMPLETED,
            thread_id=thread_id,
            output=_extract_final_message_text(result),
        )

    async def _pending_actions(self, thread_id: str) -> tuple[PendingToolAction, ...]:
        snapshot = await self._agent.aget_state(self._config(thread_id))
        interrupts = getattr(snapshot, "interrupts", ()) or ()
        logger.info(
            "_pending_actions: thread_id=%r checkpoint_id=%r next=%r interrupt_count=%d",
            thread_id,
            snapshot.config.get("configurable", {}).get("checkpoint_id") if snapshot.config else None,
            getattr(snapshot, "next", None),
            len(interrupts),
        )

        actions: list[PendingToolAction] = []
        for item in interrupts:
            value = getattr(item, "value", item)
            if not isinstance(value, Mapping):
                logger.warning(
                    "_pending_actions: thread_id=%r interrupt value is not a mapping: %r", thread_id, value
                )
                continue
            for request in value.get("action_requests") or ():
                if not isinstance(request, Mapping):
                    continue
                actions.append(
                    PendingToolAction(
                        name=str(request.get("name", "")),
                        arguments=dict(request.get("args") or {}),
                        description=str(request.get("description", "")),
                    )
                )

        logger.info(
            "_pending_actions: thread_id=%r resolved %d pending action(s): %s",
            thread_id,
            len(actions),
            [action.name for action in actions],
        )
        return tuple(actions)

    @staticmethod
    def _config(thread_id: str) -> dict[str, Any]:
        return {"configurable": {"thread_id": thread_id}}


# A single process-wide agent instance so the in-memory checkpointer survives
# between the turn that asks for approval and the turn that answers it.
_agent_singleton: SolutionArchitectAgent | None = None


def get_solution_architect_agent() -> SolutionArchitectAgent:
    global _agent_singleton
    if _agent_singleton is None:
        logger.info("get_solution_architect_agent: creating the process-wide agent singleton")
        _agent_singleton = SolutionArchitectAgent()
    return _agent_singleton


async def run_solution_architect_agent(thread_id: str, user_input: str) -> AgentTurnResult:
    return await get_solution_architect_agent().run_turn(thread_id, user_input)
