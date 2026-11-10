---
name: test-driven-implementation
description: Implement approved repository tasks with test-first changes, progress tracking, and architect-reviewed scope follow-ups.
---

# Test-driven implementation

Use the approved `SPEC.md`, `PLAN.md`, and `TASKS.md` as the work boundary.
Load the implementation-expert reference for each affected technology from
`references/`; read no unrelated reference. Inspect the exact code and tests
before editing and record what existing implementation was considered for reuse.

For behavior changes, write or update the relevant failing test first, make the
smallest change that passes it, then refactor with checks still passing. Keep
types explicit, responsibilities cohesive, control flow shallow, and code easy
for a junior developer to understand and debug. Use the frameworks and public
APIs already adopted by the repository; avoid speculative abstractions.

Update task status and `JOURNAL.md` as work proceeds. Record decisions,
commands actually run, results, and deviations. If an improvement appears,
describe its evidence and submit it to the Solution Architect for classification
as in-scope work or a follow-up proposal. Implement it in this phase only when
it is required by the approved scope. Ask the user before a material scope
change.

At completion, summarize changes, completed tasks, validation, and deferred
proposals for user review. Documentation or version skills run after acceptance
when requested or already included in the approved plan.
