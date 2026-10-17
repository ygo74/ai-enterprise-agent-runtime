# Agent Runtime Architecture

The agent runtime exposes provider-compatible HTTP endpoints and translates each
incoming request into a standard exchange request before invoking the registered
agent entrypoint. `HostingFactory` is the supported public API for registering an
agent and its endpoint surfaces.

An agent owns its use-case logic. System integrations belong behind explicit
tools or MCP servers; the agent should not embed direct enterprise API access.
OpenAI Responses and Chat Completions can share the same route and agent logic.