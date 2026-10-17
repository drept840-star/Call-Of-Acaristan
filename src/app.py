
import random
from engine.core import LEGACY_RNG as _rng_legacy  # RPE6 R6: named 'legacy' rng stream
import sys
import math
import pygame
from core.config import (C_KRAP_BLUE, C_ORANGE, C_VASILE, GRAIN_VARIANTS, HEIGHT, LETTER_H, TILE_SIZE, WIDTH, audio, clock, draw_letterbox, draw_rain, draw_scanlines, draw_vignette, font_btn, font_dialogue, font_location, font_prompt, font_terminal, font_terminal_small, font_title, get_scaled_mouse, grain_frame, grain_idx, screen)
from audio import voice  # VO stop/pause on skip, pause menu, quit
from core.state import STATE
import ui as menu
from ui import mp as menu_mp  # DM-input state owner (menu._dm_input would shadow the shim)
from ui.widgets import _classification_font
from core import game_core as gc
from core import profile_store
from core import save_system
from core import settings_store
from core.user_settings import SETTINGS
from core.fsm import GameState, GameStateManager
from core.level_editor import LevelEditor
from core.console import Console
from core import interactions
from core import ambience
from core import mission_meta as _mission_meta
from core.dev_jumps import DEV_JUMPS, jump_flag
from core import fixedstep as _fixedstep
from engine.core import now_ms as _now_ms  # RPE6 B-001 timebase
try:  # RPE6 Phase 0 dev-only recorder; never let it block startup
    from tools import input_recorder as _input_recorder
except Exception:  # noqa: BLE001
    class _input_recorder:  # noqa: N801 - inert stand-in
        enabled = staticmethod(lambda: False)
        record = staticmethod(lambda *a, **k: None)
# Arena match runtime. One process-wide instance, like STATE: it owns a
# socket, so there must never be two of them. The multiplayer screen
# delegates to it whenever it is open, and the browser underneath is
# bypassed entirely while a match is running.
from ui.match_screen import MatchScreen as _MatchScreen
_match_screen = _MatchScreen()
# The Outfitter. Same one-instance rule as the match screen: it is the only
# thing that writes the wallet, and two of them could each hold a stale view of
# the balance and spend the same Acaribucks twice.
from ui.shop import ShopScreen as _ShopScreen
_shop_screen = _ShopScreen()
# NOTE: An earlier unified-render experiment (render_pipeline /
# game_renderer / game_draw_unified) was removed as dead code: it was never
# wired into the GAME state's render path, which routes via
# game_core.game_draw() to the per-mission game_draw() functions.

# ─────────────────────────────────────────────
# STATE
# ─────────────────────────────────────────────
gsm = GameStateManager()

# NOTE on the old FSM bridge: an earlier version of fsm.py stored states in
# `self._states` and exposed only names (strings), so acaristan.py monkey-
# patched a `.current` property onto the class to reach the live state object.
# fsm.py has since been refactored: it now stores states in `self.states` and
# sets `self.current` (the live state object) natively in __init__ /
# transition(). That monkey-patch is obsolete and actively harmful - its
# `hasattr(GameStateManager, 'current')` guard is False at the *class* level
# (because `current` is an instance attribute, not a class attribute), so the
# patch would overwrite the real `.current` with a property reading the
# non-existent `self._states`, causing AttributeError on the first transition.
# Do not re-add it.

mission_complete_timer = 0
mission_complete_fade = 0

# Cosmetic transition / briefing screens
briefing_timer = 0
briefing_kind = "warehouse"
BRIEFING_DURATION = 360

escape_cutscene_timer = 0
ESCAPE_CUTSCENE_DURATION = 1080

# Multiplayer easter egg
mp_state = "browser"
mp_timer = 0
mp_selected = -1
mp_kick_msg = ""
menu_notice = ""
menu_notice_timer = 0
_slot_rects = []
_slot_focus = 0
slot_select_purpose = "new"
_last_briefing_title_chars = 0

