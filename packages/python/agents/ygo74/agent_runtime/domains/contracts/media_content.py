"""Media carried without downloading, transcoding, or guessing a codec."""

from dataclasses import dataclass
from enum import StrEnum
from typing import TypeAlias


class AudioFormat(StrEnum):
    """Name the audio encodings the runtime can describe without transcoding media.
    """
    WAV = "wav"
    MP3 = "mp3"
    PCM16 = "pcm16"
    FLAC = "flac"
    OPUS = "opus"
    AAC = "aac"


@dataclass(frozen=True, slots=True)
class MediaUri:
    """Reference media by absolute URI without retrieving the resource.

    Args:
        uri (str): Absolute URI identifying the media.
        mime_type (str): MIME type describing the referenced media.
    """
    uri: str
    mime_type: str


@dataclass(frozen=True, slots=True)
class EncodedMedia:
    """Carry base64-encoded media bytes without wrapping or transcoding them.

    Args:
        data (str): Base64-encoded media payload.
        mime_type (str): MIME type describing the encoded media.
    """
    data: str
    mime_type: str


MediaSource: TypeAlias = MediaUri | EncodedMedia
