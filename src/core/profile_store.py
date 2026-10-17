
"""The global profile: Acaribucks wallet, owned cosmetics, equipped loadout.

One profile for the whole install, deliberately NOT tied to a save slot. A
player who earns a hat in the arena keeps it in the campaign and in their next
campaign, and a corrupted campaign save must not be able to eat their
purchases.

Why this is a third file rather than more keys in one of the two existing
ones:

  * core.settings_store.load() type-checks every key down to bool/int/str and
    silently reverts anything else to its default. A wallet needs a nested
    dict and a list, so putting it there would mean widening the validator
    that every existing setting depends on - for a thing that is not a
    setting.
  * core.save_system.load_data() rebuilds its defaults and copies across only
    current_slot and slots, so a new top-level key in save_data.json is
    dropped on every load. And per-slot storage contradicts the point above.

Writes go through core.json_store, so a crash mid-save leaves the previous
profile intact rather than a truncated one.

Nothing in here raises. A wallet that can throw takes a match down with it, and
the failure mode the whole module is built against is a hand-edited or
half-written JSON file.
"""
import os
from pathlib import Path

from core import appearance as _appearance
from core import json_store

# Mirrors settings_store.SAVE_FILE / save_system.SAVE_FILE so the duo launcher
# and the smoke test can sandbox the wallet per process.
_SAVE_SUFFIX = os.environ.get("ACA_SAVE_SUFFIX", "")
PROFILE_FILE = str(
    Path(__file__).resolve().parents[2] / ("profile%s.json" % _SAVE_SUFFIX)
)

VERSION = 1
BALANCE_MAX = 1000000
"""Wallet ceiling. Not a game rule - a file-size and hand-edit guard."""

CREDIT_MAX = 1000
"""Largest single credit accepted. The real per-round cap is arena.PAYOUT_MAX;
this one exists so that a bug, or an edited file, cannot post a number that
makes the shop meaningless."""

OWNED_MAX = 64
CREDITED_MAX = 16
CREDIT_KEY_MAX = 64

_DEFAULT_OWNED = _appearance.FREE_ITEM_IDS


def _fresh():
    """A brand-new profile: broke, defaults equipped, nothing credited."""
    return {
        "version": VERSION,
        "acaribucks": 0,
        "lifetime_earned": 0,
        "rounds_scored": 0,
        "owned": list(_DEFAULT_OWNED),
        "equipped": _appearance.default_appearance(),
        "credited": [],
    }


def _int(value, lo, hi):
    """Coerce to int and clamp. Bools are refused: True is not 1 credit."""
    try:
        if isinstance(value, bool):
            return lo
        n = int(value)
    except (TypeError, ValueError):
        return lo
    return max(lo, min(hi, n))


def _restrict_to_owned(app, owned):
    """Drop any equipped identifier the profile does not actually own.

    This is the reason a hand-edited profile.json cannot grant a hat: the
    equipped loadout is filtered against the owned list on every load, not
    trusted because it came from disk.
    """
    app = _appearance.normalize(app)
    out = {"palette": app["palette"] if app["palette"] in owned
           else _appearance.DEFAULT_PALETTE,
           "head": app["head"] if app["head"] in owned
           else _appearance.DEFAULT_HEAD,
           "finish": {}}
    for gun in _appearance.GUN_KEYS:
        want = _appearance.DEFAULT_FINISH_ID % gun
        out["finish"][gun] = app["finish"][gun] if app["finish"][gun] in owned else want
    return _appearance.normalize(out)


