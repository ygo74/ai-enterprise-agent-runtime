"""Reuse LangChain's standardized content blocks rather than provider heuristics."""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from math import isfinite
from typing import ClassVar, cast

from langchain_core.messages.content import (
    AudioContentBlock,
    ContentBlock,
    ImageContentBlock,
    ReasoningContentBlock,
    ServerToolCall,
    ServerToolResult,
    TextContentBlock,
    ToolCall,
)
from ygo74.agent_runtime.domains.contracts.agent_output import (
    AgentContent,
    AudioContent,
    ImageContent,
    ReasoningContent,
    TextContent,
    ToolCallContent,
    ToolExecution,
    ToolResultContent,
    UrlCitation,
)
from ygo74.agent_runtime.domains.contracts.json_value import JsonValue
from ygo74.agent_runtime.domains.contracts.media_content import (
    AudioFormat,
    EncodedMedia,
    MediaSource,
    MediaUri,
)

from .conversion import ConversionDiagnostic, LangChainConversionError


class BlockKind(StrEnum):
    TEXT = "text"
    REASONING = "reasoning"
    IMAGE = "image"
    AUDIO = "audio"
    TOOL_CALL = "tool_call"
    TOOL_CALL_CHUNK = "tool_call_chunk"
    SERVER_TOOL_CALL = "server_tool_call"
    SERVER_TOOL_CALL_CHUNK = "server_tool_call_chunk"
    SERVER_TOOL_RESULT = "server_tool_result"


@dataclass(frozen=True, slots=True)
class ContentConversion:
    content: AgentContent | None = None
    diagnostic: ConversionDiagnostic | None = None
    unsupported: bool = False


class JsonBoundary:
    @classmethod
    def convert(cls, value: object) -> JsonValue:
        if value is None or isinstance(value, (str, bool, int)):
            return value
        if isinstance(value, float) and isfinite(value):
            return value
        if isinstance(value, list):
            return [cls.convert(item) for item in cast(list[object], value)]
        if isinstance(value, dict):
            items = cast(dict[object, object], value)
            if all(isinstance(key, str) for key in items):
                return {cast(str, key): cls.convert(item) for key, item in items.items()}
        raise LangChainConversionError("Native value is not a finite JSON value.")


