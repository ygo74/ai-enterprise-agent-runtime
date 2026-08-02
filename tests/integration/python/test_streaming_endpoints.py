from ygo74.agent_runtime.domains.streaming.stream_termination import complete_event


def test_stream_completion_event_shape() -> None:
    evt = complete_event("r1", {"text": "done"})
    assert evt["event_type"] == "completion"
