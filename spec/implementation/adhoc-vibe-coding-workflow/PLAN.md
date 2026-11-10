# Implementation Plan

## Request and approval

- Request: repository-local vibe-coding workflow and Speckit migration.
- Source: ad hoc user request; no GitHub Issue will be created.
- SPEC: approved by the user; removed after its durable requirements were
  compared with both consolidated workflow specifications and local guidance.
- Primary repository: `ai-enterprise-agent-runtime`, which owns the Speckit
  migration and coordinates the cross-repository work.
- Secondary repository: `ai_agents`.
- The user confirmed that feature `001` and its unfinished tasks are in scope
  for migration, but not implementation.

## Objective

Install repository-owned workflow instructions and skills in both repositories,
move all reusable parent-level skills into those repositories, migrate the
runtime's Speckit constitution and feature material into the approved structure,
and remove the obsolete source files only after a content-to-destination audit.
Add a tag-based image version-bump skill to `ai_agents`.

## Repository and branch plan

Keep repository histories separate. After approval of this PLAN, prepare one
branch in each repository using its current default branch as the base:

| Repository | Role | Proposed branch |
|---|---|---|
| `ai-enterprise-agent-runtime` | Primary; constitution, Speckit, and consolidated-spec migration | `chore/adhoc-repo-local-vibe-workflow` |
| `ai_agents` | Agent roles, local workflow, and image version-bump skill | `chore/adhoc-repo-local-vibe-workflow` |

The parent workspace at `/data/repos` is not a Git repository. Its general
safety and repository-location rules remain. Its workflow text will point to
the selected repository's `AGENTS.md`, `WORKFLOW.md`, and skills; its
uncommitted workflow skill copies will be removed only after both repositories
contain verified replacements.

## Target structure

Both repositories will have concise `AGENTS.md` and `WORKFLOW.md` files and a
local `.agents/skills/` tree. The workflow uses an entry-point skill plus
focused phase skills so an agent loads only the relevant procedure and role
references:

- `development-workflow`: intake and phase routing, optional Issue association,
  approval gates, tracking, and hand-offs.
- `feature-specification`: user-request analysis and SPEC creation.
- `implementation-plan`: codebase analysis and Solution Architect plan.
- `implementation-tasks`: detailed repository-scoped, test-first task list.
- `test-driven-implementation`: task execution, progress logging, and
  Solution Architect review of discovered improvements.
- `multi-repo-coordination`: independent repository branches and cross-repo
  dependencies.
- `spec-consolidation`: update the consolidated system specification from
  verified behavior.
- `repository-delivery`: validation, diff review, commit, push, and pull-request
  conventions, preserving the approval and release boundaries.

These names are proposed; skills may use an existing local naming convention
where one already fits. Existing user-doc, contributor-doc, feature-spec,
code-review, and Python package version skills remain local and available.

Role references will be loaded by the phase skill that needs them:

| Repository | References |
|---|---|
| `ai-enterprise-agent-runtime` | Solution Architect and implementation expert for Python, .NET, and Java |
| `ai_agents` | Business Analyst for agent behavior; Python Solution Architect and implementation expert for Mail/Wiki, MAF, LangChain/LangGraph, FastAPI, and MCP |

The role references will preserve repo-specific design constraints, existing
framework choices, testing and documentation expectations, and language idioms.
The shared baseline will keep DRY, SOLID, early exits, cohesive class-based
design where appropriate, type safety, test-first behavior changes, and
junior-developer readability. Runtime-specific parity, UX, performance,
observability, example, and release gates will remain explicit.

## Migration map

