"""KRAPNET Pre-Game Launcher window (Pygame) for Call of Acaristan.

Opens a terminal-styled launcher before the main game starts. All layout is
authored in a fixed 860x520 logical canvas (``L_WIDTH`` x ``L_HEIGHT``) which is
presented to the real window scaled to fit and letterboxed, so the window can be
resized freely (or opened larger on a 4K display) without touching layout code.
Mouse input is mapped back into canvas space by ``logical_mouse``.

The window checks for updates in a background daemon thread, displays a
non-intrusive "NEW VERSION AVAILABLE" notice card with changelog & delta size,
and can patch the game in-place with a live progress bar before launching.

PLAY GAME is gated on a pending update by default (``gate_play_on_update`` in
``launcher_config.json``): pressing it applies the patch first and only then
starts the game, because a running ``.exe``/``.dll``/``.pyd`` cannot be replaced
and patching after launch is exactly the case the ``.old`` rename dance exists
for. Set the key to ``false`` to launch immediately instead.
"""
from __future__ import annotations

import json
import math
import os
from pathlib import Path
import subprocess
import sys
import threading

import pygame
from engine.assets import load_image as _load_image
from engine.core import RngStreams as _RngStreams
from engine.core import now_ms as _now_ms
from engine.text import ellipsize as _ellipsize
from engine.text import load_face as _load_face
from engine.text import wrap_lines as _wrap_lines

from .updater import (
    DemoUpdateServer,
    LocalVersion,
    RemoteUpdateInfo,
    UpdateCheckResult,
    apply_update,
    check_for_updates,
    cleanup_old_binaries,
    format_bytes,
    itch_receipt_path,
    load_launcher_config,
    load_local_version,
    recover_interrupted_update,
)

# Logical canvas: every draw call below is authored in these coordinates.
L_WIDTH = 860
L_HEIGHT = 520

C_BLACK = (6, 8, 12)
C_PANEL = (10, 14, 20, 228)
C_WHITE = (240, 240, 240)
C_GREY = (150, 155, 162)
C_DIM = (95, 102, 110)
C_ORANGE = (255, 120, 0)
C_AMBER = (255, 185, 50)
C_GREEN = (55, 220, 115)
C_KRAP_BLUE = (55, 125, 185)
C_RED = (225, 75, 65)


# ── visual helpers (all built once; nothing here runs per-frame except
#    _lerp_col and _draw_brackets, which only issue draw calls) ─────────────


def _lerp_col(a, b, t):
    t = max(0.0, min(1.0, t))
    return (
        int(a[0] + (b[0] - a[0]) * t),
        int(a[1] + (b[1] - a[1]) * t),
        int(a[2] + (b[2] - a[2]) * t),
    )


def _make_vignette(size, reach=170, strength=150):
    """Dark edges, built once. Blit over the background each frame."""
    w, h = size
    surf = pygame.Surface(size, pygame.SRCALPHA)
    for i in range(reach):
        a = int(strength * (1 - i / reach) ** 2.2)
        if a > 0:
            pygame.draw.rect(surf, (0, 0, 0, a), (i, i, w - 2 * i, h - 2 * i), 1)
    return surf


