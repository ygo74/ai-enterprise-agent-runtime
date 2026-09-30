from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from ygo74.agent_runtime.domains.contracts.json_value import JsonValue


@dataclass(slots=True)
class StandardStreamingExchangeEvent:
    request_id: str
    sequence: int
    event_type: str
    delta: Any | None = None
    final_output: Any | None = None
    error: dict[str, Any] | None = None


class OpenAIResponsesStreamEventType(StrEnum):
    AUDIO_DELTA = "response.audio.delta"
    AUDIO_DONE = "response.audio.done"
    AUDIO_TRANSCRIPT_DELTA = "response.audio.transcript.delta"
    AUDIO_TRANSCRIPT_DONE = "response.audio.transcript.done"
    CODE_INTERPRETER_CALL_CODE_DELTA = "response.code_interpreter_call_code.delta"
    CODE_INTERPRETER_CALL_CODE_DONE = "response.code_interpreter_call_code.done"
    CODE_INTERPRETER_CALL_COMPLETED = "response.code_interpreter_call.completed"
    CODE_INTERPRETER_CALL_IN_PROGRESS = "response.code_interpreter_call.in_progress"
    CODE_INTERPRETER_CALL_INTERPRETING = "response.code_interpreter_call.interpreting"
    COMPACTION_COMPACTING = "response.compaction.compacting"
    COMPLETED = "response.completed"
    CONTENT_PART_ADDED = "response.content_part.added"
    CONTENT_PART_DONE = "response.content_part.done"
    CREATED = "response.created"
    ERROR = "error"
    FILE_SEARCH_CALL_COMPLETED = "response.file_search_call.completed"
    FILE_SEARCH_CALL_IN_PROGRESS = "response.file_search_call.in_progress"
    FILE_SEARCH_CALL_SEARCHING = "response.file_search_call.searching"
    FUNCTION_CALL_ARGUMENTS_DELTA = "response.function_call_arguments.delta"
    FUNCTION_CALL_ARGUMENTS_DONE = "response.function_call_arguments.done"
    SHELL_CALL_COMMAND_ADDED = "response.shell_call_command.added"
    SHELL_CALL_COMMAND_DELTA = "response.shell_call_command.delta"
    SHELL_CALL_COMMAND_DONE = "response.shell_call_command.done"
    SHELL_CALL_OUTPUT_CONTENT_DELTA = "response.shell_call_output_content.delta"
    SHELL_CALL_OUTPUT_CONTENT_DONE = "response.shell_call_output_content.done"
    IN_PROGRESS = "response.in_progress"
    FAILED = "response.failed"
    INCOMPLETE = "response.incomplete"
    OUTPUT_ITEM_ADDED = "response.output_item.added"
    OUTPUT_ITEM_DONE = "response.output_item.done"
    REASONING_SUMMARY_PART_ADDED = "response.reasoning_summary_part.added"
    REASONING_SUMMARY_PART_DONE = "response.reasoning_summary_part.done"
    REASONING_SUMMARY_TEXT_DELTA = "response.reasoning_summary_text.delta"
    REASONING_SUMMARY_TEXT_DONE = "response.reasoning_summary_text.done"
    REASONING_TEXT_DELTA = "response.reasoning_text.delta"
    REASONING_TEXT_DONE = "response.reasoning_text.done"
    REFUSAL_DELTA = "response.refusal.delta"
    REFUSAL_DONE = "response.refusal.done"
    OUTPUT_TEXT_DELTA = "response.output_text.delta"
    OUTPUT_TEXT_DONE = "response.output_text.done"
    WEB_SEARCH_CALL_COMPLETED = "response.web_search_call.completed"
    WEB_SEARCH_CALL_IN_PROGRESS = "response.web_search_call.in_progress"
    WEB_SEARCH_CALL_SEARCHING = "response.web_search_call.searching"
    IMAGE_GENERATION_CALL_COMPLETED = "response.image_generation_call.completed"
    IMAGE_GENERATION_CALL_GENERATING = "response.image_generation_call.generating"
    IMAGE_GENERATION_CALL_IN_PROGRESS = "response.image_generation_call.in_progress"
    IMAGE_GENERATION_CALL_PARTIAL_IMAGE = "response.image_generation_call.partial_image"
    MCP_CALL_ARGUMENTS_DELTA = "response.mcp_call_arguments.delta"
    MCP_CALL_ARGUMENTS_DONE = "response.mcp_call_arguments.done"
    MCP_CALL_COMPLETED = "response.mcp_call.completed"
    MCP_CALL_FAILED = "response.mcp_call.failed"
    MCP_CALL_IN_PROGRESS = "response.mcp_call.in_progress"
    MCP_LIST_TOOLS_COMPLETED = "response.mcp_list_tools.completed"
    MCP_LIST_TOOLS_FAILED = "response.mcp_list_tools.failed"
    MCP_LIST_TOOLS_IN_PROGRESS = "response.mcp_list_tools.in_progress"
    OUTPUT_TEXT_ANNOTATION_ADDED = "response.output_text.annotation.added"
    QUEUED = "response.queued"
    CUSTOM_TOOL_CALL_INPUT_DELTA = "response.custom_tool_call_input.delta"
    CUSTOM_TOOL_CALL_INPUT_DONE = "response.custom_tool_call_input.done"


@dataclass(slots=True, frozen=True)
class OpenAIResponsesStreamEvent:
    """A typed Responses event carrying its original wire payload."""

    event_type: OpenAIResponsesStreamEventType
    payload: dict[str, JsonValue]
