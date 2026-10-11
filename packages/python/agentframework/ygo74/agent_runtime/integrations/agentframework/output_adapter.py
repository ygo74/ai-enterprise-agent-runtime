"""Conversions of the Microsoft Agent Framework 1.18 unified Content API."""

from __future__ import annotations

import base64
import binascii
import json
import math
from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum

from agent_framework import AgentResponse, Content, UsageDetails
from ygo74.agent_runtime.domains.contracts.agent_output import (
    AgentContent,
    AgentOutput,
    AudioContent,
    ImageContent,
    ReasoningContent,
    Termination,
    TerminationStatus,
    TextContent,
    TokenUsage,
    ToolCallContent,
    ToolExecution,
    ToolResultContent,
)
from ygo74.agent_runtime.domains.contracts.error_envelope import ErrorEnvelope
from ygo74.agent_runtime.domains.contracts.json_value import JsonValue
from ygo74.agent_runtime.domains.contracts.media_content import (
    AudioFormat,
    EncodedMedia,
    MediaUri,
)

from .conversion import (
    ConversionDecision,
    ConversionReason,
    ConversionStatus,
    OutputConversion,
)


class NativeContentType(StrEnum):
    """Names Agent Framework content variants understood by the neutral output adapter.
    """
    TEXT = "text"
    REASONING = "text_reasoning"
    DATA = "data"
    URI = "uri"
    CALL = "function_call"
    RESULT = "function_result"
    USAGE = "usage"
    ERROR = "error"


class NativeFinishReason(StrEnum):
    """Maps supported Agent Framework finish reasons to neutral termination states.
    """
    STOP = "stop"
    LENGTH = "length"
    TOOL_CALLS = "tool_calls"
    FILTER = "content_filter"


@dataclass(frozen=True, slots=True)
class _MappedContent:
    """Carries the converted content, conversion decision, usage, and termination extracted from one framework item.

    Args:
        decision (ConversionDecision): Support or conversion decision produced for the current item.
        content (AgentContent | None): The content item being interpreted or projected.
        usage (TokenUsage | None): Token counters supplied by the framework or provider.
        termination (Termination | None): Terminal outcome used to complete the result or stream.
    """
    decision: ConversionDecision
    content: AgentContent | None = None
    usage: TokenUsage | None = None
    termination: Termination | None = None


