"""Shared trailer helpers: renderer setup, camera keys, 2D light/rain/grain FX,
letterbox + text. Internal 3D frames are W x H (2.39:1) and are upscaled
nearest-neighbour x3 into the 1920x1080 master (PS1 chunk)."""
import math
import os
import random
import sys

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
if os.path.join(ROOT, "src") not in sys.path:
    sys.path.insert(0, os.path.join(ROOT, "src"))

import pygame  # noqa: E402

FPS = 30
W, H = 640, 268                 # internal 3D frame (2.39:1)
SCALE = 3
OUT_W, OUT_H = 1920, 1080
BAR = (OUT_H - H * SCALE) // 2  # letterbox bar height (138)
ORANGE = (255, 122, 26)
INK = (238, 233, 223)
FONT_DIR = os.path.join(ROOT, "assets", "fonts")
ART = os.path.join(ROOT, "assets", "art")

_fonts = {}


def font(name, size):
    k = (name, size)
    if k not in _fonts:
        fn = {"oswald": "Oswald.ttf", "mono": "IBMPlexMono-SemiBold.ttf",
              "monob": "IBMPlexMono-Bold.ttf"}[name]
        _fonts[k] = pygame.font.Font(os.path.join(FONT_DIR, fn), size)
    return _fonts[k]


# ── maths / timing ──────────────────────────────────────────────────────
def clamp(v, a=0.0, b=1.0):
    return a if v < a else b if v > b else v


def smooth(t):
    t = clamp(t)
    return t * t * (3 - 2 * t)


def ease_out(t):
    t = clamp(t)
    return 1 - (1 - t) ** 3


def ease_in(t):
    t = clamp(t)
    return t * t * t


def seg(t, a, b):
    return clamp((t - a) / (b - a)) if b > a else float(t >= a)


def lerp(a, b, t):
    return a + (b - a) * t


def vlerp(a, b, t):
    return tuple(x + (y - x) * t for x, y in zip(a, b))


def keys(ks, t, ease=smooth):
    """ks: [(time, value_tuple_or_float)] -> eased interpolation."""
    if t <= ks[0][0]:
        return ks[0][1]
    for (t0, a), (t1, b) in zip(ks, ks[1:]):
        if t <= t1:
            u = ease((t - t0) / (t1 - t0))
            return vlerp(a, b, u) if isinstance(a, tuple) else lerp(a, b, u)
    return ks[-1][1]


def shake(t, amp, freq=23.0, seed=0):
    return (amp * math.sin(t * freq + seed) * math.sin(t * freq * 0.37 + 1.3 + seed),
            amp * math.sin(t * freq * 0.81 + 2.1 + seed) * math.cos(t * freq * 0.23 + seed))


# ── renderer ────────────────────────────────────────────────────────────
def renderer(fog, fog_start, fog_end, light=None):
    import engine3d
    r = engine3d.Renderer(W, H, fog=fog, fog_start=fog_start, fog_end=fog_end)
    if light is not None:
        r.light = light
    return r


def light(direction, ambient, diffuse, sky=0.1, tint=(1.0, 1.0, 1.0)):
    import engine3d
    return engine3d.Light(direction=direction, ambient=ambient, diffuse=diffuse, sky=sky, tint=tint)


def gradient(top, bottom, h=H, w=W, mid=None):
    s = pygame.Surface((w, h))
    for y in range(h):
        u = y / (h - 1)
        if mid is not None:
            c = vlerp(top, mid[1], u / mid[0]) if u < mid[0] else vlerp(mid[1], bottom, (u - mid[0]) / (1 - mid[0]))
        else:
            c = vlerp(top, bottom, u)
        pygame.draw.line(s, tuple(int(v) for v in c), (0, y), (w, y))
    return s


def stars(surf, n, seed, ymax, col=(150, 155, 170)):
    rng = random.Random(seed)
    for _ in range(n):
        x, y = rng.randrange(surf.get_width()), rng.randrange(int(ymax))
        k = rng.random()
        surf.set_at((x, y), tuple(int(c * (0.35 + 0.65 * k)) for c in col))


# ── additive light sprites ──────────────────────────────────────────────
_img = {}
_glow_cache = {}


def _art(name):
    if name not in _img:
        _img[name] = pygame.image.load(os.path.join(ART, name + ".png")).convert()
    return _img[name]


