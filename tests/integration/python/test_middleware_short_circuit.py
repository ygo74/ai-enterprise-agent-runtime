from ygo74.agent_runtime.middleware.pipeline import execute_pipeline


def test_short_circuit_returns_early() -> None:
    def mw(ctx, nxt):
        return {"status": "success", "output": "short"}

    out = execute_pipeline({}, [mw], lambda _: {"status": "success", "output": "handler"})
    assert out["output"] == "short"
