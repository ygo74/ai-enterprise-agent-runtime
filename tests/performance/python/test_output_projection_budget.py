import asyncio
import statistics
import time
from collections.abc import AsyncIterator

from ygo74.agent_runtime.domains.auth.apikey_authenticator import (
    ApiKeyAuthenticator,
    StaticApiKeyUserResolver,
)
from ygo74.agent_runtime.domains.auth.auth_context import ResolvedUser
from ygo74.agent_runtime.domains.auth.authenticator import RequestAuthenticator
from ygo74.agent_runtime.domains.contracts import (
    AgentOutput,
    AgentStreamEvent,
    ContentEnd,
    ContentStart,
    TerminalEvent,
    TextContent,
    TextDelta,
    TokenUsage,
    UsageEvent,
)
from ygo74.agent_runtime.domains.contracts.exchange_models import (
    StandardExchangeRequest,
    StandardExchangeResponse,
)
from ygo74.agent_runtime.domains.mapping.output_projector import (
    OutputProtocol,
    ProjectionContext,
)
from ygo74.agent_runtime.domains.mapping.request_mapper import map_to_exchange
from ygo74.agent_runtime.domains.mapping.response_mapper import ResponseMapper
from ygo74.agent_runtime.domains.streaming.stream_processor import StreamProcessor
from ygo74.agent_runtime.middleware.pipeline import execute_pipeline
from ygo74.agent_runtime.routing.dispatcher_impl import DispatcherImpl


def test_real_output_projection_p95_budget() -> None:
    mapper = ResponseMapper()
    output = AgentOutput((TextContent("a" * 1000),), TokenUsage(1, 2))
    elapsed: list[float] = []
    for protocol in OutputProtocol:
        for _ in range(100):
            started = time.perf_counter()
            mapper.project(output, ProjectionContext(protocol, "request", "route"))
            elapsed.append((time.perf_counter() - started) * 1000)
    assert statistics.quantiles(elapsed, n=100)[94] < 10


def test_authentication_dispatch_pipeline_p95_excluding_handler_time() -> None:
    authenticator = RequestAuthenticator(
        [
            ApiKeyAuthenticator(
                StaticApiKeyUserResolver(
                    {"benchmark-key": ResolvedUser(user_id="benchmark-user")}
                )
            ),
        ],
        require_authentication=True,
    )
    output = AgentOutput((TextContent("answer"),), TokenUsage(1, 2))
    mapper = ResponseMapper()
    dispatcher = DispatcherImpl()
    elapsed: list[float] = []
    normalization_dispatch_elapsed: list[float] = []
    for protocol in OutputProtocol:
        for _ in range(100):
            handler_elapsed = 0.0

            def handler(request: StandardExchangeRequest) -> StandardExchangeResponse:
                nonlocal handler_elapsed
                started = time.perf_counter()
                result = StandardExchangeResponse(request.request_id, "success", output)
                handler_elapsed += time.perf_counter() - started
                return result

            started = time.perf_counter()
            user = authenticator.authenticate({"x-api-key": "benchmark-key"})
            assert user is not None
            normalization_dispatch_started = time.perf_counter()
            request = map_to_exchange(
                protocol,
                {
                    "request_id": "request",
                    "route_key": "route",
                    "input": "question",
                    "auth_context": user.to_dict(),
                },
            )
            result = execute_pipeline(
                request,
                [lambda context, next_handler: next_handler(context)],
                lambda context: dispatcher.dispatch(context, lambda _: handler),
            )
            normalization_dispatch_elapsed.append(
                (time.perf_counter() - normalization_dispatch_started - handler_elapsed)
                * 1000
            )
            mapper.project(result, ProjectionContext(protocol, "request", "route"))
            elapsed.append((time.perf_counter() - started - handler_elapsed) * 1000)
    assert statistics.quantiles(normalization_dispatch_elapsed, n=100)[94] < 10
    assert statistics.quantiles(elapsed, n=100)[94] < 50


def test_first_delta_precedes_producer_completion_within_p95_budget() -> None:
    async def scenario() -> None:
        elapsed: list[float] = []
        for protocol in OutputProtocol:
            for _ in range(30):
                finished = False

                async def producer() -> AsyncIterator[AgentStreamEvent]:
                    nonlocal finished
                    yield UsageEvent(TokenUsage(1, 2))
                    yield ContentStart("answer", TextContent(""))
                    yield TextDelta("answer", "first")
                    await asyncio.sleep(0)
                    finished = True
                    yield ContentEnd("answer")
                    yield TerminalEvent()

                stream = StreamProcessor().stream(
                    producer(), ProjectionContext(protocol, "request", "route")
                )
                started = time.perf_counter()
                async for frame in stream:
                    if "first" in frame:
                        elapsed.append((time.perf_counter() - started) * 1000)
                        assert not finished
                        break
                await stream.aclose()
        assert statistics.quantiles(elapsed, n=100)[94] < 300

    asyncio.run(scenario())
