"""FFmpeg/ffprobe subprocess helpers."""

import json
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

from clipforge.models import ProbeResult, TimeRange


class FFmpegNotFoundError(RuntimeError):
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

    video_stream = next(s for s in data["streams"] if s["codec_type"] == "video")
    audio_stream = next(s for s in data["streams"] if s["codec_type"] == "audio")

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


def detect_silence(
    input_path: Path, threshold_db: float, min_duration: float
) -> list[TimeRange]:
    """Run FFmpeg silencedetect and return silent time ranges."""
    cmd = [
        "ffmpeg",
        "-i", str(input_path),
        "-af", f"silencedetect=noise={threshold_db}dB:d={min_duration}",
        "-f", "null", "-",
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    stderr = result.stderr

    starts = [float(m) for m in re.findall(r"silence_start: ([\d.]+)", stderr)]
    ends = [float(m) for m in re.findall(r"silence_end: ([\d.]+)", stderr)]

    # Pair them up; if a silence extends to EOF there may be one extra start
    ranges = []
    for i in range(min(len(starts), len(ends))):
        ranges.append(TimeRange(start=starts[i], end=ends[i]))
    return ranges


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
    """Concatenate keep-segments from input into output using the concat demuxer."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        part_paths: list[Path] = []

        # Cut each segment into a separate file
        for i, seg in enumerate(segments):
            part = tmpdir / f"part{i:04d}.ts"
            cmd = [
                "ffmpeg", "-y",
                "-i", str(input_path),
                "-ss", str(seg.start),
                "-to", str(seg.end),
                "-c", "copy",
                str(part),
            ]
            subprocess.run(cmd, capture_output=True, check=True)
            part_paths.append(part)

        # Write concat list
        concat_file = tmpdir / "concat.txt"
        concat_file.write_text(
            "\n".join(f"file '{p}'" for p in part_paths)
        )

        # Concat
        cmd = [
            "ffmpeg", "-y",
            "-f", "concat",
            "-safe", "0",
            "-i", str(concat_file),
            "-c", "copy",
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
