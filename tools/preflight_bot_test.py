"""Offline pre-flight: exercise GridNav + ArenaBot + foley payloads against
a bare ArenaSim (no sockets, no capture) to catch API mismatches cheaply."""
import os, sys, random, math
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import mp_trailer_capture as cap

nav = cap.GridNav(cap.AR.ARENAS["foundry"])
print("grid", nav.w, "x", nav.h)

# path across the map
p = nav.path_to(3 * 36 + 18, 2 * 36 + 18, 20 * 36 + 18, 12 * 36 + 18)
print("path nodes:", len(p), "first", p[0], "last", p[-1])
assert len(p) > 5

# bare sim with 4 players
class FakeSess:
    is_host = True
    tick = 0
    def send_events(self, tick, events): return True
    def broadcast(self, entities=None): return True
    def send_match_state(self, state): return True
    def consume_input(self, pid): return None
    def tick_once(self): self.tick += 1

sim = cap.AR.ArenaSim(FakeSess(), cap.AR.ARENAS["foundry"], mode=cap.AR.MODE_TDM)
for pid, name in ((0, "ANDREI"), (1, "BIRIBEL"), (2, "MIRELA"), (3, "MICUL FUEGO")):
    sim.add_player(pid, name)
print("teams:", {p: s["team"] for p, s in sim.players.items()})
print("spawn:", {p: (int(s["x"]), int(s["y"])) for p, s in sim.players.items()})

sim_get = lambda: sim
bots = {pid: cap.ArenaBot(pid, nav, sim_get, random.Random(pid * 7 + 1))
        for pid in range(4)}

# feed bot intent straight into the sim for ~600 ticks (bypasses network):
kills = shots = 0
for i in range(600):
    for pid in range(4):
        (ax, ay), aim, fire, want, sprint = bots[pid].think()
        st = sim.players[pid]
        st["angle"] = math.degrees(math.atan2(aim[1] - st["y"], aim[0] - st["x"])) % 360.0
        btn = (cap.P.F_FIRING if fire else 0) | (cap.P.F_SPRINTING if sprint else 0)
        inp = {"t": cap.P.T_INPUT, "q": i, "mx": ax, "my": ay,
               "a": st["angle"], "b": btn}
        if want is not None:
            inp["w"] = want
        sim._accept_input_local = None
        # inject via session-like consume: simplest is to push into MatchSession-shaped
        # hist; here we fake it by calling _step_player directly with our input
        sim._step_player(st, inp)
    for pid, st in list(sim.players.items()):
        sim._step_pickups(st)
    sim._step_round(sim.tick)
    sim.tick += 1
    shots += len(sim.shots)
    kills += sum(1 for e in sim.events if e[0] == cap.P.EV_KILL)

print(f"600 ticks: shots={shots} kills={kills}")
print("positions:", {p: (int(s["x"]), int(s["y"])) for p, s in sim.players.items()})
print("bot shots:", {p: b.shots for p, b in bots.items()})
print("hp:", {p: s["hp"] for p, s in sim.players.items()})
assert shots > 20, "bots never fired"
assert kills >= 1, "no kills - fight not lethal enough"
print("PREFLIGHT OK")

