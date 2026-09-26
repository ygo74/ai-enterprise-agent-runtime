# Human-in-the-loop approval

The Python runtime provides reusable policy, approval, ticket, and execution
building blocks. Your application or agent framework still owns the interaction
that asks a person, stores any suspended agent state, and resumes the work.

The important boundary is that the model may propose an operation, but it does
not approve or execute that operation. Application code declares the operation
and its permission. A policy decides whether confirmation is required. A human
or framework supplies a decision, and application execution code checks that
decision before protected work runs.

For background on operation descriptors, permissions, security floors, and
audit records, see the [Python security guide](security.md). This page focuses
on how those pieces participate in approval flows.

## Choose an approval flow

| Flow | When to use it | Main pieces |
|---|---|---|
| Authority and ledger | A script or host asks for a decision before invoking the capability, or a framework collected a decision before calling its tool function | `ConfirmationBroker`, `ConfirmationAuthority`, `ConfirmationLedger`, `GatedOperationRunner` |
| Framework suspension | The framework can pause a proposed tool call and collect a decision before invoking it | Framework middleware plus a ledger/broker path that carries the exact request into execution |
| Cross-request ticket | A chat or HTTP API must return a response while a person decides, then continue in a later request | `ConfirmationTicket`, `PendingConfirmationStore`, command parsing, and app-owned resume logic |

The runtime does not provide a universal approval screen, chat card, or
framework adapter. The existing
[LangChain/LangGraph example](../examples/python-langchain-fastapi/04-human-in-the-loop/README.md)
shows the cross-request flow for a FastAPI agent.

## Declare the operation and confirmation policy

Confirmation starts with an application-owned
[`ToolOperationDescriptor`](../../packages/python/security/ygo74/agent_runtime/domains/security/operations.py).
It declares the operation name, `READ` / `WRITE` type, risk level, required
permission, and whether confirmation is required by default. The descriptor is
code-owned metadata; the model does not set it.

[`ConfiguredConfirmationPolicy`](../../packages/python/agents/ygo74/agent_runtime/domains/humanapproval/confirmation.py)
combines that default with per-user preferences and a
[`SecurityFloor`](../../packages/python/security/ygo74/agent_runtime/domains/security/floor.py):

1. If the floor makes confirmation mandatory for the operation, it cannot be
   overridden.
2. Otherwise, a per-user `always_confirm` preference requires confirmation.
3. Otherwise, a per-user `auto_approve` preference skips it.
4. If neither preference applies, the descriptor's
   `confirmation_required_by_default` value decides.

If a tool appears in both preference sets, `always_confirm` wins. Risk describes
the impact of an operation; a `HIGH` risk value does not by itself require
confirmation. Use the floor to make confirmation non-overridable.

```python
from ygo74.agent_runtime.domains.humanapproval.confirmation import (
    ConfiguredConfirmationPolicy,
    ConfirmationPreferences,
    InMemoryConfirmationPreferenceStore,
)
from ygo74.agent_runtime.domains.security.floor import OperationFloor, SecurityFloor
from ygo74.agent_runtime.domains.security.operations import (
    OperationType,
    RiskLevel,
    ToolOperationDescriptor,
)
from ygo74.agent_runtime.domains.security.permissions import Permission

send_mail = ToolOperationDescriptor(
    tool_name="send_mail",
    operation_type=OperationType.WRITE,
    risk_level=RiskLevel.HIGH,
    required_permission=Permission("mail", "send"),
    confirmation_required_by_default=True,
)

preferences = InMemoryConfirmationPreferenceStore()
floor = SecurityFloor([
    OperationFloor(
        tool_name="send_mail",
        minimum_risk=RiskLevel.HIGH,
        confirmation_always_required=True,
    )
])
policy = ConfiguredConfirmationPolicy(preferences, floor)
```

`InMemoryConfirmationPreferenceStore` is useful for local composition and
examples. A deployment that supports per-user preferences should supply a
durable `ConfirmationPreferenceStore`. Treat those preferences as application
configuration: they do not replace permission checks, and the floor still wins.
Likewise, `InMemoryConfirmationLedger` is process-local; use a shared
implementation if collecting an answer and invoking the capability can happen
in different workers or processes.

