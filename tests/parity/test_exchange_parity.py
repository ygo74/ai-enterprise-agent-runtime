from ygo74.agent_runtime.domains.endpoints.adapters import normalize_request


def test_exchange_parity_for_non_stream_endpoints() -> None:
    payload = {"request_id": "r1", "route_key": "demo", "input": "hello"}
    chat = normalize_request("openai.chat_completions", payload)
    resp = normalize_request("openai.responses", payload)
    anth = normalize_request("anthropic.messages", payload)

    assert chat.request_id == resp.request_id == anth.request_id == "r1"
    assert chat.route_key == resp.route_key == anth.route_key == "demo"
    assert chat.input == resp.input == anth.input == "hello"
