# ClipForge

Local video editing tool — auto-cut silences and auto-generate captions.

Upload a video, configure silence detection thresholds, and get back a trimmed cut with dead air removed. Optionally generate captions via Whisper.

## Quick Start

```bash
# Install
pip install -e ".[dev]"

# Launch the web UI
clipforge serve
# Open http://127.0.0.1:8321
```

## Requirements

- **Python** >= 3.11
- **FFmpeg + ffprobe** on PATH
- **openai-whisper** (only for captions — install with `pip install -e ".[captions]"`)

## Usage

### Web UI

```bash
clipforge serve --port 8321
```

Upload a video in the browser, configure silence detection settings (threshold, min duration, padding), hit Process, and watch progress in real time. Preview and download the result when done.

### CLI

```bash
# Cut silence from a video
clipforge process video.mp4 --cut-silence

# Cut silence + generate captions
clipforge process video.mp4 --cut-silence --captions

# Custom settings
clipforge process video.mp4 --cut-silence \
  --silence-threshold -35 \
  --silence-min-duration 0.3 \
  --caption-model small \
  --caption-format vtt

# Use a JSON manifest
clipforge process --manifest edits.json
```

### Manifest Format

All editing operations can be declared in a JSON manifest:

```json
{
  "input": "video.mp4",
  "output": "video_edited.mp4",
  "silence_cut": {
    "enabled": true,
    "threshold_db": -30.0,
    "min_duration": 0.5,
    "padding": 0.05
  },
  "captions": {
    "enabled": true,
    "model": "base",
    "output_format": "srt"
  }
}
```

## Architecture

```
clipforge/
    cli.py              # CLI entry point (process + serve subcommands)
    engine.py           # Pipeline orchestrator: probe -> silence cut -> captions -> result
    ffutil.py           # All FFmpeg/ffprobe subprocess calls
    manifest.py         # JSON manifest schema (dataclasses)
    models.py           # Shared data types (TimeRange, Segment, ProbeResult)
    analyzers/
        silence.py      # Silence detection with edge-case handling
        transcribe.py   # Speech-to-text via Whisper
    editors/
        cut.py          # Silence removal via filter_complex concat
        captions.py     # SRT/VTT subtitle generation
    web/
        __init__.py     # Flask app factory
        routes.py       # Upload, process, SSE progress, download routes
        templates/       # Single-page Jinja2 UI
        static/          # Vanilla JS + CSS
```

The pipeline is manifest-driven: the CLI and web UI both construct a `Manifest` and pass it to `engine.process()`. Silence cutting runs first, then captioning runs on the already-cut video so timestamps match.

## Development

```bash
# Install with dev dependencies
pip install -e ".[dev]"

# Run tests
pytest tests/ -v

# Generate a synthetic test video (requires ffmpeg)
python scripts/generate_test_video.py
```

## License

MIT
