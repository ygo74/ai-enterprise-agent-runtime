# Agent invocation context

## Purpose and boundary

The Python agent runtime carries authenticated caller identity and turn
correlation through endpoint handlers, conversation engines, asynchronous
streams, and MCP requests. AgentInvocationContext is the neutral runtime value
for that information; it does not depend on MCP or a particular agent framework.
It is not part of the provider wire format or the standard exchange payload, and
it does not make application authorization decisions.

## Context values

AgentInvocationContext contains:

- the authenticated AgentPrincipal, when the request was authenticated;
- the normalized request ID and the selected conversation or session ID;
- the verified inbound AccessToken when an authenticator supplies one, for
  possible delegated authentication such as OAuth on-behalf-of.

The principal and access token come from the authentication boundary. Request
and conversation identifiers are correlation and routing values; they must not
be treated as authorization claims. The verified token remains an internal
credential: it is omitted from the context's repr and is not copied into
handler metadata or runtime logs.

## Invocation and stream lifetime

After authentication and request normalization, the Python FastAPI adapter
creates the context and binds it through AgentInvocationContextScope while it
calls or, for an asynchronous non-streaming handler, awaits the application
entrypoint. The scope uses execution-local context and restores its previous
value when the operation exits, including when the entrypoint raises or is
cancelled. Agent code reads the current value through
AgentInvocationContextScope.current(); the context is not an extra
endpoint-handler argument.

An asynchronous stream can execute after the FastAPI handler has returned.
The adapter therefore rebinds the context while pulling each stream item and
while closing the stream, then restores the consumer's context before yielding
the item. The context is not held across the consumer's yield. The conversation
entrypoint enriches the current context from its typed ConversationTurn and
binds the resulting turn identity and correlation around each normal response,
stream pull, and stream cleanup.

## MCP consumption

Binding an invocation context does not create an MCP transport or session.
McpConnection reads it when application code first requests an MCP session.
For OBO, a verified principal and subject token are required, and the MCP
session is partitioned by principal. The incoming subject token is exchanged
for the configured downstream audience; only the resulting downstream token
is sent to the MCP resource.

For HTTP transport, the MCP write adapter records the current context against
the outgoing JSON-RPC request ID. The HTTP request hook consumes that matching
context to resolve configured user ID, email, display-name, role, request,
conversation, or session header tokens. This correlation remains per request even when principal-specific
sessions share one server's HTTPX pool. Session-level requests in OBO mode use
the session's principal context. See the [MCP client and server
specification](../mcp/client-and-server.md) for pool ownership and resilience.

## Compatibility and sources

The context and scope APIs are Python-only in this repository. Other language
packages do not claim equivalent request-scoped context propagation.

The implementation is in
[invocation_context.py](../../packages/python/agents/ygo74/agent_runtime/domains/contracts/invocation_context.py),
[fastapi_endpoints.py](../../packages/python/agents/ygo74/agent_runtime/domains/endpoints/fastapi_endpoints.py),
[conversation_entrypoint.py](../../packages/python/agents/ygo74/agent_runtime/domains/endpoints/conversation_entrypoint.py),
and [request_context.py](../../packages/python/agents/ygo74/agent_runtime/domains/mcp/request_context.py).
Existing integration coverage is in
[test_fastapi_jwt_auth.py](../../tests/integration/python/test_fastapi_jwt_auth.py),
[test_mcp_request_headers.py](../../tests/integration/python/test_mcp_request_headers.py),
and [test_mcp_shared_http_client.py](../../tests/integration/python/test_mcp_shared_http_client.py).
