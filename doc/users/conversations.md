# Conversations

A conversation groups requests that belong to the same exchange with an agent.
A client can identify it with a conversation ID or another host-supported
correlation value. The host passes that association to the agent so it can
continue an earlier turn when the selected integration supports state.

## Continue a conversation

Use the same ID when sending a follow-up request:

```http
POST /v1/responses
Content-Type: application/json
x-conversation-id: support-42

{"model":"support-agent","input":"What did we decide about the maintenance window?"}
```

The ID associates the request with `support-42`; it does not itself store the
conversation. The application or framework integration chooses how messages,
checkpoints, and pending operations are stored.

## Choose state ownership

Process-local state is simple for a single-instance example, but it disappears
when the process stops and is not shared by replicas. A multi-instance service
needs shared or durable storage with appropriate concurrency controls. See the
[Python conversation and worker guide](../python/agent-runtime.md) for the
current Python APIs and constraints.
