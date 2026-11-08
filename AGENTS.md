# Repository guidance

These instructions apply throughout the repository. Current behavior is
described under [`spec/`](spec/README.md); approved work is tracked under
`spec/implementation/`. Repository principles also live in
[`WORKFLOW.md`](WORKFLOW.md) and the relevant skill references.

## Read the project context first

Before planning or changing implementation files:

1. Start from [`spec/README.md`](spec/README.md) and follow only the domain
   pages relevant to the request.
2. For active work, read its approved `SPEC.md`, `PLAN.md`, and current
   `TASKS.md` in `spec/implementation/`.
3. Inspect the affected code, public contracts, tests, documentation, and
   runnable examples before choosing changes.
4. Read relevant package documentation and examples when they clarify existing
   APIs or implementation patterns.

Do not copy obsolete task material into a competing source of current system
behavior.

## Repository layout

- `packages/python/`, `packages/dotnet/`, and `packages/java/` contain the
  language-specific runtime libraries.
- `doc/` contains user/operator guides, contributor documentation, and detailed
  Python library guides.
- `samples/<language>/` contains runnable language catalogs;
  `samples/README.md` indexes them. Existing .NET and Java samples remain
  under `samples/examples/` until migrated.
- `spec/` contains consolidated system behavior and request implementation
  records under `spec/implementation/`.
- `tests/contract/`, `tests/integration/`, `tests/parity/`, and
  `tests/performance/` contain shared contract and quality coverage. Follow the
  language-specific subdirectories already used by the affected tests.

Follow the approved request plan and task list for the detailed change scope.

## Engineering conventions

### Documentation and explanatory comments

- Every class, function, and method MUST have a docstring directly at the
  beginning of its definition. Describe its responsibility and behavior
  precisely enough that a reader can understand its purpose without first
  reading the implementation.
- Function and method docstrings MUST document every argument, including
  optional and keyword-only arguments. They SHOULD also document return values
  and exceptions when these are meaningful to callers. Class docstrings MUST
  explain the class responsibility and document constructor inputs (including
  dataclass fields when they form the constructor); document `__init__`
  separately when it has a non-trivial initialization contract.
- Keep docstrings accurate to the actual behavior, including validation,
  defaults, side effects, and error conditions. Do not use empty, generic, or
  name-only descriptions as substitutes for useful documentation.
- For each non-trivial method, document its algorithm in the method body with
  concise comments at the logical stages. Explain the important steps, order,
  invariants, and non-obvious branches, especially loops, state transitions,
  and error/cleanup paths. Keep trivial accessors and forwarding methods free
  of artificial comments; comments must explain the algorithm or why a step is
  needed, not repeat the code.

- Prefer extending reusable code over adding duplicate types or modules; record
  the reuse decision in the request plan or journal.
- Preserve language-neutral contracts and equivalent behavior across Python,
  .NET, and Java where the feature affects more than one runtime.
- Use the typed, domain-oriented APIs and language standards described in
  `WORKFLOW.md` and the relevant technology role reference.
- Follow the test-first and validation gates in `WORKFLOW.md` and the approved
  request plan for behavior changes.
- Review compliance with repository principles during plan review, pull request
  review, and release readiness. Treat non-compliance as blocking unless a
  maintainer approves a time-bound exception and remediation plan.
- Apply any relevant language-specific repository instructions. In particular,
  read `.github/instructions/python.instructions.md` for changes to Python
  files.
- When a Python change affects public behavior, APIs, configuration,
  dependencies, or supported workflows, update the corresponding user docs and
  runnable examples. Use [`doc/python/README.md`](doc/python/README.md) as the
  Python documentation entry point.

## Workflow skills

- [`development-workflow`](.agents/skills/development-workflow/SKILL.md) routes
  ad hoc and Issue-linked requests through specification, plan, tasks, and
  implementation.
- [`feature-specification`](.agents/skills/feature-specification/SKILL.md)
  creates the request SPEC and chooses relevant role guidance.
- [`implementation-plan`](.agents/skills/implementation-plan/SKILL.md) analyzes
  the existing architecture and prepares the plan.
- [`implementation-tasks`](.agents/skills/implementation-tasks/SKILL.md)
  creates the ordered implementation checklist after plan approval.
- [`test-driven-implementation`](.agents/skills/test-driven-implementation/SKILL.md)
  implements approved tasks and tracks scoped follow-ups.
- [`multi-repo-coordination`](.agents/skills/multi-repo-coordination/SKILL.md)
  coordinates independent repository histories when needed.
- [`spec-consolidation`](.agents/skills/spec-consolidation/SKILL.md) updates
  current behavior under `spec/` when requested or included in approved scope.
- [`repository-delivery`](.agents/skills/repository-delivery/SKILL.md) covers
  validation and repository delivery boundaries.

Copilot adapters may point to these repository instructions; they must not
define a competing workflow.
