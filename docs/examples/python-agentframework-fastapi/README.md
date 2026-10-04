# Microsoft Agent Framework + FastAPI (offline)

Python 3.12+. This example constructs **real** `AgentResponse`,
`AgentResponseUpdate`, `Message`, and `Content` objects from Microsoft Agent
Framework 1.18. It does not perform inference or require credentials. The
`HostingFactory` exposes all three runtime surfaces plus model discovery.
Anonymous access is intentional for local demonstration only.

This no-model producer truthfully reports zero input/output/total model tokens
through the SDK fixture: it never performs inference. Final responses carry SDK
`usage_details`; streams emit usage before answer content. This is producer-owned
knowledge, not a runtime default or a tokenization estimate. Missing optional
usage breakdowns remain unknown.

From this directory, after installing the released distributions:

```powershell
python -m pip install -r requirements.txt
python -m uvicorn app:app --host 127.0.0.1 --port 8000
```

For development, from the repository root:

```powershell
python -m pip install -e ".\packages\python\security" -e ".\packages\python\agents[http]" -e ".\packages\python\agentframework"
python -m uvicorn app:app --app-dir ".\docs\examples\python-agentframework-fastapi" --host 127.0.0.1 --port 8000
```

Invoke without streaming:

```powershell
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/v1/responses -ContentType application/json -Body '{"model":"agentframework-echo","input":"hello"}'
```

Streaming (use `curl.exe`, not the PowerShell alias):

```powershell
curl.exe -N http://127.0.0.1:8000/v1/responses -H "Content-Type: application/json" -d '{\"model\":\"agentframework-echo\",\"input\":\"hello\",\"stream\":true}'
```

Expected answer: `Echo: hello`. Also available: `/v1/chat/completions`,
`/v1/messages`, and `/v1/models`.

Offline tests from the root (pytest and httpx must be installed):

```powershell
python -m pytest ".\tests\integration\python\test_agentframework_output_adapter.py" ".\docs\examples\python-agentframework-fastapi\test_agentframework_fastapi_example.py" -q
```

See the [integration guide](../../python/agentframework.md) for actual configured
SDK agent loops, developer-controlled conversion outcomes, and limitations.