class LangChainContentAdapter:
    _audio_formats: ClassVar[dict[str, AudioFormat]] = {
        "audio/wav": AudioFormat.WAV,
        "audio/x-wav": AudioFormat.WAV,
        "audio/mpeg": AudioFormat.MP3,
        "audio/mp3": AudioFormat.MP3,
        "audio/flac": AudioFormat.FLAC,
        "audio/opus": AudioFormat.OPUS,
        "audio/aac": AudioFormat.AAC,
    }

    def __init__(self, *, expose_reasoning: bool, tool_execution: ToolExecution) -> None:
        self.expose_reasoning = expose_reasoning
        self.tool_execution = tool_execution

    def convert(
        self, block: ContentBlock, *, fallback_id: str,
        tool_names: Mapping[str, str] | None = None,
    ) -> ContentConversion:
        kind = block["type"]
        if kind == BlockKind.TEXT.value:
            return self._text(cast(TextContentBlock, block))
        if kind == BlockKind.REASONING.value:
            return self._reasoning(cast(ReasoningContentBlock, block))
        if kind == BlockKind.IMAGE.value:
            return self._image(cast(ImageContentBlock, block))
        if kind == BlockKind.AUDIO.value:
            return self._audio(cast(AudioContentBlock, block), fallback_id)
        if kind in (BlockKind.TOOL_CALL.value, BlockKind.SERVER_TOOL_CALL.value):
            return self._tool_call(cast(ToolCall | ServerToolCall, block))
        if kind == BlockKind.SERVER_TOOL_RESULT.value:
            return self._server_tool_result(cast(ServerToolResult, block), tool_names)
        return self.unsupported("unsupported_content", "The SDK content block has no neutral output mapping.")

    @staticmethod
    def unsupported(code: str, reason: str) -> ContentConversion:
        return ContentConversion(diagnostic=ConversionDiagnostic(code, reason), unsupported=True)

    @staticmethod
    def _text(block: TextContentBlock) -> ContentConversion:
        annotations: list[UrlCitation] = []
        unsupported = False
        for annotation in block.get("annotations", []):
            if annotation["type"] != "citation":
                unsupported = True
                continue
            url, title = annotation.get("url"), annotation.get("title")
            start, end = annotation.get("start_index"), annotation.get("end_index")
            if url is None or title is None or start is None or end is None:
                unsupported = True
                continue
            annotations.append(UrlCitation(url, title, start, end))
        diagnostic = ConversionDiagnostic(
            "unsupported_citation", "A text annotation lacks the genuine URL, title or offsets required by the neutral citation.",
        ) if unsupported else None
        return ContentConversion(TextContent(block["text"], tuple(annotations)), diagnostic, unsupported)

    def _reasoning(self, block: ReasoningContentBlock) -> ContentConversion:
        if not self.expose_reasoning:
            return ContentConversion(diagnostic=ConversionDiagnostic(
                "reasoning_not_selected", "Reasoning requires explicit developer selection.",
            ))
        if "reasoning" not in block:
            return self.unsupported("protected_reasoning", "The SDK block exposes no publishable reasoning text.")
        return ContentConversion(ReasoningContent(block["reasoning"], exposable=True))

    def _tool_call(self, block: ToolCall | ServerToolCall) -> ContentConversion:
        call_id = block["id"]
        if not call_id or not call_id.strip():
            return self.unsupported("missing_tool_call_id", "A tool call must have an SDK correlation identity.")
        if not block["name"].strip():
            return self.unsupported("missing_tool_name", "A tool call requires a genuine nonempty SDK name.")
        execution = ToolExecution.INTERNAL if block["type"] == BlockKind.SERVER_TOOL_CALL.value else self.tool_execution
        return ContentConversion(ToolCallContent(call_id, block["name"], JsonBoundary.convert(block["args"]), execution))

    @classmethod
    def tool_names(cls, blocks: Sequence[ContentBlock]) -> dict[str, str]:
        names: dict[str, str] = {}
        for block in blocks:
            if block["type"] not in (BlockKind.TOOL_CALL.value, BlockKind.SERVER_TOOL_CALL.value):
                continue
            call_id, name = block["id"], block["name"]
            if call_id and call_id.strip() and name.strip():
                cls.register_tool_name(names, call_id, name)
        return names

    @staticmethod
    def register_tool_name(names: dict[str, str], call_id: str, name: str) -> None:
        previous = names.setdefault(call_id, name)
        if previous != name:
            raise LangChainConversionError("SDK tool name changed for a correlated call identity.")

    def _server_tool_result(
        self, block: ServerToolResult, tool_names: Mapping[str, str] | None,
    ) -> ContentConversion:
        call_id = block["tool_call_id"]
        if not call_id.strip():
            return self.unsupported("missing_tool_call_id", "A tool result must have an SDK correlation identity.")
        name = tool_names.get(call_id) if tool_names is not None else None
        if name is None or not name.strip():
            return self.unsupported("missing_tool_name", "A server tool result requires a genuine name from its correlated SDK call.")
        content = ToolResultContent(
            call_id, name, JsonBoundary.convert(block.get("output")), ToolExecution.INTERNAL,
        )
        if block["status"] == "error":
            return ContentConversion(content, ConversionDiagnostic(
                "tool_result_status_unrepresentable", "The neutral tool result has no per-tool failure status.",
            ), unsupported=True)
        return ContentConversion(content)

    def _image(self, block: ImageContentBlock) -> ContentConversion:
        source = self._source(block)
        if source is None:
            return self.unsupported("unsupported_media_source", "Image output requires a URI or base64 and explicit MIME.")
        return ContentConversion(ImageContent(source))

    def _audio(self, block: AudioContentBlock, fallback_id: str) -> ContentConversion:
        source = self._source(block)
        audio_format = self._audio_formats.get(block.get("mime_type", ""))
        if source is None or audio_format is None:
            return self.unsupported("unsupported_audio_format", "Audio output requires a source and a known explicit MIME.")
        return ContentConversion(AudioContent(source, block.get("id") or fallback_id, format=audio_format))

    @staticmethod
    def _source(block: ImageContentBlock | AudioContentBlock) -> MediaSource | None:
        mime = block.get("mime_type")
        if not mime:
            return None
        uri, encoded = block.get("url"), block.get("base64")
        if uri and encoded:
            raise LangChainConversionError("Native media has both URI and encoded sources.")
        if uri:
            return MediaUri(uri, mime)
        if encoded is not None:
            return EncodedMedia(encoded, mime)
        return None
