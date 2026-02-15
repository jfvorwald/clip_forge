"""JSON manifest schema — the contract between CLI/API and engine."""

import json
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class SilenceCutConfig:
    """Configuration for silence detection and removal."""

    enabled: bool = False
    min_duration: float = 0.5
    threshold_db: float = -30.0
    padding: float = 0.05


@dataclass
class CaptionConfig:
    """Configuration for automatic captioning via Whisper."""

    enabled: bool = False
    model: str = "base"
    language: str | None = None
    output_format: str = "srt"
    word_level: bool = False


@dataclass
class Manifest:
    """Top-level editing manifest."""

    input: Path
    output: Path
    version: str = "1"
    silence_cut: SilenceCutConfig = field(default_factory=SilenceCutConfig)
    captions: CaptionConfig = field(default_factory=CaptionConfig)


def load_manifest(path: str | Path) -> Manifest:
    """Load and validate a manifest from a JSON file."""
    path = Path(path)
    data = json.loads(path.read_text())

    if "input" not in data or "output" not in data:
        raise ValueError("Manifest must contain 'input' and 'output' fields")

    silence_cut = SilenceCutConfig(**data["silence_cut"]) if "silence_cut" in data else SilenceCutConfig()
    captions = CaptionConfig(**data["captions"]) if "captions" in data else CaptionConfig()

    return Manifest(
        version=data.get("version", "1"),
        input=Path(data["input"]),
        output=Path(data["output"]),
        silence_cut=silence_cut,
        captions=captions,
    )
