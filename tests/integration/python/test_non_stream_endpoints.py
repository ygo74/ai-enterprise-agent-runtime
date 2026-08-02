from ygo74.agent_runtime.domains.endpoints.adapters import normalize_request
from ygo74.agent_runtime.domains.mapping.response_mapper import map_response


def test_openai_chat_non_stream_round_trip() -> None:
    req = normalize_request("openai.chat_completions", {"request_id": "r1", "route_key": "demo", "input": "hello"})
    resp = map_response(req.endpoint_type, {"request_id": req.request_id, "status": "success", "output": {"text": "ok"}})
    assert resp["status"] == "success"


def test_openai_responses_non_stream_round_trip() -> None:
    req = normalize_request("openai.responses", {"request_id": "r2", "route_key": "demo", "input": "hello"})
    resp = map_response(req.endpoint_type, {"request_id": req.request_id, "status": "success", "output": {"text": "ok"}})
    assert resp["status"] == "success"


def test_anthropic_messages_non_stream_round_trip() -> None:
    req = normalize_request("anthropic.messages", {"request_id": "r3", "route_key": "demo", "input": "hello"})
    resp = map_response(req.endpoint_type, {"request_id": req.request_id, "status": "success", "output": {"text": "ok"}})
    assert resp["status"] == "success"
