# Complete agent request walkthrough

This conceptual walkthrough follows one request through the parts an application
combines to expose an agent. It uses shared HTTP/JSON concepts; implementation
and setup details depend on the language and framework.

## Before serving requests

1. The application defines a system prompt and business rules for its domain.
2. It registers the tools and skills the agent may use. Each tool enforces its
   own access checks before reading or changing protected data.
3. The host registers an agent descriptor and selects the endpoint surfaces it
   will serve.
4. The operator configures authentication, conversation storage, model access,
   and any remote MCP service credentials outside source control.

## One request

A client calls an endpoint with an agent identifier and input:

```http
POST /v1/responses
Authorization: Bearer <access-token>
x-conversation-id: case-17
Content-Type: application/json

{"model":"support-agent","input":"Find the current support policy."}
```

The host authenticates the caller, resolves the registered agent, applies its
access policy, and associates the request with `case-17`. The agent follows its
instructions and may request an approved tool. The application decides whether
the caller may use that tool and whether the operation needs human approval.
The runtime or framework adapter maps the completed result to the endpoint's
response format.

If the answer requires a side effect or external request, the application can
return a pending approval ticket instead of executing it. A later request must
present that ticket under the same authorized caller and conversation. See the
[human approval guide](human-approval.md) for the safeguards around this flow.

## Implementation examples

The [Python LangChain approval sample](../../samples/python/python-langchain-fastapi/02-human-in-the-loop/README.md)
combines an authenticated endpoint, discovery, an MCP search tool, conversation
state, and a two-request approval flow. Its README describes which state is
process-local and what the example does not combine. For a native MAF agent,
see the [MAF catalog](../../samples/python/python-agentframework-fastapi/README.md)
and its framework-specific limits.
