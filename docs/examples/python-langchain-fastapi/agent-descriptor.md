# Declaring an agent descriptor

An agent descriptor is what turns a handler into something a client can *find*. Without one the
runtime still routes requests, but nothing appears in `GET /v1/models`. Descriptors are optional:
declare one when you want the agent to be discoverable, skip it when the agent is internal.

## The shortest useful descriptor

```python
from datetime import datetime, timezone

from ygo74.agent_runtime import AgentCapabilitySet, AgentDescriptor

descriptor = AgentDescriptor(
    agent_id="support-assistant",
    route_key="support",
    display_name="Support Assistant",
    description="Answers customer questions about billing and subscriptions.",
    version="1.4.0",
    owner="customer-platform",
    created_at_utc=datetime(2026, 8, 16, tzinfo=timezone.utc),
    capabilities=AgentCapabilitySet(streaming=True),
)
```

Two identifiers appear here and they serve different audiences:

| Field       | Audience | Role                 |
|-------------|----------|----------------------|
| `agent_id`  | External | Advertised publicly  |
| `route_key` | Internal | Selects your handler |

Clients read `agent_id` from a listing and send it back in the `model` field. `route_key` is never
published.

Keeping them separate means you can rename or reshape your internal routing without breaking
clients, and it prevents a listing from leaking your routing topology.

`agent_id` must match `^[A-Za-z0-9][A-Za-z0-9._:-]*$` and stay under 128 characters, so it is always
safe to place in a URL path. Matching is exact: `Support-Assistant` and `support-assistant` are two
different agents, and a padded `" support-assistant "` is rejected rather than trimmed.

## Describing capabilities

`AgentCapabilitySet` is what clients read to decide whether they can talk to your agent at all.

```python
from ygo74.agent_runtime import AgentCapabilitySet, CapabilitySizeUnit, Modality

capabilities = AgentCapabilitySet(
    streaming=True,
    input_modalities=(Modality.TEXT, Modality.IMAGE),
    output_modalities=(Modality.TEXT,),
    tool_invocation=True,
    structured_output=True,
    size_unit=CapabilitySizeUnit.TOKENS,
    max_input_size=128_000,
    max_output_size=4_096,
)
```

Declared capabilities are validated against your configuration at startup. Declaring
`streaming=True` while the endpoint has `enable_streaming=False` fails fast with a
`capability_contradiction` error rather than misleading clients at runtime.

## Advertising skills

Skills describe *what* the agent does, in terms a human or a planner agent can act on.

```python
from ygo74.agent_runtime import AgentSkill

skills = (
    AgentSkill(
        skill_id="invoice-lookup",
        name="Invoice lookup",
        description="Finds an invoice by number or date range.",
        tags=("billing",),
        examples=("Show me invoice 4471.",),
    ),
)
```

Skill identifiers must be unique within a descriptor, and any modality a skill declares must be one
the agent's capabilities already allow — a skill cannot promise more than the agent can deliver.

## Registering descriptors

```python
from fastapi import FastAPI

from ygo74.agent_runtime import (
    DescriptorRegistry,
    DiscoveryConfiguration,
    add_ai_endpoints,
)

app = FastAPI()

add_ai_endpoints(
    app,
    agent_entrypoint,
    default_route_key="support",
    descriptor_registry=DescriptorRegistry([descriptor]),
    discovery=DiscoveryConfiguration(enable_openai_models=True),
)
```

Discovery is opt-in. With no `discovery` argument, or with every surface left disabled, no discovery
route is registered at all — the runtime adds no externally visible surface you did not ask for.

Listings are ordered by ascending `agent_id` so repeated calls return a stable sequence.

## Hiding an agent without disabling it

```python
from ygo74.agent_runtime import DiscoveryVisibility

internal = AgentDescriptor(..., discovery_visibility=DiscoveryVisibility.HIDDEN)
```

A hidden agent is absent from listings and returns 404 on direct retrieval — indistinguishable from
an agent that does not exist — yet remains fully invocable by callers that already know its route.
Use this for agents that are orchestrated internally but should not be offered to end users.

Hiding is unconditional: it applies the same way to every caller. When visibility should instead
depend on *who* is asking (e.g. only admins can see and invoke a given agent), pass an
`AgentAccessPolicy` to `add_ai_endpoints` — see
[authorization.md](authorization.md#option-0---a-shared-agentaccesspolicy-recommended-when-you-declare-descriptors).
A denied agent behaves exactly like a hidden one for that caller: absent from the listing, 404 on
direct retrieval, and a 403 if invocation is attempted anyway.

## Letting the runtime derive a descriptor

If you register a handler without a descriptor, the runtime derives a minimal one from the route key
so the agent remains internally consistent:

```python
from ygo74.agent_runtime import DescriptorDefaults

descriptor = DescriptorDefaults(owner="agent-runtime", version="1.0.0").derive("support/billing")
# agent_id == "support-billing"
```

Unsafe characters are replaced so the derived identifier is always path-safe. Note that
`display_name` equals the derived `agent_id` verbatim — the runtime deliberately does not
prettify it, because Unicode casing rules differ between Python, .NET and Java and would produce
different names for the same agent across languages.

Derived descriptors are a safety net, not a substitute for a real one. Anything you want a client to
understand — a readable name, a description, capabilities, skills — has to be declared explicitly.

## Completing the loop

The identifier a client reads from a listing is accepted verbatim as the `model` field:

```text
GET  /v1/models          ->  { "data": [ { "id": "support-assistant", ... } ] }
POST /v1/responses       <-  { "model": "support-assistant", "input": "..." }
```

The runtime resolves `support-assistant` back to route key `support` and dispatches to your handler.
An explicit `metadata.route_key` still takes precedence, and an unrecognised `model` falls back to
the configured default route rather than being routed somewhere unintended.

## Related

- [configuration.md](configuration.md) — enabling endpoints and streaming
- [authorization.md](authorization.md) — restricting who can reach an agent
