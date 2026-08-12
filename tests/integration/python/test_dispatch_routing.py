from ygo74.agent_runtime.routing.route_registry import RouteRegistry


def test_dispatch_route_lookup() -> None:
    registry = RouteRegistry()
    registry.register("demo", lambda req: req)
    assert registry.resolve("demo") is not None
