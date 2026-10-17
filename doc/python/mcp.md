# Model Context Protocol (MCP)

The Python runtime has separate packages for connecting an agent to an MCP
server and for hosting an MCP server. Install the package that matches the role
of the process; see [installation](installation.md).

## MCP client for agent use cases

The `ygo74-agent-runtime-agents[mcp]` extra installs the MCP client dependencies
for the agents distribution. Importing unrelated runtime domains does not
require this extra. `McpServerBinding[CapabilityT]` describes a server,
transport (`stdio` or streamable HTTP), application-defined `StrEnum`
capabilities, and the aliases a server uses for its tools. The generic loader
validates the binding against that enum and the declared endpoint. Bindings also
provide `require_aliases()` and `require_declared_capabilities()` checks so a
dialect can fail before its first tool call; the latter applies when capability
names are also keys in the alias map. An application keeps that choice with its
own catalog and dialect rules.

### Declarative client configuration

Install the `mcp` extra to use `McpServerConfigurationLoader` and
`McpAgentRegistryLoader`. An agent can optionally declare a default `mcp_server`
in `agent.yaml`. An MCP-enabled skill can inherit that default by omitting its
own `mcp_server`, or override it with a skill-level value. Each MCP skill keeps
its own non-empty list of logical tool aliases. A skill without an explicit or
inherited server is rejected. The matching server file lives under
`config/mcp/<name>.yaml`; only effective server names referenced by the loaded
agent are read.
The packaged server schema is available through
`ManifestSchemas.mcp_server()` (`urn:ygo74:agent-runtime:mcp-server:1`) and is
used by the runtime loader as well as YAML editor tooling.

```yaml
# agent.yaml
mcp_server: mail-http
```

```yaml
# skill.yaml: inherits mail-http
mcp_tools:
  - search_mail
```

```yaml
# another skill.yaml: overrides the agent default
mcp_server: archive-http
mcp_tools:
  - search_archive
```

```yaml
# config/mcp/mail-http.yaml
server: mail-http
transport: http
url: https://mail.example.test/mcp
capabilities: [search_mail, send_mail]
tools:
  search_mail: messages_search
  send_mail: messages_send
request_timeout_seconds: 30
authentication_mode: api_key
authentication_api_key:
  header_name: X-API-Key
  value: ${MAIL_MCP_API_KEY}
network:
  proxy_url: http://proxy.example.test:8080
```

The server file supports `http` and `stdio`. HTTP authentication can be
`none`, `api_key`, `oauth`, or `oauth_on_behalf_of`; stdio accepts no HTTP
headers, authentication, or proxy. Timeouts and proxy settings apply only to
HTTP. Proxy URLs must use HTTP or HTTPS and cannot contain credentials.

HTTP `headers` accept literal values, exact `${ENV_NAME}` references, and
request-context templates. Environment references use the process environment
or the `.env` file beside the delivered `config/` directory; they must occupy
the entire value. Context templates are resolved separately for each outbound
JSON-RPC request:

| Template | Value |
| --- | --- |
| `{{USER_ID}}` | Authenticated principal subject |
| `{{USER_EMAIL}}` | Authenticated principal email |
| `{{USER_NAME}}` | Authenticated principal display name |
| `{{USER_ROLES}}` | Sorted roles joined with commas |
| `{{REQUEST_ID}}` | Runtime request correlation ID |
| `{{CONVERSATION_ID}}` | Caller-scoped conversation ID |
| `{{SESSION_ID}}` | Alias of the conversation ID |

For example:

```yaml
headers:
  X-User-ID: '{{USER_ID}}'
  X-Conversation-ID: '{{CONVERSATION_ID}}'
  X-Request-ID: 'request={{REQUEST_ID}}'
  X-Gateway-Key: ${MAIL_MCP_GATEWAY_KEY}
```

Unknown templates, missing values, partial environment references, invalid
header names, and authentication-header conflicts fail configuration loading
or the affected request without exposing configured values. Context values
come from the runtime's verified `AgentPrincipal` and request metadata; the
runtime does not forward arbitrary caller headers or authentication claims.
Outside OBO, one shared MCP connection correlates each HTTP POST with its
JSON-RPC request ID, so overlapping turns keep their own identity and
conversation headers. In OBO mode the connection opens a separate MCP session
for each authenticated principal. Its GET event stream, DELETE, and notifications
without a JSON-RPC ID use that session's principal-bound context; POST requests
with IDs continue to use their individual turn context. Calling an OBO connection
without a verified principal and subject token fails closed.

API-key values and OAuth client secrets must be references in the form
`${ENV_VAR}`; literal credentials in those dedicated fields, missing variables,
and empty values are rejected. The agent registry loads `.env` values without
overriding process values; callers can inject an environment mapping for
deterministic configuration loading.

OAuth settings include a client ID, client-secret reference, pinned scopes,
callback port, client name, and token-file path. Relative token paths resolve
from the directory beside `config/`. The registry constructs the existing
loopback OAuth provider but does not open a browser or make a network request
while loading configuration.

`oauth` remains the MCP client's own authorization-code flow. To delegate the
authenticated user's identity to an MCP resource, configure a separate mode:

