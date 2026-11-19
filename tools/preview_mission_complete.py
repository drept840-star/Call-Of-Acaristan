"""Render/test every mission-complete case dossier; --show opens a save-free gallery.

python tools/preview_mission_complete.py
python tools/preview_mission_complete.py --show
Gallery: 1-8 or arrows to select; Esc closes.
The gallery uses labelled sample run data, never loads/writes a player save.
"""
import argparse
import copy
import os
from pathlib import Path
import sys
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
os.chdir(ROOT)
sys.path.insert(0, str(ROOT / "src"))
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--show", action="store_true")
args = parser.parse_args()
if not args.show:
    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame
from core import config
from core.state import STATE
from engine.core import pin_wall, unpin_wall
from ui import mission_complete as complete

OUT = ROOT / "shots" / "mission_complete"
OUT.mkdir(parents=True, exist_ok=True)
CUTS = ROOT / "shots" / "mission_complete_3d"
CUTS.mkdir(parents=True, exist_ok=True)
KEYS = ["MISSION" + str(i) for i in range(1, 9)]

REPORT = {"kills": 12, "shots_fired": 45, "shots_hit": 27, "accuracy": 60,
          "time_str": "03:05", "civilians_helped": 2, "rations_used": 1,
          "intel_found": True, "stealth_clean": True, "score": 96, "rank": "S"}


def sample(key, route="revenge"):
    return SimpleNamespace(
        active_mission=key, m8_route=route,
        notebook_collected=True,
        mission2_evidence=[{"done": True}, {"done": False}, {"done": True}],
        mission3_evidence_uploaded=True,
        m4_tone=(1, "the_people"), m4_broadcast_held=True,
        m5_guard_kills=3,
        m7_preps=("tractor", "shed"),
    )


def render(key, route="revenge", elapsed=2400):
    state = sample(key, route)
    before = copy.deepcopy(vars(state))
    complete.enter()
    complete.draw(config.screen, state, REPORT, elapsed, 185000, (-100, -100),
                 key not in ("MISSION8",))
    assert vars(state) == before, "render mutated run state"
    return config.screen.copy()


def checks():
    assert set(complete.PROFILES) == set(KEYS) | {"MISSION0"}
    images = []
    for key in KEYS:
        image = render(key)
        pygame.image.save(image, str(OUT / (key.lower() + ".png")))
        images.append(pygame.image.tobytes(image, "RGB"))
        nxt = key != "MISSION8"
        first = complete.button_specs(sample(key), nxt)[0][0]
        assert first == "menu", key
        # Buttons only become hittable once the entrance fade finishes.
        complete.enter()
        click = pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1)
        hit = (760, config.HEIGHT - 40)
        assert complete.handle_event(click, hit[0], hit[1], sample(key), 17, nxt) is None
        assert complete.handle_event(click, hit[0], hit[1], sample(key), 18, nxt) == (
            "continue" if nxt else "menu")
    assert len(set(images)) == len(KEYS), "mission dossiers not distinct"
    # No arcade columns anywhere.
    for key in KEYS:
        labels = [label for label, _v in complete.ledger_rows(sample(key), REPORT, key)]
        assert "RANK" not in labels and "SCORE" not in labels, key
    # Mission 8 splits on the route the M7 radio choice set.
    pygame.image.save(render("MISSION8", "duty"), str(OUT / "mission8_duty.png"))
    assert "Interim President Vasile" in complete.debrief_copy(sample("MISSION8", "duty"), "MISSION8")[0]
    assert "train departed" in complete.debrief_copy(sample("MISSION8"), "MISSION8")[0]
    # Unknown missions fall back to the neutral dossier.
    render("MISSION9")
    assert complete.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_ESCAPE),
                                 0, 0, sample("MISSION4"), 100, True) == "menu"
    # Labels come from the string table, not markers.
    assert complete.button_specs(sample("MISSION4"), True)[1][1] == "NEXT: MISSION 05"
    assert complete.button_specs(sample("MISSION8"), False)[0][1] == "RETURN TO MENU"
    # Cached sheet: two frames in a row build once and blit only.
    render("MISSION3")
    first_sheet = complete._sheet_cache["surf"]
    complete.draw(config.screen, sample("MISSION3"), REPORT, 2400, 185000,
                  (-100, -100), True)
    assert complete._sheet_cache["surf"] is first_sheet, "sheet rebuilt every frame"
    # Gallery rail: the shipped handler steps the case, MAIN MENU closes it.
    click = pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1)
    assert _gallery_step(click, 0, 100, mouse=(760, 660)) == (1, True), "NEXT click ignored"
    assert _gallery_step(click, 3, 100, mouse=(600, 660)) == (3, False), "MAIN MENU click ignored"
    assert _gallery_step(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_ESCAPE), 2, 100) == (2, False)
    assert _gallery_step(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_RIGHT), 7, 100) == (0, True)
    diorama_checks()
    print("MISSION COMPLETE CHECK: OK (9 dossiers, split M8 route, neutral fallback, "
          "input gate, single cached blit, 10 live 3D cuts)")
    print("Preview PNGs:", OUT)


