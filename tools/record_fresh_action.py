#!/usr/bin/env python3
"""record_fresh_action.py - clean standalone combat capture.

Boots three real combat checkpoints, strips debug/UI clutter, drives a
seek-and-fight bot, and pipes raw frames straight to ffmpeg.

    python tools/record_fresh_action.py                  # all 3 acts, 10s each
    python tools/record_fresh_action.py --act 2 --seconds 5
    python tools/record_fresh_action.py --hud bare --merge
    python tools/record_fresh_action.py --list

Design notes (see docs/AUDIT_T8_STANDALONE_PLAN.md for the full blueprint):

  * No source file is edited. Nothing under src/ is imported except the
    mission layer; `app` is deliberately NOT imported, so the level editor,
    dev console, crosshair, menu cursor and FSM fade overlay are structurally
    absent rather than flag-gated.
  * Aim is driven through the real input path (`pygame.mouse.set_pos`)
    because every mission recomputes STATE.player.angle from the mouse
    inside game_update. Setting player.angle directly -- as every legacy bot
    does -- is silently overwritten before the frame is rendered.
  * Video duration is frame-count driven (60 sim ticks in, 30 frames out), so
    the clip is exactly `--seconds` long regardless of machine speed.
  * A separate ffmpeg process per act: a failure in Act II must not cost
    Acts I and III.

Outputs: <out-dir>/act<N>.mp4 plus <out-dir>/report.json. Exit code is 0 when
every requested act passed verification, 1 on act failure, 2 on preflight
failure.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import random
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

# ── 0. PREFLIGHT ────────────────────────────────────────────────────────────
# core.config.resource_path() falls back to os.path.abspath("."), so the CWD
# decides where fonts/art are found. Fix it before anything imports config.
ROOT = Path(__file__).resolve().parent.parent
os.chdir(ROOT)

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
sys.path.insert(0, str(ROOT / "src"))

# Sandbox the save/settings stores. missions.m1.main.start_mission calls
# save_system.set_slot_progress("m1"), which writes save_data.json for real.
_SCRATCH = Path(tempfile.mkdtemp(prefix="fresh_action_"))
from core import save_system as _sv  # noqa: E402
from core import settings_store as _st  # noqa: E402

_sv.SAVE_FILE = str(_SCRATCH / "save_data.json")
_st.SAVE_FILE = str(_SCRATCH / "settings.json")

import pygame  # noqa: E402

from core import config  # noqa: E402
from core import game_core as gc  # noqa: E402
from core import interactions  # noqa: E402
from core.config import TILE_SIZE as T  # noqa: E402
from core.state import STATE  # noqa: E402
from core.user_settings import SETTINGS  # noqa: E402
from entities import weapons  # noqa: E402
from entities.enemy_ai import _astar  # noqa: E402
from ui import hud as _hud  # noqa: E402

WIDTH, HEIGHT = config.WIDTH, config.HEIGHT
FPS = 30
SIM_HZ = 60
DEFAULT_SECONDS = 10.0


def ffmpeg_exe() -> str:
    """Resolve ffmpeg. imageio_ffmpeg is a last resort -- it is not a declared
    dependency (pyproject.toml lists only numpy/pygame-ce/setuptools)."""
    for cand in (os.environ.get("FFMPEG"), shutil.which("ffmpeg"),
                 r"C:\ffmpeg\bin\ffmpeg.exe"):
        if cand and Path(str(cand)).exists():
            return str(cand)
    try:
        import imageio_ffmpeg
        return str(imageio_ffmpeg.get_ffmpeg_exe())
    except Exception:
        pass
    raise SystemExit(
        "ffmpeg not found. Put it on PATH, set $FFMPEG, or install "
        "C:\\ffmpeg\\bin\\ffmpeg.exe")


def ffprobe_exe(ffmpeg: str) -> str | None:
    cand = shutil.which("ffprobe")
    if cand:
        return cand
    guess = Path(ffmpeg).with_name(
        "ffprobe.exe" if str(ffmpeg).lower().endswith(".exe") else "ffprobe")
    return str(guess) if guess.exists() else None


# ── Checkpoint table ────────────────────────────────────────────────────────
# Chosen for "combat is LIVE at t=0 with the right weapon in hand": no
# cutscene to skip, no objective to click, no staging flags to fake.
#
# Deliberately NOT used:
#   start_mission2()          -- spawns ZERO enemies; first team is ~3510px
#                                 (~12s) away. Worst dead-walk in the codebase.
#   start_mission3_breakout_* -- disarms the player behind an 8-stroke whittle
#                                 minigame the bot cannot perform.
def _act_table():
    from missions.m1.map import mission1_map
    from missions.m2.world import MISSION2_MAP
    from missions.m3 import maps as m3maps
    return [
        dict(n=1, key="act1", label="ACT I - BLACK NOTEBOOK",
             starter="gc.start_mission(preserve_timer=True)", cli="--dev-m1",
             boot=lambda: gc.start_mission(preserve_timer=True),
             tmap=mission1_map, solids=("C", "W")),
        dict(n=2, key="act2", label="ACT II - QUIET ON ROUTE 12",
             starter="gc.start_mission2_after_sniper(preserve_timer=True)",
             cli="--dev-mission2-after-sniper",
             boot=lambda: gc.start_mission2_after_sniper(preserve_timer=True),
             tmap=MISSION2_MAP, solids=("C", "B", "T")),
        dict(n=3, key="act3", label="ACT III - THE VOSTRAL",
             starter="gc.start_mission3_archives_checkpoint(preserve_timer=True)",
             cli="--dev-mission3-archives",
             boot=lambda: gc.start_mission3_archives_checkpoint(preserve_timer=True),
             tmap=m3maps.MISSION3_ARCHIVES_MAP, solids=("C", "B", "S")),
    ]


# ── 1. Ticker ───────────────────────────────────────────────────────────────
class Ticker:
    """One ffmpeg rawvideo pipe. stdio back-pressure is the intended throttle;
    the resulting clip length is frame-count driven, not wall-clock driven."""

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

    def feed(self, sample_every: int = 30) -> None:
        self.proc.stdin.write(pygame.image.tobytes(config.screen, "RGB"))
        self.frames += 1
        if self.frames % sample_every:
            return
        # Liveness probe: a downscaled RGB signature per sample. A dark game
        # has a narrow mean-luma range, so "is it animating" must be answered by
        # frame-to-frame delta, not by absolute brightness.
        self._samples += 1
        small = pygame.transform.smoothscale(config.screen, (40, 28))
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
    def unique_frames(self) -> int:
        return len(self._sigs)

    @property
    def changed_ratio(self) -> float:
        return round(self._changed / self._samples, 2) if self._samples else 0.0

    @property
    def mean_luma(self) -> float:
        return round(sum(self._lum) / len(self._lum), 2) if self._lum else 0.0


# ── 2. HudPolicy ────────────────────────────────────────────────────────────
# Taxonomy: the engine has NO debug labels or FPS overlay (grep-verified), so
# "debug labels" means the scaffolding the legacy trailer scripts drew
# themselves -- which this script simply never draws. What remains is real UI.
#
#   clean (default) remove every overlay, keep gameplay panels
#   bare            also remove the bottom-left HUD cluster
#   full            zero patching (A/B escape hatch)
#
# `bare` uses an adjacent-strip mirror: blit a HUD-free region of the same
# frame over the HUD cluster. A flat plate was measured and rejected -- bright
# green HUD text ghosts through at 5% alpha and reads as a bug.
BARE_RECTS = [
    # (destination, mirror-source)  -- covers M1/M2/M3 ammo+HP+molotov stack
    ((18, 500, 310, 180), (328, 500, 310, 180)),
    # HOSTILES chip, identical in all three missions: bg (20,20,180,26)
    ((18, 18, 190, 32), (208, 18, 190, 32)),
    # M2-only COMMS status, bottom-right
    ((846, 652, 150, 32), (536, 652, 150, 32)),
]

_orig_hud_fns: dict[str, object] = {}


def _rebind_everywhere(name: str, replacer) -> int:
    """Rebind `name` on every module that holds a reference to the original.

    Patching ui.hud alone does nothing: every mission part module did
    `from ui.hud import draw_objective_panel` at import time, binding the
    original function into its own globals -- and the three missions call it
    from three DIFFERENT modules. Sweeping sys.modules is order-independent
    and needs no module list to maintain.
    """
    orig = _orig_hud_fns.get(name)
    n = 0
    for mod in list(sys.modules.values()):
        if mod is not None and getattr(mod, name, None) is orig:
            setattr(mod, name, replacer)
            n += 1
    return n


def apply_hud_policy(policy: str) -> None:
    if policy == "full":
        return
    global _orig_hud_fns
    if not _orig_hud_fns:
        _orig_hud_fns = {
            "draw_objective_panel": _hud.draw_objective_panel,
            "draw_pinned_radio": _hud.draw_pinned_radio,
        }
    _rebind_everywhere("draw_objective_panel", _noop)
    _rebind_everywhere("draw_pinned_radio", _noop)
    # Mission 3's in-world objective nav arrow + label.
    try:
        import missions.m3.draw as m3_draw
        m3_draw._draw_objective_waypoint = _noop
    except Exception:
        pass
    if policy == "bare":
        # Belt-and-braces second layer: M2/M3 consolidate their HUD into one
        # function. M1 does not (its HUD is inline in _game_draw_inner), which
        # is exactly why the mirror-strip above is the uniform code path.
        for modname, attr in (("missions.m2.draw", "_draw_hud"),
                              ("missions.m3.systems", "_draw_mission3_hud")):
            try:
                import importlib
                setattr(importlib.import_module(modname), attr, _noop)
            except Exception:
                pass


def _noop(*a, **k):
    return None


def strip_after_boot() -> None:
    """Re-apply the per-frame-visible switches. start_mission* sets
    show_minimap back to True, so this MUST run after every boot."""
    STATE.show_minimap = False
    interactions.clear_radio_queue()
    # Kills the static startup hint text, e.g. "[G] or RIGHT-CLICK to throw a
    # molotov" (m1/main.py:136). Transient world texts still appear later.
    STATE.floating_texts.clear()


def apply_bare_mask() -> None:
    for dest, src in BARE_RECTS:
        config.screen.blit(config.screen, dest, pygame.Rect(src))


def drop_ghost_texts() -> None:
    """Prevent a world floating text inside a mirror SOURCE rect from ghosting
    into the corner we just painted over."""
    srcs = [pygame.Rect(s) for _d, s in BARE_RECTS]
    cam_x, cam_y = STATE.camera_x, STATE.camera_y
    STATE.floating_texts[:] = [
        ft for ft in STATE.floating_texts
        if len(ft) < 2 or not any(
            r.collidepoint(ft[0] - cam_x, ft[1] - cam_y) for r in srcs)
    ]


# ── 3. Router ───────────────────────────────────────────────────────────────
class Router:
    """Walkability grid + the engine's own A*. Only used for APPROACH --
    engage-on-sight is handled by the Driver. Locked doors are stamped out so
    A* cannot route through them; unlocked auto-open doors stay passable."""

    def __init__(self, tmap, solids):
        self.grid = [[ch not in solids for ch in row] for row in tmap]
        for d in getattr(STATE, "doors", []) or []:
            if getattr(d, "locked", False) and getattr(d, "collision_rect", None):
                r = d.collision_rect
                for ty in range(r.y // T, (r.y + r.height) // T + 1):
                    for tx in range(r.x // T, (r.x + r.width) // T + 1):
                        if 0 <= ty < len(self.grid) and 0 <= tx < len(self.grid[0]):
                            self.grid[ty][tx] = False

    def path_to(self, sx, sy, gx, gy):
        try:
            raw = _astar((sx, sy), (gx, gy), self.grid)
        except Exception:
            return []
        return [(x * T + T // 2, y * T + T // 2) for x, y in raw]


# ── 4. Driver ───────────────────────────────────────────────────────────────
class Keys:
    """Duck-types pygame.key.get_pressed() for game_update(keys)."""

    def __init__(self):
        self.down: set[int] = set()

    def __getitem__(self, k):
        return k in self.down


class Driver:
    ENGAGE_RADIUS = int(os.environ.get("ACA_ENGAGE", "950"))
    SEEK_RADIUS = 2400
    CLOSE_BELOW, BACKOFF_BELOW = 330, 170
    REPATH_EVERY = 30
    ARRIVE_PX = 26
    STUCK_TICKS = 45        # ~0.75s of no progress before trying another target
    NAV_BLOCK_TICKS = 240   # 4s cooldown before re-attempting a wedged target

    # Trigger discipline: minimum ticks between trigger pulls, per weapon.
    # The engine cooldown (pistol 12f / OS-12 8f / K-9 5f) is the hard rate
    # limit; this sits on top of it so the gun fires at a human rate instead
    # of being held down. Expressed as shots/second: pistol 3.0, OS-12 5.0,
    # K-9 7.5 -- and jittered so it never reads as a metronome.
    MIN_INTERVAL = {"pistol": 20, "os12": 12, "k9_smg": 8}

    def __init__(self, router: Router, crosshair: bool = False,
                 ghost_filter: bool = True):
        self.router = router
        self.keys = Keys()
        self.cam = [0, 0]
        self.crosshair = crosshair
        self.ghost_filter = ghost_filter
        self.prev: dict = {}
        self.path: list = []
        self.pi = 0
        self.repath = 0
        self.tickno = 0
        self.engaged_tick = -1
        self.shots = 0
        self.kills = 0
        self._prev_kills = 0
        self._burst = 0
        self._gap = 0
        self._last_fire = -999
        self.blind_shots = 0      # shots actually fired without confirmed LOS
        self.no_los_ticks = 0     # ticks walking with no visible target
        self.engaged_ticks = 0    # ticks with a confirmed-visible target
        self.los_rects = 0        # size of the LOS wall set actually used
        self._aim = None          # world point the barrel is actually on
        self._walk_face = None    # A* waypoint / approach point while blind
        # foley event log state
        self.events: list = []
        self._foley_last = None
        self._step_acc = 0.0
        self._foley_bullets: set = set()
        self._foley_ehp = None
        self._foley_melee = False
        self._foley_reload = False
        self._nav_eid = None      # enemy we are currently navigating toward
        self._nav_block: dict = {}   # enemy id -> tick until which to ignore
        self._stuck = 0
        self._last_pos = None
        self.repaths = 0

    # -- LOS wall set ---------------------------------------------------
    def _los_walls(self):
        """The authoritative per-mission collision set for line-of-sight.

        weapons._solid_walls() is only STATE.walls + door collision rects.
        M2 keeps FOUR extra families on top of it (vehicle hulls, props, the
        shelter blast crescent, the garden) and M3 keeps mission3_barriers
        (every shelf, cabinet, crate and pillar). Using the base set made the
        bot shoot straight through the IPA truck and every piece of Archives
        furniture -- the "aimbot that ignores walls" artefact.

        These are the same functions the bullet loops use to resolve
        collisions (m2/update.py:46, m3/systems.py:65), so LOS and bullet
        flight now agree.
        """
        mission = getattr(STATE, "active_mission", "MISSION1")
        mod = {"MISSION2": "missions.m2.world",
               "MISSION3": "missions.m3.world"}.get(mission)
        if mod:
            try:
                import importlib
                return list(importlib.import_module(mod)._solid_walls())
            except Exception:
                pass
        return list(weapons._solid_walls())

    # -- perception -----------------------------------------------------
    def _nearest_enemy(self):
        p = STATE.player
        px, py = p.rect.center
        best, bd = None, self.SEEK_RADIUS
        for e in STATE.enemies:
            if getattr(e, "hp", 0) <= 0:
                continue
            d = math.hypot(e.rect.centerx - px, e.rect.centery - py)
            if d < bd:
                best, bd = e, d
        return best

    def _acquire(self, walls):
        """Return (visible_target, navigation_target).

        Picks the nearest enemy we can actually SEE, not merely the nearest
        enemy. Locking onto raw distance makes the bot walk into a shelf to
        reach a body it cannot shoot at while a third of the room is wide open
        -- in the Archives that left line of sight available on only 23% of
        ticks. Candidates are tested nearest-first and the scan short-circuits
        on the first clear segment, so the common case costs one test.

        Falls back to the nearest overall (outside ENGAGE_RADIUS or fully
        blocked) purely as a navigation goal -- never as a shooting target.
        """
        p = STATE.player
        px, py = p.rect.center
        cands = []
        fallback, bd = None, self.SEEK_RADIUS
        for e in STATE.enemies:
            if getattr(e, "hp", 0) <= 0:
                continue
            eid = id(e)
            if self._nav_block.get(eid, -1) > self.tickno:
                continue      # wedged against this one recently; try another
            d = math.hypot(e.rect.centerx - px, e.rect.centery - py)
            if d < bd:
                fallback, bd = e, d
            if d <= self.ENGAGE_RADIUS:
                cands.append((d, e))
        if cands:
            cands.sort(key=lambda t: t[0])
            for _d, e in cands:
                if self._segment_clear(px, py, e.rect.centerx, e.rect.centery,
                                       walls):
                    return e, e
            return None, cands[0][1]
        return None, fallback

    def _segment_clear(self, x1, y1, x2, y2, walls) -> bool:
        """Strict segment test against the live collision set, plus a body
        check so we do not lock onto a point sitting inside geometry."""
        for w in walls:
            if w.collidepoint(x1, y1) or w.collidepoint(x2, y2):
                return False
            if w.clipline((x1, y1), (x2, y2)):
                return False
        return True

    def _has_los(self, e, walls) -> bool:
        p = STATE.player
        px, py = p.rect.center
        ex, ey = e.rect.centerx, e.rect.centery
        if math.hypot(ex - px, ey - py) > self.ENGAGE_RADIUS:
            return False
        return self._segment_clear(px, py, ex, ey, walls)

    # -- aim ------------------------------------------------------------
    def aim_world(self, wx, wy) -> None:
        """Drive the engine's real aim path. m1/m2/m3 all derive
        STATE.player.angle from get_scaled_mouse() every game_update, and
        pygame.mouse.set_pos() works under SDL_VIDEODRIVER=dummy."""
        pygame.mouse.set_pos((int(wx - STATE.camera_x),
                              int(wy - STATE.camera_y)))

    # -- movement -------------------------------------------------------
    def _steer_toward(self, tx, ty, px, py) -> None:
        k = self.keys
        if abs(tx - px) > 8:
            k.down.add(pygame.K_d if tx > px else pygame.K_a)
        if abs(ty - py) > 8:
            k.down.add(pygame.K_s if ty > py else pygame.K_w)

    def _move(self, seen, target, px, py) -> None:
        """Set movement intent. Returns nothing -- the face point is resolved
        post-move, because the player has not moved yet and any aim chosen now
        would be a frame stale by the time the bullet leaves the barrel."""
        k = self.keys
        if target is None:
            k.down.clear()
            self._nav_eid = None
            return
        ex, ey = target.rect.centerx, target.rect.centery
        d = math.hypot(ex - px, ey - py)
        self._nav_eid = id(target)
        if seen is None:
            # Not visible: navigate around the geometry with A* rather than
            # beelining into a wall.
            if self.repath <= 0:
                self.path = self.router.path_to(
                    int(px // T), int(py // T),
                    int(ex // T), int(ey // T))
                self.pi = 0
                self.repath = self.REPATH_EVERY
            self.repath -= 1
            while self.pi < len(self.path) - 1 and math.hypot(
                    self.path[self.pi][0] - px,
                    self.path[self.pi][1] - py) < self.ARRIVE_PX:
                self.pi += 1
            if self.pi < len(self.path):
                wp = self.path[self.pi]
                self._steer_toward(wp[0], wp[1], px, py)
                self._walk_face = wp
                return
            self._walk_face = (ex, ey)   # A* failed; walk straight at it
        else:
            self._walk_face = (ex, ey)
        if d > self.CLOSE_BELOW:
            self._steer_toward(ex, ey, px, py)
        elif d < self.BACKOFF_BELOW:
            k.down.add(pygame.K_a if ex > px else pygame.K_d)
        else:
            k.down.add(pygame.K_a if (self.tickno // 25) % 2 else pygame.K_d)

    def _aim_and_fire(self, walls):
        """Post-move phase: re-perceive from where the player NOW is, aim, and
        fire. Doing this after game_update is what makes the LOS gate honest --
        aim, trigger and bullet all derive from the same frame state instead of
        a position the player has already left."""
        p = STATE.player
        px, py = p.rect.center
        seen, _nav = self._acquire(walls)

        if seen is None:
            self.no_los_ticks += 1
            # Face the way we are walking -- never an enemy we cannot see.
            # Aiming at a hidden target is the tell-tale 'shooting through the
            # wall' silhouette even when the trigger is disciplined.
            if self._walk_face is not None:
                self.aim_world(*self._walk_face)
            self._aim = None
            return None

        self.engaged_ticks += 1
        if self.engaged_tick < 0:
            self.engaged_tick = self.tickno
        ex, ey = seen.rect.centerx, seen.rect.centery
        key = getattr(seen, "uid", id(seen))
        pvx, pvy = self.prev.get(key, (ex, ey))
        self.prev[key] = (ex, ey)
        d = math.hypot(ex - px, ey - py)
        lead = d / 30.0   # enemy bullets run 18-24 px/frame; 30 errs long
        ax, ay = ex + (ex - pvx) * lead, ey + (ey - pvy) * lead
        # Only take the lead if the led point is still reachable -- otherwise
        # the barrel drifts a few px into the corner the enemy is hugging and
        # every shot dies on the brick.
        if not self._segment_clear(px, py, ax, ay, walls):
            ax, ay = ex, ey
        self._aim = (ax, ay)
        self.aim_world(ax, ay)
        return seen

    # -- trigger discipline ---------------------------------------------
    def _want_fire(self, engaged: bool) -> bool:
        """Hold the trigger only with a confirmed-visible target, and only at a
        human cadence. handle_shoot() performs no LOS check of its own -- it
        just fires along player.angle -- so an ungated call sprays the whole
        take, which is the 'just shoots and shoots' artefact."""
        if not engaged:
            return False
        gap = self.MIN_INTERVAL.get(getattr(STATE, "current_weapon", "pistol"), 20)
        if self.tickno - self._last_fire < gap:
            return False
        self._last_fire = self.tickno - int(gap * random.uniform(-0.12, 0.30))
        return True

    def _audit_shot(self, walls, seen) -> None:
        """Independent post-hoc check on the shot that was just taken: re-test
        the ray the bullet actually travelled (the led aim point, not the
        enemy centre) against the live collision set. This is a regression
        tripwire -- if a future refactor lets the gate leak, it surfaces here
        rather than as a bullet quietly absorbed by a wall."""
        if seen is None or self._aim is None:
            self.blind_shots += 1
            return
        p = STATE.player
        px, py = p.rect.center
        ax, ay = self._aim
        if not self._segment_clear(px, py, ax, ay, walls):
            self.blind_shots += 1

    # -- foley event log -------------------------------------------------
    # The capture runs with SDL_AUDIODRIVER=dummy, so the engine's own sound
    # is discarded and the master ships silent. This log is the substitute
    # signal: tools/build_sfx_stem.py re-renders the real sfx_wav/*.wav assets
    # at these exact ticks to build trailer_sfx_stem.wav for the audio mux.
    #
    # Only events observable from live state are logged. Footsteps are the one
    # derived value: the engine plays them internally off a distance accumulator
    # (entities/player.py: _step_timer resets to 34 + rand(0,8) px), so this
    # mirrors that cadence rather than inventing a new one.
    FOOTSTEP_PX = 34.0

    def _log(self, kind: str, **kw) -> None:
        self.events.append(dict(t=self.tickno, kind=kind, **kw))

    def _track_foley(self) -> None:
        p = STATE.player
        cx, cy = p.rect.center
        if self._foley_last is not None:
            moved = math.hypot(cx - self._foley_last[0], cy - self._foley_last[1])
            if moved > 0.5:
                # Counts DOWN, exactly like entities/player.py: the engine
                # decrements _step_timer by distance travelled and fires at
                # zero. (An earlier version accumulated upward but tested for
                # <= 0, so no footstep ever logged.)
                self._step_acc -= moved
                if self._step_acc <= 0:
                    self._log("footstep")
                    self._step_acc = 34.0 + random.randint(0, 8)
            else:
                self._step_acc = min(self._step_acc, 6.0)
        self._foley_last = (cx, cy)

        # Enemy fire: new bullets owned by an enemy. Counted by uid so a
        # bullet that survives several ticks is not re-logged.
        live = set()
        for b in getattr(STATE, "bullets", []) or []:
            if isinstance(b, dict) and b.get("owner") == "enemy":
                uid = b.get("uid", id(b))
                live.add(uid)
                if uid not in self._foley_bullets:
                    self._log("enemy_shot")
        self._foley_bullets = live

        # Damage: compare total living enemy HP against last tick's total.
        total = sum(max(0, getattr(e, "hp", 0)) for e in STATE.enemies)
        if self._foley_ehp is not None and total < self._foley_ehp:
            self._log("enemy_hit", dmg=round(self._foley_ehp - total, 1))
        self._foley_ehp = total

        # Rising edges only -- a held reload must not log 90 events.
        mel = bool(getattr(STATE, "melee_active", False))
        if mel and not self._foley_melee:
            self._log("melee")
        self._foley_melee = mel
        rld = bool(getattr(STATE, "is_reloading", False))
        if rld and not self._foley_reload:
            self._log("reload")
        self._foley_reload = rld

    # -- capture harness ------------------------------------------------
    def _invulnerable(self) -> None:
        """Keep the operator alive and the active weapon loaded so a 10s take
        is 10s of combat. Only the ACTIVE weapon is topped up -- the legacy
        top_up() only handled K-9 and the M1 fields, so M2 OS-12 takes ran
        dry and stalled."""
        p = STATE.player
        p.hp = p.max_hp
        w = getattr(STATE, "current_weapon", "pistol")
        if w == "k9_smg":
            STATE.k9_ammo_in_mag = STATE.k9_mag_size
        elif w == "os12":
            STATE.os12_ammo_in_mag = STATE.os12_mag_size
        else:
            STATE.ammo_in_mag = STATE.mag_size

    def tick(self) -> None:
        self.tickno += 1
        p = STATE.player
        if p is None or STATE.player_dead:
            return
        if self.ghost_filter and BARE_RECTS and _BARE_MODE[0]:
            drop_ghost_texts()

        k = self.keys
        k.down.clear()
        self._walk_face = None

        # -- pre-move: perceive, then set movement intent ------------------
        walls = self._los_walls()
        self.los_rects = len(walls)
        px, py = p.rect.center
        seen, target = self._acquire(walls)
        self._move(seen, target, px, py)
        self._invulnerable()

        cam = gc.game_update(k)
        if cam:
            self.cam[0], self.cam[1] = cam

        # Stuck detection: the Archives is a maze, and a naive "walk at the
        # nearest body" wedges the player against a shelf for seconds while an
        # enemy stands 130px away on the other side. When progress stalls,
        # deprioritise that body and re-path toward the next candidate.
        px2, py2 = p.rect.center
        if self._last_pos is not None:
            if math.hypot(px2 - self._last_pos[0],
                          py2 - self._last_pos[1]) > 1.5:
                self._stuck = 0
            else:
                self._stuck += 1
        self._last_pos = (px2, py2)
        if self._stuck > self.STUCK_TICKS and self._nav_eid is not None:
            self._nav_block[self._nav_eid] = self.tickno + self.NAV_BLOCK_TICKS
            self.repaths += 1
            self._stuck = 0
            self.repath = 0            # force A* re-computation next tick
            self.path = []

        # -- post-move: re-perceive, aim, fire ---------------------------
        # The missions overwrite STATE.player.angle from the mouse during
        # game_update, so aiming before the update is pointless anyway. Doing
        # it here means aim, trigger and bullet all share one frame state.
        walls = self._los_walls()
        self.los_rects = len(walls)
        seen = self._aim_and_fire(walls)

        # Fire only with a confirmed-visible target. handle_shoot() just fires
        # along player.angle and checks nothing, so the gate lives here.
        if self._want_fire(seen is not None):
            before = getattr(STATE, "shots_fired", 0)
            weapons.handle_shoot()
            if getattr(STATE, "shots_fired", 0) != before:
                self.shots += 1
                self._log("player_shot",
                          weapon=getattr(STATE, "current_weapon", "pistol"))
                self._audit_shot(walls, seen)
        self._track_foley()

        gc.game_draw(self.cam[0], self.cam[1])
        if _BARE_MODE[0]:
            apply_bare_mask()
        if self.crosshair:
            try:
                _hud.draw_gameplay_crosshair(config.screen, "GAME")
            except Exception:
                pass
        pygame.event.pump()

        cur = (getattr(STATE, "hostiles_killed", 0)
               + getattr(STATE, "mission3_guards_killed", 0))
        if cur != self._prev_kills:
            self.kills += cur - self._prev_kills
            self._prev_kills = cur


_BARE_MODE = [False]   # mutable single-slot so Driver can read it cheaply


# ── 5. capture_act ──────────────────────────────────────────────────────────
def capture_act(act, args, ffmpeg: str) -> dict:
    print(f"[{act['key']}] {act['label']} -- booting checkpoint", flush=True)
    random.seed(args.seed)
    act["boot"]()
    if STATE.player is None:
        raise RuntimeError("checkpoint produced no player")

    strip_after_boot()
    driver = Driver(Router(act["tmap"], act["solids"]),
                    crosshair=args.crosshair,
                    ghost_filter=not args.no_ghost_filter)

    out = Path(args.out_dir) / f"{act['key']}.mp4"
    tick = Ticker(ffmpeg, out)
    total = int(round(args.seconds * SIM_HZ))
    t0 = time.perf_counter()
    for n in range(total):
        driver.tickno = n
        driver.tick()
        if n % 2 == 1:
            tick.feed()
    err = tick.close()
    wall = time.perf_counter() - t0

    rep = dict(
        act=act["key"], label=act["label"],
        frames=tick.frames, seconds=round(tick.frames / FPS, 2),
        ticks=total, contact_tick=driver.engaged_tick,
        contact_sec=round(max(0, driver.engaged_tick) / SIM_HZ, 2),
        shots=driver.shots, kills=driver.kills,
        shots_per_sec=round(driver.shots / max(0.001, args.seconds), 2),
        trigger_duty=round(driver.shots / max(1, driver.engaged_ticks), 3),
        no_los_ticks=driver.no_los_ticks,
        stuck_repaths=driver.repaths,
        blind_shots=driver.blind_shots,
        los_rects=driver.los_rects,
        engaged_ticks=driver.engaged_ticks,
        enemies_left=len(STATE.enemies),
        mean_luma=tick.mean_luma, unique_frames=tick.unique_frames,
        changed_ratio=tick.changed_ratio,
        wall_sec=round(wall, 1), out=str(out),
        bytes=out.stat().st_size if out.exists() else 0,
        foley_events=len(driver.events),
        foley_log=str(out.with_suffix(".foley.json")),
    )
    # Sidecar foley log: the SFX stem generator reads this, not the video.
    out.with_suffix(".foley.json").write_text(json.dumps(
        dict(act=act["key"], label=act["label"], starter=act["starter"],
             hz=SIM_HZ, frames=tick.frames, seconds=round(tick.frames / FPS, 3),
             ticks=total, seed=args.seed,
             stats=dict(shots=driver.shots, kills=driver.kills,
                        blind_shots=driver.blind_shots,
                        enemy_shots=sum(1 for e in driver.events
                                        if e["kind"] == "enemy_shot")),
             events=driver.events), indent=1), encoding="utf-8")
    return rep, err, total, driver


# ── 6. verification ─────────────────────────────────────────────────────────
def verify(rep, err, total, driver, args, ffprobe) -> list:
    fails = []
    if err:
        fails.append(err)
    if rep["frames"] != int(round(args.seconds * FPS)):
        fails.append(f'frame count {rep["frames"]} != {int(round(args.seconds * FPS))}')
    if driver.engaged_tick < 0:
        fails.append("no enemy ever acquired line of sight -- clip is not combat")
    elif driver.engaged_tick > 0.6 * total:
        fails.append(f'contact at {driver.engaged_tick / SIM_HZ:.1f}s '
                     f'(> 60% of the {args.seconds:.0f}s take)')
    if driver.kills < 2:
        fails.append(f'only {driver.kills} kill(s) -- gun is not connecting')
    # Wall discipline: the trigger must never be pulled without line of sight.
    if driver.blind_shots > 0:
        fails.append(f'{driver.blind_shots} shot(s) fired without line of sight '
                     f'-- walls are being ignored')
    # Trigger discipline: a gun held down at its cooldown is not a firefight.
    if rep["trigger_duty"] > 0.6:
        fails.append(f'trigger duty {rep["trigger_duty"]} > 0.6 -- '
                     f'firing near-continuously instead of at a human cadence')
    if rep["unique_frames"] < 3 or rep["changed_ratio"] < 0.5:
        fails.append(f'frame liveness: {rep["unique_frames"]} unique / '
                     f'{rep["changed_ratio"]} changed between samples -- '
                     f'frame looks frozen')
    if rep["mean_luma"] < 5:
        fails.append(f'mean luma {rep["mean_luma"]} < 5 -- frame is effectively black')
    if ffprobe:
        meta = probe(ffprobe, Path(rep["out"]))
        if meta.get("pix_fmt") not in (None, "yuv420p"):
            fails.append(f'pix_fmt={meta.get("pix_fmt")} (want yuv420p)')
        if meta.get("nb_frames") and int(meta["nb_frames"]) != rep["frames"]:
            fails.append(f'ffprobe nb_frames={meta["nb_frames"]} != {rep["frames"]}')
    return fails


def probe(ffprobe: str, path: Path) -> dict:
    try:
        r = subprocess.run(
            [ffprobe, "-v", "error", "-select_streams", "v:0",
             "-show_entries", "stream=codec_name,width,height,pix_fmt,nb_frames",
             "-of", "json", str(path)],
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True, timeout=60)
        return (json.loads(r.stdout).get("streams") or [{}])[0]
    except Exception:
        return {}


# ── 7. merge ────────────────────────────────────────────────────────────────
def merge(ffmpeg: str, paths, out: Path) -> bool:
    lst = out.parent / "_concat.txt"
    lst.write_text("".join(f"file '{p.resolve()}'\n" for p in paths),
                   encoding="utf-8")
    r = subprocess.run(
        [ffmpeg, "-y", "-f", "concat", "-safe", "0", "-i", str(lst),
         "-c", "copy", "-movflags", "+faststart", str(out)],
        stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True)
    lst.unlink(missing_ok=True)
    if r.returncode != 0:
        print(f"  merge failed: {r.stderr[-500:]}", flush=True)
        return False
    return True


# ── main ────────────────────────────────────────────────────────────────────
def main() -> int:
    ap = argparse.ArgumentParser(
        description="Clean standalone combat capture (3 verified checkpoints).")
    ap.add_argument("--act", default="all",
                    help="1 | 2 | 3 | all (comma list ok)")
    ap.add_argument("--seconds", type=float, default=DEFAULT_SECONDS)
    ap.add_argument("--hud", choices=("clean", "bare", "full"), default="clean")
    ap.add_argument("--out-dir", default="trailers/fresh_action")
    ap.add_argument("--merge", action="store_true",
                    help="also emit combat_<N>s.mp4 via the concat demuxer")
    ap.add_argument("--crosshair", action="store_true")
    ap.add_argument("--seed", type=int, default=20260926)
    ap.add_argument("--keep-going", action="store_true")
    ap.add_argument("--no-ghost-filter", action="store_true")
    ap.add_argument("--list", action="store_true", help="print acts and exit")
    args = ap.parse_args()

    acts = _act_table()
    if args.list:
        print(f"{'act':<6}{'starter':<54}{'equiv CLI':<26}nav solids")
        for a in acts:
            print(f"{a['key']:<6}{a['starter']:<54}{a['cli']:<26}{a['solids']}")
        return 0

    try:
        ffmpeg = ffmpeg_exe()
    except SystemExit as e:
        print(f"PREFLIGHT FAIL: {e}", file=sys.stderr)
        return 2
    ffprobe = ffprobe_exe(ffmpeg)

    want = {"1", "2", "3"} if args.act == "all" else {
        w.strip() for w in str(args.act).split(",") if w.strip()}
    selected = [a for a in acts if str(a["n"]) in want]
    if not selected:
        print(f"PREFLIGHT FAIL: --act {args.act!r} matched no checkpoint",
              file=sys.stderr)
        return 2

    out_dir = (ROOT / args.out_dir) if not Path(args.out_dir).is_absolute() \
        else Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    _BARE_MODE[0] = args.hud == "bare"
    apply_hud_policy(args.hud)
    SETTINGS.show_crosshair = bool(args.crosshair)
    if hasattr(config, "audio"):
        try:
            config.audio.set_master_volume(0)
        except Exception:
            pass

    print(f"ffmpeg   : {ffmpeg}")
    print(f"output   : {out_dir}")
    print(f"hud      : {args.hud}   seconds/act: {args.seconds:g}   seed: {args.seed}")
    print(f"scratch  : {_SCRATCH}  (save_data.json / settings.json sandboxed)")
    print("-" * 72, flush=True)

    report, failed = [], 0
    for act in selected:
        try:
            rep, err, total, driver = capture_act(act, args, ffmpeg)
        except Exception as e:
            failed += 1
            print(f"[{act['key']}] FAILED: {e!r}", flush=True)
            if not args.keep_going:
                break
            continue
        fails = verify(rep, err, total, driver, args, ffprobe)
        rep["verified"] = not fails
        rep["failures"] = fails
        report.append(rep)
        status = "OK" if not fails else "FAIL"
        print(f"  {status}  {rep['frames']}f / {rep['seconds']}s  "
              f"contact {rep['contact_sec']}s  "
              f"{rep['shots_per_sec']}/s ({rep['shots']} shots)  "
              f"kills {rep['kills']}  blind {rep['blind_shots']}  "
              f"los_rects {rep['los_rects']}  "
              f"left {rep['enemies_left']}  wall {rep['wall_sec']}s  "
              f"{rep['bytes'] // 1024} KB", flush=True)
        for f in fails:
            print(f"        - {f}", flush=True)
        if fails:
            failed += 1
            if not args.keep_going:
                break
        # Reset between acts: audio loops, radio queue, RNG.
        if hasattr(config, "audio"):
            for fn in ("stop_all", "stop_mission3_alarm"):
                try:
                    getattr(config.audio, fn)()
                except Exception:
                    pass
        interactions.clear_radio_queue()

    if args.merge and report:
        total_s = round(sum(r["seconds"] for r in report), 2)
        merged = out_dir / f"combat_{int(total_s)}s.mp4"
        print("-" * 72, flush=True)
        if merge(ffmpeg, [Path(r["out"]) for r in report], merged):
            print(f"  merged -> {merged}  {merged.stat().st_size // 1024} KB")

    (out_dir / "report.json").write_text(
        json.dumps({"hud": args.hud, "seconds": args.seconds,
                    "seed": args.seed, "acts": report}, indent=2),
        encoding="utf-8")
    print("-" * 72)
    print(f"report   : {out_dir / 'report.json'}")
    print(f"result   : {len(report)} act(s) captured, {failed} failed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())

