
"""artpack.py - loaded-sprite registry with procedural fallback.

Phase 1/2/4 of the graphics rework ride on one contract, inherited from
``entities.sprite_lib``: **every getter returns ``None`` when the PNG is
absent**, and every call site keeps its procedural renderer as the
fallback. A bare zip or stripped install therefore still runs the game;
only the art tier degrades.

Assets live in ``assets/art/`` and are authored by
``tools/make_art_pack.py`` (palette-locked, 1:1, house style). ``build.bat``
already bundles the whole ``assets/`` tree, so nothing else needs wiring.

Environment switches:
    ACA_ART=legacy   force every getter to None (A/B previews, debugging)
    ACA_ART=off      same as legacy
"""

import json
import os

import pygame

from engine.anim.pose_cache import POSES as _POSES_CACHE

# RPE6 Phase 2 (A-006): moved verbatim from core/artpack.py (owner module of engine.assets.artpack) except for the injection points marked RPE6.
__all__ = ["configure", "enabled", "path", "get", "tile", "wall", "icon", "light", "blit", "blit9slice",
           "pose", "sheet", "frame", "frame_anchor", "blit_frame", "vehicle", "prop", "fx", "rebuild"]

_RESOLVE = None   # RPE6: path resolver injected by the host (core.config.resource_path in the game)


def configure(resolve):
    """Set the function that maps a repo-relative directory to an absolute one."""
    global _RESOLVE
    _RESOLVE = resolve


def resource_path(rel):
    return _RESOLVE(rel) if _RESOLVE is not None else rel

_ART_DIR = os.path.join("assets", "art")
_CACHE = {}
_MISSING = object()


def enabled():
    """False when the loaded-art tier is switched off entirely."""
    return os.environ.get("ACA_ART", "") not in ("legacy", "off")


def path(name):
    return os.path.join(resource_path(_ART_DIR), name + ".png")


def get(name):
    """Cached Surface for assets/art/<name>.png, or None when unavailable."""
    if not enabled():
        return None
    hit = _CACHE.get(name, _MISSING)
    if hit is not _MISSING:
        return hit
    surf = None
    p = path(name)
    try:
        if os.path.exists(p):
            surf = pygame.image.load(p).convert_alpha()
    except Exception:
        surf = None
    _CACHE[name] = surf
    return surf


# ── Tileset access ──────────────────────────────────────────────────────
# Variant counts per map code. "."/"g"/"O"/"d"/"s" get 4 seeded variants;
# the checkerboard floors (K/L/Y/M) get an a/b pair matching (col+row)%2,
# which is exactly the parity the procedural renderer used.
# "d"/"s" are Mission 2's ditch and service road. They used to be absent
# here, which silently sent those two 23x15-tile regions down the flat
# pygame.draw.rect fallback in m2/draw.py - hence the hard-edged untextured
# slabs in the overview.
_TILE_VARIANTS = {".": 4, "g": 4, "O": 4, "d": 4, "s": 4}
_CHECKER_CODES = ("K", "L", "Y", "M")


def _variant_index(col, row, n):
    # Deterministic spatial hash: clustered enough to look authored,
    # mixed enough to avoid visible tiling.
    h = (col * 73856093) ^ (row * 19349663)
    h = (h ^ (h >> 13)) * 1274126177
    return (h ^ (h >> 16)) % n


def tile(code, col, row):
    """Floor tile surface for map code at (col,row), or None."""
    if code in _TILE_VARIANTS:
        return get("t_%s_%d" % (code if code != "." else "dot",
                                _variant_index(col, row, _TILE_VARIANTS[code])))
    if code in _CHECKER_CODES:
        return get("t_%s_%s" % (code, "a" if (col + row) % 2 == 0 else "b"))
    return None


def wall(code, col, row):
    """Wall / barrier / glass tile surface, or None."""
    if code == "C":
        return get("w_C_%d" % _variant_index(col, row, 4))
    if code == "B":
        return get("w_B_%d" % _variant_index(col, row, 2))
    if code == "S":
        return get("w_S")
    return None


# ── Small helpers ───────────────────────────────────────────────────────
def icon(name):
    return get("i_" + name)


def light(name):
    return get("L_" + name)


def blit(surf, name, pos):
    """Blit a named sprite if present. Returns True when blitted."""
    s = get(name)
    if s is None:
        return False
    surf.blit(s, pos)
    return True


