
"""props.py - shared set-dressing prop painters.

Promoted from missions/m3/draw.py during the Mission 1/2 graphics upgrade.
Every painter tries the loaded-art tier first (``core.artpack``) and falls
back to the project's flat-vector procedural look, so a bare install still
renders the same shapes with less shading.

Unlike the Mission 3 originals (which draw to the module-global ``screen``
and rely on the bake-time screen swap), these take an explicit ``surf`` so
bake callbacks and per-frame passes share one implementation.
"""

import math

import pygame

from core import artpack


def _soft_shadow(surf, rect, alpha=70):
    """Contact shadow that stays soft on opaque bake chunks.

    Per-pixel alpha drawn directly onto an opaque surface is discarded, so
    an (0,0,0) ellipse would bake as a solid black blob.  Draw into a small
    SRCALPHA temp and blit instead (house pattern, cf. desks in m1/draw.py).
    """
    r = pygame.Rect(rect)
    if r.w <= 0 or r.h <= 0:
        return
    t = pygame.Surface((r.w, r.h), pygame.SRCALPHA)
    pygame.draw.ellipse(t, (0, 0, 0, alpha), (0, 0, r.w, r.h))
    surf.blit(t, r.topleft)


def _grad_rect(surf, rect, c_top, c_bot, horiz=False):
    """Fill rect with a 2-tone vertical (or horizontal) step gradient."""
    r = pygame.Rect(rect)
    if r.w <= 0 or r.h <= 0:
        return
    if horiz:
        for x in range(r.w):
            t = x / max(1, r.w - 1)
            col = tuple(int(c_top[i] + (c_bot[i] - c_top[i]) * t) for i in range(3))
            pygame.draw.line(surf, col, (r.x + x, r.y), (r.x + x, r.bottom - 1))
    else:
        for y in range(r.h):
            t = y / max(1, r.h - 1)
            col = tuple(int(c_top[i] + (c_bot[i] - c_top[i]) * t) for i in range(3))
            pygame.draw.line(surf, col, (r.x, r.y + y), (r.right - 1, r.y + y))


def _hi(surf, x1, y1, x2, y2, col, w=1):
    pygame.draw.line(surf, col, (int(x1), int(y1)), (int(x2), int(y2)), w)


# Colour maths mirroring tools/make_art_pack.py, so the procedural fallbacks
# can reuse the exact art-tier values and the two tiers stay in step.
def _mix(c1, c2, f):
    """Solid stand-in for 'c2 at alpha f over c1'."""
    return tuple(int(c1[i] + (c2[i] - c1[i]) * f) for i in range(3))


def _shade(c, f):
    return tuple(max(0, min(255, int(v * f))) for v in c[:3])


def _lit(c, f):
    return tuple(max(0, min(255, int(v + (255 - v) * f))) for v in c[:3])


def crate_stack(surf, sx, sy, scale=1.0, shadow=True):
    """Set-dressing crates/pallets for empty background space."""
    s = scale
    spr = artpack.get("prop_crate")
    if spr is not None and shadow:
        if s != 1.0:
            spr = pygame.transform.smoothscale(spr, (int(96 * s), int(96 * s)))
        surf.blit(spr, (int(sx - 48 * s), int(sy - 44 * s)))
        return
    OUT = (36, 26, 16)
    if shadow:
        _soft_shadow(surf, (int(sx - 30 * s), int(sy + 16 * s), int(84 * s), int(16 * s)))

    def crate(cx, cy, cw, ch, base, brace=True, stencil=False):
        r = pygame.Rect(int(cx), int(cy), int(cw), int(ch))
        top = tuple(min(255, c + 26) for c in base)
        bot = tuple(max(0, c - 22) for c in base)
        _grad_rect(surf, r, top, bot)
        pygame.draw.rect(surf, OUT, r, 1)
        # plank seams + lit lip under each seam
        for fy in (0.36, 0.68):
            yy = r.y + int(r.h * fy)
            _hi(surf, r.x + 1, yy, r.right - 2, yy, tuple(max(0, c - 30) for c in base))
            _hi(surf, r.x + 1, yy + 1, r.right - 2, yy + 1,
                tuple(min(255, c + 14) for c in base))
        # top face highlight
        _hi(surf, r.x + 1, r.y + 1, r.right - 2, r.y + 1,
            tuple(min(255, c + 44) for c in base))
        if brace:
            pygame.draw.line(surf, tuple(min(255, c + 10) for c in base),
                             (r.x + 2, r.y + 2), (r.right - 3, r.bottom - 3), 2)
            pygame.draw.line(surf, OUT, (r.x + 2, r.y + 3), (r.right - 3, r.bottom - 2), 1)
        if stencil:
            sr = pygame.Rect(r.right - int(9 * s) - 2, r.y + 3, int(9 * s), int(6 * s))
            pygame.draw.rect(surf, (52, 40, 26), sr)
            _hi(surf, sr.x + 1, sr.centery, sr.right - 2, sr.centery, (120, 96, 60))

    # pallet: deck boards + stringer gaps
    pr = pygame.Rect(int(sx - 28 * s), int(sy + 14 * s), int(72 * s), int(7 * s))
    _grad_rect(surf, pr, (86, 66, 40), (58, 44, 26))
    pygame.draw.rect(surf, OUT, pr, 1)
    for fx in (0.3, 0.62):
        xx = pr.x + int(pr.w * fx)
        _hi(surf, xx, pr.y + 1, xx, pr.bottom - 2, (40, 30, 18))
    crate(sx - 26 * s, sy - 8 * s, 30 * s, 23 * s, (92, 68, 40), True, True)
    crate(sx + 5 * s, sy - 12 * s, 28 * s, 27 * s, (82, 62, 38), True, False)
    crate(sx - 9 * s, sy - 36 * s, 26 * s, 24 * s, (104, 78, 46), False, True)
    # strap on the top crate
    _hi(surf, sx - 9 * s + 8 * s, sy - 35 * s, sx - 9 * s + 8 * s, sy - 13 * s, (48, 38, 24), 2)


