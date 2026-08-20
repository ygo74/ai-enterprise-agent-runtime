# 04-human-in-the-loop: Python LangChain + FastAPI (Tool Approval In Chat)

This example gates every call to the agent's Microsoft Learn research tool
behind **explicit user approval**, using LangChain's
[`HumanInTheLoopMiddleware`](https://docs.langchain.com/oss/python/langchain/human-in-the-loop),
and delivers that approval through the **standard chat protocol** so it works
with existing chatbot UIs (LibreChat, Open WebUI, ...):

- The agent ends its turn by asking for authorization as a normal assistant
  message.
- The user answers in the chat (`oui`, `non`, `modifie: ...`).
- The server resumes the paused tool call from the execution state stored
  **under `X-Conversation-ID`**.

No custom approval endpoint is required. Everything goes through the same
`/v1/responses` or `/v1/chat/completions` call.

## How it works

1. The client calls `/v1/responses` (or `/v1/chat/completions`) and sends
   `X-Conversation-ID`.
2. The FastAPI app reads `X-Conversation-ID` and uses it as the LangGraph
   `thread_id` (checkpoint key).
3. If the agent decides to call `mslearn_mcp_search`, the middleware interrupts
   the graph *before* execution and the checkpointer persists the paused state.
   The turn ends with `status: "awaiting_approval"` and an assistant message
   asking for authorization.
4. The user replies in the same conversation with the same
   `X-Conversation-ID`.
5. The server maps that reply to an `approve`, `edit`, or `reject` decision and
   resumes the paused run. An unrecognized reply re-asks instead of guessing.

This keeps protocol compatibility with chat/completions and responses while
remaining stateful per conversation on the server.

## Files

- `openai_responses_app.py`: FastAPI app — the standard OpenAI-compatible
  endpoints via `add_ai_endpoints`. A request middleware captures
  `X-Conversation-ID` and binds it to the LangGraph `thread_id`.
- `agent_solution_architect.py`: `SolutionArchitectAgent` — builds the
  `create_agent(...)` graph with `HumanInTheLoopMiddleware` gating
  `mslearn_mcp_search`, plus `ChatApprovalParser` (chat reply -> decision) and
  `ApprovalPrompt` (approval question rendering) over an `InMemorySaver`
  checkpointer shared across requests.
- `mcp_mslearn_tool.py`: MCP tool wrapper to query Microsoft Learn MCP (same as 01-get-started).
- `requirements.txt`: Example dependencies (requires `langchain>=1.0` for `create_agent` + middleware).

## Prerequisites

- Python 3.11+
- OpenAI API key
- Optional MCP auth:
  - `MSLEARN_MCP_API_KEY` + optional `MSLEARN_MCP_API_KEY_HEADER`
  - or `MSLEARN_MCP_BEARER_TOKEN`

## Install

```powershell
cd docs/examples/python-langchain-fastapi/04-human-in-the-loop
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

Required key: `OPENAI_API_KEY`.

`ygo74` package source is in this repo, so include it in `PYTHONPATH` while running the example:

```powershell
$env:PYTHONPATH="../../..\packages/python"
```

## Run

```powershell
# From docs/examples/python-langchain-fastapi/04-human-in-the-loop
python -m uvicorn openai_responses_app:app --reload --port 8001
```

## Walkthrough

### 1. Ask a question that requires the research tool

```powershell
$conversationId = "librechat-conv-42"

$body = @{
  model = "gpt-4o-mini"
  input = "Design an enterprise AI architecture for RAG with governance and cost controls."
  metadata = @{
    request_id = "demo-hitl-001"
    route_key = "ai-solution-architect-hitl"
  }
  stream = $false
} | ConvertTo-Json -Depth 10

$response = Invoke-RestMethod -Method Post `
  -Uri "http://127.0.0.1:8001/v1/responses" `
  -Headers @{ "X-Conversation-ID" = $conversationId } `
  -ContentType "application/json" `
  -Body $body

$response.output
```

The turn ends with an approval request rendered as a normal assistant message:

```json
{
  "role": "assistant",
  "content": "Je dois utiliser un outil avant de continuer. Autorisez-vous cet appel ?\n\n- `mslearn_mcp_search` avec {'query': 'RAG governance cost controls Azure'}\n\nRepondez `oui` pour approuver, `non` pour refuser, ou `modifie: <nouvelle requete>` pour ajuster les arguments.",
  "status": "awaiting_approval",
  "thread_id": "librechat-conv-42",
  "pending_actions": [
    {
      "name": "mslearn_mcp_search",
      "arguments": { "query": "RAG governance cost controls Azure" },
      "description": "Tool execution pending approval\n\nTool: mslearn_mcp_search\nArgs: {...}"
    }
  ]
}
```

### 2. Approve (or reject, or edit) from the chat

```powershell
$body = @{
  model = "gpt-4o-mini"
  input = "oui"
  metadata = @{
    request_id = "demo-hitl-002"
    route_key = "ai-solution-architect-hitl"
  }
  stream = $false
} | ConvertTo-Json -Depth 10

Invoke-RestMethod -Method Post `
  -Uri "http://127.0.0.1:8001/v1/responses" `
  -Headers @{ "X-Conversation-ID" = $conversationId } `
  -ContentType "application/json" `
  -Body $body
```

The server resumes the paused run stored under
`X-Conversation-ID=librechat-conv-42`, executes `mslearn_mcp_search`, and
returns the final answer with `status: "completed"`.

Accepted replies:

|Reply|Decision|
|---|---|
|`oui`, `ok`, `yes`, `approve`, `valide`, `go`|`approve` — the tool runs|
|`non`, `no`, `refuse`, `annule`, `stop`|`reject` — the tool is skipped and the reply is sent to the model as the reason|
|`modifie: <nouvelle requete>`|`edit` — the tool runs with the rewritten `query`|
|anything else|the agent re-asks instead of guessing|

## LibreChat custom endpoint example

Use your custom endpoint headers to provide identity + conversation context:

```yaml
endpoints:
  custom:
    - name: 'mon-agent-hitl'
      apiKey: '${AGENT_API_KEY}'
      baseURL: 'https://mon-microservice/v1'
      headers:
        Content-Type: 'application/json'
        Authorization: 'Bearer {{LIBRECHAT_OPENID_TOKEN}}'
        X-User-ID: '{{LIBRECHAT_USER_ID}}'
        X-User-Email: '{{LIBRECHAT_USER_EMAIL}}'
        X-Conversation-ID: '{{LIBRECHAT_BODY_CONVERSATIONID}}'
        X-Parent-Message-ID: '{{LIBRECHAT_BODY_PARENTMESSAGEID}}'
        X-Message-ID: '{{LIBRECHAT_BODY_MESSAGEID}}'
```

In this example implementation, `X-Conversation-ID` is used as the checkpoint
key (`thread_id`), so the user's `oui` / `non` / `modifie: ...` reply resumes
the exact paused tool call for that conversation.

## Notes

- This example is intentionally non-streaming (`stream=True` is not handled
  specially), since pausing a token stream mid-flight is out of scope here —
  see [01-get-started](../01-get-started/README.md) for a streaming example.
- `InMemorySaver` is process-local and non-persistent: restarting the server
  loses any paused conversation. Swap it for a persistent LangGraph
  checkpointer (`AsyncPostgresSaver`, `MongoDBSaver`, ...) in production.
- `ChatApprovalParser` uses an explicit keyword list on purpose: an
  unrecognized reply never falls through to an implicit approval.
- Discovery (`GET /v1/models`) and invocation share the same
  `agent_descriptor`/`add_ai_endpoints` wiring as every other example in this
  folder — HITL only changes what happens *inside* the entrypoint.

## Troubleshooting: "the agent never resumes / always re-asks"

Both `openai_responses_app.py` and `agent_solution_architect.py` log at
`INFO` level (via the standard `logging` module) every step of thread
resolution and interrupt detection. Run the server and watch the console for
these lines across the two requests (the question, then the reply):

```text
capture_request_headers: POST /v1/responses x-conversation-id='...'
_resolve_thread_id: using X-Conversation-ID header thread_id='...'
solution_architect_entrypoint: request_id=... thread_id='...' extracted_input='...'
_pending_actions: thread_id='...' checkpoint_id=... next=(...) interrupt_count=...
run_turn: thread_id='...' has N pending action(s); resuming instead of starting a new turn
_resume_turn: thread_id='...' reply='...' parsed_decision=...
```

Most common root causes, in order of likelihood:

1. **`thread_id` differs between the two calls.** Compare the
   `x-conversation-id` / `thread_id` value logged on the first call (the one
   that ends with `awaiting_approval`) against the value logged on the
   second call (the reply). If they differ, the client isn't resending the
   same `X-Conversation-ID` — check the chat client's header templating (some
   clients only populate a conversation id *after* the first response, so the
   very first turn of a brand-new conversation may go out with an empty or
   different id than the follow-up turn).
2. **`interrupt_count=0` on the resume call even though `thread_id` matches.**
   This means the checkpoint for that thread has no paused state anymore —
   typically because the server process restarted in between (e.g.
   `uvicorn --reload` restarting after a code edit) and wiped the process-local
   `InMemorySaver`. Use a persistent checkpointer if this needs to survive
   restarts.
3. **`parsed_decision=None` in `_resume_turn`.** The `thread_id` and pending
   state were found correctly, but `ChatApprovalParser` didn't recognize the
   reply text — the log line prints the raw `reply` that failed to match; add
   the phrase to `ChatApprovalParser.APPROVALS` / `REJECTIONS` if it's a
   legitimate synonym.