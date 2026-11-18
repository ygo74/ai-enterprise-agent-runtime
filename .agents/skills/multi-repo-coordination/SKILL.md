---
name: multi-repo-coordination
description: Coordinate a request that changes this runtime and one or more related Git repositories under the shared workspace.
---

# Multi-repository coordination

Identify the primary repository by the request's main outcome and name every
repository's role in the SPEC. An Issue is optional. For every affected
repository independently, inspect the working tree and current branch and
successfully refresh `origin` (for example, with `git fetch origin --prune`)
before selecting a branch. Verify `origin/main` before basing a branch on it.
Continue on a non-main branch that still exists on `origin`; from `main` or a
non-main branch no
longer on `origin`, create a request branch from the latest `origin/main`.
Preserve uncommitted changes and old local branches; do not switch with
uncommitted work or use stale remote refs. If origin cannot be refreshed, stop
before deciding.

Keep one canonical SPEC/PLAN/TASKS/JOURNAL in the primary repository. If its
current non-main branch still exists on `origin`, update the uniquely matching
request record in place. Find it by Issue identifier, branch recorded in
`JOURNAL.md`, and request scope; prefer the matching record whose TASKS/JOURNAL
show related work is active. If the relevant record is ambiguous, ask the user;
do not create a competing folder. If the primary repository is on `main` or its
branch no longer exists on `origin`, create new canonical tracking on the new
request branch. Record secondary branch choices and validation in the primary
journal; do not duplicate request tracking in secondary repositories.

Read each repository's local instructions and current consolidated
specification, and inspect cross-repository public contracts and dependency
directions.

The PLAN assigns every change, task, validation, branch, and pull request to a
repository and states dependency order. Keep branches and Git histories
separate. Maintain one canonical request record in the primary repository and
record secondary branch and validation status in the canonical journal. Do not
duplicate request histories or expand scope because a related repository was
discovered.

If an additional repository materially changes approved scope, update the
existing canonical SPEC and PLAN and obtain approval before implementation.
Link related pull requests when prepared; do not merge them.
