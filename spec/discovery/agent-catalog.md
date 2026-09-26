# Agent descriptors and model discovery

## Descriptor model

Python's `AgentDescriptor` is the canonical provider-neutral description of a
discoverable agent. It separates the public identifier used by clients from
the internal `route_key` used to dispatch work.

Required descriptor fields are:

- `agent_id`: public, case-sensitive model identifier, 1–128 characters,
  matching `^[A-Za-z0-9][A-Za-z0-9._:-]*$`;
- `route_key`: non-empty internal dispatch key;
- `display_name`, `description`, `version`, and `owner`;
- timezone-aware `created_at_utc`;
- an `AgentCapabilitySet`.

Optional fields include documentation URL, tags, skills, public metadata,
advertised security scheme names, and discovery visibility. A skill has a stable
ID, name, and description, with optional tags, examples, and modality bounds.
Skill modality declarations must be compatible with the parent descriptor.

Capabilities describe modalities, streaming, tool invocation, structured
output, optional input/output size limits, and additive extensions. They are
claims; they do not turn on endpoints or handler behavior. The application must
configure real capabilities and advertise only supported behavior. No A2A card
is currently served; references to a descriptor being card-ready describe a
possible projection, not an available endpoint.

`DescriptorRegistry` rejects duplicate public IDs, provides exact lookup, and
orders catalog entries by case-sensitive ascending `agent_id`. A descriptor
can be hidden from listings while remaining directly invocable by its model
ID, unless an access policy denies that caller.

## Model projections

The Python FastAPI integration can register these optional routes:

| Dialect | Listing | Single model |
|---|---|---|
| OpenAI-compatible | `GET /v1/models` | `GET /v1/models/{agent_id}` |
| Anthropic-compatible | Shared `/v1/models` selected by dialect, or explicit `/anthropic/v1/models` when both dialects are enabled | Corresponding model ID route |
| OpenAI explicit override | `/openai/v1/models` when both dialects are enabled | `/openai/v1/models/{agent_id}` |

The default shared path selects Anthropic when a supported `anthropic-version`
header is present and OpenAI otherwise. `DiscoveryConfiguration` may choose a
different dialect-selection policy, enable either or both model dialects,
require authentication, set a route prefix, and configure page-size bounds.
Discovery is opt-in. It is not exposed by `HostingFactory` unless a discovery
configuration is supplied.

OpenAI listings use the `{"object":"list","data":[...]}` envelope and
project agent ID, creation time, and owner into native model fields. Anthropic
listings include model ID, display name, creation timestamp, first/last cursor,
and `has_more`. Both projections place additional descriptor properties in the
`x-agent-runtime` extension block. Catalog ordering and cursor pagination are
deterministic; default page size is 20 and maximum page size is 100.

## Access control and routing

When a descriptor registry and an `AgentAccessPolicy` are configured together,
the same policy gates invocation and discovery. Denied agents are omitted from
listings; direct lookup returns the same not-found result as a hidden or unknown
agent. If a policy raises, the runtime fails closed and treats that descriptor
as inaccessible.

Discovery authentication is independently configurable from invocation. It
uses the configured authenticator chain but a separate
`require_authentication` setting. Model IDs returned to clients resolve back to
the descriptor's route key at invocation; IDs and route keys are exact and
case-sensitive.

## Current limits

- Discovery is implemented in Python only.
- The current FastAPI adapter serves OpenAI and Anthropic model projections.
- No A2A `/.well-known/agent-card.json` route or card projection is implemented.
- `DiscoveryConfiguration` contains an `enable_agent_card` value, but current
  route registration does not act on it; it must not be treated as a supported
  endpoint.
- There is no AG-UI discovery or invocation adapter.
- Descriptors, registries, and in-memory configuration are initialization-time
  application data; the runtime does not load or persist them.
