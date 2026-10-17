
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

from core.config import (C_BLOOD, C_KRAP_BLUE, C_PLAYER_SKIN, C_PLAYER_UNIFORM, C_TERMINAL, Casing, ENEMY_ATTACK_RANGE, ENEMY_DAMAGE, ENEMY_DETECT_RANGE, ENEMY_FIRE_COOLDOWN, HEIGHT, Particle, TILE_SIZE, WIDTH, draw_scanlines, draw_vignette, font_dialogue, font_terminal, font_terminal_small, font_title, get_scaled_mouse, screen)
from core import artpack
from entities.art_cache import get_blood_decal, get_fullscreen_overlay, get_panel_bg
from core.state import STATE
from entities.player import Player, resolve_melee
from entities.enemy_ai import Enemy, enemy_hear_shot, _astar
from entities import corpse
from ui.hud import THEME, MiniMap, draw_objective_panel, draw_pinned_radio
from engine.ui import health_bar as _hud_health_bar, hostiles as _hud_hostiles, weapon_panel as _hud_weapon_panel
from missions.m1 import _draw_molotov_icon
from fx import effects
import cutscenes
from core.camera import update_camera, reset_camera_state, draw_bullets, collide_bullet_walls
from entities.weapons import _wall_blocks_line
from core import config as _config
from engine.core import now_ms as _now_ms, now_s as _now_s  # RPE6 B-001 timebase
audio = _config.audio
_volkov_step_timer = 0.0

from missions.m3 import maps as _m3_maps  # _m3_maps._last_keys/_m3_maps._objective owner
from game.art import m3 as _m3art  # RPE6 Phase 3: baked sprites / layers (procedural fallbacks kept)
from missions.m3 import flow as _m3_flow  # dialogue-state owner
from missions.m3.meta import BCAST_TIME_LIMIT, C_BIRIBEL, C_SYSTEM, C_VOLKOV, MAP_W, MAP_H, MISSION3_ID, MISSION3_LOCATION, MISSION3_PRIMARY_STYLE, MISSION3_STORY_FLAGS, MISSION3_TITLE, MISSION_PHASES, OPENING_CINEMATIC, mission3_ending_shots, STAGE_ARCHIVES, STAGE_ARCHIVES_TRANSITION, STAGE_BREAKOUT, STAGE_BROADCAST, STAGE_COMMS, STAGE_DONE, STAGE_INTERROGATION, STAGE_KILL_ORDER, STAGE_VENT_CUTSCENE, _DOOR_TILE_COL, _DOOR_TILE_ROW
from missions.m3.world import _ARCHIVE_EXIT_COL, _ARCHIVE_EXIT_ROW, _EXIT_TILE_COL, _EXIT_TILE_ROW, _K9_STAND_COL, _K9_STAND_ROW, _RELAY_TILE_COL, _RELAY_TILE_ROW, _VENT_EXIT_COL, _VENT_EXIT_ROW, _VENT_GRATE_COL, _VENT_GRATE_ROW, _detainee_draw_pos, _m3_damage_cell_door_with_bullet, _near, _set_objective, _snap_camera_to, _solid_walls, _build_archives_world, _spawn_m3_guards_once, _stop_m3_alarm, _radio, _update_m3_detainees
from missions.m3.flow import _acquire_vostral_file, _archives_exit_pos, _dialogue_beats, _maru_terminal_pos, _start_maru_contact, _update_chair_break_cutscene_state, _update_player, _update_stage, _vostral_file_pos, start_mission3
from missions.m3.interrog import _action_is_unskippable, _advance_beat, _beat_text, _current_beat, _line_fully_typed, _start_kill_order_phase, _trigger_action, _update_camera
from engine.text import T as _T  # RPE6 Phase 4 text table
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





def _mission3_melee_duration(weapon=None):
    """Return the melee animation duration for Mission 3's improvised weapons."""
    if weapon is None:
        weapon = getattr(STATE, "mission3_weapon", "none")
    if weapon == "chair_leg":
        return 24.0
    if weapon == "shiv":
        return 14.0
    if weapon == "k9_smg":
        return 20.0
    return 18.0


def _mission3_melee_progress():
    """0..1 swing progress, using the same durations as weapons.handle_melee."""
    if not getattr(STATE, "melee_active", False) or getattr(STATE, "melee_timer", 0) <= 0:
        return 0.0
    dur = max(1.0, _mission3_melee_duration())
    return max(0.0, min(1.0, 1.0 - STATE.melee_timer / dur))


def _update_mission3_melee(solid_walls):
    """Tick Mission 3 melee so the chair-leg/shiv swing animates in gameplay.

    M1/M2 already update STATE.melee_timer in their own loops. Mission 3 was
    missing that because its first slice had no combat, so pressing V could set
    melee_active forever. This keeps the improvised weapon visible and gives
    future M3 guards the same shared hit resolver as the rest of the game.

    The hit resolves at a weapon-specific frame so the DAMAGE lands on the
    visual peak of the swing, not before it:
      - shiv:      timer <= 7  → progress 0.5, the thrust-peak extension
      - chair_leg: timer <= 10 → the swing midpoint (unchanged)
    """
    if not getattr(STATE, "melee_active", False):
        return
    STATE.melee_timer -= 1
    hit_frame = 7 if getattr(STATE, "mission3_weapon", "none") == "shiv" else 10
    if STATE.player and not getattr(STATE, "melee_hit_done", False) and STATE.melee_timer <= hit_frame:
        hit_enemy = resolve_melee(STATE.player, STATE.enemies, solid_walls, C_BLOOD)
        STATE.melee_hit_done = True
        if hit_enemy is not None:
            STATE.shots_hit += 1
    if STATE.melee_timer <= 0:
        STATE.melee_active = False
        STATE.melee_hit_done = False


def _mission3_arm_pose_for_weapon(cam_x, cam_y):
    """Return the same two-hand grip point Player.draw uses, in screen space.

    Player.draw already supports melee arm animation even when no_gun=True.
    This helper mirrors that math so the separate Mission 3 shiv/chair-leg
    overlay sits exactly in the player's hands instead of floating nearby.
    """
    if not STATE.player:
        return None
    draw_x = STATE.player.rect.centerx - cam_x
    draw_y = STATE.player.rect.centery - cam_y + getattr(STATE.player, "breathing", 0.0)
    a = STATE.player.angle
    arm_angle = a
    arm_factor = 1.0
    p = _mission3_melee_progress()
    weapon = getattr(STATE, "mission3_weapon", "none")
    if getattr(STATE, "melee_active", False) and p > 0.0 and weapon != "shiv":
        # Chair-leg attacks are broad blunt swings, so they reuse the normal
        # melee arm arc. Shiv attacks are a straight thrust and must keep the
        # arm aimed at the mouse; otherwise the stab trail points sideways.
        if p < 0.25:
            t = p / 0.25
            arm_factor = 1.0 - t * 0.6
            arm_angle = a - t * math.pi / 4
        elif p < 0.75:
            t = (p - 0.25) / 0.5
            arm_factor = 0.4 + t * 0.8
            arm_angle = a - math.pi / 4 + t * (math.pi / 4 + math.pi / 3)
        else:
            t = (p - 0.75) / 0.25
            arm_factor = 1.2 - t * 0.2
            arm_angle = a + math.pi / 3 - t * math.pi / 3
    arm_len = int(16 * arm_factor)
    dx = math.cos(arm_angle)
    dy = math.sin(arm_angle)
    px = -dy
    py = dx
    grip_x = draw_x + dx * (arm_len + 4)
    grip_y = draw_y + dy * (arm_len + 4)
    return draw_x, draw_y, grip_x, grip_y, dx, dy, px, py, p



def _rot_vec(dx, dy, angle):
    """Rotate a unit vector by angle radians."""
    ca = math.cos(angle)
    sa = math.sin(angle)
    return dx * ca - dy * sa, dx * sa + dy * ca


def _draw_weapon_layer(surface, alpha, draw_fn):
    """Draw weapon art with optional alpha.

    Performance note: the old version allocated a full-screen SRCALPHA surface
    for every ghost weapon pose during melee. Chair-leg swings spawned several
    of those per frame, which caused visible attack stutter. Low-alpha ghost
    poses are now skipped; live weapon art draws directly.
    """
    if alpha < 120:
        return
    draw_fn(surface)




def _draw_tapered_blade(surface, grip_x, grip_y, dx, dy, px, py, length=20, alpha=255):
    """Draw the crafted shiv as an actual small knife in gameplay.

    Reads at a glance as an improvised knife: cloth-wrapped grip with fraying
    tails and a dark pommel cap, a small riveted guard, and an asymmetric
    chisel-ground blade with a fuller, edge bevel, scratches, an oxidation
    spot, a faint use-stain near the tip, and a bright tip glint. The
    chisel-ground asymmetry (wider on the edge side, narrower on the spine
    side) keeps the improvised feel - this is a ground-down chair leg,
    not a factory blade.
    """
    def _draw(target):
        # ── Drop shadow under the whole weapon silhouette ──
        # A short fat dark line that the rest of the weapon paints over, so
        # the weapon sits on the floor plane instead of floating.
        pygame.draw.line(target, (0, 0, 0),
                         (grip_x - dx * 10 + 1, grip_y - dy * 10 + 2),
                         (grip_x + dx * (length + 2) + 1,
                          grip_y + dy * (length + 2) + 2), 6)

        # ── Handle core (the broken chair-leg tube under the wrap) ──
        butt_x = grip_x - dx * 10
        butt_y = grip_y - dy * 10
        guard_x = grip_x + dx * 4
        guard_y = grip_y + dy * 4
        # Core (darkest) - the underlying metal.
        pygame.draw.line(target, (22, 17, 13), (butt_x, butt_y), (guard_x, guard_y), 8)
        # Mid-tone highlight band on the upper side.
        pygame.draw.line(target, (74, 56, 40),
                         (butt_x + px * 1.8, butt_y + py * 1.8),
                         (guard_x + px * 1.8, guard_y + py * 1.8), 2)
        # Top edge sheen - catches light along the back of the grip.
        pygame.draw.line(target, (112, 86, 60),
                         (butt_x + px * 2.6, butt_y + py * 2.6),
                         (guard_x + px * 2.6, guard_y + py * 2.6), 1)
        # Lower-edge shadow - grounds the cylinder shape.
        pygame.draw.line(target, (10, 7, 5),
                         (butt_x - px * 2.8, butt_y - py * 2.8),
                         (guard_x - px * 2.8, guard_y - py * 2.8), 1)

        # ── Pommel / butt cap ──
        # A small darker cap at the back end with a rivet dot - closes off
        # the handle so it doesn't read as an open tube.
        pommel = [
            (butt_x - dx * 2.0 + px * 3.6, butt_y - dy * 2.0 + py * 3.6),
            (butt_x + dx * 1.0 + px * 3.6, butt_y + dy * 1.0 + py * 3.6),
            (butt_x + dx * 1.0 - px * 3.6, butt_y + dy * 1.0 - py * 3.6),
            (butt_x - dx * 2.0 - px * 3.6, butt_y - dy * 2.0 - py * 3.6),
        ]
        pygame.draw.polygon(target, (44, 34, 24), pommel)
        pygame.draw.polygon(target, (12, 9, 6), pommel, 1)
        # Pommel top sheen.
        pygame.draw.line(target, (88, 66, 44),
                         (butt_x - dx * 1.2 + px * 2.6, butt_y - dy * 1.2 + py * 2.6),
                         (butt_x + dx * 0.4 + px * 2.6, butt_y + dy * 0.4 + py * 2.6), 1)
        # Rivet dot - tiny bright spec on the pommel face.
        pygame.draw.circle(target, (96, 72, 50),
                           (int(butt_x - dx * 0.6), int(butt_y - dy * 0.6)), 1)

        # ── Cloth wrap: 4 bands with alternating tones + frayed tails ──
        # Each band is a perpendicular stripe across the handle. Tones
        # alternate dark/light so the wrap reads as overlapping strips of
        # torn cloth, not a single solid sleeve. A short frayed tail wisps
        # off one side of each band - the loose end of the cloth strip.
        wrap_bands = (
            (-7.0, 3.8, (28, 22, 17), (98, 76, 56),  1),
            (-4.0, 3.6, (18, 14, 10), (110, 86, 62), -1),
            (-1.0, 3.4, (32, 24, 18), (90, 70, 50),  1),
            ( 2.0, 3.2, (22, 17, 12), (116, 90, 64), -1),
        )
        for off, half_w, dark_col, lite_col, tail_side in wrap_bands:
            cx = grip_x + dx * off
            cy = grip_y + dy * off
            # Band body - perpendicular line across the handle.
            pygame.draw.line(target, dark_col,
                             (cx - px * half_w, cy - py * half_w),
                             (cx + px * half_w, cy + py * half_w), 2)
            # Top highlight stripe - narrower, sits just inside the band.
            pygame.draw.line(target, lite_col,
                             (cx - px * (half_w - 0.7), cy - py * (half_w - 0.7)),
                             (cx + px * (half_w - 0.7), cy + py * (half_w - 0.7)), 1)
            # Frayed tail - short wispy line off one side of the band.
            tx = cx + px * half_w * tail_side
            ty = cy + py * half_w * tail_side
            pygame.draw.line(target, (66, 50, 34),
                             (tx, ty),
                             (tx + px * 1.6 * tail_side + dx * 1.6,
                              ty + py * 1.6 * tail_side + dy * 1.6), 1)

        # ── Guard / stop - a small perpendicular bar with two rivets ──
        # This is what makes the weapon read as a knife (not a key or spike):
        # a clear cross-bar between handle and blade.
        guard_poly = [
            (guard_x - dx * 1.2 + px * 5.6, guard_y - dy * 1.2 + py * 5.6),
            (guard_x + dx * 1.2 + px * 5.6, guard_y + dy * 1.2 + py * 5.6),
            (guard_x + dx * 1.2 - px * 5.6, guard_y + dy * 1.2 - py * 5.6),
            (guard_x - dx * 1.2 - px * 5.6, guard_y - dy * 1.2 - py * 5.6),
        ]
        pygame.draw.polygon(target, (54, 56, 56), guard_poly)
        pygame.draw.polygon(target, (22, 24, 24), guard_poly, 1)
        # Top sheen across the guard.
        pygame.draw.line(target, (132, 136, 134),
                         (guard_x - px * 4.4, guard_y - py * 4.4),
                         (guard_x + px * 4.4, guard_y + py * 4.4), 1)
        # Two rivets pinning the guard to the handle.
        for rivet_off in (-2.6, 2.6):
            rx = guard_x + px * rivet_off
            ry = guard_y + py * rivet_off
            pygame.draw.circle(target, (24, 26, 26), (int(rx), int(ry)), 2)
            pygame.draw.circle(target, (152, 156, 154),
                               (int(rx - 0.4), int(ry - 0.4)), 1)

        # ── Blade - asymmetric chisel-ground point with fuller + bevels ──
        # The edge side (px +) widens out more than the spine side (px -),
        # giving the asymmetric chisel-ground profile of an improvised edge.
        base_x     = grip_x + dx * 5
        base_y     = grip_y + dy * 5
        shoulder_x = grip_x + dx * 10
        shoulder_y = grip_y + dy * 10
        mid_x      = grip_x + dx * (length * 0.58)
        mid_y      = grip_y + dy * (length * 0.58)
        tip_x      = grip_x + dx * length
        tip_y      = grip_y + dy * length

        blade = [
            (base_x     + px * 3.8, base_y     + py * 3.8),  # edge side of base
            (shoulder_x + px * 3.2, shoulder_y + py * 3.2),  # edge widest point
            (mid_x      + px * 2.2, mid_y      + py * 2.2),  # edge tapering
            (tip_x,                       tip_y),                 # tip
            (mid_x      - px * 1.4, mid_y      - py * 1.4),  # spine return
            (shoulder_x - px * 2.4, shoulder_y - py * 2.4),  # spine
            (base_x     - px * 3.4, base_y     - py * 3.4),  # spine side of base
        ]
        pygame.draw.polygon(target, (122, 130, 134), blade)
        pygame.draw.polygon(target, (18, 20, 22), blade, 1)

        # Spine - darker band along the back edge of the blade.
        pygame.draw.line(target, (58, 64, 68),
                         (base_x - px * 2.6 + dx * 1.0,
                          base_y - py * 2.6 + dy * 1.0),
                         (shoulder_x - px * 1.8, shoulder_y - py * 1.8), 1)
        pygame.draw.line(target, (58, 64, 68),
                         (shoulder_x - px * 1.8, shoulder_y - py * 1.8),
                         (mid_x - px * 0.9, mid_y - py * 0.9), 1)
        pygame.draw.line(target, (78, 84, 88),
                         (mid_x - px * 0.9, mid_y - py * 0.9),
                         (tip_x - dx * 3, tip_y - dy * 3), 1)

        # Chisel-ground bevel flat - a slightly lighter inset polygon on the
        # edge side, faking the flat ground into the edge.
        bevel = [
            (base_x     + px * 2.6, base_y     + py * 2.6),
            (shoulder_x + px * 2.0, shoulder_y + py * 2.0),
            (mid_x      + px * 1.2, mid_y      + py * 1.2),
            (mid_x      + px * 0.4, mid_y      + py * 0.4),
            (shoulder_x + px * 1.0, shoulder_y + py * 1.0),
            (base_x     + px * 1.4, base_y     + py * 1.4),
        ]
        pygame.draw.polygon(target, (150, 158, 162), bevel)

        # Fuller - a thin darker groove running down the middle of the blade.
        fuller_a = (base_x + px * 0.6 + dx * 1.5, base_y + py * 0.6 + dy * 1.5)
        fuller_b = (mid_x  + px * 0.2,             mid_y  + py * 0.2)
        fuller_c = (tip_x  - dx * 4 - px * 0.3,    tip_y  - dy * 4 - py * 0.3)
        pygame.draw.line(target, (76, 82, 86), fuller_a, fuller_b, 1)
        pygame.draw.line(target, (92, 98, 102), fuller_b, fuller_c, 1)

        # Sharpened edge - bright glint line along the very edge of the blade.
        pygame.draw.line(target, (238, 246, 242),
                         (base_x     + px * 3.2 + dx * 1.0,
                          base_y     + py * 3.2 + dy * 1.0),
                         (shoulder_x + px * 2.6, shoulder_y + py * 2.6), 1)
        pygame.draw.line(target, (238, 246, 242),
                         (shoulder_x + px * 2.6, shoulder_y + py * 2.6),
                         (mid_x      + px * 1.6, mid_y      + py * 1.6), 1)
        pygame.draw.line(target, (220, 228, 224),
                         (mid_x + px * 1.6, mid_y + py * 1.6),
                         (tip_x - dx * 1.5, tip_y - dy * 1.5), 1)

        # Tip glint - tiny bright dot right at the point.
        pygame.draw.circle(target, (250, 252, 250),
                           (int(tip_x - dx * 0.5), int(tip_y - dy * 0.5)), 1)

        # Scratches - three short bright marks at angles across the flat,
        # evidence of the blade being dragged across the drain grate.
        for s_off, s_len, s_col in (
            (0.30, 2.6, (204, 214, 214)),
            (0.55, 2.0, (182, 192, 194)),
            (0.72, 1.6, (212, 222, 220)),
        ):
            sx = grip_x + dx * (length * s_off)
            sy = grip_y + dy * (length * s_off)
            pygame.draw.line(target, s_col,
                             (sx + px * 1.8, sy + py * 1.8),
                             (sx + px * 1.8 - dx * s_len * 0.6 + px * s_len * 0.4,
                              sy + py * 1.8 - dy * s_len * 0.6 + py * s_len * 0.4), 1)

        # Oxidation / patina spot near the base of the blade.
        ox_x = base_x + dx * 2.0 + px * 1.5
        ox_y = base_y + dy * 2.0 + py * 1.5
        pygame.draw.circle(target, (78, 60, 48), (int(ox_x), int(ox_y)), 1)

        # Faint use-stain near the tip - small dark patch, evidence this
        # thing has already been used at least once.
        stain_x = tip_x - dx * 5
        stain_y = tip_y - dy * 5
        pygame.draw.circle(target, (92, 40, 36), (int(stain_x), int(stain_y)), 1)
    _draw_weapon_layer(surface, alpha, _draw)

def _draw_chair_leg_weapon(surface, grip_x, grip_y, dx, dy, px, py, alpha=255):
    """Draw the snapped chair leg as a short piece of broken furniture.

    It is a bent metal tube with a rubber foot, a tiny bolt bracket, and a
    jagged hollow end - top-down scale, not a full-length pipe.
    """
    def _draw(target):
        start_x = grip_x - dx * 5
        start_y = grip_y - dy * 5
        knee_x = grip_x + dx * 10 + px * 2.2
        knee_y = grip_y + dy * 10 + py * 2.2
        end_x = grip_x + dx * 24 + px * 4.0
        end_y = grip_y + dy * 24 + py * 4.0

        # Ground shadow.
        pygame.draw.line(target, (0, 0, 0),
                         (start_x + 1, start_y + 2), (knee_x + 1, knee_y + 2), 7)
        pygame.draw.line(target, (0, 0, 0),
                         (knee_x + 1, knee_y + 2), (end_x + 1, end_y + 2), 7)

        # Main bent tube.
        pygame.draw.line(target, (24, 25, 26), (start_x, start_y), (knee_x, knee_y), 6)
        pygame.draw.line(target, (34, 35, 36), (knee_x, knee_y), (end_x, end_y), 6)
        pygame.draw.line(target, (94, 98, 100),
                         (start_x + px * 1.3, start_y + py * 1.3),
                         (end_x + px * 1.3, end_y + py * 1.3), 2)
        pygame.draw.line(target, (9, 10, 11),
                         (start_x - px * 2.2, start_y - py * 2.2),
                         (end_x - px * 2.2, end_y - py * 2.2), 1)

        # Small square welded/bolt bracket from the old chair frame.
        bx = grip_x + dx * 6 - px * 1
        by = grip_y + dy * 6 - py * 1
        bracket = [
            (bx - dx * 4 - px * 3, by - dy * 4 - py * 3),
            (bx + dx * 4 - px * 3, by + dy * 4 - py * 3),
            (bx + dx * 4 + px * 3, by + dy * 4 + py * 3),
            (bx - dx * 4 + px * 3, by - dy * 4 + py * 3),
        ]
        pygame.draw.polygon(target, (50, 48, 43), bracket)
        pygame.draw.polygon(target, (112, 105, 88), bracket, 1)
        pygame.draw.circle(target, (150, 140, 112), (int(bx), int(by)), 1)

        # Rubber foot cap on the back end.
        foot_x = start_x - dx * 3
        foot_y = start_y - dy * 3
        pygame.draw.circle(target, (9, 9, 10), (int(foot_x), int(foot_y)), 4)
        pygame.draw.circle(target, (55, 55, 54), (int(foot_x), int(foot_y)), 4, 1)

        # Jagged hollow snapped end.
        pygame.draw.circle(target, (13, 13, 15), (int(end_x), int(end_y)), 4)
        pygame.draw.circle(target, (122, 122, 116), (int(end_x), int(end_y)), 4, 1)
        for off in (-3, 0, 3):
            pygame.draw.line(target, (160, 148, 116),
                             (end_x - dx * 3 + px * off, end_y - dy * 3 + py * off),
                             (end_x + dx * 2 - px * off * 0.4, end_y + dy * 2 - py * off * 0.4), 1)
    _draw_weapon_layer(surface, alpha, _draw)



