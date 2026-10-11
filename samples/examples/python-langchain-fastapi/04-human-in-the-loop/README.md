# 04 — Human in the loop

This folder builds an approval-enabled LangGraph agent and shows two hosts.
`developer_app.py` is a small FastAPI implementation using LangGraph's native
interrupt values. `openai_responses_app.py` uses the runtime managed worker,
which adds authenticated OpenAI-compatible routes and shared conversation and
confirmation handling.

## From a custom API to the runtime

- **Keep:** the LangGraph agent and the rules that decide whether its search may
  run.
- **With your own API:** `developer_app.py` owns `/ask`, `/resume`, the
  checkpoint ID and the approve-or-reject request format. It resumes the graph
  after the user answers.
- **With the runtime:** `openai_responses_app.py` uses `LangGraphWorker` and an
  application `conversation_factory`. The application still supplies the graph,
  ticket resolver and search runner.
- **Handled by the runtime:** authenticated endpoints, conversation storage,
  confirmation command parsing, ticket ownership and ticket display.

The approval flow changes at this boundary. The direct API resumes the paused
graph. The runtime path stops the tool call, saves its exact arguments in a
ticket and runs the search from those arguments after `CONFIRM`.

The folder's `.env.sample` contains placeholders only; replace the OpenAI key
with your own local development key before starting the app.

This is the example the `humanapproval` domain of the runtime exists for, and the
only one here that shows an approval **spanning two HTTP requests**.
The runtime entrypoint returns typed runtime output, including native LangGraph
streaming. Ticket ownership, literal confirmation parsing and stored arguments
are handled by the shared conversation engine.

## The problem it solves

An OpenAI-compatible API answers every request. A turn therefore cannot hold
while a person decides.

The obvious implementation blocks the connection until somebody answers, which
fails as soon as the client times out. The obvious workaround drops the operation
and asks the user to repeat themselves, which loses the thing they were about to
approve. Neither is acceptable, and both are common.

Both hosts stop the search until a person approves it. The direct host lets the
developer own the full resume flow:

1. the model asks for the gated tool, and the graph **suspends**;
2. `/ask` returns the pending action without running it;
3. `/resume` passes the person's ordered decisions to LangGraph;
4. LangGraph resumes with the original arguments.

The runtime host uses the shared confirmation ticket flow. It declines the
suspended tool call, returns a ticket, and later parses `CONFIRM cfm-xxxx`
before the model sees that text. The confirmed operation runs from the ticket's
stored arguments; this runtime path does not resume the original graph.

In both modes, the model describes the operation but cannot change the arguments
after a person has approved them.

## Why a *search* is gated here

The agent is the one from `01-get-started`, unchanged except for the approval.
Its only tool is a Microsoft Learn search, and the honest reason to gate it is
**not** that reading is dangerous.

It is that calling the MCP server sends the user's question — which in an
enterprise is rarely generic — to a third party. Confirming that egress is a real
decision. The operation is classified `READ` and `MEDIUM` accordingly: the risk is
disclosure, not destruction, and saying so is more useful than inflating it.

The mechanism is the same one that would gate a send, a delete or a deployment.
Only the descriptor changes.

## What comes from the library, and what does not

| From `ygo74-agent-runtime-agents` and its security dependency | |
|---|---|
| `ConfiguredConfirmationPolicy` | decides whether an operation needs an approval |
| `ConfirmationTicket`, `InMemoryPendingConfirmationStore` | carry the operation, and its exact arguments, across two requests |
| `ConfirmationCommandParser` | reads `CONFIRM` / `CANCEL` before the model does |
| `PendingConfirmationRenderer` | renders what waits, and redacts ticket references found in retrieved content |
| `AgentDescriptorFactory`, `AdvertisedSecurity` | publish a descriptor derived from the authentication actually configured |

| From `ygo74-agent-runtime-langchain` | |
|---|---|
| `LangGraphSession` | runs the existing graph and translates its results/events to runtime contracts |
| `LangGraphWorker` | hosts the graph through managed, authenticated conversation routes |

| From this folder | |
|---|---|
| `conversation.py` | connects this graph's ticket resolver and confirmed search to the runtime conversation ports |
| `developer_agent.py` | builds the native graph without importing runtime packages |
| `developer_app.py` | shows the route, response shape, and manual LangGraph resume flow |

The runtime host reuses the agent instead of rebuilding its tools or graph. The
application adapter only decides how an interrupt becomes a ticket and how a
confirmed ticket runs the stored Microsoft Learn search arguments.

## A detail that is not a detail

`langgraph_approval.py` allows only `approve` and `reject`.

