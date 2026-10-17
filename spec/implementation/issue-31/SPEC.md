# Specification

## Issue

[#31 — HTTP connection optimization, retry strategy, and MCP session scope](https://github.com/ygo74/ai-enterprise-agent-runtime/issues/31)

## Objective

Make the Python runtime's managed outbound HTTP calls use application-lifecycle
HTTPX clients and reusable connection pools, bound transient-failure recovery,
and preserve caller-isolated lazy MCP sessions. Cover OIDC discovery and JWKS
retrieval as well as MCP and OAuth calls. Verify the values returned by an MCP
server, including errors, empty results, and structured results.

## Context and problem

The Python agents distribution already supports MCP Streamable HTTP, HTTP
timeouts, an optional per-server proxy, per-request context propagation, and
OBO sessions partitioned by authenticated principal. `McpConnection` opens an
MCP session only when first used. Its current HTTP client factory creates a
separate `httpx.AsyncClient` for each transport connection. The built-in RFC
8693 OBO token source also creates and closes an HTTP client for each exchange
unless a caller injects one.

The FastAPI endpoint authenticates a caller before binding the transport-neutral
`AgentInvocationContextScope` around the handler invocation. The generic
conversation entrypoint adds turn and correlation data to that context, and the
MCP adapter projects it into per-request headers and OBO session identity. This
is request context propagation; it does not eagerly create an MCP session. A
configured connection opens lazily when application code actually uses MCP,
with one session per verified principal in OBO mode.

`OidcDiscovery` uses `urllib.request`, and PyJWT's `PyJWKClient` fetches JWKS
documents through its own synchronous HTTP implementation. MCP Streamable HTTP
and the built-in OBO token source use HTTPX but currently create independent
clients. These outbound paths have no common lifecycle, retry policy, or circuit
breaker. JWT authentication is synchronous today, while MCP and OBO calls are
asynchronous, which is a compatibility and client-sharing constraint.

## Scope

- Replace runtime-managed `urllib` and PyJWT JWKS network fetches with HTTPX-
  backed paths, and extend MCP and default RFC 8693 OBO calls to use
  application-lifecycle HTTPX client ownership. Cover OIDC discovery and JWKS
  retrieval used by `JwtAuthenticator`, including when the shared security
  package is used by MCP server authentication.
- Create one long-lived `httpx.AsyncClient` per distinct HTTP MCP server in an
  agent registry, reusing it across that server's MCP sessions and OBO callers.
  Skills in the same agent that reference the same server share its connection
  and client; separately configured servers and agents have separate clients.
  Keep the server's proxy and request timeout settings on that server's client.
  Preserve secure TLS verification by default.
- Use a separate long-lived synchronous HTTPX client for JWT/OIDC discovery and
  JWKS retrieval, shared by the application's authenticators. Preserve the
  current synchronous authentication APIs.
- Keep per-request MCP headers, MCP OAuth authentication, and OBO credentials
  isolated to the appropriate request, connection, and authenticated principal
  when the client object is shared.
- Add a typed retry policy with a small, bounded attempt count and bounded
  backoff for transient transport failures. The total retry sequence must fit
  within the configured request deadline.
- Add a per-remote-service circuit breaker that can stop repeated attempts
  while a service is unavailable and permit a later recovery attempt. Make its
  failure threshold and open interval configurable with conservative defaults.
- Retry only idempotent OIDC discovery/JWKS reads, safe connection/session
  setup, and the standard token-exchange operation. Never automatically replay
  an MCP tool call whose server-side outcome may be unknown after a transport
  failure. Never retry JSON-RPC errors, MCP tool results marked `isError`,
  ordinary client errors, malformed responses, or application-level failures.
- Exercise a local MCP server that returns successful, error, empty, and
  structured-content results. Preserve the MCP SDK result fields and error
  semantics at the client boundary.
- Preserve lazy MCP session creation, one shared MCP connection per server
  within a registry, and principal-partitioned OBO sessions. Keep request
  identity context bound after authentication at the endpoint boundary; do not
  create an MCP session or perform an MCP request for agents that do not use
  MCP.
- Keep existing direct `McpConnection` and token-source composition usable.
  Callers that inject an HTTPX client retain ownership; the runtime closes only
  clients it creates and owns.
- Update the Python MCP guide and a runnable example to explain shared client
  ownership, application startup/shutdown, timeout and retry behavior, the
  circuit breaker, and MCP result handling. Update the Python security guide
  with HTTPX ownership for OIDC discovery and JWKS retrieval, and the MCP
  server guide where its JWT validation uses the shared security package.

## Out of scope

- Adding MCP, HTTPX, retry, or circuit-breaker APIs to .NET or Java; this issue
  does not claim cross-language MCP parity.
- Changing MCP server routes or transport behavior beyond using the shared
  outbound client lifecycle for its OIDC/JWKS authentication lookups.
- Reusing or reconfiguring HTTP clients created by application code, model
  provider SDKs, or frameworks such as LangChain and Microsoft Agent Framework.
  The shared lifecycle covers outbound HTTP initiated directly by runtime
  libraries, including the Python security, agents, and MCP-server packages.
- Retrying MCP tool execution or changing MCP/JSON-RPC result contracts.
- Automatically retrying arbitrary application callbacks or deciding whether
  an application-owned operation is idempotent.
- Changing caller authorization, MCP tool allow-lists, OAuth scopes, or token
  cache policy.

## Expected behavior

1. An application can construct one runtime HTTP client owner for its
   lifecycle. Each distinct HTTP MCP server in an agent's registry gets one
   asynchronous client and pool. Skills in that agent using the same server
   share it, as do that server's principal-partitioned OBO sessions and its OBO
   token exchange. Separate server definitions and agents get separate MCP
   clients. A separate synchronous client and pool serves JWT/OIDC discovery
   and JWKS retrieval. No client is created per request or per user.
2. Each MCP client uses the proxy, timeout, and TLS behavior configured for
   that MCP server. It remains open while that server's sessions use it and
   closes once when the agent registry closes. The JWT/OIDC client is owned by
   the application authentication lifecycle. Injected clients remain caller-
   owned. Async clients are scoped to the application event loop that uses
   them.
3. Requests retain their configured timeout. Retry attempts and backoff are
   bounded by that request's total deadline. A retryable connection failure
   may be attempted again within policy limits; non-transient protocol,
   authentication, authorization, validation, and application errors surface
   without retry.
4. A service that crosses the configured consecutive-failure threshold is
   temporarily circuit-open. Requests short-circuit during that interval;
   after the interval, one recovery attempt is allowed and successful service
   responses close the circuit. Breaker state is keyed by upstream service
   identity (for example, the configured MCP server or OIDC issuer), shared by
   all callers using that service, and isolated from other services. It does not
   leak caller credentials or request data.
5. Tool calls are never replayed automatically after an ambiguous transport
   failure. Their existing failure is returned to the application so it can
   decide whether to retry based on its operation semantics.
6. The MCP client exposes actual server results without flattening empty
   content, `isError`, or `structuredContent`. Runtime errors and tool-result
   errors remain distinguishable from successful empty results.
7. The endpoint binds verified identity and request context for MCP consumers;
   a connection creates its MCP session lazily. OBO connections continue to
   isolate sessions by principal and fail closed without a verified principal
   and subject token. An agent with no MCP use opens no MCP session or transport.
8. An application that uses neither remote JWT/OIDC validation nor MCP/OBO
   outbound calls does not need to create the HTTP client owner or install the
   optional HTTPX/MCP dependencies.

## Architecture, interfaces, and data

- Add a typed, application-owned lifecycle abstraction for HTTPX client(s) and
  their `httpx.Limits`, timeout, TLS, and proxy configuration. Use it from
  `OidcDiscovery`, JWKS resolution, MCP transport construction, and the default
  OBO source. Keep HTTPX optional for installations that do not use outbound
  network-backed authentication or MCP.
- Do not close an injected client from `McpConnection`, the registry,
  `OidcDiscovery`, the JWKS resolver, or the token source; close each owned
  client once from its lifecycle owner after consumers stop.
- Preserve request-specific auth and context behavior in the HTTPX transport
  integration: static MCP headers, dynamic turn headers, session-bound OBO
  identity, and MCP OAuth must not bleed between servers, users, or requests.
- Keep `AgentInvocationContextScope` at the authenticated request boundary. It
  supplies trusted identity and correlation before application handlers run;
  the MCP adapter consumes it, and the lazy `McpConnection.session()` call
  remains responsible for opening or selecting the actual MCP session.
- Represent retry and breaker configuration with explicit typed settings and
  enums for fixed states or categories. Do not expose untyped maps as policy
  contracts. Do not include credentials, request bodies, or raw provider
  exceptions in logs or diagnostics.
- Preserve server-specific MCP HTTP settings. The registry creates a client
  for each distinct server configuration and applies that server's
  `network.proxy_url` and `request_timeout_seconds`; one server's settings must
  not override another's.
- OIDC discovery and JWKS retrieval must use the configured HTTPX policy and
  per-service breaker. Keep issuer/JWKS URL validation and key-set caching;
  never expose bearer tokens or raw provider exception details in diagnostics.

## Constraints and decisions

- Reuse existing `McpConnection`, `McpAgentRegistry`,
  `Rfc8693OAuthOnBehalfOfTokenSource`, `OidcDiscovery`, JWKS resolver, and
  request-context correlation instead of adding a second MCP connection or
  session abstraction.
- MCP protocol operations have different replay safety. Session/connection
  setup and the standard OBO token exchange may use bounded transport retries;
  MCP tool calls may not be automatically replayed because a lost response
  does not establish whether the remote operation ran.
- A circuit breaker is scoped to a stable upstream service identity, not to an
  end user, client, operation, or process-wide aggregate. Calls to the same
  configured MCP service share a breaker; OIDC discovery and JWKS lookups for
  the same issuer share a breaker; OBO exchanges share one for their configured
  token service. Distinct services have isolated breakers, and callers to the
  same service contribute to the same breaker state. Its diagnostics contain
  no caller token or tool payload. OBO session state remains partitioned by
  principal as it is today.
- Breaker identity is independent of HTTP client and network profile identity:
  calls to the same upstream service share one breaker even if they use separate
  pools, while different services never share breaker state.
- MCP client/server APIs are currently Python-only, so no .NET/Java parity
  work is implied. The affected Python package and optional dependency boundary
  remain unchanged.
- A local deterministic MCP server is the integration fixture; acceptance
  does not depend on public internet services or provider credentials.

## Acceptance criteria

- OIDC discovery and JWKS retrieval share the synchronous JWT/OIDC client. One
  agent's skills referencing the same MCP server share that server's
  asynchronous client, including across OBO principal sessions. Distinct MCP
  server definitions get distinct clients. Instrumentation proves clients are
  reused rather than created per request, tool call, or principal session.
- Concurrent calls reuse each server's HTTPX pool within its configured
  connection limit. Server-specific proxy and timeout settings are applied,
  and each managed client closes once after its dependents.
- Retry tests cover a transient network failure followed by recovery, retry
  exhaustion, a non-retryable failure, total-deadline enforcement, and the
  absence of retries for MCP tool calls and MCP/JSON-RPC result errors.
- Circuit-breaker tests cover closed, open, and half-open/recovery states,
  shared state for calls to the same service, isolation between services, and a
  bounded fast failure while open. Cover MCP, OBO, and OIDC/JWKS paths.
- A local MCP server returns normal content, an MCP `isError` result, empty
  content, and `structuredContent`; tests verify the exact result shape and
  that MCP errors are not turned into successful empty results.
- Context tests prove overlapping calls and users never exchange identity,
  request, conversation, auth, or OBO headers while sharing the HTTPX client.
- OIDC/JWKS tests prove the configured HTTPX client, timeout, proxy/TLS policy,
  key-set cache, and service-scoped breaker are used without logging bearer
  tokens or provider response bodies.
- Lazy-session tests prove no MCP client transport/session is opened until a
  caller uses MCP, OBO sessions remain partitioned by principal, and the
  endpoint-bound context remains available through non-streaming and streaming
  handlers.
- Existing direct-construction APIs and injected-client ownership remain
  backward compatible; importing unrelated base runtime domains does not
  require HTTPX or the MCP SDK.
- Documentation explains the application lifecycle and actual retry boundary.

## Parity, UX, and performance requirements

- **Parity impact:** Python outbound-client lifecycle and MCP changes. The
  Python security package has .NET and Java counterparts, but this issue's
  HTTPX/OIDC transport work remains Python-specific; parity must not be claimed
  for those runtimes without an approved equivalent design.
- **UX consistency:** Configuration validation reports the affected MCP server
  setting without exposing secrets. Retry and breaker behavior is predictable,
  bounded, and documented. The breaker is shared by callers for the same
  upstream service and isolated across services. MCP result fields remain
  unchanged at the SDK-facing API.
- **Mandatory tests:** Test-first coverage includes typed policy validation,
  lifecycle/ownership, pooled concurrency, request-context isolation, retry and
  breaker state transitions, OIDC/JWKS behavior, MCP result variants, package
  optionality, and a local MCP integration server.
- **Performance budgets:** The lifecycle owner creates at most one HTTPX
  client per distinct HTTP MCP server in an agent registry, plus a shared
  synchronous JWT/OIDC client. MCP clients are created lazily on first use,
  reused thereafter, and never created per request, operation, or principal.
  A closed-circuit policy check adds less than 1 ms p95 to the no-network
  dispatch path; an open-circuit rejection returns in less than 10 ms p95.
  Retry/backoff adds no time beyond the existing request timeout budget. A
  local concurrency benchmark must confirm each MCP pool respects its per-
  server maximum connection limit under 100 concurrent operations.

## Risks and open questions

- The MCP SDK currently receives per-connection client factories that carry
  request-context hooks and may also receive OAuth handlers. Reusing one
  `AsyncClient` per configured server across that server's principal-partitioned
  sessions must preserve per-request and per-principal behavior while keeping
  one pool and one close owner per agent/server. Confirm the pinned MCP SDK
  injection and ownership semantics before implementation.
- `JwtAuthenticator`, `RequestAuthenticator`, and FastAPI endpoint auth are
  synchronous today. `OidcDiscovery` and PyJWT's `PyJWKClient` use synchronous
  network calls, while MCP and OBO are asynchronous. Preserve those APIs with
  shared sync/async clients under the same lifecycle owner; making JWT
  authentication async solely to use one `AsyncClient` is outside the proposed
  design.
- A client per MCP server gives isolation and honors per-server proxy and
  timeout settings, while agents that configure many servers can use more
  sockets. The user's intended operating guidance is one or two MCP servers per
  agent; pool limits remain explicit so each agent's aggregate connection use
  stays bounded.
- Define the default retry count, backoff bounds, breaker threshold, and
  cooldown during PLAN review using the existing 30-second MCP request timeout
  and deployment expectations. Retries must remain subordinate to the total
  request deadline.
- A circuit breaker can hide short-lived outages from downstream services but
  also rejects calls while open. The default cooldown and whether operators need
  a manual reset hook should be decided during PLAN review.
