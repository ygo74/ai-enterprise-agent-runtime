"""Expose the local MAF RAG agent through a small developer-owned FastAPI app."""

from fastapi import FastAPI
from pydantic import BaseModel, Field

from agent import create_agent


class AskRequest(BaseModel):
    """Question accepted by the RAG route."""

    question: str = Field(min_length=1)


app = FastAPI(title="MAF local knowledge-base example")
_AGENT = create_agent()


@app.post("/ask")
async def ask(request: AskRequest) -> dict[str, str]:
    """Retrieve local evidence and return the native MAF answer.

    Args:
        request: User question.

    Returns:
        dict[str, str]: Answer text returned by the MAF agent.
    """
    response = await _AGENT.run(request.question)
    return {"answer": response.text or ""}
