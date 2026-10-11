"""Exercise the installed OpenAI SDK with an in-process HTTP transport only."""

import json
import logging

import httpx
import pytest
from agent_framework import Agent, ToolApprovalMiddleware, tool
from agent_framework.openai import OpenAIChatClient
from openai import AsyncOpenAI
from ygo74.agent_runtime.integrations.agentframework.approval import ApprovalRound
from ygo74.agent_runtime.integrations.agentframework.binding import (
    AgentFrameworkSession,
)


class ResponsesTransport:
    """Return controlled Responses JSON/SSE and capture wire requests.

    Args:
        conversation: Optional provider conversation identifier.
        tools: Whether the first response requests a controlled tool.
        fail_call: Optional call index returning a provider error.
    """

    def __init__(self, conversation=None, *, tools=False, fail_call=None, tool_count=1):
        """Initialize the wire script.

        Args:
            conversation: Optional provider conversation identifier.
            tools: Whether to request a function on the first call.
            fail_call: Optional provider request to fail.
            tool_count: Number of parallel calls in the controlled response.
        """
        self.conversation = conversation
        self.tools = tools
        self.requests = []
        self.fail_call = fail_call
        self.tool_count = tool_count

    def __call__(self, request):
        """Respond without network access.

        Args:
            request: Actual serialized OpenAI SDK HTTP request.
        """
        body = json.loads(request.content)
        self.requests.append(body)
        index = len(self.requests)
        if index == self.fail_call:
            return httpx.Response(400, json={"error": {"message": "sensitive provider detail", "type": "invalid_request"}})
        output = [{
            "type": "message", "id": f"msg_{index}", "role": "assistant",
            "status": "completed", "content": [{"type": "output_text", "text": "controlled", "annotations": []}],
        }]
        if self.tools and index == 1:
            output = [{"type": "function_call", "id": f"fc_{number}", "call_id": f"call_{number}",
                       "name": "lookup", "arguments": "{}", "status": "completed"}
                      for number in range(1, self.tool_count + 1)]
        response = {
            "id": f"resp_{index}", "object": "response", "created_at": 1,
            "model": "controlled-model", "status": "completed", "output": output,
            "usage": {"input_tokens": 4, "output_tokens": 2, "total_tokens": 6},
            "conversation": {"id": self.conversation} if self.conversation else None,
        }
        if not body.get("stream"):
            return httpx.Response(200, json=response)
        events = [{"type": "response.created",
                   "response": {**response, "status": "in_progress", "output": []}}]
        for output_index, item in enumerate(output):
            events.append({"type": "response.output_item.added", "output_index": output_index, "item": item})
            if item["type"] == "message":
                events.append({"type": "response.output_text.delta", "item_id": item["id"],
                               "output_index": output_index, "content_index": 0, "delta": "controlled"})
            else:
                events.append({"type": "response.function_call_arguments.delta", "item_id": item["id"],
                               "output_index": output_index, "delta": "{}"})
            events.append({"type": "response.output_item.done", "output_index": output_index, "item": item})
        events.append({"type": "response.completed", "response": response})
        data = "".join(f"event: {item['type']}\ndata: {json.dumps(item)}\n\n" for item in events)
        return httpx.Response(200, headers={"content-type": "text/event-stream"}, text=data)


async def run_turn(session, stream):
    """Consume the real binding mode completely.

    Args:
        session: Bound native session.
        stream: Whether to stream.
    """
    if stream:
        return [event async for event in session.ask_stream("controlled user input")]
    return await session.ask_output("controlled user input")


@pytest.mark.asyncio
@pytest.mark.parametrize("modes", [(False, False), (True, True), (False, True), (True, False)])
@pytest.mark.parametrize("conversation", [None, "conv_controlled"])
async def test_installed_openai_sdk_continuation_mapping(modes, conversation, caplog):
    """Final completion must map to the next Responses wire request.

    Args:
        modes: Two real native response modes.
        conversation: Provider response or conversation mode.
        caplog: Captured safe diagnostics.
    """
    transport = ResponsesTransport(conversation)
    async with httpx.AsyncClient(transport=httpx.MockTransport(transport)) as http:
        sdk = AsyncOpenAI(api_key="synthetic-test-key", base_url="https://provider.invalid/v1", http_client=http)
        client = OpenAIChatClient(model="controlled-model", async_client=sdk)
        session = AgentFrameworkSession(Agent(client), require_provider_continuation=True)
        with caplog.at_level(logging.INFO):
            await run_turn(session, modes[0])
            await run_turn(session, modes[1])
        first, second = transport.requests
        assert "previous_response_id" not in first and "conversation" not in first
        key = "conversation" if conversation else "previous_response_id"
        assert second[key] == (conversation or "resp_1")
        assert first.get("store") is not False and second.get("store") is not False
        assert "controlled user input" not in caplog.text
        assert "resp_1" not in caplog.text and "conv_controlled" not in caplog.text
        records = [record for record in caplog.records if record.msg == "native provider continuity"]
        assert len(records) == 4
        assert records[1].provider_continuation_fingerprint == records[2].provider_continuation_fingerprint
        serialized = repr([record.__dict__ for record in records])
        for secret in ("controlled user input", "synthetic-test-key", "resp_1", "conv_controlled"):
            assert secret not in serialized


