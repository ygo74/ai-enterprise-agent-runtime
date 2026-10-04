import asyncio
from typing import Literal

import pytest
from langchain_core.language_models.fake_chat_models import FakeListChatModel
from langchain_core.messages import (
    AIMessage,
    AIMessageChunk,
    BaseMessage,
    HumanMessage,
    ToolMessage,
)
from langchain_core.messages.ai import UsageMetadata
from langchain_core.messages.content import Citation
from langchain_core.outputs import ChatGeneration, ChatResult, LLMResult
from langchain_core.runnables.schema import EventData, StandardStreamEvent
from ygo74.agent_runtime.domains.contracts.agent_output import (
    AudioContent,
    ImageContent,
    Notification,
    ReasoningContent,
    Termination,
    TerminationStatus,
    TextContent,
    TokenUsage,
    ToolCallContent,
    ToolExecution,
    ToolResultContent,
    UrlCitation,
)
from ygo74.agent_runtime.domains.contracts.error_envelope import ErrorEnvelope
from ygo74.agent_runtime.domains.contracts.media_content import (
    AudioFormat,
    EncodedMedia,
    MediaUri,
)
from ygo74.agent_runtime.domains.contracts.stream_events import (
    AgentStreamEvent,
    ContentEnd,
    ContentEvent,
    ContentStart,
    TerminalEvent,
    TextDelta,
    ToolArgumentsDelta,
    UsageEvent,
)
from ygo74.agent_runtime.domains.mapping.output_normalizer import OutputNormalizer
from ygo74.agent_runtime.integrations.langchain import (
    ConversionStatus,
    LangChainConversionError,
    LangChainResultAdapter,
    LangChainStreamAdapter,
)


def event(
    kind: str,
    *,
    run_id: str = "model-run",
    chunk: AIMessageChunk | None = None,
    output: AIMessage | ToolMessage | str | None = None,
    parents: tuple[str, ...] = ("root",),
) -> StandardStreamEvent:
    data: EventData = {}
    if chunk is not None:
        data["chunk"] = chunk
    if output is not None:
        data["output"] = output
    return StandardStreamEvent(
        event=kind, name="model", run_id=run_id, parent_ids=parents, data=data,
    )


def test_final_result_uses_sdk_messages_tools_usage_and_explicit_reasoning() -> None:
    message = AIMessage(
        content_blocks=[
            {"type": "text", "text": "Answer"},
            {"type": "reasoning", "reasoning": "Publishable summary"},
        ],
        tool_calls=[{"id": "call-1", "name": "lookup", "args": {"q": "x"}}],
        usage_metadata={"input_tokens": 4, "output_tokens": 6, "total_tokens": 10},
    )
    adapter = LangChainResultAdapter()
    conversion = adapter.convert(message)
    assert conversion.status is ConversionStatus.CONVERTED
    assert conversion.output is not None
    assert conversion.output.contents == (
        TextContent("Answer"),
        ToolCallContent("call-1", "lookup", {"q": "x"}, ToolExecution.INTERNAL),
    )
    assert conversion.output.usage is not None
    assert conversion.output.usage.total_tokens == 10
    assert conversion.diagnostics[0].code == "reasoning_not_selected"
    selected = LangChainResultAdapter(expose_reasoning=True, tool_execution=ToolExecution.CLIENT)
    exposed = selected.convert(message).output
    assert exposed is not None
    assert ReasoningContent("Publishable summary", exposable=True) in exposed.contents


def test_result_generations_and_tool_message_are_real_sdk_types() -> None:
    adapter = LangChainResultAdapter()
    generation = ChatGeneration(message=AIMessage(content="done"), generation_info={"finish_reason": "length"})
    for result in (generation, ChatResult(generations=[generation]), LLMResult(generations=[[generation]])):
        converted = adapter.convert(result)
        assert converted.output is not None
        assert converted.output.contents == (TextContent("done"),)
        assert converted.output.termination.status is TerminationStatus.INCOMPLETE
    tool = ToolMessage(content="found", tool_call_id="call-1", name="lookup", artifact={"secret": "private"})
    converted_tool = adapter.convert(tool).output
    assert converted_tool is not None
    assert converted_tool.contents == (
        ToolResultContent("call-1", "lookup", "found", ToolExecution.INTERNAL),
    )
    assert adapter.convert(HumanMessage(content="not output")).status is ConversionStatus.EXCLUDED
    assert adapter.convert(LLMResult(generations=[[generation], [generation]])).status is ConversionStatus.UNSUPPORTED


