"""Headless cinematic trailer bot, PLAN_2 cut.

Combat-only timeline, zero repeats: M1 warehouse shootout -> card ->
M3 cell breakout -> card -> M3 kill-order lobby gunfight -> outro card.
Each scene pre-rolls UNFED until first contact, so the first captured
frame is already shooting. No bottom text anywhere.

Renders REAL gameplay at 60 ticks/s, captures every 2nd frame to 30fps MP4.
"""
import math
import os
import subprocess
import sys

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "src"))

import pygame
pygame.init()

import imageio_ffmpeg
from core import game_core as gc
from core.state import STATE
from core.config import WIDTH, HEIGHT, TILE_SIZE as T
from missions.m3 import maps as M
from missions.m3 import sweep
from missions.m3.sweep import _LANE_V, _LANE_H
from entities import weapons
from entities.enemy_ai import _astar

FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()
OUT = os.path.join(os.environ.get("ARENA_WORKSPACE",
                                      os.path.dirname(os.path.abspath(__file__))),
                       "ko_phase5_preview.mp4")

proc = subprocess.Popen(
    [FFMPEG, "-y", "-f", "rawvideo", "-vcodec", "rawvideo",
     "-s", f"{WIDTH}x{HEIGHT}", "-pix_fmt", "rgb24", "-r", "30",
     "-i", "-", "-an", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "20",
     "-movflags", "+faststart", OUT],
    stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

FONT_CAP = pygame.font.Font(None, 18)
FONT_BIG = pygame.font.Font(None, 64)
FONT_MID = pygame.font.Font(None, 28)

LOCKED = {(13, 12), (13, 20), (31, 32), (32, 32)}
WGRID = [[M.MISSION3_KILL_ORDER_MAP[y][x] not in ("C", "g", "B")
          and not (M.MISSION3_KILL_ORDER_MAP[y][x] == "D" and (x, y) in LOCKED)
          for x in range(40)] for y in range(40)]
PILLARS = [(15, 13), (15, 20), (19, 16), (24, 12), (21, 24)]


class Keys:
    def __init__(self):
        self.down = set()
    def __getitem__(self, k):
        return k in self.down


KEYS = Keys()
cam = [0, 0]
frame = [0]
CUM = [0]  # absolute sim ticks (preroll + capture) for the scene log
PREV = {}


def feed(surface):
    proc.stdin.write(pygame.image.tostring(surface, "RGB"))


def card(lines, seconds):
    for _ in range(int(seconds * 30)):
        s = pygame.Surface((WIDTH, HEIGHT))
        s.fill((6, 7, 6))
        y = HEIGHT // 2 - 40 * len(lines)
        for i, ln in enumerate(lines):
            f = FONT_BIG if i == 0 else FONT_MID
            col = (220, 210, 180) if i == 0 else (140, 160, 140)
            t = f.render(ln, True, col)
            s.blit(t, (WIDTH // 2 - t.get_width() // 2, y + i * 64))
        feed(s)


class Router:
    def __init__(self, goals, grid=None, door_map=None):
        self.goals = list(goals)
        self.grid = grid if grid is not None else WGRID
        self.door_map = door_map  # char-grid for straight-through "D" filter (KO only)
        self.wps = []
        self.i = 0
        self.stuck = 0
        self.last = None
        self.jit = 0
    def _route(self):
        if not self.goals or STATE.player is None:
            return
        gx, gy = self.goals.pop(0)
        px, py = STATE.player.rect.center
        try:
            path = _astar((int(px // T), int(py // T)), (gx, gy), self.grid)
        except Exception:
            path = []
        kept = []
        for idx, (x, y) in enumerate(path):
            if (0 < idx < len(path) - 1
                    and self.door_map is not None
                    and self.door_map[y][x] == "D"):
                (ax, ay), (bx, by) = path[idx - 1], path[idx + 1]
                if (ax - x, ay - y) == (x - bx, y - by):
                    continue
            kept.append((x * T + T // 2, y * T + T // 2))
        self.wps = kept or [(gx * T + T // 2, gy * T + T // 2)]
        self.i = 0
        self.stuck = 0
    def done(self):
        return not self.goals and self.i >= len(self.wps)
    def step(self):
        if self.i >= len(self.wps) and self.goals:
            self._route()
        if self.i >= len(self.wps):
            KEYS.down.clear()
            return
        px, py = STATE.player.rect.center
        tx, ty = self.wps[self.i]
        if math.hypot(tx - px, ty - py) < 24:
            self.i += 1
            self.stuck = 0
            return
        moved = self.last and math.hypot(px - self.last[0], py - self.last[1]) > 1.5
        self.stuck = 0 if moved else self.stuck + 1
        self.last = (px, py)
        KEYS.down.clear()
        if self.stuck > 40:
            self.jit = 30
            self.stuck = 0
        dx, dy = tx - px, ty - py
        if self.jit > 0:
            self.jit -= 1
            if abs(dy) >= abs(dx):
                KEYS.down.add(pygame.K_s if dy > 0 else pygame.K_w)
                KEYS.down.add(pygame.K_a if (self.jit // 15) % 2 else pygame.K_d)
            else:
                KEYS.down.add(pygame.K_d if dx > 0 else pygame.K_a)
                KEYS.down.add(pygame.K_w if (self.jit // 15) % 2 else pygame.K_s)
            return
        if abs(dx) > 6:
            KEYS.down.add(pygame.K_d if dx > 0 else pygame.K_a)
        if abs(dy) > 6:
            KEYS.down.add(pygame.K_s if dy > 0 else pygame.K_w)


def nearest_enemy(max_d=560):
    if not STATE.player:
        return None
    px, py = STATE.player.rect.center
    best, bd = None, max_d
    for e in STATE.enemies:
        if e.hp <= 0:
            continue
        d = math.hypot(e.rect.centerx - px, e.rect.centery - py)
        if d < bd:
            best, bd = e, d
    return best


def combat(shoot=True):
    """Aim with leading, burst-fire, strafe. Returns True if engaged."""
    e = nearest_enemy()
    if e is None:
        return False
    px, py = STATE.player.rect.center
    ex, ey = e.rect.centerx, e.rect.centery
    pvx, pvy = PREV.get(e.uid, (ex, ey))
    evx, evy = ex - pvx, ey - pvy
    PREV[e.uid] = (ex, ey)
    dist = math.hypot(ex - px, ey - py)
    lead_t = dist / 24.0
    ax, ay = ex + evx * lead_t, ey + evy * lead_t
    STATE.player.angle = math.atan2(ay - py, ax - px)   # real aim, real gun
    if dist < 52:  # PLAN_2: knife/shiv range - stab immediately, no wind-up
        try:
            weapons.handle_melee()
        except Exception:
            pass
    # PLAN_2: fire EVERY tick on target - weapon cooldowns gate the true
    # rate (pistol 12f / OS-12 8f / K-9 5f), so this clears immediately
    # instead of pausing inside a burst window.
    if shoot:
        weapons.handle_shoot()
    if (frame[0] // 25) % 2:
        KEYS.down.add(pygame.K_a)
    else:
        KEYS.down.add(pygame.K_d)
    return True


def seek_cover():
    """If the overwatch laser is painting us in a lane, hug nearest pillar."""
    st = getattr(STATE, "m3_sweep", None)
    if not st or st["overwatch"]["telegraph"] <= 0 or STATE.player is None:
        return False
    px, py = STATE.player.rect.center
    if not (_LANE_V.collidepoint(px, py) or _LANE_H.collidepoint(px, py)):
        return False
    cx, cy = min(PILLARS, key=lambda p: math.hypot(p[0] * T - px, p[1] * T - py))
    tx, ty = cx * T + T // 2, cy * T + T // 2 + 40
    KEYS.down.clear()
    dx, dy = tx - px, ty - py
    if abs(dx) > 8:
        KEYS.down.add(pygame.K_d if dx > 0 else pygame.K_a)
    if abs(dy) > 8:
        KEYS.down.add(pygame.K_s if dy > 0 else pygame.K_w)
    return True


def tick(router=None, fight=False, cap_text=None, cover=True, capture=True):
    """Advance one sim tick. capture=False pre-rolls WITHOUT feeding frames
    (used to skip dead walking so scene 1st fed frame is already combat)."""
    if STATE.player:
        STATE.player.hp = STATE.player.max_hp
        STATE.k9_ammo_in_mag = STATE.k9_mag_size
    if router:
        router.step()
    c = gc.game_update(KEYS)
    if c:
        cam[0], cam[1] = c
    engaged = False
    if fight:
        if not (cover and seek_cover()):
            engaged = combat()
    gc.game_draw(cam[0], cam[1])
    # PLAN_2: bottom phase label KILLED - no text at the bottom, ever.
    # (cap_text args at call sites are now no-ops; signature kept so the
    # run section needs no edits.)
    frame[0] += 1
    CUM[0] += 1
    if capture and frame[0] % 2 == 0:
        feed(screen)
    return engaged


# ═══ run - PLAN_2 trailer timeline: combat only, no repeats ═══
def _grid_from_chars(rows, solids):
    return [[ch not in solids for ch in row] for row in rows]


def stage_breakout_flags():
    """Post-craft breakout state (same flags the game sets on shiv finish).
    Without staging the cell door stays shut and the bot shuffles inside."""
    S = STATE
    S.mission3_weapon = "shiv"
    S.mission3_cell_open = True
    S.mission3_chair_broken = True
    S.mission3_chair_break_anim = -1
    S.mission3_doorway_blocked = False
    S.mission3_crafting_progress = 1.0
    S.mission3_crafting_active = False
    S.player_disarmed = False
    S.request_chair_break_cutscene = False


def preroll_until_contact(router, label, max_ticks=600):
    """Advance UNFED until the bot is firing. Returns ticks burned (not fed)."""
    for used in range(max_ticks):
        if tick(router, fight=True, capture=False):
            print(f"  {label}: contact after {used} preroll ticks (unfed)", flush=True)
            return used
    print(f"  {label}: NO CONTACT in {max_ticks} preroll ticks - capturing anyway", flush=True)
    return max_ticks


def capture(router, ticks, label):
    start = CUM[0]
    for _ in range(ticks):
        tick(router, fight=True)
    print(f"  {label}: fed ticks {start}-{CUM[0]} ({ticks} ticks = {ticks / 60:.1f}s)", flush=True)


print("TRAILER SCENES (60 ticks = 1s; preroll ticks are UNFED dead-time kills):")
print("  A      M1 warehouse shootout   goals [(6,5),(10,11),(14,12),(18,11)]  capture 360 ticks (6.0s)")
print("  CARD   ACT I - BLACK NOTEBOOK (1.8s)")
print("  B      M3 cell breakout/shiv   goals [(32,10),(33,12),(35,13),(38,13),(40,14),(41,15)]  capture 360 ticks (6.0s)")
print("  CARD   ACT III - THE BREAKOUT (1.8s)")
print("  C      M3 kill-order lobby gunfight  goals [(5,12),(5,17),(19,12),(14,16)]  capture 420 ticks (7.0s)")
print("  OUTRO  CALL OF ACARISTAN / M1-M3 / wishlist (3.0s)")

# ── Scene A: warehouse shootout (no Route 12, no truck, no walking) ──
from missions.m1 import map as m1map  # lazy: after game boot imports
gc.start_mission()
screen = pygame.display.get_surface()
ra = Router([(6, 5), (10, 11), (14, 12), (18, 11)],
            grid=_grid_from_chars(m1map.mission1_map, ("C", "W")))
preroll_until_contact(ra, "A")
capture(ra, 360, "A")

card(["ACT I - BLACK NOTEBOOK", "the warehouse shootout"], 1.8)

# ── Scene B: prison cell breakout / shiv ──
gc.start_mission3_breakout_checkpoint()
stage_breakout_flags()
rb = Router([(32, 10), (33, 12), (35, 13), (38, 13), (40, 14), (41, 15)],
            grid=_grid_from_chars(M.MISSION3_CELL_MAP, ("C", "B", "S")))
preroll_until_contact(rb, "B")
capture(rb, 360, "B")

card(["ACT III - THE BREAKOUT", "shiv and sidearm"], 1.8)

# ── Scene C: kill-order lobby gunfight ──
gc.start_mission3_kill_order_checkpoint()
rc = Router([(5, 12), (5, 17), (19, 12), (14, 16)],
            grid=WGRID, door_map=M.MISSION3_KILL_ORDER_MAP)
preroll_until_contact(rc, "C")
capture(rc, 420, "C")

card(["CALL OF ACARISTAN",
      "M1 // BLACK NOTEBOOK - M3 // THE VOSTRAL",
      "wishlist on Steam"], 3.0)

proc.stdin.close()
proc.wait()
print("saved", OUT, os.path.getsize(OUT) // 1024, "KB")

