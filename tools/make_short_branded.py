"""make_short_branded.py - branded 9:16 vertical Short from the final master.

Re-frames ``trailers/trailer_final_master.mp4`` (1920x1080, 30 fps, 44.4 s)
for Shorts / Reels / TikTok delivery:

* **Canvas** 1080x1920 (9:16).
* **Background** - the same master scaled to *fill* the vertical canvas
  (aspect-preserving increase + centre crop), then blurred at 1/4 resolution
  (``scale -> boxblur=12:3 + gblur -> upscale``) and graded UP into a bright
  readable backdrop, so the letterbox gutters read as ambient colour instead
  of black.
* **Foreground** - the sharp original 16:9 picture at width 1080, centred
  vertically (1080x608 inside 1080x1920).
* **Banners** - two in-universe drawtext lines over the blurred gutters, no
  store/platform mentions anywhere in the copy:
    - top    y=160  "BRUTAL TACTICAL ESPIONAGE"      white, 46 px
    - bottom y=h-220 "CALL OF ACARISTAN // RETARDOVICI INC."  #FF7800, 40 px
  Both centred horizontally (``x=(w-text_w)/2``). Oswald is the game's
  bundled display face (``src/core/config.py``) and ships in a single weight,
  so the "bold" weight is faked the drawtext way: a 1 px stroke painted in the
  same colour as the fill, plus a 2 px drop shadow for legibility over the
  moving blurred backdrop.
* **Audio** - the master's AAC track is stream-copied (``-c:a copy``), so it
  is bit-identical to the master: no re-encode, no loudness drift.
* **Pixel aspect** - the master ships SAR 45:56 / DAR 10:7 (a pad/scale
  artefact from the assembly); the graph forces ``setsar=1`` so the Short
  really plays back as a square-pixel 9:16 frame.

Usage
-----
    python make_short_branded.py

Output
------
    trailers/short_branded.mp4
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "trailers" / "trailer_final_master.mp4"
OUT = ROOT / "trailers" / "short_branded.mp4"
FONT = ROOT / "assets" / "fonts" / "Oswald.ttf"

W, H = 1080, 1920                  # 9:16 canvas
FG_W = 1080                        # sharp foreground width (16:9)
FG_H = 608                         # scale=1080:-2 -> 607.5 rounded up to even

TOP_TEXT = "BRUTAL TACTICAL ESPIONAGE"
TOP_Y, TOP_SIZE = 160, 46
BOT_TEXT = "CALL OF ACARISTAN // RETARDOVICI INC."
BOT_Y, BOT_SIZE = "h-220", 40      # 1920 - 220 = 1700
TOP_COLOR = "white"
BOT_COLOR = "0xFF7800"             # game accent, same as assemble_final_trailer

# Background blur/grade. A single full-res ``boxblur=25:5`` (the first cut)
# smeared the source's macroblocks into blocky rectangles and the HUD
# lettering into dirty patches; darkening it further crushed everything to
# mud. Blurring at 1/4 resolution averages those edges away (and is far
# cheaper), a gaussian pass removes the box structure before the upscale, and
# the grade LIFTS the (inherently dark) footage into a readable backdrop
# instead of black bars.
BG_DOWN = "scale=270:480:flags=area"
BG_BLUR = "boxblur=12:3,gblur=sigma=3"
BG_UP = "scale=1080:1920:flags=lanczos"
BG_GRADE = ("eq=brightness=0.08:gamma=1.15:saturation=1.45,"
            "noise=alls=2:allf=t+u")   # dithers the smooth gradients (no banding)


# ──────────────────────────────────────────────────────────────────────
# ffmpeg plumbing
# ──────────────────────────────────────────────────────────────────────
def ffmpeg_bin() -> str:
    for cand in (shutil.which("ffmpeg"), r"C:\ffmpeg\bin\ffmpeg.exe",
                 os.environ.get("FFMPEG", "")):
        if cand and (Path(cand).exists() or shutil.which(cand)):
            return cand
    raise SystemExit("ffmpeg not found (PATH, C:\\ffmpeg\\bin, or $FFMPEG)")


FFMPEG = ffmpeg_bin()
FFPROBE = shutil.which("ffprobe") or r"C:\ffmpeg\bin\ffprobe.exe"


def run(args, label: str) -> subprocess.CompletedProcess:
    t0 = time.time()
    r = subprocess.run([str(a) for a in args], stdout=subprocess.PIPE,
                       stderr=subprocess.PIPE, text=True, errors="replace")
    if r.returncode != 0:
        sys.stderr.write(f"\n[FAIL] {label}\n"
                         f"$ {' '.join(str(a) for a in args)}\n")
        sys.stderr.write((r.stderr or "")[-4000:] + "\n")
        raise SystemExit(1)
    print(f"  ok   {label}  ({time.time() - t0:.1f}s)")
    return r


def probe(path: Path) -> dict:
    r = run([FFPROBE, "-v", "error", "-show_entries",
             "stream=codec_name,codec_type,width,height,r_frame_rate,"
             "sample_rate,channels:format=duration,size",
             "-of", "json", path], f"probe {path.name}")
    return json.loads(r.stdout)


# ──────────────────────────────────────────────────────────────────────
# filtergraph
# ──────────────────────────────────────────────────────────────────────
def _font_path() -> str:
    if not FONT.exists():
        raise SystemExit(f"font missing: {FONT}")
    # The drive colon must be escaped for the filtergraph parser (same as
    # assemble_final_trailer.graph_file_input); forward slashes keep the
    # backslash-escape noise out of the rest of the path.
    return FONT.as_posix().replace(":", r"\:")


def _banner(text: str, y, size: int, color: str) -> str:
    """One centred drawtext banner (faux-bold stroke + drop shadow)."""
    return (f"drawtext=fontfile='{_font_path()}'"
            f":text='{text}'"
            f":fontcolor={color}:fontsize={size}"
            f":borderw=1:bordercolor={color}"
            # ffmpeg >= 2025 renamed shadowxoffset/yoffset -> shadowx/y.
            f":shadowx=0:shadowy=2:shadowcolor=black@0.55"
            f":x=(w-text_w)/2:y={y}")


def build_graph() -> str:
    """Blur-padded vertical grade + sharp centred foreground + banners."""
    return ";".join([
        # The master declares SAR 45:56 / DAR 10:7 (an artefact of the trailer
        # pad/scale chain). Normalise to square pixels first, otherwise the
        # finished Short would display horizontally squashed.
        "[0:v]setsar=1,split=2[bgA][fgA]",
        # Background: fill 1080x1920 (upscale + centred crop), then the
        # downscale-blur-upscale pass and a light grade (see BG_* above).
        f"[bgA]scale={W}:{H}:force_original_aspect_ratio=increase:"
        f"flags=lanczos,crop={W}:{H},"
        f"{BG_DOWN},{BG_BLUR},{BG_UP},{BG_GRADE}[bg]",
        # Foreground: sharp original 16:9 at width 1080 -> 608 tall (even).
        f"[fgA]scale={FG_W}:-2:flags=lanczos[fg]",
        # One chain (commas): overlay -> banners -> pixel format.
        ",".join([
            "[bg][fg]overlay=x=(W-w)/2:y=(H-h)/2:shortest=1",
            _banner(TOP_TEXT, TOP_Y, TOP_SIZE, TOP_COLOR),
            _banner(BOT_TEXT, BOT_Y, BOT_SIZE, BOT_COLOR),
            "setsar=1,format=yuv420p[vout]",
        ]),
    ])


# ──────────────────────────────────────────────────────────────────────
def render(out: Path) -> None:
    if not SRC.exists():
        raise SystemExit(f"input missing: {SRC}\n"
                         "run: python assemble_final_trailer.py")
    with tempfile.TemporaryDirectory(prefix="coa_short_") as td:
        graph = Path(td) / "short.ffgraph"
        graph.write_text(build_graph(), encoding="utf-8")
        args = [FFMPEG, "-y", "-i", SRC,
                "-filter_complex_script", str(graph),
                "-map", "[vout]", "-map", "0:a",
                "-c:v", "libx264", "-preset", "medium", "-crf", "18",
                "-pix_fmt", "yuv420p", "-r", "30",
                "-c:a", "copy",                      # master audio, untouched
                "-movflags", "+faststart", str(out)]
        run(args, f"render {W}x{H} short")


def report(out: Path) -> None:
    info = probe(out)
    v = next((s for s in info["streams"] if s["codec_type"] == "video"), {})
    a = next((s for s in info["streams"] if s["codec_type"] == "audio"), {})
    print("\n" + "=" * 68)
    print(f"  video    {v.get('codec_name')} {v.get('width')}x{v.get('height')}"
          f" @ {v.get('r_frame_rate')} fps  (9:16)")
    print(f"  fg       {FG_W}x{FG_H} sharp centred; "
          f"bg {W}x{H} 1/4-res blur + grade")
    print(f"  banners  '{TOP_TEXT}'  y={TOP_Y}  {TOP_SIZE}px {TOP_COLOR}")
    print(f"           '{BOT_TEXT}'  y={BOT_Y}  {BOT_SIZE}px {BOT_COLOR}")
    print(f"  audio    {a.get('codec_name')} {a.get('sample_rate')} Hz"
          f" {a.get('channels')}ch  (stream copy)")
    print(f"  length   {float(info['format']['duration']):.2f}s"
          f"   {int(info['format']['size']) // 1024} KB")
    print("=" * 68)
    print(out)


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Render the branded 1080x1920 vertical Short.")
    ap.add_argument("-o", "--out", type=Path, default=OUT,
                    help=f"output path (default: {OUT})")
    args = ap.parse_args()

    print("=" * 68)
    print("CALL OF ACARISTAN - branded vertical Short (1080x1920)")
    print("=" * 68)
    t0 = time.time()
    render(args.out)
    report(args.out)
    print(f"  elapsed  {time.time() - t0:.1f}s")
    return 0


if __name__ == "__main__":
    sys.exit(main())

