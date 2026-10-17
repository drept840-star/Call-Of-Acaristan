"""Mission 3 - Kill Order transition cinematic (Slice 5 cutscene rehaul, v2).

Illustrated cutscene language, same family as the chair-break and Archives
handoff shots: dark vector compositions with motivated lighting, the side-view
cast sprites from cutscenes.cast, dust/bloom from cutscenes.chair, gradients
and light cones from cutscenes.route12. Deliberately NOT a top-down view of
the live tilemap - that experiment read as "gameplay with captions".

v2 ("feel pass") rules, after owner feedback that v1 read static:
  * Shots are INPUT-PACED (they hold until the player advances), so every
    shot must stay ALIVE indefinitely: looping smoke plumes, strobe cycles,
    laser micro-jitter, light shimmer, breathing/beckoning idle - no shot
    may settle into a still tableau.
  * The camera is a camera: slow push-in per shot (crop+smoothscale),
    handheld micro-shake, cut-on-flash between the charge insert and the
    stairwell wide.
  * The cast acts: walk-cycle tilt+step bob while moving, breathing idle
    when held, Volkov keeps beckoning (impatient) at the van.
  * Highlights bloom (additive), one cool film tint for continuity with the
    chair grade. App-level vignette/scanlines/letterbox/caption stay the
    single post pass (house rule).

Shots (one continuous beat, Archives -> Kill Order):
  charge    - insert: breach pack close-up, LED arms faster, breach flash
  stairwell - side-section stair tower, descent through the smoke
  aperture  - lobby low angle, marksman laser searches then paints their cover
  van       - dock reveal, warm tailgate pool, Volkov beckons, dossier in hand

Pure functions of t: no STATE reads or writes.
"""
import math

import pygame

from core.config import (HEIGHT, WIDTH, font_terminal_small)
from cutscenes.cast import draw_biribel, draw_volkov
from cutscenes.figure_kit import draw_character as _fk_draw
from cutscenes.chair import _cb_camera_shake
from entities.art_cache import get_glow
from cutscenes.route12 import (_draw_light_cone, _draw_vertical_gradient,
                               _ease_cutscene, _lerp_cutscene)


# ── shared bits ────────────────────────────────────────────────────────
_KO_BUF = None


def _ko_buf():
    global _KO_BUF
    if _KO_BUF is None:
        _KO_BUF = pygame.Surface((WIDTH, HEIGHT))
    return _KO_BUF


def _ko_clamp01(v):
    return max(0.0, min(1.0, v))


def _ko_push(surface, buf, z, fx, fy):
    """Push-in: crop around (fx, fy) at zoom z and scale back to full frame."""
    cw = WIDTH / z
    ch = HEIGHT / z
    x0 = max(0.0, min(WIDTH - cw, fx - cw / 2))
    y0 = max(0.0, min(HEIGHT - ch, fy - ch / 2))
    pygame.transform.smoothscale(buf.subsurface((int(x0), int(y0),
                                                 int(cw), int(ch))),
                                 (WIDTH, HEIGHT), surface)


def _ko_strobe(t, period=1600.0, on=700.0):
    """Lockdown strobe envelope 0..1 (fast ramp in/out inside the ON window)."""
    c = t % period
    if c >= on:
        return 0.0
    if c < 150.0:
        return c / 150.0
    if c > on - 150.0:
        return (on - c) / 150.0
    return 1.0


