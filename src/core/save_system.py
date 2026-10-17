
"""3-slot JSON save system for campaign progress.

Files live at the project root (not the CWD) and are written atomically via
``core.json_store`` - a crash mid-write can never corrupt the only copy.
"""
import os
import time
from pathlib import Path

from core import json_store

# ACA_SAVE_SUFFIX lets two game processes run side-by-side (e.g. the
# tools/mp_arena_duo.py host + join pair) without overwriting each
# other's progress: ACA_SAVE_SUFFIX=_p1 -> save_data_p1.json.
_SAVE_SUFFIX = os.environ.get("ACA_SAVE_SUFFIX", "")
SAVE_FILE = str(Path(__file__).resolve().parents[2] / ("save_data%s.json" % _SAVE_SUFFIX))
SLOT_COUNT = 3
_current_slot = 0

# active_mission key → (slot mission id, dossier label, flags written on completion)
_MISSION_RECORDS = {
    "MISSION1": (
        "MISSION_1",
        "Mission 1 - Black Notebook",
        {"mission1_complete": True},
    ),
    "MISSION2": (
        "MISSION_2",
        "Mission 2 - Quiet on Route 12",
        {"mission1_complete": True, "mission2_complete": True},
    ),
    "MISSION3": (
        "MISSION_3",
        "Mission 3 - The Vostral",
        {"mission1_complete": True, "mission2_complete": True,
         "mission3_complete": True},
    ),
    "MISSION4": (
        "MISSION_4",
        "Mission 4 - The Aftermath",
        {"mission1_complete": True, "mission2_complete": True,
         "mission3_complete": True, "mission4_complete": True},
    ),
    "MISSION5": (
        "MISSION_5",
        "Mission 5 - Martial Law",
        {"mission1_complete": True, "mission2_complete": True,
         "mission3_complete": True, "mission4_complete": True,
         "mission5_complete": True},
    ),
}


def _empty_slot(slot_index):
    return {
        "slot": slot_index,
        "occupied": False,
        "last_completed_mission": "",
        "last_completed_label": "No missions completed",
        "total_time": "00:00",
        "updated_at": 0,
        "progress": "",
        "stats": {},
        "flags": {},
    }


def _default_data():
    return {
        "version": 1,
        "current_slot": 0,
        "slots": [_empty_slot(i) for i in range(SLOT_COUNT)],
    }


def load_data():
    data = json_store.load_with_backup(SAVE_FILE, _default_data)
    if not isinstance(data, dict):
        data = _default_data()
    slots = data.get("slots", [])
    fixed = _default_data()
    try:
        fixed["current_slot"] = max(
            0, min(SLOT_COUNT - 1, int(data.get("current_slot", 0)))
        )
    except (TypeError, ValueError):
        pass
    for i in range(SLOT_COUNT):
        if i < len(slots) and isinstance(slots[i], dict):
            merged = _empty_slot(i)
            merged.update(slots[i])
            merged["slot"] = i
            fixed["slots"][i] = merged
    return fixed


def save_data(data):
    try:
        json_store.atomic_write(SAVE_FILE, data)
    except Exception as e:
        print(f"Save failed: {e}")


def select_slot(slot_index):
    global _current_slot
    idx = max(0, min(SLOT_COUNT - 1, int(slot_index)))
    _current_slot = idx
    data = load_data()
    if data.get("current_slot") != idx:
        data["current_slot"] = idx
        save_data(data)


def current_slot_index():
    return _current_slot


def get_slot(slot_index=None):
    idx = _current_slot if slot_index is None else max(0, min(SLOT_COUNT - 1, int(slot_index)))
    return load_data()["slots"][idx]


def start_new_campaign(slot_index=None):
    global _current_slot
    idx = _current_slot if slot_index is None else max(0, min(SLOT_COUNT - 1, int(slot_index)))
    _current_slot = idx
    data = load_data()
    slot = _empty_slot(idx)
    slot.update({
        "occupied": True,
        "last_completed_mission": "",
        "last_completed_label": "Campaign started - Mission 1 in progress",
        "updated_at": int(time.time()),
        "progress": "walk",
        "stats": {},
        "flags": {"mission1_started": True},
    })
    data["slots"][idx] = slot
    data["current_slot"] = idx
    save_data(data)


def set_slot_progress(progress, slot_index=None):
    """Record the coarse campaign segment ('walk' / 'm1') for resume.

    No-op when the target slot is empty so headless/dev code paths can call
    mission-start functions without creating phantom saves.
    """
    idx = _current_slot if slot_index is None else max(0, min(SLOT_COUNT - 1, int(slot_index)))
    data = load_data()
    slot = data["slots"][idx]
    if not slot.get("occupied") or slot.get("progress") == progress:
        return
    slot["progress"] = progress
    save_data(data)


def mission_complete_record(active_mission, total_time, stats=None):
    """Map an active_mission key to slot fields. Returns None if unknown."""
    rec = _MISSION_RECORDS.get(active_mission)
    if rec is None:
        print(f"save_system: unknown mission {active_mission!r} - not saving")
        return None
    mission_id, label, flags = rec
    return {
        "mission_id": mission_id,
        "label": label,
        "total_time": total_time,
        "stats": stats or {},
        "flags": dict(flags),
    }


def save_mission_complete_record(active_mission, total_time, stats=None, slot_index=None):
    """Save a mission completion from an active_mission key. False if unknown."""
    rec = mission_complete_record(active_mission, total_time, stats)
    if rec is None:
        return False
    save_mission_complete(
        rec["mission_id"],
        rec["label"],
        rec["total_time"],
        stats=rec["stats"],
        flags=rec["flags"],
        slot_index=slot_index,
    )
    return True


def save_mission_complete(mission_id, label, total_time, stats=None, flags=None, slot_index=None):
    idx = _current_slot if slot_index is None else max(0, min(SLOT_COUNT - 1, int(slot_index)))
    data = load_data()
    slot = data["slots"][idx]
    if not slot.get("occupied"):
        slot = _empty_slot(idx)
    merged_flags = dict(slot.get("flags") or {})
    merged_flags.update(flags or {})
    merged_stats = dict(slot.get("stats") or {})
    merged_stats.update(stats or {})
    slot.update({
        "occupied": True,
        "last_completed_mission": mission_id,
        "last_completed_label": label,
        "total_time": total_time,
        "updated_at": int(time.time()),
        "stats": merged_stats,
        "flags": merged_flags,
    })
    data["slots"][idx] = slot
    data["current_slot"] = idx
    save_data(data)


def format_timestamp(ts):
    if not ts:
        return "never"
    try:
        return time.strftime("%Y-%m-%d %H:%M", time.localtime(ts))
    except Exception:
        return "unknown"


def has_any_save():
    return any(bool(slot.get("occupied")) for slot in load_data().get("slots", []))


# Hydrate the persisted active slot (menu panel correctness across relaunches).
try:
    _current_slot = load_data().get("current_slot", 0)
except Exception:
    _current_slot = 0
