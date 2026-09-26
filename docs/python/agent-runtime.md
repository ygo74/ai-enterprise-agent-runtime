# Agent runtime

The agents distribution maps supported HTTP request formats into a common
handler payload, invokes your agent code, and maps successful results back to
the requested provider format. It provides transport and pipeline building
blocks; your application still owns the agent logic and domain authorization.

## Register endpoints

`add_ai_endpoints` in
[`fastapi_endpoints.py`](../../packages/python/agents/ygo74/agent_runtime/domains/endpoints/fastapi_endpoints.py)
registers the routes on an existing FastAPI app:

```python
from fastapi import FastAPI
from ygo74.agent_runtime.domains.endpoints.fastapi_endpoints import add_ai_endpoints

app = FastAPI()
add_ai_endpoints(
    app,
    agent_entrypoint,
    default_route_key="support",
    enable_openai_responses=True,
    enable_openai_chat_completions=True,
    enable_anthropic_messages=False,
)
```

OpenAI Responses and Chat Completions are enabled by default; Anthropic Messages
is opt-in. The handler may be synchronous or asynchronous. The [minimal
quickstart](quickstart.md) shows a complete working handler.

| Surface | Route | Enable option |
|---|---|---|
| OpenAI Responses | `POST /v1/responses` | `enable_openai_responses` |
| OpenAI Chat Completions | `POST /v1/chat/completions` | `enable_openai_chat_completions` |
| Anthropic Messages | `POST /v1/messages` | `enable_anthropic_messages` |

Streaming requests use Server-Sent Events. Set `stream` on the request and have
the handler return an async iterator of text or supported delta chunks. Each
endpoint family has its own event envelope; the
[endpoint surface contract](../../specs/001-openai-endpoint-exposure/contracts/endpoint-surface-contract.md)
and [quickstart scenarios](../../specs/001-openai-endpoint-exposure/quickstart.md)
describe the supported requests and events.

## Handler and exchange payload

The handler input fields are:

| Field | Purpose |
|---|---|
| `request_id` | Correlates the response and logs with the input request |
| `route_key` | Internal key used to select the use case |
| `endpoint_type` | Provider and endpoint identifier |
| `input` | Normalized user input from the provider request |
| `stream` | Whether the caller requested a streamed reply |
| `metadata` | Request metadata, including explicitly forwarded allowlisted headers |
| `auth_context` | Authenticated caller context or `None` |

Return `{"status": "success", "output": ...}` or an error envelope. The
standard typed models are `StandardExchangeRequest` and
`StandardExchangeResponse`; their current fields are defined in
[`exchange_models.py`](../../packages/python/agents/ygo74/agent_runtime/domains/contracts/exchange_models.py)
and the [versioned schema](../../specs/001-openai-endpoint-exposure/contracts/standard-exchange-v1.schema.json).
For ordinary endpoint integration, the FastAPI adapter currently passes a
normalized mapping to the configured entrypoint. Framework or agent adapters
can convert that mapping to the typed contract used by their own code.

## Configuration and routing

`EndpointConfiguration` describes a route key, which endpoint surfaces are
enabled, streaming, and an optional `AgentDescriptor`. Its `from_dict` method
binds the documented camel-case settings. See
[`models.py`](../../packages/python/agents/ygo74/agent_runtime/domains/configuration/models.py)
and the [configuration example](../examples/python-langchain-fastapi/configuration.md).

Use `RouteRegistry` and the `Dispatcher` protocol when your application
registers multiple use cases by route key. An explicit `metadata.route_key` (or
top-level `route_key`) selects a route. When a descriptor registry is provided,
an advertised model ID also resolves to its internal route key; otherwise the
configured default is used. See the [routing package](../../packages/python/agents/ygo74/agent_runtime/routing/).
There is no standalone runnable routing example yet; the quickstart demonstrates
the default single-handler route.

## Middleware

The middleware interfaces and pipeline support ordered request processing,
explicit continuation, and response inspection or modification after the next
handler returns. See the
[`Middleware` protocol](../../packages/python/agents/ygo74/agent_runtime/middleware/interfaces.py)
and [pipeline](../../packages/python/agents/ygo74/agent_runtime/middleware/pipeline.py).
The current FastAPI adapter does not accept a middleware list directly; compose
the pipeline in the application entrypoint or dispatcher that invokes the
handler. There is no standalone middleware example yet.

## Discovery

`AgentDescriptor` is the provider-neutral identity and capability record for a
discoverable agent. For a detailed walkthrough of descriptor fields, discovery
registration, and the OpenAI `GET /v1/models` endpoints, see [Agent description
and model discovery](agent-discovery.md). The [agent descriptor schema](../../specs/001-openai-endpoint-exposure/contracts/agent-descriptor-v1.schema.json)
defines the canonical serialized shape. Anthropic model discovery and A2A agent
card details are outside that topic.

## Conversations and approval

`ConversationRuntimeCache` can hold a runtime per authenticated principal and
conversation ID with an idle expiry and maximum size. The cache is a building
block; applications define how requests acquire and release leases. For the
approval policy, execution gates, and cross-request ticket flow, see the
[human-in-the-loop approval guide](human-in-the-loop.md) and its
[runnable LangGraph walkthrough](../examples/python-langchain-fastapi/04-human-in-the-loop/README.md).
There is no standalone `ConversationRuntimeCache` example yet.

## Observability

The package uses standard Python logging. See the
[`observability` domain](../../packages/python/agents/ygo74/agent_runtime/observability/).
`configure_otel_sink` is currently a placeholder integration hook, not a
complete OpenTelemetry exporter setup. Configure export through the hosting
application's OpenTelemetry pipeline. There is no runnable observability
integration example yet.
