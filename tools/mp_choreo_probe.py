#!/usr/bin/env python3
"""mp_choreo_probe.py - gate the MP trailer fight headlessly before capturing.

Runs the REAL ScriptDriver from mp_trailer_capture against the REAL ArenaSim
on foundry with no renderer, no sockets and no ffmpeg, and reports the things
the trailer actually depends on. Turns a ~50 s capture into a 2 s loop.

Gates, per seed:
  * first shot inside 2 s of GO          (was 7.5 s)
  * no silent gap over 2.5 s             (was 4.8 s)
  * every seat pulls the trigger, 5+ shots - a fair-looking scoreboard will
    happily hide a seat that never fires, which is exactly what went wrong
  * both teams score
  * neither team goes more than 5.5 s without a kill, or the killfeed stalls

Usage:  python tools/mp_choreo_probe.py
"""
import math
import os
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
os.chdir(ROOT)
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tools"))

import mp_trailer_capture as C                     # noqa: E402
from missions import arena as AR                    # noqa: E402
from net import protocol as P                       # noqa: E402

T = C.SIM_HZ
SEEDS = (20261004, 7, 4242, 99, 31337)
GATE_FIRST_SHOT = 2.0
GATE_MAX_GAP = 2.5
GATE_MIN_SHOTS = 5
GATE_MAX_SCORELULL = 5.5


class StubSession:
    """The handful of ArenaSim.session hooks a local dry-run needs."""

    def __init__(self):
        self.tick = 0
        self.world = None
        self.is_host = True
        self.local_id = 0
        self.inputs = {}

    def consume_input(self, pid):
        return self.inputs.get(pid)

    def send_events(self, tick, events):
        pass

    def broadcast(self):
        pass