@pytest.mark.asyncio
@pytest.mark.parametrize("stream", [False, True])
async def test_tool_subcall_uses_last_provider_completion(stream):
    """Tool loop and next user turn continue the latest response, never a fragment.

    Args:
        stream: Real native response mode.
    """
    transport = ResponsesTransport(tools=True)
    calls = []

    def lookup():
        """Record the controlled read operation."""
        calls.append(True)
        return "controlled result"

    async with httpx.AsyncClient(transport=httpx.MockTransport(transport)) as http:
        sdk = AsyncOpenAI(api_key="synthetic-test-key", base_url="https://provider.invalid/v1", http_client=http)
        session = AgentFrameworkSession(
            Agent(OpenAIChatClient(model="controlled-model", async_client=sdk), tools=[lookup]),
            require_provider_continuation=True,
        )
        await run_turn(session, stream)
        await run_turn(session, not stream)
    assert calls == [True]
    assert [request.get("previous_response_id") for request in transport.requests] == [None, "resp_1", "resp_2"]


@pytest.mark.asyncio
@pytest.mark.parametrize("stream", [False, True])
async def test_explicit_provider_profile_rejects_missing_continuation(stream):
    """A provider-only profile cannot silently succeed without its history handle.

    Args:
        stream: Native response mode.
    """
    from test_agentframework_binding import NativeClient

    client = NativeClient()
    client.STORES_BY_DEFAULT = True
    session = AgentFrameworkSession(Agent(client), require_provider_continuation=True)
    with pytest.raises(RuntimeError, match="continuation"):
        await run_turn(session, stream)
    with pytest.raises(RuntimeError, match="invalidated"):
        await session.ask_output("follow-up")


class ControlledApproval:
    """Make deterministic test decisions, never infer them from model content.

    Args:
        approved: Explicit test decision.
    """

    def __init__(self, approved):
        """Retain the decision.

        Args:
            approved: Explicit decision for the proposed call.
        """
        self.approved = approved
        self.batches = 0

    def will_question(self, pending):
        """Charge a human round.

        Args:
            pending: Suspended test calls.
        """
        return True

    async def resolve(self, pending):
        """Answer the native batch explicitly.

        Args:
            pending: Suspended test calls.
        """
        self.batches += 1
        return ApprovalRound(tuple(item.answer(approved=self.approved) for item in pending), True)


@pytest.mark.asyncio
@pytest.mark.parametrize("approved", [False, True])
@pytest.mark.parametrize("stream", [False, True])
async def test_approval_and_refusal_preserve_provider_chain(approved, stream):
    """Approval sub-runs and follow-ups preserve the last complete response.

    Args:
        approved: Explicit test approval or refusal.
        stream: Native response mode before the mixed-mode follow-up.
    """
    transport, calls = ResponsesTransport(tools=True), []
    resolver = ControlledApproval(approved)

    @tool(approval_mode="always_require")
    def lookup():
        """Record the controlled gated side effect."""
        calls.append(True)
        return "controlled result"

    async with httpx.AsyncClient(transport=httpx.MockTransport(transport)) as http:
        sdk = AsyncOpenAI(api_key="synthetic-test-key", base_url="https://provider.invalid/v1", http_client=http)
        session = AgentFrameworkSession(
            Agent(OpenAIChatClient(model="controlled-model", async_client=sdk),
                  tools=[lookup], middleware=[ToolApprovalMiddleware()]),
            resolver=resolver, require_provider_continuation=True,
        )
        await run_turn(session, stream)
        await run_turn(session, not stream)
    assert calls == ([True] if approved else [])
    assert resolver.batches == 1
    assert [request.get("previous_response_id") for request in transport.requests] == [None, "resp_1", "resp_2"]


