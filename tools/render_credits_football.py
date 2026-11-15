"""Render the M8 credits background football match standalone to MP4 (or PNGs)."""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import random
import shutil
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


def _find_ffmpeg():
    exe = shutil.which("ffmpeg")
    if exe:
        return exe
    try:
        import imageio_ffmpeg

        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        return None


class _FrameSink:
    def __init__(self, out_path: Path, width: int, height: int, fps: int):
        self.out_path = out_path
        self.width = width
        self.height = height
        self.fps = fps
        self.kind = None
        self._proc = None
        self._writer = None
        self._idx = 0
        self._np = None
        self._open()

    def _open(self):
        self.out_path.parent.mkdir(parents=True, exist_ok=True)
        ffmpeg = _find_ffmpeg()
        if ffmpeg:
            cmd = [
                ffmpeg,
                "-y",
                "-loglevel", "error",
                "-f", "rawvideo",
                "-vcodec", "rawvideo",
                "-pix_fmt", "rgb24",
                "-s", f"{self.width}x{self.height}",
                "-r", str(self.fps),
                "-i", "-",
                "-an",
                "-c:v", "libx264",
                "-preset", "fast",
                "-crf", "18",
                "-pix_fmt", "yuv420p",
                "-movflags", "+faststart",
                str(self.out_path),
            ]
            self._proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
            self.kind = "ffmpeg"
            return

        try:
            import imageio.v2 as imageio
            import numpy as np

            self._np = np
            self._writer = imageio.get_writer(str(self.out_path), fps=self.fps)
            self.kind = "imageio"
            return
        except Exception:
            pass

        try:
            import cv2
            import numpy as np

            self._np = np
            fourcc = cv2.VideoWriter_fourcc(*"mp4v")
            writer = cv2.VideoWriter(str(self.out_path), fourcc, float(self.fps), (self.width, self.height))
            if writer.isOpened():
                self._writer = (writer, cv2)
                self.kind = "cv2"
                return
            writer.release()
        except Exception:
            pass

        self.frames_dir = self.out_path.with_suffix("")
        self.frames_dir.mkdir(parents=True, exist_ok=True)
        self.kind = "png"

    def write(self, surf, to_rgb):
        if self.kind == "ffmpeg":
            self._proc.stdin.write(to_rgb(surf, "RGB"))
        elif self.kind == "imageio":
            arr = self._np.frombuffer(to_rgb(surf, "RGB"), dtype=self._np.uint8).reshape(
                (self.height, self.width, 3)
            )
            self._writer.append_data(arr)
        elif self.kind == "cv2":
            writer, cv2 = self._writer
            arr = self._np.frombuffer(to_rgb(surf, "RGB"), dtype=self._np.uint8).reshape(
                (self.height, self.width, 3)
            )
            writer.write(cv2.cvtColor(arr, cv2.COLOR_RGB2BGR))
        else:
            import pygame

            pygame.image.save(surf, str(self.frames_dir / f"frame_{self._idx:04d}.png"))
        self._idx += 1

    def close(self):
        if self.kind == "ffmpeg" and self._proc is not None:
            self._proc.stdin.close()
            rc = self._proc.wait()
            if rc != 0:
                raise RuntimeError(f"ffmpeg exited with code {rc}")
        elif self.kind == "imageio" and self._writer is not None:
            self._writer.close()
        elif self.kind == "cv2" and self._writer is not None:
            self._writer[0].release()


def main():
    ap = argparse.ArgumentParser(description="Render standalone M8 credits football match video.")
    ap.add_argument("--seconds", type=float, default=15.0, help="Duration in seconds (default: 15)")
    ap.add_argument("--fps", type=int, default=60, help="Output framerate (default: 60)")
    ap.add_argument("--seed", type=int, default=None, help="RNG seed (default: random)")
    ap.add_argument("--out", default=str(ROOT / "build" / "credits_football.mp4"), help="Output MP4 path")
    ap.add_argument("--software", action="store_true", help="Force software 3D renderer")
    ap.add_argument("--headless", action="store_true", help="Use dummy SDL video driver")
    ap.add_argument("--with-scrim", action="store_true", help="Keep the dark credits scrim overlay")
    args = ap.parse_args()

    os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
    if args.headless:
        os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    if args.software:
        os.environ["ACARISTAN_RENDERER"] = "software"

    import pygame
    from core.config import HEIGHT, WIDTH
    from ui.credits_football import _FootballScene, _FootballSim

    seed = args.seed if args.seed is not None else random.randrange(1, 1_000_000)
    sim = _FootballSim(seed=seed)
    scene = _FootballScene()
    canvas = pygame.Surface((WIDTH, HEIGHT))
    to_rgb = getattr(pygame.image, "tobytes", pygame.image.tostring)

    if not scene._ensure():
        raise SystemExit("Failed to initialize _FootballScene renderer.")
    if not args.with_scrim and scene._scrim is not None:
        scene._scrim.fill((0, 0, 0, 0))

    total_frames = max(1, int(round(args.seconds * args.fps)))
    dt_frame = 1.0 / float(args.fps)
    substeps = max(1, int(round(dt_frame * 60.0)))
    sub_dt = dt_frame / float(substeps)

    out_path = Path(args.out)
    sink = _FrameSink(out_path, WIDTH, HEIGHT, args.fps)
    t0 = time.perf_counter()
    print(
        f"Rendering {total_frames} frames ({args.seconds:.1f}s @ {args.fps}fps, "
        f"seed={seed}, sink={sink.kind})..."
    )

    try:
        for frame in range(total_frames):
            pygame.event.pump()
            for _ in range(substeps):
                sim.step(sub_dt)
            if not scene.draw(canvas, sim):
                raise RuntimeError(f"scene.draw returned False on frame {frame}")
            sink.write(canvas, to_rgb)
            if (frame + 1) % args.fps == 0 or frame + 1 == total_frames:
                print(f"  {frame + 1}/{total_frames} (kicks={sim.kick_count}, goals={sim.goal_count})")
    finally:
        sink.close()
        if scene._r is not None and hasattr(scene._r, "release"):
            scene._r.release()
        pygame.quit()

    elapsed = time.perf_counter() - t0
    dest = sink.frames_dir if sink.kind == "png" else out_path
    print(f"Done in {elapsed:.2f}s -> {dest}")


if __name__ == "__main__":
    main()
