import pytest
from ygo74.agent_runtime.domains.contracts.agent_output import (
    AgentOutput,
    AudioContent,
    ImageContent,
    Notification,
    Termination,
    TerminationStatus,
    TextContent,
    TokenUsage,
    ToolCallContent,
)
from ygo74.agent_runtime.domains.contracts.exchange_models import (
    StandardExchangeResponse,
)
from ygo74.agent_runtime.domains.contracts.media_content import EncodedMedia, MediaUri
from ygo74.agent_runtime.domains.mapping.output_normalizer import (
    OutputNormalizer,
    OutputValidationError,
)


def test_output_is_explicit_and_shared_with_stream_content() -> None:
    output = AgentOutput(contents=(TextContent("answer"), Notification("working")))
    assert OutputNormalizer().normalize(output).contents == output.contents


@pytest.mark.parametrize("value", ["answer", {"text": "answer"}, 123, None])
def test_legacy_outputs_are_rejected(value: object) -> None:
    with pytest.raises(OutputValidationError):
        OutputNormalizer().normalize(value)


@pytest.mark.parametrize(
    "output",
    [
        AgentOutput((TextContent(123),)),
        AgentOutput((ImageContent(EncodedMedia("not base64", "image/png")),)),
        AgentOutput((ImageContent(MediaUri("relative.png", "image/png")),)),
        AgentOutput((AudioContent(EncodedMedia("", "image/png"), "audio"),)),
        AgentOutput(usage=TokenUsage(-1, 2)),
        AgentOutput(usage=TokenUsage(True, 2)),
        AgentOutput(usage=TokenUsage(1, 2, cached_input_tokens=-1)),
        AgentOutput(usage=TokenUsage(1, 2, reasoning_output_tokens=True)),
        AgentOutput(usage=TokenUsage(1, 2, cache_write_input_tokens=-1)),
        AgentOutput(termination=Termination(TerminationStatus.FAILED)),
        AgentOutput((ToolCallContent("same", "one"), ToolCallContent("same", "two"))),
        AgentOutput((ToolCallContent("call", "one", {"value": float("nan")}),)),
    ],
)
def test_invalid_pivots_are_explicit_errors(output: AgentOutput) -> None:
    with pytest.raises(OutputValidationError):
        OutputNormalizer().normalize(output)


def test_exchange_envelope_must_preserve_request_correlation() -> None:
    with pytest.raises(OutputValidationError, match="request_id"):
        OutputNormalizer().normalize(
            StandardExchangeResponse("other-request", "success", AgentOutput()),
            request_id="request",
        )


def test_cyclic_tool_json_is_an_explicit_invalid_output() -> None:
    arguments: dict[str, object] = {}
    arguments["cycle"] = arguments
    with pytest.raises(OutputValidationError):
        OutputNormalizer().normalize(
            AgentOutput((ToolCallContent("call", "tool", arguments),))
        )
