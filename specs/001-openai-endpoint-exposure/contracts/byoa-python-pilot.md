# Native agent hosting — Python pilot (2026-10-10)

This implementation is an explicitly scoped Python/MAF pilot requested by the
consumer. It does **not** extend the earlier output-only parity exception or
claim constitutional release readiness. .NET/Java invocation, lifecycle,
approval and worker implementations and their parity gates remain deferred;
maintainer approval of a release exception is still required. No production
cross-language rollout is authorized by this document.

## Contract

An agent package exports a native factory and `AgentDefinition`. The definition
reuses `AgentDescriptor`; no skill registry or skill manifests are required.
`AgentFactoryContext` contains only the verified principal, conversation and
operator deployment/identity namespace. Factories return a native agent directly
or an async context manager owning its dependencies. Transport, credentials and
protocol selection do not enter the agent context.

The supported input profile is server-history/latest-user-text. Non-text parts,
client tool results and unsupported input shapes are rejected, not flattened.
Client history is used only to locate the latest user message, never replayed.
Streaming runs native streaming; other requests run native non-streaming.

One conversation cache belongs to one agent deployment. Keys include the
operator namespace, verified identity attributes and conversation. Turns are
serialized; queued and active turns cannot be evicted. Shutdown stops admission,
drains leases, then closes scopes. Cancellation closes producers, discards
authorization grants and invalidates the affected conversation.

MAF output adapters remain authoritative. Safe tool notifications contain only
declared tool names and lifecycle states. Tool arguments/results and private
reasoning are not public activity. Conversion diagnostics contain identifiers and
reason codes only. Usage events are cumulative snapshots, not increments.
Completed native sub-runs are summed once using final response usage (fallback:
last update). Optional counts stay unknown; late Anthropic usage buffers frames
until real counts arrive, and missing usage fails explicitly. Native failures
cannot end in success; a complete invocation has exactly
one terminal after all approval sub-runs close their contents.

The optional ticket bridge declines suspended calls to MAF, stores exact
arguments and uses the existing confirmation runner for later commands. This is
not native suspended-run resume. Domain gates/presenters/renderers stay in Mail.
Definitions with tools must declare operation/risk/confirmation and an
enforceable control point. Trusted admission validates declarations; they are
not authorization. Source ACLs and fresh operation authorization remain required.
Dynamic native context providers require explicit capability admission even for
empty-tool definitions; only the exact SDK in-memory history provider has a known
static surface. The admission policy must verify deterministic execution gates
or reject dynamic capabilities, not merely accept metadata. SDK 1.18 provider
streams hidden by function invocation are captured at the provider boundary and
closed without generator-frame inspection or incomplete-response finalization.
Failed native refusal during approval-budget abandonment preserves sanitized
failure and reported usage, invalidating the session rather than returning an
incomplete budget stop.

## Operator responsibilities and limits

Factory selection is trusted deployment configuration, never a request field.
Authentication, endpoints, namespace, timeout, capacity and discovery are operator
configuration. The local worker is single-instance, in-memory, one deployment
per process: no durability, distributed exactly-once or replica coordination.
An isolated process/container is not a sandbox; workload identity, network
policy, secret delivery and MCP admission require platform controls.
Unsupported workflows, native approvals without a bridge and capabilities outside
the profile are rejected. No new Kubernetes, registry or scheduler is introduced.

## Reuse and validation

Extend `ApprovalLoop`, `HttpConversationEngine`, `ConversationRuntimeCache`,
`ConversationPayloadReader` and `HostingFactory`. Reuse native output/stream
adapters and the existing descriptor and confirmation contracts. New definition,
binding and worker components fill missing integration seams, not domain logic.
Keep existing local budgets: normalization <10ms p95, dispatch <50ms p95,
first event <300ms p95 excluding inference. Test all protocol surfaces, both
modes, cleanup, concurrency, approvals, independent installation and a non-Mail
native agent with <=30 lines of non-domain integration glue.