def barrels(surf, sx, sy, count=3, shadow=True):
    spr = artpack.get("prop_barrels")
    if spr is not None and shadow:
        n = max(1, int(count))
        if n >= 3:
            surf.blit(spr, (int(sx - 10), int(sy - 14)))
        else:
            w = 42 if n <= 1 else 74
            surf.blit(spr, (int(sx - 10), int(sy - 14)), area=(0, 0, w, 64))
        return
    # Procedural fallback - mirrors the art-tier geometry (sprite origin is
    # sx-10, sy-14) so both tiers read identically and match FOOTPRINTS.
    HUES = ((86, 96, 88), (74, 86, 98), (98, 78, 56))
    ox, oy = int(sx - 10), int(sy - 14)
    drums = ((8, 30), (38, 32), (68, 26))[:max(1, int(count))]
    for i, (bx, bw) in enumerate(drums):
        base = HUES[i % 3]
        if shadow:
            _soft_shadow(surf, (ox + bx - 2, oy + 58, bw + 4, 8), 70)
        body = pygame.Rect(ox + bx, oy + 12, bw, 48)
        _grad_rect(surf, body, _lit(base, 0.34), _shade(base, 0.52), horiz=True)
        pygame.draw.rect(surf, (22, 26, 24), body, 1)
        # specular band down the lit third + deep shade on the right edge
        hx = body.x + int(bw * 0.28)
        _hi(surf, hx, body.y + 2, hx, body.bottom - 3, _lit(base, 0.62), 2)
        _hi(surf, hx + 3, body.y + 3, hx + 3, body.bottom - 4, _lit(base, 0.42), 1)
        _hi(surf, body.right - 2, body.y + 1, body.right - 2, body.bottom + 2,
            _shade(base, 0.36), 2)
        # top rim: lit lip over a dark inner well, then the bung
        pygame.draw.ellipse(surf, _lit(base, 0.5), (ox + bx, oy + 7, bw, 10))
        pygame.draw.ellipse(surf, (22, 26, 24), (ox + bx, oy + 7, bw, 10), 1)
        pygame.draw.ellipse(surf, _shade(base, 0.45),
                            (ox + bx + 3, oy + 8, bw - 6, 7))
        pygame.draw.ellipse(surf, (18, 21, 20),
                            (ox + bx + 5, oy + 9, bw - 10, 5))
        pygame.draw.circle(surf, (30, 34, 32), (ox + bx + bw - 7, oy + 11), 2)
        pygame.draw.circle(surf, _lit(base, 0.3),
                           (ox + bx + bw - 7, oy + 11), 2, 1)
        # rolling hoops: dark band + lit lip
        for ry in (25, 41):
            _hi(surf, body.x + 1, oy + ry, body.right - 2, oy + ry,
                _shade(base, 0.42), 3)
            _hi(surf, body.x + 1, oy + ry + 3, body.right - 2, oy + ry + 3,
                _lit(base, 0.4), 1)
        # grime streak
        _hi(surf, body.x + 5, oy + 16, body.x + 5, oy + 56,
            _mix(base, (110, 66, 38), 0.5), 1)


