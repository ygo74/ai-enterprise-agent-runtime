def configure_otel_sink(exporter: str | None = None) -> dict[str, str | None]:
    # Placeholder hook for OpenTelemetry pipeline integration.
    """Configure otel sink from supplied settings.

    Args:
        exporter (str | None): Optional OpenTelemetry exporter installed as the logging sink.
    """
    return {"exporter": exporter}
