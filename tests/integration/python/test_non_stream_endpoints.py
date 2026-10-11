import pytest
from ygo74.agent_runtime.domains.contracts import (
    AgentOutput,
    Termination,
    TerminationStatus,
    TextContent,
    TokenUsage,
)
from ygo74.agent_runtime.domains.contracts.error_envelope import ErrorEnvelope
from ygo74.agent_runtime.domains.contracts.exchange_models import (
    StandardExchangeResponse,
)
from ygo74.agent_runtime.domains.endpoints.adapters import normalize_request
from ygo74.agent_runtime.domains.mapping.output_normalizer import OutputValidationError
from ygo74.agent_runtime.domains.mapping.response_mapper import map_response


@pytest.mark.parametrize(
    "protocol", ["openai.chat_completions", "openai.responses", "anthropic.messages"]
)
def test_non_stream_round_trip(protocol: str) -> None:
    req = normalize_request(
        protocol, {"request_id": "r1", "route_key": "demo", "input": "hello"}
    )
    resp = map_response(
        protocol,
        StandardExchangeResponse(
            req.request_id,
            "success",
            AgentOutput((TextContent("ok"),), TokenUsage(1, 2)),
        ),
        model="demo-model",
    )
    assert resp["model"] == "demo-model"
    if protocol == "openai.chat_completions":
        assert resp["choices"][0]["message"] == {"role": "assistant", "content": "ok"}
        assert resp["choices"][0]["finish_reason"] == "stop"
    elif protocol == "openai.responses":
        assert resp["status"] == "completed"
        assert resp["output_text"] == "ok"
        assert resp["output"][0]["content"][0] == {
            "type": "output_text",
            "text": "ok",
            "annotations": [],
        }
    else:
        assert resp["content"] == [{"type": "text", "text": "ok"}]
        assert resp["stop_reason"] == "end_turn"


def test_an_error_keeps_the_exchange_envelope() -> None:
    resp = map_response(
        "openai.chat_completions",
        AgentOutput(
            termination=Termination(
                TerminationStatus.FAILED,
                error=ErrorEnvelope("boom", "handler_execution", "it broke"),
            )
        ),
    )
    assert resp["status"] == "error"
    assert resp["error"]["code"] == "boom"
    assert "choices" not in resp


def test_an_unknown_endpoint_type_is_explicitly_rejected() -> None:
    with pytest.raises(ValueError):
        map_response("vendor.custom", AgentOutput())


@pytest.mark.parametrize("output", ["just text", {"answer": 42}])
def test_untyped_outputs_are_not_inferred_or_serialized(output: object) -> None:
    with pytest.raises(OutputValidationError):
        map_response("openai.chat_completions", output)
