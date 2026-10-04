from typing import Protocol

from ygo74.agent_runtime.domains.contracts.agent_output import Termination
from ygo74.agent_runtime.domains.contracts.stream_events import AgentStreamEvent
from ygo74.agent_runtime.domains.streaming.sse_encoder import WireEvent
from ygo74.agent_runtime.domains.streaming.stream_state import StreamState


class StreamProjector(Protocol):
    """Translate typed runtime values into the framework stream events representation using protocol-specific mapping rules.
    """
    def start(self, state: StreamState) -> list[WireEvent]:
        """Start framework stream events the current content or operation in the target protocol.

        Args:
            state (StreamState): The state that tracks the current operation lifecycle.
        """
        ...
    def project(
        self, event: AgentStreamEvent, state: StreamState
    ) -> list[WireEvent]:
        """Project framework stream events into the response shape required by the selected protocol.

        Args:
            event (AgentStreamEvent): The typed event whose content or lifecycle effect is processed.
            state (StreamState): The state that tracks the current operation lifecycle.
        """
        ...
    def finish(
        self, termination: Termination, state: StreamState
    ) -> list[WireEvent]:
        """Finalize framework stream events the operation and emit its terminal representation.

        Args:
            termination (Termination): Terminal outcome used to complete the result or stream.
            state (StreamState): The state that tracks the current operation lifecycle.
        """
        ...
    @property
    def done_marker(self) -> bool:
        """Return the protocol end marker framework stream events used to terminate the encoded stream.
        """
        ...
