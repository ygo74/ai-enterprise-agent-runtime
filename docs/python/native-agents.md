# Native agents and managed local workers — Python pilot

Use your normal Microsoft Agent Framework `Agent` directly. The runtime does not
rebuild it or require a skill registry. Ship a factory and `AgentDefinition`:
the definition reuses `AgentDescriptor` and the existing `ToolOperationDescriptor`
security model. Factory inputs are `AgentFactoryContext` (verified principal,
conversation, deployment and issuer/tenant namespace), never HTTP payloads.

The [runnable native echo](../examples/python-agentframework-fastapi/README.md)
delivers fewer than 30 nonblank lines in `native.py` plus `app.py`, including
imports and docstrings. `echo_client.py` is the native agent's offline model
implementation; `deployment.py` is operator configuration. There is no hidden
agent-specific handler, SSE loop, registry, confirmation resolver or projector.
The native agent also runs outside the runtime with `await agent.run(...)`.

Install `ygo74-agent-runtime-agentframework[http]`. The integration supports
`agent-framework-core>=1.18,<1.19`; the core/meta runtime remains MAF-free.
The lab's OpenAI adapter is separately versioned (`>=1.14.2,<1.15`), compatible
with that core range; do not assume provider packages share the core's version.

## Native execution

`AgentFrameworkSession(agent, session_id=...)` provides `ask`, `ask_output` and
`ask_stream`. It uses the existing output/update adapters, closes native
producers and consumes final responses. Normal requests actually run MAF without
streaming. Streaming requests actually run native streaming, with content IDs
namespaced across sub-runs and exactly one terminal for the full invocation.

Tool activity exposes only declared names and states. Raw tool arguments/results
and private reasoning never become activity. Notifications remain stream-only
business-wise; current protocols render them as text, not special widgets.
Native errors retain a failed terminal with a sanitized public error message.
Conversion diagnostics contain generated correlation IDs and reason codes.
For SDK 1.18 clients, the binding installs an idempotent, context-local provider
response wrapper. It captures streams hidden inside the native function loop
and closes them on early exit without finalizing incomplete responses or
inspecting generator frames. Shared clients keep separate invocation ownership.

Usage events are cumulative snapshots, **not increments**. Final native snapshots
are authoritative; completed approval sub-runs are added once. Missing optional
counts remain unknown. Anthropic requires real input/output usage: when reported
late, its projector buffers already-converted content frames until usage arrives.
This preserves order but delays visible activity. An invocation with no usage
fails explicitly for Anthropic; no baseline or totals are invented. The offline
echo reports genuine zero inference consumption. Chat/Responses can omit unknown
usage according to their existing support matrix.
If approval sub-runs mix known and missing base usage, the invocation fails
explicitly rather than publish a partial sum as complete token consumption.

## Optional advanced approval path

Inject an `ApprovalResolver`, optional `MafApprovalTranslator` and deterministic
`discard_authorizations` callback into the session. `TicketApprovalResolver`
uses your domain `ConfirmationPresenter`, store and explicit user context. It
declines calls to MAF and stores exact arguments. Later `CONFIRM`/`DECLINE`
commands run through `ConfirmedOperationRunner` before the LLM. This is the
existing ticket behavior, **not** native suspended-run resume.

