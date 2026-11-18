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
when useful. Follow the branch and tracking decision in
[development-workflow](../development-workflow/SKILL.md): create a new
`SPEC.md` only for a new request branch, or amend the SPEC already associated
with the continuing remote branch. Preserve its prior scope and record the new
request as a clearly marked amendment with acceptance criteria; do not create
a second folder for that branch. If the existing record cannot be identified
uniquely, stop and ask.

Store the canonical SPEC in the primary repository's tracking folder. Include
request source and repository scope, goal, current context, expected behavior,
acceptance criteria, non-goals, constraints, risks, open questions, and impacts
on public contracts, parity, security, performance, examples, and docs when
relevant. Do not turn assumptions into requirements.

Choose role guidance based on the primary outcome and technology: this runtime
is a technical library, so read the matching Solution Architect reference from
the [implementation-plan references](../implementation-plan/references/) for
Python, .NET, or Java. For mixed requests, use the role matching the main
outcome and list the other concerns; ask the user only if that outcome cannot
be inferred.

Present the complete new or amended SPEC path, concise summary, key decisions,
and unresolved questions. Wait for explicit approval before preparing or
amending the plan.
