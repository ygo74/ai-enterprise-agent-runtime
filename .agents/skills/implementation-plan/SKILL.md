---
name: implementation-plan
description: Analyze the existing runtime architecture and prepare an implementation plan for an approved specification.
---

# Implementation plan

Use only after SPEC approval. Read the affected Solution Architect reference
under `references/` for each technology in scope; load no unrelated language
reference. Use the [tracking artifact templates](../development-workflow/references/artifact-templates.md).
Inspect existing code, abstractions, packages, contracts, tests,
docs, and examples before selecting changes.

The plan must name repository/file areas, dependencies, migration and
compatibility effects, reuse decisions, test-first validation, docs/examples,
security and performance checks when applicable, and completion criteria. Keep
the solution DRY and SOLID, class-oriented where it clarifies responsibility,
with early exits and no speculative abstractions. A junior developer should be
able to follow and debug the design. Record parity impacts across Python, .NET,
and Java and any proposed exception.

Present `PLAN.md`, affected repositories, major decisions, risks, and validation
approach. Wait for explicit user approval before creating implementation tasks
or changing implementation files.