def _ko_tag(surface, text):
    """Location tag, same device as the Archives handoff shots."""
    surf = font_terminal_small.render(text, True, (120, 200, 220))
    surface.blit(surf, (WIDTH // 2 - surf.get_width() // 2, HEIGHT - 250))


def _ko_glow(surface, color, center, radius, alpha):
    """Soft normal-blend glow. (_draw_bloom_circle is additive and stacks
    ~2.85x alpha at the centre - it blew highlights out to white discs.)"""
    if alpha <= 0:
        return
    g = get_glow(int(radius), color, 255).copy()  # cache is shared: never mutate
    g.set_alpha(int(min(255, alpha)))
    surface.blit(g, (int(center[0] - radius), int(center[1] - radius)))


def _ko_tint(surface):
    tint = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
    tint.fill((15, 25, 45, 8))
    surface.blit(tint, (0, 0))


def _ko_smoke_loop(layer, x, y, t_ms, seed=0.0, n=6, cycle=2.7):
    """Endless smoke plume: wisps recycle on a cycle so held shots stay alive."""
    phase = t_ms / 900.0
    for k in range(n):
        tk = (phase + k * (cycle / n)) % cycle
        a = max(0, int(88 * (1 - tk / cycle)))
        if a == 0:
            continue
        r = int(10 + tk * 20)
        px = x + math.sin(tk * 2.1 + k * 1.7 + seed) * 13
        py = y - tk * 58
        pygame.draw.circle(layer, (92, 88, 84, a), (int(px), int(py)), r)


def _ko_sparks(layer, x, y, k, n=10):
    """Radial spark burst; k=0 at the pop, fading out by k=1."""
    for i in range(n):
        a = i * 2 * math.pi / n + 0.4
        r0 = 4 + 52 * k
        r1 = r0 + 18 * (1 - k) + 6
        pygame.draw.line(
            layer, (255, 214, 130, int(220 * (1 - k))),
            (int(x + math.cos(a) * r0), int(y + math.sin(a) * r0)),
            (int(x + math.cos(a) * r1), int(y + math.sin(a) * r1)), 2)


def _ko_concrete(surface, top, bottom):
    """Base wall gradient + panel seams, the void-with-lighting backdrop."""
    _draw_vertical_gradient(surface, 0, 0, WIDTH, HEIGHT, top, bottom)
    for x in range(0, WIDTH, 190):
        s = pygame.Surface((1, HEIGHT), pygame.SRCALPHA)
        s.fill((6, 6, 8, 42))
        surface.blit(s, (x, 0))
    for y in range(120, HEIGHT, 150):
        s = pygame.Surface((WIDTH, 1), pygame.SRCALPHA)
        s.fill((6, 6, 8, 46))
        surface.blit(s, (0, y))


def _ko_actor(surface, who, cx, foot_y, scale, facing_right, t, moving,
              silhouette=False, walk_phase=None):
    """Cast sprite with acting: walk tilt + step bob, or breathing idle.

    walk_phase (radians) drives the stride when given: bob/tilt freeze when
    the actor stops advancing, so a held input-paced shot can never read as
    walking in place. Falls back to the old time-based phase for callers
    that don't track distance.
    """
    w = int(150 * scale) + 8
    h = int(320 * scale) + 8
    ts = pygame.Surface((w, h), pygame.SRCALPHA)
    if who == "volkov":
        draw_volkov(ts, w // 2, h - 6, scale=scale, facing_right=facing_right)
    else:
        draw_biribel(ts, w // 2, h - 6, scale=scale, facing_right=facing_right,
                     in_silhouette=silhouette)
    if moving:
        ph = walk_phase if walk_phase is not None else t * 0.018
        ts = pygame.transform.rotate(ts, math.sin(ph) * 2.4)
        bob = abs(math.sin(ph)) * 3
    else:
        bob = (math.sin(t * 0.006) + 1) * 0.8
    surface.blit(ts, (int(cx - ts.get_width() / 2),
                      int(foot_y - ts.get_height() + 6 - bob)))


# ── shot 0: breach charge insert ──────────────────────────────────────
def _draw_ko_charge_raw(surface, t):
    """Close-up of the charge pack on the stairwell door; breach at 1150ms."""
    boom_t = 1150.0
    arm = _ko_clamp01(t / boom_t)
    shx, shy = _cb_camera_shake(t, 0.6 + 1.2 * arm, 1.0)
    ox, oy = shx, shy

    def W(x, y):
        return (int(x + ox), int(y + oy))

    _ko_concrete(surface, (8, 7, 8), (14, 12, 11))
    layer = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)

    # Door slab filling frame right, seam + rivets + hazard band.
    pygame.draw.rect(surface, (56, 53, 48), (*W(330, -40), 760, 800))
    pygame.draw.line(surface, (24, 22, 20), W(330, -40), W(330, 760), 3)
    for ry in range(20, 700, 90):
        pygame.draw.circle(surface, (74, 71, 64), W(360, ry), 4)
    pygame.draw.line(surface, (76, 72, 62), W(700, -40), W(700, 760), 2)
    for hy in range(-40, 760, 34):
        pygame.draw.line(surface, (120, 104, 40), W(340, hy), W(372, hy + 32), 6)
        pygame.draw.line(surface, (20, 18, 16), W(356, hy - 8), W(388, hy + 24), 6)

    # Charge pack: puck, straps, blinking LED (blink rate arms up).
    px, py = W(600, 340)
    pygame.draw.circle(surface, (26, 26, 28), (px, py), 78)
    pygame.draw.circle(surface, (46, 46, 50), (px, py), 78, 4)
    pygame.draw.circle(surface, (34, 34, 38), (px, py), 52, 2)
    pygame.draw.rect(surface, (34, 32, 30), (*W(548, 288), 104, 16))
    pygame.draw.rect(surface, (34, 32, 30), (*W(548, 376), 104, 16))
    period = _lerp_cutscene(620.0, 140.0, arm)
    led_on = (t % period) < period * 0.4
    pygame.draw.circle(surface, (255, 60, 40) if led_on else (90, 30, 24),
                       (px, py - 34), 10)
    if led_on:
        _ko_glow(surface, (255, 70, 45), (px, py - 34), 26, 60)
    # Wire run up to the frame top.
    pygame.draw.line(surface, (20, 20, 22), (px, py - 78), W(620, -40), 3)

    strobe = _ko_strobe(t)
    if strobe > 0.0:
        layer.fill((200, 15, 10, int(34 * strobe)))

    if t >= boom_t:
        k = _ko_clamp01((t - boom_t) / 350.0)
        flash_a = int(150 * (1 - k))
        if flash_a > 0:
            flash = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
            flash.fill((255, 244, 214, flash_a))
            surface.blit(flash, (0, 0))
        if k < 1.0:
            _ko_sparks(layer, px, py, k, n=12)
            _ko_glow(surface, (255, 200, 120), (px, py), 90, 70 * (1 - k))
        _ko_smoke_loop(layer, px, py - 20, t - boom_t, seed=2.0, n=7)

    from cutscenes.chair import _draw_dust_motes
    _draw_dust_motes(surface, t)
    surface.blit(layer, (0, 0))
    _ko_tint(surface)
    return (px, py, 1.15 + 0.25 * arm)


def _draw_ko_charge_insert(surface, t):
    buf = _ko_buf()
    fx, fy, z = _draw_ko_charge_raw(buf, t)
    _ko_push(surface, buf, z, fx, fy)


# ── shot 1: stairwell tower ───────────────────────────────────────────
def _draw_ko_stairwell_raw(surface, t):
    """Opens just after the breach: flash decaying, smoke already pouring."""
    q = _ease_cutscene(_ko_clamp01(t / 2200.0))          # descent progress
    shake = _cb_camera_shake(t, 3.0, math.exp(-t / 450.0))
    ox = shake[0]
    oy = -56 + 66 * q + shake[1]                          # slow tilt down

    def W(x, y):
        return (int(x + ox), int(y + oy))

    _ko_concrete(surface, (12, 10, 11), (24, 19, 17))
    layer = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)

    pygame.draw.line(surface, (34, 32, 30), W(60, 90), W(940, 90), 3)
    for bx in (250, 660):
        pygame.draw.circle(surface, (58, 20, 18), W(bx, 116), 10)
        pygame.draw.circle(surface, (30, 12, 12), W(bx, 116), 10, 2)

    # Solid stair mass, landing, blown door.
    x0, y0 = 120, 170
    base = y0 + 8 * 40 + 70
    for i in range(8):
        sx, sy = x0 + i * 62, y0 + i * 40
        pygame.draw.rect(surface, (32, 29, 26), (*W(sx, sy), 62, base - sy))
        pygame.draw.line(surface, (74, 68, 58), W(sx, sy), W(sx + 62, sy), 2)
        pygame.draw.line(surface, (16, 15, 14), W(sx, sy + 3), W(sx, base), 1)
    lx, ly = x0 + 8 * 62, y0 + 7 * 40 + 42
    pygame.draw.rect(surface, (28, 26, 24), (*W(lx - 20, ly), 260, 60))
    dx, dy = lx + 150, ly - 128
    pygame.draw.rect(surface, (44, 42, 40), (*W(dx, dy), 92, 172))
    pygame.draw.rect(surface, (24, 22, 20), (*W(dx, dy), 92, 172), 2)
    pygame.draw.rect(surface, (18, 16, 14), (*W(dx + 40, dy + 6), 12, 160))
    _draw_vertical_gradient(surface, dx + 42 + int(ox), dy + 8 + int(oy),
                            8, 156, (255, 206, 140), (120, 84, 48))

    # Residual breach flash + endless smoke from the blown door.
    k0 = _ko_clamp01(t / 400.0)
    if k0 < 1.0:
        flash = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        flash.fill((255, 244, 214, int(120 * (1 - k0))))
        surface.blit(flash, (0, 0))
        _ko_glow(surface, (255, 200, 120),
                   (dx + 46 + int(ox), dy + 96 + int(oy)), 80, 50 * (1 - k0))
    _ko_smoke_loop(layer, dx + 46 + ox, dy + 30 + oy, t, seed=1.0)

    # The pair descends: Volkov leads, Biribel on his six.
    # 8 stride units = 7 stair treads + 1 final step ONTO the landing, so
    # the descent is continuous (no arrival teleport). Owner pass 2026-09-23:
    # "Biribel walks over Volkov" - they shared one diagonal, so when Volkov
    # parked at the landing Biribel's path crossed straight through him.
    # Now Volkov keeps walking a few paces toward the blown door after
    # arriving (spilling past q=1 on wall-clock time, staying slow), and
    # Biribel holds at the bottom tread - their lanes never intersect.
    # Stride stays distance-driven (walk_phase from step count), so a held
    # input-paced shot freezes the bob/tilt instead of treadmill-looping.
    qv = _ko_clamp01(q * 1.12 + 0.16)
    qb = _ko_clamp01(q * 1.12 - 0.12)
    poses = {}
    # Volkov: diagonal descent, then flat walk to the door (t=900..2100).
    step_v = qv * 8.0 + _ease_cutscene(
        _ko_clamp01((t - 900.0) / 1200.0)) * 1.4
    cx_v = x0 + step_v * 62 + 31
    cy_v = y0 + min(step_v, 8.0) * 40
    poses["volkov"] = (cx_v, cy_v)
    _ko_actor(surface, "volkov", *W(cx_v, cy_v), scale=0.66,
              facing_right=True, t=t, moving=step_v < 9.4 - 0.01,
              walk_phase=step_v * math.pi)
    # Biribel: holds at the bottom tread, well behind Volkov's lane.
    step_b = qb * 7.0
    cx_b = x0 + step_b * 62 + 31
    cy_b = y0 + step_b * 40
    poses["biribel"] = (cx_b, cy_b)
    _ko_actor(surface, "biribel", *W(cx_b, cy_b), scale=0.66,
              facing_right=True, t=t, moving=qb < 0.995,
              walk_phase=step_b * math.pi)

    # Alarm strobe wash + bell glows (loops forever while held).
    strobe = _ko_strobe(t)
    if strobe > 0.0:
        layer.fill((200, 15, 10, int(40 * strobe)))
        for bx in (250, 660):
            _draw_light_cone(surface, bx + int(ox), 120 + int(oy),
                             95, (255, 40, 30), alpha=int(44 * strobe))

    from cutscenes.chair import _draw_dust_motes
    _draw_dust_motes(surface, t)
    surface.blit(layer, (0, 0))
    _ko_tint(surface)
    _ko_tag(surface, "STAIRWELL TOWER // SUBLEVEL 1")
    bx_, by_ = poses["biribel"]
    return (bx_ + ox, by_ - 90 + oy, 1.0 + 0.14 * q)


def _draw_ko_stairwell_cut(surface, t):
    buf = _ko_buf()
    fx, fy, z = _draw_ko_stairwell_raw(buf, t)
    _ko_push(surface, buf, z, fx, fy)


# ── shot 2: lobby / mezzanine overwatch ───────────────────────────────
def _draw_ko_aperture_raw(surface, t):
    ox, oy = _cb_camera_shake(t, 1.1, 1.0)
    snap_t = 1950.0
    snapped = t >= snap_t
    flinch = 4.0 if snapped else 0.0

    def W(x, y):
        return (int(x + ox), int(y + oy))

    _ko_concrete(surface, (8, 9, 12), (20, 18, 19))
    layer = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)

    pygame.draw.rect(surface, (26, 24, 26), (*W(0, 520), WIDTH, 120))
    for rx in range(80, WIDTH, 140):
        s = pygame.Surface((60, 2), pygame.SRCALPHA)
        s.fill((255, 255, 255, 10))
        surface.blit(s, W(rx, 560 + (rx % 3) * 14))

    # Mezzanine block: platform edge + railing, backlit doorway, marksman.
    pygame.draw.rect(surface, (30, 28, 30), (*W(690, 330), 310, 200))
    pygame.draw.line(surface, (72, 68, 62), W(690, 330), W(1000, 330), 2)
    for px in range(700, 1000, 44):
        pygame.draw.line(surface, (48, 46, 44), W(px, 304), W(px, 330), 2)
    pygame.draw.line(surface, (58, 56, 52), W(690, 304), W(1000, 304), 2)
    for i in range(3):
        pygame.draw.line(surface, (62, 58, 50), W(690 - 34 + i * 12, 348 + i * 16),
                         W(700 + i * 12, 348 + i * 16), 2)
    _draw_vertical_gradient(surface, 770 + int(ox), 196 + int(oy), 108, 134,
                            (212, 162, 102), (92, 62, 36))
    _draw_light_cone(surface, 824 + int(ox), 268 + int(oy), 100,
                     (255, 200, 130), alpha=22)
    _ko_glow(surface, (255, 190, 120), (824 + int(ox), 262 + int(oy)), 60, 26)

    # Shot state early: the pair ducks with each impact.
    s = _ease_cutscene(_ko_clamp01(t / 1800.0))
    shot_k = None
    if snapped:
        ph = (t - snap_t) % 1700.0
        shot_k = ph / 140.0 if ph < 140.0 else None
    duck = 2.0 * (1.0 - shot_k) if shot_k is not None else 0.0

    # The pair stacked on the pillar's WEST face, pinned by the mezzanine
    # rifle (geometry pass 2026-09-23: the old layout put the pillar BEHIND
    # them with the marksman on the far side - rounds read as a sniper
    # repeatedly missing two motionless targets standing upright in the
    # open. Now the cover is between them and the rifle, they duck with
    # every impact, and the pillar chews the rounds.)
    by = 518 + flinch + duck
    _ko_actor(surface, "volkov", *W(344, by + 2), scale=0.82,
              facing_right=True, t=t, moving=False)
    pygame.draw.line(surface, (200, 160, 90), W(350, by - 116),
                     W(322, by - 110), 4)              # pistol, raised
    _ko_actor(surface, "biribel", *W(392, by), scale=0.8, facing_right=True,
              t=t, moving=False, silhouette=True)
    # Pillar BETWEEN the pair and the mezzanine, drawn after the actors so
    # it occludes Biribel's right edge: he reads as tucked into cover.
    pygame.draw.rect(surface, (36, 34, 36), (*W(410, 230), 86, 320))
    pygame.draw.line(surface, (52, 50, 52), W(496, 230), W(496, 550), 2)
    pygame.draw.line(surface, (20, 18, 18), W(410, 230), W(410, 550), 2)
    for ry in range(250, 540, 22):                    # doorway light grazes
        s_r = pygame.Surface((3, 12), pygame.SRCALPHA)  # the cover's east face
        s_r.fill((255, 190, 120, 46))
        surface.blit(s_r, W(493, ry))
    for rx in (344, 392):                             # faint cool rims, lobby side
        s_r = pygame.Surface((4, 100), pygame.SRCALPHA)
        s_r.fill((120, 150, 175, 44))
        surface.blit(s_r, W(rx - 24, by - 194))

    # Marksman: backlit silhouette in the doorway with warm rim edges; the
    # rifle is laid along the aim line from SHOULDER height (not forehead).
    # He is a cast-sheet IPA figure (figure_kit), cut off at the mezzanine
    # rail so only the upper body shows above the slab.
    mx, my = W(824, 250)
    mk = 0.36                                  # px per arrest unit
    m_foot = my + 258 * mk
    rail_y = W(824, 304)[1]
    prev_clip = surface.get_clip()
    surface.set_clip(pygame.Rect(0, 0, surface.get_width(), rail_y).clip(prev_clip))
    _fk_draw(surface, "ipa", mx, m_foot, mk * 296 / 262.0, facing_right=False,
             silhouette=True, reach=((-40, my + 32 - m_foot), (-22, my + 26 - m_foot)))
    surface.set_clip(prev_clip)
    pygame.draw.arc(surface, (232, 182, 118), (mx - 10, my - 10, 20, 20),
                    -0.5, 0.9, 2)
    pygame.draw.line(surface, (210, 164, 106), (mx + 14, my + 12),
                     (mx + 19, my + 40), 2)
    pygame.draw.line(surface, (10, 8, 8), (mx - 6, my + 20), (mx - 44, my + 34), 4)

    # PA speaker, cold flicker while Balaceanu talks.
    pygame.draw.rect(surface, (30, 30, 34), (*W(84, 168), 28, 38))
    cold = 1.0 if (t % 460.0) < 90.0 else 0.0
    pygame.draw.circle(surface, (220, 235, 245) if cold else (70, 80, 86),
                       W(98, 178), 3)
    if cold:
        layer.fill((190, 205, 215, 16))

    # Laser: pre-snap it sweeps the open lobby - the beam physically CLIPS
    # on the pillar's east face (cover stops light), crawling up the face
    # as it sweeps right - then snaps onto the face and runs the
    # suppression cycle: a round every ~1.7s with muzzle flash, tracer,
    # sparks and an accumulating impact scar. The pillar is the only thing
    # between them and the rifle: that IS the story.
    if snapped:
        ex = 492.0 + math.sin(t * 0.031) * 3
        ey = 430.0 + math.cos(t * 0.027) * 2
        clip_x, clip_y = ex, ey
    else:
        ex = _lerp_cutscene(210.0, 390.0, s)
        ey = 505.0
        clip_f = (818.0 - 496.0) / (818.0 - ex)   # where the beam meets x=496
        clip_x = 496.0
        clip_y = 262.0 + (ey - 262.0) * clip_f
    ax, ay = W(818, 262)
    bx, byy = W(clip_x, clip_y)
    flick = 0.75 + 0.25 * math.sin(t * 0.045)

    # Rifle: dark silhouette laid along the aim line + scope glint, so the
    # figure reads as "aiming a weapon", not "standing in a doorway".
    aim_len = math.hypot(bx - ax, byy - ay)
    ux = (bx - ax) / aim_len if aim_len > 1 else 0.0
    uy = (byy - ay) / aim_len if aim_len > 1 else 1.0
    pygame.draw.line(surface, (8, 7, 7), (ax - ux * 14, ay - uy * 14),
                     (ax + ux * 44, ay + uy * 44), 5)
    pygame.draw.line(surface, (28, 26, 26), (ax - ux * 10, ay - uy * 10),
                     (ax + ux * 40, ay + uy * 40), 2)
    pygame.draw.circle(surface, (182, 222, 238),
                       (int(ax + ux * 8), int(ay + uy * 8)), 2)

    pygame.draw.line(layer, (255, 60, 50, int(66 * flick)), (ax, ay), (bx, byy), 7)
    pygame.draw.line(layer, (255, 120, 90, int(215 * flick)), (ax, ay), (bx, byy), 2)
    pygame.draw.circle(layer, (255, 220, 200, 235), (ax, ay), 3)
    for f in (0.25, 0.45, 0.65, 0.85):
        gx = ax + (bx - ax) * f
        gy = ay + (byy - ay) * f
        ga = int((40 + 30 * math.sin(t * 0.03 + f * 20)) * flick)
        if ga > 0:
            pygame.draw.circle(layer, (255, 150, 120, ga), (int(gx), int(gy)), 2)
    _ko_glow(surface, (255, 90, 60), (bx, byy), 26, 40 * flick)
    if snapped:
        if shot_k is not None:
            _ko_glow(surface, (255, 226, 170), (ax, ay), 34, 90 * (1 - shot_k))
            pygame.draw.line(layer, (255, 232, 190, int(230 * (1 - shot_k))),
                             (ax, ay), (bx + ux * 10, byy + uy * 10), 3)
            _ko_sparks(layer, bx, byy, shot_k, n=9)
        else:
            # Between rounds: quiet tick sparks only.
            tick = (t - snap_t) % 800.0
            if tick < 260.0:
                _ko_sparks(layer, bx, byy, tick / 260.0 * 0.5, n=4)
        # Impact scar on the pillar's east face: chips accumulate round by
        # round - rounds IN, cover HOLDS.
        for i, (oxc, oyc, rc) in enumerate(((0, 0, 3), (-8, 9, 2), (-14, 16, 2),
                                            (4, -8, 2), (-18, -3, 2))):
            if (t - snap_t) > 200 + i * 260:
                pygame.draw.circle(surface, (22, 20, 19),
                                   (int(bx + oxc), int(byy + oyc)), rc)
                pygame.draw.circle(surface, (96, 90, 82),
                                   (int(bx + oxc), int(byy + oyc)), rc, 1)
    else:
        pygame.draw.circle(layer, (255, 150, 120, 235), (bx, byy), 3)

    from cutscenes.chair import _draw_dust_motes
    _draw_dust_motes(surface, t)
    surface.blit(layer, (0, 0))
    _ko_tint(surface)
    _ko_tag(surface, "CENTRAL LOBBY // MEZZANINE OVERWATCH")
    fx = _lerp_cutscene(560.0, 370.0, _ko_clamp01(t / snap_t))
    fy = _lerp_cutscene(360.0, 425.0, _ko_clamp01(t / snap_t))
    return (fx, fy, 1.06 + 0.12 * _ko_clamp01(t / snap_t))


