# Request tracking templates

Use these templates when the repository has no more specific format. Omit
irrelevant sections and add what makes an important decision reviewable.

## `SPEC.md`

```markdown
# Specification

## Request source and repositories
## Objective and current context
## Scope and exclusions
## Expected behavior
## Architecture, interfaces, and data
## Constraints and decisions
## Acceptance criteria
## Validation impact
## Risks and open questions
```

An Issue is optional. For cross-repository work, name the primary and secondary
repositories and explain their roles.

## `PLAN.md`

```markdown
# Implementation Plan

## Approved SPEC
## Existing architecture and reuse analysis
## Repository and component scope
## Ordered steps and dependencies
## Test-first validation
## Compatibility, security, and performance
## Documentation and examples
## Risks and completion criteria
```

Separate changes and validations by repository. Record the relevant Solution
Architect reference and each reuse decision.

## `TASKS.md`

```markdown
# Implementation Tasks

- [ ] REPO-001 Add a failing contract test; completion: ...; depends on: ...
- [ ] REPO-002 Implement the smallest behavior change; completion: ...; depends on: REPO-001
```

Use ordered, repository-prefixed tasks with observable completion criteria and
test dependencies. Include documentation and nonfunctional gates only when
required by approved scope.

## `JOURNAL.md`

Record approved scope, repositories and branches, progress, material decisions,
actual validation commands/results, deviations, and architect-reviewed follow-up
proposals. Never mark a check passed unless it was run and passed.
```
