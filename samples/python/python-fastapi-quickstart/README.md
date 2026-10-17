# Python FastAPI quickstart

These four examples show the runtime without an agent framework. Start with a
local echo endpoint, then explore typed output and authentication.

## Examples

1. [Basic endpoint](01-basic-endpoint/README.md): expose Responses, Chat
   Completions, and Anthropic Messages with a deterministic echo handler.
2. [Structured outputs](02-structured-outputs/README.md): inspect typed
   content, streaming events, and explicit handling of unsupported output.
3. [JWT authentication](03-jwt-authentication/README.md): protect endpoints
   with a locally signed development token.
4. [OIDC and Keycloak](04-jwt-oidc-keycloak/README.md): validate tokens using
   Keycloak's public signing keys.

Use Python 3.12 or newer. Each example has its own dependency file and run
instructions. These examples need no LLM provider key; the Keycloak example
starts a local identity provider with Docker Compose.

For native agent frameworks, see the [LangChain catalog](../python-langchain-fastapi/README.md)
and [Microsoft Agent Framework catalog](../python-agentframework-fastapi/README.md).