@pytest.mark.parametrize("generation_metadata", [False, True])
def test_content_filter_is_incomplete_for_final_messages_and_generations(generation_metadata: bool) -> None:
    message = AIMessage(content="partial", response_metadata={"finish_reason": "content_filter"})
    native: AIMessage | ChatGeneration = message
    if generation_metadata:
        native = ChatGeneration(
            message=AIMessage(content="partial"), generation_info={"finish_reason": "content_filter"},
        )
    mapped = LangChainResultAdapter().convert(native)
    assert mapped.output is not None
    assert mapped.output.termination == Termination(TerminationStatus.INCOMPLETE, "content_filter")


@pytest.mark.parametrize("chunk_snapshot", [False, True])
@pytest.mark.parametrize("root", [False, True])
def test_content_filter_is_incomplete_for_stream_snapshots(chunk_snapshot: bool, root: bool) -> None:
    adapter = LangChainStreamAdapter()
    adapter.convert_chunk(AIMessageChunk(content="partial"), run_id="model-run")
    snapshot_type = AIMessageChunk if chunk_snapshot else AIMessage
    snapshot = snapshot_type(content="partial", response_metadata={"finish_reason": "content_filter"})
    mapped = adapter.convert(event(
        "on_chat_model_end", output=snapshot, parents=() if root else ("root",),
    ))
    events = mapped.events + adapter.finish().events
    terminals = tuple(item for item in events if isinstance(item, TerminalEvent))
    assert terminals == (TerminalEvent(Termination(TerminationStatus.INCOMPLETE, "content_filter")),)


def test_typed_media_and_unknown_blocks_are_inspectable_without_downloading() -> None:
    converted = LangChainResultAdapter().convert(AIMessage(content_blocks=[
        {"type": "image", "url": "https://example.invalid/picture.png", "mime_type": "image/png"},
        {"type": "audio", "id": "audio-1", "base64": "YQ==", "mime_type": "audio/mpeg"},
        {"type": "file", "file_id": "private-provider-id"},
    ]))
    assert converted.status is ConversionStatus.UNSUPPORTED
    assert converted.output is not None
    assert converted.output.contents == (
        ImageContent(MediaUri("https://example.invalid/picture.png", "image/png")),
        AudioContent(EncodedMedia("YQ==", "audio/mpeg"), "audio-1", format=AudioFormat.MP3),
    )
    assert converted.diagnostics[0].code == "unsupported_content"
    assert "private-provider-id" not in repr(converted.diagnostics)


def test_stream_chunks_snapshot_usage_and_root_termination_do_not_duplicate() -> None:
    adapter = LangChainStreamAdapter()
    first = adapter.convert(event("on_chat_model_stream", chunk=AIMessageChunk(content="hel", id="answer")))
    second = adapter.convert(event("on_chat_model_stream", chunk=AIMessageChunk(content="lo", id="answer")))
    assert first.events == (ContentStart("model-run:text:0", TextContent("")), TextDelta("model-run:text:0", "hel"))
    assert second.events == (TextDelta("model-run:text:0", "lo"),)
    ended = adapter.convert(event("on_chat_model_end", output=AIMessage(
        content="hello", usage_metadata={"input_tokens": 1, "output_tokens": 2, "total_tokens": 3},
    )))
    assert isinstance(ended.events[0], UsageEvent)
    assert ended.events == (
        UsageEvent(ended.events[0].usage), ContentEnd("model-run:text:0"),
    )
    assert adapter.convert(event("on_chain_end", parents=())).events == (TerminalEvent(),)
    assert adapter.convert(event("on_chain_end", parents=())).status is ConversionStatus.EXCLUDED


def test_tool_argument_chunks_are_correlated_and_never_parsed_early() -> None:
    adapter = LangChainStreamAdapter()
    first = adapter.convert(event("on_chat_model_stream", chunk=AIMessageChunk(
        content="", tool_call_chunks=[{"id": "one", "name": "lookup", "args": '{"q":', "index": 0}],
    )))
    second = adapter.convert(event("on_chat_model_stream", chunk=AIMessageChunk(
        content="", tool_call_chunks=[
            {"id": "two", "name": "lookup", "args": '{"q":"b"}', "index": 1},
            {"id": None, "name": None, "args": '"a"}', "index": 0},
        ],
    )))
    assert first.events == (
        ContentStart("model-run:tool:0", ToolCallContent("one", "lookup", execution=ToolExecution.INTERNAL)),
        ToolArgumentsDelta("model-run:tool:0", '{"q":'),
    )
    assert second.events[-1] == ToolArgumentsDelta("model-run:tool:0", '"a"}')
    assert isinstance(second.events[0], ContentStart)
    assert isinstance(second.events[0].content, ToolCallContent)
    assert second.events[0].content.call_id == "two"
    end = adapter.convert(event("on_chat_model_end", output=AIMessage(content="")))
    assert end.events == (ContentEnd("model-run:tool:0"), ContentEnd("model-run:tool:1"))


