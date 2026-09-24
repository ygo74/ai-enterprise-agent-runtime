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
- [x] Existing guidance is available in `.specify/memory/constitution.md`,
  `.specify/feature.json`, `.github/copilot-instructions.md`,
  `.github/instructions/python.instructions.md`, and the active feature plan.
- [x] PLAN approved by the requester.

## Étapes

### Étape 1 — Add repository-level Codex guidance

**Objectif :** Give Codex clear directions for finding and applying the existing
project rules and feature context.

**Fichiers/composants :**

- `AGENTS.md` (new)
- `.specify/memory/constitution.md` (reference only)
- `.specify/feature.json` (reference only)
- `specs/<active-feature>/` (reference only)
- `.github/instructions/python.instructions.md` (reference only)
- `specs/001-openai-endpoint-exposure/plan.md` (reference only for the currently
  documented package and test layout)

**Modifications :**

- Direct Codex to read the constitution and determine the active feature from
  `.specify/feature.json` before feature work.
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
- Confirm that the active feature pointer, constitution, Python instructions,
  and plan paths cited by the guidance exist.

**État :** Terminé. The root guidance was added and its direct references were
checked against the repository.

### Étape 2 — Review the documentation-only change

**Objectif :** Confirm that the change stays within the approved scope and is
readable as repository guidance.

**Fichiers/composants :**

- `AGENTS.md`
- `docs/tasks/issue-10/SPEC.md`
- `docs/tasks/issue-10/PLAN.md`

**Modifications :**

- Check that the new guidance introduces no competing rules or hard-coded active
  feature path.
- Check that no Copilot/SpecKit workflows, code, or CI files were changed.

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

- `AGENTS.md` accurately points to the current constitution, active feature
  artifacts, project layout, and applicable language guidance.
- All referenced paths exist or are explicitly documented as a pattern such as
  `specs/<active-feature>/`.
- The change is limited to `AGENTS.md` and the approved issue planning documents.
- `git diff --check` reports no whitespace errors.

## Risques

- Duplicated rules can drift. Keep `AGENTS.md` short and point to the canonical
  documents.
- Hard-coding the current feature can make guidance stale. Read the feature path
  from `.specify/feature.json`.
- References into `.github/` are named for the existing Copilot integration;
  describe them as repository guidance sources rather than requiring Copilot
  tools or commands.

## Décisions techniques

- Use a root-level `AGENTS.md` as the Codex instruction entry point.
- Add no Codex skills, custom agents, prompts, or slash-command workflows; these
  are outside the requester-approved scope.
- Keep the existing SpecKit constitution, feature artifacts, and language
  instructions as the source of truth.
- Do not run runtime tests for a documentation-only change.

## Critères de réussite

- Codex receives one root-level entry point to the project's existing
  conventions and structure.
- The entry point directs Codex to the active feature and relevant language
  guidance without duplicating their contents.
- No behavior, CI, Copilot, or SpecKit workflow changes are included.
- Documentation review and `git diff --check` complete without findings.
