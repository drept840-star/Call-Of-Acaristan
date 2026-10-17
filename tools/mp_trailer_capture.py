#!/usr/bin/env python3
"""mp_trailer_capture.py - REAL multiplayer arena footage for the announcement trailer.

What this captures (1000x700 @ 30 fps, one mp4 per viewpoint):

  host_flow.mp4    the HOST's screen: browser -> ARENA MATCH panel (TDM,
                   foundry, 4 seats, callsign typed) -> HOST MATCH -> frozen
                   lobby with the room code -> joiners arrive -> START MATCH
                    -> 3/2/1/GO -> live 2v2 combat and kill feed
  client_flow.mp4  the JOINER's screen: panel -> room code typed -> JOIN
                   MATCH -> "CONNECTED - WAITING FOR HOST" lobby -> the same
                   countdown and fight from the other side of the socket

Everything is the REAL stack: two MatchScreen instances (host + joiner) and
two headless protocol bots (BIRIBEL, MICUL FUEGO) over real TCP sockets on
loopback, driven through the real input paths (pygame key state + mouse for
the rendered instances, `in` packets for the headless peers). Nothing is
mocked or re-implemented; the footage is what a player would see.

Foley sidecar (host_flow.foley.json): every sim shot / kill / hit / pickup /
dry-fire with tick + world position + shooter + weapon, so the assembler can
re-render positioned gunfire from sfx_wav on the ticks the match actually
fired (same philosophy as tools/record_fresh_action.py).

chapters.json: frame/time marks for every beat (code_ready, roster_full,
go_moment, round_over, ...) for the assembler's EDL.

Usage:
    python mp_trailer_capture.py [--no-browser] [--combat-seconds 60]

Set MP_ANNOUNCE_DIR to write a retake into a separate capture/output folder.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import random
import shutil
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path

# ── 0. PREFLIGHT (before any game import) ──────────────────────────────────
ROOT = Path(__file__).resolve().parents[1]  # repo root (this script lives in tools/)
os.chdir(ROOT)
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tools"))

# Sandbox the save/settings stores (record_fresh_action pattern).
_SCRATCH = Path(tempfile.mkdtemp(prefix="mp_trailer_"))
from core import save_system as _sv          # noqa: E402
from core import settings_store as _st       # noqa: E402
from core import profile_store as _pf        # noqa: E402
_sv.SAVE_FILE = str(_SCRATCH / "save_data.json")
_st.SAVE_FILE = str(_SCRATCH / "settings.json")
# The profile is not optional here: this drives two real MatchScreen instances
# through real round endings, and the payout is credited from the draw path.
# Without this, capturing a trailer would quietly farm Acaribucks into the
# player's own wallet.
_pf.PROFILE_FILE = str(_SCRATCH / "profile.json")

import pygame                                # noqa: E402

from core import config                      # noqa: E402
from core.config import WIDTH, HEIGHT, TILE_SIZE as T  # noqa: E402
from core.state import STATE                 # noqa: E402
from entities.enemy_ai import _astar         # noqa: E402
from missions import arena as AR             # noqa: E402
from net import protocol as P                # noqa: E402
import ui as menu                            # noqa: E402  (app.py: "import ui as menu")
from ui import mp as menu_mp                 # noqa: E402
from ui.match_screen import MatchScreen      # noqa: E402

FPS = 30
SIM_HZ = 60
DT = 1.0 / SIM_HZ

OUT_DIR = Path(os.environ.get(
    "MP_ANNOUNCE_DIR", str(ROOT / "trailers" / "mp_announce"))).resolve()
HOST_MP4 = OUT_DIR / "host_flow.mp4"
CLIENT_MP4 = OUT_DIR / "client_flow.mp4"

# Cast + staging (TDM 2v2 on foundry).
HOST_NAME = "ANDREI"
FRIEND_NAME = "MIRELA"
BOT_NAMES = ("BIRIBEL", "MICUL FUEGO")
MAP_NAME = "foundry"
MODE_NAME = AR.MODE_TDM
SEATS = 4
PARK_MOUSE = (34, 668)          # bottom-left, outside every panel/control


def ffmpeg_exe() -> str:
    for cand in (os.environ.get("FFMPEG"), shutil.which("ffmpeg")):
        if cand and Path(cand).exists():
            return str(cand)
    raise SystemExit("ffmpeg not found")


# ── 1. Ticker - one ffmpeg rawvideo pipe per viewpoint ─────────────────────
class Ticker:
    def __init__(self, ffmpeg: str, out: Path):
        self.out = out
        self.frames = 0
        self._sigs: set[bytes] = set()
        self._prev_sig: bytes | None = None
        self._changed = 0
        self._samples = 0
        self._lum: list[int] = []
        self.proc = subprocess.Popen(
            [ffmpeg, "-y", "-f", "rawvideo", "-pix_fmt", "rgb24",
             "-s", f"{WIDTH}x{HEIGHT}", "-r", str(FPS), "-i", "-", "-an",
             "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "16",
             "-preset", "medium", "-movflags", "+faststart", str(out)],
            stdin=subprocess.PIPE, stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL)

    def feed(self, surface) -> None:
        self.proc.stdin.write(pygame.image.tobytes(surface, "RGB"))
        self.frames += 1
        if self.frames % 30:
            return
        self._samples += 1
        small = pygame.transform.smoothscale(surface, (40, 28))
        sig = pygame.image.tobytes(small, "RGB")
        self._sigs.add(sig)
        if self._prev_sig is not None and sig != self._prev_sig:
            self._changed += 1
        self._prev_sig = sig
        r, g, b, _a = pygame.transform.average_color(small)
        self._lum.append((r * 299 + g * 587 + b * 114) // 1000)

    def close(self) -> str:
        self.proc.stdin.close()
        self.proc.wait()
        if self.proc.returncode != 0:
            return f"ffmpeg exited {self.proc.returncode}"
        return ""

    @property
    def changed_ratio(self) -> float:
        return round(self._changed / self._samples, 2) if self._samples else 0.0

    @property
    def mean_luma(self) -> float:
        return round(sum(self._lum) / len(self._lum), 2) if self._lum else 0.0


# ── 2. Input plumbing ───────────────────────────────────────────────────────
class Keys:
    """Duck-types pygame.key.get_pressed()."""

    def __init__(self):
        self.down: set[int] = set()

    def __getitem__(self, k):
        return k in self.down


IDLE_KEYS = Keys()


def mset(x, y):
    pygame.mouse.set_pos((int(x), int(y)))


def ev_click(pos):
    return pygame.event.Event(pygame.MOUSEBUTTONDOWN,
                              {"pos": (int(pos[0]), int(pos[1])), "button": 1})


def ev_key(key, uni=""):
    return pygame.event.Event(pygame.KEYDOWN,
                              {"key": key, "unicode": uni, "mod": 0})


# ── 3. Chapters + foley recorder ────────────────────────────────────────────
class Chapters:
    def __init__(self):
        self.marks: dict[str, dict] = {}

    def mark(self, name, frame, sec):
        self.marks[name] = {"frame": int(frame), "sec": round(sec, 3)}
        print(f"  [chapter] {name:<18} frame {frame:<5} {sec:6.2f}s", flush=True)

    def save(self, path: Path):
        path.write_text(json.dumps(self.marks, indent=1), encoding="utf-8")


WPN_NAMES = {}


def _init_wpn_names():
    for attr in ("WPN_PISTOL", "WPN_OS12", "WPN_K9"):
        val = getattr(P, attr, None)
        if val is not None:
            WPN_NAMES[val] = attr.replace("WPN_", "").lower()


class Foley:
    """Observes every host sim tick; logs positioned audio events."""

    def __init__(self):
        self.events: list[dict] = []
        self._installed = False

    def install(self, ms: MatchScreen):
        if self._installed or ms.sim is None:
            return
        self._installed = True
        sim = ms.sim
        orig_step = sim.step
        foley = self

        def observed_step():
            orig_step()
            tick = sim.tick
            view = ms.view
            cam_x = getattr(view, "cam_x", 0.0)
            cam_y = getattr(view, "cam_y", 0.0)
            for shot in sim.shots:
                shooter = shot[4]
                wst = sim.players.get(shooter, {})
                foley.events.append(dict(
                    kind="player_shot" if shooter == 0 else "enemy_shot",
                    t=tick, x=round(shot[0], 1), y=round(shot[1], 1),
                    shooter=int(shooter),
                    weapon=WPN_NAMES.get(wst.get("weapon"), "pistol"),
                    hit=bool(shot[5]),
                    cam_x=round(cam_x, 1), cam_y=round(cam_y, 1)))
            for ev in sim.events:
                kind = ev[0]
                if kind == P.EV_KILL:
                    xy = (round(float(ev[4]), 1), round(float(ev[5]), 1)) \
                        if len(ev) > 5 else (None, None)
                    foley.events.append(dict(
                        kind="kill", t=tick, killer=int(ev[1]), victim=int(ev[2]),
                        weapon=WPN_NAMES.get(ev[3], "pistol"),
                        x=xy[0], y=xy[1],
                        cam_x=round(cam_x, 1), cam_y=round(cam_y, 1)))
                elif kind == P.EV_HIT:
                    foley.events.append(dict(
                        kind="hit", t=tick, shooter=int(ev[1]), victim=int(ev[2]),
                        dmg=int(ev[3]), x=round(float(ev[4]), 1),
                        y=round(float(ev[5]), 1),
                        cam_x=round(cam_x, 1), cam_y=round(cam_y, 1)))
                elif kind == P.EV_PICKUP:
                    foley.events.append(dict(
                        kind="pickup", t=tick, who=int(ev[1]),
                        x=round(float(ev[4] or 0), 1),
                        y=round(float(ev[5] or 0), 1),
                        cam_x=round(cam_x, 1), cam_y=round(cam_y, 1)))
                elif kind == P.EV_EMPTY:
                    foley.events.append(dict(kind="dryfire", t=tick,
                                             who=int(ev[1])))

        sim.step = observed_step
        print("  [foley] observer installed on host sim", flush=True)

    def save(self, path: Path, meta: dict):
        counts = {}
        for e in self.events:
            counts[e["kind"]] = counts.get(e["kind"], 0) + 1
        path.write_text(json.dumps(dict(
            hz=SIM_HZ, fps=FPS, meta=meta, counts=counts,
            events=self.events), indent=1), encoding="utf-8")
        print(f"  [foley] {len(self.events)} events {counts}", flush=True)


# ── 4. GridNav - A* over the arena tilemap ─────────────────────────────────
class GridNav:
    def __init__(self, map_rows):
        # '+' is a doorway: bullets pass, bodies do not. A* must not
        # route onto those tiles or the bot wedges on the jamb forever.
        self.grid = [[ch not in "#+" for ch in row] for row in map_rows]
        self.h = len(self.grid)
        self.w = max(len(r) for r in self.grid)

    def path_to(self, sx, sy, gx, gy):
        """World px -> world px path (tile centres). [] when unreachable."""
        s = (int(sx // T), int(sy // T))
        g = (int(gx // T), int(gy // T))
        if not (0 <= s[0] < self.w and 0 <= s[1] < self.h):
            return []
        if not (0 <= g[0] < self.w and 0 <= g[1] < self.h):
            return []
        if not self.grid[s[1]][s[0]]:
            s = self._nearest_open(*s)
            if s is None:
                return []
        if not self.grid[g[1]][g[0]]:
            g = self._nearest_open(*g)
            if g is None:
                return []
        try:
            raw = _astar(s, g, self.grid)
        except Exception:
            raw = None
        if not raw:
            return []
        # String-pull the A* corner list: from each kept tile, jump to the
        # farthest tile with open tile-LOS. Raw A* hugs wall corners
        # tile-by-tile, which quantised onto WASD reads as a staircase
        # shuffle; the pulled path cuts smooth diagonals across open rooms.
        kept = [raw[0]]
        i = 0
        while i < len(raw) - 1:
            j = len(raw) - 1
            while j > i + 1 and not self._tile_los(kept[-1], raw[j]):
                j -= 1
            kept.append(raw[j])
            i = j
        return [(x * T + T // 2, y * T + T // 2) for x, y in kept]

    def _tile_los(self, a, b):
        """True when the tile segment a->b never crosses a solid tile."""
        x0, y0, x1, y1 = a[0], a[1], b[0], b[1]
        steps = max(abs(x1 - x0), abs(y1 - y0)) * 2 + 1
        for i in range(steps + 1):
            t = i / float(steps)
            x = int(round(x0 + (x1 - x0) * t))
            y = int(round(y0 + (y1 - y0) * t))
            if not (0 <= x < self.w and 0 <= y < self.h):
                return False
            if not self.grid[y][x]:
                return False
        return True

    def _nearest_open(self, cx, cy):
        for r in range(1, 6):
            for dx in range(-r, r + 1):
                for dy in range(-r, r + 1):
                    nx, ny = cx + dx, cy + dy
                    if 0 <= nx < self.w and 0 <= ny < self.h \
                            and self.grid[ny][nx]:
                        return (nx, ny)
        return None


# ── 5. ArenaBot - the "player" behind every seat ────────────────────────────
class ArenaBot:
    """Combat AI. Produces intent (axes, aim point, trigger, weapon request);
    an adapter delivers it through each seat's REAL input path."""

    RETARGET = 80            # frames between forced target reevaluation
    REPATH = 90              # frames between path recomputes
    ARRIVE = 26              # px: waypoint reached
    STUCK_TICKS = 35

    def __init__(self, pid, nav: GridNav, sim_get, rng: random.Random,
                 aggression=1.0, wingman_of=None):
        self.pid = pid
        self.nav = nav
        self.sim_get = sim_get
        self.rng = rng
        self.aggression = aggression
        # Soft buddy: prefer the same fight as LEADER, not a tight orbit.
        self.wingman_of = wingman_of
        self._hold = 0
        self._hold_axes = (0.0, 0.0)
        self._drift = rng.uniform(-0.18, 0.18)
        # wedge escape state: a box caught on a wall corner makes zero
        # progress on a pure-axis press; a short perpendicular slide fixes it
        self._escape = 0
        self._escape_sign = 1
        self.frame = 0
        self.target_id = None
        self.retarget_in = 0
        self.path: list = []
        self.repath_in = 0
        self.strafe = 1 if rng.random() < 0.5 else -1
        self.strafe_in = rng.randint(180, 420)
        self.waypoint = None
        self.burst = 0
        self.gap = rng.randint(4, 18)
        self._last_pos = None
        self._stuck = 0
        self._want_weapon_ok = 0
        self.shots = 0
        self.aim_pt = (0.0, 0.0)
        self.phase = rng.uniform(0, 6.28)

    # -- helpers ------------------------------------------------------------
    def _foes(self, sim, me):
        team = me.get("team")
        out = []
        for pid, st in sim.players.items():
            if pid == self.pid or st["dead"]:
                continue
            if team is not None and st.get("team") == team:
                continue
            out.append(st)
        return out

    def _pick_target(self, sim, me, foes):
        best, bd = None, 1e9
        for st in foes:
            d = math.hypot(st["x"] - me["x"], st["y"] - me["y"])
            if d < bd:
                best, bd = st, d
        self.target_id = best["id"] if best else None
        self.retarget_in = self.RETARGET + self.rng.randint(-15, 25)

    def _new_waypoint(self, sim, me, tgt, ring_lo=160, ring_hi=360):
        ang = math.atan2(me["y"] - tgt["y"], me["x"] - tgt["x"])
        ring = self.rng.uniform(ring_lo, ring_hi)
        swing = self.strafe * self.rng.uniform(0.15, 0.85)
        a = ang + swing
        wx = tgt["x"] + math.cos(a) * ring
        wy = tgt["y"] + math.sin(a) * ring
        wx = max(T, min(self.nav.w * T - T, wx))
        wy = max(T, min(self.nav.h * T - T, wy))
        self.waypoint = (wx, wy)
        self.path = self.nav.path_to(me["x"], me["y"], wx, wy)
        self.repath_in = self.REPATH + self.rng.randint(20, 80)

    def _pickup_detour(self, sim, me):
        """Nearby wanted pickup overrides the waypoint (map control)."""
        want = {"W", "M", "B"}
        if me.get("hp", 100) < 55:
            want.add("R")
        best, bd = None, 340
        for pk in sim.pickup_items:
            if pk["kind"] not in want or pk["ready_at"] > sim.tick:
                continue
            d = math.hypot(pk["x"] - me["x"], pk["y"] - me["y"])
            if d < bd:
                best, bd = pk, d
        return best

    # -- main ---------------------------------------------------------------
    def think(self):
        """Returns (axes_xy, aim_world_xy, fire, want_weapon, sprint)."""
        self.frame += 1
        sim = self.sim_get()
        me = sim.players.get(self.pid) if sim is not None else None
        if sim is None or me is None or me["dead"]:
            return (0.0, 0.0), self.aim_pt, False, None, False

        foes = self._foes(sim, me)
        if self.retarget_in <= 0 or not foes or \
                self.target_id not in sim.players or \
                sim.players[self.target_id]["dead"]:
            self._pick_target(sim, me, foes)
        tgt = sim.players.get(self.target_id) if self.target_id is not None else None

        ax = ay = 0.0
        sprint = False
        move_tgt = tgt
        wing = False
        if self.wingman_of is not None:
            lead = sim.players.get(self.wingman_of)
            if lead is not None and not lead["dead"] and lead is not me:
                # Same fight, not a leash. Only pull toward the leader if
                # they have drifted far enough that the camera lost them.
                ld = math.hypot(lead["x"] - me["x"], lead["y"] - me["y"])
                if ld > 280 and (tgt is None or ld > 420):
                    move_tgt = lead
                    wing = True
        if self._hold > 0:
            self._hold -= 1
            if tgt is not None:
                jx = tgt["x"] + math.sin(self.frame * 0.07 + self.phase) * 18
                jy = tgt["y"] + math.cos(self.frame * 0.06 + self.phase) * 18
                self.aim_pt = (jx, jy)
            return self._hold_axes, self.aim_pt, False, None, False
        if move_tgt is not None:
            dist = math.hypot(move_tgt["x"] - me["x"], move_tgt["y"] - me["y"])
            # stuck detection
            if self._last_pos is not None:
                if math.hypot(me["x"] - self._last_pos[0],
                              me["y"] - self._last_pos[1]) > 1.5:
                    self._stuck = 0
                else:
                    self._stuck += 1
            self._last_pos = (me["x"], me["y"])

            pk = self._pickup_detour(sim, me)
            if pk is not None and self.rng.random() < 0.85 and not wing:
                if self.waypoint != (pk["x"], pk["y"]):
                    self.waypoint = (pk["x"], pk["y"])
                    self.path = self.nav.path_to(me["x"], me["y"],
                                                 pk["x"], pk["y"])
                    self.repath_in = self.REPATH
            else:
                self.strafe_in -= 1
                if self.strafe_in <= 0:
                    self.strafe = -self.strafe
                    self.strafe_in = self.rng.randint(240, 520)
                if wing:
                    if self.repath_in <= 0 or not self.path:
                        self._new_waypoint(sim, me, move_tgt, 180, 320)
                elif self.repath_in <= 0 or not self.path:
                    self._new_waypoint(sim, me, move_tgt)
            self.repath_in -= 1

            # follow the path
            node = self._next_node(me)
            if node is not None:
                dx, dy = node[0] - me["x"], node[1] - me["y"]
                d = math.hypot(dx, dy) or 1.0
                ax, ay = dx / d, dy / d
                ax += self._drift
                ay += math.sin(self.frame * 0.031 + self.phase) * 0.12
                n = math.hypot(ax, ay) or 1.0
                ax, ay = ax / n, ay / n
                sprint = dist > 640 and self.rng.random() < 0.7
                if self.rng.random() < 0.012 and self._hold <= 0:
                    self._hold = self.rng.randint(10, 28)
                    self._hold_axes = (ax * 0.15, ay * 0.15)
                # ── wedge escape ──
                # A 32 px box in a 64 px corridor has zero tile margin, and a
                # pure-axis press into a corner (the quantised key path, or an
                # A* node dead ahead behind a corner) grinds forever: the
                # slide resolves x, dy stays 0, nothing ever clears. When the
                # stuck counter says "no progress", slide ALONG the wall for a
                # few frames: press only the minor axis, toward the node if it
                # is offset, else an alternating guess. 12 frames at 2-4 px is
                # 24-48 px - more than a corner depth.
                if self._stuck > 15 and self._escape <= 0:
                    self._escape = 12
                    self._escape_sign = -self._escape_sign
                if self._escape > 0:
                    self._escape -= 1
                    if abs(dx) >= abs(dy):
                        s = 1 if dy > 4 else (-1 if dy < -4
                                              else self._escape_sign)
                        ax, ay = 0.0, float(s)
                    else:
                        s = 1 if dx > 4 else (-1 if dx < -4
                                              else self._escape_sign)
                        ax, ay = float(s), 0.0
            if self._stuck > self.STUCK_TICKS:
                if wing:
                    self._new_waypoint(sim, me, move_tgt, 180, 320)
                else:
                    self._new_waypoint(sim, me, move_tgt)
                self._stuck = 0

            # aim: jittered point on the target (human-ish, occasionally off)
            # (keyed on the ENEMY target, not the movement anchor: a wingman
            # keeps moving with its leader even while no foe is in reach).
            # Eased toward the desired point so a target switch glides the
            # reticle instead of snapping it across the screen in one frame.
            if tgt is not None:
                jx = tgt["x"] + math.sin(self.frame * 0.09 + self.phase) * 13
                jy = tgt["y"] + math.cos(self.frame * 0.075 + self.phase) * 13
                ax0, ay0 = self.aim_pt
                if math.hypot(jx - ax0, jy - ay0) > 600:
                    self.aim_pt = (jx, jy)
                else:
                    self.aim_pt = (ax0 + (jx - ax0) * 0.35,
                                   ay0 + (jy - ay0) * 0.35)
        else:
            # No movement anchor (every foe dead and no live leader): push
            # to mid-map control instead of standing still. A bot idling in
            # place while the tape rolls is what made the post-wipe beats
            # read as frozen footage.
            cx = self.nav.w * T / 2.0
            cy = self.nav.h * T / 2.0
            pk = self._pickup_detour(sim, me)
            gx, gy = (pk["x"], pk["y"]) if pk is not None else (cx, cy)
            if not self.path or self.repath_in <= 0:
                self.path = self.nav.path_to(me["x"], me["y"], gx, gy)
                self.repath_in = self.REPATH
            self.repath_in -= 1
            node = self._next_node(me)
            if node is not None:
                dx, dy = node[0] - me["x"], node[1] - me["y"]
                d = math.hypot(dx, dy) or 1.0
                ax, ay = dx / d, dy / d
                sprint = True

        # trigger discipline with LOS
        fire = False
        if tgt is not None:
            stats = AR.weapon_stats(me["weapon"])
            ang = math.degrees(math.atan2(tgt["y"] - me["y"],
                                          tgt["x"] - me["x"])) % 360.0
            targets = [(st["id"], st["x"], st["y"]) for st in foes]
            kind, tid, _dist = AR.hitscan(me["x"], me["y"], ang, sim.walls,
                                          targets, range_px=2200)
            clear = kind == "player"
            d = math.hypot(tgt["x"] - me["x"], tgt["y"] - me["y"])
            if clear:
                self._no_los = 0
            else:
                self._no_los = getattr(self, "_no_los", 0) + 1
                if self._no_los > 90 and not wing:
                    # starved of shots for ~1.5 s: push the target directly
                    # (a wingman holds formation instead: staying near the
                    # leader matters more than chasing its own kill)
                    self.waypoint = (tgt["x"], tgt["y"])
                    self.path = self.nav.path_to(me["x"], me["y"],
                                                 tgt["x"], tgt["y"])
                    self.repath_in = 40
                    self._no_los = 0
            if clear and d < stats["range"] * 0.88:
                if self.burst > 0:
                    fire = True
                    self.burst -= 1
                    self.shots += 1
                    if self.burst == 0:
                        self.gap = self.rng.randint(16, 40)
                        if self.rng.random() < 0.18:
                            self._hold = self.rng.randint(8, 22)
                            self._hold_axes = (ax * 0.2, ay * 0.2)
                else:
                    self.gap -= 1
                    if self.gap <= 0:
                        self.burst = self.rng.randint(2, 5)
            else:
                self.burst = 0
            if fire and self.rng.random() < 0.08:
                fire = False

        # weapon request: switch off the pistol once something better is held
        want_weapon = None
        self._want_weapon_ok -= 1
        if self._want_weapon_ok <= 0 and me["weapon"] == "pistol":
            carry = me.get("carry") or ["pistol"]
            if "os12" in carry:
                want_weapon = P.WPN_OS12
                self._want_weapon_ok = 90
            elif "k9_smg" in carry:
                want_weapon = P.WPN_K9
                self._want_weapon_ok = 90
        return (ax, ay), self.aim_pt, fire, want_weapon, sprint

    def _next_node(self, me):
        while self.path:
            nx, ny = self.path[0]
            if math.hypot(nx - me["x"], ny - me["y"]) <= self.ARRIVE:
                self.path.pop(0)
                continue
            return (nx, ny)
        if self.waypoint is not None:
            return self.waypoint
        return None

    def axes_to_keys(self, ax, ay, sprint):
        """Quantise float axes onto a pygame key state.

        The keep-both-axes threshold is 0.35, not 0.5: a path node 26
        degrees off an axis still presses BOTH keys, so the sprite slides
        diagonally around wall corners instead of grinding into them on a
        pure-axis press. A 0.5 threshold turned (0.89, 0.46) into (1, 0)
        and wedged the driver in corridor mouths forever.
        """
        def q(v):
            return 1 if v > 0.35 else (-1 if v < -0.35 else 0)
        k = Keys()
        kx, ky = q(ax), q(ay)
        if kx < 0:
            k.down.add(pygame.K_a)
        elif kx > 0:
            k.down.add(pygame.K_d)
        if ky < 0:
            k.down.add(pygame.K_w)
        elif ky > 0:
            k.down.add(pygame.K_s)
        if sprint:
            k.down.add(pygame.K_LSHIFT)
        return k


