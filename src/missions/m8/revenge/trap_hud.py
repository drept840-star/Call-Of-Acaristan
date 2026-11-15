"""Mission 8 Revenge - trap HUD: the raid's panels, tactical radar markers and
callouts on a north-up Route 12 minimap drawn from M2's tile grid."""
import math

import pygame

from core.config import HEIGHT, WIDTH, font_terminal, font_terminal_small
from missions.m6 import hud3d as H
from missions.m6 import yard_hud as U
from missions.m7 import raid_hud as RH

from . import set3d as S3
from . import trap_world as W

MAP_W, MAP_H = 160, 184
MAP_X0, MAP_X1, MAP_Z0, MAP_Z1 = S3.MAP_X0, S3.MAP_X1, S3.MAP_Z0, S3.MAP_Z1
_SCALE = min(MAP_W / (MAP_X1 - MAP_X0), MAP_H / (MAP_Z1 - MAP_Z0))
SPEAKER = dict(RH.SPEAKER, **{"VASILE": (196, 196, 214), "VASILE (PA)": (218, 202, 168)})
_cache = {}


def _mp(x, z, ox, oy):
    return int(ox + (x - MAP_X0) * _SCALE), int(oy + MAP_H - (z - MAP_Z0) * _SCALE)


def _base_map():
    img = _cache.get("map")
    if img is None:
        img = pygame.Surface((MAP_W, MAP_H), pygame.SRCALPHA)
        img.fill((8, 12, 18, 196))
        paved = {".": (34, 36, 40), "P": (34, 36, 40), "B": (34, 36, 40), "T": (34, 36, 40),
                 "O": (40, 42, 44), "X": (40, 42, 44), "s": (44, 44, 42), "d": (22, 24, 20)}
        for row in range(80):
            for col in range(70):
                c = paved.get(S3._glyph(col, row))
                if c:
                    x, z = S3.tile(col, row)
                    a, b = _mp(x - S3.TS / 2, z + S3.TS / 2, 0, 0), _mp(x + S3.TS / 2, z - S3.TS / 2, 0, 0)
                    pygame.draw.rect(img, c, (a[0], a[1], max(1, b[0] - a[0]), max(1, b[1] - a[1])))
        for x0, z0, x1, z1, h in W.STATIC:
            col = (60, 68, 60) if h < 1.0 else (98, 104, 114) if h > 3.0 else (80, 76, 70)
            a, b = _mp(x0, z1, 0, 0), _mp(x1, z0, 0, 0)
            pygame.draw.rect(img, col, (a[0], a[1], max(1, b[0] - a[0]), max(1, b[1] - a[1])))
        gz = _mp(0.0, S3.CATWALK_Z, 0, 0)[1]
        pygame.draw.line(img, (120, 126, 136), (_mp(S3.DECK_X[0], 0, 0, 0)[0], gz),
                         (_mp(S3.DECK_X[1], 0, 0, 0)[0], gz), 2)
        pygame.draw.rect(img, (110, 118, 132), img.get_rect(), 1)
        _cache["map"] = img
    return img


