"""Execution characterization independent of Mail and proprietary registries."""

import asyncio

import pytest
from agent_framework import (
    Agent,
    AgentResponseUpdate,
    BaseChatClient,
    ChatResponse,
    ChatResponseUpdate,
    Content,
    FunctionInvocationLayer,
    Message,
    ResponseStream,
)
from ygo74.agent_runtime.domains.contracts.agent_output import (
    Notification,
    TerminationStatus,
)
from ygo74.agent_runtime.domains.contracts.stream_events import (
    ContentEvent,
    TerminalEvent,
    UsageEvent,
)
from ygo74.agent_runtime.integrations.agentframework.binding import (
    AgentFrameworkSession,
)


class NativeClient:
    def __init__(self):
        self.modes = []
        self.closed = False

    def get_response(self, messages, *, stream=False, options=None, **kwargs):
        from agent_framework import ChatResponse

        self.modes.append(stream)
        async def updates():
            try:
                yield AgentResponseUpdate(role="assistant", contents=[Content.from_text("hello")])
                yield AgentResponseUpdate(contents=[Content.from_usage(
                    {"input_token_count": 4, "output_token_count": 2},
                )])
            finally:
                self.closed = True
        if stream:
            return ResponseStream(updates(), finalizer=lambda _: ChatResponse(
                messages=[Message("assistant", ["hello"])],
                usage_details={"input_token_count": 4, "output_token_count": 2},
            ))
        async def response():
            return ChatResponse(messages=[Message("assistant", ["hello"])],
                                usage_details={"input_token_count": 4, "output_token_count": 2})
        return response()


@pytest.mark.asyncio
async def test_native_modes_are_not_simulated():
    client = NativeClient()
    session = AgentFrameworkSession(Agent(client, name="native"))
    assert await session.ask("one") == "hello"
    events = [event async for event in session.ask_stream("two")]
    assert client.modes == [False, True]
    assert sum(isinstance(event, TerminalEvent) for event in events) == 1
    assert sum(isinstance(event, UsageEvent) for event in events) == 1
    assert client.closed


@pytest.mark.asyncio
async def test_cancelled_consumer_closes_native_producer():
    client = NativeClient()
    session = AgentFrameworkSession(Agent(client))
    stream = session.ask_stream("one")
    await anext(stream)
    await stream.aclose()
    assert client.closed
    with pytest.raises(RuntimeError, match="invalidated"):
        await session.ask("two")


class FunctionClient(FunctionInvocationLayer, BaseChatClient):
    """Retain the real provider stream so garbage collection cannot hide leaks."""

    def __init__(self, *, tool_name="lookup", pause=False):
        """Configure a retained scripted provider.

        Args:
            tool_name: Function requested on the first model turn.
            pause: Whether to suspend the active pull for cancellation testing.
        """
        super().__init__()
        self.tool_name = tool_name
        self.pause = pause
        self.awaiting = asyncio.Event()
        self.resume = asyncio.Event()
        self.provider_streams = []
        self.closed = []
        self.finalized = []
        self.cleaned = []

    def _inner_get_response(self, *, messages, stream, options, **kwargs):
        """Offer a real function call, with explicit provider cleanup.

        Args:
            messages: Native transcript supplied by the SDK.
            stream: Native streaming mode.
            options: Effective provider options.
            kwargs: Additional native invocation arguments.
        """
        index = len(self.provider_streams)
        contents = ([Content.from_function_call("call", self.tool_name, arguments={})] if index == 0
                    else [Content.from_text("after")])
        async def updates():
            """Yield scripted provider updates and record generator cleanup."""
            try:
                yield ChatResponseUpdate(role="assistant", contents=contents)
                if self.pause:
                    self.awaiting.set()
                    await self.resume.wait()
                yield ChatResponseUpdate(role="assistant", contents=[Content.from_text("after")])
            finally:
                self.closed.append(index)
        def finalize(updates):
            """Record successful finalization of the collected updates.

            Args:
                updates: Updates consumed by the native SDK.
            """
            self.finalized.append(index)
            return ChatResponse(messages=Message("assistant", contents))
        response = ResponseStream(updates(), finalizer=finalize, cleanup_hooks=[lambda: self.cleaned.append(index)])
        self.provider_streams.append(response)
        return response


