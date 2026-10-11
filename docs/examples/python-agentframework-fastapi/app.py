"""Platform-owned local worker; the agent package has no HTTP implementation."""

from deployment import settings
from definition import definition
from fastapi import FastAPI
from ygo74.agent_runtime.integrations.agentframework.worker import AgentFrameworkWorker


def create_app() -> FastAPI:
    """Build the FastAPI application for the configured native example agent."""
    return AgentFrameworkWorker(definition, settings).build_app()