def run(seconds=16.0, seed=20261004, verbose=False):
    nav = C.GridNav(AR.ARENAS[C.MAP_NAME])
    sess = StubSession()
    sim = AR.ArenaSim(sess, AR.ARENAS[C.MAP_NAME], map_name=C.MAP_NAME,
                      mode=C.MODE_NAME)

    order = [(0, C.HOST_NAME), (1, "BIRIBEL"), (2, C.FRIEND_NAME),
             (3, "MICUL FUEGO")]
    for pid, nick in order:
        sim.add_player(pid, nick)
    nick_of = {pid: p["nick"] for pid, p in sim.players.items()}

    # The same opening stance phase_combat applies on the real capture.
    for pid, nick in nick_of.items():
        key = C.seat_key(nick)
        post = C.FOUNDRY_POSTS.get(key) if key else None
        if post is None:
            continue
        px, py = C._tc(*post)
        p = sim.players[pid]
        p["x"], p["y"] = float(px), float(py)
        p["dead"] = False
        p["hp"] = AR.MAX_HP
        sim.rules.spawned_at[pid] = sim.tick - AR.SPAWN_PROTECT_TICKS

    scripts = C.foundry_scripts()
    drivers = {}
    for pid, nick in nick_of.items():
        key = C.seat_key(nick)
        spec, restart = scripts[key]
        post = C.FOUNDRY_POSTS.get(key)
        drivers[pid] = C.ScriptDriver(pid, nav, lambda: sim, spec,
                                      random.Random(seed + pid),
                                      restart_at=restart,
                                      home=C._tc(*post) if post else None)

    total = int(seconds * T)
    shots, kills, seen = [], [], set()
    motion = {pid: dict(distance=0.0, minx=sim.players[pid]["x"],
                        maxx=sim.players[pid]["x"], miny=sim.players[pid]["y"],
                        maxy=sim.players[pid]["y"]) for pid in sim.players}
    previous = {}
    consumed = 0
    hist = [0] * int(seconds)
    last_sec = [-1]

    for i in range(total):
        sess.inputs = {}
        for pid, d in drivers.items():
            (ax, ay), aim, fire, want, sprint = d.think()
            st = sim.players[pid]
            if st.get("dead"):
                continue
            aim_deg = math.degrees(math.atan2(aim[1] - st["y"],
                                               aim[0] - st["x"])) % 360.0
            # ArenaSim consumes the wire-format angle field ``a`` (the same
            # conversion HeadlessBot uses). Raw aim coordinates are not a
            # recognized simulation input and silently left shots at 0 deg.
            sess.inputs[pid] = dict(mx=ax, my=ay, a=aim_deg,
                                    b=(P.F_FIRING if fire else 0)
                                    | (P.F_SPRINTING if sprint else 0),
                                    w=want)
        sim.step()
        for pid, st in sim.players.items():
            if st.get("dead"):
                previous.pop(pid, None)
                continue
            d = drivers[pid]
            if d._was_dead:  # ignore the single respawn frame before restaging
                previous.pop(pid, None)
                continue
            x, y = st["x"], st["y"]
            old = previous.get(pid)
            if old is not None and math.hypot(x - old[0], y - old[1]) > 20.0:
                # A respawn restage is a teleport, not authored footwork.
                previous[pid] = (x, y)
                continue
            box = motion[pid]
            box["minx"] = min(box["minx"], x)
            box["maxx"] = max(box["maxx"], x)
            box["miny"] = min(box["miny"], y)
            box["maxy"] = max(box["maxy"], y)
            if old is not None:
                box["distance"] += math.hypot(x - old[0], y - old[1])
            previous[pid] = (x, y)

        n = len(sim.shots)
        for shot in sim.shots[consumed:]:
            shots.append((sim.tick, shot[4]))
            hist[min(len(hist) - 1, sim.tick // T)] += 1
        consumed = n
        for ev in sim.events:
            if ev[0] == P.EV_KILL:
                key = (ev[1], ev[2], sim.tick)
                if key not in seen:
                    seen.add(key)
                    kills.append((sim.tick, ev[1], ev[2]))

        sec = min(len(hist) - 1, sim.tick // T)
        if verbose and sec != last_sec[0]:
            last_sec[0] = sec
            rows = []
            for pid in sorted(sim.players):
                st = sim.players[pid]
                d = drivers[pid]
                ent = d.script[min(d.wp, len(d.script) - 1)]
                tgt = d._target(sim, ent, AR.weapon_stats(st["weapon"])
                                ["range"] * d.RANGE_FRAC)
                td = ("-" if tgt is None else
                      "%.0f" % math.hypot(tgt["x"] - st["x"],
                                          tgt["y"] - st["y"]))
                rows.append("%s(%d,%d)hp%d%s wp%d rc%d %s tgt%s los%d hold%d gap%d"
                            % (nick_of[pid][:6], st["x"], st["y"], st["hp"],
                               "DEAD" if st["dead"] else "    ", d.wp,
                               d._respawn_count, ent.get("do", "move"), td,
                               d._no_los, d._burst_hold, d._gap))
            print("  --- t=%2ds " % sec + " | ".join(rows))
    return sim, shots, kills, nick_of, hist, motion


def report(sim, shots, kills, nick_of, hist, motion):
    problems = []
    print("  shots %d   kills %d   phase=%s"
          % (len(shots), len(kills), sim.rules.phase))
    if not shots:
        print("  NO SHOTS AT ALL")
        return False
    first = shots[0][0] / T
    gaps = [(shots[i][0] - shots[i - 1][0]) / T for i in range(1, len(shots))]
    worst = max(gaps) if gaps else 0.0
    print("  first shot  %5.2fs   (gate: < %.2f)" % (first, GATE_FIRST_SHOT))
    print("  worst gap   %5.2fs   (gate: < %.2f)" % (worst, GATE_MAX_GAP))
    print("  shots/sec   " + " ".join("%3d" % v for v in hist))

    per = {}
    for _t, s in shots:
        per[nick_of.get(s, s)] = per.get(nick_of.get(s, s), 0) + 1
    print("  shots by    " + "  ".join("%s=%d" % kv for kv in sorted(per.items())))
    moving = True
    for pid in sorted(motion):
        m = motion[pid]
        dx, dy = m["maxx"] - m["minx"], m["maxy"] - m["miny"]
        nick = nick_of[pid]
        print("  move %-13s %4.0fpx  span %3.0fx%3.0fpx"
              % (nick[:13], m["distance"], dx, dy))
        if m["distance"] < 70.0 or max(dx, dy) < 40.0:
            moving = False
            problems.append("%s barely moved" % nick)

    print("  killfeed:")
    for t, k, v in kills:
        print("    %5.2fs  %-13s > %s" % (t / T, nick_of.get(k, k),
                                          nick_of.get(v, v)))
    sc = sim.rules.kills
    ipa = sum(sc.get(p, 0) for p, s in sim.players.items() if s["team"] == 0)
    krap = sum(sc.get(p, 0) for p, s in sim.players.items() if s["team"] == 1)
    print("  score       IPA %d - %d KRAP" % (ipa, krap))

    team_of = {nick_of[pid]: s["team"] for pid, s in sim.players.items()}
    for n, v in sorted(per.items()):
        if v < GATE_MIN_SHOTS:
            problems.append("%s barely participated (%d shots)" % (n, v))
    if ipa and krap and max(ipa, krap) / float(ipa + krap) > 0.7:
        problems.append("lopsided %d-%d" % (ipa, krap))
    if not krap or not ipa:
        problems.append("one team did not score")

    last = {"IPA": None, "KRAP": None}
    lull = 0.0
    for t, k, _v in kills:
        side = "IPA" if team_of.get(nick_of.get(k)) == 0 else "KRAP"
        if last[side] is not None:
            lull = max(lull, (t - last[side]) / T)
        last[side] = t
    print("  longest stretch without a score: %.2fs   (gate: < %.2f)"
          % (lull, GATE_MAX_SCORELULL))
    if lull > GATE_MAX_SCORELULL:
        problems.append("killfeed stalled %.2fs" % lull)
    if first >= GATE_FIRST_SHOT:
        problems.append("first shot too late")
    if worst >= GATE_MAX_GAP:
        problems.append("dry gap in the middle of the fight")
    if not kills:
        problems.append("nobody died")

    for p in problems:
        print("  FAIL " + p)
    print("  VERDICT     " + ("PASS" if not problems else "FAIL"))
    return not problems


def main():
    allok = True
    for seed in SEEDS:
        print("=" * 66)
        print("CHOREOGRAPHY DRY RUN  seed=%d" % seed)
        print("=" * 66)
        sim, shots, kills, nick_of, hist, motion = run(seed=seed)
        allok &= report(sim, shots, kills, nick_of, hist, motion)
    print("=" * 66)
    print("ALL SEEDS PASS" if allok else "SOME SEEDS FAILED - retune and re-run")
    print("=" * 66)
    return 0 if allok else 1


if __name__ == "__main__":
    sys.exit(main())

