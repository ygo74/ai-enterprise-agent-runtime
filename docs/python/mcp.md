# Model Context Protocol (MCP)

The Python runtime has separate packages for connecting an agent to an MCP
server and for hosting an MCP server. Install the package that matches the role
of the process; see [installation](installation.md).

## MCP client for agent use cases

The `ygo74-agent-runtime-agents[mcp]` extra installs the MCP client dependencies
for the agents distribution. `McpServerBinding` describes a server, transport
(`stdio` or streamable HTTP), capabilities, and tool names. `McpConnection`
manages the client session and transport lifecycle. Application code supplies
its own capability enum and mapping from use-case operations to remote tools.
The client does not host the remote server.

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
