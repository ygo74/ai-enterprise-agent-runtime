# Install the runtime and make a first request

This guide starts a local FastAPI endpoint. The example returns a fixed echo, so
it does not need an AI provider account or an API key.

## Requirements

- Python 3.12 or newer
- Network access to install packages

## Install and start

Run these commands from the repository root:

```bash
cd samples/examples/python-fastapi-quickstart
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
uvicorn app:app --reload --port 8000
```

In Windows PowerShell, activate the environment with
`.venv\Scripts\Activate.ps1`.

## Send a request

Open another terminal and run:

```bash
curl -sS http://127.0.0.1:8000/v1/responses \
  -H 'Content-Type: application/json' \
  -d '{"model":"echo-agent","input":"hello"}'
```

The JSON response contains `output_text` with the value `Echo: hello`. If the
request fails, check that Uvicorn is still running on port 8000 and that the
request body is valid JSON.

## Choose packages for an application

The runtime is split into installable Python distributions. For a FastAPI agent,
install `ygo74-agent-runtime-agents[http]`. Add
`ygo74-agent-runtime-langchain` or
`ygo74-agent-runtime-agentframework` only when the application uses that
framework adapter. Use `ygo74-agent-runtime-mcp` to host an MCP server.

See the [package selection table](../../doc/python/installation.md) before
deploying. The [quickstart guide](../../doc/python/quickstart.md) explains the
handler contract and the other endpoint surfaces.
