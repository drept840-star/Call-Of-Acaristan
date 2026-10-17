
"""Split from menu.py - see menu.py (shim) for the map."""
import math
import pygame
import random
from core.config import (C_GREY, C_ORANGE, C_TERMINAL, C_WHITE, HEIGHT, WIDTH, font_btn, font_prompt, font_speaker, font_terminal, font_terminal_small, font_title, get_scaled_mouse, screen)
from engine.core import LEGACY_RNG as _rng_legacy  # RPE6 R6: named 'legacy' rng stream

from core.state import STATE

from core import mission_meta as _mission_meta

from ui.widgets import ModernButton
from engine.core import now_ms as _now_ms  # RPE6 B-001 timebase
from engine.text import T as _T  # RPE6 Phase 4 text table


# ─────────────────────────────────────────────

# SETTINGS - CRT TERMINAL style, 6 tabs, live-apply + Apply button

# Tabs: DISPLAY · AUDIO · GAMEPLAY · GRAPHICS · CONTROLS · ACCESSIBILITY

# ─────────────────────────────────────────────

SETTINGS_RESOLUTIONS = ["1920x1080", "1600x900", "1280x720"]

DISPLAY_MODES = ["WINDOWED", "FULLSCREEN"]

SETTINGS_TABS = ["VIDEO", "AUDIO", "GAMEPLAY", "IMAGE", "CONTROLS", "ACCESS"]

CROSSHAIR_SIZES = [3, 6, 10]

CROSSHAIR_SIZE_LABELS = ["SMALL", "MEDIUM", "LARGE"]

COLORBLIND_MODES = ["OFF", "PROTANOPIA", "DEUTERANOPIA", "TRITANOPIA"]



# ── Panel geometry - wider + taller to fit the expanded content ──

# Height bumped from 600 → 660 so the busiest tab (GAMEPLAY: 5 rows + 2

# section headers) fits without its last hint colliding with the Back/Apply

# buttons at the bottom.

SETTINGS_PANEL_W = 860

SETTINGS_PANEL_H = 660

SETTINGS_PANEL_X = WIDTH // 2 - SETTINGS_PANEL_W // 2

SETTINGS_PANEL_Y = (HEIGHT - SETTINGS_PANEL_H) // 2



# Tab bar - single row of 6 tabs

TAB_BAR_Y = SETTINGS_PANEL_Y + 76

TAB_W = SETTINGS_PANEL_W // len(SETTINGS_TABS)

settings_tab_rects = [

    pygame.Rect(SETTINGS_PANEL_X + i * TAB_W, TAB_BAR_Y, TAB_W, 34)

    for i in range(len(SETTINGS_TABS))

]



# Content area

CONTENT_Y = TAB_BAR_Y + 50

LABEL_X = SETTINGS_PANEL_X + 48

# CONTROL_X moved right so long labels ("Mute on Focus Loss", "Particle

# Density", "Colorblind Mode") don't run into the controls.

CONTROL_X = SETTINGS_PANEL_X + 460

# Each row needs room for: label/control (22px) + hint text (16px) + gap.

# 64px gives ~26px clear between the control and the next row's label.

ROW_H = 64

# Section headers sit ABOVE their first row - reserve 30px for the header

# text + divider line + breathing room so it doesn't overlap the row beneath.

SECTION_H = 30



# ── DISPLAY tab rows ── (section header "MONITOR" at top, then rows)

ROW_RES_Y = CONTENT_Y + SECTION_H

ROW_DISPLAY_Y = ROW_RES_Y + ROW_H

settings_res_left_rect     = pygame.Rect(CONTROL_X, ROW_RES_Y - 4, 28, 28)

settings_res_right_rect    = pygame.Rect(CONTROL_X + 250, ROW_RES_Y - 4, 28, 28)

settings_display_left_rect = pygame.Rect(CONTROL_X, ROW_DISPLAY_Y - 4, 28, 28)

settings_display_right_rect= pygame.Rect(CONTROL_X + 250, ROW_DISPLAY_Y - 4, 28, 28)



# ── AUDIO tab rows ── (header "LEVELS" at CONTENT_Y, rows start below)

VOL_BAR_W = 150

VOL_BAR_X = CONTROL_X + 38

ROW_MASTER_Y = CONTENT_Y + SECTION_H

ROW_MUSIC_Y  = ROW_MASTER_Y + ROW_H

ROW_SFX_Y    = ROW_MUSIC_Y + ROW_H

ROW_MUTE_Y   = ROW_SFX_Y + ROW_H

settings_master_left_rect  = pygame.Rect(CONTROL_X, ROW_MASTER_Y - 4, 28, 28)

settings_master_right_rect = pygame.Rect(VOL_BAR_X + VOL_BAR_W + 8, ROW_MASTER_Y - 4, 28, 28)

settings_master_bar_rect   = pygame.Rect(VOL_BAR_X, ROW_MASTER_Y + 3, VOL_BAR_W, 14)

settings_music_left_rect   = pygame.Rect(CONTROL_X, ROW_MUSIC_Y - 4, 28, 28)

settings_music_right_rect  = pygame.Rect(VOL_BAR_X + VOL_BAR_W + 8, ROW_MUSIC_Y - 4, 28, 28)

settings_music_bar_rect    = pygame.Rect(VOL_BAR_X, ROW_MUSIC_Y + 3, VOL_BAR_W, 14)

settings_sfx_left_rect     = pygame.Rect(CONTROL_X, ROW_SFX_Y - 4, 28, 28)

settings_sfx_right_rect    = pygame.Rect(VOL_BAR_X + VOL_BAR_W + 8, ROW_SFX_Y - 4, 28, 28)

settings_sfx_bar_rect      = pygame.Rect(VOL_BAR_X, ROW_SFX_Y + 3, VOL_BAR_W, 14)

settings_mute_rect         = pygame.Rect(CONTROL_X, ROW_MUTE_Y - 3, 56, 26)



# ── GAMEPLAY tab rows ── (header "COMBAT" at top, "PRESENTATION" before subtitles)

ROW_CROSSHAIR_Y      = CONTENT_Y + SECTION_H

ROW_CROSSHAIR_SIZE_Y = ROW_CROSSHAIR_Y + ROW_H

ROW_AUTO_RELOAD_Y    = ROW_CROSSHAIR_SIZE_Y + ROW_H

ROW_AIM_ASSIST_Y     = ROW_AUTO_RELOAD_Y + ROW_H

# "PRESENTATION" header before subtitles - push subtitles down by SECTION_H

ROW_SUBTITLES_Y      = ROW_AIM_ASSIST_Y + ROW_H + SECTION_H

settings_crosshair_rect      = pygame.Rect(CONTROL_X, ROW_CROSSHAIR_Y - 3, 56, 26)

settings_crosshair_size_left = pygame.Rect(CONTROL_X, ROW_CROSSHAIR_SIZE_Y - 4, 28, 28)

settings_crosshair_size_right= pygame.Rect(CONTROL_X + 250, ROW_CROSSHAIR_SIZE_Y - 4, 28, 28)

settings_auto_reload_rect    = pygame.Rect(CONTROL_X, ROW_AUTO_RELOAD_Y - 3, 56, 26)

settings_aim_assist_rect     = pygame.Rect(CONTROL_X, ROW_AIM_ASSIST_Y - 3, 56, 26)

settings_subtitles_rect      = pygame.Rect(CONTROL_X, ROW_SUBTITLES_Y - 3, 56, 26)

# RPE6 P9: dialogue typewriter rate (row under Subtitles)
ROW_TEXT_SPEED_Y             = ROW_SUBTITLES_Y + ROW_H
settings_text_speed_left     = pygame.Rect(CONTROL_X, ROW_TEXT_SPEED_Y - 4, 28, 28)
settings_text_speed_right    = pygame.Rect(CONTROL_X + 250, ROW_TEXT_SPEED_Y - 4, 28, 28)
TEXT_SPEED_LABELS            = ("SLOW", "NORMAL", "FAST")