def cable_coil(surf, sx, sy, shadow=True):
    spr = artpack.get("prop_coil")
    if spr is not None and shadow:
        surf.blit(spr, (int(sx - 32), int(sy - 36)))
        return
    # Procedural fallback - mirrors the art-tier coil (sprite origin sx-32,
    # sy-36).  Concentric RINGS rather than stacked discs: the old version
    # painted a dark disc over a dark floor and read as a tyre.
    ox, oy = int(sx - 32), int(sy - 36)
    cx, cy = ox + 32, oy + 32
    if shadow:
        _soft_shadow(surf, (cx - 24, oy + 49, 48, 12), 70)
    RUBBER = (54, 51, 44)
    RUBBER_DK = (26, 25, 22)
    LIT = (152, 148, 128)
    LIT_HOT = (198, 194, 170)
    for r in (21, 15, 9):
        pygame.draw.circle(surf, RUBBER_DK, (cx, cy), r, 6)
        pygame.draw.circle(surf, RUBBER, (cx, cy), r, 4)
        box = (cx - r, cy - r, r * 2, r * 2)
        # lit crown (top-left) + hot specular, shaded underside (bottom-right)
        pygame.draw.arc(surf, LIT, box, math.radians(100), math.radians(205), 2)
        pygame.draw.arc(surf, LIT_HOT, box, math.radians(133), math.radians(178), 1)
        pygame.draw.arc(surf, (17, 16, 14), box,
                        math.radians(-25), math.radians(70), 2)
    # Strap holding the bundle together.
    a = math.radians(28)
    dx, dy = math.cos(a) * 24, math.sin(a) * 24
    _hi(surf, cx - dx, cy - dy, cx + dx, cy + dy, (62, 58, 46), 5)
    _hi(surf, cx - dx, cy - dy - 1, cx + dx, cy + dy - 1, (104, 98, 78), 1)
    # Loose tail curling out to a plug.
    pygame.draw.lines(surf, (46, 44, 38), False,
                      [(cx + 19, cy + 11), (cx + 28, cy + 19),
                       (cx + 25, cy + 27)], 3)
    pygame.draw.circle(surf, (34, 33, 30), (cx + 25, cy + 28), 3)
    pygame.draw.circle(surf, (124, 120, 102), (cx + 25, cy + 28), 1)


def mop_bucket(surf, sx, sy, shadow=True):
    spr = artpack.get("prop_mop")
    if spr is not None and shadow:
        surf.blit(spr, (int(sx - 20), int(sy - 42)))
        return
    # Procedural fallback - mirrors the art-tier mop (sprite origin sx-20,
    # sy-42).  The old mop was a 3px handle plus hairlines, which read as a
    # bare stick at gameplay scale.
    ox, oy = int(sx - 20), int(sy - 42)
    if shadow:
        _soft_shadow(surf, (ox + 6, oy + 55, 36, 10), 70)
    body = (58, 66, 72)
    pts = [(ox + 6, oy + 26), (ox + 42, oy + 26),
           (ox + 38, oy + 58), (ox + 10, oy + 58)]
    pygame.draw.polygon(surf, body, pts)
    pygame.draw.polygon(surf, (22, 26, 30), pts, 1)
    _hi(surf, ox + 9, oy + 29, ox + 12, oy + 56, _lit(body, 0.4), 3)
    _hi(surf, ox + 39, oy + 29, ox + 36, oy + 56, _shade(body, 0.62), 2)
    # rim + water + glint
    pygame.draw.ellipse(surf, _lit(body, 0.46), (ox + 5, oy + 22, 38, 9))
    pygame.draw.ellipse(surf, (22, 26, 30), (ox + 5, oy + 22, 38, 9), 1)
    pygame.draw.ellipse(surf, (32, 44, 46), (ox + 9, oy + 23, 30, 6))
    pygame.draw.arc(surf, (128, 158, 158), (ox + 12, oy + 23, 14, 5),
                    math.radians(200), math.radians(320), 1)
    # wringer basket
    pygame.draw.rect(surf, (76, 84, 86), (ox + 25, oy + 14, 17, 11),
                     border_radius=1)
    pygame.draw.rect(surf, (28, 32, 36), (ox + 25, oy + 14, 17, 11), 1,
                     border_radius=1)
    for gx in (29, 33, 37):
        _hi(surf, ox + gx, oy + 16, ox + gx, oy + 24, (44, 50, 52))
    # mop: thick handle, ferrule band, tapered head bundle
    _hi(surf, ox + 34, oy + 15, ox + 46, oy, (96, 72, 42), 5)
    _hi(surf, ox + 33, oy + 15, ox + 45, oy, (172, 136, 88), 2)
    _hi(surf, ox + 29, oy + 23, ox + 37, oy + 17, (152, 152, 146), 4)
    head = [(ox + 28, oy + 21), (ox + 39, oy + 17), (ox + 42, oy + 29),
            (ox + 34, oy + 40), (ox + 25, oy + 33)]
    pygame.draw.polygon(surf, (132, 124, 96), head)
    pygame.draw.polygon(surf, (84, 78, 58), head, 1)
    for i in range(5):
        t = i / 4.0
        _hi(surf, ox + 29 + t * 8, oy + 21 + t * 2,
            ox + 27 + t * 12, oy + 35 + t * 3, (158, 150, 120))


