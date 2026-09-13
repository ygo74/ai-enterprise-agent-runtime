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
| Token ports | `domains.auth.tokens` | pending | pending | `tests/integration/python/test_tokens.py` |
| Manifest-derived descriptor | `domains.discovery.manifest_descriptor` | pending | pending | `tests/integration/python/test_manifest_descriptor.py` |
| Human-approval domain | `domains.humanapproval` | pending | pending | `tests/integration/python/test_human_approval.py` |
| Gated operation runner | `domains.humanapproval.gated_operations` | pending | pending | `tests/integration/python/test_gated_operations.py` |

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
- **A credential is redacted by construction.** `AccessToken` never reveals its
  value through `repr` or `str`; the raw value is reachable only through an
  explicit `expose()`, which is what makes every dereference greppable in review.
  An empty credential is refused rather than carried.
- **A token is exchanged, never relayed.** `DelegatedTokenSource` exists because
  the MCP specification forbids passthrough and requires a server to check that a
  token was issued for it - which it cannot do if the agent forwards the one its
  own caller presented.
- **A descriptor reports the deployment, not an assumption.** The advertised
  security schemes are derived from the authentication actually configured, and
  `toolInvocation` from the skills actually declared. A service accepting only an
  API key must not advertise a bearer scheme, and an agent listing skills must not
  claim it invokes no tool.
- **A service that authenticates nobody is refused, not described.** An agent
  reachable without a caller has no subject to partition state by.
- **An approval is recorded against the exact request the person was shown, and
  replayed from the arguments stored with it.** The model describes an operation
  and then plays no part in running it: the arguments never travel back through
  it, so it cannot change them between the description and the execution.
- **A ticket is claimed once, by one subject, in one conversation, before it
  expires.** All four are checked when it is claimed, not when it is issued, and a
  refusal is worded identically whether the ticket never existed, was already
  used, expired, or belongs to somebody else - distinguishing them would tell a
  guesser which identifiers are real.
- **An approval is read before the model sees the turn.** The grammar is a verb
  and an identifier, nothing more. An approval the model could reinterpret is not
  an approval, and anything short of an exact match is an ordinary message.
- **Reaching an approval authority with nobody there refuses.** It means a gated
  capability was not suspended, which must not become an unattended side effect.
- **What is displayed cannot imitate the application.** Any ticket reference found
  in retrieved content is redacted, and each fact is confined to one truncated
  line so content cannot forge an entry or flood the reply.
- **The four audit outcomes stay distinguishable.** "Nobody was asked" and
  "somebody said no" are different events, and an audit trail that conflated them
  would answer its most important question wrongly.

### Deliberate omissions

- `AgentPrincipal` has **no** method building a `UserContext`. Turning roles into
  permissions is an application decision, and an identity that knew how to grant
  itself rights would be the wrong shape. Hosts compose the two themselves.
- The **loading** of manifests - from YAML, a database or a service - is a host
  concern and is not part of this library. Only the typed contract is.
- `InMemoryPendingConfirmationStore` holds **one process**. Behind two workers a
  ticket issued on one is unclaimable on the other, and a restart loses every
  pending approval. The `PendingConfirmationStore` protocol is the contract; a
  deployment needs a shared, atomic implementation of it. Everything that makes a
  claim safe is decided in the domain, not by the store, so replacing it is a
  drop-in - but it has to be done before this domain is called production-ready.
- The bridge between a framework's suspension mechanism and this domain is **not**
  here. LangGraph's interrupts, Microsoft Agent Framework's approval mode and
  whatever comes next are each that framework's business; a library that knew
  would have to know all of them. See
  `docs/examples/python-langchain-fastapi/04-human-in-the-loop` for what such a
  bridge looks like.
