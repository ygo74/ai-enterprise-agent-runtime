# 04 — Human in the loop

An OpenAI-compatible agent that will not call its tool until a person says so.

This is the example the `humanapproval` domain of the runtime exists for, and the
only one here that shows an approval **spanning two HTTP requests**.

## The problem it solves

An OpenAI-compatible API answers every request. A turn therefore cannot hold
while a person decides.

The obvious implementation blocks the connection until somebody answers, which
fails as soon as the client times out. The obvious workaround drops the operation
and asks the user to repeat themselves, which loses the thing they were about to
approve. Neither is acceptable, and both are common.

What this example does instead:

1. the model asks for the gated tool, and the graph **suspends**;
2. the turn ends **having changed nothing**, and the reply says what is waiting
   and how to answer it;
3. the person replies `CONFIRM cfm-xxxx` in a later request;
4. that text is read by a literal parser **before the model sees it**, the ticket
   is claimed, and the suspended graph resumes from the arguments stored on the
   ticket.

The property worth stating twice: the model describes the operation, then plays
no part in running it. It cannot change the arguments between the description and
the execution, because they never come back through it.

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

| From `ygo74-agent-runtime` | |
|---|---|
| `ConfiguredConfirmationPolicy` | decides whether an operation needs an approval |
| `ConfirmationTicket`, `InMemoryPendingConfirmationStore` | carry the operation, and its exact arguments, across two requests |
| `ConfirmationCommandParser` | reads `CONFIRM` / `CANCEL` before the model does |
| `PendingConfirmationRenderer` | renders what waits, and redacts ticket references found in retrieved content |
| `AgentDescriptorFactory`, `AdvertisedSecurity` | publish a descriptor derived from the authentication actually configured |

| From this folder | |
|---|---|
| `langgraph_approval.py` | the bridge to LangGraph's interrupts |

The bridge stays here on purpose. The library owns *whether* an operation needs an
approval and *what* a person is shown; how a particular framework suspends a call
is that framework's business, and a library that knew would have to know all of
them.

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

```powershell
cd docs/examples/python-langchain-fastapi/04-human-in-the-loop
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.sample .env    # then fill OPENAI_API_KEY
uvicorn openai_responses_app:app --port 8080
```

> Port 8080, not 8000. If you point `OPENAI_API_BASE` at a local gateway, that
> gateway is very likely on 8000 — and an agent whose model endpoint is itself
> would be a short and confusing story.

Ask something that needs documentation:

```powershell
curl -s http://localhost:8080/v1/chat/completions `
  -H "x-api-key: demo-key" -H "content-type: application/json" `
  -H "x-conversation-id: demo" `
  -d '{"model":"ai-solution-architect-hitl","messages":[{"role":"user","content":"How do I expose a private AKS cluster to partners?"}]}'
```

The reply performs nothing and ends with something like:

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

Now the search runs and the architect answers. `CANCEL` instead, and nothing is
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
- Ask something that makes the model want **two** searches. You get two tickets,
  and confirming one does not run the other: the turn resumes only once every
  suspended call has an answer. A ticket per operation would be theatre if one of
  them approved the rest.
- Send an ordinary message while something is pending. The question is repeated
  rather than dropped — starting a new turn would abandon the operation the person
  is still being asked about.
- Wait fifteen minutes before answering. The ticket has expired.

## What this example is not

The ticket store is `InMemoryPendingConfirmationStore`: **one process**. Behind
two workers, a ticket issued on one is unclaimable on the other, and a restart
loses every pending approval. A deployment needs a shared, atomic store behind the
same `PendingConfirmationStore` protocol — everything that makes a claim safe is
decided in the domain, not by the store.