def test_unknown_events_and_developer_notifications_are_explicit() -> None:
    adapter = LangChainStreamAdapter()
    unknown = adapter.convert(event("on_provider_surprise"))
    assert unknown.status is ConversionStatus.UNSUPPORTED
    assert unknown.events == ()
    assert unknown.diagnostics[0].code == "unsupported_event"
    assert adapter.convert(event("on_chain_start")).status is ConversionStatus.EXCLUDED
    assert adapter.notification("progress", content_id="notice-1").events == (
        ContentEvent("notice-1", Notification("progress")),
    )


def test_real_offline_astream_events_closes_blocks_and_has_one_terminal() -> None:
    async def collect() -> tuple[AgentStreamEvent, ...]:
        model = FakeListChatModel(responses=["hello"])
        adapter = LangChainStreamAdapter()
        mapped: list[AgentStreamEvent] = []
        async for native in model.astream_events("question", version="v2"):
            converted = adapter.convert(native)
            assert converted.status is not ConversionStatus.UNSUPPORTED
            mapped.extend(converted.events)
        return tuple(mapped)

    mapped = asyncio.run(collect())
    assert "".join(item.text for item in mapped if isinstance(item, TextDelta)) == "hello"
    assert sum(isinstance(item, ContentStart) for item in mapped) == 1
    assert sum(isinstance(item, ContentEnd) for item in mapped) == 1
    assert sum(isinstance(item, TerminalEvent) for item in mapped) == 1


def test_delayed_tool_metadata_invalid_lifecycle_and_explicit_failure() -> None:
    adapter = LangChainStreamAdapter()
    delayed = AIMessageChunk(content="", tool_call_chunks=[
        {"id": None, "name": None, "args": '{"x":', "index": 0},
    ])
    assert adapter.convert_chunk(delayed, run_id="a").events == ()
    with pytest.raises(LangChainConversionError, match="identity"):
        adapter.finish()
    ready = AIMessageChunk(content="", tool_call_chunks=[
        {"id": "call", "name": "lookup", "args": "1}", "index": 0},
    ])
    converted = adapter.convert_chunk(ready, run_id="a")
    assert converted.events[1:] == (
        ToolArgumentsDelta("a:tool:0", '{"x":'), ToolArgumentsDelta("a:tool:0", "1}"),
    )
    adapter.convert(event("on_chat_model_end", run_id="a", output=AIMessage(content="")))
    with pytest.raises(LangChainConversionError, match="completed"):
        adapter.convert_chunk(AIMessageChunk(content="late"), run_id="a")


def test_usage_is_cumulative_across_model_runs_not_double_counted_from_snapshots() -> None:
    adapter = LangChainStreamAdapter()
    for run_id in ("first", "second"):
        chunk = AIMessageChunk(content="a", usage_metadata={
            "input_tokens": 2, "output_tokens": 1, "total_tokens": 3,
        })
        mapped = adapter.convert_chunk(chunk, run_id=run_id)
        usages = tuple(item.usage for item in mapped.events if isinstance(item, UsageEvent))
        expected = 3 if run_id == "first" else 6
        assert len(usages) == 1
        assert usages[0].total_tokens == expected
        closed = adapter.convert(event("on_chat_model_end", run_id=run_id, output=AIMessage(
            content="a", usage_metadata=chunk.usage_metadata,
        )))
        assert not any(isinstance(item, (TextDelta, UsageEvent)) for item in closed.events)


