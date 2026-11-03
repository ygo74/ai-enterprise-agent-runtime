---
name: development-workflow
description: Route an ad hoc or Issue-linked repository change through approved specification, architecture plan, implementation tasks, and test-driven delivery.
---

# Development workflow

Start new work from the user's request and the current system specification in
`spec/README.md`. An Issue may provide context, but is optional; never create
one unless asked.

1. Identify the primary repository and any secondary repositories. Read the
   relevant `AGENTS.md`, `WORKFLOW.md`, and consolidated domain pages.
2. Use [feature-specification](../feature-specification/SKILL.md) to create a
   request record at `spec/implementation/<issue-N-or-adhoc-slug>/SPEC.md`.
   Present it and wait for explicit user approval.
3. After SPEC approval, use [implementation-plan](../implementation-plan/SKILL.md)
   to inspect the codebase and prepare `PLAN.md`. Present it and wait for
   explicit approval.
4. After plan approval, use [implementation-tasks](../implementation-tasks/SKILL.md)
   to create ordered `TASKS.md`; then use
   [test-driven-implementation](../test-driven-implementation/SKILL.md).
5. Record progress, actual checks, decisions, and plan deviations in
   `JOURNAL.md`. Refer discovered improvements to the Solution Architect for
   an in-scope or follow-up decision.
6. Present the implementation for user review. After acceptance, run the
   documentation, consolidation, or version skills requested by the user or
   included in the approved plan.

For more than one repository, also use
[multi-repo-coordination](../multi-repo-coordination/SKILL.md). Keep Git
histories separate and keep the canonical request record in the primary repo.

Do not proceed past either approval gate until the user approves that artifact.
Task creation has no additional approval gate. Never merge a pull request or
publish a release without explicit authorization.
