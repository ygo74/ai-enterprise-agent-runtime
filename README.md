# AI Enterprise Agent Runtime

Cross-language runtime library for exposing AI use cases through standard endpoint surfaces and a unified exchange contract.

## Goal

This repository provides runtime building blocks so developers can:

- expose use cases through OpenAI-compatible and Anthropic-compatible endpoints;
- receive normalized input payloads in a standard exchange format;
- execute business logic through decoupled handlers and middleware;
- return endpoint-compliant responses (streaming and non-streaming).

## Current Scope

The first feature specification scope is documented in [specs/001-openai-endpoint-exposure/spec.md](specs/001-openai-endpoint-exposure/spec.md) and focuses on:

- OpenAI Chat Completions surface;
- OpenAI Responses surface;
- Anthropic Messages surface;
- shared request/response contracts;
- cross-language parity (Python, .NET, Java).

## Repository Layout

- [`packages/python/`](packages/python/): Python distributions — see [Python packaging](#python-packaging)
- [`packages/dotnet/`](packages/dotnet/): .NET package (`Ygo74.AgentRuntime`)
- [`packages/java/`](packages/java/): Java package (`ygo74-agent-runtime`)
- [`tests/`](tests/): contract, integration, parity, and performance tests
- [`docs/examples/`](docs/examples/): example integrations
- [`specs/001-openai-endpoint-exposure/`](specs/001-openai-endpoint-exposure/): feature specification, plan, and contracts

## Python packaging

The Python runtime ships as three distributions plus a meta-package. They are split
so that a host installs the machinery it actually runs: an MCP server has no agent,
no conversation and no discovery descriptor, but it has exactly the same question to
answer about who is calling.

| Distribution | Install it to | Depends on |
|---|---|---|
| `ygo74-agent-runtime-security` | Authenticate a caller and classify what they may do | — |
| `ygo74-agent-runtime-agents` | Host an agent behind OpenAI/Anthropic endpoints | security |
| `ygo74-agent-runtime-mcp` | Host a Model Context Protocol server | security |
| `ygo74-agent-runtime` | Everything, as before | the three |

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

1. Pick your target runtime in [`packages/python/`](packages/python/), [`packages/dotnet/`](packages/dotnet/), or [`packages/java/`](packages/java/).
2. Review feature behavior and contracts in [`specs/001-openai-endpoint-exposure/`](specs/001-openai-endpoint-exposure/).
3. Explore usage patterns in [`docs/examples/`](docs/examples/).

Important documents:

- Feature spec: [`specs/001-openai-endpoint-exposure/spec.md`](specs/001-openai-endpoint-exposure/spec.md)
- Implementation plan: [`specs/001-openai-endpoint-exposure/plan.md`](specs/001-openai-endpoint-exposure/plan.md)
- Validation scenarios: [`specs/001-openai-endpoint-exposure/quickstart.md`](specs/001-openai-endpoint-exposure/quickstart.md)
- Contracts: [`specs/001-openai-endpoint-exposure/contracts/`](specs/001-openai-endpoint-exposure/contracts/)
- Cross-language parity status: [`docs/parity-status.md`](docs/parity-status.md)

## Quickstart for contributors

The repository is multi-language. The commands below are the currently documented and verifiable starting points.

### Configure / install (Python example)

From [`docs/examples/python-langchain-fastapi/01-get-started/README.md`](docs/examples/python-langchain-fastapi/01-get-started/README.md):

```powershell
cd docs/examples/python-langchain-fastapi/01-get-started
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

### Run principal tests

From the .NET test project in [`tests/dotnet/AgentRuntime.Tests.csproj`](tests/dotnet/AgentRuntime.Tests.csproj):

```bash
DOTNET_CLI_HOME=/mnt/c/devel/ai-enterprise-agent-runtime dotnet test tests/dotnet/AgentRuntime.Tests.csproj --no-restore -v normal
```

### Start a functional example

From [`docs/examples/python-langchain-fastapi/01-get-started/README.md`](docs/examples/python-langchain-fastapi/01-get-started/README.md):

```powershell
cd docs/examples/python-langchain-fastapi/01-get-started
python -m uvicorn openai_responses_app:app --reload --port 8001
```

## Project Status

- Current feature scope is tracked in [`specs/001-openai-endpoint-exposure/`](specs/001-openai-endpoint-exposure/).
- Runtime code is organized across Python, .NET, and Java packages in [`packages/`](packages/).
- Validation assets live under [`tests/`](tests/) and feature contracts under [`specs/001-openai-endpoint-exposure/contracts/`](specs/001-openai-endpoint-exposure/contracts/).
