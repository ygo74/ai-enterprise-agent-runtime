# Model Context Protocol (MCP)

The Python runtime has separate packages for connecting an agent to an MCP
server and for hosting an MCP server. Install the package that matches the role
of the process; see [installation](installation.md).

## MCP client for agent use cases

The `ygo74-agent-runtime-agents[mcp]` extra installs the MCP client dependencies
for the agents distribution. Importing unrelated runtime domains does not
require this extra. `McpServerBinding[CapabilityT]` describes a server,
transport (`stdio` or streamable HTTP), application-defined `StrEnum`
capabilities, and the aliases a server uses for its tools. The generic loader
validates the binding against that enum and the declared endpoint. Bindings also
provide `require_aliases()` and `require_declared_capabilities()` checks so a
dialect can fail before its first tool call; the latter applies when capability
names are also keys in the alias map. An application keeps that choice with its
own catalog and dialect rules.

`McpConnection` manages one lazily opened client session and its transport. For
HTTP, applications may pass request-scoped headers; the runtime does not log
header values and its header mapping representation redacts them. The
application remains responsible for choosing credentials and ensuring a
connection is scoped to the right caller. Stdio environment-variable resolution
and deployment policies such as Wiki's read-only filter also remain application
responsibilities.

`DialectRegistry[ToolsT, Params]` dispatches by the binding's dialect and uses a
typed factory whose first parameter is the binding. Applications retain their
concrete dialect factories and can provide an error factory so transport and
dialect failures keep their public error categories. The client does not host
the remote server.

See the [MCP client binding](../../packages/python/agents/ygo74/agent_runtime/domains/mcp/binding.py)
and [dialect registry](../../packages/python/agents/ygo74/agent_runtime/domains/mcp/dialects.py).
The [LangChain + FastAPI example](../examples/python-langchain-fastapi/01-get-started/README.md)
connects to Microsoft's public Learn MCP service; that example requires its
external LLM and MCP service prerequisites.

## Host an MCP server

The `ygo74-agent-runtime-mcp` distribution hosts an MCP server without the agent
runtime. Install its `http` extra for streamable HTTP transport:

```bash
python -m pip install 'ygo74-agent-runtime-mcp[http]'
```

For stdio, install the MCP SDK explicitly because it is not a base dependency of
the server distribution:

```bash
python -m pip install ygo74-agent-runtime-mcp 'mcp>=1.24,<2'
```

`McpServerHost` wraps an MCP server application with an `AuthenticationPolicy`
and `McpHttpBinding`. Construct `FastMCP` with the actual host and port so its
DNS-rebinding allow-list includes the address clients use. The host exposes
`/healthz` and the protected-resource metadata route as public discovery
surfaces; tool requests are authenticated according to the configured policy.
An omitted HTTP authentication choice is a startup error rather than an
implicit anonymous service.

For setup and environment variables, follow the detailed [MCP server hosting
guide](../mcp-server-hosting.md) and [runnable MCP server example](../examples/python-mcp-server/README.md).
