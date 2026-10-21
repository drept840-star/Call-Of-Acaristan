"""Mission 6 yard - the 2D top-down game's HUD, brought into the 3D fight.

The yard used the thin tactical HUD of ``hud3d``.  This draws the panels the
top-down missions use instead, from the same engine widgets, so the 3D yard
reads as the same game: HOSTILES box and OBJECTIVE banner top left, the
magazine-icon weapon panel over the HP strip bottom left, the tiled corner
minimap (m6 palette) top right, the orange combat reticle and the key-cap
interaction prompt.  The yard is rasterised into a tile grid once so the
minimap is the real ``MiniMap``, not a look-alike.

Only the 3D-only pieces stay from ``hud3d``: hit markers and the reload arc
round the reticle, damage arcs, and the off-screen objective diamond.
"""
from __future__ import annotations

import math
from types import SimpleNamespace

import pygame

from core.config import HEIGHT, WIDTH, font_prompt, font_terminal_small
from engine.ui import health_bar as _health_bar
from engine.ui import hostiles as _hostiles
from engine.ui import weapon_panel as _weapon_panel
from engine.ui.std import crosshair as _reticle
from entities.art_cache import get_panel_bg
from ui.hud import THEME, MiniMap, draw_objective_panel, draw_pinned_radio

CELL = 0.5           # metres per minimap tile
TILE = 64            # the 2D world's tile size in px: MiniMap's unit
OBJECTIVE_COL = (255, 220, 100)   # the 2D minimap's objective square

_MAP = {}            # the baked MiniMap and its grid origin (built once)


def _grid(bounds, blockers, platform, rails, road_x):
    """Rasterise the yard into the 2D game's tile letters (m6 palette):
    ``W`` wall, ``C`` cover, ``O`` platform, ``Y`` its yellow edge, ``K``
    rail, ``g`` the truck road, ``.`` snow."""
    bx0, bx1, bz0, bz1 = bounds
    x1, z0 = bx1 + 1.0, bz0 - 1.0
    cols = int(math.ceil((bx1 - bx0 + 2.0) / CELL))
    rows = int(math.ceil((bz1 - bz0 + 2.0) / CELL))
    solids = [(a, c, d, f) for a, b, c, d, e, f in blockers
              if b < 1.5 and d - a <= 50 and f - c <= 25]
    px0, pz0, px1, pz1 = platform
    grid = []
    for r in range(rows):
        z = z0 + (r + 0.5) * CELL
        row = []
        for c in range(cols):
            x = x1 - (c + 0.5) * CELL          # engine3d mirrors x: +x is west
            if not (bx0 <= x <= bx1 and bz0 <= z <= bz1):
                row.append("W")
            elif any(a <= x <= d and cc <= z <= f for a, cc, d, f in solids):
                row.append("C")
            elif px0 <= x <= px1 and pz0 <= z <= pz1:
                row.append("Y" if z - pz0 < CELL else "O")
            elif any(abs(z - zr) < 0.75 for zr in rails):
                row.append("K")
            elif abs(x - road_x) < 2.5:
                row.append("g")
            else:
                row.append(".")
        grid.append("".join(row))
    return grid, (x1, z0)


def build_minimap(bounds, blockers, platform, rails, road_x):
    if "map" not in _MAP:
        grid, origin = _grid(bounds, blockers, platform, rails, road_x)
        _MAP["map"] = MiniMap(grid, tile_size=TILE, palette="m6")
        _MAP["origin"] = origin
    return _MAP["map"]


def _px(x, z):
    """Yard metres -> the minimap's world pixels."""
    x1, z0 = _MAP["origin"]
    return (x1 - x) / CELL * TILE, (z - z0) / CELL * TILE


def _actor(x, z, angle=0.0):
    rect = pygame.Rect(0, 0, 2, 2)
    px, py = _px(x, z)
    rect.center = (int(px), int(py))
    return SimpleNamespace(rect=rect, angle=angle)


def minimap(surface, player, facing, enemies, objective):
    """``player`` / ``objective`` (x, z), ``facing`` (dx, dz), ``enemies``
    [(x, z)].  The heading becomes the panel's screen angle (x mirrored, z
    down).  No camera box: the 2D one marks the screen's slice of the map."""
    mm = _MAP.get("map")
    if mm is None:
        return
    me = _actor(player[0], player[1], math.atan2(facing[1], -facing[0]))
    mm.draw(surface, me, [_actor(x, z) for x, z in enemies], None, None,
            notebook_pos=_px(*objective) if objective else None)


