"""Offline native graph factory used by the managed-worker example."""

from langchain.agents import create_agent
from langchain_core.language_models.fake_chat_models import FakeListChatModel
from ygo74.agent_runtime.domains.contracts.agent_definition import AgentFactoryContext


def build_graph(context: AgentFactoryContext) -> object:
    """Return one compiled, tool-free graph for the requested conversation."""
    del context
    return create_agent(
        model=FakeListChatModel(responses=["This answer came from an offline native LangGraph agent."]),
        tools=[],
        system_prompt="Answer briefly using the available context.",
    )
