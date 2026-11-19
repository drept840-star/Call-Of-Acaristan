"""Mission 6 gameplay renderer.

The three maps share one painter: baked ground/props from ``decor``, the
campaign's rotating top-down Guard sprite, Volkov as an upright cast figure,
floodlight cones, then the same HUD grammar as M4/M5.  The train hands the
whole frame to ``train3d`` while it is active.
"""
import math
import os


import pygame

from game import topdown3d as _td

from core.config import (
    C_BG_GAME, HEIGHT, MUZZLE_FLASH, TILE_SIZE, WIDTH,
    draw_scanlines, draw_vignette, font_prompt, font_terminal_small, screen,
)
from core.state import STATE
from core.camera import draw_bullets
from core import artpack, outfits as _outfits
from entities.art_cache import get_blood_decal, get_panel_bg
from entities import weapons as _weapons
from engine.core import now_ms as _now_ms
from engine.ui import health_bar as _hud_health_bar
from engine.ui import hostiles as _hud_hostiles
from engine.ui import objective_banner as _hud_objective
from engine.ui import weapon_panel as _hud_weapon_panel
from ui.hud import THEME, draw_combat_reticle, draw_pinned_radio

from . import hud_ui as _hud_ui
from . import decor as _decor
from . import flow as _flow
from . import maps as _maps
from . import stealth as _stealth
from . import combat as _combat
from . import world as _world
from .meta import (
    STAGE_CUSTOMS, STAGE_NOMAN, STAGE_RAIL, STAGE_BOXCAR, STAGE_TRAIN,
)

M6_TILE_BASE = _decor.M6_TILE_BASE

# One-shot diagnostic for a train frame that cannot be rasterised (see
# _draw_train: a draw error fails the run, never the mission).
_train_draw_warned = False

# Named cast bodies are supersampled 3x and cached once per facing.
_KIT_SS = 3
_KIT_SCALE = 0.232              # ~58 px tall (foot y+22 -> crown y-36)
_ANCHOR = (42, 48)
_POSE = (84, 84)


# ─────────────────────────────────────────────
# Actors
# ─────────────────────────────────────────────
def _kit_body(who, wardrobe, right, headgear=True):
    from engine.anim import SPECS, draw_character
    spec = {**SPECS[who], **(wardrobe or {})}
    k = _KIT_SCALE * _KIT_SS * spec["height"] / 296.0
    big = pygame.Surface((_POSE[0] * _KIT_SS, _POSE[1] * _KIT_SS), pygame.SRCALPHA)
    foot = (_ANCHOR[1] + 22) * _KIT_SS
    draw_character(big, who, _ANCHOR[0] * _KIT_SS, foot, _KIT_SCALE * _KIT_SS,
                   right, wardrobe=wardrobe or None)
    if headgear:
        hx = _ANCHOR[0] * _KIT_SS
        hy = foot - 258 * k
        f = 1 if right else -1
        rw = max(4, round(30 * k))
        rh = max(2, round(9 * k))
        pygame.draw.ellipse(big, (18, 18, 22), (hx - rw, hy - 10 * k, rw * 2, rh))
        pygame.draw.line(big, (42, 42, 46), (hx - rw + 2, hy - 8 * k),
                         (hx + rw - 2, hy - 8 * k), max(1, round(k * 1.2)))
        pygame.draw.circle(big, (176, 36, 36),
                           (round(hx + f * 14 * k), round(hy - 9 * k)),
                           max(1, round(3 * k)))
    return pygame.transform.smoothscale(big, _POSE)


def _draw_guard(surface, enemy, cam_x, cam_y):
    x = int(enemy.rect.centerx - cam_x)
    y = int(enemy.rect.centery - cam_y)
    if not (-60 < x < WIDTH + 60 and -60 < y < HEIGHT + 60):
        return
    from missions.m5.draw import _draw_m5_guard  # lazy: shared campaign Guard art
    # No halo and no hostile ring here: the Guard reads off his own contact
    # shadow (drawn by the shared art) plus the snow, exactly like M4/M5.
    _draw_m5_guard(surface, enemy, cam_x, cam_y)
    left = _world.entering(enemy)
    if left > 0.0:
        total = float(getattr(enemy, "m6_entry_total", 1.0) or 1.0)
        k = 1.0 - max(0.0, min(1.0, left / total))
        if k < 0.9:
            _entry_puff(surface, x, y, k, getattr(enemy, "uid", 0))
        return
    if getattr(enemy, "alerted", False):
        # Alerted is a state, not a bullseye: a small amber pip over the head,
        # the same grammar the other missions use for a live contact.
        t = _now_ms() / 1000.0
        a = 0.55 + 0.45 * math.sin(t * 7.0)
        pygame.draw.circle(surface, (236, 176, 84),
                           (x, y - 27), max(1, int(round(1.2 + a))), 0)


