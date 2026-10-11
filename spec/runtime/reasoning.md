# Framework-neutral reasoning port

## Purpose and role

Agent skills sometimes need language-model reasoning, such as summarising
retrieved content or returning a typed classification. If a skill depends on a
specific framework client, its domain behavior becomes tied to that framework.
The Python runtime's `TextReasoner` protocol keeps this call at a small,
framework-neutral boundary.

`TextReasoner.reason(request, response_model)` accepts a `ReasoningRequest` and
returns a value validated as the requested Pydantic model. Framework adapters
provide the concrete model client. They own provider selection, credentials,
timeouts, retries, and framework-specific invocation. The runtime does not
choose a model or make reasoning calls on an application's behalf.

## Request and result behavior

`ReasoningRequest` separates trusted `instructions` and `task` from labelled
untrusted context sections. The context uses `UntrustedText`; the
`PromptEnvelopeBuilder` fences each section and labels its source before
rendering it into a prompt. A request without untrusted sections receives no
untrusted-content marker.

The reasoner returns the requested typed model. A backend that is unavailable
raises `ReasoningUnavailableError`; a result that cannot be validated or used
raises `ReasoningOutputError`. Both belong to the shared `ReasoningError`
hierarchy. Callers decide whether to retry, refuse the operation, or report the
failure.

Prompt fencing helps the model treat retrieved content as data. It is not an
authorization gate. The application must still enforce permissions and
confirmation rules in deterministic code before protected operations execute.

## Scope and limits

- The port is an async Python API and accepts a typed output model.
- It does not expose a provider SDK, credentials, application tool, or framework
  state to the domain skill.
- It does not guarantee that a model follows instructions; deterministic
  security controls remain outside the model call.
- No .NET or Java equivalent is currently provided.

The API lives in [`reasoning/ports.py`](../../packages/python/agents/ygo74/agent_runtime/domains/reasoning/ports.py)
and [`reasoning/errors.py`](../../packages/python/agents/ygo74/agent_runtime/domains/reasoning/errors.py).
The request and fence are defined in
[`prompt_envelope.py`](../../packages/python/security/ygo74/agent_runtime/domains/security/prompt_envelope.py)
and the [application security specification](../security/application-security-primitives.md).
