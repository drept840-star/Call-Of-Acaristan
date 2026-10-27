"""Mission 7 raid HUD: the top-down game's panels (via the M6 yard HUD helpers), a
north-up farm minimap, speaker-coloured callouts, the Bodi countdown and the
hold-E bars.  Shapes are drawn, never glyphs: the terminal font has no arrows.
"""
import math

import pygame

from core.config import HEIGHT, WIDTH, font_terminal, font_terminal_small
from missions.m6 import hud3d as H
from missions.m6 import yard_hud as U

from . import raid_world as W

SPEAKER = {
    "BIRIBEL": (228, 230, 222),
    "BODI": (226, 170, 98),
    "ALEX": (122, 198, 234),
}
MAP_W, MAP_H = 168, 188
MAP_X0, MAP_X1, MAP_Z0, MAP_Z1 = -21.0, 46.0, -27.0, 46.0
_SCALE = min(MAP_W / (MAP_X1 - MAP_X0), MAP_H / (MAP_Z1 - MAP_Z0))
_FIRE_COL = (232, 120, 40)
_cache = {}


def _mp(x, z, ox, oy):
    """Farm metres -> minimap pixels (north up, east right)."""
    return int(ox + (x - MAP_X0) * _SCALE), int(oy + MAP_H - (z - MAP_Z0) * _SCALE)


def _base_map():
    img = _cache.get("map")
    if img is None:
        img = pygame.Surface((MAP_W, MAP_H), pygame.SRCALPHA)
        img.fill((8, 12, 18, 196))
        for x0, z0, x1, z1, h in W.STATIC:
            if h < 1.0:
                col = (60, 68, 60)
            elif h < 2.1:
                col = (46, 76, 52)
            else:
                col = (98, 104, 114)
            a = _mp(x0, z1, 0, 0)
            b = _mp(x1, z0, 0, 0)
            pygame.draw.rect(img, col, (a[0], a[1], max(1, b[0] - a[0]), max(1, b[1] - a[1])))
        pygame.draw.rect(img, (110, 118, 132), img.get_rect(), 1)
        _cache["map"] = img
    return img


def minimap(surface, s):
    ox, oy = WIDTH - MAP_W - 28, 28
    surface.blit(_base_map(), (ox, oy))
    for (i, j) in s.fire.cells:
        cx, cz = W.FIRE_COLS[i], W.FIRE_ROWS[j]
        p = _mp(cx, cz, ox, oy)
        pygame.draw.circle(surface, _FIRE_COL, p, 3)
    for e in s.brain.enemies:
        if e["alive"] and e["live"] and (s.t - e["aim"] < 2.5 or s.t - e["hit_t"] < 2.0):
            pygame.draw.circle(surface, (224, 70, 58), _mp(e["x"], e["z"], ox, oy), 2)
    for a, col in ((s.brain.alex, SPEAKER["ALEX"]), (s.brain.bodi, SPEAKER["BODI"])):
        pygame.draw.circle(surface, col, _mp(a["x"], a["z"], ox, oy), 3, 1 if a["state"] == "down" else 0)
    tx, tz = s.objective_point()
    if tx is not None:
        p = _mp(tx, tz, ox, oy)
        pygame.draw.rect(surface, U.OBJECTIVE_COL, (p[0] - 2, p[1] - 2, 5, 5))
    p = _mp(s.px, s.pz, ox, oy)
    yaw = math.radians(s.yaw)
    fx, fz = math.sin(yaw), math.cos(yaw)
    tip = (p[0] + fx * 7, p[1] - fz * 7)
    left = (p[0] - fz * 3.5 - fx * 3, p[1] - fx * 3.5 + fz * 3)
    right = (p[0] + fz * 3.5 - fx * 3, p[1] + fx * 3.5 + fz * 3)
    pygame.draw.polygon(surface, (240, 240, 232), [tip, left, right])


def callouts(surface, s):
    live = [c for c in s.lines if s.t - c[0] < c[3]][-2:]
    y = HEIGHT - 212
    for t0, who, text, dur in live:
        k = min(1.0, (dur - (s.t - t0)) / 0.4, (s.t - t0) / 0.15 + 0.05)
        col = SPEAKER.get(who, (228, 230, 222))
        alpha = int(255 * max(0.0, min(1.0, k)))
        r = H._text(surface, font_terminal_small, who + ":", col, (WIDTH // 2 - 6, y), "topright", alpha)
        H._text(surface, font_terminal_small, text, H.TEXT, (WIDTH // 2 + 2, y), "topleft", alpha)
        y += 20


def bodi_clock(surface, s):
    b = s.brain.bodi
    if b["state"] != "down":
        return
    left = max(0.0, 20.0 - (s.t - b["down_at"]))
    cx, y = WIDTH // 2, 74
    H._text(surface, font_terminal_small, "BODI IS DOWN - GET TO HIM", H.DANGER, (cx, y), "midtop")
    H._bar(surface, cx - 90, y + 20, 180, left / 20.0, H.DANGER, h=5)
    H._text(surface, font_terminal_small, "%d S" % int(math.ceil(left)), H.TEXT, (cx, y + 30), "midtop")


def hold_bar(surface, label, frac):
    cx, y = WIDTH // 2, HEIGHT - 164
    H._bar(surface, cx - 70, y, 140, frac, H.ACCENT, h=6)
    H._text(surface, font_terminal_small, label, H.TEXT, (cx, y - 18), "midtop")


def draw(surface, s):
    if s.hurt > 0.02:
        surface.fill((int(60 * max(0.0, min(1.0, s.hurt))), 0, 0), special_flags=pygame.BLEND_RGB_ADD)
    cx, cy = WIDTH // 2, HEIGHT // 2
    if s.dying:
        k = max(0.0, min(1.0, s.death_t / 2.0))
        veil = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        veil.fill((0, 0, 0, int(255 * k)))
        surface.blit(veil, (0, 0))
        img = font_terminal.render(s.death_msg, True, (220, 200, 190))
        surface.blit(img, img.get_rect(center=(cx, cy)))
        return
    U.hostiles(surface, s.brain.alive_count() + s.pending_count())
    head, dist = s.objective_text()
    U.objective(surface, head if dist is None else "%s (%d m)." % (head, int(round(dist))))
    minimap(surface, s)
    if s.marker_screen is not None and dist is not None:
        H.marker(surface, s.marker_screen, dist, None, col=U.OBJECTIVE_COL)
    U.reticle(surface, int(3 * s.recoil - 2 * s.ads))
    H.crosshair(surface, 0, lines=False,
                reload_frac=(1.0 - s.reloading / s.RELOAD_S) if s.reloading else 0.0,
                hit_age=s.t - s.hit_mark)
    H.damage_arcs(surface, s.dmg_marks, s.t, life=0.9)
    U.weapon(surface, s.hp(), s.hp_max(), s.mag, s.MAG, s.reserve, s.reloading, s.RELOAD_S)
    bodi_clock(surface, s)
    callouts(surface, s)
    if s.cp_toast and s.t - s.cp_toast < 2.6:
        H._text(surface, font_terminal, "CHECKPOINT", H.GOOD, (cx, 120), "midtop",
                int(255 * min(1.0, (2.6 - (s.t - s.cp_toast)) / 0.6)))
    prompt = s.prompt()
    if prompt is not None:
        label, key, hold = prompt
        if hold is not None:
            hold_bar(surface, label, hold)
        else:
            U.prompt(surface, label, key)
