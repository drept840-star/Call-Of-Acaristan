
"""Split from menu.py - see menu.py (shim) for the map."""
import math
import pygame
from core.config import (C_GREY, C_ORANGE, C_WHITE, HEIGHT, audio, font_btn)

from core.state import STATE
from engine.text import T as _T  # RPE6 Phase 4 text table


# ─────────────────────────────────────────────────────────────────────────────
# Shared hover bookkeeping (for the custom arrow cursor)
# ─────────────────────────────────────────────────────────────────────────────
# ui.main.draw_menu_cursor() wants to know "is the pointer over something
# clickable?" so it can switch from white to orange. Every interactive widget
# already calls check_hover() once per frame, so a single module-level flag
# covers every menu screen without each screen knowing the cursor exists.
#
# The cursor CONSUMES the flag (reads + clears) when it draws, which is the
# last thing to happen each frame. Any screen that draws no cursor simply
# leaves it clear for the next one.
_hover_hot = False


def note_hover(hot=True):
    """Mark that the pointer is over an interactive widget this frame."""
    global _hover_hot
    if hot:
        _hover_hot = True


def consume_hover():
    """Return (and clear) whether anything was hovered since the last frame."""
    global _hover_hot
    hot = _hover_hot
    _hover_hot = False
    return hot


def clipboard_text(max_len=512):
    """Best-effort clipboard read, for Ctrl+V paste in text fields.

    Every text box in the game types via ``KEYDOWN.unicode``, but a paste
    is not a keypress - SDL delivers it as a ``TEXTINPUT`` event that no
    field reads, so Ctrl+V silently did nothing. Paste must therefore pull
    the clipboard explicitly. Returns "" on any platform/init failure, and
    strips non-printable characters (clipboards often carry a trailing NUL,
    and a single-line field must not gain newlines/tabs).
    """
    try:
        if not (pygame.scrap.get_init() or pygame.scrap.init()):
            return ""
        data = pygame.scrap.get(pygame.SCRAP_TEXT)
    except Exception:
        return ""
    if not data:
        return ""
    if isinstance(data, (bytes, bytearray)):
        try:
            data = bytes(data).decode("utf-8")
        except UnicodeDecodeError:
            data = bytes(data).decode("latin-1", "ignore")
    return "".join(ch for ch in str(data) if ch.isprintable())[:max_len]


