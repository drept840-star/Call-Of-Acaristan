"""Mission 7 top-down farmyard: beat 2 (chores); beat 4 (prep) reuses the map.

The stage is peaceful: walk, press E at the marked spots, talk to Bodi.  Static
scenery is baked once per ``begin``; the figures, animals and the few things
that change are drawn per frame.
"""
import math

import pygame

from core.config import HEIGHT, WIDTH, font_prompt, font_terminal_small
from core.state import STATE
from engine.core import now_ms as _now_ms
from entities.player import Player

from . import maps as M

T = M.TILE
OX, OY = M.ORIGIN
CHORES = "chores"
PREP = "prep"
FARM_STAGES = (CHORES, PREP)
CHORES_NEEDED = ("generator", "water", "feed")
PREP_ITEMS = ("tractor", "shed", "loft")
PREP_PICKS = 2
TRACTOR_MS = 1800
CHAR_MS = 26
KICK_NEED = 4
KICK_WINDOW = 900
SPEED = 3.0

_S = {}
_TILES = {}

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
    cx, cy = int(7.5 * T), int(5.5 * T)
    pygame.draw.circle(surf, M.INK, (cx, cy), 30)
    pygame.draw.circle(surf, M.STONE, (cx, cy), 27)
    pygame.draw.circle(surf, M.STONE_D, (cx, cy), 20)
    pygame.draw.circle(surf, M.WATER, (cx, cy), 15)
    surf.fill((120, 160, 188), (cx - 8, cy - 8, 6, 3))
    surf.fill(M.WOOD_D, (cx - 34, cy - 5, 9, 10))
    surf.fill(M.WOOD_D, (cx + 25, cy - 5, 9, 10))
    surf.fill(M.WOOD, (cx - 28, cy - 2, 56, 4))


def _tractor(surf, x, y):
    _shadow(surf, pygame.Rect(x + 4, y + 8, 2 * T - 8, T - 12), 6)
    for wx, wy, ww, wh in ((8, 0, 30, 15), (8, 49, 30, 15), (92, 3, 20, 11), (92, 50, 20, 11)):
        surf.fill(M.INK, (x + wx, y + wy, ww, wh))
        for i in range(0, ww, 6):
            surf.fill((52, 52, 56), (x + wx + i, y + wy + 2, 3, wh - 4))
    surf.fill(M.TRACTOR_D, (x + 6, y + 14, 116, 36))
    surf.fill(M.TRACTOR, (x + 8, y + 16, 112, 32))
    surf.fill(M.TRACTOR_D, (x + 70, y + 20, 50, 24))
    surf.fill((44, 38, 36), (x + 22, y + 20, 38, 24))
    surf.fill((76, 66, 58), (x + 26, y + 24, 30, 16))
    surf.fill(M.METAL_D, (x + 54, y + 29, 8, 5))
    surf.fill(M.METAL, (x + 112, y + 22, 5, 5))


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
    x, y = 8 * T, 4 * T
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
    return M.LOFT_TILE if "loft" in _S["preps"] else M.BODI_TILE


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
        done=set(), carry=None, kick=0, kick_t=0, gen_on=False, gen_hint=False,
        trough={"water": False, "feed": False}, crate=False, lines=[], line_t0=0, after=None,
        toast=("", 0), prev_adv=False, face="d", step=0.0, near=None, finished=False,
        preps=[], tractor_t=0)
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
    _S["after"] = after


def _advance_line():
    text = _S["lines"][0][1]
    now = _now_ms()
    if (now - _S["line_t0"]) // CHAR_MS < len(text):
        _S["line_t0"] = now - len(text) * CHAR_MS - 1
        return
    _S["lines"].pop(0)
    _S["line_t0"] = now
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
    _S["kick"] += 1
    _S["kick_t"] = _now_ms()
    if _S["kick"] >= KICK_NEED:
        _S["gen_on"] = True
        _S["done"].add("generator")
        _toast("The generator coughs, catches, and settles into a steady thud.", 3200)


def _h_well():
    _S["carry"] = "water"
    _toast("You haul a bucket up from the well.")


def _h_bin():
    _S["carry"] = "feed"
    _toast("A scoop of grain from the bin.")


def _h_trough():
    kind = _S["carry"]
    _S["trough"][kind] = True
    _S["carry"] = None
    _S["done"].add(kind)
    _toast("Water in the trough." if kind == "water" else "Grain in the trough.")
    if _chores_done():
        _toast("Chores done. Bodi is waiting.", 3200)


