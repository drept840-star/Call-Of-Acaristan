"""End credits sequence displayed after Mission 8's Call of Acaristan title card."""
from __future__ import annotations

import random
import traceback

import pygame

from core.config import (
    HEIGHT,
    WIDTH,
    draw_scanlines,
    draw_vignette,
)
from core.state import STATE
from engine.text import T as _T
from engine.text import wrap_lines
from ui import kit
from ui.credits_football import (
    _FootballScene,
    _FootballSim,
    _fallback_football,
    _fallback_goal_post,
)

SCROLL_SPEED = 46.0
FAST_MUL = 4.0
LEAD_IN_S = 0.45
HOLD_END_S = 4.2
FADE_MUSIC_AT_S = HOLD_END_S - 1.6
_PITCH_DATE = "15.07.2000"

_BG_RGB = (6, 8, 12)

_SECTIONS = (
    (
        "CREATED BY",
        (
            ("center", "MOSKOVACI", 34, "display", kit.TEXT, 2),
            ("center", "RETARDOVICI INC.", 14, "bold", kit.STEEL, 10),
        ),
    ),
    (
        "DIRECTION & DESIGN",
        (
            ("pair", "GAME DIRECTOR & LEAD DEV", "MOSKOVACI"),
            ("pair", "MISSION DESIGN (M1)", "DS4F"),
            ("pair", "MISSION DESIGN (M4, M5)", "DSF4"),
            ("pair", "MISSION DESIGN (M2, M3, M6, M7, M8)", "MOSKOVACI"),
            ("pair", "STORY & LORE", "MOSKOVACI"),
            ("pair", "DIALOGUE", "Opus 5.5, DS4.1 Flash, Gemini 4 Hydrogen, etc."),
            ("pair", "KRAPNET UI & UPLOAD OS", "MOSKOVACI"),
        ),
    ),
    (
        "PROGRAMMING & ENGINE",
        (
            ("pair", "ENGINE ARCHITECTURE (RPE 6)", "MOSKOVACI"),
            ("pair", "2D / 2.5D & 3D RENDERER", "Maxxzy"),
            ("pair", "GAMEPLAY, AI & CUTSCENES", "Opus 5.5"),
            ("pair", "KRAPNET MULTIPLAYER", "SB"),
            ("pair", "LAUNCHER, TOOLS & CI", "MOSKOVACI"),
        ),
    ),
    (
        "ART, ANIMATION & 3D",
        (
            ("pair", "2D PIXEL ART & PORTRAITS", "Claude Opus 5.5"),
            (
                "pair",
                "3D RIGS & CINEMATICS",
                "Gemini 4 Argon, Gemini 4 Hydrogen, GPT 6.1 Sol, Opus 5.5, other AIs",
            ),
            (
                "pair",
                "IN-HOUSE GLB ASSETS",
                "Gemini 4 Argon, Gemini 4 Hydrogen, GPT 6.1 Sol, Opus 5.5, other AIs",
            ),
            (
                "pair",
                "3D MODELING",
                "Gemini 4 Argon, Gemini 4 Hydrogen, GPT 6.1 Sol, Opus 5.5, other AIs I can't remember",
            ),
        ),
    ),
    (
        "AUDIO & MUSIC",
        (
            ("pair", "ORIGINAL SOUNDTRACK", "MOSKOVACI"),
            ("pair", "PROCEDURAL FOLEY & SFX", "MOSKOVACI"),
            ("pair", "DARK CELLO HORROR TRAILER MUSIC", "Overmusic"),
        ),
    ),
    (
        "VOICE CAST",
        (
            ("pair", "ALL CHARACTER VOICES", "Google AI TTS"),
        ),
    ),
    (
        "CAST",
        (
            ("pair", "KRAP FIELD OPERATIVE", "BIRIBEL"),
            ("pair", "KRAP / PRESIDENTIAL GUARD", "COMMANDER VASILE"),
            ("pair", "MAG LEADER", "MARU"),
            ("pair", "IPA LOGISTICS", "SEBASTIAN VOLKOV"),
            ("pair", "PRESIDENTIAL GUARD", "ANDREI BOGDAN VELICU (UCILEV)"),
            ("pair", "PRESIDENT OF ACARISTAN", "SEBASTIAN RETARDOVICI"),
            ("pair", "PRIME MINISTER", "BALACEANU"),
            ("pair", "VALEA SEACA", "BODI"),
            ("pair", "MAG RUNNER", "ALEX"),
            ("pair", "KRAP SQUAD 4", "GABI, SEBY, DARIUS"),
            ("pair", "IPA ENFORCER", "CIOCAN"),
            ("pair", "CHECKPOINT GUARDS", "KOVAC & SANDU"),
            ("pair", "HARBOR DISTRICT", "OLD FISHERMAN, OLD WOMAN, KID"),
        ),
    ),
    (
        "QA & PLAYTESTING",
        (
            ("pair", "MULTIPLAYER PLAYTESTING", "Andrei V."),
            ("pair", "CAMPAIGN QA & TESTING", "MOSKOVACI"),
        ),
    ),
    (
        "SPECIAL THANKS",
        (
            ("thanks", "Dan D.", "for hating the project all the way just because it doesn't make money"),
            ("thanks", "Maru", "for never being proud of anything like he could do anything"),
            ("thanks", "Andrei V.", "for never stopping to believe"),
        ),
    ),
    (
        "ORIGINAL SOUNDTRACK",
        (
            ("pair", "01  MAIN THEME", "Call of Acaristan"),
            ("pair", "02  MISSION 1 - DAY 0", "Black Notebook"),
            ("pair", "03  MISSION 2 - DAY 1", "Quiet on Route 12"),
            ("pair", "04  MISSION 3 - DAY 4", "The Vostral"),
            ("pair", "05  MISSION 4 - THE AFTERMATH", "Curfew Dawn"),
            ("pair", "06  MISSION 5 - MARTIAL LAW", "Not Tonight"),
            ("pair", "07  MISSION 6 - DAY 10", "Whiteout"),
            ("pair", "08  ENDING FILM", "I Chose the Many"),
            ("pair", "09  MISSION 7 - THE RAID", "Fallow Ground"),
            ("pair", "10  MISSION 8 - DUTY", "Head of State"),
            ("pair", "11  MISSION 8 - REVENGE", "Old Friends"),
            ("pair", "12  OUTRO", "Gabi, Seby, Darius"),
        ),
    ),
    (
        "BUILT WITH",
        (
            ("pair", "ENGINE & RUNTIME", "RPE 6 (with Python/Pygame base)"),
            ("pair", "3D & AUDIO STACK", "ModernGL & NumPy"),
            ("pair", "TYPOGRAPHY", "Oswald & IBM Plex Mono (OFL)"),
            ("pair", "MULTIPLAYER TUNNELS", "bore & playit"),
        ),
    ),
)


