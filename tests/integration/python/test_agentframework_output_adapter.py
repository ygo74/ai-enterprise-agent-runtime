from __future__ import annotations

import pytest
from agent_framework import (
    AgentResponse,
    AgentResponseUpdate,
    Annotation,
    Content,
    Message,
    UsageDetails,
)
from ygo74.agent_runtime.domains.contracts.agent_output import (
    AudioContent,
    ImageContent,
    ReasoningContent,
    TerminationStatus,
    TextContent,
    ToolCallContent,
    ToolExecution,
    ToolResultContent,
)
from ygo74.agent_runtime.domains.contracts.media_content import EncodedMedia, MediaUri
from ygo74.agent_runtime.domains.contracts.stream_events import (
    ContentEnd,
    ContentEvent,
    ContentStart,
    TerminalEvent,
    TextDelta,
    ToolArgumentsDelta,
    UsageEvent,
)
from ygo74.agent_runtime.integrations.agentframework import (
    AgentFrameworkOutputAdapter,
    AgentFrameworkStreamAdapter,
    ConversionReason,
    ConversionStatus,
)


def test_agentframework_final_visits_every_message_and_content() -> None:
    response = AgentResponse(
        messages=[
            Message("assistant", [
                Content.from_text("first"),
                Content.from_function_call("call-1", "lookup", arguments={"query": "x"}),
            ]),
            Message("tool", [Content.from_function_result("call-1", result="found")]),
            Message("assistant", [
                Content.from_text("last"),
                Content.from_uri("https://example.test/image.png", media_type="image/png"),
                Content.from_data(b"wave", media_type="audio/wav"),
            ]),
        ],
        usage_details={"input_token_count": 2, "output_token_count": 3, "total_token_count": 5},
    )
    converted = AgentFrameworkOutputAdapter().convert(response)
    assert len(converted.output.contents) == 6
    first, call, result, last, image, audio = converted.output.contents
    assert first == TextContent("first")
    assert last == TextContent("last")
    assert isinstance(call, ToolCallContent) and call.execution is ToolExecution.INTERNAL
    assert isinstance(result, ToolResultContent) and result.name == "lookup"
    assert isinstance(image, ImageContent) and isinstance(image.source, MediaUri)
    assert isinstance(audio, AudioContent) and isinstance(audio.source, EncodedMedia)
    assert audio.source.data == "d2F2ZQ=="
    assert converted.output.usage is not None and converted.output.usage.total_tokens == 5


def test_agentframework_reasoning_requires_deliberate_opt_in_and_never_exposes_protected() -> None:
    response = AgentResponse(messages=Message("assistant", [
        Content.from_text_reasoning(text="publishable"),
        Content.from_text_reasoning(text="secret", protected_data="encrypted"),
        Content.from_hosted_file("file-private"),
        Content.from_text("answer"),
    ]))
    default = AgentFrameworkOutputAdapter().convert(response)
    assert default.output.contents == (TextContent("answer"),)
    assert [decision.status for decision in default.decisions] == [
        ConversionStatus.EXCLUDED, ConversionStatus.EXCLUDED,
        ConversionStatus.UNSUPPORTED, ConversionStatus.CONVERTED,
    ]
    opted_in = AgentFrameworkOutputAdapter(expose_reasoning=True).convert(response)
    assert opted_in.output.contents == (ReasoningContent("publishable", exposable=True), TextContent("answer"))
    assert "secret" not in repr(default.decisions) and "file-private" not in repr(default.decisions)


def test_agentframework_partial_and_unknown_usage_are_not_invented() -> None:
    converted = AgentFrameworkOutputAdapter().convert(AgentResponse(
        messages=Message("assistant", [Content.from_usage({"input_token_count": 2})]),
        finish_reason="length",
    ))
    assert converted.output.usage is None
    assert converted.output.termination.status is TerminationStatus.INCOMPLETE
    assert converted.decisions[0].status is ConversionStatus.UNSUPPORTED