## Enforce the decision at execution

[`ConfirmationGate`](../../packages/python/agents/ygo74/agent_runtime/domains/humanapproval/confirmation.py)
is framework-independent. `ensure_approved(operation, user, request, decision)`
first checks `user.require_permission(operation.required_permission)`. If the
policy requires confirmation, it then requires both a request and a decision,
requires the decision's `request_id` to match the request, and checks that the
request and decision belong to the current `UserContext`. Missing, rejected,
mismatched, or unauthorized decisions raise typed security errors.

[`GatedOperationRunner`](../../packages/python/agents/ygo74/agent_runtime/domains/humanapproval/gated_operations.py)
combines an operation catalogue, policy, gate, and audit trail around an async
operation. It records four outcomes:

- `BLOCKED`: permission was missing or a required decision was not supplied or
  did not match;
- `DECLINED`: the person refused;
- `FAILED`: the operation was allowed but raised while running;
- `EXECUTED`: it completed successfully.

The runner is a useful common execution path for capabilities. A framework
middleware interrupt is not a substitute for this execution check: code may be
called outside that framework, and a gated skill should retain its own guard.

## Obtain a request and decision before calling a tool

[`ConfirmationRequest`](../../packages/python/agents/ygo74/agent_runtime/domains/humanapproval/confirmation.py)
describes the operation a person is judging. It includes a request ID, the
operation descriptor, the user it was requested for, a title, a target, and
labelled details. Build those details from application data so the request
explains what will actually happen. Use the same request object when carrying
the decision to the gate; do not ask a model to paraphrase or reconstruct the
approval after the person has answered.

An application can implement `ConfirmationAuthority.obtain(request, user)` to
ask through its console, web UI, or other channel. A collected decision has the
request ID, an `approved` boolean, and the ID of the user who decided.
[`ConfirmationBroker`](../../packages/python/agents/ygo74/agent_runtime/domains/humanapproval/broker.py)
coordinates that authority with a `ConfirmationLedger`:

- If confirmation is not required, `resolve` returns `(None, None)`.
- If a framework has already recorded an answer, the broker consumes it from
  the ledger and returns the exact request and decision previously shown.
- Otherwise, the broker asks the configured authority.

[`UnattendedApprovalAuthority`](../../packages/python/agents/ygo74/agent_runtime/domains/humanapproval/unattended.py)
is a fail-closed authority for integrations where an absent person must never
be treated as approval. For a complete execution, pair the broker with
`GatedOperationRunner.execute`, which checks the user permission and decision
again immediately before calling the operation.

For example, the application can prepare a human-readable request, let an
authority collect the answer, then pass both to the guarded operation runner.
Here `broker` and `runner` are already configured with the same policy and
operation catalogue; `mail_api.send` is the application's async capability:

```python
from ygo74.agent_runtime.domains.humanapproval.confirmation import ConfirmationDetail


async def send_approved_message(user, message_id, recipient):
    request, decision = await broker.resolve(
        required=runner.requires_confirmation("send_mail", user),
        build_request=lambda: runner.build_confirmation_request(
            "send_mail",
            user,
            "Send this message",
            target=message_id,
            details=(ConfirmationDetail(label="Recipient", value=recipient),),
        ),
        user=user,
    )
    return await runner.execute(
        "send_mail",
        user,
        operation=lambda: mail_api.send(message_id),
        target_id=message_id,
        request=request,
        decision=decision,
    )
```

## Keep approval across HTTP requests

An HTTP request should not remain open while a person decides. Instead, return
what is waiting and continue only after a later request carries the person's
answer. The ticket contract supports that flow:

1. The framework suspends a tool call before invoking the capability.
2. Application code builds a human-readable `ConfirmationRequest` and issues a
   [`ConfirmationTicket`](../../packages/python/agents/ygo74/agent_runtime/domains/humanapproval/tickets.py)
   containing that request and the exact proposed arguments.
3. The ticket is bound to the authenticated subject and conversation. The
   request completes without running the operation.
4. On a later turn, parse an exact confirmation command **before** passing
   ordinary user text to the model. Claim the ticket using the subject and
   conversation from server-side request context.
5. A valid approval resumes the suspended operation with the stored arguments;
   a cancellation consumes the ticket without running it.

