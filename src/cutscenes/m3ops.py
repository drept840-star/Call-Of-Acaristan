"""Split from cutscenes.py - see cutscenes.py (shim) for the map."""
# cutscenes package
# ------------------------------------------------------------

"""Cutscene visuals and dialogue: character drawings, scene backgrounds, shot lists."""
import math
import random
import pygame

from core import render_util
from core.config import (HEIGHT, SCENE_BOT, SCENE_TOP, WIDTH, font_terminal, font_terminal_small)

from cutscenes.cast import draw_volkov
from cutscenes.figure_kit import draw_character as _fk_draw
from cutscenes.route12 import _lerp_cutscene

def _draw_k9_pickup_bg(surface, t):
    """Draw a quiet, shallow armory wall behind the first-person action.

    This is a practical background, not an interface panel: the rack stays
    small enough to leave room for the hands and weapon to come toward camera.
    """
    surface.fill((6, 8, 8))
    for y in range(SCENE_TOP, SCENE_BOT):
        p = (y - SCENE_TOP) / max(1, SCENE_BOT - SCENE_TOP)
        wall = (int(11 + p * 16), int(15 + p * 16), int(15 + p * 15))
        pygame.draw.line(surface, wall, (0, y), (WIDTH, y))

    # Large wall seams stay soft and low contrast behind the action.
    for x in range(80, WIDTH, 160):
        pygame.draw.line(surface, (17, 23, 23), (x, SCENE_TOP), (x, SCENE_BOT), 1)
    for y in range(SCENE_TOP + 70, SCENE_BOT, 92):
        pygame.draw.line(surface, (17, 23, 23), (70, y), (WIDTH - 70, y), 1)

    rack = pygame.Rect(WIDTH // 2 - 245, SCENE_TOP + 105, 490, 230)
    shadow = pygame.Surface((rack.w + 30, rack.h + 30), pygame.SRCALPHA)
    pygame.draw.rect(shadow, (0, 0, 0, 105), shadow.get_rect(), border_radius=7)
    surface.blit(shadow, (rack.x - 15, rack.y + 13))
    pygame.draw.rect(surface, (8, 12, 12), rack, border_radius=5)
    inset = rack.inflate(-12, -12)
    pygame.draw.rect(surface, (11, 16, 16), inset, border_radius=3)
    pygame.draw.rect(surface, (57, 71, 67), rack, 2, border_radius=5)
    pygame.draw.line(surface, (88, 104, 96),
                     (rack.x + 18, rack.y + 36), (rack.right - 18, rack.y + 36), 2)
    pygame.draw.line(surface, (35, 47, 44),
                     (rack.x + 24, rack.y + 88), (rack.right - 24, rack.y + 88), 2)
    pygame.draw.line(surface, (35, 47, 44),
                     (rack.x + 24, rack.y + 142), (rack.right - 24, rack.y + 142), 2)
    title = font_terminal_small.render(_T("m3ops.armory_rack_k_9"), True, (118, 155, 136))
    surface.blit(title, (rack.x + 20, rack.y + 13))

    # Corner fasteners. They give the rack a physical edge without adding
    # more labels or status graphics to the shot.
    for bx in (rack.x + 18, rack.right - 18):
        for by in (rack.y + 16, rack.bottom - 16):
            pygame.draw.circle(surface, (74, 83, 75), (bx, by), 3)
            pygame.draw.circle(surface, (16, 20, 18), (bx, by), 1)
    return rack


def _k9_clamp01(value):
    return max(0.0, min(1.0, float(value)))


def _k9_smooth(value):
    """Cubic ease used for hand and camera motion in the pickup."""
    p = _k9_clamp01(value)
    return p * p * (3.0 - 2.0 * p)


def _k9_soft_glow(surface, center, radius, color, alpha):
    """Small deterministic radial glow, kept deliberately below bloom scale."""
    radius = max(2, int(radius))
    glow = pygame.Surface((radius * 2, radius * 2), pygame.SRCALPHA)
    for r in range(radius, 4, -10):
        a = int(alpha * (1.0 - r / radius) ** 1.7)
        if a > 0:
            pygame.draw.circle(glow, (*color, a), (radius, radius), r)
    surface.blit(glow, (int(center[0] - radius), int(center[1] - radius)))


def _draw_k9_smg_fp(surface, cx, cy, t, held=False, scale=1.0, angle=0.0):
    """Compact first-person K-9 drawing.

    Short receiver, short integral suppressor, collapsed wire stock, straight
    stick mag. Avoids the previous long LMG-looking silhouette.  ``angle`` is
    rendered on a transparent layer so the weapon can have a subtle handheld
    tilt without distorting the clean component geometry.
    """
    if abs(angle) > 0.05:
        layer = pygame.Surface((420, 270), pygame.SRCALPHA)
        _draw_k9_smg_fp(layer, 210, 112, t, held=False, scale=scale, angle=0.0)
        rotated = pygame.transform.rotate(layer, angle)
        surface.blit(rotated, rotated.get_rect(center=(int(cx), int(cy))))
        if held:
            _draw_k9_grab_hands(surface, cx, cy, scale, t)
        return

    s = scale
    def S(v): return int(v * s)

    # Coordinates in rack/screen space.
    rec = pygame.Rect(cx - S(86), cy - S(18), S(130), S(36))
    # Receiver body and the narrow highlight that sells its metal edge.
    pygame.draw.rect(surface, (21, 25, 25), rec, border_radius=S(6))
    pygame.draw.rect(surface, (82, 100, 94), rec, 2, border_radius=S(6))
    pygame.draw.line(surface, (145, 166, 151), (rec.x + S(12), rec.y + S(7)),
                     (rec.right - S(16), rec.y + S(7)), max(1, S(2)))
    pygame.draw.line(surface, (38, 48, 44), (rec.x + S(8), rec.bottom - S(5)),
                     (rec.right - S(14), rec.bottom - S(5)), max(1, S(2)))
    # Ejection/safety detail.
    pygame.draw.rect(surface, (10, 13, 13), (rec.x + S(48), rec.y + S(14), S(26), S(9)), border_radius=S(2))
    pygame.draw.circle(surface, (65, 160, 105), (rec.x + S(23), rec.y + S(19)), max(2, S(3)))
    pygame.draw.line(surface, (120, 150, 130),
                     (rec.x + S(19), rec.y + S(29)), (rec.x + S(36), rec.y + S(29)), max(1, S(2)))

    # Short suppressor.
    sup = pygame.Rect(rec.right - S(5), cy - S(10), S(62), S(20))
    pygame.draw.rect(surface, (34, 40, 40), sup, border_radius=S(8))
    pygame.draw.rect(surface, (100, 116, 108), sup, 1, border_radius=S(8))
    pygame.draw.circle(surface, (5, 7, 7), (sup.right, cy), max(3, S(6)))

    # Straight magazine, shorter.
    mag = pygame.Rect(cx - S(16), cy + S(18), S(22), S(70))
    pygame.draw.rect(surface, (16, 19, 19), mag, border_radius=S(3))
    pygame.draw.rect(surface, (82, 96, 88), mag, 2, border_radius=S(3))
    for row in range(7):
        yy = mag.y + S(10) + row * S(8)
        pygame.draw.circle(surface, (190, 160, 58), (mag.x + S(7), yy), max(1, S(2)))
        pygame.draw.circle(surface, (190, 160, 58), (mag.x + S(15), yy), max(1, S(2)))
    pygame.draw.rect(surface, (10, 12, 12), (mag.x, mag.bottom - S(7), mag.w, S(8)), border_radius=S(2))

    # Collapsed wire stock.
    pygame.draw.line(surface, (65, 74, 70), (rec.x + S(5), cy + S(8)), (rec.x - S(48), cy + S(25)), max(1, S(3)))
    pygame.draw.line(surface, (42, 48, 46), (rec.x + S(5), cy - S(5)), (rec.x - S(48), cy + S(12)), max(1, S(2)))
    pygame.draw.circle(surface, (45, 52, 50), (rec.x - S(48), cy + S(25)), max(2, S(4)))

    # Pistol grip.
    grip = [(cx - S(62), cy + S(16)), (cx - S(38), cy + S(16)),
            (cx - S(45), cy + S(64)), (cx - S(68), cy + S(64))]
    pygame.draw.polygon(surface, (18, 21, 21), grip)
    pygame.draw.polygon(surface, (78, 88, 84), grip, 2)

    # Label on receiver, small and grounded.
    label = font_terminal_small.render(_T("m3ops.k_9"), True, (166, 220, 193))
    surface.blit(label, (cx - label.get_width() // 2 + S(15), cy - S(6)))

    if held:
        _draw_k9_grab_hands(surface, cx, cy, scale, t)


def _k9_draw_arm(surface, start, end, width, sleeve=(48, 57, 53)):
    """Draw a broad tapered sleeve instead of a straight line arm."""
    base = max(8, int(width))
    wrist = max(7, int(base * 0.54))
    dx, dy = float(end[0] - start[0]), float(end[1] - start[1])
    length = max(1.0, math.hypot(dx, dy))
    px, py = -dy / length, dx / length
    outline = [
        (int(start[0] + px * (base + 5) / 2), int(start[1] + py * (base + 5) / 2)),
        (int(start[0] - px * (base + 5) / 2), int(start[1] - py * (base + 5) / 2)),
        (int(end[0] - px * (wrist + 5) / 2), int(end[1] - py * (wrist + 5) / 2)),
        (int(end[0] + px * (wrist + 5) / 2), int(end[1] + py * (wrist + 5) / 2)),
    ]
    body = [
        (int(start[0] + px * base / 2), int(start[1] + py * base / 2)),
        (int(start[0] - px * base / 2), int(start[1] - py * base / 2)),
        (int(end[0] - px * wrist / 2), int(end[1] - py * wrist / 2)),
        (int(end[0] + px * wrist / 2), int(end[1] + py * wrist / 2)),
    ]
    pygame.draw.polygon(surface, (10, 13, 13), outline)
    pygame.draw.polygon(surface, sleeve, body)
    highlight = [body[0], body[3],
                 (int(end[0] + px * wrist * 0.18), int(end[1] + py * wrist * 0.18)),
                 (int(start[0] + px * base * 0.18), int(start[1] + py * base * 0.18))]
    pygame.draw.polygon(surface, (79, 91, 82), highlight)


def _k9_draw_glove(surface, pos, scale=1.0, side=1):
    """Compact tactical glove silhouette for a low-resolution first-person shot."""
    x, y = float(pos[0]), float(pos[1])
    s = float(scale)
    w, h = 30 * s, 38 * s
    edge = (9, 13, 12)
    glove = (35, 45, 41)
    glove_hi = (83, 98, 87)
    glove_mid = (53, 65, 57)
    # Knuckle block and cuff read as one object with the sleeve, avoiding the
    # disconnected tan circles that started this pass.
    palm = [(x - w * 0.48, y - h * 0.28),
            (x - w * 0.30, y - h * 0.50),
            (x + w * 0.30, y - h * 0.50),
            (x + w * 0.48, y - h * 0.20),
            (x + w * 0.40, y + h * 0.42),
            (x + w * 0.20, y + h * 0.54),
            (x - w * 0.34, y + h * 0.48)]
    pygame.draw.polygon(surface, edge, palm)
    inner = [(x + (px - x) * 0.88, y + (py - y) * 0.88) for px, py in palm]
    pygame.draw.polygon(surface, glove, inner)
    # Four knuckle plates and the leather crease across the palm.
    for i in range(4):
        kx = x - w * 0.27 + i * w * 0.18
        pygame.draw.line(surface, glove_hi, (int(kx), int(y - h * 0.30)),
                         (int(kx + side * w * 0.04), int(y - h * 0.10)), max(1, int(s)))
    pygame.draw.line(surface, glove_mid,
                     (int(x - w * 0.30), int(y + h * 0.08)),
                     (int(x + w * 0.28), int(y + h * 0.18)), max(1, int(s)))
    # Thumb bridges toward the weapon; the three short seams imply curled
    # fingers without drawing a row of detached flesh-colored spikes.
    thumb_dir = -side
    pygame.draw.line(surface, edge,
                     (int(x + thumb_dir * w * 0.26), int(y + h * 0.06)),
                     (int(x + thumb_dir * w * 0.72), int(y + h * 0.25)), max(3, int(8 * s)))
    pygame.draw.line(surface, glove_hi,
                     (int(x + thumb_dir * w * 0.25), int(y + h * 0.02)),
                     (int(x + thumb_dir * w * 0.68), int(y + h * 0.21)), max(1, int(2 * s)))
    for i in range(3):
        yy = y - h * 0.04 + i * h * 0.16
        pygame.draw.line(surface, glove_hi,
                         (int(x + side * w * 0.30), int(yy)),
                         (int(x + side * w * 0.63), int(yy + h * 0.04)), max(1, int(s)))


def _draw_k9_grab_hands(surface, cx, cy, scale, t):
    """Animate a right-hand grip and a left support hand into frame."""
    entry = _k9_smooth((t - 360.0) / 420.0)
    if entry <= 0.01:
        return
    settle = _k9_smooth((t - 860.0) / 300.0)
    s = float(scale)
    # Dominant hand closes around the pistol grip; the support hand arrives
    # underneath the magazine well.  These targets follow the weapon as it
    # approaches camera, so the contact points remain believable.
    dominant_target = (cx - 53 * s, cy + 47 * s)
    support_target = (cx + 5 * s, cy + 46 * s)
    # Keep each forearm on its own side of frame.  Crossing the two sleeves
    # made the previous pass read like a pair of cables instead of a grip.
    dominant_start = (cx - 245, HEIGHT + 48)
    support_start = (cx + 245, HEIGHT + 48)
    dominant = (dominant_start[0] + (dominant_target[0] - dominant_start[0]) * entry,
                dominant_start[1] + (dominant_target[1] - dominant_start[1]) * entry)
    support = (support_start[0] + (support_target[0] - support_start[0]) * entry,
               support_start[1] + (support_target[1] - support_start[1]) * entry)
    _k9_draw_arm(surface, dominant_start, dominant, max(28, int(42 * s)))
    _k9_draw_arm(surface, support_start, support, max(26, int(39 * s)), sleeve=(43, 52, 49))
    # Tactical gloves keep the silhouette readable at the cutscene resolution.
    hand_scale = max(0.92, min(1.45, 0.76 * s))
    _k9_draw_glove(surface, dominant, hand_scale, side=1)
    _k9_draw_glove(surface, support, hand_scale, side=-1)
    if settle > 0.0:
        pygame.draw.line(surface, (211, 162, 116),
                         (int(dominant[0] - 7 * s), int(dominant[1] - 4 * s)),
                         (int(dominant[0] - 12 * s), int(dominant[1] + 7 * s)), 2)
        pygame.draw.line(surface, (211, 162, 116),
                         (int(support[0] + 7 * s), int(support[1] - 4 * s)),
                         (int(support[0] + 12 * s), int(support[1] + 7 * s)), 2)


def _draw_k9_wall_stand(surface, t):
    # lazy: preserve the existing facade and engine dispatch contracts.
    from cutscenes.k9 import draw_wall
    draw_wall(surface, t)


def _draw_k9_firstperson_grab(surface, t):
    from cutscenes.k9 import draw_grab  # lazy: K-9 art is cached on first use
    draw_grab(surface, t)


def _draw_k9_ready_check(surface, t):
    from cutscenes.k9 import draw_ready  # lazy: no changes to other M3 scenes
    draw_ready(surface, t)


def _draw_m3_volkov_radio_call(surface, t):
    """Transition beat: Volkov throws Biribel's radio and Biribel catches it.

    Clear staging:
      1. Volkov yells from the service doorway.
      2. The radio flies across the frame.
      3. Biribel's hands rise into frame and catch it near the end.

    The next shot is the close-up power-on insert.
    """
    surface.fill((4, 5, 6))
    cx = WIDTH // 2
    floor_y = SCENE_BOT - 78

    # Service corridor / door backdrop.
    for y in range(SCENE_TOP, SCENE_BOT):
        pbg = (y - SCENE_TOP) / max(1, SCENE_BOT - SCENE_TOP)
        pygame.draw.line(surface, (int(7 + pbg * 18), int(9 + pbg * 20), int(10 + pbg * 18)), (0, y), (WIDTH, y))
    pygame.draw.polygon(surface, (16, 19, 20), [(0, floor_y), (WIDTH, floor_y), (WIDTH, SCENE_BOT), (0, SCENE_BOT)])
    for x in range(0, WIDTH, 110):
        pygame.draw.line(surface, (23, 27, 27), (x, floor_y), (x + 50, SCENE_BOT), 1)

    # Backlit doorway with Volkov.
    door = pygame.Rect(cx - 320, SCENE_TOP + 76, 230, 360)
    pygame.draw.rect(surface, (4, 5, 6), door.inflate(24, 24), border_radius=5)
    pygame.draw.rect(surface, (52, 78, 70), door, border_radius=3)
    pygame.draw.rect(surface, (115, 170, 145), door, 2, border_radius=3)
    spill = pygame.Surface((340, 260), pygame.SRCALPHA)
    pygame.draw.polygon(spill, (90, 140, 120, 34), [(120, 0), (220, 0), (340, 260), (0, 260)])
    surface.blit(spill, (door.centerx - 170, door.bottom - 20))
    draw_volkov(surface, door.centerx - 12, floor_y + 16, scale=0.62,
                facing_right=True, act_t=t / 1000.0)

    # Throw origin. Do NOT draw a custom arm here: the base Volkov sprite
    # already has arms, and the extra cutscene-only arm read as a detached hand.
    # The radio begins near his silhouette and immediately becomes the focus.
    throw_origin = (door.centerx + 58, floor_y - 142)
    # Tiny dark motion wedge from his hand area, connected enough to imply a toss
    # without adding a separate limb.
    pygame.draw.line(surface, (18, 18, 24),
                     (door.centerx + 16, floor_y - 145),
                     (throw_origin[0], throw_origin[1]), 5)

    # Shout marks near Volkov's head.
    for i in range(3):
        pygame.draw.arc(surface, (210, 170, 90, 118 - i * 32),
                        (door.centerx + 28 + i * 12, floor_y - 198 - i * 8, 92 + i * 20, 62 + i * 12),
                        -0.55, 0.42, 2)

    # Throw path: radio travels to Biribel's hands, then stays caught for the
    # rest of the shot. The catch happens early enough that the dialogue beat
    # clearly shows Biribel receiving it, not just watching it fly by.
    p = min(1.0, max(0.0, t / 1150.0))
    flight = min(1.0, p / 0.70)
    ease = 1.0 - (1.0 - flight) * (1.0 - flight)
    start_x, start_y = throw_origin[0] + 14, throw_origin[1] - 8
    catch_x, catch_y = cx + 190, floor_y - 125
    arc = math.sin(flight * math.pi) * 38
    radio_cx = start_x + (catch_x - start_x) * ease
    radio_cy = start_y + (catch_y - start_y) * ease - arc

    catch_p = min(1.0, max(0.0, (p - 0.34) / 0.30))
    caught = catch_p >= 1.0
    # Once caught, lock the radio between Biribel's hands.
    if caught:
        radio_cx = catch_x
        radio_cy = catch_y
    tilt = (-20 + 42 * flight) * (1.0 - 0.85 * catch_p)

    # Helper for tapered first-person forearms.
    def forearm(shoulder, wrist, col, hi=None, w0=20, w1=8):
        sx, sy = shoulder
        wx, wy = wrist
        dx, dy = wx - sx, wy - sy
        dist = max(1.0, math.hypot(dx, dy))
        px, py = -dy / dist, dx / dist
        poly = [
            (sx + px * w0, sy + py * w0),
            (sx - px * w0, sy - py * w0),
            (wx - px * w1, wy - py * w1),
            (wx + px * w1, wy + py * w1),
        ]
        pygame.draw.polygon(surface, col, poly)
        pygame.draw.polygon(surface, (8, 9, 9), poly, 1)
        if hi:
            pygame.draw.line(surface, hi, (sx + px * w0 * 0.35, sy + py * w0 * 0.35),
                             (wx + px * w1 * 0.25, wy + py * w1 * 0.25), 1)

    # Biribel's hands enter and catch. They are absent early, so it reads as a
    # throw first, catch second.
    skin = (176, 132, 100)
    sleeve = (58, 68, 52)
    left_hand = (radio_cx - 36, radio_cy + 24)
    right_hand = (radio_cx + 38, radio_cy + 20)
    if catch_p > 0.02:
        # Hands move in from below/right and clamp around the radio.
        def lerp(a, b, q): return a + (b - a) * q
        q = catch_p * catch_p * (3 - 2 * catch_p)
        lh = (lerp(WIDTH - 260, left_hand[0], q), lerp(HEIGHT + 28, left_hand[1], q))
        rh = (lerp(WIDTH - 105, right_hand[0], q), lerp(HEIGHT + 30, right_hand[1], q))
        forearm((WIDTH - 330, HEIGHT + 50), lh, sleeve, (94, 108, 80), 24, 10)
        forearm((WIDTH + 45, HEIGHT + 54), rh, sleeve, (94, 108, 80), 24, 10)
        pygame.draw.circle(surface, skin, (int(lh[0]), int(lh[1])), 14)
        pygame.draw.circle(surface, skin, (int(rh[0]), int(rh[1])), 14)
        if caught:
            # Small catch impact ticks at the wrists - not a magic effect, just
            # a readable punctuation that the device has landed in his hands.
            for hx, hy, sgn in ((lh[0], lh[1], -1), (rh[0], rh[1], 1)):
                pygame.draw.line(surface, (170, 205, 160),
                                 (int(hx + sgn * 10), int(hy - 10)),
                                 (int(hx + sgn * 20), int(hy - 18)), 2)
                pygame.draw.line(surface, (120, 150, 120),
                                 (int(hx + sgn * 7), int(hy + 5)),
                                 (int(hx + sgn * 17), int(hy + 10)), 1)

    # Motion ghosts only before catch.
    if not caught and flight < 0.92:
        for i, back in enumerate((0.16, 0.08)):
            pp = max(0.0, flight - back)
            ee = 1.0 - (1.0 - pp) * (1.0 - pp)
            tx = start_x + (catch_x - start_x) * ee
            ty = start_y + (catch_y - start_y) * ee - math.sin(pp * math.pi) * 38
            ghost = pygame.Surface((70, 42), pygame.SRCALPHA)
            pygame.draw.rect(ghost, (70, 105, 94, 42 - i * 14), (8, 10, 52, 24), border_radius=4)
            ghost = pygame.transform.rotate(ghost, tilt - 6 * i)
            surface.blit(ghost, (int(tx - ghost.get_width() // 2), int(ty - ghost.get_height() // 2)))

    # Radio body.
    radio_s = pygame.Surface((104, 64), pygame.SRCALPHA)
    body = pygame.Rect(20, 14, 62, 36)
    pygame.draw.rect(radio_s, (17, 22, 22), body, border_radius=5)
    pygame.draw.rect(radio_s, (92, 118, 106), body, 2, border_radius=5)
    pygame.draw.rect(radio_s, (6, 10, 10), (body.x + 10, body.y + 10, 29, 12), border_radius=2)
    pygame.draw.circle(radio_s, (80, 220, 130), (body.right - 10, body.y + 11), 3)
    pygame.draw.circle(radio_s, (30, 36, 34), (body.right - 15, body.bottom - 10), 5)
    pygame.draw.line(radio_s, (105, 112, 104), (body.x + 13, body.y), (body.x + 4, body.y - 28), 3)
    pygame.draw.line(radio_s, (45, 52, 50), (body.x + 11, body.y), (body.x + 2, body.y - 28), 1)
    radio_s = pygame.transform.rotate(radio_s, tilt)
    surface.blit(radio_s, (int(radio_cx - radio_s.get_width() // 2), int(radio_cy - radio_s.get_height() // 2)))

    # Fingers over radio once caught, making the catch explicit.
    if catch_p > 0.78:
        for hand_pt, side in ((left_hand, -1), (right_hand, 1)):
            for i in range(4):
                fx = hand_pt[0] + side * (i * 4 - 5)
                fy = hand_pt[1] - 7 + (i % 2)
                pygame.draw.line(surface, (132, 92, 66), (fx, fy), (fx + side * 12, fy - 8), 2)
        tag = font_terminal_small.render(_T("m3ops.caught"), True, (145, 210, 175))
        surface.blit(tag, (int(catch_x - tag.get_width() // 2), int(catch_y + 46)))
    else:
        tag = font_terminal_small.render(_T("m3ops.radio"), True, (200, 160, 90))
        surface.blit(tag, (cx - tag.get_width() // 2, SCENE_BOT - 86))


def _draw_m3_radio_recovered(surface, t):
    """Close first-person insert: Biribel catches and powers on the radio."""
    surface.fill((5, 7, 8))
    cx = WIDTH // 2
    cy = HEIGHT // 2 + 10
    # Metal table/floor plane, understated.
    for y in range(SCENE_TOP, SCENE_BOT):
        p = (y - SCENE_TOP) / max(1, SCENE_BOT - SCENE_TOP)
        pygame.draw.line(surface, (int(8 + p*18), int(12 + p*22), int(13 + p*22)), (0, y), (WIDTH, y))
    # Hands holding radio.
    skin = (176, 132, 100)
    sleeve = (58, 68, 52)
    pygame.draw.line(surface, sleeve, (cx - 210, HEIGHT + 35), (cx - 78, cy + 58), 34)
    pygame.draw.line(surface, sleeve, (cx + 210, HEIGHT + 35), (cx + 78, cy + 58), 34)
    pygame.draw.circle(surface, skin, (cx - 78, cy + 50), 24)
    pygame.draw.circle(surface, skin, (cx + 78, cy + 50), 24)
    # Radio body.
    radio = pygame.Rect(cx - 96, cy - 58, 192, 126)
    pygame.draw.rect(surface, (18, 24, 24), radio, border_radius=8)
    pygame.draw.rect(surface, (92, 116, 106), radio, 3, border_radius=8)
    pygame.draw.rect(surface, (6, 10, 10), (radio.x + 22, radio.y + 22, 88, 34), border_radius=3)
    pygame.draw.line(surface, (72, 82, 76), (radio.x + 130, radio.y + 8), (radio.x + 155, radio.y - 68), 4)
    for i in range(3):
        pygame.draw.circle(surface, (34, 40, 38), (radio.x + 136 + i*16, radio.y + 82), 7)
        pygame.draw.circle(surface, (100, 116, 104), (radio.x + 136 + i*16, radio.y + 82), 7, 1)
    # Screen boots up.
    boot = min(1.0, max(0.0, (t - 350) / 750.0))
    if boot > 0:
        glow = pygame.Surface((92, 34), pygame.SRCALPHA)
        glow.fill((80, 220, 130, int(50 + 120 * boot)))
        surface.blit(glow, (radio.x + 20, radio.y + 22), special_flags=pygame.BLEND_RGBA_ADD)
        wave_x = radio.x + 28
        wave_y = radio.y + 38
        pts = []
        for i in range(64):
            yy = wave_y + math.sin((i * 0.35) + t * 0.018) * (5 + 4 * boot)
            pts.append((wave_x + i, yy))
        if len(pts) > 1:
            pygame.draw.lines(surface, (120, 255, 170), False, pts, 2)
    text = font_terminal.render(_T("m3ops.krap_field_radio"), True, (145, 220, 175))
    surface.blit(text, (cx - text.get_width()//2, radio.bottom + 34))
    sub = font_terminal_small.render(_T("m3ops.signal_weak_relay_required"), True, (90, 135, 115))
    surface.blit(sub, (cx - sub.get_width()//2, radio.bottom + 62))



def _draw_m3_service_door_transition(surface, t):
    """Transition shot: leaving the cell block through the service door."""
    surface.fill((5, 6, 7))
    # Long service corridor, centered perspective.
    cx = WIDTH // 2
    top_y = SCENE_TOP + 40
    bot_y = SCENE_BOT - 40
    # Back wall / receding floor.
    for y in range(SCENE_TOP, SCENE_BOT):
        p = (y - SCENE_TOP) / max(1, SCENE_BOT - SCENE_TOP)
        pygame.draw.line(surface, (int(8 + p*20), int(10 + p*22), int(12 + p*20)), (0, y), (WIDTH, y))
    # Perspective walls.
    van_y = SCENE_TOP + 125
    pygame.draw.polygon(surface, (12, 14, 15), [(0, SCENE_TOP), (cx - 90, van_y), (cx - 180, bot_y), (0, SCENE_BOT)])
    pygame.draw.polygon(surface, (12, 14, 15), [(WIDTH, SCENE_TOP), (cx + 90, van_y), (cx + 180, bot_y), (WIDTH, SCENE_BOT)])
    pygame.draw.polygon(surface, (20, 23, 24), [(cx - 90, van_y), (cx + 90, van_y), (cx + 180, bot_y), (cx - 180, bot_y)])
    # Floor seams.
    for i in range(9):
        y = van_y + i * 46
        pygame.draw.line(surface, (34, 38, 38), (cx - 90 - i*12, y), (cx + 90 + i*12, y), 1)
    for side in (-1, 1):
        pygame.draw.line(surface, (45, 50, 48), (cx + side*42, van_y), (cx + side*190, bot_y), 2)
    # Door frame behind player, closing.
    door_w = 230
    door_h = 240
    door_x = cx - door_w // 2
    door_y = SCENE_TOP + 95
    close_p = min(1.0, t / 1450.0)
    pygame.draw.rect(surface, (5, 5, 6), (door_x - 18, door_y - 18, door_w + 36, door_h + 36), border_radius=4)
    left_w = int((door_w // 2) * close_p)
    right_w = left_w
    pygame.draw.rect(surface, (42, 48, 50), (door_x, door_y, left_w, door_h))
    pygame.draw.rect(surface, (42, 48, 50), (door_x + door_w - right_w, door_y, right_w, door_h))
    pygame.draw.rect(surface, (90, 100, 98), (door_x, door_y, door_w, door_h), 2)
    # Narrow light slit as it closes.
    slit_w = max(2, int(door_w * (1.0 - close_p)))
    pygame.draw.rect(surface, (120, 170, 150), (cx - slit_w//2, door_y + 12, slit_w, door_h - 24))
    # Simple first-person weapon silhouette low frame.
    pygame.draw.line(surface, (14, 16, 16), (cx - 100, SCENE_BOT - 40), (cx + 20, SCENE_BOT - 82), 10)
    pygame.draw.line(surface, (55, 66, 62), (cx - 94, SCENE_BOT - 44), (cx + 15, SCENE_BOT - 80), 2)
    label = font_terminal.render(_T("m3ops.service_door_cell_block_sealed"), True, (110, 150, 135))
    surface.blit(label, (cx - label.get_width() // 2, SCENE_BOT - 100))


def _draw_m3_comms_wing_reveal(surface, t):
    """Transition shot: first reveal of the Comms Wing."""
    surface.fill((4, 8, 9))
    # Static comms room panel, no AI-like effects.
    for y in range(SCENE_TOP, SCENE_BOT):
        p = (y - SCENE_TOP) / max(1, SCENE_BOT - SCENE_TOP)
        pygame.draw.line(surface, (int(6 + p*16), int(12 + p*24), int(13 + p*24)), (0, y), (WIDTH, y))
    # Server racks left/right.
    for side in (-1, 1):
        rack_x = WIDTH // 2 + side * 270 - 70
        rack_y = SCENE_TOP + 90
        pygame.draw.rect(surface, (12, 18, 20), (rack_x, rack_y, 140, 330), border_radius=6)
        pygame.draw.rect(surface, (60, 85, 82), (rack_x, rack_y, 140, 330), 2, border_radius=6)
        for yy in range(rack_y + 24, rack_y + 300, 24):
            pygame.draw.line(surface, (32, 48, 48), (rack_x + 10, yy), (rack_x + 130, yy), 1)
            if (yy // 24) % 3 == 0:
                pygame.draw.circle(surface, (80, 220, 130), (rack_x + 118, yy + 8), 2)
    # Main relay console.
    panel = pygame.Rect(WIDTH//2 - 210, SCENE_TOP + 155, 420, 190)
    render_util.soft_shadow(surface, (panel.x - 20, panel.bottom - 5, panel.w + 40, 34), 100)
    pygame.draw.rect(surface, (24, 36, 36), panel, border_radius=7)
    pygame.draw.rect(surface, (82, 120, 112), panel, 2, border_radius=7)
    header = font_terminal.render(_T("m3ops.comms_relay"), True, (135, 220, 190))
    surface.blit(header, (panel.centerx - header.get_width()//2, panel.y + 18))
    # Antenna dish icon and wave display.
    pygame.draw.circle(surface, (12, 18, 18), (panel.centerx, panel.y + 105), 38)
    pygame.draw.arc(surface, (120, 210, 175), (panel.centerx - 52, panel.y + 53, 104, 104), math.pi*0.15, math.pi*0.85, 3)
    pygame.draw.line(surface, (120, 210, 175), (panel.centerx, panel.y + 105), (panel.centerx + 48, panel.y + 84), 3)
    for i in range(4):
        r = 55 + i*22
        pygame.draw.arc(surface, (70, 130, 115), (panel.centerx - r, panel.y + 105 - r, r*2, r*2), -0.6, 0.6, 1)
    # Fluorescent strip above.
    pygame.draw.rect(surface, (44, 54, 52), (WIDTH//2 - 160, SCENE_TOP + 55, 320, 12), border_radius=3)
    pygame.draw.rect(surface, (170, 210, 190), (WIDTH//2 - 150, SCENE_TOP + 58, 300, 6), border_radius=3)
    caption = font_terminal_small.render(_T("m3ops.relay_access_required"), True, (110, 150, 135))
    surface.blit(caption, (WIDTH//2 - caption.get_width()//2, panel.bottom + 22))


def _draw_m3_volkov_gives_mags(surface, t):
    """First-person close-up: Biribel's own cupped hands wait at the bottom
    of frame while Volkov's arm reaches in from the top-right and tosses two
    spare magazines down into them - one per hand, well separated.

    Pacing fix: the spoken line now plays FIRST (shot 1) over Biribel's empty
    waiting hands. Only for shot 2 does Volkov's arm sweep in from off-screen,
    arc the two mags home AFTER the line is done, and retract once they're
    caught - so the handoff no longer races the dialogue. The catch is a clean
    finger-curl + soft amber rim instead of a stray tick.
    """
    surface.fill((4, 5, 6))
    cx = WIDTH // 2
    floor_y = SCENE_BOT - 30

    # Dim close-up backdrop with a soft vignette.
    for y in range(SCENE_TOP, SCENE_BOT):
        p = (y - SCENE_TOP) / max(1, SCENE_BOT - SCENE_TOP)
        pygame.draw.line(surface, (int(8 + p * 12), int(11 + p * 16), int(12 + p * 14)), (0, y), (WIDTH, y))
    pygame.draw.polygon(surface, (13, 16, 17), [(0, floor_y), (WIDTH, floor_y), (WIDTH, SCENE_BOT), (0, SCENE_BOT)])
    vig = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
    for i in range(60):
        a = max(0, 70 - i)
        pygame.draw.rect(vig, (0, 0, 0, a), (i, i, WIDTH - 2 * i, HEIGHT - 2 * i), 1)
    surface.blit(vig, (0, 0))

    skin = (176, 132, 100)
    sleeve = (58, 68, 52)

    # Helper for a tapered forearm.
    def forearm(shoulder, wrist, col, hi=None, w0=28, w1=12):
        sx, sy = shoulder
        wx, wy = wrist
        dx, dy = wx - sx, wy - sy
        dist = max(1.0, math.hypot(dx, dy))
        px, py = -dy / dist, dx / dist
        poly = [
            (sx + px * w0, sy + py * w0),
            (sx - px * w0, sy - py * w0),
            (wx - px * w1, wy - py * w1),
            (wx + px * w1, wy + py * w1),
        ]
        pygame.draw.polygon(surface, col, poly)
        pygame.draw.polygon(surface, (8, 9, 9), poly, 1)
        if hi:
            pygame.draw.line(surface, hi, (sx + px * w0 * 0.35, sy + py * w0 * 0.35),
                             (wx + px * w1 * 0.25, wy + py * w1 * 0.25), 1)

    # ── Timing (ms, cumulative since cutscene start) ──
    SHOT1_END = 2400          # the spoken line plays over shot 1
    ARM_IN = 320              # arm sweep-in duration
    ARM_OUT = 300             # arm retract duration
    ARM_RETRACT_AT = 4000     # once both mags are caught, pull back
    arm_in = max(0.0, min(1.0, (t - SHOT1_END) / ARM_IN))
    arm_out = max(0.0, min(1.0, (t - ARM_RETRACT_AT) / ARM_OUT))
    arm_vis = arm_in * (1.0 - arm_out)   # 0 -> 1 (swept in) -> 0 (retracted)

    # Biribel's two cupped hands, clearly separated at the bottom. They rise
    # into frame during the first beat and simply wait empty through shot 1.
    hand_lx, hand_ly = cx - 110, floor_y - 34
    hand_rx, hand_ry = cx + 110, floor_y - 34
    q = max(0.0, min(1.0, t / 420.0))
    q = q * q * (3 - 2 * q)
    for hx, hy in ((hand_lx, hand_ly), (hand_rx, hand_ry)):
        forearm((hx, HEIGHT + 40), (hx, hy + 14), sleeve, (94, 108, 80), 30, 13)
        pygame.draw.ellipse(surface, (60, 70, 54), (hx - 30, hy - 4, 60, 40))
        pygame.draw.ellipse(surface, skin, (hx - 23, hy - 9, 46, 30))
        pygame.draw.ellipse(surface, (150, 110, 82), (hx - 23, hy - 9, 46, 30), 2)

    # Volkov's arm exists ONLY during shot 2: it sweeps in from off-screen
    # top-right to the release point, opens to drop the mags, then retracts.
    toss_x, toss_y = WIDTH - 150, SCENE_TOP + 78
    if arm_vis > 0.001:
        ax = _lerp_cutscene(WIDTH + 90, toss_x, arm_vis)
        ay = _lerp_cutscene(SCENE_TOP - 70, toss_y, arm_vis)
        forearm((WIDTH + 120, SCENE_TOP - 90), (ax, ay), sleeve, (94, 108, 80), 28, 12)
        released = arm_in >= 1.0 and arm_out <= 0.0
        from core.hands import open_hand_dorsal
        open_hand_dorsal(surface, (ax, ay - 6), angle=180.0, mirror=1, sc=0.85,
                         spread=1.3 if released else 0.7,
                         pal={"skin": skin, "hi": (226, 186, 148),
                              "mid": (170, 126, 94), "sh": (150, 110, 82)})

    # Larger magazine sprite.
    MAG_W, MAG_H = 26, 54

    def draw_mag(x, y, angle):
        s = pygame.Surface((MAG_W, MAG_H), pygame.SRCALPHA)
        pygame.draw.rect(s, (26, 28, 33), (0, 0, MAG_W, MAG_H), border_radius=4)
        # curved grip base (amber)
        pygame.draw.rect(s, (208, 162, 92), (3, MAG_H - 14, MAG_W - 6, 11), border_radius=3)
        # ribbed body lines
        for ry in range(8, MAG_H - 16, 9):
            pygame.draw.line(s, (120, 122, 132), (4, ry), (MAG_W - 4, ry), 1)
        # top lip
        pygame.draw.rect(s, (150, 150, 160), (3, 3, MAG_W - 6, 5), border_radius=2)
        s = pygame.transform.rotate(s, angle)
        surface.blit(s, (int(x) - s.get_width() // 2, int(y) - s.get_height() // 2))

    # Each mag arcs from Volkov's hand into its OWN hand, delayed so they
    # never overlap in flight or on landing. Both launches happen AFTER the
    # line is finished (t >= SHOT1_END), so the handoff reads clean.
    def mag_traj(tx, ty, delay, dur=880):
        p = min(1.0, max(0.0, (t - delay) / dur))
        if p <= 0.0:
            return None
        flight = min(1.0, p / 0.72)
        ease = 1.0 - (1.0 - flight) * (1.0 - flight)
        arc = math.sin(flight * math.pi) * 70
        x = toss_x + (tx - toss_x) * ease
        y = toss_y + (ty - toss_y) * ease - arc
        caught = p >= 0.9
        return x, y, caught

    mags = [
        (hand_lx, hand_ly - 6, 2760, -16),   # left hand, slight tilt
        (hand_rx, hand_ry - 6, 3080, 16),    # right hand, delayed, opposite tilt
    ]
    for tx, ty, delay, tilt in mags:
        res = mag_traj(tx, ty, delay)
        if res is None:
            continue
        x, y, caught = res
        # Faint motion ghost trailing behind the mag in flight.
        if not caught:
            gp = min(1.0, max(0.0, (t - delay - 90) / 880.0))
            if gp > 0:
                gf = min(1.0, gp / 0.72)
                ge = 1.0 - (1.0 - gf) * (1.0 - gf)
                gx = toss_x + (tx - toss_x) * ge
                gy = toss_y + (ty - toss_y) * ge - math.sin(gf * math.pi) * 70
                ghost = pygame.Surface((MAG_W, MAG_H), pygame.SRCALPHA)
                pygame.draw.rect(ghost, (60, 60, 70, 80), (0, 0, MAG_W, MAG_H), border_radius=4)
                ghost = pygame.transform.rotate(ghost, tilt)
                surface.blit(ghost, (int(gx) - ghost.get_width() // 2, int(gy) - ghost.get_height() // 2))
        draw_mag(x, y, tilt)
        if caught:
            # Clean catch: Biribel's fingers curl over the mag top + soft amber rim.
            top_y = y - MAG_H / 2
            from core.hands import grip_hand
            grip_hand(surface, (x, top_y + 8), axis=0, mirror=-1, sc=0.8,
                      curl=1.0, yank=0.4, grip_d=20,
                      pal={"skin": skin, "hi": (226, 186, 148),
                           "mid": (170, 126, 94), "sh": (150, 110, 82)})
            rim = pygame.Surface((MAG_W + 8, MAG_H + 8), pygame.SRCALPHA)
            pygame.draw.rect(rim, (208, 162, 92, 90), (3, 3, MAG_W + 2, MAG_H + 2), border_radius=6)
            rim = pygame.transform.rotate(rim, tilt)
            surface.blit(rim, (int(x) - rim.get_width() // 2, int(y) - rim.get_height() // 2))


def _m3_archives_corridor_base(surface, t, advance=0.0):
    """Shared moving access corridor for the Comms → Archives sequence."""
    surface.fill((4, 6, 7))
    cx = WIDTH // 2
    top, bot = SCENE_TOP, SCENE_BOT
    horizon = top + 175
    pulse = 0.5 + 0.5 * math.sin(t * 0.008)

    # Deep doorway and converging architecture establish one continuous axis.
    pygame.draw.rect(surface, (8, 11, 13), (0, top, WIDTH, bot - top))
    pygame.draw.polygon(surface, (18, 23, 25),
                        [(0, top), (cx - 155, horizon), (cx - 230, bot), (0, bot)])
    pygame.draw.polygon(surface, (15, 20, 22),
                        [(WIDTH, top), (cx + 155, horizon), (cx + 230, bot), (WIDTH, bot)])
    pygame.draw.polygon(surface, (23, 27, 29),
                        [(cx - 230, bot), (cx - 155, horizon),
                         (cx + 155, horizon), (cx + 230, bot)])

    # Moving floor ribs sell forward motion without a disconnected camera cut.
    offset = int((advance * 220 + t * 0.06) % 74)
    for i in range(-1, 8):
        y = horizon + i * 74 + offset
        if horizon <= y <= bot:
            half = int(155 + (y - horizon) * 0.22)
            pygame.draw.line(surface, (45, 55, 57), (cx - half, y), (cx + half, y), 2)
    for x0 in (-310, -210, 210, 310):
        pygame.draw.line(surface, (38, 47, 49),
                         (cx + int(x0 * 0.50), horizon), (cx + x0, bot), 2)

    # Ceiling strips and an intermittent alarm wash.
    for depth in range(4):
        yy = top + 34 + depth * 55
        half = 240 - depth * 38
        pygame.draw.line(surface, (80, 105, 103),
                         (cx - half, yy), (cx + half, yy), 4)
        glow = pygame.Surface((half * 2 + 30, 22), pygame.SRCALPHA)
        pygame.draw.ellipse(glow, (115, 190, 170, 16 + int(12 * pulse)), glow.get_rect())
        surface.blit(glow, (cx - half - 15, yy - 8), special_flags=pygame.BLEND_ADD)

    return cx, horizon, bot


def _m3_draw_k9_low_ready(surface, x, y, sway=0.0):
    """Compact first-person K-9 silhouette; kept low so staging remains readable."""
    x, y = int(x), int(y + sway)
    sleeve = (48, 58, 53)
    skin = (165, 122, 91)
    pygame.draw.line(surface, sleeve, (x - 145, HEIGHT + 20), (x - 68, y + 42), 24)
    pygame.draw.line(surface, sleeve, (x + 150, HEIGHT + 20), (x + 66, y + 32), 22)
    pygame.draw.circle(surface, skin, (x - 65, y + 31), 13)
    pygame.draw.circle(surface, skin, (x + 61, y + 24), 12)
    # Receiver, magazine, and short suppressor.
    pygame.draw.rect(surface, (18, 23, 24), (x - 82, y - 13, 142, 34), border_radius=6)
    pygame.draw.rect(surface, (82, 103, 98), (x - 82, y - 13, 142, 34), 2, border_radius=6)
    pygame.draw.rect(surface, (31, 39, 39), (x + 54, y - 5, 68, 18), border_radius=8)
    pygame.draw.circle(surface, (3, 5, 5), (x + 122, y + 4), 6)
    pygame.draw.polygon(surface, (15, 19, 20),
                        [(x - 18, y + 18), (x + 7, y + 18),
                         (x + 2, y + 86), (x - 19, y + 86)])
    pygame.draw.polygon(surface, (77, 91, 86),
                        [(x - 18, y + 18), (x + 7, y + 18),
                         (x + 2, y + 86), (x - 19, y + 86)], 2)


def _draw_m3_archives_relay_confirm(surface, t):
    """The tuned KRAP relay authenticates the Archives access gate."""
    surface.fill((3, 7, 7))
    cx = WIDTH // 2
    # Relay console carried over visually from the preceding objective.
    console = pygame.Rect(cx - 300, SCENE_TOP + 65, 600, 330)
    pygame.draw.rect(surface, (7, 15, 15), console, border_radius=8)
    pygame.draw.rect(surface, (56, 108, 98), console, 2, border_radius=8)
    screen_r = pygame.Rect(console.x + 42, console.y + 42, console.w - 84, 190)
    pygame.draw.rect(surface, (2, 12, 10), screen_r, border_radius=4)
    pygame.draw.rect(surface, (50, 135, 112), screen_r, 1, border_radius=4)

    lines = [
        "KRAP RELAY // HANDSHAKE ACCEPTED",
        "ROUTE: COMMS-03 > ARCHIVES GATE",
        "CREDENTIAL: IPA-MAINT / GHOST AUTH",
        "MAGLOCK CONTROL ........ RELEASED",
    ]
    reveal = max(0, int(t // 210))
    for i, text in enumerate(lines[:reveal]):
        col = (105, 225, 175) if i == len(lines) - 1 else (80, 155, 132)
        s = font_terminal.render(text, True, col)
        surface.blit(s, (screen_r.x + 24, screen_r.y + 22 + i * 38))

    # A physical status strip changes from regime red to relay green.
    unlocked = t >= 760
    strip = pygame.Rect(console.x + 110, console.bottom - 68, console.w - 220, 20)
    pygame.draw.rect(surface, (42, 18, 18) if not unlocked else (14, 64, 42), strip, border_radius=4)
    fill = min(strip.w, int(strip.w * max(0.0, min(1.0, (t - 300) / 650.0))))
    if fill:
        pygame.draw.rect(surface, (80, 210, 145), (strip.x, strip.y, fill, strip.h), border_radius=4)
    status = font_terminal_small.render(
        "ARCHIVES MAGLOCK RELEASED" if unlocked else "INJECTING GATE CREDENTIAL...",
        True, (135, 235, 180) if unlocked else (180, 150, 105))
    surface.blit(status, (cx - status.get_width() // 2, SCENE_BOT - 72))


def _draw_m3_archives_corridor_push(surface, t):
    """First-person push through the newly opened access corridor."""
    p = max(0.0, min(1.0, t / 1500.0))
    cx, horizon, bot = _m3_archives_corridor_base(surface, t, p)

    # Opening blast door at the far end; panels separate as Biribel advances.
    open_p = p * p * (3.0 - 2.0 * p)
    gap = int(12 + open_p * 150)
    door_y = horizon - 58
    pygame.draw.rect(surface, (32, 41, 43), (cx - 158, door_y, 158 - gap, 250))
    pygame.draw.rect(surface, (32, 41, 43), (cx + gap, door_y, 158 - gap, 250))
    pygame.draw.line(surface, (95, 145, 132), (cx - gap, door_y), (cx - gap, door_y + 250), 3)
    pygame.draw.line(surface, (95, 145, 132), (cx + gap, door_y), (cx + gap, door_y + 250), 3)

    # Figures moving beyond the door foreshadow combat rather than an empty room.
    if p > 0.55:
        alpha = int(210 * (p - 0.55) / 0.45)
        silhouettes = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        for sx, face_r in ((cx - 86, True), (cx + 112, False)):
            # Cast-sheet IPA guards (figure_kit), flattened to silhouettes.
            _fk_draw(silhouettes, "ipa", sx, horizon + 92, 0.27, facing_right=face_r,
                     silhouette=True, moving=1, t=t + sx * 7)
        silhouettes.fill((255, 255, 255, alpha), special_flags=pygame.BLEND_RGBA_MULT)
        surface.blit(silhouettes, (0, 0))

    bob = math.sin(t * 0.018) * 4 * (0.3 + p)
    _m3_draw_k9_low_ready(surface, cx, bot - 92, bob)
    tag = font_terminal_small.render(_T("m3ops.archives_access_corridor"), True, (92, 130, 124))
    surface.blit(tag, (cx - tag.get_width() // 2, SCENE_TOP + 18))


def _draw_m3_archives_volkov_join(surface, t):
    """Volkov catches Biribel at the threshold without breaking screen direction."""
    cx, horizon, bot = _m3_archives_corridor_base(surface, t, 1.0)
    floor_y = bot - 30

    # Open threshold and cold Archives light beyond.
    pygame.draw.rect(surface, (55, 76, 79), (cx - 150, horizon - 55, 300, 230))
    spill = pygame.Surface((500, 290), pygame.SRCALPHA)
    pygame.draw.polygon(spill, (125, 190, 185, 38), [(190, 0), (310, 0), (500, 290), (0, 290)])
    surface.blit(spill, (cx - 250, horizon - 30), special_flags=pygame.BLEND_ADD)

    # Volkov enters from the player's left and turns in the same travel direction.
    enter = max(0.0, min(1.0, t / 850.0))
    ease = enter * enter * (3.0 - 2.0 * enter)
    vx = int(-100 + (cx - 190 + 100) * ease)
    draw_volkov(surface, vx, floor_y, scale=0.67, facing_right=True,
                act_t=t / 1000.0)

    # Biribel remains present in first person, preserving continuity.
    _m3_draw_k9_low_ready(surface, cx + 110, bot - 95, math.sin(t * 0.012) * 2)
    if t > 900:
        arrow = font_terminal_small.render(_T("m3ops.volkov_linked_up"), True, (205, 165, 92))
        surface.blit(arrow, (vx - arrow.get_width() // 2, floor_y - 220))


def _draw_m3_archives_hostile_reveal(surface, t):
    """A threatening Archives reveal that resolves directly into gameplay."""
    surface.fill((6, 8, 10))
    cx = WIDTH // 2
    floor_y = SCENE_BOT - 35
    push = max(0.0, min(1.0, t / 1700.0))

    # Atrium perspective: central clerk route, stacks on both sides, vault deep right.
    for y in range(SCENE_TOP, SCENE_BOT):
        p = (y - SCENE_TOP) / max(1, SCENE_BOT - SCENE_TOP)
        pygame.draw.line(surface, (int(9 + p * 22), int(12 + p * 24), int(15 + p * 26)),
                         (0, y), (WIDTH, y))
    horizon = SCENE_TOP + 155
    for side in (-1, 1):
        near_x = cx + side * 310
        far_x = cx + side * 135
        pygame.draw.polygon(surface, (16, 21, 26),
                            [(far_x - side * 65, horizon - 45), (near_x - side * 150, SCENE_TOP + 20),
                             (near_x - side * 150, floor_y), (far_x - side * 65, horizon + 170)])
        for k in range(5):
            yy = horizon - 15 + k * 48
            pygame.draw.line(surface, (57, 72, 83),
                             (far_x - side * 65, yy), (near_x - side * 150, yy + k * 4), 2)

    # Maru's destination and Vostral vault are visible but spatially distinct.
    pygame.draw.rect(surface, (22, 29, 34), (cx - 78, horizon - 18, 156, 132), border_radius=3)
    pygame.draw.rect(surface, (93, 122, 137), (cx - 78, horizon - 18, 156, 132), 2, border_radius=3)
    vault = font_terminal_small.render(_T("m3ops.cold_vault"), True, (130, 165, 180))
    surface.blit(vault, (cx - vault.get_width() // 2, horizon + 34))
    maru = font_terminal_small.render(_T("m3ops.nw_clerk_office_dead_drop"), True, (176, 135, 215))
    surface.blit(maru, (54, SCENE_TOP + 46))

    # Three guards snap into alert poses; red sight lines sweep toward camera.
    guards = [(cx - 245, floor_y - 95), (cx + 215, floor_y - 110), (cx + 30, horizon + 76)]
    for i, (gx, gy) in enumerate(guards):
        wake = max(0.0, min(1.0, (t - 300 - i * 170) / 420.0))
        # Cast-sheet IPA guard (figure_kit); hands come up as they wake.
        g_scale = 0.29
        g_foot = gy + 10
        _fk_draw(surface, "ipa", gx, g_foot, g_scale, facing_right=gx < cx, t=t + i * 300,
                 fear=0.2 * wake,
                 reach=None if wake <= 0 else ((-10, -34 - 8 * wake), (12, -36 - 8 * wake)))
        if wake > 0:
            aim_x = gx + (cx - gx) * wake
            aim_y = gy - 28 + (floor_y - 120 - (gy - 28)) * wake
            pygame.draw.line(surface, (150, 35, 34), (gx, gy - 30), (int(aim_x), int(aim_y)), 1)
            pygame.draw.circle(surface, (220, 55, 48), (int(aim_x), int(aim_y)), 2)

    # Volkov covers left while Biribel raises the K-9. End composition matches gameplay.
    draw_volkov(surface, cx - 285, floor_y, scale=0.62, facing_right=True,
                act_t=t / 1000.0)
    raise_y = floor_y - 66 - int(34 * push)
    _m3_draw_k9_low_ready(surface, cx + 105, raise_y, 0)

    plate = font_terminal.render(_T("m3ops.archives_wing_contact"), True, (205, 95, 82))
    surface.blit(plate, (cx - plate.get_width() // 2, SCENE_TOP + 18))


def _draw_m3_archives_door_unlock(surface, t):
    """Close-up: the archive access door's magnetic lock disengages."""
    surface.fill((5, 7, 8))
    cx = WIDTH // 2
    # Door slab.
    door_w, door_h = 260, 320
    door_x = cx - door_w // 2
    door_y = SCENE_TOP + 60
    pygame.draw.rect(surface, (14, 18, 20), (door_x, door_y, door_w, door_h), border_radius=4)
    pygame.draw.rect(surface, (50, 70, 68), (door_x, door_y, door_w, door_h), 2, border_radius=4)
    # Lock bar slides up.
    bar_y = door_y + int((1.0 - min(1.0, t / 900.0)) * door_h)
    pygame.draw.rect(surface, (80, 100, 96), (door_x - 6, bar_y, door_w + 12, 14), border_radius=3)
    # Green status LED.
    lit = min(1.0, t / 600.0)
    led_col = (int(40 * (1.0 - lit)), int(200 * lit), int(140 * lit))
    pygame.draw.circle(surface, led_col, (door_x + door_w - 20, door_y + 20), 6)
    # Light bleed as it opens.
    if lit > 0.0:
        bleed = pygame.Surface((door_w + 40, 60), pygame.SRCALPHA)
        pygame.draw.rect(bleed, (120, 220, 180, int(60 * lit)), (0, 0, door_w + 40, 60), border_radius=4)
        surface.blit(bleed, (door_x - 20, door_y + door_h - 30))
    # Label.
    label = font_terminal.render(_T("m3ops.archive_access_unlocked"), True, (100, 220, 170))
    surface.blit(label, (cx - label.get_width() // 2, SCENE_BOT - 90))


def _draw_m3_archives_atrium_reveal(surface, t):
    """Wide shot: stepping from the Comms Wing into the Archives atrium."""
    surface.fill((8, 10, 12))
    cx = WIDTH // 2
    # Perspective floor.
    for y in range(SCENE_TOP, SCENE_BOT):
        p = (y - SCENE_TOP) / max(1, SCENE_BOT - SCENE_TOP)
        pygame.draw.line(surface, (int(10 + p*18), int(12 + p*20), int(14 + p*22)), (0, y), (WIDTH, y))
    # Left/right archive stacks.
    for side in (-1, 1):
        rack_x = WIDTH // 2 + side * 280 - 80
        rack_y = SCENE_TOP + 70
        pygame.draw.rect(surface, (14, 18, 22), (rack_x, rack_y, 160, 340), border_radius=6)
        pygame.draw.rect(surface, (70, 90, 110), (rack_x, rack_y, 160, 340), 2, border_radius=6)
        for yy in range(rack_y + 28, rack_y + 300, 28):
            pygame.draw.line(surface, (36, 48, 56), (rack_x + 12, yy), (rack_x + 148, yy), 1)
            if (yy // 28) % 4 == 0:
                pygame.draw.line(surface, (90, 110, 130), (rack_x + 12, yy), (rack_x + 148, yy), 1)
    # Overhead fluorescents.
    for fx in (cx - 180, cx + 180):
        pygame.draw.line(surface, (28, 34, 36), (fx - 50, SCENE_TOP + 40), (fx + 50, SCENE_TOP + 40), 4)
        glow = pygame.Surface((120, 40), pygame.SRCALPHA)
        pygame.draw.ellipse(glow, (180, 210, 220, 35), (0, 0, 120, 40))
        surface.blit(glow, (fx - 60, SCENE_TOP + 36), special_flags=pygame.BLEND_ADD)
    # Distant vault door at far end.
    vault_x = cx - 60
    vault_y = SCENE_TOP + 140
    pygame.draw.rect(surface, (18, 22, 26), (vault_x, vault_y, 120, 160), border_radius=3)
    pygame.draw.rect(surface, (120, 150, 180), (vault_x, vault_y, 120, 160), 2, border_radius=3)
    pygame.draw.line(surface, (160, 190, 220), (vault_x + 20, vault_y + 40), (vault_x + 100, vault_y + 40), 2)
    pygame.draw.line(surface, (160, 190, 220), (vault_x + 20, vault_y + 80), (vault_x + 100, vault_y + 80), 2)
    pygame.draw.line(surface, (160, 190, 220), (vault_x + 20, vault_y + 120), (vault_x + 100, vault_y + 120), 2)
    label = font_terminal.render(_T("m3ops.archives_wing_atrium"), True, (140, 180, 200))
    surface.blit(label, (cx - label.get_width() // 2, SCENE_BOT - 80))


def _draw_vent_shaft(surface, t):
    """Ventilation shaft - dark corrugated metal tunnel, dust motes, forward crawl."""
    surface.fill((6, 6, 8))
    cx, cy = WIDTH // 2, HEIGHT // 2

    # Corrugated tunnel walls - perspective lines converging to center.
    for i in range(20):
        y_off = i * 28
        shrink = 0.3 + 0.7 * (i / 20)
        lw = int(WIDTH * shrink)
        left = cx - lw // 2
        right = cx + lw // 2
        top = cy - 120 + y_off
        col = (18 + i, 18 + i, 20 + i)
        # Top corrugation.
        pygame.draw.line(surface, col, (left, top), (right, top), 2)
        # Side ribs.
        if i % 3 == 0:
            rib_col = (28, 28, 30)
            pygame.draw.line(surface, rib_col, (left, top), (left, top + 26), 1)
            pygame.draw.line(surface, rib_col, (right, top), (right, top + 26), 1)

    # Dust motes drifting forward.
    rng = random.Random(int(t * 0.01))
    for _ in range(12):
        mx = rng.randint(100, WIDTH - 100)
        my = rng.randint(80, HEIGHT - 80)
        ms = 1 + rng.random() * 1.5
        pygame.draw.circle(surface, (60, 58, 52), (int(mx), int(my)), int(ms))

    # Faint light ahead - the exit glow at the tunnel end.
    glow_r = 60 + int(8 * math.sin(t * 0.03))
    glow = pygame.Surface((glow_r * 2, glow_r * 2), pygame.SRCALPHA)
    for r in range(glow_r, 0, -4):
        a = max(0, int(18 * (1 - r / glow_r)))
        pygame.draw.circle(glow, (80, 90, 70, a), (glow_r, glow_r), r)
    surface.blit(glow, (cx - glow_r, cy - glow_r - 60), special_flags=pygame.BLEND_ADD)

    # Forward motion blur streaks.
    for _ in range(6):
        sx = rng.randint(120, WIDTH - 120)
        sy = rng.randint(100, HEIGHT - 100)
        slen = rng.randint(20, 50)
        pygame.draw.line(surface, (30, 30, 34), (sx, sy), (sx, sy + slen), 1)


def _draw_vent_exit(surface, t):
    """Looking out from the vent grate into the Stabilization Center kitchen."""
    import math
    import random

    # 1. Background / Back Wall (institutional pale green/gray tiles)
    wall_col = (45, 52, 48)
    wall_dark = (30, 35, 32)
    surface.fill(wall_col)

    # Tile grid on the back wall
    tile_size = 40
    for tx in range(0, WIDTH, tile_size):
        pygame.draw.line(surface, wall_dark, (tx, 0), (tx, HEIGHT), 1)
    for ty in range(0, HEIGHT, tile_size):
        pygame.draw.line(surface, wall_dark, (0, ty), (WIDTH, ty), 1)

    # 2. Stainless steel shelving on the back wall
    shelf_y = int(HEIGHT * 0.35)
    shelf_col = (85, 90, 95)
    shelf_hi = (130, 135, 140)
    shelf_dark = (50, 55, 60)
    pygame.draw.rect(surface, shelf_col, (80, shelf_y, WIDTH - 160, 12))
    pygame.draw.line(surface, shelf_hi, (80, shelf_y), (WIDTH - 80, shelf_y), 2)
    pygame.draw.line(surface, shelf_dark, (80, shelf_y + 12), (WIDTH - 80, shelf_y + 12), 2)

    # Pots and institutional trays on the shelf
    rng = random.Random(99)
    for px in range(100, WIDTH - 100, 70):
        if rng.random() > 0.3:
            pw = rng.randint(30, 50)
            ph = rng.randint(20, 35)
            pygame.draw.rect(surface, (65, 70, 75), (px, shelf_y - ph, pw, ph), border_radius=2)
            pygame.draw.rect(surface, shelf_hi, (px, shelf_y - ph, pw, ph), 1, border_radius=2)
            pygame.draw.rect(surface, (40, 45, 50), (px + pw//2 - 10, shelf_y - ph - 4, 20, 4), border_radius=1)

    # 3. Hanging rack with pots (center)
    rack_y = int(HEIGHT * 0.15)
    pygame.draw.line(surface, (40, 45, 50), (250, rack_y), (WIDTH - 250, rack_y), 4)
    for hx in range(280, WIDTH - 280, 90):
        pygame.draw.line(surface, (60, 65, 70), (hx, rack_y), (hx, rack_y + 40), 2)
        pygame.draw.ellipse(surface, (55, 60, 65), (hx - 25, rack_y + 40, 50, 35))
        pygame.draw.ellipse(surface, shelf_hi, (hx - 25, rack_y + 40, 50, 35), 1)
        pygame.draw.line(surface, (40, 45, 50), (hx + 25, rack_y + 50), (hx + 45, rack_y + 45), 3)

    # 4. Industrial stove / prep table (lower half)
    table_y = int(HEIGHT * 0.65)
    table_w = 500
    table_x = WIDTH // 2 - table_w // 2
    pygame.draw.rect(surface, shelf_col, (table_x, table_y, table_w, 20), border_radius=2)
    pygame.draw.line(surface, shelf_hi, (table_x, table_y), (table_x + table_w, table_y), 2)
    pygame.draw.rect(surface, (70, 75, 80), (table_x, table_y + 20, table_w, 150))
    pygame.draw.line(surface, shelf_dark, (table_x, table_y + 170), (table_x + table_w, table_y + 170), 2)
    
    # Oven doors
    for ox in range(table_x + 20, table_x + table_w - 20, 120):
        pygame.draw.rect(surface, (55, 60, 65), (ox, table_y + 40, 100, 110), border_radius=4)
        pygame.draw.rect(surface, shelf_dark, (ox, table_y + 40, 100, 110), 2, border_radius=4)
        pygame.draw.rect(surface, shelf_hi, (ox + 10, table_y + 50, 80, 6), border_radius=2)
        pygame.draw.rect(surface, (15, 18, 20), (ox + 20, table_y + 70, 60, 40), border_radius=2)
        pygame.draw.rect(surface, (30, 35, 40), (ox + 20, table_y + 70, 60, 40), 1, border_radius=2)

    # 5. Overhead fluorescent light (flickering)
    light_cx = WIDTH // 2
    light_cy = int(HEIGHT * 0.05)
    flicker = 0.85 + 0.15 * math.sin(t * 0.2)
    light_col = (int(230 * flicker), int(240 * flicker), int(220 * flicker))
    pygame.draw.rect(surface, (60, 65, 70), (light_cx - 100, light_cy, 200, 16), border_radius=2)
    pygame.draw.rect(surface, light_col, (light_cx - 95, light_cy + 4, 190, 8), border_radius=2)
    
    # Light cone (additive blend)
    cone = pygame.Surface((400, 500), pygame.SRCALPHA)
    pygame.draw.polygon(cone, (*light_col, 25), [
        (200 - 95, 0), (200 + 95, 0),
        (350, 500), (50, 500)
    ])
    surface.blit(cone, (light_cx - 200, light_cy + 16), special_flags=pygame.BLEND_RGBA_ADD)

    # 6. The vent grate frame (foreground, framing the whole view)
    frame_col = (12, 14, 16)
    frame_hi = (35, 38, 42)
    frame_w = 50

    # Thick borders
    pygame.draw.rect(surface, frame_col, (0, 0, WIDTH, frame_w))
    pygame.draw.rect(surface, frame_col, (0, HEIGHT - frame_w, WIDTH, frame_w))
    pygame.draw.rect(surface, frame_col, (0, 0, frame_w, HEIGHT))
    pygame.draw.rect(surface, frame_col, (WIDTH - frame_w, 0, frame_w, HEIGHT))

    # Inner bevels
    pygame.draw.line(surface, frame_hi, (frame_w, frame_w), (WIDTH - frame_w, frame_w), 2)
    pygame.draw.line(surface, frame_hi, (frame_w, HEIGHT - frame_w), (WIDTH - frame_w, HEIGHT - frame_w), 2)
    pygame.draw.line(surface, frame_hi, (frame_w, frame_w), (frame_w, HEIGHT - frame_w), 2)
    pygame.draw.line(surface, frame_hi, (WIDTH - frame_w, frame_w), (WIDTH - frame_w, HEIGHT - frame_w), 2)

    # Grate slats (horizontal and vertical bars crossing the view)
    slat_col = (18, 20, 22)
    slat_hi = (40, 45, 50)

    # Horizontal slats
    for sy in range(frame_w, HEIGHT - frame_w, 70):
        pygame.draw.rect(surface, slat_col, (frame_w, sy, WIDTH - frame_w * 2, 10))
        pygame.draw.line(surface, slat_hi, (frame_w, sy), (WIDTH - frame_w, sy), 1)
        pygame.draw.line(surface, (5, 6, 8), (frame_w, sy + 10), (WIDTH - frame_w, sy + 10), 1)

    # Vertical slats
    for sx in range(frame_w, WIDTH - frame_w, 90):
        pygame.draw.rect(surface, slat_col, (sx, frame_w, 10, HEIGHT - frame_w * 2))
        pygame.draw.line(surface, slat_hi, (sx, frame_w), (sx, HEIGHT - frame_w), 1)
        pygame.draw.line(surface, (5, 6, 8), (sx + 10, frame_w), (sx + 10, HEIGHT - frame_w), 1)

    # Screws in the corners of the frame
    screw_col = (50, 55, 60)
    for cx, cy in [(25, 25), (WIDTH - 25, 25), (25, HEIGHT - 25), (WIDTH - 25, HEIGHT - 25)]:
        pygame.draw.circle(surface, screw_col, (cx, cy), 8)
        pygame.draw.circle(surface, (20, 22, 25), (cx, cy), 8, 1)
        pygame.draw.line(surface, (15, 16, 18), (cx - 4, cy), (cx + 4, cy), 2)
        pygame.draw.line(surface, (15, 16, 18), (cx, cy - 4), (cx, cy + 4), 2)

    # Dust motes / kitchen steam floating in the light cone
    rng2 = random.Random(int(t * 0.5))
    for _ in range(15):
        mx = rng2.randint(light_cx - 150, light_cx + 150)
        my = rng2.randint(light_cy + 50, HEIGHT - 100)
        mr = rng2.randint(1, 3)
        alpha = rng2.randint(40, 100)
        dust = pygame.Surface((mr*4, mr*4), pygame.SRCALPHA)
        pygame.draw.circle(dust, (220, 230, 210, alpha), (mr*2, mr*2), mr)
        surface.blit(dust, (mx, my), special_flags=pygame.BLEND_RGBA_ADD)


# RPE6 Phase 2 (A-003 take registry): the cutscene scene ids this module owns.
# cutscenes.engine.draw_cutscene_scene finds them through core.cutscene_registry
# instead of importing this module by name (boundary rule 4 / W1).
from core.cutscene_registry import register_scene_renderers as _register_takes  # noqa: E402
from engine.text import T as _T  # RPE6 Phase 4 text table

_register_takes({
    "k9_wall_stand": _draw_k9_wall_stand,
    "k9_firstperson_grab": _draw_k9_firstperson_grab,
    "k9_ready_check": _draw_k9_ready_check,
    "m3_service_door_transition": _draw_m3_service_door_transition,
    "m3_volkov_radio_call": _draw_m3_volkov_radio_call,
    "m3_radio_recovered": _draw_m3_radio_recovered,
    "m3_comms_wing_reveal": _draw_m3_comms_wing_reveal,
    "m3_volkov_gives_mags": _draw_m3_volkov_gives_mags,
    "m3_archives_relay_confirm": _draw_m3_archives_relay_confirm,
    "m3_archives_corridor_push": _draw_m3_archives_corridor_push,
    "m3_archives_volkov_join": _draw_m3_archives_volkov_join,
    "m3_archives_hostile_reveal": _draw_m3_archives_hostile_reveal,
    "m3_archives_door_unlock": _draw_m3_archives_door_unlock,
    "m3_archives_atrium_reveal": _draw_m3_archives_atrium_reveal,
    "vent_shaft": _draw_vent_shaft,
    "vent_exit": _draw_vent_exit,
})
