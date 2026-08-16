# Authorization Extension (Python)

The runtime authenticates the caller and hands you a normalized `auth_context`.
It never makes an authorization decision: that stays in your code.

## What you receive

`payload["auth_context"]` (or `None` when no credential was supplied):

```python
{
    "authType": "jwt",              # or "api_key"
    "userId": "96af2242-...",
    "identity": {
        "subject": "96af2242-...",
        "userId": "96af2242-...",
        "username": "admin",
        "name": "Yannick GOBERT",
        "givenName": "Yannick",
        "familyName": "GOBERT",
        "email": "admin@example.com",
        "emailVerified": True,
    },
    "roles": ["admin"],             # projected from roles_claim_path
    "groups": [],                   # projected from groups_claim_path
    "scopes": ["openid", "profile", "email"],
    "claims": {...},                # raw projected claims (incl. realm_access / resource_access)
}
```

`roles` and `groups` are projected from a configurable dot-separated claim path,
so the same runtime works with any OIDC provider:

```python
JwtValidationConfig(
    ...,
    roles_claim_path="realm_access.roles",                 # Keycloak realm roles
    # roles_claim_path="resource_access.myclient.roles",   # Keycloak client roles
    groups_claim_path="groups",
)
```

## Denying a request

### Option 1 - raise `AuthorizationError` (recommended)

```python
from ygo74.agent_runtime import AuthorizationError

async def entrypoint(payload: dict) -> dict:
    auth = payload["auth_context"] or {}

    if "admin" not in auth.get("roles", []):
        raise AuthorizationError(
            code="role_required",
            message="admin role is required",
            details={"required_role": "admin"},
        )

    return await run_protected_business_logic(payload)
```

The runtime short-circuits handler execution and returns **HTTP 403** with a
structured envelope:

```json
{
  "detail": {
    "request_id": "req-...",
    "status": "error",
    "endpoint_type": "openai.responses",
    "error": {
      "code": "role_required",
      "category": "authorization",
      "message": "admin role is required",
      "details": {"required_role": "admin"}
    }
  }
}
```

### Option 2 - return an error envelope

```python
from ygo74.agent_runtime.domains.auth.auth_errors import auth_error

return {
    "request_id": payload["request_id"],
    "status": "error",
    "error": auth_error("forbidden", "access denied", "authorization"),
}
```

### Option 3 - raise a FastAPI `HTTPException`

`HTTPException` raised from your entrypoint is passed through untouched, so you
keep full control over the status code and body.

## Error category to HTTP status mapping

Any error envelope you return is mapped to a status code by `category`:

|`category`|HTTP status|
|---|---|
|`authorization`|403|
|`authentication`|401|
|`validation`|400|
|`routing`|404|
|anything else|500|

## Streaming

Evaluate authorization **before** returning the async generator. Once the first
SSE frame is flushed the status code is already committed, so a denial raised
mid-stream can only be surfaced as a terminal SSE error frame.

```python
def entrypoint(payload: dict):
    auth = payload["auth_context"] or {}
    if "admin" not in auth.get("roles", []):
        raise AuthorizationError()      # evaluated eagerly -> real HTTP 403

    if payload.get("stream"):
        return _stream(payload)         # generator returned only once allowed

    return _once(payload)
```

## API key mode

Pass a resolution hook; the runtime calls it and exposes only the resolved
identity. The raw key is never copied into `auth_context`.

The hook is a class implementing the `ApiKeyUserResolver` protocol and must
return a `ResolvedUser` (or `None` for an unknown key).

```python
from ygo74.agent_runtime import ApiKeyUserResolver, ResolvedUser, add_ai_endpoints


class StoreApiKeyResolver(ApiKeyUserResolver):
    def resolve_user(self, api_key: str) -> ResolvedUser | None:
        record = lookup_in_your_store(api_key)
        if record is None:
            return None                 # -> HTTP 401 api_key_invalid
        return ResolvedUser(
            user_id=record.user_id,
            name=record.display_name,
            email=record.email,
            roles=record.roles,
            tenant_id=record.tenant_id,
        )


add_ai_endpoints(
    app,
    entrypoint,
    default_route_key="my-agent",
    api_key_resolver=StoreApiKeyResolver(),
)
```

The hook is only consulted for the `x-api-key` header when no `Authorization`
header was already authenticated, and the returned `ResolvedUser` must carry a
non-empty `user_id` (otherwise `user_context_malformed` is raised).

## Custom authentication schemes

Authentication is class-based. `JwtAuthenticator` and `ApiKeyAuthenticator`
both implement the `Authenticator` protocol, and `RequestAuthenticator` picks
the right one based on the incoming headers.

```python
class Authenticator(Protocol):
    @property
    def auth_type(self) -> str: ...

    def can_authenticate(self, headers: Mapping[str, str] | None) -> bool: ...

    def authenticate(self, headers: Mapping[str, str] | None) -> AuthenticatedUserContext: ...

    def missing_credential_error(self) -> AuthenticationError: ...
```

To support another scheme (mTLS header, HMAC signature, opaque token
introspection...), implement the protocol and pass the chain explicitly:

```python
add_ai_endpoints(
    app,
    entrypoint,
    default_route_key="my-agent",
    authenticators=[JwtAuthenticator(jwt_config), MyCustomAuthenticator()],
)
```

The first authenticator whose `can_authenticate` returns `True` handles the
request. When no authenticator matches and `require_bearer_token=True`, the
first one in the chain produces the missing-credential error.
