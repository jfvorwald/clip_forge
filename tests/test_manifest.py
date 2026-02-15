"""Tests for manifest loading and validation."""

import json
from pathlib import Path

import pytest

from clipforge.manifest import (
    CaptionConfig,
    Manifest,
    SilenceCutConfig,
    load_manifest,
)


class TestSilenceCutConfig:
    def test_defaults(self):
        cfg = SilenceCutConfig(enabled=True)
        assert cfg.min_duration == 0.5
        assert cfg.threshold_db == -30.0
        assert cfg.padding == 0.05

    def test_custom_values(self):
        cfg = SilenceCutConfig(enabled=True, min_duration=1.0, threshold_db=-40.0, padding=0.1)
        assert cfg.min_duration == 1.0
        assert cfg.threshold_db == -40.0


class TestCaptionConfig:
    def test_defaults(self):
        cfg = CaptionConfig(enabled=True)
        assert cfg.model == "base"
        assert cfg.language is None
        assert cfg.output_format == "srt"
        assert cfg.word_level is False

    def test_custom_values(self):
        cfg = CaptionConfig(enabled=True, model="large", language="en", output_format="vtt")
        assert cfg.model == "large"
        assert cfg.output_format == "vtt"


class TestManifest:
    def test_minimal(self):
        m = Manifest(input=Path("in.mp4"), output=Path("out.mp4"))
        assert m.version == "1"
        assert m.silence_cut.enabled is False
        assert m.captions.enabled is False

    def test_full(self):
        m = Manifest(
            input=Path("in.mp4"),
            output=Path("out.mp4"),
            silence_cut=SilenceCutConfig(enabled=True),
            captions=CaptionConfig(enabled=True, model="small"),
        )
        assert m.silence_cut.enabled is True
        assert m.captions.model == "small"


class TestLoadManifest:
    def test_load_sample(self, sample_manifest_path: Path):
        m = load_manifest(sample_manifest_path)
        assert m.version == "1"
        assert m.input == Path("video.mp4")
        assert m.silence_cut.enabled is True
        assert m.captions.enabled is True
        assert m.captions.model == "base"

    def test_load_invalid_json(self, tmp_path: Path):
        bad = tmp_path / "bad.json"
        bad.write_text("not json")
        with pytest.raises(json.JSONDecodeError):
            load_manifest(bad)

    def test_load_missing_fields(self, tmp_path: Path):
        incomplete = tmp_path / "incomplete.json"
        incomplete.write_text('{"version": "1"}')
        with pytest.raises(ValueError, match="must contain"):
            load_manifest(incomplete)
