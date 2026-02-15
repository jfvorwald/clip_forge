"""Silence-cut editor — removes silence segments from video."""

from pathlib import Path

from clipforge import ffutil
from clipforge.models import Segment, TimeRange


def apply_cuts(
    input_path: Path, segments: list[Segment], output_path: Path
) -> Path:
    """Keep only segments labeled 'keep' and concatenate them."""
    keep_ranges = [
        TimeRange(start=s.start, end=s.end)
        for s in segments
        if s.label == "keep"
    ]

    if not keep_ranges:
        raise ValueError("No keep segments found — entire video would be removed")

    ffutil.concat_segments(input_path, keep_ranges, output_path)
    return output_path
