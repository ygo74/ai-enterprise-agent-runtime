# Python FastAPI quickstart

This small, local example hosts the Python runtime behind FastAPI and echoes
requests through the OpenAI Responses, Chat Completions, and Anthropic Messages
endpoints. It needs no LLM provider key or external service.

## Requirements

- Python 3.12 or newer
- Network access to install the package dependencies

## Install and run

From this directory:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
uvicorn app:app --reload --port 8000
```

On Windows PowerShell, activate the environment with
`.venv\Scripts\Activate.ps1` instead of the `source` command.

## Send a request

With the server running in one terminal, call it from another:

```bash
curl -sS http://127.0.0.1:8000/v1/responses \
  -H 'Content-Type: application/json' \
  -d '{"model":"echo-agent","input":"hello"}'
```

The response includes `"output_text":"Echo: hello"`. The example handler
receives the runtime's normalized payload and returns a standard success
envelope; the runtime formats it as an OpenAI Responses response. To see the
Chat Completions surface, post `{"model":"echo-agent","messages":[{"role":"user","content":"hello"}]}`
to `/v1/chat/completions`.

For Anthropic Messages, post `{"model":"echo-agent","max_tokens":64,"messages":[{"role":"user","content":"hello"}]}`
to `/v1/messages`.

## Responses scenarios for compatible clients

The companion `responses_structured_app.py` is a deterministic Responses test
server. It needs no model or provider key. From this directory, run:

```bash
uvicorn responses_structured_app:app --reload --port 8001
```

Connect LibreChat or another OpenAI-compatible client to
`http://127.0.0.1:8001/v1` and select `structured-agent`. The app allows
anonymous requests. Send one of these commands as the user message:

| User message | Output shape to inspect |
|---|---|
| `test:rag` | One `output_text` block with two URL citation annotations; the stream also emits `response.output_text.annotation.added` events. |
| `test:content` | One message whose `content` is a collection of three separate `output_text` blocks, including citations. |
| `test:mcp` | A completed `mcp_call` output item with JSON tool arguments and JSON-string result, followed by an assistant message. Streaming includes MCP progress, argument, and completion events. |
| Any other message | The default message plus `function_call` example. |

The scenario text can also be posted directly to inspect the raw wire response:

```bash
curl -sS http://127.0.0.1:8001/v1/responses \
  -H 'Content-Type: application/json' \
  -d '{"model":"structured-agent","input":"test:rag"}'
```

Add `"stream":true` to the body to inspect the same scenario as Responses SSE
events. `test:rag` and `test:mcp` emit the corresponding annotation and MCP
event sequences. These are fixed fixtures for checking client rendering; they
do not call a retriever, MCP server, or language model.

The example deliberately enables anonymous access with
`AuthenticationPolicy.anonymous()` and publishes the agent through
`GET /v1/models`. Call that route to see the descriptor. See the [agent runtime
guide](../../python/agent-runtime.md) for protected authentication and discovery
options, and the [installation guide](../../python/installation.md) for package
choices.
