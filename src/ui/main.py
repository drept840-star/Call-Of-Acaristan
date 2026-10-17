
"""Split from menu.py - see menu.py (shim) for the map."""
import math
import pygame
from core.config import (C_BLACK, C_KRAP_BLUE, C_ORANGE, C_WHITE, HEIGHT, WIDTH, audio, bg_image, font_title, get_scaled_mouse, screen)
from engine.core import LEGACY_RNG as _rng_legacy  # RPE6 R6: named 'legacy' rng stream

from core.state import STATE

from core import save_system

from ui.widgets import ModernButton, buttons, consume_hover, _menu_overlay, _btn_hover_bg, _subtitle_font, _tagline_font, _classification_font, _micro_font, _glyph_font, _lerp_dt
from ui.system import _footer_font  # SYSTEM's copy: original file redefines it later, readers see the final object
from engine.core import now_ms as _now_ms  # RPE6 B-001 timebase
from engine.text import T as _T  # RPE6 Phase 4 text table

def draw_menu_background():

    if bg_image:

        screen.blit(bg_image, (0, 0))

    else:

        screen.fill(C_BLACK)

def draw_menu():

    # ── Compute dt and advance all polish animation systems ──
    # Per PYGAME_MASTER_ENGINEER Module 4: dt-based motion so the feel is
    # identical at 60Hz, 144Hz, or under frame drops.
    now_ms = _now_ms()
    if not _anim.initialized:
        _init_menu_anim()
        _anim.last_ms = now_ms
    dt = (now_ms - _anim.last_ms) / 1000.0
    _anim.last_ms = now_ms
    # Clamp dt to a max of 1/15s so a long frame stall (window drag, etc.)
    # doesn't catapult rain drops across the screen.
    dt = min(dt, 1.0 / 15.0)
    _update_menu_anim(dt)

    # ── Detect mouse motion → release keyboard focus ──
    # If the mouse actually moved since last frame, hand control back to the
    # mouse. pygame.mouse.get_rel() returns the delta since the last call.
    mx, my = pygame.mouse.get_rel()
    if mx != 0 or my != 0:
        reset_keyboard_selection()

    # ── Background + rain + embers (under the dark panel) ──
    draw_menu_background()
    _draw_rain(screen)
    _draw_embers(screen)

    # Dark panel overlay (existing CRT-style left panel)
    screen.blit(_menu_overlay, (0, 0))

    # ── Top classification banner OR boot sequence ──
    # On first menu show, the boot banner plays a typewriter sequence.
    # Once done, the normal "// KRAPNET TERMINAL //" banner takes over.
    if not _draw_boot_banner(screen):
        classif_bar = pygame.Surface((460, 22), pygame.SRCALPHA)
        classif_bar.fill((8, 10, 14, 220))
        pygame.draw.line(classif_bar, C_ORANGE, (0, 0), (460, 0), 1)
        pygame.draw.line(classif_bar, C_ORANGE, (0, 21), (460, 21), 1)
        screen.blit(classif_bar, (20, 20))
        classif_text = _classification_font.render(
            _T("menu.krapnet_terminal_clearance_opera"), True, C_ORANGE
        )
        screen.blit(classif_text, (30, 24))

    # ── Title (no glow - kept clean per user preference) ──
    title_x = 40
    title_y = 110
    title_text = "CALL OF ACARISTAN"

    # Measure title for scanline math.
    title_surf = font_title.render(title_text, True, C_WHITE)
    title_w = title_surf.get_width()
    title_h = title_surf.get_height()

    # Drop shadow
    screen.blit(font_title.render(title_text, True, (0, 0, 0)),
                (title_x + 4, title_y + 4))
    # Main title
    screen.blit(title_surf, (title_x, title_y))

    # Scanline drift over the title text (drawn after, additive).
    _draw_scanline_drift(screen, title_x, title_y, title_w, title_h)

    # Orange accent bar under title
    pygame.draw.rect(screen, C_ORANGE, (title_x, title_y + 88, 320, 3))

    # ── Section header above menu buttons ──
    pygame.draw.line(screen, (60, 45, 25), (135, 320), (420, 320), 1)
    section_lbl = _classification_font.render(_T("menu.main_terminal"), True, (140, 100, 50))
    screen.blit(section_lbl, (135, 305))

    # ── Active save slot summary ──
    slot = save_system.get_slot()
    slot_idx = save_system.current_slot_index() + 1
    slot_panel = pygame.Surface((350, 48), pygame.SRCALPHA)
    slot_panel.fill((0, 0, 0, 135))
    pygame.draw.rect(slot_panel, (45, 70, 90, 120), slot_panel.get_rect(), 1)
    pygame.draw.line(slot_panel, C_KRAP_BLUE, (0, 0), (0, 48), 3)
    screen.blit(slot_panel, (135, 260))

    active = _footer_font.render(_T("menu.active_save_slot_slot_idx", slot_idx=slot_idx), True, (80, 150, 190))
    last = slot.get("last_completed_label", "No missions completed")
    if slot.get("last_completed_mission"):
        last = "LAST COMPLETED: " + last
    elif slot.get("occupied"):
        progress = slot.get("progress", "")
        if progress == "m1":
            last = "MISSION 1 IN PROGRESS"
        elif progress == "walk":
            last = "WALKING SIM IN PROGRESS"
        else:
            last = slot.get("last_completed_label", "Campaign started")
    else:
        last = "EMPTY SLOT - START A NEW CAMPAIGN"
    last_surf = _footer_font.render(last[:48], True, (145, 145, 135))
    screen.blit(active, (150, 268))
    screen.blit(last_surf, (150, 286))

    # ── Buttons ──
    has_save = save_system.has_any_save()
    if has_save:
        layout = [
            (0, 330, "CONTINUE"),
            (1, 390, "NEW CAMPAIGN"),
            (2, 450, "MULTIPLAYER"),
            (3, 510, "SETTINGS"),
            (4, 570, "EXIT"),
        ]
    else:
        # No Continue button until at least one save slot exists.
        layout = [
            (0, -999, "CONTINUE"),
            (1, 350, "NEW CAMPAIGN"),
            (2, 410, "MULTIPLAYER"),
            (3, 470, "SETTINGS"),
            (4, 530, "EXIT"),
        ]

    # Hide everything first, then place what the layout names. Without this a
    # button missing from the layout keeps the y it was last given, which means
    # it stays visible AND stays clickable at app.py's index - so forgetting an
    # entry here would leave a phantom row that fires some other button's
    # action. Now a forgotten entry simply does not appear.
    for btn in buttons:
        btn.y = -999
        btn.rect.y = -999

    for idx, y, text in layout:
        buttons[idx].text = text
        buttons[idx].y = y
        buttons[idx].rect.y = y

    for i, btn in enumerate(buttons):
        if btn.y < 0:
            btn.is_hovered = False
            btn.is_selected = False
            btn.update(dt)
            continue
        btn.check_hover(get_scaled_mouse())
        # Apply keyboard focus: a button is selected if its index matches
        # the keyboard cursor AND the mouse isn't currently hovering it.
        btn.is_selected = (_anim.keyboard_idx == i) and not btn.is_hovered
        btn.update(dt)
        btn.draw(screen)

    # ── News ticker (above footer) ──
    _draw_news_ticker(screen)

    # ── Bottom divider line above footer ──
    pygame.draw.line(screen, (40, 30, 15), (30, HEIGHT - 50), (470, HEIGHT - 50), 1)

    # ── Footer ──
    footer_left = _footer_font.render(
        _T("menu.v0_1_0_build_4471"), True, (90, 90, 95)
    )
    screen.blit(footer_left, (30, HEIGHT - 38))

    footer_right = _footer_font.render(
        _T("menu.retardovici_inc"), True, (90, 90, 95)
    )
    screen.blit(footer_right, (470 - footer_right.get_width(), HEIGHT - 38))

    # Blinking status indicator
    if (_now_ms() // 600) % 2 == 0:
        pygame.draw.circle(screen, (50, 220, 100), (40, HEIGHT - 22), 3)
    else:
        pygame.draw.circle(screen, (30, 130, 60), (40, HEIGHT - 22), 3)

    status_text = _footer_font.render(_T("menu.connected_krapnet_relay_7"), True, (60, 70, 65))
    screen.blit(status_text, (50, HEIGHT - 26))

    # ── Vignette (drawn last so it darkens the edges over everything) ──
    _draw_vignette(screen)

    # NOTE: the custom arrow cursor is no longer drawn here. It moved to the
    # main loop (draw_menu_cursor, right after the state render pass) so it
    # also covers slot select / multiplayer / settings / pause / death / report
    # / notebook. Drawing it here too would double-blit it and double-apply its
    # additive hover glow.


# States that get the custom arrow instead of the OS pointer. Deliberately
# excludes:
#   GAME / WALK          - aiming states; they use the combat reticle instead
#   CUTSCENE / ESCAPE_CUTSCENE / BOOT_INTRO / ENGINE_INTRO - cinematics
#                          and the studio + engine bumpers, where a
#                          pointer of any kind is out of place
# app.py hides the OS cursor on exactly these states (plus GAME/WALK), so the
# two lists must stay in step or you get either a double cursor or none.
CURSOR_ARROW_STATES = frozenset({
    "MENU", "SLOT_SELECT", "MULTIPLAYER", "SETTINGS", "SHOP", "BRIEFING",
    "PAUSED", "DEATH", "MISSION_COMPLETE", "NOTEBOOK_INSPECT",
})


def draw_menu_cursor(surface=None, state_name=None, suppressed=False):
    """Custom arrow cursor, replacing the OS pointer on every menu screen.

    Tactical pointer arrow (KRAP white, orange on hover) matching the
    menu's orange/white terminal language. Tip is the hotspot.

    Single call site: the main loop, after the state's own render pass (see
    app.py), so the arrow persists across slot select, multiplayer, settings,
    pause, death, mission report and notebook instead of only the main menu.

    *state_name* may be passed by the caller; when omitted it is read off the
    FSM. Screens outside _CURSOR_ARROW_STATES (gameplay, cutscenes, the boot
    bumper) get nothing - gameplay aims with a reticle and cinematics want no
    pointer at all.

    *suppressed* lets the caller force the arrow off for one frame while a
    state still nominally belongs to _CURSOR_ARROW_STATES. MULTIPLAYER is
    such a state: its panel wants the arrow, but once a match is live the
    arena draws the combat reticle and an arrow would stack on top of it.
    """
    if surface is None:
        surface = screen

    if suppressed:
        # Still consume the hover flag so a stale menu hover cannot leak into
        # the next menu frame while the match owns the pointer.
        consume_hover()
        return

    if state_name is None:
        import app as _app
        state_name = getattr(getattr(_app, "gsm", None), "current_name", "")
    if state_name not in CURSOR_ARROW_STATES:
        # Consume anyway so a stale hover can't leak into the next menu frame.
        consume_hover()
        return

    try:
        mx, my = get_scaled_mouse()
    except Exception:
        consume_hover()
        return

    # Shared flag: any ModernButton that reported a hover this frame, on any
    # screen. Falls back to the main-menu button list for callers that render
    # the arrow without the widget pass having run.
    hovered = consume_hover() or any(
        getattr(b, "is_hovered", False)
        for b in buttons
        if getattr(b, "y", -999) > 0
    )
    fill = C_ORANGE if hovered else C_WHITE
    # Arrow body: tip is the hotspot at (mx, my), tail extends down-right.
    pts = [
        (mx, my), (mx, my + 22), (mx + 5.5, my + 16.8),
        (mx + 8.8, my + 24), (mx + 11.4, my + 22.6),
        (mx + 8.2, my + 15.2), (mx + 13.6, my + 15.2),
    ]
    int_pts = [(int(x), int(y)) for x, y in pts]
    if hovered:
        glow = pygame.Surface((44, 44), pygame.SRCALPHA)
        pygame.draw.circle(glow, (255, 120, 0, 50), (22, 22), 16)
        surface.blit(glow, (mx - 22, my - 22),
                     special_flags=pygame.BLEND_RGBA_ADD)
    # Soft drop shadow so the arrow survives bright bg art.
    shadow = [(x + 1, y + 2) for x, y in int_pts]
    pygame.draw.polygon(surface, (0, 0, 0), shadow)
    # Fill + crisp black edge + KRAP orange spine along the left edge.
    pygame.draw.polygon(surface, fill, int_pts)
    pygame.draw.polygon(surface, (0, 0, 0), int_pts, 2)
    pygame.draw.line(surface, C_ORANGE,
                     (mx + 1, my + 3), (mx + 1, my + 19), 1)


# ═══════════════════════════════════════════════════════════════════════════
# MENU POLISH SYSTEMS
# ─────────────────────────────────────────────────────────────────────────
# Applied per PYGAME_MASTER_ENGINEER Module 2 + Module 4:
#   - dt-based lerp for all motion (frame-rate independent)
#   - separate update() and draw() passes (MVC)
#   - pre-rendered surfaces for static art (vignette, glow sprites)
#
# Systems:
#   _lerp_dt          - frame-rate-independent lerp helper
#   _anim             - module-level state for all polish systems
#   _init_menu_anim   - populate rain drops + embers (idempotent)
#   _update_menu_anim - step all animations forward by dt seconds
#   _draw_rain        - 3-layer parallax rain + ground splashes
#   _draw_embers      - drifting fire embers from right-side glow
#   _draw_vignette    - radial dark edge overlay
#   _draw_title_glow  - pulsing orange halo behind the title
#   _draw_scanline_drift - moving horizontal scanline over the title
#   _draw_boot_banner - typewriter KRAPNET boot text on first menu show
#   _draw_news_ticker - scrolling lore ticker above the footer
#
# Keyboard navigation (Module 2 accessibility):
#   keyboard_idx                  - currently focused button index, -1 = mouse
#   handle_menu_keydown(event)    - call from acaristan MENU-state KEYDOWN
#   consume_keyboard_trigger()    - returns button index to fire, or -1
# ═══════════════════════════════════════════════════════════════════════════





# ── Module-level animation state ─────────────────────────────────────────
# All long-lived state for the polish systems lives here, initialized lazily
# on first draw_menu() call so we don't pay for it during gameplay.

class _MenuAnimState:
    """Holds all per-frame animation state for the menu polish systems.

    Kept as a plain class (not a dict) so attribute typos raise immediately.
    """

    def __init__(self):
        self.initialized = False
        self.last_ms = 0           # last pygame.time.get_ticks() value
        self.t = 0.0               # total elapsed time (seconds) since first draw
        self.rain_drops = []       # list of dicts: x, y, length, speed, layer, alpha
        self.splashes = []         # list of dicts: x, y, age, max_age, radius
        self.embers = []           # list of dicts: x, y, vx, vy, age, max_age, brightness
        self.vignette = None       # pre-rendered radial dark edge surface
        self.title_glow_pulse = 0.0  # 0..1, oscillates with sin(t * 1.8)
        self.boot_done = False
        self.boot_t = 0.0          # seconds since first menu draw
        self.boot_chars_typed = 0  # typewriter cursor for boot banner
        self.ticker_offset = 0.0   # pixels scrolled
        # Keyboard nav
        self.keyboard_idx = -1     # -1 = mouse control, 0..N-1 = focused button
        self.pending_trigger = -1  # button index that should fire this frame, or -1


_anim = _MenuAnimState()


# ── Boot sequence text ───────────────────────────────────────────────────
# Typewriter-rendered line-by-line in the classification banner area on the
# first menu show after launch. Each line appears with a small delay; once
# all lines are typed, the normal "// KRAPNET TERMINAL - CLEARANCE //
# banner takes over.
_BOOT_LINES = [
    "> KRAPNET TERMINAL v7.2.1",
    "> ESTABLISHING UPLINK ........ OK",
    "> AUTHENTICATING OPERATOR .... OK",
    "> CLEARANCE: OPERATOR",
    "> READY.",
]
_BOOT_LINE_DELAY = 0.18   # seconds between lines starting
_BOOT_CHAR_RATE  = 35.0   # chars per second


# ── News ticker messages ─────────────────────────────────────────────────
# Looping lore ticker that scrolls right-to-left above the footer. Each item
# is separated by a small orange diamond.
_TICKER_ITEMS = [
    "ROUTE 12 CHECKPOINT REMAINS UNDER KRAP CONTROL",
    "MAG SPOKESMAN DENIES INVOLVEMENT IN HIGHWAY BOMBING",
    "SEBY INVESTIGATION: NO NEW LEADS, SOURCES SAY",
    "IPA REINFORCEMENTS ARRIVING FROM THE NORTH - EXPECT DELAYS",
    "BIRIBEL TASKING ORDERS UPDATED - RELAY 7",
    "FUEGOTECH K1 LAUNCH PARTY INVITES LEAKED ONLINE",
    "WEATHER: HEAVY RAIN, VISIBILITY LOW - ALL ROUTES",
    "KRAP PUBLIC AFFAIRS: 'WE HAVE THE SITUATION IN HAND'",
]
_TICKER_SPEED = 60.0  # pixels per second


def _init_menu_anim():
    """Populate rain drops, embers, and pre-rendered surfaces.

    Idempotent - safe to call multiple times, only the first call does work.
    """
    if _anim.initialized:
        return
    _anim.initialized = True
    _anim.last_ms = _now_ms()

    # ---- Rain: 3 layers, very subtle ----
    # Tuned WAY down per user feedback ("pretty eh"). Now reads as a faint
    # atmospheric hint rather than a full storm - short streaks, dim alpha,
    # only 40 drops total across all three layers.
    layer_specs = [
        # (count, length_range, speed_range, alpha_range, thickness)
        (18, (6, 10),  (160, 240), (35, 60),   1),   # far - barely visible
        (15, (10, 16), (280, 380), (60, 90),   1),   # mid
        (7,  (16, 22), (440, 560), (90, 130),  1),   # near - slightly brighter
    ]
    for count, lr, sr, ar, thick in layer_specs:
        for _ in range(count):
            _anim.rain_drops.append({
                "x": _rng_legacy.uniform(0, WIDTH + 80),
                "y": _rng_legacy.uniform(0, HEIGHT),
                "length": _rng_legacy.uniform(*lr),
                "speed": _rng_legacy.uniform(*sr),
                "alpha": _rng_legacy.randint(*ar),
                "thickness": thick,
                # All drops share the same wind angle for visual coherence.
                "wind": -0.18,  # radians from vertical, blows slightly left
            })

    # ---- Vignette: pre-rendered radial gradient ----
    # Transparent in the center, dark at the edges. Built once and reused.
    vig = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
    cx, cy = WIDTH // 2, HEIGHT // 2
    max_r = math.hypot(cx, cy)
    # Render as concentric rings from outside in - cheaper per-ring than
    # per-pixel, and the gradient is smooth enough at this resolution.
    for r in range(int(max_r), 0, -2):
        # 0 at center, 1 at edge.
        t = r / max_r
        # Ease so the darkening is concentrated near the edges.
        eased = t ** 2.2
        alpha = int(180 * eased)
        if alpha < 2:
            continue
        pygame.draw.circle(vig, (0, 0, 0, alpha), (cx, cy), r)
    _anim.vignette = vig


def _update_menu_anim(dt):
    """Advance all animation systems by dt seconds."""
    if not _anim.initialized:
        _init_menu_anim()

    _anim.t += dt
    _anim.title_glow_pulse = 0.5 + 0.5 * math.sin(_anim.t * 1.8)

    # ---- Rain drops ----
    ground_y = int(HEIGHT * 0.88)
    for d in _anim.rain_drops:
        # Velocity vector: mostly downward, slight wind slant.
        vx = math.sin(d["wind"]) * d["speed"]
        vy = math.cos(d["wind"]) * d["speed"]
        d["x"] += vx * dt
        d["y"] += vy * dt
        # Wrap when off-screen.
        if d["y"] > ground_y:
            # Spawn a splash ripple on impact (rare, only mid/near layers
            # - kept sparse per "rain is pretty eh" feedback).
            if d["thickness"] >= 1 and _rng_legacy.random() < 0.12:
                _anim.splashes.append({
                    "x": d["x"],
                    "y": ground_y + _rng_legacy.uniform(0, 6),
                    "age": 0.0,
                    "max_age": _rng_legacy.uniform(0.35, 0.55),
                    "radius": _rng_legacy.uniform(3, 6),
                })
            d["y"] = _rng_legacy.uniform(-40, 0)
            d["x"] = _rng_legacy.uniform(-40, WIDTH + 80)
        elif d["x"] < -50:
            d["x"] = WIDTH + 40

    # ---- Splashes ----
    # Cheap pooled list - remove in place by swapping with the last element.
    i = 0
    while i < len(_anim.splashes):
        s = _anim.splashes[i]
        s["age"] += dt
        if s["age"] >= s["max_age"]:
            _anim.splashes[i] = _anim.splashes[-1]
            _anim.splashes.pop()
        else:
            i += 1

    # ---- Embers ----
    # Spawn new embers from the right edge (where the bg fire glow lives).
    # Rate scales with dt so spawn density is frame-rate independent.
    spawn_chance = 60.0 * dt  # avg 60 per second
    while spawn_chance > 0:
        if _rng_legacy.random() < min(1.0, spawn_chance):
            _anim.embers.append({
                "x": _rng_legacy.uniform(WIDTH - 80, WIDTH + 10),
                "y": _rng_legacy.uniform(HEIGHT * 0.45, HEIGHT * 0.85),
                "vx": _rng_legacy.uniform(-1.5, -0.4),
                "vy": _rng_legacy.uniform(-1.2, -0.2),
                "age": 0.0,
                "max_age": _rng_legacy.uniform(2.0, 4.0),
                "brightness": _rng_legacy.uniform(0.6, 1.0),
                "size": _rng_legacy.randint(1, 2),
            })
        spawn_chance -= 1.0

    i = 0
    while i < len(_anim.embers):
        e = _anim.embers[i]
        e["age"] += dt
        e["x"] += e["vx"]
        e["y"] += e["vy"]
        # Slight upward acceleration as the ember heats.
        e["vy"] -= 0.02 * dt * 60
        if e["age"] >= e["max_age"] or e["x"] < -10 or e["y"] < -10:
            _anim.embers[i] = _anim.embers[-1]
            _anim.embers.pop()
        else:
            i += 1

    # ---- Boot sequence ----
    if not _anim.boot_done:
        _anim.boot_t += dt
        # Total chars across all lines + delays between lines.
        total_chars = sum(len(line) for line in _BOOT_LINES)
        total_delays = _BOOT_LINE_DELAY * len(_BOOT_LINES)
        total_duration = total_chars / _BOOT_CHAR_RATE + total_delays
        _anim.boot_chars_typed = int(
            max(0.0, _anim.boot_t) * _BOOT_CHAR_RATE
        )
        if _anim.boot_t >= total_duration + 0.4:
            _anim.boot_done = True

    # ---- News ticker ----
    _anim.ticker_offset += _TICKER_SPEED * dt
    # Wrap when we've scrolled one full loop width.
    # Computed lazily in _draw_news_ticker; just keep the offset bounded.
    if _anim.ticker_offset > 10_000:
        _anim.ticker_offset -= 10_000


# ── Draw helpers ─────────────────────────────────────────────────────────


def _draw_rain(surface):
    """3-layer parallax rain + ground splashes."""
    if not _anim.initialized:
        return
    # Single scratch surface for all drops - drawn once per frame, cheaper
    # than per-drop SRCALPHA surfaces.
    rain_surf = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
    for d in _anim.rain_drops:
        vx = math.sin(d["wind"])
        vy = math.cos(d["wind"])
        x2 = d["x"] + vx * d["length"]
        y2 = d["y"] + vy * d["length"]
        col = (180, 200, 220, d["alpha"])
        if d["thickness"] == 1:
            pygame.draw.line(rain_surf, col,
                             (int(d["x"]), int(d["y"])),
                             (int(x2), int(y2)), 1)
        else:
            pygame.draw.line(rain_surf, col,
                             (int(d["x"]), int(d["y"])),
                             (int(x2), int(y2)), 2)
    surface.blit(rain_surf, (0, 0))

    # Splashes on top of rain.
    if _anim.splashes:
        splash_surf = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        for s in _anim.splashes:
            t = s["age"] / s["max_age"]
            r = int(s["radius"] * (1 + t * 3))
            a = int(180 * (1 - t))
            if a <= 0 or r <= 0:
                continue
            pygame.draw.ellipse(
                splash_surf, (180, 200, 220, a),
                (int(s["x"] - r), int(s["y"] - r // 2), r * 2, r),
                1,
            )
        surface.blit(splash_surf, (0, 0))


def _draw_embers(surface):
    """Drifting fire embers from the right-side bg glow."""
    if not _anim.initialized or not _anim.embers:
        return
    em_surf = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
    for e in _anim.embers:
        t = e["age"] / e["max_age"]
        # Brightness fades in then out.
        fade = math.sin(t * math.pi) * e["brightness"]
        if fade <= 0:
            continue
        # Color: bright yellow at birth → orange mid → red at death.
        if t < 0.4:
            col = (255, int(180 + 60 * (1 - t / 0.4)), 80, int(220 * fade))
        elif t < 0.75:
            col = (255, 130, 40, int(220 * fade))
        else:
            col = (220, 80, 30, int(180 * fade))
        r = e["size"]
        pygame.draw.circle(em_surf, col, (int(e["x"]), int(e["y"])), r)
        # Soft halo around bright embers.
        if fade > 0.5:
            halo_a = int(60 * fade)
            pygame.draw.circle(
                em_surf, (255, 140, 60, halo_a),
                (int(e["x"]), int(e["y"])), r * 2, 1
            )
    surface.blit(em_surf, (0, 0))


def _draw_vignette(surface):
    """Pre-rendered radial dark edge overlay."""
    if _anim.vignette is not None:
        surface.blit(_anim.vignette, (0, 0))


def _draw_title_glow(surface, title_x, title_y, title_w, title_h):
    """Slow orange glow pulse behind the title."""
    if not _anim.initialized:
        return
    # Glow size covers the title plus a 40px margin.
    glow_w = title_w + 80
    glow_h = title_h + 60
    glow = pygame.Surface((glow_w, glow_h), pygame.SRCALPHA)
    cx, cy = glow_w // 2, glow_h // 2
    max_r = math.hypot(cx, cy)
    pulse = _anim.title_glow_pulse
    # Layered concentric ellipses, each softer than the last.
    for r in range(int(max_r), 4, -8):
        t = r / max_r
        eased = (1 - t) ** 2
        alpha = int(45 * eased * pulse)
        if alpha < 2:
            continue
        pygame.draw.ellipse(
            glow, (255, 120, 0, alpha),
            (cx - r, cy - int(r * 0.55), r * 2, int(r * 1.1))
        )
    surface.blit(
        glow,
        (title_x + title_w // 2 - glow_w // 2,
         title_y + title_h // 2 - glow_h // 2),
        special_flags=pygame.BLEND_RGBA_ADD,
    )


def _draw_scanline_drift(surface, x, y, w, h):
    """A bright horizontal scanline that slowly drifts across the title."""
    if not _anim.initialized:
        return
    # Drift period: 5 seconds top-to-bottom.
    period = 5.0
    t = (_anim.t % period) / period
    line_y = y + int(t * h)
    # Bright line + soft glow above/below.
    line_surf = pygame.Surface((w, 12), pygame.SRCALPHA)
    for i in range(12):
        a = int(80 * (1 - abs(i - 6) / 6))
        if a > 0:
            pygame.draw.line(line_surf, (255, 200, 140, a),
                             (0, i), (w, i), 1)
    surface.blit(line_surf, (x, line_y - 6),
                 special_flags=pygame.BLEND_RGBA_ADD)


def _draw_boot_banner(surface):
    """Typewriter KRAPNET boot sequence shown on first menu show.

    Returns True while the boot is still playing (so draw_menu can suppress
    the normal classification banner), False when done.
    """
    if _anim.boot_done:
        return False

    # Backdrop - same dimensions as the normal classification banner.
    banner = pygame.Surface((460, 22), pygame.SRCALPHA)
    banner.fill((8, 10, 14, 230))
    pygame.draw.line(banner, C_ORANGE, (0, 0), (460, 0), 1)
    pygame.draw.line(banner, C_ORANGE, (0, 21), (460, 21), 1)
    surface.blit(banner, (20, 20))

    # Render lines with a typewriter effect, staggered by _BOOT_LINE_DELAY.
    chars_remaining = _anim.boot_chars_typed
    y_offset = 24
    for line_idx, line in enumerate(_BOOT_LINES):
        # Each line starts typing at line_idx * _BOOT_LINE_DELAY worth of
        # chars consumed.
        start_chars = int(line_idx * _BOOT_LINE_DELAY * _BOOT_CHAR_RATE)
        if chars_remaining <= start_chars:
            break
        chars_on_this_line = min(
            len(line), chars_remaining - start_chars
        )
        visible = line[:chars_on_this_line]
        # Blinking cursor on the line currently being typed.
        if chars_on_this_line < len(line) and \
           (line_idx == len(_BOOT_LINES) - 1 or
            chars_remaining < start_chars + len(line)):
            if int(_anim.t * 3) % 2 == 0:
                visible += "_"
        surf = _classification_font.render(visible, True, C_ORANGE)
        surface.blit(surf, (30, y_offset))
        y_offset += 14
        if y_offset > 64:  # clamp to banner area
            break

    return True


def _draw_news_ticker(surface):
    """Scrolling lore ticker above the footer."""
    # Compose the full ticker string with separators.
    # ASCII separator: "◆" is tofu on the bundled font, so never render it.
    separator = " // "
    full = separator.join(_TICKER_ITEMS) + separator
    full_surf = _footer_font.render(full, True, (180, 160, 110))
    sep_surf = _footer_font.render(separator, True, C_ORANGE)
    sep_w = sep_surf.get_width()
    full_w = full_surf.get_width()

    # Ticker area: above the footer divider line, full width of the dark panel.
    ticker_y = HEIGHT - 56
    ticker_h = 18
    # Backdrop strip.
    strip = pygame.Surface((WIDTH, ticker_h), pygame.SRCALPHA)
    strip.fill((0, 0, 0, 150))
    surface.blit(strip, (0, ticker_y))

    # KRAPNET WIRE label on the left - static.
    label = _classification_font.render(_T("menu.krapnet_wire"), True, C_ORANGE)
    label_w = label.get_width() + 16
    surface.blit(label, (8, ticker_y + 2))
    # Vertical separator after the label.
    pygame.draw.line(surface, (90, 60, 25),
                     (label_w, ticker_y),
                     (label_w, ticker_y + ticker_h), 1)

    # Scrolling text window: from label_w to WIDTH.
    window_w = WIDTH - label_w - 4
    if window_w <= 0 or full_w <= 0:
        return

    # Offset wraps modulo (full_w + sep_w) so the loop is seamless.
    period = full_w + sep_w
    offset = int(_anim.ticker_offset) % period

    # Draw the text twice - once at -offset, once at (period - offset) - so
    # the loop has no visible gap when it wraps.
    clip_rect = pygame.Rect(label_w + 2, ticker_y, window_w, ticker_h)
    prev_clip = surface.get_clip()
    surface.set_clip(clip_rect)
    surface.blit(full_surf, (label_w + 4 - offset, ticker_y + 2))
    surface.blit(full_surf, (label_w + 4 - offset + period, ticker_y + 2))
    surface.set_clip(prev_clip)

    # Top border line on the ticker strip.
    pygame.draw.line(surface, (60, 40, 15),
                     (0, ticker_y), (WIDTH, ticker_y), 1)


# ── Keyboard navigation API ──────────────────────────────────────────────
# Public functions called by acaristan.py. Designed so the existing mouse
# click path keeps working unchanged - keyboard input is layered on top.


def _visible_button_indices():
    """Return list of indices into `buttons[]` that are currently on-screen.

    draw_menu() sets each button's `y` to -999 when it should be hidden
    (e.g. CONTINUE when no save exists). We respect that convention here.
    """
    return [i for i, b in enumerate(buttons) if b.y > 0]


def handle_menu_keydown(event):
    """Process a KEYDOWN event in the MENU state.

    Call from acaristan.py's event loop when game_state == "MENU".
    Returns None - side effects are stored in _anim.pending_trigger, which
    acaristan.py reads via consume_keyboard_trigger().
    """
    if not _anim.initialized:
        _init_menu_anim()

    if event.key in (pygame.K_UP, pygame.K_w):
        visible = _visible_button_indices()
        if not visible:
            return
        if _anim.keyboard_idx == -1:
            # Initializing from mouse control - pick the bottom visible.
            _anim.keyboard_idx = visible[-1]
        elif _anim.keyboard_idx in visible:
            i = visible.index(_anim.keyboard_idx)
            _anim.keyboard_idx = visible[(i - 1) % len(visible)]
        else:
            _anim.keyboard_idx = visible[-1]
        audio.play("menu_hover", volume=0.3)
    elif event.key in (pygame.K_DOWN, pygame.K_s):
        visible = _visible_button_indices()
        if not visible:
            return
        if _anim.keyboard_idx == -1:
            _anim.keyboard_idx = visible[0]
        elif _anim.keyboard_idx in visible:
            i = visible.index(_anim.keyboard_idx)
            _anim.keyboard_idx = visible[(i + 1) % len(visible)]
        else:
            _anim.keyboard_idx = visible[0]
        audio.play("menu_hover", volume=0.3)
    elif event.key in (pygame.K_RETURN, pygame.K_SPACE):
        if _anim.keyboard_idx != -1:
            _anim.pending_trigger = _anim.keyboard_idx
            buttons[_anim.keyboard_idx].press()
            audio.play("menu_click", volume=0.5)


def consume_keyboard_trigger():
    """Return the button index that should fire this frame, or -1.

    acaristan.py should call this after draw_menu() and route the trigger
    through the same action handlers as a mouse click.
    """
    t = _anim.pending_trigger
    _anim.pending_trigger = -1
    return t


def reset_keyboard_selection():
    """Clear keyboard focus - called when the mouse moves."""
    _anim.keyboard_idx = -1


# ─────────────────────────────────────────────

# SERVER BROWSER

# ─────────────────────────────────────────────
