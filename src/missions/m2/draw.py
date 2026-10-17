"""Split from mission2.py - see mission2.py (shim) for the map."""
# missions.m2 package
# ------------------------------------------------------------

"""Mission 2: Quiet on Route 12 - clean cinematic vertical slice.

This module keeps the existing game integration intact:
    - game_core.start_mission2()
    - game_core.game_update()/game_draw() routing
    - acaristan.py Mission 2 intro and ending cutscenes
    - save as MISSION_2
    - dev command: python acaristan.py --dev-mission2


"""

import math
import random
from engine.core import LEGACY_RNG as _rng_legacy  # RPE6 R6: named 'legacy' rng stream
import time

import pygame

from core.config import (C_KRAP_BLUE, C_KRAP_UNIFORM, C_ORANGE, C_PLAYER_SKIN, C_TERMINAL, C_VASILE, C_WHITE, HEIGHT, MUZZLE_FLASH, TILE_SIZE, WIDTH, audio, draw_scanlines, draw_vignette, font_dialogue, font_speaker, font_terminal, font_terminal_small, get_scaled_mouse, screen)
from entities.art_cache import get_blood_decal, get_fullscreen_overlay, get_tinnitus_bar, get_panel_bg, get_glow
from core.state import STATE
from game.art import m2 as _m2art
from entities.player import Player, resolve_melee
from entities.enemy_ai import Enemy
from entities import corpse
from ui.hud import THEME, MiniMap, draw_objective_panel, draw_pinned_radio
from engine.ui import (bottle_hud as _hud_bottle_hud,
                       crosshair as _hud_crosshair,
                       health_bar as _hud_health_bar,
                       hostiles as _hud_hostiles)
from core.interactions import trigger_radio_chatter
from entities.weapons import (
    draw_thrown_bottles,
    spawn_molotov_fire as _spawn_molotov_fire,
    _wall_blocks_line,
    MOLOTOV_RADIUS,
    MOLOTOV_ENEMY_DAMAGE,
    MOLOTOV_PLAYER_DAMAGE,
    handle_shoot,
)
from fx import effects
from core.camera import update_camera, reset_camera_state, collide_bullet_walls, draw_bullets
from core import artpack, lighting, staticlayer
from core import render_util
from core import props as _props

from missions.m2 import world as _m2_world  # _last_keys/_objective reads
from missions.m2.meta import EXFIL_POS, FLANK_BEAT_BURST, FLANK_BEAT_PUSH_IN_END, FLANK_BEAT_SCRAMBLE_BEGIN, FLANK_BEAT_STAMP_FADE_IN, FLANK_BEAT_STAMP_FULL, FLANK_BEAT_STARTLE, FLANK_CUTSCENE_DURATION, GARDEN_BENCH_RECTS, GARDEN_CENTER, GARDEN_FOUNTAIN_RECT, GARDEN_HEDGE_RECTS, GARDEN_LAMP_RECTS, GARDEN_TREE_RECTS, IPA_TRUCK_POS, KILL_ZONE, MAP_H, MAP_W, MISSION2_BUILDINGS, MISSION2_CLUE_DEFS, MISSION2_ID, MISSION2_LOCATION, MISSION2_PRIMARY_STYLE, MISSION2_STORY_FLAGS, MISSION2_TITLE, MISSION_PHASES, OPENING_CINEMATIC, REQUIRED_INVESTIGATION_CLUES, SAFE_ZONE, SNIPER_GRACE_FRAMES, SNIPER_LOCK_FRAMES, SNIPER_NEST_POS, SQUADMATE_DEATH_CUTSCENE, STAGE_BLACKOUT, STAGE_COMBAT, STAGE_EVIDENCE, STAGE_EXFIL, STAGE_INVESTIGATE, STAGE_RUN, STAGE_SNIPER, STAGE_TANKER, STAGE_TRUCK, STAGE_UPLOAD, TANKER_POS, UPLOAD_TERMINAL_POS, ZONE_DEFS, _beat, mission2_ending_shots, mission2_intro_shots
from missions.m2.world import MISSION2_MAP, _burst, _muffle_radio_text, _player_pos, _radio, _set_objective
from missions.m2.starts import _clue_count, _evidence_count
from missions.m2.sniper import _draw_sniper_callout, _nearest_flank_marker, _nearest_killbox_cover, _player_exposed_to_sniper, _sniper_alive, _sniper_phase_name
from engine.core import now_ms as _now_ms, now_s as _now_s  # RPE6 B-001 timebase
from engine.text import T as _T  # RPE6 Phase 4 text table

PROP_WORLD_SCALE = 0.62
PROP_CARD_SCALE = 1.05
PROP_WORLD_HALO_RADIUS = 22
MARKER_RADIUS = 22


def _world(pos, fcx, fcy):
    # Snap world-to-screen coordinates to whole pixels.  Mission 2 camera values
    # can be fractional because the player speed is fractional; drawing tiles and
    # clue icons at fractional positions causes shimmering/"glitchy" textures
    # while walking.
    return int(round(pos[0] - fcx)), int(round(pos[1] - fcy))


# ─────────────────────────────────────────────────────────────────
# Civilian car palettes. Each car picks a palette deterministically
# from its WORLD-space rect center, so the same car always gets the
# same color and the palette doesn't jitter as the camera moves.
# Cars are oriented EAST (facing right) - the hood is on the right,
# the trunk on the left, matching the IPA truck orientation.
# ─────────────────────────────────────────────────────────────────
_CIVILIAN_CAR_PALETTES = [
    {   # faded red
        "body":        (148, 52, 44),
        "body_dark":   (98, 34, 30),
        "body_light":  (180, 72, 60),
        "roof":        (122, 44, 38),
        "glass":       (28, 38, 48),
        "glass_light": (70, 90, 105),
        "trim":        (45, 30, 28),
        "wheel":       (14, 14, 16),
        "wheel_rim":   (60, 56, 52),
        "headlight":   (230, 210, 140),
        "taillight":   (200, 50, 40),
    },
    {   # police-tan / sand
        "body":        (158, 140, 96),
        "body_dark":   (108, 94, 64),
        "body_light":  (190, 172, 124),
        "roof":        (134, 118, 80),
        "glass":       (32, 40, 48),
        "glass_light": (74, 92, 104),
        "trim":        (50, 42, 32),
        "wheel":       (14, 14, 16),
        "wheel_rim":   (62, 58, 52),
        "headlight":   (235, 215, 145),
        "taillight":   (195, 52, 42),
    },
    {   # oxidized teal
        "body":        (58, 110, 108),
        "body_dark":   (38, 76, 74),
        "body_light":  (78, 142, 138),
        "roof":        (48, 92, 90),
        "glass":       (26, 36, 44),
        "glass_light": (68, 88, 100),
        "trim":        (28, 44, 44),
        "wheel":       (14, 14, 16),
        "wheel_rim":   (58, 54, 50),
        "headlight":   (230, 210, 140),
        "taillight":   (200, 50, 40),
    },
    {   # dusty white
        "body":        (188, 184, 172),
        "body_dark":   (132, 128, 118),
        "body_light":  (215, 212, 200),
        "roof":        (168, 164, 152),
        "glass":       (30, 40, 50),
        "glass_light": (72, 92, 106),
        "trim":        (60, 56, 50),
        "wheel":       (14, 14, 16),
        "wheel_rim":   (62, 58, 52),
        "headlight":   (240, 220, 150),
        "taillight":   (200, 50, 40),
    },
    {   # sun-faded blue
        "body":        (74, 96, 128),
        "body_dark":   (50, 66, 90),
        "body_light":  (96, 120, 152),
        "roof":        (62, 82, 110),
        "glass":       (26, 36, 46),
        "glass_light": (68, 88, 102),
        "trim":        (34, 44, 58),
        "wheel":       (14, 14, 16),
        "wheel_rim":   (58, 54, 50),
        "headlight":   (230, 210, 140),
        "taillight":   (200, 50, 40),
    },
    {   # rusty brown
        "body":        (112, 78, 52),
        "body_dark":   (76, 52, 34),
        "body_light":  (140, 98, 66),
        "roof":        (94, 64, 42),
        "glass":       (28, 36, 44),
        "glass_light": (70, 86, 98),
        "trim":        (44, 30, 22),
        "wheel":       (14, 14, 16),
        "wheel_rim":   (56, 52, 48),
        "headlight":   (228, 208, 138),
        "taillight":   (195, 50, 40),
    },
]


def _car_palette(world_rect):
    """Pick a deterministic car palette from the world rect center."""
    idx = (world_rect.centerx * 7 + world_rect.centery * 13) % len(_CIVILIAN_CAR_PALETTES)
    return _CIVILIAN_CAR_PALETTES[idx]


def _draw_civilian_car(surface, r, pal):
    """Top-down civilian sedan - hood on the RIGHT, trunk on the LEFT.

    Layout (faces EAST):
      [ TRUNK .... | CABIN (roof + glass) .... | HOOD ]
      4 wheels stick out top and bottom.
      Hood has a grille slit + 2 headlights at the front edge.
      Trunk has 2 taillights at the back edge + a license-plate strip.
      Cabin has a windshield (front), rear window (back), 2 side
      windows, and a roof panel with a subtle sunroof / door lines.
    """
    # --- Soft drop shadow (offset down-right) ---
    shad = pygame.Surface((r.w + 18, r.h + 14), pygame.SRCALPHA)
    render_util.soft_shadow(shad, shad.get_rect(), 95)
    surface.blit(shad, (r.x - 4, r.y + 5))

    body = pal["body"]
    body_dark = pal["body_dark"]
    body_light = pal["body_light"]
    roof = pal["roof"]
    glass = pal["glass"]
    glass_light = pal["glass_light"]
    trim = pal["trim"]

    # --- Body - main hull with rounded corners + a subtle top highlight
    # strip and a bottom shadow strip so it reads as a 3D shape. ---
    pygame.draw.rect(surface, body, r, border_radius=7)
    # Top highlight (1px lighter along the top edge)
    pygame.draw.rect(surface, body_light,
                     (r.x, r.y, r.w, 3), border_radius=4)
    # Bottom shadow (2px darker along the bottom edge)
    pygame.draw.rect(surface, body_dark,
                     (r.x, r.bottom - 4, r.w, 4), border_radius=4)
    # Side shadow strips - a thin darker line down each long side.
    pygame.draw.line(surface, body_dark,
                     (r.x + 1, r.y + 4), (r.x + 1, r.bottom - 5), 1)
    pygame.draw.line(surface, body_dark,
                     (r.right - 2, r.y + 4), (r.right - 2, r.bottom - 5), 1)

    # --- Layout: trunk (left ~22%), cabin (middle ~52%), hood (right ~26%) ---
    trunk_w = int(r.w * 0.22)
    hood_w = int(r.w * 0.26)
    cabin_x = r.x + trunk_w
    cabin_w = r.w - trunk_w - hood_w
    hood_x = r.x + r.w - hood_w

    # --- Cabin: roof panel + glass surround ---
    # Glass surround (slightly inset, darker than body) - reads as the
    # window opening around the roof.
    glass_rect = pygame.Rect(cabin_x + 2, r.y + 4, cabin_w - 4, r.h - 8)
    pygame.draw.rect(surface, glass, glass_rect, border_radius=4)
    # Roof panel (centered inside the glass surround, leaves a glass border).
    roof_rect = pygame.Rect(cabin_x + 7, r.y + 7, cabin_w - 14, r.h - 14)
    pygame.draw.rect(surface, roof, roof_rect, border_radius=3)
    # Roof highlight strip (1px lighter along the top of the roof).
    pygame.draw.rect(surface, body_light,
                     (roof_rect.x, roof_rect.y, roof_rect.w, 2), border_radius=2)
    # Sunroof seam - a thin darker line across the roof, slightly off-center.
    sunroof_x = roof_rect.x + roof_rect.w // 2 + 2
    pygame.draw.line(surface, body_dark,
                     (sunroof_x, roof_rect.y + 2),
                     (sunroof_x, roof_rect.bottom - 2), 1)
    # Windshield highlight - 1px light blue along the front edge of the
    # glass surround (sells reflection).
    pygame.draw.line(surface, glass_light,
                     (glass_rect.right - 1, glass_rect.y + 2),
                     (glass_rect.right - 1, glass_rect.bottom - 2), 1)
    # Rear-window highlight along the back edge.
    pygame.draw.line(surface, glass_light,
                     (glass_rect.x, glass_rect.y + 2),
                     (glass_rect.x, glass_rect.bottom - 2), 1)

    # --- Door lines - 2 vertical seams dividing the cabin into front
    # and rear doors. Slightly darker than the roof. ---
    door_x1 = cabin_x + cabin_w // 3
    door_x2 = cabin_x + (cabin_w * 2) // 3
    for dx in (door_x1, door_x2):
        pygame.draw.line(surface, body_dark,
                         (dx, r.y + 5), (dx, r.bottom - 5), 1)

    # --- Hood panel + front grille + headlights ---
    # Hood sits flush with the body; add a subtle seam where it meets
    # the cabin (the cowl line).
    pygame.draw.line(surface, body_dark,
                     (hood_x, r.y + 3), (hood_x, r.bottom - 3), 1)
    # Grille slit - a dark horizontal line near the front edge.
    grille_y = r.centery
    pygame.draw.rect(surface, (20, 18, 16),
                     (hood_x + hood_w - 8, grille_y - 3, 6, 6), border_radius=1)
    # Headlights - 2 warm dots at the front corners.
    for hy in (r.y + 6, r.bottom - 8):
        pygame.draw.circle(surface, pal["headlight"],
                           (r.right - 3, hy), 2)
        pygame.draw.circle(surface, (170, 150, 90),
                           (r.right - 3, hy), 3, 1)

    # --- Trunk panel + taillights + license plate ---
    # Seam where the trunk meets the cabin.
    pygame.draw.line(surface, body_dark,
                     (r.x + trunk_w, r.y + 3), (r.x + trunk_w, r.bottom - 3), 1)
    # Taillights - 2 red dots at the back corners.
    for ty in (r.y + 6, r.bottom - 8):
        pygame.draw.circle(surface, pal["taillight"],
                           (r.x + 3, ty), 2)
        pygame.draw.circle(surface, (110, 28, 24),
                           (r.x + 3, ty), 3, 1)
    # License plate - a small lighter rect at the back edge center.
    plate = pygame.Rect(r.x - 1, r.centery - 2, 4, 5)
    pygame.draw.rect(surface, (180, 175, 160), plate)
    pygame.draw.rect(surface, (90, 88, 80), plate, 1)

    # --- Wheels (4 - 2 per side, sticking out top and bottom) ---
    # Axle positions along the car's length.
    axle_xs = [
        r.x + trunk_w + 8,         # rear axle (under trunk/cabin junction)
        hood_x + 6,                # front axle (under hood)
    ]
    wheel_r = 7
    for ax in axle_xs:
        # Top wheel (sticks up above the rect)
        pygame.draw.circle(surface, pal["wheel"], (ax, r.y - 1), wheel_r)
        pygame.draw.circle(surface, pal["wheel_rim"], (ax, r.y - 1), wheel_r, 1)
        # Hubcap
        pygame.draw.circle(surface, (95, 90, 84), (ax, r.y - 1), 2)
        # Bottom wheel (sticks down below the rect)
        pygame.draw.circle(surface, pal["wheel"], (ax, r.bottom + 1), wheel_r)
        pygame.draw.circle(surface, pal["wheel_rim"], (ax, r.bottom + 1), wheel_r, 1)
        pygame.draw.circle(surface, (95, 90, 84), (ax, r.bottom + 1), 2)

    # --- Side mirrors - 2 tiny nubs sticking out from the cabin, just
    # behind the windshield. Small but they read as mirrors at this scale. ---
    for my in (r.y + 2, r.bottom - 4):
        pygame.draw.rect(surface, body_dark,
                         (cabin_x + cabin_w - 6, my, 3, 2))

    # --- Body outline (crisp dark border) ---
    pygame.draw.rect(surface, trim, r, 2, border_radius=7)


def _draw_burned_car(surface, r, pal, world_rect, bt=0):
    """Top-down burned-out civilian sedan.

    Same silhouette as _draw_civilian_car but blackened: blistered paint,
    blown-out glass, collapsed roof, melted wheels, scorch tail behind the
    car, and a faint persistent smolder in the engine bay + cabin. Seeded
    from the world rect so the damage pattern is stable frame-to-frame.
    """
    rng = random.Random(world_rect.centerx * 41 + world_rect.centery * 23)

    # --- Scorch tail - a wide dark patch under + behind the car (the
    # fire scorched the ground around it). Drawn first so the car sits
    # on top. ---
    scorch = pygame.Surface((r.w + 40, r.h + 28), pygame.SRCALPHA)
    pygame.draw.ellipse(scorch, (8, 6, 5, 170),
                        (0, 0, r.w + 40, r.h + 28))
    # Extra oily darker center.
    pygame.draw.ellipse(scorch, (4, 3, 3, 120),
                        (20, 8, r.w, r.h + 12))
    surface.blit(scorch, (r.x - 20, r.y - 8))

    # --- Charred palette - everything is blackened/ashy, with faint
    # hints of the original paint color showing through in patches. ---
    hull_black = (16, 13, 11)
    hull_dark = (26, 21, 18)
    hull_mid = (38, 32, 27)
    hull_light = (52, 44, 36)
    soot_col = (8, 6, 5)

    # --- Body - blackened hull. ---
    pygame.draw.rect(surface, hull_dark, r, border_radius=7)
    # Blistered paint patches - irregular lighter blotches where the
    # original paint bubbled + peeled, showing hints of the car's color.
    paint = pal["body"]
    for _ in range(5):
        bx = rng.randint(r.x + 4, r.right - 12)
        by = rng.randint(r.y + 4, r.bottom - 10)
        bw = rng.randint(10, 22)
        bh = rng.randint(6, 14)
        # Faint paint remnant - heavily darkened original color.
        col = (max(8, paint[0] // 3), max(6, paint[1] // 3), max(5, paint[2] // 3))
        patch = pygame.Surface((bw, bh), pygame.SRCALPHA)
        pygame.draw.ellipse(patch, (*col, 120), (0, 0, bw, bh))
        surface.blit(patch, (bx, by))
    # Heavy soot smudges across the whole body.
    soot = pygame.Surface((r.w, r.h), pygame.SRCALPHA)
    for _ in range(7):
        sx = rng.randint(0, max(1, r.w - 30))
        sy = rng.randint(0, max(1, r.h - 18))
        sw = rng.randint(16, 32)
        sh = rng.randint(10, 20)
        pygame.draw.ellipse(soot, (*soot_col, rng.randint(120, 180)),
                            (sx, sy, sw, sh))
    surface.blit(soot, (r.x, r.y))

    # --- Layout (same as the civilian car) ---
    trunk_w = int(r.w * 0.22)
    hood_w = int(r.w * 0.26)
    cabin_x = r.x + trunk_w
    cabin_w = r.w - trunk_w - hood_w
    hood_x = r.x + r.w - hood_w

    # --- Cabin: roof collapsed into the cabin - no glass, just a dark
    # cavity with charred framing. ---
    cabin_rect = pygame.Rect(cabin_x + 2, r.y + 4, cabin_w - 4, r.h - 8)
    pygame.draw.rect(surface, (5, 4, 3), cabin_rect, border_radius=3)
    # Collapsed roof ribs - a few twisted dark lines across the cavity.
    for _ in range(4):
        rx1 = rng.randint(cabin_rect.x + 3, cabin_rect.right - 3)
        ry1 = rng.randint(cabin_rect.y + 2, cabin_rect.bottom - 2)
        rx2 = rx1 + rng.randint(-10, 10)
        ry2 = ry1 + rng.randint(-6, 6)
        pygame.draw.line(surface, hull_light, (rx1, ry1), (rx2, ry2), 2)
        pygame.draw.line(surface, hull_mid, (rx1, ry1), (rx2, ry2), 1)

    # --- Door lines - still visible but charred. ---
    door_x1 = cabin_x + cabin_w // 3
    door_x2 = cabin_x + (cabin_w * 2) // 3
    for dx in (door_x1, door_x2):
        pygame.draw.line(surface, hull_black,
                         (dx, r.y + 5), (dx, r.bottom - 5), 1)

    # --- Hood seam + grille (melted). ---
    pygame.draw.line(surface, hull_black,
                     (hood_x, r.y + 3), (hood_x, r.bottom - 3), 1)
    # Melted grille - a darker blob.
    pygame.draw.rect(surface, (4, 3, 3),
                     (hood_x + hood_w - 8, r.centery - 3, 6, 6), border_radius=2)

    # --- Trunk seam. ---
    pygame.draw.line(surface, hull_black,
                     (r.x + trunk_w, r.y + 3), (r.x + trunk_w, r.bottom - 3), 1)

    # --- Smoldering glow in the cabin + engine bay - fire still burning
    # inside. Slow pulse, seeded phase so it's independent of other cars. ---
    pulse = 0.55 + 0.45 * math.sin(bt * rng.uniform(0.08, 0.16) + rng.uniform(0, math.tau))
    # Cabin glow.
    cab_glow = pygame.Surface((cabin_w - 6, r.h - 12), pygame.SRCALPHA)
    for gr, gc, ga in [(22, (255, 90, 25), int(90 * pulse)),
                       (14, (255, 140, 45), int(120 * pulse)),
                       (7, (255, 210, 110), int(150 * pulse))]:
        pygame.draw.circle(cab_glow, (*gc, ga),
                           (cab_glow.get_width() // 2, cab_glow.get_height() // 2), gr)
    surface.blit(cab_glow, (cabin_rect.x + 3, cabin_rect.y + 3))
    # Engine-bay glow (front).
    eng_glow = pygame.Surface((20, 16), pygame.SRCALPHA)
    pygame.draw.ellipse(eng_glow, (255, 100, 30, int(130 * pulse)), (0, 0, 20, 16))
    pygame.draw.ellipse(eng_glow, (255, 200, 90, int(90 * pulse)), (5, 3, 10, 10))
    surface.blit(eng_glow, (hood_x + 4, r.centery - 8))

    # --- Headlights / taillights - shattered, dark. ---
    for hy in (r.y + 6, r.bottom - 8):
        pygame.draw.circle(surface, (14, 11, 9), (r.right - 3, hy), 2)
    for ty in (r.y + 6, r.bottom - 8):
        pygame.draw.circle(surface, (40, 12, 10), (r.x + 3, ty), 2)

    # --- Wheels - melted / deflated. Drawn as dark blobs, smaller than
    # the civilian car's wheels, with no rim detail. ---
    axle_xs = [
        r.x + trunk_w + 8,
        hood_x + 6,
    ]
    for ax in axle_xs:
        # Melted top wheel - flattened ellipse.
        pygame.draw.ellipse(surface, hull_black,
                            (ax - 6, r.y - 4, 12, 7))
        pygame.draw.ellipse(surface, hull_mid,
                            (ax - 6, r.y - 4, 12, 7), 1)
        # Melted bottom wheel.
        pygame.draw.ellipse(surface, hull_black,
                            (ax - 6, r.bottom - 3, 12, 7))
        pygame.draw.ellipse(surface, hull_mid,
                            (ax - 6, r.bottom - 3, 12, 7), 1)

    # --- Body outline - charred, slightly irregular. ---
    pygame.draw.rect(surface, (6, 5, 4), r, 2, border_radius=7)


def _draw_car_burn_overlay(surface, r, world_rect, burn_progress):
    """Mid-burn overlay drawn ON TOP of the intact civilian car.

    As burn_progress climbs 0.0 → 1.0:
      - Soot patches grow across the body (alpha + count scale with bp).
      - The cabin glass darkens (smoke inside the cabin).
      - An escalating flame glow rises from the hood + cabin.
      - Flickering flame tongues lick up from the body.

    Seeded from the world rect so the soot pattern is stable frame-to-frame.
    Once burn_progress hits 1.0 the car flips to "burned" kind and this
    overlay is no longer used (the permanent _draw_burned_car takes over).
    """
    rng = random.Random(world_rect.centerx * 41 + world_rect.centery * 23 + 99)
    bp = max(0.0, min(1.0, burn_progress))
    ticks = _now_ms()

    # --- Soot overlay - grows with burn progress. ---
    soot_alpha = int(180 * bp)
    if soot_alpha > 10:
        soot = pygame.Surface((r.w, r.h), pygame.SRCALPHA)
        patch_count = int(3 + bp * 5)
        for _ in range(patch_count):
            sx = rng.randint(2, max(3, r.w - 24))
            sy = rng.randint(2, max(3, r.h - 18))
            sw = rng.randint(14, 30)
            sh = rng.randint(10, 20)
            pygame.draw.ellipse(soot, (8, 6, 5, soot_alpha),
                                (sx, sy, sw, sh))
        surface.blit(soot, (r.x, r.y))

    # --- Darkening cabin glass - smoke fills the interior. ---
    if bp > 0.2:
        cabin_darken = int(140 * (bp - 0.2) / 0.8)
        # Approximate cabin rect (matches _draw_civilian_car layout).
        trunk_w = int(r.w * 0.22)
        hood_w = int(r.w * 0.26)
        cabin_x = r.x + trunk_w
        cabin_w = r.w - trunk_w - hood_w
        glass_rect = pygame.Rect(cabin_x + 2, r.y + 4, cabin_w - 4, r.h - 8)
        dark = pygame.Surface((glass_rect.w, glass_rect.h), pygame.SRCALPHA)
        dark.fill((6, 5, 4, cabin_darken))
        surface.blit(dark, glass_rect.topleft)

    # --- Flame glow - rises from the hood + cabin, escalating with bp. ---
    glow_strength = bp  # 0 → 1
    if glow_strength > 0.05:
        pulse = 0.7 + 0.3 * math.sin(ticks * 0.02)
        # Big soft glow under the car (light spill on the ground).
        ground_glow = pygame.Surface((r.w + 40, r.h + 20), pygame.SRCALPHA)
        for gr, ga in [(r.h // 2 + 10, int(60 * glow_strength * pulse)),
                       (r.h // 4, int(90 * glow_strength * pulse)),
                       (8, int(120 * glow_strength * pulse))]:
            pygame.draw.ellipse(ground_glow, (255, 110, 30, ga),
                                (0, 0, r.w + 40, r.h + 20))
        surface.blit(ground_glow, (r.x - 20, r.y - 4))

        # Hot core glow on the body itself.
        core_glow = pygame.Surface((r.w, r.h), pygame.SRCALPHA)
        for gr, gc, ga in [
            (r.h // 2, (255, 90, 25), int(100 * glow_strength * pulse)),
            (r.h // 3, (255, 150, 45), int(130 * glow_strength * pulse)),
            (r.h // 5, (255, 220, 120), int(160 * glow_strength * pulse)),
        ]:
            pygame.draw.ellipse(core_glow, (*gc, ga),
                                (r.w // 2 - gr, r.h // 2 - gr // 2, gr * 2, gr))
        surface.blit(core_glow, r.topleft)

    # --- Flame tongues - flickering licks of fire rising from the body.
    # More + taller as the burn progresses. Seeded per-tongue so they
    # don't jump around frame-to-frame, but the flicker is animated. ---
    tongue_count = int(2 + bp * 5)
    for i in range(tongue_count):
        # Stable base position for this tongue.
        tx = r.x + rng.randint(8, max(10, r.w - 8))
        ty = r.y + rng.randint(4, max(6, r.h - 4))
        # Animated flicker height.
        h = int((10 + bp * 22) * (0.7 + 0.3 * math.sin(ticks * 0.03 + i * 1.7)))
        w = max(3, h // 3)
        # Outer orange flame.
        outer = [
            (tx, ty - h),
            (tx - w, ty + 3),
            (tx + w, ty + 3),
        ]
        pygame.draw.polygon(surface, (255, 90, 20), outer)
        # Inner yellow-white core.
        inner = [
            (tx, ty - h * 0.6),
            (tx - w * 0.45, ty + 1),
            (tx + w * 0.45, ty + 1),
        ]
        pygame.draw.polygon(surface, (255, 210, 90), inner)


# -- Generated vehicle sprites (Polish T7) ---------------------------------
# tools/sprites/vehicles.py bakes every car palette x rect size, the burned
# wrecks, the IPA truck (intact/charred) and the tanker into spr_vehicles.
# Frame anchors are the collision-rect top-left, so a sprite lands exactly
# where the procedural renderer drew. Any miss (legacy art, unknown size,
# missing sheet) returns False and the procedural path below runs.
_CAR_PAINT_KEYS = ("faded_red", "sand", "teal", "dusty_white", "faded_blue", "rust_brown")
_SMOULDER_PHASE = {}


def _glow_level(pulse):
    """Map a 0..1 procedural pulse onto the 4 baked glow levels."""
    return max(0, min(3, int(round(pulse * 4)) - 1))


def _blit_vehicle_sprite(surface, key, r):
    img = artpack.vehicle(key)
    if img is None:
        return False
    ax, ay = artpack.frame_anchor("spr_vehicles", key)
    surface.blit(img, (r.x - ax, r.y - ay))
    return True


def _draw_vehicle_sprite(surface, r, rect, kind, vehicle, bt):
    """Sprite path for _draw_vehicle. True when it fully handled the draw."""
    if not artpack.enabled():
        return False
    charred = bool(vehicle and vehicle.get("blast_charred"))
    if kind == "ipa_truck":
        if (rect.w, rect.h) != (160, 54):  # baked at the world.py truck size
            return False
        if not charred:
            return _blit_vehicle_sprite(surface, "ipa_truck", r)
        if not _blit_vehicle_sprite(surface, "ipa_truck_charred", r):
            return False
        _blit_vehicle_sprite(surface, "ipa_glow_%d" % _glow_level(
            0.7 + 0.3 * math.sin(bt * 0.08)), r)
        if bt % 60 < 30:  # one surviving headlight, same flicker as legacy
            pygame.draw.circle(surface, (255, 200, 100), (r.right - 3, r.y + 8), 2)
        return True
    size = "%dx%d" % (rect.w, rect.h)
    paint = _CAR_PAINT_KEYS[(rect.centerx * 7 + rect.centery * 13) % len(_CAR_PAINT_KEYS)]
    if kind == "burned" or charred:
        if not _blit_vehicle_sprite(surface, "burned_%s_%s" % (paint, size), r):
            return False
        ph = _SMOULDER_PHASE.get((rect.centerx, rect.centery))
        if ph is None:
            rng = random.Random(rect.centerx * 41 + rect.centery * 23)
            ph = (rng.uniform(0.08, 0.16), rng.uniform(0, math.tau))
            _SMOULDER_PHASE[(rect.centerx, rect.centery)] = ph
        pulse = 0.55 + 0.45 * math.sin(bt * ph[0] + ph[1])
        _blit_vehicle_sprite(surface, "smoulder_%s_%d" % (size, _glow_level(pulse)), r)
        return True
    if not _blit_vehicle_sprite(surface, "car_%s_%s" % (paint, size), r):
        return False
    bp = (vehicle.get("burn_progress", 0.0) if vehicle else 0.0)
    if vehicle and vehicle.get("burning", False) and 0.0 < bp < 1.0:
        _draw_car_burn_overlay(surface, r, rect, bp)
    return True


def _draw_vehicle(surface, rect, kind, fcx, fcy, vehicle=None):
    # If the tanker blast charred this vehicle, apply the push offset so
    # the wreck sits slightly off its original spot (reads as "blast
    # shoved it"). Set in _explode_tanker for civilian vehicles within
    # ~520px of the blast.
    off_x = off_y = 0
    if vehicle and vehicle.get("blast_charred"):
        off = vehicle.get("blast_offset", (0, 0))
        off_x, off_y = int(off[0]), int(off[1])
    r = pygame.Rect(rect.x - fcx + off_x, rect.y - fcy + off_y, rect.w, rect.h)

    if _draw_vehicle_sprite(surface, r, rect, kind, vehicle,
                            getattr(STATE, "mission2_tanker_blast_timer", 0)):
        return

    if kind == "ipa_truck":
        # Route to the wrecked variant if the tanker blast charred it.
        # Pass the WORLD-space rect (not the screen-space `r`) so the
        # wreck geometry can be seeded from a stable position - otherwise
        # the fissures/soot jitter every frame as the camera moves.
        if vehicle and vehicle.get("blast_charred"):
            bt = getattr(STATE, "mission2_tanker_blast_timer", 0)
            _draw_ipa_truck_charred(surface, r, bt, rect)
        else:
            _draw_ipa_truck(surface, r)
        return

    # --- Civilian cars + burned wrecks. Each car gets a deterministic
    # palette from its world rect center, so the same car always has the
    # same color. A car can become "burned" three ways:
    #   1. Tanker blast charring (blast_charred=True, kind flipped to
    #      "burned" in _explode_tanker).
    #   2. Molotov burning (burn_progress reaches 1.0, kind flipped to
    #      "burned" in _update_molotovs, molotov_burned=True).
    #   3. Mid-molotov-burn (burning=True, 0 < burn_progress < 1.0) -
    #      draws the intact car + an escalating charred overlay + flame
    #      glow so the player sees the car catch fire and burn.
    # All three flag conditions route to _draw_burned_car for the final
    # smoldering wreck variant; the mid-burn case is handled inline below. ---
    pal = _car_palette(rect)
    bt = getattr(STATE, "mission2_tanker_blast_timer", 0)
    bp = (vehicle.get("burn_progress", 0.0) if vehicle else 0.0)
    is_burning = bool(vehicle and vehicle.get("burning", False) and 0.0 < bp < 1.0)
    if kind == "burned" or (vehicle and vehicle.get("blast_charred")):
        _draw_burned_car(surface, r, pal, rect, bt)
    elif is_burning:
        # Mid-burn: draw the intact car, then overlay escalating char
        # + flame glow proportional to burn_progress.
        _draw_civilian_car(surface, r, pal)
        _draw_car_burn_overlay(surface, r, rect, bp)
    else:
        _draw_civilian_car(surface, r, pal)


def _draw_ipa_truck(surface, r):
    """Top-down IPA military cargo truck.

    Layout (truck faces EAST / right):
      [ CARGO CONTAINER .... | CAB ]
      6 wheels (3 axles) stick out top and bottom.
      The cargo container has panel lines, rivets, a tarp ridge, and a
      large IPA stencil. The cab has a windshield and roof.
    """
    # --- Shadow (soft offset ellipse) ---
    shad = pygame.Surface((r.w + 24, r.h + 20), pygame.SRCALPHA)
    render_util.soft_shadow(shad, shad.get_rect(), 90)
    surface.blit(shad, (r.x - 6, r.y + 4))

    # --- Colors ---
    cargo_dark  = (62, 48, 36)     # shadow side of cargo
    cargo_mid   = (78, 60, 44)     # cargo body
    cargo_light = (95, 74, 54)     # highlight side
    cab_col     = (68, 55, 42)     # cab roof
    cab_dark    = (50, 40, 30)
    windshield  = (18, 28, 38)     # dark glass
    wheel_col   = (12, 12, 14)
    wheel_rim   = (45, 42, 38)
    stencil_col = (200, 175, 130)  # cream stencil text
    rivet_col   = (45, 35, 26)

    # --- Cargo container (left ~68% of rect) ---
    cargo_w = int(r.w * 0.68)
    cargo_rect = pygame.Rect(r.x, r.y, cargo_w, r.h)
    # Base
    pygame.draw.rect(surface, cargo_mid, cargo_rect, border_radius=4)
    # Top highlight strip (1px lighter along the top edge)
    pygame.draw.rect(surface, cargo_light, (cargo_rect.x, cargo_rect.y, cargo_rect.w, 3), border_radius=2)
    # Bottom shadow strip
    pygame.draw.rect(surface, cargo_dark, (cargo_rect.x, cargo_rect.bottom - 4, cargo_rect.w, 4), border_radius=2)
    # Tarp ridge line (center, vertical - reads as a folded tarp from above)
    ridge_x = cargo_rect.x + cargo_rect.w // 2
    pygame.draw.line(surface, cargo_dark, (ridge_x, cargo_rect.y + 3), (ridge_x, cargo_rect.bottom - 5), 2)
    pygame.draw.line(surface, cargo_light, (ridge_x + 1, cargo_rect.y + 3), (ridge_x + 1, cargo_rect.bottom - 5), 1)

    # Panel seams (2 horizontal lines dividing the cargo into 3rds)
    for frac in (0.33, 0.66):
        sy = cargo_rect.y + int(cargo_rect.h * frac)
        pygame.draw.line(surface, cargo_dark, (cargo_rect.x + 2, sy), (cargo_rect.right - 2, sy), 1)

    # Rivets along the seams (small dots)
    for frac in (0.33, 0.66):
        sy = cargo_rect.y + int(cargo_rect.h * frac)
        for rx in range(cargo_rect.x + 8, cargo_rect.right - 6, 16):
            pygame.draw.circle(surface, rivet_col, (rx, sy), 1)

    # IPA stencil (large, centered on cargo)
    stencil = font_terminal.render(_T("m2.ipa"), True, stencil_col)
    # Scale up slightly for a painted-stencil look
    stencil = pygame.transform.scale(stencil, (stencil.get_width() + 6, stencil.get_height() + 4))
    surface.blit(stencil, (ridge_x - stencil.get_width() // 2, cargo_rect.y + 5))
    # Cargo number below the stencil
    num = font_terminal_small.render(_T("m2.cgo_12"), True, (160, 140, 100))
    surface.blit(num, (ridge_x - num.get_width() // 2, cargo_rect.bottom - 16))

    # Tailgate line at the back (west/left edge)
    pygame.draw.line(surface, cargo_dark, (cargo_rect.x + 1, cargo_rect.y + 2), (cargo_rect.x + 1, cargo_rect.bottom - 2), 2)
    pygame.draw.line(surface, cargo_light, (cargo_rect.x + 3, cargo_rect.y + 2), (cargo_rect.x + 3, cargo_rect.bottom - 2), 1)

    # --- Cab (right ~32% of rect) ---
    cab_rect = pygame.Rect(r.x + cargo_w, r.y, r.w - cargo_w, r.h)
    pygame.draw.rect(surface, cab_col, cab_rect, border_radius=4)
    # Cab shadow on the cargo-side edge
    pygame.draw.line(surface, cab_dark, (cab_rect.x, cab_rect.y), (cab_rect.x, cab_rect.bottom), 2)
    # Windshield (dark glass strip across the front of the cab)
    ws_rect = pygame.Rect(cab_rect.right - 18, cab_rect.y + 4, 12, cab_rect.h - 8)
    pygame.draw.rect(surface, windshield, ws_rect, border_radius=2)
    # Windshield highlight (1px light blue along the top edge)
    pygame.draw.line(surface, (60, 80, 100), (ws_rect.x, ws_rect.y), (ws_rect.right, ws_rect.y), 1)
    # Roof highlight
    pygame.draw.rect(surface, (85, 70, 52), (cab_rect.x + 2, cab_rect.y + 2, cab_rect.w - 22, 3), border_radius=2)

    # --- Wheels (6 wheels: 3 axles Ã- 2 sides) ---
    # Axle positions along the truck's length
    axle_xs = [
        cargo_rect.x + 16,                    # rear axle
        cargo_rect.x + cargo_w // 2,          # mid axle
        cab_rect.right - 14,                   # front axle (under cab)
    ]
    wheel_r = 7
    for ax in axle_xs:
        # Top wheel (sticks up above the rect)
        pygame.draw.circle(surface, wheel_col, (ax, r.y - 1), wheel_r)
        pygame.draw.circle(surface, wheel_rim, (ax, r.y - 1), wheel_r, 1)
        # Bottom wheel (sticks down below the rect)
        pygame.draw.circle(surface, wheel_col, (ax, r.bottom + 1), wheel_r)
        pygame.draw.circle(surface, wheel_rim, (ax, r.bottom + 1), wheel_r, 1)

    # --- Headlights (2 small warm dots at the front/east edge of cab) ---
    for hy in (cab_rect.y + 8, cab_rect.bottom - 10):
        pygame.draw.circle(surface, (230, 200, 120), (cab_rect.right - 3, hy), 2)
        pygame.draw.circle(surface, (180, 150, 80), (cab_rect.right - 3, hy), 3, 1)

    # --- Outline (crisp dark border around the whole truck) ---
    pygame.draw.rect(surface, (30, 22, 16), r, 2, border_radius=4)


def _draw_ipa_truck_charred(surface, r, bt, world_rect):
    """Wrecked IPA truck - drawn after the tanker blast chars it.

    The truck is ~246px from the tanker, so it takes the full force of
    the blast: blackened cargo container, buckled/twisted panels, a
    blown-out windshield with glowing cracks, missing/burned-off tarp,
    scorched wheels, and a persistent smoldering glow in the engine bay
    + cargo hold. The silhouette stays recognizable as the same truck
    the player inspected earlier, just destroyed.

    ``world_rect`` is the truck's WORLD-space rect (not screen-space).
    All wreck geometry is seeded from it so the fissures/soot/cracks
    stay locked to the truck as the camera moves - previously the seed
    used the screen-space rect (``r``), which changed every frame as
    the player walked, making the fissures jitter wildly.
    """
    # --- ONE stable RNG, seeded from the world-space rect center.
    # This never changes as the camera moves, so all the wreck geometry
    # (fissure paths, soot smudges, windshield cracks, wheel presence)
    # is stable frame-to-frame. ---
    rng = random.Random(world_rect.centerx * 31 + world_rect.centery * 17)

    # --- Shadow (darker, wider - the wreck sits heavier) ---
    shad = pygame.Surface((r.w + 30, r.h + 24), pygame.SRCALPHA)
    render_util.soft_shadow(shad, shad.get_rect(), 140)
    surface.blit(shad, (r.x - 8, r.y + 6))

    # --- Charred color palette - everything is blackened/ashy. ---
    hull_black   = (18, 14, 11)
    hull_dark    = (28, 22, 18)
    hull_mid     = (42, 34, 28)
    hull_light   = (58, 48, 38)
    soot_col     = (10, 8, 7)
    glow_col     = (255, 100, 30)
    glow_core    = (255, 200, 90)
    crack_col    = (255, 80, 25)

    cargo_w = int(r.w * 0.68)
    cargo_rect = pygame.Rect(r.x, r.y, cargo_w, r.h)
    cab_rect = pygame.Rect(r.x + cargo_w, r.y, r.w - cargo_w, r.h)

    # --- Cargo container - blackened, buckled. ---
    pygame.draw.rect(surface, hull_dark, cargo_rect, border_radius=4)
    # Buckled roof - irregular darker patches where the metal caved in.
    for bx, by, bw, bh in [
        (cargo_rect.x + 6, cargo_rect.y + 3, cargo_w // 3, r.h - 8),
        (cargo_rect.x + cargo_w // 2 - 10, cargo_rect.y + 2, 28, r.h - 6),
        (cargo_rect.right - cargo_w // 3, cargo_rect.y + 4, cargo_w // 4, r.h - 10),
    ]:
        pygame.draw.rect(surface, hull_black, (bx, by, bw, bh), border_radius=3)
    # Heavy soot smudges across the whole cargo. Pre-computed from the
    # stable rng so they don't jitter.
    soot = pygame.Surface((cargo_w, r.h), pygame.SRCALPHA)
    for _ in range(6):
        sx = rng.randint(0, max(1, cargo_w - 36))
        sy = rng.randint(0, max(1, r.h - 26))
        sw = rng.randint(18, 36)
        sh = rng.randint(14, 26)
        sa = rng.randint(100, 160)
        pygame.draw.ellipse(soot, (*soot_col, sa), (sx, sy, sw, sh))
    surface.blit(soot, (cargo_rect.x, cargo_rect.y))

    # Tarp ridge - burned away, just a twisted metal rib left. Offset
    # is stable from the rng.
    ridge_x = cargo_rect.x + cargo_w // 2
    ridge_offset = rng.randint(-3, 3)
    pygame.draw.line(surface, hull_black, (ridge_x, cargo_rect.y + 3),
                     (ridge_x + ridge_offset, cargo_rect.bottom - 5), 3)
    pygame.draw.line(surface, hull_light, (ridge_x + 1, cargo_rect.y + 3),
                     (ridge_x + 1, cargo_rect.bottom - 5), 1)

    # Panel seams - still visible but charred.
    for frac in (0.33, 0.66):
        sy = cargo_rect.y + int(cargo_rect.h * frac)
        pygame.draw.line(surface, hull_black,
                         (cargo_rect.x + 2, sy), (cargo_rect.right - 2, sy), 1)

    # IPA stencil - scorched/peeling. Render faintly so it's barely
    # readable, sells that the truck is the same one from before.
    stencil = font_terminal.render(_T("m2.ipa"), True, (70, 58, 42))
    stencil = pygame.transform.scale(stencil, (stencil.get_width() + 6, stencil.get_height() + 4))
    stencil.set_alpha(120)
    surface.blit(stencil, (ridge_x - stencil.get_width() // 2, cargo_rect.y + 5))

    # --- Pre-compute fissure geometry ONCE from the stable rng, then
    # draw with a per-fissure pulse so they flicker independently instead
    # of all brightening/dimming in lockstep (which looked mechanical).
    # Each fissure gets its own phase offset + slightly different pulse
    # speed so the overall glow reads as natural smoldering, not a
    # synchronized strobe. ---
    fissures = []
    for _ in range(6):
        fx = rng.randint(cargo_rect.x + 6, cargo_rect.right - 6)
        fy = rng.randint(cargo_rect.y + 4, cargo_rect.bottom - 4)
        segs = rng.randint(2, 4)
        pts = [(fx, fy)]
        for _seg in range(segs):
            pts.append((pts[-1][0] + rng.randint(-18, 18),
                        pts[-1][1] + rng.randint(-10, 10)))
        fissures.append({
            "pts": pts,
            "phase": rng.uniform(0, math.tau),   # independent flicker phase
            "speed": rng.uniform(0.10, 0.22),    # independent flicker speed
        })
    for fis in fissures:
        # Per-fissure pulse - each crack glows on its own rhythm.
        p = 0.55 + 0.45 * math.sin(bt * fis["speed"] + fis["phase"])
        pts = fis["pts"]
        for seg in range(len(pts) - 1):
            pygame.draw.line(surface, (*crack_col, int(170 * p)),
                             pts[seg], pts[seg + 1], 3)
            pygame.draw.line(surface, (*glow_core, int(140 * p)),
                             pts[seg], pts[seg + 1], 1)

    # --- Smoldering glow in the cargo hold - fire still burning inside.
    # Slow overall pulse, independent of the fissure flicker. ---
    cargo_pulse = 0.7 + 0.3 * math.sin(bt * 0.08)
    cargo_glow = pygame.Surface((cargo_w - 20, r.h - 16), pygame.SRCALPHA)
    for gr, gc, ga in [(40, (255, 90, 25), int(80 * cargo_pulse)),
                       (24, (255, 150, 45), int(110 * cargo_pulse)),
                       (12, (255, 220, 120), int(140 * cargo_pulse))]:
        pygame.draw.circle(cargo_glow, (*gc, ga),
                           (cargo_glow.get_width() // 2, cargo_glow.get_height() // 2), gr)
    surface.blit(cargo_glow, (cargo_rect.x + 10, cargo_rect.y + 8))

    # --- Cab - blackened, windshield blown out. ---
    pygame.draw.rect(surface, hull_dark, cab_rect, border_radius=4)
    pygame.draw.line(surface, hull_black,
                     (cab_rect.x, cab_rect.y), (cab_rect.x, cab_rect.bottom), 2)
    # Blown-out windshield - dark hole with glowing crack edges.
    ws_rect = pygame.Rect(cab_rect.right - 18, cab_rect.y + 4, 12, cab_rect.h - 8)
    pygame.draw.rect(surface, (5, 4, 3), ws_rect, border_radius=2)
    # Cracks radiating from the windshield impact. Pre-computed from the
    # stable rng.
    ws_pulse = 0.6 + 0.4 * math.sin(bt * 0.18 + 1.5)
    for _ in range(5):
        x1 = ws_rect.x + rng.randint(2, max(3, ws_rect.w - 2))
        y1 = ws_rect.y + rng.randint(2, max(3, ws_rect.h - 2))
        x2 = x1 + rng.randint(-10, 10)
        y2 = y1 + rng.randint(-10, 10)
        pygame.draw.line(surface, (*crack_col, int(150 * ws_pulse)), (x1, y1), (x2, y2), 1)

    # --- Engine-bay smolder - persistent glow at the front of the cab. ---
    eng_pulse = 0.65 + 0.35 * math.sin(bt * 0.12 + 2.3)
    eng_glow = pygame.Surface((24, 20), pygame.SRCALPHA)
    pygame.draw.ellipse(eng_glow, (*glow_col, int(140 * eng_pulse)), (0, 0, 24, 20))
    pygame.draw.ellipse(eng_glow, (*glow_core, int(100 * eng_pulse)), (6, 4, 12, 12))
    surface.blit(eng_glow, (cab_rect.right - 22, cab_rect.centery - 10))

    # --- Wheels - scorched, one or two missing (just stubs). Which
    # wheels survived is pre-computed from the stable rng so it doesn't
    # change every frame. ---
    axle_xs = [
        cargo_rect.x + 16,
        cargo_rect.x + cargo_w // 2,
        cab_rect.right - 14,
    ]
    for i, ax in enumerate(axle_xs):
        top_alive = rng.random() > 0.25
        bot_alive = rng.random() > 0.25
        if top_alive:
            pygame.draw.circle(surface, (8, 8, 10), (ax, r.y - 1), 6)
            pygame.draw.circle(surface, (30, 28, 26), (ax, r.y - 1), 6, 1)
        else:
            # Burned-off stub.
            pygame.draw.circle(surface, hull_black, (ax, r.y - 1), 3)
        if bot_alive:
            pygame.draw.circle(surface, (8, 8, 10), (ax, r.bottom + 1), 6)
            pygame.draw.circle(surface, (30, 28, 26), (ax, r.bottom + 1), 6, 1)
        else:
            pygame.draw.circle(surface, hull_black, (ax, r.bottom + 1), 3)

    # --- Headlights - shattered, one still faintly glowing. ---
    for hy in (cab_rect.y + 8, cab_rect.bottom - 10):
        pygame.draw.circle(surface, (20, 16, 12), (cab_rect.right - 3, hy), 2)
    # One surviving headlight - flickering.
    if bt % 60 < 30:
        pygame.draw.circle(surface, (255, 200, 100),
                           (cab_rect.right - 3, cab_rect.y + 8), 2)

    # --- Outline - charred, irregular. ---
    pygame.draw.rect(surface, (8, 6, 5), r, 2, border_radius=4)


def _draw_tanker_dynamic(surface, valve_body_rect, pipe_cx, outlet_bottom,
                         inspected, fuel_col=(45, 38, 25)):
    """Mission-state parts of the tanker (LED + growing fuel pool).

    Shared by the procedural renderer and the T7 sprite path, which bakes
    the static truck into spr_vehicles and draws only these on top.
    """
    # === Hidden detonator LED (only visible after inspection AND before
    # the blast - after the blast the tanker is gone, so the LED must
    # disappear too, otherwise it floats in mid-air over the wreckage.)
    if inspected and not getattr(STATE, "mission2_tanker_destroyed", False):
        led_pulse = 0.5 + 0.5 * math.sin(_now_ms() * 0.15)
        led_col = (255, int(40 + 60 * led_pulse), 30)
        # LED body - small dark rectangle on the side of the valve body
        led_x = valve_body_rect.right - 2
        led_y = valve_body_rect.y + 2
        pygame.draw.rect(surface, (25, 22, 20), (led_x, led_y, 4, 3))
        # LED glow dot
        pygame.draw.circle(surface, led_col, (led_x + 2, led_y + 1), 1)
        glow = pygame.Surface((10, 10), pygame.SRCALPHA)
        pygame.draw.circle(glow, (255, 40, 30, int(80 * led_pulse)), (5, 5), 4)
        surface.blit(glow, (led_x - 3, led_y - 4))
        # Wire - thin dark line from LED back into the valve body
        pygame.draw.line(surface, (40, 35, 30), (led_x, led_y + 1), (led_x - 4, led_y + 1), 1)

    # --- Leaking fuel pool (grows over time) ---
    # Pool grows from the outlet flange downward, expanding each frame.
    # Use a deterministic growth based on mission2_timer so it doesn't
    # reset on every draw call.
    # After the tanker is destroyed, the pool shouldn't render anymore.
    if not getattr(STATE, "mission2_tanker_destroyed", False):
        pool_age = getattr(STATE, "mission2_timer", 0)
        pool_growth = min(40, pool_age // 8)
        pool_w = 60 + pool_growth
        pool_h = 20 + pool_growth // 2
        pool = pygame.Surface((pool_w, pool_h), pygame.SRCALPHA)
        pygame.draw.ellipse(pool, (*fuel_col, 140), (0, 0, pool_w, pool_h))
        pygame.draw.ellipse(pool, (*fuel_col, 80), (4, 4, pool_w - 8, pool_h - 8), 2)
        for i in range(3):
            pygame.draw.circle(pool, (90, 80, 50, 100),
                               (10 + i * 14, 6 + (i % 2) * 3), 2)
        # Pool sits just below the outlet flange
        surface.blit(pool, (pipe_cx - pool_w // 2, outlet_bottom - 2))


def _draw_tanker(surface, fcx, fcy):
    """Top-down leaking fuel tanker with hidden detonator.

    Layout (tanker faces EAST / right):
      [ CAB ] [ CYLINDRICAL TANK BODY with cradle + manifold ]
      6 wheels. Tank has end caps, hazard diamonds, IPA stencil.
      A growing fuel pool leaks from the manifold valve. After the
      player inspects, a small red detonator LED blinks on the manifold.
    """
    # After the blast, the tanker is gone - the wreckage is drawn by
    # _draw_tanker_blast_fx instead.
    if getattr(STATE, "mission2_tanker_destroyed", False):
        return
    rect = STATE.mission2_tanker_rect
    x, y = rect.x - fcx, rect.y - fcy
    exploded = getattr(STATE, "mission2_tanker_exploded", False)
    inspected = getattr(STATE, "mission2_tanker_inspected", False)

    # T7 sprite path: static truck baked in spr_vehicles; only the LED and
    # fuel pool (mission state) are drawn live, with the legacy geometry.
    if artpack.enabled() and (rect.w, rect.h) == (308, 176) and _blit_vehicle_sprite(
            surface, "tanker_wreck" if exploded else "tanker",
            pygame.Rect(x, y, rect.w, rect.h)):
        if not exploded:
            cab_w = int(rect.w * 0.18)
            pipe_cx = x + cab_w + (rect.w - cab_w) // 2
            _draw_tanker_dynamic(surface, pygame.Rect(pipe_cx - 11, y + rect.h + 14, 22, 16),
                                 pipe_cx, y + rect.h + 46, inspected)
        return

    if exploded:
        pygame.draw.ellipse(surface, (0, 0, 0), (x - 15, y + 22, rect.w + 30, rect.h + 42))
        pygame.draw.rect(surface, (28, 24, 22), (x, y, rect.w, rect.h), border_radius=22)
        pygame.draw.rect(surface, (60, 45, 35), (x, y, rect.w, rect.h), 2, border_radius=22)
        pygame.draw.ellipse(surface, (12, 10, 9), (x + 20, y + 10, rect.w - 40, rect.h - 20))
        return

    # --- Shadow ---
    shad = pygame.Surface((rect.w + 30, rect.h + 30), pygame.SRCALPHA)
    render_util.soft_shadow(shad, shad.get_rect(), 100)
    surface.blit(shad, (x - 8, y + 8))

    # --- Colors ---
    tank_dark   = (62, 58, 50)
    tank_mid    = (88, 82, 70)
    tank_light  = (115, 108, 92)
    cab_col     = (70, 66, 56)
    cab_dark    = (50, 46, 38)
    windshield  = (20, 30, 42)
    wheel_col   = (12, 12, 14)
    wheel_rim   = (50, 46, 40)
    hazard_col  = (220, 160, 30)
    hazard_text = (20, 16, 8)
    stencil_col = (200, 175, 130)
    rivet_col   = (40, 36, 30)
    manifold_col = (45, 48, 52)
    valve_col    = (140, 35, 30)
    fuel_col     = (45, 38, 25)

    # --- Cab (left ~18% of rect) ---
    cab_w = int(rect.w * 0.18)
    cab_rect = pygame.Rect(x, y, cab_w, rect.h)
    pygame.draw.rect(surface, cab_col, cab_rect, border_radius=4)
    pygame.draw.line(surface, cab_dark, (cab_rect.right - 1, cab_rect.y), (cab_rect.right - 1, cab_rect.bottom), 2)
    ws_rect = pygame.Rect(cab_rect.x + 2, cab_rect.y + 4, 10, cab_rect.h - 8)
    pygame.draw.rect(surface, windshield, ws_rect, border_radius=2)
    pygame.draw.line(surface, (60, 80, 100), (ws_rect.x, ws_rect.y), (ws_rect.right, ws_rect.y), 1)
    pygame.draw.rect(surface, (90, 84, 72), (cab_rect.x + 2, cab_rect.y + 2, cab_rect.w - 4, 3), border_radius=2)
    pygame.draw.circle(surface, (230, 200, 120), (cab_rect.x + 3, cab_rect.y + 8), 2)
    pygame.draw.circle(surface, (230, 200, 120), (cab_rect.x + 3, cab_rect.bottom - 10), 2)

    # --- Cylindrical tank body (right ~82% of rect) ---
    tank_rect = pygame.Rect(x + cab_w, y, rect.w - cab_w, rect.h)
    pygame.draw.rect(surface, tank_mid, tank_rect, border_radius=18)
    pygame.draw.rect(surface, tank_light, (tank_rect.x, tank_rect.y, tank_rect.w, 4), border_radius=2)
    pygame.draw.rect(surface, tank_dark, (tank_rect.x, tank_rect.bottom - 5, tank_rect.w, 5), border_radius=2)

    # End cap (east/right end)
    cap_rect = pygame.Rect(tank_rect.right - 24, tank_rect.y + 2, 24, tank_rect.h - 4)
    pygame.draw.ellipse(surface, tank_dark, cap_rect)
    pygame.draw.ellipse(surface, tank_light, cap_rect, 1)
    for ry in range(cap_rect.y + 8, cap_rect.bottom - 4, 12):
        pygame.draw.circle(surface, rivet_col, (cap_rect.centerx, ry), 1)

    # Tank longitudinal seam
    seam_y = tank_rect.centery
    pygame.draw.line(surface, tank_dark, (tank_rect.x + 4, seam_y), (tank_rect.right - 14, seam_y), 1)
    pygame.draw.line(surface, tank_light, (tank_rect.x + 4, seam_y - 1), (tank_rect.right - 14, seam_y - 1), 1)

    # Banding hoops
    for frac in (0.25, 0.50, 0.75):
        bx = tank_rect.x + int(tank_rect.w * frac)
        pygame.draw.line(surface, tank_dark, (bx, tank_rect.y + 4), (bx, tank_rect.bottom - 6), 2)
        pygame.draw.line(surface, tank_light, (bx + 1, tank_rect.y + 4), (bx + 1, tank_rect.bottom - 6), 1)

    # Hazard diamonds
    for hx in (tank_rect.x + int(tank_rect.w * 0.35), tank_rect.x + int(tank_rect.w * 0.65)):
        diamond = [
            (hx, tank_rect.y + 10),
            (hx + 10, tank_rect.y + 20),
            (hx, tank_rect.y + 30),
            (hx - 10, tank_rect.y + 20),
        ]
        pygame.draw.polygon(surface, hazard_col, diamond)
        pygame.draw.polygon(surface, (20, 16, 8), diamond, 1)
        cls = font_terminal_small.render(_T("m2.3"), True, hazard_text)
        cls = pygame.transform.scale(cls, (cls.get_width() // 2 + 1, cls.get_height() // 2 + 1))
        surface.blit(cls, (hx - cls.get_width() // 2, tank_rect.y + 16))

    # IPA stencil
    stencil = font_terminal.render(_T("m2.ipa"), True, stencil_col)
    stencil = pygame.transform.scale(stencil, (stencil.get_width() + 4, stencil.get_height() + 3))
    surface.blit(stencil, (tank_rect.centerx - stencil.get_width() // 2, tank_rect.y + 8))
    fuel_lbl = font_terminal_small.render(_T("m2.fuel"), True, (220, 200, 160))
    surface.blit(fuel_lbl, (tank_rect.centerx - fuel_lbl.get_width() // 2, tank_rect.y + 28))

    # --- Valve manifold - top-down pipe run with hand-wheel gate valve ---
    #
    # From the player's top-down view, a pipe is a long thin rectangle.
    # To read as a CYLINDER (not a flat bar), it needs:
    #   - parallel edges with a lighter center stripe (cylinder highlight)
    #   - bolted flanges at each joint (wider rectangles perpendicular
    #     to the pipe, with visible bolt circles)
    #   - a distinct valve body in the middle (slightly wider section)
    #   - the hand-wheel sitting on top of the valve body
    #
    # Layout (pipe runs SOUTH from the tank's south edge):
    #
    #   ┌──────── tank ────────┐
    #   │                      │
    #   └═══════ flange ═══════┘   ← welded to tank, 4 bolts
    #            ║   ║              ← pipe segment 1 (vertical, with highlight)
    #            ║   ║
    #         ┌──╫───╫──┐           ← valve body (wider, with bonnet)
    #         â”‚  â•‘ ●¯ â•‘  â”‚           â† hand-wheel on top of valve
    #         └──╫───╫──┘
    #            ║   ║              ← pipe segment 2
    #            ║   ║
    #   ─────── ═══════ ─────────   ← outlet flange, 4 bolts
    #            drip...             ← fuel leak pool below

    pipe_cx = tank_rect.centerx
    pipe_w = 10           # pipe outer width
    pipe_w_inner = 6      # pipe inner channel width
    flange_w = 22         # flange width (wider than pipe)
    flange_h = 6          # flange thickness

    # Steel colors - gradient suggests cylindrical highlight
    pipe_dark  = (45, 48, 52)    # pipe edges (shadow side)
    pipe_mid   = (70, 74, 80)    # pipe body
    pipe_light = (110, 115, 122) # pipe center highlight (cylinder sheen)
    flange_col = (55, 58, 64)    # flange body
    flange_dark = (32, 34, 38)   # flange shadow
    bolt_col   = (20, 22, 24)    # bolt heads
    bolt_rim   = (90, 92, 95)    # bolt rim highlight
    valve_body_col = (60, 62, 66)  # valve body steel
    valve_bonnet_col = (45, 47, 50)  # valve bonnet (darker)

    # === Pipe segment 1: tank outlet to valve body ===
    seg1_y_top = tank_rect.bottom - 2
    seg1_y_bot = tank_rect.bottom + 14
    seg1_h = seg1_y_bot - seg1_y_top
    # Outer (dark edges)
    pygame.draw.rect(surface, pipe_dark,
                     (pipe_cx - pipe_w // 2, seg1_y_top, pipe_w, seg1_h))
    # Inner (mid)
    pygame.draw.rect(surface, pipe_mid,
                     (pipe_cx - pipe_w_inner // 2, seg1_y_top, pipe_w_inner, seg1_h))
    # Center highlight (1px light line - reads as cylinder sheen)
    pygame.draw.line(surface, pipe_light,
                     (pipe_cx, seg1_y_top), (pipe_cx, seg1_y_bot - 1), 1)

    # === Tank outlet flange (welded to tank's south edge) ===
    outlet_flange_rect = pygame.Rect(
        pipe_cx - flange_w // 2, tank_rect.bottom - 3, flange_w, flange_h
    )
    pygame.draw.rect(surface, flange_col, outlet_flange_rect, border_radius=1)
    pygame.draw.rect(surface, flange_dark, outlet_flange_rect, 1, border_radius=1)
    # Flange bolts - 4 bolts in a row across the flange
    for bx in (outlet_flange_rect.x + 3,
               outlet_flange_rect.x + 8,
               outlet_flange_rect.right - 8,
               outlet_flange_rect.right - 3):
        pygame.draw.circle(surface, bolt_col, (bx, outlet_flange_rect.centery), 2)
        pygame.draw.circle(surface, bolt_rim, (bx, outlet_flange_rect.centery), 2, 1)

    # === Valve body (wider section in the middle of the pipe run) ===
    valve_body_w = 22
    valve_body_h = 16
    valve_body_rect = pygame.Rect(
        pipe_cx - valve_body_w // 2,
        seg1_y_bot,
        valve_body_w,
        valve_body_h
    )
    # Body main
    pygame.draw.rect(surface, valve_body_col, valve_body_rect, border_radius=2)
    # Body outline
    pygame.draw.rect(surface, flange_dark, valve_body_rect, 1, border_radius=2)
    # Bonnet - a smaller darker rectangle on top of the body where the
    # stem comes up. Reads as the valve's packing gland.
    bonnet_rect = pygame.Rect(
        pipe_cx - 6, valve_body_rect.y + 2, 12, 5
    )
    pygame.draw.rect(surface, valve_bonnet_col, bonnet_rect, border_radius=1)
    pygame.draw.rect(surface, flange_dark, bonnet_rect, 1, border_radius=1)
    # Body bolts - 2 bolts on each side of the body (where it bolts to the pipe)
    for bx in (valve_body_rect.x + 3, valve_body_rect.right - 4):
        pygame.draw.circle(surface, bolt_col, (bx, valve_body_rect.y + 3), 1)
        pygame.draw.circle(surface, bolt_col, (bx, valve_body_rect.bottom - 3), 1)

    # === Hand-wheel on top of the valve body ===
    # Sits on the bonnet, larger than the body so it's clearly visible.
    wheel_cx = pipe_cx
    wheel_cy = valve_body_rect.centery
    wheel_r = 10  # outer radius - bigger than before so it reads
    # Wheel rim (dark red outer)
    pygame.draw.circle(surface, (85, 22, 18), (wheel_cx, wheel_cy), wheel_r)
    # Wheel rim inner highlight (lighter red ring)
    pygame.draw.circle(surface, (160, 45, 35), (wheel_cx, wheel_cy), wheel_r, 2)
    # Wheel center (dark - gap between rim and hub)
    pygame.draw.circle(surface, (30, 10, 8), (wheel_cx, wheel_cy), wheel_r - 2)
    # Spokes - 4 spokes at 0°/45°/90°/135°, drawn AFTER the dark center
    spoke_col = (150, 40, 30)
    for angle_deg in (0, 45, 90, 135):
        a = math.radians(angle_deg)
        sx = wheel_cx + int(2 * math.cos(a))
        sy = wheel_cy + int(2 * math.sin(a))
        ex = wheel_cx + int((wheel_r - 1) * math.cos(a))
        ey = wheel_cy + int((wheel_r - 1) * math.sin(a))
        pygame.draw.line(surface, spoke_col, (sx, sy), (ex, ey), 2)
    # Hub - central steel boss
    pygame.draw.circle(surface, (70, 72, 78), (wheel_cx, wheel_cy), 3)
    pygame.draw.circle(surface, (30, 30, 33), (wheel_cx, wheel_cy), 3, 1)
    # Stem dot
    pygame.draw.circle(surface, (110, 112, 118), (wheel_cx, wheel_cy), 1)

    # === Pipe segment 2: valve body to outlet ===
    seg2_y_top = valve_body_rect.bottom
    seg2_y_bot = seg2_y_top + 12
    seg2_h = seg2_y_bot - seg2_y_top
    pygame.draw.rect(surface, pipe_dark,
                     (pipe_cx - pipe_w // 2, seg2_y_top, pipe_w, seg2_h))
    pygame.draw.rect(surface, pipe_mid,
                     (pipe_cx - pipe_w_inner // 2, seg2_y_top, pipe_w_inner, seg2_h))
    pygame.draw.line(surface, pipe_light,
                     (pipe_cx, seg2_y_top), (pipe_cx, seg2_y_bot - 1), 1)

    # === Outlet flange at the end of the pipe (where fuel drips out) ===
    outlet2_rect = pygame.Rect(
        pipe_cx - flange_w // 2, seg2_y_bot - 2, flange_w, flange_h
    )
    pygame.draw.rect(surface, flange_col, outlet2_rect, border_radius=1)
    pygame.draw.rect(surface, flange_dark, outlet2_rect, 1, border_radius=1)
    for bx in (outlet2_rect.x + 3,
               outlet2_rect.x + 8,
               outlet2_rect.right - 8,
               outlet2_rect.right - 3):
        pygame.draw.circle(surface, bolt_col, (bx, outlet2_rect.centery), 2)
        pygame.draw.circle(surface, bolt_rim, (bx, outlet2_rect.centery), 2, 1)

    _draw_tanker_dynamic(surface, valve_body_rect, pipe_cx, outlet2_rect.bottom,
                         inspected, fuel_col)

    # --- Wheels (6 wheels: 3 axles Ã- 2 sides) ---
    axle_xs = [
        cab_rect.x + 14,
        tank_rect.x + int(tank_rect.w * 0.35),
        tank_rect.x + int(tank_rect.w * 0.75),
    ]
    wheel_r = 8
    for ax in axle_xs:
        pygame.draw.circle(surface, wheel_col, (ax, y - 1), wheel_r)
        pygame.draw.circle(surface, wheel_rim, (ax, y - 1), wheel_r, 1)
        pygame.draw.circle(surface, wheel_col, (ax, y + rect.h + 1), wheel_r)
        pygame.draw.circle(surface, wheel_rim, (ax, y + rect.h + 1), wheel_r, 1)

    # --- Outline ---
    pygame.draw.rect(surface, (28, 24, 20), (x, y, rect.w, rect.h), 2, border_radius=18)


# -- Generated story-prop sprites (Polish T7) -------------------------------
_SPRITE_PROPS = ("cone", "barrel", "sign", "broken_camera", "spark_box",
                 "puddle", "soot", "flare")
_CHARRABLE_PROPS = ("cone", "barrel", "sign")


def _draw_story_prop_sprite(surface, prop, kind, sx, sy, charred, age, pulse):
    """Sprite path for _draw_story_prop; live-state accents stay procedural."""
    if kind not in _SPRITE_PROPS or not artpack.enabled():
        return False
    key = kind + ("_charred" if charred and kind in _CHARRABLE_PROPS else "")
    if artpack.prop(key) is None:
        return False
    if kind == "flare":  # glow sits under the stick, as in the legacy draw
        glow = pygame.Surface((70, 50), pygame.SRCALPHA)
        pygame.draw.ellipse(glow, (255, 80, 25, int(45 + 40 * pulse)), (0, 10, 70, 30))
        surface.blit(glow, (sx - 35, sy - 24))
    artpack.blit_frame(surface, "spr_props_m2", key, (sx, sy))
    if kind == "puddle" and prop.get("scorched", False):
        artpack.blit_frame(surface, "spr_props_m2", "puddle_scorch", (sx, sy))
    elif kind == "spark_box" and age % 45 < 10:
        for i in range(5):
            ang = i / 5.0 * math.tau + age * 0.12
            pygame.draw.line(surface, (255, 210, 90), (sx, sy),
                             (sx + math.cos(ang) * 18, sy + math.sin(ang) * 12), 1)
    elif kind == "cone" and charred and age % 40 < 20:
        glow = pygame.Surface((24, 16), pygame.SRCALPHA)
        pygame.draw.ellipse(glow, (255, 90, 30, 80), (0, 0, 24, 16))
        surface.blit(glow, (sx - 12, sy - 2))
    elif kind == "barrel" and charred and age % 50 < 25:
        glow = pygame.Surface((28, 10), pygame.SRCALPHA)
        pygame.draw.ellipse(glow, (255, 100, 30, 100), (0, 0, 28, 10))
        surface.blit(glow, (sx - 14, sy - 16))
    return True


def _draw_story_prop(surface, prop, fcx, fcy):
    """Small non-interactive environmental props spawned by trigger zones."""
    sx, sy = _world(prop["pos"], fcx, fcy)
    kind = prop.get("kind", "soot")
    age = prop.get("age", 0)
    pulse = 0.5 + 0.5 * math.sin(_now_ms() * 0.008 + sx * 0.01)
    # --- Blast damage: if the tanker explosion charred/tipped this prop,
    # offset its draw position (knocked over, away from the blast) and
    # render a blackened variant. Set in _explode_tanker for props within
    # ~380px of the blast. ---
    charred = prop.get("charred", False)
    if charred:
        sx += int(prop.get("tip_dx", 0))
        sy += int(prop.get("tip_dy", 0))
    if _draw_story_prop_sprite(surface, prop, kind, sx, sy, charred, age, pulse):
        return
    if kind == "flare":
        glow = pygame.Surface((70, 50), pygame.SRCALPHA)
        pygame.draw.ellipse(glow, (255, 80, 25, int(45 + 40 * pulse)), (0, 10, 70, 30))
        surface.blit(glow, (sx - 35, sy - 24))
        pygame.draw.rect(surface, (95, 35, 25), (sx - 10, sy - 3, 20, 6), border_radius=2)
        pygame.draw.circle(surface, (255, 190, 75), (sx + 9, sy), 4)
    elif kind == "soot":
        patch = pygame.Surface((95, 60), pygame.SRCALPHA)
        pygame.draw.ellipse(patch, (8, 7, 6, 120), (0, 0, 95, 60))
        pygame.draw.ellipse(patch, (55, 42, 28, 45), (10, 8, 76, 42), 2)
        surface.blit(patch, (sx - 48, sy - 30))
    elif kind == "broken_camera":
        pygame.draw.rect(surface, (28, 32, 34), (sx - 16, sy - 9, 32, 18), border_radius=3)
        pygame.draw.circle(surface, (5, 7, 8), (sx + 8, sy), 7)
        pygame.draw.line(surface, (80, 84, 82), (sx - 14, sy - 8), (sx - 28, sy - 24), 2)
        pygame.draw.line(surface, (125, 40, 35), (sx - 12, sy + 2), (sx - 25, sy + 12), 2)
    elif kind == "spark_box":
        box = pygame.Rect(sx - 14, sy - 16, 28, 32)
        for xx in range(box.w):
            t = xx / max(1, box.w - 1)
            c = int(56 - 24 * abs(t - 0.3) * 2.0)
            pygame.draw.line(surface, (c, c + 3, c), (box.x + xx, box.y), (box.x + xx, box.bottom - 1))
        pygame.draw.rect(surface, (22, 24, 22), box, 1, border_radius=3)
        pygame.draw.line(surface, (24, 26, 24), (sx + 2, sy - 14), (sx + 2, sy + 14), 1)
        pygame.draw.rect(surface, (120, 104, 40), (sx - 11, sy + 6, 14, 4))
        pygame.draw.rect(surface, (30, 30, 26), (sx - 11, sy + 6, 14, 4), 1)
        pygame.draw.circle(surface, (180, 60, 40), (sx - 8, sy - 10), 2)
        if age % 45 < 10:
            for i in range(5):
                ang = i / 5.0 * math.tau + age * 0.12
                pygame.draw.line(surface, (255, 210, 90), (sx, sy), (sx + math.cos(ang) * 18, sy + math.sin(ang) * 12), 1)
    elif kind == "glint":
        a = int(110 + 90 * pulse)
        pygame.draw.circle(surface, (255, 255, 210), (sx, sy), 4)
        pygame.draw.circle(surface, (255, 90, 45, a), (sx, sy), 15, 1)
        pygame.draw.line(surface, (255, 235, 190), (sx - 30, sy), (sx + 30, sy), 1)
        pygame.draw.line(surface, (255, 235, 190), (sx, sy - 30), (sx, sy + 30), 1)
    elif kind == "field_radio":
        _draw_prop_icon(surface, "radio", sx, sy, scale=0.62, active=True, color=(245, 190, 65))
    elif kind == "cone":
        if charred:
            # Knocked-over charred cone - lying on its side, blackened.
            # Flattened cone body (ellipse instead of triangle).
            pygame.draw.ellipse(surface, (35, 28, 24), (sx - 16, sy - 4, 32, 12))
            pygame.draw.ellipse(surface, (55, 45, 38), (sx - 16, sy - 4, 32, 12), 2)
            # Charred base still visible.
            pygame.draw.rect(surface, (25, 20, 16), (sx - 15, sy + 6, 30, 5), border_radius=1)
            # Faint glow - still smoldering.
            if age % 40 < 20:
                glow = pygame.Surface((24, 16), pygame.SRCALPHA)
                pygame.draw.ellipse(glow, (255, 90, 30, 80), (0, 0, 24, 16))
                surface.blit(glow, (sx - 12, sy - 2))
        else:
            # two-facet body: lit left face, shaded right face
            pygame.draw.polygon(surface, (228, 100, 32), [(sx, sy - 17), (sx - 12, sy + 12), (sx, sy + 12)])
            pygame.draw.polygon(surface, (168, 66, 22), [(sx, sy - 17), (sx + 12, sy + 12), (sx, sy + 12)])
            pygame.draw.polygon(surface, (60, 32, 16), [(sx, sy - 17), (sx - 12, sy + 12), (sx + 12, sy + 12)], 1)
            # reflective collar with shaded underside
            pygame.draw.line(surface, (248, 216, 140), (sx - 7, sy - 3), (sx + 7, sy - 3), 3)
            pygame.draw.line(surface, (150, 128, 84), (sx - 7, sy), (sx + 7, sy), 1)
            pygame.draw.line(surface, (255, 236, 180), (sx - 5, sy - 14), (sx - 2, sy - 14), 1)
            # square base plate
            pygame.draw.rect(surface, (92, 62, 38), (sx - 15, sy + 10, 30, 6), border_radius=1)
            pygame.draw.rect(surface, (40, 26, 14), (sx - 15, sy + 10, 30, 6), 1, border_radius=1)
            pygame.draw.line(surface, (140, 96, 56), (sx - 13, sy + 11), (sx + 13, sy + 11), 1)
    elif kind == "barrel":
        if charred:
            # Charred, dented barrel - blackened, slightly collapsed.
            pygame.draw.rect(surface, (22, 18, 15), (sx - 13, sy - 15, 26, 30), border_radius=5)
            pygame.draw.rect(surface, (40, 32, 26), (sx - 13, sy - 15, 26, 30), 2, border_radius=5)
            # Dented/buckled band lines.
            pygame.draw.line(surface, (15, 12, 10), (sx - 12, sy - 4), (sx + 12, sy - 2), 2)
            pygame.draw.line(surface, (15, 12, 10), (sx - 12, sy + 6), (sx + 12, sy + 4), 2)
            # Smoldering glow at the top rim.
            if age % 50 < 25:
                glow = pygame.Surface((28, 10), pygame.SRCALPHA)
                pygame.draw.ellipse(glow, (255, 100, 30, 100), (0, 0, 28, 10))
                surface.blit(glow, (sx - 14, sy - 16))
        else:
            for i in range(26):
                t = i / 25.0
                c = int(96 - 52 * abs(t - 0.3) * 2.0)
                pygame.draw.line(surface, (min(255, c + 8), max(0, c - 6), max(0, c - 26)), (sx - 13 + i, sy - 15), (sx - 13 + i, sy + 16))
            pygame.draw.rect(surface, (40, 32, 22), (sx - 13, sy - 17, 26, 34), 2, border_radius=5)
            pygame.draw.ellipse(surface, (122, 100, 62), (sx - 13, sy - 19, 26, 8))
            pygame.draw.ellipse(surface, (40, 32, 22), (sx - 13, sy - 19, 26, 8), 1)
            pygame.draw.ellipse(surface, (86, 70, 42), (sx - 9, sy - 18, 18, 6), 1)
            pygame.draw.circle(surface, (40, 32, 22), (sx + 7, sy - 15), 1)
            for hy in (sy - 5, sy + 7):
                pygame.draw.line(surface, (45, 36, 24), (sx - 12, hy), (sx + 12, hy), 2)
                pygame.draw.line(surface, (126, 104, 64), (sx - 12, hy + 2), (sx + 12, hy + 2), 1)
            pygame.draw.line(surface, (96, 62, 38), (sx - 8, sy - 12), (sx - 8, sy + 14), 1)
    elif kind == "puddle":
        puddle = pygame.Surface((84, 42), pygame.SRCALPHA)
        pts = [(10, 22), (20, 10), (40, 5), (62, 9), (76, 18), (70, 30), (48, 36), (24, 33)]
        pygame.draw.polygon(puddle, (22, 32, 42, 110), pts)
        pygame.draw.polygon(puddle, (60, 76, 92, 60), pts, 1)
        pygame.draw.polygon(puddle, (16, 24, 34, 120),
                            [(20, 22), (28, 14), (44, 10), (60, 14), (66, 20), (56, 28), (38, 30)])
        # sky glint + ripple arcs
        pygame.draw.line(puddle, (150, 172, 190, 90), (26, 16), (44, 13), 1)
        pygame.draw.line(puddle, (150, 172, 190, 60), (50, 20), (62, 18), 1)
        pygame.draw.arc(puddle, (90, 108, 124, 70), (30, 16, 26, 12), 3.4, 6.0, 1)
        surface.blit(puddle, (sx - 42, sy - 21))
        # Scorched puddle - evaporated/charred ring around the edge.
        if prop.get("scorched", False):
            scorch_ring = pygame.Surface((96, 50), pygame.SRCALPHA)
            pygame.draw.ellipse(scorch_ring, (8, 6, 5, 140), (0, 0, 96, 50), 4)
            surface.blit(scorch_ring, (sx - 48, sy - 25))
    elif kind == "sign":
        if charred:
            # Knocked-over charred sign post - broken, lying at an angle.
            render_util.soft_shadow(surface, (sx - 22, sy + 8, 44, 12), 80)
            # Broken post stub.
            pygame.draw.line(surface, (35, 30, 25), (sx - 4, sy + 12), (sx + 6, sy - 6), 3)
            # Fallen sign plate - rotated, blackened.
            pygame.draw.rect(surface, (28, 24, 20), (sx - 18, sy - 4, 38, 16))
            pygame.draw.rect(surface, (45, 38, 32), (sx - 18, sy - 4, 38, 16), 1)
            # Faint soot smudge.
            soot = pygame.Surface((50, 24), pygame.SRCALPHA)
            pygame.draw.ellipse(soot, (8, 6, 5, 100), (0, 0, 50, 24))
            surface.blit(soot, (sx - 22, sy - 8))
        else:
            render_util.soft_shadow(surface, (sx - 20, sy + 12, 40, 10), 55)
            pygame.draw.line(surface, (80, 80, 72), (sx - 10, sy + 14), (sx + 12, sy - 16), 3)
            pygame.draw.line(surface, (120, 120, 110), (sx - 11, sy + 13), (sx + 11, sy - 17), 1)
            plate = pygame.Rect(sx - 26, sy - 25, 42, 18)
            for yy in range(plate.h):
                t = yy / max(1, plate.h - 1)
                c = (int(72 - 24 * t), int(80 - 26 * t), int(84 - 26 * t))
                pygame.draw.line(surface, c, (plate.x, plate.y + yy), (plate.right - 1, plate.y + yy))
            pygame.draw.rect(surface, (24, 26, 28), plate, 1)
            pygame.draw.rect(surface, (150, 150, 125), plate, 2)
            pygame.draw.line(surface, (190, 190, 160), (plate.x + 3, plate.y + 3), (plate.right - 4, plate.y + 3), 1)
            txt = font_terminal_small.render(_T("m2.12"), True, (210, 210, 178))
            surface.blit(txt, (sx - txt.get_width() // 2 - 5, sy - 22))
    else:
        pygame.draw.circle(surface, (90, 80, 65), (sx, sy), 8)


def _draw_story_props(surface, fcx, fcy):
    for prop in getattr(STATE, "mission2_story_props", []):
        _draw_story_prop(surface, prop, fcx, fcy)


def _draw_sniper_lasers_world(surface, fcx, fcy):
    for laser in getattr(STATE, "mission2_sniper_lasers", []):
        sx1, sy1 = _world(laser["from"], fcx, fcy)
        sx2, sy2 = _world(laser["to"], fcx, fcy)
        alpha = max(0, min(190, int(laser.get("life", 0) * 4)))
        beam = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        pygame.draw.line(beam, (255, 35, 22, alpha), (sx1, sy1), (sx2, sy2), 3)
        pygame.draw.line(beam, (255, 175, 110, alpha // 2), (sx1, sy1), (sx2, sy2), 1)
        pygame.draw.circle(beam, (255, 45, 30, alpha), (int(sx2), int(sy2)), 8, 1)
        surface.blit(beam, (0, 0))


def _draw_sniper_muzzle_flashes(surface, fcx, fcy):
    for flash in getattr(STATE, "mission2_sniper_muzzle_flashes", []):
        sx, sy = _world(flash.get("pos", SNIPER_NEST_POS), fcx, fcy)
        life = flash.get("life", 1)
        max_life = max(1, flash.get("max_life", 16))
        t = max(0.0, min(1.0, life / max_life))
        glow = pygame.Surface((150, 120), pygame.SRCALPHA)
        cx, cy = 75, 60
        pygame.draw.circle(glow, (255, 245, 190, int(210 * t)), (cx, cy), int(10 + 20 * t))
        pygame.draw.circle(glow, (255, 110, 35, int(130 * t)), (cx, cy), int(26 + 32 * t), 2)
        pygame.draw.line(glow, (255, 220, 130, int(180 * t)), (cx, cy), (cx - 48, cy + 38), 4)
        surface.blit(glow, (sx - cx, sy - cy))


def _draw_os12_rifle(screen, cx, cy, angle=0.0, scale=1.0, highlight=False):
    """Detailed OS-12 assault rifle silhouette.
    cx, cy is the approximate center of the receiver.
    angle in radians; positive = clockwise tilt.
    scale uniformly resizes all dimensions.
    highlight=True adds a wet sheen for rain-soaked scenes.

    (Docstring previously called this a "combat shotgun" - the OS-12 is a
    full-auto assault rifle firing 5.56x45mm, not a shotgun. Fixed to match
    the stat card shown in the Seby pickup cutscene.)"""
    s = scale
    cos_a = math.cos(angle)
    sin_a = math.sin(angle)

    def pt(dx, dy):
        x = dx * s
        y = dy * s
        return (int(cx + x * cos_a - y * sin_a),
                int(cy + x * sin_a + y * cos_a))

    METAL_DARK = (28, 30, 34)
    METAL_MID  = (52, 56, 62)
    METAL_HI   = (95, 100, 108)
    WOOD_DARK  = (42, 28, 18)
    WOOD_MID   = (68, 46, 28)
    WOOD_HI    = (95, 68, 42)
    ACCENT     = (18, 20, 24)

    stock_pts = [pt(-58, -4), pt(-38, -8), pt(-26, -6), pt(-26, 8), pt(-40, 10), pt(-58, 6)]
    pygame.draw.polygon(screen, WOOD_DARK, stock_pts)
    pygame.draw.polygon(screen, WOOD_MID, [pt(-56, -2), pt(-38, -6), pt(-28, -4), pt(-28, 6), pt(-40, 8), pt(-56, 4)])
    pygame.draw.line(screen, WOOD_HI, pt(-54, -1), pt(-30, -3), 1)

    receiver_pts = [pt(-26, -7), pt(8, -7), pt(8, 9), pt(-26, 9)]
    pygame.draw.polygon(screen, METAL_MID, receiver_pts)
    pygame.draw.polygon(screen, METAL_DARK, receiver_pts, 1)
    pygame.draw.rect(screen, ACCENT, (*pt(-14, -4), max(1, int(12 * s)), max(1, int(5 * s))))
    pygame.draw.circle(screen, METAL_HI, pt(-4, -7), max(1, int(2 * s)))

    grip_pts = [pt(-10, 9), pt(-2, 9), pt(2, 22), pt(-8, 22)]
    pygame.draw.polygon(screen, WOOD_DARK, grip_pts)
    pygame.draw.polygon(screen, WOOD_MID, [pt(-9, 10), pt(-3, 10), pt(1, 20), pt(-7, 20)])

    pygame.draw.arc(screen, METAL_DARK,
                    pygame.Rect(*pt(-6, 8), max(2, int(10 * s)), max(2, int(8 * s))),
                    0, math.pi, max(1, int(2 * s)))

    barrel_pts = [pt(8, -4), pt(48, -4), pt(48, 4), pt(8, 4)]
    pygame.draw.polygon(screen, METAL_DARK, barrel_pts)
    pygame.draw.line(screen, METAL_HI, pt(10, -3), pt(46, -3), 1)

    shield_pts = [pt(10, -6), pt(36, -6), pt(36, 6), pt(10, 6)]
    pygame.draw.polygon(screen, METAL_MID, shield_pts)
    for i in range(4):
        vx = 14 + i * 5
        pygame.draw.line(screen, ACCENT, pt(vx, -5), pt(vx, -2), 1)
        pygame.draw.line(screen, ACCENT, pt(vx, 3), pt(vx, 5), 1)

    pygame.draw.rect(screen, METAL_DARK, (*pt(46, -5), max(2, int(4 * s)), max(2, int(10 * s))))
    pygame.draw.circle(screen, ACCENT, pt(50, 0), max(1, int(2 * s)))

    pygame.draw.line(screen, METAL_HI, pt(42, -4), pt(42, -8), max(1, int(2 * s)))
    pygame.draw.rect(screen, METAL_DARK, (*pt(4, -10), max(1, int(3 * s)), max(1, int(4 * s))))

    pygame.draw.circle(screen, METAL_DARK, pt(-50, 6), max(1, int(2 * s)), 1)
    pygame.draw.circle(screen, METAL_DARK, pt(28, 6), max(1, int(2 * s)), 1)

    if highlight:
        pygame.draw.line(screen, (180, 190, 200), pt(12, -3), pt(44, -3), 1)
        pygame.draw.line(screen, (130, 140, 150), pt(-24, -6), pt(6, -6), 1)
        pygame.draw.line(screen, (110, 80, 55), pt(-50, -2), pt(-32, -5), 1)


# ─────────────────────────────────────────────
# Seby OS-12 pickup cutscene (FPV)
#
# Three first-person beats:
#   1. seby_pickup_body   - looking down at Sebi's body, no hands visible
#   2. seby_pickup_reach  - hands enter frame, right hand grips the OS-12
#   3. seby_pickup_raise  - weapon brought up to a centered inspect pose,
#                           full stat card rendered bottom-right
#
# Backdrop is authored fixed Route 12 (toll plaza + gantry + tanker glow + rain).
# No subtitle bar on any beat - shots set hide_caption=True so the generic
# dialogue box is suppressed by the cutscene loop in acaristan.py.
# ─────────────────────────────────────────────

# Reusable weapon-inspect stat-card colors. Distinct from mission2 intel cards
# so future weapon pickups can share this treatment.
_WEAPON_CARD_BG        = (10, 12, 14, 215)
_WEAPON_CARD_BORDER    = (160, 145, 95)
_WEAPON_CARD_ACCENT    = (220, 195, 110)
_WEAPON_CARD_TITLE_FG  = (235, 220, 175)
_WEAPON_CARD_LABEL_FG  = (150, 145, 130)
_WEAPON_CARD_VALUE_FG  = (220, 220, 210)
_WEAPON_CARD_FLAVOR_FG = (170, 165, 150)
_WEAPON_CARD_STAMP_FG  = (240, 210, 120)


def _draw_route12_pickup_backdrop(surface, t, lighting):
    """Authored Route 12 toll-plaza backdrop for the Seby pickup cutscene.

    Fixed scene (not sampled from live state): storm sky, distant city, gantry
    silhouette, burning tanker glow, wet asphalt with lane markings, fog band,
    rain. Lighting tuple from the shot subtly tints the overall ambience as the
    three beats progress (darker on the body shot, slightly lifted on the rise).
    """
    W, H = WIDTH, HEIGHT
    horizon = int(H * 0.48)

    # Storm sky, tinted by the shot's lighting tuple.
    lr, lg, lb = lighting
    for i in range(horizon):
        f = i / horizon
        r = int(6 + f * 36 + lr * 0.3)
        g = int(8 + f * 20 + lg * 0.3)
        b = int(18 + f * 28 + lb * 0.3)
        pygame.draw.line(surface, (min(255, r), min(255, g), min(255, b)), (0, i), (W, i))

    # Occasional lightning flash. Deterministic per-second seed for stable look.
    flash_seed = int(t * 0.7)
    flash_rng = random.Random(flash_seed)
    if flash_rng.random() < 0.08:
        flash_alpha = int(80 * (1 - (t * 0.7 - flash_seed)))
        if flash_alpha > 0:
            flash = pygame.Surface((W, horizon), pygame.SRCALPHA)
            flash.fill((180, 190, 210, flash_alpha))
            surface.blit(flash, (0, 0))
            bx = flash_rng.randint(W // 4, 3 * W // 4)
            by = 20
            for _ in range(8):
                nx = bx + flash_rng.randint(-12, 12)
                ny = by + flash_rng.randint(10, 25)
                pygame.draw.line(surface, (220, 230, 255), (bx, by), (nx, ny), 2)
                bx, by = nx, ny
                if by > horizon - 40:
                    break

    # Distant city skyline.
    skyline_y = horizon - 6
    skyline_rng = random.Random(42)
    sx = 0
    while sx < W:
        bw = skyline_rng.randint(20, 55)
        bh = skyline_rng.randint(14, 42)
        pygame.draw.rect(surface, (6, 8, 14), (sx, skyline_y - bh, bw, bh))
        for _ in range(skyline_rng.randint(1, 4)):
            wx = sx + skyline_rng.randint(3, bw - 4)
            wy = skyline_y - skyline_rng.randint(4, bh - 2)
            if skyline_rng.random() < 0.7:
                pygame.draw.rect(surface, (180, 140, 60), (wx, wy, 2, 2))
        sx += bw + skyline_rng.randint(0, 4)

    # Toll booths flanking the lane.
    booth_y = horizon - 36
    for bx in (int(W * 0.08), int(W * 0.88)):
        pygame.draw.rect(surface, (8, 10, 14), (bx - 14, booth_y, 28, 36))
        pygame.draw.rect(surface, (18, 22, 28), (bx - 14, booth_y, 28, 36), 1)
        if int(t * 1.5) % 3 != 0:
            pygame.draw.rect(surface, (210, 180, 90), (bx - 6, booth_y + 8, 12, 8))

    # Checkpoint gantry overhead, upper-right area so it doesn't crowd the body.
    gantry_x = int(W * 0.62)
    gantry_y = horizon - 96
    pygame.draw.rect(surface, (4, 6, 10), (gantry_x, gantry_y, 6, 96))
    pygame.draw.rect(surface, (4, 6, 10), (gantry_x - 120, gantry_y, 130, 6))
    pygame.draw.rect(surface, (4, 6, 10), (gantry_x - 124, gantry_y - 6, 6, 12))
    if int(t * 2) % 2 == 0:
        pygame.draw.circle(surface, (220, 80, 60), (gantry_x - 116, gantry_y + 3), 3)
        pygame.draw.circle(surface, (255, 140, 100), (gantry_x - 116, gantry_y + 3), 5, 1)

    # Distant tanker fire (baked in as "on" - by this point in the mission the
    # tanker has exploded narratively).
    fire_x = int(W * 0.78)
    fire_y = horizon - 8
    glow_pulse = 0.85 + 0.15 * math.sin(t * 4)
    halo = pygame.Surface((300, 200), pygame.SRCALPHA)
    for i in range(80):
        a = int(40 * glow_pulse * (1 - i / 80))
        pygame.draw.circle(halo, (220, 100, 40, a), (150, 100), 80 - i)
    surface.blit(halo, (fire_x - 150, fire_y - 100))
    flame_rng = random.Random(int(t * 12))
    for _ in range(8):
        fx = fire_x + flame_rng.randint(-12, 12)
        fy = fire_y + flame_rng.randint(-4, 8)
        fr = flame_rng.randint(4, 10)
        col = flame_rng.choice([(240, 160, 60), (220, 100, 30), (255, 200, 90)])
        pygame.draw.circle(surface, col, (fx, fy), fr)
    for i in range(12):
        sy = fire_y - 20 - i * 14
        sx = fire_x + int(math.sin(t * 0.5 + i * 0.4) * (4 + i * 2))
        sw = 18 + i * 4
        sa = max(0, 90 - i * 7)
        smoke = pygame.Surface((sw * 2, 24), pygame.SRCALPHA)
        pygame.draw.ellipse(smoke, (30, 28, 32, sa), smoke.get_rect())
        surface.blit(smoke, (sx - sw, sy))

    # Wet asphalt foreground.
    for i in range(horizon, H):
        f = (i - horizon) / (H - horizon)
        r = int(10 + f * 14)
        g = int(12 + f * 14)
        b = int(16 + f * 18)
        pygame.draw.line(surface, (r, g, b), (0, i), (W, i))
    refl = pygame.Surface((W, H - horizon), pygame.SRCALPHA)
    for i in range(H - horizon):
        f = 1 - i / (H - horizon)
        a = int(40 * f * glow_pulse)
        pygame.draw.line(refl, (200, 90, 30, a), (fire_x - 80, i), (fire_x + 80, i))
    surface.blit(refl, (0, horizon))

    # Lane markings receding into perspective.
    for i in range(8):
        stripe_y = horizon + 10 + i * (H - horizon) // 10
        stripe_w = 4 + i * 3
        stripe_h = 2 + i
        sx = W // 2 - stripe_w // 2
        pygame.draw.rect(surface, (110, 95, 50), (sx, stripe_y, stripe_w, stripe_h))

    # Scattered puddles.
    puddle_rng = random.Random(0)
    for _ in range(6):
        px = puddle_rng.randint(0, W)
        py = puddle_rng.randint(horizon + 20, H - 20)
        pw = puddle_rng.randint(30, 80)
        ph = puddle_rng.randint(6, 12)
        puddle = pygame.Surface((pw, ph), pygame.SRCALPHA)
        pygame.draw.ellipse(puddle, (60, 70, 90, 90), puddle.get_rect())
        if int(t * 3) % 2 == 0:
            pygame.draw.ellipse(puddle, (120, 140, 170, 50), (pw // 4, ph // 4, pw // 2, ph // 2), 1)
        surface.blit(puddle, (px - pw // 2, py - ph // 2))

    # Small ground clutter.
    pygame.draw.rect(surface, (28, 24, 20), (int(W * 0.2), horizon + 80, 14, 4))
    pygame.draw.rect(surface, (28, 24, 20), (int(W * 0.82), horizon + 60, 10, 3))

    # Fog band along the horizon.
    fog = pygame.Surface((W, 100), pygame.SRCALPHA)
    for i in range(100):
        a = int(50 * (1 - abs(i - 50) / 50))
        pygame.draw.line(fog, (50, 55, 65, a), (0, i), (W, i))
    surface.blit(fog, (0, horizon - 30))


def _draw_sebi_body_fpv(surface, t, pitch_offset=40, intensity=1.0):
    """Sebi's body seen from Biribel's POV, face-down on the asphalt.

    pitch_offset:
        vertical offset of the whole composition. Higher = camera angled
        further down. Used by the pickup beats to ease the camera pitch.
    intensity:
        0.0 .. 1.0 multiplier on the cinematic flourishes (firelight rim,
        rain ripples, blood pool spread). Stage 1 uses 1.0; the reach and
        raise beats dial it down as the body leaves the frame.
    """
    W, H = WIDTH, HEIGHT
    cx = W // 2
    # Breath bob: ±2px vertical sway across the whole composition.
    breath = int(math.sin(t * 1.8) * 2 * intensity)
    ground_y = int(H * 0.66) + pitch_offset + breath

    # ---- Asphalt halo under the body --------------------------------------
    halo = pygame.Surface((360, 120), pygame.SRCALPHA)
    render_util.soft_shadow(halo, (0, 0, 360, 120), 90)
    surface.blit(halo, (cx - 180, ground_y + 4))

    # ---- Blood pool: eases out over the first ~1.2s, then creeps ---------
    pool_t = min(1.0, t / 1.2)
    pool_eased = 1 - (1 - pool_t) ** 2
    pool_w = int(180 + pool_eased * 60)
    pool_h = int(54 + pool_eased * 18)
    pool = pygame.Surface((pool_w + 20, pool_h + 20), pygame.SRCALPHA)
    pygame.draw.ellipse(pool, (70, 8, 8, 220),
                        (10, 10, pool_w, pool_h))
    pygame.draw.ellipse(pool, (110, 14, 14, 180),
                        (16, 14, pool_w - 12, pool_h - 8))
    surface.blit(pool, (cx - pool_w // 2 - 30, ground_y + 28))

    # Two rain ripples at staggered phases keep the pool surface alive.
    if intensity > 0.2:
        for i, phase in enumerate((0.0, 0.55)):
            rt = ((t + phase) % 1.3) / 1.3
            if rt < 0.9:
                rr = int(4 + rt * 28)
                ra = int(140 * (1 - rt) * intensity)
                ripple = pygame.Surface((rr * 2 + 4, rr + 4), pygame.SRCALPHA)
                pygame.draw.ellipse(ripple, (180, 40, 40, ra),
                                    (2, 2, rr * 2, rr), 1)
                rx = cx - 40 + i * 50
                surface.blit(ripple, (rx - rr, ground_y + 44))

    # ---- Firelight pulse from the distant tanker (4 Hz flicker) -----------
    fire_pulse = 0.6 + 0.4 * math.sin(t * 4.0 + 0.3)

    # ---- Torso: KRAP plate carrier, face-down ----------------------------------
    # Colors match _draw_actor's in-game squadmate rendering:
    #   torso fill  = (44, 54, 60)  - dark blue-grey KRAP uniform
    #   torso outline = (22, 28, 32)
    #   accent stripe = C_KRAP_BLUE (35, 65, 110) - blue shoulder stripe
    #   SEBY accent dot = (85, 170, 225) - light blue, Seby's squad color
    # Previously the corpse was drawn in olive green (38,42,32) with a tan
    # helmet - completely different from the in-game Seby who wears a
    # blue-grey KRAP uniform with no helmet (just a skin-colored head).
    pygame.draw.polygon(surface, (44, 54, 60), [
        (cx - 110, ground_y + 6),
        (cx + 60, ground_y + 12),
        (cx + 50, ground_y + 56),
        (cx - 120, ground_y + 50),
    ])
    pygame.draw.polygon(surface, (22, 28, 32), [
        (cx - 110, ground_y + 6),
        (cx + 60, ground_y + 12),
        (cx + 50, ground_y + 56),
        (cx - 120, ground_y + 50),
    ], 2)
    # Firelight rim on torso's right edge.
    if intensity > 0.2:
        rim_a = int(120 * fire_pulse * intensity)
        rim = pygame.Surface((10, 50), pygame.SRCALPHA)
        pygame.draw.polygon(rim, (220, 130, 60, rim_a),
                            [(0, 4), (10, 6), (8, 48), (0, 46)])
        surface.blit(rim, (cx + 52, ground_y + 10))

    # KRAP blue accent stripe across the shoulders (matches _draw_actor line 6508).
    pygame.draw.rect(surface, C_KRAP_BLUE,
                     (cx - 100, ground_y + 8, 150, 5), border_radius=2)
    # SEBY accent dot - light blue, his squad identifier (matches _draw_actor
    # line 6510 where accent is drawn as a small circle on the torso).
    pygame.draw.circle(surface, (85, 170, 225),
                       (cx + 40, ground_y + 24), 4)

    # Plate carrier pouches - dark blue-grey to match the uniform, not brown.
    pygame.draw.rect(surface, (34, 42, 48),
                     (cx - 60, ground_y + 14, 24, 18), 1)
    pygame.draw.rect(surface, (34, 42, 48),
                     (cx - 32, ground_y + 14, 24, 18), 1)
    pygame.draw.rect(surface, (34, 42, 48),
                     (cx - 20, ground_y + 14, 22, 16), 1)

    # ---- Head: skin-colored, NO helmet on head (knocked off to the side) -----
    # The in-game squadmates wear no helmet - but in this cutscene the sniper
    # round knocked Seby's helmet off. The helmet lies beside his head on the
    # asphalt, and there's an exit wound + blood pool around his skull.
    # Head position: centered on the torso's left edge so the head overlaps
    # the shoulders (no gap). Torso left edge is at cx-110; head radius is 12,
    # so head center at cx-98 puts the head's right edge at cx-86 (well inside
    # the torso) and the left edge at cx-110 (flush with the torso edge).
    head_x = cx - 98
    head_y = ground_y + 2

    # Blood pool around the head - spreads from the entry wound, darker and
    # thicker than the body blood pool. Eases in with the same timing as the
    # main pool so it reads as one continuous bleed.
    head_pool_t = min(1.0, t / 1.0)
    head_pool_eased = 1 - (1 - head_pool_t) ** 2
    head_pool_w = int(50 + head_pool_eased * 30)
    head_pool_h = int(28 + head_pool_eased * 14)
    head_pool = pygame.Surface((head_pool_w + 16, head_pool_h + 16), pygame.SRCALPHA)
    pygame.draw.ellipse(head_pool, (60, 6, 6, 210),
                        (8, 8, head_pool_w, head_pool_h))
    pygame.draw.ellipse(head_pool, (100, 10, 10, 170),
                        (12, 12, head_pool_w - 8, head_pool_h - 6))
    surface.blit(head_pool, (head_x - head_pool_w // 2 - 8, head_y - head_pool_h // 2 + 2))

    # Back of head - slightly darker skin (shadowed), with a dark exit wound
    # on the back-right where the round exited.
    pygame.draw.circle(surface, (180, 150, 115),
                       (head_x, head_y), 12)
    # Skin highlight on the crown.
    pygame.draw.circle(surface, C_PLAYER_SKIN,
                       (head_x - 2, head_y - 2), 10)
    # Outline.
    pygame.draw.circle(surface, (120, 95, 70),
                       (head_x, head_y), 12, 2)
    # Exit wound - dark red/black hole on the back of the skull.
    pygame.draw.circle(surface, (40, 5, 5),
                       (head_x + 5, head_y + 2), 4)
    pygame.draw.circle(surface, (15, 2, 2),
                       (head_x + 5, head_y + 2), 2)
    # Blood trickle running from the wound down toward the asphalt.
    pygame.draw.line(surface, (90, 10, 10),
                     (head_x + 7, head_y + 4), (head_x + 14, head_y + 16), 2)
    pygame.draw.line(surface, (70, 8, 8),
                     (head_x + 9, head_y + 8), (head_x + 18, head_y + 20), 1)

    if intensity > 0.2:
        hl_a = int(90 * fire_pulse * intensity)
        helmet_hl = pygame.Surface((20, 6), pygame.SRCALPHA)
        pygame.draw.ellipse(helmet_hl, (220, 130, 70, hl_a),
                            (0, 0, 20, 6))
        surface.blit(helmet_hl, (head_x - 10, head_y - 6))
    # Neck connecting head to torso - a short thick line from the head's
    # right side into the torso. With head at cx-98 (radius 12, right edge
    # at cx-86) and torso top at ground_y+6, the neck bridges the overlap.
    pygame.draw.line(surface, (160, 135, 100),
                     (head_x + 6, head_y + 8), (cx - 90, ground_y + 10), 4)
    # Neck shadow on the torso side for depth.
    pygame.draw.line(surface, (120, 95, 70),
                     (head_x + 8, head_y + 6), (cx - 88, ground_y + 8), 2)

    # ---- Knocked-off helmet, lying beside the head on the asphalt -----------
    # The sniper round knocked it off - it rests a few inches to the left of
    # Seby's head, tipped on its side. Drawn as a KRAP-blue-grey helmet shell
    # (matching the uniform palette) with a chin strap dangling.
    helmet_x = head_x - 34
    helmet_y = head_y + 6
    # Helmet shell - rounded dome, tipped slightly. Dark blue-grey to match
    # the KRAP uniform (not the olive/tan from before).
    helmet_shell = [
        (helmet_x - 16, helmet_y + 6),
        (helmet_x - 14, helmet_y - 8),
        (helmet_x - 4,  helmet_y - 12),
        (helmet_x + 8,  helmet_y - 10),
        (helmet_x + 14, helmet_y - 2),
        (helmet_x + 12, helmet_y + 8),
        (helmet_x - 10, helmet_y + 10),
    ]
    pygame.draw.polygon(surface, (40, 50, 58), helmet_shell)
    pygame.draw.polygon(surface, (20, 26, 32), helmet_shell, 2)
    # Helmet rim highlight (firelight catch on the upper edge).
    if intensity > 0.2:
        rim_a = int(80 * fire_pulse * intensity)
        rim_surf = pygame.Surface((24, 4), pygame.SRCALPHA)
        pygame.draw.ellipse(rim_surf, (220, 130, 70, rim_a), (0, 0, 24, 4))
        surface.blit(rim_surf, (helmet_x - 12, helmet_y - 10))
    # Chin strap dangling from the helmet.
    pygame.draw.line(surface, (20, 24, 28),
                     (helmet_x + 10, helmet_y + 4), (helmet_x + 16, helmet_y + 16), 2)
    pygame.draw.line(surface, (20, 24, 28),
                     (helmet_x - 8, helmet_y + 8), (helmet_x - 12, helmet_y + 18), 2)
    # Small blood smear on the helmet interior (where it was against the wound).
    pygame.draw.ellipse(surface, (70, 8, 8, 180),
                        (helmet_x - 6, helmet_y - 4, 12, 6))

    # ---- Right arm outstretched toward the rifle --------------------------
    # Arm color matches KRAP uniform sleeve (44, 54, 60) - was olive (38,42,32).
    pygame.draw.polygon(surface, (44, 54, 60), [
        (cx + 60, ground_y + 12),
        (cx + 140, ground_y + 18),
        (cx + 140, ground_y + 28),
        (cx + 60, ground_y + 26),
    ])
    # Hand - skin colored (was brown glove).
    pygame.draw.circle(surface, C_PLAYER_SKIN,
                       (cx + 144, ground_y + 24), 7)

    # Left arm tucked under body.
    pygame.draw.polygon(surface, (34, 42, 48), [
        (cx - 90, ground_y + 22),
        (cx - 40, ground_y + 30),
        (cx - 50, ground_y + 40),
        (cx - 100, ground_y + 34),
    ])

    # Legs extending forward (away from camera).
    # Trouser color matches _draw_actor (24, 28, 34) - was olive (34,38,30).
    pygame.draw.polygon(surface, (24, 28, 34), [
        (cx - 30, ground_y + 32),
        (cx + 80, ground_y + 36),
        (cx + 60, ground_y + 64),
        (cx - 40, ground_y + 60),
    ])
    pygame.draw.line(surface, (18, 22, 28),
                     (cx + 20, ground_y + 36), (cx + 12, ground_y + 62), 2)

    # Combat boots - matches _draw_actor boot color (10, 10, 12).
    pygame.draw.rect(surface, (10, 10, 12),
                     (cx + 56, ground_y + 56, 22, 12))
    pygame.draw.rect(surface, (10, 10, 12),
                     (cx + 30, ground_y + 58, 22, 12))

    return ground_y


def _draw_fpv_hands_reach(surface, t, ground_y):
    """Beat 2: hands enter from below, the right hand finds Sebi's OS-12 grip,
    and the rifle lifts off the asphalt locked to that hand.

    The reach is split into two sub-beats:
        approach (t = 0 .. ~0.55s):
            both hands rise into frame; rifle stays flat on the ground beside
            Sebi's outstretched right hand.
        lift (t > ~0.55s):
            the right hand snaps to the rifle's grip anchor and the rifle
            follows that hand upward, rotating slightly toward the inspect pose.
    """
    W, H = WIDTH, HEIGHT
    cx = W // 2

    # ---- 1. Authored anchors -----------------------------------------------
    # Sebi's right hand anchor matches the circle drawn in _draw_sebi_body_fpv:
    #   pygame.draw.circle(surface, ..., (cx + 144, ground_y + 24), 7)
    sebi_hand = (cx + 144, ground_y + 24)

    # Biribel's grip is a rifle-local point (matches the receiver/grip math in
    # _draw_os12_rifle: grip centroid sits at local (-4, +15)).
    grip_local = (-4, 15)

    # Rifle starts lying on the asphalt IN Sebi's outstretched hand - the
    # rifle's grip anchor (grip_local rotated/scaled by the rest pose) sits
    # exactly on Seby's hand. Previously the receiver center was placed at
    # sebi_hand - (10, +2), which left the grip ~16px below the hand and
    # made the rifle read as lying at Seby's feet instead of in his grip.
    rifle_rest_angle = -0.05  # almost horizontal, slight tilt off Sebi's wrist
    _rest_scale = 0.95
    _gdx = grip_local[0] * _rest_scale
    _gdy = grip_local[1] * _rest_scale
    _gwx = _gdx * math.cos(rifle_rest_angle) - _gdy * math.sin(rifle_rest_angle)
    _gwy = _gdx * math.sin(rifle_rest_angle) + _gdy * math.cos(rifle_rest_angle)
    rifle_rest_pos = (sebi_hand[0] - _gwx, sebi_hand[1] - _gwy)

    # ---- 2. Sub-beat blending ----------------------------------------------
    progress       = min(1.0, t / 1.6)
    approach_t     = min(1.0, progress / 0.55)          # 0..1 over the reach
    lift_t         = max(0.0, min(1.0, (progress - 0.55) / 0.45))  # 0..1 over the lift
    lift_eased     = 1 - (1 - lift_t) ** 2

    # Tremor on the right hand, only once the lift actually starts.
    tremor_x = math.sin(t * 14) * 1.4 * lift_t
    tremor_y = math.cos(t * 11) * 1.0 * lift_t

    # ---- 3. Left hand: bracing on asphalt near Sebi's shoulder -------------
    left_progress = min(1.0, progress * 1.3)
    lhx = cx - 220
    lhy = H - 40 - int(left_progress * 140)
    _draw_fpv_hand(surface, lhx, lhy, side="left",
                   splay=0.7 * left_progress, anchor="palm")

    # ---- 4. Right hand path -----------------------------------------------
    # During approach: ease up from below frame toward Sebi's hand.
    # During lift:     snap to the rifle's grip anchor exactly.
    right_progress = max(0.0, min(1.0, (progress - 0.10) * 1.3))
    enter_x = cx + 110
    enter_y = H - 30 - int(right_progress * 175)
    approach_target = sebi_hand

    # Approach lerp: from off-frame entry point to Sebi's hand.
    ax = enter_x + (approach_target[0] - enter_x) * approach_t
    ay = enter_y + (approach_target[1] - enter_y) * approach_t

    # During lift we need to know where the rifle's grip will be in screen
    # space, so we can place the hand exactly on it. Compute that next.

    # ---- 5. Rifle position / angle ----------------------------------------
    # Target lift position: a bit above and toward the camera as Biribel
    # picks the rifle up off the asphalt. Tuned to read as "raising it" without
    # crowding the next beat. Lifts from the hand position (where the rifle
    # was resting), not from past the hand.
    rifle_lift_pos   = (sebi_hand[0] - 6,
                        sebi_hand[1] - 36 + int(tremor_y))
    rifle_lift_angle = -0.32  # tilts toward the inspect angle (-0.18) gradually

    rifle_cx = rifle_rest_pos[0] + (rifle_lift_pos[0] - rifle_rest_pos[0]) * lift_eased + int(tremor_x)
    rifle_cy = rifle_rest_pos[1] + (rifle_lift_pos[1] - rifle_rest_pos[1]) * lift_eased
    rifle_angle = rifle_rest_angle + (rifle_lift_angle - rifle_rest_angle) * lift_eased
    rifle_scale = 0.95

    _draw_os12_rifle(surface, rifle_cx, rifle_cy,
                     angle=rifle_angle, scale=rifle_scale, highlight=True)

    # ---- 6. Grip-anchor math (matches _draw_fpv_hands_inspect) ------------
    cos_a = math.cos(rifle_angle)
    sin_a = math.sin(rifle_angle)
    s = rifle_scale

    def rifle_local_to_world(dx, dy):
        x = dx * s
        y = dy * s
        return (int(rifle_cx + x * cos_a - y * sin_a),
                int(rifle_cy + x * sin_a + y * cos_a))

    grip_world = rifle_local_to_world(*grip_local)

    # ---- 7. Final right-hand position -------------------------------------
    # Approach: follow the easing toward Sebi's hand.
    # Lift:     blend from the approach endpoint onto the grip anchor.
    rhx = ax + (grip_world[0] - ax) * lift_eased
    rhy = ay + (grip_world[1] - ay) * lift_eased

    # Splay tightens as the hand commits to the grip.
    splay = 0.45 - 0.30 * lift_eased

    _draw_fpv_hand(surface, int(rhx), int(rhy), side="right",
                   splay=splay, anchor="palm",
                   draw_sleeve=True,
                   rotation=rifle_angle if lift_t > 0.2 else 0.0)


def _draw_fpv_hand(surface, x, y, side="right", splay=0.5, scale=1.0,
                   anchor="palm", draw_sleeve=True, rotation=0.0):
    """Single FPV hand and forearm sprite, drawn with anatomy that reads
    correctly when wrapped around a rifle.

    The hand is built in a local coordinate system, then rotated by `rotation`
    (radians) so it can align with the forearm direction. `anchor` controls
    what (x, y) refers to:
        'palm'  - palm centre (default; matches grip-anchor math)
        'wrist' - wrist joint, sleeve trails away from there

    Layout in local space (before rotation), with +y pointing AWAY from the
    camera (i.e. "into" the screen toward the rifle):
        wrist at  (0, +28)
        palm at   (0,  0)
        fingers fan out across the top edge (y = -8 .. -22)
        thumb sits on the inside (thumb sits on the inside of the grip (x = -10 .. -4, y = -2 .. +10)

    `side` ('left' or 'right') mirrors the thumb and finger curl so the two
    hands cup the weapon symmetrically. `splay` (0..1) opens the fingers for
    a relaxed support-hand pose; low values keep them tight on a pistol grip.
    """
    skin_base   = (196, 158, 128)
    skin_shade  = (148, 112,  88)
    skin_hi     = (224, 190, 160)
    nail        = (170, 132, 104)
    sleeve_base = ( 58,  60,  54)
    sleeve_dark = ( 38,  40,  36)
    sleeve_hi   = ( 82,  84,  76)
    outline     = ( 22,  20,  18)

    mirror = -1 if side == "left" else 1
    cos_r, sin_r = math.cos(rotation), math.sin(rotation)

    def L(lx, ly):
        """Local -> screen, applying scale, mirror, rotation and anchor."""
        lx *= scale * mirror
        ly *= scale
        rx = lx * cos_r - ly * sin_r
        ry = lx * sin_r + ly * cos_r
        if anchor == "wrist":
            wx = 0 * cos_r - (28 * scale) * sin_r
            wy = 0 * sin_r + (28 * scale) * cos_r
            return (int(x + rx - wx), int(y + ry - wy))
        return (int(x + rx), int(y + ry))

    if draw_sleeve:
        sleeve_pts = [L(-9, 6), L(9, 6), L(11, 30), L(-11, 30)]
        pygame.draw.polygon(surface, sleeve_base, sleeve_pts)
        shade_pts = [L(2, 6), L(9, 6), L(11, 30), L(4, 30)]
        pygame.draw.polygon(surface, sleeve_dark, shade_pts)
        pygame.draw.line(surface, sleeve_hi, L(-6, 8), L(-8, 28), 1)
        pygame.draw.polygon(surface, outline, sleeve_pts, 1)
        pygame.draw.line(surface, outline, L(-9, 8), L(9, 8), 1)

    palm_pts = [L(-8, -6), L(8, -6), L(9, 7), L(-9, 7)]
    pygame.draw.polygon(surface, skin_base, palm_pts)
    pygame.draw.polygon(surface, skin_shade,
                        [L(-9, 2), L(9, 2), L(9, 7), L(-9, 7)])
    pygame.draw.line(surface, skin_hi, L(-6, -4), L(6, -4), 1)
    pygame.draw.polygon(surface, outline, palm_pts, 1)

    spread = 2 + splay * 3
    base_xs = [-6, -2, 2, 6]
    tip_dy  = -16 - splay * 4
    for i, bx in enumerate(base_xs):
        curl = abs(i - 1.5) * splay * 1.5
        tx = bx + (bx * 0.15) * spread
        ty = tip_dy + curl * 2
        finger = [L(bx - 1.4, -6),
                  L(bx + 1.4, -6),
                  L(tx + 1.2, ty + 2),
                  L(tx - 1.2, ty + 2)]
        pygame.draw.polygon(surface, skin_base, finger)
        pygame.draw.line(surface, skin_shade,
                         L(bx + 0.6, -5), L(tx + 0.6, ty + 1), 1)
        # knuckle bump at the root + crease at the joint (reference model)
        pygame.draw.circle(surface, skin_hi, L(bx, -7), 1)
        pygame.draw.line(surface, skin_shade, L((bx + tx) / 2 - 1, (-6 + ty) / 2),
                         L((bx + tx) / 2 + 1, (-6 + ty) / 2), 1)
        # dorsal nail bed + pale free edge
        pygame.draw.line(surface, nail, L(tx - 1.0, ty + 1), L(tx + 1.0, ty + 1), 2)
        pygame.draw.line(surface, (236, 208, 178), L(tx - 1.0, ty), L(tx + 1.0, ty), 1)
        pygame.draw.polygon(surface, outline, finger, 1)

    # long spread thumb with its own knuckle + nail (reference model)
    t0, t1, t2 = L(-8, -2), L(-14, -7), L(-18, -13)
    pygame.draw.line(surface, outline, t0, t1, 6)
    pygame.draw.line(surface, skin_base, t0, t1, 4)
    pygame.draw.line(surface, outline, t1, t2, 5)
    pygame.draw.line(surface, skin_base, t1, t2, 3)
    pygame.draw.circle(surface, skin_hi, t1, 1)
    pygame.draw.line(surface, nail, (t2[0] - 1, t2[1] - 1), (t2[0] + 1, t2[1] - 1), 2)
    pygame.draw.line(surface, skin_shade, L(-12, 1), L(-10, 7), 1)


def _draw_fpv_hands_inspect(surface, t):
    """Beat 3: rifle held up, both hands locked on. Eases in from the lift
    pose so stage 2 -> stage 3 reads as one continuous motion, then settles
    into a slow breathing bob with a traveling glint on the receiver."""
    W, H = WIDTH, HEIGHT
    cx = W // 2

    # ---- 1. Settle: rifle eases from lift angle to inspect angle ----------
    settle_t = min(1.0, t / 0.8)
    settle_eased = 1 - (1 - settle_t) ** 2

    lift_angle    = -0.32
    inspect_angle = -0.18
    rifle_angle = lift_angle + (inspect_angle - lift_angle) * settle_eased

    # ---- 2. Breathing bob: ~0.4 Hz, +/-3px vertical, +/-0.015 rad rotation -
    breath_gain = settle_eased
    breath_y = math.sin(t * 2.5) * 3.0 * breath_gain
    breath_a = math.sin(t * 2.5 + 0.4) * 0.015 * breath_gain
    rifle_angle += breath_a

    # ---- 3. Rifle position & scale -----------------------------------------
    # Scale eases from 0.95 (stage 2, on the ground) to 2.6 (inspect close-up).
    lift_scale    = 0.95
    inspect_scale = 2.6
    rifle_scale = lift_scale + (inspect_scale - lift_scale) * settle_eased

    # Position eases from stage 2's end point (at Sebi's hand) to the centered
    # inspect rest. Matches the updated rifle_lift_pos in _draw_fpv_hands_reach
    # so the rifle doesn't jump between beats.
    lift_end_x = cx + 138
    lift_end_y = int(H * 0.66) + 70 - 40
    rest_x     = cx
    rest_y     = int(H * 0.62)

    rifle_cx = lift_end_x + (rest_x - lift_end_x) * settle_eased
    rifle_cy = lift_end_y + (rest_y - lift_end_y) * settle_eased + breath_y

    _draw_os12_rifle(surface, int(rifle_cx), int(rifle_cy),
                     angle=rifle_angle, scale=rifle_scale, highlight=True)

    # ---- 4. Traveling glint on the receiver --------------------------------
    if settle_eased > 0.5:
        glint_cycle = (t % 1.4) / 1.4
        glint_local_x = -40 + glint_cycle * 80
        cos_a = math.cos(rifle_angle)
        sin_a = math.sin(rifle_angle)
        gx = rifle_cx + (glint_local_x * rifle_scale) * cos_a
        gy = rifle_cy + (glint_local_x * rifle_scale) * sin_a - 4
        glint_a = int(180 * math.sin(glint_cycle * math.pi)
                          * (settle_eased - 0.5) * 2)
        if glint_a > 0:
            glint = pygame.Surface((18, 6), pygame.SRCALPHA)
            pygame.draw.ellipse(glint, (255, 240, 200, glint_a),
                                (0, 0, 18, 6))
            glint = pygame.transform.rotate(glint, -math.degrees(rifle_angle))
            grect = glint.get_rect(center=(int(gx), int(gy)))
            surface.blit(glint, grect)

    # ---- 5. Grip anchors --------------------------------------------------
    cos_a = math.cos(rifle_angle)
    sin_a = math.sin(rifle_angle)
    s = rifle_scale

    def rifle_local_to_world(dx, dy):
        x = dx * s
        y = dy * s
        return (int(rifle_cx + x * cos_a - y * sin_a),
                int(rifle_cy + x * sin_a + y * cos_a))

    grip_world     = rifle_local_to_world(-4, 15)    # rear grip
    foregrip_world = rifle_local_to_world(22, 12)    # forward grip

    # ---- 6. Hands ----------------------------------------------------------
    # Hand scale matches the rifle scale so proportions feel right.
    hand_scale = 1.6

    tremor = max(0.0, 1.0 - settle_eased) * 1.2
    tx = math.sin(t * 14) * tremor
    ty = math.cos(t * 11) * tremor

    _draw_fpv_hand(surface, grip_world[0] + int(tx),
                            grip_world[1] + int(ty),
                   side="right", splay=0.15, scale=hand_scale,
                   anchor="palm", draw_sleeve=False, rotation=rifle_angle)

    _draw_fpv_hand(surface, foregrip_world[0] - int(tx * 0.6),
                            foregrip_world[1] - int(ty * 0.6),
                   side="left", splay=0.20, scale=hand_scale,
                   anchor="palm", draw_sleeve=True, rotation=rifle_angle)


def _draw_weapon_stat_card(surface, t, weapon_name, weapon_class, caliber,
                           magazine, role, flavor, stamp_text):
    """Reusable weapon-inspect stat card. Anchored bottom-right.

    Layout: stamp at top, weapon name as the hero, one condensed stat row
    (caliber / magazine / class), flavor line at the bottom. The card now
    auto-sizes its width to fit the longest line, with a hard cap so it
    cannot exceed the available screen real estate. The flavor line wraps
    onto a second row when needed instead of being truncated mid-word.
    The `role` parameter is kept in the signature for backward compatibility.
    """
    fade = max(0.0, min(1.0, (t - 0.6) / 0.45))
    if fade <= 0:
        return

    margin_r = 36
    margin_b = 64
    pad_x = 14

    # Pre-render text surfaces so we can measure them.
    stamp_surf = font_terminal_small.render(stamp_text, True, _WEAPON_CARD_STAMP_FG)
    name_surf = font_terminal.render(weapon_name, True, _WEAPON_CARD_TITLE_FG)
    stat_text = f"{caliber}  \u00b7  {magazine}  \u00b7  {weapon_class}"
    stat_surf = font_terminal_small.render(stat_text, True, _WEAPON_CARD_VALUE_FG)
    flavor_text = f'"{flavor}"'

    # Auto-size the card width to the widest line, clamped to fit the screen.
    max_card_w = max(280, WIDTH - margin_r * 2)
    min_card_w = 360
    content_w = max(
        stamp_surf.get_width(),
        name_surf.get_width(),
        stat_surf.get_width(),
        font_terminal_small.size(flavor_text)[0],
    )
    card_w = min(max_card_w, max(min_card_w, content_w + pad_x * 2))
    max_text_w = card_w - pad_x * 2

    # Wrap the flavor line onto up to two rows. If it still overflows the
    # second row, truncate that row with an ellipsis rather than the whole
    # quote.
    flavor_lines = _wrap_text(flavor_text, font_terminal_small, max_text_w)
    if len(flavor_lines) > 2:
        head = flavor_lines[0]
        tail = " ".join(flavor_lines[1:])
        while tail and font_terminal_small.size(tail + "\u2026")[0] > max_text_w:
            tail = tail[:-1]
        flavor_lines = [head, tail.rstrip() + "\u2026"]
    flavor_surfs = [
        font_terminal_small.render(line, True, _WEAPON_CARD_FLAVOR_FG)
        for line in flavor_lines
    ]

    line_gap = 2
    flavor_block_h = sum(s.get_height() for s in flavor_surfs) + line_gap * (len(flavor_surfs) - 1)

    # Card height grows if the flavor wrapped onto a second line.
    card_h = 150 + max(0, flavor_block_h - font_terminal_small.get_height())
    card_x = WIDTH - card_w - margin_r
    card_y = HEIGHT - card_h - margin_b

    card = pygame.Surface((card_w, card_h), pygame.SRCALPHA)
    bg = list(_WEAPON_CARD_BG)
    bg[3] = int(bg[3] * fade)
    pygame.draw.rect(card, tuple(bg), card.get_rect(), border_radius=4)

    border = (*_WEAPON_CARD_BORDER, int(220 * fade))
    pygame.draw.rect(card, border, card.get_rect(), 1, border_radius=4)
    accent = (*_WEAPON_CARD_ACCENT, int(180 * fade))
    pygame.draw.line(card, accent, (12, 40), (card_w - 12, 40), 1)
    pygame.draw.line(card, accent, (12, card_h - 38), (card_w - 12, card_h - 38), 1)
    for (tx, ty) in ((4, 4), (card_w - 4, 4), (4, card_h - 4), (card_w - 4, card_h - 4)):
        pygame.draw.line(card, accent, (tx, ty),
                         (tx + (8 if tx < card_w // 2 else -8), ty), 1)
        pygame.draw.line(card, accent, (tx, ty),
                         (tx, ty + (8 if ty < card_h // 2 else -8)), 1)

    stamp_surf.set_alpha(int(255 * fade))
    card.blit(stamp_surf, (pad_x, 14))

    name_surf.set_alpha(int(255 * fade))
    card.blit(name_surf, (pad_x, 50))

    stat_surf.set_alpha(int(255 * fade))
    card.blit(stat_surf, (pad_x, 82))

    fy = card_h - 12 - flavor_block_h
    for fs in flavor_surfs:
        fs.set_alpha(int(255 * fade))
        card.blit(fs, (pad_x, fy))
        fy += fs.get_height() + line_gap

    surface.blit(card, (card_x, card_y))


def _draw_pickup_overlays(surface, t_ms):
    """Foreground vignette and grain applied to all three pickup beats."""
    W, H = WIDTH, HEIGHT
    rng = random.Random(int(t_ms / 40))

    # Vignette.
    vig = pygame.Surface((W, H), pygame.SRCALPHA)
    for i in range(140):
        a = int(160 * (1 - i / 140))
        pygame.draw.rect(vig, (0, 0, 0, a), (i, i, W - i * 2, H - i * 2), 1)
    surface.blit(vig, (0, 0))

    # Film grain.
    for _ in range(60):
        gx = rng.randint(0, W - 1)
        gy = rng.randint(0, H - 1)
        gv = rng.randint(180, 220)
        surface.set_at((gx, gy), (gv, gv, gv))


def draw_route12_seby_pickup(surface, shot, t_ms):
    """First-person cutscene for Biribel picking up Seby's OS-12.

    Three beats:
        seby_pickup_body   - looking down at Sebi's body, no hands visible
        seby_pickup_reach  - hands reach in, right hand grips the OS-12
        seby_pickup_raise  - weapon brought up to a centered inspect pose with
                             a full stat card in the bottom-right
    """
    scene = shot["scene"]
    lighting = shot.get("lighting", (10, 10, 12))
    t = t_ms / 1000.0

    # Authored backdrop.
    _draw_route12_pickup_backdrop(surface, t, lighting)

    if scene == "seby_pickup_body":
        # Stage 1: full cinematic intensity. Pitch eases from 38 to 46 across
        # the 2.2s beat so the framing reads as Biribel slowly lowering his
        # head, not a static stare.
        pitch = 38 + int(min(1.0, t / 2.2) * 8)
        _draw_sebi_body_fpv(surface, t, pitch_offset=pitch, intensity=1.0)

    elif scene == "seby_pickup_reach":
        # Slight forward dolly + downward pitch as Biribel kneels.
        progress = min(1.0, t / 1.4)
        pitch = 40 + int(progress * 30)
        ground_y = _draw_sebi_body_fpv(surface, t, pitch_offset=pitch,
                                       intensity=0.65)
        _draw_fpv_hands_reach(surface, t, ground_y)

    elif scene == "seby_pickup_raise":
        # Camera rises slightly as the OS-12 comes up, but Seby's corpse
        # stays visible in the lower portion of the frame (per user
        # request - previously the body slid off and faded out completely
        # via body_pitch = 70 + eased * 220 and a fade to 0).
        progress = min(1.0, t / 1.6)
        eased = 1 - (1 - progress) ** 3
        # Modest pitch: starts at 70 (matches end of stage 2), eases up to
        # ~110 so the body shifts down slightly but stays in frame. The
        # rifle inspect pose is centered at H*0.62 (~y=446 at 720p), so
        # the body (which starts at ground_y = H*0.66 + pitch) remains
        # clearly below it.
        body_pitch = 70 + int(eased * 40)
        _draw_sebi_body_fpv(surface, t, pitch_offset=body_pitch,
                            intensity=1.0)
        _draw_fpv_hands_inspect(surface, t)
        # Stat card values match the ACTUAL weapon behavior in weapons.py /
        # state.py. Previously the card advertised "30 rounds / 7.62x51 mm /
        # BATTLE RIFLE / high stopping power / slow cadence" - all of which
        # were wrong after the rebalance. Now: 25-round mag (matches
        # state.os12_mag_size), 5.56x45 intermediate cartridge (matches the
        # 28-damage-per-shot model - a full-power 7.62x51 would hit harder
        # than the pistol, not softer), assault rifle class (full-auto, not
        # a slow-cadence battle rifle), and the flavor reflects the actual
        # tradeoff: lower per-shot damage than the pistol but sustained fire.
        _draw_weapon_stat_card(
            surface, t,
            weapon_name="OS-12",
            weapon_class="ASSAULT RIFLE",
            caliber="5.56 x 45 mm",
            magazine="25 rounds",
            role="Mid-range, sustained automatic fire",
            flavor="Lower per-shot damage than the pistol. Spray to suppress.",
            stamp_text="SEBY'S OS-12 - ACQUIRED",
        )

    # Shared overlays.
    _draw_pickup_overlays(surface, t_ms)


def _draw_tinnitus_overlay(surface):
    timer = getattr(STATE, "mission2_tinnitus_timer", 0)
    if timer <= 0:
        return
    strength = min(1.0, timer / 120.0)
    gray = get_fullscreen_overlay((185, 185, 175, 255))
    gray.set_alpha(int(46 * strength))
    surface.blit(gray, (0, 0))
    red = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
    pygame.draw.rect(red, (120, 0, 0, int(45 * strength)), (0, 0, WIDTH, HEIGHT), 18)
    surface.blit(red, (0, 0))
    # Cheap disorientation: scanline jitter bars.
    for i in range(9):
        y = (_now_ms() // 6 + i * 71) % HEIGHT
        bar = get_tinnitus_bar(WIDTH)
        bar.set_alpha(int(255 * strength))
        surface.blit(bar, (_rng_legacy.randint(-5, 5), y))


def _draw_gantry(surface, fcx, fcy):
    """Full gantry: baked structure + live state (facade re-export compat)."""
    _draw_gantry_static(surface, fcx, fcy)
    _draw_gantry_dynamic(surface, fcx, fcy)


def _draw_gantry_static(target, fcx, fcy):
    """Baked gantry structure: shadow, crossbeam, towers, road signs."""
    sx, sy = _world(SNIPER_NEST_POS, fcx, fcy)
    # Platform shadow.
    shadow = pygame.Surface((330, 120), pygame.SRCALPHA)
    render_util.soft_shadow(shadow, (8, 62, 314, 36), 70)
    target.blit(shadow, (sx - 165, sy - 50))
    # Crossbeam and service catwalk.
    pygame.draw.rect(target, (46, 48, 46), (sx - 160, sy - 38, 320, 18), border_radius=2)
    pygame.draw.rect(target, (83, 84, 78), (sx - 160, sy - 38, 320, 18), 2, border_radius=2)
    for gx in range(sx - 148, sx + 150, 22):
        pygame.draw.line(target, (26, 28, 27), (gx, sy - 38), (gx + 18, sy - 20), 2)
    # Support towers.
    for lx in (sx - 142, sx + 142):
        pygame.draw.rect(target, (55, 56, 52), (lx - 8, sy - 72, 16, 90))
        pygame.draw.rect(target, (96, 95, 84), (lx - 8, sy - 72, 16, 90), 2)
        for yy in range(sy - 62, sy + 12, 14):
            pygame.draw.line(target, (25, 25, 24), (lx - 7, yy), (lx + 7, yy + 12), 2)
            pygame.draw.line(target, (25, 25, 24), (lx + 7, yy), (lx - 7, yy + 12), 2)
    # Road signs under the gantry.
    sign_rects = [pygame.Rect(sx - 108, sy - 74, 92, 40), pygame.Rect(sx + 16, sy - 74, 92, 40)]
    for i, rect in enumerate(sign_rects):
        pygame.draw.rect(target, (38, 55, 52), rect, border_radius=4)
        pygame.draw.rect(target, (150, 165, 140), rect, 2, border_radius=4)
        txt = font_terminal_small.render("ROUTE 12" if i == 0 else "CHECKPOINT", True, (205, 220, 190))
        target.blit(txt, (rect.centerx - txt.get_width() // 2, rect.y + 7))
        txt2 = font_terminal_small.render("NORTH" if i == 0 else "12", True, (160, 185, 160))
        target.blit(txt2, (rect.centerx - txt2.get_width() // 2, rect.y + 22))


def _draw_gantry_dynamic(surface, fcx, fcy):
    """Per-frame gantry state: sniper silhouette, labels, threat warning."""
    sx, sy = _world(SNIPER_NEST_POS, fcx, fcy)
    # Sniper silhouette and rifle on the gantry - ONLY drawn while the sniper
    # is still physically up there. Once the flank cutscene plays and sets
    # mission2_sniper_suppressed, this decoration is hidden so it doesn't
    # conflict with the abandoned-nest decal (casings + dropped rifle) that
    # _draw_abandoned_nest() renders at the same world position.
    if not getattr(STATE, "mission2_sniper_suppressed", False):
        pygame.draw.circle(surface, (8, 8, 8), (sx, sy - 15), 7)
        pygame.draw.rect(surface, (12, 12, 11), (sx - 6, sy - 12, 12, 19), border_radius=3)
        pygame.draw.line(surface, (8, 8, 7), (sx + 3, sy - 10), (sx - 34, sy + 20), 4)
        pygame.draw.circle(surface, (255, 230, 160), (sx - 34, sy + 20), 3)
    # Location label - keep visible even after suppression so the player
    # still has a world anchor for "that's the gantry the sniper was on".
    if getattr(STATE, "mission2_stage", "") == STAGE_SNIPER or getattr(STATE, "mission2_sniper_origin_revealed", False):
        lab = font_terminal_small.render(_T("m2.northeast_gantry"), True, (255, 170, 90))
        surface.blit(lab, (sx - lab.get_width() // 2, sy + 28))
    # Threat label: while the sniper is alive in combat, pulse a red
    # "SNIPER - ACTIVE" warning above the gantry so the player knows
    # exactly where the danger comes from and why flanking is required.
    if (getattr(STATE, "mission2_stage", "") == STAGE_COMBAT
            and getattr(STATE, "mission2_post_sniper_phase", "") in ("flank",)
            and _sniper_alive()
            and not getattr(STATE, "mission2_sniper_suppressed", False)):
        pulse = 0.55 + 0.45 * math.sin(_now_ms() * 0.006)
        threat_col = (int(255 * pulse), int(60 + 30 * pulse), int(45))
        warn_bg = pygame.Surface((220, 22), pygame.SRCALPHA)
        warn_bg.fill((0, 0, 0, int(180 * pulse)))
        pygame.draw.rect(warn_bg, threat_col, (0, 0, 220, 22), 1)
        surface.blit(warn_bg, (sx - 110, sy - 78))
        warn_lbl = font_terminal_small.render(_T("m2.sniper_active"), True, threat_col)
        surface.blit(warn_lbl, (sx - warn_lbl.get_width() // 2, sy - 75))


def _draw_actor(surface, actor, fcx, fcy):
    """Top-down KRAP squadmate. Pose is driven entirely by activity string."""
    x = actor["pos"][0] - fcx
    y = actor["pos"][1] - fcy
    name  = actor.get("name", "")
    activity = (actor.get("activity") or "standing").lower()

    # alive is ONLY used for label colour and blood - never for pose branch.
    alive = actor.get("alive", True)

    accent = {
        "GABI":   (220, 175,  70),
        "SEBY":   ( 85, 170, 225),
        "DARIUS": (110, 220, 145),
    }.get(name, C_KRAP_BLUE)
    name_col = (150, 185, 230) if alive else (130, 80, 80)

    # --- Pose flags ---------------------------------------------------
    is_down      = "down"   in activity or "dead" in activity
    is_drag_body = "dragging_body" in activity
    is_drag      = ("drag" in activity) and not is_drag_body
    is_reach     = "reach"  in activity or "radio" in activity
    is_frozen    = "frozen" in activity or "shock" in activity
    is_crouch    = is_drag or is_reach or is_frozen or "crouch" in activity or "cover" in activity
    is_shout     = "shout"  in activity or "yell" in activity

    if is_down:
        # ---- DOWNED body ------------------------------------------------
        render_util.soft_shadow(surface, (x - 28, y + 2, 56, 16), 110)
        pygame.draw.rect(surface, (36, 44, 52),
                         (x - 22, y - 10, 44, 18), border_radius=6)
        pygame.draw.rect(surface, C_KRAP_BLUE,
                         (x - 12, y - 10, 24, 4), border_radius=2)
        # Rifle dropped beside body
        pygame.draw.line(surface, (16, 16, 15),
                         (x - 26, y + 6), (x + 26, y - 4), 4)
        # Head
        pygame.draw.circle(surface, C_PLAYER_SKIN,
                           (int(x - 20), int(y - 3)), 5)
        # Blood smear
        pygame.draw.ellipse(surface, (90, 14, 14, 190),
                            (x - 14, y + 6, 28, 9))

    else:
        # ---- UPRIGHT / CROUCHED body ------------------------------------
        body_dy = 6 if is_crouch else 0
        cy = y + body_dy

        # Shadow
        sw = 44 if is_crouch else 36
        shad = pygame.Surface((sw, 14), pygame.SRCALPHA)
        render_util.soft_shadow(shad, shad.get_rect(), 70)
        surface.blit(shad, (x - sw // 2, cy + 12))

        # Legs
        boot = (10, 10, 12)
        trouser = (24, 28, 34)
        if is_crouch:
            pygame.draw.ellipse(surface, boot,    (x - 15, cy + 11, 14, 8))
            pygame.draw.ellipse(surface, boot,    (x +  1, cy + 11, 14, 8))
            pygame.draw.rect(surface,   trouser,  (x - 14, cy +  4, 10, 10), border_radius=2)
            pygame.draw.rect(surface,   trouser,  (x +  4, cy +  4, 10, 10), border_radius=2)
        else:
            pygame.draw.ellipse(surface, boot,    (x - 13, cy + 17, 12, 7))
            pygame.draw.ellipse(surface, boot,    (x +  1, cy + 17, 12, 7))
            pygame.draw.rect(surface,   trouser,  (x - 10, cy +  3,  8, 15), border_radius=2)
            pygame.draw.rect(surface,   trouser,  (x +  2, cy +  3,  8, 15), border_radius=2)

        # Torso
        torso_pts = [
            (x - 13, cy - 14), (x + 13, cy - 14),
            (x + 11, cy + 10), (x -  11, cy + 10),
        ]
        pygame.draw.polygon(surface, (44, 54, 60), torso_pts)
        pygame.draw.polygon(surface, (22, 28, 32), torso_pts, 2)
        pygame.draw.rect(surface, (34, 42, 48),
                         (x - 9, cy - 9, 18, 14), border_radius=3)
        pygame.draw.rect(surface, C_KRAP_BLUE,
                         (x - 11, cy - 12, 22, 4), border_radius=2)
        pygame.draw.circle(surface, accent, (int(x + 9), int(cy + 3)), 3)

        # --- Arms & rifle: branch on pose ---
        if is_drag:
            # Both arms extended, pulling a body behind them
            lh = (x - 24, cy + 14)
            rh = (x - 18, cy +  6)
            pygame.draw.line(surface, C_KRAP_UNIFORM,
                             (x - 11, cy - 4), lh, 5)
            pygame.draw.line(surface, C_KRAP_UNIFORM,
                             (x -  9, cy - 6), rh, 5)
            pygame.draw.circle(surface, C_PLAYER_SKIN, lh, 3)
            pygame.draw.circle(surface, C_PLAYER_SKIN, rh, 3)
            # Rifle slung across back
            pygame.draw.line(surface, (16, 16, 15),
                             (x + 6, cy - 4), (x + 22, cy + 12), 3)

        elif is_reach:
            # One arm reaching forward to grab the radio handset
            lh = (x - 12, cy + 2)
            rh = (x + 20, cy - 16)
            pygame.draw.line(surface, C_KRAP_UNIFORM,
                             (x - 11, cy - 4), lh, 5)
            pygame.draw.line(surface, C_KRAP_UNIFORM,
                             (x +  9, cy - 6), rh, 5)
            pygame.draw.circle(surface, C_PLAYER_SKIN, lh, 3)
            pygame.draw.circle(surface, C_PLAYER_SKIN, rh, 3)
            # Radio handset in reaching hand
            pygame.draw.rect(surface, (20, 24, 28),
                             (rh[0] - 3, rh[1] - 5, 6, 9), border_radius=1)
            pygame.draw.line(surface, (40, 50, 55),
                             rh, (rh[0] - 6, rh[1] + 10), 1)
            # Rifle dropped across lap
            pygame.draw.line(surface, (16, 16, 15),
                             (x - 14, cy + 8), (x + 14, cy + 8), 3)

        elif is_drag_body:
            # Hunched forward, walking backward, both arms gripping under Gabi's arms.
            arm_thick = 5
            leg_col = (24, 28, 34)
            skin = C_PLAYER_SKIN
            step = (_now_ms() // 140) % 2
            leg_off = 3 if step else -3
            pygame.draw.rect(surface, leg_col,
                             (x - 12 + leg_off, cy + 4, 7, 14), border_radius=2)
            pygame.draw.rect(surface, leg_col,
                             (x + 5 - leg_off, cy + 4, 7, 14), border_radius=2)
            lh = (x - 16, cy + 14)
            rh = (x + 4, cy + 16)
            pygame.draw.line(surface, C_KRAP_UNIFORM,
                             (x - 11, cy - 4), lh, arm_thick + 1)
            pygame.draw.line(surface, C_KRAP_UNIFORM,
                             (x + 9, cy - 6), rh, arm_thick + 1)
            pygame.draw.circle(surface, skin, lh, 4)
            pygame.draw.circle(surface, skin, rh, 4)
            pygame.draw.arc(surface, (60, 72, 84),
                (x - 18, cy - 12, 36, 24),
                math.pi * 0.8, math.pi * 1.8, 3)
            pygame.draw.line(surface, (16, 16, 15),
                (x + 8 + step, cy - 10), (x + 26 + step, cy - 2), 3)

        elif is_frozen or is_shout:
            # Rifle lowered in shock, hands gripping low
            lh = (x -  8, cy + 8)
            rh = (x + 10, cy + 10)
            pygame.draw.line(surface, (16, 16, 15),
                             lh, (x + 18, cy + 2), 3)
            pygame.draw.line(surface, C_KRAP_UNIFORM,
                             (x - 11, cy - 4), lh, 5)
            pygame.draw.line(surface, C_KRAP_UNIFORM,
                             (x +  9, cy - 6), rh, 5)
            pygame.draw.circle(surface, C_PLAYER_SKIN, lh, 3)
            pygame.draw.circle(surface, C_PLAYER_SKIN, rh, 3)

        else:
            # Standard rifle-raised scanning pose
            stock  = (x - 14, cy - 2)
            muzzle = (x + 26, cy - 8)
            lh     = (x -  4, cy - 4)
            rh     = (x + 12, cy - 6)
            pygame.draw.line(surface, (75, 55, 34),
                             (x - 22, cy), stock, 4)
            pygame.draw.line(surface, (16, 16, 15), stock, muzzle, 3)
            pygame.draw.rect(surface, (25, 26, 24),
                             (x - 8, cy - 8, 14, 6), border_radius=2)
            pygame.draw.circle(surface, (9, 9, 8), muzzle, 2)
            pygame.draw.line(surface, C_KRAP_UNIFORM,
                             (x - 11, cy - 4), lh, 5)
            pygame.draw.line(surface, C_KRAP_UNIFORM,
                             (x +  9, cy - 6), rh, 5)
            pygame.draw.circle(surface, C_PLAYER_SKIN, lh, 3)
            pygame.draw.circle(surface, C_PLAYER_SKIN, rh, 3)

        # Head
        head_y = cy - (18 if is_crouch else 24)
        pygame.draw.circle(surface, ( 7,  8,  9),
                           (int(x), int(head_y)), 10)
        pygame.draw.circle(surface, (58, 70, 82),
                           (int(x), int(head_y)),  8)
        pygame.draw.rect(surface, C_KRAP_BLUE,
                         (x - 7, head_y - 5, 14, 3), border_radius=2)
        pygame.draw.circle(surface, C_PLAYER_SKIN,
                           (int(x + 1), int(head_y + 2)), 5)
        # Eyes - dot pair
        pygame.draw.circle(surface, (35, 22, 12),
                           (int(x - 1), int(head_y + 1)), 1)
        pygame.draw.circle(surface, (35, 22, 12),
                           (int(x + 3), int(head_y + 1)), 1)

    # Eye-line toward look_at target
    if alive and actor.get("look_at"):
        lx = actor["look_at"][0] - fcx
        ly = actor["look_at"][1] - fcy
        dx, dy = lx - x, ly - y
        d = max(1.0, math.hypot(dx, dy))
        ex, ey = x + dx / d * 34, y + dy / d * 34
        pygame.draw.line(surface, (95, 150, 170),
                         (int(x), int(y)), (int(ex), int(ey)), 1)
        pygame.draw.circle(surface, (95, 150, 170),
                           (int(ex), int(ey)), 2)

    # Name label
    lbl  = font_terminal_small.render(name, True, name_col)
    shad = font_terminal_small.render(name, True, (0, 0, 0))
    label_y = y - 44 if not is_down else y - 26
    surface.blit(shad, (x - lbl.get_width() // 2 + 1, label_y + 1))
    surface.blit(lbl,  (x - lbl.get_width() // 2,     label_y))

    # Activity sub-label removed - was only used by deleted sniper cutscene.

_PROP_ICON_COLOURS = (C_TERMINAL, (245, 190, 65), (255, 190, 90))
_PROP_ICON_DOCS = ("manifest", "decree", "packet", "document")
# Bake specs of game.art.m2.prop_icon (kind, active, colour index), world scale only. Kinds whose
# body ignores active / colour share one variant; the blinking LEDs / cursor are drawn live.
_PROP_ICON_VARIANTS = (
    ("radio", True, 0),                                   # 0  radio / static
    ("mag_paint", True, 0), ("mag_paint", False, 0),      # 1-2
    ("timer_fragment", True, 0),                          # 3
    ("bootprints", True, 0),                              # 4
    ("range_card", True, 0),                              # 5
    ("manifest", True, 0), ("decree", True, 0), ("packet", True, 0), ("document", True, 0),   # 6-9
    ("terminal", True, 0), ("terminal", True, 1), ("terminal", True, 2),                     # 10-12
    ("generic", True, 0), ("generic", False, 0), ("generic", True, 1),                       # 13-18
    ("generic", False, 1), ("generic", True, 2), ("generic", False, 2),
)


def _prop_icon_variant(kind, active, color):
    """Sprite variant of a world-scale prop icon, or None when the colour is not baked."""
    try:
        ci = _PROP_ICON_COLOURS.index(tuple(color))
    except ValueError:
        return None
    if kind in ("radio", "static"):
        return 0
    if kind == "mag_paint":
        return 1 if active else 2
    if kind == "timer_fragment":
        return 3
    if kind == "bootprints":
        return 4
    if kind == "range_card":
        return 5
    if kind in _PROP_ICON_DOCS:
        return 6 + _PROP_ICON_DOCS.index(kind)
    if kind == "terminal":
        return 10 + ci
    return 13 + ci * 2 + (0 if active else 1)


def _draw_prop_icon(surface, kind, cx, cy, scale=1.0, active=True, color=C_TERMINAL):
    """Draw a readable clue/evidence prop icon.

    Used by both the in-world prop and the card preview so the object identity
    stays consistent.  Positions are snapped to pixels to prevent texture shimmer
    when the camera scrolls.

    RPE6 Phase 3: at world scale the icon body is a baked sprite (game.art.m2.prop_icon, 64 x 64
    centred); _paint_prop_icon stays the fallback / bake source and the only path for other
    scales (card previews). The blinking parts are always drawn live (_draw_prop_icon_live).
    """
    cx, cy = int(round(cx)), int(round(cy))
    if abs(float(scale) - PROP_WORLD_SCALE) < 1e-9:
        variant = _prop_icon_variant(kind, active, color)
        spr = _m2art.get("prop_icon", variant) if variant is not None else None
        if spr is not None:
            surface.blit(spr, (cx - 32, cy - 32))
            _draw_prop_icon_live(surface, kind, cx, cy, scale, active, color)
            return
    _paint_prop_icon(surface, kind, cx, cy, scale, active, color)
    _draw_prop_icon_live(surface, kind, cx, cy, scale, active, color)


def _draw_prop_icon_live(surface, kind, cx, cy, scale, active, color):
    """Pulsing accents of _draw_prop_icon (radio / relay LEDs, terminal cursor); drawn after the
    body - none of them overlaps a later draw of the body."""
    s = max(0.35, float(scale))
    pulse = 0.5 + 0.5 * math.sin(_now_ms() * 0.006)
    if kind == "radio" or kind == "static":
        w, h = int(34 * s), int(24 * s)
        x, y = cx - w // 2, cy - h // 2
        led = (255, 45, 30) if active and pulse > 0.58 else (75, 18, 14)
        pygame.draw.circle(surface, led, (x + w - int(5*s), y + int(5*s)), max(2, int(2*s)))
    elif kind == "timer_fragment":
        w, h = int(42*s), int(28*s)
        x, y = cx - w//2, cy - h//2
        pygame.draw.circle(surface, (255, 55, 38) if active and pulse > 0.5 else (90, 22, 18), (x + w - int(8*s), y + int(8*s)), max(2, int(3*s)))
    elif kind == "terminal":
        w, h = int(48*s), int(38*s)
        x, y = cx - w//2, cy - h//2
        # Blinking upload cursor.
        cur_col = color if active and pulse > 0.5 else (max(0, color[0]//4), max(0, color[1]//4), max(0, color[2]//4))
        pygame.draw.rect(surface, cur_col, (x + w - int(15*s), y + int(8*s), int(3*s), int(5*s)))


def _paint_prop_icon(surface, kind, cx, cy, scale=1.0, active=True, color=C_TERMINAL):
    """Procedural prop-icon body (no pulsing parts; see _draw_prop_icon_live)."""
    s = max(0.35, float(scale))
    cx, cy = int(round(cx)), int(round(cy))
    if kind == "radio" or kind == "static":
        # Smaller broken field radio: cracked case, bent antenna, dead speaker,
        # loose wire, and a failing red indicator.
        w, h = int(34 * s), int(24 * s)
        x, y = cx - w // 2, cy - h // 2
        pygame.draw.rect(surface, (10, 13, 14), (x, y, w, h), border_radius=max(2, int(3*s)))
        pygame.draw.rect(surface, (74, 86, 88), (x, y, w, h), max(1, int(2*s)), border_radius=max(2, int(3*s)))
        # Chipped corner.
        chip = [(x + w - int(8*s), y), (x + w, y), (x + w, y + int(8*s))]
        pygame.draw.polygon(surface, (4, 6, 7), chip)
        # Cracked display.
        pygame.draw.rect(surface, (3, 6, 7), (x + int(5*s), y + int(6*s), int(13*s), int(8*s)))
        pygame.draw.line(surface, (55, 75, 76), (x + int(6*s), y + int(7*s)), (x + int(16*s), y + int(13*s)), max(1, int(1*s)))
        pygame.draw.line(surface, (55, 75, 76), (x + int(12*s), y + int(7*s)), (x + int(9*s), y + int(14*s)), max(1, int(1*s)))
        # Speaker/knob, dark and damaged.
        pygame.draw.circle(surface, (25, 29, 30), (x + int(25*s), y + int(13*s)), max(4, int(5*s)))
        pygame.draw.circle(surface, (8, 10, 11), (x + int(25*s), y + int(13*s)), max(2, int(3*s)))
        # Bent antenna and loose cable.
        pygame.draw.line(surface, (82, 90, 92), (x + int(7*s), y + int(1*s)), (x - int(5*s), y - int(13*s)), max(1, int(2*s)))
        pygame.draw.line(surface, (82, 90, 92), (x - int(5*s), y - int(13*s)), (x - int(2*s), y - int(20*s)), max(1, int(1*s)))
        pygame.draw.line(surface, (45, 48, 42), (x + int(8*s), y + h), (x - int(8*s), y + h + int(8*s)), max(1, int(2*s)))
        pygame.draw.circle(surface, (38, 40, 36), (x - int(9*s), y + h + int(8*s)), max(1, int(2*s)))
    elif kind == "mag_paint":
        tag = font_terminal.render(_T("m2.mag"), True, (22, 22, 20))
        tag = pygame.transform.rotate(tag, -9)
        if scale != 1.0:
            tag = pygame.transform.smoothscale(tag, (max(1, int(tag.get_width()*s)), max(1, int(tag.get_height()*s))))
        tag.set_alpha(190 if active else 120)
        surface.blit(tag, (cx - tag.get_width()//2, cy - tag.get_height()//2))
        pygame.draw.line(surface, (18, 18, 16), (cx - int(28*s), cy + int(18*s)), (cx + int(30*s), cy - int(16*s)), max(2, int(3*s)))
        pygame.draw.rect(surface, (95, 90, 75), (cx + int(32*s), cy - int(20*s), int(10*s), int(22*s)), border_radius=max(1, int(2*s)))
        pygame.draw.rect(surface, (25, 25, 25), (cx + int(32*s), cy - int(25*s), int(10*s), int(5*s)))
    elif kind == "timer_fragment":
        # Charred circuit/timing relay with clipped wires.
        w, h = int(42*s), int(28*s)
        x, y = cx - w//2, cy - h//2
        pygame.draw.rect(surface, (10, 20, 14), (x, y, w, h), border_radius=max(2, int(3*s)))
        pygame.draw.rect(surface, (42, 92, 58), (x, y, w, h), max(1, int(2*s)), border_radius=max(2, int(3*s)))
        for wx1, wx2 in [(-int(11*s), -int(2*s)), (w + int(2*s), w + int(12*s))]:
            pygame.draw.line(surface, (120, 45, 35), (x + wx1, y + int(7*s)), (x + wx2, y + int(15*s)), max(1, int(2*s)))
        for i, chip_col in enumerate([(18, 50, 28), (58, 120, 70), (20, 35, 28)]):
            pygame.draw.rect(surface, chip_col, (x + int((7 + i*11)*s), y + int(7*s), int(7*s), int(6*s)))
        pygame.draw.arc(surface, (25, 25, 20), (x - int(7*s), y - int(6*s), w + int(14*s), h + int(16*s)), 0.2, 2.7, max(1, int(2*s)))
    elif kind == "bootprints":
        # Two clean square-tread government prints crossing the blast soot.
        w, h = int(18*s), int(32*s)
        for i, (ox, oy, rot) in enumerate([(-10, -8, -10), (9, 9, 8)]):
            foot = pygame.Surface((w + 8, h + 8), pygame.SRCALPHA)
            pygame.draw.rect(foot, (30, 27, 23), (4, 3, w, h), border_radius=max(2, int(4*s)))
            pygame.draw.rect(foot, (12, 12, 10), (5, 4, w-2, h-2), max(1, int(1*s)), border_radius=max(2, int(4*s)))
            for ty in range(7, max(8, h - 4), max(4, int(6*s))):
                pygame.draw.line(foot, (82, 75, 58), (7, ty), (w + 1, ty), max(1, int(1*s)))
            foot = pygame.transform.rotate(foot, rot)
            surface.blit(foot, (cx + int(ox*s) - foot.get_width()//2, cy + int(oy*s) - foot.get_height()//2))
        pygame.draw.arc(surface, (92, 82, 55), (cx - int(28*s), cy - int(20*s), int(56*s), int(42*s)), 3.4, 5.9, max(1, int(1*s)))
    elif kind == "range_card":
        # Scratch marks / folded range card foreshadowing the kill-box.
        w, h = int(46*s), int(32*s)
        x, y = cx - w//2, cy - h//2
        pygame.draw.rect(surface, (0, 0, 0), (x + int(3*s), y + int(4*s), w, h), border_radius=max(1, int(2*s)))
        pygame.draw.polygon(surface, (185, 174, 132), [(x, y), (x+w, y+int(3*s)), (x+w-int(4*s), y+h), (x+int(3*s), y+h-int(2*s))])
        pygame.draw.polygon(surface, (80, 65, 42), [(x, y), (x+w, y+int(3*s)), (x+w-int(4*s), y+h), (x+int(3*s), y+h-int(2*s))], max(1, int(1*s)))
        for i, mark in enumerate(("180", "220", "260")):
            yy = y + int((7 + i*8)*s)
            pygame.draw.line(surface, (95, 68, 45), (x + int(7*s), yy), (x + int(24*s), yy), max(1, int(1*s)))
            if s >= 0.8:
                txt = font_terminal_small.render(mark, True, (75, 48, 35))
                txt = pygame.transform.smoothscale(txt, (max(1, int(txt.get_width()*s*0.55)), max(1, int(txt.get_height()*s*0.55))))
                surface.blit(txt, (x + int(27*s), yy - int(5*s)))
        pygame.draw.line(surface, (155, 35, 30), (x + int(8*s), y + h - int(7*s)), (x + w - int(8*s), y + int(6*s)), max(1, int(2*s)))
    elif kind in ("manifest", "decree", "packet", "document"):
        w, h = int(38*s), int(48*s)
        x, y = cx - w//2, cy - h//2
        paper_col = (215, 205, 174) if kind != "packet" else (185, 170, 130)
        pygame.draw.rect(surface, (0, 0, 0), (x + int(3*s), y + int(4*s), w, h), border_radius=max(1, int(2*s)))
        pygame.draw.rect(surface, paper_col, (x, y, w, h), border_radius=max(1, int(2*s)))
        pygame.draw.rect(surface, (75, 60, 42), (x, y, w, h), max(1, int(1*s)), border_radius=max(1, int(2*s)))
        if kind == "manifest":
            pygame.draw.rect(surface, (70, 55, 35), (x + int(8*s), y - int(5*s), int(22*s), int(8*s)), border_radius=max(1, int(2*s)))
        if kind == "decree":
            pygame.draw.rect(surface, (160, 35, 30), (x + int(5*s), y + int(7*s), w - int(10*s), int(8*s)))
        for i in range(4):
            yy = y + int((18 + i*7)*s)
            pygame.draw.line(surface, (95, 82, 62), (x + int(7*s), yy), (x + w - int(7*s), yy), max(1, int(1*s)))
        if kind == "packet":
            pygame.draw.circle(surface, (155, 30, 28), (x + w - int(10*s), y + int(12*s)), max(3, int(5*s)), max(1, int(1*s)))
    elif kind == "terminal":
        # Green CRT-style upload terminal: dark monitor body, glowing
        # phosphor screen, scrollbar tick marks, blinking cursor dot.
        w, h = int(48*s), int(38*s)
        x, y = cx - w//2, cy - h//2
        pygame.draw.rect(surface, (0, 0, 0), (x + int(3*s), y + int(4*s), w, h), border_radius=max(2, int(4*s)))
        pygame.draw.rect(surface, (40, 60, 45), (x, y, w, h), border_radius=max(2, int(4*s)))
        pygame.draw.rect(surface, color, (x, y, w, h), max(1, int(2*s)), border_radius=max(2, int(4*s)))
        # Screen.
        pygame.draw.rect(surface, (8, 26, 18), (x + int(6*s), y + int(6*s), w - int(12*s), h - int(16*s)))
        pygame.draw.rect(surface, color, (x + int(6*s), y + int(6*s), w - int(12*s), h - int(16*s)), max(1, int(1*s)))
        # Three scan lines.
        for i in range(3):
            yy = y + int((12 + i*7)*s)
            pygame.draw.line(surface, color, (x + int(10*s), yy), (x + w - int(10*s), yy), max(1, int(1*s)))
        # Stand.
        pygame.draw.rect(surface, (35, 45, 38), (x + w//2 - int(8*s), y + h - int(8*s), int(16*s), int(10*s)), border_radius=max(1, int(2*s)))
    else:
        w, h = int(54*s), int(38*s)
        x, y = cx - w//2, cy - h//2
        pygame.draw.rect(surface, (4, 9, 10), (x, y, w, h), border_radius=max(2, int(4*s)))
        pygame.draw.rect(surface, color, (x, y, w, h), max(1, int(2*s)), border_radius=max(2, int(4*s)))
        pygame.draw.rect(surface, (7, 22, 18), (x + int(7*s), y + int(7*s), w - int(14*s), h - int(16*s)))
        for i in range(3):
            yy = y + int((12 + i*6)*s)
            pygame.draw.line(surface, color, (x + int(12*s), yy), (x + w - int(12*s), yy), max(1, int(1*s)))
        if active:
            pygame.draw.circle(surface, color, (x + w - int(8*s), y + int(8*s)), max(2, int(3*s)))


def _draw_world_prop(surface, item, fcx, fcy, active=True):
    sx, sy = _world(item["pos"], fcx, fcy)
    kind = item.get("kind", item.get("id", "document"))
    if item in getattr(STATE, "mission2_clues", []):
        prop_col = (245, 190, 65)
    elif kind == "manifest":
        prop_col = (255, 190, 90)
    else:
        prop_col = C_TERMINAL

    # Small object, readable silhouette: visibility comes from a restrained halo
    # instead of oversized clue art.  Completed props stay visible but quieter.
    halo_r = PROP_WORLD_HALO_RADIUS
    halo = pygame.Surface((halo_r * 2 + 8, halo_r * 2 + 8), pygame.SRCALPHA)
    pulse = 0.62 + 0.38 * math.sin(_now_ms() * 0.005)
    halo_alpha = int((48 if active else 20) * pulse)
    pygame.draw.circle(halo, (*prop_col, halo_alpha), (halo_r + 4, halo_r + 4), halo_r)
    pygame.draw.circle(halo, (*prop_col, min(120, halo_alpha + 38)), (halo_r + 4, halo_r + 4), halo_r, 1)
    surface.blit(halo, (sx - halo_r - 4, sy - halo_r - 4))

    _draw_prop_icon(surface, kind, sx, sy, scale=PROP_WORLD_SCALE, active=active, color=prop_col)


def _draw_marker(surface, pos, label, col, fcx, fcy, radius=MARKER_RADIUS):
    sx, sy = _world(pos, fcx, fcy)
    pulse = int(80 + math.sin(_now_s() * 5) * 35)
    if -60 < sx < WIDTH + 60 and -60 < sy < HEIGHT + 60:
        ring = pygame.Surface((radius * 3, radius * 3), pygame.SRCALPHA)
        pygame.draw.circle(ring, (*col, pulse), (radius * 3 // 2, radius * 3 // 2), radius, 2)
        pygame.draw.circle(ring, (*col, pulse // 2), (radius * 3 // 2, radius * 3 // 2), radius + 5, 1)
        surface.blit(ring, (sx - radius * 3 // 2, sy - radius * 3 // 2))
        txt = font_terminal_small.render(label, True, col)
        surface.blit(txt, (sx - txt.get_width() // 2, sy - radius - 23))
    else:
        # Edge arrow.
        cx = max(32, min(WIDTH - 32, sx))
        cy = max(90, min(HEIGHT - 58, sy))
        ang = math.atan2(sy - HEIGHT / 2, sx - WIDTH / 2)
        pts = [
            (cx + math.cos(ang) * 16, cy + math.sin(ang) * 16),
            (cx + math.cos(ang + 2.45) * 12, cy + math.sin(ang + 2.45) * 12),
            (cx + math.cos(ang - 2.45) * 12, cy + math.sin(ang - 2.45) * 12),
        ]
        pygame.draw.polygon(surface, col, pts)
        txt = font_terminal_small.render(label, True, col)
        surface.blit(txt, (cx - txt.get_width() // 2, cy + 16))


def _draw_shelter(surface, fcx, fcy):
    """Draw the concrete outpost shelter at SAFE_ZONE.

    A top-down military fighting position / forward outpost - NOT a house.
    The player runs here during the 7-second tanker countdown to survive
    the blast (within ~110px of SAFE_ZONE = survivable debris scrape).

    Design (top-down view, N = up, tanker is NE = up-right):
      ┌─────────────────────────────────────────────┐
      │  NE quadrant: thick crescent BLAST WALL     │  ← tanker side
      │  (curved wall, 14px thick, sandbags outside)│
      ├─────────────────────────────────────────────┤
      │  radio    CONCRETE PAD (floor)   ammo crate │
      │  mast     ← player stands here              │
      │            (open, no roof)                  │
      └─────────────────────────────────────────────┘
                       SW side (open entrance)

    The blast wall is on the NE side (between the shelter and the tanker)
    so it reads as "this is the protected side." The SW side is open -
    that's where the player enters and stands. There is NO roof and NO
    building body, so in top-down view the player appears to stand INSIDE
    the position on the concrete pad, not ON TOP of a house.

    The blue accent stripe on the interior face of the blast wall matches
    C_VASILE / the "RUN HERE" marker color, so all wayfinding cues read
    as a coherent system.
    """
    sx, sy = _world(SAFE_ZONE, fcx, fcy)
    # Cull if entirely off-screen (shelter footprint is ~130x110).
    # Skipped while baking: chunk-relative coords are not screen coords.
    if not staticlayer.baking() and (sx < -150 or sx > WIDTH + 150 or sy < -150 or sy > HEIGHT + 150):
        return

    # ── Color palette (concrete military outpost) ──
    pad_col = (88, 85, 78)        # concrete floor (darker than building walls)
    pad_edge = (60, 58, 54)       # pad outline
    wall_col = (130, 124, 114)    # blast wall (lighter concrete, reads as raised)
    wall_dark = (82, 78, 72)      # wall shadow / outline
    wall_inner = (150, 144, 132)  # wall interior face (lit edge)
    sandbag_col = (95, 80, 55)
    sandbag_dark = (62, 52, 36)
    accent = (100, 160, 220)      # C_VASILE - links to "RUN HERE" marker
    metal_col = (70, 72, 76)
    crate_col = (110, 88, 52)

    # ════════════════════════════════════════════════════════════════
    # 1. CONCRETE PAD (floor) - the survival zone the player stands on.
    #    Drawn as a rounded rectangle, slightly larger than the player's
    #    survival radius so it visually contains the safe area.
    # ════════════════════════════════════════════════════════════════
    pad_w, pad_h = 112, 96
    pad_rect = pygame.Rect(sx - pad_w // 2, sy - pad_h // 2, pad_w, pad_h)
    pygame.draw.rect(surface, pad_col, pad_rect, border_radius=6)
    pygame.draw.rect(surface, pad_edge, pad_rect, 2, border_radius=6)

    # Expansion joints on the pad (subtle concrete texture - two lines
    # dividing the pad into quarters, so it doesn't read as a flat fill).
    pygame.draw.line(surface, (78, 75, 70),
                     (sx, pad_rect.top + 4), (sx, pad_rect.bottom - 4), 1)
    pygame.draw.line(surface, (78, 75, 70),
                     (pad_rect.left + 4, sy), (pad_rect.right - 4, sy), 1)

    # ════════════════════════════════════════════════════════════════
    # 2. BLAST WALL (NE side) - thick crescent wall between the shelter
    #    and the tanker. Drawn as a filled polygon following an arc from
    #    N (up) to E (right), convex toward NE (up-right). This is the
    #    "cover" that blocks the blast.
    # ════════════════════════════════════════════════════════════════
    wall_outer_r = 66   # outer radius (blast face)
    wall_inner_r = 50   # inner radius (player face) - 16px thick wall
    # Arc spans the NE quadrant: math angle 0° (E) to 90° (N).
    # In screen coords: x = cos(angle) * r, y = -sin(angle) * r
    #   (negative sin because screen y goes down, but "north" is up)
    num_arc_pts = 14
    outer_pts = []
    inner_pts = []
    for i in range(num_arc_pts + 1):
        t = i / num_arc_pts
        angle = math.radians(90.0 * t)  # 0° → 90°
        ox = sx + math.cos(angle) * wall_outer_r
        oy = sy - math.sin(angle) * wall_outer_r
        ix = sx + math.cos(angle) * wall_inner_r
        iy = sy - math.sin(angle) * wall_inner_r
        outer_pts.append((ox, oy))
        inner_pts.append((ix, iy))
    # Wall polygon: outer arc forward + inner arc reversed
    wall_poly = outer_pts + list(reversed(inner_pts))
    pygame.draw.polygon(surface, wall_col, wall_poly)
    pygame.draw.polygon(surface, wall_dark, wall_poly, 2)

    # Inner face highlight (lit edge on the player side) - a thin lighter
    # line along the inner arc so the wall reads as 3D, not flat.
    pygame.draw.lines(surface, wall_inner, False, inner_pts, 2)

    # Blue accent stripe on the interior face of the wall - this is the
    # "shelter" identifier. Matches C_VASILE / the "RUN HERE" marker color
    # so the player links the structure to the marker system.
    # Drawn as a thin arc just inside the inner edge.
    stripe_r = wall_inner_r - 5
    stripe_pts = []
    for i in range(num_arc_pts + 1):
        t = i / num_arc_pts
        angle = math.radians(90.0 * t)
        stripe_pts.append((
            sx + math.cos(angle) * stripe_r,
            sy - math.sin(angle) * stripe_r,
        ))
    pygame.draw.lines(surface, accent, False, stripe_pts, 2)

    # ════════════════════════════════════════════════════════════════
    # 3. SANDBAG REVETMENT - row of sandbags along the outer (NE) face
    #    of the blast wall. Reads as fortified fighting position.
    # ════════════════════════════════════════════════════════════════
    num_bags = 7
    for i in range(num_bags):
        t = (i + 0.5) / num_bags
        angle = math.radians(90.0 * t)
        bx = sx + math.cos(angle) * (wall_outer_r + 8)
        by = sy - math.sin(angle) * (wall_outer_r + 8)
        # Each sandbag is a small ellipse, rotated to follow the arc.
        # Simplified: just draw a small ellipse at each position.
        bag_rect = pygame.Rect(0, 0, 20, 12)
        bag_rect.center = (int(bx), int(by))
        pygame.draw.ellipse(surface, sandbag_col, bag_rect)
        pygame.draw.ellipse(surface, sandbag_dark, bag_rect, 1)
        # Center seam on each bag
        pygame.draw.line(surface, sandbag_dark,
                         (bag_rect.centerx, bag_rect.top + 1),
                         (bag_rect.centerx, bag_rect.bottom - 1), 1)

    # ════════════════════════════════════════════════════════════════
    # 4. RADIO MAST (NW corner of pad) - outpost identifier. A thin
    #    vertical mast with a small antenna dish on top. Reads as
    #    "communications point" / "forward base."
    # ════════════════════════════════════════════════════════════════
    mast_x = pad_rect.left + 12
    mast_y_top = pad_rect.top + 6
    mast_y_bot = pad_rect.top + 28
    # Mast pole
    pygame.draw.line(surface, metal_col,
                     (mast_x, mast_y_top), (mast_x, mast_y_bot), 2)
    # Antenna dish (small triangle on top)
    pygame.draw.polygon(surface, metal_col, [
        (mast_x, mast_y_top - 6),
        (mast_x - 5, mast_y_top + 2),
        (mast_x + 5, mast_y_top + 2),
    ])
    pygame.draw.polygon(surface, (45, 47, 50), [
        (mast_x, mast_y_top - 6),
        (mast_x - 5, mast_y_top + 2),
        (mast_x + 5, mast_y_top + 2),
    ], 1)
    # Guy wire (diagonal support line)
    pygame.draw.line(surface, (50, 50, 52),
                     (mast_x, mast_y_bot), (mast_x + 10, mast_y_bot + 6), 1)

    # ════════════════════════════════════════════════════════════════
    # 5. AMMO CRATE (SW part of pad) - detail + scale reference. A small
    #    wooden crate so the pad doesn't look empty and the player has a
    #    sense of the position's purpose (resupply / holdout point).
    # ════════════════════════════════════════════════════════════════
    crate_x = sx - 8
    crate_y = sy + 18
    crate_rect = pygame.Rect(crate_x, crate_y, 18, 12)
    pygame.draw.rect(surface, crate_col, crate_rect, border_radius=1)
    pygame.draw.rect(surface, (70, 54, 30), crate_rect, 1, border_radius=1)
    # Crate lid line
    pygame.draw.line(surface, (70, 54, 30),
                     (crate_x, crate_y + 4), (crate_x + 18, crate_y + 4), 1)
    # Metal corner brackets
    pygame.draw.rect(surface, (90, 88, 85), (crate_x, crate_y, 3, 3))
    pygame.draw.rect(surface, (90, 88, 85), (crate_x + 15, crate_y, 3, 3))

    # ════════════════════════════════════════════════════════════════
    # 6. LABEL during STAGE_RUN - small caption below the pad so the
    #    player can confirm "this is the shelter" at a glance.
    # ════════════════════════════════════════════════════════════════
    # Per-frame (stage-dependent) caption: _draw_shelter_live. The chunk cache used to freeze it.
    if not staticlayer.baking():
        _draw_shelter_live(surface, fcx, fcy)


def _draw_shelter_live(surface, fcx, fcy):
    """Stage-dependent part of the shelter: the SHELTER caption shown during the tanker run."""
    if getattr(STATE, "mission2_stage", "") != STAGE_RUN:
        return
    sx, sy = _world(SAFE_ZONE, fcx, fcy)
    if sx < -150 or sx > WIDTH + 150 or sy < -150 or sy > HEIGHT + 150:
        return
    pad_w, pad_h = 112, 96                     # mirrors the pad rect in _draw_shelter
    pad_bottom = pygame.Rect(sx - pad_w // 2, sy - pad_h // 2, pad_w, pad_h).bottom
    label = font_terminal_small.render(_T("m2.shelter"), True, (100, 160, 220))
    bg = pygame.Surface((label.get_width() + 8, label.get_height() + 2), pygame.SRCALPHA)
    bg.fill((0, 0, 0, 150))
    surface.blit(bg, (sx - bg.get_width() // 2, pad_bottom + 4))
    surface.blit(label, (sx - label.get_width() // 2, pad_bottom + 5))


def _draw_shelter_arrow(surface, fcx, fcy):
    """Draw a persistent directional arrow above the player pointing to SAFE_ZONE.

    Only draws during STAGE_RUN (the 7-second tanker countdown). The arrow
    hovers above the player's head and always points toward the shelter,
    so the player never has to look at screen edges or the minimap to know
    which way to run - they just follow the arrow.

    Visual language:
      - Blue color (matches C_VASILE / "RUN HERE" marker / shelter accent
        stripe) so all the wayfinding cues read as a coherent system.
      - Pulsing alpha for urgency (driven by time.time, same cadence as
        the _draw_marker pulse so they beat in sync).
      - Distance label under the arrow ("42m") so the player can gauge
        progress and know when they're close.
      - Arrow is drawn in SCREEN space (not world space) so it stays
        pinned above the player even when the camera is panning.
    """
    if not STATE.player or STATE.player_dead:
        return
    if getattr(STATE, "mission2_stage", "") != STAGE_RUN:
        return

    # Player position in screen space
    px = STATE.player.rect.centerx - fcx
    py = STATE.player.rect.centery - fcy

    # Direction from player to shelter (world space, then normalized)
    dx = SAFE_ZONE[0] - STATE.player.rect.centerx
    dy = SAFE_ZONE[1] - STATE.player.rect.centery
    dist = math.hypot(dx, dy)
    if dist < 1:
        return  # player is at the shelter - no arrow needed
    ndx = dx / dist
    ndy = dy / dist

    # Arrow position: 40px above the player's head (player sprite is ~30px
    # tall, so 40px clears the head/helmet).
    arrow_x = px
    arrow_y = py - 40

    # Arrow angle: atan2 gives the angle of the direction vector. We want
    # the arrow to point in the direction of (ndx, ndy), so the arrow's
    # "forward" axis aligns with that vector.
    ang = math.atan2(ndy, ndx)

    # Pulsing alpha for urgency (beats in sync with _draw_marker's pulse).
    pulse = int(180 + math.sin(_now_s() * 5) * 60)

    # Draw the arrow as a triangle pointing in the direction of `ang`.
    # Arrow size: 14px long, 10px wide at the base.
    arrow_len = 14
    arrow_w = 10
    # Tip of the arrow (in the direction of ang)
    tip_x = arrow_x + math.cos(ang) * arrow_len
    tip_y = arrow_y + math.sin(ang) * arrow_len
    # Base corners (perpendicular to ang, behind the tip)
    base_x = arrow_x - math.cos(ang) * (arrow_len * 0.4)
    base_y = arrow_y - math.sin(ang) * (arrow_len * 0.4)
    perp_x = math.cos(ang + math.pi / 2) * (arrow_w / 2)
    perp_y = math.sin(ang + math.pi / 2) * (arrow_w / 2)

    # Draw on a transparent surface so we can apply alpha to the whole arrow.
    arrow_surf = pygame.Surface((40, 40), pygame.SRCALPHA)
    cx, cy = 20, 20  # local center of the arrow surface
    # Translate points to local space
    tip = (int(tip_x - arrow_x + cx), int(tip_y - arrow_y + cy))
    b1 = (int(base_x + perp_x - arrow_x + cx), int(base_y + perp_y - arrow_y + cy))
    b2 = (int(base_x - perp_x - arrow_x + cx), int(base_y - perp_y - arrow_y + cy))
    accent = (100, 160, 220)
    pygame.draw.polygon(arrow_surf, (*accent, pulse), [tip, b1, b2])
    pygame.draw.polygon(arrow_surf, (255, 255, 255, pulse), [tip, b1, b2], 1)
    surface.blit(arrow_surf, (arrow_x - cx, arrow_y - cy))

    # Distance label under the arrow (in meters - 1 tile = 64px, so meters
    # ≈ px / 64). Helps the player gauge progress.
    meters = max(0, int(dist / 64))
    label = font_terminal_small.render(_T("m2.meters_m", meters=meters), True, accent)
    label_surf = pygame.Surface((label.get_width() + 6, label.get_height() + 2), pygame.SRCALPHA)
    label_surf.fill((0, 0, 0, 140))
    label_surf.blit(label, (3, 1))
    surface.blit(label_surf, (arrow_x - label_surf.get_width() // 2, arrow_y + 12))


# ════════════════════════════════════════════════════════════════════════
# OFFICERS' LEISURE GARDEN (behind the control building)
# ════════════════════════════════════════════════════════════════════════
# A manicured garden behind the control building - environmental
# storytelling contrast with the frame-up happening inside. Layout
# constants (hedge/fountain/lamp/tree/bench rects) are defined at module
# scope near the top of the file; this section is the draw + collision
# wiring.

# Pre-render the grass texture once (deterministic noise so it doesn't
# shimmer per frame). The garden sits on mud tiles by default; we overlay
# a grass surface to make it read as a cultivated garden, not a muddy lot.
_GRASS_W, _GRASS_H = 17 * TILE_SIZE, 8 * TILE_SIZE  # cols 51-67, rows 1-8
_grass_surf = pygame.Surface((_GRASS_W, _GRASS_H))
_grass_surf.fill((42, 58, 38))  # base grass green
# Deterministic grass speckle (dark + light blades) so the surface isn't flat.
# RPE6 B-008: a private generator. This used to be `import random as _rng`,
# so the seed(...)/seed() pairs below re-seeded the GLOBAL stream (seed() with
# no argument = OS entropy) and made every later random value unrepeatable.
_rng = random.Random()
_rng.seed(7919)  # fixed seed - same texture every run
for _ in range(380):
    _gx = _rng.randint(0, _GRASS_W - 1)
    _gy = _rng.randint(0, _GRASS_H - 1)
    _shade = _rng.choice([(32, 48, 28), (52, 70, 44), (60, 82, 52)])
    pygame.draw.circle(_grass_surf, _shade, (_gx, _gy), _rng.randint(1, 2))
_rng.seed()  # unseed - don't pollute the global RNG state


def _build_garden_walls():
    """Populate STATE.mission2_garden_walls with all garden collision rects.

    Called once from start_mission2() (after _build_shelter_walls). The
    dev-args shortcuts inherit it via start_mission2(). Includes:
      - 4 hedge quadrant rects (the main movement-blocking elements)
      - 1 fountain rect (solid stone basin)
      - 2 lamp post rects (thin poles at path entrances)
      - 4 tree trunk rects (corners)
      - 2 bench rects (on the path)
    Total: 13 collision rects. All are axis-aligned and use the same
    _solid_walls() path as everything else, so the player, enemies, and
    bullets all collide with them.
    """
    STATE.mission2_garden_walls = (
        list(GARDEN_HEDGE_RECTS)
        + [GARDEN_FOUNTAIN_RECT]
        + list(GARDEN_LAMP_RECTS)
        + list(GARDEN_TREE_RECTS)
        + list(GARDEN_BENCH_RECTS)
    )


def _draw_garden_fountain_fx(surface, fcx, fcy):
    """Live fountain water: spout, splash dots, ripple rings (never baked)."""
    fx, fy = GARDEN_CENTER
    fsx, fsy = fx - fcx, fy - fcy
    if not render_util.screen_visible(fsx - 90, fsy - 90, 180, 180):
        return
    water_outer_r = 60 - 6
    # Water spout from the finial (small droplet arc)
    t_anim = _now_s()
    spout_h = 6 + int(math.sin(t_anim * 4) * 3)
    pygame.draw.line(surface, (160, 210, 230),
                     (int(fsx), int(fsy - 20)),
                     (int(fsx), int(fsy - 20 - spout_h)), 2)
    # Splash particles (small white dots around the inner basin water surface)
    _rng.seed(int(t_anim * 10) % 100)
    for _ in range(6):
        sa = _rng.uniform(0, math.tau)
        sr = _rng.randint(10, 24)
        spx = fsx + math.cos(sa) * sr
        spy = fsy - 4 + math.sin(sa) * sr
        pygame.draw.circle(surface, (200, 230, 240), (int(spx), int(spy)), 1)
    _rng.seed()
    # Ripple rings (2 concentric, animated)
    for i in range(2):
        phase = (t_anim * 0.7 + i * 0.5) % 1.0
        rr = int(water_outer_r * (0.2 + 0.8 * phase))
        alpha = int(100 * (1.0 - phase))
        if alpha > 0 and rr > 2:
            ripple_surf = pygame.Surface((rr * 2 + 6, rr * 2 + 6), pygame.SRCALPHA)
            pygame.draw.circle(ripple_surf, (180, 220, 240, alpha),
                               (rr + 3, rr + 3), rr, 1)
            surface.blit(ripple_surf, (int(fsx - rr - 3), int(fsy - rr - 3)))


def _draw_garden(surface, fcx, fcy):
    """Draw the officers' leisure garden behind the control building.

    Rich-complexity garden with 9 upgraded prop types (visual pass 2):
      1. Grass overlay (pre-rendered: blade strokes + color patches + edge darken)
      2. Stone path (per-stone bevels + moss in cracks + worn center)
      3. 4 hedge quadrants (organic bump shape + 3-layer depth + clustered leaves)
      4. Central fountain (two-tier basin + depth-gradient water + splash + finial)
      5. 2 benches (backrest + armrests + wood grain + shadow)
      6. 2 lamp posts (cast-iron base + fluted pole + lantern + radial glow)
      7. 4 ornamental trees (multi-layer canopy + branches + fallen leaves)
      8. Flower beds (stems + leaves + large multi-petal blooms + clusters)
      9. Wrought-iron fence (vertical bars + corner posts + spear finials)
     10. Garden gate (arched entrance with decorative ironwork)

    Drawn in ALL mission 2 stages - pure environmental storytelling.
    """
    gx0 = 51 * TILE_SIZE
    gy0 = 1 * TILE_SIZE
    sx0, sy0 = gx0 - fcx, gy0 - fcy
    # Skipped while baking: chunk-relative coords are not screen coords.
    if not staticlayer.baking() and (sx0 > WIDTH + 100 or sx0 + _GRASS_W < -100 or sy0 > HEIGHT + 100 or sy0 + _GRASS_H < -100):
        return

    # ══════════════════════════════════════════════════════════════════
    # 1. GRASS OVERLAY (upgraded: blade strokes + color patches + edge darken)
    # ══════════════════════════════════════════════════════════════════
    surface.blit(_grass_surf, (int(sx0), int(sy0)))
    # Grass blade strokes (small vertical lines in lighter green, clustered
    # into patches so the grass reads as tufted, not uniform).
    _rng.seed(31337)
    for _ in range(120):
        bx = int(sx0) + _rng.randint(0, _GRASS_W - 1)
        by = int(sy0) + _rng.randint(0, _GRASS_H - 1)
        blade_col = _rng.choice([(58, 88, 48), (48, 78, 40), (65, 98, 55)])
        # 2-3px vertical blade
        pygame.draw.line(surface, blade_col, (bx, by), (bx, by - _rng.randint(2, 4)), 1)
    # Darker patches (reads as damp / shaded grass)
    for _ in range(8):
        px = int(sx0) + _rng.randint(20, _GRASS_W - 20)
        py = int(sy0) + _rng.randint(20, _GRASS_H - 20)
        patch = pygame.Surface((40, 30), pygame.SRCALPHA)
        pygame.draw.ellipse(patch, (28, 44, 26, 80), (0, 0, 40, 30))
        surface.blit(patch, (px - 20, py - 15))
    _rng.seed()

    # ══════════════════════════════════════════════════════════════════
    # 2. STONE PATH (upgraded: per-stone bevels + moss in cracks + worn center)
    # ══════════════════════════════════════════════════════════════════
    path_col_start, path_col_end = 54, 64
    path_row_start, path_row_end = 3, 6
    path_x = path_col_start * TILE_SIZE - fcx
    path_y = path_row_start * TILE_SIZE - fcy
    path_w = (path_col_end - path_col_start + 1) * TILE_SIZE
    path_h = (path_row_end - path_row_start + 1) * TILE_SIZE
    # Per-stone rendering (each tile = one flagstone, with individual shading)
    _rng.seed(5150)
    for row in range(path_row_start, path_row_end + 1):
        for col in range(path_col_start, path_col_end + 1):
            stone_x = col * TILE_SIZE - fcx
            stone_y = row * TILE_SIZE - fcy
            # Worn center: stones near the path center (col 59) are lighter
            # (foot traffic wears stone smooth + pale).
            dist_from_center = abs(col - 59) / 5.0
            wear = 1.0 - min(1.0, dist_from_center)
            base = int(108 + wear * 20)  # lighter near center
            stone_col = (base, base - 6, base - 14)
            pygame.draw.rect(surface, stone_col,
                             (stone_x + 1, stone_y + 1, TILE_SIZE - 2, TILE_SIZE - 2))
            # Beveled edges: lighter top-left (sun from NW), darker bottom-right
            pygame.draw.line(surface, (base + 18, base + 12, base + 6),
                             (stone_x + 1, stone_y + 1), (stone_x + TILE_SIZE - 2, stone_y + 1), 1)
            pygame.draw.line(surface, (base + 14, base + 8, base + 2),
                             (stone_x + 1, stone_y + 1), (stone_x + 1, stone_y + TILE_SIZE - 2), 1)
            pygame.draw.line(surface, (base - 20, base - 22, base - 26),
                             (stone_x + 1, stone_y + TILE_SIZE - 2),
                             (stone_x + TILE_SIZE - 2, stone_y + TILE_SIZE - 2), 1)
            pygame.draw.line(surface, (base - 20, base - 22, base - 26),
                             (stone_x + TILE_SIZE - 2, stone_y + 1),
                             (stone_x + TILE_SIZE - 2, stone_y + TILE_SIZE - 2), 1)
            # Stone speckle (texture)
            for _ in range(3):
                spx = stone_x + _rng.randint(4, TILE_SIZE - 5)
                spy = stone_y + _rng.randint(4, TILE_SIZE - 5)
                pygame.draw.circle(surface, (base - 15, base - 17, base - 19), (spx, spy), 1)
    # Moss in the cracks (green specks along joint lines)
    for col in range(path_col_start, path_col_end + 2):
        lx = col * TILE_SIZE - fcx
        for _ in range(4):
            my = path_y + _rng.randint(0, path_h - 1)
            pygame.draw.circle(surface, (45, 72, 38), (lx + _rng.randint(-1, 1), my), 1)
    for row in range(path_row_start, path_row_end + 2):
        ly = row * TILE_SIZE - fcy
        for _ in range(4):
            mx = path_x + _rng.randint(0, path_w - 1)
            pygame.draw.circle(surface, (45, 72, 38), (mx, ly + _rng.randint(-1, 1)), 1)
    _rng.seed()

    # ══════════════════════════════════════════════════════════════════
    # 3. HEDGE QUADRANTS (upgraded: organic bumps + 3-layer depth + clustered leaves)
    # ══════════════════════════════════════════════════════════════════
    hedge_dark = (20, 46, 22)
    hedge_mid = (34, 68, 34)
    hedge_light = (50, 92, 46)
    hedge_highlight = (62, 108, 56)
    for rect in GARDEN_HEDGE_RECTS:
        hx = rect.x - fcx
        hy = rect.y - fcy
        hw, hh = rect.w, rect.h
        # Layer 1: dark base (shadow under the hedge)
        shadow = pygame.Surface((hw + 8, hh + 8), pygame.SRCALPHA)
        pygame.draw.rect(shadow, (0, 0, 0, 60), (4, 4, hw, hh), border_radius=8)
        surface.blit(shadow, (hx - 4, hy - 2))
        # Layer 2: main body (mid green) - organic shape via overlapping bumps
        pygame.draw.rect(surface, hedge_mid, (hx, hy, hw, hh), border_radius=6)
        # Organic bumps: 3 rows of overlapping circles to break the rect silhouette
        _rng.seed(int(rect.x) * 31 + int(rect.y))
        bump_rows = max(2, hh // 24)
        for br in range(bump_rows):
            for bc in range(max(2, hw // 28)):
                bx = hx + 14 + bc * 28 + _rng.randint(-6, 6)
                by = hy + 14 + br * 24 + _rng.randint(-4, 4)
                br_ = _rng.randint(12, 18)
                pygame.draw.circle(surface, hedge_mid, (bx, by), br_)
        # Layer 3: top highlight (lit edge - sun from NW) - smaller bumps on top
        for br in range(max(2, bump_rows)):
            for bc in range(max(2, hw // 32)):
                bx = hx + 16 + bc * 32 + _rng.randint(-5, 5)
                by = hy + 8 + br * 22 + _rng.randint(-3, 3)
                br_ = _rng.randint(8, 13)
                pygame.draw.circle(surface, hedge_light, (bx, by), br_)
                # Specular highlight on the sun-facing side
                pygame.draw.circle(surface, hedge_highlight,
                                   (bx - 2, by - 3), max(2, br_ - 5))
        # Leaf speckle (tiny dots for texture variation)
        for _ in range(int(hw * hh / 120)):
            lx = hx + _rng.randint(3, hw - 4)
            ly = hy + _rng.randint(3, hh - 4)
            shade = _rng.choice([hedge_dark, hedge_light, hedge_highlight])
            pygame.draw.circle(surface, shade, (lx, ly), 1)
        _rng.seed()
        # Dark outline
        pygame.draw.rect(surface, hedge_dark, (hx, hy, hw, hh), 2, border_radius=6)

    # ══════════════════════════════════════════════════════════════════
    # 4. CENTRAL FOUNTAIN (upgraded: two-tier + depth gradient + splash + finial)
    # ══════════════════════════════════════════════════════════════════
    fx, fy = GARDEN_CENTER
    fsx, fsy = fx - fcx, fy - fcy
    # Shadow under the fountain
    shadow = pygame.Surface((160, 100), pygame.SRCALPHA)
    render_util.soft_shadow(shadow, (0, 0, 160, 100), 70)
    surface.blit(shadow, (int(fsx - 80), int(fsy - 40)))
    # Outer basin (wide, dark stone ring)
    outer_r = 60
    pygame.draw.circle(surface, (75, 70, 64), (int(fsx), int(fsy)), outer_r)
    pygame.draw.circle(surface, (50, 46, 42), (int(fsx), int(fsy)), outer_r, 3)
    # Outer basin rim highlight (lit top edge)
    pygame.draw.arc(surface, (115, 108, 96),
                    (int(fsx - outer_r), int(fsy - outer_r), outer_r * 2, outer_r * 2),
                    math.radians(20), math.radians(160), 3)
    # Water in outer basin (depth gradient: darker center, lighter edge)
    water_outer_r = outer_r - 6
    for r in range(water_outer_r, water_outer_r - 12, -2):
        t = (water_outer_r - r) / 12.0
        col = (
            int(28 + t * 15),
            int(72 + t * 20),
            int(92 + t * 20),
        )
        pygame.draw.circle(surface, col, (int(fsx), int(fsy)), r)
    # Inner basin (raised bowl, smaller)
    inner_r = 32
    pygame.draw.circle(surface, (88, 82, 72), (int(fsx), int(fsy - 4)), inner_r)
    pygame.draw.circle(surface, (55, 50, 44), (int(fsx), int(fsy - 4)), inner_r, 2)
    # Inner basin water (brighter - water falling from the finial)
    pygame.draw.circle(surface, (50, 110, 130), (int(fsx), int(fsy - 4)), inner_r - 4)
    pygame.draw.circle(surface, (70, 140, 160), (int(fsx - 6), int(fsy - 10)), inner_r - 10)
    # Central finial (small statue/spout in the center)
    pygame.draw.rect(surface, (90, 84, 74), (int(fsx - 3), int(fsy - 14), 6, 12))
    pygame.draw.circle(surface, (110, 104, 92), (int(fsx), int(fsy - 16)), 4)
    pygame.draw.circle(surface, (70, 64, 56), (int(fsx), int(fsy - 16)), 4, 1)
    # Animated spout/splash/ripples draw live only; the bake captures the
    # static basin (per-frame counterpart: _draw_garden_fountain_fx).
    if not staticlayer.baking():
        _draw_garden_fountain_fx(surface, fcx, fcy)

    # ══════════════════════════════════════════════════════════════════
    # 5. BENCHES (redesigned: proper top-down park bench facing the fountain)
    # ══════════════════════════════════════════════════════════════════
    # Top-down bench anatomy (west bench, facing EAST toward the fountain):
    #   ┌────────────────────────┐  ← backrest (tall, on the WEST side)
    #   │  ▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓  │  ← seat slats (run N-S, the long axis)
    #   │  ▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓  │
    #   └────────────────────────┘
    #         ▓            ▓          ← iron legs (2, at the N and S ends)
    # The bench rect is 64 wide (E-W) x 24 tall (N-S). The backrest is on
    # the west edge (left), so a player sitting on it faces east toward
    # the fountain. The east bench mirrors this - backrest on the east
    # edge so the seat faces west toward the fountain.
    bench_wood = (130, 95, 55)
    bench_wood_dark = (88, 62, 35)
    bench_wood_light = (160, 122, 75)
    bench_iron = (62, 62, 66)
    bench_iron_dark = (35, 35, 38)
    for idx, rect in enumerate(GARDEN_BENCH_RECTS):
        bx = rect.x - fcx
        by = rect.y - fcy
        bw, bh = rect.w, rect.h  # 64 x 24
        # idx 0 = west bench (backrest on west/left, faces E toward fountain)
        # idx 1 = east bench (backrest on east/right, faces W toward fountain)
        backrest_on_east = (idx == 1)
        # Drop shadow (offset down-right, sun from NW)
        sh = pygame.Surface((bw + 12, bh + 12), pygame.SRCALPHA)
        render_util.soft_shadow(sh, (0, 0, bw + 12, bh + 12), 65)
        surface.blit(sh, (bx - 6 + 4, by - 4 + 6))
        # ── Backrest (the tall vertical board on the side away from the fountain) ──
        # In top-down, the backrest reads as a tall narrow strip along one long edge.
        back_w = 8  # backrest thickness (E-W dimension)
        if backrest_on_east:
            back_x = bx + bw - back_w
        else:
            back_x = bx
        # Backrest board
        pygame.draw.rect(surface, bench_wood_dark, (back_x, by, back_w, bh), border_radius=1)
        # Backrest top edge highlight (lit by sun from NW)
        pygame.draw.line(surface, bench_wood, (back_x, by), (back_x, by + bh), 2)
        # Backrest vertical slat lines (3-4 slats running N-S)
        for slat_y in range(int(by) + 3, int(by + bh) - 2, 6):
            pygame.draw.line(surface, bench_wood_dark,
                             (back_x + 1, slat_y), (back_x + back_w - 1, slat_y), 1)
        # ── Seat (the flat wooden surface the player would sit on) ──
        # The seat is the remaining width (bw - back_w). In top-down it reads
        # as a flat rectangle with N-S running slat lines (the wood grain).
        if backrest_on_east:
            seat_x = bx
            seat_w = bw - back_w
        else:
            seat_x = bx + back_w
            seat_w = bw - back_w
        # Seat base
        pygame.draw.rect(surface, bench_wood, (seat_x, by, seat_w, bh), border_radius=1)
        pygame.draw.rect(surface, bench_wood_dark, (seat_x, by, seat_w, bh), 1, border_radius=1)
        # Seat slats (horizontal lines running E-W, reading as wooden planks)
        for slat_y in range(int(by) + 3, int(by + bh) - 1, 5):
            pygame.draw.line(surface, bench_wood_dark,
                             (seat_x + 1, slat_y), (seat_x + seat_w - 1, slat_y), 1)
        # Seat front-edge highlight (the lip facing the fountain, lit by ambient)
        if backrest_on_east:
            # Front edge is on the west side of the seat
            pygame.draw.line(surface, bench_wood_light,
                             (seat_x, by + 1), (seat_x, by + bh - 1), 1)
        else:
            # Front edge is on the east side of the seat
            pygame.draw.line(surface, bench_wood_light,
                             (seat_x + seat_w - 1, by + 1), (seat_x + seat_w - 1, by + bh - 1), 1)
        # ── Armrests (small blocks at the N and S ends of the seat) ──
        # Armrests frame the seat, reinforcing "this is a bench you sit on."
        arm_w = 4
        for arm_y in (by, by + bh - arm_w):
            pygame.draw.rect(surface, bench_wood_dark, (seat_x, arm_y, seat_w, arm_w), border_radius=1)
            pygame.draw.line(surface, bench_wood, (seat_x + 1, arm_y + 1), (seat_x + seat_w - 1, arm_y + 1), 1)
        # ── Iron legs (2 visible at the N and S ends, just outside the seat) ──
        # In top-down, legs read as small dark squares at the corners.
        for leg_y in (by - 2, by + bh - 2):
            for leg_x in (seat_x + 4, seat_x + seat_w - 8):
                pygame.draw.rect(surface, bench_iron, (leg_x, leg_y, 4, 4), border_radius=1)
                pygame.draw.rect(surface, bench_iron_dark, (leg_x, leg_y, 4, 4), 1, border_radius=1)

    # ══════════════════════════════════════════════════════════════════
    # 6. LAMP POSTS (upgraded: cast-iron base + fluted pole + lantern + glow)
    # ══════════════════════════════════════════════════════════════════
    lamp_base = (45, 45, 48)
    lamp_pole = (62, 62, 66)
    lamp_pole_light = (82, 82, 86)
    lamp_housing = (70, 58, 32)
    lamp_glass = (255, 230, 150)
    lamp_glow_col = (255, 210, 120)
    for rect in GARDEN_LAMP_RECTS:
        lx = rect.x - fcx + rect.w // 2
        ly = rect.y - fcy + rect.h // 2
        # Radial light pool on the ground (multi-layer for soft falloff)
        for r, a in [(24, 25), (18, 45), (12, 70)]:
            pool = pygame.Surface((r * 2 + 4, r * 2 + 4), pygame.SRCALPHA)
            pygame.draw.circle(pool, (*lamp_glow_col, a), (r + 2, r + 2), r)
            surface.blit(pool, (lx - r - 2, ly - r - 2))
        # Cast-iron base (square plate on the ground)
        pygame.draw.rect(surface, lamp_base, (lx - 6, ly + 4, 12, 4), border_radius=1)
        pygame.draw.rect(surface, (25, 25, 28), (lx - 6, ly + 4, 12, 4), 1, border_radius=1)
        # Fluted pole (vertical line with a highlight stripe)
        pygame.draw.line(surface, lamp_pole, (lx, ly - 20), (lx, ly + 6), 3)
        pygame.draw.line(surface, lamp_pole_light, (lx - 1, ly - 20), (lx - 1, ly + 6), 1)
        # Decorative collar (small bulge at the top of the pole)
        pygame.draw.rect(surface, lamp_pole, (lx - 3, ly - 22, 6, 3))
        pygame.draw.rect(surface, (35, 35, 38), (lx - 3, ly - 22, 6, 3), 1)
        # Lantern housing (hexagonal lamp head)
        lh_y = ly - 30
        pygame.draw.polygon(surface, lamp_housing, [
            (lx - 5, lh_y + 2), (lx + 5, lh_y + 2),
            (lx + 7, lh_y + 8), (lx + 5, lh_y + 14),
            (lx - 5, lh_y + 14), (lx - 7, lh_y + 8),
        ])
        pygame.draw.polygon(surface, (40, 30, 15), [
            (lx - 5, lh_y + 2), (lx + 5, lh_y + 2),
            (lx + 7, lh_y + 8), (lx + 5, lh_y + 14),
            (lx - 5, lh_y + 14), (lx - 7, lh_y + 8),
        ], 1)
        # Glass pane (glowing center)
        pygame.draw.rect(surface, lamp_glass, (lx - 3, lh_y + 5, 6, 6))
        # Bright glow around the lantern
        glow = pygame.Surface((24, 24), pygame.SRCALPHA)
        pygame.draw.circle(glow, (*lamp_glow_col, 80), (12, 12), 10)
        pygame.draw.circle(glow, (*lamp_glow_col, 40), (12, 12), 12)
        surface.blit(glow, (lx - 12, lh_y - 4))
        # Finial (small spike on top)
        pygame.draw.line(surface, lamp_housing, (lx, lh_y), (lx, lh_y - 4), 2)

    # ══════════════════════════════════════════════════════════════════
    # 7. ORNAMENTAL TREES (upgraded: multi-layer canopy + branches + leaves)
    # ══════════════════════════════════════════════════════════════════
    tree_canopy_dark = (22, 52, 24)
    tree_canopy_mid = (34, 72, 34)
    tree_canopy_light = (48, 96, 44)
    tree_canopy_highlight = (62, 116, 54)
    tree_trunk = (72, 48, 28)
    tree_trunk_dark = (48, 30, 16)
    for rect in GARDEN_TREE_RECTS:
        tx = rect.x - fcx + rect.w // 2
        ty = rect.y - fcy + rect.h // 2
        _rng.seed(int(rect.x) * 17 + int(rect.y))
        # Shadow (offset down-right, reads as sun from NW)
        shadow = pygame.Surface((56, 34), pygame.SRCALPHA)
        render_util.soft_shadow(shadow, (0, 0, 56, 34), 75)
        surface.blit(shadow, (tx - 28 + 10, ty - 17 + 14))
        # Trunk (visible at the base, splitting into 2 branches)
        pygame.draw.rect(surface, tree_trunk, (tx - 3, ty, 6, 10))
        pygame.draw.rect(surface, tree_trunk_dark, (tx - 3, ty, 6, 10), 1)
        # Branch stubs (2 short lines angling outward)
        pygame.draw.line(surface, tree_trunk, (tx, ty + 2), (tx - 6, ty - 4), 2)
        pygame.draw.line(surface, tree_trunk, (tx, ty + 2), (tx + 6, ty - 4), 2)
        # Canopy layer 1: dark base (shadow side, bottom-right)
        pygame.draw.circle(surface, tree_canopy_dark, (tx + 4, ty - 4), 18)
        # Canopy layer 2: mid green (main body, overlapping bumps)
        for _ in range(5):
            cx = tx + _rng.randint(-12, 12)
            cy = ty - 10 + _rng.randint(-8, 4)
            pygame.draw.circle(surface, tree_canopy_mid, (cx, cy), _rng.randint(10, 14))
        # Canopy layer 3: light green (sun side, top-left)
        for _ in range(4):
            cx = tx + _rng.randint(-12, 2)
            cy = ty - 14 + _rng.randint(-8, 2)
            pygame.draw.circle(surface, tree_canopy_light, (cx, cy), _rng.randint(7, 11))
        # Canopy layer 4: highlight (specular, top-left edge)
        pygame.draw.circle(surface, tree_canopy_highlight, (tx - 6, ty - 18), 6)
        pygame.draw.circle(surface, tree_canopy_highlight, (tx - 10, ty - 12), 4)
        # Fallen leaves (small colored dots around the base)
        for _ in range(5):
            la = _rng.uniform(0, math.tau)
            lr = _rng.randint(16, 24)
            lx = tx + math.cos(la) * lr
            ly = ty + 4 + math.sin(la) * lr * 0.5
            leaf_col = _rng.choice([(180, 140, 50), (160, 90, 40), (140, 110, 50)])
            pygame.draw.circle(surface, leaf_col, (int(lx), int(ly)), 2)
        _rng.seed()

    # ══════════════════════════════════════════════════════════════════
    # 8. FLOWER BEDS (upgraded: stems + leaves + large blooms + clusters)
    # ══════════════════════════════════════════════════════════════════
    stem_col = (40, 70, 35)
    leaf_col = (50, 88, 42)
    flower_palette = [
        ((220, 60, 80), (180, 30, 50)),    # red
        ((245, 190, 60), (200, 150, 30)),  # yellow
        ((175, 95, 200), (130, 60, 160)),  # purple
        ((245, 245, 245), (200, 200, 210)),# white
        ((255, 130, 55), (210, 90, 35)),   # orange
        ((240, 100, 160), (200, 60, 120)), # pink
    ]
    _rng.seed(2024)
    for row in range(1, 3):  # north flower beds
        for col in range(51, 68):
            if _rng.random() < 0.40:  # 40% density (clusters, not uniform)
                # Cluster of 2-4 flowers
                cluster_cx = col * TILE_SIZE + _rng.randint(12, TILE_SIZE - 12)
                cluster_cy = row * TILE_SIZE + _rng.randint(12, TILE_SIZE - 12)
                for _ in range(_rng.randint(2, 4)):
                    fwx = cluster_cx + _rng.randint(-8, 8) - fcx
                    fwy = cluster_cy + _rng.randint(-8, 8) - fcy
                    petal_col, petal_dark = _rng.choice(flower_palette)
                    petal_r = _rng.randint(3, 5)
                    # Stem (thin green line)
                    pygame.draw.line(surface, stem_col, (int(fwx), int(fwy)),
                                     (int(fwx), int(fwy + petal_r + 4)), 1)
                    # Leaves (2 small ellipses on the stem)
                    pygame.draw.ellipse(surface, leaf_col,
                                        (int(fwx - 3), int(fwy + 2), 4, 2))
                    pygame.draw.ellipse(surface, leaf_col,
                                        (int(fwx + 1), int(fwy + 4), 4, 2))
                    # Petals (6-petal bloom, two-tone)
                    for petal_ang in range(0, 360, 60):
                        pax = fwx + int(math.cos(math.radians(petal_ang)) * petal_r)
                        pay = fwy + int(math.sin(math.radians(petal_ang)) * petal_r)
                        pygame.draw.circle(surface, petal_col, (pax, pay), petal_r - 1)
                    # Petal shadow (darker ring for depth)
                    for petal_ang in range(30, 360, 60):
                        pax = fwx + int(math.cos(math.radians(petal_ang)) * (petal_r - 1))
                        pay = fwy + int(math.sin(math.radians(petal_ang)) * (petal_r - 1))
                        pygame.draw.circle(surface, petal_dark, (pax, pay), max(1, petal_r - 3))
                    # Center (yellow pollen)
                    pygame.draw.circle(surface, (240, 220, 80), (int(fwx), int(fwy)), 2)
                    pygame.draw.circle(surface, (180, 150, 40), (int(fwx), int(fwy)), 1)
    for row in range(7, 9):  # south flower beds
        for col in range(51, 68):
            if _rng.random() < 0.40:
                cluster_cx = col * TILE_SIZE + _rng.randint(12, TILE_SIZE - 12)
                cluster_cy = row * TILE_SIZE + _rng.randint(12, TILE_SIZE - 12)
                for _ in range(_rng.randint(2, 4)):
                    fwx = cluster_cx + _rng.randint(-8, 8) - fcx
                    fwy = cluster_cy + _rng.randint(-8, 8) - fcy
                    petal_col, petal_dark = _rng.choice(flower_palette)
                    petal_r = _rng.randint(3, 5)
                    pygame.draw.line(surface, stem_col, (int(fwx), int(fwy)),
                                     (int(fwx), int(fwy + petal_r + 4)), 1)
                    pygame.draw.ellipse(surface, leaf_col,
                                        (int(fwx - 3), int(fwy + 2), 4, 2))
                    pygame.draw.ellipse(surface, leaf_col,
                                        (int(fwx + 1), int(fwy + 4), 4, 2))
                    for petal_ang in range(0, 360, 60):
                        pax = fwx + int(math.cos(math.radians(petal_ang)) * petal_r)
                        pay = fwy + int(math.sin(math.radians(petal_ang)) * petal_r)
                        pygame.draw.circle(surface, petal_col, (pax, pay), petal_r - 1)
                    for petal_ang in range(30, 360, 60):
                        pax = fwx + int(math.cos(math.radians(petal_ang)) * (petal_r - 1))
                        pay = fwy + int(math.sin(math.radians(petal_ang)) * (petal_r - 1))
                        pygame.draw.circle(surface, petal_dark, (pax, pay), max(1, petal_r - 3))
                    pygame.draw.circle(surface, (240, 220, 80), (int(fwx), int(fwy)), 2)
                    pygame.draw.circle(surface, (180, 150, 40), (int(fwx), int(fwy)), 1)
    _rng.seed()

    # ══════════════════════════════════════════════════════════════════
    # 9. WROUGHT-IRON FENCE (upgraded: vertical bars + corner posts + finials)
    # ══════════════════════════════════════════════════════════════════
    fence_iron = (55, 55, 60)
    fence_iron_dark = (30, 30, 34)
    fence_post = (70, 68, 64)
    fence_top = 1 * TILE_SIZE - fcy
    fence_bot = 9 * TILE_SIZE - fcy
    fence_left = 51 * TILE_SIZE - fcx
    fence_right = 68 * TILE_SIZE - fcx
    # Vertical iron bars every 6px along all 4 sides
    bar_spacing = 6
    # Top + bottom edges (horizontal runs of bars)
    def _fence_bars_h(surf, y, x_start, x_end, spacing=6):
        x = x_start
        while x < x_end:
            pygame.draw.line(surf, fence_iron, (x, y), (x, y + 3), 1)
            # Spear finial tip (small triangle on top)
            pygame.draw.polygon(surf, fence_iron_dark,
                                [(x - 1, y), (x + 1, y), (x, y - 2)])
            x += spacing
    def _fence_bars_v(surf, x, y_start, y_end, spacing=6):
        y = y_start
        while y < y_end:
            pygame.draw.line(surf, fence_iron, (x, y), (x + 3, y), 1)
            # Spear finial on the left-facing bars
            pygame.draw.polygon(surf, fence_iron_dark,
                                [(x, y - 1), (x, y + 1), (x - 2, y)])
            y += spacing
    # Top edge (bars pointing up)
    _fence_bars_h(surface, int(fence_top), int(fence_left), int(fence_right))
    # Bottom edge (bars pointing up, same style)
    _fence_bars_h(surface, int(fence_bot), int(fence_left), int(fence_right))
    # Left edge (bars pointing left)
    _fence_bars_v(surface, int(fence_left), int(fence_top), int(fence_bot))
    # Right edge (bars pointing left, same style)
    _fence_bars_v(surface, int(fence_right), int(fence_top), int(fence_bot))
    # Corner posts (thicker square at each corner)
    for cx_, cy_ in [(fence_left, fence_top), (fence_right, fence_top),
                      (fence_left, fence_bot), (fence_right, fence_bot)]:
        pygame.draw.rect(surface, fence_post, (int(cx_ - 3), int(cy_ - 3), 6, 6))
        pygame.draw.rect(surface, fence_iron_dark, (int(cx_ - 3), int(cy_ - 3), 6, 6), 1)
        # Spear finial on top of each corner post
        pygame.draw.polygon(surface, fence_post,
                            [(int(cx_ - 3), int(cy_ - 3)),
                             (int(cx_ + 3), int(cy_ - 3)),
                             (int(cx_), int(cy_ - 8))])

    # ══════════════════════════════════════════════════════════════════
    # (Garden gates removed - they led nowhere and broke immersion. The
    # garden is enclosed by the wrought-iron fence above, with the flower-
    # bed rows on the N and S sides serving as the natural entrances. The
    # hedges frame the central path; no formal "gate" structure is needed.)
    # ══════════════════════════════════════════════════════════════════


def _draw_interactables(surface, fcx, fcy):
    if STATE.mission2_stage == STAGE_INVESTIGATE:
        for clue in STATE.mission2_clues:
            _draw_world_prop(surface, clue, fcx, fcy, active=not clue["done"])
            if not clue["done"]:
                label = f"{clue['name']} [E]"
                _draw_marker(surface, clue["pos"], label, (245, 190, 65), fcx, fcy)
        if _clue_count() >= REQUIRED_INVESTIGATION_CLUES:
            _draw_marker(surface, KILL_ZONE, "REGROUP", C_VASILE, fcx, fcy)
    elif STATE.mission2_stage == STAGE_COMBAT:
        phase = getattr(STATE, "mission2_post_sniper_phase", "")
        if phase == "get_cover":
            _draw_marker(surface, _nearest_killbox_cover(), "COVER", C_VASILE, fcx, fcy, radius=34)
        elif phase == "survive":
            _draw_marker(surface, _nearest_killbox_cover(), "STAY IN COVER", C_VASILE, fcx, fcy, radius=30)
            _draw_marker(surface, SNIPER_NEST_POS, "SNIPER NEST", (255, 110, 60), fcx, fcy, radius=34)
        elif phase == "flank":
            _draw_marker(surface, _nearest_flank_marker(), "FLANK ROUTE", (255, 170, 80), fcx, fcy, radius=34)
            _draw_marker(surface, SNIPER_NEST_POS, "SNIPER LINE", (255, 110, 60), fcx, fcy, radius=30)
        elif phase == "clear":
            _draw_marker(surface, SNIPER_NEST_POS, "SNIPER LINE", (255, 110, 60), fcx, fcy, radius=30)
        elif phase == "done":
            _draw_marker(surface, SNIPER_NEST_POS, "SNIPER SUPPRESSED", (120, 220, 150), fcx, fcy, radius=28)
    elif STATE.mission2_stage == STAGE_TRUCK:
        truck = STATE.mission2_truck_manifest
        _draw_world_prop(surface, truck, fcx, fcy, active=not truck["done"])
        _draw_marker(surface, IPA_TRUCK_POS, "IPA MANIFEST [E]", (255, 190, 90), fcx, fcy)
    elif STATE.mission2_stage == STAGE_TANKER:
        inspected = getattr(STATE, "mission2_tanker_inspected", False)
        if not inspected:
            _draw_marker(surface, TANKER_POS, "TANKER VALVE [E]", (255, 140, 60), fcx, fcy, radius=34)
    elif STATE.mission2_stage == STAGE_RUN:
        _draw_marker(surface, SAFE_ZONE, "RUN HERE", C_VASILE, fcx, fcy, radius=34)
    elif STATE.mission2_stage == STAGE_EVIDENCE:
        for ev in STATE.mission2_evidence:
            _draw_world_prop(surface, ev, fcx, fcy, active=not ev["done"])
            if not ev["done"]:
                _draw_marker(surface, ev["pos"], f"{ev['name']} [E]", C_TERMINAL, fcx, fcy)
        # Always draw the upload PC during the evidence phase so the player
        # can see where they're heading - previously the PC was only drawn
        # during STAGE_UPLOAD, which meant the terminal was an invisible
        # ground marker until the player had already walked up to it and
        # the stage had transitioned. Now the PC is visible from the
        # moment the player enters the control building.
        _draw_upload_computer(surface, *_world(UPLOAD_TERMINAL_POS, fcx, fcy), fcx, fcy)
        if _evidence_count() >= 3:
            _draw_marker(surface, UPLOAD_TERMINAL_POS, "UPLOAD [E]", C_TERMINAL, fcx, fcy)
        else:
            # Show a faint "locked" marker so the player knows the PC
            # exists but isn't usable yet. Pulses slower than the active
            # marker to read as "not yet".
            _draw_marker(surface, UPLOAD_TERMINAL_POS, "UPLOAD (after 3 evidence)", C_TERMINAL, fcx, fcy)
    elif STATE.mission2_stage == STAGE_UPLOAD:
        _draw_upload_computer(surface, *_world(UPLOAD_TERMINAL_POS, fcx, fcy), fcx, fcy)
        _draw_marker(surface, UPLOAD_TERMINAL_POS, "UPLOAD [E]", C_TERMINAL, fcx, fcy)
    elif STATE.mission2_stage == STAGE_EXFIL:
        _draw_marker(surface, EXFIL_POS, "EXFIL", (80, 220, 120), fcx, fcy, radius=34)


def _draw_upload_computer(surface, sx, sy, fcx, fcy):
    """Draw the upload terminal as a small retro desktop PC (top-down).

    TINY footprint (~40x40 px) - about 60% of the original ugly version,
    so it reads as a desk prop next to the player instead of a giant
    centerpiece. Still has all the recognizable design elements (beige
    case, green CRT phosphor, keycaps, tower vents, glowing power LED,
    VGA cable), just at a smaller scale.

    Layout (centered on (sx, sy)):
       â”Œâ”€â”€â”
       â”‚TWâ”‚   â† right, slim tower, vents + LED
       â”‚â–“â–“â”‚
       â””â”€â”€â”˜
       â”Œâ”€â”€â”€â”€â”
       â”‚CRT â”‚   â† center, small beige case, pulsing green screen
       â”‚â•”â•â•â•-â”‚
       â”‚â•šâ•â•â•â”‚
       â””â”€â”€â”€â”€â”˜
        â”Œâ”€â”€â”
        â”‚KBâ”‚   â† front, trapezoidal, 2 key rows + spacebar
        â””â”€â”€â”˜

    The screen pulses green to signal "this is the upload terminal - walk up
    and press [E]". Replaces the generic green circle marker.
    """
    sx = int(sx)
    sy = int(sy)
    t_ms = _now_ms()
    pulse = 0.5 + 0.5 * math.sin(t_ms * 0.005)
    led_pulse = 0.5 + 0.5 * math.sin(t_ms * 0.008)
    # T7: 8 baked frames (4 phosphor pulse levels x cursor on/off).
    if artpack.blit_frame(surface, "spr_props_m2", "upload_pc_%d_%d" % (
            int(round(pulse * 3)), 1 if (t_ms // 500) % 2 == 0 else 0), (sx, sy)):
        return

    # ── Palette: retro beige PC + dark accents + green CRT phosphor ──
    CASE_BEIGE = (192, 182, 152)        # main plastic case
    CASE_BEIGE_DARK = (148, 138, 110)   # case shadow side
    CASE_BEIGE_LIGHT = (220, 212, 184)  # case highlight side
    CASE_OUTLINE = (78, 70, 50)         # dark plastic outline
    KEY_DARK = (78, 72, 58)             # keycap shadow
    KEY_LIGHT = (158, 150, 122)         # keycap top
    SCREEN_FRAME = (40, 38, 30)         # bezel around the CRT
    SCREEN_BG = (4, 12, 8)              # dark CRT glass
    PHOS_BRIGHT = (180, 255, 200)       # brightest phosphor
    PHOS_BASE = (90, 220, 120)          # base phosphor
    PHOS_DIM = (40, 110, 60)            # dim phosphor / scanline shadow

    # ── CRT Monitor (centerpiece) ──
    # Tiny 36x28 case - 60% of the original ugly 56x44, so it reads as a
    # desk prop next to the player instead of a giant prop. The CRT glass
    # is still large enough for phosphor + scanlines + a cursor block
    # to read at game zoom.
    mon_w, mon_h = 36, 28
    mon_x = sx - mon_w // 2
    mon_y = sy - mon_h // 2 - 5

    # Monitor back-bulge (a darker rectangle behind the case for depth).
    pygame.draw.rect(surface, CASE_BEIGE_DARK,
                     (mon_x + 2, mon_y + 3, mon_w, mon_h), border_radius=3)
    # Monitor main case.
    pygame.draw.rect(surface, CASE_BEIGE,
                     (mon_x, mon_y, mon_w, mon_h - 2), border_radius=3)
    pygame.draw.rect(surface, CASE_OUTLINE,
                     (mon_x, mon_y, mon_w, mon_h - 2), 1, border_radius=3)
    # Highlight stripe along the top edge (fake lighting).
    pygame.draw.line(surface, CASE_BEIGE_LIGHT,
                     (mon_x + 2, mon_y + 1), (mon_x + mon_w - 4, mon_y + 1), 1)

    # Screen bezel (the dark recessed area around the glass).
    bezel = pygame.Rect(mon_x + 4, mon_y + 4, mon_w - 8, mon_h - 11)
    pygame.draw.rect(surface, SCREEN_FRAME, bezel, border_radius=2)

    # CRT glass.
    glass = pygame.Rect(bezel.x + 1, bezel.y + 1, bezel.w - 2, bezel.h - 2)
    pygame.draw.rect(surface, SCREEN_BG, glass, border_radius=1)

    # Phosphor glow - pulsing green fill.
    phos_alpha = int(120 + 100 * pulse)
    phos_surf = pygame.Surface((glass.w, glass.h), pygame.SRCALPHA)
    phos_surf.fill((*PHOS_BASE, phos_alpha))
    surface.blit(phos_surf, glass.topleft)
    # Brightest center band - CRT brightness falloff.
    if glass.w >= 4 and glass.h >= 6:
        bright_band = pygame.Rect(glass.x + 1, glass.y + glass.h // 4,
                                  max(1, glass.w - 2), max(1, glass.h // 2))
        bright_surf = pygame.Surface((bright_band.w, bright_band.h), pygame.SRCALPHA)
        bright_surf.fill((*PHOS_BRIGHT, int(80 + 60 * pulse)))
        surface.blit(bright_surf, bright_band.topleft)

    # Scanlines on the glass - every 2px.
    for ly in range(glass.y, glass.y + glass.h, 2):
        pygame.draw.line(surface, PHOS_DIM,
                         (glass.x, ly), (glass.right - 1, ly), 1)

    # Blinking cursor block - 2x2, sells "live terminal".
    if (t_ms // 500) % 2 == 0 and glass.w >= 4 and glass.h >= 4:
        cur_x = glass.x + 2
        cur_y = glass.y + glass.h - 4
        pygame.draw.rect(surface, PHOS_BRIGHT, (cur_x, cur_y, 2, 2))

    # Monitor power LED (small green dot on the bezel, bottom-right).
    led_x = bezel.right - 2
    led_y = bezel.bottom + 2
    pygame.draw.circle(surface,
                       (int(80 + 100 * led_pulse), int(220 + 35 * led_pulse), int(80 + 40 * led_pulse)),
                       (led_x, led_y), 1)

    # ── Keyboard (in front of the monitor) ──
    # Trapezoidal: back edge narrower than front edge (perspective).
    # Tiny 28→34 wide, 8 tall.
    kb_w_back = 28
    kb_w_front = 34
    kb_h = 8
    kb_cx = sx
    kb_y = sy + 11
    kb_pts = [
        (kb_cx - kb_w_back // 2, kb_y),                # top-left
        (kb_cx + kb_w_back // 2, kb_y),                # top-right
        (kb_cx + kb_w_front // 2, kb_y + kb_h),        # bottom-right
        (kb_cx - kb_w_front // 2, kb_y + kb_h),        # bottom-left
    ]
    # Keyboard case.
    pygame.draw.polygon(surface, CASE_BEIGE_DARK, kb_pts)
    # Top face (slightly inset, lighter).
    inset = 1
    inset_pts = [
        (kb_cx - kb_w_back // 2 + inset, kb_y + inset),
        (kb_cx + kb_w_back // 2 - inset, kb_y + inset),
        (kb_cx + kb_w_front // 2 - inset, kb_y + kb_h - inset),
        (kb_cx - kb_w_front // 2 + inset, kb_y + kb_h - inset),
    ]
    pygame.draw.polygon(surface, CASE_BEIGE, inset_pts)
    pygame.draw.polygon(surface, CASE_OUTLINE, kb_pts, 1)

    # Key rows - 1 row of 6 keycaps + a wider spacebar row.
    # Tiny keys at this scale - just enough to read as "keyboard".
    ry = kb_y + 2
    t = (ry - kb_y) / kb_h
    row_w = int(kb_w_back + (kb_w_front - kb_w_back) * t)
    row_x = kb_cx - row_w // 2
    n_keys = 6
    key_w = 2
    gap = (row_w - n_keys * key_w) // (n_keys + 1)
    for k in range(n_keys):
        kx = row_x + gap + k * (key_w + gap)
        pygame.draw.rect(surface, KEY_DARK, (kx, ry, key_w, 2), border_radius=1)
        pygame.draw.rect(surface, KEY_LIGHT, (kx, ry, key_w, 1), border_radius=1)
    # Spacebar row - one wide key.
    sp_y = kb_y + kb_h - 3
    sp_t = (sp_y - kb_y) / kb_h
    sp_w = int(kb_w_back + (kb_w_front - kb_w_back) * sp_t) - 4
    sp_x = kb_cx - sp_w // 2
    pygame.draw.rect(surface, KEY_DARK, (sp_x, sp_y, sp_w, 2), border_radius=1)
    pygame.draw.rect(surface, KEY_LIGHT, (sp_x, sp_y, sp_w, 1), border_radius=1)

    # ── Computer tower (to the right of the monitor) ──
    # Tiny 10x28 - slim tower, slightly behind+right.
    tw_w, tw_h = 10, 28
    tw_x = sx + mon_w // 2 - 1
    tw_y = sy - tw_h // 2 - 3
    # Tower case - back shadow.
    pygame.draw.rect(surface, CASE_BEIGE_DARK,
                     (tw_x + 1, tw_y + 1, tw_w, tw_h), border_radius=1)
    # Tower case - front face.
    pygame.draw.rect(surface, CASE_BEIGE,
                     (tw_x, tw_y, tw_w, tw_h), border_radius=1)
    pygame.draw.rect(surface, CASE_OUTLINE,
                     (tw_x, tw_y, tw_w, tw_h), 1, border_radius=1)
    # Highlight stripe (left edge).
    pygame.draw.line(surface, CASE_BEIGE_LIGHT,
                     (tw_x + 1, tw_y + 1), (tw_x + 1, tw_y + tw_h - 1), 1)

    # CD/floppy drive slot (upper third).
    slot = pygame.Rect(tw_x + 2, tw_y + 3, tw_w - 4, 2)
    pygame.draw.rect(surface, (50, 48, 42), slot)

    # Vent grilles (horizontal lines, middle of the tower).
    for i in range(3):
        vy = tw_y + 8 + i * 2
        pygame.draw.line(surface, CASE_BEIGE_DARK,
                         (tw_x + 2, vy), (tw_x + tw_w - 2, vy), 1)

    # Power button + LED (lower-middle) - the LED is the most visible
    # element on the tower. Combine the button + LED into one glowing dot.
    pwr_x = tw_x + tw_w // 2
    pwr_y = tw_y + tw_h - 4
    led2_col = (int(80 + 120 * led_pulse),
                int(220 + 35 * led_pulse),
                int(80 + 40 * led_pulse))
    # Outer glow (small halo).
    glow_r = 2 + int(1 * led_pulse)
    glow_surf = pygame.Surface((glow_r * 2 + 2, glow_r * 2 + 2), pygame.SRCALPHA)
    pygame.draw.circle(glow_surf, (*led2_col, 70),
                       (glow_r + 1, glow_r + 1), glow_r)
    surface.blit(glow_surf, (pwr_x - glow_r - 1, pwr_y - glow_r - 1))
    # LED core.
    pygame.draw.circle(surface, led2_col, (pwr_x, pwr_y), 1)

    # ── Cable from monitor to tower (decorative) ──
    # A 1-px thick dark grey curve suggesting a VGA cable.
    cable_pts = [
        (mon_x + mon_w - 1, mon_y + mon_h // 2 + 2),
        (tw_x - 1, tw_y + tw_h // 2 - 1),
        (tw_x + 1, tw_y + tw_h // 2),
    ]
    pygame.draw.lines(surface, (45, 42, 35), False, cable_pts, 1)


# ─────────────────────────────────────────────
# Evidence completion cinematic (Option E)
# ─────────────────────────────────────────────

# Cinematic shot durations (in frames @ 60fps). Total = 9.0s = 540 frames.
# Slowed down from the original 5s version - no new content, just more time
# per shot so the beat lands with weight instead of rushing past.
_EVIDENCE_CINEMATIC_SHOTS = [
    {"name": "comms_cut",    "duration": 60},   # 1.0s - world fades to near-black, comms static
    {"name": "evidence_wall", "duration": 210}, # 3.5s - red string board draws slowly, names appear one at a time
    {"name": "vasile_line",  "duration": 180},  # 3.0s - Vasile's line types out slow, through static
    {"name": "upload_punch", "duration": 90},   # 1.5s - camera holds on upload terminal, objective appears
]

# Vasile's line - cold rage, short + brutal. Delivered as a degraded radio
# transmission (comms were cut by the tanker blast). The _muffle_radio_text()
# helper will further distort this so it reads as fighting through static.
_EVIDENCE_CINEMATIC_VASILE_LINE = "Confirmed. Upload. Burn them."


def _update_evidence_cinematic():
    """Advance the evidence completion cinematic by one frame.

    Called from game_update() when STATE.mission2_evidence_cinematic_active
    is True. Handles shot transitions, flash decay, and the final handoff
    to the upload objective.

    The cinematic is a 9-second, 4-shot cutscene:
      Shot 0 (comms_cut):     1.0s - world fades to near-black, comms static
      Shot 1 (evidence_wall): 3.5s - red string board draws, names appear
      Shot 2 (vasile_line):   3.0s - Vasile's line types out through static
      Shot 3 (upload_punch):  1.5s - camera holds on upload terminal, objective

    During the cinematic, enemies are frozen (game_update skips their AI).
    A 0.5s post-cinematic grace period (mission2_evidence_cinematic_grace)
    keeps enemies frozen after the cinematic ends so the player can orient.
    """
    if not STATE.mission2_evidence_cinematic_active:
        # Post-cinematic grace period - enemies stay frozen for 0.5s.
        if getattr(STATE, "mission2_evidence_cinematic_grace", 0) > 0:
            STATE.mission2_evidence_cinematic_grace -= 1
        return

    STATE.mission2_evidence_cinematic_timer += 1
    shot_idx = STATE.mission2_evidence_cinematic_shot
    shot = _EVIDENCE_CINEMATIC_SHOTS[shot_idx]

    # Advance to the next shot when the current one's duration elapses.
    if STATE.mission2_evidence_cinematic_timer >= shot["duration"]:
        STATE.mission2_evidence_cinematic_timer = 0
        shot_idx += 1
        STATE.mission2_evidence_cinematic_shot = shot_idx

        if shot_idx == 1:
            # Entering evidence_wall shot - the world is already dark from
            # shot 0. Red string board begins drawing.
            pass
        elif shot_idx == 2:
            # Entering vasile_line shot - play radio static, then the line.
            audio.play("radio_static", volume=0.5)
            audio.schedule(15, "radio_chatter", volume=0.35)
        elif shot_idx == 3:
            # Entering upload_punch shot - camera snaps to upload terminal.
            STATE.mission2_camera_focus = UPLOAD_TERMINAL_POS
            STATE.mission2_camera_focus_timer = 90
            effects.shake(8)
        elif shot_idx >= len(_EVIDENCE_CINEMATIC_SHOTS):
            # Cinematic complete - hand off to upload objective + start grace.
            # The terminal focus + timer set by upload_punch are deliberately
            # LEFT in place: game_update keeps running _update_camera() through
            # the grace period, so the camera holds on the terminal while the
            # objective lands, then the normal focus-timer decay releases it.
            # (Clearing the focus here used to delete the whole beat - the
            # camera never held on the terminal and the punch shake fired
            # ~1.5s late instead.)
            STATE.mission2_evidence_cinematic_active = False
            STATE.mission2_evidence_cinematic_grace = 30  # 0.5s enemy freeze
            _set_objective("UPLOAD EVIDENCE - BURN THEM ALL")
            return

    # Decay the white flash over shot 0 (60 frames).
    if STATE.mission2_evidence_cinematic_flash > 0:
        STATE.mission2_evidence_cinematic_flash = max(
            0, STATE.mission2_evidence_cinematic_flash - 8
        )


def _draw_evidence_cinematic(surface):
    """Draw the evidence completion cinematic - a proper cutscene, not an overlay.

    Called from game_draw() when STATE.mission2_evidence_cinematic_active
    is True. The cinematic darkens the world to near-black (the burning tanker
    crater is the only light source) and draws the cutscene on top of that
    darkened world. Each shot has unique visuals:

      Shot 0 (comms_cut): World fades to near-black over 1s. Comms static
        sound. The 3 evidence positions glow faintly red through the dark.
      Shot 1 (evidence_wall): Red lines draw themselves connecting the 3
        evidence positions. Names appear one at a time: RETARDOVICI →
        BALACEANU → MAG (FRAMED). The conspiracy is mapped.
      Shot 2 (vasile_line): The red string board holds. Vasile's line types
        out at the bottom in radio format, degraded by _muffle_radio_text().
        CRT static interference throughout.
      Shot 3 (upload_punch): Red string board fades. Camera holds on upload
        terminal (set via camera_focus). "UPLOAD EVIDENCE - BURN THEM ALL"
        objective text fades in.
    """
    if not STATE.mission2_evidence_cinematic_active:
        return

    shot_idx = STATE.mission2_evidence_cinematic_shot
    shot_timer = STATE.mission2_evidence_cinematic_timer

    fcx = STATE.camera_x
    fcy = STATE.camera_y
    # Render camera: follow + live kick/shake sample so the upload_punch
    # shake(8) lands visibly on its beat instead of queuing up and firing
    # after the cinematic.
    if not getattr(STATE, "reduced_motion", False):
        fcx += STATE.cam_kick_x
        fcy += STATE.cam_kick_y
        _csh = int(STATE.screen_shake)
        if _csh > 0:
            fcx += _rng_legacy.randint(-_csh, _csh)
            fcy += _rng_legacy.randint(-_csh, _csh)

    # ── Darken the world to near-black ──
    # The cinematic is a cutscene, not an overlay. The world fades to ~85%
    # darkness over shot 0, then stays dark for the rest of the cinematic.
    # The burning tanker crater (still on the map) provides faint ambient
    # light through the darkness - the only visible feature of the world.
    if shot_idx == 0:
        # Fade from 0% to 85% darkness over the 60-frame shot.
        dark_alpha = int(217 * (shot_timer / 60.0))
    else:
        dark_alpha = 217  # 85% darkness for the rest of the cinematic

    dim = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
    dim.fill((0, 0, 0, dark_alpha))
    surface.blit(dim, (0, 0))

    # ── Shot 0: White flash (decays) + faint evidence glows ──
    if STATE.mission2_evidence_cinematic_flash > 0:
        flash = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        _fa = STATE.mission2_evidence_cinematic_flash
        if getattr(STATE, "flash_reduction", False):
            _fa = min(_fa, 96)   # RPE6 P9: flash reduction caps the white-out (~38%)
        flash.fill((255, 255, 255, _fa))
        surface.blit(flash, (0, 0))

    # Faint red glows at the 3 evidence positions - visible through the dark.
    if shot_idx <= 1:
        glow_pulse = 0.5 + 0.5 * math.sin(shot_timer * 0.15)
        for ev in STATE.mission2_evidence:
            sx = int(ev["pos"][0] - fcx)
            sy = int(ev["pos"][1] - fcy)
            # Soft red glow.
            glow_r = int(20 + glow_pulse * 8)
            glow = pygame.Surface((glow_r * 2 + 4, glow_r * 2 + 4), pygame.SRCALPHA)
            for i in range(4):
                r = glow_r - i * 4
                if r > 0:
                    a = 30 + i * 15
                    pygame.draw.circle(glow, (180, 30, 30, a),
                                       (glow_r + 2, glow_r + 2), r)
            surface.blit(glow, (sx - glow_r - 2, sy - glow_r - 2))

    # ── Shot 1: Red string board - lines draw slowly, names appear one at a time ──
    # The red string board is a screen-space diagram (like a detective's case
    # board), NOT tied to world positions. The 3 evidence items are arranged
    # in a triangle on screen, with red lines connecting them. This works
    # regardless of where the camera is - the board is a visualization, not
    # a map view.
    if shot_idx == 1:
        # Fixed screen positions for the 3 evidence nodes (triangle layout).
        # Names in narrative order: decree (1st), balaceanu (2nd), mag_packet (3rd).
        positions = [
            (WIDTH // 2 - 200, HEIGHT // 2 + 40),   # decree - bottom left
            (WIDTH // 2 + 200, HEIGHT // 2 + 40),   # balaceanu - bottom right
            (WIDTH // 2, HEIGHT // 2 - 100),         # mag_packet - top center
        ]
        names = ["RETARDOVICI", "BALACEANU", "MAG"]
        tags = ["DECREE", "AUTH CHAIN", "FRAMED"]

        # The 210-frame shot is divided into 3 reveal phases (70 frames each):
        #   Phase 0 (0-70):   Line 1 draws (decree → balaceanu), RETARDOVICI appears
        #   Phase 1 (70-140): Line 2 draws (balaceanu → mag_packet), BALACEANU appears
        #   Phase 2 (140-210): MAG appears, "FRAMED" tag, board pulses once
        phase = shot_timer // 70

        # Line 1: decree → balaceanu (bottom edge of triangle)
        if phase >= 0:
            line_progress = min(1.0, (shot_timer % 70) / 50.0) if phase == 0 else 1.0
            x1, y1 = positions[0]
            x2, y2 = positions[1]
            ex = x1 + (x2 - x1) * line_progress
            ey = y1 + (y2 - y1) * line_progress
            pygame.draw.line(surface, (220, 50, 50),
                             (int(x1), int(y1)), (int(ex), int(ey)), 2)
            # Node 0 (decree / RETARDOVICI).
            if line_progress > 0.3 or phase > 0:
                name_surf = font_terminal.render(names[0], True, (255, 80, 80))
                surface.blit(name_surf, (int(x1) - name_surf.get_width() // 2, int(y1) + 14))
                tag_surf = font_terminal_small.render(tags[0], True, (180, 100, 100))
                surface.blit(tag_surf, (int(x1) - tag_surf.get_width() // 2, int(y1) + 32))
        # Line 2: balaceanu → mag_packet (right edge of triangle)
        if phase >= 1:
            line_progress = min(1.0, (shot_timer % 70) / 50.0) if phase == 1 else 1.0
            x1, y1 = positions[1]
            x2, y2 = positions[2]
            ex = x1 + (x2 - x1) * line_progress
            ey = y1 + (y2 - y1) * line_progress
            pygame.draw.line(surface, (220, 50, 50),
                             (int(x1), int(y1)), (int(ex), int(ey)), 2)
            # Node 1 (balaceanu / BALACEANU).
            if line_progress > 0.3 or phase > 1:
                name_surf = font_terminal.render(names[1], True, (255, 80, 80))
                surface.blit(name_surf, (int(x1) - name_surf.get_width() // 2, int(y1) + 14))
                tag_surf = font_terminal_small.render(tags[1], True, (180, 100, 100))
                surface.blit(tag_surf, (int(x1) - tag_surf.get_width() // 2, int(y1) + 32))
        # Line 3: mag_packet → decree (left edge of triangle, completes the loop)
        # Node 2 (mag_packet / MAG + FRAMED tag)
        if phase >= 2:
            # Complete the triangle.
            x1, y1 = positions[2]
            x2, y2 = positions[0]
            pygame.draw.line(surface, (220, 50, 50),
                             (int(x1), int(y1)), (int(x2), int(y2)), 2)
            # Node 2.
            x2, y2 = positions[2]
            name_surf = font_terminal.render(names[2], True, (255, 80, 80))
            surface.blit(name_surf, (int(x2) - name_surf.get_width() // 2, int(y2) - 32))
            tag_surf = font_terminal_small.render(tags[2], True, (255, 150, 150))
            surface.blit(tag_surf, (int(x2) - tag_surf.get_width() // 2, int(y2) - 50))

        # Pulsing red dots at all revealed nodes.
        pulse = 0.5 + 0.5 * math.sin(shot_timer * 0.2)
        for i, (sx, sy) in enumerate(positions):
            if i <= phase:
                pygame.draw.circle(surface, (255, 60, 60), (int(sx), int(sy)), int(6 + pulse * 3))
                pygame.draw.circle(surface, (255, 200, 200), (int(sx), int(sy)), int(6 + pulse * 3), 1)

    # ── Shot 2: Vasile's line - typewriter through static ──
    # The red string board from shot 1 stays visible (we redraw it faintly).
    elif shot_idx == 2:
        # Redraw the red string board, dimmed (screen-space positions).
        positions = [
            (WIDTH // 2 - 200, HEIGHT // 2 + 40),
            (WIDTH // 2 + 200, HEIGHT // 2 + 40),
            (WIDTH // 2, HEIGHT // 2 - 100),
        ]
        names = ["RETARDOVICI", "BALACEANU", "MAG"]
        # Triangle lines (all visible, dimmed).
        for i in range(3):
            x1, y1 = positions[i]
            x2, y2 = positions[(i + 1) % 3]
            pygame.draw.line(surface, (100, 25, 25),
                             (int(x1), int(y1)), (int(x2), int(y2)), 1)
        for i, (sx, sy) in enumerate(positions):
            pygame.draw.circle(surface, (120, 35, 35), (int(sx), int(sy)), 5)
            name_surf = font_terminal.render(names[i], True, (140, 50, 50))
            if i < 2:
                surface.blit(name_surf, (int(sx) - name_surf.get_width() // 2, int(sy) + 14))
            else:
                surface.blit(name_surf, (int(sx) - name_surf.get_width() // 2, int(sy) - 32))

        # Letterbox bars.
        bar_h = 70
        top_bar = pygame.Surface((WIDTH, bar_h), pygame.SRCALPHA)
        top_bar.fill((0, 0, 0, 230))
        surface.blit(top_bar, (0, 0))
        bot_bar = pygame.Surface((WIDTH, bar_h), pygame.SRCALPHA)
        bot_bar.fill((0, 0, 0, 230))
        surface.blit(bot_bar, (0, HEIGHT - bar_h))

        # Radio static interference - scanline jitter.
        for i in range(8):
            y = _rng_legacy.randint(0, HEIGHT)
            jitter = pygame.Surface((WIDTH, 2), pygame.SRCALPHA)
            jitter.fill((255, 245, 220, _rng_legacy.randint(8, 25)))
            surface.blit(jitter, (_rng_legacy.randint(-3, 3), y))

        # Vasile's line - types out character-by-character over the 180-frame shot.
        # The line is degraded via _muffle_radio_text() to read as comms-cut.
        full_line = _muffle_radio_text(_EVIDENCE_CINEMATIC_VASILE_LINE)
        # Type out over the first 120 frames (2s), then hold for 60 frames (1s).
        type_progress = min(1.0, shot_timer / 120.0)
        visible_chars = int(len(full_line) * type_progress)
        visible_text = full_line[:visible_chars]

        # "VASILE" label (degraded).
        label = font_terminal_small.render(_T("m2.vasile_degraded"), True, (200, 130, 80))
        surface.blit(label, (WIDTH // 2 - label.get_width() // 2, HEIGHT // 2 - 50))

        # The dialogue line.
        if visible_text:
            txt = font_dialogue.render(visible_text, True, (255, 210, 170))
            surface.blit(txt, (WIDTH // 2 - txt.get_width() // 2, HEIGHT // 2 - 20))
            # Blinking cursor while typing.
            if type_progress < 1.0 and (shot_timer % 12) < 6:
                cursor_x = WIDTH // 2 + txt.get_width() // 2 + 4
                pygame.draw.line(surface, (255, 210, 170),
                                 (cursor_x, HEIGHT // 2 - 16),
                                 (cursor_x, HEIGHT // 2 + 4), 2)

    # ── Shot 3: Upload terminal punch-in ──
    elif shot_idx == 3:
        # Camera is focused on the upload terminal (set in update).
        # Draw a pulsing red ring around it.
        ux, uy = _world(UPLOAD_TERMINAL_POS, fcx, fcy)
        pulse = 0.5 + 0.5 * math.sin(shot_timer * 0.3)
        ring_radius = int(40 + pulse * 20)
        ring = pygame.Surface((ring_radius * 2 + 8, ring_radius * 2 + 8), pygame.SRCALPHA)
        pygame.draw.circle(ring, (255, 60, 60, int(120 * (1 - pulse))),
                           (ring_radius + 4, ring_radius + 4), ring_radius, 3)
        surface.blit(ring, (int(ux - ring_radius - 4), int(uy - ring_radius - 4)))

        # "UPLOAD EVIDENCE - BURN THEM ALL" text, fading in.
        burn_text = font_speaker.render(_T("m2.upload_evidence_burn_them_all"), True, (255, 80, 80))
        burn_text.set_alpha(min(255, shot_timer * 8))
        surface.blit(burn_text, (WIDTH // 2 - burn_text.get_width() // 2, 50))


def _draw_card(surface):
    card = getattr(STATE, "mission2_card", None)
    if not card:
        return
    age = card.get("age", 0)
    open_t = min(1.0, age / 18.0)
    ease = 1 - (1 - open_t) ** 3
    col = card["color"]

    # ── Evidence cards: dedicated document renderers ──
    # The 3 evidence kinds (decree, terminal, packet) get their own full-screen
    # renderers that draw the actual document/terminal - not the generic card
    # layout with overlays. Each looks like what it is: a paper decree, a CRT
    # monitor, a press release.
    kind = card.get("kind", "document")
    if kind == "decree":
        _draw_decree_document(surface, card, age, ease)
        return
    elif kind == "terminal":
        _draw_terminal_document(surface, card, age, ease)
        return
    elif kind == "packet":
        _draw_packet_document(surface, card, age, ease)
        return

    # --- Background dimming overlay ---
    overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
    overlay.fill((0, 0, 0, int(180 * ease)))
    surface.blit(overlay, (0, 0))

    # Bigger panel - was 720x360, now 760x460 so all 4 fields fit
    # comfortably without the Conclusion getting clipped.
    w, h = 760, 460
    x = WIDTH // 2 - w // 2
    y = int(HEIGHT // 2 - h // 2 + (1 - ease) * 80)

    # --- Drop shadow ---
    shadow = pygame.Surface((w + 28, h + 28), pygame.SRCALPHA)
    pygame.draw.rect(shadow, (0, 0, 0, int(120 * ease)), shadow.get_rect(), border_radius=8)
    surface.blit(shadow, (x - 4, y + 8))

    # --- Main panel body ---
    pygame.draw.rect(surface, (8, 12, 16), (x, y, w, h), border_radius=6)
    # Inner subtle gradient (lighter at top)
    grad = pygame.Surface((w, h), pygame.SRCALPHA)
    for i in range(h):
        a = max(0, 25 - i // 8)
        pygame.draw.line(grad, (col[0] // 4, col[1] // 4, col[2] // 4, a), (0, i), (w, i))
    surface.blit(grad, (x, y))
    # Outer accent border
    pygame.draw.rect(surface, col, (x, y, w, h), 2, border_radius=6)
    # Inner thin border (1px darker, 4px inset)
    pygame.draw.rect(surface, (col[0] // 2, col[1] // 2, col[2] // 2),
                     (x + 4, y + 4, w - 8, h - 8), 1, border_radius=4)

    # --- Corner registration marks ---
    mark_len = 12
    mark_col = (col[0] // 2, col[1] // 2, col[2] // 2)
    for cx, cy, dx, dy in [
        (x + 8, y + 8, 1, 1),
        (x + w - 8, y + 8, -1, 1),
        (x + 8, y + h - 8, 1, -1),
        (x + w - 8, y + h - 8, -1, -1),
    ]:
        pygame.draw.line(surface, mark_col, (cx, cy), (cx + mark_len * dx, cy), 1)
        pygame.draw.line(surface, mark_col, (cx, cy), (cx, cy + mark_len * dy), 1)

    # --- Header bar ---
    hdr_h = 54
    pygame.draw.rect(surface, (4, 8, 11), (x, y, w, hdr_h), border_radius=6)
    pygame.draw.rect(surface, col, (x, y + hdr_h - 3, w, 3))
    # Classification stripe
    stripe_x = x + w - 110
    stripe_surf = pygame.Surface((100, hdr_h - 6), pygame.SRCALPHA)
    for i in range(-hdr_h, 110, 8):
        pygame.draw.line(stripe_surf, (140, 35, 30, 80), (i, 0), (i + hdr_h, hdr_h), 2)
    surface.blit(stripe_surf, (stripe_x, y + 3))
    cls_text = font_terminal_small.render(_T("m2.classified"), True, (200, 60, 50))
    surface.blit(cls_text, (x + w - cls_text.get_width() - 14, y + 6))
    doc_id = font_terminal_small.render(_T("m2.doc_ipa_dm_12_007"), True, (100, 110, 120))
    surface.blit(doc_id, (x + w - doc_id.get_width() - 14, y + hdr_h - 20))
    # Title
    title = font_speaker.render(card["title"], True, col)
    surface.blit(title, (x + 24, y + 14))

    # --- Left: preview area ---
    # For the tanker inspection card, draw a technical SCHEMATIC of the
    # valve + detonator circuit instead of a paper document. Other cards
    # fall back to the prop icon.
    preview_w, preview_h = 200, 220
    preview_x = x + 30
    preview_y = y + hdr_h + 24
    preview = pygame.Surface((preview_w, preview_h), pygame.SRCALPHA)
    # Schematic background - dark blueprint green instead of paper cream
    pygame.draw.rect(preview, (0, 0, 0, 120), (0, 0, preview_w, preview_h), border_radius=4)
    pygame.draw.rect(preview, (12, 28, 22), (2, 2, preview_w - 4, preview_h - 4), border_radius=3)
    # Blueprint grid (faint)
    for gx in range(0, preview_w, 12):
        pygame.draw.line(preview, (20, 45, 35), (gx, 2), (gx, preview_h - 2), 1)
    for gy in range(0, preview_h, 12):
        pygame.draw.line(preview, (20, 45, 35), (2, gy), (preview_w - 2, gy), 1)

    is_tanker_schematic = card.get("kind") == "document" and "TANKER" in card.get("title", "").upper()
    if is_tanker_schematic:
        _draw_tanker_schematic(preview, preview_w, preview_h, age, col)
    else:
        # Fall back to the prop icon for non-tanker cards
        _draw_prop_icon(preview, card.get("kind", "document"),
                        preview_w // 2, preview_h // 2,
                        scale=PROP_CARD_SCALE, active=True, color=col)
    # Scan line
    scan_y = int((age * 2) % preview_h)
    pygame.draw.line(preview, (*col, 100), (4, scan_y), (preview_w - 4, scan_y), 2)
    # Preview border
    pygame.draw.rect(preview, (*col, 140), (0, 0, preview_w, preview_h), 1, border_radius=4)
    surface.blit(preview, (preview_x, preview_y))
    # Caption
    cap_text = "SCHEMATIC - VALVE CIRCUIT" if is_tanker_schematic else "DOCUMENT SCAN"
    cap = font_terminal_small.render(cap_text, True, (120, 130, 140))
    surface.blit(cap, (preview_x + preview_w // 2 - cap.get_width() // 2,
                       preview_y + preview_h + 6))

    # --- Right: text fields ---
    text_x = preview_x + preview_w + 30
    text_w = x + w - 30 - text_x
    yy = y + hdr_h + 28

    for line in card["lines"]:
        if ":" in line:
            label_str, _, value_str = line.partition(":")
            label_str = label_str.strip().upper()
            value_str = value_str.strip()

            # Field label (muted accent, small)
            lbl = font_terminal_small.render(label_str, True,
                                             (col[0] // 2 + 60, col[1] // 2 + 60, col[2] // 2 + 50))
            surface.blit(lbl, (text_x, yy))
            yy += 18

            # Field value (white, larger, wrapped)
            words = value_str.split()
            cur = ""
            for word in words:
                test = (cur + " " + word).strip()
                if font_dialogue.size(test)[0] > text_w and cur:
                    val_surf = font_dialogue.render(cur, True, C_WHITE)
                    surface.blit(val_surf, (text_x + 12, yy))
                    yy += 26
                    cur = word
                else:
                    cur = test
            if cur:
                val_surf = font_dialogue.render(cur, True, C_WHITE)
                surface.blit(val_surf, (text_x + 12, yy))
                yy += 26

            # Separator line under the field
            pygame.draw.line(surface, (col[0] // 3, col[1] // 3, col[2] // 3),
                             (text_x, yy + 4), (text_x + text_w, yy + 4), 1)
            yy += 16  # breathing room between fields
        else:
            words = line.split()
            cur = ""
            for word in words:
                test = (cur + " " + word).strip()
                if font_dialogue.size(test)[0] > text_w and cur:
                    surf = font_dialogue.render(cur, True, C_WHITE)
                    surface.blit(surf, (text_x, yy))
                    yy += 26
                    cur = word
                else:
                    cur = test
            if cur:
                surf = font_dialogue.render(cur, True, C_WHITE)
                surface.blit(surf, (text_x, yy))
                yy += 26
            yy += 8

    # --- Footer ---
    foot_h = 36
    foot_y = y + h - foot_h
    pygame.draw.rect(surface, (4, 8, 11), (x, foot_y, w, foot_h), border_radius=6)
    pygame.draw.line(surface, (col[0] // 3, col[1] // 3, col[2] // 3),
                     (x, foot_y), (x + w, foot_y), 1)
    # Left: page + clearance
    page = font_terminal_small.render(_T("m2.page_1_of_1_clearance_krap_eyes"),
                                      True, (100, 110, 120))
    surface.blit(page, (x + 24, foot_y + 12))
    # Right: close hint (blinking)
    hint = font_terminal.render(_T("m2.press_e_to_close"), True, col)
    if age >= 18 or (_now_ms() // 400) % 2 == 0:
        surface.blit(hint, (x + w - hint.get_width() - 24, foot_y + 10))

    # ── Evidence kinds are handled by dedicated renderers at the top of
    # _draw_card (see _draw_decree_document / _draw_terminal_document /
    # _draw_packet_document). This code is unreachable for evidence cards.


def _draw_decree_document(surface, card, age, ease):
    """Render the evidence card as an actual presidential decree paper.

    Not a "card with a decree overlay" - an actual paper document:
      - Cream paper background with subtle texture
      - Ornate presidential crest at the top (drawn with shapes)
      - "PRESIDENTIAL DECREE" header in serif-style caps
      - "BY PRESIDENTIAL AUTHORITY" sub-header
      - Decree number + body text written on the paper
      - Signature line + "Sebastian Retardovici" signature
      - Red wax seal next to the signature
      - Aged/yellowed paper edges
    """
    import random as _rng
    rng = _rng.Random(42)

    # ── Background dim ──
    overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
    overlay.fill((0, 0, 0, int(200 * ease)))
    surface.blit(overlay, (0, 0))

    # ── Paper dimensions + position ──
    # Portrait orientation - taller than wide, like a real decree.
    pw, ph = 520, 620
    px = WIDTH // 2 - pw // 2
    py = int(HEIGHT // 2 - ph // 2 + (1 - ease) * 80)

    # ── Drop shadow ──
    shadow = pygame.Surface((pw + 24, ph + 24), pygame.SRCALPHA)
    pygame.draw.rect(shadow, (0, 0, 0, int(140 * ease)), shadow.get_rect(), border_radius=4)
    surface.blit(shadow, (px - 6, py + 10))

    # ── Paper body - cream/aged yellow ──
    paper_col = (232, 220, 188)
    pygame.draw.rect(surface, paper_col, (px, py, pw, ph), border_radius=2)

    # ── Aged paper texture - random darker patches (stable via seed) ──
    texture = pygame.Surface((pw, ph), pygame.SRCALPHA)
    for _ in range(60):
        tx = rng.randint(0, pw)
        ty = rng.randint(0, ph)
        tw = rng.randint(15, 60)
        th = rng.randint(8, 18)
        ta = rng.randint(8, 20)
        pygame.draw.rect(texture, (140, 120, 80, ta), (tx, ty, tw, th))
    # Slight darker edges (aged).
    for i in range(8):
        a = 30 - i * 3
        if a > 0:
            pygame.draw.rect(texture, (100, 85, 50, a),
                             (i, i, pw - i * 2, ph - i * 2), 1)
    surface.blit(texture, (px, py))

    # ── Ornate double border (gold + dark red) ──
    gold = (170, 130, 50)
    dark_red = (110, 25, 20)
    pygame.draw.rect(surface, gold, (px + 12, py + 12, pw - 24, ph - 24), 2)
    pygame.draw.rect(surface, dark_red, (px + 18, py + 18, pw - 36, ph - 36), 1)

    # ── Presidential crest at top center ──
    # A simple drawn crest: shield shape + star + laurel lines.
    crest_cx = px + pw // 2
    crest_cy = py + 55
    # Shield outline.
    shield_pts = [
        (crest_cx - 22, crest_cy - 18),
        (crest_cx + 22, crest_cy - 18),
        (crest_cx + 22, crest_cy + 8),
        (crest_cx, crest_cy + 24),
        (crest_cx - 22, crest_cy + 8),
    ]
    pygame.draw.polygon(surface, (180, 150, 80), shield_pts)
    pygame.draw.polygon(surface, dark_red, shield_pts, 2)
    # Star in the shield.
    star_pts = []
    for i in range(10):
        angle = i * math.pi / 5 - math.pi / 2
        r = 9 if i % 2 == 0 else 4
        star_pts.append((crest_cx + math.cos(angle) * r, crest_cy + math.sin(angle) * r - 2))
    pygame.draw.polygon(surface, dark_red, star_pts)
    # Laurel lines flanking the shield.
    for side in (-1, 1):
        for j in range(3):
            lx = crest_cx + side * (30 + j * 8)
            ly = crest_cy + 2 + j * 3
            pygame.draw.line(surface, gold, (lx, ly - 4), (lx, ly + 4), 1)

    # ── "PRESIDENTIAL DECREE" header ──
    header = font_speaker.render(_T("m2.presidential_decree"), True, dark_red)
    surface.blit(header, (px + pw // 2 - header.get_width() // 2, py + 95))

    # ── "BY PRESIDENTIAL AUTHORITY" sub-header ──
    sub = font_terminal_small.render(_T("m2.by_presidential_authority"), True, (140, 90, 50))
    surface.blit(sub, (px + pw // 2 - sub.get_width() // 2, py + 125))

    # ── Horizontal rule under the header ──
    pygame.draw.line(surface, dark_red,
                     (px + 60, py + 148), (px + pw - 60, py + 148), 1)

    # ── Decree body text ──
    # Render each line directly on the paper, like typed text.
    text_y = py + 168
    text_x = px + 50
    text_w = pw - 100
    for line in card["lines"]:
        if not line:
            text_y += 14  # blank line gap
            continue
        # "DECREE NO. 47" - render in bold red.
        if "DECREE NO." in line:
            txt_surf = font_dialogue.render(line, True, dark_red)
        # Signature line - render in a script-like style (italicized via offset).
        elif "Sebastian Retardovici" in line:
            txt_surf = font_dialogue.render(line, True, (60, 50, 40))
            # Slight italic skew by blitting with x-offset per row.
            surface.blit(txt_surf, (text_x + 20, text_y))
            text_y += 24
            continue
        elif "President of Acaristan" in line:
            txt_surf = font_terminal_small.render(line, True, (100, 85, 60))
            surface.blit(txt_surf, (text_x + 20, text_y))
            text_y += 20
            continue
        else:
            txt_surf = font_dialogue.render(line, True, (50, 40, 30))
        # Word-wrap long lines.
        words = line.split()
        cur = ""
        for word in words:
            test = (cur + " " + word).strip()
            if font_dialogue.size(test)[0] > text_w and cur:
                wrapped = font_dialogue.render(cur, True,
                                                dark_red if "DECREE NO." in cur else (50, 40, 30))
                surface.blit(wrapped, (text_x, text_y))
                text_y += 22
                cur = word
            else:
                cur = test
        if cur:
            wrapped = font_dialogue.render(cur, True,
                                            dark_red if "DECREE NO." in cur else (50, 40, 30))
            surface.blit(wrapped, (text_x, text_y))
            text_y += 22

    # ── Signature line ──
    sig_y = py + ph - 100
    pygame.draw.line(surface, (80, 65, 45),
                     (px + 60, sig_y), (px + 280, sig_y), 1)

    # ── Red wax seal next to the signature ──
    seal_cx = px + pw - 75
    seal_cy = sig_y + 5
    seal_r = 32
    # Outer wax blob.
    for i in range(3):
        r = seal_r + i
        alpha = 50 - i * 15
        blob = pygame.Surface((r * 2 + 4, r * 2 + 4), pygame.SRCALPHA)
        pygame.draw.circle(blob, (130, 20, 18, alpha), (r + 2, r + 2), r)
        surface.blit(blob, (seal_cx - r - 2, seal_cy - r - 2))
    # Seal body.
    pygame.draw.circle(surface, (150, 25, 22), (seal_cx, seal_cy), seal_r)
    pygame.draw.circle(surface, (85, 15, 12), (seal_cx, seal_cy), seal_r, 2)
    pygame.draw.circle(surface, (190, 55, 45), (seal_cx, seal_cy), seal_r - 7, 1)
    # "R" monogram.
    monogram = font_speaker.render(_T("m2.r"), True, (230, 200, 180))
    surface.blit(monogram, (seal_cx - monogram.get_width() // 2,
                            seal_cy - monogram.get_height() // 2))

    # ── Close hint at the bottom ──
    hint = font_terminal.render(_T("m2.e_close"), True, dark_red)
    if age >= 18 or (_now_ms() // 400) % 2 == 0:
        surface.blit(hint, (WIDTH // 2 - hint.get_width() // 2, py + ph + 20))


def _draw_terminal_document(surface, card, age, ease):
    """Render the evidence card as an actual CRT monitor terminal.

    Not a "card with terminal overlay" - an actual CRT monitor:
      - Dark monitor body/frame with bezel
      - Green phosphor screen (dark green/black background)
      - Screen curvature (slight bulge via gradient)
      - Boot-up sequence: "ACCESSING..." types out, then "DECRYPTED"
      - Command-prompt text typed character-by-character on the screen
      - Scanlines + phosphor glow + flicker
      - Blinking block cursor at the end of the typed text
    """
    import random as _rng

    # ── Background dim ──
    overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
    overlay.fill((0, 0, 0, int(220 * ease)))
    surface.blit(overlay, (0, 0))

    # ── Monitor dimensions + position ──
    # Wider than tall - like a real CRT monitor.
    mw, mh = 680, 520
    mx = WIDTH // 2 - mw // 2
    my = int(HEIGHT // 2 - mh // 2 + (1 - ease) * 60)

    # ── Monitor body (bezel) - dark grey plastic ──
    bezel_col = (35, 38, 35)
    pygame.draw.rect(surface, (10, 12, 10), (mx - 4, my - 4, mw + 8, mh + 8), border_radius=8)
    pygame.draw.rect(surface, bezel_col, (mx, my, mw, mh), border_radius=6)
    # Bezel highlight (top edge).
    pygame.draw.line(surface, (60, 65, 60), (mx + 8, my + 2), (mx + mw - 8, my + 2), 1)

    # ── Screen area (inset from bezel) ──
    screen_inset = 24
    sx = mx + screen_inset
    sy = my + screen_inset
    sw = mw - screen_inset * 2
    sh = mh - screen_inset * 2 - 40  # leave room for power LED at bottom

    # Screen background - dark green-black.
    pygame.draw.rect(surface, (6, 18, 12), (sx, sy, sw, sh), border_radius=4)

    # ── Screen curvature gradient (lighter in center) ──
    curvature = pygame.Surface((sw, sh), pygame.SRCALPHA)
    for i in range(20):
        a = max(0, 15 - i)
        inset = i * 3
        if inset < sw // 2 and inset < sh // 2:
            pygame.draw.rect(curvature, (0, 40, 20, a),
                             (inset, inset, sw - inset * 2, sh - inset * 2),
                             border_radius=3)
    surface.blit(curvature, (sx, sy))

    # ── Phosphor glow around text ──
    glow = pygame.Surface((sw, sh), pygame.SRCALPHA)
    for i in range(8):
        a = 12 - i
        if a > 0:
            pygame.draw.rect(glow, (30, 80, 40, a),
                             (i * 2, i * 2, sw - i * 4, sh - i * 4),
                             border_radius=3)
    surface.blit(glow, (sx, sy))

    # ── Scanlines ──
    for ly in range(sy, sy + sh, 3):
        scanline = pygame.Surface((sw, 1), pygame.SRCALPHA)
        scanline.fill((0, 60, 30, 50))
        surface.blit(scanline, (sx, ly))

    # ── Screen flicker (subtle) ──
    if _rng.random() < 0.1:
        flicker = pygame.Surface((sw, sh), pygame.SRCALPHA)
        flicker.fill((40, 100, 60, 15))
        surface.blit(flicker, (sx, sy))

    # ── Boot-up sequence ──
    # Phase 1 (age 0-30): "ACCESSING DATABASE..." types out
    # Phase 2 (age 30+): "DECRYPTED" + the actual text types out
    phosphor_green = (100, 230, 120)
    dim_green = (60, 140, 75)

    # Boot header.
    boot_text = "> ACCESSING AUTHORIZATION CHAIN"
    boot_progress = min(1.0, age / 25.0)
    boot_chars = int(len(boot_text) * boot_progress)
    if boot_chars > 0:
        boot_surf = font_terminal.render(boot_text[:boot_chars], True, phosphor_green)
        surface.blit(boot_surf, (sx + 16, sy + 16))

    # Blinking cursor during boot.
    if boot_progress < 1.0 and (age % 12) < 6:
        cursor_x = sx + 16 + (font_terminal.size(boot_text[:boot_chars])[0] if boot_chars > 0 else 0)
        pygame.draw.rect(surface, phosphor_green, (cursor_x + 2, sy + 18, 10, 16))

    # After boot, show "DECRYPTED" + the text.
    if age >= 25:
        # "DECRYPTED" status.
        dec_surf = font_terminal.render(_T("m2.decrypted"), True, phosphor_green)
        surface.blit(dec_surf, (sx + 16, sy + 40))

        # Separator line.
        pygame.draw.line(surface, dim_green,
                         (sx + 16, sy + 64), (sx + sw - 16, sy + 64), 1)

        # The actual text - types out character-by-character.
        # Pre-wrap each source line to fit within the screen width so long
        # lines (e.g. "ROUTED VIA:  Office of the Prime Minister") don't
        # overflow the right edge of the monitor.
        text_max_w = sw - 32  # 16px padding each side
        wrapped_lines = []
        for line in card["lines"][2:]:
            if not line:
                wrapped_lines.append(("", line))  # preserve blank lines
                continue
            # Word-wrap this line.
            words = line.split()
            cur = ""
            for word in words:
                test = (cur + " " + word).strip()
                if font_terminal.size(test)[0] > text_max_w and cur:
                    wrapped_lines.append((cur, line))  # store original line for color
                    cur = word
                else:
                    cur = test
            if cur:
                wrapped_lines.append((cur, line))

        # Total characters across all wrapped lines, revealed progressively.
        full_text = "\n".join(wl[0] for wl in wrapped_lines)
        reveal_progress = min(1.0, max(0, (age - 30)) / 90.0)
        total_chars = len(full_text)
        revealed_chars = int(total_chars * reveal_progress)

        # Render the revealed text line by line.
        text_y = sy + 76
        char_count = 0
        for display_line, original_line in wrapped_lines:
            if char_count >= revealed_chars:
                break
            line_chars = len(display_line) + 1  # +1 for the newline
            visible = min(len(display_line), revealed_chars - char_count)
            if visible > 0:
                # Color: warnings in brighter green, regular text in phosphor.
                if "WARNING" in original_line:
                    line_col = (180, 255, 100)
                else:
                    line_col = phosphor_green
                txt_surf = font_terminal.render(display_line[:visible], True, line_col)
                surface.blit(txt_surf, (sx + 16, text_y))
                # Blinking cursor at the end of the currently-typing line.
                if char_count + visible < total_chars and (age % 12) < 6:
                    cx_cursor = sx + 16 + txt_surf.get_width()
                    pygame.draw.rect(surface, phosphor_green,
                                     (cx_cursor + 2, text_y + 2, 10, 16))
            char_count += line_chars
            text_y += 22

    # ── Screen border (green) ──
    pygame.draw.rect(surface, dim_green, (sx, sy, sw, sh), 1, border_radius=4)

    # ── Power LED at bottom of monitor ──
    led_x = mx + mw // 2
    led_y = my + mh - 20
    pygame.draw.circle(surface, (80, 200, 80), (led_x, led_y), 4)
    pygame.draw.circle(surface, (40, 100, 40), (led_x, led_y), 4, 1)

    # ── Close hint ──
    hint = font_terminal.render(_T("m2.e_close"), True, phosphor_green)
    if age >= 18 or (_now_ms() // 400) % 2 == 0:
        surface.blit(hint, (WIDTH // 2 - hint.get_width() // 2, my + mh + 20))


def _draw_packet_document(surface, card, age, ease):
    """Render the evidence card as an actual press release document.

    Not a "card with packet overlay" - an actual press release:
      - White paper with letterhead at the top
      - "IPA PRESS OFFICE" letterhead with a simple logo
      - "FOR IMMEDIATE RELEASE (HOLD)" line
      - Press release body text written on the paper
      - Red "CLASSIFIED" stamp diagonal across the document
      - Slightly crumpled/aged paper texture
      - Date stamp at the bottom
    """
    import random as _rng
    rng = _rng.Random(42)

    # ── Background dim ──
    overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
    overlay.fill((0, 0, 0, int(200 * ease)))
    surface.blit(overlay, (0, 0))

    # ── Paper dimensions + position ──
    # Portrait orientation, slightly wider than the decree.
    pw, ph = 540, 600
    px = WIDTH // 2 - pw // 2
    py = int(HEIGHT // 2 - ph // 2 + (1 - ease) * 80)

    # ── Drop shadow ──
    shadow = pygame.Surface((pw + 24, ph + 24), pygame.SRCALPHA)
    pygame.draw.rect(shadow, (0, 0, 0, int(120 * ease)), shadow.get_rect(), border_radius=4)
    surface.blit(shadow, (px - 6, py + 10))

    # ── Paper body - off-white, slightly crumpled ──
    paper_col = (238, 232, 220)
    pygame.draw.rect(surface, paper_col, (px, py, pw, ph), border_radius=2)

    # ── Crumpled paper texture ──
    texture = pygame.Surface((pw, ph), pygame.SRCALPHA)
    for _ in range(50):
        tx = rng.randint(0, pw)
        ty = rng.randint(0, ph)
        tw = rng.randint(20, 70)
        th = rng.randint(6, 16)
        ta = rng.randint(8, 18)
        # Brownish creases.
        pygame.draw.rect(texture, (160, 140, 100, ta), (tx, ty, tw, th))
    # Crease lines (darker).
    for _ in range(8):
        x1 = rng.randint(0, pw)
        y1 = rng.randint(0, ph)
        x2 = x1 + rng.randint(-60, 60)
        y2 = y1 + rng.randint(-30, 30)
        pygame.draw.line(texture, (140, 120, 90, 30), (x1, y1), (x2, y2), 1)
    surface.blit(texture, (px, py))

    # ── Letterhead at top ──
    # "IPA PRESS OFFICE" with a simple logo (rectangular badge).
    logo_x = px + 40
    logo_y = py + 30
    # Logo badge - brown rectangle with "IPA" text.
    pygame.draw.rect(surface, (110, 80, 50), (logo_x, logo_y, 50, 32), border_radius=2)
    pygame.draw.rect(surface, (70, 50, 30), (logo_x, logo_y, 50, 32), 1, border_radius=2)
    ipa_text = font_terminal_small.render(_T("m2.ipa"), True, (230, 210, 180))
    surface.blit(ipa_text, (logo_x + 25 - ipa_text.get_width() // 2, logo_y + 8))

    # Letterhead text.
    lh = font_speaker.render(_T("m2.ipa_press_office"), True, (80, 60, 40))
    surface.blit(lh, (logo_x + 60, logo_y + 2))
    lh2 = font_terminal_small.render(_T("m2.office_of_communications"), True, (120, 100, 80))
    surface.blit(lh2, (logo_x + 60, logo_y + 22))

    # ── Horizontal rule under letterhead ──
    pygame.draw.line(surface, (110, 80, 50),
                     (px + 40, py + 80), (px + pw - 40, py + 80), 2)

    # ── "FOR IMMEDIATE RELEASE (HOLD)" ──
    release = font_terminal.render(_T("m2.for_immediate_release_hold"), True, (140, 30, 25))
    surface.blit(release, (px + pw // 2 - release.get_width() // 2, py + 95))

    # ── Press release body text ──
    text_y = py + 130
    text_x = px + 50
    text_w = pw - 100
    for line in card["lines"][2:]:  # skip letterhead lines
        if not line:
            text_y += 12
            continue
        # "Prepared:" line - render in red.
        if "Prepared:" in line:
            txt_surf = font_terminal_small.render(line, True, (160, 40, 30))
            surface.blit(txt_surf, (text_x, text_y))
            text_y += 20
            continue
        # Body text - dark grey, word-wrapped.
        words = line.split()
        cur = ""
        for word in words:
            test = (cur + " " + word).strip()
            if font_dialogue.size(test)[0] > text_w and cur:
                wrapped = font_dialogue.render(cur, True, (50, 45, 40))
                surface.blit(wrapped, (text_x, text_y))
                text_y += 22
                cur = word
            else:
                cur = test
        if cur:
            wrapped = font_dialogue.render(cur, True, (50, 45, 40))
            surface.blit(wrapped, (text_x, text_y))
            text_y += 22

    # ── Red "CLASSIFIED" stamp diagonal across the document ──
    stamp_text = "CLASSIFIED"
    stamp_surf = font_speaker.render(stamp_text, True, (170, 25, 20))
    # Rotate 18 degrees for the stamped-diagonal look.
    rotated_stamp = pygame.transform.rotate(stamp_surf, 18)
    stamp_rect = rotated_stamp.get_rect(center=(px + pw // 2 + 40, py + ph // 2 + 20))
    # Stamp border (red rectangle, slightly transparent).
    stamp_bg = pygame.Surface((rotated_stamp.get_width() + 20,
                                rotated_stamp.get_height() + 14), pygame.SRCALPHA)
    pygame.draw.rect(stamp_bg, (170, 25, 20, 50),
                     stamp_bg.get_rect(), 3, border_radius=3)
    # Double-strike for ink bleed.
    surface.blit(rotated_stamp, (stamp_rect.x - 2, stamp_rect.y - 1))
    surface.blit(rotated_stamp, (stamp_rect.x + 2, stamp_rect.y + 1))
    surface.blit(rotated_stamp, stamp_rect)
    surface.blit(stamp_bg, (stamp_rect.x - 10, stamp_rect.y - 7))

    # ── Paper border ──
    pygame.draw.rect(surface, (150, 130, 100), (px, py, pw, ph), 1, border_radius=2)

    # ── Close hint ──
    hint = font_terminal.render(_T("m2.e_close"), True, (140, 30, 25))
    if age >= 18 or (_now_ms() // 400) % 2 == 0:
        surface.blit(hint, (WIDTH // 2 - hint.get_width() // 2, py + ph + 20))


def _draw_tanker_schematic(surface, w, h, age, col):
    """Technical blueprint schematic of the valve + detonator circuit.

    Drawn inside the card's preview area. Shows:
      - Tank (cross-section, top)
      - Pipe run with flanges (vertical)
      - Hand-wheel valve (mid)
      - Detonator box wired to the valve (right side)
      - "ARMED" indicator (blinking red LED)
      - Signal waves emanating from the detonator (remote trigger)
    """
    cx = w // 2

    # --- Tank cross-section (top) ---
    tank_top_y = 24
    tank_w, tank_h = 80, 40
    tank_rect = pygame.Rect(cx - tank_w // 2, tank_top_y, tank_w, tank_h)
    # Tank outline (blueprint cyan)
    tank_line = (90, 180, 200)
    pygame.draw.rect(surface, tank_line, tank_rect, 2, border_radius=2)
    # Tank hatching (diagonal lines = "this is a tank")
    for i in range(-tank_h, tank_w, 8):
        x1 = tank_rect.x + i
        y1 = tank_rect.y
        x2 = tank_rect.x + i + tank_h
        y2 = tank_rect.y + tank_h
        if x1 < tank_rect.x:
            y1 += (tank_rect.x - x1)
            x1 = tank_rect.x
        if x2 > tank_rect.right:
            y2 -= (x2 - tank_rect.right)
            x2 = tank_rect.right
        if y1 < y2 and x1 < x2:
            pygame.draw.line(surface, (40, 90, 100), (x1, y1), (x2, y2), 1)
    # "TANK" label inside
    tank_lbl = font_terminal_small.render(_T("m2.tank"), True, tank_line)
    surface.blit(tank_lbl, (tank_rect.centerx - tank_lbl.get_width() // 2,
                            tank_rect.y + tank_h // 2 - 6))

    # --- Pipe run (vertical, tank -> valve -> outlet) ---
    pipe_x = cx
    pipe_top = tank_rect.bottom
    pipe_bot = tank_rect.bottom + 30
    pygame.draw.line(surface, tank_line, (pipe_x, pipe_top), (pipe_x, pipe_bot), 3)
    # Pipe center highlight (cylinder sheen)
    pygame.draw.line(surface, (140, 210, 220), (pipe_x - 1, pipe_top), (pipe_x - 1, pipe_bot), 1)

    # --- Flange between tank and pipe ---
    flange_y = tank_rect.bottom
    pygame.draw.rect(surface, tank_line, (pipe_x - 14, flange_y - 2, 28, 4))
    # Flange bolts
    for bx in (pipe_x - 10, pipe_x - 4, pipe_x + 4, pipe_x + 10):
        pygame.draw.circle(surface, tank_line, (bx, flange_y), 1)

    # --- Hand-wheel valve (mid) ---
    valve_cx = pipe_x
    valve_cy = pipe_bot + 12
    valve_r = 12
    # Valve body (small rect)
    pygame.draw.rect(surface, tank_line, (valve_cx - 8, valve_cy - 4, 16, 8), 1)
    # Hand-wheel
    pygame.draw.circle(surface, tank_line, (valve_cx, valve_cy), valve_r, 2)
    # Spokes
    for angle_deg in (0, 45, 90, 135):
        a = math.radians(angle_deg)
        ex = valve_cx + int((valve_r - 1) * math.cos(a))
        ey = valve_cy + int((valve_r - 1) * math.sin(a))
        pygame.draw.line(surface, tank_line, (valve_cx, valve_cy), (ex, ey), 1)
    # Hub
    pygame.draw.circle(surface, tank_line, (valve_cx, valve_cy), 2)
    # Valve label
    v_lbl = font_terminal_small.render(_T("m2.valve"), True, tank_line)
    surface.blit(v_lbl, (valve_cx - v_lbl.get_width() // 2, valve_cy + valve_r + 2))

    # --- Detonator box (right of the valve) ---
    det_x = valve_cx + 36
    det_y = valve_cy - 10
    det_w, det_h = 30, 20
    pygame.draw.rect(surface, (180, 60, 50), (det_x, det_y, det_w, det_h), 2, border_radius=2)
    # "DET" label
    det_lbl = font_terminal_small.render(_T("m2.det"), True, (220, 100, 80))
    surface.blit(det_lbl, (det_x + det_w // 2 - det_lbl.get_width() // 2,
                           det_y + det_h // 2 - 6))
    # Wire from detonator to valve body (jagged = electrical)
    wire_pts = [
        (det_x, valve_cy - 4),
        (det_x - 6, valve_cy - 8),
        (det_x - 12, valve_cy - 2),
        (det_x - 18, valve_cy - 6),
        (valve_cx + 8, valve_cy - 4),
    ]
    pygame.draw.lines(surface, (220, 120, 80), False, wire_pts, 1)

    # --- ARMED LED (blinking) ---
    led_pulse = 0.5 + 0.5 * math.sin(age * 0.25)
    led_col = (255, int(40 + 80 * led_pulse), 30)
    led_x = det_x + det_w - 4
    led_y = det_y + 3
    pygame.draw.circle(surface, led_col, (led_x, led_y), 2)
    # LED glow
    glow = pygame.Surface((10, 10), pygame.SRCALPHA)
    pygame.draw.circle(glow, (255, 40, 30, int(80 * led_pulse)), (5, 5), 4)
    surface.blit(glow, (led_x - 5, led_y - 5))
    # "ARMED" text
    armed_lbl = font_terminal_small.render(_T("m2.armed"), True, led_col)
    surface.blit(armed_lbl, (led_x - armed_lbl.get_width() - 4, det_y + det_h + 2))

    # --- Signal waves emanating from the detonator (remote trigger) ---
    wave_cx = det_x + det_w + 4
    wave_cy = det_y + det_h // 2
    for i in range(3):
        wr = 6 + i * 5 + int(2 * math.sin(age * 0.15 + i))
        wave_alpha = max(0, 120 - i * 40)
        pygame.draw.arc(surface, (255, 150, 80),
                        (wave_cx - wr, wave_cy - wr, wr * 2, wr * 2),
                        -math.pi / 3, math.pi / 3, 1)

    # --- "SECONDARY DEVICE" caption at the bottom of the schematic ---
    cap = font_terminal_small.render(_T("m2.secondary_device"), True, (160, 140, 100))
    surface.blit(cap, (w // 2 - cap.get_width() // 2, h - 18))


def _draw_pistol_icon(surface, cx, cy, scale=1.0, color=None):
    """Small top-down pistol silhouette for the HUD weapon bar.

    Draws a recognizable pistol profile at HUD icon size (~20px long).
    Anatomy: grip (angled back), receiver body, barrel, trigger guard.
    All coordinates are relative to (cx, cy) = center of the receiver.
    """
    s = scale
    # Colors - dark metal with a lighter highlight edge
    metal = color if color else (130, 128, 122)
    metal_dark = (60, 58, 54)
    metal_hi = (165, 162, 155)
    grip_col = (85, 60, 38)  # wooden grip

    def p(dx, dy):
        return (int(cx + dx * s), int(cy + dy * s))

    # Grip (angled down-left from the receiver, wooden)
    grip_pts = [p(-3, 2), p(1, 2), p(3, 10), p(-4, 10)]
    pygame.draw.polygon(surface, grip_col, grip_pts)
    pygame.draw.polygon(surface, metal_dark, grip_pts, 1)

    # Receiver body (the main chunky block)
    receiver_pts = [p(-4, -2), p(6, -2), p(6, 3), p(-4, 3)]
    pygame.draw.polygon(surface, metal, receiver_pts)
    pygame.draw.polygon(surface, metal_dark, receiver_pts, 1)
    # Top slide highlight (lit edge)
    pygame.draw.line(surface, metal_hi, p(-3, -1), p(5, -1), 1)

    # Barrel (narrow rectangle extending forward)
    barrel_pts = [p(6, -1), p(11, -1), p(11, 2), p(6, 2)]
    pygame.draw.polygon(surface, metal_dark, barrel_pts)
    # Muzzle (small dark circle at the tip)
    pygame.draw.circle(surface, (30, 28, 26), p(11, 0), max(1, int(1.5 * s)))

    # Trigger guard (small arc below the receiver)
    pygame.draw.arc(surface, metal_dark,
                    pygame.Rect(p(-1, 3)[0], p(-1, 3)[1], int(6 * s), int(5 * s)),
                    math.pi, 2 * math.pi, 1)


def _draw_rifle_icon(surface, cx, cy, scale=1.0, color=None):
    """Small top-down rifle silhouette for the HUD weapon bar.

    Draws a recognizable assault rifle profile at HUD icon size (~28px long).
    Anatomy: stock, receiver, magazine, handguard, barrel, front sight.
    All coordinates are relative to (cx, cy) = center of the receiver.
    """
    s = scale
    metal = color if color else (130, 128, 122)
    metal_dark = (60, 58, 54)
    metal_hi = (165, 162, 155)
    wood_col = (110, 70, 40)  # wooden handguard + stock
    wood_dark = (75, 48, 28)

    def p(dx, dy):
        return (int(cx + dx * s), int(cy + dy * s))

    # Stock (wooden, extends back from the receiver)
    stock_pts = [p(-15, -2), p(-8, -3), p(-8, 3), p(-15, 3)]
    pygame.draw.polygon(surface, wood_col, stock_pts)
    pygame.draw.polygon(surface, wood_dark, stock_pts, 1)
    # Stock highlight
    pygame.draw.line(surface, (140, 95, 55), p(-14, -1), p(-9, -2), 1)

    # Receiver body (the main metal block)
    receiver_pts = [p(-8, -3), p(6, -3), p(6, 3), p(-8, 3)]
    pygame.draw.polygon(surface, metal, receiver_pts)
    pygame.draw.polygon(surface, metal_dark, receiver_pts, 1)
    # Top highlight
    pygame.draw.line(surface, metal_hi, p(-7, -2), p(5, -2), 1)

    # Magazine (curved, hanging below the receiver - the AK-style banana mag)
    mag_pts = [p(-3, 3), p(3, 3), p(4, 10), p(-2, 10)]
    pygame.draw.polygon(surface, metal_dark, mag_pts)
    pygame.draw.polygon(surface, (30, 28, 26), mag_pts, 1)

    # Handguard (wooden, in front of the receiver)
    hg_pts = [p(6, -2), p(12, -2), p(12, 2), p(6, 2)]
    pygame.draw.polygon(surface, wood_col, hg_pts)
    pygame.draw.polygon(surface, wood_dark, hg_pts, 1)

    # Barrel (extends past the handguard)
    barrel_pts = [p(12, -1), p(16, -1), p(16, 1), p(12, 1)]
    pygame.draw.polygon(surface, metal_dark, barrel_pts)

    # Front sight (small post on top of the barrel)
    pygame.draw.rect(surface, metal_dark, (p(14, -2)[0], p(14, -2)[1], max(1, int(2 * s)), max(1, int(2 * s))))
    # Muzzle
    pygame.draw.circle(surface, (30, 28, 26), p(16, 0), max(1, int(1 * s)))


def _draw_weapon_hud(surface):
    """Draw the weapon swap indicator as a header bar for the ammo panel.

    Tactical military style - designed to sit flush on top of the ammo
    panel as a unified header, matching its width and border style so the
    weapon selector + ammo readout read as ONE cohesive HUD element.

    Layout (flush atop the ammo panel, same width):
        ┌──────────────────────────────────────────────────┐
        │ ▌ Q  PISTOL              ⇄              Q  OS 12 │
        ├──────────────────────────────────────────────────┤
        │  (ammo panel content drawn by _draw_hud below)   │
        └──────────────────────────────────────────────────┘

    The panel width matches the ammo panel (296 for OS12, 246 for pistol)
    so the two elements align perfectly with no gap and no width mismatch.
    The weapon bar uses the same background color, border color, and
    border-radius as the ammo panel - they share a design language.
    """
    if not getattr(STATE, "os12_unlocked", False):
        return  # Only show after OS 12 is acquired

    from core.config import WIDTH, HEIGHT, font_terminal, font_terminal_small

    is_os12 = getattr(STATE, "current_weapon", "pistol") == "os12"

    # ── Match the ammo panel's width exactly (no collision, no mismatch) ──
    # The ammo panel is now unified_w wide, at x=24 (unified_x).
    # We match that width so the weapon bar sits flush on top as a header.
    panel_w = 296 if is_os12 else 246
    panel_h = 26
    panel_x = 24  # matches unified_x
    # Sit directly above the molotov panel. The stack from bottom up:
    #   HP bar:      HEIGHT-40 .. HEIGHT-10  (30px tall)
    #   Ammo panel:  HEIGHT-40-bg_h-2 .. HEIGHT-40-2  (96 or 92 tall)
    #   Molotov:     ammo_y-38 .. ammo_y-2  (36 tall)
    #   Weapon bar:  molotov_y-panel_h-2 .. molotov_y-2  (26 tall)
    ammo_bg_h = 96 if is_os12 else 92
    ammo_y = HEIGHT - 40 - ammo_bg_h - 2
    molotov_y = ammo_y - 38
    panel_y = molotov_y - panel_h - 2  # 2px gap above molotov panel

    # ── Panel background - matches ammo panel styling exactly ──
    panel_bg = pygame.Surface((panel_w, panel_h), pygame.SRCALPHA)
    pygame.draw.rect(panel_bg, (0, 0, 0, 150), (0, 0, panel_w, panel_h), border_radius=4)
    pygame.draw.rect(panel_bg, (40, 42, 38), (0, 0, panel_w, panel_h), 1, border_radius=4)
    surface.blit(panel_bg, (panel_x, panel_y))

    # ── Colors ──
    active_name_col = C_TERMINAL           # (50, 255, 150) green phosphor
    active_q_col = (255, 200, 80)          # amber
    inactive_name_col = (80, 80, 75)       # dim grey
    inactive_q_col = (120, 100, 50)        # dim amber
    arrow_col = (50, 180, 110)             # medium green
    accent_bar_col = C_TERMINAL             # green accent bar on active

    # ── Render text elements ──
    pistol_active = not is_os12
    pistol_q_col = active_q_col if pistol_active else inactive_q_col
    pistol_name_col = active_name_col if pistol_active else inactive_name_col
    pistol_q = font_terminal_small.render(_T("m2.q"), True, pistol_q_col)
    pistol_name = font_terminal_small.render(_T("m2.pistol"), True, pistol_name_col)

    os12_q_col = active_q_col if is_os12 else inactive_q_col
    os12_name_col = active_name_col if is_os12 else inactive_name_col
    os12_q = font_terminal_small.render(_T("m2.q"), True, os12_q_col)
    os12_name = font_terminal_small.render(_T("m2.os_12"), True, os12_name_col)

    arrow = font_terminal_small.render(_T("m2.text"), True, arrow_col)

    # ── Positions (icon + Q + name per slot, arrow centered between) ──
    text_y = panel_y + 6
    padding = 14
    icon_scale = 0.9
    # Icon dimensions (approximate, for spacing):
    #   pistol icon is ~15px wide (from -4 to +11), rifle is ~31px wide (-15 to +16)
    pistol_icon_w = int(15 * icon_scale)
    rifle_icon_w = int(31 * icon_scale)
    icon_gap = 4  # gap between icon and "Q"

    # Left slot: [accent] [pistol icon] [Q] [PISTOL], starting at panel_x + padding
    pistol_icon_cx = panel_x + padding + 6  # icon center (6px in from slot start)
    pistol_q_x = pistol_icon_cx + pistol_icon_w // 2 + icon_gap
    pistol_name_x = pistol_q_x + pistol_q.get_width() + 6

    # Right slot: [accent] [rifle icon] [Q] [OS 12], right-aligned
    os12_name_x = panel_x + panel_w - padding - os12_name.get_width()
    os12_q_x = os12_name_x - 6 - os12_q.get_width()
    os12_icon_cx = os12_q_x - icon_gap - rifle_icon_w // 2

    # Arrow centered in the gap between the two slots
    left_slot_end = pistol_name_x + pistol_name.get_width()
    right_slot_start = os12_icon_cx - rifle_icon_w // 2
    arrow_x = left_slot_end + (right_slot_start - left_slot_end - arrow.get_width()) // 2

    # ── Active weapon accent bar (3px vertical bar on the active slot's left edge) ──
    if pistol_active:
        accent_x = panel_x + 6
    else:
        accent_x = os12_icon_cx - rifle_icon_w // 2 - 6
    pygame.draw.rect(surface, accent_bar_col,
                     (accent_x, panel_y + 5, 3, panel_h - 10), border_radius=1)

    # ── Weapon icons (dimmed for inactive, bright for active) ──
    # Active weapon gets full-color icons; inactive gets a dim grey wash.
    pistol_icon_col = None if pistol_active else (85, 85, 80)
    rifle_icon_col = None if is_os12 else (85, 85, 80)
    # Icons are vertically centered in the panel (panel_y + panel_h/2)
    icon_cy = panel_y + panel_h // 2 + 1
    _draw_pistol_icon(surface, pistol_icon_cx, icon_cy, scale=icon_scale, color=pistol_icon_col)
    _draw_rifle_icon(surface, os12_icon_cx, icon_cy, scale=icon_scale, color=rifle_icon_col)

    # ── Blit text ──
    surface.blit(pistol_q, (pistol_q_x, text_y))
    surface.blit(pistol_name, (pistol_name_x, text_y))
    surface.blit(arrow, (arrow_x, text_y))
    surface.blit(os12_q, (os12_q_x, text_y))
    surface.blit(os12_name, (os12_name_x, text_y))


def _draw_hud(surface):
    if not STATE.player:
        return
    # ── Unified bottom-left HUD stack ──
    # All 4 elements (weapon swap, molotov, ammo, HP) now share the same
    # width (296 for OS12, 246 for pistol), x position (24), background
    # color, and border style. They stack flush with no gaps so they read
    # as ONE cohesive panel rather than 4 separate floating elements.
    is_os12_hud = getattr(STATE, "current_weapon", "pistol") == "os12"
    unified_w = 296 if is_os12_hud else 246
    unified_x = 24

    # HP bar - shared engine.ui.std widget (Phase 4). The panel tracks
    # unified_w (296 with the OS-12) so it stays flush under the ammo panel.
    _hud_health_bar.draw(surface, THEME, STATE.player.hp, STATE.player.max_hp,
                         panel_bg=get_panel_bg, panel=(unified_w, 30),
                         bb=(6, 4, unified_w - 12, 14))

    # Shared objective panel (was 620 px wide; now uses the shared 520 px panel
    # so the layout matches M1 exactly).
    draw_objective_panel(surface, _m2_world._objective)

    # The OS 12 panel needs more room: two tall AR mags, ammo number,
    # caliber tag, mag counter, and a reload bar. The pistol panel keeps
    # its original footprint since it has far less to show.
    if is_os12_hud:
        bg_w, bg_h = unified_w, 96
    else:
        bg_w, bg_h = unified_w, 92
    ammo_x, ammo_y = unified_x + 6, HEIGHT - 40 - bg_h - 2  # 2px gap above HP bar
    bg = get_panel_bg(bg_w, bg_h)
    surface.blit(bg, (unified_x, ammo_y))
    # No separate header label: the weapon-selector tabs above the panel
    # already identify the active weapon, so an extra title here just
    # crowded the area.

    if is_os12_hud:
        o_ammo = STATE.os12_ammo_in_mag
        o_mag = STATE.os12_mag_size
        o_spares = STATE.os12_spare_mags
        o_reloading = getattr(STATE, "os12_is_reloading", False)
        o_reload_timer = getattr(STATE, "os12_reload_timer", 0)

        # AR-15 / STANAG-style 25-round magazine.
        # (History: was "30-round" → "20-round" → now "25-round" to match
        # state.os12_mag_size = 25. The visible round count in the witness
        # slot is also 25 now, so the HUD matches the actual ammo state.)
        # Silhouette cues:
        #   - body width roughly constant top-to-bottom (no AK-style inward taper)
            #   - distinct forward curve toward the floorplate (banana arc)
        #   - squared feed lips up top with a small follower notch
        #   - wider floorplate sticking out the bottom
        #   - witness slot on the spine, rounds peek through
        num_mags = 2
        mag_w, mag_h = 18, 60           # slightly slimmer so the pair fits the column comfortably
        mag_gap = 14
        curve_amt = 6                   # how far the bottom kicks forward
        floor_overhang = 3              # floorplate extends past body sides
        floor_h = 5
        lip_h = 3
        total_mag_w = num_mags * (mag_w + floor_overhang * 2) + (num_mags - 1) * mag_gap
        # Center the mag pair inside its own left column of the panel.
        mag_col_w = 100
        start_x = ammo_x + (mag_col_w - total_mag_w) // 2

        def _curve_x(t):
            # t in [0,1] from feed lips (top) to floorplate (bottom).
            # Quadratic ease so the curve accelerates toward the bottom,
            # matching how 5.56 mags arc forward.
            return curve_amt * (t * t)

        for i in range(num_mags):
            mx = start_x + i * (mag_w + floor_overhang * 2 + mag_gap) + floor_overhang
            my = ammo_y + 6
            if i == 0:
                bullets_fill = min(o_ammo, o_mag)
                is_empty = o_ammo <= 0
            else:
                bullets_fill = o_mag if o_spares >= i else 0
                is_empty = o_spares < i

            # Body silhouette: trace down the left spine, across the floorplate
            # top, and back up the right (front) side. Both sides curve forward
            # by the same amount so width stays constant.
            steps = 10
            left_pts = []
            right_pts = []
            body_top_y = my + lip_h
            body_bot_y = my + mag_h - floor_h
            for s in range(steps + 1):
                t = s / steps
                offset = _curve_x(t)
                yy = body_top_y + (body_bot_y - body_top_y) * t
                left_pts.append((mx + offset, yy))
                right_pts.append((mx + mag_w + offset, yy))
            body_pts = left_pts + list(reversed(right_pts))

            if is_empty:
                base = (45, 42, 38); hl = (62, 58, 52); rim = (55, 50, 45)
            elif i == 0:
                base = (78, 74, 68); hl = (108, 104, 96); rim = (52, 48, 42)
            else:
                base = (62, 58, 52); hl = (88, 84, 76); rim = (46, 42, 38)

            pygame.draw.polygon(surface, base, body_pts)

            # Left-spine highlight strip - sells the curve and a polymer sheen.
            hl_pts = []
            for s in range(steps + 1):
                t = s / steps
                offset = _curve_x(t)
                yy = body_top_y + (body_bot_y - body_top_y) * t
                hl_pts.append((mx + offset + 1, yy))
            for s in range(steps, -1, -1):
                t = s / steps
                offset = _curve_x(t)
                yy = body_top_y + (body_bot_y - body_top_y) * t
                hl_pts.append((mx + offset + 4, yy))
            pygame.draw.polygon(surface, hl, hl_pts)

            outline = C_TERMINAL if i == 0 else rim
            pygame.draw.polygon(surface, outline, body_pts, 1)

            # Feed lips - squared block on top with a small follower notch.
            lip_rect = pygame.Rect(mx - 1, my, mag_w + 2, lip_h + 1)
            pygame.draw.rect(surface, base, lip_rect)
            pygame.draw.rect(surface, outline, lip_rect, 1)
            # Follower notch (the gap between the feed lips).
            notch_w = 4
            notch_x = mx + (mag_w - notch_w) // 2
            pygame.draw.rect(surface, (20, 18, 16), (notch_x, my + 1, notch_w, lip_h - 1))
            if not is_empty:
                # Topmost cartridge poking through the lips when loaded.
                pygame.draw.line(surface, (220, 185, 45),
                                 (notch_x + 1, my + 2),
                                 (notch_x + notch_w - 1, my + 2), 1)

            # Floorplate - wider rectangle at the bottom, kicked forward by
            # the full curve amount so it sits under the curved body.
            fp_offset = _curve_x(1.0)
            fp_rect = pygame.Rect(int(mx - floor_overhang + fp_offset),
                                  body_bot_y,
                                  mag_w + floor_overhang * 2,
                                  floor_h)
            fp_col = (38, 36, 32) if is_empty else (50, 47, 42)
            pygame.draw.rect(surface, fp_col, fp_rect)
            pygame.draw.rect(surface, outline, fp_rect, 1)

            # Bullet column - dots follow the spine curve, single column of
            # 25 rounds visible through a witness slot on the back.
            gold = (220, 185, 45)
            dark = (40, 38, 35) if not is_empty else (32, 30, 28)
            # Witness slot background - a thin dark stripe down the spine.
            slot_pts = []
            for s in range(steps + 1):
                t = s / steps
                offset = _curve_x(t)
                yy = body_top_y + 2 + (body_bot_y - body_top_y - 4) * t
                slot_pts.append((mx + offset + 6, yy))
            for s in range(steps, -1, -1):
                t = s / steps
                offset = _curve_x(t)
                yy = body_top_y + 2 + (body_bot_y - body_top_y - 4) * t
                slot_pts.append((mx + offset + mag_w - 6, yy))
            pygame.draw.polygon(surface, (28, 26, 24), slot_pts)

            # 25 rounds shown as a stacked column following the curve.
            # (Was 20 - bumped to match state.os12_mag_size = 25. The mag
            # silhouette is the same height, so rounds are slightly tighter
            # together, which reads as a denser/fuller magazine - appropriate
            # for the rebalanced middle-ground mag size.)
            rounds_total = 25
            round_span_top = body_top_y + 3
            round_span_bot = body_bot_y - 2
            for r in range(rounds_total):
                t = r / max(1, rounds_total - 1)
                offset = _curve_x(t)
                ry = round_span_top + (round_span_bot - round_span_top) * t
                rx = mx + offset + mag_w // 2
                # Round is visible if it would be in the loaded stack.
                # Stack fills from bottom up, so the BOTTOM rounds are present
                # first and missing rounds are at the top of the column.
                stack_index_from_bottom = rounds_total - 1 - r
                col = gold if stack_index_from_bottom < bullets_fill else dark
                pygame.draw.rect(surface, col, (int(rx - 3), int(ry), 7, 2))
                # Tiny case-rim highlight on loaded rounds.
                if stack_index_from_bottom < bullets_fill:
                    pygame.draw.line(surface, (255, 220, 120),
                                     (int(rx - 3), int(ry)),
                                     (int(rx + 3), int(ry)), 1)

            if is_empty:
                # Red diagonal across the whole mag silhouette for empty state.
                pygame.draw.line(surface, (160, 60, 55),
                                 (mx, my + 2),
                                 (mx + mag_w + fp_offset, body_bot_y + floor_h - 2), 2)

        # Right column of the panel: big ammo number, caliber tag,
        # mag counter, and optional reload bar. Anchored to the panel
        # so it doesn't shift when the mag silhouette dimensions change.
        text_x = ammo_x + mag_col_w + 12
        ammo_text = f"{o_ammo}/{o_mag}"
        text_col = (255, 200, 80) if o_ammo > 5 else (220, 60, 60)
        ammo_surf = font_terminal.render(ammo_text, True, text_col)
        surface.blit(ammo_surf, (text_x, ammo_y + 10))

        cal_surf = font_terminal_small.render(_T("m2.5_56_x_45_nato"), True, (110, 120, 110))
        surface.blit(cal_surf, (text_x, ammo_y + 36))

        if o_reloading:
            bar_x = text_x
            bar_y = ammo_y + 60
            bar_w_local, bar_h_local = 140, 8
            progress = 1.0 - o_reload_timer / 90
            pygame.draw.rect(surface, (50, 50, 50),
                             (bar_x, bar_y, bar_w_local, bar_h_local), border_radius=2)
            pygame.draw.rect(surface, (220, 160, 40),
                             (bar_x, bar_y, int(bar_w_local * progress), bar_h_local), border_radius=2)
            surface.blit(font_terminal_small.render(_T("m2.reloading"), True, (220, 160, 40)),
                         (text_x, ammo_y + 74))
        else:
            mag_label = f"MAGS  x {o_spares}"
            surface.blit(font_terminal_small.render(mag_label, True, (150, 160, 140)),
                         (text_x, ammo_y + 60))
    else:
        num_mags = 4
        for i in range(num_mags):
            mx = ammo_x + 8 + i * 36
            my = ammo_y + 8
            is_active = i == 0
            if is_active:
                bullets_fill = min(STATE.ammo_in_mag, 12)
                is_empty = STATE.ammo_in_mag <= 0
            else:
                bullets_fill = 12 if STATE.spare_mags >= i else 0
                is_empty = STATE.spare_mags < i
            top_w, bot_w, h = 24, 20, 46
            taper = (top_w - bot_w) // 2
            body_pts = [(mx, my), (mx + top_w, my), (mx + taper + bot_w, my + h), (mx + taper, my + h)]
            if is_empty:
                base = (45, 42, 38); hl = (55, 52, 48); rim = (55, 50, 45)
            elif is_active:
                base = (90, 86, 78); hl = (115, 110, 100); rim = (70, 66, 58)
            else:
                base = (72, 68, 62); hl = (92, 88, 80); rim = (60, 56, 50)
            pygame.draw.polygon(surface, base, body_pts)
            pygame.draw.polygon(surface, hl, [(mx + 1, my + 2), (mx + 5, my + 2), (mx + taper + 3, my + h - 3), (mx + taper + 1, my + h - 3)])
            outline = C_TERMINAL if is_active else (rim if not is_empty else (55, 50, 45))
            pygame.draw.polygon(surface, outline, body_pts, 1)
            bullet_y = my + 8
            gold = (220, 185, 45)
            dark = (55, 52, 48) if not is_empty else (40, 38, 35)
            for bi in range(12):
                col = gold if bi < bullets_fill else dark
                pygame.draw.circle(surface, col, (mx + top_w // 2, bullet_y + bi * 3), 2)
            if is_empty:
                pygame.draw.line(surface, (90, 55, 55), (mx + 2, my + 2), (mx + top_w - 2, my + h - 2), 1)
                pygame.draw.line(surface, (90, 55, 55), (mx + top_w - 2, my + 2), (mx + 2, my + h - 2), 1)
        ammo_text = f"{STATE.ammo_in_mag}/{STATE.mag_size}"
        text_col = C_TERMINAL if STATE.ammo_in_mag > 0 else (220, 60, 60)
        surface.blit(font_terminal_small.render(ammo_text, True, text_col), (ammo_x + 154, ammo_y + 8))
        surface.blit(font_terminal_small.render(_T("m2.9mm"), True, (100, 110, 100)), (ammo_x + 154, ammo_y + 26))
        if STATE.is_reloading:
            bar_x, bar_y = ammo_x + 148, ammo_y + 46
            bar_w, bar_h = 80, 8
            progress = 1.0 - STATE.reload_timer / 60
            pygame.draw.rect(surface, (50, 50, 50), (bar_x, bar_y, bar_w, bar_h), border_radius=2)
            pygame.draw.rect(surface, (220, 160, 40), (bar_x, bar_y, int(bar_w * progress), bar_h), border_radius=2)
            surface.blit(font_terminal_small.render(_T("m2.reloading"), True, (220, 160, 40)), (ammo_x + 150, ammo_y + 58))
        else:
            mag_label = f"MAGS: {STATE.spare_mags}"
            surface.blit(font_terminal_small.render(mag_label, True, (140, 150, 130)), (ammo_x + 154, ammo_y + 44))

    # Bottle HUD - shared engine.ui.std strip (panel_bg = the cached 150 panel).
    from missions.m1 import _draw_molotov_icon as _mission1_molotov_icon
    _hud_bottle_hud.draw(surface, THEME, STATE.player_bottles,
                         panel_bg=get_panel_bg, icon=_mission1_molotov_icon,
                         x=unified_x, y=ammo_y - 38, width=bg_w, cap=4)

    _hud_hostiles.draw(surface, THEME, len(STATE.enemies))

    comms = "COMMS OFFLINE" if STATE.mission2_comms_cut else "COMMS: VASILE"
    comms_col = (220, 60, 55) if STATE.mission2_comms_cut else C_VASILE
    cs = font_terminal_small.render(comms, True, comms_col)
    surface.blit(cs, (WIDTH - cs.get_width() - 28, HEIGHT - 40))

    if STATE.mission2_stage == STAGE_COMBAT and getattr(STATE, "mission2_post_sniper_phase", "") in ("get_cover", "survive", "flank"):
        phase = getattr(STATE, "mission2_post_sniper_phase", "")
        exposed = _player_exposed_to_sniper()
        lock = getattr(STATE, "mission2_sniper_lock", 0)
        lock_max = max(1, getattr(STATE, "mission2_sniper_lock_max", SNIPER_LOCK_FRAMES))
        grace = getattr(STATE, "mission2_grace_timer", 0)

        if grace > 0:
            label = "SNIPER ACQUIRING"
            col = (255, 180, 80)
            ratio = 1.0 - grace / max(1, SNIPER_GRACE_FRAMES)
        elif exposed:
            label = "SNIPER LOCK"
            col = (255, 65, 40)
            ratio = lock / lock_max
        else:
            if phase == "get_cover":
                label = "BEHIND COVER"
            elif phase == "survive":
                label = "HOLD COVER"
            elif phase == "flank":
                label = "FLANK NOW"
            else:
                label = "LINE BROKEN"
            col = (90, 220, 135)
            ratio = lock / lock_max

        is_safe = not exposed and grace <= 0
        show_bar = not (phase == "flank" and is_safe)

        if is_safe:
            panel_w, panel_h = 220, 34
        else:
            panel_w, panel_h = 380, 58

        panel_x = WIDTH // 2 - panel_w // 2
        panel_y = 92

        panel = pygame.Surface((panel_w, panel_h), pygame.SRCALPHA)
        panel.fill((0, 0, 0, 190))
        pygame.draw.rect(panel, col, panel.get_rect(), 1)
        pygame.draw.rect(panel, (*col, 130), (0, 0, 5, panel_h))

        surface.blit(panel, (panel_x, panel_y))

        warn = font_terminal.render(label, True, col)
        surface.blit(warn, (WIDTH // 2 - warn.get_width() // 2, panel_y + 7))

        if show_bar:
            bar_w = 310 if not is_safe else 180
            bar_h = 9 if not is_safe else 5
            bx = WIDTH // 2 - bar_w // 2
            by = panel_y + (38 if not is_safe else 22)

            pygame.draw.rect(surface, (35, 20, 18), (bx, by, bar_w, bar_h))

            fill_w = int(bar_w * max(0.0, min(1.0, ratio)))

            if grace > 0:
                fill_col = (255, 180, 80)
            elif exposed:
                fill_col = (255, 55, 35)
            else:
                fill_col = (90, 220, 135)

            pygame.draw.rect(surface, fill_col, (bx, by, fill_w, bar_h))
            pygame.draw.rect(surface, col, (bx, by, bar_w, bar_h), 1)

            if exposed and lock > lock_max * 0.75 and (_now_ms() // 160) % 2 == 0:
                urgent = font_terminal_small.render(_T("m2.move_or_die"), True, (255, 210, 190))
                surface.blit(urgent, (WIDTH // 2 - urgent.get_width() // 2, by + 13))

    if STATE.mission2_stage == STAGE_RUN:
        sec = max(0, STATE.mission2_countdown // 60 + 1)
        warn = font_speaker.render(_T("m2.run_tanker_detonation_sec", sec=sec), True, (255, 75, 45))
        panel = pygame.Surface((warn.get_width() + 34, warn.get_height() + 14), pygame.SRCALPHA)
        panel.fill((0, 0, 0, 195))
        pygame.draw.rect(panel, (220, 60, 40), panel.get_rect(), 2)
        surface.blit(panel, (WIDTH // 2 - panel.get_width() // 2, 96))
        surface.blit(warn, (WIDTH // 2 - warn.get_width() // 2, 103))

    # NOTE: The old "EVIDENCE UPLOAD 0%" HUD bar that was drawn here during
    # STAGE_UPLOAD has been removed. It referenced STATE.mission2_upload_progress
    # which is NEVER updated - the retro CRT OS (upload_os.py) has its own
    # internal _upload_progress that drives the in-OS progress bar. The HUD
    # bar was dead UI from the old "hold [E]" mechanic and always showed 0%.


def _draw_radio_text(surface):
    if getattr(STATE, "mission2_card", None) or STATE.mission2_stage in (STAGE_SNIPER, STAGE_BLACKOUT):
        return
    draw_pinned_radio(surface)


def _draw_clues_note(surface):
    if not getattr(STATE, "mission2_all_clues_found", False):
        return
    if STATE.mission2_stage != STAGE_SNIPER:
        return
    phase = _sniper_phase_name()
    if phase != "movement_one":
        return
    txt = font_dialogue.render(_T("m2.the_evidence_was_wrong"), True, C_TERMINAL)
    bg = pygame.Surface((txt.get_width() + 24, txt.get_height() + 12), pygame.SRCALPHA)
    bg.fill((0, 0, 0, 150))
    pygame.draw.rect(bg, C_TERMINAL, bg.get_rect(), 1)
    surface.blit(bg, (WIDTH // 2 - bg.get_width() // 2, HEIGHT - 90))
    surface.blit(txt, (WIDTH // 2 - txt.get_width() // 2, HEIGHT - 86))


def _draw_sniper_closeup_insert(surf, actor, cam_x, cam_y):
    sx, sy = _world(actor["pos"], cam_x, cam_y)
    panel_w, panel_h = 220, 280
    px = WIDTH // 2 - panel_w // 2
    py = 0
    panel = pygame.Surface((panel_w, panel_h), pygame.SRCALPHA)
    panel.fill((18, 16, 20, 235))
    name = actor.get("name", "???")
    fnt = pygame.font.Font(None, 22)
    name_s = fnt.render(name, True, (200, 195, 180))
    panel.blit(name_s, (panel_w // 2 - name_s.get_width() // 2, 8))
    portrait_rect = pygame.Rect(panel_w // 2 - 48, 40, 96, 120)
    pygame.draw.rect(panel, (35, 30, 28), portrait_rect, border_radius=4)
    pygame.draw.rect(panel, (80, 75, 65), portrait_rect, 1, border_radius=4)
    face_cx = portrait_rect.centerx
    face_cy = portrait_rect.centery + 6
    pygame.draw.circle(panel, (60, 55, 50), (face_cx, face_cy), 28)
    pygame.draw.circle(panel, (85, 78, 70), (face_cx - 8, face_cy - 6), 5)
    pygame.draw.circle(panel, (85, 78, 70), (face_cx + 8, face_cy - 6), 5)
    activity = actor.get("activity", "")
    if activity == "frozen":
        pygame.draw.line(panel, (100, 95, 85), (face_cx - 14, face_cy + 12), (face_cx + 14, face_cy + 12), 2)
    elif activity in ("shouting", "breaking"):
        mouth_pts = [(face_cx - 10, face_cy + 10), (face_cx, face_cy + 16), (face_cx + 10, face_cy + 10)]
        pygame.draw.lines(panel, (140, 130, 115), False, mouth_pts, 2)
    hr_fnt = pygame.font.Font(None, 16)
    hr = hr_fnt.render(_T("m2.hr_112_sig_active"), True, (140, 35, 30))
    panel.blit(hr, (panel_w // 2 - hr.get_width() // 2, 168))
    for i in range(8):
        bar_h = 4 + ((i * 7 + getattr(STATE, "mission2_timer", 0) * 3) % 17)
        bar_x = 24 + i * 24
        bar_y = 194 + (22 - bar_h)
        c = (100 + i * 12, 180 + i * 6, 60 + i * 8)
        pygame.draw.rect(panel, c, (bar_x, bar_y, 12, bar_h))
    for i in range(6):
        sy2 = 222 + i * 8
        pygame.draw.line(panel, (55, 65, 50, 60 + i * 20), (16, sy2), (panel_w - 16, sy2), 1)
    pygame.draw.line(panel, (40, 120, 200, 100), (16, 260), (panel_w - 16, 260), 1)
    pygame.draw.line(panel, (40, 120, 200, 100), (16, 264), (panel_w - 16, 264), 1)
    audio_lines = ["V-16  //  MIC-DROP", "BW  4.2kHz  //  VOX"]
    for j, line in enumerate(audio_lines):
        al = hr_fnt.render(line, True, (80, 160, 210))
        panel.blit(al, (panel_w // 2 - al.get_width() // 2, 242 + j * 14))
    surf.blit(panel, (px, py))

def _draw_dead_air_overlay(surf):
    overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
    overlay.fill((8, 6, 10, 110))
    surf.blit(overlay, (0, 0))


def _draw_sniper_subtitles(surface, bar_h):
    # NOTE: The Gameplay → Subtitles setting is intentionally NOT honored here.
    # The sniper cutscene is a story-critical sequence where the dialogue is
    # the only way to understand what's happening (who dies, who's speaking,
    # the squad's reactions). Suppressing these subtitles would leave the
    # player watching a silent cutscene with no context. The subtitles setting
    # only affects in-mission gameplay radio chatter, not authored cutscene
    # dialogue.
    # Same radio widget as gameplay, anchored in the bottom letterbox bar.
    from ui.radio import draw_radio
    draw_radio(surface, anchor="letterbox", bar_h=bar_h, force_text=True)


def _draw_sniper_overlay(surface):
    if STATE.mission2_stage != STAGE_SNIPER:
        return
    phase = _sniper_phase_name()
    pt = int(getattr(STATE, "mission2_sniper_phase_timer", 0))
    cam_x = int(round(STATE.camera_x))
    cam_y = int(round(STATE.camera_y))

    def clamp(v, lo=0, hi=255):
        return max(lo, min(hi, int(v)))

    if getattr(STATE, "mission2_sniper_origin_revealed", False):
        pulse = (math.sin(STATE.mission2_timer * 0.06) + 1) / 2
        sx, sy = _world(SNIPER_NEST_POS, cam_x, cam_y)
        gl = pygame.Surface((60, 60), pygame.SRCALPHA)
        a = 90 + int(80 * pulse)
        pygame.draw.circle(gl, (255, 255, 210, a), (30, 30), 4)
        pygame.draw.circle(gl, (255, 255, 220, a // 2), (30, 30), 9)
        surface.blit(gl, (sx - 30, sy - 30))

    sil = getattr(STATE, "mission2_sniper_silhouette_flash", 0)
    if sil > 0:
        sx, sy = _world(SNIPER_NEST_POS, cam_x, cam_y)
        a = clamp(sil * 12, 0, 220)
        s = pygame.Surface((46, 58), pygame.SRCALPHA)
        pygame.draw.ellipse(s, (10, 8, 10, a), (16, 4, 14, 14))
        pygame.draw.polygon(s, (10, 8, 10, a), [(10, 22), (36, 22), (40, 50), (6, 50)])
        pygame.draw.line(s, (10, 8, 10, a), (24, 26), (46, 18), 3)
        surface.blit(s, (sx - 23, sy - 48))

    flash = getattr(STATE, "mission2_sniper_flash", 0)
    if flash > 0:
        full = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        full.fill((255, 245, 220, clamp(flash * 12, 0, 200) // 6))
        surface.blit(full, (0, 0))

    bar_h = 64
    bar = pygame.Surface((WIDTH, bar_h), pygame.SRCALPHA)
    bar.fill((0, 0, 0, 235))
    surface.blit(bar, (0, 0))
    surface.blit(bar, (0, HEIGHT - bar_h))

    label = {"regroup": "ROUTE 12 \u00b7 CHECKPOINT 12",
             "movement_one": "ROUTE 12 \u00b7 CONTACT",
             "movement_two": "ROUTE 12 \u00b7 THE SQUAD",
             "movement_three": "ROUTE 12 \u00b7 YOU'RE NEXT"}.get(phase, "ROUTE 12")
    stamp = font_terminal_small.render(label, True, (180, 60, 60))
    surface.blit(stamp, (28, bar_h // 2 - stamp.get_height() // 2))
    if (_now_ms() // 500) % 2 == 0:
        rec = font_terminal_small.render(_T("m2.rec"), True, (220, 50, 50))
        surface.blit(rec, (WIDTH - rec.get_width() - 28, bar_h // 2 - rec.get_height() // 2))

    s_start = _beat("movement_one", "silence_start", 999999)
    s_len = _beat("movement_one", "silence_frames", 110)
    if phase == "movement_one" and s_start <= pt < s_start + s_len:
        _draw_dead_air_overlay(surface)

    _draw_sniper_callout(surface, cam_x, cam_y)

    _draw_sniper_subtitles(surface, bar_h)
    _draw_tinnitus_overlay(surface)
    draw_vignette(surface, strength=210)


def clamp_alpha(v):
    return max(0, min(255, int(v)))


def _wrap_text(text, font, max_width):
    """Simple word-wrap that respects an existing pygame font."""
    words = text.split()
    if not words:
        return [""]
    lines = []
    cur = words[0]
    for w in words[1:]:
        trial = cur + " " + w
        if font.size(trial)[0] <= max_width:
            cur = trial
        else:
            lines.append(cur)
            cur = w
    lines.append(cur)
    return lines


def _draw_tanker_blast_fx(surface, cam_x, cam_y):
    """Cinematic fuel-tanker blast: screen-dominating fireball, massive
    mushroom cloud, BLEVE pops, heavy debris with smoke trails, ground
    glow, persistent scorch, and smoking wreckage where the tanker used
    to be. Drawn on top of the world layer."""
    if not getattr(STATE, "mission2_tanker_exploded", False):
        return

    tanker = STATE.mission2_tanker_rect
    cx, cy = tanker.centerx, tanker.centery
    scx = int(cx - cam_x)
    scy = int(cy - cam_y)
    bt = getattr(STATE, "mission2_tanker_blast_timer", 0)

    # --- Radial blast streaks - drawn FIRST (under the scorch) so the
    # scorch sits on top near the crater while the streaks reach far out.
    # Long tapering scorch marks radiating outward, like the shockwave
    # scorched the ground as it expanded. Grows in over 60 frames so the
    # streaks "shoot out" from the blast. Pre-computed at blast time.
    # All streaks are batched onto ONE full-screen alpha surface (16
    # streaks Ã- 6 segments = 96 polygons) so we only do a single blit. ---
    streak_grow = min(1.0, bt / 60.0) if bt < 60 else 1.0
    streak_surf = None
    for angle, start_r, end_r, width in getattr(STATE, "mission2_tanker_blast_streaks", []):
        cur_end_r = start_r + (end_r - start_r) * streak_grow
        # Quick bounds check - skip the whole streak if its midpoint is
        # well off-screen.
        mid_r = (start_r + cur_end_r) / 2
        mid_x = int(cx + math.cos(angle) * mid_r - cam_x)
        mid_y = int(cy + math.sin(angle) * mid_r - cam_y)
        if mid_x < -120 or mid_x > WIDTH + 120 or mid_y < -120 or mid_y > HEIGHT + 120:
            continue
        if streak_surf is None:
            streak_surf = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        # 6 trapezoid segments along the streak, tapering from `width` at
        # the base to ~2px at the tip. Drawn as filled polygons.
        segs = 6
        perp_x = -math.sin(angle)
        perp_y = math.cos(angle)
        for s in range(segs):
            frac1 = s / segs
            frac2 = (s + 1) / segs
            r1 = start_r + (cur_end_r - start_r) * frac1
            r2 = start_r + (cur_end_r - start_r) * frac2
            w1 = width * (1.0 - frac1 * 0.85)
            w2 = width * (1.0 - frac2 * 0.85)
            x1a = cx + math.cos(angle) * r1 + perp_x * w1
            y1a = cy + math.sin(angle) * r1 + perp_y * w1
            x1b = cx + math.cos(angle) * r1 - perp_x * w1
            y1b = cy + math.sin(angle) * r1 - perp_y * w1
            x2a = cx + math.cos(angle) * r2 + perp_x * w2
            y2a = cy + math.sin(angle) * r2 + perp_y * w2
            x2b = cx + math.cos(angle) * r2 - perp_x * w2
            y2b = cy + math.sin(angle) * r2 - perp_y * w2
            # Darken + reduce alpha toward the tip.
            shade = 1.0 - frac1 * 0.6
            col = (int(18 * shade), int(13 * shade), int(10 * shade))
            alpha = int(190 * (1.0 - frac1 * 0.5))
            pts = [
                (x1a - cam_x, y1a - cam_y),
                (x2a - cam_x, y2a - cam_y),
                (x2b - cam_x, y2b - cam_y),
                (x1b - cam_x, y1b - cam_y),
            ]
            pygame.draw.polygon(streak_surf, (*col, alpha), pts)
    if streak_surf is not None:
        surface.blit(streak_surf, (0, 0))

    # --- Cracked-asphalt ring - thin lighter crack lines radiating outward
    # BEYOND the scorch, showing the blast wave cracked the road surface.
    # Drawn under the scorch. Pre-computed jagged segments. ---
    crack_grow = min(1.0, bt / 50.0) if bt < 50 else 1.0
    for segs in getattr(STATE, "mission2_tanker_asphalt_cracks", []):
        if len(segs) < 2:
            continue
        pts = []
        for angle, r, jitter in segs:
            cur_r = r * crack_grow
            px = cx + math.cos(angle) * cur_r + jitter
            py = cy + math.sin(angle) * cur_r + jitter
            pts.append((px - cam_x, py - cam_y))
        # Cull if all points are off-screen.
        if all(p[0] < -40 or p[0] > WIDTH + 40 for p in pts):
            continue
        if all(p[1] < -40 or p[1] > HEIGHT + 40 for p in pts):
            continue
        # Lighter gray cracks on the dark asphalt.
        pygame.draw.lines(surface, (95, 88, 78), False, pts, 2)
        pygame.draw.lines(surface, (130, 120, 105), False, pts, 1)

    # --- Persistent outer debris ring - 60 small charred chunks thrown
    # 340-720px from the blast. Smaller than the inner debris field (they
    # traveled further). Drawn under the scorch so the inner field + scorch
    # dominate near the crater. ---
    for piece in getattr(STATE, "mission2_tanker_outer_debris", []):
        px = int(piece["x"] - cam_x)
        py = int(piece["y"] - cam_y)
        sz = piece["size"]
        if px < -30 or px > WIDTH + 30 or py < -30 or py > HEIGHT + 30:
            continue
        # Smaller, fainter shadow.
        shadow_surf = pygame.Surface((sz * 2, sz), pygame.SRCALPHA)
        render_util.soft_shadow(shadow_surf, (0, 0, sz * 2, sz), 90)
        surface.blit(shadow_surf, (px - sz, py - sz // 2 + 1))
        col = piece["color"]
        pygame.draw.rect(surface, col, (px - sz // 2, py - sz // 2, sz, sz))
        pygame.draw.rect(surface, (max(0, col[0] - 20),
                                    max(0, col[1] - 18),
                                    max(0, col[2] - 16)),
                         (px - sz // 2, py - sz // 2, sz, sz), 1)

    # --- Persistent scorch decal: 520px radius (was 350), irregular oily
    # layers, radial cracks, scattered fuel-splatter patches. Drawn forever
    # after the blast. Grows in over 40 frames. Pre-computed crack lengths
    # stored on STATE so they don't jitter every frame. ---
    scorch = getattr(STATE, "mission2_tanker_scorch", None)
    if scorch:
        sx, sy, sr = scorch
        grow = min(1.0, bt / 40.0) if bt < 40 else 1.0
        r = int(sr * grow)
        # T7: once fully grown the decal is static - blit the baked sprite
        # (same placement as below) instead of rebuilding a ~1450x1080
        # surface and rescaling it every frame. Grow-in stays procedural.
        if grow >= 1.0 and sr == 520 and artpack.blit_frame(
                surface, "spr_fx_scorch", "scorch", (int(sx), int(sy) + 15)):
            r = 0
        if r > 4:
            scorch_surf = pygame.Surface((r * 2 + 40, r * 2 + 40), pygame.SRCALPHA)
            # Layered ellipses for an irregular, oily look. Extra layers
            # (was 4) so the scorch has a deeper, more charred center.
            for off, alpha, col in [
                (0,   220, (8, 6, 5)),
                (16,  180, (18, 14, 11)),
                (34,  140, (32, 24, 18)),
                (56,  100, (55, 40, 32)),
                (82,  65,  (82, 62, 48)),
                (110, 40,  (110, 88, 68)),
            ]:
                rr = max(2, r - off)
                pygame.draw.circle(scorch_surf, (*col, alpha),
                                   (r + 20, r + 20), rr)
            # Radial cracks - pre-computed, 12 jagged lines (was 8) radiating
            # out from the crater. Stored on STATE at blast time so the
            # crack lengths don't jitter every frame.
            for ang, end_r in getattr(STATE, "mission2_tanker_scorch_cracks", []):
                x1 = r + 20 + math.cos(ang) * (r - 30)
                y1 = r + 20 + math.sin(ang) * (r - 30)
                x2 = r + 20 + math.cos(ang) * (r + end_r)
                y2 = r + 20 + math.sin(ang) * (r + end_r)
                pygame.draw.line(scorch_surf, (15, 10, 8, 200),
                                 (x1, y1), (x2, y2), 4)
                pygame.draw.line(scorch_surf, (40, 30, 22, 120),
                                 (x1, y1), (x2, y2), 2)
            # Horizontal stretch - fuel splashes wider than tall.
            scorch_surf = pygame.transform.scale(
                scorch_surf, (int(scorch_surf.get_width() * 1.35),
                              scorch_surf.get_height())
            )
            sw, sh = scorch_surf.get_size()
            surface.blit(scorch_surf,
                         (int(sx - sw // 2), int(sy - sh // 2 + 15)))

    # --- Permanent scattered debris field. ~70 small charred metal chunks
    # stamped in a ring around the crater when the tanker exploded. Drawn
    # forever after the blast so the aftermath keeps reading as "something
    # exploded here" instead of just a scorch mark + campfires. ---
    for piece in getattr(STATE, "mission2_tanker_debris_field", []):
        px = int(piece["x"] - cam_x)
        py = int(piece["y"] - cam_y)
        sz = piece["size"]
        # Cull off-screen pieces for perf.
        if px < -40 or px > WIDTH + 40 or py < -40 or py > HEIGHT + 40:
            continue
        # Drop shadow under the chunk - grounds it.
        shadow_surf = pygame.Surface((sz * 3, sz * 2), pygame.SRCALPHA)
        render_util.soft_shadow(shadow_surf, (0, 0, sz * 3, sz * 2), 110)
        surface.blit(shadow_surf, (px - sz * 3 // 2, py - sz // 2 + 1))
        # The chunk itself - small rect, slightly darker outline.
        col = piece["color"]
        pygame.draw.rect(surface, col,
                         (px - sz // 2, py - sz // 2, sz, sz))
        pygame.draw.rect(surface, (max(0, col[0] - 25),
                                    max(0, col[1] - 22),
                                    max(0, col[2] - 20)),
                         (px - sz // 2, py - sz // 2, sz, sz), 1)
        # Tiny edge highlight on a few pieces - fake specular so they
        # read as 3D metal, not flat squares.
        if sz >= 6:
            pygame.draw.line(surface, (140, 130, 120),
                             (px - sz // 2 + 1, py - sz // 2 + 1),
                             (px - sz // 2 + 1, py + sz // 2 - 1), 1)

    # --- Persistent outer spot fires - ~12 small glowing fire patches
    # 250-600px from the crater (embers that landed and ignited secondary
    # blazes). Drawn as flickering glowing patches on the ground; particles
    # are emitted separately in the update loop. These keep the wider scene
    # burning forever, not just the crater. ---
    for sf in getattr(STATE, "mission2_tanker_spot_fires", []):
        px = int(sf["x"] - cam_x)
        py = int(sf["y"] - cam_y)
        sz = sf["size"]
        if px < -60 or px > WIDTH + 60 or py < -60 or py > HEIGHT + 60:
            continue
        # Flicker - each spot fire pulses on its own phase.
        flicker = 0.65 + 0.35 * math.sin(bt * 0.25 + sf["phase"])
        # T7: nearest baked size x flicker level (patch + 4 glow rings).
        if artpack.blit_frame(surface, "spr_fx_m2", "spot_%d_%d" % (
                min((14, 18, 22, 26), key=lambda s: abs(s - sz)),
                min(range(4), key=lambda i: abs((0.65, 0.78, 0.9, 1.0)[i] - flicker))),
                (px, py)):
            continue
        # Scorched patch under the fire.
        scorch_patch = pygame.Surface((sz * 3, sz * 2), pygame.SRCALPHA)
        pygame.draw.ellipse(scorch_patch, (10, 7, 5, 160),
                            (0, 0, sz * 3, sz * 2))
        surface.blit(scorch_patch, (px - sz * 3 // 2, py - sz))
        # Layered glow - orange outer, yellow mid, white-hot core.
        for r, col, alpha_mul in [
            (sz,        (255, 90, 25),  0.45),
            (int(sz * 0.65), (255, 150, 45), 0.65),
            (int(sz * 0.4),  (255, 210, 110), 0.85),
            (int(sz * 0.2),  (255, 250, 200), 1.0),
        ]:
            if r > 0:
                glow = pygame.Surface((r * 2 + 4, r * 2 + 4), pygame.SRCALPHA)
                pygame.draw.circle(glow, (*col, int(220 * flicker * alpha_mul)),
                                   (r + 2, r + 2), r)
                surface.blit(glow, (px - r - 2, py - r - 2))

    # --- Smoking wreckage: blackened tanker hull. Drawn IN PLACE of the
    # pristine tanker after the blast. Bigger footprint (1.4x, was 1.0x),
    # pre-computed rib positions (no per-frame jitter), more ribs (8, was
    # 5), and persistent glowing fissures across the hull so it keeps
    # reading as "still smoldering" forever. The tanker sprite itself is
    # gated on `mission2_tanker_destroyed` in _draw_tanker. ---
    if (getattr(STATE, "mission2_tanker_destroyed", False) and (tanker.w, tanker.h) == (308, 176)
            and artpack.blit_frame(surface, "spr_fx_m2", "wreck_hull", (scx, scy + 14))):
        # T7 sprite path: baked hull + nearest fissure / core glow level.
        f_alpha = (110 if bt > 400 else 170) * (0.55 + 0.45 * math.sin(bt * 0.18))
        artpack.blit_frame(surface, "spr_fx_m2", "wreck_fissure_%d" % min(
            (50, 90, 130, 170), key=lambda a: abs(a - f_alpha)), (scx, scy + 14))
        if bt < 400 or bt % 30 < 15:
            g_alpha = 80 if bt > 400 else int(150 * max(0.0, 1.0 - bt / 400.0))
            if g_alpha >= 20:
                artpack.blit_frame(surface, "spr_fx_m2", "wreck_core_%d" % min(
                    (40, 80, 115, 150), key=lambda a: abs(a - g_alpha)), (scx, scy + 14))
    elif getattr(STATE, "mission2_tanker_destroyed", False):
        # Bigger footprint so the wreckage spills beyond the original
        # tanker rect - a real blast doesn't leave a neatly-shaped hull.
        wreck_w = tanker.w + 80
        wreck_h = tanker.h + 80
        wreck = pygame.Surface((wreck_w, wreck_h), pygame.SRCALPHA)
        wx, wy = wreck.get_size()
        # Outer charred shadow - wider than the hull, sells the impact.
        render_util.soft_shadow(wreck, (-10, 18, wx + 20, wy - 6), 160)
        # Blackened hull blob - irregular, charred. Two layers (was 2)
        # but bigger and darker.
        pygame.draw.ellipse(wreck, (12, 9, 8), (0, 12, wx, wy - 12))
        pygame.draw.ellipse(wreck, (28, 22, 18), (12, 18, wx - 24, wy - 30))
        pygame.draw.ellipse(wreck, (45, 36, 28), (24, 24, wx - 48, wy - 48))
        # Twisted metal ribs sticking up - pre-computed, 8 (was 5), no
        # per-frame jitter.
        ribs = getattr(STATE, "mission2_tanker_wreckage_ribs", [])
        for i, (rx_off, ry_top) in enumerate(ribs):
            rx = 24 + i * (wx - 48) // max(1, len(ribs) - 1) + rx_off
            pygame.draw.line(wreck, (55, 46, 38),
                             (rx, wy - 14), (rx, ry_top), 3)
            pygame.draw.line(wreck, (80, 70, 60),
                             (rx, wy - 14), (rx, ry_top), 1)
        # Persistent glowing fissures - jagged hot lines across the hull
        # that keep flickering forever. This is what was missing: after
        # the fireball fades, the wreckage itself should still look hot.
        # Deterministic seed from the wreck center so the fissures don't
        # jitter either.
        fissure_seed = int(cx * 31 + cy * 17)
        rng = random.Random(fissure_seed)
        for _ in range(5):
            fx_start = rng.randint(20, wx - 20)
            fy_start = rng.randint(20, wy - 20)
            # 3-4 segment jagged line.
            seg_count = rng.randint(3, 4)
            pts = [(fx_start, fy_start)]
            for _seg in range(seg_count):
                pts.append((pts[-1][0] + rng.randint(-25, 25),
                            pts[-1][1] + rng.randint(-15, 15)))
            # Pulse the fissure glow - slow flicker, always visible.
            pulse = 0.55 + 0.45 * math.sin(bt * 0.18 + fx_start * 0.07)
            fissure_alpha = int(110 * pulse) if bt > 400 else int(170 * pulse)
            if fissure_alpha > 0:
                for seg in range(len(pts) - 1):
                    # Hot orange outer glow.
                    pygame.draw.line(wreck, (255, 100, 30, fissure_alpha),
                                     pts[seg], pts[seg + 1], 5)
                    # Brighter yellow-white core.
                    pygame.draw.line(wreck, (255, 200, 100, min(255, fissure_alpha + 40)),
                                     pts[seg], pts[seg + 1], 2)
        # Persistent glow at the base - still smoldering. Bigger radii
        # (was 40/25/12) and the flicker keeps going forever.
        if bt < 400 or bt % 30 < 15:
            glow_alpha = 80 if bt > 400 else int(150 * max(0.0, 1.0 - bt / 400.0))
            for r, col in [(70, (255, 90, 25)), (45, (255, 140, 45)), (25, (255, 200, 90)), (12, (255, 240, 180))]:
                pygame.draw.circle(wreck, (*col, glow_alpha),
                                   (wx // 2, wy - 12), r)
        surface.blit(wreck, (scx - wx // 2, scy - wy // 2 + 14))

    # Active blast fireball - only during STAGE_BLACKOUT.
    if STATE.mission2_stage != STAGE_BLACKOUT:
        return

    # --- Ground glow: wider, hotter, pulses with the fireball. 600px wide. ---
    if bt < 250:
        glow_w = 600
        glow_h = 180
        glow = pygame.Surface((glow_w, glow_h), pygame.SRCALPHA)
        pulse = 0.85 + 0.15 * math.sin(bt * 0.4)
        for i, (alpha, col) in enumerate([
            (int(140 * pulse), (255, 90, 30)),
            (int(100 * pulse), (255, 140, 50)),
            (int(70 * pulse),  (255, 200, 90)),
            (int(40 * pulse),  (255, 240, 180)),
        ]):
            rect = pygame.Rect(0, 0, glow_w - i * 80, glow_h - i * 25)
            rect.center = (glow_w // 2, glow_h // 2)
            pygame.draw.ellipse(glow, (*col, alpha), rect)
        surface.blit(glow, (scx - glow_w // 2, scy - glow_h // 2 + 25))

    # --- Fireball core: 700px radius, 4-layer (halo / mid / core / white
    # center). Color ramps white-hot -> yellow -> orange -> red over 110 frames.
    # Burns visibly for 250 frames (~4s). ---
    fb_r = getattr(STATE, "mission2_tanker_fireball_radius", 0)
    if fb_r > 0 and bt < 250:
        cool = min(1.0, bt / 90.0)
        if cool < 0.15:
            core_col = (255, 255, 245)
        elif cool < 0.35:
            t = (cool - 0.15) / 0.20
            core_col = (255, int(255 - 40 * t), int(245 - 110 * t))
        elif cool < 0.65:
            t = (cool - 0.35) / 0.30
            core_col = (255, int(215 - 80 * t), int(135 - 95 * t))
        elif cool < 0.90:
            t = (cool - 0.65) / 0.25
            core_col = (255, int(135 - 70 * t), int(40 - 25 * t))
        else:
            core_col = (180, 60, 25)
        # Alpha fades in the last 60 frames.
        if bt < 190:
            alpha = 240
        else:
            alpha = int(240 * max(0.0, 1.0 - (bt - 190) / 60.0))
        if alpha > 0:
            fb_surf = pygame.Surface((fb_r * 2 + 40, fb_r * 2 + 40), pygame.SRCALPHA)
            # Outer halo - wide and soft.
            pygame.draw.circle(fb_surf, (*core_col, alpha // 4),
                               (fb_r + 20, fb_r + 20), fb_r + 15)
            # Mid layer
            pygame.draw.circle(fb_surf, (*core_col, alpha // 2),
                               (fb_r + 20, fb_r + 20), int(fb_r * 0.78))
            # Hot core
            pygame.draw.circle(fb_surf, (*core_col, alpha),
                               (fb_r + 20, fb_r + 20), int(fb_r * 0.50))
            # White-hot inner
            if cool < 0.6:
                pygame.draw.circle(fb_surf, (255, 255, 250, alpha),
                                   (fb_r + 20, fb_r + 20), int(fb_r * 0.28))
            # Blinding center for the first 60 frames
            if cool < 0.35:
                pygame.draw.circle(fb_surf, (255, 255, 255, alpha),
                                   (fb_r + 20, fb_r + 20), int(fb_r * 0.14))
            surface.blit(fb_surf, (scx - fb_r - 20, scy - fb_r - 20))

    # --- Roiling fire column: 40 fireballs (was 24), taller (450px, was
    # 320), burns for 350 frames (~5.8s, was 200). This is the rising
    # fireball that feeds the mushroom cap. ---
    if bt < 350:
        burn = max(0.0, 1.0 - bt / 350.0)
        plume_w = 320
        plume_h = 450
        plume = pygame.Surface((plume_w, plume_h), pygame.SRCALPHA)
        base_x = plume_w // 2
        base_y = plume_h - 30
        for i in range(40):
            frac = i / 39.0
            phase = bt * (0.052 + frac * 0.018) + i * 1.73
            spread = 18 + frac * 70
            ox = math.sin(phase) * spread + math.sin(phase * 0.41) * 10
            oy = (frac * 360 + math.sin(phase * 0.8) * 10)
            rr = max(4, int(26 - frac * 9 + math.sin(phase) * 3))
            heat = max(0.0, 1.0 - frac * 0.82)
            alpha = int((210 * burn) * (1.0 - frac * 0.25))
            if alpha <= 0:
                continue
            col = (
                255,
                int(95 + 130 * heat),
                int(28 + 80 * heat),
                max(0, min(255, alpha)),
            )
            pos = (int(base_x + ox), int(base_y - oy))
            pygame.draw.circle(plume, col, pos, rr)
            if i < 12 and bt < 100:
                pygame.draw.circle(
                    plume,
                    (255, 245, 200, int(130 * max(0.0, 1.0 - bt / 110.0))),
                    pos, max(2, rr // 2)
                )
        surface.blit(plume, (scx - plume_w // 2, scy - plume_h + 40))

    # --- Mushroom cap: MASSIVE. 1200px wide (was 400), rises 600px,
    # forms after 50 frames and billows for 500 frames (~8s). This is
    # the iconic "nuke cloud" shape that sells the scale. ---
    if 50 < bt < 550:
        cap_age = min(1.0, (bt - 50) / 200.0)
        cap_w = int(280 + cap_age * 320)   # up to 600 (half-width -> 1200 diameter)
        cap_h = int(120 + cap_age * 100)
        cap = pygame.Surface((cap_w * 2, cap_h * 2), pygame.SRCALPHA)
        # 16 overlapping dark ellipses for a rolling billowing cloud.
        for i in range(16):
            phase = bt * 0.018 + i * 0.7
            ox = math.sin(phase) * cap_w * 0.35 + (i - 8) * cap_w * 0.06
            oy = math.cos(phase * 1.3) * cap_h * 0.18 + math.sin(phase * 0.7) * 8
            r = int(cap_w * (0.45 - i * 0.018))
            shade = 22 + i * 3
            alpha = max(0, int(160 - i * 7 - cap_age * 25))
            if r > 2 and alpha > 0:
                pygame.draw.circle(
                    cap,
                    (shade, shade - 4, shade - 2, alpha),
                    (cap_w + int(ox), cap_h + int(oy)),
                    r
                )
        # Hot orange underbelly on the cap - the fireball glowing through.
        if bt < 200:
            under_alpha = int(100 * max(0.0, 1.0 - bt / 200.0))
            pygame.draw.ellipse(cap, (255, 120, 40, under_alpha),
                                (cap_w - 100, cap_h - 20, 200, 60))
        surface.blit(cap, (scx - cap_w, scy - cap_h - 280))

    # --- BLEVE pops: 5 timed secondaries (was 3), each bigger. ---
    for pop_t, pop_off in [(15, (-80, 10)), (30, (70, 20)), (50, (-30, -30)),
                            (75, (90, -10)), (105, (-100, 30))]:
        dt = bt - pop_t
        if 0 <= dt < 30:
            pop_alpha = int(200 * (1.0 - dt / 30.0))
            pop_r = int(30 + dt * 6)
            px = scx + pop_off[0]
            py = scy + pop_off[1]
            pop_surf = pygame.Surface((pop_r * 2 + 12, pop_r * 2 + 12), pygame.SRCALPHA)
            pygame.draw.circle(pop_surf, (255, 230, 170, pop_alpha),
                               (pop_r + 6, pop_r + 6), pop_r)
            pygame.draw.circle(pop_surf, (255, 140, 50, pop_alpha),
                               (pop_r + 6, pop_r + 6), int(pop_r * 0.65))
            pygame.draw.circle(pop_surf, (255, 250, 210, pop_alpha),
                               (pop_r + 6, pop_r + 6), int(pop_r * 0.35))
            pygame.draw.circle(pop_surf, (255, 255, 255, pop_alpha),
                               (pop_r + 6, pop_r + 6), int(pop_r * 0.15))
            surface.blit(pop_surf, (px - pop_r - 6, py - pop_r - 6))

    # --- Heavy debris chunks: 90 of them, bigger, with longer smoke trails
    # and hotter glow. ---
    for chunk in getattr(STATE, "mission2_tanker_debris_chunks", []):
        sx = int(chunk["x"] - cam_x)
        sy = int(chunk["y"] - cam_y)
        sz = chunk["size"]
        # Smoke trail - longer for bigger chunks.
        trail_len = min(12, chunk["age"] // 2)
        for i in range(trail_len):
            tx = sx - int(chunk["dx"] * i * 1.5)
            ty = sy - int(chunk["dy"] * i * 1.5)
            ta = max(0, 90 - i * 10)
            if ta > 0:
                trail_surf = pygame.Surface((sz * 2, sz * 2), pygame.SRCALPHA)
                pygame.draw.circle(trail_surf, (50, 45, 40, ta),
                                   (sz, sz), max(1, sz - i // 2))
                surface.blit(trail_surf, (tx - sz, ty - sz))
        # Glowing edge while still hot.
        hot = max(0.0, 1.0 - chunk["age"] / 60.0)
        if hot > 0.1:
            glow_surf = pygame.Surface((sz * 5, sz * 5), pygame.SRCALPHA)
            pygame.draw.circle(glow_surf, (255, 120, 40, int(140 * hot)),
                               (sz * 2, sz * 2), sz * 2)
            surface.blit(glow_surf, (sx - sz * 2, sy - sz * 2))
        # The chunk itself.
        pygame.draw.rect(surface, chunk["color"],
                         (sx - sz // 2, sy - sz // 2, sz, sz))
        pygame.draw.rect(surface, (140, 130, 120),
                         (sx - sz // 2, sy - sz // 2, sz, sz), 1)


def _draw_blackout_overlay(surface):
    if STATE.mission2_stage != STAGE_BLACKOUT:
        return

    bt = getattr(STATE, "mission2_tanker_blast_timer", 0)
    shock_r = getattr(STATE, "mission2_tanker_shockwave_radius", 0)

    # --- Screen ripple distortion: horizontal wobble for the first 40
    # frames (and briefly on each BLEVE secondary). Drawn by slicing the
    # screen into horizontal strips and offsetting each by a sine wave. ---
    ripple = getattr(STATE, "mission2_tanker_ripple_timer", 0)
    if ripple > 0:
        # Capture the current screen, then re-blit it with horizontal
        # offsets. Cheap and reads as a real shockwave distortion.
        amplitude = ripple * 0.8  # up to 32px wobble at peak
        strip_h = 8
        snapshot = surface.copy()
        surface.fill((0, 0, 0))
        for y in range(0, HEIGHT, strip_h):
            offset = int(math.sin(y * 0.05 + bt * 0.5) * amplitude)
            surface.blit(snapshot, (offset, y), pygame.Rect(0, y, WIDTH, strip_h))

    # --- Shockwave rings: 3 layers (was 2). Fast BLEVE shock (1600px),
    # slower ground shock, and a faint tertiary pressure wave. ---
    if bt <= 50 and shock_r > 0:
        sx = WIDTH // 2
        sy = HEIGHT // 2
        # Fast BLEVE shock - bright, sharp, fades over 25 frames.
        bleve_alpha = max(0, 250 - bt * 10)
        if bleve_alpha > 0:
            ring = pygame.Surface((shock_r * 2 + 40, shock_r * 2 + 40), pygame.SRCALPHA)
            pygame.draw.circle(ring, (255, 245, 210, bleve_alpha),
                               (shock_r + 20, shock_r + 20), shock_r, 6)
            if shock_r > 30:
                pygame.draw.circle(ring, (255, 150, 60, bleve_alpha // 2),
                                   (shock_r + 20, shock_r + 20), shock_r - 22, 4)
            if shock_r > 70:
                pygame.draw.circle(ring, (255, 80, 30, bleve_alpha // 4),
                                   (shock_r + 20, shock_r + 20), shock_r - 50, 2)
            surface.blit(ring, (sx - shock_r - 20, sy - shock_r - 20))

        # Slower ground shock.
        ground_r = int(shock_r * 0.65)
        ground_alpha = max(0, 170 - bt * 3.5)
        if ground_alpha > 0 and ground_r > 20:
            ground = pygame.Surface((ground_r * 2 + 20, ground_r * 2 + 20), pygame.SRCALPHA)
            pygame.draw.circle(ground, (200, 180, 160, ground_alpha),
                               (ground_r + 10, ground_r + 10), ground_r, 3)
            surface.blit(ground, (sx - ground_r - 10, sy - ground_r - 10))

        # Faint tertiary pressure wave - widest, softest.
        tert_r = int(shock_r * 1.3)
        tert_alpha = max(0, 80 - bt * 1.5)
        if tert_alpha > 0 and tert_r > 50:
            tert = pygame.Surface((tert_r * 2 + 20, tert_r * 2 + 20), pygame.SRCALPHA)
            pygame.draw.circle(tert, (180, 170, 150, tert_alpha),
                               (tert_r + 10, tert_r + 10), tert_r, 1)
            surface.blit(tert, (sx - tert_r - 10, sy - tert_r - 10))

    # --- Dimming overlay: comes in MUCH slower so the player sees the
    # fireball rise. Full dim by frame 180 (was 130), floor at 160 (was 95).
    # The fire glow from _draw_tanker_blast_fx stays visible through the dim. ---
    fade = min(160, 160 - max(0, STATE.mission2_timer - 180))
    overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
    overlay.fill((0, 0, 0, max(80, fade)))
    surface.blit(overlay, (0, 0))

    # --- Vasile's cut-off line + COMMS LOST. COMMS LOST now appears at
    # frame 180 (was 130) so it doesn't punch in while the fireball is
    # still on screen. Flickers for a damaged-radio feel. ---
    if 60 < STATE.mission2_timer < 160:
        txt = font_dialogue.render(_T("m2.vasile_biribel_the_file_said_the"), True, C_VASILE)
        surface.blit(txt, (WIDTH // 2 - txt.get_width() // 2, HEIGHT // 2 - 52))
    if STATE.mission2_timer > 180:
        if (STATE.mission2_timer // 4) % 3 != 0:
            txt = font_speaker.render(_T("m2.comms_lost"), True, (160, 165, 175))
            surface.blit(txt, (WIDTH // 2 - txt.get_width() // 2, HEIGHT // 2 - 10))


# ── Static bake + lighting fixtures (Mission 3 pipeline, Mission 2 wiring) ──
# Route 12 re-rendered its whole tile grid, walls and shelter/garden every
# frame. The static half (tiles, lane paint, walls, gantry structure,
# shelter, garden base, dressing) is baked into chunked offscreen surfaces
# once; only animated state (vehicles, tanker, props, actors, weather)
# draws live.
_M2_CAM = [0, 0]
_M2_SOLID_TILES = ("C", "B", "T")
_M2_WALL_TILES = None
_M2_WALL_TILES_SIG = None


def _m2_walls_sig():
    walls = STATE.walls
    return (len(walls), sum(w.x + w.y + w.w + w.h for w in walls))


def _m2_wall_tiles():
    """Cached set of map tiles covered by STATE.walls collision rects."""
    global _M2_WALL_TILES, _M2_WALL_TILES_SIG
    sig = _m2_walls_sig()
    if _M2_WALL_TILES is None or _M2_WALL_TILES_SIG != sig:
        tiles = set()
        for w in STATE.walls:
            for ty in range(w.y // TILE_SIZE, (w.y + w.h - 1) // TILE_SIZE + 1):
                for tx in range(w.x // TILE_SIZE, (w.x + w.w - 1) // TILE_SIZE + 1):
                    tiles.add((tx, ty))
        _M2_WALL_TILES = tiles
        _M2_WALL_TILES_SIG = sig
    return _M2_WALL_TILES


def _m2_static_layer():
    sig = ("m2", id(MISSION2_MAP)) + _m2_walls_sig()
    return staticlayer.get_layer("m2", sig, MAP_W * TILE_SIZE, MAP_H * TILE_SIZE, cap=32)


def _m2_wing_name():
    """Grading zone: rainy highway night, dark blast aftermath, warm control interior."""
    if getattr(STATE, "mission2_stage", "") == STAGE_BLACKOUT:
        return "blackout"
    p = STATE.player
    if p is not None:
        tx = p.rect.centerx // TILE_SIZE
        ty = p.rect.centery // TILE_SIZE
        if 51 <= tx <= 67 and 9 <= ty <= 25:
            return "control"
    return "route12"


def _m2_solid_world(wx, wy):
    """Light-blocking predicate: map structure tiles + wall-rect coverage."""
    tx = int(wx) // TILE_SIZE
    ty = int(wy) // TILE_SIZE
    if 0 <= ty < len(MISSION2_MAP):
        row = MISSION2_MAP[ty]
        if 0 <= tx < len(row) and row[tx] in _M2_SOLID_TILES:
            return True
    return (tx, ty) in _m2_wall_tiles()


def _m2_light_sig():
    return (render_util.doors_anim_sig(getattr(STATE, "doors", ())),) + _m2_walls_sig()


# Lamp fixtures in tile coords: (col, row, radius, color, key). Light
# centers sit on open tiles next to their fixture geometry so the
# shadow-casting visibility masks don't start inside solid geometry.
_M2_LAMPS = (
    # Highway guardrail street lamps - cool white.
    (17, 25, 170, (210, 225, 255), "st_25w"),
    (17, 29, 170, (210, 225, 255), "st_a"),
    (17, 41, 170, (210, 225, 255), "st_41w"),
    (17, 45, 170, (210, 225, 255), "st_b"),
    (17, 53, 170, (210, 225, 255), "st_53w"),
    (17, 61, 170, (210, 225, 255), "st_c"),
    (17, 69, 170, (210, 225, 255), "st_69w"),
    (53, 25, 170, (210, 225, 255), "st_25e"),
    (53, 30, 170, (210, 225, 255), "st_d"),
    (53, 41, 170, (210, 225, 255), "st_41e"),
    (53, 46, 170, (210, 225, 255), "st_e"),
    (53, 54, 170, (210, 225, 255), "st_54e"),
    (53, 62, 170, (210, 225, 255), "st_f"),
    (53, 70, 170, (210, 225, 255), "st_70e"),
    # South insertion-shoulder poles near the start.
    (12, 70, 150, (210, 225, 255), "st_g"),
    (22, 68, 150, (210, 225, 255), "st_h"),
    # Toll plaza floods - warm sodium.
    (27, 34, 180, (255, 230, 180), "toll_a"),
    (47, 34, 180, (255, 230, 180), "toll_b"),
    # Control-building window spill (south face).
    (55, 26, 120, (255, 236, 190), "win_a"),
    (60, 26, 120, (255, 236, 190), "win_b"),
    (64, 26, 120, (255, 236, 190), "win_c"),
    # Upload terminal phosphor + security hut.
    (62, 16, 110, (150, 255, 180), "term"),
    (45, 21, 120, (255, 236, 190), "hut"),
    # Tanker worklight - only while the tanker is on the map.
    (46, 42, 170, (255, 200, 120), "tnk"),
    # Shelter floodlight + garden lanterns.
    (28, 46, 150, (220, 230, 255), "shl"),
    (55, 4, 110, (255, 230, 170), "grd_a"),
    (62, 5, 110, (255, 230, 170), "grd_b"),
    # Sniper-nest glint - only during the sniper stage.
    (58, 26, 70, (255, 60, 40), "nest"),
    # IPA truck parking pool.
    (48, 32, 120, (255, 230, 170), "trk"),
)


def _m2_lamp_visible(key):
    if key == "tnk":
        return getattr(STATE, "mission2_tanker_rect", None) in STATE.walls
    if key == "nest":
        return (getattr(STATE, "mission2_stage", "") == STAGE_SNIPER
                and not getattr(STATE, "mission2_sniper_suppressed", False))
    return True


def _push_m2_lights(cam_x, cam_y, t):
    lb = lighting.buffer()
    render_util.push_lamps(
        lb,
        ((tx * TILE_SIZE, ty * TILE_SIZE, r, col, key)
         for tx, ty, r, col, key in _M2_LAMPS),
        cam_x, cam_y, t, _m2_solid_world, key_filter=_m2_lamp_visible)
    # IPA truck headlights - motivated cone east down the road.
    hx = 49 * TILE_SIZE + 32 - cam_x
    hy = 32 * TILE_SIZE + 32 - cam_y
    if render_util.screen_visible(hx - 230, hy - 120, 460, 240):
        lb.cone(hx - 100, hy, math.radians(0), 22, 230, (255, 230, 170), 0.32,
                caster=_m2_solid_world, cam=(cam_x, cam_y), key="truckbeam")
    # Night-sky ambient: a faint cool wash following the camera so unlit
    # stretches stay readable. No caster - it is the sky, not a fixture.
    lb.light(WIDTH // 2, HEIGHT // 2, 750, (150, 170, 210), 0.09)


# ── Deterministic per-tile noise ────────────────────────────────────────
# Deliberately NOT ``row * 97 + col * 131``.  That expression is *linear* in
# (row, col), so every ``seed % k`` predicate derived from it fires on a
# perfect diagonal lattice: the highway wear decals marched down the road in
# repeating stripes and the service-road ruts landed on a regular 3-tile
# beat.  Uncorrelated per-tile noise is the whole point here, so hash the
# coordinates.
def _tile_hash(col, row, salt=0):
    h = (col * 73856093) ^ (row * 19349663) ^ (salt * 83492791)
    h = (h ^ (h >> 13)) * 1274126177
    return (h ^ (h >> 16)) & 0x7FFFFFFF


def _draw_m2_barrier_unit(target, sx, sy, col, row):
    """One modular jersey barrier standing on the terrain at (sx, sy).

    Modular units are correct here - real jersey barriers are separate
    castings with visible joints - so unlike the building walls these stay
    per-tile.  What they must not do is sit on a 64px slab of their own base
    colour, which is why the caller lays the neighbouring ground down first.
    """
    seed = _tile_hash(col, row, 21)
    # Ground contact: the casting is heavy, so it crushes a shadow under
    # itself before anything else is drawn.
    render_util.soft_shadow(target, (sx + 2, sy + 48, TILE_SIZE - 4, 22), 110)
    crown_l, crown_r = sx + 9, sx + 54
    base_l, base_r = sx + 2, sx + 61
    top_y, bot_y = sy + 17, sy + 61
    for yy in range(top_y, bot_y + 1):
        t = (yy - top_y) / float(bot_y - top_y)
        lx = int(crown_l + (base_l - crown_l) * t)
        rx = int(crown_r + (base_r - crown_r) * t)
        v = int(60 + 34 * t)          # the flared base catches more light
        pygame.draw.line(target, (v, v, v - 5), (lx, yy), (rx, yy))
    # Crown cap: the one lit edge, and the only part that reads as "top".
    # Kept well under the concrete's real albedo - at full brightness a field
    # of these turned the highway into a scatter of white blobs and stole
    # attention from the road itself.
    pygame.draw.rect(target, (98, 96, 88), (crown_l - 1, sy + 11, crown_r - crown_l + 2, 6))
    pygame.draw.line(target, (124, 122, 112), (crown_l - 1, sy + 11), (crown_r, sy + 11), 1)
    pygame.draw.line(target, (44, 44, 40), (crown_l - 1, sy + 16), (crown_r, sy + 16), 1)
    pygame.draw.polygon(target, (30, 30, 28), [
        (crown_l - 1, sy + 11), (crown_r + 1, sy + 11),
        (base_r + 1, bot_y), (base_l - 1, bot_y)], 1)
    if seed % 5 == 0:
        pygame.draw.line(target, (58, 55, 48), (sx + 16, sy + 24), (sx + 30, sy + 40), 1)
    if seed % 7 == 0:
        pygame.draw.ellipse(target, (62, 60, 52), (sx + 34, sy + 30, 12, 8))
    pygame.draw.circle(target, (170, 58, 48) if (row % 2) else (188, 188, 178),
                       (sx + 32, sy + 20), 2)


_DROP_SHADOW_CACHE = {}


def _m2_drop_shadow(target, sx, sy, w, h, alpha=80):
    """Linear falloff band, cached by size.

    A per-tile ellipse shadow tiles into a row of separate dark blobs - the
    wall looks like it is standing in puddles.  A band with a smooth vertical
    falloff merges across a run into one continuous shadow, and there are
    only a handful of distinct sizes so one surface each is enough.
    """
    w, h = int(w), int(h)
    if w <= 0 or h <= 0:
        return
    key = (w, h, alpha)
    band = _DROP_SHADOW_CACHE.get(key)
    if band is None:
        band = pygame.Surface((w, h), pygame.SRCALPHA)
        for i in range(h):
            a = int(alpha * (1 - i / float(h)) ** 1.5)
            pygame.draw.line(band, (0, 0, 0, a), (0, i), (w, i))
        _DROP_SHADOW_CACHE[key] = band
    target.blit(band, (int(sx), int(sy)))


# Single-slab asphalt ground.  The slab keeps its original (34,36,37) base
# colour - detail is fine grain only (per-pixel hash noise, sparse 1px
# aggregate speckle, a few soft large-scale tonal breaths), no motifs, no
# shapes, nothing that reads at tile scale.
_M2_GROUND_SURFACE = None


def _m2_ground_surface():
    global _M2_GROUND_SURFACE
    if _M2_GROUND_SURFACE is None:
        base = (34, 36, 37)
        surf = pygame.Surface((TILE_SIZE, TILE_SIZE))
        surf.fill(base)
        for y in range(TILE_SIZE):
            for x in range(TILE_SIZE):
                delta = (_tile_hash(x, y, 47) % 9) - 4
                if _tile_hash(x, y, 53) % 19 == 0:
                    delta -= 1
                surf.set_at((x, y), tuple(max(0, min(255, c + delta)) for c in base))
        rnd = random.Random(1202)
        for _ in range(22):
            x, y = rnd.randrange(TILE_SIZE), rnd.randrange(TILE_SIZE)
            if rnd.random() < 0.65:
                color = (28, 30, 31)
            else:
                color = (46, 49, 50)
            pygame.draw.rect(surf, color,
                             (x, y, 1 if rnd.random() < 0.8 else 2, 1))
        # Extra fine aggregate: 1px dots at barely-there contrast so the
        # slab has tooth up close but stays the same colour at play distance.
        for _ in range(48):
            x, y = rnd.randrange(TILE_SIZE), rnd.randrange(TILE_SIZE)
            d = 2 if rnd.random() < 0.5 else -2
            surf.set_at((x, y), tuple(max(0, min(255, c + d)) for c in base))
        _M2_GROUND_SURFACE = surf
    return _M2_GROUND_SURFACE


# Road-wear helpers were removed - asphalt stays a clean uniform slab.


def _render_m2_bg(target, cam_x, cam_y):
    """Static tilemap pass with uniform ground tiles and lane paint."""
    start_col = max(0, int(cam_x // TILE_SIZE) - 1)
    end_col = min(MAP_W, int((cam_x + WIDTH) // TILE_SIZE) + 2)
    start_row = max(0, int(cam_y // TILE_SIZE) - 1)
    end_row = min(MAP_H, int((cam_y + HEIGHT) // TILE_SIZE) + 2)

    tile_base = {
        "C": (54, 54, 52),
        "B": (82, 82, 76),
    }
    for row in range(start_row, end_row):
        for col in range(start_col, end_col):
            sx, sy = col * TILE_SIZE - cam_x, row * TILE_SIZE - cam_y
            tile = MISSION2_MAP[row][col]
            if tile in ".gOdsXTP":
                target.blit(_m2_ground_surface(), (sx, sy))
                continue
            if tile == "B":
                target.blit(_m2_ground_surface(), (sx, sy))
                _draw_m2_barrier_unit(target, sx, sy, col, row)
                continue
            base = tile_base.get(tile, (31, 32, 32))
            pygame.draw.rect(target, base, (sx, sy, TILE_SIZE, TILE_SIZE))

    # Vertical lane stripes for the expanded Route 12 corridor.
    for xcol in (28, 36, 44):
        x = xcol * TILE_SIZE + TILE_SIZE // 2 - cam_x
        for y in range(-int(cam_y) % 150 - 150, HEIGHT + 150, 150):
            pygame.draw.rect(target, (145, 130, 60), (x, y, 5, 72))


# Structure-wall palette.  M2's walls are drawn from STATE.walls rects rather
# than from map tiles, so the colours live here rather than in the art pack.
_WALL_BODY = (72, 70, 64)
_WALL_MOTTLE = (62, 60, 55)
_WALL_LIT = (98, 95, 87)
_WALL_CAP = (112, 109, 100)
_WALL_CAP_LIT = (152, 149, 138)
_WALL_SEAM = (52, 50, 47)
_WALL_BASE = (40, 39, 36)
_WALL_CAP_H = 12


def _m2_structure_tiles():
    """Tile set covered by non-barrier, non-tanker wall rects."""
    barrier_ids = {id(r) for r in STATE.mission2_barriers}
    tiles = set()
    for wall in STATE.walls:
        if wall is STATE.mission2_tanker_rect or id(wall) in barrier_ids:
            continue
        for ty in range(wall.y // TILE_SIZE, (wall.y + wall.h - 1) // TILE_SIZE + 1):
            for tx in range(wall.x // TILE_SIZE, (wall.x + wall.w - 1) // TILE_SIZE + 1):
                tiles.add((tx, ty))
    return tiles


def _draw_m2_walls(target, cam_x, cam_y):
    """Structure walls as connected geometry (the tanker body draws live).

    This used to be one filled rect plus a 2px light outline per wall rect,
    which is exactly why the control building read as a heap of loose
    crates: a 17-tile facade came out as seventeen separately outlined
    boxes, and every tile in a vertical run grew its own bright cap stripe,
    so a wall looked like a stack of slabs.  Walls are drawn edge-aware
    instead - one unbroken body, a lit cap only where the run's top edge is
    actually exposed, side highlights only on exposed flanks, and contact AO
    plus a drop shadow where the run meets open ground.
    """
    struct = _m2_structure_tiles()
    for tx, ty in sorted(struct):
        sx, sy = tx * TILE_SIZE - cam_x, ty * TILE_SIZE - cam_y
        if not render_util.screen_visible(sx, sy, TILE_SIZE, TILE_SIZE):
            continue
        up = (tx, ty - 1) in struct
        down = (tx, ty + 1) in struct
        left = (tx - 1, ty) in struct
        right = (tx + 1, ty) in struct

        pygame.draw.rect(target, _WALL_BODY, (sx, sy, TILE_SIZE, TILE_SIZE))
        # Faint mottle so long unbroken faces do not read as flat plastic.
        m = _tile_hash(tx, ty, 11)
        if m % 3 == 0:
            pygame.draw.ellipse(target, _WALL_MOTTLE,
                                (sx + 8 + m % 24, sy + 18 + m % 28, 22, 14))
        if up:
            # Inside a run: a construction joint, never a cap.
            pygame.draw.line(target, _WALL_SEAM,
                             (sx + 1, sy), (sx + TILE_SIZE - 2, sy), 1)
        if left:
            pygame.draw.line(target, _WALL_SEAM,
                             (sx, sy), (sx, sy + TILE_SIZE - 1), 1)
        else:
            pygame.draw.line(target, _WALL_LIT,
                             (sx, sy), (sx, sy + TILE_SIZE - 1), 2)
        if not right:
            pygame.draw.line(target, _WALL_BASE, (sx + TILE_SIZE - 1, sy),
                             (sx + TILE_SIZE - 1, sy + TILE_SIZE - 1), 2)

        if not up:
            # Exposed top of the run: the only place a cap belongs.
            pygame.draw.rect(target, _WALL_CAP, (sx, sy, TILE_SIZE, _WALL_CAP_H))
            pygame.draw.line(target, _WALL_CAP_LIT,
                             (sx, sy), (sx + TILE_SIZE - 1, sy), 1)
            pygame.draw.line(target, _WALL_SEAM, (sx, sy + _WALL_CAP_H - 1),
                             (sx + TILE_SIZE - 1, sy + _WALL_CAP_H - 1), 1)

        if not down:
            # Foot of the run: the base darkens, then the wall drops a
            # shadow onto the floor.  Clamped to this tile's own column so
            # the shadow can never smear across a neighbouring wall.
            pygame.draw.rect(target, _WALL_BASE,
                             (sx, sy + TILE_SIZE - 5, TILE_SIZE, 5))
            _m2_drop_shadow(target, sx, sy + TILE_SIZE - 4, TILE_SIZE, 24, 96)


def _draw_m2_control_facade(target, cam_x, cam_y):
    bcol, brow, bw, bh = MISSION2_BUILDINGS[0]
    right = bcol + bw - 1
    bottom = brow + bh - 1
    wall_tiles = {
        (tx, ty)
        for ty in range(brow, bottom + 1)
        for tx in range(bcol, right + 1)
        if MISSION2_MAP[ty][tx] == "C"
    }
    bounds = target.get_rect()
    body = (55, 64, 69)
    panel = (69, 80, 84)
    panel_dark = (37, 45, 49)
    cap = (105, 119, 121)
    edge = (126, 145, 145)
    glass = (31, 51, 56)
    lit_glass = (91, 73, 48)
    frame = (91, 117, 121)
    floor = (68, 76, 77)
    floor_seam = (51, 60, 62)
    for ty in range(brow, bottom + 1):
        for tx in range(bcol, right + 1):
            if MISSION2_MAP[ty][tx] != "O":
                continue
            sx, sy = tx * TILE_SIZE - cam_x, ty * TILE_SIZE - cam_y
            rect = pygame.Rect(sx, sy, TILE_SIZE, TILE_SIZE)
            if not rect.colliderect(bounds):
                continue
            pygame.draw.rect(target, floor, rect)
            if tx % 2 == 0:
                pygame.draw.line(target, floor_seam, (sx, sy), (sx, sy + TILE_SIZE - 1), 1)
            if ty % 2 == 0:
                pygame.draw.line(target, floor_seam, (sx, sy), (sx + TILE_SIZE - 1, sy), 1)
            pygame.draw.line(target, (88, 96, 96), (sx + 1, sy + 1), (sx + TILE_SIZE - 2, sy + 1), 1)
    for tx, ty in sorted(wall_tiles):
        sx, sy = tx * TILE_SIZE - cam_x, ty * TILE_SIZE - cam_y
        rect = pygame.Rect(sx, sy, TILE_SIZE, TILE_SIZE)
        if not rect.colliderect(bounds):
            continue
        outer = tx in (bcol, right) or ty in (brow, bottom)
        pygame.draw.rect(target, body if outer else panel_dark, rect)
        pygame.draw.rect(target, panel, (sx + 3, sy + 3, TILE_SIZE - 6, TILE_SIZE - 6), 1)
        pygame.draw.line(target, panel_dark, (sx + 32, sy + 4), (sx + 32, sy + TILE_SIZE - 4), 1)
        if ty == bottom or ty == brow:
            glass_color = lit_glass if ty == bottom and tx in (55, 60, 64) else glass
            pygame.draw.rect(target, glass_color, (sx + 6, sy + 18, 52, 28))
            pygame.draw.rect(target, frame, (sx + 6, sy + 18, 52, 28), 2)
            pygame.draw.line(target, (119, 148, 149), (sx + 32, sy + 20), (sx + 32, sy + 44), 1)
        elif tx == bcol or tx == right:
            if not (tx == bcol and ty == 18):
                pygame.draw.rect(target, glass, (sx + 18, sy + 6, 28, 52))
                pygame.draw.rect(target, frame, (sx + 18, sy + 6, 28, 52), 2)
                pygame.draw.line(target, (119, 148, 149), (sx + 20, sy + 32), (sx + 44, sy + 32), 1)
        if (tx, ty - 1) not in wall_tiles:
            pygame.draw.rect(target, cap, (sx, sy, TILE_SIZE, 7))
            pygame.draw.line(target, edge, (sx, sy), (sx + TILE_SIZE - 1, sy), 1)
        if (tx - 1, ty) not in wall_tiles:
            pygame.draw.line(target, edge, (sx, sy), (sx, sy + TILE_SIZE - 1), 2)
        if (tx + 1, ty) not in wall_tiles:
            pygame.draw.line(target, (24, 30, 32), (sx + TILE_SIZE - 1, sy),
                             (sx + TILE_SIZE - 1, sy + TILE_SIZE - 1), 2)
        if (tx, ty + 1) not in wall_tiles:
            pygame.draw.rect(target, panel_dark, (sx, sy + TILE_SIZE - 5, TILE_SIZE, 5))
            _m2_drop_shadow(target, sx, sy + TILE_SIZE - 3, TILE_SIZE, 18, 90)
    door_x = 57 * TILE_SIZE - cam_x
    door_y = bottom * TILE_SIZE - cam_y
    if pygame.Rect(door_x - 8, door_y + 38, TILE_SIZE * 2 + 16, 46).colliderect(bounds):
        render_util.soft_shadow(target, (door_x + 2, door_y + 52, TILE_SIZE * 2 - 4, 20), 110)
        pygame.draw.rect(target, panel_dark, (door_x - 5, door_y + 46, TILE_SIZE * 2 + 10, 20), border_radius=3)
        pygame.draw.rect(target, cap, (door_x - 5, door_y + 46, TILE_SIZE * 2 + 10, 4), border_radius=2)
        label = font_terminal_small.render(_T("m2.control_04"), True, edge)
        target.blit(label, (door_x + (TILE_SIZE * 2 - label.get_width()) // 2, door_y + 51))
        pygame.draw.rect(target, (89, 99, 98), (door_x + 4, door_y + 40, TILE_SIZE * 2 - 8, 6))
    side_x = bcol * TILE_SIZE - cam_x
    side_y = 18 * TILE_SIZE - cam_y
    if pygame.Rect(side_x - 12, side_y - 4, 80, 72).colliderect(bounds):
        pygame.draw.rect(target, (28, 38, 42), (side_x - 4, side_y + 4, 68, 56), 2)
        pygame.draw.line(target, edge, (side_x - 4, side_y + 4), (side_x + 63, side_y + 4), 2)
        pygame.draw.line(target, edge, (side_x - 4, side_y + 59), (side_x + 63, side_y + 59), 2)


def _m2_prop_overlaps_solid(kind, tx, ty, arg):
    """True when a dressing prop's footprint intersects solid map tiles."""
    rect = _props.footprint_rect(kind, tx, ty, arg, TILE_SIZE)
    if rect is None:
        return False
    # Dressing props draw at the tile CENTRE, but footprint_rect anchors at
    # the tile top-left: shift so the checked rect matches the drawn one.
    rect = rect.move(TILE_SIZE // 2, TILE_SIZE // 2)
    for row in range(rect.top // TILE_SIZE, rect.bottom // TILE_SIZE + 1):
        for col in range(rect.left // TILE_SIZE, rect.right // TILE_SIZE + 1):
            if not (0 <= row < MAP_H and 0 <= col < MAP_W):
                return True
            if MISSION2_MAP[row][col] in _M2_SOLID_TILES:
                return True
            # Geometry also lives in runtime wall rects (shelter crescent,
            # garden hedges/fountain, barriers) - same source _m2_solid_world
            # uses for light blocking.
            if (col, row) in _m2_wall_tiles():
                return True
    return False


def _draw_m2_lamp_post(target, sx, sy, head_col=(210, 225, 255)):
    """Guardrail lamp post: pole, arm, head + halo."""
    halo = get_glow(24, head_col, 90)
    target.blit(halo, (int(sx - 24), int(sy - 52)))
    pygame.draw.rect(target, (25, 27, 30), (int(sx - 2), int(sy - 46), 4, 46))
    pygame.draw.rect(target, (25, 27, 30), (int(sx - 2), int(sy - 50), 16, 4))
    pygame.draw.rect(target, head_col, (int(sx + 10), int(sy - 52), 8, 5))


def _draw_m2_static_dressing(target, cam_x, cam_y):
    """Baked road-dressing pass: edges, stops, posts, cracks, windows, pools."""
    start_col = max(0, int(cam_x // TILE_SIZE) - 1)
    end_col = min(MAP_W, int((cam_x + WIDTH) // TILE_SIZE) + 2)
    start_row = max(0, int(cam_y // TILE_SIZE) - 1)
    end_row = min(MAP_H, int((cam_y + HEIGHT) // TILE_SIZE) + 2)
    for row in range(start_row, end_row):
        map_row = MISSION2_MAP[row]
        for col in range(start_col, end_col):
            tile = map_row[col]
            sx, sy = col * TILE_SIZE - cam_x, row * TILE_SIZE - cam_y
            if tile == ".":
                if col == 17 and (row % 2) == 0:
                    pygame.draw.rect(target, (120, 115, 90),
                                     (int(sx + 2), int(sy + 6), 3, 34))
                if col == 53 and (row % 2) == 1:
                    pygame.draw.rect(target, (120, 115, 90),
                                     (int(sx + TILE_SIZE - 5), int(sy + 24), 3, 34))
            elif tile == "B" and col in (16, 54):
                # Guardrail post + reflector on the barrier tiles.
                pygame.draw.rect(target, (40, 42, 40),
                                 (int(sx + 28), int(sy + 10), 8, 44))
                pygame.draw.rect(target, (90, 90, 86),
                                 (int(sx + 28), int(sy + 10), 8, 44), 1)
                pygame.draw.circle(target, (200, 60, 50) if (row % 2) else (220, 220, 210),
                                   (int(sx + 32), int(sy + 16)), 2)
    # Toll stop bars across the lanes.
    for brow in (31, 36):
        for bcol in range(20, 54):
            if MISSION2_MAP[brow][bcol] != ".":
                continue
            bx = bcol * TILE_SIZE - cam_x
            by = brow * TILE_SIZE + 50 - cam_y
            if render_util.screen_visible(bx, by, TILE_SIZE, 6):
                pygame.draw.rect(target, (150, 145, 120),
                                 (int(bx + 6), int(by), TILE_SIZE - 12, 4))
    # Checkpoint clutter: pallet + drums near the toll booths, plus roadside
    # dressing down both shoulders.  Every entry is validated against the
    # tilemap so nothing lands inside solid geometry, and they all sit on the
    # shoulder bands (cols 18-20 / 51-53) - clear of the centre lane the
    # sniper fight relies on.
    for kind, ptx, pty, arg in (
        ("crates", 26, 35, 0.8), ("barrels", 50, 38, 2),
        # Shoulder dressing.  The north-west verge (cols 2-38, rows 2-22) is
        # outside every zone - the player can walk it, so leaving it as bare
        # ground read as an unfinished map.  Everything here sits off the
        # centre lane (cols 28-44) so the sniper sightline is untouched.
        ("crates", 19, 27, 0.72), ("coil", 18, 40, 1),
        ("barrels", 20, 49, 2), ("mop", 52, 28, 1),
        ("cart", 52, 50, 1), ("crates", 51, 62, 0.85),
        ("barrels", 19, 66, 3), ("coil", 52, 68, 1),
        ("crates", 8, 8, 0.85), ("barrels", 20, 11, 2),
        ("coil", 31, 15, 1), ("crates", 11, 19, 0.72),
        ("mop", 25, 20, 1), ("barrels", 34, 9, 3),
        ("cart", 6, 31, 1), ("crates", 7, 39, 0.85),
        ("coil", 5, 56, 1), ("mop", 9, 63, 1),
        ("crates", 30, 72, 0.72), ("barrels", 41, 73, 2),
        ("cart", 56, 70, 1), ("coil", 61, 60, 1),
        ("crates", 62, 52, 0.85), ("barrels", 46, 20, 2),
        # North-west overflow yard (cols 6-36, rows 3-22) - the block sat
        # outside every zone and rendered as a bare field.  Grouped into the
        # same six kit clusters as the story props so the two passes read as
        # one yard instead of two unrelated scatterings.
        ("crates", 6, 10, 0.85), ("barrels", 9, 12, 3), ("coil", 12, 9, 1),
        ("crates", 19, 17, 0.8), ("barrels", 22, 19, 2), ("mop", 25, 16, 1),
        ("crates", 25, 7, 0.72), ("barrels", 28, 9, 2), ("coil", 32, 6, 1),
        ("crates", 7, 21, 0.85), ("barrels", 12, 20, 2), ("coil", 14, 22, 1),
        ("crates", 29, 13, 0.8), ("barrels", 34, 12, 2), ("cart", 31, 15, 1),
        ("crates", 17, 4, 0.72), ("barrels", 21, 3, 2), ("coil", 24, 5, 1),
        # Thin margins: south edge strip, west edge strip, south-east block.
        ("barrels", 26, 78, 2), ("coil", 42, 78, 1), ("crates", 58, 78, 0.72),
        ("barrels", 1, 34, 2), ("coil", 1, 43, 1), ("crates", 2, 39, 0.72),
        ("crates", 59, 59, 0.85), ("barrels", 63, 61, 3), ("coil", 66, 64, 1),
        ("crates", 61, 71, 0.8), ("barrels", 65, 74, 2), ("mop", 68, 69, 1),
    ):
        if _m2_prop_overlaps_solid(kind, ptx, pty, arg):
            continue
        ax = ptx * TILE_SIZE + TILE_SIZE // 2 - cam_x
        ay = pty * TILE_SIZE + TILE_SIZE // 2 - cam_y
        if not render_util.screen_visible(ax - 60, ay - 60, 120, 120):
            continue
        if kind == "crates":
            _props.crate_stack(target, ax, ay, arg, shadow=False)
        elif kind == "barrels":
            _props.barrels(target, ax, ay, int(arg), shadow=False)
        elif kind == "coil":
            _props.cable_coil(target, ax, ay, shadow=False)
        elif kind == "mop":
            _props.mop_bucket(target, ax, ay, shadow=False)
        elif kind == "cart":
            _props.service_cart(target, ax, ay, shadow=False)
    # Lamp posts at the street-lamp bases + toll floods + shelter mast.
    for ptx, pty, head in ((16, 25, (210, 225, 255)), (16, 29, (210, 225, 255)),
                           (16, 41, (210, 225, 255)), (16, 45, (210, 225, 255)),
                           (16, 53, (210, 225, 255)), (16, 61, (210, 225, 255)),
                           (16, 69, (210, 225, 255)), (54, 25, (210, 225, 255)),
                           (54, 30, (210, 225, 255)), (54, 41, (210, 225, 255)),
                           (54, 46, (210, 225, 255)), (54, 54, (210, 225, 255)),
                           (54, 62, (210, 225, 255)), (54, 70, (210, 225, 255)),
                           (27, 34, (255, 230, 180)), (47, 34, (255, 230, 180)),
                           (28, 46, (220, 230, 255)),
                           (12, 70, (210, 225, 255)), (22, 68, (210, 225, 255))):
        px = ptx * TILE_SIZE + TILE_SIZE // 2 - cam_x
        py = pty * TILE_SIZE + TILE_SIZE // 2 - cam_y
        if render_util.screen_visible(px - 30, py - 60, 60, 110):
            _draw_m2_lamp_post(target, px, py, head)


def _bake_m2_static(surf, ox, oy):
    _render_m2_bg(surf, ox, oy)
    _draw_m2_static_dressing(surf, ox, oy)
    _draw_m2_walls(surf, ox, oy)
    _draw_m2_control_facade(surf, ox, oy)
    _draw_gantry_static(surf, ox, oy)
    _draw_shelter(surf, ox, oy)
    _draw_garden(surf, ox, oy)


def game_draw(fcx: float, fcy: float) -> None:
    cine = getattr(STATE, "mission2_sniper3d", None)
    if cine is not None and STATE.mission2_stage == STAGE_SNIPER:
        try:
            cine.draw(screen)
            return
        except Exception as exc:          # fall back to the 2D view, keep playing
            print(f"[m2] 3D sniper film draw failed: {exc}")
            cine.done = True
    if artpack.enabled():
        lighting.buffer().begin_frame(_m2_wing_name(), _m2_light_sig())
    _game_draw_inner(fcx, fcy)
    if artpack.enabled():
        _push_m2_lights(_M2_CAM[0], _M2_CAM[1], _now_s())
        lighting.buffer().composite(screen, _now_s())


def _game_draw_inner(fcx: float, fcy: float) -> None:
    screen.fill((25, 26, 26))
    # Render from an integer camera.  This removes the tile/prop seam shimmer
    # that happens when the camera scrolls by fractional pixels.
    cam_x, cam_y = int(round(fcx)), int(round(fcy))
    _M2_CAM[0], _M2_CAM[1] = cam_x, cam_y
    if staticlayer.enabled():
        if not _m2art.blit_layer(screen, "world_static", cam_x, cam_y):
            _m2_static_layer().blit(screen, cam_x, cam_y, _bake_m2_static)
        _draw_shelter_live(screen, cam_x, cam_y)
    else:
        _render_m2_bg(screen, cam_x, cam_y)
        _draw_m2_static_dressing(screen, cam_x, cam_y)
        _draw_m2_walls(screen, cam_x, cam_y)
        _draw_m2_control_facade(screen, cam_x, cam_y)
        _draw_gantry_static(screen, cam_x, cam_y)
        _draw_shelter(screen, cam_x, cam_y)
        _draw_garden(screen, cam_x, cam_y)

    for v in STATE.mission2_vehicles:
        _draw_vehicle(screen, v["rect"], v["kind"], cam_x, cam_y, v)

    # (Static walls are baked; the tanker body draws live below.)
    _draw_gantry_dynamic(screen, cam_x, cam_y)

    for decal in STATE.blood_decals[:]:
        surf = get_blood_decal(decal[3])
        surf.set_alpha(int(decal[2]))
        screen.blit(surf, (decal[0] - decal[3] - cam_x, decal[1] - decal[3] - cam_y))
        decal[2] -= 0.25
        if decal[2] <= 0:
            STATE.blood_decals.remove(decal)

    _draw_tanker(screen, cam_x, cam_y)
    _draw_tanker_blast_fx(screen, cam_x, cam_y)   # <-- NEW: cinematic blast fx
    # Blast fireball as a real light: flash floods the scene, then settles
    # to a smoking-wreck glow while the wreckage persists.
    if artpack.enabled() and getattr(STATE, "mission2_tanker_exploded", False):
        tanker = STATE.mission2_tanker_rect
        scx, scy = tanker.centerx - cam_x, tanker.centery - cam_y
        bt = getattr(STATE, "mission2_tanker_blast_timer", 0)
        if bt < 40:
            blast_r, blast_i = 520, 1.2
        elif bt < 130:
            blast_r, blast_i = 360, 0.6
        else:
            blast_r, blast_i = 170, 0.28
        if render_util.screen_visible(scx - blast_r, scy - blast_r,
                                      blast_r * 2, blast_r * 2):
            lighting.buffer().light(scx, scy, blast_r, (255, 170, 90), blast_i,
                                    caster=_m2_solid_world, cam=(cam_x, cam_y),
                                    key="blast")
    for fz in STATE.fire_zones:
        fz.draw(screen, cam_x, cam_y)
    _draw_story_props(screen, cam_x, cam_y)
    # Shelter structure + garden base are baked (drawn in ALL stages via the
    # static layer, so the player sees them during investigation and
    # recognizes the shelter when the "RUN HERE" marker appears during
    # STAGE_RUN). Baked ground sits under vehicles/blood/fire here - correct
    # for walkable pads - while the pulsing shelter arrow below still draws
    # on top via _draw_interactables-adjacent passes.
    _draw_garden_fountain_fx(screen, cam_x, cam_y)

    _draw_interactables(screen, cam_x, cam_y)

    # Shared bullet renderer (glow + sharp core + motion trail). M2 previously
    # skipped the glow halo that M1 had, so M2 bullets looked like crisp dots
    # while M1's looked like glowing tracers. Now consistent.
    draw_bullets(screen, STATE.bullets, cam_x, cam_y, with_glow=True)

    for tr in STATE.mission2_sniper_traces:
        sx1, sy1 = _world(tr["from"], cam_x, cam_y)
        sx2, sy2 = _world(tr["to"], cam_x, cam_y)
        life_pct = max(0, min(1, tr["life"] / max(tr.get("max_life", 1), 1)))
        a = max(0, min(255, int(life_pct * 200)))
        kind = tr.get("kind", "body")
        if kind == "near_miss":
            base_c = (255, 220, 180)
        elif kind == "concrete":
            base_c = (200, 185, 160)
        else:
            base_c = (220, 180, 170)
        segments = 9
        seg_dist = 6
        trace_surf = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        for i in range(segments):
            frac = i / segments
            jfrac = (i + 1) / segments
            mx1 = sx1 + (sx2 - sx1) * frac + _rng_legacy.randint(-3, 3)
            my1 = sy1 + (sy2 - sy1) * frac + _rng_legacy.randint(-3, 3)
            mx2 = sx1 + (sx2 - sx1) * jfrac + _rng_legacy.randint(-3, 3)
            my2 = sy1 + (sy2 - sy1) * jfrac + _rng_legacy.randint(-3, 3)
            seg_a = max(0, a - i * 15)
            thickness = max(1, 4 - i // 3)
            pygame.draw.line(trace_surf, (*base_c, seg_a), (mx1, my1), (mx2, my2), thickness)
        screen.blit(trace_surf, (0, 0))
        if life_pct > 0.6:
            spark = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
            end_a = int((life_pct - 0.6) / 0.4 * 180)
            pygame.draw.circle(spark, (255, 200, 150, end_a), (int(sx2), int(sy2)), 4)
            pygame.draw.circle(spark, (255, 240, 220, end_a // 2), (int(sx2), int(sy2)), 8)
            screen.blit(spark, (0, 0))

    _draw_sniper_lasers_world(screen, cam_x, cam_y)
    _draw_sniper_muzzle_flashes(screen, cam_x, cam_y)
    _draw_abandoned_nest(screen, cam_x, cam_y)
    _draw_flank_cutscene(screen, cam_x, cam_y)

    # ── Thrown bottles (in flight) - shared Mission 1 renderer ──
    draw_thrown_bottles(screen, cam_x, cam_y)

    for actor in STATE.mission2_squad:
        _draw_actor(screen, actor, cam_x, cam_y)

    # Fallen enemy bodies - under the living enemies, over the floor decals.
    corpse.draw_corpses(screen, cam_x, cam_y)
    for e in STATE.enemies:
        e.draw(screen, cam_x, cam_y)

    reload_max_p = 90 if getattr(STATE, "current_weapon", "pistol") == "os12" else 60
    reload_progress = 1.0 - STATE.reload_timer / reload_max_p if STATE.is_reloading and STATE.reload_timer > 0 else 0.0
    melee_progress = 1.0 - STATE.melee_timer / 18.0 if STATE.melee_active and STATE.melee_timer > 0 else 0.0
    if STATE.player:
        # During the death animation, skip the standing player draw - the
        # fallen-body silhouette is drawn by death_anim.draw_death_overlay().
        from entities import death_anim
        if not death_anim.should_skip_player_draw():
            STATE.player.draw(
                screen,
                cam_x,
                cam_y,
                STATE.walls,
                STATE.is_reloading,
                reload_progress,
                STATE.melee_active,
                melee_progress,
                is_moving=not STATE.player_dead and _m2_world._last_keys and (_m2_world._last_keys[pygame.K_w] or _m2_world._last_keys[pygame.K_s] or _m2_world._last_keys[pygame.K_a] or _m2_world._last_keys[pygame.K_d]),
            )
    # Shelter directional arrow - drawn AFTER the player so it renders on
    # top of the player's head. Only draws during STAGE_RUN. See
    # _draw_shelter_arrow() for the full rationale.
    _draw_shelter_arrow(screen, cam_x, cam_y)

    for p in STATE.particles:
        p.draw(screen, cam_x, cam_y)
    for c in STATE.casings:
        c.draw(screen, cam_x, cam_y)
    for pu in STATE.pickups:
        px = pu[0] - cam_x
        py = pu[1] - cam_y + math.sin(_now_s() * 3 + pu[0]) * 3
        if pu[2] == "bandage":
            pygame.draw.rect(screen, (240, 240, 240), (px - 10, py - 10, 20, 20), border_radius=3)
            pygame.draw.rect(screen, (220, 40, 40), (px - 2, py - 6, 4, 12))
            pygame.draw.rect(screen, (220, 40, 40), (px - 6, py - 2, 12, 4))
        else:
            pygame.draw.rect(screen, (95, 90, 82), (px - 7, py - 12, 14, 24))

    if STATE.muzzle_flash_timer > 0 and STATE.player:
        tip_x, tip_y = STATE.player.barrel_tip()
        screen.blit(MUZZLE_FLASH, (int(tip_x - cam_x - 40), int(tip_y - cam_y - 40)))
        if artpack.enabled():
            lighting.buffer().light(tip_x - cam_x, tip_y - cam_y, 240,
                                    (255, 190, 110), 0.9)
        STATE.muzzle_flash_timer -= 1

    ch_x, ch_y = get_scaled_mouse()
    # Honor the Gameplay → Crosshair setting. The shared
    # ui_hud.draw_gameplay_crosshair() (called from acaristan.py after this
    # function returns) already respects SETTINGS.show_crosshair, but this
    # mission also draws its OWN orange reticle here - gate it on the same
    # setting so the user's "Crosshair: Off" preference actually applies.
    try:
        from core.user_settings import SETTINGS
        _show_ch = SETTINGS.show_crosshair
    except Exception:
        _show_ch = True
    if _show_ch and not getattr(STATE, "mission2_card", None) and STATE.mission2_stage not in (STAGE_SNIPER, STAGE_BLACKOUT):
        # Suppress the reticle when the upload OS is active - the OS uses the
        # mouse cursor for clicking, not aiming.
        try:
            from ui import upload_os
            if upload_os.is_upload_os_active():
                _show_ch = False
        except ImportError:
            pass
    if _show_ch and not getattr(STATE, "mission2_card", None) and STATE.mission2_stage not in (STAGE_SNIPER, STAGE_BLACKOUT):
        # Respects crosshair_size (3=small, 6=medium, 10=large) and
        # colorblind_mode - same logic as the shared
        # ui_hud.draw_gameplay_crosshair() and mission.py's reticle.
        from core.user_settings import SETTINGS
        cb = SETTINGS.colorblind_mode
        col = _hud_crosshair.color_for(cb, default=C_ORANGE)
        size = max(3, int(SETTINGS.crosshair_size))
        _hud_crosshair.draw_combat(screen, ch_x, ch_y, size=size, color=col)

    if STATE.player_dead:
        # Death animation overlay: blood pool, fallen body, weapon eject,
        # tinnitus. Camera tilt is applied at the very end of the frame.
        from entities import death_anim
        death_anim.draw_death_overlay(screen, cam_x, cam_y)
    if STATE.gc_flash_timer > 0 and not getattr(STATE, "reduced_motion", False):
        flash = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        t = STATE.gc_flash_timer
        # Main flash: 130 frames. Subflashes: 30 frames (from update loop).
        # Main flash stages:
        #   t > 90  -> pure white (vapor detonation, 40 frames)
        #   t > 60  -> white -> yellow (30 frames)
        #   t > 30  -> yellow -> orange (30 frames)
        #   t > 0   -> orange -> deep red fade (30 frames)
        # Subflashes (t <= 30) read as a quick white punch on top of
        # whatever stage the main flash is in.
        if t > 90:
            alpha = 255
            flash_col = (255, 255, 250)
        elif t > 60:
            alpha = 255
            blend = (90 - t) / 30.0
            flash_col = (255, int(255 - 50 * blend), int(250 - 130 * blend))
        elif t > 30:
            alpha = 255
            blend = (60 - t) / 30.0
            flash_col = (255, int(205 - 75 * blend), int(120 - 80 * blend))
        else:
            # Could be the main flash's final fade OR a subflash punch.
            # If gc_flash_timer was just reset to 30 by a subflash trigger,
            # we want pure white. We detect this by checking if we're still
            # in the early blackout phase (bt < 130 means main flash would
            # still be running, so t<=30 here must be a subflash).
            bt = getattr(STATE, "mission2_tanker_blast_timer", -1)
            if 0 <= bt < 130 and STATE.mission2_stage == STAGE_BLACKOUT:
                # Subflash - bright white punch.
                alpha = 255
                flash_col = (255, 255, 250)
            else:
                # Main flash final fade.
                alpha = int(255 * (t / 30.0))
                flash_col = (255, 130 - int(50 * (1 - t / 30.0)), 40)
        flash.fill((*flash_col, alpha))
        screen.blit(flash, (0, 0))

    if getattr(STATE, "mission2_sniper_kill_flash", 0) > 0:
        a = min(220, STATE.mission2_sniper_kill_flash * 10)
        flash = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        flash.fill((255, 40, 25, a))
        screen.blit(flash, (0, 0))

    draw_vignette(screen, strength=150)
    draw_scanlines(screen)

    if STATE.mission2_stage == STAGE_SNIPER:
        _draw_sniper_overlay(screen)
    elif STATE.mission2_stage == STAGE_BLACKOUT:
        _draw_blackout_overlay(screen)
    else:
        _draw_hud(screen)
        _draw_weapon_hud(screen)
        _draw_radio_text(screen)
        if STATE.show_minimap and STATE.minimap:
            # Pass the IPA truck (current inspect objective) and the tanker
            # (when it's still on the map) so the minimap actually shows the
            # mission's central landmarks instead of looking empty.
            tanker_pos = TANKER_POS if STATE.mission2_tanker_rect in STATE.walls else None
            # Shelter waypoint - shown during STAGE_TANKER (so the player can
            # see where the shelter is BEFORE the countdown starts) and
            # STAGE_RUN (so they can navigate to it during the 7-second
            # countdown). Hidden in other stages to keep the minimap clean.
            stage = getattr(STATE, "mission2_stage", "")
            shelter_pos = SAFE_ZONE if stage in (STAGE_TANKER, STAGE_RUN) else None
            STATE.minimap.draw(
                screen, STATE.player, STATE.enemies, cam_x, cam_y,
                notebook_pos=UPLOAD_TERMINAL_POS,
                exfil_pos=EXFIL_POS,
                ipa_truck_pos=IPA_TRUCK_POS,
                tanker_pos=tanker_pos,
                shelter_pos=shelter_pos,
            )
    _draw_card(screen)

    # ── Evidence completion cinematic (Option E) ──
    # Drawn after the card so it covers everything when active.
    _draw_evidence_cinematic(screen)

    # ── Upload OS ──
    # Drawn on top of everything when active - the OS takes over the screen.
    from ui import upload_os
    if upload_os.is_upload_os_active():
        upload_os.draw_upload_os(screen)

    # Fade transition: smooth fade-out, tooltip, fade-in replacing hard black
    fade = getattr(STATE, "mission2_fade_out", 0)
    if fade > 0:
        STATE.mission2_fade_out = max(0, fade - 1)
        total = 60
        if fade > 40:                     # Fade out: 60→40, alpha 0→255
            t = (fade - 40) / 20.0
            alpha = int((1 - t) * 255)
        elif fade > 20:                   # Hold: 40→20, alpha 255
            alpha = 255
        else:                              # Fade in: 20→0, alpha 255→0
            t = fade / 20.0
            alpha = int(t * 255)
        overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        overlay.fill((15, 15, 18, alpha))
        screen.blit(overlay, (0, 0))
        if 20 < fade <= 40:
            tip = font_terminal_small.render(_T("m2.q_switch_weapon_rmb_aim_lmb_fire"), True, (180, 180, 170))
            tip.set_alpha(200)
            screen.blit(tip, (WIDTH // 2 - tip.get_width() // 2, HEIGHT // 2 + 80))

    # ── Death animation: camera tilt ──
    # Apply at the very end of the frame so the entire rendered scene
    # (world + HUD + minimap + card) rotates together. No-op when alive.
    if STATE.player_dead:
        from entities import death_anim
        death_anim.apply_camera_tilt(screen)


# ─────────────────────────────────────────────
# Data helper accessors
# ─────────────────────────────────────────────
def get_mission2_overview():
    return {
        "id": MISSION2_ID,
        "title": MISSION2_TITLE,
        "location": MISSION2_LOCATION,
        "style": MISSION2_PRIMARY_STYLE,
        "story_flags": MISSION2_STORY_FLAGS.copy(),
    }


def get_opening_cinematic():
    return list(OPENING_CINEMATIC)


def get_squadmate_death_cutscene():
    return list(SQUADMATE_DEATH_CUTSCENE)


def get_mission_phases():
    return list(MISSION_PHASES)


def get_mission2_zones():
    return {
        name: {
            "label": data["label"],
            "tile_rect": (data["tile_rect"].x, data["tile_rect"].y, data["tile_rect"].w, data["tile_rect"].h),
        }
        for name, data in ZONE_DEFS.items()
    }


def get_mission2_clue_defs():
    return [
        {"id": c["id"], "name": c["name"], "zone": c["zone"], "pos": c["pos"]}
        for c in MISSION2_CLUE_DEFS
    ]


def get_ending_cinematic():
    return list(mission2_ending_shots)


def get_all_dialogue_lines():
    out = []
    for group in (mission2_intro_shots, mission2_ending_shots, SQUADMATE_DEATH_CUTSCENE):
        for beat in group:
            if beat.get("speaker") and beat.get("text"):
                out.append({"speaker": beat["speaker"], "text": beat["text"]})
    return out


_NEST_BITS = {"scuff": (0, (24, 8)), "casing": (1, (4, 3)), "rifle": (2, (20, 6))}


def _nest_bit(surface, what, x, y):
    variant, (ax, ay) = _NEST_BITS[what]
    spr = _m2art.get("nest_bits", variant)
    if spr is not None:
        surface.blit(spr, (x - ax, y - ay))
    else:
        _paint_nest_bit(surface, what, x, y)


def _paint_nest_bit(surface, what, x, y):
    """One element of the abandoned sniper nest anchored at x/y (bake source of
    game.art.m2.nest_bits): scuff 48x24 at (x-24, y-8), casing 8x6 at (x-4, y-3), rifle 40x12 at
    (x-20, y-6)."""
    if what == "scuff":
        scuff = pygame.Surface((48, 24), pygame.SRCALPHA)
        pygame.draw.ellipse(scuff, (60, 55, 48, 70), (0, 0, 48, 24))
        surface.blit(scuff, (x - 24, y - 8))
    elif what == "casing":
        pygame.draw.ellipse(surface, (40, 30, 18), (x - 3, y - 1, 6, 3))
        pygame.draw.ellipse(surface, (180, 140, 60), (x - 3, y - 2, 6, 3))
        pygame.draw.ellipse(surface, (230, 200, 110), (x - 2, y - 2, 3, 2))
    else:
        pygame.draw.line(surface, (28, 24, 20), (x - 18, y + 2), (x + 18, y - 1), 4)
        pygame.draw.rect(surface, (40, 36, 30), (x - 4, y - 5, 8, 5))
        pygame.draw.line(surface, (80, 70, 55), (x - 16, y + 1), (x + 16, y - 2), 1)


def _draw_abandoned_nest(surface, fcx, fcy):
    """Persistent trace at the old sniper nest after relocation."""
    nest = getattr(STATE, "mission2_abandoned_nest", None)
    if not nest:
        return
    nest["age"] = nest.get("age", 0) + 1
    sx, sy = _world(nest["pos"], fcx, fcy)
    # RPE6 Phase 3: scuff / casing / rifle are baked sprites (game.art.m2.nest_bits); positions
    # stay data-driven, _paint_nest_bit is the fallback / bake source, the fading glow is live.
    _nest_bit(surface, "scuff", sx, sy)
    for ox, oy in nest.get("casings", []):
        _nest_bit(surface, "casing", sx + ox, sy + oy)
    # Left-behind rifle - persists into gameplay as evidence the sniper left in a hurry.
    rifle_pos = nest.get("rifle_pos")
    if rifle_pos:
        rx, ry = _world(rifle_pos, fcx, fcy)
        _nest_bit(surface, "rifle", rx, ry)
    age = nest["age"]
    if age < 150:
        fade = 1.0 - (age / 150.0)
        a = int(140 * fade)
        gl = pygame.Surface((24, 24), pygame.SRCALPHA)
        pygame.draw.circle(gl, (255, 240, 200, a), (12, 12), 3)
        pygame.draw.circle(gl, (255, 230, 180, a // 3), (12, 12), 7)
        surface.blit(gl, (sx - 12, sy - 16))


def _start_flank_cutscene():
    """Open the 9-second 'sniper flees the nest' cinematic.

    Beats (elapsed frames from cutscene start):
      0–90     Slow push-in on the gantry. Sniper prone, aiming south at player.
      90–180   Hold on nest. Scope glint pulses. Tension builds.
      180–220  Sniper startles, head pulls back from rifle.
      220–300  Rifle drops to the deck. Silhouette crawls north, exits frame.
      300–330  Big dust burst + casing scatter + screen shake. Nest empty.
      330–390  "NEST ABANDONED" stamp fades in.
      390–510  Hold on empty nest. Stamp + subtitle + objective hint.
      510–540  Letterbox retracts. Camera releases. Player lock removed.
    """
    STATE.mission2_flank_cutscene_timer = FLANK_CUTSCENE_DURATION
    STATE.mission2_flank_cutscene_max = FLANK_CUTSCENE_DURATION
    STATE.player_locked = True
    # Wide establishing shot first; the cutscene update will push the
    # focus target closer over the first 90 frames for a slow dolly-in.
    sx, sy = SNIPER_NEST_POS
    STATE.mission2_camera_focus = (sx - 100, sy + 90)
    STATE.mission2_camera_focus_timer = FLANK_CUTSCENE_DURATION + 20
    STATE.mission2_flank_cutscene_phase = 0
    STATE.mission2_flank_cutscene_casings_scattered = False
    STATE.mission2_flank_cutscene_rifle_dropped = False
    STATE.screen_shake = max(STATE.screen_shake, 6)


def _update_flank_cutscene():
    t = getattr(STATE, "mission2_flank_cutscene_timer", 0)
    if t <= 0:
        return
    tmax = getattr(STATE, "mission2_flank_cutscene_max", FLANK_CUTSCENE_DURATION)
    elapsed = tmax - t
    STATE.mission2_flank_cutscene_timer = t - 1
    sx, sy = SNIPER_NEST_POS

    # --- Camera moves per beat ------------------------------------------------
    if elapsed == 0:
        STATE.mission2_camera_focus = (sx - 100, sy + 90)
    elif elapsed == FLANK_BEAT_PUSH_IN_END:
        # Slow dolly-in to a hero close-up of the nest.
        STATE.mission2_camera_focus = (sx, sy + 50)
    elif elapsed == FLANK_BEAT_BURST:
        # Pull back slightly so the dust burst is fully visible.
        STATE.mission2_camera_focus = (sx, sy + 80)

    # --- Beat: hold + aim (push-in completes → startle) ----------------------
    # Subtle handheld shake during the aiming hold for tension.
    if FLANK_BEAT_PUSH_IN_END <= elapsed < FLANK_BEAT_STARTLE:
        if elapsed % 7 == 0:
            STATE.screen_shake = max(STATE.screen_shake, 2)

    # --- Beat: startle (sniper notices the flanker) -------------------------
    if elapsed == FLANK_BEAT_STARTLE:
        STATE.screen_shake = max(STATE.screen_shake, 10)
        audio.play("radio_static", volume=0.22)

    # --- Beat: scramble (silhouette crawls north off the gantry) ------------
    if FLANK_BEAT_SCRAMBLE_BEGIN <= elapsed < FLANK_BEAT_BURST:
        # Footstep dust puffs trailing NORTH from the nest - reads as
        # someone scrambling backwards off the platform away from the player.
        if elapsed % 6 == 0:
            fx = sx + _rng_legacy.randint(-30, 10)
            fy = sy - _rng_legacy.randint(5, 25)  # north = -y
            _burst(fx, fy, (110, 100, 88), 3, speed_mul=0.5)
        # Drop the rifle the moment the scramble begins - it stays on
        # the deck for the rest of the cutscene and beyond.
        if not getattr(STATE, "mission2_flank_cutscene_rifle_dropped", False):
            STATE.mission2_flank_cutscene_rifle_dropped = True
            audio.play("rifle_handle", volume=0.4)
            STATE.mission2_flank_cutscene_rifle_pos = (sx + 6, sy + 24)

    # --- Beat: dust burst (sniper is gone, nest empty) ----------------------
    if elapsed == FLANK_BEAT_BURST:
        _burst(sx, sy, (90, 88, 80), 40, speed_mul=2.0)
        _burst(sx + 8, sy - 6, (130, 120, 100), 22, speed_mul=2.4)
        _burst(sx - 10, sy + 8, (70, 65, 58), 18, speed_mul=1.4)
        if not getattr(STATE, "mission2_flank_cutscene_casings_scattered", False):
            STATE.mission2_flank_cutscene_casings_scattered = True
            casings = [
                (_rng_legacy.randint(-22, 22), _rng_legacy.randint(-14, 14))
                for _ in range(10)
            ]
            for ox, oy in casings:
                _burst(sx + ox, sy + oy, (200, 160, 70), 2, speed_mul=1.2)
            STATE.mission2_abandoned_nest = {
                "pos": (sx, sy),
                "age": 0,
                "casings": casings,
                "rifle_pos": getattr(STATE, "mission2_flank_cutscene_rifle_pos", (sx + 6, sy + 24)),
            }
        STATE.screen_shake = max(STATE.screen_shake, 26)
        audio.play("concrete_impact", volume=0.55)

    # --- Beat: stamp fade-in - soft radio chirp bridges into Vasile's line -
    if elapsed == FLANK_BEAT_STAMP_FADE_IN:
        audio.play("radio_static", volume=0.18)

    # --- Beat: Vasile's line - fires during the stamp hold so it doesn't
    # step on the letterbox retract audio. NOTE: do NOT mention the cleanup
    # team here - that squad spawns AFTER the cutscene ends (in the "done"
    # branch of _update_post_sniper_gameplay) and gets its own intro radio
    # line at that point. This line just confirms the sniper bailed.
    if t == 60:
        _radio('VASILE: "Sniper bugged out. Nest is empty."',
               color=C_VASILE, mark="sniper_suppressed")

    # --- Cutscene end: clear camera focus so the player regains control ----
    # CRITICAL: without clearing mission2_camera_focus, the camera stays
    # glued to the gantry forever - which is the bug where the player
    # couldn't move on to the truck-inspection phase.
    if t == 1:
        STATE.player_locked = False
        STATE.mission2_flank_cutscene_timer = 0
        STATE.mission2_camera_focus = None
        STATE.mission2_camera_focus_timer = 0
        STATE.mission2_flank_cutscene_rifle_dropped = False
        STATE.mission2_flank_cutscene_casings_scattered = False
        if not getattr(STATE, "mission2_abandoned_nest", None):
            STATE.mission2_abandoned_nest = {
                "pos": (sx, sy),
                "age": 0,
                "casings": [
                    (_rng_legacy.randint(-18, 18), _rng_legacy.randint(-12, 12))
                    for _ in range(7)
                ],
            }


def _draw_flank_cutscene(surface, fcx, fcy):
    t = getattr(STATE, "mission2_flank_cutscene_timer", 0)
    if t <= 0:
        return
    tmax = getattr(STATE, "mission2_flank_cutscene_max", FLANK_CUTSCENE_DURATION)
    elapsed = tmax - t

    # --- Letterbox bars (animate in over 30 frames, out over 30) ------------
    if elapsed < 30:
        bar_h = int(90 * (elapsed / 30.0))
    elif t < 30:
        bar_h = int(90 * (t / 30.0))
    else:
        bar_h = 90
    if bar_h > 0:
        bar = pygame.Surface((WIDTH, bar_h), pygame.SRCALPHA)
        bar.fill((0, 0, 0, 245))
        surface.blit(bar, (0, 0))
        surface.blit(bar, (0, HEIGHT - bar_h))

    sx, sy = _world(SNIPER_NEST_POS, fcx, fcy)

    # ====================================================================
    # SNIPER SILHOUETTE
    # Drawn in the SAME top-down construction language as _draw_actor()
    # (line 4179) so the cutscene sniper reads as a real game actor, not
    # a custom blob. Only differences from a regular soldier:
    #   - IPA orange accent instead of KRAP blue
    #   - Longer rifle barrel with scope mount + bipod
    #   - Crouched-aim pose (frozen, scope down)
    #   - Pulsing scope glint at the front of the scope
    #
    # Pose progression:
    #   AIM       - crouched, eye at scope, rifle level, glint pulsing
    #   STARTLE   - head lifts off scope, rifle tilts up
    #   SCRAMBLE  - rifle drops to deck; body crawls NORTH and fades
    # ====================================================================
    if elapsed < FLANK_BEAT_BURST:
        # --- Compute pose_t: 0 = AIM, 1 = STARTLE, 2 = SCRAMBLE/GONE ------
        if elapsed < FLANK_BEAT_STARTLE:
            pose_t = 0.0
        elif elapsed < FLANK_BEAT_SCRAMBLE_BEGIN:
            pose_t = (elapsed - FLANK_BEAT_STARTLE) / (FLANK_BEAT_SCRAMBLE_BEGIN - FLANK_BEAT_STARTLE)
        else:
            pose_t = 1.0 + (elapsed - FLANK_BEAT_SCRAMBLE_BEGIN) / (FLANK_BEAT_BURST - FLANK_BEAT_SCRAMBLE_BEGIN)
            pose_t = min(pose_t, 2.0)

        # --- Per-pose transforms -------------------------------------------
        if pose_t < 1.0:
            # AIM → STARTLE: head lifts up off the scope, rifle tilts up
            p = pose_t
            head_lift = int(6 * p)               # head rises off the scope
            rifle_tilt = -0.18 * p               # radians, negative = barrel up
            body_alpha = 255
            body_y_off = 0
            body_x_off = 0
            rifle_in_hands = True
        elif pose_t < 2.0:
            # STARTLE → SCRAMBLE: rifle drops, body crawls NORTH (-y) and fades
            p = pose_t - 1.0
            head_lift = 6 + int(3 * p)
            rifle_tilt = -0.18
            body_alpha = int(255 - 240 * p)
            body_y_off = -int(45 * p)            # crawl north (off top of frame)
            body_x_off = int(10 * p)
            rifle_in_hands = (p < 0.06)          # rifle drops almost instantly
        else:
            pose_t = 2.0
            head_lift = 0
            rifle_tilt = 0
            body_alpha = 0
            body_y_off = 0
            body_x_off = 0
            rifle_in_hands = False

        if body_alpha > 0:
            sil = pygame.Surface((90, 90), pygame.SRCALPHA)

            # Local origin: sniper centered at (45, 45) on the sil surface.
            lx, ly = 45, 45

            # Crouch offset (matches _draw_actor's is_crouch branch)
            body_dy = 6
            cy = ly + body_dy

            # --- Shadow at feet (matches _draw_actor crouch shadow) -------
            shad = pygame.Surface((44, 14), pygame.SRCALPHA)
            render_util.soft_shadow(shad, shad.get_rect(), 70)
            sil.blit(shad, (lx - 22, cy + 12))

            # --- Legs (crouch pose: boots together, trousers short) -------
            boot = (10, 10, 12)
            trouser = (24, 28, 34)
            pygame.draw.ellipse(sil, boot,    (lx - 15, cy + 11, 14, 8))
            pygame.draw.ellipse(sil, boot,    (lx +  1, cy + 11, 14, 8))
            pygame.draw.rect(sil,   trouser,  (lx - 14, cy +  4, 10, 10), border_radius=2)
            pygame.draw.rect(sil,   trouser,  (lx +  4, cy +  4, 10, 10), border_radius=2)

            # --- Torso (4-point trapezoid, same as _draw_actor) -----------
            torso_pts = [
                (lx - 13, cy - 14), (lx + 13, cy - 14),
                (lx + 11, cy + 10), (lx - 11, cy + 10),
            ]
            pygame.draw.polygon(sil, (44, 54, 60), torso_pts)
            pygame.draw.polygon(sil, (22, 28, 32), torso_pts, 2)
            # Inner vest
            pygame.draw.rect(sil, (34, 42, 48),
                             (lx - 9, cy - 9, 18, 14), border_radius=3)
            # Accent stripe - IPA orange instead of KRAP blue. This is the
            # single visual cue that tells the player "this is an enemy
            # sniper", not one of our guys.
            IPA_ACCENT = (210, 95, 55)
            pygame.draw.rect(sil, IPA_ACCENT,
                             (lx - 11, cy - 12, 22, 4), border_radius=2)
            # Shoulder patch dot
            pygame.draw.circle(sil, IPA_ACCENT, (lx + 9, cy + 3), 3)

            # --- Arms + rifle (crouched-aim pose) -------------------------
            # Rifle points SOUTH (down on screen, toward the player).
            # Both hands grip the rifle - left hand at stock, right hand
            # at trigger. Arms extend DOWN-FORWARD from shoulders to hands.
            if rifle_in_hands:
                # Rifle geometry - compute end points with optional tilt
                # Stock at upper chest, muzzle extends DOWN and slightly out.
                stock_pos = (lx - 4, cy - 2)
                # Tilt the rifle: rotate the muzzle around the stock.
                rifle_len = 36  # longer than normal soldier rifle (24)
                muzzle_dx = int(rifle_len * math.sin(rifle_tilt))
                muzzle_dy = int(rifle_len * math.cos(rifle_tilt))
                muzzle_pos = (stock_pos[0] + muzzle_dx, stock_pos[1] + muzzle_dy)

                # Hands - left at stock, right near trigger (mid-barrel)
                lh = (stock_pos[0] - 2, stock_pos[1] + 2)
                rh = (stock_pos[0] + 4, stock_pos[1] + 12)

                # Arms (5px uniform-color lines, same as _draw_actor)
                pygame.draw.line(sil, (40, 48, 56),
                                 (lx - 11, cy - 4), lh, 5)
                pygame.draw.line(sil, (40, 48, 56),
                                 (lx + 9, cy - 6), rh, 5)
                # Hands (skin circles r=3)
                pygame.draw.circle(sil, (190, 150, 120), lh, 3)
                pygame.draw.circle(sil, (190, 150, 120), rh, 3)

                # Rifle stock (brown, 4px thick - matches _draw_actor stock)
                pygame.draw.line(sil, (75, 55, 34),
                                 (lx - 14, cy - 6), stock_pos, 4)
                # Rifle barrel (very dark, 3px - matches _draw_actor barrel)
                pygame.draw.line(sil, (16, 16, 15), stock_pos, muzzle_pos, 3)
                # Scope mount (rect on top of barrel, midway)
                scope_cx = (stock_pos[0] + muzzle_pos[0]) // 2
                scope_cy = (stock_pos[1] + muzzle_pos[1]) // 2 - 5
                pygame.draw.rect(sil, (25, 26, 24),
                                 (scope_cx - 5, scope_cy - 3, 12, 6), border_radius=2)
                # Scope lens (dark circle at the FRONT of the scope)
                lens_x = scope_cx + 6
                lens_y = scope_cy + 1
                pygame.draw.circle(sil, (9, 9, 8), (lens_x, lens_y), 3)
                # Bipod - two short angled legs at the muzzle
                pygame.draw.line(sil, (16, 16, 15),
                                 muzzle_pos, (muzzle_pos[0] - 4, muzzle_pos[1] + 6), 2)
                pygame.draw.line(sil, (16, 16, 15),
                                 muzzle_pos, (muzzle_pos[0] + 4, muzzle_pos[1] + 6), 2)
                # Muzzle dot
                pygame.draw.circle(sil, (9, 9, 8), muzzle_pos, 2)

                # Scope glint - pulsing bright dot at the lens,
                # AIM/STARTLE only. Fades to 0 by the time pose_t reaches 1.0.
                if pose_t < 1.0:
                    glint_strength = (1.0 - pose_t)
                    glint_pulse = 0.4 + 0.6 * (0.5 + 0.5 * math.sin(elapsed * 0.18))
                    glint_alpha = int(240 * glint_strength * glint_pulse)
                    if glint_alpha > 0:
                        # Bright core
                        pygame.draw.circle(sil, (255, 245, 200, glint_alpha),
                                           (lens_x, lens_y), 3)
                        # Soft halo
                        pygame.draw.circle(sil, (255, 200, 100, glint_alpha // 3),
                                           (lens_x, lens_y), 8)

            # --- Head (same construction as _draw_actor, top-down) --------
            # head_lift pulls the head UP (north, -y) during startle/scramble.
            head_y = cy - 18 - head_lift
            # Helmet outer (dark, r=10)
            pygame.draw.circle(sil, (7, 8, 9),    (lx, head_y), 10)
            # Helmet inner (steel, r=8)
            pygame.draw.circle(sil, (58, 70, 82), (lx, head_y), 8)
            # Accent stripe (IPA orange)
            pygame.draw.rect(sil, IPA_ACCENT,
                             (lx - 7, head_y - 5, 14, 3), border_radius=2)
            # Face (skin circle r=5, offset down-right like _draw_actor)
            pygame.draw.circle(sil, (190, 150, 120), (lx + 1, head_y + 2), 5)
            # Eyes (2 dark dots)
            pygame.draw.circle(sil, (35, 22, 12), (lx - 1, head_y + 1), 1)
            pygame.draw.circle(sil, (35, 22, 12), (lx + 3, head_y + 1), 1)

            # Apply body_alpha to the whole silhouette via surface alpha.
            # This fades the entire body during the scramble, matching the
            # visual intent of _draw_actor's dead/alive alpha handling.
            sil.set_alpha(body_alpha)

            # Blit. body_y_off shifts the whole sprite north during scramble;
            # body_x_off adds slight eastward drift.
            surface.blit(sil, (sx - 45 + body_x_off, sy - 45 + body_y_off))

    # --- Dropped rifle on the deck (visible after the scramble begins) ------
    # Drawn separately from the silhouette so it stays put after the body
    # has crawled off-frame. Persists into gameplay via _draw_abandoned_nest.
    if getattr(STATE, "mission2_flank_cutscene_rifle_dropped", False):
        rifle_pos = getattr(STATE, "mission2_flank_cutscene_rifle_pos", (sx + 6, sy + 24))
        rx, ry = _world(rifle_pos, fcx, fcy)
        # Rifle body - dark line with stock and scope bumps
        pygame.draw.line(surface, (24, 22, 20), (rx, ry - 14), (rx, ry + 10), 5)
        pygame.draw.rect(surface, (32, 28, 24), (rx - 8, ry - 4, 12, 8))   # stock
        pygame.draw.rect(surface, (32, 28, 24), (rx + 2, ry - 8, 12, 6))   # scope
        # Subtle highlight so it doesn't vanish into the gantry shadow
        pygame.draw.line(surface, (75, 65, 50), (rx, ry - 13), (rx, ry + 9), 1)

    # --- "NEST ABANDONED" stamp with scale-in + subtitle + objective hint --
    if elapsed >= FLANK_BEAT_STAMP_FADE_IN:
        stamp_age = elapsed - FLANK_BEAT_STAMP_FADE_IN
        # Scale-in over the first 15 frames (slower than before), then hold.
        if stamp_age < 15:
            scale = 1.8 - (stamp_age / 15.0) * 0.8
        else:
            scale = 1.0
        # Alpha: fade in over 30 frames, hold, then fade out in the last 30
        # frames of the cutscene so the stamp doesn't pop off.
        if stamp_age < 30:
            alpha = int(255 * (stamp_age / 30.0))
        elif t < 30:
            alpha = int(255 * (t / 30.0))
        else:
            alpha = 255

        cx = WIDTH // 2
        cy = HEIGHT // 2 - 30

        # Title
        font = pygame.font.Font(None, int(56 * scale))
        title = font.render(_T("m2.nest_abandoned"), True, (230, 190, 120))
        title.set_alpha(alpha)
        tw, th = title.get_size()
        surface.blit(title, (cx - tw // 2, cy - th // 2))

        # Underline bar
        bar_w = int(tw * 1.15)
        ul = pygame.Surface((bar_w, 3), pygame.SRCALPHA)
        ul.fill((230, 190, 120, alpha))
        surface.blit(ul, (cx - bar_w // 2, cy + th // 2 + 6))

        # Subtitle
        sub_font = pygame.font.Font(None, 24)
        sub = sub_font.render(_T("m2.sniper_has_relocated"), True, (190, 170, 130))
        sub.set_alpha(alpha)
        sw = sub.get_width()
        surface.blit(sub, (cx - sw // 2, cy + th // 2 + 16))

        # Objective hint - fades in after the stamp is fully visible
        if elapsed >= FLANK_BEAT_STAMP_FULL:
            hint_age = elapsed - FLANK_BEAT_STAMP_FULL
            hint_alpha = min(255, int(255 * (hint_age / 30.0)))
            hint_font = pygame.font.Font(None, 20)
            hint = hint_font.render(_T("m2.vasile_wants_the_cleanup_team_cl"),
                                    True, (200, 140, 90))
            hint.set_alpha(hint_alpha)
            hw = hint.get_width()
            surface.blit(hint, (cx - hw // 2, cy + th // 2 + 44))


if __name__ == "__main__":
    print(f"{MISSION2_TITLE} - clean vertical slice")
    print(f"Map: {MAP_W}x{MAP_H}")
    print(f"Intro shots: {len(mission2_intro_shots)}")
    print(f"Ending shots: {len(mission2_ending_shots)}")