| Existing source | Destination and treatment |
|---|---|
| `/data/repos/.agents/skills/issue-driven-development/` | Local `development-workflow`, phase skills, delivery skill, and request templates in both repositories. Issue association becomes optional; SPEC and PLAN approval gates remain. |
| `/data/repos/.agents/skills/multi-repo-coordination/` | Local coordination skill in both repositories. Keep one tracking record in the primary repo and separate branches, commits, and PRs. |
| `/data/repos/.agents/skills/spec-consolidation/` | Local consolidation skill in both repositories, tied to each repo's consolidated `spec/` and validated behavior. |
| `/data/repos/.agents/skills/backend-architect/` | Replace with the repository/technology-specific Solution Architect role references; retain only guidance relevant to these two repositories. |
| `/data/repos/AGENTS.md` and `/data/repos/WORKFLOW.md` | Keep workspace safety/location rules; remove the parent-skill workflow dependency and point contributors to repository-local instructions. |
| `/data/repos/.agents/skills/` | Remove the migrated skill copies only after equivalence and local references are checked. |
| Runtime `.specify/memory/constitution.md` | Split durable baseline rules between runtime `AGENTS.md`, `WORKFLOW.md`, workflow skills, and the Python/.NET/Java role references. Preserve every applicable gate listed below. |
| Runtime `.specify/templates/`, scripts, workflow registry, extension, and Speckit integrations | Map reusable SPEC/PLAN/task structure to the new workflow skills and their references. Remove scripts and configuration that have no role in the new skills. |
| Runtime `.github/agents/speckit.*` and `.github/prompts/speckit.*` | Migrate applicable procedures to local skills; remove the Speckit-specific files. Replace stale Copilot guidance with a short pointer to repository instructions where the platform still needs a file. |
| Runtime `.github/instructions/python.instructions.md` | Move its applicable type, class, enum, control-flow, and reuse rules to the Python role references. Keep a concise compatible instruction entry only if repository tooling still consumes it. |
| Runtime `specs/001-openai-endpoint-exposure/spec.md`, `plan.md`, and `tasks.md` | Convert to `spec/implementation/adhoc-openai-anthropic-endpoints/{SPEC.md,PLAN.md,TASKS.md,JOURNAL.md}`. Preserve every task ID and the source statuses (139 complete / 67 open); migrate the open work without implementing it here. |
| Runtime feature `research.md`, `data-model.md`, `quickstart.md`, checklist, and contract Markdown | Transfer validated system contracts and behavior to the relevant `spec/` domain pages and current user/contributor guides. Put unresolved decisions and still-needed design details in the new implementation record or linked references. |
| Runtime feature JSON schemas | Move the three machine-readable schemas to an indexed location under `spec/contracts/`; update contract tests and all links that currently point into `specs/001`. |
| Runtime README, Python guides, current `spec/` pages, and issue records referencing `specs/001` or `.specify` | Update links to the consolidated pages, migrated tracking record, or current repository instructions. Keep existing issue records, but remove stale instructions and paths. |
| Runtime consolidated specification | Add and index a development-workflow page. Verify it describes the installed skills and approval/tracking behavior after implementation. |
| `ai_agents/AGENTS.md` (currently absent) and new local `WORKFLOW.md` | Add repository baseline principles, workflow routing, existing architecture boundaries, and links to skills and current system specifications. |
| `ai_agents/.agents/skills/` | Add the workflow and coordination/consolidation/delivery skills; retain and align existing documentation and code-review skills. Add Business Analyst and Python role references. |
| `ai_agents/.agents/skills/image-version-bump/SKILL.md` | Add a release preparation skill using `vMAJOR.MINOR.PATCH` Git tags as the existing source for image versions. There is no package version manifest. Pushing a tag triggers image builds and GHCR publication, so creating/pushing a tag requires explicit user authorization. |
| `ai_agents/spec/README.md` | Add and index a consolidated development-workflow page. Preserve the current agent architecture and business specifications as the source of current behavior. |

The migration ledger will include every file under `.specify/`, every
Speckit-specific prompt/agent, every file under the feature `001` directory,
and every repository reference to those paths. No obsolete copy will remain in
the working tree after the audit. Existing `spec/implementation/issue-*`
records are already repository tracking documents; retain them and update stale
links rather than copying duplicate task history.

## Runtime principles to preserve

The old constitution is not copied as a standalone file. Its requirements are
allocated to always-loaded rules, workflow skills, or relevant role references:

1. Language-neutral contracts and equivalent Python/.NET/Java behavior, with
   explicit approved exceptions.
2. DRY/SOLID reuse-first design, small responsibilities, early exits, and
   domain-oriented boundaries.
