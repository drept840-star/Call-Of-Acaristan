"""Mission 7 top-down farmyard: beat 2 (chores); beat 4 (prep) reuses the map.

The stage is peaceful: walk, press E at the marked spots, talk to Bodi.  Static
scenery is baked once per ``begin``; the figures, animals and the few things
that change are drawn per frame.
"""
import math

import pygame

from core.config import HEIGHT, WIDTH, audio as _audio_manager, font_prompt, font_terminal_small
from core.state import STATE
from engine.core import now_ms as _now_ms
from entities.player import Player

from . import m7_audio as _m7_audio
from . import minigames as G
from . import maps as M

T = M.TILE
OX, OY = M.ORIGIN
CHORES = "chores"
PREP = "prep"
FARM_STAGES = (CHORES, PREP)
CHORES_NEEDED = ("generator", "water", "feed")
PREP_ITEMS = ("tractor", "shed", "loft")
PREP_PICKS = 2
CHAR_MS = 26
SPEED = 3.0

_S = {}
_TILES = {}
_TRACTOR_ROT = {}


def _snd():
    return _m7_audio.instance(_audio_manager)

_LOOKS = {
    "biribel": dict(torso=(40, 42, 52), arm=(34, 36, 46), legs=(30, 32, 40), boots=(20, 20, 24),
                    hair=(34, 26, 22), skin=(200, 156, 116), patch=(70, 120, 190)),
    "bodi": dict(torso=(126, 72, 48), arm=(116, 66, 44), legs=(60, 74, 112), boots=(70, 56, 40),
                 hair=(36, 30, 26), skin=(206, 164, 124), patch=None),
    "alex": dict(torso=(56, 96, 180), arm=(50, 88, 170), legs=(74, 88, 124), boots=(226, 226, 230),
                 hair=(128, 90, 62), skin=(212, 172, 132), patch=None),
}
_GOATS = (
    ((10.9, 8.0), (226, 220, 206), 0.0),
    ((12.3, 8.2), (150, 146, 140), 2.1),
    ((13.0, 7.7), (142, 98, 66), 4.0),
)


# -- baking ---------------------------------------------------------------

def _rng(seed):
    s = seed & 0x7FFFFFFF
    while True:
        s = (s * 1103515245 + 12345) & 0x7FFFFFFF
        yield s >> 8


def _inside(c, r, box):
    return box[0] <= c < box[0] + box[2] and box[1] <= r < box[1] + box[3]


def _ground_kind(c, r, ch):
    if _inside(c, r, M.BARN_INSIDE) or (c, r) == (11, 3):
        return "hay"
    if _inside(c, r, M.PEN):
        return "pen"
    if ch == ":" or (r >= 8 and 6 <= c <= 8):
        return "track"
    if ch == "#" or (r <= 3 and not 6 <= c <= 8):
        return "grass"
    return "dirt"


_PALETTES = {"grass": M.GRASS, "dirt": M.DIRT, "pen": M.PENDIRT, "track": M.TRACK, "hay": M.HAYFLOOR}


def _ground_tile(kind, variant):
    key = (kind, variant)
    tile = _TILES.get(key)
    if tile is None:
        base, dark, light = _PALETTES[kind]
        tile = pygame.Surface((T, T))
        tile.fill(base)
        rnd = _rng(variant * 7919 + len(kind) * 131)
        for _ in range(10):
            x, y = next(rnd) % (T - 9), next(rnd) % (T - 9)
            col = dark if next(rnd) % 3 else light
            if kind == "grass":
                tile.fill(col, (x, y, 2, 5))
            elif kind == "hay":
                tile.fill(col, (x, y, 9, 2))
            else:
                tile.fill(col, (x, y, 4, 2))
        if kind == "track":
            tile.fill(dark, (12, 0, 8, T))
            tile.fill(dark, (44, 0, 8, T))
        _TILES[key] = tile
    return tile


def _shadow(surf, rect, off=8):
    s = pygame.Surface(rect.size, pygame.SRCALPHA)
    s.fill((0, 0, 0, 70))
    surf.blit(s, (rect.x + off, rect.y + off))


