"""Render/test all failure terminals; --show opens a safe, save-free gallery.

python tools/preview_mission_failed.py
python tools/preview_mission_failed.py --show
Gallery: 1-5 or arrows to select; M toggles Maru-loss variant; Esc closes.
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
import ui.system as ui
from ui import mission_failed as failed

OUT = ROOT / "shots" / "mission_failed"
OUT.mkdir(parents=True, exist_ok=True)
KEYS = list(failed.PROFILES)


def sample(key, maru=False):
    return SimpleNamespace(active_mission=key, mission_start_time=1000,
                           mission_end_time=185000, shots_fired=45, shots_hit=27,
                           hostiles_killed=12, mission3_weapon="chair_leg",
                           mission2_evidence=[{"done": True}, {"done": False}, {"done": True}],
                           m4_jammer_installed=True, m5_maru_found=True,
                           m5_maru_dead=maru, mission5_tunnel_checkpoint_reached=True)


def render(key, maru=False, elapsed=2400):
    state = sample(key, maru)
    before = copy.deepcopy(vars(state))
    failed.draw(config.screen, state, ui.death_buttons, elapsed, 185000, (-100, -100))
    assert vars(state) == before, "render mutated run state"
    return config.screen.copy()


def checks():
    from core import artpack
    # The default tier must use the bespoke procedural frames, not silently fall back.
    for kind in ("notebook", "route", "cells", "tower", "press", "maru_lost"):
        frame = artpack.frame("spr_mission_failed", kind)
        assert frame is not None and frame.get_size() == (320, 250), kind
    assert failed._illustrated_art(config.screen, sample("MISSION5", True), "press")
    # Explicit low-art settings still retain the old renderer safely.
    old_tier = os.environ.get("ACA_ART")
    try:
        for tier in ("legacy", "off"):
            os.environ["ACA_ART"] = tier
            assert not failed._illustrated_art(config.screen, sample("MISSION1"), "notebook")
            render("MISSION1")
    finally:
        if old_tier is None:
            os.environ.pop("ACA_ART", None)
        else:
            os.environ["ACA_ART"] = old_tier
    images = []
    for key in KEYS:
        image = render(key)
        path = OUT / (key.lower() + ".png")
        pygame.image.save(image, str(path))
        images.append(pygame.image.tobytes(image, "RGB"))
        for button in ui.death_buttons:
            assert config.screen.get_rect().contains(button.rect)
            event = pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=button.rect.center)
            button.check_hover(button.rect.center)
            assert button.is_clicked(event, button.rect.center)
        render(key, elapsed=1199)
        assert all(b.rect.top > config.HEIGHT for b in ui.death_buttons)
        render(key, elapsed=1200)
        assert all(b.rect.top == config.HEIGHT - 78 for b in ui.death_buttons)
    assert len(set(images)) == 5, "mission screens not distinct"
    pygame.image.save(render("MISSION5", True), str(OUT / "mission5_maru_lost.png"))
    for elapsed in [0, 250, 1199, 1200]:
        pygame.image.save(render("MISSION1", elapsed=elapsed), str(OUT / f"reveal_{elapsed}.png"))
    assert failed.failure_copy(sample("MISSION5", True))[0] == "MARU DID NOT MAKE IT OUT"
    for key, flag, label in [
        ("MISSION2", "mission2_checkpoint_reached", "ROUTE 12 CHECKPOINT"),
        ("MISSION3", "mission3_broadcast_checkpoint_reached", "BROADCAST WING"),
        ("MISSION4", "mission4_tower_checkpoint_reached", "TRANSMITTER TOWER"),
        ("MISSION5", "mission5_tunnel_checkpoint_reached", "TUNNEL"),
    ]:
        s = sample(key)
        setattr(s, flag, True)
        assert failed.checkpoint_label(s) == label
    assert failed.stat_rows(sample("MISSION2"), 185000)[3] == ("EVIDENCE FOUND", "2/3")
    # Verify actual ui.system dispatch and transition resets, not only the painter.
    original = STATE.active_mission if hasattr(STATE, "active_mission") else None
    try:
        pin_wall(ms=10000)
        for key in KEYS:
            STATE.active_mission = key
            ui.reset_death_animation()
            ui._death_animation_start = 7600
            ui.draw_death_screen()
        ui.reset_death_animation()
        assert all(b.rect.size == (b.width, b.height) for b in ui.death_buttons)
        STATE.active_mission = "ARENA"
        ui._death_animation_start = 7600
        ui.draw_death_screen()
        ui.reset_death_animation()
        ui._death_animation_start = 7600
        ui.draw_black_ledger_death_buttons()
    finally:
        STATE.active_mission = original
        ui.reset_death_animation()
        unpin_wall()
    print("MISSION FAILED CHECK: OK (5 missions, Maru variant, reveal/input gates, dispatch, neutral + Ledger)")
    print("Preview PNGs:", OUT)


def gallery():
    pygame.display.set_caption("Mission Failed Gallery | SAMPLE DATA | 1-5 / arrows | M: Maru loss | Esc: close")
    index, maru, running = 0, False, True
    clock = pygame.time.Clock()
    tick = 0
    pin_wall(ms=lambda: tick)
    try:
        while running:
            tick += clock.tick(60)
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                elif event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE:
                        running = False
                    elif pygame.K_1 <= event.key <= pygame.K_5:
                        index = event.key - pygame.K_1
                    elif event.key in (pygame.K_RIGHT, pygame.K_SPACE):
                        index = (index+1) % 5
                    elif event.key == pygame.K_LEFT:
                        index = (index-1) % 5
                    elif event.key == pygame.K_m:
                        maru = not maru
            failed.draw(config.screen, sample(KEYS[index], maru), ui.death_buttons,
                        2400 + tick, 185000, config.get_scaled_mouse())
            # Gallery controls are navigation only, never restart real gameplay.
            failed._text(config.screen, "PREVIEW / SAMPLE RUN DATA / 1-5 SELECT / M MARU", 48, 601, 12, failed.MUTED)
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
