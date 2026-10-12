"""Carry trusted caller context to each outbound MCP HTTP request."""

from __future__ import annotations

import re
from collections.abc import AsyncIterator, Iterator, Mapping
from contextlib import aclosing, contextmanager
from contextvars import ContextVar, Token
from dataclasses import dataclass, field, replace
from typing import Any, TypeVar

from ygo74.agent_runtime.domains.auth.agent_principal import AgentPrincipal
from ygo74.agent_runtime.domains.auth.tokens import (
    AccessToken,
    DelegatedTokenRequest,
    DelegatedTokenSource,
    TokenExchangeError,
)
from ygo74.agent_runtime.domains.contracts.conversation import ConversationTurn
from ygo74.agent_runtime.domains.mcp.configuration import (
    McpDelegatedOAuthSettings,
    McpHeaderContextToken,
)
from ygo74.agent_runtime.domains.mcp.mcp_errors import McpBindingError

_CONTEXT_TOKEN = re.compile(r"\{\{(?P<name>[^{}]+)\}\}")
_ItemT = TypeVar("_ItemT")
_current_mcp_request: ContextVar[McpRequestContext | None] = ContextVar(
    "agent_runtime_mcp_request_context", default=None
)


@dataclass(frozen=True, slots=True, repr=False)
class McpRequestContext:
    """Trusted identity and correlation values for one agent invocation.

    Args:
        principal (AgentPrincipal | None): Authenticated, credential-free caller identity.
        request_id (str): Runtime correlation identifier for the current turn.
        conversation_id (str): Caller-scoped conversation or session identifier.
        subject_token (AccessToken | None): Verified inbound token retained only for OBO exchange.
    """

    principal: AgentPrincipal | None = None
    request_id: str = ""
    conversation_id: str = ""
    subject_token: AccessToken | None = field(default=None, repr=False, compare=False)

    @classmethod
    def for_turn(
        cls,
        turn: ConversationTurn,
        request_id: str,
        subject_token: AccessToken | None = None,
    ) -> McpRequestContext:
        """Create the outbound context from a verified conversation turn.

        Args:
            turn (ConversationTurn): Typed turn produced by the authenticated payload reader.
            request_id (str): Correlation identifier assigned by the endpoint.
            subject_token (AccessToken | None): Verified inbound token, when JWT auth was used.
        """
        return cls(
            principal=turn.principal,
            request_id=request_id,
            conversation_id=turn.conversation_id,
            subject_token=subject_token,
        )

    def with_turn(self, turn: ConversationTurn, request_id: str) -> McpRequestContext:
        """Add typed identity and conversation routing to the current request context.

        Args:
            turn (ConversationTurn): Typed turn produced by the authenticated payload reader.
            request_id (str): Correlation identifier assigned by the endpoint.
        """
        return replace(
            self,
            principal=turn.principal,
            request_id=request_id,
            conversation_id=turn.conversation_id,
        )

    def values(self) -> Mapping[McpHeaderContextToken, str | None]:
        """Return only the documented identity and request values for interpolation."""
        principal = self.principal
        return {
            McpHeaderContextToken.USER_ID: None
            if principal is None
            else principal.subject,
            McpHeaderContextToken.USER_EMAIL: None
            if principal is None or not principal.email
            else principal.email,
            McpHeaderContextToken.USER_NAME: (
                None
                if principal is None or not principal.display_name
                else principal.display_name
            ),
            McpHeaderContextToken.USER_ROLES: (
                None if principal is None else ",".join(sorted(principal.roles))
            ),
            McpHeaderContextToken.REQUEST_ID: self.request_id or None,
            McpHeaderContextToken.CONVERSATION_ID: self.conversation_id or None,
            McpHeaderContextToken.SESSION_ID: self.conversation_id or None,
        }

    def __repr__(self) -> str:
        """Describe the available context without exposing user or token values."""
        return (
            f"{type(self).__name__}(principal_present={self.principal is not None}, "
            f"request_id_present={bool(self.request_id)}, conversation_id_present={bool(self.conversation_id)}, "
            f"subject_token_present={self.subject_token is not None})"
        )


