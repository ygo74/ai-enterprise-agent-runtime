# Native LangGraph worker

This small offline example runs one compiled LangGraph with a deterministic
`FakeListChatModel` through two entrypoints. `developer_app.py` is a direct
FastAPI route around the agent. `app.py` uses the runtime's `LangGraphWorker`,
`AgentDefinition`, operator authentication and managed HTTP lifecycle. Neither
path needs an API key from an LLM provider or an external service.

## From a custom API to the runtime

- **Keep:** `native_agent.py` builds the same LangGraph for both entrypoints.
- **With your own API:** `developer_app.py` owns `/ask`, calls the graph and
  chooses the response format.
- **With the runtime:** `app.py` gives the graph factory to `LangGraphWorker`.
- **Handled by the runtime:** authenticated endpoints, conversation IDs and
  cache, discovery, readiness, shutdown and turn limits.

This is the short path when the application does not need its own conversation
factory. The example graph has no tools. If you add tools, you must also provide
an admission policy for them.

Create a Python 3.12 environment and install `requirements-developer.txt` to run
the developer-owned API:

```shell
uvicorn developer_app:app --app-dir . --port 8122
```

```shell
curl http://127.0.0.1:8122/ask \
  -H 'content-type: application/json' \
  -d '{"question":"hello"}'
```

Install `requirements.txt` to run the runtime-hosted entrypoint:

```shell
uvicorn app:app --app-dir . --port 8123
```

The local key in `app.py` is for this example only. Query the OpenAI-compatible
surface with:

```shell
curl http://127.0.0.1:8123/v1/chat/completions \
  -H 'content-type: application/json' \
  -H 'x-api-key: local-demo-key' \
  -d '{"model":"offline-langgraph-demo","messages":[{"role":"user","content":"hello"}]}'
```

Both apps call the graph builder in `native_agent.py`. The developer route owns
its `/ask` route and response shape. The worker owns identity
and conversation partitioning, cache lifecycle, routes, discovery, readiness,
authentication and turn limits. This agent has no tools. If a graph adds tools,
the worker requires an explicit admission hook; tool declarations by themselves
do not grant execution rights. For domain ticket stores, authorization or
application-owned resources, pass an advanced `conversation_factory` as the Wiki
integration does.
