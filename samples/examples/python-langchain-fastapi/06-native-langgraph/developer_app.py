"""A minimal developer-owned FastAPI host for the offline LangGraph agent."""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI
from langchain_core.messages import AIMessage
from pydantic import BaseModel, Field

from native_agent import build_graph


class AskRequest(BaseModel):
    """Question accepted by the developer-owned route."""

    question: str = Field(min_length=1)


app = FastAPI(title="Offline LangGraph - developer-owned API")
graph: Any = build_graph(None)


@app.post("/ask")
async def ask(request: AskRequest) -> dict[str, str]:
    """Invoke the existing native graph and return its final assistant text."""
    state = await graph.ainvoke({"messages": [{"role": "user", "content": request.question}]})
    messages = state.get("messages", []) if isinstance(state, dict) else []
    answer = next((item for item in reversed(messages) if isinstance(item, AIMessage)), None)
    return {"answer": _message_text(answer) if answer is not None else ""}


def _message_text(message: AIMessage) -> str:
    """Render text blocks from a native assistant message."""
    if isinstance(message.content, str):
        return message.content
    return "\n".join(
        str(block["text"])
        for block in message.content
        if isinstance(block, dict) and isinstance(block.get("text"), str)
    )