class _ContentMapper:
    """Maps Agent Framework content and metadata into typed provider-neutral values and validates JSON-compatible arguments.

    Args:
        expose_reasoning (bool): Whether reasoning content may be included in client-visible output.
        tool_execution (ToolExecution): Whether tool calls are internal or delegated to the client.
    """
    _USAGE_KEYS: tuple[str, ...] = (
        "input_token_count", "output_token_count", "total_token_count",
        "cache_read_input_token_count", "reasoning_output_token_count",
    )
    _OPTIONAL_USAGE_KEYS: tuple[str, ...] = (
        "total_token_count", "cache_read_input_token_count", "reasoning_output_token_count",
    )
    _AUDIO_FORMATS: Mapping[str, AudioFormat] = {
        "audio/wav": AudioFormat.WAV,
        "audio/x-wav": AudioFormat.WAV,
        "audio/mpeg": AudioFormat.MP3,
        "audio/mp3": AudioFormat.MP3,
        "audio/flac": AudioFormat.FLAC,
        "audio/opus": AudioFormat.OPUS,
        "audio/aac": AudioFormat.AAC,
        "audio/pcm": AudioFormat.PCM16,
    }

    def __init__(self, *, expose_reasoning: bool, tool_execution: ToolExecution) -> None:
        """Initialize the instance framework output with supplied collaborators and configuration.

        Args:
            expose_reasoning (bool): Whether reasoning content may be included in client-visible output.
            tool_execution (ToolExecution): Whether tool calls are internal or delegated to the client.
        """
        self.expose_reasoning = expose_reasoning
        self.tool_execution = tool_execution
        self.tool_names: dict[str, str] = {}
        self._usage_details: dict[str, int] = {}
        self._unknown_usage: set[str] = set()

    @staticmethod
    def _decision(
        content: Content, identity: str, reason: ConversionReason,
        status: ConversionStatus = ConversionStatus.UNSUPPORTED,
    ) -> _MappedContent:
        """Create a conversion decision for the native content type and its support outcome.

        Args:
            content (Content): The content item being interpreted or projected.
            identity (str): Identifier required to correlate a route, content item, tool call, or user.
            reason (ConversionReason): Reason code or message associated with this decision or failure.
            status (ConversionStatus): Success, incomplete, or failed outcome for the operation.
        """
        return _MappedContent(ConversionDecision(identity, content.type, status, reason))

    @staticmethod
    def annotation_decision(content: Content, identity: str) -> ConversionDecision | None:
        """Report whether native annotations can be represented as neutral citations.

        Args:
            content (Content): The content item being interpreted or projected.
            identity (str): Identifier required to correlate a route, content item, tool call, or user.
        """
        if not content.annotations:
            return None
        return ConversionDecision(
            f"{identity}:annotations", "annotations", ConversionStatus.UNSUPPORTED,
            ConversionReason.UNSUPPORTED_ANNOTATIONS,
        )

    @staticmethod
    def json_value(value: object) -> JsonValue:
        """Convert recursive framework values to JSON-compatible scalars, objects, and arrays or reject them.

        Args:
            value (object): The value being converted, checked, or serialized.
        """
        # Accept JSON scalars, finite numbers, string-keyed objects, and arrays recursively; reject values that cannot be represented faithfully as JSON.
        if value is None or isinstance(value, (str, bool, int)):
            return value
        if isinstance(value, float) and math.isfinite(value):
            return value
        if isinstance(value, Mapping):
            result: dict[str, JsonValue] = {}
            for key, item in value.items():
                if not isinstance(key, str):
                    raise TypeError("JSON object keys must be strings")
                result[key] = _ContentMapper.json_value(item)
            return result
        if isinstance(value, (list, tuple)):
            return [_ContentMapper.json_value(item) for item in value]
        raise ValueError("Value is not JSON-compatible")

    @staticmethod
    def usage(details: Mapping[str, object] | None) -> TokenUsage | None:
        """Project usage information framework output into the typed usage contract or provider-specific counters.

        Args:
            details (Mapping[str, object] | None): Framework-provided token counters to validate and aggregate.
        """
        if details is None:
            return None
        incoming = details.get("input_token_count")
        outgoing = details.get("output_token_count")
        total = details.get("total_token_count")
        cached = details.get("cache_read_input_token_count")
        reasoning = details.get("reasoning_output_token_count")
        if any(isinstance(count, bool) or not isinstance(count, int) or count < 0
               for count in (incoming, outgoing)):
            return None
        if any(value is not None and (
            isinstance(value, bool) or not isinstance(value, int) or value < 0
        ) for value in (total, cached, reasoning)):
            return None
        assert isinstance(incoming, int) and isinstance(outgoing, int)
        assert total is None or isinstance(total, int)
        assert cached is None or isinstance(cached, int)
        assert reasoning is None or isinstance(reasoning, int)
        return TokenUsage(
            incoming, outgoing, total,
            cached_input_tokens=cached, reasoning_output_tokens=reasoning,
        )

    @staticmethod
    def termination(reason: str | None) -> Termination:
        """Project termination status framework output into the provider or framework representation.

        Args:
            reason (str | None): Reason code or message associated with this decision or failure.
        """
        if reason in (NativeFinishReason.LENGTH, NativeFinishReason.FILTER):
            return Termination(TerminationStatus.INCOMPLETE, reason=reason)
        if reason is None or reason in (NativeFinishReason.STOP, NativeFinishReason.TOOL_CALLS):
            return Termination()
        return Termination(TerminationStatus.INCOMPLETE, reason="unknown_sdk_finish_reason")

    def _consume_usage(self, details: UsageDetails | None) -> TokenUsage | None:
        """Accumulate valid framework token counters while preserving unknown optional totals.

        Args:
            details (UsageDetails | None): Framework-provided token counters to validate and aggregate.
        """
        # Validate counters before accumulating them, and remember missing optional counters so the combined usage never presents an unknown total as complete.
        if details is None:
            return None
        for key in self._USAGE_KEYS:
            value = details.get(key)
            if value is None:
                continue
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                return None
        for key in self._OPTIONAL_USAGE_KEYS:
            if details.get(key) is None:
                self._unknown_usage.add(key)
        for key in self._USAGE_KEYS:
            value = details.get(key)
            if isinstance(value, int):
                self._usage_details[key] = (self._usage_details.get(key) or 0) + value
        return self.usage({key: value for key, value in self._usage_details.items()
                           if key not in self._unknown_usage})

    def map(self, content: Content, identity: str) -> _MappedContent:
        """Map framework output between the source representation and the target contract.

        Args:
            content (Content): The content item being interpreted or projected.
            identity (str): Identifier required to correlate a route, content item, tool call, or user.
        """
        decision = ConversionDecision(identity, content.type, ConversionStatus.CONVERTED, ConversionReason.SUPPORTED)
        if content.type == NativeContentType.TEXT.value:
            return _MappedContent(decision, TextContent(content.text or ""))
        if content.type == NativeContentType.REASONING.value:
            if content.protected_data is not None:
                return self._decision(content, identity, ConversionReason.PROTECTED_REASONING, ConversionStatus.EXCLUDED)
            if not self.expose_reasoning:
                return self._decision(content, identity, ConversionReason.REASONING_NOT_SELECTED, ConversionStatus.EXCLUDED)
            return _MappedContent(decision, ReasoningContent(content.text or "", exposable=True))
        if content.type == NativeContentType.CALL.value:
            return self._call(content, identity, decision)
        if content.type == NativeContentType.RESULT.value:
            return self._result(content, identity, decision)
        if content.type in (NativeContentType.DATA, NativeContentType.URI):
            return self._media(content, identity, decision)
        if content.type == NativeContentType.USAGE.value:
            usage = self._consume_usage(content.usage_details)
            if usage is None:
                return self._decision(content, identity, ConversionReason.INCOMPLETE_USAGE)
            return _MappedContent(decision, usage=usage)
        if content.type == NativeContentType.ERROR.value:
            return _MappedContent(decision, termination=Termination(
                TerminationStatus.FAILED, reason="sdk_error",
                error=ErrorEnvelope(
                    code=content.error_code or "agent_framework_error",
                    category="handler_execution", message=content.message or "Agent Framework execution failed",
                ),
            ))
        return self._decision(content, identity, ConversionReason.UNKNOWN_CONTENT)

    def _call(self, content: Content, identity: str, decision: ConversionDecision) -> _MappedContent:
        """Convert a framework function call to typed tool-call content with its execution ownership.

        Args:
            content (Content): The content item being interpreted or projected.
            identity (str): Identifier required to correlate a route, content item, tool call, or user.
            decision (ConversionDecision): Support or conversion decision produced for the current item.
        """
        if not content.call_id or not content.name:
            return self._decision(content, identity, ConversionReason.MISSING_TOOL_IDENTITY)
        if content.exception:
            return self._decision(content, identity, ConversionReason.TOOL_ERROR)
        try:
            arguments = self.json_value(json.loads(content.arguments) if isinstance(content.arguments, str)
                                        else content.arguments if content.arguments is not None else {})
        except (ValueError, TypeError):
            return self._decision(content, identity, ConversionReason.INVALID_JSON)
        self.tool_names[content.call_id] = content.name
        return _MappedContent(decision, ToolCallContent(
            content.call_id, content.name, arguments, execution=self.tool_execution,
        ))

    def _result(self, content: Content, identity: str, decision: ConversionDecision) -> _MappedContent:
        """Convert a framework function result and correlate it with the original tool call.

        Args:
            content (Content): The content item being interpreted or projected.
            identity (str): Identifier required to correlate a route, content item, tool call, or user.
            decision (ConversionDecision): Support or conversion decision produced for the current item.
        """
        name = content.name or self.tool_names.get(content.call_id or "")
        if not content.call_id or not name:
            return self._decision(content, identity, ConversionReason.MISSING_TOOL_IDENTITY)
        if content.exception:
            return self._decision(content, identity, ConversionReason.TOOL_ERROR)
        if content.items is not None:
            if any(item.type != NativeContentType.TEXT.value for item in content.items):
                return self._decision(content, identity, ConversionReason.STRUCTURED_TOOL_RESULT)
            result: JsonValue = "\n".join(item.text or "" for item in content.items)
        else:
            try:
                result = self.json_value(content.result)
            except (ValueError, TypeError):
                return self._decision(content, identity, ConversionReason.INVALID_JSON)
        return _MappedContent(decision, ToolResultContent(
            content.call_id, name, result, execution=self.tool_execution,
        ))

    def _media(self, content: Content, identity: str, decision: ConversionDecision) -> _MappedContent:
        """Convert native media references or encoded data while preserving MIME and format metadata.

        Args:
            content (Content): The content item being interpreted or projected.
            identity (str): Identifier required to correlate a route, content item, tool call, or user.
            decision (ConversionDecision): Support or conversion decision produced for the current item.
        """
        uri, mime = content.uri, content.media_type
        if not uri or not mime:
            return self._decision(content, identity, ConversionReason.UNSUPPORTED_MEDIA)
        source: MediaUri | EncodedMedia
        if uri.startswith("data:"):
            header, separator, data = uri.partition(",")
            if not separator or header != f"data:{mime};base64":
                return self._decision(content, identity, ConversionReason.UNSUPPORTED_MEDIA)
            try:
                base64.b64decode(data, validate=True)
            except (ValueError, binascii.Error):
                return self._decision(content, identity, ConversionReason.UNSUPPORTED_MEDIA)
            source = EncodedMedia(data, mime)
        else:
            source = MediaUri(uri, mime)
        if mime.startswith("image/"):
            return _MappedContent(decision, ImageContent(source))
        audio_format = self._AUDIO_FORMATS.get(mime)
        if audio_format is not None:
            return _MappedContent(decision, AudioContent(source, content.id or identity, format=audio_format))
        return self._decision(content, identity, ConversionReason.UNSUPPORTED_MEDIA)


