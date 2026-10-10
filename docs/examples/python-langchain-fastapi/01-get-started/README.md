# 01-get-started: Python LangChain + FastAPI (AI Solution Architect)

This example shows a real implementation of an **AI Solution Architect** agent that:

1. Uses a LangChain agent.
2. Calls a remote MCP tool for Microsoft Learn (`https://learn.microsoft.com/api/mcp`).
3. Exposes OpenAI Responses (`/v1/responses`) and Chat Completions endpoints through the runtime's public `HostingFactory` API.

## Files

- `openai_responses_app.py`: FastAPI endpoint exposed as OpenAI Responses.
- `agent_solution_architect.py`: LangChain tool-calling agent setup.
- `mcp_mslearn_tool.py`: MCP tool wrapper to query Microsoft Learn MCP.
- `requirements.txt`: Example dependencies.
- `.env.sample`: safe local configuration template.

## Prerequisites

- Python 3.12+
- OpenAI API key
- Optional MCP auth:
  - `MSLEARN_MCP_API_KEY` + optional `MSLEARN_MCP_API_KEY_HEADER`
  - or `MSLEARN_MCP_BEARER_TOKEN`

## Install

```powershell
cd docs/examples/python-langchain-fastapi/01-get-started
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

## Environment

This example loads variables from the local `.env` file automatically.
Create it from `.env.sample` and replace the OpenAI key placeholder:

```powershell
Copy-Item .env.sample .env
```

Required key:
- `OPENAI_API_KEY`

The model and Microsoft Learn MCP URL/tool have defaults. The sample includes
only placeholder values; replace the OpenAI key before running the app.

You can still override values from the shell if needed:

```powershell
$env:OPENAI_API_KEY="<your-openai-key>"
$env:OPENAI_MODEL="gpt-4o-mini"
$env:MSLEARN_MCP_URL="https://learn.microsoft.com/api/mcp"
$env:MSLEARN_MCP_TOOL="microsoft_docs_search"
# Optional auth headers:
# $env:MSLEARN_MCP_API_KEY="..."
# $env:MSLEARN_MCP_API_KEY_HEADER="Ocp-Apim-Subscription-Key"
# $env:MSLEARN_MCP_BEARER_TOKEN="..."
```

The requirements explicitly install agents 1.x and the independent LangChain
integration, not the base meta package. For development against this repository,
include both source distributions in `PYTHONPATH`:

```powershell
$env:PYTHONPATH="..\..\..\..\packages\python\security;..\..\..\..\packages\python\agents;..\..\..\..\packages\python\langchain"
```

## Run

```powershell
# From docs/examples/python-langchain-fastapi/01-get-started
python -m uvicorn openai_responses_app:app --reload --port 8001
```

## Test Request

```powershell
$body = @{
  model = "gpt-5-chat"
  input = "Design an enterprise AI solution architecture for RAG with governance and cost controls."
  metadata = @{
    request_id = "demo-architect-001"
    route_key = "ai-solution-architect"
  }
  stream = $false
} | ConvertTo-Json -Depth 10

Invoke-RestMethod -Method Post `
  -Uri "http://127.0.0.1:8001/v1/responses" `
  -ContentType "application/json" `
  -Body $body
```

## SDK Compatibility Client

Use the Python client below to test this endpoint with both SDKs:

- OpenAI SDK -> `/v1/responses`
- OpenAI SDK -> `/v1/chat/completions`
- OpenAI SDK -> `/v1/chat/completions` with `stream=True` (Server-Sent Events)
- Anthropic SDK -> `/v1/messages`

Run all checks (default):

```powershell
# From docs/examples/python-langchain-fastapi/01-get-started
python sdk_compat_client.py --base-url http://127.0.0.1:8001
```

If `/v1/messages` is not enabled yet:

```powershell
python sdk_compat_client.py --base-url http://127.0.0.1:8001 --skip-anthropic
```

Run a single specific check with `--test-openai-responses`, `--test-openai-chat-completions`, or
`--test-anthropic-messages` (if none of these are passed, all checks run, same as the default above):

```powershell
python sdk_compat_client.py --base-url http://127.0.0.1:8001 --test-openai-chat-completions
```

Add `--enable-stream` to run the selected check(s) with `stream=True` instead of a single blocking response:

```powershell
python sdk_compat_client.py --base-url http://127.0.0.1:8001 --test-openai-chat-completions --enable-stream
python sdk_compat_client.py --base-url http://127.0.0.1:8001 --test-openai-responses --enable-stream
```

## Notes

- The MCP tool call is implemented in `mcp_mslearn_tool.py` with `streamable-http` transport.
- If the MCP SDK is unavailable at runtime, the tool returns a deterministic fallback message that includes the intended MCP call details.
- Endpoint registration uses `HostingFactory`; the example allows anonymous requests, matching the low-level registrar's default.
- `stream=True` requests are served as real Server-Sent Events (`text/event-stream`) with genuine token-by-token incremental deltas: `run_solution_architect_agent_stream` (in `agent_solution_architect.py`) consumes the LangChain agent via `astream_events(..., version="v2")` and forwards each `on_chat_model_stream` text delta as it is produced, including after any MCP tool call the agent makes along the way.
- **Tool call visibility (e.g. in LibreChat)**: the developer's `astream_events`
  loop chooses tool starts/ends to expose as typed `Notification` contents.
  The runtime renders these short Markdown notices in streaming only; they are
  not assistant answer deltas and never contaminate non-streaming answers.
  Set `AGENT_STREAM_TOOL_NOTICES=false` to suppress them. Other native events
  are selected or ignored by developer code, not blindly forwarded.
- Native LangChain answers/events are converted through the optional integration
  to `AgentOutput`/`AgentStreamEvent`; no handler builds OpenAI wire output.
