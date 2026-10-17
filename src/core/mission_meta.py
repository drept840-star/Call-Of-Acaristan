"""Per-mission display metadata (operation name + failure-screen copy).

One table, keyed by ``STATE.active_mission``. UI code (fail screen, pause
menu, mission-complete card) reads it through the helpers below instead of
hard-coding per-mission strings, so a later mission can never fall back to
Mission 1's "BLACK NOTEBOOK" copy.

Dependency-free on purpose (no pygame, no game imports): anything may import
it at load time without creating a cycle. Callers pass the state object.
"""

NEUTRAL_OPERATION = "OPERATION"
NEUTRAL_FAIL_SUBTITLE = "OPERATION COMPROMISED"
NEUTRAL_FAIL_FLAVOR = "SIGNAL LOST."

# key -> (operation display name, fail subtitle, fail flavour line)
# Flavour lines are written in each mission's voice: who is (or isn't)
# listening on the other end when Biribel goes down.
MISSION_META = {
    "MISSION1": {
        "operation": "WAREHOUSE RAID - BLACK NOTEBOOK",
        "fail_subtitle": "OPERATION BLACK NOTEBOOK COMPROMISED",
        "fail_flavor": "KRAP COMMAND: SIGNAL LOST. DISPATCHING CLEANUP CREW.",
        "radio_channel": "KRAP CMD // 141.20",
    },
    "MISSION2": {
        "operation": "ROUTE 12, QUIET ON ROUTE 12",
        "fail_subtitle": "OPERATION QUIET ON ROUTE 12 COMPROMISED",
        "fail_flavor": "VASILE LINK: LOST. IPA CLEANUP TEAMS CLOSING ON ROUTE 12.",
        "radio_channel": "KRAP SQD 4 // 146.85",
    },
    "MISSION3": {
        "operation": "THE STABILIZATION CENTER - THE VOSTRAL",
        "fail_subtitle": "THE VOSTRAL STAYS BURIED",
        "fail_flavor": "IPA BLOCK CONTROL: PRISONER RECAPTURED. THE BROADCAST GOES OUT ON SCHEDULE.",
        "radio_channel": "SALVAGED SET // 153.05",
    },
    "MISSION4": {
        "operation": "THE CAPITAL - 48H CURFEW",
        "fail_subtitle": "THE TRANSMITTER GOES DARK",
        "fail_flavor": "LOYALIST NET: STATION RETAKEN. THE CAPITAL HEARS ONLY STATIC.",
        "radio_channel": "LIAISON NET // 162.40",
    },
    "MISSION5": {
        "operation": "THE CAPITAL - EMERGENCY RULE",
        "fail_subtitle": "OPERATION EMERGENCY RULE COMPROMISED",
        "fail_flavor": "GUARD NET: LOWER QUARTER SECURED. THE PRESSES GO QUIET.",
        "radio_channel": "GUARD NET // 168.10",
    },
}


def mission_key(state):
    """Current mission key (``"MISSION1"``...), or ``None`` if unknown."""
    key = getattr(state, "active_mission", None)
    return key if key in MISSION_META else None


def meta_for(state):
    """Table entry for the current mission (empty dict when unknown)."""
    key = mission_key(state)
    return MISSION_META.get(key, {}) if key else {}


def operation_name(state):
    """Operation display name: table first, then the state field, then neutral."""
    meta = meta_for(state)
    if meta:
        return meta["operation"]
    op = getattr(state, "active_mission_operation", None)
    return op or NEUTRAL_OPERATION


NEUTRAL_RADIO_CHANNEL = "OPEN CHANNEL"


def radio_channel(state):
    """Flavour channel / frequency plate for the radio widget (ui/radio.py)."""
    return meta_for(state).get("radio_channel", NEUTRAL_RADIO_CHANNEL)


def fail_text(state):
    """(subtitle, flavour) for the Mission Failed screen. Never M1's copy
    unless Mission 1 is actually the active mission."""
    meta = meta_for(state)
    if not meta:
        return NEUTRAL_FAIL_SUBTITLE, NEUTRAL_FAIL_FLAVOR
    return meta["fail_subtitle"], meta["fail_flavor"]
