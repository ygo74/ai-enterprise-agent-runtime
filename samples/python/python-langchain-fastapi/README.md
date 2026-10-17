# Python LangChain + FastAPI Examples

Each example lives in its own folder. Agent examples have two entrypoints: one
uses FastAPI and LangChain directly; the other uses the runtime. Compare them to
see which agent code stays and which hosting code the runtime takes over.

For package selection, installation, and an overview of the Python runtime, see
the [Python library documentation](../../../doc/python/README.md).

## Available examples

- `01-get-started`: keep the Solution Architect agent and Microsoft Learn tool; compare a custom `/ask` route with runtime OpenAI endpoints.
- `02-human-in-the-loop`: compare a developer-owned LangGraph approval flow with the runtime worker's confirmation tickets.
- `03-rag`: keep the RAG pipeline and local Markdown index; compare custom JSON/text responses with runtime OpenAI endpoints.
- `04-native-langgraph`: keep an offline LangGraph and replace the custom `/ask` host with the `LangGraphWorker` facade.
- `05-managed-worker`: use the same offline graph with `ManagedAgentWorker` directly and provide a custom conversation factory.
- `06-mcp-configuration`: load typed MCP server YAML, share one connection across skills, and validate configuration without contacting a server.

## How to compare the two entrypoints

Examples 01 and 03 compare application-owned routes with runtime endpoints.
Example 02 compares developer-owned approval with runtime confirmation tickets.
Example 04 uses the native LangGraph worker facade. Example 05 uses the lower-
level worker API with an application-provided conversation factory. Example 06
loads and validates MCP configuration without contacting a server.

- Each example folder contains source files, a `requirements.txt`, and a README
  with run instructions. Environment files or `.env.sample` templates are
  included when the particular example uses them.
