
"""The Outfitter - spend Acaribucks on the loadout you play the arena in.

One screen with three tabs, not a shop and a separate customization screen:
buying and wearing act on the same rows, and splitting them would mean two
layouts to keep in step and two trips for one decision.

Follows ui.match_screen's shape rather than ui.system's - a class holding its
own state, drawn onto a surface handed in by app.py - for one specific reason.
The settings screen is a module of functions plus module-level rects whose
state is rebound globals read through the ui facade. That works for settings
because nothing else writes them. This screen mutates a wallet, so instance
state means there is no shared global for another module to snapshot stale, and
the "never `from <owner> import <mutable>`" rule in AGENTS.md cannot be broken
here by accident.

The preview is not a drawing of a drawing. Every icon and the big preview call
the PRODUCTION sprite code - entities.player.Player.draw(), the weapon rigs and
the head-gear registry - so what the shop shows is literally what the arena
renders. A hand-drawn preview would be a second art path, and it would promise
hats the game then fails to wear.
"""
import math

import pygame

from core import appearance, artpack, profile_store
from core.config import (
    WIDTH, C_ORANGE, font_speaker, font_terminal, font_terminal_small,
    font_prompt,
)
from entities import weapon_rig
from entities.player import Player
from ui.widgets import note_hover
from engine.text import T as _T  # RPE6 Phase 4 text table

# ── Panel geometry ──
# Same plate size and position as the settings screen, so the two full-screen
# panels do not jump between each other.
PANEL_W, PANEL_H = 720, 660
PANEL_X = WIDTH // 2 - PANEL_W // 2
PANEL_Y = 30
TAB_BAR_Y = PANEL_Y + 76
CONTENT_Y = TAB_BAR_Y + 50

# A 4 x 2 grid holds the largest tab (8 palettes) with no scrolling, which is
# why there is no scroll state in this file at all. The weapons tab would be
# 18 rows; it is cut to 6 by picking one gun at a time, which is also the way
# anybody actually browses finishes.
#
# CELL_H is icon + up to two label lines + status + the gaps, measured rather
# than guessed. Names get two lines because the alternative was either renaming
# items the designer chose or shipping a shop where "Ballistic Goggles" reads as
# "Ballisti...". At 96px of one line, four names lost their second word.
COLS, ROWS = 4, 2
CELL_W, CELL_H = 104, 164
# The cell border eats 8px, and the label keeps 8px of its own margin. One
# constant for the label budget so the renderer and the smoke check cannot
# measure against different widths and both think they passed.
LABEL_MAX_W = (CELL_W - 8) - 8
ICON_BOX = 96
ICON_TOP = 4
LABEL_TOP = ICON_TOP + ICON_BOX + 6      # 104
LABEL_LINE_H = 15
STATUS_TOP = LABEL_TOP + 2 * LABEL_LINE_H + 2   # 136
GRID_X = PANEL_X + 28
GRID_Y = CONTENT_Y + 40
GRID_W = COLS * CELL_W

GUN_CHIP_W = GRID_W // 3

RIGHT_X = PANEL_X + GRID_W + 44
RIGHT_W = PANEL_X + PANEL_W - 28 - RIGHT_X
# Sized so the preview column ends level with the bottom of the two-row grid,
# which stops the panel reading as a tall empty band on the right.
PREVIEW_H = 292
ACTION = pygame.Rect(RIGHT_X, GRID_Y + PREVIEW_H + 14, RIGHT_W, 36)
COST_Y = ACTION.bottom + 12

DESC_Y = GRID_Y + ROWS * CELL_H + 16
BACK = pygame.Rect(PANEL_X + 28, PANEL_Y + PANEL_H - 56, 150, 30)

# Catalog gun key -> the rig name Player.rig_weapon expects.
RIG_BY_GUN = {"os12": "os12", "k9": "k9_smg", "pistol": "pistol"}

# Icon poses. The rifle is drawn along the facing and the head sits two pixels
# further along that same line, so a head-on crop of the head has a barrel
# running through it. Yawing the gear poses clears the thing being sold without
# touching what is rendered.
BODY_ANGLE = -math.pi / 2
HEAD_ANGLE = -math.pi / 2 + 0.6

TABS = ("PALETTES", "GEAR", "WEAPONS")