- `edit` is excluded because it lets the human change the arguments *after* the
  approval was granted, while the approval is recorded against the exact request
  they were shown. Running arguments nobody confirmed is a confirmation bypass
  wearing the costume of a feature.
- `respond` is excluded because its message is delivered to the model as a
  *successful* tool result. On an operation with side effects, a refusal would
  then be indistinguishable from the operation having happened.

## Running it

Use Python 3.12 or newer. The example calls OpenAI and Microsoft's public
Microsoft Learn MCP service, so configure a working OpenAI API key.

```powershell
cd samples/examples/python-langchain-fastapi/04-human-in-the-loop
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements-developer.txt
Copy-Item .env.sample .env
uvicorn developer_app:app --port 8080
```

This direct entrypoint has `POST /ask` and `POST /resume`. The developer owns
these routes, the response schema and the checkpoint identifier. `/ask` returns
the framework action requests when approval is needed; `/resume` accepts an
ordered list of `approve` or `reject` decisions and resumes the graph.

```powershell
Invoke-RestMethod -Method Post -Uri "http://localhost:8080/ask" `
  -ContentType "application/json" `
  -Body '{"conversation_id":"demo","question":"How do I expose a private AKS cluster to partners?"}'

Invoke-RestMethod -Method Post -Uri "http://localhost:8080/resume" `
  -ContentType "application/json" `
  -Body '{"conversation_id":"demo","decisions":[{"type":"approve"}]}'
```

For the runtime-hosted entrypoint, install `requirements.txt` instead and set
`PYTHONPATH` to the repository's `security`, `agents`, and `langchain` package
directories, as shown in `01-get-started`. Then run:

```powershell
uvicorn openai_responses_app:app --port 8080
```

It uses `LangGraphWorker` with an application `conversation_factory`. The
worker handles API-key authentication, caller and conversation partitioning,
confirmation command parsing, one-time ticket claims, and pending-ticket
rendering. The application supplies the graph, the ticket resolver and the
search runner.

> Port 8080, not 8000. If you point `OPENAI_API_BASE` at a local gateway, that
> gateway is very likely on 8000 — and an agent whose model endpoint is itself
> would be a short and confusing story.

Ask something that needs documentation through the runtime-hosted endpoint:

```powershell
curl -s http://localhost:8080/v1/chat/completions `
  -H "x-api-key: demo-key" -H "content-type: application/json" `
  -H "x-conversation-id: demo" `
  -d '{"model":"ai-solution-architect-hitl","messages":[{"role":"user","content":"How do I expose a private AKS cluster to partners?"}]}'
```

The first reply performs nothing and includes a ticket. A later `CONFIRM` runs
the search with the exact arguments saved on that ticket and returns the tool
result. This runtime path does not resume the original graph after confirmation.
The initial reply includes something like:

```text
Awaiting your confirmation - nothing has been changed yet:

- **Send this question to Microsoft Learn**
  - Query: expose private AKS cluster to partners
  - Reply `CONFIRM cfm-4f2a1c9b7e03` to approve, `CANCEL cfm-4f2a1c9b7e03` to decline.
```

Answer it, **in the same conversation**:

```powershell
curl -s http://localhost:8080/v1/chat/completions `
  -H "x-api-key: demo-key" -H "content-type: application/json" `
  -H "x-conversation-id: demo" `
  -d '{"model":"ai-solution-architect-hitl","messages":[{"role":"user","content":"CONFIRM cfm-4f2a1c9b7e03"}]}'
```

Now the search runs and its result is returned. `CANCEL` instead, and nothing is
sent — the ticket is consumed either way, so a declined operation cannot be
confirmed a moment later by repeating the identifier.

## Things to try

- Quote a ticket identifier from **another** conversation (change
  `x-conversation-id`). It is refused, and with the same wording as an identifier
  that never existed — distinguishing them would tell a guesser which ones are
  real.
- Reply `yes go ahead`. It is not an approval; it reaches the model as an ordinary
  message. The grammar is deliberately tiny, because an approval the model can
  reinterpret is not an approval.
- Ask something that makes the model want **two** searches. You get one ticket
  for each call; each command consumes only the ticket it names.
- Send an ordinary message while a ticket is pending. The runtime treats it as a
  new agent turn; the ticket remains available until it is answered or expires.
- Wait fifteen minutes before answering. The ticket has expired.

## What this example is not

The ticket store is `InMemoryPendingConfirmationStore`: **one process**. Behind
two workers, a ticket issued on one is unclaimable on the other, and a restart
loses every pending approval. A deployment needs a shared, atomic store behind the
same `PendingConfirmationStore` protocol — everything that makes a claim safe is
decided in the domain, not by the store.
