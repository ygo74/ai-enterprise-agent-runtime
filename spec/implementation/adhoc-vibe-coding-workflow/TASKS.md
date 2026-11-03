# Implementation Tasks

Tasks are ordered; repository prefixes identify the repository being changed.
Completed feature-001 tasks are tracked separately in
`adhoc-openai-anthropic-endpoints/TASKS.md` and are not implementation scope
for this workflow change.

## 1. Repository-local workflow foundation

- [x] RUNTIME-001 Record the approved migration checklist and initial state in this tracking directory.
- [x] RUNTIME-002 Add repository-local `WORKFLOW.md` and revise `AGENTS.md` to carry the durable constitution and route to local skills.
- [x] RUNTIME-003 Add workflow entry, specification, planning, task, TDD implementation, multi-repository, consolidation, and delivery skills.
- [x] RUNTIME-004 Add Python, .NET, and Java Solution Architect and implementation-expert references.
- [x] RUNTIME-005 Preserve and align the existing user-doc, contributor-doc, spec-doc, and Python version-bump skills.

## 2. ai_agents workflow and roles

- [x] AGENTS-001 Add repository `AGENTS.md` and `WORKFLOW.md` based on the current architecture and system specification.
- [x] AGENTS-002 Add local workflow, specification, planning, task, TDD implementation, multi-repository, consolidation, and delivery skills.
- [x] AGENTS-003 Add Business Analyst, Python Solution Architect, and Python implementation-expert references for Mail, Wiki, MAF, LangChain/LangGraph, FastAPI, and MCP.
- [x] AGENTS-004 Add a Git-tag-based image version-bump skill with the publication boundary documented.
- [x] AGENTS-005 Preserve and align the existing user-doc, contributor-doc, spec-doc, and code-review skills.

## 3. Consolidated specifications and feature-001 migration

- [x] RUNTIME-006 Add and index the current development-workflow specification in `spec/`.
- [x] AGENTS-006 Add and index the current development-workflow specification in `spec/`.
- [x] RUNTIME-007 Compare feature-001 behavior and contracts with current code, tests, and consolidated specifications.
- [x] RUNTIME-008 Consolidate verified feature-001 behavior and accepted contract details into the appropriate current `spec/` pages and guides.
- [x] RUNTIME-009 Move the three JSON schemas to `spec/contracts/` and update affected tests and references.
- [x] RUNTIME-010 Convert all 206 feature-001 tasks, preserving IDs and the 139 complete / 67 open statuses, into a new implementation tracking record.
- [x] RUNTIME-011 Transfer unique accepted research, data-model, quickstart, checklist, and contract details to their durable destinations.
- [x] RUNTIME-012 Audit every file under `.specify/`, each Speckit agent/prompt, and every feature-001 file against a destination.
- [x] RUNTIME-013 Remove obsolete `.specify/`, Speckit-only agents/prompts, and feature-001 source files after the audit.
- [x] RUNTIME-014 Update repository documentation, implementation records, tests, and adapters that refer to obsolete Speckit or feature-001 paths.

## 4. Workspace guidance migration

- [x] WORKSPACE-001 Update `/data/repos/AGENTS.md` and `WORKFLOW.md` so workspace safety rules remain and process details defer to repository-local instructions and skills.
- [x] WORKSPACE-002 Audit local replacements and remove parent-level skill copies after both repositories contain the verified equivalents.

## 5. Final audit and delivery readiness

- [x] AUDIT-001 Compare all durable requirements in this temporary SPEC against both consolidated workflow specifications and local instructions/skills.
- [x] AUDIT-002 Check Markdown links, skill metadata and references, obsolete-path mentions, repository diffs, and `git diff --check` in both repositories.
- [x] AUDIT-003 Run the four affected runtime contract tests listed in the approved PLAN.
- [x] AUDIT-004 Remove this temporary SPEC only after AUDIT-001 passes; retain PLAN, TASKS, and JOURNAL as the developer tracking record.
- [ ] AUDIT-005 Record final validation evidence, remaining follow-ups, and per-repository branch status in JOURNAL.
