from __future__ import annotations

from contextvars import ContextVar
import logging
from collections.abc import Mapping, Sequence
from datetime import datetime, timezone
from typing import Any

from fastapi import FastAPI, Request

from agent_solution_architect import (
    AgentTurnResult,
    AgentTurnStatus,
    run_solution_architect_agent,
)
from env_loader import ensure_env_loaded
from ygo74.agent_runtime import (
    AgentCapabilitySet,
    AgentDescriptor,
    AgentSkill,
    DescriptorRegistry,
    DiscoveryConfiguration,
    Modality,
    add_ai_endpoints,
)

ensure_env_loaded()

logging.basicConfig(level=logging.INFO)
logging.getLogger("ygo74.agent_runtime").setLevel(logging.INFO)

logger = logging.getLogger(__name__)


app = FastAPI(title="AI Solution Architect - Human-in-the-Loop Example")

_REQUEST_HEADERS: ContextVar[dict[str, str]] = ContextVar("request_headers", default={})


@app.middleware("http")
async def capture_request_headers(request: Request, call_next: Any) -> Any:
    header_map = {str(key).lower(): str(value) for key, value in request.headers.items()}
    logger.info(
        "capture_request_headers: %s %s x-conversation-id=%r",
        request.method,
        request.url.path,
        header_map.get("x-conversation-id"),
    )
    token = _REQUEST_HEADERS.set(header_map)
    try:
        return await call_next(request)
    finally:
        _REQUEST_HEADERS.reset(token)

# Declaring an identity is what makes this agent discoverable via GET /v1/models.
# See ../agent-descriptor.md for the full guide.
AGENT_ID = "ai-solution-architect-hitl"

agent_descriptor = AgentDescriptor(
    agent_id=AGENT_ID,
    route_key=AGENT_ID,
    display_name="AI Solution Architect (Human-in-the-Loop)",
    description=(
        "Same solution-architecture agent as 01-get-started, but every call to its "
        "Microsoft Learn research tool must be approved by the user in the chat before "
        "it runs (LangChain HumanInTheLoopMiddleware, resumed by conversation id)."
    ),
    version="1.0.0",
    owner="ai-enterprise-agent-runtime",
    created_at_utc=datetime(2026, 8, 17, tzinfo=timezone.utc),
    capabilities=AgentCapabilitySet(
        streaming=False,
        input_modalities=(Modality.TEXT,),
        output_modalities=(Modality.TEXT,),
    ),
    tags=("solution-architecture", "azure", "human-in-the-loop"),
    skills=(
        AgentSkill(
            skill_id="solution-architecture-qa",
            name="Solution architecture Q&A",
            description=(
                "Answers Azure architecture questions, citing Microsoft Learn content. "
                "Tool calls are proposed in the chat and run only after the user approves."
            ),
            examples=("What's the best way to expose a private AKS cluster to partners?",),
        ),
    ),
)


class ConversationInputReader:
    """Reads the latest user message out of an endpoint payload.

    Chat clients such as LibreChat replay the whole conversation on every call,
    so `payload["input"]` is usually the full `messages` array rather than the
    text the user just typed. The agent keeps its own history in the LangGraph
    checkpoint keyed by conversation id, so only the newest user message must be
    forwarded — otherwise an approval reply like `oui` would be buried inside a
    serialized transcript and never recognized.
    """

    USER_ROLE = "user"
    TEXT_KEYS = ("text", "input_text")

    def latest_user_text(self, payload: Mapping[str, Any]) -> str:
        incoming = payload.get("input")

        if isinstance(incoming, str):
            return incoming.strip()

        if isinstance(incoming, Sequence):
            for item in reversed(list(incoming)):
                text = self._user_text(item)
                if text:
                    return text
            return ""

        return str(incoming or "").strip()

    def _user_text(self, item: Any) -> str:
        if isinstance(item, str):
            return item.strip()

        if not isinstance(item, Mapping):
            return ""

        role = item.get("role")
        if role is not None and str(role) != self.USER_ROLE:
            return ""

        return self._content_text(item.get("content", item.get("text")))

    def _content_text(self, content: Any) -> str:
        if isinstance(content, str):
            return content.strip()

        if isinstance(content, Sequence):
            parts: list[str] = []
            for part in content:
                if isinstance(part, str):
                    parts.append(part)
                    continue
                if not isinstance(part, Mapping):
                    continue
                for key in self.TEXT_KEYS:
                    value = part.get(key)
                    if isinstance(value, str):
                        parts.append(value)
                        break
            return "\n".join(part for part in parts if part).strip()

        return ""


_input_reader = ConversationInputReader()


def _resolve_thread_id(payload: dict[str, Any]) -> str:
    """Resolve the LangGraph thread_id used to persist/resume this conversation."""

    headers = _REQUEST_HEADERS.get()
    conversation_header = headers.get("x-conversation-id")
    if isinstance(conversation_header, str) and conversation_header:
        logger.info("_resolve_thread_id: using X-Conversation-ID header thread_id=%r", conversation_header)
        return conversation_header

    metadata = payload.get("metadata") or {}
    thread_id = metadata.get("thread_id")
    if isinstance(thread_id, str) and thread_id:
        logger.info("_resolve_thread_id: X-Conversation-ID header missing; using metadata.thread_id=%r", thread_id)
        return thread_id

    fallback = str(payload["request_id"])
    logger.warning(
        "_resolve_thread_id: no X-Conversation-ID header and no metadata.thread_id; falling back to "
        "request_id=%r as thread_id. Every call without a stable conversation id starts a brand-new "
        "thread, so a pending tool approval can never be found on the next call.",
        fallback,
    )
    return fallback


def _turn_output(turn: AgentTurnResult) -> dict[str, Any]:
    output: dict[str, Any] = {
        "role": "assistant",
        "content": turn.output,
        "status": turn.status.value,
        "thread_id": turn.thread_id,
    }

    if turn.status is AgentTurnStatus.AWAITING_APPROVAL:
        output["pending_actions"] = [
            {
                "name": action.name,
                "arguments": action.arguments,
                "description": action.description,
            }
            for action in turn.pending_actions
        ]

    return output


async def solution_architect_entrypoint(payload: dict[str, Any]) -> dict[str, Any]:
    thread_id = _resolve_thread_id(payload)
    user_input = _input_reader.latest_user_text(payload)
    logger.info(
        "solution_architect_entrypoint: request_id=%r thread_id=%r extracted_input=%r",
        payload.get("request_id"),
        thread_id,
        user_input[:200],
    )

    turn = await run_solution_architect_agent(thread_id=thread_id, user_input=user_input)
    logger.info(
        "solution_architect_entrypoint: request_id=%r thread_id=%r turn.status=%s turn.thread_id=%r",
        payload.get("request_id"),
        thread_id,
        turn.status.value,
        turn.thread_id,
    )

    return {
        "request_id": payload["request_id"],
        "status": "success",
        "output": _turn_output(turn),
        "metadata": {
            "route_key": payload["route_key"],
            "thread_id": turn.thread_id,
            "conversation_id": turn.thread_id,
        },
    }


add_ai_endpoints(
    app,
    solution_architect_entrypoint,
    default_route_key=AGENT_ID,
    enable_openai_responses=True,
    enable_openai_chat_completions=True,
    enable_anthropic_messages=False,
    descriptor_registry=DescriptorRegistry([agent_descriptor]),
    discovery=DiscoveryConfiguration(enable_openai_models=True, enable_anthropic_models=True),
)
