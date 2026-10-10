# Native MAF reference worker (offline)

`native.py` supplies a native Agent factory plus the existing discovery descriptor
inside a typed definition. `app.py` is platform glue (combined <=30 nonblank lines).
`echo_client.py` is domain/model code, with genuine zero inference token usage.
`deployment.py` belongs to the operator. No proprietary registry/skills or
agent-owned HTTP/SSE code is required.

From this directory, with the runtime's optional integration installed:

```powershell
$env:NATIVE_WORKER_API_KEY = "<your-local-test-key>"
python -m uvicorn app:app --host 127.0.0.1 --port 8099
```

Send `x-api-key` with your configured key to `/v1/chat/completions`,
`/v1/responses`, `/v1/messages` or `/v1/models`. Model: `agentframework-echo`.
Set `stream=true` to invoke real native streaming. `/health/ready` is public,
read-only and contains only readiness. Use normal operator logging configuration.

The same native agent works independently: construct it with `create_agent`
and use `await agent.run("hello")`. There is no network/model credential needed.
Only the local HTTP authentication key is operator-supplied.

This is a **single-instance Python pilot**, not a production sandbox or
cross-language release. Keep one deployment per worker. Container/workload
identity, network and secret/MCP restrictions are platform responsibilities.
See [native agents](../../python/native-agents.md) for admission, input-profile,
usage, lifecycle and parity limits.