def test_agentframework_stream_maps_all_contents_and_parallel_tool_fragments() -> None:
    adapter = AgentFrameworkStreamAdapter()
    first = adapter.convert_update(AgentResponseUpdate(message_id="message-1", contents=[
        Content.from_text("Hello"),
        Content.from_function_call("a", "alpha", arguments='{"a":'),
        Content.from_function_call("b", "beta", arguments='{"b":'),
    ]))
    second = adapter.convert_update(AgentResponseUpdate(message_id="message-1", contents=[
        Content.from_text(" world"),
        Content.from_function_call("b", "beta", arguments="2}"),
        Content.from_function_call("a", "alpha", arguments="1}"),
        Content.from_usage({"input_token_count": 1, "output_token_count": 2}),
    ], finish_reason="stop"))
    assert len([event for event in first.events if isinstance(event, ContentStart)]) == 3
    assert any(isinstance(event, TextDelta) and event.text == " world" for event in second.events)
    fragments = [event for event in second.events if isinstance(event, ToolArgumentsDelta)]
    assert len(fragments) == 2 and fragments[0].content_id != fragments[1].content_id
    assert any(isinstance(event, UsageEvent) for event in second.events)
    terminal = adapter.finish()
    assert len([event for event in terminal if isinstance(event, ContentEnd)]) == 3
    assert isinstance(terminal[-1], TerminalEvent)
    assert adapter.finish() == ()


def test_agentframework_unsupported_media_and_tool_result_are_inspectable() -> None:
    response = AgentResponse(messages=Message("assistant", [
        Content.from_uri("https://example.test/movie", media_type="video/mp4"),
        Content.from_function_result("unknown", result="result"),
    ]))
    converted = AgentFrameworkOutputAdapter().convert(response)
    assert converted.output.contents == ()
    assert all(decision.status is ConversionStatus.UNSUPPORTED for decision in converted.decisions)


def test_agentframework_stream_usage_matches_native_aggregation() -> None:
    updates = [
        AgentResponseUpdate(contents=[Content.from_usage({
            "input_token_count": 2, "output_token_count": 3, "total_token_count": 5,
        })]),
        AgentResponseUpdate(contents=[Content.from_usage({
            "input_token_count": 4, "output_token_count": 1, "total_token_count": 5,
        })]),
    ]
    adapter = AgentFrameworkStreamAdapter()
    adapter.convert_update(updates[0])
    converted = adapter.convert_update(updates[1])
    usage_event = converted.events[0]
    assert isinstance(usage_event, UsageEvent)
    native_final = AgentFrameworkOutputAdapter().convert(AgentResponse.from_updates(updates))
    assert usage_event.usage == native_final.output.usage


def test_agentframework_failures_remain_failed_and_stream_rejects_post_terminal() -> None:
    adapter = AgentFrameworkStreamAdapter()
    error_content = Content.from_error(
        message="failed", error_code="provider", error_details="private-provider-detail",
        raw_representation={"secret": "private-raw-payload"},
    )
    adapter.convert_update(AgentResponseUpdate(contents=[error_content]))
    adapter.convert_update(AgentResponseUpdate(finish_reason="stop"))
    terminal = adapter.finish()[-1]
    assert isinstance(terminal, TerminalEvent)
    assert terminal.termination.status is TerminationStatus.FAILED
    assert terminal.termination.error is not None
    assert terminal.termination.error.category == "handler_execution"
    assert terminal.termination.error.message == "failed"
    assert "private-provider-detail" not in repr(terminal)
    assert "private-raw-payload" not in repr(terminal)
    final = AgentFrameworkOutputAdapter().convert(
        AgentResponse(messages=Message("assistant", [error_content])),
    )
    assert final.output.termination.error is not None
    assert final.output.termination.error.category == "handler_execution"
    assert final.output.termination.error.details is None
    with pytest.raises(ValueError, match="after finish"):
        adapter.convert_update(AgentResponseUpdate(contents=[Content.from_text("late")]))


def test_agentframework_nested_tool_result_media_is_not_silently_lost() -> None:
    response = AgentResponse(messages=[
        Message("assistant", [Content.from_function_call("a", "lookup")]),
        Message("tool", [Content.from_function_result("a", result=[
            Content.from_text("caption"),
            Content.from_uri("https://example.test/image.png", media_type="image/png"),
        ])]),
    ])
    converted = AgentFrameworkOutputAdapter().convert(response)
    assert len(converted.output.contents) == 1
    assert converted.decisions[-1].status is ConversionStatus.UNSUPPORTED


