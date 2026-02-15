"""FFmpeg/ffprobe subprocess helpers."""

import json
import re
import shutil
import subprocess
from pathlib import Path

from clipforge.models import ProbeResult, TimeRange


class FFmpegNotFoundError(RuntimeError):
    pass


class NoAudioStreamError(ValueError):
    """Raised when the input file has no audio stream."""
    pass


def check_ffmpeg() -> None:
    """Raise FFmpegNotFoundError if ffmpeg/ffprobe are not on PATH."""
    for cmd in ("ffmpeg", "ffprobe"):
        if shutil.which(cmd) is None:
            raise FFmpegNotFoundError(f"{cmd} not found on PATH")


def probe(input_path: Path) -> ProbeResult:
    """Extract media metadata via ffprobe."""
    cmd = [
        "ffprobe",
        "-v", "quiet",
        "-print_format", "json",
        "-show_format",
        "-show_streams",
        str(input_path),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, check=True)
    data = json.loads(result.stdout)

    video_stream = next(
        (s for s in data["streams"] if s["codec_type"] == "video"), None
    )
    audio_stream = next(
        (s for s in data["streams"] if s["codec_type"] == "audio"), None
    )

    if video_stream is None:
        raise ValueError(f"No video stream found in {input_path}")
    if audio_stream is None:
        raise NoAudioStreamError(
            f"No audio stream found in {input_path}; silence detection requires audio"
        )

    # Parse fps from r_frame_rate (e.g. "30/1")
    num, den = video_stream["r_frame_rate"].split("/")
    fps = int(num) / int(den)

    return ProbeResult(
        duration=float(data["format"]["duration"]),
        width=int(video_stream["width"]),
        height=int(video_stream["height"]),
        fps=fps,
        audio_sample_rate=int(audio_stream["sample_rate"]),
        codec_video=video_stream["codec_name"],
        codec_audio=audio_stream["codec_name"],
    )


def parse_silence_ranges(stderr: str, duration: float | None = None) -> list[TimeRange]:
    """Parse silencedetect output from ffmpeg stderr into TimeRanges.

    If a silence_start has no matching silence_end (silence extends to EOF),
    ``duration`` is used as the end time. If ``duration`` is also None the
    unpaired start is dropped.
    """
    starts = [float(m) for m in re.findall(r"silence_start: ([\d.]+)", stderr)]
    ends = [float(m) for m in re.findall(r"silence_end: ([\d.]+)", stderr)]

    ranges: list[TimeRange] = []
    for i, start in enumerate(starts):
        if i < len(ends):
            ranges.append(TimeRange(start=start, end=ends[i]))
        elif duration is not None:
            # Unpaired silence_start — silence extends to EOF
            ranges.append(TimeRange(start=start, end=duration))
    return ranges


def detect_silence(
    input_path: Path,
    threshold_db: float,
    min_duration: float,
    duration: float | None = None,
) -> list[TimeRange]:
    """Run FFmpeg silencedetect and return silent time ranges.

    *duration* is used to cap trailing silence that extends to EOF (an unpaired
    ``silence_start`` with no matching ``silence_end``).  When not supplied, any
    unpaired trailing silence is dropped.
    """
    cmd = [
        "ffmpeg",
        "-i", str(input_path),
        "-af", f"silencedetect=noise={threshold_db}dB:d={min_duration}",
        "-f", "null", "-",
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode != 0 and not result.stderr:
        raise RuntimeError(
            f"ffmpeg silencedetect failed (rc={result.returncode}) with no output"
        )

    return parse_silence_ranges(result.stderr, duration=duration)


def extract_audio(
    input_path: Path, output_path: Path, sample_rate: int = 16000
) -> Path:
    """Extract audio as mono WAV at the given sample rate (for Whisper)."""
    cmd = [
        "ffmpeg", "-y",
        "-i", str(input_path),
        "-vn",
        "-acodec", "pcm_s16le",
        "-ar", str(sample_rate),
        "-ac", "1",
        str(output_path),
    ]
    subprocess.run(cmd, capture_output=True, check=True)
    return output_path


def concat_segments(
    input_path: Path, segments: list[TimeRange], output_path: Path
) -> None:
    """Concatenate keep-segments using a single ffmpeg filter_complex call.

    Uses trim/atrim + concat filters so no intermediate files are needed and
    the approach works regardless of the input codec/container.
    """
    if not segments:
        raise ValueError("concat_segments called with empty segment list")

    n = len(segments)
    filter_parts: list[str] = []
    stream_labels: list[str] = []

    for i, seg in enumerate(segments):
        filter_parts.append(
            f"[0:v]trim=start={seg.start}:end={seg.end},setpts=PTS-STARTPTS[v{i}]"
        )
        filter_parts.append(
            f"[0:a]atrim=start={seg.start}:end={seg.end},asetpts=PTS-STARTPTS[a{i}]"
        )
        stream_labels.append(f"[v{i}][a{i}]")

    concat_input = "".join(stream_labels)
    filter_parts.append(f"{concat_input}concat=n={n}:v=1:a=1[outv][outa]")

    filter_complex = ";\n".join(filter_parts)

    cmd = [
        "ffmpeg", "-y",
        "-i", str(input_path),
        "-filter_complex", filter_complex,
        "-map", "[outv]",
        "-map", "[outa]",
        str(output_path),
    ]
    subprocess.run(cmd, capture_output=True, check=True)


def burn_captions(
    input_path: Path, subtitle_path: Path, output_path: Path
) -> None:
    """Hard-burn subtitles into video."""
    cmd = [
        "ffmpeg", "-y",
        "-i", str(input_path),
        "-vf", f"subtitles={subtitle_path}",
        str(output_path),
    ]
    subprocess.run(cmd, capture_output=True, check=True)