def _entry_puff(surface, x, y, k, seed):
    """Kicked-up snow at a walking-in Guard's feet (cheap, deterministic)."""
    fade = int(120 * (1.0 - k))
    if fade <= 4:
        return
    puff = pygame.Surface((46, 20), pygame.SRCALPHA)
    for i in range(4):
        h = ((seed + i) * 2654435761) & 0xFFFF
        px = 10 + (h % 26)
        py = 8 + ((h >> 6) % 8)
        pygame.draw.ellipse(puff, (206, 218, 232, fade),
                            (px - 7, py - 3, 14 + (h % 5), 7))
    surface.blit(puff, (x - 23, y + 12))


def _volkov_pose(right):
    return artpack.pose(("m6volkov_v1", bool(right)), _POSE,
                        lambda s: s.blit(_kit_body("volkov", None, right, headgear=False),
                                         (0, 0)))


def _draw_volkov(surface, v, cam_x, cam_y):
    x = int(v["x"] - cam_x)
    y = int(v["y"] - cam_y)
    if not (-60 < x < WIDTH + 60 and -60 < y < HEIGHT + 60):
        return
    right = math.cos(v.get("angle", -math.pi / 2)) >= 0
    surface.blit(_volkov_pose(right), (x - _ANCHOR[0], y - _ANCHOR[1]))
    tag = font_terminal_small.render("VOLKOV", True, (214, 188, 146))
    surface.blit(tag, (x - tag.get_width() // 2, y - 44 - tag.get_height()))


def _melee_progress():
    """0..1 swing progress from the real swing length, like M4/M5.

    ``weapons.handle_melee`` already stores ``STATE.melee_duration`` (it picks
    a different length for the K-9 buttstroke than for the pistol); M6 used to
    pass no progress at all, so ``Player.draw`` held the arm at the swing's
    first frame and the melee read as a frozen twitch instead of the
    buttstroke the other missions play.
    """
    if not getattr(STATE, "melee_active", False) or getattr(STATE, "melee_timer", 0) <= 0:
        return 0.0
    dur = max(1.0, float(getattr(STATE, "melee_duration", 18)))
    return max(0.0, min(1.0, 1.0 - STATE.melee_timer / dur))


def _player_is_moving():
    k = _maps._last_keys
    return bool(k) and (k[pygame.K_w] or k[pygame.K_s] or k[pygame.K_a]
                        or k[pygame.K_d]) and not _world._movement_locked()


def _scene_drawables(surface, cam_x, cam_y):
    """Static props + actors in one y-sorted list (tall props hide feet)."""
    stage = getattr(STATE, "mission6_stage", STAGE_CUSTOMS)
    out = _decor.tall_drawables(stage, cam_x, cam_y)
    out.extend(_combat.drawables(cam_x, cam_y))

    for body in getattr(STATE, "corpses", []):
        out.append((body.y + 12,
                    lambda s, b=body: b.draw(s, cam_x, cam_y)))

    for enemy in getattr(STATE, "enemies", []):
        if enemy.hp > 0:
            out.append((enemy.rect.bottom,
                        lambda s, e=enemy: _draw_guard(s, e, cam_x, cam_y)))

    v = _world.volkov()
    if v and not v.get("dead"):
        out.append((v["y"] + 22,
                    lambda s: _draw_volkov(s, v, cam_x, cam_y)))

    p = STATE.player
    if p:
        from entities import death_anim
        if not death_anim.should_skip_player_draw():
            p.story_outfit = _outfits.gameplay_outfit(STATE)
            out.append((p.rect.bottom,
                        lambda s: p.draw(
                            s, cam_x, cam_y, walls=_world.solid_walls(),
                            reload_active=getattr(STATE, "is_reloading", False),
                            reload_progress=(1.0 - STATE.reload_timer
                                             / max(1, getattr(STATE, "reload_duration", 72)))
                            if getattr(STATE, "is_reloading", False) else 0.0,
                            no_gun=getattr(STATE, "player_disarmed", False),
                            melee_active=getattr(STATE, "melee_active", False),
                            melee_progress=_melee_progress(),
                            is_moving=_player_is_moving(),
                        )))

    out.sort(key=lambda item: item[0])
    for _, draw in out:
        draw(surface)


# ─────────────────────────────────────────────
# World dressing
# ─────────────────────────────────────────────
def _objective_world_pos():
    stage = getattr(STATE, "mission6_stage", STAGE_CUSTOMS)
    return _flow._anchor_pos(stage)


def _draw_beacon(surface, cam_x, cam_y):
    if getattr(STATE, "m6_train_active", False):
        return
    pos = _objective_world_pos()
    if pos is None:
        return
    x, y = int(pos[0] - cam_x), int(pos[1] - cam_y)
    if not (-40 < x < WIDTH + 40 and -40 < y < HEIGHT + 40):
        return
    if not _combat.cleared():
        # Locked: a steady dim red ring and a padlock, no pulse.
        red = (190, 66, 56)
        pygame.draw.circle(surface, (10, 12, 16), (x, y), 15, 4)
        pygame.draw.circle(surface, red, (x, y), 14, 2)
        pygame.draw.rect(surface, (10, 12, 16), (x - 6, y - 1, 12, 9))
        pygame.draw.rect(surface, red, (x - 5, y, 10, 7))
        pygame.draw.lines(surface, red, False,
                          [(x - 3, y), (x - 3, y - 5), (x + 3, y - 5), (x + 3, y)], 1)
        return
    t = _now_ms() / 1000.0
    r = 13 + int(4 * (0.5 + 0.5 * math.sin(t * 3.2)))
    pygame.draw.circle(surface, (10, 12, 16), (x, y), r + 1, 4)
    pygame.draw.circle(surface, (216, 182, 78), (x, y), r, 2)
    pygame.draw.circle(surface, (246, 222, 140), (x, y), 2)


def _draw_pickup(surface, pu, cam_x, cam_y):
    x, y = int(pu[0] - cam_x), int(pu[1] - cam_y)
    if not (-40 < x < WIDTH + 40 and -40 < y < HEIGHT + 40):
        return
    kind = pu[2] if len(pu) > 2 else "bandage"
    ink = (10, 12, 16)
    if kind == "bandage":
        pygame.draw.ellipse(surface, (6, 8, 12), (x - 10, y + 3, 22, 8))
        pygame.draw.rect(surface, ink, (x - 10, y - 8, 20, 16), border_radius=4)
        pygame.draw.rect(surface, (222, 226, 224), (x - 9, y - 7, 18, 14),
                         border_radius=3)
        pygame.draw.rect(surface, (200, 70, 70), (x - 2, y - 6, 4, 12))
        pygame.draw.rect(surface, (200, 70, 70), (x - 6, y - 2, 12, 4))
        return
    body = pygame.Rect(x - 6, y - 12, 12, 24)
    pygame.draw.ellipse(surface, (6, 8, 12), (x - 9, y + 7, 20, 8))
    pygame.draw.rect(surface, ink, body.inflate(2, 2), border_radius=3)
    pygame.draw.rect(surface, (34, 40, 42), body, border_radius=2)
    pygame.draw.rect(surface, (96, 120, 116), body, 1, border_radius=2)
    for ri in range(4):
        pygame.draw.circle(surface, (210, 178, 70), (x, body.y + 4 + ri * 5), 2)


def _draw_pickup_mark(surface, pu, cam_x, cam_y):
    """Four hard corner ticks round a pickup, painted after the light pass so
    a loot drop reads in the dark."""
    x, y = int(pu[0] - cam_x), int(pu[1] - cam_y)
    if not (-40 < x < WIDTH + 40 and -40 < y < HEIGHT + 40):
        return
    kind = pu[2] if len(pu) > 2 else "bandage"
    col = (118, 226, 168) if kind == "bandage" else (240, 204, 92)
    r = 15 + int((_now_ms() // 260) % 2)
    for sx in (-1, 1):
        for sy in (-1, 1):
            cx, cy = x + sx * r, y + sy * r
            pygame.draw.line(surface, col, (cx, cy), (cx - sx * 4, cy), 1)
            pygame.draw.line(surface, col, (cx, cy), (cx, cy - sy * 4), 1)


def _draw_iff_lamps(surface, cam_x, cam_y, stage):
    """The squad's red IFF lamp on every living Guard, painted after the light
    pass: a Guard in the dark is still a red pin, not a dark smudge.  Skipped
    when a tall prop is in front of him, so it never leaks a Guard through a
    boxcar."""
    for e in getattr(STATE, "enemies", []):
        if e.hp <= 0 or _world.entering(e) > 0.0:
            continue
        x = int(e.rect.centerx - cam_x)
        y = int(e.rect.centery - cam_y)
        if not (-10 < x < WIDTH + 10 and -10 < y < HEIGHT + 10):
            continue
        if _decor.hides(stage, e.rect.centerx, e.rect.centery):
            continue
        px = x - int(math.cos(e.angle) * 7)
        py = y - int(math.sin(e.angle) * 7) - 1
        bright = int(_now_ms() / 600 + getattr(e, "uid", 0)) % 2 == 0
        pygame.draw.circle(surface, (10, 12, 16), (px, py), 3)
        pygame.draw.circle(surface, (232, 62, 52), (px, py), 2)
        if bright:
            pygame.draw.circle(surface, (255, 178, 150), (px, py), 1)


def _draw_exit_lamps(surface, cam_x, cam_y, stage):
    """Two status lamps on the exit's steel plate: red and blinking while
    Guards remain, steady green once the way is open."""
    if getattr(STATE, "m6_train_active", False):
        return
    pts = _decor.exit_lamps(stage)
    if not pts:
        return
    opened = _combat.cleared()
    col = (110, 232, 150) if opened else (232, 70, 58)
    if not opened and int(_now_ms() / 420) % 2:
        col = (96, 32, 28)
    for wx, wy in pts:
        x, y = int(wx - cam_x), int(wy - cam_y)
        if -10 < x < WIDTH + 10 and -10 < y < HEIGHT + 10:
            pygame.draw.circle(surface, (10, 12, 16), (x, y), 5)
            pygame.draw.circle(surface, col, (x, y), 4)
            pygame.draw.circle(surface, (255, 244, 230) if opened else (255, 150, 130),
                               (x - 1, y - 1), 1)


def _draw_emissives(surface, cam_x, cam_y, stage):
    """Everything that glows on its own, after the light multiply."""
    _draw_exit_lamps(surface, cam_x, cam_y, stage)
    for pu in getattr(STATE, "pickups", []):
        _draw_pickup_mark(surface, pu, cam_x, cam_y)
    _draw_iff_lamps(surface, cam_x, cam_y, stage)
    _combat.draw_blasts(surface, cam_x, cam_y)


def _draw_world_effects(surface, cam_x, cam_y):
    for decal in getattr(STATE, "blood_decals", [])[:]:
        try:
            d_surf = get_blood_decal(decal[3])
            d_surf.set_alpha(int(decal[2]))
            surface.blit(d_surf, (decal[0] - decal[3] - cam_x,
                                  decal[1] - decal[3] - cam_y))
            decal[2] -= 0.5
            if decal[2] <= 0 and decal in STATE.blood_decals:
                STATE.blood_decals.remove(decal)
        except Exception:
            if decal in getattr(STATE, "blood_decals", []):
                STATE.blood_decals.remove(decal)
    for pu in getattr(STATE, "pickups", []):
        _draw_pickup(surface, pu, cam_x, cam_y)
    for fire in getattr(STATE, "fire_zones", []):
        fire.draw(surface, cam_x, cam_y)
    _weapons.draw_thrown_bottles(surface, cam_x, cam_y)
    for particle in getattr(STATE, "particles", []):
        particle.draw(surface, cam_x, cam_y)
    for casing in getattr(STATE, "casings", []):
        casing.draw(surface, cam_x, cam_y)


def _draw_muzzle_flash(surface, cam_x, cam_y):
    if getattr(STATE, "muzzle_flash_timer", 0) <= 0 or STATE.player is None:
        return
    p = STATE.player
    if hasattr(p, "barrel_tip"):
        tx, ty = p.barrel_tip()
    else:
        tx = p.rect.centerx + math.cos(p.angle) * 39
        ty = p.rect.centery + math.sin(p.angle) * 39
    surface.blit(MUZZLE_FLASH, (tx - cam_x - 40, ty - cam_y - 40))
    STATE.muzzle_flash_timer -= 1


# ─────────────────────────────────────────────
# HUD
# ─────────────────────────────────────────────
_SHELL_CACHE = {}


def _draw_12ga_shell(surface, x, y, w, brass_w, active=True, tone="live"):
    """One horizontal 12-gauge shell (brass head on the left, red hull on the right)."""
    if tone == "reload":
        brass, brass_hi, brass_lo = (244, 206, 108), (255, 234, 160), (176, 132, 48)
        hull, hull_hi, hull_lo, crimp = (206, 76, 44), (242, 128, 72), (138, 38, 24), (168, 52, 32)
    elif active:
        brass, brass_hi, brass_lo = (212, 174, 78), (246, 222, 140), (146, 112, 40)
        hull, hull_hi, hull_lo, crimp = (184, 38, 32), (222, 76, 62), (114, 22, 20), (142, 30, 26)
    else:
        brass, brass_hi, brass_lo = (196, 158, 68), (228, 194, 106), (132, 102, 36)
        hull, hull_hi, hull_lo, crimp = (160, 38, 32), (194, 62, 52), (104, 22, 20), (128, 28, 24)
    hull_w = w - brass_w
    surface.fill(brass, (x, y, brass_w, 5))
    surface.fill(brass_hi, (x, y, brass_w, 1))
    surface.fill(brass_lo, (x, y + 4, brass_w, 1))
    surface.fill(brass_lo, (x + brass_w - 1, y + 1, 1, 3))
    surface.fill(hull, (x + brass_w, y, hull_w, 5))
    surface.fill(hull_hi, (x + brass_w, y, max(1, hull_w - 1), 1))
    surface.fill(hull_lo, (x + brass_w, y + 4, hull_w, 1))
    surface.fill(crimp, (x + w - 1, y + 1, 1, 3))


def _fallow_tube_bg(rim):
    key = ("tube", rim)
    s = _SHELL_CACHE.get(key)
    if s is None:
        s = pygame.Surface((26, 55), pygame.SRCALPHA)
        s.fill((74, 82, 92), (10, 0, 5, 2))
        s.fill((58, 66, 76), (5, 2, 15, 4))
        s.fill((112, 124, 138), (5, 2, 14, 1))
        for kx in (7, 10, 13, 16):
            s.fill((34, 38, 44), (kx, 3, 1, 2))
        s.fill((26, 32, 38), (3, 5, 19, 39))
        s.fill((12, 14, 18), (4, 6, 17, 37))
        pygame.draw.rect(s, rim, (3, 5, 19, 39), 1)
        for idx in range(6):
            sy = 37 - idx * 6
            s.fill((18, 21, 26), (5, sy + 1, 15, 3))
            s.fill((38, 44, 52), (5, sy + 1, 3, 3))
            s.fill((48, 56, 66), (11, sy + 2, 3, 1))
        s.fill((118, 72, 40), (3, 44, 19, 8))
        s.fill((152, 98, 56), (3, 44, 18, 1))
        s.fill((142, 90, 50), (3, 44, 1, 7))
        for rx in (6, 10, 14, 18):
            s.fill((76, 44, 26), (rx, 45, 1, 6))
        s.fill((28, 32, 38), (4, 52, 17, 3))
        s.fill(rim, (24, 5, 2, 46))
        _SHELL_CACHE[key] = s
    return s


def _fallow_card_bg(has_ammo):
    key = ("card6", bool(has_ammo))
    s = _SHELL_CACHE.get(key)
    if s is None:
        s = pygame.Surface((26, 55), pygame.SRCALPHA)
        if has_ammo:
            s.fill((86, 82, 64), (9, 2, 8, 3))
            s.fill((118, 112, 86), (9, 2, 7, 1))
            s.fill((44, 50, 42), (2, 5, 21, 41))
            pygame.draw.rect(s, (78, 86, 72), (2, 5, 21, 41), 1)
            s.fill((102, 112, 92), (2, 5, 20, 1))
            s.fill((92, 102, 82), (2, 5, 1, 40))
            s.fill((68, 74, 62), (3, 44, 19, 1))
        else:
            s.fill((36, 40, 48), (9, 2, 8, 3))
            s.fill((50, 56, 66), (9, 2, 7, 1))
            s.fill((20, 23, 28), (2, 5, 21, 41))
            pygame.draw.rect(s, (48, 54, 62), (2, 5, 21, 41), 1)
        for idx in range(6):
            sy = 37 - idx * 6
            s.fill((14, 16, 20), (5, sy + 1, 15, 3))
            s.fill((36, 40, 38) if has_ammo else (28, 32, 38), (12, sy, 3, 5))
        _SHELL_CACHE[key] = s
    return s


def _draw_fallow_icon(surface, ox, oy, rounds, capacity, active, reload_prog=0.0, incoming=0):
    rounds, capacity = max(0, int(rounds)), max(1, int(capacity))
    if active:
        rim = (220, 68, 58) if rounds <= 0 else ((232, 172, 56) if rounds == 1 else (120, 230, 180))
        surface.blit(_fallow_tube_bg(rim), (ox, oy))
        filled = min(6, int(round(rounds / capacity * 6))) if capacity != 6 else min(6, rounds)
        for idx in range(filled):
            _draw_12ga_shell(surface, ox + 5, oy + 37 - idx * 6, 15, 4, active=True, tone="live")
        if reload_prog > 0.0 and incoming > 0:
            step = reload_prog * incoming
            for s_i in range(incoming):
                idx = filled + s_i
                if idx >= 6:
                    break
                frac = step - s_i
                if frac <= 0.0:
                    continue
                sy = oy + 37 - idx * 6
                if frac >= 1.0:
                    _draw_12ga_shell(surface, ox + 5, sy, 15, 4, active=True, tone="reload")
                else:
                    w = max(3, int(round(15 * frac)))
                    surface.fill((232, 172, 56), (ox + 5 + (15 - w), sy + 1, w, 3))
        return
    filled = min(6, rounds if capacity == 6 else int(round(rounds / capacity * 6)))
    surface.blit(_fallow_card_bg(filled > 0), (ox, oy))
    for idx in range(filled):
        sy = oy + 37 - idx * 6
        _draw_12ga_shell(surface, ox + 5, sy, 15, 4, active=False, tone="live")
        surface.fill((42, 46, 38), (ox + 12, sy, 3, 5))
        surface.fill((62, 68, 56), (ox + 12, sy, 3, 1))
        surface.fill((26, 28, 24), (ox + 12, sy + 4, 3, 1))


def _draw_mag_icon(surface, mx, my, kind, rounds, capacity, active):
    if kind == "shell":
        _draw_fallow_icon(surface, mx - 12, my - 29, rounds, capacity, active)
        return
    color = (75, 220, 150) if active else (155, 165, 150)
    pygame.draw.rect(surface, (24, 27, 29), (mx - 7, my - 18, 14, 36), 1)
    if kind == "stick":
        pygame.draw.rect(surface, color, (mx - 4, my - 14, 8, 28), 1)
        filled = int(24 * max(0, min(1.0, rounds / max(1, capacity))))
        pygame.draw.rect(surface, color, (mx - 3, my + 10 - filled, 6, filled))
    else:
        pygame.draw.rect(surface, color, (mx - 5, my - 10, 10, 20), 1)
        filled = int(16 * max(0, min(1.0, rounds / max(1, capacity))))
        pygame.draw.rect(surface, color, (mx - 4, my + 8 - filled, 8, filled))


def _panel_mag_icon(surface, mx, my, kind, rounds, capacity, active,
                    reload_prog=0.0, incoming=0):
    """weapon_panel's mag slot: (mx, my) is the top left of a 25 x 56 cell.
    The K-9 stick (12 witness holes) uses M5's baked shell, while the Fallow 12
    draws its 6-shell magazine tube (active) or 12-shell reserve boxes (idle).
    A box mag or missing art falls back to _draw_mag_icon, which draws centred."""
    rounds, capacity = max(0, int(rounds)), max(1, int(capacity))
    if kind == "shell":
        _draw_fallow_icon(surface, mx, my - 3, rounds, capacity, active,
                          reload_prog=reload_prog, incoming=incoming)
        return
    state = 0 if rounds <= 0 else (1 if active else 2)
    base = {"stick": 0}.get(kind)
    shell = None
    if base is not None:
        try:
            from art import m5 as _art
            shell = _art.get("mag_icon", base + state)
        except Exception:
            shell = None
    if shell is None:
        _draw_mag_icon(surface, mx + 12, my + 26, kind, rounds, capacity, active)
        return
    surface.blit(shell, (mx, my - 3))
    col = (220, 190, 70) if active else (150, 128, 58)
    for row in range(min(12, int(round(rounds / capacity * 12)))):
        for dx in (10, 14):
            pygame.draw.circle(surface, col, (mx + dx, my + 44 - row * 3), 1)


def _draw_hud(surface, cam_x, cam_y):
    m = _hud_ui.HUD_MARGIN
    has_waves = bool(getattr(_combat, "_waves", ()))
    obj_y = m + (_hud_ui.CLUSTER_H if has_waves else 26) + 8
    _hud_objective.draw(surface, _maps._objective, _hud_ui.M6_THEME, x=m, y=obj_y)
    draw_pinned_radio(surface)
    if STATE.player:
        hp_y = HEIGHT - m - 30
        wpn_anchor_y = hp_y - _hud_ui.PANEL_GAP + 2
        _hud_health_bar.draw(surface, _hud_ui.M6_THEME, STATE.player.hp, STATE.player.max_hp,
                             panel_bg=_hud_ui.m6_panel_bg, x=m, y=hp_y)
        _hud_weapon_panel.draw(
            surface, _hud_ui.M6_THEME, _hud_weapon_panel.WeaponInfo.from_state(STATE),
            panel_bg=_hud_ui.m6_panel_bg, mag_icon=_panel_mag_icon, x=m, y=wpn_anchor_y)
        if not has_waves:
            _hud_hostiles.draw(surface, _hud_ui.M6_THEME, _combat.remaining(), x=m, y=m)
        if STATE.show_minimap and STATE.minimap:
            STATE.minimap._theme = _hud_ui.M6_THEME
            STATE.minimap.x = WIDTH - STATE.minimap.minimap_w - m
            STATE.minimap.y = m
            STATE.minimap.draw(surface, STATE.player,
                               [e for e in STATE.enemies if e.hp > 0],
                               cam_x, cam_y,
                               notebook_pos=_objective_world_pos())
        _stealth.draw_hud(surface)
        _combat.draw_hud(surface)


def _draw_prompt(surface):
    prompt = _flow.interaction_prompt()
    if not prompt:
        return
    label = prompt.split("  ", 1)[-1]
    f = font_prompt
    tw = f.size(label)[0]
    w = tw + 58
    x = (WIDTH - w) // 2
    y = HEIGHT - 128
    panel = pygame.Surface((w, 34), pygame.SRCALPHA)
    panel.fill((6, 9, 14, 220))
    pygame.draw.rect(panel, (110, 118, 132), panel.get_rect(), 1)
    key = pygame.Rect(8, 6, 24, 22)
    pygame.draw.rect(panel, (28, 30, 36), key, border_radius=3)
    pygame.draw.rect(panel, (150, 156, 168), key, 1, border_radius=3)
    kt = font_terminal_small.render("E", True, (232, 232, 224))
    panel.blit(kt, (key.centerx - kt.get_width() // 2, key.centery - kt.get_height() // 2))
    panel.blit(f.render(label, True, (222, 224, 218)), (40, 8))
    surface.blit(panel, (x, y))


# ─────────────────────────────────────────────
# Frame
# ─────────────────────────────────────────────
def _draw_train(surface):
    global _train_draw_warned
    try:
        from . import train3d as _train
        if not _train.active():
            return False
        _train.draw(surface)
        return True
    except Exception as exc:
        if (getattr(STATE, "player_dead", False)
                or getattr(STATE, "m6_train_death", False)
                or getattr(STATE, "m6_train_result", None) == "failed"):
            # The failure frame failed to rasterise, but this is still a
            # failed run: never convert a draw error into an ending handoff.
            return True
        # A render failure is not a story outcome.  This branch used to call
        # on_train_done("fallback"), which hands the mission to the ending
        # film - so one bad frame (e.g. a subtitle stamped in a dead run's
        # clock after a redeploy) passed Mission 6 for free.  A run that
        # cannot be drawn is a failed run: freeze it and let the failure
        # terminal offer the train checkpoint, exactly like a Guard kill.
        if not _train_draw_warned:
            _train_draw_warned = True
            print("M6 train draw failed (%s: %s) - failing the run, not the mission"
                  % (type(exc).__name__, exc))
        STATE.m6_train_active = False
        STATE.m6_train_death = True
        STATE.request_death_screen = True
        try:
            from . import train3d as _train
            _train.reset()          # stop the scene audio; the terminal owns the frame
        except Exception:
            pass
        return False


def _td3d_gate():
    """Enable 2.5D for all top-down M6 stages (set ACA_M6_RAIL_25D=0 for 2D rail).

    This gate also selects the aim camera; the train and post-train yard retain
    their own 3D hosts independently of the top-down view.
    """
    if (getattr(STATE, "m6_yard_active", False) or getattr(STATE, "m6_train_active", False)
            or getattr(STATE, "m6_train_death", False)):
        return False
    stage = getattr(STATE, "mission6_stage", STAGE_CUSTOMS)
    if stage == STAGE_RAIL and os.environ.get("ACA_M6_RAIL_25D") == "0":
        return False
    return stage in (STAGE_CUSTOMS, STAGE_NOMAN, STAGE_RAIL, STAGE_BOXCAR)


_td.GATES["MISSION6"] = _td3d_gate


def game_draw(fcx=0, fcy=0, surface=None):
    target = surface or screen
    if target is None:
        target = pygame.display.get_surface()
    if target is None:
        return

    if getattr(STATE, "m6_yard_active", False):
        try:
            from . import yard3d as _yard
            if _yard.active():
                _yard.draw(target)
                return
        except Exception as exc:
            print("M6 yard draw failed (%s: %s)" % (type(exc).__name__, exc))
            from . import yard3d as _yard
            _yard.force_finish("fallback")

    if ((getattr(STATE, "m6_train_active", False)
         or getattr(STATE, "m6_train_death", False))
            and _draw_train(target)):
        return

    if _td.active_cam() is not None:
        from . import draw3d as _draw3d
        if _draw3d.render_world(target, fcx, fcy):
            draw_vignette(target)
            draw_scanlines(target)
            _draw_hud(target, int(fcx), int(fcy))
            _draw_prompt(target)
            if STATE.player:
                draw_combat_reticle(target)
            return

    cam_x, cam_y = int(fcx), int(fcy)
    stage = getattr(STATE, "mission6_stage", STAGE_CUSTOMS)

    scene = target
    scene.blit(_decor.void_surface(), (0, 0))

    _decor.draw_ground(scene, cam_x, cam_y, stage)
    _combat.draw_ground(scene, cam_x, cam_y)
    _draw_beacon(scene, cam_x, cam_y)
    _draw_world_effects(scene, cam_x, cam_y)
    _scene_drawables(scene, cam_x, cam_y)
    _combat.draw_smoke(scene, cam_x, cam_y)
    _draw_muzzle_flash(scene, cam_x, cam_y)
    draw_bullets(scene, getattr(STATE, "bullets", []), cam_x, cam_y, with_glow=True)

    _decor.draw_over(scene, cam_x, cam_y, stage)
    _stealth.draw_cones(scene, cam_x, cam_y)
    _draw_emissives(scene, cam_x, cam_y, stage)

    if STATE.player_dead:
        from entities import death_anim
        death_anim.draw_death_overlay(scene, cam_x, cam_y)

    draw_vignette(scene)
    draw_scanlines(scene)
    _draw_hud(target, cam_x, cam_y)
    _draw_prompt(target)
    if STATE.player and not getattr(STATE, "m6_train_active", False):
        draw_combat_reticle(target)
