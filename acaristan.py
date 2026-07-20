# ------------------------------------------------------------
# acaristan.py
# ------------------------------------------------------------

# ------------------------------------------------------------
# acaristan.py
# ------------------------------------------------------------

# ------------------------------------------------------------
# acaristan.py
# ------------------------------------------------------------

# ------------------------------------------------------------
# acaristan.py
# ------------------------------------------------------------

import random
import sys
from config import *
from state import STATE
import menu
import game_core as gc
import save_system
import settings_store
from user_settings import SETTINGS
from fsm import GameState, GameStateManager
from level_editor import LevelEditor
from console import Console
# NOTE: RenderPipeline is available via render_pipeline.py but not yet
# wired into the GAME state's render path. It will be activated when
# game_draw_unified.py is integrated.

# ─────────────────────────────────────────────
# STATE
# ─────────────────────────────────────────────
gsm = GameStateManager()

# NOTE on the old FSM bridge: an earlier version of fsm.py stored states in
# `self._states` and exposed only names (strings), so acaristan.py monkey-
# patched a `.current` property onto the class to reach the live state object.
# fsm.py has since been refactored: it now stores states in `self.states` and
# sets `self.current` (the live state object) natively in __init__ /
# transition(). That monkey-patch is obsolete and actively harmful — its
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
mission_complete_saved = False
_slot_rects = []
slot_select_purpose = "new"
_last_briefing_title_chars = 0

