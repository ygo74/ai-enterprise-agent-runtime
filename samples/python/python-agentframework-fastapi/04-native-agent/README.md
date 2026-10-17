# 04 — Host a native MAF agent with the runtime

This example gives a native MAF `Agent` to `AgentFrameworkWorker`. The agent
factory remains separate from HTTP setup; the runtime owns endpoint formats,
streaming, authentication, conversations, discovery, readiness, and shutdown.

The deterministic echo client needs no model key or external service. The
worker is a single-instance Python pilot. It is not a production sandbox and
does not claim .NET/Java parity.

## Install and run

From this directory, install the sample requirements and set a local API key:

```powershell
python -m pip install -r requirements.txt
$env:NATIVE_WORKER_API_KEY = "<your-local-test-key>"
python -m uvicorn app:create_app --factory --host 127.0.0.1 --port 8099
```

The API key protects the agent endpoints; it is not a model credential.

## Send a request

```shell
curl http://127.0.0.1:8099/v1/responses \
  -H 'content-type: application/json' \
  -H 'x-api-key: <your-local-test-key>' \
  -d '{"model":"agentframework-echo","input":"hello"}'
```

The response contains `Echo: hello`. Set `"stream":true` to use native MAF
streaming. `GET /health/ready` is public and reports readiness without identity
or secret details.

`definition.py` contains the trusted factory reference and discovery descriptor.
`deployment.py` contains operator-owned authentication and identity settings.
The worker loads that trusted factory; request data cannot select a module or
agent.

See the [native agent guide](../../../../doc/python/native-agents.md) for tool
admission, input limits, conversations, approval, and worker lifecycle limits.
