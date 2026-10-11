"""A developer-owned FastAPI entrypoint for the RAG agent."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from rag_agent import LocalKnowledgeBaseAgent

EXAMPLE_DIRECTORY = Path(__file__).resolve().parent
KNOWLEDGE_DIRECTORY = EXAMPLE_DIRECTORY / "knowledge_base"
load_dotenv(EXAMPLE_DIRECTORY / ".env")


class AskRequest(BaseModel):
    """Question accepted by the developer-owned RAG route."""

    question: str = Field(min_length=1)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Build the RAG index once for this application process."""
    app.state.agent = await LocalKnowledgeBaseAgent.from_directory(KNOWLEDGE_DIRECTORY)
    yield


app = FastAPI(title="Local Knowledge Base RAG - developer-owned API", lifespan=lifespan)


@app.post("/ask")
async def ask(request: AskRequest, http_request: Request) -> dict[str, str]:
    """Return a grounded answer using an application-owned JSON envelope."""
    agent: LocalKnowledgeBaseAgent = http_request.app.state.agent
    return {"answer": await agent.answer(request.question)}


@app.post("/ask/stream")
async def ask_stream(request: AskRequest, http_request: Request) -> StreamingResponse:
    """Stream answer text from the native model without runtime event conversion."""
    agent: LocalKnowledgeBaseAgent = http_request.app.state.agent
    return StreamingResponse(
        _answer_chunks(agent, request.question),
        media_type="text/plain; charset=utf-8",
    )


async def _answer_chunks(agent: LocalKnowledgeBaseAgent, question: str) -> AsyncIterator[str]:
    """Forward native RAG text chunks to the developer-owned HTTP response."""
    async for chunk in agent.stream(question):
        yield chunk
