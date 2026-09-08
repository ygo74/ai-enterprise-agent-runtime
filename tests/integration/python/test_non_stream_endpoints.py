from ygo74.agent_runtime.domains.endpoints.adapters import normalize_request
from ygo74.agent_runtime.domains.mapping.response_mapper import map_response


def test_openai_chat_non_stream_round_trip() -> None:
    req = normalize_request("openai.chat_completions", {"request_id": "r1", "route_key": "demo", "input": "hello"})
    resp = map_response(
        req.endpoint_type,
        {"request_id": req.request_id, "status": "success", "output": {"text": "ok"}},
        model="demo-model",
    )
    assert resp["object"] == "chat.completion"
    assert resp["id"] == "r1"
    assert resp["model"] == "demo-model"
    assert resp["choices"][0]["message"] == {"role": "assistant", "content": "ok"}
    assert resp["choices"][0]["finish_reason"] == "stop"


def test_openai_responses_non_stream_round_trip() -> None:
    req = normalize_request("openai.responses", {"request_id": "r2", "route_key": "demo", "input": "hello"})
    resp = map_response(
        req.endpoint_type,
        {"request_id": req.request_id, "status": "success", "output": {"text": "ok"}},
        model="demo-model",
    )
    assert resp["object"] == "response"
    assert resp["status"] == "completed"
    assert resp["output_text"] == "ok"
    assert resp["output"][0]["content"][0] == {"type": "output_text", "text": "ok", "annotations": []}


def test_anthropic_messages_non_stream_round_trip() -> None:
    req = normalize_request("anthropic.messages", {"request_id": "r3", "route_key": "demo", "input": "hello"})
    resp = map_response(
        req.endpoint_type,
        {"request_id": req.request_id, "status": "success", "output": {"text": "ok"}},
        model="demo-model",
    )
    assert resp["type"] == "message"
    assert resp["role"] == "assistant"
    assert resp["content"] == [{"type": "text", "text": "ok"}]
    assert resp["stop_reason"] == "end_turn"


def test_an_error_keeps_the_exchange_envelope() -> None:
    """Errors already carry an HTTP status; their body is unchanged by this mapping."""
    resp = map_response(
        "openai.chat_completions",
        {"request_id": "r4", "status": "error", "error": {"code": "boom", "message": "it broke"}},
    )
    assert resp["status"] == "error"
    assert resp["error"]["code"] == "boom"
    assert "choices" not in resp


def test_an_unknown_endpoint_type_keeps_the_envelope() -> None:
    """Adding a protocol must never silently reshape an existing one."""
    resp = map_response(
        "vendor.custom",
        {"request_id": "r5", "status": "success", "output": {"text": "ok"}},
    )
    assert resp["output"] == {"text": "ok"}
    assert resp["endpoint_type"] == "vendor.custom"


def test_a_plain_string_output_is_rendered_as_the_message() -> None:
    resp = map_response(
        "openai.chat_completions",
        {"request_id": "r6", "status": "success", "output": "just text"},
    )
    assert resp["choices"][0]["message"]["content"] == "just text"


def test_a_structured_output_is_serialised_rather_than_dropped() -> None:
    """An empty message would look like a model failure instead of a shape mismatch."""
    resp = map_response(
        "openai.chat_completions",
        {"request_id": "r7", "status": "success", "output": {"answer": 42}},
    )
    assert "42" in resp["choices"][0]["message"]["content"]
