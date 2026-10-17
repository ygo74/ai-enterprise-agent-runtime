# 02 — Structured outputs

This deterministic server demonstrates provider-neutral typed outputs without
a framework, model, or provider key. It registers all three endpoint families
and chooses an output scenario from the latest user message.

## Install and run

From this directory:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
uvicorn responses_structured_app:app --reload --port 8001
```

On Windows PowerShell, activate the environment with
`.venv\Scripts\Activate.ps1` instead of `source`.

Connect an OpenAI-compatible client to `http://127.0.0.1:8001/v1` and select
`structured-agent`. The app allows anonymous requests.

## Inspect scenarios

Send one of these messages to `/v1/responses`:

| Message | Output to inspect |
| --- | --- |
| `test:rag` | Grounded text with source references. |
| `test:content` | Three separate typed text contents. |
| `test:tools` | Correlated internal tool call and result events. |
| `test:notifications` | A streaming-only progress notification followed by the answer. |
| `test:media` | Typed content that current endpoint projections explicitly filter. |
| Any other message | A typed text answer. |

For example:

```bash
curl -sS http://127.0.0.1:8001/v1/responses \
  -H 'Content-Type: application/json' \
  -d '{"model":"structured-agent","input":"test:content"}'
```

Add `"stream":true` to inspect the event stream. The runtime formats protocol
events and emits diagnostics when an output type is unsupported by a surface.
The example does not call a retriever, MCP server, or language model.

Anthropic requires known usage counts. This example leaves usage unspecified,
so its Anthropic projection fails explicitly rather than inventing token
counts. See [typed outputs](../../../../doc/python/typed-outputs.md) for
the output contract and support matrix.
