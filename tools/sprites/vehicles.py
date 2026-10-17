"""vehicles.py - Mission 2 road vehicles as authored sprite sheets (Polish T7).

Replaces the per-frame polygon soup in ``missions/m2/draw.py``
(``_draw_civilian_car``, ``_draw_burned_car``, ``_draw_ipa_truck``,
``_draw_ipa_truck_charred``, ``_draw_tanker``). Those renderers stay as the
fallback; ``core.artpack.vehicle(key)`` returns ``None`` when this sheet is
absent or ``ACA_ART=legacy``.

Frames (all face EAST, hood right, like the procedural cars):
  car_<paint>_<w>x<h>         intact sedan, one per palette x rect size used
  burned_<paint>_<w>x<h>      charred wreck of the same car
  smoulder_<w>x<h>_<0..3>     glow overlay (cabin + engine bay), 4 levels
  ipa_truck / ipa_truck_charred / ipa_glow_<0..3>
  tanker / tanker_wreck       (tanker LED + fuel pool stay procedural: they
                               animate with mission state)

Every frame's ``anchor`` is the offset of the vehicle's collision-rect
top-left inside the frame: blit at (rect.x - ax, rect.y - ay).

    python tools/sprites/vehicles.py [--preview] [--out DIR]
"""
import math
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import kit  # noqa: E402
import palette as P  # noqa: E402
import pygame  # noqa: E402

FAMILY = "vehicles"
PAD = 24
# Every civilian rect size placed by missions/m2/world.py. A car whose size
# is not listed simply falls back to the procedural renderer.
CAR_SIZES = ((118, 44), (126, 48), (110, 42), (112, 44), (116, 44), (126, 46), (112, 42))
TRUCK = (160, 54)
TANKER = (64 * 5 - 12, 64 * 3 - 16)
SMOULDER_LEVELS = (0.25, 0.5, 0.75, 1.0)
# Charred metal: warm-neutral ramp (the generic ramp() drifts cool, which
# read as blue paint on burnt steel). deep -> hi.
CHAR_RAMP = [(10, 8, 7), (21, 17, 14), (36, 30, 25), (54, 45, 37), (74, 62, 50)]


def _car_layout(w, h):
    trunk_w = int(w * 0.22)
    hood_w = int(w * 0.26)
    return trunk_w, hood_w, trunk_w, w - trunk_w - hood_w, w - hood_w


