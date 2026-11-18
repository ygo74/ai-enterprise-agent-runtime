---
name: development-workflow
description: Route an ad hoc or Issue-linked repository change through approved specification, architecture plan, implementation tasks, and test-driven delivery.
---

# Development workflow

Start by classifying the request and checking repository state. An Issue may
provide context, but is optional; never create one unless asked.

For a request limited to user documentation, contributor documentation, or
global specification consolidation, do not create or update a development
request SPEC/PLAN. Apply the branch selection rules below, then invoke the
corresponding skill directly. If the request also changes implementation
behavior, use the full development workflow.

For each affected repository, inspect its working tree and current branch, then
successfully refresh `origin` (for example, with `git fetch origin --prune`)
before choosing a branch. Do not use stale remote-tracking refs as evidence of
a live remote branch; verify `origin/main` before basing a new branch on it.

- If the current branch is `main`, fetch the latest `origin/main` and create a
  request branch from it. Create a new canonical SPEC and PLAN in the primary
  repository.
- If the current branch is not `main` and still exists on `origin`, continue on
  that branch. Update its existing canonical SPEC and PLAN in place; do not
  create another tracking folder.
- If the current branch is not `main` and no longer exists on `origin`, fetch
  the latest `origin/main` and create a new request branch from it. Preserve
  the old local branch and commits, and create a new canonical SPEC and PLAN
  in the primary repository.

Do not switch branches with uncommitted changes or discard them. If `origin`
cannot be refreshed, stop before making a branch decision. For an existing
remote branch, identify the relevant tracking folder by its Issue identifier,
branch in `JOURNAL.md`, and request scope. Prefer the single record whose
TASKS/JOURNAL show the related work is active. If the relevant record is still
ambiguous, ask which one to continue instead of creating a new one. In a
multi-repo request, make the branch decision independently in every repository
while keeping the sole canonical SPEC/PLAN/TASKS/JOURNAL in the primary
repository; record secondary branch state in the canonical journal.

1. Identify the primary and secondary repositories, apply branch selection,
   then read local `AGENTS.md`, `WORKFLOW.md`, and relevant consolidated pages.
2. Use [feature-specification](../feature-specification/SKILL.md) to create a
   new canonical `SPEC.md` or amend the existing branch's SPEC. Present the
   complete current SPEC and wait for explicit user approval.
3. After approval, use [implementation-plan](../implementation-plan/SKILL.md)
   to inspect the codebase and create or amend `PLAN.md`. Present the complete
   current plan and wait for explicit approval.
4. After plan approval, use [implementation-tasks](../implementation-tasks/SKILL.md)
   to create or extend the ordered `TASKS.md`, then use
   [test-driven-implementation](../test-driven-implementation/SKILL.md).
5. Record progress, actual checks, decisions, and plan deviations in
   `JOURNAL.md`. Refer discovered improvements to the Solution Architect for
   an in-scope or follow-up decision.
6. Present the implementation for user review. After acceptance, run the
   documentation, consolidation, or version skills requested by the user or
   included in the approved plan; those phases do not require SPEC/PLAN
   amendments unless implementation scope also changes.

For more than one repository, also use
[multi-repo-coordination](../multi-repo-coordination/SKILL.md). Keep Git
histories separate and keep the canonical request record in the primary repo.

Do not proceed past either approval gate until the user approves that artifact,
including an amendment. Task creation has no additional approval gate. Never
merge a pull request or publish a release without explicit authorization.