def _draw_gripping_hand(surface, grip_x, grip_y, dx, dy, px, py,
                        origin_x=None, origin_y=None):
    """Draw a top-down clenched hand locked around the handle.

    This replaces the old loose circle hand, which made the wrist/handle look
    broken. The palm, thumb, and knuckles are oriented to the weapon vector and
    the handle passes through the fist.

    When ``origin_x``/``origin_y`` (the player's screen-space centre) are
    supplied, a uniform-coloured forearm is drawn from the shoulder out to the
    grip as a tapered quad. This lets the grip sit WELL past the neutral hand
    position - so during a shiv thrust the whole arm visibly extends forward
    instead of the blade floating off a frozen wrist. Without the origin the
    original short wrist stub is drawn (used by the chair-leg swing, whose
    grip stays put).
    """
    skin = C_PLAYER_SKIN
    shade = (145, 112, 84)
    dark = (82, 55, 38)

    if origin_x is not None:
        # Extending forearm: shoulder (near player centre) → wrist (just
        # behind the grip). Drawn AFTER Player.draw's static arm, so it
        # paints over it and the reach reads as the arm straightening.
        sh_x = origin_x + dx * 9
        sh_y = origin_y + dy * 9
        w0 = 7.0    # shoulder half-width
        w1 = 3.5    # wrist half-width
        forearm = [
            (sh_x + px * w0, sh_y + py * w0),
            (sh_x - px * w0, sh_y - py * w0),
            (grip_x - px * w1 - dx * 3, grip_y - py * w1 - dy * 3),
            (grip_x + px * w1 - dx * 3, grip_y + py * w1 - dy * 3),
        ]
        pygame.draw.polygon(surface, (18, 24, 18),
                            [(x + 1, y + 1) for x, y in forearm])
        pygame.draw.polygon(surface, C_PLAYER_UNIFORM, forearm)
        pygame.draw.polygon(surface,
                            (max(0, C_PLAYER_UNIFORM[0] - 12),
                             max(0, C_PLAYER_UNIFORM[1] - 9),
                             max(0, C_PLAYER_UNIFORM[2] - 7)),
                            forearm, 1)
        # Sleeve cuff ring where the forearm meets the fist.
        cuff_x = grip_x - dx * 5
        cuff_y = grip_y - dy * 5
        pygame.draw.line(surface, (26, 32, 24),
                         (cuff_x - px * 4, cuff_y - py * 4),
                         (cuff_x + px * 4, cuff_y + py * 4), 3)
    else:
        # Original short visible wrist/cuff stub.
        wx0 = grip_x - dx * 9
        wy0 = grip_y - dy * 9
        wx1 = grip_x - dx * 2
        wy1 = grip_y - dy * 2
        pygame.draw.line(surface, (42, 52, 44), (wx0, wy0), (wx1, wy1), 5)
        pygame.draw.line(surface, (24, 30, 26),
                         (wx0 - px * 2, wy0 - py * 2), (wx1 - px * 2, wy1 - py * 2), 1)

    # Palm polygon angled with the grip.
    palm = [
        (grip_x - dx * 5 + px * 5, grip_y - dy * 5 + py * 5),
        (grip_x + dx * 5 + px * 4, grip_y + dy * 5 + py * 4),
        (grip_x + dx * 7 - px * 3, grip_y + dy * 7 - py * 3),
        (grip_x - dx * 3 - px * 5, grip_y - dy * 3 - py * 5),
    ]
    pygame.draw.polygon(surface, dark, [(x + 1, y + 1) for x, y in palm])
    pygame.draw.polygon(surface, skin, palm)
    pygame.draw.polygon(surface, shade, palm, 1)

    # Knuckles curling over the handle on the forward side.
    for off in (-3.5, 0.0, 3.5):
        kx = grip_x + dx * 5 + px * off
        ky = grip_y + dy * 5 + py * off
        pygame.draw.circle(surface, skin, (int(kx), int(ky)), 3)
        pygame.draw.circle(surface, shade, (int(kx + dx * 1), int(ky + dy * 1)), 2, 1)
        pygame.draw.line(surface, (205, 168, 138),
                         (int(kx + dx * 2) - 1, int(ky + dy * 2)),
                         (int(kx + dx * 2) + 1, int(ky + dy * 2)), 1)

    # Thumb crosses the handle; this is the visual anchor that makes the
    # weapon read as gripped instead of floating past the hand.
    t0 = (grip_x - dx * 2 + px * 5, grip_y - dy * 2 + py * 5)
    t1 = (grip_x + dx * 6 - px * 3, grip_y + dy * 6 - py * 3)
    pygame.draw.line(surface, shade, (t0[0] + 1, t0[1] + 1), (t1[0] + 1, t1[1] + 1), 5)
    pygame.draw.line(surface, skin, t0, t1, 4)
    t2 = (grip_x + dx * 9 - px * 6, grip_y + dy * 9 - py * 6)
    pygame.draw.line(surface, shade, (t1[0] + 1, t1[1] + 1), (t2[0] + 1, t2[1] + 1), 4)
    pygame.draw.line(surface, skin, t1, t2, 3)
    pygame.draw.circle(surface, (205, 168, 138), (int(t2[0]), int(t2[1])), 1)

def _draw_shiv_spark(surface, x, y, t):
    """Brief additive glint at the blade tip on the thrust peak.

    Drawn with pre-multiplied RGB on a black surface + BLEND_RGB_ADD so it
    reads as a real light flash (brightens whatever is underneath) rather
    than an opaque blob pasted on top. ``t`` is 0..1 across the flash life
    (0 = full intensity, 1 = faded out).
    """
    fade = max(0.0, 1.0 - t)
    size = 24
    spark = pygame.Surface((size * 2, size * 2))   # opaque black, no alpha
    spark.fill((0, 0, 0))
    cx = cy = size

    # Bright core (pre-multiplied for additive blend).
    core_r = max(2, int(3 + 4 * fade))
    core_v = int(225 * fade)
    pygame.draw.circle(spark, (core_v, core_v, min(255, core_v + 18)), (cx, cy), core_r)
    halo_v = int(85 * fade)
    pygame.draw.circle(spark, (halo_v, halo_v, min(255, halo_v + 12)), (cx, cy), core_r + 4)

    # Four short cross-spikes radiating from the core.
    spike_v = int(155 * fade)
    spike_len = 10 * fade + 4
    for ang in (0.0, math.pi / 2, math.pi / 4, -math.pi / 4):
        ex = cx + math.cos(ang) * spike_len
        ey = cy + math.sin(ang) * spike_len
        pygame.draw.line(spark, (spike_v, spike_v, min(255, spike_v + 12)),
                         (cx, cy), (int(ex), int(ey)), 2)

    surface.blit(spark, (int(x) - size, int(y) - size),
                 special_flags=pygame.BLEND_RGB_ADD)


def _draw_mission3_hand_weapon(surface, cam_x, cam_y):
    """Draw the actual M3 improvised weapon in Biribel's hands in gameplay."""
    weapon = getattr(STATE, "mission3_weapon", "none")
    if weapon not in ("chair_leg", "shiv") or not STATE.player:
        return
    pose = _mission3_arm_pose_for_weapon(cam_x, cam_y)
    if pose is None:
        return
    _draw_x, _draw_y, grip_x, grip_y, dx, dy, px, py, swing_p = pose
    attacking = bool(getattr(STATE, "melee_active", False)) and swing_p > 0.0

    if weapon == "chair_leg":
        # Heavy side-swing: wind-up left, sweep right, recover. The trail is
        # built from the weapon's real tip positions, so it always follows the
        # actual swing direction instead of using a generic screen-space arc.
        if attacking:
            base_dx, base_dy = dx, dy
            e = swing_p * swing_p * (3 - 2 * swing_p)
            sweep = -0.95 + 1.9 * e

            def _chair_tip(angle):
                tdx, tdy = _rot_vec(base_dx, base_dy, angle)
                tpx, tpy = -tdy, tdx
                return (grip_x + tdx * 30 + tpx * 4,
                        grip_y + tdy * 30 + tpy * 4)

            # Lightweight swing indication: no full-screen alpha surfaces.
            # The old ghost/smear pass allocated several WIDTH x HEIGHT surfaces
            # every frame and made chair-leg attacks stutter badly.
            old_tip = _chair_tip(-0.95 + 1.9 * max(0.0, e - 0.16))
            live_tip = _chair_tip(sweep)

            dx, dy = _rot_vec(base_dx, base_dy, sweep)
            px, py = -dy, dx

            if 0.22 < swing_p < 0.78:
                pygame.draw.line(surface, (90, 96, 90), old_tip, live_tip, 2)
                pygame.draw.circle(surface, (120, 125, 110), (int(live_tip[0]), int(live_tip[1])), 3)
        _draw_chair_leg_weapon(surface, grip_x, grip_y, dx, dy, px, py)

    else:  # shiv
        # FAST STAB - a knife THRUST, not a slash. Three phases (all driven
        # by the smoothstepped progress ``e`` so the motion eases naturally):
        #
        #   windup   (e 0.00→0.22): cock the blade back ~6px and flick the
        #                            wrist ~23° to telegraph the strike.
        #   thrust   (e 0.22→0.50): blade shoots forward FAST (ease-out) to
        #                            ~18px past the neutral grip - the stab.
        #                            Wrist straightens back to dead-ahead.
        #   recover  (e 0.50→1.00): settle back to the neutral ready pose.
        #
        # The grip itself extends forward along the aim direction (the
        # ``reach`` offset), and _draw_gripping_hand draws a forearm that
        # stretches from the player's shoulder out to that grip - so the
        # whole arm+blade visibly LUNGES, instead of the blade wiggling on a
        # frozen wrist. A motion-blur trail traces the blade tip's path and
        # a bright glint flashes at the thrust peak (where the hit lands).
        if attacking:
            base_dx, base_dy = dx, dy
            ox, oy = grip_x, grip_y          # neutral grip from the arm pose
            e = swing_p * swing_p * (3 - 2 * swing_p)

            def _stab(pe):
                """Blade state at progress ``pe``.

                Returns (reach, flick, dir_x, dir_y, perp_x, perp_y) where
                reach is the forward grip offset along the aim vector and
                flick is the wrist rotation applied to the blade direction.
                """
                if pe < 0.22:                # windup - cock back, telegraph
                    t = pe / 0.22
                    reach = -6.0 * t
                    flick = 0.40 * t
                elif pe < 0.50:              # thrust - shoot forward (snappy)
                    t = (pe - 0.22) / 0.28
                    te = 1.0 - (1.0 - t) ** 2   # ease-out: fast off the mark
                    reach = -6.0 + 24.0 * te
                    flick = 0.40 * (1.0 - te)
                else:                        # recover - settle to neutral
                    t = (pe - 0.50) / 0.50
                    reach = 18.0 - 18.0 * t
                    flick = 0.0
                fdx, fdy = _rot_vec(base_dx, base_dy, flick)
                return reach, flick, fdx, fdy, -fdy, fdx

            # Lightweight thrust line. Avoid full-screen motion-blur surfaces;
            # the live blade + hand extension is readable enough and cheaper.
            pe_tail = max(0.0, e - 0.10)
            tr, _tf, tdx, tdy, _tpx, _tpy = _stab(pe_tail)
            tail_tip = (ox + base_dx * tr + tdx * 20,
                        oy + base_dy * tr + tdy * 20)

            # ── Live blade at the current progress ──
            r, f, fdx, fdy, fpx, fpy = _stab(e)
            grip_x = ox + base_dx * r
            grip_y = oy + base_dy * r
            dx, dy, px, py = fdx, fdy, fpx, fpy
            live_tip = (grip_x + dx * 20, grip_y + dy * 20)
            if 0.22 < e < 0.58:
                pygame.draw.line(surface, (115, 130, 126), tail_tip, live_tip, 2)

            # ── Thrust-peak glint: a bright additive flash at full extension ──
            # Fires right around e≈0.5, which is exactly where the melee hit
            # resolves (see _update_mission3_melee). Reads as the blade
            # catching light at the moment of impact.
            if 0.44 < e < 0.60:
                _draw_shiv_spark(surface,
                                 grip_x + dx * 20, grip_y + dy * 20,
                                 (e - 0.44) / 0.16)
        _draw_tapered_blade(surface, grip_x, grip_y, dx, dy, px, py, length=20)

    # Repaint a proper oriented fist over the handle so it reads as gripped.
    # The shiv passes the player's centre so _draw_gripping_hand can render
    # the extending forearm that lunges with the thrust.
    if weapon == "shiv":
        _draw_gripping_hand(surface, grip_x, grip_y, dx, dy, px, py,
                            origin_x=_draw_x, origin_y=_draw_y)
    else:
        _draw_gripping_hand(surface, grip_x, grip_y, dx, dy, px, py)

_M3_WEAPON_ICON_VARIANTS = {"shiv": 0, "chair_leg": 1, "k9_smg": 2, "sidearm": 3}


def _draw_m3_weapon_icon(surface, x, y, weapon):
    """Tiny HUD icon for Mission 3's improvised weapon (baked sprite game.art.m3.weapon_icon,
    procedural _paint_m3_weapon_icon as the fallback / bake source)."""
    spr = _m3art.get("weapon_icon", _M3_WEAPON_ICON_VARIANTS.get(weapon, 4))
    if spr is not None:
        surface.blit(spr, (x - 8, y - 4))
        return
    _paint_m3_weapon_icon(surface, x, y, weapon)


def _paint_m3_weapon_icon(surface, x, y, weapon):
    """Procedural weapon icon; opaque primitives only inside (x-8, y-4) .. (x+48, y+32)."""
    if weapon == "shiv":
        # Unique M3 shiv icon: wrapped handle with pommel cap + riveted
        # guard + asymmetric chisel-ground blade with fuller, edge bevel,
        # scratches, and a tip glint. Same visual language as the in-world
        # _draw_tapered_blade, just simplified for the 40x24 icon box.
        # Handle core.
        pygame.draw.line(surface, (22, 17, 13), (x, y + 18), (x + 13, y + 10), 6)
        pygame.draw.line(surface, (96, 76, 56),
                         (x + 1, y + 16), (x + 12, y + 9), 1)
        # Pommel cap at the back.
        pygame.draw.circle(surface, (44, 34, 24), (x - 1, y + 19), 3)
        pygame.draw.circle(surface, (12, 9, 6), (x - 1, y + 19), 3, 1)
        pygame.draw.circle(surface, (96, 72, 50), (x - 1, y + 19), 1)
        # Cloth wrap bands - alternating dark/light with little tails.
        for ox, col, tail in (
            (3, (28, 22, 17), 1),
            (6, (110, 86, 62), -1),
            (9, (32, 24, 18), 1),
            (12, (116, 90, 64), -1),
        ):
            bx = x + ox
            by = y + 19 - ox // 2
            pygame.draw.line(surface, col, (bx, by - 2), (bx, by + 3), 1)
            pygame.draw.line(surface, (66, 50, 34),
                             (bx + tail * 2, by + 1),
                             (bx + tail * 3, by + 2), 1)
        # Guard bar with two rivets.
        pygame.draw.line(surface, (54, 56, 56),
                         (x + 12, y + 7), (x + 16, y + 14), 3)
        pygame.draw.line(surface, (132, 136, 134),
                         (x + 12, y + 8), (x + 15, y + 13), 1)
        pygame.draw.circle(surface, (24, 26, 26), (x + 13, y + 9), 1)
        pygame.draw.circle(surface, (24, 26, 26), (x + 15, y + 12), 1)
        # Blade silhouette - asymmetric chisel-ground profile.
        blade = [
            (x + 14, y + 9),
            (x + 22, y + 5),
            (x + 33, y + 0),
            (x + 36, y + 4),
            (x + 30, y + 9),
            (x + 18, y + 13),
        ]
        pygame.draw.polygon(surface, (122, 130, 134), blade)
        pygame.draw.polygon(surface, (18, 20, 22), blade, 1)
        # Chisel-ground bevel flat (lighter inset on the edge side).
        bevel = [
            (x + 16, y + 9),
            (x + 24, y + 5),
            (x + 32, y + 1),
            (x + 28, y + 6),
            (x + 20, y + 10),
        ]
        pygame.draw.polygon(surface, (150, 158, 162), bevel)
        # Fuller - darker groove down the middle.
        pygame.draw.line(surface, (76, 82, 86),
                         (x + 18, y + 8), (x + 30, y + 3), 1)
        # Sharpened edge - bright glint along the very edge.
        pygame.draw.line(surface, (238, 246, 242),
                         (x + 22, y + 5), (x + 34, y + 0), 1)
        pygame.draw.line(surface, (220, 228, 224),
                         (x + 34, y + 0), (x + 36, y + 4), 1)
        # Tip glint dot.
        pygame.draw.circle(surface, (250, 252, 250), (x + 35, y + 1), 1)
        # Two small scratches across the flat.
        pygame.draw.line(surface, (204, 214, 214),
                         (x + 22, y + 4), (x + 24, y + 6), 1)
        pygame.draw.line(surface, (182, 192, 194),
                         (x + 27, y + 3), (x + 29, y + 5), 1)
        # Oxidation spot near the base.
        pygame.draw.circle(surface, (78, 60, 48), (x + 18, y + 9), 1)
    elif weapon == "chair_leg":
        # Bent metal tube with rubber foot + jagged end.
        pygame.draw.line(surface, (36, 38, 40), (x, y + 18), (x + 15, y + 9), 5)
        pygame.draw.line(surface, (46, 48, 50), (x + 15, y + 9), (x + 34, y + 7), 5)
        pygame.draw.line(surface, (100, 104, 104), (x + 2, y + 17), (x + 33, y + 6), 1)
        pygame.draw.circle(surface, (12, 12, 13), (x - 2, y + 20), 4)
        pygame.draw.circle(surface, (118, 118, 114), (x + 35, y + 7), 4, 1)
    elif weapon == "k9_smg":
        # K-9 suppressed SMG - compact receiver, long suppressor, stick mag.
        pygame.draw.rect(surface, (24, 28, 28), (x + 3, y + 8, 25, 7), border_radius=2)
        pygame.draw.rect(surface, (78, 98, 90), (x + 3, y + 8, 25, 7), 1, border_radius=2)
        pygame.draw.line(surface, (40, 46, 46), (x + 27, y + 11), (x + 42, y + 11), 5)
        pygame.draw.line(surface, (105, 120, 112), (x + 28, y + 9), (x + 41, y + 9), 1)
        pygame.draw.rect(surface, (18, 20, 20), (x + 13, y + 14, 6, 14), border_radius=1)
        pygame.draw.rect(surface, (88, 96, 92), (x + 13, y + 14, 6, 14), 1, border_radius=1)
        pygame.draw.line(surface, (60, 68, 64), (x + 4, y + 14), (x - 5, y + 19), 2)
        pygame.draw.circle(surface, (7, 8, 8), (x + 43, y + 11), 2)
    elif weapon == "sidearm":
        # Looted IPA pistol - top-down silhouette mirroring the ground
        # pickup marker, with a small highlight on the slide.
        # Slide.
        pygame.draw.rect(surface, (40, 40, 44),
                         (x + 4, y + 6, 28, 8), border_radius=2)
        pygame.draw.rect(surface, (60, 60, 64),
                         (x + 4, y + 6, 28, 8), 1, border_radius=2)
        # Slide highlight.
        pygame.draw.line(surface, (110, 110, 116),
                         (x + 6, y + 7), (x + 30, y + 7), 1)
        # Grip.
        pygame.draw.rect(surface, (30, 30, 34),
                         (x + 16, y + 13, 9, 12), border_radius=1)
        # Trigger guard.
        pygame.draw.arc(surface, (50, 50, 54),
                        (x + 10, y + 12, 8, 8),
                        math.pi * 0.5, math.pi * 1.5, 1)
        # Sights.
        pygame.draw.rect(surface, (90, 90, 95), (x + 6, y + 4, 2, 2))
        pygame.draw.rect(surface, (90, 90, 95), (x + 28, y + 4, 2, 2))
    else:
        pygame.draw.circle(surface, (80, 80, 85), (x + 16, y + 8), 8, 1)
        pygame.draw.line(surface, (110, 70, 70), (x + 8, y), (x + 24, y + 16), 1)


_COMMS_CHECKLIST_ROWS = (
    ("m3_comms_power_restored", "AUX POWER", "Battery Backup"),
    ("m3_comms_auth_acquired", "RELAY AUTH", "Security booth"),
    ("m3_relay_tuned", "TUNE RELAY", "Comms relay"),
)


def _draw_comms_checklist(surface):
    """Persistent 3-row restoration checklist (top-right, under the minimap).

    Replaces the old one-sentence arrow chain as the durable teaching of the
    power -> auth -> tune order: done rows tick, the current row is highlighted
    with its station name, future rows stay dim.
    """
    if getattr(STATE, "mission3_stage", None) != STAGE_COMMS:
        return
    if getattr(STATE, "m3_relay_tuned", False):
        return
    rows_rendered = []
    current_marked = False
    done_n = 0
    for flag, label, place in _COMMS_CHECKLIST_ROWS:
        done = bool(getattr(STATE, flag, False))
        if done:
            done_n += 1
        is_current = (not done) and (not current_marked)
        if is_current:
            current_marked = True
        if done:
            text, col = f"[x] {label}", (105, 200, 140)
        elif is_current:
            text, col = f">> {label}  -  {place}", (255, 214, 110)
        else:
            text, col = f"[ ] {label}", (92, 96, 92)
        surf = font_terminal_small.render(text, True, col)
        if is_current:
            surf.set_alpha(int(200 + 55 * math.sin(_now_s() * 4.0)))
        rows_rendered.append(surf)
    head = font_terminal_small.render(
        _T("m3.relay_restoration", done=done_n, total=len(_COMMS_CHECKLIST_ROWS)),
        True, (150, 190, 170))
    # Size the panel to its widest line so text can never overflow the box,
    # then right-align it to the minimap's right edge and clamp to the screen
    # so it can never run off it (whatever the font metrics resolve to).
    box_w = max([head.get_width()] + [r.get_width() for r in rows_rendered]) + 16
    box_h = 24 + 17 * len(rows_rendered) + 8
    panel = pygame.Surface((box_w, box_h), pygame.SRCALPHA)
    pygame.draw.rect(panel, (8, 12, 12, 205), panel.get_rect(), border_radius=4)
    pygame.draw.rect(panel, (96, 148, 128, 210), panel.get_rect(), 1,
                     border_radius=4)
    panel.blit(head, (8, 6))
    for i, surf in enumerate(rows_rendered):
        panel.blit(surf, (8, 24 + i * 17))
    mm = getattr(STATE, "minimap", None)
    if mm is not None:
        px = mm.x + mm.minimap_w - box_w
        py = mm.y + mm.minimap_h + 12
    else:
        px, py = WIDTH - box_w - 16, 196
    px = max(8, min(px, WIDTH - box_w - 8))
    surface.blit(panel, (px, py))


