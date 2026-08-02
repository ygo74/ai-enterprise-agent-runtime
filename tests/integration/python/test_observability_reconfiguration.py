from ygo74.agent_runtime.observability.logging_config import configure_logging
from ygo74.agent_runtime.observability.otel import configure_otel_sink


def test_observability_reconfiguration_hooks() -> None:
    configure_logging()
    out = configure_otel_sink("otlp")
    assert out["exporter"] == "otlp"
