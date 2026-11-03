# Implementation Plan

## Issue

#10 — Prepare repository for Codex implementation

## Specification

./SPEC.md

## Objectif

Add one root-level `AGENTS.md` that gives Codex an entry point into the
repository's existing conventions and feature structure, referring to canonical
documents instead of copying their rules.

## Préconditions

- [x] SPEC approved by the requester.
- [x] Repository is `/data/repos/ai-enterprise-agent-runtime`.
- [x] Existing guidance was available in the project constitution and active
  feature pointer, `.github/copilot-instructions.md`,
  `.github/instructions/python.instructions.md`, and the active feature plan.
- [x] PLAN approved by the requester.

## Étapes

### Étape 1 — Add repository-level Codex guidance

**Objectif :** Give Codex clear directions for finding and applying the existing
project rules and feature context.

**Fichiers/composants :**

- `AGENTS.md` (new)
- `AGENTS.md` and `WORKFLOW.md` (current repository guidance)
- `spec/implementation/<request>/` (request tracking)
- `spec/` (consolidated system behavior)
- `.github/instructions/python.instructions.md` (reference only)
- `spec/implementation/adhoc-openai-anthropic-endpoints/PLAN.md` (migrated
  feature backlog context)

**Modifications :**

- Direct Codex to read repository guidance and select the canonical request
  tracking record before feature work.
- Direct Codex to consult the applicable `spec.md`, `plan.md`, `tasks.md`, and
  supporting contracts or design documents before changing implementation files.
- Summarize where production code, tests, examples, and specifications belong,
  based on the active plan.
- Direct Codex to apply matching language-specific instructions, including the
  Python instructions for Python files.
- State that existing documents are canonical and should not be duplicated or
  contradicted, and that Copilot-only commands are not required.

**Validation :**

- Review `AGENTS.md` against the cited source documents for consistency.
- Confirm that the repository guidance, request tracking, Python instructions,
  and consolidated specification cited by the instructions exist.

**État :** Terminé. The root guidance was added and its direct references were
checked against the repository.

### Étape 2 — Review the documentation-only change

**Objectif :** Confirm that the change stays within the approved scope and is
readable as repository guidance.

**Fichiers/composants :**

- `AGENTS.md`
- `spec/implementation/issue-10/SPEC.md`
- `spec/implementation/issue-10/PLAN.md`

**Modifications :**

- Check that the new guidance introduces no competing rules or hard-coded active
  feature path.
- Check that no unrelated Copilot workflow, code, or CI files were changed.

**Validation :**

- Review repository status and the resulting documentation diff.
- Run `git diff --check` on the change.

**État :** Terminé. The change is limited to the approved planning documents and
`AGENTS.md`; all cited files exist, and whitespace checks found no issues.

## Tests

No runtime tests are planned because this change adds repository instructions and
does not alter executable behavior. Validation consists of reviewing the
referenced files, confirming their paths, and checking the documentation diff.

## Validation finale

- `AGENTS.md` accurately points to repository rules, request tracking, project
  layout, and applicable language guidance.
- All referenced paths exist or are explicitly documented as patterns such as
  `spec/implementation/<request>/`.
- The change is limited to `AGENTS.md` and the approved issue planning documents.
- `git diff --check` reports no whitespace errors.

## Risques

- Duplicated rules can drift. Keep `AGENTS.md` short and point to the canonical
  documents.
- Hard-coding a request path can make guidance stale. Select the current request
  record under `spec/implementation/`.
- References into `.github/` are named for the existing Copilot integration;
  describe them as repository guidance sources rather than requiring Copilot
  tools or commands.

## Décisions techniques

- Use a root-level `AGENTS.md` as the Codex instruction entry point.
- Add no Codex skills, custom agents, prompts, or slash-command workflows; these
  are outside the requester-approved scope.
- Keep the existing project rules, feature artifacts, and language instructions
  as the source of truth.
- Do not run runtime tests for a documentation-only change.

## Critères de réussite

- Codex receives one root-level entry point to the project's existing
  conventions and structure.
- The entry point directs Codex to the active feature and relevant language
  guidance without duplicating their contents.
- No behavior, CI, Copilot, or feature-tool workflow changes are included.
- Documentation review and `git diff --check` complete without findings.
