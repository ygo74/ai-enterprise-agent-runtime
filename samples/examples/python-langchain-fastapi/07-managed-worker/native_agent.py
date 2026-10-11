"""Offline LangGraph builder shared by both hosting approaches."""

from langchain.agents import create_agent
from langchain_core.language_models.fake_chat_models import FakeListChatModel


def build_graph(context: object) -> object:
    """Build a deterministic, tool-free graph for one conversation."""
    del context
    return create_agent(
        model=FakeListChatModel(responses=["This answer came from the managed-worker example."]),
        tools=[],
        system_prompt="Answer briefly using the available context.",
    )
