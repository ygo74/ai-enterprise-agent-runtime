# Require a human decision before a tool call

Human approval is useful when a tool call needs a person's decision. For HTTP,
the first request must finish while that person decides, so the agent returns a
single-use ticket and resumes the suspended operation in a later request.

## Run the example

Requirements: Python 3.12+, an OpenAI API key, and access to the Microsoft Learn
MCP service. From the repository root, run:

```bash
cd samples/examples/python-langchain-fastapi/04-human-in-the-loop
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

Copy `.env.sample` to `.env`, set `OPENAI_API_KEY`, then start the app:

```bash
uvicorn openai_responses_app:app --port 8080
```

## Ask and approve

In another terminal, send a question. The example's API key is `demo-key` and
the conversation ID is `demo`:

```bash
curl -sS http://127.0.0.1:8080/v1/chat/completions \
  -H 'x-api-key: demo-key' \
  -H 'x-conversation-id: demo' \
  -H 'Content-Type: application/json' \
  -d '{"model":"ai-solution-architect-hitl","messages":[{"role":"user","content":"How do I expose a private AKS cluster to partners?"}]}'
```

The response explains that the question will be sent to Microsoft Learn and
includes a `CONFIRM cfm-...` command. Copy that exact ticket into a second
request, preserving both the API key and conversation ID:

```bash
curl -sS http://127.0.0.1:8080/v1/chat/completions \
  -H 'x-api-key: demo-key' \
  -H 'x-conversation-id: demo' \
  -H 'Content-Type: application/json' \
  -d '{"model":"ai-solution-architect-hitl","messages":[{"role":"user","content":"CONFIRM cfm-<ticket-id-from-first-response>"}]}'
```

The agent performs the approved search and returns its answer. Use `CANCEL`
instead to decline; no search runs. Tickets expire after 15 minutes, can be
claimed once, and belong to the authenticated subject and conversation.

This example stores tickets and graph checkpoints in memory. It is a single
process demonstration; a multi-worker deployment needs shared atomic ticket
storage and durable or shared graph state. Streaming is disabled because this
approval flow finishes one request before continuing in another. See
[Human-in-the-loop approval](../../doc/python/human-in-the-loop.md) for the
policy and storage contracts.
