# Agent runtime

The agents distribution maps supported HTTP request formats into a common
handler payload, invokes your agent code, and maps successful results back to
the requested provider format. It provides transport and pipeline building
blocks; your application still owns the agent logic and domain authorization.

## Register endpoints

`HostingFactory` provides a typed setup flow for one agent and registers its
routes on an existing FastAPI app:

```python
from datetime import UTC, datetime

from fastapi import FastAPI
from ygo74.agent_runtime.domains.auth.authentication_policy import AuthenticationPolicy
from ygo74.agent_runtime.domains.discovery.agent_descriptor import AgentCapabilitySet, AgentDescriptor
from ygo74.agent_runtime.domains.discovery.discovery_configuration import DiscoveryConfiguration
from ygo74.agent_runtime.domains.endpoints.hosting_factory import EndpointSurface, HostingFactory

app = FastAPI()
descriptor = AgentDescriptor(
    agent_id="support",
    route_key="support",
    display_name="Support",
    description="Answers customer support questions.",
    version="1.0.0",
    owner="customer-platform",
    created_at_utc=datetime.now(UTC),
    capabilities=AgentCapabilitySet(),
)

(
    HostingFactory(app)
    .add_agent(agent_entrypoint, descriptor)
    .add_ai_endpoints(EndpointSurface.OPENAI_RESPONSES, EndpointSurface.OPENAI_CHAT_COMPLETIONS)
    .add_security(AuthenticationPolicy.api_key(api_key_resolver))
    .add_discovery(DiscoveryConfiguration(enable_openai_models=True, require_authentication=True))
    .register()
)
```

`add_agent` takes the synchronous or asynchronous entrypoint and its
`AgentDescriptor`. `add_ai_endpoints` selects only the routes to expose. Call
`register()` after configuration; the factory validates the complete setup
before delegating route registration to `add_ai_endpoints`. Authentication is
explicit: use `AuthenticationPolicy.anonymous()` only when open access is
intentional. Discovery is optional, and its authentication requirement is
configured separately from invocation. The [minimal quickstart](quickstart.md)
shows a complete runnable setup.

| Surface | Route | Enable option |
|---|---|---|
| OpenAI Responses | `POST /v1/responses` | `EndpointSurface.OPENAI_RESPONSES` |
| OpenAI Chat Completions | `POST /v1/chat/completions` | `EndpointSurface.OPENAI_CHAT_COMPLETIONS` |
| Anthropic Messages | `POST /v1/messages` | `EndpointSurface.ANTHROPIC_MESSAGES` |

The factory currently supports one descriptor/entrypoint pair. Applications
with a dispatcher and multiple agents can continue to use
[`add_ai_endpoints`](../../packages/python/agents/ygo74/agent_runtime/domains/endpoints/fastapi_endpoints.py)
directly with a `DescriptorRegistry`. The Python runtime does not currently
provide A2A or AG-UI route adapters.

Streaming requests use Server-Sent Events. Set `stream` on the request and have
the handler return an async iterator of typed output events. Each
endpoint family has its own event envelope; the
[endpoint surface specification](../../spec/endpoints/provider-surfaces.md)
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
| `provider_options` | Provider-specific request options not represented by the common fields; for Responses, this retains the raw options from the create request |

Return a typed `AgentOutput`, a typed stream, or a typed
`StandardExchangeResponse` carrying output/error. Raw result dictionaries and
strings are not accepted as output contracts in agents 1.0. The exchange models
are `StandardExchangeRequest` and `StandardExchangeResponse`; their fields are defined in
[`exchange_models.py`](../../packages/python/agents/ygo74/agent_runtime/domains/contracts/exchange_models.py)
and the [exchange specification](../../spec/contracts/exchange-contract.md).
The [typed output contract](../../specs/001-openai-endpoint-exposure/contracts/typed-output-contract.md)
replaces the historical v1 Python output shape. See [migration](typed-outputs.md).
For ordinary endpoint integration, the FastAPI adapter currently passes a
normalized mapping to the configured entrypoint. Framework or agent adapters
can convert that mapping to the typed contract used by their own code.

