import asyncio
import importlib.util
from pathlib import Path
from types import ModuleType

import httpx
import pytest
from ygo74.agent_runtime.domains.contracts.agent_output import (
    AgentOutput,
    TextContent,
    TokenUsage,
)
from ygo74.agent_runtime.domains.contracts.stream_events import (
    ContentEnd,
    ContentStart,
    TerminalEvent,
    TextDelta,
    UsageEvent,
)


def _load_echo() -> ModuleType:
    path = Path(__file__).resolve().parents[3] / "docs" / "examples" / "python-fastapi-quickstart" / "app.py"
    spec = importlib.util.spec_from_file_location("typed_echo_example", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_echo_returns_typed_output_and_keeps_incremental_prefix_and_input() -> None:
    module = _load_echo()

    async def run() -> None:
        result = await module.echo_agent({"input": "hello"})
        assert isinstance(result, AgentOutput)
        assert result.contents == (TextContent("Echo: hello"),)
        assert result.usage == TokenUsage(
            input_tokens=0, output_tokens=0, total_tokens=0,
            cached_input_tokens=0, reasoning_output_tokens=0, cache_write_input_tokens=0,
        )
        stream = await module.echo_agent({"input": "hello", "stream": True})
        events = [event async for event in stream]
        assert events[0] == UsageEvent(result.usage)
        assert isinstance(events[1], ContentStart)
        assert [event.text for event in events if isinstance(event, TextDelta)] == ["Echo: ", "hello"]
        assert isinstance(events[-2], ContentEnd)
        assert isinstance(events[-1], TerminalEvent)

    asyncio.run(run())


def test_echo_anthropic_sdk_accepts_known_zero_usage_in_final_and_streamed_messages() -> None:
    anthropic = pytest.importorskip("anthropic")
    from anthropic import _base_client

    sdk_httpx = getattr(_base_client, "httpx2", getattr(_base_client, "httpx", None))
    assert sdk_httpx is not None
    module = _load_echo()

    async def run() -> None:
        async with sdk_httpx.AsyncClient(
            transport=sdk_httpx.ASGITransport(app=module.app), base_url="http://test",
        ) as client:
            sdk = anthropic.AsyncAnthropic(
                api_key="offline-test", base_url="http://test", http_client=client, max_retries=0,
            )
            message = await sdk.messages.create(
                model="echo-agent", max_tokens=64, messages=[{"role": "user", "content": "hello"}],
            )
            assert message.content[0].text == "Echo: hello"
            assert message.usage.input_tokens == message.usage.output_tokens == 0
            assert message.usage.cache_read_input_tokens == message.usage.cache_creation_input_tokens == 0
            async with sdk.messages.stream(
                model="echo-agent", max_tokens=64, messages=[{"role": "user", "content": "hello"}],
            ) as stream:
                assert [delta async for delta in stream.text_stream] == ["Echo: ", "hello"]
                completed = await stream.get_final_message()
            assert completed.content[0].text == "Echo: hello"
            assert completed.usage.input_tokens == completed.usage.output_tokens == 0
            assert completed.usage.cache_read_input_tokens == completed.usage.cache_creation_input_tokens == 0

    asyncio.run(run())


def test_echo_openai_sdk_accepts_known_zero_usage_and_preserves_incremental_text() -> None:
    openai = pytest.importorskip("openai")
    module = _load_echo()

    async def run() -> None:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=module.app), base_url="http://test",
        ) as client:
            sdk = openai.AsyncOpenAI(
                api_key="offline-test", base_url="http://test/v1", http_client=client, max_retries=0,
            )
            response = await sdk.responses.create(model="echo-agent", input="hello")
            assert response.output_text == "Echo: hello"
            assert response.usage.input_tokens == response.usage.output_tokens == response.usage.total_tokens == 0
            assert response.usage.input_tokens_details.cached_tokens == 0
            assert response.usage.output_tokens_details.reasoning_tokens == 0
            stream = await sdk.responses.create(model="echo-agent", input="hello", stream=True)
            events = [event async for event in stream]
            assert [event.delta for event in events if event.type == "response.output_text.delta"] == ["Echo: ", "hello"]
            assert events[-1].type == "response.completed"
            completed_usage = events[-1].response.usage
            assert completed_usage.input_tokens == completed_usage.output_tokens == completed_usage.total_tokens == 0
            assert completed_usage.input_tokens_details.cached_tokens == 0
            assert completed_usage.output_tokens_details.reasoning_tokens == 0

            chat = await sdk.chat.completions.create(
                model="echo-agent", messages=[{"role": "user", "content": "hello"}],
            )
            assert chat.choices[0].message.content == "Echo: hello"
            assert chat.usage.prompt_tokens == chat.usage.completion_tokens == chat.usage.total_tokens == 0
            assert chat.usage.prompt_tokens_details.cached_tokens == 0
            assert chat.usage.completion_tokens_details.reasoning_tokens == 0
            chat_stream = await sdk.chat.completions.create(
                model="echo-agent", messages=[{"role": "user", "content": "hello"}], stream=True,
                stream_options={"include_usage": True},
            )
            chunks = [chunk async for chunk in chat_stream]
            assert [choice.delta.content for chunk in chunks for choice in chunk.choices
                    if choice.delta.content] == ["Echo: ", "hello"]
            snapshots = [chunk.usage for chunk in chunks if chunk.usage is not None]
            assert snapshots
            assert all(usage.total_tokens == usage.prompt_tokens == usage.completion_tokens == 0
                       for usage in snapshots)
            assert all(usage.prompt_tokens_details.cached_tokens == 0
                       and usage.completion_tokens_details.reasoning_tokens == 0 for usage in snapshots)

    asyncio.run(run())