@pytest.mark.parametrize("arguments", ['{"broken":', {"invalid": object()}, {"nan": float("nan")}])
def test_agentframework_invalid_final_arguments_are_inspectable(arguments: object) -> None:
    # Content's external boundary is intentionally exercised with malformed provider data.
    content = Content("function_call", call_id="a", name="lookup")
    content.arguments = arguments  # type: ignore[assignment]
    converted = AgentFrameworkOutputAdapter().convert(AgentResponse(messages=Message("assistant", [content])))
    assert converted.output.contents == ()
    assert converted.decisions[0].status is ConversionStatus.UNSUPPORTED


def test_agentframework_stream_media_results_and_reasoning_have_explicit_outcomes() -> None:
    adapter = AgentFrameworkStreamAdapter(expose_reasoning=True)
    adapter.convert_update(AgentResponseUpdate(contents=[
        Content.from_function_call("a", "lookup", arguments={}),
    ]))
    converted = adapter.convert_update(AgentResponseUpdate(contents=[
        Content.from_function_result("a", result="found"),
        Content.from_uri("https://example.test/image.png", media_type="image/png"),
        Content.from_data(b"sound", media_type="audio/mpeg"),
        Content.from_text_reasoning(text="selected"),
        Content.from_text_reasoning(text="private", protected_data="encrypted"),
        Content.from_hosted_file("file-private"),
    ]))
    assert len([event for event in converted.events if isinstance(event, ContentEvent)]) == 3
    assert converted.events[0] == ContentEnd("tool:a")
    assert converted.decisions[-2].status is ConversionStatus.EXCLUDED
    assert converted.decisions[-1].status is ConversionStatus.UNSUPPORTED
    assert any(isinstance(event, TextDelta) and event.text == "selected" for event in converted.events)
    assert "private" not in repr(converted.events)


def test_agentframework_adapter_invocations_do_not_share_tool_or_stream_state() -> None:
    final_adapter = AgentFrameworkOutputAdapter()
    final_adapter.convert(AgentResponse(messages=Message("assistant", [
        Content.from_function_call("a", "lookup"),
    ])))
    orphan = final_adapter.convert(AgentResponse(messages=Message("tool", [
        Content.from_function_result("a", result="must not inherit a name"),
    ])))
    assert orphan.decisions[0].status is ConversionStatus.UNSUPPORTED
    first, second = AgentFrameworkStreamAdapter(), AgentFrameworkStreamAdapter()
    update = AgentResponseUpdate(message_id="m", contents=[Content.from_text("one")])
    first.convert_update(update)
    assert isinstance(second.convert_update(update).events[0], ContentStart)


def test_agentframework_native_annotations_are_inspectably_unsupported_without_guessed_offsets() -> None:
    annotation: Annotation = {
        "type": "citation", "title": "Reference", "url": "https://example.test/private-reference",
    }
    content = Content.from_text("answer", annotations=[annotation])
    final = AgentFrameworkOutputAdapter().convert(AgentResponse(messages=Message("assistant", [content])))
    streamed = AgentFrameworkStreamAdapter().convert_update(AgentResponseUpdate(contents=[content]))
    assert final.output.contents == (TextContent("answer"),)
    for decisions in (final.decisions, streamed.decisions):
        assert decisions[-1].status is ConversionStatus.UNSUPPORTED
        assert decisions[-1].reason is ConversionReason.UNSUPPORTED_ANNOTATIONS
        assert "private-reference" not in repr(decisions)


@pytest.mark.parametrize(("cached", "reasoning"), [(3, 2), (0, 0), (None, None)])
def test_agentframework_final_preserves_native_optional_usage_breakdowns(
    cached: int | None, reasoning: int | None,
) -> None:
    details: UsageDetails = {
        "input_token_count": 10,
        "output_token_count": 5,
        "total_token_count": 15,
        "cache_read_input_token_count": cached,
        "reasoning_output_token_count": reasoning,
        "cache_creation_input_token_count": 4,
    }
    converted = AgentFrameworkOutputAdapter().convert(AgentResponse(usage_details=details))
    assert converted.output.usage is not None
    assert converted.output.usage.cached_input_tokens == cached
    assert converted.output.usage.reasoning_output_tokens == reasoning
    assert converted.output.usage.cache_write_input_tokens is None
    assert converted.output.usage.total_tokens == 15


