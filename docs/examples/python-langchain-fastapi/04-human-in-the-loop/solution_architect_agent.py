"""The AI Solution Architect agent, with its research call gated.

The agent is the one from ``01-get-started``. Exactly one thing is added: the
Microsoft Learn search is suspended until a person approves it.

Why gate a read? Because the control is not about writing. Calling the MCP server
sends the user's question - which in an enterprise is rarely generic - to a third
party. Confirming that egress is a real decision, and it is the same mechanism
that would gate a send, a delete or a deployment. Nothing here pretends a search
is dangerous.
"""

from __future__ import annotations

import os
from typing import Any

from langchain.agents import create_agent
from langchain.agents.middleware import HumanInTheLoopMiddleware
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.memory import InMemorySaver

from env_loader import ensure_env_loaded
from langgraph_approval import LangGraphApprovalBridge
from mcp_mslearn_tool import mslearn_mcp_search

from ygo74.agent_runtime.domains.humanapproval.confirmation import ConfirmationPolicy
from ygo74.agent_runtime.domains.security.operations import OperationType, RiskLevel, ToolOperationDescriptor
from ygo74.agent_runtime.domains.security.permissions import Permission
from ygo74.agent_runtime.domains.security.user_context import UserContext

ensure_env_loaded()

SYSTEM_PROMPT = (
    "You are a Senior AI Solution Architect. "
    "Design production-ready AI architectures, justify tradeoffs, cite Microsoft Learn references, "
    "and provide clear migration and operations guidance. "
    "When documentation is needed, call the mslearn_mcp_search tool first."
)

RESEARCH = Permission("research", "query")

# The posture of every capability this agent exposes, in one place. The bridge
# reads it to configure the interrupts and the policy reads it to decide, so the
# two can never disagree about which operations are gated.
OPERATIONS: tuple[ToolOperationDescriptor, ...] = (
    ToolOperationDescriptor(
        tool_name="mslearn_mcp_search",
        operation_type=OperationType.READ,
        # READ, but not free: the question leaves the organisation. The risk is
        # disclosure, which is why it is classified rather than ignored.
        risk_level=RiskLevel.MEDIUM,
        required_permission=RESEARCH,
        confirmation_required_by_default=True,
    ),
)


def build_agent(policy: ConfirmationPolicy, user: UserContext, *, model: Any | None = None) -> Any:
    """Build the graph, with the gated tools declared to the middleware.

    A checkpointer is required, not optional: an interrupt suspends the graph,
    and resuming it later - in a *different* HTTP request - only works if the
    suspended state was saved somewhere.

    ``model`` is injectable so the approval path can be exercised without
    reaching a model provider. Everything that makes this example interesting -
    the interrupt, the ticket, the parser, the replay - happens around the model,
    not inside it.
    """
    chat_model = model or ChatOpenAI(model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"), temperature=1)
    interrupt_on = LangGraphApprovalBridge().interrupt_on(OPERATIONS, policy, user)

    return create_agent(
        model=chat_model,
        tools=[mslearn_mcp_search],
        system_prompt=SYSTEM_PROMPT,
        middleware=[HumanInTheLoopMiddleware(interrupt_on=interrupt_on)],
        checkpointer=InMemorySaver(),
    )


def answer_of(state: Any) -> str:
    """Read the assistant's reply out of a graph result."""
    messages = state.get("messages") if isinstance(state, dict) else None
    if not messages:
        return ""
    content = getattr(messages[-1], "content", "")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = [str(item.get("text", "")) for item in content if isinstance(item, dict)]
        return "\n".join(part for part in parts if part)
    return str(content)


def interrupts_of(state: Any) -> tuple[Any, ...]:
    """Read the interrupts a graph result carries, whatever the key is called."""
    if not isinstance(state, dict):
        return ()
    raw = state.get("__interrupt__") or ()
    return tuple(raw)
