"""Projection support decisions shared by final and incremental outputs."""

import logging
import time
import uuid
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Protocol

from ygo74.agent_runtime.domains.contracts.agent_output import (
    AgentContent,
    AgentOutput,
    AudioContent,
    ImageContent,
    Notification,
    ReasoningContent,
    Termination,
    TerminationStatus,
    TextContent,
    TokenUsage,
    ToolCallContent,
    ToolExecution,
    ToolResultContent,
    UrlCitation,
)
from ygo74.agent_runtime.domains.contracts.json_value import JsonValue
from ygo74.agent_runtime.domains.contracts.media_content import EncodedMedia

logger = logging.getLogger(__name__)


class OutputProtocol(StrEnum):
    CHAT_COMPLETIONS = "openai.chat_completions"
    RESPONSES = "openai.responses"
    ANTHROPIC_MESSAGES = "anthropic.messages"


class OutputProjectionError(RuntimeError):
    code = "unsupported_output_projection"
    category = "projection"


class FilterReason(StrEnum):
    NOTIFICATION_NONSTREAM = "notification_nonstream"
    INTERNAL_TOOL = "internal_tool"
    TOOL_RESULT = "tool_result_not_assistant_output"
    PRIVATE_REASONING = "reasoning_not_exposable"
    UNSUPPORTED_REASONING = "unsupported_reasoning"
    UNSUPPORTED_IMAGE = "unsupported_assistant_image"
    UNSUPPORTED_AUDIO = "unsupported_audio"
    UNSUPPORTED_STREAMING_AUDIO = "unsupported_streaming_audio"
    AUDIO_METADATA = "audio_expiry_required"
    MULTIPLE_AUDIO = "multiple_audio_outputs"
    TOOL_ARGUMENTS = "unsupported_tool_arguments"
    UNSUPPORTED_CITATION = "unsupported_citation"
    INCOMPLETE_USAGE = "incomplete_usage"
    UNSUPPORTED_TERMINATION_REASON = "unsupported_termination_reason"
    EMPTY_OUTPUT = "all_contents_filtered"


@dataclass(frozen=True, slots=True)
class ProjectionContext:
    protocol: OutputProtocol
    request_id: str
    route_key: str = ""
    model: str | None = None
    provider_options: dict[str, JsonValue] = field(default_factory=dict)
    request_metadata: dict[str, JsonValue] = field(default_factory=dict)
    response_id: str = field(default_factory=lambda: f"resp_{uuid.uuid4().hex}")
    created_at: int = field(default_factory=lambda: int(time.time()))


@dataclass(frozen=True, slots=True)
class ProjectionDecision:
    supported: bool
    reason: FilterReason | None = None


class OutputProjector(Protocol):
    def project(
        self, output: AgentOutput, context: ProjectionContext
    ) -> dict[str, JsonValue]: ...


