from __future__ import annotations

import logging
from collections.abc import AsyncIterator, Awaitable
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from fastapi import FastAPI

from rag_agent import LocalKnowledgeBaseAgent
from ygo74.agent_runtime.domains.auth.authentication_policy import AuthenticationPolicy
from ygo74.agent_runtime.domains.discovery.agent_descriptor import (
    AgentCapabilitySet,
    AgentDescriptor,
    AgentSkill,
    Modality,
)
from ygo74.agent_runtime.domains.discovery.discovery_configuration import DiscoveryConfiguration
from ygo74.agent_runtime.domains.endpoints.hosting_factory import EndpointSurface, HostingFactory


EXAMPLE_DIRECTORY = Path(__file__).resolve().parent
KNOWLEDGE_DIRECTORY = EXAMPLE_DIRECTORY / "knowledge_base"
load_dotenv(EXAMPLE_DIRECTORY / ".env")

logging.basicConfig(level=logging.INFO)
logging.getLogger("ygo74.agent_runtime").setLevel(logging.DEBUG)


class RagApplication:
    def __init__(self, knowledge_directory: Path) -> None:
        self._knowledge_directory = knowledge_directory
        self._agent: LocalKnowledgeBaseAgent | None = None

    async def initialize(self) -> None:
        self._agent = await LocalKnowledgeBaseAgent.from_directory(self._knowledge_directory)

    def entrypoint(
        self,
        payload: dict[str, Any],
    ) -> Awaitable[dict[str, Any]] | AsyncIterator[str]:
        if payload.get("stream"):
            return self._stream(payload)
        return self._invoke(payload)

    async def _invoke(self, payload: dict[str, Any]) -> dict[str, Any]:
        agent = self._get_agent()
        result = await agent.answer(self._extract_question(payload))
        return {
            "request_id": payload["request_id"],
            "status": "success",
            "output": {"role": "assistant", "content": result},
            "metadata": {"route_key": payload["route_key"]},
        }

    async def _stream(self, payload: dict[str, Any]) -> AsyncIterator[str]:
        agent = self._get_agent()
        async for delta in agent.stream(self._extract_question(payload)):
            yield delta

    def _get_agent(self) -> LocalKnowledgeBaseAgent:
        if self._agent is None:
            raise RuntimeError("RAG application has not completed startup initialization")
        return self._agent

    @staticmethod
    def _extract_question(payload: dict[str, Any]) -> str:
        incoming = payload.get("input")
        if isinstance(incoming, str):
            return incoming

        if isinstance(incoming, list):
            questions: list[str] = []
            for item in incoming:
                if isinstance(item, dict):
                    if item.get("role") not in (None, "user"):
                        continue
                    content = item.get("content", item.get("text", ""))
                    if isinstance(content, list):
                        questions.extend(
                            str(part["text"])
                            for part in content
                            if isinstance(part, dict) and isinstance(part.get("text"), str)
                        )
                    elif isinstance(content, str):
                        questions.append(content)
                    continue
                questions.append(str(item))
            return "\n".join(questions)

        return str(incoming or "")


rag_application = RagApplication(KNOWLEDGE_DIRECTORY)


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    await rag_application.initialize()
    yield


app = FastAPI(title="Local Knowledge Base RAG Example", lifespan=lifespan)

AGENT_ID = "enterprise-rag-demo"
agent_descriptor = AgentDescriptor(
    agent_id=AGENT_ID,
    route_key=AGENT_ID,
    display_name="Enterprise Knowledge Base RAG",
    description="Answers questions grounded in a local Markdown knowledge base.",
    version="1.0.0",
    owner="ai-enterprise-agent-runtime",
    created_at_utc=datetime(2026, 10, 3, tzinfo=timezone.utc),
    capabilities=AgentCapabilitySet(
        streaming=True,
        input_modalities=(Modality.TEXT,),
        output_modalities=(Modality.TEXT,),
    ),
    tags=("rag", "knowledge-base"),
    skills=(
        AgentSkill(
            skill_id="grounded-qa",
            name="Grounded knowledge-base Q&A",
            description="Retrieves relevant local documents and answers with source citations.",
            examples=("How is retrieved document content protected from prompt injection?",),
        ),
    ),
)

(
    HostingFactory(app)
    .add_agent(rag_application.entrypoint, agent_descriptor)
    .add_ai_endpoints(
        EndpointSurface.OPENAI_RESPONSES,
        EndpointSurface.OPENAI_CHAT_COMPLETIONS,
    )
    .add_security(AuthenticationPolicy.anonymous())
    .add_discovery(DiscoveryConfiguration(enable_openai_models=True, enable_anthropic_models=True))
    .register()
)