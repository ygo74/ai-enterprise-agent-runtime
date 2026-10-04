"""Media carried without downloading, transcoding, or guessing a codec."""

from dataclasses import dataclass
from enum import StrEnum
from typing import TypeAlias


class AudioFormat(StrEnum):
    WAV = "wav"
    MP3 = "mp3"
    PCM16 = "pcm16"
    FLAC = "flac"
    OPUS = "opus"
    AAC = "aac"


@dataclass(frozen=True, slots=True)
class MediaUri:
    uri: str
    mime_type: str


@dataclass(frozen=True, slots=True)
class EncodedMedia:
    """Base64-encoded bytes, not a data URI."""

    data: str
    mime_type: str


MediaSource: TypeAlias = MediaUri | EncodedMedia