def _draw_ko_aperture_cut(surface, t):
    buf = _ko_buf()
    fx, fy, z = _draw_ko_aperture_raw(buf, t)
    _ko_push(surface, buf, z, fx, fy)


# ── shot 3: loading dock / exfil ──────────────────────────────────────
def _draw_ko_van_raw(surface, t):
    # Empty-dock establishing preview: nobody is physically here yet
    # (Volkov is beside you in the previous shot), so the shot stays a
    # promise, not a continuity break.
    drift = _ease_cutscene(_ko_clamp01(t / 2600.0))
    pan = -34 + 26 * drift
    ox, oy = _cb_camera_shake(t, 0.8, 1.0)
    ox += pan
    oy += -26

    def W(x, y):
        return (int(x + ox), int(y + oy))

    _ko_concrete(surface, (7, 8, 10), (18, 16, 14))
    layer = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
    layer0 = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)

    # Shutter half-raised, cold slit shimmering over the top.
    pygame.draw.rect(surface, (26, 28, 32), (*W(600, 120), 340, 250))
    for i in range(0, 250, 14):
        pygame.draw.line(surface, (40, 44, 50), W(604, 128 + i),
                         W(936, 128 + i), 3)
    slit_a = 200 + int(30 * math.sin(t * 0.011))
    pygame.draw.rect(surface, (120, min(255, slit_a), 180), (*W(600, 108), 340, 10))
    for sx in range(620, 940, 46):
        pygame.draw.polygon(layer0, (150, 180, 205, 18),
                            [W(sx, 370), W(sx + 26, 370),
                             W(sx - 26, 560), W(sx - 60, 560)])
    # Crane silhouette + crate stack.
    pygame.draw.line(surface, (50, 48, 42), W(90, 70), W(90, 300), 6)
    pygame.draw.line(surface, (50, 48, 42), W(90, 84), W(360, 84), 5)
    sway = math.sin(t * 0.0016) * 6
    pygame.draw.line(surface, (30, 28, 24), W(300, 84),
                     W(300 + int(sway), 180), 2)
    pygame.draw.rect(surface, (34, 32, 26), (*W(292 + int(sway), 180), 16, 14))
    surface.blit(layer0, (0, 0))   # streaks stay BEHIND van, crates and cast
    for (cxx, cyy) in ((880, 430), (880, 486), (824, 486)):
        pygame.draw.rect(surface, (74, 62, 40), (*W(cxx, cyy), 56, 56))
        pygame.draw.rect(surface, (44, 36, 24), (*W(cxx, cyy), 56, 56), 2)

    # The van - armored cargo van, side-on, rear doors open. Owner pass
    # 2026-09-22: the old flat box read "ugly truck". Proper silhouette
    # now: cargo box + raked cab, roof kit, wheel arches, panel seams,
    # and a warm load bay spilling light onto the dock.
    shadow = pygame.Surface((450, 44), pygame.SRCALPHA)
    pygame.draw.ellipse(shadow, (0, 0, 0, 80), (0, 0, 450, 44))
    surface.blit(shadow, W(400, 482))
    # Cargo box: body, roof strip, skirt, panel seams, rivet rails, band.
    vb_x, vb_y, vb_w, vb_h = 434, 310, 302, 162
    pygame.draw.rect(surface, (66, 70, 78), (*W(vb_x, vb_y), vb_w, vb_h),
                     border_radius=5)
    pygame.draw.rect(surface, (30, 33, 38), (*W(vb_x, vb_y), vb_w, vb_h), 2,
                     border_radius=5)
    pygame.draw.rect(surface, (94, 100, 110), (*W(vb_x, vb_y), vb_w, 9))
    pygame.draw.rect(surface, (40, 43, 49), (*W(vb_x, vb_y + vb_h - 16), vb_w, 16),
                     border_radius=4)
    for i in range(1, 5):
        sxp = vb_x + int(i * vb_w / 5)
        pygame.draw.line(surface, (48, 52, 60), W(sxp, vb_y + 12),
                         W(sxp, vb_y + vb_h - 16), 2)
    for i in range(10):
        pygame.draw.circle(surface, (46, 50, 58),
                           W(vb_x + 14 + i * 30, vb_y + 5), 2)
    pygame.draw.rect(surface, (112, 120, 132),
                     (*W(vb_x + 14, vb_y + 66), vb_w - 28, 6))
    # Open rear: dark jamb, warm load-bay gradient, door swung flat left.
    pygame.draw.rect(surface, (34, 30, 25), (*W(vb_x - 2, vb_y + 8), 26, vb_h - 14))
    _draw_vertical_gradient(surface, vb_x + int(ox), vb_y + 10 + int(oy), 24,
                            vb_h - 20, (255, 210, 142), (118, 82, 46))
    pygame.draw.polygon(surface, (52, 56, 64),
                        [W(vb_x, vb_y + 2), W(vb_x - 30, vb_y + 12),
                         W(vb_x - 30, vb_y + vb_h - 6), W(vb_x, vb_y + vb_h - 2)])
    pygame.draw.line(surface, (26, 28, 32), W(vb_x - 30, vb_y + 12),
                     W(vb_x - 30, vb_y + vb_h - 6), 2)
    # Cab: raked windshield, glass, headlight, bumper.
    cab = [(vb_x + vb_w, vb_y + 16), (vb_x + vb_w + 46, vb_y + 24),
           (vb_x + vb_w + 72, vb_y + 52), (vb_x + vb_w + 82, vb_y + 88),
           (vb_x + vb_w + 86, vb_y + vb_h - 2), (vb_x + vb_w, vb_y + vb_h - 2)]
    pygame.draw.polygon(surface, (58, 62, 70), [W(*p) for p in cab])
    pygame.draw.polygon(surface, (28, 31, 36), [W(*p) for p in cab], 2)
    pygame.draw.polygon(surface, (134, 170, 192),
                        [W(vb_x + vb_w + 44, vb_y + 30),
                         W(vb_x + vb_w + 68, vb_y + 54),
                         W(vb_x + vb_w + 44, vb_y + 54)])
    pygame.draw.line(surface, (204, 226, 240), W(vb_x + vb_w + 60, vb_y + 38),
                     W(vb_x + vb_w + 50, vb_y + 50), 2)
    pygame.draw.rect(surface, (110, 130, 140),
                     (*W(vb_x + vb_w + 8, vb_y + 26), 26, 20))
    pygame.draw.circle(surface, (235, 214, 150),
                       W(vb_x + vb_w + 80, vb_y + vb_h - 34), 4)
    pygame.draw.rect(surface, (24, 26, 30),
                     (*W(vb_x + vb_w + 78, vb_y + vb_h - 22), 12, 12))
    # Wheels in arches: tire, rim, hub.
    for wx in (506, 792):
        pygame.draw.arc(surface, (20, 22, 26), (*W(wx - 34, vb_y + vb_h - 40), 68, 68),
                        math.pi, 2 * math.pi, 8)
        pygame.draw.circle(surface, (17, 17, 20), W(wx, 486), 27)
        pygame.draw.circle(surface, (98, 104, 114), W(wx, 486), 11)
        pygame.draw.circle(surface, (40, 44, 50), W(wx, 486), 4)
    # Roof kit: AC unit + pulsing beacon so it reads as the same armored
    # van the player exfils onto in the gameplay slice.
    pygame.draw.rect(surface, (54, 58, 66), (*W(608, vb_y - 14), 46, 14))
    pygame.draw.rect(surface, (30, 33, 38), (*W(608, vb_y - 14), 46, 14), 1)
    beacon_pulse = 0.5 + 0.5 * math.sin(t * 0.006)
    pygame.draw.circle(surface, (70, 60, 30), W(560, vb_y - 4), 9, 1)
    pygame.draw.circle(surface, (225, int(120 + 90 * beacon_pulse), 70),
                       W(560, vb_y - 4), 7)
    # Rear kit on the dock: jack + hazard chevrons by the open doors.
    pygame.draw.rect(surface, (160, 44, 40), (*W(392, 458), 6, 24))
    for hy in (0, 8, 16):
        pygame.draw.line(surface, (148, 130, 30), W(404 + hy, 478 - hy),
                         W(422 + hy, 460 - hy), 3)
    shimmer = 0.5 + 0.5 * math.sin(t * 0.007)
    pool = pygame.Surface((340, 110), pygame.SRCALPHA)
    pygame.draw.ellipse(pool, (255, 205, 140, 22), (0, 0, 340, 110))
    pygame.draw.ellipse(pool, (255, 208, 148, 22), (36, 14, 268, 82))
    pygame.draw.ellipse(pool, (255, 214, 160, int(18 + 8 * shimmer)),
                        (72, 28, 196, 54))
    surface.blit(pool, W(262, 470))
    _draw_light_cone(surface, 424 + int(ox), 408 + int(oy), 150,
                     (255, 205, 140), alpha=26)
    _ko_glow(surface, (255, 205, 140), (428 + int(ox), 400 + int(oy)),
               70, 26 + 12 * shimmer)

    from cutscenes.chair import _draw_dust_motes
    _draw_dust_motes(surface, t)
    surface.blit(layer, (0, 0))
    _ko_tint(surface)
    _ko_tag(surface, "LOADING DOCK // EXFIL")
    fx = _lerp_cutscene(620.0, 470.0, drift)
    return (fx, 400.0 + oy, 1.0 + 0.16 * drift)


def _draw_ko_van_cut(surface, t):
    buf = _ko_buf()
    fx, fy, z = _draw_ko_van_raw(buf, t)
    _ko_push(surface, buf, z, fx, fy)


# RPE6 Phase 2 (A-003 take registry): the cutscene scene ids this module owns.
# cutscenes.engine.draw_cutscene_scene finds them through core.cutscene_registry
# instead of importing this module by name (boundary rule 4 / W1).
from core.cutscene_registry import register_scene_renderers as _register_takes  # noqa: E402

_register_takes({
    "m3_ko_charge": _draw_ko_charge_insert,
    "m3_ko_stairwell": _draw_ko_stairwell_cut,
    "m3_ko_aperture": _draw_ko_aperture_cut,
    "m3_ko_van": _draw_ko_van_cut,
})
