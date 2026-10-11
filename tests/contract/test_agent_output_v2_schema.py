import json
from dataclasses import fields
from pathlib import Path
from typing import get_args

import pytest
from jsonschema import Draft202012Validator
from ygo74.agent_runtime.domains.contracts import (
    AgentContent,
    AgentOutput,
    AgentStreamEvent,
    AudioContent,
    AudioDelta,
    AudioFormat,
    AudioTranscriptDelta,
    ContentEnd,
    ContentEvent,
    ContentStart,
    EncodedMedia,
    ErrorEnvelope,
    ImageContent,
    MediaUri,
    Notification,
    OutputSerializationError,
    OutputValueType,
    ReasoningContent,
    StandardExchangeResponse,
    TerminalEvent,
    Termination,
    TerminationStatus,
    TextContent,
    TextDelta,
    TokenUsage,
    ToolArgumentsDelta,
    ToolCallContent,
    ToolExecution,
    ToolResultContent,
    UrlCitation,
    UsageEvent,
)
from ygo74.agent_runtime.domains.contracts.output_serialization import (
    AgentOutputSerializer,
)

SCHEMA_PATH = Path(
    "specs/001-openai-endpoint-exposure/contracts/agent-output-v2.schema.json"
)

MODELS = (
    AgentOutput,
    TextContent,
    Notification,
    ReasoningContent,
    ToolCallContent,
    ToolResultContent,
    ImageContent,
    AudioContent,
    UrlCitation,
    MediaUri,
    EncodedMedia,
    TokenUsage,
    Termination,
    ErrorEnvelope,
    StandardExchangeResponse,
    ContentEvent,
    ContentStart,
    TextDelta,
    ToolArgumentsDelta,
    AudioDelta,
    AudioTranscriptDelta,
    ContentEnd,
    UsageEvent,
    TerminalEvent,
)


def _schema() -> dict:
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


def _validate(value: object, definition: str = "AgentOutput") -> None:
    schema = _schema()
    schema["$ref"] = f"#/$defs/{definition}"
    if definition != "AgentStreamEvent":
        definition = f"Tagged{definition}"
    schema["$ref"] = f"#/$defs/{definition}"
    Draft202012Validator(schema).validate(AgentOutputSerializer().serialize(value))


def test_output_schema_is_independently_versioned_and_valid() -> None:
    schema = _schema()
    Draft202012Validator.check_schema(schema)
    assert schema["$id"].endswith("/agent-output-v2.schema.json")
    assert schema["$ref"] == "#/$defs/TaggedAgentOutput"
    assert "standard-exchange-v1" not in json.dumps(schema)


@pytest.mark.parametrize("model", MODELS)
def test_schema_fields_exactly_match_concrete_dataclasses(model: type) -> None:
    definition = _schema()["$defs"][model.__name__]
    assert set(definition["properties"]) == {field.name for field in fields(model)}
    assert set(definition["required"]) == set(definition["properties"])
    assert definition["additionalProperties"] is False


def test_schema_unions_and_enums_match_the_public_api() -> None:
    definitions = _schema()["$defs"]
    for name, union in (
        ("AgentContent", AgentContent),
        ("AgentStreamEvent", AgentStreamEvent),
    ):
        references = definitions[name]["oneOf"]
        assert {
            entry["$ref"].rsplit("/", 1)[-1].removeprefix("Tagged")
            for entry in references
        } == {model.__name__ for model in get_args(union)}
    for name, enum in (
        ("ToolExecution", ToolExecution),
        ("TerminationStatus", TerminationStatus),
        ("AudioFormat", AudioFormat),
        ("OutputValueType", OutputValueType),
    ):
        assert definitions[name]["enum"] == [value.value for value in enum]


