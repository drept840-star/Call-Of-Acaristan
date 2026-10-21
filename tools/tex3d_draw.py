"""Draws the M6 3D pixel textures (assets/tex3d/<name>.png) from the 2D palette.

    python tools/tex3d_draw.py                 # every texture
    python tools/tex3d_draw.py brick snow      # some of them
    python tools/tex3d_draw.py --sheet OUT.png # also a 4x contact sheet, tiled 2x2

Every tile is 64x64, wraps on both axes, and uses only colours from
assets/tex3d/m6.gpl. Each texture has its own fixed seed, so a rerun gives
the same pixels. engine3d.tex tiles them in world space; the densities the
scenes use are noted on each function (texels per metre).

The light in a texture always comes from the top left, like the 2D game's
sprites: stones and bricks get a lit top-left edge and a dark bottom-right.
"""
import math
import os
import sys

import numpy as np

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
import pygame  # noqa: E402

N = 64
ROOT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets", "tex3d")


def _palette():
    cols, names = [], {}
    with open(os.path.join(ROOT, "m6.gpl"), encoding="utf-8") as f:
        for line in f:
            parts = line.split()
            if len(parts) < 4 or not parts[0].isdigit():
                continue
            rgb = tuple(int(v) for v in parts[:3])
            names[" ".join(parts[3:])] = len(cols)
            cols.append(rgb)
    return cols, names


PAL, _NAMES = _palette()


def c(key):
    """A palette colour by its .gpl name ("rust hi") or hex ("#2D1513")."""
    return PAL[_NAMES[key]]


# The palette by role.  Names are the .gpl's; the hex ones are unnamed there.
INK, NIGHT, SLATE_DEEP, SLATE, SLATE_MID, SLATE_HI = (
    c("ink"), c("night"), c("slate deep"), c("slate"), c("slate mid"), c("slate hi"))
STEEL, EMBER, RUST, RUST_HI = c("steel"), c("ember"), c("rust"), c("rust hi")
SNOW_DIM, SNOW = c("snow dim"), c("snow")
WARM_BLACK, WARM_DARK, BROWN_GREY = c("#110E0F"), c("#171312"), c("#1D1918")
OXBLOOD, NEUTRAL, WARM_GREY = c("#2D1513"), c("#212021"), c("#2D2825")
BLUE_GREY, RUST_DARK, GREY = c("#242B37"), c("#42251A"), c("#353130")
BLUE_GREY_HI, BROWN, COOL_GREY = c("#2C3441"), c("#403125"), c("#3A4049")
TAUPE, DUN, OCHRE, KHAKI, LIGHT_GREY = (
    c("#463E36"), c("#594F44"), c("#90662E"), c("#83785E"), c("#788088"))

