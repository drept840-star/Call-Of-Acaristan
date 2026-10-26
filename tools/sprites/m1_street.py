"""m1_street.py - Mission 1 street band furniture (WP4) as authored sprites.

Art only: nothing here is wired into the map or the draw code yet; the WP4
map-growth package consumes the sheet later. It holds the pieces of the new
north street (plan rows 0-9) that no existing sheet could supply:

  fence_mesh / fence_post   chain-link fence, one 64 px tile, alpha (the map
                            tile blocks movement but NOT sight, so it is drawn
                            over the floor; alternate mesh/post along a run)
  lamp_post / lamp_post_off sodium street lamp, anchor = base centre
  rubble_0 / rubble_1       brick-and-concrete rubble pile (the brick pickup)
  shutter_3w                closed loading roller shutter, 3 x 64 px,
                            anchor = tile top-left
  van_delivery              plain panel van, top-down, faces east

Reused verbatim instead of re-authored (see the WP4 survey):
  * wet asphalt floor  - art pack ``t_dot_0..3`` via ``artpack.tile(".", ...)``
                         (ROAD base) and ``t_s_0..3`` for the worn service strip
  * puddles / scorch   - ``spr_props_m2:puddle``, ``puddle_scorch``, ``soot``
  * parked cargo truck - ``spr_vehicles:ipa_truck`` (160 x 54, faces east)
  * side door (dark)   - ``door_leaf`` / ``door_open_inner``
  * rain over the band - ``rain_0..5`` + ``splash``

House style (palette.py / kit.py): key light upper-left, flat material ramps,
1 px darker-hue outlines, stepped (never blurred) AO and contact shadows, no
gradients, no smoothscale, no noise scatter. Deterministic: fixed seeds only,
frames packed in insertion order, JSON sorted.

    python tools/sprites/m1_street.py [--preview] [--out DIR]
"""
import math
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import kit  # noqa: E402
import palette as P  # noqa: E402
import pygame  # noqa: E402

FAMILY = "m1_street"
T = P.T                      # 64 px - every street piece is authored 1:1
VAN = (152, 56)              # delivery van collision rect (faces east)
VAN_PAD = 14                 # frame border so the outline + shadow fit
SHUTTER_W = T * 3            # the loading shutter is 3 tiles wide

STEEL = P.SIGN_STEEL         # (72, 80, 84) - fence, lamp, shutter frames
SLAT_STEEL = (58, 62, 66)    # galvanised roller slats
SODIUM = (255, 214, 150)     # lit lens, same value M5's lamp posts use
BRICK = (126, 70, 54)
CONCRETE = (98, 92, 84)
VAN_PAINT = dict(P.CAR_PAINTS)["dusty_white"]


# ── shared helpers (flat tone, stepped edges - no blur, no noise) ──────────
def _ramp_lines(surf, pts, R):
    """Lit upper-left hull edges, shaded lower-right ones (house pattern)."""
    cx = sum(p[0] for p in pts) / len(pts)
    cy = sum(p[1] for p in pts) / len(pts)
    for i in range(len(pts)):
        a, b = pts[i], pts[(i + 1) % len(pts)]
        mx, my = (a[0] + b[0]) * 0.5, (a[1] + b[1]) * 0.5
        lit_side = (mx - cx) + (my - cy) < 0.0
        pygame.draw.line(surf, R[3] if lit_side else R[1], a, b, 1)


def _shrink(pts, k=0.80):
    cx = sum(p[0] for p in pts) / len(pts)
    cy = sum(p[1] for p in pts) / len(pts)
    return [(cx + (x - cx) * k, cy + (y - cy) * k) for x, y in pts]


def _jag(cx, cy, w, h, rng, n=6):
    """Jagged, blocky stone/cobble hull around (cx, cy)."""
    pts = []
    for i in range(n):
        a = math.tau * i / n + 0.18
        rx = w * 0.5 * (0.72 + 0.28 * rng.random())
        ry = h * 0.5 * (0.72 + 0.28 * rng.random())
        pts.append((cx + math.cos(a) * rx, cy + math.sin(a) * ry))
    return pts


