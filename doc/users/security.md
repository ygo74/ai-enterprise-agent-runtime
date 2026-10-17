# Security

Authentication establishes who sent a request. Authorization decides what that
caller may see or do. Keep the two decisions distinct: a valid credential does
not automatically grant access to every agent or tool.

## Authenticate a caller

An application can require an API key or validate a bearer token issued by an
identity provider. For example, a protected request can carry a bearer token:

```http
POST /v1/responses
Authorization: Bearer <access-token>
Content-Type: application/json

{"model":"support-agent","input":"Show my open requests."}
```

The host validates the credential and passes verified identity information to
the application. It should not trust identity fields supplied in the request
body. Keep secrets outside source control and use transport encryption when
credentials cross a network.

## Authorize the operation

The application decides whether an authenticated caller can invoke an agent,
read a resource, or perform a tool operation. Apply the decision at the point
where the protected operation is selected or executed. Discovery visibility
should follow the same policy as invocation when agent existence is sensitive.

MCP servers also need their own authentication and authorization; a client-side
allow-list does not protect a remotely reachable server. See the [MCP server
hosting guide](mcp-server-hosting.md).

For Python authentication, identity context, authorization policies, and JWT
validation, see [Python security](../python/security.md). Runnable Python
examples cover [JWT](../../samples/python/python-fastapi-quickstart/03-jwt-authentication/README.md)
and [OIDC with Keycloak](../../samples/python/python-fastapi-quickstart/04-jwt-oidc-keycloak/README.md).
