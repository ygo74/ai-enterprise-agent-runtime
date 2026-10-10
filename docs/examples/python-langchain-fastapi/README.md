# Python LangChain + FastAPI Examples

Each example lives in its own folder.

For package selection, installation, and an overview of the Python runtime, see
the [Python library documentation](../../python/README.md).

## Available examples

- `01-get-started`: AI Solution Architect agent with LangChain, MCP Microsoft Learn tool, and OpenAI Responses exposure via `ygo74` runtime.
- `02-jwt-authentication`: OpenAI-compatible FastAPI endpoints protected with JWT validation (`Bearer` + claims + signature).
- `03-jwt-oidc-keycloak`: same protection, but signature validation against a real OIDC provider (Keycloak) via JWKS instead of a static secret.
- `04-human-in-the-loop`: the same agent, but its tool call waits for an explicit human approval that spans two HTTP requests - a ticket is issued, the turn ends having changed nothing, and a later `CONFIRM` replays the stored arguments.
- `05-rag`: LangChain RAG agent using Azure OpenAI chat and embedding deployments, an in-memory vector index over a local Markdown knowledge base, source citations, and OpenAI Responses/Chat Completions exposure.

## Convention

All hosting entrypoints return `AgentOutput` or `AgentStreamEvent` streams
from the agents 1.x typed output contract. Framework-native values and strings
remain internal to model helpers, never the HTTP handler output boundary.
`01-get-started` explicitly installs `ygo74-agent-runtime-langchain` for native
result/event conversion. Other examples wrap their own text answers directly;
they do not install an unused integration or the framework-pulling meta package.
Reuse decision: extend existing entrypoints, input/security helpers and model
helpers; reuse the agents content/event contracts and optional integration
adapters rather than adding example-specific output models.

- Each example folder contains source files, a `requirements.txt`, and a README
  with run instructions. Environment files or `.env.sample` templates are
  included when the particular example uses them.