```yaml
authentication_mode: oauth_on_behalf_of
authentication_oauth_on_behalf_of:
  token_url: https://identity.example.test/realms/agents/protocol/openid-connect/token
  client_id: mail-agent
  client_secret: ${MCP_MAIL_OBO_CLIENT_SECRET}
  audience: https://mail.example.test
  scopes: [mail.read, mail.send]
```

The runtime maps these fields to `OAuthTokenExchangeSettings` and uses its
`Rfc8693OAuthOnBehalfOfTokenSource` by default. The token endpoint and client ID
stay in YAML; only `client_secret` is an exact `${ENV_VAR}` reference resolved
from the process environment or the `.env` beside `config/`. The secret is held
as `SecretStr`, never included in representations or configuration errors, and
the endpoint must use HTTPS. The three client fields are optional as a group
for custom injected sources that need only `audience` and `scopes`.

The standard source is constructed locally for each configured server and makes
no request until an MCP call needs a delegated token. Applications can override
it with `delegated_token_source_factory` for provider-specific exchanges, or
continue to inject one shared `OAuthOnBehalfOfTokenSource` with
`delegated_token_source`.

The source's `token_for(DelegatedTokenRequest)` implementation exchanges the
verified agent bearer token for an `AccessToken` whose audience matches the
configured MCP audience. The existing `DelegatedTokenSource` contract remains
credential-free and receives only the principal and audience. The runtime sends
only the token returned by the OBO source to MCP. API-key and anonymous
requests cannot use OBO, and a missing source, failed exchange, or wrong-audience
token stops the call. Provider-specific exchange and token-cache policy stay in
the custom host implementation; caches must be partitioned by caller, audience,
and scopes.

`McpAgentRegistryLoader(configuration_directory, capabilities).load(agent)`
loads each referenced server once and keeps its `McpConnection` lazy. Call
`registry.for_skill(tool_name)` to get that skill's view; its `tools` mapping
contains only that skill's allow-listed aliases and `remote_tool(alias)` rejects
all others, even when another skill shares the same server. The registry owns
the shared connection lifecycle, including all principal-partitioned OBO
sessions, and should be closed with `await registry.aclose()` when the agent
stops. Existing direct use of
`McpServerBinding`, `McpServerBindingLoader`, and `McpConnection` remains
available for application-controlled composition.

The agents `configuration` extra includes PyYAML, python-dotenv, and JSON Schema
validation for manifests. The `mcp` extra installs those configuration
dependencies together with the MCP SDK and HTTPX; they remain optional for
unrelated runtime domains. Existing skill-level server declarations remain
valid. Non-MCP skills need neither `mcp_server` nor `mcp_tools`; MCP skills must
declare `mcp_tools` and resolve a server from either the skill or its agent.
Skills that declare a local `mcp_server` must also add at least one `mcp_tools`
alias. The packaged agent and skill schemas reflect their respective parts of
this contract, and server YAML must match the strict schema, including its
known fields.

See the [configuration example](../../samples/examples/python-langchain-fastapi/08-mcp-configuration/README.md)
for shared and distinct server references and a local loader smoke path that
does not connect to a server.

`McpConnection` manages one lazily opened client session and its transport.
Configured header values are redacted in representations and diagnostics.
Stdio environment-variable resolution and deployment policies such as Wiki's
read-only filter remain application responsibilities.

`DialectRegistry[ToolsT, Params]` dispatches by the binding's dialect and uses a
typed factory whose first parameter is the binding. Applications retain their
concrete dialect factories and can provide an error factory so transport and
dialect failures keep their public error categories. The client does not host
the remote server.

See the [MCP client binding](../../packages/python/agents/ygo74/agent_runtime/domains/mcp/binding.py)
and [dialect registry](../../packages/python/agents/ygo74/agent_runtime/domains/mcp/dialects.py).
The [LangChain + FastAPI example](../../samples/examples/python-langchain-fastapi/01-get-started/README.md)
connects to Microsoft's public Learn MCP service; that example requires its
external LLM and MCP service prerequisites.

## Host an MCP server

The `ygo74-agent-runtime-mcp` distribution hosts an MCP server without the agent
runtime. Install its `http` extra for streamable HTTP transport:

```bash
python -m pip install 'ygo74-agent-runtime-mcp[http]'
```

For stdio, install the MCP SDK explicitly because it is not a base dependency of
the server distribution:

```bash
python -m pip install ygo74-agent-runtime-mcp 'mcp>=1.24,<2'
```

`McpServerHost` wraps an MCP server application with an `AuthenticationPolicy`
and `McpHttpBinding`. Construct `FastMCP` with the actual host and port so its
DNS-rebinding allow-list includes the address clients use. The host exposes
`/healthz` and the protected-resource metadata route as public discovery
surfaces; tool requests are authenticated according to the configured policy.
An omitted HTTP authentication choice is a startup error rather than an
implicit anonymous service.

For setup and environment variables, follow the detailed [MCP server hosting
guide](../users/mcp-server-hosting.md) and [runnable MCP server example](../../samples/examples/python-mcp-server/README.md).
