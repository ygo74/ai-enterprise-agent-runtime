# 08 - Declarative MCP client configuration

This example loads two MCP server files through the Python agent runtime. Two
skills share the mail server, and a third skill uses an archive server. The
smoke script prints the aliases available to each skill and closes the registry
without opening an MCP connection, contacting a remote service, or starting OAuth
consent.

## Files

- `config/mcp/mail.yaml`: shared HTTP server using an API-key reference and an
  optional proxy.
- `config/mcp/archive.yaml`: distinct HTTP server using OAuth client settings.
- `config/agents/mail-assistant/agent.yaml` and `config/skills/mail-assistant/`:
  three delivered skills, with two referencing the shared mail server.
- `.env.example`: placeholder values for the API key and OAuth client secret.
- `registry_smoke.py`: loads the delivered agent and skill manifests, then loads
  the server configuration through `McpAgentRegistryLoader`.

## Run the configuration smoke path

Use Python 3.12 or newer, install the local security and agent packages with the
MCP extra, and copy the placeholder environment file:

```bash
cd samples/examples/python-langchain-fastapi/08-mcp-configuration
python -m pip install -e ../../../../packages/python/security
python -m pip install -e '../../../../packages/python/agents[mcp]'
cp .env.example .env
python registry_smoke.py
```

The placeholder credentials are enough to validate and compose the registry.
Replace them with real values only when the application later opens a remote
connection. To use a proxy, edit `config/mcp/mail.yaml` and set
`network.proxy_url`; the registry validates it before any connection is opened.

The `# yaml-language-server: $schema=...` annotations point to the packaged
MCP server schema in this repository. The runtime reads the same Draft 2020-12
schema while loading each referenced file.
