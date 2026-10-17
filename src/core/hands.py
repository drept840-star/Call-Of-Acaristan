
"""Canonical hand renderers - the reference-anatomy model (dorsal view).

Every hand in the game that is large enough to read (>= ~8 px) should be drawn
through this module so the anatomy stays consistent:

  * DORSAL staging: nails on the fingertips (elongated bed + pale free edge),
    knuckle ridge with MCP bumps, tendon lines down the back of the hand,
    webbing notches between the finger roots.
  * The thumb is a LONG, SPREAD, fully separate digit leaving the hand at
    ~45 degrees from the midboard edge at mid-hand height, with its own
    knuckle, nail and a webbing gap to the index. Never a wrist nub.
  * Fingers are three tapered phalanges with joint creases, splayed
    (index 4 deg, middle 0, ring 6, pinky 12) with webbing gaps.

Local frame for every renderer: origin at the wrist centre, -y toward the
fingertips, +x toward the THUMB (midboard) side. ``mirror`` flips +x to place
left/right hands; ``angle`` rotates the whole hand (radians-free, degrees).
"""
import math

import pygame

HAND_SKIN      = (151, 111, 82)
HAND_SKIN_HI   = (184, 137, 98)
HAND_SKIN_MID  = (128, 92, 68)
HAND_SKIN_SH   = (88, 59, 44)
HAND_NAIL      = (168, 124, 94)
HAND_NAIL_EDGE = (104, 70, 52)
HAND_NAIL_TIP  = (226, 190, 160)

_DEFAULT_PAL = {
    "skin": HAND_SKIN, "hi": HAND_SKIN_HI, "mid": HAND_SKIN_MID,
    "sh": HAND_SKIN_SH, "nail": HAND_NAIL, "nail_edge": HAND_NAIL_EDGE,
    "nail_tip": HAND_NAIL_TIP,
}

# (midboard offset, length, base width, splay deg) - index..pinky
_FINGER_SPECS = ((23, 50, 11, 4), (8, 57, 11, 0), (-8, 52, 10, 6), (-23, 42, 9, 12))


def _capsule(s, p1, p2, w, col):
    pygame.draw.line(s, col, (int(round(p1[0])), int(round(p1[1]))),
                     (int(round(p2[0])), int(round(p2[1]))), max(1, int(round(w))))
    r = int(round(w / 2))
    pygame.draw.circle(s, col, (int(round(p1[0])), int(round(p1[1]))), r)
    pygame.draw.circle(s, col, (int(round(p2[0])), int(round(p2[1]))), r)


def _xf(wrist, angle, mirror, sc):
    ca, sa = math.cos(math.radians(angle)), math.sin(math.radians(angle))
    wx, wy = wrist

    def P(lx, ly):
        x = lx * mirror * sc
        y = ly * sc
        return (wx + x * ca - y * sa, wy + x * sa + y * ca)
    return P


