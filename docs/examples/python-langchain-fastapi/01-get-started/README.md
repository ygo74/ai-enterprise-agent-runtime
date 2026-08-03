# 01-get-started: Python LangChain + FastAPI (AI Solution Architect)

This example shows a real implementation of an **AI Solution Architect** agent that:

1. Uses a LangChain agent.
2. Calls a remote MCP tool for Microsoft Learn (`https://learn.microsoft.com/api/mcp`).
3. Exposes an **OpenAI Responses** compatible endpoint (`/v1/responses`) via the `ygo74` runtime mapping layer.

## Files

- `openai_responses_app.py`: FastAPI endpoint exposed as OpenAI Responses.
- `agent_solution_architect.py`: LangChain tool-calling agent setup.
- `mcp_mslearn_tool.py`: MCP tool wrapper to query Microsoft Learn MCP.
- `requirements.txt`: Example dependencies.

## Prerequisites

- Python 3.11+
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
Create it from `.env.sample` and set your values:

```powershell
Copy-Item .env.sample .env
```

Required key:
- `OPENAI_API_KEY`

Optional keys are prefilled in `.env.sample`.

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

`ygo74` package source is in this repo, so include it in `PYTHONPATH` while running the example:

```powershell
$env:PYTHONPATH="../../..\packages/python"
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
- This example is intentionally scoped to the OpenAI Responses endpoint; Chat Completions can be added similarly.
- `stream=True` requests are served as real Server-Sent Events (`text/event-stream`) with genuine token-by-token incremental deltas: `run_solution_architect_agent_stream` (in `agent_solution_architect.py`) consumes the LangChain agent via `astream_events(..., version="v2")` and forwards each `on_chat_model_stream` text delta as it is produced, including after any MCP tool call the agent makes along the way.
- **Tool call visibility (e.g. in LibreChat)**: when the agent calls `mslearn_mcp_search`, a short Markdown notice (`> 🔧 _Calling tool ..._` / `> ✅ _Tool ... completed._`) is injected directly into the streamed `content`, so any OpenAI-compatible client — including LibreChat, which only sees standard chat completion chunks and has no visibility into server-side tool execution — displays that a tool was used. Set `AGENT_STREAM_TOOL_NOTICES=false` to disable these notices and stream only the final answer text.
