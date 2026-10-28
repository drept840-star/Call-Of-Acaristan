"""Draws the M7 farm 3D pixel textures (assets/tex3d/m7_<name>.png) from the
2D farm palette (src/cutscenes/m7palette3d.py), with the M6 helpers.

    python tools/tex3d_draw_m7.py                 # every texture (+ m7.gpl)
    python tools/tex3d_draw_m7.py grass track     # some of them
    python tools/tex3d_draw_m7.py --sheet OUT.png # also a 4x contact sheet

Same rules as tools/tex3d_draw.py: 64x64 tiles that wrap on both axes, only
palette colours, a fixed seed per texture, light from the top left.

Ground textures are drawn for 16 texels/m (a tile is 4 m), the rest for 32.
On ground faces the GL backend runs image columns (u) along world z and rows
(v) along world x, with world x = 0 on row 0: rows 16 and 48 are x = -1 / +1 m,
which is where the track's ruts sit.  On walls, rows stay level and the image
top is up the wall (or up a roof slope).
"""
import math
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "src"))

import tex3d_draw as T  # noqa: E402  (M6 helpers: noise, fbm, ramp, put, Bayer)
from cutscenes import m7palette3d as P  # noqa: E402
import pygame  # noqa: E402

N = T.N
BAYER = T.BAYER
noise, fbm, ramp, put, disc_mask = T.noise, T.fbm, T.ramp, T.put, T.disc_mask
ROOT = T.ROOT


def _palette():
    out = {}
    for k in dir(P):
        v = getattr(P, k)
        if k.isupper() and isinstance(v, tuple) and len(v) == 3 and k not in (
                "LAMP_WARM", "WINDOW"):
            out[k.lower().replace("_", " ")] = v
    return out


PAL = _palette()


def _clumps(rng, img, count, rmin, rmax, cols, lit_cols=None):
    """Discs with a lit top-left rim and a dark bottom-right rim (leaves,
    clods, stones).  ``cols`` dark to light; the base is never an end."""
    for _ in range(count):
        cx, cy = rng.integers(0, N, 2)
        r = rmin + (rmax - rmin) * rng.random()
        i = int(rng.integers(1, len(cols) - 1))
        base, lit, dark = cols[i], cols[i + 1], cols[i - 1]
        if lit_cols and rng.random() < 0.3:
            j = int(rng.integers(0, len(lit_cols)))
            base = lit_cols[j]
            lit = lit_cols[min(j + 1, len(lit_cols) - 1)]
        for dx, dy, d in disc_mask(r):
            col = base
            if d > 0.55:
                lam = (-dx * 0.6 - dy * 0.8) / max(1e-6, math.hypot(dx, dy))
                if lam > 0.35:
                    col = lit
                elif lam < -0.35:
                    col = dark
            put(img, cx + dx, cy + dy, col)


# ── ground (16 texels/m) ────────────────────────────────────────────────
def grass(rng):
    """Late-autumn pasture: olive turf going to straw in drifts, tufts with a
    dark foot, a few bare-earth specks."""
    v = fbm(rng, [16, 8, 4], [0.5, 0.3, 0.2])
    img = ramp(v, [P.GRASS_DD, P.GRASS_D, P.GRASS, P.GRASS_DRY], dither=0.7)
    dry = noise(rng, 32) * 0.6 + noise(rng, 8) * 0.4
    m = (dry > 0.62) & (BAYER > -0.2)
    img[m] = np.where((v[m] > 0.5)[:, None], np.array(P.HAY_D), np.array(P.GRASS_DRY))
    for _ in range(150):
        x, y = rng.integers(0, N, 2)
        hi = P.GRASS_HI if rng.random() < 0.6 else P.HAY_SHADE
        put(img, x, y, hi)
        put(img, x, y + 1, P.GRASS)
        put(img, x + 1, y + 1, P.GRASS_INK)
    img[rng.random((N, N)) < 0.006] = P.DIRT_D
    return img


