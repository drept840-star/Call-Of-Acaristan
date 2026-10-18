"""Mission 6 gameplay renderer.

The three maps share one painter: baked ground/props from ``decor``, Guards
and Volkov as upright cast figures, floodlight cones over the finished world,
then the same HUD grammar as M4/M5.  The train hands the whole frame to
``train3d`` while it is active.
"""
import math

import pygame

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
from engine.ui import weapon_panel as _hud_weapon_panel
from ui.hud import THEME, draw_combat_reticle, draw_objective_panel, draw_pinned_radio

from . import decor as _decor
from . import flow as _flow
from . import maps as _maps
from . import stealth as _stealth
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

# Guard troopers: Presidential Guard black + red armband (the ``ucilev`` cast
# body), varied by skin/build so a squad does not read as clones.  The black
# beret + cockade are painted over the kit's head.
_GUARD_LOOKS = (
    {},
    {"skin": (196, 158, 128), "bulk": 1.02, "height": 254},
    {"skin": (162, 124, 98), "bulk": 1.07, "height": 260, "hair": (26, 22, 20)},
    {"skin": (206, 170, 140), "bulk": 0.97, "height": 250, "stubble": False},
)


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


def _guard_pose(enemy):
    idx = int(getattr(enemy, "uid", 0)) % len(_GUARD_LOOKS)
    right = math.cos(getattr(enemy, "angle", 0.0)) >= 0
    key = ("m6guard_v1", idx, bool(right))
    return artpack.pose(key, _POSE,
                        lambda s: s.blit(_kit_body("ucilev", _GUARD_LOOKS[idx], right),
                                         (0, 0)))


def _draw_guard(surface, enemy, cam_x, cam_y):
    x = int(enemy.rect.centerx - cam_x)
    y = int(enemy.rect.centery - cam_y)
    if not (-60 < x < WIDTH + 60 and -60 < y < HEIGHT + 60):
        return
    left = _world.entering(enemy)
    if left > 0.0:
        # Walk-in beat: he fades up out of the dark as he steps in, with the
        # snow his boots are throwing up behind him.  No alert pip yet - he
        # is not hunting until he is planted.
        total = float(getattr(enemy, "m6_entry_total", 1.0) or 1.0)
        k = 1.0 - max(0.0, min(1.0, left / total))
        img = _guard_pose(enemy).copy()
        img.set_alpha(int(70 + 185 * k))
        surface.blit(img, (x - _ANCHOR[0], y - _ANCHOR[1]))
        if k < 0.9:
            _entry_puff(surface, x, y, k, getattr(enemy, "uid", 0))
        return
    surface.blit(_guard_pose(enemy), (x - _ANCHOR[0], y - _ANCHOR[1]))
    if getattr(enemy, "alerted", False):
        t = _now_ms() / 1000.0
        a = 0.5 + 0.5 * math.sin(t * 7.0)
        pygame.draw.circle(surface, (214, 90, 66),
                           (x, y - 46), 2, max(1, int(1 + a)))


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


def _scene_drawables(surface, cam_x, cam_y):
    """Static props + actors in one y-sorted list (tall props hide feet)."""
    stage = getattr(STATE, "mission6_stage", STAGE_CUSTOMS)
    out = _decor.tall_drawables(stage, cam_x, cam_y)

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
    t = _now_ms() / 1000.0
    r = 13 + int(4 * (0.5 + 0.5 * math.sin(t * 3.2)))
    pygame.draw.circle(surface, (216, 182, 78), (x, y), r, 2)
    pygame.draw.circle(surface, (246, 222, 140), (x, y), 2)


def _draw_pickup(surface, pu, cam_x, cam_y):
    x, y = int(pu[0] - cam_x), int(pu[1] - cam_y)
    if not (-40 < x < WIDTH + 40 and -40 < y < HEIGHT + 40):
        return
    kind = pu[2] if len(pu) > 2 else "bandage"
    if kind == "bandage":
        pygame.draw.rect(surface, (222, 226, 224), (x - 9, y - 7, 18, 14),
                         border_radius=3)
        pygame.draw.rect(surface, (200, 70, 70), (x - 2, y - 6, 4, 12))
        pygame.draw.rect(surface, (200, 70, 70), (x - 6, y - 2, 12, 4))
        return
    body = pygame.Rect(x - 6, y - 12, 12, 24)
    pygame.draw.rect(surface, (34, 40, 42), body, border_radius=2)
    pygame.draw.rect(surface, (96, 120, 116), body, 1, border_radius=2)
    for ri in range(4):
        pygame.draw.circle(surface, (210, 178, 70), (x, body.y + 4 + ri * 5), 2)


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
def _draw_mag_icon(surface, mx, my, kind, rounds, capacity, active):
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


def _draw_hud(surface, cam_x, cam_y):
    draw_objective_panel(surface, _maps._objective)
    draw_pinned_radio(surface)
    if STATE.player:
        _hud_health_bar.draw(surface, THEME, STATE.player.hp, STATE.player.max_hp,
                             panel_bg=get_panel_bg)
        _hud_weapon_panel.draw(
            surface, THEME, _hud_weapon_panel.WeaponInfo.from_state(STATE),
            panel_bg=get_panel_bg, mag_icon=_draw_mag_icon)
        _hud_hostiles.draw(surface, THEME, _world.living_guards())
        if STATE.show_minimap and STATE.minimap:
            STATE.minimap.draw(surface, STATE.player,
                               [e for e in STATE.enemies if e.hp > 0],
                               cam_x, cam_y,
                               notebook_pos=_objective_world_pos())
        _stealth.draw_hud(surface)


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


def game_draw(fcx=0, fcy=0, surface=None):
    target = surface or screen
    if target is None:
        target = pygame.display.get_surface()
    if target is None:
        return

    if ((getattr(STATE, "m6_train_active", False)
         or getattr(STATE, "m6_train_death", False))
            and _draw_train(target)):
        return

    cam_x, cam_y = int(fcx), int(fcy)
    stage = getattr(STATE, "mission6_stage", STAGE_CUSTOMS)
    target.fill(C_BG_GAME)

    _decor.draw_ground(target, cam_x, cam_y, stage)
    _draw_beacon(target, cam_x, cam_y)
    _draw_world_effects(target, cam_x, cam_y)
    _scene_drawables(target, cam_x, cam_y)
    _draw_muzzle_flash(target, cam_x, cam_y)
    draw_bullets(target, getattr(STATE, "bullets", []), cam_x, cam_y, with_glow=True)

    _decor.draw_over(target, cam_x, cam_y, stage)
    _stealth.draw_cones(target, cam_x, cam_y)

    if STATE.player_dead:
        from entities import death_anim
        death_anim.draw_death_overlay(target, cam_x, cam_y)

    draw_vignette(target)
    draw_scanlines(target)
    _draw_hud(target, cam_x, cam_y)
    _draw_prompt(target)
    if STATE.player and not getattr(STATE, "m6_train_active", False):
        draw_combat_reticle(target)
