
"""Mission 3 - Kill Order -> Broadcast transition cinematic (Slice 5 -> 6).

Illustrated cutscene language, same family as the KO transition
(cutscenes.m3ko) and the chair-break shots: dark vector compositions with
motivated lighting, gradients and light cones from cutscenes.route12,
dust/bloom from cutscenes.chair, the side-view cast from cutscenes.cast.

Same house rules as m3ko v2:
  * Shots are INPUT-PACED (they hold until the player advances), so every
    shot stays ALIVE indefinitely: swinging lamp, streaming road, sweeping
    searchlights, breathing idle - no still tableaus.
  * The camera is a camera: slow push-in per shot (crop+smoothscale) plus
    handheld micro-shake.
  * Highlights bloom (soft normal-blend glow), one cool film tint for
    continuity. App-level vignette/scanlines/letterbox/caption stay the
    single post pass.

Shots (one continuous beat, dock -> road -> broadcast wing -> studio door):
  shutter - roller shutter slams on the loading dock, work-lamp swinging
  road    - night drive, wet ring road, the mast blinking on the horizon
  mast    - state broadcast wing exterior, beacon + sweeping searchlights
  onair   - studio corridor, ON AIR sign, Biribel advances on the doors

Branch-neutral by design: no van, no Volkov on screen. The branch-specific
exfil bark (VOLKOV's van vs MARU's roof line) already played in gameplay,
so these frames read correctly whether Volkov drove or bailed.

Also owns the 22:00 fail sequence (m3_bcast_fail_studio/_pa/_retry), the
three-shot cut the broadcast wing plays when the address finishes first:
studio lost -> the address on the monitor wall -> feed released / re-arm.
Same family, palette flipped cold; the retry shot is the plate the auto
retry hands the wing back on.

Pure functions of t: no STATE reads or writes.
"""
import math
import random

import pygame

from core.config import (HEIGHT, SCENE_TOP, WIDTH, font_terminal, font_terminal_small)
from cutscenes.chair import _cb_camera_shake, _draw_dust_motes
from cutscenes.m3cell import _m3_draw_balaceanu
from cutscenes.m3ko import (_ko_actor, _ko_clamp01, _ko_concrete, _ko_glow,
                             _ko_push, _ko_smoke_loop, _ko_strobe, _ko_tag,
                             _ko_tint)
from cutscenes.route12 import (_draw_light_cone, _draw_vertical_gradient,
                                _ease_cutscene, _lerp_cutscene)


# ── shared bits ────────────────────────────────────────────────────────
_BC_BUF = None


def _bc_buf():
    global _BC_BUF
    if _BC_BUF is None:
        _BC_BUF = pygame.Surface((WIDTH, HEIGHT))
    return _BC_BUF


