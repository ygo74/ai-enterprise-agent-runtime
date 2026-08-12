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

- [`packages/python/`](packages/python/): Python package (`ygo74-agent-runtime`)
- [`packages/dotnet/`](packages/dotnet/): .NET package (`Ygo74.AgentRuntime`)
- [`packages/java/`](packages/java/): Java package (`ygo74-agent-runtime`)
- [`tests/`](tests/): contract, integration, parity, and performance tests
- [`docs/examples/`](docs/examples/): example integrations
- [`specs/001-openai-endpoint-exposure/`](specs/001-openai-endpoint-exposure/): feature specification, plan, and contracts

## Architecture at a Glance

The runtime is organized around reusable domains:

- **Endpoint adapters** to map endpoint payloads to standard contracts;
- **Request/response mapping** to keep transport details separate from use-case logic;
- **Routing and dispatch** to call registered handlers by route key;
- **Authentication context** for JWT/API key flows;
- **Middleware pipeline** for ordered pre/post processing;
- **Observability** hooks for logging and OpenTelemetry.

## Getting Started

1. Pick your target runtime in [`packages/python/`](packages/python/), [`packages/dotnet/`](packages/dotnet/), or [`packages/java/`](packages/java/).
2. Review feature behavior and contracts in [`specs/001-openai-endpoint-exposure/`](specs/001-openai-endpoint-exposure/).
3. Explore usage patterns in [`docs/examples/`](docs/examples/).

Important documents:

- Feature spec: [`specs/001-openai-endpoint-exposure/spec.md`](specs/001-openai-endpoint-exposure/spec.md)
- Implementation plan: [`specs/001-openai-endpoint-exposure/plan.md`](specs/001-openai-endpoint-exposure/plan.md)
- Validation scenarios: [`specs/001-openai-endpoint-exposure/quickstart.md`](specs/001-openai-endpoint-exposure/quickstart.md)
- Contracts: [`specs/001-openai-endpoint-exposure/contracts/`](specs/001-openai-endpoint-exposure/contracts/)

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