class ModernButton:
    """Menu button with dt-based scale, glow, and click feedback.

    Polish layers (applied on top of the existing slide-on-hover behavior):
      - Hover:   text scales up to 1.04x, left accent bar gets a soft orange
                 glow halo, chevron brightens.
      - Click:   button visually dips +2px on Y and emits a brief 180ms white
                 flash overlay.
      - Keyboard selection (arrow keys): same visual as hover, plus a brighter
        left bar so the user can always see which item is focused.

    All animation state is updated with delta time so the feel is identical at
    60Hz, 144Hz, or under frame drops. The lerp constants below are tuned for
    a 60Hz frame; the per-frame coefficient is recomputed from dt so motion
    stays frame-rate independent.
    """

    # Lerp speeds in "fraction of remaining distance per second".
    # Higher = snappier. Tune here, used by _lerp_dt.
    _SLIDE_SPEED = 12.0      # hover slide-in
    _SCALE_SPEED = 14.0      # hover scale-up
    _GLOW_SPEED = 10.0       # left-bar glow ramp
    _PRESS_SPEED = 18.0      # click Y-dip recover
    _FLASH_DECAY = 5.5       # post-click white flash fade

    def __init__(self, x, y, text):

        self.x, self.y, self.text = x, y, text

        self.width, self.height = 300, 40

        self.rect = pygame.Rect(x, y, self.width, self.height)

        self.is_hovered = False
        self.is_selected = False   # keyboard focus (arrow keys)
        self._prev_hover = False

        # Animated state - all updated via dt-based lerp.
        self.anim_offset = 0.0     # horizontal slide on hover
        self.scale = 1.0           # text scale, 1.0 idle → 1.04 hover
        self.glow_alpha = 0.0      # 0..255, left accent bar glow
        self.press_dip = 0.0       # 0..2px Y dip on click
        self.flash_timer = 0.0     # seconds remaining of click flash

        # Pre-rendered glow surface for the left accent bar (regenerated only
        # if the bar geometry changes - currently fixed at 9px wide).
        self._glow_surf = pygame.Surface((24, self.height + 20), pygame.SRCALPHA)

    # ---- public API -------------------------------------------------------

    def update(self, dt):
        """Advance animation state by dt seconds.

        Called once per frame by draw_menu() for every visible button. Idempotent
        when called with dt=0 - safe to skip if the frame is paused.
        """
        active = self.is_hovered or self.is_selected
        # Hover/selected drive the slide + scale + glow in unison so the
        # keyboard-focus and mouse-focus feel identical.
        self.anim_offset = _lerp_dt(self.anim_offset, 20.0 if active else 0.0,
                                    self._SLIDE_SPEED, dt)
        self.scale = _lerp_dt(self.scale, 1.04 if active else 1.0,
                              self._SCALE_SPEED, dt)
        self.glow_alpha = _lerp_dt(self.glow_alpha, 220.0 if active else 0.0,
                                   self._GLOW_SPEED, dt)

        # Click dip recovers on its own.
        if self.press_dip > 0.0:
            self.press_dip = _lerp_dt(self.press_dip, 0.0,
                                      self._PRESS_SPEED, dt)
            if self.press_dip < 0.05:
                self.press_dip = 0.0

        # Flash decays linearly with time.
        if self.flash_timer > 0.0:
            self.flash_timer = max(0.0, self.flash_timer - dt)

    def press(self):
        """Trigger click feedback: 2px Y dip + 180ms white flash."""
        self.press_dip = 2.0
        self.flash_timer = 0.18

    def draw(self, surface):

        text_color = C_WHITE if (self.is_hovered or self.is_selected) else C_GREY

        actual_x = self.x + int(self.anim_offset)
        actual_y = self.y + int(self.press_dip)

        # Always-visible tick mark (orange accent bar on the left)
        tick_col = C_ORANGE if (self.is_hovered or self.is_selected) else (90, 55, 20)
        pygame.draw.rect(surface, tick_col,
                         (self.x - 25, self.y + 6, 3, self.height - 12))

        # Soft glow halo around the left bar - only when active.
        if self.glow_alpha > 4.0:
            self._glow_surf.fill((0, 0, 0, 0))
            for r, a_mult in [(12, 0.25), (8, 0.45), (5, 0.75)]:
                a = int(self.glow_alpha * a_mult)
                if a <= 0:
                    continue
                pygame.draw.rect(
                    self._glow_surf, (255, 120, 0, a),
                    (12 - r, 10 - r + 2, r * 2, self.height + r * 2 - 4),
                    border_radius=r,
                )
            surface.blit(self._glow_surf, (self.x - 36, self.y - 10))

        # Always-visible chevron prefix
        chevron_col = C_ORANGE if (self.is_hovered or self.is_selected) else (110, 110, 110)
        chevron = font_btn.render(_T("widgets.text"), True, chevron_col)
        surface.blit(chevron, (self.x - 15, actual_y + 4))

        # Solid orange left bar + hover background - only when active.
        if self.is_hovered or self.is_selected:
            pygame.draw.rect(surface, C_ORANGE,
                             (actual_x - 15, actual_y, 5, self.height))
            surface.blit(_btn_hover_bg, (actual_x - 5, actual_y))

        # Scaled text. Pygame doesn't do sub-pixel scale cleanly on SysFont,
        # so we round to the nearest int. The 1.04x gain is small but reads
        # clearly in motion.
        text_surf = font_btn.render(self.text, True, text_color)
        if self.scale > 1.01:
            new_w = max(1, int(text_surf.get_width() * self.scale))
            new_h = max(1, int(text_surf.get_height() * self.scale))
            text_surf = pygame.transform.smoothscale(text_surf, (new_w, new_h))
        surface.blit(text_surf, (actual_x, actual_y + 4))

        # Click flash overlay - white tint that fades over 180ms.
        if self.flash_timer > 0.0:
            flash_alpha = int(140 * (self.flash_timer / 0.18))
            flash = pygame.Surface((self.width, self.height), pygame.SRCALPHA)
            flash.fill((255, 240, 200, flash_alpha))
            surface.blit(flash, (actual_x - 5, actual_y))

    def check_hover(self, mp):

        self._prev_hover = self.is_hovered

        self.is_hovered = self.rect.collidepoint(mp)

        if self.is_hovered and not self._prev_hover:

            audio.play("menu_hover", volume=0.3)

        # Report to the shared cursor so the custom arrow can switch to its
        # orange "hot" state on ANY menu screen, not just the main menu.
        if self.is_hovered:
            note_hover()

    def is_clicked(self, event, mp):

        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1 and self.is_hovered:

            audio.play("menu_click", volume=0.5)
            self.press()
            return True

        return False

buttons = [

    ModernButton(135, 330, "CONTINUE"),

    ModernButton(135, 390, "NEW CAMPAIGN"),

    ModernButton(135, 450, "MULTIPLAYER"),

    ModernButton(135, 510, "SETTINGS"),

    ModernButton(135, 570, "EXIT"),

]

# The OUTFITTER deliberately does NOT live here. Acaribucks are earned from
# arena results and spent on loadouts other players see, so the shop belongs
# behind MULTIPLAYER, next to the balance it is fed by - not on the same row as
# NEW CAMPAIGN, where it would read as a campaign feature.

# Pre-rendered overlays and decorations

_menu_overlay = pygame.Surface((500, HEIGHT), pygame.SRCALPHA)

pygame.draw.rect(_menu_overlay, (5, 5, 8, 230), (0, 0, 500, HEIGHT))

# Soft gradient fade on the right edge of the dark panel for smoother transition

for fx in range(40):

    a = int(230 * (1 - fx / 40))

    pygame.draw.line(_menu_overlay, (5, 5, 8, a), (500 - fx, 0), (500 - fx, HEIGHT))