def diorama_checks():
    """Direct sweep of the exhibit viewport (ui/mission_complete_3d.py)."""
    from ui import mission_complete_3d as mc3d

    assert mc3d.enabled(), "3D exhibit viewport is disabled"
    cuts = [("MISSION0", None)] + [("MISSION" + str(i), None) for i in range(1, 8)]
    cuts += [("MISSION8", "duty"), ("MISSION8", "revenge")]
    seen = set()
    for key, route in cuts:
        surf = mc3d.render(key, route, 4000)
        assert surf is not None, "3D cut failed to render: %s %s" % (key, route)
        assert surf.get_size() == (mc3d.OUT_W, mc3d.OUT_H), (key, route)
        data = pygame.image.tobytes(surf, "RGB")
        assert data not in seen, "duplicate 3D cut: %s %s" % (key, route)
        seen.add(data)
        pygame.image.save(surf, str(CUTS / ((key if route is None else key + "_" + route).lower()
                                            + ".png")))
    # Reduced motion hands back a still instead of stepping the drift.
    mc3d.render("MISSION4", None, 4000)
    still = mc3d.render("MISSION4", None, 9000, reduced_motion=True)
    assert still is not None, "reduced-motion frame missing"
    # ACA_MC_2D=1 is the shipped opt-out: the dossier falls back to its plate.
    old = os.environ.get("ACA_MC_2D")
    os.environ["ACA_MC_2D"] = "1"
    try:
        assert not mc3d.enabled(), "ACA_MC_2D=1 did not disable the viewport"
        assert mc3d.render("MISSION4", None, 4000) is None, "opt-out still rendered"
    finally:
        if old is None:
            os.environ.pop("ACA_MC_2D", None)
        else:
            os.environ["ACA_MC_2D"] = old
    print("Exhibit 3D cuts:", CUTS)


def _gallery_step(event, index, tick, mouse=None):
    """Preview-only event step: arrows/1-8 select, the real rail buttons step or close."""
    if event.type == pygame.QUIT:
        return index, False
    if event.type == pygame.KEYDOWN:
        if event.key == pygame.K_ESCAPE:
            return index, False
        if pygame.K_1 <= event.key <= pygame.K_8:
            return event.key - pygame.K_1, True
        if event.key in (pygame.K_RIGHT, pygame.K_SPACE):
            return (index + 1) % len(KEYS), True
        if event.key == pygame.K_LEFT:
            return (index - 1) % len(KEYS), True
        return index, True
    # Mouse goes through the shipped rail handler, not a preview copy of it.
    if mouse is None:
        mouse = config.get_scaled_mouse()
    frames = 2400 + int(round(tick / 16.667))
    action = complete.handle_event(event, mouse[0], mouse[1], sample(KEYS[index]),
                                   frames, KEYS[index] != "MISSION8")
    if action == "continue":
        return (index + 1) % len(KEYS), True
    if action == "menu":
        return index, False
    return index, True


def gallery():
    pygame.display.set_mode((config.WIDTH, config.HEIGHT))
    config.reset_present_cache()
    pygame.display.set_caption("Mission Complete Gallery | SAMPLE DATA | 1-8 / arrows / click | Esc: close")
    index, running = 0, True
    clock = pygame.time.Clock()
    tick = 0
    pin_wall(ms=lambda: tick)
    try:
        while running:
            tick += clock.tick(60)
            for event in pygame.event.get():
                index, running = _gallery_step(event, index, tick)
                if not running:
                    break
            if not running:
                break
            frames = 2400 + int(round(tick / 16.667))
            complete.draw(config.screen, sample(KEYS[index]), REPORT, frames,
                          185000, config.get_scaled_mouse(), KEYS[index] != "MISSION8")
            complete._draw_text(config.screen, "PREVIEW / SAMPLE RUN DATA / 1-8 SELECT",
                                48, 604, 10, (152, 148, 136), "bold")
            config.present(config.screen)
            pygame.display.flip()
    finally:
        unpin_wall()
        pygame.quit()


if __name__ == "__main__":
    if args.show:
        gallery()
    else:
        checks()
        pygame.quit()
