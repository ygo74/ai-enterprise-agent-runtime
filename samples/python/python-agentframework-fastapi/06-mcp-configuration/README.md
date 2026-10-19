# 06 — Declarative MCP configuration for a MAF application

MCP server and skill configuration is framework-neutral, so a MAF host can use
the same typed registry as a LangChain host. This smoke example loads the
agent's skills and their referenced server YAML through
`McpAgentRegistryLoader`, lists each skill's aliases, then closes the registry.
It does not open a remote MCP connection, start OAuth consent, or execute a
tool. The application remains responsible for admitting and invoking tools.

## Run the configuration smoke path

Use Python 3.12 or newer. From this directory, install the local security and
agent distributions with the MCP extra, then copy the placeholder environment
file:

```bash
python -m pip install -e ../../../../packages/python/security
python -m pip install -e '../../../../packages/python/agents[mcp]'
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
