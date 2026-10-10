# ygo74 Agent Runtime: Microsoft Agent Framework integration

Native execution binding and typed final-result/incremental-output adapters for Microsoft Agent Framework
Python. Requires Python 3.12+, `ygo74-agent-runtime-agents` 1.x and
`agent-framework-core` 1.18.x (unified `Content` API).

```python
from agent_framework import AgentResponse, Content, Message
from ygo74.agent_runtime.integrations.agentframework import AgentFrameworkOutputAdapter

response = AgentResponse(messages=Message("assistant", [Content.from_text("Hello")]))
converted = AgentFrameworkOutputAdapter().convert(response)
output = converted.output
```

Inspect `converted.decisions` for deliberately excluded or unsupported native
content. Reasoning is excluded by default and protected reasoning is never
automatically exposed. Tool calls describe internal execution by default.

Public namespace: `ygo74.agent_runtime.integrations.agentframework`.
Base adapters and sessions do not import FastAPI or choose output protocols.
The optional `worker` module uses the `[http]` extra for managed local hosting.
See `docs/python/native-agents.md` for the factory + declarative-definition path
and the optional domain approval bridge.

See the repository's `docs/python/agentframework.md` guide and the runnable,
offline `docs/examples/python-agentframework-fastapi` example (operator-supplied
local authentication key, no model credentials).
