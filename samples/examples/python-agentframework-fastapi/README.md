# Microsoft Agent Framework with FastAPI

This example uses one native Microsoft Agent Framework (MAF) agent in two ways.
`developer_app.py` is a small FastAPI app written in the usual MAF style.
`app.py` gives the same agent factory to the runtime worker.

## From your own API to the runtime

- **Keep:** `native.py` builds a normal MAF `Agent`; `echo_client.py` supplies
  its offline chat client. The agent code has no runtime imports.
- **With your own API:** `developer_app.py` calls `await agent.run(question)`
  and returns `{"answer": ...}`. The application owns the route and response.
- **With the runtime:** `app.py` connects the agent definition and operator
  settings to `AgentFrameworkWorker`.
- **Handled by the runtime:** OpenAI and Anthropic endpoint formats, streaming,
  conversation history, authentication, discovery, readiness and shutdown.

`definition.py` names the trusted agent factory. `deployment.py` contains
operator settings such as the API key and deployment identity. The runtime
integration converts MAF responses and updates to typed runtime output. The app
does not write provider protocol or SSE code.

The sample uses a deterministic local chat client, so it needs no model key or
external service. Dependencies for the developer-owned API and the runtime app
are listed separately.

## Developer workflow

1. Build and run the native MAF agent with `developer_app.py`. At this stage,
   you only need the MAF SDK, FastAPI and your agent code.
2. Add or change the agent's instructions, model client and tools in
   `native.py` and `echo_client.py`. Keep these files free of runtime imports.
3. When the agent is ready to serve standard AI endpoints, add its trusted
   factory to `definition.py` and operator settings to `deployment.py`.
4. Use `AgentFrameworkWorker` in `app.py`. The integration handles HTTP
   protocols, typed output, authentication and conversation lifecycle.

This sample keeps these steps small. A real agent can use its normal MAF model
and tool types in place of the offline echo client.

## Run the developer-owned API

From this directory, install `requirements-developer.txt`, then start the app:

```powershell
cd samples/examples/python-agentframework-fastapi
python -m pip install -r requirements-developer.txt
python -m uvicorn developer_app:app --host 127.0.0.1 --port 8098
```

```shell
curl http://127.0.0.1:8098/ask \
  -H 'content-type: application/json' \
  -d '{"question":"hello"}'
```

The response is owned by this app: `{"answer":"Echo: hello"}`.

## Run with the runtime worker

Install `requirements.txt` in an environment with the runtime packages
available. From this directory, install the requirements, then set the local
API key and start the worker:

```powershell
python -m pip install -r requirements.txt
$env:NATIVE_WORKER_API_KEY = "<your-local-test-key>"
python -m uvicorn app:create_app --factory --host 127.0.0.1 --port 8099
```

Send `x-api-key` with your configured key to `/v1/chat/completions`,
`/v1/responses`, `/v1/messages` or `/v1/models`. The model name is
`agentframework-echo`. Set `stream=true` to use native MAF streaming.

`/health/ready` is public and returns only readiness. The worker owns the HTTP
and conversation lifecycle. The API key protects these endpoints; it is not a
model credential.

This is a **single-instance Python pilot**, not a production sandbox or a
cross-language release. Keep one deployment per worker. Container identity,
network rules and secret access remain platform responsibilities. See
[native agents](../../../doc/python/native-agents.md) for tool admission, input limits,
usage, lifecycle and support limits.
