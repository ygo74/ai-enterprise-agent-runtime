---
name: feature-specification
description: Turn a user request into a reviewable repository change specification using only the relevant system context and role reference.
---

# Feature specification

Read the current `spec/README.md` and only the domain pages relevant to the
request. Inspect affected APIs, code, tests, examples, and documentation enough
to separate current behavior from requested behavior. An Issue is optional; do
not create one.

Use the [tracking artifact templates](../development-workflow/references/artifact-templates.md)
when useful. Create `SPEC.md` in the canonical request tracking folder. Include request
source and repository scope, goal, current context, expected behavior,
acceptance criteria, non-goals, constraints, risks, open questions, and impacts
on public contracts, parity, security, performance, examples, and docs when
relevant. Do not turn assumptions into requirements.

Choose role guidance based on the primary outcome and technology: this runtime
is a technical library, so read the matching Solution Architect reference from
the [implementation-plan references](../implementation-plan/references/) for
Python, .NET, or Java. For mixed requests, use the role matching the main
outcome and list the other concerns; ask the user only if that outcome cannot
be inferred.

Present the SPEC path, concise summary, key decisions, and unresolved questions.
Wait for explicit approval before planning or implementation.
