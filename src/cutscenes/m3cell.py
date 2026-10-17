"""Split from cutscenes.py - see cutscenes.py (shim) for the map."""
# cutscenes package
# ------------------------------------------------------------

"""Cutscene visuals and dialogue: character drawings, scene backgrounds, shot lists."""
import math
import random
import pygame

from core import render_util
from core.hands import open_hand_dorsal
from core.config import (C_VOLKOV, HEIGHT, SCENE_BOT, SCENE_TOP, WIDTH, draw_letterbox, draw_scanlines, draw_vignette, font_speaker, font_terminal, font_terminal_small)

from cutscenes.cast import draw_volkov
from cutscenes.figure_kit import draw_character as _fk_draw, HEIGHT as _FK_HEIGHT, _REF_H as _FK_REF_H



# ─────────────────────────────────────
# Mission 3 - Stabilization Center scene renderers
# ─────────────────────────────────────
# Four procedural scenes for the M3 intro cutscene. Purely visual - no
# new art assets needed. All reuse the existing character renderers
# (draw_biribel, draw_volkov), the light-cone helper, and gradient tools.


def _m3_clamp01(v):
    return max(0.0, min(1.0, float(v)))


def _m3_smooth(v):
    v = _m3_clamp01(v)
    return v * v * (3.0 - 2.0 * v)


def _m3_noise(surface, seed, count=80, alpha=26, region=None):
    """Deterministic dust/grime pass.

    The old M3 intro used live random jitter in a few shots, which made the
    image shimmer like a generated placeholder. These specks are seeded, so the
    scene feels filmed rather than regenerated every frame.
    """
    rng = random.Random(seed)
    if region is None:
        x0, y0, w, h = 0, SCENE_TOP, WIDTH, SCENE_BOT - SCENE_TOP
    else:
        x0, y0, w, h = region
    for _ in range(count):
        x = x0 + rng.randint(0, max(1, w - 1))
        y = y0 + rng.randint(0, max(1, h - 1))
        r = rng.randint(1, 2)
        v = rng.randint(20, 50)
        pygame.draw.circle(surface, (v, v, v + 3, alpha), (x, y), r)


def _m3_soft_light(surface, center, radius, color, alpha, elliptical=0.65, blend=True):
    """Disabled visible wash overlays for the M3 intro.

    The scene art already has enough contrast from the monitor/tube sprites.
    Big red/blue glow washes made the compositions unreadable, so this helper
    intentionally avoids drawing any large visible shape. Kept as a no-op seam
    so the scene code can stay simple and future lighting can be reintroduced
    in a more controlled way.
    """
    return


def _m3_draw_fluorescent(surface, x, y, w, t, glow_alpha=52):
    """Institutional fluorescent tube.

    No large bloom overlays: keep the shot readable by limiting glow to a
    tight halo immediately around the fixture.
    """
    flicker = 0.86 + 0.10 * math.sin(t * 0.011) + 0.04 * math.sin(t * 0.037)
    flicker = max(0.55, min(1.0, flicker))

    # Tight fixture halo only. This gives the tube intensity without throwing
    # a giant blue rectangle across the scene.
    tight = pygame.Surface((w + 84, 62), pygame.SRCALPHA)
    for i in range(7):
        a = int(glow_alpha * flicker * (1.0 - i / 7.0) * 0.16)
        if a <= 0:
            continue
        rect = pygame.Rect(42 - i * 4, 26 - i * 2, w + i * 8, 9 + i * 4)
        pygame.draw.rect(tight, (185, 205, 215, a), rect, border_radius=7)
    # Normal alpha blit - additive blending ignores alpha on some pygame
    # backends and made this read as another bright overlay block.
    surface.blit(tight, (x - 42, y - 26))

    pygame.draw.rect(surface, (18, 18, 18), (x - 8, y - 8, w + 16, 22), border_radius=3)
    pygame.draw.rect(surface, (65, 70, 72), (x - 4, y - 5, w + 8, 16), 1, border_radius=3)
    tube_col = (int(180 * flicker), int(195 * flicker), int(202 * flicker))
    pygame.draw.rect(surface, tube_col, (x, y, w, 9), border_radius=5)
    pygame.draw.line(surface, (245, 250, 240), (x + 8, y + 2), (x + w - 8, y + 2), 2)
    for cap_x in (x - 12, x + w + 2):
        pygame.draw.rect(surface, (44, 44, 42), (cap_x, y - 2, 12, 13), border_radius=2)


