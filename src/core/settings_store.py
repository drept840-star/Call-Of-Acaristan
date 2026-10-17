
"""Settings store - persistent JSON-backed user preferences.

Expanded from the original 6-field store to a full settings schema covering
Display, Audio, Gameplay, Graphics, Controls, and Accessibility. The load()
function merges saved values over a default dict, so missing keys (from old
save files) always fall back to sane defaults - no migration step needed.

save() merges the caller's dict over the currently loaded settings before
writing, so keys the caller doesn't know about (e.g. ambience_layers) are
never dropped. Writes are atomic via core.json_store.
"""
from pathlib import Path
import os

from core import json_store
from engine.settings import BOOL as _BOOL
from engine.settings import ENUM as _ENUM
from engine.settings import INT as _INT
from engine.settings import STR as _STR
from engine.settings import Field as _Field
from engine.settings import env_layer as _env_layer
from engine.settings import resolve as _resolve

# Mirrors save_system.ACA_SAVE_SUFFIX so the duo launcher can sandbox
# both files per process (settings_p1.json / settings_p2.json).
_SAVE_SUFFIX = os.environ.get("ACA_SAVE_SUFFIX", "")
SAVE_FILE = str(Path(__file__).resolve().parents[2] / ("settings%s.json" % _SAVE_SUFFIX))

# ── Default settings ──
# Every key here MUST have a default; load() only overrides keys that exist
# in the saved JSON, so adding new keys later is always backward-compatible.
_DEFAULTS = {
    # ── Display ──
    "display_mode": 0,            # 0=Windowed, 1=Fullscreen
    "resolution_idx": 0,          # index into SETTINGS_RESOLUTIONS
    # ── Audio ──
    "master_volume": 80,
    "music_volume": 70,
    "sfx_volume": 85,
    "mute_on_focus_loss": True,
    # ── Gameplay ──
    "crosshair": True,
    "crosshair_size": 6,          # 3=small, 6=medium, 10=large
    "auto_reload": True,
    "aim_assist": False,
    "subtitles": True,
    "radio_text_size": 1,        # 0=small, 1=medium, 2=large (ui.radio)
    "radio_speaker_names": True,  # callsign plate on radio transmissions
    # ── Graphics ──
    "brightness": 50,             # 0-100, 50 = neutral
    "scanlines": True,
    "grain": True,
    "particle_density": 75,       # 0-100, scales particle counts
    # ── Controls ──
    "mouse_sensitivity": 50,      # 0-100, 50 = default
    "invert_mouse": False,
    # ── Accessibility ──
    "reduced_motion": False,
    "shake_scale": 100,           # percent; scales gameplay shake + cutscene handheld (P9)
    "flash_reduction": False,     # caps full-screen white flashes (P9)
    "quality_3d": 2,              # 0=off, 1=low, 2=high: local lights/shadows/AO (P11)
    "text_speed": 1,              # 0=slow, 1=normal, 2=fast typewriter (P9)
    "ambience_layers": True,   # False = no room tone/hum/drips/gusts loops
    "colorblind_mode": 0,         # 0=off, 1=protanopia, 2=deuteranopia, 3=tritanopia
    # ── Multiplayer ──
    # The name you play under in an arena match. Deliberately NOT the lobby
    # nickname: that one is what strangers see in the GLOBAL CHAT panel next
    # to a server list, this one is what goes over your head while somebody
    # is actively trying to shoot you. Empty means "not chosen yet", and the
    # arena entry panel makes you choose one.
    "player_name": "",
}


_PERCENT_KEYS = {"master_volume", "music_volume", "sfx_volume", "brightness",
                 "particle_density", "mouse_sensitivity", "shake_scale"}
_ENUM_VALUES = {"display_mode": (0, 1), "resolution_idx": (0, 1, 2),
                "crosshair_size": (3, 6, 10), "colorblind_mode": (0, 1, 2, 3),
                "radio_text_size": (0, 1, 2), "text_speed": (0, 1, 2),
                "quality_3d": (0, 1, 2)}

# RPE6 P9: the typed schema (engine.settings) the normaliser runs on.
_SCHEMA = []
for _key, _default in _DEFAULTS.items():
    if _key in _ENUM_VALUES:
        _SCHEMA.append(_Field(_key, _ENUM, _default, "settings", values=_ENUM_VALUES[_key]))
    elif _key in _PERCENT_KEYS:
        _SCHEMA.append(_Field(_key, _INT, _default, "settings", minimum=0, maximum=100))
    elif isinstance(_default, bool):
        _SCHEMA.append(_Field(_key, _BOOL, _default, "settings"))
    elif isinstance(_default, int):
        _SCHEMA.append(_Field(_key, _INT, _default, "settings"))
    elif isinstance(_default, str):
        _SCHEMA.append(_Field(_key, _STR, _default, "settings"))


def _normalize(values):
    """Validate known preferences while preserving unrelated/forward-version keys."""
    resolved, _problems = _resolve(_SCHEMA, values)
    return resolved


def load():
    """Load a complete validated profile, falling back to defaults or backup.

    Layers (RPE6 §6.18): schema defaults < settings file < ACARISTAN_* env.
    """
    saved = json_store.load_with_backup(SAVE_FILE, dict)
    resolved, _problems = _resolve(
        _SCHEMA, saved if isinstance(saved, dict) else {},
        _env_layer(_SCHEMA, os.environ))
    return resolved


def save(settings_dict):
    """Merge and write atomically. Return True only after the commit succeeds."""
    try:
        merged = load()
        merged.update(settings_dict)
        json_store.atomic_write(SAVE_FILE, _normalize(merged))
        return True
    except Exception as e:
        print(f"Settings save failed: {e}")
        # An incomplete temporary file is not a saved profile.
        try:
            Path(SAVE_FILE + ".tmp").unlink(missing_ok=True)
        except OSError:
            pass
        return False


# Generous against the protocol's own cap (net/protocol.MAX_NAME_CHARS) so a
# legitimate name is never truncated by the store, but short enough that a
# hand-edited settings file cannot put a paragraph over somebody's head. The
# protocol sanitizes again on the way onto the wire; this bound is about the
# file, not the network.
PLAYER_NAME_MAX = 64


def player_name():
    """The remembered arena name, or '' when the player has not chosen one."""
    value = load().get("player_name", "")
    if not isinstance(value, str):
        return ""
    return value.strip()[:PLAYER_NAME_MAX]


def set_player_name(name):
    """Remember *name* for the next session. Never raises.

    Returns what was actually stored, or '' if the write failed, so the
    caller can keep showing the typed value rather than pretending it saved.
    """
    try:
        value = str(name or "").strip()[:PLAYER_NAME_MAX]
        save({"player_name": value})
        return value
    except Exception as e:
        print(f"Player name save failed: {e}")
        return ""
