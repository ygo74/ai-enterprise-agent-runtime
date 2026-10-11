# Use MCP tools and host MCP servers

Model Context Protocol (MCP) lets an agent call tools exposed by another
process or service. The runtime provides MCP client bindings for agent
applications and a separate distribution for hosting MCP servers.

## Install the client or server package

For an agent that connects to an MCP service, install the agent package with its
MCP extra:

```bash
python -m pip install 'ygo74-agent-runtime-agents[mcp]'
```

For a server exposed over HTTP, install:

```bash
python -m pip install 'ygo74-agent-runtime-mcp[http]'
```

The MCP server can also use stdio. Install the MCP SDK explicitly for that
transport:

```bash
python -m pip install ygo74-agent-runtime-mcp 'mcp>=1.24,<2'
```

## Check an MCP server's authentication

The repository's [MCP server example](../../docs/examples/python-mcp-server/README.md)
listens on `127.0.0.1:9300`. From its folder, install `requirements.txt`, then
start it in API-key mode:

```powershell
python -m pip install -r requirements.txt
$env:DEMO_MCP_AUTH_MODE = "api_key"
$env:DEMO_MCP_HTTP_TOKEN = "<local-example-secret>"
python server.py
```

In another terminal, check the health route and try the protected MCP route
without a credential:

```powershell
curl.exe -i http://127.0.0.1:9300/healthz
curl.exe -i -X POST http://127.0.0.1:9300/mcp `
  -H "Accept: application/json, text/event-stream" `
  -H "Content-Type: application/json" `
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/list"}'
```

The health check returns `200`; the unauthenticated MCP request returns `401`.
The example's README shows the authenticated request and its expected response,
including the MCP session handshake. A `401` on the protected route means the
client credential is missing or invalid.

## Configure a remote tool

An MCP binding maps an application tool name to a server endpoint, transport,
authentication settings, and remote tool name. Keep tokens in environment
variables or a secret manager. The agent should expose only the capabilities it
needs, and the server should enforce its own authorization.

See [MCP client bindings and server hosting](../../docs/python/mcp.md) for
configuration fields, OAuth support, lifecycle rules, and the server host API.