@pytest.mark.asyncio
@pytest.mark.parametrize("stream", [False, True])
@pytest.mark.parametrize("approved", [False, True])
@pytest.mark.parametrize("budget", [None, 1])
async def test_parallel_sdk_approval_dispatch_has_no_provider_usage_gap(stream, approved, budget):
    """SDK-only sequential approval prompts preserve real counts and continuation."""
    from ygo74.agent_runtime.domains.contracts.stream_events import (
        TerminalEvent,
        UsageEvent,
    )

    transport = ResponsesTransport(tools=True, tool_count=3)
    resolver, calls = ControlledApproval(approved), []

    @tool(approval_mode="always_require")
    def lookup():
        """Record the controlled gated operation."""
        calls.append(True)
        return "controlled result"

    async with httpx.AsyncClient(transport=httpx.MockTransport(transport)) as http:
        sdk = AsyncOpenAI(api_key="synthetic-test-key", base_url="https://provider.invalid/v1", http_client=http)
        session = AgentFrameworkSession(
            Agent(OpenAIChatClient(model="controlled-model", async_client=sdk),
                  tools=[lookup], middleware=[ToolApprovalMiddleware()]),
            resolver=resolver, require_provider_continuation=True,
            max_approval_rounds=budget or 25,
        )
        output = await run_turn(session, stream)
        if stream:
            assert sum(isinstance(item, TerminalEvent) for item in output) == 1
            usage = [item.usage for item in output if isinstance(item, UsageEvent)][-1]
            termination = output[-1].termination
        else:
            usage = output.usage
            termination = output.termination
        assert termination.status.value == ("success" if budget is None else "incomplete")
        assert (usage.input_tokens, usage.output_tokens, usage.total_tokens) == (8, 4, 12)
        if budget is None:
            await run_turn(session, not stream)
    assert resolver.batches == (3 if budget is None else 1)
    assert calls == ([True] * (3 if budget is None else 1) if approved else [])
    expected_chain = [None, "resp_1", "resp_2"] if budget is None else [None, "resp_1"]
    assert [request.get("previous_response_id") for request in transport.requests] == expected_chain


@pytest.mark.asyncio
@pytest.mark.parametrize("stores", [False, True])
@pytest.mark.parametrize("stream", [False, True])
async def test_missing_provider_handle_characterizes_history_selection(stores, stream):
    """Default profiles remain compatible, but provider storage without an ID loses context.

    Args:
        stores: Simulated service default storage.
        stream: Native mode for both turns.
    """
    from test_agentframework_binding import NativeClient

    class RecordingClient(NativeClient):
        """Retain only controlled transcript data inside this deterministic test."""

        STORES_BY_DEFAULT = stores

        def get_response(self, messages, **kwargs):
            """Record SDK messages.

            Args:
                messages: Controlled transcript.
                kwargs: Native arguments passed through.
            """
            transcripts.append(list(messages))
            return super().get_response(messages, **kwargs)

    transcripts = []
    session = AgentFrameworkSession(Agent(RecordingClient()))
    await run_turn(session, stream)
    await run_turn(session, stream)
    assert len(transcripts[1]) == (1 if stores else 3)


def test_provider_profile_refuses_local_configuration_before_execution():
    """An explicit provider requirement never changes or silently ignores store=False."""
    from test_agentframework_binding import NativeClient

    client = NativeClient()
    with pytest.raises(ValueError, match="conflicts"):
        AgentFrameworkSession(Agent(client, default_options={"store": False}), require_provider_continuation=True)
    assert client.modes == []


@pytest.mark.asyncio
@pytest.mark.parametrize("stream", [False, True])
async def test_real_provider_failure_never_becomes_success(stream):
    """SDK failures invalidate the binding and expose only sanitized errors.

    Args:
        stream: Native response mode.
    """
    transport = ResponsesTransport(fail_call=1)
    async with httpx.AsyncClient(transport=httpx.MockTransport(transport)) as http:
        sdk = AsyncOpenAI(api_key="synthetic-test-key", base_url="https://provider.invalid/v1", http_client=http)
        session = AgentFrameworkSession(Agent(OpenAIChatClient(model="controlled-model", async_client=sdk)))
        with pytest.raises(RuntimeError, match="Native agent execution failed") as error:
            await run_turn(session, stream)
        assert "sensitive provider detail" not in str(error.value)
        with pytest.raises(RuntimeError, match="invalidated"):
            await run_turn(session, False)


@pytest.mark.asyncio
async def test_stale_existing_handle_does_not_hide_a_missing_provider_result():
    """Presence of an older service handle cannot validate the latest response."""
    from test_agentframework_binding import FunctionClient

    client = FunctionClient()
    session = AgentFrameworkSession(Agent(client), require_provider_continuation=True)
    session._session.service_session_id = "resp_old"
    with pytest.raises(RuntimeError, match="continuation"):
        await run_turn(session, True)


@pytest.mark.asyncio
async def test_shared_real_provider_keeps_two_session_chains_separate():
    """A reused client does not authorize continuation across conversations."""
    transport = ResponsesTransport()
    async with httpx.AsyncClient(transport=httpx.MockTransport(transport)) as http:
        sdk = AsyncOpenAI(api_key="synthetic-test-key", base_url="https://provider.invalid/v1", http_client=http)
        client = OpenAIChatClient(model="controlled-model", async_client=sdk)
        first, second = AgentFrameworkSession(Agent(client)), AgentFrameworkSession(Agent(client))
        await run_turn(first, True)
        await run_turn(second, False)
        await run_turn(first, False)
        await run_turn(second, True)
    assert [request.get("previous_response_id") for request in transport.requests] == [None, None, "resp_1", "resp_2"]
