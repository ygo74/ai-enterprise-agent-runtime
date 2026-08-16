<!--
Sync Impact Report
- Version change: 1.1.0 -> 1.2.0
- Modified principles:
  - None
- Added sections:
  - Language Idiom and Type Safety Standards
- Removed sections:
  - None
- Templates requiring updates:
  - ✅ updated: .specify/templates/plan-template.md (added Language Idiom Gate)
  - ✅ checked/no change needed: .specify/templates/spec-template.md
  - ✅ checked/no change needed: .specify/templates/tasks-template.md
  - ⚠ pending: .specify/templates/commands/*.md (directory not present)
  - ✅ checked/no change needed: .github/copilot-instructions.md
  - ✅ aligned: .github/instructions/python.instructions.md (applyTo `**/*.py`)
- Deferred TODOs:
  - None
-->

# AI Enterprise Agent Runtime Constitution

## Core Principles

### I. Cross-Language Behavioral Parity

Every capability MUST be defined as a language-neutral contract and implemented
with equivalent behavior across Python, .NET, and Java libraries. Public APIs,
error semantics, configuration keys, and observable side effects MUST match the
approved contract unless a documented platform constraint is accepted in writing.
Rationale: this project exists to provide one agent feature set that integrates
consistently into multiple client ecosystems.

### II. DRY-First Reuse + SOLID + Early-Leave Simplicity

All production code MUST apply DRY and SOLID principles and MUST prefer
early-return/early-exit control flow to limit nesting and cognitive complexity.
Before creating any new class, function, or module, contributors MUST first
search the codebase for existing reusable implementations and document the
decision: extend/reuse existing code or create new code with justification.
Functions and methods MUST remain small, single-purpose, and composable; complex
branching MUST be extracted into named units with clear interfaces. Rationale:
reuse-first discipline prevents duplication and keeps cross-language parity
maintainable over time.

### III. Test-First Quality Gates (NON-NEGOTIABLE)

Development MUST follow a test-first cycle: define contract and acceptance tests,
write failing tests, implement the minimal change, then refactor while keeping
tests green. Unit, integration, and cross-language parity tests are mandatory
for all new features and behavior changes. Merges are blocked unless all required
quality gates pass in CI for Python, .NET, and Java. Rationale: test-first
discipline is required to preserve correctness across multiple runtimes.

### IV. User Experience Consistency by Contract

User-facing behavior (input schema, output schema, error wording classes,
interaction flow, and defaults) MUST be specified and validated as part of the
feature contract. Any UX deviation between language implementations MUST be
treated as a defect unless explicitly approved and documented with migration
guidance. Rationale: consumers adopt these libraries to gain a predictable
standalone agent experience independent of implementation language.

### V. Performance Budgets and Regression Control

Each feature MUST define measurable performance budgets (latency, throughput,
memory, and startup where applicable) and include automated regression checks.
Changes that violate budgets MUST not be released without a documented exception,
owner approval, and remediation timeline. Rationale: consistent performance is a
product requirement for multi-client agent integrations.

## Multi-Language Library Standards

- Libraries MUST be packaged for direct inclusion in Python, .NET, and Java
  projects with equivalent versioned capabilities.
- Semantic versioning MUST be applied consistently across language artifacts;
  breaking contract changes require a major version increment.
- Shared contracts (schemas, protocol docs, examples) MUST be source-controlled
  and versioned with compatibility notes.
- Observability surfaces (structured logs, error codes, tracing fields) SHOULD
  use a common naming convention across languages.

## Observability and Logging Standards

- Implementations MUST use the standard logging mechanisms of each language
  ecosystem so runtime operators can reconfigure logging without code changes.
- Logging configuration MUST support level changes and sink redirection through
  host-standard mechanisms (for example OpenTelemetry pipeline integration).
- Logs MUST include correlation-friendly fields (for example request ID, route
  key, and error category) while avoiding sensitive payload leakage.

## Domain-Oriented Package Organization

- Features MUST be organized into domain-oriented namespaces/packages/modules
  that reflect business capabilities and are easy to discover.
- Public APIs MUST expose domain entry points that are coherent, documented,
  and stable across Python, .NET, and Java equivalents.
- Cross-domain shared utilities MUST remain minimal and MUST NOT hide domain
  boundaries or create circular dependencies.

## Language Idiom and Type Safety Standards

These standards keep the three implementations structurally comparable, which is
what makes cross-language parity reviewable rather than merely asserted.

- Behavior MUST be organized into cohesive classes or types. Free-standing
  functions are permitted only for pure, stateless utilities that belong to no
  type; related helpers MUST NOT be scattered across a module.
- Structured data MUST be represented by explicit typed constructs, never by
  untyped maps. Python uses dataclasses, `NamedTuple`, or validated models;
  .NET uses records or classes; Java uses records or classes. Dictionaries, maps,
  and hashtables are reserved for genuine key/value collections and for raw wire
  payloads at the system boundary.
- Wire payloads MUST be converted into typed objects at the boundary and back to
  serializable form only on output.
- A property that accepts a fixed set of text values MUST be modeled as an
  enumeration (`Enum`/`StrEnum`, `enum`, Java `enum`), not as bare string
  literals compared across modules.
- Contracts shared by interchangeable implementations MUST be declared as
  explicit abstractions (Python `Protocol`, .NET interface, Java interface), with
  the concrete implementation selected at runtime from the incoming data.
- All public and internal APIs MUST be fully type-annotated and MUST pass the
  strict static analysis configuration of their language toolchain.
- Language-specific elaborations of these rules live in repository instruction
  files and MUST stay consistent with this section.

## Example-First Adoption Guidance

- Each new feature implementation MUST include runnable usage examples that show
  configuration and expected behavior.
- Example defaults:
  - .NET agent examples MUST use Microsoft Agent Framework.
  - Python agent examples MUST use LangChain with FastAPI.
  - Java agent examples SHOULD use Spring AI with Spring Boot unless an approved
    alternative is documented.
- Examples MUST be versioned alongside feature contracts and updated when
  behavior or configuration changes.

## Delivery Workflow and Release Gates

- Each specification MUST include: parity impact, UX consistency criteria,
  mandatory test scope, and explicit performance budgets.
- Each implementation plan MUST pass a Constitution Check before development and
  before merge readiness.
- Each task breakdown MUST include contract, parity, and performance validation
  tasks for the affected feature.
- Each implementation MUST include evidence of reuse search for impacted areas
  (existing classes/functions reviewed, reuse decision recorded).
- Each implementation MUST conform to the Language Idiom and Type Safety
  Standards; reviewers MUST reject untyped data containers and bare string
  literals used in place of enumerations.
- Pull requests MUST include evidence of: test-first sequence, CI matrix pass
  across Python/.NET/Java, and performance regression status.

## Governance

This constitution supersedes conflicting local practices for this repository.
Amendments require: (1) proposed text diff, (2) rationale and migration impact,
(3) approval from project maintainers, and (4) updates to affected templates and
automation artifacts in the same change set.

Versioning policy:

- MAJOR: principle removal, redefinition, or governance changes that alter
  compliance obligations.
- MINOR: new principle/section or materially expanded mandatory guidance.
- PATCH: clarifications, wording improvements, typo fixes, and non-semantic edits.

Compliance review expectations:

- Constitution compliance MUST be checked during plan review, pull request
  review, and release readiness review.
- Non-compliance MUST be tracked as a blocking issue or an explicit time-bound
  exception approved by maintainers.

**Version**: 1.2.0 | **Ratified**: 2026-07-31 | **Last Amended**: 2026-08-16