def _draw_broadcast_address_clock(surface):
    """The 22:00 clock, top-right under the minimap (Broadcast Wing only).

    The finale is a race, so the race has to be legible: the upload OS shows
    the clock only once the player is already at the PC, which is exactly too
    late. This plate ticks during the corridor/gate/booth waves, warms to red
    in the last minute, and reads ADDRESS COMPLETE after the timeout (the
    fail cutscene takes over from there).

    Drawn as an analog dial: the studio wall clock runs 22:00 minus the slice
    time limit -> 22:00 (21:57 at the current 3-minute limit) as the slice burns
    down, the minute hand crawls toward the red 12 o'clock deadline notch, a
    thin sweep hand keeps the seconds alive, and the remaining-time ring
    outside the face drains with the countdown. A small digital IN MM:SS line
    stays under the dial because the last minute must stay readable at a
    glance - the analog face is the fiction, the digits are the safety net.
    """
    if getattr(STATE, "mission3_stage", None) != STAGE_BROADCAST:
        return
    left = getattr(STATE, "m3_bcast_time_left", None)
    if left is None:
        return
    # The station OS draws its own ADDRESS IN plate - don't double up.
    try:
        from ui import upload_os  # lazy: ui package
        if upload_os.is_upload_os_active():
            return
    except Exception:
        pass

    failed = bool(getattr(STATE, "m3_bcast_failed", False))
    urgent = not failed and left <= 60 * 60
    col = (235, 70, 60) if failed else ((255, 150, 90) if urgent else (150, 190, 170))

    # In-game wall time. One tick is one display-second (the limit is authored
    # in frames at 60fps), so ``left`` doubles as seconds-to-22:00 and the dial
    # opens at 22:00 minus BCAST_TIME_LIMIT (21:57 at the current 3-minute
    # limit). Failure pins the hands to 22:00 - the address has begun.
    disp = max(0.0, float(left) / 60.0)
    tod = (22 * 3600 - disp) % (12 * 3600)
    if failed:
        hour12, minute_f, second = 10.0, 0.0, 0.0
    else:
        hour12 = float(int(tod // 3600))
        minute_f = float(int((tod % 3600) // 60)) + (tod % 60) / 60.0
        second = float(tod % 60)
    # 12 o'clock sits at -90deg; screen y grows down, so +angle reads clockwise.
    sec_ang = math.radians(second / 60.0 * 360.0 - 90.0)
    min_ang = math.radians(minute_f / 60.0 * 360.0 - 90.0)
    hour_ang = math.radians(((hour12 % 12.0) + minute_f / 60.0) / 12.0
                            * 360.0 - 90.0)

    head_surf = font_terminal_small.render(_T("m3.state_address_22_00"), True,
                                           (120, 160, 150))
    if failed:
        body = "ADDRESS COMPLETE"
    else:
        body = f"IN {int(disp) // 60:02d}:{int(disp) % 60:02d}"
    body_surf = font_terminal.render(body, True, col)
    if urgent:
        # Blink faster the closer it gets, but never fully vanish - the clock
        # must stay readable on every frame of the last minute.
        body_surf.set_alpha(int(170 + 85 * math.sin(_now_s() * 6.0)))

    dial_r = 34           # clock face radius
    ring_r = dial_r + 7   # countdown ring, outside the ticks
    pad = 10
    box_w = max(head_surf.get_width(), body_surf.get_width(),
                2 * ring_r + 4) + 2 * pad
    box_h = (6 + head_surf.get_height() + 4 + 2 * ring_r + 4
             + body_surf.get_height() + 8)
    border = (*col, 205) if failed else (120, 100, 90, 205)
    panel = pygame.Surface((box_w, box_h), pygame.SRCALPHA)
    pygame.draw.rect(panel, (10, 8, 10, 210), panel.get_rect(), border_radius=4)
    pygame.draw.rect(panel, border, panel.get_rect(), 1, border_radius=4)
    panel.blit(head_surf, ((box_w - head_surf.get_width()) // 2, 6))

    cx = box_w // 2
    cy = 6 + head_surf.get_height() + 4 + ring_r

    def _dial_pt(angle, radius):
        return (cx + math.cos(angle) * radius, cy + math.sin(angle) * radius)

    # Face + bezel, then the hour ticks (12/3/6/9 long).
    pygame.draw.circle(panel, (16, 18, 18, 232), (cx, cy), dial_r)
    pygame.draw.circle(panel, (96, 118, 110, 220), (cx, cy), dial_r, 2)
    for i in range(12):
        a = math.radians(i * 30 - 90)
        major = i % 3 == 0
        pygame.draw.line(panel, (170, 200, 190, 225),
                         _dial_pt(a, dial_r - (11 if major else 7)),
                         _dial_pt(a, dial_r - 3),
                         2 if major else 1)
    # 22:00 deadline notch: the minute hand reaching the 12 ends the slice.
    pygame.draw.line(panel, (235, 70, 60, 255),
                     _dial_pt(math.radians(-90), dial_r - 12),
                     _dial_pt(math.radians(-90), dial_r - 2), 3)
    # Remaining-time ring: full at spawn, drains to the notch by 22:00.
    pygame.draw.circle(panel, (52, 52, 58, 200), (cx, cy), ring_r, 3)
    if failed:
        pygame.draw.circle(panel, (*col, 235), (cx, cy), ring_r, 3)
    else:
        frac = max(0.0, min(1.0, left / float(BCAST_TIME_LIMIT)))
        steps = max(2, int(60 * frac))
        arc = [_dial_pt(math.radians(-90 + 360.0 * frac * i / steps), ring_r)
               for i in range(steps + 1)]
        if urgent:
            pulse = 0.5 + 0.5 * math.sin(_now_s() * 6.0)
            ring_col = (col[0], col[1], col[2], int(150 + 105 * pulse))
        else:
            ring_col = (*col, 235)
        pygame.draw.lines(panel, ring_col, False, arc, 3)
    # Hands: thin sweep, bold minute hand toward the notch, short hour hand.
    pygame.draw.line(panel, (205, 92, 80, 210), (cx, cy),
                     _dial_pt(sec_ang, dial_r - 6), 1)
    pygame.draw.line(panel, (*col, 245), (cx, cy),
                     _dial_pt(min_ang, dial_r - 8), 2)
    pygame.draw.line(panel, (205, 226, 216, 240), (cx, cy),
                     _dial_pt(hour_ang, dial_r * 0.55), 3)
    pygame.draw.circle(panel, (205, 226, 216, 245), (cx, cy), 3)
    pygame.draw.circle(panel, (10, 8, 10, 255), (cx, cy), 3, 1)
    panel.blit(body_surf, ((box_w - body_surf.get_width()) // 2,
                           6 + head_surf.get_height() + 4 + 2 * ring_r + 4))

    mm = getattr(STATE, "minimap", None)
    if mm is not None:
        px = mm.x + mm.minimap_w - box_w
        py = mm.y + mm.minimap_h + 12
    else:
        px, py = WIDTH - box_w - 16, 196
    px = max(8, min(px, WIDTH - box_w - 8))
    py = max(8, min(py, HEIGHT - box_h - 8))
    surface.blit(panel, (px, py))


def _draw_comms_step_arrow(cam_x, cam_y):
    """One off-screen edge arrow, pointing at the CURRENT checklist step only.

    Silent while the station is on screen (its world label is enough), so the
    player is pulled to one object at a time instead of everything at once.
    """
    if getattr(STATE, "mission3_stage", None) != STAGE_COMMS:
        return
    if STATE.player is None or getattr(STATE, "m3_relay_tuned", False):
        return
    if not getattr(STATE, "m3_comms_power_restored", False):
        wx, wy = _comms_breaker_pos()
    elif not getattr(STATE, "m3_comms_auth_acquired", False):
        wx, wy = _comms_auth_pos()
    else:
        wx, wy = _relay_pos()
    sx, sy = wx - cam_x, wy - cam_y
    m = 64
    if m <= sx <= WIDTH - m and m <= sy <= HEIGHT - m:
        return
    cx = min(max(sx, m), WIDTH - m)
    cy = min(max(sy, m), HEIGHT - m)
    ang = math.atan2(sy - cy, sx - cx)
    pts = [(cx + math.cos(ang) * 15, cy + math.sin(ang) * 15),
           (cx + math.cos(ang + 2.5) * 9, cy + math.sin(ang + 2.5) * 9),
           (cx + math.cos(ang - 2.5) * 9, cy + math.sin(ang - 2.5) * 9)]
    pulse = 170 + int(60 * math.sin(_now_s() * 5.0))
    pygame.draw.polygon(screen, (255, 200, 90), pts)
    pygame.draw.polygon(screen, (pulse, pulse // 2, 40), pts, 1)


def _draw_m3_mag_icon(surface, mx, my, kind, rounds, cap, is_active):
    """M3 magazine icon painter (K-9 straight 24-round stick / sidearm box mag).

    Extracted verbatim from ``_draw_mission3_hud`` (Phase 4) so the shared
    ``engine.ui.std`` weapon panel can draw M3's icon language; ``rounds`` /
    ``cap`` / ``is_active`` come from the panel. These are the shapes the M4/M5
    panels were ported from; the state mapping is:

        active   -> rounds = ammo in the chambered mag   (empty at 0)
        spare    -> rounds = mag size, 0 past the spares  (empty when 0)
    """
    if kind == "stick":
        # K-9 uses straight 24-round stick mags, not chunky pistol mags.
        mag_w, mag_h = 14, 52
        rounds = max(0, min(24, rounds))
        is_empty = (rounds <= 0)
        body = pygame.Rect(mx + 5, my, mag_w, mag_h)
        if is_empty:
            base, rim, hi = (24, 28, 28), (52, 62, 58), (36, 42, 40)
        elif is_active:
            base, rim, hi = (36, 48, 44), (120, 230, 180), (70, 92, 84)
        else:
            base, rim, hi = (32, 38, 36), (86, 112, 102), (54, 66, 62)
        # Slight perspective taper.
        mag_poly = [
            (body.x + 1, body.y), (body.right - 1, body.y + 1),
            (body.right - 3, body.bottom), (body.x + 3, body.bottom)
        ]
        pygame.draw.polygon(surface, base, mag_poly)
        pygame.draw.polygon(surface, rim if is_active else (64, 70, 66), mag_poly, 1)
        pygame.draw.line(surface, hi, (body.x + 4, body.y + 4), (body.x + 5, body.bottom - 5), 1)
        # Feed lips / base plate.
        pygame.draw.rect(surface, (80, 86, 78), (body.x + 2, body.y - 3, mag_w - 2, 4),
                         border_radius=1)
        pygame.draw.rect(surface, (18, 20, 20), (body.x + 1, body.bottom - 4, mag_w - 1, 5),
                         border_radius=1)
        # 24-round witness holes: two columns, 12 rows.
        filled_rows = int(round(rounds / 2.0))
        for row_i in range(12):
            wy = body.bottom - 8 - row_i * 3
            row_filled = row_i < filled_rows
            for col_i, wx_off in enumerate((5, 9)):
                wx = body.x + wx_off
                if row_filled:
                    col = (220, 190, 70) if is_active else (150, 128, 58)
                else:
                    col = (18, 20, 20)
                pygame.draw.circle(surface, col, (wx, wy), 1)
        # Small active-mag accent stripe.
        if is_active:
            pygame.draw.line(surface, (120, 230, 180), (body.right + 3, body.y + 4),
                             (body.right + 3, body.bottom - 4), 2)
    else:
        bullets_fill = min(rounds, 12)
        is_empty = (rounds <= 0)

        top_w, bot_w, h = 24, 20, 46
        taper = (top_w - bot_w) // 2
        body_pts = [(mx, my), (mx + top_w, my),
                    (mx + taper + bot_w, my + h), (mx + taper, my + h)]

        if is_empty:
            base, hl, rim = (45, 42, 38), (55, 52, 48), (55, 50, 45)
        elif is_active:
            base, hl, rim = (90, 86, 78), (115, 110, 100), (70, 66, 58)
        else:
            base, hl, rim = (72, 68, 62), (92, 88, 80), (60, 56, 50)

        pygame.draw.polygon(surface, base, body_pts)
        pygame.draw.polygon(surface, hl, [
            (mx + 1, my + 2), (mx + 5, my + 2),
            (mx + taper + 3, my + h - 3), (mx + taper + 1, my + h - 3)])
        pygame.draw.polygon(surface, C_TERMINAL if is_active else rim, body_pts, 1)

        gold = (220, 185, 45)
        dark = (55, 52, 48) if not is_empty else (40, 38, 35)
        for bi in range(12):
            col = gold if bi < bullets_fill else dark
            pygame.draw.circle(surface, col, (mx + top_w // 2, my + 8 + bi * 3), 2)


def _draw_mission3_hud(surface, cam_x, cam_y):
    """Mission 3 gameplay HUD. No molotov counter for this mission."""
    draw_objective_panel(surface, _m3_maps._objective)

    draw_pinned_radio(surface)

    _draw_comms_checklist(surface)
    _draw_broadcast_address_clock(surface)
    _draw_comms_step_arrow(cam_x, cam_y)

    if not STATE.player:
        return

    if getattr(STATE, "mission3_stage", STAGE_INTERROGATION) == STAGE_INTERROGATION:
        return

    unified_x = 24
    weapon = getattr(STATE, "mission3_weapon", "none")
    has_firearm = (weapon in ("sidearm", "k9_smg")
                   and not getattr(STATE, "player_disarmed", False))

    # ── HP Bar (shared engine.ui.std widget, Phase 4) ──
    _hud_health_bar.draw(surface, THEME, STATE.player.hp, STATE.player.max_hp,
                         panel_bg=get_panel_bg)

    # ── Weapon / Ammo Panel (sits directly above HP bar, no molotov gap) ──
    if has_firearm:
        # Phase 4: the panel body is the shared engine.ui.std weapon_panel; M3
        # keeps its own magazine language (_draw_m3_mag_icon: trapezoid stick /
        # box mags with witness holes) and its 92px panel height as arguments.
        if weapon == "k9_smg":
            _m3_info = _hud_weapon_panel.WeaponInfo(
                cw="k9_smg", label="K-9 SMG", caliber="9MM-S", kind="stick",
                ammo=getattr(STATE, "k9_ammo_in_mag", 0),
                mag=getattr(STATE, "k9_mag_size", 24),
                spares=getattr(STATE, "k9_spare_mags", 0))
        else:
            _m3_info = _hud_weapon_panel.WeaponInfo(
                cw="pistol", label="SIDEARM", caliber="9MM", kind="box",
                ammo=STATE.ammo_in_mag, mag=STATE.mag_size, spares=STATE.spare_mags)
        _m3_info.reloading = bool(STATE.is_reloading)
        _m3_info.reload_timer = STATE.reload_timer
        _hud_weapon_panel.draw(surface, THEME, _m3_info, panel_bg=get_panel_bg,
                               mag_icon=_draw_m3_mag_icon, panel_h=92,
                               reload_label_dx=2)
    else:
        panel_h = 74
        panel_y = HEIGHT - 40 - panel_h - 2
        bg = get_panel_bg(246, panel_h)
        surface.blit(bg, (unified_x, panel_y))
        pygame.draw.line(surface, C_KRAP_BLUE,
                         (unified_x, panel_y), (unified_x, panel_y + panel_h), 3)
        _draw_m3_weapon_icon(surface, unified_x + 20, panel_y + 34, weapon)

        if weapon == "chair_leg":
            label, sub, col = "CHAIR LEG", "BLUNT IMPROVISED", (200, 170, 115)
        elif weapon == "shiv":
            label, sub, col = "SHIV", "CLOSE-RANGE BLADE", (155, 205, 210)
        else:
            label, sub, col = "RESTRAINED", "NO WEAPON", (170, 95, 85)

        surface.blit(font_terminal.render(label, True, col), (unified_x + 70, panel_y + 12))
        surface.blit(font_terminal_small.render(sub, True, (120, 130, 125)),
                     (unified_x + 70, panel_y + 35))
        if weapon != "none":
            surface.blit(font_terminal_small.render(_T("m3.v_attack"), True, (150, 160, 150)),
                         (unified_x + 70, panel_y + 53))

    # ── Hostiles counter (shared engine.ui.std widget, Phase 4) ──
    _hud_hostiles.draw(surface, THEME, len(STATE.enemies))

    # ── Minimap ──
    if STATE.show_minimap and STATE.minimap:
        drain_marker = None
        if weapon == "chair_leg":
            drain_marker = (_DRAIN_TILE_COL * TILE_SIZE + TILE_SIZE // 2,
                            _DRAIN_TILE_ROW * TILE_SIZE + TILE_SIZE // 2)
        # After all cell-block guards are dead, mark the service door + draw a
        # directional arrow. The K-9 stand is marked (cyan) until taken.
        # Both markers live on the cell-block map, so hide them once the player
        # live on the cell-block map only - hide on Comms/Archives/later stages.
        service_door_marker = None
        smg_marker = None
        if getattr(STATE, "mission3_stage", "") in (
                STAGE_INTERROGATION, STAGE_BREAKOUT, STAGE_VENT_CUTSCENE):
            if getattr(STATE, "m3_guards_all_killed", False):
                service_door_marker = (_EXIT_TILE_COL * TILE_SIZE + TILE_SIZE // 2,
                                       _EXIT_TILE_ROW * TILE_SIZE + TILE_SIZE // 2)
            if not getattr(STATE, "k9_unlocked", False):
                smg_marker = (_K9_STAND_COL * TILE_SIZE + TILE_SIZE // 2,
                              _K9_STAND_ROW * TILE_SIZE + TILE_SIZE // 2)
        STATE.minimap.draw(surface, STATE.player, STATE.enemies, cam_x, cam_y,
                           notebook_pos=drain_marker,
                           service_door_pos=service_door_marker,
                           smg_pos=smg_marker)

def _update_weapon_timers():
    """Tick down weapon cooldowns, reloads, and weapon-swap timers for Mission 3."""

    if STATE.shot_cooldown > 0:
        STATE.shot_cooldown -= 1

    if getattr(STATE, "os12_shot_cooldown", 0) > 0:
        STATE.os12_shot_cooldown -= 1

    if getattr(STATE, "k9_shot_cooldown", 0) > 0:
        STATE.k9_shot_cooldown -= 1

    if STATE.is_reloading:
        STATE.reload_timer -= 1
        if STATE.reload_timer <= 0:
            STATE.is_reloading = False

            current_weapon = getattr(STATE, "current_weapon", "pistol")
            is_os12 = current_weapon == "os12"
            is_k9 = current_weapon == "k9_smg"

            if is_os12:
                if STATE.os12_spare_mags > 0:
                    STATE.os12_spare_mags -= 1
                    STATE.os12_ammo_in_mag = STATE.os12_mag_size
            elif is_k9:
                if getattr(STATE, "k9_spare_mags", 0) > 0:
                    STATE.k9_spare_mags -= 1
                    STATE.k9_ammo_in_mag = STATE.k9_mag_size
            else:
                if STATE.spare_mags > 0:
                    STATE.spare_mags -= 1
                    STATE.ammo_in_mag = STATE.mag_size

    if getattr(STATE, "weapon_swap_timer", 0) > 0:
        STATE.weapon_swap_timer -= 1

        duration = getattr(STATE, "weapon_swap_duration", 24)
        midpoint = duration // 2

        if (
            STATE.weapon_swap_timer <= midpoint
            and not getattr(STATE, "weapon_swap_sound_played", False)
            and getattr(STATE, "weapon_swap_pending", None) is not None
        ):
            STATE.current_weapon = STATE.weapon_swap_pending
            # Keep the M3 weapon enum in sync so HUD icon / fire gates match
            # the carried gun (pistol <-> K-9 swap).
            if STATE.current_weapon == "pistol":
                STATE.mission3_weapon = "sidearm"
            elif STATE.current_weapon == "k9_smg":
                STATE.mission3_weapon = "k9_smg"
            audio.play("rifle_handle", volume=0.35)
            STATE.weapon_swap_sound_played = True

        if STATE.weapon_swap_timer <= 0:
            STATE.weapon_swap_pending = None
            STATE.weapon_swap_sound_played = False


def _update_doors():
    """Update Mission 3 doors like Mission 1 doors."""
    if not STATE.player:
        return
    for d in getattr(STATE, "doors", []):
        d.update(STATE.player.rect, getattr(STATE, "enemies", []))


def _m3_volkov_navigation_walls(solid_walls):
    """Return obstacles for route planning, treating unlocked doors as routes.

    Closed unlocked doors still block movement for a few animation frames, but
    Volkov opens them when he approaches. If their temporary collision panels
    are included in A*, he concludes that the doorway itself is impassable and
    either takes a ridiculous detour or never enters the room.
    """
    passable_door_rects = {
        id(d.collision_rect)
        for d in getattr(STATE, "doors", [])
        if not getattr(d, "locked", False)
        and getattr(d, "collision_rect", None) is not None
    }
    return [w for w in solid_walls if id(w) not in passable_door_rects]


def _m3_volkov_segment_clear(x1, y1, x2, y2, walls, padding=13):
    """Body-width line-of-travel test, not a zero-width LOS ray."""
    for wall in walls:
        if wall.inflate(padding * 2, padding * 2).clipline((x1, y1), (x2, y2)):
            return False
    return True


def _m3_volkov_build_grid(walls):
    """Build an actor-clearance grid for the 24px-wide ally.

    Unlike the generic enemy grid, this marks every tile touched by wide prop
    rectangles and inflates obstacles by Volkov's body radius. That prevents
    paths through server racks, console corners, and decorative barriers.
    """
    grid = [[True for _ in range(MAP_W)] for _ in range(MAP_H)]
    half = 13
    for wall in walls:
        expanded = wall.inflate(half * 2, half * 2)
        min_col = max(0, int((expanded.left - TILE_SIZE / 2) // TILE_SIZE))
        max_col = min(MAP_W - 1, int((expanded.right - TILE_SIZE / 2) // TILE_SIZE))
        min_row = max(0, int((expanded.top - TILE_SIZE / 2) // TILE_SIZE))
        max_row = min(MAP_H - 1, int((expanded.bottom - TILE_SIZE / 2) // TILE_SIZE))
        for row in range(min_row, max_row + 1):
            cy = row * TILE_SIZE + TILE_SIZE // 2
            for col in range(min_col, max_col + 1):
                cx = col * TILE_SIZE + TILE_SIZE // 2
                if expanded.collidepoint(cx, cy):
                    grid[row][col] = False
    return grid


def _m3_volkov_repath(vx, vy, target_x, target_y, walls):
    grid = _m3_volkov_build_grid(walls)
    start = (int(vx // TILE_SIZE), int(vy // TILE_SIZE))
    goal = (int(target_x // TILE_SIZE), int(target_y // TILE_SIZE))

    # A prop, wall, or the actor's own body can overlap part of the tile he is
    # standing in - and the body-inflated grid can wall that tile in on all
    # sides. Clearing only the start tile is not enough: A* then has no legal
    # first step and returns no path at all (he stops moving forever). Open a
    # 3x3 around start and goal so an enclosed tile still connects outward.
    for tx, ty in (start, goal):
        for dy in (-1, 0, 1):
            for dx in (-1, 0, 1):
                gx, gy = tx + dx, ty + dy
                if 0 <= gx < MAP_W and 0 <= gy < MAP_H:
                    grid[gy][gx] = True

    path = _astar(start, goal, grid)
    return [(col * TILE_SIZE + TILE_SIZE // 2,
             row * TILE_SIZE + TILE_SIZE // 2) for col, row in path]


def _m3_volkov_move(vx, vy, move_x, move_y, solid_walls):
    """Collision-safe axis movement with clean wall sliding."""
    global _volkov_step_timer
    actor = pygame.Rect(0, 0, 24, 24)
    actor.center = (round(vx), round(vy))

    actor.x += round(move_x)
    for wall in solid_walls:
        if actor.colliderect(wall):
            if move_x > 0:
                actor.right = wall.left
            elif move_x < 0:
                actor.left = wall.right

    actor.y += round(move_y)
    for wall in solid_walls:
        if actor.colliderect(wall):
            if move_y > 0:
                actor.bottom = wall.top
            elif move_y < 0:
                actor.top = wall.bottom

    # ── Volkov's boots: positional, heavier than the player's ──
    moved = math.hypot(actor.centerx - round(vx), actor.centery - round(vy))
    if moved > 0.5 and STATE.player is not None:
        _volkov_step_timer -= moved
        if _volkov_step_timer <= 0:
            audio.play_3d(
                "volkov_step",
                (actor.centerx, actor.centery),
                (STATE.player.rect.centerx, STATE.player.rect.centery),
                max_dist=620,
                base_volume=0.60,
            )
            _volkov_step_timer = 38.0 + _rng_legacy.randint(0, 6)
    elif moved <= 0.5:
        _volkov_step_timer = min(_volkov_step_timer, 8.0)

    return float(actor.centerx), float(actor.centery)


def _update_volkov_ally(solid_walls):
    """Temporary ally AI for the Comms Wing with real A* navigation.

    Volkov follows Biribel loosely and fires at guards he can actually see.
    It is intentionally simple: no escort fail state, no minimap marker, no
    friendly collision. He helps, but the player still owns the fight.
    """
    if not getattr(STATE, "m3_volkov_ally_active", False):
        return
    if getattr(STATE, "m3_volkov_ally_hp", 0) <= 0:
        STATE.m3_volkov_ally_active = False
        return
    bail_t = getattr(STATE, "m3_volkov_bail_timer", 0)
    if bail_t > 0:
        # Slice 5c bail branch: Volkov walks back up the stairwell over
        # ~3s, then despawns (covering fire lost for the holdout).
        STATE.m3_volkov_bail_timer = bail_t - 1
        tx, ty = 6 * TILE_SIZE + 32, 4 * TILE_SIZE + 32
        vx = float(getattr(STATE, "m3_volkov_ally_x", STATE.player.rect.centerx - 48))
        vy = float(getattr(STATE, "m3_volkov_ally_y", STATE.player.rect.centery + 28))
        d = math.hypot(tx - vx, ty - vy)
        if d > 6:
            vx += (tx - vx) / d * 3.4
            vy += (ty - vy) / d * 3.4
        STATE.m3_volkov_ally_x, STATE.m3_volkov_ally_y = vx, vy
        if STATE.m3_volkov_bail_timer <= 0:
            STATE.m3_volkov_ally_active = False
        return
    if not STATE.player or STATE.player_dead:
        return
    if getattr(STATE, "mission3_stage", None) not in (STAGE_COMMS, STAGE_ARCHIVES, STAGE_KILL_ORDER, STAGE_BROADCAST):
        return
    if getattr(STATE, "m3_volkov_ally_hit_flash", 0) > 0:
        STATE.m3_volkov_ally_hit_flash -= 1

    vx = float(getattr(STATE, "m3_volkov_ally_x", STATE.player.rect.centerx - 48))
    vy = float(getattr(STATE, "m3_volkov_ally_y", STATE.player.rect.centery + 28))
    px, py = STATE.player.rect.centerx, STATE.player.rect.centery

    # Follow behind Biribel. Route planning uses unlocked doors as passable
    # links, body-width obstacle clearance, periodic A* refreshes, waypoint
    # smoothing, and stuck recovery. The old implementation only tried X then Y
    # against the nearest wall, so Volkov had no way to understand corners.
    follow_dist = 82
    target_x = px - math.cos(STATE.player.angle) * follow_dist
    target_y = py - math.sin(STATE.player.angle) * follow_dist
    dx = target_x - vx
    dy = target_y - vy
    dist = math.hypot(dx, dy)

    nav_walls = _m3_volkov_navigation_walls(solid_walls)
    direct_clear = _m3_volkov_segment_clear(
        vx, vy, target_x, target_y, nav_walls)
    goal_tile = (int(target_x // TILE_SIZE), int(target_y // TILE_SIZE))
    path = list(getattr(STATE, "m3_volkov_path", []))
    path_timer = max(0, int(getattr(STATE, "m3_volkov_path_timer", 0)) - 1)
    old_goal = getattr(STATE, "m3_volkov_path_goal", None)

    # Replan when the player enters another tile, periodically while blocked,
    # or immediately after stuck detection asks for a fresh route.
    if direct_clear:
        path = []
    elif path_timer <= 0 or old_goal != goal_tile or not path:
        path = _m3_volkov_repath(vx, vy, target_x, target_y, nav_walls)
        path_timer = 15
        STATE.m3_volkov_path_goal = goal_tile

    nav_x, nav_y = target_x, target_y
    if path:
        # Drop reached nodes.
        while path and math.hypot(path[0][0] - vx, path[0][1] - vy) < 24:
            path.pop(0)

        if path:
            # Path smoothing: take the furthest currently reachable waypoint,
            # avoiding robotic tile-center zig-zags in open corridors.
            furthest = 0
            for i, waypoint in enumerate(path[:8]):
                if _m3_volkov_segment_clear(vx, vy, waypoint[0], waypoint[1], nav_walls):
                    furthest = i
                else:
                    break
            if furthest:
                path = path[furthest:]
            nav_x, nav_y = path[0]

    move_dx = nav_x - vx
    move_dy = nav_y - vy
    move_dist = math.hypot(move_dx, move_dy)
    if dist > 28 and move_dist > 1:
        step = min(3.05 * 60.0 * STATE.dt, move_dist)
        move_x = move_dx / move_dist * step
        move_y = move_dy / move_dist * step
        vx, vy = _m3_volkov_move(vx, vy, move_x, move_y, solid_walls)

    # Stuck recovery is based on real displacement, not intended velocity.
    last_x, last_y = getattr(STATE, "m3_volkov_last_pos", (vx, vy))
    moved = math.hypot(vx - last_x, vy - last_y)
    stuck = int(getattr(STATE, "m3_volkov_stuck_timer", 0))
    if dist > 64 and moved < 0.35:
        stuck += 1
    else:
        stuck = 0
    if stuck >= 18:
        path = []
        path_timer = 0
        stuck = 0

    STATE.m3_volkov_path = path
    STATE.m3_volkov_path_timer = path_timer
    STATE.m3_volkov_stuck_timer = stuck
    STATE.m3_volkov_last_pos = (vx, vy)

    # Volkov can open non-locked doors near him. Doors use the same target_open
    # / manual_timer logic as player doors, so they animate instead of popping.
    for door in getattr(STATE, "doors", []):
        if getattr(door, "locked", False):
            continue
        if getattr(door, "collision_disabled", False):
            continue
        if math.hypot(door.rect.centerx - vx, door.rect.centery - vy) <= TILE_SIZE * 1.15:
            door.target_open = True
            door.manual_timer = max(getattr(door, "manual_timer", 0), 55)

    # Find nearest visible guard.
    target = None
    best = 999999.0
    for e in getattr(STATE, "enemies", []):
        if e.hp <= 0:
            continue
        ex, ey = e.rect.centerx, e.rect.centery
        d = math.hypot(ex - vx, ey - vy)
        if d < best and d < 620 and not _wall_blocks_line(vx, vy, ex, ey, solid_walls):
            best = d
            target = e

    if target is not None:
        angle = math.atan2(target.rect.centery - vy, target.rect.centerx - vx)
        STATE.m3_volkov_ally_angle = angle
        cd = max(0, int(getattr(STATE, "m3_volkov_ally_cooldown", 0)) - 1)
        if cd <= 0:
            # Fire a real bullet using the same pipeline as the player instead
            # of directly subtracting HP. This gives Volkov the same tracer,
            # wall collision, impact, casing, and timing behavior.
            spread = _rng_legacy.uniform(-0.035, 0.035)
            shot_a = angle + spread
            # Match the lifted gun sprite: muzzle comes from chest-height,
            # not from the sprite center/belt.
            muzzle_x = vx + math.cos(angle) * 44
            muzzle_y = vy - 7 + math.sin(angle) * 44
            STATE.bullets.append({
                "x": muzzle_x,
                "y": muzzle_y,
                "prev_x": muzzle_x,
                "prev_y": muzzle_y,
                "dx": math.cos(shot_a) * 24,
                "dy": math.sin(shot_a) * 24,
                "life": 20,
                "owner": "player",
                "damage": 28,
                "volkov": True,
            })
            try:
                STATE.casings.append(Casing(
                    vx + math.cos(angle) * 8 + math.cos(angle - math.pi / 2) * 10,
                    vy + math.sin(angle) * 8 + math.sin(angle - math.pi / 2) * 10,
                    angle - math.pi / 2,
                ))
            except Exception:
                pass
            target.alerted = True
            target.last_seen_pos = (px, py)
            STATE.m3_volkov_ally_shots.append([muzzle_x, muzzle_y, target.rect.centerx, target.rect.centery, 5])
            STATE.particles.append(Particle(muzzle_x, muzzle_y, (255, 190, 90)))
            try:
                audio.play("gunshot_distant", volume=0.34)
            except Exception:
                pass
            cd = 32
        STATE.m3_volkov_ally_cooldown = cd
    else:
        if dist > 3:
            STATE.m3_volkov_ally_angle = math.atan2(dy, dx)
        STATE.m3_volkov_ally_cooldown = max(0, int(getattr(STATE, "m3_volkov_ally_cooldown", 0)) - 1)

    # Update tracer lifetimes.
    shots = []
    for shot in getattr(STATE, "m3_volkov_ally_shots", []):
        shot[4] -= 1
        if shot[4] > 0:
            shots.append(shot)
    STATE.m3_volkov_ally_shots = shots
    STATE.m3_volkov_ally_x = vx
    STATE.m3_volkov_ally_y = vy


def _draw_volkov_ally(cam_x, cam_y):
    from missions.m3.draw import _draw_volkov_in_game  # lazy: breaks systems<->draw cycle
    if not getattr(STATE, "m3_volkov_ally_active", False):
        return
    if getattr(STATE, "mission3_stage", None) not in (
            STAGE_COMMS, STAGE_ARCHIVES, STAGE_ARCHIVES_TRANSITION,
            STAGE_KILL_ORDER, STAGE_BROADCAST):
        return
    # Brief muzzle/tracer hint for Volkov's support shots. The actual projectile
    # is drawn by the normal bullet system; this is just a small firing cue.
    for x1, y1, x2, y2, life in getattr(STATE, "m3_volkov_ally_shots", []):
        sx1, sy1 = x1 - cam_x, y1 - cam_y
        sx2, sy2 = x2 - cam_x, y2 - cam_y
        pygame.draw.line(screen, (255, 190, 90), (sx1, sy1), (sx2, sy2), 1)
        pygame.draw.circle(screen, (255, 210, 120), (int(sx1), int(sy1)), max(1, life))
    vx = getattr(STATE, "m3_volkov_ally_x", 0.0) - cam_x
    vy = getattr(STATE, "m3_volkov_ally_y", 0.0) - cam_y
    angle = getattr(STATE, "m3_volkov_ally_angle", 0.0)
    _draw_volkov_in_game(screen, vx, vy, angle, kick_phase=0, charge_plant=0)



def game_update(keys):
    """Per-frame update. Returns (cam_x, cam_y) for acaristan's renderer."""
    _m3_maps._last_keys = keys
    # AEGIS Pass E: advance player i-frame timer + sprite blink every frame.
    # Mission 3 is interrogation/crafting-focused, but the player can still
    # take damage during the escape sequence - i-frames must apply uniformly
    # across the campaign so the player's damage-state expectations are
    # consistent.
    if STATE.player:
        STATE.player.update_iframes(STATE.dt)
    if STATE.gc_flash_timer > 0:
        STATE.gc_flash_timer -= 1
    # Corpses animate on every frame - including cinematic/death-anim
    # early-return paths below (they tick with slow-mo via the logic ticks).
    corpse.update_corpses()

    if _update_black_ledger_death():
        STATE._death_logic_ticks = 1
        effects.update_particles()
        effects.update_floating_texts()
        return _update_camera()

    if STATE.player and STATE.player.hp <= 0 and not STATE.player_dead:
        _stop_m3_alarm()
        from entities import death_anim
        death_anim.trigger_death()
    if STATE.player_dead:
        from entities import death_anim
        ticks = death_anim.update_death_anim()
        STATE._death_logic_ticks = ticks
    else:
        STATE._death_logic_ticks = 1

    if _update_chair_break_cutscene_state():
        effects.update_particles()
        effects.update_floating_texts()
        return _update_camera()

    # ── Station PC upload OS (Slice 6) ──
    # While the OS is open combat freezes and the 22:00 countdown holds
    # (this return skips _update_stage, which owns the timer): the terminal
    # session IS the upload gameplay. On DONE, hand off to the ending.
    from ui import upload_os  # lazy: ui package
    if upload_os.is_upload_os_active():
        upload_os.update_upload_os(keys, pygame.mouse.get_pos())
        if upload_os.is_upload_complete():
            upload_os.deactivate_upload_os()
            from missions.m3.flow import _complete_mission3  # lazy: breaks systems<->flow cycle
            _complete_mission3()
        effects.update_particles()
        effects.update_floating_texts()
        return _update_camera()

    _update_doors()
    solid_walls = _solid_walls()
    _update_player(keys, solid_walls)

    _update_mission3_melee(solid_walls)
    _update_weapon_timers()
    _update_volkov_ally(solid_walls)
    if (getattr(STATE, "current_weapon", "pistol") == "k9_smg"
            and not getattr(STATE, "mission3_crafting_active", False)
            and not getattr(STATE, "player_dead", False)):
        try:
            if pygame.mouse.get_pressed()[0]:
                from entities import weapons as _weapons
                _weapons.handle_shoot()
        except Exception:
            pass

    guards_active = _m3_guards_active()
    if guards_active:
        _update_m3_enemies(solid_walls)
        _update_m3_camera(solid_walls)
    _update_bullets(solid_walls)
    _update_black_ledger_inmate()
    if getattr(STATE, "m3_black_ledger_death_active", False):
        effects.update_particles()
        effects.update_floating_texts()
        return _update_camera()
    _update_m3_pickups()
    _update_comms_relay()
    _update_m3_detainees()
    effects.update_particles()
    effects.update_floating_texts()
    _update_stage(keys)
    _update_crafting()
    return _update_camera()


# ─────────────────────────────────────────────
# Slice 2 - enemy + pickup per-frame loops
# ─────────────────────────────────────────────
def _m3_guards_active():
    """True when Mission 3 guards should run combat/pathfinding.

    Guards used to activate during the Volkov breach/interrogation and pile up
    against Biribel's cell while the player was still locked in scripted beats.
    Freeze AI until the actual breakout is playable, and keep them held back
    while the mandatory chair-leg crafting lock is active (Volkov is holding
    the doorway in-fiction).
    """
    stage = getattr(STATE, "mission3_stage", STAGE_INTERROGATION)
    if stage in (STAGE_INTERROGATION, STAGE_VENT_CUTSCENE, STAGE_DONE):
        return False
    if (stage == STAGE_BREAKOUT
            and getattr(STATE, "mission3_doorway_blocked", False)
            and getattr(STATE, "mission3_weapon", "none") == "chair_leg"):
        return False
    return True


def _m3_enemy_has_strict_los(enemy, px, py, solid_walls):
    """Mission 3 tactical LOS: center-to-center only.

    The shared Enemy._can_see() samples several points around the player so AI
    does not forget targets on tiny corner clips in open maps. In this tight
    prison layout that felt like guards were seeing through cell/room walls.
    Mission 3 uses stricter center-line visibility for detection and shooting.
    """
    return _m3_enemy_has_los_to_point(enemy, px, py, solid_walls)


def _m3_enemy_has_los_to_point(enemy, tx, ty, solid_walls):
    if not enemy:
        return False
    ex, ey = enemy.rect.centerx, enemy.rect.centery
    dist = math.hypot(tx - ex, ty - ey)
    aware = getattr(enemy, "alerted", False) or getattr(enemy, "combat_alert_timer", 0) > 0
    max_range = ENEMY_DETECT_RANGE * (2.0 if aware else 1.05)
    if dist > max_range:
        return False
    return not _wall_blocks_line(ex, ey, tx, ty, solid_walls)


def _m3_volkov_target_pos():
    if not getattr(STATE, "m3_volkov_ally_active", False):
        return None
    if getattr(STATE, "mission3_stage", None) not in (STAGE_COMMS, STAGE_ARCHIVES, STAGE_BROADCAST):
        return None
    if getattr(STATE, "m3_volkov_ally_hp", 0) <= 0:
        return None
    return (float(getattr(STATE, "m3_volkov_ally_x", 0.0)),
            float(getattr(STATE, "m3_volkov_ally_y", 0.0)))


def _m3_choose_enemy_target(enemy, player_x, player_y, solid_walls):
    """Pick whether this guard targets Biribel or Volkov.

    If both are visible, guards split their attention roughly 50/50 and keep the
    choice for a short window to avoid jitter. If only one target is visible,
    use that target. If neither is visible, fall back to last-known behavior.
    """
    if getattr(STATE, "mission3_stage", None) == STAGE_KILL_ORDER:
        # Slice 5b: fireteam formation targets while the sweep hunts the
        # player's last-seen position (docs/MISSION3_KILL_ORDER.md §3).
        stx = getattr(STATE, "m3_sweep", None)
        if (stx is not None
                and stx["overwatch"].get("uid") == getattr(enemy, "uid", None)
                and not stx.get("committed")):
            # The mezzanine marksman is pinned by sweep._update_overwatch -
            # feeding him any target here starts a chase-fight over his
            # rect and makes the sniper wander/jitter.
            return "none", -99999, -99999, False
        # A member with a live strict-LOS sightline engages normally; only
        # the blind remainder keeps the formation advance (so the whole
        # fireteam pushes, not just the leader, but they DO shoot at you
        # the moment the line finds you).
        from missions.m3 import sweep as _ko_sweep
        if not _m3_enemy_has_los_to_point(enemy, player_x, player_y, solid_walls):
            ov = _ko_sweep.coord_target(enemy, player_x, player_y, solid_walls)
            if ov is not None:
                return ov
    player_visible = _m3_enemy_has_los_to_point(enemy, player_x, player_y, solid_walls)
    if _m3g(enemy).always_alert:
        # Broadcast Wing security: the PC is theirs, so Biribel's position is
        # never hidden from them. They never re-acquire-search either.
        _m3g(enemy).target_kind = "player"
        _m3g(enemy).target_timer = 0
        return "player", player_x, player_y, True
    volkov_pos = _m3_volkov_target_pos()
    volkov_visible = False
    if volkov_pos is not None:
        volkov_visible = _m3_enemy_has_los_to_point(enemy, volkov_pos[0], volkov_pos[1], solid_walls)

    # Keep current target briefly if still valid.
    timer = max(0, int(_m3g(enemy).target_timer) - 1)
    current = _m3g(enemy).target_kind
    if timer > 0:
        if current == "volkov" and volkov_visible:
            _m3g(enemy).target_timer = timer
            return "volkov", volkov_pos[0], volkov_pos[1], True
        if current == "player" and player_visible:
            _m3g(enemy).target_timer = timer
            return "player", player_x, player_y, True

    if player_visible and volkov_visible:
        # Stable-ish 50/50 split. Use random at retarget moments only.
        if _rng_legacy.random() < 0.5:
            _m3g(enemy).target_kind = "volkov"
            _m3g(enemy).target_timer = _rng_legacy.randint(35, 70)
            return "volkov", volkov_pos[0], volkov_pos[1], True
        _m3g(enemy).target_kind = "player"
        _m3g(enemy).target_timer = _rng_legacy.randint(35, 70)
        return "player", player_x, player_y, True
    if volkov_visible:
        _m3g(enemy).target_kind = "volkov"
        _m3g(enemy).target_timer = _rng_legacy.randint(30, 60)
        return "volkov", volkov_pos[0], volkov_pos[1], True
    if player_visible:
        _m3g(enemy).target_kind = "player"
        _m3g(enemy).target_timer = _rng_legacy.randint(30, 60)
        return "player", player_x, player_y, True

    # No current LOS. Continue toward last known target if alert/searching.
    last = getattr(enemy, "last_seen_pos", None)
    if last and (getattr(enemy, "alerted", False)
                 or getattr(enemy, "combat_alert_timer", 0) > 0
                 or getattr(enemy, "state", "") in ("CHASE", "ATTACK", "SEARCH")):
        return _m3g(enemy).target_kind, last[0], last[1], False
    return "none", -99999, -99999, False


def _m3_enemy_update_target(enemy, px, py, strict_can_see):
    """Target passed into the shared Enemy.update().

    If strict LOS says the player is hidden, do not feed the real player
    position into Enemy.update(), because its looser multi-point visibility can
    reacquire through corners/walls. Alerted guards instead act on last-known
    position; unaware guards get an off-map dummy point so they keep patrolling.
    """
    if strict_can_see:
        return px, py
    last = getattr(enemy, "last_seen_pos", None)
    if last and (getattr(enemy, "alerted", False)
                 or getattr(enemy, "combat_alert_timer", 0) > 0
                 or getattr(enemy, "state", "") in ("CHASE", "ATTACK", "SEARCH")):
        return last
    return (-99999, -99999)


def _update_m3_enemies(solid_walls):
    if not STATE.player or STATE.player_dead:
        return
    px, py = STATE.player.rect.centerx, STATE.player.rect.centery

    for e in STATE.enemies[:]:
        if e.hp > 0:
            target_kind, tx, ty, can_see = _m3_choose_enemy_target(e, px, py, solid_walls)

            if target_kind == "sweep":
                # Formation advance: the sweep point is NOT a visible contact,
                # but the enemy must physically march on it. The SEARCH branch
                # of Enemy.update never pathfinds toward a coordinate, so a
                # SEARCH sweep member would just stand and scan - the "they
                # don't know where I am" behavior. Force CHASE-on-the-point;
                # the director keeps the point moving as last-seen updates.
                e.state = "CHASE"
                e.last_seen_pos = (tx, ty)

            # Feed Enemy.update() the chosen target (Biribel or Volkov). If
            # neither is visible it receives last-known/dummy coordinates so
            # it cannot reacquire through walls.
            e.update(tx, ty, solid_walls, STATE.bullets, STATE.particles,
                     STATE.enemies, getattr(STATE, "fire_zones", []))

            # Re-evaluate LOS after movement.
            if target_kind == "volkov":
                vpos = _m3_volkov_target_pos()
                if vpos is not None:
                    tx, ty = vpos
                    can_see = _m3_enemy_has_los_to_point(e, tx, ty, solid_walls)
                else:
                    can_see = False
            elif target_kind == "player":
                tx, ty = px, py
                can_see = _m3_enemy_has_los_to_point(e, tx, ty, solid_walls)
            else:
                can_see = False

            dist = math.hypot(e.rect.centerx - tx, e.rect.centery - ty)

            if can_see:
                e.alerted = True
                e.combat_alert_timer = 420
                etype = (_m3l(e).kind or "guard")
                attack_range = _m3g(e).attack_range

                # Type identity beyond visuals:
                # - breachers rush close before firing
                # - marksmen hold longer sightlines and backpedal if rushed
                # - technicians alert the room once when they spot you
                if etype == "breacher" and dist > attack_range:
                    e.state = "CHASE"
                    e.last_seen_pos = (tx, ty)
                    e.speed = max(getattr(e, "speed", 1.4), 1.85)
                elif etype == "marksman" and dist < 150:
                    # Backpedal away from the current target while keeping aim.
                    away = math.atan2(e.rect.centery - ty, e.rect.centerx - tx)
                    e._apply_move(math.cos(away) * 1.8, math.sin(away) * 1.8, solid_walls)
                    e.state = "ATTACK"
                    e.last_seen_pos = (tx, ty)
                elif etype == "technician" and not _m3g(e).called_alert:
                    _m3g(e).called_alert = True
                    STATE.floating_texts.append([e.rect.centerx, e.rect.centery - 28, "CALLING IT IN", (90, 220, 150), 70])
                    for other in getattr(STATE, "enemies", []):
                        other.combat_alert_timer = max(getattr(other, "combat_alert_timer", 0), 300)
                        other.alerted = True
                    e.state = "ATTACK" if dist < attack_range else "CHASE"
                    e.last_seen_pos = (tx, ty)
                elif dist < attack_range:
                    e.state = "ATTACK"
                    e.last_seen_pos = (tx, ty)
                else:
                    e.state = "CHASE"
                    e.last_seen_pos = (tx, ty)
            elif e.state == "ATTACK":
                # Do not keep firing after LOS breaks.
                e.state = "CHASE" if getattr(e, "last_seen_pos", None) else "SEARCH"

            if e.state == "ATTACK" and can_see and e.fire_cooldown <= 0:
                spread = _rng_legacy.uniform(-_m3g(e).spread, _m3g(e).spread)
                shot_angle = math.atan2(ty - e.rect.centery, tx - e.rect.centerx)
                bx = e.rect.centerx + math.cos(shot_angle) * 18
                by = e.rect.centery + math.sin(shot_angle) * 18
                bullet_speed = _m3g(e).bullet_speed
                STATE.bullets.append({
                    "x": bx, "y": by,
                    "prev_x": bx, "prev_y": by,
                    "dx": math.cos(shot_angle + spread) * bullet_speed,
                    "dy": math.sin(shot_angle + spread) * bullet_speed,
                    "life": 62 if (_m3l(e).kind or "guard") == "marksman" else 50,
                    "owner": "enemy",
                    "damage": _m3g(e).damage,
                    "enemy_type": (_m3l(e).kind or "guard"),
                })
                e.fire_cooldown = _m3g(e).fire_cooldown
                try:
                    vol = 0.42 if (_m3l(e).kind or "guard") == "marksman" else 0.34
                    audio.play("gunshot_distant", volume=vol)
                except Exception:
                    pass

        if e.hp <= 0:
            STATE.hostiles_killed += 1
            STATE.mission3_guards_killed += 1
            STATE.blood_decals.append([
                e.rect.centerx, e.rect.centery, 165, _rng_legacy.randint(12, 22)])
            effects.burst(e.rect.centerx, e.rect.centery, C_BLOOD, 24)
            effects.shake(6)
            # Body topples, bleeds out, and fades instead of vanishing
            # on the death frame (entities/corpse.py).
            corpse.spawn_corpse(e)

            # FIRST-PISTOL GUARANTEE: the first guard killed in Mission 3 while
            # the player still lacks a firearm ALWAYS drops a usable sidearm
            # (pistol) - 100% of the time - so the player can never get stuck
            # with only the improvised melee weapon. This uses a dedicated
            # one-shot flag (not the kill counter) so scripted/other kills
            # can't consume the guarantee and leave the first real guard
            # dropping only a random mag.
            label = _m3l(e).text
            sidearm_pickup_already_spawned = any(
                len(pu) >= 3 and pu[2] == "sidearm"
                for pu in getattr(STATE, "pickups", [])
            )
            # v2: the guarantee no longer expires on the first drop and is not
            # voided by the K-9. While the player has never acquired the pistol,
            # EVERY guard kill drops that guard's sidearm (one on the ground at
            # a time) so a missed pickup can never leave the player pistol-less
            # and farming mags instead.
            first_pistol_pending = (
                not getattr(STATE, "mission3_sidearm_acquired", False)
                and not sidearm_pickup_already_spawned
            )
            if first_pistol_pending:
                STATE.mission3_first_pistol_dropped = True
                STATE.pickups.append([e.rect.centerx, e.rect.centery, "sidearm"])
                STATE.floating_texts.append([
                    e.rect.centerx, e.rect.centery - 18,
                    "GUARD SIDEARM DROPPED", (200, 185, 120), 60])
                # Guarantee one emergency bandage with the first pistol so the
                # player is never sent into the breakout with zero healing.
                if getattr(STATE, "mission3_bandages_spawned", 0) < 1:
                    STATE.mission3_bandages_spawned += 1
                    STATE.pickups.append([
                        e.rect.centerx + _rng_legacy.randint(-8, 8),
                        e.rect.centery + _rng_legacy.randint(-8, 8),
                        "bandage"])
            else:
                # Drop economy: after the guaranteed first sidearm, guards only
                # sometimes drop usable 9mm. Armory/exit guards have a slightly
                # better chance; extra 9mm drops are rare and capped so the
                # breakout doesn't turn into a loot piñata.
                mag_chance = 0.22 + (0.08 if label in ("guard_armory", "guard_exit_checkpoint") else 0.0)
                can_drop_extra_ammo = (
                    getattr(STATE, "mission3_sidearm_acquired", False)
                    or getattr(STATE, "k9_unlocked", False)
                )
                if (can_drop_extra_ammo
                        and getattr(STATE, "mission3_ammo_drops_spawned", 0) < 3
                        and _rng_legacy.random() < mag_chance):
                    STATE.mission3_ammo_drops_spawned += 1
                    STATE.pickups.append([e.rect.centerx, e.rect.centery, "sidearm"])

            # Bandages are scarce in M3 but now noticeably more reliable: up to
            # three emergency wraps per breakout slice.
            if (getattr(STATE, "mission3_bandages_spawned", 0) < 3
                    and _rng_legacy.random() < 0.22):
                STATE.mission3_bandages_spawned += 1
                STATE.pickups.append([
                    e.rect.centerx + _rng_legacy.randint(-8, 8),
                    e.rect.centery + _rng_legacy.randint(-8, 8),
                    "bandage"])
            try:
                audio.play("bullet_impact_enemy", volume=0.45)
            except Exception:
                pass
            STATE.enemies.remove(e)


def _m3_black_ledger_player_hit_count():
    return sum(1 for d in getattr(STATE, "mission3_detainees", [])
               if d.get("black_ledger_hit_by_player"))


def _m3_spawn_black_ledger_inmate():
    """Spawn the Black Ledger punishment entity.

    This is intentionally NOT a normal Enemy: it is unkillable, ignores normal
    hostile counts/drops, and owns a custom death animation.
    """
    if getattr(STATE, "m3_black_ledger_triggered", False):
        return

    STATE.m3_black_ledger_triggered = True
    STATE.m3_black_ledger_inmate_active = True
    STATE.m3_black_ledger_intro_timer = 210
    STATE.m3_alarm_active = True
    STATE.m3_alarm_timer = 0

    px = STATE.player.rect.centerx if STATE.player else _EXIT_TILE_COL * TILE_SIZE
    py = STATE.player.rect.centery if STATE.player else _EXIT_TILE_ROW * TILE_SIZE

    # Spawn away from the player but inside the authored cell-block footprint.
    candidates = [
        (_EXIT_TILE_COL * TILE_SIZE + TILE_SIZE // 2, _EXIT_TILE_ROW * TILE_SIZE + TILE_SIZE // 2),
        (28 * TILE_SIZE + TILE_SIZE // 2, 39 * TILE_SIZE + TILE_SIZE // 2),
        (10 * TILE_SIZE + TILE_SIZE // 2, 37 * TILE_SIZE + TILE_SIZE // 2),
        (_DOOR_TILE_COL * TILE_SIZE + TILE_SIZE // 2, (_DOOR_TILE_ROW + 2) * TILE_SIZE + TILE_SIZE // 2),
    ]
    sx, sy = max(candidates, key=lambda p: math.hypot(p[0] - px, p[1] - py))

    STATE.m3_black_ledger_inmate = {
        "x": float(sx),
        "y": float(sy),
        "angle": math.atan2(py - sy, px - sx),
        "timer": 0,
        "lunge_timer": 0,
        "footstep": 0,
    }

    _set_objective("SURVIVE THE BLACK LEDGER")
    STATE.floating_texts.append([
        px, py - 90,
        "BLACK LEDGER OPENED",
        (230, 70, 70),
        210,
    ])
    audio.play("pa_chime", volume=0.45)
    audio.schedule(40, "pa_mumble", volume=0.35)
    _radio("PA SYSTEM: Thirteen names closed. One name opened.",
           color=(230, 70, 70), duration=360, mark="black_ledger_opened")
    effects.shake(14)
    STATE.gc_flash_timer = max(getattr(STATE, "gc_flash_timer", 0), 10)
    try:
        audio.play("alarm", volume=0.55)
        audio.play("door_break", volume=0.45)
    except Exception:
        pass


def _m3_check_black_ledger_trigger():
    detainees = getattr(STATE, "mission3_detainees", [])
    if not detainees or getattr(STATE, "m3_black_ledger_triggered", False):
        return
    if _m3_black_ledger_player_hit_count() >= len(detainees):
        _m3_spawn_black_ledger_inmate()


def _trigger_black_ledger_death():
    if getattr(STATE, "m3_black_ledger_death_active", False):
        return
    STATE.m3_black_ledger_death_active = True
    STATE.m3_black_ledger_death_timer = 0
    STATE.player_dead = True
    STATE.request_death_screen = False
    STATE.death_timer = 120
    effects.shake(22)
    _set_objective("THE LEDGER COLLECTS")
    try:
        audio.play("door_break", volume=0.60)
        audio.play("bullet_impact_enemy", volume=0.50)
    except Exception:
        pass


def _update_black_ledger_death():
    if not getattr(STATE, "m3_black_ledger_death_active", False):
        return False
    STATE.m3_black_ledger_death_timer += 1
    t = STATE.m3_black_ledger_death_timer
    if t in (1, 24, 54, 88):
        effects.shake(18 if t < 54 else 10)
    # Hold the Black Ledger case-file result on-screen before handing off to
    # the interactive custom death screen. The old 150-frame handoff felt like
    # a hard cut; this gives the stamp/record time to land.
    if t >= 270:
        STATE.request_death_screen = True
    return True


def _update_black_ledger_inmate():
    if not getattr(STATE, "m3_black_ledger_inmate_active", False):
        return
    if getattr(STATE, "m3_black_ledger_death_active", False):
        return
    if not STATE.player or STATE.player_dead:
        return

    inmate = getattr(STATE, "m3_black_ledger_inmate", None)
    if not inmate:
        return

    inmate["timer"] = inmate.get("timer", 0) + 1
    STATE.m3_black_ledger_intro_timer = max(0, getattr(STATE, "m3_black_ledger_intro_timer", 0) - 1)

    px, py = STATE.player.rect.centerx, STATE.player.rect.centery
    dx = px - inmate["x"]
    dy = py - inmate["y"]
    dist = max(1.0, math.hypot(dx, dy))
    inmate["angle"] = math.atan2(dy, dx)

    # Faster than the player and allowed to force through geometry: this is a
    # supernatural punishment encounter, not a fair combatant.
    speed = 3.7 + min(2.2, inmate.get("timer", 0) / 360.0)
    if dist > 260:
        speed += 1.8
    if dist > 520:
        speed += 2.0
    if dist < 150:
        speed += 1.4
    inmate["x"] += (dx / dist) * speed * 60.0 * STATE.dt
    inmate["y"] += (dy / dist) * speed * 60.0 * STATE.dt

    inmate["footstep"] = inmate.get("footstep", 0) - 1
    if inmate["footstep"] <= 0:
        inmate["footstep"] = max(10, int(26 - min(10, inmate.get("timer", 0) / 80)))
        effects.shake(3 if dist > 220 else 7)
        try:
            audio.play_3d(
                f"enemy_footstep_{_rng_legacy.randint(1, 3)}",
                (inmate["x"], inmate["y"]),
                (STATE.player.rect.centerx, STATE.player.rect.centery),
                max_dist=560,
                base_volume=0.60 if dist < 360 else 0.38,
            )
        except Exception:
            pass

    if dist < 54:
        _trigger_black_ledger_death()


def _draw_black_ledger_inmate(cam_x, cam_y):
    if not getattr(STATE, "m3_black_ledger_inmate_active", False):
        return
    inmate = getattr(STATE, "m3_black_ledger_inmate", None)
    if not inmate:
        return

    sx = int(inmate["x"] - cam_x)
    sy = int(inmate["y"] - cam_y)
    t = inmate.get("timer", 0)
    stride = math.sin(t * 0.25)
    bob = int(math.sin(t * 0.13) * 2)

    # Screen-upright on purpose. The old version rotated the whole body toward
    # movement and read like a sideways bug. This keeps the silhouette readable
    # as a prisoner from every camera angle, like the other character sprites.
    outline = (22, 13, 8)
    suit = (168, 92, 34)          # dirty orange prison jumpsuit
    suit_dark = (92, 48, 24)
    suit_hi = (218, 132, 58)
    stripe = (228, 180, 86)
    skin = (156, 112, 82)
    skin_dark = (86, 54, 42)
    boot = (18, 15, 13)
    metal = (132, 134, 124)
    blood_mark = (110, 18, 18)

    # Heavy shadow + subtle alarm stain.
    shadow = pygame.Surface((132, 88), pygame.SRCALPHA)
    pygame.draw.ellipse(shadow, (0, 0, 0, 176), (8, 40, 116, 34))
    if getattr(STATE, "m3_alarm_active", False):
        pygame.draw.ellipse(shadow, (90, 0, 0, 30), (0, 18, 132, 58))
    screen.blit(shadow, (sx - 66, sy - 42))

    # Legs / boots. Big, upright, readable.
    for side, phase in [(-1, stride), (1, -stride)]:
        hip = (sx + side * 15, sy + 14 + bob)
        knee = (sx + side * 18, sy + 36 + bob + int(phase * 4))
        foot = (sx + side * 21, sy + 61 + bob + int(phase * 8))
        pygame.draw.line(screen, outline, hip, knee, 17)
        pygame.draw.line(screen, suit_dark, hip, knee, 12)
        pygame.draw.line(screen, outline, knee, foot, 16)
        pygame.draw.line(screen, suit, knee, foot, 11)
        pygame.draw.ellipse(screen, outline, (foot[0] - 13, foot[1] - 7, 26, 14))
        pygame.draw.ellipse(screen, boot, (foot[0] - 10, foot[1] - 5, 20, 10))

    # Torso: broad orange jumpsuit, shoulder-heavy.
    torso_outer = [
        (sx - 40, sy - 38 + bob), (sx - 24, sy - 58 + bob),
        (sx + 24, sy - 58 + bob), (sx + 40, sy - 38 + bob),
        (sx + 30, sy + 22 + bob), (sx - 30, sy + 22 + bob),
    ]
    pygame.draw.polygon(screen, outline, torso_outer)
    torso_inner = [
        (sx - 34, sy - 36 + bob), (sx - 20, sy - 52 + bob),
        (sx + 20, sy - 52 + bob), (sx + 34, sy - 36 + bob),
        (sx + 25, sy + 18 + bob), (sx - 25, sy + 18 + bob),
    ]
    pygame.draw.polygon(screen, suit, torso_inner)

    # Jumpsuit seams / stripes / zipper.
    pygame.draw.line(screen, suit_dark, (sx, sy - 51 + bob), (sx, sy + 17 + bob), 3)
    pygame.draw.line(screen, suit_hi, (sx - 25, sy - 39 + bob), (sx - 12, sy + 10 + bob), 2)
    pygame.draw.line(screen, suit_hi, (sx + 25, sy - 39 + bob), (sx + 12, sy + 10 + bob), 2)
    for xoff in (-19, 19):
        pygame.draw.line(screen, stripe, (sx + xoff, sy - 28 + bob), (sx + xoff, sy + 14 + bob), 2)

    # Chest inmate patch.
    patch = pygame.Rect(sx - 19, sy - 20 + bob, 38, 17)
    pygame.draw.rect(screen, (36, 22, 12), patch, border_radius=2)
    pygame.draw.rect(screen, (230, 170, 90), patch, 1, border_radius=2)
    num = font_terminal_small.render(_T("m3.000"), True, (245, 196, 112))
    screen.blit(num, (patch.centerx - num.get_width() // 2, patch.centery - num.get_height() // 2 - 1))

    # Arms: huge bare forearms/fists, screen-upright and prisoner-readable.
    cuffs = []
    for side, phase in [(-1, -stride), (1, stride)]:
        shoulder = (sx + side * 39, sy - 36 + bob)
        elbow = (sx + side * (53 + int(phase * 4)), sy - 6 + bob)
        hand = (sx + side * (55 + int(phase * 7)), sy + 24 + bob)
        pygame.draw.line(screen, outline, shoulder, elbow, 19)
        pygame.draw.line(screen, suit_dark, shoulder, elbow, 14)
        pygame.draw.line(screen, outline, elbow, hand, 18)
        pygame.draw.line(screen, skin_dark, elbow, hand, 13)
        pygame.draw.circle(screen, outline, hand, 14)
        pygame.draw.circle(screen, skin, hand, 11)
        pygame.draw.line(screen, skin_dark, (hand[0] - 7, hand[1] + 2), (hand[0] + 7, hand[1] + 2), 2)
        cuff = (sx + side * (52 + int(phase * 6)), sy + 11 + bob)
        pygame.draw.circle(screen, metal, cuff, 10, 2)
        cuffs.append(cuff)

    # Chain between cuffs, with small sag.
    if len(cuffs) == 2:
        c1, c2 = cuffs
        pygame.draw.line(screen, (38, 36, 34), c1, c2, 5)
        for i in range(7):
            q = i / 6
            cx = int(c1[0] * (1 - q) + c2[0] * q)
            cy = int(c1[1] * (1 - q) + c2[1] * q + 5 + math.sin(t * 0.2 + i) * 2)
            pygame.draw.ellipse(screen, metal, (cx - 4, cy - 3, 8, 6), 1)

    # Neck + shaved head. Human, upright, not hooded or monster-like.
    pygame.draw.circle(screen, outline, (sx, sy - 56 + bob), 18)
    pygame.draw.circle(screen, skin_dark, (sx, sy - 56 + bob), 14)
    pygame.draw.circle(screen, outline, (sx, sy - 82 + bob), 25)
    pygame.draw.circle(screen, skin, (sx, sy - 82 + bob), 21)
    pygame.draw.arc(screen, (54, 38, 30), (sx - 19, sy - 100 + bob, 38, 30), math.pi, math.tau, 5)
    pygame.draw.circle(screen, (34, 18, 14), (sx - 7, sy - 84 + bob), 2)
    pygame.draw.circle(screen, (34, 18, 14), (sx + 7, sy - 84 + bob), 2)
    pygame.draw.line(screen, (58, 26, 20), (sx - 9, sy - 73 + bob), (sx + 9, sy - 73 + bob), 2)

    # Small tally mark on jumpsuit: creepy, but still human/prisoner-coded.
    pygame.draw.line(screen, blood_mark, (sx + 9, sy - 44 + bob), (sx + 24, sy - 12 + bob), 3)

    # Restrained red rim light only, no monster aura.
    if getattr(STATE, "m3_alarm_active", False) and (t // 18) % 2 == 0:
        pygame.draw.arc(screen, (170, 34, 24), (sx - 48, sy - 100 + bob, 96, 132), -0.25, 0.95, 2)

    if getattr(STATE, "m3_black_ledger_intro_timer", 0) > 0:
        cap = font_terminal_small.render(_T("m3.cam_13_inmate_000_released"), True, (230, 98, 58))
        bg = pygame.Surface((cap.get_width() + 18, cap.get_height() + 8), pygame.SRCALPHA)
        bg.fill((0, 0, 0, 165))
        screen.blit(bg, (sx - bg.get_width() // 2, sy - 132))
        screen.blit(cap, (sx - cap.get_width() // 2, sy - 128))

def _draw_black_ledger_death_overlay():
    """Custom Black Ledger death screen.

    The previous pass became too much like an archive UI.  This version is a
    death screen first: one dominant symbol, one clear verdict, minimal context.
    The ledger still explains itself through faint tallies/entry text, but the
    screen is no longer a busy dossier table.
    """
    if not getattr(STATE, "m3_black_ledger_death_active", False):
        return

    t = getattr(STATE, "m3_black_ledger_death_timer", 0)
    rng = random.Random(99173 + t // 3)

    def clamp01(v):
        return max(0.0, min(1.0, v))

    def smooth(v):
        v = clamp01(v)
        return v * v * (3.0 - 2.0 * v)

    def draw_center(font, text, y, color, alpha=255, shadow=True):
        surf = font.render(text, True, color)
        surf.set_alpha(alpha)
        x = WIDTH // 2 - surf.get_width() // 2
        if shadow:
            sh = font.render(text, True, (0, 0, 0))
            sh.set_alpha(min(alpha, 190))
            screen.blit(sh, (x + 3, y + 3))
        screen.blit(surf, (x, y))
        return surf

    # ── Base death-screen field ────────────────────────────────────────────
    screen.fill((2, 1, 1))
    pulse = 0.5 + 0.5 * math.sin(t * 0.045)
    red = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
    red.fill((54, 3, 3, int(70 + 35 * pulse)))
    screen.blit(red, (0, 0))

    # Dirty static, but sparse - atmosphere, not information overload.
    for _ in range(18):
        y = rng.randrange(0, HEIGHT)
        a = rng.randrange(8, 30)
        pygame.draw.rect(screen, (150, 90, 70, a), (rng.randrange(-80, 70), y, WIDTH + 140, 1))
    for _ in range(42):
        x = rng.randrange(0, WIDTH)
        y = rng.randrange(0, HEIGHT)
        col = rng.choice([(50, 12, 10), (20, 8, 7), (80, 22, 18)])
        screen.set_at((x, y), col)

    # Early impact flash.
    if t < 18:
        a = max(0, 180 - t * 10)
        hit = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        hit.fill((180, 12, 8, a))
        screen.blit(hit, (0, 0))
        if t < 5:
            w = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
            w.fill((240, 222, 190, 92 - t * 15))
            screen.blit(w, (0, 0))

    # Vignette.
    vign = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
    for r, a in ((720, 12), (520, 34), (330, 58), (190, 44)):
        pygame.draw.circle(vign, (92, 8, 6, a), (WIDTH // 2, HEIGHT // 2), r)
    screen.blit(vign, (0, 0), special_flags=pygame.BLEND_ADD)
    draw_vignette(screen, strength=225)

    # ── Central ledger/book silhouette ─────────────────────────────────────
    appear = smooth((t - 18) / 36.0)
    book_w = int(520 * appear)
    book_h = int(330 * appear)
    book_x = WIDTH // 2 - book_w // 2
    book_y = HEIGHT // 2 - book_h // 2 - 26
    if appear > 0:
        # Book shadow.
        shadow = pygame.Surface((book_w + 60, book_h + 60), pygame.SRCALPHA)
        pygame.draw.ellipse(shadow, (0, 0, 0, 150), (15, book_h + 20, book_w + 30, 32))
        screen.blit(shadow, (book_x - 30, book_y - 30))

        # Left/right pages, slightly separated by spine.
        left = pygame.Rect(book_x, book_y, book_w // 2, book_h)
        right = pygame.Rect(book_x + book_w // 2, book_y, book_w // 2, book_h)
        pygame.draw.rect(screen, (145, 119, 84), left, border_radius=8)
        pygame.draw.rect(screen, (170, 143, 102), right, border_radius=8)
        pygame.draw.rect(screen, (44, 16, 12), (book_x + book_w // 2 - 8, book_y, 16, book_h), border_radius=4)
        pygame.draw.rect(screen, (72, 24, 18), (book_x, book_y, book_w, book_h), 4, border_radius=8)

        # Page grain and a few cracks, not rows of UI.
        # Guard against early open frames where book_w/book_h are still tiny;
        # otherwise randint(min, max) can receive an empty range.
        if book_w > 40 and book_h > 40:
            for _ in range(80):
                # Clamp the range so a too-narrow book can never produce an
                # empty randint(a, b) (a > b) on early open frames.
                gx = rng.randint(book_x + 12, max(book_x + 12, book_x + book_w - 12))
                gy = rng.randint(book_y + 12, max(book_y + 12, book_y + book_h - 12))
                if 0 <= gx < WIDTH and 0 <= gy < HEIGHT:
                    screen.set_at((gx, gy), rng.choice([(112, 84, 58), (194, 170, 124), (86, 55, 38)]))
        if book_w > 130 and book_h > 80:
            for _ in range(9):
                x1 = rng.randint(book_x + 22, max(book_x + 22, book_x + book_w - 80))
                y1 = rng.randint(book_y + 35, max(book_y + 35, book_y + book_h - 35))
                pygame.draw.line(screen, (83, 48, 34), (x1, y1), (x1 + rng.randint(30, 95), y1 + rng.randint(-6, 6)), 1)

        # Faint tally marks: the 13 detainees. They are symbolic now, not a full
        # spreadsheet. They fill quickly, then become background guilt.
        tally_count = min(13, max(0, int((t - 42) / 4)))
        start_x = book_x + 48
        start_y = book_y + 78
        for i in range(13):
            tx = start_x + (i % 7) * 24
            ty = start_y + (i // 7) * 48
            col = (92, 24, 18) if i < tally_count else (88, 66, 48)
            alpha = 210 if i < tally_count else 80
            mark = pygame.Surface((20, 34), pygame.SRCALPHA)
            pygame.draw.line(mark, (*col, alpha), (7, 2), (5, 30), 3)
            if i % 5 == 4:
                pygame.draw.line(mark, (*col, alpha), (1, 26), (17, 7), 2)
            screen.blit(mark, (tx, ty))

        # Entry 014: only the player name and the number matter.
        entry_p = smooth((t - 82) / 34.0)
        if entry_p > 0:
            entry = pygame.Rect(book_x + book_w // 2 + 34, book_y + 92, book_w // 2 - 68, 94)
            pygame.draw.rect(screen, (112, 82, 58), entry, border_radius=5)
            pygame.draw.rect(screen, (76, 28, 22), entry, 2, border_radius=5)
            num = font_terminal.render(_T("m3.014"), True, (43, 15, 11))
            num.set_alpha(int(255 * entry_p))
            screen.blit(num, (entry.x + 18, entry.y + 16))
            chars = max(0, min(len("BIRIBEL"), int((t - 88) / 5)))
            nm = "BIRIBEL"[:chars]
            cursor = "_" if chars < len("BIRIBEL") and (t // 9) % 2 == 0 else ""
            name = font_terminal.render(nm + cursor, True, (36, 12, 9))
            name.set_alpha(int(255 * entry_p))
            screen.blit(name, (entry.x + 88, entry.y + 16))
            cause = font_terminal_small.render(_T("m3.entry_generated_by_ledger_contac"), True, (80, 36, 28))
            cause.set_alpha(int(210 * entry_p))
            screen.blit(cause, (entry.x + 20, entry.y + 58))

        # Inmate 000 symbol: small, iconic, not a second whole UI panel.
        zero_p = smooth((t - 54) / 26.0)
        if zero_p > 0:
            mx, my = book_x + book_w // 2, book_y + 52
            pygame.draw.circle(screen, (8, 5, 4), (mx, my), int(26 * zero_p))
            pygame.draw.rect(screen, (12, 7, 5), (mx - int(32 * zero_p), my + int(19 * zero_p), int(64 * zero_p), int(35 * zero_p)), border_radius=10)
            z = font_terminal_small.render(_T("m3.000"), True, (188, 48, 38))
            z.set_alpha(int(230 * zero_p))
            screen.blit(z, (mx - z.get_width() // 2, my + 36))

    # ── Verdict text / death screen identity ───────────────────────────────
    title_p = smooth((t - 58) / 24.0)
    if title_p > 0:
        draw_center(font_terminal, "BLACK LEDGER", HEIGHT // 2 - 232, (166, 34, 28), int(235 * title_p))

    counted_p = smooth((t - 118) / 18.0)
    if counted_p > 0:
        # Big simple death message. This replaces the busy stamp/table climax.
        scale = 1.0 + (1.0 - counted_p) * 0.35
        txt = font_title.render(_T("m3.you_are_counted"), True, (158, 12, 10))
        if scale != 1.0:
            txt = pygame.transform.smoothscale(txt, (int(txt.get_width() * scale), int(txt.get_height() * scale)))
        txt.set_alpha(int(255 * counted_p))
        x = WIDTH // 2 - txt.get_width() // 2
        y = HEIGHT // 2 + 126 - txt.get_height() // 2
        sh = txt.copy()
        sh.fill((0, 0, 0, int(190 * counted_p)), special_flags=pygame.BLEND_RGBA_MULT)
        screen.blit(sh, (x + 4, y + 4))
        screen.blit(txt, (x, y))

    sub_p = smooth((t - 142) / 28.0)
    if sub_p > 0:
        draw_center(font_terminal_small, "ENTRY 014 / BIRIBEL / RECORD SEALED",
                    HEIGHT // 2 + 176, (174, 126, 98), int(220 * sub_p))

    # Make the late state feel like a death screen, not a transition screen.
    if t > 178:
        fade = min(130, int((t - 178) * 1.5))
        veil = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        veil.fill((0, 0, 0, fade))
        screen.blit(veil, (0, 0))
        draw_center(font_terminal, "BLACK LEDGER", HEIGHT // 2 - 54, (150, 34, 30), 240)
        draw_center(font_title, "YOU ARE COUNTED", HEIGHT // 2 - 12, (172, 18, 14), 255)
        draw_center(font_terminal_small, "ENTRY 014 / BIRIBEL / RECORD SEALED",
                    HEIGHT // 2 + 60, (156, 118, 96), 220)
        if t > 214:
            # This appears only once it is basically functioning as the custom
            # death screen. The actual restart/menu input is still handled by
            # the game's existing DEATH state after handoff.
            draw_center(font_terminal_small, "death record complete", HEIGHT - 58, (94, 68, 62), 170)

    # Minimal scanlines and occasional glitch.
    for y in range(0, HEIGHT, 4):
        pygame.draw.line(screen, (0, 0, 0, 35), (0, y), (WIDTH, y))
    if t % 10 in (0, 1):
        for _ in range(4):
            gy = rng.randint(0, HEIGHT - 1)
            pygame.draw.rect(screen, (220, 180, 150, rng.randint(12, 38)), (0, gy, WIDTH, 1))


def _m3_hit_detainee_with_bullet(b):
    """Return True if bullet hits an ambient detainee.

    Detainees are non-combat, but they are physical people in the space. Player
    or enemy bullets can hit them; they then become fallen bodies and stop
    speaking/animating. They are not enemies and do not affect hostiles count.
    """
    if b.get("owner") not in ("player", "enemy"):
        return False
    prev = (b.get("prev_x", b.get("x", 0)), b.get("prev_y", b.get("y", 0)))
    cur = (b.get("x", 0), b.get("y", 0))
    for d in getattr(STATE, "mission3_detainees", []):
        if d.get("dead"):
            continue
        wx, wy = _detainee_draw_pos(d)
        hitbox = pygame.Rect(int(wx - 17), int(wy - 24), 34, 46)
        if hitbox.clipline(prev, cur) or hitbox.collidepoint(cur):
            d["dead"] = True
            d["state"] = "dead"
            d["line_timer"] = 0
            STATE.blood_decals.append([wx, wy, 150, _rng_legacy.randint(7, 13)])
            effects.burst(wx, wy, C_BLOOD, 10)
            if b.get("owner") == "player":
                d["black_ledger_hit_by_player"] = True
                STATE.shots_hit += 1
                hit_count = _m3_black_ledger_player_hit_count()
                total = max(1, len(getattr(STATE, "mission3_detainees", [])))
                STATE.floating_texts.append([
                    wx, wy - 22,
                    f"DETAINEE HIT {hit_count}/{total}",
                    (220, 120, 95),
                    75,
                ])
                _m3_check_black_ledger_trigger()
            try:
                audio.play("bullet_impact_enemy", volume=0.36)
            except Exception:
                pass
            return True
    return False



def _update_bullets(solid_walls):
    """Move bullets, check player/wall collisions, remove expired.

    Mirrors mission2._update_bullets_enemies but simplified for M3:
    only enemy-to-player bullets matter (the player fires via weapons.py
    which handles its own collision). Enemy bullets must move, check the
    player hitbox, check walls, and expire.
    """
    if not STATE.player or STATE.player_dead:
        return
    px, py = STATE.player.rect.centerx, STATE.player.rect.centery
    for b in STATE.bullets[:]:
        b["prev_x"] = b["x"]
        b["prev_y"] = b["y"]
        _dt_mul = 60.0 * STATE.dt
        b["x"] += b["dx"] * _dt_mul
        b["y"] += b["dy"] * _dt_mul
        b["life"] -= 1
        hit = False
        # Enemy bullets vs player
        if b.get("owner") == "enemy" and not hit:
            if math.hypot(b["x"] - px, b["y"] - py) < 22:
                if STATE.player.take_damage(b.get("damage", ENEMY_DAMAGE)):
                    effects.shake(6)
                    effects.burst(b["x"], b["y"], C_BLOOD, 8)
                    STATE.gc_flash_timer = max(STATE.gc_flash_timer, 4)
                    try:
                        audio.play("bullet_impact_enemy", volume=0.5)
                    except Exception:
                        pass
                hit = True
        # Bullets vs ambient detainees (non-combat prisoners). They are not
        # enemies, but they are physical people in the world and can be hit.
        if not hit:
            hit = _m3_hit_detainee_with_bullet(b)
        # Enemy bullets vs Volkov ally
        if b.get("owner") == "enemy" and not hit and getattr(STATE, "m3_volkov_ally_active", False):
            if getattr(STATE, "mission3_stage", None) == STAGE_COMMS and getattr(STATE, "m3_volkov_ally_hp", 0) > 0:
                vx = float(getattr(STATE, "m3_volkov_ally_x", -99999))
                vy = float(getattr(STATE, "m3_volkov_ally_y", -99999))
                if math.hypot(b["x"] - vx, b["y"] - vy) < 22:
                    dmg = b.get("damage", ENEMY_DAMAGE)
                    STATE.m3_volkov_ally_hp = max(0, getattr(STATE, "m3_volkov_ally_hp", 220) - dmg)
                    STATE.m3_volkov_ally_hit_flash = 12
                    effects.shake(3)
                    effects.burst(b["x"], b["y"], C_BLOOD, 7)
                    try:
                        audio.play("bullet_impact_enemy", volume=0.38)
                    except Exception:
                        pass
                    if STATE.m3_volkov_ally_hp <= 0:
                        STATE.m3_volkov_ally_active = False
                        STATE.floating_texts.append([vx, vy - 24, "VOLKOV PINNED", (220, 150, 90), 120])
                    hit = True

        # Player/Volkov bullets vs enemies
        if b.get("owner") == "player" and not hit:
            for e in STATE.enemies:
                if math.hypot(b["x"] - e.rect.centerx, b["y"] - e.rect.centery) < 22:
                    damage = b.get("damage", 50)
                    shielded = False
                    if _m3l(e).kind == "shield":
                        # Front-facing shield reduces incoming fire. Flanking or
                        # back shots still do full damage.
                        # Use the bullet's previous position to determine where
                        # the shot came from. Current position may already have
                        # crossed through the guard center this frame.
                        incoming = math.atan2(b.get("prev_y", b["y"]) - e.rect.centery,
                                              b.get("prev_x", b["x"]) - e.rect.centerx)
                        diff = abs(math.atan2(math.sin(incoming - e.angle), math.cos(incoming - e.angle)))
                        if diff < _m3g(e).shield_angle_width:
                            damage = max(3, int(damage * 0.28))
                            shielded = True
                    e.hp -= damage
                    e.on_hit(px, py)
                    hit = True
                    STATE.shots_hit += 1
                    if shielded:
                        effects.burst(b["x"], b["y"], (150, 150, 125), 8)
                        if _rng_legacy.random() < 0.35:
                            STATE.floating_texts.append([b["x"], b["y"] - 18, "SHIELD", (180, 170, 110), 34])
                    else:
                        STATE.blood_decals.append([b["x"], b["y"], 140, _rng_legacy.randint(8, 16)])
                        effects.burst(b["x"], b["y"], C_BLOOD, 14)
                    try:
                        audio.play("bullet_impact" if shielded else "bullet_impact_enemy", volume=0.42)
                    except Exception:
                        pass
                    break
        # Cell-door hits before generic wall hits.
        if not hit:
            hit = _m3_damage_cell_door_with_bullet(b)

        # Wall hits (only if no entity / door was hit)
        if not hit:
            hit = collide_bullet_walls(b, solid_walls)
            if hit:
                effects.burst(b["x"], b["y"], (130, 125, 110), 4)
                try:
                    audio.play("bullet_impact", volume=0.30)
                except Exception:
                    pass
        if hit or b["life"] <= 0 or not (-500 < b["x"] < MAP_W * TILE_SIZE + 500 and -500 < b["y"] < MAP_H * TILE_SIZE + 500):
            if b in STATE.bullets:
                STATE.bullets.remove(b)


def _update_m3_camera(solid_walls):
    """Per-frame security camera update: sweep, detect, trigger alarm."""
    global _security_camera
    if _security_camera is None or not STATE.player or STATE.player_dead:
        return
    px, py = STATE.player.rect.centerx, STATE.player.rect.centery
    _security_camera.update(px, py, solid_walls)


def _update_m3_pickups():
    """Per-frame pickup collection for Mission 3.

    Auto-picks up any pickup within 36px of the player center (generous
    radius so the player doesn't have to pixel-hunt). Kinds:
      - "sidearm": looted IPA pistol. Disarms the disarmed flag, clears
        mission3_weapon past "chair_leg"/"shiv" (so weapons.py's
        _player_has_firearm() returns True), gives the player a full
        mag + 2 spare mags. Idempotent - picking up a second sidearm
        only refills ammo.
      - "bandage": heals 40 HP (matches M1's field dressing; M3 was the
        outlier at 15, which was a rounding error against a 115 HP pool
        during the sweep's damage output).
    """
    if not STATE.player or STATE.player_dead:
        return
    for pu in STATE.pickups[:]:
        if math.hypot(pu[0] - STATE.player.rect.centerx,
                      pu[1] - STATE.player.rect.centery) > 36:
            continue
        kind = pu[2]
        if kind == "sidearm":
            if (getattr(STATE, "k9_unlocked", False)
                    and getattr(STATE, "mission3_sidearm_acquired", False)):
                # K-9 equipped AND pistol already holstered: spare 9mm only.
                STATE.spare_mags = min(5, STATE.spare_mags + 1)
                STATE.floating_texts.append([
                    pu[0], pu[1] - 16, "+1 9MM MAG", C_TERMINAL, 70])
            elif (getattr(STATE, "k9_unlocked", False)
                    and not getattr(STATE, "mission3_sidearm_acquired", False)):
                # Player holds the K-9 but never got the pistol: holster the
                # looted sidearm as a swap-ready backup (Q toggles pistol/K-9).
                # Never hand out a bare pistol mag to a player with no pistol.
                STATE.mission3_sidearm_acquired = True
                STATE.player_disarmed = False
                STATE.ammo_in_mag = STATE.mag_size
                STATE.spare_mags = 2
                STATE.floating_texts.append([
                    pu[0], pu[1] - 16, "IPA PISTOL HOLSTERED - Q TO SWAP",
                    (220, 200, 120), 90])
            elif not getattr(STATE, "mission3_sidearm_acquired", False):
                STATE.mission3_sidearm_acquired = True
                STATE.player_disarmed = False
                # Clear mission3_weapon past the improvised-weapon enum so
                # weapons._player_has_firearm() returns True and the pistol
                # can fire. The shiv stays in inventory (V-key still works
                # for melee - handle_melee checks mission3_weapon first).
                STATE.mission3_weapon = "sidearm"
                STATE.current_weapon = "pistol"
                STATE.ammo_in_mag = STATE.mag_size
                STATE.spare_mags = 1
                STATE.floating_texts.append([
                    pu[0], pu[1] - 16, "SIDEARM ACQUIRED", (220, 200, 120), 90])
            else:
                # Already armed - just top off mags.
                STATE.spare_mags = min(5, STATE.spare_mags + 1)
                STATE.floating_texts.append([
                    pu[0], pu[1] - 16, "+1 MAG", C_TERMINAL, 70])
            try:
                audio.play("rifle_handle", volume=0.55)
            except Exception:
                pass
        elif kind == "bandage":
            old = STATE.player.hp
            heal_amount = 40
            STATE.player.hp = min(STATE.player.max_hp,
                                  STATE.player.hp + heal_amount)
            STATE.floating_texts.append([
                pu[0], pu[1] - 16,
                f"+{int(STATE.player.hp - old)} HP",
                (100, 220, 100), 70])
            try:
                audio.play("pickup", volume=0.45)
            except Exception:
                pass
        STATE.pickups.remove(pu)


# ─────────────────────────────────────────────
# Per-frame draw
# ─────────────────────────────────────────────
# Tile base colors (mirrors mission2.game_draw's tile_base dict).
_TILE_BASE = {
    ".": (32, 33, 33),   # corridor floor
    "g": (46, 46, 48),   # exterior compound ground (neutral grey aggregate;
                         # brown (40,36,32) -> warm (43,42,38) -> this, because
                         # even a warm cast read as wet dirt next to the
                         # concrete interiors - must match FLOOR["g"] in
                         # tools/make_art_pack.py or the legacy tier drifts)
    "O": (29, 36, 38),   # interior / control sector
    "L": (36, 46, 48),   # laundry / uniform processing (matches live draw branch)
    "Y": (48, 48, 44),   # exercise-yard concrete (matches live draw branch)
    "M": (34, 36, 34),   # maintenance / boiler wing (matches live draw branch)
    "K": (45, 48, 52),   # kitchen checker base (legacy-tier fallback parity)
    "E": (33, 34, 34),   # interior exit-zone / KO floor concrete (no longer
                         # falls back to exterior ground and reads as mud)
    "P": (32, 33, 33),   # player spawn tile = corridor floor
    "X": (29, 38, 32),   # objective marker tile
    "C": (54, 54, 52),   # concrete wall
    "B": (60, 50, 40),   # barrier
    # "D" intentionally omitted - drawn by _draw_m3_door_tile()
    "S": (60, 90, 100),  # security glass (passable, frosted cyan)
}


def _door_obj_at_tile(col, row):
    """Return the Door object placed at tile col,row, if any."""
    wx = col * TILE_SIZE
    wy = row * TILE_SIZE
    for d in getattr(STATE, "doors", []):
        if d.rect.x == wx and d.rect.y == wy:
            return d
    return None


def _draw_tiny_padlock(surface, x, y, col):
    """Tiny drawn lock icon. Avoids unicode emoji font issues."""
    pygame.draw.arc(surface, col, pygame.Rect(x + 2, y, 10, 10), math.pi, math.tau, 2)
    pygame.draw.rect(surface, col, (x + 1, y + 7, 12, 9), border_radius=2)
    pygame.draw.rect(surface, (30, 25, 20), (x + 5, y + 10, 4, 4))


def _m3_door_tile_state(col, row):
    """(door, locked, open_p, breach_active_on_this_door, hits) for the D tile at col/row."""
    d = _door_obj_at_tile(col, row)
    locked = getattr(d, "locked", True) if d else True
    open_p = getattr(d, "anim_progress", 0.0) if d else 0.0

    is_cell_door = (col == _DOOR_TILE_COL and row == _DOOR_TILE_ROW) or \
                   (col == _DOOR_TILE_COL + 1 and row == _DOOR_TILE_ROW)
    if is_cell_door:
        # Only show the cell door as OPEN after detonation (frame 301+).
        # During charge planting (frames 0-300) the door is still INTACT -
        # Volkov is placing the C4, it hasn't blown yet. Showing the door
        # as open during this phase made it look like a dark empty doorway
        # (a "grey box") that was already open/openable before the blast.
        if getattr(STATE, "mission3_cell_open", False) or _m3_flow._volkov_breach_t >= 301:
            open_p = 1.0
            locked = False
    # Suppress the door's own LEDs while the breach sequence is active on THIS door - the C4
    # charge (drawn by _draw_volkov_breach) carries its own red blinking LED.
    breach_active_on_this_door = is_cell_door and _m3_flow._volkov_breach_t >= 0
    hits = _m3d(d).shot_hits if d else 0
    return d, locked, open_p, breach_active_on_this_door, hits


def _draw_m3_door_tile(surface, sx, sy, col, row):
    """Draw a proper reinforced prison door at any D tile."""
    sx, sy = int(sx), int(sy)
    d, locked, open_p, breach, hits = _m3_door_tile_state(col, row)
    # RPE6 Phase 3: the two rest states (closed, fully open) are baked sprites
    # (game.art.m3.door_tile); the painter stays the fallback and draws the swing animation
    # and bullet damage.
    if hits == 0 and (open_p <= 0.0 or open_p >= 0.95):
        variant = (2 + (1 if breach else 0)) if open_p >= 0.95 else (0 if locked else 1)
        spr = _m3art.get("door_tile", variant)
        if spr is not None:
            surface.blit(spr, (sx - 2, sy - 2))
            return
    _paint_m3_door_tile(surface, sx, sy, col, row, d, locked, open_p, breach, hits)


def _paint_m3_door_tile(surface, sx, sy, col, row, d, locked, open_p, breach_active_on_this_door, hits):
    """Procedural door tile (frame 2 px around the 64 px tile). Bake source of game.art.m3.door_tile."""
    sx, sy = int(sx), int(sy)
    ts = TILE_SIZE

    frame_col = (38, 40, 45)
    frame_dark = (22, 24, 28)
    frame_hi = (55, 58, 64)
    pygame.draw.rect(surface, frame_dark, (sx - 2, sy - 2, ts + 4, ts + 4))
    pygame.draw.rect(surface, frame_col, (sx, sy, ts, ts))
    pygame.draw.line(surface, frame_hi, (sx, sy), (sx + ts, sy), 1)
    pygame.draw.line(surface, frame_hi, (sx, sy), (sx, sy + ts), 1)
    pygame.draw.line(surface, frame_dark, (sx, sy + ts - 1), (sx + ts, sy + ts - 1), 1)
    pygame.draw.line(surface, frame_dark, (sx + ts - 1, sy), (sx + ts - 1, sy + ts), 1)

    inner_spr = artpack.get("door_open_inner")
    if open_p >= 0.95:
        inner = pygame.Rect(sx + 4, sy + 4, ts - 8, ts - 8)
        if inner_spr is not None:
            surface.blit(inner_spr, inner.topleft)
        else:
            pygame.draw.rect(surface, (4, 5, 7), inner)
        # Green LED only when the door is open through normal gameplay (keycard / unlocked),
        # not during the scripted breach (see _m3_door_tile_state).
        if not breach_active_on_this_door:
            pygame.draw.circle(surface, (60, 220, 110), (sx + ts - 10, sy + 10), 4)
            pygame.draw.circle(surface, (30, 130, 60), (sx + ts - 10, sy + 10), 4, 1)
        return

    panel_w = int((ts - 8) * (1.0 - min(0.90, open_p)))
    if panel_w < 4:
        panel_w = 4

    panel = pygame.Rect(sx + 4, sy + 4, panel_w, ts - 8)
    leaf_spr = artpack.get("door_leaf")
    if leaf_spr is not None:
        cw = max(2, min(panel_w, ts - 8))
        surface.blit(leaf_spr.subsurface((0, 0, cw, ts - 8)), panel.topleft)
        if locked:
            _draw_tiny_padlock(surface, sx + ts - 16, sy + 6, (230, 200, 90))
        return
    panel_base = (52, 60, 72)
    panel_dark = (22, 28, 36)
    panel_hi = (82, 92, 108)
    panel_mid = (38, 44, 54)

    pygame.draw.rect(surface, panel_base, panel, border_radius=2)
    pygame.draw.line(surface, panel_hi, (panel.x + 2, panel.y + 1), (panel.right - 2, panel.y + 1), 1)
    pygame.draw.line(surface, panel_dark, (panel.x + 2, panel.bottom - 2), (panel.right - 2, panel.bottom - 2), 1)
    pygame.draw.rect(surface, panel_dark, panel, 2, border_radius=2)

    rib_start = panel.x + 8
    rib_end = panel.right - 8
    rib_spacing = max(10, (rib_end - rib_start) // 4)
    for rx in range(rib_start, rib_end, rib_spacing):
        if rx > panel.right - 6:
            break
        pygame.draw.line(surface, panel_dark, (rx, panel.y + 6), (rx, panel.bottom - 6), 3)
        pygame.draw.line(surface, panel_hi, (rx - 1, panel.y + 6), (rx - 1, panel.bottom - 6), 1)

    for frac in (0.33, 0.66):
        bar_y = panel.y + int(panel.h * frac)
        pygame.draw.line(surface, panel_dark, (panel.x + 4, bar_y), (panel.right - 4, bar_y), 2)
        pygame.draw.line(surface, panel_hi, (panel.x + 4, bar_y - 1), (panel.right - 4, bar_y - 1), 1)

    if panel_w > 20:
        vp_w = min(28, panel_w - 12)
        vp_h = 16
        vp_x = panel.x + 6
        vp_y = panel.y + 8
        vp = pygame.Rect(vp_x, vp_y, vp_w, vp_h)
        pygame.draw.rect(surface, (6, 8, 12), vp)
        pygame.draw.rect(surface, (70, 82, 96), vp, 1)
        bar_spacing = max(5, vp_w // 5)
        for bx in range(vp.x + bar_spacing, vp.right - 2, bar_spacing):
            pygame.draw.line(surface, (65, 75, 88), (bx, vp.y + 1), (bx, vp.bottom - 1), 2)
            pygame.draw.line(surface, (105, 118, 135), (bx - 1, vp.y + 1), (bx - 1, vp.bottom - 1), 1)

    if panel_w > 28:
        kp_w = 11
        kp_h = 20
        kp_x = panel.right - kp_w - 6
        kp_y = panel.centery - kp_h // 2
        pygame.draw.rect(surface, (14, 18, 24), (kp_x, kp_y, kp_w, kp_h), border_radius=2)
        pygame.draw.rect(surface, (55, 65, 78), (kp_x, kp_y, kp_w, kp_h), 1, border_radius=2)
        # Same suppression as the open-state green LED above: hide the
        # keypad LED during the breach so only the C4's red blink reads.
        if not breach_active_on_this_door:
            led_col = (220, 50, 40) if locked else (60, 230, 120)
            pygame.draw.circle(surface, led_col, (kp_x + kp_w // 2, kp_y + 5), 2)
        for ky in range(2):
            for kx in range(2):
                btn_x = kp_x + 2 + kx * 4
                btn_y = kp_y + 10 + ky * 4
                pygame.draw.rect(surface, (35, 42, 52), (btn_x, btn_y, 3, 3), border_radius=1)

    if panel_w > 22:
        handle_x = panel.right - 16
        handle_y = panel.centery + 12
        pygame.draw.rect(surface, (65, 75, 88), (handle_x - 2, handle_y - 4, 8, 12), border_radius=2)
        pygame.draw.circle(surface, (120, 130, 145), (handle_x + 2, handle_y + 2), 3)
        pygame.draw.circle(surface, (45, 52, 62), (handle_x + 2, handle_y + 2), 3, 1)

    if locked and panel_w > 18:
        lock_x = panel.x + 5
        lock_y = panel.bottom - 18
        pygame.draw.arc(surface, (180, 130, 55), pygame.Rect(lock_x + 1, lock_y, 10, 8), 0, math.pi, 2)
        pygame.draw.rect(surface, (180, 130, 55), (lock_x, lock_y + 5, 12, 9), border_radius=1)
        pygame.draw.rect(surface, (30, 22, 12), (lock_x + 4, lock_y + 8, 4, 4))

    # Bullet damage overlay for shootable Mission 3 cell doors.
    if hits > 0 and open_p < 0.95:
        dmg_rng = random.Random((col * 113) + (row * 271))

        dmg_cx = panel.right - 13 if panel_w > 26 else panel.centerx
        dmg_cy = panel.centery + 6

        for i in range(hits):
            ox = dmg_rng.randint(-10, 10)
            oy = dmg_rng.randint(-14, 10)
            px = dmg_cx + ox
            py = dmg_cy + oy

            pygame.draw.circle(surface, (18, 16, 14), (px, py), 3)
            pygame.draw.circle(surface, (120, 112, 94), (px, py), 3, 1)

            ang = dmg_rng.uniform(0, math.tau)
            ln = dmg_rng.randint(7, 15)
            pygame.draw.line(
                surface,
                (18, 14, 12),
                (px, py),
                (px + math.cos(ang) * ln, py + math.sin(ang) * ln),
                1,
            )

        required = _m3d(d).required_shots if d else 6
        if hits >= required - 1:
            if (_now_ms() // 140) % 2 == 0:
                pygame.draw.line(surface, (255, 180, 80), (dmg_cx - 6, dmg_cy), (dmg_cx + 7, dmg_cy - 5), 2)
                pygame.draw.circle(surface, (255, 90, 40), (dmg_cx + 7, dmg_cy - 5), 2)

    lbl_col = (180, 140, 70) if locked else (90, 200, 140)
    lbl = font_terminal_small.render(_T("m3.door"), True, lbl_col)
    surface.blit(lbl, (sx + ts // 2 - lbl.get_width() // 2, sy + ts - 14))

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
           color=C_SYSTEM, duration=300, mark="comms_power_restored",
           priority=1)


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
           color=C_VOLKOV, duration=280, mark="comms_auth_acquired",
           priority=1)


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
            rx, ry - 34, "NO POWER - CHECK BATTERY BACKUP", (220, 165, 80), 100])
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
               color=C_SYSTEM, duration=420, mark="comms_relay_restored",
               priority=1)



# ─────────────────────────────────────────────
# Crafting - grind the chair leg into a shiv
# ─────────────────────────────────────────────
# After the chair breaks, the player has a "chair_leg" (blunt, slow, weak).
# They walk to the floor drain (tile 9, 8) and press E to open the crafting
# overlay. The overlay is a close-up of the drain grate with the metal chair leg
# lying across it. The player holds the left mouse button and drags
# left/right to grind the leg against the metal grate. Progress accrues
# based on drag distance; the leg visually transforms from a thick tube
# to a tapered shiv. At 100%, the shiv is done, the overlay closes,
# the doorway unblocks, and the objective updates.
#
# This is NOT a timing bar or QTE - the crafting IS the drag motion. The
# player is directly manipulating the object, and the object transforms in
# real-time based on how much they've dragged.

_DRAIN_TILE_COL, _DRAIN_TILE_ROW = 34, 9   # centre floor of Biribel's cell
_CRAFT_DRAG_RATE = 0.0004   # legacy tuning note; current minigame uses strokes
_CRAFT_MAX_OFFSET = 86      # how far the leg slides left/right (px)
_CRAFT_CONTACT_Y = HEIGHT // 2 + 20
_CRAFT_CONTACT_BAND = 58    # vertical mouse band where pressure/contact is good


def is_crafting_active():
    """True while the crafting overlay is open. acaristan.py checks this to
    route mouse/keyboard input to handle_crafting_event instead of the
    normal game input."""
    return bool(getattr(STATE, "mission3_crafting_active", False))


def grant_k9_smg():
    """Equip the Mission 3 armory reward."""
    if getattr(STATE, "k9_unlocked", False):
        return
    STATE.k9_unlocked = True
    STATE.player_disarmed = False
    STATE.mission3_weapon = "k9_smg"
    STATE.current_weapon = "k9_smg"
    STATE.k9_mag_size = 24
    STATE.k9_ammo_in_mag = STATE.k9_mag_size
    STATE.k9_spare_mags = 2
    STATE.k9_shot_cooldown = 0
    STATE.is_reloading = False
    STATE.reload_timer = 0
    STATE.floating_texts.append([
        _K9_STAND_COL * TILE_SIZE + TILE_SIZE // 2,
        _K9_STAND_ROW * TILE_SIZE + TILE_SIZE // 2 - 24,
        "K-9 SUPPRESSED SMG ACQUIRED",
        (140, 230, 190),
        120,
    ])
    try:
        audio.play("pickup", volume=0.55)
    except Exception:
        pass


def start_black_ledger_debug():
    """Dev jump: 12/13 detainees counted, full loadout, guards removed.

    Leaves exactly one living detainee near the player so testers can fire the
    final shot and trigger the Black Ledger easter egg naturally.
    """
    start_mission3(preserve_timer=True)

    STATE.mission3_stage = STAGE_BREAKOUT
    STATE.mission_phase = "m3_black_ledger_debug"
    STATE.mission3_cell_open = True
    STATE.mission3_chair_broken = True
    STATE.mission3_chair_break_anim = -1
    STATE.mission3_doorway_blocked = False
    STATE.mission3_crafting_active = False
    STATE.mission3_crafting_progress = 1.0
    STATE.mission3_vent_open = True
    STATE.mission3_cell_block_cleared = True
    STATE.mission3_guards_spawned = True
    STATE.mission3_guards_killed = 999
    STATE.enemies = []
    STATE.bullets = []
    STATE.pickups = []
    STATE.fire_zones = []
    STATE.thrown_bottles = []
    STATE.m3_alarm_active = False
    STATE.m3_black_ledger_triggered = False
    STATE.m3_black_ledger_inmate_active = False
    STATE.m3_black_ledger_inmate = None
    STATE.m3_black_ledger_intro_timer = 0
    STATE.m3_black_ledger_death_active = False
    STATE.m3_black_ledger_death_timer = 0

    # Complete practical M3 loadout: crafted shiv state, sidearm progression,
    # and armory K-9 equipped with full ammo.
    STATE.player_disarmed = False
    STATE.mission3_weapon = "k9_smg"
    STATE.current_weapon = "k9_smg"
    STATE.mission3_sidearm_acquired = True
    STATE.k9_unlocked = True
    STATE.k9_mag_size = 24
    STATE.k9_ammo_in_mag = 24
    STATE.k9_spare_mags = 4
    STATE.ammo_in_mag = 15
    STATE.spare_mags = 4
    STATE.is_reloading = False
    STATE.reload_timer = 0
    STATE.player_bottles = 0
    if STATE.player:
        STATE.player.hp = STATE.player.max_hp

    detainees = getattr(STATE, "mission3_detainees", [])
    for d in detainees:
        d["dead"] = False
        d["state"] = "idle"
        d["line_timer"] = 0
        d.pop("black_ledger_hit_by_player", None)

    # Count every detainee except the final one. Use the last authored
    # detainee so repeated debug starts are deterministic.
    final = detainees[-1] if detainees else None
    for d in detainees[:-1]:
        d["dead"] = True
        d["state"] = "dead"
        d["line_timer"] = 0
        d["black_ledger_hit_by_player"] = True

    STATE.blood_decals = []
    for d in detainees[:-1]:
        wx, wy = _detainee_draw_pos(d)
        STATE.blood_decals.append([wx, wy, 115, 10])

    if final and STATE.player:
        fx, fy = _detainee_draw_pos(final)
        # Put Biribel just west of the last detainee, facing them. Tester only
        # needs to aim/click once to open the Ledger.
        STATE.player.rect.centerx = int(fx - 105)
        STATE.player.rect.centery = int(fy)
        STATE.player.angle = 0.0
        final["line_timer"] = 120
        final["line"] = final.get("line") or "don't"
        _snap_camera_to((STATE.player.rect.centerx, STATE.player.rect.centery))

    _set_objective("DEBUG: shoot the last detainee to open the Black Ledger. 12/13 counted.")
    STATE.floating_texts.append([
        STATE.player.rect.centerx if STATE.player else 0,
        (STATE.player.rect.centery - 64) if STATE.player else 0,
        "BLACK LEDGER DEBUG: 12/13",
        (230, 90, 80),
        210,
    ])
    return final


def handle_interact():
    """E key handler for M3. Routes:
      - Crafting overlay open → no-op (let handle_crafting_event handle it).
      - Near the drain with a chair_leg → start crafting.
      - Near the vent grate with a shiv → pry open / crawl through.
      - Near the armory wall stand → acquire the K-9 and trigger FP pickup.
    """
    if getattr(STATE, "mission3_crafting_active", False):
        return

    weapon = getattr(STATE, "mission3_weapon", "none")

    # Comms Wing now has a small objective chain instead of one passive relay
    # interaction: clear the wing, restore battery power, copy authorization
    # from Security, then tune the relay.
    if getattr(STATE, "mission3_stage", None) == STAGE_COMMS:
        bx, by = _comms_breaker_pos()
        if _near((bx, by), radius=78):
            _restore_comms_power()
            return
        ax, ay = _comms_auth_pos()
        if _near((ax, ay), radius=78):
            _acquire_comms_auth()
            return
        rx, ry = _relay_pos()
        if _near((rx, ry), radius=92):
            _start_comms_relay_tuning()
            return
        # Manual archive-door push if the player presses E on the E-tile.
        if getattr(STATE, "m3_relay_tuned", False):
            exit_pos = (
                _ARCHIVE_EXIT_COL * TILE_SIZE + TILE_SIZE // 2,
                _ARCHIVE_EXIT_ROW * TILE_SIZE + TILE_SIZE // 2,
            )
            if _near(exit_pos, radius=TILE_SIZE * 0.9):
                _build_archives_world()
                STATE.m3_archives_transition_prebuilt = True
                STATE.mission3_stage = STAGE_ARCHIVES_TRANSITION
                STATE.mission_phase = "m3_archives_transition"
                STATE.request_archives_transition_cutscene = True
                return

    if getattr(STATE, "mission3_stage", None) == STAGE_ARCHIVES:
        if getattr(STATE, "m3_maru_contact_active", False):
            return  # locked during transmission
        mx, my = _maru_terminal_pos()
        if _near((mx, my), radius=78):
            _start_maru_contact()
            return
        vx, vy = _vostral_file_pos()
        # Match the visible prompt range and allow interaction from any side of
        # the pedestal. The pedestal itself is solid, so requiring the player
        # to reach its exact center made the prompt appear while E did nothing.
        if _near((vx, vy), radius=150):
            _acquire_vostral_file()
            return
        if getattr(STATE, "m3_vostral_acquired", False):
            if _near(_archives_exit_pos(), radius=TILE_SIZE * 0.9):
                _start_kill_order_phase()
                return

    # Check proximity to the drain (crafting).
    if weapon == "chair_leg":
        drain_pos = (_DRAIN_TILE_COL * TILE_SIZE + TILE_SIZE // 2,
                     _DRAIN_TILE_ROW * TILE_SIZE + TILE_SIZE // 2)
        if _near(drain_pos, radius=60):
            start_crafting()
            return

    # Check proximity to the vent grate.
    vent_pos = (_VENT_GRATE_COL * TILE_SIZE + TILE_SIZE // 2,
                _VENT_GRATE_ROW * TILE_SIZE + TILE_SIZE // 2)
    if _near(vent_pos, radius=50):
        if not getattr(STATE, "mission3_vent_open", False):
            # Pry open with shiv.
            try:
                audio.play("door_break", volume=0.4)
            except Exception:
                pass
            STATE.mission3_vent_open = True
            _set_objective("Escape through the vent or the corridor.")
        else:
            # Teleport to vent exit.
            STATE.player.rect.centerx = _VENT_EXIT_COL * TILE_SIZE + TILE_SIZE // 2
            STATE.player.rect.centery = _VENT_EXIT_ROW * TILE_SIZE + TILE_SIZE // 2
            # Trigger the escape cutscene.
            STATE.mission3_stage = STAGE_VENT_CUTSCENE
            STATE.mission_phase = "m3_vent_cutscene"
            STATE.request_vent_cutscene = True
            return

    # Armory wall stand: acquire K-9 suppressed SMG and play the first-person
    # pickup cutscene. The grant happens immediately so returning from the
    # cutscene leaves the player armed.
    k9_pos = (_K9_STAND_COL * TILE_SIZE + TILE_SIZE // 2,
              _K9_STAND_ROW * TILE_SIZE + TILE_SIZE // 2)
    if not getattr(STATE, "k9_unlocked", False) and _near(k9_pos, radius=72):
        grant_k9_smg()
        STATE.request_k9_pickup_cutscene = True
        return

    from core.interactions import interact_door
    interact_door()


def start_crafting():
    """Open the crafting overlay. Called when the player presses E near the
    drain while holding a chair_leg."""
    if getattr(STATE, "mission3_weapon", "none") != "chair_leg":
        return
    if getattr(STATE, "mission3_crafting_active", False):
        return
    STATE.mission3_crafting_active = True
    STATE.mission3_crafting_mouse_held = False
    mx, _ = get_scaled_mouse()
    STATE.mission3_crafting_prev_mx = mx
    STATE.mission3_crafting_accum = 0.0
    STATE.mission3_crafting_progress = 0.0
    STATE.mission3_crafting_stroke_dir = 1       # start by dragging right
    STATE.mission3_crafting_stroke_progress = 0.0
    STATE.mission3_crafting_stroke_target = 150.0   # pixels per stroke; pressure gates speed
    STATE.mission3_crafting_strokes_done = 0
    STATE.mission3_crafting_strokes_needed = 9
    STATE.mission3_crafting_heat = 0.0             # 0..1, visual/spark intensity
    STATE.mission3_crafting_wrong_flash = 0        # frames of red feedback
    STATE.mission3_crafting_contact = 0.0          # 0..1 pressure/contact quality
    STATE.mission3_crafting_last_dx = 0.0
    STATE.mission3_crafting_last_good = False
    STATE.mission3_crafting_tip_glow = 0.0
    pygame.mouse.set_visible(True)


def _finish_crafting():
    """Called when progress reaches 1.0 - the shiv is done."""
    STATE.mission3_weapon = "shiv"
    STATE.mission3_doorway_blocked = False
    STATE.mission3_crafting_active = False
    STATE.mission3_crafting_progress = 1.0
    STATE.mission3_crafting_shavings = []
    _spawn_m3_guards_once()
    pygame.mouse.set_visible(False)
    try:
        audio.play("melee_hit", volume=0.5)  # final "done" thunk
    except Exception:
        pass


def _craft_contact_from_mouse(my):
    """Return pressure/contact quality based on vertical mouse position.

    The chair leg must be pressed near the drain grate to grind.  This makes
    the minigame feel physical instead of "move mouse horizontally anywhere".
    """
    dist = abs(my - _CRAFT_CONTACT_Y)
    return max(0.0, min(1.0, 1.0 - dist / _CRAFT_CONTACT_BAND))


def _craft_overall_progress():
    needed = max(1, getattr(STATE, "mission3_crafting_strokes_needed", 9))
    done = getattr(STATE, "mission3_crafting_strokes_done", 0)
    target = max(1.0, getattr(STATE, "mission3_crafting_stroke_target", 150.0))
    partial = max(0.0, min(1.0, getattr(STATE, "mission3_crafting_stroke_progress", 0.0) / target))
    return max(0.0, min(1.0, (done + partial) / needed))


def handle_crafting_event(event):
    """Handle input while the sharpening overlay is open.

    Improved interaction model:
      - Hold LMB to grip the chair leg.
      - Drag in the indicated direction.
      - Keep the mouse near the grate for good pressure/contact.
      - Wrong direction slips and flashes red instead of feeling silent.
      - Partial stroke progress contributes visibly to the blade shape.
    """
    if not getattr(STATE, "mission3_crafting_active", False):
        return

    if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
        STATE.mission3_crafting_mouse_held = True
        mx, my = get_scaled_mouse()
        STATE.mission3_crafting_prev_mx = mx
        STATE.mission3_crafting_contact = _craft_contact_from_mouse(my)
        STATE.mission3_crafting_last_dx = 0.0
        STATE.mission3_crafting_last_good = False
        return

    if event.type == pygame.MOUSEBUTTONUP and event.button == 1:
        STATE.mission3_crafting_mouse_held = False
        # Releasing does not wipe progress anymore; it just cools the motion.
        STATE.mission3_crafting_last_dx = 0.0
        STATE.mission3_crafting_last_good = False
        return

    if event.type == pygame.MOUSEMOTION and STATE.mission3_crafting_mouse_held:
        mx, my = get_scaled_mouse()
        dx = mx - STATE.mission3_crafting_prev_mx
        STATE.mission3_crafting_prev_mx = mx
        STATE.mission3_crafting_last_dx = dx

        contact = _craft_contact_from_mouse(my)
        STATE.mission3_crafting_contact = contact
        required_dir = STATE.mission3_crafting_stroke_dir

        # Tiny jitter should not punish the player.
        if abs(dx) < 0.4:
            return

        if dx * required_dir > 0 and contact > 0.12:
            # Correct direction + near the grate: grind.  Better contact gives
            # more progress and hotter sparks.
            gain = abs(dx) * (0.35 + contact * 0.85)
            STATE.mission3_crafting_stroke_progress += gain
            STATE.mission3_crafting_heat = min(1.0, getattr(STATE, "mission3_crafting_heat", 0.0) + 0.018 + contact * 0.018)
            STATE.mission3_crafting_tip_glow = min(1.0, getattr(STATE, "mission3_crafting_tip_glow", 0.0) + 0.035)
            STATE.mission3_crafting_last_good = True

            if abs(dx) > 1:
                _spawn_shaving(contact=contact, speed=abs(dx), good=True)

            target = STATE.mission3_crafting_stroke_target
            if STATE.mission3_crafting_stroke_progress >= target:
                STATE.mission3_crafting_strokes_done += 1
                STATE.mission3_crafting_stroke_progress = 0.0
                STATE.mission3_crafting_stroke_dir *= -1
                STATE.mission3_crafting_progress = _craft_overall_progress()
                effects.shake(3)
                try:
                    audio.play("melee_hit", volume=0.34 + 0.14 * contact)
                except Exception:
                    pass

                if STATE.mission3_crafting_strokes_done >= STATE.mission3_crafting_strokes_needed:
                    STATE.mission3_crafting_progress = 1.0
                    _finish_crafting()
                    return
            else:
                STATE.mission3_crafting_progress = _craft_overall_progress()
        else:
            # Slip: wrong direction or no pressure.  Do not obliterate progress,
            # but bleed a little so the player understands the stroke failed.
            STATE.mission3_crafting_last_good = False
            STATE.mission3_crafting_wrong_flash = 14
            STATE.mission3_crafting_stroke_progress = max(
                0.0, STATE.mission3_crafting_stroke_progress - abs(dx) * 0.45)
            STATE.mission3_crafting_heat = max(0.0, getattr(STATE, "mission3_crafting_heat", 0.0) - 0.015)
            STATE.mission3_crafting_progress = _craft_overall_progress()
            if abs(dx) > 2:
                _spawn_shaving(contact=max(0.15, contact), speed=abs(dx), good=False)
        return

    if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
        # Mandatory crafting lock: cannot cancel, but give subtle feedback.
        STATE.mission3_crafting_wrong_flash = 10
        return


def _spawn_shaving(contact=1.0, speed=4.0, good=True):
    """Spawn sparks and metal filings at the grinding contact point."""
    cx = WIDTH // 2
    cy = _CRAFT_CONTACT_Y + 8
    mx, _ = get_scaled_mouse()
    contact_x = int(cx + max(-_CRAFT_MAX_OFFSET, min(_CRAFT_MAX_OFFSET, mx - cx)) * 0.62)

    spark_count = 1 + int(min(5, speed / 4.0 + contact * 3.0))
    if not good:
        spark_count = max(1, spark_count // 2)

    for _ in range(spark_count):
        hot = good and _rng_legacy.random() < (0.55 + contact * 0.35)
        STATE.mission3_crafting_shavings.append({
            "x": contact_x + _rng_legacy.randint(-12, 12),
            "y": cy + _rng_legacy.randint(-4, 5),
            "vx": _rng_legacy.uniform(-3.8, 3.8) + (0.7 if STATE.mission3_crafting_stroke_dir > 0 else -0.7),
            "vy": _rng_legacy.uniform(-3.2, -0.6),
            "life": 16 + _rng_legacy.randint(0, 18),
            "rot": _rng_legacy.uniform(0, math.pi * 2),
            "len": _rng_legacy.randint(3, 8) if hot else _rng_legacy.randint(2, 5),
            "type": "spark" if hot else "filing",
            "good": good,
        })

    # Longer dull curls of scraped metal.
    if _rng_legacy.random() < (0.25 + contact * 0.4):
        STATE.mission3_crafting_shavings.append({
            "x": contact_x + _rng_legacy.randint(-22, 22),
            "y": cy + _rng_legacy.randint(-2, 4),
            "vx": _rng_legacy.uniform(-1.3, 1.3),
            "vy": _rng_legacy.uniform(-0.5, 0.25),
            "life": 55 + _rng_legacy.randint(0, 40),
            "rot": _rng_legacy.uniform(0, math.pi * 2),
            "len": _rng_legacy.randint(5, 11),
            "type": "filing",
            "good": good,
        })


def _update_crafting():
    """Per-frame update for the crafting overlay (heat + particles)."""
    if not getattr(STATE, "mission3_crafting_active", False):
        return

    # Heat and feedback decay. Heat gives the tip glow/sparks a physical rhythm.
    STATE.mission3_crafting_heat = max(0.0, getattr(STATE, "mission3_crafting_heat", 0.0) - 0.006)
    STATE.mission3_crafting_tip_glow = max(0.0, getattr(STATE, "mission3_crafting_tip_glow", 0.0) - 0.012)
    if getattr(STATE, "mission3_crafting_wrong_flash", 0) > 0:
        STATE.mission3_crafting_wrong_flash -= 1
    if not getattr(STATE, "mission3_crafting_mouse_held", False):
        STATE.mission3_crafting_contact = max(0.0, getattr(STATE, "mission3_crafting_contact", 0.0) - 0.04)

    # Keep the displayed total in sync with partial stroke progress.
    STATE.mission3_crafting_progress = _craft_overall_progress()

    for s in STATE.mission3_crafting_shavings:
        s["x"] += s["vx"]
        s["y"] += s["vy"]
        s["vy"] += 0.16  # gravity
        s["vx"] *= 0.985
        s["life"] -= 1
        s["rot"] += 0.16 if s.get("type") == "spark" else 0.06

    STATE.mission3_crafting_shavings = [
        s for s in STATE.mission3_crafting_shavings if s["life"] > 0
    ]


def _draw_crafting_overlay():
    """Sharpening minigame overlay - v2: one compact workbench panel.

    The v1 overlay washed the whole screen with a giant additive spotlight
    disc and scattered readouts top/bottom. v2 puts everything inside a
    single centered card: header (title + stroke/edge chips), edge bar,
    stroke-direction rail, the drain + leg + hands diorama, pressure meter,
    and a footer instruction line. Outside the card stays dark and quiet.
    """
    ticks = _now_ms()
    progress = max(0.0, min(1.0, getattr(STATE, "mission3_crafting_progress", 0.0)))
    heat = max(0.0, min(1.0, getattr(STATE, "mission3_crafting_heat", 0.0)))
    contact = max(0.0, min(1.0, getattr(STATE, "mission3_crafting_contact", 0.0)))
    wrong_flash = getattr(STATE, "mission3_crafting_wrong_flash", 0)
    held = getattr(STATE, "mission3_crafting_mouse_held", False)

    # Quiet dark backdrop with cold concrete speckle.
    backdrop = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
    backdrop.fill((3, 4, 6, 236))
    screen.blit(backdrop, (0, 0))
    rng = random.Random(4404)
    for _ in range(60):
        x = rng.randrange(0, WIDTH)
        y = rng.randrange(0, HEIGHT)
        col = rng.choice([(12, 13, 14), (18, 17, 15), (7, 8, 10), (22, 20, 17)])
        pygame.draw.rect(screen, col, (x, y, rng.randrange(8, 34), rng.randrange(1, 4)))

    cx = WIDTH // 2
    cy = _CRAFT_CONTACT_Y
    mx, my = get_scaled_mouse()
    drag = max(-_CRAFT_MAX_OFFSET, min(_CRAFT_MAX_OFFSET, mx - cx)) if held else 0
    leg_cx = cx + drag
    leg_cy = cy - 4 + int((1.0 - contact) * 10 if held else 4)
    stroke_dir = getattr(STATE, "mission3_crafting_stroke_dir", 1)
    stroke_prog = getattr(STATE, "mission3_crafting_stroke_progress", 0.0)
    stroke_target = max(1.0, getattr(STATE, "mission3_crafting_stroke_target", 150.0))
    stroke_p = max(0.0, min(1.0, stroke_prog / stroke_target))
    strokes_done = getattr(STATE, "mission3_crafting_strokes_done", 0)
    strokes_needed = getattr(STATE, "mission3_crafting_strokes_needed", 9)

    # ── workbench card ──
    PW, PH = 760, 476
    PX, PY = cx - PW // 2, 126
    panel = pygame.Rect(PX, PY, PW, PH)
    pygame.draw.rect(screen, (6, 7, 8), panel.inflate(8, 8), border_radius=14)
    pygame.draw.rect(screen, (11, 12, 13), panel, border_radius=12)
    pygame.draw.rect(screen, (58, 54, 46), panel, 2, border_radius=12)
    # wrong-direction tint confined to the card
    if wrong_flash > 0:
        tint = pygame.Surface((PW, PH), pygame.SRCALPHA)
        tint.fill((130, 20, 14, min(80, wrong_flash * 6)))
        screen.blit(tint, panel.topleft)
    # header strip
    pygame.draw.rect(screen, (17, 18, 19), (PX + 2, PY + 2, PW - 4, 44), border_radius=10)
    pygame.draw.line(screen, (44, 42, 36), (PX + 2, PY + 46), (PX + PW - 2, PY + 46), 1)
    title = font_terminal.render(_T("m3.sharpen_the_chair_leg"), True, (215, 190, 135))
    screen.blit(title, (PX + 18, PY + 14))
    chip2 = font_terminal_small.render(_T("m3.edge_pct", pct=int(progress * 100)), True, (200, 178, 130))
    chip1 = font_terminal_small.render(_T("m3.stroke_strokes_done_strokes_need", strokes_done=strokes_done, strokes_needed=strokes_needed), True, (160, 150, 120))
    x2 = PX + PW - 16 - chip2.get_width()
    x1 = x2 - 26 - chip1.get_width()
    for txt, xx in ((chip1, x1), (chip2, x2)):
        bg = pygame.Rect(xx - 8, PY + 12, txt.get_width() + 16, 22)
        pygame.draw.rect(screen, (24, 26, 28), bg, border_radius=5)
        pygame.draw.rect(screen, (52, 50, 44), bg, 1, border_radius=5)
        screen.blit(txt, (xx, PY + 16))
    # edge bar under the header
    bar_x, bar_y, bar_w, bar_h = PX + 18, PY + 56, PW - 36, 7
    pygame.draw.rect(screen, (28, 24, 18), (bar_x, bar_y, bar_w, bar_h), border_radius=3)
    pygame.draw.rect(screen, (170, 120, 58), (bar_x, bar_y, int(bar_w * progress), bar_h), border_radius=3)
    if heat > 0:
        pygame.draw.rect(screen, (255, 100, 35), (bar_x, bar_y, int(bar_w * min(1.0, heat)), bar_h), 1, border_radius=3)
    pygame.draw.rect(screen, (76, 62, 42), (bar_x, bar_y, bar_w, bar_h), 1, border_radius=3)

    # contained warm work-light (no full-screen additive disc)
    pool = pygame.Surface((PW, PH), pygame.SRCALPHA)
    pygame.draw.ellipse(pool, (150, 135, 95, 24), (cx - PX - 300, cy - PY - 62, 600, 190))
    pygame.draw.ellipse(pool, (172, 152, 106, 20), (cx - PX - 190, cy - PY - 46, 380, 140))
    screen.blit(pool, panel.topleft)

    # ── stroke direction rail ──
    rail_y = cy - 118
    pygame.draw.line(screen, (64, 57, 45), (cx - 160, rail_y), (cx + 160, rail_y), 4)
    if stroke_dir > 0:
        sx, ex = cx - 160, cx - 160 + int(320 * stroke_p)
    else:
        sx, ex = cx + 160, cx + 160 - int(320 * stroke_p)
    pygame.draw.line(screen, (205, 160, 82), (sx, rail_y), (ex, rail_y), 5)
    arrow = "DRAG RIGHT" if stroke_dir > 0 else "DRAG LEFT"
    arrow_col = (230, 190, 110) if (held and contact > 0.18) else (150, 132, 98)
    arrow_surf = font_dialogue.render(("> " + arrow + " >") if stroke_dir > 0 else ("< " + arrow + " <"), True, arrow_col)
    screen.blit(arrow_surf, (cx - arrow_surf.get_width() // 2, rail_y - 34))

    # ── drain basin + grate ──
    basin = pygame.Rect(cx - 190, cy - 54, 380, 118)
    pygame.draw.ellipse(screen, (8, 8, 7), basin.move(0, 18))
    pygame.draw.rect(screen, (20, 19, 16), basin, border_radius=18)
    pygame.draw.rect(screen, (48, 44, 36), basin, 2, border_radius=18)
    pygame.draw.rect(screen, (10, 9, 8), (cx - 160, cy - 24, 320, 68), border_radius=12)
    grate_w, grate_h = 290, 42
    grate_rect = pygame.Rect(cx - grate_w // 2, cy - 10, grate_w, grate_h)
    pygame.draw.rect(screen, (38, 35, 29), grate_rect, border_radius=7)
    pygame.draw.rect(screen, (78, 70, 55), grate_rect, 2, border_radius=7)
    for off in range(12, grate_w - 8, 18):
        x = grate_rect.x + off
        col = (92, 82, 62) if off % 36 == 12 else (58, 53, 43)
        pygame.draw.line(screen, col, (x, grate_rect.y + 5), (x - 12, grate_rect.bottom - 5), 3)
        pygame.draw.line(screen, (13, 12, 10), (x + 2, grate_rect.y + 7), (x - 10, grate_rect.bottom - 3), 1)
    groove_alpha = int(55 + 120 * progress + 50 * heat)
    pygame.draw.line(screen, (210, 156, 72), (cx - 130, cy + 8), (cx + 130, cy + 8), 2)
    pygame.draw.line(screen, (255, 190, 80, min(210, groove_alpha)), (cx - 128, cy + 7), (cx + 128, cy + 7), 1)

    # ── chair leg / blade transformation ──
    leg_len = 260
    base_w = 28 - 14 * progress
    leg_left = leg_cx - leg_len // 2
    leg_right = leg_cx + leg_len // 2
    top_pts, bot_pts = [], []
    for i in range(leg_len + 1):
        t = i / leg_len
        taper_zone = max(0.0, (t - 0.38) / 0.62)
        taper = 1.0 - taper_zone * progress * 0.96
        jag = math.sin((i + ticks * 0.03) * 0.27) * 0.65 * (1.0 - progress)
        w = max(2.2, base_w * taper)
        x = leg_left + i
        top_pts.append((x, leg_cy - w / 2 + jag))
        bot_pts.append((x, leg_cy + w / 2 + jag * 0.4))
    leg_pts = top_pts + list(reversed(bot_pts))
    pygame.draw.polygon(screen, (3, 3, 3), [(x, y + 10) for x, y in leg_pts])
    pygame.draw.polygon(screen, (116, 118, 120), leg_pts)
    pygame.draw.polygon(screen, (48, 50, 54), leg_pts, 2)
    pygame.draw.line(screen, (170, 174, 176), (leg_left + 14, leg_cy - base_w * 0.22), (leg_right - 18, leg_cy - 2), 2)
    pygame.draw.line(screen, (72, 74, 78), (leg_left + 12, leg_cy + base_w * 0.28), (leg_right - 12, leg_cy + 3), 2)
    for k in range(5):
        x = leg_left + 14 + k * 12
        pygame.draw.line(screen, (70, 52, 36), (x, leg_cy - 18), (x + 16, leg_cy + 17), 3)
    tip_glow = max(heat, getattr(STATE, "mission3_crafting_tip_glow", 0.0), progress * 0.55)
    if progress > 0.20 or heat > 0.05:
        tip_x = int(leg_right - 5)
        pygame.draw.circle(screen, (245, 230, 190), (tip_x, int(leg_cy)), max(2, int(2 + progress * 4)))
        glow = pygame.Surface((90, 70), pygame.SRCALPHA)
        pygame.draw.circle(glow, (255, 145, 55, int(80 * tip_glow)), (45, 35), int(16 + 24 * tip_glow))
        screen.blit(glow, (tip_x - 45, int(leg_cy) - 35), special_flags=pygame.BLEND_ADD)

    # ── gripping hands ──
    from core.hands import grip_hand
    for hx in (leg_left + 46, leg_left + 86):
        pygame.draw.rect(screen, (34, 40, 36), (hx - 34, leg_cy + 26, 68, 26), border_radius=10)
        grip_hand(screen, (hx, leg_cy - 14), axis=0, mirror=-1, sc=1.15, curl=1.0,
                  yank=0.3, grip_d=26)

    # ── sparks and filings ──
    for s in STATE.mission3_crafting_shavings:
        alpha = max(0, min(255, s["life"] * (9 if s["type"] == "spark" else 4)))
        if s["type"] == "spark":
            col = (255, _rng_legacy.randint(150, 225), 45, alpha) if s.get("good", True) else (180, 70, 55, alpha)
        else:
            col = (92, 94, 92, alpha)
        sv = pygame.Surface((s["len"] * 2 + 4, 5), pygame.SRCALPHA)
        pygame.draw.line(sv, col, (1, 2), (s["len"] + 1, 2), 2 if s["type"] == "spark" else 1)
        sv_rot = pygame.transform.rotate(sv, math.degrees(s["rot"]))
        screen.blit(sv_rot, (int(s["x"]) - sv_rot.get_width() // 2, int(s["y"]) - sv_rot.get_height() // 2))

    # ── pressure meter (inside card, right edge) ──
    meter_x, meter_y = PX + PW - 44, cy - 64
    pygame.draw.rect(screen, (16, 14, 12), (meter_x, meter_y, 16, 128), border_radius=6)
    fill_h = int(122 * contact)
    fill_col = (210, 145, 65) if contact > 0.35 else (120, 75, 52)
    pygame.draw.rect(screen, fill_col, (meter_x + 3, meter_y + 125 - fill_h, 10, fill_h), border_radius=4)
    pygame.draw.rect(screen, (70, 62, 48), (meter_x, meter_y, 16, 128), 1, border_radius=6)
    label = font_terminal_small.render(_T("m3.press"), True, (130, 116, 92))
    screen.blit(label, (meter_x + 8 - label.get_width() // 2, meter_y + 134))

    # ── footer instructions ──
    pygame.draw.line(screen, (40, 38, 34), (PX + 14, PY + PH - 68), (PX + PW - 14, PY + PH - 68), 1)
    if not held:
        instr = "HOLD LEFT MOUSE ON THE LEG"
        instr_col = (205, 180, 130)
    elif contact <= 0.18:
        instr = "LOWER / RAISE THE MOUSE TO PRESS AGAINST THE GRATE"
        instr_col = (205, 120, 90)
    elif wrong_flash > 0:
        instr = "WRONG WAY - FOLLOW THE SCRATCH DIRECTION"
        instr_col = (230, 90, 75)
    else:
        instr = "GRIND - KEEP PRESSURE, FINISH THE STROKE"
        instr_col = (220, 185, 105)
    instr_surf = font_dialogue.render(instr, True, instr_col)
    screen.blit(instr_surf, (cx - instr_surf.get_width() // 2, PY + PH - 58))
    hint = font_terminal_small.render(_T("m3.volkov_holds_the_door_make_it_qu"), True, (115, 105, 88))
    screen.blit(hint, (cx - hint.get_width() // 2, PY + PH - 30))

    draw_vignette(screen, strength=190)
    draw_scanlines(screen)


# ─────────────────────────────────────────────
# Input (dialogue router - the scaffolding calls this for ALL M3 input)
# ─────────────────────────────────────────────
def handle_event(event):
    """Mission 3 input router.

    acaristan.py routes every event here while active_mission == "MISSION3".

    Once the stage leaves STAGE_INTERROGATION, acaristan.py stops routing
    here and normal mouse-shoot / movement input falls through.
    """

    if getattr(STATE, "mission3_stage", STAGE_INTERROGATION) != STAGE_INTERROGATION:
        return  # action phases own their own input via acaristan's fallthrough

    if event.type != pygame.KEYDOWN:
        return

    beat = _current_beat()
    if beat is None:
        return

    btype = beat.get("type")

    # Volkov breach is a cinematic beat. Ignore SPACE/ENTER so the player
    # cannot skip the approach → charge plant → retreat → detonation → re-entry.
    if _action_is_unskippable(beat):
        return

    if btype == "choice":
        # Options are inert until the prompt finishes typing.
        if not _line_fully_typed(beat):
            if event.key in (pygame.K_RETURN, pygame.K_SPACE, pygame.K_KP_ENTER):
                _m3_flow._dialogue_char_idx = len(_beat_text(beat))  # finish the prompt
            return
        options = beat.get("options", [])
        if not options:
            _advance_beat()
            return
        if event.key in (pygame.K_UP, pygame.K_LEFT):
            _m3_flow._dialogue_choice = (_m3_flow._dialogue_choice - 1) % len(options)
            _click_blip()
        elif event.key in (pygame.K_DOWN, pygame.K_RIGHT):
            _m3_flow._dialogue_choice = (_m3_flow._dialogue_choice + 1) % len(options)
            _click_blip()
        elif event.key in (pygame.K_RETURN, pygame.K_SPACE, pygame.K_KP_ENTER):
            _resolve_choice(beat, _m3_flow._dialogue_choice)
        return

    # line / action beat: two-stage ENTER (finish typing, then advance).
    if event.key in (pygame.K_RETURN, pygame.K_SPACE, pygame.K_KP_ENTER):
        if not _line_fully_typed(beat):
            # First press: snap the typewriter to full length so the whole
            # line is readable, then the next press advances.
            _m3_flow._dialogue_char_idx = len(_beat_text(beat))
        else:
            # If the player mashes ENTER on an action beat before its FX
            # fired on entry, fire them now so the breach flash/shake lands.
            if btype == "action" and _m3_flow._dialogue_timer <= 1:
                _trigger_action(beat.get("action"))
            _advance_beat()


def _resolve_choice(beat, chosen):
    """Confirm a choice: remember the tone, inject the player's line, advance.

    The chosen option's ``line`` (the second tuple element) becomes a new
    BIRIBEL beat inserted right after this choice beat, so the player's
    voice plays in-scene before the next scripted line. The option *index*
    (0/1/2) is appended to _m3_flow._dialogue_tone for later slices to read.
    """
    options = beat.get("options", [])
    if not (0 <= chosen < len(options)):
        return
    _label, line = options[chosen]
    _m3_flow._dialogue_tone.append(chosen)
    STATE.mission3_dialogue_choices.append(chosen)

    follow_up = {
        "type": "line",
        "speaker": "BIRIBEL",
        "color": C_BIRIBEL,
        "text": line,
    }
    idx = _m3_flow._dialogue_index
    _dialogue_beats.insert(idx + 1, follow_up)
    _m3_flow._dialogue_choice = 0  # reset highlight for the next choice beat
    _click_blip(confirm=True)
    _advance_beat()


def _click_blip(confirm=False):
    """Tiny UI sound for choice navigation. Falls back to silence if the
    audio sample is missing (headless test harness)."""
    try:
        if confirm:
            audio.play("type_tick", volume=0.18)
        else:
            audio.play("type_tick", volume=0.10)
    except Exception:
        pass



# ─────────────────────────────────────────────
# Security camera - kitchen area
# ─────────────────────────────────────────────
# A surveillance camera mounted on the kitchen's north wall that sweeps
# back and forth. If it detects the player, it triggers an alarm and
# alerts all guards in the cell block.

_CAMERA_TILE_COL = 16          # centre of kitchen north wall
_CAMERA_TILE_ROW = 4           # north wall of kitchen
_CAMERA_SWEEP_HALF = math.radians(60)   # ±60° sweep
_CAMERA_SWEEP_SPEED = 0.008    # radians per frame
_CAMERA_CONE_HALF = math.radians(40)    # 80° total FOV
_CAMERA_DETECT_RANGE = 250     # px


class SecurityCamera:
    """A ceiling-mounted security camera that sweeps and detects the player.

    Attributes:
        col, row: tile position
        angle: current facing direction (radians, 0=east, pi/2=south)
        sweep_center: centre angle of the sweep arc
        sweep_dir: 1 or -1 (current sweep direction)
        alerted: True if the camera has spotted the player
        alarm_timer: frames remaining on the alarm flash
        sweep_lock: if alerted, stop sweeping and lock on player
    """
    __slots__ = ("col", "row", "angle", "sweep_center", "sweep_dir",
                 "alerted", "alarm_timer", "sweep_lock")

    def __init__(self, col, row, angle=math.pi * 0.5):
        self.col = col
        self.row = row
        self.angle = angle
        self.sweep_center = angle
        self.sweep_dir = 1
        self.alerted = False
        self.alarm_timer = 0
        self.sweep_lock = False

    @property
    def rect(self):
        cx = self.col * TILE_SIZE + TILE_SIZE // 2
        cy = self.row * TILE_SIZE + TILE_SIZE // 2
        return pygame.Rect(cx - 8, cy - 8, 16, 16)

    @property
    def center(self):
        return (self.col * TILE_SIZE + TILE_SIZE // 2,
                self.row * TILE_SIZE + TILE_SIZE // 2)

    def update(self, px, py, walls):
        """Per-frame update: sweep, detect, alarm."""
        if self.alerted:
            # Lock onto player position while alarmed.
            dx = px - self.center[0]
            dy = py - self.center[1]
            if dx != 0 or dy != 0:
                self.angle = math.atan2(dy, dx)
            if self.alarm_timer > 0:
                self.alarm_timer -= 1
            return

        # Sweep back and forth.
        self.angle += _CAMERA_SWEEP_SPEED * self.sweep_dir
        if abs(self.angle - self.sweep_center) > _CAMERA_SWEEP_HALF:
            self.sweep_dir *= -1

        # Detection check.
        dist = math.hypot(px - self.center[0], py - self.center[1])
        if dist > _CAMERA_DETECT_RANGE:
            return

        # Check if player is within the cone of vision.
        angle_to_player = math.atan2(py - self.center[1],
                                     px - self.center[0])
        diff = abs(angle_to_player - self.angle)
        if diff > math.pi:
            diff = 2 * math.pi - diff
        if diff > _CAMERA_CONE_HALF:
            return

        # Line-of-sight check: ray from camera to player.
        if not _has_los(self.center[0], self.center[1], px, py, walls):
            return

        # DETECTED!
        self.alerted = True
        self.alarm_timer = 120   # 2 seconds of alarm flash
        self.sweep_lock = True
        effects.shake(8)
        try:
            audio.play("alarm", volume=0.6)
        except Exception:
            pass
        # Alert all guards.
        for e in STATE.enemies:
            if _m3g(e).ipa:
                e.alerted = True
                if e.state in ("IDLE", "PATROL"):
                    e.state = "CHASE"
                e.last_seen_pos = (px, py)


def _has_los(x1, y1, x2, y2, walls):
    """True if the line (x1,y1)->(x2,y2) is unobstructed by solid walls."""
    for w in walls:
        if w.clipline(x1, y1, x2, y2):
            return False
    return True


# Camera instance (created in _build_world).
_security_camera = None


def _paint_security_camera_body(surface, body_cx, body_cy, alerted):
    """Camera mount + smoked dome centred on body_cx/body_cy (14 x 14 box from (-7, -7))."""
    # Mounting bracket (small rectangle on ceiling).
    pygame.draw.rect(surface, (60, 60, 65),
                     (body_cx - 5, body_cy - 6, 10, 5))
    # Camera dome (dark glass hemisphere).
    dome_alpha = 180 if not alerted else 255
    dome_surf = pygame.Surface((14, 14), pygame.SRCALPHA)
    pygame.draw.circle(dome_surf, (30, 30, 40, dome_alpha),
                       (7, 7), 7)
    surface.blit(dome_surf, (body_cx - 7, body_cy - 7))


def _draw_security_camera(cam_x, cam_y, walls):
    """Draw the security camera body + detection cone."""
    global _security_camera
    cam = _security_camera
    if cam is None:
        return
    cx = cam.center[0] - cam_x
    cy = cam.center[1] - cam_y

    # Draw the detection cone.
    cone_col = (255, 220, 60, 40) if not cam.alerted else (255, 40, 40, 80)
    cone_len = _CAMERA_DETECT_RANGE
    cone_surf = pygame.Surface((cone_len * 2, cone_len * 2), pygame.SRCALPHA)
    left_angle = cam.angle - _CAMERA_CONE_HALF
    right_angle = cam.angle + _CAMERA_CONE_HALF

    # Build cone polygon.
    cone_pts = [(cone_len, cone_len)]
    steps = 16
    for i in range(steps + 1):
        t = i / steps
        a = left_angle + (right_angle - left_angle) * t
        px = cone_len + math.cos(a) * cone_len
        py = cone_len + math.sin(a) * cone_len
        cone_pts.append((px, py))
    pygame.draw.polygon(cone_surf, cone_col, cone_pts)
    screen.blit(cone_surf, (cx - cone_len, cy - cone_len),
                special_flags=pygame.BLEND_ALPHA_SDL2)

    # Draw cone outline (thin dashed-style lines at the edges).
    edge_col = (255, 200, 50, 120) if not cam.alerted else (255, 50, 50, 180)
    for a in (left_angle, right_angle):
        ex = cx + math.cos(a) * cone_len
        ey = cy + math.sin(a) * cone_len
        pygame.draw.line(screen, edge_col, (cx, cy), (ex, ey), 1)

    # Draw camera body.
    body_cx = int(cx)
    body_cy = int(cy)

    # RPE6 Phase 3: mount + dome are a baked sprite (game.art.m3.camera_body, 0 idle / 1 alerted);
    # cone, glint and alarm light stay live, _paint_security_camera_body is the fallback.
    spr = _m3art.get("camera_body", 1 if cam.alerted else 0)
    if spr is not None:
        screen.blit(spr, (body_cx - 7, body_cy - 7))
    else:
        _paint_security_camera_body(screen, body_cx, body_cy, cam.alerted)

    # Glint on the dome (small bright dot at the edge - catches light).
    glint_off = (int(3 * math.cos(cam.angle - 0.5)),
                 int(3 * math.sin(cam.angle - 0.5)))
    pygame.draw.circle(screen, (180, 200, 220),
                       (body_cx + glint_off[0], body_cy + glint_off[1]), 2)

    # Red alarm light (flashing when alerted).
    if cam.alerted and (cam.alarm_timer // 15) % 2 == 0:
        pygame.draw.circle(screen, (255, 20, 20),
                           (body_cx, body_cy - 8), 3)
        # Glow.
        glow = pygame.Surface((16, 16), pygame.SRCALPHA)
        pygame.draw.circle(glow, (255, 50, 50, 80), (8, 8), 8)
        screen.blit(glow, (body_cx - 8, body_cy - 16),
                    special_flags=pygame.BLEND_ADD)


# ─────────────────────────────────────────────
# Inspector-style getters (mirrors mission2's surface for menus/acaristan)
# ─────────────────────────────────────────────
def get_mission3_overview():
    return {
        "id": MISSION3_ID,
        "title": MISSION3_TITLE,
        "location": MISSION3_LOCATION,
        "style": MISSION3_PRIMARY_STYLE,
        "story_flags": dict(MISSION3_STORY_FLAGS),
    }


def get_opening_cinematic():
    return list(OPENING_CINEMATIC)


def get_mission_phases():
    return [dict(p) for p in MISSION_PHASES]


def get_ending_cinematic():
    return [{"speaker": s.get("speaker", ""), "text": s.get("text", "")}
            for s in mission3_ending_shots]


# ── Slice 6: Broadcast Wing combat helpers ───────────────────────────
def _spawn_bcast_wave(wave):
    """Spawn a broadcast wave. Wave 1: corridor. Wave 2: gate. Wave 3: control-room assault."""
    from missions.m3.world import _spawn_m3_guard

    if wave == 1:
        _spawn_m3_guard(14, 8, hp=90, speed=1.6, label="bcast_corridor_1")
        _spawn_m3_guard(17, 10, hp=90, speed=1.6, label="bcast_corridor_2")
        _spawn_m3_guard(15, 12, hp=110, speed=1.4, label="bcast_corridor_3",
                        enemy_type="breacher")
    elif wave == 2:
        # Gate flankers stand on corridor floor with LOS south to the gate.
        # (Old coords (10/20/25, 14) were "g" wall tiles - guards spawned
        # inside solid rock and the wave could never clear.)
        _spawn_m3_guard(14, 12, hp=90, speed=1.6, label="bcast_gate_1")
        _spawn_m3_guard(17, 12, hp=90, speed=1.6, label="bcast_gate_2")
        _spawn_m3_guard(15, 13, hp=110, speed=1.4, label="bcast_gate_3",
                        enemy_type="breacher")
        _spawn_m3_guard(15, 11, hp=80, speed=1.8, label="bcast_gate_4",
                        enemy_type="marksman")
    elif wave == 3:
        # The PC's protectors: four hold the open floor, one is already
        # posted in the antechamber. All alerted and tracking her.
        _spawn_m3_guard(7, 20, hp=90, speed=1.6, label="bcast_booth_1")
        _spawn_m3_guard(10, 20, hp=90, speed=1.6, label="bcast_booth_2")
        _spawn_m3_guard(18, 20, hp=110, speed=1.4, label="bcast_booth_3",
                        enemy_type="breacher")
        _spawn_m3_guard(15, 18, hp=130, speed=1.2, label="bcast_booth_4",
                        enemy_type="shield")
        _spawn_m3_guard(25, 23, hp=80, speed=1.8, label="bcast_booth_5",
                        enemy_type="marksman")
