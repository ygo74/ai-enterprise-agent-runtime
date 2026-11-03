# Implementation Journal

## Approved scope

- Ad hoc request; no GitHub Issue is being created.
- SPEC and PLAN approved by the user.
- Primary repository: `ai-enterprise-agent-runtime`.
- Secondary repository: `ai_agents`.
- Feature `001` and its 67 unfinished tasks are migrated as tracking material only; those behaviors are not implemented in this change.

## Branches and starting state

| Repository | Branch | Starting commit | Initial changes |
|---|---|---|---|
| `ai-enterprise-agent-runtime` | `chore/adhoc-repo-local-vibe-workflow` | `ddd12dcd05351e5790063a061f1d6d9768848b72` | Approved temporary SPEC and PLAN in this tracking directory |
| `ai_agents` | `chore/adhoc-repo-local-vibe-workflow` | `2af080d70ca7762336120352f795d5336623c1a6` | None |

## Progress

- 2026-11-03: Confirmed both repositories started on `main` at `origin/main`; no pre-existing changes in `ai_agents`. Created the approved work branch in each repository.
- 2026-11-03: Read workspace instructions, repository guidance, current runtime constitution, existing system specifications, and parent workflow skills. The runtime currently has no `WORKFLOW.md`; `ai_agents` has neither root `AGENTS.md` nor `WORKFLOW.md`.
- 2026-11-03: Added this task checklist and journal after PLAN approval.
- 2026-11-03: Audited the feature-001 source task file: it contains 206 checklist entries (139 checked and 67 unchecked). This source count supersedes the earlier 389-complete estimate in the initial PLAN/SPEC analysis; all 67 open entries remain in scope for migration only.

## Decisions and evidence

- Parent workflow guidance requires an Issue by default, but this request is explicitly ad hoc. The new repository skills will treat Issue linking as optional and will never create one automatically.
- The image workflow in `ai_agents` publishes containers for `v*` tags; tag creation/pushing remains an explicit release action and will not be performed while adding the skill.

## Source-to-destination audit

| Removed or retired source | Verified destination or disposition |
|---|---|
| `.specify/memory/constitution.md` | Durable rules split between root `AGENTS.md`, `WORKFLOW.md`, the consolidated workflow specification, and language-specific architect/implementation references. The nine migration principles in the PLAN are represented across those files. |
| `.specify/templates/spec-template.md`, `plan-template.md`, `tasks-template.md`, and `checklist-template.md` | Request content, approval gates, task ordering, and required validation are represented by the local specification, plan, and task skills. Shared request artifact shapes live in `development-workflow/references/artifact-templates.md`. No parallel feature-readiness checklist is required. |
| `.specify/templates/constitution-template.md` | Replaced by repository-owned `AGENTS.md`, `WORKFLOW.md`, and focused role references; no separately versioned constitution document remains. |
| `.specify/scripts/powershell/*` | No equivalent scripts are needed: their feature selection, prerequisites, setup, and generation responsibilities now belong to the workflow skills and canonical `spec/implementation/` record. |
| `.specify/feature.json`, `init-options.json`, `integration.json`, integration manifests, extension registry, and workflow registry | Active feature pointers and Speckit integration state are retired. The development skill chooses a request folder; editor-specific instructions point to `AGENTS.md` and `WORKFLOW.md`. |
| `.specify/extensions/agent-context/*` and `.github/agents/speckit.agent-context.update.agent.md` | Managed Copilot context markers are retired. `.github/copilot-instructions.md` is now a short pointer to repository guidance and the current system specification. |
| `.github/agents/speckit.*` and `.github/prompts/speckit.*` | Applicable phases are mapped to `development-workflow`, `feature-specification`, `implementation-plan`, `implementation-tasks`, `test-driven-implementation`, `spec-consolidation`, and `repository-delivery`; command-only operations with no new workflow role are removed. |
| `specs/001-openai-endpoint-exposure/spec.md`, `plan.md`, and `tasks.md` | Migrated to `spec/implementation/adhoc-openai-anthropic-endpoints/{SPEC,PLAN,TASKS,JOURNAL}.md`; all 206 task IDs and check states are preserved. |
| Feature `001` data model and endpoint, typed-output, native-hosting contracts | Consolidated into `spec/contracts/`, `spec/endpoints/`, `spec/discovery/`, `spec/security/`, `spec/integrations/`, and the existing Python/contributor guides; the feature migration journal records the detailed mapping. |
| Feature `001` research and decisions | Current architecture and contract pages now express dispatch and exchange boundaries, auth/authorization ownership, framework-native configuration, streaming, error contracts, performance budgets, descriptor/discovery projections, capability validation, and initialization-time immutability. |
| Feature `001` quickstart scenarios 1–12 and readiness checklist | Implemented behavior is described in current guides and specifications and backed by repository tests; the checklist's acceptance criteria are reflected by the migrated feature SPEC and PLAN. |
| Feature `001` quickstart scenarios 13–17 | Remaining discovery scenarios are retained in `spec/implementation/adhoc-openai-anthropic-endpoints/references/discovery-validation-scenarios.md` and linked from the migrated TASKS/JOURNAL. |
| Three feature `001` JSON schemas | Moved to `spec/contracts/`; the four affected runtime tests now point to the canonical paths. |
| `/data/repos/.agents/skills/issue-driven-development/` and request templates | Replaced by local `development-workflow`, `feature-specification`, `implementation-plan`, `implementation-tasks`, `test-driven-implementation`, and `repository-delivery` skills plus `development-workflow/references/artifact-templates.md` in both repositories. Both local entry skills accept ad hoc requests and optional Issues. |
| `/data/repos/.agents/skills/multi-repo-coordination/` | Replaced by repository-local coordination skills in both repositories, with separate histories and one canonical primary-repository request record. |
| `/data/repos/.agents/skills/spec-consolidation/` | Replaced by repository-local consolidation skills tied to each repository's current `spec/` pages and verified behavior. |
| `/data/repos/.agents/skills/backend-architect/` | Replaced by runtime Python/.NET/Java architect references and the `ai_agents` Python architect reference, linked from the local planning skills. |

