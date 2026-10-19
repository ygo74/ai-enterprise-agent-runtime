# Authentication and authorization

## Responsibility boundaries

Authentication establishes which caller presented a request. Agent access
policies decide whether that caller may invoke or discover a registered agent.
Authorization for business operations remains with the application handler and
domain code. The runtime does not turn roles, groups, or token claims into
application permissions automatically.

The Python security distribution owns the common authentication contracts. The
agents and MCP server distributions use them at their respective HTTP
boundaries. .NET and Java provide authentication primitives, but do not include
the Python hosting integrations.

## Authentication policy and chain

`AuthenticationPolicy` makes the host's posture explicit:

- `anonymous()` deliberately accepts requests without a credential;
- `api_key(resolver)` validates a key through an application-supplied user
  resolver;
- `jwt(validation)` validates bearer tokens against configured signing keys and
  claims;
- `of(...)` accepts one or more application-defined `Authenticator`
  implementations.

An omitted credential is accepted only when the policy does not require
authentication. A credential claimed by a configured authenticator is still
validated when authentication is optional; malformed or invalid credentials are
rejected rather than treated as anonymous. In a chain, the first authenticator
that claims the request wins, so order defines precedence.

The API-key resolver owns key lookup, storage, rotation, and revocation. JWT
validation configuration owns accepted algorithms, issuer, audience, required
claims, clock leeway, and the key resolver. The built-in JWT implementation
supports an explicit JWKS URL or lazy OpenID discovery of the JWKS URL.

Successful authentication produces an `AuthenticatedUserContext` containing
the authentication type, normalized identity, roles, groups, scopes, selected
claims, and optional tenant ID. Its dictionary projection omits bearer
credentials. JWT authentication may retain the verified access token in a
redacted internal field for delegated exchange; the FastAPI runtime carries it
in the request-scoped context rather than handler metadata. The agent runtime
may project the credential-free identity into an immutable `AgentPrincipal`
for conversation and audit identity. A missing authenticated subject is an
error; client-supplied request fields do not establish the principal.

## Remote OIDC discovery and JWKS retrieval

JWT validation with remote keys uses the security package's managed synchronous
HTTPX lifecycle. When an issuer is configured without an explicit JWKS URL,
OpenID discovery is fetched lazily and its advertised JWKS URL is cached. The
JWKS resolver caches usable signing keys for 300 seconds by default and refreshes
on expiry or once when a requested key identifier is not cached. An explicit
JWKS URL bypasses discovery.

Discovery and JWKS reads use a lazily created HTTPX client with TLS verification
enabled. An application can inject and share one SyncHttpClientOwner across
discovery and key resolution to reuse a synchronous pool. When the
authenticator creates its owner, closing the authenticator closes that owner
and its client. An application-supplied owner or client remains application-
owned and must be closed by the application. The base security package does not
require HTTPX or Tenacity: remote lookup support is provided by the optional
security oidc-http extra. Static or symmetric-key JWT validation does not need
that extra.

Each safe lookup has a finite retry count and elapsed-time retry budget.
Discovery uses its configured timeout, five seconds by default; JWKS retrieval
uses a five-second retry budget. Each synchronous HTTPX request receives the
remaining budget as its phase timeout, and the retry loop stops starting new
attempts after the budget elapses. This is not a strict total wall-clock cap:
HTTPX phase timeouts do not cancel a blocking synchronous request that spans
multiple phases, and a successful in-flight request can return after the
budget. Defaults allow three attempts with randomized exponential backoff
from 0.1 to 0.5 seconds. Only classified transient transport failures
and HTTP 500, 502, 503, or 504 responses are retried; client errors, malformed
documents, and token validation failures are not. By default, the in-process
breaker registry is shared by callers for the same issuer or explicit JWKS
service identity. Five consecutive availability failures open it for 30 seconds
by default; it then
permits one probe, closes after success, and reopens after failure. An open
circuit fails authentication closed. Diagnostics do not include credentials
or provider response bodies.

These policies cover the runtime's remote JWT key lookups. They do not take
ownership of application-created HTTP clients or clients used internally by
agent frameworks and model-provider SDKs.

## Agent access and discovery

In Python, an application may provide an `AgentAccessPolicy` alongside an agent
descriptor registry. The policy can gate both invocation and model discovery.
The built-in role policy requires a configured role; a custom policy can use
descriptor attributes or other application rules. A denial blocks invocation
and hides the agent from listings and direct model retrieval. A policy error
fails closed.

Discovery has a separate `require_authentication` setting from invocation. This
lets a host publish listings publicly while protecting invocation, or protect
both. The hosting factory validates that protected discovery has at least one
authenticator configured.

## Handler authorization

After authentication, the application receives caller context with the
normalized exchange input. It decides whether the caller may perform the
requested business action, using its own rules and data. Python handlers can
return a structured authorization error or raise the runtime's
`AuthorizationError`; the FastAPI adapter maps authorization failures to HTTP
403. This decision is separate from agent-level access and from the lower-level
`Permission` checks described in [application security
primitives](application-security-primitives.md).

## Header and credential boundaries

FastAPI does not copy request headers into handler metadata by default. An
application can explicitly allowlist headers for forwarding; credential-bearing
headers are excluded. Credentials should not be placed in exchange metadata,
application logs, or prompts. MCP server hosting attaches the normalized
authentication context to the request scope, but tools still receive and
authorize the subject they act for according to application policy.

## Language limits

The authentication types and API-key/JWT building blocks exist in Python,
.NET, and Java. Python additionally provides explicit authentication policy
composition and integrated FastAPI and MCP server request handling. See
[language support](../compatibility/language-status.md) for the current package
boundaries.
