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

The example enables no authentication or discovery. See the [agent runtime guide](../../python/agent-runtime.md)
for those options and the [installation guide](../../python/installation.md) for
package choices.
