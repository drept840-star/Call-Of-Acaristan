"""Mission checkpoint ladders: detect, persist, resume, label, toast.

Missions keep owning their checkpoint flags and loaders. This module only
reads the flags (deepest first), writes the reached token plus the player's
loadout on arrival to the save slot, and replays loader + loadout on a death
restart (game_core.restart_current_mission) or on Continue (app.py).
M7 is stage-based and persists itself (missions.m7.flow), so it is not here.
"""
import math

import pygame

from core.state import STATE
from core import save_system

# mission key -> (slot progress, rows deepest first)
# row: (STATE flag, slot token, game_core loader, failure-screen label)
LADDERS = {
    "MISSION1": ("m1", [
        ("m1_notebook_checkpoint_reached", "notebook", "start_mission1_notebook_checkpoint", "THE NOTEBOOK"),
    ]),
    "MISSION2": ("m2", [
        ("mission2_checkpoint_reached", "evidence", "start_mission2_checkpoint", "ROUTE 12 CHECKPOINT"),
        ("mission2_killbox_checkpoint_reached", "killbox", "start_mission2_killbox_checkpoint", "THE KILL BOX"),
    ]),
    "MISSION3": ("m3", [
        ("mission3_broadcast_checkpoint_reached", "broadcast", "start_mission3_broadcast_checkpoint", "BROADCAST WING"),
        ("mission3_kill_order_checkpoint_reached", "kill_order", "start_mission3_kill_order_checkpoint", "KILL ORDER"),
        ("mission3_archives_checkpoint_reached", "archives", "start_mission3_archives_checkpoint", "ARCHIVES"),
        ("mission3_comms_checkpoint_reached", "comms", "start_mission3_comms_checkpoint", "COMMS WING"),
        ("mission3_breakout_checkpoint_reached", "breakout", "start_mission3_breakout_checkpoint", "BREAKOUT"),
    ]),
    "MISSION4": ("m4", [
        ("mission4_tower_checkpoint_reached", "tower", "start_mission4_tower_checkpoint", "TRANSMITTER TOWER"),
        ("mission4_station_checkpoint_reached", "station", "start_mission4_station_checkpoint", "STATION"),
    ]),
    "MISSION5": ("m5", [
        ("mission5_tunnel_mid_checkpoint_reached", "tunnel_mid", "start_mission5_tunnel_mid_checkpoint", "TUNNEL JUNCTION"),
        ("mission5_tunnel_checkpoint_reached", "tunnel", "start_mission5_tunnel_checkpoint", "TUNNEL"),
        ("mission5_printworks_checkpoint_reached", "printworks", "start_mission5_printworks_checkpoint", "PRINTWORKS"),
        ("mission5_quarter_checkpoint_reached", "quarter", "start_mission5_quarter_checkpoint", "LOWER QUARTER"),
    ]),
    "MISSION6": ("m6", [
        ("m6_train_checkpoint_reached", "train", "start_mission6_train_checkpoint", "TRAIN"),
        ("m6_rail_checkpoint", "rail", "start_mission6_rail_checkpoint", "RAIL YARD"),
        ("m6_noman_checkpoint", "noman", "start_mission6_noman_checkpoint", "NO MAN'S LAND"),
    ]),
}

# The M4 siege restores its own per-wave hp/ammo snapshot within a session.
_OWN_LOADOUT = {("MISSION4", "tower")}

_LOADOUT_FIELDS = ("ammo_in_mag", "spare_mags", "current_weapon",
                   "os12_unlocked", "os12_ammo_in_mag", "os12_spare_mags",
                   "k9_unlocked", "k9_ammo_in_mag", "k9_spare_mags", "player_bottles")
_HP_FLOOR = 0.3          # never respawn a player into a fight at a sliver of health

_seen = {"key": None, "token": None}
_loadouts = {}           # (key, token) -> loadout captured on arrival this session
_toast = {"t": 0, "label": ""}
_TOAST_FRAMES = 200
_ICON_FRAMES = 80


def deepest(key=None, state=STATE):
    """Deepest reached ladder row for ``key`` (default: the active mission)."""
    entry = LADDERS.get(key or getattr(state, "active_mission", ""))
    for row in entry[1] if entry else ():
        if getattr(state, row[0], False):
            return row
    return None


def capture_loadout():
    out = {f: getattr(STATE, f) for f in _LOADOUT_FIELDS if hasattr(STATE, f)}
    p = getattr(STATE, "player", None)
    if p is not None and hasattr(p, "hp"):
        out["hp"] = p.hp
    return out


