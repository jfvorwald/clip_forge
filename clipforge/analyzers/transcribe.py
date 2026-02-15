"""Speech-to-text analyzer using OpenAI Whisper."""

import tempfile
from pathlib import Path

from clipforge import ffutil
from clipforge.manifest import CaptionConfig
from clipforge.models import Segment


def transcribe(input_path: Path, config: CaptionConfig) -> list[Segment]:
    """Extract audio, run Whisper, and return timed transcript segments."""
    import whisper

    with tempfile.TemporaryDirectory() as tmpdir:
        wav_path = Path(tmpdir) / "audio.wav"
        ffutil.extract_audio(input_path, wav_path)

        model = whisper.load_model(config.model)
        result = model.transcribe(
            str(wav_path),
            language=config.language,
            word_timestamps=config.word_level,
        )

    segments: list[Segment] = []
    for seg in result["segments"]:
        segments.append(
            Segment(
                start=seg["start"],
                end=seg["end"],
                label="caption",
                text=seg["text"].strip(),
            )
        )
    return segments
