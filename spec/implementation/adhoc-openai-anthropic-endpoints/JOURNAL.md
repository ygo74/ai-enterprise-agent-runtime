# Implementation Journal — OpenAI and Anthropic Endpoint Exposure

## Migration state

- The old feature checklist had 206 entries: 139 complete and 67 open.
- All original task IDs and checkbox states are retained in [`TASKS.md`](TASKS.md).
- This migration did not implement any open feature behavior.
- Current implemented behavior is documented in the repository's consolidated
  specification and linked from [`PLAN.md`](PLAN.md).

## Source-to-destination audit

| Source material | Durable destination |
|---|---|
| Feature request and functional requirements | [`SPEC.md`](SPEC.md); current behavior is in `spec/endpoints/`, `spec/contracts/`, `spec/discovery/`, and `spec/security/`. |
| Feature implementation design | [`PLAN.md`](PLAN.md) reframed around the 67 open backlog items and the present architecture. |
| Task statuses and task identifiers | [`TASKS.md`](TASKS.md), preserving all 206 entries. |
| Endpoint surface contract | [`spec/endpoints/provider-surfaces.md`](../../endpoints/provider-surfaces.md) and [`spec/discovery/agent-catalog.md`](../../discovery/agent-catalog.md). |
| Endpoint authentication, authorization, routing, middleware, and configuration contract | [`spec/security/authentication-and-authorization.md`](../../security/authentication-and-authorization.md), [`spec/runtime/routing-and-middleware.md`](../../runtime/routing-and-middleware.md), [`spec/endpoints/provider-surfaces.md`](../../endpoints/provider-surfaces.md), and the relevant package/configuration pages. |
| Exchange and output data model | [`spec/contracts/exchange-contract.md`](../../contracts/exchange-contract.md), [`spec/contracts/agent-invocation-context.md`](../../contracts/agent-invocation-context.md), [`spec/contracts/agent-output-and-streaming.md`](../../contracts/agent-output-and-streaming.md), and the relocated JSON schemas. |
| Typed output API and support matrix | [`doc/python/typed-outputs.md`](../../../doc/python/typed-outputs.md), runtime output contract, and language-support specification. |
| Native hosting pilot design, operator responsibilities, validation, and limits | [`spec/endpoints/managed-agent-worker.md`](../../endpoints/managed-agent-worker.md), [`doc/python/native-agents.md`](../../../doc/python/native-agents.md), and [`doc/contributors/managed-worker.md`](../../../doc/contributors/managed-worker.md). |
| Research decisions and entity relationships | Current contract, architecture, security, endpoint, discovery, and language-support specifications; deferred behavior remains in the migrated feature record. |
| Completed quickstart scenarios 1–12 | Existing Python user/contributor guides, current specifications, and contract/integration tests; the old checklist is not retained. |
| Open discovery scenarios | [`references/discovery-validation-scenarios.md`](references/discovery-validation-scenarios.md). |
| Requirements readiness checklist | Acceptance criteria in [`SPEC.md`](SPEC.md), task statuses, and validation criteria in [`PLAN.md`](PLAN.md); no separate checklist is needed. |
| Descriptor, exchange, and typed-output JSON schemas | `spec/contracts/agent-descriptor-v1.schema.json`, `spec/contracts/standard-exchange-v1.schema.json`, and `spec/contracts/agent-output-v2.schema.json`. |

## Evidence and follow-up

The current consolidated pages were compared with repository code, tests, and
the implemented feature task entries. Open items include .NET/Java discovery
and typed-output parity, the A2A card, bounded visibility evaluation, and
remaining discovery performance/parity validation. These remain requirements
or backlog; the system specification does not claim they are delivered.

The four contract tests affected by schema relocation will be recorded in the
workflow migration journal after they are run.
