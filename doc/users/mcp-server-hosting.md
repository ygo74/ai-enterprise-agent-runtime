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

A health endpoint may be public if it reveals only service availability, such
as `{"status":"ok"}`. Do not expose tool listings, configuration, or identity
provider details through an unauthenticated health response.

## Check a protected endpoint

A client lists tools by sending a JSON-RPC request with the configured
credential:

```http
POST /mcp
Authorization: Bearer <server-credential>
Accept: application/json, text/event-stream
Content-Type: application/json

{"jsonrpc":"2.0","id":1,"method":"tools/list"}
```

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