def _m3_draw_seated_biribel(surface, cx, seat_y, scale=1.0, rim=(130, 150, 155)):
    """Restrained Biribel for the M3 intro wide shot.

    The first pass looked like a normal seated silhouette. This version makes
    the restraint read immediately even behind the dialogue panel: tall chair
    back, chest harness, bolted arm rails, oversized cuffs, and taut chains.
    """
    s = scale
    ix = lambda v: int(round(v))

    # Ground shadow / bolted chair footprint.
    render_util.soft_shadow(surface, (ix(cx - 98*s), ix(seat_y + 38*s), ix(196*s), ix(34*s)), 110)

    frame = (29, 30, 30)
    frame_dark = (10, 10, 11)
    frame_hi = (78, 80, 76)
    strap = (72, 78, 78)
    strap_dark = (22, 24, 24)
    cuff_col = (118, 120, 112)
    cuff_hi = (185, 188, 176)

    # Tall interrogation-chair back. Draw it before the body so it reads as a
    # device, not a normal office chair.
    back = pygame.Rect(ix(cx - 62*s), ix(seat_y - 142*s), ix(124*s), ix(176*s))
    pygame.draw.rect(surface, (0, 0, 0, 95), back.move(ix(8*s), ix(9*s)), border_radius=ix(10*s))
    pygame.draw.rect(surface, frame_dark, back, border_radius=ix(10*s))
    pygame.draw.rect(surface, frame_hi, back, 2, border_radius=ix(10*s))
    # Padded vertical slats / welded seams.
    for off in (-34, 0, 34):
        pygame.draw.line(surface, (38, 40, 40), (ix(cx + off*s), back.y + ix(14*s)), (ix(cx + off*s), back.bottom - ix(12*s)), max(1, ix(2*s)))
    # Head brace behind the skull.
    brace = pygame.Rect(ix(cx - 46*s), ix(seat_y - 132*s), ix(92*s), ix(34*s))
    pygame.draw.rect(surface, (20, 21, 21), brace, border_radius=ix(7*s))
    pygame.draw.rect(surface, (84, 86, 82), brace, 1, border_radius=ix(7*s))

    # Seat and bolted arm rails.
    seat = pygame.Rect(ix(cx - 66*s), ix(seat_y + 12*s), ix(132*s), ix(33*s))
    pygame.draw.rect(surface, frame, seat, border_radius=ix(6*s))
    pygame.draw.rect(surface, frame_hi, seat, 1, border_radius=ix(6*s))

    rail_y = seat_y - 4*s
    for side in (-1, 1):
        rail = pygame.Rect(ix(cx + side*42*s), ix(rail_y - 10*s), ix(side*126*s), ix(22*s))
        if rail.w < 0:
            rail.x += rail.w
            rail.w = -rail.w
        pygame.draw.rect(surface, (0, 0, 0, 80), rail.move(ix(4*s), ix(5*s)), border_radius=ix(5*s))
        pygame.draw.rect(surface, frame, rail, border_radius=ix(5*s))
        pygame.draw.rect(surface, frame_hi, rail, 1, border_radius=ix(5*s))
        # Anchor plate at the far end.
        plate = pygame.Rect(0, 0, ix(30*s), ix(28*s))
        plate.center = (ix(cx + side*162*s), ix(rail_y))
        pygame.draw.rect(surface, (24, 24, 23), plate, border_radius=ix(4*s))
        pygame.draw.rect(surface, (93, 90, 82), plate, 1, border_radius=ix(4*s))
        pygame.draw.circle(surface, (120, 116, 104), (plate.centerx, plate.centery), max(2, ix(3*s)))

    # Biribel himself comes from the cast sheet (figure_kit): seated, wrists
    # hauled out to the rails, head bowed.  Only the restraint rig below is
    # bespoke to this shot.
    k = 0.75 * s                                   # screen px per arrest unit
    fig_scale = k * _FK_REF_H / _FK_HEIGHT["biribel"]
    foot_y = seat_y + 12*s + 49*k                  # seated hips land on the seat
    wrists = [(cx + side * 136*s, rail_y - 1*s) for side in (-1, 1)]
    _fk_draw(surface, "biribel", cx, foot_y, fig_scale, facing_right=True,
             seated=True, bow=1.0, fear=0.35,
             reach=tuple((wx - cx, wy - foot_y) for wx, wy in wrists))
    # Cold rim from the door slit on his screen-right edge.
    pygame.draw.line(surface, rim, (ix(cx + 36*s), ix(seat_y - 62*s)), (ix(cx + 40*s), ix(seat_y + 12*s)), max(1, ix(2*s)))

    # Chest harness: two diagonals + a horizontal belt. This is the main cue
    # that he is strapped down, and it sits above the dialogue box.
    pygame.draw.line(surface, strap, (ix(cx - 36*s), ix(seat_y - 58*s)), (ix(cx + 34*s), ix(seat_y + 9*s)), max(3, ix(7*s)))
    pygame.draw.line(surface, strap_dark, (ix(cx - 36*s), ix(seat_y - 58*s)), (ix(cx + 34*s), ix(seat_y + 9*s)), max(1, ix(2*s)))
    pygame.draw.line(surface, strap, (ix(cx + 36*s), ix(seat_y - 58*s)), (ix(cx - 34*s), ix(seat_y + 9*s)), max(3, ix(7*s)))
    pygame.draw.line(surface, strap_dark, (ix(cx + 36*s), ix(seat_y - 58*s)), (ix(cx - 34*s), ix(seat_y + 9*s)), max(1, ix(2*s)))
    belt = pygame.Rect(ix(cx - 46*s), ix(seat_y - 24*s), ix(92*s), ix(15*s))
    pygame.draw.rect(surface, strap, belt, border_radius=ix(3*s))
    pygame.draw.rect(surface, strap_dark, belt, 1, border_radius=ix(3*s))
    buckle = pygame.Rect(0, 0, ix(20*s), ix(15*s))
    buckle.center = belt.center
    pygame.draw.rect(surface, cuff_hi, buckle, 1, border_radius=ix(2*s))

    # Wrists are pinned to the rails, palms down: cuffs + taut chains.
    for side, wrist in zip((-1, 1), wrists):
        wrist = (ix(wrist[0]), ix(wrist[1]))
        # Large rectangular wrist cuff, bright enough to read in the dark.
        cuff = pygame.Rect(0, 0, ix(42*s), ix(17*s))
        cuff.center = wrist
        pygame.draw.rect(surface, (0, 0, 0, 90), cuff.move(ix(2*s), ix(3*s)), border_radius=ix(4*s))
        pygame.draw.rect(surface, cuff_col, cuff, border_radius=ix(4*s))
        pygame.draw.rect(surface, cuff_hi, cuff, 2, border_radius=ix(4*s))
        pygame.draw.line(surface, (48, 48, 45), (cuff.x + ix(6*s), cuff.centery), (cuff.right - ix(6*s), cuff.centery), max(1, ix(2*s)))

        # Taut chain from cuff to anchor plate.
        anchor = (ix(cx + side * 164*s), ix(rail_y))
        for j in range(4):
            q = (j + 0.5) / 4
            lx = wrist[0] + (anchor[0] - wrist[0]) * q
            ly = wrist[1] + (anchor[1] - wrist[1]) * q
            link = pygame.Rect(ix(lx - 5*s), ix(ly - 4*s), ix(10*s), ix(8*s))
            pygame.draw.ellipse(surface, (45, 45, 44), link, max(1, ix(2*s)))
            pygame.draw.ellipse(surface, (132, 128, 116), link, 1)

    # Foot shackles on the cast figure's shoes.
    for side in (-1, 1):
        ankle = pygame.Rect(0, 0, ix(31*s), ix(11*s))
        ankle.center = (ix(cx + side * 21*k), ix(foot_y - 8*k))
        pygame.draw.rect(surface, cuff_col, ankle, border_radius=ix(3*s))
        pygame.draw.rect(surface, cuff_hi, ankle, 1, border_radius=ix(3*s))



def _m3_draw_balaceanu(surface, cx, foot_y, scale=1.0, facing_left=True):
    """Balaceanu, drawn by figure_kit so he matches the arrest scene exactly
    (same face/suit as m4aftermath's general), holding the VOSTRAL folder."""
    _fk_draw(surface, "balaceanu", cx, foot_y, scale, facing_right=not facing_left,
             prop="folder", prop_label="VOSTRAL", label_font=font_terminal_small)


