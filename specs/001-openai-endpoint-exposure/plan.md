# Implementation Plan: OpenAI and Anthropic Endpoint Exposure

**Branch**: `[001-openai-endpoint-exposure]` | **Date**: 2026-08-16 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/001-openai-endpoint-exposure/spec.md`

**Note**: This template is filled in by the `/speckit.plan` command. See `.specify/templates/plan-template.md` for the execution workflow.

**Revision**: 2026-08-16 regeneration adds agent capability discovery (FR-024..FR-046,
SC-014..SC-019) covering the shared agent descriptor, OpenAI and Anthropic model
listing surfaces, and the A2A agent card projection.

## Summary

Expose OpenAI-compatible endpoint surfaces (Chat Completions and Responses)
and Anthropic-compatible Messages endpoint surfaces,
through Python, .NET, and Java libraries with a clean, decoupled request-dispatch
pipeline. The runtime normalizes endpoint payloads into a standard exchange
request, authenticates callers (JWT or API key user-resolution hook), dispatches
to developer handlers, and maps standard exchange responses back to endpoint
format, including streaming mode for each supported endpoint family.
The dispatch model includes a middleware pipeline where developers can inspect,
enrich, validate, and transform messages before and after handler execution,
with explicit chaining to the next middleware in the pipeline.
Authorization remains developer-owned and is executed in handler logic.

The same runtime additionally exposes agent capability discovery. Developers
declare one provider-neutral `AgentDescriptor` per exposed agent, and the runtime
projects it into three read-only surfaces without duplicating configuration:
the OpenAI-compatible model listing, the Anthropic-compatible model listing, and
the A2A agent card. Discovery reuses the existing route-key registry,
authentication layer, and error envelope, so agents advertised by discovery are
guaranteed to be invocable through the endpoints above.

## Technical Context

**Language/Version**: Python 3.11+, .NET 8+, Java 21+

**Primary Dependencies**: Web framework adapters per language,
JWT validation libraries, JSON schema validation libraries, shared contract
definitions under `specs/001-openai-endpoint-exposure/contracts/`,
streaming transport/event serialization support,
middleware pipeline abstractions in each language runtime,
framework-native configuration binding for agent descriptor declaration

**Storage**: N/A (in-memory request processing; descriptors held in an
initialization-time in-memory registry)

**Testing**: Unit tests per language, contract tests for exchange format and
agent descriptor schema, integration tests for endpoint and discovery surfaces,
cross-surface consistency tests, cross-language parity tests

**Target Platform**: Server-side runtime on Linux/Windows containers and local dev

**Project Type**: Multi-language library package set

**Performance Goals**: Request normalization + dispatch overhead adds <10ms p95
for typical payload sizes (<64 KB); authentication + dispatch pipeline remains
<50ms p95 excluding user handler execution; first stream event emitted <300ms
p95 after request acceptance (excluding user handler cold start); discovery
listing responses served <20ms p95 for catalogues up to 100 agents, and single
descriptor lookup is O(1) by agent identifier

**Constraints**: DRY-first reuse; clean decoupling of endpoint transport and
handler business logic; authorization is developer-owned; deterministic mapping
rules between endpoint and exchange formats; package namespace root fixed to
`ygo74` across Python/.NET/Java; middleware execution order MUST be deterministic
and allow pre-handler and post-handler interception; exactly one descriptor is
the source of truth for every discovery surface, and discovery output MUST NOT
advertise anything the runtime cannot serve

**Scale/Scope**: First feature targets OpenAI-compatible Chat Completions,
OpenAI-compatible Responses, and Anthropic-compatible Messages, each with
streaming and non-streaming behavior, with one or more handlers per service and
equivalent behavior across Python/.NET/Java, plus middleware pipeline extension
points for request/response processing, plus three read-only discovery
projections over a catalogue sized for up to 100 agents per runtime instance

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **Parity Gate**: PASS. Contracts define shared payload, stream-event,
  error envelope, and agent descriptor semantics; the test matrix enforces
  equivalent endpoint and discovery behavior across Python/.NET/Java.
- **Design Simplicity Gate**: PASS. Dispatcher/handler separation follows SOLID;
  mapping and authn concerns are isolated; early-return error flow is mandated.
  Discovery adds one registry plus three stateless projections, with no new
  control flow in the invocation path.
- **Reuse-First Gate**: PASS. Discovery reuses the existing route-key registry,
  authentication layer, and error envelope rather than introducing parallel
  mechanisms; implementation tasks require an inventory of existing reusable
  modules before creating new components.
- **Testing Gate**: PASS. Red-green-refactor with unit, contract, integration,
  cross-surface consistency, and parity suites required before merge.
- **UX Consistency Gate**: PASS. Standard exchange, stream-event, error envelope,
  and agent descriptor contracts ensure consistent developer-facing behavior
  across language SDKs, endpoint families, and discovery dialects.
- **Performance Gate**: PASS. P95 overhead budgets and regression benchmarks are
  included in scope and validated per language runtime, including a discovery
  listing budget.
- **Observability Gate**: PASS. Implementations use language-standard loggers,
  runtime-reconfigurable levels/sinks, and OpenTelemetry-compatible redirection;
  discovery requests emit correlation-friendly structured logs without leaking
  caller credentials.
- **Domain Organization Gate**: PASS. Packages are organized by domain capability
  with discoverable public entry points across Python/.NET/Java; discovery lands
  in its own `discovery` domain rather than inside the endpoint transport layer.
- **Language Idiom Gate**: PASS. Descriptors, capability sets, skills, and
  discovery configuration are modeled as explicit typed constructs in all three
  languages rather than untyped maps; the provider dialect, discovery surface,
  visibility mode, and capability size unit are modeled as enumerations; the
  visibility rule and the discovery projections are declared as explicit
  abstractions selected at runtime.
- **Adoption Examples Gate**: PASS. Feature includes runnable examples strategy:
  .NET on Microsoft Agent Framework, Python on LangChain + FastAPI, Java on
  Spring AI + Spring Boot unless approved alternative is documented; each example
  declares a descriptor and exposes all three discovery surfaces.
- **Middleware Pipeline Gate**: PASS. Pipeline contract supports ordered middleware
  chain with inspect/modify hooks before and after core handler execution.
- **Discovery Truthfulness Gate**: PASS. Declared capability claims are validated
  at initialization against actual endpoint configuration, every advertised agent
  identifier is round-trip tested as an invocation target, and shared attributes
  are asserted equal across all three projections.

Post-design constitution check: PASS (no violations requiring justification).

## Project Structure

### Documentation (this feature)

```text
specs/001-openai-endpoint-exposure/
├── plan.md              # This file (/speckit.plan command output)
├── research.md          # Phase 0 output (/speckit.plan command)
├── data-model.md        # Phase 1 output (/speckit.plan command)
├── quickstart.md        # Phase 1 output (/speckit.plan command)
├── contracts/           # Phase 1 output (/speckit.plan command)
│   ├── endpoint-surface-contract.md
│   ├── standard-exchange-v1.schema.json
│   └── agent-descriptor-v1.schema.json
└── tasks.md             # Phase 2 output (/speckit.tasks command - NOT created by /speckit.plan)
```

### Source Code (repository root)

```text
packages/
├── python/
│   └── ygo74/agent_runtime/
│       ├── middleware/
│       ├── observability/
│       ├── routing/
│       └── domains/
│           ├── auth/
│           ├── configuration/
│           ├── contracts/
│           ├── discovery/
│           ├── endpoints/
│           ├── handlers/
│           ├── mapping/
│           └── streaming/
├── dotnet/
│   └── Ygo74.AgentRuntime/
│       ├── Middleware/
│       ├── Observability/
│       ├── Routing/
│       └── Domains/
│           ├── Auth/
│           ├── Configuration/
│           ├── Contracts/
│           ├── Discovery/
│           ├── Endpoints/
│           ├── Handlers/
│           ├── Mapping/
│           └── Streaming/
└── java/
  └── ygo74-agent-runtime/
      ├── middleware/
      ├── observability/
      ├── routing/
      └── domains/
          ├── auth/
          ├── configuration/
          ├── contracts/
          ├── discovery/
          ├── endpoints/
          ├── handlers/
          ├── mapping/
          └── streaming/

tests/
├── contract/
├── integration/
├── parity/
└── performance/

docs/
└── examples/
    ├── dotnet-agentframework/
    ├── python-langchain-fastapi/
    └── java-springai-springboot/
```

**Structure Decision**: Multi-package library monorepo structure selected to
support equivalent language-specific SDKs with shared cross-language contracts.
Discovery is introduced as a sibling domain (`discovery`) to `endpoints`, holding
the descriptor model, the registry, and the three projections, so the invocation
path and the discovery path share the route-key registry without either depending
on the other's transport concerns.

## Complexity Tracking

> **Fill ONLY if Constitution Check has violations that must be justified**

|Violation|Why Needed|Simpler Alternative Rejected Because|
|---|---|---|
|None|N/A|N/A|