@pytest.mark.asyncio
async def test_early_close_releases_function_invocation_provider_without_finalizing():
    """Closing the binding must close the provider, not merely the SDK loop."""
    client = FunctionClient()
    def lookup():
        """Return controlled tool output."""
        return "result"
    session = AgentFrameworkSession(Agent(client, tools=[lookup]), tool_names=("lookup",))
    stream = session.ask_stream("one")
    await anext(stream)
    await stream.aclose()
    assert client.closed == [0]
    assert client.cleaned == [0]
    assert client.finalized == []
    with pytest.raises(RuntimeError, match="invalidated"):
        await session.ask("two")


@pytest.mark.asyncio
async def test_early_close_after_tool_execution_closes_next_provider():
    """Real function invocation must not orphan a subsequent provider stream."""
    client, calls = FunctionClient(), []
    def lookup():
        """Record actual native function execution."""
        calls.append(True)
        return "result"
    session = AgentFrameworkSession(Agent(client, tools=[lookup]), tool_names=("lookup",))
    stream = session.ask_stream("one")
    async for _ in stream:
        if len(client.provider_streams) == 2:
            break
    await stream.aclose()
    assert calls == [True]
    assert client.closed == [0, 1]
    assert client.cleaned == [0, 1]
    assert client.finalized == [0]


@pytest.mark.asyncio
async def test_shared_client_stream_ownership_is_per_invocation():
    """Closing one native binding leaves another retained provider alive."""
    client = FunctionClient()
    def lookup():
        """Return controlled tool output."""
        return "result"
    first = AgentFrameworkSession(Agent(client, tools=[lookup]), tool_names=("lookup",)).ask_stream("one")
    second = AgentFrameworkSession(Agent(client, tools=[lookup]), tool_names=("lookup",)).ask_stream("two")
    await anext(first)
    await anext(second)
    await first.aclose()
    assert client.closed == [0]
    await second.aclose()
    assert client.closed == [0, 1]
    assert client.finalized == []


@pytest.mark.asyncio
async def test_task_cancellation_releases_real_function_provider():
    """Cancelling an active provider pull runs cleanup without a final response."""
    client = FunctionClient(pause=True)
    def lookup():
        """Return controlled tool output."""
        return "result"
    session = AgentFrameworkSession(Agent(client, tools=[lookup]), tool_names=("lookup",))
    async def consume():
        """Drive the binding until provider cancellation."""
        async for _ in session.ask_stream("one"):
            pass
    task = asyncio.create_task(consume())
    await client.awaiting.wait()
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert client.closed == [0]
    assert client.cleaned == [0]
    assert client.finalized == []
    with pytest.raises(RuntimeError, match="invalidated"):
        await session.ask("next")


def test_progress_has_no_raw_arguments_or_results():
    from ygo74.agent_runtime.integrations.agentframework.progress import (
        ToolProgressPolicy,
    )

    policy = ToolProgressPolicy(("lookup",))
    update = AgentResponseUpdate(role="assistant", contents=[
        Content.from_function_call("1", "lookup", arguments={"password": "PRIVATE"}),
        Content.from_function_result("1", result={"secret": "PRIVATE"}),
        Content.from_text_reasoning(text="PRIVATE"),
    ])
    events = policy.observe(update)
    assert len(events) == 2
    assert all(isinstance(event, ContentEvent) and isinstance(event.content, Notification) for event in events)
    assert "PRIVATE" not in repr(events)


def test_native_error_stays_failed():
    from ygo74.agent_runtime.integrations.agentframework.stream_adapter import (
        AgentFrameworkStreamAdapter,
    )

    adapter = AgentFrameworkStreamAdapter()
    adapter.convert_update(AgentResponseUpdate(contents=[Content(type="error", message="private error")]))
    adapter.convert_update(AgentResponseUpdate(finish_reason="stop"))
    assert adapter.finish()[-1].termination.status is TerminationStatus.FAILED


