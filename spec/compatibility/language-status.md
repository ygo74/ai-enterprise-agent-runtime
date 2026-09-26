# Language support and parity

The library shares provider-neutral contracts and runtime building blocks
across Python, .NET, and Java, but the packages do not expose identical hosting
features. This table records the repository's current implementation boundaries.

| Capability | Python | .NET | Java |
|---|---|---|---|
| Exchange contracts, errors, stream events | Yes | Yes | Yes |
| Provider request/response mapping | Yes | Yes | Yes |
| HTTP route hosting | FastAPI adapter | No built-in ASP.NET Core adapter | No built-in Spring adapter |
| Invocation surfaces | OpenAI Responses, OpenAI Chat Completions, Anthropic Messages | Shared endpoint identifiers and mapping/dispatch building blocks | Shared endpoint identifiers and mapping/dispatch building blocks |
| JWT/API-key authentication primitives | Yes | Yes | Yes |
| Explicit authentication policy composition | Yes | No equivalent integrated HTTP composition | No equivalent integrated HTTP composition |
| Agent descriptors and model discovery | OpenAI and Anthropic projections | No | No |
| Agent access policy | Yes | No | No |
| Routing and middleware building blocks | Yes | Yes | Yes |
| Conversation runtime cache | Yes | No | No |
| Human approval and application-security primitives | Yes | No | No |
| MCP client | Optional extra | No | No |
| MCP server hosting | Separate Python distribution | No | No |
| Logging and OpenTelemetry integration hooks | Yes; OpenTelemetry hook incomplete | Yes; OpenTelemetry hook incomplete | Yes; OpenTelemetry hook incomplete |

## Python

Python provides the most complete hosting composition in this repository. Its
agents distribution includes a FastAPI adapter for the three invocation
surfaces, optional OpenAI and Anthropic model discovery, descriptors, routing,
middleware, conversation contracts and cache, approval primitives, and an
optional MCP client. A separate package hosts MCP servers. `HostingFactory`
composes one descriptor/entrypoint pair; applications with multiple agents can
use the lower-level registration helper and dispatcher.

There is no A2A agent-card endpoint and no AG-UI adapter. The discovery
configuration's `enable_agent_card` field currently does not register a route.

## .NET and Java

The .NET package targets .NET 8 and the Java package targets Java 21. Both
provide typed exchange contracts, endpoint/mapping and streaming building
blocks, configuration validation, authentication classes, routing, middleware,
and logging/telemetry hooks. They do not contain framework-native HTTP endpoint
registration in this repository. Applications connect the building blocks to
ASP.NET Core or Spring themselves.

The detailed shared status matrix is maintained in
[`docs/parity-status.md`](../../docs/parity-status.md). The feature contracts
and tests define shared behavior where an implementation exists; listing the
same endpoint identifiers does not imply identical host integration.
