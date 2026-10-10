"""Managed worker characterization on all supported endpoint families."""

from importlib import import_module
from pathlib import Path

import pytest
from agent_framework import Agent, ContextProvider
from fastapi.testclient import TestClient


@pytest.fixture
def example(monkeypatch):
    directory = Path(__file__).resolve().parents[3] / "docs" / "examples" / "python-agentframework-fastapi"
    monkeypatch.syspath_prepend(str(directory))
    monkeypatch.setenv("NATIVE_WORKER_API_KEY", "controlled-test-key")
    native, deployment = import_module("native"), import_module("deployment")
    from ygo74.agent_runtime.integrations.agentframework.worker import (
        AgentFrameworkWorker,
    )
    return directory, AgentFrameworkWorker(native.definition, deployment.settings)


@pytest.mark.parametrize(("path", "body"), [
    ("/v1/chat/completions", {"model": "agentframework-echo", "messages": [{"role": "user", "content": "hello"}]}),
    ("/v1/responses", {"model": "agentframework-echo", "input": "hello"}),
    ("/v1/messages", {"model": "agentframework-echo", "max_tokens": 100,
                      "messages": [{"role": "user", "content": "hello"}]}),
])
@pytest.mark.parametrize("stream", [False, True])
def test_native_example_is_served_without_agent_owned_http(example, path, body, stream):
    _, worker = example
    app = worker.build_app()
    with TestClient(app) as client:
        assert client.get("/health/ready").json() == {"ready": True}
        assert client.post(path, json=body).status_code == 401
        response = client.post(path, json={**body, "stream": stream},
                               headers={"x-api-key": "controlled-test-key"})
        assert response.status_code == 200, response.text
        assert "hello" in response.text
        expected_type = "text/event-stream" if stream else "application/json"
        assert expected_type in response.headers["content-type"]
    assert worker.worker.conversations.live_conversations == 0
    assert client.get("/health/ready").status_code == 503


def test_delivered_simple_glue_is_at_most_thirty_lines(example):
    directory, _ = example
    lines = sum(sum(bool(line.strip()) for line in (directory / filename).read_text().splitlines())
                for filename in ("native.py", "app.py"))
    assert lines <= 30, lines


def test_native_input_profile_refuses_images(example):
    _, worker = example
    with TestClient(worker.build_app()) as client:
        response = client.post("/v1/chat/completions", headers={"x-api-key": "controlled-test-key"},
                               json={"model": "agentframework-echo", "messages": [{
                                   "role": "user", "content": [{"type": "image_url", "image_url": {"url": "https://example.test/img"}}],
                               }]})
        assert response.status_code >= 400


def test_trusted_factory_cannot_be_changed_by_request(example):
    _, worker = example
    with TestClient(worker.build_app()) as client:
        response = client.post("/v1/responses", headers={"x-api-key": "controlled-test-key"},
                               json={"model": "agentframework-echo", "input": "hello",
                                     "metadata": {"factory": "os:system"}})
        assert response.status_code == 200
        assert "hello" in response.text


@pytest.mark.parametrize("modes", [(False, False), (True, True), (False, True), (True, False)])
def test_completed_http_stream_retains_real_provider_continuation(example, modes):
    """Closing a transport at its terminal must not retire valid provider state.

    Args:
        example: Controlled native worker configuration.
        modes: Native modes for consecutive HTTP turns.
    """
    from contextlib import asynccontextmanager

    import httpx
    from agent_framework.openai import OpenAIChatClient
    from openai import AsyncOpenAI
    from test_provider_continuity import ResponsesTransport
    from ygo74.agent_runtime.integrations.agentframework.worker import (
        AgentFrameworkWorker,
    )

    _, configured = example
    transport = ResponsesTransport()

    @asynccontextmanager
    async def factory(context):
        """Close the SDK client with the caller's native dependency scope.

        Args:
            context: Verified factory context, not request-controlled wiring.
        """
        async with httpx.AsyncClient(transport=httpx.MockTransport(transport)) as http:
            sdk = AsyncOpenAI(api_key="synthetic-test-key", base_url="https://provider.invalid/v1", http_client=http)
            yield Agent(OpenAIChatClient(model="controlled-model", async_client=sdk))

    worker = AgentFrameworkWorker(configured._definition, configured._settings, factory=factory)
    with TestClient(worker.build_app()) as http:
        for stream in modes:
            response = http.post(
                "/v1/chat/completions",
                headers={"x-api-key": "controlled-test-key", "X-Conversation-Id": "one"},
                json={"model": "agentframework-echo", "stream": stream,
                      "messages": [{"role": "user", "content": "controlled"}]},
            )
            assert response.status_code == 200
            assert worker.worker.conversations.live_conversations == 1
        response = http.post(
            "/v1/chat/completions",
            headers={"x-api-key": "controlled-test-key", "X-Conversation-Id": "other"},
            json={"model": "agentframework-echo", "messages": [{"role": "user", "content": "controlled"}]},
        )
        assert response.status_code == 200
        assert worker.worker.conversations.live_conversations == 2
    assert [request.get("previous_response_id") for request in transport.requests] == [None, "resp_1", None]