class ErrorClient(NativeClient):
    def get_response(self, messages, *, stream=False, options=None, **kwargs):
        from agent_framework import ChatResponse
        error = Content(type="error", message="PRIVATE provider error", error_code="private-provider-code")
        if stream:
            async def updates():
                try:
                    yield AgentResponseUpdate(role="assistant", contents=[error])
                    yield AgentResponseUpdate(role="assistant", finish_reason="stop")
                finally:
                    self.closed = True
            return ResponseStream(updates(), finalizer=lambda _: ChatResponse(messages=Message("assistant", [error])))
        async def response():
            return ChatResponse(messages=Message("assistant", [error]))
        return response()


@pytest.mark.asyncio
async def test_binding_sanitizes_native_errors_and_never_emits_success():
    client = ErrorClient()
    discarded = []
    session = AgentFrameworkSession(Agent(client), discard_authorizations=lambda: discarded.append(True))
    events = [event async for event in session.ask_stream("one")]
    terminals = [event for event in events if isinstance(event, TerminalEvent)]
    assert len(terminals) == 1
    assert terminals[0].termination.status is TerminationStatus.FAILED
    assert "PRIVATE" not in repr(events)
    assert "private-provider-code" not in repr(events)
    assert discarded and client.closed
    output = await AgentFrameworkSession(Agent(ErrorClient())).ask_output("two")
    assert output.termination.status is TerminationStatus.FAILED
    assert "PRIVATE" not in repr(output)
    with pytest.raises(RuntimeError, match="execution failed"):
        await AgentFrameworkSession(Agent(ErrorClient())).ask("three")


def test_parallel_partial_tool_updates_are_deduplicated_and_safe():
    from ygo74.agent_runtime.integrations.agentframework.progress import (
        ToolProgressPolicy,
    )

    policy = ToolProgressPolicy(("first", "second"))
    notices = []
    for content in (
        Content.from_function_call("a", "first", arguments="{"),
        Content.from_function_call("b", "second", arguments={"secret": "PRIVATE"}),
        Content.from_function_call("a", "first", arguments='"secret":"PRIVATE"}'),
        Content.from_function_result("b", result="PRIVATE"),
        Content.from_function_result("a", result="PRIVATE"),
        Content.from_function_result("b", result="PRIVATE"),
    ):
        notices.extend(policy.observe(AgentResponseUpdate(role="assistant", contents=[content])))
    assert len(notices) == 4
    assert "PRIVATE" not in repr(notices)
    assert [event.content.text for event in notices] == [
        "Calling first…", "Calling second…", "Completed second.", "Completed first.",
    ]


@pytest.mark.parametrize("missing_first", [False, True])
def test_partial_subrun_usage_is_never_presented_as_complete(missing_first):
    from ygo74.agent_runtime.domains.contracts.agent_output import TokenUsage
    from ygo74.agent_runtime.integrations.agentframework.binding import UsageAccumulator

    counts = UsageAccumulator()
    counts.add(None if missing_first else TokenUsage(3, 2))
    with pytest.raises(RuntimeError, match="consistently"):
        counts.add(TokenUsage(3, 2) if missing_first else None)


@pytest.mark.asyncio
async def test_scope_is_closed_when_native_factory_is_rejected():
    from contextlib import asynccontextmanager

    from test_native_agent_definition import descriptor
    from ygo74.agent_runtime.domains.auth.agent_principal import AgentPrincipal
    from ygo74.agent_runtime.domains.auth.apikey_authenticator import (
        StaticApiKeyUserResolver,
    )
    from ygo74.agent_runtime.domains.auth.auth_context import ResolvedUser
    from ygo74.agent_runtime.domains.auth.authentication_policy import (
        AuthenticationPolicy,
    )
    from ygo74.agent_runtime.domains.contracts.agent_definition import AgentDefinition
    from ygo74.agent_runtime.domains.endpoints.managed_worker import WorkerSettings
    from ygo74.agent_runtime.integrations.agentframework.worker import (
        AgentFrameworkWorker,
    )

    closed = []
    @asynccontextmanager
    async def factory(context):
        try:
            yield object()
        finally:
            closed.append(True)
    settings = WorkerSettings("deployment", "issuer", AuthenticationPolicy.api_key(
        StaticApiKeyUserResolver({"key": ResolvedUser(user_id="user")}),
    ))
    worker = AgentFrameworkWorker(AgentDefinition(descriptor(), "example:factory"), settings, factory=factory)
    with pytest.raises(TypeError, match="native agent"):
        async with worker.worker.conversations.turn(AgentPrincipal(subject="verified"), "one"):
            pass
    assert closed == [True]
    assert worker.worker.conversations.live_conversations == 0