def _chunk(surf, pts, col):
    R = P.ramp(col, 5, 0.95)
    pygame.draw.polygon(surf, R[0], pts)                 # ink hull (1 px)
    body = _shrink(pts, 0.82)
    pygame.draw.polygon(surf, R[2], body)
    _ramp_lines(surf, body, R)


def _brick(surf, x, y, w=14, h=7, col=BRICK):
    R = P.ramp(col, 5, 0.9)
    surf.fill(R[0], (x, y, w, h))
    surf.fill(R[2], (x + 1, y + 1, w - 2, h - 2))
    surf.fill(R[3], (x + 1, y + 1, w - 2, 1))
    surf.fill(R[1], (x + 1, y + h - 2, w - 2, 1))
    surf.fill(R[4], (x + 2, y + 1, 2, 1))                # key-light fleck


def _wheel(s, ax, oy, h, tw=16, th=9):
    """Road wheel, top-down: same recipe as tools/sprites/vehicles.py::_tyres."""
    for ty in (oy - 4, oy + h - th + 4):
        kit.rrect(s, P.TYRE, (ax - tw // 2, ty, tw, th), 2)
        s.fill(P.TYRE_HI, (ax - tw // 2 + 2, ty, tw - 4, 1))
        for gx in range(ax - tw // 2 + 3, ax + tw // 2 - 2, 3):
            s.fill(P.mix(P.TYRE, P.TYRE_HI, 0.35), (gx, ty + 2, 1, th - 3))
        s.fill(P.mix(P.TYRE, P.TYRE_HI, 0.5), (ax - 1, ty + 1, 2, th - 2))
        s.fill(P.HUB, (ax - 2, ty + th // 2 - 1, 4, 2))       # hub cap


# ── chain-link fence (rows 7, gaps at 7 and 22) ─────────────────────────────
def fence(with_post):
    """One fence tile: a horizontal band at the tile's vertical centre.

    The map char ``f`` blocks movement only, so the mesh stays transparent and
    the art-pack floor shows through.  Pitch (16 px) divides the tile, so a run
    of the same key keeps its weave across every 64 px seam; posts are a second
    key so a run can alternate post/mesh/post instead of picketing every tile.
    """
    s = kit.new(T, T)
    R = P.ramp(P.mix(STEEL, (44, 48, 52), 0.38), 5, 0.95)
    deep, shd, base, lit, hi = R
    top, bot = 12, 46                       # band: rail/rail (fence line)
    rail_h = 4
    m_top, m_bot = top + rail_h + 1, bot - 1
    # mesh: two diagonal families, one lit, one shaded (a weave, not a lattice)
    for i in range(-16, T + 32, 16):
        pygame.draw.line(s, shd, (i, m_top), (i + 16, m_bot), 1)
        pygame.draw.line(s, lit, (i + 18, m_top), (i + 2, m_bot), 1)
    for i in range(-8, T + 24, 16):         # half-pitch wires: finer mesh read
        pygame.draw.line(s, P.mix(shd, base, 0.45), (i, m_top), (i + 16, m_bot), 1)
    # tension wire under the top rail
    pygame.draw.line(s, deep, (0, m_top + 1), (T - 1, m_top + 1), 1)
    # rails: dark hull, flat body, 1 px lit crown
    for y in (top, bot):
        s.fill(deep, (0, y, T, rail_h + 1))
        s.fill(base, (0, y + 1, T, rail_h - 1))
        s.fill(hi, (0, y + 1, T, 1))
        s.fill(shd, (0, y + rail_h, T, 1))
    if with_post:
        # 5 px post on the tile's left edge, standing proud of the rails
        s.fill(deep, (0, 7, 6, 46))
        s.fill(base, (1, 8, 4, 44))
        s.fill(hi, (1, 8, 1, 44))
        s.fill(lit, (1, 6, 4, 2))                       # cap
        s.fill(shd, (4, 8, 1, 44))
        s.fill(deep, (0, 51, 7, 3))                     # foot block
        s.fill(base, (1, 51, 5, 2))
        s.fill((0, 0, 0, 52), (0, 54, 8, 2))            # flat contact shadow
        s.fill((0, 0, 0, 26), (0, 56, 10, 1))
    return s


# ── sodium street lamp (row 2, and the shutter floodlight F) ───────────────
def lamp_post(lit=True):
    """Street lamp, top-down: base plate, arm reaching north, hooded head.

    Anchor is the base centre, so a caller blits at the tile's centre and the
    head overhangs the row above.  Glow is the lighting pass's job (``L_radial``
    / LightBuffer); the lens itself stays a hard-edged sodium rectangle.
    """
    W, H = 64, 88
    ax, ay = 32, 76
    s = kit.new(W, H)
    S = P.ramp(STEEL, 5, 1.05)
    D = P.ramp((44, 46, 50), 5, 1.0)                    # cast-iron base
    kit.ellipse_shadow(s, (ax - 14, ay - 8, 30, 16))
    # arm: 5 px hull, 3 px body, lit left edge (key light upper-left)
    pygame.draw.line(s, S[0], (ax, ay - 4), (ax, 34), 5)
    pygame.draw.line(s, S[2], (ax, ay - 4), (ax, 34), 3)
    pygame.draw.line(s, S[4], (ax - 1, ay - 4), (ax - 1, 34), 1)
    # head: hood, dark recess, lens
    hood = pygame.Rect(ax - 10, 14, 20, 22)
    pygame.draw.rect(s, S[0], hood.inflate(4, 2))
    pygame.draw.rect(s, S[2], hood)
    s.fill(S[3], (hood.x + 1, hood.y + 1, hood.w - 2, 1))
    s.fill(S[1], (hood.x + 1, hood.bottom - 2, hood.w - 2, 1))
    pygame.draw.rect(s, (18, 18, 20), (hood.x + 3, hood.y + 5, hood.w - 6, hood.h - 8))
    lens = pygame.Rect(hood.x + 5, hood.y + 7, hood.w - 10, hood.h - 12)
    if lit:
        pygame.draw.rect(s, SODIUM, lens)
        pygame.draw.rect(s, (255, 246, 214), (lens.x + 1, lens.y + 1, lens.w - 2, lens.h // 2))
    else:
        pygame.draw.rect(s, P.ramp(P.GLASS)[2], lens)
        s.set_at((lens.x + 2, lens.y + 2), P.GLASS_HI)
    # finial + base plate (bolted, three tone steps)
    pygame.draw.rect(s, S[0], (ax - 12, 11, 24, 4))
    pygame.draw.rect(s, S[2], (ax - 11, 12, 22, 2))
    pygame.draw.circle(s, D[0], (ax, ay), 10)
    pygame.draw.circle(s, D[2], (ax, ay), 9)
    pygame.draw.circle(s, D[3], (ax - 1, ay - 1), 6)
    pygame.draw.circle(s, D[1], (ax + 3, ay + 3), 3)
    for bx, by in ((ax - 7, ay - 6), (ax + 7, ay - 6), (ax - 7, ay + 6), (ax + 7, ay + 6)):
        pygame.draw.circle(s, D[0], (bx, by), 1)
    return s


# ── rubble / brick pickup pile (rows 5 and 9) ──────────────────────────────
def rubble(seed, variant):
    """A heap of broken concrete with two whole bricks on top.

    Rubble is a *pickup* (2 bricks), so the two whole bricks sit proud on the
    crest; everything else is broken slab and chip.  Ground dust is a hard-edged
    angular smear under the stones - never a sprinkled pixel field.
    """
    s = kit.new(T, T)
    kit.ellipse_shadow(s, (7, 32, 52, 20))
    rng = random.Random(seed)
    # dust smear: two flat, stepped polygons under the heap (hard edges only)
    dust = P.mix(CONCRETE, (156, 150, 140), 0.22)
    pygame.draw.polygon(s, (*dust, 96), [(10, 40), (18, 34), (46, 33), (56, 41),
                                         (50, 50), (16, 49)])
    pygame.draw.polygon(s, (*P.shade(dust, 0.80), 110), [(16, 43), (26, 37), (44, 38),
                                                        (50, 45), (34, 48)])
    # back row: big slabs (fills most of the tile), then chips in front
    for i in range(5):
        cx = 10 + i * 11 + rng.randint(-2, 2)
        cy = 32 + rng.randint(-3, 3)
        col = CONCRETE if (i + variant) % 3 else BRICK
        _chunk(s, _jag(cx, cy, rng.randint(20, 27), rng.randint(15, 20), rng), col)
    for i in range(5):
        cx = 12 + i * 10 + rng.randint(-2, 2)
        cy = 44 + rng.randint(-2, 2)
        col = BRICK if (i + variant) % 2 else CONCRETE
        _chunk(s, _jag(cx, cy, rng.randint(12, 16), rng.randint(9, 13), rng), col)
    # whole bricks on the crest - the pile *is* the pickup (2 bricks per pile)
    _brick(s, 20, 25, 17, 9, BRICK)
    bx, by = 38, 31
    pygame.draw.polygon(s, P.ramp(BRICK)[0], [(bx, by), (bx + 15, by - 2), (bx + 16, by + 6),
                                             (bx + 2, by + 8)])
    pygame.draw.polygon(s, P.ramp(P.mix(BRICK, CONCRETE, 0.35))[2],
                        [(bx + 1, by), (bx + 14, by - 1), (bx + 15, by + 5), (bx + 3, by + 6)])
    pygame.draw.line(s, P.ramp(BRICK)[3], (bx + 1, by), (bx + 14, by - 1), 1)
    # two loose bricks spilled off the front edge (the pickup, readable at 1:1)
    _brick(s, 40, 47, 14, 8, P.mix(BRICK, CONCRETE, 0.20))
    _brick(s, 26, 50, 12, 7, BRICK)
    return s


# ── loading shutter (row 10, cols 22-24) ───────────────────────────────────
def shutter_3w():
    """Closed roller shutter, 3 tiles wide: slats, guide rails, bottom bar.

    Authored once for the whole opening (a per-tile repeat cannot carry the
    one dented slat, the latch and the guide rails).  Anchor = tile top-left,
    so the caller blits at (col * 64, row * 64) for the 3-wide ``S`` run.
    """
    W, H = SHUTTER_W, T
    s = kit.new(W, H)
    S = P.ramp(STEEL, 5, 1.05)
    D = P.ramp(SLAT_STEEL, 5, 1.0)
    s.fill((14, 15, 16), (0, 0, W, H))                  # dark recess behind
    # slats, 6 px pitch; every other slat a shade darker so the roll reads
    y, i = 5, 0
    while y < H - 12:
        body = D[2] if i % 2 == 0 else P.mix(D[2], D[1], 0.5)
        s.fill(body, (5, y, W - 10, 5))
        s.fill(D[3], (6, y, W - 12, 1))                 # lit lip
        s.fill(D[0], (6, y + 4, W - 12, 1))             # seam shadow
        y += 6
        i += 1
    # one dented slat: the middle third sags a pixel, with a lit buckle crease
    dy = 34
    s.fill(D[2], (66, dy + 1, 76, 4))
    s.fill(D[3], (70, dy + 1, 68, 1))
    s.fill(D[0], (66, dy + 5, 76, 1))
    pygame.draw.line(s, (18, 20, 22), (86, dy), (96, dy + 5), 1)
    pygame.draw.line(s, D[3], (96, dy + 5), (104, dy), 1)
    # guide rails (lit on the inside, shaded outward)
    for gx, inner in ((0, S[3]), (W - 5, S[1])):
        s.fill(S[0], (gx, 0, 5, H))
        s.fill(S[2], (gx + 1, 0, 3, H))
        s.fill(inner, (gx + 1 if gx == 0 else gx + 3, 0, 1, H))
    # lintel shadow at the head, floor contact under the bar
    kit.ao_band(s, (5, 0, W - 10, 9), alpha=120, height=9, edge="bottom")
    # bottom bar: handle slot, latch plate, hazard sticker
    bar = pygame.Rect(5, H - 12, W - 10, 8)
    s.fill(D[0], bar.inflate(0, 1))
    s.fill(D[2], bar)
    s.fill(D[3], (bar.x + 1, bar.y + 1, bar.w - 2, 1))
    s.fill((20, 22, 24), (W // 2 - 20, bar.y + 2, 40, 3))
    s.fill(D[1], (W // 2 - 19, bar.y + 2, 38, 1))
    s.fill((150, 128, 52), (bar.x + 6, bar.y - 10, 16, 9))
    for hx in range(bar.x + 7, bar.x + 22, 4):
        pygame.draw.line(s, (34, 30, 16), (hx, bar.y - 9), (hx + 2, bar.y - 2), 2)
    # latch plate + stencil
    plate = pygame.Rect(W // 2 - 8, H - 19, 16, 10)
    s.fill(S[0], plate.inflate(2, 2))
    s.fill(S[2], plate)
    s.fill(S[3], (plate.x + 1, plate.y + 1, plate.w - 2, 1))
    pygame.draw.circle(s, (16, 17, 18), (plate.centerx, plate.y + 4), 2)
    s.fill((16, 17, 18), (plate.centerx - 1, plate.y + 4, 2, 4))
    kit.text(s, "LOADING", W // 2 - kit.text_w("LOADING") // 2, 13,
             P.shade(P.CREAM, 0.58))
    return s


# ── delivery van (row 6 cover) ─────────────────────────────────────────────
def van_delivery():
    """Plain panel van, top-down, faces east (same facing as spr_vehicles)."""
    w, h = VAN
    fw, fh = w + VAN_PAD * 2, h + VAN_PAD * 2
    ox = oy = VAN_PAD
    V = P.ramp(VAN_PAINT, 5, 0.9)
    RR = P.ramp(P.shade(VAN_PAINT, 0.80), 5, 0.85)
    G = P.ramp(P.GLASS, 5, 0.9)
    cargo_w = int(w * 0.66)
    out = kit.new(fw, fh)
    kit.shadow(out, (ox, oy - 2, w, h + 4), r=6, alpha=(74, 40))
    b = kit.new(fw, fh)
    _wheel(b, ox + 24, oy, h)
    _wheel(b, ox + w - 26, oy, h)
    # shell: lit crown band, shaded sill, darker nose edge
    kit.rrect(b, V[2], (ox, oy, w, h), 6)
    kit.rrect(b, V[3], (ox + 1, oy, w - 2, 3), 4)
    b.fill(V[4], (ox + 6, oy, w - 12, 1))
    kit.rrect(b, V[1], (ox + 1, oy + h - 4, w - 2, 4), 3)
    b.fill(V[0], (ox + 6, oy + h - 1, w - 12, 1))
    # box roof: raised panel, ribs, vent
    rx, ry, rw, rh = ox + 7, oy + 6, cargo_w - 14, h - 12
    kit.rrect(b, RR[2], (rx, ry, rw, rh), 3)
    kit.inner_line(b, (rx, ry, rw, rh), RR[3], RR[1])
    b.fill(RR[4], (rx + 2, ry, rw - 4, 1))
    for i in range(3):
        yy = ry + 6 + i * ((rh - 12) // 3)
        b.fill(RR[0], (rx + 2, yy, rw - 4, 1))
        b.fill(RR[3], (rx + 2, yy + 1, rw - 4, 1))
    vent = pygame.Rect(rx + rw - 16, ry + 4, 11, 7)
    b.fill(RR[0], vent.inflate(2, 2))
    b.fill(RR[1], vent)
    b.fill(RR[3], (vent.x + 1, vent.y + 1, vent.w - 2, 1))
    # roof stencil (house convention: cargo numbers are painted on the roof)
    kit.text(b, "CGO 07", rx + 6, ry + rh - 13, P.shade(P.CREAM, 0.62))
    # rear doors: two leaves, hasp
    b.fill(V[0], (ox + 2, oy + 5, 1, h - 10))
    b.fill(V[3], (ox + 3, oy + 5, 1, h - 10))
    b.fill(V[1], (ox + 1, oy + h // 2 - 4, 3, 8))
    b.fill(V[0], (ox, oy + h // 2, 3, 1))
    # cab: joint seam, receded roof, driver door seam, windscreen facing east
    cx = ox + cargo_w
    cw = w - cargo_w
    C = P.ramp(P.mix(VAN_PAINT, (118, 120, 116), 0.30))
    b.fill(V[0], (cx, oy + 2, 2, h - 4))
    kit.rrect(b, C[2], (cx + 3, oy + 4, cw - 17, h - 8), 3)
    kit.inner_line(b, (cx + 3, oy + 4, cw - 17, h - 8), C[3], C[1])
    b.fill(C[4], (cx + 4, oy + 4, cw - 19, 1))
    b.fill(V[0], (cx + 11, oy + 4, 1, h - 8))              # driver door seam
    b.fill(V[3], (cx + 12, oy + 4, 1, h - 8))
    b.fill((34, 34, 34), (cx + 5, oy + h // 2 - 2, 5, 3))  # door handle
    wx, wy, ww, wh = ox + w - 15, oy + 5, 10, h - 10
    kit.rrect(b, G[0], (wx - 1, wy - 1, ww + 2, wh + 2), 2)
    kit.rrect(b, G[2], (wx, wy, ww, wh), 1)
    for k in range(7):                                     # windscreen glint
        b.set_at((wx + ww - 3 - k // 3, wy + 2 + k), G[4])
    b.fill(G[3], (wx - 2, wy + 2, 1, wh - 4))
    b.fill((22, 22, 24), (ox + w - 4, oy + 3, 3, h - 6))   # nose / bumper shade
    b.fill((44, 44, 46), (ox + w - 3, oy + 8, 1, h - 16))
    for my in (oy - 2, oy + h):                            # mirrors
        b.fill(V[1], (ox + w - 21, my, 7, 2))
        b.fill(V[3], (ox + w - 21, my, 7, 1))
    # lamps + plate: headlights east, tail lights west
    for hy in (oy + 5, oy + h - 9):
        b.fill(P.mix(P.HEADLIGHT, V[0], 0.4), (ox + w - 3, hy, 3, 4))
        b.fill(P.HEADLIGHT, (ox + w - 2, hy + 1, 2, 2))
        b.fill(P.mix(P.TAILLIGHT, V[0], 0.35), (ox, hy, 2, 4))
        b.fill(P.TAILLIGHT, (ox + 1, hy + 1, 1, 2))
    b.fill((20, 18, 16), (ox + cargo_w - 4, oy + h // 2 - 3, 2, 6))
    b = kit.outline(b)
    out.blit(b, (0, 0))
    return out


def build():
    sh = kit.Sheet("spr_m1_street", FAMILY, max_w=1024)
    sh.meta = {
        "anchor": "fence/lamp/rubble = world pos, shutter = tile top-left, van = collision-rect top-left",
        "tile": T,
        "fence": {"blocks": "movement only - sight passes; draw over the floor",
                  "run": "alternate fence_post / fence_mesh so posts land every other tile",
                  "frame": "64x64, alpha"},
        "lamp_post": {"anchor": "base centre", "reach_px": 62, "lens": "sodium"},
        "shutter_3w": {"tiles_wide": 3, "draw_at": "col * 64, row * 64"},
        "van_delivery": {"facing": "east", "rect_size": list(VAN)},
        "missing_floor": "wet asphalt is the art-pack tile . (t_dot_0..3) / s (t_s_0..3)",
    }
    sh.add("fence_mesh", fence(False), (0, 0), blocks="move_only")
    sh.add("fence_post", fence(True), (0, 0), blocks="move_only")
    sh.add("lamp_post", lamp_post(True), (32, 76), state="on")
    sh.add("lamp_post_off", lamp_post(False), (32, 76), state="off")
    for i, seed in enumerate((70341, 70342)):
        sh.add("rubble_%d" % i, rubble(seed, i), (32, 42), variant=i, pickup="brick")
    sh.add("shutter_3w", shutter_3w(), (0, 0), tiles_wide=3)
    sh.add("van_delivery", van_delivery(), (VAN_PAD, VAN_PAD), rect_size=list(VAN), facing="east")
    return [sh]


if __name__ == "__main__":
    sys.exit(kit.run(FAMILY, build))
