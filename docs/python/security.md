# Security and authentication

The Python runtime separates request authentication from authorization decisions
and from application security controls. The
[`ygo74-agent-runtime-security` distribution](../../packages/python/security/pyproject.toml)
provides the shared authentication types and security-domain building blocks;
the agents and MCP server distributions use those types at their respective
HTTP boundaries.

This guide covers how to configure those existing pieces and where application
code must supply policy. It does not define a universal role model for every
application.

## Choose the layer for each decision

| Layer | Question | Runtime or application responsibility |
|---|---|---|
| Authentication | Who sent this request? | A configured authenticator validates a credential and creates a normalized caller context. |
| Agent access | May this caller see or invoke this declared agent? | The application provides an `AgentAccessPolicy`; the FastAPI adapter can reuse it for invocation and discovery. |
| Handler authorization | May this caller perform this operation with this request's input? | The handler checks application rules and returns or raises a structured denial. |
| Domain permissions | May this application operation be attempted for this user? | The application maps its identity and business rules to `Permission` values and checks them. The runtime does not do this mapping. |

Authentication alone does not grant business permissions. Treat data from the
identity provider as input to your application policy, not as an automatic
authorization decision.

## FastAPI request authentication

[`add_ai_endpoints`](../../packages/python/agents/ygo74/agent_runtime/domains/endpoints/fastapi_endpoints.py)
accepts these authentication arguments:

- `jwt_validation`: a `JwtValidationConfig` used to validate bearer JWTs.
- `api_key_resolver`: an application object implementing `resolve_user(api_key)`.
- `authenticators`: an explicit ordered sequence of custom or built-in
  `Authenticator` implementations. When supplied, it replaces the chain that
  would otherwise be assembled from `jwt_validation` and `api_key_resolver`.
- `require_bearer_token`: despite its name, this makes a credential from the
  configured authenticator chain mandatory. Leave it `False` to allow requests
  without credentials.

With the defaults, no credentials are required and an anonymous request reaches
the handler with `auth_context=None`. If a recognized credential is present, it
is still validated; an invalid credential is rejected with HTTP 401 rather than
being treated as anonymous. Setting `require_bearer_token=True` also rejects
requests with no matching credential. Configure at least one authenticator when
you require authentication.

For example, this OIDC configuration validates RS256 tokens against the
identity provider's published keys and requires a token to name the configured
issuer and audience:

```python
import os

from ygo74.agent_runtime.domains.auth.jwt_authenticator import (
    DiscoveredJwksKeyResolver,
    JwtValidationConfig,
)
from ygo74.agent_runtime.domains.endpoints.fastapi_endpoints import add_ai_endpoints

issuer = os.environ["OIDC_ISSUER"]
jwt_validation = JwtValidationConfig(
    allowed_algorithms=("RS256",),
    required_claims=("sub", "exp", "iss", "aud"),
    issuer=issuer,
    audience=os.environ["OIDC_AUDIENCE"],
    key_resolver=DiscoveredJwksKeyResolver(issuer=issuer),
    roles_claim_path="realm_access.roles",
    groups_claim_path="groups",
)

add_ai_endpoints(
    app,
    agent_entrypoint,
    default_route_key="support-agent",
    jwt_validation=jwt_validation,
    require_bearer_token=True,
)
```

[`DiscoveredJwksKeyResolver`, `JwksKeyResolver`, and `JwtValidationConfig`](../../packages/python/security/ygo74/agent_runtime/domains/auth/jwt_authenticator.py)
define the JWT key and validation options. `DiscoveredJwksKeyResolver` lazily
reads the issuer's OpenID configuration to find its JWKS URL when the first
token is validated. If the operator already knows the JWKS URL, use
`JwksKeyResolver(jwks_url=...)` instead. A JWT configuration without a
`key_resolver` rejects tokens because it has no key with which to verify
signatures. `JwtValidationConfig` also supports
`leeway_seconds` for clock skew; its default required claim is `sub`. Set
`required_claims`, `issuer`, `audience`, and `allowed_algorithms` to match the
token contract you intend to accept. The runnable
[JWT example](../examples/python-langchain-fastapi/02-jwt-authentication/README.md)
uses a local HS256 key; the
[OIDC/Keycloak example](../examples/python-langchain-fastapi/03-jwt-oidc-keycloak/README.md)
shows asymmetric JWKS validation and role projection.

### API keys

An API key resolver maps a presented key to an application-owned `ResolvedUser`.
Returning `None` rejects an unknown key; a successful result must have a
non-empty `user_id`. The handler receives the resolved identity and attributes;
the raw key is not copied into `auth_context`.

