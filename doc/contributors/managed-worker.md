# Managed native-agent worker

`ManagedAgentWorker` hosts an existing native agent behind runtime endpoints.
It owns authentication enforcement, the process-local conversation cache,
timeouts, readiness, and graceful resource cleanup. It does not construct the
native agent, model, tools, or domain authorization policy.

```mermaid
classDiagram
    class AgentDefinition
    class WorkerSettings
    class ManagedAgentWorker
    class TrustedFactoryLoader
    class AgentFrameworkWorker
    class LangGraphWorker
    class ConversationRuntimeCache
    class ConversationEntrypoint
    class HttpConversationEngine
    class HostingFactory
    ManagedAgentWorker --> AgentDefinition : validates trusted definition
    ManagedAgentWorker --> WorkerSettings : uses operator settings
    ManagedAgentWorker --> ConversationEntrypoint : adapts request turns
    ConversationEntrypoint --> HttpConversationEngine : creates turns
    HttpConversationEngine --> ConversationRuntimeCache : leases conversations
    ManagedAgentWorker --> HostingFactory : registers HTTP surfaces
    AgentFrameworkWorker --> TrustedFactoryLoader : loads trusted factory
    LangGraphWorker --> TrustedFactoryLoader : loads trusted factory
    AgentFrameworkWorker --> ManagedAgentWorker : delegates lifecycle
    LangGraphWorker --> ManagedAgentWorker : delegates lifecycle
```

## Request lifecycle

```mermaid
sequenceDiagram
    participant Client
    participant Worker as ManagedAgentWorker
    participant Auth as Authentication policy
    participant Entrypoint as ConversationEntrypoint
    participant Engine as HttpConversationEngine
    participant Cache as ConversationRuntimeCache
    participant Factory as Trusted conversation factory
    Client->>Worker: endpoint request
    Worker->>Auth: authenticate caller
    Auth-->>Worker: verified principal
    Worker->>Entrypoint: normalized turn and principal
    Entrypoint->>Engine: respond to conversation turn
    Engine->>Cache: lease principal + conversation ID
    Cache->>Factory: build conversation on cache miss
    Factory-->>Cache: conversation and close behavior
    Cache-->>Engine: active lease
    Engine-->>Entrypoint: typed conversation reply
    Entrypoint-->>Client: provider-shaped HTTP response
```

The framework workers use `TrustedFactoryLoader` to load an
`AgentDefinition.factory` selected by deployment configuration; request data
cannot choose that module. The core worker requires explicit authentication
and identity namespace. Cache defaults and turn timeout live in
`WorkerSettings`; state is local to one process. Framework bindings add their
own tool-admission checks.

Source: [`managed_worker.py`](../../packages/python/agents/ygo74/agent_runtime/domains/endpoints/managed_worker.py)
and [`agent_definition.py`](../../packages/python/agents/ygo74/agent_runtime/domains/contracts/agent_definition.py).
Tests: [native agent definition](../../tests/integration/python/test_native_agent_definition.py)
and [native worker](../../tests/integration/python/test_native_worker.py).

See the [managed worker specification](../../spec/endpoints/managed-agent-worker.md)
and [native agent guide](../../docs/python/native-agents.md).
