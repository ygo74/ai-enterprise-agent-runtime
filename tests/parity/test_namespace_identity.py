import ygo74.agent_runtime as runtime


def test_namespace_identity_python_root() -> None:
    assert runtime.__name__.startswith("ygo74")
    assert "StandardExchangeRequest" in runtime.__all__
