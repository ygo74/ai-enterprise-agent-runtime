import json
from pathlib import Path

from ygo74.agent_runtime.domains.contracts import stream_events
from ygo74.agent_runtime.domains.endpoints.adapters import normalize_request
from ygo74.agent_runtime.domains.streaming.sse_encoder import SseEncoder, WireEvent

FIXTURE_PATH = Path("tests/contract/fixtures/openai_responses_v1.json")


def _fixture() -> dict[str, object]:
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


def test_handler_stream_contract_does_not_expose_native_provider_events() -> None:
    assert not hasattr(stream_events, "OpenAIResponsesStreamEvent")
    assert not hasattr(stream_events, "OpenAIResponsesStreamEventType")


def test_standard_exchange_provider_options_are_optional_wire_json() -> None:
    schema_path = Path(
        "specs/001-openai-endpoint-exposure/contracts/standard-exchange-v1.schema.json"
    )
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    request_schema = schema["properties"]["request"]

    assert "providerOptions" not in request_schema["required"]
    assert request_schema["properties"]["providerOptions"] == {
        "type": "object",
        "additionalProperties": True,
    }


def test_responses_create_parameters_are_preserved_from_the_pinned_sdk_inventory() -> (
    None
):
    fields = _fixture()["requestFields"]
    payload = {field: {"preserved": field} for field in fields}
    payload.update(
        {
            "request_id": "req-parameters",
            "route_key": "support",
            "endpoint_type": "openai.responses",
            "model": "support-agent",
            "input": [{"role": "user", "content": "hello"}],
            "stream": True,
            "metadata": {"tenant": "alpha"},
        }
    )

    request = normalize_request("openai.responses", payload)

    normalized_fields = {"input", "model", "stream", "metadata"}
    expected_options = {
        key: payload[key] for key in fields if key not in normalized_fields
    }
    assert request.provider_options == expected_options


def test_openai_responses_encoder_preserves_every_event_payload() -> None:
    encoder = SseEncoder()
    for index, event_name in enumerate(_fixture()["streamEventTypes"]):
        payload = {
            "type": event_name,
            "sequence_number": index,
            "sample": {"keep": True},
        }
        event = WireEvent(payload, event_name)

        frame = encoder.encode(event)
        event_line, data_line, _, _ = frame.split("\n")

        assert event_line == f"event: {event_name}"
        assert json.loads(data_line.removeprefix("data: ")) == payload