@pytest.mark.parametrize(("metadata", "expected"), [
    (
        UsageMetadata(
            input_tokens=10, output_tokens=6, total_tokens=19,
            input_token_details={"cache_read": 2, "cache_creation": 3}, output_token_details={"reasoning": 3},
        ),
        TokenUsage(10, 6, 19, cached_input_tokens=2, reasoning_output_tokens=3, cache_write_input_tokens=3),
    ),
    (
        UsageMetadata(
            input_tokens=10, output_tokens=6, total_tokens=16,
            input_token_details={"cache_read": 0, "cache_creation": 0}, output_token_details={"reasoning": 0},
        ),
        TokenUsage(10, 6, 16, cached_input_tokens=0, reasoning_output_tokens=0, cache_write_input_tokens=0),
    ),
    (
        UsageMetadata(input_tokens=10, output_tokens=6, total_tokens=16),
        TokenUsage(10, 6, 16),
    ),
    (
        UsageMetadata(
            input_tokens=10, output_tokens=6, total_tokens=16, input_token_details={"cache_read": 2},
        ),
        TokenUsage(10, 6, 16, cached_input_tokens=2),
    ),
    (
        UsageMetadata(
            input_tokens=10, output_tokens=6, total_tokens=16, output_token_details={"reasoning": 3},
        ),
        TokenUsage(10, 6, 16, reasoning_output_tokens=3),
    ),
    (
        UsageMetadata(
            input_tokens=10, output_tokens=6, total_tokens=16,
            input_token_details={"cache_creation": 4, "audio": 1}, output_token_details={"audio": 2},
        ),
        TokenUsage(10, 6, 16, cache_write_input_tokens=4),
    ),
    (
        UsageMetadata(
            input_tokens=10, output_tokens=6, total_tokens=16,
            input_token_details={"audio": 1}, output_token_details={"audio": 2},
        ),
        TokenUsage(10, 6, 16),
    ),
])
def test_final_usage_details_preserve_genuine_sdk_fields_and_unknowns(
    metadata: UsageMetadata, expected: TokenUsage,
) -> None:
    message = AIMessage(content="done", usage_metadata=metadata)
    for native in (message, ChatGeneration(message=message)):
        mapped = LangChainResultAdapter().convert(native)
        assert mapped.output is not None
        assert mapped.output.usage == expected
        assert OutputNormalizer().normalize(mapped.output) is mapped.output
    streamed = LangChainStreamAdapter().convert(event("on_chat_model_end", output=message))
    usages = tuple(item.usage for item in streamed.events if isinstance(item, UsageEvent))
    assert usages == (expected,)
    OutputNormalizer().validate_usage(usages[0])


@pytest.mark.parametrize("snapshot", [False, True])
def test_genuine_usage_precedes_visible_content_from_the_same_sdk_update(snapshot: bool) -> None:
    metadata = UsageMetadata(
        input_tokens=4, output_tokens=2, total_tokens=6,
        input_token_details={"cache_read": 1, "cache_creation": 1}, output_token_details={"reasoning": 1},
    )
    adapter = LangChainStreamAdapter()
    if snapshot:
        mapped = adapter.convert(event("on_chat_model_end", output=AIMessage(
            content="hello", usage_metadata=metadata,
        )))
    else:
        mapped = adapter.convert_chunk(AIMessageChunk(content="hello", usage_metadata=metadata), run_id="r")
    assert isinstance(mapped.events[0], UsageEvent)
    assert mapped.events[0].usage == TokenUsage(
        4, 2, 6, cached_input_tokens=1, reasoning_output_tokens=1, cache_write_input_tokens=1,
    )
    assert any(isinstance(item, (ContentStart, ContentEvent)) for item in mapped.events[1:])