class ApprovalClient(NativeClient):
    def __init__(self):
        super().__init__()
        self.round = 0

    def get_response(self, messages, *, stream=False, options=None, **kwargs):
        from agent_framework import ChatResponse
        self.round += 1
        contents = [Content.from_text("before" if self.round == 1 else "after")]
        if self.round == 1:
            contents.append(Content.from_function_approval_request(
                "approval", Content.from_function_call("call", "write", arguments={"secret": "PRIVATE"}),
            ))
        async def updates():
            for content in contents:
                yield AgentResponseUpdate(role="assistant", contents=[content])
            yield AgentResponseUpdate(contents=[Content.from_usage(
                {"input_token_count": 3, "output_token_count": 2},
            )])
        if not stream:
            async def response():
                return ChatResponse(messages=Message("assistant", contents),
                                    usage_details={"input_token_count": 3, "output_token_count": 2})
            return response()
        return ResponseStream(updates(), finalizer=lambda _: ChatResponse(
            messages=Message("assistant", contents),
            usage_details={"input_token_count": 3, "output_token_count": 2},
        ))


class DeclineResolver:
    def will_question(self, pending):
        return False

    async def resolve(self, pending):
        from ygo74.agent_runtime.integrations.agentframework.approval import (
            ApprovalRound,
        )
        return ApprovalRound(tuple(item.answer(approved=False) for item in pending), False)


class QuestionResolver(DeclineResolver):
    def will_question(self, pending):
        return True


@pytest.mark.asyncio
async def test_budget_cleanup_counts_native_usage_and_never_ends_success():
    session = AgentFrameworkSession(Agent(ApprovalClient()), resolver=QuestionResolver(), max_approval_rounds=0)
    events = [event async for event in session.ask_stream("one")]
    terminals = [event for event in events if isinstance(event, TerminalEvent)]
    assert len(terminals) == 1
    assert terminals[0].termination.status is TerminationStatus.INCOMPLETE
    usage = [event.usage for event in events if isinstance(event, UsageEvent)][-1]
    assert (usage.input_tokens, usage.output_tokens) == (6, 4)
    assert await session.ask("next unrelated turn") == "after"


class FailedDeclineClient(ApprovalClient):
    """Return a native error when an approval-budget stop submits refusal."""

    def __init__(self, *, raises=False, report_usage=True):
        """Configure a failed native termination or an exceptional refusal.

        Args:
            raises: Whether refusal raises instead of returning error content.
            report_usage: Whether refusal reports actual native token counts.
        """
        super().__init__()
        self.raises = raises
        self.report_usage = report_usage

    def get_response(self, messages, *, stream=False, options=None, **kwargs):
        """Preserve the first approval round and fail the non-streaming decline.

        Args:
            messages: Transcript containing the explicit approval refusal.
            stream: Native mode for the initial approval round.
            options: Effective model options.
            kwargs: Other native arguments forwarded to the initial round.
        """
        if self.round == 0:
            return super().get_response(messages, stream=stream, options=options, **kwargs)
        self.round += 1
        assert not stream
        assert any(content.type == "function_approval_response" and not content.approved
                   for message in messages for content in message.contents)
        async def response():
            """Fail the refusal with native error content or a provider exception."""
            if self.raises:
                raise ValueError("PRIVATE decline error")
            return ChatResponse(messages=Message("assistant", [
                Content(type="error", message="PRIVATE decline error", error_code="private-decline"),
            ]), usage_details={"input_token_count": 5, "output_token_count": 1} if self.report_usage else None)
        return response()


