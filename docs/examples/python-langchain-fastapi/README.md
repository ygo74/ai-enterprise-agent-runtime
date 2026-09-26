# Python LangChain + FastAPI Examples

Each example lives in its own folder.

For package selection, installation, and an overview of the Python runtime, see
the [Python library documentation](../../python/README.md).

## Available examples

- `01-get-started`: AI Solution Architect agent with LangChain, MCP Microsoft Learn tool, and OpenAI Responses exposure via `ygo74` runtime.
- `02-jwt-authentication`: OpenAI-compatible FastAPI endpoints protected with JWT validation (`Bearer` + claims + signature).
- `03-jwt-oidc-keycloak`: same protection, but signature validation against a real OIDC provider (Keycloak) via JWKS instead of a static secret.
- `04-human-in-the-loop`: the same agent, but its tool call waits for an explicit human approval that spans two HTTP requests - a ticket is issued, the turn ends having changed nothing, and a later `CONFIRM` replays the stored arguments.

## Convention

- Each example folder contains source files, a `requirements.txt`, and a README
  with run instructions. Environment files or `.env.sample` templates are
  included when the particular example uses them.
