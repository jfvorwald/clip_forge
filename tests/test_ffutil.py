"""Unit tests for ffutil — silence parsing and subprocess wrappers."""

from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from clipforge.ffutil import (
    NoAudioStreamError,
    parse_silence_ranges,
    detect_silence,
    concat_segments,
    probe,
)
from clipforge.models import TimeRange


# ---------------------------------------------------------------------------
# parse_silence_ranges (pure parsing, no subprocess)
# ---------------------------------------------------------------------------

SAMPLE_STDERR = """\
[silencedetect @ 0x...] silence_start: 1.5
[silencedetect @ 0x...] silence_end: 3.2 | silence_duration: 1.7
[silencedetect @ 0x...] silence_start: 7.0
[silencedetect @ 0x...] silence_end: 9.5 | silence_duration: 2.5
"""


class TestParseSilenceRanges:
    def test_basic_paired(self):
        ranges = parse_silence_ranges(SAMPLE_STDERR)
        assert ranges == [
            TimeRange(start=1.5, end=3.2),
            TimeRange(start=7.0, end=9.5),
        ]

    def test_unpaired_trailing_silence_with_duration(self):
        stderr = (
            "[silencedetect @ 0x...] silence_start: 1.0\n"
            "[silencedetect @ 0x...] silence_end: 2.0 | silence_duration: 1.0\n"
            "[silencedetect @ 0x...] silence_start: 8.0\n"
        )
        ranges = parse_silence_ranges(stderr, duration=10.0)
        assert ranges == [
            TimeRange(start=1.0, end=2.0),
            TimeRange(start=8.0, end=10.0),
        ]

    def test_unpaired_trailing_silence_without_duration(self):
        stderr = (
            "[silencedetect @ 0x...] silence_start: 8.0\n"
        )
        ranges = parse_silence_ranges(stderr, duration=None)
        assert ranges == []

    def test_empty_stderr(self):
        assert parse_silence_ranges("") == []

    def test_no_silence_detected(self):
        stderr = "Some other ffmpeg output\nsize=0 speed=1x\n"
        assert parse_silence_ranges(stderr) == []

    def test_silence_at_start_of_file(self):
        stderr = (
            "[silencedetect @ 0x...] silence_start: 0\n"
            "[silencedetect @ 0x...] silence_end: 2.5 | silence_duration: 2.5\n"
        )
        ranges = parse_silence_ranges(stderr)
        assert ranges == [TimeRange(start=0.0, end=2.5)]


# ---------------------------------------------------------------------------
# detect_silence (mocked subprocess)
# ---------------------------------------------------------------------------

class TestDetectSilence:
    @patch("clipforge.ffutil.subprocess.run")
    def test_returns_parsed_ranges(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0, stderr=SAMPLE_STDERR)
        ranges = detect_silence(Path("video.mp4"), threshold_db=-30, min_duration=0.5)
        assert len(ranges) == 2
        assert ranges[0] == TimeRange(start=1.5, end=3.2)

    @patch("clipforge.ffutil.subprocess.run")
    def test_empty_output(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0, stderr="")
        ranges = detect_silence(Path("video.mp4"), threshold_db=-30, min_duration=0.5)
        assert ranges == []

    @patch("clipforge.ffutil.subprocess.run")
    def test_trailing_silence_with_duration(self, mock_run):
        stderr = "[silencedetect @ 0x...] silence_start: 8.0\n"
        mock_run.return_value = MagicMock(returncode=0, stderr=stderr)
        ranges = detect_silence(
            Path("video.mp4"), threshold_db=-30, min_duration=0.5, duration=10.0
        )
        assert ranges == [TimeRange(start=8.0, end=10.0)]

    @patch("clipforge.ffutil.subprocess.run")
    def test_failure_with_no_stderr_raises(self, mock_run):
        mock_run.return_value = MagicMock(returncode=1, stderr="")
        with pytest.raises(RuntimeError, match="silencedetect failed"):
            detect_silence(Path("video.mp4"), threshold_db=-30, min_duration=0.5)


# ---------------------------------------------------------------------------
# probe (mocked subprocess)
# ---------------------------------------------------------------------------

PROBE_JSON = {
    "format": {"duration": "60.0"},
    "streams": [
        {
            "codec_type": "video",
            "codec_name": "h264",
            "width": 1920,
            "height": 1080,
            "r_frame_rate": "30/1",
        },
        {
            "codec_type": "audio",
            "codec_name": "aac",
            "sample_rate": "44100",
        },
    ],
}


class TestProbe:
    @patch("clipforge.ffutil.subprocess.run")
    def test_basic(self, mock_run):
        import json
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout=json.dumps(PROBE_JSON),
        )
        result = probe(Path("video.mp4"))
        assert result.duration == 60.0
        assert result.width == 1920
        assert result.codec_audio == "aac"

    @patch("clipforge.ffutil.subprocess.run")
    def test_no_audio_stream(self, mock_run):
        import json
        data = {
            "format": {"duration": "60.0"},
            "streams": [
                {
                    "codec_type": "video",
                    "codec_name": "h264",
                    "width": 1920,
                    "height": 1080,
                    "r_frame_rate": "30/1",
                },
            ],
        }
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout=json.dumps(data),
        )
        with pytest.raises(NoAudioStreamError, match="No audio stream"):
            probe(Path("video.mp4"))

    @patch("clipforge.ffutil.subprocess.run")
    def test_no_video_stream(self, mock_run):
        import json
        data = {
            "format": {"duration": "60.0"},
            "streams": [
                {
                    "codec_type": "audio",
                    "codec_name": "aac",
                    "sample_rate": "44100",
                },
            ],
        }
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout=json.dumps(data),
        )
        with pytest.raises(ValueError, match="No video stream"):
            probe(Path("video.mp4"))


# ---------------------------------------------------------------------------
# concat_segments (mocked subprocess — just verify the command shape)
# ---------------------------------------------------------------------------

class TestConcatSegments:
    @patch("clipforge.ffutil.subprocess.run")
    def test_builds_filter_complex(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0)
        segments = [TimeRange(start=0, end=5), TimeRange(start=8, end=12)]
        concat_segments(Path("in.mp4"), segments, Path("out.mp4"))

        mock_run.assert_called_once()
        cmd = mock_run.call_args[0][0]
        assert "-filter_complex" in cmd
        fc_idx = cmd.index("-filter_complex")
        fc = cmd[fc_idx + 1]
        assert "concat=n=2" in fc
        assert "[outv]" in fc
        assert "[outa]" in fc

    def test_empty_segments_raises(self):
        with pytest.raises(ValueError, match="empty segment list"):
            concat_segments(Path("in.mp4"), [], Path("out.mp4"))
