# Hosting an MCP server

An MCP server reached over stdio is defended by the operating system: it is a child
process, its credential never leaves it, and the caller talks to it through a pipe
nobody else can open.

Over HTTP that argument is gone. The pipe becomes a port, every process that can
reach the port can reach the tools, and **nothing else about the server changes** —
same tools, same payloads, same code. That is exactly why the difference is easy to
miss, and why this package exists.

```python
from mcp.server.fastmcp import FastMCP

from ygo74.agent_runtime.domains.auth.authentication_policy import AuthenticationPolicy
from ygo74.agent_runtime.domains.mcpserver.host import McpServerHost
from ygo74.agent_runtime.domains.mcpserver.http_binding import McpHttpBinding

server = FastMCP("my-server", host="0.0.0.0", port=9100)

@server.tool(description="Return a greeting.")
def greet(name: str) -> str:
    return f"hello {name}"

McpServerHost(
    policy=AuthenticationPolicy.api_key(my_resolver, header_name="authorization", scheme="Bearer"),
    binding=McpHttpBinding(host="0.0.0.0", port=9100, public_host="my-server:9100"),
).serve(server)
```

Install with `pip install "ygo74-agent-runtime-mcp[http]"`.

---

## The bind address goes in the constructor

`FastMCP(name, host=..., port=...)` — not `server.settings.host = ...` afterwards.

This is the single most expensive mistake this package can save you from. FastMCP
derives a DNS-rebinding allow-list from the bind address **at construction** and
never revisits it. Build the server with the default address and every request
carrying a service name in `Host` is answered `421 Misdirected Request` — after
authentication, before any tool, with the health probe still green because the probe
never reaches the handler that enforces the rule.

`McpServerHost.serve` reads that allow-list at start-up and refuses to serve when it
does not contain the address callers use:

```
McpServerUnreachableError: this server would answer 421 to a request for host
'my-server:9100': its DNS-rebinding allow-list is ['127.0.0.1:*', 'localhost:*'],
derived from a bind address that does not include it.
```

---

## The three modes

There is no default. Serving everyone is a decision, and a decision has to be
written down.

### None — anonymous

```python
AuthenticationPolicy.anonymous()
```

Legitimate for a server over public, read-only data. **It is never what you get by
forgetting to configure anything** — that is a refusal to start. The two states must
stay distinguishable, because one is a choice somebody can be asked about and the
other is an accident nobody notices.

### API key — a caller you recognise

```python
AuthenticationPolicy.api_key(resolver, header_name="authorization", scheme="Bearer")
```

You write the resolver. It maps a key to whatever user information your deployment
has — a constant for a shared deployment secret, a database lookup for many callers:

```python
class DatabaseKeyResolver:
    def resolve_user(self, api_key: str) -> ResolvedUser | None:
        row = self._users.find_by_key_hash(sha256(api_key))
        return None if row is None else ResolvedUser(user_id=row.id, roles=row.roles)
```

Returning `None` refuses the caller. The raw key never reaches the handler: only what
the resolver returned does.

`scheme` covers the deployments that carry their key in an `Authorization` header. A
header not carrying that scheme is not claimed at all, so this authenticator cannot
swallow a credential meant for another one.

### JWT — an identity provider

```python
AuthenticationPolicy.jwt(JwtValidationConfig(issuer="https://idp/realms/agents",
                                             audience="my-server",
                                             allowed_algorithms=("RS256",)))
```

The server then behaves as an **OAuth 2.1 resource server**: it publishes RFC 9728
metadata at `/.well-known/oauth-protected-resource` and answers a credential-less
call with `WWW-Authenticate: Bearer resource_metadata="…"`. That is what lets VS
Code, Claude Desktop or any MCP client discover the issuer from the URL alone,
instead of somebody being told which realm to use out of band.

It needs `resource_url` — a resource server that cannot name itself cannot be
discovered, so the host refuses to start without one.

Use asymmetric algorithms only. `HS256` would mean this server holds the key that
signs tokens, which turns a resource server into an issuer by accident.

---

## Adding a scheme of your own

Basic, Kerberos, mutual TLS — whatever your deployment actually has. Implement
`Authenticator` and pass it in. **No change to this library is required**, and its
test suite proves that by running a Basic authenticator written entirely outside it.

```python
class KerberosAuthenticator:
    @property
    def auth_type(self) -> str:
        return "kerberos"

    @property
    def header_name(self) -> str:
        return "authorization"

    def can_authenticate(self, headers) -> bool:
        return headers.get("authorization", "").lower().startswith("negotiate ")

    def missing_credential_error(self) -> AuthenticationError:
        return AuthenticationError(code="negotiate_missing", message="Missing Negotiate token")

    def authenticate(self, headers) -> AuthenticatedUserContext:
        principal = self._gssapi.accept(headers["authorization"].split(None, 1)[1])
        return AuthenticatedUserContext(auth_type=self.auth_type,
                                        identity=ResolvedUser(user_id=principal).to_identity())

McpServerHost(policy=AuthenticationPolicy.of(KerberosAuthenticator()), binding=binding)
```

Order is precedence: the first authenticator claiming a request wins. If yours
raises, the caller is refused with 401 rather than handed a traceback — the
extension point is arbitrary code on the request path, and a caller who can make a
credential-holding process raise has a log-flood vector.

---

## Reading it from the environment

`McpServerAuthentication.from_env` maps a variable prefix onto the three modes, so
two servers in one deployment share one implementation and differ only by prefix:

```python
authentication = McpServerAuthentication.from_env("MAIL_MCP_", caller_id="mail-agent")
```

| Variable | Meaning |
|---|---|
| `<prefix>AUTH_MODE` | `none`, `api_key` or `jwt` |
| `<prefix>HTTP_TOKEN` | The shared secret, for `api_key` |
| `<prefix>OIDC_ISSUER` | The issuer to validate against, for `jwt` |
| `<prefix>OIDC_AUDIENCE` | The audience a token must carry |
| `<prefix>RESOURCE_URL` | What the server calls itself, required for `jwt` |

The mode may be inferred from an unambiguous signal — a configured token means a
token is checked — so a deployment that already set one does not have to say it
twice. **Silence is never inferred as anonymity.**

---

## What the host does not do

**It does not make the authenticated caller authoritative over what a tool operates
on.** The identity is attached to the request scope under `AUTH_CONTEXT_KEY` and is
available to a tool, but tools still take the subject they act for as an argument.
Closing that gap is separate work; this host is shaped so it will not have to be
undone first.

**It does not authorise.** Authentication answers "who is calling". What that caller
may do is a question for the permission model in
`ygo74-agent-runtime-security`, and for the server itself — which remains the
authority on who may read what.

---

## What is open, and why

| Path | Authenticated | Why |
|---|---|---|
| `/healthz` | No | An orchestrator must be able to ask whether a process is alive without being handed a credential. It returns `{"status": "ok"}` and nothing else. |
| `/.well-known/oauth-protected-resource` | No | A client cannot present a token before learning where to get one. Answers 404 when the server implements no OAuth flow — an honest "I am not a resource server" rather than a misleading 401. |
| Everything else | Yes | Including the tools. |

Both are matched exactly, not by prefix: `/healthzextra` is guarded.
