# Logging and telemetry hooks

## Purpose and role

Hosts need a predictable place to configure logs and connect telemetry without
making provider payloads part of the agent contract. The runtime exposes small
language-specific logging setup helpers and names an OpenTelemetry setup hook.
These helpers are not a complete tracing or metrics system.

## Current behavior

Python `configure_logging(level)` calls `logging.basicConfig` with a request ID
and route in its format. It does not configure a logging destination, exporter,
retention policy, or application-specific redaction. Python
`configure_otel_sink(exporter)` currently returns the exporter value in a
dictionary and installs no sink.

Java `LoggingSetup.configure(name, level)` returns a configured named logger.
The .NET logging setup currently leaves the supplied builder unchanged. The
Java and .NET OpenTelemetry methods return the supplied exporter value; they do
not create an SDK provider or exporter.

Security audit records are separate application-security events with their own
content minimization rules. They do not imply that the runtime has configured a
distributed trace or an OpenTelemetry pipeline.

## Host responsibility and limits

The host configures logging sinks, OpenTelemetry providers and exporters,
correlation with surrounding services, sampling, data retention, and redaction
for application-owned fields. It should not log credentials, prompts, tool
arguments, or retrieved message/page content by default. Framework-specific
diagnostics must follow the same data-minimization rules.

The logging API exists in Python, .NET, and Java, but its behavior is not yet
equivalent across the languages. OpenTelemetry setup is an incomplete
placeholder in each implementation. Do not treat method presence as evidence
that telemetry is exported.

Acceptance for the current implementation is limited to accurate logger
configuration behavior and explicit disclosure that exporter setup is not
implemented. A complete tracing or metrics integration remains future work.

See the [packaging and operations specification](packaging-configuration-observability.md),
the [language support matrix](../compatibility/language-status.md), and the
reconfiguration integration checks in
[`tests/integration`](../../tests/integration/).
