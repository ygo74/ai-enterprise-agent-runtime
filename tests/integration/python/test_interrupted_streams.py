from ygo74.agent_runtime.domains.streaming.stream_termination import error_event


def test_interrupted_stream_maps_to_error_event() -> None:
    evt = error_event("r1", {"code": "stream_interrupted"})
    assert evt["event_type"] == "error"
