---
name: implementation-plan
description: Analyze the existing runtime architecture and prepare an implementation plan for an approved specification.
---

# Implementation plan

Use only after the new or amended SPEC is approved. Read the affected Solution
Architect reference under `references/` for each technology in scope; load no
unrelated language reference. Use the
[tracking artifact templates](../development-workflow/references/artifact-templates.md).
Inspect existing code, abstractions, packages, contracts, tests,
docs, and examples before selecting changes.

Create a new `PLAN.md` for a new tracking folder or amend the existing branch's
PLAN in place. Keep previously completed work clear, add the new scope and
decisions as an amendment, and do not create another tracking folder for an
existing remote branch. The plan must name repository/file areas, dependencies,
migration and compatibility effects, reuse decisions, test-first validation,
docs/examples, security and performance checks when applicable, and completion
criteria. Keep the solution DRY and SOLID, class-oriented where it clarifies responsibility,
with early exits and no speculative abstractions. A junior developer should be
able to follow and debug the design. Record parity impacts across Python, .NET,
and Java and any proposed exception.

Present the complete new or amended `PLAN.md`, affected repositories, major
decisions, risks, and validation approach. Wait for explicit user approval
before creating or extending implementation tasks or changing implementation
files.
