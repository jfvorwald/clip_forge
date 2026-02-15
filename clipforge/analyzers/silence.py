"""Silence detection analyzer."""

from pathlib import Path
from typing import Callable

from clipforge import ffutil
from clipforge.manifest import SilenceCutConfig
from clipforge.models import Segment


def analyze_silence(
    input_path: Path,
    config: SilenceCutConfig,
    on_progress: Callable[[float], None] | None = None,
) -> list[Segment]:
    """Detect silence and return labeled keep/silence segments.

    Returns segments covering the full duration, each labeled "keep" or "silence".
    Padding is subtracted from silence boundaries (added to keep regions).
    """
    probe = ffutil.probe(input_path)
    duration = probe.duration

    silent_ranges = ffutil.detect_silence(
        input_path,
        threshold_db=config.threshold_db,
        min_duration=config.min_duration,
        duration=duration,
        on_progress=on_progress,
    )

    # No silence detected — the entire file is one keep segment
    if not silent_ranges:
        return [Segment(start=0.0, end=duration, label="keep")]

    segments: list[Segment] = []
    cursor = 0.0

    for sr in silent_ranges:
        # Apply padding: shrink silence, expand keep
        silence_start = max(sr.start + config.padding, 0.0)
        silence_end = min(sr.end - config.padding, duration)

        if silence_start < cursor:
            silence_start = cursor
        if silence_end <= silence_start:
            continue

        # Keep region before this silence
        if silence_start > cursor:
            segments.append(Segment(start=cursor, end=silence_start, label="keep"))

        segments.append(Segment(start=silence_start, end=silence_end, label="silence"))
        cursor = silence_end

    # Trailing keep region
    if cursor < duration:
        segments.append(Segment(start=cursor, end=duration, label="keep"))

    # If all silence was eliminated by padding, return single keep segment
    if not segments:
        return [Segment(start=0.0, end=duration, label="keep")]

    return segments
