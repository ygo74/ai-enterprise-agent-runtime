# Native LangGraph worker

This small offline example runs a real compiled LangGraph with a deterministic
`FakeListChatModel`. It demonstrates a trusted factory, `AgentDefinition`,
operator authentication and the managed HTTP worker without an API key from an
LLM provider or an external service.

Create a Python 3.12 environment, install `requirements.txt`, then run:

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

`native_agent.py` contains the trusted graph factory. The worker owns identity
and conversation partitioning, cache lifecycle, routes, discovery, readiness,
authentication and turn limits. This agent has no tools. If a graph adds tools,
the worker requires an explicit admission hook; tool declarations by themselves
do not grant execution rights. For domain ticket stores, authorization or
application-owned resources, pass an advanced `conversation_factory` as the Wiki
integration does.
