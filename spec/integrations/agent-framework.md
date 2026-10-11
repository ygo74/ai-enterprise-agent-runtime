# Microsoft Agent Framework integration

## Purpose and role

Applications built with Microsoft Agent Framework already own a native `Agent`,
its tools, model client, and policies. They still need to map SDK output and
stream updates into runtime-neutral contracts and, optionally, connect a native
agent to the managed HTTP worker. The separately installed
`ygo74-agent-runtime-agentframework` distribution provides that binding.

The integration does not construct an agent from manifests or provide
application skills. It executes an existing native agent and leaves tool
authorization, credentials, prompt design, and domain composition to the
application. The core agents distribution does not depend on the framework.

## Result and stream conversion

`AgentFrameworkOutputAdapter` visits SDK response messages and their content and
returns typed `AgentOutput` plus safe conversion decisions. It supports text,
selected tool information, and media that the neutral contract can represent.
Unsupported SDK content is diagnosed instead of stringified or exposed as an
answer. Protected reasoning is always excluded; other reasoning is hidden unless
the application explicitly enables its exposure.

`AgentFrameworkStreamAdapter` converts real SDK updates into neutral stream
events. One adapter belongs to one invocation. It tracks content identity and
tool argument deltas, closes open items, and emits exactly one terminal event
when `finish()` is called. A developer must not call successful finalization
after an exception or cancellation. Raw tool arguments/results remain internal
unless the application deliberately exposes an allowed client-execution call.

Known provider usage is preserved, including known zero counts; unknown optional
counts remain unknown. Approval sub-runs that do not call a provider are not
counted as model usage. The Anthropic projection requires genuine input/output
counts and an initial usage event before visible stream content. The runtime
does not invent counts to meet that requirement.

## Native session and approvals

`AgentFrameworkSession` wraps an existing `SupportsAgentRun` agent and owns its
native `AgentSession`. The input profile is latest-user-text with
server-managed history; client history is not replayed. Normal calls use native
non-streaming execution, while streaming calls consume actual SDK updates.
Failed or cancelled native turns invalidate their session state.

The session uses the framework-neutral bounded `ApprovalLoop` for repeated
approval rounds. It can be given an application `ApprovalResolver` and grant
cleanup callback. Framework suspension and resumption are translated by the
integration; the application resolver owns the decision and any domain ticket
bridge. Missing approval policy fails closed.

An optional provider-continuation profile is available for applications that
require provider-managed history. When enabled, missing, stale, or inconsistent
provider continuation fails explicitly; the integration does not fall back to
replayed client history or silently switch storage. This requirement is opt-in
so local agents and other providers remain supported by default.

## Managed worker and tool admission

`AgentFrameworkWorker` composes the shared managed worker with a trusted native
factory. Authentication, identity partitioning, conversation cache, timeout,
readiness, and shutdown behavior come from the generic worker. The factory is
selected by trusted deployment configuration, not request content, and may
return a native agent, an awaitable, or an async context-managed resource.

Tool declarations are not permission grants. Declared native tools require an
application admission hook that checks deterministic execution controls. The
integration compares inspectable tool names with the declarations. Custom
agents and dynamic context providers need explicit admission because their
complete tool surface cannot be proven from the standard static surface alone.
If admission is missing or fails, the worker refuses to create that conversation.

## Constraints and acceptance

- The optional SDK dependency is limited to this integration distribution.
- Results and streams use the runtime's neutral output/event contracts.
- Client history is not replayed; the native session owns server-side history.
- Approval limits and abandonment cleanup are bounded and fail closed.
- Tool declarations never replace operation permission checks or admission.
- Provider continuation is enforced only when the application selects that
  profile.
- The integration is Python-only; .NET and Java output integrations remain
  pending.

The [Microsoft Agent Framework guide](../../doc/python/agentframework.md) and
[native-agent guide](../../doc/python/native-agents.md) show the public APIs.
The implementation is under
[`integrations/agentframework`](../../packages/python/agentframework/ygo74/agent_runtime/integrations/agentframework/);
the integration coverage includes
[`test_agentframework_binding.py`](../../tests/integration/python/test_agentframework_binding.py),
[`test_agentframework_output_adapter.py`](../../tests/integration/python/test_agentframework_output_adapter.py),
and [`test_native_worker.py`](../../tests/integration/python/test_native_worker.py).
