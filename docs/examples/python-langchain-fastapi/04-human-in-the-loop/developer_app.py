"""A manually hosted approval flow using FastAPI and native LangGraph values."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any, Literal

from fastapi import FastAPI
from langchain_core.messages import AIMessage
from langgraph.types import Command
from pydantic import BaseModel, Field

from developer_agent import build_developer_agent


class AskRequest(BaseModel):
    """Input for the developer-owned agent route."""

    conversation_id: str = Field(min_length=1)
    question: str = Field(min_length=1)


class ApprovalDecision(BaseModel):
    """One direct answer to a suspended LangGraph tool call."""

    type: Literal["approve", "reject"]


class ResumeRequest(BaseModel):
    """Input used to resume a graph after the caller reviewed its actions."""

    conversation_id: str = Field(min_length=1)
    decisions: list[ApprovalDecision] = Field(min_length=1)


app = FastAPI(title="AI Solution Architect - developer-owned approval API")
agent = build_developer_agent()


@app.post("/ask")
async def ask(request: AskRequest) -> dict[str, object]:
    """Run one turn and return its answer or the actions waiting for a decision."""
    result = await agent.ainvoke(
        {"messages": [{"role": "user", "content": request.question}]},
        _config(request.conversation_id),
    )
    return _render_result(result)


@app.post("/resume")
async def resume(request: ResumeRequest) -> dict[str, object]:
    """Resume the graph with the caller's ordered approve-or-reject decisions."""
    command = Command(resume={"decisions": [item.model_dump() for item in request.decisions]})
    result = await agent.ainvoke(command, _config(request.conversation_id))
    return _render_result(result)


def _config(conversation_id: str) -> dict[str, dict[str, str]]:
    """Build the checkpoint configuration for one developer-owned conversation."""
    return {"configurable": {"thread_id": conversation_id}}


def _render_result(result: Any) -> dict[str, object]:
    """Select pending tool actions or the final assistant answer from graph state."""
    actions = _pending_actions(result)
    if actions:
        return {"status": "approval_required", "actions": actions}
    messages = result.get("messages", []) if isinstance(result, Mapping) else []
    answer = next((message for message in reversed(messages) if isinstance(message, AIMessage)), None)
    return {"status": "completed", "answer": _message_text(answer) if answer else ""}


def _pending_actions(result: Any) -> list[dict[str, object]]:
    """Read the framework's public action request fields without runtime adapters."""
    interrupts = result.get("__interrupt__", ()) if isinstance(result, Mapping) else ()
    actions: list[dict[str, object]] = []
    for interrupt in interrupts:
        value = getattr(interrupt, "value", None)
        if not isinstance(value, Mapping):
            continue
        requests = value.get("action_requests", ())
        if isinstance(requests, Sequence) and not isinstance(requests, (str, bytes)):
            actions.extend(dict(request) for request in requests if isinstance(request, Mapping))
    return actions


def _message_text(message: AIMessage) -> str:
    """Render text blocks from a native assistant message."""
    if isinstance(message.content, str):
        return message.content
    return "\n".join(
        str(block["text"])
        for block in message.content
        if isinstance(block, dict) and isinstance(block.get("text"), str)
    )
