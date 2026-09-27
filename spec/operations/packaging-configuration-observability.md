# Packaging, configuration, and observability

## Package layout

The repository contains Python, .NET, and Java implementations. Python is split
into three runtime distributions and one dependency-only meta-package:

| Distribution | Responsibility | Optional features |
|---|---|---|
| `ygo74-agent-runtime-security` | Authentication, application-security primitives, common Python domain errors, and user-context construction | None in this repository |
| `ygo74-agent-runtime-agents` | Agent contracts, configuration loading and schemas, reasoning port, endpoints, discovery, routing, sessions, approval | `configuration` for YAML and `.env`; `http` for FastAPI; `mcp` for the MCP client |
| `ygo74-agent-runtime-mcp` | MCP server hosting | `http` for streamable HTTP server transport |
| `ygo74-agent-runtime` | Installs all Python distributions | `http`, `mcp`, and `mcp-server` extras forwarded to the relevant package |

The packages contribute to a shared `ygo74.agent_runtime` namespace and should
be imported from their domain modules. The current design avoids a flat facade
and keeps framework/protocol dependencies optional. Python requires 3.12 or
newer. The .NET library targets .NET 8; the Java library targets Java 21.

## Configuration ownership

Configuration is typed at the domain boundary. Python defines endpoint and
discovery configuration, authentication policies, agent HTTP settings, MCP
bindings and MCP server settings. The agents distribution also provides optional
loading for delivered `agent.yaml` and `skill.yaml` files, their Draft 2020-12
schemas, and `.env` files. The manifest schemas are fixed versioned contracts;
permission resolution and security-floor enforcement remain dynamic runtime
checks. .NET binds endpoint options and validates them; Java provides endpoint
properties and validation. The host application owns deployment selection,
secrets, identity-provider registration, public URLs, persistence, and framework
startup. The runtime does not load arbitrary deployment configuration globally.
Python applications select the delivered agent-configuration directory with
`YGO74_AGENT_RUNTIME_CONFIG_DIR`; process environment values take precedence
over values loaded from `.env`.

In particular, an authentication mode must be selected explicitly where the
host API requires it. Choosing anonymous service is a named configuration
decision, not the consequence of omitting credentials. Discovery and invocation
may use separate authentication requirements.

## Logging and telemetry

The language packages integrate with their normal logging abstractions. Python
provides a logging setup helper and request-oriented log context. Security audit
logging records operation identifiers and outcomes without message content or
credentials. Applications remain responsible for log destinations, retention,
redaction of their own data, and correlation with surrounding services.

OpenTelemetry support is incomplete: `configure_otel_sink` and its .NET/Java
counterparts are integration placeholders rather than a full tracing or metrics
exporter configuration. Applications configure SDK providers, exporters,
resource attributes, sampling, and collection through their hosting stack.

## Compatibility and validation

Shared request/response contracts and endpoint identifiers are intended to
behave consistently across languages where an adapter exists. Provider wire
envelopes and HTTP status mapping remain adapter-specific. Language-only
capabilities and missing framework adapters are recorded in the [language
support matrix](../compatibility/language-status.md) and detailed [parity
status](../../docs/parity-status.md).

The repository's validation layers include shared JSON contract fixtures,
language-specific unit and integration tests, cross-language parity checks,
and performance-baseline checks under `tests/`. The checked-in percentile
thresholds are 10 ms for normalization/dispatch, 50 ms for authenticated
dispatch/middleware, and 300 ms for first stream event. The current performance
tests validate that these thresholds exist and are positive; they do not run
measurements or enforce the percentile values as an execution-time gate. These
numbers are therefore repository baselines, not a measured service-level
objective.

The system specification summarizes implemented behavior; the repository's
code and executable contracts remain the source of truth for exact details.