def _h_hay():
    _S["crate"] = True
    STATE.m7_crate = True
    _say([("", "Under the hay: a crate of rifle magazines."),
          ("", "Behind it, a photograph. Bodi and Maru in uniform, years younger.")])


def _h_porch():
    _toast("The porch. Boots by the door, a kettle gone cold.")


def _picked(kind):
    _S["preps"].append(kind)
    STATE.m7_preps = list(_S["preps"])
    _make_walls()
    if len(_S["preps"]) >= PREP_PICKS:
        _toast("Two jobs done. Talk to Alex when you are ready.", 3400)


def _h_tractor():
    _S["tractor_t"] = _now_ms()
    _picked("tractor")
    _say([("", "You turn the key. The old tractor shudders down the yard and slews across the track.")])


def _h_shed():
    _picked("shed")
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
    if _S["lines"]:
        _advance_line()
        return True
    near = _S["near"]
    if near is None:
        return False
    _HANDLERS[near[0]]()
    return True


# -- update ---------------------------------------------------------------

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
    if _S["kick"] and not _S["gen_on"] and now - _S["kick_t"] > KICK_WINDOW:
        _S["kick"] -= 1
        _S["kick_t"] = now
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
        _S["face"] = ("r" if dx > 0 else "l") if abs(dx) > abs(dy) else ("d" if dy > 0 else "u")
        p.angle = math.atan2(dy, dx)
    _S["near"] = _nearest()
    return (0, 0)


# -- draw -------------------------------------------------------------------

def _figure(surf, x, y, face, step, look, moving=True):
    """Blocky figure; (x, y) is the centre of its feet in screen pixels."""
    k = _LOOKS[look]
    swing = int(math.sin(step) * 3) if moving else 0
    shade = pygame.Surface((22, 8), pygame.SRCALPHA)
    shade.fill((0, 0, 0, 80))
    surf.blit(shade, (x - 11, y - 5))
    side = face in "lr"
    if side:
        for off, col in ((swing, k["legs"]), (-swing, k["legs"])):
            surf.fill(col, (x - 4 + off, y - 11, 8, 8))
            surf.fill(k["boots"], (x - 4 + off, y - 4, 8, 4))
    else:
        for off, lx in ((swing, x - 8), (-swing, x + 2)):
            surf.fill(k["legs"], (lx, y - 11, 6, 8 + max(0, off)))
            surf.fill(k["boots"], (lx, y - 4 + max(0, off), 6, 4))
    torso = pygame.Rect(x - 9, y - 25, 18, 15)
    pygame.draw.rect(surf, M.INK, torso.inflate(2, 2))
    surf.fill(k["torso"], torso)
    if side:
        surf.fill(k["arm"], (x - 2 - swing, y - 24, 5, 11))
    else:
        surf.fill(k["arm"], (x - 14, y - 24 + swing, 5, 11))
        surf.fill(k["arm"], (x + 9, y - 24 - swing, 5, 11))
        if k["patch"]:
            surf.fill(k["patch"], (x - 14, y - 24 + swing, 4, 3))
    head = pygame.Rect(x - 6, y - 37, 12, 12)
    pygame.draw.rect(surf, M.INK, head.inflate(2, 2))
    surf.fill(k["skin"], head)
    hair = k["hair"]
    if face == "u":
        surf.fill(hair, (x - 7, y - 38, 14, 13))
    elif face == "d":
        surf.fill(hair, (x - 7, y - 38, 14, 5))
        surf.fill(hair, (x - 7, y - 34, 2, 4))
        surf.fill(hair, (x + 5, y - 34, 2, 4))
        surf.fill(M.INK, (x - 3, y - 31, 2, 2))
        surf.fill(M.INK, (x + 1, y - 31, 2, 2))
    else:
        sign = -1 if face == "l" else 1
        surf.fill(hair, (x - 7, y - 38, 14, 5))
        surf.fill(hair, (x - 7 if sign > 0 else x + 1, y - 34, 6, 8))
        surf.fill(M.INK, (x + (3 if sign > 0 else -5), y - 31, 2, 2))


