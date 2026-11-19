"""Gameplay sweep regressions (2026-11-19): loot, revive range, checkpoint ammo.

Each test fails on the code before the fix:
- M8 trap: a checkpoint retry reset both guns to starting ammo (``_setup``
  overwrote the saved mag/reserve with the defaults).
- M8 trap and mansion: walking over a body with both reserves full consumed
  its ammo for nothing.
- M8 mansion: a downed ally under the gallery offered "Help ally up" to the
  player on the landing above, and that prompt outranked the study door.
- M1-M5: full-HP bandages, full-pouch mags and molotovs were eaten on touch.

Run: python -m unittest tests.unit.test_gameplay_sweep -v
"""
import unittest

from tests.unit import _helpers  # noqa: F401 (src path and headless SDL)

from core.state import STATE
from missions.m8.duty import mansion3d as M3
from missions.m8.duty import mansion_set as MS
from missions.m8.revenge import trap3d as TR


class _Rect:
    def __init__(self, x, y):
        self.centerx, self.centery = x, y


class _Player:
    def __init__(self, hp=100, max_hp=100):
        self.rect = _Rect(100, 100)
        self.hp, self.max_hp = hp, max_hp


class TrapSweepTests(unittest.TestCase):
    def setUp(self):
        STATE.dt = 1.0 / 60.0
        STATE.m8_trap_cp = 0
        self.sc = TR.TrapScene()
        self.sc.begin()

    def test_checkpoint_retry_keeps_both_guns_ammo(self):
        sc = self.sc
        sc.weapon = "shotgun"
        sc._sync_weapon_attrs()
        sc.mag, sc.reserve = 3, 30
        sc.wpns["rifle"] = [12, 140]
        sc.cp_state = sc._cp_snapshot()
        sc._setup(1)
        self.assertEqual(sc.wpns["shotgun"], [3, 30])
        self.assertEqual(sc.wpns["rifle"], [12, 140])
        self.assertEqual((sc.mag, sc.reserve), (3, 30))

    def test_checkpoint_retry_floors_reserve_at_the_start_value(self):
        sc = self.sc
        sc.wpns["rifle"] = [30, 10]
        sc.cp_state = sc._cp_snapshot()
        sc._setup(1)
        self.assertEqual(sc.wpns["rifle"][1], TR.WPN_SPECS["rifle"]["reserve0"])

    def test_full_reserves_leave_the_body_its_ammo(self):
        sc = self.sc
        sc.brain.enemies = []
        e = sc.brain.add("rifle", sc.px + 1.0, sc.pz, [], 0.0, 1)
        e["alive"] = False
        e["mags"] = 1
        for k, sp in TR.WPN_SPECS.items():
            sc.wpns[k][1] = sp["cap"]
        sc._sync_weapon_attrs()
        sc._loot()
        self.assertEqual(e["mags"], 1, "a full player emptied the body")
        sc.wpns["rifle"][1] -= 20
        sc._sync_weapon_attrs()
        sc._loot()
        self.assertEqual(e["mags"], 0)
        self.assertEqual(sc.wpns["rifle"][1], TR.WPN_SPECS["rifle"]["cap"] - 5)

    def test_kiosk_gate_moves_bodi_up_like_a_wave_clear(self):
        sc = self.sc
        b = sc.brain.bodi
        b["state"] = "up"
        b["goal"] = TR.B.BODI_POSTS.get(1)
        sc._open_gate()
        self.assertEqual(b["goal"], TR.B.BODI_POSTS.get(2), "Bodi stayed a post behind")


class MansionSweepTests(unittest.TestCase):
    def setUp(self):
        STATE.dt = 1.0 / 60.0
        self.sc = M3.MansionScene()
        self.sc._setup(2)

    def test_full_reserves_leave_the_body_its_ammo(self):
        sc = self.sc
        sc.brain.enemies = []
        e = sc.brain.add("rifle", sc.px + 1.0, sc.pz, [], 0.0, 4)
        e["alive"] = False
        e["y"] = sc.py
        for k, sp in M3.WPN_SPECS.items():
            sc.wpns[k][1] = sp["cap"]
        sc._sync_weapon_attrs()
        sc._loot()
        self.assertEqual(e["mags"], 1, "a full player emptied the body")

    def test_downed_ally_on_another_floor_offers_no_revive(self):
        sc = self.sc
        b = sc.brain.bodi
        b["state"] = "down"
        b["x"], b["z"], b["y"] = sc.px + 1.0, sc.pz, MS.GF
        sc.py = MS.FF
        self.assertIsNone(sc.brain.near_revive())
        sc.py = MS.GF
        self.assertEqual(sc.brain.near_revive(), "bodi")


class PickupSweepTests(unittest.TestCase):
    def setUp(self):
        self._saved = {k: getattr(STATE, k, None) for k in
                       ("player", "player_dead", "pickups", "spare_mags", "k9_spare_mags",
                        "floating_texts", "player_bottles", "mission3_sidearm_acquired")}
        STATE.player = _Player()
        STATE.player_dead = False
        STATE.floating_texts = []

    def tearDown(self):
        for k, v in self._saved.items():
            setattr(STATE, k, v)

    def _drop(self, kind):
        pu = [100, 100, kind]
        STATE.pickups = [pu]
        return pu

    def test_m2_full_player_leaves_bandage_and_mag(self):
        from missions.m2 import update as m2u
        STATE.spare_mags = 5
        for kind in ("bandage", "mag"):
            self._drop(kind)
            m2u._update_pickups()
            self.assertEqual(len(STATE.pickups), 1, kind)

    def test_m3_full_player_leaves_bandage_and_sidearm(self):
        from missions.m3 import systems as m3s
        STATE.spare_mags = 5
        STATE.mission3_sidearm_acquired = True
        for kind in ("bandage", "sidearm"):
            self._drop(kind)
            m3s._update_m3_pickups()
            self.assertEqual(len(STATE.pickups), 1, kind)

    def test_m4_m5_full_pouches_leave_the_k9_mag(self):
        from missions.m4 import systems as m4s
        from missions.m4.meta import M4_SPARE_CAP
        from missions.m5 import systems as m5s
        for upd, cap in ((m4s._update_m4_pickups, M4_SPARE_CAP), (m5s._update_m5_pickups, 5)):
            STATE.spare_mags = STATE.k9_spare_mags = cap
            self._drop("k9mag")
            upd()
            self.assertEqual(len(STATE.pickups), 1, upd.__module__)


if __name__ == "__main__":
    unittest.main()
