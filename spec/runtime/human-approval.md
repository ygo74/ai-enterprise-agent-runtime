# Human approval

The Python runtime includes framework-independent policy and execution
primitives for operations that may need a human decision. It does not provide a
universal approval UI or automatically suspend and resume an agent framework.
The application owns the interaction channel and any suspended agent state.

## Policy inputs

Application code describes a capability with a `ToolOperationDescriptor`,
including its required permission, read/write classification, risk, and default
confirmation requirement. `ConfiguredConfirmationPolicy` combines this default
with per-user preferences and a `SecurityFloor`: a mandatory floor wins, then
`always_confirm`, then `auto_approve`, then the descriptor default. An
`always_confirm` preference takes precedence if a tool appears in both sets.
Risk level alone does not imply confirmation.

Preferences are configuration rather than permissions. A skipped confirmation
never skips the operation's permission check, and a security floor can prevent
preferences from disabling confirmation. Built-in preference stores and
confirmation ledgers are in-memory and process-local; deployments requiring
durability or cross-worker coordination provide protocol implementations.

## Request, decision, and execution gate

A `ConfirmationRequest` identifies the request, operation, user, title, target,
and labelled details to present to a person. A `ConfirmationDecision` records
approval or refusal and the deciding user. The request shown to the person is
carried forward unchanged; model output does not reconstruct or alter the
approved operation.

`ConfirmationGate` checks the user's required permission and, when confirmation
is needed, verifies that a request and decision exist, their request IDs match,
and both belong to the current user. A refusal or mismatch prevents execution.
`GatedOperationRunner` places that gate around an asynchronous operation and
records `BLOCKED`, `DECLINED`, `FAILED`, or `EXECUTED` outcomes through the
configured audit trail.

`ConfirmationBroker` coordinates a configured `ConfirmationAuthority` with a
`ConfirmationLedger`. An authority is application-supplied and may ask through
a console, web interface, or other channel. `UnattendedApprovalAuthority`
fails closed when no person can decide.

## Cross-request approval

For a chat or HTTP flow, `ConfirmationTicket` and
`PendingConfirmationStore` can carry a pending operation across requests. A
ticket is bound to its authenticated subject and conversation, contains the
operation arguments and expires. The command parser recognizes explicit
`CONFIRM` and `CANCEL` commands before model processing. The host must render the
pending action, store and restore any suspended agent state, and resume the
application flow. The integrated FastAPI example demonstrates this composition;
it is not an automatic endpoint feature.

In-memory ticket, ledger, and preference implementations are local to one
process. A multi-worker deployment needs shared implementations if an approval
may be answered by a different worker from the one that issued it.

## Limits

Human approval is implemented in Python only. The library supplies reusable
contracts and enforcement points, while applications remain responsible for
using the gate at every protected execution path. Framework-level interrupts
alone do not replace the gate.