# ── GRAPHICS tab rows ── (header "IMAGE" at top, "POST-PROCESSING" before scanlines)

ROW_BRIGHTNESS_Y    = CONTENT_Y + SECTION_H

# "POST-PROCESSING" header before scanlines - push down by SECTION_H

ROW_SCANLINES_Y     = ROW_BRIGHTNESS_Y + ROW_H + SECTION_H

ROW_GRAIN_Y         = ROW_SCANLINES_Y + ROW_H

ROW_PARTICLES_Y     = ROW_GRAIN_Y + ROW_H

settings_brightness_left  = pygame.Rect(CONTROL_X, ROW_BRIGHTNESS_Y - 4, 28, 28)

settings_brightness_right = pygame.Rect(VOL_BAR_X + VOL_BAR_W + 8, ROW_BRIGHTNESS_Y - 4, 28, 28)

settings_brightness_bar   = pygame.Rect(VOL_BAR_X, ROW_BRIGHTNESS_Y + 3, VOL_BAR_W, 14)

settings_scanlines_rect   = pygame.Rect(CONTROL_X, ROW_SCANLINES_Y - 3, 56, 26)

settings_grain_rect       = pygame.Rect(CONTROL_X, ROW_GRAIN_Y - 3, 56, 26)

settings_particles_left   = pygame.Rect(CONTROL_X, ROW_PARTICLES_Y - 4, 28, 28)

settings_particles_right  = pygame.Rect(VOL_BAR_X + VOL_BAR_W + 8, ROW_PARTICLES_Y - 4, 28, 28)

settings_particles_bar    = pygame.Rect(VOL_BAR_X, ROW_PARTICLES_Y + 3, VOL_BAR_W, 14)



# ── CONTROLS tab rows ── (header "MOUSE" at top, "KEYBINDS" after invert)

ROW_MOUSE_SENS_Y = CONTENT_Y + SECTION_H

ROW_INVERT_Y     = ROW_MOUSE_SENS_Y + ROW_H

settings_mouse_sens_left  = pygame.Rect(CONTROL_X, ROW_MOUSE_SENS_Y - 4, 28, 28)

settings_mouse_sens_right = pygame.Rect(VOL_BAR_X + VOL_BAR_W + 8, ROW_MOUSE_SENS_Y - 4, 28, 28)

settings_mouse_sens_bar   = pygame.Rect(VOL_BAR_X, ROW_MOUSE_SENS_Y + 3, VOL_BAR_W, 14)

settings_invert_rect      = pygame.Rect(CONTROL_X, ROW_INVERT_Y - 3, 56, 26)



# ── ACCESSIBILITY tab rows ── (header "MOTION" at top, "VISION" before colorblind)

ROW_REDUCED_MOTION_Y = CONTENT_Y + SECTION_H

# "VISION" header before colorblind - push down by SECTION_H

ROW_COLORBLIND_Y     = ROW_REDUCED_MOTION_Y + ROW_H + SECTION_H

settings_reduced_motion_rect  = pygame.Rect(CONTROL_X, ROW_REDUCED_MOTION_Y - 3, 56, 26)

settings_colorblind_left      = pygame.Rect(CONTROL_X, ROW_COLORBLIND_Y - 4, 28, 28)

settings_colorblind_right     = pygame.Rect(CONTROL_X + 250, ROW_COLORBLIND_Y - 4, 28, 28)
# Radio widget prefs (polish pass T6): own "RADIO" section under VISION.
ROW_RADIO_SIZE_Y     = ROW_COLORBLIND_Y + ROW_H + SECTION_H
ROW_RADIO_NAMES_Y    = ROW_RADIO_SIZE_Y + ROW_H
settings_radio_size_left     = pygame.Rect(CONTROL_X, ROW_RADIO_SIZE_Y - 4, 28, 28)
settings_radio_size_right    = pygame.Rect(CONTROL_X + 250, ROW_RADIO_SIZE_Y - 4, 28, 28)
settings_radio_names_rect    = pygame.Rect(CONTROL_X, ROW_RADIO_NAMES_Y - 3, 56, 26)

# RPE6 P9 COMFORT rows (compact pitch - the footer divider sits at panel H-100)
ROW_COMFORT_Y        = ROW_RADIO_NAMES_Y + 58
ROW_FLASH_Y          = ROW_COMFORT_Y + 30
ROW_SHAKE_Y           = ROW_FLASH_Y + 36
settings_flash_rect        = pygame.Rect(CONTROL_X, ROW_FLASH_Y - 3, 56, 26)
# RPE6 P9: CONTROLS-tab binding badges (filled per frame by draw_settings)
settings_binding_rects: dict = {}
settings_binding_reset_rect = pygame.Rect(0, 0, 150, 31)
settings_shake_left        = pygame.Rect(CONTROL_X, ROW_SHAKE_Y - 4, 28, 28)
settings_shake_right       = pygame.Rect(CONTROL_X + 250, ROW_SHAKE_Y - 4, 28, 28)



# ── Pre-rendered surfaces ──

# Volume/brightness bar gradient (orange → yellow)

_VOL_GRADIENT = pygame.Surface((VOL_BAR_W, 14))
for vx in range(VOL_BAR_W):
    t = vx / max(1, VOL_BAR_W - 1)
    pygame.draw.line(_VOL_GRADIENT, (int(170 + t * 61), int(139 + t * 42), 75),
                     (vx, 0), (vx, 13))

# CRT scanline overlay for the settings panel - thin horizontal lines every 3px

_CRT_SCANLINES = pygame.Surface((SETTINGS_PANEL_W, SETTINGS_PANEL_H), pygame.SRCALPHA)

for y in range(0, SETTINGS_PANEL_H, 3):

    pygame.draw.line(_CRT_SCANLINES, (0, 0, 0, 28), (0, y), (SETTINGS_PANEL_W, y), 1)



# Settings panel background - dark CRT phosphor with a green-tinted border

_settings_overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)

_settings_overlay.fill((0, 0, 0, 190))

_settings_panel = pygame.Surface((SETTINGS_PANEL_W, SETTINGS_PANEL_H), pygame.SRCALPHA)

_settings_panel.fill((16, 21, 17, 250))

# Double border: outer green phosphor, inner darker

pygame.draw.rect(_settings_panel, (115, 129, 91), (0, 0, SETTINGS_PANEL_W, SETTINGS_PANEL_H), 2)

pygame.draw.rect(_settings_panel, (49, 61, 43), (3, 3, SETTINGS_PANEL_W - 6, SETTINGS_PANEL_H - 6), 1)



# ── Buttons ──

settings_back_btn = ModernButton(

    SETTINGS_PANEL_X + SETTINGS_PANEL_W // 2 - 230,

    SETTINGS_PANEL_Y + SETTINGS_PANEL_H - 52,

    "BACK",

)

settings_apply_btn = ModernButton(

    SETTINGS_PANEL_X + SETTINGS_PANEL_W // 2 + 10,

    SETTINGS_PANEL_Y + SETTINGS_PANEL_H - 52,

    "APPLY",

)

for _button, _x in ((settings_back_btn, SETTINGS_PANEL_X + 48),
                    (settings_apply_btn, SETTINGS_PANEL_X + SETTINGS_PANEL_W - 258)):
    _button.x, _button.y = _x, SETTINGS_PANEL_Y + SETTINGS_PANEL_H - 48
    _button.width, _button.height = 210, 36
    _button.rect = pygame.Rect(_button.x, _button.y, 210, 36)

server_back_btn = ModernButton(0, 0, "BACK")





# ─────────────────────────────────────────────

# CRT terminal drawing helpers

# ─────────────────────────────────────────────