3. Test-first changes with unit, contract, integration, parity, and performance
   coverage when relevant to the approved feature.
4. Consistent user-facing contracts, configuration defaults, errors, and
   examples across implementations.
5. Measurable performance budgets and regression evidence for applicable work.
6. Standard language logging, correlation fields, and secret/payload hygiene.
7. Cohesive typed classes/records/enums and explicit shared abstractions; no
   ad hoc maps for structured domain data.
8. Stack-specific runnable examples (Python LangChain/FastAPI, .NET Microsoft
   Agent Framework, and Java Spring AI/Spring Boot unless a documented
   alternative is approved).
9. Version compatibility, schema/contract migration notes, parity and release
   checks, and explicit handling of exceptions.

The `ai_agents` rules will be derived from its current consolidated system
specification and architecture pages, including framework isolation, MCP as
the integration boundary, deterministic security decisions, untrusted-content
handling, and domain ownership.

## Ordered implementation steps

### Step 1 — Prepare repositories and migration ledger

- Reconfirm clean worktrees, current branches, default branches, and local
  instructions in each repository before creating the proposed work branches.
- Build a source-to-destination checklist for all Speckit, parent-skill, and
  feature `001` files. Compare each contract against implementation, tests, and
  current consolidated specification before deciding its destination.
- Record all 206 feature tasks (139 complete and 67 unfinished in the source)
  and keep their
  IDs, status, dependencies, and notes during conversion.

### Step 2 — Establish repository-local instructions and workflow skills

- Add `AGENTS.md` and `WORKFLOW.md` to `ai_agents`; revise both files in the
  runtime repo to make the repository constitution and skill routing clear.
- Add the focused workflow skills and shared templates to each repository.
- Add the Solution Architect and implementation-expert references for runtime
  Python/.NET/Java, and for `ai_agents` add its Business Analyst plus the
  framework-aware Python role references.
- Copy and adapt coordination and consolidation skills to each repo; provide a
  delivery skill that retains each repository's branch and PR rules.
- Update workspace instructions so ad hoc requests use the selected repo's
  workflow. Remove parent skill files only in Step 6.

### Step 3 — Migrate runtime Speckit constitution and feature content

- Move constitution rules into the approved local locations and review the
  resulting rules against the nine principles above.
- Convert feature SPEC/PLAN/TASKS into the new implementation record. Keep all
  task IDs and statuses, with 139 complete and 67 still open; create a migration JOURNAL
  that records sources, content mappings, and the current feature state.
- Consolidate implemented endpoint, exchange, streaming, discovery, output,
  and native-hosting behavior into their existing `spec/` pages. Keep pending
  behavior in the migrated task record, not in current-behavior claims.
- Relocate the JSON contract files under `spec/contracts/`, then update tests,
  user/contributor docs, current specifications, and implementation records to
  the new paths.
- Transfer any unique accepted research decisions, data definitions, and
  validation scenarios to the relevant specification, guide, task record, or
  migrated reference. Remove the old Speckit feature directory once every
  source item has a destination.

### Step 4 — Add the `ai_agents` workflow and version-bump skill

- Add repository instructions reflecting the current system boundaries and
  links to the Mail/Wiki architecture and behavior specifications.
- Add the workflow, coordination, consolidation, and delivery skills, then
  add Business Analyst, Python Solution Architect, and Python implementation
  references specific to the current MAF and LangChain/LangGraph compositions.
- Add an image version-bump skill that checks existing tags and changes, selects
  or recommends a semantic version, and reports that pushing the tag publishes
  images. Do not create or push a tag during skill creation.
- Add the consolidated workflow page and index it in `spec/README.md`.

### Step 5 — Complete cross-repository documentation and reference migration

- Update root README files, repository documentation indexes, and links to
  consolidated contracts and current workflow skills.
- Replace stale `.specify`, Speckit, `specs/001`, and parent-skill references in
  retained implementation records and contributor instructions.
- Verify the workflow and role documentation agrees with the current source
  architecture and active validation commands in each repository.

### Step 6 — Remove obsolete sources after destination audit