def glow(surf, x, y, r, col, kind="L_radial"):
    """Additive soft light (r = radius in pixels)."""
    r = int(r)
    if r < 1 or r > 900:
        return
    q = (kind, max(1, r // 2) * 2, tuple(int(c) // 4 * 4 for c in col))
    g = _glow_cache.get(q)
    if g is None:
        base = pygame.transform.smoothscale(_art(kind), (q[1] * 2, q[1] * 2))
        tint = pygame.Surface(base.get_size())
        tint.fill(q[2])
        base.blit(tint, (0, 0), special_flags=pygame.BLEND_RGB_MULT)
        g = base
        if len(_glow_cache) > 600:
            _glow_cache.clear()
        _glow_cache[q] = g
    surf.blit(g, (int(x) - q[1], int(y) - q[1]), special_flags=pygame.BLEND_RGB_ADD)


def glow_at(r, surf, p, radius_m, col, kind="L_radial"):
    """Glow at world point p sized in metres (no depth test)."""
    pr = r.project(p)
    if pr is None:
        return None
    sx, sy, z = pr
    glow(surf, sx, sy, radius_m * r.focal / z, col, kind)
    return pr


def glow_sprite(radius_m, col, kind="L_radial"):
    """engine3d sprite callback (depth-masked by the renderer)."""
    def draw(surf, sx, sy, scale, z):
        glow(surf, sx, sy, radius_m * scale, col, kind)
    return draw


def beam(r, surf, a, b, width_a, width_b, col):
    """Additive light shaft from world a to world b (2D quad)."""
    pa, pb = r.project(a), r.project(b)
    if pa is None or pb is None:
        return
    dx, dy = pb[0] - pa[0], pb[1] - pa[1]
    ln = math.hypot(dx, dy) or 1.0
    nx, ny = -dy / ln, dx / ln
    wa = width_a * r.focal / pa[2]
    wb = width_b * r.focal / pb[2]
    pts = [(pa[0] + nx * wa, pa[1] + ny * wa), (pb[0] + nx * wb, pb[1] + ny * wb),
           (pb[0] - nx * wb, pb[1] - ny * wb), (pa[0] - nx * wa, pa[1] - ny * wa)]
    tmp = pygame.Surface(surf.get_size())
    tmp.fill((0, 0, 0))
    pygame.draw.polygon(tmp, col, pts)
    inner = [(pa[0] + nx * wa * .45, pa[1] + ny * wa * .45), (pb[0] + nx * wb * .45, pb[1] + ny * wb * .45),
             (pb[0] - nx * wb * .45, pb[1] - ny * wb * .45), (pa[0] - nx * wa * .45, pa[1] - ny * wa * .45)]
    pygame.draw.polygon(tmp, tuple(min(255, int(c * 1.8)) for c in col), inner)
    surf.blit(tmp, (0, 0), special_flags=pygame.BLEND_RGB_ADD)


def fire_sprite(fl, size=0.55, seed=0):
    """Flickering flame: a cluster of tapered tongues (outer red-orange,
    orange, hot core) plus a few rising sparks, drawn additively."""
    def draw(surf, sx, sy, scale, z):
        r = max(2, int(size * scale))
        if r > 160:
            return
        g = pygame.Surface((r * 5, r * 6))
        g.fill((0, 0, 0))
        cx, by = int(r * 2.5), r * 5
        rng = random.Random(seed * 131 + 7)
        n = 5
        layers = (((150, 46, 6), 1.0), ((235, 120, 24), 0.68), ((255, 214, 120), 0.36))
        tongues = []
        for k in range(n):
            u = (k + 0.5) / n - 0.5
            ph = rng.uniform(0, 6.3)
            hk = (1.0 - abs(u) * 1.2) * rng.uniform(0.75, 1.1)
            h = r * 3.4 * hk * (0.75 + 0.35 * math.sin(fl * 7.0 + ph) + 0.15 * fl)
            sway = r * 0.45 * math.sin(fl * 5.0 + ph * 1.3)
            tongues.append((cx + u * r * 1.9, max(r * 0.6, h), sway, r * rng.uniform(0.38, 0.55)))
        for col, k in layers:
            for x, h, sway, w in tongues:
                hh, ww = h * k, max(1.0, w * (0.55 + 0.45 * k))
                pts = [(x - ww, by), (x - ww * 0.75, by - hh * 0.35), (x + sway * 0.5, by - hh * 0.75),
                       (x + sway, by - hh), (x + ww * 0.7, by - hh * 0.4), (x + ww, by)]
                pygame.draw.polygon(g, col, pts)
        pygame.draw.ellipse(g, (255, 240, 200), (cx - r * 0.7, by - r * 0.35, r * 1.4, r * 0.5))
        sr = random.Random(int(fl * 977) + seed)
        for _ in range(3):
            px, py = cx + sr.uniform(-1.2, 1.2) * r, by - sr.uniform(2.0, 5.0) * r
            if 0 <= px < g.get_width() and 0 <= py < g.get_height():
                g.fill((255, 170, 70), (int(px), int(py), max(1, r // 6), max(1, r // 6)))
        surf.blit(g, (sx - cx, sy - by + r // 2), special_flags=pygame.BLEND_RGB_ADD)
    return draw


def smoke_sprite(age, col=(34, 33, 34), size=0.6, grow=2.4, alpha=110):
    def draw(surf, sx, sy, scale, z):
        r = max(2, int((size + age * grow) * scale))
        if r > 300:
            return
        a = int(alpha * (1 - age))
        if a <= 2:
            return
        g = pygame.Surface((r * 2, r * 2), pygame.SRCALPHA)
        pygame.draw.circle(g, (*col, a), (r, r), r)
        surf.blit(g, (sx - r, sy - r))
    return draw


def muzzle_sprite(size=0.5, direction=None, seed=0):
    """Muzzle flash anchored at the barrel tip. ``direction`` = screen-space
    (dx, dy) of the barrel; the flash is a forward cone + short side spikes
    + small hot core, all starting AT the tip (nothing behind it)."""
    def draw(surf, sx, sy, scale, z):
        r = max(2, int(size * scale))
        if r > 90:
            return
        dx, dy = direction if direction else (1.0, 0.0)
        ln = math.hypot(dx, dy) or 1.0
        dx, dy = dx / ln, dy / ln
        nx, ny = -dy, dx
        rng = random.Random(seed)
        L = r * rng.uniform(2.2, 3.2)
        Wd = r * 0.55
        g = pygame.Surface((r * 8, r * 8))
        g.fill((0, 0, 0))
        c = r * 4
        def P(f, s_):
            return (c + dx * f + nx * s_, c + dy * f + ny * s_)
        pygame.draw.polygon(g, (200, 90, 20), [P(0, -Wd), P(L * 0.5, -Wd * 1.1), P(L, 0), P(L * 0.5, Wd * 1.1), P(0, Wd)])
        pygame.draw.polygon(g, (255, 190, 90), [P(0, -Wd * 0.6), P(L * 0.45, -Wd * 0.6), P(L * 0.75, 0), P(L * 0.45, Wd * 0.6), P(0, Wd * 0.6)])
        for sgn in (-1, 1):
            k = rng.uniform(0.8, 1.3)
            pygame.draw.polygon(g, (240, 150, 60), [P(r * 0.1, sgn * r * 0.15), P(r * 0.5, sgn * r * 1.3 * k), P(r * 0.45, sgn * r * 0.1)])
        pygame.draw.circle(g, (255, 250, 225), (int(c + dx * r * 0.35), int(c + dy * r * 0.35)), max(1, int(r * 0.45)))
        surf.blit(g, (sx - c, sy - c), special_flags=pygame.BLEND_RGB_ADD)
        glow(surf, sx + dx * r, sy + dy * r, r * 2.2, (110, 60, 20))
    return draw


def muzzle_at(r, muzzle, back, size=0.12, seed=0):
    """Sprite for a flash at world ``muzzle``; ``back`` = a world point behind
    it on the barrel (e.g. the hand), used for the screen direction."""
    a, b = r.project(muzzle), r.project(back)
    if a is None or b is None:
        return None
    return muzzle_sprite(size, (a[0] - b[0], a[1] - b[1]), seed)


_WARP_CACHE = {}


def warp_sprite(img, quad):
    """Sprite callback that perspective-maps ``img`` (RGBA Surface) onto the
    screen quad [TL, TR, BR, BL] (pixel coords) - for paper/text that has to
    lie flat on a surface. Anchor it at the quad's centre in world space."""
    import cv2
    import numpy as np
    rgba = _WARP_CACHE.get(id(img))
    if rgba is None:
        arr = pygame.surfarray.array3d(img).swapaxes(0, 1)
        alpha = pygame.surfarray.array_alpha(img).T
        rgba = np.ascontiguousarray(np.dstack([arr, alpha]).astype(np.uint8))
        _WARP_CACHE[id(img)] = rgba
    h, w = rgba.shape[:2]
    src = np.float32([[0, 0], [w, 0], [w, h], [0, h]])

    def draw(surf, sx, sy, scale, z):
        dst = np.float32(quad)
        x0, y0 = np.floor(dst.min(0)).astype(int)
        x1, y1 = np.ceil(dst.max(0)).astype(int)
        SW, SH = surf.get_size()
        x0, y0 = max(0, x0), max(0, y0)
        x1, y1 = min(SW, x1), min(SH, y1)
        if x1 - x0 < 2 or y1 - y0 < 2:
            return
        M = cv2.getPerspectiveTransform(src, dst - np.float32([x0, y0]))
        out = cv2.warpPerspective(rgba, M, (x1 - x0, y1 - y0), flags=cv2.INTER_AREA,
                                  borderMode=cv2.BORDER_CONSTANT, borderValue=(0, 0, 0, 0))
        g = pygame.image.frombuffer(np.ascontiguousarray(out).tobytes(), (x1 - x0, y1 - y0), "RGBA")
        surf.blit(g, (x0, y0))
    return draw


def quad_on(r, center, half_x, half_z, y_off=0.0):
    """Screen quad [TL, TR, BR, BL] of a horizontal rectangle (top = +z edge)."""
    cx, cy, cz = center
    pts = [(cx - half_x, cy + y_off, cz + half_z), (cx + half_x, cy + y_off, cz + half_z),
           (cx + half_x, cy + y_off, cz - half_z), (cx - half_x, cy + y_off, cz - half_z)]
    out = []
    for p in pts:
        q = r.project(p)
        if q is None:
            return None
        out.append((q[0], q[1]))
    return out


# ── weather / grade ─────────────────────────────────────────────────────
class Rain:
    def __init__(self, n=420, seed=3, slant=0.18, speed=900, length=(6, 16), col=(120, 130, 150)):
        rng = random.Random(seed)
        self.drops = [(rng.random() * (W + 80) - 40, rng.random() * H, rng.uniform(*length),
                       rng.uniform(0.7, 1.3), rng.random()) for _ in range(n)]
        self.slant, self.speed, self.col = slant, speed, col

    def draw(self, surf, t, k=1.0, dx=0.0):
        if k <= 0:
            return
        tmp = pygame.Surface((W, H))
        tmp.fill((0, 0, 0))
        for x0, y0, ln, sp, b in self.drops:
            y = (y0 + t * self.speed * sp) % (H + 30) - 15
            x = (x0 + y * self.slant + dx) % (W + 80) - 40
            c = tuple(int(v * k * (0.45 + 0.55 * b)) for v in self.col)
            pygame.draw.line(tmp, c, (x, y), (x + ln * self.slant, y + ln))
        surf.blit(tmp, (0, 0), special_flags=pygame.BLEND_RGB_ADD)


class Grade:
    """Film grain + vignette at internal res (chunky, matches the PS1 look)."""
    def __init__(self, seed=7):
        rng = random.Random(seed)
        self.noise = []
        for _ in range(6):
            s = pygame.Surface((W, H))
            arr = pygame.PixelArray(s)
            for y in range(0, H):
                for x in range(0, W, 1):
                    v = int(abs(rng.gauss(0, 7)))
                    arr[x, y] = (v, v, v)
            del arr
            self.noise.append(s)
        self.vig = pygame.Surface((W, H), pygame.SRCALPHA)
        for y in range(H):
            for x in range(0, W, 2):
                dx, dy = (x - W / 2) / (W / 2), (y - H / 2) / (H / 2)
                a = int(clamp((dx * dx * 0.55 + dy * dy * 0.75 - 0.25) * 0.9) * 200)
                self.vig.fill((0, 0, 0, a), (x, y, 2, 1))

    def apply(self, surf, frame, grain=1.0, vignette=True):
        if vignette:
            surf.blit(self.vig, (0, 0))
        if grain > 0:
            a = self.noise[frame % 6]
            b = self.noise[(frame * 7 + 3) % 6]
            surf.blit(a, (0, 0), special_flags=pygame.BLEND_RGB_ADD)
            surf.blit(b, (0, 0), special_flags=pygame.BLEND_RGB_SUB)


def text_center(canvas, txt, fnt, col, cy, alpha=255, spacing=0, cx=None):
    if spacing:
        glyphs = [fnt.render(ch, True, col) for ch in txt]
        w = sum(g.get_width() for g in glyphs) + spacing * (len(glyphs) - 1)
        s = pygame.Surface((w, fnt.get_height()), pygame.SRCALPHA)
        x = 0
        for g in glyphs:
            s.blit(g, (x, 0)); x += g.get_width() + spacing
    else:
        s = fnt.render(txt, True, col)
    if alpha < 255:
        s.set_alpha(alpha)
    cx = OUT_W // 2 if cx is None else cx
    canvas.blit(s, (cx - s.get_width() // 2, cy - s.get_height() // 2))
    return s.get_width()


def typed(txt, t, cps=24):
    n = int(max(0, t) * cps)
    return txt[:n]
