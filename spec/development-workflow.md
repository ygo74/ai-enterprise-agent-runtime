# Development workflow and engineering principles

This page describes the repository's current contribution workflow and durable
engineering rules. Start each new request from the consolidated system pages in
[`README.md`](README.md); request tracking files under
[`implementation/`](implementation/README.md) record one change and are not
user documentation.

## Request workflow

Both ad hoc requests and requests linked to an Issue use the repository-local
skills under [`.agents/skills/`](../.agents/skills/):

| Phase | Skill | Result |
|---|---|---|
| Route and track | `development-workflow` | Select primary/secondary repositories and create one canonical request record. |
| Specify | `feature-specification` | Draft `SPEC.md` from the user request and relevant current system pages. |
| Plan | `implementation-plan` | Inspect current architecture and prepare `PLAN.md` for affected languages. |
| Break down | `implementation-tasks` | Create ordered, repository-scoped `TASKS.md` after PLAN approval. |
| Implement | `test-driven-implementation` | Follow tasks test-first, update progress, and route improvements for scope review. |
| Coordinate | `multi-repo-coordination` | Keep repository branches, commits, validations, and pull requests separate. |
| Consolidate and deliver | `spec-consolidation`, `repository-delivery` | Update verified current behavior and prepare reviewed changes when in scope. |

SPEC and PLAN each require explicit user approval. Tasks do not add another
approval gate. Behavior changes use a failing test, minimal passing
implementation, then refactoring with relevant checks still passing. Record
decisions, actual validation, and deviations in the primary request's
`JOURNAL.md`. The implementation agent routes newly discovered improvements to
the Solution Architect, who decides whether each belongs in approved scope or
should be proposed separately.

The canonical request directory is
`spec/implementation/<issue-N-or-adhoc-slug>/` with `SPEC.md`, `PLAN.md`,
`TASKS.md`, and `JOURNAL.md`. Multi-repository work keeps one request record in
the primary repository and separate Git histories in each repository. A new
request starts from this consolidated system specification, not an earlier
request record.

## Role selection and context loading

The runtime is a technical library. Specification and plan work load the
Solution Architect reference for the affected technology: Python, .NET, or
Java. Load no unrelated technology reference. A separate repository that
primarily builds user-facing agent behavior may use a Business Analyst role for
its SPEC, then its technology-specific Solution Architect for the PLAN.

Implementation loads the relevant implementation-expert reference. Role
references are linked from the applicable skills, so an agent reads detailed
guidance only for the current request and stack.

## Engineering principles

- **Cross-language contracts:** define shared behavior neutrally and preserve
  Python/.NET/Java equivalence. Record approved platform exceptions and their
  scope; do not imply deferred behavior is delivered.
- **Reuse and simplicity:** inspect existing code first. Prefer DRY, SOLID,
  focused responsibilities, clear domain boundaries, early exits, and simple
  implementations. Record whether existing code is reused or new code is
  justified. Avoid speculative extension points.
- **Typed design:** use cohesive classes/types; use dataclasses, `NamedTuple`,
  or validated models in Python, and records/classes in .NET and Java. Use
  enums for finite values. Convert raw wire data at boundaries rather than
  passing untyped maps through domain code.
- **Test-first quality:** add or update the relevant failing contract or
  acceptance test before behavior code. Validate at unit and, where relevant,
  integration, parity, performance, and security levels. Apply repository
  quality gates to each affected package.
- **Consistent user experience:** specify and validate input/output contracts,
  error categories, defaults, and interaction flows. Treat unapproved
  cross-language differences as defects.
- **Measured performance:** set measurable budgets when latency, throughput,
  memory, or startup is material. Report evidence and seek maintainer approval
  for a budget exception and remediation plan.
- **Safe observability:** use host-standard logging and correlation fields.
  Keep credentials, secrets, and sensitive request/response payloads out of
  logs and traces.
- **Runnable adoption examples:** update examples with public behavior. Defaults
  are Python LangChain/FastAPI, .NET Microsoft Agent Framework, and Java Spring
  AI/Spring Boot unless the approved design specifies otherwise.
- **Compatibility and release readiness:** document schema/API migrations,
  package compatibility, and parity limits. Check examples and performance
  evidence before release readiness. Track a violation as a blocking item or a
  maintainer-approved, time-bound exception.

Use focused reviews for the change's actual surface. Do not claim a parity,
performance, or security gate passed without the corresponding evidence.
