# Use LangChain or Microsoft Agent Framework

The runtime keeps framework-specific dependencies in optional distributions.
Install the adapter for the framework your application uses, in addition to
the agents distribution and any HTTP extra.

## LangChain and LangGraph

From the repository root, install the integration into an isolated environment
with the example's requirements:

```bash
cd docs/examples/python-langchain-fastapi/01-get-started
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

Create `.env` from `.env.sample`, set `OPENAI_API_KEY`, and follow the example
README to start the server. It listens on port 8001 by default. Send a question
with:

```powershell
Invoke-RestMethod -Method Post `
  -Uri "http://127.0.0.1:8001/v1/responses" `
  -ContentType "application/json" `
  -Body '{"model":"gpt-5-chat","input":"Design an enterprise RAG architecture."}'
```

The example returns a Responses API result containing the agent's architecture
answer. It calls the Microsoft Learn MCP service when research is needed. See the
[LangChain guide](../../docs/python/langchain.md) for supported adapters and
event conversion.

## Microsoft Agent Framework

The Microsoft Agent Framework example is in
[`docs/examples/python-agentframework-fastapi/`](../../docs/examples/python-agentframework-fastapi/).
Its README explains setup and the API call. The example adapts SDK response and
stream updates to neutral runtime outputs; install the framework adapter only
when using this SDK. See the
[Agent Framework guide](../../docs/python/agentframework.md) for the supported
types and limitations.

## Native LangGraph worker

The runtime can also host a trusted native LangGraph factory through its managed
worker. The [offline worker example](../../docs/examples/python-langchain-fastapi/06-native-langgraph/README.md)
uses a deterministic fake model, so it needs no provider credentials. It has no
tools; a graph with tools needs an explicit admission hook. The worker handles
authentication, discovery, readiness, conversation cache, and shutdown.
