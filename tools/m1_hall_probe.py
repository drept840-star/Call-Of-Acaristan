"""Diagnostic probe: can the player actually cross commander K's hall (rows 21-25)?

Simulates the canonical quiet route with the CURRENT tuning:
  stockroom door (8,20) -> desk (13,22) -> gate console (13,25)
and records every stealth event per guard: first SUSPICIOUS, SEARCHING/radio call,
alarm latch. Run from the repo root:

    python tools/m1_hall_probe.py
"""
import math
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
os.environ.setdefault("ACA_FREEZE", "1")     # deterministic lamps/no flicker

import pygame  # noqa: E402

from core import game_core as gc  # noqa: E402
from core.state import STATE  # noqa: E402
from core.config import TILE_SIZE  # noqa: E402
from missions.m1 import update as m1u  # noqa: E402
from missions.m1 import stealth as S  # noqa: E402
from missions.m1.map import _tc  # noqa: E402


class EmptyKeys:
    def get_pressed(self):
        return []

    def __getitem__(self, _k):
        return 0


def run(label, waypoints, step_px=2.0):
    gc.start_mission(preserve_timer=True)
    STATE.dt = 1 / 60
    STATE.bullets.clear()
    if STATE.NOTEBOOK_POS is None:
        m1u._init_mission_specials()
    p = STATE.player

    guards = [(e, "K" if getattr(e, "is_commander", False) else "g%d" % i)
              for i, e in enumerate(STATE.enemies)]
    print("\n=== %s ===" % label)
    print("  guards: %d total; hall (rows 21-25): %s" % (
        len(guards),
        [w for e, w in guards
         if 21 * TILE_SIZE - 32 <= e.rect.centery <= 25 * TILE_SIZE + 32]))

    events = []
    seen = set()
    alarm_at = None
    frame = 0

    def note(tag, who, extra=""):
        events.append((frame / 60.0, tag, who, extra))

    for (x0, y0), (x1, y1) in zip(waypoints, waypoints[1:]):
        if alarm_at is not None:
            break
        dist = math.hypot(x1 - x0, y1 - y0)
        n = max(1, int(dist / step_px))
        for k in range(1, n + 1):
            t = k / n
            p.rect.center = (int(x0 + (x1 - x0) * t), int(y0 + (y1 - y0) * t))
            m1u.game_update(EmptyKeys())
            frame += 1
            if STATE.firefight_triggered and alarm_at is None:
                alarm_at = frame / 60.0
            for e, who in guards:
                m = S.mind_of(e)
                if m is None:
                    continue
                if (e.uid, "sus") not in seen and m["s"] >= S.SUSPICIOUS_AT:
                    seen.add((e.uid, "sus"))
                    note("SUSPICIOUS", who, "s=%.2f pos=(%d,%d) row=%.1f" % (
                        m["s"], e.rect.centerx, e.rect.centery,
                        e.rect.centery / TILE_SIZE))
                if (e.uid, "call") not in seen and m["call_t"] > 0:
                    seen.add((e.uid, "call"))
                    note("RADIO-CALL", who, "pos row=%.1f" % (e.rect.centery / TILE_SIZE))

    if alarm_at is not None:
        print("  ALARM LATCHED at t=%.2f s (%d frames)" % (alarm_at, frame))
    else:
        print("  %.1f s walking, alarm did NOT latch" % (frame / 60.0))
    if events:
        for t, tag, who, extra in events:
            print("  t=%5.2f  %-10s %s  %s" % (t, tag, who, extra))
    else:
        print("  no guard ever got suspicious")
    return alarm_at


def main():
    pygame.init()
    door = _tc(8, 20)
    desk = _tc(13, 22)
    console = _tc(13, 25)

    # route A: straight through the open hall
    run("A: door(8,20) -> desk(13,22) -> console(13,25), straight",
        [door, desk, console])

    # route B: hug the west wall down, then east along row 24
    run("B: door -> west wall col 2 -> row 24 east -> console",
        [door, _tc(2, 22), _tc(2, 24), _tc(13, 25)])

    # route C: north edge corridor (row 21) east, then south to the console
    run("C: door -> row 21 east to col 13 -> console",
        [door, _tc(13, 21), console])


if __name__ == "__main__":
    main()
