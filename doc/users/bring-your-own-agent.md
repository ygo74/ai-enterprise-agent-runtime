# Bring your own agent

The runtime hosts an agent application; it does not write the application's
business behavior. The application supplies the agent's instructions, tools,
and policies, then connects that logic to a supported hosting or framework
integration.

## What the application owns

- **Business rules:** validate the request, decide what work is permitted, and
  define how the agent should handle domain cases.
- **Tools:** implement the operations an agent may request, including checks
  before reading data or causing side effects.
- **Skills:** group reusable instructions and tool choices for a task. The
  application decides which skills are available to an agent.
- **System prompt:** set the agent's role, constraints, and response guidance.
  Keep authorization in enforceable application policy; prompt text alone is
  not an access control.

The runtime can normalize requests, host provider-compatible endpoints, manage
shared request concerns, and adapt supported framework outputs. It does not
choose your business rules or grant a tool access to data on its own.

## Choose an integration approach

The runtime supports several ways to connect agent logic. Availability varies
by language and framework; consult the implementation guide before choosing.

| Approach | Use it when | Ownership boundary |
|---|---|---|
| Direct handler | The application already has its own agent or business logic. | The application owns its logic and its route; the runtime can adapt the handler to standard endpoint contracts. |
| Framework adapter | The application uses a supported agent framework. | The framework owns agent construction; an adapter maps its results and events to runtime outputs. |
| Native framework worker | The runtime has a worker for the framework's native agent type. | The framework owns the agent; the worker hosts it through standard runtime endpoints. |
| Managed worker | The application needs lower-level control of conversations and resources. | The application composes conversation state and lifecycle with the runtime worker. |
| Declarative configuration | Agent, skill, or MCP settings should be loaded from maintained configuration files. | The application validates the configuration and decides which capabilities to admit. |
| Custom hosting | Existing application routes or deployment needs should remain in control. | The application owns HTTP lifecycle and connects runtime components as needed. |

These are integration patterns, not six universally available products. For
current Python examples, see the [Python sample catalog](../../samples/python/README.md)
and [Python implementation guides](../python/README.md). Follow the
[complete agent request walkthrough](complete-agent.md) for one conceptual
request that combines these responsibilities. The [hosting guide](agent-hosting.md)
explains where endpoint and conversation responsibilities sit.