def test_actual_local_dispatch_performance_budget(example):
    """Measure the native no-inference worker path, not just a threshold file."""
    import json
    from time import perf_counter

    directory, worker = example
    root = directory.parents[2]
    budgets = json.loads((root / "tests" / "performance" / "baselines" / "performance_thresholds.json").read_text())
    latencies = []
    with TestClient(worker.build_app()) as client:
        for _ in range(40):
            start = perf_counter()
            response = client.post("/v1/responses", headers={"x-api-key": "controlled-test-key"},
                                   json={"model": "agentframework-echo", "input": "hello"})
            latencies.append((perf_counter() - start) * 1000)
            assert response.status_code == 200
    p95 = sorted(latencies)[int(len(latencies) * 0.95) - 1]
    print(f"native worker authenticated dispatch p95={p95:.3f}ms")
    assert p95 < budgets["auth_dispatch_pipeline_p95_ms"]


@pytest.mark.asyncio
async def test_actual_normalization_and_native_first_event_budgets(example):
    """Measure input translation and time to the first actual native update."""
    import json
    from contextlib import aclosing
    from time import perf_counter

    from native import create_agent
    from ygo74.agent_runtime.domains.auth.agent_principal import AgentPrincipal
    from ygo74.agent_runtime.domains.contracts.agent_definition import (
        AgentFactoryContext,
    )
    from ygo74.agent_runtime.domains.endpoints.conversation_payloads import (
        ConversationPayloadReader,
    )
    from ygo74.agent_runtime.integrations.agentframework.binding import (
        AgentFrameworkSession,
    )

    directory, _ = example
    budgets = json.loads((directory.parents[2] / "tests" / "performance" / "baselines" / "performance_thresholds.json").read_text())
    reader = ConversationPayloadReader(require_email=False)
    normalization, first_events = [], []
    for _ in range(40):
        start = perf_counter()
        turn = reader.to_turn({"auth_context": {"identity": {"subject": "verified"}},
                               "input": [{"role": "user", "content": "hello"}]})
        normalization.append((perf_counter() - start) * 1000)
        agent = create_agent(AgentFactoryContext(AgentPrincipal(subject="verified"), "one", "deployment", "issuer"))
        session = AgentFrameworkSession(agent)
        start = perf_counter()
        async with aclosing(session.ask_stream(turn.message)) as stream:
            await anext(stream)
            first_events.append((perf_counter() - start) * 1000)
    normalize_p95 = sorted(normalization)[37]
    first_p95 = sorted(first_events)[37]
    print(f"native input normalization p95={normalize_p95:.3f}ms; first event p95={first_p95:.3f}ms")
    assert normalize_p95 < budgets["normalization_dispatch_p95_ms"]
    assert first_p95 < budgets["first_stream_event_p95_ms"]


class DynamicTools(ContextProvider):
    """A real SDK provider adds tools outside Agent.default_options."""

    def __init__(self):
        """Initialize a native provider with a controlled side-effect marker."""
        super().__init__("dynamic")
        self.executed = False

    async def before_run(self, *, agent, session, context, state):
        """Inject an undeclared callable through the native provider contract.

        Args:
            agent: Native agent running the provider pipeline.
            session: Current native session.
            context: Mutable SDK invocation context.
            state: Provider-specific state.
        """
        def write():
            """Record an unguarded dynamic tool invocation."""
            self.executed = True
            return "changed"
        context.extend_tools(self.source_id, [write])


@pytest.mark.asyncio
async def test_real_context_provider_extends_native_invocation_tools():
    """Characterize the effective dynamic surface that admission must protect."""
    from test_agentframework_binding import FunctionClient

    provider = DynamicTools()
    agent = Agent(FunctionClient(tool_name="write"), context_providers=[provider])
    assert not agent.default_options.get("tools")
    stream = agent.run("one", stream=True)
    await stream.get_final_response()
    assert provider.executed


@pytest.mark.asyncio
@pytest.mark.parametrize("explicit_admission", [False, True])
async def test_dynamic_context_tools_require_explicit_admission(example, explicit_admission):
    """No-tools definitions cannot bypass policy through context providers.

    Args:
        example: Controlled worker definition and operator settings.
        explicit_admission: Whether to install a deterministic rejecting policy.
    """
    from test_agentframework_binding import NativeClient
    from ygo74.agent_runtime.domains.auth.agent_principal import AgentPrincipal
    from ygo74.agent_runtime.integrations.agentframework.worker import (
        AgentFrameworkWorker,
    )

    _, configured = example
    provider, client = DynamicTools(), NativeClient()
    agent = Agent(client, context_providers=[provider])
    assert not agent.default_options.get("tools")
    admitted = []
    def admission(definition, native):
        """Reject unguarded dynamic capabilities without trusting declarations.

        Args:
            definition: Trusted deployment metadata.
            native: Constructed native agent requiring actual policy validation.
        """
        admitted.append(native)
        if any(isinstance(item, DynamicTools) for item in native.context_providers):
            raise ValueError("admission rejects ungated dynamic capabilities")
    worker = AgentFrameworkWorker(configured._definition, configured._settings, factory=lambda _: agent,
                                  admission=admission if explicit_admission else None)
    try:
        with pytest.raises(ValueError, match="admission"):
            async with worker.worker.conversations.turn(AgentPrincipal(subject="verified"), "one"):
                pass
        assert client.modes == [] and not provider.executed
        assert admitted == ([agent] if explicit_admission else [])
    finally:
        await worker.worker.conversations.aclose()
