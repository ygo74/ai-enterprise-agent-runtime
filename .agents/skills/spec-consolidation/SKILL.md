---
name: spec-consolidation
description: Update the consolidated runtime specification to describe validated current behavior under spec/.
---

# Consolidate the system specification

For a request limited to consolidating current repository behavior, use this
skill directly after the repository branch is selected by
[development-workflow](../development-workflow/SKILL.md). Do not create or
update a development request SPEC or PLAN for consolidation-only work. If
consolidation is part of an implementation request, update the consolidated
specification after behavior is validated without amending the request SPEC or
PLAN solely for that documentation phase.

Run when requested by the user or included in the approved change. Begin at
`spec/README.md` and inspect only the relevant domain pages. Use implementation,
tests, and accepted validation as evidence; planned behavior and a task SPEC do
not prove delivery.

Revise existing pages where they fit; add a focused page only for a durable
system concept. Describe current responsibilities, flows, contracts, and
constraints without turning `spec/` into an issue history. Update the index,
user or contributor guides, examples, and links when needed. Check descriptions
against code and tests and record unverified claims as open items.
