"""Mission 8 Duty - Mansion HUD: floor-aware minimap, weapon panel, area cards,
callouts, Andrei M.'s boss bar and the helicopter spin-up bar."""
import math

import pygame

from core.config import HEIGHT, WIDTH, font_terminal, font_terminal_small
from missions.m6 import hud3d as H
from missions.m6 import yard_hud as U
from missions.m7 import raid_hud as RH

from . import mansion_set as MS
from . import mansion_world as W

SPEAKER = dict(
    RH.SPEAKER,
    **{
        "VASILE": (196, 196, 214),
        "ANDREI M.": (236, 98, 84),
        "RETARDOVICI": (230, 200, 120),
    },
)
MAP_W, MAP_H = 160, 184
MAP_X0, MAP_X1, MAP_Z0, MAP_Z1 = W.BOUNDS[0] - 1.0, W.BOUNDS[1] + 1.0, W.BOUNDS[2] - 1.0, W.BOUNDS[3] + 1.0
_SCALE = 3.0
_cache = {}
_VEIL = [None]


def _get_veil(alpha):
    v = _VEIL[0]
    if v is None:
        v = _VEIL[0] = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
    v.fill((0, 0, 0, alpha))
    return v


def _mp(x, z):
    return int((x - MAP_X0) * _SCALE), int((MAP_Z1 - z) * _SCALE)


def _base_map(upper):
    img = _cache.get(upper)
    if img is None:
        img = pygame.Surface((int((MAP_X1 - MAP_X0) * _SCALE), int((MAP_Z1 - MAP_Z0) * _SCALE)), pygame.SRCALPHA)
        img.fill((8, 12, 18, 196))
        a, b = _mp(-MS.HX, MS.HZ), _mp(MS.HX, 0.0)
        pygame.draw.rect(img, (38, 40, 46), (a[0], a[1], b[0] - a[0], b[1] - a[1]))
        lo = MS.FF - 0.5 if upper else 0.0
        hi = MS.FF + 2.0 if upper else MS.GF + 2.0
        for x0, z0, x1, z1, y0, y1 in W.STATIC:
            if y1 - y0 > 20.0 or y1 <= lo + 0.3 or y0 >= hi:
                continue
            if x1 - x0 > 20.0 and z1 - z0 > 6.0:
                continue
            col = (60, 68, 60) if y1 - max(y0, lo) < 1.2 else (98, 104, 114)
            pa, pb = _mp(x0, z1), _mp(x1, z0)
            pygame.draw.rect(img, col, (pa[0], pa[1], max(1, pb[0] - pa[0]), max(1, pb[1] - pa[1])))
        _cache[upper] = img
    return img


