# 02-get-started-maf: Python Microsoft Agent Framework + FastAPI (AI Solution Architect)

This example implements the **exact same** AI Solution Architect agent as
[`python-langchain-fastapi/01-get-started`](../../python-langchain-fastapi/01-get-started/), but built with
**Microsoft Agent Framework (MAF)** instead of LangChain, and exposed through the same
`ygo74.agent_runtime` library.

Its purpose is to prove that `ygo74.agent_runtime` is **not tied to any particular agent framework**:
only the technology used to build the agent changes (business logic), the endpoint-exposure code stays a
one-liner using the library.

| | 01-get-started (LangChain) | 02-get-started-maf (this example) |
| --- | --- | --- |
| Agent framework | LangChain (`create_agent` / `AgentExecutor`) | Microsoft Agent Framework (`Agent` via `OpenAIChatClient.as_agent`) |
| MCP tool wrapper | `langchain.tools.tool` decorator | Plain Python `async def` function (schema inferred from type hints/docstring) |
| Wiring in `openai_responses_app.py` | `create_langchain_agent_entrypoint(build_solution_architect_agent)` | `create_agent_framework_entrypoint(build_solution_architect_agent)` |
| Endpoint exposure, streaming, tool-call notices | `ygo74.agent_runtime` (identical) | `ygo74.agent_runtime` (identical) |

Microsoft Agent Framework already ships its own way of exposing OpenAI-compatible endpoints, but as of
today that hosting capability is only documented for .NET
([`Microsoft.Agents.AI.Hosting.OpenAI`](https://learn.microsoft.com/en-us/agent-framework/integrations/openai-endpoints?pivots=programming-language-csharp)).
On Python, the framework only ships the **client** side (`OpenAIChatClient`/`OpenAIChatCompletionClient`
with `base_url=...` to *call* any OpenAI-compatible endpoint). `ygo74.agent_runtime` fills that gap for
Python MAF agents exactly the same way it does for LangChain agents.

## Files

- `openai_responses_app.py`: FastAPI app. Wires `build_solution_architect_agent` into
  `add_ai_endpoints` via `create_agent_framework_entrypoint` -- no endpoint/streaming plumbing here.
- `agent_solution_architect.py`: **Business logic only** -- model, tools, instructions for the Solution
  Architect agent, built with `agent_framework.openai.OpenAIChatClient(...).as_agent(...)`.
- `mcp_mslearn_tool.py`: MCP tool wrapper to query Microsoft Learn MCP, as a plain async function.
- `requirements.txt`: Example dependencies.

### Why is there so little "endpoint" code here?

All the technical concerns that are the same for *any* agent -- normalizing input, extracting the final
answer text, real token-by-token streaming, and inline tool-call notices for chat UIs (e.g. LibreChat) --
are implemented once in the library as `ygo74.agent_runtime.create_agent_framework_entrypoint`. This
adapter is written entirely against duck-typed attributes (`agent.run(...)`, `response.text`,
`update.contents`, `content.type`) and never imports `agent_framework` itself, so it works with any object
respecting that same shape. Agent authors only write a `build_my_agent()` factory and pass it to that
helper.

## Prerequisites

- Python 3.11+
- OpenAI API key (or any OpenAI-compatible endpoint via `OPENAI_API_BASE`)
- Optional MCP auth:
  - `MSLEARN_MCP_API_KEY` + optional `MSLEARN_MCP_API_KEY_HEADER`
  - or `MSLEARN_MCP_BEARER_TOKEN`

## Install

```powershell
cd docs/examples/python-agentframework-fastapi/02-get-started-maf
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

Optional keys are prefilled in `.env.sample`. Note that Microsoft Agent Framework's `OpenAIChatClient`
reads `OPENAI_BASE_URL` by default (LangChain's `ChatOpenAI` reads the legacy `OPENAI_API_BASE` name) --
this example passes `OPENAI_API_BASE` explicitly to `OpenAIChatClient(base_url=...)` in
`agent_solution_architect.py` so the same `.env` convention works across both examples.

`ygo74` package source is in this repo, so include it in `PYTHONPATH` while running the example:

```powershell
$env:PYTHONPATH="../../..\packages/python"
```

## Run

```powershell
# From docs/examples/python-agentframework-fastapi/02-get-started-maf
python -m uvicorn openai_responses_app:app --reload --port 8002
```

## SDK Compatibility Client

Use the same compatibility client pattern as the LangChain example:

```powershell
# From docs/examples/python-agentframework-fastapi/02-get-started-maf
python sdk_compat_client.py --base-url http://127.0.0.1:8002 --skip-anthropic
```

Run a single specific check, optionally with real streaming:

```powershell
python sdk_compat_client.py --base-url http://127.0.0.1:8002 --test-openai-chat-completions --enable-stream
python sdk_compat_client.py --base-url http://127.0.0.1:8002 --test-openai-responses --enable-stream
```

## Notes

- The MCP tool call is implemented in `mcp_mslearn_tool.py` with `streamable-http` transport, reusing the
  same `MSLearnMCPClient` logic as the LangChain example -- only the tool wrapper (plain function vs
  `@langchain.tools.tool`) differs.
- `stream=True` requests are served as real Server-Sent Events (`text/event-stream`) with genuine
  token-by-token incremental deltas: `create_agent_framework_entrypoint` (in `ygo74.agent_runtime`)
  iterates `agent.run(user_input, stream=True)` and forwards each `AgentResponseUpdate.text` delta as it
  is produced, including after any MCP tool call the agent makes along the way.
- **Tool call visibility (e.g. in LibreChat)**: when the agent calls `mslearn_mcp_search`, a short
  Markdown notice (`> 🔧 _Calling tool ..._` / `> ✅ _Tool ... completed._`) is injected directly into the
  streamed `content`, exactly like the LangChain example. Set `AGENT_STREAM_TOOL_NOTICES=false` to disable
  these notices and stream only the final answer text.