def open_hand_dorsal(surface, wrist, angle=0.0, mirror=1, sc=1.0, spread=1.0,
                     trem=0, pal=None, rim=None, curl=0.0):
    """Open hand, back of the hand toward the camera (the reference pose).

    ``curl`` (0..1) closes the hand toward a grip. In a dorsal view a flexed
    finger foreshortens rather than swinging sideways, so curling shortens the
    visible phalanges, tightens the splay and fattens the knuckle/PIP bulges -
    which is what separates "holding an edge" from jazz hands. Default 0 keeps
    every existing call site pixel-identical.
    """
    p = dict(_DEFAULT_PAL)
    if pal:
        p.update(pal)
    P = _xf(wrist, angle, mirror, sc)
    out = -mirror  # splay direction (away from midboard)

    # ── back of hand ──
    fingers = []
    base_y = -40.0
    ln_mul = 1.0 - 0.40 * curl
    spread_mul = spread * (1.0 - 0.55 * curl)
    for off, ln, w, splay in _FINGER_SPECS:
        bx = off * (1.0 - 0.18 * curl)
        ln = ln * ln_mul
        a = math.radians(splay * spread_mul) * out
        d = (math.sin(a), -math.cos(a))
        j1 = (bx + d[0] * ln * 0.42, base_y + d[1] * ln * 0.42)
        a2 = a + math.radians(3.0) * out
        d2 = (math.sin(a2), -math.cos(a2))
        j2 = (j1[0] + d2[0] * ln * 0.33, j1[1] + d2[1] * ln * 0.33)
        tip = (j2[0] + d2[0] * ln * 0.25 + trem * out * 0.5,
               j2[1] + d2[1] * ln * 0.25)
        fingers.append(((bx, base_y), j1, j2, tip, w))
    kx = [f[0][0] for f in fingers]
    hand_poly = [(-32, -2), (-35, -24), (min(kx) - 8, -37), (min(kx) - 6, -44),
                 (max(kx) + 6, -44), (max(kx) + 8, -37), (35, -24), (32, -2)]
    pygame.draw.polygon(surface, p["sh"], [P(*q) for q in hand_poly])
    inner = [(q[0], q[1] + 1) for q in hand_poly[1:-1]] + [hand_poly[-1], hand_poly[0]]
    pygame.draw.polygon(surface, p["skin"], [P(*q) for q in inner])
    # knuckle ridge + MCP bumps + tendons + webbing notches
    pygame.draw.line(surface, p["mid"], P(min(kx) - 2, -41), P(max(kx) + 2, -41), max(1, int(sc)))
    for f in fingers:
        pygame.draw.arc(surface, p["mid"],
                        pygame.Rect(P(f[0][0] - 4, f[0][1] - 7), (int(9 * sc), int(8 * sc))),
                        math.radians(200), math.radians(340), 1)
        pygame.draw.circle(surface, p["hi"], (int(P(f[0][0] - 1, f[0][1] - 4)[0]),
                                              int(P(f[0][0] - 1, f[0][1] - 4)[1])), 1)
    for off in (16, 0, -16):
        pygame.draw.line(surface, p["mid"], P(off, -10), P(off + mirror * 2, -34), 1)
    for i in range(3):
        wx_ = (fingers[i][0][0] + fingers[i + 1][0][0]) / 2
        pygame.draw.arc(surface, p["sh"],
                        pygame.Rect(P(wx_ - 5, -44), (int(10 * sc), int(10 * sc))),
                        math.radians(200), math.radians(340), 1)
    # ulna bump
    pygame.draw.circle(surface, p["hi"], (int(P(out * 28, -6)[0]), int(P(out * 28, -6)[1])), 2)

    # ── thumb: long, spread ~45 deg, own knuckle + nail, webbing gap ──
    tk = 1.0 - 0.30 * curl          # a gripping thumb closes, it does not splay
    t0 = P(23, -17)
    t1 = P(23 + 19 * tk, -17 - 17 * tk)
    t2 = P(23 + 27 * tk, -17 - 30 * tk + trem)
    pygame.draw.ellipse(surface, p["skin"],
                        pygame.Rect(P(14, -26), (int(22 * sc), int(20 * sc))))
    pygame.draw.arc(surface, p["sh"],
                    pygame.Rect(P(13, -24), (int(24 * sc), int(22 * sc))),
                    math.radians(10), math.radians(120), 1)
    _capsule(surface, t0, t1, (10 + 2 * curl) * sc, p["sh"])
    _capsule(surface, t0, t1, (8 + 2 * curl) * sc, p["skin"])
    _capsule(surface, t1, t2, (8 + 2 * curl) * sc, p["sh"])
    _capsule(surface, t1, t2, (6 + 2 * curl) * sc, p["skin"])
    pygame.draw.circle(surface, p["hi"], (int(t1[0]), int(t1[1] - 1)), max(1, int(2 * sc)))
    pygame.draw.ellipse(surface, p["nail"], (int(t2[0] - 2 * sc), int(t2[1] - 2 * sc),
                                             int(5 * sc), int(6 * sc)))
    pygame.draw.arc(surface, p["nail_edge"],
                    (int(t2[0] - 3 * sc), int(t2[1] - 2 * sc), int(7 * sc), int(7 * sc)),
                    math.radians(200), math.radians(340), 1)
    pygame.draw.arc(surface, p["sh"],
                    pygame.Rect(P(12, -38), (int(26 * sc), int(22 * sc))),
                    math.radians(200), math.radians(340), 1)

    # ── fingers: 3 phalanges, creases, dorsal nails with pale free edge ──
    for (b, j1, j2, tip, w) in fingers:
        b = P(*b); j1 = P(*j1); j2 = P(*j2); tip = P(*tip)
        _capsule(surface, b, j1, (w + 2) * sc, p["sh"])
        _capsule(surface, j1, j2, w * sc, p["sh"])
        _capsule(surface, j2, tip, (w - 2) * sc, p["sh"])
        _capsule(surface, b, j1, w * sc, p["skin"])
        _capsule(surface, j1, j2, (w - 2) * sc, p["skin"])
        _capsule(surface, j2, tip, (w - 4) * sc, p["skin"])
        pygame.draw.line(surface, p["hi"], (b[0] - 1, b[1] - 3), (j1[0] - 1, j1[1] - 1), 1)
        pygame.draw.line(surface, p["hi"], (j1[0] - 1, j1[1] - 3), (j2[0] - 1, j2[1] - 1), 1)
        bw = 7 + 3 * curl
        for j in (j1, j2):
            pygame.draw.arc(surface, p["mid"], (int(j[0] - bw * sc / 2), int(j[1] - 2 * sc),
                                                int(bw * sc), int(5 * sc)),
                            math.radians(15), math.radians(165), 1)
        nw = max(4, w - 5) * sc
        pygame.draw.ellipse(surface, p["nail"], (int(tip[0] - nw / 2), int(tip[1] - 2 * sc),
                                                 int(nw), int(7 * sc)))
        pygame.draw.arc(surface, p["nail_edge"],
                        (int(tip[0] - nw / 2 - 1), int(tip[1] - 2 * sc), int(nw + 2), int(8 * sc)),
                        math.radians(200), math.radians(340), 1)
        pygame.draw.line(surface, p["nail_tip"],
                         (int(tip[0] - nw / 2 + 1), int(tip[1] - 1)),
                         (int(tip[0] + nw / 2 - 1), int(tip[1] - 1)), 1)
        if rim:
            pygame.draw.arc(surface, rim,
                            (int(tip[0] - w * sc / 2 + 1), int(tip[1] - w * sc / 2 + 1),
                             int(w * sc - 2), int(w * sc - 2)),
                            math.radians(230), math.radians(310), 1)
    # inter-finger occlusion
    for i in range(3):
        a = fingers[i][3]; b = fingers[i + 1][3]
        x0 = (fingers[i][0][0] + fingers[i + 1][0][0]) / 2
        y0 = base_y + 9
        x1 = (a[0] + b[0]) / 2; y1 = (a[1] + b[1]) / 2 + 16
        pygame.draw.line(surface, p["sh"], P(x0, y0), P(x1, y1), max(1, int(2 * sc)))
    return fingers


