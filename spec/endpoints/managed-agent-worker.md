# Managed native-agent worker

## Purpose and role

Applications that already use a native agent framework should be able to reuse
runtime hosting, authentication, conversation state, and shutdown behavior
without translating their agent into a runtime-specific skill abstraction. The
Python `ManagedAgentWorker` is a local, single-deployment FastAPI composition
for a trusted native-agent factory.

Framework-specific distributions such as Microsoft Agent Framework and
LangChain provide typed bindings and worker facades. The core worker stays
independent of those SDKs. It creates the host, not the agent, model, tool
policy, or data access layer.

## Trusted definition and caller context

`AgentDefinition` reuses the existing `AgentDescriptor` and declares a trusted
factory export, the input profile, required identity fields, and any tool
operation metadata. A factory path is deployment configuration and is never
selected from a request. The worker passes the factory an `AgentFactoryContext`
containing the verified principal, conversation ID, deployment ID, and
operator-selected identity namespace. It does not pass the raw HTTP payload or
credentials.

The implemented input profile accepts the latest user text with history kept by
the server-side native session. Client-supplied history is not replayed. The
descriptor must match the implemented profile: text input, no structured-output
claim, and tool invocation consistent with tool declarations. Declarations
describe capability; they do not authorize execution. Framework bindings must
prove or explicitly admit the actual tool surface through a deterministic
application policy.

## Authentication, state, and limits

`WorkerSettings` requires explicit authentication, deployment identity, and
identity namespace. Anonymous access is refused. It also sets enabled endpoint
surfaces, optional discovery, a conversation limit, idle lifetime, and a turn
timeout. Defaults are 200 cached conversations, 30 minutes idle lifetime, and
120 seconds per turn.

The worker builds or reuses one conversation per verified identity and
conversation ID. The cache serializes turns for an entry, keeps a lease while a
turn is active, retires failed native state after leases drain, closes resources
on expiry/eviction, and drains active leases before closing all scopes at
shutdown. This is process-local state, not durable or shared across workers.

## HTTP lifecycle

The worker registers the selected invocation endpoints and optional discovery
using the existing endpoint host. It applies request authentication before
creating the native conversation. `/health/ready` reports `503` before startup
and during shutdown, and `200` while the worker lifespan is active. The
readiness response contains no identity or secret data.

Turn timeout applies to normal and streamed execution. Stream producers are
closed when a response completes, fails, or is cancelled. On shutdown, the
worker stops accepting new work, drains queued and active leases, then closes
conversation resources. Operators should still set a process-level shutdown
deadline for custom resources that fail to close.

## Acceptance and limits

- Only an operator-trusted factory is loaded; request data cannot select code.
- Authentication and identity partitioning are mandatory.
- An active turn's resources remain open until its lease ends.
- Failed, cancelled, or abandoned native state is not reused as a healthy
  conversation.
- Expiry, eviction, explicit release, and shutdown close application resources.
- The worker is an in-process Python/FastAPI pilot, not a durable store, cluster
  coordinator, or production agent sandbox.

Framework-specific admission, output conversion, and approval rules are covered
in the [Agent Framework integration](../integrations/agent-framework.md) and
[LangChain/LangGraph integration](../integrations/langchain-langgraph.md)
specifications. The Python implementation is in
[`managed_worker.py`](../../packages/python/agents/ygo74/agent_runtime/domains/endpoints/managed_worker.py)
and the [native worker guide](../../docs/python/native-agents.md).
