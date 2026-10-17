"""t7_probe.py - before/after shots + draw-time probe for Polish T7.

    python tools/sprites/t7_probe.py            # sprite tier  -> after.png
    python tools/sprites/t7_probe.py --no-t7    # T7 sheets off -> before.png
    ACA_ART=legacy python tools/sprites/t7_probe.py   # whole art tier off -> legacy.png
    ... --frames 120  --no-shots  --json out.json

Shots go to shots/polish_pass/07/<family>/{before,after}.png with the same
camera both runs (ACA_FREEZE=1 pins time-driven terms). The probe times
gc.game_draw over N frames per scene with the dummy video driver, so the
numbers are CPU draw cost (ms/frame -> FPS ceiling), not vsynced FPS.
"""
import json
import os
import sys
import time
from pathlib import Path

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
os.environ["ACA_FREEZE"] = "1"
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

import pygame  # noqa: E402

from core import config  # noqa: E402
from core import game_core as gc  # noqa: E402
from core.state import STATE  # noqa: E402

from core import artpack  # noqa: E402

T = config.TILE_SIZE
LEGACY = os.environ.get("ACA_ART", "") in ("legacy", "off")
NO_T7 = "--no-t7" in sys.argv
if NO_T7:
    # Pre-T7 look: rest of the art tier on, T7 sheets reported missing so
    # every T7 call site takes its procedural fallback.
    artpack.frame = lambda *_a, **_k: None
MODE = "legacy" if LEGACY else ("pre_t7" if NO_T7 else "t7")
SHOT = {"legacy": "legacy.png", "pre_t7": "before.png", "t7": "after.png"}[MODE]


def _cam(tx, ty):
    STATE.player.rect.center = (int(tx * T), int(ty * T))
    return int(tx * T - config.WIDTH // 2), int(ty * T - config.HEIGHT // 2)


def _m2_road():
    gc.start_mission2(preserve_timer=True)
    return _cam(46, 33)                     # tanker + IPA truck + cars


def _m2_props():
    gc.start_mission2(preserve_timer=True)
    return _cam(13, 70)                     # spawn-road flares / cones


def _m2_blast():
    from missions.m2 import sniper
    gc.start_mission2(preserve_timer=True)
    sniper._explode_tanker()
    STATE.mission2_tanker_blast_timer = 520  # settled aftermath
    STATE.mission2_stage = "evidence"        # past the blackout overlay
    return _cam(46, 37)


def _m3_archives():
    from missions import m3
    m3.start_mission3_archives_checkpoint(preserve_timer=True)
    STATE.player.rect.center = (12 * T, 27 * T)
    return m3._clamp_m3_camera(12 * T - config.WIDTH // 2, 27 * T - config.HEIGHT // 2)


def _m4_tower():
    gc.start_mission4_tower_checkpoint(preserve_timer=True)
    p = STATE.player.rect.center
    return p[0] - config.WIDTH // 2, p[1] - config.HEIGHT // 2


SCENES = (("m2_road", _m2_road), ("m2_props", _m2_props), ("m2_blast", _m2_blast),
          ("m3_archives", _m3_archives), ("m4_tower", _m4_tower))


def _lineup(fam):
    """Isolated family shot: the real m2 draw entry points on flat asphalt,
    so before/after differ only by the T7 sprite path (no HUD / grading)."""
    from missions.m2 import draw as d
    surf = pygame.Surface((config.WIDTH, config.HEIGHT))
    surf.fill((58, 56, 52))
    gc.start_mission2(preserve_timer=True)
    STATE.mission2_tanker_blast_timer = 520
    if fam == "vehicles":
        sizes = ((118, 44), (126, 48), (110, 42), (112, 44), (116, 44), (126, 46), (112, 42))
        for i, (w, h) in enumerate(sizes):
            x = 16 + i * 140
            d._draw_vehicle(surf, pygame.Rect(x, 40, w, h), "car", 0, 0, {})
            d._draw_vehicle(surf, pygame.Rect(x, 150, w, h), "burned", 0, 0, {})
        d._draw_vehicle(surf, pygame.Rect(40, 270, 160, 54), "ipa_truck", 0, 0, {})
        d._draw_vehicle(surf, pygame.Rect(260, 270, 160, 54), "ipa_truck", 0, 0,
                        {"blast_charred": True})
        STATE.mission2_tanker_inspected = True
        t = STATE.mission2_tanker_rect
        d._draw_tanker(surf, t.x - 480, t.y - 260)
    elif fam == "props":
        kinds = ("cone", "barrel", "sign", "broken_camera", "spark_box", "puddle", "soot", "flare")
        for i, k in enumerate(kinds):
            x = 70 + i * 118
            d._draw_story_prop(surf, {"kind": k, "pos": (x, 120), "age": 5, "life": -1}, 0, 0)
            d._draw_story_prop(surf, {"kind": k, "pos": (x, 300), "age": 5, "life": -1,
                                      "charred": True, "scorched": True}, 0, 0)
        for i in range(4):
            d._draw_upload_computer(surf, 140 + i * 220, 520, 0, 0)
    else:
        import random
        random.seed(7)                       # same debris / spot fires both runs
        _m2_blast()
        t = STATE.mission2_tanker_rect
        d._draw_tanker_blast_fx(surf, t.centerx - config.WIDTH // 2, t.centery - config.HEIGHT // 2)
    return surf


def main():
    # core.config already opened the display; a second set_mode would leave
    # config.screen (imported by name all over src/) pointing at a dead surface.
    frames = int(sys.argv[sys.argv.index("--frames") + 1]) if "--frames" in sys.argv else 120
    shots = "--no-shots" not in sys.argv
    res = {"mode": MODE, "frames": frames, "scenes": {}}
    if shots:
        for fam in ("vehicles", "props", "fx"):
            out = ROOT / "shots" / "polish_pass" / "07" / fam
            out.mkdir(parents=True, exist_ok=True)
            pygame.image.save(_lineup(fam), str(out / SHOT))
    for name, fn in SCENES:
        try:
            fcx, fcy = fn()
        except Exception as exc:  # report and keep probing the other scenes
            print("%-12s SKIP (%s: %s)" % (name, type(exc).__name__, exc))
            continue
        for _ in range(3):                     # warm caches / settle state
            gc.game_draw(fcx, fcy)
        t0 = time.perf_counter()
        for _ in range(frames):
            gc.game_draw(fcx, fcy)
        ms = (time.perf_counter() - t0) * 1000.0 / frames
        res["scenes"][name] = round(ms, 2)
        print("%-12s %6.2f ms/frame  (%5.0f fps ceiling)" % (name, ms, 1000.0 / max(ms, 1e-6)))
    if "--json" in sys.argv:
        Path(sys.argv[sys.argv.index("--json") + 1]).write_text(json.dumps(res, indent=1))
    print("T7 PROBE: OK (%s)" % res["mode"])


if __name__ == "__main__":
    main()
