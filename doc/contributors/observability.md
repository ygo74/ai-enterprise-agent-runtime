# Observability

Observability is a supporting domain, not part of the request contract.
`configure_logging` sets the runtime's logging defaults. `configure_otel_sink`
is currently a placeholder: it returns the supplied exporter setting but does
not install an OpenTelemetry pipeline. The .NET helper also returns its input.
Application hosts still own exporters, resource attributes, and deployment
logging policy.

```mermaid
flowchart LR
    Host[Application host] --> Logging[configure_logging]
    Host --> OTel[configure_otel_sink placeholder]
    Request[Runtime operation] --> AppLogger[Application/runtime logger]
    AppLogger --> Sink[Configured log or telemetry sink]
```

Do not log credentials, authorization headers, request bodies, or raw exception
messages. Python FastAPI execution failures log correlation fields, exception
type, and the innermost raising origin. A `DomainError` can supply
`safe_diagnostic_detail` only for explicitly credential-free metadata; the
runtime flattens it and caps it at 1024 characters. The MCP configuration loader
uses this for a missing environment reference, logging only its file, field,
and variable name. Keep raw secrets and provider response bodies out of this
field. Keep logging configuration callable more than once so test and
application hosts can set their own logging configuration. Do not document the
telemetry helper as an exporter until its implementation actually installs one.

Python source: [`observability`](../../packages/python/agents/ygo74/agent_runtime/observability/).
Cross-language setup is under `packages/dotnet/.../Observability` and
`packages/java/.../observability`. Tests: [Python reconfiguration](../../tests/integration/python/test_observability_reconfiguration.py),
[stream error redaction](../../tests/integration/python/test_interrupted_streams.py),
[Responses failure diagnostics](../../tests/integration/python/test_openai_responses_api.py),
[.NET reconfiguration](../../tests/integration/dotnet/ObservabilityReconfigurationTests.cs),
and [Java reconfiguration](../../tests/integration/java/ObservabilityReconfigurationTest.java).

See [observability specification](../../spec/operations/observability.md).
