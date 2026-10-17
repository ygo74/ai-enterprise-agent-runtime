# Human approval

Require a human decision before a tool performs an operation that changes data,
sends information outside the application, or carries another meaningful risk.
The application defines which operations need approval and what information a
reviewer sees.

## Approval across HTTP requests

The first request can return a pending operation and a single-use ticket. The
reviewer approves or cancels it in a later request, associated with the same
caller and conversation:

```http
POST /v1/chat/completions
Content-Type: application/json
x-api-key: <application-credential>
x-conversation-id: support-42

{"model":"support-agent","messages":[{"role":"user","content":"CONFIRM <ticket-id>"}]}
```

The host must verify that the ticket belongs to the caller and conversation,
has not expired, and has not already been consumed. Approval should apply to the
exact operation and arguments shown to the reviewer. Cancellation consumes the
ticket without performing the operation.

Ticket storage and agent checkpoints must survive the deployment pattern. A
single-process example may keep them in memory; a multi-instance application
needs shared atomic ticket storage and shared or durable conversation state.

See [Python human-in-the-loop approval](../python/human-in-the-loop.md) for the
current policy and storage APIs. The [LangChain](../../samples/python/python-langchain-fastapi/02-human-in-the-loop/README.md)
and [MAF](../../samples/python/python-agentframework-fastapi/02-human-in-the-loop/README.md)
examples document their different framework-specific approval flows.
