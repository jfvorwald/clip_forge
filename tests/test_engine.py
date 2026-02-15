"""Tests for the engine module."""

from pathlib import Path
from unittest.mock import MagicMock, patch

from clipforge.engine import EngineResult


class TestEngineResult:
    def test_defaults(self):
        r = EngineResult(output_path=Path("out.mp4"))
        assert r.caption_path is None
        assert r.segments_removed == 0
        assert r.duration_original == 0.0
        assert r.duration_final == 0.0
        assert r.transcript_segments == []
