"""Build the native MAF agent used by the lower-level managed-worker sample."""

from agent_framework import Agent

from echo_client import EchoClient


def create_agent() -> Agent:
    """Return the local echo agent shared by each worker conversation.

    Returns:
        Agent: A tool-free native MAF agent.
    """
    return Agent(EchoClient(), name="managed-maf-echo", instructions="Echo the user's text.")
