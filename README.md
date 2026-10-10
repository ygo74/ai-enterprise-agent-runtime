# AI Enterprise Agent Runtime

Cross-language runtime library for exposing AI use cases through standard endpoint surfaces and a unified exchange contract.

## Goal

This repository provides runtime building blocks so developers can:

- expose use cases through OpenAI-compatible and Anthropic-compatible endpoints;
- receive normalized input payloads in a standard exchange format;
- execute business logic through decoupled handlers and middleware;
- return endpoint-compliant responses (streaming and non-streaming).

## Current Scope

The consolidated [system specification](spec/README.md) describes the library
as it is currently implemented. The shared core covers provider-neutral
exchange contracts, request/response mapping, routing, middleware, and
authentication building blocks across Python, .NET, and Java. Python also
provides optional FastAPI hosting, agent discovery, application-security and
approval primitives, conversation state, MCP client/server packages, and
Python-only agent-development APIs for configuration, manifest schemas,
framework-neutral reasoning, and user-context construction. See the
[language support matrix](spec/compatibility/language-status.md) for current
parity limits.

## Repository Layout

- [`packages/python/`](packages/python/): Python distributions — see [Python packaging](#python-packaging)
- [`packages/dotnet/`](packages/dotnet/): .NET package (`Ygo74.AgentRuntime`)
- [`packages/java/`](packages/java/): Java package (`ygo74-agent-runtime`)
- [`tests/`](tests/): contract, integration, parity, and performance tests
- [`docs/examples/`](docs/examples/): example integrations
- [`spec/`](spec/): consolidated system specification
- [`specs/001-openai-endpoint-exposure/`](specs/001-openai-endpoint-exposure/): legacy feature contracts and validation assets

## Python packaging

The Python runtime ships as three core distributions, a meta-package and two
optional framework integration distributions. They are split
so that a host installs the machinery it actually runs: an MCP server has no agent,
no conversation and no discovery descriptor, but it has exactly the same question to
answer about who is calling.

| Distribution | Install it to | Depends on |
|---|---|---|
| `ygo74-agent-runtime-security` | Authenticate a caller and classify what they may do | — |
| `ygo74-agent-runtime-agents` | Host an agent and load its delivered configuration | security; `configuration`, `http`, and `mcp` extras |
| `ygo74-agent-runtime-mcp` | Host a Model Context Protocol server | security |
| `ygo74-agent-runtime` | Everything, as before | the three |
| `ygo74-agent-runtime-langchain` | Adapt LangChain results/events | agents and LangChain |
| `ygo74-agent-runtime-agentframework` | Adapt Microsoft Agent Framework Python results/updates | agents and Agent Framework |

The core and base meta-package have no dependency on an agent framework.
Version 1.0 of the Python agents output API uses a typed neutral pivot and
removes raw outputs/native OpenAI Responses passthrough. See
[typed outputs and migration](docs/python/typed-outputs.md). This output contract
is Python-first; .NET/Java implementation follows separately.

They all contribute to the same namespace, so the import path does not say which
distribution a name came from:

```python
from ygo74.agent_runtime.domains.security.permissions import Permission
from ygo74.agent_runtime.domains.auth.authenticator import RequestAuthenticator
from ygo74.agent_runtime.domains.endpoints.fastapi_endpoints import add_ai_endpoints
```

> **Breaking change in 0.1.0.** The flat facade `from ygo74.agent_runtime import X`
> is gone. A regular package can be contributed by exactly one distribution, so
> keeping it would have made an editable install of the other two invisible. Import
> from the domain module instead, which is what nearly all consumer code already
> did.

## Architecture at a Glance

The runtime is organized around reusable domains:

- **Endpoint adapters** to map endpoint payloads to standard contracts;
- **Request/response mapping** to keep transport details separate from use-case logic;
- **Routing and dispatch** to call registered handlers by route key;
- **Authentication context** for JWT/API key flows, and a typed `AgentPrincipal` projection of the authenticated caller;
- **Agent contracts** - the conversation port a serving surface needs from an agent, the manifest that describes a capability, and the registry an orchestrator builds its tools from;
- **Agent configuration** - typed loaders for delivered YAML manifests, local `.env` loading, and packaged JSON Schemas for `agent.yaml` and `skill.yaml` (`configuration` extra);
- **Reasoning port** - a framework-neutral protocol and error hierarchy for typed model-backed results;
- **Security model** - permissions declared by the domain that owns them, user contexts, the read/write and risk classification of an operation, the posture floor a configuration may not go below, and an audit trail;
- **Human approval** - a deterministic policy deciding what needs a person's answer, tickets that carry an operation and its exact arguments across two requests, a literal `CONFIRM`/`CANCEL` parser that runs before the model, and a gated runner that authorises, executes and audits;
- **Untrusted content** - a redacted-by-construction wrapper for anything a third party wrote, and a fence that keeps it from escaping into the instruction space of a prompt;
- **Session state** - one runtime per conversation per authenticated subject, leased so nothing closes what a request is using, bounded and expiring;
- **Tool access** - Model Context Protocol transport lifecycle, binding schema, dialect registry and the generic OAuth pieces, behind the `mcp` extra;
- **Middleware pipeline** for ordered pre/post processing;
- **Observability** hooks for logging and OpenTelemetry.

The security model and the agent contracts are currently **Python only**; see
[`docs/parity-status.md`](docs/parity-status.md) for what .NET and Java must
implement to reach parity, and for the behaviour those implementations have to
preserve.

The Python distributions keep their domains separable, so importing one loads no
more than it needs. `import ygo74.agent_runtime.domains.security.permissions`
brings in no endpoint code, no web framework and no protocol client — which is the
property that lets an MCP server share this authentication model without inheriting
an agent's dependencies. `tests/integration/python/test_public_surface.py` is what
keeps that true.

## Getting Started

The [Python library documentation](docs/python/README.md) covers package
selection, installation, a local quickstart, and the current Python runtime
capabilities.

1. Pick your target runtime in [`packages/python/`](packages/python/), [`packages/dotnet/`](packages/dotnet/), or [`packages/java/`](packages/java/).
2. Review current behavior in [`spec/`](spec/) and shared machine-readable contracts in [`specs/001-openai-endpoint-exposure/contracts/`](specs/001-openai-endpoint-exposure/contracts/).
3. Explore usage patterns in [`docs/examples/`](docs/examples/).

Important documents:

- [System overview](spec/architecture/system-overview.md)
- [Exchange contract](spec/contracts/exchange-contract.md)
- [Provider endpoint surfaces](spec/endpoints/provider-surfaces.md)
- [Language support and parity](spec/compatibility/language-status.md)
- [Shared machine-readable contracts and validation assets](specs/001-openai-endpoint-exposure/contracts/)
- Hosting an MCP server: [`docs/mcp-server-hosting.md`](docs/mcp-server-hosting.md)
- Cross-language parity status: [`docs/parity-status.md`](docs/parity-status.md)

## Quickstart for contributors

The repository is multi-language. The commands below are the currently documented and verifiable starting points.

### Install the local Python quickstart

From [`docs/examples/python-fastapi-quickstart/README.md`](docs/examples/python-fastapi-quickstart/README.md):

```powershell
cd docs/examples/python-fastapi-quickstart
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

### Run principal tests

From the .NET test project in [`tests/dotnet/AgentRuntime.Tests.csproj`](tests/dotnet/AgentRuntime.Tests.csproj):

```bash
DOTNET_CLI_HOME=/mnt/c/devel/ai-enterprise-agent-runtime dotnet test tests/dotnet/AgentRuntime.Tests.csproj --no-restore -v normal
```

### Start the local Python endpoint

From [`docs/examples/python-fastapi-quickstart/README.md`](docs/examples/python-fastapi-quickstart/README.md):

```powershell
cd docs/examples/python-fastapi-quickstart
uvicorn app:app --reload --port 8000
```

Send a request to `/v1/responses` as shown in that guide. This echo example does
not need an external LLM provider or API key.

## Project Status

- Current system behavior is described in [`spec/`](spec/).
- Runtime code is organized across Python, .NET, and Java packages in [`packages/`](packages/).
- Validation assets live under [`tests/`](tests/) and shared machine-readable contracts under [`specs/001-openai-endpoint-exposure/contracts/`](specs/001-openai-endpoint-exposure/contracts/).
