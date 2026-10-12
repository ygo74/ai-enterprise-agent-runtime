# Python LangChain + FastAPI Examples

Each example lives in its own folder. Agent examples have two entrypoints: one
uses FastAPI and LangChain directly; the other uses the runtime. Compare them to
see which agent code stays and which hosting code the runtime takes over.

For package selection, installation, and an overview of the Python runtime, see
the [Python library documentation](../../../doc/python/README.md).

## Available examples

- `01-get-started`: keep the Solution Architect agent and Microsoft Learn tool; compare a custom `/ask` route with runtime OpenAI endpoints.
- `04-human-in-the-loop`: compare a developer-owned LangGraph approval flow with the runtime worker's confirmation tickets.
- `05-rag`: keep the RAG pipeline and local Markdown index; compare custom JSON/text responses with runtime OpenAI endpoints.
- `06-native-langgraph`: keep an offline LangGraph and replace the custom `/ask` host with the `LangGraphWorker` facade.
- `07-managed-worker`: use the same offline graph with `ManagedAgentWorker` directly and provide a custom conversation factory.
- `08-mcp-configuration`: load typed MCP server YAML, share one connection across skills, and validate configuration without contacting a server.

## How to compare the two entrypoints

In each agent example, start with the developer-owned entrypoint. It calls
LangChain directly and owns its route and response. Then open the runtime
entrypoint. The agent or RAG work stays in the application; the runtime adds
standard endpoints and handles the shared HTTP and conversation work.

Examples 01 and 05 show how to connect an existing application to runtime
contracts. Example 04 shows a custom conversation factory for domain rules.
Example 06 is the shorter LangGraph worker setup. Example 07 shows the lower
level worker API for applications that need to build their own conversation.

- Each example folder contains source files, a `requirements.txt`, and a README
  with run instructions. Environment files or `.env.sample` templates are
  included when the particular example uses them.
