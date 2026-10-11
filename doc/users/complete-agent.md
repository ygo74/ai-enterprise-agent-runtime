# Complete agent: LangChain with an approved MCP search

This walkthrough runs one coherent example: a LangChain solution architect
agent behind FastAPI. It uses API-key authentication, authenticated model
discovery, an MCP search tool, and a two-request approval flow. The search sends
the user's question to Microsoft's public Microsoft Learn MCP service, so the
example asks for permission before sending it.

The runnable source is
[`04-human-in-the-loop`](../../samples/examples/python-langchain-fastapi/04-human-in-the-loop/README.md).
Use that folder as the source of truth if package versions or code change.

## What this example includes

| Feature | How it appears | What you observe |
|---|---|---|
| LangChain agent | `solution_architect_agent.py` builds a LangChain agent and LangGraph checkpoint | The model can request Microsoft Learn search. |
| MCP tool | `mcp_mslearn_tool.py` calls the configured public MCP service | The user's question is sent externally only after approval. |
| Authentication | The HTTP adapter resolves `demo-key` to `demo-user` | Calls without the key are rejected. |
| Discovery | A descriptor is registered and authenticated `/v1/models` is enabled | The client can list `ai-solution-architect-hitl`. |
| Typed output | The entrypoint returns `AgentOutput((TextContent(...),))` | The runtime formats a normal provider response. |
| Conversation state | The conversation ID selects a checkpoint thread scoped by authenticated subject | A later request resumes the same suspended turn. |
| Human approval | A ticket stores the operation and exact tool arguments | The first request does not call the tool; `CONFIRM` or `CANCEL` answers later. |
| Safe configuration | `.env.sample` contains placeholders | The operator supplies the model key locally. |

## Limits of this example

This example uses `add_ai_endpoints` rather than the newer managed LangGraph
worker. The managed worker is demonstrated separately by the
[offline native LangGraph example](../../samples/examples/python-langchain-fastapi/06-native-langgraph/README.md);
that example has no tools or approval flow. Do not combine the two examples by
assuming they share the same application setup.

Streaming is disabled: the approval interaction spans separate HTTP requests
and returns complete messages. Tickets, turn bookkeeping, and LangGraph state
are held in process memory. Run one process only; production multi-worker use
needs shared atomic ticket storage and shared or durable graph checkpoints and
turn state. The MCP search service and model provider are external requirements.

## Prerequisites

- Python 3.12 or newer
- An OpenAI API key and permission to call the selected model
- Network access to the public Microsoft Learn MCP endpoint
- The packages listed in `requirements.txt`

## Install and configure

Run from the repository root:

```bash
cd samples/examples/python-langchain-fastapi/04-human-in-the-loop
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
cp .env.sample .env
```

Edit `.env` and replace `OPENAI_API_KEY` with your own key. Keep this file local
and do not commit it. The sample also sets the model and public MCP URL/tool
name; change those only to values supported by the example's MCP client.

## Start the agent

In the same directory, start the FastAPI app:

```bash
uvicorn openai_responses_app:app --host 127.0.0.1 --port 8080
```

The example listens on port 8080 and uses `demo-key` as its local API key.
`demo-key` is defined in the example source and is not suitable for a shared or
public deployment.

## Check discovery

In another terminal, list the registered model:

```bash
curl -sS http://127.0.0.1:8080/v1/models -H 'x-api-key: demo-key'
```

The result contains the ID `ai-solution-architect-hitl`. A missing or invalid
key should be rejected by authentication.

## Ask a question and review the operation

Use the same conversation ID for every request in this interaction:

```bash
curl -sS http://127.0.0.1:8080/v1/chat/completions \
  -H 'x-api-key: demo-key' \
  -H 'x-conversation-id: demo' \
  -H 'Content-Type: application/json' \
  -d '{"model":"ai-solution-architect-hitl","messages":[{"role":"user","content":"How do I expose a private AKS cluster to partners?"}]}'
```

When the agent needs documentation, the response says that it is waiting for
approval, shows the search query, and prints a ticket such as
`cfm-4f2a1c9b7e03`. Nothing has been sent to Microsoft Learn yet. If the agent
answers without requesting a search, it returns an ordinary assistant answer.

## Approve or cancel

Copy the ticket from the response. Replace the placeholder below with that
ticket ID, and keep the same API key and conversation ID:

```bash
curl -sS http://127.0.0.1:8080/v1/chat/completions \
  -H 'x-api-key: demo-key' \
  -H 'x-conversation-id: demo' \
  -H 'Content-Type: application/json' \
  -d '{"model":"ai-solution-architect-hitl","messages":[{"role":"user","content":"CONFIRM cfm-<ticket-id>"}]}'
```

The application parses this command before invoking the model, claims the
single-use ticket for the authenticated subject and conversation, then resumes
the suspended graph with the arguments already stored on the ticket. The search
runs and the agent returns an answer. Send `CANCEL cfm-<ticket-id>` to consume
the ticket without calling the search. A ticket expires after 15 minutes.

## Stop the service

Stop Uvicorn with `Ctrl+C`. The graph checkpoints and pending tickets are
in-memory, so stopping the process ends the example's conversation state.

For the individual runtime APIs, see [Human approval](human-approval.md),
[MCP](mcp.md), [Authentication and discovery](security-and-discovery.md), and
[Framework integrations](framework-integrations.md).
