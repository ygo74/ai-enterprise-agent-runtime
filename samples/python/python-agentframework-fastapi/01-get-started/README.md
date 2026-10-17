# 01 — Develop a native MAF agent

This first example builds a normal Microsoft Agent Framework (MAF) agent and
runs it behind an application-owned FastAPI route. The app controls its own
request and response shape. The next example shows the boundary where the
runtime takes over standard endpoint hosting.

## From your own API to the runtime

- **Keep:** `native.py` builds a normal MAF `Agent`; `echo_client.py` supplies
  its offline chat client. The agent code has no runtime imports.
- **With your own API:** `developer_app.py` calls `await agent.run(question)`
  and returns `{"answer": ...}`. The application owns the route and response.
- **Handled by the runtime later:** standard endpoint formats, streaming,
  conversation history, authentication, discovery, readiness and shutdown.

The sample uses a deterministic local chat client, so it needs no model key or
external service. The developer-owned API uses only the MAF SDK and FastAPI. It
does not install the runtime package or write provider protocol and SSE code.

## Developer workflow

1. Build and run the native MAF agent with `developer_app.py`. At this stage,
   you only need the MAF SDK, FastAPI and your agent code.
2. Add or change the agent's instructions, model client and tools in
   `native.py` and `echo_client.py`. Keep these files free of runtime imports.
3. When the agent is ready to serve standard AI endpoints, continue with
   [native agent hosting](../04-native-agent/README.md).

This sample keeps these steps small. A real agent can use its normal MAF model
and tool types in place of the offline echo client.

## Run the developer-owned API

From this directory, install `requirements-developer.txt`, then start the app:

```powershell
cd samples/python/python-agentframework-fastapi/01-get-started
python -m pip install -r requirements-developer.txt
python -m uvicorn developer_app:app --host 127.0.0.1 --port 8098
```

```shell
curl http://127.0.0.1:8098/ask \
  -H 'content-type: application/json' \
  -d '{"question":"hello"}'
```

The response is owned by this app: `{"answer":"Echo: hello"}`.

This example focuses on native agent development. For standard provider
endpoints, worker-managed conversations, authentication, and discovery, use
[native agent hosting](../04-native-agent/README.md).