```python
from ygo74.agent_runtime.domains.auth.auth_context import ResolvedUser


class ApiKeyUsers:
    def resolve_user(self, api_key: str) -> ResolvedUser | None:
        record = lookup_key_by_hash(api_key)
        if record is None:
            return None
        return ResolvedUser(
            user_id=record.user_id,
            roles=record.roles,
            groups=record.groups,
            tenant_id=record.tenant_id,
        )


add_ai_endpoints(
    app,
    agent_entrypoint,
    default_route_key="support-agent",
    api_key_resolver=ApiKeyUsers(),
    require_bearer_token=True,
)
```

[`ApiKeyAuthenticator`](../../packages/python/security/ygo74/agent_runtime/domains/auth/apikey_authenticator.py)
reads `x-api-key` by default. It can also read a named
scheme from a selected header. Keep key storage, rotation, revocation, and the
resolver's lookup behavior in the application. See the
[authorization walkthrough](../examples/python-langchain-fastapi/authorization.md)
for the complete API-key extension point.

### Combining or extending authenticators

[`RequestAuthenticator`](../../packages/python/security/ygo74/agent_runtime/domains/auth/authenticator.py)
uses the order of its chain as precedence. If `authenticators` is omitted, the
runtime assembles a chain with JWT first and
API key second when both are configured. The first authenticator that claims a
request handles it. When JWT is configured, a request with an `Authorization`
header is claimed by the JWT authenticator; if it is malformed or is not a
valid bearer token, the request fails with 401 instead of falling back to an
`x-api-key` value. This prevents an invalid higher-priority credential from
being silently ignored.

For another scheme, implement the [`Authenticator` protocol](../../packages/python/security/ygo74/agent_runtime/domains/auth/authenticator.py)
(`auth_type`, `can_authenticate`, `authenticate`, and
`missing_credential_error`) and pass an ordered list through `authenticators`.
Each authenticator should return an `AuthenticatedUserContext` after validating
its credential. Use a custom chain when you need explicit precedence or a scheme
such as a signed request or an application-specific token.

## The handler's `auth_context`

After authentication, the HTTP adapter passes `auth_context` alongside the
standard exchange payload. For an authenticated caller its normalized shape is
roughly:

```json
{
  "authType": "jwt",
  "userId": "subject-123",
  "identity": {
    "userId": "subject-123",
    "subject": "subject-123",
    "username": "alex",
    "name": "Alex Example",
    "givenName": null,
    "familyName": null,
    "email": "alex@example.com",
    "emailVerified": true
  },
  "roles": ["support"],
  "groups": ["operations"],
  "scopes": ["openid", "profile"],
  "claims": {"iss": "https://issuer.example.com", "exp": 2000000000},
  "tenantId": "tenant-7"
}
```

See the [`AuthenticatedUserContext` and `ResolvedUser` definitions](../../packages/python/security/ygo74/agent_runtime/domains/auth/auth_context.py)
for the exact projection. Fields without values may be `null`, empty, or absent
according to the authenticator. JWT identity is projected from standard claims such as `sub`,
`preferred_username`, `name`, and `email`. Roles and groups are projected from
the configured dot-separated `roles_claim_path` and `groups_claim_path`;
scopes are read from the token's `scope` claim. The JWT `claims` member contains
a selected set of claims, including common time and identity fields and nested
`realm_access` / `resource_access` values when present. It is not an unrestricted
copy of every token claim. API-key fields come from the resolver's
`ResolvedUser`.

An application can use this context to establish its own principal, but should
pass only the minimum identity information its handler needs. In particular,
do not log access tokens or put credentials in metadata or prompts.

## Agent access and handler authorization

### One `AgentAccessPolicy` for discovery and invocation

When descriptors are registered, an
[`AgentAccessPolicy`](../../packages/python/agents/ygo74/agent_runtime/domains/discovery/agent_access_policy.py)
can apply the same agent-level rule before invocation and while serving model
discovery. When given a non-empty `required_role`, the built-in
`RoleRequiredAccessPolicy` requires that role for every registered agent; its
empty default allows any caller. Implement the protocol for rules that depend
on descriptor attributes.

```python
from ygo74.agent_runtime.domains.discovery.agent_access_policy import (
    RoleRequiredAccessPolicy,
)

add_ai_endpoints(
    app,
    agent_entrypoint,
    default_route_key="support-agent",
    descriptor_registry=descriptor_registry,
    discovery=discovery_configuration,
    authorization_policy=RoleRequiredAccessPolicy(required_role="support"),
    jwt_validation=jwt_validation,
    require_bearer_token=True,
)
```

The policy is application-supplied; the runtime does not invent a role rule.
An invocation denied by this policy returns HTTP 403. When discovery is
enabled, unauthorized agents are omitted from `GET /v1/models`, and direct
retrieval returns 404, like an unknown or hidden agent, so that its existence
is not disclosed. The discovery endpoints use the same configured authenticator
chain. Set `DiscoveryConfiguration(require_authentication=True)` if discovery
itself must reject unauthenticated requests; access filtering can also operate
with an anonymous context when authentication is optional. If the policy raises,
the adapter fails closed and treats the agent as denied.

