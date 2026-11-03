---
name: multi-repo-coordination
description: Coordinate a request that changes this runtime and one or more related Git repositories under the shared workspace.
---

# Multi-repository coordination

Identify the primary repository by the request's main outcome and name every
repository's role in the SPEC. An Issue is optional. Read each repository's
local instructions and current consolidated specification, and inspect
cross-repository public contracts and dependency directions.

The PLAN assigns every change, task, validation, branch, and pull request to a
repository and states dependency order. Keep branches and Git histories
separate. Maintain one canonical request record in the primary repository and
record secondary branch and validation status in its journal. Do not duplicate
request histories or expand scope because a related repository was discovered.

If an additional repository materially changes approved scope, update SPEC and
PLAN and obtain approval before implementation. Link related pull requests when
they are prepared; do not merge them.