_cutscene_fog = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
_cutscene_fog.fill((18, 22, 30, 60))
_cutscene_top_fog = pygame.Surface((WIDTH, HEIGHT // 2), pygame.SRCALPHA)
for _i in range(HEIGHT // 2):
    _a = int(80 * (1 - _i / (HEIGHT // 2)))
    pygame.draw.line(_cutscene_top_fog, (20, 25, 35, _a), (0, _i), (WIDTH, _i))

TEXT_SPEED = 4


def _text_speed_interval():
    """Frames per typed cutscene character (text_speed setting; TEXT_SPEED at 1.0x)."""
    try:
        from core.user_settings import SETTINGS as _us
        return max(1, int(round(TEXT_SPEED / max(0.1, _us.text_speed_mul))))
    except Exception:
        return TEXT_SPEED
_fade_surf = pygame.Surface((WIDTH, HEIGHT))

_pause_dim_overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
_pause_dim_overlay.fill((0, 0, 0, 180))

# Settings - loaded from settings_store
_settings = settings_store.load()

from game import input_adapter as _input_adapter  # RPE6 P9 (after settings load use)
_input_adapter.load_bindings(_settings.get("bindings"))

STATE.reduced_motion = _settings["reduced_motion"]
STATE.flash_reduction = _settings["flash_reduction"]   # RPE6 P9 live mirror for painters
shake_scale = _settings["shake_scale"]
flash_reduction = _settings["flash_reduction"]
text_speed = _settings["text_speed"]
display_mode = _settings["display_mode"]
res_idx = _settings["resolution_idx"]
master_volume = _settings["master_volume"]
music_volume = _settings["music_volume"]
sfx_volume = _settings["sfx_volume"]
mute_on_focus_loss = _settings["mute_on_focus_loss"]
crosshair = _settings["crosshair"]
crosshair_size = _settings["crosshair_size"]
auto_reload = _settings["auto_reload"]
aim_assist = _settings["aim_assist"]
subtitles = _settings["subtitles"]
radio_text_size = _settings["radio_text_size"]
radio_speaker_names = _settings["radio_speaker_names"]
brightness = _settings["brightness"]
scanlines_enabled = _settings["scanlines"]
grain_enabled = _settings["grain"]
particle_density = _settings["particle_density"]
mouse_sensitivity = _settings["mouse_sensitivity"]
invert_mouse = _settings["invert_mouse"]
colorblind_mode = _settings["colorblind_mode"]

settings_active_tab = 0
_binding_capture = None   # RPE6 P9: action awaiting a keypress in CONTROLS, or None
_settings_return_to = "MENU"
_settings_saved = None
_settings_status = "CONFIG SYNCED"
_settings_save_failed = False
_settings_drag_bar = None
# Where BACK leaves you. The Outfitter is reached from the multiplayer screen,
# and dropping the player on the main menu from there would mean re-navigating
# the whole way back to a match. "MENU" is only the fallback for a transition
# that did not come through that button. Same trick as _settings_return_to.
_shop_return_to = "MENU"

# Tracks last camera position for states that freeze the game frame
# (PAUSED, DEATH, NOTEBOOK_INSPECT, SETTINGS-from-pause).
_frozen_cx = 0
_frozen_cy = 0


def _current_settings_dict():
    return {
        "display_mode": display_mode,
        "resolution_idx": res_idx,
        "master_volume": master_volume,
        "music_volume": music_volume,
        "sfx_volume": sfx_volume,
        "mute_on_focus_loss": mute_on_focus_loss,
        "crosshair": crosshair,
        "crosshair_size": crosshair_size,
        "auto_reload": auto_reload,
        "aim_assist": aim_assist,
        "subtitles": subtitles,
        "radio_text_size": radio_text_size,
        "radio_speaker_names": radio_speaker_names,
        "brightness": brightness,
        "scanlines": scanlines_enabled,
        "grain": grain_enabled,
        "particle_density": particle_density,
        "mouse_sensitivity": mouse_sensitivity,
        "invert_mouse": invert_mouse,
        "reduced_motion": STATE.reduced_motion,
        "shake_scale": shake_scale,
        "flash_reduction": flash_reduction,
        "text_speed": text_speed,
        "colorblind_mode": colorblind_mode,
        "bindings": _input_adapter.bindings_dict(),   # RPE6 P9: non-default bindings only
    }


def _apply_audio_settings():
    audio.set_master_volume(master_volume)
    audio.set_music_volume(music_volume / 100.0)
    audio.set_sfx_volume(sfx_volume / 100.0)


def _push_live_settings():
    SETTINGS.push_from_raw(_current_settings_dict())
    from ui import radio as _radio_ui
    _radio_ui.apply_settings(_current_settings_dict())
    _apply_audio_settings()


def _persist_settings():
    global _settings_saved, _settings_status, _settings_save_failed
    current = _current_settings_dict()
    _push_live_settings()
    if current == _settings_saved:
        return True
    if not settings_store.save(current):
        _settings_save_failed = True
        _settings_status = "SAVE FAILED / CHECK FILE ACCESS, THEN RETRY APPLY"
        return False
    _settings_saved = dict(current)
    _settings_save_failed = False
    _settings_status = "CONFIG SAVED / LOCAL PROFILE"
    return True


def _preview_settings():
    global _settings_status, _settings_save_failed
    _push_live_settings()
    _settings_save_failed = False
    _settings_status = ("UNSAVED CHANGES / LIVE PREVIEW" if
                        _current_settings_dict() != _settings_saved else "CONFIG SYNCED")


_settings_saved = _current_settings_dict()
_push_live_settings()

_bright_dark = pygame.Surface((WIDTH, HEIGHT))
_bright_dark.fill((0, 0, 0))
_bright_light = pygame.Surface((WIDTH, HEIGHT))
_bright_light.fill((255, 245, 220))


def _advance_grain():
    global grain_frame, grain_idx
    if not SETTINGS.film_grain:
        return None
    grain_frame += 1
    if grain_frame >= 3:
        grain_frame = 0
        grain_idx = (grain_idx + 1) % len(GRAIN_VARIANTS)
    return GRAIN_VARIANTS[grain_idx]


def _apply_postprocess():
    b = SETTINGS.brightness
    if abs(b - 1.0) < 0.01:
        return
    if b < 1.0:
        alpha = int((1.0 - b) * 255)
        _bright_dark.set_alpha(alpha)
        screen.blit(_bright_dark, (0, 0))
    else:
        alpha = int(min(1.0, (b - 1.0)) * 120)
        _bright_light.set_alpha(alpha)
        screen.blit(_bright_light, (0, 0), special_flags=pygame.BLEND_RGB_ADD)


def _present_frame():
    """Present the fixed 1000x700 game frame to the actual OS window.

    Normally pygame.SCALED does this for us. On some Windows/SDL paths,
    toggling F11 from fullscreen to windowed and then maximizing the window
    leaves the display surface at the physical window size, so the game draws
    only into the top-left 1000x700 area and the rest stays black. This helper
    detects that fallback path and scales/centers the logical frame manually.
    """
    display_surf = pygame.display.get_surface()
    if display_surf is None:
        return

    render_surf = screen
    dw, dh = display_surf.get_size()
    rw, rh = render_surf.get_size()

    # Fast path: normal pygame.SCALED logical surface.
    if display_surf is render_surf and (dw, dh) == (WIDTH, HEIGHT):
        return

    # Build/copy a clean logical frame. If render_surf is already the logical
    # surface, copy it only when we're about to overwrite the display surface.
    if (rw, rh) == (WIDTH, HEIGHT):
        frame = render_surf.copy() if display_surf is render_surf else render_surf
    else:
        frame = pygame.Surface((WIDTH, HEIGHT)).convert()
        frame.fill((0, 0, 0))
        src_rect = pygame.Rect(0, 0, min(WIDTH, rw), min(HEIGHT, rh))
        frame.blit(render_surf, (0, 0), src_rect)

    if (dw, dh) == (WIDTH, HEIGHT):
        if display_surf is not frame:
            display_surf.blit(frame, (0, 0))
        return

    scale = min(dw / WIDTH, dh / HEIGHT) if WIDTH and HEIGHT else 1.0
    scaled_w = max(1, int(WIDTH * scale))
    scaled_h = max(1, int(HEIGHT * scale))
    ox = (dw - scaled_w) // 2
    oy = (dh - scaled_h) // 2

    display_surf.fill((0, 0, 0))
    scaled = pygame.transform.scale(frame, (scaled_w, scaled_h))
    display_surf.blit(scaled, (ox, oy))


def handle_settings_event(event):
    global settings_active_tab, _settings_drag_bar, _binding_capture
    global display_mode, res_idx
    global master_volume, music_volume, sfx_volume, mute_on_focus_loss
    global crosshair, crosshair_size, auto_reload, aim_assist, subtitles
    global radio_text_size, radio_speaker_names
    global brightness, scanlines_enabled, grain_enabled, particle_density
    global mouse_sensitivity, invert_mouse, colorblind_mode
    global shake_scale, flash_reduction, text_speed

    if event.type == pygame.KEYDOWN:
        if _binding_capture is not None:
            if event.key != pygame.K_ESCAPE:   # ESC cancels capture
                _input_adapter.set_binding(_binding_capture, pygame.key.name(event.key))
            _binding_capture = None
            _preview_settings()
            return None
        if event.key == pygame.K_TAB:
            delta = -1 if getattr(event, "mod", 0) & pygame.KMOD_SHIFT else 1
            settings_active_tab = (settings_active_tab + delta) % len(menu.SETTINGS_TABS)
            _settings_drag_bar = None
        elif pygame.K_1 <= event.key <= pygame.K_6:
            settings_active_tab = event.key - pygame.K_1
            _settings_drag_bar = None
        elif event.key == pygame.K_s and getattr(event, "mod", 0) & pygame.KMOD_CTRL:
            _persist_settings()
        return None

    mp = get_scaled_mouse()
    slider_specs = {
        1: [(menu.settings_master_bar_rect, "master_volume"),
            (menu.settings_music_bar_rect, "music_volume"),
            (menu.settings_sfx_bar_rect, "sfx_volume")],
        3: [(menu.settings_brightness_bar, "brightness"),
            (menu.settings_particles_bar, "particle_density")],
    }
    if event.type == pygame.MOUSEBUTTONUP and event.button == 1:
        _settings_drag_bar = None
        return None
    if event.type == pygame.MOUSEMOTION:
        if _settings_drag_bar is not None and getattr(event, "buttons", (0, 0, 0))[0]:
            rect, key = _settings_drag_bar
            globals()[key] = max(0, min(100, round((mp[0] - rect.x) * 100 / (rect.width - 1))))
            _preview_settings()
        else:
            _settings_drag_bar = None
        return None
    if event.type != pygame.MOUSEBUTTONDOWN or event.button != 1:
        return None

    if menu.settings_apply_btn.rect.collidepoint(mp):
        _settings_drag_bar = None
        if _persist_settings():
            audio.play("menu_click", volume=0.5)
            return "apply"
        return None

    if menu.settings_back_btn.rect.collidepoint(mp):
        _settings_drag_bar = None
        return "back" if _persist_settings() else None

    for rect, key in slider_specs.get(settings_active_tab, []):
        if rect.inflate(0, 24).collidepoint(mp):
            _settings_drag_bar = (rect, key)
            globals()[key] = max(0, min(100, round((mp[0] - rect.x) * 100 / (rect.width - 1))))
            _preview_settings()
            return None

    for i, rect in enumerate(menu.settings_tab_rects):
        if rect.collidepoint(mp):
            _settings_drag_bar = None
            settings_active_tab = i
            audio.play("menu_click", volume=0.4)
            return None

    def _bar_value(bar_rect):
        t = (mp[0] - bar_rect.x) / bar_rect.width
        return max(0, min(100, int(t * 100)))

    step = 5

    if settings_active_tab == 0:
        mode_changed = False
        if menu.settings_display_left_rect.collidepoint(mp):
            display_mode = (display_mode - 1) % len(menu.DISPLAY_MODES)
            mode_changed = True
        elif menu.settings_display_right_rect.collidepoint(mp):
            display_mode = (display_mode + 1) % len(menu.DISPLAY_MODES)
            mode_changed = True
        if mode_changed:
            if mode_changed:
                apply_display_mode(display_mode, menu.SETTINGS_RESOLUTIONS[res_idx])
            _preview_settings()
            audio.play("menu_click", volume=0.4)

    elif settings_active_tab == 1:
        changed = False
        if menu.settings_master_left_rect.collidepoint(mp):
            master_volume = max(0, master_volume - step); changed = True
        elif menu.settings_master_right_rect.collidepoint(mp):
            master_volume = min(100, master_volume + step); changed = True
        elif menu.settings_master_bar_rect.collidepoint(mp):
            master_volume = _bar_value(menu.settings_master_bar_rect); changed = True
        elif menu.settings_music_left_rect.collidepoint(mp):
            music_volume = max(0, music_volume - step); changed = True
        elif menu.settings_music_right_rect.collidepoint(mp):
            music_volume = min(100, music_volume + step); changed = True
        elif menu.settings_music_bar_rect.collidepoint(mp):
            music_volume = _bar_value(menu.settings_music_bar_rect); changed = True
        elif menu.settings_sfx_left_rect.collidepoint(mp):
            sfx_volume = max(0, sfx_volume - step); changed = True
        elif menu.settings_sfx_right_rect.collidepoint(mp):
            sfx_volume = min(100, sfx_volume + step); changed = True
        elif menu.settings_sfx_bar_rect.collidepoint(mp):
            sfx_volume = _bar_value(menu.settings_sfx_bar_rect); changed = True
        elif menu.settings_mute_rect.collidepoint(mp):
            mute_on_focus_loss = not mute_on_focus_loss; changed = True
        if changed:
            _preview_settings()
            audio.play("menu_click", volume=0.3)

    elif settings_active_tab == 2:
        changed = False
        if menu.settings_crosshair_rect.collidepoint(mp):
            crosshair = not crosshair; changed = True
        elif menu.settings_crosshair_size_left.collidepoint(mp):
            idx = menu.CROSSHAIR_SIZES.index(crosshair_size) if crosshair_size in menu.CROSSHAIR_SIZES else 1
            crosshair_size = menu.CROSSHAIR_SIZES[(idx - 1) % len(menu.CROSSHAIR_SIZES)]; changed = True
        elif menu.settings_crosshair_size_right.collidepoint(mp):
            idx = menu.CROSSHAIR_SIZES.index(crosshair_size) if crosshair_size in menu.CROSSHAIR_SIZES else 1
            crosshair_size = menu.CROSSHAIR_SIZES[(idx + 1) % len(menu.CROSSHAIR_SIZES)]; changed = True
        elif menu.settings_auto_reload_rect.collidepoint(mp):
            auto_reload = not auto_reload; changed = True
        elif menu.settings_aim_assist_rect.collidepoint(mp):
            aim_assist = not aim_assist; changed = True
        elif menu.settings_subtitles_rect.collidepoint(mp):
            subtitles = not subtitles; changed = True
        elif menu.settings_text_speed_left.collidepoint(mp):
            text_speed = (text_speed - 1) % 3; changed = True
        elif menu.settings_text_speed_right.collidepoint(mp):
            text_speed = (text_speed + 1) % 3; changed = True
        if changed:
            _preview_settings()
            audio.play("menu_click", volume=0.3)

    elif settings_active_tab == 3:
        changed = False
        if menu.settings_brightness_left.collidepoint(mp):
            brightness = max(0, brightness - step); changed = True
        elif menu.settings_brightness_right.collidepoint(mp):
            brightness = min(100, brightness + step); changed = True
        elif menu.settings_brightness_bar.collidepoint(mp):
            brightness = _bar_value(menu.settings_brightness_bar); changed = True
        elif menu.settings_scanlines_rect.collidepoint(mp):
            scanlines_enabled = not scanlines_enabled; changed = True
        elif menu.settings_grain_rect.collidepoint(mp):
            grain_enabled = not grain_enabled; changed = True
        elif menu.settings_particles_left.collidepoint(mp):
            particle_density = max(0, particle_density - step); changed = True
        elif menu.settings_particles_right.collidepoint(mp):
            particle_density = min(100, particle_density + step); changed = True
        elif menu.settings_particles_bar.collidepoint(mp):
            particle_density = _bar_value(menu.settings_particles_bar); changed = True
        if changed:
            _preview_settings()
            audio.play("menu_click", volume=0.3)

    elif settings_active_tab == 4:
        changed = False
        for action, rect in menu.settings_binding_rects.items():
            if rect.collidepoint(mp):
                _binding_capture = action
                changed = True
                break
        else:
            if menu.settings_binding_reset_rect.collidepoint(mp):
                _input_adapter.reset_bindings()
                changed = True
        if changed:
            _preview_settings()

    else:
        changed = False
        if menu.settings_reduced_motion_rect.collidepoint(mp):
            STATE.reduced_motion = not STATE.reduced_motion; changed = True
        elif menu.settings_colorblind_left.collidepoint(mp):
            colorblind_mode = (colorblind_mode - 1) % len(menu.COLORBLIND_MODES); changed = True
        elif menu.settings_colorblind_right.collidepoint(mp):
            colorblind_mode = (colorblind_mode + 1) % len(menu.COLORBLIND_MODES); changed = True
        elif menu.settings_radio_size_left.collidepoint(mp):
            radio_text_size = (radio_text_size - 1) % 3; changed = True
        elif menu.settings_radio_size_right.collidepoint(mp):
            radio_text_size = (radio_text_size + 1) % 3; changed = True
        elif menu.settings_radio_names_rect.collidepoint(mp):
            radio_speaker_names = not radio_speaker_names; changed = True
        elif menu.settings_flash_rect.collidepoint(mp):
            flash_reduction = not flash_reduction
            STATE.flash_reduction = flash_reduction; changed = True
        elif menu.settings_shake_left.collidepoint(mp):
            shake_scale = max(0, shake_scale - 25); changed = True
        elif menu.settings_shake_right.collidepoint(mp):
            shake_scale = min(100, shake_scale + 25); changed = True
        if changed:
            _preview_settings()
            audio.play("menu_click", volume=0.3)

    return None


def trigger_transition(target_state):
    """Fade-transition to target_state. Delegates to gsm (AEGIS FSM)."""
    gsm.trigger_transition(target_state)


# ─────────────────────────────────────────────
# CUTSCENE PLAYER (encapsulated state)
# ─────────────────────────────────────────────

# One-shot SFX cues for the Mission 3 Kill Order transition cinematic
# (scene -> (elapsed_ms, sfx, volume)); fired once per shot instance.
# Also covers the Kill Order -> Broadcast transition (same player).
KO_CUT_CUES = {
    "m3_ko_charge": ((0, "door_rattle", 0.35), (1150, "breach", 0.9)),
    "m3_ko_stairwell": ((0, "concrete_impact", 0.28),),
    "m3_ko_aperture": ((0, "elec_hum", 0.20), (1950, "bullet_snap", 0.45)),
    "m3_ko_van": ((0, "door_creak", 0.40),),
    "m3_bcast_shutter": ((0, "door_rattle", 0.35), (900, "concrete_impact", 0.50)),
    "m3_bcast_road": ((0, "wind_gust", 0.15),),
    "m3_bcast_mast": ((0, "elec_hum", 0.20),),
    "m3_bcast_onair": ((0, "radio_static", 0.25), (1200, "pa_mumble", 0.30)),
}


class CutscenePlayer:
    """Encapsulates all cutscene playback state.

    Replaces the 7 module-level globals that previously tracked
    active_cutscene_shots, cutscene_shot_idx, cutscene_char_idx,
    cutscene_timer, cutscene_start_time, cutscene_after,
    cutscene_transition_timer, cutscene_use_fades.
    """

    def __init__(self, shots, after_state, use_fades=True):
        self.shots = [self._normalize(s) for s in shots]
        self.after_state = after_state
        self.use_fades = use_fades
        self.shot_idx = 0
        self.char_idx = 0
        self.timer = 0
        self.start_time = _now_ms()
        self.transition_timer = 0  # >0 = fading out, <0 = fading in, 0 = none
        self.fired_cues = set()
        self._paused_at = None
        self.skip_confirm = False
        self.completed = False
        self.finale_audio = None  # optional scene-owned stems / foley channels

    @staticmethod
    def _normalize(shot):
        """Ensure all shots have text as string, not None."""
        shot = dict(shot)
        if shot.get("text") is None:
            shot["text"] = ""
        return shot

    @property
    def current_shot(self):
        if 0 <= self.shot_idx < len(self.shots):
            return self.shots[self.shot_idx]
        return None

    @property
    def is_finished(self):
        return self.shot_idx >= len(self.shots)

    @property
    def elapsed_ms(self):
        now = self._paused_at if self._paused_at is not None else _now_ms()
        return now - self.start_time

    @property
    def paused(self):
        return self._paused_at is not None

    def pause(self):
        if not self.paused:
            self._paused_at = _now_ms()

    def resume(self):
        if self.paused:
            self.start_time += _now_ms() - self._paused_at
            self._paused_at = None


# Module-level reference to the active cutscene player (or None).
active_cutscene = None


_M5_MID = {"key": None}   # key of the M5 mid-mission cutscene being played


def _m0_outro_pending():
    """RPE6 P10: Mission 0 exit reached -> play its outro timeline."""
    try:
        from missions import m0 as _m0
        return _m0.take_outro_request()
    except Exception:
        return False


def _m5_mid_cut_key():
    """Pending M5 mid-mission cutscene key (round 2), or None."""
    from core.state import STATE as _st5  # lazy: app keeps STATE access local
    key = getattr(_st5, "request_m5_cutscene", None)
    from missions.m5.meta import M5_MID_CUTSCENES  # lazy: M5-only data
    return key if key in M5_MID_CUTSCENES else None


def start_cutscene(shots, after_state, use_fades=True):
    global active_cutscene
    if active_cutscene and active_cutscene.finale_audio:
        active_cutscene.finale_audio.stop()  # replacement/replay owns fresh channels
    # Lazy synthesis is warmed before the shot clock starts: otherwise the
    # first long sound can consume the opening camera beat on slower machines.
    # The finale brings its own sound set; creating FinaleAudio registers its
    # generators, so it happens before the cue prewarm below can ask for them.
    finale_audio = None
    if any(s.get("scene") == "m5_shadow_finale" for s in shots):
        from missions.m5.finale_audio import FinaleAudio
        finale_audio = FinaleAudio(audio)
    for shot in shots:
        for _, name, _ in shot.get("cues", ()):
            audio.get_sound(name)
        for _, speaker, text, _ in shot.get("dialogue_events", ()):
            voice.clip_ms(speaker, text)  # scan/load takes before the actor clock
        if shot.get("scene") == "m5_shadow_finale":
            from cutscenes.m5shadow3d import prepare
            prepare()
    # A live radio line must not talk over the scene: fade it (~120 ms),
    # squelch, drop its subtitle; critical queued lines are held for after.
    if finale_audio is not None:
        finale_audio.prepare()
    interactions.radio_cutscene_cut()
    active_cutscene = CutscenePlayer(shots, after_state, use_fades)
    active_cutscene.finale_audio = finale_audio
    gc.reset_dialogue_slide()


# ─────────────────────────────────────────────
# AMBIENCE
# ─────────────────────────────────────────────

_current_ambience = set()
MENU_MUSIC_FILE = "menu_theme.mp3"
_menu_music_active = False
_menu_music_failed = False
MENU_MUSIC_STATES = {"MENU", "SLOT_SELECT", "SETTINGS", "SHOP", "MULTIPLAYER"}


def _set_menu_music(should_play):
    global _menu_music_active, _menu_music_failed
    if should_play:
        if not _menu_music_active and not _menu_music_failed:
            _menu_music_active = bool(audio.play_music(MENU_MUSIC_FILE, volume=0.48))
            _menu_music_failed = not _menu_music_active
    else:
        if _menu_music_active:
            audio.stop_music()
            _menu_music_active = False


def _play_typewriter_tick(ch, idx, volume=0.11):
    if not ch or ch.isspace():
        return
    if idx % 2 != 0 and ch not in ".!?":
        return
    try:
        audio.play("type_tick", volume=volume)
    except Exception:
        pass


_ambience_epoch = 0


def _set_ambience(sounds_to_play):
    global _current_ambience, _ambience_epoch
    ep = getattr(audio, "stop_epoch", 0)
    if ep != _ambience_epoch:            # audio.hard_stop()/stop_all() killed the loops
        _ambience_epoch = ep
        _current_ambience = set()
    for name in list(_current_ambience):
        if name not in sounds_to_play:
            audio.stop(name)
    for name in sounds_to_play:
        if name not in _current_ambience:
            audio.play(name, volume=0.3, loops=-1)
    _current_ambience = set(sounds_to_play)


# ─────────────────────────────────────────────
# DISPLAY MODE
# ─────────────────────────────────────────────

_applied_display_mode = 0


def apply_display_mode(mode, resolution_str=None):
    global display_mode, _applied_display_mode, screen
    if mode == _applied_display_mode:
        display_mode = mode
        return True

    flags = pygame.SCALED | pygame.RESIZABLE
    if mode == 1:
        flags = pygame.SCALED | pygame.FULLSCREEN

    try:
        pygame.display.set_mode((WIDTH, HEIGHT), flags)
        from core import config
        from core import game_core
        import ui as m
        new_surf = pygame.display.get_surface()
        config.screen = new_surf
        config._engine_app.set_screen(new_surf)  # RPE6 A-001
        game_core.screen = new_surf
        m.screen = new_surf
        screen = new_surf
        display_mode = mode
        _applied_display_mode = mode
        print(f"Display set to: {['Windowed', 'Fullscreen'][mode]}")
        return True
    except Exception as e:
        print(f"Display mode change failed ({e}), falling back to Windowed")
        try:
            pygame.display.set_mode((WIDTH, HEIGHT), pygame.SCALED | pygame.RESIZABLE)
            from core import config
            from core import game_core
            import ui as m
            new_surf = pygame.display.get_surface()
            config.screen = new_surf
            config._engine_app.set_screen(new_surf)  # RPE6 A-001
            game_core.screen = new_surf
            m.screen = new_surf
            screen = new_surf
            display_mode = 0
            _applied_display_mode = 0
        except Exception as e2:
            print(f"FATAL: Cannot create display surface: {e2}")
        return False


# ─────────────────────────────────────────────
# MISSION REPORT
# ─────────────────────────────────────────────

def _mission_report_data(success=True):
    end_t = gc.mission_end_time or _now_ms()
    start_t = gc.mission_start_time or end_t
    elapsed_sec = max(0, (end_t - start_t) // 1000)
    accuracy = int((gc.shots_hit / gc.shots_fired) * 100) if gc.shots_fired > 0 else 0
    civilians_helped = 0
    try:
        civilians_helped = sum(1 for n in gc.walk_npcs if n.get("has_given"))
    except Exception:
        civilians_helped = 0
    try:
        rations_used = max(0, 2 - int(gc.player_rations))
    except Exception:
        rations_used = 0
    if getattr(gc, "active_mission", "MISSION1") == "MISSION2":
        intel_found = bool(getattr(gc, "mission2_evidence_uploaded", False))
    else:
        intel_found = bool(getattr(gc, "notebook_collected", False) or getattr(gc, "warehouse_intel_given", False))
    stealth_clean = bool(getattr(gc, "stealth_clean", False))
    score = 0
    if success:
        score += 40
    score += min(25, int(gc.hostiles_killed) * 3)
    score += min(15, accuracy // 5)
    score += civilians_helped * 8
    score += 10 if intel_found else 0
    score += 8 if stealth_clean else 0
    score -= max(0, (elapsed_sec - 900) // 45) * 2
    score = max(0, min(100, score))
    if not success:
        rank = "FAILED"
    elif score >= 92:
        rank = "S"
    elif score >= 82:
        rank = "A"
    elif score >= 68:
        rank = "B"
    elif score >= 52:
        rank = "C"
    else:
        rank = "D"
    return {
        "kills": int(gc.hostiles_killed),
        "shots_fired": int(gc.shots_fired),
        "shots_hit": int(gc.shots_hit),
        "accuracy": accuracy,
        "time_str": f"{elapsed_sec // 60:02d}:{elapsed_sec % 60:02d}",
        "civilians_helped": civilians_helped,
        "rations_used": rations_used,
        "intel_found": intel_found,
        "stealth_clean": stealth_clean,
        "score": score,
        "rank": rank,
    }


# ─────────────────────────────────────────────
# SLOT SELECT
# ─────────────────────────────────────────────

def draw_slot_select_screen():
    """Draw save-slot selection in the house orange-terminal style.

    Pause-menu chrome recipe (orange 2px border + inner line + corner ticks +
    classification banner + Oswald title with drop shadow), dossier cards,
    CRT scanlines + vignette last. Same click rectangles / save logic as
    before - hit rects now cover the hover lift so they match what's drawn.
    """
    global _slot_rects, _slot_focus, menu_notice, menu_notice_timer

    menu.draw_menu_background()

    # Dark cinematic wash, cooler center so cards have depth but background art
    # still contributes atmosphere.
    dim = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
    dim.fill((0, 0, 0, 205))
    screen.blit(dim, (0, 0))

    data = save_system.load_data()
    mouse = get_scaled_mouse()
    current_idx = data.get("current_slot", 0)
    title_text = "SELECT SAVE SLOT" if slot_select_purpose == "new" else "CONTINUE CAMPAIGN"
    sub_text = ("Choose a file for the new operation. Occupied files will be overwritten."
                if slot_select_purpose == "new"
                else "Choose an active operation record to continue.")

    # ── Header plaque: pause-menu recipe ──
    plaque = pygame.Rect(WIDTH // 2 - 380, 56, 760, 112)
    pl = pygame.Surface((plaque.w, plaque.h), pygame.SRCALPHA)
    pl.fill((3, 8, 12, 220))
    pygame.draw.rect(pl, C_ORANGE, pl.get_rect(), 2)
    pygame.draw.rect(pl, (90, 50, 20), pl.get_rect().inflate(-6, -6), 1)
    for cx, cy in ((12, 12), (plaque.w - 12, 12), (12, plaque.h - 12), (plaque.w - 12, plaque.h - 12)):
        dx = 1 if cx < plaque.w // 2 else -1
        dy = 1 if cy < plaque.h // 2 else -1
        pygame.draw.line(pl, C_ORANGE, (cx, cy), (cx + dx * 14, cy), 2)
        pygame.draw.line(pl, C_ORANGE, (cx, cy), (cx, cy + dy * 14), 2)
    # Classification banner - same treatment as the main menu / pause panel.
    pygame.draw.line(pl, C_ORANGE, (40, 10), (plaque.w - 40, 10), 1)
    pygame.draw.line(pl, C_ORANGE, (40, 30), (plaque.w - 40, 30), 1)
    eyebrow = _classification_font.render(_T("app.krapnet_archive_save_management"), True, C_ORANGE)
    pl.blit(eyebrow, ((plaque.w - eyebrow.get_width()) // 2, 14))
    # Title: bundled Oswald (font_location) cached in config - never SysFont.
    t_w = font_location.size(title_text)[0]
    pl.blit(font_location.render(title_text, True, (0, 0, 0)),
            ((plaque.w - t_w) // 2 + 3, 34 + 3))
    pl.blit(font_location.render(title_text, True, (235, 242, 246)),
            ((plaque.w - t_w) // 2, 34))
    pygame.draw.rect(pl, C_ORANGE, (plaque.w // 2 - 110, 84, 220, 3))
    sub = font_terminal_small.render(
        menu_mp._fit_text(sub_text, font_terminal_small, plaque.w - 70),
        True, (152, 160, 154))
    pl.blit(sub, ((plaque.w - sub.get_width()) // 2, 92))
    screen.blit(pl, plaque.topleft)

    _slot_rects = []
    card_w, card_h = 286, 270
    gap = 28
    start_x = WIDTH // 2 - (card_w * 3 + gap * 2) // 2
    y = 222

    def _mission_label(slot):
        if not slot.get("occupied"):
            return "No campaign data"
        completed = slot.get("last_completed_mission")
        if completed:
            return slot.get("last_completed_label", "Campaign record")
        return slot.get("last_completed_label", "Campaign started")

    for i in range(3):
        x = start_x + i * (card_w + gap)
        # Hit rect covers the -8px hover lift so visual and hitbox match.
        rect = pygame.Rect(x, y - 8, card_w, card_h + 8)
        _slot_rects.append(rect)
        slot = data["slots"][i]
        occupied = bool(slot.get("occupied"))
        selectable = slot_select_purpose == "new" or occupied
        hovered = rect.collidepoint(mouse) and selectable
        if hovered and _slot_focus != i:
            _slot_focus = i
            audio.play("menu_hover", volume=0.25)
        active = hovered or (selectable and _slot_focus == i)

        # Card lift/outline.
        lift = -8 if active else 0
        draw_y = y + lift
        shadow = pygame.Surface((card_w + 20, card_h + 24), pygame.SRCALPHA)
        pygame.draw.rect(shadow, (0, 0, 0, 120 if active else 82), shadow.get_rect(), border_radius=12)
        screen.blit(shadow, (x - 8, draw_y + 8))

        card = pygame.Surface((card_w, card_h), pygame.SRCALPHA)
        base = (8, 14, 20, 238 if selectable else 178)
        pygame.draw.rect(card, base, card.get_rect(), border_radius=10)
        pygame.draw.rect(card, (255, 120, 0, 230) if active else ((70, 76, 82, 120) if not selectable else (52, 96, 128, 180)),
                         card.get_rect(), 3 if active else 1, border_radius=10)
        # Left file-tab accent.
        accent = (255, 120, 0) if active else ((75, 110, 130) if selectable else (55, 55, 58))
        pygame.draw.rect(card, (*accent, 230), (0, 0, 7, card_h), border_radius=5)
        # Dossier section lines - header band + separator above the action strip
        # (no line runs through any text row).
        for yy in (72, 210):
            pygame.draw.line(card, (44, 70, 86, 95), (22, yy), (card_w - 22, yy), 1)

        # File number header.
        file_num = font_terminal_small.render(_T("app.file_n", n=i + 1), True, (88, 142, 172))
        card.blit(file_num, (24, 18))
        header = font_terminal.render(_T("app.save_slot", n=i + 1), True,
                                      (255, 190, 95) if active else (150, 205, 232))
        card.blit(header, (24, 38))

        # Status chip.
        if occupied:
            status_text = "ACTIVE FILE"
            status_col = (92, 226, 142)
            chip_col = (10, 42, 25, 210)
        else:
            status_text = "EMPTY FILE"
            status_col = (150, 155, 158)
            chip_col = (28, 30, 32, 210)
        chip = pygame.Rect(24, 82, 132, 26)
        pygame.draw.rect(card, chip_col, chip, border_radius=4)
        pygame.draw.rect(card, (*status_col, 120), chip, 1, border_radius=4)
        st = font_terminal_small.render(status_text, True, status_col)
        card.blit(st, (chip.x + 10, chip.y + 6))

        # CURRENT-slot marker (persisted active slot), right of the chip.
        if occupied and i == current_idx:
            badge = "CURRENT"
            bw = font_terminal_small.size(badge)[0] + 16
            brect = pygame.Rect(card_w - 24 - bw, 84, bw, 22)
            pygame.draw.rect(card, (46, 24, 6, 230), brect, border_radius=3)
            pygame.draw.rect(card, (*C_ORANGE, 200), brect, 1, border_radius=3)
            bs = font_terminal_small.render(badge, True, C_ORANGE)
            card.blit(bs, (brect.x + 8, brect.y + 4))

        # Mission data.
        if occupied:
            completed = slot.get("last_completed_mission")
            l1 = "LAST COMPLETED" if completed else "IN PROGRESS"
            mission = _mission_label(slot)
            tline = f"TOTAL TIME  {slot.get('total_time', '00:00')}"
            updated = "UPDATED  " + save_system.format_timestamp(slot.get("updated_at"))
        else:
            if slot_select_purpose == "new":
                l1 = "NEW CAMPAIGN"
                mission = "Operation file will begin at Mission 1"
            else:
                l1 = "NO SAVE DATA"
                mission = "No operation record in this file"
            tline = "TOTAL TIME  --:--"
            updated = "UPDATED  never"

        label = font_terminal_small.render(l1, True, (92, 154, 190))
        card.blit(label, (24, 118))
        # Width-based truncation so long labels never overrun the card.
        mission_text = menu_mp._fit_text(mission, font_terminal_small, card_w - 48)
        mission_surf = font_terminal_small.render(mission_text, True,
                                                  (205, 205, 190) if occupied else (165, 165, 154))
        card.blit(mission_surf, (24, 142))
        time_surf = font_terminal_small.render(tline, True, (178, 184, 178))
        card.blit(time_surf, (24, 170))
        upd_surf = font_terminal_small.render(updated, True, (136, 142, 140))
        card.blit(upd_surf, (24, 190))

        # Action strip - reads as a button affordance.
        strip = pygame.Rect(14, 216, card_w - 28, 36)
        pygame.draw.rect(card, (14, 20, 28, 220) if selectable else (10, 12, 14, 180),
                         strip, border_radius=4)
        pygame.draw.rect(card, (C_ORANGE if active else ((52, 96, 128, 180) if selectable else (70, 76, 82, 120))),
                         strip, 1 if not active else 2, border_radius=4)
        if slot_select_purpose == "new":
            action = "OVERWRITE FILE" if occupied else "CREATE FILE"
            if occupied:
                action_col = (255, 165, 90) if active else (235, 115, 80)
            else:
                action_col = (150, 245, 180) if active else (115, 220, 150)
        else:
            action = "LOAD FILE" if occupied else "NO DATA"
            action_col = ((255, 190, 90) if active else (180, 190, 170)) if occupied else (120, 120, 120)
        action_surf = font_terminal_small.render(action, True, action_col if selectable else (90, 90, 90))
        card.blit(action_surf, (strip.centerx - action_surf.get_width() // 2, strip.y + 11))

        if active:
            # Small focus chevron and warm tint. Normal alpha blit - BLEND_ADD
            # ignores source alpha and would flood the whole card orange.
            pygame.draw.polygon(card, (255, 120, 0, 220), [(card_w - 31, 20), (card_w - 17, 27), (card_w - 31, 34)])
            glow = pygame.Surface((card_w, card_h), pygame.SRCALPHA)
            pygame.draw.rect(glow, (255, 120, 0, 28), glow.get_rect(), border_radius=10)
            card.blit(glow, (0, 0))

        screen.blit(card, (x, draw_y))

    # Bottom footer - orange top strip (MP-browser recipe) + purpose + ESC hint.
    footer_panel = pygame.Surface((720, 68), pygame.SRCALPHA)
    footer_panel.fill((0, 0, 0, 150))
    pygame.draw.rect(footer_panel, (42, 72, 90, 120), footer_panel.get_rect(), 1)
    pygame.draw.rect(footer_panel, (*C_ORANGE, 170), (0, 0, 720, 3))
    if slot_select_purpose == "new":
        footer_text = "New campaign writes to the selected file. Occupied files will be overwritten."
        footer_col = (184, 132, 92)
    else:
        footer_text = "Only active files can be continued."
        footer_col = (126, 150, 160)
    f1 = font_terminal_small.render(
        menu_mp._fit_text(footer_text, font_terminal_small, 690), True, footer_col)
    f2 = font_terminal_small.render(_T("app.press_esc_to_return_save_data_js"), True, (100, 108, 112))
    footer_panel.blit(f1, (720 // 2 - f1.get_width() // 2, 14))
    footer_panel.blit(f2, (720 // 2 - f2.get_width() // 2, 40))
    screen.blit(footer_panel, (WIDTH // 2 - footer_panel.get_width() // 2, HEIGHT - 92))

    # Toast notices (e.g. deny feedback on empty slots) - same style as the
    # menu's menu_notice pill, positioned in the gap above the footer.
    if menu_notice_timer > 0:
        notice = font_prompt.render(menu_notice, True, C_ORANGE)
        bg = pygame.Surface((notice.get_width() + 28, notice.get_height() + 12), pygame.SRCALPHA)
        bg.fill((0, 0, 0, 190))
        pygame.draw.rect(bg, (120, 70, 20), bg.get_rect(), 1)
        screen.blit(bg, (WIDTH // 2 - bg.get_width() // 2, 536))
        screen.blit(notice, (WIDTH // 2 - notice.get_width() // 2, 542))
        menu_notice_timer -= 1

    # CRT finish - same as death/settings screens.
    draw_scanlines(screen)
    draw_vignette(screen)


# ─────────────────────────────────────────────
# BRIEFING
# ─────────────────────────────────────────────

def start_briefing(kind="warehouse"):
    global briefing_timer, briefing_kind, _last_briefing_title_chars
    briefing_timer = 0
    briefing_kind = kind
    _last_briefing_title_chars = 0
    audio.play("radio_static", volume=0.22)
    audio.play("menu_click", volume=0.35)


def finish_briefing():
    if briefing_kind == "warehouse":
        gc.start_mission(preserve_timer=True)
        gsm.transition("GAME")
        pygame.mouse.set_visible(False)


def draw_briefing_screen():
    global _last_briefing_title_chars
    t = briefing_timer
    for y in range(HEIGHT):
        p = y / HEIGHT
        col = (int(4 + p * 6), int(8 + p * 12), int(15 + p * 22))
        pygame.draw.line(screen, col, (0, y), (WIDTH, y))
    rng = random.Random(t // 2)
    for _ in range(55):
        nx = rng.randint(0, WIDTH - 1)
        ny = rng.randint(0, HEIGHT - 1)
        shade = rng.randint(12, 32)
        screen.set_at((nx, ny), (shade, shade + 4, shade + 10))
    for y in range((t * 2) % 6, HEIGHT, 6):
        pygame.draw.line(screen, (0, 0, 0, 32), (0, y), (WIDTH, y), 1)
    sweep_y = int((t * 2.4) % (HEIGHT + 120)) - 60
    sweep = pygame.Surface((WIDTH, 80), pygame.SRCALPHA)
    for i in range(80):
        a = int(36 * (1 - abs(i - 40) / 40))
        pygame.draw.line(sweep, (45, 110, 160, max(0, a)), (0, i), (WIDTH, i))
    screen.blit(sweep, (0, sweep_y))
    panel_w, panel_h = min(860, WIDTH - 110), 470
    panel_x = WIDTH // 2 - panel_w // 2
    panel_y = HEIGHT // 2 - panel_h // 2 - 4
    panel = pygame.Surface((panel_w, panel_h), pygame.SRCALPHA)
    panel.fill((5, 10, 17, 232))
    pygame.draw.rect(panel, (45, 88, 126, 170), panel.get_rect(), 1)
    pygame.draw.rect(panel, C_KRAP_BLUE, (0, 0, 4, panel_h))
    pygame.draw.line(panel, (45, 88, 126, 120), (18, 64), (panel_w - 18, 64), 1)
    screen.blit(panel, (panel_x, panel_y))
    if 18 < t < 80 or (t // 45) % 5 == 0:
        for _ in range(3):
            gy = panel_y + rng.randint(20, panel_h - 20)
            gh = rng.randint(2, 7)
            gx = panel_x + rng.randint(-16, 16)
            strip = pygame.Surface((panel_w, gh), pygame.SRCALPHA)
            strip.fill((90, 170, 220, rng.randint(18, 45)))
            screen.blit(strip, (gx, gy))

    def blit_alpha(surf, x, y, alpha):
        surf.set_alpha(max(0, min(255, int(alpha))))
        screen.blit(surf, (x, y))

    boot_alpha = min(255, t * 7)
    eyebrow = font_terminal_small.render(_T("app.krap_signal_intercepted"), True, (85, 170, 220))
    blit_alpha(eyebrow, panel_x + 24, panel_y + 20, boot_alpha)
    stamp = font_terminal_small.render(_T("app.field_copy_unverified"), True, (190, 80, 60))
    blit_alpha(stamp, panel_x + panel_w - stamp.get_width() - 22, panel_y + 20, boot_alpha)
    title_text = "MISSION BRIEFING"
    title_chars = min(len(title_text), max(0, (t - 28) // 2))
    if title_chars > _last_briefing_title_chars:
        ch = title_text[title_chars - 1]
        _play_typewriter_tick(ch, title_chars - 1, volume=0.095)
        _last_briefing_title_chars = title_chars
    title = pygame.font.SysFont("Consolas", 40, bold=True).render(title_text[:title_chars], True, (220, 225, 220))
    blit_alpha(title, panel_x + 36, panel_y + 86, 255)
    loc_alpha = min(255, max(0, (t - 62) * 6))
    lines = [
        ("OPERATION", "BLACK NOTEBOOK"),
        ("LOCATION", "KILEMENO HARBOR DISTRICT / WAREHOUSE ROW"),
        ("STATUS", "OFFSHORE RIGS DESTROYED - UNKNOWN ATTACK CRAFT CONFIRMED"),
    ]
    value_x = panel_x + 170
    max_value_w = panel_w - 210
    for i, (label, value) in enumerate(lines):
        y = panel_y + 150 + i * 42
        lbl = font_terminal_small.render(label, True, (65, 120, 160))
        val_font = font_terminal
        val = val_font.render(value, True, (190, 190, 176))
        if val.get_width() > max_value_w:
            val_font = font_prompt
            val = val_font.render(value, True, (190, 190, 176))
        blit_alpha(lbl, panel_x + 42, y, loc_alpha - i * 35)
        blit_alpha(val, value_x, y - 4, loc_alpha - i * 35)
    obj_alpha = min(255, max(0, (t - 128) * 5))
    obj_divider_y = panel_y + 292
    pygame.draw.line(screen, (35, 68, 96), (panel_x + 36, obj_divider_y), (panel_x + panel_w - 36, obj_divider_y), 1)
    obj_title = font_terminal.render(_T("app.objectives"), True, (255, 150, 60))
    blit_alpha(obj_title, panel_x + 42, panel_y + 312, obj_alpha)
    objectives = [
        "Infiltrate the warehouse perimeter",
        "Locate and recover the black notebook",
        "Escape through the service exit",
    ]
    for i, txt in enumerate(objectives):
        alpha = obj_alpha - i * 30
        # Drawn square: "■" rendered as text is tofu on the bundled font.
        bullet = pygame.Surface((10, 10), pygame.SRCALPHA)
        bullet.fill((65, 150, 210, 255))
        line = font_prompt.render(txt, True, (205, 205, 195))
        row_y = panel_y + 350 + i * 26
        blit_alpha(bullet, panel_x + 48, row_y + 4, alpha)
        blit_alpha(line, panel_x + 72, row_y, alpha)
    bar_w = int((panel_w - 72) * min(1.0, max(0, (t - 42) / max(1, BRIEFING_DURATION - 92))))
    bar_y = panel_y + panel_h - 34
    pygame.draw.rect(screen, (10, 20, 30), (panel_x + 36, bar_y, panel_w - 72, 5))
    pygame.draw.rect(screen, C_KRAP_BLUE, (panel_x + 36, bar_y, bar_w, 5))
    prompt_txt = "PRESS SPACE TO DEPLOY" if t > 115 else "DECODING FIELD TRANSMISSION..."
    prompt_col = C_ORANGE if t > 115 else (95, 125, 145)
    prompt = font_terminal_small.render(prompt_txt, True, prompt_col)
    if t <= 115 or (_now_ms() // 450) % 2 == 0:
        blit_alpha(prompt, WIDTH // 2 - prompt.get_width() // 2, panel_y + panel_h + 22, min(255, t * 5))
    draw_scanlines(screen)
    draw_vignette(screen, strength=155)


# ─────────────────────────────────────────────
# DEV ARGS
# ─────────────────────────────────────────────

def _dev_flag_value(raw, name, default=None):
    """Return the value of `--name VALUE` / `--name=VALUE`, or *default*."""
    for _i, _a in enumerate(raw):
        if _a == name and _i + 1 < len(raw):
            return raw[_i + 1]
        if _a.startswith(name + "="):
            return _a.split("=", 1)[1]
    return default


def _apply_dev_args():
    global _frozen_cx, _frozen_cy, slot_select_purpose
    raw = sys.argv[1:]
    args = set(raw)
    if "--list-jumps" in args:
        print("Dev jump targets (python acaristan.py --jump NAME):")
        for _name, (_flag, _desc) in DEV_JUMPS.items():
            print(f"  {_name:<20} {_desc}")
            print(f"  {'':<20} (also: python acaristan.py {_flag})")
        print("\nUsage: python acaristan.py --jump NAME [extra flags...]")
        print("   or: python tools/dev.py NAME")
        sys.exit(0)
    # --jump NAME / --jump=NAME: look up the canonical flag in the
    # core.dev_jumps registry and inject it so the chain below handles it.
    _jump = None
    for _i, _a in enumerate(raw):
        if _a == "--jump" and _i + 1 < len(raw):
            _jump = raw[_i + 1]
            break
        if _a.startswith("--jump="):
            _jump = _a.split("=", 1)[1]
            break
    if _jump is not None:
        _flag = jump_flag(_jump)
        if _flag is None:
            print(f"Unknown --jump target {_jump!r}. Available targets:")
            for _name in DEV_JUMPS:
                print(f"  {_name}")
            sys.exit(2)
        args.add(_flag)
    if "--dev-m1" in args or "--m1" in args:
        # Jump into Mission 1 from the start, playable
        # (--dev-safe goes to the safe keypad instead).
        gc.mission_start_time = _now_ms()
        gc.mission_end_time = 0
        gc.start_mission(preserve_timer=True)
        gsm.transition("GAME")
        pygame.mouse.set_visible(False)
    elif "--dev-walk" in args or "--walk" in args:
        # Jump into the walking sim harbor from the start.
        gc.mission_start_time = _now_ms()
        gc.mission_end_time = 0
        gc.start_walking_sim()
        trigger_transition("WALK")
        pygame.mouse.set_visible(True)
    elif "--dev-safe" in args or "--m1-safe" in args or "--safe" in args:
        # Mission 1 safe/keypad debug jump. Opens the safe keypad immediately
        # so Easter eggs / keypad behavior can be tested without clearing the
        # warehouse first.
        gc.mission_start_time = _now_ms()
        gc.mission_end_time = 0
        gc.start_mission(preserve_timer=True)
        try:
            from missions import m1 as _m1
            _m1._init_mission_specials()
            if STATE.NOTEBOOK_POS and STATE.player:
                STATE.player.rect.centerx = STATE.NOTEBOOK_POS[0]
                STATE.player.rect.centery = STATE.NOTEBOOK_POS[1] + 54
                max_x = max(0, _m1.MAP_W * TILE_SIZE - WIDTH)
                max_y = max(0, _m1.MAP_H * TILE_SIZE - HEIGHT)
                STATE.camera_x = max(0, min(max_x, STATE.NOTEBOOK_POS[0] - WIDTH // 2))
                STATE.camera_y = max(0, min(max_y, STATE.NOTEBOOK_POS[1] - HEIGHT // 2))
                _frozen_cx, _frozen_cy = STATE.camera_x, STATE.camera_y
            # Remove hostiles for the debug jump; otherwise closing the keypad
            # instantly drops the tester into a live firefight.
            STATE.enemies = []
            STATE.safe_keypad_active = True
            STATE.safe_keypad_code = ""
            STATE.safe_keypad_target = "742"
            STATE.safe_keypad_callback = _m1._on_safe_opened
            STATE.safe_666_active = False
            STATE.safe_666_timer = 0
            STATE.active_read_note = None
        except Exception as _safe_err:
            print(f"--dev-safe setup failed: {_safe_err}")
        gsm.transition("GAME")
        pygame.mouse.set_visible(True)
    elif "--dev-mission2" in args or "--m2" in args:
        gc.mission_start_time = _now_ms()
        gc.mission_end_time = 0
        start_cutscene(gc.mission2_intro_shots, "MISSION2", use_fades=False)
        gsm.transition("CUTSCENE")
        pygame.mouse.set_visible(True)
    elif "--dev-mission2-game" in args or "--m2-game" in args:
        gc.mission_start_time = _now_ms()
        gc.mission_end_time = 0
        gc.start_mission2(preserve_timer=True)
        gsm.transition("GAME")
        pygame.mouse.set_visible(False)
    elif "--dev-mission2-sniper" in args or "--m2-sniper" in args:
        gc.mission_start_time = _now_ms()
        gc.mission_end_time = 0
        gc.start_mission2_sniper(preserve_timer=True)
        gsm.transition("GAME")
        pygame.mouse.set_visible(False)
    elif "--dev-mission2-after-sniper" in args or "--m2-after-sniper" in args:
        gc.mission_start_time = _now_ms()
        gc.mission_end_time = 0
        gc.start_mission2_after_sniper(preserve_timer=True)
        gsm.transition("GAME")
        pygame.mouse.set_visible(False)
    elif "--dev-mission2-flank" in args or "--m2-flank" in args:
        gc.mission_start_time = _now_ms()
        gc.mission_end_time = 0
        gc.start_mission2_flank(preserve_timer=True)
        gsm.transition("GAME")
        pygame.mouse.set_visible(False)
    elif "--dev-mission2-truck" in args or "--m2-truck" in args:
        gc.mission_start_time = _now_ms()
        gc.mission_end_time = 0
        gc.start_mission2_truck(preserve_timer=True)
        gsm.transition("GAME")
        pygame.mouse.set_visible(False)
    elif "--dev-mission2-evidence" in args or "--m2-evidence" in args:
        gc.mission_start_time = _now_ms()
        gc.mission_end_time = 0
        gc.start_mission2_evidence_debug(preserve_timer=True)
        gsm.transition("GAME")
        pygame.mouse.set_visible(False)
    elif ("--dev-mission3-vostral-cutscene" in args or "--m3-vostral-cutscene" in args
          or "--m3-vostral" in args):
        # Jump directly to the Vostral acquisition cinematic.
        gc.mission_start_time = _now_ms()
        gc.mission_end_time = 0
        try:
            from missions import m3
            m3.start_mission3_archives_checkpoint(preserve_timer=True)
            STATE.enemies = []
            STATE.m3_archives_cleared = True
            STATE.m3_maru_contacted = True
            STATE.m3_vostral_acquired = True
            STATE.request_vostral_pickup_cutscene = False
            if STATE.player:
                vx, vy = m3._vostral_file_pos()
                STATE.player.rect.center = (vx, vy + 88)
            start_cutscene(gc.vostral_pickup_shots, "GAME", use_fades=True)
            gsm.transition("CUTSCENE")
            pygame.mouse.set_visible(True)
        except Exception as _m3_vostral_err:
            print(f"--m3-vostral-cutscene setup failed: {_m3_vostral_err}")
            gc.start_mission3(preserve_timer=True)
            gsm.transition("GAME")
            pygame.mouse.set_visible(False)
    elif ("--dev-mission3-archives-cutscene" in args or "--m3-archives-cutscene" in args
          or "--m3-archive-cutscene" in args):
        # Jump directly to the seamless Comms → Archives transition. Build the
        # real Archives world first because the cutscene renders that live map.
        gc.mission_start_time = _now_ms()
        gc.mission_end_time = 0
        try:
            from missions import m3
            m3.start_mission3_archives_checkpoint(preserve_timer=True)
            STATE.mission3_stage = m3.STAGE_ARCHIVES_TRANSITION
            STATE.mission_phase = "m3_archives_transition"
            STATE.m3_archives_transition_prebuilt = True
            STATE.request_archives_transition_cutscene = False
            start_cutscene(gc.archives_transition_shots, "GAME", use_fades=True)
            gsm.transition("CUTSCENE")
            pygame.mouse.set_visible(True)
        except Exception as _m3_arch_cut_err:
            print(f"--m3-archives-cutscene setup failed: {_m3_arch_cut_err}")
            gc.start_mission3(preserve_timer=True)
            gsm.transition("GAME")
            pygame.mouse.set_visible(False)
    elif ("--dev-mission3-archives" in args or "--m3-archives" in args
          or "--m3-part3" in args or "--dev-m3-part3" in args
          or "--m3-phase4" in args):
        # Skip straight to Mission 3 Phase 4 - Archives Wing.
        gc.mission_start_time = _now_ms()
        gc.mission_end_time = 0
        try:
            from missions import m3
            m3.start_mission3_archives_checkpoint(preserve_timer=True)
        except Exception as _m3_arch_err:
            print(f"--m3-archives setup failed: {_m3_arch_err}")
            gc.start_mission3(preserve_timer=True)
        gsm.transition("GAME")
        pygame.mouse.set_visible(False)
    elif ("--dev-mission3-kill-order" in args or "--m3-kill-order" in args
          or "--m3-part5" in args or "--dev-m3-part5" in args
          or "--m3-phase5" in args):
        # Skip straight to Mission 3 Phase 5 - Kill Order ground floor
        # (Slice 5). Grants the Vostral flag + K-9 loadout + Volkov ally
        # via the checkpoint loader, then enters the phase for real.
        gc.mission_start_time = _now_ms()
        gc.mission_end_time = 0
        try:
            from missions import m3
            m3.start_mission3_kill_order_checkpoint(preserve_timer=True)
        except Exception as _m3_ko_err:
            print(f"--m3-kill-order setup failed: {_m3_ko_err}")
            gc.start_mission3(preserve_timer=True)
        # Dev flag plays the phase-intro cutscene as well (the in-campaign
        # handoff triggers it via STAGE_KO_TRANSITION; checkpoint code paths
        # that need silence clear the flag themselves).
        STATE.request_ko_transition_cutscene = True
        gsm.transition("GAME")
        pygame.mouse.set_visible(False)
    elif ("--dev-mission3-broadcast-transition" in args
          or "--m3-broadcast-transition" in args
          or "--m3-broadcast-cutscene" in args):
        # Jump directly to the Kill Order → Broadcast transition (Slice 5 → 6).
        # Loads the KO world so the exfil staging matches, then plays the
        # transition cutscene; landing continues into the Slice 6 stub.
        gc.mission_start_time = _now_ms()
        gc.mission_end_time = 0
        try:
            from missions import m3
            m3.start_mission3_kill_order_checkpoint(preserve_timer=True)
            STATE.mission3_stage = m3.STAGE_BROADCAST_TRANSITION
            STATE.mission_phase = "m3_broadcast_transition"
            STATE.request_broadcast_transition_cutscene = False
            start_cutscene(gc.broadcast_transition_shots, "GAME", use_fades=True)
            gsm.transition("CUTSCENE")
            pygame.mouse.set_visible(True)
        except Exception as _m3_bcast_cut_err:
            print(f"--m3-broadcast-transition setup failed: {_m3_bcast_cut_err}")
            gc.start_mission3(preserve_timer=True)
            gsm.transition("GAME")
            pygame.mouse.set_visible(False)
    elif ("--dev-mission3-broadcast" in args
          or "--m3-broadcast" in args
          or "--m3-slice6" in args):
        # Jump directly to the Broadcast Wing (Slice 6).
        # Grants the Vostral flag and loadout, builds the broadcast world,
        # and starts the combat gauntlet with a fresh 22:00 timer.
        gc.mission_start_time = _now_ms()
        gc.mission_end_time = 0
        try:
            from missions import m3
            m3.start_mission3_broadcast_checkpoint()
            gsm.transition("GAME")
            pygame.mouse.set_visible(False)
        except Exception as _m3_bcast_err:
            print(f"--m3-broadcast setup failed: {_m3_bcast_err}")
            gc.start_mission3(preserve_timer=True)
            gsm.transition("GAME")
            pygame.mouse.set_visible(False)
    elif ("--dev-mission3-upload" in args
          or "--m3-upload" in args
          or "--m3-upload-os" in args):
        # Skip the whole slice up to the station PC, with the broadcast OS
        # already booted. For working on the PC session itself.
        gc.mission_start_time = _now_ms()
        gc.mission_end_time = 0
        try:
            from missions import m3
            m3.start_mission3_upload_checkpoint()
            gsm.transition("GAME")
            pygame.mouse.set_visible(False)
        except Exception as _m3_up_err:
            print(f"--m3-upload setup failed: {_m3_up_err}")
            gc.start_mission3(preserve_timer=True)
            gsm.transition("GAME")
            pygame.mouse.set_visible(False)
    elif ("--dev-mission3-comms" in args or "--m3-comms" in args
          or "--m3-part2" in args or "--dev-m3-part2" in args):
        # Skip to Mission 3's second playable slice, but still play the
        # service-door -> radio -> comms-wing transition cutscene first.
        gc.mission_start_time = _now_ms()
        gc.mission_end_time = 0
        gc.start_mission3(preserve_timer=True)
        # Give the player the expected end-of-cell-block loadout so the Comms
        # Wing starts like a real continuation, not a fresh interrogation state.
        STATE.mission3_stage = "vent_cutscene"
        STATE.mission_phase = "m3_service_transition"
        STATE.mission3_cell_open = True
        STATE.mission3_chair_broken = True
        STATE.mission3_doorway_blocked = False
        STATE.mission3_cell_block_cleared = True
        STATE.mission3_guards_spawned = True
        STATE.player_disarmed = False
        STATE.mission3_weapon = "k9_smg"
        STATE.current_weapon = "k9_smg"
        STATE.k9_unlocked = True
        STATE.k9_mag_size = 24
        STATE.k9_ammo_in_mag = 24
        STATE.k9_spare_mags = 2
        STATE.request_service_transition_cutscene = False
        STATE.request_vent_cutscene = False
        start_cutscene(gc.service_transition_shots, "GAME", use_fades=True)
        trigger_transition("CUTSCENE")
        pygame.mouse.set_visible(True)
    elif ("--dev-mission3-ledger" in args or "--m3-ledger" in args
          or "--dev-m3-ledger" in args):
        gc.mission_start_time = _now_ms()
        gc.mission_end_time = 0
        try:
            from missions import m3
            m3.start_black_ledger_debug()
        except Exception as _ledger_err:
            print(f"--m3-ledger setup failed: {_ledger_err}")
            gc.start_mission3(preserve_timer=True)
        gsm.transition("GAME")
        pygame.mouse.set_visible(False)
    elif "--dev-mission3" in args or "--m3" in args:
        gc.mission_start_time = _now_ms()
        gc.mission_end_time = 0
        gc.start_mission3(preserve_timer=True)
        start_cutscene(gc.mission3_intro_shots, "GAME", use_fades=True)
        trigger_transition("CUTSCENE")
        pygame.mouse.set_visible(True)
    elif "--dev-audio-parade" in args or "--audio-parade" in args:
        # Audio verification walk: drop into the Comms Wing with verbose sound
        # logging so every triggered sound prints its name. Walk it with
        # headphones and tune volumes by feel.
        gc.mission_start_time = _now_ms()
        gc.mission_end_time = 0
        try:
            from missions import m3
            m3.start_mission3_comms_checkpoint(preserve_timer=True)
        except Exception as _parade_err:
            print(f"--dev-audio-parade setup failed: {_parade_err}")
            gc.start_mission3(preserve_timer=True)
        audio.verbose = True
        gsm.transition("GAME")
        pygame.mouse.set_visible(False)
    elif ("--dev-mission3-game" in args or "--m3-game" in args
          or "--dev-m3-game" in args or "--m3-skip" in args):
        # NEW: skip the Mission 3 intro/breach/interrogation cutscenes and
        # drop straight into playable breakout gameplay (post-Volkov-breach,
        # with the chair leg; you still sharpen the shiv at the drain).
        # Mirrors start_mission3_breakout_checkpoint().
        gc.mission_start_time = _now_ms()
        gc.mission_end_time = 0
        try:
            from missions import m3
            m3.start_mission3_breakout_checkpoint(preserve_timer=True)
        except Exception as _m3_dev_err:
            print(f"--dev-mission3-game setup failed: {_m3_dev_err}")
            gc.start_mission3(preserve_timer=True)
        gsm.transition("GAME")
        pygame.mouse.set_visible(False)
        pygame.mouse.set_visible(True)
    elif ("--dev-mission4" in args or "--m4" in args
          or "--dev-mission4-intro" in args):
        # Mission 4: play the real intro cutscene (m4aftermath art), then
        # chain into STAGE_AFTERMATH gameplay on cutscene end (after=MISSION4).
        gc.mission_start_time = _now_ms()
        gc.mission_end_time = 0
        gc.start_mission4(preserve_timer=True)
        start_cutscene(gc.mission4_intro_shots, "MISSION4", use_fades=True)
        trigger_transition("CUTSCENE")
        pygame.mouse.set_visible(True)
    elif ("--dev-mission4-game" in args or "--m4-game" in args):
        # Skip the intro and drop straight into the curfew-street shell.
        gc.mission_start_time = _now_ms()
        gc.mission_end_time = 0
        try:
            from missions import m4
            m4.start_m4(preserve_timer=True)
        except Exception as _m4_dev_err:
            print(f"--dev-mission4-game setup failed: {_m4_dev_err}")
            gc.start_mission4(preserve_timer=True)
        gsm.transition("GAME")
        pygame.mouse.set_visible(False)
    elif ("--dev-mission4-station" in args or "--m4-station" in args):
        # Radio-station interior checkpoint (liaison meet resume point).
        gc.mission_start_time = _now_ms()
        gc.mission_end_time = 0
        try:
            gc.start_mission4_station_checkpoint(preserve_timer=True)
        except Exception as _m4_st_err:
            print(f"--dev-mission4-station setup failed: {_m4_st_err}")
            gc.start_mission4(preserve_timer=True)
        gsm.transition("GAME")
        pygame.mouse.set_visible(False)
    elif ("--dev-mission4-tower" in args or "--m4-tower" in args):
        # Transmitter hold (siege checkpoint) - deepest M4 resume point.
        gc.mission_start_time = _now_ms()
        gc.mission_end_time = 0
        try:
            gc.start_mission4_tower_checkpoint(preserve_timer=True)
        except Exception as _m4_tw_err:
            print(f"--dev-mission4-tower setup failed: {_m4_tw_err}")
            gc.start_mission4(preserve_timer=True)
        gsm.transition("GAME")
        pygame.mouse.set_visible(False)
    elif "--dev-mission0" in args or "--m0" in args:
        gc.mission_start_time = _now_ms()
        gc.mission_end_time = 0
        gc.start_mission0(preserve_timer=True)
        gsm.transition("GAME")
        pygame.mouse.set_visible(False)
    elif ("--dev-mission5" in args or "--m5" in args
          or "--dev-mission5-intro" in args):
        # Mission 5: play the martial-law bulletin chain, then drop into the
        # Guard HQ walk on cutscene end (after=MISSION5).
        gc.mission_start_time = _now_ms()
        gc.mission_end_time = 0
        gc.start_mission5(preserve_timer=True)
        start_cutscene(gc.mission5_intro_shots, "MISSION5", use_fades=True)
        trigger_transition("CUTSCENE")
        pygame.mouse.set_visible(True)
    elif ("--dev-mission5-hq" in args or "--m5-hq" in args):
        # Guard HQ walking sim (phase 2) - squadmates, Vasile's office.
        gc.mission_start_time = _now_ms()
        gc.mission_end_time = 0
        try:
            gc.start_mission5_hq_checkpoint(preserve_timer=True)
        except Exception as _m5_hq_err:
            print(f"--dev-mission5-hq setup failed: {_m5_hq_err}")
            gc.start_mission5(preserve_timer=True)
        gsm.transition("GAME")
        pygame.mouse.set_visible(False)
    elif ("--dev-mission5-game" in args or "--m5-game" in args):
        # Skip the bulletin + HQ and drop straight onto the curfew avenue.
        gc.mission_start_time = _now_ms()
        gc.mission_end_time = 0
        try:
            gc.start_mission5_quarter_checkpoint(preserve_timer=True)
        except Exception as _m5_dev_err:
            print(f"--dev-mission5-game setup failed: {_m5_dev_err}")
            gc.start_mission5(preserve_timer=True)
        gsm.transition("GAME")
        pygame.mouse.set_visible(False)
    elif ("--dev-mission5-printworks" in args or "--m5-printworks" in args):
        # MAG print works interior - find Maru, then the Guard raid.
        gc.mission_start_time = _now_ms()
        gc.mission_end_time = 0
        try:
            gc.start_mission5_printworks_checkpoint(preserve_timer=True)
        except Exception as _m5_pw_err:
            print(f"--dev-mission5-printworks setup failed: {_m5_pw_err}")
            gc.start_mission5(preserve_timer=True)
        gsm.transition("GAME")
        pygame.mouse.set_visible(False)
    elif ("--dev-mission5-tunnel" in args or "--m5-tunnel" in args):
        # Basement tunnel escort - deepest M5 resume point.
        gc.mission_start_time = _now_ms()
        gc.mission_end_time = 0
        try:
            gc.start_mission5_tunnel_checkpoint(preserve_timer=True)
        except Exception as _m5_tn_err:
            print(f"--dev-mission5-tunnel setup failed: {_m5_tn_err}")
            gc.start_mission5(preserve_timer=True)
        gsm.transition("GAME")
        pygame.mouse.set_visible(False)
    elif ("--dev-mission5-ending" in args or "--m5-ending" in args
          or "--dev-m5-ending" in args):
        # Mission 5 finale - shadow standoff at the river. Builds the tunnel
        # world first (save marker / outfit / Maru state) then plays the
        # ending cutscene straight to MISSION_COMPLETE.
        gc.mission_start_time = _now_ms()
        gc.mission_end_time = 0
        try:
            gc.start_mission5_tunnel_checkpoint(preserve_timer=True)
        except Exception as _m5_end_err:
            print(f"--dev-mission5-ending setup failed: {_m5_end_err}")
            gc.start_mission5(preserve_timer=True)
        start_cutscene(gc.mission5_ending_shots, "MISSION5_COMPLETE", use_fades=True)
        trigger_transition("CUTSCENE")
        pygame.mouse.set_visible(True)
    elif "--dev-slot-select" in args:
        # Dev/screenshot jump: open the save-slot screen directly (skips
        # BOOT_INTRO). Pass `--continue` as well for the CONTINUE variant -
        # tools/slot_select_shot.py captures both.
        slot_select_purpose = "continue" if "--continue" in args else "new"
        gsm.transition("SLOT_SELECT")
        pygame.mouse.set_visible(True)
    elif "--dev-mp-host" in args or "--dev-mp-join" in args:
        # Multiplayer arena duo (tools/mp_arena_duo.py): boot straight onto
        # the MULTIPLAYER browser with the arena panel raised, already
        # hosting or joining - no menu clicks needed.
        _mp_map = _dev_flag_value(raw, "--mp-map", "yard") or "yard"
        _mp_players = 2
        try:
            _mp_players = max(2, min(8, int(
                _dev_flag_value(raw, "--mp-players", "2") or "2")))
        except (TypeError, ValueError):
            pass
        if _mp_map:
            _match_screen.map_name = _mp_map
        _match_screen.players = _mp_players
        gsm.transition("MULTIPLAYER")
        pygame.mouse.set_visible(True)
        _match_screen.open_panel()
        if "--dev-mp-host" in args:
            _mp_port = 27017
            try:
                _mp_port = int(
                    _dev_flag_value(raw, "--mp-port", "27017") or "27017")
            except (TypeError, ValueError):
                pass
            _match_screen.request_host(_mp_port)
        else:
            _mp_addr = (_dev_flag_value(raw, "--mp-join", "") or "").strip()
            if _mp_addr:
                _match_screen.request_join(_mp_addr)
    # Trailer bot flags (AI 1). Gated, off by default, never affects play.
    # Standalone `if` (not elif) so it composes with any --jump target above.
    if "--trailer-bot" in args:
        # lazy: tools.trailer_bot owns _BOT_* state
        from tools import trailer_bot as _bot
        _bot.set_active(True)
        _act = "act1"
        for _i, _a in enumerate(raw):
            if _a == "--trailer-act" and _i + 1 < len(raw):
                _act = raw[_i + 1]
            if _a.startswith("--trailer-act="):
                _act = _a.split("=", 1)[1]
        _bot.reset(_act)


# ═══════════════════════════════════════════════
# FSM STATE CLASSES - FULLY MIGRATED
# ═══════════════════════════════════════════════

class _BootIntroState(GameState):
    name = "BOOT_INTRO"

    # Clean animated-logo-only studio bumper.
    DURATION = 330      # ~5.5s @ 60fps
    FADE_IN = 42
    HOLD_END = 255
    FADE_OUT = 75

    def enter(self):
        self.timer = 0
        self._skip_requested = False
        pygame.mouse.set_visible(False)
        try:
            audio.play("terminal_beep", volume=0.20)
        except Exception:
            pass

    def handle_event(self, event, mouse_x, mouse_y, keys):
        if event.type == pygame.KEYDOWN and event.key in (
                pygame.K_SPACE, pygame.K_RETURN, pygame.K_ESCAPE):
            self._skip_requested = True
            return True
        if event.type == pygame.MOUSEBUTTONDOWN:
            self._skip_requested = True
            return True
        return False

    def update(self, dt):
        self.timer += 1
        if self._skip_requested or self.timer >= self.DURATION:
            gsm.transition("ENGINE_INTRO")
            # cursor: the engine bumper keeps it hidden and restores it
            # on the way to MENU (see _EngineIntroState).

    def set_ambience(self):
        _set_ambience(set())

    def _alpha(self):
        if self.timer < self.FADE_IN:
            return int(255 * (self.timer / self.FADE_IN))
        if self.timer > self.HOLD_END:
            return int(255 * max(0.0, 1.0 - ((self.timer - self.HOLD_END) / self.FADE_OUT)))
        return 255

    @staticmethod
    def _smooth(v):
        v = max(0.0, min(1.0, v))
        return v * v * (3.0 - 2.0 * v)

    def _draw_retardovici_r_logo(self, surface, cx, cy, t, alpha):
        """Stylized single-R monogram inspired by the studio mark.

        Important: this is NOT RI. It is one heavy R with a triangular negative
        cut and diagonal lower stroke, matching the user's clarification while
        still being original/procedural.
        """
        build = self._smooth((t - 34) / 74.0)
        a = int(alpha * build)
        if a <= 0:
            return

        gx = gy = 0
        if 62 <= t <= 92 and t % 5 in (0, 1):
            rng = random.Random(4000 + t)
            gx = rng.randint(-5, 5)
            gy = rng.randint(-2, 2)

        logo = pygame.Surface((360, 270), pygame.SRCALPHA)
        dark = (232, 238, 235, a)
        red = (168, 28, 24, int(a * 0.95))

        # Construction grid fades as the R finishes stamping in.
        grid_a = int(a * max(0.0, 1.0 - build) * 0.50)
        if grid_a > 0:
            for x in range(48, 314, 28):
                pygame.draw.line(logo, (130, 150, 156, grid_a), (x, 34), (x, 226), 1)
            for y in range(38, 226, 28):
                pygame.draw.line(logo, (130, 150, 156, grid_a), (42, y), (318, y), 1)

        p1 = self._smooth((t - 34) / 32.0)   # stem
        p2 = self._smooth((t - 54) / 38.0)   # bowl
        p3 = self._smooth((t - 78) / 36.0)   # leg/cut
        p4 = self._smooth((t - 112) / 28.0)  # slash accent/frame

        # Draw main R on a mask so we can punch the triangular cutout.
        mask = pygame.Surface((360, 270), pygame.SRCALPHA)

        # Thick left stem.
        stem_h = int(174 * p1)
        pygame.draw.rect(mask, dark, (72, 42 + (174 - stem_h), 48, stem_h))

        # Upper R bowl: blocky top bar + rounded right shoulder + middle bar.
        pygame.draw.rect(mask, dark, (112, 42, int(128 * p2), 42))
        if p2 > 0:
            pygame.draw.rect(mask, dark, (200, 74, int(52 * p2), 66), border_radius=26)
            pygame.draw.rect(mask, dark, (112, 116, int(112 * p2), 34))
            # Fill interior left of rounded shoulder to make it read as a bowl.
            pygame.draw.rect(mask, dark, (166, 76, int(54 * p2), 58))

        # Diagonal lower leg of the R.
        if p3 > 0:
            leg = pygame.Surface((360, 270), pygame.SRCALPHA)
            pygame.draw.polygon(leg, dark, [(112, 142), (166, 142), (256, 222), (196, 222)])
            mask.blit(leg, (0, 0), area=pygame.Rect(0, 0, int(360 * p3), 270))

        # Negative cut: keep it as a sharp diagonal bite inside the R, not a
        # big centered triangle that reads like a separate "A" symbol.
        if p3 > 0:
            cut = pygame.Surface((360, 270), pygame.SRCALPHA)
            # Narrow internal wedge aligned to the lower R leg.
            pygame.draw.polygon(cut, (0, 0, 0, int(255 * p3)), [
                (148, 210), (178, 150), (196, 166), (174, 210)
            ])
            mask.blit(cut, (0, 0), special_flags=pygame.BLEND_RGBA_SUB)
            # Left diagonal bite, also slimmer and less triangle-like.
            bite = pygame.Surface((360, 270), pygame.SRCALPHA)
            pygame.draw.polygon(bite, (0, 0, 0, int(255 * p3)), [
                (82, 224), (154, 112), (166, 122), (102, 224)
            ])
            mask.blit(bite, (0, 0), special_flags=pygame.BLEND_RGBA_SUB)

        logo.blit(mask, (0, 0))

        # Red diagonal accent, separate from the negative cut.
        if p4 > 0:
            slash = pygame.Surface((360, 270), pygame.SRCALPHA)
            pygame.draw.polygon(slash, red, [(52, 232), (142, 94), (158, 104), (82, 242)])
            slash.set_alpha(int(a * p4))
            logo.blit(slash, (0, 0))

        # Frame brackets.
        frame_p = self._smooth((t - 118) / 34.0)
        if frame_p > 0:
            fa = int(a * frame_p * 0.75)
            l = int(58 * frame_p)
            for sx, sy, dx, dy in [(48, 36, 1, 0), (48, 36, 0, 1), (312, 36, -1, 0), (312, 36, 0, 1),
                                   (48, 232, 1, 0), (48, 232, 0, -1), (312, 232, -1, 0), (312, 232, 0, -1)]:
                pygame.draw.line(logo, (142, 34, 30, fa), (sx, sy), (sx + dx * l, sy + dy * l), 2)

        # Subtle distress scratches.
        rng = random.Random(7701)
        for _ in range(12):
            x = rng.randint(70, 270); y = rng.randint(50, 220)
            pygame.draw.line(logo, (0, 0, 0, int(a * 0.20)), (x, y), (x + rng.randint(10, 30), y + rng.randint(-2, 2)), 2)

        glow = logo.copy()
        glow.fill((160, 20, 16, int(a * 0.18)), special_flags=pygame.BLEND_RGBA_MULT)
        surface.blit(glow, (cx - 180 + gx + 5, cy - 135 + gy + 6), special_flags=pygame.BLEND_ADD)
        shadow = logo.copy()
        shadow.fill((0, 0, 0, int(a * 0.8)), special_flags=pygame.BLEND_RGBA_MULT)
        surface.blit(shadow, (cx - 180 + gx + 4, cy - 135 + gy + 5))
        surface.blit(logo, (cx - 180 + gx, cy - 135 + gy))


    def render(self, surface):
        t = self.timer
        a = self._alpha()

        # Clean dark background with subtle red studio glow.
        surface.fill((2, 3, 5))
        for y in range(0, HEIGHT, 3):
            p = y / HEIGHT
            shade = int(5 + 12 * (1.0 - abs(p - 0.52)))
            pygame.draw.rect(surface, (shade, shade + 1, shade + 3), (0, y, WIDTH, 3))

        glow = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        pulse = 0.5 + 0.5 * math.sin(t * 0.04)
        for r, ga in ((420, 18), (260, 30), (140, 42)):
            pygame.draw.circle(glow, (120, 16, 13, int(ga * (0.8 + pulse * 0.25))),
                               (WIDTH // 2, HEIGHT // 2 - 50), r)
        surface.blit(glow, (0, 0), special_flags=pygame.BLEND_ADD)

        # Minimal scanline/noise texture.
        rng = random.Random(3000 + t // 6)
        for _ in range(22):
            x = rng.randrange(0, WIDTH)
            y = rng.randrange(0, HEIGHT)
            pygame.draw.rect(surface, rng.choice([(10, 12, 16), (18, 7, 7), (4, 5, 8)]),
                             (x, y, rng.randrange(14, 80), 1))
        for y in range(0, HEIGHT, 4):
            pygame.draw.line(surface, (0, 0, 0), (0, y), (WIDTH, y))

        # Tiny boot labels, intentionally understated.
        label_a = int(a * self._smooth((t - 18) / 34.0) * 0.55)
        boot = font_terminal_small.render(_T("app.retardovici_inc_studio_ident"), True, (90, 104, 110))
        boot.set_alpha(label_a)
        surface.blit(boot, (56, 54))
        pygame.draw.line(surface, (70, 26, 24), (52, 48), (220, 48), 1)
        pygame.draw.line(surface, (70, 26, 24), (WIDTH - 220, 48), (WIDTH - 52, 48), 1)

        self._draw_retardovici_r_logo(surface, WIDTH // 2, HEIGHT // 2 - 70, t, a)

        # Wordmark.
        name_p = self._smooth((t - 138) / 50.0)
        name_alpha = int(a * name_p)
        title = font_title.render(_T("app.retardovici"), True, (232, 238, 235))
        title = pygame.transform.smoothscale(title, (int(title.get_width() * 0.78), int(title.get_height() * 0.78)))
        title.set_alpha(name_alpha)
        x = WIDTH // 2 - title.get_width() // 2
        y = HEIGHT // 2 + 92
        sh = title.copy()
        sh.fill((0, 0, 0, min(235, name_alpha)), special_flags=pygame.BLEND_RGBA_MULT)
        surface.blit(sh, (x + 4, y + 4))
        surface.blit(title, (x, y))

        inc = font_terminal.render(_T("app.i_n_c"), True, (206, 214, 210))
        inc.set_alpha(name_alpha)
        ix = WIDTH // 2 - inc.get_width() // 2
        iy = y + 66
        ish = font_terminal.render(_T("app.i_n_c"), True, (0, 0, 0))
        ish.set_alpha(min(220, name_alpha))
        surface.blit(ish, (ix + 3, iy + 3))
        surface.blit(inc, (ix, iy))

        # Presents strip.
        strip_p = self._smooth((t - 190) / 42.0)
        if strip_p > 0:
            strip_w = int(420 * strip_p)
            strip = pygame.Surface((strip_w, 26), pygame.SRCALPHA)
            strip.fill((8, 5, 4, int(132 * strip_p)))
            pygame.draw.rect(strip, (130, 30, 24, int(160 * strip_p)), strip.get_rect(), 1)
            txt = font_terminal_small.render(_T("app.presents"), True, (150, 116, 84))
            txt.set_alpha(int(a * strip_p))
            strip.blit(txt, (strip_w // 2 - txt.get_width() // 2, 7))
            surface.blit(strip, (WIDTH // 2 - strip_w // 2, HEIGHT // 2 + 214))

        # Small reveal glitch only, not persistent clutter.
        if 82 < t < 104 and t % 5 in (0, 1):
            gr = pygame.Surface((WIDTH, 20), pygame.SRCALPHA)
            gr.fill((170, 28, 24, 42))
            surface.blit(gr, (_rng_legacy.randint(-10, 10), HEIGHT // 2 + _rng_legacy.randint(-84, 84)))

        if t > 205 and (_now_ms() // 700) % 2 == 0:
            hint = font_terminal_small.render(_T("app.space_enter_to_skip"), True, (82, 76, 66))
            hint.set_alpha(min(a, 96))
            surface.blit(hint, (WIDTH // 2 - hint.get_width() // 2, HEIGHT - 48))

        if a < 255:
            fade = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
            fade.fill((0, 0, 0, 255 - a))
            surface.blit(fade, (0, 0))



class _EngineIntroState(GameState):
    name = "ENGINE_INTRO"

    # Engine bumper (RPE6): a pulse trace sweeps across a dark scope,
    # the wordmark lands as the trace completes. Plays after the studio
    # ident (_BootIntroState), before the menu; skippable like it.
    DURATION = 216      # ~3.6s @ 60fps
    FADE_IN = 26
    HOLD_END = 168
    FADE_OUT = 48

    def enter(self):
        self.timer = 0
        self._skip_requested = False
        self._beat_played = False
        pygame.mouse.set_visible(False)

    def handle_event(self, event, mouse_x, mouse_y, keys):
        if event.type == pygame.KEYDOWN and event.key in (
                pygame.K_SPACE, pygame.K_RETURN, pygame.K_ESCAPE):
            self._skip_requested = True
            return True
        if event.type == pygame.MOUSEBUTTONDOWN:
            self._skip_requested = True
            return True
        return False

    def update(self, dt):
        self.timer += 1
        if self.timer == 62 and not self._beat_played:
            self._beat_played = True
            try:
                audio.play("heartbeat", volume=0.32)
            except Exception:
                pass
        if self._skip_requested or self.timer >= self.DURATION:
            gsm.transition("MENU")
            pygame.mouse.set_visible(True)

    def set_ambience(self):
        _set_ambience(set())

    def _alpha(self):
        if self.timer < self.FADE_IN:
            return int(255 * (self.timer / self.FADE_IN))
        if self.timer > self.HOLD_END:
            return int(255 * max(0.0, 1.0 - ((self.timer - self.HOLD_END) / self.FADE_OUT)))
        return 255

    @staticmethod
    def _smooth(v):
        v = max(0.0, min(1.0, v))
        return v * v * (3.0 - 2.0 * v)

    @staticmethod
    def _wave(u):
        """One ECG beat (u in 0..1): P bump, QRS spike, T bump."""
        def g(c, w, amp):
            d = (u - c) / w
            return amp * math.exp(-d * d)
        return (g(0.16, 0.030, 0.14) + g(0.315, 0.010, -0.12)
                + g(0.35, 0.013, 1.0) + g(0.395, 0.014, -0.24)
                + g(0.55, 0.042, 0.18))

    def render(self, surface):
        t = self.timer
        a = self._alpha()

        surface.fill((3, 4, 6))
        for y in range(0, HEIGHT, 4):
            pygame.draw.line(surface, (0, 0, 0), (0, y), (WIDTH, y))

        cx, cy = WIDTH // 2, HEIGHT // 2 - 46

        # Scope grid + baseline.
        for gx in range(cx - 330, cx + 331, 30):
            pygame.draw.line(surface, (10, 15, 17), (gx, cy - 108), (gx, cy + 108))
        for gy in range(cy - 90, cy + 91, 30):
            pygame.draw.line(surface, (10, 15, 17), (cx - 330, gy), (cx + 330, gy))
        pygame.draw.line(surface, (24, 31, 33), (cx - 330, cy), (cx + 330, cy))

        # Understated corner label, mirrored on the studio ident.
        label_a = int(a * self._smooth((t - 14) / 30.0) * 0.55)
        boot = font_terminal_small.render(_T("app.engine_ident"), True, (104, 110, 96))
        boot.set_alpha(label_a)
        surface.blit(boot, (56, 54))
        pygame.draw.line(surface, (86, 64, 26), (52, 48), (220, 48), 1)
        pygame.draw.line(surface, (86, 64, 26), (WIDTH - 220, 48), (WIDTH - 52, 48), 1)

        # Pulse trace: a pen sweeps the scope, two beats wide, the
        # segment right behind the pen burning brighter.
        sweep = self._smooth((t - 24) / 118.0)
        pen = cx - 340 + 680 * sweep
        pts = []
        x = cx - 340
        while x <= pen:
            u = ((x - (cx - 340)) / 340.0) % 1.0
            pts.append((x, cy - self._wave(u) * 92))
            x += 4
        if len(pts) > 2:
            pygame.draw.lines(surface, (92, 62, 18), False, pts, 7)
            pygame.draw.lines(surface, (238, 186, 84), False, pts, 3)
            hx, hy = pts[-1]
            pygame.draw.circle(surface, (120, 84, 24), (int(hx), int(hy)), 9)
            pygame.draw.circle(surface, (255, 214, 120), (int(hx), int(hy)), 4)

        # Wordmark lands as the sweep completes.
        name_p = self._smooth((t - 118) / 28.0)
        name_alpha = int(a * name_p)
        if name_alpha > 0:
            powered = font_terminal_small.render(_T("app.powered_by"), True, (148, 138, 116))
            powered.set_alpha(int(name_alpha * 0.8))
            surface.blit(powered, (cx - powered.get_width() // 2, cy + 72))

            title = font_title.render(_T("app.engine_name"), True, (236, 238, 234))
            title = pygame.transform.smoothscale(
                title, (int(title.get_width() * 0.78), int(title.get_height() * 0.78)))
            title.set_alpha(name_alpha)
            sh = title.copy()
            sh.fill((0, 0, 0, min(235, name_alpha)), special_flags=pygame.BLEND_RGBA_MULT)
            surface.blit(sh, (cx - title.get_width() // 2 + 4, cy + 100))
            surface.blit(title, (cx - title.get_width() // 2, cy + 96))

            gold = font_terminal.render(_T("app.engine_gold"), True, (238, 186, 84))
            gold.set_alpha(name_alpha)
            surface.blit(gold, (cx - gold.get_width() // 2, cy + 168))

        if t > 150 and (_now_ms() // 700) % 2 == 0:
            hint = font_terminal_small.render(_T("app.space_enter_to_skip"), True, (82, 80, 70))
            hint.set_alpha(min(a, 96))
            surface.blit(hint, (WIDTH // 2 - hint.get_width() // 2, HEIGHT - 48))

        if a < 255:
            fade = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
            fade.fill((0, 0, 0, 255 - a))
            surface.blit(fade, (0, 0))


class _MenuState(GameState):
    name = "MENU"

    def enter(self):
        global menu_notice_timer
        menu_notice_timer = 0
        # back at the main menu: nothing from the mission may keep playing
        # (VO, death screams, sniper-film cues, alarms, loops)
        if gsm.previous_name not in ("", "SLOT_SELECT", "SETTINGS", "SHOP", "MULTIPLAYER", "MENU"):
            audio.hard_stop()

    def handle_event(self, event, mouse_x, mouse_y, keys):
        if event.type == pygame.KEYDOWN:
            menu.handle_menu_keydown(event)
        if menu.buttons[0].is_clicked(event, (mouse_x, mouse_y)) and save_system.has_any_save():
            global slot_select_purpose
            slot_select_purpose = "continue"
            gsm.transition("SLOT_SELECT")
        if menu.buttons[1].is_clicked(event, (mouse_x, mouse_y)):
            slot_select_purpose = "new"
            gsm.transition("SLOT_SELECT")
        if menu.buttons[2].is_clicked(event, (mouse_x, mouse_y)):
            global mp_state, mp_selected, mp_kick_msg
            mp_state = "browser"
            mp_selected = -1
            mp_kick_msg = ""
            gsm.transition("MULTIPLAYER")
        if menu.buttons[3].is_clicked(event, (mouse_x, mouse_y)):
            global _settings_return_to
            _settings_return_to = "MENU"
            gsm.transition("SETTINGS")
        if menu.buttons[4].is_clicked(event, (mouse_x, mouse_y)):
            global running
            running = False

    def update(self, dt):
        pass

    def set_ambience(self):
        _set_ambience(set())

    def render(self, surface):
        global menu_notice_timer, menu_notice
        menu.draw_menu()
        kb_trigger = menu.consume_keyboard_trigger()
        global slot_select_purpose, mp_state, mp_selected, mp_kick_msg, _settings_return_to, running
        if kb_trigger == 0 and save_system.has_any_save():
            slot_select_purpose = "continue"
            gsm.transition("SLOT_SELECT")
        elif kb_trigger == 1:
            slot_select_purpose = "new"
            gsm.transition("SLOT_SELECT")
        elif kb_trigger == 2:
            mp_state = "browser"
            mp_selected = -1
            mp_kick_msg = ""
            gsm.transition("MULTIPLAYER")
        elif kb_trigger == 3:
            _settings_return_to = "MENU"
            gsm.transition("SETTINGS")
        elif kb_trigger == 4:
            running = False
        if menu_notice_timer > 0:
            notice = font_prompt.render(menu_notice, True, C_ORANGE)
            bg = pygame.Surface((notice.get_width() + 28, notice.get_height() + 12), pygame.SRCALPHA)
            bg.fill((0, 0, 0, 190))
            pygame.draw.rect(bg, (120, 70, 20), bg.get_rect(), 1)
            surface.blit(bg, (WIDTH // 2 - bg.get_width() // 2, HEIGHT - 120))
            surface.blit(notice, (WIDTH // 2 - notice.get_width() // 2, HEIGHT - 114))
            menu_notice_timer -= 1


class _SlotSelectState(GameState):
    name = "SLOT_SELECT"

    def enter(self):
        global _slot_focus
        _slot_focus = save_system.current_slot_index()

    def _activate_slot(self, i):
        """Shared click/keyboard activation for slot index *i*."""
        global slot_select_purpose, menu_notice, menu_notice_timer
        data = save_system.load_data()
        if slot_select_purpose == "continue" and not data["slots"][i].get("occupied"):
            # Locked empty slot in Continue mode - audible + visible deny.
            audio.play("menu_click", volume=0.25)
            menu_notice = "EMPTY SLOT - NO DATA"
            menu_notice_timer = 120
            return
        save_system.select_slot(i)
        audio.play("menu_click", volume=0.5)
        if slot_select_purpose == "new":
            save_system.start_new_campaign(i)
            gc.mission_start_time = _now_ms()
            gc.mission_end_time = 0
            start_cutscene(gc.cutscene1_shots, "WALK", use_fades=False)
            trigger_transition("CUTSCENE")
        else:
            slot = save_system.get_slot(i)
            last = slot.get("last_completed_mission", "")
            progress = slot.get("progress", "")
            if last == "MISSION_1":
                gc.mission_start_time = _now_ms()
                gc.mission_end_time = 0
                start_cutscene(gc.mission2_intro_shots, "MISSION2", use_fades=False)
                trigger_transition("CUTSCENE")
            elif last == "MISSION_2":
                gc.mission_start_time = _now_ms()
                gc.mission_end_time = 0
                gc.start_mission3(preserve_timer=True)
                gsm.transition("GAME")
                pygame.mouse.set_visible(False)
            elif last == "MISSION_3":
                # M3 done → Mission 4 is the next chapter (was the campaign-
                # complete notice until M4 landed). Resume at the deepest M4
                # checkpoint reached, mirroring the in-progress branch below.
                gc.mission_start_time = _now_ms()
                gc.mission_end_time = 0
                gc.start_mission4(preserve_timer=True)
                gsm.transition("GAME")
                pygame.mouse.set_visible(False)
            elif last == "MISSION_4":
                # M4 done → Mission 5 is the next chapter (was the campaign-
                # complete notice until M5 landed). Play the bulletin chain;
                # its after_state="MISSION5" path drops into the Lower Quarter.
                gc.mission_start_time = _now_ms()
                gc.mission_end_time = 0
                gc.start_mission5(preserve_timer=True)
                start_cutscene(gc.mission5_intro_shots, "MISSION5", use_fades=True)
                trigger_transition("CUTSCENE")
            elif last == "MISSION_5":
                menu_notice = "FULL CAMPAIGN COMPLETE - START A NEW CAMPAIGN"
                menu_notice_timer = 200
                gsm.transition("MENU")
            elif progress == "m5":
                # Mid-M5 save: resume at the tunnel escort if it was reached,
                # else the print works, else the Lower Quarter.
                gc.mission_start_time = _now_ms()
                gc.mission_end_time = 0
                if getattr(STATE, "mission5_tunnel_checkpoint_reached", False):
                    gc.start_mission5_tunnel_checkpoint(preserve_timer=True)
                elif getattr(STATE, "mission5_printworks_checkpoint_reached", False):
                    gc.start_mission5_printworks_checkpoint(preserve_timer=True)
                elif getattr(STATE, "mission5_quarter_checkpoint_reached", False):
                    gc.start_mission5_quarter_checkpoint(preserve_timer=True)
                else:
                    gc.start_mission5(preserve_timer=True)
                gsm.transition("GAME")
                pygame.mouse.set_visible(False)
            elif progress == "m4":
                # Mid-M4 save: resume at the transmitter hold if it was
                # reached, else the station interior, else the street.
                gc.mission_start_time = _now_ms()
                gc.mission_end_time = 0
                if getattr(STATE, "mission4_tower_checkpoint_reached", False):
                    gc.start_mission4_tower_checkpoint(preserve_timer=True)
                elif getattr(STATE, "mission4_station_checkpoint_reached", False):
                    gc.start_mission4_station_checkpoint(preserve_timer=True)
                else:
                    gc.start_mission4(preserve_timer=True)
                gsm.transition("GAME")
                pygame.mouse.set_visible(False)
            elif progress == "m1":
                # Resume Mission 1 gameplay where the player left off.
                gc.start_mission()
                trigger_transition("GAME")
                pygame.mouse.set_visible(False)
            else:
                # In-progress / unknown → resume at the walking sim
                # (skip the opening cutscene the player already saw).
                gc.mission_start_time = _now_ms()
                gc.mission_end_time = 0
                gc.start_walking_sim()
                trigger_transition("WALK")
                pygame.mouse.set_visible(True)

    def handle_event(self, event, mouse_x, mouse_y, keys):
        global _slot_focus
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                gsm.transition("MENU")
                return
            # Keyboard navigation: arrows/WASD move, 1-3 direct, Enter/Space confirm.
            if event.key in (pygame.K_LEFT, pygame.K_a):
                _slot_focus = (_slot_focus - 1) % 3
                audio.play("menu_hover", volume=0.25)
                return
            if event.key in (pygame.K_RIGHT, pygame.K_d):
                _slot_focus = (_slot_focus + 1) % 3
                audio.play("menu_hover", volume=0.25)
                return
            direct = {pygame.K_1: 0, pygame.K_2: 1, pygame.K_3: 2,
                      pygame.K_KP1: 0, pygame.K_KP2: 1, pygame.K_KP3: 2}
            if event.key in direct:
                _slot_focus = direct[event.key]
                audio.play("menu_hover", volume=0.25)
                return
            if event.key in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_SPACE):
                self._activate_slot(_slot_focus)
                return
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            for i, rect in enumerate(_slot_rects):
                if rect.collidepoint(mouse_x, mouse_y):
                    self._activate_slot(i)
                    break

    def update(self, dt):
        pass

    def set_ambience(self):
        _set_ambience(set())

    def render(self, surface):
        draw_slot_select_screen()


class _MultiplayerState(GameState):
    name = "MULTIPLAYER"

    def handle_event(self, event, mouse_x, mouse_y, keys):
        global mp_state, mp_selected, mp_kick_msg, mp_timer, _shop_return_to
        # While the match screen is up it consumes input first. During a
        # live match it deliberately does NOT consume: gameplay keys must
        # fall through to the match's own per-frame input, which reads the
        # key state rather than events.
        if _match_screen.mode in ("panel", "hosting", "playing"):
            _match_screen.handle_event(event, (mouse_x, mouse_y))
            if _match_screen.mode == "closed":
                mp_state = "browser"
                mp_selected = -1
            return
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1 \
                and menu.enter_arena_hit(get_scaled_mouse()):
            _match_screen.open_panel()
            mp_state = "browser"
            return
        if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            if mp_state == "kicked":
                mp_state = "browser"
                mp_kick_msg = ""
                mp_selected = -1
            elif menu._dm_open_user is not None:
                menu.close_dm()
            else:
                gsm.transition("MENU")
        # Address box first: when it has focus it owns every key, so a typed
        # address can never leak into the chat composer or the DM input.
        if event.type == pygame.KEYDOWN:
            if menu.direct_connect_key(event):
                return
        # Global chat composer: claim the key first when a live relay is up,
        # so typed characters never leak into the DM input below.
        if event.type == pygame.KEYDOWN:
            if menu.relay_chat_key(event):
                return
        if event.type == pygame.MOUSEWHEEL and mp_state == "browser":
            if menu._mp_tab == "SERVERS":
                menu.scroll_server_list(-event.y)
            elif menu._mp_tab == "CONNECTIONS":
                menu.scroll_dm_list(-event.y)
        if mp_state == "browser":
            if menu._mp_tab == "CONNECTIONS" and menu._dm_open_user is not None:
                if event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_RETURN:
                        menu.send_dm_message()
                    elif event.key == pygame.K_BACKSPACE:
                        menu_mp._dm_input = menu_mp._dm_input[:-1]
                    elif event.key == pygame.K_v and (
                            event.mod & (pygame.KMOD_CTRL | pygame.KMOD_META)):
                        paste = menu.clipboard_text(200 - len(menu_mp._dm_input))
                        if paste:
                            menu_mp._dm_input += paste
                    elif event.unicode and event.unicode.isprintable() and len(menu_mp._dm_input) < 200:
                        menu_mp._dm_input += event.unicode
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                menu.server_back_btn.is_hovered = False
                if menu.server_back_btn.rect.collidepoint(get_scaled_mouse()):
                    gsm.transition("MENU")
                elif menu.connect_bar_click(get_scaled_mouse()):
                    pass
                elif menu.servers_tab_rect.collidepoint(get_scaled_mouse()):
                    menu.switch_mp_tab("SERVERS")
                elif menu.connections_tab_rect.collidepoint(get_scaled_mouse()):
                    menu.switch_mp_tab("CONNECTIONS")
                elif menu.outfitter_btn_rect.collidepoint(get_scaled_mouse()):
                    # Back returns here rather than to the main menu, so a
                    # player who just checked their balance is not made to walk
                    # the whole way back to a match.
                    _shop_return_to = "MULTIPLAYER"
                    _shop_screen.open_panel("MULTIPLAYER")
                    gsm.transition("SHOP")
                elif menu._mp_tab == "SERVERS":
                    if menu.refresh_btn_rect.collidepoint(get_scaled_mouse()):
                        menu.trigger_server_refresh()
                    else:
                        mp_scaled = get_scaled_mouse()
                        for i, _lines, row_h, ry in menu.server_row_layouts():
                            row_rect = pygame.Rect(
                                menu.SERVER_ROW_X,
                                ry,
                                menu.SERVER_ROW_W,
                                row_h - 4,
                            )
                            if row_rect.collidepoint(mp_scaled):
                                mp_selected = i
                                mp_state = "connecting"
                                mp_timer = 180
                                break
                elif menu._mp_tab == "CONNECTIONS":
                    list_x = menu.CONTACTS_X
                    list_y = menu.CONTACTS_Y
                    list_w = menu.CONTACTS_W
                    row_h = menu.CONNECTIONS_ROW_H
                    visible_friends = (menu.SERVER_LIST_LIMIT - list_y) // row_h
                    visible_friends = min(visible_friends, len(menu.CONNECTIONS))
                    mp_scaled = get_scaled_mouse()
                    for vi in range(visible_friends):
                        i = vi + menu._dm_scroll_offset
                        if i >= len(menu.CONNECTIONS):
                            break
                        ry = list_y + vi * row_h
                        row_rect = pygame.Rect(list_x, ry, list_w, row_h - 4)
                        if row_rect.collidepoint(mp_scaled):
                            menu.open_dm(i)
                            break
        elif mp_state == "kicked":
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                if menu.kick_dismiss_btn_rect.collidepoint(get_scaled_mouse()):
                    mp_state = "browser"
                    mp_kick_msg = ""
                    mp_selected = -1

    def enter(self):
        # Bring up the relay as soon as the browser is shown. relay_start()
        # only spawns a daemon thread, so this cannot stall the frame.
        try:
            menu.relay_start()
        except Exception as exc:
            print("Multiplayer relay failed to start (non-fatal):", exc)

    def exit(self):
        # Close the socket when leaving the screen. The worker is a daemon,
        # but a clean stop avoids a lingering thread and a half-open port.
        try:
            menu.relay_stop()
        except Exception:
            pass

    def update(self, dt):
        global mp_state, mp_timer, mp_selected, mp_kick_msg
        # A live match owns the frame. The server browser underneath must
        # not animate or process its own state while players are shooting,
        # or leaving a match would reveal a browser that has drifted.
        if _match_screen.mode in ("hosting", "playing", "panel"):
            _match_screen.update(
                pygame.key.get_pressed(),
                (pygame.mouse.get_pos()[0], pygame.mouse.get_pos()[1],
                 pygame.mouse.get_pressed()[0]),
                dt)
            if _match_screen.mode == "closed":
                mp_state = "browser"
            return
        menu.update_server_browser_animation()
        menu.update_dm_state()
        menu.direct_connect_tick()
        if mp_state == "connecting":
            mp_timer -= 1
            if mp_timer <= 0:
                mp_state = "kicked"
                if 0 <= mp_selected < len(menu.server_list):
                    server_name = menu.server_list[mp_selected][0]
                    mp_kick_msg = menu.get_kick_message_for_server(server_name)
                else:
                    mp_kick_msg = _rng_legacy.choice(menu.KICK_MESSAGES)
                mp_timer = 0

    def set_ambience(self):
        _set_ambience(set())

    def render(self, surface):
        # The match screen paints the whole frame on its own -- it is not an
        # overlay on the browser -- so the browser is skipped entirely.
        if _match_screen.mode in ("hosting", "playing", "panel"):
            _match_screen.draw(surface)
            return
        menu.draw_menu_background()
        mp_connect_progress = 0.0
        if mp_state == "connecting":
            mp_connect_progress = 1.0 - max(0, min(180, mp_timer)) / 180.0
        menu.draw_server_browser(
            mp_selected,
            mp_state == "connecting",
            mp_kick_msg if mp_state == "kicked" else "",
            mp_connect_progress,
        )


class _SettingsState(GameState):
    name = "SETTINGS"

    def enter(self):
        global _settings_drag_bar
        _settings_drag_bar = None
        _preview_settings()

    def handle_event(self, event, mouse_x, mouse_y, keys):
        global _settings_return_to
        if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            if _persist_settings():
                gsm.transition(_settings_return_to)
                _settings_return_to = "MENU"
            return
        result = handle_settings_event(event)
        if result == "back":
            gsm.transition(_settings_return_to)
            _settings_return_to = "MENU"

    def update(self, dt):
        pass

    def set_ambience(self):
        _set_ambience(set())

    def render(self, surface):
        if _settings_return_to == "PAUSED":
            # Shake-free follow camera: frozen overlays must never sit on a
            # mid-kick frame (the live render camera in _frozen_* includes
            # transient shake/kick that would never decay while paused).
            gc.game_draw(STATE.camera_x, STATE.camera_y)
            _g = _advance_grain()
            if _g is not None:
                surface.blit(_g, (0, 0))
            surface.blit(_pause_dim_overlay, (0, 0))
        else:
            menu.draw_menu_background()
        menu.draw_settings(
            settings_active_tab,
            display_mode, res_idx,
            master_volume, music_volume, sfx_volume, mute_on_focus_loss,
            crosshair, crosshair_size, auto_reload, aim_assist, subtitles,
            brightness, scanlines_enabled, grain_enabled, particle_density,
            mouse_sensitivity, invert_mouse,
            STATE.reduced_motion, colorblind_mode,
            shake_scale, flash_reduction, text_speed,
            save_status=_settings_status, save_failed=_settings_save_failed,
            bindings=_input_adapter.display_bindings(), binding_capture=_binding_capture,
        )


class _ShopState(GameState):
    """The Outfitter: buy and wear cosmetics with Acaribucks.

    Delegates the whole panel to the one ShopScreen instance and keeps only the
    transition here, because a screen that spends money should not also be the
    thing deciding where the player goes next.
    """
    name = "SHOP"

    def enter(self):
        # Whoever navigates here calls open_panel() so the tab and the selected
        # item survive a trip to the match screen and back. This covers the
        # paths that do not - a dev --state=SHOP, or a transition added later -
        # without which the screen renders an empty panel.
        if _shop_screen.mode != "open":
            _shop_screen.open_panel(_shop_return_to)

    def handle_event(self, event, mouse_x, mouse_y, keys):
        global _shop_return_to
        if _shop_screen.handle_event(event, (mouse_x, mouse_y)) == "back":
            target = _shop_return_to
            _shop_return_to = "MENU"
            _shop_screen.close()
            gsm.transition(target)

    def update(self, dt):
        _shop_screen.update(dt)

    def set_ambience(self):
        _set_ambience(set())

    def render(self, surface):
        menu.draw_menu_background()
        _shop_screen.draw(surface)


class _CutsceneState(GameState):
    name = "CUTSCENE"

    def enter(self):
        cp = active_cutscene
        if cp and cp.current_shot and cp.current_shot.get("cinematic_controls"):
            # The gameplay transition must not consume the opening camera beat.
            cp.start_time = _now_ms()

    def exit(self):
        cp = active_cutscene
        if cp and cp.finale_audio:
            cp.finale_audio.stop()
        # Dedicated finale cues must not leak into the completion/menu state.
        for name in ("m4_tension", "m4_cuff_close", "m4_crowd", "m4_aftermath",
                     "m4_breath", "m4_roof_air"):
            audio.stop(name)
        _set_ambience(set())

    def _handle_end(self):
        """Called when the last shot finishes. Routes to after_state."""
        global mission_complete_timer, mission_complete_fade
        cp = active_cutscene
        if cp.current_shot and cp.current_shot.get("cinematic_controls"):
            if cp.completed:
                return
            cp.completed = True
            if cp.finale_audio:
                cp.finale_audio.stop()
            voice.stop()
        after = cp.after_state
        if after == "WALK":
            gc.start_walking_sim()
            trigger_transition("WALK")
        elif after == "GAME":
            if getattr(gc, "active_mission", "MISSION1") == "MISSION2":
                gc.grant_seby_os12()
                gc.player_locked = False
                trigger_transition("GAME")
            elif getattr(gc, "active_mission", "MISSION1") == "MISSION3":
                trigger_transition("GAME")
            else:
                gc.start_mission(preserve_timer=True)
                trigger_transition("GAME")
        elif after == "MISSION2":
            gc.start_mission2(preserve_timer=True)
            trigger_transition("GAME")
        elif after == "MISSION2_COMPLETE":
            gsm.transition("MISSION_COMPLETE")
            mission_complete_timer = 0
            mission_complete_fade = 0
            pygame.mouse.set_visible(True)
        elif after == "MISSION3_COMPLETE":
            gsm.transition("MISSION_COMPLETE")
            mission_complete_timer = 0
            mission_complete_fade = 0
            pygame.mouse.set_visible(True)
        elif after == "MISSION4":
            # M4 intro cutscene over: make sure the mission is live (slot-
            # resume/dev paths may already have started it; re-running is the
            # idempotent start idiom, same as the MISSION2 branch below).
            gc.start_mission4(preserve_timer=True)
            trigger_transition("GAME")
            pygame.mouse.set_visible(False)
        elif after == "MISSION4_COMPLETE":
            gsm.transition("MISSION_COMPLETE")
            mission_complete_timer = 0
            mission_complete_fade = 0
            pygame.mouse.set_visible(True)
        elif after == "MISSION5":
            # M5 bulletin chain over: make sure the mission is live (slot-
            # resume/dev paths may already have started it; re-running is the
            # idempotent start idiom, same as the MISSION4 branch above).
            gc.start_mission5(preserve_timer=True)
            trigger_transition("GAME")
            pygame.mouse.set_visible(False)
        elif after == "M5_RESUME":
            from missions.m5 import flow as _m5_flow  # lazy: M5-only
            _m5_flow.on_m5_cutscene_done(_M5_MID["key"])
            trigger_transition("GAME")
            pygame.mouse.set_visible(False)
        elif after == "MISSION5_COMPLETE":
            gsm.transition("MISSION_COMPLETE")
            mission_complete_timer = 0
            mission_complete_fade = 0
            pygame.mouse.set_visible(True)
        elif after == "MISSION3_BROADCAST_FAIL":
            # Fail sequence over: rebuild the wing, reset the 22:00 clock and
            # drop the player back into Slice 6. Guarded so a double _handle_end
            # (or a non-M3 cutscene reusing the tag) can't rebuild twice.
            from missions import m3
            if getattr(STATE, "active_mission", "MISSION1") == "MISSION3" \
                    and getattr(STATE, "m3_bcast_failed", False):
                m3._retry_broadcast_slice()
            trigger_transition("GAME")
            pygame.mouse.set_visible(False)
        elif after == "BRIEFING":
            start_briefing("warehouse")
            gsm.transition("BRIEFING")

    def handle_event(self, event, mouse_x, mouse_y, keys):
        if event.type != pygame.KEYDOWN:
            return
        cp = active_cutscene
        if cp is None or cp.completed:
            return
        shot = cp.current_shot
        if shot and shot.get("cinematic_controls"):
            if event.key == pygame.K_ESCAPE:
                if cp.skip_confirm or cp.paused:
                    cp.skip_confirm = False
                    cp.resume()
                    voice.resume()
                    if cp.finale_audio:
                        cp.finale_audio.resume()
                else:
                    cp.pause()
                    voice.pause()
                    if cp.finale_audio:
                        cp.finale_audio.pause()
                return
            if event.key == pygame.K_RETURN:
                if cp.skip_confirm:
                    self._handle_end()
                else:
                    cp.skip_confirm = True
                    cp.pause()
                    voice.pause()
                    if cp.finale_audio:
                        cp.finale_audio.pause()
                return
            if cp.paused:
                return
        if event.key != pygame.K_SPACE:
            return
        if shot is None or cp.transition_timer != 0:
            return
        if cp.char_idx < len(shot["text"]):
            cp.char_idx = len(shot["text"])
        else:
            elapsed_ms = cp.elapsed_ms
            if elapsed_ms < shot.get("min_ms", 0):
                if not shot.get("quiet_ui"):
                    audio.play("menu_hover", volume=0.12)
                return
            try:
                voice.stop()             # skipping a shot cuts its line
            except Exception:
                pass
            if cp.shot_idx < len(cp.shots) - 1:
                if not shot.get("quiet_ui"):
                    audio.play("menu_click", volume=0.3)
                if cp.use_fades and not shot.get("hard_cut"):
                    cp.transition_timer = 15  # fade out
                else:
                    cp.shot_idx += 1
                    cp.char_idx = 0
                    cp.timer = 0
                    cp.start_time = _now_ms()
                    gc.reset_dialogue_slide()
            else:
                self._handle_end()

    def update(self, dt):
        cp = active_cutscene
        if cp is None or cp.paused or cp.completed:
            return
        cp.timer += 1
        shot = cp.current_shot
        if shot is None:
            return
        elapsed = cp.elapsed_ms
        if cp.finale_audio:
            cp.finale_audio.update(elapsed)
        cues = shot.get("cues", KO_CUT_CUES.get(shot["scene"], ()))
        for cue_idx, (ms, name, vol) in enumerate(cues):
            key = (cp.shot_idx, cue_idx)
            if elapsed >= ms and key not in cp.fired_cues:
                cp.fired_cues.add(key)
                # Mark stale cues consumed rather than blasting a backlog after
                # a suspended window. Repeated footsteps each own one cue key.
                if elapsed - ms <= 350:
                    channel = audio.play(name, volume=vol)
                    if cp.finale_audio:
                        cp.finale_audio.track(channel)
        # Timeline-owned lines: once per cue, no audio backlog after suspension.
        for idx, (ms, speaker, text, radio) in enumerate(shot.get("dialogue_events", ())):
            key = (cp.shot_idx, "dialogue", idx)
            if elapsed >= ms and key not in cp.fired_cues:
                cp.fired_cues.add(key)
                if elapsed - ms <= 350:
                    from audio import voice
                    voice.play_line(speaker, text, radio=radio)
        if shot["scene"] == "m4_arrest_screen" and 7600 <= elapsed < 9400:
            audio.duck_ambience(frames=3, factor=0.16)
        # Handle shot-to-shot transition
        if cp.transition_timer > 0:
            cp.transition_timer -= 1
            if cp.transition_timer == 8:
                cp.shot_idx += 1
                cp.char_idx = 0
                cp.timer = 0
                cp.start_time = _now_ms()
                cp.transition_timer = -12  # fade in
                gc.reset_dialogue_slide()
                return  # do not apply the old shot's text length to the new shot
        elif cp.transition_timer < 0:
            cp.transition_timer += 1
        # Explicitly authored silent takes must not freeze on their final frame
        # with no visible continue prompt. Dialogue remains player-controlled.
        if (shot.get("auto_advance") and cp.transition_timer == 0
                and elapsed >= shot.get("min_ms", 0)
                and cp.char_idx >= len(shot["text"])):
            self.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_SPACE),
                              0, 0, {})
            return
        # Typewriter effect
        if elapsed < shot.get("caption_after_ms", 0):
            cp.timer = 0
            return
        # Voice-over: once per shot, as the caption starts typing. Shots
        # tagged "radio": True (Vasile on comms, etc.) get the radio filter.
        if (cp.shot_idx, "vo") not in cp.fired_cues:
            cp.fired_cues.add((cp.shot_idx, "vo"))
            if shot.get("speaker") and shot["text"]:
                try:
                    from audio import voice
                    voice.play_line(shot["speaker"], shot["text"],
                                    radio=bool(shot.get("radio")))
                except Exception as exc:
                    print(f"[voice] cutscene VO skipped: {exc}")
        if cp.char_idx < len(shot["text"]):
            if cp.timer >= _text_speed_interval():  # RPE6 P9 text speed (live setting)
                cp.timer = 0
                last = shot["text"][max(0, cp.char_idx - 1)]
                if last in ".!?":
                    cp.timer -= 25
                elif last in ",;:":
                    cp.timer -= 12
                elif last == "-":
                    cp.timer -= 15
                next_ch = shot["text"][cp.char_idx] if cp.char_idx < len(shot["text"]) else ""
                if not shot.get("quiet_ui"):
                    _play_typewriter_tick(next_ch, cp.char_idx, volume=0.11)
                cp.char_idx += 1

    def set_ambience(self):
        cp = active_cutscene
        if cp is None:
            return
        shot = cp.current_shot
        if shot is None:
            return
        rain_scenes = {"ocean_wide", "city_skyline", "biribel_arrival", "krap_convoy",
                       "route12_checkpoint", "route12_tanker", "route12_aftermath",
                       "seby_pickup_body", "seby_pickup_reach", "seby_pickup_raise"}
        amb = {"ambient_drone"}
        if shot["scene"] == "m5_shadow_finale":
            # Dedicated stereo river/rain stem replaces the generic loops.
            _set_ambience(set() if cp.finale_audio else
                          (set() if cp.paused else {"rain", "wind"}))
            return
        if shot["scene"] == "m4_arrest_screen":
            amb = {"room_tone"} if cp.elapsed_ms < 12400 else set()
        elif shot["scene"] == "m4_maru_silhouette":
            amb = {"room_tone", "elec_hum"}
        elif shot["scene"] == "m4_roof_dawn":
            amb = {"m4_roof_air"}
        if shot["scene"] in {"m5_river_gate", "m5_ucilev_scope",
                             "m5_ucilev_reveal", "m5_ucilev_leaves", "m5_radio"}:
            amb = {"rain", "wind"}
        elif cp.after_state == "MISSION5_COMPLETE" and shot["scene"] == "title_card":
            amb = set()
        if shot["scene"] in rain_scenes:
            amb.add("rain")
            amb.add("wind")
        _set_ambience(amb)

    def render(self, surface):
        cp = active_cutscene
        if cp is None:
            return
        shot = cp.current_shot
        if shot is None:
            return
        t_ms = cp.elapsed_ms
        gc.draw_cutscene_scene(surface, shot, t_ms)
        if shot["scene"] == "title_card":
            lines = shot["text"].split("\n")
            gc.draw_typewriter_title(surface, lines, cp.char_idx)
        else:
            outdoor_rain = {"ocean_wide", "city_skyline", "biribel_arrival", "krap_convoy",
                            "route12_checkpoint", "route12_tanker", "route12_aftermath"}
            if shot["scene"] in outdoor_rain:
                draw_rain(surface, gc.rain_drops, speed_mul=1.0)
                surface.blit(_cutscene_fog, (0, 0))
                surface.blit(_cutscene_top_fog, (0, LETTER_H))
            # The finale grades its own picture; don't crush its facial detail
            # with the legacy heavy vignette or double-scan its public CRT.
            if not shot.get("self_graded"):
                draw_vignette(surface, strength=80 if shot.get("quiet_ui") else 180)
            if not shot.get("quiet_ui"):
                draw_scanlines(surface)
            draw_letterbox(surface)
            can_continue = t_ms >= shot.get("min_ms", 0)
            if t_ms >= shot.get("caption_after_ms", 0) and not shot.get("hide_caption") and (shot["text"] or shot.get("speaker")):
                gc.draw_dialogue_box(
                    surface,
                    shot["speaker"],
                    shot["text"],
                    cp.char_idx,
                    len(shot["text"]),
                    can_continue,
                )
            if not shot.get("self_graded"):
                _g = _advance_grain()
                if _g is not None:
                    surface.blit(_g, (0, 0))
            if shot.get("cinematic_controls"):
                from cutscenes.m5shadow3d import draw_controls
                draw_controls(surface, cp.paused, cp.skip_confirm, t_ms)
        # Shot transition fade
        if abs(cp.transition_timer) > 0:
            fade_alpha = 0
            if cp.transition_timer > 0:
                fade_alpha = int(255 * (cp.transition_timer / 15))
            else:
                fade_alpha = int(255 * (1 - abs(cp.transition_timer) / 12))
            fade_surf = pygame.Surface((WIDTH, HEIGHT))
            fade_surf.fill((0, 0, 0))
            fade_surf.set_alpha(min(255, fade_alpha))
            surface.blit(fade_surf, (0, 0))


class _BriefingState(GameState):
    name = "BRIEFING"

    def handle_event(self, event, mouse_x, mouse_y, keys):
        if event.type == pygame.KEYDOWN and event.key in (pygame.K_SPACE, pygame.K_RETURN):
            finish_briefing()

    def update(self, dt):
        global briefing_timer
        briefing_timer += 1
        if briefing_timer >= BRIEFING_DURATION:
            finish_briefing()

    def set_ambience(self):
        _set_ambience({"ambient_drone"})

    def render(self, surface):
        draw_briefing_screen()


class _WalkState(GameState):
    name = "WALK"

    def handle_event(self, event, mouse_x, mouse_y, keys):
        if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            gsm.transition("PAUSED")
        if event.type == pygame.KEYDOWN and event.key == pygame.K_SPACE:
            if gc.walk_dialogue_active:
                if gc.walk_dialogue_char_idx < len(gc.walk_dialogue_text):
                    gc.walk_dialogue_char_idx = len(gc.walk_dialogue_text)
                else:
                    gc.walk_dialogue_active = False
        if event.type == pygame.KEYDOWN and event.key == pygame.K_e:
            gc.handle_walk_interact()

    def update(self, dt):
        # NOTE: Do NOT update _frozen_cx/_frozen_cy here. The walking sim
        # camera coords don't correspond to the game map, so if PAUSED is
        # entered from WALK, rendering with those coords on game_draw()
        # would show black void / garbled tiles. Instead, PAUSED from WALK
        # draws via gc.draw_walking_sim().
        _cx, _cy, complete = gc.update_walking_sim(keys)
        if complete:
            start_cutscene(gc.cutscene2_shots, "BRIEFING", use_fades=False)
            trigger_transition("CUTSCENE")

    def set_ambience(self):
        _set_ambience({"ambient_drone", "rain", "wind"})

    def render(self, surface):
        gc.draw_walking_sim()
        _g = _advance_grain()
        if _g is not None:
            surface.blit(_g, (0, 0))


def _apply_equipped_look():
    """Dress the campaign player in whatever the Outfitter has equipped.

    Applied from the GAME state rather than at the dozen Player(...) sites,
    because this is the one point every mission passes through and because
    set_appearance() is safe to re-run on a live sprite. Never raises: a
    cosmetic loadout that cannot be read must not stop a mission from starting.

    The walking sim deliberately does not call this - it is a shirtless
    prologue, and arriving in purchased gear would be a continuity error the
    player would notice before the gear matters.
    """
    player = getattr(STATE, "player", None)
    if player is None:
        return
    try:
        player.set_appearance(profile_store.equipped())
    except Exception as exc:
        print("Equipped look not applied: %s" % exc)


class _GameState_(GameState):
    name = "GAME"

    def enter(self):
        _apply_equipped_look()

    def handle_event(self, event, mouse_x, mouse_y, keys):
        # Mission 3 interrogation phase
        if getattr(gc, "active_mission", "MISSION1") == "MISSION3":
            _m3_stage = getattr(gc, "mission3_stage", "interrogation")
            _is_escape = (event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE)
            if _m3_stage == "interrogation" and not _is_escape:
                try:
                    from missions import m3
                    m3.handle_event(event)
                except ImportError:
                    pass
                return
            elif _is_escape:
                gsm.transition("PAUSED")
                return

        # Mission 4 liaison dialogue owns the keyboard while the meet is up
        # (Enter/Space advance + confirm, arrows move the choice highlight).
        if getattr(gc, "active_mission", "MISSION1") == "MISSION4" \
                and getattr(STATE, "m4_dialogue_active", False):
            if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                gsm.transition("PAUSED")
                return
            try:
                from missions import m4
                m4.handle_dialogue_event(event)
            except ImportError:
                pass
            return

        # Mission 5 first-person [E] look: any key or click closes it (ESC too -
        # it is a glance, not a menu), and nothing else sees the event.
        if getattr(gc, "active_mission", "MISSION1") == "MISSION5":
            try:
                from missions import m5
                if m5.inspect_active():
                    m5.handle_inspect_event(event)
                    return
            except ImportError:
                pass

        # Mission 5 typewriter dialogue (Maru in the back office) owns the
        # keyboard while it is up - Enter/Space/E snap the line, then advance.
        if getattr(gc, "active_mission", "MISSION1") == "MISSION5" \
                and getattr(STATE, "m5_dialogue_active", False):
            if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                gsm.transition("PAUSED")
                return
            try:
                from missions import m5
                m5.handle_dialogue_event(event)
            except ImportError:
                pass
            return

        # Mission 2 intel cards
        if getattr(gc, "active_mission", "MISSION1") == "MISSION2" and getattr(gc, "mission2_card", None):
            if event.type == pygame.KEYDOWN and event.key in (pygame.K_e, pygame.K_SPACE, pygame.K_RETURN, pygame.K_ESCAPE):
                gc.handle_interact()
            return

        # Upload OS (M2 evidence terminal + M3 broadcast station PC)
        if getattr(gc, "active_mission", "MISSION1") in ("MISSION2", "MISSION3"):
            try:
                from ui import upload_os
                if upload_os.is_upload_os_active():
                    upload_os.handle_upload_os_event(event)
                    return
            except ImportError:
                pass

        # Mission 3 crafting overlay
        if getattr(gc, "active_mission", "MISSION1") == "MISSION3":
            try:
                from missions import m3
                if m3.is_crafting_active():
                    m3.handle_crafting_event(event)
                    return
            except ImportError:
                pass

        # Mission 2 authored beats lock player actions
        if getattr(gc, "active_mission", "MISSION1") == "MISSION2" and getattr(gc, "blocks_player_actions", lambda: False)():
            if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                gsm.transition("PAUSED")
            return

        if gc.active_read_note:
            if event.type == pygame.KEYDOWN and event.key in (pygame.K_SPACE, pygame.K_e, pygame.K_RETURN):
                gc.dismiss_note()
        elif gc.safe_keypad_active:
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                gc.handle_keypad_click(event.pos)
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    gc.safe_keypad_active = False
                    pygame.mouse.set_visible(False)
                else:
                    gc.handle_keypad_keypress(event.key)
        else:
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                if gc.truck_hotwiring:
                    gc.handle_hotwire_click(event.pos)
                else:
                    gc.handle_shoot()
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 3:
                if not gc.truck_hotwiring:
                    gc.handle_throw_bottle()
            if event.type == pygame.KEYDOWN and event.key == pygame.K_g:
                gc.handle_throw_bottle()
            if event.type == pygame.KEYDOWN and event.key == pygame.K_r:
                gc.start_reload()
            if event.type == pygame.KEYDOWN and event.key == pygame.K_q:
                gc.switch_weapon()
            if event.type == pygame.KEYDOWN and event.key == pygame.K_e:
                if gc.truck_hotwiring:
                    gc.handle_hotwire_press()
                else:
                    gc.handle_interact()
            if event.type == pygame.KEYDOWN and event.key == pygame.K_v:
                gc.handle_melee()
            if event.type == pygame.KEYDOWN and event.key == pygame.K_m:
                gc.show_minimap = not gc.show_minimap
            if event.type == pygame.KEYDOWN and event.key == pygame.K_F9:
                gc.debug_jump_to_exfil()
            if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                gsm.transition("PAUSED")

    def update(self, dt):
        global _frozen_cx, _frozen_cy, mission_complete_timer, mission_complete_fade

        if gc.request_death_screen:
            gc.request_death_screen = False
            if not gc.mission_end_time:
                gc.mission_end_time = _now_ms()
            if hasattr(STATE, 'mission2_card'):
                STATE.mission2_card = None
            gsm.transition("DEATH")
            pygame.mouse.set_visible(True)
            menu.reset_death_animation()
            return

        if gc.request_notebook_inspect:
            gsm.transition("NOTEBOOK_INSPECT")
            gc.request_notebook_inspect = False
            pygame.mouse.set_visible(True)
            from ui import hud; hud.reset_notebook_inspect()
            return

        # Trailer bot injects aim + WASD before the sim steps (AI 1).
        # Uses keys_eff (not rebinding `keys`) because `keys` is a
        # module-global read here - rebinding the name would make it a
        # method-local and raise UnboundLocalError on the RHS read.
        keys_eff = keys
        try:
            from tools import trailer_bot as _bot
            if _bot.is_active():
                keys_eff, _ = _bot.tick_bot(keys_eff)
        except Exception:
            pass
        # RPE6 Phase 0: dev-only input recorder (ACA_RECORD_INPUT=<file>);
        # read-only, a no-op unless the env flag is set.
        if _input_recorder.enabled():
            _input_recorder.record(keys_eff, (mouse_x, mouse_y), pygame.mouse.get_pressed()[0])
        cx, cy = gc.game_update(keys_eff)
        # Live render camera (follow + shake + kick): GAME.render draws every
        # frame from this, so gunfire/explosion shake actually reaches the
        # screen. Frozen states (pause/death/notebook/settings) read the
        # shake-free STATE.camera_x/y directly instead, so they never sit on
        # a mid-kick frame.
        _frozen_cx, _frozen_cy = cx, cy

        if getattr(gc, "request_mission2_ending", False):
            gc.request_mission2_ending = False
            start_cutscene(gc.mission2_ending_shots, "MISSION2_COMPLETE", use_fades=True)
            trigger_transition("CUTSCENE")
            pygame.mouse.set_visible(True)
        elif getattr(gc, "request_mission3_ending", False):
            gc.request_mission3_ending = False
            start_cutscene(gc.mission3_ending_shots, "MISSION3_COMPLETE", use_fades=True)
            trigger_transition("CUTSCENE")
            pygame.mouse.set_visible(True)
        elif getattr(gc, "request_mission4_ending", False):
            gc.request_mission4_ending = False
            start_cutscene(gc.mission4_ending_shots, "MISSION4_COMPLETE", use_fades=True)
            trigger_transition("CUTSCENE")
            pygame.mouse.set_visible(True)
        elif getattr(gc, "request_mission5_ending", False):
            gc.request_mission5_ending = False
            if gc.mission5_ending_shots:
                start_cutscene(gc.mission5_ending_shots, "MISSION5_COMPLETE", use_fades=True)
                trigger_transition("CUTSCENE")
            else:
                # Finale cut for a clean rebuild. Never enter an empty
                # CutscenePlayer: it has no shot and would strand the game.
                interactions.clear_radio_queue()
                gsm.transition("MISSION_COMPLETE")
                mission_complete_timer = 0
                mission_complete_fade = 0
            pygame.mouse.set_visible(True)
        elif _m0_outro_pending():
            from missions import m0 as _m0mod  # lazy: see _m0_outro_pending
            start_cutscene(_m0mod.outro_shots(), "MISSION_COMPLETE", use_fades=True)
            trigger_transition("CUTSCENE")
            pygame.mouse.set_visible(True)
        elif _m5_mid_cut_key():
            from missions.m5.meta import M5_MID_CUTSCENES  # lazy: M5-only data
            _M5_MID["key"] = _m5_mid_cut_key()
            from core.state import STATE as _st5  # lazy: see _m5_mid_cut_key
            _st5.request_m5_cutscene = None
            start_cutscene(M5_MID_CUTSCENES[_M5_MID["key"]], "M5_RESUME", use_fades=True)
            trigger_transition("CUTSCENE")
        elif getattr(gc, "request_seby_pickup_cutscene", False):
            gc.request_seby_pickup_cutscene = False
            start_cutscene(gc.seby_pickup_shots, "GAME", use_fades=True)
            trigger_transition("CUTSCENE")
            pygame.mouse.set_visible(True)
        elif getattr(gc, "request_k9_pickup_cutscene", False):
            gc.request_k9_pickup_cutscene = False
            start_cutscene(gc.k9_pickup_shots, "GAME", use_fades=True)
            trigger_transition("CUTSCENE")
            pygame.mouse.set_visible(True)
        elif getattr(STATE, "request_vostral_pickup_cutscene", False):
            STATE.request_vostral_pickup_cutscene = False
            start_cutscene(gc.vostral_pickup_shots, "GAME", use_fades=True)
            trigger_transition("CUTSCENE")
            pygame.mouse.set_visible(True)
        elif getattr(STATE, "request_volkov_mags_cutscene", False):
            STATE.request_volkov_mags_cutscene = False
            # Grant two spare mags to whatever Biribel is currently carrying.
            if STATE.current_weapon == "k9_smg":
                STATE.k9_spare_mags = getattr(STATE, "k9_spare_mags", 0) + 2
            elif STATE.current_weapon == "pistol":
                STATE.spare_mags = getattr(STATE, "spare_mags", 0) + 2
            start_cutscene(gc.volkov_mags_shots, "GAME", use_fades=True)
            trigger_transition("CUTSCENE")
            pygame.mouse.set_visible(True)
        elif getattr(gc, "request_escape_cutscene", False):
            gc.request_escape_cutscene = False
            gsm.transition("ESCAPE_CUTSCENE")
            global escape_cutscene_timer
            escape_cutscene_timer = 0
            pygame.mouse.set_visible(False)
        elif getattr(gc, "request_chair_break_cutscene", False):
            gc.request_chair_break_cutscene = False
            # Set state mutations for the breakout.
            STATE.mission3_chair_broken = True
            STATE.player_disarmed = False
            STATE.mission3_weapon = "chair_leg"
            start_cutscene(gc.chair_break_shots, "GAME", use_fades=True)
            trigger_transition("CUTSCENE")
            pygame.mouse.set_visible(True)
        elif getattr(STATE, "request_service_transition_cutscene", False):
            STATE.request_service_transition_cutscene = False
            start_cutscene(gc.service_transition_shots, "GAME", use_fades=True)
            trigger_transition("CUTSCENE")
            pygame.mouse.set_visible(True)
        elif getattr(STATE, "request_vent_cutscene", False):
            STATE.request_vent_cutscene = False
            start_cutscene(gc.vent_escape_shots, "GAME", use_fades=True)
            trigger_transition("CUTSCENE")
            pygame.mouse.set_visible(True)
        elif getattr(STATE, "request_archives_transition_cutscene", False):
            STATE.request_archives_transition_cutscene = False
            start_cutscene(gc.archives_transition_shots, "GAME", use_fades=True)
            trigger_transition("CUTSCENE")
            pygame.mouse.set_visible(True)
        elif getattr(STATE, "request_ko_transition_cutscene", False):
            STATE.request_ko_transition_cutscene = False
            from core.interactions import clear_radio_queue
            clear_radio_queue()
            start_cutscene(gc.ko_transition_shots, "GAME", use_fades=True)
            trigger_transition("CUTSCENE")
            pygame.mouse.set_visible(True)
        elif getattr(STATE, "request_broadcast_transition_cutscene", False):
            STATE.request_broadcast_transition_cutscene = False
            from core.interactions import clear_radio_queue
            clear_radio_queue()
            start_cutscene(gc.broadcast_transition_shots, "GAME", use_fades=True)
            trigger_transition("CUTSCENE")
            pygame.mouse.set_visible(True)
        elif getattr(STATE, "request_mission3_fail_cutscene", False):
            # 22:00 landed before the file did. Play the fail sequence, then
            # hand control back so _CutsceneState._handle_end retries the
            # slice (_retry_broadcast_slice). Without this the wing used to
            # sit frozen with "Retry Slice 6" and no way to act on it.
            STATE.request_mission3_fail_cutscene = False
            from core.interactions import clear_radio_queue
            clear_radio_queue()
            start_cutscene(gc.broadcast_fail_shots,
                           "MISSION3_BROADCAST_FAIL", use_fades=True)
            trigger_transition("CUTSCENE")
            pygame.mouse.set_visible(True)

    def set_ambience(self):
        mission = getattr(gc, "active_mission", "MISSION1")
        if mission == "MISSION2":
            _set_ambience({"ambient_drone", "rain", "wind"})
        elif mission == "MISSION4":
            # The Aftermath: same rain-slick night-city bed as M2's exterior
            # (the curfew capital is open air; rain_inside + wind gusts are
            # layered per-frame from core.ambience for MISSION4).
            _set_ambience({"ambient_drone", "rain", "wind"})
        elif mission == "MISSION5":
            # Martial Law: the Lower Quarter is open air and raining, but the
            # print works and the tunnel are indoors, where the exterior bed
            # reads as a leak. set_ambience() runs every frame and
            # _set_ambience() is diff-based, so the stage switch swaps the
            # loops for free. M5 is deliberately NOT in ambience.RAIN_MISSIONS:
            # the roof-rain layer would follow the player underground.
            from missions.m5.meta import STAGE_QUARTER as _m5_exterior
            if getattr(STATE, "mission5_stage", None) == _m5_exterior:
                _set_ambience({"ambient_drone", "rain", "wind"})
            else:
                _set_ambience({"ambient_drone"})
        else:
            _set_ambience(set())

    def render(self, surface):
        gc.game_draw(_frozen_cx, _frozen_cy)
        _g = _advance_grain()
        if _g is not None:
            surface.blit(_g, (0, 0))
        gc.draw_desk_note()
        gc.draw_safe_keypad()
        # NOTE: the reticle is no longer drawn here. It moved to the main loop
        # (hud.draw_crosshair, right after the state render pass) so it also
        # survives pause/settings/death/report. Drawing it here as well would
        # double-blit it and double-decay STATE.crosshair_kick.


class _EscapeCutsceneState(GameState):
    name = "ESCAPE_CUTSCENE"

    def handle_event(self, event, mouse_x, mouse_y, keys):
        global mission_complete_timer, mission_complete_fade
        if event.type == pygame.KEYDOWN and event.key in (pygame.K_SPACE, pygame.K_RETURN):
            gc.mission_end_time = _now_ms()
            gsm.transition("MISSION_COMPLETE")
            mission_complete_timer = 0
            mission_complete_fade = 0
            pygame.mouse.set_visible(True)

    def update(self, dt):
        global escape_cutscene_timer, mission_complete_timer, mission_complete_fade
        escape_cutscene_timer += 1
        if escape_cutscene_timer == 18:
            audio.play("door_open", volume=0.45)
        if escape_cutscene_timer == 38:
            audio.play("rig_low_boom", volume=0.25)
        if escape_cutscene_timer == 310:
            audio.play("missile_launch", volume=0.32)
        if escape_cutscene_timer == 650:
            audio.play("radio_static", volume=0.22)
        if escape_cutscene_timer == 735:
            audio.play("terminal_glitch", volume=0.24)
        if escape_cutscene_timer == 820:
            audio.play("menu_click", volume=0.34)
        if escape_cutscene_timer >= ESCAPE_CUTSCENE_DURATION:
            gc.mission_end_time = _now_ms()
            gsm.transition("MISSION_COMPLETE")
            mission_complete_timer = 0
            mission_complete_fade = 0
            pygame.mouse.set_visible(True)

    def set_ambience(self):
        _set_ambience({"rain", "wind", "ambient_drone"})

    def render(self, surface):
        gc.draw_biribel_escape_cutscene(surface, escape_cutscene_timer)


class _NotebookInspectState(GameState):
    name = "NOTEBOOK_INSPECT"

    def handle_event(self, event, mouse_x, mouse_y, keys):
        if event.type == pygame.KEYDOWN and event.key in (pygame.K_SPACE, pygame.K_RETURN):
            gsm.transition("GAME")
            pygame.mouse.set_visible(False)

    def update(self, dt):
        pass

    def set_ambience(self):
        _set_ambience(set())

    def render(self, surface):
        gc.game_draw(STATE.camera_x, STATE.camera_y)
        gc.draw_notebook_inspection()


class _PausedState(GameState):
    name = "PAUSED"
    _return_to = "GAME"  # Snapshot of the state we came from

    def enter(self):
        # Snapshot the previous state on entry. This prevents the
        # PAUSED → SETTINGS → PAUSED round-trip from corrupting
        # gsm.previous_name (which would become "SETTINGS" instead
        # of the original gameplay state).
        _PausedState._return_to = gsm.previous_name
        try:
            voice.pause()               # keep VO/screams in sync with the frozen scene
        except Exception:
            pass

    def handle_event(self, event, mouse_x, mouse_y, keys):
        global _settings_return_to
        if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            voice.resume()
            gsm.transition(_PausedState._return_to)
            pygame.mouse.set_visible(False)
        if menu.pause_buttons[0].is_clicked(event, (mouse_x, mouse_y)):
            voice.resume()
            gsm.transition(_PausedState._return_to)
            pygame.mouse.set_visible(False)
        if menu.pause_buttons[1].is_clicked(event, (mouse_x, mouse_y)):
            _settings_return_to = "PAUSED"
            gsm.transition("SETTINGS")
        if menu.pause_buttons[2].is_clicked(event, (mouse_x, mouse_y)):
            gc.restart_current_mission()
            gsm.transition("GAME")
            pygame.mouse.set_visible(False)
            menu.reset_death_animation()
        if menu.pause_buttons[3].is_clicked(event, (mouse_x, mouse_y)):
            audio.hard_stop()            # cut right away, not after the fade
            trigger_transition("MENU")

    def update(self, dt):
        pass

    def set_ambience(self):
        _set_ambience(set())

    def render(self, surface):
        # Draw the correct background based on where we came from.
        # WALK uses its own renderer; GAME/NOTEBOOK_INSPECT use game_draw.
        if _PausedState._return_to == "WALK":
            gc.draw_walking_sim()
        else:
            gc.game_draw(STATE.camera_x, STATE.camera_y)
        _g = _advance_grain()
        if _g is not None:
            surface.blit(_g, (0, 0))
        menu.draw_pause_menu()


class _DeathState(GameState):
    name = "DEATH"

    def handle_event(self, event, mouse_x, mouse_y, keys):
        if (getattr(STATE, "active_mission", "MISSION1") == "MISSION3"
                and getattr(STATE, "m3_black_ledger_death_active", False)
                and hasattr(menu, "black_ledger_death_buttons_ready")
                and not menu.black_ledger_death_buttons_ready()):
            return

        if menu.death_buttons[0].is_clicked(event, (mouse_x, mouse_y)):
            try:
                gc.restart_current_mission()
            except Exception as _restart_err:
                import traceback
                traceback.print_exc()
                # Save the checkpoint flag BEFORE the fallback - start_mission2()
                # calls STATE.reset() which clears mission2_checkpoint_reached to
                # False. Without this, a failed checkpoint respawn (e.g.
                # _explode_tanker threw) cascades into a permanent loss of the
                # checkpoint: the fallback does a full start_mission2() (clearing
                # the flag), and every subsequent death also does a full restart
                # instead of a checkpoint respawn. We restore the flag after the
                # fallback so the next death uses the checkpoint.
                _checkpoint_was_reached = getattr(STATE, "mission2_checkpoint_reached", False)
                try:
                    if getattr(STATE, "active_mission", "MISSION1") == "MISSION2":
                        from missions import m2
                        # If the checkpoint was reached, retry the checkpoint
                        # respawn before falling back to a full mission restart.
                        # The first failure (inside restart_current_mission →
                        # start_mission2_checkpoint) may have been transient
                        # (audio state, partial initialization race). The retry
                        # calls start_mission2_checkpoint() which re-runs
                        # start_mission2() (STATE.reset + full init) so STATE
                        # is clean - this isn't retrying on corrupted state.
                        _checkpoint_retry_ok = False
                        if _checkpoint_was_reached:
                            try:
                                m2.start_mission2_checkpoint(preserve_timer=False)
                                _checkpoint_retry_ok = True
                            except Exception:
                                traceback.print_exc()
                        if not _checkpoint_retry_ok:
                            # Full mission restart as last resort. Preserve
                            # the checkpoint flag so the next death respawn
                            # uses the checkpoint instead of restarting the
                            # entire mission from the intro cutscene.
                            m2.start_mission2(preserve_timer=False)
                            if _checkpoint_was_reached:
                                STATE.mission2_checkpoint_reached = True
                    elif getattr(STATE, "active_mission", "MISSION1") == "MISSION3":
                        from missions import m3
                        # Deepest phase reached, mirroring
                        # restart_current_mission(): the Kill Order and the
                        # Broadcast Wing are the two gauntlets, so a respawn
                        # there beats dumping the player back in the atrium.
                        if getattr(STATE, "mission3_broadcast_checkpoint_reached", False):
                            m3.start_mission3_broadcast_checkpoint(preserve_timer=False)
                        elif getattr(STATE, "mission3_kill_order_checkpoint_reached", False):
                            m3.start_mission3_kill_order_checkpoint(preserve_timer=False)
                        elif getattr(STATE, "mission3_archives_checkpoint_reached", False):
                            m3.start_mission3_archives_checkpoint(preserve_timer=False)
                        elif getattr(STATE, "mission3_comms_checkpoint_reached", False):
                            m3.start_mission3_comms_checkpoint(preserve_timer=False)
                        elif getattr(STATE, "mission3_breakout_checkpoint_reached", False):
                            m3.start_mission3_breakout_checkpoint(preserve_timer=False)
                        else:
                            m3.start_mission3(preserve_timer=False)
                    else:
                        from missions import m1
                        m1.start_mission(preserve_timer=False)
                except Exception as _fallback_err:
                    traceback.print_exc()
                    trigger_transition("MENU")
                    menu.reset_death_animation()
                    return
            gsm.transition("GAME")
            pygame.mouse.set_visible(False)
            menu.reset_death_animation()
        elif menu.death_buttons[1].is_clicked(event, (mouse_x, mouse_y)):
            trigger_transition("MENU")
            menu.reset_death_animation()

    def update(self, dt):
        pass

    def set_ambience(self):
        _set_ambience({"heartbeat"})

    def render(self, surface):
        if (getattr(STATE, "active_mission", "MISSION1") == "MISSION3"
                and getattr(STATE, "m3_black_ledger_death_active", False)
                and hasattr(menu, "draw_black_ledger_death_buttons")):
            # Black Ledger death is its own final screen. Do NOT call
            # gc.game_draw() here: that draws the gameplay HUD, minimap,
            # objective, ammo panel, etc. The final animated ledger frame
            # becomes the death screen on a clean black-site background.
            surface.fill((3, 2, 2))
            try:
                from missions import m3
                m3._draw_black_ledger_death_overlay()
            except Exception:
                # If the custom renderer ever fails, fall back to the normal
                # death screen rather than trapping the player.
                gc.game_draw(STATE.camera_x, STATE.camera_y)
            menu.draw_black_ledger_death_buttons()
            return

        gc.game_draw(STATE.camera_x, STATE.camera_y)
        _g = _advance_grain()
        if _g is not None:
            surface.blit(_g, (0, 0))
        menu.draw_death_screen()


class _MissionCompleteState(GameState):
    name = "MISSION_COMPLETE"

    def enter(self):
        global mission_complete_timer, mission_complete_fade
        mission_complete_timer = 0
        mission_complete_fade = 0
        # Save exactly once on entry - before any handler can zero the timer.
        # Handles MISSION1 / MISSION2 / MISSION3 via save_system's mapping.
        report = _mission_report_data(success=True)
        save_system.save_mission_complete_record(
            getattr(gc, "active_mission", "MISSION1"),
            report["time_str"],
            stats=report,
        )

    def handle_event(self, event, mouse_x, mouse_y, keys):
        if event.type == pygame.KEYDOWN and event.key in (pygame.K_SPACE, pygame.K_RETURN):
            if getattr(gc, "active_mission", "MISSION1") == "MISSION1":
                gc.mission_start_time = _now_ms()
                gc.mission_end_time = 0
                start_cutscene(gc.mission2_intro_shots, "MISSION2", use_fades=False)
                trigger_transition("CUTSCENE")
            elif getattr(gc, "active_mission", "MISSION1") == "MISSION2":
                # Campaign flow: Mission 2 completion should lead into the
                # Mission 3 intro cutscene, not drop directly into gameplay.
                # The cutscene's after_state="GAME" path then transitions
                # cleanly into Mission 3 gameplay once the intro finishes.
                gc.mission_start_time = _now_ms()
                gc.mission_end_time = 0
                gc.start_mission3(preserve_timer=True)
                start_cutscene(gc.mission3_intro_shots, "GAME", use_fades=True)
                trigger_transition("CUTSCENE")
                pygame.mouse.set_visible(True)
            elif getattr(gc, "active_mission", "MISSION1") == "MISSION3":
                # M3 → M4 chain (mirrors the M2 → M3 idiom): start M4 while
                # the intro plays; the cutscene's after_state="MISSION4"
                # path drops into gameplay when it ends.
                gc.mission_start_time = _now_ms()
                gc.mission_end_time = 0
                gc.start_mission4(preserve_timer=True)
                start_cutscene(gc.mission4_intro_shots, "MISSION4", use_fades=True)
                trigger_transition("CUTSCENE")
                pygame.mouse.set_visible(True)
            elif getattr(gc, "active_mission", "MISSION1") == "MISSION4":
                # M4 → M5 chain (mirrors the M3 → M4 idiom): start M5 while
                # the bulletin plays; the cutscene's after_state="MISSION5"
                # path drops into the Lower Quarter when it ends.
                gc.mission_start_time = _now_ms()
                gc.mission_end_time = 0
                gc.start_mission5(preserve_timer=True)
                start_cutscene(gc.mission5_intro_shots, "MISSION5", use_fades=True)
                trigger_transition("CUTSCENE")
                pygame.mouse.set_visible(True)
            else:
                # MISSION5 (and anything after): back to the menu. M5
                # completing the campaign is the W4 behavior until a later
                # milestone extends the chain into M6.
                trigger_transition("MENU")
                pygame.mouse.set_visible(True)

    def update(self, dt):
        pass

    def set_ambience(self):
        _set_ambience(set())
        if mission_complete_timer == 1:
            audio.play("mission_complete", volume=0.6)

    def render(self, surface):
        global mission_complete_timer, mission_complete_fade
        mission_complete_timer += 1
        mission_complete_fade = min(255, mission_complete_timer * 5)

        # Background gradient
        for i in range(HEIGHT):
            t = i / HEIGHT
            r = int(5 + t * 8)
            g = int(8 + t * 12)
            b = int(14 + t * 20)
            pygame.draw.line(surface, (r, g, b), (0, i), (WIDTH, i))
        if mission_complete_timer % 3 == 0:
            rng_n = random.Random(mission_complete_timer // 3)
            for _ in range(60):
                nx = rng_n.randint(0, WIDTH - 1)
                ny = rng_n.randint(0, HEIGHT - 1)
                surface.set_at((nx, ny), (12, 16, 22))

        # Card
        card_w, card_h = 520, 440
        card_x = WIDTH // 2 - card_w // 2
        card_y = HEIGHT // 2 - card_h // 2 - 10
        shadow = pygame.Surface((card_w + 16, card_h + 16), pygame.SRCALPHA)
        shadow.fill((0, 0, 0, 80))
        surface.blit(shadow, (card_x + 8, card_y + 8))
        card = pygame.Surface((card_w, card_h), pygame.SRCALPHA)
        card.fill((8, 12, 18, 235))
        pygame.draw.rect(card, (35, 60, 85, 160), (0, 0, card_w, card_h), 1)
        pygame.draw.rect(card, (50, 120, 180), (0, 0, 4, card_h))
        surface.blit(card, (card_x, card_y))

        def _mc_text(surf, x, y, alpha):
            surf.set_alpha(min(255, alpha))
            surface.blit(surf, (x, y))

        def _mc_wrap(text, font, max_w):
            """Word-wrap to max_w. Long quotes/outcome lines used to render
            as one line and ran off both screen edges."""
            out = []
            for para in str(text).split("\n"):
                line = ""
                for word in para.split(" "):
                    test = (line + " " + word).strip()
                    if font.size(test)[0] <= max_w or not line:
                        line = test
                    else:
                        out.append(line)
                        line = word
                out.append(line)
            return out

        # Header area
        pygame.draw.rect(surface, (6, 10, 16, 240),
                         (card_x + 4, card_y, card_w - 4, 42))
        pygame.draw.line(surface, (35, 60, 85),
                         (card_x + 16, card_y + 42),
                         (card_x + card_w - 16, card_y + 42), 1)
        eyebrow = font_terminal_small.render(
            _T("app.krap_intel_after_action_report"), True, (60, 120, 170))
        _mc_text(eyebrow,
                 card_x + card_w // 2 - eyebrow.get_width() // 2,
                 card_y + 8, mission_complete_fade)
        classif = font_terminal_small.render(_T("app.classified"), True, (180, 60, 50))
        _mc_text(classif, card_x + card_w - classif.get_width() - 20,
                 card_y + 8, mission_complete_fade)
        title_font = pygame.font.SysFont("Consolas", 32, bold=True)
        title_surf = title_font.render(_T("app.mission_complete"), True, (200, 198, 190))
        _mc_text(title_surf,
                 card_x + card_w // 2 - title_surf.get_width() // 2,
                 card_y + 56, mission_complete_fade)
        op_name = _mission_meta.operation_name(STATE)
        op = font_terminal.render(op_name, True, (160, 155, 145))
        _mc_text(op,
                 card_x + card_w // 2 - op.get_width() // 2,
                 card_y + 96, mission_complete_fade)
        outcome_line = getattr(gc, "active_mission_outcome", "Target escaped  ·  Notebook recovered  ·  Questions remain")
        out_lines = _mc_wrap(outcome_line, font_terminal_small, card_w - 48)
        for _oli, out_line in enumerate(out_lines):
            out = font_terminal_small.render(out_line, True, (150, 120, 90))
            _mc_text(out,
                     card_x + card_w // 2 - out.get_width() // 2,
                     card_y + 120 + _oli * 16, mission_complete_fade)
        pygame.draw.line(surface, (30, 50, 70),
                         (card_x + 30, card_y + 145),
                         (card_x + card_w - 30, card_y + 145), 1)

        # Stats grid
        if mission_complete_timer > 25:
            stats_fade = min(255, (mission_complete_timer - 25) * 7)
            report = _mission_report_data(success=True)
            stats = [
                ("KILLS", str(report["kills"])),
                ("SHOTS FIRED", str(report["shots_fired"])),
                ("ACCURACY", f"{report['accuracy']}%"),
                ("TOTAL TIME", report["time_str"]),
                ("CIVILIANS HELPED", str(report["civilians_helped"])),
                ("INTEL FOUND", "YES" if report["intel_found"] else "NO"),
                ("RATIONS USED", str(report["rations_used"])),
                ("RANK", report["rank"]),
            ]
            stat_x = card_x + 36
            stat_y = card_y + 158
            for i, (label, value) in enumerate(stats):
                col = i % 2
                row = i // 2
                sx = stat_x + col * 240
                sy = stat_y + row * 42
                lbl = font_terminal_small.render(label, True, (55, 95, 130))
                lbl.set_alpha(stats_fade)
                surface.blit(lbl, (sx, sy))
                val_font = pygame.font.SysFont("Consolas", 22, bold=True)
                val_col = (255, 220, 120) if label == "RANK" else (180, 220, 245)
                val = val_font.render(value, True, val_col)
                val.set_alpha(stats_fade)
                surface.blit(val, (sx, sy + 14))
                line_alpha = min(stats_fade, 60)
                ul = pygame.Surface((200, 1), pygame.SRCALPHA)
                ul.fill((35, 60, 85, line_alpha))
                surface.blit(ul, (sx, sy + 34))

        pygame.draw.line(surface, (30, 50, 70),
                         (card_x + 30, card_y + 325),
                         (card_x + card_w - 30, card_y + 325), 1)

        # Vasile quote
        if mission_complete_timer > 70:
            q_fade = min(255, (mission_complete_timer - 70) * 5)
            attr = font_terminal_small.render(
                getattr(gc, "active_mission_quote_attr", "Vasile, after a long pause:"), True, (90, 80, 70))
            attr.set_alpha(q_fade)
            surface.blit(attr, (card_x + 36, card_y + 338))
            quote_lines = _mc_wrap(
                getattr(gc, "active_mission_quote", '"Bring it straight to me. Don\'t read it."'),
                font_dialogue, card_w - 72)
            quote_h = 18
            quote_top = card_y + 360 - (len(quote_lines) - 1) * quote_h // 2
            for _qi, quote_line in enumerate(quote_lines):
                quote = font_dialogue.render(quote_line, True, C_VASILE)
                quote.set_alpha(q_fade)
                surface.blit(quote,
                             (card_x + card_w // 2 - quote.get_width() // 2,
                              quote_top + _qi * quote_h))

        # Bottom bar
        pygame.draw.line(surface, (35, 60, 85),
                         (card_x + 16, card_y + card_h - 34),
                         (card_x + card_w - 16, card_y + card_h - 34), 1)
        footer = font_terminal_small.render(
            _T("app.krap_intelligence_division_field"), True, (45, 65, 80))
        _mc_text(footer,
                 card_x + card_w // 2 - footer.get_width() // 2,
                 card_y + card_h - 26, mission_complete_fade)

        # Continue prompt
        if mission_complete_timer > 120 and (_now_ms() // 600) % 2 == 0:
            next_prompt = "PRESS SPACE TO START MISSION 2" if getattr(gc, "active_mission", "MISSION1") == "MISSION1" else "PRESS SPACE TO RETURN TO MENU"
            prompt = font_btn.render(next_prompt, True, C_ORANGE)
            prompt.set_alpha(mission_complete_fade)
            surface.blit(prompt,
                         (WIDTH // 2 - prompt.get_width() // 2,
                          card_y + card_h + 18))


# ═══════════════════════════════════════════════
# FSM REGISTRATION
# ═══════════════════════════════════════════════

for _state_cls in (
    _BootIntroState, _EngineIntroState,
    _MenuState, _SlotSelectState, _MultiplayerState, _SettingsState,
    _ShopState,
    _CutsceneState, _BriefingState, _WalkState, _GameState_,
    _EscapeCutsceneState, _NotebookInspectState, _PausedState,
    _DeathState, _MissionCompleteState,
):
    gsm.add(_state_cls())

gsm.transition("BOOT_INTRO")
_apply_dev_args()

# ─────────────────────────────────────────────
# DEV TOOLS - Level Editor & Console
# ─────────────────────────────────────────────
level_editor = LevelEditor()
console = Console()

# RPE6 Phase 10 (§6.19): debug overlay / inspector / collision view.
from game.devtools import DEV as _devtools  # noqa: E402

console.bind("scene", lambda name: (gsm.transition(name.upper()), f"scene -> {name.upper()}")[1])
console.bind("events", lambda: _console_events_tail())
_dev_sim_ms = 0.0
_dev_draw_ms = 0.0


def _console_events_tail():
    try:
        bus = _rpe6_config._engine_app.events
        return [repr(e)[:70] for e in bus.tail(10)] or ["(no events yet)"]
    except Exception as e:
        return [f"events unavailable: {e!r}"]


def _console_timeline_play(timeline_id, t_ms=0):
    try:
        from game import timelines as _tl
        data = _tl.timeline(timeline_id)
        if data is None:
            return f"timeline {timeline_id!r} not found"
        shots = _tl.shots(timeline_id, [])
        start_cutscene(shots, "MENU")
        if active_cutscene is not None and t_ms:
            active_cutscene.start_time -= int(t_ms)
        return f"playing timeline {timeline_id} ({len(shots)} shots) from {t_ms}ms"
    except Exception as e:
        return f"timeline failed: {e!r}"


console.bind("timeline", _console_timeline_play)


def _console_heat(value):
    try:
        from missions.m5 import quarter as _q  # lazy: mission module (app-side binding, keeps core.console shared-clean)
        if value is not None:
            _q._S["heat"] = float(value)
        return f"m5 quarter heat={_q._S.get('heat')}"
    except Exception:
        return "heat: M5 quarter state not loaded"


def _console_reload():
    try:
        from game import levels as _lv, dialogues as _dl, timelines as _tl
        from art import m5 as _art
        _lv._cache.clear(); _dl._cache.clear(); _tl._cache.clear()
        _art.invalidate()
        return "reloaded: level/dialogue/timeline caches + m5 art"
    except Exception as e:
        return f"reload failed: {e!r}"


console.bind("heat", _console_heat)
console.bind("reload", _console_reload)


def _devtools_cutscene_info():
    cp = active_cutscene
    if cp is None or not cp.shots:
        return None
    shot = cp.current_shot or {}
    return {"idx": cp.shot_idx, "count": len(cp.shots),
            "scene": shot.get("scene", "?"), "speaker": shot.get("speaker", ""),
            "text": shot.get("text", "")}


_devtools.bind_cutscene(_devtools_cutscene_info)


def _devtools_cache_line():
    from art import m5 as _m5art  # lazy: A-008 shim (same import as _rpe6_hot_reload)
    return f"assets registered={len(_m5art.registry().ids())}"

def _update_editor_map():
    mission = getattr(gc, "active_mission", "MISSION1")
    try:
        if mission == "MISSION1":
            from missions import m1
            level_editor.set_map(m1.mission1_map, map_name="mission1")
        elif mission == "MISSION2":
            from missions import m2
            level_editor.set_map(m2.MISSION2_MAP, map_name="mission2")
        elif mission == "MISSION3":
            from missions import m3
            level_editor.set_map(m3.MISSION3_MAP, map_name="mission3")
    except (ImportError, AttributeError):
        pass

# ─────────────────────────────────────────────
# Apply saved display mode on startup
# ─────────────────────────────────────────────
try:
    apply_display_mode(display_mode, menu.SETTINGS_RESOLUTIONS[res_idx])
except Exception as _e:
    print(f"Startup display apply failed (non-fatal): {_e}")


# ═══════════════════════════════════════════════
# MAIN LOOP - CLEAN FSM DISPATCH
# ═══════════════════════════════════════════════

MAX_DT = 0.05
running = True

# RPE6 ADAPTER A-002: the loop body is unchanged; it now runs as one frame
# of a scene hosted by engine.core.App.run_scene (crash reports on uncaught
# errors). Every name the body assigns stays a module global, exactly as
# under the old module-level `while running:` loop.
def _legacy_frame():
    global CURSOR_ARROW_STATES, _frame_ms, _hud, _mp_live, _s, _sim_step, current_name, dt, event, keys, mouse_visible, mouse_x, mouse_y, music_state, new_mode, running, upload_os
    global _dev_sim_ms, _dev_draw_ms
    import time as _dev_time
    _dev_t0 = _dev_time.perf_counter()
    _frame_ms = clock.tick(60)
    _devtools.frames.push(_frame_ms, _dev_sim_ms, _dev_draw_ms)   # RPE6 P10
    dt = min(_frame_ms / 1000.0, MAX_DT)
    STATE.dt = dt
    mouse_x, mouse_y = get_scaled_mouse()
    keys = pygame.key.get_pressed()
    try:
        keys = _input_adapter.apply(keys)   # RPE6 P9: bindings + gamepad (identity at defaults)
    except Exception:
        pass

    if hasattr(audio, "update"):
        audio.update()

    # ── Radio director: release queued transmissions (called in all states;
    # the pump itself decides whether the current state may speak) ──
    # Gated by interactions.radio_allowed(): only GAME / WALK outside
    # cutscene handoffs and dialogue; PAUSED/SETTINGS freeze the radio clock.
    interactions.pump_radio(gsm.current_name, gsm.transitioning)

    # ── Mouse visibility ──
    current_name = gsm.current_name
    # Hide the OS pointer wherever the game draws its own cursor instead:
    #   GAME / WALK          → combat reticle (drawn by the mission modules)
    #   menu-family states   → custom tactical arrow (ui.main.draw_menu_cursor)
    # Single source of truth for the menu half is ui.main.CURSOR_ARROW_STATES;
    # hiding the pointer on a state that draws no cursor would strand the user
    # with no visible pointer at all.
    from ui.main import CURSOR_ARROW_STATES
    mouse_visible = current_name not in (CURSOR_ARROW_STATES | {"GAME", "WALK"})
    if current_name == "GAME":
        if level_editor.active:
            mouse_visible = True
        else:
            try:
                from ui import upload_os
                if upload_os.is_upload_os_active():
                    mouse_visible = False
            except ImportError:
                pass
    pygame.mouse.set_visible(mouse_visible)

    # ── Event dispatch ──
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False
            continue

        # Global: mute on focus loss
        if event.type == pygame.ACTIVEEVENT:
            try:
                from core.user_settings import SETTINGS as _s
                if _s.mute_on_focus_loss:
                    if event.gain == 0:
                        audio.mute_all()
                    else:
                        audio.unmute_all()
            except Exception:
                pass

        # Global: F11 fullscreen toggle
        if event.type == pygame.KEYDOWN and event.key == pygame.K_F11:
            new_mode = 1 if display_mode == 0 else 0
            apply_display_mode(new_mode, menu.SETTINGS_RESOLUTIONS[res_idx])
            if gsm.current_name == "SETTINGS":
                _preview_settings()
            else:
                _persist_settings()
            continue

        # F12 - Level Editor toggle (gameplay only)
        if event.type == pygame.KEYDOWN and event.key == pygame.K_F12:
            if gsm.current_name == "GAME":
                if level_editor.map_data is None:
                    _update_editor_map()
                level_editor.toggle()
            continue

        # `~` - Developer Console toggle (any state)
        if event.type == pygame.KEYDOWN and event.key == pygame.K_BACKQUOTE:
            console.toggle()
            continue

        # RPE6 P10: F3/F4 overlay toggles + inspector clicks
        if _devtools.handle_event(event, (mouse_x, mouse_y),
                                  "CONSOLE" if console.active else gsm.current_name):
            continue

        # Console consumes all events while active
        if console.active:
            console.handle_event(event)
            continue

        # Level Editor processes events alongside game
        if level_editor.active:
            level_editor.handle_event(event)

        # State-level event handling
        if not gsm.transitioning:
            gsm.current.handle_event(event, mouse_x, mouse_y, keys)

    # ── Update dispatch ──
    # NOTE: `keys` is read as a module-level global. It's set each frame
    # at the top of the loop. This works because Python's while-loop
    # doesn't create a new scope. If the loop is ever moved into a
    # function, `keys` must be passed as a parameter to update().
    #
    # ── Fixed-timestep (multiplayer only) ──
    # Off by default: single-player keeps the exact legacy variable-dt
    # behaviour, one update() call per rendered frame. When a multiplayer
    # session enables it (core.fixedstep.set_enabled(True)), the simulation
    # is instead advanced in whole 1/60 s ticks, so a frame counter like
    # `fire_cooldown -= 1` advances the same amount of *game time* on every
    # machine. Without this the host's hardware silently sets the rules of
    # the match: a host rendering at 30 FPS would hand out half the fire rate
    # of one at 60. Rendering is untouched and still happens once per frame,
    # so this cannot change how anything looks.
    #
    # Deliberate asymmetry: this loop advances the simulation and nothing
    # else. Audio, ambience, event handling and rendering stay per-frame so
    # they keep their real-time feel and the frame rate stays free of
    # simulation concerns.
    if _fixedstep.is_enabled():
        for _sim_step in range(_fixedstep.clock().steps(dt)):
            # Each tick sees exactly one fixed dt, so `60.0 * STATE.dt` is
            # exactly 1.0 and px/frame speeds mean the intended thing.
            STATE.dt = _fixedstep.clock().dt
            if not gsm.transitioning:
                gsm.current.update(_fixedstep.clock().dt)
    else:
        # RPE6 Phase 1 (ADR-004): single-player now also runs on the engine's
        # fixed-step clock (App.clock, 60 Hz, max 5 steps/frame). Render,
        # audio and events stay per-frame, exactly like the MP branch above.
        _eng_clock = _rpe6_config._engine_app.clock
        for _sim_step in range(_eng_clock.advance(dt)):
            STATE.dt = _eng_clock.dt
            if not gsm.transitioning:
                gsm.current.update(_eng_clock.dt)
            _eng_clock.tick()

    # ── Ambience dispatch ──
    gsm.current.set_ambience()

    # ── World ambience layers (zone-driven loops + scheduled foley) ──
    ambience.update_ambience()
    # Stream menu music on menu-family states
    music_state = gsm.next_state if gsm.transitioning and gsm.fade_speed > 0 else current_name
    _set_menu_music(music_state in MENU_MUSIC_STATES)

    _dev_sim_ms = (_dev_time.perf_counter() - _dev_t0) * 1000.0   # RPE6 P10 sim split
    # ── Render dispatch ──
    gsm.current.render(screen)

    # ── Screen-space cursors (two call sites, mutually exclusive) ──
    # Both are drawn here, after the state's own pass, so they persist no
    # matter what the state rendered on top. Each owns its own state gate:
    #   hud.draw_crosshair()    → GAME / WALK (aiming)
    #   menu.draw_menu_cursor() → every menu-family screen (pointing)
    # They never both paint: the two state sets are disjoint by construction.
    from ui import hud as _hud
    _hud.draw_crosshair(screen, current_name)
    # MULTIPLAYER is a menu-family state, but a live arena match renders
    # through that state name and aims with the combat reticle. Keep the
    # arrow during play; keep it visible on the host's frozen waiting screen
    # so COPY CODE remains easy to target. The pause menu also needs the arrow
    # back to click RESUME / LEAVE MATCH.
    # MULTIPLAYER is the one menu-family state that also hosts live play, so it
    # decides for itself which pointer owns the frame. Asking the match screen
    # rather than testing its mode here keeps host and joiner on the same rule:
    # the frozen lobby and the start countdown want the arrow, a live round
    # wants the reticle. The previous inline test used waiting_for_player(),
    # which only ever returns True for the host -- so a joiner in the very same
    # lobby lost the arrow they needed to click the team panels with.
    _mp_live = (current_name == "MULTIPLAYER"
                and not _match_screen.wants_menu_cursor())
    menu.draw_menu_cursor(screen, current_name, suppressed=_mp_live)

    # ── Dev tool overlays ──
    level_editor.draw(screen)
    console.draw(screen)
    _devtools.draw(screen)   # RPE6 P10: F3 overlay / inspector / F4 collision

    # ── FSM transition overlay ──
    gsm.update_transition()
    gsm.draw_transition(screen)

    # ── Global post-processing ──
    _apply_postprocess()

    _present_frame()
    _dev_draw_ms = (_dev_time.perf_counter() - _dev_t0) * 1000.0 - _dev_sim_ms   # RPE6 P10
    pygame.display.flip()
    # RPE6 B-001: the frame-coherent wall clock (engine.core.now_ms/now_s)
    # advances once per presented frame by the raw, unclamped frame time, so
    # every read during the next frame sees the same "now". Fed after flip:
    # reads during frame k return the time at which frame k-1 was presented.
    _rpe6_config._engine_app.clock.feed_wall(_frame_ms)
    if _RPE6_HOT_RELOAD is not None:          # dev only (ACARISTAN_HOT_RELOAD=1): poll every 500 ms
        _RPE6_HOT_RELOAD.poll(_now_ms())


from core import config as _rpe6_config  # noqa: E402
from core.scene_mirror import FsmSceneMirror as _FsmSceneMirror  # noqa: E402
from engine.scene import CutsceneScene as _RpeCutsceneScene, InspectScene as _RpeInspectScene, SceneStack as _RpeSceneStack  # noqa: E402,E501
from missions.m5 import inspect_fpv as _m5_inspect_fpv  # noqa: E402  (A-007 observer; M5-only inspect)
from engine.text import T as _T  # RPE6 Phase 4 text table

# FSM states that draw over the one below them (push/pop on the scene stack);
# every other state replaces the top. Data for the A-005 mirror, not game logic.
_RPE6_OVERLAY_STATES = frozenset({"PAUSED", "NOTEBOOK_INSPECT"})


def _rpe6_hot_reload():
    """RPE6 Phase 3 (§6.5 hot reload): ``ACARISTAN_HOT_RELOAD=1`` watches the sprite-pack
    sources + baked files; an edit re-executes the module, drops its cached surfaces and
    emits ``AssetReloaded`` on the engine bus (logged on the 'assets' channel). Off by default."""
    import os as _os
    if _os.environ.get("ACARISTAN_HOT_RELOAD", "0").strip() != "1":
        return None
    from art import m5 as _m5art
    from engine.assets import AssetWatcher as _AssetWatcher
    _reg = _m5art.registry()
    _reg.bus = _rpe6_config._engine_app.events
    _reg.log = _rpe6_config._engine_app.log
    _w = _AssetWatcher(_reg, interval_ms=500)
    _rpe6_config._engine_app.log.info("assets", "hot reload on: watching %d files" % _w.rescan())
    return _w


_RPE6_HOT_RELOAD = _rpe6_hot_reload()


class _LegacyGameScene:
    """RPE6 ADAPTER A-002: the whole legacy game as one engine scene.

    Owns the engine SceneStack that mirrors ``gsm`` (A-005, ``core.scene_mirror``):
    every FSM transition becomes push/pop/replace on the stack, so the scene
    trace (``log.channel("scene")``, ``stack.trace``) exists before any state is
    migrated. The stack never drives behaviour here.
    """

    def __init__(self):
        app = _rpe6_config._engine_app
        self.stack = _RpeSceneStack(ctx=app, log=app.log)
        _devtools.bind(scene_stack=self.stack.names, state_name=lambda: gsm.current_name,   # RPE6 P10
                       cache=_devtools_cache_line)
        self.mirror = _FsmSceneMirror(gsm, self.stack, _RPE6_OVERLAY_STATES, scene_factory=self._scene_for)
        _m5_inspect_fpv.on_change = self._on_inspect   # A-007: inspect_fpv -> InspectScene overlay

    @staticmethod
    def _scene_for(name, overlay):
        """A-007: the CUTSCENE state is mirrored as a CutsceneScene carrying the take that
        plays (shot list identity: first scene id + shot count). Timing stays with the
        legacy CutscenePlayer until the state is lifted (Phase 4); the scene is a mirror."""
        if name == "CUTSCENE" and active_cutscene is not None and active_cutscene.shots:
            shots = active_cutscene.shots
            take = f"{shots[0].get('scene', '?')}+{len(shots)}"
            return _RpeCutsceneScene(take, shots, renderer=None)
        return None

    def _on_inspect(self, is_active, key):
        stack = self.stack
        if is_active:
            if stack.top is None or stack.top.name != f"INSPECT[{key}]":
                scene = _RpeInspectScene(_m5_inspect_fpv, key)
                scene.started = True            # the module already started itself
                stack.push(scene)
        elif stack.top is not None and stack.top.name == f"INSPECT[{key}]":
            stack.pop()

    @property
    def done(self):
        return not running

    def frame(self):
        _legacy_frame()


_rpe6_config._engine_app.run_scene(_LegacyGameScene())

try:
    audio.hard_stop(music=True)          # no VO/loop tail after the window closes
    pygame.mixer.quit()
except Exception:
    pass
pygame.quit()
sys.exit()

