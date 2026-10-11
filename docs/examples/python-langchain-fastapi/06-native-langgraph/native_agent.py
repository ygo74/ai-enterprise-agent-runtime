"""Offline native graph factory used by the managed-worker example."""

from langchain.agents import create_agent
from langchain_core.language_models.fake_chat_models import FakeListChatModel


def build_graph(context: object) -> object:
    """Return one compiled, tool-free graph for either host entrypoint."""
    del context
    return create_agent(
        model=FakeListChatModel(responses=["This answer came from an offline native LangGraph agent."]),
        tools=[],
        system_prompt="Answer briefly using the available context.",
    )
