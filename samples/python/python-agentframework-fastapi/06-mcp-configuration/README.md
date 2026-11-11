# 06 — Declarative MCP configuration for a MAF application

MCP server and skill configuration is framework-neutral, so a MAF host can use
the same typed registry as a LangChain host. This smoke example loads the
agent's skills and their referenced server YAML through
`McpAgentRegistryLoader`, lists each skill's aliases, then closes the registry.
It does not open a remote MCP connection, start OAuth consent, or execute an
outbound tool. The application remains responsible for its MCP client calls.
The same agent manifest also enables an inbound `/mcp` endpoint, shown by the
small local hosting smoke app below.

## Run the configuration smoke path

Use Python 3.12 or newer. From this directory, install the local security and
agent distributions with the MCP extra, then copy the placeholder environment
file:

```bash
python -m pip install -e ../../../../packages/python/security
python -m pip install -e '../../../../packages/python/mcpserver[http]'
python -m pip install -e '../../../../packages/python/agents[configuration,http,mcp,mcp-server]'
cp .env.sample .env
python registry_smoke.py
python http_configuration_smoke.py
```

The delivered values validate and compose the registry without making a
connection. Replace them only when the MAF application later opens a remote
server. See the Python [MCP guide](../../../../doc/python/mcp.md) for server
configuration, identity templates, and tool allow-lists.

The agent manifest selects Chat Completions and Responses, a service API-key
identity, and a `60/minute` rate limit. `registry_smoke.py` loads the agent for
MCP use without resolving its HTTP key. `http_configuration_smoke.py` resolves
the HTTP settings from the placeholder `.env` value and prints only the
selected endpoints, authentication mode, and limits. A MAF FastAPI host can
pass the built settings to `HostingFactory.add_http_settings()`.

## Run the inbound agent MCP endpoint

The manifest selects OpenAI routes and MCP Streamable HTTP at `/mcp`, protected
by the same API key. From this directory, start the deterministic hosting
example after installing the packages above:

```bash
python -m uvicorn hosting_smoke:app --host 127.0.0.1 --port 8102
```

The sample handler returns an echo so the transport can be exercised without a
model or remote mail server. Use an MCP client pointed at
`http://127.0.0.1:8102/mcp` with the value of `MAIL_ASSISTANT_HTTP_API_KEY`.
`hosting_smoke.py` starts the mounted FastMCP session manager and closes it with
the parent FastAPI lifespan. `GET /health/ready` remains available alongside
the root-mounted MCP app.

API-key mode does not require OAuth resource metadata. For a JWT deployment,
add the canonical public resource URL (including `/mcp`) to the manifest and
provide it through the environment:

```yaml
http:
  endpoints: [mcp]
  mcp:
    resource_url: ${MAIL_ASSISTANT_MCP_RESOURCE_URL}
  security:
    mode: jwt
    jwt:
      issuer: https://identity.example.test/issuer
      jwks_url: https://identity.example.test/keys
```

The endpoint reuses the agent's conversation cache. That cache is bounded and
process-local, so a multi-replica deployment needs session affinity to continue
an existing conversation.