# Faint horizontal scanlines baked into the panel for a CRT terminal feel

for sy in range(0, HEIGHT, 3):

    pygame.draw.line(_menu_overlay, (255, 255, 255, 6), (0, sy), (500, sy))

# Vertical accent bar on the right edge of the panel

pygame.draw.line(_menu_overlay, (255, 120, 0, 70), (498, 0), (498, HEIGHT), 1)

pygame.draw.line(_menu_overlay, (255, 120, 0, 30), (495, 0), (495, HEIGHT), 1)

_btn_hover_bg = pygame.Surface((300, 40), pygame.SRCALPHA)

pygame.draw.rect(_btn_hover_bg, (0, 0, 0, 180), _btn_hover_bg.get_rect())

# Diagonal hatched pattern at very top-right corner of panel

for hx in range(0, 60, 4):

    pygame.draw.line(_menu_overlay, (255, 120, 0, 25), (440 + hx, 0), (500, 60 - hx), 1)

# Subtitle / accent fonts

_subtitle_font = pygame.font.SysFont("Consolas", 18, bold=True)

_tagline_font = pygame.font.SysFont("Consolas", 14, italic=True)

_footer_font = pygame.font.SysFont("Consolas", 12)

_classification_font = pygame.font.SysFont("Consolas", 11, bold=True)

_micro_font = pygame.font.SysFont("Consolas", 10)

_glyph_font = pygame.font.SysFont("Consolas", 10, bold=True)

# Decorative corner ticks - drawn directly to the overlay so they're free at runtime

for cx, cy in [(8, 8), (488, 8), (8, HEIGHT - 8), (488, HEIGHT - 8)]:

    pygame.draw.line(_menu_overlay, (255, 120, 0, 180), (cx, cy), (cx + 12 if cx < 200 else cx - 12, cy), 1)

    pygame.draw.line(_menu_overlay, (255, 120, 0, 180), (cx, cy), (cx, cy + 12 if cy < 200 else cy - 12), 1)

def _lerp_dt(current, target, speed_per_sec, dt):
    """Frame-rate-independent exponential lerp.

    `speed_per_sec` is the approximate "fraction of remaining distance closed
    per second". At 60fps with speed=12, this behaves like the old `* 0.2`
    per-frame lerp but stays correct at any frame rate.
    """
    if dt <= 0:
        return current
    # Equivalent to applying `* k` per-frame where k = 1 - exp(-speed * dt).
    k = 1.0 - math.exp(-speed_per_sec * dt)
    return current + (target - current) * k

# ------------------------------------------------------------
# tools\assemble_final_trailer.py
# ------------------------------------------------------------

"""assemble_final_trailer.py - Post-production assembler for CALL OF ACARISTAN.

Takes the three clean combat acts captured by Terminal 8
(``trailers/fresh_action/act{1,2,3}.mp4``), splices the game's own title /
divider / stamp / end cards between them, and mixes a trailer audio bed
against the in-repo SFX + radio bank.

Design notes
------------
* Title cards are NOT re-implemented. They are rendered headless through the
  game's existing card renderer (``tools/render_trailer_v2.card`` for the
  PLAN_2 title/divider/stamp finish, ``tools/render_trailer.end_card`` for the
  AI-4 CTA lockup), so the cards match the in-game look (Oswald / IBM Plex
  Mono, 255,120,0 accent, vignette, fade finish) instead of being an ffmpeg
  re-creation that drifts.
* The picture is assembled with ffmpeg's ``concat`` *filter* (not the demuxer)
  so a timebase mismatch in the acts cannot silently desync A/V. Every row is
  normalised to 1000x700 @ 30 fps CFR yuv420p and trimmed to its EDL duration
  before the join.
* Final grade follows ``docs/PLAN_3_AUDIO.md`` §5: 1000x700 blur-padded into
  1920x1080 over a darkened blurred background, audio loudnorm'd to
  -14 LUFS / -2 dBTP.
* Audio arrangement follows ``docs/PLAN_3_AUDIO.md`` §1 (arrangement),
  §2.2 (radio filters), §3 (hit stacks) and §4 (beat-sync map), retimed onto
  this assembly's EDL. 100 BPM grid = 0.6 s; every cut lands on the grid.
* **Gunshots are foley-driven, never hand-placed.** The acts are silent -
  ``tools/record_fresh_action.py`` captures with ``SDL_AUDIODRIVER=dummy`` and
  ``set_master_volume(0)``, so it logs every live shot to an
  ``act<N>.foley.json`` sidecar instead of an audio track. Guessing shot times
  here (the old ``4.2 + i*1.4`` loops) put reports on empty picture and left
  real muzzle flashes dry. ``tools/build_sfx_stem.py`` re-renders the real
  ``sfx_wav/`` stacks at the logged ticks; this script calls it with this EDL's
  act offsets and mixes the result as the diegetic stem.

Usage
-----
    python assemble_final_trailer.py
    python assemble_final_trailer.py --probe          # print the EDL only
    python assemble_final_trailer.py --keep-stems     # keep intermediate wavs

Output
------
    trailer_final_master.mp4
"""