def blit9slice(surf, name, rect):
    """9-slice a 24x24 source panel into rect. False when source missing."""
    s = get(name)
    if s is None:
        return False
    r = pygame.Rect(rect)
    m = 8  # source corner margin
    sw = sh = 24
    # corners
    surf.blit(s.subsurface((0, 0, m, m)), (r.x, r.y))
    surf.blit(s.subsurface((sw - m, 0, m, m)), (r.right - m, r.y))
    surf.blit(s.subsurface((0, sh - m, m, m)), (r.x, r.bottom - m))
    surf.blit(s.subsurface((sw - m, sh - m, m, m)), (r.right - m, r.bottom - m))
    # edges (stretched along one axis only)
    top = pygame.transform.scale(s.subsurface((m, 0, sw - 2 * m, m)),
                                 (r.width - 2 * m, m))
    surf.blit(top, (r.x + m, r.y))
    bot = pygame.transform.scale(s.subsurface((m, sh - m, sw - 2 * m, m)),
                                 (r.width - 2 * m, m))
    surf.blit(bot, (r.x + m, r.bottom - m))
    left = pygame.transform.scale(s.subsurface((0, m, m, sh - 2 * m)),
                                  (m, r.height - 2 * m))
    surf.blit(left, (r.x, r.y + m))
    right = pygame.transform.scale(s.subsurface((sw - m, m, m, sh - 2 * m)),
                                   (m, r.height - 2 * m))
    surf.blit(right, (r.right - m, r.y + m))
    mid = pygame.transform.scale(s.subsurface((m, m, sw - 2 * m, sh - 2 * m)),
                                 (r.width - 2 * m, r.height - 2 * m))
    surf.blit(mid, (r.x + m, r.y + m))
    return True


# ── Pose cache (phase 4) ────────────────────────────────────────────────
# Owner: engine.anim.pose_cache.POSES (Phase 3 moved the LRU there; this is a delegate).


def pose(key, size, draw_cb):
    """Render-once cache for parameterised procedural bodies.

    ``draw_cb(surface)`` draws the body into a fresh SRCALPHA surface of
    ``size``; the result is cached under ``key`` and blitted by callers.
    This turns per-frame polygon soup into a single blit without authoring
    any new art, and it is where outlines/shading get baked in for free.
    """
    return _POSES_CACHE.get(key, size, draw_cb)


# -- Generated sprite sheets (Polish T7) ----------------------------------
# Sheets are authored by tools/sprites/<family>.py (see tools/build_all_sprites.py)
# as assets/art/spr_<family>.png + .json. The JSON frame table maps a key to
# {"rect": [x, y, w, h], "anchor": [ax, ay]}; "scale" (integer, default 1,
# sheet-level or per-frame) means the sheet was authored at 1/scale resolution and is upscaled here
# with nearest-neighbour only. Same contract as get(): None when ACA_ART is
# legacy/off, when the PNG/JSON is missing, or when the JSON disagrees with
# the PNG - callers then fall back to their procedural renderer.
_SHEETS = {}
_FRAMES = {}


def _load_sheet(name):
    img = get(name)
    if img is None:
        return None
    jp = os.path.join(resource_path(_ART_DIR), name + ".json")
    try:
        with open(jp, "r", encoding="utf-8") as fh:
            meta = json.load(fh)
    except Exception:
        return None
    if list(meta.get("size", ())) != [img.get_width(), img.get_height()]:
        return None
    scale = int(meta.get("scale", 1) or 1)
    if scale < 1:
        return None
    return {"image": img, "frames": meta.get("frames", {}), "scale": scale}


def sheet(name):
    """Loaded sheet dict {image, frames, scale}, or None when unavailable."""
    if not enabled():
        return None
    hit = _SHEETS.get(name, _MISSING)
    if hit is _MISSING:
        hit = _load_sheet(name)
        _SHEETS[name] = hit
    return hit


def frame(sheet_name, key):
    """Cached Surface for one frame of a sheet (already integer-scaled)."""
    if not enabled():
        return None
    ck = (sheet_name, key)
    hit = _FRAMES.get(ck, _MISSING)
    if hit is not _MISSING:
        return hit
    surf = None
    sh = sheet(sheet_name)
    info = sh["frames"].get(key) if sh else None
    if info is not None:
        try:
            x, y, w, h = info["rect"]
            surf = sh["image"].subsurface((x, y, w, h))
            k = int(info.get("scale", sh["scale"]) or 1)
            if k != 1:
                # Nearest-neighbour integer upscale only (house rule).
                surf = pygame.transform.scale(surf, (w * k, h * k))
        except Exception:
            surf = None
    _FRAMES[ck] = surf
    return surf


def frame_anchor(sheet_name, key):
    """(ax, ay) of a frame in output pixels, or (0, 0) when unknown."""
    sh = sheet(sheet_name)
    info = sh["frames"].get(key) if sh else None
    if not info:
        return (0, 0)
    ax, ay = info.get("anchor", (0, 0))
    k = int(info.get("scale", sh["scale"]) or 1)
    return (ax * k, ay * k)


def blit_frame(surf, sheet_name, key, pos):
    """Blit frame so its anchor lands on pos. True when blitted."""
    img = frame(sheet_name, key)
    if img is None:
        return False
    ax, ay = frame_anchor(sheet_name, key)
    surf.blit(img, (int(pos[0]) - ax, int(pos[1]) - ay))
    return True


def vehicle(key):
    """Vehicle frame from spr_vehicles (cars, IPA truck, tanker), or None."""
    return frame("spr_vehicles", key)


def prop(key):
    """Mission 2 story-prop frame from spr_props_m2, or None."""
    return frame("spr_props_m2", key)


def fx(key):
    """Static FX frame (scorch decal, wreck, spot fires), or None."""
    return frame("spr_fx_scorch" if key == "scorch" else "spr_fx_m2", key)


def rebuild():
    """Drop caches after a display-mode change (mirrors art_cache)."""
    _CACHE.clear()
    _POSES_CACHE.clear()
    _SHEETS.clear()
    _FRAMES.clear()