def service_cart(surf, sx, sy, shadow=True):
    spr = artpack.get("prop_cart")
    if spr is not None and shadow:
        surf.blit(spr, (int(sx - 44), int(sy - 30)))
        return
    if shadow:
        _soft_shadow(surf, (int(sx - 34), int(sy + 18), int(76), int(13)))
    # posts
    for px in (sx - 30, sx + 27):
        pygame.draw.rect(surf, (66, 72, 74), (int(px), int(sy - 12), 3, 30))
        pygame.draw.line(surf, (104, 112, 112), (int(px), int(sy - 12)), (int(px), int(sy + 17)))
    # shelves
    top = pygame.Rect(int(sx - 33), int(sy - 12), 66, 7)
    _grad_rect(surf, top, (84, 92, 92), (52, 58, 58))
    pygame.draw.rect(surf, (26, 30, 30), top, 1)
    low = pygame.Rect(int(sx - 31), int(sy + 6), 62, 6)
    _grad_rect(surf, low, (70, 76, 76), (44, 50, 50))
    pygame.draw.rect(surf, (26, 30, 30), low, 1)
    # lip rail on the top shelf
    _hi(surf, sx - 33, sy - 15, sx + 33, sy - 15, (92, 100, 100))
    for lx in (sx - 33, sx - 11, sx + 11, sx + 32):
        _hi(surf, lx, sy - 15, lx, sy - 12, (72, 80, 80))
    # load: folded linen stack, spray bottle, small crate
    pygame.draw.rect(surf, (96, 104, 98), (int(sx - 26), int(sy - 18), 16, 6), border_radius=1)
    pygame.draw.rect(surf, (78, 88, 84), (int(sx - 25), int(sy - 21), 14, 4), border_radius=1)
    pygame.draw.rect(surf, (58, 78, 88), (int(sx - 4), int(sy - 20), 5, 8), border_radius=1)
    pygame.draw.rect(surf, (40, 56, 64), (int(sx - 3), int(sy - 23), 3, 3))
    pygame.draw.rect(surf, (88, 70, 46), (int(sx + 8), int(sy - 19), 12, 7), border_radius=1)
    pygame.draw.rect(surf, (48, 36, 22), (int(sx + 8), int(sy - 19), 12, 7), 1, border_radius=1)
    # lower shelf: bucket silhouette
    pygame.draw.rect(surf, (54, 60, 62), (int(sx - 12), int(sy), 12, 6), border_radius=1)
    # handle bar
    pygame.draw.line(surf, (96, 104, 104), (int(sx + 30), int(sy - 14)), (int(sx + 36), int(sy - 14)), 2)
    pygame.draw.line(surf, (96, 104, 104), (int(sx + 36), int(sy - 14)), (int(sx + 36), int(sy + 2)), 2)
    # casters
    for wx in (sx - 24, sx + 22):
        pygame.draw.rect(surf, (52, 56, 56), (int(wx) - 1, int(sy + 14), 3, 4))
        pygame.draw.circle(surf, (14, 14, 14), (int(wx), int(sy + 20)), 4)
        pygame.draw.circle(surf, (72, 72, 68), (int(wx), int(sy + 20)), 1)


