# Provider invocation surfaces

## Supported invocation dialects

| Endpoint type | Python FastAPI route | Normalized input selection |
|---|---|---|
| `openai.responses` | `POST /v1/responses` | Request body's `input` |
| `openai.chat_completions` | `POST /v1/chat/completions` | `messages`, falling back to `input` |
| `anthropic.messages` | `POST /v1/messages` | `messages`, falling back to `input` |

The Python HTTP adapter is part of the agents distribution and imports FastAPI
defensively. Install the `http` extra to serve these routes. The direct
`add_ai_endpoints` function enables OpenAI Responses and Chat Completions by
default and leaves Anthropic Messages disabled. It also supports explicit
route selection, authentication, descriptor-based model resolution,
authorization, discovery, and allowlisted request-header forwarding.

`HostingFactory` is the typed Python/FastAPI composition API for one
entrypoint/descriptor pair. It requires explicit endpoint selection and an
`AuthenticationPolicy`, optionally accepts `DiscoveryConfiguration`, validates
its collected setup, and registers through `add_ai_endpoints`. Use
`AuthenticationPolicy.anonymous()` to make intentionally open invocation
explicit. Multi-agent applications continue to use the direct helper with a
dispatcher and `DescriptorRegistry`.

The .NET and Java packages identify the same endpoint type strings and provide
typed configuration, normalization, response-mapping, streaming, and dispatch
building blocks. This repository currently includes no built-in HTTP route
registrations for ASP.NET Core or Spring; the application supplies that host
integration.

## Handler mapping

For Python FastAPI, the normalized handler payload carries:

- request ID;
- selected internal route key;
- endpoint type;
- normalized user input;
- stream flag;
- safe metadata;
- authentication context or `None`.

An application handler can be synchronous or asynchronous and returns typed
`AgentOutput`, optionally in `StandardExchangeResponse`. Protocol projection
classes render the response envelope outside the FastAPI transport. Raw strings,
dictionaries and native OpenAI Responses result/event payloads are no longer
accepted as output contracts. Incoming normalized mappings remain unchanged.

The handler remains responsible for application behavior. The runtime does
not invoke an LLM, select a provider, or infer a business operation from the
request.

## Streaming

The Python adapter responds with `text/event-stream` when the request asks for
streaming. A handler returns typed events or a typed final result. Separate
stream processing/projection classes own validation, correlation, protocol
lifecycle and SSE serialization. Only Chat Completions uses `data: [DONE]`;
Responses and Anthropic terminate through their native lifecycle events.
Failures after stream headers are sent are terminal stream failures.

Notifications are deliberate stream-visible text, not business answer content.
Non-streaming projection excludes them with diagnostics. Images/audio retain
their URI or encoded data and MIME/format without transcoding. A valid content
unsupported by the selected protocol is filtered with a correlated log; the
developer need not inspect the invoking protocol. Invalid event sequences still
fail. See the tested [output contract and support matrix](../../specs/001-openai-endpoint-exposure/contracts/typed-output-contract.md).

The .NET package includes an OpenAI stream mapper and stream termination
building blocks; Java includes Anthropic stream mapping and termination types.
The shared `StreamingEvent` contract records sequence, event type, delta,
completion, and error. Current framework-specific integration is not uniform
across languages; see [language support](../compatibility/language-status.md).

## Authentication and forwarded metadata

FastAPI endpoint registration authenticates before calling the user entrypoint.
Recognized invalid credentials are rejected even when credentials are optional;
when authentication is required, an uncredentialed caller is rejected. Headers
are not copied into handler metadata by default. The application must explicitly
allowlist forwarded headers, and credential-bearing headers are excluded.
Authorization failures are returned as structured errors and do not execute
protected handler logic.

See the [authentication and authorization specification](../security/authentication-and-authorization.md)
for policy details and the [exchange contract](../contracts/exchange-contract.md)
for the normalized handler boundary.