class ContentSupport:
    def annotations(
        self, content: TextContent, context: ProjectionContext
    ) -> tuple[UrlCitation, ...]:
        if context.protocol == OutputProtocol.RESPONSES:
            return content.annotations
        for annotation in content.annotations:
            self.log(context, annotation, FilterReason.UNSUPPORTED_CITATION)
        return ()

    def decide(
        self, content: AgentContent, context: ProjectionContext, *, streaming: bool
    ) -> ProjectionDecision:
        if isinstance(content, Notification):
            return (
                ProjectionDecision(True)
                if streaming
                else ProjectionDecision(False, FilterReason.NOTIFICATION_NONSTREAM)
            )
        if (
            isinstance(content, ToolCallContent)
            and content.execution == ToolExecution.INTERNAL
        ):
            return ProjectionDecision(False, FilterReason.INTERNAL_TOOL)
        if (
            isinstance(content, ToolCallContent)
            and context.protocol == OutputProtocol.ANTHROPIC_MESSAGES
            and not isinstance(content.arguments, dict)
        ):
            return ProjectionDecision(False, FilterReason.TOOL_ARGUMENTS)
        if isinstance(content, ToolResultContent):
            return ProjectionDecision(False, FilterReason.TOOL_RESULT)
        if isinstance(content, ReasoningContent):
            if not content.exposable:
                return ProjectionDecision(False, FilterReason.PRIVATE_REASONING)
            if context.protocol != OutputProtocol.RESPONSES:
                return ProjectionDecision(False, FilterReason.UNSUPPORTED_REASONING)
        if isinstance(content, ImageContent):
            return ProjectionDecision(False, FilterReason.UNSUPPORTED_IMAGE)
        if isinstance(content, AudioContent):
            if streaming:
                return ProjectionDecision(
                    False, FilterReason.UNSUPPORTED_STREAMING_AUDIO
                )
            if context.protocol != OutputProtocol.CHAT_COMPLETIONS or not isinstance(
                content.source, EncodedMedia
            ):
                return ProjectionDecision(False, FilterReason.UNSUPPORTED_AUDIO)
            if content.expires_at is None:
                return ProjectionDecision(False, FilterReason.AUDIO_METADATA)
        return ProjectionDecision(True)

    @staticmethod
    def log(context: ProjectionContext, content: object, reason: FilterReason) -> None:
        logger.info(
            "Output content filtered request_id=%s route_key=%s protocol=%s pivot_type=%s reason=%s",
            context.request_id,
            context.route_key,
            context.protocol,
            type(content).__name__,
            reason,
            extra={
                "request_id": context.request_id,
                "route_key": context.route_key,
                "protocol": context.protocol.value,
                "pivot_type": type(content).__name__,
                "reason_code": reason.value,
            },
        )

    def filter(
        self, output: AgentOutput, context: ProjectionContext
    ) -> tuple[AgentContent, ...]:
        contents: list[AgentContent] = []
        has_audio = False
        for content in output.contents:
            decision = self.decide(content, context, streaming=False)
            if isinstance(content, AudioContent) and decision.supported:
                if has_audio:
                    decision = ProjectionDecision(False, FilterReason.MULTIPLE_AUDIO)
                has_audio = True
            if decision.supported:
                if isinstance(content, TextContent):
                    self.annotations(content, context)
                contents.append(content)
            elif decision.reason is not None:
                self.log(context, content, decision.reason)
        if output.contents and not contents:
            self.log(context, output, FilterReason.EMPTY_OUTPUT)
        return tuple(contents)