def test_stream_usage_details_accumulate_per_run_and_across_runs_without_snapshot_double_counting() -> None:
    adapter = LangChainStreamAdapter()
    for metadata, expected in (
        (
            UsageMetadata(
                input_tokens=10, output_tokens=6, total_tokens=16,
                input_token_details={"cache_read": 2, "cache_creation": 3}, output_token_details={"reasoning": 3},
            ),
            TokenUsage(10, 6, 16, cached_input_tokens=2, reasoning_output_tokens=3, cache_write_input_tokens=3),
        ),
        (
            UsageMetadata(
                input_tokens=4, output_tokens=2, total_tokens=6,
                input_token_details={"cache_read": 1, "cache_creation": 1}, output_token_details={"reasoning": 1},
            ),
            TokenUsage(14, 8, 22, cached_input_tokens=3, reasoning_output_tokens=4, cache_write_input_tokens=4),
        ),
    ):
        mapped = adapter.convert_chunk(AIMessageChunk(content="", usage_metadata=metadata), run_id="first")
        assert mapped.events == (UsageEvent(expected),)
        OutputNormalizer().validate_usage(expected)
    final_metadata = UsageMetadata(
        input_tokens=14, output_tokens=8, total_tokens=22,
        input_token_details={"cache_read": 3, "cache_creation": 4}, output_token_details={"reasoning": 4},
    )
    closed = adapter.convert(event("on_chat_model_end", run_id="first", output=AIMessage(
        content="", usage_metadata=final_metadata,
    )))
    assert not any(isinstance(item, UsageEvent) for item in closed.events)
    another = adapter.convert_chunk(AIMessageChunk(content="", usage_metadata={
        "input_tokens": 8, "output_tokens": 4, "total_tokens": 12,
        "input_token_details": {"cache_read": 4, "cache_creation": 2}, "output_token_details": {"reasoning": 2},
    }), run_id="second")
    assert another.events == (
        UsageEvent(TokenUsage(22, 12, 34, cached_input_tokens=7, reasoning_output_tokens=6, cache_write_input_tokens=6)),
    )


def test_missing_chunk_usage_detail_stays_unknown_until_genuine_final_snapshot() -> None:
    adapter = LangChainStreamAdapter()
    adapter.convert_chunk(AIMessageChunk(content="", usage_metadata={
        "input_tokens": 10, "output_tokens": 6, "total_tokens": 16,
        "input_token_details": {"cache_read": 2, "cache_creation": 3}, "output_token_details": {"reasoning": 3},
    }), run_id="r")
    partial = adapter.convert_chunk(AIMessageChunk(content="", usage_metadata={
        "input_tokens": 4, "output_tokens": 2, "total_tokens": 6,
        "output_token_details": {"reasoning": 1},
    }), run_id="r")
    assert partial.events == (UsageEvent(TokenUsage(14, 8, 22, reasoning_output_tokens=4)),)
    final = adapter.convert(event("on_chat_model_end", run_id="r", output=AIMessage(content="", usage_metadata={
        "input_tokens": 14, "output_tokens": 8, "total_tokens": 22,
        "input_token_details": {"cache_read": 3, "cache_creation": 4}, "output_token_details": {"reasoning": 4},
    })))
    assert final.events == (
        UsageEvent(TokenUsage(14, 8, 22, cached_input_tokens=3, reasoning_output_tokens=4, cache_write_input_tokens=4)),
    )


@pytest.mark.parametrize("unknown_first", [False, True])
def test_missing_run_usage_details_never_become_fabricated_zero(unknown_first: bool) -> None:
    adapter = LangChainStreamAdapter()
    known = UsageMetadata(
        input_tokens=2, output_tokens=3, total_tokens=5,
        input_token_details={"cache_read": 0, "cache_creation": 0}, output_token_details={"reasoning": 0},
    )
    unknown = UsageMetadata(input_tokens=2, output_tokens=3, total_tokens=5)
    for index, metadata in enumerate((unknown, known) if unknown_first else (known, unknown)):
        mapped = adapter.convert_chunk(AIMessageChunk(content="", usage_metadata=metadata), run_id=f"r-{index}")
    assert mapped.events == (UsageEvent(TokenUsage(4, 6, 10)),)


def test_absent_sdk_usage_never_creates_totals_or_detail_counters() -> None:
    message = AIMessage(content="answer")
    mapped = LangChainResultAdapter().convert(message)
    assert mapped.output is not None
    assert mapped.output.usage is None
    adapter = LangChainStreamAdapter()
    chunk = adapter.convert_chunk(AIMessageChunk(content="answer"), run_id="model-run")
    snapshot = adapter.convert(event("on_chat_model_end", output=message))
    assert not any(isinstance(item, UsageEvent) for item in chunk.events + snapshot.events + adapter.finish().events)


def test_tool_execution_observations_use_sdk_run_identity_or_developer_call_id() -> None:
    from langchain_core.tools import tool

    @tool
    def lookup(q: str) -> str:
        """Return a local fixture without external access."""
        return q.upper()

    async def collect() -> tuple[AgentStreamEvent, ...]:
        adapter = LangChainStreamAdapter(tool_execution=ToolExecution.CLIENT)
        mapped: list[AgentStreamEvent] = []
        async for native in lookup.astream_events({"q": "local"}, version="v2"):
            converted = adapter.convert(native, tool_call_id="call-1")
            assert converted.status is ConversionStatus.CONVERTED
            mapped.extend(converted.events)
        return tuple(mapped)

    mapped = asyncio.run(collect())
    assert isinstance(mapped[0], ContentEvent)
    assert isinstance(mapped[1], ContentEvent)
    assert mapped[0].content == ToolCallContent("call-1", "lookup", {"q": "local"}, ToolExecution.INTERNAL)
    assert mapped[1].content == ToolResultContent("call-1", "lookup", "LOCAL", ToolExecution.INTERNAL)
    assert isinstance(mapped[2], TerminalEvent)