def minimap(surface, s):
    ox, oy = WIDTH - MAP_W - 28, 28
    surface.blit(_base_map(), (ox, oy))
    for bar in getattr(s, "barrels", ()):
        if bar["alive"]:
            pygame.draw.circle(surface, (232, 138, 54), _mp(bar["x"], bar["z"], ox, oy), 2)
    if getattr(s, "fuse_alive", False):
        p = _mp(W.FUSEBOX_AT[0], W.FUSEBOX_AT[1], ox, oy)
        pygame.draw.rect(surface, (240, 198, 72), (p[0] - 2, p[1] - 2, 4, 4))
    if getattr(s, "supply_left", False):
        p = _mp(W.SUPPLY_AT[0], W.SUPPLY_AT[1], ox, oy)
        pygame.draw.rect(surface, (118, 224, 132), (p[0] - 2, p[1] - 2, 5, 5))
    if not getattr(s, "gate_open", True) and s.phase in ("w1", "advance1"):
        p = _mp(W.KIOSK_AT[0], W.KIOSK_AT[1], ox, oy)
        pygame.draw.rect(surface, (238, 94, 72), (p[0] - 2, p[1] - 2, 5, 5))
    for t in s.brain.trucks:
        if t["state"] != "wait":
            p = _mp(t["x"], t["z"], ox, oy)
            col = (94, 86, 82) if t["crashed"] else (150, 64, 54)
            pygame.draw.rect(surface, col, (p[0] - 3, p[1] - 6, 7, 12))
    for e in s.brain.enemies:
        if e["alive"] and e["live"]:
            if e["kind"] == "overwatch" or s.t - e["aim"] < 2.5 or s.t - e["hit_t"] < 2.0:
                rad = 3 if e["kind"] in ("overwatch", "breacher", "officer") else 2
                col = (255, 62, 48) if e["kind"] == "overwatch" else (224, 70, 58)
                pygame.draw.circle(surface, col, _mp(e["x"], e["z"], ox, oy), rad)
    b = s.brain.bodi
    pygame.draw.circle(surface, SPEAKER["BODI"], _mp(b["x"], b["z"], ox, oy), 3,
                       1 if b["state"] == "down" else 0)
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
        alpha = int(255 * max(0.0, min(1.0, k)))
        H._text(surface, font_terminal_small, who + ":", SPEAKER.get(who, H.TEXT),
                (WIDTH // 2 - 6, y), "topright", alpha)
        H._text(surface, font_terminal_small, text, H.TEXT, (WIDTH // 2 + 2, y), "topleft", alpha)
        y += 20


def _tactical_status(surface, s, cx):
    truck = s.active_truck()
    if truck is not None:
        w, h = 260, 11
        x, y = cx - w // 2, 58
        frac = max(0.0, min(1.0, truck["hp"] / max(1.0, truck["max_hp"])))
        fill_col = (232, 66, 48) if frac < 0.35 else (204, 88, 56)
        pygame.draw.rect(surface, (14, 18, 24), (x - 2, y - 2, w + 4, h + 4))
        if frac > 0.0:
            fw = max(2, int(w * frac))
            pygame.draw.rect(surface, fill_col, (x, y, fw, h))
            pygame.draw.rect(surface, (245, 142, 102), (x, y, fw, 2))
        for q in (0.25, 0.50, 0.75):
            pygame.draw.line(surface, (24, 28, 34), (x + int(w * q), y), (x + int(w * q), y + h - 1), 1)
        pygame.draw.rect(surface, (150, 156, 168), (x - 2, y - 2, w + 4, h + 4), 1)
        H._text(surface, font_terminal_small, "GUARD TRUCK", (226, 214, 198), (cx, y - 4), "midbottom")
    if getattr(s, "sniper_locked", False):
        pulse = 0.65 + 0.35 * math.sin(s.t * 14.0)
        msg = "OVERWATCH LASER  -  TAKE COVER"
        if s.in_floodlight(s.px, s.pz):
            msg = "EXPOSED IN FLOODLIGHT  -  OVERWATCH LOCK"
        H._text(surface, font_terminal_small, msg, (255, 86, 74),
                (cx, 96), "midtop", int(255 * pulse))


def _grenade_warnings(surface, s):
    for screen, dist, rem_frac in getattr(s, "grenade_markers", ()):
        if dist > 9.5:
            continue
        sx, sy, front = screen
        pad = 44
        inside = front and pad <= sx <= WIDTH - pad and pad <= sy <= HEIGHT - pad
        if not inside:
            cx, cy = WIDTH / 2.0, HEIGHT / 2.0
            dx, dy = (sx - cx, sy - cy) if front else (cx - sx, cy - sy)
            if abs(dx) < 1e-3 and abs(dy) < 1e-3:
                dy = 1.0
            scale = min((WIDTH / 2.0 - pad) / max(1e-3, abs(dx)),
                        (HEIGHT / 2.0 - pad) / max(1e-3, abs(dy)))
            sx, sy = cx + dx * scale, cy + dy * scale
        px, py = int(sx), int(sy)
        urgent = dist < 5.6
        blink = 0.55 + 0.45 * math.sin(s.t * (22.0 if urgent else 10.0))
        col = (255, 74, 52) if urgent else (244, 168, 64)
        H.diamond(surface, px, py, col, 9, 2)
        H.diamond(surface, px, py, (255, 224, 180), 4)
        label = "GRENADE %dM" % max(1, int(round(dist)))
        H._text(surface, font_terminal_small, label, col, (px, py - 14), "midbottom", int(255 * blink))


def draw(surface, s):
    if s.hurt > 0.02:
        h_int = int(75 * max(0.0, min(1.0, s.hurt)))
        surface.fill((int(h_int * 0.55), 0, 0), special_flags=pygame.BLEND_RGB_ADD)
        for k in range(3):
            t_b = 14 * (3 - k)
            v = int(h_int * (0.24 - k * 0.05))
            if v > 0:
                surface.fill((v, 0, 0), (0, 0, WIDTH, t_b), special_flags=pygame.BLEND_RGB_ADD)
                surface.fill((v, 0, 0), (0, HEIGHT - t_b, WIDTH, t_b), special_flags=pygame.BLEND_RGB_ADD)
    cx, cy = WIDTH // 2, HEIGHT // 2
    if s.dying:
        k = max(0.0, min(1.0, s.death_t / 2.0))
        veil = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        veil.fill((0, 0, 0, int(255 * k)))
        surface.blit(veil, (0, 0))
        img = font_terminal.render(s.death_msg, True, (220, 200, 190))
        surface.blit(img, img.get_rect(center=(cx, cy)))
        return
    fighting = s.phase not in ("clear", "climb", "catwalk")
    if fighting:
        U.hostiles(surface, s.brain.alive_count() + s.pending_count())
    head, dist = s.objective_text()
    U.objective(surface, head if dist is None else "%s (%d m)." % (head, int(round(dist))))
    minimap(surface, s)
    _tactical_status(surface, s, cx)
    if s.marker_screen is not None and dist is not None:
        H.marker(surface, s.marker_screen, dist, None, col=U.OBJECTIVE_COL)
    _grenade_warnings(surface, s)
    rel_tot = s.reload_total() if hasattr(s, "reload_total") else s.RELOAD_S
    slot_prog, slot_count = s.reload_shell_info() if hasattr(s, "reload_shell_info") else (None, None)
    if s.phase not in ("climb", "catwalk"):
        U.reticle(surface, int(3 * s.recoil - 2 * s.ads))
        H.crosshair(surface, 0, lines=False,
                    reload_frac=(1.0 - s.reloading / rel_tot) if s.reloading else 0.0,
                    hit_age=s.t - s.hit_mark)
    H.damage_arcs(surface, s.dmg_marks, s.t, life=0.9)
    wname = getattr(s, "weapon", "shotgun")
    if wname == "rifle":
        U.weapon(surface, s.hp(), s.hp_max(), s.mag, s.MAG, s.reserve, s.reloading, rel_tot,
                 cw="os12", label="OS-12", caliber="5.56X45", kind="stick", reload_ms=90)
    else:
        U.weapon(surface, s.hp(), s.hp_max(), s.mag, s.MAG, s.reserve, s.reloading, rel_tot,
                 cw="fallow12", label="FALLOW 12", caliber="12GA", kind="shell", reload_ms=132,
                 slot_prog=slot_prog, slot_count=slot_count)
    if s.phase not in ("climb", "catwalk"):
        H._text(surface, font_terminal_small, "[Q] SWAP WEAPON", (156, 152, 138),
                (WIDTH - 32, HEIGHT - 28), "bottomright", 200)
    RH.bodi_clock(surface, s)
    callouts(surface, s)
    if s.cp_toast and s.t - s.cp_toast < 2.6:
        H._text(surface, font_terminal, "CHECKPOINT", H.GOOD, (cx, 120), "midtop",
                int(255 * min(1.0, (2.6 - (s.t - s.cp_toast)) / 0.6)))
    prompt = s.prompt()
    if prompt is not None:
        label, key, hold = prompt
        if hold is not None:
            RH.hold_bar(surface, label, hold)
        else:
            U.prompt(surface, label, key)