def _fence(surf, grid, c, r):
    x, y = c * T, r * T
    cx, cy = x + T // 2, y + T // 2

    def linked(cc, rr):
        return 0 <= rr < len(grid) and 0 <= cc < len(grid[rr]) and grid[rr][cc] in "#f"

    for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
        if not linked(c + dx, r + dy):
            continue
        if dx:
            x0 = cx if dx > 0 else x
            surf.fill(M.WOOD, (x0, cy - 3, T // 2, 6))
            surf.fill(M.WOOD_L, (x0, cy - 3, T // 2, 2))
        else:
            y0 = cy if dy > 0 else y
            surf.fill(M.WOOD, (cx - 3, y0, 6, T // 2))
            surf.fill(M.WOOD_L, (cx - 3, y0, 2, T // 2))
    surf.fill(M.WOOD_D, (cx - 6, cy - 6, 12, 12))
    surf.fill(M.WOOD_L, (cx - 4, cy - 4, 8, 8))


def _house(surf):
    c, r, w, h = M.HOUSE
    box = pygame.Rect(c * T, r * T, w * T, h * T)
    _shadow(surf, box)
    pygame.draw.rect(surf, M.INK, box)
    roof = pygame.Rect(box.x + 4, box.y + 4, box.w - 8, box.h - 22)
    surf.fill(M.ROOF, roof)
    for yy in range(roof.y + 12, roof.bottom - 4, 14):
        surf.fill(M.ROOF_D, (roof.x, yy, roof.w, 2))
    surf.fill(M.ROOF_L, (roof.x, roof.centery - 3, roof.w, 6))
    surf.fill(M.ROOF_D, (roof.x, roof.centery + 3, roof.w, 2))
    chim = pygame.Rect(roof.right - 48, roof.y + 12, 26, 26)
    pygame.draw.rect(surf, M.STONE_D, chim)
    surf.fill(M.STONE, chim.inflate(-8, -8))
    surf.fill((30, 28, 28), chim.inflate(-16, -16))
    wall = pygame.Rect(box.x + 4, box.bottom - 18, box.w - 8, 14)
    surf.fill((206, 190, 156), wall)
    for col in (2, 3, 5):
        surf.fill((60, 86, 112), (col * T + 25, wall.y + 3, 14, 8))
    surf.fill(M.WOOD_D, (4 * T + 14, wall.y - 2, 36, 16))
    surf.fill(M.WOOD, (4 * T + 17, wall.y + 1, 30, 13))
    surf.fill((220, 190, 90), (4 * T + 41, wall.y + 7, 3, 3))
    # porch boards, walkable
    for i in range(3 * T // 16):
        surf.fill(M.WOOD if i % 2 else M.WOOD_L, (3 * T + i * 16, 4 * T, 16, 26))
    surf.fill(M.INK, (3 * T, 4 * T + 26, 3 * T, 2))


def _barn(surf, grid):
    c, r, w, h = M.BARN
    box = pygame.Rect(c * T, r * T, w * T, h * T)
    _shadow(surf, box)
    for rr, row in enumerate(grid):
        for cc, ch in enumerate(row):
            if ch != "B":
                continue
            x, y = cc * T, rr * T
            surf.fill(M.BARN_WALL, (x, y, T, T))
            for i in range(0, T, 16):
                surf.fill((84, 44, 38), (x + i, y, 2, T))
            surf.fill((140, 80, 66), (x, y, T, 3))
    pygame.draw.rect(surf, M.INK, box, 3)
    inner = pygame.Rect(M.BARN_INSIDE[0] * T, M.BARN_INSIDE[1] * T,
                        M.BARN_INSIDE[2] * T, M.BARN_INSIDE[3] * T)
    pygame.draw.rect(surf, (60, 34, 30), inner.inflate(4, 4), 3)
    surf.fill(M.WOOD_D, (11 * T - 6, 3 * T, 8, T))
    surf.fill(M.WOOD_D, (12 * T - 2, 3 * T, 8, T))
    for i in range(3):
        surf.fill(M.HAYFLOOR[2], (10 * T + 10 + i * 12, 1 * T + 8, 8, 20))
        surf.fill(M.HAYFLOOR[1], (10 * T + 10 + i * 12, 1 * T + 26, 8, 4))


def _well(surf):
    cx, cy = M.tile_px(M.POINTS["well"]["at"])
    pygame.draw.circle(surf, M.INK, (cx, cy), 30)
    pygame.draw.circle(surf, M.STONE, (cx, cy), 27)
    pygame.draw.circle(surf, M.STONE_D, (cx, cy), 20)
    pygame.draw.circle(surf, M.WATER, (cx, cy), 15)
    surf.fill((120, 160, 188), (cx - 8, cy - 8, 6, 3))
    surf.fill(M.WOOD_D, (cx - 34, cy - 5, 9, 10))
    surf.fill(M.WOOD_D, (cx + 25, cy - 5, 9, 10))
    surf.fill(M.WOOD, (cx - 28, cy - 2, 56, 4))


def _tractor_surface():
    """Top-down tractor facing east, nose right, in a 128x64 cell."""
    surf = pygame.Surface((128, 64), pygame.SRCALPHA)
    for wx, wy, ww, wh in ((8, 0, 30, 15), (8, 49, 30, 15), (92, 3, 20, 11), (92, 50, 20, 11)):
        surf.fill(M.INK, (wx, wy, ww, wh))
        for i in range(0, ww, 6):
            surf.fill((52, 52, 56), (wx + i, wy + 2, 3, wh - 4))
    surf.fill(M.TRACTOR_D, (6, 14, 116, 36))
    surf.fill(M.TRACTOR, (8, 16, 112, 32))
    surf.fill(M.TRACTOR_D, (70, 20, 50, 24))
    surf.fill((44, 38, 36), (22, 20, 38, 24))
    surf.fill((76, 66, 58), (26, 24, 30, 16))
    surf.fill(M.METAL_D, (54, 29, 8, 5))
    surf.fill(M.METAL, (112, 22, 5, 5))
    return surf


def _tractor_draw(surf, cx, cy, ang):
    step = int(round(ang / 22.5)) % 16
    base = _TRACTOR_ROT.get(-1)
    if base is None:
        base = _TRACTOR_ROT[-1] = _tractor_surface()
    img = _TRACTOR_ROT.get(step)
    if img is None:
        img = pygame.transform.rotate(base, -step * 22.5)
        _TRACTOR_ROT[step] = img
    shade = pygame.Surface((112, 44), pygame.SRCALPHA)
    pygame.draw.ellipse(shade, (0, 0, 0, 80), shade.get_rect())
    surf.blit(shade, shade.get_rect(center=(int(cx), int(cy) + 6)))
    surf.blit(img, img.get_rect(center=(int(cx), int(cy))))


def _shed(surf):
    box = pygame.Rect(1 * T, 7 * T, 3 * T, T)
    _shadow(surf, box, 6)
    pygame.draw.rect(surf, M.INK, box)
    roof = box.inflate(-6, -6)
    surf.fill(M.METAL, roof)
    for xx in range(roof.x + 6, roof.right, 14):
        surf.fill(M.METAL_D, (xx, roof.y, 3, roof.h))
    for bx in (1 * T + 18, 1 * T + 46):
        pygame.draw.circle(surf, M.INK, (bx, 8 * T + 16), 14)
        pygame.draw.circle(surf, (168, 52, 40), (bx, 8 * T + 16), 12)
        pygame.draw.circle(surf, (120, 36, 30), (bx, 8 * T + 16), 6)


def _bin(surf):
    cx, cy = M.tile_px(M.POINTS["bin"]["at"])
    x, y = cx - T // 2, cy - T // 2
    _shadow(surf, pygame.Rect(x + 6, y + 10, 52, 44), 5)
    surf.fill(M.INK, (x + 5, y + 9, 54, 46))
    surf.fill(M.WOOD, (x + 7, y + 11, 50, 42))
    surf.fill(M.GRAIN, (x + 13, y + 17, 38, 30))
    for i in range(3):
        surf.fill((166, 136, 70), (x + 13, y + 22 + i * 9, 38, 2))
    surf.fill(M.WOOD_L, (x + 7, y + 11, 50, 4))


def _bike(surf):
    """Alex's dirt bike seen from above, nose up."""
    cx, cy = M.tile_px(M.BIKE_AT)
    _shadow(surf, pygame.Rect(cx - 7, cy - 26, 14, 52), 4)
    for wy in (-27, 15):
        surf.fill(M.INK, (cx - 5, cy + wy, 10, 13))
        surf.fill((74, 74, 80), (cx - 3, cy + wy + 1, 6, 11))
    surf.fill(M.INK, (cx - 7, cy - 14, 14, 30))
    surf.fill((232, 112, 30), (cx - 5, cy - 11, 10, 14))
    surf.fill((38, 34, 34), (cx - 4, cy + 4, 8, 11))
    surf.fill(M.METAL, (cx - 13, cy - 19, 26, 3))
    surf.fill(M.INK, (cx - 13, cy - 19, 3, 3))
    surf.fill(M.INK, (cx + 10, cy - 19, 3, 3))


def _build_static(grid, stage):
    surf = pygame.Surface((M.COLS * T, M.ROWS * T))
    for r, row in enumerate(grid):
        for c, ch in enumerate(row):
            kind = _ground_kind(c, r, ch)
            surf.blit(_ground_tile(kind, (c * 3 + r * 5) % 4), (c * T, r * T))
    for r, row in enumerate(grid):
        for c, ch in enumerate(row):
            if ch in "#f":
                _fence(surf, grid, c, r)
    _house(surf)
    _barn(surf, grid)
    _well(surf)
    _shed(surf)
    _bin(surf)
    if stage == PREP:
        _bike(surf)
    return surf


# -- state ----------------------------------------------------------------

def _bodi_tile():
    return M.LOFT_TILE if "loft" in _S["preps"] else ((4.5, 5.5) if _S["stage"] == PREP else M.BODI_TILE)


def _make_walls():
    moved = "tractor" in _S["preps"]
    walls = [pygame.Rect(c * T, r * T, T, T)
             for r, row in enumerate(_S["grid"]) for c, ch in enumerate(row)
             if ch in M.SOLID and not (moved and ch == "T")]
    bx, by = M.tile_px(_bodi_tile())
    walls.append(pygame.Rect(bx - 14, by - 6, 28, 22))
    if _S["stage"] == PREP:
        ax, ay = M.tile_px(M.ALEX_TILE)
        walls.append(pygame.Rect(ax - 14, ay - 6, 28, 22))
        kx, ky = M.tile_px(M.BIKE_AT)
        walls.append(pygame.Rect(kx - 10, ky - 28, 20, 56))
    if moved:
        walls.append(pygame.Rect(6 * T, M.TRACTOR_PARK[1] + 10, 3 * T, 44))
    STATE.walls = walls


def begin(stage, on_done):
    grid = M.farm_grid()
    STATE.enemies, STATE.bullets, STATE.particles, STATE.doors = [], [], [], []
    px, py = M.tile_px(M.PLAYER_TILE)
    STATE.player = Player(px - 16, py - 16)
    STATE.camera_x, STATE.camera_y = 0, 0
    STATE.m7_preps = []
    _S.clear()
    _S.update(
        stage=stage, on_done=on_done, grid=grid, static=_build_static(grid, stage), now=_now_ms(),
        done=set(), carry=None, gen_on=False, gen_hint=False, genplay=None, e_prev=False,
        trough={"water": False, "feed": False}, crate=False, lines=[], line_t0=0, after=None,
        toast=("", 0), prev_adv=False, face="d", step=0.0, near=None, finished=False,
        preps=[], tick_n=0, life_t=_now_ms() + 2500, life_i=0, life_gap=6000,
        step_ph=0)
    _S["crate"] = stage == PREP and bool(STATE.m7_crate)
    _make_walls()
    if stage == PREP:
        _say([("", "Two Guard trucks on the valley road, trailing dust up the hill."),
              ("ALEX", "Twenty minutes, maybe less. Whatever you're doing, do it fast."),
              ("BODI", "The farm can spare two things. Choose well.")])


def active():
    return bool(_S)


def _toast(text, ms=2600):
    _S["toast"] = (text, _now_ms() + ms)


def _say(lines, after=None):
    _S["lines"] = list(lines)
    _S["line_t0"] = _now_ms()
    _S["tick_n"] = 0
    _S["after"] = after


def _advance_line():
    text = _S["lines"][0][1]
    now = _now_ms()
    if (now - _S["line_t0"]) // CHAR_MS < len(text):
        _S["line_t0"] = now - len(text) * CHAR_MS - 1
        return
    _S["lines"].pop(0)
    _S["line_t0"] = now
    _S["tick_n"] = 0
    if not _S["lines"]:
        after, _S["after"] = _S["after"], None
        if after:
            after()


def _finish():
    _S["finished"] = True
    _S["on_done"]()


def _chores_done():
    return all(k in _S["done"] for k in CHORES_NEEDED)


# -- interaction ------------------------------------------------------------

def _point_px(pid):
    if pid == "bodi":
        return M.tile_px(_bodi_tile())
    if pid == "alex":
        return M.tile_px(M.ALEX_TILE)
    return M.tile_px(M.POINTS[pid]["at"])


def _reach(pid):
    return 70 if pid in ("bodi", "alex") else M.POINTS[pid]["reach"]


def _preps_open():
    """Prep items the player may still pick (none once two are chosen)."""
    if len(_S["preps"]) >= PREP_PICKS:
        return []
    return [k for k in PREP_ITEMS if k not in _S["preps"]]


def _available():
    """(point id, prompt label) for everything usable right now."""
    if _S["stage"] == PREP:
        out = [("alex", "TALK TO ALEX")]
        pick = _preps_open()
        out.append(("bodi", "SEND BODI TO THE HAYLOFT" if "loft" in pick else "TALK"))
        if "tractor" in pick:
            out.append(("tractor", "BLOCK THE TRACK"))
        if "shed" in pick:
            out.append(("shed", "RIG THE FUEL SHED"))
        return out
    done, carry = _S["done"], _S["carry"]
    out = [("bodi", "TALK")]
    if not _S["gen_on"]:
        out.append(("generator", "START THE GENERATOR"))
    if "water" not in done and carry is None:
        out.append(("well", "DRAW WATER"))
    if "feed" not in done and carry is None:
        out.append(("bin", "TAKE FEED"))
    if carry:
        out.append(("trough", "FILL THE TROUGH"))
    if not _S["crate"]:
        out.append(("hay", "SEARCH THE HAY"))
    out.append(("porch", "LOOK"))
    return out


def _nearest():
    px, py = STATE.player.rect.center
    best, best_d = None, 1e9
    for pid, label in _available():
        x, y = _point_px(pid)
        d = math.hypot(px - x, py - y)
        if d <= _reach(pid) and d < best_d:
            best, best_d = (pid, label), d
    return best


def _h_generator():
    if not _S["gen_hint"]:
        _S["gen_hint"] = True
        _say([("BODI", "The generator kicks. Hit it like you mean it.")])
        return
    _S["genplay"] = G.GenPuzzle(_now_ms())
    _S["e_prev"] = True
    _toast("Prime it, set the choke, then pull until she catches.")


def _gen_sound(ev):
    snd = _snd()
    if ev in ("prime", "pull_ok"):
        snd.gen_pull()
    elif ev in ("choke_ok", "choke_miss"):
        snd.gen_cough()
    elif ev == "pull_miss":
        snd.gen_backfire()
    elif ev == "run":
        snd.gen_catch()


def _h_well():
    _S["carry"] = "water"
    _snd().well()
    _toast("You haul a bucket up from the well.")


def _h_bin():
    _S["carry"] = "feed"
    _snd().grain()
    _toast("A scoop of grain from the bin.")


def _h_trough():
    kind = _S["carry"]
    _S["trough"][kind] = True
    _S["carry"] = None
    _S["done"].add(kind)
    _snd().pour()
    _snd().bucket()
    _toast("Water in the trough." if kind == "water" else "Grain in the trough.")
    if _chores_done():
        _toast("Chores done. Bodi is waiting.", 3200)


def _h_hay():
    _S["crate"] = True
    STATE.m7_crate = True
    _snd().hay()
    _snd().crate()
    _say([("", "Under the hay: a crate of rifle magazines."),
          ("", "Behind it, a photograph. Bodi and Maru in uniform, years younger.")])


def _h_porch():
    _snd().door()
    _toast("The porch. Boots by the door, a kettle gone cold.")


def _picked(kind):
    _S["preps"].append(kind)
    STATE.m7_preps = list(_S["preps"])
    _make_walls()
    if len(_S["preps"]) >= PREP_PICKS:
        _toast("Two jobs done. Talk to Alex when you are ready.", 3400)


def _h_tractor():
    _S["drive"] = G.TractorPuzzle(M.tractor_route_px(), _now_ms())
    _S["drive_prev"] = set()
    _snd().trac_idle()
    _toast("Back it out, swing her round, and set it across the track.")


def _finish_tractor():
    _picked("tractor")
    px, py = M.tile_px((6.0, 7.0))
    STATE.player.rect.center = (px, py)
    _S["drive"] = None
    _toast("The tractor sits across the track.", 3200)
    _say([("", "You set the brake and climb down. The track is blocked.")])


def _h_shed():
    _picked("shed")
    _snd().crate()
    _snd().fence_creak()
    _say([("", "You loosen the drum caps and string a wire to the door. One spark and the shed goes up.")])


def _h_loft():
    _picked("loft")
    _say([("BODI", "The hayloft. Long sight over the whole yard."),
          ("BODI", "Don't make me waste the shots.")])


def _h_alex():
    if len(_S["preps"]) >= PREP_PICKS:
        _say([("ALEX", "Dust on the road. Here they come."),
              ("ALEX", "Try not to get shot, Biribel. It would be embarrassing for both of us.")],
             after=_finish)
    else:
        _say([("ALEX", "Pick two! The road is running out.")])


def _h_bodi():
    if _S["stage"] == PREP:
        if "loft" in _S["preps"]:
            _say([("BODI", "Up here. Go on, I have the yard.")])
        elif "loft" in _preps_open():
            _h_loft()
        else:
            _say([("BODI", "I'll stay on the ground. Somebody has to watch the goats.")])
    elif _chores_done():
        _say([("BODI", "I grow potatoes. I don't do politics.")], after=_finish)
    else:
        _say([("BODI", "Generator, well, feed bin. Then we talk.")])


_HANDLERS = {"generator": _h_generator, "well": _h_well, "bin": _h_bin, "trough": _h_trough,
             "hay": _h_hay, "porch": _h_porch, "bodi": _h_bodi, "tractor": _h_tractor,
             "shed": _h_shed, "alex": _h_alex}


def interact():
    if not _S:
        return False
    if _S.get("genplay") is not None or _S.get("drive") is not None:
        return True
    if _S["lines"]:
        _advance_line()
        return True
    near = _S["near"]
    if near is None:
        return False
    _HANDLERS[near[0]]()
    return True


# -- update ---------------------------------------------------------------

_DRIVE_KEYS = (("w", pygame.K_w, pygame.K_UP), ("a", pygame.K_a, pygame.K_LEFT),
               ("s", pygame.K_s, pygame.K_DOWN), ("d", pygame.K_d, pygame.K_RIGHT))


def _drive_frame(keys, pz, now):
    held = set()
    for name, code, alt in _DRIVE_KEYS:
        try:
            if keys[code] or keys[alt]:
                held.add(name)
        except Exception:
            pass
    fresh = held - _S["drive_prev"]
    _S["drive_prev"] = held
    pz.update(now)
    if pz.state == "prompt" and pz.step()[6] in held:
        pz.press(now, pz.step()[6])
    elif fresh:
        pz.press(now, sorted(fresh)[0])
    snd = _snd()
    for ev in pz.take_events():
        if ev == "drive":
            if pz.clean:
                snd.trac_rev()
            else:
                snd.gen_cough()
            snd.trac_move()
        elif ev == "arrive":
            snd.trac_still()
        elif ev == "stall":
            snd.trac_still()
            snd.trac_stall()
        elif ev == "park":
            snd.trac_off()
            snd.chock()
            _finish_tractor()


def update(keys):
    if not _S or keys is None:
        return (0, 0)
    now = _now_ms()
    _S["now"] = now
    adv = bool(keys[pygame.K_SPACE] or keys[pygame.K_RETURN])
    if adv and not _S["prev_adv"] and _S["lines"]:
        _advance_line()
    _S["prev_adv"] = adv
    if _S["lines"] or _S["finished"]:
        return (0, 0)
    pz = _S.get("genplay")
    if pz is not None:
        held = bool(keys[pygame.K_e])
        if held and not _S["e_prev"]:
            pz.press(now)
        _S["e_prev"] = held
        pz.update(now)
        for ev in pz.take_events():
            _gen_sound(ev)
        if pz.done:
            _S["gen_on"] = True
            _S["done"].add("generator")
            _S["genplay"] = None
            _toast("The generator coughs, catches, and settles into a steady thud.", 3200)
            _snd().start_loop("m7_gen_idle", 0.20)
            if _chores_done():
                _toast("Chores done. Bodi is waiting.", 3200)
        return (0, 0)
    drv = _S.get("drive")
    if drv is not None:
        _drive_frame(keys, drv, now)
        return (0, 0)
    p = STATE.player
    dx = (keys[pygame.K_d] or keys[pygame.K_RIGHT]) - (keys[pygame.K_a] or keys[pygame.K_LEFT])
    dy = (keys[pygame.K_s] or keys[pygame.K_DOWN]) - (keys[pygame.K_w] or keys[pygame.K_UP])
    if dx and dy:
        dx, dy = dx * 0.7071, dy * 0.7071
    r = p.rect
    r.x += int(round(dx * SPEED))
    for w in STATE.walls:
        if r.colliderect(w):
            r.x = w.left - r.w if dx > 0 else w.right
    r.y += int(round(dy * SPEED))
    for w in STATE.walls:
        if r.colliderect(w):
            r.y = w.top - r.h if dy > 0 else w.bottom
    r.clamp_ip(pygame.Rect(0, 0, M.COLS * T, M.ROWS * T))
    if dx or dy:
        _S["step"] += 0.22
        ph = int(_S["step"] / math.pi)
        if ph != _S["step_ph"]:
            _S["step_ph"] = ph
            _snd().step(ph)
        _S["face"] = ("r" if dx > 0 else "l") if abs(dx) > abs(dy) else ("d" if dy > 0 else "u")
        p.angle = math.atan2(dy, dx)
    _S["near"] = _nearest()
    _wildlife(now)
    return (0, 0)


def _wildlife(now):
    if now - _S["life_t"] < _S["life_gap"]:
        return
    i = _S["life_i"]
    if i % 3 == 0:
        _snd().bird()
    elif i % 3 == 1:
        _snd().goat()
    else:
        _snd().hen()
    _S["life_i"] = i + 1
    _S["life_t"] = now
    _S["life_gap"] = 6000 + (now % 5000)


# -- draw -------------------------------------------------------------------

PX = 2                      # one art pixel = 2x2 screen pixels
FW, FH, FCX, FBASE = 34, 28, 17, 24   # figure canvas; feet centre at (FCX, FBASE)
GW, GH, GCX, GBASE = 20, 13, 9, 11    # goat canvas (facing right)
_CLEAR = (0, 0, 0, 0)
_GUN = dict(metal=(46, 44, 46), steel=(118, 120, 128), wood=(128, 84, 48),
            wood_d=(86, 54, 32), wood_l=(160, 112, 70))
_BELT, _BUCKLE = (44, 34, 28), (176, 156, 104)
_HORN = (176, 164, 140)
_FIG_CACHE = {}
_GOAT_CACHE = {}
_SHADOWS = {}


def _tone(c, k, add=0):
    return tuple(max(0, min(255, int(v * k + add))) for v in c)


def _pal(look):
    p = {}
    for name, c in _LOOKS[look].items():
        if c is not None:
            p[name], p[name + "_l"], p[name + "_d"] = c, _tone(c, 1.2, 24), _tone(c, 0.66)
    return p


def _ink_scaled(c):
    """1px INK outline around the canvas silhouette, then nearest x2."""
    m = pygame.mask.from_surface(c, 1)
    ink = m.to_surface(setcolor=M.INK + (255,), unsetcolor=_CLEAR)
    out = pygame.Surface(c.get_size(), pygame.SRCALPHA)
    for d in ((1, 0), (-1, 0), (0, 1), (0, -1)):
        out.blit(ink, d)
    out.blit(c, (0, 0))
    w, h = c.get_size()
    return pygame.transform.scale(out, (w * PX, h * PX))


def _drop_shadow(w, h):
    img = _SHADOWS.get((w, h))
    if img is None:
        s = pygame.Surface((w, h), pygame.SRCALPHA)
        pygame.draw.ellipse(s, (14, 12, 10, 92), s.get_rect())
        img = _SHADOWS[(w, h)] = pygame.transform.scale(s, (w * PX, h * PX))
    return img


def _held_gun(surf, x, y, face):
    """Rifle in figure-canvas pixels; (x, y) are the feet like ``_figure``."""
    c = pygame.Surface((FW, FH), pygame.SRCALPHA)
    _paint_gun(c, face, 11)
    img = _ink_scaled(c)
    surf.blit(img, (x - FCX * PX, y - FBASE * PX))


def _paint_gun(c, face, ty):
    g, cx = _GUN, FCX
    sg = -1 if face == "l" else 1

    def s(dx, yy, w, h, col):
        c.fill(col, (cx + dx if sg > 0 else cx - dx - w, yy, w, h))

    if face in "lr":
        s(-4, ty + 2, 4, 2, g["wood"])
        s(-4, ty + 3, 4, 1, g["wood_d"])
        s(0, ty + 2, 4, 2, g["metal"])
        s(0, ty + 2, 4, 1, g["steel"])
        s(4, ty + 2, 8, 1, g["metal"])
        s(11, ty + 2, 1, 1, g["steel"])
        s(4, ty + 3, 3, 1, g["wood"])
    elif face == "u":
        c.fill(g["metal"], (cx + 4, ty - 9, 2, 12))
        c.fill(g["steel"], (cx + 4, ty - 9, 1, 12))
        c.fill(g["wood"], (cx + 4, ty + 3, 2, 4))
    else:
        c.fill(g["wood"], (cx + 1, ty + 1, 3, 3))
        c.fill(g["wood_l"], (cx + 1, ty + 1, 1, 2))
        c.fill(g["wood_d"], (cx + 3, ty + 1, 1, 3))
        c.fill(g["metal"], (cx + 1, ty + 4, 3, 2))
        c.fill(g["steel"], (cx + 1, ty + 4, 1, 2))
        c.fill(g["metal"], (cx + 2, ty + 6, 1, 6))
        c.fill(g["steel"], (cx + 2, ty + 6, 1, 1))


def _fig_frame(look, face, frame, ub, blink, gun, carry):
    key = (look, face, frame, ub, blink, gun, carry)
    img = _FIG_CACHE.get(key)
    if img is not None:
        return img
    p = _pal(look)
    c = pygame.Surface((FW, FH), pygame.SRCALPHA)
    cx, sg, side = FCX, (-1 if face == "l" else 1), face in "lr"
    hy, ty = 4 + ub, 11 + ub
    lf = (1, 0, -1, 0)[frame] if frame >= 0 else 0
    bodi = look == "bodi"
    apron = _tone(p["torso"], 0.6)

    def r(x, yy, w, h, col):
        c.fill(col, (x, yy, w, h))

    def s(dx, yy, w, h, col):
        r(cx + dx if sg > 0 else cx - dx - w, yy, w, h, col)

    if gun and face == "u":
        _paint_gun(c, face, ty)

    # legs
    if side:
        for off, lift, near in ((-2 * lf, 1 if lf == 0 else 0, False), (2 * lf, 0, True)):
            leg, boot = (p["legs"], p["boots"]) if near else (p["legs_d"], p["boots_d"])
            s(-2 + off, 17, 3, 5 - lift, leg)
            s(-2 + off, 22 - lift, 4, 2, boot)
            if near:
                s(-2 + off, 17, 1, 5, p["legs_d"])
                s(1 + off, 22, 1, 1, p["boots_l"])
    else:
        for lx, e in ((-4, lf), (1, -lf)):
            bot = 21 + e
            r(cx + lx, 17, 3, bot - 16, p["legs"])
            r(cx + lx + (2 if lx < 0 else 0), 17, 1, bot - 16, p["legs_d"])
            r(cx + lx, bot + 1, 3, 2, p["boots"])
            r(cx + lx, bot + 2, 3, 1, p["boots_d"])
            if face == "d":
                r(cx + lx + (0 if lx < 0 else 2), bot + 1, 1, 1, p["boots_l"])

    # torso
    if side:
        s(-4, ty, 8, 7, p["torso"])
        s(-4, ty, 1, 1, _CLEAR)
        r(cx - 4, ty + 1, 1, 4, p["torso_l"])
        s(-3, ty, 6, 1, p["torso_l"])
        r(cx + 3, ty + 1, 1, 5, p["torso_d"])
        if bodi:
            s(1, ty + 1, 3, 4, apron)
        s(-4, ty + 5, 8, 1, _BELT)
        s(2, ty + 5, 1, 1, _BUCKLE)
        s(-4, ty + 6, 8, 1, p["torso_d"])
        s(1, ty, 2, 1, p["skin_d"])
    else:
        r(cx - 5, ty, 10, 7, p["torso"])
        r(cx - 5, ty, 1, 1, _CLEAR)
        r(cx + 4, ty, 1, 1, _CLEAR)
        r(cx - 4, ty, 8, 1, p["torso_l"])
        r(cx - 5, ty + 1, 1, 4, p["torso_l"])
        r(cx + 4, ty + 1, 1, 5, p["torso_d"])
        if bodi and face == "d":
            r(cx - 3, ty + 1, 6, 4, apron)
            r(cx - 2, ty + 3, 4, 1, p["torso_d"])
        elif bodi:
            r(cx - 3, ty, 1, 5, apron)
            r(cx + 2, ty, 1, 5, apron)
        elif face == "u":
            r(cx - 1, ty + 1, 1, 4, p["torso_d"])
        r(cx - 5, ty + 5, 10, 1, _BELT)
        r(cx - 5, ty + 6, 10, 1, p["torso_d"])
        if face == "d":
            r(cx - 1, ty + 5, 2, 1, _BUCKLE)
            r(cx - 2, ty, 4, 1, p["torso_d"])
            r(cx - 1, ty, 2, 1, p["skin_d"])
        # arms
        for ax, e in ((cx - 7, -lf), (cx + 5, lf)):
            inner = ax + 1 if ax < cx else ax
            if carry:
                r(ax, hy - 1, 2, ty + 3 - hy, p["arm"])
                r(inner, hy - 1, 1, ty + 3 - hy, p["arm_d"])
                r(ax, hy - 2, 2, 1, p["skin"])
            else:
                r(ax, ty + 1, 2, 4 + e, p["arm"])
                r(inner, ty + 1, 1, 4 + e, p["arm_d"])
                r(ax, ty + 5 + e, 2, 1, p["skin"])
            if ax < cx:
                r(ax, ty + 1, 1, 2, p["arm_l"])
            if p.get("patch") and (ax < cx) == (face == "d"):
                r(ax, ty + 1 if not carry else hy + 1, 2, 2, p["patch"])
        if gun and face == "d":
            _paint_gun(c, face, ty)
            r(cx + 4, ty + 4, 1, 1, p["skin"])

    # side arm (in front of the torso)
    if side and not carry:
        if gun:
            _paint_gun(c, face, ty)
            s(-1, ty + 1, 2, 3, p["arm"])
            s(-1, ty + 3, 4, 1, p["arm"])
            s(3, ty + 3, 1, 1, p["skin"])
        else:
            a = -lf
            s(-2 + a, ty + 1, 1, 4, p["torso_d"])
            s(-1 + a, ty + 1, 2, 4, p["arm"])
            s(-1 + a, ty + 5, 2, 1, p["skin"])
        if p.get("patch"):
            s(-1 + (0 if gun else -lf), ty + 1, 2, 2, p["patch"])

    if side and carry:
        s(-1, hy - 1, 2, ty + 3 - hy, p["arm"])
        s(-1, hy - 1, 1, ty + 3 - hy, p["arm_d"])
        s(-1, hy - 2, 2, 1, p["skin"])

    # head
    eye = p["skin_d"] if blink else M.INK
    r(cx - 4, hy, 8, 7, p["skin"])
    r(cx - 4, hy + 6, 1, 1, _CLEAR)
    r(cx + 3, hy + 6, 1, 1, _CLEAR)
    r(cx - 3, hy + 6, 6, 1, p["skin_d"])
    r(cx + 3, hy + 1, 1, 5, p["skin_d"])
    hair, hair_l, hair_d = p["hair"], p["hair_l"], p["hair_d"]
    r(cx - 3, hy - 1, 6, 1, hair)
    r(cx - 4, hy, 8, 2, hair)
    r(cx - 2, hy - 1, 2, 1, hair_l)
    r(cx - 3, hy, 1, 1, hair_l)
    if face == "d":
        r(cx - 4, hy + 2, 1, 2, hair)
        r(cx + 3, hy + 2, 1, 2, hair)
        r(cx - 2, hy + 2, 2, 1, hair)
        r(cx - 5, hy + 3, 1, 2, p["skin_d"])
        r(cx + 4, hy + 3, 1, 2, p["skin_d"])
        r(cx - 2, hy + 3, 1, 1, eye)
        r(cx + 1, hy + 3, 1, 1, eye)
        r(cx - 1, hy + 4, 1, 1, p["skin_d"])
    elif face == "u":
        r(cx - 4, hy + 2, 8, 4, hair)
        r(cx - 4, hy + 5, 8, 1, hair_d)
        r(cx, hy + 2, 1, 1, hair_d)
        r(cx - 5, hy + 3, 1, 2, p["skin_d"])
        r(cx + 4, hy + 3, 1, 2, p["skin_d"])
    else:
        s(-4, hy + 2, 4, 3, hair)
        s(-4, hy + 5, 3, 1, hair_d)
        s(2, hy + 2, 1, 1, hair)
        s(-1, hy + 3, 1, 2, p["skin_d"])
        s(2, hy + 3, 1, 1, eye)
        s(4, hy + 4, 1, 1, p["skin"])

    img = _FIG_CACHE[key] = _ink_scaled(c)
    return img


_LOOK_PHASE = {"biribel": 0, "bodi": 1300, "alex": 2600}


def _figure(surf, x, y, face, step, look, moving=True, gun=False, carry=False):
    """Blocky pixel figure; (x, y) is the centre of its feet in screen pixels."""
    if moving:
        frame = int(step / (math.pi / 2)) % 4
        ub, blink = (-1 if frame % 2 else 0), False
    else:
        now = pygame.time.get_ticks() + _LOOK_PHASE.get(look, 0)
        frame, ub, blink = -1, (now // 800) % 2, now % 3700 < 120
    surf.blit(_drop_shadow(12, 4), (x - 12, y - 5))
    img = _fig_frame(look, face, frame, ub, blink, gun, carry)
    surf.blit(img, (x - FCX * PX, y - FBASE * PX))


def _goat_frame(col, right, frame, moving, dip):
    key = (col, right, frame if moving else -1, dip)
    img = _GOAT_CACHE.get(key)
    if img is not None:
        return img
    c = pygame.Surface((GW, GH), pygame.SRCALPHA)
    d, l, dd = _tone(col, 0.72), _tone(col, 1.1, 16), _tone(col, 0.5)

    def r(x, yy, w, h, cl):
        c.fill(cl, (x, yy, w, h))

    for lx in (5, 6, 11, 12):
        lifted = moving and ((lx in (5, 12)) == (frame == 1))
        tone = d if lx in (6, 11) else col
        r(lx, 9, 1, 1 if lifted else 2, tone)
        r(lx, 9 if lifted else 10, 1, 1, dd)
    r(3, 4, 11, 5, col)
    r(3, 4, 1, 1, _CLEAR)
    r(4, 4, 8, 1, l)
    r(5, 7, 7, 1, d)
    r(3, 8, 11, 1, d)
    r(2, 3, 1, 2, col)
    r(1, 2, 1, 1, l)
    hx, hy = (14, 5) if dip else (13, 2)
    r(12, 3, 2, 3 if not dip else 4, col)
    r(hx, hy, 4, 3, col)
    r(hx, hy, 3, 1, l)
    r(hx + 4, hy + 1, 1, 2, d)
    r(hx + 2, hy + 1, 1, 1, M.INK)
    r(hx - 1, hy + 1, 1, 1, d)
    r(hx, hy - 1, 1, 1, _HORN)
    r(hx - 1, hy - 2, 1, 1, _HORN)
    r(hx + 3, hy + 3, 1, 1, dd)
    img = _ink_scaled(c)
    if not right:
        img = pygame.transform.flip(img, True, False)
    _GOAT_CACHE[key] = img
    return img


def _goat(surf, x, y, col, face_right, frame=0, moving=False, dip=False):
    surf.blit(_drop_shadow(12, 4), (x - 12, y + 1))
    img = _goat_frame(col, face_right, frame, moving, dip)
    ax = GCX if face_right else GW - GCX
    surf.blit(img, (x - ax * PX, y + 6 - GBASE * PX))


def _draw_goats(surf, now):
    t = now / 1000.0
    for (hx, hy), col, ph in _GOATS:
        a, b = t * 0.35 + ph, t * 0.5 + ph * 1.7
        x = (hx + 0.35 * math.sin(a)) * T + OX
        y = (hy + 0.25 * math.sin(b)) * T + OY
        speed = abs(0.35 * 0.35 * math.cos(a)) + abs(0.25 * 0.5 * math.cos(b))
        moving = speed > 0.07
        dip = not moving and ((now + int(ph * 1000)) // 900) % 3 == 0
        _goat(surf, int(x), int(y), col, math.cos(a) > 0,
              frame=(now // 170 + int(ph * 10)) % 2, moving=moving, dip=dip)


def _draw_trough(surf):
    x, y = M.TROUGH[0] * T + OX, M.TROUGH[1] * T + OY
    surf.fill(M.INK, (x + 2, y + 14, 2 * T - 4, 30))
    surf.fill(M.WOOD, (x + 4, y + 16, 2 * T - 8, 26))
    inner = pygame.Rect(x + 10, y + 22, 2 * T - 20, 14)
    surf.fill(M.WOOD_D, inner)
    if _S["trough"]["water"]:
        surf.fill(M.WATER, (inner.x + 2, inner.y + 2, inner.w // 2, inner.h - 4))
    if _S["trough"]["feed"]:
        surf.fill(M.GRAIN, (inner.centerx, inner.y + 2, inner.w // 2 - 2, inner.h - 4))


def _draw_generator(surf, now):
    gx, gy = _point_px("generator")
    x, y = gx - 32 + OX, gy - 32 + OY
    pz = _S.get("genplay")
    running = _S["gen_on"] or (pz is not None and pz.done)
    jitter = int(math.sin(now * 0.06) * 1.6) if running else (
        int(math.sin(now * 0.09) * 1.4) if pz is not None and abs(pz.flash) > 0.2 else 0)
    surf.fill(M.INK, (x + 4 + jitter, y + 10, 56, 44))
    surf.fill(M.GENERATOR, (x + 6 + jitter, y + 12, 52, 40))
    surf.fill((120, 60, 28), (x + 6 + jitter, y + 12, 52, 5))
    for i in range(4):
        surf.fill((70, 40, 24), (x + 12 + jitter, y + 24 + i * 6, 24, 2))
    surf.fill(M.METAL, (x + 42 + jitter, y + 22, 12, 12))
    surf.fill(M.METAL_D, (x + 44 + jitter, y + 24, 8, 8))
    surf.fill(M.METAL_D, (x + 50, y + 2, 5, 12))
    if running:
        for i in range(3):
            age = ((now * 0.0007) + i / 3.0) % 1.0
            sz = 5 + int(age * 6)
            tone = int(150 - age * 70)
            surf.fill((tone, tone, tone), (x + 50 - int(age * 10), y - int(age * 40), sz, sz))
    elif pz is not None:
        filled = int(round(pz.comp * G.GenPuzzle.PULLS))
        for i in range(G.GenPuzzle.PULLS):
            col = (232, 200, 90) if i < filled else (60, 56, 50)
            surf.fill(M.INK, (x + 12 + i * 14, y - 8, 11, 9))
            surf.fill(col, (x + 14 + i * 14, y - 6, 7, 5))


def _draw_hay(surf):
    x, y = int(12 * T + OX), int(1 * T + OY)
    surf.fill(M.HAYFLOOR[1], (x + 4, y + 12, 56, 44))
    surf.fill(M.HAYFLOOR[0], (x + 8, y + 10, 48, 40))
    surf.fill(M.HAYFLOOR[2], (x + 14, y + 14, 20, 6))
    if _S["crate"]:
        surf.fill(M.INK, (x + 10, y + 22, 40, 26))
        surf.fill(M.WOOD, (x + 12, y + 24, 36, 22))
        surf.fill(M.WOOD_D, (x + 12, y + 33, 36, 3))


def _draw_carry(surf, x, y):
    kind = _S["carry"]
    if not kind:
        return
    col = M.WATER if kind == "water" else M.GRAIN

    def p(lx, ly, w, h, c):
        surf.fill(c, (x + lx * PX, y + ly * PX, w * PX, h * PX))

    p(-3, -33, 6, 1, M.INK)
    p(-4, -32, 1, 3, M.INK)
    p(3, -32, 1, 3, M.INK)
    p(-5, -30, 10, 8, M.INK)
    p(-4, -29, 8, 6, M.METAL)
    p(-4, -29, 8, 1, _tone(M.METAL, 1.25, 20))
    p(-3, -28, 6, 1, col)
    p(-3, -28, 2, 1, _tone(col, 1.2, 18))
    p(3, -27, 1, 4, M.METAL_D)
    p(-4, -25, 8, 1, M.METAL_D)


def _draw_tractor(surf, now):
    pz = _S.get("drive")
    if pz is not None:
        x, y, ang = pz.pose(now)
    elif "tractor" in _S["preps"]:
        x, y, ang = M.TRACTOR_PARK[0] + T, M.TRACTOR_PARK[1] + T // 2, 0.0
    else:
        x, y, ang = M.TRACTOR_AT[0] * T + T, M.TRACTOR_AT[1] * T + T // 2, 0.0
    _tractor_draw(surf, int(x) + OX, int(y) + OY, ang)
    if "tractor" in _S["preps"]:
        px, py = M.TRACTOR_PARK
        for bx in (6 * T, int(8.5 * T)):
            surf.fill(M.INK, (bx + OX, py + 16 + OY, T // 2, 40))
            surf.fill(M.WOOD, (bx + 2 + OX, py + 18 + OY, T // 2 - 4, 36))
            surf.fill(M.WOOD_D, (bx + 2 + OX, py + 30 + OY, T // 2 - 4, 3))


def _draw_rig(surf, now):
    if "shed" not in _S["preps"]:
        return
    bx, by = 1 * T + 46 + OX, 8 * T + 16 + OY
    for a, b in (((bx, by), (3 * T + 14 + OX, 8 * T + 34 + OY)),
                 ((3 * T + 14 + OX, 8 * T + 34 + OY), (3 * T + 14 + OX, 7 * T + 52 + OY))):
        pygame.draw.line(surf, M.INK, a, b, 3)
        pygame.draw.line(surf, (190, 60, 44), a, b, 1)
    if int(now / 350) % 2:
        surf.fill((255, 86, 56), (bx - 2, by - 4, 5, 5))


def _objective():
    if _S["finished"]:
        return ""
    if _S.get("genplay") is not None:
        return "START THE GENERATOR"
    if _S.get("drive") is not None:
        return "STEER THE TRACTOR"
    if _S["stage"] == PREP:
        if len(_S["preps"]) >= PREP_PICKS:
            return "TALK TO ALEX"
        mark = ["x" if k in _S["preps"] else " " for k in PREP_ITEMS]
        return "PREPARE  %d/%d  TRACTOR [%s]  SHED [%s]  LOFT [%s]" % ((len(_S["preps"]), PREP_PICKS) + tuple(mark))
    if _chores_done():
        return "TALK TO BODI"
    mark = ["x" if k in _S["done"] else " " for k in CHORES_NEEDED]
    return "CHORES  GENERATOR [%s]  WATER [%s]  FEED [%s]" % tuple(mark)


def draw(surface):
    if not _S:
        surface.fill(M.SKY_EDGE)
        return
    from cutscenes.engine import draw_dialogue_box
    from engine.ui import prompt as _prompt
    from ui import hud
    now = _now_ms()
    _S["now"] = now
    surface.fill(M.SKY_EDGE)
    surface.blit(_S["static"], (OX, OY))
    _draw_goats(surface, now)
    _draw_trough(surface)
    _draw_generator(surface, now)
    _draw_hay(surface)
    _draw_tractor(surface, now)
    _draw_rig(surface, now)
    p = STATE.player
    px, py = p.rect.centerx, p.rect.bottom - 2

    def _face_to(fx, fy):
        if abs(px - fx) > abs(py - fy) + 16:
            return "r" if px > fx else "l"
        return "u" if py < fy else "d"

    bx, by = M.tile_px(_bodi_tile())
    if _S["step"] != _S.get("step_seen"):
        _S["step_seen"], _S["step_t"] = _S["step"], now
    walking = now - _S.get("step_t", -10 ** 9) < 140
    figures = [(by + 14, "bodi", bx + OX, by + 14 + OY, _face_to(bx, by), 0.0)]
    if _S.get("drive") is None:
        figures.append((py, "biribel", px + OX, py + OY, _S["face"], _S["step"]))
    if _S["stage"] == PREP:
        ax, ay = M.tile_px(M.ALEX_TILE)
        figures.append((ay + 14, "alex", ax + OX, ay + 14 + OY, _face_to(ax, ay), 0.0))
    for _, look, fx, fy, face, step in sorted(figures, key=lambda f: f[0]):
        me = look == "biribel"
        _figure(surface, fx, fy, face, step, look,
                moving=me and walking,
                gun=me and _S["stage"] == PREP,
                carry=me and bool(_S["carry"]))
    _draw_carry(surface, px + OX, py + OY)
    near = _S["near"]
    busy = _S.get("genplay") is not None or _S.get("drive") is not None
    if near and not _S["lines"] and not busy:
        x, y = _point_px(near[0])
        _prompt.draw(surface, x + OX, y + OY, "[E] " + near[1], (236, 228, 196), font=font_prompt)
    obj = _objective()
    if obj:
        hud.draw_objective_panel(surface, obj, x=20, y=16)
    if not _S["lines"]:
        if _S.get("genplay") is not None:
            G.draw_generator(surface, _S["genplay"], now)
        elif _S.get("drive") is not None:
            G.draw_tractor(surface, _S["drive"], now)
    text, until = _S["toast"]
    if text and now < until and not _S["lines"]:
        img = font_terminal_small.render(text, True, (240, 232, 204))
        box = img.get_rect(center=(WIDTH // 2, HEIGHT - 70)).inflate(24, 14)
        pygame.draw.rect(surface, (20, 20, 22), box)
        pygame.draw.rect(surface, M.WOOD_L, box, 2)
        surface.blit(img, img.get_rect(center=box.center))
    if _S["lines"]:
        who, line = _S["lines"][0]
        n = min(len(line), (now - _S["line_t0"]) // CHAR_MS)
        if n > _S["tick_n"] and n % 3 == 0:
            _snd().dialogue_tick()
        _S["tick_n"] = n
        draw_dialogue_box(surface, who, line, n, len(line), can_continue=n >= len(line),
                          show_speaker=bool(who))