def grip_hand(surface, wrist, axis=90.0, mirror=1, sc=1.0, curl=1.0, yank=0.0,
              grip_d=24, pal=None, cuff=False, cuff_col=None, chain_dir=None):
    """Clenched fist wrapped around a tube/handle whose axis is ``axis`` deg."""
    p = dict(_DEFAULT_PAL)
    if pal:
        p.update(pal)
    cuff_col = cuff_col or ((42, 40, 36), (60, 56, 50))
    a = math.radians(axis)
    ux, uy = math.cos(a), math.sin(a)
    px, py = -uy * mirror, ux * mirror
    wx, wy = wrist
    bx, by = wx + px * 10 * sc, wy + py * 10 * sc
    bw, bh = 13 * sc, 15 * sc
    quad = [(bx - ux * bw + px * bh * 0.5, by - uy * bw + py * bh * 0.5),
            (bx + ux * bw + px * bh * 0.5, by + uy * bw + py * bh * 0.5),
            (bx + ux * bw - px * bh, by + uy * bw - py * bh),
            (bx - ux * bw - px * bh, by - uy * bw - py * bh)]
    pygame.draw.polygon(surface, p["sh"], quad)
    pygame.draw.polygon(surface, p["skin"],
                        [(_lerp(q[0], bx, 0.14), _lerp(q[1], by, 0.14)) for q in quad])
    kn = (int(_lerp(p["skin"][0], 240, yank)), int(_lerp(p["skin"][1], 230, yank)),
          int(_lerp(p["skin"][2], 208, yank)))
    cross = grip_d * 0.62 * sc
    for i in range(4):
        off = (-10.5 + 7 * i) * sc
        root = (bx + ux * off - px * bh * 0.55, by + uy * off - py * bh * 0.55)
        mid = (root[0] - px * cross, root[1] - py * cross)
        tip = (mid[0] + ux * 2 * sc + px * 5 * sc * curl, mid[1] + uy * 2 * sc + py * 5 * sc * curl)
        w0 = (7.5 - i * 0.45) * sc
        _capsule(surface, root, mid, w0, p["sh"])
        _capsule(surface, root, mid, w0 - 2 * sc, p["skin"])
        _capsule(surface, mid, tip, w0 - 3 * sc, p["sh"])
        _capsule(surface, mid, tip, w0 - 4 * sc, p["skin"])
        pygame.draw.circle(surface, kn, (int(root[0] + px), int(root[1] + py)), int(3.4 * sc))
        # dorsal nail on the curled middle phalanx
        pygame.draw.ellipse(surface, p["nail"],
                            (int(mid[0] - 2 * sc), int(mid[1] - 2.5 * sc), int(4 * sc), int(3 * sc)))
        pygame.draw.line(surface, p["sh"], (int(mid[0] - ux * 2), int(mid[1] - uy * 2)),
                         (int(mid[0] + ux * 2), int(mid[1] + uy * 2)), 1)
    t0 = (bx - ux * 12 * sc - px * 2 * sc, by - uy * 12 * sc - py * 2 * sc)
    t1 = (t0[0] - px * 10 * sc + ux * 4 * sc, t0[1] - py * 10 * sc + uy * 4 * sc)
    t2 = (t1[0] + ux * 9 * sc, t1[1] + uy * 9 * sc)
    _capsule(surface, t0, t1, 8 * sc, p["sh"])
    _capsule(surface, t0, t1, 6 * sc, p["skin"])
    _capsule(surface, t1, t2, 5.5 * sc, p["sh"])
    _capsule(surface, t1, t2, 4 * sc, p["skin"])
    pygame.draw.ellipse(surface, p["nail"], (int(t2[0] - 2 * sc), int(t2[1] - 2 * sc),
                                             int(4 * sc), int(3 * sc)))
    if cuff:
        c0 = (wx - px * 5 * sc, wy - py * 5 * sc)
        pygame.draw.line(surface, cuff_col[0], (c0[0] - ux * 5 * sc, c0[1] - uy * 5 * sc),
                         (c0[0] + ux * 5 * sc, c0[1] + uy * 5 * sc), int(8 * sc))
        pygame.draw.line(surface, cuff_col[1], (c0[0] - ux * 5 * sc, c0[1] - uy * 5 * sc - 2),
                         (c0[0] + ux * 5 * sc, c0[1] + uy * 5 * sc - 2), 1)
    if chain_dir:
        ex, ey = chain_dir
        n = max(2, int(math.hypot(ex - wx, ey - wy) // 11))
        for k in range(n):
            u = (k + 1) / (n + 1)
            lx, ly = _lerp(wx, ex, u), _lerp(wy, ey, u) + math.sin(k * 1.9) * 2
            r = pygame.Rect(int(lx - 4), int(ly - 3), 8, 6)
            pygame.draw.ellipse(surface, (45, 45, 45), r, 2)
            pygame.draw.ellipse(surface, (112, 108, 96), r, 1)


def point_hand(surface, wrist, angle=0.0, mirror=1, sc=1.0, pal=None):
    """Pointing hand: index extended, other fingers curled, thumb spread."""
    p = dict(_DEFAULT_PAL)
    if pal:
        p.update(pal)
    P = _xf(wrist, angle, mirror, sc)
    # back of hand (shorter than open pose)
    poly = [(-26, 0), (-28, -18), (-20, -30), (20, -30), (28, -18), (26, 0)]
    pygame.draw.polygon(surface, p["sh"], [P(*q) for q in poly])
    pygame.draw.polygon(surface, p["skin"],
                        [P(*q) for q in poly[1:-1]] + [P(*poly[-1]), P(*poly[0])])
    pygame.draw.line(surface, p["mid"], P(-18, -28), P(18, -28), max(1, int(sc)))
    for off in (10, 0, -10):
        pygame.draw.line(surface, p["mid"], P(off, -6), P(off, -24), 1)
    # index: straight, two creases, nail
    i0, i1, i2 = P(16, -30), P(18, -52), P(19, -70)
    _capsule(surface, i0, i1, 9 * sc, p["sh"])
    _capsule(surface, i0, i1, 7 * sc, p["skin"])
    _capsule(surface, i1, i2, 7 * sc, p["sh"])
    _capsule(surface, i1, i2, 5 * sc, p["skin"])
    pygame.draw.arc(surface, p["mid"], (int(i1[0] - 3 * sc), int(i1[1] - 2 * sc),
                                        int(7 * sc), int(5 * sc)),
                    math.radians(15), math.radians(165), 1)
    pygame.draw.ellipse(surface, p["nail"], (int(i2[0] - 2.5 * sc), int(i2[1] - 2 * sc),
                                             int(5 * sc), int(6 * sc)))
    pygame.draw.line(surface, p["nail_tip"], (int(i2[0] - 2 * sc), int(i2[1] - 1)),
                     (int(i2[0] + 2 * sc), int(i2[1] - 1)), 1)
    # curled middle/ring/pinky: folded caps with nail dots
    for k, off in enumerate((4, -6, -16)):
        c0 = P(off, -30)
        c1 = P(off - 2, -40 - (1 if k == 0 else 0) * 3)
        w = (9 - k) * sc
        _capsule(surface, c0, c1, w, p["sh"])
        _capsule(surface, c0, c1, w - 2 * sc, p["skin"])
        pygame.draw.ellipse(surface, p["nail"], (int(c1[0] - 2 * sc), int(c1[1] - 2 * sc),
                                                 int(4 * sc), int(4 * sc)))
        pygame.draw.arc(surface, p["sh"], (int(c1[0] - 4 * sc), int(c1[1] - 1),
                                           int(8 * sc), int(6 * sc)),
                        math.radians(200), math.radians(340), 1)
    # spread thumb
    t0, t1, t2 = P(24, -14), P(36, -24), P(43, -34)
    _capsule(surface, t0, t1, 9 * sc, p["sh"])
    _capsule(surface, t0, t1, 7 * sc, p["skin"])
    _capsule(surface, t1, t2, 7 * sc, p["sh"])
    _capsule(surface, t1, t2, 5 * sc, p["skin"])
    pygame.draw.ellipse(surface, p["nail"], (int(t2[0] - 2 * sc), int(t2[1] - 2 * sc),
                                             int(4 * sc), int(5 * sc)))
    pygame.draw.arc(surface, p["sh"], (int(P(10, -22)[0]), int(P(10, -22)[1]),
                                       int(20 * sc), int(16 * sc)),
                    math.radians(200), math.radians(340), 1)


def _lerp(a, b, u):
    return a + (b - a) * u
