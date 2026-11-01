# Host an agent

An agent can run behind routes owned by its application, or use a runtime
worker that registers standard endpoints and manages shared hosting concerns.
The right choice depends on whether the application needs full control of HTTP
and agent lifecycle or prefers a runtime-managed adapter.

## Hosting choices

- **Application-owned endpoint:** keep existing routes and call the agent from
  the application's handler. This is useful when the public API is specific to
  the product.
- **Runtime endpoint adapter:** register selected provider-compatible routes
  around an application handler. The application continues to construct and
  execute the agent.
- **Native framework worker:** give a supported framework agent to a runtime
  worker. The worker maps endpoint requests to framework calls and owns shared
  endpoint lifecycle.
- **Managed worker composition:** use a lower-level worker and provide
  conversation creation or resource-lifecycle behavior when the application
  needs custom control.

Not every language or framework currently provides all four options. For
Python support and runnable examples, see [native agent hosting](../python/native-agents.md)
and the [Python sample catalog](../../samples/python/README.md).

## Declare Python HTTP hosting in `agent.yaml`

Python applications can also select their invocation routes, authentication
mode, and optional request limits in an agent manifest. API keys and static JWT
key material are supplied through environment-variable references. Loading the
manifest for a command-line or MCP use does not require those HTTP credentials;
they are resolved when the HTTP host is built.

Limits apply to the client address seen by FastAPI. They use process-local
storage by default; Redis can share counters across workers. Configure trusted
proxy handling at the server boundary because client-supplied forwarding
headers are not used as the limit identity. An unselected route stays disabled,
and a request over its limit receives HTTP 429 before agent code runs.

This manifest-driven HTTP setup is currently a Python FastAPI capability. See
the [agent manifest reference](../python/agent-manifest.md) for the accepted
keys and [Python hosting guide](../python/agent-runtime.md) for setup details.

## Readiness and shutdown

Keep readiness distinct from liveness. Readiness should report whether the
agent can accept work without exposing credentials, prompts, or user data.
Shutdown should close framework clients and other resources owned by the
application. A process-local worker may lose its conversations when it stops;
choose shared or durable storage when requests can reach different replicas.