@pytest.mark.asyncio
@pytest.mark.parametrize("stream", [False, True])
@pytest.mark.parametrize("raises", [False, True])
async def test_failed_budget_decline_is_sanitized_and_invalidates_session(stream, raises):
    """Refusal errors override budget interruptions in both invocation modes.

    Args:
        stream: Whether to consume real native streaming.
        raises: Whether native refusal raises instead of returning error content.
    """
    client, discarded = FailedDeclineClient(raises=raises), []
    session = AgentFrameworkSession(Agent(client), resolver=QuestionResolver(), max_approval_rounds=0,
                                    discard_authorizations=lambda: discarded.append(True))
    if stream:
        events = [event async for event in session.ask_stream("one")]
        terminals = [event for event in events if isinstance(event, TerminalEvent)]
        assert len(terminals) == 1
        termination = terminals[0].termination
        usage = [event.usage for event in events if isinstance(event, UsageEvent)][-1]
        public = repr(events)
    else:
        output = await session.ask_output("one")
        termination, usage, public = output.termination, output.usage, repr(output)
    assert termination.status is TerminationStatus.FAILED
    assert termination.error.code == "native_execution_failed"
    assert "PRIVATE" not in public and "private-decline" not in public
    assert (usage.input_tokens, usage.output_tokens) == ((3, 2) if raises else (8, 3))
    assert discarded
    with pytest.raises(RuntimeError, match="invalidated"):
        await session.ask("next")
    assert client.round == 2


@pytest.mark.asyncio
@pytest.mark.parametrize("stream", [False, True])
async def test_unreported_decline_usage_does_not_discard_native_failure(stream):
    """Missing refusal counts must not displace a native failed termination.

    Args:
        stream: Whether to consume native streaming instead of normal output.
    """
    session = AgentFrameworkSession(Agent(FailedDeclineClient(report_usage=False)),
                                    resolver=QuestionResolver(), max_approval_rounds=0)
    if stream:
        events = [event async for event in session.ask_stream("one")]
        termination = next(event.termination for event in events if isinstance(event, TerminalEvent))
        # The initial snapshot remains valid, but no complete aggregate is emitted.
        assert [(event.usage.input_tokens, event.usage.output_tokens)
                for event in events if isinstance(event, UsageEvent)] == [(3, 2)]
    else:
        output = await session.ask_output("one")
        termination = output.termination
        assert output.usage is None
    assert termination.status is TerminationStatus.FAILED
    assert termination.error.code == "native_execution_failed"
    with pytest.raises(RuntimeError, match="invalidated"):
        await session.ask("next")


@pytest.mark.asyncio
@pytest.mark.parametrize("protocol_name", ["openai.chat_completions", "openai.responses", "anthropic.messages"])
async def test_approval_subruns_have_unique_content_one_terminal_and_true_usage(protocol_name):
    from ygo74.agent_runtime.domains.contracts.stream_events import ContentStart
    from ygo74.agent_runtime.domains.mapping.output_projector import (
        OutputProtocol,
        ProjectionContext,
    )
    from ygo74.agent_runtime.domains.streaming.stream_processor import StreamProcessor

    session = AgentFrameworkSession(Agent(ApprovalClient()), resolver=DeclineResolver())
    events = [event async for event in session.ask_stream("one")]
    assert sum(isinstance(event, TerminalEvent) for event in events) == 1
    ids = [event.content_id for event in events if isinstance(event, ContentStart)]
    assert len(ids) == len(set(ids)) == 2
    usage = [event.usage for event in events if isinstance(event, UsageEvent)][-1]
    assert (usage.input_tokens, usage.output_tokens, usage.total_tokens) == (6, 4, None)
    assert "PRIVATE" not in repr(events)
    async def producer():
        for event in events:
            yield event
    wire = "".join([frame async for frame in StreamProcessor().stream(
        producer(), ProjectionContext(OutputProtocol(protocol_name), "request", "agent"),
    )])
    assert "before" in wire and "after" in wire
    assert "invalid_agent_output" not in wire and "unsupported_output_projection" not in wire
