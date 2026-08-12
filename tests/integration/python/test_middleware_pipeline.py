from ygo74.agent_runtime.middleware.registry import MiddlewareRegistry


def test_registry_orders_middlewares() -> None:
    registry = MiddlewareRegistry()
    registry.register("a", lambda c, n: n(c), 10)
    registry.register("b", lambda c, n: n(c), 5)
    assert [m.middleware_id for m in registry.ordered()] == ["b", "a"]
