"""A developer-owned FastAPI entrypoint around the LangChain agent."""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI
from pydantic import BaseModel, Field
from langchain_core.messages import AIMessage

from solution_architect_graph import build_solution_architect_agent


class AskRequest(BaseModel):
    """Question accepted by the developer's custom HTTP route."""

    question: str = Field(min_length=1)


app = FastAPI(title="AI Solution Architect - developer-owned API")
agent = build_solution_architect_agent()


@app.post("/ask")
async def ask(request: AskRequest) -> dict[str, str]:
    """Run the agent and return the answer using an application-owned response shape."""
    state = await agent.ainvoke({"messages": [{"role": "user", "content": request.question}]})
    message = _last_answer(state)
    return {"answer": _message_text(message)}


def _last_answer(state: Any) -> AIMessage:
    """Select the last assistant message from the LangGraph state."""
    messages = state.get("messages", []) if isinstance(state, dict) else []
    message = next((item for item in reversed(messages) if isinstance(item, AIMessage)), None)
    if message is None:
        raise ValueError("The agent returned no assistant answer.")
    return message


def _message_text(message: AIMessage) -> str:
    """Render the text blocks from a native assistant message."""
    if isinstance(message.content, str):
        return message.content
    return "\n".join(
        str(block["text"])
        for block in message.content
        if isinstance(block, dict) and isinstance(block.get("text"), str)
    )
