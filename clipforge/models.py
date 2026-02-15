"""Shared data types used across ClipForge."""

from dataclasses import dataclass


@dataclass
class TimeRange:
    """A start/end time pair in seconds."""

    start: float
    end: float


@dataclass
class Segment:
    """A labeled time segment, optionally carrying transcript text."""

    start: float
    end: float
    label: str
    text: str | None = None


@dataclass
class ProbeResult:
    """Metadata extracted from a media file via ffprobe."""

    duration: float
    width: int
    height: int
    fps: float
    audio_sample_rate: int
    codec_video: str
    codec_audio: str