def _tyres(s, ox, oy, w, h, xs, tw=16, th=9, col=P.TYRE, hi=P.TYRE_HI, melt=False):
    for ax in xs:
        for ty in (oy - 4, oy + h - th + 4):
            if melt:
                pygame.draw.ellipse(s, col, (ox + ax - tw // 2, ty + 1, tw, th - 1))
                continue
            kit.rrect(s, col, (ox + ax - tw // 2, ty, tw, th), 2)
            s.fill(hi, (ox + ax - tw // 2 + 2, ty, tw - 4, 1))
            for gx in range(ox + ax - tw // 2 + 3, ox + ax + tw // 2 - 2, 3):   # tread
                s.fill(P.mix(col, hi, 0.35), (gx, ty + 2, 1, th - 3))
            s.fill(P.mix(col, hi, 0.5), (ox + ax - 1, ty + 1, 2, th - 2))


def car(paint, w, h):
    R = P.ramp(paint)
    deep, shd, base, lit, hi = R
    roof = P.shade(paint, 0.84)
    RR = P.ramp(roof, 5, 0.8)
    G = P.ramp(P.GLASS, 5, 0.9)
    fw, fh = w + PAD * 2, h + PAD * 2
    ox = oy = PAD
    trunk_w, hood_w, cab_x, cab_w, hood_x = _car_layout(w, h)
    body = kit.new(fw, fh)
    _tyres(body, ox, oy, w, h, (trunk_w + 8, hood_x + 6))
    # mirrors (stick out of the cabin just behind the windshield)
    for my in (oy - 2, oy + h):
        body.fill(shd, (ox + cab_x + cab_w - 7, my, 4, 2))
    # hull: base, lit top band, shaded lower band, rounded nose/tail
    kit.rrect(body, base, (ox, oy, w, h), 8)
    kit.rrect(body, lit, (ox + 1, oy, w - 2, 4), 4)
    body.fill(hi, (ox + 6, oy, w - 12, 1))
    kit.rrect(body, shd, (ox + 1, oy + h - 5, w - 2, 5), 4)
    body.fill(deep, (ox + 6, oy + h - 1, w - 12, 1))
    body.fill(lit, (ox, oy + 6, 1, h - 12))                 # lit tail edge
    body.fill(shd, (ox + w - 1, oy + 6, 1, h - 12))         # shaded nose edge
    # hood: crease lines catch the light, cowl seam
    body.fill(deep, (ox + hood_x, oy + 3, 1, h - 6))
    for cy, c in ((oy + h // 3, lit), (oy + 2 * h // 3, shd)):
        body.fill(c, (ox + hood_x + 4, cy, hood_w - 9, 1))
    # trunk seam + lid highlight
    body.fill(deep, (ox + trunk_w, oy + 3, 1, h - 6))
    body.fill(lit, (ox + 3, oy + 5, trunk_w - 6, 1))
    # glass surround (windshield front, rear window back) with selective inner edge
    gx, gy, gw, gh = ox + cab_x + 2, oy + 4, cab_w - 4, h - 8
    kit.rrect(body, G[1], (gx, gy, gw, gh), 4)
    kit.rrect(body, G[2], (gx + 1, gy + 1, gw - 2, gh - 2), 3)
    # windshield reflection: two warm diagonal glints, upper-left lit
    for k, c in ((0, G[4]), (4, G[3])):
        for i in range(min(gh - 4, 9)):
            x = gx + gw - 4 - k - i // 2
            body.set_at((x, gy + 2 + i), c)
    body.fill(G[3], (gx + 1, gy + 2, 1, gh - 4))             # rear window edge
    # roof panel
    rx, ry, rw, rh = ox + cab_x + 7, oy + 7, cab_w - 14, h - 14
    kit.rrect(body, RR[2], (rx, ry, rw, rh), 3)
    kit.inner_line(body, (rx + 1, ry, rw - 2, rh), RR[3], RR[1])
    body.fill(RR[4], (rx + 2, ry, rw - 4, 1))
    body.fill(RR[1], (rx + rw // 2 + 2, ry + 2, 1, rh - 4))  # sunroof seam
    # door seams only on the exposed body strip above/below the glass
    for dx in (cab_x + cab_w // 3, cab_x + 2 * cab_w // 3):
        body.fill(deep, (ox + dx, oy + 1, 1, 3))
        body.fill(deep, (ox + dx, oy + h - 4, 1, 3))
        body.fill(lit, (ox + dx + 1, oy + 1, 1, 2))
    # lights, grille, plate
    for hy in (oy + 4, oy + h - 8):
        body.fill(P.mix(P.HEADLIGHT, deep, 0.45), (ox + w - 4, hy, 3, 4))
        body.fill(P.HEADLIGHT, (ox + w - 3, hy, 2, 3))
        body.fill(P.TAILLIGHT, (ox + 1, hy, 2, 4))
    body.fill((20, 18, 16), (ox + w - 7, oy + h // 2 - 4, 3, 8))
    body.fill(P.PLATE, (ox - 1, oy + h // 2 - 3, 3, 7))
    body.fill(P.shade(P.PLATE, 0.6), (ox - 1, oy + h // 2 + 3, 3, 1))
    body = kit.outline(body)
    out = kit.new(fw, fh)
    kit.shadow(out, (ox, oy - 2, w, h + 4), r=8)
    out.blit(body, (0, 0))
    return out


def burned(paint, w, h, seed):
    rng = random.Random(seed)
    C = CHAR_RAMP
    deep, shd, base, lit, hi = C
    fw, fh = w + PAD * 2, h + PAD * 2
    ox = oy = PAD
    trunk_w, hood_w, cab_x, cab_w, hood_x = _car_layout(w, h)
    out = kit.new(fw, fh)
    # ground scorch: flat two-step, wider than the car, offset with the wind
    lay = kit.new(fw, fh)
    pygame.draw.ellipse(lay, (*P.SOOT, 120), (ox - 20, oy - 10, w + 40, h + 26))
    pygame.draw.ellipse(lay, (4, 3, 3, 110), (ox - 6, oy - 2, w + 14, h + 10))
    out.blit(lay, (0, 0))
    body = kit.new(fw, fh)
    _tyres(body, ox, oy, w, h, (trunk_w + 8, hood_x + 6), 14, 7, (12, 10, 9), deep, melt=True)
    kit.rrect(body, base, (ox, oy, w, h), 8)
    kit.rrect(body, lit, (ox + 1, oy, w - 2, 3), 4)
    kit.rrect(body, shd, (ox + 1, oy + h - 4, w - 2, 4), 4)
    # blistered paint remnants - flat blotches of the original colour
    rem = P.mix(paint, P.CHAR, 0.55)
    rem_hi = P.mix(paint, P.CHAR, 0.35)
    for _ in range(5):
        bx = rng.randint(4, w - 22)
        by = rng.choice((rng.randint(2, 6), rng.randint(h - 12, h - 8)))
        bw, bh = rng.randint(10, 20), rng.randint(4, 7)
        pygame.draw.ellipse(body, rem, (ox + bx, oy + by, bw, bh))
        body.fill(rem_hi, (ox + bx + 2, oy + by, max(1, bw - 6), 1))
    # soot smears (flat, darkest step)
    for _ in range(3):
        sx, sy = rng.randint(0, w - 26), rng.randint(0, h - 12)
        pygame.draw.ellipse(body, shd, (ox + sx, oy + sy, rng.randint(14, 26), rng.randint(6, 10)))
    # cabin cavity: roof collapsed, glass gone
    cx, cy, cw, ch = ox + cab_x + 2, oy + 4, cab_w - 4, h - 8
    kit.rrect(body, (8, 6, 5), (cx, cy, cw, ch), 3)
    kit.rrect(body, (16, 13, 11), (cx + 3, cy + 3, cw - 6, ch - 6), 2)   # ash-covered seats
    for _ in range(6):
        body.fill(P.ASH, (rng.randint(cx + 4, cx + cw - 6), rng.randint(cy + 4, cy + ch - 5), 2, 1))
    body.fill(lit, (cx + 1, cy, cw - 2, 1))                   # sill catches the key light
    for _ in range(4):                                        # twisted roof ribs
        x1 = rng.randint(cx + 3, cx + cw - 4)
        y1 = rng.randint(cy + 2, cy + ch - 3)
        x2, y2 = x1 + rng.randint(-8, 8), y1 + rng.randint(-5, 5)
        pygame.draw.line(body, base, (x1, y1), (x2, y2), 2)
        pygame.draw.line(body, hi, (x1, y1), (x2, y2), 1)
    for dx in (cab_x + cab_w // 3, cab_x + 2 * cab_w // 3):
        body.fill(deep, (ox + dx, oy + 1, 1, 3))
        body.fill(deep, (ox + dx, oy + h - 4, 1, 3))
    body.fill(deep, (ox + hood_x, oy + 3, 1, h - 6))
    body.fill(deep, (ox + trunk_w, oy + 3, 1, h - 6))
    body.fill((4, 3, 3), (ox + hood_x + hood_w - 8, oy + h // 2 - 3, 6, 6))
    for hy in (oy + 5, oy + h - 8):
        body.fill((14, 11, 9), (ox + w - 3, hy, 2, 3))
        body.fill((40, 12, 10), (ox + 1, hy, 2, 3))
    body = kit.outline(body, (6, 5, 4))
    out.blit(body, (0, 0))
    return out


def _glow(surf, cx, cy, rings, level, clip=None):
    lay = kit.new(*surf.get_size())
    for r, col, a in rings:
        pygame.draw.circle(lay, (*col, int(a * level)), (cx, cy), r)
    if clip is not None:
        x, y, w, h = clip
        m = kit.new(*surf.get_size())
        m.fill((255, 255, 255, 255), clip)
        lay.blit(m, (0, 0), special_flags=pygame.BLEND_RGBA_MIN)
    surf.blit(lay, (0, 0))


def smoulder(w, h, level):
    fw, fh = w + PAD * 2, h + PAD * 2
    ox = oy = PAD
    trunk_w, hood_w, cab_x, cab_w, hood_x = _car_layout(w, h)
    s = kit.new(fw, fh)
    cab = (ox + cab_x + 5, oy + 7, cab_w - 10, h - 14)
    F = P.FIRE
    _glow(s, cab[0] + cab[2] // 2, cab[1] + cab[3] // 2,
          ((22, F[1], 90), (14, F[2], 120), (7, F[3], 150)), level, cab)
    _glow(s, ox + hood_x + 14, oy + h // 2, ((10, F[1], 130), (5, F[3], 90)), level)
    return s


def _font_label(surf, s, x, y, col, scale=1):
    kit.text(surf, s, x, y, col, sx=scale, sy=scale)


def ipa_truck(charred=False, seed=0):
    w, h = TRUCK
    fw, fh = w + PAD * 2, h + PAD * 2
    ox = oy = PAD
    rng = random.Random(seed)
    cargo_w = int(w * 0.68)
    if charred:
        CG = CHAR_RAMP
        CB = CG
    else:
        CG = P.ramp(P.IPA_CARGO)
        CB = P.ramp(P.IPA_CAB)
    out = kit.new(fw, fh)
    kit.shadow(out, (ox, oy - 2, w, h + 4), r=5, alpha=(90, 50) if charred else (75, 40))
    b = kit.new(fw, fh)
    axles = (16, cargo_w // 2, w - 14)
    if charred:
        for ax in axles:
            for ty in (oy - 3, oy + h - 3):
                if rng.random() > 0.25:
                    kit.rrect(b, (8, 8, 10), (ox + ax - 7, ty, 14, 6), 2)
                else:
                    b.fill(CG[0], (ox + ax - 3, ty + 2, 6, 3))
    else:
        _tyres(b, ox, oy, w, h, axles, 16, 7)
    # cargo box
    deep, shd, base, lit, hi = CG
    kit.rrect(b, base, (ox, oy, cargo_w, h), 4)
    kit.rrect(b, lit, (ox + 1, oy, cargo_w - 2, 4), 3)
    b.fill(hi, (ox + 4, oy, cargo_w - 8, 1))
    kit.rrect(b, shd, (ox + 1, oy + h - 5, cargo_w - 2, 5), 3)
    b.fill(lit, (ox, oy + 4, 1, h - 8))
    rx = ox + cargo_w // 2
    if charred:
        for bx, bw in ((6, cargo_w // 3), (cargo_w // 2 - 10, 28), (cargo_w - cargo_w // 3, cargo_w // 4)):
            kit.rrect(b, shd, (ox + bx, oy + 3, bw, h - 8), 3)
            b.fill(deep, (ox + bx + 1, oy + h - 6, bw - 2, 1))
        for _ in range(5):
            sx, sy = rng.randint(4, cargo_w - 30), rng.randint(2, h - 16)
            pygame.draw.ellipse(b, P.SOOT, (ox + sx, oy + sy, rng.randint(16, 30), rng.randint(10, 18)))
        off = rng.randint(-3, 3)
        pygame.draw.line(b, P.SOOT, (rx, oy + 3), (rx + off, oy + h - 5), 3)
        b.fill(hi, (rx + 1, oy + 3, 1, h - 8))
    else:
        # tarp ridge: folded crest lit on the left face
        b.fill(deep, (rx - 1, oy + 3, 2, h - 8))
        b.fill(hi, (rx + 1, oy + 3, 1, h - 8))
    for frac in (0.33, 0.66):
        sy = oy + int(h * frac)
        b.fill(deep, (ox + 2, sy, cargo_w - 4, 1))
        if not charred:
            b.fill(lit, (ox + 2, sy + 1, cargo_w - 4, 1))
            for x in range(ox + 8, ox + cargo_w - 6, 16):
                b.fill(deep, (x, sy - 1, 2, 2))
                b.set_at((x, sy - 1), hi)
    sten = (70, 58, 42) if charred else P.IPA_STENCIL
    tw = kit.text_w("IPA", 1, 2)
    _font_label(b, "IPA", rx - tw // 2, oy + 6, sten, 2)
    if not charred:
        _font_label(b, "CGO-12", rx - kit.text_w("CGO-12") // 2, oy + h - 14, P.shade(P.IPA_STENCIL, 0.8))
    b.fill(deep, (ox + 1, oy + 2, 2, h - 4))                 # tailgate
    b.fill(lit, (ox + 3, oy + 2, 1, h - 4))
    # cab
    cx = ox + cargo_w
    cw = w - cargo_w
    d2, s2, b2, l2, h2 = CB
    kit.rrect(b, b2, (cx, oy, cw, h), 4)
    kit.rrect(b, l2, (cx + 2, oy + 2, cw - 22, 3), 2)
    b.fill(d2, (cx, oy, 2, h))
    kit.rrect(b, s2, (cx + 1, oy + h - 4, cw - 2, 4), 3)
    wx, wy, ww, wh = cx + cw - 18, oy + 4, 12, h - 8
    if charred:
        kit.rrect(b, (5, 4, 3), (wx, wy, ww, wh), 2)
    else:
        G = P.ramp(P.GLASS)
        kit.rrect(b, G[2], (wx, wy, ww, wh), 2)
        b.fill(G[4], (wx + 1, wy, ww - 2, 1))
        for i in range(6):
            b.set_at((wx + ww - 3 - i // 2, wy + 3 + i), G[3])
        for hy in (oy + 6, oy + h - 11):
            b.fill(P.mix(P.HEADLIGHT, d2, 0.4), (ox + w - 4, hy, 3, 5))
            b.fill(P.HEADLIGHT, (ox + w - 3, hy + 1, 2, 3))
    b = kit.outline(b, (8, 6, 5) if charred else None)
    out.blit(b, (0, 0))
    return out


def ipa_glow(level, seed):
    w, h = TRUCK
    fw, fh = w + PAD * 2, h + PAD * 2
    ox = oy = PAD
    cargo_w = int(w * 0.68)
    rng = random.Random(seed)
    s = kit.new(fw, fh)
    F = P.FIRE
    _glow(s, ox + 10 + (cargo_w - 20) // 2, oy + 8 + (h - 16) // 2,
          ((26, F[1], 80), (16, F[2], 110), (8, F[3], 140)), level, (ox + 6, oy + 4, cargo_w - 12, h - 8))
    lay = kit.new(fw, fh)
    for i in range(6):                     # glowing fissures, own phase each
        x, y = rng.randint(ox + 6, ox + cargo_w - 6), rng.randint(oy + 4, oy + h - 4)
        pts = [(x, y)]
        for _ in range(rng.randint(2, 4)):
            px = max(ox + 4, min(ox + cargo_w - 5, pts[-1][0] + rng.randint(-18, 18)))
            pts.append((px, max(oy + 3, min(oy + h - 4, pts[-1][1] + rng.randint(-10, 10)))))
        ph = 0.55 + 0.45 * math.sin(level * 6.0 + i * 1.9)
        pygame.draw.lines(lay, (*F[1], int(200 * ph)), False, pts, 3)
        pygame.draw.lines(lay, (*F[3], int(230 * ph)), False, pts, 1)
    s.blit(lay, (0, 0))
    _glow(s, ox + w - 12, oy + h // 2, ((11, F[1], 140), (6, F[3], 100)), level)
    return s


def tanker(wreck=False):
    w, h = TANKER
    fw, fh = w + PAD * 2, h + PAD * 2 + 40            # valve hangs below the tank
    ox = oy = PAD
    out = kit.new(fw, fh)
    if wreck:
        lay = kit.new(fw, fh)
        pygame.draw.ellipse(lay, (0, 0, 0, 200), (ox - 15, oy + 22, w + 30, h + 30 - PAD))
        out.blit(lay, (0, 0))
        b = kit.new(fw, fh)
        C = CHAR_RAMP
        kit.rrect(b, C[1], (ox, oy, w, h), 22)
        kit.rrect(b, C[2], (ox + 3, oy + 2, w - 6, h // 2), 20)
        pygame.draw.ellipse(b, (12, 10, 9), (ox + 20, oy + 10, w - 40, h - 20))
        pygame.draw.ellipse(b, C[0], (ox + 34, oy + 20, w - 68, h - 40))
        rng = random.Random(4517)
        for i in range(7):
            x = ox + 40 + i * (w - 80) // 6 + rng.randint(-4, 4)
            y1, y2 = oy + 18 + rng.randint(0, 10), oy + h - 18 - rng.randint(0, 10)
            pygame.draw.line(b, C[3], (x, y1), (x + rng.randint(-6, 6), y2), 2)
        kit.rrect(b, (60, 45, 35), (ox, oy, w, h), 22, 2)
        out.blit(kit.outline(b, (8, 6, 5)), (0, 0))
        return out
    kit.shadow(out, (ox, oy - 2, w, h + 4), r=18, alpha=(80, 42))
    b = kit.new(fw, fh)
    cab_w = int(w * 0.18)
    tx, tw = ox + cab_w, w - cab_w
    _tyres(b, ox, oy, w, h, (14, cab_w + int(tw * 0.35), cab_w + int(tw * 0.75)), 18, 8)
    # cab (faces WEST here, like the procedural tanker)
    CB = P.ramp(P.TANK_CAB)
    kit.rrect(b, CB[2], (ox, oy, cab_w, h), 5)
    kit.rrect(b, CB[3], (ox + 2, oy + 2, cab_w - 4, 4), 2)
    kit.rrect(b, CB[1], (ox + 1, oy + h - 5, cab_w - 2, 5), 3)
    b.fill(CB[0], (ox + cab_w - 2, oy, 2, h))
    G = P.ramp(P.GLASS)
    kit.rrect(b, G[2], (ox + 3, oy + 6, 11, h - 12), 2)
    b.fill(G[4], (ox + 4, oy + 6, 9, 1))
    for i in range(10):
        b.set_at((ox + 5 + i // 3, oy + 9 + i), G[3])
    for hy in (oy + 6, oy + h - 11):
        b.fill(P.HEADLIGHT, (ox + 1, hy, 2, 4))
    # tank: a horizontal cylinder - lit crown band, shaded belly, steel ramp
    T = P.ramp(P.TANK_STEEL)
    kit.rrect(b, T[2], (tx, oy, tw, h), 18)
    belly = P.mix(T[1], T[0], 0.45)
    bands = ((0.00, 0.14, T[3]), (0.05, 0.09, T[4]), (0.72, 0.88, T[1]), (0.88, 1.0, belly))
    for a, z, c in bands:
        y0, y1 = oy + int(h * a), oy + int(h * z)
        kit.rrect(b, c, (tx + 2, y0, tw - 4, max(1, y1 - y0)), 10)
    # dither the crown-to-body and body-to-belly transitions (broad, reads)
    kit.dither(b, (tx + 10, oy + int(h * 0.14), tw - 20, 3), T[3])
    kit.dither(b, (tx + 10, oy + int(h * 0.69), tw - 20, 3), T[1])
    # end cap + rivets
    pygame.draw.ellipse(b, T[1], (tx + tw - 26, oy + 2, 24, h - 4))
    pygame.draw.ellipse(b, T[3], (tx + tw - 26, oy + 2, 24, h - 4), 1)
    for ry in range(oy + 10, oy + h - 6, 12):
        b.fill(T[0], (tx + tw - 15, ry, 2, 2))
    # hoop bands
    for frac in (0.25, 0.5, 0.75):
        bx = tx + int(tw * frac)
        b.fill(T[0], (bx, oy + 4, 2, h - 9))
        b.fill(T[4], (bx + 2, oy + 4, 1, h - 9))
    # hazard diamonds with class "3"
    for hx in (tx + int(tw * 0.35), tx + int(tw * 0.65)):
        d = [(hx, oy + 10), (hx + 10, oy + 20), (hx, oy + 30), (hx - 10, oy + 20)]
        pygame.draw.polygon(b, P.HAZARD, d)
        pygame.draw.polygon(b, P.mix(P.HAZARD, P.INK, 0.8), d, 1)
        pygame.draw.line(b, P.mix(P.HAZARD, (255, 255, 220), 0.5), (hx - 8, oy + 20), (hx, oy + 12))
        kit.text(b, "3", hx - 2, oy + 17, (20, 16, 8), sy=1)
    cxm = tx + tw // 2
    _font_label(b, "IPA", cxm - kit.text_w("IPA", 1, 2) // 2, oy + 40, P.IPA_STENCIL, 2)
    _font_label(b, "FUEL", cxm - kit.text_w("FUEL") // 2, oy + 58, P.CREAM)
    # manifold: outlet flange, pipe, valve body + red hand-wheel, outlet 2
    M = P.ramp(P.MANIFOLD)
    y0 = oy + h - 3
    def flange(y):
        kit.rrect(b, M[1], (cxm - 11, y, 22, 6), 1)
        b.fill(M[3], (cxm - 10, y, 20, 1))
        for bx in (cxm - 8, cxm - 3, cxm + 3, cxm + 8):
            b.fill((20, 22, 24), (bx - 1, y + 2, 2, 2))
    b.fill(M[0], (cxm - 5, y0, 10, 17))
    b.fill(M[2], (cxm - 3, y0, 6, 17))
    b.fill(M[4], (cxm - 1, y0, 1, 17))
    flange(y0)
    vy = oy + h + 14
    kit.rrect(b, M[1], (cxm - 11, vy, 22, 16), 2)
    b.fill(M[3], (cxm - 10, vy + 1, 20, 1))
    V = P.ramp(P.VALVE_RED)
    pygame.draw.circle(b, V[1], (cxm, vy + 8), 10)
    pygame.draw.circle(b, V[3], (cxm, vy + 8), 10, 2)
    pygame.draw.circle(b, (30, 10, 8), (cxm, vy + 8), 8)
    for a in (0, 45, 90, 135):
        r = math.radians(a)
        pygame.draw.line(b, V[2], (cxm + int(2 * math.cos(r)), vy + 8 + int(2 * math.sin(r))),
                         (cxm + int(9 * math.cos(r)), vy + 8 + int(9 * math.sin(r))), 2)
    pygame.draw.circle(b, M[2], (cxm, vy + 8), 3)
    b.set_at((cxm - 1, vy + 7), M[4])
    y2 = vy + 16
    b.fill(M[0], (cxm - 5, y2, 10, 12))
    b.fill(M[2], (cxm - 3, y2, 6, 12))
    b.fill(M[4], (cxm - 1, y2, 1, 12))
    flange(y2 + 10)
    b = kit.outline(b)
    out.blit(b, (0, 0))
    return out


def build():
    sh = kit.Sheet("spr_vehicles", FAMILY, max_w=1400)
    sh.meta = {"facing": "east", "anchor": "collision-rect top-left",
               "smoulder_levels": list(SMOULDER_LEVELS),
               "smoulder_timing": "pick level from the procedural pulse 0.55+0.45*sin(...)",
               "car_sizes": [list(s) for s in CAR_SIZES],
               "paints": [n for n, _c in P.CAR_PAINTS]}
    for pi, (pname, paint) in enumerate(P.CAR_PAINTS):
        for (w, h) in CAR_SIZES:
            sh.add("car_%s_%dx%d" % (pname, w, h), car(paint, w, h), (PAD, PAD),
                   variant=pi, rect_size=[w, h])
            sh.add("burned_%s_%dx%d" % (pname, w, h), burned(paint, w, h, 9001 + pi * 131 + w * 7 + h),
                   (PAD, PAD), variant=pi, rect_size=[w, h], state="burned")
    for (w, h) in CAR_SIZES:
        for i, lv in enumerate(SMOULDER_LEVELS):
            sh.add("smoulder_%dx%d_%d" % (w, h, i), smoulder(w, h, lv), (PAD, PAD),
                   level=lv, overlay=True)
    sh.add("ipa_truck", ipa_truck(False), (PAD, PAD), rect_size=list(TRUCK))
    sh.add("ipa_truck_charred", ipa_truck(True, 7311), (PAD, PAD), rect_size=list(TRUCK), state="charred")
    for i, lv in enumerate(SMOULDER_LEVELS):
        sh.add("ipa_glow_%d" % i, ipa_glow(lv, 7312), (PAD, PAD), level=lv, overlay=True)
    sh.add("tanker", tanker(False), (PAD, PAD), rect_size=list(TANKER),
           dynamic="LED + fuel pool drawn procedurally on top")
    sh.add("tanker_wreck", tanker(True), (PAD, PAD), rect_size=list(TANKER), state="exploded")
    return [sh]


if __name__ == "__main__":
    sys.exit(kit.run(FAMILY, build))