`HttpConversationEngine` shares streaming and normal command routing, serializes
turns and retains native output usage/status. `ConversationEntrypoint` owns
transport parsing. `ManagedAgentWorker` accepts an advanced typed conversation
factory when domain composition (for example Mail's ledger/gates/renderers)
requires it. This trusted composition hook does not bypass source ACLs.

Tools require declarations and an enforceable admission policy. With
`AgentFrameworkWorker`, a trusted `admission(definition, agent)` validates actual
deterministic gates; declarations alone never authorize execution. Standard Agent
tools are checked against declarations before use. Identity-dependent instances
are validated when first constructed, before model execution. Custom native
`SupportsAgentRun`/`BaseAgent` implementations require explicit capability
admission because their hidden tool surface cannot be inspected generically.
Dynamic context providers also require explicit admission even when the definition
declares no tools: `ContextProvider.before_run` can inject tools or middleware.
Only the exact SDK `InMemoryHistoryProvider` implementation is exempt. Admission
must reject unapproved dynamic surfaces or verify their deterministic execution
gates; matching declarative metadata alone is insufficient.
Unsupported native approvals without a resolver fail closed.

## Managed worker operations

`AgentFrameworkWorker(definition, WorkerSettings(...)).build_app()` loads only the
trusted configured export. An operator can inject an already-resolved factory
from trusted DI. No request can select a module or factory.

`WorkerSettings` owns authentication, endpoints, discovery, deployment and
identity namespace, capacity, idle expiry and turn timeout. Authentication is
mandatory. `/health/ready` is 200 during lifespan and 503 otherwise; it exposes no
identity or secrets. Shutdown stops admission, drains queued/active leases and
then closes scopes. The operator's process supervisor should enforce an outer
shutdown deadline if custom dependencies do not close.

Factories may return a native agent, an awaitable, or a standard async context
manager yielding an agent. Use scopes for MCP clients/credentials; do not place
credentials in the factory context or model-visible data. Failed/cancelled turns
retire their cache entry after leases drain. Changed verified claims select fresh
resources; authorization must still be rechecked at each protected operation.
Bounded approval abandonment resets unsafe native state for the next CLI turn.
If declining an abandoned approval returns a native error (or raises), the result
is failed with a sanitized error, not merely an incomplete budget stop. Reported
decline usage is retained and that session is invalidated in both response modes.
If refusal usage is inconsistent or missing, the final aggregate stays unknown;
the sanitized native failure still takes precedence over accounting errors.

The input profile is latest-user-text with server-managed MAF history. Non-text
parts are rejected. Client history only locates the latest user message; full
client-history replay and multimodal profiles are not implemented.

## Provider continuity diagnostics

The caller's conversation header is a runtime routing handle, **not** a provider
continuation. With the installed `OpenAIChatClient` (OpenAI adapter 1.14.2/core
1.18), requests use the provider **Responses API**, even when the exposed worker
serves Chat Completions. Its `STORES_BY_DEFAULT=True` selects service history.
MAF maps `service_session_id` beginning `resp_` to `previous_response_id`, and
`conv_` to `conversation`. An unset `store` preserves the provider default.

Select `AgentFrameworkSession(agent, require_provider_continuation=True)` when
the trusted application deliberately requires provider-only history. This
checks finalized subcalls and the retained service handle, including stale/
missing/mismatched continuation, and fails explicitly without replaying client
history or switching storage. Explicit `store=False` conflicts with this profile
and is rejected before execution. The default remains compatible with local,
stateless and custom BYOA agents; no provider requirement is inferred for all
native agents merely from `STORES_BY_DEFAULT`.

INFO records on the existing session-cache, binding and progress loggers expose:

- `conversation cache continuity`: `phase` create/hit/expire/evict/invalidate/
  release, reason, `cache_instance`, `identity_fingerprint`,
  `conversation_fingerprint`;
- `native session continuity`: binding `session_instance`, turn/subrun, mode,
  storage options, before/after service continuation kind/fingerprint and
  explicit invalidation/recreation;
- `native provider continuity`: provider subcall index, request/complete-response
  phase, effective storage, structural message/role counts and continuation
  kind/fingerprint. Result hooks execute only after SDK finalization, never on
  fragments; the existing provider-boundary ownership hook forwards SDK requests
  unchanged.

`request_fingerprint` correlates cache, session and provider events across each
HTTP request, scoped separately for stream pulls and cleanup. All fingerprints
use a random process-local HMAC key: they are opaque, resist guessed identities,
and cannot correlate across restarts. No prompts, mail, tools' arguments/results,
tokens, raw identity/conversation/provider IDs or native objects are emitted.
Configure your standard logging sink to retain these `LogRecord` extra fields;
plain default formatters generally display only the event message. Do not enable
global DEBUG or dump complete SDK records to diagnose continuity.

Normal HTTP stream cleanup releases the serialized cache turn **before** yielding
its terminal. The transport closes its source at that terminal; yielding inside
the lease previously injected `GeneratorExit`, invalidated successful state, and
created a fresh conversation on the next request. This defect is reproduced and
fixed by real FastAPI plus mocked installed-SDK transport tests (stream, normal,
mixed modes). Cancellation/errors before completion still invalidate fail-closed.
This deterministic defect is evidence about the code, not proof of the cause of
any specific live LibreChat exchange.

Installed MAF middleware dispatches a provider response containing parallel
approval-required calls as successive local approval-only sub-runs. Intermediate
dispatch makes no provider request and has no token usage. The binding excludes
only these instrumented, provider-free approval-only rounds from usage accounting;
it neither invents zero usage for provider calls nor relaxes missing provider usage
checks. Installed-SDK mocked HTTP tests cover parallel approval/refusal in both
modes, exact accumulated token counts and the next turn's continuation.

The Mail consumer's authenticated HTTP/SSE regression replays two complete
LibreChat-shaped payloads in normal/stream/mixed modes with a context-dependent
mock Responses provider store. Its 15 synthetic messages span 04–10 October 2026;
the second turn derives 10 exact approval tickets from the prior table, leaving
five uncertain messages and two out-of-period sentinels unchanged. No duplicated
history, title request, live mailbox, real LibreChat or real model inference is
involved. This validates implementation behavior, not semantic performance of a
real model or attribution of the original historical live exchange.

Reuse decision: extend `NativeStreamScope`/its existing provider hook and standard
loggers; share small framework-neutral correlation primitives with the cache and
entrypoint. No second memory store, database, SDK request reconstruction, frame
inspection, public debug endpoint or provider-history fetch is introduced.

## Limits and parity

One deployment per isolated process/container, one in-memory instance. No durable
tickets/history, multi-replica idempotency, scheduler, Kubernetes or remote
registry is supplied. Isolation alone is not a sandbox: admission, workload
identity, network/secret policy and approved MCP access are platform obligations.

This is an implementation pilot requested by the consumer, not evidence of
.NET/Java parity or production release approval. Their invocation/lifecycle/
approval/worker semantics are deferred separately from the earlier output-only
exception. Maintainer release-exception approval and cross-language quality gates
remain outstanding. See the [pilot contract](../../specs/001-openai-endpoint-exposure/contracts/byoa-python-pilot.md).
