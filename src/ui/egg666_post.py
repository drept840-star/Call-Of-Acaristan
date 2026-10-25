"""egg666_post.py - screen effects for the 3D "666" scare.

All of it runs on the small internal buffer (the PS2-look frame), as numpy
views and pygame blits, so the whole chain costs a few milliseconds: lens
distortion, a pinching vignette, chromatic aberration, scanline tears, a
vertical roll, film grain, the red flash and the CRT switch-off.  Levels are
whole numbers and every table is cached, so nothing is built twice.
"""
import numpy as np
import pygame


class Post:
    def __init__(self, w, h):
        self.w, self.h = w, h
        self._vig = {}
        self._barrel = {}
        self._grain = None

    # -- tables ---------------------------------------------------------------
    def _make_vig(self, strength):
        u, v = np.meshgrid(np.linspace(-1.0, 1.0, self.w, dtype=np.float32),
                           np.linspace(-1.0, 1.0, self.h, dtype=np.float32), indexing="ij")
        r = np.sqrt(u * u + v * v) / 1.41
        k = 1.0 - strength * np.clip((r - 0.30) / 0.70, 0.0, 1.0) ** 1.6
        s = pygame.Surface((self.w, self.h))
        pygame.surfarray.blit_array(s, np.repeat((k * 255.0).astype(np.uint8)[:, :, None], 3, axis=2))
        return s

    def _make_barrel(self, k):
        w, h = self.w, self.h
        u, v = np.meshgrid((np.arange(w, dtype=np.float32) + 0.5) / w * 2.0 - 1.0,
                           (np.arange(h, dtype=np.float32) + 0.5) / h * 2.0 - 1.0)
        s = 1.0 + k * (u * u + v * v)
        sx = np.clip((u * s + 1.0) * 0.5 * w - 0.5, 0, w - 1).round().astype(np.int32)
        sy = np.clip((v * s + 1.0) * 0.5 * h - 0.5, 0, h - 1).round().astype(np.int32)
        return (sy * w + sx).ravel()                      # row-major (y, x) source index

    def _make_grain(self):
        rng = np.random.default_rng(666)
        pool = []
        for amp in (8, 16):
            row = []
            for _ in range(3):
                n = rng.integers(0, amp, size=(self.w, self.h), dtype=np.uint8)
                s = pygame.Surface((self.w, self.h))
                pygame.surfarray.blit_array(s, np.repeat(n[:, :, None], 3, axis=2))
                row.append(s)
            pool.append(row)
        return pool

    def warm(self):
        """Build every table now, behind the black cut, so no frame pays for one."""
        for q in range(3, 9):
            self.vignette(pygame.Surface((self.w, self.h)), q)
        for q in range(1, 8):
            self._barrel.setdefault(q, self._make_barrel(0.035 * q))
        if self._grain is None:
            self._grain = self._make_grain()

    # -- effects --------------------------------------------------------------
    def vignette(self, buf, level):
        """level 1..8: how far the corners go to black."""
        s = self._vig.get(level)
        if s is None:
            s = self._vig[level] = self._make_vig(level / 8.0)
        buf.blit(s, (0, 0), special_flags=pygame.BLEND_RGB_MULT)

    def barrel(self, buf, level):
        """level 1..8: the lens pulls the edges in."""
        idx = self._barrel.get(level)
        if idx is None:
            idx = self._barrel[level] = self._make_barrel(0.035 * level)
        p = pygame.surfarray.pixels2d(buf)                # packed pixels, [x, y]
        t = p.T                                           # [y, x]
        t[:] = t.reshape(-1)[idx].reshape(t.shape)
        del p, t

    def chroma(self, buf, px):
        """Red and blue slide apart by ``px`` pixels."""
        if px <= 0:
            return
        a = pygame.surfarray.pixels3d(buf)
        r, b = a[:, :, 0].copy(), a[:, :, 2].copy()
        a[px:, :, 0] = r[:-px]
        a[:-px, :, 2] = b[px:]
        del a

    def tear(self, buf, rg, n, amp):
        """``n`` bands of scanlines kicked sideways by up to ``amp`` pixels."""
        if n <= 0 or amp <= 0:
            return
        a = pygame.surfarray.pixels3d(buf)
        for _ in range(n):
            y0, hh, dx = rg.randrange(0, self.h - 16), rg.randrange(2, 14), rg.randint(-amp, amp)
            if dx:
                a[:, y0:y0 + hh] = np.roll(a[:, y0:y0 + hh], dx, axis=0)
        del a

    def roll(self, buf, dy):
        """The picture slips vertically, wrapping round (a lost vertical hold)."""
        if dy % self.h:
            a = pygame.surfarray.pixels3d(buf)
            a[:] = np.roll(a, dy % self.h, axis=1)
            del a

    def grain(self, buf, level, f):
        """level 1 or 2: zero-mean film grain, a new pattern every frame."""
        if level <= 0:
            return
        if self._grain is None:
            self._grain = self._make_grain()
        row = self._grain[min(2, level) - 1]
        buf.blit(row[f % 3], (0, 0), special_flags=pygame.BLEND_RGB_ADD)
        buf.blit(row[(f + 1) % 3], (0, 0), special_flags=pygame.BLEND_RGB_SUB)

    def flash(self, buf, rgb):
        if rgb[0] or rgb[1] or rgb[2]:
            buf.fill(rgb, special_flags=pygame.BLEND_RGB_ADD)

    def crt_off(self, buf, s):
        """The picture collapses to a bright line: s runs 1 -> 0."""
        h = max(2, int(self.h * s))
        small = pygame.transform.scale(buf, (self.w, h))
        small.fill((int(110 * (1.0 - s)),) * 3, special_flags=pygame.BLEND_RGB_ADD)
        buf.fill((0, 0, 0))
        buf.blit(small, (0, (self.h - h) // 2))
