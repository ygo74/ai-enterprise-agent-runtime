"""A reasoning task, and the untrusted material it must be grounded in.

A request separates trusted instructions from untrusted material by construction:
the instructions and the task come from the application, the context comes from a
third-party system and is carried as
:class:`~ygo74.agent_runtime.domains.security.untrusted.UntrustedText`. The type
system therefore records which is which, and the builder below is the only place
allowed to put them in the same string.

What is deliberately *not* here: the port a host calls to obtain reasoning. Which
model answers, and through which framework, is the host's business - this library
owns the shape of the question and the fence around its evidence, not the
provider.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from ygo74.agent_runtime.domains.security.fencing import (
    DEFAULT_UNTRUSTED_SOURCE,
    UntrustedFence,
    untrusted_contract,
)
from ygo74.agent_runtime.domains.security.untrusted import UntrustedText


class UntrustedSection(BaseModel):
    """A labelled block of third-party content offered to the model as data."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    label: str = Field(min_length=1)
    content: UntrustedText


class ReasoningRequest(BaseModel):
    """A reasoning task with its untrusted context.

    Attributes:
        instructions: Trusted role and rules given to the model.
        task: Trusted description of what must be produced.
        context: Untrusted material the answer must be grounded in.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    instructions: str = Field(min_length=1)
    task: str = Field(min_length=1)
    context: tuple[UntrustedSection, ...] = ()


class PromptEnvelopeBuilder:
    """Renders a :class:`ReasoningRequest` into a prompt string.

    Args:
        source: Where the untrusted material came from, in the words the model
            should read - ``"a mailbox"``, ``"a documentation wiki"``. It is named
            in the prompt, so leaving it at the default tells the model less than
            it could about what it is looking at.
        nonce_bytes: Width of the per-rendering fence delimiter.
    """

    def __init__(self, *, source: str = DEFAULT_UNTRUSTED_SOURCE, nonce_bytes: int = 8) -> None:
        self._source = source
        self._nonce_bytes = nonce_bytes

    def build(self, request: ReasoningRequest) -> str:
        """Render the request, fencing every untrusted section.

        A request with no context renders no fence and no contract: announcing
        untrusted content that is not there would teach the model to discount the
        announcement when it is.
        """
        parts = [request.instructions.strip(), "# Task", request.task.strip()]

        if not request.context:
            return "\n\n".join(parts)

        fence = UntrustedFence(nonce_bytes=self._nonce_bytes)
        parts.append(f"# Untrusted content from {self._source}")
        parts.append(untrusted_contract(self._source))
        parts.extend(fence.render(section.label, section.content.expose()) for section in request.context)
        return "\n\n".join(parts)
