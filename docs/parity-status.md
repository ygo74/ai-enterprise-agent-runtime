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
| Untrusted content and prompt fence | `domains.security.untrusted`, `.fencing`, `.prompt_envelope` | pending | pending | `tests/integration/python/test_untrusted_content.py` |
| Conversation state cache | `domains.sessions.conversation_cache` | pending | pending | `tests/integration/python/test_conversation_cache.py` |
| OIDC discovery and HTTP settings | `domains.auth.oidc_discovery`, `domains.configuration.agent_http_settings` | pending | pending | `tests/integration/python/test_agent_http_settings.py` |
| MCP transport, binding, dialects, OAuth | `domains.mcp` | pending | pending | `tests/integration/python/test_mcp_plumbing.py` |

## 2026-09-13 — MCP server hosting and the shared authentication policy

Origin: an MCP server and an agent must answer exactly the same question about who
is calling, but almost nothing else is shared. Expressing that required splitting
the Python runtime into three distributions, and gave the servers of the AI Agent
Lab one authentication model instead of one per server.

Accepted constraint: **Python only, for now**, for the same reason as the entries
above. The Python tests listed here are the contract.

Note for .NET and Java: the *distribution* split is a Python packaging decision, not
a contract. The equivalent there is namespace separation - the security types must
not require the agent-hosting assembly, and MCP hosting must not require either.

| Capability | Python module | .NET | Java | Behaviour contract |
|---|---|---|---|---|
| Authentication policy and modes | `domains.auth.authentication_policy` | pending | pending | `tests/integration/python/test_authentication_policy.py` |
| Scheme-prefixed API keys | `domains.auth.apikey_authenticator` | pending | pending | `tests/integration/python/test_authentication_policy.py` |
| MCP server hosting | `domains.mcpserver.host` | pending | pending | `tests/integration/python/test_mcp_server_hosting.py` |
| MCP bind and public address | `domains.mcpserver.http_binding` | pending | pending | `tests/integration/python/test_mcp_server_hosting.py` |
| OAuth protected-resource metadata | `domains.mcpserver.protected_resource` | pending | pending | `tests/integration/python/test_mcp_server_hosting.py` |
| MCP authentication settings | `domains.mcpserver.settings` | pending | pending | `tests/integration/python/test_mcp_server_settings.py` |

### What these implementations must preserve

- **Anonymity is a decision, never a residue.** A host that was told nothing refuses
  to start; only an explicitly named "none" mode serves everyone. The scheme may be
  inferred from an unambiguous signal - a configured token means a token is checked -
  but silence is never inferred as anonymity.
- **One authentication model serves every host.** An agent and an MCP server run the
  same chain. A server-specific authentication path is how a weaker one appears
  without anybody deciding it should.
- **Adding a scheme requires no change to the foundation.** Basic, Kerberos or mutual
  TLS are implementations of the `Authenticator` contract. The Python suite proves
  this by running one written entirely outside the library.
- **An authenticator that raises is a refusal, not a 500.** The extension point is
  arbitrary code on the request path, and an unauthenticated caller able to produce a
  traceback in the log of a credential-holding process is a log-flood vector.
- **A server that would refuse its own callers does not start.** The DNS-rebinding
  allow-list is read at start-up and compared against the address callers use. It
  cannot be probed: the only route that enforces it is the one the authentication
  guard sits in front of.
- **A bind address is not a public name.** A wildcard bind means "every interface",
  which no caller can put in a `Host` header, so it must never become an OAuth
  resource identifier.
- **The health probe is open in every mode and discloses only liveness.** An
  orchestrator must be able to ask whether a process is alive without being handed a
  credential to do it.
- **A server that implements no OAuth flow answers 404 on the metadata path, not
  401.** A probing client must read "I am not a resource server", not "there is a
  flow here, you just need a credential".
- **Only asymmetric algorithms validate tokens.** A symmetric one would mean the
  resource server holds the key that signs them, which turns it into an issuer by
  accident.
- **A refusal says nothing about what was wrong.** Which part failed is information a
  guesser can use; the operator has the log.


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
- **Untrusted content is redacted by construction and readable only on purpose.**
  `repr` and `str` never reveal a payload; `expose()` is the only way in, which is
  what makes every dereference reviewable. The origin is a value object declared
  by the domain that owns it, never an enumeration in this library.
- **Fenced content cannot close its own block.** The delimiter is unguessable and
  differs per rendering, any copy of it found inside the content is neutralised,
  and a request carrying no untrusted context renders no fence at all - announcing
  one that is not there teaches a model to discount the announcement when it is.
- **A leased conversation is never closed.** Eviction and expiry skip an entry
  somebody is using, and a cache at its bound is allowed to overshoot rather than
  close a runtime mid-turn. Builds and closers are awaited off the lock, so one
  unresponsive server cannot stall every conversation in the process.
- **A signing key set is discovered, not guessed.** Appending a path to the issuer
  works for one provider; reading `jwks_uri` from its OpenID configuration works
  for all of them. An explicit override still wins.
- **An undeclared capability is never offered to the model.** A binding that
  advertised one without naming the tool behind it would fail on the first call -
  for a gated operation, *after* somebody approved it - so it fails at load time.
- **The requested OAuth scope is re-pinned before every authorisation attempt.**
  Without it the SDK substitutes whatever the resource server advertises, which
  for at least one well-known server means full mailbox control including
  permanent deletion.

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
- `domains.sessions` and `domains.mcp` are **Python-first for a stronger reason**
  than the rest: the first is built on `asyncio` primitives and the second on the
  Python MCP SDK. Their .NET and Java equivalents will be rewrites against the
  same behaviour contract rather than transliterations.
- `domains.mcp` deliberately **does not** interpret an application's capability
  names, withdraw a capability by itself, or know a provider. A binding's
  `read_only_variable` is carried as schema; deciding what it means for a given
  deployment is the application's call. Scope *values* likewise stay with whoever
  knows which provider they belong to - only the pinning mechanism is here.
