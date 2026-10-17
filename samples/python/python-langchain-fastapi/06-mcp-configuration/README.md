# 06 — Declarative MCP client configuration

This example loads three MCP server files through the Python agent runtime.
The agent declares `mail` as its default: two skills inherit it, a third
overrides it with `archive`, and a fourth uses the delegated-OAuth server. The
smoke script prints each skill's aliases and closes the registry without opening
an MCP connection, contacting a remote service, or starting OAuth consent. Its fake
delegated-token source is injected only to demonstrate the host integration
point.

## Files

- `config/mcp/mail.yaml`: shared HTTP server using an API-key reference,
  environment-backed gateway header, identity templates, and an optional proxy.
- `config/mcp/archive.yaml`: distinct HTTP server using OAuth client settings.
- `config/mcp/delegated.yaml`: separate OBO server with its token endpoint and
  client ID in YAML, a client-secret environment reference, audience, and scopes.
- `config/agents/mail-assistant/agent.yaml` and `config/skills/mail-assistant/`:
  four delivered skills, with the two mail skills inheriting the agent default.
- `.env.sample`: placeholder values for API-key, gateway-header, OAuth-client,
  and OBO-client secrets.
- `OfflineOAuthOnBehalfOfTokenSource`: fake source proving the OBO provider port can
  be supplied without contacting an identity provider.
- `registry_smoke.py`: loads the delivered agent and skill manifests, then loads
  the server configuration through `McpAgentRegistryLoader`.

## Run the configuration smoke path

Use Python 3.12 or newer, install the local security and agent packages with the
MCP extra, and copy the placeholder environment file:

```bash
cd samples/python/python-langchain-fastapi/06-mcp-configuration
python -m pip install -e ../../../../packages/python/security
python -m pip install -e '../../../../packages/python/agents[mcp]'
cp .env.sample .env
python registry_smoke.py
```

The placeholder credentials are enough to validate and compose the registry.
Replace them with real values only when the application later opens a remote
connection. The OBO fake token is never requested during configuration loading.
To use a proxy, edit `config/mcp/mail.yaml` and set
`network.proxy_url`; the registry validates it before any connection is opened.

The `# yaml-language-server: $schema=...` annotations point to the packaged
MCP server schema in this repository. The runtime reads the same Draft 2020-12
schema while loading each referenced file.
