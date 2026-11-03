# Implementation Plan — Remaining Endpoint and Discovery Work

## Scope and status

This plan accompanies the migrated feature scope in [`SPEC.md`](SPEC.md) and
the preserved checklist in [`TASKS.md`](TASKS.md). The source checklist has 206
entries: 139 complete and 67 open. Completed entries remain checked as delivery
evidence; open entries remain backlog and are not implementation scope for the
separate repository-workflow migration.

Any future implementation starts from a new user request and follows the
repository workflow, including approval of its SPEC and PLAN. The checklist
below preserves the remaining feature intent; it does not authorize work by
itself.

## Current architecture and source of truth

Read these current consolidated pages before planning a future task:

- [Provider endpoint surfaces](../../endpoints/provider-surfaces.md)
- [Standard exchange contract](../../contracts/exchange-contract.md)
- [Typed output and streaming](../../contracts/agent-output-and-streaming.md)
- [Agent descriptors and discovery](../../discovery/agent-catalog.md)
- [Managed native-agent worker](../../endpoints/managed-agent-worker.md)
- [Language support](../../compatibility/language-status.md)

Python provides provider invocation and model discovery today. The A2A agent
card is not implemented. .NET and Java retain earlier output/stream contracts
and do not yet provide the full descriptor, discovery, card, or managed-worker
behavior. Do not describe these pending capabilities as delivered.

## Remaining work areas

1. **Descriptor and configuration parity** — complete the .NET and Java
   descriptor models, registry, defaults, route binding, capability validation,
   and configuration support. Keep uniqueness, exact public IDs, immutable
   startup state, and deterministic ordering consistent with Python.
2. **Provider discovery parity** — complete .NET and Java OpenAI and Anthropic
   model projections, routing, dialect selection, pagination, structured
   failures, exact identifier matching, and capability extensions. Preserve
   listing-to-invocation round trips.
3. **A2A card** — implement the descriptor-based card projection and
   well-known route, derive advertised URLs from configured public base URL,
   advertise only enforced authentication schemes, and prove cross-surface
   consistency. Keep the card opt-in.
4. **Discovery access control** — finish authentication modes, developer-owned
   visibility policy, hidden agents, indistinguishable forbidden/not-found
   lookup, and fail-closed behavior including a bounded evaluation deadline.
5. **Quality and adoption** — complete the 100-agent performance budget,
   deterministic ordering and cross-language parity checks, safe observability,
   runnable examples, and the remaining discovery scenarios.
6. **Typed-output parity** — implement and validate the versioned Python output
   contract in .NET and Java without claiming parity before the contract tests
   pass. Preserve the existing v1 behavior in those runtimes until the change
   is delivered.
7. **Native worker parity** — plan .NET/Java invocation, lifecycle, approval,
   and worker behavior separately, and obtain maintainer approval for any
   production release exception before rollout.

## Architecture and engineering review

- Preserve language-neutral contracts and equivalent behavior across Python,
  .NET, and Java; document and approve any platform exception.
- Search for and reuse existing endpoint, descriptor, auth, error, streaming,
  and framework configuration abstractions before adding types.
- Keep transport mapping, domain contracts, dispatch, and business handlers
  separate. Use cohesive typed classes/records/enums, clear domain boundaries,
  SOLID reuse, and early exits.
- Preserve framework-native configuration, standard logging, secret hygiene,
  deterministic caller authorization, and explicit user-facing defaults.
- Keep runnable examples aligned with Python LangChain/FastAPI, .NET Microsoft
  Agent Framework, and Java Spring AI/Spring Boot unless an approved plan says
  otherwise.

## Test and validation approach

For each future behavior change, add a failing unit or contract test before the
implementation, then validate the smallest affected layer. Add integration,
cross-surface, parity, security, and performance checks where the contract
requires them. In particular:

- test endpoint and discovery envelopes against versioned schemas;
- test caller scoping, deterministic authorization, hidden agents, and
  fail-closed visibility;
- test exact discovery ID round trips and shared descriptor fields;
- compare provider and A2A surfaces against the same descriptor;
- measure discovery listing p95 at 100 agents against the existing 20 ms budget
  and verify lookup uses the indexed registry;
- verify logs expose correlation and reason codes without credentials or
  sensitive request content;
- run the relevant language suites and update the implementation journal with
  actual commands, results, and deviations.

## Completion criteria

- Every open task in `TASKS.md` is either completed with evidence or deliberately
  re-scoped through a newly approved request.
- Consolidated specifications and user/contributor guides describe verified
  behavior only.
- Python, .NET, and Java differences are covered by passing contract/parity
  checks or by an explicit, maintainer-approved exception.
- Performance, security, package, and example requirements for the changed
  surfaces are validated before release readiness.
