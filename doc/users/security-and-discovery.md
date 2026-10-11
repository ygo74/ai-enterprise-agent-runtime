# Authentication and agent discovery

Authentication establishes who sent an HTTP request. Your application decides
what that caller may invoke. Agent discovery publishes descriptors so a client
can list configured agents; discovery access can have its own authentication
requirement.

## Require an API key

The LangChain approval example provides a local API key and protects both agent
calls and model discovery. Start it by following the setup in
[Complete agent walkthrough](complete-agent.md), then list models:

```bash
curl -sS http://127.0.0.1:8080/v1/models \
  -H 'x-api-key: demo-key'
```

The response is an OpenAI-compatible model list containing
`ai-solution-architect-hitl`. Without the key, the endpoint returns an
authentication error. `demo-key` is hard-coded for this local example only; use
an application-owned resolver or an identity provider for a deployed service.

## Use a bearer token

For OIDC, configure JWT validation with the issuer, audience, signing key
resolver, and required claims expected from your identity provider. The
[Keycloak example](../../samples/examples/python-fastapi-quickstart/03-jwt-oidc-keycloak/README.md)
shows a local setup. Its development realm and signing keys are for local use,
not production.

## Discovery behavior

Register an `AgentDescriptor` with the endpoint application and enable the
OpenAI models discovery route. The descriptor supplies the public agent ID,
description, version, owner, and capabilities. An access policy can be applied
to both invocation and discovery so a caller does not see agents they cannot
use.

For descriptor fields, route registration, and access policy behavior, see
[Agent discovery](../../doc/python/agent-discovery.md). Authentication and
authorization responsibilities are described in
[Security](../../doc/python/security.md).
