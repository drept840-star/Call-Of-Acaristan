
"""Split from mission3.py - see mission3.py (shim) for the map."""
"""Mission 3: The Vostral - dialogue-driven cold open into action.

This is the third campaign mission, picking up 3 days after Mission 2's
Route 12 frame-up. Biribel wakes in an IPA black-site cell (the
"Stabilization Center") facing Prime Minister Balaceanu's long-promised
vendetta. The mission's spine is the Vostral - the buried rumor that
Balaceanu's decorated military career is fabricated. The only copy of
the service record that can prove it is held in the regime's own
Archives, so the engine of the mission is: break out of the cell, reach
the Archives, steal the file, and get it onto a live state broadcast
before Balaceanu finishes his 22:00 address pinning Route 12 on Biribel
personally.

Story posture (per the project bible): KRAP is STILL an organization -
disavowed, under siege, fighting for its survival and credibility. So
this is not Vasile-as-lone-wolf feeding floor plans out of guilt; KRAP
mobilizes as a resistance. Vasile brings real assets (an off-book
extraction element, a stolen IPA comms relay). The trust tension is
organizational, not personal.

This module keeps the existing game integration intact:
    - game_core.start_mission3()
    - game_core.game_update()/game_draw() routing (MISSION3 is checked
      BEFORE MISSION2 - see game_core.game_update)
    - acaristan.py Mission 3 intro and ending cutscenes (shot-lists
      exposed as module-level names below)
    - save as MISSION_3
    - dev command: python acaristan.py --dev-mission3

Scaffolding note: acaristan.py already routes ALL Mission 3 input
through mission3.handle_event(event) (arrow keys to pick choices,
ENTER to confirm) - this was purpose-built for the dialogue-driven
interrogation cold open that is Phase 1. Action phases (STAGE_BREAKOUT
onward) later relax that gate in acaristan.py so normal mouse-shoot
input falls through.
"""

import math
import random
from engine.core import LEGACY_RNG as _rng_legacy  # RPE6 R6: named 'legacy' rng stream
import time

import pygame
from engine.assets import load_image as _load_image  # RPE6 D5: raw loads via engine.assets

import os
from core.config import (C_PLAYER_SKIN, C_PLAYER_UNIFORM, HEIGHT, LETTER_H, MUZZLE_FLASH, Particle, SCENE_TOP, TILE_SIZE, WIDTH, draw_scanlines, draw_vignette, font_dialogue, font_location, font_location_sub, font_prompt, font_speaker, font_terminal, font_terminal_small, screen)
from entities.art_cache import get_blood_decal, get_fullscreen_overlay, get_panel_bg, get_glow
from entities.sprite_lib import get_sprite
from core import artpack, lighting, staticlayer
from core import render_util
from core import props as _props
from core.state import STATE
from game.art import m3 as _m3art  # RPE6 Phase 3: baked world layers (mission-owned pack)
from entities.player import Player, resolve_melee
from entities.enemy_ai import Enemy, enemy_hear_shot, _astar
from entities import corpse
from ui.hud import MiniMap, draw_combat_reticle, draw_objective_panel, draw_pinned_radio
from missions.m1 import _draw_molotov_icon
from fx import effects
import cutscenes
from cutscenes import m3cell as _m3cell  # RPE6 A-003: M3-owned take module, imported directly
from core.camera import update_camera, reset_camera_state, draw_bullets, collide_bullet_walls
from core.hands import open_hand_dorsal
from entities.weapons import _wall_blocks_line
from core import config as _config
from engine.core import now_ms as _now_ms, now_s as _now_s  # RPE6 B-001 timebase
audio = _config.audio

from missions.m3 import maps as _m3_maps  # _m3_maps.MISSION3_MAP/_m3_maps._last_keys owner
from missions.m3 import flow as _m3_flow  # dialogue/monitor/volkov-breach state owner
from missions.m3.meta import C_BALACEANU, C_BIRIBEL, C_PROMPT, C_SYSTEM, C_VOLKOV, MAP_W, MAP_H, STAGE_ARCHIVES, STAGE_ARCHIVES_TRANSITION, STAGE_BREAKOUT, STAGE_BROADCAST, STAGE_BROADCAST_TRANSITION, STAGE_COMMS, STAGE_DONE, STAGE_INTERROGATION, STAGE_KILL_ORDER, STAGE_KO_TRANSITION, STAGE_VENT_CUTSCENE, _DOOR_TILE_COL, _DOOR_TILE_ROW, _MONITOR_TILE_COL, _MONITOR_TILE_ROW
from missions.m3.flow import _archives_exit_pos, _draw_archives_nav_arrow, _m3_exit_requirements, _maru_terminal_pos, _vostral_file_pos
from missions.m3.world import _exfil_pos, _ARCHIVES_EXIT_COL, _ARCHIVES_EXIT_ROW, _EXIT_TILE_COL, _EXIT_TILE_ROW, _K9_STAND_COL, _K9_STAND_ROW, _MARU_TERMINAL_COL, _MARU_TERMINAL_ROW, _RELAY_TILE_COL, _RELAY_TILE_ROW, _VENT_EXIT_COL, _VENT_EXIT_ROW, _VENT_GRATE_COL, _VENT_GRATE_ROW, _VOSTRAL_FILE_COL, _VOSTRAL_FILE_ROW, _draw_m3_alarm_effect, _draw_m3_detainees, _draw_volkov_mags, _interrogation_chair_pos, _movement_locked, _near, _radio, _set_objective, _solid_walls, _volkov_world_pose, _bcast_uplink_pos, _bcast_pc_pos
from missions.m3.interrog import _ACTION_CAPTIONS, _action_is_unskippable, _current_beat, _line_fully_typed
from missions.m3 import sweep as _ko_sweep
from missions.m3.systems import _DRAIN_TILE_COL, _DRAIN_TILE_ROW, _TILE_BASE, _draw_black_ledger_death_overlay, _draw_black_ledger_inmate, _draw_crafting_overlay, _draw_m3_door_tile, _m3_door_tile_state, _paint_m3_door_tile, _draw_mission3_hand_weapon, _draw_mission3_hud, _draw_security_camera, _draw_volkov_ally, _mission3_melee_progress
import game.world as _gw  # RPE6 Phase 5 (D4): mission data lives in components
from engine.world import Label as _Label
from missions.m3.components import M3Door as _M3Door, M3Guard as _M3Guard


def _m3d(door):
    """Declared M3 data of a door (replaces the ad hoc ``door.m3_*`` attributes)."""
    return _gw.ensure(door, _M3Door)



def _m3g(e):
    """Declared M3 data of an enemy (replaces the ad hoc ``e.m3_*`` attributes)."""
    return _gw.ensure(e, _M3Guard)


def _m3l(e):
    """Shared ``Label`` component of an enemy: ``kind`` = enemy type, ``text`` = spawn label."""
    return _gw.ensure(e, _Label)




def _render_cell_bg(target, cam_x, cam_y):
    """Render the Mission 3 tilemap cell background (floor + walls + the
    pulsing objective beacon) onto `target` for the given camera offset.

    Factored out of game_draw so the chair-break cutscene can render the
    REAL cell (not an invented backdrop) to an offscreen buffer and pass
    it to the cutscenes._draw_cb_* shots as `cell_surf` - making every
    shot recognizably the same cell at a different focal length.
    """
    mw, mh = _m3_maps._live_map_dims()
    start_col = max(0, int(cam_x // TILE_SIZE) - 1)
    end_col = min(mw, int((cam_x + WIDTH) // TILE_SIZE) + 2)
    start_row = max(0, int(cam_y // TILE_SIZE) - 1)
    end_row = min(mh, int((cam_y + HEIGHT) // TILE_SIZE) + 2)

    for row in range(start_row, end_row):
        map_row = _m3_maps.MISSION3_MAP[row]
        for col in range(start_col, end_col):
            tile = map_row[col]
            x = col * TILE_SIZE - cam_x
            y = row * TILE_SIZE - cam_y

            if tile == "D":
                pygame.draw.rect(target, _TILE_BASE["."], (x, y, TILE_SIZE, TILE_SIZE))
                pygame.draw.rect(target, (25, 26, 26), (x, y, TILE_SIZE, TILE_SIZE), 1)
                continue

            base = _TILE_BASE.get(tile, (46, 46, 48))
            spr = (artpack.wall(tile, col, row) if tile in "CBS"
                   else artpack.tile(tile, col, row))
            if spr is not None:
                target.blit(spr, (x, y))
                continue
            pygame.draw.rect(target, base, (x, y, TILE_SIZE, TILE_SIZE))
            if tile == "C":
                pygame.draw.rect(target, (38, 38, 36),
                                 (x, y, TILE_SIZE, TILE_SIZE), 1)
            elif tile == "X":
                if staticlayer.baking():
                    continue
                pulse = 0.5 + 0.5 * math.sin(_now_s() * 3.0)
                glow = pygame.Surface((TILE_SIZE, TILE_SIZE), pygame.SRCALPHA)
                pygame.draw.rect(
                    glow,
                    (int(60 + 80 * pulse), 120, 90, int(60 + 50 * pulse)),
                    (0, 0, TILE_SIZE, TILE_SIZE),
                )
                target.blit(glow, (x, y))
            elif tile == "S":
                # Security glass - frosted cyan tint + faint diagonal hatch.
                hatch = pygame.Surface((TILE_SIZE, TILE_SIZE), pygame.SRCALPHA)
                hatch.fill((60, 90, 100, 60))
                for off in range(-TILE_SIZE, TILE_SIZE, 8):
                    pygame.draw.line(hatch, (90, 130, 140, 90),
                                     (off, 0),
                                     (off + TILE_SIZE, TILE_SIZE), 1)
                target.blit(hatch, (x, y))
            elif tile == "K":
                is_light = (col + row) % 2 == 0
                base = (60, 62, 66) if is_light else (45, 48, 52)
                pygame.draw.rect(target, base, (x, y, TILE_SIZE, TILE_SIZE))
                pygame.draw.rect(target, (35, 38, 42), (x, y, TILE_SIZE, TILE_SIZE), 1)
            elif tile == "L":
                base = (36, 46, 48) if (col + row) % 2 == 0 else (30, 39, 42)
                pygame.draw.rect(target, base, (x, y, TILE_SIZE, TILE_SIZE))
                pygame.draw.rect(target, (23, 29, 31), (x, y, TILE_SIZE, TILE_SIZE), 1)
            elif tile == "Y":
                base = (48, 48, 44) if (col + row) % 2 == 0 else (42, 42, 39)
                pygame.draw.rect(target, base, (x, y, TILE_SIZE, TILE_SIZE))
                pygame.draw.rect(target, (34, 34, 31), (x, y, TILE_SIZE, TILE_SIZE), 1)
            elif tile == "M":
                base = (34, 36, 34) if (col + row) % 2 == 0 else (27, 31, 30)
                pygame.draw.rect(target, base, (x, y, TILE_SIZE, TILE_SIZE))
                pygame.draw.rect(target, (20, 24, 23), (x, y, TILE_SIZE, TILE_SIZE), 1)


# Shared screen-culling predicate (promoted to core.render_util; the alias
# keeps the facade re-export and the ~40 call sites below unchanged).
_screen_visible_rect = render_util.screen_visible


# ── static-layer bake + lighting fixtures (graphics rework phases 0/3) ──
_M3_CAM = [0, 0]


def _m3_static_layer():
    sig = (getattr(STATE, "mission3_stage", ""), id(_m3_maps.MISSION3_MAP))
    mw, mh = _m3_maps._live_map_dims()
    return staticlayer.get_layer("m3", sig, mw * TILE_SIZE, mh * TILE_SIZE)


def _with_screen(surf, fn):
    render_util.swap_screen(globals(), surf, fn)


def _bake_m3_static(surf, ox, oy):
    _with_screen(surf, lambda: (
        _render_cell_bg(surf, ox, oy),
        _draw_m3_exterior_ground(ox, oy),
        _draw_m3_background_dressing(ox, oy),
        _draw_m3_corridor_and_map_details(ox, oy),
        # neighbour cells (clipped to their interiors; nothing drawn between the static layer and
        # their original z-slot overlaps them) - tubes / flies are drawn live at that slot
        _draw_neighbor_cells(ox, oy, live=False)))


def _bake_m3_ko(surf, ox, oy):
    _with_screen(surf, lambda: (
        _render_cell_bg(surf, ox, oy),
        _draw_m3_exterior_ground(ox, oy),
        _draw_ko_dressing(ox, oy)))


def _bake_m3_archives(surf, ox, oy):
    _with_screen(surf, lambda: (
        _render_cell_bg(surf, ox, oy),
        _draw_m3_exterior_ground(ox, oy),
        _draw_archives_wing_details(ox, oy),
        _draw_archives_map_polish(ox, oy)))


def _bake_m3_comms(surf, ox, oy):
    _with_screen(surf, lambda: (
        _render_cell_bg(surf, ox, oy),
        _draw_m3_exterior_ground(ox, oy),
        _draw_comms_wing_details(ox, oy),
        _draw_comms_map_polish(ox, oy)))


def _bake_m3_broadcast(surf, ox, oy):
    _with_screen(surf, lambda: (
        _render_cell_bg(surf, ox, oy),
        _draw_m3_exterior_ground(ox, oy),
        _draw_broadcast_wing_details(ox, oy),
        _draw_broadcast_map_polish(ox, oy)))


def _draw_m3_dynamic_tiles(cam_x, cam_y):
    """Per-frame pass for tiles whose look animates (objective beacon)."""
    mw, mh = _m3_maps._live_map_dims()
    start_col = max(0, int(cam_x // TILE_SIZE) - 1)
    end_col = min(mw, int((cam_x + WIDTH) // TILE_SIZE) + 2)
    start_row = max(0, int(cam_y // TILE_SIZE) - 1)
    end_row = min(mh, int((cam_y + HEIGHT) // TILE_SIZE) + 2)
    for row in range(start_row, end_row):
        map_row = _m3_maps.MISSION3_MAP[row]
        for col in range(start_col, end_col):
            if map_row[col] != "X":
                continue
            x = col * TILE_SIZE - cam_x
            y = row * TILE_SIZE - cam_y
            pulse = 0.5 + 0.5 * math.sin(_now_s() * 3.0)
            glow = pygame.Surface((TILE_SIZE, TILE_SIZE), pygame.SRCALPHA)
            pygame.draw.rect(glow, (int(60 + 80 * pulse), 120, 90, int(60 + 50 * pulse)),
                             (0, 0, TILE_SIZE, TILE_SIZE))
            screen.blit(glow, (x, y))


def _m3_wing_name():
    p = STATE.player
    if not p:
        return "corridor"
    tx = p.rect.centerx // TILE_SIZE
    ty = p.rect.centery // TILE_SIZE
    if 4 <= tx <= 21 and 6 <= ty <= 35:
        return "archives"
    if 36 <= tx <= 46 and 30 <= ty <= 44:
        return "comms"
    if 16 <= tx <= 20 and 30 <= ty <= 34:
        return "laundry"
    if 20 <= tx <= 33 and 30 <= ty <= 42:
        return "yard"
    if 34 <= tx <= 46 and 18 <= ty <= 30:
        return "maint"
    if 20 <= tx <= 33 and 18 <= ty <= 29:
        return "cell"
    return "corridor"


_M3_LAMPS = (
    (24, 20, 150, (255, 240, 214), "cell_a"),
    (28, 20, 150, (255, 240, 214), "cell_b"),
    (24, 24, 150, (255, 240, 214), "cell_c"),
    (28, 24, 150, (255, 240, 214), "cell_d"),
    (26, 21, 150, (255, 240, 214), "cell_e"),
    (27, 23, 150, (255, 240, 214), "cell_f"),
    (22, 29, 140, (240, 240, 246), "cor_a"),
    (26, 29, 140, (240, 240, 246), "cor_b"),
    (30, 29, 140, (240, 240, 246), "cor_c"),
    # Atrium fixtures share rows with the authored hard fixture bars
    # (_draw_archives_wing_details) so glow and geometry line up.
    (24, 16, 170, (255, 232, 190), "atr_a"),
    (24, 22, 170, (255, 232, 190), "atr_b"),
    (24, 28, 170, (255, 232, 190), "atr_c"),
    (24, 34, 170, (255, 232, 190), "atr_d"),
    (11, 11, 150, (255, 226, 178), "clerk"),
    (8, 27, 120, (255, 232, 190), "stk_a"),
    (13, 27, 120, (255, 232, 190), "stk_b"),
    (16, 27, 120, (255, 232, 190), "stk_c"),
    (24, 41, 140, (255, 236, 200), "lob_a"),
    (41, 9, 120, (255, 236, 190), "vlt_a"),
    (25, 4, 110, (240, 232, 210), "r22_a"),
    (28, 9, 130, (240, 232, 210), "r20_a"),
    (38, 34, 150, (190, 255, 220), "com_a"),
    (42, 34, 150, (190, 255, 220), "com_b"),
    (40, 38, 150, (190, 255, 220), "com_c"),
    (13, 19, 110, (200, 240, 250), "sec_a"),
    (18, 32, 140, (200, 240, 250), "lnd_a"),
    (24, 34, 150, (236, 240, 236), "yrd_a"),
    (28, 36, 150, (236, 240, 236), "yrd_b"),
    (38, 24, 150, (250, 226, 190), "mnt_a"),
    (42, 26, 150, (250, 226, 190), "mnt_b"),
    (14, 16, 150, (255, 240, 214), "kog_a"),
    (24, 18, 150, (255, 240, 214), "kog_b"),
    (32, 22, 150, (255, 240, 214), "kog_c"),
    (16, 24, 150, (255, 240, 214), "kog_d"),
    (26, 26, 150, (255, 240, 214), "kog_e"),
    (12, 35, 130, (250, 236, 200), "dock_a"),
    (28, 35, 130, (250, 236, 200), "dock_b"),
    (6, 4, 110, (240, 232, 210), "kst_a"),
    (35, 34, 150, (250, 226, 190), "mnt_c"),
    (41, 39, 150, (250, 226, 190), "mnt_d"),
    (6, 23, 110, (200, 240, 250), "air_a"),
    (20, 14, 150, (190, 255, 220), "rel_a"),
    (27, 18, 150, (190, 255, 220), "rel_b"),
    (18, 33, 140, (190, 255, 220), "bat_a"),
    (26, 35, 140, (190, 255, 220), "bat_b"),
    (33, 24, 140, (255, 236, 200), "res_a"),
    (39, 30, 140, (255, 236, 200), "res_b"),
    (25, 4, 110, (240, 232, 210), "kst_b"),
    (38, 18, 140, (190, 255, 220), "cag_a"),
    (41, 25, 140, (190, 255, 220), "cag_b"),
)

# Lamp keys are prefixed by wing family; each family belongs to exactly one
# map.  _M3_LAMPS used to be applied to every map, so comms lamps lit the
# cell-block maintenance bay and cell lamps lit the Archives atrium.
_M3_LAMP_FAMILY_MAP = (
    (("cell", "cor", "lnd", "yrd", "mnt"), "cell"),
    (("atr", "stk", "clerk", "lob", "vlt", "r22", "r20", "res"), "archives"),
    (("com", "sec", "air", "rel", "bat", "cag"), "comms"),
    (("kog", "dock", "kst"), "ko"),
)

_M3_STAGE_MAP_NAME = {
    STAGE_INTERROGATION: "cell", STAGE_BREAKOUT: "cell", STAGE_VENT_CUTSCENE: "cell",
    STAGE_COMMS: "comms",
    STAGE_ARCHIVES: "archives", STAGE_ARCHIVES_TRANSITION: "archives",
    STAGE_KILL_ORDER: "ko", STAGE_KO_TRANSITION: "ko", STAGE_BROADCAST: "ko",
    STAGE_BROADCAST_TRANSITION: "ko",
    STAGE_DONE: "ko",
}


def _m3_lamp_map(key):
    fam = key.split("_")[0]
    for families, map_name in _M3_LAMP_FAMILY_MAP:
        if fam in families:
            return map_name
    return "cell"


def _m3_active_map_name():
    stage = getattr(STATE, "mission3_stage", STAGE_INTERROGATION)
    return _M3_STAGE_MAP_NAME.get(stage, "cell")


def _m3_solid_world(wx, wy):
    """Light-blocking predicate over the tilemap (walls, barriers, doors)."""
    tx = int(wx) // TILE_SIZE
    ty = int(wy) // TILE_SIZE
    mw, mh = _m3_maps._live_map_dims()
    if not (0 <= tx < mw and 0 <= ty < mh):
        return True
    return _m3_maps.MISSION3_MAP[ty][tx] in ("C", "B", "D")


def _m3_doors_sig():
    return int(sum(getattr(d, "anim_progress", 0.0)
                   for d in getattr(STATE, "doors", ())) * 4)


def _push_m3_lights(cam_x, cam_y, t):
    lb = lighting.buffer()
    cast = _m3_solid_world
    cam = (cam_x, cam_y)
    active = _m3_active_map_name()
    # Lamp pools (shared submission loop; world-space view of the tile table
    # with the original tile-based visibility-cache keys preserved).
    render_util.push_lamps(
        lb,
        ((tx * TILE_SIZE, ty * TILE_SIZE, r, col, key)
         for tx, ty, r, col, key in _M3_LAMPS),
        cam_x, cam_y, t, cast,
        key_filter=lambda k: _m3_lamp_map(k) == active,
        key_fn=lambda wx, wy: ("lamp", int(wx // TILE_SIZE), int(wy // TILE_SIZE)))
    # Motivated cones: the archives case spotlight and the chair lamp.
    try:
        if active == "archives":
            vx, vy = _vostral_file_pos()
            sx, sy = vx - cam_x, vy - cam_y
            if _screen_visible_rect(sx, sy, 1, 1):
                lb.cone(sx, sy - 160, math.radians(90), 24, 200,
                        (255, 236, 190), 0.30, caster=cast, cam=cam, key="case")
                lb.light(sx, sy, 110, (255, 230, 180), 0.26,
                         caster=cast, cam=cam, key="casepool")
            mx, my = _maru_terminal_pos()
            sx, sy = mx - cam_x, my - cam_y
            if _screen_visible_rect(sx, sy, 1, 1):
                lb.light(sx, sy, 100, (150, 110, 200), 0.28,
                         caster=cast, cam=cam, key="maru")
    except Exception:
        pass
    try:
        if active == "cell":
            cx, cy = _interrogation_chair_pos()
            sx, sy = cx - cam_x, cy - cam_y
            if _screen_visible_rect(sx, sy, 1, 1):
                lb.cone(sx, sy - 150, math.radians(90), 20, 180,
                        (255, 244, 220), 0.24, caster=cast, cam=cam, key="chair")
    except Exception:
        pass


def _draw_bg_crate_stack(sx, sy, scale=1.0):
    """Pure set-dressing crates/pallets for empty background space."""
    _props.crate_stack(screen, sx, sy, scale)


def _draw_bg_barrels(sx, sy, count=3):
    _props.barrels(screen, sx, sy, count)


def _draw_bg_cable_coil(sx, sy):
    _props.cable_coil(screen, sx, sy)


def _draw_bg_mop_bucket(sx, sy):
    _props.mop_bucket(screen, sx, sy)


def _draw_bg_service_cart(sx, sy):
    _props.service_cart(screen, sx, sy)


def _draw_bg_wall_pipe(x1, y1, x2, y2, color=(54, 56, 52)):
    _props.wall_pipe(screen, x1, y1, x2, y2, color)


# Tiles that read as wall/barrier geometry on the cell-block map.
_BG_SOLID_TILES = ("C", "B", "S", "D")


def _bg_prop_overlaps_solid(kind, tx, ty, arg):
    """True when a background prop's drawn footprint intersects wall tiles.

    Footprint geometry lives in core.props (single owner); the anchor here
    is the tile top-left, matching the draw loop below.  Props failing this
    check are skipped instead of drawn clipped, so a mis-authored anchor
    reads as missing dressing (visible in review) rather than boxes embedded
    in the wall geometry.
    """
    rect = _props.footprint_rect(kind, tx, ty, arg, TILE_SIZE)
    if rect is None:
        return False
    x0, y0 = rect.left, rect.top
    x1, y1 = rect.right, rect.bottom
    mw, mh = _m3_maps._live_map_dims()
    for row in range(int(y0 // TILE_SIZE), int(y1 // TILE_SIZE) + 1):
        for col in range(int(x0 // TILE_SIZE), int(x1 // TILE_SIZE) + 1):
            if not (0 <= row < mh and 0 <= col < mw):
                return True
            if _m3_maps.MISSION3_MAP[row][col] in _BG_SOLID_TILES:
                return True
    return False


def _m3_map_key():
    """Which of the five M3 tilemaps is currently bound to MISSION3_MAP."""
    cur = _m3_maps.MISSION3_MAP
    for key, grid in (
        ("cell", _m3_maps.MISSION3_CELL_MAP),
        ("comms", _m3_maps.MISSION3_COMMS_MAP),
        ("archives", _m3_maps.MISSION3_ARCHIVES_MAP),
        ("killorder", _m3_maps.MISSION3_KILL_ORDER_MAP),
        ("broadcast", _m3_maps.MISSION3_BROADCAST_MAP),
    ):
        if cur is grid:
            return key
    return "cell"


# Per-map background dressing.  The four M3 maps share this draw pass but
# have completely different geometry, so ONE shared anchor list either put
# props inside walls (drawn embedded in the geometry) or got culled by
# _bg_prop_overlaps_solid (invisible dressing).  Anchors below were picked
# per-map on open ground with a full-tile margin from solid tiles; the
# validator stays as the safety net.  Footprints (px, anchor = tile top-left):
# crates ~1.6x1.5t, barrels3 ~1.5x1t, coil ~1.1x1t, mop ~1x1.1t, cart ~1.5x1t.
_M3_DRESSING_PROPS = {
    "cell": (
        ("crates", 3.6, 17.7, 0.82), ("barrels", 42.9, 13.7, 3),
        ("coil", 43.2, 19.8, 1), ("mop", 7.8, 27.0, 1),
        ("cart", 37.5, 27.2, 1), ("crates", 44.2, 26.5, 0.72),
        ("barrels", 4.6, 28.3, 2), ("coil", 28.8, 4.5, 1),
        ("mop", 12.5, 3.8, 1), ("cart", 5.8, 44.0, 1),
        ("crates", 30.2, 28.5, 0.85), ("barrels", 39.5, 44.5, 3),
    ),
    "comms": (
        ("crates", 6.0, 5.0, 0.85), ("barrels", 20.0, 6.5, 3),
        ("coil", 30.0, 3.5, 1), ("mop", 40.0, 7.0, 1),
        ("cart", 12.0, 2.5, 1), ("crates", 28.0, 43.0, 0.72),
        ("barrels", 40.0, 44.5, 2), ("coil", 44.0, 32.0, 1),
        ("mop", 5.0, 33.0, 1), ("cart", 8.0, 44.0, 1),
        ("crates", 36.0, 41.5, 0.85), ("barrels", 4.0, 12.0, 2),
    ),
    "archives": (
        ("crates", 3.0, 4.0, 0.85), ("barrels", 10.0, 2.0, 3),
        ("coil", 17.5, 6.0, 1), ("mop", 32.0, 2.5, 1),
        ("cart", 40.0, 3.0, 1), ("crates", 33.0, 16.0, 0.72),
        ("barrels", 42.0, 16.5, 2), ("coil", 45.0, 40.0, 1),
        ("mop", 34.0, 43.0, 1), ("cart", 12.0, 41.0, 1),
        ("crates", 6.0, 44.0, 0.85), ("barrels", 16.0, 39.5, 3),
    ),
    "killorder": (
        ("crates", 15.0, 3.0, 0.85), ("barrels", 25.0, 5.5, 3),
        ("coil", 33.0, 2.5, 1), ("mop", 42.0, 6.0, 1),
        ("cart", 20.0, 44.0, 1), ("crates", 33.0, 42.0, 0.72),
        ("barrels", 43.0, 44.0, 2), ("coil", 6.0, 40.0, 1),
        ("mop", 10.0, 44.5, 1), ("cart", 40.0, 20.0, 1),
        ("crates", 40.0, 30.0, 0.85), ("barrels", 14.0, 41.0, 3),
    ),
    "broadcast": (
        ("coil", 14.5, 8.0, 1), ("coil", 17.5, 10.0, 1),
        ("cart", 5.0, 8.0, 1), ("barrels", 27.0, 8.0, 3),
        ("crates", 10.0, 20.0, 0.85), ("crates", 22.0, 20.0, 0.72),
        ("coil", 14.5, 12.0, 1), ("mop", 27.0, 22.0, 1),
    ),
}

# Utility pipe runs per map: horizontal runs hug real wall faces (drawn on
# the wall row so they read as mounted conduits) or follow open ground bands
# the same way the cell map's authored north run does.
_M3_PIPE_RUNS = {
    "cell": (
        (4.4, 3.7, 38.5, 3.7),
        (4.5, 18.0, 39.5, 18.0),
        (8.0, 26.2, 36.0, 26.2),
        (1.8, 13.2, 1.8, 24.8),
        (44.0, 12.5, 44.0, 20.8),
    ),
    "comms": (
        (8.0, 6.5, 40.0, 6.5),
        (14.2, 9.7, 29.8, 9.7),
        (30.5, 11.0, 30.5, 21.0),
        (13.2, 29.5, 29.8, 29.5),
    ),
    "archives": (
        (4.2, 18.5, 20.8, 18.5),
        (28.2, 18.5, 36.8, 18.5),
        (2.0, 20.5, 2.0, 36.5),
        (24.0, 45.2, 44.0, 45.2),
    ),
    "killorder": (
        (3.2, 8.5, 35.8, 8.5),
        (2.2, 38.5, 37.8, 38.5),
        (41.5, 9.5, 41.5, 26.5),
    ),
    "broadcast": (
        (14.5, 6.5, 14.5, 14.5),
        (17.5, 6.5, 17.5, 14.5),
        (4.2, 16.5, 27.8, 16.5),
        (4.2, 29.5, 27.8, 29.5),
    ),
}

# Floor vents / access plates per map, on open tiles only.
_M3_VENTS = {
    "cell": ((11.5, 17.7), (33.5, 4.2), (45.0, 17.0), (5.5, 27.0)),
    "comms": ((20.5, 44.5), (40.5, 8.5), (24.5, 24.5), (6.5, 44.5)),
    "archives": ((10.5, 42.5), (40.5, 20.5), (24.5, 40.5), (17.5, 10.5)),
    "killorder": ((20.5, 41.5), (41.5, 12.5), (12.5, 3.5), (44.5, 33.5)),
    "broadcast": ((8.5, 18.5), (23.5, 18.5), (15.5, 27.5), (6.5, 27.5)),
}


# ── exterior ground: world-space dressing ────────────────────────────────
# 'g' is the largest surface in most Mission 3 frames, and tile art can only
# vary on a 64 px grid - at field scale that read as wallpaper (the old
# variant motifs literally repeated every tile).  This pass adds what tiles
# cannot: tone blotches anchored in world space that cross tile borders, a
# contact shadow where open ground meets a wall, and sparse scuffs/aggregate
# chips.  Everything is seeded by world position (never time) so chunk
# bakes, goldens and replays stay deterministic, and it only ever touches
# 'g' tiles - floors, walls and doors are untouched.
_M3_GROUND_BLOBS = {}
_M3_GROUND_AO = {}
# Half of the largest blotch must stay inside the open block that guards it
# (max size 128 -> 64px = exactly one tile), so a blotch can never bleed off
# the ground onto a wall or an interior floor.  That also keeps the block test
# at 3x3, which is what the 3-4 tile wide exterior strips can actually offer.
_GROUND_BLOB_SIZES = (96, 112, 128)
_GROUND_BLOB_CELL = 5          # tiles per blotch slot
_GROUND_BLOB_CHANCE = 0.7      # share of slots that spawn a blotch
_GROUND_BLOB_TRIES = 4         # tile probes per slot (narrow strips still hit)
_GROUND_BLOB_SOLID = 1         # tiles that must be open ground under a blotch
_GROUND_AO_DEPTH = 16          # px of contact shadow against a wall
# Tiles a ground tile is shadowed against; mirrors _BG_SOLID_TILES so the
# contact shadow and the prop-placement safety net agree on what is blocked.
_M3_GROUND_SOLID = ("C", "B", "S", "D")


def _m3_ground_blob(dark, size):
    """Cached soft radial blotch for world-space ground tone."""
    key = (dark, size)
    spr = _M3_GROUND_BLOBS.get(key)
    if spr is None:
        spr = pygame.Surface((size, size), pygame.SRCALPHA)
        cx = cy = size // 2
        # Light blotches are aggregate catching the sky, dark ones are
        # compacted tread.  Both inks are neutral now: the surface used to be
        # warm brown, where a strong dark blotch read as a damp patch - hence
        # the dark peak sitting at little more than a tint (the owner's call
        # on the ground pass: "kill the brown cast and the sprigs/damp
        # patches").  The peaks look high on paper but the bake happens before
        # the lighting/vignette passes, which flatten them to a delta of a
        # few levels out in the dark parts of the field - enough to read as
        # material, never enough to look like a painted-on smear.
        ink = (8, 8, 10) if dark else (236, 238, 244)
        peak = 26 if dark else 34
        for r in range(cx, 0, -1):
            a = int(peak * (1.0 - r / float(cx)) ** 1.7)
            if a <= 0:
                continue
            pygame.draw.circle(spr, (ink[0], ink[1], ink[2], a), (cx, cy), r)
        _M3_GROUND_BLOBS[key] = spr
    return spr


def _m3_ground_ao(edge):
    """Cached contact-shadow band along one ground edge ('n','s','w','e')."""
    spr = _M3_GROUND_AO.get(edge)
    if spr is None:
        depth = _GROUND_AO_DEPTH
        size = (depth, TILE_SIZE) if edge in ("w", "e") else (TILE_SIZE, depth)
        spr = pygame.Surface(size, pygame.SRCALPHA)
        for i in range(depth):
            a = int(76 * (1.0 - i / float(depth)) ** 1.5)
            if a <= 0:
                continue
            if edge == "n":
                pygame.draw.line(spr, (0, 0, 0, a), (0, i), (TILE_SIZE - 1, i))
            elif edge == "s":
                pygame.draw.line(spr, (0, 0, 0, a),
                                 (0, depth - 1 - i), (TILE_SIZE - 1, depth - 1 - i))
            elif edge == "w":
                pygame.draw.line(spr, (0, 0, 0, a), (i, 0), (i, TILE_SIZE - 1))
            else:
                pygame.draw.line(spr, (0, 0, 0, a),
                                 (depth - 1 - i, 0), (depth - 1 - i, TILE_SIZE - 1))
        _M3_GROUND_AO[edge] = spr
    return spr


def _m3_ground_open_block(tc, tr, reach):
    """True when the whole (2*reach+1) tile square is open exterior ground.

    Blotches are skipped otherwise: one that spilled over a wall would read
    as grit sprayed onto a facade, and one that spilled onto an interior
    floor as a stain the mission's own detail passes never clean up.
    """
    mw, mh = _m3_maps._live_map_dims()
    if tc - reach < 0 or tr - reach < 0 or tc + reach >= mw or tr + reach >= mh:
        return False
    grid = _m3_maps.MISSION3_MAP
    for row in range(tr - reach, tr + reach + 1):
        map_row = grid[row]
        for col in range(tc - reach, tc + reach + 1):
            if map_row[col] != "g":
                return False
    return True


def _draw_m3_ground_scuff(x, y, rnd):
    """Faint drag mark. Drawn from a world anchor, so it can cross a tile."""
    ink = (30, 30, 32)
    pygame.draw.line(screen, ink, (x - 14, y), (x + 14, y + rnd.randint(-4, 4)), 1)
    if rnd.random() < 0.5:
        pygame.draw.line(screen, ink, (x - 5, y + 3), (x + 9, y + 5), 1)


def _draw_m3_ground_chips(x, y, rnd):
    """Loose aggregate chips at a world anchor (this was a weed sprig).

    A dim two-blade tuft made sense on dirt, but on neutral grey aggregate an
    organic shape reads as weeds growing out of a paved compound - so the
    second clutter variety on this surface is the material itself: a scatter
    of light and dark chips that keeps the aggregate look continuous.
    """
    for _ in range(rnd.randint(3, 4)):
        cx = x + rnd.randint(-12, 12)
        cy = y + rnd.randint(-9, 9)
        ink = (30, 30, 32) if rnd.random() < 0.35 else (76, 78, 82)
        pygame.draw.rect(screen, ink, (cx, cy, 2, 1))
    if rnd.random() < 0.5:
        pygame.draw.line(screen, (58, 59, 62), (x - 8, y + 6), (x + 7, y + 5), 1)


def _draw_m3_exterior_ground(cam_x, cam_y):
    """World-space dressing for the exterior 'g' ground (all five M3 maps)."""
    mw, mh = _m3_maps._live_map_dims()
    grid = _m3_maps.MISSION3_MAP
    start_col = max(0, int(cam_x // TILE_SIZE) - 1)
    end_col = min(mw, int((cam_x + WIDTH) // TILE_SIZE) + 2)
    start_row = max(0, int(cam_y // TILE_SIZE) - 1)
    end_row = min(mh, int((cam_y + HEIGHT) // TILE_SIZE) + 2)

    # 1. Tone blotches: one seeded slot per _GROUND_BLOB_CELL square, jittered
    #    inside its slot so the slots themselves never read as a lattice.
    cell = _GROUND_BLOB_CELL
    for crow in range(start_row // cell - 1, end_row // cell + 2):
        for ccol in range(start_col // cell - 1, end_col // cell + 2):
            rnd = random.Random(ccol * 2750159 + crow * 76841)
            if rnd.random() > _GROUND_BLOB_CHANCE:
                continue
            # A slot can straddle a wall, and the narrow strips only ever offer
            # their middle row.  Probe a few tiles inside the slot instead of
            # one: the candidates stay uniform over the slot (no lattice) but
            # the strips still get their share of blotches.
            spot = None
            for _ in range(_GROUND_BLOB_TRIES):
                tc = ccol * cell + rnd.randrange(0, cell)
                tr = crow * cell + rnd.randrange(0, cell)
                if _m3_ground_open_block(tc, tr, _GROUND_BLOB_SOLID):
                    # Dark blotches are the minority: they read as compacted
                    # traffic lines, the light ones as aggregate.
                    spot = (tc, tr, rnd.choice(_GROUND_BLOB_SIZES),
                            rnd.random() < 0.30)
                    break
            if spot is None:
                continue
            tc, tr, size, dark = spot
            spr = _m3_ground_blob(dark, size)
            bx = tc * TILE_SIZE + rnd.randrange(0, TILE_SIZE) - cam_x
            by = tr * TILE_SIZE + rnd.randrange(0, TILE_SIZE) - cam_y
            if not _screen_visible_rect(bx - size, by - size, size * 2, size * 2):
                continue
            screen.blit(spr, (bx - size // 2, by - size // 2))

    # 2. Contact shadow where open ground meets a wall (the one cue that makes
    #    a flat field read as ground the buildings actually sit ON).
    ao_n, ao_s = _m3_ground_ao("n"), _m3_ground_ao("s")
    ao_w, ao_e = _m3_ground_ao("w"), _m3_ground_ao("e")
    depth = _GROUND_AO_DEPTH
    for row in range(start_row, end_row):
        map_row = grid[row]
        for col in range(start_col, end_col):
            if map_row[col] != "g":
                continue
            x = col * TILE_SIZE - cam_x
            y = row * TILE_SIZE - cam_y
            if row == 0 or grid[row - 1][col] in _M3_GROUND_SOLID:
                screen.blit(ao_n, (x, y))
            if row == mh - 1 or grid[row + 1][col] in _M3_GROUND_SOLID:
                screen.blit(ao_s, (x, y + TILE_SIZE - depth))
            if col == 0 or map_row[col - 1] in _M3_GROUND_SOLID:
                screen.blit(ao_w, (x, y))
            if col == mw - 1 or map_row[col + 1] in _M3_GROUND_SOLID:
                screen.blit(ao_e, (x + TILE_SIZE - depth, y))

    # 3. Sparse scuffs and aggregate chips - one seeded slot per 2x2 tiles, so
    #    density is per-world-area and never lines up with the tile grid.
    for crow in range(start_row // 2, end_row // 2 + 1):
        for ccol in range(start_col // 2, end_col // 2 + 1):
            rnd = random.Random(ccol * 40503 + crow * 12289)
            tc = ccol * 2 + rnd.randrange(0, 2)
            tr = crow * 2 + rnd.randrange(0, 2)
            if not (0 <= tr < mh and 0 <= tc < mw) or grid[tr][tc] != "g":
                continue
            r = rnd.random()
            if r > 0.22:
                continue
            x = tc * TILE_SIZE + rnd.randrange(6, TILE_SIZE - 6) - cam_x
            y = tr * TILE_SIZE + rnd.randrange(6, TILE_SIZE - 6) - cam_y
            if not _screen_visible_rect(x - 40, y - 40, 80, 80):
                continue
            if r < 0.14:
                _draw_m3_ground_scuff(x, y, rnd)
            else:
                _draw_m3_ground_chips(x, y, rnd)


def _draw_m3_background_dressing(cam_x, cam_y):
    """Dress the big empty negative spaces around the prison block.

    These props are intentionally not lore-heavy: crates, buckets, pipes,
    carts, vents, stains. They exist to make the place feel cared-for and
    hand-authored without changing gameplay collision.

    The open-ground tone/scuff treatment itself lives in
    :func:`_draw_m3_exterior_ground`, which every M3 map shares; this pass
    only adds the authored per-map furniture on top of it.
    """
    mw, mh = _m3_maps._live_map_dims()
    start_col = max(0, int(cam_x // TILE_SIZE) - 1)
    end_col = min(mw, int((cam_x + WIDTH) // TILE_SIZE) + 2)
    start_row = max(0, int(cam_y // TILE_SIZE) - 1)
    end_row = min(mh, int((cam_y + HEIGHT) // TILE_SIZE) + 2)

    # Long utility pipes following exterior walls.
    pipe_runs = _M3_PIPE_RUNS[_m3_map_key()]
    for a, b, c, d in pipe_runs:
        x1, y1 = a * TILE_SIZE - cam_x, b * TILE_SIZE - cam_y
        x2, y2 = c * TILE_SIZE - cam_x, d * TILE_SIZE - cam_y
        if _screen_visible_rect(min(x1, x2), min(y1, y2), abs(x2 - x1) + 8, abs(y2 - y1) + 8):
            _draw_bg_wall_pipe(x1, y1, x2, y2)

    # Hand-placed background props in non-critical space (per-map anchors).
    # _bg_prop_overlaps_solid stays as the safety net: a mis-authored anchor
    # reads as missing dressing rather than boxes embedded in wall geometry.
    props = _M3_DRESSING_PROPS[_m3_map_key()]
    for kind, tx, ty, arg in props:
        sx = tx * TILE_SIZE - cam_x
        sy = ty * TILE_SIZE - cam_y
        if not _screen_visible_rect(sx - 80, sy - 80, 160, 160):
            continue
        # Hide props whose footprint lands on wall/barrier tiles: drawing them
        # there reads as boxes embedded in the wall geometry.
        if _bg_prop_overlaps_solid(kind, tx, ty, arg):
            continue
        if kind == "crates":
            _draw_bg_crate_stack(sx, sy, arg)
        elif kind == "barrels":
            _draw_bg_barrels(sx, sy, int(arg))
        elif kind == "coil":
            _draw_bg_cable_coil(sx, sy)
        elif kind == "mop":
            _draw_bg_mop_bucket(sx, sy)
        elif kind == "cart":
            _draw_bg_service_cart(sx, sy)

    # A couple of wall vents / floor access plates.
    for tx, ty in _M3_VENTS[_m3_map_key()]:
        sx = int(tx * TILE_SIZE - cam_x)
        sy = int(ty * TILE_SIZE - cam_y)
        if not _screen_visible_rect(sx - 20, sy - 20, 50, 40):
            continue
        plate = pygame.Rect(sx - 17, sy - 8, 34, 16)
        pygame.draw.rect(screen, (34, 34, 32), plate, border_radius=2)
        pygame.draw.rect(screen, (78, 78, 70), plate, 1, border_radius=2)
        for off in (-5, 0, 5):
            pygame.draw.line(screen, (52, 52, 48), (plate.x + 4, plate.centery + off), (plate.right - 4, plate.centery + off), 1)



def _draw_m3_corridor_and_map_details(cam_x, cam_y):
    """Environmental detail pass for the prison-block map.

    The raw tilemap made the four-cell corridor read like a flat road. This
    pass adds authored, deterministic top-down details while staying under
    actors/doors so collision readability is unchanged.
    """
    _draw_cell_block_corridor_details(cam_x, cam_y)
    _draw_guard_room_details(cam_x, cam_y)
    _draw_armory_details(cam_x, cam_y)
    _draw_lower_service_wing_details(cam_x, cam_y)
    _draw_lower_wing_wall_readability(cam_x, cam_y)
    _draw_exit_zone_details(cam_x, cam_y)


def _draw_m3_static_live(cam_x, cam_y):
    """Per-frame bits of the cell-block static world (skipped while baking): the corridor cell-door
    LEDs and the maintenance cabinet blink. Drawn right over the static layer."""
    x0 = 6 * TILE_SIZE - cam_x
    y0 = 13 * TILE_SIZE - cam_y
    if not (x0 > WIDTH + 80 or x0 + 34 * TILE_SIZE < -80 or y0 > HEIGHT + 80 or y0 + 4 * TILE_SIZE < -80):
        for idx, base in enumerate((6, 14, 22, 30)):
            door_x = (base + 3) * TILE_SIZE - cam_x
            door_y = 12 * TILE_SIZE - cam_y
            led_on = ((_now_ms() // 700) + idx) % 2 == 0
            pygame.draw.circle(screen, (145 if led_on else 50, 22, 18), (int(door_x + TILE_SIZE * 2 - 10), int(door_y + TILE_SIZE + 12)), 3)
    if _screen_visible_rect(31 * TILE_SIZE - cam_x, 31 * TILE_SIZE - cam_y, 14 * TILE_SIZE, 12 * TILE_SIZE):
        cab = pygame.Rect(int(43.0 * TILE_SIZE - cam_x), int(39.2 * TILE_SIZE - cam_y), 62, 86)
        if (_now_ms() // 500) % 2 == 0:
            pygame.draw.circle(screen, (80, 220, 120), (cab.right - 10, cab.y + 10), 2)


def _draw_cell_block_corridor_details(cam_x, cam_y):
    """Dress the row-13..16 corridor that connects the four cells."""
    x0 = 6 * TILE_SIZE - cam_x
    y0 = 13 * TILE_SIZE - cam_y
    w = 34 * TILE_SIZE
    h = 4 * TILE_SIZE
    if x0 > WIDTH + 80 or x0 + w < -80 or y0 > HEIGHT + 80 or y0 + h < -80:
        return

    old_clip = screen.get_clip()
    screen.set_clip(pygame.Rect(int(x0), int(y0), int(w), int(h)))
    try:
        # Dark institutional floor wash over the plain tile bases.
        wash = pygame.Surface((int(w), int(h)), pygame.SRCALPHA)
        for yy in range(int(h)):
            p = yy / max(1, h)
            col = (5, 6, 6, int(26 + 18 * abs(p - 0.5)))
            pygame.draw.line(wash, col, (0, yy), (int(w), yy))
        screen.blit(wash, (int(x0), int(y0)))

        # Smaller slab seams and expansion joints - the big 64px tile grid alone
        # looked like a placeholder road.
        for gx in range(6 * TILE_SIZE, 40 * TILE_SIZE + 1, 32):
            sx = gx - cam_x
            pygame.draw.line(screen, (24, 25, 25), (sx, y0), (sx, y0 + h), 1)
        for gy in range(13 * TILE_SIZE, 17 * TILE_SIZE + 1, 32):
            sy = gy - cam_y
            pygame.draw.line(screen, (23, 24, 24), (x0, sy), (x0 + w, sy), 1)

        # North/south drainage gutters make it read as a corridor, not a road.
        north = 13 * TILE_SIZE - cam_y + 8
        south = 17 * TILE_SIZE - cam_y - 12
        for yy, alpha in ((north, 70), (south, 82)):
            pygame.draw.rect(screen, (11, 12, 12, alpha), (int(x0), int(yy), int(w), 10))
            pygame.draw.line(screen, (45, 48, 45), (int(x0), int(yy)), (int(x0 + w), int(yy)), 1)
            # Drain grating ticks.
            for gx in range(7 * TILE_SIZE, 39 * TILE_SIZE, 48):
                sx = gx - cam_x
                pygame.draw.line(screen, (38, 40, 38), (sx, yy + 2), (sx + 18, yy + 2), 1)
                pygame.draw.line(screen, (8, 9, 9), (sx, yy + 6), (sx + 18, yy + 6), 1)

        # Worn traffic strip where guards patrol.
        strip_y = 15 * TILE_SIZE - cam_y + 14
        strip = pygame.Surface((int(w), 54), pygame.SRCALPHA)
        render_util.soft_shadow(strip, (-80, 6, int(w) + 160, 38), 42)
        pygame.draw.ellipse(strip, (32, 33, 31, 34), (-40, 12, int(w) + 80, 22))
        screen.blit(strip, (int(x0), int(strip_y - 26)))

        # Cell door thresholds and labels for the four cells.
        cell_names = ["A-01", "A-02", "A-03", "A-04"]
        for idx, base in enumerate((6, 14, 22, 30)):
            door_x = (base + 3) * TILE_SIZE - cam_x
            door_y = 12 * TILE_SIZE - cam_y
            thresh = pygame.Rect(int(door_x), int(door_y + TILE_SIZE - 8), TILE_SIZE * 2, 22)
            pygame.draw.rect(screen, (18, 19, 19), thresh)
            pygame.draw.rect(screen, (66, 62, 50), thresh, 1)
            for off in range(8, TILE_SIZE * 2 - 8, 14):
                pygame.draw.line(screen, (72, 68, 56), (thresh.x + off, thresh.y + 3), (thresh.x + off - 10, thresh.bottom - 3), 1)
            lbl = font_terminal_small.render(cell_names[idx], True, (78, 84, 80))
            screen.blit(lbl, (door_x + TILE_SIZE - lbl.get_width() // 2, door_y + TILE_SIZE + 19))
            # Small red status LEDs next to each cell door (per-frame; see _draw_m3_static_live).
            if not staticlayer.baking():
                led_on = ((_now_ms() // 700) + idx) % 2 == 0
                pygame.draw.circle(screen, (145 if led_on else 50, 22, 18), (int(door_x + TILE_SIZE * 2 - 10), int(door_y + TILE_SIZE + 12)), 3)

        # Overhead fixtures represented by narrow reflections on the floor.
        for i, col in enumerate((10, 16, 22, 28, 34)):
            lx = col * TILE_SIZE + TILE_SIZE // 2 - cam_x
            ly = 14 * TILE_SIZE - cam_y + 18
            pygame.draw.rect(screen, (86, 90, 78), (int(lx - 35), int(ly), 70, 4), border_radius=2)
            refl = pygame.Surface((120, 42), pygame.SRCALPHA)
            pygame.draw.ellipse(refl, (160, 165, 135, 20), (0, 0, 120, 42))
            screen.blit(refl, (int(lx - 60), int(ly + 5)))

        # Directional stencils and hazard striping near the exit side.
        stencil = font_terminal_small.render(_T("m3.cell_block_a_exit"), True, (74, 84, 72))
        stencil.set_alpha(165)
        screen.blit(stencil, (int(28 * TILE_SIZE - cam_x), int(16 * TILE_SIZE - cam_y - 20)))
        for i in range(10):
            sx = int(38 * TILE_SIZE - cam_x + i * 18)
            sy = int(16 * TILE_SIZE - cam_y + 35)
            col = (110, 92, 44) if i % 2 == 0 else (28, 28, 24)
            pygame.draw.polygon(screen, col, [(sx, sy), (sx + 13, sy), (sx + 5, sy + 14), (sx - 8, sy + 14)])

        # Deterministic grime, footprints, and a few spent casings.
        rng = random.Random(13016)
        for _ in range(34):
            px = int(x0 + rng.randint(20, max(21, int(w) - 20)))
            py = int(y0 + rng.randint(24, max(25, int(h) - 24)))
            sw = rng.randint(14, 54)
            sh = rng.randint(4, 16)
            a = rng.randint(12, 34)
            pygame.draw.ellipse(screen, (5, 6, 5, a), (px - sw // 2, py - sh // 2, sw, sh))
        for i in range(26):
            fx = int((9 + (i * 1.05)) * TILE_SIZE - cam_x + rng.randint(-8, 8))
            fy = int(15 * TILE_SIZE - cam_y + 18 + math.sin(i * 0.9) * 18)
            pygame.draw.ellipse(screen, (18, 18, 16), (fx, fy, 7, 3))
            pygame.draw.ellipse(screen, (18, 18, 16), (fx + 8, fy + 5, 7, 3))
        for _ in range(8):
            cx = int((18 + rng.random() * 17) * TILE_SIZE - cam_x)
            cy = int((14.2 + rng.random() * 1.8) * TILE_SIZE - cam_y)
            pygame.draw.line(screen, (125, 98, 46), (cx, cy), (cx + rng.randint(3, 7), cy + rng.randint(-1, 2)), 2)

        # Low cable conduit along the north wall.
        pipe_y = int(13 * TILE_SIZE - cam_y + 24)
        pygame.draw.line(screen, (52, 52, 48), (int(x0 + 26), pipe_y), (int(x0 + w - 26), pipe_y), 3)
        pygame.draw.line(screen, (83, 82, 72), (int(x0 + 26), pipe_y - 1), (int(x0 + w - 26), pipe_y - 1), 1)
        for jx in range(8 * TILE_SIZE, 39 * TILE_SIZE, 256):
            sx = jx - cam_x
            pygame.draw.rect(screen, (30, 30, 28), (int(sx), pipe_y - 5, 10, 10), border_radius=2)
    finally:
        screen.set_clip(old_clip)


def _draw_guard_room_details(cam_x, cam_y):
    """Dress the large guard/control room so it stops reading as an empty box."""
    x0 = 11 * TILE_SIZE - cam_x
    y0 = 18 * TILE_SIZE - cam_y
    w = 21 * TILE_SIZE
    h = 7 * TILE_SIZE
    if x0 > WIDTH + 80 or x0 + w < -80 or y0 > HEIGHT + 80 or y0 + h < -80:
        return

    old_clip = screen.get_clip()
    screen.set_clip(pygame.Rect(int(x0), int(y0), int(w), int(h)))
    try:
        # Fine floor seams.
        for gx in range(11 * TILE_SIZE, 32 * TILE_SIZE, 32):
            sx = gx - cam_x
            pygame.draw.line(screen, (22, 28, 29), (sx, y0 + TILE_SIZE), (sx, y0 + h - TILE_SIZE), 1)
        for gy in range(19 * TILE_SIZE, 24 * TILE_SIZE, 32):
            sy = gy - cam_y
            pygame.draw.line(screen, (22, 28, 29), (x0 + TILE_SIZE, sy), (x0 + w - TILE_SIZE, sy), 1)

        # North wall console bank.
        console_y = int(19 * TILE_SIZE - cam_y + 8)
        for idx, tx in enumerate((13, 17, 21, 25, 29)):
            sx = int(tx * TILE_SIZE - cam_x + 8)
            pygame.draw.rect(screen, (18, 23, 24), (sx, console_y, 44, 24), border_radius=3)
            pygame.draw.rect(screen, (58, 72, 72), (sx, console_y, 44, 24), 1, border_radius=3)
            pygame.draw.rect(screen, (12, 20, 18), (sx + 5, console_y + 5, 22, 10))
            led_col = (75, 210, 130) if idx % 3 else (200, 55, 42)
            pygame.draw.circle(screen, led_col, (sx + 35, console_y + 9), 2)
            pygame.draw.line(screen, (42, 76, 58), (sx + 6, console_y + 18), (sx + 25, console_y + 18), 1)

        # Central briefing table / map. Low visual prop, not heavy cover.
        table_cx = int(23 * TILE_SIZE - cam_x)
        table_cy = int(21.4 * TILE_SIZE - cam_y)
        _soft_table_sh = pygame.Surface((200, 18), pygame.SRCALPHA)
        render_util.soft_shadow(_soft_table_sh, (0, 0, 200, 18), 52)
        screen.blit(_soft_table_sh, (table_cx - 100, table_cy + 24))
        table = pygame.Rect(table_cx - 92, table_cy - 20, 184, 44)
        for yy in range(table.h):
            t = yy / max(1, table.h - 1)
            c = (int(64 - 22 * t), int(62 - 20 * t), int(52 - 16 * t))
            pygame.draw.line(screen, c, (table.x, table.y + yy), (table.right - 1, table.y + yy))
        pygame.draw.rect(screen, (28, 26, 22), table, 1, border_radius=5)
        pygame.draw.line(screen, (110, 98, 76), (table.x + 2, table.y + 1), (table.right - 3, table.y + 1))
        pygame.draw.rect(screen, (32, 42, 38), (table.x + 15, table.y + 8, 70, 26), border_radius=2)
        pygame.draw.line(screen, (92, 130, 92), (table.x + 22, table.y + 20), (table.x + 78, table.y + 14), 1)
        pygame.draw.line(screen, (120, 80, 60), (table.x + 42, table.y + 10), (table.x + 62, table.y + 33), 1)
        for px, py in ((table.x + 106, table.y + 10), (table.x + 124, table.y + 14), (table.x + 145, table.y + 9)):
            pygame.draw.rect(screen, (115, 105, 78), (px, py, 15, 10))
            pygame.draw.line(screen, (62, 54, 38), (px + 2, py + 4), (px + 12, py + 4), 1)

        # Chairs around the table.
        for sx, sy, rot in ((table.x - 16, table.y + 2, 0), (table.right + 2, table.y + 2, 0),
                            (table.centerx - 10, table.y - 25, 1), (table.centerx - 10, table.bottom + 6, 1)):
            render_util.soft_shadow(screen, (sx - 2, sy + 12, 24, 8), 55)
            pygame.draw.rect(screen, (30, 34, 34), (sx, sy, 20, 18), border_radius=3)
            pygame.draw.rect(screen, (68, 72, 68), (sx, sy, 20, 18), 1, border_radius=3)
            if rot:
                pygame.draw.line(screen, (52, 54, 50), (sx + 3, sy + 4), (sx + 17, sy + 4), 1)
            else:
                pygame.draw.line(screen, (52, 54, 50), (sx + 4, sy + 3), (sx + 4, sy + 15), 1)

        # Lockers / weapon rack along south wall.
        rack_y = int(23 * TILE_SIZE - cam_y + 22)
        for tx in (13, 14, 15):
            sx = int(tx * TILE_SIZE - cam_x + 8)
            pygame.draw.rect(screen, (32, 40, 38), (sx, rack_y, 34, 42), border_radius=2)
            pygame.draw.rect(screen, (72, 82, 76), (sx, rack_y, 34, 42), 1, border_radius=2)
            pygame.draw.line(screen, (18, 24, 24), (sx + 17, rack_y + 3), (sx + 17, rack_y + 39), 1)
            pygame.draw.circle(screen, (110, 95, 50), (sx + 13, rack_y + 22), 2)
            pygame.draw.circle(screen, (110, 95, 50), (sx + 21, rack_y + 22), 2)
        wr_x = int(31 * TILE_SIZE - cam_x + 8)
        wr_y = rack_y + 7
        pygame.draw.rect(screen, (24, 24, 22), (wr_x, wr_y, 112, 24), border_radius=2)
        pygame.draw.rect(screen, (82, 76, 62), (wr_x, wr_y, 112, 24), 1, border_radius=2)
        for i in range(4):
            rx = wr_x + 12 + i * 24
            pygame.draw.line(screen, (74, 78, 76), (rx, wr_y + 5), (rx + 14, wr_y + 17), 2)
            pygame.draw.circle(screen, (24, 24, 22), (rx + 14, wr_y + 17), 2)

        # Scattered paperwork/grime.
        rng = random.Random(2318)
        for _ in range(18):
            px = int(x0 + TILE_SIZE + rng.randint(0, int(w - TILE_SIZE * 2)))
            py = int(y0 + TILE_SIZE + rng.randint(0, int(h - TILE_SIZE * 2)))
            if rng.random() < 0.45:
                pygame.draw.rect(screen, (104, 96, 70), (px, py, rng.randint(8, 14), rng.randint(5, 9)))
                pygame.draw.line(screen, (58, 52, 38), (px + 2, py + 3), (px + 8, py + 3), 1)
            else:
                render_util.soft_shadow(screen, (px - 14, py - 5, rng.randint(18, 45), rng.randint(6, 18)), rng.randint(14, 34))
    finally:
        screen.set_clip(old_clip)


def _draw_k9_wall_stand(surface, x, y, acquired=False, scale=1.0):
    """Small top-down wall rack for the K-9 SMG."""
    s = scale
    # Back plate / pegboard.
    pygame.draw.rect(surface, (18, 24, 24), (int(x - 38*s), int(y - 18*s), int(76*s), int(36*s)), border_radius=max(1, int(3*s)))
    pygame.draw.rect(surface, (70, 86, 80), (int(x - 38*s), int(y - 18*s), int(76*s), int(36*s)), 1, border_radius=max(1, int(3*s)))
    for px in range(-28, 33, 14):
        for py in (-8, 6):
            pygame.draw.circle(surface, (36, 48, 44), (int(x + px*s), int(y + py*s)), max(1, int(1*s)))
    # Hooks.
    for hx in (-20, 20):
        pygame.draw.line(surface, (120, 124, 110), (int(x + hx*s), int(y - 3*s)), (int(x + hx*s), int(y + 9*s)), max(1, int(2*s)))
        pygame.draw.arc(surface, (120, 124, 110), (int(x + hx*s - 5*s), int(y + 4*s), int(10*s), int(8*s)), 0, math.pi, max(1, int(1*s)))
    if acquired:
        empty = font_terminal_small.render(_T("m3.empty"), True, (80, 90, 84))
        surface.blit(empty, (int(x - empty.get_width() // 2), int(y - 6*s)))
        return
    # K-9 silhouette on rack: suppressor + receiver + stick mag.
    pygame.draw.line(surface, (22, 26, 26), (int(x - 28*s), int(y - 2*s)), (int(x + 21*s), int(y - 2*s)), max(2, int(5*s)))
    pygame.draw.line(surface, (78, 98, 90), (int(x - 28*s), int(y - 5*s)), (int(x + 12*s), int(y - 5*s)), max(1, int(1*s)))
    pygame.draw.line(surface, (40, 46, 46), (int(x + 18*s), int(y - 2*s)), (int(x + 35*s), int(y - 2*s)), max(2, int(5*s)))
    pygame.draw.line(surface, (100, 116, 108), (int(x + 20*s), int(y - 5*s)), (int(x + 34*s), int(y - 5*s)), max(1, int(1*s)))
    pygame.draw.rect(surface, (18, 20, 20), (int(x - 3*s), int(y + 1*s), int(7*s), int(18*s)), border_radius=max(1, int(2*s)))
    pygame.draw.rect(surface, (82, 90, 86), (int(x - 3*s), int(y + 1*s), int(7*s), int(18*s)), 1, border_radius=max(1, int(2*s)))
    pygame.draw.line(surface, (55, 62, 60), (int(x - 26*s), int(y + 2*s)), (int(x - 40*s), int(y + 7*s)), max(1, int(2*s)))


def _draw_armory_details(cam_x, cam_y):
    """Draw the armory room and the K-9 weapon stand."""
    x0 = 32 * TILE_SIZE - cam_x
    y0 = 18 * TILE_SIZE - cam_y
    w = 13 * TILE_SIZE
    h = 7 * TILE_SIZE
    if x0 > WIDTH + 80 or x0 + w < -80 or y0 > HEIGHT + 80 or y0 + h < -80:
        return

    old_clip = screen.get_clip()
    screen.set_clip(pygame.Rect(int(x0), int(y0), int(w), int(h)))
    try:
        # Floor overlay + fine tile grid.
        # West bay (K-9 side) and east bay (racks), split by the partition at
        # cols 35-36 so the floor overlay never paints over that wall.
        for ix0, iw in ((32, 4), (37, 7)):
            interior = pygame.Rect(int(ix0 * TILE_SIZE - cam_x), int(19 * TILE_SIZE - cam_y), iw * TILE_SIZE, 5 * TILE_SIZE)
            pygame.draw.rect(screen, (28, 35, 35), interior)
            for gx in range(interior.x, interior.right + 1, 16):
                pygame.draw.line(screen, (20, 25, 25), (gx, interior.y), (gx, interior.bottom), 1)
            for gy in range(interior.y, interior.bottom + 1, 16):
                pygame.draw.line(screen, (20, 25, 25), (interior.x, gy), (interior.right, gy), 1)
        pygame.draw.rect(screen, (0, 0, 0, 75), (int(x0), int(y0), int(w), int(h)), 2)

        # North-wall slat racks and empty hooks.
        rack_y = int(19 * TILE_SIZE - cam_y + 8)
        for tx in (37.7, 39.2, 42.6):
            sx = int(tx * TILE_SIZE - cam_x)
            pygame.draw.rect(screen, (20, 25, 25), (sx, rack_y, 70, 30), border_radius=3)
            pygame.draw.rect(screen, (65, 78, 72), (sx, rack_y, 70, 30), 1, border_radius=3)
            for yy in (rack_y + 8, rack_y + 18):
                pygame.draw.line(screen, (44, 54, 50), (sx + 6, yy), (sx + 64, yy), 1)
            for hx in (sx + 16, sx + 36, sx + 56):
                pygame.draw.line(screen, (112, 110, 96), (hx, rack_y + 13), (hx, rack_y + 22), 1)

        # K-9 wall stand.
        stand_x = _K9_STAND_COL * TILE_SIZE + TILE_SIZE // 2 - cam_x
        stand_y = _K9_STAND_ROW * TILE_SIZE + TILE_SIZE // 2 - cam_y
        _draw_k9_wall_stand(screen, stand_x, stand_y, getattr(STATE, "k9_unlocked", False))

        # Ammo cabinets and crates.
        for tx, ty, label in ((38.0, 22.6, "9MM"), (42.2, 22.6, "SMG")):
            sx = int(tx * TILE_SIZE - cam_x)
            sy = int(ty * TILE_SIZE - cam_y)
            pygame.draw.rect(screen, (42, 47, 43), (sx, sy, 54, 42), border_radius=3)
            pygame.draw.rect(screen, (94, 102, 90), (sx, sy, 54, 42), 1, border_radius=3)
            pygame.draw.line(screen, (22, 25, 23), (sx + 27, sy + 4), (sx + 27, sy + 38), 1)
            txt = font_terminal_small.render(label, True, (120, 150, 120))
            screen.blit(txt, (sx + 27 - txt.get_width() // 2, sy + 14))
            pygame.draw.circle(screen, (120, 95, 45), (sx + 22, sy + 30), 2)
            pygame.draw.circle(screen, (120, 95, 45), (sx + 32, sy + 30), 2)

        # Soft green rack light over the weapon wall.
        light = pygame.Surface((210, 95), pygame.SRCALPHA)
        pygame.draw.ellipse(light, (10, 16, 13, 255), light.get_rect())
        screen.blit(light, (int(stand_x - 105), int(stand_y - 58)), special_flags=pygame.BLEND_RGBA_ADD)
    finally:
        screen.set_clip(old_clip)


def _draw_wall_segment(surface, x1, y1, x2, y2, *, vertical=False, accent=(84, 86, 78)):
    """Chunky top-down wall edge used to make room boundaries readable."""
    pygame.draw.line(surface, (5, 5, 5), (int(x1), int(y1)), (int(x2), int(y2)), 10)
    pygame.draw.line(surface, (34, 36, 34), (int(x1), int(y1)), (int(x2), int(y2)), 7)
    if vertical:
        pygame.draw.line(surface, accent, (int(x1) + 2, int(y1)), (int(x2) + 2, int(y2)), 2)
    else:
        pygame.draw.line(surface, accent, (int(x1), int(y1) + 2), (int(x2), int(y2) + 2), 2)


def _draw_wall_jamb(surface, x, y, *, vertical=True, accent=(110, 100, 76)):
    """Short bright door-jamb marker at a doorway gap."""
    if vertical:
        pygame.draw.rect(surface, (10, 10, 9), (int(x) - 4, int(y) - 16, 8, 32))
        pygame.draw.rect(surface, accent, (int(x) - 3, int(y) - 14, 6, 28), 1)
    else:
        pygame.draw.rect(surface, (10, 10, 9), (int(x) - 16, int(y) - 4, 32, 8))
        pygame.draw.rect(surface, accent, (int(x) - 14, int(y) - 3, 28, 6), 1)


def _draw_room_label_plate(text, cx, cy, color):
    """Sized to the label text so names never clip inside a fixed plate."""
    lbl = font_terminal_small.render(text, True, color)
    pad_x, pad_y = 10, 5
    w = max(40, lbl.get_width() + pad_x * 2)
    h = lbl.get_height() + pad_y * 2
    plate = pygame.Surface((w, h), pygame.SRCALPHA)
    pygame.draw.rect(plate, (0, 0, 0, 160), plate.get_rect(), border_radius=3)
    pygame.draw.rect(plate, (*color, 140), plate.get_rect(), 1, border_radius=3)
    plate.blit(lbl, (pad_x, pad_y))
    # The surface we are drawing into decides the bounds - NOT the screen.
    # Inside the static-layer bake this is a 512x512 chunk (see
    # staticlayer.StaticLayer._bake), and _with_screen() has swapped `screen`
    # to it. Rooms are wider than a chunk, so _draw_rect_room_frame() bakes a
    # room into every chunk its footprint overlaps - but the label is anchored
    # at the room CENTRE, which is usually far outside those chunks. Clamping
    # to WIDTH/HEIGHT there would drag the label back on-surface to the chunk's
    # corner and bake it in, duplicating it once per overlapping chunk (and
    # those chunks blit 512px apart, so the copies tile across the map).
    # Clip instead: off-surface means this chunk simply does not own the label.
    sw, sh = screen.get_size()
    x = int(cx - w // 2)
    y = int(cy - h // 2)
    if staticlayer.baking():
        if x + w < 0 or x > sw or y + h < 0 or y > sh:
            return
    else:
        # Live screen: keep plates fully on-screen so edge rooms don't clip.
        x = max(4, min(sw - w - 4, x))
        y = max(4, min(sh - h - 4, y))
    screen.blit(plate, (x, y))


def _frame_solid(tc, tr):
    """True when the tilemap has real wall geometry at tile (tc, tr).

    Room frames are authored as rects, but the tilemap is the collision
    source of truth.  Drawing frame walls over passable tiles produced
    ghost walls the player could walk through (and ghost doorways).
    """
    grid = _m3_maps.MISSION3_MAP
    return (0 <= tr < len(grid) and 0 <= tc < len(grid[tr])
            and grid[tr][tc] in "CBD")


def _draw_rect_room_frame(cam_x, cam_y, col, row, w_tiles, h_tiles, *, gaps_top=(), gaps_bottom=(), gaps_left=(), gaps_right=(), label=None, label_col=(130, 150, 140)):
    x = col * TILE_SIZE - cam_x
    y = row * TILE_SIZE - cam_y
    w = w_tiles * TILE_SIZE
    h = h_tiles * TILE_SIZE
    if not _screen_visible_rect(x, y, w, h, margin=120):
        return

    def _h_run(p0, p1, ypos):
        """Draw a horizontal frame wall run, clipped to solid map tiles."""
        tr = int((ypos + cam_y) // TILE_SIZE)
        tc0 = int((p0 + cam_x) // TILE_SIZE)
        tc1 = int((p1 - 1 + cam_x) // TILE_SIZE)
        run = None
        for tc in range(tc0, tc1 + 1):
            if _frame_solid(tc, tr) and run is None:
                run = tc
            elif not _frame_solid(tc, tr) and run is not None:
                _draw_wall_segment(screen, run * TILE_SIZE - cam_x, ypos,
                                   tc * TILE_SIZE - cam_x, ypos, vertical=False)
                run = None
        if run is not None:
            _draw_wall_segment(screen, run * TILE_SIZE - cam_x, ypos,
                               (tc1 + 1) * TILE_SIZE - cam_x, ypos, vertical=False)

    def _v_run(p0, p1, xpos):
        """Draw a vertical frame wall run, clipped to solid map tiles."""
        tc = int((xpos + cam_x) // TILE_SIZE)
        tr0 = int((p0 + cam_y) // TILE_SIZE)
        tr1 = int((p1 - 1 + cam_y) // TILE_SIZE)
        run = None
        for tr in range(tr0, tr1 + 1):
            if _frame_solid(tc, tr) and run is None:
                run = tr
            elif not _frame_solid(tc, tr) and run is not None:
                _draw_wall_segment(screen, xpos, run * TILE_SIZE - cam_y,
                                   xpos, tr * TILE_SIZE - cam_y, vertical=True)
                run = None
        if run is not None:
            _draw_wall_segment(screen, xpos, run * TILE_SIZE - cam_y,
                               xpos, (tr1 + 1) * TILE_SIZE - cam_y, vertical=True)

    def draw_horizontal(ypos, gaps):
        intervals = []
        for a, b in gaps:
            intervals.append((a * TILE_SIZE - cam_x, (b + 1) * TILE_SIZE - cam_x))
        intervals.sort()
        cur = x
        for a, b in intervals:
            if a > cur:
                _h_run(cur, a, ypos)
            # Door jambs only where the wall line actually exists on either
            # side of the gap (a jamb floating on open floor reads as a
            # doorway into nowhere).
            tr = int((ypos + cam_y) // TILE_SIZE)
            ga = int((a + cam_x) // TILE_SIZE)
            gb = int((b + cam_x) // TILE_SIZE)
            if _frame_solid(ga - 1, tr):
                _draw_wall_jamb(screen, a, ypos, vertical=True)
            if _frame_solid(gb + 1, tr):
                _draw_wall_jamb(screen, b, ypos, vertical=True)
            cur = max(cur, b)
        if cur < x + w:
            _h_run(cur, x + w, ypos)

    def draw_vertical(xpos, gaps):
        intervals = []
        for a, b in gaps:
            intervals.append((a * TILE_SIZE - cam_y, (b + 1) * TILE_SIZE - cam_y))
        intervals.sort()
        cur = y
        for a, b in intervals:
            if a > cur:
                _v_run(cur, a, xpos)
            tc = int((xpos + cam_x) // TILE_SIZE)
            ga = int((a + cam_y) // TILE_SIZE)
            gb = int((b + cam_y) // TILE_SIZE)
            if _frame_solid(tc, ga - 1):
                _draw_wall_jamb(screen, xpos, a, vertical=False)
            if _frame_solid(tc, gb + 1):
                _draw_wall_jamb(screen, xpos, b, vertical=False)
            cur = max(cur, b)
        if cur < y + h:
            _v_run(cur, y + h, xpos)

    draw_horizontal(y, gaps_top)
    draw_horizontal(y + h, gaps_bottom)
    draw_vertical(x, gaps_left)
    draw_vertical(x + w, gaps_right)

    if label:
        _draw_room_label_plate(label, x + w // 2, y + 24, label_col)


def _draw_lower_wing_wall_readability(cam_x, cam_y):
    """Strong wall/door outlines for the lower rooms."""
    _draw_rect_room_frame(
        cam_x, cam_y, 3, 25, 43, 6,
        gaps_top=[(22, 23)],
        gaps_bottom=[(10, 11), (23, 24), (36, 37)],
        label="SERVICE SPINE", label_col=(120, 135, 120),
    )
    _draw_rect_room_frame(
        cam_x, cam_y, 4, 31, 14, 12,
        gaps_top=[(10, 11)],
        label="LAUNDRY", label_col=(120, 170, 180),
    )
    _draw_rect_room_frame(
        cam_x, cam_y, 18, 31, 13, 13,
        gaps_top=[(23, 24)],
        label="REC YARD", label_col=(165, 165, 120),
    )
    _draw_rect_room_frame(
        cam_x, cam_y, 31, 31, 14, 12,
        gaps_top=[(36, 37)],
        label="MAINTENANCE", label_col=(180, 150, 90),
    )



def _draw_lower_service_wing_details(cam_x, cam_y):
    """Dress the optional lower wing: service spine, laundry, yard, maintenance."""
    _draw_lower_service_spine_details(cam_x, cam_y)
    _draw_laundry_room_details(cam_x, cam_y)
    _draw_exercise_yard_details(cam_x, cam_y)
    _draw_maintenance_wing_details(cam_x, cam_y)


def _draw_lower_service_spine_details(cam_x, cam_y):
    x0 = 3 * TILE_SIZE - cam_x
    y0 = 25 * TILE_SIZE - cam_y
    w = 43 * TILE_SIZE
    h = 6 * TILE_SIZE
    if not _screen_visible_rect(x0, y0, w, h):
        return
    old_clip = screen.get_clip()
    screen.set_clip(pygame.Rect(int(x0), int(y0), int(w), int(h)))
    try:
        # Central worn strip and service arrows.
        strip_y = 27 * TILE_SIZE - cam_y + 22
        strip = pygame.Surface((int(w), 66), pygame.SRCALPHA)
        render_util.soft_shadow(strip, (-120, 8, int(w) + 240, 38), 44)
        screen.blit(strip, (int(x0), int(strip_y - 28)))
        pygame.draw.line(screen, (78, 82, 72), (int(x0 + 36), int(y0 + 20)), (int(x0 + w - 36), int(y0 + 20)), 3)
        pygame.draw.line(screen, (34, 36, 32), (int(x0 + 36), int(y0 + 24)), (int(x0 + w - 36), int(y0 + 24)), 1)
        # Direction labels above the three doorways.
        for label, tx, col in (
            ("LAUNDRY", 10.5, (130, 175, 185)),
            ("YARD", 23.5, (160, 170, 135)),
            ("MAINT", 36.5, (175, 155, 105)),
        ):
            sx = int(tx * TILE_SIZE - cam_x)
            sy = int(30 * TILE_SIZE - cam_y - 24)
            pygame.draw.rect(screen, (8, 10, 10, 150), (sx - 44, sy - 6, 88, 20), border_radius=2)
            txt = font_terminal_small.render(label, True, col)
            screen.blit(txt, (sx - txt.get_width() // 2, sy - 2))
            pygame.draw.polygon(screen, col, [(sx, sy + 20), (sx - 7, sy + 11), (sx + 7, sy + 11)])
        # Wall pipes and ceiling light strips.
        for tx in (7, 14, 21, 28, 35, 42):
            lx = int(tx * TILE_SIZE - cam_x)
            ly = int(27 * TILE_SIZE - cam_y + 8)
            pygame.draw.rect(screen, (100, 104, 88), (lx - 34, ly, 68, 4), border_radius=2)
            glow = pygame.Surface((120, 38), pygame.SRCALPHA)
            pygame.draw.ellipse(glow, (150, 150, 120, 18), glow.get_rect())
            screen.blit(glow, (lx - 60, ly + 5))
        # Utility junction boxes on the walls.
        for tx, ty, green in ((5.2, 26.4, True), (18.4, 29.2, False), (32.8, 26.5, True), (43.2, 28.8, False)):
            sx = int(tx * TILE_SIZE - cam_x)
            sy = int(ty * TILE_SIZE - cam_y)
            pygame.draw.rect(screen, (22, 28, 27), (sx - 15, sy - 9, 30, 18), border_radius=2)
            pygame.draw.rect(screen, (62, 70, 64), (sx - 15, sy - 9, 30, 18), 1, border_radius=2)
            pygame.draw.circle(screen, (90, 220, 130) if green else (190, 55, 45), (sx + 9, sy - 1), 2)
        # Floor scuffs.
        rng = random.Random(2751)
        for _ in range(28):
            px = int(x0 + rng.randint(20, max(21, int(w) - 20)))
            py = int(y0 + rng.randint(22, max(23, int(h) - 22)))
            pygame.draw.line(screen, (23, 23, 21), (px, py), (px + rng.randint(-28, 28), py + rng.randint(-8, 12)), 1)
    finally:
        screen.set_clip(old_clip)


def _draw_laundry_room_details(cam_x, cam_y):
    x0 = 4 * TILE_SIZE - cam_x
    y0 = 31 * TILE_SIZE - cam_y
    w = 14 * TILE_SIZE
    h = 12 * TILE_SIZE
    if not _screen_visible_rect(x0, y0, w, h):
        return
    old_clip = screen.get_clip()
    screen.set_clip(pygame.Rect(int(x0), int(y0), int(w), int(h)))
    try:
        # Cohesive room base: a damp blue-grey processing floor that hides the
        # raw 64px tile grid. Big shapes first, detail second.
        pygame.draw.rect(screen, (27, 38, 41), (int(x0), int(y0), int(w), int(h)))
        # Slight wall-to-floor falloff.
        shade = pygame.Surface((int(w), int(h)), pygame.SRCALPHA)
        for yy in range(int(h)):
            p = yy / max(1, h)
            pygame.draw.line(shade, (0, 0, 0, int(18 + 22 * abs(p - 0.45))), (0, yy), (int(w), yy))
        screen.blit(shade, (int(x0), int(y0)))
        # North service wall / tile backsplash.
        pygame.draw.rect(screen, (34, 48, 50), (int(x0 + 12), int(y0 + 18), int(w - 24), 42), border_radius=3)
        pygame.draw.line(screen, (82, 98, 96), (int(x0 + 20), int(y0 + 55)), (int(x0 + w - 20), int(y0 + 55)), 2)
        # Wet tile shine and drains.
        for tx in range(int(x0 + TILE_SIZE), int(x0 + w - TILE_SIZE), 32):
            pygame.draw.line(screen, (26, 34, 36), (tx, int(y0 + TILE_SIZE)), (tx, int(y0 + h - TILE_SIZE)), 1)
        for ty in range(int(y0 + TILE_SIZE), int(y0 + h - TILE_SIZE), 32):
            pygame.draw.line(screen, (26, 34, 36), (int(x0 + TILE_SIZE), ty), (int(x0 + w - TILE_SIZE), ty), 1)
        # Washer/dryer bank on west wall.
        for i in range(5):
            sx = int((5.0 + i * 1.15) * TILE_SIZE - cam_x)
            sy = int(33.0 * TILE_SIZE - cam_y)
            body = pygame.Rect(sx, sy, 44, 42)
            for xx in range(body.w):
                t = xx / max(1, body.w - 1)
                c = int(72 - 26 * abs(t - 0.3) * 2.2)
                pygame.draw.line(screen, (c - 6, c, c), (sx + xx, sy), (sx + xx, sy + 41))
            pygame.draw.rect(screen, (24, 30, 30), body, 1, border_radius=4)
            # door ring + glass + control strip
            pygame.draw.circle(screen, (16, 22, 23), (sx + 22, sy + 24), 13)
            pygame.draw.circle(screen, (96, 118, 118), (sx + 22, sy + 24), 13, 2)
            pygame.draw.circle(screen, (34, 46, 48), (sx + 22, sy + 24), 9)
            pygame.draw.arc(screen, (130, 160, 160), (sx + 13, sy + 15, 18, 18),
                            math.radians(140), math.radians(250), 2)
            pygame.draw.rect(screen, (18, 22, 22), (sx + 6, sy + 4, 32, 6), border_radius=1)
            pygame.draw.circle(screen, (90, 210, 130) if i % 2 else (200, 170, 60),
                               (sx + 34, sy + 7), 2)
            pygame.draw.circle(screen, (120, 128, 126), (sx + 12, sy + 7), 2, 1)
        # Folding tables / uniform racks.
        table = pygame.Rect(int(10.2 * TILE_SIZE - cam_x), int(36.0 * TILE_SIZE - cam_y), 176, 40)
        render_util.soft_shadow(screen, (table.x - 4, table.y + 26, table.w + 8, 16), 60)
        for lx in (table.x + 10, table.right - 14):
            pygame.draw.rect(screen, (40, 38, 32), (lx, table.y + 30, 5, 14))
        for yy in range(table.h):
            t = yy / max(1, table.h - 1)
            c = (int(88 - 26 * t), int(84 - 24 * t), int(70 - 20 * t))
            pygame.draw.line(screen, c, (table.x, table.y + yy), (table.right - 1, table.y + yy))
        pygame.draw.rect(screen, (30, 28, 24), table, 1, border_radius=4)
        pygame.draw.line(screen, (140, 132, 108), (table.x + 2, table.y + 1), (table.right - 3, table.y + 1))
        for px, py, col in ((table.x + 15, table.y + 9, (150, 150, 142)), (table.x + 48, table.y + 14, (70, 90, 110)),
                            (table.x + 88, table.y + 8, (120, 110, 85)), (table.x + 128, table.y + 13, (95, 105, 90))):
            pygame.draw.rect(screen, col, (px, py, 28, 12), border_radius=2)
            pygame.draw.rect(screen, (40, 40, 38), (px, py, 28, 12), 1, border_radius=2)
            pygame.draw.line(screen, (40, 40, 38), (px + 3, py + 6), (px + 25, py + 6), 1)
            pygame.draw.line(screen, tuple(min(255, c + 26) for c in col), (px + 2, py + 1), (px + 26, py + 1), 1)
        # Hanging uniform rail.
        rail_y = int(39.0 * TILE_SIZE - cam_y)
        rail_x1 = int(6.0 * TILE_SIZE - cam_x)
        rail_x2 = int(15.8 * TILE_SIZE - cam_x)
        pygame.draw.line(screen, (90, 94, 88), (rail_x1, rail_y), (rail_x2, rail_y), 3)
        rng = random.Random(3301)
        for i in range(14):
            hx = rail_x1 + 16 + i * 38
            col = rng.choice([(36, 50, 58), (46, 52, 48), (62, 58, 44), (34, 44, 40)])
            pygame.draw.line(screen, (130, 130, 120), (hx, rail_y), (hx - 6, rail_y + 8), 1)
            pygame.draw.rect(screen, col, (hx - 12, rail_y + 8, 24, 28), border_radius=3)
            pygame.draw.rect(screen, (14, 16, 16), (hx - 12, rail_y + 8, 24, 28), 1, border_radius=3)
        # Overhead steam pipe / ductwork ties this room into the service spine.
        pipe_y = int(32.15 * TILE_SIZE - cam_y)
        pygame.draw.line(screen, (46, 50, 48), (int(x0 + 46), pipe_y), (int(x0 + w - 46), pipe_y), 6)
        pygame.draw.line(screen, (106, 112, 104), (int(x0 + 46), pipe_y - 2), (int(x0 + w - 46), pipe_y - 2), 1)
        for valve_x in (6.8, 12.7, 16.0):
            vx = int(valve_x * TILE_SIZE - cam_x)
            pygame.draw.circle(screen, (126, 72, 46), (vx, pipe_y), 8, 2)
            pygame.draw.line(screen, (126, 72, 46), (vx - 6, pipe_y), (vx + 6, pipe_y), 1)
            pygame.draw.line(screen, (126, 72, 46), (vx, pipe_y - 6), (vx, pipe_y + 6), 1)

        # Linen cages / sorting bins along the east wall: readable structure,
        # not just loose props.
        for tx, ty, tag in ((15.2, 37.3, "LINEN"), (15.2, 39.3, "IPA")):
            sx = int(tx * TILE_SIZE - cam_x)
            sy = int(ty * TILE_SIZE - cam_y)
            cage = pygame.Rect(sx - 34, sy - 24, 68, 48)
            pygame.draw.rect(screen, (24, 30, 30), cage, border_radius=3)
            pygame.draw.rect(screen, (78, 88, 84), cage, 2, border_radius=3)
            for gx in range(cage.x + 10, cage.right - 6, 10):
                pygame.draw.line(screen, (48, 56, 54), (gx, cage.y + 4), (gx, cage.bottom - 4), 1)
            for gy in range(cage.y + 12, cage.bottom - 4, 10):
                pygame.draw.line(screen, (48, 56, 54), (cage.x + 4, gy), (cage.right - 4, gy), 1)
            lbl = font_terminal_small.render(tag, True, (120, 150, 145))
            screen.blit(lbl, (cage.centerx - lbl.get_width() // 2, cage.y + 5))
            # Folded cloth silhouettes inside.
            for i in range(3):
                pygame.draw.rect(screen, (88 + i * 12, 94 + i * 10, 92 + i * 8),
                                 (cage.x + 8 + i * 16, cage.bottom - 15 - i * 2, 14, 7), border_radius=1)

        # Wet floor lane with footprints from machine bank to folding table.
        wet = pygame.Surface((int(w), int(h)), pygame.SRCALPHA)
        pygame.draw.ellipse(wet, (10, 22, 24, 42), (int(w * 0.22), int(h * 0.44), int(w * 0.48), 70))
        screen.blit(wet, (int(x0), int(y0)))
        for i in range(18):
            fx = int((6.1 + i * 0.42) * TILE_SIZE - cam_x)
            fy = int((35.0 + math.sin(i * 0.8) * 0.45) * TILE_SIZE - cam_y)
            pygame.draw.ellipse(screen, (14, 22, 22), (fx, fy, 8, 3))
            pygame.draw.ellipse(screen, (14, 22, 22), (fx + 8, fy + 5, 8, 3))

        # Wall signage / floor stencil, purely flavor but anchored to the room.
        sign = font_terminal_small.render(_T("m3.uniform_processing"), True, (95, 135, 140))
        screen.blit(sign, (int(8.0 * TILE_SIZE - cam_x), int(32.55 * TILE_SIZE - cam_y)))
        arrow = font_terminal.render(_T("m3.text"), True, (90, 125, 130))
        arrow.set_alpha(150)
        screen.blit(arrow, (int(13.4 * TILE_SIZE - cam_x), int(32.45 * TILE_SIZE - cam_y)))

        # Laundry carts.
        for tx, ty in ((6.1, 41.0), (15.2, 34.9)):
            sx = int(tx * TILE_SIZE - cam_x)
            sy = int(ty * TILE_SIZE - cam_y)
            render_util.soft_shadow(screen, (sx - 24, sy + 12, 48, 10), 55)
            pygame.draw.rect(screen, (40, 46, 46), (sx - 22, sy - 12, 44, 26), border_radius=4)
            pygame.draw.rect(screen, (92, 100, 96), (sx - 22, sy - 12, 44, 26), 1, border_radius=4)
            # canvas bag slats + rim
            for vx in range(sx - 16, sx + 18, 8):
                pygame.draw.line(screen, (58, 64, 62), (vx, sy - 10), (vx, sy + 12), 1)
            pygame.draw.line(screen, (120, 128, 122), (sx - 21, sy - 11), (sx + 21, sy - 11), 2)
            pygame.draw.line(screen, (74, 84, 82), (sx - 20, sy - 3), (sx + 20, sy - 3), 1)
            # folded linen peeking over the rim
            pygame.draw.rect(screen, (150, 150, 142), (sx - 12, sy - 15, 14, 5), border_radius=1)
            for wx in (-14, 14):
                pygame.draw.circle(screen, (8, 8, 8), (sx + wx, sy + 16), 4)
                pygame.draw.circle(screen, (70, 70, 66), (sx + wx, sy + 16), 1)
        pygame.draw.rect(screen, (0, 0, 0, 70), (x0, y0, w, h), 2)
    finally:
        screen.set_clip(old_clip)


def _draw_exercise_yard_details(cam_x, cam_y):
    x0 = 18 * TILE_SIZE - cam_x
    y0 = 31 * TILE_SIZE - cam_y
    w = 13 * TILE_SIZE
    h = 13 * TILE_SIZE
    if not _screen_visible_rect(x0, y0, w, h):
        return
    old_clip = screen.get_clip()
    screen.set_clip(pygame.Rect(int(x0), int(y0), int(w), int(h)))
    try:
        # Cohesive exercise-yard base. Make the whole room read as one worn
        # concrete rec block instead of raw tile grid plus random props.
        pygame.draw.rect(screen, (42, 43, 39), (int(x0), int(y0), int(w), int(h)))
        # Large, uneven concrete slabs.
        for tx in range(int(x0 + TILE_SIZE), int(x0 + w - TILE_SIZE), 96):
            pygame.draw.line(screen, (34, 35, 32), (tx, int(y0 + 18)), (tx, int(y0 + h - 18)), 2)
        for ty in range(int(y0 + TILE_SIZE), int(y0 + h - TILE_SIZE), 96):
            pygame.draw.line(screen, (34, 35, 32), (int(x0 + 18), ty), (int(x0 + w - 18), ty), 2)
        # Darkened perimeter under the fence/walls.
        edge = pygame.Surface((int(w), int(h)), pygame.SRCALPHA)
        pygame.draw.rect(edge, (0, 0, 0, 80), (0, 0, int(w), 22))
        pygame.draw.rect(edge, (0, 0, 0, 70), (0, int(h) - 24, int(w), 24))
        pygame.draw.rect(edge, (0, 0, 0, 55), (0, 0, 22, int(h)))
        pygame.draw.rect(edge, (0, 0, 0, 55), (int(w) - 22, 0, 22, int(h)))
        screen.blit(edge, (int(x0), int(y0)))
        # Concrete court markings.
        cx = int(x0 + w / 2)
        cy = int(y0 + h / 2)
        pygame.draw.rect(screen, (62, 62, 56), (int(x0 + TILE_SIZE), int(y0 + TILE_SIZE), int(w - TILE_SIZE*2), int(h - TILE_SIZE*2)), 2)
        pygame.draw.line(screen, (70, 70, 62), (cx, int(y0 + TILE_SIZE)), (cx, int(y0 + h - TILE_SIZE)), 1)
        pygame.draw.circle(screen, (70, 70, 62), (cx, cy), 44, 1)
        # Chain-link fence is suggested at the edges only. A full-room diagonal
        # pattern looked very procedural/noisy.
        fence = pygame.Surface((int(w), int(h)), pygame.SRCALPHA)
        for off in range(-80, int(w) + 80, 18):
            pygame.draw.line(fence, (92, 92, 82, 26), (off, 0), (off + 80, 80), 1)
            pygame.draw.line(fence, (92, 92, 82, 18), (off, int(h) - 80), (off + 80, int(h)), 1)
        for off in range(-80, int(h) + 80, 18):
            pygame.draw.line(fence, (92, 92, 82, 20), (0, off), (80, off + 80), 1)
            pygame.draw.line(fence, (92, 92, 82, 20), (int(w) - 80, off), (int(w), off + 80), 1)
        screen.blit(fence, (int(x0), int(y0)))
        # Pull-up bars / benches.
        for tx, ty in ((20.4, 35.8), (27.8, 35.8)):
            sx = int(tx * TILE_SIZE - cam_x)
            sy = int(ty * TILE_SIZE - cam_y)
            pygame.draw.line(screen, (28, 30, 30), (sx - 20, sy + 30), (sx - 20, sy - 28), 4)
            pygame.draw.line(screen, (28, 30, 30), (sx + 20, sy + 30), (sx + 20, sy - 28), 4)
            pygame.draw.line(screen, (90, 92, 86), (sx - 24, sy - 28), (sx + 24, sy - 28), 4)
        for tx, ty in ((21.5, 41.0), (27.1, 41.0)):
            sx = int(tx * TILE_SIZE - cam_x)
            sy = int(ty * TILE_SIZE - cam_y)
            pygame.draw.rect(screen, (44, 42, 36), (sx - 38, sy - 7, 76, 14), border_radius=3)
            pygame.draw.rect(screen, (82, 78, 62), (sx - 38, sy - 7, 76, 14), 1, border_radius=3)
        # Wall-mounted floodlights and caged skylight shadows make it feel like
        # a real rec block instead of a flat concrete rectangle.
        for tx, ty, aim in ((19.2, 32.0, 0.8), (29.2, 32.0, 2.3), (19.2, 42.2, -0.4), (29.2, 42.2, -2.7)):
            sx = int(tx * TILE_SIZE - cam_x)
            sy = int(ty * TILE_SIZE - cam_y)
            pygame.draw.rect(screen, (28, 30, 28), (sx - 10, sy - 6, 20, 12), border_radius=2)
            pygame.draw.circle(screen, (112, 116, 96), (sx, sy), 5)
            # Nested wedges: additive stacking makes the pool brightest at
            # the fixture and fade toward the throw - a single flat polygon
            # read as a paper triangle stuck to the floor.
            cone = pygame.Surface((120, 80))
            cone.fill((0, 0, 0))
            # BLEND_RGBA_ADD ignores source alpha: intensity lives in RGB.
            # Nested wedges accumulate toward the fixture (drawn large->small).
            for cum, sc in (((3, 3, 2), 1.0), ((7, 7, 5), 0.72),
                            ((10, 10, 8), 0.46), ((14, 14, 11), 0.24)):
                pts = [(60, 40 - 36 * sc), (60 - 48 * sc, 40 + 36 * sc),
                       (60 + 48 * sc, 40 + 36 * sc)]
                pygame.draw.polygon(cone, cum, pts)
            pygame.draw.ellipse(cone, (6, 6, 5), (22, 52, 76, 22))
            cone = pygame.transform.rotate(cone, math.degrees(aim))
            screen.blit(cone, (sx - cone.get_width() // 2, sy - cone.get_height() // 2), special_flags=pygame.BLEND_RGBA_ADD)

        # Painted court blocks / exercise lanes.
        lane_col = (78, 78, 68)
        for lx in (21.0, 24.0, 27.0):
            sx = int(lx * TILE_SIZE - cam_x)
            pygame.draw.line(screen, lane_col, (sx, int(33.0 * TILE_SIZE - cam_y)), (sx, int(42.0 * TILE_SIZE - cam_y)), 1)
        for ly in (34.6, 39.3):
            sy = int(ly * TILE_SIZE - cam_y)
            pygame.draw.line(screen, lane_col, (int(19.2 * TILE_SIZE - cam_x), sy), (int(29.2 * TILE_SIZE - cam_x), sy), 1)

        # Basketball hoop / backboard on the north wall: one big readable focal
        # element makes the yard feel authored instead of generic.
        hoop_x = int(24.0 * TILE_SIZE - cam_x)
        hoop_y = int(32.2 * TILE_SIZE - cam_y)
        pygame.draw.rect(screen, (58, 58, 52), (hoop_x - 34, hoop_y - 22, 68, 28), border_radius=2)
        pygame.draw.rect(screen, (118, 118, 96), (hoop_x - 34, hoop_y - 22, 68, 28), 2, border_radius=2)
        pygame.draw.rect(screen, (42, 42, 38), (hoop_x - 15, hoop_y - 13, 30, 16), 1)
        pygame.draw.circle(screen, (140, 80, 50), (hoop_x, hoop_y + 12), 10, 2)
        pygame.draw.line(screen, (110, 100, 78), (hoop_x - 9, hoop_y + 15), (hoop_x - 3, hoop_y + 29), 1)
        pygame.draw.line(screen, (110, 100, 78), (hoop_x + 9, hoop_y + 15), (hoop_x + 3, hoop_y + 29), 1)

        # Heavy bag station + weight rack.
        bag_x = int(24.4 * TILE_SIZE - cam_x)
        bag_y = int(34.2 * TILE_SIZE - cam_y)
        pygame.draw.line(screen, (72, 72, 66), (bag_x, bag_y - 36), (bag_x, bag_y - 8), 3)
        render_util.soft_shadow(screen, (bag_x - 15, bag_y + 21, 30, 10), 70)
        pygame.draw.rect(screen, (66, 48, 34), (bag_x - 11, bag_y - 8, 22, 34), border_radius=9)
        pygame.draw.rect(screen, (118, 86, 54), (bag_x - 11, bag_y - 8, 22, 34), 1, border_radius=9)
        rack = pygame.Rect(int(27.6 * TILE_SIZE - cam_x), int(38.2 * TILE_SIZE - cam_y), 78, 28)
        pygame.draw.rect(screen, (25, 27, 26), rack, border_radius=3)
        pygame.draw.rect(screen, (84, 84, 74), rack, 1, border_radius=3)
        for i in range(4):
            wx = rack.x + 12 + i * 16
            pygame.draw.circle(screen, (64, 64, 58), (wx, rack.centery), 6, 2)
            pygame.draw.line(screen, (116, 112, 92), (wx - 7, rack.centery), (wx + 7, rack.centery), 1)

        # Faint prisoner scrawl / tally target on concrete wall.
        graff = font_terminal_small.render(_T("m3.rec_block_12_min"), True, (72, 72, 62))
        graff.set_alpha(150)
        screen.blit(graff, (int(20.0 * TILE_SIZE - cam_x), int(32.2 * TILE_SIZE - cam_y)))

        # Scuffs / chalk marks.
        rng = random.Random(4414)
        for _ in range(34):
            px = int(x0 + rng.randint(70, int(w - 70)))
            py = int(y0 + rng.randint(70, int(h - 70)))
            if rng.random() < 0.5:
                pygame.draw.line(screen, (34, 34, 31), (px, py), (px + rng.randint(-20, 20), py + rng.randint(-10, 12)), 1)
            else:
                pygame.draw.ellipse(screen, (25, 25, 23), (px - 10, py - 4, rng.randint(12, 34), rng.randint(4, 12)))
        pygame.draw.rect(screen, (0, 0, 0, 70), (x0, y0, w, h), 2)
    finally:
        screen.set_clip(old_clip)


def _draw_maintenance_wing_details(cam_x, cam_y):
    x0 = 31 * TILE_SIZE - cam_x
    y0 = 31 * TILE_SIZE - cam_y
    w = 14 * TILE_SIZE
    h = 12 * TILE_SIZE
    if not _screen_visible_rect(x0, y0, w, h):
        return
    old_clip = screen.get_clip()
    screen.set_clip(pygame.Rect(int(x0), int(y0), int(w), int(h)))
    try:
        # Cohesive maintenance base: dark green utility floor with broad shadow
        # bands, so the machinery sits inside a room rather than on raw tiles.
        pygame.draw.rect(screen, (25, 31, 29), (int(x0), int(y0), int(w), int(h)))
        floor_shadow = pygame.Surface((int(w), int(h)), pygame.SRCALPHA)
        for yy in range(int(h)):
            p = yy / max(1, h)
            pygame.draw.line(floor_shadow, (0, 0, 0, int(20 + 28 * abs(p - 0.35))), (0, yy), (int(w), yy))
        screen.blit(floor_shadow, (int(x0), int(y0)))
        # Catwalk stripe / floor grates.
        for gx in range(int(x0 + TILE_SIZE), int(x0 + w - TILE_SIZE), 24):
            pygame.draw.line(screen, (18, 24, 22), (gx, int(y0 + TILE_SIZE)), (gx, int(y0 + h - TILE_SIZE)), 1)
        for gy in range(int(y0 + TILE_SIZE), int(y0 + h - TILE_SIZE), 24):
            pygame.draw.line(screen, (18, 24, 22), (int(x0 + TILE_SIZE), gy), (int(x0 + w - TILE_SIZE), gy), 1)
        # Boilers / tanks: shaded cylinders with dome caps, weld seams,
        # gauges and a pipe stub up to the north manifold.
        for tx, ty, tall in ((34.0, 35.0, True), (42.0, 35.4, False)):
            sx = int(tx * TILE_SIZE - cam_x)
            sy = int(ty * TILE_SIZE - cam_y)
            tw, th = (56, 118) if tall else (66, 76)
            bx, by = sx - tw // 2, sy - th // 2
            render_util.soft_shadow(screen, (bx - 6, by + th - 9, tw + 12, 18), 75)
            # pipe stub to the manifold
            pygame.draw.line(screen, (58, 60, 54), (sx, by - 14), (sx, by + 6), 5)
            pygame.draw.line(screen, (96, 98, 88), (sx - 1, by - 14), (sx - 1, by + 6), 1)
            # body: horizontal shade gradient (light from the left)
            for i in range(tw):
                t = i / max(1, tw - 1)
                c = int(74 - 34 * abs(t - 0.32) * 2.1)
                col = (c + 6, c + 12, c + 8)
                pygame.draw.line(screen, col, (bx + i, by + 6), (bx + i, by + th - 2))
            body = pygame.Rect(bx, by + 4, tw, th - 4)
            pygame.draw.rect(screen, (24, 28, 26), body, 2, border_radius=8)
            # dome cap + base ring
            pygame.draw.ellipse(screen, (86, 94, 86), (bx, by - 4, tw, 16))
            pygame.draw.ellipse(screen, (24, 28, 26), (bx, by - 4, tw, 16), 2)
            pygame.draw.arc(screen, (128, 134, 122), (bx + 2, by - 3, tw - 4, 14),
                            math.radians(150), math.radians(260), 2)
            pygame.draw.ellipse(screen, (40, 46, 42), (bx - 2, by + th - 8, tw + 4, 10))
            pygame.draw.ellipse(screen, (22, 26, 24), (bx - 2, by + th - 8, tw + 4, 10), 2)
            # weld seams with lit lip + rivets
            for fy in (0.34, 0.66):
                yy = by + int(th * fy)
                pygame.draw.line(screen, (30, 34, 32), (bx + 2, yy), (bx + tw - 3, yy), 2)
                pygame.draw.line(screen, (96, 104, 96), (bx + 2, yy + 2), (bx + tw - 3, yy + 2), 1)
                for rx in range(bx + 6, bx + tw - 4, 9):
                    pygame.draw.circle(screen, (110, 116, 106), (rx, yy + 1), 1)
            # gauge dial + valve wheel
            gx, gy = bx + tw - 16, by + 20
            pygame.draw.circle(screen, (26, 30, 28), (gx, gy), 7)
            pygame.draw.circle(screen, (150, 158, 146), (gx, gy), 7, 1)
            pygame.draw.line(screen, (200, 90, 60), (gx, gy), (gx + 4, gy - 3), 1)
            pygame.draw.circle(screen, (120, 55, 40), (bx + 12, by + 24), 5, 2)
            pygame.draw.circle(screen, (60, 26, 18), (bx + 12, by + 24), 1)
        # Generator / control desk.
        gen = pygame.Rect(int(37.3 * TILE_SIZE - cam_x), int(38.1 * TILE_SIZE - cam_y), 128, 58)
        render_util.soft_shadow(screen, (gen.x - 8, gen.y + 38, gen.w + 16, 22), 80)
        pygame.draw.rect(screen, (38, 42, 38), gen, border_radius=6)
        pygame.draw.rect(screen, (90, 96, 82), gen, 2, border_radius=6)
        for i in range(5):
            pygame.draw.rect(screen, (22, 26, 24), (gen.x + 12 + i * 21, gen.y + 14, 12, 30), border_radius=2)
        pygame.draw.circle(screen, (90, 220, 120), (gen.right - 16, gen.y + 14), 3)
        # Pipe manifold and valve wheels - routed along the NORTH wall, not
        # across the open bay floor.
        pipe_y = int(31.4 * TILE_SIZE - cam_y)
        pygame.draw.line(screen, (68, 70, 62), (int(x0 + 50), pipe_y), (int(x0 + w - 50), pipe_y), 6)
        pygame.draw.line(screen, (110, 110, 92), (int(x0 + 50), pipe_y - 2), (int(x0 + w - 50), pipe_y - 2), 1)
        for tx in (35.5, 39.8, 43.2):
            sx = int(tx * TILE_SIZE - cam_x)
            pygame.draw.circle(screen, (118, 64, 44), (sx, pipe_y), 10, 3)
            pygame.draw.line(screen, (118, 64, 44), (sx - 8, pipe_y), (sx + 8, pipe_y), 2)
            pygame.draw.line(screen, (118, 64, 44), (sx, pipe_y - 8), (sx, pipe_y + 8), 2)
        # Raised catwalk rails across the maintenance bay.
        cat_y = int(36.8 * TILE_SIZE - cam_y)
        pygame.draw.rect(screen, (23, 28, 26), (int(32.0 * TILE_SIZE - cam_x), cat_y, int(11.8 * TILE_SIZE), 22))
        for gx in range(int(32.2 * TILE_SIZE - cam_x), int(43.5 * TILE_SIZE - cam_x), 18):
            pygame.draw.line(screen, (48, 56, 52), (gx, cat_y), (gx, cat_y + 22), 1)
        pygame.draw.line(screen, (98, 104, 92), (int(32.0 * TILE_SIZE - cam_x), cat_y), (int(43.8 * TILE_SIZE - cam_x), cat_y), 2)
        pygame.draw.line(screen, (98, 104, 92), (int(32.0 * TILE_SIZE - cam_x), cat_y + 22), (int(43.8 * TILE_SIZE - cam_x), cat_y + 22), 2)

        # Tool cage / workbench along west side.
        bench = pygame.Rect(int(32.4 * TILE_SIZE - cam_x), int(39.0 * TILE_SIZE - cam_y), 118, 42)
        render_util.soft_shadow(screen, (bench.x - 8, bench.y + 26, bench.w + 16, 18), 70)
        pygame.draw.rect(screen, (54, 48, 38), bench, border_radius=4)
        pygame.draw.rect(screen, (104, 92, 70), bench, 2, border_radius=4)
        for i in range(5):
            tx = bench.x + 12 + i * 20
            pygame.draw.line(screen, (138, 130, 104), (tx, bench.y + 10), (tx + 12, bench.y + 6), 2)
            pygame.draw.circle(screen, (36, 36, 32), (tx + 13, bench.y + 6), 2)
        tag = font_terminal_small.render(_T("m3.tools"), True, (130, 115, 80))
        screen.blit(tag, (bench.x + 8, bench.bottom - 14))

        # Electrical cabinet with gauges and breaker handles.
        cab = pygame.Rect(int(43.0 * TILE_SIZE - cam_x), int(39.2 * TILE_SIZE - cam_y), 62, 86)
        pygame.draw.rect(screen, (34, 44, 40), cab, border_radius=4)
        pygame.draw.rect(screen, (86, 98, 86), cab, 2, border_radius=4)
        for i, gy in enumerate((cab.y + 16, cab.y + 36, cab.y + 56)):
            pygame.draw.circle(screen, (22, 28, 26), (cab.x + 18, gy), 8)
            pygame.draw.circle(screen, (118, 142, 110), (cab.x + 18, gy), 8, 1)
            pygame.draw.line(screen, (160, 80, 45), (cab.x + 18, gy), (cab.x + 24, gy - 3 + i), 1)
            pygame.draw.rect(screen, (78, 82, 72), (cab.x + 36, gy - 6, 12, 12), border_radius=1)
        if not staticlayer.baking() and (_now_ms() // 500) % 2 == 0:
            pygame.draw.circle(screen, (80, 220, 120), (cab.right - 10, cab.y + 10), 2)

        # Colored service pipes: routed along the SOUTH wall band, not across
        # the open floor (they read as floating conveyors otherwise).
        for idx, (py_off, col) in enumerate(((0.0, (115, 62, 48)), (0.18, (54, 82, 96)), (0.36, (88, 90, 62)))):
            py = int((42.25 + py_off) * TILE_SIZE - cam_y)
            pygame.draw.line(screen, (18, 20, 18), (int(32.2 * TILE_SIZE - cam_x), py + 3), (int(43.7 * TILE_SIZE - cam_x), py + 3), 5)
            pygame.draw.line(screen, col, (int(32.2 * TILE_SIZE - cam_x), py), (int(43.7 * TILE_SIZE - cam_x), py), 4)
            pygame.draw.line(screen, (150, 150, 128), (int(32.2 * TILE_SIZE - cam_x), py - 1), (int(43.7 * TILE_SIZE - cam_x), py - 1), 1)

        # Warning floor stripes near machinery.
        for i in range(9):
            sx = int(32.0 * TILE_SIZE - cam_x + i * 18)
            sy = int(41.0 * TILE_SIZE - cam_y)
            col = (112, 92, 42) if i % 2 == 0 else (28, 28, 24)
            pygame.draw.polygon(screen, col, [(sx, sy), (sx + 13, sy), (sx + 4, sy + 14), (sx - 8, sy + 14)])
        # Steam wisps: soft layered puffs that thin out as they rise (flat
        # single-alpha ellipses read as stickers pasted on the boilers).
        rng = random.Random(8841)
        for i in range(10):
            bx_t, by_t = (34.0, 35.0) if i % 2 == 0 else (42.0, 35.4)
            sx = int((bx_t + rng.uniform(-0.5, 0.5)) * TILE_SIZE - cam_x)
            rise = rng.uniform(0.4, 2.2)
            sy = int((by_t - rise) * TILE_SIZE - cam_y)
            a = max(6, 22 - int(rise * 7))
            w = int(22 + rise * 10)
            puff = pygame.Surface((w, 16), pygame.SRCALPHA)
            for layer, (lw, lh, la) in enumerate(((w, 14, a // 3),
                                                  (int(w * 0.7), 10, a // 2),
                                                  (int(w * 0.4), 6, a))):
                pygame.draw.ellipse(puff, (105, 120, 112, la),
                                    ((w - lw) // 2, (14 - lh) // 2, lw, lh))
            screen.blit(puff, (sx - w // 2, sy - 8))
        pygame.draw.rect(screen, (0, 0, 0, 70), (x0, y0, w, h), 2)
    finally:
        screen.set_clip(old_clip)



def _draw_exit_zone_details(cam_x, cam_y):
    """Add readable exit/transition language to the east E tiles."""
    x0 = 40 * TILE_SIZE - cam_x
    # Rows 14-16: same vertical axis as the main road/cell-block corridor.
    y0 = 14 * TILE_SIZE - cam_y
    w = 3 * TILE_SIZE
    h = 3 * TILE_SIZE
    if x0 > WIDTH + 80 or x0 + w < -80 or y0 > HEIGHT + 80 or y0 + h < -80:
        return

    pygame.draw.rect(screen, (18, 30, 24), (int(x0), int(y0), w, h))
    for yy in range(int(y0 + 10), int(y0 + h - 10), 16):
        pygame.draw.line(screen, (44, 84, 58), (int(x0 + 8), yy), (int(x0 + w - 8), yy), 1)
    center_y = y0 + h // 2
    pygame.draw.rect(screen, (42, 92, 58), (int(x0 + 18), int(center_y - 39), int(w - 36), 18), border_radius=3)
    sign = font_terminal_small.render(_T("m3.service_exit"), True, (160, 235, 170))
    screen.blit(sign, (int(x0 + w // 2 - sign.get_width() // 2), int(center_y - 35)))
    arrow = font_terminal.render(_T("m3.text"), True, (120, 220, 150))
    screen.blit(arrow, (int(x0 + w // 2 - arrow.get_width() // 2), int(center_y - 10)))



def _draw_m3_doors_foreground(cam_x, cam_y):
    """Draw all Mission 3 D tiles as actual doors."""
    mw, mh = _m3_maps._live_map_dims()
    start_col = max(0, int(cam_x // TILE_SIZE) - 1)
    end_col = min(mw, int((cam_x + WIDTH) // TILE_SIZE) + 2)
    start_row = max(0, int(cam_y // TILE_SIZE) - 1)
    end_row = min(mh, int((cam_y + HEIGHT) // TILE_SIZE) + 2)

    for row in range(start_row, end_row):
        map_row = _m3_maps.MISSION3_MAP[row]
        for col in range(start_col, end_col):
            if map_row[col] != "D":
                continue
            if row == _DOOR_TILE_ROW and col in (_DOOR_TILE_COL, _DOOR_TILE_COL + 1):
                continue
            sx = col * TILE_SIZE - cam_x
            sy = row * TILE_SIZE - cam_y
            _draw_m3_door_tile(screen, sx, sy, col, row)


def _draw_m3_doors(cam_x, cam_y):
    for d in STATE.doors:
        # Skip Biribel's cell door - it's drawn entirely by _draw_cell_door
        # (via _draw_cell_room). Drawing it here too leaves a grey rect
        # (70, 76, 84) that bleeds through the smaller breached-panel
        # polygon after detonation, making the door read as a flat grey
        # box instead of a damaged door.
        door_col = d.rect.x // TILE_SIZE
        door_row = d.rect.y // TILE_SIZE
        if door_row == _DOOR_TILE_ROW and door_col in (_DOOR_TILE_COL, _DOOR_TILE_COL + 1):
            continue
        dr = pygame.Rect(d.rect.x - cam_x, d.rect.y - cam_y, TILE_SIZE, TILE_SIZE)
        if d.anim_progress < 1.0:
            draw_h = int(TILE_SIZE * (1.0 - d.anim_progress))
            if draw_h > 0:
                pygame.draw.rect(screen, (70, 76, 84), (dr.x, dr.y, TILE_SIZE, draw_h))
                pygame.draw.rect(screen, (30, 36, 42), (dr.x, dr.y, TILE_SIZE, draw_h), 1)
        else:
            pygame.draw.rect(screen, (36, 40, 46), (dr.x, dr.y, TILE_SIZE, 4))
            pygame.draw.rect(screen, (36, 40, 46), (dr.x, dr.bottom - 4, TILE_SIZE, 4))
            pygame.draw.rect(screen, (36, 40, 46), (dr.x, dr.y, 4, TILE_SIZE))
            pygame.draw.rect(screen, (36, 40, 46), (dr.right - 4, dr.y, 4, TILE_SIZE))


def _draw_interrogation_restrained_player(cam_x, cam_y):
    """Draw Biribel cuffed into the live gameplay interrogation chair.

    Kept deliberately close to the game's normal top-down sprite language:
    small footprint, flat colors, readable restraints. The previous pass looked
    like a separate cutscene icon pasted into the tilemap.
    """
    wx, wy = _interrogation_chair_pos()
    cx = int(wx - cam_x)
    # Sit the body a few pixels lower than the furniture center so it lines up
    # with the chair seat drawn by _draw_cell_room instead of floating over it.
    cy = int(wy - cam_y + 5)

    tick = _now_ms()
    trem = 1 if (tick // 240) % 2 == 0 else 0

    uniform = C_PLAYER_UNIFORM
    uniform_dark = (max(0, uniform[0] - 28), max(0, uniform[1] - 28), max(0, uniform[2] - 28))
    skin = C_PLAYER_SKIN
    skin_shadow = (126, 88, 66)
    metal = (96, 94, 86)
    metal_hi = (148, 144, 130)
    strap = (58, 64, 64)
    strap_dark = (18, 20, 20)

    # Small chair silhouette matching the tile-prop scale.
    render_util.soft_shadow(screen, (cx - 25, cy + 12, 50, 16), 85)
    back = pygame.Rect(cx - 17, cy - 28, 34, 26)
    pygame.draw.rect(screen, (24, 23, 21), back, border_radius=4)
    pygame.draw.rect(screen, (64, 60, 54), back, 1, border_radius=4)
    seat = pygame.Rect(cx - 18, cy - 6, 36, 23)
    pygame.draw.rect(screen, (34, 32, 29), seat, border_radius=4)
    pygame.draw.rect(screen, (70, 66, 58), seat, 1, border_radius=4)

    # Chair arm rails/anchor plates. These line up with the cuffed wrists and
    # immediately communicate "locked down" without a huge custom rig.
    rail_y = cy + 1
    for side in (-1, 1):
        pygame.draw.line(screen, (46, 44, 40), (cx + side * 14, rail_y), (cx + side * 42, rail_y), 5)
        pygame.draw.line(screen, (84, 80, 72), (cx + side * 15, rail_y - 2), (cx + side * 40, rail_y - 2), 1)
        plate = pygame.Rect(0, 0, 14, 12)
        plate.center = (cx + side * 45, rail_y)
        pygame.draw.rect(screen, (36, 34, 31), plate, border_radius=3)
        pygame.draw.rect(screen, metal, plate, 1, border_radius=3)
        pygame.draw.circle(screen, (20, 18, 16), plate.center, 2)

    # Hunched torso, same scale as the normal Player sprite.
    torso = [
        (cx - 13, cy - 12),
        (cx + 13, cy - 12),
        (cx + 16, cy + 13),
        (cx - 16, cy + 13),
    ]
    pygame.draw.polygon(screen, uniform_dark, torso)
    pygame.draw.polygon(screen, uniform, [(cx - 9, cy - 10), (cx + 10, cy - 10), (cx + 12, cy + 11), (cx - 12, cy + 11)])

    # Harness straps over the normal uniform. This is the main confinement cue.
    pygame.draw.line(screen, strap, (cx - 13, cy - 11), (cx + 13, cy + 11), 4)
    pygame.draw.line(screen, strap_dark, (cx - 13, cy - 11), (cx + 13, cy + 11), 1)
    pygame.draw.line(screen, strap, (cx + 13, cy - 11), (cx - 13, cy + 11), 4)
    pygame.draw.line(screen, strap_dark, (cx + 13, cy - 11), (cx - 13, cy + 11), 1)
    pygame.draw.rect(screen, strap, (cx - 17, cy + 1, 34, 6), border_radius=2)
    pygame.draw.rect(screen, strap_dark, (cx - 17, cy + 1, 34, 6), 1, border_radius=2)
    pygame.draw.rect(screen, metal_hi, (cx - 4, cy, 8, 8), 1, border_radius=1)

    # Head bowed toward the monitor. It uses the same skin colors as Player.draw
    # but darker, so it doesn't read as a different art style.
    pygame.draw.circle(screen, skin_shadow, (cx, cy - 22), 12)
    pygame.draw.circle(screen, skin, (cx, cy - 24), 10)
    pygame.draw.arc(screen, (42, 30, 24), (cx - 10, cy - 34, 20, 16), math.pi, math.tau, 4)
    pygame.draw.line(screen, (46, 34, 28), (cx - 5, cy - 18), (cx + 5, cy - 18), 1)

    # Simple head brace behind the neck, sized like a prop detail rather than a
    # separate cinematic device.
    brace = pygame.Rect(cx - 15, cy - 33, 30, 7)
    pygame.draw.rect(screen, (22, 22, 21), brace, border_radius=2)
    pygame.draw.rect(screen, metal, brace, 1, border_radius=2)

    # Arms locked outward to the chair rails. Use thick dark sleeves like the
    # normal player silhouette, then bright cuffs on top.
    for side in (-1, 1):
        shoulder = (cx + side * 13, cy - 4)
        elbow = (cx + side * 25, cy + 2)
        wrist = (cx + side * (39 + trem), rail_y)
        pygame.draw.line(screen, uniform_dark, shoulder, elbow, 8)
        pygame.draw.line(screen, uniform_dark, elbow, wrist, 8)
        pygame.draw.line(screen, uniform, shoulder, elbow, 3)
        pygame.draw.line(screen, uniform, elbow, wrist, 3)

        # Hand trapped under cuff.
        pygame.draw.circle(screen, skin, (wrist[0] - side * 3, wrist[1]), 4)
        cuff = pygame.Rect(0, 0, 18, 8)
        cuff.center = wrist
        pygame.draw.rect(screen, metal, cuff, border_radius=3)
        pygame.draw.rect(screen, metal_hi, cuff, 1, border_radius=3)
        pygame.draw.line(screen, (42, 42, 38), (cuff.x + 3, cuff.centery), (cuff.right - 3, cuff.centery), 1)

        # Taut chain from cuff to chair anchor.
        anchor = (cx + side * 45, rail_y)
        pygame.draw.line(screen, (54, 54, 50), wrist, anchor, 1)
        for i in range(2):
            q = (i + 0.5) / 2.0
            lx = int(wrist[0] + (anchor[0] - wrist[0]) * q)
            ly = int(wrist[1] + (anchor[1] - wrist[1]) * q)
            pygame.draw.ellipse(screen, metal_hi, (lx - 3, ly - 2, 6, 4), 1)

    # Ankles cuffed to the chair base, small but visible when the dialogue panel
    # is not covering the bottom of the sprite.
    for side in (-1, 1):
        foot = pygame.Rect(cx + side * 9 - 6, cy + 17, 12, 6)
        pygame.draw.rect(screen, (10, 10, 11), foot, border_radius=2)
        pygame.draw.rect(screen, metal, foot, 1, border_radius=2)



WAYPOINT_COL = (220, 180, 90)          # craft/objective gold (drain legacy)
WAYPOINT_GREEN = (130, 215, 160)         # ready / acquired
WAYPOINT_AMBER = (240, 205, 120)         # K-9 / story pickup
WAYPOINT_CYAN = (120, 200, 220)          # relay/tech terminal
WAYPOINT_VIOLET = (200, 160, 255)        # Maru / ghost contact
WAYPOINT_RED = (235, 120, 100)           # locked / blocked
WAYPOINT_WHITE = (230, 232, 235)         # neutral exit


def _objective_waypoint_target():
    """Return the current step's world waypoint as (x, y, label, color).

    Never points at enemies. Returns None when no guidance is appropriate
    (interrogation, black ledger debug, or the step has no fixed location).
    Mirrors the objective ladder from _update_breakout / _update_comms /
    _update_archives so the visual marker always matches the text objective.
    """
    stage = getattr(STATE, "mission3_stage", STAGE_INTERROGATION)

    if stage == STAGE_BREAKOUT:
        weapon = getattr(STATE, "mission3_weapon", "none")
        if weapon == "chair_leg" and not getattr(STATE, "mission3_crafting_active", False):
            return (_DRAIN_TILE_COL * TILE_SIZE + TILE_SIZE // 2,
                    _DRAIN_TILE_ROW * TILE_SIZE + TILE_SIZE // 2,
                    "DRAIN", WAYPOINT_COL)
        if not getattr(STATE, "m3_volkov_run_done", False):
            return None  # Volkov is still running his scripted escape - no objective yet.
        if not getattr(STATE, "mission3_guards_spawned", False):
            return None
        if getattr(STATE, "m3_guards_all_killed", False):
            exit_ready, _ = _m3_exit_requirements()
            if not exit_ready and not getattr(STATE, "k9_unlocked", False):
                return (_K9_STAND_COL * TILE_SIZE + TILE_SIZE // 2,
                        _K9_STAND_ROW * TILE_SIZE + TILE_SIZE // 2,
                        "K-9 SMG", WAYPOINT_AMBER)
            return (_EXIT_TILE_COL * TILE_SIZE + TILE_SIZE // 2,
                    _EXIT_TILE_ROW * TILE_SIZE + TILE_SIZE // 2,
                    "EXIT", WAYPOINT_WHITE)
        return None  # "Clear hostiles: N left" - player hunts remaining guards.

    if stage == STAGE_COMMS:
        if getattr(STATE, "m3_relay_active", False):
            return None  # tuning in progress - stand at the relay.
        if getattr(STATE, "m3_relay_tuned", False):
            return None  # transition to Archives handles the next guidance.
        if len(getattr(STATE, "enemies", [])) > 0:
            return None  # clear hostiles first.
        if not getattr(STATE, "m3_comms_power_restored", False):
            return (*_comms_breaker_pos(), "BATTERY", WAYPOINT_CYAN)
        if not getattr(STATE, "m3_comms_auth_acquired", False):
            return (*_comms_auth_pos(), "AUTH", WAYPOINT_CYAN)
        return (*_relay_pos(), "RELAY", WAYPOINT_CYAN)

    if stage == STAGE_ARCHIVES:
        hostiles = [e for e in getattr(STATE, "enemies", []) if not getattr(e, "dead", False)]
        if getattr(STATE, "m3_maru_contact_active", False):
            return None  # message is playing - hold position.
        if not getattr(STATE, "m3_archives_cleared", False):
            return None  # clear hostiles first.
        if not getattr(STATE, "m3_maru_contacted", False):
            return (_MARU_TERMINAL_COL * TILE_SIZE + TILE_SIZE // 2,
                    _MARU_TERMINAL_ROW * TILE_SIZE + TILE_SIZE // 2,
                    "MARU", WAYPOINT_VIOLET)
        if not getattr(STATE, "m3_vostral_acquired", False):
            return (_VOSTRAL_FILE_COL * TILE_SIZE + TILE_SIZE // 2,
                    _VOSTRAL_FILE_ROW * TILE_SIZE + TILE_SIZE // 2,
                    "VOSTRAL", WAYPOINT_AMBER)
        return (_ARCHIVES_EXIT_COL * TILE_SIZE + TILE_SIZE // 2,
                _ARCHIVES_EXIT_ROW * TILE_SIZE + TILE_SIZE // 2,
                "STAIRWELL", WAYPOINT_GREEN)

    return None


def _draw_objective_waypoint(cam_x, cam_y):
    """Draw a pulsing ring + off-screen edge arrow toward the current part.

    Generalized from the original drain guidance: one template, many targets.
    The dispatcher above picks the target based on the active stage/step, so
    the player always sees guidance for the *specific* thing they need to find
    next - never an enemy, never a vague area.
    """
    target = _objective_waypoint_target()
    if target is None:
        return
    if not STATE.player:
        return

    wx, wy, label_text, marker_col = target
    sx = wx - cam_x
    sy = wy - cam_y
    pulse = 0.5 + 0.5 * math.sin(_now_s() * 5.0)
    alpha = int(145 + 80 * pulse)

    if -40 <= sx <= WIDTH + 40 and -40 <= sy <= HEIGHT + 40:
        ring = pygame.Surface((72, 72), pygame.SRCALPHA)
        pygame.draw.circle(ring, (*marker_col, int(45 + 35 * pulse)), (36, 36), 31)
        pygame.draw.circle(ring, (*marker_col, alpha), (36, 36), 24, 2)
        pygame.draw.circle(ring, (255, 235, 200, alpha), (36, 36), 8, 1)
        screen.blit(ring, (int(sx - 36), int(sy - 36)))
        ar = artpack.icon("arrow")
        # Keep the arrow + label out of the top HUD/objective band: clamp the
        # tag (not the ring) below the safe area when the target projects high.
        tag_y = max(sy, 150)
        if ar is not None:
            bob = int(3 * math.sin(_now_s() * 4.0))
            screen.blit(ar, (int(sx - 9), int(tag_y - 62 + bob)))
        lbl = font_terminal_small.render(label_text, True, marker_col)
        lbl.set_alpha(alpha)
        screen.blit(lbl, (int(sx - lbl.get_width() // 2), int(tag_y - 44)))

        # Directional line only when the player still has to travel a bit.
        dist = math.hypot(STATE.player.rect.centerx - wx,
                          STATE.player.rect.centery - wy)
        if dist > 85:
            px = STATE.player.rect.centerx - cam_x
            py = STATE.player.rect.centery - cam_y
            ang = math.atan2(sy - py, sx - px)
            start = (int(px + math.cos(ang) * 28), int(py + math.sin(ang) * 28))
            end = (int(px + math.cos(ang) * 68), int(py + math.sin(ang) * 68))
            pygame.draw.line(screen, (*marker_col, alpha), start, end, 2)
            left = (int(end[0] - math.cos(ang - 0.55) * 10),
                    int(end[1] - math.sin(ang - 0.55) * 10))
            right = (int(end[0] - math.cos(ang + 0.55) * 10),
                     int(end[1] - math.sin(ang + 0.55) * 10))
            pygame.draw.polygon(screen, marker_col, [end, left, right])
    else:
        # Off-screen fallback arrow clamped to screen edge.
        px = STATE.player.rect.centerx - cam_x
        py = STATE.player.rect.centery - cam_y
        ang = math.atan2(sy - py, sx - px)
        edge_x = max(40, min(WIDTH - 40, int(WIDTH / 2 + math.cos(ang) * (WIDTH / 2 - 60))))
        edge_y = max(LETTER_H + 35, min(HEIGHT - LETTER_H - 35,
                                       int(HEIGHT / 2 + math.sin(ang) * (HEIGHT / 2 - LETTER_H - 45))))
        tip = (edge_x, edge_y)
        back = (int(edge_x - math.cos(ang) * 24), int(edge_y - math.sin(ang) * 24))
        left = (int(back[0] + math.cos(ang + math.pi / 2) * 10),
                int(back[1] + math.sin(ang + math.pi / 2) * 10))
        right = (int(back[0] - math.cos(ang + math.pi / 2) * 10),
                 int(back[1] - math.sin(ang + math.pi / 2) * 10))
        pygame.draw.polygon(screen, marker_col, [tip, left, right])
        lbl = font_terminal_small.render(label_text, True, marker_col)
        screen.blit(lbl, (edge_x - lbl.get_width() // 2, edge_y + 12))


# Back-compat shim: the old name was called from the cell-block draw path.
# Kept so nothing else that references _draw_drain_guidance silently breaks.
def _draw_drain_guidance(cam_x, cam_y):
    _draw_objective_waypoint(cam_x, cam_y)



def _draw_comms_wing_details(cam_x, cam_y):
    """Art pass for the second Mission 3 map: service/comms wing."""
    # Arrival airlock: visually links back to the cell-block service door.
    ax0 = 3 * TILE_SIZE - cam_x
    ay0 = 18 * TILE_SIZE - cam_y
    aw = 8 * TILE_SIZE
    ah = 11 * TILE_SIZE
    if _screen_visible_rect(ax0, ay0, aw, ah):
        pygame.draw.rect(screen, (0, 0, 0, 72), (int(ax0), int(ay0), int(aw), int(ah)), 2)
        # Same greenish sealed-door language as the transition cutscene.
        sealed = pygame.Rect(int(4.15 * TILE_SIZE - cam_x), int(19.0 * TILE_SIZE - cam_y), 112, 142)
        pygame.draw.rect(screen, (5, 7, 8), sealed.inflate(14, 14), border_radius=4)
        pygame.draw.rect(screen, (46, 76, 68), sealed, border_radius=3)
        pygame.draw.rect(screen, (110, 168, 142), sealed, 2, border_radius=3)
        slit = pygame.Rect(sealed.centerx - 8, sealed.y + 10, 16, sealed.h - 20)
        pygame.draw.rect(screen, (120, 175, 150), slit)
        pygame.draw.rect(screen, (36, 58, 52), slit, 1)
        label = font_terminal_small.render(_T("m3.cell_block_a_sealed"), True, (110, 155, 135))
        label.set_alpha(180)
        screen.blit(label, (sealed.centerx - label.get_width() // 2, sealed.bottom + 10))
        # Scuffed handoff / arrival path out of the sealed door into the corridor.
        path = pygame.Surface((230, 120), pygame.SRCALPHA)
        render_util.soft_shadow(path, (0, 25, 230, 58), 55)
        pygame.draw.ellipse(path, (60, 90, 78, 26), (34, 34, 150, 30))
        screen.blit(path, (sealed.centerx - 115, sealed.bottom - 15))
        # Cable/pipe continuation from old service wing.
        pygame.draw.line(screen, (52, 60, 56), (sealed.right + 16, sealed.y + 18), (int(10.0 * TILE_SIZE - cam_x), sealed.y + 18), 4)
        pygame.draw.line(screen, (104, 118, 104), (sealed.right + 16, sealed.y + 16), (int(10.0 * TILE_SIZE - cam_x), sealed.y + 16), 1)
        # Wall panel / status box.
        panel = pygame.Rect(int(8.3 * TILE_SIZE - cam_x), int(20.0 * TILE_SIZE - cam_y), 54, 38)
        pygame.draw.rect(screen, (20, 28, 27), panel, border_radius=3)
        pygame.draw.rect(screen, (72, 90, 84), panel, 1, border_radius=3)
        pygame.draw.circle(screen, (190, 45, 38), (panel.right - 10, panel.y + 10), 3)
        pygame.draw.line(screen, (44, 62, 56), (panel.x + 8, panel.y + 24), (panel.right - 8, panel.y + 24), 1)
        # A few familiar black scuffs so it feels continuous with the first map.
        for i, (sx, sy, sw, sh) in enumerate(((6.2, 23.0, 44, 12), (4.6, 26.1, 34, 9), (8.7, 24.8, 28, 8))):
            pygame.draw.ellipse(screen, (5, 6, 6), (int(sx*TILE_SIZE - cam_x), int(sy*TILE_SIZE - cam_y), sw, sh))

    # Service arrival corridor.
    x0 = 3 * TILE_SIZE - cam_x
    y0 = 22 * TILE_SIZE - cam_y
    w = 42 * TILE_SIZE
    h = 6 * TILE_SIZE
    if _screen_visible_rect(x0, y0, w, h):
        pygame.draw.rect(screen, (0, 0, 0, 55), (int(x0), int(y0), int(w), int(h)), 2)
        stencil = font_terminal_small.render(_T("m3.service_access_comms_wing"), True, (78, 110, 105))
        stencil.set_alpha(160)
        screen.blit(stencil, (int(14 * TILE_SIZE - cam_x), int(26 * TILE_SIZE - cam_y + 18)))
        for tx in (8, 16, 24, 32, 40):
            lx = tx * TILE_SIZE + TILE_SIZE // 2 - cam_x
            ly = 23 * TILE_SIZE - cam_y + 8
            pygame.draw.rect(screen, (95, 112, 104), (int(lx - 38), int(ly), 76, 4), border_radius=2)
            glow = pygame.Surface((130, 44), pygame.SRCALPHA)
            pygame.draw.ellipse(glow, (6, 10, 9, 255), glow.get_rect())
            screen.blit(glow, (int(lx - 65), int(ly + 7)), special_flags=pygame.BLEND_RGBA_ADD)

    # Relay room.
    rx = 15 * TILE_SIZE - cam_x
    ry = 10 * TILE_SIZE - cam_y
    rw = 18 * TILE_SIZE
    rh = 12 * TILE_SIZE
    if _screen_visible_rect(rx, ry, rw, rh):
        pygame.draw.rect(screen, (0, 0, 0, 70), (int(rx), int(ry), int(rw), int(rh)), 2)
        label = font_terminal.render(_T("m3.relay_room"), True, (120, 185, 165))
        screen.blit(label, (int(rx + rw // 2 - label.get_width() // 2), int(ry + 18)))
        # Console banks.
        for cx_tile in (19.8, 28.2):
            sx = int(cx_tile * TILE_SIZE - cam_x)
            sy = int(16.4 * TILE_SIZE - cam_y)
            console = pygame.Rect(sx - 70, sy - 22, 140, 44)
            render_util.soft_shadow(screen, (console.x - 8, console.y + 28, console.w + 16, 20), 80)
            pygame.draw.rect(screen, (22, 34, 34), console, border_radius=5)
            pygame.draw.rect(screen, (72, 104, 96), console, 2, border_radius=5)
            if not staticlayer.baking():
                fr = int(_now_s() * 2.0)
                for i in range(4):
                    px = console.x + 16 + i * 28
                    pygame.draw.rect(screen, (8, 16, 14), (px, console.y + 10, 18, 12), border_radius=1)
                    on = (i + fr) % 2 == 0
                    pygame.draw.circle(screen, (80, 220, 130) if on else (190, 60, 48), (px + 22, console.y + 16), 2)
        # Central relay table with dish graphic.
        table = pygame.Rect(int(24 * TILE_SIZE - cam_x - 59), int(19.2 * TILE_SIZE - cam_y - 26), 118, 52)
        pygame.draw.rect(screen, (42, 48, 44), table, border_radius=5)
        pygame.draw.rect(screen, (92, 112, 96), table, 2, border_radius=5)
        pygame.draw.circle(screen, (18, 24, 22), table.center, 18)
        pygame.draw.arc(screen, (95, 170, 130), (table.centerx - 26, table.centery - 26, 52, 52), math.pi * 0.1, math.pi * 0.9, 2)
        pygame.draw.line(screen, (95, 170, 130), table.center, (table.centerx + 22, table.centery - 12), 2)
        # Cable runs.
        for off in (-38, 0, 38):
            pygame.draw.line(screen, (32, 42, 40), (table.centerx + off, table.bottom), (table.centerx + off + 24, int(21 * TILE_SIZE - cam_y)), 2)

    # Server cage/equipment bay.
    sx0 = 34 * TILE_SIZE - cam_x
    sy0 = 13 * TILE_SIZE - cam_y
    sw = 11 * TILE_SIZE
    sh = 17 * TILE_SIZE
    if _screen_visible_rect(sx0, sy0, sw, sh):
        pygame.draw.rect(screen, (0, 0, 0, 70), (int(sx0), int(sy0), int(sw), int(sh)), 2)
        label = font_terminal_small.render(_T("m3.server_cage"), True, (110, 150, 145))
        screen.blit(label, (int(sx0 + sw // 2 - label.get_width() // 2), int(sy0 + 14)))
        for cx_tile in (36, 42):
            rack = pygame.Rect(int(cx_tile * TILE_SIZE - cam_x - 29), int(18 * TILE_SIZE - cam_y - 115), 58, 230)
            if not staticlayer.baking():
                rf = artpack.get("rack_%d" % (int(_now_s() * 2.5 + cx_tile) % 3))
                if rf is not None:
                    screen.blit(pygame.transform.smoothscale(rf, rack.size), rack.topleft)
                    continue
            pygame.draw.rect(screen, (16, 22, 24), rack, border_radius=4)
            pygame.draw.rect(screen, (58, 80, 78), rack, 2, border_radius=4)
            for yy in range(rack.y + 16, rack.bottom - 12, 18):
                pygame.draw.line(screen, (30, 42, 42), (rack.x + 6, yy), (rack.right - 6, yy), 1)
                if (yy // 18) % 3 == 0:
                    pygame.draw.circle(screen, (65, 210, 120), (rack.right - 10, yy + 4), 2)
        # Workbench.
        bench = pygame.Rect(int(37.5 * TILE_SIZE - cam_x - 64), int(25 * TILE_SIZE - cam_y - 21), 128, 42)
        pygame.draw.rect(screen, (48, 44, 38), bench, border_radius=4)
        pygame.draw.rect(screen, (104, 92, 70), bench, 2, border_radius=4)
        for i in range(4):
            pygame.draw.rect(screen, (95, 90, 70), (bench.x + 12 + i * 25, bench.y + 10, 16, 10))

    # South utility/battery room.
    ux = 13 * TILE_SIZE - cam_x
    uy = 29 * TILE_SIZE - cam_y
    uw = 18 * TILE_SIZE
    uh = 11 * TILE_SIZE
    if _screen_visible_rect(ux, uy, uw, uh):
        pygame.draw.rect(screen, (0, 0, 0, 70), (int(ux), int(uy), int(uw), int(uh)), 2)
        label = font_terminal_small.render(_T("m3.battery_backup"), True, (160, 145, 100))
        screen.blit(label, (int(ux + uw // 2 - label.get_width() // 2), int(uy + 14)))
        for cx_tile in (17.0, 27.2):
            sx = int(cx_tile * TILE_SIZE - cam_x)
            sy = int(35.0 * TILE_SIZE - cam_y)
            pygame.draw.rect(screen, (36, 42, 34), (sx - 35, sy - 59, 70, 118), border_radius=6)
            pygame.draw.rect(screen, (88, 104, 78), (sx - 35, sy - 59, 70, 118), 2, border_radius=6)
            if staticlayer.baking():
                continue
            for i in range(4):
                pygame.draw.rect(screen, (18, 22, 18), (sx - 22, sy - 44 + i * 24, 44, 12), border_radius=2)
                on = (i + int(_now_s() * 1.5)) % 3 != 0
                pygame.draw.circle(screen, (190, 80, 40) if on else (70, 40, 26), (sx + 26, sy - 38 + i * 24), 2)
        # Hero interactable: the breaker cabinet the [E] prompt sits on.
        # Previously this spot was bare wall, so the objective's target had
        # no machine to be seen on.
        _hx, _hy = _comms_breaker_pos()
        _bat_spr = get_sprite("station_battery_backup.png")
        if _bat_spr is not None:
            screen.blit(_bat_spr, (int(_hx - cam_x - _bat_spr.get_width() // 2),
                                   int(_hy - cam_y - _bat_spr.get_height() // 2)))

    # Archive access door marker, east side.
    ax = 46 * TILE_SIZE + TILE_SIZE // 2 - cam_x
    ay = 24 * TILE_SIZE + TILE_SIZE // 2 - cam_y
    if -80 < ax < WIDTH + 80 and -80 < ay < HEIGHT + 80:
        sign = font_terminal.render(_T("m3.archives"), True, (150, 220, 170))
        screen.blit(sign, (int(ax - sign.get_width() - 20), int(ay - 45)))
        pygame.draw.rect(screen, (30, 80, 48), (int(ax - 32), int(ay - 20), 64, 40), 2, border_radius=4)


def _draw_comms_map_polish(cam_x, cam_y):
    """Final readability/art pass for the Comms Wing map."""
    _draw_rect_room_frame(cam_x, cam_y, 3, 18, 8, 11, gaps_right=[(24, 25)], label="AIRLOCK", label_col=(120, 165, 145))
    _draw_rect_room_frame(cam_x, cam_y, 11, 17, 5, 6, gaps_bottom=[(12, 13)], label="SECURITY", label_col=(145, 155, 120))
    _draw_rect_room_frame(cam_x, cam_y, 15, 10, 18, 12, gaps_bottom=[(23, 24)], label="RELAY ROOM", label_col=(120, 190, 165))
    _draw_rect_room_frame(cam_x, cam_y, 34, 13, 11, 17, gaps_left=[(23, 24)], gaps_right=[(24, 24)], label="SERVER CAGE", label_col=(110, 155, 150))
    _draw_rect_room_frame(cam_x, cam_y, 13, 29, 18, 11, gaps_top=[(21, 22)], label="BATTERY BACKUP", label_col=(170, 145, 90))

    # Security booth details.
    bx = 11 * TILE_SIZE - cam_x
    by = 17 * TILE_SIZE - cam_y
    if _screen_visible_rect(bx, by, 5*TILE_SIZE, 6*TILE_SIZE):
        glass = pygame.Rect(int(11.2*TILE_SIZE - cam_x), int(20.0*TILE_SIZE - cam_y), 46, 92)
        pygame.draw.rect(screen, (30, 55, 58), glass, border_radius=3)
        pygame.draw.rect(screen, (90, 130, 132), glass, 1, border_radius=3)
        for off in range(-40, 80, 12):
            pygame.draw.line(screen, (120, 165, 165, 60), (glass.x + off, glass.y), (glass.x + off + 70, glass.bottom), 1)
        desk = pygame.Rect(int(12.0*TILE_SIZE - cam_x), int(18.45*TILE_SIZE - cam_y), 165, 44)
        mon = pygame.Rect(desk.x + 14, desk.y - 24, 42, 25)
        chair = pygame.Rect(int(13.8*TILE_SIZE - cam_x), int(19.35*TILE_SIZE - cam_y), 24, 24)
        _booth_spr = get_sprite("station_security_booth.png")
        if _booth_spr is not None:
            screen.blit(_booth_spr, (desk.x, mon.y))
        else:
            pygame.draw.ellipse(screen, (0,0,0,75), (desk.x-8, desk.y+28, desk.w+16, 18))
            pygame.draw.rect(screen, (48, 43, 36), desk, border_radius=4)
            pygame.draw.rect(screen, (106, 92, 70), desk, 2, border_radius=4)
            pygame.draw.rect(screen, (10, 18, 18), mon, border_radius=3)
            pygame.draw.rect(screen, (66, 95, 88), mon, 1, border_radius=3)
            pygame.draw.circle(screen, (80, 220, 130), (mon.right - 6, mon.y + 6), 2)
            for i in range(3):
                pygame.draw.rect(screen, (105, 98, 74), (desk.x + 72 + i*24, desk.y + 12, 16, 10))
            pygame.draw.ellipse(screen, (0,0,0,60), (chair.x-2, chair.y+14, 28, 10))
            pygame.draw.rect(screen, (32, 38, 38), chair, border_radius=4)
            pygame.draw.rect(screen, (70, 78, 74), chair, 1, border_radius=4)

    # Cable tray connecting airlock -> relay/server/utility.
    sx0 = 10 * TILE_SIZE - cam_x
    sy = 25 * TILE_SIZE - cam_y + 12
    sx1 = 43 * TILE_SIZE - cam_x
    if _screen_visible_rect(sx0, sy-40, sx1-sx0, 120):
        pygame.draw.rect(screen, (18, 22, 22), (int(sx0), int(sy), int(sx1-sx0), 14), border_radius=2)
        pygame.draw.rect(screen, (58, 68, 62), (int(sx0), int(sy), int(sx1-sx0), 14), 1, border_radius=2)
        for i, col in enumerate([(120,60,48), (62,98,120), (92,110,70), (130,110,55)]):
            y = int(sy + 3 + i*2)
            pygame.draw.line(screen, col, (int(sx0+12), y), (int(sx1-12), y), 1)
        for tx, branch_y in ((23.5, 21.0), (38.0, 23.4), (22.0, 29.2)):
            bx2 = int(tx*TILE_SIZE - cam_x)
            by2 = int(branch_y*TILE_SIZE - cam_y)
            pygame.draw.line(screen, (42, 54, 50), (bx2, int(sy+7)), (bx2, by2), 3)
            pygame.draw.line(screen, (90, 125, 105), (bx2+2, int(sy+7)), (bx2+2, by2), 1)

    sign = font_terminal_small.render(_T("m3.from_cell_block_a"), True, (92, 140, 120))
    sign.set_alpha(170)
    screen.blit(sign, (int(4.45*TILE_SIZE - cam_x), int(26.6*TILE_SIZE - cam_y)))
    spool_x = int(8.2*TILE_SIZE - cam_x)
    spool_y = int(26.1*TILE_SIZE - cam_y)
    if -80 < spool_x < WIDTH+80 and -80 < spool_y < HEIGHT+80:
        pygame.draw.ellipse(screen, (0,0,0,70), (spool_x-20, spool_y+12, 42, 12))
        pygame.draw.circle(screen, (52,42,30), (spool_x, spool_y), 16)
        pygame.draw.circle(screen, (26,22,18), (spool_x, spool_y), 8)
        pygame.draw.line(screen, (60,58,48), (spool_x+12, spool_y+7), (spool_x+46, spool_y+24), 3)
    for i in range(5):
        ax = int((11.2+i*0.55)*TILE_SIZE - cam_x)
        ay = int(26.1*TILE_SIZE - cam_y)
        pygame.draw.polygon(screen, (120, 100, 46), [(ax,ay), (ax+18,ay), (ax+10,ay+12), (ax-8,ay+12)])

    # Relay room wall map + mast.
    rx = 15 * TILE_SIZE - cam_x
    ry = 10 * TILE_SIZE - cam_y
    if _screen_visible_rect(rx, ry, 18*TILE_SIZE, 12*TILE_SIZE):
        wallmap = pygame.Rect(int(16.0*TILE_SIZE - cam_x), int(11.1*TILE_SIZE - cam_y), 210, 92)
        pygame.draw.rect(screen, (18, 30, 30), wallmap, border_radius=4)
        pygame.draw.rect(screen, (72, 108, 98), wallmap, 1, border_radius=4)
        pts = [(wallmap.x+20, wallmap.y+70), (wallmap.x+58, wallmap.y+32), (wallmap.x+102, wallmap.y+48), (wallmap.x+144, wallmap.y+20), (wallmap.x+190, wallmap.y+60)]
        pygame.draw.lines(screen, (90,175,135), False, pts, 2)
        for pt in pts:
            pygame.draw.circle(screen, (120,220,160), pt, 3)
        mast_x = int(30.0*TILE_SIZE - cam_x)
        mast_y = int(12.1*TILE_SIZE - cam_y)
        pygame.draw.line(screen, (70,86,78), (mast_x, mast_y), (mast_x, mast_y+180), 5)
        for off in (24,62,104):
            pygame.draw.line(screen, (90,116,104), (mast_x-42, mast_y+off), (mast_x+42, mast_y+off), 2)

    # Server cage mesh overlay.
    sx = 34*TILE_SIZE - cam_x
    syc = 13*TILE_SIZE - cam_y
    sw = 11*TILE_SIZE
    sh = 17*TILE_SIZE
    if _screen_visible_rect(sx, syc, sw, sh):
        mesh = pygame.Surface((int(sw), int(sh)), pygame.SRCALPHA)
        for off in range(-int(sh), int(sw), 18):
            pygame.draw.line(mesh, (95,110,105,45), (off,0), (off+int(sh), int(sh)), 1)
            pygame.draw.line(mesh, (95,110,105,30), (off,int(sh)), (off+int(sh), 0), 1)
        screen.blit(mesh, (int(sx), int(syc)))
        pygame.draw.rect(screen, (82,110,100), (int(sx+8), int(syc+8), int(sw-16), int(sh-16)), 1)



def _relay_pos():
    return (_RELAY_TILE_COL * TILE_SIZE + TILE_SIZE // 2,
            _RELAY_TILE_ROW * TILE_SIZE + TILE_SIZE // 2)


def _comms_breaker_pos():
    # East wall of the battery-backup room.
    return (29 * TILE_SIZE + TILE_SIZE // 2,
            36 * TILE_SIZE + TILE_SIZE // 2)


def _comms_auth_pos():
    # Security-booth desk terminal near the arrival airlock.
    return (13 * TILE_SIZE + TILE_SIZE // 2,
            19 * TILE_SIZE + TILE_SIZE // 2)


def _restore_comms_power():
    if getattr(STATE, "m3_comms_power_restored", False):
        return
    STATE.m3_comms_power_restored = True
    bx, by = _comms_breaker_pos()
    STATE.floating_texts.append([
        bx, by - 34, "AUXILIARY POWER RESTORED", (125, 225, 160), 120])
    try:
        audio.play("rifle_handle", volume=0.48)
        audio.play("terminal_glitch", volume=0.35)
    except Exception:
        pass
    _radio("VASILE: Power spike received. Now find a relay authorization key.",
           color=C_SYSTEM, duration=300, mark="comms_power_restored")


def _acquire_comms_auth():
    if getattr(STATE, "m3_comms_auth_acquired", False):
        return
    STATE.m3_comms_auth_acquired = True
    ax, ay = _comms_auth_pos()
    STATE.floating_texts.append([
        ax, ay - 34, "RELAY AUTHORIZATION COPIED", (130, 215, 190), 120])
    try:
        audio.play("pickup", volume=0.50)
        audio.play("type_tick", volume=0.16)
    except Exception:
        pass
    _radio("VOLKOV: Authorization is good. Get back to the relay.",
           color=C_VOLKOV, duration=280, mark="comms_auth_acquired")


def _start_comms_relay_tuning():
    if getattr(STATE, "m3_relay_tuned", False):
        return
    if getattr(STATE, "m3_relay_active", False):
        return
    if len(getattr(STATE, "enemies", [])) > 0:
        rx, ry = _relay_pos()
        STATE.floating_texts.append([rx, ry - 34, "CLEAR HOSTILES FIRST", (220, 150, 90), 90])
        _set_objective(f"Clear hostiles: {len(STATE.enemies)} guard(s) left.")
        return
    if not getattr(STATE, "m3_comms_power_restored", False):
        rx, ry = _relay_pos()
        STATE.floating_texts.append([
            rx, ry - 34, "NO POWER, CHECK BATTERY BACKUP", (220, 165, 80), 100])
        _set_objective("Restore auxiliary power in Battery Backup.")
        return
    if not getattr(STATE, "m3_comms_auth_acquired", False):
        rx, ry = _relay_pos()
        STATE.floating_texts.append([
            rx, ry - 34, "AUTHORIZATION REQUIRED", (220, 165, 80), 100])
        _set_objective("Copy relay authorization from the Security booth.")
        return
    STATE.m3_relay_active = True
    STATE.m3_relay_timer = 0
    _set_objective("Tuning relay...")
    try:
        audio.play("terminal_glitch", volume=0.45)
        audio.play("radio_static", volume=0.40)
    except Exception:
        pass


def _update_comms_relay():
    if getattr(STATE, "mission3_stage", None) != STAGE_COMMS:
        return
    if not getattr(STATE, "m3_relay_active", False):
        return

    duration = int(getattr(STATE, "m3_relay_duration", 360) or 360)
    STATE.m3_relay_timer = getattr(STATE, "m3_relay_timer", 0) + 1
    t = STATE.m3_relay_timer

    # Longer, staged tuning sequence: noisy scan -> handshake -> sync -> auth -> lock.
    # Audio ticks are sparse and diegetic so the overlay feels like a machine
    # stabilizing, not a QTE.
    if t in (34, 72, 118, 166, 218, 274, 326):
        try:
            audio.play("type_tick", volume=0.12)
            audio.play("radio_static", volume=0.20)
        except Exception:
            pass

    if t >= duration:
        STATE.m3_relay_active = False
        STATE.m3_relay_tuned = True
        STATE.m3_relay_timer = duration
        for door in getattr(STATE, "doors", []):
            if _m3d(door).archive_access:
                door.locked = False
                door.target_open = True
                door.manual_timer = 180
        _set_objective("Signal restored. Reach Archives.")
        try:
            audio.play("terminal_glitch", volume=0.50)
            audio.play("radio_chatter", volume=0.34)
        except Exception:
            pass
        _radio("VASILE: Biribel. Confirmed. I have you. Archives access is east.",
               color=C_SYSTEM, duration=420, mark="comms_relay_restored")


def _draw_comms_relay_prompt(cam_x, cam_y):
    if getattr(STATE, "mission3_stage", None) != STAGE_COMMS:
        return
    if getattr(STATE, "m3_relay_active", False):
        return
    rx, ry = _relay_pos()
    sx, sy = rx - cam_x, ry - cam_y
    if not (-80 < sx < WIDTH + 80 and -80 < sy < HEIGHT + 80):
        return
    if getattr(STATE, "m3_relay_tuned", False):
        prompt = "RELAY ONLINE"
        col = (120, 220, 160)
    elif not getattr(STATE, "m3_comms_power_restored", False):
        prompt = "RELAY OFFLINE // NO POWER"
        col = (165, 95, 65)
    elif not getattr(STATE, "m3_comms_auth_acquired", False):
        prompt = "RELAY LOCKED // AUTH REQUIRED"
        col = (190, 140, 72)
    elif STATE.player and math.hypot(STATE.player.rect.centerx - rx, STATE.player.rect.centery - ry) <= 92:
        prompt = "[E] ESTABLISH KRAP LINK"
        col = (145, 220, 190)
    else:
        prompt = "RELAY READY"
        col = (90, 155, 125)
    a = int(175 + math.sin(_now_s() * 4) * 50)
    label = font_terminal_small.render(prompt, True, col)
    label.set_alpha(a)
    screen.blit(label, (int(sx - label.get_width() // 2), int(sy - 58)))
    # Soft marker ring.
    ring = pygame.Surface((72, 72), pygame.SRCALPHA)
    pygame.draw.circle(ring, (*col, 28), (36, 36), 30)
    pygame.draw.circle(ring, (*col, a), (36, 36), 24, 1)
    screen.blit(ring, (int(sx - 36), int(sy - 36)))


def _draw_comms_dynamic_atmosphere(cam_x, cam_y):
    """State-driven lighting and machinery feedback for the Comms Wing."""
    timer = getattr(STATE, "m3_comms_ambience_timer", 0)
    powered = getattr(STATE, "m3_comms_power_restored", False)

    if not powered:
        # Emergency power: slow red rotating-beacon wash with occasional hard
        # fluorescent dropouts. Kept under actors/HUD in the draw order.
        pulse = 0.5 + 0.5 * math.sin(timer * 0.055)
        wash = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        wash.fill((105, 8, 6, int(12 + 25 * pulse)))
        screen.blit(wash, (0, 0))
        if timer % 150 in range(0, 5):
            dropout = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
            dropout.fill((0, 0, 0, 82))
            screen.blit(dropout, (0, 0))
    else:
        # Restored green status glow centered on the relay room.
        rx, ry = _relay_pos()
        sx, sy = int(rx - cam_x), int(ry - cam_y)
        glow = pygame.Surface((220, 220), pygame.SRCALPHA)
        pygame.draw.circle(glow, (4, 17, 10, 255), (110, 110), 104)
        pygame.draw.circle(glow, (11, 36, 22, 255), (110, 110), 58)
        screen.blit(glow, (sx - 110, sy - 110), special_flags=pygame.BLEND_RGBA_ADD)


def _draw_comms_system_prompts(cam_x, cam_y):
    """World-space prompts for the power/auth/relay objective chain."""
    objectives = [
        (_comms_breaker_pos(),
         "POWER ONLINE" if getattr(STATE, "m3_comms_power_restored", False)
         else "[E] RESTORE AUX POWER",
         getattr(STATE, "m3_comms_power_restored", False)),
        (_comms_auth_pos(),
         "AUTH COPIED" if getattr(STATE, "m3_comms_auth_acquired", False)
         else "[E] COPY RELAY AUTH",
         getattr(STATE, "m3_comms_auth_acquired", False)),
    ]
    for (wx, wy), text, complete in objectives:
        sx, sy = wx - cam_x, wy - cam_y
        if not (-90 < sx < WIDTH + 90 and -90 < sy < HEIGHT + 90):
            continue
        near = bool(STATE.player) and math.hypot(
            STATE.player.rect.centerx - wx,
            STATE.player.rect.centery - wy) <= 78
        col = (105, 210, 150) if complete else ((225, 184, 92) if near else (135, 118, 76))
        alpha = int(170 + 55 * math.sin(_now_s() * 4.0)) if near else 155
        # Distance falloff: a station you are nowhere near stops shouting.
        dist = math.hypot(STATE.player.rect.centerx - wx,
                          STATE.player.rect.centery - wy) if STATE.player else 9999.0
        fall = 1.0 if near else max(0.22, min(1.0, 1.0 - (dist - 240.0) / 520.0))
        label = font_terminal_small.render(text, True, col)
        label.set_alpha(max(40, min(230, int(alpha * fall))))
        screen.blit(label, (int(sx - label.get_width() // 2), int(sy - 47)))
        if near or fall > 0.45:
            pygame.draw.circle(screen, col, (int(sx), int(sy)), 22, 2 if near else 1)

    # Diegetic archive-lock status beside the east portal.
    wx = 44 * TILE_SIZE + TILE_SIZE // 2
    wy = 24 * TILE_SIZE + TILE_SIZE // 2
    sx, sy = wx - cam_x, wy - cam_y
    if -90 < sx < WIDTH + 90 and -90 < sy < HEIGHT + 90:
        unlocked = getattr(STATE, "m3_relay_tuned", False)
        text = "ARCHIVE LINK OPEN" if unlocked else "ARCHIVE LINK SEALED"
        col = (110, 220, 155) if unlocked else (210, 72, 55)
        label = font_terminal_small.render(text, True, col)
        # Sit above the green "ARCHIVES ->" stencil (drawn at ay - 45) so the
        # two world labels never overprint each other at the portal.
        screen.blit(label, (int(sx - label.get_width() // 2), int(sy - 68)))


def _draw_comms_relay_overlay():
    if not getattr(STATE, "m3_relay_active", False):
        return
    t = getattr(STATE, "m3_relay_timer", 0)
    duration = int(getattr(STATE, "m3_relay_duration", 360) or 360)
    progress = max(0.0, min(1.0, t / float(duration)))

    panel_w, panel_h = 650, 280
    panel_x = WIDTH // 2 - panel_w // 2
    panel_y = HEIGHT // 2 - panel_h // 2

    dim = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
    dim.fill((0, 0, 0, 155))
    screen.blit(dim, (0, 0))

    panel = pygame.Surface((panel_w, panel_h), pygame.SRCALPHA)
    pygame.draw.rect(panel, (4, 10, 10, 242), panel.get_rect(), border_radius=7)
    pygame.draw.rect(panel, (74, 136, 116, 220), panel.get_rect(), 2, border_radius=7)
    pygame.draw.line(panel, (26, 48, 44, 220), (0, 42), (panel_w, 42), 1)

    title = font_terminal.render(_T("m3.krap_relay_tuner"), True, (142, 235, 195))
    panel.blit(title, (20, 13))
    sub = font_terminal_small.render(_T("m3.stabilization_center_service_rel"), True, (82, 126, 110))
    panel.blit(sub, (panel_w - sub.get_width() - 18, 18))

    # Main waveform scope.
    scope = pygame.Rect(34, 62, 390, 126)
    pygame.draw.rect(panel, (2, 7, 7), scope, border_radius=4)
    pygame.draw.rect(panel, (48, 90, 78), scope, 1, border_radius=4)
    # Scope grid.
    for gx in range(scope.x + 32, scope.right, 32):
        pygame.draw.line(panel, (12, 28, 26), (gx, scope.y + 4), (gx, scope.bottom - 4), 1)
    for gy in range(scope.y + 24, scope.bottom, 24):
        pygame.draw.line(panel, (12, 28, 26), (scope.x + 4, gy), (scope.right - 4, gy), 1)

    # Target center line and unstable waveform. As progress rises, amplitude and
    # phase jitter collapse toward a clean signal.
    pygame.draw.line(panel, (38, 70, 60), (scope.x + 6, scope.centery), (scope.right - 6, scope.centery), 1)
    pts = []
    phase_jitter = math.sin(t * 0.041) * (1.0 - progress) * 14
    amp = 33 * (1.0 - progress) + 7
    for i in range(scope.w - 14):
        x = scope.x + 7 + i
        harmonic = math.sin(i * 0.048 + t * 0.080 + phase_jitter)
        noise = math.sin(i * 0.19 + t * 0.15) * (1.0 - progress) * 10
        y = scope.centery + harmonic * amp + noise
        pts.append((x, y))
    if len(pts) > 1:
        pygame.draw.lines(panel, (112, 245, 174), False, pts, 2)
    # Secondary ghost/noise trace early on.
    if progress < 0.72:
        pts2 = []
        for i in range(scope.w - 14):
            x = scope.x + 7 + i
            y = scope.centery + math.sin(i * 0.072 - t * 0.11) * (amp * 0.55) + math.sin(i * 0.31) * (12 * (1-progress))
            pts2.append((x, y))
        if len(pts2) > 1:
            pygame.draw.lines(panel, (50, 120, 102, 80), False, pts2, 1)

    # Right side signal/buffer meter.
    meter = pygame.Rect(452, 62, 160, 126)
    pygame.draw.rect(panel, (3, 8, 8), meter, border_radius=4)
    pygame.draw.rect(panel, (48, 90, 78), meter, 1, border_radius=4)
    meter_title = font_terminal_small.render(_T("m3.signal_lock"), True, (116, 170, 145))
    panel.blit(meter_title, (meter.centerx - meter_title.get_width() // 2, meter.y + 9))
    for i in range(8):
        bh = 8 + i * 6
        bx = meter.x + 25 + i * 14
        by = meter.bottom - 20 - bh
        locked = progress >= (i + 1) / 8.8
        col = (90, 225, 145) if locked else (22, 38, 35)
        pygame.draw.rect(panel, col, (bx, by, 8, bh), border_radius=2)
        pygame.draw.rect(panel, (70, 100, 86), (bx, by, 8, bh), 1, border_radius=2)

    # Step boxes - longer sequence than the old three locks.
    steps = [
        ("SCAN", 0.16),
        ("HANDSHAKE", 0.34),
        ("SYNC", 0.54),
        ("AUTH", 0.74),
        ("LOCK", 0.94),
    ]
    base_y = 205
    for idx, (label, threshold) in enumerate(steps):
        bx = 34 + idx * 116
        by = base_y
        complete = progress >= threshold
        active = (idx == 0 and progress < threshold) or (idx > 0 and progress >= steps[idx-1][1] and progress < threshold)
        bg = (12, 22, 20) if not complete else (10, 42, 28)
        border = (80, 220, 130) if complete else ((160, 150, 80) if active else (64, 76, 70))
        pygame.draw.rect(panel, bg, (bx, by, 92, 34), border_radius=4)
        pygame.draw.rect(panel, border, (bx, by, 92, 34), 1, border_radius=4)
        txt = font_terminal_small.render(label, True, (110, 240, 160) if complete else ((210, 190, 90) if active else (110, 125, 118)))
        panel.blit(txt, (bx + 46 - txt.get_width() // 2, by + 10))

    # Progress line.
    pygame.draw.rect(panel, (15, 24, 22), (34, 255, panel_w - 68, 9), border_radius=3)
    pygame.draw.rect(panel, (92, 220, 145), (34, 255, int((panel_w - 68) * progress), 9), border_radius=3)
    pct = font_terminal_small.render(_T("m3.progress_pct", pct="{:03d}".format(int(progress * 100))), True, (120, 200, 160))
    panel.blit(pct, (panel_w - pct.get_width() - 36, 240))

    # Warning/hold hint.
    hint = "HOLD POSITION, RELAY CARRIER LOCKING"
    if progress > 0.92:
        hint = "SIGNAL STABLE, KRAP HANDSHAKE COMPLETE"
    hsurf = font_terminal_small.render(hint, True, (120, 150, 132))
    panel.blit(hsurf, (34, 240))

    screen.blit(panel, (panel_x, panel_y))



def _draw_m3_enemy_type_overlay(surface, enemy, cam_x, cam_y):
    """Mission 3 enemy visual differentiation.

    Draw these as equipment layers on top of the shared Enemy.draw() silhouette,
    not as labels/UI. The goal is: same game style, distinct roles.
    """
    et = (_m3l(enemy).kind or "guard")
    if et == "guard" or enemy.hp <= 0:
        return
    x = enemy.rect.centerx - cam_x
    y = enemy.rect.centery - cam_y
    a = enemy.angle
    dx, dy = math.cos(a), math.sin(a)
    px, py = -dy, dx

    def _rot_box(cx, cy, length, half_w, col, outline=(10, 10, 10), offset=0.0):
        ax = cx - dx * length * 0.5 + px * offset
        ay = cy - dy * length * 0.5 + py * offset
        bx = cx + dx * length * 0.5 + px * offset
        by = cy + dy * length * 0.5 + py * offset
        poly = [(ax + px*half_w, ay + py*half_w), (ax - px*half_w, ay - py*half_w),
                (bx - px*half_w, by - py*half_w), (bx + px*half_w, by + py*half_w)]
        pygame.draw.polygon(surface, outline, poly)
        inner = [(ax + px*(half_w-1), ay + py*(half_w-1)), (ax - px*(half_w-1), ay - py*(half_w-1)),
                 (bx - px*(half_w-1), by - py*(half_w-1)), (bx + px*(half_w-1), by + py*(half_w-1))]
        pygame.draw.polygon(surface, col, inner)
        return poly

    if et == "breacher":
        # Armored vest + compact weapon, all in-body and in same palette.
        vest = [(x - 9, y - 11), (x + 9, y - 11), (x + 11, y + 8), (x, y + 13), (x - 11, y + 8)]
        pygame.draw.polygon(surface, (12, 14, 14), vest)
        pygame.draw.polygon(surface, (40, 45, 40), [(x - 7, y - 9), (x + 7, y - 9), (x + 8, y + 6), (x, y + 10), (x - 8, y + 6)])
        # Red shoulder tabs, subtle not UI text.
        pygame.draw.line(surface, (150, 55, 42), (x - 10, y - 6), (x - 4, y - 9), 3)
        pygame.draw.line(surface, (150, 55, 42), (x + 10, y - 6), (x + 4, y - 9), 3)
        # Compact SMG barrel overlay aligned with enemy aim.
        _rot_box(x + dx*24, y + dy*24, 26, 2.2, (34, 31, 25))
        pygame.draw.circle(surface, (8, 8, 8), (int(x + dx*38), int(y + dy*38)), 2)
        # Visor/goggles on head.
        hx, hy = x + dx*2, y + dy*2
        pygame.draw.line(surface, (20, 18, 16), (hx - px*5, hy - py*5), (hx + px*5, hy + py*5), 3)

    elif et == "shield":
        # Riot shield as the silhouette feature. No floating label.
        cx = x + dx * 20
        cy = y + dy * 20
        hw, hh = 13, 23
        shield = [
            (cx + px*hw - dx*hh, cy + py*hw - dy*hh),
            (cx - px*hw - dx*hh, cy - py*hw - dy*hh),
            (cx - px*hw + dx*hh, cy - py*hw + dy*hh),
            (cx + px*hw + dx*hh, cy + py*hw + dy*hh),
        ]
        pygame.draw.polygon(surface, (8, 12, 14), shield)
        inner = [
            (cx + px*(hw-2) - dx*(hh-2), cy + py*(hw-2) - dy*(hh-2)),
            (cx - px*(hw-2) - dx*(hh-2), cy - py*(hw-2) - dy*(hh-2)),
            (cx - px*(hw-2) + dx*(hh-2), cy - py*(hw-2) + dy*(hh-2)),
            (cx + px*(hw-2) + dx*(hh-2), cy + py*(hw-2) + dy*(hh-2)),
        ]
        pygame.draw.polygon(surface, (34, 44, 46), inner)
        pygame.draw.polygon(surface, (110, 130, 124), shield, 2)
        # Viewport slit.
        pygame.draw.line(surface, (132, 164, 154),
                         (cx - px*8 - dx*8, cy - py*8 - dy*8),
                         (cx + px*8 - dx*8, cy + py*8 - dy*8), 3)
        # Shield center stripe.
        pygame.draw.line(surface, (70, 82, 80), (cx - dx*15, cy - dy*15), (cx + dx*17, cy + dy*17), 1)

    elif et == "technician":
        # Backpack/radio pack + headset, but still same human silhouette.
        pack_cx = x - dx*10
        pack_cy = y - dy*10
        _rot_box(pack_cx, pack_cy, 18, 7, (20, 40, 38), offset=0)
        pygame.draw.rect(surface, (70, 145, 120), (int(pack_cx-3), int(pack_cy-3), 6, 6))
        # Antenna/back cable.
        pygame.draw.line(surface, (88, 170, 135), (int(pack_cx), int(pack_cy-8)), (int(pack_cx - px*5 - dx*12), int(pack_cy - py*5 - dy*12)), 2)
        # Headset line around head.
        hx, hy = x + dx*2, y + dy*2
        pygame.draw.arc(surface, (80, 190, 140), (int(hx-9), int(hy-9), 18, 18), a-1.9, a+1.9, 2)
        pygame.draw.circle(surface, (80, 220, 140), (int(hx + px*8), int(hy + py*8)), 2)
        # Small tablet/satchel.
        tab = pygame.Rect(int(x + px*12 - 5), int(y + py*12 - 4), 12, 8)
        pygame.draw.rect(surface, (32, 54, 50), tab, border_radius=2)
        pygame.draw.rect(surface, (86, 140, 120), tab, 1, border_radius=2)

    elif et == "marksman":
        # Long rifle and scope integrated with base arms.
        start = (x + dx*13, y + dy*13)
        end = (x + dx*46, y + dy*46)
        pygame.draw.line(surface, (8, 8, 8), start, end, 6)
        pygame.draw.line(surface, (42, 40, 34), start, end, 4)
        pygame.draw.line(surface, (96, 92, 76), (start[0]-px*1.5, start[1]-py*1.5), (end[0]-px*1.5, end[1]-py*1.5), 1)
        # Scope and muzzle.
        scope = (x + dx*24 - px*3, y + dy*24 - py*3)
        pygame.draw.circle(surface, (12, 16, 16), (int(scope[0]), int(scope[1])), 5)
        pygame.draw.circle(surface, (92, 150, 128), (int(scope[0]), int(scope[1])), 2)
        pygame.draw.circle(surface, (5, 5, 5), (int(end[0]), int(end[1])), 2)
        # Helmet/visor stripe.
        hx, hy = x + dx*2, y + dy*2
        pygame.draw.arc(surface, (18, 18, 16), (int(hx-10), int(hy-11), 20, 16), math.pi, math.tau, 4)
        pygame.draw.line(surface, (120, 95, 60), (hx - px*6, hy - py*6), (hx + px*6, hy + py*6), 2)




def _draw_pillar_cap(cam_x, cam_y, col, row, kind="slate"):
    """Full-tile architectural pillar cap over a 'B' barrier tile.

    'B' tiles render through the w_B_* hazard-hatch sprite (core/artpack.py).
    Where maps use them as structural pillars (Archives atrium, KO lobby
    cover pockets) the bare hatch read as a floating crate/pad, so a proper
    cap is drawn over the whole tile instead of a small top.
    """
    x = int(col * TILE_SIZE - cam_x)
    y = int(row * TILE_SIZE - cam_y)
    if not _screen_visible_rect(x - TILE_SIZE, y - TILE_SIZE, TILE_SIZE * 3, TILE_SIZE * 3):
        return
    if kind == "slate":
        fill, edge, bevel, boss = (34, 30, 42), (70, 60, 95), (52, 46, 66), (24, 21, 30)
    else:
        fill, edge, bevel, boss = (52, 50, 48), (82, 78, 72), (66, 63, 58), (34, 32, 30)
    render_util.soft_shadow(screen, (x + 4, y + TILE_SIZE - 10, TILE_SIZE - 8, 12), 90)
    pygame.draw.rect(screen, fill, (x + 2, y + 2, TILE_SIZE - 4, TILE_SIZE - 4), border_radius=4)
    pygame.draw.rect(screen, edge, (x + 2, y + 2, TILE_SIZE - 4, TILE_SIZE - 4), 2, border_radius=4)
    pygame.draw.rect(screen, bevel, (x + 8, y + 8, TILE_SIZE - 16, TILE_SIZE - 16), 1, border_radius=3)
    pygame.draw.rect(screen, boss, (x + 22, y + 22, 20, 20), border_radius=2)
    pygame.draw.line(screen, bevel, (x + 8, y + 10), (x + TILE_SIZE - 10, y + 10), 1)


def _draw_vestibule_laser_cone(cx, cy, cx_t, t_sec, vx0, vy0, vw, vh):
    """One sweeping dome-camera laser cone of the archives vault vestibule."""
    sweep_angle = math.sin(t_sec * 1.5 + (cx_t * 0.7)) * 0.35
    laser_w = 48
    laser_h = 96
    poly_laser = [
        (cx, cy + 12),
        (cx - laser_w + int(sweep_angle * 35), cy + laser_h),
        (cx + laser_w + int(sweep_angle * 35), cy + laser_h),
    ]
    laser_surf = pygame.Surface((vw, vh), pygame.SRCALPHA)
    rel_pts = [(p[0] - vx0, p[1] - vy0) for p in poly_laser]
    pygame.draw.polygon(laser_surf, (220, 50, 40, 22), rel_pts)
    pygame.draw.polygon(laser_surf, (255, 100, 80, 50), rel_pts, 1)
    screen.blit(laser_surf, (vx0, vy0))


def _draw_archives_wing_live(cam_x, cam_y):
    """Per-frame part of the archives dressing (everything the static bake skips): vestibule gate
    LEDs, dome-camera laser cones + recording LEDs and the keypad biometric laser. Positions mirror
    the static painter; drawn right over the baked layer."""
    vx0 = 20 * TILE_SIZE - cam_x
    vy0 = 6 * TILE_SIZE - cam_y
    vw, vh = 17 * TILE_SIZE, 7 * TILE_SIZE
    if not _screen_visible_rect(vx0, vy0, vw, vh):
        return
    t_sec = _now_ms() / 1000.0
    unlocked = getattr(STATE, "m3_maru_contacted", False)
    gate_y = int(11.2 * TILE_SIZE - cam_y)
    for px_gate in (int(23.2 * TILE_SIZE - cam_x), int(25.8 * TILE_SIZE - cam_x)):
        pill = pygame.Rect(px_gate - 8, gate_y - 12, 16, 28)
        led_col = (80, 220, 120) if unlocked else ((220, 60, 50) if int(t_sec * 3) % 2 == 0 else (120, 30, 25))
        pygame.draw.circle(screen, led_col, (pill.centerx, pill.y + 6), 3)
        pygame.draw.circle(screen, (220, 230, 255), (pill.centerx - 1, pill.y + 5), 1)
    for cx_t in (23, 30):
        cx = int(cx_t * TILE_SIZE - cam_x)
        cy = int(6.4 * TILE_SIZE - cam_y)
        _draw_vestibule_laser_cone(cx, cy, cx_t, t_sec, vx0, vy0, vw, vh)
        rec_led = (240, 40, 40) if int(t_sec * 2.5) % 2 == 0 else (120, 20, 20)
        pygame.draw.circle(screen, rec_led, (cx + 5, cy + 8), 2)
    pad = pygame.Rect(int(35.2 * TILE_SIZE - cam_x), int(8.1 * TILE_SIZE - cam_y), 26, 38)
    bio = pygame.Rect(pad.x + 4, pad.y + 31, 18, 4)
    scr_col = (80, 230, 140) if unlocked else (240, 80, 70)
    bio_laser = scr_col if int(t_sec * 4) % 2 == 0 else (100, 100, 100)
    pygame.draw.line(screen, bio_laser, (bio.x + 2, bio.centery), (bio.right - 2, bio.centery), 1)


def _draw_archives_wing_details(cam_x, cam_y):
    """Art pass for the redesigned vertical Archives stack."""
    # ── Elevator lobby (south) ──
    lx = 18 * TILE_SIZE - cam_x
    ly = 38 * TILE_SIZE - cam_y
    lw, lh = 13 * TILE_SIZE, 8 * TILE_SIZE
    if _screen_visible_rect(lx, ly, lw, lh):
        # Sealed elevator doors.
        for ex in (20.5, 26.5):
            door = pygame.Rect(int(ex * TILE_SIZE - cam_x - 28),
                               int(44 * TILE_SIZE - cam_y - 40), 56, 80)
            pygame.draw.rect(screen, (10, 10, 14), door.inflate(8, 8), border_radius=3)
            pygame.draw.rect(screen, (50, 48, 70), door, border_radius=2)
            pygame.draw.rect(screen, (130, 120, 170), door, 2, border_radius=2)
            pygame.draw.line(screen, (90, 85, 120),
                             (door.centerx, door.top + 6),
                             (door.centerx, door.bottom - 6), 2)
        tag = font_terminal_small.render(_T("m3.service_elevator_sealed"), True, (140, 125, 180))
        tag.set_alpha(180)
        screen.blit(tag, (int(24 * TILE_SIZE - cam_x - tag.get_width() // 2),
                          int(43.1 * TILE_SIZE - cam_y)))
        stencil = font_terminal_small.render(_T("m3.arrival_lobby"), True, (120, 110, 150))
        stencil.set_alpha(150)
        screen.blit(stencil, (int(24 * TILE_SIZE - cam_x - stencil.get_width() // 2),
                              int(39.2 * TILE_SIZE - cam_y)))

    # ── Atrium (vertical spine) ──
    ax = 20 * TILE_SIZE - cam_x
    ay = 12 * TILE_SIZE - cam_y
    aw, ah = 9 * TILE_SIZE, 27 * TILE_SIZE
    if _screen_visible_rect(ax, ay, aw, ah):
        # Floor stripe down the atrium center.
        for yy in range(14, 38, 2):
            stripe = pygame.Rect(int(23.2 * TILE_SIZE - cam_x),
                                 int(yy * TILE_SIZE - cam_y),
                                 int(2.6 * TILE_SIZE), 10)
            pygame.draw.rect(screen, (40, 34, 55), stripe)
        # Overhead lamp fixtures (hard geometry, no soft blobs).
        for yy in (16, 22, 28, 34):
            cx = int(24 * TILE_SIZE - cam_x)
            cy = int(yy * TILE_SIZE - cam_y)
            pygame.draw.rect(screen, (55, 48, 70), (cx - 34, cy - 8, 68, 8), border_radius=2)
            pygame.draw.rect(screen, (140, 125, 170), (cx - 30, cy - 5, 60, 3), border_radius=1)
            pygame.draw.line(screen, (90, 80, 120), (cx - 20, cy + 3), (cx + 20, cy + 3), 1)
        label = font_terminal.render(_T("m3.atrium"), True, (160, 140, 200))
        label.set_alpha(160)
        screen.blit(label, (int(24 * TILE_SIZE - cam_x - label.get_width() // 2),
                            int(15 * TILE_SIZE - cam_y)))
        # Pillar caps: full-tile, so the 'B' hazard hatch underneath never shows.
        for py_t, px_t in ((22, 22), (22, 26), (30, 22), (30, 26)):
            _draw_pillar_cap(cam_x, cam_y, px_t, py_t, kind="slate")

    # ── West catalog stacks ──
    sx0 = 4 * TILE_SIZE - cam_x
    sy0 = 18 * TILE_SIZE - cam_y
    sw, sh = 17 * TILE_SIZE, 19 * TILE_SIZE
    if _screen_visible_rect(sx0, sy0, sw, sh):
        title = font_terminal_small.render(_T("m3.catalog_stacks"), True, (130, 150, 150))
        title.set_alpha(170)
        screen.blit(title, (int(12 * TILE_SIZE - cam_x - title.get_width() // 2),
                            int(19.2 * TILE_SIZE - cam_y)))
        # Book spines on aisle walls.
        for aisle_x in (7, 10, 13, 16):
            for yy in range(20, 35, 3):
                if yy in (24, 25, 30, 31):
                    continue
                bx = int(aisle_x * TILE_SIZE - cam_x)
                by = int(yy * TILE_SIZE - cam_y)
                spr = artpack.get("shelf_%s" % "abc"[(aisle_x + yy) % 3])
                if spr is not None:
                    screen.blit(spr, (bx, by))
                    continue
                for ty in range(3):
                    for i in range(5):
                        col = ((90, 50, 70), (50, 70, 90), (70, 60, 40),
                               (60, 40, 80), (40, 55, 50))[(yy + ty + i) % 5]
                        pygame.draw.rect(screen, col,
                                         (bx + 8 + i * 10,
                                          by + ty * TILE_SIZE + 12, 7, 36))

    # ── Maru clerk office (hero set-piece) ──
    mx0 = 6 * TILE_SIZE - cam_x
    my0 = 8 * TILE_SIZE - cam_y
    mw, mh = 11 * TILE_SIZE, 11 * TILE_SIZE
    if _screen_visible_rect(mx0, my0, mw, mh):
        # Carpet / office floor plate.
        floor = pygame.Surface((int(mw - 16), int(mh - 16)), pygame.SRCALPHA)
        floor.fill((32, 26, 42, 55))
        for yy in range(0, floor.get_height(), 8):
            pygame.draw.line(floor, (40, 32, 52, 40), (0, yy), (floor.get_width(), yy), 1)
        screen.blit(floor, (int(mx0 + 8), int(my0 + 8)))

        # Brass wall plaque.
        plq = artpack.get("plaque")
        label = font_terminal_small.render(_T("m3.clerk_07_restricted"), True, (230, 200, 120))
        pw = (plq.get_width() if plq is not None else label.get_width() + 20)
        plaque = pygame.Rect(int(11 * TILE_SIZE - cam_x - pw // 2),
                             int(8.35 * TILE_SIZE - cam_y), pw, 22)
        if plq is not None:
            screen.blit(plq, (plaque.x, plaque.y - 1))
        else:
            pygame.draw.rect(screen, (48, 38, 22), plaque, border_radius=2)
            pygame.draw.rect(screen, (180, 150, 70), plaque, 1, border_radius=2)
            screen.blit(label, (plaque.centerx - label.get_width() // 2, plaque.y + 4))

        # Back wall shelves packed with dossiers.
        for col_i, fx in enumerate((7.2, 8.6, 13.4, 14.8)):
            shelf_x = int(fx * TILE_SIZE - cam_x)
            shelf_y = int(9.3 * TILE_SIZE - cam_y)
            cab_spr = artpack.get("cab_dossier")
            if cab_spr is not None:
                screen.blit(cab_spr, (shelf_x - 18, shelf_y))
            else:
                # Cabinet body
                cab = pygame.Rect(shelf_x - 18, shelf_y, 40, 110)
                pygame.draw.rect(screen, (28, 24, 34), cab, border_radius=2)
                pygame.draw.rect(screen, (70, 58, 88), cab, 1, border_radius=2)
                for row in range(5):
                    ry = shelf_y + 8 + row * 20
                    pygame.draw.line(screen, (50, 42, 62), (cab.x + 3, ry), (cab.right - 3, ry), 1)
                    for b in range(4):
                        bc = ((90, 50, 70), (50, 70, 100), (70, 60, 40), (60, 40, 90))[(row + b + col_i) % 4]
                        pygame.draw.rect(screen, bc, (cab.x + 5 + b * 8, ry - 14, 6, 13))
                # Drawer pulls
                pygame.draw.circle(screen, (160, 140, 90), (cab.centerx, cab.bottom - 12), 2)

        # Cork notice board on north wall.
        board = pygame.Rect(int(11 * TILE_SIZE - cam_x - 50),
                            int(9.5 * TILE_SIZE - cam_y), 100, 48)
        cork_spr = artpack.get("cork")
        if cork_spr is not None:
            screen.blit(cork_spr, (board.x, board.y))
            board = pygame.Rect(-9999, -9999, 100, 48)
        else:
            pygame.draw.rect(screen, (92, 68, 40), board, border_radius=2)
            pygame.draw.rect(screen, (140, 110, 70), board, 1, border_radius=2)
        for i, (px, py, pw, ph, pc) in enumerate((
            (6, 6, 28, 16, (220, 210, 180)),
            (38, 8, 24, 14, (200, 190, 160)),
            (66, 6, 26, 18, (210, 200, 170)),
            (12, 26, 32, 14, (190, 185, 160)),
            (50, 28, 36, 12, (200, 195, 170)),
        )):
            pygame.draw.rect(screen, pc, (board.x + px, board.y + py, pw, ph))
            pygame.draw.circle(screen, (160, 40, 40), (board.x + px + 3, board.y + py + 3), 2)

        # Main dead-drop terminal - heavy console, dual screens, keyboard.
        term_cx = int(11 * TILE_SIZE - cam_x)
        term_cy = int(12.1 * TILE_SIZE - cam_y)
        # Desk slab
        desk = pygame.Rect(term_cx - 70, term_cy - 18, 140, 58)
        pygame.draw.rect(screen, (10, 10, 14), (desk.x - 4, desk.y + 40, desk.w + 8, 14), border_radius=2)
        pygame.draw.rect(screen, (36, 30, 48), desk, border_radius=3)
        pygame.draw.rect(screen, (110, 90, 150), desk, 2, border_radius=3)
        # Desk edge highlight
        pygame.draw.line(screen, (70, 58, 90), (desk.x + 6, desk.y + 4), (desk.right - 6, desk.y + 4), 1)
        # Twin CRT housings
        live = not getattr(STATE, "m3_maru_contacted", False)
        bezel = (180, 150, 230) if live else (90, 190, 140)
        for ox, w in ((-58, 54), (4, 54)):
            mon = pygame.Rect(term_cx + ox, term_cy - 10, w, 34)
            pygame.draw.rect(screen, (18, 16, 24), mon.inflate(6, 6), border_radius=2)
            pygame.draw.rect(screen, (8, 10, 12), mon, border_radius=2)
            pygame.draw.rect(screen, bezel, mon, 1, border_radius=2)
            # phosphor content (per-frame; skipped while baking static chunks)
            if live and not staticlayer.baking():
                fr = int(_now_s() * 7 + ox) % 4
                for i in range(4):
                    wl = 12 + (i * 7 + fr * 5) % 28
                    pygame.draw.line(screen, (90, 70, 130),
                                     (mon.x + 6, mon.y + 8 + i * 6),
                                     (mon.x + 6 + wl, mon.y + 8 + i * 6), 1)
                pygame.draw.circle(screen, bezel, (mon.right - 7, mon.y + 7), 2)
                if artpack.enabled():
                    lighting.buffer().light(mon.centerx - cam_x, mon.centery - cam_y,
                                            90, (150, 110, 200), 0.30)
            else:
                # Standby phosphor: dim glyph rows + power dot. (A literal
                # "OK" string read as placeholder debug buttons top-down.)
                for i in range(3):
                    wl = 10 + (i * 9) % 18
                    pygame.draw.line(screen, (60, 90, 75),
                                     (mon.x + 6, mon.y + 8 + i * 6),
                                     (mon.x + 6 + wl, mon.y + 8 + i * 6), 1)
                pygame.draw.circle(screen, (70, 90, 80), (mon.right - 7, mon.y + 7), 2)
        # Keyboard
        kb = pygame.Rect(term_cx - 40, term_cy + 22, 80, 14)
        pygame.draw.rect(screen, (22, 20, 28), kb, border_radius=2)
        for i in range(10):
            pygame.draw.rect(screen, (50, 48, 58), (kb.x + 4 + i * 7, kb.y + 3, 5, 4))
        # Side tower PC
        tower = pygame.Rect(term_cx + 62, term_cy - 8, 18, 42)
        pygame.draw.rect(screen, (24, 22, 30), tower, border_radius=2)
        pygame.draw.rect(screen, (80, 70, 100), tower, 1, border_radius=2)
        pygame.draw.circle(screen, bezel, (tower.centerx, tower.y + 10), 2)
        for i in range(3):
            pygame.draw.line(screen, (45, 40, 55), (tower.x + 3, tower.y + 18 + i * 6),
                             (tower.right - 3, tower.y + 18 + i * 6), 1)
        # Desk lamp
        pygame.draw.line(screen, (90, 85, 70), (term_cx - 62, term_cy + 8),
                         (term_cx - 50, term_cy - 22), 2)
        pygame.draw.polygon(screen, (200, 180, 100),
                            [(term_cx - 56, term_cy - 24),
                             (term_cx - 44, term_cy - 20),
                             (term_cx - 48, term_cy - 14),
                             (term_cx - 58, term_cy - 16)])
        # Floor cable
        pygame.draw.lines(screen, (40, 36, 48), False, [
            (term_cx + 20, term_cy + 40),
            (term_cx + 40, term_cy + 55),
            (term_cx + 70, term_cy + 60),
        ], 2)
        # No floor caption here - the wall plaque + near-prompt cover naming
        # without stacking a third label on the desk.

    # ── East research cubicles ──
    rx0 = 28 * TILE_SIZE - cam_x
    ry0 = 18 * TILE_SIZE - cam_y
    rw, rh = 16 * TILE_SIZE, 19 * TILE_SIZE
    if _screen_visible_rect(rx0, ry0, rw, rh):
        label = font_terminal_small.render(_T("m3.research"), True, (150, 145, 120))
        label.set_alpha(170)
        screen.blit(label, (int(35.5 * TILE_SIZE - cam_x - label.get_width() // 2),
                            int(19.2 * TILE_SIZE - cam_y)))
        for cx_t, cy_t in ((34, 22), (38, 22), (34, 32), (38, 32)):
            desk = pygame.Rect(int(cx_t * TILE_SIZE - cam_x - 35),
                               int(cy_t * TILE_SIZE - cam_y - 20), 70, 40)
            pygame.draw.rect(screen, (36, 34, 30), desk, border_radius=3)
            pygame.draw.rect(screen, (90, 85, 70), desk, 1, border_radius=3)
            pygame.draw.rect(screen, (20, 30, 28), (desk.x + 10, desk.y + 8, 28, 18), border_radius=1)
            pygame.draw.circle(screen, (80, 200, 120), (desk.right - 14, desk.y + 14), 3)

    # ── Vault vestibule (security antechamber) ──
    vx0 = 20 * TILE_SIZE - cam_x
    vy0 = 6 * TILE_SIZE - cam_y
    vw, vh = 17 * TILE_SIZE, 7 * TILE_SIZE
    if _screen_visible_rect(vx0, vy0, vw, vh):
        t_sec = _now_ms() / 1000.0
        unlocked = getattr(STATE, "m3_maru_contacted", False)

        # 1. High-security two-tone slate marble floor with bevel tiles
        for ty in range(7, 12):
            for tx in range(21, 36):
                fx = int(tx * TILE_SIZE - cam_x)
                fy = int(ty * TILE_SIZE - cam_y)
                is_alt = (tx + ty) % 2 == 0
                bg_col = (42, 38, 34) if is_alt else (28, 25, 22)
                bevel_col = (62, 56, 50) if is_alt else (42, 38, 33)
                shadow_col = (18, 16, 14)

                pygame.draw.rect(screen, bg_col, (fx + 1, fy + 1, TILE_SIZE - 2, TILE_SIZE - 2))
                # Tile bevel highlights
                pygame.draw.line(screen, bevel_col, (fx + 1, fy + 1), (fx + TILE_SIZE - 2, fy + 1), 1)
                pygame.draw.line(screen, bevel_col, (fx + 1, fy + 1), (fx + 1, fy + TILE_SIZE - 2), 1)
                pygame.draw.line(screen, shadow_col, (fx + 1, fy + TILE_SIZE - 2), (fx + TILE_SIZE - 2, fy + TILE_SIZE - 2), 1)
                pygame.draw.line(screen, shadow_col, (fx + TILE_SIZE - 2, fy + 1), (fx + TILE_SIZE - 2, fy + TILE_SIZE - 2), 1)

        # Floor grid metallic brass/steel inlay seams
        for tx in range(21, 37):
            sx = int(tx * TILE_SIZE - cam_x)
            sy1 = int(7 * TILE_SIZE - cam_y)
            sy2 = int(12 * TILE_SIZE - cam_y)
            pygame.draw.line(screen, (16, 14, 12), (sx, sy1), (sx, sy2), 2)
            pygame.draw.line(screen, (80, 70, 50), (sx, sy1), (sx, sy2), 1)

        for ty in range(7, 13):
            sy = int(ty * TILE_SIZE - cam_y)
            sx1 = int(21 * TILE_SIZE - cam_x)
            sx2 = int(36 * TILE_SIZE - cam_x)
            pygame.draw.line(screen, (16, 14, 12), (sx1, sy), (sx2, sy), 2)
            pygame.draw.line(screen, (80, 70, 50), (sx1, sy), (sx2, sy), 1)

        # Central inlaid security floor crest (tile center at 28.5, 9.5)
        cx_crest = int(28.5 * TILE_SIZE - cam_x)
        cy_crest = int(9.5 * TILE_SIZE - cam_y)
        pygame.draw.circle(screen, (18, 16, 14), (cx_crest, cy_crest), 54)
        pygame.draw.circle(screen, (140, 115, 60), (cx_crest, cy_crest), 52, 2)
        pygame.draw.circle(screen, (200, 165, 80), (cx_crest, cy_crest), 46, 1)
        pygame.draw.circle(screen, (32, 28, 24), (cx_crest, cy_crest), 44)
        # Emblem star / eagle cross geometric inlay
        for angle in range(0, 360, 45):
            rad = math.radians(angle)
            x1 = cx_crest + int(math.cos(rad) * 16)
            y1 = cy_crest + int(math.sin(rad) * 16)
            x2 = cx_crest + int(math.cos(rad) * 42)
            y2 = cy_crest + int(math.sin(rad) * 42)
            pygame.draw.line(screen, (180, 150, 70), (x1, y1), (x2, y2), 2 if angle % 90 == 0 else 1)
        pygame.draw.circle(screen, (220, 180, 90), (cx_crest, cy_crest), 10)
        pygame.draw.circle(screen, (40, 32, 20), (cx_crest, cy_crest), 6)

        # 2. South Warning Hazard Striping along entry threshold (y = 11.75 * TILE_SIZE)
        bx1 = int(21 * TILE_SIZE - cam_x)
        bx2 = int(36 * TILE_SIZE - cam_x)
        by = int(11.7 * TILE_SIZE - cam_y)
        bw_total = bx2 - bx1

        # Background base plate for hazard striping
        pygame.draw.rect(screen, (20, 18, 16), (bx1, by, bw_total, 14))
        # Angled hazard slashes
        stripe_w = 16
        for sx in range(bx1 - 16, bx2 + 16, stripe_w * 2):
            pts = [
                (max(bx1, min(bx2, sx)), by),
                (max(bx1, min(bx2, sx + stripe_w)), by),
                (max(bx1, min(bx2, sx + stripe_w - 8)), by + 14),
                (max(bx1, min(bx2, sx - 8)), by + 14),
            ]
            if pts[1][0] > pts[0][0]:
                pygame.draw.polygon(screen, (210, 170, 40), pts)

        # Metal edge trim & rivet studs top & bottom
        pygame.draw.line(screen, (120, 110, 90), (bx1, by), (bx2, by), 2)
        pygame.draw.line(screen, (120, 110, 90), (bx1, by + 14), (bx2, by + 14), 2)
        for rx in range(bx1 + 8, bx2, 32):
            pygame.draw.circle(screen, (180, 170, 150), (rx, by + 2), 2)
            pygame.draw.circle(screen, (180, 170, 150), (rx, by + 12), 2)

        # 3. Dual Metal-Detector Archways & Security Gate (south doorway tx=23..25, ty=11)
        gate_x1 = int(23.2 * TILE_SIZE - cam_x)
        gate_x2 = int(25.8 * TILE_SIZE - cam_x)
        gate_y = int(11.2 * TILE_SIZE - cam_y)

        # Translucent scanning floor line
        scan_surf = pygame.Surface((gate_x2 - gate_x1 + 12, 16), pygame.SRCALPHA)
        # Baked at mid-phase (the chunk cache froze it at a random phase); see _draw_archives_wing_live.
        scan_alpha = 120 if staticlayer.baking() else int(120 + 60 * math.sin(t_sec * 4.0))
        scan_surf.fill((40, 180, 240, scan_alpha // 3))
        pygame.draw.line(scan_surf, (80, 220, 255, scan_alpha), (0, 8), (gate_x2 - gate_x1 + 12, 8), 3)
        screen.blit(scan_surf, (gate_x1 - 6, gate_y - 2))

        # Metal detector upright pillars
        for px_gate in (gate_x1, gate_x2):
            pill = pygame.Rect(px_gate - 8, gate_y - 12, 16, 28)
            pygame.draw.rect(screen, (14, 16, 20), pill.inflate(4, 4), border_radius=3)
            pygame.draw.rect(screen, (50, 56, 66), pill, border_radius=2)
            pygame.draw.rect(screen, (140, 150, 170), pill, 2, border_radius=2)

            # Indicator lights on top: per-frame (blink while locked) -> _draw_archives_wing_live
            if not staticlayer.baking():
                led_col = (80, 220, 120) if unlocked else ((220, 60, 50) if int(t_sec * 3) % 2 == 0 else (120, 30, 25))
                pygame.draw.circle(screen, led_col, (pill.centerx, pill.y + 6), 3)
                pygame.draw.circle(screen, (220, 230, 255), (pill.centerx - 1, pill.y + 5), 1)

            # Scanner sensor vertical strip
            pygame.draw.line(screen, (20, 24, 30), (pill.centerx, pill.y + 12), (pill.centerx, pill.bottom - 4), 3)
            pygame.draw.line(screen, (60, 200, 255), (pill.centerx, pill.y + 12), (pill.centerx, pill.bottom - 4), 1)

        # Overhead arch bar joining pillars
        arch_bar = pygame.Rect(gate_x1 - 8, gate_y - 14, (gate_x2 - gate_x1) + 16, 6)
        pygame.draw.rect(screen, (40, 46, 56), arch_bar, border_radius=1)
        pygame.draw.rect(screen, (120, 130, 150), arch_bar, 1, border_radius=1)

        # 4. Overhead Dome Security Cameras with Dynamic Laser Cones
        for cx_t in (23, 30):
            cx = int(cx_t * TILE_SIZE - cam_x)
            cy = int(6.4 * TILE_SIZE - cam_y)

            # Laser cone sweep projected down: per-frame -> _draw_archives_wing_live
            if not staticlayer.baking():
                _draw_vestibule_laser_cone(cx, cy, cx_t, t_sec, vx0, vy0, vw, vh)

            # Wall mount bracket & conduit pipe
            pygame.draw.line(screen, (40, 42, 48), (cx, cy - 8), (cx, cy + 4), 4)
            pygame.draw.rect(screen, (25, 28, 34), (cx - 14, cy - 10, 28, 8), border_radius=2)
            pygame.draw.rect(screen, (90, 95, 110), (cx - 14, cy - 10, 28, 8), 1, border_radius=2)

            # Dome housing
            pygame.draw.circle(screen, (18, 20, 24), (cx, cy + 12), 11)
            pygame.draw.circle(screen, (60, 65, 78), (cx, cy + 12), 11, 2)
            # Tinted glass lens
            pygame.draw.circle(screen, (30, 35, 45), (cx, cy + 12), 8)
            # Lens specular reflection
            pygame.draw.arc(screen, (200, 220, 255), (cx - 6, cy + 6, 12, 12), math.radians(45), math.radians(160), 2)
            # Recording status LED: per-frame -> _draw_archives_wing_live
            if not staticlayer.baking():
                rec_led = (240, 40, 40) if int(t_sec * 2.5) % 2 == 0 else (120, 20, 20)
                pygame.draw.circle(screen, rec_led, (cx + 5, cy + 8), 2)

        # 5. Wall Sign Plaque ("SECURITY VESTIBULE // ZONE 04")
        lab = font_prompt.render(_T("m3.security_vestibule"), True, (245, 215, 120))
        sub_lab = font_terminal_small.render(_T("m3.zone_04_security_checkpoint"), True, (180, 160, 110))

        pw = max(lab.get_width(), sub_lab.get_width()) + 20
        ph = 28
        target_cx = int(30.5 * TILE_SIZE - cam_x)
        sign_x = target_cx - pw // 2

        # Strict bounds clamping: keep plaque on solid north wall between doorway (col 26) and east wall (col 36)
        min_x = int(26.2 * TILE_SIZE - cam_x)
        max_x = int(35.8 * TILE_SIZE - cam_x - pw)
        if max_x >= min_x:
            sign_x = max(min_x, min(max_x, sign_x))

        sign = pygame.Rect(sign_x, int(6.35 * TILE_SIZE - cam_y), pw, ph)

        # Drop shadow
        pygame.draw.rect(screen, (10, 8, 6), sign.move(2, 2), border_radius=3)
        # Metallic brass frame
        pygame.draw.rect(screen, (42, 34, 20), sign, border_radius=3)
        pygame.draw.rect(screen, (180, 145, 65), sign, 2, border_radius=3)
        pygame.draw.rect(screen, (100, 80, 35), sign.inflate(-4, -4), 1, border_radius=2)

        # Rivets
        for rx, ry in ((sign.x + 3, sign.y + 3), (sign.right - 4, sign.y + 3),
                       (sign.x + 3, sign.bottom - 4), (sign.right - 4, sign.bottom - 4)):
            pygame.draw.circle(screen, (220, 185, 90), (rx, ry), 2)

        screen.blit(lab, (sign.centerx - lab.get_width() // 2, sign.y + 2))
        screen.blit(sub_lab, (sign.centerx - sub_lab.get_width() // 2, sign.y + 15))

        # 6. High-Detail Central Card-Catalog / Security Desk Console Island
        cat = pygame.Rect(int(28 * TILE_SIZE - cam_x - 70),
                          int(9 * TILE_SIZE - cam_y - 22), 140, 48)
        # Soft floor shadow
        pygame.draw.rect(screen, (12, 10, 8), cat.move(4, 6), border_radius=4)

        # Mahogany body
        pygame.draw.rect(screen, (52, 38, 24), cat, border_radius=4)
        pygame.draw.rect(screen, (150, 115, 65), cat, 2, border_radius=4)

        # Corner brass trim plates
        for bx_c, by_c in ((cat.x, cat.y), (cat.right - 8, cat.y),
                           (cat.x, cat.bottom - 8), (cat.right - 8, cat.bottom - 8)):
            corner_r = pygame.Rect(bx_c, by_c, 8, 8)
            pygame.draw.rect(screen, (180, 145, 65), corner_r)
            pygame.draw.circle(screen, (80, 60, 25), corner_r.center, 1)

        # Drawer Matrix (2 rows x 7 drawers)
        for row in range(2):
            for i in range(7):
                drawer = pygame.Rect(cat.x + 8 + i * 18, cat.y + 6 + row * 20, 15, 16)
                pygame.draw.rect(screen, (32, 24, 16), drawer, border_radius=2)
                pygame.draw.rect(screen, (95, 72, 42), drawer, 1, border_radius=2)

                # Brass index label card slot
                label_slot = pygame.Rect(drawer.x + 2, drawer.y + 2, 11, 6)
                pygame.draw.rect(screen, (210, 200, 170), label_slot)
                pygame.draw.rect(screen, (160, 125, 55), label_slot, 1)
                pygame.draw.line(screen, (40, 30, 20), (label_slot.x + 2, label_slot.y + 3), (label_slot.right - 2, label_slot.y + 3), 1)

                # Brass pull handle
                pygame.draw.rect(screen, (180, 145, 65), (drawer.centerx - 3, drawer.y + 10, 6, 3), border_radius=1)

        # Desktop accessories (Logbook + Gooseneck Lamp)
        logbook = pygame.Rect(cat.x + 14, cat.y + 12, 22, 24)
        pygame.draw.rect(screen, (140, 40, 30), logbook, border_radius=2)
        pygame.draw.rect(screen, (220, 210, 185), (logbook.x + 2, logbook.y + 2, logbook.w - 4, logbook.h - 4))
        for ly in range(logbook.y + 5, logbook.bottom - 4, 4):
            pygame.draw.line(screen, (80, 90, 120), (logbook.x + 4, ly), (logbook.right - 4, ly), 1)

        # Desk gooseneck lamp with warm radial glow on desk
        lamp_x = cat.right - 22
        lamp_y = cat.y + 16
        glow_surf = pygame.Surface((64, 64), pygame.SRCALPHA)
        pygame.draw.circle(glow_surf, (255, 220, 140, 35), (32, 32), 32)
        pygame.draw.circle(glow_surf, (255, 235, 180, 60), (32, 32), 18)
        screen.blit(glow_surf, (lamp_x - 32, lamp_y - 32))

        pygame.draw.line(screen, (160, 130, 70), (lamp_x + 6, lamp_y + 12), (lamp_x, lamp_y), 2)
        pygame.draw.polygon(screen, (210, 170, 70), [(lamp_x - 6, lamp_y - 4), (lamp_x + 6, lamp_y - 4), (lamp_x + 8, lamp_y + 4), (lamp_x - 8, lamp_y + 4)])

        # 7. Heavy Access Terminal & Biometric Keypad next to Vault Door
        pad = pygame.Rect(int(35.2 * TILE_SIZE - cam_x),
                          int(8.1 * TILE_SIZE - cam_y), 26, 38)

        # Cable conduit coming from ceiling
        pygame.draw.line(screen, (25, 28, 32), (pad.centerx, pad.y - 14), (pad.centerx, pad.y), 3)
        pygame.draw.line(screen, (70, 80, 90), (pad.centerx, pad.y - 14), (pad.centerx, pad.y), 1)

        # Terminal body frame
        pygame.draw.rect(screen, (10, 12, 14), pad.move(2, 2), border_radius=3)
        pygame.draw.rect(screen, (28, 34, 40), pad, border_radius=3)
        pygame.draw.rect(screen, (110, 130, 140), pad, 2, border_radius=3)

        # Screen display box
        scr_rect = pygame.Rect(pad.x + 3, pad.y + 4, 20, 12)
        pygame.draw.rect(screen, (8, 14, 12) if unlocked else (16, 8, 8), scr_rect)
        pygame.draw.rect(screen, (60, 160, 120) if unlocked else (160, 60, 50), scr_rect, 1)

        # Phosphor status text lines inside screen
        scr_col = (80, 230, 140) if unlocked else (240, 80, 70)
        for i in range(2):
            pygame.draw.line(screen, scr_col, (scr_rect.x + 2, scr_rect.y + 3 + i * 4), (scr_rect.right - 3, scr_rect.y + 3 + i * 4), 1)

        # Keypad buttons (3 cols x 3 rows)
        for r in range(3):
            for c in range(3):
                kp_btn = pygame.Rect(pad.x + 4 + c * 6, pad.y + 18 + r * 4, 4, 3)
                pygame.draw.rect(screen, (60, 70, 75), kp_btn, border_radius=1)

        # Biometric thumbprint reader slot below buttons
        bio = pygame.Rect(pad.x + 4, pad.y + 31, 18, 4)
        pygame.draw.rect(screen, (15, 18, 22), bio, border_radius=1)
        if not staticlayer.baking():
            bio_laser = scr_col if int(t_sec * 4) % 2 == 0 else (100, 100, 100)
            pygame.draw.line(screen, bio_laser, (bio.x + 2, bio.centery), (bio.right - 2, bio.centery), 1)

        # Wall emergency override lock box on West wall (tx=21, ty=8.5)
        box_x = int(21.1 * TILE_SIZE - cam_x)
        box_y = int(8.5 * TILE_SIZE - cam_y)
        lockbox = pygame.Rect(box_x, box_y, 18, 24)
        pygame.draw.rect(screen, (140, 30, 25), lockbox, border_radius=2)
        pygame.draw.rect(screen, (200, 60, 50), lockbox, 1, border_radius=2)
        pygame.draw.rect(screen, (220, 230, 240, 120), (lockbox.x + 3, lockbox.y + 3, 12, 18))
        pygame.draw.rect(screen, (180, 190, 200), (lockbox.x + 3, lockbox.y + 3, 12, 18), 1)
        pygame.draw.line(screen, (200, 40, 40), (lockbox.x + 6, lockbox.y + 12), (lockbox.right - 6, lockbox.y + 12), 2)

    # ── Vostral cold vault (prize room) ──
    # Dense archive vault: metal floor, wall racks, cryo canisters, and a
    # single glass-case centerpiece. No stacked floating labels.
    vx = 36 * TILE_SIZE - cam_x
    vy = 4 * TILE_SIZE - cam_y
    vw, vh = 11 * TILE_SIZE, 11 * TILE_SIZE
    if _screen_visible_rect(vx, vy, vw, vh):
        # Dark steel floor tiles.
        for ty in range(5, 14):
            for tx in range(37, 46):
                fx = int(tx * TILE_SIZE - cam_x)
                fy = int(ty * TILE_SIZE - cam_y)
                base = (28, 32, 36) if (tx + ty) % 2 == 0 else (22, 26, 30)
                pygame.draw.rect(screen, base, (fx + 1, fy + 1, TILE_SIZE - 2, TILE_SIZE - 2))
                pygame.draw.rect(screen, (14, 16, 18), (fx + 1, fy + 1, TILE_SIZE - 2, TILE_SIZE - 2), 1)
                # Bolt marks in corners of every other tile.
                if (tx + ty) % 2 == 0:
                    for ox, oy in ((4, 4), (TILE_SIZE - 8, 4), (4, TILE_SIZE - 8), (TILE_SIZE - 8, TILE_SIZE - 8)):
                        pygame.draw.circle(screen, (50, 55, 60), (fx + ox, fy + oy), 2)

        # Hazard tape strip along the inner wall perimeter.
        for tx in range(37, 46):
            bx = int(tx * TILE_SIZE - cam_x)
            by = int(5.15 * TILE_SIZE - cam_y)
            col = (200, 170, 40) if tx % 2 == 0 else (18, 16, 14)
            pygame.draw.rect(screen, col, (bx, by, TILE_SIZE, 5))
        for ty in range(5, 14):
            for tx in (37, 45):
                bx = int(tx * TILE_SIZE - cam_x + (0 if tx == 37 else TILE_SIZE - 5))
                by = int(ty * TILE_SIZE - cam_y)
                col = (200, 170, 40) if ty % 2 == 0 else (18, 16, 14)
                pygame.draw.rect(screen, col, (bx, by, 5, TILE_SIZE))

        # North wall plaque (single clean title).
        title = font_prompt.render(_T("m3.vostral_vault"), True, (255, 220, 140))
        tw = title.get_width() + 28
        title_bg = pygame.Rect(int(41 * TILE_SIZE - cam_x - tw // 2),
                               int(4.55 * TILE_SIZE - cam_y), tw, 26)
        pygame.draw.rect(screen, (24, 20, 14), title_bg, border_radius=2)
        pygame.draw.rect(screen, (190, 150, 60), title_bg, 2, border_radius=2)
        screen.blit(title, (title_bg.centerx - title.get_width() // 2, title_bg.y + 5))

        # West wall: vertical file racks (fills the old empty glass-stripe zone).
        for i, ty in enumerate((6.2, 8.0, 9.8, 11.6)):
            rx = int(37.55 * TILE_SIZE - cam_x)
            ry = int(ty * TILE_SIZE - cam_y)
            rack = pygame.Rect(rx, ry, 52, 70)
            pygame.draw.rect(screen, (18, 20, 24), rack, border_radius=2)
            pygame.draw.rect(screen, (70, 80, 90), rack, 1, border_radius=2)
            for row in range(4):
                yy = ry + 8 + row * 14
                pygame.draw.line(screen, (40, 48, 55), (rx + 4, yy), (rx + 48, yy), 1)
                for b in range(5):
                    bc = ((90, 40, 40), (40, 60, 90), (70, 60, 35), (50, 45, 70), (35, 55, 50))[(i + row + b) % 5]
                    pygame.draw.rect(screen, bc, (rx + 6 + b * 8, yy - 10, 6, 10))

        # East wall: cryo canisters + conduit.
        for i, ty in enumerate((6.4, 8.6, 10.8)):
            cx = int(44.6 * TILE_SIZE - cam_x)
            cy = int(ty * TILE_SIZE - cam_y)
            # Tank body
            pygame.draw.ellipse(screen, (12, 14, 16), (cx - 18, cy + 40, 36, 12))
            tank = pygame.Rect(cx - 16, cy, 32, 44)
            pygame.draw.rect(screen, (48, 58, 68), tank, border_radius=4)
            pygame.draw.rect(screen, (90, 120, 140), tank, 2, border_radius=4)
            pygame.draw.rect(screen, (30, 40, 50), (cx - 12, cy + 6, 24, 18), border_radius=2)
            # Frost lines
            for ly in (cy + 8, cy + 14, cy + 20):
                pygame.draw.line(screen, (140, 180, 200), (cx - 10, ly), (cx + 8, ly), 1)
            # Valve
            pygame.draw.circle(screen, (160, 160, 150), (cx, cy + 2), 4)
            pygame.draw.circle(screen, (80, 80, 70), (cx, cy + 2), 4, 1)
            # Status LED
            led = (80, 200, 220) if i != 1 else (200, 80, 60)
            pygame.draw.circle(screen, led, (cx + 10, cy + 30), 2)
        # Pipe along east wall
        pygame.draw.line(screen, (60, 70, 80),
                         (int(45.4 * TILE_SIZE - cam_x), int(6.2 * TILE_SIZE - cam_y)),
                         (int(45.4 * TILE_SIZE - cam_x), int(12.8 * TILE_SIZE - cam_y)), 4)
        pygame.draw.line(screen, (100, 120, 130),
                         (int(45.4 * TILE_SIZE - cam_x) - 1, int(6.2 * TILE_SIZE - cam_y)),
                         (int(45.4 * TILE_SIZE - cam_x) - 1, int(12.8 * TILE_SIZE - cam_y)), 1)

        # South wall bench with tools.
        bench = pygame.Rect(int(39.5 * TILE_SIZE - cam_x),
                            int(12.6 * TILE_SIZE - cam_y), 140, 28)
        pygame.draw.rect(screen, (16, 16, 18), (bench.x + 4, bench.bottom - 2, bench.w - 4, 8))
        pygame.draw.rect(screen, (42, 40, 38), bench, border_radius=2)
        pygame.draw.rect(screen, (90, 85, 70), bench, 1, border_radius=2)
        for i in range(4):
            pygame.draw.rect(screen, (70, 70, 65), (bench.x + 12 + i * 30, bench.y + 6, 18, 10), border_radius=1)
            pygame.draw.circle(screen, (180, 160, 60), (bench.x + 21 + i * 30, bench.y + 20), 2)

        # Overhead hard light bars (no soft blobs).
        for lx in (39.5, 42.0, 44.5):
            x = int(lx * TILE_SIZE - cam_x)
            y = int(5.5 * TILE_SIZE - cam_y)
            pygame.draw.rect(screen, (50, 55, 60), (x - 28, y, 56, 7), border_radius=2)
            pygame.draw.rect(screen, (200, 210, 220), (x - 24, y + 2, 48, 3), border_radius=1)

        # ── Centerpiece: multi-tier pedestal + glass cube ──
        ped_cx = int(42 * TILE_SIZE - cam_x)
        ped_cy = int(9.1 * TILE_SIZE - cam_y)

        # Floor ring / warning circle (thin, geometric - not a blob).
        for r, c in ((54, (50, 55, 60)), (48, (90, 80, 40)), (42, (50, 55, 60))):
            pygame.draw.circle(screen, c, (ped_cx, ped_cy + 18), r, 2)
        # Cross marks on ring
        for ang in (0, 90, 180, 270):
            rad = math.radians(ang)
            pygame.draw.line(screen, (120, 100, 50),
                             (ped_cx + math.cos(rad) * 44, ped_cy + 18 + math.sin(rad) * 44),
                             (ped_cx + math.cos(rad) * 52, ped_cy + 18 + math.sin(rad) * 52), 2)

        # Tiered stone/metal base
        pygame.draw.rect(screen, (18, 18, 20), (ped_cx - 40, ped_cy + 22, 80, 12), border_radius=2)
        pygame.draw.rect(screen, (55, 52, 48), (ped_cx - 36, ped_cy + 10, 72, 16), border_radius=2)
        pygame.draw.rect(screen, (100, 90, 70), (ped_cx - 36, ped_cy + 10, 72, 16), 1, border_radius=2)
        # Column
        pygame.draw.rect(screen, (40, 38, 36), (ped_cx - 18, ped_cy - 8, 36, 22), border_radius=2)
        pygame.draw.rect(screen, (120, 105, 70), (ped_cx - 18, ped_cy - 8, 36, 22), 2, border_radius=2)
        # Brass capital
        pygame.draw.rect(screen, (150, 125, 55), (ped_cx - 26, ped_cy - 14, 52, 10), border_radius=2)
        pygame.draw.rect(screen, (200, 170, 80), (ped_cx - 26, ped_cy - 14, 52, 10), 1, border_radius=2)
        # Tiny bolts on capital
        for ox in (-18, -6, 6, 18):
            pygame.draw.circle(screen, (90, 75, 40), (ped_cx + ox, ped_cy - 9), 2)

        taken = getattr(STATE, "m3_vostral_acquired", False)
        # Glass cube case
        case = pygame.Rect(ped_cx - 28, ped_cy - 58, 56, 48)
        # Shadow under case
        pygame.draw.rect(screen, (10, 12, 14), (case.x + 4, case.bottom - 2, case.w - 4, 6))
        # Metal frame
        pygame.draw.rect(screen, (70, 78, 86), case, border_radius=2)
        pygame.draw.rect(screen, (160, 170, 180), case, 2, border_radius=2)
        # Glass fill
        glass = pygame.Surface((case.w - 6, case.h - 6), pygame.SRCALPHA)
        glass.fill((140, 180, 200, 28))
        # Diagonal highlight
        pygame.draw.line(glass, (220, 240, 255, 50), (4, 4), (glass.get_width() - 8, glass.get_height() // 2), 2)
        screen.blit(glass, (case.x + 3, case.y + 3))
        # Corner brackets
        for cx0, cy0, dx, dy in (
            (case.x, case.y, 1, 1),
            (case.right, case.y, -1, 1),
            (case.x, case.bottom, 1, -1),
            (case.right, case.bottom, -1, -1),
        ):
            pygame.draw.line(screen, (200, 210, 220), (cx0, cy0), (cx0 + dx * 10, cy0), 2)
            pygame.draw.line(screen, (200, 210, 220), (cx0, cy0), (cx0, cy0 + dy * 10), 2)

        if not taken:
            # Thin charcoal service-record dossier, not a bright loot box.
            folder = pygame.Rect(ped_cx - 16, ped_cy - 44, 32, 21)
            pygame.draw.rect(screen, (18, 20, 22), folder.move(1, 2), border_radius=2)
            pygame.draw.rect(screen, (38, 40, 42), folder, border_radius=2)
            pygame.draw.rect(screen, (92, 88, 78), folder, 1, border_radius=2)
            # Folder tab, clipped pages, red classification stamp and IPA seal.
            pygame.draw.rect(screen, (48, 49, 48), (folder.x + 3, folder.y - 3, 12, 4), border_radius=1)
            pygame.draw.line(screen, (178, 172, 150),
                             (folder.x + 5, folder.y + 6), (folder.right - 5, folder.y + 6), 1)
            pygame.draw.line(screen, (125, 122, 108),
                             (folder.x + 5, folder.y + 10), (folder.right - 9, folder.y + 10), 1)
            pygame.draw.rect(screen, (132, 38, 34),
                             (folder.x + 5, folder.bottom - 7, 16, 4), 1)
            pygame.draw.circle(screen, (122, 105, 58),
                               (folder.right - 6, folder.bottom - 5), 3, 1)
            # Nameplate ON the case front only (one label). The plate is sized
            # from the rendered label (+6px padding per side, min 56 so it stays
            # case-proportioned) so the border always frames the text exactly,
            # whatever SysFont metrics resolve to on a given platform.
            nm = font_terminal_small.render(_T("m3.vostral"), True, (255, 230, 150))
            plate_w = max(56, nm.get_width() + 12)
            plate = pygame.Rect(ped_cx - plate_w // 2, case.bottom - 2, plate_w, 16)
            pygame.draw.rect(screen, (20, 18, 14), plate, border_radius=2)
            pygame.draw.rect(screen, (200, 170, 70), plate, 1, border_radius=2)
            screen.blit(nm, (plate.centerx - nm.get_width() // 2, plate.y + 2))
        else:
            # Empty mount
            pygame.draw.rect(screen, (40, 44, 48), (ped_cx - 12, ped_cy - 40, 24, 8), border_radius=1)
            nm = font_terminal_small.render(_T("m3.case_empty"), True, (140, 210, 160))
            plate_w = max(56, nm.get_width() + 12)
            plate = pygame.Rect(ped_cx - plate_w // 2, case.bottom - 2, plate_w, 16)
            pygame.draw.rect(screen, (14, 20, 16), plate, border_radius=2)
            pygame.draw.rect(screen, (100, 180, 130), plate, 1, border_radius=2)
            screen.blit(nm, (plate.centerx - nm.get_width() // 2, plate.y + 2))

        # Side spot lamps aimed at case (hard geometry).
        for side in (-1, 1):
            lx = ped_cx + side * 58
            ly = ped_cy - 30
            pygame.draw.rect(screen, (40, 42, 46), (lx - 6, ly - 8, 12, 10), border_radius=1)
            pygame.draw.polygon(screen, (70, 75, 80),
                                [(lx, ly + 2), (lx - side * 8, ly + 18), (lx + side * 4, ly + 18)])

    # ── North stairwell exit ──
    ex = 22 * TILE_SIZE - cam_x
    ey = 2 * TILE_SIZE - cam_y
    if _screen_visible_rect(ex, ey, 7 * TILE_SIZE, 5 * TILE_SIZE):
        unlocked = getattr(STATE, "m3_vostral_acquired", False)
        sx_center = int(25 * TILE_SIZE - cam_x)

        # Recessed stairwell cavity background
        stair_box = pygame.Rect(int(23.5 * TILE_SIZE - cam_x),
                                int(2.4 * TILE_SIZE - cam_y),
                                int(3.0 * TILE_SIZE),
                                int(3.4 * TILE_SIZE))
        pygame.draw.rect(screen, (14, 16, 20), stair_box, border_radius=2)
        pygame.draw.rect(screen, (35, 40, 50), stair_box, 1, border_radius=2)

        # 1. 3D Top-Down Concrete Step Treads
        step_rows = [5.3, 4.8, 4.3, 3.8, 3.3, 2.8]
        nose_col = (140, 220, 160) if unlocked else (210, 160, 50)

        for idx, r_y in enumerate(step_rows):
            sy = int(r_y * TILE_SIZE - cam_y)
            step_w = int(108 - idx * 4)  # Slight perspective narrowing towards top landing
            step_x = sx_center - step_w // 2

            # Step riser (shadow face under tread)
            pygame.draw.rect(screen, (18, 20, 26), (step_x, sy, step_w, 3))
            # Step tread surface
            tread = pygame.Rect(step_x, sy + 3, step_w, 8)
            pygame.draw.rect(screen, (48, 54, 64), tread)
            pygame.draw.rect(screen, (32, 36, 44), tread, 1)

            # Anti-slip texture lines
            for gx in range(step_x + 8, step_x + step_w - 8, 12):
                pygame.draw.line(screen, (38, 44, 52), (gx, sy + 5), (gx + 6, sy + 5), 1)

            # High-visibility nosing lip along front edge
            pygame.draw.line(screen, nose_col, (step_x + 2, sy + 3), (step_x + step_w - 2, sy + 3), 2)

            # Step side wall lights (recessed lamps)
            if idx in (1, 4):
                for side_x in (step_x - 4, step_x + step_w + 1):
                    pygame.draw.circle(screen, (120, 130, 140), (side_x + 1, sy + 4), 2)
                    lamp_glow = nose_col + (40,)
                    gl_surf = pygame.Surface((16, 16), pygame.SRCALPHA)
                    pygame.draw.circle(gl_surf, lamp_glow, (8, 8), 7)
                    screen.blit(gl_surf, (side_x - 7, sy - 4))

        # 2. Stainless Steel Safety Banister Handrails
        x_left_bottom, y_bottom = sx_center - 50, int(5.4 * TILE_SIZE - cam_y)
        x_left_top, y_top = sx_center - 42, int(2.7 * TILE_SIZE - cam_y)

        x_right_bottom = sx_center + 50
        x_right_top = sx_center + 42

        for (x_b, x_t) in ((x_left_bottom, x_left_top), (x_right_bottom, x_right_top)):
            # Shadow line
            pygame.draw.line(screen, (12, 14, 18), (x_b + 2, y_bottom + 2), (x_t + 2, y_top + 2), 4)
            # Main tubular rail
            pygame.draw.line(screen, (80, 90, 105), (x_b, y_bottom), (x_t, y_top), 4)
            # Top specular shine
            pygame.draw.line(screen, (200, 215, 235), (x_b, y_bottom - 1), (x_t, y_top - 1), 1)

            # Vertical support stanchions attached to steps
            for frac in (0.2, 0.55, 0.85):
                px_rail = int(x_b + (x_t - x_b) * frac)
                py_rail = int(y_bottom + (y_top - y_bottom) * frac)
                pygame.draw.line(screen, (100, 110, 125), (px_rail, py_rail), (px_rail, py_rail + 6), 2)
                pygame.draw.circle(screen, (160, 170, 180), (px_rail, py_rail + 6), 2)

        # 3. Backlit Exit Sign Plaque on North Landing Wall
        col_sign = (80, 220, 140) if unlocked else (230, 70, 60)
        bg_sign = (12, 38, 22) if unlocked else (48, 14, 14)
        txt_str = "EXIT > KILL ORDER" if unlocked else "STAIRWELL SEALED"

        sign_lbl = font_terminal_small.render(txt_str, True, col_sign)
        sign_w = sign_lbl.get_width() + 20
        sign_rect = pygame.Rect(sx_center - sign_w // 2, int(2.15 * TILE_SIZE - cam_y), sign_w, 20)

        # Glow halo
        glow_box = sign_rect.inflate(8, 6)
        glow_surf = pygame.Surface((glow_box.w, glow_box.h), pygame.SRCALPHA)
        pygame.draw.rect(glow_surf, col_sign + (40,), glow_surf.get_rect(), border_radius=4)
        screen.blit(glow_surf, glow_box)

        # Frame and plate
        pygame.draw.rect(screen, bg_sign, sign_rect, border_radius=3)
        pygame.draw.rect(screen, col_sign, sign_rect, 2, border_radius=3)
        screen.blit(sign_lbl, (sign_rect.centerx - sign_lbl.get_width() // 2, sign_rect.y + 2))


def _draw_archives_map_polish(cam_x, cam_y):
    """Room frames only. Hero rooms keep their custom wall plaques -
    duplicate frame labels (DEAD-DROP / VOSTRAL / VESTIBULE) used to
    stack on top of those plaques and clip."""
    _draw_rect_room_frame(cam_x, cam_y, 18, 38, 13, 8, gaps_top=[(23, 25)],
                          label="LOBBY", label_col=(140, 120, 180))
    _draw_rect_room_frame(cam_x, cam_y, 20, 12, 9, 27, gaps_bottom=[(23, 25)],
                          gaps_top=[(23, 25)], gaps_left=[(24, 25)], gaps_right=[(24, 25)],
                          label="ATRIUM", label_col=(160, 140, 200))
    _draw_rect_room_frame(cam_x, cam_y, 4, 18, 17, 19, gaps_right=[(24, 25)],
                          gaps_top=[(10, 11)],
                          label="STACKS", label_col=(120, 150, 145))
    # Clerk office / dead-drop - frame only, plaque drawn in wing details.
    _draw_rect_room_frame(cam_x, cam_y, 6, 8, 11, 11, gaps_bottom=[(10, 11)],
                          label=None)
    _draw_rect_room_frame(cam_x, cam_y, 28, 18, 16, 19, gaps_left=[(24, 25)],
                          label="RESEARCH", label_col=(150, 145, 120))
    # Vestibule + vault + exit - custom signs only.
    _draw_rect_room_frame(cam_x, cam_y, 20, 6, 16, 6,
                          gaps_top=[(24, 25)], gaps_bottom=[(23, 25)], gaps_right=[(8, 9)],
                          label=None)
    _draw_rect_room_frame(cam_x, cam_y, 36, 4, 10, 10, gaps_left=[(8, 9)],
                          label=None)
    _draw_rect_room_frame(cam_x, cam_y, 22, 2, 7, 5, gaps_bottom=[(24, 25)],
                          label=None)


def _draw_prompt_tag(sx, sy, text, col, *, y_off=-46, icon=None):
    """Readable world prompt, guaranteed to fit inside the viewport.

    Phase 4: the body is ``engine.ui.std.prompt`` (M3's look is its default);
    the caller keeps resolving the art pack icon.
    """
    from engine.ui import prompt as _hud_prompt  # lazy: engine.ui facade
    _hud_prompt.draw(screen, sx, sy, text, col, y_off=y_off,
                     icon=artpack.icon(icon) if icon else None,
                     font=font_prompt, fallback_font=font_terminal_small)


def _draw_archives_system_prompts(cam_x, cam_y):
    """Sparse world prompts - only when the player is in range to act.

    Far-away status labels used to stack on room plaques and get clipped.
    The nav arrow + objective panel already handle long-range guidance.
    """
    if getattr(STATE, "mission3_stage", None) not in (STAGE_ARCHIVES, STAGE_KILL_ORDER):
        return
    if not STATE.player:
        return
    if getattr(STATE, "m3_maru_contact_active", False):
        return  # fullscreen overlay owns the UI

    px, py = STATE.player.rect.centerx, STATE.player.rect.centery

    # Maru terminal - only when close enough to interact.
    mx, my = _maru_terminal_pos()
    if math.hypot(px - mx, py - my) <= 88:
        sx, sy = mx - cam_x, my - cam_y
        if getattr(STATE, "m3_maru_contacted", False):
            _draw_prompt_tag(sx, sy, "CHANNEL CLOSED", (120, 220, 160), y_off=-62)
        else:
            _draw_prompt_tag(sx, sy, "[E] CONTACT MARU", (255, 210, 110), y_off=-62, icon="radio")

    # Vostral file - near pedestal only.
    if not getattr(STATE, "m3_vostral_acquired", False):
        vx, vy = _vostral_file_pos()
        if math.hypot(px - vx, py - vy) <= 150:
            sx, sy = vx - cam_x, vy - cam_y
            if not getattr(STATE, "m3_maru_contacted", False):
                _draw_prompt_tag(sx, sy, "VAULT SEALED, CONTACT MARU", (220, 130, 90), y_off=-74)
            else:
                _draw_prompt_tag(sx, sy, "[E] TAKE THE VOSTRAL", (255, 210, 110), y_off=-74, icon="dossier")

    # North exit - near only.
    ex, ey = _archives_exit_pos()
    if math.hypot(px - ex, py - ey) <= 110:
        sx, sy = ex - cam_x, ey - cam_y
        if getattr(STATE, "m3_vostral_acquired", False):
            _draw_prompt_tag(sx, sy, "[E] EXIT, KILL ORDER", (120, 230, 160), y_off=-48, icon="keycard")
        else:
            _draw_prompt_tag(sx, sy, "EXIT SEALED", (230, 90, 70), y_off=-48)


def _draw_archives_atmosphere(cam_x, cam_y):
    """Subtle cool grade only - no soft circular blobs."""
    wash = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
    wash.fill((18, 12, 28, 18))
    screen.blit(wash, (0, 0))


def _draw_maru_contact_overlay():
    """Fullscreen Maru transmission - slow, readable, high-contrast."""
    if not getattr(STATE, "m3_maru_contact_active", False):
        return
    t = getattr(STATE, "m3_maru_contact_timer", 0)
    duration = int(getattr(STATE, "m3_maru_contact_duration", 960) or 960)
    progress = max(0.0, min(1.0, t / float(duration)))

    dim = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
    dim.fill((0, 0, 0, 200))
    screen.blit(dim, (0, 0))

    panel_w, panel_h = min(860, WIDTH - 36), min(430, HEIGHT - 50)
    panel_x = WIDTH // 2 - panel_w // 2
    panel_y = HEIGHT // 2 - panel_h // 2

    panel = pygame.Surface((panel_w, panel_h))
    panel.fill((12, 12, 16))
    pygame.draw.rect(panel, (200, 170, 255), panel.get_rect(), 3, border_radius=6)
    pygame.draw.rect(panel, (40, 36, 52), (3, 3, panel_w - 6, 56), border_radius=4)
    pygame.draw.line(panel, (140, 120, 190), (16, 62), (panel_w - 16, 62), 2)

    title = font_speaker.render(_T("m3.ghost_channel_m_a_g"), True, (245, 235, 255))
    panel.blit(title, (22, 16))
    sub = font_prompt.render(_T("m3.former_ipa_archivist_dead_drop"), True, (200, 185, 230))
    panel.blit(sub, (panel_w - sub.get_width() - 22, 24))

    # Staggered over ~16s so players can read each line fully.
    # thresh = when line starts; type_frames = how long it types out.
    lines = [
        (40,  70,  "MARU",   "You shouldn't be alive, Biribel."),
        (150, 70,  "MARU",   "Neither should this file."),
        (280, 90,  "MARU",   "Balaceanu forged every medal."),
        (420, 100, "MARU",   "The real record is in the cold vault."),
        (560, 100, "MARU",   "I unlock it. You steal it. Then run north."),
        (720, 120, "SYSTEM", "Vault authorization, granting access..."),
        (860, 80,  "SYSTEM", "Access granted. East vault door is open."),
    ]

    body_y = 84
    for thresh, type_frames, speaker, line in lines:
        if t < thresh:
            continue
        local = max(0.0, min(1.0, (t - thresh) / float(type_frames)))
        shown = line[:max(1, int(len(line) * local))]
        if speaker == "MARU":
            sp_col = (210, 170, 255)
            body_col = (245, 245, 250)
        else:
            sp_col = (120, 220, 240)
            body_col = (200, 235, 245)
        sp = font_dialogue.render(_T("m3.speaker", speaker=speaker), True, sp_col)
        body = font_dialogue.render(shown, True, body_col)
        panel.blit(font_dialogue.render(_T("m3.speaker", speaker=speaker), True, (0, 0, 0)), (25, body_y + 1))
        panel.blit(sp, (24, body_y))
        panel.blit(font_dialogue.render(shown, True, (0, 0, 0)), (24 + sp.get_width() + 11, body_y + 1))
        panel.blit(body, (24 + sp.get_width() + 10, body_y))
        # Cursor while typing.
        if local < 1.0 and int(t / 8) % 2 == 0:
            cx = 24 + sp.get_width() + 10 + body.get_width() + 2
            pygame.draw.rect(panel, body_col, (cx, body_y + 4, 8, font_dialogue.get_height() - 8))
        body_y += 40

    bar = pygame.Rect(24, panel_h - 48, panel_w - 48, 18)
    pygame.draw.rect(panel, (30, 28, 40), bar, border_radius=3)
    fill = bar.copy()
    fill.width = max(4, int(bar.width * progress))
    pygame.draw.rect(panel, (170, 130, 230), fill, border_radius=3)
    pygame.draw.rect(panel, (220, 200, 255), bar, 2, border_radius=3)
    pct = font_prompt.render(_T("m3.handshake_pct", pct="{:02d}".format(int(progress * 100))), True, (235, 225, 255))
    panel.blit(pct, (bar.centerx - pct.get_width() // 2, bar.y - 24))
    hint = font_terminal_small.render(_T("m3.stand_by_channel_locked_until_ha"), True, (160, 150, 180))
    panel.blit(hint, (bar.centerx - hint.get_width() // 2, bar.bottom + 4))

    scan = pygame.Surface((panel_w, panel_h), pygame.SRCALPHA)
    for yy in range(0, panel_h, 4):
        pygame.draw.line(scan, (0, 0, 0, 22), (0, yy), (panel_w, yy), 1)
    panel.blit(scan, (0, 0))

    screen.blit(panel, (panel_x, panel_y))



def draw_archives_transition_cinematic(surface, t, phase):
    """Render the Comms → Archives transition using the live Archives world.

    This is intentionally the normal top-down visual language: real tilemap,
    authored room dressing, gameplay player/Volkov sprites, doors, and guards.
    Only the camera and temporary actor positions are directed. All positions
    are restored after drawing, so the cutscene cannot mutate gameplay state.
    """
    target = screen
    if STATE.player is None:
        target.fill((8, 10, 12))
        return

    sx, sy = STATE.player.rect.center
    if phase == "enter":
        duration = 1400.0
        p = max(0.0, min(1.0, t / duration))
        move = 42.0 * (p * p * (3.0 - 2.0 * p))
        reveal_enemies = False
        camera_lead = 95.0 + 85.0 * p
    elif phase == "join":
        duration = 1800.0
        p = max(0.0, min(1.0, t / duration))
        move = 42.0 + 38.0 * p
        reveal_enemies = False
        camera_lead = 180.0 + 100.0 * p
    else:
        duration = 2200.0
        p = max(0.0, min(1.0, t / duration))
        move = 80.0 + 36.0 * p
        reveal_enemies = True
        camera_lead = 280.0 + 270.0 * (p * p * (3.0 - 2.0 * p))

    # A small walking cadence makes the directed movement feel alive while
    # remaining visually identical to normal gameplay.
    bob = math.sin(t * 0.018) * 2.0
    player_pos = (sx, sy - move + bob)
    volkov_pos = (sx - 56, sy - move + 30 - bob)
    focus = (sx, sy - camera_lead)
    mw, mh = _m3_maps._live_map_dims()
    cam_x = max(0.0, min(mw * TILE_SIZE - WIDTH, focus[0] - WIDTH / 2))
    cam_y = max(0.0, min(mh * TILE_SIZE - HEIGHT, focus[1] - HEIGHT / 2))
    cam_x, cam_y = int(cam_x), int(cam_y)

    target.fill((12, 10, 16))
    _render_cell_bg(target, cam_x, cam_y)
    _draw_archives_wing_details(cam_x, cam_y)
    _draw_archives_map_polish(cam_x, cam_y)
    _draw_archives_atmosphere(cam_x, cam_y)
    _draw_m3_doors(cam_x, cam_y)
    _draw_m3_doors_foreground(cam_x, cam_y)

    old_player_pos = STATE.player.rect.center
    old_player_angle = STATE.player.angle
    old_vx = getattr(STATE, "m3_volkov_ally_x", 0.0)
    old_vy = getattr(STATE, "m3_volkov_ally_y", 0.0)
    old_va = getattr(STATE, "m3_volkov_ally_angle", 0.0)
    try:
        STATE.player.rect.center = (int(player_pos[0]), int(player_pos[1]))
        STATE.player.angle = -math.pi / 2
        STATE.player.draw(
            target, cam_x, cam_y,
            walls=solid_walls_view(),
            reload_active=False,
            reload_progress=0.0,
            no_gun=False,
            melee_active=False,
            melee_progress=0.0,
            is_moving=True,
        )

        STATE.m3_volkov_ally_x = float(volkov_pos[0])
        STATE.m3_volkov_ally_y = float(volkov_pos[1])
        STATE.m3_volkov_ally_angle = -math.pi / 2
        _draw_volkov_ally(cam_x, cam_y)

        # The first two beats establish geography without exposing the whole
        # encounter. The final pan reveals the actual guards in their gameplay
        # positions, so the cut lands directly into a readable combat space.
        if reveal_enemies:
            for e in STATE.enemies:
                e.draw(target, cam_x, cam_y)
                _draw_m3_enemy_type_overlay(target, e, cam_x, cam_y)
    finally:
        STATE.player.rect.center = old_player_pos
        STATE.player.angle = old_player_angle
        STATE.m3_volkov_ally_x = old_vx
        STATE.m3_volkov_ally_y = old_vy
        STATE.m3_volkov_ally_angle = old_va

    # Restrained cinematic treatment over gameplay art: no HUD, only a subtle
    # vignette and location plate during the final reveal.
    draw_vignette(target, strength=115)
    if phase == "reveal" and t > 450:
        alpha = min(255, int((t - 450) * 0.45))
        plate = font_location.render(_T("m3.archives_wing"), True, (205, 214, 218))
        sub = font_location_sub.render(_T("m3.the_stabilization_center"), True, (105, 135, 145))
        plate.set_alpha(alpha)
        sub.set_alpha(alpha)
        target.blit(plate, (54, SCENE_TOP + 42))
        target.blit(sub, (58, SCENE_TOP + 84))

    if surface is not target:
        surface.blit(target, (0, 0))


def _vp_lerp(a, b, u):
    return a + (b - a) * u


def _vp_forearm(surface, wrist, elbow, w0, w1):
    """Tapered sleeve from wrist off-screen; no pipe-stick arms."""
    dx, dy = elbow[0] - wrist[0], elbow[1] - wrist[1]
    d = math.hypot(dx, dy) or 1
    px, py = -dy / d, dx / d
    quad = [(wrist[0] + px * w1, wrist[1] + py * w1),
            (elbow[0] + px * w0, elbow[1] + py * w0),
            (elbow[0] - px * w0, elbow[1] - py * w0),
            (wrist[0] - px * w1, wrist[1] - py * w1)]
    pygame.draw.polygon(surface, (40, 30, 23), quad)
    pygame.draw.polygon(surface, (72, 52, 38),
                        [(_vp_lerp(q[0], (wrist[0] + elbow[0]) / 2, 0.2),
                          _vp_lerp(q[1], (wrist[1] + elbow[1]) / 2, 0.2)) for q in quad])
    pygame.draw.line(surface, (40, 30, 23),
                     (wrist[0] - px * w1, wrist[1] - py * w1),
                     (wrist[0] + px * w1, wrist[1] + py * w1), 3)


def _v2_dossier(surface, cx, cy, sc, angle, alpha=255):
    """The Vostral: a manila IPA service-record dossier, portrait format -
    red VOSTRAL stencil, string-and-button closure, paper block edge, small
    binder clip. Reads as a file, not a slab."""
    w, h = int(112 * sc), int(150 * sc)
    lay = pygame.Surface((w + 28, h + 28), pygame.SRCALPHA)
    ox, oy = 14, 14
    # paper block behind (pages slightly offset)
    pygame.draw.rect(lay, (226, 220, 202, alpha), (ox + 3, oy + 4, w, h), border_radius=3)
    # manila cover
    pygame.draw.rect(lay, (96, 82, 58, alpha), (ox - 2, oy + 2, w, h), border_radius=4)
    pygame.draw.rect(lay, (172, 150, 112, alpha), (ox, oy, w, h), border_radius=4)
    pygame.draw.rect(lay, (142, 122, 88, alpha), (ox, oy, w, h), 2, border_radius=4)
    # spine shade + cover crease
    pygame.draw.rect(lay, (142, 122, 88, alpha), (ox, oy, int(10 * sc), h), border_radius=3)
    pygame.draw.line(lay, (142, 122, 88, alpha), (ox + int(10 * sc), oy + 2),
                     (ox + int(10 * sc), oy + h - 2), 1)
    pygame.draw.line(lay, (142, 122, 88, alpha), (ox + w - int(8 * sc), oy + 4),
                     (ox + w - int(8 * sc), oy + h - 4), 1)
    if sc >= 0.7:
        fnt = font_terminal_small if sc < 1.5 else font_terminal
        st = fnt.render(_T("m3.vostral"), True, (168, 44, 36))
        st.set_alpha(alpha)
        lay.blit(st, (ox + int(18 * sc), oy + int(18 * sc)))
        pygame.draw.line(lay, (168, 44, 36, alpha), (ox + int(18 * sc), oy + int(30 * sc)),
                         (ox + int(86 * sc), oy + int(30 * sc)), max(1, int(1.5 * sc)))
        sub = font_terminal_small.render(_T("m3.service_record"), True, (96, 82, 58))
        sub.set_alpha(int(alpha * 0.9))
        lay.blit(sub, (ox + int(18 * sc), oy + int(36 * sc)))
        # string-and-button closure
        pygame.draw.circle(lay, (92, 78, 54, alpha), (ox + w - int(16 * sc), oy + int(20 * sc)),
                           max(2, int(3 * sc)))
        pygame.draw.circle(lay, (92, 78, 54, alpha), (ox + w - int(16 * sc), oy + int(44 * sc)),
                           max(2, int(3 * sc)))
        pygame.draw.line(lay, (210, 200, 178, alpha),
                         (ox + w - int(16 * sc), oy + int(20 * sc)),
                         (ox + w - int(16 * sc), oy + int(44 * sc)), 1)
        # corner binder clip
        pygame.draw.rect(lay, (60, 62, 66, alpha), (ox + int(6 * sc), oy - int(4 * sc),
                                                   int(22 * sc), int(10 * sc)), border_radius=2)
    lay = pygame.transform.rotate(lay, angle)
    surface.blit(lay, (int(cx - lay.get_width() / 2), int(cy - lay.get_height() / 2)))


_VP_WRIST = (-30.0, 60.0)      # local hand frame: +x onto the face, +y down
_VP_KNUCK = (-12.0, -8.0)      # knuckle centre - the hand leans on this axis


def _vp_hp(x, y, sc, mirror, tilt, lx, ly):
    """Local hand coords -> screen, with mirror, scale and folder tilt."""
    ca, sa = math.cos(math.radians(tilt)), math.sin(math.radians(tilt))
    px, py = lx * mirror * sc, ly * sc
    return (x + px * ca - py * sa, y + px * sa + py * ca)


_VP_HAND_CACHE = {}
_VP_ANCHOR = (0.095, 0.30)     # thumb-pad centre, as fractions of the sprite
_VP_WRISTF = (0.740, 0.960)    # wrist cut centre, same fractions
_VP_HAND_SCALE = 0.38          # sprite pixels per world unit at sc=1
_VP_TUCK = 24.0              # world units the hand tucks toward/under the sheet edge


def _vp_hand_sprites():
    """Lazy-load the pre-rendered pinch-grip hand (see assets/hand_pinch.png).

    The sprite is authored outside pygame (generated illustration, chroma-keyed
    and quantized to the game palette) because polygon primitives could not
    produce a believable hand. The thumb-only variant lets the cinematic draw
    the index BEHIND the sheet and the thumb IN FRONT - a true pinch.
    """
    if not _VP_HAND_CACHE:
        base = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                            "..", "..", "..", "assets")
        try:
            full = _load_image(os.path.join(base, "hand_pinch.png"), convert="alpha")
            thumb = _load_image(os.path.join(base, "hand_pinch_thumb.png"), convert="alpha")
        except Exception:
            full = thumb = None
        _VP_HAND_CACHE["full"] = full
        _VP_HAND_CACHE["thumb"] = thumb
    return _VP_HAND_CACHE["full"], _VP_HAND_CACHE["thumb"]


def _vp_hand_xform(spr, sc, mirror, tilt):
    """Scale/mirror/rotate a hand sprite; returns (surface, anchor, wrist)."""
    k = _VP_HAND_SCALE * sc
    w = max(2, int(spr.get_width() * k))
    h = max(2, int(spr.get_height() * k))
    surf = pygame.transform.smoothscale(spr, (w, h))
    ax, ay = _VP_ANCHOR[0] * w, _VP_ANCHOR[1] * h
    wx, wy = _VP_WRISTF[0] * w, _VP_WRISTF[1] * h
    if mirror == 1:
        surf = pygame.transform.flip(surf, True, False)
        ax, ay = w - ax, ay
        wx, wy = w - wx, wy
    if tilt:
        ang = tilt if mirror == 1 else -tilt
        cx, cy = w / 2.0, h / 2.0
        ca, sa = math.cos(math.radians(ang)), math.sin(math.radians(ang))
        rx = lambda px, py: (cx + (px - cx) * ca - (py - cy) * sa,
                             cy + (px - cx) * sa + (py - cy) * ca)
        ax, ay = rx(ax, ay)
        wx, wy = rx(wx, wy)
        surf = pygame.transform.rotate(surf, -ang)
    return surf, (ax, ay), (wx, wy)


def _vp_hand_world(x, y, sc, mirror, tilt, frac):
    """World position of a point given in sprite fractions."""
    full, _t = _vp_hand_sprites()
    if full is None:
        return (x, y)
    k = _VP_HAND_SCALE * sc
    w = max(2, int(full.get_width() * k))
    h = max(2, int(full.get_height() * k))
    px, py = frac[0] * w, frac[1] * h
    if mirror == 1:
        px = w - px
    ang = (tilt if mirror == 1 else -tilt)
    cx, cy = w / 2.0, h / 2.0
    ca, sa = math.cos(math.radians(ang)), math.sin(math.radians(ang))
    rx = cx + (px - cx) * ca - (py - cy) * sa
    ry = cy + (px - cx) * sa + (py - cy) * ca
    # the anchor (thumb pad) sits at the grip point (x, y)
    ax, ay = _VP_ANCHOR[0] * w, _VP_ANCHOR[1] * h
    if mirror == 1:
        ax = w - ax
    bx = cx + (ax - cx) * ca - (ay - cy) * sa
    by = cy + (ax - cx) * sa + (ay - cy) * ca
    return (x + (rx - bx) + mirror * _VP_TUCK * sc, y + (ry - by))


def _vp_pinch_wrist(x, y, sc, mirror, tilt=0.0):
    return _vp_hand_world(x, y, sc, mirror, tilt, _VP_WRISTF)


def _vp_pinch_elbow(x, y, sc, mirror, tilt=0.0):
    """Forearm continues down-and-outward from the wrist, same diagonal as the
    hand, so the wrist flows into the sleeve with no kink."""
    wx, wy = _vp_pinch_wrist(x, y, sc, mirror, tilt)
    return (wx + mirror * -55 * sc, wy + 300 * sc)


def _vp_edge_hold_back(s, x, y, sc, mirror, tilt=0.0):
    """Full hand behind the sheet: everything except the thumb is occluded by
    the paper where they overlap, which is what puts the index behind it."""
    full, _t = _vp_hand_sprites()
    if full is None:
        return _vp_pinch_wrist(x, y, sc, mirror, tilt)
    surf, (ax, ay), _w = _vp_hand_xform(full, sc, mirror, tilt)
    s.blit(surf, (int(x - ax + mirror * _VP_TUCK * sc), int(y - ay)))
    return _vp_pinch_wrist(x, y, sc, mirror, tilt)


def _vp_edge_hold_front(s, x, y, sc, mirror, tilt=0.0, cuff_to=None):
    """Thumb in front of the sheet + soft cast shadow + cuff on the wrist."""
    full, thumb = _vp_hand_sprites()
    wx, wy = _vp_pinch_wrist(x, y, sc, mirror, tilt)
    if thumb is None:
        return (wx, wy)
    # soft layered cast shadow under the thumb pad, on the paper
    sh = pygame.Surface((int(40 * sc), int(60 * sc)), pygame.SRCALPHA)
    for cx, cy, rw, rh, al in ((20, 34, 24, 42, 26), (19, 32, 14, 28, 38)):
        pygame.draw.ellipse(sh, (46, 34, 20, al), (int(cx - rw / 2), int(cy - rh / 2),
                                                  int(rw), int(rh)))
    if tilt:
        sh = pygame.transform.rotate(sh, tilt if mirror == -1 else -tilt)
    px, py = _vp_hand_world(x, y, sc, mirror, tilt, (0.15, 0.46))
    s.blit(sh, (int(px - sh.get_width() / 2), int(py - sh.get_height() / 2)))
    surf, (ax, ay), _w = _vp_hand_xform(thumb, sc, mirror, tilt)
    s.blit(surf, (int(x - ax + mirror * _VP_TUCK * sc), int(y - ay)))
    # cuff: tapered band across the wrist, along the forearm diagonal
    ex, ey = _vp_pinch_elbow(x, y, sc, mirror, tilt)
    dx, dy = ex - wx, ey - wy
    dl = math.hypot(dx, dy) or 1.0
    ux, uy = dx / dl, dy / dl
    qx, qy = -uy, ux
    cw0, cw1 = 12 * sc, 14 * sc
    pygame.draw.polygon(s, (52, 38, 28),
                        [(int(wx + ux * 0 * sc + qx * cw0), int(wy + uy * 0 * sc + qy * cw0)),
                         (int(wx + ux * 0 * sc - qx * cw0), int(wy + uy * 0 * sc - qy * cw0)),
                         (int(wx + ux * 20 * sc - qx * cw1), int(wy + uy * 20 * sc - qy * cw1)),
                         (int(wx + ux * 20 * sc + qx * cw1), int(wy + uy * 20 * sc + qy * cw1))])
    pygame.draw.line(s, (72, 52, 38),
                     (int(wx + qx * cw0), int(wy + qy * cw0)),
                     (int(wx - qx * cw0), int(wy - qy * cw0)), 2)
    return (wx, wy)


def draw_vostral_pickup_cinematic(surface, t, phase):
    """FIRST-PERSON Vostral acquisition, staged inside the real Archives
    look: blue-gray tile room, book-spine shelves, wall terminal, yellow
    door frame. Approach -> glass retracts -> take the dossier -> hold and
    confirm with the KRAP evidence stamp.
    """
    s = surface
    _world = pygame.Surface((WIDTH, HEIGHT))   # virtual-camera target
    s = _world
    ms = float(t)
    u = lambda a, b: max(0.0, min(1.0, (ms - a) / b))  # noqa: E731

    hx = math.sin(ms * 0.0035) * 1.2 + math.sin(ms * 0.009) * 0.6
    hy = math.cos(ms * 0.0045) * 1.0
    if phase == "open":
        hy += abs(math.sin(ms * 0.007)) * 7 * max(0.0, 1.0 - ms / 800)
    if phase == "confirm" and 900 < ms < 1050:
        hx += math.sin(ms * 0.9) * 3
        hy += math.cos(ms * 0.8) * 2

    # ── Archives room, first person (palette matched to the map) ──
    for y in range(0, HEIGHT, 4):
        g = 14 + int(8 * (y / HEIGHT))
        pygame.draw.rect(s, (g, g + 2, g + 2), (0, y, WIDTH, 4))
    horizon = 470
    pygame.draw.rect(s, (24, 27, 28), (0, horizon, WIDTH, HEIGHT - horizon))
    for i in range(7):  # converging floor tiles
        yy = horizon + int((i / 7.0) ** 1.6 * (HEIGHT - horizon))
        pygame.draw.line(s, (31, 35, 36), (0, yy), (WIDTH, yy), 1)
    for xx in range(-200, WIDTH + 200, 150):
        pygame.draw.line(s, (31, 35, 36), (500 + (xx - 500) * 0.35, horizon), (xx, HEIGHT), 1)
    pygame.draw.line(s, (38, 42, 43), (0, horizon), (WIDTH, horizon), 2)
    # book-spine shelves, left and right (Archives prop language)
    for sx0 in (-40, WIDTH - 250):
        pygame.draw.rect(s, (18, 21, 22), (int(sx0 + hx * 0.4), 120, 290, 330))
        pygame.draw.rect(s, (30, 34, 35), (int(sx0 + hx * 0.4), 120, 290, 330), 2)
        rr = random.Random(71 + sx0)
        for row in range(4):
            ry = 140 + row * 80
            pygame.draw.line(s, (30, 34, 35), (sx0 + 8, ry + 62), (sx0 + 282, ry + 62), 3)
            bx = sx0 + 12
            while bx < sx0 + 272:
                bw = rr.randrange(7, 15)
                c = rr.choice([(122, 72, 66), (86, 108, 92), (92, 98, 122),
                               (148, 124, 72), (104, 84, 64), (70, 84, 88)])
                pygame.draw.rect(s, c, (int(bx + hx * 0.4), ry + 62 - rr.randrange(34, 52),
                                        bw, rr.randrange(34, 52)))
                bx += bw + rr.randrange(1, 4)
    # wall terminal (right) + yellow door frame (left), per the map props
    pygame.draw.rect(s, (86, 102, 116), (int(760 + hx * 0.5), 180, 74, 108), border_radius=6)
    pygame.draw.rect(s, (52, 62, 72), (int(760 + hx * 0.5), 180, 74, 108), 2, border_radius=6)
    for i in range(3):
        pygame.draw.line(s, (226, 232, 236), (768 + hx * 0.5, 200 + i * 18),
                         (820 + hx * 0.5, 200 + i * 18), 2)
    pygame.draw.circle(s, (90, 200, 210), (int(822 + hx * 0.5), 268), 3)
    pygame.draw.line(s, (196, 168, 58), (int(238 + hx * 0.5), 120), (int(238 + hx * 0.5), 470), 4)
    pygame.draw.line(s, (196, 168, 58), (int(742 + hx * 0.5), 120), (int(742 + hx * 0.5), 470), 2)

    # ── pedestal + display case, as on the map (gray housing, dark inset) ──
    pcx, pcy = int(500 + hx), int(400 + hy)
    # the glass retracts during this shot; the light cue follows it
    case_p = u(300, 800) if phase == "open" else 1.0
    lit = 1.0 + 1.1 * case_p
    ca = int(min(48, 26 * lit))
    pa = int(min(64, 34 * lit))
    cone = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
    pygame.draw.polygon(cone, (214, 202, 168, ca), [(474, 40), (526, 40), (630, pcy), (370, pcy)])
    pygame.draw.ellipse(cone, (222, 210, 176, pa), (pcx - 160, pcy - 20, 320, 70))
    s.blit(cone, (0, 0))
    pygame.draw.polygon(s, (30, 32, 34), [(pcx - 74, pcy + 70), (pcx + 74, pcy + 70),
                                          (pcx + 52, pcy - 6), (pcx - 52, pcy - 6)])
    pygame.draw.rect(s, (150, 154, 158), (pcx - 56, pcy - 74, 112, 72), border_radius=5)
    pygame.draw.rect(s, (96, 100, 104), (pcx - 56, pcy - 74, 112, 72), 2, border_radius=5)
    pygame.draw.rect(s, (40, 38, 36), (pcx - 42, pcy - 62, 84, 48), border_radius=3)
    pygame.draw.line(s, (168, 44, 36), (pcx - 34, pcy - 40), (pcx + 34, pcy - 40), 2)
    pygame.draw.line(s, (168, 44, 36), (pcx - 34, pcy - 30), (pcx + 10, pcy - 30), 2)

    # ── security glass retracts along rails (shot 1) ──
    gap = int(60 * case_p)
    if case_p > 0:
        for sgn in (-1, 1):
            pygame.draw.line(s, (52, 54, 58), (pcx + sgn * 62, pcy - 96),
                             (pcx + sgn * 62, pcy - 2), 3)
    if gap < 60:
        gl = pygame.Surface((130, 100), pygame.SRCALPHA)
        lw = max(3, 58 - gap)
        for x0 in (6, 124 - lw):
            # pane body: faintly tinted so the glass is present but see-through
            pygame.draw.rect(gl, (116, 178, 196, 30), (x0, 4, lw, 92), border_radius=4)
            pygame.draw.rect(gl, (168, 220, 232, 110), (x0, 4, lw, 92), 2, border_radius=4)
            # the parting edge catches the display light
            ex = x0 + lw - 2 if x0 == 6 else x0 + 1
            pygame.draw.line(gl, (208, 240, 248, 150), (ex, 6), (ex, 94), 2)
            # a specular streak that travels as the pane slides
            sx = x0 + 2 + int(((case_p * 1.7) % 1.0) * max(1, lw - 6))
            pygame.draw.line(gl, (226, 246, 252, 80), (sx, 8), (sx - 6, 92), 2)
        s.blit(gl, (pcx - 65, pcy - 96))
    if 0.0 < case_p < 1.0:
        # pygame's BLEND_RGBA_ADD ignores the source's per-pixel alpha, so the
        # old "subtle bloom" (alpha <=46) added FULL-strength colour and blew the
        # pedestal out to a solid teal disc for most of shot 0. Draw the glow
        # with plain alpha instead: warm, soft-edged, peaking mid-retraction.
        ga = int(74 * math.sin(math.pi * case_p))
        bloom = pygame.Surface((240, 170), pygame.SRCALPHA)
        # nested ellipses sized to FIT the surface - an oversized one gets
        # clipped to the surface rect and reads as a hard-edged haze box
        for rw, rh, al in ((120, 85, ga // 3), (78, 55, ga // 2), (42, 30, ga)):
            pygame.draw.ellipse(bloom, (236, 216, 172, max(4, al)),
                                (120 - rw, 85 - rh, rw * 2, rh * 2))
        s.blit(bloom, (pcx - 120, pcy - 135))

    # ── dossier transform per phase ──
    if phase == "open":
        doc_cx, doc_cy, doc_sc, doc_ang = pcx, pcy - 44, 0.5, 0.0
    elif phase == "take":
        e = u(250, 900)
        e = e * e * (3 - 2 * e)
        doc_cx = _vp_lerp(pcx, 520, e) + hx * 0.5
        doc_cy = _vp_lerp(pcy - 44, 350, e) + hy * 0.5
        doc_sc = _vp_lerp(0.5, 1.7, e)
        doc_ang = _vp_lerp(0.0, -7.0, e)
    else:
        doc_cx, doc_cy, doc_sc, doc_ang = 520 + hx * 0.5, 366 + hy * 0.5, 1.8, -7.0

    # ── hands BEHIND the folder first (palms hidden by it) ──
    hsc = 1.0
    if phase == "take":
        e2 = max(0.0, min(1.0, (ms - 250) / 900))
        if e2 > 0.15:
            hsc = 1.0 + 0.35 * e2
            exL, eyL = doc_cx - 52 * doc_sc, doc_cy + 6 * doc_sc
            # the sleeve must start at the wrist open_hand_dorsal() is given
            # inside _vp_edge_hold_back, else the grip floats above the arm
            _vp_forearm(s, _vp_pinch_wrist(exL, eyL, hsc, 1, doc_ang),
                        _vp_pinch_elbow(exL, eyL, hsc, 1, doc_ang), 38, 24)
            _vp_edge_hold_back(s, exL, eyL, hsc, 1, doc_ang)
    elif phase == "confirm":
        hsc = 1.25
        exL, eyL = doc_cx - 52 * doc_sc, doc_cy + 22 * doc_sc
        exR, eyR = doc_cx + 52 * doc_sc, doc_cy - 6 * doc_sc
        _vp_forearm(s, _vp_pinch_wrist(exL, eyL, hsc, 1, doc_ang),
                    _vp_pinch_elbow(exL, eyL, hsc, 1, doc_ang), 40, 26)
        _vp_edge_hold_back(s, exL, eyL, hsc, 1, doc_ang)
        _vp_forearm(s, _vp_pinch_wrist(exR, eyR, hsc, -1, doc_ang),
                    _vp_pinch_elbow(exR, eyR, hsc, -1, doc_ang), 40, 26)
        _vp_edge_hold_back(s, exR, eyR, hsc, -1, doc_ang)
    elif phase == "open":
        r = u(750, 550)
        if r > 0:
            wx = _vp_lerp(880, 680, r)
            wy = _vp_lerp(780, 560, r)
            _vp_forearm(s, (wx + 26, wy + 34), (900, 830), 40, 26)

    # ── the dossier itself ──
    _v2_dossier(s, int(doc_cx), int(doc_cy), doc_sc, doc_ang)

    # ── hands IN FRONT: fingertips/thumb over the face, stamp, radio ──
    if phase == "open":
        r = u(750, 550)
        if r > 0:
            from core.hands import open_hand_dorsal
            open_hand_dorsal(s, (wx, wy), angle=-18, mirror=-1, sc=1.5 * r + 0.4,
                             spread=1.15)
    elif phase == "take":
        if ms > 250 + 900 * 0.15:
            _vp_edge_hold_front(s, exL, eyL, hsc, 1, cuff_to=(300, 820))
        if 300 < ms < 1300:
            rr = random.Random(5)
            for i in range(10):
                dx = rr.uniform(-50, 50)
                dy = (ms - 300) * rr.uniform(0.05, 0.12) + i * 7
                if doc_cy + dy < 640:
                    s.set_at((int(doc_cx + dx), int(doc_cy + dy)), (150, 140, 116))
    else:
        fl = 0.5 + 0.5 * math.sin(ms * 0.02)
        pygame.draw.rect(s, (18, 20, 22), (128, 560, 34, 74), border_radius=5)
        pygame.draw.rect(s, (60, 64, 68), (128, 560, 34, 74), 1, border_radius=5)
        pygame.draw.rect(s, (90, 200, 210), (134, 568, 22, 8), border_radius=2)
        for k in range(3):
            pygame.draw.arc(s, (120, 220, 230, int(50 + 40 * fl)),
                            (150 - k * 4, 566 - k * 10, 30 + k * 14, 30 + k * 14),
                            math.radians(-70), math.radians(70), 2)
        st_p = u(900, 140)
        if st_p > 0:
            stsc = _vp_lerp(1.45, 1.0, min(1.0, st_p))
            st = pygame.Surface((220, 64), pygame.SRCALPHA)
            pygame.draw.rect(st, (168, 44, 36, int(150 * st_p)), (4, 4, 212, 56), 3)
            f = font_terminal.render(_T("m3.krap_evidence"), True, (186, 62, 50))
            tw = f.get_width()
            if tw > 196:   # was overflowing the stamp's own border
                k2 = 196.0 / tw
                f = pygame.transform.smoothscale(f, (196, max(8, int(f.get_height() * k2))))
            f.set_alpha(int(200 * st_p))
            st.blit(f, (12, 32 - f.get_height() // 2))
            st = pygame.transform.rotozoom(st, -10, stsc)
            s.blit(st, (int(doc_cx - 6 - st.get_width() / 2),
                        int(doc_cy + 34 - st.get_height() / 2)))
        _vp_edge_hold_front(s, exL, eyL, hsc, 1, cuff_to=(250, 820))
        _vp_edge_hold_front(s, exR, eyR, hsc, -1, cuff_to=(830, 820))

    # ── virtual camera: one slow push-in on the prize, continuous across cuts
    ez = lambda v: v * v * (3 - 2 * v)  # noqa: E731
    if phase == "open":
        z = _vp_lerp(1.04, 1.30, ez(u(0, 1250)))
        fx, fy = pcx, pcy - 30
    elif phase == "take":
        z = _vp_lerp(1.30, 1.52, ez(u(0, 1100)))
        fx, fy = doc_cx, doc_cy
    else:
        z = _vp_lerp(1.52, 1.44, ez(u(0, 900)))
        fx, fy = doc_cx, doc_cy - 6
    cam = pygame.transform.smoothscale(_world, (int(WIDTH * z), int(HEIGHT * z)))
    surface.blit(cam, (int(500 - fx * z), int(352 - fy * z)))

    if phase == "confirm" and ms > 1800:
        a = int(255 * min(1.0, (ms - 1800) / 300))
        fk = pygame.Surface((WIDTH, HEIGHT))
        fk.fill((0, 0, 0))
        fk.set_alpha(a)
        surface.blit(fk, (0, 0))

def _game_draw_archives(fcx, fcy):
    """Draw path for the Archives Wing map (Phase 4)."""
    if getattr(STATE, "m3_black_ledger_death_active", False):
        screen.fill((3, 2, 2))
        _draw_black_ledger_death_overlay()
        return

    screen.fill((12, 10, 16))
    cam_x, cam_y = int(round(fcx)), int(round(fcy))
    _M3_CAM[0], _M3_CAM[1] = cam_x, cam_y

    if staticlayer.enabled():
        if not _m3art.blit_layer(screen, "archives_static", cam_x, cam_y):
            _m3_static_layer().blit(screen, cam_x, cam_y, _bake_m3_archives)
        _draw_archives_wing_live(cam_x, cam_y)
    else:
        _render_cell_bg(screen, cam_x, cam_y)
        _draw_m3_exterior_ground(cam_x, cam_y)
        _draw_archives_wing_details(cam_x, cam_y)
        _draw_archives_map_polish(cam_x, cam_y)
    _draw_archives_atmosphere(cam_x, cam_y)
    _draw_m3_doors(cam_x, cam_y)
    _draw_m3_doors_foreground(cam_x, cam_y)

    if STATE.player:
        from entities import death_anim as _da
        if not _da.should_skip_player_draw():
            is_moving = bool(_m3_maps._last_keys) and (
                _m3_maps._last_keys[pygame.K_w] or _m3_maps._last_keys[pygame.K_s]
                or _m3_maps._last_keys[pygame.K_a] or _m3_maps._last_keys[pygame.K_d]
            ) and not _movement_locked()
            _m3_weapon = getattr(STATE, "mission3_weapon", "none")
            _has_firearm = (_m3_weapon not in ("none", "chair_leg", "shiv")
                            and not getattr(STATE, "player_disarmed", False))
            _cw = getattr(STATE, "current_weapon", "pistol")
            reload_duration = 90 if _cw == "os12" else (72 if _cw == "k9_smg" else 60)
            reload_progress = (1.0 - STATE.reload_timer / reload_duration
                               if STATE.is_reloading and STATE.reload_timer > 0 else 0.0)
            reload_progress = max(0.0, min(1.0, reload_progress))
            _animate_player_melee = bool(getattr(STATE, "melee_active", False))
            STATE.player.draw(
                screen, cam_x, cam_y,
                walls=solid_walls_view(),
                reload_active=STATE.is_reloading and _has_firearm,
                reload_progress=reload_progress,
                no_gun=not _has_firearm,
                melee_active=_animate_player_melee,
                melee_progress=_mission3_melee_progress() if _animate_player_melee else 0.0,
                is_moving=is_moving,
            )

    _draw_volkov_ally(cam_x, cam_y)
    _draw_volkov_mags(cam_x, cam_y)
    _draw_archives_nav_arrow(cam_x, cam_y)

    draw_bullets(screen, STATE.bullets, cam_x, cam_y, with_glow=True)
    # Fallen enemy bodies - under the living enemies, over the floor decals.
    for decal in STATE.blood_decals[:]:
        surf = get_blood_decal(decal[3])
        surf.set_alpha(int(decal[2]))
        screen.blit(surf, (decal[0] - decal[3] - cam_x, decal[1] - decal[3] - cam_y))
        decal[2] -= 0.25
        if decal[2] <= 0:
            STATE.blood_decals.remove(decal)
    corpse.draw_corpses(screen, cam_x, cam_y)
    for e in STATE.enemies:
        e.draw(screen, cam_x, cam_y)
        _draw_m3_enemy_type_overlay(screen, e, cam_x, cam_y)
    _draw_black_ledger_inmate(cam_x, cam_y)
    for p in STATE.particles:
        p.draw(screen, cam_x, cam_y)
    for c in STATE.casings:
        c.draw(screen, cam_x, cam_y)
    for pu in STATE.pickups:
        _draw_m3_pickup(screen, pu, cam_x, cam_y)

    _draw_archives_system_prompts(cam_x, cam_y)

    for ft in [ft for ft in STATE.floating_texts if not (len(ft) >= 6 and ft[5] == "pin")]:
        txt = font_terminal_small.render(ft[2], True, ft[3])
        screen.blit(txt, (ft[0] - cam_x - txt.get_width() // 2, ft[1] - cam_y))

    if STATE.player_dead:
        from entities import death_anim
        death_anim.draw_death_overlay(screen, cam_x, cam_y)

    draw_vignette(screen, strength=130)
    draw_scanlines(screen)
    _draw_mission3_hud(screen, cam_x, cam_y)
    _draw_maru_contact_overlay()
    if getattr(STATE, "m3_black_ledger_death_active", False):
        _draw_black_ledger_death_overlay()

    if (STATE.player_dead
            and not getattr(STATE, "m3_black_ledger_death_active", False)):
        from entities import death_anim
        death_anim.apply_camera_tilt(screen)


# ── Slice 5: Kill Order ground-floor draw path ──────────────────────
def _draw_ko_dressing(cam_x, cam_y):
    """Static set dressing for the Kill Order map (5a baseline).

    Stairwell steps, dock crane + van + crate stack, mezzanine stair nosing.
    All world-anchored; culled cheaply by the screen-rect check.
    """
    T = TILE_SIZE

    def vis(wx, wy, pad=96):
        return -pad < wx - cam_x < WIDTH + pad and -pad < wy - cam_y < HEIGHT + pad

    # Pillar cover pockets: cap the 'B' hazard tiles so they read as pillars,
    # not floating caution pads on the lobby floor.
    for bx, by in ((15, 13), (15, 20), (19, 16), (24, 12), (21, 24)):
        _draw_pillar_cap(cam_x, cam_y, bx, by, kind="concrete")

    # Stairwell steps (tower interior, rows 2-3).
    sx, sy = 4 * T - cam_x, 2 * T - cam_y
    if vis(4 * T, 2 * T):
        for i in range(4):
            pygame.draw.rect(screen, (70, 66, 58), (sx + i * 6, sy + 4 + i * 7, T // 2 + 14, 5))
            pygame.draw.line(screen, (40, 38, 32), (sx + i * 6, sy + 9 + i * 7),
                             (sx + i * 6 + T // 2 + 14, sy + 9 + i * 7), 1)
    # Mezzanine stair nosing (above its doorway).
    mx, my = 25 * T - cam_x, 20 * T - cam_y
    if vis(25 * T, 20 * T):
        for i in range(3):
            pygame.draw.line(screen, (60, 56, 48), (mx - 4, my + 6 + i * 8),
                             (mx + 2 * T + 4, my + 6 + i * 8), 2)
    # Dock crane: mast + jib + hook chain.
    cx, cy = 8 * T - cam_x, 34 * T - cam_y
    if vis(8 * T, 34 * T, 160):
        pygame.draw.line(screen, (90, 84, 60), (cx, cy + 3 * T), (cx, cy - T // 2), 5)
        pygame.draw.line(screen, (90, 84, 60), (cx, cy - T // 2), (cx + 4 * T, cy - T // 2), 4)
        pygame.draw.line(screen, (60, 56, 44), (cx + 3 * T, cy - T // 2),
                         (cx + 3 * T, cy + T // 2), 2)
        pygame.draw.rect(screen, (70, 66, 52), (cx + 3 * T - 8, cy + T // 2, 16, 12))
        pygame.draw.rect(screen, (30, 28, 22), (cx - 6, cy + 3 * T - 6, 12, 8))
    # Crate stack (dock NE).
    for (cxx, cyy) in ((35, 33), (36, 33), (36, 34)):
        wx, wy = cxx * T - cam_x, cyy * T - cam_y
        if vis(cxx * T, cyy * T):
            pygame.draw.rect(screen, (85, 70, 45), (wx + 4, wy + 4, T - 8, T - 8))
            pygame.draw.rect(screen, (50, 40, 26), (wx + 4, wy + 4, T - 8, T - 8), 2)
            pygame.draw.line(screen, (50, 40, 26), (wx + 4, wy + 4),
                             (wx + T - 4, wy + T - 4), 1)
    # Volkov's van (exfil): body + cab + wheels. If he bailed (5c), the
    # van is gone and the roof-line cage replaces it at the exfil point.
    if getattr(STATE, "m3_volkov_bailed", False):
        exx, exy = _exfil_pos()
        wxl, wyl = exx - cam_x, exy - cam_y
        if vis(exx, exy, 160):
            pygame.draw.line(screen, (90, 84, 60), (wxl, wyl + 22), (wxl, wyl - 44), 3)
            for i in range(5):
                pygame.draw.line(screen, (70, 66, 50),
                                 (wxl - 9, wyl + 14 - i * 13), (wxl + 9, wyl + 14 - i * 13), 2)
            pygame.draw.rect(screen, (60, 56, 44), (wxl - 12, wyl + 16, 24, 16), 2)
    vx, vy = 31 * T - cam_x, 35 * T - cam_y
    if vis(31 * T, 35 * T, 160) and not getattr(STATE, "m3_volkov_bailed", False):
        # Volkov's armored cargo van, top-down (5d).
        # Deliberately collision-free: the van must stay boardable, it is
        # the exfil point players step onto. Long axis runs east-west; the
        # lit sliding side door faces SOUTH toward the exfil ring.
        bw, bh = int(4 * T - 16), int(T + 18)
        bx, by = vx + 8, vy + 2
        # Ground shadow + warm spill out of the open side door (south).
        render_util.soft_shadow(screen, (bx - 8, by + bh - 6, bw + 16, 22), 110)
        door_cx = bx + bw // 2 + 10
        pool = pygame.Surface((170, 66), pygame.SRCALPHA)
        pygame.draw.ellipse(pool, (255, 205, 140, 20), (0, 8, 170, 50))
        pygame.draw.ellipse(pool, (255, 214, 160, 30), (39, 24, 92, 34))
        screen.blit(pool, (door_cx - 85, by + bh - 10))
        # Body slab (roof seen from above) + bottom shade so it sits grounded.
        body = pygame.Rect(bx, by, bw, bh)
        pygame.draw.rect(screen, (46, 50, 56), body, border_radius=8)
        pygame.draw.rect(screen, (32, 36, 42), (bx, by + bh - 6, bw, 6), border_radius=2)
        pygame.draw.rect(screen, (24, 26, 30), body, 2, border_radius=8)
        # Roof cargo panel + longitudinal ribs.
        pygame.draw.rect(screen, (52, 57, 64), (bx + 64, by + 12, bw - 108, bh - 24), border_radius=4)
        pygame.draw.rect(screen, (36, 40, 47), (bx + 64, by + 12, bw - 108, bh - 24), 1, border_radius=4)
        pygame.draw.line(screen, (70, 76, 84), (bx + 70, by + bh // 2 - 6), (bx + bw - 50, by + bh // 2 - 6), 1)
        pygame.draw.line(screen, (70, 76, 84), (bx + 70, by + bh // 2 + 6), (bx + bw - 50, by + bh // 2 + 6), 1)
        pygame.draw.line(screen, (84, 90, 98), (bx + 10, by + 8), (bx + bw - 10, by + 8), 1)
        # Roof vent + amber beacon (ON the roof, not the edge).
        pygame.draw.rect(screen, (54, 58, 66), (bx + bw // 2 - 34, by + 12, 40, 14))
        pygame.draw.rect(screen, (30, 33, 38), (bx + bw // 2 - 34, by + 12, 40, 14), 1)
        pygame.draw.circle(screen, (70, 60, 30), (bx + bw // 2 + 22, by + 19), 6, 1)
        if not staticlayer.baking():   # amber beacon pulses per frame -> _draw_ko_dressing_live
            _draw_ko_van_beacon(bx, by, bw)
        # Cab at the WEST end: hood nose + transverse windshield band.
        pygame.draw.rect(screen, (40, 44, 51), (bx + 2, by + 6, 16, bh - 12), border_radius=3)
        pygame.draw.rect(screen, (104, 138, 158), (bx + 22, by + 10, 14, bh - 20), border_radius=2)
        pygame.draw.rect(screen, (28, 32, 40), (bx + 22, by + 10, 14, bh - 20), 1, border_radius=2)
        pygame.draw.line(screen, (30, 34, 40), (bx + 29, by + 10), (bx + 29, by + bh - 10), 1)
        pygame.draw.line(screen, (150, 180, 200), (bx + 24, by + 13), (bx + 24, by + bh - 13), 1)
        # Cab side glass on both flanks.
        pygame.draw.rect(screen, (22, 34, 46), (bx + 40, by + 3, 22, 6))
        pygame.draw.rect(screen, (22, 34, 46), (bx + 40, by + bh - 9, 22, 6))
        # Hood bumper + headlights facing west.
        pygame.draw.line(screen, (24, 26, 30), (bx + 2, by + 4), (bx + 2, by + bh - 4), 3)
        pygame.draw.rect(screen, (235, 220, 160), (bx - 3, by + 12, 5, 8))
        pygame.draw.rect(screen, (235, 220, 160), (bx - 3, by + bh - 20, 5, 8))
        # Rear at the EAST end: door seam + handles + bumper + taillights.
        pygame.draw.line(screen, (28, 32, 38), (bx + bw - 20, by + 8), (bx + bw - 20, by + bh - 8), 2)
        pygame.draw.line(screen, (28, 32, 38), (bx + 66, by + bh // 2), (bx + bw - 20, by + bh // 2), 1)
        for hx in (bx + bw - 30, bx + bw - 27):
            pygame.draw.line(screen, (120, 126, 134), (hx, by + bh // 2 - 7), (hx, by + bh // 2 - 3), 1)
            pygame.draw.line(screen, (120, 126, 134), (hx, by + bh // 2 + 3), (hx, by + bh // 2 + 7), 1)
        pygame.draw.line(screen, (24, 26, 30), (bx + bw - 2, by + 4), (bx + bw - 2, by + bh - 4), 3)
        pygame.draw.rect(screen, (168, 44, 40), (bx + bw - 3, by + 12, 5, 9))
        pygame.draw.rect(screen, (168, 44, 40), (bx + bw - 3, by + bh - 21, 5, 9))
        # Open sliding side door on the SOUTH flank: dark mouth + lit sill.
        pygame.draw.rect(screen, (16, 14, 11), (door_cx - 48, by + bh - 13, 96, 11))
        pygame.draw.rect(screen, (255, 210, 145), (door_cx - 44, by + bh - 12, 88, 5))
        pygame.draw.rect(screen, (150, 105, 60), (door_cx - 44, by + bh - 7, 88, 2))
        # Cargo seen top-down inside the mouth: crate + straps.
        pygame.draw.rect(screen, (96, 74, 46), (door_cx - 12, by + bh - 22, 22, 10))
        pygame.draw.rect(screen, (52, 40, 26), (door_cx - 12, by + bh - 22, 22, 10), 1)
        pygame.draw.line(screen, (52, 40, 26), (door_cx - 12, by + bh - 17), (door_cx + 10, by + bh - 17), 1)
        pygame.draw.line(screen, (52, 40, 26), (door_cx - 1, by + bh - 22), (door_cx - 1, by + bh - 12), 1)
        # Reflective tape segments flanking the door + amber north markers.
        pygame.draw.rect(screen, (150, 50, 46), (bx + 14, by + bh - 6, 34, 4))
        pygame.draw.rect(screen, (150, 50, 46), (bx + bw - 48, by + bh - 6, 34, 4))
        pygame.draw.rect(screen, (200, 160, 90), (bx + 14, by + 3, 8, 3))
        pygame.draw.rect(screen, (200, 160, 90), (bx + bw - 22, by + 3, 8, 3))
        # Wheels top-down: dark tire shoulders just peeking past the flanks.
        for wx in (bx + 48, bx + bw - 48):
            pygame.draw.ellipse(screen, (10, 11, 13), (wx - 9, by - 6, 18, 11))
            pygame.draw.ellipse(screen, (10, 11, 13), (wx - 9, by + bh - 5, 18, 11))
            pygame.draw.ellipse(screen, (42, 45, 50), (wx - 5, by - 3, 10, 5))
            pygame.draw.ellipse(screen, (42, 45, 50), (wx - 5, by + bh - 2, 10, 5))
    if not staticlayer.baking():   # shutter cycle + exfil pulse are per-frame
        _draw_ko_dressing_live(cam_x, cam_y)


def _draw_ko_van_beacon(bx, by, bw):
    """Amber roof beacon of Volkov's van (per-frame; ``bx, by, bw`` = van body on screen)."""
    beacon = 0.55 + 0.45 * math.sin(_now_s() * 5)
    pygame.draw.circle(screen, (225, int(110 + 70 * beacon), 60),
                       (bx + bw // 2 + 22, by + 19), 4)


def _draw_ko_dressing_live(cam_x, cam_y):
    """Per-frame part of the Kill Order dressing (drawn right after the static layer): the van's
    roof beacon, the garage shutter cycle and the pulsing exfil marker."""
    T = TILE_SIZE

    def vis(wx, wy, pad=96):
        return -pad < wx - cam_x < WIDTH + pad and -pad < wy - cam_y < HEIGHT + pad

    if vis(31 * T, 35 * T, 160) and not getattr(STATE, "m3_volkov_bailed", False):
        _draw_ko_van_beacon(31 * T - cam_x + 8, 35 * T - cam_y + 2, int(4 * T - 16))
    # Garage shutter cycles open over the holdout (5d).
    cyc = getattr(STATE, "m3_exfil_door_cycle", 0)
    if cyc > 0:
        closed = int((T + 10) * (1.0 - min(1.0, cyc / 2700.0)))
        sx0, sy0 = 30 * T - cam_x, 38 * T - cam_y - 8
        if vis(30 * T, 38 * T, 200):
            pygame.draw.rect(screen, (26, 28, 32), (sx0 - 6, sy0 - 4, 6 * T + 12, T + 12))
            for i in range(0, max(0, closed), 7):
                pygame.draw.line(screen, (58, 62, 70),
                                 (sx0 - 4, sy0 + i), (sx0 + 6 * T + 4, sy0 + i), 3)
            pygame.draw.line(screen, (200, 185, 120),
                             (sx0 - 4, sy0 + closed), (sx0 + 6 * T + 4, sy0 + closed), 2)
    # Exfil marker: pulsing glow + ring at the van door.
    ex, ey = _exfil_pos()
    wx, wy = ex - cam_x, ey - cam_y
    if vis(ex, ey, 160):
        pulse = int(50 + math.sin(_now_s() * 4) * 26)
        glow = get_glow(26, (200, 185, 120), 90)
        glow.set_alpha(pulse)
        screen.blit(glow, (int(wx - 26), int(wy - 26)))
        pygame.draw.circle(screen, (200, 185, 120), (int(wx), int(wy)), 14, 2)


def _draw_ko_nav_arrow(cam_x, cam_y):
    """Edge-of-screen arrow toward the current beat.

    Pre-commit: the nearest sealed beat gate (the authored fight ahead),
    else the live sweep centroid, else the van - the old van-arrow routed
    the sprint straight past the action (2026-09-27 rush fix).
    """
    if not STATE.player or getattr(STATE, "m3_sweep_committed", False):
        return
    wx, wy = STATE.player.rect.centerx, STATE.player.rect.centery
    tx = ty = None
    best = 1e18
    for d in STATE.doors:
        if _m3d(d).ko_beat_gate is None or not d.locked:
            continue
        dd = math.hypot(d.rect.centerx - wx, d.rect.centery - wy)
        if dd < best:
            best = dd
            tx, ty = d.rect.centerx, d.rect.centery
    if tx is None:
        mem = [e for e in STATE.enemies
               if _m3g(e).sweep_team is not None and e.hp > 0]
        if mem:
            tx = sum(e.rect.centerx for e in mem) / len(mem)
            ty = sum(e.rect.centery for e in mem) / len(mem)
    if tx is None:
        tx, ty = _exfil_pos()
    px, py = wx - cam_x, wy - cam_y
    tx, ty = tx - cam_x, ty - cam_y
    if 0 <= tx <= WIDTH and 0 <= ty <= HEIGHT:
        return                      # target already on screen - no arrow needed
    ang = math.atan2(ty - py, tx - px)
    ax, ay = px + math.cos(ang) * 150, py + math.sin(ang) * 150
    ax = max(24, min(WIDTH - 24, ax))
    ay = max(24, min(HEIGHT - 24, ay))
    pts = [(ax + math.cos(ang) * 10, ay + math.sin(ang) * 10),
           (ax + math.cos(ang + 2.5) * 8, ay + math.sin(ang + 2.5) * 8),
           (ax + math.cos(ang - 2.5) * 8, ay + math.sin(ang - 2.5) * 8)]
    pygame.draw.polygon(screen, (200, 185, 120), pts)


def _draw_ko_system_prompts(cam_x, cam_y):
    """Local prompts: sealed beat gates / breach doors + exfil hold notice."""
    if not STATE.player:
        return
    px, py = STATE.player.rect.centerx, STATE.player.rect.centery
    st = getattr(STATE, "m3_sweep", None)
    for d in STATE.doors:
        if math.hypot(d.rect.centerx - px, d.rect.centery - py) >= TILE_SIZE * 2.0:
            continue
        gate = _m3d(d).ko_beat_gate
        if gate is not None and d.locked:
            text = "SEALED, CLEAR SWEEP TEAMS (%d LEFT)" % _ko_sweep._beat_gate_remaining(st, gate)
            color = (200, 150, 90)
        elif _m3d(d).ko_breach and d.locked:
            text = "SEALED, BREACH TEAMS ONLY"
            color = (150, 120, 90)
        else:
            continue
        tag = font_terminal_small.render(text, True, color)
        tag.set_alpha(190)
        screen.blit(tag, (int(d.rect.centerx - cam_x - tag.get_width() // 2),
                          int(d.rect.centery - cam_y - 22)))
    ex, ey = _exfil_pos()
    if math.hypot(ex - px, ey - py) < TILE_SIZE * 2.2:
        tag = font_terminal_small.render(_T("m3.exfil_point_holdout_incoming"), True, (200, 185, 120))
        screen.blit(tag, (int(ex - cam_x - tag.get_width() // 2), int(ey - cam_y - 34)))

def _draw_broadcast_wing_details(cam_x, cam_y):
    """Dress the Broadcast Wing: cable runs, studio lights, cameras, ON AIR."""
    mw, mh = _m3_maps._live_map_dims()
    start_col = max(0, int(cam_x // TILE_SIZE) - 1)
    end_col = min(mw, int((cam_x + WIDTH) // TILE_SIZE) + 2)
    start_row = max(0, int(cam_y // TILE_SIZE) - 1)
    end_row = min(mh, int((cam_y + HEIGHT) // TILE_SIZE) + 2)

    for row in range(start_row, end_row):
        for col in range(start_col, end_col):
            tile = _m3_maps.MISSION3_MAP[row][col]
            x = col * TILE_SIZE - cam_x
            y = row * TILE_SIZE - cam_y

            if tile == "E":
                pygame.draw.rect(screen, (28, 24, 32), (x, y, TILE_SIZE, TILE_SIZE))
                pygame.draw.line(screen, (38, 32, 44), (x, y), (x + TILE_SIZE, y), 1)
                pygame.draw.line(screen, (38, 32, 44), (x, y), (x, y + TILE_SIZE), 1)
            elif tile == ".":
                pygame.draw.rect(screen, (22, 20, 26), (x, y, TILE_SIZE, TILE_SIZE))
                pygame.draw.line(screen, (30, 27, 34), (x, y), (x + TILE_SIZE, y), 1)
                pygame.draw.line(screen, (30, 27, 34), (x, y), (x, y + TILE_SIZE), 1)

    for x0, y0, x1, y1 in _M3_PIPE_RUNS["broadcast"]:
        sx0 = x0 * TILE_SIZE - cam_x
        sy0 = y0 * TILE_SIZE - cam_y
        sx1 = x1 * TILE_SIZE - cam_x
        sy1 = y1 * TILE_SIZE - cam_y
        pygame.draw.line(screen, (50, 48, 56), (sx0, sy0), (sx1, sy1), 2)

    for vx, vy in _M3_VENTS["broadcast"]:
        sx = vx * TILE_SIZE - cam_x
        sy = vy * TILE_SIZE - cam_y
        pygame.draw.rect(screen, (40, 38, 46), (sx + 8, sy + 8, TILE_SIZE - 16, TILE_SIZE - 16), 1)
        for i in range(3):
            pygame.draw.line(screen, (50, 48, 56),
                             (sx + 12, sy + 12 + i * 6),
                             (sx + TILE_SIZE - 12, sy + 12 + i * 6), 1)

    for cx, cy in ((8, 18), (24, 18), (16, 24)):
        sx = cx * TILE_SIZE - cam_x
        sy = cy * TILE_SIZE - cam_y
        if _screen_visible_rect(sx, sy, 1, 1):
            pygame.draw.circle(screen, (70, 65, 85), (sx + TILE_SIZE // 2, sy + TILE_SIZE // 2), 14, 2)
            pygame.draw.circle(screen, (90, 85, 110), (sx + TILE_SIZE // 2, sy + TILE_SIZE // 2), 8)

    if not staticlayer.baking():
        _draw_broadcast_wing_live(cam_x, cam_y)


def _draw_broadcast_wing_live(cam_x, cam_y):
    """Per-frame part of the broadcast dressing: the pulsing ON AIR sign."""
    on_air_x = 15 * TILE_SIZE - cam_x
    on_air_y = 28 * TILE_SIZE - cam_y
    if _screen_visible_rect(on_air_x, on_air_y, 2, 1):
        pulse = 0.5 + 0.5 * math.sin(_now_s() * 2.0)
        r = int(180 + 60 * pulse)
        pygame.draw.rect(screen, (r, 40, 40), (on_air_x - 30, on_air_y - 8, 60, 16))
        txt = font_terminal_small.render(_T("m3.on_air"), True, (255, 220, 220))
        screen.blit(txt, (on_air_x - txt.get_width() // 2, on_air_y - 4))


def _draw_broadcast_map_polish(cam_x, cam_y):
    """Polish pass: subtle atmosphere for the broadcast wing."""
    wash = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
    wash.fill((10, 8, 18, 12))
    screen.blit(wash, (0, 0))


def _game_draw_broadcast(fcx, fcy):
    """Draw path for the Broadcast Wing studio floor (Phase 6, Slice 6)."""
    if getattr(STATE, "m3_black_ledger_death_active", False):
        screen.fill((3, 2, 2))
        _draw_black_ledger_death_overlay()
        return

    screen.fill((16, 14, 20))
    cam_x, cam_y = int(round(fcx)), int(round(fcy))
    _M3_CAM[0], _M3_CAM[1] = cam_x, cam_y

    if staticlayer.enabled():
        if not _m3art.blit_layer(screen, "broadcast_static", cam_x, cam_y):
            _m3_static_layer().blit(screen, cam_x, cam_y, _bake_m3_broadcast)
        _draw_broadcast_wing_live(cam_x, cam_y)
    else:
        _render_cell_bg(screen, cam_x, cam_y)
        _draw_m3_exterior_ground(cam_x, cam_y)
        _draw_broadcast_wing_details(cam_x, cam_y)

    _draw_m3_doors(cam_x, cam_y)
    _draw_m3_doors_foreground(cam_x, cam_y)

    # Station PC - SAME retro terminal art as Mission 2's upload station.
    # DYNAMIC pass: it pulses, so it must not live in the static bake, and
    # it cannot live in _draw_broadcast_wing_details either (that function is
    # the bake callback and is skipped entirely on the cached frames, which
    # is what made the PC invisible).
    _draw_bcast_station_pc(cam_x, cam_y)

    if STATE.player:
        from entities import death_anim as _da
        if not _da.should_skip_player_draw():
            is_moving = bool(_m3_maps._last_keys) and (
                _m3_maps._last_keys[pygame.K_w] or _m3_maps._last_keys[pygame.K_s]
                or _m3_maps._last_keys[pygame.K_a] or _m3_maps._last_keys[pygame.K_d]
            ) and not _movement_locked()
            _m3_weapon = getattr(STATE, "mission3_weapon", "none")
            _has_firearm = (_m3_weapon not in ("none", "chair_leg", "shiv")
                            and not getattr(STATE, "player_disarmed", False))
            _cw = getattr(STATE, "current_weapon", "pistol")
            reload_duration = 90 if _cw == "os12" else (72 if _cw == "k9_smg" else 60)
            reload_progress = (1.0 - STATE.reload_timer / reload_duration
                               if STATE.is_reloading and _has_firearm else 0.0)
            reload_progress = max(0.0, min(1.0, reload_progress))
            _animate_player_melee = bool(getattr(STATE, "melee_active", False))
            STATE.player.draw(
                screen, cam_x, cam_y,
                walls=solid_walls_view(),
                reload_active=STATE.is_reloading and _has_firearm,
                reload_progress=reload_progress,
                no_gun=not _has_firearm,
                melee_active=_animate_player_melee,
                melee_progress=_mission3_melee_progress() if _animate_player_melee else 0.0,
                is_moving=is_moving,
            )

    _draw_volkov_ally(cam_x, cam_y)
    _draw_volkov_mags(cam_x, cam_y)

    draw_bullets(screen, STATE.bullets, cam_x, cam_y, with_glow=True)
    for decal in STATE.blood_decals[:]:
        surf = get_blood_decal(decal[3])
        surf.set_alpha(int(decal[2]))
        screen.blit(surf, (decal[0] - decal[3] - cam_x, decal[1] - decal[3] - cam_y))
        decal[2] -= 0.25
        if decal[2] <= 0:
            STATE.blood_decals.remove(decal)
    corpse.draw_corpses(screen, cam_x, cam_y)
    for e in STATE.enemies:
        e.draw(screen, cam_x, cam_y)
        _draw_m3_enemy_type_overlay(screen, e, cam_x, cam_y)
    for p in STATE.particles:
        p.draw(screen, cam_x, cam_y)
    for c in STATE.casings:
        c.draw(screen, cam_x, cam_y)
    for pu in STATE.pickups:
        _draw_m3_pickup(screen, pu, cam_x, cam_y)

    _draw_broadcast_system_prompts(cam_x, cam_y)

    for ft in [ft for ft in STATE.floating_texts if not (len(ft) >= 6 and ft[5] == "pin")]:
        txt = font_terminal_small.render(ft[2], True, ft[3])
        screen.blit(txt, (ft[0] - cam_x - txt.get_width() // 2, ft[1] - cam_y))

    if STATE.player_dead:
        from entities import death_anim
        death_anim.draw_death_overlay(screen, cam_x, cam_y)

    draw_vignette(screen, strength=130)
    draw_scanlines(screen)
    _draw_mission3_hud(screen, cam_x, cam_y)

    # Station PC upload OS takes over the screen when active.
    from ui import upload_os  # lazy: ui package
    if upload_os.is_upload_os_active():
        upload_os.draw_upload_os(screen)

    if (STATE.player_dead
            and not getattr(STATE, "m3_black_ledger_death_active", False)):
        from entities import death_anim
        death_anim.apply_camera_tilt(screen)


def _draw_bcast_station_pc(cam_x, cam_y):
    """The uplink PC, drawn with Mission 2's retro terminal art.

    Separate from the static bake: the CRT screen pulses, and the bake pass
    only runs on the frames that build a new chunk.
    """
    from missions.m2.draw import _draw_upload_computer  # lazy: cross-mission

    pcx, pcy = _bcast_pc_pos()
    sx, sy = pcx - cam_x, pcy - cam_y
    if not _screen_visible_rect(sx, sy, 3, 3):
        return
    _draw_upload_computer(screen, sx, sy, cam_x, cam_y)
    if getattr(STATE, "m3_bcast_pc_ready", False):
        # Sits above the [E] prompt, which uses sy - 44.
        tag = font_terminal_small.render(_T("m3.station_pc"), True, (120, 235, 165))
        screen.blit(tag, (int(sx - tag.get_width() // 2), int(sy - 62)))


def _draw_broadcast_system_prompts(cam_x, cam_y):
    """Draw the [E] prompt at the control-room station PC."""
    if not STATE.player:
        return
    if not getattr(STATE, "m3_bcast_pc_ready", False):
        return
    from ui import upload_os  # lazy: ui package
    if upload_os.is_upload_os_active():
        return
    px, py = STATE.player.rect.centerx, STATE.player.rect.centery
    pcx, pcy = _bcast_pc_pos()
    if math.hypot(px - pcx, py - pcy) > 110:
        return
    sx, sy = pcx - cam_x, pcy - cam_y
    if not _screen_visible_rect(sx, sy, 2, 2):
        return
    txt = font_terminal_small.render(_T("m3.e_use_station_pc"), True, (200, 185, 230))
    screen.blit(txt, (sx - txt.get_width() // 2, sy - 44))


def _game_draw_kill_order(fcx, fcy):
    """Draw path for the Kill Order ground floor (Phase 5, Slice 5a)."""
    if getattr(STATE, "m3_black_ledger_death_active", False):
        screen.fill((3, 2, 2))
        _draw_black_ledger_death_overlay()
        return

    screen.fill((11, 10, 12))
    cam_x, cam_y = int(round(fcx)), int(round(fcy))
    _M3_CAM[0], _M3_CAM[1] = cam_x, cam_y

    if staticlayer.enabled():
        # RPE6 Phase 3: baked world layer (game.art.m3.ko_static, variant = van / bailed);
        # the runtime chunk bake of the same painters is the fallback.
        if not _m3art.blit_layer(screen, "ko_static", cam_x, cam_y):
            _m3_static_layer().blit(screen, cam_x, cam_y, _bake_m3_ko)
        _draw_ko_dressing_live(cam_x, cam_y)
    else:
        _render_cell_bg(screen, cam_x, cam_y)
        _draw_m3_exterior_ground(cam_x, cam_y)
        _draw_ko_dressing(cam_x, cam_y)
    _draw_m3_doors(cam_x, cam_y)
    _draw_m3_doors_foreground(cam_x, cam_y)

    if STATE.player:
        from entities import death_anim as _da
        if not _da.should_skip_player_draw():
            is_moving = bool(_m3_maps._last_keys) and (
                _m3_maps._last_keys[pygame.K_w] or _m3_maps._last_keys[pygame.K_s]
                or _m3_maps._last_keys[pygame.K_a] or _m3_maps._last_keys[pygame.K_d]
            ) and not _movement_locked()
            _m3_weapon = getattr(STATE, "mission3_weapon", "none")
            _has_firearm = (_m3_weapon not in ("none", "chair_leg", "shiv")
                            and not getattr(STATE, "player_disarmed", False))
            _cw = getattr(STATE, "current_weapon", "pistol")
            reload_duration = 90 if _cw == "os12" else (72 if _cw == "k9_smg" else 60)
            reload_progress = (1.0 - STATE.reload_timer / reload_duration
                               if STATE.is_reloading and STATE.reload_timer > 0 else 0.0)
            reload_progress = max(0.0, min(1.0, reload_progress))
            _animate_player_melee = bool(getattr(STATE, "melee_active", False))
            STATE.player.draw(
                screen, cam_x, cam_y,
                walls=solid_walls_view(),
                reload_active=STATE.is_reloading and _has_firearm,
                reload_progress=reload_progress,
                no_gun=not _has_firearm,
                melee_active=_animate_player_melee,
                melee_progress=_mission3_melee_progress() if _animate_player_melee else 0.0,
                is_moving=is_moving,
            )

    _draw_volkov_ally(cam_x, cam_y)
    _draw_volkov_mags(cam_x, cam_y)
    _draw_ko_nav_arrow(cam_x, cam_y)
    _ko_sweep.draw_overwatch_laser(screen, cam_x, cam_y)

    draw_bullets(screen, STATE.bullets, cam_x, cam_y, with_glow=True)
    # Fallen enemy bodies - under the living enemies, over the floor decals.
    for decal in STATE.blood_decals[:]:
        surf = get_blood_decal(decal[3])
        surf.set_alpha(int(decal[2]))
        screen.blit(surf, (decal[0] - decal[3] - cam_x, decal[1] - decal[3] - cam_y))
        decal[2] -= 0.25
        if decal[2] <= 0:
            STATE.blood_decals.remove(decal)
    corpse.draw_corpses(screen, cam_x, cam_y)
    for e in STATE.enemies:
        e.draw(screen, cam_x, cam_y)
        _draw_m3_enemy_type_overlay(screen, e, cam_x, cam_y)
    for p in STATE.particles:
        p.draw(screen, cam_x, cam_y)
    for c in STATE.casings:
        c.draw(screen, cam_x, cam_y)
    for pu in STATE.pickups:
        _draw_m3_pickup(screen, pu, cam_x, cam_y)

    _draw_ko_system_prompts(cam_x, cam_y)
    # Phase-long alarm: reuse the lockdown strobe, but windowed - one
    # ~1.2s flash cycle every 4s instead of a continuous red strobe.
    if getattr(STATE, "m3_alarm_active", False):
        if getattr(STATE, "m3_alarm_timer", 0) % 240 < 70:
            _draw_m3_alarm_effect(screen)

    for ft in [ft for ft in STATE.floating_texts if not (len(ft) >= 6 and ft[5] == "pin")]:
        txt = font_terminal_small.render(ft[2], True, ft[3])
        screen.blit(txt, (ft[0] - cam_x - txt.get_width() // 2, ft[1] - cam_y))

    if STATE.player_dead:
        from entities import death_anim
        death_anim.draw_death_overlay(screen, cam_x, cam_y)

    draw_vignette(screen, strength=130)
    draw_scanlines(screen)
    _draw_mission3_hud(screen, cam_x, cam_y)

    if (STATE.player_dead
            and not getattr(STATE, "m3_black_ledger_death_active", False)):
        from entities import death_anim
        death_anim.apply_camera_tilt(screen)


def _game_draw_comms(fcx, fcy):
    """Draw path for the separate Comms Wing map."""
    if getattr(STATE, "m3_black_ledger_death_active", False):
        screen.fill((3, 2, 2))
        _draw_black_ledger_death_overlay()
        return

    screen.fill((14, 18, 18))
    cam_x, cam_y = int(round(fcx)), int(round(fcy))
    _M3_CAM[0], _M3_CAM[1] = cam_x, cam_y

    if staticlayer.enabled():
        if not _m3art.blit_layer(screen, "comms_static", cam_x, cam_y):
            _m3_static_layer().blit(screen, cam_x, cam_y, _bake_m3_comms)
    else:
        _render_cell_bg(screen, cam_x, cam_y)
        _draw_m3_exterior_ground(cam_x, cam_y)
        _draw_comms_wing_details(cam_x, cam_y)
        _draw_comms_map_polish(cam_x, cam_y)
    _draw_comms_dynamic_atmosphere(cam_x, cam_y)
    _draw_m3_doors(cam_x, cam_y)
    _draw_m3_doors_foreground(cam_x, cam_y)

    if STATE.player:
        from entities import death_anim as _da
        if not _da.should_skip_player_draw():
            is_moving = bool(_m3_maps._last_keys) and (
                _m3_maps._last_keys[pygame.K_w] or _m3_maps._last_keys[pygame.K_s]
                or _m3_maps._last_keys[pygame.K_a] or _m3_maps._last_keys[pygame.K_d]
            )
            _m3_weapon = getattr(STATE, "mission3_weapon", "none")
            _has_firearm = (_m3_weapon not in ("none", "chair_leg", "shiv")
                            and not getattr(STATE, "player_disarmed", False))
            _cw = getattr(STATE, "current_weapon", "pistol")
            reload_duration = 90 if _cw == "os12" else (72 if _cw == "k9_smg" else 60)
            reload_progress = (1.0 - STATE.reload_timer / reload_duration
                               if STATE.is_reloading and STATE.reload_timer > 0 else 0.0)
            reload_progress = max(0.0, min(1.0, reload_progress))
            _animate_player_melee = bool(getattr(STATE, "melee_active", False))
            STATE.player.draw(
                screen, cam_x, cam_y,
                walls=solid_walls_view(),
                reload_active=STATE.is_reloading and _has_firearm,
                reload_progress=reload_progress,
                no_gun=not _has_firearm,
                melee_active=_animate_player_melee,
                melee_progress=_mission3_melee_progress() if _animate_player_melee else 0.0,
                is_moving=is_moving,
            )

    _draw_volkov_ally(cam_x, cam_y)

    # The Comms Wing has its own early-return draw path, so world objects that
    # only exist in this slice must be rendered here.  Previously the magazines
    # were drawn only in game_draw() *after* the STAGE_COMMS early return, which
    # made Volkov's resupply throw completely invisible even though its physics
    # and ammo grant were running.
    _draw_volkov_mags(cam_x, cam_y)

    draw_bullets(screen, STATE.bullets, cam_x, cam_y, with_glow=True)
    # Fallen enemy bodies - under the living enemies, over the floor decals.
    for decal in STATE.blood_decals[:]:
        surf = get_blood_decal(decal[3])
        surf.set_alpha(int(decal[2]))
        screen.blit(surf, (decal[0] - decal[3] - cam_x, decal[1] - decal[3] - cam_y))
        decal[2] -= 0.25
        if decal[2] <= 0:
            STATE.blood_decals.remove(decal)
    corpse.draw_corpses(screen, cam_x, cam_y)
    for e in STATE.enemies:
        e.draw(screen, cam_x, cam_y)
        _draw_m3_enemy_type_overlay(screen, e, cam_x, cam_y)
    _draw_black_ledger_inmate(cam_x, cam_y)
    for p in STATE.particles:
        p.draw(screen, cam_x, cam_y)
    for c in STATE.casings:
        c.draw(screen, cam_x, cam_y)
    for pu in STATE.pickups:
        _draw_m3_pickup(screen, pu, cam_x, cam_y)
    _draw_comms_system_prompts(cam_x, cam_y)
    _draw_comms_relay_prompt(cam_x, cam_y)
    _draw_objective_waypoint(cam_x, cam_y)
    for ft in [ft for ft in STATE.floating_texts if not (len(ft) >= 6 and ft[5] == "pin")]:
        txt = font_terminal_small.render(ft[2], True, ft[3])
        screen.blit(txt, (ft[0] - cam_x - txt.get_width() // 2, ft[1] - cam_y))

    # The Comms Wing is a separate draw path and returns before game_draw()'s
    # normal death pass. Without this call the standing player was hidden, but
    # the replacement fallen body/blood pool was never drawn, making Biribel
    # appear to sink underneath the floor.
    if STATE.player_dead:
        from entities import death_anim
        death_anim.draw_death_overlay(screen, cam_x, cam_y)

    draw_vignette(screen, strength=125)
    draw_scanlines(screen)
    _draw_mission3_hud(screen, cam_x, cam_y)
    _draw_comms_relay_overlay()
    if getattr(STATE, "m3_black_ledger_death_active", False):
        _draw_black_ledger_death_overlay()

    # Match the normal Mission 3 path: tilt only after the complete scene and
    # HUD have been composed. Applying it earlier can rotate the corpse and then
    # paint floor/HUD layers over it, which looks like the body is buried.
    if (STATE.player_dead
            and not getattr(STATE, "m3_black_ledger_death_active", False)):
        from entities import death_anim
        death_anim.apply_camera_tilt(screen)




# ── bound-hand POV palette (v2 art pass) ─────────────────────────────────
_HAND_SKIN      = (151, 111, 82)
_HAND_SKIN_HI   = (184, 137, 98)
_HAND_SKIN_MID  = (128, 92, 68)
_HAND_SKIN_SH   = (88, 59, 44)
_HAND_SKIN_DEEP = (62, 40, 30)
_HAND_NAIL      = (168, 124, 94)
_HAND_NAIL_EDGE = (104, 70, 52)
_HAND_RIM       = (150, 52, 45)


def _m3_capsule(surf, p1, p2, w, col):
    pygame.draw.line(surf, col, p1, p2, max(1, int(round(w))))
    r = w / 2.0
    pygame.draw.circle(surf, col, (int(round(p1[0])), int(round(p1[1]))), int(round(r)))
    pygame.draw.circle(surf, col, (int(round(p2[0])), int(round(p2[1]))), int(round(r)))


def _draw_bound_hand_v2(surface, hx, side, tick):
    oy = 0  # absolute screen coords in-game
    trem = 1 if (tick // 240) % 2 == 0 else 0
    m = -side                      # direction toward body midline
    out = side                     # direction away from midline
    arm_y = 574

    # --- contact shadow on the chair arm ------------------------------------
    sh = pygame.Surface((200, 40), pygame.SRCALPHA)
    render_util.soft_shadow(sh, (8, 6, 184, 30), 90)
    surface.blit(sh, (hx - 100, arm_y + 8 + oy))

    # --- chair arm -----------------------------------------------------------
    pygame.draw.rect(surface, (18, 16, 13), (hx - 92, arm_y + 14 + oy, 184, 48), border_radius=15)
    pygame.draw.rect(surface, (42, 36, 29), (hx - 88, arm_y + 4 + oy, 176, 34), border_radius=13)
    pygame.draw.line(surface, (82, 75, 65), (hx - 76, arm_y + 9 + oy), (hx + 76, arm_y + 9 + oy), 2)
    pygame.draw.line(surface, (8, 7, 6), (hx - 76, arm_y + 38 + oy), (hx + 76, arm_y + 38 + oy), 2)

    # --- sleeve / forearm ----------------------------------------------------
    sleeve, sleeve_hi = (36, 43, 38), (55, 62, 54)
    forearm = [(hx - side * 56, 678 + oy), (hx + side * 34, 678 + oy),
               (hx + side * 31, 602 + oy), (hx - side * 36, 596 + oy)]
    pygame.draw.polygon(surface, sleeve, forearm)
    pygame.draw.line(surface, sleeve_hi, forearm[2], forearm[3], 2)
    pygame.draw.line(surface, (12, 14, 12), forearm[0], forearm[3], 2)
    # cloth fold ticks
    pygame.draw.line(surface, (24, 29, 25), (hx - side * 20, 640 + oy), (hx + side * 14, 636 + oy), 1)
    pygame.draw.line(surface, (24, 29, 25), (hx - side * 16, 660 + oy), (hx + side * 18, 656 + oy), 1)

    # wrist creases above the cuff
    pygame.draw.arc(surface, _HAND_SKIN_MID, (hx - 26, 574 + oy, 52, 14), math.radians(200), math.radians(340), 1)
    pygame.draw.arc(surface, _HAND_SKIN_MID, (hx - 22, 578 + oy, 44, 12), math.radians(200), math.radians(340), 1)
    # Reference-anatomy hand (dorsal, spread fingers, long 45-degree thumb)
    # from the shared hand model in core.hands.
    open_hand_dorsal(surface, (hx, 586 + oy), angle=0.0, mirror=m, sc=1.0,
                     spread=1.0, trem=trem, rim=_HAND_RIM)

    # --- cuff -----------------------------------------------------------------
    cuff_o = pygame.Rect(hx - 54, 574 + oy, 108, 26)
    pygame.draw.rect(surface, (16, 17, 18), cuff_o.inflate(4, 4), border_radius=11)
    pygame.draw.rect(surface, (26, 27, 28), cuff_o, border_radius=10)
    pygame.draw.rect(surface, (86, 88, 84), (hx - 49, 578 + oy, 98, 17), border_radius=7)
    pygame.draw.line(surface, (168, 168, 156), (hx - 44, 580 + oy), (hx + 44, 580 + oy), 1)
    pygame.draw.arc(surface, (40, 41, 40), (hx - 49, 578 + oy, 98, 17), math.radians(10), math.radians(170), 2)
    # hinge lug + rivets (outer side), keyhole inward
    lug = pygame.Rect(hx + side * 46 - 5, 576 + oy, 11, 22)
    pygame.draw.rect(surface, (34, 35, 36), lug, border_radius=3)
    pygame.draw.rect(surface, (120, 120, 112), lug, 1, border_radius=3)
    pygame.draw.circle(surface, (18, 18, 18), (lug.centerx, lug.top + 4), 2)
    pygame.draw.circle(surface, (18, 18, 18), (lug.centerx, lug.bottom - 4), 2)
    pygame.draw.circle(surface, (14, 14, 14), (hx - side * 30, 586 + oy), 3)
    pygame.draw.line(surface, (60, 60, 56), (hx - side * 30, 586 + oy), (hx - side * 30, 590 + oy), 1)

    # --- chain to arm anchor ---------------------------------------------------
    anchor = (hx + side * 74, arm_y + 25 + oy)
    pygame.draw.circle(surface, (24, 24, 23), anchor, 9)
    pygame.draw.circle(surface, (116, 116, 108), anchor, 9, 2)
    pygame.draw.circle(surface, (10, 10, 10), anchor, 4)
    x0, y0 = hx + side * 52, 588 + oy
    for k in range(4):
        t = (k + 1) / 5
        lx = int(x0 + (anchor[0] - x0) * t)
        ly = int(y0 + (anchor[1] - y0) * t + math.sin(k * 1.7) * 3)
        link = pygame.Rect(lx - 7, ly - 4, 14, 9)
        pygame.draw.ellipse(surface, (20, 20, 19), link.inflate(3, 3))
        pygame.draw.ellipse(surface, (126, 126, 116), link, 2)
        pygame.draw.ellipse(surface, (70, 70, 64), link.move(1, 1), 1)

    # --- red rim light over hand silhouette ------------------------------------
    pygame.draw.arc(surface, _HAND_RIM, (hx - 36, 540 + oy, 72, 26), math.radians(200), math.radians(340), 1)


def _draw_interrogation_monitor_view():
    """Interactive Mission 3 interrogation staging: restrained POV at monitor.

    This replaces the top-down cell view ONLY while STAGE_INTERROGATION is
    active.  The dialogue tree/input is unchanged; only the camera language
    changes so the scene reads as Biribel staring at Balaceanu's monitor, not
    a gameplay map with an overlay.
    """
    beat = _current_beat()
    ticks = _now_ms()
    btype = beat.get("type") if beat else "line"
    speaker = beat.get("speaker", "") if beat else ""
    accent = beat.get("color", C_BIRIBEL) if beat else C_BIRIBEL

    # Concrete wall / black-site room.  Everything is screen-space because this
    # is a restrained POV, not a movable gameplay camera.
    screen.fill((5, 6, 8))
    for y in range(0, HEIGHT, 4):
        shade = 9 + int(10 * (y / HEIGHT))
        pygame.draw.rect(screen, (shade, shade + 1, shade + 3), (0, y, WIDTH, 4))

    # Dirty wall texture.
    rng = random.Random(3003)
    for _ in range(130):
        x = rng.randrange(0, WIDTH)
        y = rng.randrange(0, HEIGHT)
        col = rng.choice([(18, 19, 21), (22, 20, 18), (12, 13, 15), (28, 25, 22)])
        a = rng.randrange(24, 70)
        s = pygame.Surface((rng.randrange(8, 38), rng.randrange(1, 5)), pygame.SRCALPHA)
        s.fill((*col, a))
        screen.blit(s, (x, y))

    # Monitor glow on wall.
    mon = pygame.Rect(145, 58, 710, 390)
    glow = pygame.Surface((mon.w + 170, mon.h + 170), pygame.SRCALPHA)
    glow_col = (105, 18, 18) if (speaker == "BALACEANU" or _m3_flow._monitor_on) else (35, 45, 48)
    for i in range(18):
        a = int(42 * (1 - i / 18) ** 2)
        pygame.draw.rect(glow, (*glow_col, a), glow.get_rect().inflate(-i * 9, -i * 9), border_radius=28)
    screen.blit(glow, (mon.x - 85, mon.y - 85))

    # Heavy monitor housing.
    pygame.draw.rect(screen, (3, 4, 5), mon.inflate(34, 34), border_radius=12)
    pygame.draw.rect(screen, (28, 30, 30), mon.inflate(24, 24), 3, border_radius=10)
    pygame.draw.rect(screen, (0, 1, 2), mon, border_radius=5)

    # Monitor surface.
    crt = pygame.Surface(mon.size, pygame.SRCALPHA)
    live = speaker == "BALACEANU" or (beat and beat.get("type") == "action" and beat.get("action") in {"monitor_on", "broadcast_caption"}) or _m3_flow._monitor_on
    base = (24, 5, 6) if live else (4, 8, 9)
    crt.fill((*base, 255))

    # CRT scan/noise.
    for yy in range(0, mon.h, 3):
        pygame.draw.line(crt, (0, 0, 0, 60), (0, yy), (mon.w, yy))
    noise_rng = random.Random(ticks // 80)
    for _ in range(90 if live else 55):
        nx = noise_rng.randrange(0, mon.w)
        ny = noise_rng.randrange(0, mon.h)
        na = noise_rng.randrange(16, 55)
        pygame.draw.rect(crt, (180, 45, 45, na) if live else (80, 110, 110, na), (nx, ny, noise_rng.randrange(2, 10), 1))

    # Balaceanu on the monitor / dead screen.  IMPORTANT: match the existing
    # campaign design from cutscenes._m3_draw_balaceanu(): tailored dark suit,
    # red tie, rigid posture, and VOSTRAL folder/tablet.  Do not invent a new
    # face here; this is a degraded state-TV feed of the same character.
    if live:
        pulse = 0.5 + 0.5 * math.sin(ticks * 0.004)
        cx = mon.w // 2

        # Broadcast backdrop: red institutional field with a faint podium/flag
        # shape, so the full-body Balaceanu figure reads like a state address.
        pygame.draw.rect(crt, (20, 4, 5, 255), (0, 0, mon.w, mon.h))
        pygame.draw.rect(crt, (42, 8, 9, 185), (60, 54, mon.w - 120, mon.h - 88), border_radius=4)
        pygame.draw.line(crt, (120, 26, 24, 95), (85, 86), (mon.w - 85, 86), 1)
        pygame.draw.line(crt, (120, 26, 24, 75), (85, mon.h - 72), (mon.w - 85, mon.h - 72), 1)
        for sx in (cx - 230, cx + 230):
            pygame.draw.polygon(crt, (65, 12, 14, 80), [(sx, 80), (sx + 34, 260), (sx - 18, 350), (sx - 50, 150)])

        # Draw the actual existing Balaceanu figure from cutscenes.py to a
        # transparent feed layer, then tint/degrade it with CRT effects.
        feed = pygame.Surface(mon.size, pygame.SRCALPHA)
        _m3cell._m3_draw_balaceanu(feed, cx, mon.h - 26, scale=1.10, facing_left=True)

        # Red monitor grading: keep recognisable suit/tie/folder colors, but
        # wash them into the CRT palette so it still feels like a transmission.
        red_wash = pygame.Surface(mon.size, pygame.SRCALPHA)
        red_wash.fill((22, 2, 2, 58))
        feed.blit(red_wash, (0, 0), special_flags=pygame.BLEND_RGBA_ADD)

        # Slight ghost offset to mimic analog signal bleed without changing the
        # character design.
        ghost = feed.copy()
        ghost.set_alpha(58)
        crt.blit(ghost, (3, 0))
        crt.blit(feed, (0, 0))

        # State-TV crop around the real figure.
        pygame.draw.rect(crt, (150, 38, 34, 105), (cx - 155, 56, 310, 306), 1)
        pygame.draw.rect(crt, (255, 80, 55, int(22 + 24 * pulse)), (cx - 151, 60, 302, 298), 1)

        # Subtle scan hotspot around head/shoulders, not a new face.
        head_glow = pygame.Surface(mon.size, pygame.SRCALPHA)
        _ha = int(34 + 28 * pulse)
        pygame.draw.ellipse(head_glow, (160 * _ha // 255, 36 * _ha // 255, 32 * _ha // 255, _ha), (cx - 82, 62, 164, 116), 2)
        crt.blit(head_glow, (0, 0), special_flags=pygame.BLEND_ADD)
    else:
        pygame.draw.line(crt, (55, 75, 78, 95), (40, mon.h // 2), (mon.w - 40, mon.h // 2), 1)
        pygame.draw.line(crt, (55, 75, 78, 65), (mon.w // 2, 40), (mon.w // 2, mon.h - 40), 1)

    # In-monitor surveillance labels, not external HUD.
    rec_on = (ticks // 360) % 2 == 0
    if rec_on:
        pygame.draw.circle(crt, (190, 25, 25, 190), (24, 24), 4)
    lab = font_terminal_small.render(_T("m3.cell_03_recording"), True, (125, 110, 105) if live else (80, 105, 105))
    lab.set_alpha(145)
    crt.blit(lab, (36, 15))
    stamp = font_terminal_small.render(_T("m3.22_00_address_pending"), True, (125, 72, 72))
    stamp.set_alpha(130)
    crt.blit(stamp, (mon.w - stamp.get_width() - 22, 15))

    # Dialogue as part of the monitor/room composition.
    if beat:
        if btype == "action":
            caption, cap_color = _ACTION_CAPTIONS.get(beat.get("action"), ("[...]", C_SYSTEM))
            visible = caption[:_m3_flow._dialogue_char_idx]
            lines = _wrap(visible, font_terminal, mon.w - 100)
            yy = mon.h - 92
            for i, ln in enumerate(lines[:2]):
                surf = font_terminal.render(ln, True, cap_color)
                surf.set_alpha(min(230, max(30, _m3_flow._dialogue_char_idx * 8 - i * 35)))
                crt.blit(surf, ((mon.w - surf.get_width()) // 2, yy + i * 28))

        elif btype == "line" and speaker == "BALACEANU":
            full_text = beat.get("text", "")
            visible = full_text[:_m3_flow._dialogue_char_idx]
            lines = _wrap(visible, font_dialogue, mon.w - 110)
            yy = mon.h - 112
            name = font_terminal_small.render(_T("m3.balaceanu_prerecorded"), True, C_BALACEANU)
            name.set_alpha(185)
            crt.blit(name, (54, yy - 26))
            for i, ln in enumerate(lines[:3]):
                surf = font_dialogue.render(ln, True, (232, 205, 198))
                surf.set_alpha(min(238, max(25, _m3_flow._dialogue_char_idx * 8 - i * 38)))
                crt.blit(surf, (54, yy + i * 27))

        elif btype == "choice":
            # The prompt/choices appear as faint response telemetry reflected in
            # the CRT glass - still readable, but no boxes/cards/overlay panel.
            prompt = beat.get("prompt", "Choose:")
            visible_prompt = prompt[:_m3_flow._dialogue_char_idx]
            lines = _wrap(visible_prompt, font_dialogue, mon.w - 130)
            yy = mon.h - 155
            for i, ln in enumerate(lines[:2]):
                surf = font_dialogue.render(ln, True, C_PROMPT)
                surf.set_alpha(min(210, max(20, _m3_flow._dialogue_char_idx * 8 - i * 35)))
                crt.blit(surf, (66, yy + i * 27))
            if _line_fully_typed(beat):
                opt_y = yy + 62
                for i, (label, _line) in enumerate(beat.get("options", [])):
                    selected = i == _m3_flow._dialogue_choice
                    prefix = ">" if selected else " "
                    col = (245, 220, 145) if selected else (135, 135, 130)
                    alpha = 230 if selected else 130
                    surf = font_dialogue.render(_T("m3.prefix_label", label=label, prefix=prefix), True, col)
                    surf.set_alpha(alpha)
                    crt.blit(surf, (92, opt_y + i * 28))
                    if selected:
                        pulse = int(45 + 35 * (0.5 + 0.5 * math.sin(ticks * 0.007)))
                        pygame.draw.line(crt, (*C_PROMPT, pulse), (94, opt_y + i * 28 + 24), (310, opt_y + i * 28 + 24), 1)

    screen.blit(crt, mon.topleft)
    pygame.draw.rect(screen, (120, 26, 24, 105) if live else (70, 90, 92, 90), mon, 2, border_radius=5)

    # Restraints / hands in foreground to sell the first-person chair POV.
    table_y = 535
    table = pygame.Surface((WIDTH, HEIGHT - table_y), pygame.SRCALPHA)
    pygame.draw.polygon(table, (12, 11, 10, 235), [(80, 70), (WIDTH - 80, 70), (WIDTH, HEIGHT - table_y), (0, HEIGHT - table_y)])
    pygame.draw.line(table, (46, 41, 35, 165), (90, 72), (WIDTH - 90, 72), 2)
    screen.blit(table, (0, table_y))

    # Chair arms, forearms, hands, and cuffs.  These are intentionally drawn
    # with asymmetry and perspective so they read as Biribel's restrained POV,
    # not two flat cartoon ovals pasted over the scene.
    def _draw_bound_hand(hx, side):
        # v2 art pass: real hand anatomy lives in module-level
        # _draw_bound_hand_v2 (tapered phalanges, knuckles, nails, thumb,
        # seated cuff + chain). Kept as a thin closure so the call sites
        # below stay unchanged.
        _draw_bound_hand_v2(screen, hx, side, _now_ms())

    _draw_bound_hand(310, -1)
    _draw_bound_hand(690, 1)

    # Biribel/Volkov lines are not on the monitor; they sit low in the room as
    # restrained mutters, still without a panel.
    if beat and btype == "line" and speaker != "BALACEANU":
        full_text = beat.get("text", "")
        visible = full_text[:_m3_flow._dialogue_char_idx]
        lines = _wrap(visible, font_dialogue, WIDTH - 180)
        name = font_terminal_small.render(speaker.upper(), True, accent)
        name.set_alpha(175)
        screen.blit(name, (88, 478))
        pygame.draw.line(screen, (*accent, 105), (88, 500), (172, 500), 1)
        for i, ln in enumerate(lines[:3]):
            _draw_text_shadowed(screen, font_dialogue, ln, (88, 510 + i * 27), (224, 226, 224), alpha=min(230, max(25, _m3_flow._dialogue_char_idx * 8 - i * 38)))

    # Instructions are tiny and almost dead, not a UI prompt.
    if beat and _line_fully_typed(beat) and not _action_is_unskippable(beat):
        hint = "ENTER" if btype == "choice" else "SPACE / ENTER"
        if btype == "choice":
            hint = "UP/DOWN  ENTER"
        h = font_terminal_small.render(hint, True, (90, 86, 78))
        h.set_alpha(int(80 + 35 * (0.5 + 0.5 * math.sin(ticks * 0.004))))
        screen.blit(h, (WIDTH - h.get_width() - 30, HEIGHT - 28))

    # Final oppressive vignette and scanlines.
    draw_vignette(screen, strength=215)
    draw_scanlines(screen)


def _clamp_m3_camera(cx, cy):
    """Clamp desired camera top-left to the Mission 3 map bounds."""
    mw, mh = _m3_maps._live_map_dims()
    max_x = max(0, mw * TILE_SIZE - WIDTH)
    max_y = max(0, mh * TILE_SIZE - HEIGHT)
    return max(0, min(int(cx), max_x)), max(0, min(int(cy), max_y))


def _ease_in_out(p):
    p = max(0.0, min(1.0, p))
    return p * p * (3.0 - 2.0 * p)


def _mission3_breach_camera():
    """Cinematic camera director for Volkov's breach.

    The breach choreography already exists in world space; this function makes
    the camera *show* it:
      - starts near Biribel's restrained chair,
      - pans/leans to the door as boots/charge become important,
      - holds on Volkov planting/backing away,
      - kicks hard on detonation,
      - settles between Biribel and the blown doorway for Volkov's line.
    """
    chair_x, chair_y = _interrogation_chair_pos()
    door_x = _DOOR_TILE_COL * TILE_SIZE + TILE_SIZE
    door_y = _DOOR_TILE_ROW * TILE_SIZE + TILE_SIZE // 2
    t = max(0, _m3_flow._volkov_breach_t)

    # Volkov, if available, becomes the moving focus. Otherwise use doorway.
    pose = _volkov_world_pose()
    if pose:
        vx, vy, _ang, _running = pose
    else:
        vx, vy = door_x, door_y

    # Stage targets.  Offsets bias the camera so the relevant subject sits in
    # the upper/middle of frame instead of dead-center under UI text.
    chair_cam = (chair_x - WIDTH * 0.50, chair_y - HEIGHT * 0.55)
    door_cam = (door_x - WIDTH * 0.50, door_y - HEIGHT * 0.43)
    volkov_cam = (vx - WIDTH * 0.50, vy - HEIGHT * 0.46)
    two_shot_cam = (((chair_x + door_x) * 0.5) - WIDTH * 0.50,
                    ((chair_y + door_y) * 0.5) - HEIGHT * 0.48)

    if t < 55:
        # Snap out of monitor POV and begin turning toward the noise.
        p = _ease_in_out(t / 55.0)
        cam_x = chair_cam[0] + (two_shot_cam[0] - chair_cam[0]) * p
        cam_y = chair_cam[1] + (two_shot_cam[1] - chair_cam[1]) * p
    elif t < 145:
        # Track Volkov as he reaches/works at the door.
        p = _ease_in_out((t - 55) / 90.0)
        cam_x = two_shot_cam[0] + (volkov_cam[0] - two_shot_cam[0]) * p
        cam_y = two_shot_cam[1] + (volkov_cam[1] - two_shot_cam[1]) * p
    elif t < 260:
        # Hold on the planted charge / Volkov backing away. Small breathing sway.
        cam_x, cam_y = door_cam
        cam_x += math.sin(t * 0.055) * 4
        cam_y += math.sin(t * 0.041 + 1.2) * 3
    elif t < 306:
        # Pre-blast tension: slowly drift wider so the whole doorway reads.
        p = _ease_in_out((t - 260) / 46.0)
        cam_x = door_cam[0] + (two_shot_cam[0] - door_cam[0]) * p
        cam_y = door_cam[1] + (two_shot_cam[1] - door_cam[1]) * p
    else:
        # After detonation: settle on the blown doorway and Volkov entering.
        p = _ease_in_out(min(1.0, (t - 306) / 90.0))
        cam_x = door_cam[0] + (two_shot_cam[0] - door_cam[0]) * p
        cam_y = door_cam[1] + (two_shot_cam[1] - door_cam[1]) * p

    # Impact shake around detonation and first entrance frames.
    shake = 0
    if 296 <= t <= 340:
        shake = int(max(0, 18 * (1.0 - abs(t - 306) / 44.0)))
    elif 341 <= t <= 390:
        shake = int(max(0, 7 * (1.0 - (t - 341) / 49.0)))
    if shake > 0 and not getattr(STATE, "reduced_motion", False):
        # Deterministic per-frame shake so screenshots are stable for a given t.
        rng = random.Random(9100 + int(t))
        cam_x += rng.randint(-shake, shake)
        cam_y += rng.randint(-shake, shake)

    return _clamp_m3_camera(cam_x, cam_y)


def _draw_breach_cinematic_letterbox():
    """Subtle letterbox during the breach so it reads as directed action."""
    h = 46
    top = pygame.Surface((WIDTH, h), pygame.SRCALPHA)
    bot = pygame.Surface((WIDTH, h), pygame.SRCALPHA)
    top.fill((0, 0, 0, 190))
    bot.fill((0, 0, 0, 190))
    screen.blit(top, (0, 0))
    screen.blit(bot, (0, HEIGHT - h))

def game_draw(fcx, fcy):
    if artpack.enabled():
        lighting.buffer().begin_frame(_m3_wing_name(), _m3_doors_sig())
    _game_draw_inner(fcx, fcy)
    if artpack.enabled() and not getattr(STATE, "m3_black_ledger_death_active", False):
        _push_m3_lights(_M3_CAM[0], _M3_CAM[1], _now_s())
        lighting.buffer().composite(screen, _now_s())
    _draw_m3_combat_reticle()


def _draw_m3_combat_reticle():
    """Orange combat reticle, matching M1/M2 (M3 previously drew none).

    Suppressed while restrained in the interrogation (monitor POV / breach
    cinematic - not aiming) and while the crafting overlay owns the mouse.
    """
    if getattr(STATE, "mission3_stage", STAGE_INTERROGATION) == STAGE_INTERROGATION:
        return
    if getattr(STATE, "mission3_crafting_active", False):
        return
    # While the upload OS is up it owns the pointer and draws its own CRT
    # arrow; app.py already suppresses hud.draw_crosshair in that state, so
    # drawing the combat reticle too left two cursors stacked on the mouse.
    try:
        from ui import upload_os as _upload_os
        if _upload_os.is_upload_os_active():
            return
    except ImportError:
        pass
    draw_combat_reticle(screen)


def _game_draw_inner(fcx, fcy):
    if getattr(STATE, "m3_black_ledger_death_active", False):
        screen.fill((3, 2, 2))
        _draw_black_ledger_death_overlay()
        return

    stage_now = getattr(STATE, "mission3_stage", STAGE_INTERROGATION)

    if stage_now == STAGE_COMMS:
        _game_draw_comms(fcx, fcy)
        return

    if stage_now == STAGE_ARCHIVES:
        _game_draw_archives(fcx, fcy)
        return

    if stage_now == STAGE_KILL_ORDER:
        # Slice 5a: own ground-floor map + draw path.
        _game_draw_kill_order(fcx, fcy)
        return

    if stage_now == STAGE_BROADCAST:
        # Slice 6: own studio-floor map + draw path.
        _game_draw_broadcast(fcx, fcy)
        return

    # Interactive interrogation uses a restrained-chair monitor POV instead of
    # the normal top-down gameplay renderer, BUT only until Volkov's breach.
    # Once the breach starts, the monitor POV ends and the scene returns to the
    # real cell so the door, C4, flash, and Volkov entrance are physically seen.
    if stage_now == STAGE_INTERROGATION:
        beat = _current_beat()
        breach_started = (
            _m3_flow._volkov_breach_t >= 0
            or (beat is not None and beat.get("type") == "action" and beat.get("action") == "breach")
            or (beat is not None and beat.get("speaker") == "VOLKOV")
        )
        if not breach_started:
            _draw_interrogation_monitor_view()
            return

        # Directed breach camera: pan from Biribel's chair to the door/Volkov,
        # hold on charge placement, shake on detonation, then settle for the
        # doorway entrance. This replaces the old static chair-centered view.
        if _m3_flow._volkov_breach_t >= 0:
            fcx, fcy = _mission3_breach_camera()
        else:
            _cx, _cy = _interrogation_chair_pos()
            fcx, fcy = _clamp_m3_camera(_cx - WIDTH // 2, _cy - HEIGHT // 2)

    screen.fill((18, 18, 22))
    cam_x, cam_y = int(round(fcx)), int(round(fcy))
    _M3_CAM[0], _M3_CAM[1] = cam_x, cam_y

    if staticlayer.enabled():
        if not _m3art.blit_layer(screen, "cellblock_static", cam_x, cam_y):
            _m3_static_layer().blit(screen, cam_x, cam_y, _bake_m3_static)
        _draw_m3_static_live(cam_x, cam_y)
    else:
        _render_cell_bg(screen, cam_x, cam_y)
        _draw_m3_exterior_ground(cam_x, cam_y)
        _draw_m3_background_dressing(cam_x, cam_y)
        _draw_m3_corridor_and_map_details(cam_x, cam_y)
    _draw_m3_dynamic_tiles(cam_x, cam_y)
    _draw_m3_doors(cam_x, cam_y)

    if getattr(STATE, "m3_hide_molotov", False):
        STATE.show_molotov_hud = False
    else:
        STATE.show_molotov_hud = True

    stage = getattr(STATE, "mission3_stage", STAGE_INTERROGATION)

    # Static world detail pass. Keep doors/props behind actors so the player is
    # never visually swallowed by an open doorway tile.
    if staticlayer.enabled():
        # RPE6 Phase 3: the cells themselves are part of the static world layer
        # (game.art.m3.cellblock_static); tubes flicker and flies move live.
        _draw_neighbor_cells_live(cam_x, cam_y)
    else:
        _draw_neighbor_cells(cam_x, cam_y)
    _draw_cell_room(cam_x, cam_y)
    _draw_m3_doors_foreground(cam_x, cam_y)
    _draw_m3_detainees(cam_x, cam_y)

    # Volkov mags resupply (Comms Wing)
    _draw_volkov_mags(cam_x, cam_y)

    # Player - skip during death animation (fallen body drawn by death_anim).
    if STATE.player:
        from entities import death_anim as _da
        if not _da.should_skip_player_draw():
            if stage == STAGE_INTERROGATION:
                _draw_interrogation_restrained_player(cam_x, cam_y)
            else:
                is_moving = bool(_m3_maps._last_keys) and (
                    _m3_maps._last_keys[pygame.K_w] or _m3_maps._last_keys[pygame.K_s]
                    or _m3_maps._last_keys[pygame.K_a] or _m3_maps._last_keys[pygame.K_d]
                ) and not _movement_locked()
                _m3_weapon = getattr(STATE, "mission3_weapon", "none")
                _animate_player_melee = (getattr(STATE, "melee_active", False)
                                         and _m3_weapon != "shiv")
                # Once the sidearm is acquired, the player has a real firearm -
                # pass no_gun=False so Player.draw renders the pistol. While the
                # player only has the chair_leg/shiv (or nothing), keep no_gun=True
                # so the improvised weapon overlay (_draw_mission3_hand_weapon
                # below) is the only weapon shown.
                _has_firearm = (_m3_weapon not in ("none", "chair_leg", "shiv")
                                and not getattr(STATE, "player_disarmed", False))

                # Match Mission 1 / Mission 2's player reload animation path.
                _cw = getattr(STATE, "current_weapon", "pistol")
                reload_duration = 90 if _cw == "os12" else (72 if _cw == "k9_smg" else 60)
                reload_progress = (
                    1.0 - STATE.reload_timer / reload_duration
                    if STATE.is_reloading and STATE.reload_timer > 0 else 0.0
                )
                reload_progress = max(0.0, min(1.0, reload_progress))

                STATE.player.draw(
                    screen, cam_x, cam_y,
                    walls=solid_walls_view(),
                    reload_active=STATE.is_reloading and _has_firearm,
                    reload_progress=reload_progress,
                    no_gun=not _has_firearm,
                    melee_active=_animate_player_melee,
                    melee_progress=_mission3_melee_progress() if _animate_player_melee else 0.0,
                    is_moving=is_moving,
                )

    # Bullets (player + enemy fire).
    draw_bullets(screen, STATE.bullets, cam_x, cam_y, with_glow=True)

    # Enemies (IPA cell-block guards). Drawn after bullets so a guard
    # hit by a bullet appears in front of the impact particle (matches
    # M2's z-order).
    # Fallen enemy bodies - under the living enemies, over the floor decals.
    for decal in STATE.blood_decals[:]:
        surf = get_blood_decal(decal[3])
        surf.set_alpha(int(decal[2]))
        screen.blit(surf, (decal[0] - decal[3] - cam_x, decal[1] - decal[3] - cam_y))
        decal[2] -= 0.25
        if decal[2] <= 0:
            STATE.blood_decals.remove(decal)
    corpse.draw_corpses(screen, cam_x, cam_y)
    for e in STATE.enemies:
        e.draw(screen, cam_x, cam_y)
        _draw_m3_enemy_type_overlay(screen, e, cam_x, cam_y)
    _draw_black_ledger_inmate(cam_x, cam_y)

    # Particles (impact sparks, blood bursts, metal filings).
    for p in STATE.particles:
        p.draw(screen, cam_x, cam_y)

    # Shell casings ejected from firearms.
    for c in STATE.casings:
        c.draw(screen, cam_x, cam_y)

    # Blood decals (fading pools from killed enemies).

    # Fire zones (molotov burning areas).
    for fz in STATE.fire_zones:
        fz.draw(screen, cam_x, cam_y)

    # Security camera cone + body in the kitchen area.
    _draw_security_camera(cam_x, cam_y, _solid_walls())

    # Pickups (looted sidearms + bandages). Drawn as small ground
    # markers so the player can spot them at a glance.
    for pu in STATE.pickups:
        _draw_m3_pickup(screen, pu, cam_x, cam_y)

    # Unpinned floating texts (damage numbers, pickup notifications).
    unpinned = [ft for ft in STATE.floating_texts if not (len(ft) >= 6 and ft[5] == "pin")]
    for ft in unpinned:
        txt = font_terminal_small.render(ft[2], True, ft[3])
        screen.blit(txt, (ft[0] - cam_x - txt.get_width() // 2, ft[1] - cam_y))

    # Subtle facility lockdown lighting after Volkov detonates the door.
    _draw_m3_alarm_effect(screen)

    # Drain objective marker while crafting the shiv objective is active.
    _draw_drain_guidance(cam_x, cam_y)

    # Draw the Mission 3 improvised weapon after the room overlays so the
    # chair leg / crafted shiv is visibly in Biribel's hands during gameplay.
    # (Only drawn while the player has an improvised weapon; once the sidearm
    # is acquired, the pistol is rendered by Player.draw above and this overlay
    # is suppressed.)
    _draw_mission3_hand_weapon(screen, cam_x, cam_y)

    # Muzzle flash - matches M1/M2 barrel-tip flash.
    if STATE.muzzle_flash_timer > 0 and STATE.player:
        if hasattr(STATE.player, "barrel_tip"):
            tip_x, tip_y = STATE.player.barrel_tip()
        else:
            tip_x = STATE.player.rect.centerx + math.cos(STATE.player.angle) * 39
            tip_y = STATE.player.rect.centery + math.sin(STATE.player.angle) * 39
        screen.blit(MUZZLE_FLASH, (int(tip_x - cam_x - 40), int(tip_y - cam_y - 40)))
        if artpack.enabled():
            lighting.buffer().light(tip_x - cam_x, tip_y - cam_y, 240,
                                    (255, 190, 110), 0.9)
        STATE.muzzle_flash_timer -= 1

    # Default vignette + scanlines for the live gameplay view. The
    # chair-break cutscene branch (above) returns early and never reaches
    # here, so we always draw the gameplay vignette on this path.
    v_default = 180 if getattr(STATE, "mission3_stage", STAGE_INTERROGATION) == STAGE_INTERROGATION else 130
    draw_vignette(screen, strength=v_default)
    draw_scanlines(screen)

    # Death animation overlay (blood pool, fallen body, tinnitus).
    # Black Ledger owns its own custom death animation.
    if getattr(STATE, "m3_black_ledger_death_active", False):
        _draw_black_ledger_death_overlay()
    elif STATE.player_dead:
        from entities import death_anim
        death_anim.draw_death_overlay(screen, cam_x, cam_y)

    # GC flash overlay (grenade/blast white flash) - matches M1/M2.
    if STATE.gc_flash_timer > 0 and not getattr(STATE, "reduced_motion", False):
        flash_surf = get_fullscreen_overlay((255, 255, 255, 255))
        flash_surf.set_alpha(min(255, STATE.gc_flash_timer * 22))
        screen.blit(flash_surf, (0, 0))

    # HUD + dialogue panel - drawn LAST so they sit on top of all world
    # geometry, props, and atmosphere overlays. During the held interrogation
    # beat the normal combat HUD/minimap is intentionally suppressed; Biribel
    # is restrained and the only useful information is the scene objective.
    if getattr(STATE, "mission3_stage", STAGE_INTERROGATION) == STAGE_INTERROGATION:
        if _m3_flow._volkov_breach_t >= 0:
            # Breach is a physical action beat now: no REC/status strip, just
            # directed camera + letterbox + the current caption/Volkov line.
            _draw_breach_cinematic_letterbox()
            _draw_dialogue_panel()
        else:
            _draw_interrogation_status_strip()
            _draw_dialogue_panel()
    else:
        _draw_mission3_hud(screen, cam_x, cam_y)

    # Drain prompt: if the player has a chair_leg and is near the drain,
    # show "Press E to sharpen" so they know to start crafting.
    if (getattr(STATE, "mission3_weapon", "none") == "chair_leg"
            and not getattr(STATE, "mission3_crafting_active", False)):
        drain_pos = (_DRAIN_TILE_COL * TILE_SIZE + TILE_SIZE // 2,
                     _DRAIN_TILE_ROW * TILE_SIZE + TILE_SIZE // 2)
        if _near(drain_pos, radius=60):
            prompt = font_terminal_small.render(
                _T("m3.e_sharpen_the_leg"), True, (200, 170, 120))
            px = drain_pos[0] - cam_x
            py = drain_pos[1] - cam_y - 30
            # Pulsing alpha.
            a = int(180 + math.sin(_now_s() * 4) * 60)
            prompt.set_alpha(a)
            screen.blit(prompt,
                        (px - prompt.get_width() // 2, py))

    # Vent shaft prompt: show when near the grate in the cell.
    if getattr(STATE, "mission3_stage", STAGE_INTERROGATION) == STAGE_BREAKOUT:
        vent_pos = (_VENT_GRATE_COL * TILE_SIZE + TILE_SIZE // 2,
                    _VENT_GRATE_ROW * TILE_SIZE + TILE_SIZE // 2)
        if _near(vent_pos, radius=50):
            if not getattr(STATE, "mission3_vent_open", False):
                prompt = font_terminal_small.render(
                    _T("m3.e_pry_open_vent"), True, (200, 170, 120))
            else:
                prompt = font_terminal_small.render(
                    _T("m3.e_crawl_into_vent"), True, (140, 220, 160))
            px = vent_pos[0] - cam_x
            py = vent_pos[1] - cam_y - 30
            a = int(180 + math.sin(_now_s() * 4) * 60)
            prompt.set_alpha(a)
            screen.blit(prompt,
                        (px - prompt.get_width() // 2, py))

    # Cell-block exit prompt: if the player is in STAGE_BREAKOUT and near
    # the exit tile, show "Reach the exit" so they know where to go. The
    # actual STAGE_COMMS transition fires from _update_stage when the
    # player enters the exit tile.
    if getattr(STATE, "mission3_stage", STAGE_INTERROGATION) == STAGE_BREAKOUT:
        exit_pos = (_EXIT_TILE_COL * TILE_SIZE + TILE_SIZE // 2,
                    _EXIT_TILE_ROW * TILE_SIZE + TILE_SIZE // 2)
        if _near(exit_pos, radius=120):
            exit_ready, exit_reason = _m3_exit_requirements()
            prompt_text = "[ REACH THE EXIT ]" if exit_ready else "[ EXIT LOCKED: OBJECTIVE INCOMPLETE ]"
            prompt_col = (140, 220, 160) if exit_ready else (220, 170, 90)
            prompt = font_terminal_small.render(prompt_text, True, prompt_col)
            px = exit_pos[0] - cam_x
            py = exit_pos[1] - cam_y - 36
            a = int(180 + math.sin(_now_s() * 4) * 60)
            prompt.set_alpha(a)
            screen.blit(prompt,
                        (px - prompt.get_width() // 2, py))
            if not exit_ready:
                reason = font_terminal_small.render(exit_reason[:54], True, (170, 140, 100))
                reason.set_alpha(a)
                screen.blit(reason, (px - reason.get_width() // 2, py + 16))

    # K-9 wall-stand prompt in the armory.
    if not getattr(STATE, "k9_unlocked", False):
        k9_pos = (_K9_STAND_COL * TILE_SIZE + TILE_SIZE // 2,
                  _K9_STAND_ROW * TILE_SIZE + TILE_SIZE // 2)
        if _near(k9_pos, radius=72):
            prompt = font_terminal_small.render(
                _T("m3.e_take_k_9_suppressed_smg"), True, (140, 230, 190))
            px = k9_pos[0] - cam_x
            py = k9_pos[1] - cam_y + 36
            a = int(180 + math.sin(_now_s() * 4) * 60)
            prompt.set_alpha(a)
            screen.blit(prompt, (px - prompt.get_width() // 2, py))

    # Crafting overlay - drawn LAST, on top of everything, when active.
    if getattr(STATE, "mission3_crafting_active", False):
        _draw_crafting_overlay()

    # Camera tilt on death - applied at the very end so the entire
    # rendered scene (world + HUD + overlays) rotates together. Matches M1/M2.
    # Black Ledger uses its own full-screen death composition instead.
    if STATE.player_dead and not getattr(STATE, "m3_black_ledger_death_active", False):
        from entities import death_anim
        death_anim.apply_camera_tilt(screen)

    # Interactive struggle removed.


def _draw_m3_pickup(surface, pu, cam_x, cam_y):
    """Draw a Mission 3 ground pickup (looted sidearm or bandage).

    Small isometric marker so the player can spot them at a glance - a
    pistol-shaped silhouette for sidearms, a white cross for bandages.
    Faint pulsing glow so they read as "interactive" without screaming.
    """
    px = pu[0] - cam_x
    py = pu[1] - cam_y
    kind = pu[2]
    # Cull if off-screen.
    if px < -40 or px > WIDTH + 40 or py < -40 or py > HEIGHT + 40:
        return
    pulse = 0.5 + 0.5 * math.sin(_now_s() * 3.0)
    if kind == "sidearm":
        # Dark gun-shaped silhouette on a faint amber ground halo.
        halo = pygame.Surface((40, 40), pygame.SRCALPHA)
        pygame.draw.circle(halo, (220, 180, 80, int(40 + 30 * pulse)),
                           (20, 20), 18)
        surface.blit(halo, (px - 20, py - 20))
    elif kind == "bandage":
        # White cross on a faint green ground halo.
        halo = pygame.Surface((32, 32), pygame.SRCALPHA)
        pygame.draw.circle(halo, (120, 220, 120, int(40 + 30 * pulse)),
                           (16, 16), 14)
        surface.blit(halo, (px - 16, py - 16))
    else:
        return
    # RPE6 Phase 3: the marker itself is a baked sprite (game.art.m3.pickup_icon); the pulsing
    # halo above stays live, _paint_m3_pickup_icon is the fallback / bake source.
    spr = _m3art.get("pickup_icon", 0 if kind == "sidearm" else 1)
    if spr is not None:
        surface.blit(spr, (px - 8, py - 8))
    else:
        _paint_m3_pickup_icon(surface, px, py, kind)


def _paint_m3_pickup_icon(surface, px, py, kind):
    """Pickup marker centred on px/py (opaque primitives inside (px-8, py-8) .. (px+8, py+9))."""
    if kind == "sidearm":
        # Pistol body (top-down): slide + grip.
        pygame.draw.rect(surface, (40, 40, 44),
                         (px - 8, py - 3, 16, 6), border_radius=1)
        pygame.draw.rect(surface, (40, 40, 44),
                         (px - 3, py + 2, 6, 7), border_radius=1)
        # Subtle highlight on the slide.
        pygame.draw.line(surface, (90, 90, 95),
                         (px - 7, py - 2), (px + 7, py - 2), 1)
    elif kind == "bandage":
        pygame.draw.rect(surface, (240, 240, 240),
                         (px - 7, py - 2, 14, 4))
        pygame.draw.rect(surface, (240, 240, 240),
                         (px - 2, py - 7, 4, 14))


def solid_walls_view():
    """Walls subset passed to Player.draw for gun-occlusion logic.

    Player.draw uses walls only to hide the gun barrel behind cover; in
    the cell (no gun) this is a no-op, but we keep the signature right so
    Slice 2 combat drops in without touching the call site.
    """
    return _solid_walls()


# ─────────────────────────────────────
# Phase 1 - Interrogation renderer
# ─────────────────────────────────────
# The cold-open is a fixed-camera beat: the player is cuffed to the chair
# facing the monitor, so we render the dialogue as a full-width letterboxed
# panel at the bottom of the screen and the Balaceanu monitor as a glowing
# rectangle on the cell's north wall. No new art assets - all procedural,
# matching the project's "cinematic art deferred to Slice C" note in
# MISSION3_PLOT.md.

# Screen layout constants for the interrogation UI.  This scene is a held,
# non-combat beat, so it intentionally uses a cleaner cinematic lower-third
# instead of the full gameplay HUD + full-width dialogue slab.
_PANEL_H = 154
_PANEL_PAD = 18
_PANEL_W = 820
_PANEL_X = (WIDTH - _PANEL_W) // 2
_MONITOR_TILE_COL, _MONITOR_TILE_ROW = 33, 5  # north wall of Biribel's cell (cell 3)


def _wrap(text, font, max_width):
    """Word-wrap ``text`` to fit ``max_width`` pixels using ``font``.

    Returns a list of lines. Preserves explicit newlines in the source text
    so multi-line captions (e.g. the title card) keep their breaks.
    """
    lines = []
    for raw in text.split("\n"):
        if not raw:
            lines.append("")
            continue
        words = raw.split(" ")
        cur = ""
        for w in words:
            trial = w if not cur else cur + " " + w
            if font.size(trial)[0] <= max_width:
                cur = trial
            else:
                if cur:
                    lines.append(cur)
                cur = w
        lines.append(cur)
    return lines


def _draw_wall_monitor(cam_x, cam_y):
    """Draw the wall monitor on the cell's north wall.

    Lit (Balaceanu's feed) → a red CRT with a dark head-and-shoulders
    silhouette (so it reads as a man on a screen, not just a label),
    scanline noise, and a pulsing red glow halo that washes the cell.
    Off → a dead dark rectangle. The flicker flag (post-monitor-off)
    strobes between the two for ~1s.

    RPE6 Phase 3: the static parts are baked sprites (game.art.m3.wall_monitor: 0 off, 1 lit
    bezel + screen, 2 lit silhouette / scanlines / labels); the pulsing additive glow and the
    blinking REC dot stay live, _paint_wall_monitor_part is the fallback / bake source.
    """
    sx = _MONITOR_TILE_COL * TILE_SIZE - cam_x
    sy = _MONITOR_TILE_ROW * TILE_SIZE - cam_y
    mw, mh = TILE_SIZE * 3, int(TILE_SIZE * 0.9)
    rect = pygame.Rect(sx, sy + 6, mw, mh)

    # The monitor's lit state is driven solely by _m3_flow._monitor_on. The
    # post-cutoff _m3_flow._light_flicker is allowed to strobe the room's fluorescent
    # ambience, but it must never re-light this screen once the feed is cut.
    lit = _m3_flow._monitor_on

    def part(idx, name):
        spr = _m3art.get("wall_monitor", idx)
        if spr is not None:
            screen.blit(spr, (rect.x - 4, rect.y - 4))
        else:
            _paint_wall_monitor_part(screen, rect, name)

    if lit:
        part(1, "lit_base")
        glow = pygame.Surface((mw + 120, mh + 120), pygame.SRCALPHA)
        pulse = 0.5 + 0.5 * math.sin(_now_s() * 6.0)
        _k = 0.6 + 0.4 * pulse
        _cum = [0, 0, 0]
        for r, a in ((1.0, 18), (0.7, 26), (0.45, 40)):
            _step = (170 * a / 255.0 * _k, 40 * a / 255.0 * _k, 40 * a / 255.0 * _k)
            _cum = [min(255, int(_cum[i] + _step[i])) for i in range(3)]
            pygame.draw.rect(
                glow,
                (_cum[0], _cum[1], _cum[2], 255),
                (60 - mw * r / 2 + mw / 2, 60 - mh * r / 2 + mh / 2,
                 mw * r, mh * r),
                border_radius=6,
            )
        screen.blit(glow, (rect.x - 60, rect.y - 60), special_flags=pygame.BLEND_ADD)
        part(2, "lit_fg")
        if int(_now_s() * 2) % 2 == 0:
            pygame.draw.circle(screen, (220, 40, 40),
                               (rect.right - 14, rect.y + 10), 3)
    else:
        part(0, "off")


def _paint_wall_monitor_part(surface, rect, part):
    """Static parts of the wall monitor (bake source of game.art.m3.wall_monitor); ``rect`` is the
    screen rectangle, part in ("off", "lit_base", "lit_fg")."""
    mw, mh = rect.w, rect.h
    if part == "lit_base":
        pygame.draw.rect(surface, (30, 18, 18), rect.inflate(8, 8), border_radius=4)
        pygame.draw.rect(surface, (10, 6, 6), rect, border_radius=2)
    elif part == "lit_fg":
        # Head-and-shoulders silhouette so the screen reads as a person.
        cx = rect.centerx
        head_cy = rect.y + int(mh * 0.40)
        head_r = int(mh * 0.22)
        shoulder_top = head_cy + head_r - 2
        shoulder_w = int(mw * 0.55)
        pygame.draw.circle(surface, (4, 2, 2), (cx, head_cy), head_r)
        pygame.draw.ellipse(
            surface, (4, 2, 2),
            (cx - shoulder_w // 2, shoulder_top, shoulder_w, rect.bottom - shoulder_top + 6),
        )
        # Scanline noise.
        for ny in range(rect.y + 2, rect.bottom - 2, 3):
            pygame.draw.line(surface, (60, 20, 20),
                             (rect.x + 2, ny), (rect.right - 2, ny), 1)
        label = font_terminal_small.render(_T("m3.balaceanu"), True, (210, 90, 90))
        surface.blit(label, (rect.x + 6, rect.y + 4))
        rec = font_terminal_small.render(_T("m3.rec"), True, (180, 60, 60))
        surface.blit(rec, (rect.right - 40, rect.y + 4))
    else:
        pygame.draw.rect(surface, (30, 30, 34), rect.inflate(8, 8), border_radius=4)
        pygame.draw.rect(surface, (8, 8, 10), rect, border_radius=2)
        pygame.draw.rect(surface, (40, 40, 44), rect, 1)
        dead = font_terminal_small.render(_T("m3.no_signal"), True, (70, 70, 74))
        surface.blit(dead, (rect.x + 6, rect.y + 4))


def _draw_interrogation_status_strip():
    """Tiny diegetic monitor noise for the interrogation.

    No mission title, no objective box: the point of this stage is that Biribel
    is trapped, not browsing a HUD.  This reads as surveillance/recording noise
    rather than a gameplay panel.
    """
    ticks = _now_ms()
    rec_on = (ticks // 420) % 2 == 0
    x, y = 26, 22
    if rec_on:
        pygame.draw.circle(screen, (170, 28, 28), (x, y + 7), 4)
    rec = font_terminal_small.render(_T("m3.rec_cell_03"), True, (95, 100, 100))
    time_left = font_terminal_small.render(_T("m3.22_00_address_pending"), True, (105, 70, 70))
    rec.set_alpha(145)
    time_left.set_alpha(118)
    screen.blit(rec, (x + 12, y))
    screen.blit(time_left, (x + 12, y + 18))


def _draw_text_shadowed(surface, font, text, pos, color, shadow=(0, 0, 0), alpha=255):
    """Small helper for minimal interrogation text: no boxes, just readable text."""
    sx, sy = pos
    sh = font.render(text, True, shadow)
    sh.set_alpha(min(alpha, 190))
    surface.blit(sh, (sx + 2, sy + 2))
    fg = font.render(text, True, color)
    fg.set_alpha(alpha)
    surface.blit(fg, pos)
    return fg.get_width(), fg.get_height()


def _draw_interrogation_text_scrim(y, h, alpha=78):
    """Very soft readability band; deliberately not a panel/card."""
    scrim = pygame.Surface((WIDTH, h), pygame.SRCALPHA)
    for i in range(h):
        # darkest at center, feathered at top/bottom
        mid = 1.0 - abs((i / max(1, h - 1)) * 2.0 - 1.0)
        a = int(alpha * (mid ** 0.75))
        pygame.draw.line(scrim, (0, 0, 0, a), (0, i), (WIDTH, i))
    screen.blit(scrim, (0, y))


def _draw_dialogue_panel():
    """Render the minimal-horror Mission 3 interrogation interface.

    This intentionally avoids obvious UI furniture: no cards, no large panels,
    no boxed objective.  Dialogue becomes sparse subtitle text over the cell;
    choices become bare thoughts/responses, like things Biribel can force out
    while restrained.
    """
    beat = _current_beat()
    if beat is None:
        return

    if _m3_flow._dialogue_slide > 0:
        _m3_flow._dialogue_slide = max(0.0, _m3_flow._dialogue_slide - 1.0)
    slide_offset = int(_m3_flow._dialogue_slide)

    btype = beat.get("type")
    speaker = beat.get("speaker", "")
    accent = beat.get("color", C_BIRIBEL)
    ticks = _now_ms()
    cursor_visible = (ticks // 330) % 2 == 0

    # Oppressive focus layer: always slight; heavier when the player is forced
    # to choose.  This replaces the previous UI cards with mood.
    dim = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
    dim_alpha = 34 if btype != "choice" else 82
    dim.fill((0, 0, 0, dim_alpha))
    screen.blit(dim, (0, 0))

    if btype == "action":
        caption, cap_color = _ACTION_CAPTIONS.get(beat.get("action"), ("[...]", C_SYSTEM))
        visible = caption[:_m3_flow._dialogue_char_idx]
        lines = _wrap(visible, font_terminal, WIDTH - 160)
        total_h = max(1, len(lines[:2])) * 30
        y = HEIGHT // 2 - total_h // 2
        _draw_interrogation_text_scrim(y - 28, total_h + 56, alpha=58)
        for i, ln in enumerate(lines[:2]):
            surf = font_terminal.render(ln, True, cap_color)
            surf.set_alpha(min(230, max(80, _m3_flow._dialogue_char_idx * 7 - i * 35)))
            x = WIDTH // 2 - surf.get_width() // 2
            _draw_text_shadowed(screen, font_terminal, ln, (x, y + i * 30), cap_color, alpha=surf.get_alpha())
        if not _line_fully_typed(beat) and cursor_visible:
            pygame.draw.rect(screen, cap_color, (WIDTH // 2 + 4, y + total_h + 2, 8, 18))
        _draw_continue_hint(0, accent, beat, "SPACE / ENTER")
        return

    if btype == "line":
        full_text = beat.get("text", "")
        visible = full_text[:_m3_flow._dialogue_char_idx]
        inner_w = WIDTH - 180
        lines = _wrap(visible, font_dialogue, inner_w)
        speaker_label = speaker.upper() if speaker else ""

        block_h = 26 + max(1, len(lines[:3])) * 28
        y = HEIGHT - block_h - 52 + slide_offset
        x = 92
        _draw_interrogation_text_scrim(y - 18, block_h + 46, alpha=70)

        if speaker_label:
            _draw_text_shadowed(screen, font_terminal_small, speaker_label,
                                (x, y), accent, alpha=190)
            # Small speaker-color wound line; less UI than a full stripe.
            pygame.draw.line(screen, (*accent, 125), (x, y + 20), (x + 94, y + 20), 1)
        ty = y + 30
        for i, ln in enumerate(lines[:3]):
            la = min(238, max(0, _m3_flow._dialogue_char_idx * 8 - i * 40))
            _draw_text_shadowed(screen, font_dialogue, ln, (x, ty + i * 28),
                                (228, 230, 230), alpha=la)
        if not _line_fully_typed(beat) and lines and cursor_visible:
            last = lines[min(len(lines), 3) - 1]
            cx = x + font_dialogue.size(last)[0] + 4
            cy = ty + (min(len(lines), 3) - 1) * 28 + 4
            pygame.draw.rect(screen, accent, (cx, cy, 8, 20))
        _draw_continue_hint(0, accent, beat, "SPACE / ENTER")
        return

    if btype == "choice":
        prompt = beat.get("prompt", "Choose:")
        visible_prompt = prompt[:_m3_flow._dialogue_char_idx]
        inner_w = WIDTH - 200
        prompt_lines = _wrap(visible_prompt, font_dialogue, inner_w)

        x = 118
        y = HEIGHT - 232
        _draw_interrogation_text_scrim(y - 22, 190, alpha=82)
        for i, ln in enumerate(prompt_lines[:2]):
            la = min(220, max(0, _m3_flow._dialogue_char_idx * 8 - i * 40))
            _draw_text_shadowed(screen, font_dialogue, ln, (x, y + i * 28),
                                C_PROMPT, alpha=la)

        if not _line_fully_typed(beat):
            if cursor_visible:
                last_line = prompt_lines[-1] if prompt_lines else ""
                cx = x + font_dialogue.size(last_line)[0] + 4
                pygame.draw.rect(screen, C_PROMPT, (cx, y + 4, 8, 20))
            return

        options = beat.get("options", [])
        opt_y = y + 66
        for i, (label, _line) in enumerate(options):
            selected = (i == _m3_flow._dialogue_choice)
            prefix = ">" if selected else " "
            col = (245, 216, 132) if selected else (150, 154, 154)
            alpha = 235 if selected else 150
            line = f"{prefix} {label}"
            _draw_text_shadowed(screen, font_dialogue, line, (x + 24, opt_y + i * 30),
                                col, alpha=alpha)
            if selected:
                pulse = int(80 + 50 * (0.5 + 0.5 * math.sin(ticks * 0.006)))
                pygame.draw.line(screen, (*C_PROMPT, pulse),
                                 (x + 24, opt_y + i * 30 + 25),
                                 (x + 235, opt_y + i * 30 + 25), 1)
        _draw_continue_hint(0, accent, beat, "UP/DOWN choose  ENTER")
        return


def _draw_continue_hint(x, accent, beat, text):
    """Pulsing bottom-right hint - only once the current line is fully typed
    (so it never reads as skippable mid-type). Mirrors draw_dialogue_box's
    sine-modulated "SPACE TO CONTINUE" prompt."""
    if _action_is_unskippable(beat):
        return

    if not _line_fully_typed(beat):
        return
    ticks = _now_ms()
    a = int(140 + math.sin(ticks * 0.004) * 60)
    hint = font_terminal_small.render(text, True,
                                      (accent[0] // 2, accent[1] // 2, accent[2] // 2))
    hint.set_alpha(a)
    screen.blit(hint, (WIDTH - hint.get_width() - 22, HEIGHT - 24))


def _draw_cell_atmosphere(cam_x, cam_y):
    """Atmospheric overlays that sell the cell as a cell, not a tilemap.

    Layers, back-to-front:
      - Red monitor wash: when the monitor is lit, a low-alpha red overlay
        tinting the visible interior (the monitor is the only light source).
      - Hanging fluorescent light: a tube on the ceiling + a soft light cone
        spilling down. Flickers (steady while lit, strobing after the cut).
    Drawn BEFORE the monitor so the monitor's glow halo sits on top.
    """
    # Red monitor wash over the whole screen while Balaceanu's feed is live.
    if _m3_flow._monitor_on and not (_m3_flow._light_flicker > 0 and _m3_flow._light_flicker % 8 < 4):
        pulse = 0.5 + 0.5 * math.sin(_now_s() * 6.0)
        wash = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        wash.fill((90, 12, 12, int(28 + 18 * pulse)))
        screen.blit(wash, (0, 0))

    # Hanging fluorescent tube on the ceiling + light cone below it.
    # Position it a couple tiles right of the monitor, high on the wall.
    tube_cx = (_MONITOR_TILE_COL + 5) * TILE_SIZE - cam_x
    tube_cy = _MONITOR_TILE_ROW * TILE_SIZE - cam_y + 6
    tube_w, tube_h = TILE_SIZE, 8
    # Flicker: steady while the monitor is on; strobe after monitor_off.
    tube_lit = True
    if _m3_flow._light_flicker > 0:
        tube_lit = _m3_flow._light_flicker % 10 < 6
    if tube_lit:
        # The tube itself.
        pygame.draw.rect(screen, (30, 30, 26),
                         (tube_cx - tube_w // 2 - 4, tube_cy - 6, tube_w + 8, tube_h + 6),
                         border_radius=2)
        glow_pulse = 0.75 + 0.25 * math.sin(_now_s() * 8.0)
        pygame.draw.rect(
            screen,
            (int(200 * glow_pulse), int(205 * glow_pulse), int(180 * glow_pulse)),
            (tube_cx - tube_w // 2, tube_cy, tube_w, tube_h),
            border_radius=2,
        )
        # Soft cone of cold light spilling DOWN into the cell only.
        # The tube is on the north wall; light should only illuminate south
        # (into the cell interior), NOT north (into the wall above the tube).
        # _draw_light_cone draws a full radial circle which leaks up; we
        # draw a half-cone manually -- a half-circle glow clipped to y >=
        # tube_cy + tube_h.
        cone_radius = int(TILE_SIZE * 2.2)
        cone_cx = tube_cx
        cone_cy = tube_cy + tube_h
        cone_alpha = int(55 * glow_pulse)
        if cone_alpha > 0 and cone_radius > 0:
            # Build the glow on a surface sized to the lower half only.
            cone_surf = pygame.Surface((cone_radius * 2, cone_radius),
                                        pygame.SRCALPHA)
            steps = 16
            for i in range(steps):
                t = i / steps
                rad = int(cone_radius * (1 - t * 0.6))
                aa = int(cone_alpha * (1 - t) ** 2)
                if aa > 0 and rad > 0:
                    # Draw a half-circle (bottom half) centered at the top
                    # edge of the cone_surf.
                    pygame.draw.circle(
                        cone_surf, (210, 215, 190, aa),
                        (cone_radius, 0), rad,
                        draw_top_right=False, draw_top_left=False,
                        draw_bottom_right=True, draw_bottom_left=True,
                    )
            screen.blit(cone_surf, (cone_cx - cone_radius, cone_cy))


# Cell interior tile bounds (Biribel's cell = cell index 3 in the new 48x48
# layout: cols 30..37, rows 5..12). Used to place furniture against walls.
_CELL_COL_WEST = 30
_CELL_COL_EAST = 37
_CELL_ROW_NORTH = 5
_CELL_ROW_SOUTH = 12


def _draw_cell_details(cam_x, cam_y, chair_broken=None, live=True):
    """Draw cell furniture, floor details, and wall scratches to make the
    cell read as a real interrogation cell, not a bare tilemap.

    All fixtures use seeded random (random.Random(42)) so stains and cracks
    look organic but stay deterministic (no per-frame shimmer).

    Called from _draw_cell_room AFTER atmosphere but BEFORE the wall monitor.
    This function draws Biribel's cell (cell 3) only - neighbor cells
    are handled by _draw_neighbor_cells.

    RPE6 Phase 3: this painter is also the bake source of the world layer
    ``game.art.m3.cell_details`` (variant 0 = chair intact, 1 = broken).
    ``chair_broken`` pins the variant for the bake; ``live=False`` skips the
    per-frame parts (the speaker LED), which ``_draw_cell_details_live`` draws
    on top of the blitted layer.
    """
    if chair_broken is None:
        chair_broken = bool(getattr(STATE, "mission3_chair_broken", False))
    rng = random.Random(42)

    # Wall baseboard
    base_col = (22, 24, 26)
    base_h = 3
    by = _CELL_ROW_NORTH * TILE_SIZE - cam_y - base_h
    pygame.draw.rect(screen, base_col,
                     (_CELL_COL_WEST * TILE_SIZE - cam_x, by,
                      (_CELL_COL_EAST - _CELL_COL_WEST + 1) * TILE_SIZE, base_h))
    bx = _CELL_COL_WEST * TILE_SIZE - cam_x - base_h
    pygame.draw.rect(screen, base_col,
                     (bx, _CELL_ROW_NORTH * TILE_SIZE - cam_y,
                      base_h, (_CELL_ROW_SOUTH - _CELL_ROW_NORTH + 1) * TILE_SIZE))
    bx = (_CELL_COL_EAST + 1) * TILE_SIZE - cam_x
    pygame.draw.rect(screen, base_col,
                     (bx, _CELL_ROW_NORTH * TILE_SIZE - cam_y,
                      base_h, (_CELL_ROW_SOUTH - _CELL_ROW_NORTH + 1) * TILE_SIZE))

    # Barred window
    win_x = (_CELL_COL_WEST + 3) * TILE_SIZE - cam_x + 20
    win_y = _CELL_ROW_NORTH * TILE_SIZE - cam_y + 4
    win_w, win_h = 42, 18
    pygame.draw.rect(screen, (10, 12, 16), (win_x, win_y, win_w, win_h))
    pygame.draw.rect(screen, (60, 64, 68), (win_x, win_y, win_w, win_h), 2)
    bar_col = (50, 54, 58)
    for bar_off in (6, 16, 26, 36):
        pygame.draw.line(screen, bar_col, (win_x + bar_off, win_y + 1), (win_x + bar_off, win_y + win_h - 1), 2)
    glow = pygame.Surface((win_w, win_h), pygame.SRCALPHA)
    pygame.draw.rect(glow, (40, 60, 80, 30), glow.get_rect())
    screen.blit(glow, (win_x, win_y))

    # Floor drain
    drain_x = _DRAIN_TILE_COL * TILE_SIZE - cam_x + TILE_SIZE // 2
    drain_y = _DRAIN_TILE_ROW * TILE_SIZE - cam_y + TILE_SIZE // 2
    pygame.draw.rect(screen, (28, 26, 22), (drain_x - 11, drain_y - 11, 22, 22), border_radius=3)
    pygame.draw.rect(screen, (18, 17, 14), (drain_x - 9, drain_y - 9, 18, 18))
    pygame.draw.rect(screen, (6, 6, 5), (drain_x - 7, drain_y - 7, 14, 14))
    bar_col = (40, 36, 32)
    bar_hi = (58, 52, 46)
    for off in (-5, 0, 5):
        pygame.draw.line(screen, bar_col, (drain_x - 7, drain_y + off), (drain_x + 7, drain_y + off), 1)
        pygame.draw.line(screen, bar_col, (drain_x + off, drain_y - 7), (drain_x + off, drain_y + 7), 1)
    for off in (-5, 0, 5):
        pygame.draw.line(screen, bar_hi, (drain_x - 7, drain_y + off - 1), (drain_x + 7, drain_y + off - 1), 1)

    # Ventilation grate
    vent_x = (_CELL_COL_WEST + 1) * TILE_SIZE - cam_x + TILE_SIZE // 2
    vent_y = (_CELL_ROW_SOUTH - 2) * TILE_SIZE - cam_y + TILE_SIZE // 2
    vent_w, vent_h = 28, 14
    pygame.draw.rect(screen, (6, 6, 8), (vent_x - vent_w // 2, vent_y - vent_h // 2, vent_w, vent_h), border_radius=2)
    pygame.draw.rect(screen, (44, 42, 38), (vent_x - vent_w // 2, vent_y - vent_h // 2, vent_w, vent_h), 2, border_radius=2)
    slat_col = (38, 36, 32)
    for slat_off in (-4, 0, 4):
        pygame.draw.line(screen, slat_col, (vent_x - vent_w // 2 + 3, vent_y + slat_off), (vent_x + vent_w // 2 - 3, vent_y + slat_off), 2)
    draft = pygame.Surface((vent_w - 4, 2), pygame.SRCALPHA)
    draft.fill((60, 80, 100, 20))
    screen.blit(draft, (vent_x - vent_w // 2 + 2, vent_y - 2))

    # Floor stains
    stain = pygame.Surface((56, 42), pygame.SRCALPHA)
    pygame.draw.ellipse(stain, (28, 24, 18, 60), (0, 0, 56, 42))
    pygame.draw.ellipse(stain, (32, 26, 18, 80), (8, 6, 40, 30))
    pygame.draw.ellipse(stain, (22, 18, 14, 100), (16, 12, 24, 18))
    for _ in range(8):
        bx = rng.randint(0, 52)
        by = rng.randint(0, 38)
        br = rng.randint(2, 5)
        pygame.draw.circle(stain, (26, 22, 16, 70), (bx, by), br)
    screen.blit(stain, (drain_x - 28, drain_y - 21))

    # Blood stain
    blood_x = (_CELL_COL_WEST + 2) * TILE_SIZE - cam_x + TILE_SIZE // 2
    blood_y = (_CELL_ROW_NORTH + 2) * TILE_SIZE - cam_y + TILE_SIZE // 2 + 8
    blood = pygame.Surface((40, 32), pygame.SRCALPHA)
    pygame.draw.ellipse(blood, (40, 6, 6, 80), (0, 0, 40, 32))
    pygame.draw.ellipse(blood, (55, 8, 8, 160), (6, 4, 28, 22))
    pygame.draw.ellipse(blood, (50, 6, 6, 200), (12, 8, 16, 14))
    for _ in range(10):
        sx = 20 + rng.randint(-16, 16)
        sy = 16 + rng.randint(-12, 12)
        sr = rng.randint(1, 3)
        pygame.draw.circle(blood, (45, 8, 8, 140), (sx, sy), sr)
    for _ in range(3):
        sx = 20 + rng.randint(-14, 14)
        sy = 16 + rng.randint(-10, 10)
        ex = sx + rng.randint(-2, 2)
        ey = sy + rng.randint(2, 6)
        pygame.draw.line(blood, (40, 6, 6, 120), (sx, sy), (ex, ey), 1)
    screen.blit(blood, (blood_x - 20, blood_y - 16))

    # Floor cracks
    crack_col = (20, 18, 16)
    for _ in range(5):
        angle = rng.uniform(0, math.pi * 2)
        length = rng.randint(35, 55)
        cx, cy = drain_x, drain_y
        for _ in range(4):
            seg_len = length / 4
            ex = cx + math.cos(angle) * seg_len + rng.randint(-3, 3)
            ey = cy + math.sin(angle) * seg_len + rng.randint(-3, 3)
            pygame.draw.line(screen, crack_col, (cx, cy), (int(ex), int(ey)), 1)
            cx, cy = ex, ey
            angle += rng.uniform(-0.4, 0.4)

    # Tally marks
    wall_x = _CELL_COL_WEST * TILE_SIZE - cam_x
    tally_start_y = (_CELL_ROW_NORTH + 2) * TILE_SIZE - cam_y
    tally_col = (62, 56, 46)
    for group in range(4):
        gx = wall_x + 5
        gy = tally_start_y + group * 22
        for i in range(4):
            x = gx + i * 4 + rng.randint(-1, 1)
            y_off = rng.randint(0, 2)
            pygame.draw.line(screen, tally_col, (x, gy + y_off), (x, gy + 14 + y_off), 1)
        pygame.draw.line(screen, tally_col, (gx - 2, gy + 14), (gx + 14, gy), 1)

    # Graffiti (MAG tag + IPA crest)
    gx = (_CELL_COL_EAST + 1) * TILE_SIZE - cam_x - 14
    tag_col = (140, 60, 40, 120)
    mag_y = (_CELL_ROW_NORTH + 3) * TILE_SIZE - cam_y
    tag_surf = pygame.Surface((30, 24), pygame.SRCALPHA)
    for i, letter in enumerate("MAG"):
        lx = 2 + i * 10
        ly = 4
        for j in range(5):
            ch = rng.randint(-1, 1)
            tag_surf.set_at((lx + j, ly + i * 7 + ch), tag_col)
            tag_surf.set_at((lx + j, ly + i * 7 + 1 + ch), tag_col)
    screen.blit(tag_surf, (gx, mag_y))
    crest_cx = gx + 12
    crest_cy = mag_y + 36
    pygame.draw.circle(screen, (40, 45, 55, 80), (crest_cx, crest_cy), 6, 1)

    # Conduit pipe
    conduit_col = (44, 42, 38)
    conduit_hi = (62, 58, 52)
    conduit_x = (_MONITOR_TILE_COL + 1) * TILE_SIZE - cam_x
    conduit_start_y = (_MONITOR_TILE_ROW + 1) * TILE_SIZE - cam_y
    conduit_end_y = conduit_start_y + TILE_SIZE * 2
    pygame.draw.line(screen, conduit_col, (conduit_x, conduit_start_y), (conduit_x, conduit_end_y), 4)
    pygame.draw.line(screen, conduit_hi, (conduit_x - 1, conduit_start_y), (conduit_x - 1, conduit_end_y), 1)
    box_rect = pygame.Rect(conduit_x - 6, conduit_end_y, 12, 9)
    pygame.draw.rect(screen, (50, 46, 40), box_rect, border_radius=1)
    pygame.draw.rect(screen, (30, 28, 24), box_rect, 1, border_radius=1)
    pygame.draw.circle(screen, (200, 140, 30), (conduit_x, conduit_end_y + 4), 1)
    pygame.draw.circle(screen, (90, 86, 80), (conduit_x - 4, conduit_end_y + 2), 1)
    pygame.draw.circle(screen, (90, 86, 80), (conduit_x + 4, conduit_end_y + 2), 1)

    # Water stains
    for (sx_frac, sy_off, sw, sh) in [
        (0.25, 2, 36, 10), (0.65, 4, 28, 8), (0.85, 6, 20, 6),
    ]:
        sx = (_CELL_COL_WEST + int((_CELL_COL_EAST - _CELL_COL_WEST) * sx_frac)) * TILE_SIZE - cam_x
        sy = _CELL_ROW_NORTH * TILE_SIZE - cam_y + sy_off
        ws = pygame.Surface((sw, sh), pygame.SRCALPHA)
        pygame.draw.ellipse(ws, (22, 20, 18, 60), (0, 0, sw, sh))
        pygame.draw.ellipse(ws, (18, 16, 14, 80), (4, 2, sw - 8, sh - 4))
        pygame.draw.ellipse(ws, (14, 12, 10, 60), (8, 4, sw - 16, sh - 8))
        screen.blit(ws, (sx, sy))

    # Loudspeaker
    speaker_x = (_CELL_COL_EAST + 1) * TILE_SIZE - cam_x - 10
    speaker_y = (_CELL_ROW_NORTH + 1) * TILE_SIZE - cam_y - 2
    pygame.draw.rect(screen, (80, 74, 66), (speaker_x, speaker_y, 16, 12), border_radius=2)
    pygame.draw.rect(screen, (60, 56, 50), (speaker_x, speaker_y, 16, 12), 1, border_radius=2)
    for grille_y in range(speaker_y + 3, speaker_y + 11, 3):
        pygame.draw.line(screen, (50, 46, 40), (speaker_x + 3, grille_y), (speaker_x + 13, grille_y), 1)
    if live:
        _draw_cell_details_live(cam_x, cam_y)

    # Interrogation chair
    chair_cx = (_MONITOR_TILE_COL + 0.5) * TILE_SIZE - cam_x
    chair_cy = (_CELL_ROW_NORTH + 1) * TILE_SIZE - cam_y + TILE_SIZE // 2
    seat_col = (42, 40, 36)
    seat_dark = (28, 26, 24)
    seat_edge = (60, 56, 50)

    if not chair_broken:
        chair_shad = pygame.Surface((34, 28), pygame.SRCALPHA)
        render_util.soft_shadow(chair_shad, (0, 0, 34, 28), 90)
        screen.blit(chair_shad, (chair_cx - 17, chair_cy - 10 + 6))
        back_r = pygame.Rect(int(chair_cx) - 13, int(chair_cy) - 14, 26, 8)
        pygame.draw.rect(screen, seat_col, back_r, border_radius=2)
        pygame.draw.rect(screen, seat_edge, back_r, 1, border_radius=2)
        pygame.draw.line(screen, seat_dark, (int(chair_cx), int(chair_cy) - 13), (int(chair_cx), int(chair_cy) - 8), 1)
        seat_r = pygame.Rect(int(chair_cx) - 13, int(chair_cy) - 8, 26, 18)
        pygame.draw.rect(screen, seat_col, seat_r, border_radius=2)
        pygame.draw.rect(screen, seat_edge, seat_r, 1, border_radius=2)
        pygame.draw.rect(screen, seat_dark, (int(chair_cx) - 10, int(chair_cy) - 5, 20, 12), border_radius=1)
        for side in (-1, 1):
            ar = pygame.Rect(int(chair_cx) + side * 13 - 2, int(chair_cy) - 6, 4, 14)
            pygame.draw.rect(screen, seat_col, ar, border_radius=1)
            pygame.draw.rect(screen, seat_edge, ar, 1, border_radius=1)
        bolt_col = (76, 72, 64)
        bolt_dark = (30, 28, 24)
        for (bx, by) in [(-13, -8), (13, -8), (-13, 10), (13, 10)]:
            pygame.draw.circle(screen, bolt_col, (int(chair_cx + bx), int(chair_cy + by)), 2)
            pygame.draw.circle(screen, bolt_dark, (int(chair_cx + bx), int(chair_cy + by)), 1)
        chain_col = (100, 96, 88)
        chain_dark = (60, 56, 50)
        for side in (-1, 1):
            cx = chair_cx + side * 11
            cy = chair_cy - 2
            for i in range(4):
                pygame.draw.circle(screen, chain_col, (int(cx), int(cy + i * 3)), 2, 1)
            cuff_y = cy + 11
            pygame.draw.circle(screen, (130, 124, 112), (int(cx), int(cuff_y)), 3, 1)
            pygame.draw.circle(screen, chain_dark, (int(cx), int(cuff_y)), 1)
    else:
        chair_shad = pygame.Surface((30, 22), pygame.SRCALPHA)
        render_util.soft_shadow(chair_shad, (0, 0, 30, 22), 70)
        screen.blit(chair_shad, (chair_cx - 15, chair_cy - 6 + 6))
        back_r = pygame.Rect(int(chair_cx) - 13, int(chair_cy) - 12, 26, 6)
        pygame.draw.rect(screen, seat_dark, back_r, border_radius=2)
        pygame.draw.line(screen, (52, 44, 36), (int(chair_cx) - 13, int(chair_cy) - 12), (int(chair_cx) - 8, int(chair_cy) - 14), 1)
        pygame.draw.line(screen, (52, 44, 36), (int(chair_cx) - 8, int(chair_cy) - 14), (int(chair_cx) - 3, int(chair_cy) - 11), 1)
        pygame.draw.line(screen, (52, 44, 36), (int(chair_cx) - 3, int(chair_cy) - 11), (int(chair_cx) + 2, int(chair_cy) - 15), 1)
        pygame.draw.line(screen, (52, 44, 36), (int(chair_cx) + 2, int(chair_cy) - 15), (int(chair_cx) + 8, int(chair_cy) - 12), 1)
        pygame.draw.line(screen, (52, 44, 36), (int(chair_cx) + 8, int(chair_cy) - 12), (int(chair_cx) + 13, int(chair_cy) - 14), 1)
        seat_r = pygame.Rect(int(chair_cx) - 13, int(chair_cy) - 8, 26, 16)
        pygame.draw.rect(screen, seat_dark, seat_r, border_radius=2)
        pygame.draw.rect(screen, (48, 44, 38), seat_r, 1, border_radius=2)
        pygame.draw.line(screen, (16, 14, 12), (int(chair_cx) - 10, int(chair_cy) - 5), (int(chair_cx) + 8, int(chair_cy) + 4), 1)
        bolt_col = (76, 72, 64)
        bolt_dark = (30, 28, 24)
        for (bx, by) in [(-13, -8), (13, -8), (-13, 10)]:
            pygame.draw.circle(screen, bolt_col, (int(chair_cx + bx), int(chair_cy + by)), 2)
            pygame.draw.circle(screen, bolt_dark, (int(chair_cx + bx), int(chair_cy + by)), 1)
        pygame.draw.circle(screen, (12, 10, 8), (int(chair_cx + 13), int(chair_cy + 10)), 3)
        pygame.draw.circle(screen, (6, 5, 4), (int(chair_cx + 13), int(chair_cy + 10)), 2)
        splinter_col = (50, 42, 34)
        for (sx, sy, slen, sang) in [(18, 14, 5, 0.3), (-20, 8, 4, -0.2), (22, -4, 6, 1.2), (-16, -12, 4, 0.8), (6, 18, 5, -0.5)]:
            ex = chair_cx + sx + math.cos(sang) * slen
            ey = chair_cy + sy + math.sin(sang) * slen
            pygame.draw.line(screen, splinter_col, (int(chair_cx + sx), int(chair_cy + sy)), (int(ex), int(ey)), 1)
        pygame.draw.circle(screen, (90, 84, 76), (int(chair_cx + 16), int(chair_cy + 6)), 2, 1)

    # Metal cot
    cot_x = int((_CELL_COL_WEST + 0.5) * TILE_SIZE) - cam_x - 2
    cot_y_top = 9 * TILE_SIZE - cam_y
    cot_y_bot = 12 * TILE_SIZE - cam_y
    cot_w = 24
    cot_h = cot_y_bot - cot_y_top
    cot_shad = pygame.Surface((cot_w + 8, cot_h + 4), pygame.SRCALPHA)
    render_util.soft_shadow(cot_shad, (0, 0, cot_w + 8, cot_h + 4), 70)
    screen.blit(cot_shad, (cot_x - cot_w // 2 - 4, cot_y_top))
    frame_col = (32, 30, 28)
    frame_edge = (50, 46, 42)
    frame_r = pygame.Rect(cot_x - cot_w // 2, cot_y_top, cot_w, cot_h)
    pygame.draw.rect(screen, frame_col, frame_r, border_radius=2)
    pygame.draw.rect(screen, frame_edge, frame_r, 1, border_radius=2)
    matt_col = (54, 50, 44)
    matt_r = pygame.Rect(cot_x - cot_w // 2 + 2, cot_y_top + 2, cot_w - 4, cot_h - 4)
    pygame.draw.rect(screen, matt_col, matt_r, border_radius=1)
    mesh_col = (44, 40, 36)
    for my in range(matt_r.top + 4, matt_r.bottom - 2, 5):
        pygame.draw.line(screen, mesh_col, (matt_r.left + 2, my), (matt_r.right - 2, my), 1)
    for mx in range(matt_r.left + 4, matt_r.right - 2, 5):
        pygame.draw.line(screen, mesh_col, (mx, matt_r.top + 2), (mx, matt_r.bottom - 2), 1)
    pillow_col = (66, 60, 52)
    pillow_r = pygame.Rect(cot_x - cot_w // 2 + 3, cot_y_top + 3, cot_w - 6, 10)
    pygame.draw.rect(screen, pillow_col, pillow_r, border_radius=2)
    pygame.draw.rect(screen, (80, 74, 64), pillow_r, 1, border_radius=2)
    pygame.draw.line(screen, (50, 46, 40), (pillow_r.left + 2, pillow_r.centery), (pillow_r.right - 2, pillow_r.centery), 1)
    leg_col = (24, 22, 20)
    leg_hi = (44, 40, 36)
    for (lx, ly) in [(cot_x - cot_w // 2, cot_y_top), (cot_x + cot_w // 2, cot_y_top), (cot_x - cot_w // 2, cot_y_bot), (cot_x + cot_w // 2, cot_y_bot)]:
        pygame.draw.circle(screen, leg_col, (int(lx), int(ly)), 3)
        pygame.draw.circle(screen, leg_hi, (int(lx), int(ly)), 3, 1)

    # Stainless steel sink
    sink_cx = int((_CELL_COL_EAST + 0.5) * TILE_SIZE) - cam_x - 4
    sink_cy = int((_CELL_ROW_NORTH + 0.5) * TILE_SIZE + 2) - cam_y
    sink_shad = pygame.Surface((32, 22), pygame.SRCALPHA)
    render_util.soft_shadow(sink_shad, (0, 0, 32, 22), 80)
    screen.blit(sink_shad, (sink_cx - 16, sink_cy - 6))
    rim_col = (110, 112, 116)
    rim_dark = (70, 72, 76)
    pygame.draw.ellipse(screen, rim_col, (sink_cx - 14, sink_cy - 9, 28, 18))
    pygame.draw.ellipse(screen, rim_dark, (sink_cx - 14, sink_cy - 9, 28, 18), 1)
    basin_col = (80, 82, 86)
    pygame.draw.ellipse(screen, basin_col, (sink_cx - 11, sink_cy - 6, 22, 12))
    deep = pygame.Surface((22, 5), pygame.SRCALPHA)
    render_util.soft_shadow(deep, (0, 0, 22, 5), 90)
    screen.blit(deep, (sink_cx - 11, sink_cy - 6))
    pygame.draw.circle(screen, (16, 16, 18), (sink_cx, sink_cy + 1), 3)
    pygame.draw.circle(screen, (6, 6, 8), (sink_cx, sink_cy + 1), 2)
    pygame.draw.line(screen, (40, 40, 42), (sink_cx - 2, sink_cy + 1), (sink_cx + 2, sink_cy + 1), 1)
    pygame.draw.line(screen, (40, 40, 42), (sink_cx, sink_cy - 1), (sink_cx, sink_cy + 3), 1)
    faucet_col = (120, 122, 126)
    faucet_dark = (80, 82, 86)
    pygame.draw.line(screen, faucet_col, (sink_cx, sink_cy - 8), (sink_cx, sink_cy - 16), 3)
    pygame.draw.line(screen, faucet_dark, (sink_cx + 1, sink_cy - 8), (sink_cx + 1, sink_cy - 16), 1)
    pygame.draw.line(screen, faucet_col, (sink_cx, sink_cy - 16), (sink_cx + 5, sink_cy - 16), 3)
    pygame.draw.line(screen, faucet_dark, (sink_cx, sink_cy - 15), (sink_cx + 5, sink_cy - 15), 1)
    pygame.draw.circle(screen, faucet_dark, (sink_cx + 5, sink_cy - 16), 2)
    pygame.draw.arc(screen, (160, 162, 166), (sink_cx - 12, sink_cy - 7, 24, 14), math.pi * 1.1, math.pi * 1.9, 2)
    pygame.draw.line(screen, (50, 52, 56), (sink_cx - 4, sink_cy - 2), (sink_cx - 2, sink_cy), 1)


# Stages at/after which the Vostral dossier physically exists in the world
# (Archives phase onward: it sits in the cold vault, then in Biribel's hands).
# Before that - Slice 1 (interrogation) and Slice 2 (breakout) - the Vostral is
# only a rumor, so no dossier prop or "VOSTRAL" sign may render on the
# cell-block map.
_VOSTRAL_PRESENT_STAGES = (
    STAGE_ARCHIVES, STAGE_ARCHIVES_TRANSITION, STAGE_KILL_ORDER,
    STAGE_KO_TRANSITION, STAGE_BROADCAST, STAGE_BROADCAST_TRANSITION,
    STAGE_VENT_CUTSCENE, STAGE_DONE,
)


def _vostral_present_in_timeline():
    """True only once the Vostral actually exists in the mission timeline.

    Mirrors the gating the real Vostral visuals already use
    (STATE.m3_vostral_acquired) and extends it to the Archives-onward stages,
    so remains-cell set dressing cannot spoil the reveal in Slices 1-2.
    """
    stage = getattr(STATE, "mission3_stage", STAGE_INTERROGATION)
    if stage in _VOSTRAL_PRESENT_STAGES:
        return True
    return bool(getattr(STATE, "m3_vostral_acquired", False))


def _draw_neighbor_cell_base(cell_idx, L, T, W, H, vostral=None, live=True):
    """Extra atmosphere/detail pass for the non-player cells.

    Makes the side cells read as distinct rooms instead of plain grey boxes:
    - unique color wash per cell
    - ceiling light / shadow falloff
    - grime, cracks, warning plaques
    - foreground bars / cell numbers
    - extra themed clutter
    """
    ix, iy, iw, ih = int(L), int(T), int(W), int(H)

    themes = [
        # cell_idx 0 - storage / archives overflow
        {
            "tint": (85, 70, 35),
            "label": "CELL 01 / STORAGE",
            "sub": "ARCHIVE OVERFLOW",
            "accent": (190, 150, 70),
        },
        # cell_idx 1 - torture / interrogation overflow
        {
            "tint": (105, 28, 22),
            "label": "CELL 02 / INTERVIEW",
            "sub": "CLEANED DAILY",
            "accent": (210, 65, 45),
        },
        # cell_idx 2 - remains / Vostral rumor cell
        {
            "tint": (45, 82, 60),
            "label": "CELL 03 / NO LOG",
            "sub": "TRANSFER RECORD MISSING",
            "accent": (110, 180, 130),
        },
    ]

    theme = themes[cell_idx]
    tint = theme["tint"]
    accent = theme["accent"]

    # ── Cell-wide colored grime wash ──
    wash = pygame.Surface((iw, ih), pygame.SRCALPHA)
    for yy in range(ih):
        p = yy / max(1, ih)
        a = int(14 + p * 34)
        pygame.draw.line(wash, (*tint, a), (0, yy), (iw, yy))
    screen.blit(wash, (ix, iy))

    # ── Dark corners / cell occlusion ──
    edge = pygame.Surface((iw, ih), pygame.SRCALPHA)
    pygame.draw.rect(edge, (0, 0, 0, 110), (0, 0, iw, ih), 3)
    pygame.draw.rect(edge, (0, 0, 0, 55), (4, 4, iw - 8, ih - 8), 2)
    screen.blit(edge, (ix, iy))

    # ── Broken fluorescent strip / mood light ──
    light_x = ix + iw // 2 + (-48 if cell_idx == 0 else 0 if cell_idx == 1 else 46)
    light_y = iy + 12

    pygame.draw.rect(screen, (18, 18, 17), (light_x - 34, light_y - 4, 68, 8), border_radius=2)

    light_col = _NEIGHBOR_LIGHT_COLS[cell_idx]
    if live:   # flickering tube (per-frame) -> _draw_neighbor_cells_live
        _draw_neighbor_cell_tube(cell_idx, light_x, light_y, ix, iy, iw, ih)

    # Light pool on the floor
    pool = pygame.Surface((iw, ih), pygame.SRCALPHA)
    pygame.draw.ellipse(
        pool,
        (*light_col, 26),
        (iw // 2 - 115, 18, 230, ih - 30),
    )
    screen.blit(pool, (ix, iy))

    # ── Cell number / warning plaque ──
    plaque = pygame.Surface((150, 30), pygame.SRCALPHA)
    plaque.fill((0, 0, 0, 145))
    pygame.draw.rect(plaque, (*accent, 145), plaque.get_rect(), 1)
    pygame.draw.rect(plaque, (*accent, 180), (0, 0, 4, 30))
    lbl = font_terminal_small.render(theme["label"], True, accent)
    sub = font_terminal_small.render(theme["sub"], True, (140, 130, 110))
    plaque.blit(lbl, (8, 3))
    plaque.blit(sub, (8, 16))
    screen.blit(plaque, (ix + 8, iy + ih - 38))

    # ── Deterministic grime, cracks, scratches ──
    rng = random.Random(9100 + cell_idx)

    for stain, pos in _neighbor_cell_stains(rng, ix, iy, iw, ih):
        screen.blit(stain, pos)

    for _ in range(6):
        cx = ix + rng.randint(20, max(24, iw - 24))
        cy = iy + rng.randint(28, max(32, ih - 28))
        pts = [(cx, cy)]
        for _seg in range(rng.randint(2, 4)):
            pts.append((pts[-1][0] + rng.randint(-20, 20),
                        pts[-1][1] + rng.randint(-12, 18)))
        pygame.draw.lines(screen, (18, 16, 14), False, pts, 1)

    # ── Stronger bars / foreground shadow at cell opening ──
    bar_y = iy + ih - 18
    for bx in range(ix + 14, ix + iw - 10, 22):
        pygame.draw.line(screen, (8, 8, 9), (bx, bar_y), (bx, iy + ih + 8), 3)
        pygame.draw.line(screen, (50, 50, 55), (bx - 1, bar_y), (bx - 1, iy + ih + 8), 1)

    # ── Themed extra clutter per neighboring cell ──
    if cell_idx == 0:
        # Storage shelves with folders and evidence boxes
        shelf_x = ix + iw - 58
        shelf_y = iy + 48
        pygame.draw.rect(screen, (36, 32, 24), (shelf_x, shelf_y, 42, ih - 100))
        pygame.draw.rect(screen, (88, 64, 34), (shelf_x, shelf_y, 42, ih - 100), 2)

        for row in range(4):
            yy = shelf_y + 14 + row * 34
            pygame.draw.line(screen, (62, 44, 24), (shelf_x + 3, yy), (shelf_x + 39, yy), 2)

            for b in range(3):
                bx = shelf_x + 6 + b * 11
                by = yy - 11
                col = rng.choice([(120, 96, 52), (92, 80, 58), (130, 110, 72)])
                pygame.draw.rect(screen, col, (bx, by, 8, 10))
                pygame.draw.rect(screen, (45, 34, 22), (bx, by, 8, 10), 1)

        tag = font_terminal_small.render(_T("m3.evidence_hold"), True, (190, 150, 70))
        tag.set_alpha(160)
        screen.blit(tag, (ix + 20, iy + 42))

    elif cell_idx == 1:
        # Restraint chair / bloody cleaning tray
        table = pygame.Rect(ix + iw // 2 - 36, iy + ih // 2 - 12, 72, 24)
        render_util.soft_shadow(screen, (table.x - 6, table.y + 12, table.w + 12, 22), 90)
        pygame.draw.rect(screen, (56, 48, 42), table, border_radius=3)
        pygame.draw.rect(screen, (95, 80, 66), table, 2, border_radius=3)

        for strap_y in (table.y + 5, table.y + 17):
            pygame.draw.line(screen, (20, 16, 12), (table.x + 6, strap_y), (table.right - 6, strap_y), 3)

        # Small red-stained drain
        dx = ix + iw // 2 + 70
        dy = iy + ih // 2 + 34
        pygame.draw.circle(screen, (28, 24, 20), (dx, dy), 10)
        pygame.draw.circle(screen, (8, 6, 5), (dx, dy), 6)
        pygame.draw.ellipse(screen, (70, 8, 8, 120), (dx - 20, dy - 7, 40, 14))

        # Hanging hook silhouettes
        for hx in (ix + 42, ix + 72, ix + iw - 70):
            pygame.draw.line(screen, (46, 44, 42), (hx, iy + 10), (hx, iy + 40), 2)
            pygame.draw.arc(screen, (75, 70, 64), (hx - 6, iy + 34, 12, 14), 0, math.pi * 1.4, 2)

    elif cell_idx == 2:
        if live:   # flies around the remains (per-frame) -> _draw_neighbor_cells_live
            _draw_neighbor_cell_flies(ix, iy, iw, ih)

        # Vostral dossier + its "VOSTRAL" sign. Gated: the file only exists in
        # the world from the Archives phase onward (Slice 4+). In Slices 1-2 the
        # Vostral is still a rumor, so neither the book-shaped prop nor the
        # sign may render here.
        if _vostral_present_in_timeline() if vostral is None else vostral:
            doc_x = ix + iw - 92
            doc_y = iy + ih - 92
            pygame.draw.rect(screen, (110, 100, 72), (doc_x, doc_y, 46, 30))
            pygame.draw.rect(screen, (58, 48, 32), (doc_x, doc_y, 46, 30), 1)
            pygame.draw.line(screen, (70, 56, 38), (doc_x + 5, doc_y + 10), (doc_x + 40, doc_y + 10), 1)
            pygame.draw.line(screen, (70, 56, 38), (doc_x + 5, doc_y + 18), (doc_x + 34, doc_y + 18), 1)

            stamp = font_terminal_small.render(_T("m3.vostral"), True, (110, 180, 130))
            stamp.set_alpha(170)
            screen.blit(stamp, (doc_x + 4, doc_y - 16))


def _draw_cell_details_live(cam_x, cam_y):
    """Per-frame part of the cell dressing: the loudspeaker LED blink (drawn
    over the baked ``cell_details`` layer or inline by the live painter)."""
    speaker_x = (_CELL_COL_EAST + 1) * TILE_SIZE - cam_x - 10
    speaker_y = (_CELL_ROW_NORTH + 1) * TILE_SIZE - cam_y - 2
    led_on = (_now_ms() // 1200) % 3 != 0
    pygame.draw.circle(screen, (200 if led_on else 60, 20, 20), (speaker_x + 4, speaker_y + 2), 1)


_NEIGHBOR_LIGHT_COLS = ((210, 185, 115), (180, 55, 45), (120, 190, 145))


def _neighbor_cell_screen_rect(cell_idx, cam_x, cam_y):
    """Interior of neighbour cell ``cell_idx`` (0..2) in screen space: (L, T, W, H)."""
    col_start = 6 + cell_idx * 8
    L = (col_start + 1) * TILE_SIZE - cam_x
    R = (col_start + 7) * TILE_SIZE - cam_x
    T = (_CELL_ROW_NORTH + 1) * TILE_SIZE - cam_y
    B = _CELL_ROW_SOUTH * TILE_SIZE - cam_y
    return L, T, R - L, B - T


def _neighbor_cell_stains(rng, ix, iy, iw, ih):
    """The ten grime stains of a neighbour cell as (surface, screen pos); consumes ``rng`` exactly
    like the original inline loop (the crack pass continues on the same generator)."""
    out = []
    for _ in range(10):
        sx = ix + rng.randint(10, max(12, iw - 28))
        sy = iy + rng.randint(8, max(10, ih - 36))
        sh = rng.randint(16, 50)
        stain = pygame.Surface((12, sh), pygame.SRCALPHA)
        for yy in range(sh):
            a = int(45 * (1 - yy / max(1, sh)))
            pygame.draw.line(stain, (12, 10, 8, a), (6, yy), (6 + rng.randint(-3, 3), yy))
        out.append((stain, (sx, sy)))
    return out


_NC_TUBE_STAINS = {}


def _draw_neighbor_cell_tube(cell_idx, light_x, light_y, ix, iy, iw, ih, over_bake=False):
    """Flickering light tube of a neighbour cell. ``over_bake``: the tube goes on top of the baked
    layer, so the grime stains the painter draws *after* the tube are re-composited over it
    (off-screen, same blend order) and the four corner pixels the rounded rect never paints are
    kept - bit-identical to the inline draw."""
    flicker = 0.7 + 0.3 * math.sin(_now_s() * (5.0 + cell_idx))
    col = tuple(int(c * flicker) for c in _NEIGHBOR_LIGHT_COLS[cell_idx])
    rect = pygame.Rect(light_x - 30, light_y - 2, 60, 4)
    if not over_bake:
        pygame.draw.rect(screen, col, rect, border_radius=2)
        return
    overlays = _NC_TUBE_STAINS.get(cell_idx)
    if overlays is None:
        # Everything the painters draw over the tube later, relative to the cell interior
        # (deterministic): the grime stains that intersect it and, in the interview cell, the
        # first graffiti line (``_draw_neighbor_cells``). Verified by gp.m3.cell_a/b/c.
        overlays = []
        for stain, (sx, sy) in _neighbor_cell_stains(random.Random(9100 + cell_idx), ix, iy, iw, ih):
            if stain.get_rect(topleft=(sx, sy)).colliderect(rect):
                overlays.append((stain, (sx - ix, sy - iy)))
        if cell_idx == 1:
            t1 = font_terminal_small.render(_T("m3.they_took_everything"), True, (60, 54, 44))
            t1.set_alpha(180)
            overlays.append((t1, (10, 6)))
        _NC_TUBE_STAINS[cell_idx] = overlays
    tmp = pygame.Surface(rect.size)
    tmp.fill(col)
    for over, (dx, dy) in overlays:
        tmp.blit(over, (ix + dx - rect.x, iy + dy - rect.y))
    bounds = screen.get_rect()
    corners = [(p, screen.get_at(p)) for p in ((rect.x, rect.y), (rect.right - 1, rect.y),
                                               (rect.x, rect.bottom - 1), (rect.right - 1, rect.bottom - 1))
               if bounds.collidepoint(p)]
    screen.blit(tmp, rect)
    for p, c in corners:
        screen.set_at(p, c)


def _draw_neighbor_cell_flies(ix, iy, iw, ih):
    fly_t = _now_s() * 4.0
    for i in range(14):
        fx = ix + iw // 2 + math.sin(fly_t + i * 1.7) * (18 + i % 4 * 4)
        fy = iy + ih // 2 + math.cos(fly_t * 0.7 + i * 2.1) * (14 + i % 3 * 3)
        pygame.draw.circle(screen, (4, 4, 4), (int(fx), int(fy)), 1)


def _draw_remains_cell_scraps(L, T, W, H):
    """Paper scraps on the remains-cell floor (deterministic). Drawn by the painter after the flies,
    so the live fly pass redraws them on top - identical z-order."""
    scrap_rng = random.Random(2010)
    for _ in range(8):
        px = int(L + 30 + scrap_rng.randint(0, max(1, W - 60)))
        py = int(T + 55 + scrap_rng.randint(0, max(1, H - 90)))
        pw = scrap_rng.randint(8, 12)
        ph = scrap_rng.randint(5, 8)
        pygame.draw.rect(screen, (115, 108, 86), (px, py, pw, ph))
        pygame.draw.rect(screen, (75, 68, 50), (px, py, pw, ph), 1)
        # Text line on paper
        pygame.draw.line(screen, (58, 52, 40), (px + 2, py + 3), (px + pw - 2, py + 3), 1)


def _draw_neighbor_cells_live(cam_x, cam_y):
    """Per-frame bits of the neighbour cells (drawn right after the baked layer): the flickering
    light tubes and the flies in the remains cell. Clipped to each cell like the painter."""
    for cell_idx in range(3):
        L, T, W, H = _neighbor_cell_screen_rect(cell_idx, cam_x, cam_y)
        if L + W < -40 or L > WIDTH + 40 or T + H < -40 or T > HEIGHT + 40:
            continue
        ix, iy, iw, ih = int(L), int(T), int(W), int(H)
        old_clip = screen.get_clip()
        screen.set_clip(pygame.Rect(ix, iy, iw, ih))
        try:
            _draw_neighbor_cell_tube(cell_idx, ix + iw // 2 + (-48 if cell_idx == 0 else 0 if cell_idx == 1 else 46), iy + 12,
                                     ix, iy, iw, ih, over_bake=True)
            if cell_idx == 2:
                _draw_neighbor_cell_flies(ix, iy, iw, ih)
                _draw_remains_cell_scraps(L, T, W, H)   # the only later paint that can cover a fly
        finally:
            screen.set_clip(old_clip)


def _draw_neighbor_cells(cam_x, cam_y, vostral=None, live=True):
    """Draw props inside cells 0, 1, 2 (the 3 cells next to yours).

    Does not touch floors, walls, or your cell (cell 3).
    Uses world-to-screen math that matches the tilemap exactly.

    ``vostral`` pins the dossier variant for the bake (default: timeline gate); ``live=False``
    skips the per-frame parts (tube flicker, flies), which ``_draw_neighbor_cells_live`` draws.
    """
    if vostral is None:
        vostral = _vostral_present_in_timeline()
    for cell_idx in range(3):
        col_start = 6 + cell_idx * 8

        # World-space cell interior (1 tile inset from walls on each side)
        world_left   = (col_start + 1) * TILE_SIZE
        world_right  = (col_start + 7) * TILE_SIZE
        world_top    = (_CELL_ROW_NORTH + 1) * TILE_SIZE
        world_bottom = _CELL_ROW_SOUTH * TILE_SIZE

        # Screen-space
        L = world_left - cam_x
        R = world_right - cam_x
        T = world_top - cam_y
        B = world_bottom - cam_y
        W = R - L
        H = B - T

        # Skip if off screen
        if R < -40 or L > WIDTH + 40 or B < -40 or T > HEIGHT + 40:
            continue

        # Clip to cell interior
        old_clip = screen.get_clip()
        screen.set_clip(pygame.Rect(int(L), int(T), int(W), int(H)))

        try:
            _draw_neighbor_cell_base(cell_idx, L, T, W, H, vostral=vostral, live=live)

            if cell_idx == 2:
                # ════════════════════════════════════
                # REMAINS CELL - skeleton on cot, bucket, Vostral graffiti
                # ════════════════════════════════════

                # ── Cot against west wall ──
                cot_x = int(L + 6)
                cot_y = int(T + 20)
                cot_w = 20
                cot_h = 52
                # Shadow
                render_util.soft_shadow(screen, (cot_x - 2, cot_y + cot_h - 2, cot_w + 4, 6), 60)
                # Frame
                pygame.draw.rect(screen, (40, 36, 32), (cot_x, cot_y, cot_w, cot_h), border_radius=2)
                pygame.draw.rect(screen, (52, 48, 42), (cot_x, cot_y, cot_w, cot_h), 1, border_radius=2)
                # Mattress
                pygame.draw.rect(screen, (44, 40, 34), (cot_x + 2, cot_y + 2, cot_w - 4, cot_h - 4))
                # Blood on mattress
                pygame.draw.ellipse(screen, (52, 10, 10, 140), (cot_x + 4, cot_y + 12, 12, 8))
                # Mesh lines
                for my in range(cot_y + 8, cot_y + cot_h - 4, 6):
                    pygame.draw.line(screen, (32, 28, 24), (cot_x + 3, my), (cot_x + cot_w - 3, my), 1)

                # ── Skeleton on the cot ──
                sk_x = cot_x + cot_w // 2
                sk_y = cot_y + 10
                # Skull
                pygame.draw.circle(screen, (198, 190, 174), (sk_x, sk_y), 5)
                pygame.draw.circle(screen, (14, 12, 10), (sk_x, sk_y), 5, 1)
                # Eye sockets
                pygame.draw.circle(screen, (10, 8, 6), (sk_x - 2, sk_y), 1)
                pygame.draw.circle(screen, (10, 8, 6), (sk_x + 2, sk_y), 1)
                # Jaw
                pygame.draw.arc(screen, (14, 12, 10), (sk_x - 3, sk_y + 1, 6, 4), 0, math.pi, 1)
                # Spine
                pygame.draw.line(screen, (198, 190, 174), (sk_x, sk_y + 5), (sk_x, sk_y + 28), 2)
                # Ribs (4 pairs)
                for ri in range(4):
                    ry = sk_y + 9 + ri * 5
                    pygame.draw.line(screen, (190, 182, 166), (sk_x, ry), (sk_x - 5, ry + 2), 1)
                    pygame.draw.line(screen, (190, 182, 166), (sk_x, ry), (sk_x + 5, ry + 2), 1)
                # Pelvis
                pygame.draw.arc(screen, (190, 182, 166), (sk_x - 4, sk_y + 28, 8, 4), math.pi, math.tau, 1)
                # Legs (splayed)
                pygame.draw.line(screen, (190, 182, 166), (sk_x - 2, sk_y + 32), (sk_x - 6, sk_y + 44), 1)
                pygame.draw.line(screen, (190, 182, 166), (sk_x + 2, sk_y + 32), (sk_x + 5, sk_y + 42), 1)

                # ── Rusted sink (NE corner) ──
                sink_x = int(R - 28)
                sink_y = int(T + 8)
                pygame.draw.ellipse(screen, (78, 54, 35), (sink_x, sink_y, 18, 12))
                pygame.draw.ellipse(screen, (48, 34, 20), (sink_x, sink_y, 18, 12), 1)
                pygame.draw.ellipse(screen, (42, 30, 18), (sink_x + 3, sink_y + 3, 12, 6))
                pygame.draw.circle(screen, (10, 8, 6), (sink_x + 9, sink_y + 6), 2)
                # Rust drip stain below sink
                pygame.draw.line(screen, (65, 42, 22), (sink_x + 9, sink_y + 12), (sink_x + 9, sink_y + 22), 2)
                pygame.draw.line(screen, (55, 36, 18), (sink_x + 8, sink_y + 18), (sink_x + 10, sink_y + 28), 1)

                # ── Rusted bucket ──
                bk_x = int(R - 55)
                bk_y = int(B - 28)
                render_util.soft_shadow(screen, (bk_x - 7, bk_y + 4, 14, 6), 65)
                pygame.draw.circle(screen, (72, 48, 26), (bk_x, bk_y), 6)
                pygame.draw.circle(screen, (42, 28, 14), (bk_x, bk_y), 6, 2)
                pygame.draw.circle(screen, (18, 14, 10), (bk_x, bk_y), 3)
                # Bucket handle
                pygame.draw.arc(screen, (55, 45, 30), (bk_x - 5, bk_y - 8, 10, 8), 0, math.pi, 1)

                # ── Scratched wall text ──
                t1 = font_terminal_small.render(_T("m3.the_vostral_is_real"), True, (62, 56, 46))
                t1.set_alpha(185)
                screen.blit(t1, (int(L + 10), int(T + 6)))

                t2 = font_terminal_small.render(_T("m3.they_lied_about_his_service"), True, (55, 50, 42))
                t2.set_alpha(150)
                screen.blit(t2, (int(L + 10), int(T + 20)))

                t3 = font_terminal_small.render(_T("m3.the_record_exists"), True, (50, 45, 38))
                t3.set_alpha(130)
                screen.blit(t3, (int(L + 10), int(T + 34)))

                # ── Blood smears on floor ──
                for bx_off, by_off, bsz in [(65, H - 45, 22), (W // 2, H - 30, 14)]:
                    bl = pygame.Surface((bsz * 2, int(bsz * 1.2)), pygame.SRCALPHA)
                    pygame.draw.ellipse(bl, (48, 8, 8, 130), bl.get_rect())
                    screen.blit(bl, (int(L + bx_off - bsz), int(T + by_off)))

                # ── Paper scraps on floor ──
                _draw_remains_cell_scraps(L, T, W, H)

            elif cell_idx == 1:
                # ════════════════════════════════════
                # TORTURE CELL - chains, blood, torn cot, drag marks
                # ════════════════════════════════════

                # ── Torn cot ──
                cot_x = int(L + 6)
                cot_y = int(T + 20)
                cot_w = 20
                cot_h = 52
                render_util.soft_shadow(screen, (cot_x - 2, cot_y + cot_h - 2, cot_w + 4, 6), 60)
                pygame.draw.rect(screen, (40, 36, 32), (cot_x, cot_y, cot_w, cot_h), border_radius=2)
                pygame.draw.rect(screen, (52, 48, 42), (cot_x, cot_y, cot_w, cot_h), 1, border_radius=2)
                pygame.draw.rect(screen, (44, 40, 34), (cot_x + 2, cot_y + 2, cot_w - 4, cot_h - 4))
                # Rip across mattress
                pygame.draw.line(screen, (12, 10, 8), (cot_x + 3, cot_y + 16), (cot_x + cot_w - 3, cot_y + 30), 3)
                # Cotton stuffing
                for ox, oy in [(-5, 22), (7, 28), (2, 34), (10, 18)]:
                    pygame.draw.circle(screen, (162, 155, 142), (cot_x + cot_w // 2 + ox, cot_y + oy), 3)
                    pygame.draw.circle(screen, (140, 134, 122), (cot_x + cot_w // 2 + ox, cot_y + oy), 3, 1)

                # ── Rusted sink ──
                sink_x = int(R - 28)
                sink_y = int(T + 8)
                pygame.draw.ellipse(screen, (78, 54, 35), (sink_x, sink_y, 18, 12))
                pygame.draw.ellipse(screen, (48, 34, 20), (sink_x, sink_y, 18, 12), 1)
                pygame.draw.ellipse(screen, (42, 30, 18), (sink_x + 3, sink_y + 3, 12, 6))

                # ── Wall chains (two sets) ──
                for chain_x_off in (35, 90):
                    cx = int(L + chain_x_off)
                    cy = int(T + 4)
                    # Wall anchor bolt
                    pygame.draw.circle(screen, (55, 52, 48), (cx, cy), 3)
                    pygame.draw.circle(screen, (35, 32, 28), (cx, cy), 3, 1)
                    # Chain links
                    for i in range(6):
                        pygame.draw.ellipse(screen, (52, 52, 58),
                                            (cx - 2, cy + 4 + i * 5, 4, 6), 1)
                    # Open shackle at bottom
                    pygame.draw.ellipse(screen, (82, 78, 68),
                                        (cx - 5, cy + 34, 10, 6), 1)
                    pygame.draw.circle(screen, (75, 72, 64), (cx - 5, cy + 37), 2)

                # ── Heavy blood pools ──
                for bx_off, by_off, bsz in [
                    (W // 3, H // 3, 28),
                    (W * 2 // 3, H - 40, 18),
                    (W // 2 - 10, H // 2 + 20, 14),
                ]:
                    bl = pygame.Surface((bsz * 2, int(bsz * 1.4)), pygame.SRCALPHA)
                    pygame.draw.ellipse(bl, (50, 8, 8, 145), bl.get_rect())
                    pygame.draw.ellipse(bl, (30, 4, 4, 175),
                                        (bsz // 3, bsz // 4, bsz, int(bsz * 0.7)))
                    screen.blit(bl, (int(L + bx_off - bsz), int(T + by_off)))

                # ── Floor drag marks ──
                for i in range(5):
                    y0 = int(T + H // 3 + i * 12)
                    pygame.draw.line(screen, (55, 10, 10),
                                     (int(L + 40), y0),
                                     (int(L + 110), y0 + 14), 1)

                # ── Scratched text ──
                t1 = font_terminal_small.render(_T("m3.they_took_everything"), True, (60, 54, 44))
                t1.set_alpha(180)
                screen.blit(t1, (int(L + 10), int(T + 6)))

                t2 = font_terminal_small.render(_T("m3.do_not_confess"), True, (55, 50, 42))
                t2.set_alpha(150)
                screen.blit(t2, (int(L + 10), int(T + 20)))

                t3 = font_terminal_small.render(_T("m3.i_will_not_break"), True, (50, 44, 38))
                t3.set_alpha(120)
                screen.blit(t3, (int(L + 10), int(T + 34)))

            elif cell_idx == 0:
                # ════════════════════════════════════
                # STORAGE CELL - crates, cabinets, folders, clutter
                # ════════════════════════════════════

                # ── Stacked crates (two, against south wall) ──
                for i, col in enumerate([(82, 54, 26), (96, 66, 34)]):
                    cx = int(L + 10 + i * 3)
                    cy = int(B - 36 - i * 16)
                    pygame.draw.rect(screen, (0, 0, 0, 55), (cx + 2, cy + 2, 24, 18))
                    pygame.draw.rect(screen, col, (cx, cy, 24, 18), border_radius=1)
                    pygame.draw.rect(screen, (28, 18, 8), (cx, cy, 24, 18), 1, border_radius=1)
                    # Cross plank
                    pygame.draw.line(screen, (28, 18, 8), (cx + 1, cy + 1), (cx + 23, cy + 17), 1)
                    pygame.draw.line(screen, (28, 18, 8), (cx + 23, cy + 1), (cx + 1, cy + 17), 1)
                    # Plank seam
                    pygame.draw.line(screen, (28, 18, 8), (cx, cy + 9), (cx + 24, cy + 9), 1)

                # ── Filing cabinets (two, against north wall) ──
                for cx_off, cy_off in [(W // 3 - 12, 14), (W * 2 // 3 - 12, 32)]:
                    cab_x = int(L + cx_off)
                    cab_y = int(T + cy_off)
                    # Shadow
                    pygame.draw.rect(screen, (0, 0, 0, 55), (cab_x + 2, cab_y + 2, 26, 20))
                    # Body
                    pygame.draw.rect(screen, (34, 44, 38), (cab_x, cab_y, 26, 20))
                    pygame.draw.rect(screen, (20, 28, 22), (cab_x, cab_y, 26, 20), 1)
                    # Two drawers
                    for dx in (0, 13):
                        pygame.draw.rect(screen, (22, 30, 26),
                                         (cab_x + dx + 1, cab_y + 2, 11, 16))
                        pygame.draw.rect(screen, (16, 22, 18),
                                         (cab_x + dx + 1, cab_y + 2, 11, 16), 1)
                        # Brass handle
                        pygame.draw.line(screen, (132, 108, 48),
                                         (cab_x + dx + 3, cab_y + 10),
                                         (cab_x + dx + 9, cab_y + 10), 2)

                # ── Loose folders scattered on floor ──
                folder_rng = random.Random(3010)
                for _ in range(8):
                    fx = int(L + 25 + folder_rng.randint(0, max(1, W - 50)))
                    fy = int(T + 60 + folder_rng.randint(0, max(1, H - 100)))
                    fw = folder_rng.randint(12, 16)
                    fh = folder_rng.randint(8, 10)
                    fcol = folder_rng.choice([
                        (125, 112, 74), (135, 118, 82), (115, 102, 68)
                    ])
                    pygame.draw.rect(screen, fcol, (fx, fy, fw, fh))
                    pygame.draw.rect(screen, (62, 52, 32), (fx, fy, fw, fh), 1)
                    # Text lines on folder
                    pygame.draw.line(screen, (58, 50, 38), (fx + 2, fy + 3), (fx + fw - 2, fy + 3), 1)
                    if fh > 8:
                        pygame.draw.line(screen, (58, 50, 38), (fx + 2, fy + 6), (fx + fw - 4, fy + 6), 1)

                # ── Junk pile in corner ──
                junk_x = int(R - 30)
                junk_y = int(B - 26)
                render_util.soft_shadow(screen, (junk_x - 10, junk_y + 4, 22, 8), 50)
                pygame.draw.polygon(screen, (88, 78, 62),
                                    [(junk_x - 6, junk_y), (junk_x + 2, junk_y - 10),
                                     (junk_x + 12, junk_y - 2), (junk_x + 6, junk_y + 6)])
                pygame.draw.polygon(screen, (68, 58, 42),
                                    [(junk_x - 6, junk_y), (junk_x + 2, junk_y - 10),
                                     (junk_x + 12, junk_y - 2), (junk_x + 6, junk_y + 6)], 1)
                pygame.draw.circle(screen, (48, 44, 38), (junk_x - 8, junk_y + 4), 3)
                pygame.draw.circle(screen, (32, 28, 24), (junk_x + 10, junk_y - 4), 4)

                # ── Scratched text ──
                t1 = font_terminal_small.render(_T("m3.do_not_open"), True, (60, 54, 44))
                t1.set_alpha(180)
                screen.blit(t1, (int(L + 10), int(T + 6)))

                t2 = font_terminal_small.render(_T("m3.archive_transfer_void"), True, (52, 48, 40))
                t2.set_alpha(140)
                screen.blit(t2, (int(L + 10), int(T + 20)))

            # Final foreground grime/bar pass so the cells feel boxed-in.
            pygame.draw.rect(screen, (0, 0, 0, 75), (int(L), int(T), int(W), int(H)), 2)

        finally:
            screen.set_clip(old_clip)


def _draw_kitchen_details(cam_x, cam_y):
    """Draw the prison kitchen/utility room as a coherent top-down space.

    The old pass was three isolated props on huge 64px checker tiles. This
    keeps the same collision footprint, but adds a clipped room treatment:
    smaller floor tiles, wall backsplash, shelves, stains, vent hatch, and
    stainless fixtures that match the rest of Mission 3's grimy institutional
    style.
    """
    room_x = 2 * TILE_SIZE - cam_x
    room_y = 20 * TILE_SIZE - cam_y
    room_w = 5 * TILE_SIZE
    room_h = 5 * TILE_SIZE

    if room_x > WIDTH + 80 or room_x + room_w < -80 or room_y > HEIGHT + 80 or room_y + room_h < -80:
        return

    old_clip = screen.get_clip()
    screen.set_clip(pygame.Rect(int(room_x), int(room_y), room_w, room_h))

    try:
        # Interior floor: cols 3-5 / rows 21-23. Door threshold is col 6,row22.
        ix = 3 * TILE_SIZE - cam_x
        iy = 21 * TILE_SIZE - cam_y
        iw = 3 * TILE_SIZE
        ih = 3 * TILE_SIZE

        # Subtle unified floor base over the K tiles.
        pygame.draw.rect(screen, (38, 42, 43), (ix, iy, iw, ih))
        # Smaller institutional tiles so the kitchen stops looking like three
        # giant checkerboard blocks.
        for ty in range(int(iy), int(iy + ih) + 1, 16):
            pygame.draw.line(screen, (27, 30, 31), (ix, ty), (ix + iw, ty), 1)
        for tx in range(int(ix), int(ix + iw) + 1, 16):
            pygame.draw.line(screen, (27, 30, 31), (tx, iy), (tx, iy + ih), 1)
        # Uneven grime passes.
        grime_rng = random.Random(4217)
        for _ in range(42):
            gx = int(ix + grime_rng.randint(0, iw - 1))
            gy = int(iy + grime_rng.randint(0, ih - 1))
            gw = grime_rng.randint(8, 28)
            gh = grime_rng.randint(3, 12)
            a = grime_rng.randint(10, 28)
            pygame.draw.ellipse(screen, (8, 9, 9, a), (gx - gw // 2, gy - gh // 2, gw, gh))

        # Low wall/backsplash band on the north edge.
        wall_band = pygame.Rect(int(ix), int(iy - 20), iw, 24)
        pygame.draw.rect(screen, (30, 36, 36), wall_band)
        pygame.draw.line(screen, (62, 70, 68), (wall_band.x, wall_band.bottom - 2), (wall_band.right, wall_band.bottom - 2), 2)
        for tx in range(wall_band.x, wall_band.right, 24):
            pygame.draw.line(screen, (22, 26, 26), (tx, wall_band.y), (tx, wall_band.bottom), 1)

        # Door threshold / scuffed traffic path toward corridor.
        door_x = 6 * TILE_SIZE - cam_x
        door_y = 22 * TILE_SIZE - cam_y
        pygame.draw.rect(screen, (35, 38, 39), (door_x - 6, door_y + 4, 12, TILE_SIZE - 8))
        pygame.draw.line(screen, (82, 80, 70), (door_x - 6, door_y + 10), (door_x - 6, door_y + TILE_SIZE - 10), 1)
        path = pygame.Surface((84, 54), pygame.SRCALPHA)
        render_util.soft_shadow(path, (0, 8, 84, 28), 42)
        screen.blit(path, (int(door_x - 72), int(door_y + 15)))

        # Vent hatch where Biribel emerges. Keep it under the player sprite.
        vent_x = int((_VENT_EXIT_COL + 0.5) * TILE_SIZE - cam_x)
        vent_y = int((_VENT_EXIT_ROW + 0.5) * TILE_SIZE - cam_y)
        render_util.soft_shadow(screen, (vent_x - 22, vent_y + 10, 44, 14), 70)
        vent = pygame.Rect(vent_x - 15, vent_y - 9, 30, 18)
        pygame.draw.rect(screen, (18, 20, 22), vent, border_radius=3)
        pygame.draw.rect(screen, (82, 88, 88), vent, 2, border_radius=3)
        for off in (-8, -3, 2, 7):
            pygame.draw.line(screen, (56, 62, 62), (vent.x + 4, vent.centery + off), (vent.right - 4, vent.centery + off), 1)

        # ── Fridge (tile 3,21): grim stainless locker, not a toy block. ──
        fridge_x = int((3 + 0.5) * TILE_SIZE) - cam_x
        fridge_y = int((21 + 0.5) * TILE_SIZE) - cam_y
        render_util.soft_shadow(screen, (fridge_x - 17, fridge_y + 10, 34, 12), 75)
        fridge = pygame.Rect(fridge_x - 13, fridge_y - 18, 26, 36)
        pygame.draw.rect(screen, (92, 100, 102), fridge, border_radius=3)
        pygame.draw.rect(screen, (155, 164, 164), fridge, 1, border_radius=3)
        pygame.draw.line(screen, (60, 66, 68), (fridge.centerx, fridge.y + 2), (fridge.centerx, fridge.bottom - 2), 1)
        pygame.draw.line(screen, (188, 196, 194), (fridge.x + 4, fridge.y + 3), (fridge.right - 4, fridge.y + 3), 1)
        for hx in (fridge.x + 5, fridge.centerx + 5):
            pygame.draw.rect(screen, (54, 58, 60), (hx, fridge.y + 10, 3, 10), border_radius=1)
        # Warning sticker / grime.
        pygame.draw.rect(screen, (145, 124, 48), (fridge.x + 4, fridge.bottom - 10, 7, 4))
        pygame.draw.line(screen, (58, 62, 63), (fridge.x + 3, fridge.y + 17), (fridge.right - 4, fridge.y + 20), 1)

        # ── Stove (tile 5,21): industrial cooktop with hood shadow. ──
        stove_x = int((5 + 0.5) * TILE_SIZE) - cam_x
        stove_y = int((21 + 0.5) * TILE_SIZE) - cam_y
        render_util.soft_shadow(screen, (stove_x - 20, stove_y + 10, 40, 13), 80)
        hood = pygame.Rect(stove_x - 18, stove_y - 24, 36, 8)
        pygame.draw.rect(screen, (42, 46, 48), hood, border_radius=2)
        pygame.draw.line(screen, (82, 86, 86), (hood.x + 3, hood.y + 2), (hood.right - 3, hood.y + 2), 1)
        stove = pygame.Rect(stove_x - 16, stove_y - 15, 32, 30)
        pygame.draw.rect(screen, (42, 44, 48), stove, border_radius=3)
        pygame.draw.rect(screen, (82, 84, 88), stove, 1, border_radius=3)
        pygame.draw.rect(screen, (28, 30, 34), (stove.x + 3, stove.bottom - 9, stove.w - 6, 6), border_radius=1)
        for bx, by in [(-7, -6), (7, -6), (-7, 6), (7, 6)]:
            pygame.draw.circle(screen, (20, 21, 23), (stove_x + bx, stove_y + by), 5)
            pygame.draw.circle(screen, (72, 72, 74), (stove_x + bx, stove_y + by), 5, 1)
            pygame.draw.circle(screen, (8, 8, 9), (stove_x + bx, stove_y + by), 2)
        # Small cold pilot light.
        pygame.draw.circle(screen, (60, 120, 120), (stove.right - 5, stove.y + 5), 2)

        # ── South prep counter / sink. ──
        counter_x = int((4 + 0.5) * TILE_SIZE) - cam_x
        counter_y = int((23 + 0.5) * TILE_SIZE) - cam_y
        render_util.soft_shadow(screen, (counter_x - 40, counter_y + 6, 80, 16), 78)
        counter = pygame.Rect(counter_x - 36, counter_y - 11, 72, 22)
        pygame.draw.rect(screen, (78, 76, 66), counter, border_radius=3)
        pygame.draw.rect(screen, (122, 118, 102), counter, 1, border_radius=3)
        pygame.draw.line(screen, (142, 136, 118), (counter.x + 4, counter.y + 3), (counter.right - 4, counter.y + 3), 1)
        basin = pygame.Rect(counter.centerx - 11, counter.centery - 5, 22, 10)
        pygame.draw.ellipse(screen, (52, 58, 62), basin)
        pygame.draw.ellipse(screen, (28, 32, 34), basin.inflate(-5, -3))
        pygame.draw.line(screen, (134, 138, 136), (counter.centerx + 3, counter.y + 1), (counter.centerx + 3, counter.y - 8), 2)
        pygame.draw.line(screen, (134, 138, 136), (counter.centerx + 3, counter.y - 8), (counter.centerx + 10, counter.y - 8), 2)
        # Knife/tray clutter, small enough not to imply pickup.
        pygame.draw.rect(screen, (48, 50, 48), (counter.x + 7, counter.y + 7, 14, 6), border_radius=1)
        pygame.draw.line(screen, (155, 160, 158), (counter.right - 19, counter.y + 8), (counter.right - 7, counter.y + 4), 2)
        pygame.draw.line(screen, (70, 48, 30), (counter.right - 8, counter.y + 4), (counter.right - 3, counter.y + 2), 2)

        # Shelf + hanging utensils on the west/top wall.
        shelf_y = int(21 * TILE_SIZE - cam_y - 9)
        shelf_x = int(3 * TILE_SIZE - cam_x + 10)
        pygame.draw.rect(screen, (54, 48, 42), (shelf_x, shelf_y, 112, 5), border_radius=1)
        pygame.draw.line(screen, (102, 90, 76), (shelf_x, shelf_y), (shelf_x + 112, shelf_y), 1)
        for i, px in enumerate((shelf_x + 16, shelf_x + 38, shelf_x + 72, shelf_x + 95)):
            pygame.draw.line(screen, (70, 70, 66), (px, shelf_y + 5), (px, shelf_y + 18 + (i % 2) * 3), 1)
            if i == 0:
                pygame.draw.circle(screen, (92, 88, 78), (px, shelf_y + 22), 5, 1)
            elif i == 1:
                pygame.draw.rect(screen, (90, 86, 76), (px - 4, shelf_y + 18, 8, 8), 1)
            else:
                pygame.draw.line(screen, (130, 130, 120), (px - 5, shelf_y + 20), (px + 5, shelf_y + 16), 2)

        # Floor drain / wet patch away from the vent, to ground the room.
        drain_x = int(3.35 * TILE_SIZE - cam_x)
        drain_y = int(23.25 * TILE_SIZE - cam_y)
        wet = pygame.Surface((54, 34), pygame.SRCALPHA)
        pygame.draw.ellipse(wet, (8, 12, 13, 55), wet.get_rect())
        pygame.draw.ellipse(wet, (18, 26, 28, 55), (8, 7, 38, 18))
        screen.blit(wet, (drain_x - 27, drain_y - 17))
        pygame.draw.circle(screen, (20, 22, 23), (drain_x, drain_y), 7)
        pygame.draw.circle(screen, (66, 70, 68), (drain_x, drain_y), 7, 1)
        for a in (0, math.pi / 3, 2 * math.pi / 3):
            pygame.draw.line(screen, (42, 44, 44),
                             (drain_x + math.cos(a) * 2, drain_y + math.sin(a) * 2),
                             (drain_x + math.cos(a) * 6, drain_y + math.sin(a) * 6), 1)

        # Final subtle room outline so the tiny utility room reads intentionally.
        pygame.draw.rect(screen, (0, 0, 0, 70), (room_x, room_y, room_w, room_h), 2)
    finally:
        screen.set_clip(old_clip)


def _draw_cell_room(cam_x, cam_y):
    """Render the cell's persistent room elements: atmosphere (red wash +
    fluorescent tube), cell details (floor drain, furniture, wall scratches),
    wall monitor, the cell door (closed/swinging/open depending on breach
    state), Volkov in the doorway (if the breach has fired), and the breach
    flash.

    Called in EVERY stage so the player sees the cell they just escaped,
    the dead monitor still on the wall, the kicked-in door, and Volkov
    standing in the doorway. The dialogue panel is rendered separately,
    only during STAGE_INTERROGATION (see game_draw).
    """
    # 1. Atmospheric layers (wash + fluorescent light) under everything.
    _draw_cell_atmosphere(cam_x, cam_y)

    # 2. Cell details: floor drain, stains, furniture (chair, cot, sink),
    # wall tally marks, conduit. Drawn BEFORE the monitor so the monitor's
    # glow sits on top of the furniture.
    # RPE6 Phase 3: baked world layer (game.art.m3.cell_details; variant 1 =
    # broken chair); the painter stays as the live fallback, the LED blinks live.
    _chair = 1 if getattr(STATE, "mission3_chair_broken", False) else 0
    if not _m3art.blit_layer(screen, "cell_details", cam_x, cam_y, _chair):
        _draw_cell_details(cam_x, cam_y, chair_broken=bool(_chair), live=False)
    _draw_cell_details_live(cam_x, cam_y)

    # Kitchen details (fridge, stove, counters): baked world layer (game.art.m3.kitchen),
    # the painter stays as the live fallback.
    if not _m3art.blit_layer(screen, "kitchen", cam_x, cam_y):
        _draw_kitchen_details(cam_x, cam_y)

    # 3. Wall monitor on the cell's north wall (its glow sits on top of details).
    _draw_wall_monitor(cam_x, cam_y)

    # 3.5 Boots-approach shadow: while the pre-breach establishing beat is
    # active, draw a faint dark sliver sweeping under the cell door. This is
    # the visible cue that someone is walking past in the corridor outside
    # BEFORE the breach fires - answering "where did he come from?" before
    # the C4 even appears. Suppressed once the breach action fires.
    if _m3_flow._boots_approach_t >= 0 and _m3_flow._volkov_breach_t < 0:
        _draw_boots_approach_shadow(cam_x, cam_y)

    # 4. Cell door on the south wall. Drawn BEFORE Volkov so Volkov (who
    # steps through the doorway) appears in front of the open door panel.
    _draw_cell_door(cam_x, cam_y)

    # 5. Volkov in the doorway (only once the breach has been triggered).
    if _m3_flow._volkov_breach_t >= 0:
        _draw_volkov_breach(cam_x, cam_y)

    # 6. Breach flash: a decaying white overlay (max ~28 frames).
    if _m3_flow._breach_flash > 0:
        alpha = int(255 * (_m3_flow._breach_flash / 28.0))
        flash = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        flash.fill((255, 255, 255, alpha))
        screen.blit(flash, (0, 0))
        # Second layer: orange flash on the door (explosion fireball).
        if _m3_flow._breach_flash > 18:
            fire_alpha = int(180 * ((_m3_flow._breach_flash - 18) / 10.0))
            door_x = _DOOR_TILE_COL * TILE_SIZE - cam_x
            door_y = _DOOR_TILE_ROW * TILE_SIZE - cam_y
            fire = pygame.Surface((TILE_SIZE, TILE_SIZE), pygame.SRCALPHA)
            pygame.draw.circle(fire, (255 * fire_alpha // 255, 140 * fire_alpha // 255,
                                        40 * fire_alpha // 255, fire_alpha),
                               (TILE_SIZE // 2, TILE_SIZE // 2), TILE_SIZE // 2)
            screen.blit(fire, (door_x, door_y), special_flags=pygame.BLEND_ADD)


# Door tile (col 9, row 13) is where the cell's south-wall door sits.
# Computed from the map authoring: outline at (4,4) w=12 h=10 with a door
# gap at tile offset (5,9) -> (4+5, 4+9) = (9, 13).
_DOOR_TILE_COL, _DOOR_TILE_ROW = 33, 12   # south wall of Biribel's cell


def _draw_boots_approach_shadow(cam_x, cam_y):
    """Draw a faint shadow sweeping under the cell door during the
    boots-approach establishing beat.

    The shadow is a soft dark sliver that appears at the bottom edge of the
    closed cell door - light from the corridor leaking under the door, then
    partially blocked by someone walking past. It sweeps horizontally back
    and forth (south-to-north light block) to read as "footsteps in the
    corridor" rather than a static stain.

    Driven by _m3_flow._boots_approach_t (frames since the boots_approach action fired).
    The shadow is intentionally subtle (low alpha) so the player registers
    it peripherally - "did something just move?" - rather than as a bright
    UI element demanding attention.
    """
    t = _m3_flow._boots_approach_t
    if t < 0:
        return

    # Door position in screen space.
    door_x = _DOOR_TILE_COL * TILE_SIZE - cam_x
    door_y = _DOOR_TILE_ROW * TILE_SIZE - cam_y
    door_w = TILE_SIZE * 2  # the cell door is a 2-tile gap

    # Sweep: shadow x-offset oscillates across the door width over ~3s
    # (180 frames). Two full passes during the beat's hold, which matches
    # the three spaced footstep SFX (frames 0, 45, 90).
    sweep_period = 180
    phase = (t % sweep_period) / sweep_period  # 0..1
    # Ease in/out so the shadow slows at the edges (matches a walker
    # reaching the door's far jamb, then turning back).
    eased = 0.5 - 0.5 * math.cos(phase * math.pi * 2)
    shadow_cx = door_x + int(door_w * eased)

    # Shadow shape: a short horizontal sliver at the very bottom of the
    # door gap, wider than tall (reads as feet blocking light from a
    # side-on angle).
    shadow_w = 28
    shadow_h = 6
    shadow_surf = pygame.Surface((shadow_w, shadow_h), pygame.SRCALPHA)
    # Pulse the alpha slightly so the shadow "breathes" - adds motion
    # even when the sweep is at its slow eased edges.
    pulse = 0.85 + 0.15 * math.sin(t * 0.4)
    alpha = int(90 * pulse)
    render_util.soft_shadow(shadow_surf, (0, 0, shadow_w, shadow_h), alpha)
    # Soft edge: blit a slightly larger, dimmer ellipse under the main one.
    soft = pygame.Surface((shadow_w + 8, shadow_h + 4), pygame.SRCALPHA)
    render_util.soft_shadow(soft, (0, 0, shadow_w + 8, shadow_h + 4), max(0, alpha // 3))
    screen.blit(soft, (shadow_cx - (shadow_w + 8) // 2,
                       door_y + TILE_SIZE - 4))
    screen.blit(shadow_surf, (shadow_cx - shadow_w // 2,
                              door_y + TILE_SIZE - 3))


def _draw_cell_door(cam_x, cam_y):
    """Draw the cell door on the south wall, top-down.

    The door is a reinforced metal panel. Before the breach it sits intact
    in the frame. After detonation, the C4 tears a jagged blast hole
    through the center - but the door stays IN the doorway (it doesn't
    fly across the room). Scorch marks and cracks radiate from the hole.

    States (driven by _m3_flow._volkov_breach_t):
      t < 0           (pre-breach):    Door fills the doorway intact.
      0 <= t < 301    (charge planted): Door still intact; C4 visible on
                                       the surface (drawn by _draw_volkov_breach).
      t >= 301        (post-blast):    Door panel still in place but with
                                       a jagged blast hole, scorch marks,
                                       and cracks radiating from the hole.
    """
    t = _m3_flow._volkov_breach_t

    door_x = _DOOR_TILE_COL * TILE_SIZE - cam_x
    door_y = _DOOR_TILE_ROW * TILE_SIZE - cam_y
    door_w = TILE_SIZE * 2
    door_h = TILE_SIZE
    doorway_cy = door_y + door_h // 2

    # RPE6 Phase 3: once the blast damage has settled (dt >= 20) the door is a fixed composite ->
    # baked sprite game.art.m3.cell_door_blown (138 x 68 at door_x - 4, door_y - 2). Everything
    # below stays the live path (pre-breach, swing, the 20-frame blast animation, odd tile states).
    if t >= 301 + _CELL_DOOR_SETTLED_DT:
        variant = _cell_door_settled_variant()
        if variant is not None:
            spr = _m3art.get("cell_door_blown", variant)
            if spr is not None:
                screen.blit(spr, (door_x - 4, door_y - 2))
                return

    _paint_cell_door_jambs(screen, door_x, doorway_cy)

    # ── Scorch marks around the frame (post-breach) ──
    if t >= 0:
        scorch = pygame.Surface((door_w + 16, door_h + 16), pygame.SRCALPHA)
        for i in range(8):
            r = 12 + t // 4
            a = max(0, 60 - t // 2)
            pygame.draw.circle(scorch, (20, 15, 10, a),
                               (r + i * 4, r + i * 3), r)
        screen.blit(scorch, (door_x - 8, door_y - 8))

    # ── Pre-detonation / pre-breach: door sits intact in the frame. ──
    if t < 0:
        _draw_m3_door_tile(screen, door_x, door_y, _DOOR_TILE_COL, _DOOR_TILE_ROW)
        _draw_m3_door_tile(screen, door_x + TILE_SIZE, door_y, _DOOR_TILE_COL + 1, _DOOR_TILE_ROW)
        pygame.draw.line(screen, (18, 20, 24), (door_x + TILE_SIZE, door_y + 6), (door_x + TILE_SIZE, door_y + TILE_SIZE - 6), 3)
        return

    # ── Charge planted: door still closed while Volkov backs away. ──
    # During frames 0-300, the door is INTACT (closed panel). The C4 charge
    # is drawn on top by _draw_volkov_breach. The door does NOT show as
    # open/openable during this phase - it's a solid closed door with a
    # bomb on it.
    if 0 <= t < 301:
        _draw_m3_door_tile(screen, door_x, door_y, _DOOR_TILE_COL, _DOOR_TILE_ROW)
        _draw_m3_door_tile(screen, door_x + TILE_SIZE, door_y, _DOOR_TILE_COL + 1, _DOOR_TILE_ROW)
        pygame.draw.line(screen, (18, 20, 24), (door_x + TILE_SIZE, door_y + 6), (door_x + TILE_SIZE, door_y + TILE_SIZE - 6), 3)
        return

    # ── Post-detonation (t >= 301): the door is BLOWN but still IN the
    # doorway. We draw the intact door panel (same ribs, same colors, same
    # proportions as _draw_m3_door_tile) and add visible blast damage on
    # top: scorch marks, a jagged blast hole in the center (so the player
    # can see the doorway is passable), and cracks radiating from the
    # hole. This keeps the door reading as the SAME object pre- and
    # post-breach - not a flat grey box. ──

    # 1. Draw the intact door panel (closed state). Temporarily fake
    #    _m3_flow._volkov_breach_t to -1 so _draw_m3_door_tile renders the closed
    #    panel (not the open doorway).
    saved_breach_t = _m3_flow._volkov_breach_t
    _m3_flow._volkov_breach_t = -1
    _draw_m3_door_tile(screen, door_x, door_y, _DOOR_TILE_COL, _DOOR_TILE_ROW)
    _draw_m3_door_tile(screen, door_x + TILE_SIZE, door_y, _DOOR_TILE_COL + 1, _DOOR_TILE_ROW)
    pygame.draw.line(screen, (18, 20, 24),
                     (door_x + TILE_SIZE, door_y + 6),
                     (door_x + TILE_SIZE, door_y + TILE_SIZE - 6), 3)
    _m3_flow._volkov_breach_t = saved_breach_t

    # 2. Blast hole in the center of the door (where the C4 was). An
    #    irregular dark shape showing the door has been torn open. The
    #    hole grows over ~12 frames from the detonation point.
    _paint_cell_door_blast_damage(screen, door_x, door_y, t - 301)


_CELL_DOOR_SETTLED_DT = 20   # frames after detonation until hole, scorch and cracks are final


def _paint_cell_door_jambs(surface, door_x, doorway_cy):
    """Door jamb (frame posts on either side of the 2-tile cell door)."""
    door_w = TILE_SIZE * 2
    jamb_col = (50, 48, 44)
    jamb_dark = (32, 30, 28)
    pygame.draw.rect(surface, jamb_col,
                     (door_x - 4, doorway_cy - 8, 5, 16))
    pygame.draw.rect(surface, jamb_dark,
                     (door_x - 4, doorway_cy - 8, 5, 16), 1)
    pygame.draw.rect(surface, jamb_col,
                     (door_x + door_w, doorway_cy - 8, 5, 16))
    pygame.draw.rect(surface, jamb_dark,
                     (door_x + door_w, doorway_cy - 8, 5, 16), 1)


def _cell_door_settled_variant():
    """Sprite variant of the settled post-blast door from the two tiles' rest state
    (0 = tiles read as open, 1 = closed + locked), or None when a tile is mid-swing / damaged."""
    saved = _m3_flow._volkov_breach_t
    _m3_flow._volkov_breach_t = -1
    try:
        states = [_m3_door_tile_state(_DOOR_TILE_COL + i, _DOOR_TILE_ROW) for i in (0, 1)]
    finally:
        _m3_flow._volkov_breach_t = saved
    if any(st[4] for st in states):
        return None
    if all(st[2] >= 0.95 for st in states):
        return 0
    if all(st[2] <= 0.0 and st[1] for st in states):
        return 1
    return None


def _paint_cell_door_blown(surface, door_x, door_y, open_tiles=True):
    """Settled post-blast cell door at door_x/door_y (bake source of game.art.m3.cell_door_blown)."""
    _paint_cell_door_jambs(surface, door_x, door_y + TILE_SIZE // 2)
    locked, open_p = (False, 1.0) if open_tiles else (True, 0.0)
    for i in (0, 1):
        _paint_m3_door_tile(surface, door_x + i * TILE_SIZE, door_y, _DOOR_TILE_COL + i, _DOOR_TILE_ROW,
                            None, locked, open_p, False, 0)
    pygame.draw.line(surface, (18, 20, 24),
                     (door_x + TILE_SIZE, door_y + 6),
                     (door_x + TILE_SIZE, door_y + TILE_SIZE - 6), 3)
    _paint_cell_door_blast_damage(surface, door_x, door_y, _CELL_DOOR_SETTLED_DT)


def _paint_cell_door_blast_damage(surface, door_x, door_y, dt):
    """Blast hole, scorch, cracks and the hinge stub over an already drawn cell door; dt = frames
    since detonation (the animation is final from _CELL_DOOR_SETTLED_DT on)."""
    door_w = TILE_SIZE * 2
    door_h = TILE_SIZE
    doorway_cy = door_y + door_h // 2
    if dt > 0:
        hole_p = min(1.0, dt / 12.0)
        hole_cx = door_x + door_w // 2
        hole_cy = door_y + door_h // 2
        hole_rx = int(TILE_SIZE * 0.45 * hole_p)
        hole_ry = int(TILE_SIZE * 0.35 * hole_p)
        if hole_rx > 2 and hole_ry > 2:
            # Jagged blast hole: draw several overlapping dark ellipses
            # with slightly offset centers to create an irregular edge.
            for i, (ox, oy, scale) in enumerate([
                (0, 0, 1.0), (-3, 2, 0.8), (4, -1, 0.7), (-1, 4, 0.6)
            ]):
                rx = max(1, int(hole_rx * scale))
                ry = max(1, int(hole_ry * scale))
                pygame.draw.ellipse(surface, (6, 5, 4),
                                    (hole_cx + ox - rx, hole_cy + oy - ry,
                                     rx * 2, ry * 2))
            # Orange-hot edge around the hole (fades over ~20 frames).
            if dt < 20:
                edge_alpha = int(180 * (1.0 - dt / 20.0))
                edge_surf = pygame.Surface((hole_rx * 3, hole_ry * 3),
                                           pygame.SRCALPHA)
                pygame.draw.ellipse(edge_surf, (255, 120, 30, edge_alpha),
                                    (0, 0, hole_rx * 3, hole_ry * 3), 3)
                surface.blit(edge_surf,
                            (hole_cx - hole_rx * 3 // 2,
                             hole_cy - hole_ry * 3 // 2))

    # 3. Scorch marks on the door panel (dark overlay radiating from the
    #    blast hole). Drawn as several dark semi-transparent circles.
    scorch_surf = pygame.Surface((door_w, door_h), pygame.SRCALPHA)
    scorch_intensity = min(1.0, dt / 10.0) if dt > 0 else 0.0
    if scorch_intensity > 0:
        for i in range(6):
            r = int(8 + i * 4)
            a = int(100 * scorch_intensity * (1.0 - i * 0.15))
            if a > 0:
                pygame.draw.circle(scorch_surf, (15, 10, 8, a),
                                   (door_w // 2, door_h // 2), r)
        surface.blit(scorch_surf, (door_x, door_y))

    # 4. Cracks radiating from the blast hole - thin dark lines going
    #    outward from the hole edges to the door frame.
    if dt > 6:
        crack_alpha = min(255, int(255 * (dt - 6) / 10.0))
        crack_surf = pygame.Surface((door_w, door_h), pygame.SRCALPHA)
        hole_cx_local = door_w // 2
        hole_cy_local = door_h // 2
        for angle_deg in (30, 75, 120, 165, 210, 255, 300, 345):
            a = math.radians(angle_deg)
            r1 = int(TILE_SIZE * 0.4)
            r2 = int(TILE_SIZE * 0.8)
            x1 = hole_cx_local + math.cos(a) * r1
            y1 = hole_cy_local + math.sin(a) * r1
            x2 = hole_cx_local + math.cos(a) * r2
            y2 = hole_cy_local + math.sin(a) * r2
            pygame.draw.line(crack_surf, (10, 8, 6, crack_alpha),
                             (x1, y1), (x2, y2), 1)
        surface.blit(crack_surf, (door_x, door_y))

    # 5. Torn hinge on the left jamb (broken bolt visible).
    pygame.draw.circle(surface, (30, 28, 26),
                       (door_x + 1, doorway_cy), 3)
    pygame.draw.line(surface, (60, 56, 52),
                     (door_x - 2, doorway_cy - 2),
                     (door_x + 4, doorway_cy + 2), 2)


def _draw_volkov_breach(cam_x, cam_y):
    """Draw Volkov during the breach, then during his escape run.

    After the cell door detonates and the interrogation hands off to
    STAGE_BREAKOUT, Volkov sprints east toward the service-exit side to draw
    attention instead of standing forever in the doorway.
    """
    t = _m3_flow._volkov_breach_t
    if t < 0:
        return

    door_x = _DOOR_TILE_COL * TILE_SIZE - cam_x
    door_y = _DOOR_TILE_ROW * TILE_SIZE - cam_y
    door_w = TILE_SIZE * 2

    pose = _volkov_world_pose()
    if pose is None:
        return

    world_x, world_y, facing_angle, running = pose
    draw_x = world_x - cam_x
    draw_y = world_y - cam_y

    # Charge position on the door.
    charge_cx = door_x + door_w // 2 - 4
    charge_cy = door_y - 2

    # Planting arm phase only during the breach choreography, not while running.
    charge_plant_phase = 0
    if not running:
        if 91 <= t <= 140:
            charge_plant_phase = 1
        elif 141 <= t <= 210:
            charge_plant_phase = 2
        elif 211 <= t <= 250:
            charge_plant_phase = 3

    # Running dust / motion accents.
    if running:
        # Dust behind his feet.
        if getattr(STATE, "m3_volkov_run_timer", 0) % 6 == 0:
            for _ in range(2):
                STATE.particles.append(Particle(
                    world_x + _rng_legacy.randint(-6, 6),
                    world_y + _rng_legacy.randint(4, 14),
                    _rng_legacy.choice([(85, 78, 66), (55, 50, 45), (110, 95, 75)])
                ))

        # Screen-space afterimage trail opposite the movement direction.
        trail = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        for i in range(3):
            back = (i + 1) * 10
            tx = draw_x - math.cos(facing_angle) * back
            ty = draw_y - math.sin(facing_angle) * back
            alpha = 42 - i * 12
            pygame.draw.ellipse(trail, (255, 110, 40, alpha), (tx - 11, ty - 18, 22, 34))
        screen.blit(trail, (0, 0))

    # Draw Volkov. During his eastbound escape, fade him out as he clears the
    # service-exit side so he doesn't linger awkwardly at the edge of the map.
    alpha = 255
    if getattr(STATE, "m3_volkov_run_active", False):
        run_t = getattr(STATE, "m3_volkov_run_timer", 0)
        if run_t > 150:
            alpha = max(0, min(255, int(255 * (1.0 - (run_t - 150) / 90.0))))
    if alpha >= 255:
        _draw_volkov_in_game(
            screen,
            draw_x,
            draw_y,
            facing_angle,
            kick_phase=0,
            charge_plant=charge_plant_phase,
        )
    elif alpha > 0:
        volkov_surf = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        _draw_volkov_in_game(
            volkov_surf,
            draw_x,
            draw_y,
            facing_angle,
            kick_phase=0,
            charge_plant=charge_plant_phase,
        )
        volkov_surf.set_alpha(alpha)
        screen.blit(volkov_surf, (0, 0))

    # Door charge, visible after Volkov places it and before detonation.
    if 150 <= t <= 300:
        pygame.draw.rect(screen, (90, 75, 60),
                         (charge_cx, charge_cy, 8, 6), border_radius=1)
        pygame.draw.rect(screen, (60, 50, 40),
                         (charge_cx, charge_cy, 8, 6), 1, border_radius=1)

        pygame.draw.circle(screen, (40, 40, 45),
                           (charge_cx + 4, charge_cy - 2), 2)

        pygame.draw.line(screen, (120, 50, 30),
                         (charge_cx + 4, charge_cy - 2),
                         (charge_cx + 2, charge_cy - 8), 1)

        blink_interval_ms = max(80, 300 - max(0, t - 150) * 2)
        led_on = (_now_ms() // blink_interval_ms) % 2 == 0
        pygame.draw.circle(screen, (255 if led_on else 60, 0, 0),
                           (charge_cx + 6, charge_cy), 1)

    elif 300 < t <= 306:
        pygame.draw.circle(screen, (255, 160, 40, 180),
                           (charge_cx + 4, charge_cy + 3), 14)
        pygame.draw.circle(screen, (255, 200, 100, 120),
                           (charge_cx + 4, charge_cy + 3), 20)


# Volkov's palette -- mirrors his cutscene sprite (cutscenes.draw_volkov)
# exactly, so the in-game top-down sprite reads as the same character the
# player saw in the intro cutscene. The M2 squadmate top-down STRUCTURE is
# used (legs, shadow, layered head, name label) but every COLOR is
# Volkov's, not the KRAP squad's.
_C_VOLKOV_COAT = (14, 14, 20)        # near-black coat (cutscene coat_col)
_C_VOLKOV_COAT_OPEN = (30, 28, 32)   # center opening line (cutscene)
_C_VOLKOV_LEG = (18, 18, 24)         # dark navy legs (cutscene leg_col)
_C_VOLKOV_BOOT = (12, 10, 10)        # near-black shoes (cutscene shoe_col)
_C_VOLKOV_RIM = (255, 110, 40)       # orange rim light (cutscene rim_col)
_C_VOLKOV_RIM_DIM = (102, 44, 16)    # rim at 0.4 intensity (cutscene halo)
_C_VOLKOV_HEAD_RIM = (153, 33, 4)    # head rim (rim_col at 0.6/0.3/0.1)
_C_VOLKOV_SKIN = (42, 36, 32)        # DARK skin (cutscene skin_col)
_C_VOLKOV_HAIR = (8, 6, 6)           # near-black hair arc (cutscene)
_C_VOLKOV_EYE_OUTER = (100, 35, 35)  # dark red eye (cutscene)
_C_VOLKOV_EYE_INNER = (180, 60, 40)  # brighter red pupil (cutscene)
_C_VOLKOV_CIG = (200, 200, 200)      # cigarette paper (cutscene)
_C_VOLKOV_EMBER = (255, 80, 20)      # glowing ember (cutscene)
_C_VOLKOV_NAME = (255, 180, 100)     # amber name label


def _draw_volkov_in_game(surface, draw_x, draw_y, angle, kick_phase=0,
                         charge_plant=0):
    """Draw Volkov top-down, matching the M2 squadmate STRUCTURE but using
    his cutscene sprite's exact colors and features.

    Structure (from mission2._draw_actor -- top-down KRAP squadmate):
      - shadow ellipse at the feet
      - visible legs (boot ellipses + trouser rects)
      - trapezoid torso with outline
      - arms as thick lines from shoulders to hands
      - multi-layer head (outer ring + inner + face dot + eyes)
      - name label above head with drop shadow

    Colors/features (from cutscenes.draw_volkov -- his actual identity):
      - Near-black coat (14,14,20), NOT M2 navy
      - Orange RIM LIGHT HALO behind the torso and head (his signature --
        drawn as dim orange polygons/circles slightly larger than the body,
        BEFORE the body, so it rims his silhouette)
      - Dark skin (42,36,32), NOT light
      - RED eyes (100,35,35 outer, 180,60,40 inner), NOT brown
      - Near-black hair arc on top of head
      - Center coat opening line (vertical, down the middle)
      - NO vest, NO accent stripe, NO headband -- plain dark coat + rim
      - Cigarette + glowing ember at the mouth corner

    kick_phase drives the kick leg overlay:
      0 = idle, 1 = cocked back, 2 = forward/impact, 3 = retracting

    charge_plant drives the planting arm overlay (for the explosive breach):
      0 = idle (normal arms), 1 = arm reaching back (holding charge),
      2 = arm forward (placing charge on door), 3 = arm retracting.

    The `angle` parameter is accepted for call-site compatibility but
    IGNORED -- Volkov always faces north (up on screen) like the M2
    squadmates, which is correct for the breach scene.
    """
    x = int(draw_x)
    y = int(draw_y)

    # ── Shadow (matches M2: 36x14 ellipse, alpha 70, at cy+12) ──
    shad = pygame.Surface((36, 14), pygame.SRCALPHA)
    render_util.soft_shadow(shad, shad.get_rect(), 70)
    surface.blit(shad, (x - 18, y + 12))

    # ── RIM LIGHT HALO behind the torso (Volkov's signature) ──
    # Drawn FIRST, as a dim orange trapezoid slightly wider/taller than the
    # coat, so the coat polygon (drawn next) rims it. Mirrors the cutscene's
    # rim_pts polygon (rim_col * 0.4 = (102, 44, 16)).
    rim_halo_pts = [
        (x - 16, y - 16), (x + 16, y - 16),
        (x + 14, y + 12), (x - 14, y + 12),
    ]
    pygame.draw.polygon(surface, _C_VOLKOV_RIM_DIM, rim_halo_pts)

    # ── Legs (matches M2 upright: boot ellipses + trouser rects) ──
    pygame.draw.ellipse(surface, _C_VOLKOV_BOOT, (x - 13, y + 17, 12, 7))
    pygame.draw.ellipse(surface, _C_VOLKOV_BOOT, (x + 1, y + 17, 12, 7))
    pygame.draw.rect(surface, _C_VOLKOV_LEG,
                     (x - 10, y + 3, 8, 15), border_radius=2)
    pygame.draw.rect(surface, _C_VOLKOV_LEG,
                     (x + 2, y + 3, 8, 15), border_radius=2)

    # ── Kick leg overlay (optional, only during breach) ──
    if kick_phase > 0:
        if kick_phase == 1:
            end_x, end_y = x, y + 26       # cocked back (south, into corridor)
        elif kick_phase == 2:
            end_x, end_y = x, y - 26       # forward (north, into door)
        else:
            end_x, end_y = x, y - 12       # retracting
        pygame.draw.line(surface, _C_VOLKOV_LEG,
                         (x, y), (end_x, end_y), 5)
        pygame.draw.ellipse(surface, _C_VOLKOV_BOOT,
                            (end_x - 6, end_y - 3, 12, 7))

    # ── Torso (trapezoid, near-black coat + center opening line) ──
    torso_pts = [
        (x - 13, y - 14), (x + 13, y - 14),
        (x + 11, y + 10), (x - 11, y + 10),
    ]
    pygame.draw.polygon(surface, _C_VOLKOV_COAT, torso_pts)
    # Center coat opening line (cutscene signature -- the coat's lapels).
    pygame.draw.line(surface, _C_VOLKOV_COAT_OPEN,
                     (x, y - 14), (x, y + 8), 2)

    # ── Arms (thick lines from shoulders to hands, empty hands) ──
    lh = (x - 14, y + 6)
    rh = (x + 14, y + 6)
    # If charge_plant is active, override the right arm (reaches forward).
    if charge_plant > 0:
        if charge_plant == 1:
            # Arm reaching back (holding the charge).
            plant_end = (x + 20, y + 2)
        elif charge_plant == 2:
            # Arm forward, placing charge on the door.
            plant_end = (x + 16, y - 14)
        else:
            # Arm retracting.
            plant_end = (x + 10, y - 6)
        # Hide right arm, draw planting arm instead.
        pygame.draw.line(surface, _C_VOLKOV_COAT,
                         (x - 11, y - 4), lh, 5)
        pygame.draw.line(surface, _C_VOLKOV_COAT,
                         (x + 9, y - 6), plant_end, 5)
        pygame.draw.circle(surface, _C_VOLKOV_SKIN, lh, 3)
        pygame.draw.circle(surface, _C_VOLKOV_SKIN, plant_end, 3)
        # Small grey rectangle at the hand (the charge).
        if charge_plant == 2:
            charge_rect = pygame.Rect(plant_end[0] - 3, plant_end[1] - 2, 6, 4)
            pygame.draw.rect(surface, (90, 75, 60), charge_rect, border_radius=1)
            pygame.draw.rect(surface, (60, 50, 40), charge_rect, 1, border_radius=1)
    else:
        # Combat/ally pose: Volkov holds a compact rifle/SMG in the same
        # top-down language as the player/enemies. Earlier versions left his
        # hands empty, so support fire felt disconnected from the sprite.
        gun_dx = math.cos(angle)
        gun_dy = math.sin(angle)
        gun_px = -gun_dy
        gun_py = gun_dx
        # Lift the whole weapon rig to chest/shoulder height. Previously the
        # gun was anchored at Volkov's sprite center, which made it look like it
        # was coming out of his belt/groin.
        gun_anchor_x = x
        gun_anchor_y = y - 7
        shoulder_l = (x + gun_px * 9 - gun_dx * 1, gun_anchor_y + gun_py * 9 - gun_dy * 1)
        shoulder_r = (x - gun_px * 9 - gun_dx * 1, gun_anchor_y - gun_py * 9 - gun_dy * 1)
        hand_l = (gun_anchor_x + gun_dx * 17 + gun_px * 4, gun_anchor_y + gun_dy * 17 + gun_py * 4)
        hand_r = (gun_anchor_x + gun_dx * 20 - gun_px * 4, gun_anchor_y + gun_dy * 20 - gun_py * 4)
        pygame.draw.line(surface, _C_VOLKOV_COAT, shoulder_l, hand_l, 5)
        pygame.draw.line(surface, _C_VOLKOV_COAT, shoulder_r, hand_r, 5)
        pygame.draw.circle(surface, _C_VOLKOV_SKIN, (int(hand_l[0]), int(hand_l[1])), 3)
        pygame.draw.circle(surface, _C_VOLKOV_SKIN, (int(hand_r[0]), int(hand_r[1])), 3)
        # Weapon body: dark receiver, short barrel, tiny stock.
        grip_x = gun_anchor_x + gun_dx * 19
        grip_y = gun_anchor_y + gun_dy * 19
        start_x = grip_x - gun_dx * 8
        start_y = grip_y - gun_dy * 8
        end_x = grip_x + gun_dx * 22
        end_y = grip_y + gun_dy * 22
        pygame.draw.line(surface, (8, 9, 10), (start_x, start_y), (end_x, end_y), 7)
        pygame.draw.line(surface, (36, 38, 38), (start_x, start_y), (end_x, end_y), 5)
        pygame.draw.line(surface, (92, 96, 90),
                         (start_x - gun_px * 1.8, start_y - gun_py * 1.8),
                         (end_x - gun_px * 1.8, end_y - gun_py * 1.8), 1)
        muzzle_x = end_x + gun_dx * 6
        muzzle_y = end_y + gun_dy * 6
        pygame.draw.line(surface, (18, 20, 20), (end_x, end_y), (muzzle_x, muzzle_y), 4)
        pygame.draw.circle(surface, (5, 5, 6), (int(muzzle_x), int(muzzle_y)), 2)
        # Stick magazine / grip hanging below receiver.
        mag_base = (start_x + gun_dx * 11, start_y + gun_dy * 11)
        pygame.draw.line(surface, (16, 18, 18), mag_base,
                         (mag_base[0] + gun_px * 9 - gun_dx * 1,
                          mag_base[1] + gun_py * 9 - gun_dy * 1), 5)
        # Short collapsed stock.
        stock_root = (start_x - gun_dx * 1, start_y - gun_dy * 1)
        stock_tip = (start_x - gun_dx * 10 + gun_px * 2, start_y - gun_dy * 10 + gun_py * 2)
        pygame.draw.line(surface, (42, 44, 42), stock_root, stock_tip, 2)

    # ── Head rim halo (dim orange circle behind the head) ──
    # Mirrors cutscene: rim_col at (0.6, 0.3, 0.1) = (153, 33, 4), drawn as
    # a circle slightly larger than the head.
    head_y = y - 24
    pygame.draw.circle(surface, _C_VOLKOV_HEAD_RIM,
                       (int(x), int(head_y)), 12)

    # ── Head (dark skin + near-black hair arc on top) ──
    pygame.draw.circle(surface, _C_VOLKOV_SKIN,
                       (int(x), int(head_y)), 10)
    # Hair arc on the top half of the head (cutscene signature).
    pygame.draw.arc(
        surface, _C_VOLKOV_HAIR,
        (int(x - 10), int(head_y - 10), 20, 20),
        0, math.pi, 5,
    )

    # ── Eyes (RED -- dark red outer + brighter red inner, cutscene signature) ──
    # Two eyes, slightly offset left/right of center.
    for ex_off in (-3, 3):
        ex = x + ex_off
        ey = head_y + 1
        pygame.draw.circle(surface, _C_VOLKOV_EYE_OUTER,
                           (int(ex), int(ey)), 2)
        pygame.draw.circle(surface, _C_VOLKOV_EYE_INNER,
                           (int(ex), int(ey)), 1)

    # ── Cigarette + glowing ember at the mouth corner ──
    # Mouth is below the face center; cig sticks out to the right.
    mouth_x = x + 6
    mouth_y = head_y + 5
    cig_end_x = mouth_x + 7
    cig_end_y = mouth_y - 1
    pygame.draw.line(surface, _C_VOLKOV_CIG,
                     (mouth_x, mouth_y), (cig_end_x, cig_end_y), 2)
    # Ember flickers ~3Hz (matches cutscene cadence).
    if int(_now_ms() / 170) % 2 == 0:
        pygame.draw.circle(surface, _C_VOLKOV_EMBER,
                           (int(cig_end_x), int(cig_end_y)), 2)
        # Soft ember glow halo.
        ember_glow = pygame.Surface((12, 12), pygame.SRCALPHA)
        pygame.draw.circle(ember_glow, (60, 24, 7, 60),
                           (6, 6), 6)
        surface.blit(ember_glow,
                     (int(cig_end_x - 6), int(cig_end_y - 6)),
                     special_flags=pygame.BLEND_ADD)

    # ── Name label (M2 style: font_terminal_small, with drop shadow) ──
    name = "VOLKOV"
    lbl = font_terminal_small.render(name, True, _C_VOLKOV_NAME)
    shad_lbl = font_terminal_small.render(name, True, (0, 0, 0))
    label_y = y - 44
    surface.blit(shad_lbl, (x - lbl.get_width() // 2 + 1, label_y + 1))
    surface.blit(lbl, (x - lbl.get_width() // 2, label_y))


# RPE6 Phase 2 (A-003 take registry): the cutscene scene ids this module owns.
# cutscenes.engine.draw_cutscene_scene finds them through core.cutscene_registry
# instead of importing this module by name (boundary rule 4 / W1).
from core.cutscene_registry import register_scene_renderers as _register_takes  # noqa: E402
from engine.text import T as _T  # RPE6 Phase 4 text table

_register_takes({
    "m3_archives_ingame_enter": lambda surface, t, _p="enter": draw_archives_transition_cinematic(surface, t, _p),
    "m3_archives_ingame_join": lambda surface, t, _p="join": draw_archives_transition_cinematic(surface, t, _p),
    "m3_archives_ingame_reveal": lambda surface, t, _p="reveal": draw_archives_transition_cinematic(surface, t, _p),
    "m3_vostral_case_open": lambda surface, t, _p="open": draw_vostral_pickup_cinematic(surface, t, _p),
    "m3_vostral_take": lambda surface, t, _p="take": draw_vostral_pickup_cinematic(surface, t, _p),
    "m3_vostral_confirm": lambda surface, t, _p="confirm": draw_vostral_pickup_cinematic(surface, t, _p),
})
