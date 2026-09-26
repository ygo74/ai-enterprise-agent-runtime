# Installation and package selection

The runtime supports Python 3.12 or newer. The four distributions share the
`ygo74.agent_runtime` import namespace, but each owns a separate set of domains.
Install the smallest distribution that serves your process.

| Distribution | Use it for | Base dependencies |
|---|---|---|
| [`ygo74-agent-runtime-security`](../../packages/python/security/pyproject.toml) | Shared authentication and security types | Pydantic, PyJWT |
| [`ygo74-agent-runtime-agents`](../../packages/python/agents/pyproject.toml) | Hosting agents, endpoint mapping, discovery, sessions, approval, and MCP clients | Security distribution, Pydantic, typing-extensions |
| [`ygo74-agent-runtime-mcp`](../../packages/python/mcpserver/pyproject.toml) | Hosting MCP servers over stdio or HTTP | Security distribution, Pydantic |
| [`ygo74-agent-runtime`](../../packages/python/meta/pyproject.toml) | Meta-package that installs all three distributions | All three distributions |

## Install a distribution

Install security primitives only:

```bash
python -m pip install ygo74-agent-runtime-security
```

Host an agent over HTTP (FastAPI and Uvicorn):

```bash
python -m pip install 'ygo74-agent-runtime-agents[http]'
```

Use the agents package's MCP client (the Python MCP SDK, HTTPX, and PyYAML):

```bash
python -m pip install 'ygo74-agent-runtime-agents[mcp]'
```

Host an MCP server over HTTP:

```bash
python -m pip install 'ygo74-agent-runtime-mcp[http]'
```

The MCP server package can also host a stdio server. The MCP SDK is not a base
dependency, so install it explicitly for that transport:

```bash
python -m pip install ygo74-agent-runtime-mcp 'mcp>=1.24,<2'
```

Install all three distributions through the meta-package:

```bash
python -m pip install ygo74-agent-runtime
```

The meta-package's extras forward optional features:

```bash
python -m pip install 'ygo74-agent-runtime[http,mcp,mcp-server]'
```

`http` and `mcp` enable the corresponding extras on the agents distribution;
`mcp-server` enables HTTP hosting on the MCP server distribution. Quote extras
when using shells that treat square brackets as patterns.

## Create an environment

Use an isolated environment for each service:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install 'ygo74-agent-runtime-agents[http]'
```

On Windows PowerShell, activate it with `.venv\Scripts\Activate.ps1`.

## Develop from this repository

From the repository root, install the local source packages in editable mode.
This example installs the security and agent packages with HTTP support:

```bash
python -m pip install -e ./packages/python/security -e './packages/python/agents[http]'
```

The repository examples that run directly from a checkout document their own
`PYTHONPATH` setup. Its relative path depends on the example's depth; on Windows,
separate entries with semicolons.
