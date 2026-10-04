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
