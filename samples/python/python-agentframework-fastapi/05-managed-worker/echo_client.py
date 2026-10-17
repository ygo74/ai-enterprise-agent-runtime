"""Deterministic MAF chat client for the managed-worker example."""

from collections.abc import AsyncIterator, Awaitable, Mapping, Sequence
from typing import Any

from agent_framework import BaseChatClient, ChatResponse, ChatResponseUpdate, Content, Message, ResponseStream


class EchoClient(BaseChatClient[Any]):
    """Return the latest user text without an external model call."""

    def _inner_get_response(
        self, *, messages: Sequence[Message], stream: bool, options: Mapping[str, Any], **kwargs: Any,
    ) -> Awaitable[ChatResponse[Any]] | ResponseStream[ChatResponseUpdate, ChatResponse[Any]]:
        """Build the requested normal or streaming response.

        Args:
            messages: Native conversation history supplied by MAF.
            stream: Whether MAF requested incremental output.
            options: SDK options, unused by this deterministic client.
            kwargs: Additional SDK settings, unused by this client.

        Returns:
            Awaitable[ChatResponse[Any]] | ResponseStream[ChatResponseUpdate, ChatResponse[Any]]:
                Native final response or stream.
        """
        question = next((item.text for item in reversed(messages) if item.role == "user"), "")
        answer = f"Echo: {question}"
        if stream:
            return ResponseStream(
                self._updates(answer),
                finalizer=lambda _: ChatResponse(
                    messages=Message("assistant", [Content.from_text(answer)]),
                    usage_details={"input_token_count": 0, "output_token_count": 0},
                ),
            )
        return self._response(answer)

    @staticmethod
    async def _response(answer: str) -> ChatResponse[Any]:
        """Return one native response with known zero inference usage.

        Args:
            answer: Text to return.

        Returns:
            ChatResponse[Any]: Completed native response.
        """
        return ChatResponse(
            messages=Message("assistant", [Content.from_text(answer)]),
            usage_details={"input_token_count": 0, "output_token_count": 0},
        )

    @staticmethod
    async def _updates(answer: str) -> AsyncIterator[ChatResponseUpdate]:
        """Yield usage followed by two correlated text fragments.

        Args:
            answer: Complete echo to split into stream fragments.

        Yields:
            ChatResponseUpdate: Native usage or text update.
        """
        yield ChatResponseUpdate(contents=[Content.from_usage(
            {"input_token_count": 0, "output_token_count": 0},
        )])
        yield ChatResponseUpdate(role="assistant", contents=[Content.from_text("Echo: ")])
        yield ChatResponseUpdate(role="assistant", contents=[Content.from_text(answer[6:])])
