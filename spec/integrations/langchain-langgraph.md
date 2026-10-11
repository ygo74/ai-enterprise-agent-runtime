# LangChain and LangGraph integration

## Purpose and role

Applications that use LangChain already own their agent graph, tools, prompts,
model choices, and domain rules. They still need to translate LangChain results
and stream events into the runtime's provider-neutral output contracts. Native
LangGraph applications also need a safe way to run one graph as a server-managed
conversation and to handle graph interruptions.

The optional `ygo74-agent-runtime-langchain` distribution provides that adapter.
It keeps framework-specific execution separate from the provider-neutral
contracts and from the Microsoft Agent Framework integration. It does not
create an agent or replace application composition.

## Scope and ownership

- `LangChainResultAdapter` and `LangChainStreamAdapter` convert supported public
  LangChain messages, results, and events into runtime output contracts.
- `LangGraphSession` invokes an existing compiled graph, selects the latest
  assistant message, translates interruptions, and returns neutral results or
  stream events.
- `LangGraphWorker` optionally connects a trusted graph factory to the shared
  managed HTTP worker.
- The application continues to own graph construction, tools, authorization,
  confirmation policy, persistence, model credentials, and deployment settings.

The distribution depends on the runtime agents package and LangChain libraries.
FastAPI is optional and is needed only for the worker. Importing the provider
neutral runtime does not require LangChain or LangGraph.

## Conversation behavior

`LangGraphSession` accepts the latest user message as text. It sends that one
message to the graph and uses a server-controlled `thread_id` for checkpoint
state. The session does not replay message history supplied by a client. The
application must derive the thread identifier from the authenticated identity
and conversation so that callers cannot share graph state.

For a non-streaming turn, the session returns the latest assistant message as
`AgentOutput`, together with usage when the graph reports it and its termination
status. A missing or unsupported final assistant result is a failure; a whole
graph state is never returned as answer text. Provider exceptions are represented
with a safe failure code rather than their raw message.

For a streaming turn, the session reads LangGraph's public v2 event stream. It
converts supported events to neutral events, omits internal tool arguments and
results, and emits one terminal event after the complete invocation, including
any approval resumes. It closes the graph event producer when a run completes,
fails, or is cancelled. If the client abandons the stream or execution fails,
the session is invalidated because the checkpoint may contain an unfinished
turn. Unsupported stream content produces incomplete termination rather than a
false success.

## Interruptions and approval

LangGraph interruptions are translated into ordered pending actions. A
domain-supplied resolver decides whether a batch requires a person and returns
one explicit approve or reject decision for each action. Decisions are matched
to actions in their original order before the graph resumes.

The shared runtime `ApprovalLoop` enforces per-invocation approval-question and
total-turn limits. If a limit is reached, it clears recorded authorizations and
makes a bounded attempt to reject suspended actions. A cleanup failure does not
approve or resume a pending action. The adapter invalidates the session after
execution failure, cancellation, or abandoned streaming.

The LangGraph adapter does not decide whether an action is authorized, ask the
user, or approve a tool based on its declaration. A missing resolver rejects
interruptions. Applications that keep grants outside the resolver provide a
cleanup hook so grants are removed when a turn is abandoned.

## Managed worker and tool admission

`LangGraphWorker` composes the shared `ManagedAgentWorker`; it does not provide
a second cache, authentication stack, endpoint router, or shutdown lifecycle.
The worker selects a graph factory only from trusted application configuration.
Its simple path accepts a graph, an awaitable that returns a graph, or an async
context manager that yields a graph. The factory is resolved per authenticated
conversation and its resources are closed when that conversation is retired.

Declared tools describe the agent surface but do not grant permission to run a
tool. A graph with tools requires an application admission hook. The worker
also checks an inspectable static tool surface against the agent definition;
dynamic or uninspectable surfaces cannot be proven from declarations alone. If
the required admission check is missing or fails, the worker refuses to serve
the graph.

Applications with domain-owned ticket stores, renderers, or resource lifetimes
can provide an advanced conversation factory. That factory owns those
application-specific policies while the shared worker still owns HTTP hosting,
authentication, cache, readiness, and shutdown behavior.

## Constraints and acceptance

- The client sends only the latest user text; checkpoint identity comes from
  authenticated server context and the conversation identifier.
- Final output is selected from a supported assistant message, not an arbitrary
  framework state object.
- Streams close their producer and emit one terminal event on normal completion;
  failures and abandoned or cancelled turns cannot be reused as healthy state.
- Approval decisions are explicit, ordered, bounded, and fail closed.
- Tool declarations are not authorization. A graph with tools requires an
  application admission hook, and unprovable surfaces cannot be inferred from
  declarations alone.
- The core agents distribution remains usable without LangChain, LangGraph, or
  FastAPI. The integration is Python-only; .NET and Java parity is not implied.

The implementation and public API are described in the
[LangChain user guide](../../docs/python/langchain.md). The source behavior is
covered by the integration tests under `tests/integration/python/`, including
`test_langgraph_worker.py` and `test_native_worker.py`.
