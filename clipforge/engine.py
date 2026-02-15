"""Orchestrator — runs the editing pipeline defined by a Manifest."""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from clipforge import ffutil
from clipforge.analyzers.silence import analyze_silence
from clipforge.analyzers.transcribe import transcribe
from clipforge.editors.captions import apply_captions
from clipforge.editors.cut import apply_cuts
from clipforge.manifest import Manifest
from clipforge.models import Segment


@dataclass
class EngineResult:
    output_path: Path
    caption_path: Path | None = None
    segments_removed: int = 0
    duration_original: float = 0.0
    duration_final: float = 0.0
    transcript_segments: list[Segment] = field(default_factory=list)


def process(
    manifest: Manifest,
    on_progress: Callable[[str, float], None] | None = None,
) -> EngineResult:
    """Execute the full editing pipeline.

    Args:
        manifest: Validated editing manifest.
        on_progress: Optional callback(stage_name, fraction_complete).
    """

    def _progress(stage: str, frac: float) -> None:
        if on_progress:
            on_progress(stage, frac)

    def _sub_progress(stage: str, base: float, span: float):
        """Return a callback that maps ffmpeg's [0,1] to [base, base+span]."""
        def cb(frac: float) -> None:
            _progress(stage, base + frac * span)
        return cb

    ffutil.check_ffmpeg()

    _progress("Probing video metadata", 0.0)
    probe_result = ffutil.probe(manifest.input)
    duration_original = probe_result.duration
    _progress("Probing video metadata", 0.05)

    current_input = manifest.input
    segments_removed = 0

    # --- Silence cutting ---
    if manifest.silence_cut.enabled:
        _progress("Scanning audio for silence", 0.06)
        segments = analyze_silence(
            current_input,
            manifest.silence_cut,
            on_progress=_sub_progress("Scanning audio for silence", 0.06, 0.19),
        )
        _progress("Analyzing segments", 0.25)

        segments_removed = sum(1 for s in segments if s.label == "silence")

        if segments_removed > 0:
            _progress(f"Encoding — cutting {segments_removed} silent segments", 0.27)
            cut_output = manifest.output.with_stem(manifest.output.stem + "_cut")
            apply_cuts(
                current_input,
                segments,
                cut_output,
                on_progress=_sub_progress(
                    f"Encoding — cutting {segments_removed} silent segments", 0.27, 0.53
                ),
            )
            current_input = cut_output
            _progress("Silence removal complete", 0.80)
        else:
            _progress("No silence found", 0.80)

    # --- Captions ---
    caption_path = None
    transcript_segments: list[Segment] = []
    if manifest.captions.enabled:
        _progress("Transcribing audio", 0.50)
        transcript_segments = transcribe(current_input, manifest.captions)

        _progress("Generating captions", 0.80)
        caption_path = apply_captions(
            current_input, transcript_segments, manifest.output, manifest.captions
        )

    # --- Finalize output ---
    _progress("Finalizing output", 0.85)
    if current_input != manifest.output:
        # If silence cut produced an intermediate file, rename it to final output
        if current_input != manifest.input:
            current_input.rename(manifest.output)
        else:
            # No edits changed the file; copy input to output
            import shutil
            shutil.copy2(manifest.input, manifest.output)

    # Probe final duration
    _progress("Verifying result", 0.92)
    final_probe = ffutil.probe(manifest.output)

    _progress("Done", 1.0)
    return EngineResult(
        output_path=manifest.output,
        caption_path=caption_path,
        segments_removed=segments_removed,
        duration_original=duration_original,
        duration_final=final_probe.duration,
        transcript_segments=transcript_segments,
    )
