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
`McpAgentRegistryLoader`. Each skill can declare a server name and a non-empty
list of logical tool aliases. The matching server file lives under
`config/mcp/<name>.yaml`; only names referenced by the loaded agent are read.
The packaged server schema is available through
`ManifestSchemas.mcp_server()` (`urn:ygo74:agent-runtime:mcp-server:1`) and is
used by the runtime loader as well as YAML editor tooling.

```yaml
# skill.yaml
mcp_server: mail-http
mcp_tools:
  - search_mail
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
`none`, `api_key`, or `oauth`; stdio accepts no HTTP authentication or proxy.
Timeouts and proxy settings apply only to HTTP. Proxy URLs must use HTTP or
HTTPS and cannot contain credentials. API-key values and OAuth client secrets
must be references in the form `${ENV_VAR}`; literal credentials in YAML,
missing variables, and empty values are rejected. Only those two credential
fields are interpolated. Put variables in the process environment or in the
`.env` file beside the delivered `config/` directory. The agent registry
entrypoint loads that file without overriding process values; callers can
inject an environment mapping for deterministic configuration loading.

OAuth settings include a client ID, client-secret reference, pinned scopes,
callback port, client name, and token-file path. Relative token paths resolve
from the directory beside `config/`. The registry constructs the existing
loopback OAuth provider but does not open a browser or make a network request
while loading configuration.

`McpAgentRegistryLoader(configuration_directory, capabilities).load(agent)`
loads each referenced server once and keeps its `McpConnection` lazy. Call
`registry.for_skill(tool_name)` to get that skill's view; its `tools` mapping
contains only that skill's allow-listed aliases and `remote_tool(alias)` rejects
all others, even when another skill shares the same server. The registry owns
the shared connection lifecycle and should be closed with `await
registry.aclose()` when the agent stops. Existing direct use of
`McpServerBinding`, `McpServerBindingLoader`, and `McpConnection` remains
available for application-controlled composition.

The agents `configuration` extra includes PyYAML, python-dotenv, and JSON Schema
validation for manifests. The `mcp` extra installs those configuration
dependencies together with the MCP SDK and HTTPX; they remain optional for
unrelated runtime domains. Existing skill manifests without `mcp_server` remain
valid. Skills that add `mcp_server` must also add at least one `mcp_tools`
alias, and server YAML must now match the strict packaged schema, including its
known fields.

See the [configuration example](../../samples/examples/python-langchain-fastapi/08-mcp-configuration/README.md)
for shared and distinct server references and a local loader smoke path that
does not connect to a server.

`McpConnection` manages one lazily opened client session and its transport. For
HTTP, applications may pass request-scoped headers; the runtime does not log
header values and its header mapping representation redacts them. The
application remains responsible for choosing credentials and ensuring a
connection is scoped to the right caller. Stdio environment-variable resolution
and deployment policies such as Wiki's read-only filter also remain application
responsibilities.

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
