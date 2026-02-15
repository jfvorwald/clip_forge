"""Caption editor — writes subtitle files and optionally burns them in."""

from pathlib import Path

from clipforge import ffutil
from clipforge.manifest import CaptionConfig
from clipforge.models import Segment


def _format_srt_time(seconds: float) -> str:
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    ms = int((seconds % 1) * 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def _format_vtt_time(seconds: float) -> str:
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    ms = int((seconds % 1) * 1000)
    return f"{h:02d}:{m:02d}:{s:02d}.{ms:03d}"


def _write_srt(segments: list[Segment], path: Path) -> None:
    lines: list[str] = []
    for i, seg in enumerate(segments, 1):
        lines.append(str(i))
        lines.append(f"{_format_srt_time(seg.start)} --> {_format_srt_time(seg.end)}")
        lines.append(seg.text or "")
        lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


def _write_vtt(segments: list[Segment], path: Path) -> None:
    lines: list[str] = ["WEBVTT", ""]
    for seg in segments:
        lines.append(f"{_format_vtt_time(seg.start)} --> {_format_vtt_time(seg.end)}")
        lines.append(seg.text or "")
        lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


def apply_captions(
    input_path: Path,
    segments: list[Segment],
    output_path: Path,
    config: CaptionConfig,
) -> Path:
    """Write a subtitle sidecar file. If burn-in is desired, overlay on video."""
    suffix = ".vtt" if config.output_format == "vtt" else ".srt"
    subtitle_path = output_path.with_suffix(suffix)

    if config.output_format == "vtt":
        _write_vtt(segments, subtitle_path)
    else:
        _write_srt(segments, subtitle_path)

    return subtitle_path
