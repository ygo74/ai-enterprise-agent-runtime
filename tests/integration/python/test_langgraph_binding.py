"""Native LangGraph binding tests using deterministic graph fakes."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Mapping, Sequence
from types import SimpleNamespace
from typing import Any

import pytest
from langchain_core.messages import AIMessage, AIMessageChunk, HumanMessage, ToolMessage
from langchain_core.runnables.schema import EventData, StandardStreamEvent
from langgraph.types import Command
from ygo74.agent_runtime.domains.contracts.agent_output import (
    AgentOutput,
    TextContent,
    TokenUsage,
)
from ygo74.agent_runtime.domains.contracts.stream_events import (
    ContentStart,
    TerminalEvent,
    TextDelta,
    ToolArgumentsDelta,
    UsageEvent,
)
from ygo74.agent_runtime.integrations.langchain import (
    LangGraphApprovalDecision,
    LangGraphDecisionType,
    LangGraphPendingApproval,
    LangGraphSession,
)


def _event(
    name: str,
    *,
    run_id: str,
    event: str,
    data: EventData,
    parents: tuple[str, ...] = ("graph",),
) -> StandardStreamEvent:
    """Build one SDK event for a controlled graph stream."""
    return StandardStreamEvent(
        event=event,
        name=name,
        run_id=run_id,
        parent_ids=parents,
        data=data,
    )


class GraphFake:
    """Record graph inputs and return scripted states or event sequences."""

    def __init__(self, states: Sequence[object], events: Sequence[StandardStreamEvent] = ()) -> None:
        self.states = list(states)
        self.events = tuple(events)
        self.inputs: list[object] = []
        self.configs: list[Mapping[str, Any]] = []
        self.stream_inputs: list[object] = []

    async def ainvoke(self, value: object, *, config: Mapping[str, Any]) -> object:
        """Return the next scripted graph state and retain invocation metadata."""
        self.inputs.append(value)
        self.configs.append(config)
        return self.states.pop(0)

    async def astream_events(
        self,
        value: object,
        *,
        config: Mapping[str, Any],
        version: str,
    ) -> AsyncIterator[StandardStreamEvent]:
        """Yield the scripted graph events for one native stream call."""
        assert version == "v2"
        self.stream_inputs.append(value)
        self.configs.append(config)
        for item in self.events:
            yield item


class ResolverFake:
    """Resolve every pending tool call to a deterministic typed decision."""

    def __init__(self) -> None:
        self.batches: list[tuple[LangGraphPendingApproval, ...]] = []

    def will_question(self, pending: tuple[LangGraphPendingApproval, ...]) -> bool:
        """Treat each approval batch as a user question for budget coverage."""
        return True

    async def resolve(
        self,
        pending: tuple[LangGraphPendingApproval, ...],
    ) -> tuple[LangGraphApprovalDecision, ...]:
        """Approve the scripted calls in their original order."""
        self.batches.append(pending)
        return tuple(LangGraphApprovalDecision(LangGraphDecisionType.APPROVE) for _ in pending)


class RoundedGraphFake:
    """Serve a distinct scripted event sequence for each successive stream round."""

    def __init__(self, rounds: Sequence[Sequence[StandardStreamEvent]]) -> None:
        self._rounds = [list(round_events) for round_events in rounds]
        self.stream_inputs: list[object] = []
        self.configs: list[Mapping[str, Any]] = []

    async def astream_events(
        self,
        value: object,
        *,
        config: Mapping[str, Any],
        version: str,
    ) -> AsyncIterator[StandardStreamEvent]:
        """Yield the next scripted round, preserving call order for assertions."""
        assert version == "v2"
        self.stream_inputs.append(value)
        self.configs.append(config)
        for item in self._rounds.pop(0):
            yield item


@pytest.mark.asyncio
async def test_ask_output_uses_only_latest_text_and_extracts_assistant_usage() -> None:
    """Conversation state stays server-managed and output contains only the final assistant message."""
    graph = GraphFake([{
        "messages": [
            HumanMessage("previous turn"),
            AIMessage(content="previous answer"),
            HumanMessage("latest question"),
            AIMessage(
                content="current answer",
                usage_metadata={"input_tokens": 4, "output_tokens": 3, "total_tokens": 7},
            ),
        ],
    }])
    session = LangGraphSession(graph, thread_id="subject-conversation")

    output = await session.ask_output("latest question")

    assert output == AgentOutput(
        contents=(TextContent("current answer"),),
        usage=TokenUsage(4, 3, 7),
    )
    assert graph.inputs == [{"messages": [{"role": "user", "content": "latest question"}]}]
    assert graph.configs[0]["configurable"]["thread_id"] == "subject-conversation"


@pytest.mark.asyncio
async def test_ask_output_resolves_interruptions_with_ordered_commands() -> None:
    """Pending calls become typed approvals and are resumed without changing their order."""
    interrupt = SimpleNamespace(value={"action_requests": [
        {"name": "search", "args": {"query": "one"}},
        {"name": "read", "args": {"page_id": "two"}},
    ]})
    graph = GraphFake([
        {"messages": [HumanMessage("go")], "__interrupt__": [interrupt]},
        {"messages": [HumanMessage("go"), AIMessage(content="done")]},
    ])
    resolver = ResolverFake()
    session = LangGraphSession(graph, thread_id="t", resolver=resolver)

    output = await session.ask_output("go")

    assert tuple(call.tool_name for call in resolver.batches[0]) == ("search", "read")
    assert graph.inputs[1] == Command(resume={"decisions": [
        {"type": "approve"},
        {"type": "approve"},
    ]})
    assert output.contents == (TextContent("done"),)


@pytest.mark.asyncio
async def test_stream_runs_native_events_and_emits_one_terminal() -> None:
    """LangGraph streaming is translated from SDK events and terminates once."""
    final_state = {"messages": [
        HumanMessage("question"),
        AIMessage(content="hello", usage_metadata={
            "input_tokens": 2, "output_tokens": 1, "total_tokens": 3,
        }),
    ]}
    graph = GraphFake([], [
        _event("model", run_id="model-1", event="on_chat_model_stream",
               data={"chunk": AIMessageChunk(content="hel")}),
        _event("model", run_id="model-1", event="on_chat_model_stream",
               data={"chunk": AIMessageChunk(content="lo")}),
        _event("model", run_id="model-1", event="on_chat_model_end",
               data={"output": AIMessage(content="hello", usage_metadata={
                   "input_tokens": 2, "output_tokens": 1, "total_tokens": 3,
               })}),
        _event("graph", run_id="graph-1", event="on_chain_end", data={"output": final_state}, parents=()),
    ])
    session = LangGraphSession(graph, thread_id="t")

    events = [item async for item in session.ask_stream("question")]

    assert "".join(item.text for item in events if isinstance(item, TextDelta)) == "hello"
    assert sum(isinstance(item, ContentStart) for item in events) == 1
    assert sum(isinstance(item, UsageEvent) for item in events) == 1
    assert sum(isinstance(item, TerminalEvent) for item in events) == 1
    assert graph.stream_inputs == [{"messages": [{"role": "user", "content": "question"}]}]


@pytest.mark.asyncio
async def test_stream_suppresses_tool_arguments_and_results() -> None:
    """Internal tool calls and raw results are never exposed by the binding."""
    final_state = {"messages": [HumanMessage("q"), AIMessage(content="done")]}
    graph = GraphFake([], [
        _event("lookup", run_id="tool-1", event="on_tool_start", data={"input": {"secret": "x"}}),
        _event("lookup", run_id="tool-1", event="on_tool_end", data={"output": ToolMessage(
            content="private result", tool_call_id="call-1", name="lookup",
        )}),
        _event("graph", run_id="graph-1", event="on_chain_end", data={"output": final_state}, parents=()),
    ])
    session = LangGraphSession(graph, thread_id="t")

    events = [item async for item in session.ask_stream("q")]

    assert not any(isinstance(item, (ToolArgumentsDelta,)) for item in events)
    assert "secret" not in repr(events)
    assert "private result" not in repr(events)
    assert events[-1] == TerminalEvent()


@pytest.mark.asyncio
async def test_cancelled_stream_closes_graph_producer_and_invalidates_session() -> None:
    """Closing a consumer stops the native graph stream and prevents state reuse."""
    closed = False

    class PausedGraph(GraphFake):
        async def astream_events(
            self,
            value: object,
            *,
            config: Mapping[str, Any],
            version: str,
        ) -> AsyncIterator[StandardStreamEvent]:
            nonlocal closed
            try:
                yield _event("model", run_id="model-1", event="on_chat_model_stream",
                             data={"chunk": AIMessageChunk(content="partial")})
                await asyncio.Event().wait()
            finally:
                closed = True

    session = LangGraphSession(PausedGraph([]), thread_id="t")
    stream = session.ask_stream("q")
    await anext(stream)
    await stream.aclose()

    assert closed
    with pytest.raises(RuntimeError, match="invalidated"):
        await session.ask_output("next")


@pytest.mark.asyncio
async def test_ask_stream_resolves_streamed_interruption_and_keeps_history_valid() -> None:
    """A streamed interrupt is captured even though it is absent from on_chain_end.

    LangGraph only carries ``__interrupt__`` on an intermediate root
    ``on_chain_stream`` chunk; the terminal ``on_chain_end`` output for the
    suspended round never repeats it. The approval loop must still see the
    pending action so it resolves it before the turn completes, otherwise the
    next turn's prompt would contain an ``AIMessage.tool_calls`` entry with no
    matching ``ToolMessage`` response (invalid history, rejected by providers).
    """
    pending_state = {"messages": [
        HumanMessage("please act"),
        AIMessage(
            content="",
            tool_calls=[{"name": "search", "args": {"query": "one"}, "id": "call-1", "type": "tool_call"}],
        ),
    ]}
    interrupt = SimpleNamespace(value={"action_requests": [
        {"name": "search", "args": {"query": "one"}},
    ]})
    resumed_state = {"messages": [
        *pending_state["messages"],
        ToolMessage(content="ok", tool_call_id="call-1", name="search"),
        AIMessage(content="done"),
    ]}
    graph = RoundedGraphFake([
        [
            _event("model", run_id="model-1", event="on_chat_model_end",
                   data={"output": pending_state["messages"][-1]}),
            # Only the streamed chunk carries the interrupt; on_chain_end never does.
            _event("graph", run_id="graph-1", event="on_chain_stream",
                   data={"chunk": {"__interrupt__": (interrupt,)}}, parents=()),
            _event("graph", run_id="graph-1", event="on_chain_end",
                   data={"output": pending_state}, parents=()),
        ],
        [
            _event("model", run_id="model-2", event="on_chat_model_end",
                   data={"output": resumed_state["messages"][-1]}),
            _event("graph", run_id="graph-2", event="on_chain_end",
                   data={"output": resumed_state}, parents=()),
        ],
    ])
    resolver = ResolverFake()
    session = LangGraphSession(graph, thread_id="t", resolver=resolver)

    events = [item async for item in session.ask_stream("please act")]

    assert tuple(call.tool_name for call in resolver.batches[0]) == ("search",)
    assert graph.stream_inputs[1] == Command(resume={"decisions": [{"type": "approve"}]})
    assert sum(isinstance(item, TerminalEvent) for item in events) == 1
    final_messages = resumed_state["messages"]
    tool_call_ids = {call["id"] for call in final_messages[1].tool_calls}
    answered_ids = {
        message.tool_call_id for message in final_messages if isinstance(message, ToolMessage)
    }
    assert tool_call_ids == answered_ids


@pytest.mark.asyncio
async def test_ask_stream_without_interruption_still_terminates_once() -> None:
    """An ordinary ungated stream round is unaffected by interrupt capture."""
    final_state = {"messages": [HumanMessage("q"), AIMessage(content="hi")]}
    graph = GraphFake([], [
        _event("model", run_id="model-1", event="on_chat_model_end",
               data={"output": AIMessage(content="hi")}),
        _event("graph", run_id="graph-1", event="on_chain_end", data={"output": final_state}, parents=()),
    ])
    session = LangGraphSession(graph, thread_id="t")

    events = [item async for item in session.ask_stream("q")]

    assert sum(isinstance(item, TerminalEvent) for item in events) == 1


def test_pending_approval_requires_an_action_request_mapping() -> None:
    """Framework interrupt payloads are converted to safe typed approval values."""
    call = LangGraphPendingApproval({"name": "search", "args": {"query": "x"}})
    assert call.tool_name == "search"
    assert call.arguments == {"query": "x"}
