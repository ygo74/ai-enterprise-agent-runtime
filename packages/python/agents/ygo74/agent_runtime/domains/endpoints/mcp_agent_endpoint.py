"""Expose one provider-neutral agent invocation as an MCP operation."""

from __future__ import annotations

import inspect
from collections.abc import AsyncIterable, Mapping
from typing import Any, cast

from mcp.server.fastmcp import Context, FastMCP
from mcp.server.fastmcp.exceptions import ToolError
from pydantic import BaseModel, ConfigDict
from starlette.requests import Request
from ygo74.agent_runtime.domains.auth.agent_principal import AgentPrincipal
from ygo74.agent_runtime.domains.auth.auth_context import AuthenticatedUserContext
from ygo74.agent_runtime.domains.auth.tokens import AccessToken
from ygo74.agent_runtime.domains.contracts.agent_output import (
    AgentOutput,
    TerminationStatus,
)
from ygo74.agent_runtime.domains.contracts.exchange_models import (
    StandardExchangeResponse,
)
from ygo74.agent_runtime.domains.contracts.invocation_context import (
    AgentInvocationContext,
    AgentInvocationContextScope,
)
from ygo74.agent_runtime.domains.contracts.output_serialization import (
    AgentOutputSerializer,
)
from ygo74.agent_runtime.domains.discovery.agent_descriptor import AgentDescriptor
from ygo74.agent_runtime.domains.endpoints.conversation_payloads import (
    DEFAULT_CONVERSATION,
)
from ygo74.agent_runtime.domains.endpoints.header_forwarding import CONVERSATION_KEY
from ygo74.agent_runtime.domains.endpoints.hosting_factory import AgentEntrypoint
from ygo74.agent_runtime.domains.mapping.output_normalizer import OutputNormalizer
from ygo74.agent_runtime.domains.mcpserver.host import AUTH_CONTEXT_KEY


class McpAgentResponse(BaseModel):
    """Structured result returned by the MCP agent operation.

    Args:
        status: Normalized termination status of the agent output.
        conversation_id: Caller-scoped conversation used for this invocation.
        output: Explicitly tagged serialization of the typed agent output.
        metadata: Safe exchange metadata, including pending confirmation identifiers.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    status: str
    conversation_id: str
    output: dict[str, Any]
    metadata: dict[str, list[str]]


class McpAgentEndpoint:
    """Build the FastMCP server exposing the agent's ``invoke_agent`` operation.

    The authenticated identity is read from the ASGI request scope populated by
    ``McpServerHost``. MCP tool arguments contain only the user message and its
    caller-scoped conversation identifier.

    Args:
        entrypoint: Existing generic agent entrypoint used by HTTP surfaces.
        descriptor: Canonical agent metadata used for the MCP server identity and route key.
    """

    def __init__(
        self, entrypoint: AgentEntrypoint, descriptor: AgentDescriptor
    ) -> None:
        """Retain the invocation callback and descriptor for server construction.

        Args:
            entrypoint: Existing generic agent entrypoint.
            descriptor: Canonical agent metadata.
        """
        self._entrypoint = entrypoint
        self._descriptor = descriptor
        self._output_normalizer = OutputNormalizer()
        self._output_serializer = AgentOutputSerializer()

    def build_server(self) -> FastMCP:
        """Create one FastMCP server and register its public agent operation."""
        server = FastMCP(
            name=self._descriptor.display_name,
            instructions=self._descriptor.description,
            host="0.0.0.0",
        )

        @server.tool(
            name="invoke_agent",
            description="Send one message to this agent and continue the supplied conversation.",
            structured_output=True,
        )
        async def invoke_agent(
            message: str,
            conversation_id: str = DEFAULT_CONVERSATION,
            *,
            ctx: Context[Any, Any, Any],
        ) -> McpAgentResponse:
            """Invoke the existing agent entrypoint with authenticated request context.

            Args:
                message: User message to send to the agent.
                conversation_id: Caller-scoped conversation to continue, defaulting to ``default``.
                ctx: FastMCP request context containing the authenticated ASGI request.
            """
            response = await self._invoke(message, conversation_id, ctx)
            return McpAgentResponse.model_validate(response)

        return server

    async def _invoke(
        self,
        message: str,
        conversation_id: str,
        context: Context[Any, Any, Any],
    ) -> dict[str, Any]:
        """Normalize one MCP tool call and project the typed agent exchange.

        Args:
            message: User-authored message supplied to the MCP tool.
            conversation_id: Caller-scoped conversation identifier.
            context: FastMCP request context injected by the SDK.

        Raises:
            ToolError: The authenticated request is missing or the agent invocation fails.
        """
        authenticated_context = self._authenticated_context(context)
        normalized_conversation_id = conversation_id.strip() or DEFAULT_CONVERSATION
        request_id = str(context.request_id)
        principal = AgentPrincipal.from_context(
            authenticated_context, require_email=False
        )
        payload: dict[str, Any] = {
            "request_id": request_id,
            "route_key": self._descriptor.route_key,
            "input": message,
            "metadata": {CONVERSATION_KEY: normalized_conversation_id},
            "auth_context": authenticated_context.to_dict(),
        }
        invocation_context = AgentInvocationContext(
            principal=principal,
            request_id=request_id,
            conversation_id=normalized_conversation_id,
            subject_token=(
                authenticated_context.verified_access_token
                if isinstance(authenticated_context.verified_access_token, AccessToken)
                else None
            ),
        )

        try:
            # Bind the verified principal and token while the existing entrypoint builds its typed conversation turn.
            with AgentInvocationContextScope.bind(invocation_context):
                result = self._entrypoint(payload)
                if inspect.isawaitable(result):
                    result = await result
            if isinstance(result, AsyncIterable):
                raise ToolError("This MCP operation does not support streaming output")

            response_metadata: Mapping[str, object] = {}
            if isinstance(result, StandardExchangeResponse):
                response_metadata = result.metadata
            output = cast(
                AgentOutput,
                self._output_normalizer.normalize(result, request_id=request_id),
            )
            if output.termination.status is TerminationStatus.FAILED:
                raise ToolError("Agent invocation failed")

            pending_confirmations = response_metadata.get("pending_confirmations", [])
            if not isinstance(pending_confirmations, (list, tuple)) or not all(
                isinstance(item, str) for item in pending_confirmations
            ):
                raise ToolError("Agent returned invalid confirmation metadata")
            return {
                "status": output.termination.status.value,
                "conversation_id": normalized_conversation_id,
                "output": self._output_serializer.serialize(output),
                "metadata": {
                    "pending_confirmations": list(pending_confirmations),
                },
            }
        except ToolError:
            raise
        except Exception as failure:
            raise ToolError("Agent invocation failed") from failure

    @staticmethod
    def _authenticated_context(
        context: Context[Any, Any, Any],
    ) -> AuthenticatedUserContext:
        """Read and validate the identity established by the MCP host middleware.

        Args:
            context: FastMCP request context injected by the SDK.

        Raises:
            ToolError: The host did not attach a valid authenticated context.
        """
        request = context.request_context.request
        if not isinstance(request, Request):
            raise ToolError("Authenticated request context is unavailable")
        scope = request.scope
        authenticated_context = scope.get(AUTH_CONTEXT_KEY)
        if (
            not isinstance(authenticated_context, AuthenticatedUserContext)
            or not isinstance(authenticated_context.identity.user_id, str)
            or not authenticated_context.identity.user_id.strip()
        ):
            raise ToolError("Authenticated request context is unavailable")
        return authenticated_context
