"""Strict validation at the handler-output boundary; no legacy inference."""

import base64
import binascii
import json
from urllib.parse import urlsplit

from ygo74.agent_runtime.domains.contracts.agent_output import (
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
from ygo74.agent_runtime.domains.contracts.error_envelope import ErrorEnvelope
from ygo74.agent_runtime.domains.contracts.exchange_models import (
    StandardExchangeResponse,
)
from ygo74.agent_runtime.domains.contracts.media_content import (
    AudioFormat,
    EncodedMedia,
    MediaUri,
)


class OutputValidationError(ValueError):
    code = "invalid_agent_output"


class OutputNormalizer:
    def normalize(
        self, result: object, *, request_id: str | None = None
    ) -> AgentOutput:
        if isinstance(result, StandardExchangeResponse):
            if request_id is not None and result.request_id != request_id:
                raise OutputValidationError(
                    "StandardExchangeResponse.request_id must match the invocation"
                )
            if (
                result.status == "error"
                and isinstance(result.error, ErrorEnvelope)
                and result.output is None
            ):
                result = AgentOutput(
                    termination=Termination(
                        TerminationStatus.FAILED, error=result.error
                    )
                )
            elif result.status == "success" and result.error is None:
                result = result.output
            else:
                raise OutputValidationError(
                    "Invalid StandardExchangeResponse output envelope"
                )
        if not isinstance(result, AgentOutput):
            raise OutputValidationError(
                "Handlers must return AgentOutput or StandardExchangeResponse with typed output"
            )
        if not isinstance(result.contents, tuple):
            raise OutputValidationError(
                "AgentOutput.contents must be a tuple of typed contents"
            )
        call_ids: set[str] = set()
        audio_ids: set[str] = set()
        for content in result.contents:
            self.validate_content(content)
            if isinstance(content, TextContent):
                self.validate_citation_bounds(content)
            if isinstance(content, ToolCallContent):
                if content.call_id in call_ids:
                    raise OutputValidationError("Tool call identities must be unique")
                call_ids.add(content.call_id)
            if isinstance(content, AudioContent):
                if content.audio_id in audio_ids:
                    raise OutputValidationError("Audio identities must be unique")
                audio_ids.add(content.audio_id)
        self.validate_termination(result.termination)
        if result.usage is not None:
            self.validate_usage(result.usage)
        return result

    def validate_content(self, content: object) -> None:
        if isinstance(content, (TextContent, Notification, ReasoningContent)):
            self.text(content.text)
            if isinstance(content, TextContent):
                self._validate_annotations(content.annotations)
            if isinstance(content, ReasoningContent) and not isinstance(
                content.exposable, bool
            ):
                raise OutputValidationError("Reasoning exposable must be a boolean")
            return
        if isinstance(content, (ToolCallContent, ToolResultContent)):
            self.identity(content.call_id)
            self.identity(content.name)
            if not isinstance(content.execution, ToolExecution):
                raise OutputValidationError("Tool execution must be ToolExecution")
            self.json_value(
                content.arguments
                if isinstance(content, ToolCallContent)
                else content.result
            )
            return
        if isinstance(content, (ImageContent, AudioContent)):
            source = content.source
            if not isinstance(source, (MediaUri, EncodedMedia)):
                raise OutputValidationError("Media must have a typed source")
            self.identity(source.mime_type)
            prefix = "audio/" if isinstance(content, AudioContent) else "image/"
            if not source.mime_type.startswith(prefix) or len(source.mime_type) <= len(
                prefix
            ):
                raise OutputValidationError(
                    "Media MIME type must match the content kind"
                )
            if isinstance(source, MediaUri):
                self.identity(source.uri)
                if ":" not in source.uri:
                    raise OutputValidationError("Media URI must be absolute")
            else:
                self.base64(source.data)
            if isinstance(content, AudioContent):
                self.identity(content.audio_id)
                if not isinstance(content.format, AudioFormat):
                    raise OutputValidationError("Audio format must be AudioFormat")
                if content.transcript is not None:
                    self.text(content.transcript)
                if content.expires_at is not None:
                    self.counter(content.expires_at)
            return
        raise OutputValidationError("Unsupported pivot content type")

    def _validate_annotations(self, annotations: object) -> None:
        if not isinstance(annotations, tuple):
            raise OutputValidationError(
                "Text annotations must be a tuple of UrlCitation values"
            )
        for annotation in annotations:
            if not isinstance(annotation, UrlCitation):
                raise OutputValidationError(
                    "Text annotations must be UrlCitation values"
                )
            self.identity(annotation.url)
            self.text(annotation.title)
            try:
                uri = urlsplit(annotation.url)
                valid_url = uri.scheme in {"http", "https"} and bool(uri.netloc)
            except ValueError:
                valid_url = False
            if not valid_url:
                raise OutputValidationError(
                    "Citation URL must be an absolute HTTP or HTTPS URL"
                )
            self.counter(annotation.start_index)
            self.counter(annotation.end_index)
            if annotation.end_index < annotation.start_index:
                raise OutputValidationError(
                    "Citation end_index cannot precede start_index"
                )

    @staticmethod
    def validate_citation_bounds(content: TextContent) -> None:
        if any(
            annotation.end_index > len(content.text)
            for annotation in content.annotations
        ):
            raise OutputValidationError(
                "Citation offsets must be within the completed text"
            )

    def validate_termination(self, termination: object) -> None:
        if not isinstance(termination, Termination) or not isinstance(
            termination.status, TerminationStatus
        ):
            raise OutputValidationError("Termination must have a typed status")
        if termination.reason is not None:
            self.identity(termination.reason)
        if termination.status == TerminationStatus.FAILED:
            if not isinstance(termination.error, ErrorEnvelope):
                raise OutputValidationError("Failed termination requires ErrorEnvelope")
            self.identity(termination.error.code)
            self.identity(termination.error.category)
            self.text(termination.error.message)
            return
        if termination.error is not None:
            raise OutputValidationError("Only failed termination may contain an error")

    def validate_usage(self, usage: object) -> None:
        if not isinstance(usage, TokenUsage):
            raise OutputValidationError("Usage must be TokenUsage")
        self.counter(usage.input_tokens)
        self.counter(usage.output_tokens)
        if usage.cached_input_tokens is not None:
            self.counter(usage.cached_input_tokens)
        if usage.reasoning_output_tokens is not None:
            self.counter(usage.reasoning_output_tokens)
        if usage.cache_write_input_tokens is not None:
            self.counter(usage.cache_write_input_tokens)
        if usage.total_tokens is not None:
            self.counter(usage.total_tokens)
            if usage.total_tokens < usage.input_tokens + usage.output_tokens:
                raise OutputValidationError(
                    "Total tokens cannot be less than input plus output tokens"
                )

    @staticmethod
    def counter(value: object) -> None:
        if type(value) is not int or value < 0:
            raise OutputValidationError("Counters must be nonnegative integers")

    @staticmethod
    def text(value: object) -> None:
        if not isinstance(value, str):
            raise OutputValidationError("Text values must be strings")

    @staticmethod
    def identity(value: object) -> None:
        if not isinstance(value, str) or not value.strip():
            raise OutputValidationError(
                "Content identifiers and names must be nonempty strings"
            )

    @staticmethod
    def base64(value: object) -> None:
        if not isinstance(value, str):
            raise OutputValidationError("Encoded media must be base64 text")
        try:
            base64.b64decode(value, validate=True)
        except (ValueError, binascii.Error) as exc:
            raise OutputValidationError("Encoded media must be valid base64") from exc

    @classmethod
    def json_value(cls, value: object) -> None:
        try:
            json.dumps(value, allow_nan=False)
        except (ValueError, TypeError, RecursionError) as exc:
            raise OutputValidationError(
                "Tool values must be finite, acyclic JSON values"
            ) from exc
        cls._json_types(value)

    @classmethod
    def _json_types(cls, value: object) -> None:
        if value is None or isinstance(value, (str, bool, int, float)):
            return
        if isinstance(value, list):
            for item in value:
                cls._json_types(item)
            return
        if isinstance(value, dict) and all(isinstance(key, str) for key in value):
            for item in value.values():
                cls._json_types(item)
            return
        raise OutputValidationError("Tool values must be JSON values")