def test_final_snapshot_after_stream_exposes_only_new_media_and_not_replayed_text() -> None:
    adapter = LangChainStreamAdapter()
    adapter.convert_chunk(AIMessageChunk(content="hello"), run_id="model-run")
    mapped = adapter.convert(event("on_chat_model_end", output=AIMessage(content_blocks=[
        {"type": "text", "text": "hello"},
        {"type": "image", "base64": "YQ==", "mime_type": "image/png"},
        {"type": "audio", "id": "a", "url": "https://example.invalid/audio", "mime_type": "audio/wav"},
    ])))
    assert mapped.status is ConversionStatus.CONVERTED
    assert len(mapped.events) == 3
    assert isinstance(mapped.events[1], ContentEvent)
    assert isinstance(mapped.events[2], ContentEvent)
    assert mapped.events[1].content == ImageContent(EncodedMedia("YQ==", "image/png"))
    assert mapped.events[2].content == AudioContent(
        MediaUri("https://example.invalid/audio", "audio/wav"), "a", format=AudioFormat.WAV,
    )


def test_reasoning_streaming_requires_selection_and_uses_its_own_identity() -> None:
    chunk = AIMessageChunk(content=[
        {"type": "reasoning", "reasoning": "summary", "index": 0},
        {"type": "text", "text": "answer", "index": 1},
    ])
    hidden = LangChainStreamAdapter().convert_chunk(chunk, run_id="r")
    assert not any(isinstance(item, ContentStart) and isinstance(item.content, ReasoningContent) for item in hidden.events)
    selected = LangChainStreamAdapter(expose_reasoning=True).convert_chunk(chunk, run_id="r")
    assert selected.events[0] == ContentStart("r:reasoning:0", ReasoningContent("", exposable=True))
    assert selected.events[1] == TextDelta("r:reasoning:0", "summary")
    assert selected.events[2] == ContentStart("r:text:1", TextContent(""))


def test_protected_media_and_arbitrary_objects_are_not_guessed_or_leaked() -> None:
    result = LangChainResultAdapter().convert(AIMessage(content_blocks=[
        {"type": "audio", "base64": "YQ==", "mime_type": "audio/pcm"},
        {"type": "image", "url": "https://secret.invalid"},
        {"type": "reasoning", "extras": {"encrypted": "private"}},
    ]))
    assert result.status is ConversionStatus.UNSUPPORTED
    assert result.output is not None
    assert result.output.contents == ()
    assert "secret" not in repr(result.diagnostics)
    assert "private" not in repr(result.diagnostics)
    invalid = ToolMessage(content="data", tool_call_id="c", name="lookup")
    invalid.content = [{"type": "text", "text": float("nan")}]
    with pytest.raises(LangChainConversionError, match="JSON"):
        LangChainResultAdapter().convert(invalid)


def test_explicit_failure_is_terminal_even_when_tool_metadata_is_incomplete() -> None:
    adapter = LangChainStreamAdapter()
    adapter.convert_chunk(AIMessageChunk(content="a"), run_id="r")
    adapter.convert_chunk(AIMessageChunk(content="", tool_call_chunks=[
        {"id": None, "name": None, "args": "{", "index": 0},
    ]), run_id="r")
    error = ErrorEnvelope("agent_failed", "handler_execution", "Agent failed.")
    failure = Termination(TerminationStatus.FAILED, error=error)
    mapped = adapter.finish(failure)
    assert mapped.events == (ContentEnd("r:text:0"), TerminalEvent(failure))
    assert adapter.finish().status is ConversionStatus.EXCLUDED