def stubble(rng):
    """Cut cereal field: ochre stubble rows every 4 texels (25 cm) running
    along u (world z), dark loam between them, bare and trampled patches."""
    img = np.empty((N, N, 3), np.uint8)
    bare = fbm(rng, [16, 8], [0.6, 0.4])
    jit = rng.random((N, N))
    for y in range(N):
        ph = y % 4
        for x in range(N):
            if bare[y, x] > 0.72 and BAYER[y, x] > -0.1:
                col = P.LOAM if ph else P.WOOD_D
            elif ph == 0:
                col = P.HAY_MID if jit[y, x] < 0.35 else P.HAY_SHADE if jit[y, x] < 0.8 else P.HAY
            elif ph == 1:
                col = P.HAY_D if jit[y, x] < 0.7 else P.HAY_DD
            elif ph == 2:
                col = P.HAY_DD if jit[y, x] < 0.5 else P.LOAM
            else:
                col = P.LOAM if jit[y, x] < 0.8 else P.WOOD_D
            img[y, x] = col
    for _ in range(40):                              # loose straw lying across
        x, y = rng.integers(0, N, 2)
        for i in range(int(rng.integers(2, 5))):
            put(img, x + i, y + (i // 2), P.HAY_HI)
    return img


def furrow(rng):
    """Ploughed loam: ridges every 8 texels (50 cm) along u, a lit crest,
    dark troughs, clods and a few buried straw ends."""
    img = np.empty((N, N, 3), np.uint8)
    cols = [P.INK, P.WOOD_DARK, P.LOAM, P.TRACK_D, P.DIRT_D]
    wob = noise(rng, 16, 64)
    for y in range(N):
        for x in range(N):
            ph = (y + int(wob[y, x] * 2.0)) % 8
            img[y, x] = cols[(1, 3, 4, 3, 2, 2, 1, 0)[ph]]
    _clumps(rng, img, 70, 0.9, 1.8, [P.INK, P.WOOD_DARK, P.LOAM, P.TRACK_D, P.DIRT_D])
    for _ in range(24):
        x, y = rng.integers(0, N, 2)
        put(img, x, y, P.HAY_D)
        put(img, x + 1, y, P.HAY_DD)
    return img


def dirt(rng):
    """Packed yard dirt: worn smooth, pebbles, trodden straw, boot and hoof
    prints."""
    v = fbm(rng, [16, 8, 4], [0.45, 0.35, 0.2])
    img = ramp(v, [P.TRACK_D, P.DIRT_D, P.DIRT, P.DIRT, P.DIRT_HI], dither=0.8)
    _clumps(rng, img, 26, 0.6, 1.3, [P.WOOD_DARK, P.STONE_D, P.STONE, P.DIRT_HI])
    for _ in range(36):
        x, y = rng.integers(0, N, 2)
        for i in range(int(rng.integers(2, 4))):
            put(img, x + i, y, P.HAY_D if i % 2 else P.HAY_SHADE)
    for _ in range(14):
        x, y = rng.integers(0, N, 2)
        put(img, x, y, P.TRACK_D); put(img, x + 1, y, P.TRACK_D)
        put(img, x, y + 1, P.WOOD_D); put(img, x + 1, y + 1, P.DIRT_HI)
    return img


def track(rng):
    """Farm track, 16 texels/m: packed earth and grit, two ruts at x = -1 and
    +1 m with tyre tread running along them, a grass crown down the middle."""
    v = fbm(rng, [16, 8, 4], [0.5, 0.3, 0.2])
    img = ramp(v, [P.TRACK_D, P.TRACK, P.TRACK, P.TRACK_HI], dither=0.8)
    _clumps(rng, img, 60, 0.5, 1.2, [P.WOOD_DARK, P.STONE_D, P.STONE, P.DIRT_HI])
    wob = noise(rng, 16, 64)
    yy, xx = np.mgrid[0:N, 0:N]
    for y0 in (16, 48):
        d = np.abs(((yy - y0 - 2.0 * (wob - 0.5)) + N / 2) % N - N / 2)
        rut = d < 3.4
        deep = d < 1.8
        img[rut] = np.where((BAYER[rut] > 0.1)[:, None], np.array(P.TRACK_D), np.array(P.WOOD_D))
        img[deep] = P.WOOD_DARK
        tread = deep & (xx % 3 == 0)
        img[tread] = P.LOAM
        img[rut & (d > 2.9) & (BAYER > 0.2)] = P.TRACK_HI       # pushed-up lip
    crown = (np.abs(yy - 32) < 5) & (noise(rng, 8) > 0.45) & (BAYER > -0.15)
    img[crown] = P.GRASS_D
    img[crown & (rng.random((N, N)) < 0.25)] = P.GRASS_DRY
    img[(np.abs(yy - 32) < 3) & (rng.random((N, N)) < 0.07)] = P.GRASS_DD
    return img


# ── buildings (32 texels/m) ─────────────────────────────────────────────
def plank(rng):
    """Weathered grey-brown boards (fences, shed, porch, doors): 8-texel
    boards running level, a dark gap under each, grain, nail heads."""
    img = np.empty((N, N, 3), np.uint8)
    woods = [P.WOOD_BLACK, P.WOOD_GREY, P.WOOD_DUN, P.WOOD_MID, P.WOOD, P.WOOD_L]
    for p in range(N // 8):
        i = int(rng.integers(1, 4))
        base = woods[i]
        grain = noise(rng, 16, 2)
        for dy in range(8):
            y = p * 8 + dy
            img[y, :] = np.where((grain[y] > 0.6)[:, None], np.array(woods[i - 1]), np.array(base))
            if dy == 0:
                img[y, :] = woods[i + 1]
            if dy == 7:
                img[y, :] = P.INK
        for j in (int(rng.integers(0, N)), int(rng.integers(0, N))):
            for dy in range(7):
                put(img, j, p * 8 + dy, P.WOOD_DARK)
            put(img, j - 2, p * 8 + 2, P.INK)
            put(img, j + 2, p * 8 + 5, P.INK)
    silver = (fbm(rng, [32, 8], [0.7, 0.3]) > 0.68) & (BAYER > 0.0)
    img[silver & (img.sum(axis=2) > 200)] = P.WOOD_GREY
    return img


def barnboard(rng):
    """Oxblood board-and-batten: 8-texel boards standing upright, a batten
    shadow on every joint, paint worn through to grey wood low and at the
    edges, grain running down."""
    img = np.empty((N, N, 3), np.uint8)
    reds = [P.BARN_INK, P.BARN_DD, P.BARN_D, P.BARN, P.BARN_L]
    wear = fbm(rng, [16, (8, 32)], [0.6, 0.4])
    for b in range(N // 8):
        i = int(rng.integers(2, 4))
        grain = noise(rng, 2, 16)
        for dx in range(8):
            x = b * 8 + dx
            col = np.where((grain[:, x] > 0.64)[:, None], np.array(reds[i - 1]), np.array(reds[i]))
            img[:, x] = col
            if dx == 0:
                img[:, x] = reds[i + 1]
            if dx == 7:
                img[:, x] = P.BARN_INK
            if dx == 6:
                img[:, x] = P.BARN_DD
    worn = (wear > 0.74) & ((np.arange(N) % 8) < 6)[None, :]
    img[worn] = np.where((BAYER[worn] > 0.0)[:, None], np.array(P.WOOD_GREY), np.array(P.WOOD_DUN))
    for _ in range(20):                              # nail rows
        x = int(rng.integers(0, N // 8)) * 8 + 3
        put(img, x, int(rng.integers(0, N)), P.BARN_INK)
    return img


def plaster(rng):
    """Whitewashed render: low-contrast trowel marks, hairline cracks, flaked
    patches showing the stone and brick under it, grime run down."""
    v = fbm(rng, [32, 8, 4], [0.4, 0.4, 0.2])
    img = ramp(v, [P.PLASTER_SHADE, P.PLASTER, P.PLASTER, P.PLASTER_L], dither=0.5)
    flake = noise(rng, 16) * 0.7 + noise(rng, 4) * 0.3
    hole = flake > 0.80
    img[hole] = np.where((BAYER[hole] > 0.0)[:, None], np.array(P.STONE), np.array(P.STONE_D))
    img[hole & (noise(rng, 4) > 0.6)] = P.BARN_L
    rim = (flake > 0.76) & ~hole
    img[rim] = P.PLASTER_SHADE
    for _ in range(6):
        x, y = int(rng.integers(0, N)), int(rng.integers(0, N))
        for _s in range(int(rng.integers(8, 20))):
            put(img, x, y, P.DIRT_HI)
            x += int(rng.integers(-1, 2))
            y += 1
    for _ in range(5):                               # grime under sills and eaves
        x = int(rng.integers(0, N))
        for i in range(int(rng.integers(6, 18))):
            if BAYER[i % N, x % N] < 0.2:
                put(img, x, i, P.PLASTER_SHADE)
    return img


def tile(rng):
    """Clay pantile roof: courses every 8 rows, a tile every 8 columns, each
    one rounded (lit left, dark right), a shadow under every course, a few
    darker replacements and moss."""
    img = np.empty((N, N, 3), np.uint8)
    for row in range(N // 8):
        off = 4 if row % 2 else 0
        for c in range(N // 8):
            k = rng.random()
            mid = P.ROOF if k < 0.7 else P.ROOF_D if k < 0.92 else P.BARN_L
            hi = P.ROOF_L if mid != P.ROOF_D else P.ROOF
            lo = P.ROOF_D if mid != P.ROOF_D else P.BARN_D
            for dx in range(8):
                col = hi if dx < 2 else lo if dx >= 6 else mid
                for dy in range(8):
                    put(img, c * 8 + dx + off, row * 8 + dy,
                        P.BRICK_D if dy == 7 else (P.BARN_D if dy == 6 and dx >= 5 else col))
    moss = (noise(rng, 16) > 0.66) & (rng.random((N, N)) < 0.35)
    img[moss] = P.MOSS
    return img


def tin(rng):
    """Corrugated sheet roof, galvanised gone to rust: a rib every 4 columns
    running up the slope, a lapped seam, rust blooms and runs from the
    fixings."""
    img = np.empty((N, N, 3), np.uint8)
    shade = [P.GALV_D, P.GALV, P.GALV_D, P.STEEL_D]
    for x in range(N):
        img[:, x] = shade[x % 4]
    rust = fbm(rng, [32, 16, 8], [0.5, 0.3, 0.2])
    rib = (np.arange(N) % 4 == 1)[None, :]
    r1 = (rust > 0.68) & (BAYER > -0.1)
    img[r1] = np.where(np.broadcast_to(rib, (N, N))[r1][:, None], np.array(P.RUST), np.array(P.RUST_D))
    img[(rust > 0.86)] = P.BRICK_D
    img[0, :] = P.INK
    img[1, :] = P.GALV
    for x in range(2, N, 8):
        put(img, x, 2, P.STONE)
        for i in range(int(rng.integers(3, 16))):
            if BAYER[(3 + i) % N, x % N] < 0.3:
                put(img, x, 3 + i, P.RUST if i < 5 else P.RUST_D)
    return img


def hay(rng):
    """Baled straw: strands packed along u, bright cut ends, two orange
    twine bands."""
    v = fbm(rng, [(16, 2), (8, 1), 4], [0.5, 0.3, 0.2])
    img = ramp(v, [P.HAY_DD, P.HAY_D, P.HAY_SHADE, P.HAY_SIDE, P.HAY_MID, P.HAY], dither=0.9)
    for _ in range(60):
        x, y = rng.integers(0, N, 2)
        put(img, x, y, P.HAY_HI)
        put(img, x + 1, y, P.HAY_HI)
    for x0 in (14, 46):
        img[:, x0] = P.GENERATOR
        img[:, x0 + 1] = P.RUST
    return img


def stone(rng):
    """Field-stone masonry (well, gate piers, chimney): rounded stones in
    dark mortar, lit top left."""
    img = np.empty((N, N, 3), np.uint8)
    img[:] = P.WOOD_DARK
    _clumps(rng, img, 120, 2.5, 5.0, [P.INK, P.STONE_D, P.STONE, P.PLASTER_SHADE])
    img[(rng.random((N, N)) < 0.03) & (img.sum(axis=2) > 300)] = P.STONE_D
    return img


def bark(rng):
    """Old fruit-tree bark: deep vertical fissures, lit plates between."""
    v = fbm(rng, [(4, 32), (2, 16), 8], [0.5, 0.3, 0.2])
    img = ramp(v, [P.INK, P.WOOD_DARK, P.WOOD_GREY, P.WOOD_D, P.WOOD_DUN], dither=0.8)
    img[(v > 0.8) & (BAYER > 0.2)] = P.MOSS
    return img


def leaf(rng):
    """Autumn orchard crowns: dark olive leaf clumps with ochre and rust
    turned leaves, lit top left, gaps of deep shade."""
    img = np.empty((N, N, 3), np.uint8)
    img[:] = P.GRASS_INK
    greens = [P.GRASS_INK, P.GRASS_DD, P.MOSS, P.GRASS_D, P.GRASS]
    turned = [P.RUST_D, P.RUST, P.HAY_DD, P.HAY_D, P.HAY_SHADE]
    _clumps(rng, img, 150, 1.6, 3.4, greens, lit_cols=turned)
    return img


TEXTURES = {
    "grass": (grass, 71, 16.0), "stubble": (stubble, 72, 16.0),
    "furrow": (furrow, 73, 16.0), "dirt": (dirt, 74, 16.0), "track": (track, 75, 16.0),
    "plank": (plank, 76, 32.0), "barnboard": (barnboard, 77, 32.0),
    "plaster": (plaster, 78, 32.0), "tile": (tile, 79, 32.0), "tin": (tin, 80, 32.0),
    "hay": (hay, 81, 32.0), "stone": (stone, 82, 32.0), "bark": (bark, 83, 32.0),
    "leaf": (leaf, 84, 32.0),
}


def draw(name):
    fn, seed, _density = TEXTURES[name]
    img = fn(np.random.default_rng(seed))
    assert img.shape == (N, N, 3)
    ok = set(PAL.values())
    stray = {tuple(int(c) for c in p) for p in img.reshape(-1, 3)} - ok
    assert not stray, "%s: off-palette %r" % (name, sorted(stray)[:4])
    return img


def write_gpl():
    cols = sorted(PAL.items(), key=lambda kv: sum(kv[1]))
    lines = ["GIMP Palette", "Name: Acaristan M7", "Columns: 8",
             "# The 2D top-down M7 farm palette, sampled from the farmyard frames,",
             "# dark to light.  Names match src/cutscenes/m7palette3d.py."]
    lines += ["%3d %3d %3d\t%s" % (c[0], c[1], c[2], n) for n, c in cols]
    with open(os.path.join(ROOT, "m7.gpl"), "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(lines) + "\n")


def main(argv):
    out_sheet = None
    if "--sheet" in argv:
        k = argv.index("--sheet")
        out_sheet = argv[k + 1]
        argv = argv[:k] + argv[k + 2:]
    names = argv or list(TEXTURES)
    imgs = {}
    for name in names:
        imgs[name] = draw(name)
        T.save(imgs[name], os.path.join(ROOT, "m7_" + name + ".png"))
        print("drew m7_" + name)
    if not argv:
        write_gpl()
    if out_sheet:
        T.sheet(imgs, out_sheet)


if __name__ == "__main__":
    pygame.init()
    main(sys.argv[1:])