class McpRequestContextScope:
    """Bind an invocation's trusted context to async tasks that issue MCP calls."""

    @staticmethod
    def current() -> McpRequestContext | None:
        """Return the context inherited by the current async task, if any."""
        return _current_mcp_request.get()

    @staticmethod
    @contextmanager
    def bind(context: McpRequestContext) -> Iterator[None]:
        """Set and restore the current request context around one operation.

        Args:
            context (McpRequestContext): Trusted identity, request, and conversation values for this invocation.
        """
        token: Token[McpRequestContext | None] = _current_mcp_request.set(context)
        try:
            yield
        finally:
            _current_mcp_request.reset(token)

    @staticmethod
    async def iterate(
        source: AsyncIterator[_ItemT],
        context: McpRequestContext,
    ) -> AsyncIterator[_ItemT]:
        """Pull and close a stream under its request context without crossing yields.

        Args:
            source (AsyncIterator[_ItemT]): Streaming result whose work must inherit caller context.
            context (McpRequestContext): Trusted identity, request, and conversation values for this invocation.
        """
        try:
            while True:
                with McpRequestContextScope.bind(context):
                    try:
                        item = await anext(source)
                    except StopAsyncIteration:
                        return
                yield item
        finally:
            with McpRequestContextScope.bind(context):
                async with aclosing(source):
                    pass


class McpRequestContextRegistry:
    """Associate MCP JSON-RPC request IDs with their originating agent turns."""

    def __init__(self) -> None:
        """Create an empty, connection-local map of outbound request contexts."""
        self._contexts: dict[str | int, McpRequestContext] = {}

    def register(self, request_id: str | int, context: McpRequestContext) -> None:
        """Store a context until the matching HTTP request begins.

        Args:
            request_id (str | int): JSON-RPC identifier generated by the MCP client session.
            context (McpRequestContext): Turn context to use for the corresponding HTTP request.
        """
        self._contexts[request_id] = context

    def take(self, request_id: str | int) -> McpRequestContext | None:
        """Remove and return a request context so it cannot leak into another send.

        Args:
            request_id (str | int): JSON-RPC identifier found in the HTTP request body.
        """
        return self._contexts.pop(request_id, None)

    def discard(self, request_id: str | int) -> None:
        """Forget a context if its message could not be queued for transport.

        Args:
            request_id (str | int): JSON-RPC identifier generated by the MCP client session.
        """
        self._contexts.pop(request_id, None)

    def clear(self) -> None:
        """Release any contexts whose outbound HTTP send was cancelled with the connection."""
        self._contexts.clear()


