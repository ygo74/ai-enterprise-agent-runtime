# Specification

## Issue

#10 — Prepare repository for Codex implementation

## Objectif

Provide repository-level Codex guidance so Codex follows the project's existing
engineering conventions and feature structure established through GitHub Copilot
and SpecKit.

## Contexte

This is a multi-language library repository with an existing SpecKit constitution,
feature specifications, implementation plans, task lists, and language-specific
instructions. Copilot currently receives repository context through
`.github/copilot-instructions.md`; the repository has no root `AGENTS.md` for
Codex.

The requester clarified that this issue covers project conventions and structure
only. It does not require reproducing SpecKit's command workflows for Codex.

## Problème

Codex does not have a repository-level entry point directing it to the existing
governance, active feature documents, language rules, and package layout. Without
that context, its changes may not follow the same conventions or be placed in the
same structure used by existing work.

## Périmètre

- Add repository-level Codex instructions that direct Codex to the existing
  source-of-truth guidance rather than copying it into a second set of rules.
- Direct Codex to `.specify/memory/constitution.md`, the active feature directory
  recorded in `.specify/feature.json`, and the relevant feature documents such as
  `spec.md`, `plan.md`, `tasks.md`, contracts, and quickstart.
- Describe the existing multi-language package, test, documentation, and feature
  specification layout at the level needed to place changes consistently.
- Direct Codex to apply relevant language-specific guidance, including
  `.github/instructions/python.instructions.md` for Python files.
- Keep the guidance consistent with the existing Copilot/SpecKit instructions
  and project constitution.

## Hors périmètre

- Recreating SpecKit agents, prompts, or slash-command workflows as Codex skills.
- Modifying SpecKit templates, existing feature artifacts, code, or CI behavior.
- Introducing new engineering conventions that are not present in the
  constitution or current repository guidance.
- Changing the Copilot integration.

## Comportement attendu

When working in this repository, Codex is directed to:

1. Read the constitution and the relevant active feature documents before
   planning or changing implementation files.
2. Treat feature specifications, plans, contracts, and task lists as the source
   of truth for feature scope and design.
3. Follow the existing package and test layout for the affected language(s), and
   preserve cross-language contract and parity expectations where relevant.
4. Apply language-specific instructions to matching files, and avoid duplicating
   repository rules in Codex-only copies.

## Architecture concernée

- Repository guidance: root-level `AGENTS.md` (proposed Codex entry point).
- Governance: `.specify/memory/constitution.md`.
- Active feature selection: `.specify/feature.json`.
- Feature design and structure: `specs/<feature>/spec.md`, `plan.md`, `tasks.md`,
  and supporting design documents.
- Language guidance: `.github/instructions/python.instructions.md`.
- Existing Copilot entry point: `.github/copilot-instructions.md`.

The feature plan documents the canonical layout under `packages/`, `tests/`,
`docs/`, and `specs/`.

## Contraintes

- Keep the instructions concise and actionable; link to canonical documents
  instead of reproducing their full contents.
- Do not require Codex to invoke Copilot-only agents or commands.
- Do not make the guide assume that the current feature remains
  `001-openai-endpoint-exposure`; use the feature pointer already maintained by
  SpecKit.
- Do not weaken or contradict the constitution or applicable language-specific
  instructions.

## Critères d'acceptation

- A root-level Codex instruction entry point exists and identifies the
  constitution and active feature artifacts Codex must consult.
- The instructions point to the repository's existing feature and source layout
  instead of defining a competing layout.
- The instructions make Codex aware of the existing language-specific guidance
  and direct it to follow the Python instructions for Python changes.
- The guidance preserves the repository's cross-language contract and parity
  expectations where applicable.
- No SpecKit command workflows, Copilot files, implementation code, or CI
  behavior are changed as part of this scope.

## Stratégie de test

- Review the instruction file against the constitution, active feature pointer,
  feature plan, Copilot entry point, and Python instructions.
- Verify all referenced paths exist and the documented package/test layout agrees
  with the active feature plan.
- There is no runtime behavior change; no automated runtime test is required.

## Risques

- Duplicating rules in `AGENTS.md` can cause them to drift from the constitution
  or feature documents; mitigate this by using direct references wherever
  possible.
- A hard-coded feature path would become stale as SpecKit advances to another
  feature; use `.specify/feature.json` as the active feature pointer.
- Too little context could leave Codex missing important repository rules;
  explicitly reference the constitution, feature artifacts, layout, and
  applicable language guidance.

## Questions ouvertes

- None. The requester confirmed that this issue should add Codex convention
  guidance only, without recreating SpecKit command workflows.
