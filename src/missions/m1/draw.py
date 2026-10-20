"""Split from mission.py - see mission.py (shim) for the map."""
"""Mission 1B gameplay: warehouse infiltrate/firefight/escape."""
import math
import random
from engine.core import LEGACY_RNG as _rng_legacy  # RPE6 R6: named 'legacy' rng stream
import time
import pygame
from core.config import (BAY_DOOR_FRAME_3W, BAY_DOOR_TILE_3W, CONTAINER_TILE_BLUE, CONTAINER_TILE_GREY, CONTAINER_TILE_RED, CONTAINER_TILE_RUST, C_BG_GAME, C_KRAP_BLUE, C_ORANGE, C_TERMINAL, C_WHITE, DOOR_FRAME_TILE, DOOR_INTERACT_RANGE, DOOR_TILE, FLOOR_TILE, FLOOR_TILE_SIZE, HEIGHT, LETTER_H, MUZZLE_FLASH, SLUM_FLOOR, TILE_SIZE, WAREHOUSE_WALL, WIDTH, bay_door_shadow, draw_letterbox, draw_scanlines, draw_vignette, font_dialogue, font_location_sub, font_prompt, font_speaker, font_terminal, font_terminal_small, get_scaled_mouse, screen, wall_shadow)
from entities.art_cache import get_blood_decal, get_glow, get_panel_bg
from entities import corpse
from entities.enemy_ai import Enemy, enemy_hear_shot
from core.state import STATE
from game.art import m1 as _m1art
from ui.hud import THEME, MiniMap, draw_objective_panel, draw_pinned_radio
from engine.ui import (bottle_hud as _hud_bottle_hud,
                       crosshair as _hud_crosshair,
                       health_bar as _hud_health_bar,
                       hostiles as _hud_hostiles)
from entities.player import Player, resolve_melee
from core.interactions import (
    Door,
    trigger_alarm_early,
    trigger_radio_chatter,
)
from entities.weapons import (
    draw_thrown_bottles,
    spawn_molotov_fire as _spawn_molotov_fire,
    _wall_blocks_line,
    MOLOTOV_RADIUS,
    MOLOTOV_DURATION,
    MOLOTOV_ENEMY_DAMAGE,
    MOLOTOV_PLAYER_DAMAGE,
)
from cutscenes import draw_volkov, draw_commander, draw_biribel
from missions import walking_sim
from core import artpack, lighting, staticlayer
from core import render_util
from core import props as _props
from fx import effects
from core.camera import update_camera, reset_camera_state, collide_bullet_walls, draw_bullets

from missions.m1.map import _lerp, mission1_map, MAP_W, MAP_H
from missions.m1 import update as _m1_update
from missions.m1.hotwire import _hotwire_wire_nodes, HOTWIRE_TARGET_PAIRS, HOTWIRE_WIRES
from engine.core import now_ms as _now_ms, now_s as _now_s  # RPE6 B-001 timebase
from engine.text import T as _T  # RPE6 Phase 4 text table

def _draw_molotov_icon(surface, cx, cy, active=True):
    """Small chunky pixel-art Molotov icon for the HUD (baked sprite game.art.m1.molotov_icon,
    procedural _paint_molotov_icon as fallback / bake source)."""
    spr = _m1art.get("molotov_icon", 0 if active else 1)
    if spr is not None:
        surface.blit(spr, (cx - 6, cy - 26))
        return
    _paint_molotov_icon(surface, cx, cy, active)


def _paint_molotov_icon(surface, cx, cy, active=True):
    """Procedural Molotov icon; opaque primitives inside (cx-6, cy-26) .. (cx+5, cy+9)."""
    if active:
        glass = (105, 75, 42)
        glass_dark = (42, 28, 18)
        fuel = (230, 120, 35)
        rag = (190, 170, 120)
        flame_outer = (255, 95, 20)
        flame_inner = (255, 220, 90)
    else:
        glass = (42, 45, 46)
        glass_dark = (25, 27, 28)
        fuel = (60, 62, 64)
        rag = (65, 65, 60)
        flame_outer = None
        flame_inner = None
    # Bottle body
    pygame.draw.rect(surface, glass_dark, (cx - 5, cy - 8, 10, 18), border_radius=2)
    pygame.draw.rect(surface, glass, (cx - 4, cy - 7, 8, 16), border_radius=2)
    # Fuel strip
    pygame.draw.rect(surface, fuel, (cx - 2, cy - 5, 3, 11))
    # Neck
    pygame.draw.rect(surface, glass_dark, (cx - 2, cy - 14, 4, 6))
    pygame.draw.rect(surface, glass, (cx - 1, cy - 14, 2, 6))
    # Rag
    pygame.draw.rect(surface, rag, (cx - 4, cy - 17, 8, 3))
    # Highlight
    if active:
        pygame.draw.line(surface, (255, 180, 90), (cx - 3, cy - 5), (cx - 3, cy + 6), 1)
    # Tiny flame
    if active:
        pygame.draw.polygon(
            surface,
            flame_outer,
            [(cx, cy - 25), (cx - 5, cy - 16), (cx + 5, cy - 16)],
        )
        pygame.draw.polygon(
            surface,
            flame_inner,
            [(cx, cy - 22), (cx - 2, cy - 16), (cx + 2, cy - 16)],
        )
def _escape_subtitle(surface, speaker, text, alpha=255):
    box_w, box_h = 720, 92
    box_x = WIDTH // 2 - box_w // 2
    box_y = HEIGHT - LETTER_H - box_h + 16
    box = pygame.Surface((box_w, box_h), pygame.SRCALPHA)
    box.fill((0, 0, 0, min(205, alpha)))
    pygame.draw.rect(box, (120, 120, 105, min(180, alpha)), box.get_rect(), 1)
    pygame.draw.line(box, C_KRAP_BLUE, (0, 0), (0, box_h), 4)
    surface.blit(box, (box_x, box_y))
    sp = font_speaker.render(speaker, True, (190, 190, 175))
    tx = font_dialogue.render(text, True, C_WHITE)
    sp.set_alpha(alpha)
    tx.set_alpha(alpha)
    surface.blit(sp, (box_x + 22, box_y + 12))
    surface.blit(tx, (box_x + 22, box_y + 48))
def _draw_biribel_soldier_closeup(surface, cx, cy, t, scale=1.0):
    """Close-up of Biribel in the escape truck.

    Uses the cast-sheet Biribel (cutscenes.figure_kit) framed head-and-
    shoulders, so the face is the same one every other cutscene uses; only
    the dashboard/rain lighting below is specific to this shot.
    """
    from cutscenes.figure_kit import draw_character, HEIGHT as _FK_HEIGHT, _REF_H
    s = scale
    k = 2.07 * s                                  # px per arrest unit (head ~116px wide)
    head_cy = cy - 6 * s
    foot_y = head_cy + 258 * k
    ms = t * 1000.0 / 60.0                        # escape timer is in frames
    blink = 0.95 if (int(ms) % 4200) < 130 else 0
    draw_character(surface, "biribel", cx, foot_y, k * _REF_H / _FK_HEIGHT["biribel"],
                   facing_right=False, t=ms, look=-0.3, fear=0.15, blink=blink)
    # ── Dashboard/rain cinematic lighting ─────────────────────────────
    orange = pygame.Surface((int(230*s), int(195*s)), pygame.SRCALPHA)
    pygame.draw.ellipse(orange, (255, 130, 48, 30), orange.get_rect())
    surface.blit(orange, (int(cx - 115*s), int(cy - 10*s)))
    blue = pygame.Surface((int(190*s), int(180*s)), pygame.SRCALPHA)
    pygame.draw.ellipse(blue, (50, 120, 180, 22), blue.get_rect())
    surface.blit(blue, (int(cx - 118*s), int(cy - 96*s)))
