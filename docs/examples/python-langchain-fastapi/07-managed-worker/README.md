# 07 — Managed worker with LangGraph

This offline example hosts the same native LangGraph through two entrypoints.
`developer_app.py` is a small application-owned `/ask` API. The runtime entrypoint
uses the framework-neutral `ManagedAgentWorker` directly and supplies a
`conversation_factory` that binds LangGraph to the runtime conversation ports.
The fake model is deterministic and needs no provider key or network access.

## What changes when using the runtime

- **Keep:** `native_agent.py` builds the LangGraph. The same graph builder is
  used by both entrypoints.
- **With your own API:** `developer_app.py` owns `/ask`, calls the graph and
  returns an application response.
- **With the runtime:** `managed_worker_app.py` passes a `conversation_factory`
  to `ManagedAgentWorker`. The factory connects the graph session to the
  runtime's conversation interface.
- **Handled by the runtime:** authenticated endpoints, conversation caching
  and identity separation, readiness, shutdown and turn limits.

Use this lower-level setup when the application needs to add its own resources
or conversation services. For a simpler LangGraph setup, start with
[`06-native-langgraph`](../06-native-langgraph/README.md).

## Run the developer-owned API

Use Python 3.12 or newer:

```shell
cd docs/examples/python-langchain-fastapi/07-managed-worker
python -m venv .venv
source .venv/bin/activate
pip install -r requirements-developer.txt
uvicorn developer_app:app --port 8122
```

```shell
curl http://127.0.0.1:8122/ask \
  -H 'content-type: application/json' \
  -d '{"question":"hello"}'
```

This entrypoint owns the route, request model, graph invocation and response.

## Run with `ManagedAgentWorker`

Install `requirements.txt` in the runtime repository environment. From this
example directory, add the source checkout's Python packages to `PYTHONPATH`:

```shell
export PYTHONPATH="$PWD/../../../../packages/python/security:$PWD/../../../../packages/python/agents:$PWD/../../../../packages/python/langchain:$PYTHONPATH"
uvicorn managed_worker_app:app --port 8123
```

The example key is `local-demo-key`:

```shell
curl http://127.0.0.1:8123/v1/chat/completions \
  -H 'content-type: application/json' \
  -H 'x-api-key: local-demo-key' \
  -d '{"model":"managed-langgraph-demo","messages":[{"role":"user","content":"hello"}]}'
```

The `conversation_factory` receives the verified principal and conversation
handle, builds a server-side `AgentFactoryContext`, then returns an
`AgentConversation` containing the native graph session and application runtime.
The worker owns authenticated routes, conversation caching and partitioning,
readiness, shutdown and turn limits. This is the lower-level extension point for
applications that need to add their own conversation resources or domain
services. The example graph has no tools; a tool-enabled application must also
enforce its own admission and authorization policy.

For the shorter framework-specific setup, see
[`06-native-langgraph`](../06-native-langgraph/README.md), which uses the
`LangGraphWorker` facade. Both entrypoints ultimately use the same managed
worker services.
