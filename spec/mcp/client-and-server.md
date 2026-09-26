# MCP client and server

Model Context Protocol support is split into two Python distributions with
different responsibilities. The agent distribution contains an optional MCP
client; the MCP distribution hosts an MCP server and depends only on the shared
security distribution.

## Client used by agents

The `ygo74-agent-runtime-agents[mcp]` extra installs the MCP SDK, HTTP client,
and YAML support. `McpServerBinding` describes a named server, transport,
declared application capabilities, mappings from application tool aliases to
remote tool names, and transport settings. The supported transports are stdio
and streamable HTTP. A YAML loader validates that the transport endpoint is
present, capabilities are known to the application, and declared capabilities
have corresponding tool mappings.

`McpConnection` opens and initializes a session lazily on first use, reuses that
session for concurrent tool calls, and closes its transport through an async
close operation. Connection failures are translated to MCP runtime errors. The
binding and connection do not choose an application's capability vocabulary,
translate domain inputs, or decide which remote tools are authorized; those
remain application responsibilities. The agents package does not host the
remote server.

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
not need the MCP SDK. MCP integration is currently Python-only; .NET and Java
do not provide an MCP client or server in this repository.