For `POST /v1/responses`, `input` keeps the submitted JSON value, including
arrays and multimodal content. Other Responses parameters such as `tools`,
`tool_choice`, `instructions`, and generation settings are passed in
`provider_options`; the request's `metadata` remains in the separate `metadata`
field. A handler returns neutral typed contents rather than constructing
Responses output items. The runtime projects the supported content into the
Response envelope and filters unsupported content with a safe diagnostic.
See the runnable
[structured Responses example](../examples/python-fastapi-quickstart/responses_structured_app.py)
for a complete example.

When streaming, return neutral typed events for text, tools, notifications,
reasoning, media, usage and termination. The core does not depend on an agent
framework. Install [LangChain](langchain.md) or [Agent Framework](agentframework.md)
integration independently to adapt SDK outputs.

Separate protocol projection classes handle output formatting and streaming
lifecycles outside the FastAPI transport. The runtime assigns protocol indices
and sequence numbers, closes the producer after a terminal event, and does not
add the Chat Completions `[DONE]` marker to Responses or Anthropic streams.
Notifications are text-visible in streaming, but excluded from non-streaming
results with diagnostics. Media is never automatically fetched or transcoded.

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

## Delivered agent configuration

Install `ygo74-agent-runtime-agents[configuration]` to load an agent's delivered
configuration without installing an HTTP or MCP transport. The
`domains.configuration` APIs resolve the configuration directory using
`YGO74_AGENT_RUNTIME_CONFIG_DIR`, load `.env` values without overriding the
process environment, and validate `agent.yaml` and `skill.yaml` against typed
input models before resolving permissions and enforcing security floors.

Draft 2020-12 schemas ship in the same distribution as package resources:

- `urn:ygo74:agent-runtime:agent-manifest:1`
- `urn:ygo74:agent-runtime:skill-manifest:1`

Use `ManifestSchemas.agent()` and `ManifestSchemas.skill()` from
`ygo74.agent_runtime.domains.configuration.manifest_schemas` to read those
resources. `AGENT.md` and `SKILL.md` remain separate Markdown inputs. See the
[manifest schema guide](../../spec/operations/packaging-configuration-observability.md)
and the [agent configuration example](../examples/python-langchain-fastapi/configuration.md).

## Reasoning port

Framework-specific chat clients live in adapters such as Microsoft Agent
Framework and LangGraph. Agent skills depend on the runtime's
`ygo74.agent_runtime.domains.reasoning.ports.TextReasoner` protocol and return
typed Pydantic models; `domains.reasoning.errors` provides the shared error
hierarchy. This keeps functional agent code independent of the selected client
library.

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
block; applications define how requests acquire and release leases.
`domains.sessions.agent_conversation` adds `AgentConversation[RuntimeT,
SessionT]` as a typed container for one application's runtime, framework
session, confirmation store, runner and renderer. `HttpConversationEngine`
leases that container, handles confirmation commands before calling the model,
and creates the shared `AgentReply`. Applications keep their composition roots
and framework-specific session adapters; their runtime types only need to
satisfy the small structural ports. Mail and Wiki in `ai_agents` are reference
consumers of this API.

For the approval policy, execution gates, and cross-request ticket flow, see the
[human-in-the-loop approval guide](human-in-the-loop.md) and its
[runnable LangGraph walkthrough](../examples/python-langchain-fastapi/04-human-in-the-loop/README.md).
The runtime also provides `domains.humanapproval.approval_loop.ApprovalLoop`.
Framework adapters expose pending calls, resume/decline operations and final
text through `ApprovalTurnAdapter`; the shared loop applies the approval and
total-turn limits and clears recorded grants before bounded, fail-closed cleanup.
The adapter still interprets Microsoft Agent Framework or LangGraph state.

## Observability

The package uses standard Python logging. See the
[`observability` domain](../../packages/python/agents/ygo74/agent_runtime/observability/).
`configure_otel_sink` is currently a placeholder integration hook, not a
complete OpenTelemetry exporter setup. Configure export through the hosting
application's OpenTelemetry pipeline. There is no runnable observability
integration example yet.
