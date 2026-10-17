
"""Trailer bot - deterministic operator driver for cinematic capture.

Usage (after the app.py hook lands):
  python acaristan.py --jump m1 --trailer-bot --trailer-act act1
  python acaristan.py --jump m2-game --trailer-bot --trailer-act act2_killbox
  python acaristan.py --jump m3-game --trailer-bot --trailer-act act3_breakout
  python acaristan.py --jump m3-comms --trailer-bot --trailer-act act3_relay

Design: the bot does NOT pathfind. Each act is a waypoint list
(tile-center coords resolved at runtime via each mission's _tc).
Every frame: sprint full-speed at current waypoint, snap angle
instantly to pre-aim, fire double-taps via the real weapons pipeline.

State ownership: all _BOT_* globals live HERE (per AGENTS.md shared
mutable state rule). Consumers access them ONLY via
``import tools.trailer_bot as _bot`` + ``_bot.NAME`` - never
``from tools.trailer_bot import _BOT_x`` (snapshots go stale).
"""
import math
import pygame
from core.state import STATE

_BOT_active = False
_BOT_act = "act1"
_BOT_wp_idx = 0
_BOT_hold = 0
_BOT_waypoints = []  # list of (x, y, aim_x, aim_y, action)
_BOT_fire_cd = 0

TAP_GAP = 9          # frames between the 2 shots of a double-tap
REACQUIRE = 18       # frames to hold aim after a kill before moving
PREAIM_SPREAD = 0.06  # radians of humanising jitter around pre-aim


def reset(act="act1"):
    global _BOT_act, _BOT_wp_idx, _BOT_hold, _BOT_waypoints, _BOT_fire_cd
    _BOT_act = act
    _BOT_wp_idx = 0
    _BOT_hold = 0
    _BOT_fire_cd = 0
    _BOT_waypoints = _build_script(act)


def is_active():
    return _BOT_active


def set_active(v):
    global _BOT_active
    _BOT_active = bool(v)


def _tc64(col, row):
    return (col * 64 + 32, row * 64 + 32)


def _build_script(act):
    """Waypoint = (move_x, move_y, aim_x, aim_y, action).

    Actions: move | tap2 | molotov | melee | interact | reload | swap.
    """
    T = _tc64
    if act == "act1":
        # Warehouse: patrol kill -> gate console (13,15) -> notebook (runtime)
        # -> bay-mouth hold (15,18) -> exfil (runtime). Notebook/exfil patched
        # at runtime from STATE.NOTEBOOK_POS / STATE.EXFIL_POS (see tick_bot).
        return [
            (T(6, 5)[0], T(6, 5)[1], T(6, 7)[0], T(6, 7)[1], "tap2"),
            (T(10, 11)[0], T(10, 11)[1], T(12, 11)[0], T(12, 11)[1], "tap2"),
            (T(13, 15)[0], T(13, 15)[1], T(15, 15)[0], T(15, 15)[1], "interact"),
            (T(14, 17)[0], T(14, 17)[1], T(16, 18)[0], T(16, 18)[1], "molotov"),
            (T(15, 18)[0], T(15, 18)[1], T(15, 20)[0], T(15, 20)[1], "tap2"),
            (T(15, 18)[0], T(15, 18)[1], T(13, 17)[0], T(13, 17)[1], "tap2"),
            (T(15, 21)[0], T(15, 21)[1], T(15, 21)[0], T(15, 21)[1], "interact"),
        ]
    if act == "act2_killbox":
        return [
            (T(34, 40)[0], T(34, 40)[1], T(36, 34)[0], T(36, 34)[1], "tap2"),
            (T(40, 41)[0], T(40, 41)[1], T(44, 34)[0], T(44, 34)[1], "tap2"),
            (T(40, 41)[0], T(40, 41)[1], T(40, 41)[0], T(40, 41)[1], "reload"),
            (T(30, 43)[0], T(30, 43)[1], T(36, 34)[0], T(36, 34)[1], "tap2"),
            (T(22, 47)[0], T(22, 47)[1], T(30, 40)[0], T(30, 40)[1], "tap2"),
        ]
    if act == "act2_evidence":
        return [
            (T(55, 23)[0], T(55, 23)[1], T(57, 23)[0], T(57, 23)[1], "interact"),
            (T(63, 19)[0], T(63, 19)[1], T(63, 17)[0], T(63, 17)[1], "tap2"),
            (T(59, 14)[0], T(59, 14)[1], T(59, 12)[0], T(59, 12)[1], "interact"),
        ]
    if act == "act3_breakout":
        return [
            (T(6, 6)[0], T(6, 6)[1], T(8, 6)[0], T(8, 6)[1], "melee"),
            (T(8, 6)[0], T(8, 6)[1], T(10, 6)[0], T(10, 6)[1], "tap2"),
            (T(10, 8)[0], T(10, 8)[1], T(12, 8)[0], T(12, 8)[1], "tap2"),
        ]
    if act == "act3_relay":
        # Comms chain: breaker -> auth booth -> relay. Exact relay pos via
        # missions.m3.draw._relay_pos() at runtime; tiles below are approach.
        return [
            (T(8, 10)[0], T(8, 10)[1], T(10, 10)[0], T(10, 10)[1], "tap2"),
            (T(12, 10)[0], T(12, 10)[1], T(14, 10)[0], T(14, 10)[1], "interact"),
            (T(14, 12)[0], T(14, 12)[1], T(16, 12)[0], T(16, 12)[1], "tap2"),
            (T(16, 12)[0], T(16, 12)[1], T(16, 12)[0], T(16, 12)[1], "reload"),
            (T(16, 12)[0], T(16, 12)[1], T(16, 12)[0], T(16, 12)[1], "swap"),
        ]
    return []