def _draw_arrow_btn(rect, sym):

    """Arrow button with CRT phosphor glow on hover."""

    hover = rect.collidepoint(get_scaled_mouse())

    bg = (55, 61, 40) if hover else (23, 29, 22)

    pygame.draw.rect(screen, bg, rect)

    border_col = (231, 181, 94) if hover else (79, 89, 69)

    pygame.draw.rect(screen, border_col, rect, 1)

    c = font_btn.render(sym, True, (231, 181, 94) if hover else (185, 192, 167))

    screen.blit(c, (rect.centerx - c.get_width() // 2, rect.centery - c.get_height() // 2))





def _draw_volume_slider(label, bar_rect, left_rect, right_rect, value, row_y):

    """Volume/brightness slider with CRT phosphor fill."""

    screen.blit(font_terminal_small.render(label, True, (215, 220, 199)), (LABEL_X, row_y + 3))

    _draw_arrow_btn(left_rect, "<")

    pygame.draw.rect(screen, (12, 17, 13), bar_rect)

    value = max(0, min(100, int(value)))
    fill_w = int(bar_rect.width * value / 100)

    if fill_w > 0:

        screen.blit(_VOL_GRADIENT, bar_rect.topleft, (0, 0, fill_w, bar_rect.height))

    pygame.draw.rect(screen, (79, 89, 69), bar_rect, 1)
    thumb_x = bar_rect.x + int((bar_rect.width - 4) * value / 100)
    pygame.draw.rect(screen, (237, 213, 158), (thumb_x, bar_rect.y - 3, 4, bar_rect.height + 6))

    _draw_arrow_btn(right_rect, ">")

    pct = font_terminal.render(_T("sys.value_3", value=value), True, (231, 181, 94))

    screen.blit(pct, (right_rect.right + 12, row_y))





def _draw_toggle(label, rect, value, row_y):

    """CRT toggle switch - green when ON, dim when OFF."""

    screen.blit(font_terminal_small.render(label, True, (215, 220, 199)), (LABEL_X, row_y + 3))

    hover = rect.collidepoint(get_scaled_mouse())

    on_col = (93, 110, 62) if value else (23, 29, 22)

    border_col = (231, 181, 94) if (hover or value) else (79, 89, 69)

    pygame.draw.rect(screen, on_col, rect)

    pygame.draw.rect(screen, border_col, rect, 1)

    # Knob

    knob_x = rect.right - 22 if value else rect.x + 4

    pygame.draw.rect(screen, (230, 220, 177) if value else (135, 145, 124),

                     (knob_x, rect.y + 4, 18, rect.height - 8))

    state_label = "ON" if value else "OFF"

    s = font_terminal_small.render(state_label, True, (231, 181, 94) if value else (175, 182, 160))

    screen.blit(s, (rect.right + 12, row_y + 3))





def _draw_stepper(label, left_rect, right_rect, value_str, row_y):

    """Stepper control: < VALUE >  for enumerated settings (resolution, mode, etc.)."""

    screen.blit(font_terminal_small.render(label, True, (215, 220, 199)), (LABEL_X, row_y + 3))

    _draw_arrow_btn(left_rect, "<")

    val_surf = font_terminal.render(value_str, True, (231, 181, 94))

    val_cx = (left_rect.right + right_rect.left) // 2

    screen.blit(val_surf, (val_cx - val_surf.get_width() // 2, row_y))

    _draw_arrow_btn(right_rect, ">")





def _draw_section_header(text, y):

    """Small green section divider with a label - groups related settings."""

    header = font_terminal_small.render(text, True, (231, 181, 94))

    screen.blit(header, (LABEL_X, y))

    line_y = y + header.get_height() + 2

    pygame.draw.line(screen, (67, 78, 60), (LABEL_X, line_y),

                     (SETTINGS_PANEL_X + SETTINGS_PANEL_W - 48, line_y), 1)





def _draw_hint(text, y):

    """Dim helper text under a setting."""

    hint = font_terminal_small.render(text, True, (157, 170, 143))

    screen.blit(hint, (LABEL_X, y))





def draw_settings(active_tab, display_mode, res_idx,

                  master_volume, music_volume, sfx_volume, mute_on_focus_loss,

                  crosshair, crosshair_size, auto_reload, aim_assist, subtitles,

                  brightness, scanlines, grain, particle_density,

                  mouse_sensitivity, invert_mouse,

                  reduced_motion, colorblind_mode,
                  shake_scale=100, flash_reduction=False, text_speed=1,
                  save_status="CONFIG SYNCED", save_failed=False,
                  bindings=None, binding_capture=None):

    """Render the local tactical configuration console without changing other menus."""
    global screen
    # Display switches rebind config.screen; do not retain a stale import snapshot.
    from core import config as _config
    screen = _config.screen

    screen.blit(_settings_overlay, (0, 0))

    screen.blit(_settings_panel, (SETTINGS_PANEL_X, SETTINGS_PANEL_Y))



    # Field-console hierarchy: equipment label, title, restrained serial mark.
    screen.blit(font_terminal_small.render(_T("sys.acaristan_field_equipment"), True, (157, 170, 143)),
                (SETTINGS_PANEL_X + 32, SETTINGS_PANEL_Y + 14))
    screen.blit(font_speaker.render(_T("sys.system_configuration"), True, (230, 220, 177)),
                (SETTINGS_PANEL_X + 32, SETTINGS_PANEL_Y + 36))
    serial = font_terminal_small.render(_T("sys.local_profile_01"), True, (231, 181, 94))
    screen.blit(serial, (SETTINGS_PANEL_X + SETTINGS_PANEL_W - serial.get_width() - 32,
                         SETTINGS_PANEL_Y + 20))
    pygame.draw.line(screen, (115, 129, 91),
                     (SETTINGS_PANEL_X + 32, SETTINGS_PANEL_Y + 66),
                     (SETTINGS_PANEL_X + SETTINGS_PANEL_W - 32, SETTINGS_PANEL_Y + 66))
    # Inner content plate and hardware corner marks.
    plate = pygame.Rect(SETTINGS_PANEL_X + 24, CONTENT_Y - 6,
                        SETTINGS_PANEL_W - 48, 426)
    pygame.draw.rect(screen, (12, 17, 13), plate)
    pygame.draw.rect(screen, (49, 61, 43), plate, 1)
    for x, y, dx, dy in [(SETTINGS_PANEL_X, SETTINGS_PANEL_Y, 1, 1),
                         (SETTINGS_PANEL_X + SETTINGS_PANEL_W - 1, SETTINGS_PANEL_Y, -1, 1),
                         (SETTINGS_PANEL_X, SETTINGS_PANEL_Y + SETTINGS_PANEL_H - 1, 1, -1),
                         (SETTINGS_PANEL_X + SETTINGS_PANEL_W - 1, SETTINGS_PANEL_Y + SETTINGS_PANEL_H - 1, -1, -1)]:
        pygame.draw.line(screen, (231, 181, 94), (x, y), (x + dx * 15, y), 2)
        pygame.draw.line(screen, (231, 181, 94), (x, y), (x, y + dy * 15), 2)

    # ── Tab bar ──

    mouse = get_scaled_mouse()

    for i, (rect, label) in enumerate(zip(settings_tab_rects, SETTINGS_TABS)):

        is_active = (i == active_tab)

        hover = rect.collidepoint(mouse)

        bg = (50, 55, 36) if is_active else ((30, 37, 26) if hover else (12, 17, 13))

        pygame.draw.rect(screen, bg, rect)

        if is_active:

            pygame.draw.rect(screen, (231, 181, 94), (rect.x, rect.bottom - 3, rect.width, 3))

        else:

            pygame.draw.line(screen, (67, 78, 60), (rect.x, rect.bottom), (rect.right, rect.bottom), 1)

        col = (231, 181, 94) if is_active else ((212, 215, 190) if hover else (162, 174, 144))

        ts = font_terminal_small.render(_T("sys.session_row", n="{:02}".format(i + 1), label=label), True, col)

        screen.blit(ts, (rect.centerx - ts.get_width() // 2, rect.centery - ts.get_height() // 2))



    # ── Tab content ──

    if active_tab == 0:

        # DISPLAY

        _draw_section_header("MONITOR", CONTENT_Y)

        screen.blit(font_terminal_small.render(_T("sys.logical_canvas"), True, (215, 220, 199)), (LABEL_X, ROW_RES_Y + 3))
        screen.blit(font_terminal.render(_T("sys.1000_x_700"), True, (185, 192, 167)), (CONTROL_X, ROW_RES_Y))
        _draw_hint("Fixed render canvas; the window scales without changing gameplay.", ROW_RES_Y + 30)
        _draw_stepper("Display Mode", settings_display_left_rect, settings_display_right_rect,
                      DISPLAY_MODES[max(0, min(display_mode, len(DISPLAY_MODES) - 1))], ROW_DISPLAY_Y)
        _draw_hint("Fullscreen uses your desktop. Windowed mode is freely resizable.", ROW_DISPLAY_Y + 36)
        _draw_section_header("DISPLAY PROCEDURE", ROW_DISPLAY_Y + 94)
        _draw_hint("F11 switches modes. Image effects are in 04 IMAGE.", ROW_DISPLAY_Y + 126)
        _draw_hint("Changes preview immediately; APPLY writes the local profile.", ROW_DISPLAY_Y + 150)



    elif active_tab == 1:

        # AUDIO

        _draw_section_header("LEVELS", CONTENT_Y)

        _draw_volume_slider("Master Volume", settings_master_bar_rect,

                            settings_master_left_rect, settings_master_right_rect,

                            master_volume, ROW_MASTER_Y)

        _draw_volume_slider("Music Volume", settings_music_bar_rect,

                            settings_music_left_rect, settings_music_right_rect,

                            music_volume, ROW_MUSIC_Y)

        _draw_volume_slider("SFX Volume", settings_sfx_bar_rect,

                            settings_sfx_left_rect, settings_sfx_right_rect,

                            sfx_volume, ROW_SFX_Y)

        _draw_toggle("Mute on Focus Loss", settings_mute_rect,

                     mute_on_focus_loss, ROW_MUTE_Y)

        _draw_hint("Silences all audio when the window loses focus.", ROW_MUTE_Y + 36)



    elif active_tab == 2:

        # GAMEPLAY

        _draw_section_header("COMBAT", CONTENT_Y)

        _draw_toggle("Crosshair", settings_crosshair_rect, crosshair, ROW_CROSSHAIR_Y)


        _draw_stepper("Crosshair Size", settings_crosshair_size_left, settings_crosshair_size_right,

                      CROSSHAIR_SIZE_LABELS[CROSSHAIR_SIZES.index(crosshair_size)] if crosshair_size in CROSSHAIR_SIZES else "MEDIUM",

                      ROW_CROSSHAIR_SIZE_Y)

        _draw_toggle("Auto-Reload", settings_auto_reload_rect, auto_reload, ROW_AUTO_RELOAD_Y)

        _draw_hint("Automatically reload when the magazine runs dry.", ROW_AUTO_RELOAD_Y + 36)

        _draw_toggle("Aim Assist", settings_aim_assist_rect, aim_assist, ROW_AIM_ASSIST_Y)

        _draw_hint("Subtly pulls the aim toward nearby enemies.", ROW_AIM_ASSIST_Y + 30)

        _draw_section_header("PRESENTATION", ROW_SUBTITLES_Y - 30)

        _draw_toggle("Subtitles", settings_subtitles_rect, subtitles, ROW_SUBTITLES_Y)

        _draw_hint("Shows spoken dialogue as on-screen text.", ROW_SUBTITLES_Y + 36)

        _draw_stepper("Text Speed", settings_text_speed_left, settings_text_speed_right,
                      TEXT_SPEED_LABELS[text_speed] if text_speed in (0, 1, 2) else "NORMAL",
                      ROW_TEXT_SPEED_Y)



    elif active_tab == 3:

        # GRAPHICS

        _draw_section_header("IMAGE", CONTENT_Y)

        _draw_volume_slider("Brightness", settings_brightness_bar,

                            settings_brightness_left, settings_brightness_right,

                            brightness, ROW_BRIGHTNESS_Y)

        _draw_hint("Adjusts the overall image brightness. 50 = default.", ROW_BRIGHTNESS_Y + 36)

        _draw_section_header("POST-PROCESSING", ROW_SCANLINES_Y - 30)

        _draw_toggle("Scanlines", settings_scanlines_rect, scanlines, ROW_SCANLINES_Y)

        _draw_hint("CRT horizontal scanline overlay.", ROW_SCANLINES_Y + 36)

        _draw_toggle("Film Grain", settings_grain_rect, grain, ROW_GRAIN_Y)

        _draw_hint("Animated grain texture over the screen.", ROW_GRAIN_Y + 36)

        _draw_volume_slider("Particle Density", settings_particles_bar,

                            settings_particles_left, settings_particles_right,

                            particle_density, ROW_PARTICLES_Y)

        _draw_hint("Scales the number of particles (explosions, smoke, blood).", ROW_PARTICLES_Y + 36)



    elif active_tab == 4:

        # CONTROLS (RPE6 P9): live key remapping + gamepad.  Click a badge,
        # then press a key; ESC cancels.  FIRE stays on the mouse.
        _draw_section_header("INPUT / CURSOR AIM", CONTENT_Y)
        _draw_hint("Aim follows your mouse pointer directly; no look sensitivity or inversion.", ROW_MOUSE_SENS_Y)
        _draw_hint("Gamepad: left stick moves, buttons act. FIRE stays on the mouse.", ROW_MOUSE_SENS_Y + 24)
        _draw_section_header("KEY BINDINGS", ROW_MOUSE_SENS_Y + 66)
        _binding_actions = [("move_up", "MOVE UP"), ("move_down", "MOVE DOWN"),
                            ("move_left", "MOVE LEFT"), ("move_right", "MOVE RIGHT"),
                            ("interact", "INTERACT"), ("reload", "RELOAD"),
                            ("sprint", "SPRINT"), ("advance", "ADVANCE"),
                            ("skip", "PAUSE / SKIP")]
        settings_binding_rects.clear()
        for i, (action, label) in enumerate(_binding_actions):
            col, row = i % 2, i // 2
            x = LABEL_X + col * 376
            y = ROW_MOUSE_SENS_Y + 103 + row * 41
            badge = pygame.Rect(x + 150, y, 118, 31)
            settings_binding_rects[action] = badge
            capturing = (binding_capture == action)
            pygame.draw.rect(screen, (44, 40, 22) if capturing else (28, 35, 25), badge)
            pygame.draw.rect(screen, (231, 181, 94) if capturing else (79, 89, 69), badge, 1)
            key_label = "PRESS A KEY..." if capturing else str((bindings or {}).get(action, "")).upper()
            text = font_terminal_small.render(key_label, True, (231, 181, 94))
            screen.blit(text, (badge.centerx - text.get_width() // 2, badge.centery - text.get_height() // 2))
            screen.blit(font_terminal_small.render(label, True, (215, 220, 199)), (x, y + 8))
        reset_y = ROW_MOUSE_SENS_Y + 103 + 5 * 41
        settings_binding_reset_rect.update(LABEL_X, reset_y, 150, 31)
        pygame.draw.rect(screen, (28, 35, 25), settings_binding_reset_rect)
        pygame.draw.rect(screen, (79, 89, 69), settings_binding_reset_rect, 1)
        text = font_terminal_small.render("RESET DEFAULTS", True, (215, 220, 199))
        screen.blit(text, (settings_binding_reset_rect.centerx - text.get_width() // 2,
                           settings_binding_reset_rect.centery - text.get_height() // 2))



    else:

        # ACCESSIBILITY

        _draw_section_header("MOTION", CONTENT_Y)

        _draw_toggle("Reduced Motion", settings_reduced_motion_rect,

                     reduced_motion, ROW_REDUCED_MOTION_Y)

        _draw_hint("Disables screen shake and bright full-screen flashes.", ROW_REDUCED_MOTION_Y + 36)

        _draw_section_header("VISION", ROW_COLORBLIND_Y - 30)

        _draw_stepper("Colorblind Mode", settings_colorblind_left, settings_colorblind_right,

                      COLORBLIND_MODES[colorblind_mode] if colorblind_mode < len(COLORBLIND_MODES) else "OFF",

                      ROW_COLORBLIND_Y)

        _draw_hint("Adjusts UI colors for color vision deficiency.", ROW_COLORBLIND_Y + 38)
        _draw_section_header("RADIO", ROW_RADIO_SIZE_Y - 30)
        from ui import radio as _radio_ui
        _draw_stepper("Radio Text Size", settings_radio_size_left, settings_radio_size_right,
                      _radio_ui.SIZE_LABELS[_radio_ui.PREFS.get("radio_text_size", 1)],
                      ROW_RADIO_SIZE_Y)
        _draw_hint("Size of radio transmission text in missions.", ROW_RADIO_SIZE_Y + 38)
        _draw_toggle("Radio Speaker Names", settings_radio_names_rect,
                     _radio_ui.PREFS.get("radio_speaker_names", True), ROW_RADIO_NAMES_Y)
        _draw_hint("Callsign plate on radio transmissions.", ROW_RADIO_NAMES_Y + 36)
        _draw_section_header("COMFORT", ROW_COMFORT_Y)
        _draw_toggle("Flash Reduction", settings_flash_rect, flash_reduction, ROW_FLASH_Y)
        _draw_stepper("Shake Scale", settings_shake_left, settings_shake_right,
                      "%d%%" % shake_scale, ROW_SHAKE_Y)



    # Texture stays off labels and controls; no flickering/glitch effects here.
    if scanlines and not reduced_motion:
        screen.blit(_CRT_SCANLINES, (SETTINGS_PANEL_X, SETTINGS_PANEL_Y),
                    (0, 0, SETTINGS_PANEL_W, 10))

    line_y = SETTINGS_PANEL_Y + SETTINGS_PANEL_H - 100
    pygame.draw.line(screen, (67, 78, 60), (LABEL_X, line_y),
                     (SETTINGS_PANEL_X + SETTINGS_PANEL_W - 48, line_y))
    status_col = (240, 142, 115) if save_failed else (231, 181, 94)
    screen.blit(font_terminal_small.render(save_status, True, status_col), (LABEL_X, line_y + 10))
    shortcuts = font_terminal_small.render(_T("sys.tab_1_6_sections_ctrl_s_apply_es"), True, (157, 170, 143))
    screen.blit(shortcuts, (SETTINGS_PANEL_X + SETTINGS_PANEL_W - 48 - shortcuts.get_width(), line_y + 30))

    # Explicit, consistent command bar. Rectangles also work before first draw.
    for button, primary in ((settings_back_btn, False), (settings_apply_btn, True)):
        button.check_hover(mouse)
        bg = (56, 61, 38) if button.is_hovered else (28, 35, 25)
        pygame.draw.rect(screen, bg, button.rect)
        pygame.draw.rect(screen, (231, 181, 94) if primary or button.is_hovered else (79, 89, 69), button.rect, 1)
        label = font_prompt.render("APPLY / SAVE" if primary else "SAVE & BACK", True,
                                   (231, 181, 94) if primary else (215, 220, 199))
        screen.blit(label, (button.rect.centerx - label.get_width() // 2,
                            button.rect.centery - label.get_height() // 2))

# ─────────────────────────────────────────────

# PAUSE / DEATH

# ─────────────────────────────────────────────

# Pause buttons moved down to make room for a proper title + mission status
# block. The original positions (280/340/400) left the pause menu as just a
# flat overlay with "PAUSED" text + 3 naked buttons - visually jarring next
# to the polished main menu and death screen.
#
# Layout (screen Y coordinates):
#   Panel:     y=70 to y=630 (560 tall)
#   Banner:    y=92
#   Title:     y=135 (Impact 80, bottom ~215)
#   Accent:    y=220
#   Op name:   y=235
#   Header:    y=265
#   Divider:   y=283
#   Status:    y=298, 324, 350, 376 (4 rows, bottom ~394)
#   Buttons:   y=410, 460, 510, 560 (4 buttons, 50px apart, bottom ~600)
#   Footer:    y=608
#
# 4 buttons: RESUME, SETTINGS, RESTART MISSION, QUIT TO MENU.
# SETTINGS was added so the user can adjust options mid-mission without
# quitting. The SETTINGS state returns to PAUSED (not MENU) when entered
# from the pause menu - see _settings_return_to in acaristan.py.

pause_buttons = [

    ModernButton(WIDTH // 2 - 150, 410, "RESUME"),

    ModernButton(WIDTH // 2 - 150, 460, "SETTINGS"),

    ModernButton(WIDTH // 2 - 150, 510, "RESTART MISSION"),

    ModernButton(WIDTH // 2 - 150, 560, "QUIT TO MENU"),

]

death_buttons = [

    ModernButton(WIDTH // 2 - 150, 330, "RESTART MISSION"),

    ModernButton(WIDTH // 2 - 150, 390, "QUIT TO MENU"),

]

# Darker overlay for the pause screen - 200 alpha makes the frozen gameplay
# recede more than the old 180, giving the panel better contrast.
#
# The custom arrow cursor is drawn AFTER this overlay (see acaristan.py's main
# loop). It carries its own drop shadow and black outline, so it stays legible
# over a 200 dim - no need to lighten the overlay for it.
_PAUSE_DIM_ALPHA = 200
_pause_overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)

_pause_overlay.fill((0, 0, 0, _PAUSE_DIM_ALPHA))

# Cached panel frame: border + corner ticks + classification banner + title +
# accent bar + footer. These never change during a pause session, so we build
# them once. Dynamic content (operation name, status block, buttons) is drawn
# on top each frame.
_pause_panel_w, _pause_panel_h = 560, 560

_pause_panel_x = (WIDTH - _pause_panel_w) // 2

_pause_panel_y = 70

_pause_panel_frame = pygame.Surface((_pause_panel_w, _pause_panel_h), pygame.SRCALPHA)

# Panel background - slightly lighter than the full-screen overlay so the
# panel reads as a distinct surface.
_pause_panel_frame.fill((8, 10, 14, 210))

# Orange border (2px) + inner dim border (1px) - matches the settings panel
# treatment in draw_settings().
pygame.draw.rect(_pause_panel_frame, C_ORANGE, _pause_panel_frame.get_rect(), 2)

pygame.draw.rect(_pause_panel_frame, (90, 50, 20), _pause_panel_frame.get_rect().inflate(-4, -4), 1)

# Corner ticks - matching the main menu _menu_overlay corner accent style.
for cx, cy in [(10, 10), (_pause_panel_w - 10, 10), (10, _pause_panel_h - 10), (_pause_panel_w - 10, _pause_panel_h - 10)]:

    dx = 1 if cx < _pause_panel_w // 2 else -1

    dy = 1 if cy < _pause_panel_h // 2 else -1

    pygame.draw.line(_pause_panel_frame, C_ORANGE, (cx, cy), (cx + dx * 16, cy), 2)

    pygame.draw.line(_pause_panel_frame, C_ORANGE, (cx, cy), (cx, cy + dy * 16), 2)

# Classification banner at top of panel - matches the main menu's banner.
_banner_y = 22

pygame.draw.line(_pause_panel_frame, C_ORANGE, (30, _banner_y), (_pause_panel_w - 30, _banner_y), 1)

pygame.draw.line(_pause_panel_frame, C_ORANGE, (30, _banner_y + 24), (_pause_panel_w - 30, _banner_y + 24), 1)

_banner_font = pygame.font.SysFont("Consolas", 11, bold=True)

_banner_text = _banner_font.render(_T("sys.krapnet_terminal_operation_suspe"), True, C_ORANGE)

_pause_panel_frame.blit(_banner_text, ((_pause_panel_w - _banner_text.get_width()) // 2, _banner_y + 5))

# "PAUSED" title - Impact 80 with drop shadow, matching the main menu title.
# Panel-relative Y=65 → screen Y = _pause_panel_y + 65 = 135.
_title_y = 65

_title_shadow = font_title.render(_T("sys.paused"), True, (0, 0, 0))

_pause_panel_frame.blit(_title_shadow, ((_pause_panel_w - _title_shadow.get_width()) // 2 + 4, _title_y + 4))

_title_main = font_title.render(_T("sys.paused"), True, C_WHITE)

_pause_panel_frame.blit(_title_main, ((_pause_panel_w - _title_main.get_width()) // 2, _title_y))

# Orange accent bar under title - matches the main menu's accent bar.
_bar_y = _title_y + 88

pygame.draw.rect(_pause_panel_frame, C_ORANGE, ((_pause_panel_w - 200) // 2, _bar_y, 200, 3))

# Footer hint at bottom of panel.
_footer_font = pygame.font.SysFont("Consolas", 12)

_footer_text = _footer_font.render(_T("sys.esc_resume_f11_toggle_fullscreen"), True, (100, 100, 100))

_pause_panel_frame.blit(_footer_text, ((_pause_panel_w - _footer_text.get_width()) // 2, _pause_panel_h - 22))

# Small status-block font (reused for the dynamic rows).
_pause_stat_label_font = pygame.font.SysFont("Consolas", 13, bold=True)

_pause_stat_value_font = pygame.font.SysFont("Consolas", 18, bold=True)


def _format_elapsed(seconds):
    """mm:ss for the elapsed-time stat."""
    m = int(seconds) // 60
    s = int(seconds) % 60
    return f"{m:02d}:{s:02d}"


def draw_pause_menu():
    """Draw the pause overlay + framed panel + mission status + buttons.

    Redesigned from the original 3-line placeholder (flat overlay + "PAUSED"
    text + naked buttons) to match the main menu's visual language: framed
    panel with corner ticks, classification banner, Impact title with drop
    shadow + orange accent bar, operation subtitle, live mission status
    block (elapsed time / hostiles / accuracy / ammo), and the same
    ModernButton style used everywhere else.
    """

    screen.blit(_pause_overlay, (0, 0))

    screen.blit(_pause_panel_frame, (_pause_panel_x, _pause_panel_y))

    # ── Operation subtitle (dynamic - depends on current mission) ──
    op_name = _mission_meta.operation_name(STATE)

    op_surf = font_terminal.render(op_name, True, C_TERMINAL)

    screen.blit(op_surf, (WIDTH // 2 - op_surf.get_width() // 2, _pause_panel_y + 165))

    # ── Mission status header ──
    header_surf = _pause_stat_label_font.render(_T("sys.mission_status"), True, C_ORANGE)

    screen.blit(header_surf, (WIDTH // 2 - header_surf.get_width() // 2, _pause_panel_y + 195))

    # Thin divider under the header.
    pygame.draw.line(screen, (90, 50, 20),

                     (WIDTH // 2 - 120, _pause_panel_y + 213),

                     (WIDTH // 2 + 120, _pause_panel_y + 213), 1)

    # ── Status rows ──
    # Compute live values from STATE. Everything degrades gracefully to
    # "-" if the mission hasn't started yet or STATE doesn't have the field.
    try:

        end_t = getattr(STATE, "mission_end_time", 0) or _now_ms()

        start_t = getattr(STATE, "mission_start_time", 0) or end_t

        elapsed = max(0, (end_t - start_t) // 1000)

        elapsed_str = _format_elapsed(elapsed)

    except Exception:

        elapsed_str = "--:--"

    hostiles = getattr(STATE, "hostiles_killed", 0)

    shots_fired = getattr(STATE, "shots_fired", 0)

    shots_hit = getattr(STATE, "shots_hit", 0)

    accuracy = int((shots_hit / shots_fired) * 100) if shots_fired > 0 else 0

    ammo_in_mag = getattr(STATE, "ammo_in_mag", 0)

    mag_size = getattr(STATE, "mag_size", 0)

    spare_mags = getattr(STATE, "spare_mags", 0)

    # Two columns: labels on the left, values on the right, centered as a block.
    col_label_x = WIDTH // 2 - 140

    col_value_x = WIDTH // 2 + 140

    rows = [

        ("ELAPSED", elapsed_str),

        ("HOSTILES NEUTRALIZED", str(hostiles)),

        ("ACCURACY", f"{accuracy}%  ({shots_hit}/{shots_fired})"),

        ("AMMO", f"{ammo_in_mag}/{mag_size}  +{spare_mags} mags"),

    ]

    row_y = _pause_panel_y + 228

    for label, value in rows:

        lbl_surf = _pause_stat_label_font.render(label, True, C_GREY)

        val_surf = _pause_stat_value_font.render(value, True, C_WHITE)

        screen.blit(lbl_surf, (col_label_x - lbl_surf.get_width(), row_y))

        screen.blit(val_surf, (col_value_x, row_y))

        row_y += 26

    # ── Buttons ──
    for btn in pause_buttons:

        btn.check_hover(get_scaled_mouse())

        btn.draw(screen)

_death_animation_start = 0

_death_particles = []

_death_font = pygame.font.SysFont("Arial Black", 70)

_death_sub_font = pygame.font.SysFont("Consolas", 22, bold=True)

_death_flavor_font = pygame.font.SysFont("Consolas", 16)

_server_title_font = pygame.font.SysFont("Impact", 46)

def reset_death_animation():

    global _death_animation_start, _death_particles

    _death_animation_start = 0

    _death_particles = []

    # The Black Ledger custom screen temporarily lays these shared buttons out
    # side-by-side. Always restore the generic death-screen layout on reset so
    # Mission 1 / Mission 2 death screens cannot inherit M3-specific positions.
    for i, btn in enumerate(death_buttons):
        btn.x = WIDTH // 2 - 150
        btn.y = 330 + i * 60
        btn.rect.x = btn.x
        btn.rect.y = HEIGHT + 200  # not clickable before the first reveal frame
        btn.rect.size = (btn.width, btn.height)
        btn.is_hovered = False
        btn.is_selected = False


def draw_death_screen():
    """Dispatch known missions to their own terminal; preserve neutral modes."""
    global _death_animation_start
    # lazy: presentation is loaded after the ui facade has finished importing.
    from ui import mission_failed
    if _mission_meta.mission_key(STATE) in mission_failed.PROFILES:
        if _death_animation_start == 0:
            _death_animation_start = max(1, _now_ms())
        mission_failed.draw(screen, STATE, death_buttons,
                            max(0, _now_ms() - _death_animation_start),
                            _now_ms(), get_scaled_mouse())
        return
    _draw_generic_death_screen()


def _draw_generic_death_screen():

    global _death_animation_start, _death_particles

    if _death_animation_start == 0:

        _death_animation_start = _now_ms()

        for _ in range(150):

            _death_particles.append({

                'x': _rng_legacy.randint(0, WIDTH),

                'y': _rng_legacy.randint(0, HEIGHT),

                'r': _rng_legacy.randint(2, 7),

                'a': _rng_legacy.randint(60, 160),

                'vy': _rng_legacy.uniform(0.1, 0.4)

            })

    elapsed = _now_ms() - _death_animation_start

    dark_alpha = min(180, int(elapsed * 0.15))

    overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)

    overlay.fill((10, 5, 5, dark_alpha))

    screen.blit(overlay, (0, 0))

    beat_cycle = elapsed % 1200

    if beat_cycle < 200:

        beat_intensity = 1.0 - (beat_cycle / 200.0)

    else:

        beat_intensity = 0.0

    vig_alpha = int(100 * beat_intensity) + 30

    vig = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)

    for i in range(0, WIDTH, 3):

        a = max(0, vig_alpha - int(vig_alpha * i / WIDTH * 1.2))

        if a > 0:

            pygame.draw.rect(vig, (120, 0, 0, a), (i, i, WIDTH - i * 2, HEIGHT - i * 2), 3)

    screen.blit(vig, (0, 0))

    for p in _death_particles:

        p['y'] += p['vy']

        pygame.draw.circle(screen, (80, 5, 5, p['a']), (int(p['x']), int(p['y'])), p['r'])

    if elapsed < 400:

        flash_alpha = max(0, 255 - int(elapsed * 1.2))

        flash = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)

        if elapsed < 100:

            flash_color = (255, 220, 220, flash_alpha)

        else:

            flash_color = (150, 10, 10, flash_alpha)

        flash.fill(flash_color)

        screen.blit(flash, (0, 0))

    if elapsed > 600:

        text_alpha = min(255, (elapsed - 600) * 2)

        offset_x, offset_y = 0, 0

        if elapsed < 700:

            offset_x = _rng_legacy.randint(-8, 8)

            offset_y = _rng_legacy.randint(-4, 4)

        shadow_surf = _death_font.render(_T("sys.mission_failed"), True, (0, 0, 0))

        shadow_surf.set_alpha(text_alpha)

        title_y = HEIGHT // 2 - 140

        screen.blit(shadow_surf, (WIDTH // 2 - shadow_surf.get_width() // 2 + 4 + offset_x, title_y + 4 + offset_y))

        text_surf = _death_font.render(_T("sys.mission_failed"), True, (210, 30, 30))

        text_surf.set_alpha(text_alpha)

        screen.blit(text_surf, (WIDTH // 2 - text_surf.get_width() // 2 + offset_x, title_y + offset_y))

    if elapsed > 1000:

        sub_alpha = min(255, (elapsed - 1000) * 2)

        # Per-mission copy lives in core/mission_meta.py (neutral fallback
        # for unknown modes - never Mission 1's BLACK NOTEBOOK by default).
        sub_text, flavor_text = _mission_meta.fail_text(STATE)

        sub = _death_sub_font.render(sub_text, True, (180, 180, 180))

        sub.set_alpha(sub_alpha)

        screen.blit(sub, (WIDTH // 2 - sub.get_width() // 2, HEIGHT // 2 - 60))

        flavor = _death_flavor_font.render(flavor_text, True, (120, 120, 120))

        flavor.set_alpha(sub_alpha)

        screen.blit(flavor, (WIDTH // 2 - flavor.get_width() // 2, HEIGHT // 2 - 30))

    if elapsed > 1150:

        panel_alpha = min(230, int((elapsed - 1150) * 0.35))

        try:

            from missions import walking_sim

            civilians_helped = sum(1 for n in walking_sim.walk_npcs if n.get("has_given"))

            rations_used = max(0, 2 - int(walking_sim.player_rations))

        except Exception:

            civilians_helped = 0

            rations_used = 0

        end_t = STATE.mission_end_time or _now_ms()

        start_t = STATE.mission_start_time or end_t

        elapsed_sec = max(0, (end_t - start_t) // 1000)

        accuracy = int((STATE.shots_hit / STATE.shots_fired) * 100) if STATE.shots_fired > 0 else 0

        if getattr(STATE, "active_mission", "MISSION1") == "MISSION2":

            evidence_found = 0

            try:

                evidence_found = sum(1 for item in getattr(STATE, "mission2_evidence", []) if item.get("done"))

            except Exception:

                evidence_found = 0

            stats = [

                ("KILLS", str(STATE.hostiles_killed)),

                ("SHOTS FIRED", str(STATE.shots_fired)),

                ("ACCURACY", f"{accuracy}%"),

                ("TOTAL TIME", f"{elapsed_sec // 60:02d}:{elapsed_sec % 60:02d}"),

                ("EVIDENCE FOUND", f"{evidence_found}/3"),

                ("COMMS", "OFFLINE" if getattr(STATE, "mission2_comms_cut", False) else "VASILE"),

            ]

        else:

            stats = [

                ("KILLS", str(STATE.hostiles_killed)),

                ("SHOTS FIRED", str(STATE.shots_fired)),

                ("ACCURACY", f"{accuracy}%"),

                ("TOTAL TIME", f"{elapsed_sec // 60:02d}:{elapsed_sec % 60:02d}"),

                ("CIVILIANS HELPED", str(civilians_helped)),

                ("RATIONS USED", str(rations_used)),

            ]

        panel_w, panel_h = 520, 104

        panel_x = WIDTH // 2 - panel_w // 2

        panel_y = HEIGHT // 2 + 16

        panel = pygame.Surface((panel_w, panel_h), pygame.SRCALPHA)

        panel.fill((8, 8, 12, panel_alpha))

        pygame.draw.rect(panel, (120, 35, 35, min(160, panel_alpha)), panel.get_rect(), 1)

        pygame.draw.rect(panel, (170, 35, 35, min(200, panel_alpha)), (0, 0, 4, panel_h))

        screen.blit(panel, (panel_x, panel_y))

        for i, (label, value) in enumerate(stats):

            col = i % 3

            row = i // 3

            sx = panel_x + 24 + col * 165

            sy = panel_y + 16 + row * 42

            lbl = font_terminal_small.render(label, True, (135, 80, 80))

            val = _death_sub_font.render(value, True, (220, 210, 205))

            lbl.set_alpha(panel_alpha)

            val.set_alpha(panel_alpha)

            screen.blit(lbl, (sx, sy))

            screen.blit(val, (sx, sy + 15))

    if elapsed > 600 and _rng_legacy.random() > 0.92:

        glitch_y = _rng_legacy.randint(0, HEIGHT)

        glitch_h = _rng_legacy.randint(2, 8)

        glitch_surf = pygame.Surface((WIDTH, glitch_h), pygame.SRCALPHA)

        glitch_surf.fill((255, 255, 255, 40))

        screen.blit(glitch_surf, (_rng_legacy.randint(-10, 10), glitch_y))

    if elapsed > 1500:

        btn_progress = min(1.0, (elapsed - 1500) / 600.0)

        ease = 1 - (1 - btn_progress) ** 3

        for i, btn in enumerate(death_buttons):

            # Generic death screen is always centered. Black Ledger uses the
            # same button objects with a different layout, so reset X here too.
            btn.x = WIDTH // 2 - 150
            btn.rect.x = btn.x

            target_y = HEIGHT // 2 + 150 + i * 60

            start_y = target_y + 40

            current_y = start_y + (target_y - start_y) * ease

            btn.y = int(current_y)

            btn.rect.y = btn.y

            btn.check_hover(get_scaled_mouse())

            btn.draw(screen)

def draw_black_ledger_death_screen():
    """Persistent custom death screen for Mission 3's Black Ledger easter egg.

    Unlike the generic death screen, this is intentionally static/readable:
    a sealed black-site dossier with the normal Restart Mission / Quit to Menu
    buttons below it.
    """
    global _death_animation_start

    if _death_animation_start == 0:
        _death_animation_start = _now_ms()

    elapsed = _now_ms() - _death_animation_start

    # Full black-site background.
    screen.fill((5, 4, 4))

    # Very subtle red surveillance wash.
    wash = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
    pulse = int(18 + 8 * math.sin(_now_ms() * 0.0025))
    wash.fill((70, 0, 0, pulse))
    screen.blit(wash, (0, 0))

    # Slow, sparse scanlines/noise - static screen, not chaos.
    for y in range(0, HEIGHT, 4):
        pygame.draw.line(screen, (18, 12, 12), (0, y), (WIDTH, y), 1)
    rng = random.Random(91414 + _now_ms() // 250)
    for _ in range(70):
        x = rng.randint(0, WIDTH - 1)
        y = rng.randint(0, HEIGHT - 1)
        a = rng.randint(12, 38)
        screen.set_at((x, y), (min(255, 30 + a), min(255, 22 + a // 2), min(255, 20 + a // 2)))

    # Main dossier card.
    card_w, card_h = 720, 455
    card_x = WIDTH // 2 - card_w // 2
    card_y = 54
    shadow = pygame.Surface((card_w + 24, card_h + 24), pygame.SRCALPHA)
    shadow.fill((0, 0, 0, 160))
    screen.blit(shadow, (card_x + 10, card_y + 12))

    card = pygame.Rect(card_x, card_y, card_w, card_h)
    pygame.draw.rect(screen, (174, 149, 108), card, border_radius=3)
    pygame.draw.rect(screen, (38, 12, 10), card, 4, border_radius=3)
    pygame.draw.rect(screen, (110, 30, 24), card.inflate(-10, -10), 1, border_radius=2)

    # Header.
    title = font_title.render(_T("sys.black_ledger"), True, (36, 10, 8))
    screen.blit(title, (card.centerx - title.get_width() // 2, card_y + 18))
    sub = font_terminal.render(_T("sys.incident_sealed_entry_014"), True, (96, 22, 18))
    screen.blit(sub, (card.centerx - sub.get_width() // 2, card_y + 96))

    pygame.draw.line(screen, (70, 28, 22), (card_x + 36, card_y + 130), (card.right - 36, card_y + 130), 2)

    # Left side: entry data.
    rows = [
        ("SUBJECT", "BIRIBEL"),
        ("STATUS", "COUNTED"),
        ("CAUSE", "INMATE 000 CONTACT"),
        ("REGISTER", "NONCOMBATANT LEDGER"),
        ("CAMERA", "CAM-13 / SIGNAL LOST"),
        ("RESPONSE", "AUTOMATED RECORD SEAL"),
    ]
    row_x = card_x + 54
    row_y = card_y + 158
    for i, (label, value) in enumerate(rows):
        y = row_y + i * 38
        lbl = font_terminal_small.render(label, True, (82, 48, 36))
        val_col = (132, 12, 12) if value in ("COUNTED", "BIRIBEL") else (38, 20, 15)
        val = font_terminal.render(value, True, val_col)
        screen.blit(lbl, (row_x, y))
        screen.blit(val, (row_x + 142, y - 4))

    # Right side: mugshot/silhouette block.
    mug = pygame.Rect(card.right - 250, card_y + 155, 190, 205)
    pygame.draw.rect(screen, (28, 22, 19), mug)
    pygame.draw.rect(screen, (84, 54, 40), mug, 2)
    for yy in range(mug.top + 18, mug.bottom - 12, 26):
        pygame.draw.line(screen, (52, 42, 36), (mug.left + 12, yy), (mug.right - 12, yy), 1)
    pygame.draw.ellipse(screen, (4, 4, 4), (mug.centerx - 58, mug.bottom - 66, 116, 38))
    pygame.draw.rect(screen, (6, 6, 6), (mug.centerx - 38, mug.top + 86, 76, 88), border_radius=18)
    pygame.draw.circle(screen, (7, 7, 7), (mug.centerx, mug.top + 74), 30)
    pygame.draw.rect(screen, (152, 84, 34), (mug.centerx - 38, mug.top + 136, 76, 25), border_radius=3)
    zero = font_terminal.render(_T("sys.000"), True, (236, 172, 82))
    screen.blit(zero, (mug.centerx - zero.get_width() // 2, mug.top + 134))
    cap = font_terminal_small.render(_T("sys.inmate_000"), True, (154, 124, 88))
    screen.blit(cap, (mug.centerx - cap.get_width() // 2, mug.bottom + 8))

    # Large red stamp.
    stamp = pygame.Surface((310, 96), pygame.SRCALPHA)
    pygame.draw.rect(stamp, (125, 0, 0, 38), (0, 0, 310, 96), border_radius=5)
    pygame.draw.rect(stamp, (146, 10, 10, 220), (10, 10, 290, 76), 6, border_radius=5)
    stxt = font_title.render(_T("sys.counted"), True, (150, 8, 8))
    stxt = pygame.transform.scale(stxt, (264, 62))
    stamp.blit(stxt, (24, 18))
    stamp = pygame.transform.rotate(stamp, -7)
    screen.blit(stamp, (card_x + 380, card_y + 334))

    # Warning footer on the card.
    warn = font_terminal_small.render(_T("sys.the_ledger_does_not_forget_who_f"), True, (84, 20, 16))
    screen.blit(warn, (card.centerx - warn.get_width() // 2, card.bottom - 34))

    # Screen title/footer outside the card.
    footer = font_terminal_small.render(_T("sys.mission_3_the_vostral_black_ledg"), True, (100, 60, 54))
    screen.blit(footer, (WIDTH // 2 - footer.get_width() // 2, HEIGHT - 36))

    # Buttons fade in quickly and then remain static.
    btn_alpha_ready = elapsed > 350
    for i, btn in enumerate(death_buttons):
        btn.y = HEIGHT - 150 + i * 58
        btn.rect.y = btn.y
        btn.check_hover(get_scaled_mouse())
        if btn_alpha_ready:
            btn.draw(screen)
        else:
            ghost = font_terminal.render(btn.text, True, (80, 45, 45))
            screen.blit(ghost, (btn.x + btn.width // 2 - ghost.get_width() // 2, btn.y + 13))

def _black_ledger_death_button_progress():
    """0..1 reveal progress for Black Ledger death controls."""
    global _death_animation_start
    if _death_animation_start == 0:
        _death_animation_start = _now_ms()
    elapsed = _now_ms() - _death_animation_start
    # Let the Ledger verdict breathe before controls appear.
    delay = 850
    duration = 900
    p = max(0.0, min(1.0, (elapsed - delay) / duration))
    # Smoothstep easing.
    return p * p * (3.0 - 2.0 * p)


def black_ledger_death_buttons_ready():
    """True once the Black Ledger death controls are visually usable."""
    return _black_ledger_death_button_progress() >= 0.92


def draw_black_ledger_death_buttons():
    """Draw only the interactive controls for the Black Ledger death screen.

    They now fade/slide in after the verdict instead of popping into existence.
    This keeps the final Ledger frame feeling like a death screen first and an
    options menu second.
    """
    progress = _black_ledger_death_button_progress()
    if progress <= 0.01:
        # Keep button rects away from the mouse while invisible.
        for btn in death_buttons:
            btn.rect.y = HEIGHT + 200
            btn.is_hovered = False
        return

    alpha = int(225 * progress)
    slide = int((1.0 - progress) * 34)

    controls = pygame.Surface((WIDTH, 112), pygame.SRCALPHA)

    # Bottom shelf fades in softly from black, not as a hard new UI panel.
    shelf_h = 92
    shelf = pygame.Surface((WIDTH, shelf_h), pygame.SRCALPHA)
    shelf.fill((0, 0, 0, int(142 * progress)))
    pygame.draw.line(shelf, (105, 34, 28, int(130 * progress)), (0, 0), (WIDTH, 0), 1)
    controls.blit(shelf, (0, 18 + slide // 2))

    prompt_alpha = int(160 * progress)
    prompt = font_terminal_small.render(
        _T("sys.death_record_complete"), True, (135, 82, 74)
    )
    prompt.set_alpha(prompt_alpha)
    controls.blit(prompt, (WIDTH // 2 - prompt.get_width() // 2, 10 + slide // 2))

    # Place the two existing death buttons side-by-side under the death verdict.
    positions = [
        (WIDTH // 2 - 320, 54 + slide),
        (WIDTH // 2 + 20, 54 + slide),
    ]

    ready_for_hover = progress >= 0.84
    mp = get_scaled_mouse()
    # Convert mouse into the local controls surface coordinate.
    local_mp = (mp[0], mp[1] - (HEIGHT - controls.get_height()))

    for btn, (x, y) in zip(death_buttons, positions):
        btn.x = int(x)
        btn.y = int(y)
        btn.rect.x = btn.x
        # Actual screen-space rect must include the controls surface offset.
        btn.rect.y = int(HEIGHT - controls.get_height() + btn.y)

        if ready_for_hover:
            # Temporarily test hover against local surface coordinates.
            old_rect_y = btn.rect.y
            btn.rect.y = btn.y
            btn.check_hover(local_mp)
            btn.rect.y = old_rect_y
        else:
            btn.is_hovered = False

        # Draw to local surface with local y, then restore screen-space rect.
        old_rect_y = btn.rect.y
        btn.rect.y = btn.y
        btn.draw(controls)
        btn.rect.y = old_rect_y

    controls.set_alpha(alpha)
    screen.blit(controls, (0, HEIGHT - controls.get_height()))