The old configuration, scripts, prompts, agents, and feature directory were
removed after this mapping and the matching destination files were reviewed
together. The migrated feature task file retains all 206 IDs and the 139
checked / 67 open status split.

## Temporary SPEC comparison and removal evidence

Before removing the temporary SPEC, every durable requirement was compared with
both repositories' local instructions and consolidated workflow pages:

| Requirement area | Durable destination |
|---|---|
| Ad hoc requests and optional Issue association; SPEC and PLAN approval gates; ordered tasks without a third gate | Both repository `WORKFLOW.md` files, both `development-workflow` skills, both specification/planning/task skills, and both consolidated workflow pages. |
| Functional Business Analyst versus technical Solution Architect selection in `ai_agents` | `ai_agents/WORKFLOW.md`, its `feature-specification` skill, and its Business Analyst / Python Solution Architect references. |
| Technology-matched runtime architecture planning and implementation | Runtime planning/task/implementation skills and Python, .NET, and Java architect/expert references. |
| Existing architecture analysis; DRY, SOLID, class-based cohesion, early exits, reuse, and junior-readable code | Both local `AGENTS.md` and `WORKFLOW.md` files and the relevant architecture/implementation references. |
| TDD sequence, progress tracking, scope routing for discovered improvements | Both `test-driven-implementation` skills, both workflow pages, and request tracking conventions. |
| Developer-only request tracking and starting future work from consolidated behavior | Both `spec/development-workflow.md` pages, `spec/README.md` indexes, and the runtime `spec/implementation/README.md`. |
| Post-acceptance consolidation, user docs, contributor docs, and version work | Both `WORKFLOW.md` files and the preserved repository-local documentation, consolidation, delivery, and version skills. |
| Runtime constitution: parity, contracts, reuse, test gates, user behavior, performance, packages/versioning, observability, typed domain design, examples, delivery, and compliance | Runtime `AGENTS.md`, `WORKFLOW.md`, consolidated workflow spec, language-specific architect/expert references, and the local planning, task, TDD, and delivery skills. |
| `ai_agents` image release versioning | `ai_agents/.agents/skills/image-version-bump/SKILL.md`, including the `v*` publication boundary. |
| Multi-repository coordination and separate Git histories | Both local `multi-repo-coordination` and `repository-delivery` skills. |

## Validation log

- The `skill-creator` validator passed for all 12 runtime skills and all 13
  `ai_agents` skills.
- Parsed all three relocated contract schemas and `.vscode/settings.json` as
  JSON successfully.
- `git diff --check` passed in both repositories after correcting one modified
  CRLF description line in the existing `ai_agents` code-review skill.
- The system Python does not provide `pytest`; the repository `.venv` does.
  The four approved runtime contract test files passed with 53 tests total.
- Local Markdown links were checked in 46 changed runtime Markdown files and
  21 changed `ai_agents` Markdown files. One migrated scenario-reference link
  was corrected before both checks passed.
- The migrated feature backlog contains 206 unique task IDs: 139 complete and
  67 open.
- After repository-local replacements and validation were complete, the
  workspace owner approved elevated deletion of `/data/repos/.agents/skills`;
  the shared copies are now removed.

## Delivery

| Repository | Branch | Commit | Pull request |
|---|---|---|---|
| `ai-enterprise-agent-runtime` | `chore/adhoc-repo-local-vibe-workflow` | `51f2daf` | [#36](https://github.com/ygo74/ai-enterprise-agent-runtime/pull/36) |
| `ai_agents` | `chore/adhoc-repo-local-vibe-workflow` | `f41cec2` | [#12](https://github.com/ygo74/ai_agents/pull/12) |

Both pull requests are open and cross-linked. Neither was merged. No release
tag was created or pushed.