def _patch_runtime_targets():
    # Resolve M1 notebook/exfil from live STATE so the script survives
    # map-authoring moves. Called once per tick (cheap).
    if _BOT_act == "act1" and _BOT_waypoints:
        nb = getattr(STATE, "NOTEBOOK_POS", None)
        ex = getattr(STATE, "EXFIL_POS", None)
        if nb:
            _BOT_waypoints[3] = (nb[0], nb[1] + 54, nb[0], nb[1], "interact")
        if ex:
            _BOT_waypoints[-1] = (ex[0] - 42, ex[1], ex[0], ex[1], "interact")


def tick_bot(keys):
    """Called from app GAME.update BEFORE gc.game_update(keys).

    Returns (keys, fired_action). Sets STATE.player.angle directly
    (instant snap - never lerp). Fires through the real weapons pipeline
    so shake/kick/casings/tracers match human play. Movement is injected
    by returning a fake keys object with WASD set toward the waypoint.
    """
    # lazy: breaks tools<->app load cycle (AGENTS.md import direction)
    from entities import weapons as _w
    _patch_runtime_targets()
    p = getattr(STATE, "player", None)
    if p is None or getattr(STATE, "player_dead", False):
        return keys, None
    if not _BOT_waypoints:
        return keys, None
    global _BOT_wp_idx, _BOT_hold, _BOT_fire_cd
    if _BOT_fire_cd > 0:
        _BOT_fire_cd -= 1
    if _BOT_hold > 0:
        _BOT_hold -= 1
        return keys, "hold"
    mx, my, ax, ay, action = _BOT_waypoints[min(_BOT_wp_idx, len(_BOT_waypoints) - 1)]
    # 1. Snap aim (human flick: instant + tiny jitter, no ease).
    import random as _r
    p.angle = math.atan2(
        (ay + _r.uniform(-4, 4)) - p.rect.centery,
        (ax + _r.uniform(-4, 4)) - p.rect.centerx)
    # 2. Movement: full-speed (5px/f) toward waypoint via fake WASD.
    dx, dy = mx - p.rect.centerx, my - p.rect.centery
    dist = math.hypot(dx, dy)
    if dist < 26 and action in ("move", "tap2", "molotov", "melee", "interact"):
        _do_action(action, _w)
        if action in ("tap2", "molotov", "melee"):
            _BOT_hold = REACQUIRE
        _BOT_wp_idx = min(_BOT_wp_idx + 1, len(_BOT_waypoints) - 1)
        return keys, action
    if dist < 26:  # reload / swap waypoints fire in place
        _do_action(action, _w)
        _BOT_wp_idx = min(_BOT_wp_idx + 1, len(_BOT_waypoints) - 1)
        return keys, action
    return _FakeKeys(dx, dy), None


def _do_action(action, _w):
    global _BOT_fire_cd
    if action == "tap2" and _BOT_fire_cd <= 0:
        _w.handle_shoot()
        _BOT_fire_cd = TAP_GAP
        # Second tap queued next tick by hold window; weapon cd gates it
        # exactly like a human double-tap (pistol 12f / OS-12 8f / K-9 5f).
    elif action == "molotov":
        _w.handle_throw_bottle()
    elif action == "melee":
        _w.handle_melee()
    elif action == "reload":
        _w.start_reload()
    elif action == "swap":
        _w.switch_weapon()
    elif action == "interact":
        # lazy: game_core routes E per mission (M1 gate / M2 clue / M3 relay)
        from core import game_core as _gc
        _gc.handle_interact()


class _FakeKeys:
    """Duck-types pygame.key.get_pressed() for game_update(keys)."""

    def __init__(self, dx, dy):
        self._dx, self._dy = dx, dy

    def __getitem__(self, key):
        if key == pygame.K_w:
            return self._dy < -8
        if key == pygame.K_s:
            return self._dy > 8
        if key == pygame.K_a:
            return self._dx < -8
        if key == pygame.K_d:
            return self._dx > 8
        return False
