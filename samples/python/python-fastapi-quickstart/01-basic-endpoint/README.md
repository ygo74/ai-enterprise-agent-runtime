# 01 — Basic FastAPI endpoint

This small local example hosts the Python runtime behind FastAPI and echoes
requests through OpenAI Responses, Chat Completions, and Anthropic Messages.
It needs no LLM provider key or external service.

## Install and run

From this directory, create an environment and install the example's
dependencies:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
uvicorn app:app --reload --port 8000
```

On Windows PowerShell, activate the environment with
`.venv\Scripts\Activate.ps1` instead of `source`.

## Send a request

With the server running, call it from another terminal:

```bash
curl -sS http://127.0.0.1:8000/v1/responses \
  -H 'Content-Type: application/json' \
  -d '{"model":"echo-agent","input":"hello"}'
```

The response includes `"output_text":"Echo: hello"`. The handler returns a
typed `AgentOutput`; the runtime creates the provider response envelope. Chat
Completions and Anthropic Messages are available at `/v1/chat/completions` and
`/v1/messages`.

To see incremental Responses events, send `"stream":true` and use curl's
unbuffered output option, `-N`:

```bash
curl -N http://127.0.0.1:8000/v1/responses \
  -H 'Content-Type: application/json' \
  -d '{"model":"echo-agent","input":"hello","stream":true}'
```

The stream emits text deltas followed by `response.completed`. The echo
producer reports zero token usage because it does not call a model; this is not
a fallback for unknown usage.
