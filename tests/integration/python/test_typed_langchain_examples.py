from __future__ import annotations

import asyncio
import importlib.util
import json
import sys
from collections.abc import AsyncIterator
from pathlib import Path
from types import ModuleType
from typing import Any

import httpx
import jwt
import pytest
from langchain_core.messages import AIMessage, AIMessageChunk, HumanMessage
from ygo74.agent_runtime.domains.contracts.agent_output import (
    AgentOutput,
    Notification,
    TextContent,
)
from ygo74.agent_runtime.domains.contracts.stream_events import (
    ContentEnd,
    ContentEvent,
    ContentStart,
    TerminalEvent,
    TextDelta,
)

EXAMPLES = Path(__file__).resolve().parents[3] / "docs" / "examples" / "python-langchain-fastapi"


class ExampleLoader:
    @staticmethod
    def load(folder: str, filename: str, monkeypatch: pytest.MonkeyPatch) -> ModuleType:
        directory = EXAMPLES / folder
        monkeypatch.syspath_prepend(str(directory))
        for name in ("env_loader", "mcp_mslearn_tool", "agent_solution_architect", "rag_agent",
                     "langgraph_approval", "solution_architect_agent"):
            monkeypatch.delitem(sys.modules, name, raising=False)
        name = f"typed_example_{folder.replace('-', '_')}_{Path(filename).stem}"
        spec = importlib.util.spec_from_file_location(name, directory / filename)
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        monkeypatch.setitem(sys.modules, name, module)
        spec.loader.exec_module(module)
        return module


class LocalRagFixture:
    async def answer(self, question: str) -> str:
        assert question == "latest question"
        return "Grounded answer [security.md].\n\nSources: security.md"

    async def stream(self, question: str) -> AsyncIterator[str]:
        assert question == "latest question"
        yield "Grounded answer [security.md]."
        yield "\n\nSources: security.md"


class ArchitectFixture:
    async def ainvoke(self, payload: dict[str, Any]) -> dict[str, Any]:
        return {"messages": [HumanMessage("question"), AIMessage("Final architect answer.")]}

    async def astream_events(
        self, payload: dict[str, Any], *, version: str,
    ) -> AsyncIterator[dict[str, Any]]:
        assert version == "v2"
        base = {"run_id": "model-1", "parent_ids": ["agent-1"], "name": "fixture",
                "tags": [], "metadata": {}}
        yield {**base, "event": "on_custom_event", "data": {"text": "Do not expose this."}}
        yield {**base, "event": "on_tool_start", "data": {"input": {"query": "architecture"}}}
        yield {**base, "event": "on_tool_end", "data": {"output": "private tool payload"}}
        yield {**base, "event": "on_chat_model_stream", "data": {"chunk": AIMessageChunk("Final ")}}
        yield {**base, "event": "on_chat_model_stream", "data": {"chunk": AIMessageChunk("answer.")}}
        yield {**base, "event": "on_chat_model_end", "data": {"output": AIMessage("Final answer.")}}
        yield {**base, "event": "on_chain_stream", "data": {"chunk": {"messages": [AIMessage("Final answer.")]}}}


class ClosingArchitectFixture(ArchitectFixture):
    def __init__(self) -> None:
        self.closed: bool = False

    async def astream_events(
        self, payload: dict[str, Any], *, version: str,
    ) -> AsyncIterator[dict[str, Any]]:
        try:
            async for event in super().astream_events(payload, version=version):
                yield event
        finally:
            self.closed = True


def test_architect_closes_native_producer_on_early_consumer_exit(monkeypatch: pytest.MonkeyPatch) -> None:
    example = ExampleLoader.load("01-get-started", "agent_solution_architect.py", monkeypatch)
    native = ClosingArchitectFixture()
    architect = example.SolutionArchitect(native, tool_notices=False)

    async def run() -> None:
        stream = architect.stream("question")
        assert isinstance(await anext(stream), ContentStart)
        await stream.aclose()
        assert native.closed

    asyncio.run(run())


@pytest.mark.parametrize("tool_notices", [True, False])
def test_architect_controls_native_event_selection_and_emits_typed_notices(
    tool_notices: bool, monkeypatch: pytest.MonkeyPatch,
) -> None:
    example = ExampleLoader.load("01-get-started", "agent_solution_architect.py", monkeypatch)
    architect = example.SolutionArchitect(ArchitectFixture(), tool_notices=tool_notices)

    async def run() -> None:
        result = await architect.run("question")
        assert result.contents == (TextContent("Final architect answer."),)
        events = [event async for event in architect.stream("question")]
        notices = [event.content for event in events if isinstance(event, ContentEvent)
                   and isinstance(event.content, Notification)]
        assert len(notices) == (2 if tool_notices else 0)
        if notices:
            assert "Calling tool" in notices[0].text
            assert "completed" in notices[1].text
        assert [event.text for event in events if isinstance(event, TextDelta)] == ["Final ", "answer."]
        assert sum(isinstance(event, TerminalEvent) for event in events) == 1
        assert isinstance(events[-1], TerminalEvent)

    asyncio.run(run())


