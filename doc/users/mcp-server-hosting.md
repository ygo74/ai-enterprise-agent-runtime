# Host an MCP server

A Model Context Protocol server exposes tools to client applications. Hosting
it over HTTP makes the service reachable to every process that can reach its
network address, so the operator must choose an authentication policy and limit
network exposure deliberately.

## Protect the service

Use anonymous access only when the tools and data are intentionally public.
Otherwise require an API key or validate access tokens from a trusted identity
provider. The server should return an authentication error for a missing or
invalid credential and enforce authorization before running a tool. Keep
credentials out of URLs and logs.

## Expose a managed agent

Python agents can expose their existing conversation entrypoint through MCP Streamable HTTP by selecting `mcp` in the agent manifest's `http.endpoints`. This mounts `/mcp` in the same FastAPI application as any selected provider routes. The runtime exposes one conversational tool with `message` and optional `conversation_id` arguments. Its name and description default to the agent's `name` and `description`; optional `mcp_agent_operation_name` and `mcp_agent_description` keys override them independently. Clients should list tools before calling the agent operation. Set `mcp_agent_operation_name: invoke_agent` to retain that name for existing clients. The caller identity comes from the request's verified authentication context. With JWT authentication, configure `http.mcp.resource_url` as the public HTTPS resource URL. Install the agents package with its `http` and `mcp-server` extras.

The host starts the mounted MCP session manager and closes its resources with the parent FastAPI lifespan. The agent's existing conversation cache is process-local, so a deployment with multiple workers or replicas needs session affinity. See [agent hosting](agent-hosting.md) and the [Python MCP guide](../python/mcp.md) for configuration details.

A health endpoint may be public if it reveals only service availability, such
as `{"status":"ok"}`. Do not expose tool listings, configuration, or identity
provider details through an unauthenticated health response.

## Check a protected endpoint

A client connects to `/mcp` with the configured credential. Its MCP SDK handles
the Streamable HTTP initialization handshake and session headers. Once the
session is initialized, it lists tools by sending this JSON-RPC request:

```json
{"jsonrpc": "2.0", "id": 1, "method": "tools/list"}
```

The response contains the operation's `name`, `description`, and `inputSchema`
under `result.tools`. By default, the operation name and description come from
the agent manifest's `name` and `description`; `mcp_agent_operation_name` and
`mcp_agent_description` can override them independently. A client that connects
to more than one agent should inspect each server and use the operation name
returned by that server.

For example, `tools/list` returns the advertised metadata and the required and
optional arguments in the input schema:

```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "result": {
    "tools": [
      {
        "name": "<agent-name-or-mcp_agent_operation_name>",
        "description": "<agent-description-or-mcp_agent_description>",
        "inputSchema": {
          "type": "object",
          "properties": {
            "message": {"title": "Message", "type": "string"},
            "conversation_id": {
              "default": "default",
              "title": "Conversation Id",
              "type": "string"
            }
          },
          "required": ["message"]
        }
      }
    ]
  }
}
```

Call the discovered operation with a user message and, when needed, a
conversation identifier:

```json
{
  "jsonrpc": "2.0",
  "id": 2,
  "method": "tools/call",
  "params": {
    "name": "<operation-name-from-tools-list>",
    "arguments": {
      "message": "Summarize the project status.",
      "conversation_id": "project-review"
    }
  }
}
```

The `message` argument is required. `conversation_id` is optional and defaults
to `default`; reuse the same value to continue a conversation. The tool result
contains structured content with `status`, `conversation_id`, `output`, and
`metadata`. Authentication supplies the caller identity. Tool arguments do not
select a subject, email address, or roles.

A protected endpoint should reject this request when the credential is absent
or invalid. Confirm that the host address, TLS termination, and allowed Host
values match the deployment's public endpoint; a healthy process does not
necessarily mean the tool route is reachable.

The server remains responsible for deciding who may use each tool and what data
that tool can access. Client-side configuration is not a replacement for
server-side checks. Python hosting APIs and transport-specific options are
covered in [Python MCP documentation](../python/mcp.md); the runnable
[Python MCP server sample](../../samples/python/python-mcp-server/README.md)
shows a protected streamable HTTP host.

When the Python host validates JWTs against a remote issuer, the security
package retrieves OIDC metadata and JWKS through a reusable synchronous HTTPX
client. The host closes its internally owned client at shutdown. Install the
security package's `oidc-http` extra for this network-backed validation; local
or static-key authentication does not need it. See the
[Python security guide](../python/security.md) for sharing an injected client
owner across resolvers.