def _make_glow_sprite(radius, color, peak=0.85):
    """Radial glow for BLEND_ADD (black = no effect), with a hot core."""
    d = radius * 2 + 1
    s = pygame.Surface((d, d))
    for ring in range(radius, 0, -1):
        k = peak * (1 - ring / radius) ** 2
        pygame.draw.circle(s, tuple(int(c * k) for c in color), (radius, radius), ring)
    pygame.draw.circle(s, (255, 200, 110), (radius, radius), max(1, radius // 4))
    return s


def _render_glow_text(font, text, color, glow_color, radius=4, alpha=12, shadow=(3, 3)):
    """Pre-render text with soft glow + drop shadow. Returns (surface, pad)."""
    pad = radius + max(shadow) + 1
    base = font.render(text, True, color)
    surf = pygame.Surface((base.get_width() + pad * 2, base.get_height() + pad * 2), pygame.SRCALPHA)
    glow = font.render(text, True, glow_color)
    glow.set_alpha(alpha)
    for dx in range(-radius, radius + 1, 2):
        for dy in range(-radius, radius + 1, 2):
            if dx * dx + dy * dy <= radius * radius:
                surf.blit(glow, (pad + dx, pad + dy))
    surf.blit(font.render(text, True, (0, 0, 0)), (pad + shadow[0], pad + shadow[1]))
    surf.blit(base, (pad, pad))
    return surf, pad


def _make_gradient_rule(w, h, color):
    """Horizontal rule that fades out to the right."""
    surf = pygame.Surface((w, h), pygame.SRCALPHA)
    for x in range(w):
        a = int(40 + 215 * (1 - x / w) ** 1.5)
        pygame.draw.line(surf, (*color, a), (x, 0), (x, h - 1))
    return surf


def _draw_brackets(surf, rect, color, size=12, width=2):
    x0, y0, x1, y1 = rect.left, rect.top, rect.right - 1, rect.bottom - 1
    for cx, cy, sx, sy in ((x0, y0, 1, 1), (x1, y0, -1, 1), (x0, y1, 1, -1), (x1, y1, -1, -1)):
        pygame.draw.line(surf, color, (cx, cy), (cx + sx * size, cy), width)
        pygame.draw.line(surf, color, (cx, cy), (cx, cy + sy * size), width)


def play_requires_update(
    result: UpdateCheckResult | None,
    config: dict | None = None,
) -> bool:
    """True when PLAY GAME must apply a pending patch before launching.

    Default is gated (``gate_play_on_update`` absent => True): patching a tree
    the game is already running from cannot replace a locked binary, so the
    patch has to happen first.
    """
    cfg = config or {}
    if not bool(cfg.get("gate_play_on_update", True)):
        return False
    return bool(
        result is not None
        and result.status == "update_available"
        and result.remote is not None
    )


class _LauncherButton:
    """KRAPNET-styled launcher button with dt-based hover animation.

    The plate (background, border, accent bar) is drawn exactly where the
    hitbox is and never moves — a button that slides away from the cursor
    decouples what you see from what you click. Hover feedback is: instant
    colour change (border/text), the "> " prefix, and the label easing 6px
    right (`slide` is a 0..1 progress). `glow` drives the alpha pulse the same
    way. The two translucent layers are allocated once per button and
    re-filled each frame, so nothing here creates a Surface in the draw path.
    """

    def __init__(self, x: int, y: int, w: int, h: int, text: str, primary: bool = False):
        self.x = x
        self.y = y
        self.w = w
        self.h = h
        self.text = text
        self.primary = primary
        self.enabled = True
        self.badge = ""
        self.is_hovered = False
        self.is_selected = False
        self.slide = 0.0
        self.glow = 0.0
        self.flash = 0.0
        self.rect = pygame.Rect(x, y, w, h)
        self._bg = pygame.Surface((w, h), pygame.SRCALPHA)
        self._flash_surf = pygame.Surface((w, h), pygame.SRCALPHA)

    def check_hover(self, mouse_pos: tuple[int, int]) -> bool:
        if not self.enabled:
            self.is_hovered = False
            return False
        self.is_hovered = self.rect.collidepoint(mouse_pos)
        return self.is_hovered

    def press(self) -> None:
        self.flash = 0.16

    def update(self, dt: float) -> None:
        active = self.enabled and (self.is_hovered or self.is_selected)
        # Snappy in, smooth out: a hover that needs a fifth of a second to
        # arrive reads as "unresponsive"; one that vanishes between two frames
        # reads as "flickery". 30/s settles in ~3 frames, 10/s eases out.
        rate = 30.0 if active else 10.0
        k = min(1.0, dt * rate)
        target = 1.0 if active else 0.0
        self.slide += (target - self.slide) * k
        self.glow += (target - self.glow) * k
        if self.flash > 0.0:
            self.flash = max(0.0, self.flash - dt)

    def draw(self, surf: pygame.Surface, font: pygame.font.Font, badge_font: pygame.font.Font) -> None:
        # The plate never moves: hover styling must not shift the thing the
        # user is pointing at out from under the cursor (the hitbox `rect` and
        # the drawn rect stay identical). Only the label nudges.
        r = pygame.Rect(self.x, self.y, self.w, self.h)
        active = self.is_hovered or self.is_selected

        if not self.enabled:
            self._bg.fill((14, 17, 22, 140))
            border_col = (40, 45, 52)
            bar_col = (55, 60, 68)
            txt_col = (85, 90, 98)
        elif self.primary:
            self._bg.fill((32, 22, 12, int(190 + 45 * self.glow)))
            if active:
                border_col = C_ORANGE
            else:
                # Idle pulse so PLAY reads as the primary action.
                pulse = 0.5 + 0.5 * math.sin(_now_ms() / 450.0)
                border_col = _lerp_col((150, 78, 18), (215, 110, 25), pulse)
            bar_col = C_ORANGE
            txt_col = C_WHITE
        else:
            self._bg.fill((14, 20, 28, int(165 + 50 * self.glow)))
            border_col = C_ORANGE if active else (45, 62, 82)
            bar_col = C_ORANGE if active else C_KRAP_BLUE
            txt_col = C_WHITE if active else C_GREY

        if self.enabled:
            # Faint top sheen.
            pygame.draw.line(self._bg, (255, 255, 255, 28 if active else 12), (1, 1), (self.w - 2, 1))

        surf.blit(self._bg, r.topleft)
        pygame.draw.rect(surf, border_col, r, 1)
        pygame.draw.rect(surf, bar_col, (r.x, r.y, 5 + int(round(self.slide * 3.0)), r.h))

        if self.flash > 0.0:
            self._flash_surf.fill((255, 220, 170, int(110 * (self.flash / 0.16))))
            surf.blit(self._flash_surf, r.topleft)

        prefix = "> " if active and self.enabled else ""
        lbl = font.render(prefix + self.text, True, txt_col)
        dx = int(round(self.slide * 6.0))
        surf.blit(lbl, (r.x + 16 + dx, r.y + (r.h - lbl.get_height()) // 2))

        if self.badge:
            b_surf = badge_font.render(self.badge, True, C_BLACK if self.enabled else C_DIM)
            bw = b_surf.get_width() + 12
            bh = b_surf.get_height() + 4
            bx = r.right - bw - 10
            by = r.y + (r.h - bh) // 2
            b_col = C_ORANGE if self.enabled else (35, 40, 48)
            pygame.draw.rect(surf, b_col, (bx, by, bw, bh), border_radius=2)
            surf.blit(b_surf, (bx + 6, by + 2))


def _read_save_summary(root: Path) -> str:
    spath = root / "save_data.json"
    if not spath.is_file():
        return "NO ACTIVE CAMPAIGN SAVE"
    try:
        data = json.loads(spath.read_text(encoding="utf-8"))
        idx = int(data.get("active_slot") or 0)
        slots = data.get("slots") or []
        if 0 <= idx < len(slots) and isinstance(slots[idx], dict):
            slot = slots[idx]
            if slot.get("occupied"):
                label = str(slot.get("last_completed_label") or slot.get("progress") or "Campaign started")
                return f"SLOT {idx + 1}: {label.upper()[:30]}"
        return f"SLOT {idx + 1}: EMPTY"
    except Exception:
        return "SAVE DATA READY"


def _draw_tactical_cursor(surf: pygame.Surface, pos: tuple[int, int], hot: bool) -> None:
    x, y = pos
    fill = C_ORANGE if hot else C_WHITE
    pts = [(x, y), (x, y + 17), (x + 5, y + 13), (x + 9, y + 20), (x + 12, y + 18), (x + 8, y + 11), (x + 14, y + 11)]
    shadow = [(px + 2, py + 2) for px, py in pts]
    pygame.draw.polygon(surf, (0, 0, 0), shadow)
    pygame.draw.polygon(surf, fill, pts)
    pygame.draw.polygon(surf, (20, 20, 25), pts, 1)


class LauncherApp:
    """Self-contained Pygame pre-game launcher and updater."""

    def __init__(
        self,
        root: Path,
        demo_update: bool = False,
        target_root: Path | None = None,
    ):
        self.root = root
        self.demo_update = demo_update
        self.target_root = target_root
        self.demo_server: DemoUpdateServer | None = None

        cleanup_old_binaries(self.root)
        # A patch interrupted by a crash / power loss is rolled back before we
        # look at versions, so the install is never a mix of two builds.
        self.recovery_status = recover_interrupted_update(self.root)
        self.config = load_launcher_config(self.root)
        if self.demo_update:
            self.demo_server = DemoUpdateServer(self.root)
            self.config["update_url"] = self.demo_server.start()
            if self.target_root is None:
                # In demo mode, write patched demo files to build/demo_install so repo stays clean
                self.target_root = self.root / "build" / "demo_install"
                self.target_root.mkdir(parents=True, exist_ok=True)

        self.local_version: LocalVersion = load_local_version(self.root)
        self.save_summary = _read_save_summary(self.root)
        # itch-managed install: the itch app is the updater, so the launcher
        # says so instead of advertising a relay check it cannot fulfill.
        self.itch_receipt = itch_receipt_path(self.root)

        self.check_result: UpdateCheckResult | None = None
        self.is_checking = False
        self.is_updating = False
        self.update_done = False
        self.update_error = ""
        self.progress_stage = ""
        self.progress_frac = 0.0
        self.progress_detail = ""
        self._lock = threading.Lock()
        # PLAY pressed while an update is pending: patch, then launch.
        self._play_after_update = False
        self._pending_action: str | None = None

        self._rng = _RngStreams(1986).stream("launcher_fx")
        self._rain = [
            [
                self._rng.uniform(0, L_WIDTH),
                self._rng.uniform(0, L_HEIGHT),
                self._rng.uniform(260, 420),
                self._rng.randint(10, 20),
            ]
            for _ in range(55)
        ]
        self._embers = [
            [
                self._rng.uniform(0, L_WIDTH),
                self._rng.uniform(0, L_HEIGHT),
                self._rng.uniform(-18, 18),
                self._rng.uniform(22, 52),
                self._rng.uniform(1.5, 3.2),
            ]
            for _ in range(24)
        ]

        self._card_key: str | None = None   # right-panel state, for fade-in
        self._card_fade = 0.0
        self._shown_frac = 0.0              # eased progress bar value
        self._dt = 1.0 / 60.0

        self._init_pygame()

    # ── window / canvas ────────────────────────────────────────────────────

    def _default_window_size(self) -> tuple[int, int]:
        """Largest integer multiple of the canvas that fits comfortably on screen."""
        try:
            info = pygame.display.Info()
            dw, dh = int(info.current_w), int(info.current_h)
        except Exception:
            dw, dh = 0, 0
        if dw <= 0 or dh <= 0:
            return (L_WIDTH, L_HEIGHT)
        usable_w, usable_h = dw * 0.85, dh * 0.85
        scale = min(usable_w / L_WIDTH, usable_h / L_HEIGHT)
        scale = max(1.0, min(2.0, float(int(scale))))
        return (int(L_WIDTH * scale), int(L_HEIGHT * scale))

    def _init_pygame(self) -> None:
        pygame.init()
        pygame.display.set_caption("Call of Acaristan — KRAPNET Launcher")
        # `screen` is the fixed logical canvas; `display` is the real window.
        self.display = pygame.display.set_mode(self._default_window_size(), pygame.RESIZABLE)
        self.screen = pygame.Surface((L_WIDTH, L_HEIGHT)).convert()
        self._scaled: pygame.Surface | None = None
        pygame.mouse.set_visible(False)
        self.clock = pygame.time.Clock()

        icon_path = self.root / "assets" / "logo.ico"
        if icon_path.is_file():
            try:
                pygame.display.set_icon(_load_image(str(icon_path)))
            except Exception:
                pass

        fdir = self.root / "assets" / "fonts"
        oswald = str(fdir / "Oswald.ttf")
        mono_b = str(fdir / "IBMPlexMono-Bold.ttf")
        mono_sb = str(fdir / "IBMPlexMono-SemiBold.ttf")
        mono_r = str(fdir / "IBMPlexMono-Regular.ttf")

        self.font_title = _load_face(oswald, 40, "Impact")
        self.font_card_hdr = _load_face(oswald, 21, "Impact")
        self.font_btn = _load_face(mono_sb, 17, "Consolas", bold=True)
        self.font_badge = _load_face(mono_b, 11, "Consolas", bold=True)
        self.font_mono_b = _load_face(mono_b, 13, "Consolas", bold=True)
        self.font_mono = _load_face(mono_r, 12, "Consolas")
        self.font_small = _load_face(mono_r, 11, "Consolas")

        bg_path = self.root / "assets" / "bg.jpg"
        if bg_path.is_file():
            try:
                raw_bg = _load_image(str(bg_path), convert="opaque")
                self.bg_surf = pygame.transform.smoothscale(raw_bg, (L_WIDTH, L_HEIGHT))
            except Exception:
                self.bg_surf = pygame.Surface((L_WIDTH, L_HEIGHT))
                self.bg_surf.fill((12, 16, 24))
        else:
            self.bg_surf = pygame.Surface((L_WIDTH, L_HEIGHT))
            self.bg_surf.fill((12, 16, 24))

        self.dim_overlay = pygame.Surface((L_WIDTH, L_HEIGHT), pygame.SRCALPHA)
        self.dim_overlay.fill((6, 9, 14, 185))
        for y in range(0, L_HEIGHT, 3):
            pygame.draw.line(self.dim_overlay, (0, 0, 0, 28), (0, y), (L_WIDTH, y), 1)

        # Pre-rendered visual layers (built once, blitted every frame).
        self.vignette = _make_vignette((L_WIDTH, L_HEIGHT))
        self._ember_sprites = {r: _make_glow_sprite(r * 4, (255, 135, 35)) for r in range(1, 5)}
        self._title_surf, self._title_pad = _render_glow_text(
            self.font_title, "CALL OF ACARISTAN", C_WHITE, C_ORANGE
        )
        self._title_rule = _make_gradient_rule(286, 3, C_ORANGE)

        # Pre-allocated translucent plates (no Surface churn in the draw path).
        self._plate_cache: dict[tuple[int, int], pygame.Surface] = {}

        self.btn_play = _LauncherButton(28, 252, 286, 44, "PLAY GAME", primary=True)
        self.btn_update = _LauncherButton(28, 308, 286, 42, "UPDATE NOW", primary=False)
        self.btn_check = _LauncherButton(28, 362, 286, 38, "CHECK FOR UPDATES", primary=False)
        self.btn_exit = _LauncherButton(28, 412, 286, 38, "EXIT", primary=False)
        self.buttons = [self.btn_play, self.btn_update, self.btn_check, self.btn_exit]
        self.focus_idx = 0

    def _plate(self, w: int, h: int) -> pygame.Surface:
        """A reusable SRCALPHA surface of (w, h); caller fills it each frame."""
        key = (int(w), int(h))
        surf = self._plate_cache.get(key)
        if surf is None:
            surf = pygame.Surface(key, pygame.SRCALPHA)
            self._plate_cache[key] = surf
        return surf

    def logical_mouse(self) -> tuple[int, int]:
        """Map the real window cursor position into canvas coordinates."""
        raw = pygame.mouse.get_pos()
        dw, dh = self.display.get_size()
        if (dw, dh) == (L_WIDTH, L_HEIGHT):
            return raw
        scale = min(dw / L_WIDTH, dh / L_HEIGHT)
        if scale <= 0:
            return raw
        scaled_w, scaled_h = int(L_WIDTH * scale), int(L_HEIGHT * scale)
        ox, oy = (dw - scaled_w) // 2, (dh - scaled_h) // 2
        return (int((raw[0] - ox) / scale), int((raw[1] - oy) / scale))

    def present(self) -> None:
        """Blit the logical canvas to the window, scaled to fit with letterboxing."""
        dw, dh = self.display.get_size()
        if (dw, dh) == (L_WIDTH, L_HEIGHT):
            self.display.blit(self.screen, (0, 0))
        else:
            scale = min(dw / L_WIDTH, dh / L_HEIGHT)
            w = max(1, int(L_WIDTH * scale))
            h = max(1, int(L_HEIGHT * scale))
            if self._scaled is None or self._scaled.get_size() != (w, h):
                self._scaled = pygame.Surface((w, h)).convert()
            pygame.transform.scale(self.screen, (w, h), self._scaled)
            self.display.fill((0, 0, 0))
            self.display.blit(self._scaled, ((dw - w) // 2, (dh - h) // 2))
        pygame.display.flip()

    # ── background work ───────────────────────────────────────────────────

    def start_background_check(self) -> None:
        with self._lock:
            if self.is_checking or self.is_updating:
                return
            self.is_checking = True
            self.update_error = ""

        def _worker() -> None:
            res = check_for_updates(self.root, self.config)
            with self._lock:
                self.check_result = res
                self.is_checking = False

        threading.Thread(target=_worker, daemon=True).start()

    def start_background_update(self) -> None:
        with self._lock:
            if self.is_updating or self.check_result is None or self.check_result.remote is None:
                return
            remote = self.check_result.remote
            self.is_updating = True
            self.update_error = ""
            self.progress_stage = "INITIALIZING"
            self.progress_frac = 0.01
            self.progress_detail = f"Preparing update {remote.display_tag}..."

        def _progress(stage: str, frac: float, detail: str) -> None:
            with self._lock:
                self.progress_stage = stage
                self.progress_frac = frac
                self.progress_detail = detail

        def _worker() -> None:
            try:
                new_local = apply_update(
                    self.root,
                    remote,
                    config=self.config,
                    progress_cb=_progress,
                    target_root=self.target_root,
                )
                with self._lock:
                    self.local_version = new_local
                    self.is_updating = False
                    self.update_done = True
                    self.check_result = UpdateCheckResult(
                        status="up_to_date",
                        local=new_local,
                        remote=remote,
                        message=f"UPDATED TO {new_local.display_tag}",
                    )
                    if self._play_after_update:
                        # Patch landed: hand the run loop its 'play' decision.
                        self._play_after_update = False
                        self._pending_action = "play"
            except Exception as exc:
                with self._lock:
                    self.is_updating = False
                    self.update_error = str(exc)
                    # apply_update rolled the tree back, so launching is safe;
                    # let the player retry instead of silently exiting.
                    self._play_after_update = False

        threading.Thread(target=_worker, daemon=True).start()

    def _update_pending(self) -> bool:
        with self._lock:
            res = self.check_result
            done = self.update_done
        return (not done) and play_requires_update(res, self.config)

    def _sync_buttons(self) -> None:
        with self._lock:
            checking = self.is_checking
            updating = self.is_updating
            res = self.check_result
            done = self.update_done
            play_after = self._play_after_update
            frac = self.progress_frac

        self.btn_check.enabled = not (checking or updating)
        self.btn_check.text = "CHECKING RELAY..." if checking else "CHECK FOR UPDATES"

        pending = (not done) and play_requires_update(res, self.config)
        self.btn_play.enabled = not updating
        if play_after:
            self.btn_play.text = "UPDATING, THEN LAUNCH..."
        elif pending:
            self.btn_play.text = "UPDATE & PLAY"
        else:
            self.btn_play.text = "PLAY GAME"

        if updating:
            self.btn_update.enabled = False
            self.btn_update.text = "UPDATING..."
            self.btn_update.badge = f"{int(frac * 100)}%"
        elif done:
            self.btn_update.enabled = False
            self.btn_update.text = "UPDATE INSTALLED"
            self.btn_update.badge = "OK"
        elif res and res.status == "update_available" and res.remote:
            self.btn_update.enabled = True
            self.btn_update.text = f"UPDATE TO v{res.remote.version}"
            self.btn_update.badge = "NEW"
        else:
            self.btn_update.enabled = False
            self.btn_update.text = "UP TO DATE"
            self.btn_update.badge = ""

    def _update_fx(self, dt: float) -> None:
        for drop in self._rain:
            drop[0] -= drop[2] * 0.22 * dt
            drop[1] += drop[2] * dt
            if drop[1] > L_HEIGHT:
                drop[1] = -drop[3]
                drop[0] = self._rng.uniform(0, L_WIDTH + 80)
        for emb in self._embers:
            emb[0] += emb[2] * dt
            emb[1] -= emb[3] * dt
            if emb[1] < -10:
                emb[1] = L_HEIGHT + 6
                emb[0] = self._rng.uniform(0, L_WIDTH)

    def _draw_fx(self) -> None:
        self.screen.blit(self.bg_surf, (0, 0))
        # Rain brightness follows speed: faster drops read as nearer.
        for x, y, spd, length in self._rain:
            shade = 0.55 + 0.45 * ((spd - 260.0) / 160.0)
            col = (int(110 * shade), int(125 * shade), int(145 * shade))
            pygame.draw.line(
                self.screen, col, (int(x), int(y)), (int(x - length * 0.22), int(y + length)), 1
            )
        self.screen.blit(self.dim_overlay, (0, 0))
        # Embers are additive glows drawn after the dim layer so they glow.
        now = _now_ms()
        for x, y, _vx, _vy, rad in self._embers:
            size = max(1, min(4, int(rad + 0.6 * math.sin(now / 200.0 + x * 0.1))))
            spr = self._ember_sprites[size]
            half = spr.get_width() // 2
            self.screen.blit(spr, (int(x) - half, int(y) - half), special_flags=pygame.BLEND_ADD)
        self.screen.blit(self.vignette, (0, 0))

    def _draw_left_column(self) -> None:
        # Top classification bar
        bar = self._plate(L_WIDTH - 56, 24)
        bar.fill((10, 14, 20, 230))
        pygame.draw.line(bar, C_ORANGE, (0, 0), (bar.get_width(), 0), 1)
        pygame.draw.line(bar, (60, 45, 25), (0, 23), (bar.get_width(), 23), 1)
        self.screen.blit(bar, (28, 16))

        hdr = self.font_small.render(
            "// KRAPNET TERMINAL // PRE-FLIGHT LAUNCHER & AUTO-PATCH RELAY //",
            True,
            C_ORANGE,
        )
        self.screen.blit(hdr, (38, 21))

        # Game title (glow + shadow are pre-rendered)
        pad = self._title_pad
        self.screen.blit(self._title_surf, (28 - pad, 52 - pad))
        self.screen.blit(self._title_rule, (28, 106))

        # Local version & active save card
        info_card = self._plate(286, 118)
        info_card.fill((10, 14, 20, 210))
        pygame.draw.rect(info_card, (45, 65, 85), info_card.get_rect(), 1)
        pygame.draw.line(info_card, C_KRAP_BLUE, (0, 0), (0, 118), 3)
        self.screen.blit(info_card, (28, 122))

        l1 = self.font_small.render("INSTALLED VERSION", True, (95, 155, 200))
        l2 = self.font_mono_b.render(self.local_version.display_tag, True, C_WHITE)
        eng_short = f"ENGINE: RPE6 GOLD v{self.local_version.version}"
        l3 = self.font_small.render(_ellipsize(self.font_small, eng_short, 260), True, C_GREY)
        l4 = self.font_small.render(_ellipsize(self.font_small, self.save_summary, 260), True, (130, 140, 135))
        self.screen.blit(l1, (42, 132))
        self.screen.blit(l2, (42, 150))
        pygame.draw.line(self.screen, (45, 65, 85), (42, 172), (300, 172), 1)
        self.screen.blit(l3, (42, 176))
        self.screen.blit(l4, (42, 196))

        for btn in self.buttons:
            btn.draw(self.screen, self.font_btn, self.font_badge)

    def _draw_right_panel(self) -> None:
        px, py, pw, ph = 336, 54, 496, 396
        panel = self._plate(pw, ph)
        panel.fill(C_PANEL)

        with self._lock:
            checking = self.is_checking
            updating = self.is_updating
            done = self.update_done
            err = self.update_error
            res = self.check_result
            stage = self.progress_stage
            frac = self.progress_frac
            detail = self.progress_detail

        has_update = (res is not None and res.status == "update_available" and res.remote is not None and not done)

        # Which card is showing; a change restarts the fade-in.
        if updating:
            key = "updating"
        elif has_update:
            key = "notice"
        elif done and res and res.remote:
            key = "done"
        else:
            key = "status"
        if key != self._card_key:
            self._card_key = key
            self._card_fade = 0.0
        else:
            self._card_fade = min(1.0, self._card_fade + self._dt / 0.30)
        if not updating:
            self._shown_frac = 0.0

        border_col = C_ORANGE if (has_update or updating) else (C_GREEN if done else (48, 64, 82))
        bracket_col = C_ORANGE if (has_update or updating) else (C_GREEN if done else (95, 130, 165))
        pygame.draw.rect(panel, border_col, panel.get_rect(), 1)
        pygame.draw.rect(panel, border_col, (0, 0, pw, 4))
        self.screen.blit(panel, (px, py))
        _draw_brackets(self.screen, pygame.Rect(px - 3, py - 3, pw + 6, ph + 6), bracket_col, 12, 2)

        if key == "updating":
            self._draw_updating_card(px, py, pw, ph, stage, frac, detail)
        elif key == "notice":
            self._draw_update_notice_card(px, py, pw, ph, res.remote, err)
        elif key == "done":
            self._draw_update_complete_card(px, py, pw, ph, res.remote)
        else:
            self._draw_status_card(px, py, pw, ph, checking, res, err)

        if self._card_fade < 1.0:
            veil = self._plate(pw - 2, ph - 5)
            veil.fill((10, 14, 20, int(228 * (1.0 - self._card_fade) ** 2)))
            self.screen.blit(veil, (px + 1, py + 4))

    def _draw_update_notice_card(
        self,
        px: int,
        py: int,
        pw: int,
        ph: int,
        remote: RemoteUpdateInfo,
        err: str,
    ) -> None:
        # Glowing orange notice banner
        banner = self._plate(pw - 32, 36)
        pulse = int(40 + 25 * math.sin(_now_ms() / 220.0))
        banner.fill((255, 120, 0, pulse))
        pygame.draw.rect(banner, C_ORANGE, banner.get_rect(), 1)
        self.screen.blit(banner, (px + 16, py + 16))

        b_str = _ellipsize(
            self.font_mono_b,
            f"// NEW VERSION AVAILABLE: {remote.display_tag} //",
            pw - 52,
        )
        b_txt = self.font_mono_b.render(b_str, True, C_ORANGE)
        self.screen.blit(b_txt, (px + 26, py + 25))

        # Version comparison strip
        comp_str = _ellipsize(
            self.font_small,
            f"INSTALLED: {self.local_version.display_tag}   -->   NEW: {remote.display_tag}",
            pw - 36,
        )
        comp = self.font_small.render(comp_str, True, C_WHITE)
        self.screen.blit(comp, (px + 18, py + 62))

        # Delta / download size badge
        dl_bytes = remote.download_bytes
        if remote.changed_files and remote.files_base_url:
            mode_str = (
                f"DELTA PATCH: {len(remote.changed_files)} CHANGED FILE(S) "
                f"({format_bytes(dl_bytes)}) — NO .EXE DOWNLOAD"
            )
        elif dl_bytes > 0:
            mode_str = f"IN-PLACE PATCH PACKAGE: {format_bytes(dl_bytes)} — SAVES PRESERVED"
        else:
            mode_str = "IN-PLACE UPDATE READY — SAVES & SETTINGS PRESERVED"
        m_surf = self.font_small.render(_ellipsize(self.font_small, mode_str, pw - 36), True, C_GREEN)
        self.screen.blit(m_surf, (px + 18, py + 82))

        # What the patcher will NOT touch / will overwrite.
        note_y = py + 96
        if remote.protected_files:
            prot = f"KEEPING {len(remote.protected_files)} PROTECTED FILE(S) (.aca_skip)"
            self.screen.blit(
                self.font_small.render(_ellipsize(self.font_small, prot, pw - 36), True, (110, 165, 200)),
                (px + 18, note_y),
            )
            note_y += 15
        if remote.locally_modified:
            mod = f"WARNING: {len(remote.locally_modified)} LOCALLY MODIFIED FILE(S) WILL BE REPLACED"
            self.screen.blit(
                self.font_small.render(_ellipsize(self.font_small, mod, pw - 36), True, C_AMBER),
                (px + 18, note_y),
            )
            note_y += 15

        # Everything below the notes shifts down by however many note lines
        # were added (0 when there are none, matching the original layout).
        off = max(0, note_y + 4 - (py + 104))

        pygame.draw.line(
            self.screen, (45, 55, 68), (px + 16, py + 104 + off), (px + pw - 16, py + 104 + off), 1
        )

        # Headline
        hl = self.font_card_hdr.render(_ellipsize(self.font_card_hdr, remote.headline, pw - 36), True, C_WHITE)
        self.screen.blit(hl, (px + 18, py + 112 + off))

        # Changelog notes
        sub = self.font_small.render("TRANSMISSION CHANGELOG:", True, C_ORANGE)
        self.screen.blit(sub, (px + 18, py + 146 + off))

        y_cursor = py + 168 + off
        notes = remote.notes or ["General stability, netcode, and campaign improvements."]
        for note in notes[:6]:
            wrapped = _wrap_lines(self.font_mono, note, pw - 56)
            for i, ln in enumerate(wrapped[:2]):
                prefix = "  * " if i == 0 else "    "
                ln_surf = self.font_mono.render(prefix + ln, True, C_GREY)
                self.screen.blit(ln_surf, (px + 14, y_cursor))
                y_cursor += 19
            y_cursor += 4
            if y_cursor > py + ph - 72:
                break

        if err:
            e_surf = self.font_small.render(_ellipsize(self.font_small, f"ERROR: {err}", pw - 36), True, C_RED)
            self.screen.blit(e_surf, (px + 18, py + ph - 62))

        # Bottom instruction box
        foot_box = self._plate(pw - 32, 34)
        foot_box.fill((16, 22, 30, 220))
        pygame.draw.rect(foot_box, (65, 85, 105), foot_box.get_rect(), 1)
        self.screen.blit(foot_box, (px + 16, py + ph - 44))
        if play_requires_update(self.check_result, self.config):
            foot_line = "Click [UPDATE & PLAY] to patch and launch, or [EXIT] to patch later."
        else:
            foot_line = f"Click [UPDATE TO v{remote.version}] to patch now, or [PLAY GAME] to skip."
        f_txt = self.font_small.render(_ellipsize(self.font_small, foot_line, pw - 48), True, C_WHITE)
        self.screen.blit(f_txt, (px + 24, py + ph - 34))

    def _draw_updating_card(
        self,
        px: int,
        py: int,
        pw: int,
        ph: int,
        stage: str,
        frac: float,
        detail: str,
    ) -> None:
        hdr = self.font_card_hdr.render("// APPLYING IN-PLACE UPDATE //", True, C_ORANGE)
        self.screen.blit(hdr, (px + 20, py + 22))

        st = self.font_mono_b.render(_ellipsize(self.font_mono_b, f"STAGE: {stage}", pw - 40), True, C_WHITE)
        self.screen.blit(st, (px + 20, py + 66))

        # Progress bar: eases toward the real value, with animated stripes,
        # a top highlight, a bright leading edge and 10% tick marks.
        self._shown_frac += (frac - self._shown_frac) * min(1.0, self._dt * 8.0)
        shown = max(0.0, min(1.0, self._shown_frac))
        bar_x, bar_y, bar_w, bar_h = px + 20, py + 98, pw - 40, 28
        pygame.draw.rect(self.screen, (16, 20, 28), (bar_x, bar_y, bar_w, bar_h))
        fill_w = int((bar_w - 4) * shown)
        if fill_w > 0:
            fill = pygame.Rect(bar_x + 2, bar_y + 2, fill_w, bar_h - 4)
            pygame.draw.rect(self.screen, C_ORANGE, fill)
            pygame.draw.rect(self.screen, (255, 175, 90), (fill.x, fill.y, fill.w, 3))
            old_clip = self.screen.get_clip()
            self.screen.set_clip(fill)
            off = (_now_ms() // 40) % 16
            for sx in range(fill.x - 16 + off, fill.right, 16):
                pygame.draw.line(self.screen, (225, 95, 0), (sx, fill.bottom), (sx + fill.h, fill.y), 3)
            self.screen.set_clip(old_clip)
            pygame.draw.line(
                self.screen, (255, 235, 200), (fill.right - 1, fill.y), (fill.right - 1, fill.bottom - 1), 2
            )
        for i in range(1, 10):
            tx = bar_x + 2 + int((bar_w - 4) * i / 10)
            pygame.draw.line(self.screen, (16, 20, 28), (tx, bar_y + 2), (tx, bar_y + 6), 1)
            pygame.draw.line(self.screen, (16, 20, 28), (tx, bar_y + bar_h - 7), (tx, bar_y + bar_h - 3), 1)
        pygame.draw.rect(self.screen, C_ORANGE, (bar_x, bar_y, bar_w, bar_h), 1)

        pct_s = self.font_mono_b.render(f"{int(frac * 100)}%", True, C_WHITE)
        pct_sh = self.font_mono_b.render(f"{int(frac * 100)}%", True, (0, 0, 0))
        pcx = bar_x + (bar_w - pct_s.get_width()) // 2
        self.screen.blit(pct_sh, (pcx + 1, bar_y + 6))
        self.screen.blit(pct_s, (pcx, bar_y + 5))

        det = self.font_mono.render(_ellipsize(self.font_mono, detail, pw - 40), True, C_GREY)
        self.screen.blit(det, (px + 20, py + 140))

        reassure = [
            "Verifying SHA-256 file integrity before replacing local files.",
            "Preserving save_data.json, settings.json, and operator profiles.",
            "Rolling back automatically if any file fails to apply.",
        ]
        y_c = py + 195
        for line in reassure:
            s = self.font_small.render(_ellipsize(self.font_small, "> " + line, pw - 40), True, (115, 130, 140))
            self.screen.blit(s, (px + 20, y_c))
            y_c += 24

    def _draw_update_complete_card(
        self,
        px: int,
        py: int,
        pw: int,
        ph: int,
        remote: RemoteUpdateInfo,
    ) -> None:
        banner = self._plate(pw - 32, 38)
        banner.fill((25, 85, 45, 140))
        pygame.draw.rect(banner, C_GREEN, banner.get_rect(), 1)
        self.screen.blit(banner, (px + 16, py + 18))

        done_hdr = _ellipsize(
            self.font_mono_b,
            f"// UPDATE COMPLETE: {self.local_version.display_tag} //",
            pw - 52,
        )
        b_txt = self.font_mono_b.render(done_hdr, True, C_GREEN)
        self.screen.blit(b_txt, (px + 26, py + 28))

        hl = self.font_card_hdr.render(_ellipsize(self.font_card_hdr, remote.headline, pw - 36), True, C_WHITE)
        self.screen.blit(hl, (px + 18, py + 72))

        sub = self.font_small.render("APPLIED CHANGES:", True, C_GREEN)
        self.screen.blit(sub, (px + 18, py + 108))

        y_c = py + 130
        for note in (remote.notes or ["All files verified and patched in-place."])[:6]:
            wrapped = _wrap_lines(self.font_mono, note, pw - 56)
            for i, ln in enumerate(wrapped[:2]):
                prefix = "  * " if i == 0 else "    "
                self.screen.blit(self.font_mono.render(prefix + ln, True, C_GREY), (px + 14, y_c))
                y_c += 19
            y_c += 4
            if y_c > py + ph - 64:
                break

        foot_box = self._plate(pw - 32, 34)
        foot_box.fill((16, 28, 22, 220))
        pygame.draw.rect(foot_box, C_GREEN, foot_box.get_rect(), 1)
        self.screen.blit(foot_box, (px + 16, py + ph - 44))
        ready = self.font_small.render(
            "Press ENTER or click [PLAY GAME] to launch Call of Acaristan.",
            True,
            C_WHITE,
        )
        self.screen.blit(ready, (px + 24, py + ph - 34))

    def _status_headline(
        self, checking: bool, res: UpdateCheckResult | None
    ) -> tuple[str, tuple[int, int, int]]:
        if checking:
            return "CONTACTING UPDATE RELAY...", C_AMBER
        if res is None:
            return "STANDBY", C_GREY
        if res.status == "up_to_date":
            return f"UP TO DATE // {self.local_version.display_tag} IS LATEST", C_GREEN
        if res.status == "offline":
            return res.message, C_AMBER
        if res.status == "refused":
            return "FEED REFUSED // UNTRUSTED UPDATE SOURCE", C_RED
        if res.status == "unconfigured":
            if self.itch_receipt is not None:
                return "ITCH.IO INSTALL // UPDATES ARRIVE VIA THE ITCH APP", C_GREEN
            return "LOCAL BUILD // NO UPDATE RELAY CONFIGURED", C_KRAP_BLUE
        return f"READY // {self.local_version.display_tag} (LOCAL MODE)", C_KRAP_BLUE

    def _draw_status_card(
        self,
        px: int,
        py: int,
        pw: int,
        ph: int,
        checking: bool,
        res: UpdateCheckResult | None,
        err: str,
    ) -> None:
        hdr = self.font_card_hdr.render("// KRAPNET RELAY STATUS & DISPATCH //", True, C_WHITE)
        self.screen.blit(hdr, (px + 18, py + 18))
        pygame.draw.line(self.screen, (45, 58, 72), (px + 18, py + 52), (px + pw - 18, py + 52), 1)

        st_txt, st_col = self._status_headline(checking, res)
        st_surf = self.font_mono_b.render(_ellipsize(self.font_mono_b, st_txt, pw - 36), True, st_col)
        self.screen.blit(st_surf, (px + 18, py + 64))

        hl = self.font_mono_b.render(
            _ellipsize(self.font_mono_b, self.local_version.headline, pw - 36), True, C_WHITE
        )
        self.screen.blit(hl, (px + 18, py + 98))

        sub = self.font_small.render("CURRENT BUILD HIGHLIGHTS:", True, C_ORANGE)
        self.screen.blit(sub, (px + 18, py + 126))

        y_c = py + 148
        for note in self.local_version.notes[:5]:
            for i, ln in enumerate(_wrap_lines(self.font_mono, note, pw - 52)[:2]):
                prefix = "  * " if i == 0 else "    "
                self.screen.blit(self.font_mono.render(prefix + ln, True, C_GREY), (px + 14, y_c))
                y_c += 20
            y_c += 4

        if err:
            self.screen.blit(
                self.font_small.render(_ellipsize(self.font_small, f"NOTICE: {err}", pw - 36), True, C_RED),
                (px + 18, py + ph - 72),
            )
        elif res is not None and res.refused_reason:
            reason = self.font_small.render(
                _ellipsize(self.font_small, f"NOTICE: {res.refused_reason}", pw - 36), True, C_RED
            )
            self.screen.blit(reason, (px + 18, py + ph - 72))

        tip_box = self._plate(pw - 28, 44)
        tip_box.fill((12, 18, 26, 210))
        pygame.draw.rect(tip_box, (40, 55, 72), tip_box.get_rect(), 1)
        self.screen.blit(tip_box, (px + 14, py + ph - 54))
        if self._dev_mode():
            t1 = self.font_small.render(
                "DEV: python launcher.py --demo-update previews a live update notice.",
                True,
                (110, 145, 175),
            )
        elif res is not None and res.status == "unconfigured" and self.itch_receipt is not None:
            t1 = self.font_small.render(
                "This install is managed by the itch app; it updates the game for you.",
                True,
                C_DIM,
            )
        elif res is not None and res.status == "unconfigured":
            t1 = self.font_small.render(
                "This build is a local install; no update feed is configured.",
                True,
                C_DIM,
            )
        else:
            t1 = self.font_small.render(
                "Updates appear here automatically when a new release is published.",
                True,
                C_DIM,
            )
        t2 = self.font_small.render(
            "Saves, settings, and protected files are never overwritten.",
            True,
            (110, 145, 175),
        )
        self.screen.blit(t1, (px + 22, py + ph - 48))
        self.screen.blit(t2, (px + 22, py + ph - 30))

    def _dev_mode(self) -> bool:
        return bool(self.demo_update or os.environ.get("ACA_DEV") == "1")

    def _draw_footer(self) -> None:
        pygame.draw.line(self.screen, (45, 35, 20), (28, L_HEIGHT - 44), (L_WIDTH - 28, L_HEIGHT - 44), 1)

        with self._lock:
            checking = self.is_checking
            updating = self.is_updating
            res = self.check_result

        if updating or checking:
            led_col = C_AMBER
            status_msg = "RELAY TRANSMISSION ACTIVE..."
        elif res and res.status == "update_available" and res.remote:
            led_col = C_ORANGE
            status_msg = f"UPDATE NOTICE: {res.remote.display_tag} READY TO INSTALL"
        else:
            led_col = C_GREEN
            status_msg = f"KRAPNET RELAY READY // {self.local_version.display_tag}"

        if (_now_ms() // 500) % 2 == 0:
            pygame.draw.circle(self.screen, led_col, (38, L_HEIGHT - 24), 4)
        else:
            pygame.draw.circle(
                self.screen,
                (led_col[0] // 2, led_col[1] // 2, led_col[2] // 2),
                (38, L_HEIGHT - 24),
                4,
            )

        self.screen.blit(self.font_small.render(status_msg, True, C_GREY), (50, L_HEIGHT - 31))
        right_lbl = self.font_small.render("RETARDOVICI INC. // RPE6 GOLD", True, C_DIM)
        self.screen.blit(right_lbl, (L_WIDTH - 28 - right_lbl.get_width(), L_HEIGHT - 31))

    def render_frame(self, dt: float = 1.0 / 60.0) -> None:
        self._dt = dt
        self._sync_buttons()
        self._update_fx(dt)
        mouse_pos = self.logical_mouse()
        # Two passes: hover must be resolved for every button before keyboard
        # selection is assigned. Evaluating `any_hover` mid-loop left an
        # earlier focused button lit while the pointer hovered a later one —
        # two "active" buttons at once, which reads as the hover being broken.
        for btn in self.buttons:
            btn.check_hover(mouse_pos)
        any_hover = any(b.is_hovered for b in self.buttons)
        for i, btn in enumerate(self.buttons):
            btn.is_selected = (self.focus_idx == i) and not any_hover
            btn.update(dt)

        self._draw_fx()
        self._draw_left_column()
        self._draw_right_panel()
        self._draw_footer()
        _draw_tactical_cursor(self.screen, mouse_pos, any_hover)
        self.present()

    def _trigger_button(self, btn: _LauncherButton) -> str | None:
        if not btn.enabled:
            return None
        btn.press()
        if btn is self.btn_play:
            if self._update_pending():
                # Patch first: a running exe/dll cannot be replaced later.
                with self._lock:
                    self._play_after_update = True
                self.start_background_update()
                return None
            return "play"
        if btn is self.btn_update:
            self.start_background_update()
            return None
        if btn is self.btn_check:
            self.start_background_check()
            return None
        if btn is self.btn_exit:
            return "exit"
        return None

    def _take_pending_action(self) -> str | None:
        with self._lock:
            action = self._pending_action
            self._pending_action = None
        return action

    def _enter_target(self) -> _LauncherButton | None:
        """Which button ENTER/SPACE activates: the hovered one, else the focused.

        Pointer-first means the keyboard marker never fights the mouse: after
        the cursor moves (focus released), ENTER still clicks what you are
        pointing at.
        """
        mouse_pos = self.logical_mouse()
        for btn in self.buttons:
            if btn.enabled and btn.rect.collidepoint(mouse_pos):
                return btn
        if 0 <= self.focus_idx < len(self.buttons):
            return self.buttons[self.focus_idx]
        return None

    def run(self) -> str:
        """Run the launcher loop; returns `'play'` or `'exit'`.

        Input model: the pointer is always authoritative for what is hovered;
        mouse motion releases keyboard focus (arrows re-acquire it), and
        ENTER/SPACE activates the hovered button first, the focused one second.
        """
        if self.config.get("check_on_startup", True):
            self.start_background_check()

        last_ms = _now_ms()
        action = "exit"
        running = True
        try:
            while running:
                now = _now_ms()
                dt = min(1.0 / 15.0, max(0.001, (now - last_ms) / 1000.0))
                last_ms = now

                for event in pygame.event.get():
                    if event.type == pygame.QUIT:
                        action = "exit"
                        running = False
                    elif event.type == pygame.MOUSEMOTION:
                        # Moving the mouse hands control to the pointer (the
                        # same convention as the game menu): the keyboard
                        # focus marker should not stay lit under a resting
                        # cursor that is pointing somewhere else.
                        self.focus_idx = -1
                    elif event.type == pygame.KEYDOWN:
                        if event.key == pygame.K_ESCAPE:
                            if not self.is_updating:
                                action = "exit"
                                running = False
                        elif event.key in (pygame.K_DOWN, pygame.K_s):
                            if self.focus_idx < 0:
                                self.focus_idx = 0
                            else:
                                self.focus_idx = (self.focus_idx + 1) % len(self.buttons)
                        elif event.key in (pygame.K_UP, pygame.K_w):
                            if self.focus_idx < 0:
                                self.focus_idx = len(self.buttons) - 1
                            else:
                                self.focus_idx = (self.focus_idx - 1) % len(self.buttons)
                        elif event.key in (pygame.K_RETURN, pygame.K_SPACE):
                            target = self._enter_target()
                            if target is not None:
                                res_act = self._trigger_button(target)
                                if res_act:
                                    action = res_act
                                    running = False
                    elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                        for idx, btn in enumerate(self.buttons):
                            if btn.check_hover(self.logical_mouse()):
                                self.focus_idx = idx
                                res_act = self._trigger_button(btn)
                                if res_act:
                                    action = res_act
                                    running = False
                                break

                # 'update & play' finishes in the worker thread.
                pending = self._take_pending_action()
                if pending:
                    action = pending
                    running = False

                self.render_frame(dt)
                self.clock.tick(60)
        finally:
            if self.demo_server is not None:
                self.demo_server.stop()
            pygame.quit()

        return action


def launch_game_process(root: Path) -> int:
    """Spawn the main Call of Acaristan game after closing the launcher.

    Blocks until the game exits (``subprocess.call``) so the launcher process
    stays the parent: nothing can patch the tree underneath a running game.
    """
    env = dict(os.environ, ACA_FROM_LAUNCHER="1")
    # If packaged via PyInstaller onedir, prefer `Call of Acaristan.exe` in the same folder
    exe_candidate = root / "Call of Acaristan.exe"
    if exe_candidate.is_file():
        cmd = [str(exe_candidate)]
    else:
        cmd = [sys.executable, str(root / "acaristan.py")]
    return subprocess.call(cmd, cwd=str(root), env=env)


def run_launcher(
    root: Path | None = None,
    demo_update: bool = False,
    no_launch: bool = False,
) -> int:
    repo_root = root if root is not None else Path(__file__).resolve().parents[2]
    app = LauncherApp(repo_root, demo_update=demo_update)
    decision = app.run()
    if decision == "play" and not no_launch:
        return launch_game_process(repo_root)
    return 0