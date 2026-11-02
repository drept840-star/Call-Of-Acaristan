"""Split from menu.py - see menu.py (shim) for the map."""
import math
import time
import pygame
from core.config import (C_BLACK, C_ORANGE, C_WHITE, HEIGHT, WIDTH, audio, bg_image, font_title, get_scaled_mouse, screen)
from engine.core import LEGACY_RNG as _rng_legacy  # RPE6 R6: named 'legacy' rng stream

from core.state import STATE

from core import save_system

from ui.widgets import ModernButton, buttons, consume_hover, note_hover, _menu_overlay, _btn_hover_bg, _subtitle_font, _tagline_font, _classification_font, _micro_font, _glyph_font, _lerp_dt
from engine.core import now_ms as _now_ms  # RPE6 B-001 timebase
from engine.text import T as _T  # RPE6 Phase 4 text table
from pathlib import Path as _Path
from ui import kit


def _resolve_menu_version_override() -> str:
    try:
        from launcher import load_local_version
        lv = load_local_version(_Path(__file__).resolve().parents[2])
        if (lv.version, lv.build) != ("0.1.0", "4471"):
            return f"v{lv.version}  \u00b7  BUILD {lv.build}"
    except Exception:
        pass
    return ""


_menu_version_override = _resolve_menu_version_override()