_BAYER = np.array([[0, 8, 2, 10], [12, 4, 14, 6], [3, 11, 1, 9], [15, 7, 13, 5]]) / 16.0 - 15 / 32
BAYER = np.tile(_BAYER, (N // 4, N // 4))


# ── helpers ─────────────────────────────────────────────────────────────
def noise(rng, cx, cy=None, n=N):
    """Wrapping value noise in [0, 1]: a random lattice every cx x cy texels,
    smoothstep-blended. cx, cy must divide 64."""
    cy = cx if cy is None else cy
    gx, gy = n // cx, n // cy
    lat = rng.random((gy, gx))
    x = np.arange(n) / cx
    y = np.arange(n) / cy
    x0 = np.floor(x).astype(int); y0 = np.floor(y).astype(int)
    fx = x - x0; fy = y - y0
    fx = fx * fx * (3 - 2 * fx); fy = fy * fy * (3 - 2 * fy)
    x1 = (x0 + 1) % gx; y1 = (y0 + 1) % gy
    x0 %= gx; y0 %= gy
    a = lat[np.ix_(y0, x0)]; b = lat[np.ix_(y0, x1)]
    cc = lat[np.ix_(y1, x0)]; d = lat[np.ix_(y1, x1)]
    top = a + (b - a) * fx[None, :]
    bot = cc + (d - cc) * fx[None, :]
    return top + (bot - top) * fy[:, None]


def fbm(rng, cells, weights):
    v = sum(w * noise(rng, cl) if isinstance(cl, int) else w * noise(rng, *cl)
            for cl, w in zip(cells, weights))
    return (v - v.min()) / max(1e-9, v.max() - v.min())


def ramp(v, cols, dither=1.0):
    """v in [0, 1] -> one of ``cols`` per texel, Bayer-dithered between steps."""
    k = len(cols) - 1
    idx = np.clip(np.floor(v * k + 0.5 + BAYER * dither), 0, k).astype(int)
    return np.asarray(cols, dtype=np.uint8)[idx]


def put(img, x, y, col):
    img[y % N, x % N] = col


def disc_mask(r):
    """Texel offsets inside a disc of radius r, with their outward direction."""
    out = []
    ri = int(math.ceil(r))
    for dy in range(-ri, ri + 1):
        for dx in range(-ri, ri + 1):
            d = math.hypot(dx * 0.85, dy * 1.1)
            if d <= r:
                out.append((dx, dy, d / max(r, 1e-6)))
    return out


def shade_step(cols, col, step):
    """The neighbour of ``col`` in the ramp ``cols``, ``step`` places up/down."""
    i = cols.index(col)
    return cols[max(0, min(len(cols) - 1, i + step))]


# ── textures ────────────────────────────────────────────────────────────
def snow(rng):
    """Open snow ground, 16 texels/m (a tile is 4 m). Soft drifts, wind
    ripples running across, a crust of single bright texels."""
    drift = fbm(rng, [32, 16, 8], [0.55, 0.3, 0.15])
    warp = noise(rng, 8)
    yy, xx = np.mgrid[0:N, 0:N]
    rip = np.sin(2 * math.pi * (3 * xx + yy) / N + 2.6 * warp) * 0.5 + 0.5
    rip = rip ** 3                                   # thin lit crests, wide troughs
    v = 0.30 + 0.55 * drift + 0.22 * rip
    # a narrow dither band at each step: a full Bayer ramp read as a
    # checkerboard on the drifts at the player's feet
    img = ramp(np.clip(v, 0, 1), [LIGHT_GREY, SNOW_DIM, SNOW_DIM, SNOW], dither=0.4)
    crust = rng.random((N, N))
    img[(crust < 0.018) & (v > 0.55)] = SNOW
    img[(crust > 0.994)] = LIGHT_GREY
    return img


def snow_trod(rng):
    """Packed, sooty snow beside the tracks and paths, 16 texels/m. Boot and
    tyre ruts, cinder flecks, a few stones poking through."""
    base = fbm(rng, [16, 8, 4], [0.5, 0.35, 0.15])
    yy, xx = np.mgrid[0:N, 0:N]
    rut = np.zeros((N, N))
    for x0 in (11, 37):                              # two ruts along the tile
        dx = np.abs(((xx - x0 - 3 * noise(rng, 16)) + N / 2) % N - N / 2)
        rut += np.clip(1 - dx / 4.5, 0, 1)
    v = 0.25 + 0.55 * base - 0.30 * rut
    img = ramp(np.clip(v, 0, 1), [COOL_GREY, LIGHT_GREY, SNOW_DIM, SNOW_DIM], dither=0.5)
    fleck = rng.random((N, N))
    img[fleck < 0.014] = GREY
    img[fleck > 0.990] = WARM_GREY
    for _ in range(14):
        x, y = rng.integers(0, N, 2)
        col = [GREY, TAUPE, COOL_GREY][rng.integers(0, 3)]
        put(img, x, y, col); put(img, x + 1, y, col)
        put(img, x, y + 1, WARM_DARK); put(img, x + 1, y + 1, WARM_DARK)
    return img


def _stones(rng, img, count, rmin, rmax, cols, rare=(), rare_p=0.0, snow_v=None,
            snow_col=SNOW_DIM, snow_at=0.62):
    """Packed stones: base colour per stone, lit top-left rim, dark
    bottom-right rim, later stones on top. ``snow_v``: where it is above
    ``snow_at`` the stones' top-left rims take ``snow_col``."""
    for _ in range(count):
        cx, cy = rng.integers(0, N, 2)
        r = rmin + (rmax - rmin) * rng.random()
        base = rare[rng.integers(0, len(rare))] if rare and rng.random() < rare_p \
            else cols[rng.integers(1, len(cols) - 1)]
        ramp_c = cols if base in cols else [WARM_DARK, base, shade_step(cols, cols[-1], 0)]
        lit = shade_step(ramp_c, base, +1)
        dark = shade_step(ramp_c, base, -1)
        snowy = snow_v is not None and snow_v[cy % N, cx % N] > snow_at
        for dx, dy, d in disc_mask(r):
            col = base
            if d > 0.55:
                lam = (-dx * 0.6 - dy * 0.8) / max(1e-6, math.hypot(dx, dy))
                if lam > 0.35:
                    col = snow_col if snowy else lit
                elif lam < -0.35:
                    col = dark
            put(img, cx + dx, cy + dy, col)


def ballast(rng):
    """Track ballast, 32 texels/m (a tile is 2 m). Grey and brown crushed
    stone, a rusty one here and there, a little snow lodged on top edges.

    Kept to a narrow, dark range: the shader multiplies by texel / mean, so a
    snow-white rim on a mean this dark lit up 4x and the bed read as camo."""
    img = np.empty((N, N, 3), np.uint8)
    img[:] = WARM_DARK
    gaps = rng.random((N, N)) < 0.3
    img[gaps] = WARM_BLACK
    cols = [WARM_BLACK, WARM_DARK, NEUTRAL, BLUE_GREY, GREY, COOL_GREY, TAUPE]
    _stones(rng, img, 330, 1.2, 2.7, cols, rare=[RUST_DARK, BROWN], rare_p=0.05,
            snow_v=noise(rng, 16), snow_col=COOL_GREY, snow_at=0.74)
    return img


def sleeper(rng):
    """Creosoted wooden sleepers and old beams, 32 texels/m. Grain runs
    along the tile (u), with dark checks split into it."""
    grain = fbm(rng, [(32, 2), (16, 1), (8, 4)], [0.5, 0.35, 0.15])
    img = ramp(grain, [WARM_BLACK, BROWN_GREY, WARM_GREY, BROWN], dither=0.6)
    for _ in range(16):                              # checks along the grain
        x, y = rng.integers(0, N, 2)
        for i in range(int(rng.integers(5, 22))):
            put(img, x + i, y, INK)
            if i % 7 == 3:
                y += 1 if rng.random() < 0.5 else 0
    for _ in range(40):                              # pale worn flecks
        x, y = rng.integers(0, N, 2)
        put(img, x, y, TAUPE)
    return img


def concrete(rng):
    """Platform and yard slabs, 32 texels/m: 1 m slabs with a dark joint and
    a lit lip, hairline cracks, rust bleeding from the joints."""
    v = fbm(rng, [16, 8, 4], [0.45, 0.35, 0.2])
    img = ramp(v, [SLATE_MID, BLUE_GREY, BLUE_GREY_HI, COOL_GREY], dither=1.0)
    stain = noise(rng, 16) * noise(rng, 8)
    img[(stain > 0.56) & (BAYER > 0.05)] = RUST_DARK
    for j in (0, 32):
        img[j, :] = SLATE_DEEP
        img[:, j] = SLATE_DEEP
        img[(j + 1) % N, :] = np.where((BAYER[0] > 0)[:, None], COOL_GREY, img[(j + 1) % N, :])
        img[:, (j + 1) % N] = np.where((BAYER[:, 0] > 0)[:, None], COOL_GREY, img[:, (j + 1) % N])
    for _ in range(5):                               # cracks: random walks off a joint
        x = int(rng.choice([0, 32])) if rng.random() < 0.5 else int(rng.integers(0, N))
        y = int(rng.integers(0, N)) if x in (0, 32) else int(rng.choice([0, 32]))
        dx, dy = (1, 0) if x in (0, 32) else (0, 1)
        for _ in range(int(rng.integers(8, 20))):
            x += dx + (int(rng.integers(-1, 2)) if dy else 0)
            y += dy + (int(rng.integers(-1, 2)) if dx else 0)
            put(img, x, y, SLATE)
    pits = rng.random((N, N)) < 0.01
    img[pits] = SLATE
    return img


def brick(rng):
    """Old rust-red brick, 32 texels/m: 8 x 4 texel courses (25 x 12.5 cm),
    grey mortar, soot-darkened and chipped bricks."""
    img = np.empty((N, N, 3), np.uint8)
    img[:] = WARM_GREY
    soot = noise(rng, 32)
    reds = [OXBLOOD, RUST_DARK, RUST, RUST_HI]
    for row in range(N // 4):
        off = 4 if row % 2 else 0
        for b in range(N // 8):
            x0, y0 = b * 8 + off, row * 4
            k = rng.random()
            base = RUST if k < 0.45 else RUST_DARK if k < 0.80 else BROWN if k < 0.90 else RUST_HI
            if soot[y0 % N, x0 % N] > 0.62 and rng.random() < 0.7:
                base = OXBLOOD if base != BROWN else WARM_GREY
            top = shade_step(reds, base, +1) if base in reds else TAUPE
            low = shade_step(reds, base, -1) if base in reds else BROWN_GREY
            for dx in range(7):
                for dy in range(3):
                    col = top if dy == 0 and dx < 6 else low if (dy == 2 or dx == 6) else base
                    put(img, x0 + dx, y0 + dy, col)
            if rng.random() < 0.12:                  # chipped corner
                put(img, x0 + int(rng.choice([0, 6])), y0 + int(rng.integers(0, 3)), WARM_DARK)
    return img


def metal_rib(rng):
    """Corrugated galvanised sheet, 32 texels/m: a rib every 4 texels, a
    riveted seam, rust running down from the fixings."""
    img = np.empty((N, N, 3), np.uint8)
    shade = [COOL_GREY, STEEL, COOL_GREY, BLUE_GREY]
    grime = noise(rng, 64, 8)
    for x in range(N):
        img[:, x] = shade[x % 4]
    dark = (grime > 0.6) & (BAYER > 0.1)
    ribs = np.where((np.arange(N) % 4 == 1)[None, :, None], COOL_GREY, BLUE_GREY_HI)
    img[dark] = np.broadcast_to(ribs, (N, N, 3))[dark]
    img[0, :] = SLATE
    img[1, :] = BLUE_GREY_HI
    for x in range(2, N, 8):
        put(img, x, 1, LIGHT_GREY)
    for _ in range(9):                               # rust runs
        x = int(rng.integers(0, N)); y = int(rng.integers(0, 3))
        length = int(rng.integers(8, 34))
        for i in range(length):
            f = i / length
            col = RUST if f < 0.35 else RUST_DARK if f < 0.75 else BROWN
            if f > 0.6 and BAYER[(y + i) % N, x % N] > 0.2 - f * 0.4:
                continue
            put(img, x, y + i, col)
            if i < length * 0.3 and x % 4 == 1:
                put(img, x + 1, y + i, RUST_DARK)
    return img


def boxcar(rng):
    """Oxide-red planked boxcar side, 32 texels/m: 4-texel boards, a
    riveted steel strap across, paint worn through to grey wood."""
    img = np.empty((N, N, 3), np.uint8)
    wear = fbm(rng, [16, 8], [0.6, 0.4])
    tone = [OXBLOOD, RUST_DARK, RUST_DARK, RUST]
    for b in range(N // 4):
        base = tone[rng.integers(0, len(tone))]
        for dx in range(4):
            col = WARM_BLACK if dx == 3 else (shade_step([OXBLOOD, RUST_DARK, RUST, RUST_HI], base, +1)
                                              if dx == 0 else base)
            img[:, b * 4 + dx] = col
    grain = noise(rng, 4, 16)
    img[(grain > 0.7) & (np.arange(N) % 4 != 3)[None, :]] = OXBLOOD
    worn = (wear > 0.82) & (np.arange(N) % 4 != 3)[None, :]
    img[worn] = np.where((BAYER > 0)[..., None], WARM_GREY, GREY)[worn]
    for y in (40, 41, 42, 43):                       # steel strap
        img[y, :] = SLATE if y in (40, 43) else BLUE_GREY
    for x in range(2, N, 8):
        put(img, x, 41, COOL_GREY)
        put(img, x, 42, SLATE)
    for _ in range(6):                               # grime streaks under the strap
        x = int(rng.integers(0, N))
        for i in range(int(rng.integers(4, 14))):
            if BAYER[(44 + i) % N, x] < 0.3:
                put(img, x, 44 + i, OXBLOOD)
    return img


def crate(rng):
    """Weathered grey-brown planks, 32 texels/m: 8-texel boards, butt joints
    with nail heads, grain streaks."""
    img = np.empty((N, N, 3), np.uint8)
    woods = [BROWN_GREY, WARM_GREY, BROWN, TAUPE, DUN]
    for p in range(N // 8):
        base = woods[rng.integers(1, 4)]
        grain = noise(rng, 16, 2)
        for dy in range(8):
            y = p * 8 + dy
            row = np.where((grain[y] > 0.62)[:, None], shade_step(woods, base, -1), base)
            img[y, :] = row
            if dy == 0:
                img[y, :] = shade_step(woods, base, +1)
            if dy == 7:
                img[y, :] = WARM_BLACK
        for j in (int(rng.integers(0, N)), int(rng.integers(0, N))):
            for dy in range(7):
                put(img, j, p * 8 + dy, WARM_DARK)
            for nx in (j - 2, j + 2):
                put(img, nx, p * 8 + 2, WARM_BLACK)
                put(img, nx, p * 8 + 5, WARM_BLACK)
    return img


def rust(rng):
    """Rusted plate (tanks, drums, old machinery), 32 texels/m: grey steel
    eaten by blotches of rust, deep pits in the worst of it."""
    v = fbm(rng, [32, 16, 8, 4], [0.35, 0.3, 0.2, 0.15])
    img = ramp(v, [BLUE_GREY, COOL_GREY, BROWN, RUST_DARK, RUST, RUST_HI], dither=1.2)
    pits = (v > 0.7) & (rng.random((N, N)) < 0.08)
    img[pits] = OXBLOOD
    return img


def steel(rng):
    """Dark painted steel (wagon frames, the loco, cabinets), 32 texels/m:
    nearly flat slate paint, grime running down, rust specks."""
    v = fbm(rng, [(64, 16), 16, (8, 32)], [0.3, 0.3, 0.4])
    img = ramp(v, [SLATE, SLATE_MID, BLUE_GREY, BLUE_GREY_HI], dither=0.9)
    sp = rng.random((N, N))
    img[sp < 0.006] = RUST_DARK
    img[sp > 0.997] = RUST
    return img


TEXTURES = {
    "snow": (snow, 11), "snow_trod": (snow_trod, 12), "ballast": (ballast, 13),
    "sleeper": (sleeper, 14), "concrete": (concrete, 15), "brick": (brick, 16),
    "metal_rib": (metal_rib, 17), "boxcar": (boxcar, 18), "crate": (crate, 19),
    "rust": (rust, 20), "steel": (steel, 21),
}


def draw(name):
    fn, seed = TEXTURES[name]
    img = fn(np.random.default_rng(seed))
    assert img.shape == (N, N, 3)
    ok = {tuple(p) for p in PAL}
    stray = {tuple(p) for p in img.reshape(-1, 3)} - ok
    assert not stray, "%s: off-palette %r" % (name, sorted(stray)[:4])
    return img


def save(img, path):
    surf = pygame.surfarray.make_surface(np.ascontiguousarray(img.transpose(1, 0, 2)))
    pygame.image.save(surf, path)


def sheet(imgs, path, scale=4):
    """Each texture tiled 2x2 at ``scale``x, in a row of labelled cells."""
    cell = N * 2 * scale
    cols = 4
    rows = (len(imgs) + cols - 1) // cols
    out = np.zeros((rows * (cell + 8), cols * (cell + 8), 3), np.uint8)
    for i, img in enumerate(imgs.values()):
        t = np.tile(img, (2, 2, 1)).repeat(scale, 0).repeat(scale, 1)
        y, x = (i // cols) * (cell + 8), (i % cols) * (cell + 8)
        out[y:y + cell, x:x + cell] = t
    save(out, path)


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
        save(imgs[name], os.path.join(ROOT, name + ".png"))
        print("drew", name)
    if out_sheet:
        sheet(imgs, out_sheet)


if __name__ == "__main__":
    pygame.init()
    main(sys.argv[1:])