_cutscene_fog = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
_cutscene_fog.fill((18, 22, 30, 60))
_cutscene_top_fog = pygame.Surface((WIDTH, HEIGHT // 2), pygame.SRCALPHA)
for _i in range(HEIGHT // 2):
    _a = int(80 * (1 - _i / (HEIGHT // 2)))
    pygame.draw.line(_cutscene_top_fog, (20, 25, 35, _a), (0, _i), (WIDTH, _i))

TEXT_SPEED = 4
_fade_surf = pygame.Surface((WIDTH, HEIGHT))

_pause_dim_overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
_pause_dim_overlay.fill((0, 0, 0, 180))

# Settings — loaded from settings_store
_settings = settings_store.load()

STATE.reduced_motion = _settings["reduced_motion"]
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
brightness = _settings["brightness"]
scanlines_enabled = _settings["scanlines"]
grain_enabled = _settings["grain"]
particle_density = _settings["particle_density"]
mouse_sensitivity = _settings["mouse_sensitivity"]
invert_mouse = _settings["invert_mouse"]
colorblind_mode = _settings["colorblind_mode"]

settings_active_tab = 0
_settings_return_to = "MENU"

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
        "brightness": brightness,
        "scanlines": scanlines_enabled,
        "grain": grain_enabled,
        "particle_density": particle_density,
        "mouse_sensitivity": mouse_sensitivity,
        "invert_mouse": invert_mouse,
        "reduced_motion": STATE.reduced_motion,
        "colorblind_mode": colorblind_mode,
    }


def _apply_audio_settings():
    audio.set_master_volume(master_volume)
    audio.set_music_volume(music_volume / 100.0)
    audio.set_sfx_volume(sfx_volume / 100.0)


def _push_live_settings():
    SETTINGS.push_from_raw(_current_settings_dict())
    _apply_audio_settings()


def _persist_settings():
    settings_store.save(_current_settings_dict())
    _push_live_settings()


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
    global settings_active_tab
    global display_mode, res_idx
    global master_volume, music_volume, sfx_volume, mute_on_focus_loss
    global crosshair, crosshair_size, auto_reload, aim_assist, subtitles
    global brightness, scanlines_enabled, grain_enabled, particle_density
    global mouse_sensitivity, invert_mouse, colorblind_mode

    if event.type != pygame.MOUSEBUTTONDOWN or event.button != 1:
        return None

    mp = get_scaled_mouse()

    if menu.settings_apply_btn.rect.collidepoint(mp):
        _persist_settings()
        audio.play("menu_click", volume=0.5)
        return "apply"

    if menu.settings_back_btn.rect.collidepoint(mp):
        _persist_settings()
        return "back"

    for i, rect in enumerate(menu.settings_tab_rects):
        if rect.collidepoint(mp):
            settings_active_tab = i
            audio.play("menu_click", volume=0.4)
            return None

    def _bar_value(bar_rect):
        t = (mp[0] - bar_rect.x) / bar_rect.width
        return max(0, min(100, int(t * 100)))

    step = 5

    if settings_active_tab == 0:
        res_changed = False
        mode_changed = False
        if menu.settings_res_left_rect.collidepoint(mp):
            res_idx = (res_idx - 1) % len(menu.SETTINGS_RESOLUTIONS)
            res_changed = True
        elif menu.settings_res_right_rect.collidepoint(mp):
            res_idx = (res_idx + 1) % len(menu.SETTINGS_RESOLUTIONS)
            res_changed = True
        elif menu.settings_display_left_rect.collidepoint(mp):
            display_mode = (display_mode - 1) % len(menu.DISPLAY_MODES)
            mode_changed = True
        elif menu.settings_display_right_rect.collidepoint(mp):
            display_mode = (display_mode + 1) % len(menu.DISPLAY_MODES)
            mode_changed = True
        if mode_changed or res_changed:
            if mode_changed:
                apply_display_mode(display_mode, menu.SETTINGS_RESOLUTIONS[res_idx])
            _persist_settings()
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
            _persist_settings()
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
        if changed:
            _persist_settings()
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
            _persist_settings()
            audio.play("menu_click", volume=0.3)

    elif settings_active_tab == 4:
        pass  # Controls tab — display-only

    else:
        changed = False
        if menu.settings_reduced_motion_rect.collidepoint(mp):
            STATE.reduced_motion = not STATE.reduced_motion; changed = True
        elif menu.settings_colorblind_left.collidepoint(mp):
            colorblind_mode = (colorblind_mode - 1) % len(menu.COLORBLIND_MODES); changed = True
        elif menu.settings_colorblind_right.collidepoint(mp):
            colorblind_mode = (colorblind_mode + 1) % len(menu.COLORBLIND_MODES); changed = True
        if changed:
            _persist_settings()
            audio.play("menu_click", volume=0.3)

    return None


def trigger_transition(target_state):
    """Fade-transition to target_state. Delegates to gsm (AEGIS FSM)."""
    gsm.trigger_transition(target_state)


# ─────────────────────────────────────────────
# CUTSCENE PLAYER (encapsulated state)
# ─────────────────────────────────────────────

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
        self.start_time = pygame.time.get_ticks()
        self.transition_timer = 0  # >0 = fading out, <0 = fading in, 0 = none

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
        return pygame.time.get_ticks() - self.start_time


# Module-level reference to the active cutscene player (or None).
active_cutscene = None


def start_cutscene(shots, after_state, use_fades=True):
    global active_cutscene
    active_cutscene = CutscenePlayer(shots, after_state, use_fades)
    gc.reset_dialogue_slide()


# ─────────────────────────────────────────────
# AMBIENCE
# ─────────────────────────────────────────────

_current_ambience = set()
MENU_MUSIC_FILE = "menu_theme.mp3"
_menu_music_active = False
_menu_music_failed = False
MENU_MUSIC_STATES = {"MENU", "SLOT_SELECT", "SETTINGS", "MULTIPLAYER"}


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


def _set_ambience(sounds_to_play):
    global _current_ambience
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
        import config, game_core, menu as m
        new_surf = pygame.display.get_surface()
        config.screen = new_surf
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
            import config, game_core, menu as m
            new_surf = pygame.display.get_surface()
            config.screen = new_surf
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
    end_t = gc.mission_end_time or pygame.time.get_ticks()
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
    """Draw save-slot selection as KRAP dossier cards.

    New campaign selection used to be three flat boxes over the menu art.  This
    keeps the same click rectangles / save logic, but makes the screen read as
    an intentional save-management interface with clearer overwrite states.
    """
    global _slot_rects

    menu.draw_menu_background()

    # Dark cinematic wash, lighter center so cards have depth but background art
    # still contributes atmosphere.
    dim = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
    dim.fill((0, 0, 0, 205))
    screen.blit(dim, (0, 0))
    center_glow = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
    for r, a in ((520, 26), (360, 34), (210, 38)):
        pygame.draw.ellipse(center_glow, (25, 55, 72, a),
                            (WIDTH // 2 - r, 38, r * 2, 520))
    screen.blit(center_glow, (0, 0), special_flags=pygame.BLEND_ADD)

    data = save_system.load_data()
    mouse = get_scaled_mouse()
    title_text = "SELECT SAVE SLOT" if slot_select_purpose == "new" else "CONTINUE CAMPAIGN"
    sub_text = ("Choose where the new operation record will be written. Occupied files will be overwritten."
                if slot_select_purpose == "new"
                else "Choose an active operation record to continue.")

    # Top classification plaque.
    plaque = pygame.Rect(WIDTH // 2 - 380, 56, 760, 112)
    plaque_surf = pygame.Surface((plaque.w, plaque.h), pygame.SRCALPHA)
    pygame.draw.rect(plaque_surf, (3, 8, 12, 205), plaque_surf.get_rect(), border_radius=8)
    pygame.draw.rect(plaque_surf, (46, 84, 112, 130), plaque_surf.get_rect(), 1, border_radius=8)
    pygame.draw.line(plaque_surf, (120, 180, 220, 110), (26, 78), (plaque.w - 26, 78), 1)
    screen.blit(plaque_surf, plaque.topleft)

    eyebrow = font_terminal_small.render(
        "KRAP INTELLIGENCE ARCHIVE // SAVE MANAGEMENT", True, (86, 142, 170))
    screen.blit(eyebrow, (plaque.centerx - eyebrow.get_width() // 2, plaque.y + 12))
    title = pygame.font.SysFont("Consolas", 46, bold=True).render(title_text, True, (235, 242, 246))
    screen.blit(title, (plaque.centerx - title.get_width() // 2, plaque.y + 34))
    sub = font_terminal_small.render(sub_text, True, (152, 160, 154))
    screen.blit(sub, (plaque.centerx - sub.get_width() // 2, plaque.y + 84))

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
        rect = pygame.Rect(x, y, card_w, card_h)
        _slot_rects.append(rect)
        slot = data["slots"][i]
        occupied = bool(slot.get("occupied"))
        selectable = slot_select_purpose == "new" or occupied
        hovered = rect.collidepoint(mouse) and selectable

        # Card lift/outline.
        lift = -8 if hovered else 0
        draw_y = y + lift
        shadow = pygame.Surface((card_w + 20, card_h + 24), pygame.SRCALPHA)
        pygame.draw.rect(shadow, (0, 0, 0, 120 if hovered else 82), shadow.get_rect(), border_radius=12)
        screen.blit(shadow, (x - 8, draw_y + 8))

        card = pygame.Surface((card_w, card_h), pygame.SRCALPHA)
        base = (8, 14, 20, 238 if selectable else 178)
        pygame.draw.rect(card, base, card.get_rect(), border_radius=10)
        pygame.draw.rect(card, (255, 120, 0, 230) if hovered else ((70, 76, 82, 120) if not selectable else (52, 96, 128, 180)),
                         card.get_rect(), 3 if hovered else 1, border_radius=10)
        # Left file-tab accent.
        accent = (255, 120, 0) if hovered else ((75, 110, 130) if selectable else (55, 55, 58))
        pygame.draw.rect(card, (*accent, 230), (0, 0, 7, card_h), border_radius=5)
        # Faint dossier lines.
        for yy in (72, 176, 218):
            pygame.draw.line(card, (44, 70, 86, 95), (22, yy), (card_w - 22, yy), 1)

        # File number header.
        file_num = font_terminal_small.render(f"FILE 0{i + 1}", True, (88, 142, 172))
        card.blit(file_num, (24, 18))
        header = font_terminal.render(f"SAVE SLOT {i + 1}", True,
                                      (255, 190, 95) if hovered else (150, 205, 232))
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
        chip = pygame.Rect(24, 84, 132, 28)
        pygame.draw.rect(card, chip_col, chip, border_radius=4)
        pygame.draw.rect(card, (*status_col, 120), chip, 1, border_radius=4)
        st = font_terminal_small.render(status_text, True, status_col)
        card.blit(st, (chip.x + 10, chip.y + 7))

        # Mission data.
        if occupied:
            completed = slot.get("last_completed_mission")
            l1 = "LAST COMPLETED" if completed else "IN PROGRESS"
            mission = _mission_label(slot)
            tline = f"TOTAL TIME  {slot.get('total_time', '00:00')}"
            updated = save_system.format_timestamp(slot.get("updated_at"))
            updated = "UPDATED  " + updated
        else:
            l1 = "NEW CAMPAIGN"
            mission = "Operation file will begin at Mission 1"
            tline = "TOTAL TIME  --:--"
            updated = "UPDATED  never"

        label = font_terminal_small.render(l1, True, (92, 154, 190))
        card.blit(label, (24, 132))
        # Truncate cleanly to fit card.
        mission_short = mission if len(mission) <= 31 else mission[:28] + "..."
        mission_surf = font_terminal_small.render(mission_short, True, (205, 205, 190) if occupied else (165, 165, 154))
        card.blit(mission_surf, (24, 158))
        time_surf = font_terminal_small.render(tline, True, (178, 184, 178))
        card.blit(time_surf, (24, 190))
        upd_surf = font_terminal_small.render(updated, True, (136, 142, 140))
        card.blit(upd_surf, (24, 210))

        # New campaign overwrite warning / continue availability.
        if slot_select_purpose == "new":
            action = "OVERWRITE FILE" if occupied else "CREATE FILE"
            action_col = (235, 115, 80) if occupied else (115, 220, 150)
        else:
            action = "LOAD FILE" if occupied else "NO DATA"
            action_col = (255, 170, 70) if hovered else ((120, 120, 120) if not occupied else (180, 190, 170))
        action_surf = font_terminal_small.render(action, True, action_col if selectable else (90, 90, 90))
        card.blit(action_surf, (card_w // 2 - action_surf.get_width() // 2, card_h - 42))

        if hovered:
            # Small hover chevrons and glow.
            pygame.draw.polygon(card, (255, 120, 0, 220), [(card_w - 31, 20), (card_w - 17, 27), (card_w - 31, 34)])
            glow = pygame.Surface((card_w, card_h), pygame.SRCALPHA)
            pygame.draw.rect(glow, (255, 120, 0, 28), glow.get_rect(), border_radius=10)
            card.blit(glow, (0, 0), special_flags=pygame.BLEND_ADD)

        screen.blit(card, (x, draw_y))

    # Bottom warning / footer.
    footer_panel = pygame.Surface((720, 64), pygame.SRCALPHA)
    pygame.draw.rect(footer_panel, (0, 0, 0, 118), footer_panel.get_rect(), border_radius=8)
    pygame.draw.rect(footer_panel, (42, 72, 90, 92), footer_panel.get_rect(), 1, border_radius=8)
    if slot_select_purpose == "new":
        footer_text = "New campaign writes to selected file. Existing active files will be overwritten."
        footer_col = (184, 132, 92)
    else:
        footer_text = "Only active files can be continued. Press ESC to return."
        footer_col = (126, 150, 160)
    f1 = font_terminal_small.render(footer_text, True, footer_col)
    f2 = font_terminal_small.render("Save file: save_data.json", True, (86, 94, 98))
    footer_panel.blit(f1, (footer_panel.get_width() // 2 - f1.get_width() // 2, 13))
    footer_panel.blit(f2, (footer_panel.get_width() // 2 - f2.get_width() // 2, 37))
    screen.blit(footer_panel, (WIDTH // 2 - footer_panel.get_width() // 2, HEIGHT - 92))


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
    eyebrow = font_terminal_small.render("KRAP SIGNAL INTERCEPTED", True, (85, 170, 220))
    blit_alpha(eyebrow, panel_x + 24, panel_y + 20, boot_alpha)
    stamp = font_terminal_small.render("FIELD COPY // UNVERIFIED", True, (190, 80, 60))
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
        ("STATUS", "OFFSHORE RIGS DESTROYED — UNKNOWN ATTACK CRAFT CONFIRMED"),
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
    obj_title = font_terminal.render("OBJECTIVES", True, (255, 150, 60))
    blit_alpha(obj_title, panel_x + 42, panel_y + 312, obj_alpha)
    objectives = [
        "Infiltrate the warehouse perimeter",
        "Locate and recover the black notebook",
        "Escape through the service exit",
    ]
    for i, txt in enumerate(objectives):
        alpha = obj_alpha - i * 30
        bullet = font_terminal.render("■", True, (65, 150, 210))
        line = font_prompt.render(txt, True, (205, 205, 195))
        row_y = panel_y + 350 + i * 26
        blit_alpha(bullet, panel_x + 48, row_y, alpha)
        blit_alpha(line, panel_x + 72, row_y, alpha)
    bar_w = int((panel_w - 72) * min(1.0, max(0, (t - 42) / max(1, BRIEFING_DURATION - 92))))
    bar_y = panel_y + panel_h - 34
    pygame.draw.rect(screen, (10, 20, 30), (panel_x + 36, bar_y, panel_w - 72, 5))
    pygame.draw.rect(screen, C_KRAP_BLUE, (panel_x + 36, bar_y, bar_w, 5))
    prompt_txt = "PRESS SPACE TO DEPLOY" if t > 115 else "DECODING FIELD TRANSMISSION..."
    prompt_col = C_ORANGE if t > 115 else (95, 125, 145)
    prompt = font_terminal_small.render(prompt_txt, True, prompt_col)
    if t <= 115 or (pygame.time.get_ticks() // 450) % 2 == 0:
        blit_alpha(prompt, WIDTH // 2 - prompt.get_width() // 2, panel_y + panel_h + 22, min(255, t * 5))
    draw_scanlines(screen)
    draw_vignette(screen, strength=155)


# ─────────────────────────────────────────────
# DEV ARGS
# ─────────────────────────────────────────────

def _apply_dev_args():
    global mission_complete_saved, _frozen_cx, _frozen_cy
    args = set(sys.argv[1:])
    if "--dev-safe" in args or "--m1-safe" in args or "--safe" in args:
        # Mission 1 safe/keypad debug jump. Opens the safe keypad immediately
        # so Easter eggs / keypad behavior can be tested without clearing the
        # warehouse first.
        gc.mission_start_time = pygame.time.get_ticks()
        gc.mission_end_time = 0
        mission_complete_saved = False
        gc.start_mission(preserve_timer=True)
        try:
            import mission as _m1
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
        gc.mission_start_time = pygame.time.get_ticks()
        gc.mission_end_time = 0
        mission_complete_saved = False
        start_cutscene(gc.mission2_intro_shots, "MISSION2", use_fades=False)
        gsm.transition("CUTSCENE")
        pygame.mouse.set_visible(True)
    elif "--dev-mission2-game" in args or "--m2-game" in args:
        gc.mission_start_time = pygame.time.get_ticks()
        gc.mission_end_time = 0
        mission_complete_saved = False
        gc.start_mission2(preserve_timer=True)
        gsm.transition("GAME")
        pygame.mouse.set_visible(False)
    elif "--dev-mission2-sniper" in args or "--m2-sniper" in args:
        gc.mission_start_time = pygame.time.get_ticks()
        gc.mission_end_time = 0
        mission_complete_saved = False
        gc.start_mission2_sniper(preserve_timer=True)
        gsm.transition("GAME")
        pygame.mouse.set_visible(False)
    elif "--dev-mission2-after-sniper" in args or "--m2-after-sniper" in args:
        gc.mission_start_time = pygame.time.get_ticks()
        gc.mission_end_time = 0
        mission_complete_saved = False
        gc.start_mission2_after_sniper(preserve_timer=True)
        gsm.transition("GAME")
        pygame.mouse.set_visible(False)
    elif "--dev-mission2-flank" in args or "--m2-flank" in args:
        gc.mission_start_time = pygame.time.get_ticks()
        gc.mission_end_time = 0
        mission_complete_saved = False
        gc.start_mission2_flank(preserve_timer=True)
        gsm.transition("GAME")
        pygame.mouse.set_visible(False)
    elif "--dev-mission2-truck" in args or "--m2-truck" in args:
        gc.mission_start_time = pygame.time.get_ticks()
        gc.mission_end_time = 0
        mission_complete_saved = False
        gc.start_mission2_truck(preserve_timer=True)
        gsm.transition("GAME")
        pygame.mouse.set_visible(False)
    elif "--dev-mission2-evidence" in args or "--m2-evidence" in args:
        gc.mission_start_time = pygame.time.get_ticks()
        gc.mission_end_time = 0
        mission_complete_saved = False
        gc.start_mission2_evidence_debug(preserve_timer=True)
        gsm.transition("GAME")
        pygame.mouse.set_visible(False)
    elif ("--dev-mission3-archives" in args or "--m3-archives" in args
          or "--m3-part3" in args or "--dev-m3-part3" in args
          or "--m3-phase4" in args):
        # Skip straight to Mission 3 Phase 4 — Archives Wing.
        gc.mission_start_time = pygame.time.get_ticks()
        gc.mission_end_time = 0
        mission_complete_saved = False
        try:
            import mission3
            mission3.start_mission3_archives_checkpoint(preserve_timer=True)
        except Exception as _m3_arch_err:
            print(f"--m3-archives setup failed: {_m3_arch_err}")
            gc.start_mission3(preserve_timer=True)
        gsm.transition("GAME")
        pygame.mouse.set_visible(False)
    elif ("--dev-mission3-comms" in args or "--m3-comms" in args
          or "--m3-part2" in args or "--dev-m3-part2" in args):
        # Skip to Mission 3's second playable slice, but still play the
        # service-door -> radio -> comms-wing transition cutscene first.
        gc.mission_start_time = pygame.time.get_ticks()
        gc.mission_end_time = 0
        mission_complete_saved = False
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
        gc.mission_start_time = pygame.time.get_ticks()
        gc.mission_end_time = 0
        mission_complete_saved = False
        try:
            import mission3
            mission3.start_black_ledger_debug()
        except Exception as _ledger_err:
            print(f"--m3-ledger setup failed: {_ledger_err}")
            gc.start_mission3(preserve_timer=True)
        gsm.transition("GAME")
        pygame.mouse.set_visible(False)
    elif "--dev-mission3" in args or "--m3" in args:
        gc.mission_start_time = pygame.time.get_ticks()
        gc.mission_end_time = 0
        mission_complete_saved = False
        gc.start_mission3(preserve_timer=True)
        start_cutscene(gc.mission3_intro_shots, "GAME", use_fades=True)
        trigger_transition("CUTSCENE")
        pygame.mouse.set_visible(True)
    elif ("--dev-mission3-game" in args or "--m3-game" in args
          or "--dev-m3-game" in args or "--m3-skip" in args):
        # NEW: skip the Mission 3 intro/breach/interrogation cutscenes and
        # drop straight into playable breakout gameplay (post-Volkov-breach,
        # with the chair leg; you still sharpen the shiv at the drain).
        # Mirrors start_mission3_breakout_checkpoint().
        gc.mission_start_time = pygame.time.get_ticks()
        gc.mission_end_time = 0
        mission_complete_saved = False
        try:
            import mission3
            mission3.start_mission3_breakout_checkpoint(preserve_timer=True)
        except Exception as _m3_dev_err:
            print(f"--dev-mission3-game setup failed: {_m3_dev_err}")
            gc.start_mission3(preserve_timer=True)
        gsm.transition("GAME")
        pygame.mouse.set_visible(False)
        pygame.mouse.set_visible(True)


# ═══════════════════════════════════════════════
# FSM STATE CLASSES — FULLY MIGRATED
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
        boot = font_terminal_small.render("RETARDOVICI INC. // STUDIO IDENT", True, (90, 104, 110))
        boot.set_alpha(label_a)
        surface.blit(boot, (56, 54))
        pygame.draw.line(surface, (70, 26, 24), (52, 48), (220, 48), 1)
        pygame.draw.line(surface, (70, 26, 24), (WIDTH - 220, 48), (WIDTH - 52, 48), 1)

        self._draw_retardovici_r_logo(surface, WIDTH // 2, HEIGHT // 2 - 70, t, a)

        # Wordmark.
        name_p = self._smooth((t - 138) / 50.0)
        name_alpha = int(a * name_p)
        title = font_title.render("RETARDOVICI", True, (232, 238, 235))
        title = pygame.transform.smoothscale(title, (int(title.get_width() * 0.78), int(title.get_height() * 0.78)))
        title.set_alpha(name_alpha)
        x = WIDTH // 2 - title.get_width() // 2
        y = HEIGHT // 2 + 92
        sh = title.copy()
        sh.fill((0, 0, 0, min(235, name_alpha)), special_flags=pygame.BLEND_RGBA_MULT)
        surface.blit(sh, (x + 4, y + 4))
        surface.blit(title, (x, y))

        inc = font_terminal.render("I  N  C .", True, (206, 214, 210))
        inc.set_alpha(name_alpha)
        ix = WIDTH // 2 - inc.get_width() // 2
        iy = y + 66
        ish = font_terminal.render("I  N  C .", True, (0, 0, 0))
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
            txt = font_terminal_small.render("PRESENTS", True, (150, 116, 84))
            txt.set_alpha(int(a * strip_p))
            strip.blit(txt, (strip_w // 2 - txt.get_width() // 2, 7))
            surface.blit(strip, (WIDTH // 2 - strip_w // 2, HEIGHT // 2 + 214))

        # Small reveal glitch only, not persistent clutter.
        if 82 < t < 104 and t % 5 in (0, 1):
            gr = pygame.Surface((WIDTH, 20), pygame.SRCALPHA)
            gr.fill((170, 28, 24, 42))
            surface.blit(gr, (random.randint(-10, 10), HEIGHT // 2 + random.randint(-84, 84)))

        if t > 205 and (pygame.time.get_ticks() // 700) % 2 == 0:
            hint = font_terminal_small.render("SPACE / ENTER TO SKIP", True, (82, 76, 66))
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

    def handle_event(self, event, mouse_x, mouse_y, keys):
        global mission_complete_saved, slot_select_purpose, menu_notice, menu_notice_timer
        if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            gsm.transition("MENU")
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            data = save_system.load_data()
            for i, rect in enumerate(_slot_rects):
                if rect.collidepoint(mouse_x, mouse_y):
                    if slot_select_purpose == "continue" and not data["slots"][i].get("occupied"):
                        continue
                    save_system.select_slot(i)
                    audio.play("menu_click", volume=0.5)
                    if slot_select_purpose == "new":
                        save_system.start_new_campaign(i)
                        gc.mission_start_time = pygame.time.get_ticks()
                        gc.mission_end_time = 0
                        mission_complete_saved = False
                        start_cutscene(gc.cutscene1_shots, "WALK", use_fades=False)
                        trigger_transition("CUTSCENE")
                    else:
                        slot = save_system.get_slot(i)
                        if slot.get("last_completed_mission") == "MISSION_1":
                            gc.mission_start_time = pygame.time.get_ticks()
                            gc.mission_end_time = 0
                            mission_complete_saved = False
                            start_cutscene(gc.mission2_intro_shots, "MISSION2", use_fades=False)
                            trigger_transition("CUTSCENE")
                        elif slot.get("last_completed_mission") == "MISSION_2":
                            gc.mission_start_time = pygame.time.get_ticks()
                            gc.mission_end_time = 0
                            mission_complete_saved = False
                            gc.start_mission3(preserve_timer=True)
                            gsm.transition("GAME")
                            pygame.mouse.set_visible(False)
                        else:
                            menu_notice = "SAVE SELECTED — NO CHECKPOINT RESUME YET"
                            menu_notice_timer = 200
                            gsm.transition("MENU")
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
        global mp_state, mp_selected, mp_kick_msg, mp_timer
        if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            if mp_state == "kicked":
                mp_state = "browser"
                mp_kick_msg = ""
                mp_selected = -1
            elif menu._dm_open_user is not None:
                menu.close_dm()
            else:
                gsm.transition("MENU")
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
                        menu._dm_input = menu._dm_input[:-1]
                    elif event.unicode and event.unicode.isprintable() and len(menu._dm_input) < 200:
                        menu._dm_input += event.unicode
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                menu.server_back_btn.is_hovered = False
                if menu.server_back_btn.rect.collidepoint(get_scaled_mouse()):
                    gsm.transition("MENU")
                elif menu.servers_tab_rect.collidepoint(get_scaled_mouse()):
                    menu.switch_mp_tab("SERVERS")
                elif menu.connections_tab_rect.collidepoint(get_scaled_mouse()):
                    menu.switch_mp_tab("CONNECTIONS")
                elif menu._mp_tab == "SERVERS":
                    if menu.refresh_btn_rect.collidepoint(get_scaled_mouse()):
                        menu.trigger_server_refresh()
                    else:
                        cur_y = menu.SERVER_LIST_TOP
                        mp_scaled = get_scaled_mouse()
                        for vi in range(5):
                            i = vi + menu._scroll_offset
                            if i >= len(menu.server_list):
                                break
                            name = menu.server_list[i][0]
                            name_max_w = 320 - 24
                            lines = menu._wrap_server_name(name, menu.font_terminal, name_max_w)
                            row_h = 64 if len(lines) > 1 else 50
                            row_rect = pygame.Rect(
                                menu.SERVER_ROW_X,
                                cur_y,
                                menu.SERVER_ROW_W,
                                row_h - 4,
                            )
                            if row_rect.collidepoint(mp_scaled):
                                mp_selected = i
                                mp_state = "connecting"
                                mp_timer = 180
                                break
                            cur_y += row_h + 5
                elif menu._mp_tab == "CONNECTIONS":
                    list_x = menu.SERVER_PANEL_X + 28
                    list_y = menu.SERVER_LIST_TOP - 4
                    list_w = 340
                    row_h = 38
                    list_bottom_limit = menu.SERVER_PANEL_Y + menu.SERVER_PANEL_H - 90
                    visible_friends = (list_bottom_limit - list_y) // row_h
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

    def update(self, dt):
        global mp_state, mp_timer, mp_selected, mp_kick_msg
        menu.update_server_browser_animation()
        menu.update_dm_state()
        if mp_state == "connecting":
            mp_timer -= 1
            if mp_timer <= 0:
                mp_state = "kicked"
                if 0 <= mp_selected < len(menu.server_list):
                    server_name = menu.server_list[mp_selected][0]
                    mp_kick_msg = menu.get_kick_message_for_server(server_name)
                else:
                    mp_kick_msg = random.choice(menu.KICK_MESSAGES)
                mp_timer = 0

    def set_ambience(self):
        _set_ambience(set())

    def render(self, surface):
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

    def handle_event(self, event, mouse_x, mouse_y, keys):
        global _settings_return_to
        if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            _persist_settings()
            gsm.transition(_settings_return_to)
            _settings_return_to = "MENU"
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
            gc.game_draw(_frozen_cx, _frozen_cy)
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
        )


class _CutsceneState(GameState):
    name = "CUTSCENE"

    def _handle_end(self):
        """Called when the last shot finishes. Routes to after_state."""
        global mission_complete_saved, mission_complete_timer, mission_complete_fade
        after = active_cutscene.after_state
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
            mission_complete_saved = False
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
        elif after == "BRIEFING":
            start_briefing("warehouse")
            gsm.transition("BRIEFING")

    def handle_event(self, event, mouse_x, mouse_y, keys):
        if event.type != pygame.KEYDOWN or event.key != pygame.K_SPACE:
            return
        cp = active_cutscene
        if cp is None:
            return
        shot = cp.current_shot
        if shot is None:
            return
        if cp.char_idx < len(shot["text"]):
            cp.char_idx = len(shot["text"])
        else:
            elapsed_ms = pygame.time.get_ticks() - cp.start_time
            if elapsed_ms < shot.get("min_ms", 0):
                audio.play("menu_hover", volume=0.12)
                return
            if cp.shot_idx < len(cp.shots) - 1:
                audio.play("menu_click", volume=0.3)
                if cp.use_fades:
                    cp.transition_timer = 15  # fade out
                else:
                    cp.shot_idx += 1
                    cp.char_idx = 0
                    cp.timer = 0
                    cp.start_time = pygame.time.get_ticks()
                    gc.reset_dialogue_slide()
            else:
                self._handle_end()

    def update(self, dt):
        cp = active_cutscene
        if cp is None:
            return
        cp.timer += 1
        shot = cp.current_shot
        if shot is None:
            return
        # Handle shot-to-shot transition
        if cp.transition_timer > 0:
            cp.transition_timer -= 1
            if cp.transition_timer == 8:
                cp.shot_idx += 1
                cp.char_idx = 0
                cp.timer = 0
                cp.start_time = pygame.time.get_ticks()
                cp.transition_timer = -12  # fade in
        elif cp.transition_timer < 0:
            cp.transition_timer += 1
        # Typewriter effect
        if cp.char_idx < len(shot["text"]):
            if cp.timer >= TEXT_SPEED:
                cp.timer = 0
                last = shot["text"][max(0, cp.char_idx - 1)]
                if last in ".!?":
                    cp.timer -= 25
                elif last in ",;:":
                    cp.timer -= 12
                elif last == "-":
                    cp.timer -= 15
                next_ch = shot["text"][cp.char_idx] if cp.char_idx < len(shot["text"]) else ""
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
        t_ms = pygame.time.get_ticks() - cp.start_time
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
            draw_vignette(surface, strength=180)
            draw_scanlines(surface)
            draw_letterbox(surface)
            can_continue = (pygame.time.get_ticks() - cp.start_time) >= shot.get("min_ms", 0)
            if not shot.get("hide_caption") and (shot["text"] or shot.get("speaker")):
                gc.draw_dialogue_box(
                    surface,
                    shot["speaker"],
                    shot["text"],
                    cp.char_idx,
                    len(shot["text"]),
                    can_continue,
                )
            _g = _advance_grain()
            if _g is not None:
                surface.blit(_g, (0, 0))
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


class _GameState_(GameState):
    name = "GAME"

    def handle_event(self, event, mouse_x, mouse_y, keys):
        # Mission 3 interrogation phase
        if getattr(gc, "active_mission", "MISSION1") == "MISSION3":
            _m3_stage = getattr(gc, "mission3_stage", "interrogation")
            _is_escape = (event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE)
            if _m3_stage == "interrogation" and not _is_escape:
                try:
                    import mission3
                    mission3.handle_event(event)
                except ImportError:
                    pass
                return
            elif _is_escape:
                gsm.transition("PAUSED")
                return

        # Mission 2 intel cards
        if getattr(gc, "active_mission", "MISSION1") == "MISSION2" and getattr(gc, "mission2_card", None):
            if event.type == pygame.KEYDOWN and event.key in (pygame.K_e, pygame.K_SPACE, pygame.K_RETURN, pygame.K_ESCAPE):
                gc.handle_interact()
            return

        # Upload OS
        if getattr(gc, "active_mission", "MISSION1") == "MISSION2":
            try:
                import upload_os
                if upload_os.is_upload_os_active():
                    upload_os.handle_upload_os_event(event)
                    return
            except ImportError:
                pass

        # Mission 3 crafting overlay
        if getattr(gc, "active_mission", "MISSION1") == "MISSION3":
            try:
                import mission3
                if mission3.is_crafting_active():
                    mission3.handle_crafting_event(event)
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
        global _frozen_cx, _frozen_cy, mission_complete_saved, mission_complete_timer, mission_complete_fade

        if gc.request_death_screen:
            gc.request_death_screen = False
            if not gc.mission_end_time:
                gc.mission_end_time = pygame.time.get_ticks()
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
            import ui_hud; ui_hud.reset_notebook_inspect()
            return

        cx, cy = gc.game_update(keys)
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
        elif gc.request_mission_complete:
            gc.request_mission_complete = False
            if not gc.mission_end_time:
                gc.mission_end_time = pygame.time.get_ticks()
            gsm.transition("MISSION_COMPLETE")
            mission_complete_timer = 0
            mission_complete_fade = 0

    def set_ambience(self):
        if getattr(gc, "active_mission", "MISSION1") == "MISSION2":
            _set_ambience({"ambient_drone", "rain", "wind"})
        else:
            _set_ambience(set())

    def render(self, surface):
        gc.game_draw(_frozen_cx, _frozen_cy)
        _g = _advance_grain()
        if _g is not None:
            surface.blit(_g, (0, 0))
        gc.draw_desk_note()
        gc.draw_safe_keypad()
        import ui_hud as _hud
        try:
            import upload_os
            if not upload_os.is_upload_os_active():
                _hud.draw_gameplay_crosshair()
        except ImportError:
            _hud.draw_gameplay_crosshair()


class _EscapeCutsceneState(GameState):
    name = "ESCAPE_CUTSCENE"

    def handle_event(self, event, mouse_x, mouse_y, keys):
        global mission_complete_timer, mission_complete_fade
        if event.type == pygame.KEYDOWN and event.key in (pygame.K_SPACE, pygame.K_RETURN):
            gc.mission_end_time = pygame.time.get_ticks()
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
            gc.mission_end_time = pygame.time.get_ticks()
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
        gc.game_draw(_frozen_cx, _frozen_cy)
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

    def handle_event(self, event, mouse_x, mouse_y, keys):
        global _settings_return_to
        if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            gsm.transition(_PausedState._return_to)
            pygame.mouse.set_visible(False)
        if menu.pause_buttons[0].is_clicked(event, (mouse_x, mouse_y)):
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
            gc.game_draw(_frozen_cx, _frozen_cy)
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
                # Save the checkpoint flag BEFORE the fallback — start_mission2()
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
                        import mission2
                        # If the checkpoint was reached, retry the checkpoint
                        # respawn before falling back to a full mission restart.
                        # The first failure (inside restart_current_mission →
                        # start_mission2_checkpoint) may have been transient
                        # (audio state, partial initialization race). The retry
                        # calls start_mission2_checkpoint() which re-runs
                        # start_mission2() (STATE.reset + full init) so STATE
                        # is clean — this isn't retrying on corrupted state.
                        _checkpoint_retry_ok = False
                        if _checkpoint_was_reached:
                            try:
                                mission2.start_mission2_checkpoint(preserve_timer=False)
                                _checkpoint_retry_ok = True
                            except Exception:
                                traceback.print_exc()
                        if not _checkpoint_retry_ok:
                            # Full mission restart as last resort. Preserve
                            # the checkpoint flag so the next death respawn
                            # uses the checkpoint instead of restarting the
                            # entire mission from the intro cutscene.
                            mission2.start_mission2(preserve_timer=False)
                            if _checkpoint_was_reached:
                                STATE.mission2_checkpoint_reached = True
                    elif getattr(STATE, "active_mission", "MISSION1") == "MISSION3":
                        import mission3
                        if getattr(STATE, "mission3_comms_checkpoint_reached", False):
                            mission3.start_mission3_comms_checkpoint(preserve_timer=False)
                        elif getattr(STATE, "mission3_breakout_checkpoint_reached", False):
                            mission3.start_mission3_breakout_checkpoint(preserve_timer=False)
                        else:
                            mission3.start_mission3(preserve_timer=False)
                    else:
                        import mission
                        mission.start_mission(preserve_timer=False)
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
                import mission3
                mission3._draw_black_ledger_death_overlay()
            except Exception:
                # If the custom renderer ever fails, fall back to the normal
                # death screen rather than trapping the player.
                gc.game_draw(_frozen_cx, _frozen_cy)
            menu.draw_black_ledger_death_buttons()
            return

        gc.game_draw(_frozen_cx, _frozen_cy)
        _g = _advance_grain()
        if _g is not None:
            surface.blit(_g, (0, 0))
        menu.draw_death_screen()


class _MissionCompleteState(GameState):
    name = "MISSION_COMPLETE"

    def enter(self):
        global mission_complete_timer, mission_complete_fade, mission_complete_saved
        mission_complete_timer = 0
        mission_complete_fade = 0

    def handle_event(self, event, mouse_x, mouse_y, keys):
        global mission_complete_saved
        if event.type == pygame.KEYDOWN and event.key in (pygame.K_SPACE, pygame.K_RETURN):
            if getattr(gc, "active_mission", "MISSION1") == "MISSION1":
                gc.mission_start_time = pygame.time.get_ticks()
                gc.mission_end_time = 0
                mission_complete_saved = False
                start_cutscene(gc.mission2_intro_shots, "MISSION2", use_fades=False)
                trigger_transition("CUTSCENE")
            elif getattr(gc, "active_mission", "MISSION1") == "MISSION2":
                # Campaign flow: Mission 2 completion should lead into the
                # Mission 3 intro cutscene, not drop directly into gameplay.
                # The cutscene's after_state="GAME" path then transitions
                # cleanly into Mission 3 gameplay once the intro finishes.
                gc.mission_start_time = pygame.time.get_ticks()
                gc.mission_end_time = 0
                mission_complete_saved = False
                gc.start_mission3(preserve_timer=True)
                start_cutscene(gc.mission3_intro_shots, "GAME", use_fades=True)
                trigger_transition("CUTSCENE")
                pygame.mouse.set_visible(True)
            else:
                trigger_transition("MENU")
                pygame.mouse.set_visible(True)

    def update(self, dt):
        pass

    def set_ambience(self):
        _set_ambience(set())
        if mission_complete_timer == 1:
            audio.play("mission_complete", volume=0.6)

    def render(self, surface):
        global mission_complete_timer, mission_complete_fade, mission_complete_saved
        mission_complete_timer += 1
        mission_complete_fade = min(255, mission_complete_timer * 5)
        if not mission_complete_saved:
            report = _mission_report_data(success=True)
            if getattr(gc, "active_mission", "MISSION1") == "MISSION2":
                save_system.save_mission_complete(
                    "MISSION_2",
                    "Mission 2 — Quiet on Route 12",
                    report["time_str"],
                    stats=report,
                    flags={"mission1_complete": True, "mission2_complete": True},
                )
            else:
                save_system.save_mission_complete(
                    "MISSION_1",
                    "Mission 1 — Black Notebook",
                    report["time_str"],
                    stats=report,
                    flags={"mission1_complete": True},
                )
            mission_complete_saved = True

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

        # Header area
        pygame.draw.rect(surface, (6, 10, 16, 240),
                         (card_x + 4, card_y, card_w - 4, 42))
        pygame.draw.line(surface, (35, 60, 85),
                         (card_x + 16, card_y + 42),
                         (card_x + card_w - 16, card_y + 42), 1)
        eyebrow = font_terminal_small.render(
            "KRAP INTEL — AFTER ACTION REPORT", True, (60, 120, 170))
        _mc_text(eyebrow,
                 card_x + card_w // 2 - eyebrow.get_width() // 2,
                 card_y + 8, mission_complete_fade)
        classif = font_terminal_small.render("CLASSIFIED", True, (180, 60, 50))
        _mc_text(classif, card_x + card_w - classif.get_width() - 20,
                 card_y + 8, mission_complete_fade)
        title_font = pygame.font.SysFont("Consolas", 32, bold=True)
        title_surf = title_font.render("MISSION COMPLETE", True, (200, 198, 190))
        _mc_text(title_surf,
                 card_x + card_w // 2 - title_surf.get_width() // 2,
                 card_y + 56, mission_complete_fade)
        op_name = getattr(gc, "active_mission_operation", "WAREHOUSE RAID — BLACK NOTEBOOK")
        op = font_terminal.render(op_name, True, (160, 155, 145))
        _mc_text(op,
                 card_x + card_w // 2 - op.get_width() // 2,
                 card_y + 96, mission_complete_fade)
        outcome_line = getattr(gc, "active_mission_outcome", "Target escaped  ·  Notebook recovered  ·  Questions remain")
        out = font_terminal_small.render(outcome_line, True, (150, 120, 90))
        _mc_text(out,
                 card_x + card_w // 2 - out.get_width() // 2,
                 card_y + 120, mission_complete_fade)
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
            quote = font_dialogue.render(
                getattr(gc, "active_mission_quote", '"Bring it straight to me. Don\'t read it."'),
                True, C_VASILE)
            quote.set_alpha(q_fade)
            surface.blit(quote,
                         (card_x + card_w // 2 - quote.get_width() // 2,
                          card_y + 362))

        # Bottom bar
        pygame.draw.line(surface, (35, 60, 85),
                         (card_x + 16, card_y + card_h - 34),
                         (card_x + card_w - 16, card_y + card_h - 34), 1)
        footer = font_terminal_small.render(
            "KRAP INTELLIGENCE DIVISION — FIELD COPY", True, (45, 65, 80))
        _mc_text(footer,
                 card_x + card_w // 2 - footer.get_width() // 2,
                 card_y + card_h - 26, mission_complete_fade)

        # Continue prompt
        if mission_complete_timer > 120 and (pygame.time.get_ticks() // 600) % 2 == 0:
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
    _BootIntroState,
    _MenuState, _SlotSelectState, _MultiplayerState, _SettingsState,
    _CutsceneState, _BriefingState, _WalkState, _GameState_,
    _EscapeCutsceneState, _NotebookInspectState, _PausedState,
    _DeathState, _MissionCompleteState,
):
    gsm.add(_state_cls())

gsm.transition("BOOT_INTRO")
_apply_dev_args()

# ─────────────────────────────────────────────
# DEV TOOLS — Level Editor & Console
# ─────────────────────────────────────────────
level_editor = LevelEditor()
console = Console()

def _update_editor_map():
    mission = getattr(gc, "active_mission", "MISSION1")
    try:
        if mission == "MISSION1":
            import mission
            level_editor.set_map(mission.mission1_map, map_name="mission1")
        elif mission == "MISSION2":
            import mission2
            level_editor.set_map(mission2.MISSION2_MAP, map_name="mission2")
        elif mission == "MISSION3":
            import mission3
            level_editor.set_map(mission3.MISSION3_MAP, map_name="mission3")
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
# MAIN LOOP — CLEAN FSM DISPATCH
# ═══════════════════════════════════════════════

MAX_DT = 0.05
running = True

while running:
    dt = min(clock.tick(60) / 1000.0, MAX_DT)
    STATE.dt = dt
    mouse_x, mouse_y = get_scaled_mouse()
    keys = pygame.key.get_pressed()

    if hasattr(audio, "update"):
        audio.update()

    # ── Mouse visibility ──
    current_name = gsm.current_name
    mouse_visible = current_name not in ("GAME", "WALK")
    if current_name == "GAME":
        if level_editor.active:
            mouse_visible = True
        else:
            try:
                import upload_os
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
                from user_settings import SETTINGS as _s
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
            _persist_settings()
            continue

        # F12 — Level Editor toggle (gameplay only)
        if event.type == pygame.KEYDOWN and event.key == pygame.K_F12:
            if gsm.current_name == "GAME":
                if level_editor.map_data is None:
                    _update_editor_map()
                level_editor.toggle()
            continue

        # `~` — Developer Console toggle (any state)
        if event.type == pygame.KEYDOWN and event.key == pygame.K_BACKQUOTE:
            console.toggle()
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
    if not gsm.transitioning:
        gsm.current.update(dt)

    # ── Ambience dispatch ──
    gsm.current.set_ambience()
    # Stream menu music on menu-family states
    music_state = gsm.next_state if gsm.transitioning and gsm.fade_speed > 0 else current_name
    _set_menu_music(music_state in MENU_MUSIC_STATES)

    # ── Render dispatch ──
    gsm.current.render(screen)

    # ── Dev tool overlays ──
    level_editor.draw(screen)
    console.draw(screen)

    # ── FSM transition overlay ──
    gsm.update_transition()
    gsm.draw_transition(screen)

    # ── Global post-processing ──
    _apply_postprocess()

    _present_frame()
    pygame.display.flip()

pygame.quit()
sys.exit()
