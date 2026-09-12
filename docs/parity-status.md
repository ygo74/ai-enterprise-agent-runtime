# Parity status

The constitution of this repository requires every capability to be implemented
with equivalent behaviour across Python, .NET and Java, *unless a documented
platform constraint is accepted in writing* (Core Principle I).

This file is that written record. It lists capabilities that currently ship in
one language only, why, and what the other implementations must provide to reach
parity. An entry here is a debt with a name, not a waiver.

## 2026-09-12 — capabilities adopted from the AI Agent Lab

Origin: these components were written and proven in the `ai_agents` laboratory,
where two independent agents (a mail agent on Microsoft Agent Framework, a wiki
agent on LangChain/LangGraph) had each grown their own copy. They were moved here
because they contain no business knowledge and because a copy per agent is one
copy away from a weaker security path.

Accepted constraint: **Python only, for now.** The source material is Python, and
implementing .NET and Java from the same contract is a separate, sequenced effort
rather than a reason to delay the Python consolidation. The behaviour is specified
by the Python tests listed below, which are the contract the other languages must
satisfy.

| Capability | Python module | .NET | Java | Behaviour contract |
|---|---|---|---|---|
| Security errors | `domains.security.security_errors` | pending | pending | `tests/integration/python/test_security_posture.py` |
| Permission model | `domains.security.permissions` | pending | pending | `tests/integration/python/test_permissions.py` |
| User context | `domains.security.user_context` | pending | pending | `tests/integration/python/test_security_posture.py` |
| Operation classification | `domains.security.operations` | pending | pending | `tests/integration/python/test_security_posture.py` |
| Security floor | `domains.security.floor` | pending | pending | `tests/integration/python/test_security_posture.py` |
| Audit trail | `domains.security.audit` | pending | pending | `tests/integration/python/test_security_posture.py` |
| Agent principal | `domains.auth.agent_principal` | pending | pending | `tests/integration/python/test_agent_principal.py` |
| Conversation port | `domains.contracts.conversation` | pending | pending | `tests/integration/python/test_conversation_payloads.py` |
| Conversation payloads | `domains.endpoints.conversation_payloads` | pending | pending | `tests/integration/python/test_conversation_payloads.py` |
| Manifest contract | `domains.contracts.manifests` | pending | pending | `tests/integration/python/test_capability_registry.py` |
| Capability registry | `domains.contracts.capability_registry` | pending | pending | `tests/integration/python/test_capability_registry.py` |

### What the .NET and Java implementations must preserve

These are the properties the Python tests assert. They are security properties
rather than conveniences, so an implementation that omits one is not merely
incomplete, it is wrong.

- **A principal is never invented.** An absent authentication context is a refusal
  to serve, never a fallback to an anonymous or default identity. The subject is
  read from the verified authentication context and never from the request body.
- **The address is optional, the subject is not.** An agent that addresses its
  subject by e-mail asks for one explicitly; an agent whose accounts are not
  e-mail addresses must not be made to invent one. The subject is what state is
  partitioned by, so it is always mandatory.
- **A conversation key puts the authenticated subject first.** A caller supplying
  somebody else's conversation identifier must reach their own state, never that
  person's.
- **A permission is declared by the domain that owns it.** The library ships the
  registry and the value type, never a catalogue of permissions.
- **A configuration below the security floor is refused, not corrected.** A
  control that repairs itself in silence teaches nobody that the configuration was
  wrong. Risk level and the floor answer different questions and must not be
  conflated.
- **An audit record carries identifiers and outcomes only.** No message body, no
  recipient list, no credential.
- **A capability cannot advertise one name while carrying the posture of
  another.** Both the manifest and the descriptor reject that mismatch at
  construction.
- **An empty request is reported, not answered.** Replying to a request that
  carried no user message would look like a model failure rather than a malformed
  request.

### Deliberate omissions

- `AgentPrincipal` has **no** method building a `UserContext`. Turning roles into
  permissions is an application decision, and an identity that knew how to grant
  itself rights would be the wrong shape. Hosts compose the two themselves.
- The **loading** of manifests - from YAML, a database or a service - is a host
  concern and is not part of this library. Only the typed contract is.