### Request-specific checks in the handler

Use handler-owned authorization for decisions depending on request content or
business data. Raise `AuthorizationError` for a structured HTTP 403, or return
an error envelope with category `authorization`. The handler can also raise a
FastAPI `HTTPException` when it needs a different transport response.

```python
from ygo74.agent_runtime.domains.auth.auth_errors import AuthorizationError


async def agent_entrypoint(payload: dict) -> dict:
    auth = payload.get("auth_context") or {}
    if not may_read_ticket(auth, payload["input"]):
        raise AuthorizationError(
            code="ticket_access_denied",
            message="The caller may not read this ticket",
        )
    return await read_ticket(payload["input"])
```

Authentication failures map to HTTP 401; authorization denials map to HTTP 403.
The adapter preserves structured error details. A handler may instead return an
error envelope: categories `authentication` and `authorization` map to 401 and
403, `validation` to 400, `routing` to 404, and other categories to 500.

For streaming handlers, check authorization before returning an iterator or
async generator. Once the server has sent the first SSE frame, the HTTP status
is committed; a later denial can only be represented as a stream error frame.
The shared `AgentAccessPolicy` check is performed before dispatch, while
request-body-dependent checks belong at the beginning of the handler.

## Forwarding request headers safely

[`RequestHeaderForwarder`](../../packages/python/agents/ygo74/agent_runtime/domains/endpoints/header_forwarding.py)
implements the header allowlist. By default, the adapter forwards only selected
correlation headers. Configure
`forwarded_headers` as an allowlist for any additional header your handler
requires. Those values appear in `payload["metadata"]["headers"]` in lowercase.
The configured conversation header is also promoted to
`payload["metadata"]["conversation_id"]`; its default name is
`x-conversation-id`.

Credential-bearing headers such as `authorization`, `x-api-key`, and cookies
cannot be forwarded. The adapter also excludes header names exposed by a
configured authenticator through `header_name` or `HEADER_NAME`; custom
authenticators should expose that property for their credential header. Trying
to include one causes endpoint registration to fail. The adapter replaces the
transport-derived `metadata.headers` value rather than merging it with a value
from the request body. This keeps a caller from forging transport headers in
JSON metadata. An explicit `conversation_id` in body metadata takes precedence
over the conversation header.

## MCP server authentication

MCP hosting uses a separate, explicit
[`AuthenticationPolicy`](../../packages/python/security/ygo74/agent_runtime/domains/auth/authentication_policy.py)
rather than the
FastAPI arguments above:

- `AuthenticationPolicy.anonymous()` explicitly serves requests without a
  credential.
- `AuthenticationPolicy.api_key(resolver, ...)` validates an API key through a
  host-supplied resolver.
- `AuthenticationPolicy.jwt(JwtValidationConfig(...))` validates bearer JWTs.
- `AuthenticationPolicy.of(authenticator, ...)` installs one or more custom
  authenticators in precedence order.

An empty or unknown policy is a configuration error; the HTTP host does not
silently interpret missing configuration as anonymous access. JWT hosting also
needs a public resource URL and an issuer. The host takes its signing algorithm
allowlist from `JwtValidationConfig`, so configure an asymmetric algorithm
allowlist for this resource-server use. MCP caller authentication does not
itself authorize access to the resources used by a tool. See the
[MCP server hosting guide](../mcp-server-hosting.md) for protected-resource
metadata, HTTP transport setup, health endpoints, and complete configurations.

## Application security building blocks

The security domain provides typed pieces for composing application policy. It
does not install those pieces into every handler or automatically enforce them
at the HTTP boundary.

### Permissions and user context

[`Permission` and `PermissionRegistry`](../../packages/python/security/ygo74/agent_runtime/domains/security/permissions.py)
provide namespaced capabilities such as
`mail:read` or `mail:send`. Each application domain declares its own values and
composes a `PermissionRegistry` explicitly. The registry resolves configured
strings and raises `UnknownPermissionError` for undeclared values, which helps
catch misspelled permission configuration.

[`UserContext`](../../packages/python/security/ygo74/agent_runtime/domains/security/user_context.py)
is a credential-free application principal: it contains a
`user_id`, `session_id`, and a set of permissions. Its `require_permission`
method raises `PermissionDeniedError` if a check fails. The application decides
which permissions to put in this context; there is no automatic mapping from
JWT roles or groups to `Permission` values.

