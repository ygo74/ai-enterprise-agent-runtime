# Repository Development Workflow

`AGENTS.md` is the always-loaded source for repository principles and skill
routing. The current system behavior starts in [`spec/README.md`](spec/README.md).
Request-specific records live in `spec/implementation/` and are developer and
agent tracking material, not user documentation.

## Request lifecycle

```text
user request or optional Issue
  → SPEC → user approval → PLAN → user approval → TASKS
  → test-driven implementation → review and user acceptance
  → requested documentation, consolidation, and release work
```

Use [`development-workflow`](.agents/skills/development-workflow/SKILL.md) as
the entry point. An Issue is optional; do not create one unless the user asks.

The specification skill records the request source, repositories, outcome,
scope, acceptance criteria, constraints, risks, and open decisions. It presents
the SPEC and waits for explicit approval. The planning skill analyzes the
current code, tests, contracts, docs, and examples, then presents a PLAN and
waits for approval. After plan approval, the architect prepares ordered tasks;
there is no extra task-approval gate.

Implementation follows the approved tasks and uses a failing test, minimal
change, passing test, and refactor cycle for behavior changes. Keep the code
simple, typed, cohesive, and understandable to a junior developer. Record work
and actual validation in the request journal. Route discovered improvements to
the Solution Architect, who decides whether they are in approved scope or a
separate proposal.

## Engineering constitution

- Structure runtime domains with Clean Architecture / Onion Architecture:
  dependencies point inward toward domain and application policy. Keep
  transports, frameworks, databases, and external SDKs in outer adapters or
  infrastructure, and connect them at an explicit composition root.
- Prefer constructor dependency injection through typed interfaces or ports for
  replaceable behavior. Compose concrete implementations at the application
  boundary; avoid service locators, hidden globals, and abstractions that do not
  isolate a real dependency or policy.
- Define shared Python, .NET, and Java behavior through language-neutral
  contracts. Maintain equivalent behavior unless an approved exception is
  documented.
- Prefer reuse (record what was inspected), DRY, SOLID, small responsibilities,
  clear domain boundaries, and early exits. Use cohesive classes and explicit
  abstractions where they clarify ownership; avoid needless frameworks and
  speculative generalization.
- Use typed domain models: dataclasses/validated models in Python, records or
  classes in .NET and Java. Convert wire data at system boundaries. Use enums
  for fixed value sets, not scattered string comparisons.
- Design for horizontal scalability whenever application state is retained
  beyond one operation. Put state access behind an injected port/interface;
  provide an in-memory adapter for development and tests and a PostgreSQL or
  Redis production adapter selected by configuration, chosen to match
  durability, query, and concurrency needs. Do not silently rely on
  process-local state in production. Treat bounded process-local caches as a
  separate design choice and document their limits.
- Define user-visible inputs, outputs, errors, defaults, and interaction flows
  as contracts. Document and approve any cross-language difference.
- Use test-first development with unit and relevant contract, integration,
  parity, performance, and security coverage. Size the validation to the
  affected behavior and existing repository gates.
- Every feature plan states whether latency, throughput, memory, or startup
  budgets apply. Define measurable budgets and regression checks where relevant;
  explain when a dimension does not apply. Report evidence and obtain approval
  for exceptions.
- Use standard language logging with correlation fields. Never log credentials,
  secrets, or sensitive payloads.
- Keep runnable examples with feature contracts. Default examples are Python
  LangChain/FastAPI, .NET Microsoft Agent Framework, and Java Spring AI/Spring
  Boot, unless the approved design documents another choice.
- Check language parity, compatibility, migration notes, docs, and release
  implications during plan and review. Track non-compliance as a blocking item
  or a maintainer-approved, time-bound exception.
- Package the Python, .NET, and Java libraries as directly consumable artifacts.
  Apply semantic versioning consistently; breaking contract changes require a
  major version increment. Version shared schemas and protocol documentation
  with compatibility notes.

Review these principles during plan review, pull request review, and release
readiness. A change is not ready to merge until the required CI quality gates
for Python, .NET, and Java pass. Pull request evidence includes the test-first
sequence, CI status, and applicable performance regression results. Any
exception requires maintainer approval, an owner, and a remediation timeline.

## Tracking and completion

Each request has one canonical folder in the primary repository:

```text
spec/implementation/<issue-N-or-adhoc-slug>/{SPEC,PLAN,TASKS,JOURNAL}.md
```

Start new requests from the consolidated `spec/` pages, not from an old task
record. Keep separate branches, changes, checks, commits, and pull requests per
repository. Follow delivery, documentation, and release skills only when
requested or included in the approved plan; never publish or release
implicitly.
