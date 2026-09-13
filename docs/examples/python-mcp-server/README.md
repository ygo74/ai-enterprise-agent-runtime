# An MCP server, hosted

Two tools over a small catalogue. The tools are not the point — what is, is who gets
to call them, how that is decided, and what happens when nobody decided.

## Install

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

## Run it, four ways

### Nothing configured

```powershell
python server.py
```

```
AuthenticationConfigurationError: serving over HTTP requires DEMO_MCP_AUTH_MODE:
this process holds a credential for the system behind it, and an unauthenticated
port would hand that system to anything that can reach it.
```

**This is the behaviour to notice.** A forgotten variable stops the process instead
of opening a port. Anonymity exists, but you have to ask for it.

### A shared secret

```powershell
$env:DEMO_MCP_AUTH_MODE = "api_key"
$env:DEMO_MCP_HTTP_TOKEN = "choose-a-secret"
python server.py
```

```powershell
curl.exe -s -o NUL -w "no token    -> %{http_code}`n" -X POST http://127.0.0.1:9300/mcp `
  -H "Accept: application/json, text/event-stream" -H "Content-Type: application/json" `
  -d '{\"jsonrpc\":\"2.0\",\"id\":1,\"method\":\"tools/list\"}'

curl.exe -s -o NUL -w "with token  -> %{http_code}`n" -X POST http://127.0.0.1:9300/mcp `
  -H "Authorization: Bearer choose-a-secret" `
  -H "Accept: application/json, text/event-stream" -H "Content-Type: application/json" `
  -d '{\"jsonrpc\":\"2.0\",\"id\":1,\"method\":\"tools/list\"}'

curl.exe -s -o NUL -w "healthz     -> %{http_code}`n" http://127.0.0.1:9300/healthz
curl.exe -s -o NUL -w "oauth meta  -> %{http_code}`n" http://127.0.0.1:9300/.well-known/oauth-protected-resource
```

```
no token    -> 401
with token  -> 400     <- past the guard; the MCP layer wants a session
healthz     -> 200     <- open, so an orchestrator needs no credential
oauth meta  -> 404     <- honest: this server implements no OAuth flow
```

That last line is worth a moment. Answering 401 there would tell a probing client
"there is a flow here, you just need a credential", which is not true.

### An identity provider

```powershell
$env:DEMO_MCP_AUTH_MODE = "jwt"
$env:DEMO_MCP_OIDC_ISSUER = "https://keycloak.example/realms/agents"
$env:DEMO_MCP_RESOURCE_URL = "http://127.0.0.1:9300"
python server.py
```

```powershell
curl.exe -s http://127.0.0.1:9300/.well-known/oauth-protected-resource
curl.exe -s -D - -o NUL -X POST http://127.0.0.1:9300/mcp -H "Accept: application/json, text/event-stream"
```

```json
{"resource":"http://127.0.0.1:9300",
 "authorization_servers":["https://keycloak.example/realms/agents"],
 "bearer_methods_supported":["header"]}
```

```
HTTP/1.1 401 Unauthorized
www-authenticate: Bearer resource_metadata="http://127.0.0.1:9300/.well-known/oauth-protected-resource"
```

This is what makes the server usable by VS Code or Claude Desktop from its URL
alone: the client reads the challenge, follows it to the metadata, and finds the
realm by itself. Nobody has to be told which one out of band.

### Anonymous

```powershell
$env:DEMO_MCP_AUTH_MODE = "none"
python server.py
```

Every caller is served, and the start-up log says so:

```
INFO ...host: serving MCP over HTTP on 127.0.0.1:9300 as 127.0.0.1:9300 -
     anonymous: every caller is served, no credential is checked
```

A line somebody can question in a review. That is the difference between a decision
and an accident.

## Adding a scheme

Basic, Kerberos, mutual TLS: implement `Authenticator` and pass it to
`AuthenticationPolicy.of(...)`. No change to the library, and the library's own test
suite proves it by running a Basic authenticator written entirely outside it.

See [docs/mcp-server-hosting.md](../../mcp-server-hosting.md).

## The mistake this saves you from

Build the server with `FastMCP("name")` and no bind address, deploy it in a
container, and every request will be answered `421 Misdirected Request` — after
authentication, before any tool, with the health probe still green. `FastMCP` freezes
a DNS-rebinding allow-list to loopback at construction and never revisits it.

`McpServerHost.serve` reads that allow-list and refuses to start instead:

```
McpServerUnreachableError: this server would answer 421 to a request for host
'demo:9300': its DNS-rebinding allow-list is ['127.0.0.1:*', 'localhost:*',
'[::1]:*'], derived from a bind address that does not include it.
```
