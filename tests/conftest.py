"""Shared test fixtures."""

from pathlib import Path

import pytest

FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture
def sample_manifest_path() -> Path:
    return FIXTURES_DIR / "sample_manifest.json"
