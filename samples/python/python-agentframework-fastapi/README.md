# Microsoft Agent Framework examples

These examples use native Microsoft Agent Framework (MAF) agents and the
runtime's Python integration. They cover the same adoption tasks as the
[LangChain catalog](../python-langchain-fastapi/README.md), with MAF-specific
hosting and approval behavior.

## Examples

1. [Get started](01-get-started/README.md): develop a native echo agent and
   expose an application-owned `/ask` route.
2. [Human approval](02-human-in-the-loop/README.md): gate a MAF tool call with
   MAF's native approval request and an explicit resolver.
3. [RAG](03-rag/README.md): retrieve local Markdown evidence before asking a
   native MAF agent to answer.
4. [Native agent hosting](04-native-agent/README.md): host the same native
   agent through `AgentFrameworkWorker`.
5. [Managed worker](05-managed-worker/README.md): compose a native session with
   the framework-neutral `ManagedAgentWorker`.
6. [MCP configuration](06-mcp-configuration/README.md): load declarative MCP
   server/skill configuration for an MAF application. The loader is framework
   neutral; the application still owns tool admission and execution.

The MAF HTTP hosting path is a single-instance Python pilot. It does not claim
.NET/Java parity or production sandboxing. See the [native agent guide](../../../doc/python/native-agents.md)
for the supported input profile, admission rules, approval ticket bridge, and
operational limits.