def _draw_cell_ceiling(surface, t):
    """Biribel's POV waking up: a real cell ceiling, not an abstract glow."""
    surface.fill((3, 4, 5))
    sec = t / 1000.0
    focus = _m3_smooth(t / 2200.0)

    # Eye opening is intentionally slow and uncomfortable; the previous 60 ms
    # blink made the shot read like a placeholder flash.
    eye_open = 0.10 + 0.90 * _m3_smooth((t - 180) / 1500.0)
    if 760 < t < 1040:
        eye_open *= 0.68  # one involuntary blink
    eye_open = _m3_clamp01(eye_open)

    sway_x = int(math.sin(sec * 0.9) * (5 - 3 * focus))
    sway_y = int(math.sin(sec * 0.63 + 1.7) * (4 - 2 * focus))

    # Concrete ceiling slab with perspective seams.
    top = SCENE_TOP - 20 + sway_y
    bot = SCENE_BOT + 40 + sway_y
    for y in range(top, bot):
        p = (y - top) / max(1, bot - top)
        shade = int(10 + p * 24)
        pygame.draw.line(surface, (shade, shade + 1, shade + 4), (0, y), (WIDTH, y))

    van_x = WIDTH // 2 + sway_x
    for i, x in enumerate((-420, -250, -95, 55, 220, 390)):
        pygame.draw.line(surface, (18, 19, 22), (van_x + x, SCENE_TOP - 20), (van_x + int(x * 1.35), SCENE_BOT + 60), 1)
    for y in (SCENE_TOP + 55, SCENE_TOP + 145, SCENE_TOP + 248, SCENE_TOP + 365, SCENE_TOP + 500):
        pygame.draw.line(surface, (17, 18, 21), (0, y + sway_y), (WIDTH, y + sway_y + int((y - SCENE_TOP) * 0.02)), 1)

    # Old water stains and cracks. Deterministic: no AI-jitter shimmer.
    stain = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
    rng = random.Random(3091)
    for _ in range(16):
        x = rng.randint(80, WIDTH - 80) + sway_x // 2
        y = rng.randint(SCENE_TOP + 30, SCENE_BOT - 90) + sway_y // 2
        w = rng.randint(45, 140)
        h = rng.randint(10, 38)
        pygame.draw.ellipse(stain, (5, 7, 8, rng.randint(25, 54)), (x - w // 2, y - h // 2, w, h))
    cracks = [
        [(WIDTH//2 - 230, SCENE_TOP + 110), (WIDTH//2 - 170, SCENE_TOP + 147), (WIDTH//2 - 130, SCENE_TOP + 210), (WIDTH//2 - 78, SCENE_TOP + 234)],
        [(WIDTH//2 + 130, SCENE_TOP + 330), (WIDTH//2 + 190, SCENE_TOP + 372), (WIDTH//2 + 216, SCENE_TOP + 444)],
        [(WIDTH//2 + 265, SCENE_TOP + 120), (WIDTH//2 + 245, SCENE_TOP + 180), (WIDTH//2 + 275, SCENE_TOP + 235)],
    ]
    crack_a = int(40 + 80 * focus)
    for pts in cracks:
        pts = [(x + sway_x // 2, y + sway_y // 2) for x, y in pts]
        pygame.draw.lines(stain, (4, 5, 6, crack_a), False, pts, 2)
        for x, y in pts[1:-1]:
            pygame.draw.line(stain, (4, 5, 6, crack_a // 2), (x, y), (x + rng.randint(-28, 28), y + rng.randint(14, 38)), 1)
    surface.blit(stain, (0, 0))

    # Security camera / sprinkler: small institutional details sell the room.
    pygame.draw.circle(surface, (19, 21, 23), (WIDTH - 168 + sway_x//3, SCENE_TOP + 92 + sway_y//3), 26)
    pygame.draw.circle(surface, (8, 9, 10), (WIDTH - 168 + sway_x//3, SCENE_TOP + 92 + sway_y//3), 14)
    if int(t // 680) % 2 == 0:
        pygame.draw.circle(surface, (170, 22, 18), (WIDTH - 158 + sway_x//3, SCENE_TOP + 82 + sway_y//3), 3)

    _m3_draw_fluorescent(surface, WIDTH // 2 - 155 + sway_x, SCENE_TOP + 190 + sway_y, 310, t, glow_alpha=64)

    # Unfocused double-image fades out instead of per-frame random blur.
    if focus < 0.75:
        ghost = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        _m3_draw_fluorescent(ghost, WIDTH // 2 - 154 + sway_x + 10, SCENE_TOP + 190 + sway_y - 6, 310, t + 90, glow_alpha=25)
        ghost.set_alpha(int(90 * (1.0 - focus)))
        surface.blit(ghost, (0, 0))

    # Eyelid mask: hard black with a soft inner edge.
    bar_h = int((HEIGHT * 0.50) * (1.0 - eye_open))
    if bar_h > 0:
        pygame.draw.rect(surface, (0, 0, 0), (0, 0, WIDTH, bar_h))
        pygame.draw.rect(surface, (0, 0, 0), (0, HEIGHT - bar_h, WIDTH, bar_h))
        soft = pygame.Surface((WIDTH, 34), pygame.SRCALPHA)
        for i in range(34):
            a = int(150 * (1 - i / 34))
            pygame.draw.line(soft, (0, 0, 0, a), (0, i), (WIDTH, i))
        surface.blit(soft, (0, bar_h - 2))
        surface.blit(pygame.transform.flip(soft, False, True), (0, HEIGHT - bar_h - 32))


def _draw_cell_restraints(surface, t):
    """Close-up of the restraint chair: clinical, physical, and quiet.

    The old version reused chair-break language (sparks, CRITICAL overlays), so
    the intro looked like the later action cutscene. This shot should feel like
    waking up strapped to state property, not already breaking out.
    """
    surface.fill((5, 6, 7))
    sec = t / 1000.0
    settle = _m3_smooth(t / 1400.0)

    # Cold concrete and floor-to-wall split.
    wall_h = SCENE_TOP + 320
    for y in range(SCENE_TOP, SCENE_BOT):
        p = (y - SCENE_TOP) / max(1, SCENE_BOT - SCENE_TOP)
        col = (int(9 + p * 12), int(10 + p * 12), int(12 + p * 14))
        pygame.draw.line(surface, col, (0, y), (WIDTH, y))
    pygame.draw.line(surface, (28, 30, 31), (0, wall_h), (WIDTH, wall_h), 2)
    for x in range(-40, WIDTH + 80, 92):
        pygame.draw.line(surface, (16, 17, 19), (x, SCENE_TOP), (x + 58, wall_h), 1)
    _m3_noise(surface, 5531, 130, alpha=20)

    # No broad red/blue light overlays here. The cuffs, hands, chair arms and
    # background must stay readable; the monitor glow is handled by the actual
    # monitor prop in the following room shot.

    cx = WIDTH // 2
    cy = SCENE_TOP + 382
    trem = math.sin(sec * 8.4) * (1.0 + 1.2 * settle)

    # Metal chair arms / instrument table-like composition.
    for side in (-1, 1):
        rail_x = cx + side * 172
        rail = pygame.Rect(0, 0, 310, 54)
        rail.center = (rail_x, cy + 18)
        pygame.draw.rect(surface, (0, 0, 0, 85), rail.move(7, 9), border_radius=10)
        pygame.draw.rect(surface, (31, 31, 30), rail, border_radius=10)
        pygame.draw.rect(surface, (75, 72, 66), rail, 2, border_radius=10)
        pygame.draw.line(surface, (95, 92, 84), (rail.x + 12, rail.y + 8), (rail.right - 12, rail.y + 8), 1)
        for bx in (rail.x + 36, rail.right - 36):
            pygame.draw.circle(surface, (88, 84, 75), (bx, rail.centery), 7)
            pygame.draw.circle(surface, (18, 17, 16), (bx, rail.centery), 3)
        # Serial stencil.
        st = font_terminal_small.render(_T("m3cell.ipa_sc_restraint_chair_03"), True, (72, 78, 76))
        if side == -1:
            surface.blit(st, (rail.x + 18, rail.y + 34))

    skin = (188, 148, 116)
    skin_dark = (105, 73, 55)
    skin_hi = (226, 194, 158)

    for side in (-1, 1):
        wrist_x = cx + side * 152 + trem * side
        wrist_y = cy - 8 + math.sin(sec * 6.1 + side) * 0.8
        elbow_x = cx + side * 275
        elbow_y = HEIGHT + 78
        # Forearm emerges from the bottom edge.
        arm_pts = [
            (int(elbow_x - side * 42), elbow_y),
            (int(elbow_x + side * 24), elbow_y),
            (int(wrist_x + side * 26), int(wrist_y + 35)),
            (int(wrist_x - side * 31), int(wrist_y + 35)),
        ]
        pygame.draw.polygon(surface, skin_dark, arm_pts)
        inner = [
            (int(elbow_x - side * 29), elbow_y),
            (int(elbow_x + side * 17), elbow_y),
            (int(wrist_x + side * 16), int(wrist_y + 31)),
            (int(wrist_x - side * 20), int(wrist_y + 31)),
        ]
        pygame.draw.polygon(surface, skin, inner)
        pygame.draw.line(surface, skin_hi, (int(wrist_x - side * 12), int(wrist_y + 42)), (int(elbow_x - side * 18), int(elbow_y - 70)), 2)
        # Red cuff marks under the steel.
        chafe = pygame.Surface((84, 30), pygame.SRCALPHA)
        pygame.draw.ellipse(chafe, (142, 28, 24, 112), chafe.get_rect())
        surface.blit(chafe, (int(wrist_x - 42), int(wrist_y + 11)))
        # Reference-model hand (dorsal, spread fingers, long thumb) at mitt
        # scale; mirrored per hand so each is the correct one.
        hand_y = wrist_y - 24
        open_hand_dorsal(surface, (wrist_x, hand_y + 43), angle=0.0,
                         mirror=-side, sc=0.5, spread=0.85, trem=0,
                         pal={"skin": skin, "hi": skin_hi, "mid": (150, 112, 84),
                              "sh": skin_dark, "nail": (205, 165, 132),
                              "nail_edge": (130, 92, 66),
                              "nail_tip": (240, 210, 175)})

        # Cuff and short chain to chair rail.
        cuff = pygame.Rect(0, 0, 104, 35)
        cuff.center = (int(wrist_x), int(wrist_y + 30))
        pygame.draw.rect(surface, (19, 20, 22), cuff, border_radius=8)
        pygame.draw.rect(surface, (104, 101, 93), cuff, 3, border_radius=8)
        pygame.draw.line(surface, (151, 142, 120), (cuff.x + 12, cuff.y + 8), (cuff.right - 12, cuff.y + 8), 1)
        anchor = (int(wrist_x + side * 86), int(wrist_y + 30))
        for j in range(5):
            q = (j + 0.5) / 5
            lx = wrist_x + side * 48 + (anchor[0] - (wrist_x + side * 48)) * q
            ly = wrist_y + 30 + (anchor[1] - (wrist_y + 30)) * q
            link = pygame.Rect(int(lx - 7), int(ly - 5), 14, 10)
            pygame.draw.ellipse(surface, (45, 45, 45), link, 3)
            pygame.draw.ellipse(surface, (112, 108, 96), link, 1)
        pygame.draw.circle(surface, (78, 74, 66), anchor, 13)
        pygame.draw.circle(surface, (20, 18, 16), anchor, 5)

    _m3_draw_fluorescent(surface, WIDTH // 2 - 96, SCENE_TOP + 42, 192, t, glow_alpha=28)
    _m3_soft_light(surface, (cx, cy - 110), 360, (170, 190, 200), 18)


def _draw_interrogation_room(surface, t):
    """Wide interrogation composition: room, chair, Balaceanu, monitor."""
    surface.fill((3, 3, 4))
    sec = t / 1000.0
    push = _m3_smooth(t / 3600.0)
    cam_x = int(-18 * push)
    cam_y = int(6 * math.sin(sec * 0.55))

    # Back wall and floor, muted institutional colors.
    horizon = SCENE_TOP + 330 + cam_y
    for y in range(SCENE_TOP, SCENE_BOT):
        if y < horizon:
            p = (y - SCENE_TOP) / max(1, horizon - SCENE_TOP)
            col = (int(9 + p * 18), int(10 + p * 18), int(12 + p * 17))
        else:
            p = (y - horizon) / max(1, SCENE_BOT - horizon)
            col = (int(18 + p * 20), int(18 + p * 20), int(19 + p * 19))
        pygame.draw.line(surface, col, (0, y), (WIDTH, y))
    pygame.draw.line(surface, (36, 38, 39), (0, horizon), (WIDTH, horizon), 2)
    # Tile perspective.
    for x in range(-120, WIDTH + 120, 92):
        pygame.draw.line(surface, (24, 25, 26), (WIDTH // 2, horizon), (x + cam_x, SCENE_BOT), 1)
    for i in range(9):
        yy = horizon + int((i / 9.0) ** 1.7 * (SCENE_BOT - horizon))
        pygame.draw.line(surface, (25, 26, 27), (0, yy), (WIDTH, yy), 1)

    # Observation window / black mirror.
    win = pygame.Rect(WIDTH // 2 - 410 + cam_x, SCENE_TOP + 92 + cam_y, 310, 128)
    pygame.draw.rect(surface, (5, 7, 9), win, border_radius=3)
    pygame.draw.rect(surface, (54, 60, 62), win, 2, border_radius=3)
    pygame.draw.line(surface, (80, 86, 88), (win.x + 20, win.y + 12), (win.right - 28, win.y + 12), 1)
    if int(t // 700) % 2 == 0:
        pygame.draw.circle(surface, (130, 20, 18), (win.right - 24, win.y + 22), 4)
    obs = font_terminal_small.render(_T("m3cell.observation_rec"), True, (88, 92, 92))
    surface.blit(obs, (win.x + 18, win.y + win.h - 25))

    # Broadcast monitor on the back wall.
    mon = pygame.Rect(WIDTH // 2 + 100 + cam_x, SCENE_TOP + 64 + cam_y, 270, 160)
    _m3_soft_light(surface, mon.center, 230, (110, 18, 16), 42)
    pygame.draw.rect(surface, (12, 5, 5), mon.inflate(18, 18), border_radius=5)
    pygame.draw.rect(surface, (100, 18, 16), mon, border_radius=4)
    pygame.draw.rect(surface, (230, 78, 48), mon, 2, border_radius=4)
    # Monitor image: podium silhouette and countdown, not just an abstract blob.
    pygame.draw.rect(surface, (28, 7, 7), (mon.x + 16, mon.y + 18, mon.w - 32, mon.h - 36))
    pygame.draw.circle(surface, (18, 2, 2), (mon.centerx, mon.y + 64), 32)
    pygame.draw.rect(surface, (18, 2, 2), (mon.centerx - 58, mon.y + 94, 116, 42), border_radius=4)
    txt = font_terminal_small.render(_T("m3cell.state_address_22_00"), True, (245, 180, 120))
    surface.blit(txt, (mon.centerx - txt.get_width() // 2, mon.y + 12))
    for sy in range(mon.y + 22, mon.bottom - 12, 5):
        pygame.draw.line(surface, (55, 8, 8), (mon.x + 10, sy), (mon.right - 10, sy), 1)

    # Hanging light pools the table and chair, leaving corners dead.
    _m3_draw_fluorescent(surface, WIDTH // 2 - 132 + cam_x, SCENE_TOP + 28 + cam_y, 264, t, glow_alpha=50)
    _m3_soft_light(surface, (WIDTH // 2 - 40 + cam_x, SCENE_TOP + 365 + cam_y), 420, (160, 178, 180), 28)

    # Table between them.
    # Keep the interrogation blocking above the bottom dialogue box.
    # The caption panel starts around the lower third, so all story-critical
    # props/characters live in the upper safe area.
    table_y = SCENE_TOP + 300 + cam_y
    render_util.soft_shadow(surface, (WIDTH // 2 - 250 + cam_x, table_y + 22, 500, 42), 92)
    pygame.draw.rect(surface, (30, 29, 27), (WIDTH // 2 - 220 + cam_x, table_y - 12, 440, 54), border_radius=8)
    pygame.draw.line(surface, (76, 70, 60), (WIDTH // 2 - 204 + cam_x, table_y - 6), (WIDTH // 2 + 204 + cam_x, table_y - 6), 2)
    # Folder as visual hook for Vostral.
    folder = pygame.Rect(WIDTH // 2 + 46 + cam_x, table_y - 42, 122, 74)
    pygame.draw.rect(surface, (72, 54, 34), folder, border_radius=4)
    pygame.draw.rect(surface, (150, 45, 36), folder, 2, border_radius=4)
    tag = font_terminal.render(_T("m3cell.vostral"), True, (220, 174, 104))
    surface.blit(tag, (folder.centerx - tag.get_width() // 2, folder.y + 20))
    stamp = font_terminal_small.render(_T("m3cell.sealed"), True, (170, 45, 40))
    surface.blit(stamp, (folder.centerx - stamp.get_width() // 2, folder.y + 48))

    # Biribel restrained left; Balaceanu right, standing too composed.
    _m3_draw_seated_biribel(surface, WIDTH // 2 - 270 + cam_x, SCENE_TOP + 342 + cam_y, scale=0.88, rim=(118, 142, 148))
    _m3_draw_balaceanu(surface, WIDTH // 2 + 310 + cam_x, SCENE_TOP + 456 + cam_y, scale=0.72, facing_left=True)

    # Foreground darkness as if camera is peeking from the corner/through glass.
    fg = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
    pygame.draw.rect(fg, (0, 0, 0, 90), (0, SCENE_TOP, 82, SCENE_BOT - SCENE_TOP))
    pygame.draw.rect(fg, (0, 0, 0, 70), (WIDTH - 64, SCENE_TOP, 64, SCENE_BOT - SCENE_TOP))
    pygame.draw.line(fg, (120, 120, 120, 26), (86, SCENE_TOP), (86, SCENE_BOT), 2)
    surface.blit(fg, (0, 0))
    _m3_noise(surface, 9910, 70, alpha=12)


def _draw_monitor_broadcast(surface, t):
    """CRT close-up of the state broadcast setup.

    Still displays the plot information, but as a broadcast image with a face,
    podium, lower-third and countdown instead of a flat generated text card.
    """
    surface.fill((5, 1, 1))
    sec = t / 1000.0

    # CRT body.
    # Place the CRT in the visual safe area above the dialogue box.
    # The bottom caption covers roughly y=506+, so the whole monitor sits above it.
    bezel = pygame.Rect(130, SCENE_TOP + 22, WIDTH - 260, 360)
    pygame.draw.rect(surface, (7, 7, 8), bezel.inflate(42, 42), border_radius=28)
    pygame.draw.rect(surface, (28, 22, 21), bezel.inflate(28, 28), border_radius=24)
    pygame.draw.rect(surface, (85, 72, 60), bezel.inflate(28, 28), 2, border_radius=24)
    screen_rect = bezel
    pygame.draw.rect(surface, (20, 5, 5), screen_rect, border_radius=18)

    # Render the TV picture to a separate surface so we can curve/scan it a bit.
    tv = pygame.Surface((screen_rect.w, screen_rect.h), pygame.SRCALPHA)
    tv.fill((28, 6, 6))
    for y in range(tv.get_height()):
        p = y / max(1, tv.get_height())
        pygame.draw.line(tv, (int(36 + p * 25), int(8 + p * 8), int(8 + p * 6)), (0, y), (tv.get_width(), y))
    # Studio background.
    header = pygame.Rect(34, 24, tv.get_width() - 68, 46)
    pygame.draw.rect(tv, (108, 18, 16), header, border_radius=4)
    h = font_terminal.render(_T("m3cell.acaristan_state_address"), True, (255, 224, 190))
    tv.blit(h, (header.centerx - h.get_width() // 2, header.y + 12))
    for x in (70, 132, tv.get_width() - 178, tv.get_width() - 116):
        pygame.draw.rect(tv, (32, 36, 48), (x, 84, 36, tv.get_height() - 132))
        pygame.draw.rect(tv, (132, 30, 26), (x + 20, 90, 8, tv.get_height() - 150))
        pygame.draw.rect(tv, (34, 58, 100), (x + 7, 90, 8, tv.get_height() - 150))
    # Balaceanu at podium - the cast-sheet general, legs hidden by the podium.
    podium_y = tv.get_height() - 70
    bx = tv.get_width() // 2
    _fk_draw(tv, "balaceanu", bx, podium_y - 10, 1.0, facing_right=True,
             t=t, look=0, blink=0.9 if 2400 < (t % 5200) < 2540 else 0)
    pygame.draw.rect(tv, (76, 54, 42), (tv.get_width()//2 - 170, podium_y - 88, 340, 110), border_radius=7)
    pygame.draw.rect(tv, (150, 110, 78), (tv.get_width()//2 - 170, podium_y - 88, 340, 110), 2, border_radius=7)
    seal = pygame.Rect(tv.get_width()//2 - 62, podium_y - 70, 124, 42)
    pygame.draw.rect(tv, (32, 24, 20), seal, border_radius=4)
    s_txt = font_terminal_small.render(_T("m3cell.ipa_state"), True, (230, 205, 155))
    tv.blit(s_txt, (seal.centerx - s_txt.get_width()//2, seal.y + 12))
    for mx in (-22, 22):
        pygame.draw.line(tv, (8, 8, 9), (bx + mx, podium_y - 62), (bx + mx//2, podium_y - 120), 3)
        pygame.draw.circle(tv, (8, 8, 9), (bx + mx//2, podium_y - 122), 7)
    # Lower third / subject.
    lower = pygame.Rect(0, tv.get_height() - 58, tv.get_width(), 46)
    pygame.draw.rect(tv, (112, 12, 12), lower)
    pygame.draw.line(tv, (235, 105, 58), (0, lower.y), (tv.get_width(), lower.y), 2)
    lt = font_terminal.render(_T("m3cell.route_12_perpetrator_biribel_kra"), True, (255, 226, 195))
    tv.blit(lt, (tv.get_width()//2 - lt.get_width()//2, lower.y + 11))
    # Countdown block.
    cd = pygame.Rect(tv.get_width() - 156, 82, 112, 58)
    pygame.draw.rect(tv, (18, 6, 6), cd, border_radius=4)
    pygame.draw.rect(tv, (210, 72, 46), cd, 2, border_radius=4)
    live = font_terminal_small.render(_T("m3cell.live_at"), True, (230, 180, 140))
    clock = font_speaker.render(_T("m3cell.22_00"), True, (255, 220, 170))
    tv.blit(live, (cd.centerx - live.get_width()//2, cd.y + 7))
    tv.blit(clock, (cd.centerx - clock.get_width()//2, cd.y + 25))

    # TV interference: deterministic rows plus occasional horizontal tear.
    for y in range(0, tv.get_height(), 4):
        pygame.draw.line(tv, (0, 0, 0, 55), (0, y), (tv.get_width(), y), 1)
    rng = random.Random(int(t // 110))
    if rng.random() < 0.55:
        tear_y = rng.randint(80, tv.get_height() - 90)
        tear_h = rng.randint(2, 8)
        offset = rng.randint(-18, 18)
        strip = tv.subsurface((0, tear_y, tv.get_width(), tear_h)).copy()
        pygame.draw.rect(tv, (20, 4, 4), (0, tear_y, tv.get_width(), tear_h))
        tv.blit(strip, (offset, tear_y))
    # Slight pulse/roll bar.
    bar_y = int((sec * 58) % max(1, tv.get_height()))
    pygame.draw.rect(tv, (255, 255, 255, 18), (0, bar_y, tv.get_width(), 3))

    # Blit with a small curved-screen inset illusion.
    surface.blit(tv, screen_rect.topleft)
    pygame.draw.rect(surface, (180, 140, 105), screen_rect, 3, border_radius=18)
    _m3_soft_light(surface, screen_rect.center, 430, (145, 30, 22), 32)

    # CRT glass reflection.
    glass = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
    pygame.draw.line(glass, (255, 220, 180, 32), (screen_rect.x + 74, screen_rect.y + 28), (screen_rect.x + 260, screen_rect.y + 12), 4)
    pygame.draw.line(glass, (255, 220, 180, 18), (screen_rect.right - 250, screen_rect.y + 50), (screen_rect.right - 88, screen_rect.y + 32), 3)
    surface.blit(glass, (0, 0), special_flags=pygame.BLEND_RGBA_ADD)

def _draw_volkov_in_cell(surface, t):
    """Volkov entering from the detention corridor.

    Staged in four visual beats:

    Beat 1 (0.0 - 0.8s): Empty corridor shot. Distant footsteps implied
    by camera framing. Player reads "there is a hallway out there."

    Beat 2 (0.8 - 1.6s): Silhouette visible through the door viewport
    before it opens. Keypad light changes red -> green. Lock disengages.

    Beat 3 (1.6 - 2.8s): Door slides open with weight - light floods in
    from corridor. Volkov stands in threshold, backlit, not yet moving.

    Beat 4 (2.8s+): Volkov walks in. Cigarette ember. Name tag fades in.
    """
    sec = t / 1000.0

    surface.fill((2, 2, 4))

    for y in range(SCENE_TOP, SCENE_BOT):
        p = (y - SCENE_TOP) / max(1, SCENE_BOT - SCENE_TOP)
        r = int(6 + p * 8)
        g = int(6 + p * 8)
        b = int(8 + p * 10)
        pygame.draw.line(surface, (r, g, b), (0, y), (WIDTH, y))

    floor_y = SCENE_BOT - 80

    for y in range(floor_y, SCENE_BOT):
        p = (y - floor_y) / max(1, SCENE_BOT - floor_y)
        shade = int(8 + p * 10)
        pygame.draw.line(surface, (shade, shade, shade + 2), (0, y), (WIDTH, y))

    refl = pygame.Surface((WIDTH, SCENE_BOT - floor_y), pygame.SRCALPHA)
    for y in range(SCENE_BOT - floor_y):
        a = max(0, int(30 * (1 - y / (SCENE_BOT - floor_y))))
        pygame.draw.line(refl, (40, 55, 80, a), (0, y), (WIDTH, y))
    surface.blit(refl, (0, floor_y))

    rng_wall = random.Random(77)
    for x in range(0, WIDTH, 88):
        pygame.draw.line(surface, (14, 14, 17), (x, SCENE_TOP + 20), (x, floor_y), 1)
    for y in range(SCENE_TOP + 40, floor_y, 52):
        pygame.draw.line(surface, (13, 13, 16), (0, y), (WIDTH, y), 1)

    for _ in range(6):
        sx = rng_wall.randint(40, WIDTH - 40)
        sy = rng_wall.randint(SCENE_TOP + 20, floor_y - 30)
        sw = rng_wall.randint(3, 10)
        sh = rng_wall.randint(20, 80)
        stain = pygame.Surface((sw, sh), pygame.SRCALPHA)
        for i in range(sh):
            a = max(0, int(18 * (1 - i / sh)))
            pygame.draw.line(stain, (20, 30, 45, a), (0, i), (sw, i))
        surface.blit(stain, (sx, sy))

    flicker = 0.85 + 0.15 * math.sin(sec * 12.3)
    tube_y = SCENE_TOP + 18
    pygame.draw.rect(surface, (22, 22, 20), (WIDTH // 2 - 80, tube_y, 160, 7))
    tube_col = (int(175 * flicker), int(180 * flicker), int(160 * flicker))
    pygame.draw.rect(surface, tube_col, (WIDTH // 2 - 76, tube_y + 1, 152, 5))

    cone = pygame.Surface((360, 240), pygame.SRCALPHA)
    for i in range(18):
        r = max(0, 160 - i * 9)
        a = max(0, int(18 * (1 - i / 18) * flicker))
        pygame.draw.ellipse(cone, (210, 215, 190, a), (180 - r, 120 - r // 2, r * 2, r))
    surface.blit(cone, (WIDTH // 2 - 180, tube_y + 6))

    door_left = WIDTH // 2 + 168
    door_top = SCENE_TOP + 55
    door_w = 164
    door_h = floor_y - door_top + 14

    pygame.draw.rect(surface, (28, 26, 22), (door_left, door_top, door_w, door_h))

    vanish_x = door_left + door_w // 2
    vanish_y = door_top + door_h // 2
    for cx, cy in [(door_left, door_top), (door_left + door_w, door_top),
                   (door_left, door_top + door_h), (door_left + door_w, door_top + door_h)]:
        pygame.draw.line(surface, (38, 36, 30), (cx, cy), (vanish_x, vanish_y), 1)

    pygame.draw.line(surface, (42, 40, 34),
                     (door_left + 8, floor_y - 12),
                     (door_left + door_w - 8, floor_y - 12), 2)

    cor_light_x = door_left + door_w // 2
    cor_light_y = door_top + 18
    cor_glow = pygame.Surface((door_w + 40, door_h + 20), pygame.SRCALPHA)
    for i in range(12):
        r = int((door_w // 2) * (1 - i / 12))
        a = max(0, int(35 * (1 - i / 12)))
        pygame.draw.ellipse(cor_glow, (220, 200, 160, a),
                            (door_w // 2 + 20 - r, i * 8, r * 2, r))
    surface.blit(cor_glow, (door_left - 20, door_top))

    frame_thick = 14
    pygame.draw.rect(surface, (32, 34, 38),
                     (door_left - frame_thick, door_top - frame_thick,
                      door_w + frame_thick * 2, frame_thick))
    pygame.draw.rect(surface, (32, 34, 38),
                     (door_left - frame_thick, door_top - frame_thick,
                      frame_thick, door_h + frame_thick))
    pygame.draw.rect(surface, (32, 34, 38),
                     (door_left + door_w, door_top - frame_thick,
                      frame_thick, door_h + frame_thick))
    pygame.draw.line(surface, (52, 56, 62),
                     (door_left - frame_thick, door_top - frame_thick),
                     (door_left - frame_thick, door_top + door_h), 1)
    pygame.draw.line(surface, (52, 56, 62),
                     (door_left - frame_thick, door_top - frame_thick),
                     (door_left + door_w + frame_thick, door_top - frame_thick), 1)

    kp_x = door_left - frame_thick - 28
    kp_y = door_top + 90
    pygame.draw.rect(surface, (10, 14, 18), (kp_x, kp_y, 22, 52), border_radius=3)
    pygame.draw.rect(surface, (55, 65, 75), (kp_x, kp_y, 22, 52), 1, border_radius=3)
    for ky in range(2):
        for kx in range(3):
            pygame.draw.rect(surface, (22, 30, 38),
                             (kp_x + 3 + kx * 6, kp_y + 6 + ky * 8, 4, 5), border_radius=1)

    access_t = max(0.0, min(1.0, (sec - 0.65) / 0.25))
    if access_t < 1.0:
        blink = (int(sec * 4)) % 2 == 0
        led_col = (220, 50, 40) if blink else (120, 20, 16)
    else:
        led_col = (60, 230, 100)
    pygame.draw.circle(surface, led_col, (kp_x + 11, kp_y + 38), 3)
    glow_r = 8
    glow = pygame.Surface((glow_r * 2, glow_r * 2), pygame.SRCALPHA)
    pygame.draw.circle(glow, (*led_col, 60), (glow_r, glow_r), glow_r)
    surface.blit(glow, (kp_x + 11 - glow_r, kp_y + 38 - glow_r))

    if access_t >= 1.0:
        access_surf = font_terminal_small.render(_T("m3cell.access_granted"), True, (80, 220, 110))
        surface.blit(access_surf, (kp_x - access_surf.get_width() + 22, kp_y - 16))
        id_surf = font_terminal_small.render(_T("m3cell.volkov_auth_delta"), True, (60, 160, 85))
        surface.blit(id_surf, (kp_x - id_surf.get_width() + 22, kp_y - 30))
    else:
        locked_surf = font_terminal_small.render(_T("m3cell.cell_03_secured"), True, (180, 60, 50))
        surface.blit(locked_surf, (kp_x - locked_surf.get_width() + 22, kp_y - 16))

    if 0.4 < sec < 1.6:
        vp_alpha = max(0.0, min(1.0, (sec - 0.4) / 0.35))
        vp_fade = min(1.0, max(0.0, (1.6 - sec) / 0.25)) if sec > 1.35 else 1.0
        vp = pygame.Rect(door_left + 20, door_top + 38, 60, 28)
        pygame.draw.rect(surface, (4, 6, 8), vp)
        pygame.draw.rect(surface, (70, 80, 90), vp, 1)
        for bx in range(vp.x + 8, vp.right - 4, 10):
            pygame.draw.line(surface, (60, 70, 82), (bx, vp.y + 2), (bx, vp.bottom - 2), 1)
        if vp_alpha > 0.2:
            fig_a = int(200 * vp_alpha * vp_fade)
            fig = pygame.Surface((vp.w, vp.h), pygame.SRCALPHA)
            pygame.draw.circle(fig, (0, 0, 0, fig_a), (vp.w // 2, vp.h // 2 - 4), 6)
            render_util.soft_shadow(fig, (4, vp.h // 2, vp.w - 8, vp.h // 2), fig_a)
            surface.blit(fig, (vp.x, vp.y))
        if sec > 0.75 and vp_alpha > 0.5:
            ember_pulse = 0.5 + 0.5 * math.sin(sec * 8)
            ember_a = int(150 * vp_alpha * vp_fade * ember_pulse)
            ember_surf = pygame.Surface((20, 20), pygame.SRCALPHA)
            pygame.draw.circle(ember_surf, (255, 90, 25, ember_a), (10, 10), 6)
            surface.blit(ember_surf, (vp.x + vp.w // 2 + 8, vp.centery - 6))

    open_t = max(0.0, min(1.0, (sec - 1.2) / 0.75))
    open_ease = 1.0 - (1.0 - open_t) ** 3
    door_slide = int(door_w * open_ease)

    if open_t < 1.0:
        panel_rect = pygame.Rect(door_left - door_slide, door_top, door_w, door_h)
        pygame.draw.rect(surface, (52, 62, 74), panel_rect, border_radius=2)
        pygame.draw.rect(surface, (22, 28, 36), panel_rect, 2, border_radius=2)
        for i in range(5):
            rx = panel_rect.x + 16 + i * 28
            if rx < panel_rect.right - 8:
                pygame.draw.line(surface, (28, 35, 45),
                                 (rx, panel_rect.y + 8), (rx, panel_rect.bottom - 8), 3)
                pygame.draw.line(surface, (95, 112, 132),
                                 (rx - 1, panel_rect.y + 8), (rx - 1, panel_rect.bottom - 8), 1)
        handle_y = panel_rect.centery
        pygame.draw.rect(surface, (40, 50, 62),
                         (panel_rect.right - 18, handle_y - 20, 10, 40), border_radius=3)
        pygame.draw.rect(surface, (80, 95, 110),
                         (panel_rect.right - 18, handle_y - 20, 10, 40), 1, border_radius=3)

    if open_t > 0.05:
        spill_w = int((door_w + 200) * open_ease)
        spill_h = door_h + 60
        spill_surf = pygame.Surface((spill_w, spill_h), pygame.SRCALPHA)
        for i in range(spill_h):
            dist_from_door = abs(i - spill_h // 2) / (spill_h // 2)
            a = int(55 * open_ease * (1 - dist_from_door ** 2))
            if a > 0:
                pygame.draw.line(spill_surf, (220, 205, 165, a), (0, i), (spill_w, i))
        surface.blit(spill_surf, (door_left - spill_w + door_w, door_top - 30))

    if 1.2 < sec < 3.5:
        mote_rng = random.Random(int(sec * 20))
        mote_alpha = int(min(1.0, (sec - 1.2) / 0.4) * 120 * open_ease)
        for _ in range(12):
            mx = door_left + mote_rng.randint(-80, 40)
            my = door_top + mote_rng.randint(20, door_h - 20)
            ms = mote_rng.randint(1, 2)
            mote = pygame.Surface((ms * 4, ms * 4), pygame.SRCALPHA)
            pygame.draw.circle(mote, (220, 210, 180, mote_alpha), (ms * 2, ms * 2), ms)
            surface.blit(mote, (mx, my))

    threshold_t = max(0.0, min(1.0, (sec - 1.8) / 0.5))

    # Threshold pose hands off to the walk at 2.6s - only one Volkov on screen.
    if 1.8 < sec <= 2.6 and open_t > 0.6:
        vol_x = door_left + door_w // 2 + 10
        vol_y = floor_y
        halo_a = int(80 * threshold_t * open_ease)
        halo = pygame.Surface((180, 320), pygame.SRCALPHA)
        pygame.draw.ellipse(halo, (235, 215, 165, halo_a), (0, 0, 180, 320))
        surface.blit(halo, (vol_x - 90, vol_y - 300))
        draw_volkov(surface, vol_x, vol_y, scale=0.74 + 0.08 * threshold_t, facing_right=False)

    walk_t = max(0.0, min(1.0, (sec - 2.6) / 1.2))
    walk_ease = 1.0 - (1.0 - walk_t) ** 2

    if sec > 2.6 and open_t > 0.7:
        start_x = door_left + door_w // 2 + 10
        end_x = door_left + door_w // 2 - 55
        vol_x = int(start_x + (end_x - start_x) * walk_ease)
        start_y = floor_y
        end_y = floor_y - 4
        vol_y = int(start_y + (end_y - start_y) * walk_ease)
        halo_a = int(80 * (1.0 - walk_ease * 0.7) * open_ease)
        halo = pygame.Surface((180, 320), pygame.SRCALPHA)
        pygame.draw.ellipse(halo, (235, 215, 165, halo_a), (0, 0, 180, 320))
        surface.blit(halo, (vol_x - 70, vol_y - 300))
        shadow_a = int(70 * walk_ease)
        shadow = pygame.Surface((60, 16), pygame.SRCALPHA)
        render_util.soft_shadow(shadow, shadow.get_rect(), shadow_a)
        surface.blit(shadow, (vol_x - 30, vol_y - 6))
        draw_volkov(surface, vol_x, vol_y, scale=0.82, facing_right=False)

        name_a = int(255 * min(1.0, (sec - 3.0) / 0.6))
        if name_a > 0:
            name_surf = font_terminal.render(_T("m3cell.volkov"), True, C_VOLKOV)
            name_surf.set_alpha(name_a)
            surface.blit(name_surf, (vol_x - name_surf.get_width() // 2, vol_y - 220))
            role_a = int(200 * min(1.0, (sec - 3.3) / 0.5))
            if role_a > 0:
                role_surf = font_terminal_small.render(_T("m3cell.ipa_logistics_s_volkov"), True, (180, 120, 70))
                role_surf.set_alpha(role_a)
                surface.blit(role_surf, (vol_x - role_surf.get_width() // 2, vol_y - 196))

    chair_cx = WIDTH // 2 - 170
    chair_cy = floor_y
    ch_shad = pygame.Surface((80, 18), pygame.SRCALPHA)
    render_util.soft_shadow(ch_shad, ch_shad.get_rect(), 100)
    surface.blit(ch_shad, (chair_cx - 40, chair_cy - 8))
    for cx_off in (-16, 16):
        pygame.draw.line(surface, (25, 25, 28),
                         (chair_cx + cx_off, chair_cy - 6),
                         (chair_cx + cx_off, chair_cy - 72), 3)
    pygame.draw.rect(surface, (22, 22, 26),
                     (chair_cx - 28, chair_cy - 76, 56, 12), border_radius=2)
    pygame.draw.rect(surface, (20, 20, 24),
                     (chair_cx - 26, chair_cy - 132, 52, 58), border_radius=2)
    pygame.draw.rect(surface, (30, 30, 35),
                     (chair_cx - 26, chair_cy - 132, 52, 58), 1, border_radius=2)
    pygame.draw.ellipse(surface, (8, 9, 11), (chair_cx - 20, chair_cy - 126, 40, 56))
    pygame.draw.circle(surface, (10, 11, 13), (chair_cx - 6, chair_cy - 138), 12)
    pygame.draw.rect(surface, (7, 8, 10),
                     (chair_cx - 28, chair_cy - 82, 12, 34), border_radius=2)
    pygame.draw.rect(surface, (7, 8, 10),
                     (chair_cx + 16, chair_cy - 82, 12, 34), border_radius=2)

    draw_vignette(surface, strength=210)
    draw_scanlines(surface)
    draw_letterbox(surface)


# ─────────────────────────────────────────────
# Chair-break cutscene shots (Mission 3 - the post-breach moment).
# ─────────────────────────────────────────────
# A four-shot, wordless, auto-timed cinematic that REPLACES the old
# shake-overlay chair-break. The in-cell state mutations (chair broken,
# player armed, weapon granted, objective update) still fire from
# mission3._update_chair_break_anim at the Crack shot; only the
# presentation changes - the action is now SHOWN rather than implied.
#
# Each shot is a pure pygame.draw function (rect / polygon / ellipse /
# line / circle / arc) plus the shared helpers above. They take the
# PER-SHOT frame counter `t` (resets each shot) and are deterministic in
# `t` so the transition fades stay clean.
#
# Palette: sourced VERBATIM from mission3._draw_cell_details so the
# cutscene's chair/cuffs/splinters are pixel-identical to the in-game
# cell. The interrogation chair is METAL (dark gunmetal), not wood -
# earlier revisions used invented warm-wood tones (120,90,60) which made
# the shots look like a different game. These are the real values:
#   seat_col (42,40,36)  seat_dark (28,26,24)  seat_edge (60,56,50)
#   splinter_col (50,42,34)
#   chain (100,96,88)    chain_dark (60,56,50) cuff (130,124,112)
#   bolt (76,72,64)
CB_METAL       = (42, 40, 36)
CB_METAL_DARK  = (28, 26, 24)
CB_METAL_EDGE  = (60, 56, 50)
CB_SPLINTER    = (50, 42, 34)
CB_SPLINTER_HI = (74, 64, 52)
CB_CHAIN       = (100, 96, 88)
CB_CHAIN_DARK  = (60, 56, 50)
CB_CUFF        = (130, 124, 112)
CB_BOLT        = (76, 72, 64)
CB_SKIN        = (202, 172, 142)
CB_SKIN_SHADE  = (148, 118, 92)
CB_DUST        = (96, 88, 76)
# Cold overhead fluorescent - the ONLY light after the breach (the monitor
# is off, so there is NO red wash). Matches _draw_cell_atmosphere's tube.
CB_TUBE_COL    = (210, 215, 190)
CB_BG          = (8, 9, 11)


# RPE6 Phase 2 (A-003 take registry): the cutscene scene ids this module owns.
# cutscenes.engine.draw_cutscene_scene finds them through core.cutscene_registry
# instead of importing this module by name (boundary rule 4 / W1).
from core.cutscene_registry import register_scene_renderers as _register_takes  # noqa: E402
from engine.text import T as _T  # RPE6 Phase 4 text table

_register_takes({
    "cell_ceiling": _draw_cell_ceiling,
    "cell_restraints": _draw_cell_restraints,
    "interrogation_room": _draw_interrogation_room,
    "monitor_broadcast": _draw_monitor_broadcast,
    "volkov_in_cell": _draw_volkov_in_cell,
})