def load():
    """Read the profile from disk, fully normalized. Never raises."""
    try:
        raw = json_store.load_with_backup(PROFILE_FILE, _fresh)
        if not isinstance(raw, dict):
            return _fresh()
        out = _fresh()
        out["version"] = _int(raw.get("version"), 1, VERSION)
        out["acaribucks"] = _int(raw.get("acaribucks"), 0, BALANCE_MAX)
        out["lifetime_earned"] = _int(raw.get("lifetime_earned"), 0, BALANCE_MAX)
        out["rounds_scored"] = _int(raw.get("rounds_scored"), 0, 10 ** 9)

        owned = set(_DEFAULT_OWNED)
        listed = raw.get("owned")
        if isinstance(listed, list):
            for item in listed[:OWNED_MAX]:
                # Membership in the catalog, not a shape check: an id we do
                # not sell is not owned, whatever the file claims.
                if isinstance(item, str) and _appearance.is_known(item):
                    owned.add(item)
        out["owned"] = sorted(owned)

        out["equipped"] = _restrict_to_owned(raw.get("equipped"), owned)

        credited = raw.get("credited")
        if isinstance(credited, list):
            out["credited"] = [str(k)[:CREDIT_KEY_MAX] for k in credited
                               if isinstance(k, (str, int))][-CREDITED_MAX:]
        return out
    except Exception as exc:
        print(f"Profile load failed, starting clean: {exc}")
        return _fresh()


def save(patch):
    """Merge *patch* over the loaded profile and write it atomically.

    Keys the caller omits keep their on-disk value, so a buy() cannot lose a
    credit log it knows nothing about.
    """
    try:
        merged = load()
        merged.update(patch)
        _write(merged)
        return True
    except Exception as exc:
        print(f"Profile save failed: {exc}")
        return False


def _write(data):
    json_store.atomic_write(PROFILE_FILE, data)


# ── Ownership and equipping ─────────────────────────────────────────────

def balance():
    """What the player can spend right now."""
    return load()["acaribucks"]


def buy(item_id):
    """Purchase one catalog item. Returns (ok, reason).

    Re-reads and re-checks rather than trusting a caller's snapshot, because
    the UI's idea of the balance is at least one frame stale and a double-click
    on BUY should not be able to buy the same hat twice for half the price.
    """
    data = load()
    if not _appearance.is_known(item_id):
        return False, "unknown"
    if item_id in data["owned"]:
        return False, "owned"
    price = _int(_appearance.price_of(item_id), 0, BALANCE_MAX)
    if price > data["acaribucks"]:
        return False, "poor"
    owned = sorted(set(data["owned"]) | {item_id})
    save({"acaribucks": data["acaribucks"] - price, "owned": owned})
    return True, "ok"


def equipped():
    """The appearance to draw this player with. Safe to hand to Player."""
    return load()["equipped"]


def equip(item_id):
    """Wear an owned item, routing it to the right slot by catalog membership.

    Refuses anything not owned. Returns False on either count.
    """
    data = load()
    if not _appearance.is_known(item_id) or item_id not in data["owned"]:
        return False
    app = _appearance.normalize(data["equipped"])
    if item_id in _appearance.PALETTES:
        app["palette"] = item_id
    elif item_id in _appearance.HEADGEARS:
        app["head"] = item_id
    else:
        app["finish"][_appearance.FINISHES[item_id]["gun"]] = item_id
    save({"equipped": _restrict_to_owned(app, set(data["owned"]))})
    return True


# ── Round credit ────────────────────────────────────────────────────────

def credit_round(key, amount):
    """Pay a round's earnings exactly once.

    *key* identifies the round - the match token, the round number, the slot
    and the kill count. Receiving a key that is already in the log is refused,
    which is what stops a round-end card that lingers on screen for five
    seconds from paying out three hundred times, and what stops a client
    re-deriving the same result from being paid again.

    Returns True only when this call actually moved money.
    """
    try:
        data = load()
        k = str(key)[:CREDIT_KEY_MAX]
        if not k or k in data["credited"]:
            return False
        amount = _int(amount, 0, CREDIT_MAX)
        credited = (data["credited"] + [k])[-CREDITED_MAX:]
        _write(dict(
            data,
            acaribucks=_int(data["acaribucks"] + amount, 0, BALANCE_MAX),
            lifetime_earned=_int(data["lifetime_earned"] + amount, 0, BALANCE_MAX),
            rounds_scored=_int(data["rounds_scored"] + 1, 0, 10 ** 9),
            credited=credited,
        ))
        return True
    except Exception as exc:
        print(f"Round credit failed: {exc}")
        return False