- Remove runtime `.specify/` and all Speckit-only generated prompts/agents.
- Remove parent `/data/repos/.agents/skills/` source files after the two local
  skill sets are checked.
- Retain workspace safety/location rules and, if needed by the editor, a
  concise Copilot adapter pointing to local instructions; do not retain duplicate
  Speckit content or a legacy archive.
- Compare the durable requirements in this workflow's temporary SPEC against
  both consolidated workflow pages and the local AGENTS/WORKFLOW/skill files.
  Only after a complete match, remove this workflow SPEC file as requested.

### Step 7 — Validate and prepare repository delivery

- Check all local Markdown links and skill references; search for stale
  `.specify`, `speckit`, `specs/001-openai-endpoint-exposure`, and
  `/data/repos/.agents/skills` references.
- Parse relocated JSON schemas and run the four affected runtime contract
  tests: `test_agent_descriptor_schema.py`,
  `test_standard_exchange_schema.py`, `test_agent_output_v2_schema.py`, and
  `test_openai_responses_contract.py`.
- Review `git diff --check`, each complete repository diff, and both worktrees.
  Do not run unrelated full suites for this documentation/skill migration.
- Keep release/version skills unexecuted. Creating a Git tag or pushing it in
  `ai_agents` is outside this task; it would trigger image publication.
- Prepare one pull request per repository after local validation, documenting
  the cross-repository relationship. Do not merge either pull request.

## Validation strategy

| Area | Validation |
|---|---|
| Instructions and skills | Review frontmatter, names/descriptions, phase routing, explicit approval stops, ad hoc support, role-reference selection, TDD, junior-readable code guidance, and no duplicated/conflicting rules. |
| Constitution migration | Compare every rule and gate in the old constitution with its new `AGENTS.md`, `WORKFLOW.md`, or skill/reference destination. |
| Feature migration | Compare every old feature file and each task ID/status with the destination ledger; confirm 139 are complete and 67 remain open. Verify pending requirements are not described as current behavior. |
| Consolidated specifications | Check each updated description against runtime source and current tests. Verify both development-workflow pages link to the installed instructions and skills. |
| Relocated machine contracts | Parse schemas and run the four affected contract tests after changing paths. |
| Links and stale content | Check internal Markdown links; search for removed path/name references; review platform adapters for accidental remaining Speckit commands. |
| Repository hygiene | `git diff --check`, complete diff review, worktree status, and no unintended changes. |

No source implementation behavior is planned to change. Runtime contract tests
are included only because their canonical schema files and paths move.

## Risks and mitigations

- **Contract detail is lost while consolidating.** Use a file-by-file source and
  destination ledger; preserve the schema tests and all open task IDs/statuses.
- **Planned behavior is described as implemented.** Verify current system pages
  against source/tests and keep pending work in `TASKS.md`.
- **Constitution rules are duplicated or contradicted.** Keep a compact shared
  baseline in `AGENTS.md` and put technology and workflow detail in skills and
  references; run a clause-by-clause comparison before removal.
- **A tag unexpectedly publishes images.** Make the `ai_agents` skill prepare
  and explain the tag only; creation/push remains explicit user action.
- **The two repositories drift in workflow gates.** Keep shared phase contracts
  aligned and document repo-specific role and validation differences.
- **Migration references break examples/tests.** Update every consumer found by
  repository-wide path search and run the affected contract tests.

## Completion criteria

- Both repositories have local AGENTS/WORKFLOW instructions and the approved
  workflow/role/release skills.
- The runtime constitution, Speckit tooling, and feature `001` content have
  verified new destinations; no old Speckit directory, feature directory, or
  obsolete parent skills remain.
- Runtime schemas and consumers use their new canonical paths, and all four
  affected contract tests pass.
- Existing current-behavior specifications are accurate, the two workflow
  specifications are indexed, and the temporary workflow SPEC is removed only
  after its content comparison is complete.
- The image version-bump skill explains the `v*` release trigger without
  creating or pushing a tag.
- Separate repository diffs are reviewed and separate pull requests are
  prepared; neither is merged.