def test_server_tools_stay_internal_and_unknown_custom_events_remain_developer_owned() -> None:
    from langchain_core.runnables.schema import CustomStreamEvent

    output = LangChainResultAdapter(tool_execution=ToolExecution.CLIENT).convert(AIMessage(content_blocks=[
        {"type": "server_tool_call", "id": "server-1", "name": "search", "args": {"q": "a"}},
        {"type": "server_tool_result", "tool_call_id": "server-1", "status": "success", "output": ["b"]},
    ]))
    assert output.output is not None
    assert output.output.contents == (
        ToolCallContent("server-1", "search", {"q": "a"}, ToolExecution.INTERNAL),
        ToolResultContent("server-1", "search", ["b"], ToolExecution.INTERNAL),
    )
    assert OutputNormalizer().normalize(output.output) is output.output
    native = CustomStreamEvent(
        event="on_custom_event", name="progress", run_id="r", parent_ids=[],
        data={"message": "developer selected"},
    )
    adapter = LangChainStreamAdapter()
    assert adapter.convert(native).status is ConversionStatus.UNSUPPORTED
    selected = adapter.notification(native["data"]["message"], content_id="notice")
    assert isinstance(selected.events[0], ContentEvent)


def test_server_tool_chunks_stay_internal_and_final_calls_are_not_duplicated() -> None:
    adapter = LangChainStreamAdapter(tool_execution=ToolExecution.CLIENT)
    chunk = AIMessageChunk(content=[
        {"type": "server_tool_call_chunk", "id": "server-1", "name": "search", "args": '{"q":', "index": 0},
    ])
    first = adapter.convert_chunk(chunk, run_id="r")
    assert first.events == (
        ContentStart("r:server_tool:0", ToolCallContent("server-1", "search", execution=ToolExecution.INTERNAL)),
        ToolArgumentsDelta("r:server_tool:0", '{"q":'),
    )
    second = adapter.convert_chunk(AIMessageChunk(content=[
        {"type": "server_tool_call_chunk", "args": '"a"}', "index": 0},
    ]), run_id="r")
    assert second.events == (ToolArgumentsDelta("r:server_tool:0", '"a"}'),)
    final = adapter.convert(event("on_chat_model_end", run_id="r", output=AIMessage(content_blocks=[
        {"type": "server_tool_call", "id": "server-1", "name": "search", "args": {"q": "a"}},
    ])))
    assert final.events == (ContentEnd("r:server_tool:0"),)


def test_genuine_sdk_url_citations_preserve_fields_without_inventing_missing_offsets() -> None:
    native = AIMessage(content_blocks=[{
        "type": "text", "text": "hello",
        "annotations": [
            {"type": "citation", "url": "https://example.invalid", "title": "Source", "start_index": 0, "end_index": 5},
            {"type": "citation", "url": "https://private.invalid", "title": "Missing offsets"},
        ],
    }])
    mapped = LangChainResultAdapter().convert(native)
    assert mapped.output is not None
    assert mapped.output.contents == (
        TextContent("hello", (UrlCitation("https://example.invalid", "Source", 0, 5),)),
    )
    assert mapped.status is ConversionStatus.UNSUPPORTED
    assert mapped.diagnostics[0].code == "unsupported_citation"
    assert "private.invalid" not in repr(mapped.diagnostics)


def test_stream_citations_known_at_start_are_preserved_and_late_annotations_are_inspectable() -> None:
    annotation: Citation = {
        "type": "citation", "url": "https://example.invalid", "title": "Source", "start_index": 0, "end_index": 5,
    }
    adapter = LangChainStreamAdapter()
    initial = adapter.convert_chunk(AIMessageChunk(content=[{
        "type": "text", "text": "hel", "annotations": [annotation],
    }]), run_id="r")
    assert initial.events[0] == ContentStart(
        "r:text:0", TextContent("", (UrlCitation("https://example.invalid", "Source", 0, 5),)),
    )
    adapter.convert_chunk(AIMessageChunk(content="lo"), run_id="r")
    completed = adapter.convert(event("on_chat_model_end", run_id="r", output=AIMessage(content_blocks=[{
        "type": "text", "text": "hello", "annotations": [annotation],
    }])))
    assert completed.status is ConversionStatus.CONVERTED
    assert completed.events == (ContentEnd("r:text:0"),)
    late = LangChainStreamAdapter()
    late.convert_chunk(AIMessageChunk(content="hello"), run_id="r")
    late_chunk = late.convert_chunk(AIMessageChunk(content=[{
        "type": "text", "text": "", "annotations": [annotation],
    }]), run_id="r")
    assert late_chunk.status is ConversionStatus.UNSUPPORTED
    assert late_chunk.events == ()
    snapshot = late.convert(event("on_chat_model_end", run_id="r", output=AIMessage(content_blocks=[{
        "type": "text", "text": "hello", "annotations": [annotation],
    }])))
    assert snapshot.status is ConversionStatus.UNSUPPORTED
    assert snapshot.events == (ContentEnd("r:text:0"),)
    assert snapshot.diagnostics[0].code == "late_citation"


