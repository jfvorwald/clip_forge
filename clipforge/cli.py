"""Thin CLI entry point — builds a Manifest and calls the engine."""

import argparse
import sys
from pathlib import Path

from clipforge.engine import process
from clipforge.manifest import CaptionConfig, Manifest, SilenceCutConfig, load_manifest


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="clipforge",
        description="ClipForge — local video editing: silence cutting & auto-captions.",
    )
    sub = parser.add_subparsers(dest="command")

    proc = sub.add_parser("process", help="Process a video file")
    proc.add_argument("video", nargs="?", type=Path, help="Input video file")
    proc.add_argument("--manifest", "-m", type=Path, help="Path to a JSON manifest file")
    proc.add_argument("--output", "-o", type=Path, help="Output file path")
    proc.add_argument("--cut-silence", action="store_true", help="Auto-cut silent segments")
    proc.add_argument("--captions", action="store_true", help="Auto-generate captions")
    proc.add_argument("--silence-threshold", type=float, default=-30.0, help="Silence threshold in dB")
    proc.add_argument("--silence-min-duration", type=float, default=0.5, help="Minimum silence duration (seconds)")
    proc.add_argument("--caption-model", type=str, default="base", help="Whisper model size")
    proc.add_argument("--caption-format", choices=["srt", "vtt"], default="srt", help="Caption output format")

    serve = sub.add_parser("serve", help="Launch the web UI")
    serve.add_argument("--port", type=int, default=8321, help="Port to listen on")
    serve.add_argument("--host", type=str, default="127.0.0.1", help="Host to bind to")

    args = parser.parse_args()

    if args.command is None:
        parser.print_help()
        sys.exit(0)

    if args.command == "serve":
        from clipforge.web import create_app
        app = create_app()
        print(f"ClipForge web UI: http://{args.host}:{args.port}")
        app.run(host=args.host, port=args.port, debug=False)
        return

    if args.manifest:
        m = load_manifest(args.manifest)
    elif args.video:
        output = args.output or args.video.with_stem(args.video.stem + "_edited")
        m = Manifest(
            input=args.video,
            output=output,
            silence_cut=SilenceCutConfig(
                enabled=args.cut_silence,
                threshold_db=args.silence_threshold,
                min_duration=args.silence_min_duration,
            ),
            captions=CaptionConfig(
                enabled=args.captions,
                model=args.caption_model,
                output_format=args.caption_format,
            ),
        )
    else:
        print("Error: provide either a VIDEO argument or --manifest.", file=sys.stderr)
        sys.exit(1)

    def on_progress(stage: str, frac: float) -> None:
        print(f"  [{frac:3.0%}] {stage}")

    result = process(m, on_progress=on_progress)

    print()
    print(f"Done! Output: {result.output_path}")
    print(f"  Duration: {result.duration_original:.1f}s -> {result.duration_final:.1f}s")
    if result.segments_removed:
        print(f"  Silent segments removed: {result.segments_removed}")
    if result.caption_path:
        print(f"  Captions: {result.caption_path}")
