---
name: repository-delivery
description: Review and prepare validated repository changes for commits and pull requests while preserving release and merge boundaries.
---

# Repository delivery

Follow the approved plan and repository hosting conventions. Before delivery,
review the full diff, status, generated files, secrets, links, and
`git diff --check`; run the validations that the plan requires and report only
actual results. Keep commits focused and repository histories independent.

When a commit or push is requested, follow the
[origin-push skill](../origin-push/SKILL.md). It requires Ruff and pytest for
every change that includes Python files.

Push only the approved working branches and prepare linked pull requests when
the user or approved plan requests them. Never merge. A release action, package
publication, or Git tag that triggers publication requires explicit user
authorization immediately before the action.