# Colours, in the terminal green the settings panel uses.
C_ON = (80, 220, 120)
C_HEAD = (140, 240, 160)
C_BODY = (110, 160, 120)
C_OFF = (80, 110, 90)
C_DARK = (6, 12, 8)
C_MID = (10, 20, 14)
C_SEL = (14, 40, 22)
C_LINE = (25, 50, 32)
C_UNAFFORD = (90, 100, 96)
C_PLATE = (10, 16, 22)


def _money(n):
    return "{:,}".format(int(n))


def _fit(font, text, max_w):
    """Ellipsize *text* until it fits max_w pixels.

    Measured rather than counted. The cell is 96px wide and this face is
    monospace at roughly 8.4px a character, so a fixed character budget both
    wastes room on "Issue" and lets "Ballistic Goggles" run straight through the
    cell border - which is exactly the bug a 13-character limit produced.
    """
    text = str(text)
    if font.size(text)[0] <= max_w:
        return text
    while text and font.size(text + "...")[0] > max_w:
        text = text[:-1]
    return (text.rstrip() + "...") if text else ""


class ShopScreen(object):
    """The Outfitter panel. Instance state only; see the module docstring."""

    def __init__(self):
        self.mode = "closed"          # "closed" | "open"
        self.tab = 0
        self.gun = "os12"
        self.selected = None          # catalog id the buttons act on
        self.toast = ""
        self.toast_left = 0.0
        self.return_to = "MENU"
        self._rects = []              # (rect, item_id), rebuilt every draw
        self._tab_rects = []
        self._gun_rects = []

    # ── lifecycle ──────────────────────────────────────────────────────

    def open_panel(self, return_to="MENU"):
        self.mode = "open"
        self.return_to = return_to
        self.toast = ""
        self.toast_left = 0.0
        # Land on the first thing this player does not own, so the panel opens
        # showing a choice rather than a wall of EQUIPPED.
        self.selected = self._first_unowned()

    def close(self):
        self.mode = "closed"

    def update(self, dt):
        if self.toast_left > 0:
            self.toast_left = max(0.0, self.toast_left - max(0.0, float(dt)))
            if not self.toast_left:
                self.toast = ""

    def _rows(self):
        """Catalog rows for the active tab as [(item_id, entry, is_default)]."""
        if self.tab == 0:
            return appearance.catalog_rows("palette")
        if self.tab == 1:
            return appearance.catalog_rows("head")
        return appearance.catalog_rows(self.gun)

    def _first_unowned(self):
        owned = set(profile_store.load()["owned"])
        for item_id, _entry, _default in self._rows():
            if item_id not in owned:
                return item_id
        return None

    # ── input ───────────────────────────────────────────────────────────

    def handle_event(self, event, mouse):
        """Returns "back" when the player asks to leave, else None."""
        if self.mode != "open":
            return None
        if event.type == pygame.KEYDOWN:
            if event.key in (pygame.K_ESCAPE, pygame.K_BACKSPACE):
                return "back"
            if event.key in (pygame.K_LEFT, pygame.K_RIGHT):
                step = -1 if event.key == pygame.K_LEFT else 1
                self.tab = (self.tab + step) % len(TABS)
                self.selected = self._first_unowned()
                return None
            if event.key == pygame.K_RETURN:
                self._act()
                return None
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            # Cells first: a click on a row selects it, and selecting is by far
            # the most common intent on a shop screen.
            for rect, item_id in self._rects:
                if rect.collidepoint(mouse):
                    self.selected = item_id
                    return None
            for i, rect in enumerate(self._tab_rects):
                if rect.collidepoint(mouse):
                    self.tab = i
                    self.selected = self._first_unowned()
                    return None
            for gun, rect in self._gun_rects:
                if rect.collidepoint(mouse):
                    self.gun = gun
                    self.selected = self._first_unowned()
                    return None
            if ACTION.collidepoint(mouse):
                self._act()
                return None
            if BACK.collidepoint(mouse):
                return "back"
        return None

    def _act(self):
        """Buy the selected item if it is affordable, then wear it."""
        item_id = self.selected
        if not item_id:
            self._say("NOTHING SELECTED")
            return
        profile = profile_store.load()
        if item_id in profile["owned"]:
            profile_store.equip(item_id)
            self._say("WEARING %s" % appearance.item_label(item_id).upper())
            return
        ok, reason = profile_store.buy(item_id)
        if not ok:
            if reason == "poor":
                need = int(appearance.price_of(item_id) or 0) \
                    - profile["acaribucks"]
                self._say("NEED %s MORE ACARIBUCKS" % _money(need))
            elif reason == "unknown":
                # Only reachable if the catalog shrank under a saved profile,
                # which is the one drift this screen has to survive gracefully.
                self._say("NOT IN THE CATALOG")
                self.selected = self._first_unowned()
            else:
                self._say("ALREADY OWNED")
            return
        profile_store.equip(item_id)
        self._say("BOUGHT %s" % appearance.item_label(item_id).upper())

    def _say(self, text):
        self.toast = text
        self.toast_left = 2.6

    # ── art ─────────────────────────────────────────────────────────────

    def _loadout_with(self, item_id):
        """The equipped loadout, with *item_id* tried on in its own slot."""
        app = profile_store.equipped()
        if item_id in appearance.PALETTES:
            app["palette"] = item_id
        elif item_id in appearance.HEADGEARS:
            app["head"] = item_id
        elif item_id in appearance.FINISHES:
            app["finish"] = dict(app["finish"])
            app["finish"][appearance.FINISHES[item_id]["gun"]] = item_id
        return appearance.normalize(app)

    def _avatar(self, app, rig, box, scale=1, focus=0, angle=BODY_ANGLE):
        """Render a whole character through the production sprite code.

        Cached in core.artpack.pose, which is what that cache exists for: a
        parameterised procedural body drawn once and blitted thereafter. The
        LIVE avatar must never go through it, because Player.draw() advances
        breathing, the walk cycle and the blink timer as a side effect of
        rendering -- caching a live sprite would freeze it mid-breath and pin it
        to one spot. Static shop art has none of that problem.

        Facing north by default, because that is the only angle where a peak, a
        brow band and a night-vision mount are all visible at once.

        ``focus`` crops a native-resolution square of that half-width around
        the head and scales it back up, for the gear cells. The head is an
        18-pixel circle on a sprite whose rifle reaches 46 pixels out, so at
        icon size a beret and a helmet differ by a couple of pixels. This is a
        crop of the real render rather than a second drawing of a hat, which is
        what keeps the zoom honest: the pixels shown are the pixels you wear.

        The yaw in HEAD_ANGLE exists because the rifle is drawn along the
        facing and the head sits two pixels further along it, so at a dead
        north the barrel runs straight through the thing being sold. Turning
        the pose a little clears the head without changing what is rendered.
        """
        def paint(surf):
            native = pygame.Surface((box, box), pygame.SRCALPHA)
            p = Player(0, 0)
            p.rig_weapon = rig
            p.angle = angle
            p.blink_timer = 40
            p.set_appearance(app)
            # Player(0, 0) puts the body centre at (16, 16); offset by that
            # minus half the box to land the sprite in the middle.
            p.draw(native, offset_x=16 - box // 2, offset_y=16 - box // 2)
            out = native
            if focus:
                cx = cy = box // 2
                half = min(cx, cy, int(focus))
                out = native.subsurface(pygame.Rect(cx - half, cy - half,
                                                    half * 2, half * 2))
            total = int(box * scale)
            surf.blit(pygame.transform.scale(out, (total, total)), (0, 0))
        return artpack.pose(("outfitter_avatar", appearance.key_of(app), rig,
                             box, scale, int(focus), round(angle, 3)),
                            (box * scale, box * scale), paint)

    def _rig_icon(self, item_id, gun, box, scale=2):
        """One weapon, drawn by the same function the match calls.

        A finish swatch has to be the real rig or it is a decoration: the
        geometry - where the handguard ends, how far the suppressor reaches -
        is most of what identifies a gun, and a re-drawn silhouette would sell
        a colour scheme attached to the wrong shape.

        Rendered at 1/scale and blown back up because a pistol is about twenty
        pixels long at the size the match draws it, which in a 96-pixel cell is
        a smudge. Scaling is the same trick the gear crops use: bigger, but
        still the pixels the game produces.
        """
        roles = appearance.resolve(self._loadout_with(item_id))["rigs"]
        inner = max(24, int(box) // int(scale))

        def paint(surf):
            ctx = {"grip_x": inner * 0.30, "grip_y": inner * 0.5,
                   "arm_dx": 1.0, "arm_dy": 0.0, "raise_factor": 0.0,
                   "reload_active": False, "reload_progress": 0.0}
            small = pygame.Surface((inner, inner), pygame.SRCALPHA)
            weapon_rig.draw(small, RIG_BY_GUN[gun], ctx, roles)
            surf.blit(pygame.transform.scale(small, (box, box)), (0, 0))
        return artpack.pose(("outfitter_rig", item_id, box, scale),
                            (box, box), paint)

    # ── draw ────────────────────────────────────────────────────────────

    def draw(self, surface):
        if self.mode != "open":
            return
        mouse = pygame.mouse.get_pos()
        dim = pygame.Surface(surface.get_size(), pygame.SRCALPHA)
        dim.fill((0, 0, 0, 168))
        surface.blit(dim, (0, 0))
        panel = pygame.Rect(PANEL_X, PANEL_Y, PANEL_W, PANEL_H)
        pygame.draw.rect(surface, C_PLATE, panel)
        pygame.draw.rect(surface, (30, 90, 50), panel, 2)

        self._rects = []
        self._draw_header(surface)
        self._draw_tabs(surface, mouse)
        self._draw_grid(surface, mouse)
        self._draw_detail(surface, mouse)
        self._draw_footer(surface, mouse)

    def _draw_header(self, surface):
        """Title with the two-layer phosphor glow, and the wallet."""
        title = "// OUTFITTER //"
        glow = font_speaker.render(title, True, (30, 90, 50))
        top = font_speaker.render(title, True, C_HEAD)
        surface.blit(glow, (PANEL_X + 29, PANEL_Y + 24))
        surface.blit(top, (PANEL_X + 28, PANEL_Y + 23))

        amount = font_terminal.render(_money(profile_store.balance()), True,
                                      C_ORANGE)
        label = font_terminal_small.render(_T("shop.acaribucks"), True, C_OFF)
        right = PANEL_X + PANEL_W - 28
        surface.blit(amount, (right - amount.get_width(), PANEL_Y + 22))
        surface.blit(label, (right - label.get_width(), PANEL_Y + 48))
        pygame.draw.line(surface, (50, 140, 80), (PANEL_X + 24, PANEL_Y + 66),
                         (PANEL_X + PANEL_W - 24, PANEL_Y + 66), 1)

    def _draw_tabs(self, surface, mouse):
        self._tab_rects = []
        w = PANEL_W // len(TABS)
        for i, name in enumerate(TABS):
            rect = pygame.Rect(PANEL_X + i * w, TAB_BAR_Y, w, 34)
            self._tab_rects.append(rect)
            active = (i == self.tab)
            hot = rect.collidepoint(mouse)
            if hot:
                note_hover()
            pygame.draw.rect(surface, C_SEL if active else (
                C_MID if hot else C_DARK), rect)
            if active:
                pygame.draw.rect(surface, C_ON,
                                 (rect.x, rect.bottom - 3, rect.width, 3))
            else:
                pygame.draw.line(surface, C_LINE, (rect.x, rect.bottom),
                                 (rect.right, rect.bottom), 1)
            text = font_terminal_small.render(
                name, True,
                C_HEAD if active else (C_BODY if hot else C_OFF))
            surface.blit(text, (rect.centerx - text.get_width() // 2,
                                rect.centery - text.get_height() // 2))

    def _draw_grid(self, surface, mouse):
        self._gun_rects = []
        if self.tab == 2:
            for i, gun in enumerate(appearance.GUN_KEYS):
                rect = pygame.Rect(GRID_X + i * GUN_CHIP_W, CONTENT_Y,
                                   GUN_CHIP_W - 6, 26)
                self._gun_rects.append((gun, rect))
                active = (gun == self.gun)
                hot = rect.collidepoint(mouse)
                if hot:
                    note_hover()
                pygame.draw.rect(surface, C_SEL if active else (
                    C_MID if hot else C_DARK), rect)
                if active:
                    pygame.draw.rect(surface, C_ON, rect, 1)
                text = font_terminal_small.render(
                    _gun_label(gun), True, C_HEAD if active else C_OFF)
                surface.blit(text, (rect.centerx - text.get_width() // 2,
                                    rect.centery - text.get_height() // 2))

        profile = profile_store.load()
        owned = set(profile["owned"])
        wearing = profile["equipped"]
        balance = profile["acaribucks"]
        for index, (item_id, entry, _default) in enumerate(self._rows()):
            col, row = index % COLS, index // COLS
            rect = pygame.Rect(GRID_X + col * CELL_W, GRID_Y + row * CELL_H,
                               CELL_W - 8, CELL_H - 8)
            self._rects.append((rect, item_id))
            hot = rect.collidepoint(mouse)
            picked = (item_id == self.selected)
            if hot:
                note_hover()
            if picked:
                pygame.draw.rect(surface, C_SEL, rect)
                pygame.draw.rect(surface, C_ON, rect, 1)
            else:
                pygame.draw.rect(surface, C_MID if hot else C_DARK, rect)

            if item_id in appearance.FINISHES:
                art = self._rig_icon(item_id,
                                     appearance.FINISHES[item_id]["gun"],
                                     ICON_BOX)
            else:
                # Gear is a zoom on the head; a palette is the whole body,
                # because that is the difference between what is being sold.
                gear = item_id in appearance.HEADGEARS
                art = self._avatar(self._loadout_with(item_id), "os12",
                                   ICON_BOX,
                                   focus=24 if gear else 0,
                                   angle=HEAD_ANGLE if gear else BODY_ANGLE)
            surface.blit(art, (rect.centerx - art.get_width() // 2,
                               rect.top + ICON_TOP))

            label_color = C_HEAD if picked else (C_BODY if hot else C_OFF)
            for li, line in enumerate(_name_lines(font_terminal_small,
                                                  entry["name"],
                                                  LABEL_MAX_W)):
                text = font_terminal_small.render(line, True, label_color)
                surface.blit(text, (rect.centerx - text.get_width() // 2,
                                    rect.top + LABEL_TOP
                                    + li * LABEL_LINE_H))
            self._status_line(surface, rect, item_id, entry, owned, wearing,
                              balance)

    def _status_line(self, surface, rect, item_id, entry, owned, wearing,
                     balance):
        """Price, OWNED, or EQUIPPED - the one line that decides a click."""
        if _is_worn(item_id, wearing):
            text, color = "EQUIPPED", C_ON
        elif item_id in owned:
            text, color = "OWNED", C_BODY
        elif entry["price"] > balance:
            text, color = "%s ACB" % _money(entry["price"]), C_UNAFFORD
        else:
            text, color = "%s ACB" % _money(entry["price"]), C_ORANGE
        surf = font_terminal_small.render(text, True, color)
        surface.blit(surf, (rect.centerx - surf.get_width() // 2,
                            rect.top + STATUS_TOP))

    def _draw_detail(self, surface, mouse):
        """Live preview, price, description and the one action button."""
        box = pygame.Rect(RIGHT_X, GRID_Y, RIGHT_W, PREVIEW_H)
        pygame.draw.rect(surface, C_DARK, box)
        pygame.draw.rect(surface, C_LINE, box, 1)

        item_id = self.selected
        if not item_id:
            surface.blit(font_prompt.render(_T("shop.select_an_item"), True, C_OFF),
                         (box.centerx - 66, box.centery - 8))
            return

        app = self._loadout_with(item_id)
        rig = (RIG_BY_GUN[appearance.FINISHES[item_id]["gun"]]
               if item_id in appearance.FINISHES else "os12")
        art = self._avatar(app, rig, 116, scale=2)
        surface.blit(art, (box.centerx - art.get_width() // 2,
                           box.centery - art.get_height() // 2))

        price = int(appearance.price_of(item_id) or 0)
        owned = item_id in profile_store.load()["owned"]
        if price == 0:
            cost, cost_color = "ISSUE - FREE", C_BODY
        elif owned:
            cost, cost_color = "OWNED", C_ON
        elif price > profile_store.balance():
            cost, cost_color = ("%s ACB - SHORT" % _money(price)), C_UNAFFORD
        else:
            cost, cost_color = "%s ACARIBUCKS" % _money(price), C_ORANGE
        text = font_terminal_small.render(cost, True, cost_color)
        surface.blit(text, (RIGHT_X + (RIGHT_W - text.get_width()) // 2,
                            COST_Y))

        surface.blit(font_terminal.render(
            _fit(font_terminal, appearance.item_label(item_id).upper(),
                 GRID_W - 12), True, C_HEAD),
            (GRID_X, DESC_Y))
        _wrap(surface, appearance.item_desc(item_id), GRID_X, DESC_Y + 26,
              GRID_W - 12, font_terminal_small, C_BODY, 2)

        hot = ACTION.collidepoint(mouse)
        if hot:
            note_hover()
        pygame.draw.rect(surface, C_SEL if hot else C_DARK, ACTION)
        pygame.draw.rect(surface, C_ON, ACTION, 1)
        worn = _is_worn(item_id, profile_store.equipped())
        label = "WORN" if worn else ("BUY & WEAR" if not owned else "WEAR")
        text = font_prompt.render(label, True, C_HEAD if hot else C_BODY)
        surface.blit(text, (ACTION.centerx - text.get_width() // 2,
                            ACTION.centery - text.get_height() // 2))

    def _draw_footer(self, surface, mouse):
        hot = BACK.collidepoint(mouse)
        if hot:
            note_hover()
        pygame.draw.rect(surface, C_MID if hot else C_DARK, BACK)
        pygame.draw.rect(surface, C_LINE, BACK, 1)
        text = font_prompt.render(_T("shop.back"), True, C_HEAD if hot else C_BODY)
        surface.blit(text, (BACK.centerx - text.get_width() // 2,
                            BACK.centery - text.get_height() // 2))
        hint = font_terminal_small.render(
            _T("shop.left_right_tab_enter_confirm_esc"), True, C_OFF)
        surface.blit(hint, (BACK.right + 24, BACK.centery - 7))
        if self.toast:
            toast = font_terminal.render(self.toast, True, C_ORANGE)
            surface.blit(toast, (PANEL_X + PANEL_W - 28 - toast.get_width(),
                                 BACK.centery - 11))


# ── helpers ─────────────────────────────────────────────────────────────

def _is_worn(item_id, wearing):
    """Is this exact catalog id what the profile currently has equipped?"""
    if item_id == wearing["palette"] or item_id == wearing["head"]:
        return True
    return item_id in wearing["finish"].values()


def _gun_label(gun):
    return {"os12": "OS-12", "k9": "K-9", "pistol": "PISTOL"}.get(gun, gun)


def _name_lines(font, name, max_w):
    """Split an item name across at most two lines, breaking between words.

    Returns a single line whenever the name already fits, so "Issue" and
    "Beret" stay on one row and the grid does not read as having a gap in it.
    Only the names that genuinely need the second row get one.
    """
    words = str(name).split()
    if not words:
        return [""]
    joined = " ".join(words)
    if font.size(joined)[0] <= max_w:
        return [joined]
    # Grow line one word by word until adding the next would overflow.
    count = 1
    while (count < len(words)
           and font.size(" ".join(words[:count + 1]))[0] <= max_w):
        count += 1
    line1 = _fit(font, " ".join(words[:count]), max_w)
    rest = " ".join(words[count:])
    return [line1] if not rest else [line1, _fit(font, rest, max_w)]


def _wrap(surface, text, x, y, width, font, color, max_lines=2):
    """Greedy word wrap, capped at max_lines with a visible cut."""
    words = str(text).split()
    lines = []
    current = ""
    for word in words:
        trial = (current + " " + word).strip()
        if not current or font.size(trial)[0] <= width:
            current = trial
            continue
        lines.append(current)
        current = word
        if len(lines) == max_lines:
            break
    if current and len(lines) < max_lines:
        lines.append(current)
    if len(lines) == max_lines and " ".join(lines).split() != words:
        # Something was dropped, so mark the cut. Measured, because the last
        # line is already exactly as wide as the column allows.
        lines[-1] = _fit(font, lines[-1], width)
    for i, line in enumerate(lines[:max_lines]):
        surface.blit(font.render(line, True, color), (x, y + i * 16))