# ── shot 0: shutter slam ───────────────────────────────────────────────
def _draw_m3_bcast_shutter_raw(surface, t):
    """The dock shutter comes DOWN: exfil is behind us now.

    Drops over ~900ms with a dust punch on impact, then holds shut while a
    caged work-lamp swings overhead and the lockdown strobe dies out.
    """
    slam = _ease_cutscene(_ko_clamp01(t / 900.0))
    ox, oy = _cb_camera_shake(t, 2.2, math.exp(-t / 500.0))

    def W(x, y):
        return (int(x + ox), int(y + oy))

    _ko_concrete(surface, (9, 8, 8), (16, 13, 11))
    layer = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)

    # Shutter housing + side rails.
    dx0, dw = 250, 500
    pygame.draw.rect(surface, (30, 28, 26), (*W(dx0 - 26, 60), dw + 52, 44))
    for rx in (dx0 - 26, dx0 + dw + 8):
        pygame.draw.rect(surface, (38, 36, 32), (*W(rx, 60), 18, 470))
        pygame.draw.line(surface, (70, 66, 58), W(rx + 9, 64), W(rx + 9, 526), 2)
    # Slats: descend with the slam, then sit shut.
    top = 104
    bot = _lerp_cutscene(300.0, 512.0, slam)
    pygame.draw.rect(surface, (10, 10, 12), (*W(dx0, top), dw, int(bot - top)))
    y = top
    while y < bot - 4:
        shade = 44 + int(8 * math.sin(y * 0.4))
        pygame.draw.rect(surface, (shade, shade - 2, shade - 6),
                         (*W(dx0, int(y)), dw, 12))
        pygame.draw.line(surface, (20, 18, 16), W(dx0, int(y) + 12),
                         W(dx0 + dw, int(y) + 12), 2)
        y += 14
    # Bottom bar with hazard chevrons.
    pygame.draw.rect(surface, (52, 48, 40), (*W(dx0 - 6, int(bot)), dw + 12, 22))
    for hx in range(dx0 - 6, dx0 + dw + 6, 26):
        pygame.draw.line(surface, (150, 128, 44), W(hx, int(bot) + 20),
                         W(hx + 13, int(bot) + 2), 4)
    # Stencil tag above the housing.
    tag = font_terminal_small.render(_T("m3broadcast.dock_03_sealed"), True, (150, 140, 120))
    surface.blit(tag, W(dx0 + dw // 2 - tag.get_width() // 2, 40))

    # Impact dust punch on the slam, then endlessly settling motes.
    if t < 1600:
        k = _ko_clamp01(t / 900.0)
        puff = int(90 * (1 - k))
        if puff > 0:
            dust = pygame.Surface((dw + 120, 120), pygame.SRCALPHA)
            for i in range(26):
                rng = random.Random(31 + i)
                px = rng.randint(0, dw + 120)
                py = rng.randint(0, 120)
                r = rng.randint(4, 12)
                pygame.draw.circle(dust, (150, 140, 126, puff), (px, py), r)
            surface.blit(dust, W(dx0 - 60, int(bot) - 40))
    _ko_smoke_loop(layer, dx0 + dw // 2 + ox, bot + oy + 10, t, seed=4.0, n=4)

    # Caged work-lamp swings overhead: the pool of light never sits still.
    swing = math.sin(t * 0.0011) * 46
    lamp_x, lamp_y = WIDTH // 2 + swing, 96
    pygame.draw.line(surface, (16, 16, 18),
                     W(WIDTH // 2, 60), W(int(lamp_x), int(lamp_y)), 3)
    pygame.draw.rect(surface, (60, 58, 52),
                     (*W(int(lamp_x) - 16, int(lamp_y)), 32, 18))
    _draw_light_cone(surface, int(lamp_x + ox), int(lamp_y + 14 + oy), 110,
                     (255, 205, 140), alpha=14)
    pool = pygame.Surface((300, 60), pygame.SRCALPHA)
    pygame.draw.ellipse(pool, (255, 205, 140, 20), (0, 0, 300, 60))
    surface.blit(pool, W(int(lamp_x) - 150, 520))
    _ko_glow(surface, (255, 205, 140), (lamp_x + ox, lamp_y + oy), 40, 30)

    # Lockdown strobe dies with the phase; a faint fault-blink stays alive.
    strobe = _ko_strobe(t) * math.exp(-t / 2500.0)
    fault = 0.25 if (t % 4200.0) < 140.0 else 0.0
    if strobe + fault > 0.01:
        layer.fill((200, 15, 10, int(38 * min(1.0, strobe + fault))))

    _draw_dust_motes(surface, t)
    surface.blit(layer, (0, 0))
    _ko_tint(surface)
    _ko_tag(surface, "LOADING DOCK // EXFIL")
    return (dx0 + dw // 2 + ox, 300 + oy, 1.12 + 0.18 * slam)


def _draw_m3_bcast_shutter(surface, t):
    buf = _bc_buf()
    fx, fy, z = _draw_m3_bcast_shutter_raw(buf, t)
    _ko_push(surface, buf, z, fx, fy)


# ── shot 1: night road ─────────────────────────────────────────────────
def _draw_m3_bcast_road_raw(surface, t):
    """Through the windshield: wet ring road, the mast on the horizon.

    Lane dashes stream, streetlights sweep past, rain needles the glass,
    the dossier rides the dash. First-person and vehicle-neutral.
    """
    horizon = SCENE_TOP + 190
    ox, oy = _cb_camera_shake(t, 0.9, 1.0)
    vib = math.sin(t * 0.09) * 1.5  # engine tremor on the whole frame

    def W(x, y):
        return (int(x + ox), int(y + vib + oy))

    _draw_vertical_gradient(surface, 0, 0, WIDTH, horizon + 60,
                            (5, 7, 15), (24, 16, 20))
    layer = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)

    # Distant city glow + window dots + the mast, blinking.
    glow = pygame.Surface((WIDTH, 130), pygame.SRCALPHA)
    for i in range(60):
        a = max(0, 40 - i)
        pygame.draw.line(glow, (255, 150, 80, a),
                         (0, 60 + i), (WIDTH, 60 + i), 1)
    surface.blit(glow, (0, horizon - 100))
    rng = random.Random(77)
    for _ in range(70):
        wx = rng.randint(40, WIDTH - 40)
        wy = rng.randint(int(horizon - 78), int(horizon - 18))
        warm = rng.random() > 0.35
        col = (255, 190, 120) if warm else (150, 190, 220)
        pygame.draw.rect(surface, col, (*W(wx, wy), 3, 2))
    mx, my = WIDTH - 190, horizon - 30
    pygame.draw.line(surface, (12, 12, 16), W(mx - 26, my), W(mx, my - 92), 3)
    pygame.draw.line(surface, (12, 12, 16), W(mx + 26, my), W(mx, my - 92), 3)
    pygame.draw.line(surface, (12, 12, 16), W(mx, my - 92), W(mx, my - 104), 3)
    if (t % 1200.0) < 600.0:
        pygame.draw.circle(surface, (255, 60, 50), W(mx, my - 108), 5)
        _ko_glow(surface, (255, 70, 60), (mx + ox, my - 108 + vib + oy), 26, 60)

    # Wet asphalt trapezoid + streaming lane dashes.
    pygame.draw.polygon(surface, (13, 13, 16),
                        [W(0, HEIGHT), W(WIDTH, HEIGHT),
                         W(WIDTH // 2 + 90, horizon), W(WIDTH // 2 - 90, horizon)])
    pygame.draw.polygon(surface, (22, 22, 26),
                        [W(0, HEIGHT), W(WIDTH, HEIGHT),
                         W(WIDTH // 2 + 90, horizon), W(WIDTH // 2 - 90, horizon)], 1)
    for k in range(9):
        p = (t * 0.00035 + k / 9.0) % 1.0
        y = horizon + (HEIGHT - horizon) * p * p
        w = 2 + 15 * p * p
        x = WIDTH // 2
        pygame.draw.rect(surface, (190, 170, 120), (*W(int(x - w // 2), int(y)),
                                                    int(w), int(3 + 9 * p)))
    # Streetlight pools rushing past, alternating sides.
    for k in range(4):
        p = (t * 0.00035 + k / 4.0 + 0.5) % 1.0
        y = horizon + (HEIGHT - horizon) * p * p
        side = -1 if k % 2 == 0 else 1
        spread = 120 + 420 * p
        ex = WIDTH // 2 + side * spread
        pool = pygame.Surface((180, 46), pygame.SRCALPHA)
        pygame.draw.ellipse(pool, (255, 205, 140, int(10 + 26 * p)), (0, 0, 180, 46))
        surface.blit(pool, W(int(ex) - 90, int(y) - 20))
        pygame.draw.line(surface, (10, 10, 12),
                         W(int(ex + side * 60), int(y) - int(220 * p)),
                         W(int(ex + side * 60), int(y)), max(1, int(2 + 3 * p)))
    # Rain needles on the glass.
    rng = random.Random(9)
    for _ in range(46):
        bx = rng.randint(0, WIDTH)
        by = rng.randint(0, HEIGHT)
        ln = rng.randint(9, 22)
        fall = (t * 0.55 + rng.randint(0, 700)) % (HEIGHT + 60)
        yy = (by + fall) % (HEIGHT + 60) - 30
        pygame.draw.line(layer, (170, 190, 210, 70),
                         (bx, int(yy)), (bx - 5, int(yy) + ln), 1)
    surface.blit(layer, (0, 0))

    # Dashboard + the dossier riding shotgun.
    pygame.draw.rect(surface, (8, 8, 10), (0, HEIGHT - 120, WIDTH, 120))
    pygame.draw.line(surface, (40, 42, 46), (0, HEIGHT - 120), (WIDTH, HEIGHT - 120), 2)
    for vx in range(120, WIDTH, 200):
        pygame.draw.circle(surface, (120, 200, 170), (vx, HEIGHT - 96), 3)
    dossier_x, dossier_y = WIDTH // 2 + 150, HEIGHT - 96
    pygame.draw.rect(surface, (208, 196, 170),
                     (*W(dossier_x, dossier_y), 74, 52))
    pygame.draw.rect(surface, (60, 50, 40), (*W(dossier_x, dossier_y), 74, 52), 2)
    for ly in range(dossier_y + 10, dossier_y + 40, 8):
        pygame.draw.line(surface, (120, 110, 92), W(dossier_x + 8, ly),
                         W(dossier_x + 66, ly), 1)
    stamp = font_terminal_small.render(_T("m3broadcast.vostral"), True, (170, 40, 34))
    surface.blit(stamp, W(dossier_x + 8, dossier_y + 34))
    # Windshield frame + mirror.
    pygame.draw.rect(surface, (5, 5, 7), (0, 0, WIDTH, SCENE_TOP - 6))
    pygame.draw.rect(surface, (16, 18, 20),
                     (WIDTH // 2 - 90, SCENE_TOP - 34, 180, 30), border_radius=6)

    _ko_tint(surface)
    _ko_tag(surface, "RING ROAD // 21:47")
    # Push-in bounds: _ko_push only clamps the crop origin, so the focus must
    # keep the whole crop window on-surface (fy +/- (HEIGHT/z)/2 in range).
    breathe = 1.08 + 0.03 * math.sin(t * 2.0 * math.pi / 9000.0)
    return (WIDTH // 2 + ox, horizon + 40 + vib + oy, breathe)


def _draw_m3_bcast_road(surface, t):
    buf = _bc_buf()
    fx, fy, z = _draw_m3_bcast_road_raw(buf, t)
    _ko_push(surface, buf, z, fx, fy)


# ── shot 2: broadcast wing ─────────────────────────────────────────────
def _draw_m3_bcast_mast_raw(surface, t):
    """The state broadcast wing at night: lit facade, mast, searchlights."""
    ox, oy = _cb_camera_shake(t, 0.8, 1.0)

    def W(x, y):
        return (int(x + ox), int(y + oy))

    _draw_vertical_gradient(surface, 0, 0, WIDTH, HEIGHT, (4, 6, 12), (10, 9, 12))
    layer = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
    rng = random.Random(5)
    for _ in range(60):
        sx = rng.randint(0, WIDTH)
        sy = rng.randint(0, 220)
        pygame.draw.circle(layer, (200, 210, 230, 60), (sx, sy), 1)
    surface.blit(layer, (0, 0))

    # Facade block with lit windows (two flicker).
    fx0, fy0, fw, fh = 90, 210, 560, 330
    pygame.draw.rect(surface, (24, 24, 30), (*W(fx0, fy0), fw, fh))
    pygame.draw.rect(surface, (52, 52, 60), (*W(fx0, fy0), fw, fh), 2)
    pygame.draw.rect(surface, (34, 34, 42), (*W(fx0 - 14, fy0 - 18), fw + 28, 18))
    for r in range(4):
        for c in range(7):
            wx = fx0 + 34 + c * 70
            wy = fy0 + 40 + r * 72
            lit = ((r * 7 + c) % 4) != 3
            flick = (r == 1 and c == 4 and (t % 900.0) < 180.0)
            col = (255, 196, 130) if (lit and not flick) else (26, 26, 32)
            pygame.draw.rect(surface, col, (*W(wx, wy), 44, 50))
            pygame.draw.rect(surface, (60, 60, 68), (*W(wx, wy), 44, 50), 1)
            pygame.draw.line(surface, (60, 60, 68), W(wx + 22, wy), W(wx + 22, wy + 50), 1)
    # Entrance canopy + warm doors.
    pygame.draw.rect(surface, (16, 16, 20), (*W(fx0 + 180, fy0 + fh - 96), 200, 96))
    _draw_vertical_gradient(surface, fx0 + 180 + int(ox), fy0 + fh - 92 + int(oy),
                            200, 88, (255, 206, 140), (120, 84, 48))
    pygame.draw.polygon(surface, (20, 20, 24),
                        [W(fx0 + 150, fy0 + fh - 96), W(fx0 + 410, fy0 + fh - 96),
                         W(fx0 + 440, fy0 + fh - 60), W(fx0 + 120, fy0 + fh - 60)])
    # No facade sign band: the window grid leaves no clean gap for one, and
    # the location tag below already names the wing. The red beacon + beams
    # carry the "live broadcast" read instead.

    # Mast: lattice, guy wires, pulsing beacon.
    bx, byb = 770, 540
    pygame.draw.line(surface, (14, 14, 18), W(bx - 60, byb), W(bx, byb - 330), 4)
    pygame.draw.line(surface, (14, 14, 18), W(bx + 60, byb), W(bx, byb - 330), 4)
    for k in range(9):
        yy = byb - k * 36
        half = 60 * (1 - k / 10.0)
        pygame.draw.line(surface, (26, 26, 32),
                         W(int(bx - half), int(yy)), W(int(bx + half), int(yy)), 2)
        pygame.draw.line(surface, (26, 26, 32),
                         W(int(bx - half), int(yy)), W(int(bx + half), int(yy) - 36), 1)
    pulse = 0.5 + 0.5 * math.sin(t * 0.006)
    pygame.draw.circle(surface, (255, 60, 50), W(bx, byb - 336), 8)
    _ko_glow(surface, (255, 70, 60), (bx + ox, byb - 336 + oy), 60, 30 + 50 * pulse)
    # Uplink dish on the facade roof, tracking slowly.
    dish_x, dish_y = fx0 + fw - 90, fy0 - 18
    pygame.draw.line(surface, (40, 42, 48), W(dish_x, dish_y), W(dish_x, dish_y + 18), 4)
    pygame.draw.ellipse(surface, (70, 74, 82), (*W(dish_x - 34, dish_y - 26), 68, 26))
    arm_a = t * 0.00025
    pygame.draw.line(surface, (120, 150, 170),
                     W(dish_x, dish_y - 13),
                     W(int(dish_x + math.cos(arm_a) * 34), int(dish_y - 13 + math.sin(arm_a) * 10)), 2)

    # Searchlight cones sweeping the sky.
    for k, phase in ((0, 0.0), (1, 2.4)):
        ang = math.sin(t * 0.00045 + phase) * 0.55
        sx = 200 + k * 620
        length = 420
        ex = sx + math.sin(ang) * length
        ey = 40 - math.cos(ang) * 60
        beam = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        pygame.draw.polygon(beam, (180, 200, 230, 16),
                            [(sx, 540), (ex - 60, ey), (ex + 60, ey)])
        surface.blit(beam, (0, 0))

    # Foreground fence silhouette.
    for px in range(-20, WIDTH + 20, 64):
        pygame.draw.line(surface, (8, 8, 10), (px, HEIGHT - 70), (px, HEIGHT - 150), 4)
    pygame.draw.line(surface, (8, 8, 10), (0, HEIGHT - 140), (WIDTH, HEIGHT - 140), 2)
    pygame.draw.line(surface, (8, 8, 10), (0, HEIGHT - 110), (WIDTH, HEIGHT - 110), 1)

    _draw_dust_motes(surface, t)
    _ko_tint(surface)
    _ko_tag(surface, "STATE BROADCAST WING")
    return (bx + ox, byb - 200 + oy, 1.05 + 0.12 * _ko_clamp01(t / 6000.0))


def _draw_m3_bcast_mast(surface, t):
    buf = _bc_buf()
    fx, fy, z = _draw_m3_bcast_mast_raw(buf, t)
    _ko_push(surface, buf, z, fx, fy)


# ── shot 3: studio corridor ────────────────────────────────────────────
def _draw_m3_bcast_onair_raw(surface, t):
    """The last walk: Biribel advances on the ON AIR doors, solo and framed.

    Solo by design - no Volkov on screen, so the frame reads correctly
    whether he drove the van or bailed at the dock.
    """
    ox, oy = _cb_camera_shake(t, 0.9, 1.0)

    def W(x, y):
        return (int(x + ox), int(y + oy))

    _draw_vertical_gradient(surface, 0, 0, WIDTH, HEIGHT, (14, 8, 9), (26, 16, 14))
    layer = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
    cx = WIDTH // 2
    horizon = SCENE_TOP + 200

    # Converging corridor.
    pygame.draw.polygon(surface, (30, 18, 20),
                        [(0, SCENE_TOP), (cx - 130, horizon),
                         (cx - 210, HEIGHT), (0, HEIGHT)])
    pygame.draw.polygon(surface, (26, 15, 17),
                        [(WIDTH, SCENE_TOP), (cx + 130, horizon),
                         (cx + 210, HEIGHT), (WIDTH, HEIGHT)])
    pygame.draw.polygon(surface, (38, 24, 24),
                        [(cx - 210, HEIGHT), (cx - 130, horizon),
                         (cx + 130, horizon), (cx + 210, HEIGHT)])
    for i in range(7):
        y = horizon + i * 62
        half = 130 + (y - horizon) * 0.32
        pygame.draw.line(surface, (58, 38, 38),
                         W(int(cx - half), int(y)), W(int(cx + half), int(y)), 2)
    for depth in range(3):
        yy = SCENE_TOP + 30 + depth * 48
        half = 220 - depth * 40
        pygame.draw.line(surface, (150, 60, 55), W(int(cx - half), int(yy)),
                         W(int(cx + half), int(yy)), 4)

    # The double doors + ON AIR sign.
    door_w, door_h = 220, 260
    door_x, door_y = cx - door_w // 2, horizon - 40
    pygame.draw.rect(surface, (12, 10, 12),
                     (*W(door_x - 12, door_y - 12), door_w + 24, door_h + 24))
    pygame.draw.rect(surface, (64, 40, 36), (*W(door_x, door_y), door_w, door_h))
    pygame.draw.rect(surface, (120, 80, 60), (*W(door_x, door_y), door_w, door_h), 2)
    pygame.draw.line(surface, (20, 14, 12), W(cx, door_y), W(cx, door_y + door_h), 3)
    for hx, hy in ((door_x + 26, door_y + door_h // 2),
                   (door_x + door_w - 26, door_y + door_h // 2)):
        pygame.draw.circle(surface, (200, 160, 110), W(hx, hy), 5)
    # Warm bleed through the seams + under the doors.
    bleed = pygame.Surface((door_w + 60, 60), pygame.SRCALPHA)
    bleed.fill((255, 190, 120, 40))
    surface.blit(bleed, W(door_x - 30, door_y + door_h - 12))
    seam = pygame.Surface((6, door_h), pygame.SRCALPHA)
    seam.fill((255, 210, 150, 90))
    surface.blit(seam, W(cx - 3, door_y))
    _draw_light_cone(surface, cx + int(ox), door_y + door_h + int(oy), 170,
                     (255, 195, 130), alpha=24)
    # ON AIR sign, breathing red.
    sign_on = 0.6 + 0.4 * math.sin(t * 0.005)
    pygame.draw.rect(surface, (40, 8, 8),
                     (*W(door_x + 20, door_y - 64), door_w - 40, 44), border_radius=4)
    pygame.draw.rect(surface, (255, 60, 50),
                     (*W(door_x + 20, door_y - 64), door_w - 40, 44), 2, border_radius=4)
    onair = font_terminal.render(_T("m3broadcast.on_air"), True, (255, 90, 80))
    surface.blit(onair, W(cx - onair.get_width() // 2, door_y - 58))
    _ko_glow(surface, (255, 60, 50), (cx + ox, door_y - 42 + oy),
             70, 20 + 30 * sign_on)

    # Wall dressing: EXIT sign + framed poster.
    exit_s = font_terminal_small.render(_T("m3broadcast.exit"), True, (110, 230, 150))
    pygame.draw.rect(surface, (8, 20, 12),
                     (*W(96, horizon + 40), exit_s.get_width() + 16, 26))
    surface.blit(exit_s, W(104, horizon + 45))
    pygame.draw.rect(surface, (52, 40, 34), (*W(WIDTH - 170, horizon + 30), 110, 150))
    pygame.draw.rect(surface, (150, 120, 90),
                     (*W(WIDTH - 170, horizon + 30), 110, 150), 2)
    pygame.draw.circle(surface, (150, 60, 55),
                       W(WIDTH - 115, horizon + 80), 20, 2)
    seal = font_terminal_small.render(_T("m3broadcast.ipa"), True, (170, 130, 100))
    surface.blit(seal, W(WIDTH - 115 - seal.get_width() // 2, horizon + 118))

    # Biribel advances, then holds at the doors - stride is distance-driven
    # so a held shot freezes instead of treadmill-looping.
    q = _ease_cutscene(_ko_clamp01(t / 2200.0))
    step = q * 3.0
    bx = _lerp_cutscene(300.0, 430.0, q)
    by = HEIGHT - 60
    _ko_actor(surface, "biribel", *W(int(bx), int(by)), scale=0.78,
              facing_right=True, t=t, moving=q < 0.995,
              walk_phase=step * math.pi, silhouette=True)

    _draw_dust_motes(surface, t)
    surface.blit(layer, (0, 0))
    _ko_tint(surface)
    _ko_tag(surface, "STUDIO CORRIDOR // ON AIR")
    return (cx + ox, door_y + 100 + oy, 1.06 + 0.12 * q)


def _draw_m3_bcast_onair(surface, t):
    buf = _bc_buf()
    fx, fy, z = _draw_m3_bcast_onair_raw(buf, t)
    _ko_push(surface, buf, z, fx, fy)


# ── 22:00 fail sequence (Slice 6) ────────────────────────────────────────
# The address lands before the file does. Same house rules as the four
# transition shots above (input-paced, push-in, bloom, always alive), but the
# palette flips cold: the studio we were about to take is already theirs.
#   fail_studio - the booth we lost: dead console, red emergency wash
#   fail_pa     - the address itself, playing out on the monitor wall
#   fail_retry  - the feed released; the wing re-arms (auto-retry card)
# Pure functions of t: no STATE reads or writes.


def _draw_m3_bcast_fail_studio_raw(surface, t):
    """The studio after we lost it: ON AIR burnt out, emergency red, desk dead.

    Biribel is a silhouette at the console - the frame is about the room
    winning, not about her. The dossier sits on the desk, still in hand.
    """
    ox, oy = _cb_camera_shake(t, 0.6, 0.7)
    # Emergency lamp: slow breathing pulse + a lazy fault blink so a held
    # frame never settles into a static red wash.
    pulse = 0.55 + 0.45 * math.sin(t * 0.0022)
    fault = 0.22 if (t % 5200.0) < 160.0 else 0.0
    red = min(1.0, pulse * 0.7 + fault)

    def W(x, y):
        return (int(x + ox), int(y + oy))

    _ko_concrete(surface, (11, 7, 8), (26, 14, 13))
    layer = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
    cx = WIDTH // 2
    floor_y = SCENE_TOP + 330

    # Floor + the console bank across the back of the booth.
    pygame.draw.rect(surface, (20, 12, 12), (0, floor_y, WIDTH, HEIGHT - floor_y))
    for i in range(6):
        y = floor_y + 18 + i * 44
        pygame.draw.line(surface, (34, 20, 19), (0, y), (WIDTH, y), 2)
    desk_x, desk_y, desk_w, desk_h = cx - 250, floor_y - 96, 500, 96
    pygame.draw.rect(surface, (30, 20, 20),
                     (*W(desk_x, desk_y), desk_w, desk_h), border_radius=6)
    pygame.draw.rect(surface, (86, 54, 48),
                     (*W(desk_x, desk_y), desk_w, desk_h), 2, border_radius=6)
    pygame.draw.rect(surface, (14, 10, 10),
                     (*W(desk_x + 16, desk_y - 26), desk_w - 32, 28), border_radius=4)

    # Dead monitors: a housing bar behind the bank, residual glow, no image.
    # One keeps a rolling scan flicker so the wall is never fully static.
    hous_y = desk_y - 150
    pygame.draw.rect(surface, (22, 15, 15),
                     (*W(desk_x + 18, hous_y - 8), desk_w - 36, 92), border_radius=4)
    pygame.draw.rect(surface, (64, 40, 36),
                     (*W(desk_x + 18, hous_y - 8), desk_w - 36, 92), 2,
                     border_radius=4)
    for i in range(4):
        mw = 96
        mx = desk_x + 30 + i * ((desk_w - 60) // 4)
        my = desk_y - 132
        rect = pygame.Rect(*W(mx, my), mw, 78)
        pygame.draw.rect(surface, (10, 8, 8), rect, border_radius=3)
        alive = 0.10 + 0.05 * math.sin(t * 0.004 + i * 1.7)
        pygame.draw.rect(surface,
                         (int(70 * alive), int(12 * alive), int(12 * alive)), rect, 2,
                         border_radius=3)
        if i == 2:
            sweep = int((t * 0.32) % 78)
            line = pygame.Surface((mw, 2), pygame.SRCALPHA)
            line.fill((150, 40, 30, 120))
            surface.blit(line, W(mx, my + sweep))
        _ko_glow(surface, (255, 60, 50), (rect.centerx + ox, rect.centery + oy),
                 58, int(10 + 12 * alive))

    # ON AIR sign, dark and dead - the one that should have been hers.
    sign_y = desk_y - 214
    pygame.draw.rect(surface, (24, 10, 10), (*W(cx - 84, sign_y), 168, 40),
                     border_radius=4)
    pygame.draw.rect(surface, (74, 30, 26), (*W(cx - 84, sign_y), 168, 40), 2,
                     border_radius=4)
    off = font_terminal.render(_T("m3broadcast.on_air"), True, (74, 32, 28))
    surface.blit(off, W(cx - off.get_width() // 2, sign_y + 7))

    # Emergency dome: a tight bloom over the sign, NOT a frame-wide red wash -
    # the room has to stay a room. Soft ellipse only; a hard-filled dome plate
    # read as a red card taped to the shot.
    dome_x, dome_y = cx + 190, sign_y - 30
    pygame.draw.rect(surface, (54, 30, 28), (*W(dome_x - 24, dome_y), 48, 10),
                     border_radius=3)
    dome_g = pygame.Surface((160, 96), pygame.SRCALPHA)
    for i, shrink in enumerate((0, 14, 28)):
        a = int((150 + 50 * red) * (0.35 + 0.22 * i))
        pygame.draw.ellipse(dome_g, (255, 92, 72, a),
                            (shrink, shrink // 2,
                             160 - shrink * 2, 96 - shrink))
    surface.blit(dome_g, W(dome_x - 80, dome_y - 4))
    _ko_glow(surface, (255, 70, 60), (dome_x + ox, dome_y + 24 + oy), 140,
             int(28 + 26 * red))
    _draw_light_cone(surface, dome_x + int(ox), dome_y + 30 + int(oy), 190,
                     (255, 70, 60), alpha=int(14 + 14 * red))
    wash = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
    wash.fill((200, 26, 22, int(10 + 14 * red)))
    surface.blit(wash, (0, 0))

    # Cold desk lamp, still on, the only honest light in the room.
    lamp_x = cx - 330
    lamp_top = W(lamp_x, floor_y - 250)
    pygame.draw.line(surface, (58, 50, 46), lamp_top, W(lamp_x, floor_y - 96), 6)
    # Shade + bulb, then the pool it throws on the desk.
    pygame.draw.polygon(surface, (86, 94, 104), [
        W(lamp_x - 30, floor_y - 118), W(lamp_x + 30, floor_y - 118),
        W(lamp_x + 18, floor_y - 96), W(lamp_x - 18, floor_y - 96)])
    pygame.draw.line(surface, (126, 138, 150), W(lamp_x - 30, floor_y - 118),
                     W(lamp_x + 30, floor_y - 118), 2)
    pygame.draw.circle(surface, (196, 220, 240), W(lamp_x, floor_y - 100), 5)
    pool = pygame.Surface((300, 64), pygame.SRCALPHA)
    pygame.draw.ellipse(pool, (170, 200, 230, 34), (0, 0, 300, 64))
    surface.blit(pool, W(lamp_x - 150, floor_y - 96))
    _draw_light_cone(surface, lamp_x + int(ox), floor_y - 96 + int(oy), 170,
                     (170, 200, 230), alpha=18)
    _ko_glow(surface, (190, 215, 240), (lamp_x + ox, floor_y - 100 + oy), 60, 30)

    # The dossier, face-down on the desk. It is still the win condition.
    file_rect = pygame.Rect(*W(cx + 60, desk_y + 16), 74, 54)
    pygame.draw.rect(surface, (74, 58, 40), file_rect, border_radius=3)
    pygame.draw.rect(surface, (140, 48, 40), file_rect, 2, border_radius=3)
    seal = font_terminal_small.render(_T("m3broadcast.vostral"), True, (196, 164, 118))
    seal = pygame.transform.smoothscale(
        seal, (max(1, int(seal.get_width() * 0.6)), max(1, int(seal.get_height() * 0.6))))
    surface.blit(seal, (file_rect.centerx - seal.get_width() // 2,
                        file_rect.y + int(9)))

    # Biribel: standing at the console, not advancing, facing the dead sign.
    # Drawn lit (not a silhouette) so the red key reads ON her - the room is
    # the antagonist of this shot, she is not a cardboard cutout in it.
    _ko_actor(surface, "biribel", *W(cx - 150, floor_y + 44), scale=0.74,
              facing_right=True, t=t, moving=False)

    _draw_dust_motes(surface, t)
    surface.blit(layer, (0, 0))
    _ko_tint(surface)
    _ko_tag(surface, "STATE STUDIO // FEED LOST")
    return (cx - 120 + ox, floor_y - 90 + oy, 1.04 + 0.10 * _ko_clamp01(t / 4000.0))


def _draw_m3_bcast_fail_studio(surface, t):
    buf = _bc_buf()
    fx, fy, z = _draw_m3_bcast_fail_studio_raw(buf, t)
    _ko_push(surface, buf, z, fx, fy)


def _draw_m3_bcast_fail_pa_raw(surface, t):
    """The address finishing: Balaceanu on the monitor wall, tally on.

    The same figure used in the interrogation monitor, played large across a
    wall of CRTs and graded into the studio's red key so the frame reads as
    live state television rather than an illustration of him.
    """
    ox, oy = _cb_camera_shake(t, 0.5, 0.5)
    sweep = (t * 0.18) % 2000.0

    def W(x, y):
        return (int(x + ox), int(y + oy))

    _ko_concrete(surface, (8, 6, 7), (20, 13, 12))
    layer = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
    cx = WIDTH // 2

    # Monitor wall: 3 x 2 grid of CRTs behind the control glass. Sized so the
    # wall, the tally and the shared location-tag band (HEIGHT-250) never
    # stack on top of each other.
    cols, rows = 3, 2
    wall_w, wall_h = 700, 250
    wall_x, wall_y = cx - wall_w // 2, SCENE_TOP + 16
    pygame.draw.rect(surface, (16, 12, 12),
                     (*W(wall_x - 22, wall_y - 22), wall_w + 44, wall_h + 44),
                     border_radius=8)
    pygame.draw.rect(surface, (70, 46, 42),
                     (*W(wall_x - 22, wall_y - 22), wall_w + 44, wall_h + 44), 2,
                     border_radius=8)
    gap_x = wall_w // cols
    gap_y = wall_h // rows
    for r in range(rows):
        for c in range(cols):
            mx = wall_x + c * gap_x + 8
            my = wall_y + r * gap_y + 8
            mw, mh = gap_x - 16, gap_y - 16
            crt = pygame.Surface((mw, mh))
            crt.fill((22, 5, 5))
            pygame.draw.rect(crt, (46, 9, 10), (8, 8, mw - 16, mh - 22),
                             border_radius=3)
            # Balaceanu on the feed, at podium scale per tile.
            pygame.draw.rect(crt, (44, 8, 9), (10, 10, mw - 20, mh - 26),
                             border_radius=2)
            _m3_draw_balaceanu(crt, mw // 2, mh - 22, scale=0.30,
                               facing_left=bool(c % 2))
            red_wash = pygame.Surface((mw, mh), pygame.SRCALPHA)
            red_wash.fill((26, 2, 2, 60))
            crt.blit(red_wash, (0, 0), special_flags=pygame.BLEND_RGBA_ADD)
            ghost = crt.copy()
            ghost.set_alpha(54)
            crt.blit(ghost, (3, 0))
            # Scanlines + a slow vertical roll bar so the wall is alive.
            for ly in range(0, mh, 3):
                pygame.draw.line(crt, (0, 0, 0), (0, ly), (mw, ly), 1)
            roll = int((t * 0.10 + c * 130 + r * 90) % mh)
            bar = pygame.Surface((mw, 3), pygame.SRCALPHA)
            bar.fill((255, 120, 100, 40))
            crt.blit(bar, (0, roll))
            pygame.draw.rect(surface, (8, 6, 6), (*W(mx, my), mw, mh), border_radius=3)
            pygame.draw.rect(surface, (120, 40, 34), (*W(mx, my), mw, mh), 2,
                             border_radius=3)
            surface.blit(crt, W(mx, my))
            _ko_glow(surface, (255, 70, 60), (mx + mw // 2 + ox, my + mh // 2 + oy),
                     90, 14)

    # Control-glass reflection + a slow pass of the room's key light.
    glass = pygame.Surface((wall_w, wall_h), pygame.SRCALPHA)
    glass.fill((180, 200, 230, 12))
    surface.blit(glass, W(wall_x, wall_y))
    band_x = wall_x + int((sweep / 2000.0) * wall_w) - 70
    band = pygame.Surface((140, wall_h), pygame.SRCALPHA)
    band.fill((210, 225, 245, 16))
    surface.blit(band, W(band_x, wall_y))

    # Tally: ON, and it is not ours.
    tally_y = wall_y + wall_h + 30
    tally = font_terminal.render(_T("m3broadcast.address_complete"), True, (255, 96, 86))
    surface.blit(tally, W(cx - tally.get_width() // 2, tally_y))
    _ko_glow(surface, (255, 70, 60), (cx + ox, tally_y + 14 + oy), 190, 24)
    dot_on = (t % 1400.0) < 900.0
    if dot_on:
        pygame.draw.circle(surface, (255, 70, 60),
                           W(cx - tally.get_width() // 2 - 26, tally_y + 8), 7)
        _ko_glow(surface, (255, 70, 60),
                 (cx - tally.get_width() // 2 - 26 + ox, tally_y + 8 + oy), 34, 40)

    wash = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
    wash.fill((210, 30, 24, 20))
    surface.blit(wash, (0, 0))

    _draw_dust_motes(surface, t)
    surface.blit(layer, (0, 0))
    _ko_tint(surface)
    _ko_tag(surface, "STATE ADDRESS // 22:00 ON AIR")
    return (cx + ox, wall_y + wall_h // 2 + oy,
            1.05 + 0.14 * _ko_clamp01(t / 5200.0))


def _draw_m3_bcast_fail_pa(surface, t):
    buf = _bc_buf()
    fx, fy, z = _draw_m3_bcast_fail_pa_raw(buf, t)
    _ko_push(surface, buf, z, fx, fy)


def _draw_m3_bcast_fail_retry_raw(surface, t):
    """The re-arm plate: feed released, wing reset, clock back to full.

    Deliberately cold and quiet after two red shots - a dead-green terminal
    plate with static breathing behind it, so the retry reads as a system
    handing the wing back rather than another thing going wrong.
    """
    ox, oy = _cb_camera_shake(t, 0.35, 0.35)
    cx = WIDTH // 2

    def W(x, y):
        return (int(x + ox), int(y + oy))

    _draw_vertical_gradient(surface, 0, 0, WIDTH, HEIGHT, (4, 7, 7), (9, 15, 14))
    layer = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)

    # Rolling static behind the plate - recycled bands, so a held shot lives.
    band_h = 14
    for y in range(0, HEIGHT, band_h):
        k = (y + int(t * 0.11)) // band_h
        a = 6 + int(9 * (0.5 + 0.5 * math.sin(k * 1.7 + t * 0.004)))
        b = pygame.Surface((WIDTH, band_h), pygame.SRCALPHA)
        b.fill((120, 190, 150, a))
        layer.blit(b, (0, y))

    # The plate.
    pw, ph = 520, 210
    px, py = cx - pw // 2, SCENE_TOP + 120
    pygame.draw.rect(surface, (7, 13, 11), (*W(px - 10, py - 10), pw + 20, ph + 20),
                     border_radius=6)
    pygame.draw.rect(surface, (70, 130, 100), (*W(px - 10, py - 10), pw + 20, ph + 20),
                     2, border_radius=6)
    pygame.draw.rect(surface, (10, 20, 16), (*W(px, py), pw, ph))
    pygame.draw.rect(surface, (52, 104, 80), (*W(px, py), pw, ph), 1)

    head = font_terminal.render(_T("m3broadcast.studio_feed_released"), True, (150, 235, 180))
    surface.blit(head, W(cx - head.get_width() // 2, py + 34))
    # Blinking cursor keeps the plate alive while the caption types.
    if (t % 900.0) < 520.0:
        pygame.draw.rect(surface, (150, 235, 180),
                         (*W(px + 34, py + 82), pw - 68, 3))
    line1 = font_terminal_small.render(_T("m3broadcast.broadcast_wing_re_arming"), True, (96, 170, 132))
    surface.blit(line1, W(cx - line1.get_width() // 2, py + 104))
    line2 = font_terminal_small.render(_T("m3broadcast.address_slot_22_00_reclaimed"), True,
                                       (78, 138, 108))
    surface.blit(line2, W(cx - line2.get_width() // 2, py + 126))

    # A single green telltale on the plate bezel: the wing is ours again.
    tell = 0.6 + 0.4 * math.sin(t * 0.006)
    pygame.draw.circle(surface, (120, 220, 160),
                       W(px + pw - 26, py + 20), 5)
    _ko_glow(surface, (120, 220, 160), (px + pw - 26 + ox, py + 20 + oy), 40,
             int(30 + 34 * tell))

    _ko_glow(surface, (120, 220, 160), (cx + ox, py + ph // 2 + oy), 300, 12)
    surface.blit(layer, (0, 0))
    _ko_tint(surface)
    _ko_tag(surface, "STUDIO TERMINAL // RE-ENTRY")
    return (cx + ox, py + ph // 2 + oy, 1.03 + 0.09 * _ko_clamp01(t / 3000.0))


def _draw_m3_bcast_fail_retry(surface, t):
    buf = _bc_buf()
    fx, fy, z = _draw_m3_bcast_fail_retry_raw(buf, t)
    _ko_push(surface, buf, z, fx, fy)


# RPE6 Phase 2 (A-003 take registry): the cutscene scene ids this module owns.
# cutscenes.engine.draw_cutscene_scene finds them through core.cutscene_registry
# instead of importing this module by name (boundary rule 4 / W1).
from core.cutscene_registry import register_scene_renderers as _register_takes  # noqa: E402
from engine.text import T as _T  # RPE6 Phase 4 text table

_register_takes({
    "m3_bcast_shutter": _draw_m3_bcast_shutter,
    "m3_bcast_road": _draw_m3_bcast_road,
    "m3_bcast_mast": _draw_m3_bcast_mast,
    "m3_bcast_onair": _draw_m3_bcast_onair,
    "m3_bcast_fail_studio": _draw_m3_bcast_fail_studio,
    "m3_bcast_fail_pa": _draw_m3_bcast_fail_pa,
    "m3_bcast_fail_retry": _draw_m3_bcast_fail_retry,
})
