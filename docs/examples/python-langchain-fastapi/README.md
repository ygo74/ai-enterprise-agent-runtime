# Python LangChain + FastAPI Examples

Each example lives in its own folder.

## Available examples

- `01-get-started`: AI Solution Architect agent with LangChain, MCP Microsoft Learn tool, and OpenAI Responses exposure via `ygo74` runtime.
- `02-jwt-authentication`: OpenAI-compatible FastAPI endpoints protected with JWT validation (`Bearer` + claims + signature).
- `03-jwt-oidc-keycloak`: same protection, but signature validation against a real OIDC provider (Keycloak) via JWKS instead of a static secret.

## Convention

- Each example folder contains:
  - source files
  - `.env` for local execution
  - `.env.sample` template with required keys
  - its own `README.md` with run instructions
