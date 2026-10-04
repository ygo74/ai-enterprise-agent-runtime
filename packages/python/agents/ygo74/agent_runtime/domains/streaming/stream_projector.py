from typing import Protocol

from ygo74.agent_runtime.domains.contracts.agent_output import Termination
from ygo74.agent_runtime.domains.contracts.stream_events import AgentStreamEvent
from ygo74.agent_runtime.domains.streaming.sse_encoder import WireEvent
from ygo74.agent_runtime.domains.streaming.stream_state import StreamState


class StreamProjector(Protocol):
    def start(self, state: StreamState) -> list[WireEvent]: ...
    def project(
        self, event: AgentStreamEvent, state: StreamState
    ) -> list[WireEvent]: ...
    def finish(
        self, termination: Termination, state: StreamState
    ) -> list[WireEvent]: ...
    @property
    def done_marker(self) -> bool: ...