class McpOutboundHeaderResolver:
    """Render configured context headers and exchange OBO tokens per JSON-RPC ID.

    Args:
        configured_headers (Mapping[str, str]): Resolved configured values and context templates.
        contexts (McpRequestContextRegistry): Connection-local map keyed by JSON-RPC request ID.
        delegated_oauth (McpDelegatedOAuthSettings | None): Optional target audience and scopes.
        delegated_token_source (DelegatedTokenSource | None): Host-owned provider implementation for OBO exchange.
        error_factory (type[Exception]): Error type for invalid or missing context values.
    """

    def __init__(
        self,
        configured_headers: Mapping[str, str],
        contexts: McpRequestContextRegistry,
        *,
        delegated_oauth: McpDelegatedOAuthSettings | None = None,
        delegated_token_source: DelegatedTokenSource | None = None,
        error_factory: type[Exception] = McpBindingError,
    ) -> None:
        """Keep connection configuration and its request correlation registry.

        Args:
            configured_headers (Mapping[str, str]): Resolved configured values and context templates.
            contexts (McpRequestContextRegistry): Connection-local map keyed by JSON-RPC request ID.
            delegated_oauth (McpDelegatedOAuthSettings | None): Optional target audience and scopes.
            delegated_token_source (DelegatedTokenSource | None): Host-owned provider implementation for OBO exchange.
            error_factory (type[Exception]): Error type for invalid or missing context values.
        """
        self._configured_headers = dict(configured_headers)
        self._contexts = contexts
        self._delegated_oauth = delegated_oauth
        self._delegated_token_source = delegated_token_source
        self._error_factory = error_factory

    async def for_request(self, request_id: str | int) -> dict[str, str]:
        """Resolve headers using only context correlated with this JSON-RPC ID.

        Args:
            request_id (str | int): JSON-RPC identifier found in the HTTP request body.

        Raises:
            TokenExchangeError: the verified subject token or delegated token is invalid or unavailable.
        """
        context = self._contexts.take(request_id)
        headers = self._render_headers(context)
        if self._delegated_oauth is not None:
            headers["Authorization"] = await self._delegated_authorization(context)
        return headers

    def _render_headers(self, context: McpRequestContext | None) -> dict[str, str]:
        """Substitute validated header tokens or fail when the current value is absent.

        Args:
            context (McpRequestContext | None): Context correlated with the current JSON-RPC request.
        """
        if not any(
            _CONTEXT_TOKEN.search(value) for value in self._configured_headers.values()
        ):
            return dict(self._configured_headers)
        values = {} if context is None else context.values()
        rendered: dict[str, str] = {}
        for name, template in self._configured_headers.items():
            rendered[name] = self._render_header(name, template, values)
        return rendered

    def _render_header(
        self,
        name: str,
        template: str,
        values: Mapping[McpHeaderContextToken, str | None],
    ) -> str:
        """Render one configured value while reporting only its header and token names.

        Args:
            name (str): Configured HTTP header name.
            template (str): Validated literal and context-token template.
            values (Mapping[McpHeaderContextToken, str | None]): Values for the current caller and turn.
        """

        def substitute(match: re.Match[str]) -> str:
            """Replace one prevalidated context token with its current request value.

            Args:
                match (re.Match[str]): Match for one validated context token.
            """
            token = McpHeaderContextToken(match.group("name"))
            value = values.get(token)
            if value is None:
                raise self._error_factory(
                    f"headers.{name} requires a value for {token.value}"
                )
            return value

        return _CONTEXT_TOKEN.sub(substitute, template)

    async def _delegated_authorization(self, context: McpRequestContext | None) -> str:
        """Exchange the verified subject token and validate the returned audience.

        Args:
            context (McpRequestContext | None): Context correlated with the current JSON-RPC request.

        Raises:
            TokenExchangeError: OBO prerequisites, exchange, or result validation failed.
        """
        settings = self._delegated_oauth
        source = self._delegated_token_source
        if settings is None or source is None:
            raise TokenExchangeError("delegated token exchange is not configured")
        if (
            context is None
            or context.principal is None
            or context.subject_token is None
        ):
            raise TokenExchangeError(
                "delegated token exchange requires a verified caller token"
            )
        request = DelegatedTokenRequest(
            principal=context.principal,
            subject_token=context.subject_token,
            audience=settings.audience,
            scopes=settings.scopes,
        )
        try:
            token: AccessToken = await source.token_for(request)
        except Exception:  # noqa: BLE001 - provider errors may contain the inbound credential.
            raise TokenExchangeError("delegated token exchange failed") from None
        if not isinstance(token, AccessToken) or token.audience != settings.audience:
            raise TokenExchangeError(
                "delegated token audience does not match the configured MCP audience"
            )
        return f"Bearer {token.expose()}"


def json_rpc_request_id(message: Any) -> str | int | None:
    """Return a JSON-RPC request identifier from an SDK session message.

    Args:
        message (Any): MCP SDK ``SessionMessage`` passed to its transport stream.
    """
    root = getattr(getattr(message, "message", None), "root", None)
    request_id = getattr(root, "id", None)
    return request_id if isinstance(request_id, (str, int)) else None
