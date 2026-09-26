# Repository guidance

These instructions apply to the whole repository. The project constitution is
the source of truth for engineering rules; feature plans and contracts are the
source of truth for feature design.

## Read the project context first

Before planning or changing implementation files:

1. Read `.specify/memory/constitution.md` and follow its required principles and
quality gates.
2. Read `.specify/feature.json` and use its `feature_directory` value to find
   the active feature under `specs/`.
3. Read that feature's `spec.md`, `plan.md`, and `tasks.md` when present. Also
   consult relevant contracts, research, data model, and quickstart documents.
4. Read relevant package documentation and examples when they clarify existing
   APIs or implementation patterns.

Do not assume a feature number or copy rules from these source documents into a
competing set of Codex-only conventions.

## Repository layout

- `packages/python/`, `packages/dotnet/`, and `packages/java/` contain the
  language-specific runtime libraries.
- `tests/contract/`, `tests/integration/`, `tests/parity/`, and
  `tests/performance/` contain shared contract and quality coverage. Follow the
  language-specific subdirectories already used by the affected tests.
- `docs/examples/` contains runnable integrations and usage examples.
- `specs/<feature>/` contains feature specifications, plans, tasks, and related
  design artifacts.

Follow the active feature plan for the detailed layout and conventions relevant
to the change.

## Engineering conventions

- Prefer extending reusable code over adding duplicate types or modules; record
  the reuse decision as required by the constitution and active plan.
- Preserve language-neutral contracts and equivalent behavior across Python,
  .NET, and Java where the feature affects more than one runtime.
- Use the typed, domain-oriented APIs and language standards required by the
  constitution.
- Follow the test-first and validation gates in the constitution and active
  feature plan for behavior changes.
- Apply any relevant language-specific repository instructions. In particular,
  read `.github/instructions/python.instructions.md` for changes to Python
  files.
- When a Python change affects public behavior, APIs, configuration,
  dependencies, or supported workflows, update the corresponding user docs and
  runnable examples. Use [`docs/python/README.md`](docs/python/README.md) as the
  Python documentation entry point.

These instructions provide repository context only. Copilot-specific agents,
prompts, and commands are not prerequisites for Codex work.
