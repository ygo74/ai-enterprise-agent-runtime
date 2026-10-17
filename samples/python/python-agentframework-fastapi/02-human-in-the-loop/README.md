# 02 — Human approval for a MAF tool

This example puts an approval step in front of a MAF tool that records a local
note. MAF requests approval before it calls the function; the runtime's
`AgentFrameworkSession` resolves that native request. The FastAPI worker uses a
ticket so approval can happen in a later HTTP turn. The ticket stores the exact
tool arguments, and the runner applies the note only after `CONFIRM`.

This is the MAF ticket bridge. It declines the suspended call to MAF and runs
the approved operation from the ticket; it does not resume MAF's suspended run.
The example keeps the result in process memory and needs an OpenAI API key.

## Install and run

```powershell
python -m pip install -r requirements.txt
$env:OPENAI_API_KEY = "<your-openai-key>"
python -m uvicorn approval_worker:app --host 127.0.0.1 --port 8102
```

The local API key is `local-demo-key`. Send a request and retain the returned
conversation ID and confirmation ticket:

```shell
curl http://127.0.0.1:8102/v1/responses \
  -H 'content-type: application/json' \
  -H 'x-api-key: local-demo-key' \
  -H 'x-conversation-id: demo-1' \
  -d '{"model":"maf-approval-demo","input":"Write a note saying the maintenance window starts at 18:00."}'
```

The response displays the pending action and a ticket such as `cfm-...`. In a
second turn, replace the input with `CONFIRM <ticket-id>` to record the exact
note shown in the ticket. Use `CANCEL <ticket-id>` to discard it. The example
requires authentication and separates ticket ownership by user and
conversation.

For operation classification, policy choices, and the runtime's shared
approval behavior, see [human approval](../../../../doc/python/human-in-the-loop.md)
and [native MAF agents](../../../../doc/python/native-agents.md).