# ── 5b. ScriptDriver - the choreographed operator ──────────────────────────
class ScriptDriver:
    """Hand-authored waypoint driver, same think() contract as ArenaBot.

    The announcement tape needs two players who look like they know what
    they are doing, not a roaming AI filling time. Each seat gets a short
    waypoint script (move / snap-to-target / swap / tap), authored against
    the foundry map; all four seats are scripted so the exchange reads as a
    firefight instead of four robots orbiting each other.

    Entry shape (all keys optional):
        to      world-px move target; None = hold position
        aim     (x, y) fixed point, or a selector (see _target)
        do      "move" (default, advance on arrival) | "tap" | "swap" | "hold"
        n       exact shots per burst for this entry; omitted = random burst size
        gun     weapon id for "swap"
        hold    dwell ticks once the action is done (entry length)
        lead    ticks before the first burst may open (entry minimum)
        initial_only  hold only on the first life, never after respawn
        jitter  aim-point noise radius in pixels for this entry
        sprint  sprint the long legs of the move

    ``aim`` selectors:
        ("t", pid)     one specific seat - only safe when the tape has
                       already proven which pid is on which team
        ("vs", name)   one specific OPPONENT by callsign. This is what the
                       2v2 staging uses: it pins two independent duels, so a
                       seat can never switch to the far opponent while its
                       own partner is respawning
        ("foe",)       nearest living enemy, whatever team it is on
        ("foe", cols)  nearest living enemy within +/- cols columns of me,
                       so a seat holds its own lane instead of tracking
                       somebody three rooms away through a wall
    """

    ARRIVE = 22
    AIM_EASE = 0.45
    REPATH = 90
    # Trigger defaults for entries without explicit pacing. The foundry
    # trailer taps use one shot per burst, a randomized per-seat gap, and a
    # small aim-noise radius: that avoids perfect synchronized volleys while
    # still letting every seat contribute. Full multi-shot bursts caused the
    # original staging to kill players almost immediately, then leave a long
    # respawn-only lull before they could complete their authored movement.
    BURST = (2, 3)
    GAP = (26, 58)
    RANGE_FRAC = 0.9
    # Ticks a lane may stay blocked before a seat gives up holding its post
    # and walks at the target. OFF by default, and bounded when on: the
    # staging posts are pre-verified, so a blocked lane means a teammate or
    # a corpse is in the way, not that the seat is lost - and an unbounded
    # push walked all four seats off the spine into the south-east corner
    # over ~8 s, which silently killed every sightline in the round.
    STARVE = 40
    PUSH = False
    PUSH_RANGE = 800.0

    def __init__(self, pid, nav, sim_get, script, rng, restart_at=0,
                 home=None):
        self.pid = pid
        self.nav = nav
        self.sim_get = sim_get
        self.script = script
        self.rng = rng
        self.restart_at = restart_at
        self._respawn_count = 0
        # Where this seat fights from. A respawn drops a player on their map
        # corner spawn, and on foundry those corners are ~1000 px from the
        # posts - long enough that a seat which died at 1.5 s was still
        # walking back at the end of a 15 s round, which is six seconds of
        # the fight with nobody in range of anybody. Re-staging on respawn
        # keeps all four in the same room for the whole round, which is the
        # only way the firefight actually stays a firefight.
        self.home = home
        self.frame = 0
        self._aim_pt = None
        self._was_dead = False
        self._wp_reset()

    def _wp_reset(self):
        self.wp = self.restart_at
        self._cur_idx = -1

    def _restage(self, sim, me):
        """Put a just-respawned seat back on its post."""
        if not self.home:
            return
        px, py = self.home
        if math.hypot(px - me["x"], py - me["y"]) <= self.ARRIVE:
            return
        me["x"], me["y"] = float(px), float(py)
        # Keep the protection timestamp assigned by the real respawn. The
        # opening stance clears protection once at round start; later restages
        # must not turn a normal protected respawn into an instant spawn-kill.
        self._arrived = False
        self._push_to = None
        self._push_goal = None
        self.path = []
        self.repath_in = 0

    def _begin_entry(self, entry):
        """Per-entry bookkeeping. Called once when the entry changes."""
        self.path = []
        self.repath_in = 0
        self._stuck = 0
        self._last_pos = None
        self._arrived = False
        self._act_left = int(entry.get("hold", 30))
        if self._respawn_count and entry.get("initial_only"):
            self._act_left = 0
        self._swap_want = None
        self._no_los = 0
        self._burst_hold = 0
        cycle = entry.get("lead_cycle")
        if cycle:
            self._gap = int(cycle[self._respawn_count % len(cycle)])
        else:
            self._gap = int(entry.get("lead", 6))
        self._gap_range = entry.get("gap") or self.GAP
        self._push_to = None
        self._push_goal = None

    def _foes(self, sim):
        """Living players on the other team, plus the team-less (FFA)."""
        me = sim.players.get(self.pid)
        my_team = me.get("team") if me else None
        out = []
        for st in sim.players.values():
            if st["id"] == self.pid or st.get("dead"):
                continue
            if my_team is not None and st.get("team") == my_team:
                continue
            out.append(st)
        return out

    def _target(self, sim, entry, rng_px=None):
        """The seat this entry shoots at, or None.

        For the nearest-foe selector, ``rng_px`` makes it aim at the nearest
        enemy the seat can ACTUALLY SEE rather than the nearest enemy full
        stop. That distinction is the whole ball game in TEAM_DEATHMATCH: a
        teammate's body stops the ray for zero damage, so a rear seat whose
        partner is standing in front of it has a "target" it can never
        shoot. Selecting on plain distance left that seat - measured at
        BIRIBEL - firing zero shots for a whole round while his partner did
        all the work.
        """
        a = entry.get("aim")
        if a is None or not (isinstance(a, (tuple, list)) and a
                             and isinstance(a[0], str)):
            return None
        kind = a[0]
        if kind == "t":
            if len(a) < 2:
                return None
            return sim.players.get(a[1])
        if kind == "vs":
            # Duel with one named opponent. Nearest-foe selection cannot be
            # used for a 2v2: with everyone on one lane, a seat whose own
            # partner was respawning simply switched to the far opponent
            # and farmed him instead, which is how one seat ended the round
            # on 8 of 10 kills and how three deaths cascaded into one
            # three-second silence. Naming the opponent pins two
            # independent duels, so neither can feed the other.
            if len(a) < 2:
                return None
            want = seat_key(a[1])
            for st in sim.players.values():
                if st["id"] != self.pid and seat_key(st.get("nick")) == want:
                    return st
            return None
        if kind != "foe":
            return None
        me = sim.players.get(self.pid)
        if me is None:
            return None
        foes = self._foes(sim)
        if not foes:
            return None
        half = a[1] if len(a) > 1 else None
        cand = []
        for st in foes:
            d = math.hypot(st["x"] - me["x"], st["y"] - me["y"])
            if half is not None and \
                    abs(int(st["x"] // T) - int(me["x"] // T)) > int(half):
                continue
            cand.append((d, st))
        if not cand:
            return None
        cand.sort(key=lambda c: c[0])
        if rng_px is not None:
            for _d, st in cand:
                if self._in_los(sim, me, st, rng_px):
                    return st
        return cand[0][1]

    def _aim_point(self, sim, entry, rng_px=None):
        a = entry.get("aim")
        if a is None:
            return self._aim_pt
        if isinstance(a, (tuple, list)) and len(a) == 2 and \
                isinstance(a[0], (int, float)):
            return a
        st = self._target(sim, entry, rng_px)
        if st is not None:
            return (st["x"], st["y"])
        return self._aim_pt

    def _in_los(self, sim, me, tgt, rng_px):
        ang = math.degrees(math.atan2(tgt["y"] - me["y"],
                                      tgt["x"] - me["x"])) % 360.0
        # Dead players must be excluded, exactly as ArenaSim._shoot excludes
        # them. Leaving them in made a body lying in the lane read as cover,
        # so a seat whose kill had just fallen would decide it had no shot at
        # all and stand there - the corpse it had just created silenced the
        # whole firefight for the rest of the exchange.
        targets = [(st["id"], st["x"], st["y"])
                   for st in sim.players.values()
                   if st["id"] != self.pid and not st.get("dead")]
        kind, tid, _d = AR.hitscan(me["x"], me["y"], ang, sim.walls,
                                   targets, range_px=rng_px)
        return kind == "player" and tid == tgt["id"] \
            and math.hypot(tgt["x"] - me["x"], tgt["y"] - me["y"]) <= rng_px

    def think(self):
        sim = self.sim_get()
        me = sim.players.get(self.pid) if sim is not None else None
        idle = self._aim_pt or (0.0, 0.0)
        if sim is None or me is None:
            return (0.0, 0.0), idle, False, None, False
        self.frame += 1
        if me.get("dead"):
            self._was_dead = True
            return (0.0, 0.0), idle, False, None, False
        if self._was_dead:
            self._was_dead = False
            self._respawn_count += 1
            self._restage(sim, me)
            self._wp_reset()
        idx = min(self.wp, len(self.script) - 1)
        entry = self.script[idx]
        if idx != self._cur_idx:
            self._cur_idx = idx
            self._begin_entry(entry)
        action = entry.get("do", "move")
        stats = AR.weapon_stats(me["weapon"])
        # Target selection is range-aware: a seat must be sent at an enemy it
        # can actually hit, not the nearest one on the map.
        reach = stats["range"] * self.RANGE_FRAC
        tgt_pt = self._aim_point(sim, entry, reach)
        # A tap has to connect on its FIRST shot, so the crosshair is put on
        # the target outright; only a moving entry eases toward it. Easing
        # while the trigger is already open is what produced the old tape -
        # the muzzle flashed at a target the aim had not reached yet, so a
        # burst only started landing once the lerp had converged, and the
        # round read as a stare followed by a panic burst.
        jitter = float(entry.get("jitter", 1.2 if action == "tap" else 2.0))
        if self._aim_pt is None or tgt_pt is None:
            self._aim_pt = tgt_pt if tgt_pt is not None else self._aim_pt
        elif action == "tap":
            self._aim_pt = (tgt_pt[0] + self.rng.uniform(-jitter, jitter),
                            tgt_pt[1] + self.rng.uniform(-jitter, jitter))
        else:
            ax0, ay0 = self._aim_pt
            self._aim_pt = (
                ax0 + (tgt_pt[0] - ax0) * self.AIM_EASE
                + self.rng.uniform(-jitter, jitter),
                ay0 + (tgt_pt[1] - ay0) * self.AIM_EASE
                + self.rng.uniform(-jitter, jitter))
        fire = False
        want = None
        sprint = False
        axes = (0.0, 0.0)
        # A starving lane overrides the authored post: after STARVE ticks with
        # no shot the seat walks at the target instead of standing there.
        goal = entry.get("to")
        if self._push_to is not None:
            goal = self._push_to
            if self._push_goal != self._push_to:
                # a fresh push destination has to re-arm arrival, or the
                # seat sits at the old post for the rest of the entry
                self._arrived = False
                self._push_goal = self._push_to
        if goal is not None and not self._arrived:
            d = math.hypot(goal[0] - me["x"], goal[1] - me["y"])
            if d > self.ARRIVE:
                if not self.path or self.repath_in <= 0:
                    self.path = self.nav.path_to(me["x"], me["y"],
                                                 goal[0], goal[1])
                    self.repath_in = self.REPATH
                node = self._next_node(me, goal)
                if node is not None:
                    dx, dy = node[0] - me["x"], node[1] - me["y"]
                    n = math.hypot(dx, dy) or 1.0
                    axes = (dx / n, dy / n)
                    sprint = bool(entry.get("sprint")) and d > 320
                if self._last_pos is not None:
                    if math.hypot(me["x"] - self._last_pos[0],
                                  me["y"] - self._last_pos[1]) > 1.5:
                        self._stuck = 0
                    else:
                        self._stuck += 1
                self._last_pos = (me["x"], me["y"])
                if self._stuck > 40:
                    self.path = []
                    self.repath_in = 0
                    self._stuck = 0
                self.repath_in -= 1
            else:
                self._arrived = True
                if action == "swap":
                    self._swap_want = entry.get("gun")
        standing = self._arrived or goal is None
        if standing and action == "move":
            self.wp += 1
        elif standing and action in ("tap", "swap", "hold"):
            if action == "tap":
                tgt = self._target(sim, entry, reach)
                # A burst is a HELD trigger, not a one-tick pulse, and the
                # weapon's own cooldown spaces the shots inside it. That is
                # how a real trigger pull behaves - and it is also the only
                # thing that survives the wire: both headless bots and the
                # joiner drive over TCP, where the host sees the latest
                # packet per peer and a single-tick fire flag is simply
                # coalesced away. Pulsing cost the remote seats roughly 40%
                # of their shots on the real capture (39 on tape against 61
                # for the same script driven locally), which showed up as
                # bursts of fire separated by holes.
                if self._burst_hold > 0:
                    self._burst_hold -= 1
                    fire = True
                elif tgt is not None and self._in_los(sim, me, tgt, reach):
                    self._no_los = 0
                    self._push_to = None
                    if self._gap <= 0:
                        n = (int(entry["n"]) if entry.get("n") is not None
                             else self.rng.randint(*self.BURST))
                        self._burst_hold = n * stats["cooldown"]
                        self._gap = self.rng.randint(*self._gap_range)
                        fire = True
                    else:
                        self._gap -= 1
                else:
                    # Blocked lane. Counted purely as a diagnostic unless the
                    # entry opts into pushing - and even then only for a
                    # target close enough that closing the gap is the fix.
                    self._no_los += 1
                    if self._no_los >= self.STARVE and tgt is not None \
                            and (entry.get("push") or self.PUSH) \
                            and math.hypot(tgt["x"] - me["x"],
                                           tgt["y"] - me["y"]) <= self.PUSH_RANGE:
                        self._no_los = 0
                        self._push_to = (tgt["x"], tgt["y"])
                        self.path = []
                        self.repath_in = 0
            elif action == "swap" and self._swap_want is not None:
                if me.get("weapon") != self._swap_want:
                    want = self._swap_want
            self._act_left -= 1
            if self._act_left <= 0:
                self.wp += 1
        return axes, self._aim_pt or idle, fire, want, sprint

    def _next_node(self, me, goal):
        while self.path:
            nx, ny = self.path[0]
            if math.hypot(nx - me["x"], ny - me["y"]) <= self.ARRIVE:
                self.path.pop(0)
                continue
            return (nx, ny)
        if self.path is None:
            return None
        return goal

    def axes_to_keys(self, ax, ay, sprint):
        return ArenaBot.axes_to_keys(self, ax, ay, sprint)


# ── 6. HeadlessBot - a real protocol client with no renderer ───────────────
class HeadlessBot:
    """Speaks the real match protocol over a real socket (tools/mp_bot
    philosophy, but for ARENA MATCH): joinmatch handshake, then 60 Hz input
    packets built from ArenaBot intent."""

    def __init__(self, name, host, port, bot: ArenaBot):
        self.name = name
        self.host, self.port = host, port
        self.bot = bot
        self.sock = None
        self.buf = b""
        self.out = b""
        self.seq = 0
        self.pid = None
        self.joined = False
        self.chat_queue: list[str] = []

    def connect(self, timeout=8.0):
        deadline = time.time() + timeout
        while time.time() < deadline:
            try:
                s = socket.create_connection((self.host, self.port), timeout=2)
                s.setblocking(False)
                s.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
                self.sock = s
                self._send(P.make_join_match(MAP_NAME, self.name))
                self._flush()
                self.joined = True
                print(f"  [bot] {self.name} connected + handshake sent",
                      flush=True)
                return True
            except OSError:
                time.sleep(0.15)
        print(f"  [bot] {self.name} could NOT connect", flush=True)
        return False

    def _send(self, obj):
        self.out += P.encode(obj)
        if len(self.out) > 8192:
            self._flush()

    def _flush(self):
        if not self.out or self.sock is None:
            self.out = b""
            return
        data, self.out = self.out, b""
        try:
            self.sock.sendall(data)
        except OSError:
            pass

    def say(self, text):
        self.chat_queue.append(text)

    def pump(self):
        """One frame's worth of socket work + input submission."""
        if self.sock is None:
            return
        # read whatever arrived
        try:
            while True:
                chunk = self.sock.recv(65536)
                if not chunk:
                    self.sock = None
                    return
                self.buf += chunk
                if len(self.buf) > 1 << 20:
                    self.buf = b""
                    return
        except (BlockingIOError, OSError):
            pass
        while b"\n" in self.buf:
            line, self.buf = self.buf.split(b"\n", 1)
            if not line.strip():
                continue
            raw = P.decode(line)
            if not isinstance(raw, dict):
                continue
            assigned = P.parse_assign(raw)
            if assigned is not None and self.pid is None:
                self.pid = assigned
                print(f"  [bot] {self.name} seated as player {assigned}",
                      flush=True)
        # scheduled chat
        while self.chat_queue:
            self._send(P.make_match_chat(self.chat_queue.pop(0)))
        # submit this tick's intent
        if self.pid is not None:
            (ax, ay), aim, fire, want, sprint = self.bot.think()
            buttons = 0
            # Same low-mag reload as the rendered seats, through the real
            # protocol reload flag (no dry-mag click stretches on tape).
            try:
                sim = self.bot.sim_get()
                me = sim.players.get(self.pid) if sim is not None else None
                if me is not None and not me.get("dead"):
                    mag = AR.weapon_stats(me.get("weapon"))["mag"]
                    if me.get("ammo", mag) <= max(1, mag // 4):
                        buttons |= P.F_RELOAD
                        fire = False
            except Exception:
                pass
            if fire:
                buttons |= P.F_FIRING
            if sprint:
                buttons |= P.F_SPRINTING
            sim = self.bot.sim_get()
            me = sim.players.get(self.pid) if sim is not None else None
            if me is not None:
                aim_deg = math.degrees(math.atan2(aim[1] - me["y"],
                                                  aim[0] - me["x"])) % 360.0
                self._send(P.make_input(self.seq, ax, ay, aim_deg, buttons,
                                        weapon=want))
                self.seq = (self.seq + 1) & 0xFFFFFFFF
        self._flush()


# ── 7. Rendered-seat adapters ──────────────────────────────────────────────
class RenderedSeat:
    """Drives one MatchScreen instance (host or joiner) through its REAL
    per-frame input path: Keys duck-type + (x, y, firing) mouse tuple."""

    def __init__(self, ms: MatchScreen, pid: int, bot: ArenaBot):
        self.ms = ms
        self.pid = pid
        self.bot = bot

    def drive(self):
        (ax, ay), aim, fire, want, sprint = self.bot.think()
        view = self.ms.view
        cam_x = getattr(view, "cam_x", 0.0)
        cam_y = getattr(view, "cam_y", 0.0)
        sx = aim[0] - cam_x
        sy = aim[1] - cam_y
        sx = max(0, min(WIDTH - 1, sx))
        sy = max(0, min(HEIGHT - 1, sy))
        keys = self.bot.axes_to_keys(ax, ay, sprint)
        # one-shot weapon request rides as a key event
        if want is not None and self.ms.session_phase() == "playing" \
                and not self.ms.paused:
            key = {P.WPN_OS12: pygame.K_2, P.WPN_K9: pygame.K_3}.get(want)
            if key is not None:
                self.ms.handle_event(ev_key(key), (sx, sy))
        # Reload on a low mag through the real key path. Without this the
        # bot fires every mag dry and the tape fills with empty clicks
        # instead of gunfire.
        if not fire and self.ms.session_phase() == "playing" \
                and not self.ms.paused:
            try:
                sim = self.bot.sim_get()
                me = sim.players.get(self.pid) if sim is not None else None
                if me is not None and not me.get("dead"):
                    mag = AR.weapon_stats(me.get("weapon"))["mag"]
                    if me.get("ammo", mag) <= max(1, mag // 4):
                        keys.down.add(pygame.K_r)
            except Exception:
                pass
        return keys, (sx, sy, fire)


# ── 7b. PerViewCamera - each rendered surface owns its own camera ───────────
class PerViewCamera:
    """Stash/restore the shared camera state around one MatchScreen's draw.

    ``core.camera.update_camera`` keeps the player-follow position (and the
    recoil kick / screen shake it decays) in single module-level STATE
    fields. That is correct for a real game - one process, one local player -
    and wrong for this tape, which draws BOTH viewpoints here. Without the
    stash, every frame eases the one shared camera toward ANDREI and then
    toward MIRELA, so two roaming seats that are far apart produce one
    thrashing average: neither video tracks its own player and the footage
    reads as a camera pointed at nothing. Each view gets private follow
    state instead, exactly like the two machines a real match runs on.
    """

    _FIELDS = ("camera_x", "camera_y", "camera_initialized",
               "screen_shake", "cam_kick_x", "cam_kick_y")

    def __init__(self, ms: MatchScreen, name: str):
        self.name = name
        self.vals = {"camera_x": 0.0, "camera_y": 0.0,
                     "camera_initialized": False, "screen_shake": 0,
                     "cam_kick_x": 0.0, "cam_kick_y": 0.0}
        orig_draw = ms.draw
        me = self

        def draw(surface, *a, **kw):
            saved = {f: getattr(STATE, f, me.vals[f]) for f in me._FIELDS}
            for f, v in me.vals.items():
                setattr(STATE, f, v)
            try:
                return orig_draw(surface, *a, **kw)
            finally:
                for f in me._FIELDS:
                    me.vals[f] = getattr(STATE, f, me.vals[f])
                for f, v in saved.items():
                    setattr(STATE, f, v)

        ms.draw = draw


# ── 8. Stage - the two-surface frame driver ────────────────────────────────
class Stage:
    def __init__(self, seed=20261004):
        self.rng = random.Random(seed)
        pygame.init()
        pygame.display.set_mode((WIDTH, HEIGHT))
        self.screen = config.screen
        self.client_surf = pygame.Surface((WIDTH, HEIGHT))
        try:
            if hasattr(config, "audio"):
                config.audio.set_master_volume(0)
        except Exception:
            pass

        self.host_ms = MatchScreen()
        self.host_ms.map_name = MAP_NAME
        self.host_ms.mode_name = MODE_NAME
        self.host_ms.players = SEATS
        self.client_ms = MatchScreen()
        self.client_ms.player_name = FRIEND_NAME
        # Private camera per viewpoint; see PerViewCamera.
        self.host_cam = PerViewCamera(self.host_ms, "host")
        self.client_cam = PerViewCamera(self.client_ms, "client")

        self.host_tick = None
        self.client_tick = None
        self.hf = 0            # host frames (60 Hz)
        self.cf = 0            # client frames (60 Hz)
        self.cursor = {"host": (WIDTH // 2, HEIGHT // 2),
                       "client": (WIDTH // 2, HEIGHT // 2)}
        self.hl_bots: list[HeadlessBot] = []
        self.nav = GridNav(AR.ARENAS[MAP_NAME])
        self.foley = Foley()
        self.chapters = Chapters()
        self._sim = lambda: self.host_ms.sim

        # created when the match goes live
        self.host_seat: RenderedSeat | None = None
        self.client_seat: RenderedSeat | None = None
        self.subprocs: list[subprocess.Popen] = []
        # wall-clock pacing anchor (sim time == wall time)
        self._wall = time.monotonic()

    # -- cursor ----------------------------------------------------------------
    # Replicates app.py's rule: the arrow shows on the panel, in the frozen
    # lobby (COPY CODE must stay targetable) and on pause - never over a live
    # match, where the arena already draws the combat reticle and a second
    # pointer would stack on top of it. Without this the tape shows invisible
    # clicks: MatchScreen draws no cursor itself, the real game adds it in
    # the main loop (app.py), and the capture bypasses that loop.
    def _arrow_for(self, ms) -> bool:
        try:
            if not ms.is_open():
                return False
            if ms.mode == "panel":
                return True
            if ms.mode in ("hosting", "playing") and (
                    getattr(ms, "paused", False) or ms.waiting_for_player()):
                return True
        except Exception:
            return False
        return False

    def _draw_arrow(self, surface) -> None:
        try:
            # state_name MUST be passed: the default path imports app.py,
            # whose module body IS the game's main loop.
            menu.draw_menu_cursor(surface, "MULTIPLAYER")
        except Exception:
            pass

    # -- frames -------------------------------------------------------------
    def frame(self, host_in=None, client_in=None, feed_host=True,
              feed_client=False, host_draw=None, client_cursor=False):
        """Advance one 60 Hz frame: headless bots, then host, then client."""
        for b in self.hl_bots:
            b.pump()
        self.foley.install(self.host_ms)

        # Default the pointer to the last glided position. Parking it in the
        # corner made the hosting tutorial look click-driven with no cursor:
        # MatchScreen draws no pointer, and draw_menu_cursor reads pygame's
        # mouse, which this loop is the only thing that sets.
        if host_in is None:
            hx, hy = self.cursor["host"]
            host_in = (IDLE_KEYS, (hx, hy, False))
        keys, mouse = host_in
        mset(mouse[0], mouse[1])
        self.host_ms.update(keys, mouse, DT)
        if host_draw is not None:
            host_draw()
        else:
            self.host_ms.draw(self.screen)
            if self._arrow_for(self.host_ms):
                self._draw_arrow(self.screen)
        if feed_host and self.host_tick is not None and self.hf % 2 == 1:
            self.host_tick.feed(self.screen)
        self.hf += 1

        # client surface
        if self.client_ms.is_open():
            if client_in is None:
                cx, cy = self.cursor["client"]
                client_in = (IDLE_KEYS, (cx, cy, False))
            ckeys, cmouse = client_in
            mset(cmouse[0], cmouse[1])
            self.client_ms.update(ckeys, cmouse, DT)
            self.client_ms.draw(self.client_surf)
            if client_cursor or self._arrow_for(self.client_ms):
                self._draw_arrow(self.client_surf)
            if feed_client and self.client_tick is not None \
                    and self.cf % 2 == 1:
                self.client_tick.feed(self.client_surf)
            self.cf += 1
        pygame.event.pump()
        # Real-time pacing. The match is full of wall-clock cadences (roster
        # publish every 0.15 s, forwarding probes, peer timeouts), so the
        # frame loop must track wall time, not run flat out.
        now = time.monotonic()
        budget = self._wall + DT
        if now < budget:
            time.sleep(budget - now)
        self._wall = max(budget, now)

    def run(self, n, **kw):
        for _ in range(n):
            self.frame(**kw)

    def wait_until(self, fn, timeout_frames, **kw):
        i = 0
        while i < timeout_frames:
            if fn():
                return True
            self.frame(**kw)
            i += 1
        return False

    # -- cursor helpers -----------------------------------------------------
    def glide(self, surface, target, frames, **kw):
        """Ease the cursor to target over N frames (feeds the active surface)."""
        x0, y0 = self.cursor[surface]
        x1, y1 = target
        for i in range(frames):
            t = (i + 1) / frames
            e = t * t * (3 - 2 * t)      # smoothstep
            x = x0 + (x1 - x0) * e
            y = y0 + (y1 - y0) * e
            self.cursor[surface] = (x, y)
            if surface == "host":
                self.frame(host_in=(IDLE_KEYS, (x, y, False)),
                           host_draw=kw.get("host_draw"),
                           feed_host=kw.get("feed_host", True),
                           feed_client=kw.get("feed_client", False))
            else:
                self.frame(host_in=kw.pop("host_in", None),
                           client_in=(IDLE_KEYS, (x, y, False)),
                           feed_host=kw.get("feed_host", True),
                           feed_client=kw.get("feed_client", True),
                           client_cursor=True)
        self.cursor[surface] = (float(x1), float(y1))

    def click(self, surface, pos=None):
        pos = pos or self.cursor[surface]
        if surface == "host":
            self.host_ms.handle_event(ev_click(pos), (pos[0], pos[1]))
        else:
            self.client_ms.handle_event(ev_click(pos), (pos[0], pos[1]))

    def hold(self, frames, surface="host", **kw):
        if surface == "host":
            self.run(frames, **kw)
        else:
            self.run(frames, **kw)

    def type_text(self, surface, text, per_char=3, key_handler=None):
        ms = self.host_ms if surface == "host" else self.client_ms
        for ch in text:
            ms.handle_event(ev_key(0, ch), self.cursor[surface])
            self.run(per_char)
        ms.handle_event(ev_key(pygame.K_RETURN), self.cursor[surface])


# ── 9. Beat phases ──────────────────────────────────────────────────────────
def phase_browser(st: Stage, chapters: Chapters):
    """MULTIPLAYER browser with a REAL hosted lobby visible, then the
    ARENA MATCH button. Falls back to opening the panel directly."""
    print("[phase] browser", flush=True)
    proc = None
    try:
        proc = subprocess.Popen(
            [sys.executable, str(ROOT / "tools" / "mp_host.py"),
             "--name", "Biribel's Backyard Brawl", "--no-forward"],
            cwd=str(ROOT), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        st.subprocs.append(proc)
        time.sleep(1.2)
        menu_mp.relay_start(nick=HOST_NAME)
        time.sleep(1.6)

        def draw_browser():
            menu_mp.update_server_browser_animation()
            menu_mp.draw_server_browser(-1, False, "", 0.0)
            try:
                menu.draw_menu_cursor(st.screen, "MULTIPLAYER")
            except Exception:
                pass

        st.run(30, host_draw=draw_browser)
        chapters.mark("browser_open", st.hf, st.hf / SIM_HZ)
        r = menu_mp.enter_arena_rect()
        st.glide("host", r.center, 26, host_draw=draw_browser)
        st.run(6, host_draw=draw_browser)
        if menu_mp.enter_arena_hit(r.center):
            st.host_ms.open_panel()
        st.run(16, host_draw=draw_browser)
        chapters.mark("panel_open", st.hf, st.hf / SIM_HZ)
    except Exception as exc:
        print(f"  [browser] FAILED ({exc!r}) - opening panel directly",
              flush=True)
        if not st.host_ms.is_open():
            st.host_ms.open_panel()
    finally:
        try:
            menu_mp.relay_stop()
        except Exception:
            pass
        if proc is not None:
            proc.terminate()


def phase_panel(st: Stage, chapters: Chapters):
    """Pick TDM / foundry / 4 seats, type the callsign, click HOST MATCH."""
    print("[phase] panel", flush=True)
    # one draw to materialise the rects
    st.frame()
    ms = st.host_ms
    rects_ready = getattr(ms, "_btn_rects", None)
    assert rects_ready, "panel rects not built"

    st.glide("host", ms._mode_rects[0].center, 16)
    st.run(5)
    st.click("host")
    st.run(9)

    st.glide("host", ms._map_rects[1].center, 14)     # foundry (maps() is alphabetical)
    st.run(4)
    st.click("host")
    st.run(9)

    st.glide("host", ms._pl_rects[SEATS].center, 12)
    st.run(4)
    st.click("host")
    st.run(9)

    st.glide("host", ms._name_rect.center, 12)
    st.run(3)
    st.click("host")
    st.run(6)
    # clear whatever minted callsign is in the box, type ours
    for _ in range(14):
        ms.handle_event(ev_key(pygame.K_BACKSPACE), st.cursor["host"])
    st.run(6)
    for ch in HOST_NAME:
        ms.handle_event(ev_key(0, ch), st.cursor["host"])
        st.run(4)
    ms.handle_event(ev_key(pygame.K_RETURN), st.cursor["host"])
    st.run(10)
    chapters.mark("callsign_typed", st.hf, st.hf / SIM_HZ)

    st.glide("host", ms._btn_rects[1].center, 16)     # HOST MATCH
    st.run(5)
    st.click("host")
    st.run(8)
    chapters.mark("host_clicked", st.hf, st.hf / SIM_HZ)

    ok = st.wait_until(lambda: ms.mode == "hosting", 240)
    if not ok:
        raise RuntimeError(f"hosting never started (mode={ms.mode}, "
                           f"status={ms.status!r})")
    print(f"  hosting: {ms.status!r} port {ms.share_port}", flush=True)
    # room code settles in the background (UPnP probe, no tunnels here)
    ok = st.wait_until(lambda: ms.room_code_ready(), 900)
    print(f"  room code: {ms.room_code!r} ready={ok} "
          f"note={ms.forward_note[:60]!r}", flush=True)
    chapters.mark("code_ready", st.hf, st.hf / SIM_HZ)
    st.frame()
    copy_r = getattr(ms, "_wait_rects", {}).get("copy")
    if copy_r is not None:
        st.glide("host", copy_r.center, 18)
        st.run(16)
        st.click("host")
        st.run(28)
    else:
        st.run(45)
    return ms.room_code


def phase_lobby(st: Stage, chapters: Chapters, code: str):
    """Joiners arrive; the friend types the code on their own screen."""
    print("[phase] lobby", flush=True)
    ms, cms = st.host_ms, st.client_ms
    port = ms.share_port

    # 1) first stranger
    b1 = HeadlessBot(BOT_NAMES[0], "127.0.0.1", port,
                     ArenaBot(None, st.nav, st._sim, random.Random(11)))
    if not b1.connect():
        raise RuntimeError("BIRIBEL could not connect")
    st.hl_bots.append(b1)
    ok = st.wait_until(lambda: len(ms.peers) == 1, 300)
    print(f"  peers={len(ms.peers)} ok={ok}", flush=True)
    st.run(30)
    chapters.mark("roster_2", st.hf, st.hf / SIM_HZ)
    b1.say("ready when you are")
    st.run(50)

    # 2) the friend (second rendered surface starts recording HERE)
    st.client_tick = Ticker(ffmpeg_exe(), CLIENT_MP4)
    cms.open_panel()
    st.frame()                                     # build client panel rects
    st.glide("client", cms._addr_rect.center, 14, feed_client=True)
    st.run(4, feed_client=True, client_cursor=True)
    st.click("client")
    st.run(6, feed_client=True, client_cursor=True)
    chapters.mark("client_addr_focus", st.cf, st.cf / SIM_HZ)
    for ch in code:
        cms.handle_event(ev_key(0, ch), st.cursor["client"])
        st.run(3, feed_client=True)
    chapters.mark("client_code_typed", st.cf, st.cf / SIM_HZ)
    st.run(8, feed_client=True, client_cursor=True)
    cms.handle_event(ev_key(pygame.K_RETURN), st.cursor["client"])
    chapters.mark("join_clicked", st.cf, st.cf / SIM_HZ)
    ok = st.wait_until(
        lambda: cms.mode == "playing" and cms.sess is not None
        and cms.sess.local_id not in (None, 0), 600, feed_client=True)
    print(f"  friend seated={ok} local_id={cms.sess.local_id if cms.sess else None}",
          flush=True)
    ok2 = st.wait_until(lambda: len(ms.peers) == 2, 300, feed_client=True)
    print(f"  peers={len(ms.peers)} ok={ok2}", flush=True)
    st.run(55, feed_client=True, client_cursor=True)
    chapters.mark("client_connected", st.cf, st.cf / SIM_HZ)

    # 3) last stranger fills the room
    b2 = HeadlessBot(BOT_NAMES[1], "127.0.0.1", port,
                     ArenaBot(None, st.nav, st._sim, random.Random(77)))
    if not b2.connect():
        raise RuntimeError("MICUL FUEGO could not connect")
    st.hl_bots.append(b2)
    st.wait_until(lambda: len(ms.peers) == 3, 300, feed_client=True)
    print(f"  peers={len(ms.peers)} (room full)", flush=True)
    st.run(70, feed_client=True)
    chapters.mark("roster_full", st.hf, st.hf / SIM_HZ)
    st.run(40, feed_client=True)


def phase_countdown(st: Stage, chapters: Chapters):
    """START MATCH -> synchronized 3 / 2 / 1 / GO on every screen."""
    print("[phase] countdown", flush=True)
    ms = st.host_ms
    st.frame(feed_client=True)
    start_r = ms._lobby_rects.get("start")
    if start_r is None:
        raise RuntimeError("START MATCH button not available "
                           f"(peers={len(ms.peers)})")
    st.glide("host", start_r.center, 16, feed_client=True)
    st.run(5, feed_client=True)
    st.click("host")
    chapters.mark("start_clicked", st.hf, st.hf / SIM_HZ)
    ok = st.wait_until(lambda: ms._session_phase == "playing", 420,
                       feed_client=True)
    if not ok:
        raise RuntimeError("countdown never reached playing")
    chapters.mark("go_moment", st.hf, st.hf / SIM_HZ)
    chapters.mark("go_moment_client", st.cf, st.cf / SIM_HZ)
    print(f"  GO at host {st.hf / SIM_HZ:.2f}s client {st.cf / SIM_HZ:.2f}s",
          flush=True)
    st.run(36, feed_client=True)


def _finish_natural_round(ms):
    """Publish a round that the real arena rules have already decided.

    Never manufacture a winner or pad kill counts for announcement footage;
    a round-over panel is only used if the sim reached the actual score limit.
    """
    sim = getattr(ms, "sim", None)
    if sim is None:
        return False
    rules = getattr(sim, "rules", None)
    if rules is None or rules.winner is None:
        return False
    if getattr(rules, "phase", "") == "live":
        rules.start_intermission(getattr(sim, "tick", 0))
    sim.finished = True
    try:
        state = sim.match_state()
        state["scoreboard"] = sim.scoreboard()
        ms._match_state = state
    except Exception:
        pass
    return True


def _tc(col, row):
    return (col * T + T // 2, row * T + T // 2)


# ── 5c. The foundry staging ─────────────────────────────────────────────────
# Geometry facts this staging is built on, all verified against the real
# AR.hitscan in tools/mp_lane_probe.py rather than eyeballed:
#
#  * Row 7 is the only long east-west sightline on the map. It is open from
#    col 1 to col 22, so four players strung along it can all see each other.
#  * In TEAM_DEATHMATCH a ray stops at the NEAREST body and a teammate in the
# The new fight tableau uses two separated vertical sightlines, not four
# silhouettes parked on one horizontal rail. Each opposing pair can see one
# another down a clear foundry corridor; the pairs are framed close enough to
# remain in either rendered player's camera, while their lateral footwork
# gives the match a readable push / evade / re-engage rhythm.
FOUNDRY_POSTS = {
    "MIRELA": (13, 6),
    "BIRIBEL": (13, 10),
    "MICUL": (17, 6),
    "ANDREI": (17, 10),
}
FOUNDRY_TARGET = {
    "MIRELA": ("vs", "BIRIBEL"), "BIRIBEL": ("vs", "MIRELA"),
    "MICUL": ("vs", "ANDREI"), "ANDREI": ("vs", "MICUL"),
}
FOUNDRY_GAP = {
    "MIRELA": (22, 42), "BIRIBEL": (18, 38),
    "MICUL": (24, 46), "ANDREI": (20, 40),
}


def seat_key(nick):
    """Map a live callsign onto a post/script key."""
    n = (nick or "").strip()
    if n in FOUNDRY_POSTS:
        return n
    head = n.split()[0] if n else ""
    return head if head in FOUNDRY_POSTS else None


def foundry_scripts():
    """Author a 2v2 duel tableau with separate lanes and active footwork.

    MIRELA/BIRIBEL contest the western central lane; MICUL/ANDREI contest
    the eastern one. The pairings have verified clear hitscan lines, and the
    two lanes fit inside each local player's view. Each fighter trades bursts
    from a starting post, then shifts laterally across a three-tile pocket
    before re-engaging. Different route order and dwell times keep the four
    players from moving or firing like synchronized targets.
    """
    def fighter(home, opening, steps, foe, gap, dwell, lead_cycle,
                intro_wait=0):
        tap = {"aim": foe, "do": "tap", "gap": gap,
               "n": 1, "jitter": 8.0}
        route = []
        if intro_wait:
            route.append(dict(aim=foe, do="hold", hold=intro_wait,
                              initial_only=True))
        route.extend([
            dict(to=_tc(*opening), aim=foe, do="move"),
            dict(tap, lead_cycle=lead_cycle, hold=dwell),
        ])
        for i, tile in enumerate(steps):
            route.append(dict(to=_tc(*tile), aim=foe, do="move"))
            route.append(dict(tap, hold=dwell + (10 if i % 2 == 0 else 0)))
        route.append(dict(to=_tc(*home), aim=foe, do="move"))
        route.append(dict(tap, hold=2600))
        return route

    scripts = {
        # West lane: step into the light, cut outward, then recoil to cover.
        "MIRELA": fighter(FOUNDRY_POSTS["MIRELA"], (14, 7),
                          ((15, 7), (14, 6)), FOUNDRY_TARGET["MIRELA"],
                          FOUNDRY_GAP["MIRELA"], 24, (0, 8)),
        "BIRIBEL": fighter(FOUNDRY_POSTS["BIRIBEL"], (14, 9),
                           ((15, 9), (14, 10)), FOUNDRY_TARGET["BIRIBEL"],
                           FOUNDRY_GAP["BIRIBEL"], 32, (8, 0)),
        # East lane: its own duel starts half a beat later.
        "MICUL": fighter(FOUNDRY_POSTS["MICUL"], (18, 7),
                         ((19, 7), (18, 6)), FOUNDRY_TARGET["MICUL"],
                         FOUNDRY_GAP["MICUL"], 30, (0, 8), intro_wait=42),
        "ANDREI": fighter(FOUNDRY_POSTS["ANDREI"], (18, 9),
                          ((19, 9), (18, 10)), FOUNDRY_TARGET["ANDREI"],
                          FOUNDRY_GAP["ANDREI"], 38, (8, 0), intro_wait=42),
    }
    # On respawn, ScriptDriver returns each seat to its post and replays the
    # movement route. The cinematic opening hold is first-life only, while the
    # real respawn-protection timestamp is left intact.
    return {nick: (spec, 0) for nick, spec in scripts.items()}


def phase_combat(st: Stage, chapters: Chapters, seconds=60.0):
    """Free-roam 2v2. Every seat is an ArenaBot driver through its REAL
    input path (rendered seats via keys+mouse, headless peers via `in`
    packets) - no posts, no waypoint scripts, no teleports. The four bots
    roam, hunt, strafe, grab pickups and fight wherever the round takes
    them; the assembler cuts its montage around whatever kills the foley
    log records, so the tape is pure emergent play."""
    print("[phase] combat", flush=True)
    ms, cms = st.host_ms, st.client_ms
    client_pid = cms.sess.local_id

    sim = ms.sim
    if sim is None:
        raise RuntimeError("combat phase entered with no live sim")
    nick_of = {pid: p.get("nick") or "" for pid, p in sim.players.items()}
    print("  seats: " + "  ".join(f"{n or p}={p}"
                                  for p, n in sorted(nick_of.items())),
          flush=True)

    # All four seats roam. The headless peers already hold ArenaBot drivers
    # from phase_lobby and only need their seat pid filled in; the two
    # rendered seats get fresh ArenaBots with their own seeds so no two
    # seats think alike. Nobody is teleported: everyone fights from the
    # spawn the sim actually gave them.
    for b in st.hl_bots:
        b.bot.pid = b.pid
    st.host_seat = RenderedSeat(
        ms, 0, ArenaBot(0, st.nav, st._sim, random.Random(2026)))
    st.client_seat = RenderedSeat(
        cms, client_pid,
        ArenaBot(client_pid, st.nav, st._sim, random.Random(4242)))

    total = int(seconds * SIM_HZ)
    win_hold = int(3.4 * SIM_HZ)
    won = False
    won_ticks = 0
    combat_log = []                       # diagnostic: per-second world state
    for i in range(total):
        # Trailer safety net for the two RENDERED seats: never let the tape
        # rest on an ELIMINATED plate while the seat is out of contact. The
        # old version topped up unconditionally EVERY tick, which against a
        # 34-damage pistol made both IPA seats effectively immortal - the
        # debug log shows ANDREI pinned at hp=100 for the whole round - and
        # that is precisely why KRAP finished on zero kills. So the refill
        # now stands down the moment somebody is actually shooting at the
        # seat: chip damage stays on the HUD while a seat walks in, and a
        # contested seat fights on its real HP like everyone else.
        try:
            sim = ms.sim
            if sim is not None:
                for _pid in (0, client_pid):
                    _p = sim.players.get(_pid)
                    if _p is None or _p.get("dead"):
                        continue
                    if _p.get("hp", AR.MAX_HP) >= 25:
                        continue
                    _contested = any(
                        math.hypot(q["x"] - _p["x"], q["y"] - _p["y"]) < 900
                        and q.get("team") != _p.get("team")
                        for qid, q in sim.players.items()
                        if qid != _pid and not q["dead"])
                    if not _contested:
                        _p["hp"] = AR.MAX_HP
        except Exception:
            pass
        if i % SIM_HZ == 0:
            sim = st._sim() if callable(st._sim) else st._sim
            if sim is not None:
                snap = {"i": i, "tick": sim.tick, "p": [], "bots": [],
                        "inputs": []}
                try:
                    sess = st.host_ms.sess
                    for pid in sorted(sess._inputs):
                        hist = sess._inputs.get(pid) or {}
                        if hist:
                            nw = hist[max(hist)]
                            snap["inputs"].append(
                                dict(pid=pid, seq=max(hist),
                                     mx=nw.get("mx"), my=nw.get("my"),
                                     b=nw.get("b"), n=len(hist)))
                except Exception as exc:
                    snap["inputs"] = [dict(err=str(exc))]
                for seat_name, seat in (("host", st.host_seat),
                                         ("client", st.client_seat)):
                    if seat is None:
                        continue
                    b = seat.bot
                    snap["bots"].append(dict(
                        seat=seat_name, pid=getattr(b, "pid", None),
                        wp=getattr(b, "wp", None),
                        path=len(getattr(b, "path", []) or []),
                        stuck=getattr(b, "_stuck", 0)))
                for pid, p in sorted(sim.players.items()):
                    foes = [(q["x"], q["y"]) for qid, q in sim.players.items()
                            if qid != pid and not q["dead"]
                            and q.get("team") != p.get("team")]
                    los = False
                    for fx, fy in foes:
                        ang = math.degrees(math.atan2(fy - p["y"],
                                                      fx - p["x"])) % 360.0
                        k, _tid, _d = AR.hitscan(
                            p["x"], p["y"], ang, sim.walls,
                            [(qid, q["x"], q["y"]) for qid, q
                             in sim.players.items() if qid != pid],
                            range_px=520)
                        if k == "player" and _tid in [
                                qid for qid, q in sim.players.items()
                                if qid != pid and q.get("team") != p.get("team")]:
                            los = True
                            break
                    snap["p"].append(dict(id=pid, nick=p.get("nick"),
                                          x=round(p["x"]), y=round(p["y"]),
                                          hp=p["hp"], dead=p["dead"],
                                          team=p.get("team"), los=los))
                combat_log.append(snap)
        # Only use the round-over panel if the real TDM score limit decided
        # the round. Otherwise the cut stays in live play and uses the actual
        # kill log; no synthetic winner or scoreboard padding is introduced.
        if not won:
            _s = ms.sim
            _rules = getattr(_s, "rules", None) if _s is not None else None
            if _rules is not None and _rules.winner is not None:
                _finish_natural_round(ms)
                won = True
                chapters.mark("round_over", st.hf, st.hf / SIM_HZ)
        if won:
            st.frame(host_in=(IDLE_KEYS, (*st.cursor["host"], False)),
                     client_in=(IDLE_KEYS, (*st.cursor["client"], False)),
                     feed_client=True)
            won_ticks += 1
            if won_ticks >= win_hold:
                break
        else:
            st.frame(host_in=st.host_seat.drive(),
                     client_in=st.client_seat.drive(), feed_client=True)
    chapters.mark("combat_end", st.hf, st.hf / SIM_HZ)
    chapters.mark("combat_end_client", st.cf, st.cf / SIM_HZ)
    (OUT_DIR / "combat_debug.json").write_text(
        json.dumps(combat_log, indent=1), encoding="utf-8")
    print(f"  [debug] combat_log -> combat_debug.json ({len(combat_log)} snaps)",
          flush=True)


# ── 10. main ────────────────────────────────────────────────────────────────
def main() -> int:
    ap = argparse.ArgumentParser(description="Capture real MP arena footage")
    ap.add_argument("--no-browser", action="store_true")
    ap.add_argument("--combat-seconds", type=float, default=60.0)
    ap.add_argument("--seed", type=int, default=20261004)
    args = ap.parse_args()

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    _init_wpn_names()
    st = Stage(seed=args.seed)
    chapters = st.chapters
    t0 = time.time()

    st.host_tick = Ticker(ffmpeg_exe(), HOST_MP4)

    if not args.no_browser:
        phase_browser(st, chapters)
    else:
        st.host_ms.open_panel()
        chapters.mark("panel_open", st.hf, st.hf / SIM_HZ)

    code = phase_panel(st, chapters)
    phase_lobby(st, chapters, code)
    phase_countdown(st, chapters)
    phase_combat(st, chapters, seconds=args.combat_seconds)

    # Read actual kill events and the final scoreboard BEFORE teardown drops
    # the sim. The cinematic round-close margin is tracked separately.
    kills = {}
    scoreboard_kills = {}
    score_adjustments = {}
    nick_by_pid = {}
    try:
        sim = st.host_ms.sim
        if sim is not None:
            for pid, p in sim.players.items():
                nick = p.get("nick") or str(pid)
                nick_by_pid[pid] = nick
                scoreboard_kills[nick] = sim.rules.kills.get(pid, 0)
                kills[nick] = 0
                score_adjustments[nick] = 0
    except Exception:
        pass
    # Which pid the client tape's camera follows (the assembler needs it to
    # know which kills are visible on the joiner's screen).
    client_pid = 0
    try:
        if st.client_ms.sess is not None:
            client_pid = int(st.client_ms.sess.local_id or 0)
    except Exception:
        pass
    for ev in st.foley.events:
        if ev.get("kind") == "kill":
            nick = nick_by_pid.get(ev.get("killer"), str(ev.get("killer")))
            kills[nick] = kills.get(nick, 0) + 1
        elif ev.get("kind") == "score_adjustment":
            nick = nick_by_pid.get(ev.get("player"), str(ev.get("player")))
            score_adjustments[nick] = (
                score_adjustments.get(nick, 0) + int(ev.get("amount", 0)))

    # teardown
    err_h = st.host_tick.close()
    err_c = st.client_tick.close() if st.client_tick else ""
    try:
        st.host_ms.close()
    except Exception:
        pass
    try:
        st.client_ms.close()
    except Exception:
        pass
    for p in st.subprocs:
        try:
            p.terminate()
        except Exception:
            pass

    chapters.save(OUT_DIR / "chapters.json")
    st.foley.save(OUT_DIR / "host_flow.foley.json", dict(
        map=MAP_NAME, mode=MODE_NAME, code=code, client_pid=client_pid,
        names=[HOST_NAME, FRIEND_NAME] + list(BOT_NAMES)))
    report = dict(
        wall_sec=round(time.time() - t0, 1),
        host_frames=st.host_tick.frames,
        host_seconds=round(st.host_tick.frames / FPS, 2),
        client_frames=st.client_tick.frames if st.client_tick else 0,
        client_seconds=round((st.client_tick.frames if st.client_tick else 0) / FPS, 2),
        room_code=code,
        client_pid=client_pid,
        kills=kills,
        scoreboard_kills=scoreboard_kills,
        score_adjustments=score_adjustments,
        host_err=err_h, client_err=err_c,
        host_liveness=st.host_tick.changed_ratio,
        host_luma=st.host_tick.mean_luma,
        chapters=chapters.marks,
    )
    (OUT_DIR / "report.json").write_text(json.dumps(report, indent=1),
                                         encoding="utf-8")
    print("-" * 64)
    for k, v in report.items():
        print(f"  {k:<18} {v}")
    ok = (not err_h and not err_c and st.host_tick.frames > 600
          and sum(kills.values()) >= 3)
    print("CAPTURE:", "OK" if ok else "CHECK REPORT")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())

