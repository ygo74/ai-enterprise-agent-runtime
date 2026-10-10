"""Deterministic native chat client for offline reference-worker validation."""

from collections.abc import AsyncIterator, Awaitable, Mapping, Sequence
from typing import Any

from agent_framework import (
    BaseChatClient,
    ChatResponse,
    ChatResponseUpdate,
    Content,
    Message,
    ResponseStream,
)


class EchoClient(BaseChatClient[Any]):
    """Echo offline; its known inference token consumption is exactly zero."""

    def _inner_get_response(
        self, *, messages: Sequence[Message], stream: bool, options: Mapping[str, Any], **kwargs: Any,
    ) -> Awaitable[ChatResponse[Any]] | ResponseStream[ChatResponseUpdate, ChatResponse[Any]]:
        """Execute the selected native response mode.

        Args:
            messages: Native conversation history.
            stream: Native mode requested by MAF.
            options: SDK options, unused by this deterministic model.
            kwargs: Additional SDK arguments, unused by this model.
        """
        text = next((message.text for message in reversed(messages) if message.role == "user"), "")
        answer = f"Echo: {text}"
        if stream:
            return ResponseStream(self._updates(answer), finalizer=lambda _: ChatResponse(
                messages=Message("assistant", [Content.from_text(answer)]),
                usage_details={"input_token_count": 0, "output_token_count": 0},
            ))
        return self._response(answer)

    @staticmethod
    async def _response(answer: str) -> ChatResponse[Any]:
        """Return a normal native response.

        Args:
            answer: Model text to return.
        """
        return ChatResponse(messages=Message("assistant", [Content.from_text(answer)]),
                            usage_details={"input_token_count": 0, "output_token_count": 0})

    @staticmethod
    async def _updates(answer: str) -> AsyncIterator[ChatResponseUpdate]:
        """Yield native updates before the final response exists.

        Args:
            answer: Model text to emit incrementally.
        """
        yield ChatResponseUpdate(contents=[Content.from_usage(
            {"input_token_count": 0, "output_token_count": 0},
        )])
        for fragment in ("Echo: ", answer[6:]):
            yield ChatResponseUpdate(role="assistant", contents=[Content.from_text(fragment)])