def _build_backdrop():
    surf = pygame.Surface((WIDTH, HEIGHT)).convert()
    surf.fill(_BG_RGB)
    for y in range(HEIGHT):
        p = y / float(HEIGHT)
        band = max(0.0, 1.0 - abs(p - 0.5) * 2.0)
        shade = int(band * 7)
        if shade > 0:
            pygame.draw.line(
                surf,
                (_BG_RGB[0] + shade, _BG_RGB[1] + shade + 1, _BG_RGB[2] + shade + 3),
                (0, y),
                (WIDTH, y),
            )
    return surf


def _build_edge_mask(top=True, h=64):
    surf = pygame.Surface((WIDTH, h), pygame.SRCALPHA)
    for y in range(h):
        k = (1.0 - y / float(h - 1)) if top else (y / float(h - 1))
        a = int(255 * (k ** 1.4))
        pygame.draw.line(surf, (*_BG_RGB, a), (0, y), (WIDTH, y))
    return surf


class CreditsRoll:
    """Self-contained vertical credit roller and closing card."""

    def __init__(self):
        self._bg = None
        self._top_mask = None
        self._bot_mask = None
        self._items = []
        self._motes = []
        self.stop_scroll = 0.0
        self._sim = _FootballSim()
        self._scene = _FootballScene()
        self.reset()

    def reset(self):
        self.t = 0.0
        self.scroll_y = 0.0
        self.phase = "lead"      # "lead" -> "scroll" -> "hold" -> "done"
        self.hold_t = 0.0
        self._fade_sent = False
        self._key_hold = False
        self._mouse_hold = False
        self._fast = False
        self._wait_release = True
        self._route = getattr(STATE, "m8_route", "revenge")
        self._sim.reset()
        self._build_layout()

    def _ensure_chrome(self):
        if self._bg is None:
            self._bg = _build_backdrop()
            self._top_mask = _build_edge_mask(top=True)
            self._bot_mask = _build_edge_mask(top=False)
        if not self._motes:
            rng = random.Random(1991)
            self._motes = [
                [
                    rng.uniform(0, WIDTH),
                    rng.uniform(0, HEIGHT),
                    rng.uniform(6.0, 18.0),
                    rng.uniform(-4.0, 4.0),
                    rng.choice(((74, 80, 92), (112, 92, 68))),
                    1 if i % 3 else 2,
                ]
                for i in range(26)
            ]

    def _build_layout(self):
        self._ensure_chrome()
        items = []
        cx = WIDTH // 2
        y = 0

        def add_center(text, size, weight, color, gap_after=0):
            nonlocal y
            s = kit.font(size, weight).render(text, True, color)
            items.append((y, s, cx - s.get_width() // 2))
            y += s.get_height() + gap_after

        def add_rule(width=260, tick=72, gap_after=16):
            nonlocal y
            bar = pygame.Surface((width, 3), pygame.SRCALPHA)
            pygame.draw.line(bar, kit.EDGE_HI, (0, 1), (width - 1, 1))
            tx = (width - tick) // 2
            pygame.draw.rect(bar, kit.ORANGE, (tx, 0, tick, 3))
            items.append((y, bar, cx - width // 2))
            y += 3 + gap_after

        def add_section_header(title):
            nonlocal y
            y += 30
            hdr_w = 480
            ts = kit.font(24, "display").render(title, True, kit.AMBER)
            hdr = pygame.Surface((hdr_w, ts.get_height()), pygame.SRCALPHA)
            tw = ts.get_width()
            mid_y = ts.get_height() // 2 + 2
            side_w = max(0, (hdr_w - tw) // 2 - 16)
            if side_w > 0:
                pygame.draw.line(hdr, kit.EDGE_HI, (0, mid_y), (side_w, mid_y))
                pygame.draw.line(hdr, kit.EDGE_HI, (hdr_w - side_w, mid_y), (hdr_w - 1, mid_y))
            hdr.blit(ts, ((hdr_w - tw) // 2, 0))
            items.append((y, hdr, cx - hdr_w // 2))
            y += ts.get_height() + 18

        def add_pair(role, name):
            nonlocal y
            rs = kit.font(14, "regular").render(role, True, kit.DIM)
            nf = kit.font(15, "semibold")
            lines = wrap_lines(nf, name, 420)
            first_ns = nf.render(lines[0], True, kit.TEXT)
            ry = y + max(0, (first_ns.get_height() - rs.get_height()) // 2)
            items.append((ry, rs, cx - 22 - rs.get_width()))
            for i, line in enumerate(lines):
                ns = first_ns if i == 0 else nf.render(line, True, kit.TEXT)
                items.append((y, ns, cx + 22))
                y += ns.get_height() + (4 if i < len(lines) - 1 else 0)
            y += 10

        def add_thanks(name, reason):
            nonlocal y
            add_center(name, 15, "bold", kit.AMBER, gap_after=4)
            rf = kit.font(14, "regular")
            for line in wrap_lines(rf, reason, 620):
                add_center(line, 14, "regular", kit.TEXT, gap_after=3)
            y += 12

        # Title header
        top = kit.font(26, "display").render("CALL OF", True, kit.AMBER)
        items.append((y, top, cx - top.get_width() // 2))
        y += top.get_height() - 12
        big = kit.font(68, "display").render("ACARISTAN", True, kit.TEXT)
        items.append((y, big, cx - big.get_width() // 2))
        y += big.get_height() + 10
        add_rule(260, 72, 14)
        add_center(_T("credits.subtitle"), 13, "bold", kit.STEEL, gap_after=56)

        # Credit sections
        for title, entries in _SECTIONS:
            add_section_header(title)
            for row in entries:
                kind = row[0]
                if kind == "pair":
                    add_pair(row[1], row[2])
                elif kind == "center":
                    add_center(row[1], row[2], row[3], row[4], gap_after=row[5])
                elif kind == "thanks":
                    add_thanks(row[1], row[2])
            y += 16

        # Closing card (rests vertically centered when scroll ends)
        y += 48
        closing_top = y
        add_rule(220, 48, 22)
        if self._route == "revenge":
            add_center("IN MEMORY OF SQUAD 4  -  ROUTE 12", 14, "bold", kit.AMBER, gap_after=6)
            add_center("Gabi, Seby, Darius. Volkov.", 14, "regular", kit.DIM, gap_after=24)
        else:
            add_center("ROUTE 12  -  DAY 12", 14, "bold", kit.AMBER, gap_after=24)
        add_center(_T("credits.thanks"), 40, "display", kit.TEXT, gap_after=14)
        add_center(_T("menu.retardovici_inc"), 13, "bold", kit.STEEL, gap_after=0)
        closing_bottom = y

        closing_center_y = (closing_top + closing_bottom) // 2
        self._items = items
        self.stop_scroll = max(0.0, float(HEIGHT // 2 + 28 + closing_center_y))

    def handle_event(self, event):
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                return "skip"
            if event.key in (pygame.K_SPACE, pygame.K_RETURN, pygame.K_KP_ENTER):
                if self.phase == "hold" and self.hold_t >= 0.35:
                    self.phase = "done"
                    return "done"
                if not self._wait_release:
                    self._key_hold = True
            elif event.key in (pygame.K_DOWN, pygame.K_s):
                self._key_hold = True
        elif event.type == pygame.KEYUP:
            if event.key in (pygame.K_SPACE, pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_DOWN, pygame.K_s):
                self._key_hold = False
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.phase == "hold" and self.hold_t >= 0.35:
                self.phase = "done"
                return "done"
            self._mouse_hold = True
        elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            self._mouse_hold = False
        return None

    def update(self, dt, keys=None):
        dt = max(0.0, min(float(dt or 0.0), 0.05))
        self.t += dt
        self._sim.step(dt)

        for m in self._motes:
            m[1] -= m[2] * dt
            m[0] += m[3] * dt
            if m[1] < -4:
                m[1] = HEIGHT + 4
            if m[0] < -4:
                m[0] = WIDTH + 4
            elif m[0] > WIDTH + 4:
                m[0] = -4

        key_down = False
        if keys is not None:
            try:
                key_down = bool(
                    keys[pygame.K_SPACE]
                    or keys[pygame.K_RETURN]
                    or keys[pygame.K_DOWN]
                    or keys[pygame.K_s]
                )
            except Exception:
                key_down = False

        if self._wait_release:
            if not key_down and not self._mouse_hold:
                self._wait_release = False
            self._fast = False
        else:
            self._fast = bool(self._key_hold or self._mouse_hold or key_down)

        if self.phase == "lead":
            if self.t >= LEAD_IN_S or self._fast:
                self.phase = "scroll"
            return None

        if self.phase == "scroll":
            speed = SCROLL_SPEED * (FAST_MUL if self._fast else 1.0)
            self.scroll_y += speed * dt
            if self.scroll_y >= self.stop_scroll:
                self.scroll_y = self.stop_scroll
                self.phase = "hold"
                self.hold_t = 0.0
            return None

        if self.phase == "hold":
            self.hold_t += dt * (2.0 if self._fast else 1.0)
            if not self._fade_sent and self.hold_t >= FADE_MUSIC_AT_S:
                self._fade_sent = True
                return "fade_music"
            if self.hold_t >= HOLD_END_S:
                self.phase = "done"
                return "done"
            return None

        return "done"

    def draw(self, surface):
        self._ensure_chrome()
        try:
            pitch = self._scene.draw(surface, self._sim)
        except Exception:
            if not self._scene._failed:
                traceback.print_exc()
            self._scene._failed, self._scene._r, pitch = True, None, False
        if not pitch:
            surface.blit(self._bg, (0, 0))
            for mx, my, _vy, _vx, col, sz in self._motes:
                pygame.draw.rect(surface, col, (int(mx), int(my), sz, sz))

        offset_y = HEIGHT + 28.0 - self.scroll_y
        for y_local, surf, x in self._items:
            sy = int(round(offset_y + y_local))
            sh = surf.get_height()
            if -sh <= sy < HEIGHT:
                surface.blit(surf, (x, sy))

        surface.blit(self._top_mask, (0, 0))
        surface.blit(self._bot_mask, (0, HEIGHT - self._bot_mask.get_height()))
        draw_scanlines(surface)
        draw_vignette(surface, strength=140)

        if pitch:
            dfont = kit.font(13, "bold")
            dshadow = dfont.render(_PITCH_DATE, True, (4, 5, 8))
            dsurf = dfont.render(_PITCH_DATE, True, kit.AMBER)
            dshadow.set_alpha(150)
            dsurf.set_alpha(200)
            surface.blit(dshadow, (29, 23))
            surface.blit(dsurf, (28, 22))

        hint_alpha = 0
        if self.phase in ("lead", "scroll"):
            hint_alpha = int(175 * max(0.0, min(1.0, (self.t - 0.8) / 1.0)))
        elif self.phase == "hold":
            hint_alpha = int(175 * max(0.0, min(1.0, 1.0 - self.hold_t / 1.4)))

        if hint_alpha > 4:
            hint = kit.font(11).render(_T("credits.controls_hint"), True, kit.MUTED)
            hint.set_alpha(hint_alpha)
            surface.blit(hint, (WIDTH - 28 - hint.get_width(), HEIGHT - 28))

        if self._fast and self.phase == "scroll":
            fwd = kit.font(11, "bold").render(_T("credits.fast_forward"), True, kit.AMBER)
            surface.blit(fwd, (28, HEIGHT - 28))


_ROLL: CreditsRoll | None = None


def _roll():
    global _ROLL
    if _ROLL is None:
        _ROLL = CreditsRoll()
    return _ROLL


def begin():
    _roll().reset()


def handle_event(event):
    return _roll().handle_event(event)


def update(dt, keys=None):
    return _roll().update(dt, keys)


def draw(surface):
    _roll().draw(surface)