def _draw_escape_truck(surface, x, y, scale=1.0, angle=0.0, headlights=True):
    s = scale
    # shadow/wake
    sh = pygame.Surface((int(170*s), int(70*s)), pygame.SRCALPHA)
    render_util.soft_shadow(sh, sh.get_rect(), 110)
    surface.blit(sh, (int(x - 85*s), int(y + 20*s)))
    body = pygame.Rect(int(x - 70*s), int(y - 28*s), int(140*s), int(56*s))
    pygame.draw.rect(surface, (20, 26, 20), body, border_radius=max(2, int(5*s)))
    pygame.draw.rect(surface, (52, 64, 46), body, max(1, int(2*s)), border_radius=max(2, int(5*s)))
    # Top highlight + tarp seams + crates so the flatbed reads at any scale.
    pygame.draw.line(surface, (86, 102, 76),
                     (int(x - 66*s), int(y - 24*s)), (int(x + 62*s), int(y - 24*s)),
                     max(1, int(1*s)))
    for ci in (-30, -8, 14, 36):
        pygame.draw.line(surface, (34, 44, 32),
                         (int(x + ci*s), int(y - 22*s)), (int(x + ci*s), int(y + 22*s)),
                         max(1, int(1*s)))
    for cxo, cyo in ((-48, -8), (-24, 6)):
        rx, ry = int(x + cxo*s), int(y + cyo*s)
        rw, rh = max(2, int(20*s)), max(2, int(13*s))
        pygame.draw.rect(surface, (96, 76, 48), (rx - rw//2, ry - rh//2, rw, rh), border_radius=1)
        pygame.draw.rect(surface, (52, 38, 24), (rx - rw//2, ry - rh//2, rw, rh), 1, border_radius=1)
    cab = pygame.Rect(int(x + 18*s), int(y - 24*s), int(45*s), int(48*s))
    pygame.draw.rect(surface, (22, 28, 22), cab, border_radius=max(2, int(4*s)))
    pygame.draw.rect(surface, (44, 56, 40), cab, border_radius=max(2, int(4*s)))
    pygame.draw.rect(surface, (72, 86, 64), cab, 1, border_radius=max(2, int(4*s)))
    pygame.draw.rect(surface, (16, 24, 26), (int(x + 32*s), int(y - 17*s), int(20*s), int(14*s)), border_radius=2)
    pygame.draw.line(surface, (150, 190, 200),
                     (int(x + 34*s), int(y - 14*s)), (int(x + 49*s), int(y - 14*s)),
                     max(1, int(1*s)))
    pygame.draw.rect(surface, C_KRAP_BLUE, (int(x - 52*s), int(y - 16*s), int(62*s), int(6*s)))
    pygame.draw.rect(surface, (210, 210, 205), (int(x - 52*s), int(y - 9*s), int(62*s), 1))
    for wx in (-45, 20, 52):
        for wy in (-31, 27):
            pygame.draw.ellipse(surface, (8, 8, 10), (int(x + wx*s - 10*s), int(y + wy*s - 5*s), int(20*s), int(10*s)))
            pygame.draw.ellipse(surface, (70, 74, 80), (int(x + wx*s - 5*s), int(y + wy*s - 3*s), int(10*s), int(6*s)))
    if headlights:
        beam = pygame.Surface((int(260*s), int(95*s)), pygame.SRCALPHA)
        pygame.draw.polygon(beam, (255, 230, 145, 38), [(0, 28*s), (250*s, 0), (250*s, 95*s), (0, 65*s)])
        surface.blit(beam, (int(x + 58*s), int(y - 48*s)))
        pygame.draw.rect(surface, (245, 220, 130), (int(x + 62*s), int(y - 18*s), int(8*s), int(10*s)))
        pygame.draw.rect(surface, (245, 220, 130), (int(x + 62*s), int(y + 8*s), int(8*s), int(10*s)))
def draw_biribel_escape_cutscene(surface, timer):
    """Cinematic escape cutscene after the real hotwire minigame."""
    t = int(timer)
    # base rainy night road/warehouse palette
    surface.fill((5, 7, 10))
    for y in range(HEIGHT):
        p = y / HEIGHT
        pygame.draw.line(surface, (int(6+p*8), int(8+p*10), int(13+p*18)), (0, y), (WIDTH, y))
    # rain streaks
    rng_r = random.Random(92)
    for _ in range(110):
        rx = (rng_r.randint(0, WIDTH) + t * 3) % WIDTH
        ry = (rng_r.randint(LETTER_H, HEIGHT - LETTER_H) + t * 7) % (HEIGHT - LETTER_H) + LETTER_H
        pygame.draw.line(surface, (110, 130, 160, 55), (rx, ry), (rx - 5, ry + 18), 1)
    if t < 135:
        # dashboard / wire close-up
        dash_y = HEIGHT // 2 + 80
        pygame.draw.rect(surface, (8, 10, 12), (0, dash_y, WIDTH, HEIGHT - dash_y))
        pygame.draw.rect(surface, (28, 34, 32), (160, dash_y - 80, WIDTH - 320, 105), border_radius=10)
        pygame.draw.rect(surface, (58, 70, 62), (160, dash_y - 80, WIDTH - 320, 105), 2, border_radius=10)
        for i, col in enumerate([(215,55,45), (225,190,55), (60,130,220), (70,185,95)]):
            y = dash_y - 54 + i * 20
            pygame.draw.line(surface, col, (235, y), (WIDTH//2 - 30, y + math.sin(t*.12+i)*8), 5)
            pygame.draw.circle(surface, (220, 140, 70), (WIDTH//2 - 25, int(y + math.sin(t*.12+i)*8)), 7)
        if t > 30 and (t // 5) % 2 == 0:
            for _ in range(10):
                sx = WIDTH//2 + _rng_legacy.randint(-20, 18)
                sy = dash_y - 25 + _rng_legacy.randint(-28, 18)
                pygame.draw.line(surface, (255, 220, 90), (sx, sy), (sx+_rng_legacy.randint(-24,24), sy+_rng_legacy.randint(-18,18)), 1)
        wheel_r = 92 + int(math.sin(t*.08)*2)
        pygame.draw.circle(surface, (12, 13, 14), (WIDTH//2 + 190, dash_y - 16), wheel_r, 12)
        _escape_subtitle(surface, "ENGINE", "starter catches...", min(255, t*6))
    elif t < 300:
        # Biribel close-up, soldier not suit.
        # windshield frame
        pygame.draw.rect(surface, (8, 10, 12), (80, LETTER_H + 20, WIDTH - 160, HEIGHT - 2*LETTER_H - 40), 6)
        for lx in (180, WIDTH-180):
            pygame.draw.line(surface, (20, 24, 28), (lx, LETTER_H+28), (lx-70, HEIGHT-LETTER_H-30), 5)
        _draw_biribel_soldier_closeup(surface, WIDTH//2, HEIGHT//2 - 20, t, scale=1.1)
        # windshield rain highlights
        for i in range(18):
            x = 120 + i * 47 + int(math.sin(t*.03+i)*8)
            pygame.draw.line(surface, (130, 150, 175, 45), (x, LETTER_H+40), (x-40, HEIGHT-LETTER_H-50), 1)
        _escape_subtitle(surface, "BIRIBEL", "Hold on.", 255)
    elif t < 500:
        # Clear readable side-view escape: truck starts, bursts through service gate, drives right.
        prog = (t - 300) / 200.0
        ease = 1 - (1 - max(0.0, min(1.0, prog))) ** 3
        ground_y = HEIGHT - LETTER_H - 118
        scroll = int(ease * 260)
        # Sky / rain / warehouse exterior.
        pygame.draw.rect(surface, (13, 15, 20), (0, LETTER_H, WIDTH, ground_y - LETTER_H))
        pygame.draw.rect(surface, (34, 31, 28), (-scroll, LETTER_H + 42, WIDTH + 340, ground_y - LETTER_H - 42))
        # Warehouse panels and grime.
        for x in range(-scroll - 80, WIDTH + 260, 110):
            pygame.draw.rect(surface, (27, 25, 23), (x, LETTER_H + 42, 104, ground_y - LETTER_H - 42), 1)
            pygame.draw.line(surface, (45, 38, 32), (x + 104, LETTER_H + 42), (x + 104, ground_y), 1)
        # Service gate behind truck, clearly breaking open.
        gate_x = 90 - scroll
        gate_y = LETTER_H + 92
        gate_w, gate_h = 260, 185
        pygame.draw.rect(surface, (8, 9, 10), (gate_x, gate_y, gate_w, gate_h))
        pygame.draw.rect(surface, (90, 72, 54), (gate_x, gate_y, gate_w, gate_h), 4)
        for i in range(8):
            gx = gate_x + i * (gate_w // 8)
            bend = int(ease * (20 if i % 2 == 0 else -14))
            pygame.draw.line(surface, (82, 68, 52), (gx, gate_y), (gx + bend, gate_y + gate_h), 3)
        gate_lbl = font_terminal_small.render(_T("m1.service_gate"), True, (135, 120, 95))
        surface.blit(gate_lbl, (gate_x + gate_w//2 - gate_lbl.get_width()//2, gate_y - 24))
        # Ground / wet road.
        pygame.draw.rect(surface, (10, 12, 14), (0, ground_y, WIDTH, HEIGHT - LETTER_H - ground_y))
        for y in range(ground_y + 12, HEIGHT - LETTER_H, 28):
            pygame.draw.line(surface, (30, 40, 50), (0, y), (WIDTH, y), 1)
        # Puddles and reflections.
        rng_p = random.Random(77)
        for i in range(12):
            px = (rng_p.randint(0, WIDTH + 260) - scroll * 2) % (WIDTH + 220) - 110
            py = ground_y + rng_p.randint(18, 86)
            pygame.draw.ellipse(surface, (20, 28, 38, 130), (px, py, rng_p.randint(45, 100), rng_p.randint(8, 18)))
        # Big readable side-view truck.
        # Drive fully off-screen by the end of the shot; previously it lingered in frame.
        truck_x = int(_lerp(140, WIDTH + 235, ease))
        truck_y = ground_y - 28 + int(math.sin(t * 0.19) * 2)
        # Headlight beam
        beam = pygame.Surface((330, 135), pygame.SRCALPHA)
        pygame.draw.polygon(beam, (255, 225, 145, 48), [(0, 48), (325, 6), (325, 126), (0, 82)])
        surface.blit(beam, (truck_x + 104, truck_y - 74))
        # Motion / rain spray trail
        for i in range(22):
            mx = truck_x - 25 - i * int(28 + 18 * ease)
            my = truck_y + 38 + random.Random(i + t // 2).randint(-16, 24)
            pygame.draw.line(surface, (100, 128, 150, 80), (mx, my), (mx - 44, my + 5), 2)
        # Truck shadow
        render_util.soft_shadow(surface, (truck_x - 112, truck_y + 46, 245, 38), 120)
        # Cargo body
        pygame.draw.rect(surface, (28, 39, 28), (truck_x - 106, truck_y - 32, 156, 72), border_radius=5)
        pygame.draw.rect(surface, (72, 84, 62), (truck_x - 106, truck_y - 32, 156, 72), 3, border_radius=5)
        pygame.draw.rect(surface, (18, 25, 18), (truck_x - 92, truck_y - 19, 96, 43), border_radius=3)
        pygame.draw.line(surface, C_KRAP_BLUE, (truck_x - 88, truck_y - 8), (truck_x - 2, truck_y - 8), 5)
        pygame.draw.line(surface, (210, 210, 205), (truck_x - 88, truck_y - 1), (truck_x - 2, truck_y - 1), 1)
        # Cab
        cab_pts = [(truck_x + 45, truck_y - 32), (truck_x + 93, truck_y - 28), (truck_x + 116, truck_y + 0), (truck_x + 106, truck_y + 40), (truck_x + 46, truck_y + 40)]
        pygame.draw.polygon(surface, (36, 50, 36), cab_pts)
        pygame.draw.polygon(surface, (80, 94, 70), cab_pts, 2)
        pygame.draw.polygon(surface, (24, 42, 52), [(truck_x + 58, truck_y - 20), (truck_x + 88, truck_y - 17), (truck_x + 101, truck_y + 0), (truck_x + 60, truck_y + 0)])
        # Headlights / tail lights
        pygame.draw.rect(surface, (245, 220, 130), (truck_x + 108, truck_y + 6, 9, 10))
        pygame.draw.rect(surface, (180, 35, 28), (truck_x - 111, truck_y - 16, 6, 12))
        pygame.draw.rect(surface, (180, 35, 28), (truck_x - 111, truck_y + 19, 6, 12))
        # Wheels, very obvious.
        for wx in (truck_x - 70, truck_x - 10, truck_x + 76):
            pygame.draw.circle(surface, (5, 6, 7), (wx, truck_y + 44), 23)
            pygame.draw.circle(surface, (46, 50, 50), (wx, truck_y + 44), 12)
            spoke_ang = t * 0.22
            for sp in range(4):
                a = spoke_ang + sp * math.pi / 2
                pygame.draw.line(surface, (85, 88, 84), (wx, truck_y + 44), (wx + math.cos(a)*11, truck_y + 44 + math.sin(a)*11), 2)
        # Shards from gate
        if t < 390:
            rng_s = random.Random(800 + t // 3)
            for i in range(20):
                sx = gate_x + gate_w - 30 + rng_s.randint(-15, 70) + int((t-300)*1.4)
                sy = gate_y + rng_s.randint(10, gate_h - 8) + int((t-300)*0.25)
                pygame.draw.rect(surface, (95, 78, 56), (sx, sy, rng_s.randint(4, 12), rng_s.randint(2, 7)))
        # Clear text overlay for readability.
        banner = font_terminal.render(_T("m1.escape_truck_moving"), True, (255, 180, 70))
        bg = pygame.Surface((banner.get_width()+28, banner.get_height()+10), pygame.SRCALPHA)
        bg.fill((0, 0, 0, 150))
        pygame.draw.rect(bg, (255, 180, 70, 120), bg.get_rect(), 1)
        surface.blit(bg, (WIDTH//2 - bg.get_width()//2, LETTER_H + 24))
        surface.blit(banner, (WIDTH//2 - banner.get_width()//2, LETTER_H + 29))
        if t < 372:
            _escape_subtitle(surface, "BIRIBEL", "Go, go, go!", 255)
        # M6 plant (docs/MISSION8_PLOT.md "Foreshadowing to Retrofit"): Vasile
        # pockets the notebook without reading it in front of Biribel.  He
        # already knew what was in it - in M6 the leaf in Volkov's copy says
        # so, and the M2 auth chain already carried his name.
        if 392 <= t < 470:
            _escape_subtitle(surface, "VASILE",
                             "Good. I've got it. Later. You need sleep.",
                             min(255, (t - 392) * 5, (470 - t) * 6))
    else:
        # Clear rear-view escape: visible truck body, tail-lights, road, warehouse glow behind.
        prog = min(1.0, (t - 500) / 160.0)
        horizon = LETTER_H + 120
        road_bot = HEIGHT - LETTER_H
        pygame.draw.rect(surface, (6, 8, 12), (0, LETTER_H, WIDTH, HEIGHT - 2*LETTER_H))
        # Distant warehouse / fire glow behind.
        pygame.draw.rect(surface, (24, 21, 19), (0, horizon - 52, WIDTH, 70))
        for i, x in enumerate((110, 210, 805, 900)):
            glow = pygame.Surface((170, 120), pygame.SRCALPHA)
            a = 30 + int(22 * math.sin(t*0.04 + i))
            pygame.draw.ellipse(glow, (255, 105, 30, max(12, a)), glow.get_rect())
            surface.blit(glow, (x, horizon - 82))
        # Road in perspective.
        road = [(WIDTH//2-78, horizon), (WIDTH//2+78, horizon), (WIDTH+180, road_bot), (-180, road_bot)]
        pygame.draw.polygon(surface, (10, 12, 16), road)
        for i in range(8):
            frac = i / 7
            y = int(horizon + frac*frac*(road_bot-horizon))
            pygame.draw.line(surface, (32, 42, 52), (0, y), (WIDTH, y), 1)
        pygame.draw.line(surface, (82, 82, 70), (WIDTH//2, horizon), (WIDTH//2-150, road_bot), 2)
        pygame.draw.line(surface, (82, 82, 70), (WIDTH//2, horizon), (WIDTH//2+150, road_bot), 2)
        # Draw visible rear truck shrinking into distance.
        # Stay locked to the perspective road centerline; only tiny suspension sway.
        tx = int(WIDTH // 2 + math.sin(t * 0.045) * (5 * (1.0 - prog)))
        ty = int(_lerp(road_bot - 88, horizon + 38, prog))
        sc = _lerp(1.12, 0.36, prog)
        tw = int(122 * sc)
        th = int(76 * sc)
        render_util.soft_shadow(surface, (tx - tw//2, ty + int(th*0.38), tw, max(8, int(22*sc))), 120)
        pygame.draw.rect(surface, (24, 35, 25), (tx - tw//2, ty - th//2, tw, th), border_radius=max(2, int(5*sc)))
        pygame.draw.rect(surface, (70, 84, 62), (tx - tw//2, ty - th//2, tw, th), max(1, int(2*sc)), border_radius=max(2, int(5*sc)))
        pygame.draw.rect(surface, (15, 22, 18), (tx - int(42*sc), ty - int(24*sc), int(84*sc), int(36*sc)), border_radius=max(1, int(3*sc)))
        # Rear windows/tail lights
        pygame.draw.rect(surface, (18, 28, 36), (tx - int(28*sc), ty - int(18*sc), int(18*sc), int(16*sc)))
        pygame.draw.rect(surface, (18, 28, 36), (tx + int(10*sc), ty - int(18*sc), int(18*sc), int(16*sc)))
        for side in (-1, 1):
            lx = tx + side * int(43*sc)
            ly = ty + int(20*sc)
            pygame.draw.rect(surface, (220, 35, 28), (lx - int(6*sc), ly - int(5*sc), max(3, int(12*sc)), max(3, int(10*sc))))
            refl = pygame.Surface((max(8, int(45*sc)), max(18, int(130*sc))), pygame.SRCALPHA)
            pygame.draw.ellipse(refl, (220, 35, 28, int(85*(1-prog))), refl.get_rect())
            surface.blit(refl, (lx - refl.get_width()//2, ly + int(7*sc)))
        fog = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        fog.fill((18, 24, 32, int(70 * prog)))
        surface.blit(fog, (0, 0))
        loc = font_location_sub.render(_T("m1.kilemeno_harbor_road_03_17"), True, (165, 165, 150))
        loc.set_alpha(min(255, max(0, (t-520)*4)))
        surface.blit(loc, (WIDTH//2 - loc.get_width()//2, LETTER_H + 34))
        if t > 570:
            _escape_subtitle(surface, "RADIO", "Signal clear. They're away.", min(255, (t-570)*5))
    # Polished handoff to the results screen:
    # 1) long radio acquisition hold, 2) slower signal corruption, 3) readable report boot card.
    if t > 620:
        # Phase 1: keep the road visible and hold the radio acquisition long enough to read.
        acq_alpha = min(230, max(0, int((t - 620) * 3)))
        if t < 720:
            readout = pygame.Surface((500, 70), pygame.SRCALPHA)
            readout.fill((0, 0, 0, min(175, acq_alpha)))
            pygame.draw.rect(readout, (50, 110, 150, min(165, acq_alpha)), readout.get_rect(), 1)
            pygame.draw.rect(readout, C_KRAP_BLUE, (0, 0, 4, readout.get_height()))
            r1 = font_terminal.render(_T("m1.radio_signal_acquired"), True, (90, 170, 220))
            r2 = font_terminal_small.render(_T("m1.exfil_confirmed_packetizing_fiel"), True, (165, 150, 125))
            r1.set_alpha(acq_alpha)
            r2.set_alpha(acq_alpha)
            surface.blit(readout, (WIDTH // 2 - 250, LETTER_H + 70))
            surface.blit(r1, (WIDTH // 2 - r1.get_width() // 2, LETTER_H + 84))
            surface.blit(r2, (WIDTH // 2 - r2.get_width() // 2, LETTER_H + 116))
        # Phase 2: signal tears slowly take over the road image.
        if t >= 700:
            glitch_t = min(1.0, (t - 700) / 110.0)
            rng_g = random.Random(8800 + t)
            for _ in range(4 + int(glitch_t * 16)):
                gy = rng_g.randint(LETTER_H, HEIGHT - LETTER_H)
                gh = rng_g.randint(2, 10)
                strip = pygame.Surface((WIDTH, gh), pygame.SRCALPHA)
                col = rng_g.choice([(70, 160, 220), (255, 130, 50), (230, 230, 220)])
                strip.fill((*col, rng_g.randint(16, 70)))
                surface.blit(strip, (rng_g.randint(-35, 35), gy))
            for _ in range(int(45 * glitch_t)):
                sx = rng_g.randint(0, WIDTH - 1)
                sy = rng_g.randint(LETTER_H, HEIGHT - LETTER_H - 1)
                shade = rng_g.randint(90, 210)
                surface.set_at((sx, sy), (shade, shade, shade))
            dark = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
            dark.fill((0, 0, 0, int(145 * glitch_t)))
            surface.blit(dark, (0, 0))
        # Phase 3: report receiver card has a much slower boot/read time.
        if t >= 790:
            report_t = min(1.0, (t - 790) / 120.0)
            wipe = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
            wipe.fill((2, 5, 9, int(235 * report_t)))
            surface.blit(wipe, (0, 0))
            card_w, card_h = 600, 240
            card_x = WIDTH // 2 - card_w // 2
            card_y = HEIGHT // 2 - card_h // 2
            card_alpha = int(255 * report_t)
            card = pygame.Surface((card_w, card_h), pygame.SRCALPHA)
            card.fill((5, 11, 18, min(238, card_alpha)))
            pygame.draw.rect(card, (45, 88, 126, min(180, card_alpha)), card.get_rect(), 1)
            pygame.draw.rect(card, C_KRAP_BLUE, (0, 0, 5, card_h))
            pygame.draw.line(card, (45, 88, 126, min(120, card_alpha)), (22, 62), (card_w - 22, 62), 1)
            surface.blit(card, (card_x, card_y))
            def _fade_text(surf, x, y, a=card_alpha):
                surf.set_alpha(max(0, min(255, int(a))))
                surface.blit(surf, (x, y))
            eyebrow = font_terminal_small.render(_T("m1.krap_archive_link_established"), True, (80, 160, 215))
            _fade_text(eyebrow, card_x + 24, card_y + 22, min(card_alpha, max(0, (t - 790) * 5)))
            stamp = font_terminal_small.render(_T("m1.exfil_confirmed"), True, (80, 220, 135))
            _fade_text(stamp, card_x + card_w - stamp.get_width() - 24, card_y + 22, min(card_alpha, max(0, (t - 815) * 5)))
            title = font_terminal.render(_T("m1.field_report_received"), True, (220, 222, 210))
            _fade_text(title, card_x + 38, card_y + 88, min(card_alpha, max(0, (t - 835) * 5)))
            sub = font_prompt.render(_T("m1.operation_black_notebook_uploadi"), True, (170, 160, 130))
            _fade_text(sub, card_x + 38, card_y + 126, min(card_alpha, max(0, (t - 855) * 5)))
            bar_w, bar_h = card_w - 76, 6
            bx = card_x + 38
            by = card_y + 178
            pygame.draw.rect(surface, (12, 20, 28), (bx, by, bar_w, bar_h))
            # Deliberately slow upload fill so the player can actually read the report handoff.
            upload_t = min(1.0, max(0.0, (t - 850) / 170.0))
            pygame.draw.rect(surface, C_KRAP_BLUE, (bx, by, int(bar_w * upload_t), bar_h))
            pct = font_terminal_small.render(_T("m1.upload_pct", pct="{:03d}".format(int(upload_t * 100))), True, (95, 135, 165))
            _fade_text(pct, bx + bar_w - pct.get_width(), by + 12, min(card_alpha, max(0, (t - 850) * 4)))
            if t > 1025:
                ready_alpha = min(255, (t - 1025) * 7)
                ready = font_terminal_small.render(_T("m1.report_ready"), True, C_ORANGE)
                _fade_text(ready, card_x + card_w // 2 - ready.get_width() // 2, card_y + 202, ready_alpha)
    draw_vignette(surface, strength=185)
    draw_scanlines(surface)
    draw_letterbox(surface)
# ── Static bake + lighting fixtures (Mission 3 pipeline, Mission 1 wiring) ──
# Mission 1 re-rendered its whole tile grid, walls and desk bodies every
# frame. The static half (floors, walls, desk bodies, bay label, dressing)
# is baked into chunked offscreen surfaces once; only animated state
# (breach markers, doors, desk indicator dots, blood, actors) draws live.
_M1_CAM = [0, 0]
_M1_SOLID_TILES = ("C", "W", "D")


def _m1_static_layer():
    sig = (id(mission1_map), id(STATE.walls), id(STATE.desks))
    return staticlayer.get_layer("m1", sig, MAP_W * TILE_SIZE, MAP_H * TILE_SIZE)


def _m1_wing_name():
    """Grading zone: warm tungsten inside the warehouse, cool night outside."""
    p = STATE.player
    if not p:
        return "slums"
    if 11 * TILE_SIZE <= p.rect.centery < 21 * TILE_SIZE:
        return "warehouse"
    return "slums"


def _m1_solid_world(wx, wy):
    """Light-blocking predicate over the Mission 1 tilemap."""
    tx = int(wx) // TILE_SIZE
    ty = int(wy) // TILE_SIZE
    if not (0 <= ty < len(mission1_map)):
        return True
    row = mission1_map[ty]
    if not (0 <= tx < len(row)):
        return True
    return row[tx] in _M1_SOLID_TILES


def _m1_light_sig():
    return render_util.doors_anim_sig(getattr(STATE, "doors", ()))


# Lamp fixtures in tile coords: (col, row, radius, color, key).
_M1_LAMPS = (
    # Warehouse hall - warm tungsten ceiling rows.
    (5, 12, 170, (255, 232, 190), "wh_a"),
    (11, 12, 170, (255, 232, 190), "wh_b"),
    (17, 12, 170, (255, 232, 190), "wh_c"),
    (22, 12, 160, (255, 232, 190), "wh_d"),
    (8, 14, 150, (255, 232, 190), "wh_e"),
    (15, 14, 150, (255, 232, 190), "wh_f"),
    (8, 17, 160, (255, 232, 190), "wh_g"),
    (15, 17, 160, (255, 232, 190), "wh_h"),
    (21, 17, 150, (255, 232, 190), "wh_i"),
    # Office desk accents - cool monitor spill.
    (13, 12, 90, (150, 200, 220), "dk_a"),
    (20, 12, 90, (150, 200, 220), "dk_b"),
    # Gate bulkheads.
    (8, 11, 120, (255, 236, 200), "gate_a"),
    (14, 16, 120, (255, 236, 200), "gate_b"),
    # Slum street lamps - cool night.
    (5, 3, 150, (190, 210, 255), "sl_a"),
    (13, 6, 150, (190, 210, 255), "sl_b"),
    (21, 7, 150, (190, 210, 255), "sl_c"),
    # Exfil tripod work-light.
    (21, 21, 140, (235, 245, 225), "ex_a"),
)


def _push_m1_lights(cam_x, cam_y, t):
    lb = lighting.buffer()
    render_util.push_lamps(
        lb,
        ((tx * TILE_SIZE, ty * TILE_SIZE, r, col, key)
         for tx, ty, r, col, key in _M1_LAMPS),
        cam_x, cam_y, t, _m1_solid_world)
    # Bay-door moonlight spill - grows as the doors roll open.
    bay_open = 0.0
    for d in getattr(STATE, "doors", ()):
        if getattr(d, "is_bay", False):
            bay_open = max(bay_open, getattr(d, "anim_progress", 0.0))
    if bay_open > 0.02:
        bx = 14 * TILE_SIZE + 32 - cam_x
        by = 20 * TILE_SIZE - cam_y
        if render_util.screen_visible(bx, by, 1, 1):
            lb.cone(bx, by, math.radians(90), 26, 230, (200, 220, 255),
                    0.35 * bay_open, caster=_m1_solid_world,
                    cam=(cam_x, cam_y), key="bayspill")
            lb.light(bx, by + 60, 150, (200, 220, 255), 0.30 * bay_open,
                     caster=_m1_solid_world, cam=(cam_x, cam_y), key="baypool")


def _render_m1_bg(target, cam_x, cam_y):
    """Static tilemap pass: floor grid, container/warehouse walls, desk bodies."""
    start_tx = int(cam_x // FLOOR_TILE_SIZE) * FLOOR_TILE_SIZE
    start_ty = int(cam_y // FLOOR_TILE_SIZE) * FLOOR_TILE_SIZE
    warehouse_y_start = 11 * TILE_SIZE
    warehouse_y_end = 20 * TILE_SIZE
    for tx in range(
        start_tx - FLOOR_TILE_SIZE,
        int(cam_x + WIDTH + FLOOR_TILE_SIZE * 2),
        FLOOR_TILE_SIZE,
    ):
        for ty in range(
            start_ty - FLOOR_TILE_SIZE,
            int(cam_y + HEIGHT + FLOOR_TILE_SIZE * 2),
            FLOOR_TILE_SIZE,
        ):
            tile = (
                FLOOR_TILE
                if (warehouse_y_start <= ty <= warehouse_y_end)
                else SLUM_FLOOR
            )
            target.blit(tile, (tx - cam_x, ty - cam_y))
    container_tiles = [
        CONTAINER_TILE_RED,
        CONTAINER_TILE_BLUE,
        CONTAINER_TILE_RUST,
        CONTAINER_TILE_GREY,
    ]
    for wall in STATE.walls:
        dr = pygame.Rect(wall.x - cam_x, wall.y - cam_y, TILE_SIZE, TILE_SIZE)
        target.blit(wall_shadow, (dr.x - 4, dr.y - 4))
        col = wall.x // TILE_SIZE
        row = wall.y // TILE_SIZE
        if (col, row) in STATE.warehouse_walls_set:
            target.blit(WAREHOUSE_WALL, (dr.x, dr.y))
        else:
            tile_idx = (col + row) % 4
            target.blit(container_tiles[tile_idx], (dr.x, dr.y))
    for desk in STATE.desks:
        dx = desk["x"] - cam_x
        dy = desk["y"] - cam_y
        if -50 < dx < WIDTH + 50 and -50 < dy < HEIGHT + 50:
            _draw_m1_desk_body(target, dx, dy)
    bay_x = 15 * TILE_SIZE + 32 - cam_x
    bay_y = 19 * TILE_SIZE + 32 - cam_y
    if -50 < bay_x < WIDTH + 50 and -50 < bay_y < HEIGHT + 50:
        label = font_terminal_small.render(_T("m1.bay_door"), True, (150, 140, 120))
        target.blit(label, (bay_x - label.get_width() // 2, bay_y - 40))


def _draw_m1_desk_body(target, dx, dy):
    """Static desk geometry (shadow, wood, papers, mug). Indicator dot + label stay dynamic."""
    # ── Desk shadow ──
    shad = pygame.Surface((72, 54), pygame.SRCALPHA)
    pygame.draw.rect(shad, (0, 0, 0, 45), (0, 0, 72, 54), border_radius=3)
    target.blit(shad, (dx - 34, dy - 23))
    # ── Desk surface ──
    pygame.draw.rect(target, (70, 52, 32), (dx - 32, dy - 22, 64, 46), border_radius=2)
    # wood grain lines
    for gi in range(4):
        gy = dy - 18 + gi * 10
        pygame.draw.line(target, (62, 46, 28), (dx - 30, gy), (dx + 30, gy), 1)
    pygame.draw.rect(target, (95, 72, 44), (dx - 32, dy - 22, 64, 46), 1, border_radius=2)
    # ── Desk legs (visible corners in top-down) ──
    for lx2, ly2 in [(-28, -18), (24, -18), (-28, 18), (24, 18)]:
        pygame.draw.rect(target, (48, 36, 22), (dx + lx2, dy + ly2, 6, 6))
    # ── Papers / scattered docs on desk ──
    pygame.draw.rect(target, (220, 215, 200), (dx - 20, dy - 14, 28, 20), border_radius=1)
    pygame.draw.rect(target, (200, 195, 178), (dx - 20, dy - 14, 28, 20), 1, border_radius=1)
    for li in range(3):
        pygame.draw.line(target, (140, 135, 120), (dx - 16, dy - 8 + li * 5), (dx + 4, dy - 8 + li * 5), 1)
    # ── Folded note / envelope ──
    pygame.draw.rect(target, (230, 220, 190), (dx + 6, dy - 6, 18, 14), border_radius=1)
    pygame.draw.line(target, (190, 180, 155), (dx + 6, dy - 6), (dx + 15, dy + 1), 1)
    pygame.draw.line(target, (190, 180, 155), (dx + 24, dy - 6), (dx + 15, dy + 1), 1)
    # ── Coffee mug ──
    pygame.draw.circle(target, (42, 32, 24), (dx + 22, dy + 12), 7)
    pygame.draw.circle(target, (58, 44, 30), (dx + 22, dy + 12), 7, 1)
    pygame.draw.circle(target, (80, 55, 20), (dx + 22, dy + 12), 4)  # coffee inside


def _draw_m1_desk_overlays(cam_x, cam_y):
    """Per-frame desk state: read/unread indicator dot + label."""
    for desk in STATE.desks:
        dx = desk["x"] - cam_x
        dy = desk["y"] - cam_y
        if -50 < dx < WIDTH + 50 and -50 < dy < HEIGHT + 50:
            # ── Unread/read indicator dot ──
            dot_col = (100, 220, 100) if desk["read"] else (240, 190, 50)
            glow2 = get_glow(7, dot_col, 70)
            screen.blit(glow2, (dx - 3, dy - 21))
            pygame.draw.circle(screen, dot_col, (dx, dy - 14), 4)
            label = font_terminal_small.render(_T("m1.desk"), True, (150, 140, 120))
            screen.blit(label, (dx - label.get_width() // 2, dy + 28))


def _m1_hash(col, row, n):
    """Deterministic spatial hash for dressing placement (no per-frame shimmer)."""
    h = (col * 73856093) ^ (row * 19349663)
    h = (h ^ (h >> 13)) * 1274126177
    return (h ^ (h >> 16)) % n


def _m1_prop_overlaps_solid(kind, tx, ty, arg):
    """True when a dressing prop's footprint intersects wall/door tiles."""
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
            if mission1_map[row][col] in _M1_SOLID_TILES:
                return True
    return False


# Hand-authored dressing anchors: (kind, tile_col, tile_row, arg).
_M1_DRESSING_PROPS = (
    ("crates", 4, 13, 1.0),
    ("crates", 23, 12, 0.85),
    ("barrels", 25, 17, 3),
    ("barrels", 2, 8, 2),
    ("coil", 10, 13, 1.0),
)


def _draw_m1_hall_fixture(target, sx, sy):
    """Ceiling lamp housing + glowing tube (top-down) with halo."""
    halo = get_glow(26, (255, 232, 190), 90)
    target.blit(halo, (int(sx - 26), int(sy - 26)))
    pygame.draw.rect(target, (30, 30, 32), (int(sx - 26), int(sy - 6), 52, 12))
    pygame.draw.rect(target, (255, 240, 210), (int(sx - 22), int(sy - 3), 44, 6))


def _draw_m1_street_post(target, sx, sy):
    """Slum lamp post: pole, arm, head + cool halo."""
    halo = get_glow(24, (190, 210, 255), 90)
    target.blit(halo, (int(sx - 24), int(sy - 52)))
    pygame.draw.rect(target, (25, 27, 30), (int(sx - 2), int(sy - 46), 4, 46))
    pygame.draw.rect(target, (25, 27, 30), (int(sx - 2), int(sy - 50), 16, 4))
    pygame.draw.rect(target, (200, 215, 255), (int(sx + 10), int(sy - 52), 8, 5))


def _draw_m1_bulkhead(target, sx, sy):
    """Wall-mounted gate bulkhead light + warm glow."""
    halo = get_glow(18, (255, 236, 200), 90)
    target.blit(halo, (int(sx - 18), int(sy - 18)))
    pygame.draw.rect(target, (35, 33, 30), (int(sx - 10), int(sy - 6), 20, 12))
    pygame.draw.rect(target, (255, 240, 205), (int(sx - 7), int(sy - 3), 14, 6))


def _draw_m1_tripod(target, sx, sy):
    """Exfil tripod work-light + halo."""
    halo = get_glow(24, (235, 245, 225), 110)
    target.blit(halo, (int(sx - 24), int(sy - 58)))
    for dx in (-10, 0, 10):
        pygame.draw.line(target, (40, 42, 44), (int(sx), int(sy - 44)), (int(sx + dx), int(sy)), 2)
    pygame.draw.rect(target, (60, 62, 64), (int(sx - 8), int(sy - 52), 16, 8))
    pygame.draw.rect(target, (240, 248, 230), (int(sx - 6), int(sy - 50), 12, 4))


def _draw_m1_static_dressing(target, cam_x, cam_y):
    """Baked set-dressing pass: joints, grime, props, pipes, fixtures, tracks."""
    # ── Concrete expansion joints across the warehouse floor band ──
    y0 = 11 * TILE_SIZE - cam_y
    y1 = 21 * TILE_SIZE - cam_y
    if y1 >= 0 and y0 <= HEIGHT:
        for gx in range(0, MAP_W * TILE_SIZE + 1, FLOOR_TILE_SIZE):
            sx = gx - cam_x
            if -2 < sx < WIDTH + 2:
                pygame.draw.line(target, (36, 34, 30),
                                 (int(sx), int(max(0, y0))), (int(sx), int(min(HEIGHT, y1))), 1)
        for k in range(6):
            sy = 11 * TILE_SIZE + k * FLOOR_TILE_SIZE - cam_y
            if -2 < sy < HEIGHT + 2:
                pygame.draw.line(target, (36, 34, 30),
                                 (int(max(0, TILE_SIZE - cam_x)), int(sy)),
                                 (int(min(WIDTH, 27 * TILE_SIZE - cam_x)), int(sy)), 1)
    # ── Seeded cracks + grime blotches on the 128px floor grid ──
    gx0 = max(0, int(cam_x // FLOOR_TILE_SIZE) - 1)
    gx1 = int((cam_x + WIDTH) // FLOOR_TILE_SIZE) + 2
    gy0 = max(0, int(cam_y // FLOOR_TILE_SIZE) - 1)
    gy1 = int((cam_y + HEIGHT) // FLOOR_TILE_SIZE) + 2
    for grow in range(gy0, gy1):
        for gcol in range(gx0, gx1):
            h = _m1_hash(gcol, grow, 100)
            bx = gcol * FLOOR_TILE_SIZE - cam_x
            by = grow * FLOOR_TILE_SIZE - cam_y
            if h < 22:
                # grime blotch
                w, hh = 30 + _m1_hash(gcol + 7, grow, 40), 20 + _m1_hash(gcol, grow + 3, 30)
                ox, oy = _m1_hash(gcol + 1, grow + 1, 80), _m1_hash(gcol + 2, grow + 2, 80)
                pygame.draw.ellipse(target, (30, 28, 26),
                                    (int(bx + ox), int(by + oy), int(w), int(hh)))
            if h >= 60 and h < 78:
                # crack polyline
                pts = []
                px, py = bx + _m1_hash(gcol, grow, 120), by + _m1_hash(grow, gcol, 120)
                for _ in range(4):
                    pts.append((int(px), int(py)))
                    px += _m1_hash(int(px), int(py), 40) - 20
                    py += _m1_hash(int(py), int(px), 40) - 20
                if len(pts) > 1:
                    pygame.draw.lines(target, (28, 26, 24), False, pts, 1)
    # ── Hand-authored props (validated against the tilemap) ──
    for kind, ptx, pty, arg in _M1_DRESSING_PROPS:
        if _m1_prop_overlaps_solid(kind, ptx, pty, arg):
            continue
        ax = ptx * TILE_SIZE + TILE_SIZE // 2 - cam_x
        ay = pty * TILE_SIZE + TILE_SIZE // 2 - cam_y
        if not render_util.screen_visible(ax - 60, ay - 60, 120, 120):
            continue
        if kind == "crates":
            _props.crate_stack(target, ax, ay, arg)
        elif kind == "barrels":
            _props.barrels(target, ax, ay, int(arg))
        elif kind == "coil":
            _props.cable_coil(target, ax, ay)
    # ── Wall pipes (utility runs along solid walls) ──
    _props.wall_pipe(target, 32 - cam_x, 11 * TILE_SIZE + 20 - cam_y,
                     32 - cam_x, 14 * TILE_SIZE + 44 - cam_y)
    _props.wall_pipe(target, 10 * TILE_SIZE - cam_x, 10 * TILE_SIZE + 50 - cam_y,
                     18 * TILE_SIZE - cam_x, 10 * TILE_SIZE + 50 - cam_y)
    _props.wall_pipe(target, 2 * TILE_SIZE - cam_x, 15 * TILE_SIZE + 50 - cam_y,
                     13 * TILE_SIZE - cam_x, 15 * TILE_SIZE + 50 - cam_y)
    # ── Oil stain by the miniboss + scattered papers near desks ──
    ox, oy = 10 * TILE_SIZE + 32 - cam_x, 17 * TILE_SIZE + 40 - cam_y
    if render_util.screen_visible(ox - 40, oy - 20, 80, 40):
        pygame.draw.ellipse(target, (22, 21, 20), (int(ox - 34), int(oy - 14), 68, 28))
        pygame.draw.ellipse(target, (30, 28, 26), (int(ox - 20), int(oy - 8), 40, 16))
    for ptx, pty in ((12, 12), (19, 13), (7, 17)):
        px = ptx * TILE_SIZE + 20 - cam_x
        py = pty * TILE_SIZE + 44 - cam_y
        if render_util.screen_visible(px, py, 20, 14):
            pygame.draw.rect(target, (205, 198, 180), (int(px), int(py), 14, 10))
            pygame.draw.rect(target, (150, 142, 125), (int(px), int(py), 14, 10), 1)
    # ── Bay chevrons + stencil on the apron ──
    for i in range(6):
        cx0 = (11 + i) * TILE_SIZE - cam_x
        cy0 = 20 * TILE_SIZE + 8 - cam_y
        if render_util.screen_visible(cx0, cy0, TILE_SIZE, 20):
            col = (170, 140, 40) if i % 2 == 0 else (25, 25, 25)
            pygame.draw.polygon(target, col, [
                (int(cx0 + 8), int(cy0)), (int(cx0 + 24), int(cy0)),
                (int(cx0 + 12), int(cy0 + 18)), (int(cx0 - 4), int(cy0 + 18))])
    stencil = font_terminal_small.render(_T("m1.bay_03"), True, (170, 150, 90))
    stx, sty = 14 * TILE_SIZE + 32 - cam_x, 20 * TILE_SIZE + 40 - cam_y
    if render_util.screen_visible(stx - 40, sty, 80, 16):
        stencil.set_alpha(160)
        target.blit(stencil, (int(stx - stencil.get_width() // 2), int(sty)))
    # ── Tire tracks: bay apron curving to the exfil ──
    x0, y0 = 14 * TILE_SIZE + 32 - cam_x, 20 * TILE_SIZE + 32 - cam_y
    x1, y1 = 21 * TILE_SIZE + 32 - cam_x, 21 * TILE_SIZE + 32 - cam_y
    if render_util.screen_visible(min(x0, x1) - 20, min(y0, y1) - 20,
                                  abs(x1 - x0) + 40, abs(y1 - y0) + 40):
        dx, dy = x1 - x0, y1 - y0
        dist = max(1, math.hypot(dx, dy))
        nx, ny = -dy / dist, dx / dist
        for side in (-7, 7):
            prev = None
            for s in range(0, int(dist), 14):
                q = s / dist
                cxp = x0 + dx * q + nx * side
                cyp = y0 + dy * q + ny * side
                if s % 28 < 14:
                    if prev is not None:
                        pygame.draw.line(target, (30, 28, 26),
                                         (int(prev[0]), int(prev[1])), (int(cxp), int(cyp)), 3)
                    prev = (cxp, cyp)
                else:
                    prev = None
    # ── Lamp fixtures + floor light pools ──
    for tx, ty, _r, _col, key in _M1_LAMPS:
        fam = key.split("_")[0]
        sx = tx * TILE_SIZE + TILE_SIZE // 2 - cam_x
        sy = ty * TILE_SIZE + TILE_SIZE // 2 - cam_y
        if not render_util.screen_visible(sx - 60, sy - 70, 120, 140):
            continue
        if fam == "wh":
            _draw_m1_hall_fixture(target, sx, sy)
            render_util.add_radial(target, sx, sy, 34, (255, 225, 175), 24)
        elif fam == "sl":
            _draw_m1_street_post(target, sx, sy)
        elif fam == "gate":
            _draw_m1_bulkhead(target, sx, sy)
        elif fam == "ex":
            _draw_m1_tripod(target, sx, sy)


def _bake_m1_static(surf, ox, oy):
    _render_m1_bg(surf, ox, oy)
    _draw_m1_static_dressing(surf, ox, oy)


def game_draw(fcx: float, fcy: float) -> None:
    if artpack.enabled():
        lighting.buffer().begin_frame(_m1_wing_name(), _m1_light_sig())
    _game_draw_inner(fcx, fcy)
    if artpack.enabled():
        _push_m1_lights(_M1_CAM[0], _M1_CAM[1], _now_s())
        lighting.buffer().composite(screen, _now_s())


_M1_PICKUP_VARIANTS = {"mag": 0, "keycard": 1, "bandage": 2, "bottle": 3}


def _paint_m1_pickup_icon(surface, kind, px, py):
    """Ground-pickup icon centred on px/py (opaque primitives inside a 32 x 32 box)."""
    if kind == "mag":
        top_w, bot_w, h = 14, 11, 24
        taper = (top_w - bot_w) // 2
        mg_pts = [
            (px - top_w // 2, py - h // 2),
            (px + top_w // 2, py - h // 2),
            (px + taper + bot_w // 2, py + h // 2),
            (px + taper - bot_w // 2, py + h // 2),
        ]
        pygame.draw.polygon(surface, (100, 95, 87), mg_pts)
        pygame.draw.polygon(surface, (255, 210, 40), mg_pts, 1)
        for bi in range(5):
            by = py - h // 2 + 5 + bi * 3
            pygame.draw.circle(surface, (220, 185, 45), (px, by), 2)
    elif kind == "keycard":
        pygame.draw.rect(surface, (200, 200, 200), (px - 8, py - 12, 16, 24))
        pygame.draw.rect(surface, (255, 50, 50), (px - 8, py - 6, 16, 6))
        pygame.draw.rect(surface, (100, 100, 100), (px - 8, py - 12, 16, 24), 1)
    elif kind == "bandage":
        pygame.draw.rect(
            surface, (240, 240, 240), (px - 10, py - 10, 20, 20), border_radius=3
        )
        pygame.draw.rect(
            surface, (180, 180, 180), (px - 10, py - 10, 20, 20), 1, border_radius=3
        )
        pygame.draw.rect(surface, (220, 40, 40), (px - 2, py - 6, 4, 12))
        pygame.draw.rect(surface, (220, 40, 40), (px - 6, py - 2, 12, 4))
    elif kind == "bottle":
        pygame.draw.rect(surface, (60, 60, 60), (px - 2, py - 12, 4, 2))
        pygame.draw.rect(surface, (80, 55, 25), (px - 1, py - 10, 2, 4))
        pygame.draw.rect(surface, (115, 75, 35), (px - 5, py - 6, 10, 16), border_radius=2)
        pygame.draw.rect(surface, (255, 155, 55), (px - 3, py - 4, 2, 12))
        pygame.draw.rect(surface, (50, 30, 15), (px - 5, py - 6, 10, 16), 1, border_radius=2)


def _paint_m1_exfil_headlights(surface, ex, ey):
    """Headlight glow + lenses of the exfil truck; drawn live over the baked body because the
    translucent glow overlaps the soft ground shadow (two translucent layers cannot share one
    sprite bit-exactly). Nothing drawn later by the truck painter overlaps this area."""
    cab_x = int(ex + 18)
    for hy in (int(ey - 14), int(ey + 8)):
        glow = get_glow(9, (255, 230, 150), 70)
        surface.blit(glow, (cab_x + 32, hy - 6))
        pygame.draw.ellipse(surface, (245, 225, 150), (cab_x + 38, hy, 8, 6))


def _paint_m1_exfil_truck(surface, ex, ey, headlights=True):
    """Top-down KRAP exfil flatbed parked at screen position ex/ey (faces right). Bake source of
    game.art.m1.exfil_truck (baked with headlights=False); everything drawn lies inside
    (ex-60, ey-34) .. (ex+76, ey+36)."""
    render_util.soft_shadow(surface, (int(ex - 52), int(ey - 20), 112, 52), 90)
    # Chassis rail peeking under the body.
    pygame.draw.rect(surface, (18, 20, 18), (int(ex - 50), int(ey - 3), 102, 6))
    # Cargo bed: base + side walls + tarp + crates + tie-downs.
    pygame.draw.rect(surface, (20, 26, 20), (int(ex - 50), int(ey - 22), 68, 44), border_radius=3)
    pygame.draw.rect(surface, (52, 64, 46), (int(ex - 50), int(ey - 22), 68, 44), 2, border_radius=3)
    pygame.draw.line(surface, (86, 102, 76), (int(ex - 47), int(ey - 19)), (int(ex + 15), int(ey - 19)), 1)
    pygame.draw.rect(surface, (46, 58, 42), (int(ex - 46), int(ey - 16), 60, 32), border_radius=2)
    # Tarp fold seams.
    for ci in range(1, 3):
        pygame.draw.line(surface, (34, 44, 32),
            (int(ex - 46 + ci * 20), int(ey - 16)),
            (int(ex - 46 + ci * 20), int(ey + 16)), 1)
    # Cargo crates lashed under the tarp edges.
    for cxo, cyo in ((-36, -8), (-16, 4)):
        rx, ry = int(ex + cxo), int(ey + cyo)
        pygame.draw.rect(surface, (96, 76, 48), (rx - 9, ry - 6, 18, 12), border_radius=1)
        pygame.draw.rect(surface, (52, 38, 24), (rx - 9, ry - 6, 18, 12), 1, border_radius=1)
        pygame.draw.line(surface, (52, 38, 24), (rx - 9, ry), (rx + 9, ry), 1)
    # Rear gate + tail-lights + bumper.
    pygame.draw.rect(surface, (30, 36, 28), (int(ex - 54), int(ey - 20), 6, 40), border_radius=2)
    pygame.draw.rect(surface, (180, 40, 30), (int(ex - 54), int(ey - 20), 4, 7))
    pygame.draw.rect(surface, (180, 40, 30), (int(ex - 54), int(ey + 13), 4, 7))
    pygame.draw.rect(surface, (24, 24, 26), (int(ex - 56), int(ey - 24), 3, 48), border_radius=1)
    # Cab: body + roof highlight + door seam + windshield + hood.
    cab_x = int(ex + 18)
    pygame.draw.rect(surface, (20, 26, 20), (cab_x, int(ey - 22), 34, 44), border_radius=4)
    pygame.draw.rect(surface, (44, 56, 40), (cab_x, int(ey - 22), 34, 44), border_radius=4)
    pygame.draw.rect(surface, (72, 86, 64), (cab_x, int(ey - 22), 34, 44), 1, border_radius=4)
    pygame.draw.line(surface, (96, 112, 88), (cab_x + 4, int(ey - 19)), (cab_x + 28, int(ey - 19)), 1)
    pygame.draw.line(surface, C_KRAP_BLUE, (cab_x + 4, int(ey - 2)), (cab_x + 14, int(ey - 2)), 3)
    pygame.draw.line(surface, (210, 210, 205), (cab_x + 4, int(ey + 1)), (cab_x + 14, int(ey + 1)), 1)
    pygame.draw.rect(surface, (16, 24, 26), (cab_x + 18, int(ey - 16), 12, 32), border_radius=2)
    pygame.draw.rect(surface, (90, 120, 130), (cab_x + 18, int(ey - 16), 12, 32), 1, border_radius=2)
    pygame.draw.line(surface, (150, 190, 200), (cab_x + 20, int(ey - 13)), (cab_x + 27, int(ey - 13)), 1)
    pygame.draw.rect(surface, (48, 60, 44), (cab_x + 30, int(ey - 14), 10, 28), border_radius=2)
    pygame.draw.rect(surface, (28, 36, 28), (cab_x + 30, int(ey - 14), 10, 28), 1, border_radius=2)
    if headlights:
        _paint_m1_exfil_headlights(surface, ex, ey)
    # Wheels: tire + sidewall + hub (3 axles, both sides).
    for wx in (int(ex - 36), int(ex + 4), int(ex + 28)):
        for wy in (int(ey - 27), int(ey + 21)):
            pygame.draw.ellipse(surface, (8, 8, 10), (wx - 8, wy - 5, 16, 10))
            pygame.draw.ellipse(surface, (40, 42, 46), (wx - 8, wy - 5, 16, 10), 1)
            pygame.draw.ellipse(surface, (70, 74, 80), (wx - 4, wy - 3, 8, 6))
            pygame.draw.circle(surface, (28, 28, 30), (wx, wy), 1)
    # KRAP door stencil.
    krap_lbl = font_terminal_small.render(_T("m1.krap"), True, (140, 185, 220))
    surface.blit(krap_lbl, (cab_x + 2, int(ey - 9)))


def _m1_hp_panel(w, h):
    """M1's plain HP backdrop (the shared health_bar takes a panel factory)."""
    surf = pygame.Surface((w, h), pygame.SRCALPHA)
    pygame.draw.rect(surf, (0, 0, 0, 140), (0, 0, w, h))
    return surf


def _m1_panel_140(w, h):
    """M1's 140-alpha panel backdrop (the shared art_cache.get_panel_bg with M1's alpha)."""
    return get_panel_bg(w, h, alpha=140)


def _game_draw_inner(fcx: float, fcy: float) -> None:
    screen.fill(C_BG_GAME)
    # Render from an integer camera (like M2/M3). This removes the tile/prop
    # seam shimmer that happens when the camera scrolls by fractional pixels.
    fcx, fcy = round(fcx), round(fcy)
    _M1_CAM[0], _M1_CAM[1] = fcx, fcy
    if staticlayer.enabled():
        if not _m1art.blit_layer(screen, "world_static", fcx, fcy):
            _m1_static_layer().blit(screen, fcx, fcy, _bake_m1_static)
    else:
        _render_m1_bg(screen, fcx, fcy)
        _draw_m1_static_dressing(screen, fcx, fcy)
    _draw_m1_desk_overlays(fcx, fcy)
    for marker in STATE.breach_markers[:]:
        mx, my, timer = marker
        mx -= fcx
        my -= fcy
        if -50 < mx < WIDTH + 50 and -50 < my < HEIGHT + 50:
            alpha = min(255, timer * 2)
            for i in range(3):
                radius = 8 + i * 4
                s = get_glow(radius, (255, 80, 20), 255)
                s.set_alpha(alpha // (i + 1))
                screen.blit(s, (mx - radius, my - radius))
        marker[2] -= 1
        if marker[2] <= 0:
            STATE.breach_markers.remove(marker)
    # (Static desk bodies + bay label are baked; overlays drawn above.)
    left_bay = None
    for d in STATE.doors:
        if d.is_bay and (left_bay is None or d.rect.x < left_bay.rect.x):
            left_bay = d
    for d in STATE.doors:
        dr = pygame.Rect(d.rect.x - fcx, d.rect.y - fcy, TILE_SIZE, TILE_SIZE)
        if d.is_bay:
            if d is not left_bay:
                if STATE.player and not STATE.player_dead:
                    pdist = math.hypot(
                        STATE.player.rect.centerx - d.rect.centerx,
                        STATE.player.rect.centery - d.rect.centery,
                    )
                    if pdist <= DOOR_INTERACT_RANGE:
                        prompt = font_terminal_small.render(_T("m1.e"), True, C_TERMINAL)
                        screen.blit(
                            prompt,
                            (
                                dr.x + TILE_SIZE // 2 - prompt.get_width() // 2,
                                dr.y - 18,
                            ),
                        )
                continue
            bw = TILE_SIZE * 3
            bdr = pygame.Rect(d.rect.x - fcx, d.rect.y - fcy, bw, TILE_SIZE)
            if d.anim_progress < 1.0:
                draw_h = int(TILE_SIZE * (1.0 - d.anim_progress))
                src = pygame.Rect(0, 0, bw, draw_h)
                screen.blit(bay_door_shadow, (bdr.x - 4, bdr.y - 4))
                screen.blit(BAY_DOOR_TILE_3W, (bdr.x, bdr.y), src)
            else:
                screen.blit(BAY_DOOR_FRAME_3W, (bdr.x, bdr.y))
            if STATE.player and not STATE.player_dead:
                pdist = math.hypot(
                    STATE.player.rect.centerx - d.rect.centerx,
                    STATE.player.rect.centery - d.rect.centery,
                )
                if pdist <= DOOR_INTERACT_RANGE:
                    prompt = font_terminal_small.render(_T("m1.e"), True, C_TERMINAL)
                    screen.blit(
                        prompt, (bdr.x + bw // 2 - prompt.get_width() // 2, bdr.y - 18)
                    )
        else:
            door_tile = DOOR_TILE
            door_frame = DOOR_FRAME_TILE
            if d.anim_progress < 1.0:
                draw_h = int(TILE_SIZE * (1.0 - d.anim_progress))
                src = pygame.Rect(0, 0, TILE_SIZE, draw_h)
                screen.blit(wall_shadow, (dr.x - 4, dr.y - 4))
                screen.blit(door_tile, (dr.x, dr.y), src)
            else:
                screen.blit(door_frame, (dr.x, dr.y))
            if STATE.player and not STATE.player_dead:
                pdist = math.hypot(
                    STATE.player.rect.centerx - d.rect.centerx,
                    STATE.player.rect.centery - d.rect.centery,
                )
                if pdist <= DOOR_INTERACT_RANGE:
                    prompt = font_terminal_small.render(_T("m1.e"), True, C_TERMINAL)
                    screen.blit(
                        prompt,
                        (dr.x + TILE_SIZE // 2 - prompt.get_width() // 2, dr.y - 18),
                    )
    for decal in STATE.blood_decals[:]:
        d_surf = get_blood_decal(decal[3])
        d_surf.set_alpha(int(decal[2]))
        screen.blit(d_surf, (decal[0] - decal[3] - fcx, decal[1] - decal[3] - fcy))
        decal[2] -= 0.5
        if decal[2] <= 0:
            STATE.blood_decals.remove(decal)
    # Draw fire zones
    for fz in STATE.fire_zones:
        fz.draw(screen, fcx, fcy)
    # Shared bullet renderer (glow + sharp core + motion trail).
    draw_bullets(screen, STATE.bullets, fcx, fcy, with_glow=True)
    # ── Thrown bottles (in flight) - shared renderer ──
    draw_thrown_bottles(screen, fcx, fcy)
    if STATE.firefight_triggered and STATE.volkov_escape_timer > 0:
        if STATE.volkov_escape_pos and not STATE.volkov_escaped:
            vx = STATE.volkov_escape_pos[0] - fcx
            vy = STATE.volkov_escape_pos[1] - fcy + 30
            if -100 < vx < WIDTH + 100 and -100 < vy < HEIGHT + 100:
                facing = STATE.volkov_escape_pos[0] < (15 * TILE_SIZE + 32)
                draw_volkov(screen, int(vx), int(vy), scale=0.35, facing_right=facing)
        if STATE.commander_escape_pos and not STATE.commander_escaped:
            kx = STATE.commander_escape_pos[0] - fcx
            ky = STATE.commander_escape_pos[1] - fcy + 30
            if -100 < kx < WIDTH + 100 and -100 < ky < HEIGHT + 100:
                facing = STATE.commander_escape_pos[0] < (15 * TILE_SIZE + 32)
                draw_commander(
                    screen, int(kx), int(ky), scale=0.35, facing_right=facing
                )
    # Fallen enemy bodies - under the living enemies, over the floor decals.
    corpse.draw_corpses(screen, fcx, fcy)
    for e in STATE.enemies:
        e.draw(screen, fcx, fcy)
    reload_progress = 0.0
    if STATE.is_reloading and STATE.reload_timer > 0:
        reload_progress = 1.0 - STATE.reload_timer / 60.0
    melee_progress = 0.0
    if STATE.melee_active and STATE.melee_timer > 0:
        melee_progress = 1.0 - STATE.melee_timer / 18.0
    if STATE.player:
        # During the death animation, skip the standing player draw - the
        # fallen-body silhouette is drawn by death_anim.draw_death_overlay().
        from entities import death_anim
        if not death_anim.should_skip_player_draw():
            STATE.player.draw(
                screen,
                fcx,
                fcy,
                STATE.walls,
                STATE.is_reloading,
                reload_progress,
                STATE.melee_active,
                melee_progress,
                is_moving=not STATE.player_dead and (
                    _m1_update._last_keys and (
                        _m1_update._last_keys[pygame.K_w] or _m1_update._last_keys[pygame.K_s] or
                        _m1_update._last_keys[pygame.K_a] or _m1_update._last_keys[pygame.K_d]
                    )
                ),
            )
    for p in STATE.particles:
        p.draw(screen, fcx, fcy)
    for c in STATE.casings:
        c.draw(screen, fcx, fcy)
    for pu in STATE.pickups:
        px = pu[0] - fcx
        py = pu[1] - fcy + math.sin(_now_s() * 3 + pu[0]) * 3
        if pu[2] == "bandage":
            glow_col = (100, 255, 100)
        elif pu[2] == "bottle":
            glow_col = (100, 200, 130)
        else:
            glow_col = (255, 210, 40)
        glow = get_glow(16, glow_col, 40)
        screen.blit(glow, (int(px - 16), int(py - 16)))
        # RPE6 Phase 3: the icon is a baked sprite (game.art.m1.pickup_icon, 32 x 32 centred;
        # pygame truncates the float draw coordinates, hence int()); the bob + glow stay live and
        # _paint_m1_pickup_icon is the fallback / bake source.
        _spr = _m1art.get("pickup_icon", _M1_PICKUP_VARIANTS.get(pu[2], -1)) if pu[2] in _M1_PICKUP_VARIANTS else None
        if _spr is not None:
            screen.blit(_spr, (int(px) - 16, int(py) - 16))
        else:
            _paint_m1_pickup_icon(screen, pu[2], px, py)
    if STATE.firefight_triggered and not STATE.notebook_collected and STATE.NOTEBOOK_POS:
        nx = STATE.NOTEBOOK_POS[0] - fcx
        ny = STATE.NOTEBOOK_POS[1] - fcy + math.sin(_now_s() * 2) * 3
        glow = get_glow(18, (255, 220, 100))
        pulse = int(60 + math.sin(_now_s() * 4) * 30)
        glow.set_alpha(pulse)
        screen.blit(glow, (int(nx - 20), int(ny - 20)))
        pygame.draw.rect(screen, (15, 15, 15), (nx - 8, ny - 10, 16, 20))
        pygame.draw.rect(screen, (40, 40, 40), (nx - 8, ny - 10, 16, 20), 1)
        pygame.draw.line(screen, (40, 40, 40), (nx, ny - 10), (nx, ny + 10), 1)
        if (
            STATE.player
            and math.hypot(
                STATE.player.rect.centerx - STATE.NOTEBOOK_POS[0],
                STATE.player.rect.centery - STATE.NOTEBOOK_POS[1],
            )
            < 80
        ):
            nearby = [
                e
                for e in STATE.enemies
                if math.hypot(
                    e.rect.centerx - STATE.NOTEBOOK_POS[0], e.rect.centery - STATE.NOTEBOOK_POS[1]
                )
                < 300
            ]
            if len(nearby) == 0:
                txt = font_prompt.render(_T("m1.walk_over_to_collect"), True, (255, 220, 100))
            else:
                txt = font_prompt.render(_T("m1.clear_hostiles_first"), True, (220, 60, 60))
            screen.blit(txt, (int(nx) - txt.get_width() // 2, int(ny) - 35))
    if STATE.notebook_collected and STATE.EXFIL_POS:
        ex = STATE.EXFIL_POS[0] - fcx
        ey = STATE.EXFIL_POS[1] - fcy
        # ──── Top-down exfil truck (KRAP flatbed, faces right) ────
        # Soft ground shadow, offset SE so the body sits on the floor plane.
        # RPE6 Phase 3: the parked truck is a baked sprite (game.art.m1.exfil_truck, 136 x 70 at
        # ex - 60, ey - 34); _paint_m1_exfil_truck is the fallback / bake source.
        spr = _m1art.get("exfil_truck", 0)
        if spr is not None:
            screen.blit(spr, (int(ex) - 60, int(ey) - 34))
            _paint_m1_exfil_headlights(screen, ex, ey)
        else:
            _paint_m1_exfil_truck(screen, ex, ey)
        # ──── Exfil pulsing ring and label (above truck) ────
        pulse = int(80 + math.sin(_now_s() * 3) * 40)
        circle_surf = pygame.Surface((100, 100), pygame.SRCALPHA)
        pygame.draw.circle(circle_surf, (50, 200, 100, pulse), (50, 50), 40, 3)
        pygame.draw.circle(circle_surf, (50, 200, 100, pulse // 2), (50, 50), 30, 2)
        screen.blit(circle_surf, (int(ex - 50), int(ey - 50)))
        ext = font_prompt.render(_T("m1.exfil"), True, (50, 200, 100))
        screen.blit(ext, (int(ex) - ext.get_width() // 2, int(ey) - 72))
        if (
            STATE.player
            and math.hypot(
                STATE.player.rect.centerx - STATE.EXFIL_POS[0], STATE.player.rect.centery - STATE.EXFIL_POS[1]
            )
            < 80
        ):
            if not STATE.truck_hotwiring:
                if STATE.enemies:
                    prompt_txt = font_prompt.render(
                        _T("m1.clear_hostiles", n=len(STATE.enemies)), True, (230, 80, 60)
                    )
                else:
                    prompt_txt = font_prompt.render(
                        _T("m1.e_open_ignition_panel"), True, (100, 255, 100)
                    )
                screen.blit(
                    prompt_txt, (int(ex) - prompt_txt.get_width() // 2, int(ey) - 85)
                )
    if STATE.truck_hotwiring:
        # First-person-ish ignition panel overlay with a short open animation.
        open_t = min(1.0, getattr(STATE, "hotwire_panel_timer", 0) / 34.0)
        ease = 1 - (1 - open_t) ** 3
        overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, int(112 * ease)))
        screen.blit(overlay, (0, 0))
        panel_w, panel_h = 640, 410
        panel_x = WIDTH // 2 - panel_w // 2
        panel_y = int(HEIGHT // 2 - panel_h // 2 + (1.0 - ease) * 90)
        panel = pygame.Surface((panel_w, panel_h), pygame.SRCALPHA)
        panel.fill((10, 12, 15, 236))
        pygame.draw.rect(panel, (80, 82, 78), panel.get_rect(), 2)
        pygame.draw.rect(panel, C_KRAP_BLUE, (0, 0, 5, panel_h))
        # scratched metal plate
        rng_panel = random.Random(74)
        for _ in range(34):
            x1 = rng_panel.randint(24, panel_w - 24)
            y1 = rng_panel.randint(58, panel_h - 20)
            pygame.draw.line(panel, (30, 34, 38, 100), (x1, y1), (x1 + rng_panel.randint(8, 40), y1 + rng_panel.randint(-2, 2)), 1)
        screen.blit(panel, (panel_x, panel_y))
        title = font_terminal.render(_T("m1.van_ignition_panel"), True, (180, 205, 210))
        screen.blit(title, (panel_x + 26, panel_y + 18))
        sub = font_terminal_small.render(_T("m1.bridge_the_correct_exposed_wires"), True, (150, 150, 135))
        screen.blit(sub, (panel_x + 28, panel_y + 48))
        nodes = _hotwire_wire_nodes()
        used = {w for pair in STATE.hotwire_connections for w in pair}
        # Draw loose wire tails from side openings.
        for name, data in nodes.items():
            x, y = data["pos"]
            col = data["color"]
            side = data["side"]
            start_x = panel_x + 36 if side == "L" else panel_x + panel_w - 36
            mid_x = x - 34 if side == "L" else x + 34
            pygame.draw.line(screen, (18, 18, 20), (start_x, y + 3), (mid_x, y + 3), 7)
            pygame.draw.line(screen, col, (start_x, y), (mid_x, y), 5)
            pygame.draw.line(screen, col, (mid_x, y), (x, y), 4)
            # copper exposed tip
            pygame.draw.circle(screen, (210, 135, 70), (x, y), 9)
            pygame.draw.circle(screen, (40, 24, 12), (x, y), 9, 1)
            if name == STATE.hotwire_selected_wire:
                glow = pygame.Surface((58, 58), pygame.SRCALPHA)
                pygame.draw.circle(glow, (*col, 85), (29, 29), 26)
                screen.blit(glow, (x - 29, y - 29))
            if name in used:
                pygame.draw.circle(screen, (100, 255, 150), (x, y), 14, 2)
            label = font_terminal_small.render(name, True, col if name != "BLACK" else (120, 120, 125))
            lx = x - label.get_width() - 18 if side == "L" else x + 18
            screen.blit(label, (lx, y - 8))
        # Draw completed bridges.
        for pair in STATE.hotwire_connections:
            a, b = pair
            ax, ay = nodes[a]["pos"]
            bx, by = nodes[b]["pos"]
            pair_key = frozenset(pair)
            purpose = HOTWIRE_TARGET_PAIRS.get(pair_key, "")
            col = (95, 240, 145)
            # cable curve with three segments
            mid_y = (ay + by) // 2 - 24
            pygame.draw.line(screen, (18, 35, 24), (ax, ay), (WIDTH // 2, mid_y), 8)
            pygame.draw.line(screen, (18, 35, 24), (WIDTH // 2, mid_y), (bx, by), 8)
            pygame.draw.line(screen, col, (ax, ay), (WIDTH // 2, mid_y), 4)
            pygame.draw.line(screen, col, (WIDTH // 2, mid_y), (bx, by), 4)
            # Purpose text is shown in the status lights below; avoid center overlap.
        # Status lights.
        statuses = ["POWER", "IGNITION", "STARTER"]
        connected = {HOTWIRE_TARGET_PAIRS.get(frozenset(pair)) for pair in STATE.hotwire_connections}
        for i, st in enumerate(statuses):
            sx = panel_x + 128 + i * 150
            sy = panel_y + panel_h - 76
            live = st in connected
            pygame.draw.circle(screen, (70, 240, 120) if live else (50, 55, 55), (sx, sy), 9)
            pygame.draw.circle(screen, (10, 15, 12), (sx, sy), 9, 1)
            stxt = font_terminal_small.render(st, True, (160, 220, 170) if live else (90, 95, 95))
            screen.blit(stxt, (sx + 16, sy - 8))
        # Sparks on wrong pair / fresh connection.
        if STATE.hotwire_spark_timer > 0:
            rng_s = random.Random(_now_ms() // 20)
            center = nodes.get(STATE.hotwire_selected_wire or "RED", {"pos": (WIDTH // 2, HEIGHT // 2)})["pos"]
            for _ in range(18 if STATE.hotwire_fail_flash > 0 else 8):
                ang = rng_s.random() * math.tau
                dist = rng_s.randint(8, 46)
                sx = center[0] + math.cos(ang) * dist
                sy = center[1] + math.sin(ang) * dist
                pygame.draw.line(screen, (255, 210, 90), center, (sx, sy), 1)
        if STATE.hotwire_fail_flash > 0:
            flash = pygame.Surface((panel_w, panel_h), pygame.SRCALPHA)
            flash.fill((255, 55, 35, min(95, STATE.hotwire_fail_flash * 8)))
            screen.blit(flash, (panel_x, panel_y))
        msg_col = (220, 90, 70) if STATE.hotwire_fail_flash > 0 else (180, 215, 190)
        msg = font_prompt.render(STATE.hotwire_message or "Click a wire endpoint", True, msg_col)
        screen.blit(msg, (WIDTH // 2 - msg.get_width() // 2, panel_y + panel_h - 34))
        hint = font_terminal_small.render(_T("m1.vasile_s_hint_red_feeds_yellow_b"), True, (115, 125, 120))
        screen.blit(hint, (WIDTH // 2 - hint.get_width() // 2, panel_y + panel_h + 10))
    unpinned = [ft for ft in STATE.floating_texts if not (len(ft) >= 6 and ft[5] == "pin")]
    for ft in unpinned:
        txt = font_terminal_small.render(ft[2], True, ft[3])
        screen.blit(txt, (ft[0] - fcx - txt.get_width() // 2, ft[1] - fcy))
    # Shared radio transmission widget (ui.radio, polish pass T6).
    draw_pinned_radio(screen)
    # Honor the Gameplay → Crosshair setting. The shared
    # ui_hud.draw_gameplay_crosshair() (called from acaristan.py) already
    # respects SETTINGS.show_crosshair, but this mission also draws its OWN
    # combat reticle below - gate it on the same setting so the user's
    # "Crosshair: Off" preference actually applies during gameplay.
    try:
        from core.user_settings import SETTINGS
        _show_ch = SETTINGS.show_crosshair
    except Exception:
        _show_ch = True
    ch_x, ch_y = get_scaled_mouse()
    if STATE.truck_hotwiring:
        # Compact pointing-hand cursor. The ACTUAL click/contact point is the
        # fingertip at (ch_x, ch_y), so it no longer feels offset.
        skin = (218, 178, 136)
        skin_hi = (238, 205, 165)
        outline = (54, 36, 24)
        glove_shadow = (120, 82, 55)
        cuff_col = (56, 68, 50)
        # soft shadow
        pygame.draw.polygon(
            screen, (0, 0, 0, 95),
            [(ch_x + 2, ch_y + 3), (ch_x - 7, ch_y + 13), (ch_x - 4, ch_y + 39),
             (ch_x - 19, ch_y + 47), (ch_x - 9, ch_y + 66), (ch_x + 22, ch_y + 62),
             (ch_x + 26, ch_y + 40), (ch_x + 10, ch_y + 34), (ch_x + 8, ch_y + 12)],
        )
        # reference-anatomy pointing hand; fingertip is the contact point
        from core.hands import point_hand
        point_hand(screen, (ch_x + 10, ch_y + 35), angle=0.0, mirror=-1, sc=0.52,
                   pal={"skin": skin, "hi": skin_hi, "mid": (170, 128, 92),
                        "sh": glove_shadow, "nail": (205, 165, 130),
                        "nail_edge": (150, 110, 80), "nail_tip": (246, 222, 192)})
        # sleeve/cuff
        pygame.draw.rect(screen, outline, (ch_x - 13, ch_y + 59, 31, 16), border_radius=4)
        pygame.draw.rect(screen, cuff_col, (ch_x - 10, ch_y + 60, 26, 14), border_radius=3)
        pygame.draw.line(screen, (34, 42, 30), (ch_x - 8, ch_y + 64), (ch_x + 14, ch_y + 64), 1)
        # exact contact point marker on top of the fingertip
        pygame.draw.circle(screen, C_ORANGE, (ch_x, ch_y), 3, 1)
    else:
        # Combat reticle. Gated on SETTINGS.show_crosshair so the user's
        # "Crosshair: Off" preference is honored. Respects crosshair_size
        # (3=small, 6=medium, 10=large) and colorblind_mode (recolors the
        # reticle for accessibility) - same logic as the shared
        # ui_hud.draw_gameplay_crosshair(), so the two renderers match.
        if _show_ch:
            from core.user_settings import SETTINGS
            cb = SETTINGS.colorblind_mode
            col = _hud_crosshair.color_for(cb, default=C_ORANGE)
            size = max(3, int(SETTINGS.crosshair_size))
            _hud_crosshair.draw_combat(screen, ch_x, ch_y, size=size, color=col)

    if STATE.muzzle_flash_timer > 0:
        if STATE.player:
            if hasattr(STATE.player, "barrel_tip"):
                tip_x, tip_y = STATE.player.barrel_tip()
            else:
                tip_x = STATE.player.rect.centerx + math.cos(STATE.player.angle) * 39
                tip_y = STATE.player.rect.centery + math.sin(STATE.player.angle) * 39
            flash_x = tip_x - fcx
            flash_y = tip_y - fcy
        else:
            flash_x, flash_y = ch_x, ch_y
        screen.blit(MUZZLE_FLASH, (int(flash_x - 40), int(flash_y - 40)))
        if artpack.enabled():
            lighting.buffer().light(flash_x, flash_y, 240, (255, 190, 110), 0.9)
        STATE.muzzle_flash_timer -= 1
    if STATE.player_dead:
        # Death animation overlay: blood pool, fallen body, weapon eject,
        # tinnitus. The camera tilt is applied at the very end of the frame
        # (after HUD) so the entire screen rotates including UI.
        from entities import death_anim
        death_anim.draw_death_overlay(screen, fcx, fcy)
    if STATE.gc_flash_timer > 0 and not getattr(STATE, "reduced_motion", False):
        flash_surf = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        flash_surf.fill((255, 255, 255, min(255, STATE.gc_flash_timer * 22)))
        screen.blit(flash_surf, (0, 0))
    # ── Breach stage flicker + alarm wash ──
    if STATE.breach_stage in (3, 4):
        wash = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        wash.fill((180, 30, 20, 26 + _rng_legacy.randint(0, 22)))
        screen.blit(wash, (0, 0))
        if (_now_ms() // 80) % 3 == 0:
            flicker = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
            flicker.fill((0, 0, 0, _rng_legacy.randint(40, 120)))
            screen.blit(flicker, (0, 0))
    draw_scanlines(screen)
    draw_vignette(screen)
    if STATE.player and not STATE.truck_hotwiring:
        # HP bar - shared engine.ui.std widget in M1's compact layout (Phase 4).
        _hud_health_bar.draw(screen, THEME, STATE.player.hp, STATE.player.max_hp,
                             panel_bg=_m1_hp_panel, x=30, y=HEIGHT - 50,
                             bb=(0, 0, 160, 14), inset=0, panel=(180, 42),
                             panel_off=(-10, -16), label_dy=-14)

        # Objective text (without "OBJECTIVE:" prefix - the shared helper
        # prepends it, matching M2's behavior).
        obj_text = "Locate Volkov in the warehouse"
        if STATE.mission_phase == "firefight":
            if STATE.notebook_collected:
                obj_text = "Reach exfil"
            elif len(STATE.enemies) > 1:
                obj_text = f"Clear hostiles ({len(STATE.enemies)} remaining)"
            else:
                obj_text = "Recover the notebook"
        elif STATE.mission_phase == "escape":
            obj_text = "Reach exfil zone"
        draw_objective_panel(screen, obj_text)
        # Ammo panel sits 96 px above the HP strip anchor (Phase 4: the strip
        # is the shared widget now, so its anchor is spelled out here).
        ammo_x, ammo_y = 30, (HEIGHT - 50) - 96
        bg_w, bg_h = 246, 92
        bg = pygame.Surface((bg_w, bg_h), pygame.SRCALPHA)
        pygame.draw.rect(bg, (0, 0, 0, 140), (0, 0, bg_w, bg_h), border_radius=4)
        pygame.draw.rect(bg, (40, 42, 38), (0, 0, bg_w, bg_h), 1, border_radius=4)
        screen.blit(bg, (ammo_x - 6, ammo_y))
        for i in range(4):
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
            body_pts = [
                (mx, my),
                (mx + top_w, my),
                (mx + taper + bot_w, my + h),
                (mx + taper, my + h),
            ]
            if is_empty:
                base = (45, 42, 38)
                hl = (55, 52, 48)
                rim = (55, 50, 45)
            elif is_active:
                base = (90, 86, 78)
                hl = (115, 110, 100)
                rim = (70, 66, 58)
            else:
                base = (72, 68, 62)
                hl = (92, 88, 80)
                rim = (60, 56, 50)
            pygame.draw.polygon(screen, base, body_pts)
            pygame.draw.polygon(
                screen,
                hl,
                [
                    (mx + 1, my + 2),
                    (mx + 5, my + 2),
                    (mx + taper + 3, my + h - 3),
                    (mx + taper + 1, my + h - 3),
                ],
            )
            outline = (
                C_TERMINAL if is_active else (rim if not is_empty else (55, 50, 45))
            )
            pygame.draw.polygon(screen, outline, body_pts, 1)
            bullet_y = my + 8
            gold = (220, 185, 45)
            dark = (55, 52, 48) if not is_empty else (40, 38, 35)
            for bi in range(12):
                col = gold if bi < bullets_fill else dark
                pygame.draw.circle(screen, col, (mx + top_w // 2, bullet_y + bi * 3), 2)
            if is_empty:
                pygame.draw.line(
                    screen,
                    (90, 55, 55),
                    (mx + 2, my + 2),
                    (mx + top_w - 2, my + h - 2),
                    1,
                )
                pygame.draw.line(
                    screen,
                    (90, 55, 55),
                    (mx + top_w - 2, my + 2),
                    (mx + 2, my + h - 2),
                    1,
                )
        ammo_text = f"{STATE.ammo_in_mag}/{STATE.mag_size}"
        text_col = C_TERMINAL if STATE.ammo_in_mag > 0 else (220, 60, 60)
        screen.blit(
            font_terminal_small.render(ammo_text, True, text_col),
            (ammo_x + 154, ammo_y + 8),
        )
        screen.blit(
            font_terminal_small.render(_T("m1.9mm"), True, (100, 110, 100)),
            (ammo_x + 154, ammo_y + 26),
        )
        if STATE.is_reloading:
            bar_x, bar_y = ammo_x + 148, ammo_y + 46
            bar_w, bar_h = 80, 8
            progress = 1.0 - STATE.reload_timer / 60.0
            pygame.draw.rect(
                screen, (50, 50, 50), (bar_x, bar_y, bar_w, bar_h), border_radius=2
            )
            pygame.draw.rect(
                screen,
                (220, 160, 40),
                (bar_x, bar_y, int(bar_w * progress), bar_h),
                border_radius=2,
            )
            reload_lbl = font_terminal_small.render(_T("m1.reloading"), True, (220, 160, 40))
            screen.blit(reload_lbl, (ammo_x + 150, ammo_y + 58))
        else:
            mag_label = f"MAGS: {STATE.spare_mags}"
            screen.blit(
                font_terminal_small.render(mag_label, True, (140, 150, 130)),
                (ammo_x + 154, ammo_y + 44),
            )
        # ── Bottle HUD ──
        # Bottle HUD - shared engine.ui.std strip (M1's 140-alpha panel).
        _hud_bottle_hud.draw(screen, THEME, STATE.player_bottles,
                             panel_bg=_m1_panel_140, icon=_draw_molotov_icon,
                             x=ammo_x - 6, y=ammo_y - 42, width=246, cap=4)

        _hud_hostiles.draw(screen, THEME, len(STATE.enemies))

    if STATE.show_minimap and STATE.minimap:
        STATE.minimap.draw(
            screen,
            STATE.player,
            STATE.enemies,
            fcx,
            fcy,
            STATE.NOTEBOOK_POS,
            STATE.EXFIL_POS,
            STATE.volkov_pos,
            STATE.commander_pos,
        )
    # ── Death animation: camera tilt ──
    # Apply at the very end of the frame so the entire rendered scene
    # (world + HUD + minimap) rotates together. No-op when alive.
    if STATE.player_dead:
        from entities import death_anim
        death_anim.apply_camera_tilt(screen)
