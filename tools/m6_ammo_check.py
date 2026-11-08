"""Focused headless regression for the M6 K-9 supply ladder.

Run from the repo root: python tools/m6_ammo_check.py
"""
import os
import sys
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import pygame

pygame.init()
from core.state import STATE
from missions.m6 import flow, systems, world, yard3d, train3d

with patch.object(flow, "_save_progress"), patch.object(train3d, "begin", return_value=True):
    flow.start_m6()
    assert (STATE.k9_ammo_in_mag, STATE.k9_spare_mags) == (30, 4)

    # Normal reloads consume whole spare mags, not just a counter in the HUD.
    for _ in range(4):
        STATE.k9_ammo_in_mag = 0
        STATE.is_reloading, STATE.reload_timer = True, 1
        systems._update_weapon_timers()
    assert STATE.k9_spare_mags == 0
    STATE.k9_ammo_in_mag = 7
    flow._enter_noman()
    assert (STATE.k9_ammo_in_mag, STATE.k9_spare_mags) == (7, 3)

    # Every second kill drops loot; it must be collected, respects the cap,
    # and neither resets nor refills an already-loaded magazine.
    STATE.k9_spare_mags = 2
    for enemy in STATE.enemies[:3]:
        systems._kill_enemy(enemy)
    assert len(STATE.pickups) == 1 and STATE.pickups[0][2] == "k9mag"
    pickup = STATE.pickups[0]
    systems._update_pickups()
    assert STATE.k9_spare_mags == 2  # not a map-wide instant grant
    STATE.player.rect.center = (pickup[0], pickup[1])
    systems._update_pickups()
    assert (STATE.k9_ammo_in_mag, STATE.k9_spare_mags) == (7, 3)
    assert not STATE.pickups
    STATE.pickups.append([STATE.player.rect.centerx, STATE.player.rect.centery, "k9mag"])
    STATE.k9_spare_mags = systems.K9_SPARE_CAP
    systems._update_pickups()
    assert len(STATE.pickups) == 1 and STATE.k9_spare_mags == systems.K9_SPARE_CAP

    flow._enter_rail()
    assert STATE.k9_spare_mags == systems.K9_SPARE_CAP  # carryover above the stage floor
    STATE.k9_spare_mags = 0
    flow._enter_train()
    assert (STATE.k9_ammo_in_mag, STATE.k9_spare_mags) == (7, 4)
    flow.start_mission6_train_checkpoint()
    assert (STATE.k9_ammo_in_mag, STATE.k9_spare_mags) == (30, 4)
    STATE.k9_ammo_in_mag = 0
    train = train3d.scene()
    train._begin_reload()
    assert train.reloading
    train._update_reload(3.0)
    assert (STATE.k9_ammo_in_mag, STATE.k9_spare_mags) == (30, 3)

scene = yard3d.YardScene()
assert (scene.mag, scene.reserve) == (30, 150)
scene.reserve = 120
x, y, z = scene.pos
body = {"alive": False, "pos": (x + 2.0, y, z), "mags": 2}
scene.guards = [body]
scene._loot()
assert (scene.reserve, body["mags"]) == (150, 1)
scene.mag = 0
scene._begin_reload()
assert scene.reloading > 0
assert yard3d.RESERVE_CAP == 150

pygame.quit()
print("M6 AMMO CHECK: OK")