def draw_menu_background():
    """Sub-screen backdrop: the menu art under the kit's ink wash."""
    kit.backdrop(screen)

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

    # ── Background + rain + embers, then the ink shades ──
    # Mouse parallax: the art drifts against the pointer, the rain/ember
    # foreground drifts with it, so the right side reads as depth.
    bg_off, fg_off = _parallax_offsets(dt)
    if _anim.parallax_bg is not None:
        screen.blit(_anim.parallax_bg,
                    (bg_off[0] - _PARALLAX_PAD_X, bg_off[1] - _PARALLAX_PAD_Y))
    else:
        draw_menu_background()
    _draw_rain(screen, fg_off)
    _draw_embers(screen, fg_off)
    screen.blit(_anim.shade_left, (0, 0))
    screen.blit(_anim.shade_bottom, (0, HEIGHT - _anim.shade_bottom.get_height()))

    _draw_top_bar(screen)
    _draw_title(screen)

    # ── Buttons ──
    # Index order is a contract with app.py's routing; CONTINUE only shows
    # once a save slot exists.
    names = ["CONTINUE", "NEW CAMPAIGN", "MULTIPLAYER", "SETTINGS", "EXIT"]
    shown = range(5) if save_system.has_any_save() else range(1, 5)
    layout = [(idx, _ROW_TOP + n * _ROW_STEP, names[idx]) for n, idx in enumerate(shown)]

    # Hide everything first, then place what the layout names. Without this a
    # button missing from the layout keeps the y it was last given, which means
    # it stays visible AND stays clickable at app.py's index - so forgetting an
    # entry here would leave a phantom row that fires some other button's
    # action. Now a forgotten entry simply does not appear.
    for btn in buttons:
        btn.y = -999
        btn.rect.y = -999

    # Hitboxes span the whole row and close the vertical gaps between rows,
    # so a click anywhere on the line counts, not just on the letters.
    for idx, y, text in layout:
        buttons[idx].text = text
        buttons[idx].y = y
        buttons[idx].rect.update(_ROW_X, y, _ROW_W, _ROW_STEP)

    kit.section(screen, _T("menu.main_terminal"), _ROW_X + 18, _ROW_TOP - 22, _ROW_W - 18)
    focused = None
    for n, (idx, y, text) in enumerate(layout):
        btn = buttons[idx]
        btn.check_hover(get_scaled_mouse())
        # Apply keyboard focus: a button is selected if its index matches
        # the keyboard cursor AND the mouse isn't currently hovering it.
        btn.is_selected = (_anim.keyboard_idx == idx) and not btn.is_hovered
        btn.update(dt)
        if btn.is_hovered or btn.is_selected:
            focused = btn
        _draw_row(screen, btn, n, _reveal(0.15 + n * 0.06))
    for btn in buttons:
        if btn.y < 0:
            btn.is_hovered = False
            btn.is_selected = False
            btn.update(dt)

    _draw_brief(screen, focused, _ROW_TOP + len(layout) * _ROW_STEP + 12, dt)
    _draw_slot_card(screen)

    # ── News ticker + footer ──
    _draw_news_ticker(screen)
    footer_ver_str = _T("menu.v0_1_0_build_4471")
    if _menu_version_override:
        footer_ver_str = _menu_version_override
    kit.text(screen, footer_ver_str, 24, HEIGHT - 27, 11, kit.MUTED)
    kit.key_hints(screen, [("ARROWS", "SELECT"), ("ENTER", "OPEN"), ("TAB", "SWITCH FILE")],
                  WIDTH // 2 + 170, HEIGHT - 29)
    kit.text(screen, _T("menu.retardovici_inc"), WIDTH - 24, HEIGHT - 27, 11, kit.MUTED,
             align="right")

    # ── Vignette (drawn last so it darkens the edges over everything) ──
    _draw_vignette(screen)

    # NOTE: the custom arrow cursor is no longer drawn here. It moved to the
    # main loop (draw_menu_cursor, right after the state render pass) so it
    # also covers slot select / multiplayer / settings / pause / death / report
    # / notebook. Drawing it here too would double-blit it and double-apply its
    # additive hover glow.


def _reveal(delay, dur=0.4):
    """0..1 ease-out for the intro stagger, *delay* seconds after first show.

    Frame count backs the clock up, so a pinned timebase (headless tools)
    still ends with the menu fully drawn.
    """
    t = max(0.0, min(1.0, (max(_anim.t, _anim.frames / 60.0) - delay) / dur))
    return 1.0 - (1.0 - t) ** 3


def _draw_top_bar(surface):
    """Full-width status strip: boot log, then the clearance line and a clock."""
    pygame.draw.rect(surface, kit.INK, (0, 0, WIDTH, 26))
    pygame.draw.line(surface, kit.EDGE, (0, 26), (WIDTH, 26))
    pygame.draw.rect(surface, kit.ORANGE, (0, 0, 4, 26))
    if not _draw_boot_banner(surface):
        kit.text(surface, _T("menu.krapnet_terminal_clearance_opera"), 20, 6, 11, kit.AMBER, "bold")
    live = (_now_ms() // 600) % 2 == 0
    r = kit.text(surface, time.strftime("%H:%M:%S"), WIDTH - 20, 6, 11, kit.DIM, "bold", "right")
    r = kit.text(surface, _T("menu.connected_krapnet_relay_7"), r.x - 22, 6, 11, kit.MUTED,
                 align="right")
    pygame.draw.circle(surface, kit.GOOD if live else (40, 120, 70), (r.x - 10, 13), 3)


def _draw_title(surface):
    """Two-line wordmark, rendered once; slides up and fades in on first show."""
    if _anim.title_surf is None:
        top = kit.font(30, "display").render("CALL OF", True, kit.AMBER)
        big_f = kit.font(96, "display")
        big = big_f.render("ACARISTAN", True, kit.TEXT)
        shadow = big_f.render("ACARISTAN", True, (0, 0, 0))
        w = max(top.get_width(), big.get_width()) + 6
        # Oswald carries a tall line box; tuck the big line up under the small.
        big_y = top.get_height() - 20
        s = pygame.Surface((w, big_y + big.get_height() + 6), pygame.SRCALPHA)
        s.blit(top, (2, 0))
        s.blit(shadow, (5, big_y + 4))
        s.blit(big, (0, big_y))
        _anim.title_surf = s.subsurface(s.get_bounding_rect()).copy()
    a = _reveal(0.0, 0.6)
    s = _anim.title_surf
    s.set_alpha(int(255 * a))
    y = _TITLE_Y + int(10 * (1 - a))
    surface.blit(s, (_TITLE_X, y))
    rule_y = _TITLE_Y + s.get_height() + 18
    pygame.draw.line(surface, kit.EDGE, (_TITLE_X, rule_y), (_ROW_X + _ROW_W, rule_y))
    pygame.draw.rect(surface, kit.ORANGE, (_TITLE_X, rule_y - 1, int(96 * a), 3))


def _draw_row(surface, btn, n, reveal):
    """One menu row: index, Oswald label, amber wash and bar when focused."""
    hot = btn.is_hovered or btn.is_selected
    g = btn.glow_alpha / 220.0
    r = btn.rect
    box = pygame.Rect(r.x, r.y + 5, r.w, r.h - 10)
    dip = int(btn.press_dip)
    if g > 0.03:
        wash = pygame.Surface(box.size, pygame.SRCALPHA)
        wash.fill((40, 26, 10, int(170 * g)))
        surface.blit(wash, box.topleft)
        pygame.draw.rect(surface, kit.ORANGE, (box.x, box.y, 3, box.h))
        pygame.draw.line(surface, kit.EDGE_HI, (box.x, box.bottom - 1),
                         (box.x + int(box.w * g), box.bottom - 1))
    fade = int(255 * reveal)
    num = kit.font(12, "bold").render("%02d" % (n + 1), True, kit.AMBER if hot else kit.MUTED)
    num.set_alpha(fade)
    surface.blit(num, (box.x + 18, box.centery - num.get_height() // 2 + dip))
    label = _row_font.render(btn.text, True, kit.AMBER if hot else (214, 210, 198))
    label.set_alpha(fade)
    x = box.x + 54 + int(btn.anim_offset * 0.5) - int(28 * (1 - reveal))
    surface.blit(label, (x, box.centery - label.get_height() // 2 - 2 + dip))
    if hot:
        kit.text(surface, ">", box.right - 22, box.centery - 11 + dip, 16, kit.ORANGE, "bold")
    if btn.flash_timer > 0.0:
        flash = pygame.Surface(box.size, pygame.SRCALPHA)
        flash.fill((255, 236, 200, int(110 * btn.flash_timer / 0.18)))
        surface.blit(flash, box.topleft)


def _draw_brief(surface, focused, y, dt):
    """Typed one-line readout of what the focused row does."""
    line = _BRIEFS.get(focused.text, "") if focused else ""
    if line != _anim.brief_line:
        _anim.brief_line = line
        _anim.brief_t = 0.0
    _anim.brief_t += dt
    if not line:
        kit.text(surface, "> " + _BRIEF_IDLE, _ROW_X + 18, y, 12, kit.MUTED)
        return
    shown = line[:int(_anim.brief_t * 90)]
    if int(_anim.t * 3) % 2 == 0:
        shown += "_"
    kit.text(surface, "> " + shown, _ROW_X + 18, y, 12, kit.DIM)


def _slot_status(slot):
    if slot.get("last_completed_mission"):
        return "LAST: " + slot.get("last_completed_label", "Campaign record")
    if slot.get("occupied"):
        progress = slot.get("progress", "")
        if progress == "m1":
            return "MISSION 1 IN PROGRESS"
        if progress == "walk":
            return "WALKING SIM IN PROGRESS"
        return slot.get("last_completed_label", "Campaign started")
    return "EMPTY FILE - START A NEW CAMPAIGN"


def _draw_slot_card(surface):
    """Active operation file, bottom right. Click or TAB cycles the slot."""
    rect = SLOT_PANEL_RECT
    hot = rect.collidepoint(get_scaled_mouse())
    if hot:
        note_hover()
        if not _anim.slot_hot:
            audio.play("menu_hover", volume=0.3)
    _anim.slot_hot = hot
    a = _reveal(0.5)
    plate = pygame.Surface(rect.size, pygame.SRCALPHA)
    plate.fill((*kit.PLATE, int((236 if hot else 214) * a)))
    surface.blit(plate, rect.topleft)
    pygame.draw.rect(surface, kit.EDGE_HI if hot else kit.EDGE, rect, 1)
    pygame.draw.rect(surface, kit.AMBER if hot else kit.STEEL, (rect.x, rect.y, 3, rect.h))
    if a < 1.0:
        return
    data = save_system.load_data()
    cur = save_system.current_slot_index()
    slot = save_system.get_slot()
    x = rect.x + 16
    kit.text(surface, "OPERATION FILE %02d" % (cur + 1), x, rect.y + 10, 11, kit.STEEL, "bold")
    # One pip per slot: filled when occupied, amber outline on the active one.
    for i in range(save_system.SLOT_COUNT):
        pip = pygame.Rect(rect.right - 16 - (save_system.SLOT_COUNT - i) * 14, rect.y + 13, 9, 9)
        if data["slots"][i].get("occupied"):
            pygame.draw.rect(surface, kit.STEEL, pip)
        pygame.draw.rect(surface, kit.AMBER if i == cur else kit.EDGE_HI, pip, 1)
    status = _slot_status(slot)
    kit.text(surface, kit.fit(status, 13, rect.w - 32, "semibold"), x, rect.y + 30, 13,
             kit.TEXT if slot.get("occupied") else kit.DIM, "semibold")
    if slot.get("occupied"):
        meta = "TIME %s  /  %s" % (slot.get("total_time", "00:00"),
                                   save_system.format_timestamp(slot.get("updated_at")))
    else:
        meta = "NO RECORD IN THIS FILE"
    kit.text(surface, kit.fit(meta, 11, rect.w - 120), x, rect.y + 54, 11, kit.MUTED)
    kit.text(surface, "[TAB] SWITCH", rect.right - 14, rect.y + 54, 11,
             kit.AMBER if hot else kit.AMBER_DIM, "bold", "right")


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
    # Terminal amber, so it reads as a KRAPNET OS pointer and not the
    # desktop arrow; it brightens toward pale amber over anything clickable.
    fill = (255, 214, 130) if hovered else _CURSOR_AMBER
    # Arrow body: tip is the hotspot at (mx, my), tail extends down-right.
    pts = [
        (mx, my), (mx, my + 22), (mx + 5.5, my + 16.8),
        (mx + 8.8, my + 24), (mx + 11.4, my + 22.6),
        (mx + 8.2, my + 15.2), (mx + 13.6, my + 15.2),
    ]
    int_pts = [(int(x), int(y)) for x, y in pts]
    if hovered:
        glow = pygame.Surface((44, 44))
        pygame.draw.circle(glow, (60, 28, 0), (22, 22), 16)
        surface.blit(glow, (mx - 22, my - 22),
                     special_flags=pygame.BLEND_RGB_ADD)
    # Soft drop shadow so the arrow survives bright bg art.
    shadow = [(x + 1, y + 2) for x, y in int_pts]
    pygame.draw.polygon(surface, (0, 0, 0), shadow)
    # Fill + crisp black edge + KRAP orange spine along the left edge.
    pygame.draw.polygon(surface, fill, int_pts)
    pygame.draw.polygon(surface, (0, 0, 0), int_pts, 2)
    pygame.draw.line(surface, C_ORANGE,
                     (mx + 1, my + 3), (mx + 1, my + 19), 1)
    # Pixel corner bracket framing the tip (top-left of the hotspot).
    bx, by = mx - 4, my - 4
    for col, o in (((0, 0, 0), 1), (fill, 0)):
        pygame.draw.rect(surface, col, (bx + o, by + o, 5, 2))
        pygame.draw.rect(surface, col, (bx + o, by + o, 2, 5))


_CURSOR_AMBER = (255, 170, 40)

# Main-menu layout. Row hitboxes are _ROW_STEP tall so the gaps close.
_TITLE_X, _TITLE_Y = 56, 62
_ROW_X, _ROW_W = 40, 400
_ROW_TOP, _ROW_STEP = 282, 56
SLOT_PANEL_RECT = pygame.Rect(WIDTH - 334, HEIGHT - 162, 310, 78)
_row_font = kit.font(28, "display")

# One typed line per row, shown under the menu while that row has focus.
_BRIEFS = {
    "CONTINUE": "RESUME THE ACTIVE OPERATION FILE",
    "NEW CAMPAIGN": "OPEN A FRESH OPERATION FILE FROM MISSION 1",
    "MULTIPLAYER": "KRAPNET LOBBIES, ARENA MATCHES, OUTFITTER",
    "SETTINGS": "DISPLAY, AUDIO, CONTROLS, ACCESSIBILITY",
    "EXIT": "CLOSE THE TERMINAL",
}
_BRIEF_IDLE = "AWAITING OPERATOR INPUT"

# Parallax travel in pixels at the screen edge. The art is pre-scaled by
# twice the pad so its edges never come into view.
_PARALLAX_BG = (7, 5)
_PARALLAX_FG = (12, 7)
_PARALLAX_PAD_X, _PARALLAX_PAD_Y = 8, 6
_PARALLAX_SPEED = 6.0


def _parallax_offsets(dt):
    """Smoothed (bg, fg) pixel offsets from the pointer's place on screen."""
    mx, my = get_scaled_mouse()
    nx = max(-1.0, min(1.0, (mx - WIDTH / 2) / (WIDTH / 2)))
    ny = max(-1.0, min(1.0, (my - HEIGHT / 2) / (HEIGHT / 2)))
    _anim.parallax_x = _lerp_dt(_anim.parallax_x, nx, _PARALLAX_SPEED, dt)
    _anim.parallax_y = _lerp_dt(_anim.parallax_y, ny, _PARALLAX_SPEED, dt)
    px, py = _anim.parallax_x, _anim.parallax_y
    bg = (int(round(-px * _PARALLAX_BG[0])), int(round(-py * _PARALLAX_BG[1])))
    fg = (int(round(px * _PARALLAX_FG[0])), int(round(py * _PARALLAX_FG[1])))
    return bg, fg


def slot_panel_clicked(event, mp):
    """Left click on the save slot panel: cycle to the next slot."""
    if not (event.type == pygame.MOUSEBUTTONDOWN and event.button == 1
            and SLOT_PANEL_RECT.collidepoint(mp)):
        return False
    audio.play("menu_click", volume=0.5)
    save_system.select_slot((save_system.current_slot_index() + 1) % save_system.SLOT_COUNT)
    return True


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
        self.slot_hot = False      # pointer over the save slot panel last frame
        # Mouse parallax: smoothed pointer position (-1..1) and padded art.
        self.parallax_x = 0.0
        self.parallax_y = 0.0
        self.parallax_bg = None
        # Overhaul chrome: cached shades and wordmark, typed brief line.
        self.shade_left = None
        self.shade_bottom = None
        self.title_surf = None
        self.brief_line = ""
        self.brief_t = 0.0
        self.ticker_surf = None
        self.frames = 0            # draws since first show; reveal fallback


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
_BOOT_CHAR_RATE  = 70.0   # chars per second


# ── News ticker messages ─────────────────────────────────────────────────
# Looping lore ticker that scrolls right-to-left above the footer. Each item
# is separated by a small orange diamond.
_TICKER_ITEMS = [
    "ROUTE 12 CHECKPOINT REMAINS UNDER KRAP CONTROL",
    "MAG SPOKESMAN DENIES INVOLVEMENT IN HIGHWAY BOMBING",
    "KRAP PATROL SCHEDULE EXTENDED - ROUTE 12",
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

    # ---- Ink shades: solid left column fading into the art, bottom band ----
    shade = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
    solid, fade = 430, 300
    for x in range(solid + fade):
        a = 238 if x < solid else int(238 * (1 - (x - solid) / fade) ** 1.7)
        pygame.draw.line(shade, (*kit.INK, a), (x, 0), (x, HEIGHT))
    _anim.shade_left = shade
    band = pygame.Surface((WIDTH, 190), pygame.SRCALPHA)
    for y in range(190):
        pygame.draw.line(band, (*kit.INK, int(200 * (y / 189) ** 1.5)), (0, y), (WIDTH, y))
    _anim.shade_bottom = band

    # ---- Parallax art: menu bg grown by the pad on every side ----
    if bg_image:
        _anim.parallax_bg = pygame.transform.scale(
            bg_image, (WIDTH + 2 * _PARALLAX_PAD_X, HEIGHT + 2 * _PARALLAX_PAD_Y))


def _update_menu_anim(dt):
    """Advance all animation systems by dt seconds."""
    if not _anim.initialized:
        _init_menu_anim()

    _anim.t += dt
    _anim.frames += 1
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


def _draw_rain(surface, offset=(0, 0)):
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
    surface.blit(rain_surf, offset)

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
        surface.blit(splash_surf, offset)


def _draw_embers(surface, offset=(0, 0)):
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
    surface.blit(em_surf, offset)


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
    """Typewriter KRAPNET boot sequence in the top bar on first menu show.

    Types the lines one after another on the bar's single line. Returns True
    while the boot is still playing (so the bar skips its clearance line),
    False when done.
    """
    if _anim.boot_done:
        return False
    chars = _anim.boot_chars_typed
    line = ""
    for line_idx, candidate in enumerate(_BOOT_LINES):
        # Each line starts typing after the previous one plus a short pause.
        start = sum(len(l) for l in _BOOT_LINES[:line_idx]) + \
            int(line_idx * _BOOT_LINE_DELAY * _BOOT_CHAR_RATE)
        if chars <= start:
            break
        line = candidate[:chars - start]
    if int(_anim.t * 3) % 2 == 0:
        line += "_"
    kit.text(surface, line, 20, 6, 11, kit.AMBER, "bold")
    return True


def _draw_news_ticker(surface):
    """Scrolling lore ticker above the footer."""
    # ASCII separator: "◆" is tofu on the bundled font, so never render it.
    separator = "   //   "
    if _anim.ticker_surf is None:
        f = kit.font(11)
        _anim.ticker_surf = f.render(separator.join(_TICKER_ITEMS) + separator, True,
                                     (184, 164, 120))
    full_surf = _anim.ticker_surf
    period = full_surf.get_width()

    # Ticker strip above the footer, full width.
    ticker_y = HEIGHT - 56
    ticker_h = 20
    strip = pygame.Surface((WIDTH, ticker_h), pygame.SRCALPHA)
    strip.fill((*kit.INK, 210))
    surface.blit(strip, (0, ticker_y))
    pygame.draw.line(surface, kit.EDGE, (0, ticker_y), (WIDTH, ticker_y))
    pygame.draw.line(surface, kit.EDGE, (0, ticker_y + ticker_h), (WIDTH, ticker_y + ticker_h))

    # KRAPNET WIRE tag on the left - static, amber block.
    label = kit.font(10, "bold").render(_T("menu.krapnet_wire"), True, kit.INK)
    tag = pygame.Rect(0, ticker_y + 1, label.get_width() + 28, ticker_h - 1)
    pygame.draw.rect(surface, kit.AMBER, tag)
    surface.blit(label, (tag.x + 14, ticker_y + 4))

    window = pygame.Rect(tag.right + 8, ticker_y, WIDTH - tag.right - 8, ticker_h)
    if period <= 0:
        return
    offset = int(_anim.ticker_offset) % period
    # Drawn twice so the loop has no visible gap when it wraps.
    prev_clip = surface.get_clip()
    surface.set_clip(window)
    surface.blit(full_surf, (window.x - offset, ticker_y + 3))
    surface.blit(full_surf, (window.x - offset + period, ticker_y + 3))
    surface.set_clip(prev_clip)


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
    elif event.key == pygame.K_TAB:
        # Same as clicking the operation file card.
        audio.play("menu_click", volume=0.5)
        save_system.select_slot((save_system.current_slot_index() + 1) % save_system.SLOT_COUNT)
    elif pygame.K_1 <= event.key <= pygame.K_9:
        # Number keys fire the row with that on-screen index.
        visible = _visible_button_indices()
        n = event.key - pygame.K_1
        if n < len(visible):
            _anim.keyboard_idx = visible[n]
            _anim.pending_trigger = visible[n]
            buttons[visible[n]].press()
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
