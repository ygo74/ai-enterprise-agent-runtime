"""Developer-owned FastAPI entrypoint for the offline LangGraph agent."""

from typing import Any

from fastapi import FastAPI
from langchain_core.messages import AIMessage
from pydantic import BaseModel, Field

from native_agent import build_graph


class AskRequest(BaseModel):
    """Question accepted by the custom route."""

    question: str = Field(min_length=1)


app = FastAPI(title="LangGraph - developer-owned API")
graph: Any = build_graph(None)


@app.post("/ask")
async def ask(request: AskRequest) -> dict[str, str]:
    """Invoke the native graph and return its final assistant text."""
    state = await graph.ainvoke({"messages": [{"role": "user", "content": request.question}]})
    messages = state.get("messages", []) if isinstance(state, dict) else []
    answer = next((item for item in reversed(messages) if isinstance(item, AIMessage)), None)
    if answer is None:
        return {"answer": ""}
    if isinstance(answer.content, str):
        return {"answer": answer.content}
    return {
        "answer": "\n".join(
            str(block["text"])
            for block in answer.content
            if isinstance(block, dict) and isinstance(block.get("text"), str)
        )
    }