The default ticket lifetime is 15 minutes. A ticket can be claimed once, must
match both its subject and conversation, and cannot be claimed after expiry.
Unknown, used, expired, or out-of-scope tickets return the same not-awaiting
result so the response does not reveal which case occurred. A ticket ID is not
a credential: derive the subject from the authenticated `auth_context`, never
from the command text.

[`PendingConfirmationStore`](../../packages/python/agents/ygo74/agent_runtime/domains/humanapproval/tickets.py)
defines issue, claim, list, and discard operations. The supplied
`InMemoryPendingConfirmationStore` is for one process; a production
implementation must support atomic single-use claims across workers. Ticket
storage is only part of restart-safe hosting: persist or share the framework's
suspended graph/checkpoint and the application's turn bookkeeping as well.

[`ConfirmationCommandParser`](../../packages/python/agents/ygo74/agent_runtime/domains/humanapproval/commands.py)
recognizes only an exact `CONFIRM cfm-<hex>` or `CANCEL cfm-<hex>` command,
case-insensitively, with optional surrounding whitespace, Markdown decoration,
and final punctuation. A sentence that merely mentions a ticket is an ordinary
message. In the chat flow, consume a ticket on cancellation as well as
approval; otherwise an old operation could be approved after the person had
already declined it.

[`PendingConfirmationRenderer`](../../packages/python/agents/ygo74/agent_runtime/domains/humanapproval/pending_renderer.py)
renders the request title, details, and command the person should send. It
keeps each detail to one line, truncates long values, and redacts text that
looks like a ticket reference so retrieved content cannot imitate an approval
prompt.

## Keep the framework bridge in the host

The existing example uses LangChain's `HumanInTheLoopMiddleware` to suspend
calls, LangGraph's checkpointer to retain state, and a small
[`LangGraphApprovalBridge`](../examples/python-langchain-fastapi/04-human-in-the-loop/langgraph_approval.py)
to translate interrupts and resume commands. That bridge lives in the example,
not the runtime package.

The host uses the same operation list and confirmation policy to configure the
middleware and describe each pending call. It issues one ticket per suspended
tool call and waits for an answer to every call before resuming the graph, in
the order expected by the framework. The bridge accepts only `approve` and
`reject`: editing arguments after approval would change the operation, and a
free-form response delivered back to the model could make a refusal look like a
successful tool result.

The example derives `UserContext` from the runtime-authenticated caller and the
forwarded conversation ID. It does not trust a user ID in the request body to
partition tickets or graph state. Its current runtime state is in memory:
`InMemorySaver`, `InMemoryPendingConfirmationStore`, and dictionaries keep the
graph, tickets, and outstanding answers in one process. Behind multiple
workers or across restarts, provide shared/durable checkpoint and turn state
and an atomic ticket store.

## What the current example demonstrates

The [human-in-the-loop walkthrough](../examples/python-langchain-fastapi/04-human-in-the-loop/README.md)
is the existing end-to-end example. It requires Python 3.12 or newer, an OpenAI
API key, and access to Microsoft's public Microsoft Learn MCP service. Its
README contains the dependency installation, environment setup, server command,
and the first request / later `CONFIRM` or `CANCEL` sequence.

The example demonstrates the configured confirmation policy, operation
classification, tickets, in-memory ticket storage, literal command parsing,
bounded rendering, and the example-owned LangGraph bridge. It uses
`UserContext` to scope caller and conversation state, but does not wire the
generic `ConfirmationGate` or `GatedOperationRunner` into the tool itself. Use
those pieces when your capability also needs the runtime's domain permission
check at its execution boundary. The generic
`ConfirmationBroker`, `ConfirmationGate`, `GatedOperationRunner`,
`ConfirmationPresenter`, and `ConfirmedOperationRunner` are reusable API
contracts but are not wired into this example as a generic execution pipeline.
`ConfirmedOperationRunner` claims a ticket, records the decision in a ledger,
validates the saved arguments against the skill schema, and invokes the skill;
the skill implementation still needs to enforce its own permission and
confirmation gate. Domain-level behavior is covered in the existing
[human approval integration tests](../../tests/integration/python/test_human_approval.py),
but those tests are not a separate runnable user example.