def test_complete_typed_output_serializes_into_the_v2_schema() -> None:
    output = AgentOutput(
        (
            TextContent(
                "Answer", (UrlCitation("https://example.test/source", "Source", 0, 6),)
            ),
            Notification("Working"),
            ReasoningContent("Summary", True),
            ToolCallContent("call", "lookup", {"city": "Paris"}),
            ToolResultContent("call", "lookup", {"found": True}),
            ImageContent(MediaUri("https://example.test/image.png", "image/png")),
            ImageContent(EncodedMedia("YQ==", "image/png")),
            AudioContent(
                EncodedMedia("YQ==", "audio/wav"),
                "audio",
                "transcript",
                expires_at=12345,
            ),
        ),
        TokenUsage(2, 3, 5),
    )
    _validate(output)
    _validate(
        StandardExchangeResponse("request", "success", output),
        "StandardExchangeResponse",
    )
    _validate(
        AgentOutput(
            termination=Termination(
                TerminationStatus.FAILED,
                error=ErrorEnvelope("failed", "handler_execution", "Failed"),
            )
        )
    )


@pytest.mark.parametrize(
    "event",
    [
        ContentEvent("text", TextContent("Answer")),
        ContentStart("text", TextContent("")),
        TextDelta("text", "Answer"),
        ToolArgumentsDelta("tool", '{"city":'),
        AudioDelta("audio", "YQ==", 0),
        AudioTranscriptDelta("audio", "words"),
        ContentEnd("text"),
        UsageEvent(TokenUsage(2, 3)),
        TerminalEvent(),
    ],
)
def test_each_event_has_an_exact_structural_schema(event: object) -> None:
    _validate(event, type(event).__name__)
    _validate(event, "AgentStreamEvent")


@pytest.mark.parametrize(
    "invalid",
    [
        {
            "contents": ["raw text"],
            "usage": None,
            "termination": {"status": "success", "reason": None, "error": None},
        },
        {
            "contents": [],
            "usage": {"input_tokens": -1, "output_tokens": 0, "total_tokens": None},
            "termination": {"status": "success", "reason": None, "error": None},
        },
        {
            "contents": [],
            "usage": None,
            "termination": {"status": "failed", "reason": None, "error": None},
        },
        {
            "contents": [
                {"text": "Answer", "annotations": [], "native_provider_field": True}
            ],
            "usage": None,
            "termination": {"status": "success", "reason": None, "error": None},
        },
    ],
)
def test_invalid_json_output_shapes_are_rejected(invalid: dict) -> None:
    assert list(
        Draft202012Validator(_schema()).iter_errors(
            {"type": "agent_output", "value": invalid}
        )
    )


def test_notice_cannot_be_mistaken_for_answer_after_serialization() -> None:
    serializer = AgentOutputSerializer()
    notice = serializer.serialize(Notification("working"))
    answer = serializer.serialize(TextContent("working"))
    assert notice["type"] == "notification"
    assert answer["type"] == "text"
    assert notice != answer
    schema = _schema()
    schema["$ref"] = "#/$defs/TaggedTextContent"
    assert list(Draft202012Validator(schema).iter_errors(notice))


def test_atomic_content_and_content_start_have_distinct_serialized_tags() -> None:
    serializer = AgentOutputSerializer()
    content = TextContent("answer")
    atomic = serializer.serialize(ContentEvent("answer", content))
    start = serializer.serialize(ContentStart("answer", content))
    assert atomic["value"] == start["value"]
    assert atomic["type"] == "content_event"
    assert start["type"] == "content_start"
    schema = _schema()
    schema["$ref"] = "#/$defs/TaggedContentStart"
    assert list(Draft202012Validator(schema).iter_errors(atomic))


def test_serialization_does_not_reintroduce_raw_handler_outputs() -> None:
    with pytest.raises(OutputSerializationError):
        AgentOutputSerializer().serialize({"text": "legacy"})
    with pytest.raises(OutputSerializationError):
        AgentOutputSerializer().serialize("legacy")


def test_equal_delta_fields_preserve_distinct_semantic_identity() -> None:
    serializer = AgentOutputSerializer()
    text = serializer.serialize(TextDelta("content", "words"))
    transcript = serializer.serialize(AudioTranscriptDelta("content", "words"))
    assert text["value"] == transcript["value"]
    assert text["type"] == "text_delta"
    assert transcript["type"] == "audio_transcript_delta"
