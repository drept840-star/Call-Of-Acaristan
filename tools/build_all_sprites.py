"""Rebuild every generated art asset in one go (Polish T7).

    python tools/build_all_sprites.py [--preview] [--skip-legacy]

Runs, in order, and stops on the first failure (non-zero exit):
  1. tools/make_art_pack.py        tiles / walls / icons / lights (assets/art)
  2. tools/ae_bake.py --pack m5    Mission 5 sprites (assets/baked/m5)
  3. tools/sprites/vehicles.py     spr_vehicles   (cars, IPA truck, tanker)
  4. tools/sprites/props.py        spr_props_m2   (story props, upload PC)
  5. tools/sprites/fx.py           spr_fx_scorch + spr_fx_m2 (blast aftermath)
  6. tools/sprites/portraits.py    spr_portraits  (radio caller-ID busts, T6b)
  7. tools/sprites/mission_failed.py spr_mission_failed (bespoke procedural failure scenes)

--preview     also write previews/sprites/<family>.png (light + dark, 2x)
--skip-legacy only run the tools/sprites/* family generators (3-7)

Every generator is deterministic (fixed seeds, sorted JSON), so a clean
rebuild produces byte-identical PNG/JSON; the smoke test checks that.
"""
import os
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LEGACY = ("tools/make_art_pack.py", "tools/bake_m5_sprites.py")   # bake_m5_sprites -> ae_bake --pack m5
FAMILIES = ("tools/sprites/vehicles.py", "tools/sprites/props.py", "tools/sprites/fx.py",
            "tools/sprites/portraits.py", "tools/sprites/mission_failed.py")


def _run(rel, extra):
    t0 = time.time()
    env = dict(os.environ, SDL_VIDEODRIVER=os.environ.get("SDL_VIDEODRIVER", "dummy"))
    proc = subprocess.run([sys.executable, os.path.join(ROOT, rel)] + extra, cwd=ROOT, env=env)
    dt = time.time() - t0
    if proc.returncode != 0:
        print("BUILD ALL SPRITES: FAILED in %s (exit %d)" % (rel, proc.returncode))
        sys.exit(proc.returncode or 1)
    print("  ok  %-30s %.1fs" % (rel, dt))


def main():
    preview = ["--preview"] if "--preview" in sys.argv else []
    steps = [] if "--skip-legacy" in sys.argv else [(p, []) for p in LEGACY]
    steps += [(p, preview) for p in FAMILIES]
    for rel, extra in steps:
        _run(rel, extra)
    print("BUILD ALL SPRITES: OK (%d steps)" % len(steps))


if __name__ == "__main__":
    main()
