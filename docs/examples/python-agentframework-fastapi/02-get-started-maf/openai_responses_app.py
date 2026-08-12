from __future__ import annotations

import logging

from fastapi import FastAPI

from agent_solution_architect import build_solution_architect_agent
from env_loader import ensure_env_loaded
from ygo74.agent_runtime import add_ai_endpoints, create_agent_framework_entrypoint

ensure_env_loaded()

logging.basicConfig(level=logging.INFO)
logging.getLogger("ygo74.agent_runtime").setLevel(logging.DEBUG)


app = FastAPI(title="AI Solution Architect - Microsoft Agent Framework Example")

# create_agent_framework_entrypoint wraps build_solution_architect_agent (pure business
# logic: model, tools, instructions) into an add_ai_endpoints-compatible entrypoint that
# transparently handles single-shot responses, real token-by-token streaming, and inline
# tool-call notices for chat UIs (e.g. LibreChat). This is the exact same runtime helper
# contract as create_langchain_agent_entrypoint used in the 01-get-started (LangChain)
# example -- ygo74.agent_runtime itself has no dependency on either framework.
solution_architect_entrypoint = create_agent_framework_entrypoint(build_solution_architect_agent)

add_ai_endpoints(
    app,
    solution_architect_entrypoint,
    default_route_key="ai-solution-architect",
    enable_openai_responses=True,
    enable_openai_chat_completions=True,
    enable_anthropic_messages=False,
)
