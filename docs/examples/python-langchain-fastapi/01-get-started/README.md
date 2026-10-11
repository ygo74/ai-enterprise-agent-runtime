# 01-get-started: Python LangChain + FastAPI (AI Solution Architect)

This example builds one **AI Solution Architect** LangChain agent and shows two
ways to host it:

- `developer_app.py` is the developer-owned FastAPI API. It uses LangChain and
  returns the developer's own `{"answer": ...}` response shape.
- `openai_responses_app.py` gives the same agent to the runtime `HostingFactory`,
  which exposes OpenAI Responses and Chat Completions.

The agent uses the Microsoft Learn MCP tool at
`https://learn.microsoft.com/api/mcp` in both modes.

## From a custom API to the runtime

- **Keep:** `solution_architect_graph.py` builds the LangChain agent and its
  MCP tool. Both entrypoints use this builder.
- **With your own API:** `developer_app.py` calls `agent.ainvoke()` and returns
  the application's `{"answer": ...}` response.
- **With the runtime:** `agent_solution_architect.py` adapts LangChain results
  and stream events to runtime output. `openai_responses_app.py` registers the
  OpenAI endpoints with `HostingFactory`.
- **Handled by the runtime:** endpoint protocols, streaming transport and
  discovery. This example still keeps a small adapter because it selects which
  graph events become user-visible output.

## Files

- `developer_app.py`: custom `/ask` FastAPI route without runtime imports.
- `openai_responses_app.py`: runtime-hosted OpenAI-compatible endpoints.
- `solution_architect_graph.py`: shared native LangChain agent construction.
- `agent_solution_architect.py`: runtime result and stream conversion.
- `mcp_mslearn_tool.py`: MCP tool wrapper to query Microsoft Learn MCP.
- `requirements.txt`: dependencies for the runtime entrypoint.
- `requirements-developer.txt`: dependencies for the developer-owned entrypoint.
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

For the developer-owned entrypoint, install only its framework requirements:

```powershell
pip install -r requirements-developer.txt
```

For the runtime entrypoint, `requirements.txt` installs the independent agents
and LangChain integration distributions. When using this repository's source,
include those packages in `PYTHONPATH`:

```powershell
$env:PYTHONPATH="..\..\..\..\packages\python\security;..\..\..\..\packages\python\agents;..\..\..\..\packages\python\langchain"
```

## Run

Run the developer-owned API without the runtime:

```powershell
python -m uvicorn developer_app:app --reload --port 8001
```

It accepts a small application-owned request and response:

```powershell
Invoke-RestMethod -Method Post `
  -Uri "http://127.0.0.1:8001/ask" `
  -ContentType "application/json" `
  -Body '{"question":"Design an enterprise RAG architecture with governance and cost controls."}'
```

Run the same native agent through runtime endpoints:

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
- `solution_architect_graph.py` contains the agent construction shared by both entrypoints. The direct API owns its route and response; the runtime entrypoint owns protocol mapping, typed output conversion, discovery and endpoint registration.
- Endpoint registration uses `HostingFactory`; the example allows anonymous requests, matching its explicit `AuthenticationPolicy.anonymous()` configuration.
- `stream=True` requests are served as real Server-Sent Events (`text/event-stream`) with genuine token-by-token incremental deltas: `run_solution_architect_agent_stream` (in `agent_solution_architect.py`) consumes the LangChain agent via `astream_events(..., version="v2")` and forwards each `on_chat_model_stream` text delta as it is produced, including after any MCP tool call the agent makes along the way.
- **Tool call visibility (e.g. in LibreChat)**: the developer's `astream_events`
  loop chooses tool starts/ends to expose as typed `Notification` contents.
  The runtime renders these short Markdown notices in streaming only; they are
  not assistant answer deltas and never contaminate non-streaming answers.
  Set `AGENT_STREAM_TOOL_NOTICES=false` to suppress them. Other native events
  are selected or ignored by developer code, not blindly forwarded.
- Native LangChain answers/events are converted through the optional integration
  to `AgentOutput`/`AgentStreamEvent`; no handler builds OpenAI wire output.