def minimap(surface, s):
    ox, oy = WIDTH - MAP_W - 28, 28
    upper = s.py > 3.0
    base = _base_map(upper)
    cx, cz = _mp(s.px, s.pz)
    sx = max(0, min(base.get_width() - MAP_W, cx - MAP_W // 2))
    sz = max(0, min(base.get_height() - MAP_H, cz - MAP_H // 2))
    surface.blit(base, (ox, oy), pygame.Rect(sx, sz, MAP_W, MAP_H))

    def mp(x, z):
        p = _mp(x, z)
        return ox + p[0] - sx, oy + p[1] - sz

    def inside(p):
        return ox <= p[0] < ox + MAP_W and oy <= p[1] < oy + MAP_H

    for e in s.brain.enemies:
        if e["alive"] and e["live"] and (s.t - e["aim"] < 2.5 or s.t - e["hit_t"] < 2.0):
            p = mp(e["x"], e["z"])
            if inside(p):
                pygame.draw.circle(surface, (224, 70, 58), p, 2 if (e["y"] > 3.0) == upper else 1)
    for name, a in (("BODI", s.brain.bodi), ("ALEX", s.brain.alex)):
        p = mp(a["x"], a["z"])
        if inside(p):
            pygame.draw.circle(surface, SPEAKER[name], p, 3, 1 if a["state"] == "down" else 0)
    tx, tz = s.objective_point()
    if tx is not None:
        p = mp(tx, tz)
        p = (max(ox + 2, min(ox + MAP_W - 3, p[0])), max(oy + 2, min(oy + MAP_H - 3, p[1])))
        pygame.draw.rect(surface, U.OBJECTIVE_COL, (p[0] - 2, p[1] - 2, 5, 5))
    p = mp(s.px, s.pz)
    yaw = math.radians(s.yaw)
    fx, fz = math.sin(yaw), math.cos(yaw)
    tip = (p[0] + fx * 7, p[1] - fz * 7)
    left = (p[0] - fz * 3.5 - fx * 3, p[1] - fx * 3.5 + fz * 3)
    right = (p[0] + fz * 3.5 - fx * 3, p[1] + fx * 3.5 + fz * 3)
    pygame.draw.polygon(surface, (240, 240, 232), [tip, left, right])
    pygame.draw.rect(surface, (110, 118, 132), (ox, oy, MAP_W, MAP_H), 1)
    H._text(surface, font_terminal_small, "FIRST FLOOR" if upper else "GROUND", (156, 152, 138),
            (ox + MAP_W - 4, oy + MAP_H + 4), "topright", 200)


def callouts(surface, s):
    live = [c for c in s.lines if s.t - c[0] < c[3]][-2:]
    y = HEIGHT - 212
    for t0, who, text, dur in live:
        k = min(1.0, (dur - (s.t - t0)) / 0.4, (s.t - t0) / 0.15 + 0.05)
        alpha = int(255 * max(0.0, min(1.0, k)))
        H._text(surface, font_terminal_small, who + ":", SPEAKER.get(who, H.TEXT),
                (WIDTH // 2 - 6, y), "topright", alpha)
        H._text(surface, font_terminal_small, text, H.TEXT, (WIDTH // 2 + 2, y), "topleft", alpha)
        y += 20


def _bar(surface, title, frac, col, hi):
    cx, y, w, h = WIDTH // 2, 58, 320, 12
    pygame.draw.rect(surface, (16, 18, 22), (cx - w // 2 - 2, y - 2, w + 4, h + 4))
    if frac > 0.0:
        pygame.draw.rect(surface, col, (cx - w // 2, y, int(w * frac), h))
        pygame.draw.rect(surface, hi, (cx - w // 2, y, int(w * frac), 2))
    pygame.draw.rect(surface, (170, 176, 186), (cx - w // 2 - 2, y - 2, w + 4, h + 4), 1)
    H._text(surface, font_terminal_small, title, (240, 210, 198), (cx, y - 4), "midbottom")


def _andrei_boss_bar(surface, s):
    an = s.brain.andrei
    if an["state"] not in ("intro", "dying"):
        return False
    if an["state"] == "dying" and s.t - an["dead_t"] > 1.8:
        return False
    title = "ANDREI M.  //  HEAD OF PALACE IT & PAYROLL"
    if an["state"] == "dying":
        title = "ANDREI M.  //  ADMIN PRIVS REVOKED"
    _bar(surface, title, 1.0 if an["state"] == "intro" else 0.0, (220, 58, 48), (250, 130, 110))
    return True


def _heli_bar(surface, s):
    left = s.heli_left()
    if left is None:
        return
    frac = 1.0 - left / s.HELI_SPIN
    secs = int(math.ceil(left))
    title = "RETARDOVICI'S HELICOPTER  //  ROTORS %d%%  -  %d S" % (int(frac * 100), secs)
    if s.phase == "liftoff":
        title = "RETARDOVICI'S HELICOPTER  //  LIFTING OFF"
        frac = 1.0
    _bar(surface, title, frac, (226, 150, 56), (255, 210, 120))


def _area_card(surface, s):
    if not s.area_card:
        return
    t0, title, sub = s.area_card
    age = s.t - t0
    if age > 3.6:
        return
    a = int(255 * max(0.0, min(1.0, age / 0.35, (3.6 - age) / 0.7)))
    cx = WIDTH // 2
    H._text(surface, font_terminal, title, (236, 222, 190), (cx, 108), "midtop", a)
    H._text(surface, font_terminal_small, sub, (176, 170, 156), (cx, 140), "midtop", a)


def draw(surface, s):
    if s.hurt > 0.02:
        v = int(70 * max(0.0, min(1.0, s.hurt)))
        surface.fill((int(v * 0.55), 0, 0), special_flags=pygame.BLEND_RGB_ADD)
    cx, cy = WIDTH // 2, HEIGHT // 2
    if s.dying:
        k = max(0.0, min(1.0, s.death_t / 2.0))
        surface.blit(_get_veil(int(255 * k)), (0, 0))
        img = font_terminal.render(s.death_msg, True, (220, 200, 190))
        surface.blit(img, img.get_rect(center=(cx, cy)))
        return
    U.hostiles(surface, s.brain.alive_count())
    head, dist = s.objective_text()
    U.objective(surface, head if dist is None else "%s (%d m)." % (head, int(round(dist))))
    minimap(surface, s)
    if not _andrei_boss_bar(surface, s):
        _heli_bar(surface, s)
    if s.marker_screen is not None and dist is not None:
        H.marker(surface, s.marker_screen, dist, None, col=U.OBJECTIVE_COL)
    rel_tot = s.reload_total()
    slot_prog, slot_count = s.reload_shell_info()
    U.reticle(surface, int(3 * s.recoil - 2 * s.ads))
    H.crosshair(surface, 0, lines=False,
                reload_frac=(1.0 - s.reloading / rel_tot) if s.reloading else 0.0,
                hit_age=s.t - s.hit_mark)
    H.damage_arcs(surface, s.dmg_marks, s.t, life=0.9)
    if s.weapon == "rifle":
        U.weapon(surface, s.hp(), s.hp_max(), s.mag, s.MAG, s.reserve, s.reloading, rel_tot,
                 cw="os12", label="OS-12", caliber="5.56X45", kind="stick", reload_ms=90)
    else:
        U.weapon(surface, s.hp(), s.hp_max(), s.mag, s.MAG, s.reserve, s.reloading, rel_tot,
                 cw="fallow12", label="FALLOW 12", caliber="12GA", kind="shell", reload_ms=132,
                 slot_prog=slot_prog, slot_count=slot_count)
    H._text(surface, font_terminal_small, "[1/2/Q] WEAPONS", (156, 152, 138),
            (WIDTH - 32, HEIGHT - 28), "bottomright", 200)
    callouts(surface, s)
    _area_card(surface, s)
    prompt = s.prompt()
    if prompt is not None:
        label, key, hold = prompt
        if hold is not None:
            RH.hold_bar(surface, label, hold)
        else:
            U.prompt(surface, label, key)
