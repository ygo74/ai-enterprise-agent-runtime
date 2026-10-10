# Quickstart: serve an agent with FastAPI

This quickstart runs a local echo handler behind the OpenAI Responses endpoint.
It exercises endpoint registration, normalized handler input, and response
mapping without requiring an LLM key or an external service.

## Prerequisites

- Python 3.12 or newer
- Network access to install the Python package and its HTTP dependencies

## Run the example

Follow the [quickstart example README](../examples/python-fastapi-quickstart/README.md):

```bash
cd docs/examples/python-fastapi-quickstart
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
uvicorn app:app --reload --port 8000
```

On Windows PowerShell, activate the virtual environment using
`.venv\Scripts\Activate.ps1`.

## Call the endpoint

In another terminal:

```bash
curl -sS http://127.0.0.1:8000/v1/responses \
  -H 'Content-Type: application/json' \
  -d '{"model":"echo-agent","input":"hello"}'
```

The response's `output_text` is `Echo: hello`.

The app registers `/v1/responses`, `/v1/chat/completions`, and `/v1/messages`. The
`add_ai_endpoints` helper accepts a FastAPI app, a handler, and a default route
key. Its handler receives a mapping with `request_id`, `route_key`, `endpoint_type`,
`input`, `stream`, `metadata`, and `auth_context`; it returns a typed `AgentOutput`
or a stream of typed events. The runtime handles conversion between that pivot and the
provider response shape. See the [agent runtime guide](agent-runtime.md) for
streaming, authentication, discovery, and other configuration.

Raw output strings/dictionaries and native OpenAI stream events were removed in
agents 1.0. See [typed outputs and migration](typed-outputs.md) before adapting
an older handler.

This quickstart is deliberately minimal. See the [LangChain + FastAPI examples](../examples/python-langchain-fastapi/README.md)
for a real agent with an external LLM and MCP tool, JWT and OIDC authentication,
agent discovery, and human approval.
