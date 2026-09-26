# Security and authentication

The `ygo74-agent-runtime-security` distribution provides shared authentication
and security domain types. The agents and MCP server distributions depend on it
so their hosts can use the same caller context model.

## Authentication

For FastAPI agent endpoints, `add_ai_endpoints` can validate JWT bearer tokens,
resolve API keys through an application-supplied user resolver, or accept a
custom `Authenticator`. Set `require_bearer_token=True` when requests must carry
a recognized credential. The
[authentication policy](../../packages/python/security/ygo74/agent_runtime/domains/auth/authentication_policy.py),
[JWT configuration](../../packages/python/security/ygo74/agent_runtime/domains/auth/jwt_authenticator.py),
and [authorization example](../examples/python-langchain-fastapi/authorization.md)
describe the extension points.

The runtime authenticates callers and supplies an `auth_context`; application
code owns domain-specific authorization. An `AgentAccessPolicy` can apply one
rule to agent invocation and discovery visibility. See the
[JWT example](../examples/python-langchain-fastapi/02-jwt-authentication/README.md)
and [OIDC/Keycloak example](../examples/python-langchain-fastapi/03-jwt-oidc-keycloak/README.md)
for runnable configurations.

For an MCP server, choose an explicit `AuthenticationPolicy`: `none`, `api_key`,
`jwt`, or a custom authenticator. HTTP hosting refuses to start when the mode
was not configured. JWT resource hosting also requires a resource URL and
asymmetric signing algorithms. See [MCP server hosting](../mcp-server-hosting.md).

## Security domain building blocks

The `security` domain provides typed permissions and a registry, user context,
operation type and risk classification, posture floor, audit records, and
untrusted-content fencing. These are application building blocks: the library
does not decide which domain permissions a user receives or whether a user may
perform a business action. Start at the
[security package](../../packages/python/security/ygo74/agent_runtime/domains/security/)
and the [human-in-the-loop example](../examples/python-langchain-fastapi/04-human-in-the-loop/README.md)
for an example of classifying an operation and requesting confirmation. There
is no dedicated runnable example yet for the permission registry, audit trail,
security floor, or untrusted-content fence in isolation.

## Header forwarding

The agent endpoint adapter can pass selected request headers into handler
metadata with `forwarded_headers`; credential headers used by configured
authenticators are excluded. The configured conversation header is separately
promoted to `metadata.conversation_id`. Forward only headers the handler needs.
