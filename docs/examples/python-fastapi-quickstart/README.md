# Python FastAPI quickstart

This small, local example hosts the Python runtime behind FastAPI and echoes
requests through OpenAI Responses, Chat Completions and Anthropic Messages.
It needs no LLM provider key or external service.

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
receives the runtime's normalized payload and returns
`AgentOutput((TextContent("Echo: hello"),), usage=ECHO_MODEL_USAGE)`; the runtime owns the provider
envelope. To see the
Chat Completions surface, post `{"model":"echo-agent","messages":[{"role":"user","content":"hello"}]}`
to `/v1/chat/completions`.

To receive incremental Responses events, send `"stream":true` and keep curl's
output unbuffered with `-N`:

```bash
curl -N http://127.0.0.1:8000/v1/responses \
  -H 'Content-Type: application/json' \
  -d '{"model":"echo-agent","input":"hello","stream":true}'
```

The stream emits separate text deltas for `Echo: ` and `hello`, followed by
`response.completed`.

For Anthropic Messages, post `{"model":"echo-agent","max_tokens":64,"messages":[{"role":"user","content":"hello"}]}`
to `/v1/messages`. Pure Echo invokes no model at all: its model token consumption
is genuinely zero, including input/output/total, cached read/write and reasoning
counters. The producer explicitly provides that known `TokenUsage` snapshot in
final output and as a `UsageEvent` **before** visible stream content. This is not
a generic fallback for unknown usage, nor a token estimate from displayed text.
All three SDK surfaces can therefore consume Echo successfully.
For chat/message inputs the example reuses the runtime's latest-user-message
reader instead of echoing the serialized conversation history.

## Provider-neutral structured scenarios

The companion `responses_structured_app.py` is a deterministic typed-output
server with all three routes registered. Unlike pure Echo, it deliberately
leaves usage unspecified and does not assign zero counters. OpenAI projections
work without usage; Anthropic fails explicitly with `unsupported_output_projection`
rather than inventing token counts (an SSE error without successful `message_start`
in streaming mode). A real Anthropic-compatible handler must provide known
`AgentOutput.usage`, or an initial `UsageEvent` before visible streaming content;
later measured cumulative usage may update the stream. This separate fixture
preserves the unknown-usage rejection demonstration.
It needs no framework, model or provider key.
Only `ygo74-agent-runtime-agents[http]>=1.0,<2` is installed. From this directory, run:

```bash
uvicorn responses_structured_app:app --reload --port 8001
```

Connect LibreChat or another OpenAI-compatible client to
`http://127.0.0.1:8001/v1` and select `structured-agent`. The app allows
anonymous requests. When `input` contains conversation history, the scenario is
selected from the latest user message; earlier messages do not select a scenario.

Send one of these commands as the user message:

| User message | Output shape to inspect |
|---|---|
| `test:rag` | Grounded text with source references. |
| `test:content` | Three separate typed text contents. |
| `test:tools` | The handler emits a correlated internal tool call/result with fragmented stream arguments; current projections filter these internal observations and deliver the final text. |
| `test:notifications` | A typed progress notification in streaming only, followed by the business answer. |
| `test:media` | The handler emits text and an encoded one-pixel PNG; current projections filter assistant images on all three surfaces with a runtime diagnostic. |
| Any other message | A typed text answer. |

The scenario text can also be posted directly to inspect the raw wire response:

```bash
curl -sS http://127.0.0.1:8001/v1/responses \
  -H 'Content-Type: application/json' \
  -d '{"model":"structured-agent","input":"test:rag"}'
```

In PowerShell, use `ConvertTo-Json -Depth 100` to display the complete nested
response payload, including the `output` items and explicit source URLs:

```powershell
$body = @{
    model = "structured-agent"
    input = "test:rag"
} | ConvertTo-Json

$response = Invoke-RestMethod `
    -Uri "http://127.0.0.1:8001/v1/responses" `
    -Method Post `
    -ContentType "application/json" `
    -Body $body

$response | ConvertTo-Json -Depth 100
```

Add `"stream":true` to inspect the same scenario as SSE. The handler emits
`ContentStart`, `TextDelta`/`ToolArgumentsDelta`, `ContentEnd`, `ContentEvent`
and `TerminalEvent`, never provider-native dictionaries or raw string streams.
The runtime assigns provider event names and sequence numbers. Internal tool
observations are not client-delegated tools or fabricated provider-hosted MCP
calls; each surface maps or explicitly filters them according to its support.
These fixtures do not call a retriever, MCP server, or language model.
Discovery advertises text output only: the image demonstrates unsupported pivot
content and does not claim a projected image-generation capability.

The example deliberately enables anonymous access with
`AuthenticationPolicy.anonymous()` and publishes the agent through
`GET /v1/models`. Call that route to see the descriptor. See the [agent runtime
guide](../../python/agent-runtime.md) for protected authentication and discovery
options, and the [installation guide](../../python/installation.md) for package
choices.