def test_agentframework_stream_preserves_and_aggregates_native_usage_breakdowns() -> None:
    updates = [
        AgentResponseUpdate(contents=[Content.from_usage({
            "input_token_count": 10, "output_token_count": 5, "total_token_count": 15,
            "cache_read_input_token_count": 3, "reasoning_output_token_count": 2,
            "cache_creation_input_token_count": 4,
        })]),
        AgentResponseUpdate(contents=[Content.from_usage({
            "input_token_count": 5, "output_token_count": 2, "total_token_count": 7,
            "cache_read_input_token_count": 1, "reasoning_output_token_count": 1,
            "cache_creation_input_token_count": 2,
        })]),
    ]
    adapter = AgentFrameworkStreamAdapter()
    adapter.convert_update(updates[0])
    converted = adapter.convert_update(updates[1])
    event = converted.events[0]
    assert isinstance(event, UsageEvent)
    assert event.usage.cached_input_tokens == 4
    assert event.usage.reasoning_output_tokens == 3
    assert event.usage.cache_write_input_tokens is None
    assert event.usage == AgentFrameworkOutputAdapter().convert(AgentResponse.from_updates(updates)).output.usage


def test_agentframework_absent_native_breakdowns_are_not_zero_or_cache_creation() -> None:
    details: UsageDetails = {
        "input_token_count": 10, "output_token_count": 5,
        "cache_creation_input_token_count": 4,
    }
    final = AgentFrameworkOutputAdapter().convert(AgentResponse(
        messages=Message("assistant", [Content.from_usage(details)]),
    ))
    streamed = AgentFrameworkStreamAdapter().convert_update(AgentResponseUpdate(
        contents=[Content.from_usage(details)],
    ))
    assert final.output.usage is not None
    event = streamed.events[0]
    assert isinstance(event, UsageEvent)
    for usage in (final.output.usage, event.usage):
        assert usage.cached_input_tokens is None
        assert usage.reasoning_output_tokens is None
        assert usage.total_tokens is None
        assert usage.cache_write_input_tokens is None


def test_agentframework_partial_stream_breakdowns_remain_unknown_cumulatively() -> None:
    adapter = AgentFrameworkStreamAdapter()
    adapter.convert_update(AgentResponseUpdate(contents=[Content.from_usage({
        "input_token_count": 10, "output_token_count": 5,
        "cache_read_input_token_count": 3, "reasoning_output_token_count": 2,
        "total_token_count": 15,
        "cache_creation_input_token_count": 4,
    })]))
    converted = adapter.convert_update(AgentResponseUpdate(contents=[Content.from_usage({
        "input_token_count": 5, "output_token_count": 2,
    })]))
    event = converted.events[0]
    assert isinstance(event, UsageEvent)
    assert event.usage.input_tokens == 15 and event.usage.output_tokens == 7
    assert event.usage.cached_input_tokens is None
    assert event.usage.reasoning_output_tokens is None
    assert event.usage.total_tokens is None
    assert event.usage.cache_write_input_tokens is None


@pytest.mark.parametrize("creation", [None, 0, 4])
def test_agentframework_native_cache_creation_is_not_inferred_as_cache_write(creation: int | None) -> None:
    assert "cache_creation_input_token_count" in UsageDetails.__annotations__
    assert "cache_write_input_token_count" not in UsageDetails.__annotations__
    details: UsageDetails = {
        "input_token_count": 10, "output_token_count": 5,
        "cache_creation_input_token_count": creation,
    }
    final = AgentFrameworkOutputAdapter().convert(AgentResponse(usage_details=details))
    streamed = AgentFrameworkStreamAdapter().convert_update(AgentResponseUpdate(
        contents=[Content.from_usage(details)],
    ))
    assert final.output.usage is not None
    event = streamed.events[0]
    assert isinstance(event, UsageEvent)
    for usage in (final.output.usage, event.usage):
        assert usage.cache_write_input_tokens is None
        assert usage.cached_input_tokens is None


@pytest.mark.parametrize("invalid", [-1, True])
def test_agentframework_invalid_breakdowns_are_inspectably_unsupported(invalid: int) -> None:
    details: UsageDetails = {
        "input_token_count": 10, "output_token_count": 5,
        "cache_read_input_token_count": invalid,
    }
    final = AgentFrameworkOutputAdapter().convert(AgentResponse(usage_details=details))
    streamed = AgentFrameworkStreamAdapter().convert_update(AgentResponseUpdate(
        contents=[Content.from_usage(details)],
    ))
    assert final.output.usage is None
    assert final.decisions[-1].reason is ConversionReason.INCOMPLETE_USAGE
    assert streamed.events == ()
    assert streamed.decisions[-1].reason is ConversionReason.INCOMPLETE_USAGE
