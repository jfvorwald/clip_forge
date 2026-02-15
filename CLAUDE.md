# ClipForge

Local YouTube video editing tool — auto-cut silences and auto-generate captions.

## Architecture

- **Manifest-driven**: All editing operations are declared in a JSON manifest (Pydantic schema in `manifest.py`). The CLI constructs a Manifest from flags; a future API will accept one directly.
- **Engine**: `engine.py` orchestrates the pipeline: probe → silence cut → captions → result.
- **Analyzers** (`analyzers/`): Detect features (silence, speech) and return `Segment` lists.
- **Editors** (`editors/`): Apply edits (cut, captions) using analyzer output.
- **ffutil**: All FFmpeg subprocess calls are centralized here.

## Key conventions

- Pipeline order matters: silence cutting runs first, captioning runs on the already-cut video so timestamps match.
- All data types are Pydantic `BaseModel` (in `models.py` and `manifest.py`).
- `engine.process()` accepts an `on_progress` callback for UI updates.

## Commands

```bash
pip install -e ".[dev]"     # Install with dev dependencies
pytest                       # Run tests
clipforge --help             # CLI usage
clipforge process video.mp4 --cut-silence --captions
clipforge process --manifest edits.json
```

## Dependencies

- FFmpeg + ffprobe must be on PATH
- Python >=3.11
- openai-whisper for transcription
