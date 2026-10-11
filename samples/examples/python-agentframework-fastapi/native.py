"""Build the native MAF agent without runtime dependencies."""

from agent_framework import Agent
from echo_client import EchoClient


def create_agent(context: object | None = None) -> Agent:
    """Return a normal MAF agent for either host."""
    del context
    return Agent(EchoClient(), name="native-echo", instructions="Echo the user's text.")