def _goat(surf, x, y, col, face_right):
    dark = tuple(max(0, v - 40) for v in col)
    surf.fill(M.INK, (x - 11, y - 11, 22, 14))
    surf.fill(col, (x - 10, y - 10, 20, 11))
    surf.fill(dark, (x - 10, y - 2, 20, 3))
    hx = x + 8 if face_right else x - 15
    surf.fill(M.INK, (hx - 1, y - 14, 9, 10))
    surf.fill(col, (hx, y - 13, 7, 8))
    surf.fill(dark, (hx + (4 if face_right else 1), y - 16, 2, 4))
    for lx in (x - 8, x + 5):
        surf.fill(dark, (lx, y + 2, 3, 4))


def _draw_goats(surf, now):
    t = now / 1000.0
    for (hx, hy), col, ph in _GOATS:
        vx = math.cos(t * 0.35 + ph)
        x = (hx + 0.35 * math.sin(t * 0.35 + ph)) * T + OX
        y = (hy + 0.25 * math.sin(t * 0.5 + ph * 1.7)) * T + OY
        _goat(surf, int(x), int(y), col, vx > 0)


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
    jitter = int(math.sin(now * 0.06) * 1.6) if _S["gen_on"] else 0
    surf.fill(M.INK, (x + 4 + jitter, y + 10, 56, 44))
    surf.fill(M.GENERATOR, (x + 6 + jitter, y + 12, 52, 40))
    surf.fill((120, 60, 28), (x + 6 + jitter, y + 12, 52, 5))
    for i in range(4):
        surf.fill((70, 40, 24), (x + 12 + jitter, y + 24 + i * 6, 24, 2))
    surf.fill(M.METAL, (x + 42 + jitter, y + 22, 12, 12))
    surf.fill(M.METAL_D, (x + 44 + jitter, y + 24, 8, 8))
    surf.fill(M.METAL_D, (x + 50, y + 2, 5, 12))
    if _S["gen_on"]:
        for i in range(3):
            age = ((now * 0.0007) + i / 3.0) % 1.0
            sz = 5 + int(age * 6)
            tone = int(150 - age * 70)
            surf.fill((tone, tone, tone), (x + 50 - int(age * 10), y - int(age * 40), sz, sz))
    elif _S["kick"]:
        for i in range(KICK_NEED):
            col = (232, 200, 90) if i < _S["kick"] else (60, 56, 50)
            surf.fill(M.INK, (x + 10 + i * 12, y - 8, 11, 9))
            surf.fill(col, (x + 12 + i * 12, y - 6, 7, 5))


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
    surf.fill(M.INK, (x - 8, y - 56, 16, 14))
    surf.fill(col, (x - 6, y - 54, 12, 10))
    surf.fill(M.WOOD_D, (x - 5, y - 60, 10, 4))


def _draw_tractor(surf, now):
    x0, y0 = M.TRACTOR_AT[0] * T, M.TRACTOR_AT[1] * T
    u = 0.0
    if "tractor" in _S["preps"]:
        u = min(1.0, (now - _S["tractor_t"]) / float(TRACTOR_MS))
        u = u * u * (3.0 - 2.0 * u)
    px, py = M.TRACTOR_PARK
    _tractor(surf, int(x0 + (px - x0) * u) + OX, int(y0 + (py - y0) * u) + OY)
    if u >= 1.0:
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
    bob = int(math.sin(now * 0.002) * 1.5)
    figures = [(by + 14, "bodi", bx + OX, by + 14 + OY + bob, _face_to(bx, by), 0.0),
               (py, "biribel", px + OX, py + OY, _S["face"], _S["step"])]
    if _S["stage"] == PREP:
        ax, ay = M.tile_px(M.ALEX_TILE)
        figures.append((ay + 14, "alex", ax + OX, ay + 14 + OY + bob, _face_to(ax, ay), 0.0))
    for _, look, fx, fy, face, step in sorted(figures, key=lambda f: f[0]):
        _figure(surface, fx, fy, face, step, look, moving=look == "biribel" and bool(step))
    _draw_carry(surface, px + OX, py + OY)
    near = _S["near"]
    if near and not _S["lines"]:
        x, y = _point_px(near[0])
        _prompt.draw(surface, x + OX, y + OY, "[E] " + near[1], (236, 228, 196), font=font_prompt)
    obj = _objective()
    if obj:
        hud.draw_objective_panel(surface, obj, x=20, y=16)
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
        draw_dialogue_box(surface, who, line, n, len(line), can_continue=n >= len(line),
                          show_speaker=bool(who))
