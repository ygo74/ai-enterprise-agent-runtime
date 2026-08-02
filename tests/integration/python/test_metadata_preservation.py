from ygo74.agent_runtime.domains.endpoints.adapters import normalize_request


def test_metadata_fields_preserved() -> None:
    raw = {
        "request_id": "r-meta",
        "route_key": "demo",
        "input": "hello",
        "model": "gpt-x",
        "metadata": {"tenant": "acme"},
    }
    req = normalize_request("openai.responses", raw)
    assert req.request_id == "r-meta"
    assert req.metadata.get("model") == "gpt-x"
    assert req.metadata.get("tenant") == "acme"
