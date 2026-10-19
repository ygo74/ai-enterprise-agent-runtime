# MCP client and server

Model Context Protocol support is split into two Python distributions with
different responsibilities. The agent distribution contains an optional MCP
client; the MCP distribution hosts an MCP server and depends only on the shared
security distribution.

## Client used by agents

Agent applications commonly repeat binding parsing, transport lifecycle, and
dialect selection around their domain-specific MCP tools. The generic client
API centralizes those mechanics and validates integration details before a
tool call can be offered for execution.

The `ygo74-agent-runtime-agents[mcp]` extra installs the MCP SDK, HTTP client,
and YAML support. `McpServerBinding` describes a named server, transport,
declared application capabilities, mappings from application tool aliases to
remote tool names, and transport settings. The supported transports are stdio
and streamable HTTP. A YAML loader validates that the transport endpoint is
present and capability names belong to the application-owned enum. It accepts
an explicit path, leaving configuration location to the application. The
binding's `require_declared_capabilities()` and `require_aliases()` methods let
an application or dialect reject missing tool mappings before exposing
capabilities or making a call.

`McpConnection` opens and initializes a session lazily on first use, reuses that
session for concurrent tool calls, and closes its transport through an async
close operation. Connection failures are translated to MCP runtime errors. The
connection can receive application-computed HTTP request headers; their values
are redacted from object representations and are not logged by the runtime.
Applications remain responsible for selecting credentials, scoping headers to
the correct caller, resolving deployment secret references, and applying
policies such as withdrawing write capabilities in read-only mode.

`DialectRegistry[ToolsT, Params]` selects a typed, application-provided factory
from the binding's dialect name. It reports unknown dialects when the
application asks it to build a client and can use an application error factory
to preserve domain-specific error categories. Binding, connection, and registry
mechanics do not translate domain inputs or decide which remote tools are
authorized; those remain application responsibilities. The agents package
does not host the remote server.

## Managed HTTP client pools and resilience

McpAgentRegistryLoader groups an agent's skills by the configured MCP server
name. Skills that reference the same name share one McpConnection and its
connection pool within that agent registry. Loading the registry does not open
a network connection: the MCP session and, for HTTP transport, its HTTPX
AsyncClient are created lazily on first use. The client and pool are reused
across that server's MCP sessions, including the principal-partitioned sessions
used by OBO. A different server definition or agent registry owns a separate
client even when it points to the same URL; stdio connections have no HTTPX
pool. There is no client per request or user.

The agent registry closes each unique connection once. A connection first
closes its MCP sessions and then its owned HTTPX client. Applications should
close the registry during application shutdown. Pool settings are scoped to
each HTTP server: network.proxy_url accepts a credential-free HTTP or HTTPS
proxy URL, network.max_connections defaults to 20, and
network.max_keepalive_connections defaults to 10. TLS verification remains
enabled. request_timeout_seconds defaults to 30. Recommended practice is to
keep an agent to one or two MCP servers so its total pool and socket use stays
bounded; this is guidance, not a registry-enforced limit.

The HTTP-only network, retry, and circuit-breaker settings are optional typed
fields in each MCP server YAML file. The values below show their defaults;
proxy_url is unset by default and appears here as an example:

~~~yaml
request_timeout_seconds: 30
network:
  proxy_url: https://proxy.example.test:8443
  max_connections: 20
  max_keepalive_connections: 10
retry:
  max_attempts: 3
  initial_delay_seconds: 0.1
  maximum_delay_seconds: 0.5
circuit_breaker:
  failure_threshold: 5
  open_seconds: 30
~~~

These HTTP settings are rejected when explicitly supplied for a stdio server.

Retry attempts include the first request and are capped at ten. For retried MCP
transport operations, randomized exponential backoff shares a total deadline
bounded by the configured MCP request timeout. The MCP transport retries only
HTTP GET reads and POST initialization or ping requests when classified
transient transport failures or HTTP 500, 502, 503, or 504 responses occur. MCP
tool calls are never replayed automatically; JSON-RPC errors, tool results
marked isError, ordinary client errors, malformed responses, and application
failures are not retried. The default RFC 8693 OBO source uses the same
per-server HTTPX client and that server's retry policy; its default total
exchange deadline is 10 seconds and its breaker is keyed to the OAuth token
endpoint.

An application-supplied token source retains responsibility for its own HTTP
policy.

The breaker is keyed by upstream service identity, independently of the HTTP
pool or caller identity. With the default registry, callers targeting the same
MCP endpoint in one process share state; different endpoints remain isolated.
Breaker state is process-local and is not distributed across workers. After five
consecutive availability failures by default, the breaker rejects calls for 30
seconds without sending them; it then allows one recovery probe. Success closes
the breaker, while probe failure starts a new open interval. Classified
transport failures and HTTP 5xx responses count toward availability; an
MCP-level error returned in an HTTP success response does not. Conflicting
breaker settings for the same service identity are rejected. OIDC and JWKS use
the authentication configuration and shared security lifecycle described in
the [authentication specification](../security/authentication-and-authorization.md),
not the MCP server YAML.

Per-request context headers and principal isolation use the neutral
[agent invocation context contract](../contracts/agent-invocation-context.md).

These policies cover the MCP resource endpoint and default OBO token exchange,
alongside the OIDC/JWKS lookups described in the authentication specification.
The runtime does not take ownership of application, framework, or model-provider
HTTP clients.

## Hosting an MCP server

The `ygo74-agent-runtime-mcp` distribution wraps an MCP application with
`McpServerHost`. The `http` extra supplies streamable HTTP hosting; stdio use
does not require that extra. The host applies a shared `AuthenticationPolicy`
to protected HTTP requests and places the authenticated context on the request
scope. It adds an unauthenticated `/healthz` route and, when configured, public
OAuth protected-resource metadata. Authentication can be anonymous only when
the host explicitly chooses `AuthenticationPolicy.anonymous()`.

The application still defines tools and their data access policy. Authentication
identifies the caller; it does not automatically authorize a tool operation or
make an untrusted tool argument authoritative for the subject whose data is
accessed. The host validates its binding and checks FastMCP's DNS-rebinding
allow-list against the public host configuration before serving.

## Packaging and boundaries

The client and server are separate roles: installing the MCP host does not pull
in agent discovery, endpoint routes, or conversation state. The client extra is
also optional so applications that only use contracts or provider endpoints do
not need the MCP SDK. Client binding, connection, and dialect-registry APIs are
Python-first, as is MCP server hosting; .NET and Java do not provide equivalent
MCP client or server APIs in this repository.
