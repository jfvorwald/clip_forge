"""Unit tests for the silence analyzer."""

from pathlib import Path
from unittest.mock import patch

import pytest

from clipforge.analyzers.silence import analyze_silence
from clipforge.manifest import SilenceCutConfig
from clipforge.models import ProbeResult, Segment, TimeRange


def _make_probe(duration: float = 30.0) -> ProbeResult:
    return ProbeResult(
        duration=duration,
        width=1920,
        height=1080,
        fps=30.0,
        audio_sample_rate=44100,
        codec_video="h264",
        codec_audio="aac",
    )


CONFIG = SilenceCutConfig(enabled=True, min_duration=0.5, threshold_db=-30.0, padding=0.1)


class TestAnalyzeSilenceNoSilence:
    """When no silence is detected, the entire file should be one keep segment."""

    @patch("clipforge.analyzers.silence.ffutil.detect_silence", return_value=[])
    @patch("clipforge.analyzers.silence.ffutil.probe")
    def test_returns_single_keep(self, mock_probe, mock_detect):
        mock_probe.return_value = _make_probe(30.0)
        result = analyze_silence(Path("video.mp4"), CONFIG)
        assert len(result) == 1
        assert result[0] == Segment(start=0.0, end=30.0, label="keep")


class TestAnalyzeSilenceBasic:
    """Standard silence in the middle of the file."""

    @patch("clipforge.analyzers.silence.ffutil.detect_silence")
    @patch("clipforge.analyzers.silence.ffutil.probe")
    def test_keep_silence_keep(self, mock_probe, mock_detect):
        mock_probe.return_value = _make_probe(30.0)
        mock_detect.return_value = [TimeRange(start=10.0, end=15.0)]
        config = SilenceCutConfig(enabled=True, padding=0.0)

        result = analyze_silence(Path("video.mp4"), config)

        assert result == [
            Segment(start=0.0, end=10.0, label="keep"),
            Segment(start=10.0, end=15.0, label="silence"),
            Segment(start=15.0, end=30.0, label="keep"),
        ]


class TestAnalyzeSilenceAtStart:
    """Silence at the very beginning of the file."""

    @patch("clipforge.analyzers.silence.ffutil.detect_silence")
    @patch("clipforge.analyzers.silence.ffutil.probe")
    def test_silence_then_keep(self, mock_probe, mock_detect):
        mock_probe.return_value = _make_probe(20.0)
        mock_detect.return_value = [TimeRange(start=0.0, end=3.0)]
        config = SilenceCutConfig(enabled=True, padding=0.0)

        result = analyze_silence(Path("video.mp4"), config)

        assert result == [
            Segment(start=0.0, end=3.0, label="silence"),
            Segment(start=3.0, end=20.0, label="keep"),
        ]


class TestAnalyzeSilenceAtEnd:
    """Silence extending to the end of the file."""

    @patch("clipforge.analyzers.silence.ffutil.detect_silence")
    @patch("clipforge.analyzers.silence.ffutil.probe")
    def test_keep_then_silence(self, mock_probe, mock_detect):
        mock_probe.return_value = _make_probe(20.0)
        mock_detect.return_value = [TimeRange(start=17.0, end=20.0)]
        config = SilenceCutConfig(enabled=True, padding=0.0)

        result = analyze_silence(Path("video.mp4"), config)

        assert result == [
            Segment(start=0.0, end=17.0, label="keep"),
            Segment(start=17.0, end=20.0, label="silence"),
        ]


class TestAnalyzeSilencePadding:
    """Padding shrinks silence regions and expands keep regions."""

    @patch("clipforge.analyzers.silence.ffutil.detect_silence")
    @patch("clipforge.analyzers.silence.ffutil.probe")
    def test_padding_shrinks_silence(self, mock_probe, mock_detect):
        mock_probe.return_value = _make_probe(30.0)
        mock_detect.return_value = [TimeRange(start=10.0, end=15.0)]
        config = SilenceCutConfig(enabled=True, padding=0.5)

        result = analyze_silence(Path("video.mp4"), config)

        assert result == [
            Segment(start=0.0, end=10.5, label="keep"),
            Segment(start=10.5, end=14.5, label="silence"),
            Segment(start=14.5, end=30.0, label="keep"),
        ]

    @patch("clipforge.analyzers.silence.ffutil.detect_silence")
    @patch("clipforge.analyzers.silence.ffutil.probe")
    def test_padding_eliminates_small_gap(self, mock_probe, mock_detect):
        """If padding is larger than half the silence, the gap disappears."""
        mock_probe.return_value = _make_probe(30.0)
        mock_detect.return_value = [TimeRange(start=10.0, end=10.5)]
        config = SilenceCutConfig(enabled=True, padding=0.5)

        result = analyze_silence(Path("video.mp4"), config)

        # The 0.5s silence with 0.5 padding on each side is eliminated
        assert len(result) == 1
        assert result[0] == Segment(start=0.0, end=30.0, label="keep")


class TestAnalyzeSilenceClamping:
    """Segment boundaries should be clamped to [0, duration]."""

    @patch("clipforge.analyzers.silence.ffutil.detect_silence")
    @patch("clipforge.analyzers.silence.ffutil.probe")
    def test_padding_does_not_go_negative(self, mock_probe, mock_detect):
        mock_probe.return_value = _make_probe(10.0)
        # Silence at very start — padding would push start negative
        mock_detect.return_value = [TimeRange(start=0.0, end=2.0)]
        config = SilenceCutConfig(enabled=True, padding=0.5)

        result = analyze_silence(Path("video.mp4"), config)

        # silence_start = max(0.0 + 0.5, 0.0) = 0.5, silence_end = min(2.0 - 0.5, 10.0) = 1.5
        assert result[0] == Segment(start=0.0, end=0.5, label="keep")
        assert result[1] == Segment(start=0.5, end=1.5, label="silence")

    @patch("clipforge.analyzers.silence.ffutil.detect_silence")
    @patch("clipforge.analyzers.silence.ffutil.probe")
    def test_padding_does_not_exceed_duration(self, mock_probe, mock_detect):
        mock_probe.return_value = _make_probe(10.0)
        mock_detect.return_value = [TimeRange(start=8.0, end=10.5)]
        config = SilenceCutConfig(enabled=True, padding=0.5)

        result = analyze_silence(Path("video.mp4"), config)

        # silence_end clamped to duration
        silence_segs = [s for s in result if s.label == "silence"]
        assert all(s.end <= 10.0 for s in silence_segs)


class TestAnalyzeSilenceEntireFileSilent:
    """The entire file is silent — should still return valid segments."""

    @patch("clipforge.analyzers.silence.ffutil.detect_silence")
    @patch("clipforge.analyzers.silence.ffutil.probe")
    def test_whole_file_silent(self, mock_probe, mock_detect):
        mock_probe.return_value = _make_probe(10.0)
        mock_detect.return_value = [TimeRange(start=0.0, end=10.0)]
        config = SilenceCutConfig(enabled=True, padding=0.0)

        result = analyze_silence(Path("video.mp4"), config)

        assert result == [Segment(start=0.0, end=10.0, label="silence")]