```python
from ygo74.agent_runtime.domains.security.permissions import (
    Permission,
    PermissionRegistry,
)
from ygo74.agent_runtime.domains.security.user_context import UserContext

declared = PermissionRegistry([Permission("mail", "read"), Permission("mail", "send")])
read_mail = declared.resolve("mail:read")

user = UserContext(
    user_id="subject-123",
    session_id="conversation-456",
    permissions=frozenset({read_mail}),
)
user.require_permission(read_mail)
```

Treat this as an application composition point: your code must translate the
authenticated caller into the appropriate application `UserContext` and call
the checks before protected work.

### Operation classification and security floors

[`ToolOperationDescriptor`](../../packages/python/security/ygo74/agent_runtime/domains/security/operations.py)
records a tool name, `READ` or `WRITE` operation type, `LOW` / `MEDIUM` / `HIGH`
risk, required permission, and whether
confirmation is required by default. These are application declarations, not
values chosen by the model. A
[`SecurityFloor`](../../packages/python/security/ygo74/agent_runtime/domains/security/floor.py)
can reject a descriptor whose
risk is below a code-defined minimum or whose confirmation setting weakens a
mandatory confirmation.

```python
from ygo74.agent_runtime.domains.security.floor import OperationFloor, SecurityFloor
from ygo74.agent_runtime.domains.security.operations import (
    OperationType,
    RiskLevel,
    ToolOperationDescriptor,
)

send_mail = ToolOperationDescriptor(
    tool_name="send_mail",
    operation_type=OperationType.WRITE,
    risk_level=RiskLevel.HIGH,
    required_permission=declared.resolve("mail:send"),
    confirmation_required_by_default=True,
)
floor = SecurityFloor([
    OperationFloor(
        tool_name="send_mail",
        minimum_risk=RiskLevel.HIGH,
        confirmation_always_required=True,
    )
])
floor.enforce(send_mail)
```

The application must call `enforce` when it loads or constructs its operation
configuration and must use the descriptor when it runs its own confirmation
and permission flow. The floor is not an HTTP middleware or a tool-execution
interceptor.

### Audit records

[`AuditRecord`, `AuditTrail`, and the supplied trail implementations](../../packages/python/security/ygo74/agent_runtime/domains/security/audit.py)
capture identifiers and outcomes such as the tool, operation
type, risk, user and session IDs, target ID, confirmation request ID, and error
type. It does not carry message bodies or credentials. Implement the
`AuditTrail` protocol for a durable destination, or use `LoggingAuditTrail`
(optionally delegating to another trail). `InMemoryAuditTrail` is useful for
examples and assertions, not as durable production storage. The application
decides which events to record and when.

### Untrusted content and prompt envelopes

[`UntrustedText`](../../packages/python/security/ygo74/agent_runtime/domains/security/untrusted.py)
pairs external text with an `UntrustedOrigin` and redacts its
payload from `str()` and `repr()`. Call `expose()` only where the content must be
used. [`UntrustedFence`](../../packages/python/security/ygo74/agent_runtime/domains/security/fencing.py)
creates a per-rendering delimiter and neutralizes an embedded copy of that
delimiter. [`PromptEnvelopeBuilder`](../../packages/python/security/ygo74/agent_runtime/domains/security/prompt_envelope.py)
combines trusted
instructions and a task with labelled `UntrustedSection` values, adding a
statement that retrieved material is data rather than instructions.

```python
from ygo74.agent_runtime.domains.security.prompt_envelope import (
    PromptEnvelopeBuilder,
    ReasoningRequest,
    UntrustedSection,
)
from ygo74.agent_runtime.domains.security.untrusted import UntrustedOrigin, untrusted

external_text = untrusted(
    retrieved_page_text,
    UntrustedOrigin(domain="wiki", kind="page_body"),
)
prompt = PromptEnvelopeBuilder(source="the documentation wiki").build(
    ReasoningRequest(
        instructions="Answer the user's question using the evidence provided.",
        task="Summarize the deployment steps.",
        context=(UntrustedSection(label="Deployment page", content=external_text),),
    )
)
```

Fencing helps make the trust boundary explicit in a prompt, but it cannot
prevent prompt injection, guarantee that a model will follow the boundary, or
block a tool call or other side effect. Keep deterministic permission checks,
validation, confirmation, and downstream system authorization around operations
with consequences. The
[human-in-the-loop walkthrough](../examples/python-langchain-fastapi/04-human-in-the-loop/README.md)
shows a confirmation flow spanning requests; it is an example of application
composition rather than automatic enforcement by the fence.

The primitives in this section do not currently have a standalone runnable
example covering permission registries, audit trails, security floors, or
prompt fencing individually. The
[authorization walkthrough](../examples/python-langchain-fastapi/authorization.md)
demonstrates the HTTP adapter authorization hooks, while the
[human-in-the-loop example](../examples/python-langchain-fastapi/04-human-in-the-loop/README.md)
demonstrates operation classification and confirmation in an agent flow.
