# Python LangChain + FastAPI Example (AI Solution Architect)

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
cd docs/examples/python-langchain-fastapi
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

## Environment

```powershell
$env:OPENAI_API_KEY="<your-openai-key>"
$env:OPENAI_MODEL="gpt-4o-mini"
$env:MSLEARN_MCP_URL="https://learn.microsoft.com/api/mcp"
$env:MSLEARN_MCP_TOOL="search"
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
uvicorn openai_responses_app:app --reload --port 8000
```

## Test Request

```powershell
$body = @{
  model = "gpt-4o-mini"
  input = "Design an enterprise AI solution architecture for RAG with governance and cost controls."
  metadata = @{
    request_id = "demo-architect-001"
    route_key = "ai-solution-architect"
  }
  stream = $false
} | ConvertTo-Json -Depth 10

Invoke-RestMethod -Method Post `
  -Uri "http://127.0.0.1:8000/v1/responses" `
  -ContentType "application/json" `
  -Body $body
```

## Notes

- The MCP tool call is implemented in `mcp_mslearn_tool.py` with `streamable-http` transport.
- If the MCP SDK is unavailable at runtime, the tool returns a deterministic fallback message that includes the intended MCP call details.
- This example is intentionally scoped to the OpenAI Responses endpoint; Chat Completions can be added similarly.
