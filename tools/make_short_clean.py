"""make_short_clean.py - 9:16 vertical Short from the final master.

Takes ``trailers/trailer_final_master.mp4`` (1920x1080, AAC stereo) and
re-composes it onto a 1080x1920 canvas:

* BACKGROUND  - cover-scale + crop to fill 1080x1920, heavy ``boxblur=25:5``,
  darkened with ``eq=brightness=-0.15`` so it reads as an ambient wash.
* FOREGROUND  - the untouched 16:9 picture, sharp, scaled to width 1080 and
  vertically centred (``overlay=0:(H-h)/2``).
* TEXT        - none. 100% clean / cinematic, no titles, no bug, no CTA.
* AUDIO       - the master track copied bit-for-bit (``-c:a copy``).

Output: ``trailers/short_clean.mp4``

Usage
-----
    python make_short_clean.py
"""
import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "trailers" / "trailer_final_master.mp4"
OUT = ROOT / "trailers" / "short_clean.mp4"

W, H = 1080, 1920          # 9:16 vertical canvas
FPS = None                  # keep source cadence (30 fps master)
CRF = "18"
PRESET = "medium"


def ffmpeg_bin() -> str:
    for cand in (shutil.which("ffmpeg"), r"C:\ffmpeg\bin\ffmpeg.exe",
                 __import__("os").environ.get("FFMPEG", "")):
        if cand and (Path(cand).exists() or shutil.which(cand)):
            return cand
    raise SystemExit("ffmpeg not found (PATH, C:\\ffmpeg\\bin, or $FFMPEG)")


def run(args, label):
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


def graph(work: Path, text: str) -> str:
    p = work / "short_clean.ffgraph"
    p.write_text(text, encoding="utf-8")
    return str(p)


def main() -> None:
    if not SRC.exists():
        raise SystemExit(f"missing input: {SRC}")

    FFMPEG = ffmpeg_bin()
    work = OUT.parent
    work.mkdir(parents=True, exist_ok=True)

    # [0:v] split once: one branch becomes the blurred canvas, the other is
    # the sharp centred foreground (no input referenced twice in one graph).
    chain = (
        "[0:v]split[bgA][fgA];"
        # --- background: cover-fill the vertical canvas, blur, darken ---
        f"[bgA]scale={W}:{H}:force_original_aspect_ratio=increase,"
        f"crop={W}:{H},"
        "boxblur=25:5,"
        "eq=brightness=-0.15,"
        f"setsar=1[bg];"
        # --- foreground: sharp original 16:9 at width 1080 ---
        f"[fgA]scale={W}:-1:flags=lanczos,setsar=1[fg];"
        # --- compose: vertically centred, no text, ever ---
        "[bg][fg]overlay=0:(H-h)/2,format=yuv420p,setsar=1[v]"
    )

    args = [FFMPEG, "-y", "-i", SRC,
            "-filter_complex_script", graph(work, chain),
            "-map", "[v]", "-map", "0:a?",
            "-c:v", "libx264", "-crf", CRF, "-preset", PRESET,
            "-pix_fmt", "yuv420p",
            "-c:a", "copy",                 # master audio, bit-for-bit
            "-movflags", "+faststart", str(OUT)]
    if FPS:
        args += ["-r", str(FPS)]
    run(args, f"vertical short -> {OUT.name}")

    print(f"  saved {OUT.name}  {OUT.stat().st_size // 1024} KB")


if __name__ == "__main__":
    main()