def apply_loadout(loadout):
    for f in _LOADOUT_FIELDS:
        if f in loadout:
            setattr(STATE, f, loadout[f])
    weapon = str(getattr(STATE, "current_weapon", ""))
    if (weapon == "os12" and not getattr(STATE, "os12_unlocked", False)) or (
            weapon.startswith("k9") and not getattr(STATE, "k9_unlocked", False)):
        STATE.current_weapon = "pistol"
    p = getattr(STATE, "player", None)
    if p is not None and "hp" in loadout:
        p.hp = max(int(loadout["hp"]), int(p.max_hp * _HP_FLOOR))


def poll():
    """Once per gameplay frame: persist a newly reached checkpoint and toast it."""
    key = getattr(STATE, "active_mission", "")
    if key not in LADDERS or getattr(STATE, "player", None) is None:
        return
    row = deepest(key)
    token = row[1] if row else ""
    if _seen["key"] == key and _seen["token"] == token:
        return
    _seen["key"], _seen["token"] = key, token
    loadout = capture_loadout() if row else {}
    if row:
        _loadouts[(key, token)] = loadout
        _toast["t"], _toast["label"] = _TOAST_FRAMES, row[3]
    try:
        save_system.set_slot_progress(LADDERS[key][0], checkpoint=token, loadout=loadout)
    except Exception as e:
        print(f"checkpoints: save failed: {e}")


def restart():
    """Death restart at the deepest checkpoint. Returns False when none is reached."""
    key = getattr(STATE, "active_mission", "")
    row = deepest(key)
    if row is None:
        return False
    from core import game_core as gc
    getattr(gc, row[2])(preserve_timer=False)
    loadout = _loadouts.get((key, row[1]))
    if loadout and (key, row[1]) not in _OWN_LOADOUT:
        apply_loadout(loadout)
    return True


def slot_row(slot):
    """(mission key, ladder row) for a save slot's checkpoint, or None."""
    progress, token = slot.get("progress", ""), slot.get("checkpoint", "")
    for key, (prog, rows) in LADDERS.items():
        if prog == progress:
            for row in rows:
                if row[1] == token:
                    return key, row
    return None


def resume_slot(slot):
    """Continue from a save slot's checkpoint. Returns False when the slot has none."""
    hit = slot_row(slot)
    if hit is None:
        return False
    key, row = hit
    from core import game_core as gc
    getattr(gc, row[2])(preserve_timer=True)
    loadout = dict(slot.get("loadout") or {})
    if loadout:
        apply_loadout(loadout)
        _loadouts[(key, row[1])] = loadout
    _seen["key"], _seen["token"] = key, row[1]
    return True


def draw(surface):
    """CHECKPOINT toast with a save spinner, bottom-right, over any mission HUD."""
    if _toast["t"] <= 0:
        return
    from ui import pixfont
    t = _toast["t"]
    _toast["t"] -= 1
    alpha = 255 if t > 40 else int(255 * t / 40)
    big, small = pixfont.font("R7", 3, bold=True), pixfont.font("R7", 2)
    title, sub = big.render("CHECKPOINT", color=(236, 226, 196)), small.render(_toast["label"], color=(255, 150, 60))
    w = max(title.get_width(), sub.get_width()) + 44
    h = title.get_height() + sub.get_height() + 16
    sw, sh = surface.get_size()
    x, y = sw - w - 24, sh - h - 24
    panel = pygame.Surface((w, h), pygame.SRCALPHA)
    panel.fill((8, 10, 14, 170))
    pygame.draw.rect(panel, (255, 150, 60, 200), (0, 0, 3, h))
    panel.blit(title, (34, 6))
    panel.blit(sub, (34, 10 + title.get_height()))
    if _TOAST_FRAMES - t < _ICON_FRAMES:      # save spinner while the slot is written
        cx, cy, spin = 18, h // 2, (_TOAST_FRAMES - t) // 4
        for i in range(8):
            a = (i + spin) * math.pi / 4
            shade = 90 + 20 * i
            panel.fill((shade, shade, shade, 255),
                       (int(cx + 7 * math.cos(a)) - 1, int(cy + 7 * math.sin(a)) - 1, 3, 3))
    else:
        pygame.draw.rect(panel, (236, 226, 196, 255), (12, h // 2 - 6, 12, 12), 2)   # floppy: done
        panel.fill((236, 226, 196, 255), (15, h // 2 - 6, 6, 4))
    panel.set_alpha(alpha)
    surface.blit(panel, (x, y))