class OutputWireValues:
    @staticmethod
    def incomplete_reason(
        termination: Termination, context: ProjectionContext
    ) -> str | None:
        budget_reason = {
            OutputProtocol.CHAT_COMPLETIONS: "length",
            OutputProtocol.RESPONSES: "max_output_tokens",
            OutputProtocol.ANTHROPIC_MESSAGES: "max_tokens",
        }[context.protocol]
        if termination.reason in ("length", "max_tokens", "max_output_tokens"):
            return budget_reason
        if (
            termination.reason == "content_filter"
            and context.protocol != OutputProtocol.ANTHROPIC_MESSAGES
        ):
            return "content_filter"
        if termination.reason is not None:
            ContentSupport.log(
                context, termination, FilterReason.UNSUPPORTED_TERMINATION_REASON
            )
        if context.protocol == OutputProtocol.CHAT_COMPLETIONS:
            return "length"
        return None

    @staticmethod
    def finish_reason(
        termination: Termination, context: ProjectionContext, *, has_tools: bool
    ) -> str | None:
        if termination.status == TerminationStatus.INCOMPLETE:
            return OutputWireValues.incomplete_reason(termination, context)
        if context.protocol == OutputProtocol.CHAT_COMPLETIONS:
            return "tool_calls" if has_tools else "stop"
        return "tool_use" if has_tools else "end_turn"

    @staticmethod
    def incomplete_details(
        termination: Termination, context: ProjectionContext
    ) -> dict[str, JsonValue] | None:
        if termination.status != TerminationStatus.INCOMPLETE:
            return None
        reason = OutputWireValues.incomplete_reason(termination, context)
        return {"reason": reason} if reason is not None else None

    @staticmethod
    def citations(content: TextContent) -> list[JsonValue]:
        return [
            {
                "type": "url_citation",
                "url": annotation.url,
                "title": annotation.title,
                "start_index": annotation.start_index,
                "end_index": annotation.end_index,
            }
            for annotation in content.annotations
        ]

    @staticmethod
    def text(contents: tuple[AgentContent, ...]) -> str:
        return "".join(
            content.text for content in contents if isinstance(content, TextContent)
        )

    @staticmethod
    def anthropic_usage(
        usage: TokenUsage | None, context: ProjectionContext
    ) -> dict[str, JsonValue]:
        if usage is None:
            ContentSupport.log(context, usage, FilterReason.INCOMPLETE_USAGE)
            raise OutputProjectionError(
                "Anthropic Messages requires known input/output token usage; "
                "streams require UsageEvent before visible content"
            )
        result = OutputWireValues.usage(usage, context)
        assert result is not None
        return result

    @staticmethod
    def usage(
        usage: TokenUsage, context: ProjectionContext
    ) -> dict[str, JsonValue] | None:
        if context.protocol == OutputProtocol.CHAT_COMPLETIONS:
            if usage.total_tokens is None:
                ContentSupport.log(context, usage, FilterReason.INCOMPLETE_USAGE)
                return None
            result: dict[str, JsonValue] = {
                "prompt_tokens": usage.input_tokens,
                "completion_tokens": usage.output_tokens,
                "total_tokens": usage.total_tokens,
            }
            prompt_details: dict[str, JsonValue] = {}
            if usage.cached_input_tokens is not None:
                prompt_details["cached_tokens"] = usage.cached_input_tokens
            if usage.cache_write_input_tokens is not None:
                prompt_details["cache_write_tokens"] = usage.cache_write_input_tokens
            if prompt_details:
                result["prompt_tokens_details"] = prompt_details
            if usage.reasoning_output_tokens is not None:
                result["completion_tokens_details"] = {
                    "reasoning_tokens": usage.reasoning_output_tokens
                }
            return result
        if context.protocol == OutputProtocol.RESPONSES:
            if (
                usage.total_tokens is None
                or usage.cached_input_tokens is None
                or usage.reasoning_output_tokens is None
                or usage.cache_write_input_tokens is None
            ):
                ContentSupport.log(context, usage, FilterReason.INCOMPLETE_USAGE)
                return None
            return {
                "input_tokens": usage.input_tokens,
                "output_tokens": usage.output_tokens,
                "total_tokens": usage.total_tokens,
                "input_tokens_details": {
                    "cached_tokens": usage.cached_input_tokens,
                    "cache_write_tokens": usage.cache_write_input_tokens,
                },
                "output_tokens_details": {
                    "reasoning_tokens": usage.reasoning_output_tokens
                },
            }
        result = {
            "input_tokens": usage.input_tokens,
            "output_tokens": usage.output_tokens,
        }
        if usage.cached_input_tokens is not None:
            result["cache_read_input_tokens"] = usage.cached_input_tokens
        if usage.cache_write_input_tokens is not None:
            result["cache_creation_input_tokens"] = usage.cache_write_input_tokens
        return result

    @staticmethod
    def error(
        output: AgentOutput, context: ProjectionContext
    ) -> dict[str, JsonValue] | None:
        error = output.termination.error
        if output.termination.status != TerminationStatus.FAILED or error is None:
            return None
        if context.protocol == OutputProtocol.RESPONSES:
            error_type = {
                "validation": "invalid_request_error",
                "authentication": "authentication_error",
                "authorization": "permission_error",
                "routing": "not_found_error",
            }.get(error.category, "server_error")
            return {
                "error": {
                    "code": error.code,
                    "type": error_type,
                    "message": error.message,
                    "param": None,
                }
            }
        return {
            "request_id": context.request_id,
            "status": "error",
            "endpoint_type": context.protocol.value,
            "error": {
                "code": error.code,
                "category": error.category,
                "message": error.message,
            },
        }