class AgentFrameworkOutputAdapter:
    """Convert final SDK messages; reasoning exposure and client tools are opt-in.

    Args:
        expose_reasoning (bool): Whether reasoning content may be included in client-visible output.
        tool_execution (ToolExecution): Whether tool calls are internal or delegated to the client.
    """
    def __init__(
        self, *, expose_reasoning: bool = False,
        tool_execution: ToolExecution = ToolExecution.INTERNAL,
    ) -> None:
        """Initialize the instance framework output with supplied collaborators and configuration.

        Args:
            expose_reasoning (bool): Whether reasoning content may be included in client-visible output.
            tool_execution (ToolExecution): Whether tool calls are internal or delegated to the client.
        """
        self._expose_reasoning = expose_reasoning
        self._tool_execution = tool_execution

    def convert(self, response: AgentResponse) -> OutputConversion:
        """Convert assistant and tool messages into the provider-neutral result contract in source order.

        Args:
            response (AgentResponse): The response value to validate, transform, or return.
        """
        # Preserve message and content order while excluding non-output roles; collect conversion diagnostics alongside typed content and prefer the response-level usage snapshot.
        if not isinstance(response, AgentResponse):
            raise TypeError("response must be an AgentResponse")
        mapper = _ContentMapper(expose_reasoning=self._expose_reasoning, tool_execution=self._tool_execution)
        contents: list[AgentContent] = []
        decisions: list[ConversionDecision] = []
        usage = mapper.usage(response.usage_details)
        termination = mapper.termination(response.finish_reason)
        for message_index, message in enumerate(response.messages):
            for content_index, content in enumerate(message.contents):
                identity = f"{message.message_id or f'message-{message_index}'}:content-{content_index}"
                if message.role not in ("assistant", "tool"):
                    decisions.append(ConversionDecision(
                        identity, content.type, ConversionStatus.EXCLUDED, ConversionReason.NON_OUTPUT_ROLE,
                    ))
                    continue
                mapped = mapper.map(content, identity)
                decisions.append(mapped.decision)
                annotation_decision = mapper.annotation_decision(content, identity)
                if annotation_decision is not None:
                    decisions.append(annotation_decision)
                if mapped.content is not None:
                    contents.append(mapped.content)
                if mapped.usage is not None and response.usage_details is None:
                    usage = mapped.usage
                if mapped.termination is not None:
                    termination = mapped.termination
        if response.usage_details is not None and usage is None:
            decisions.append(ConversionDecision(
                "response:usage", NativeContentType.USAGE, ConversionStatus.UNSUPPORTED, ConversionReason.INCOMPLETE_USAGE,
            ))
        if response.value is not None:
            decisions.append(ConversionDecision(
                "response:value", "value", ConversionStatus.UNSUPPORTED, ConversionReason.STRUCTURED_RESPONSE_VALUE,
            ))
        if response.finish_reason is not None and response.finish_reason not in NativeFinishReason:
            decisions.append(ConversionDecision(
                "response:finish", "finish_reason", ConversionStatus.UNSUPPORTED, ConversionReason.UNKNOWN_FINISH_REASON,
            ))
        return OutputConversion(AgentOutput(tuple(contents), usage, termination), tuple(decisions))
