# 05 — Compose MAF with `ManagedAgentWorker`

This offline example uses the framework-neutral `ManagedAgentWorker` directly
and supplies a `conversation_factory` that binds each conversation to a native
MAF session. Use this lower-level entry point when the application needs to
compose its own conversation resources. For the simpler MAF adapter, see
[native agent hosting](../04-native-agent/README.md).

## Run

From this directory:

```powershell
python -m pip install -r requirements.txt
python -m uvicorn managed_worker_app:app --host 127.0.0.1 --port 8105
```

The local API key is `managed-demo-key`:

```shell
curl http://127.0.0.1:8105/v1/chat/completions \
  -H 'content-type: application/json' \
  -H 'x-api-key: managed-demo-key' \
  -d '{"model":"managed-maf-echo","messages":[{"role":"user","content":"hello"}]}'
```

The response contains `Echo: hello`. The deterministic local MAF client makes
no model requests. The worker still owns authentication, conversation cache,
readiness, and shutdown; this process-local sample does not provide durable or
multi-replica state.
