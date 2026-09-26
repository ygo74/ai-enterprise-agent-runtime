# Application security primitives

The Python security distribution supplies composable primitives for application
authorization, operation classification, audit records, caller context, and
handling untrusted text. These primitives do not create a complete enterprise
policy by themselves. Application domains declare permissions, map authenticated
identities to those permissions, and call the checks at the operation boundary.

## Permissions and user context

`Permission` is an application-owned domain/action value, such as
`mail:send`. `PermissionRegistry` resolves the permissions an application
explicitly declares; importing a domain does not register permissions as a side
effect. `UserContext` carries a user ID, session ID, and an immutable set of
permissions. `require_permission` raises a typed denial when a requested
permission is absent. It contains no token, password, or other credential.

The runtime does not derive permissions from roles or claims. The application
maps trusted identity-provider data and business rules into the permissions
given to a `UserContext`.

## Operation classification and security floor

An application declares each exposed capability with a
`ToolOperationDescriptor`: tool name, `READ` or `WRITE` type, risk (`LOW`,
`MEDIUM`, `HIGH`), required permission, and whether confirmation is required by
default. This metadata is code-owned and is not supplied by model output.

`SecurityFloor` defines the minimum risk and confirmation posture for selected
operations. It rejects descriptors configured below the declared minimum and
can make confirmation non-overridable. Risk level alone does not require
confirmation; policy and floor configuration determine that requirement. The
human approval flow consumes these values before execution.

## Audit trail

`AuditRecord` identifies the operation, its type and risk, outcome, user,
session, optional target and confirmation request, error type, and occurrence
time. Outcomes are `EXECUTED`, `DECLINED`, `BLOCKED`, and `FAILED`.
`AuditTrail` is an application extension point; the package includes
process-local in-memory and standard-logging implementations. Records omit
message bodies, retrieved content, recipients, and credentials. Applications
that need durable retention supply their own trail implementation.

## Untrusted content and prompt envelopes

`UntrustedText` pairs third-party text with an `UntrustedOrigin`. Its string and
debug representations redact the payload; code must explicitly call `expose()`
to read it. `ReasoningRequest` separates application instructions and task from
labelled untrusted context. `PromptEnvelopeBuilder` renders that context with a
per-rendering random delimiter, neutralizes delimiter collisions, and labels
the content as data rather than instruction.

Prompt fencing is a model-facing defense-in-depth measure. It does not enforce
authorization or prevent side effects. Protected operations still require
application permission checks and, where configured, the deterministic
confirmation gate described in [human approval](../runtime/human-approval.md).

## Scope

These primitives are currently Python-only. .NET and Java expose authentication
and runtime contracts but not these application-security domains. They do not
replace identity-provider configuration, authorization policy, persistence,
data-retention rules, or secret management owned by the host application.
