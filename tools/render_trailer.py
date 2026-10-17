"""render_trailer.py - 75-90s MP4 game trailer (headless real gameplay).

PLAN_4_VISUALS implementation: zero debug labels, no menu capture.
  Cold Open  - KRAPNET boot typewriter -> broadcast card -> title slam
  Act I      - M1 warehouse (establish the world)
  Act II     - M2 Route 12 + sniper ambush (escalation)
  Act III    - M3 Vostral breakout + kill-order (climax)
  End Card   - Steam wishlist lockup (no COMING SOON)

Video: native 1000x700 @30fps (60 game ticks, feed every 2nd) piped as
rawvideo to system ffmpeg (libx264, yuv420p, faststart). A second ffmpeg
pass upscales/pads to 1920x1080 and muxes the music track (-shortest),
plus an optional 9:16 center-crop vertical export.

Usage:
    python tools/render_trailer.py            # full trailer -> trailers/trailer_60s.mp4
    python tools/render_trailer.py --smoke    # ~15s fast check -> trailers/trailer_smoke.mp4
    python tools/render_trailer.py --no-audio # skip music mux
"""
import argparse
import math
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

_TMP = Path(tempfile.mkdtemp(prefix="acaristan_trailer_"))
from core import save_system as _sv  # noqa: E402
from core import settings_store as _st  # noqa: E402
_sv.SAVE_FILE = str(_TMP / "save_data.json")
_st.SAVE_FILE = str(_TMP / "settings.json")

import pygame  # noqa: E402
from core import game_core as gc  # noqa: E402
from core import config  # noqa: E402
from core.state import STATE  # noqa: E402
from entities import weapons  # noqa: E402
from missions import walking_sim as ws  # noqa: E402
from entities.enemy_ai import _astar  # noqa: E402
from core.config import TILE_SIZE as T  # noqa: E402

W, H = config.WIDTH, config.HEIGHT
FPS = 30

FFMPEG = (
    shutil.which("ffmpeg")
    or r"C:\ffmpeg\bin\ffmpeg.exe"
    or os.environ.get("FFMPEG", "")
)
if not FFMPEG or not Path(str(FFMPEG)).exists() and not shutil.which("ffmpeg"):
    raise SystemExit("ffmpeg not found (PATH or C:\\ffmpeg\\bin\\ffmpeg.exe)")

TRAILERS = ROOT / "trailers"
TRAILERS.mkdir(exist_ok=True)


def _font(name, size):
    p = ROOT / "assets" / "fonts" / name
    try:
        if p.exists():
            return pygame.font.Font(str(p), size)
    except Exception:
        pass
    return pygame.font.Font(None, size)


FONT_BIG = _font("Oswald.ttf", 72)
FONT_MID = _font("Oswald.ttf", 30)
FONT_CAP = _font("IBMPlexMono-Regular.ttf", 18)
FONT_TAG = _font("IBMPlexMono-SemiBold.ttf", 22)


class Keys:
    def __init__(self):
        self.down = set()

    def __getitem__(self, k):
        return k in self.down


KEYS = Keys()
PREV = {}
FRAME = [0]
PROC = [None]


def feed():
    PROC[0].stdin.write(pygame.image.tobytes(config.screen, "RGB"))