@pytest.mark.parametrize("name", [None, "", " "])
def test_standalone_tool_message_without_genuine_name_is_explicitly_unsupported(name: str | None) -> None:
    mapped = LangChainResultAdapter().convert(ToolMessage(content="result", tool_call_id="call-1", name=name))
    assert mapped.status is ConversionStatus.UNSUPPORTED
    assert mapped.output is None
    assert mapped.diagnostics[0].code == "missing_tool_name"


@pytest.mark.parametrize("status", ["success", "error"])
def test_orphan_server_tool_result_never_emits_an_invalid_empty_name(status: Literal["success", "error"]) -> None:
    native = AIMessage(content_blocks=[{
        "type": "server_tool_result", "tool_call_id": "orphan", "status": status, "output": "result",
    }])
    mapped = LangChainResultAdapter().convert(native)
    assert mapped.status is ConversionStatus.UNSUPPORTED
    assert mapped.output is not None
    assert mapped.output.contents == ()
    assert mapped.diagnostics[0].code == "missing_tool_name"
    assert OutputNormalizer().normalize(mapped.output) is mapped.output
    streamed = LangChainStreamAdapter().convert(event("on_chat_model_end", output=native))
    assert streamed.status is ConversionStatus.UNSUPPORTED
    assert streamed.events == ()


def test_server_tool_result_recovers_genuine_name_from_correlated_stream_call() -> None:
    adapter = LangChainStreamAdapter()
    started = adapter.convert_chunk(AIMessageChunk(content=[{
        "type": "server_tool_call_chunk", "id": "server-1", "name": "search", "args": "{}", "index": 0,
    }]), run_id="r")
    for item in started.events:
        if isinstance(item, ContentStart):
            OutputNormalizer().validate_content(item.content)
    completed = adapter.convert(event("on_chat_model_end", run_id="r", output=AIMessage(content_blocks=[{
        "type": "server_tool_result", "tool_call_id": "server-1", "status": "success", "output": "found",
    }])))
    assert completed.status is ConversionStatus.CONVERTED
    assert completed.events == (
        ContentEnd("r:server_tool:0"),
        ContentEvent("r:final:0", ToolResultContent("server-1", "search", "found", ToolExecution.INTERNAL)),
    )
    for item in completed.events:
        if isinstance(item, ContentEvent):
            OutputNormalizer().validate_content(item.content)


@pytest.mark.parametrize("native", [
    AIMessage(content="text"),
    AIMessage(content_blocks=[{"type": "reasoning", "reasoning": "public summary"}]),
    AIMessage(content="calling", tool_calls=[{"id": "call-1", "name": "lookup", "args": {"q": "a"}}]),
    ToolMessage(content="found", tool_call_id="call-1", name="lookup"),
    ToolMessage(content="failed", tool_call_id="call-1", name="lookup", status="error"),
    ToolMessage(content="unnamed", tool_call_id="call-1"),
    AIMessage(content_blocks=[
        {"type": "server_tool_result", "tool_call_id": "server-1", "status": "success", "output": "found"},
        {"type": "server_tool_call", "id": "server-1", "name": "search", "args": {}},
    ]),
    AIMessage(content_blocks=[
        {"type": "image", "base64": "YQ==", "mime_type": "image/png"},
        {"type": "audio", "id": "a", "url": "https://example.invalid/audio", "mime_type": "audio/wav"},
    ]),
    AIMessage(content="hello", usage_metadata={"input_tokens": 2, "output_tokens": 3, "total_tokens": 5}),
    AIMessage(content_blocks=[{
        "type": "text", "text": "hello",
        "annotations": [{"type": "citation", "url": "https://example.invalid", "title": "Source", "start_index": 0, "end_index": 5}],
    }]),
])
def test_every_produced_final_output_is_accepted_by_core_normalizer(native: BaseMessage) -> None:
    mapped = LangChainResultAdapter(expose_reasoning=True).convert(native)
    if mapped.output is not None:
        assert OutputNormalizer().normalize(mapped.output) is mapped.output
    else:
        assert mapped.status is ConversionStatus.UNSUPPORTED
