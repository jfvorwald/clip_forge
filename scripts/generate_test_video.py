#!/usr/bin/env python3
"""Generate a synthetic test video for ClipForge pipeline testing.

Produces a ~22-second video with alternating tone+color and silence+black segments:
  0-3s   440 Hz tone + blue
  3-6s   silence + black
  6-10s  880 Hz tone + red
  10-12s silence + black
  12-16s 440 Hz tone + green
  16-18s silence + black
  18-22s 660 Hz tone + yellow
"""

import subprocess
import sys
from pathlib import Path


def generate_test_video(output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)

    audio_filter = (
        "sine=f=440:d=3[a0];"
        "anullsrc=d=3[s0];"
        "sine=f=880:d=4[a1];"
        "anullsrc=d=2[s1];"
        "sine=f=440:d=4[a2];"
        "anullsrc=d=2[s2];"
        "sine=f=660:d=4[a3];"
        "[a0][s0][a1][s1][a2][s2][a3]concat=n=7:v=0:a=1[aout]"
    )

    video_filter = (
        "color=c=blue:s=320x240:d=3:r=30[v0];"
        "color=c=black:s=320x240:d=3:r=30[v1];"
        "color=c=red:s=320x240:d=4:r=30[v2];"
        "color=c=black:s=320x240:d=2:r=30[v3];"
        "color=c=green:s=320x240:d=4:r=30[v4];"
        "color=c=black:s=320x240:d=2:r=30[v5];"
        "color=c=yellow:s=320x240:d=4:r=30[v6];"
        "[v0][v1][v2][v3][v4][v5][v6]concat=n=7:v=1:a=0[vout]"
    )

    filter_complex = audio_filter + ";" + video_filter

    cmd = [
        "ffmpeg", "-y",
        "-filter_complex", filter_complex,
        "-map", "[vout]",
        "-map", "[aout]",
        "-c:v", "libx264",
        "-c:a", "aac",
        "-shortest",
        str(output),
    ]
    subprocess.run(cmd, check=True)
    print(f"Generated: {output}")


if __name__ == "__main__":
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("tests/fixtures/synthetic.mp4")
    generate_test_video(out)