def card(lines, seconds, tag=None, accent=(255, 120, 0), flash_first=False,
         fade_out_seconds=0.0):
    total = int(seconds * FPS)
    fade_frames = int(fade_out_seconds * FPS)
    for i in range(total):
        s = pygame.Surface((W, H))
        s.fill((4, 5, 6))
        pygame.draw.rect(s, accent, (W // 2 - 90, H // 2 - 150, 180, 3))
        y = H // 2 - 110
        for li, ln in enumerate(lines):
            f = FONT_BIG if li == 0 else FONT_MID
            col = (232, 222, 190) if li == 0 else (150, 170, 150)
            t = f.render(ln, True, col)
            s.blit(t, (W // 2 - t.get_width() // 2, y))
            y += t.get_height() + (26 if li == 0 else 0)
        if tag:
            t = FONT_TAG.render(tag, True, accent)
            s.blit(t, (W // 2 - t.get_width() // 2, y + 36))
        # PLAN_4 §2.1/§3: 1-frame muzzle exposure bump on title slam.
        if flash_first and i < 2:
            flash = pygame.Surface((W, H), pygame.SRCALPHA)
            flash.fill((255, 240, 220, 90 if i == 0 else 35))
            s.blit(flash, (0, 0))
        # PLAN_4 §4: end-card fade to black over last N seconds.
        if fade_frames > 0 and i >= total - fade_frames:
            a = int(255 * (i - (total - fade_frames) + 1) / max(1, fade_frames))
            fade = pygame.Surface((W, H), pygame.SRCALPHA)
            fade.fill((0, 0, 0, max(0, min(255, a))))
            s.blit(fade, (0, 0))
        config.screen.blit(s, (0, 0))
        feed()
        FRAME[0] += 1


def black_frame(seconds):
    for _ in range(int(seconds * FPS)):
        config.screen.fill((0, 0, 0))
        feed()
        FRAME[0] += 1


# PLAN_4 §3: cold-open boot typewriter (no menu capture).
# Reuses ui/main.py _BOOT_LINES text + 35 chars/sec rate; tick sfx is AI-3.
_BOOT_LINES = [
    "> KRAPNET TERMINAL v7.2.1",
    "> AUTHENTICATING OPERATOR .... OK",
]
_BOOT_CHAR_RATE = 35.0


def boot_intro(seconds):
    total = int(seconds * FPS)
    full = "\n".join(_BOOT_LINES)
    total_chars = len(full)
    for i in range(total):
        s = pygame.Surface((W, H))
        s.fill((0, 0, 0))
        elapsed = i / float(FPS)
        n_chars = min(total_chars, int(elapsed * _BOOT_CHAR_RATE))
        visible = full[:n_chars]
        if n_chars < total_chars and (i // 9) % 2 == 0:
            visible += "_"
        y = H // 2 - 30
        for ln in visible.split("\n"):
            if ln:
                t = FONT_CAP.render(ln, True, (255, 120, 0))
                s.blit(t, (W // 2 - t.get_width() // 2, y))
            y += 30
        config.screen.blit(s, (0, 0))
        feed()
        FRAME[0] += 1


def broadcast_card(seconds):
    # PLAN_4 §3: hard-cut ROUTE 12 BLACK frame + red banner.
    # Text source: src/missions/m3/meta.py STATE ADDRESS - LIVE TONIGHT - 22:00.
    for _ in range(int(seconds * FPS)):
        s = pygame.Surface((W, H))
        s.fill((8, 5, 5))
        banner = FONT_MID.render("STATE ADDRESS - LIVE TONIGHT - 22:00", True, (255, 80, 60))
        s.blit(banner, (W // 2 - banner.get_width() // 2, H // 2 - 40))
        sub = FONT_TAG.render("SUBJECT: ROUTE 12 PERPETRATOR", True, (200, 170, 150))
        s.blit(sub, (W // 2 - sub.get_width() // 2, H // 2 + 10))
        pygame.draw.rect(s, (180, 30, 30), (W // 2 - 90, H // 2 - 70, 180, 3))
        config.screen.blit(s, (0, 0))
        feed()
        FRAME[0] += 1


def _draw_retardovici_mark(s, cx, top_y, scale=1.0):
    """Compact static version of the studio R mark (see app.py
    _draw_retardovici_r_logo, which is animated and bound to the boot flow).
    Heavy single-R stem + bowl + diagonal leg, red slash accent, corner
    brackets. Returns the y just below the mark."""
    lw, lh = int(200 * scale), int(150 * scale)
    logo = pygame.Surface((lw, lh), pygame.SRCALPHA)
    dark = (232, 238, 235)
    red = (168, 28, 24)
    k = scale
    # Stem.
    pygame.draw.rect(logo, dark, (int(40 * k), int(24 * k),
                                  int(27 * k), int(102 * k)))
    # Bowl: top bar + rounded right shoulder + middle bar.
    pygame.draw.rect(logo, dark, (int(61 * k), int(24 * k),
                                  int(72 * k), int(24 * k)))
    pygame.draw.rect(logo, dark, (int(113 * k), int(48 * k),
                                  int(29 * k), int(37 * k)),
                     border_radius=int(15 * k))
    pygame.draw.rect(logo, dark, (int(61 * k), int(82 * k),
                                  int(63 * k), int(19 * k)))
    pygame.draw.rect(logo, dark, (int(92 * k), int(50 * k),
                                  int(30 * k), int(33 * k)))
    # Diagonal lower leg.
    pygame.draw.polygon(logo, dark, [(int(61 * k), int(96 * k)),
                                     (int(86 * k), int(96 * k)),
                                     (int(130 * k), int(132 * k)),
                                     (int(103 * k), int(132 * k))])
    # Red diagonal accent.
    pygame.draw.polygon(logo, red, [(int(28 * k), int(136 * k)),
                                    (int(72 * k), int(62 * k)),
                                    (int(81 * k), int(67 * k)),
                                    (int(44 * k), int(141 * k))])
    # Corner brackets.
    bl = int(32 * k)
    for sx, sy, dx, dy in [(int(26 * k), int(20 * k), 1, 0),
                            (int(26 * k), int(20 * k), 0, 1),
                            (int(174 * k), int(20 * k), -1, 0),
                            (int(174 * k), int(20 * k), 0, 1),
                            (int(26 * k), int(130 * k), 1, 0),
                            (int(26 * k), int(130 * k), 0, -1),
                            (int(174 * k), int(130 * k), -1, 0),
                            (int(174 * k), int(130 * k), 0, -1)]:
        pygame.draw.line(logo, (142, 34, 30), (sx, sy),
                         (sx + dx * bl, sy + dy * bl), 2)
    s.blit(logo, (cx - lw // 2, top_y))
    return top_y + lh


def end_card(seconds, fade_out_seconds=1.0):
    # Studio lockup. The game is NOT on Steam: no wishlist / demo /
    # social-handle lines - just the title, the tagline, the studio mark
    # and an official copyright strip.
    total = int(seconds * FPS)
    fade_frames = int(fade_out_seconds * FPS)
    for i in range(total):
        s = pygame.Surface((W, H))
        s.fill((4, 5, 6))
        pygame.draw.rect(s, (255, 120, 0), (W // 2 - 90, H // 2 - 170, 180, 3))
        y = H // 2 - 130
        title = FONT_BIG.render("CALL OF ACARISTAN", True, (232, 222, 190))
        s.blit(title, (W // 2 - title.get_width() // 2, y))
        y += title.get_height() + 10
        tagline = FONT_TAG.render("THE VOSTRAL IS REAL", True, (255, 120, 0))
        s.blit(tagline, (W // 2 - tagline.get_width() // 2, y))
        y += tagline.get_height() + 18
        y = _draw_retardovici_mark(s, W // 2, y, scale=0.62)
        y += 12
        studio = FONT_MID.render("RETARDOVICI INC.", True, (232, 238, 235))
        s.blit(studio, (W // 2 - studio.get_width() // 2, y))
        y += studio.get_height() + 10
        copyr = FONT_CAP.render(
            "COPYRIGHT RETARDOVICI INC. 2026-20XX - ALL RIGHTS RESERVED",
            True, (150, 170, 150))
        s.blit(copyr, (W // 2 - copyr.get_width() // 2, y))
        if fade_frames > 0 and i >= total - fade_frames:
            a = int(255 * (i - (total - fade_frames) + 1) / max(1, fade_frames))
            fade = pygame.Surface((W, H), pygame.SRCALPHA)
            fade.fill((0, 0, 0, max(0, min(255, a))))
            s.blit(fade, (0, 0))
        config.screen.blit(s, (0, 0))
        feed()
        FRAME[0] += 1


def _apply_muzzle_flash():
    # PLAN_4 §2.1: trailer-only 110% exposure bump for 1 frame on muzzle
    # flash. Reads STATE timers set by game code, never writes gameplay state.
    try:
        active = (int(getattr(STATE, "muzzle_flash_timer", 0) or 0) > 0
                  or int(getattr(STATE, "gc_flash_timer", 0) or 0) > 0)
    except Exception:
        active = False
    if active:
        flash = pygame.Surface((W, H), pygame.SRCALPHA)
        flash.fill((255, 240, 220, 25))
        config.screen.blit(flash, (0, 0),
                           special_flags=pygame.BLEND_RGBA_ADD)


def top_up():
    p = getattr(STATE, "player", None)
    if p is not None:
        try:
            p.hp = p.max_hp
        except Exception:
            pass
    try:
        if hasattr(STATE, "k9_ammo_in_mag") and hasattr(STATE, "k9_mag_size"):
            STATE.k9_ammo_in_mag = STATE.k9_mag_size
    except Exception:
        pass


def _m2_extras():
    if getattr(STATE, "active_mission", "") != "MISSION2":
        return []
    return (list(getattr(STATE, "mission2_vehicle_walls", []) or [])
            + list(getattr(STATE, "mission2_prop_walls", []) or []))


def los_walls():
    w = weapons._solid_walls()
    w += _m2_extras()
    return w


def has_los(x1, y1, x2, y2, walls):
    return not weapons._wall_blocks_line(x1, y1, x2, y2, walls)


def visible_enemy(max_d=620):
    p = getattr(STATE, "player", None)
    if p is None:
        return None
    px, py = p.rect.center
    walls = los_walls()
    cands = []
    for e in getattr(STATE, "enemies", []) or []:
        if getattr(e, "hp", 0) <= 0:
            continue
        d = math.hypot(e.rect.centerx - px, e.rect.centery - py)
        if d <= max_d:
            cands.append((d, e))
    for d, e in sorted(cands, key=lambda c: c[0]):
        if has_los(px, py, e.rect.centerx, e.rect.centery, walls):
            return e
    return None


def combat_pre():
    e = visible_enemy()
    if e is None or getattr(STATE, "player", None) is None:
        return None
    if (FRAME[0] // 25) % 2:
        KEYS.down.add(pygame.K_a)
    else:
        KEYS.down.add(pygame.K_d)
    return e


def combat_post(e):
    if e is None or getattr(STATE, "player", None) is None:
        return False
    if getattr(e, "hp", 0) <= 0:
        return False
    px, py = STATE.player.rect.center
    ex, ey = e.rect.centerx, e.rect.centery
    if not has_los(px, py, ex, ey, los_walls()):
        return False
    pvx, pvy = PREV.get(getattr(e, "uid", id(e)), (ex, ey))
    evx, evy = ex - pvx, ey - pvy
    PREV[getattr(e, "uid", id(e))] = (ex, ey)
    dist = math.hypot(ex - px, ey - py)
    lead = dist / 24.0
    STATE.player.angle = math.atan2(ey + evy * lead - py, ex + evx * lead - px)
    if (FRAME[0] // 2) % 10 < 6:
        try:
            weapons.handle_shoot()
        except Exception:
            pass
    return True


def build_grid(tmap, solids):
    return [[tmap[y][x] not in solids for x in range(len(tmap[0]))]
            for y in range(len(tmap))]


def overlay_rects(grid, rects):
    for r in rects:
        if r is None:
            continue
        x0, y0 = r.x // T, r.y // T
        x1 = (r.x + r.width - 1) // T
        y1 = (r.y + r.height - 1) // T
        for ty in range(max(0, y0), min(len(grid), y1 + 1)):
            row = grid[ty]
            for tx in range(max(0, x0), min(len(row), x1 + 1)):
                row[tx] = False


class Router:
    def __init__(self, goals, grid, pos_fn, grid_fn=None):
        self.goals = list(goals)
        self.grid = grid
        self.grid_fn = grid_fn
        self.pos_fn = pos_fn
        self.tmap = None
        self.wps = []
        self.i = 0
        self.stuck = 0
        self.last = None
        self.jit = 0
        self.jit_total = 0

    def refresh(self):
        if self.grid_fn is not None:
            self.grid = self.grid_fn()

    def _route(self):
        pos = self.pos_fn()
        if not self.goals or pos is None:
            return
        gx, gy = self.goals.pop(0)
        px, py = pos
        path = _astar((int(px // T), int(py // T)), (gx, gy), self.grid)
        kept = []
        for idx, (x, y) in enumerate(path):
            if (0 < idx < len(path) - 1 and self.tmap is not None
                    and self.tmap[y][x] == "D"):
                (ax, ay), (bx, by) = path[idx - 1], path[idx + 1]
                if (ax - x, ay - y) == (x - bx, y - by):
                    continue
            kept.append((x * T + T // 2, y * T + T // 2))
        self.wps = kept or [(gx * T + T // 2, gy * T + T // 2)]
        self.i = 0
        self.stuck = 0

    def done(self):
        return not self.goals and self.i >= len(self.wps)

    def target(self):
        if self.i < len(self.wps):
            return self.wps[self.i]
        if self.goals:
            gx, gy = self.goals[0]
            return (gx * T + T // 2, gy * T + T // 2)
        return None

    def step(self):
        if self.i >= len(self.wps) and self.goals:
            self._route()
        if self.i >= len(self.wps):
            KEYS.down.clear()
            return
        pos = self.pos_fn()
        if pos is None:
            KEYS.down.clear()
            return
        px, py = pos
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
            self.jit_total += 1
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


def player_pos():
    p = getattr(STATE, "player", None)
    return p.rect.center if p is not None else None


def walk_pos():
    wp = ws.walk_player
    return wp.rect.center if wp is not None else None


def face_player(tx, ty):
    p = getattr(STATE, "player", None)
    if p is None:
        return
    px, py = p.rect.center
    if math.hypot(tx - px, ty - py) > 4:
        p.angle = math.atan2(ty - py, tx - px)


def run_gameplay(seconds, router, fight=True):
    cam = [0, 0]
    total = int(seconds * 60)
    for tick in range(total):
        top_up()
        if tick % 60 == 0:
            router.refresh()
        router.step()
        foe = combat_pre() if fight else None
        out = gc.game_update(KEYS)
        if out:
            cam[0], cam[1] = out
        engaged = combat_post(foe) if fight else False
        if not engaged:
            tgt = router.target()
            if tgt is not None:
                face_player(*tgt)
        gc.game_draw(cam[0], cam[1])
        _apply_muzzle_flash()
        pygame.event.pump()
        FRAME[0] += 1
        if FRAME[0] % 2 == 0:
            feed()
    return router.jit_total


def run_walk(seconds, router):
    total = int(seconds * 60)
    for tick in range(total):
        if tick % 60 == 0:
            router.refresh()
        router.step()
        try:
            ws.update_walking_sim(KEYS)
        except Exception:
            pass
        ws.draw_walking_sim()
        pygame.event.pump()
        FRAME[0] += 1
        if FRAME[0] % 2 == 0:
            feed()
    return router.jit_total


TOURS = {
    "m1": [("C", "W", "D"), "m1", [(8, 2), (8, 8), (8, 11), (10, 14), (13, 16), (15, 17), (15, 18), (14, 20), (22, 21)]],
    "m2": [("C", "B", "T"), "m2", [(14, 72), (22, 68), (30, 62), (24, 58)]],
    "m2sniper": [("C", "B", "T"), "m2", [(48, 28), (52, 30), (58, 28), (50, 26)]],
    "m3break": [("C", "B", "S", "D"), "cell", [(33, 8), (35, 10), (31, 10), (31, 7)]],
    "m3comms": [("C", "B", "S", "D"), "comms", [(8, 21), (8, 23), (14, 24), (17, 24)]],
    "m3arch": [("C", "B", "S", "D"), "archives", [(24, 38), (24, 30), (24, 22), (24, 13), (24, 12), (30, 10), (36, 9), (42, 9)]],
    "m3ko": [("C", "g", "B"), "ko", [(5, 8), (9, 13), (19, 12)]],
    "walk": [("C", "W"), "walk", [(10, 2), (16, 2), (22, 2)]],
}


def tour_grid(map_key):
    if map_key == "m1":
        from missions.m1 import map as m1map
        return m1map.mission1_map
    if map_key == "m2":
        from missions.m2 import world as m2w
        return m2w.MISSION2_MAP
    if map_key in ("cell", "comms", "archives", "ko"):
        from missions.m3 import maps as M
        return {"cell": M.MISSION3_CELL_MAP, "comms": M.MISSION3_COMMS_MAP,
                "archives": M.MISSION3_ARCHIVES_MAP, "ko": M.MISSION3_KILL_ORDER_MAP}[map_key]
    if map_key == "walk":
        return ws.walk_map
    raise KeyError(map_key)


def router_colliders():
    rects = list(getattr(STATE, "walls", []) or [])
    rects += _m2_extras()
    for d in getattr(STATE, "doors", []) or []:
        if getattr(d, "locked", False) and getattr(d, "collision_rect", None):
            rects.append(d.collision_rect)
    return rects


def make_router(section_key):
    solids, map_key, goals = TOURS[section_key]
    tmap = tour_grid(map_key)
    use_colliders = section_key != "walk"

    def grid_fn():
        g = build_grid(tmap, solids)
        if use_colliders:
            overlay_rects(g, router_colliders())
        return g

    pos_fn = walk_pos if section_key == "walk" else player_pos
    r = Router(goals, grid_fn(), pos_fn, grid_fn=grid_fn)
    r.tmap = tmap
    return r


SECTIONS = [
    ("m1", gc.start_mission, 10.0, "game"),
    ("m2", gc.start_mission2, 8.0, "game"),
    ("m2sniper", gc.start_mission2_sniper, 7.0, "game"),
    ("m3break", gc.start_mission3_breakout_checkpoint, 7.0, "game"),
    ("m3comms", gc.start_mission3_comms_checkpoint, 6.0, "game"),
    ("m3arch", gc.start_mission3_archives_checkpoint, 6.0, "game"),
    ("m3ko", gc.start_mission3_kill_order_checkpoint, 7.0, "game"),
]


def open_pipe(out_path):
    proc = subprocess.Popen(
        [str(FFMPEG), "-y", "-f", "rawvideo", "-vcodec", "rawvideo",
         "-s", f"{W}x{H}", "-pix_fmt", "rgb24", "-r", str(FPS),
         "-i", "-", "-an", "-c:v", "libx264", "-pix_fmt", "yuv420p",
         "-crf", "18", "-preset", "medium", "-movflags", "+faststart",
         str(out_path)],
        stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    return proc


def mux_1080p_with_music(silent_mp4, music_mp3, out_mp4):
    cmd = [
        str(FFMPEG), "-y", "-i", str(silent_mp4), "-i", str(music_mp3),
        "-filter_complex",
        "[0:v]scale=1920:1080:force_original_aspect_ratio=decrease,"
        "pad=1920:1080:(ow-iw)/2:(oh-ih)/2,format=yuv420p[v]",
        "-map", "[v]", "-map", "1:a",
        "-c:v", "libx264", "-crf", "18", "-preset", "medium",
        "-c:a", "aac", "-b:a", "160k", "-shortest",
        "-movflags", "+faststart", str(out_mp4),
    ]
    r = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"audio mux failed: {r.stderr[-2000:]}")


def export_vertical(silent_mp4, music_mp3, out_vertical, with_audio=True):
    # PLAN_4 §2.1/§4: 9:16 center-crop vertical for Shorts/TikTok.
    # 608x1080 center crop of the 1920x1080 master (gameplay effectively
    # punched in; end-card lines were laid out center-safe so they survive).
    # Non-fatal: trailer succeeds even if this fails.
    try:
        if with_audio and Path(str(music_mp3)).exists():
            cmd = [
                str(FFMPEG), "-y", "-i", str(silent_mp4), "-i", str(music_mp3),
                "-filter_complex",
                "[0:v]scale=1920:1080:force_original_aspect_ratio=decrease,"
                "pad=1920:1080:(ow-iw)/2:(oh-ih)/2,"
                "crop=608:1080:(in_w-608)/2:(in_h-1080)/2,format=yuv420p[v]",
                "-map", "[v]", "-map", "1:a",
                "-c:v", "libx264", "-crf", "20", "-preset", "medium",
                "-c:a", "aac", "-b:a", "128k", "-shortest",
                "-movflags", "+faststart", str(out_vertical),
            ]
        else:
            cmd = [
                str(FFMPEG), "-y", "-i", str(silent_mp4),
                "-vf",
                "scale=1920:1080:force_original_aspect_ratio=decrease,"
                "pad=1920:1080:(ow-iw)/2:(oh-ih)/2,"
                "crop=608:1080:(in_w-608)/2:(in_h-1080)/2,format=yuv420p",
                "-c:v", "libx264", "-crf", "20", "-preset", "medium",
                "-an", "-movflags", "+faststart", str(out_vertical),
            ]
        r = subprocess.run(cmd, stdout=subprocess.DEVNULL,
                           stderr=subprocess.PIPE, text=True)
        if r.returncode != 0:
            print(f"vertical export skipped: {r.stderr[-500:]}")
        else:
            print("saved vertical", out_vertical,
                  Path(str(out_vertical)).stat().st_size // 1024, "KB")
    except Exception as e:
        print(f"vertical export skipped: {e!r}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--smoke", action="store_true", help="fast ~15s check render")
    ap.add_argument("--no-audio", action="store_true", help="skip music mux")
    ap.add_argument("--out", default="trailer_60s.mp4")
    args = ap.parse_args()

    smoke = args.smoke
    if smoke:
        out_silent = TRAILERS / "trailer_smoke_silent.mp4"
        out_final = TRAILERS / "trailer_smoke.mp4"
    else:
        out_silent = TRAILERS / "trailer_60s_silent.mp4"
        out_final = TRAILERS / args.out

    PROC[0] = open_pipe(out_silent)

    def sec_seconds(base):
        return 1.0 if smoke else base

    def card_seconds(base):
        return 0.6 if smoke else base

    # PLAN_4 §3: cold open replaces black 1.5s -> card 3.0s -> black 0.8s -> menu.
    boot_intro(card_seconds(1.0))
    broadcast_card(card_seconds(2.0))
    card(["CALL OF ACARISTAN", "a tactical trilogy in three missions"],
         card_seconds(1.8), tag="OFFICIAL TRAILER" if not smoke else "SMOKE CHECK",
         flash_first=True)

    for key, starter, secs, mode in SECTIONS:
        print(f"[{key}] ({sec_seconds(secs):.1f}s)", flush=True)
        PREV.clear()
        KEYS.down.clear()
        FRAME[0] = 0
        try:
            if mode == "walk":
                starter()
                jit = run_walk(sec_seconds(secs), make_router(key))
                print(f"  jit_events={jit}", flush=True)
            else:
                starter()
                # PLAN_4 §2.1: 60-tick pre-roll so first fed frame is
                # mid-action, never spawn idle (5 ticks in smoke for speed).
                pre_roll = 5 if smoke else 60
                for _ in range(pre_roll):
                    top_up()
                    out = gc.game_update(KEYS)
                    if out:
                        gc.game_draw(out[0], out[1])
                jit = run_gameplay(sec_seconds(secs), make_router(key), fight=True)
                print(f"  jit_events={jit}", flush=True)
        except Exception as e:
            print(f"  !! section {key} failed: {e!r} (tape keeps rolling)")
            import traceback
            traceback.print_exc()

    black_frame(card_seconds(1.0))
    end_card(card_seconds(4.0), fade_out_seconds=card_seconds(1.0))

    PROC[0].stdin.close()
    PROC[0].wait()
    print("silent tape:", out_silent, out_silent.stat().st_size // 1024, "KB")

    if smoke:
        import numpy as np  # noqa: F401
        print("smoke final:", out_final)
        out_silent.replace(out_final)
        print("saved", out_final, out_final.stat().st_size // 1024, "KB")
        return

    if args.no_audio:
        out_silent.replace(out_final)
        print("saved (silent)", out_final, out_final.stat().st_size // 1024, "KB")
        return

    music = ROOT / "menu_theme.mp3"
    if not music.exists():
        print("menu_theme.mp3 missing - shipping silent")
        out_silent.replace(out_final)
        return
    mux_1080p_with_music(out_silent, music, out_final)
    print("saved", out_final, out_final.stat().st_size // 1024, "KB")
    out_vertical = out_final.with_name(out_final.stem + "_vertical.mp4")
    export_vertical(out_silent, music, out_vertical, with_audio=True)


if __name__ == "__main__":
    main()