def test_architect_fastapi_entrypoint_imports_and_converts_both_modes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    example = ExampleLoader.load("01-get-started", "openai_responses_app.py", monkeypatch)
    native = sys.modules["agent_solution_architect"]
    monkeypatch.setattr(native, "build_solution_architect_agent", lambda: ArchitectFixture())
    payload = {"input": "question"}

    async def run() -> None:
        output = await example.solution_architect_entrypoint(payload)
        assert output.contents == (TextContent("Final architect answer."),)
        events = [event async for event in example.solution_architect_entrypoint({**payload, "stream": True})]
        assert [event.text for event in events if isinstance(event, TextDelta)] == ["Final ", "answer."]
        assert isinstance(events[-1], TerminalEvent)

    asyncio.run(run())


def test_rag_host_wraps_text_and_preserves_sources_without_network(monkeypatch: pytest.MonkeyPatch) -> None:
    example = ExampleLoader.load("05-rag", "openai_rag_app.py", monkeypatch)
    application = example.RagApplication(EXAMPLES / "05-rag" / "knowledge_base")
    application._agent = LocalRagFixture()
    payload = {"input": [
        {"role": "assistant", "content": "ignore assistant history"},
        {"role": "user", "content": [{"type": "input_text", "text": "latest question"}]},
    ]}

    async def run() -> None:
        result = await application.entrypoint(payload)
        assert isinstance(result, AgentOutput)
        assert result.contents == (TextContent("Grounded answer [security.md].\n\nSources: security.md"),)
        events = [event async for event in application.entrypoint({**payload, "stream": True})]
        assert isinstance(events[0], ContentStart)
        assert [event.text for event in events if isinstance(event, TextDelta)] == [
            "Grounded answer [security.md].", "\n\nSources: security.md",
        ]
        assert isinstance(events[-2], ContentEnd)
        assert isinstance(events[-1], TerminalEvent)

    asyncio.run(run())


@pytest.mark.parametrize("folder", ["02-jwt-authentication", "03-jwt-oidc-keycloak"])
def test_jwt_handlers_preserve_verified_identity_in_typed_content(
    folder: str, monkeypatch: pytest.MonkeyPatch,
) -> None:
    example = ExampleLoader.load(folder, "openai_responses_jwt_app.py", monkeypatch)
    payload = {
        "input": "hello",
        "auth_context": {
            "identity": {"subject": "verified-subject", "email": "verified@example.com"},
            "roles": ["admin"], "groups": ["engineering"], "claims": {"sub": "verified-subject"},
        },
    }
    result = asyncio.run(example._entrypoint(payload))
    assert isinstance(result, AgentOutput)
    assert isinstance(result.contents[0], TextContent)
    record = json.loads(result.contents[0].text)
    assert record["subject"] == "verified-subject"
    assert record["claims"] == {"sub": "verified-subject"}
    assert record["input"] == "hello"
    if folder == "03-jwt-oidc-keycloak":
        assert record["roles"] == ["admin"]
        assert record["groups"] == ["engineering"]


def test_jwt_example_still_rejects_missing_credentials_and_accepts_verified_token(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    secret = "offline-test-key-at-least-32-bytes-long"
    monkeypatch.setenv("JWT_HS256_SECRET", secret)
    monkeypatch.setenv("JWT_ISSUER", "https://offline.example")
    monkeypatch.setenv("JWT_AUDIENCE", "offline")
    example = ExampleLoader.load("02-jwt-authentication", "openai_responses_jwt_app.py", monkeypatch)
    token = jwt.encode(
        {"sub": "alice", "exp": 4102444800, "nbf": 0, "iss": "https://offline.example", "aud": "offline"},
        secret, algorithm="HS256",
    )

    async def run() -> None:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=example.app), base_url="http://test",
        ) as client:
            body = {"model": "jwt-protected-agent", "input": "hello"}
            denied = await client.post("/v1/responses", json=body)
            assert denied.status_code == 401
            accepted = await client.post("/v1/responses", json=body, headers={"Authorization": f"Bearer {token}"})
            assert accepted.status_code == 200
            assert "alice" in accepted.text

    asyncio.run(run())


def test_hitl_output_keeps_verified_subject_and_confirmation_before_model(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    example = ExampleLoader.load("04-human-in-the-loop", "openai_responses_app.py", monkeypatch)
    seen: list[str] = []

    async def start(user: Any, message: str) -> str:
        seen.append(f"start:{user.user_id}:{message}")
        return "I need your approval."

    async def honour(user: Any, command: Any) -> str:
        seen.append(f"confirm:{user.user_id}:{command.ticket_id}")
        return "Approved."

    monkeypatch.setattr(example, "_start", start)
    monkeypatch.setattr(example, "_honour", honour)
    payload = {"auth_context": {"identity": {"subject": "verified-user"}}, "input": "research",
               "metadata": {"conversation_id": "thread"}}
    result = asyncio.run(example.entrypoint(payload))
    assert result.contents == (TextContent("I need your approval."),)
    result = asyncio.run(example.entrypoint({**payload, "input": "CONFIRM cfm-12345678"}))
    assert result.contents == (TextContent("Approved."),)
    assert seen == ["start:verified-user:research", "confirm:verified-user:cfm-12345678"]