def objective(surface, text):
    draw_objective_panel(surface, text)
    draw_pinned_radio(surface)


def hostiles(surface, count):
    _hostiles.draw(surface, THEME, count)


def _mag_icon(surface, mx, my, kind, rounds, capacity, active):
    """The K-9 stick mag the 2D weapon panel was laid out for: M5's baked
    shell with its 12 witness holes.  Without the art, M6's own top-down
    painter, moved down into the panel (it draws centred, not from the top)."""
    rounds, capacity = max(0, int(rounds)), max(1, int(capacity))
    try:
        from art import m5 as _art
        shell = _art.get("mag_icon", 0 if rounds <= 0 else (1 if active else 2))
    except Exception:
        shell = None
    if shell is None:
        from .draw import _draw_mag_icon       # late: pulls in the 2D mission
        _draw_mag_icon(surface, mx + 12, my + 26, kind, rounds, capacity, active)
        return
    surface.blit(shell, (mx, my - 3))
    col = (220, 190, 70) if active else (150, 128, 58)
    for row in range(min(12, int(round(rounds / capacity * 12)))):
        for dx in (10, 14):
            pygame.draw.circle(surface, col, (mx + dx, my + 44 - row * 3), 1)


def weapon(surface, hp, hp_max, mag, mag_size, reserve, reload_left, reload_s):
    """HP strip and the K-9 panel.  ``reload_left`` seconds of the reload to
    go (0 when not reloading); the panel's bar runs on 2D frames."""
    _health_bar.draw(surface, THEME, hp, hp_max, panel_bg=get_panel_bg)
    dur = _weapon_panel.RELOAD_MS["k9_smg"]
    info = _weapon_panel.WeaponInfo(
        cw="k9_smg", label="K-9 SMG", caliber="9MM-S", kind="stick",
        ammo=mag, mag=mag_size, spares=-(-reserve // mag_size),
        reloading=reload_left > 0.0,
        reload_timer=int(round(dur * reload_left / reload_s)) if reload_left > 0.0 else 0)
    _weapon_panel.draw(surface, THEME, info, panel_bg=get_panel_bg, mag_icon=_mag_icon)


def reticle(surface, spread=0):
    """The 2D game's orange combat reticle, pinned to the screen centre
    (the 2D one follows the mouse; here the camera is the mouse)."""
    from core.config import C_ORANGE
    from core.user_settings import SETTINGS
    try:
        if not SETTINGS.show_crosshair:
            return
        size = max(3, int(SETTINGS.crosshair_size))
        cb = SETTINGS.colorblind_mode
    except Exception:
        size, cb = 6, "none"
    col = _reticle.color_for(cb, default=C_ORANGE)
    _reticle.draw_combat(surface, WIDTH // 2, HEIGHT // 2, size=size + spread, color=col)


def prompt(surface, label, key=None):
    """The top-down missions' interaction prompt: a key cap and the label in a
    framed strip above the HUD.  No ``key`` draws the strip alone (pickups)."""
    tw = font_prompt.size(label)[0]
    pad = 40 if key else 12
    w = tw + pad + 18
    x, y = (WIDTH - w) // 2, HEIGHT - 128
    panel = pygame.Surface((w, 34), pygame.SRCALPHA)
    panel.fill((6, 9, 14, 220))
    pygame.draw.rect(panel, (110, 118, 132), panel.get_rect(), 1)
    if key:
        cap = pygame.Rect(8, 6, 24, 22)
        pygame.draw.rect(panel, (28, 30, 36), cap, border_radius=3)
        pygame.draw.rect(panel, (150, 156, 168), cap, 1, border_radius=3)
        kt = font_terminal_small.render(key, True, (232, 232, 224))
        panel.blit(kt, (cap.centerx - kt.get_width() // 2, cap.centery - kt.get_height() // 2))
    panel.blit(font_prompt.render(label, True, (222, 224, 218)), (pad, 8))
    surface.blit(panel, (x, y))