def wall_pipe(surf, x1, y1, x2, y2, color=(54, 56, 52)):
    ph = artpack.get("pipe_h")
    pv = artpack.get("pipe_v")
    if ph is not None and pv is not None and (x1 == x2 or y1 == y2):
        if y1 == y2:
            x0, xe = int(min(x1, x2)), int(max(x1, x2))
            for xx in range(x0, xe, 64):
                rem = xe - xx
                if rem >= 64:
                    surf.blit(ph, (xx, int(y1 - 8)))
                else:
                    surf.blit(ph, (xx, int(y1 - 8)), area=(0, 0, rem, 16))
        else:
            y0, ye = int(min(y1, y2)), int(max(y1, y2))
            for yy in range(y0, ye, 64):
                rem = ye - yy
                if rem >= 64:
                    surf.blit(pv, (int(x1 - 8), yy))
                else:
                    surf.blit(pv, (int(x1 - 8), yy), area=(0, 0, 16, rem))
        return
    horiz = y1 == y2
    dist = max(1, int(math.hypot(x2 - x1, y2 - y1)))
    # body: dark base, lit core line, shadow line
    pygame.draw.line(surf, (24, 24, 22), (int(x1), int(y1 + 3)), (int(x2), int(y2 + 3)), 6 if horiz else 6)
    pygame.draw.line(surf, color, (int(x1), int(y1)), (int(x2), int(y2)), 5)
    pygame.draw.line(surf, (96, 100, 92), (int(x1), int(y1 - 1)), (int(x2), int(y2 - 1)), 1)
    pygame.draw.line(surf, (30, 30, 28), (int(x1), int(y1 + 2)), (int(x2), int(y2 + 2)), 1)
    # couplings + bracket tabs
    for k in range(24, dist, 64):
        q = k / dist
        px = x1 + (x2 - x1) * q
        py = y1 + (y2 - y1) * q
        if horiz:
            pygame.draw.rect(surf, (74, 78, 70), (int(px - 3), int(py - 4), 6, 9), border_radius=1)
            pygame.draw.rect(surf, (26, 26, 24), (int(px - 3), int(py - 4), 6, 9), 1, border_radius=1)
            pygame.draw.circle(surf, (30, 30, 28), (int(px), int(py + 6)), 2)
        else:
            pygame.draw.rect(surf, (74, 78, 70), (int(px - 4), int(py - 3), 9, 6), border_radius=1)
            pygame.draw.rect(surf, (26, 26, 24), (int(px - 4), int(py - 3), 9, 6), 1, border_radius=1)
            pygame.draw.circle(surf, (30, 30, 28), (int(px + 6), int(py)), 2)
    # end flanges
    for ex, ey in ((x1, y1), (x2, y2)):
        if horiz:
            pygame.draw.rect(surf, (70, 74, 68), (int(ex - 2), int(ey - 5), 4, 11), border_radius=1)
        else:
            pygame.draw.rect(surf, (70, 74, 68), (int(ex - 5), int(ey - 2), 11, 4), border_radius=1)


# Drawn footprint (dx, dy, w, h in px, relative to the prop anchor) of every
# set-dressing prop. Unions the art-sprite blit rect with the procedural
# fallback extents, so placement can be validated against the tilemap before
# drawing regardless of which tier renders.
#
# Art reference (blit offsets in the painters above):
#   crates: 96x96 PNG at (sx-48a, sy-44a); procedural pallet reaches +54a.
#   barrels: 96x64 PNG at (sx-10, sy-14) for count>=3; left-n crop (42/74 px
#     wide) for count 1/2; procedural drums span (-8,-10)..(+26,+21).
#   coil: 64x64 PNG at (sx-32, sy-36); procedural tail plug reaches +41.
#   mop: 48x64 PNG at (sx-20, sy-42); procedural handle reaches +46.
#   cart: 96x64 PNG at (sx-44, sy-30); procedural body is fully inside it.
FOOTPRINTS = {
    "crates": lambda a: (-48 * a, -44 * a, 102 * a, 96 * a),
    "barrels": lambda a: ((-10, -14, 96, 64) if int(a) >= 3
                          else (-10, -14, 42 if int(a) <= 1 else 74, 64)),
    "coil": lambda a: (-32, -36, 73, 64),
    "mop": lambda a: (-20, -42, 66, 72),
    "cart": lambda a: (-44, -30, 96, 64),
}


def footprint_rect(kind, tx, ty, arg, tile_size):
    """World-space rect of a prop anchored at tile (tx, ty), or None.

    The anchor is the tile's TOP-LEFT corner.  Callers that draw at the tile
    centre (M1/M2 dressing loops) must shift the result by half a tile so
    the validated rect matches what is actually drawn.
    """
    foot = FOOTPRINTS.get(kind)
    if foot is None:
        return None
    dx, dy, dw, dh = foot(arg)
    x0, y0 = tx * tile_size + dx, ty * tile_size + dy
    return pygame.Rect(int(x0), int(y0), int(dw), int(dh))
