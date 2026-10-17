"""Mission 3 entity components (RPE6 Phase 5, D4).

Declared data that ``missions.m3`` used to stuff onto ``Enemy`` objects as ad hoc
``m3_*`` attributes (plus ``is_mission3_ipa`` and ``shield_angle_width``). Attach/read
through ``game.world`` (``_gw.ensure(e, M3Guard)``); every default equals the
``getattr(..., default)`` fallback the old reads assumed, so an enemy that never received
the data behaves exactly as before. The enemy *type* and spawn *label* live in the shared
``engine.world.Label`` component (``kind`` / ``text``) so mission-agnostic code (corpses)
can read them without knowing Mission 3.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

from core.config import ENEMY_ATTACK_RANGE, ENEMY_DAMAGE, ENEMY_FIRE_COOLDOWN
from engine.world import component

__all__ = ["M3Door", "M3Guard"]


@component
@dataclass(slots=True)
class M3Guard:
    ipa: bool = False                        # spawned by _spawn_m3_guard (IPA cell-block guard)
    always_alert: bool = False               # Broadcast Wing: engages without line of sight
    damage: float = ENEMY_DAMAGE             # per-type combat tuning (type_stats / ROLE_TUNING)
    fire_cooldown: float = ENEMY_FIRE_COOLDOWN
    spread: float = 0.06
    bullet_speed: float = 18
    attack_range: float = ENEMY_ATTACK_RANGE
    target_kind: str = "player"              # current target ("player" | "volkov")
    target_timer: int = 0                    # frames until the target choice is revisited
    called_alert: bool = False               # already raised the alarm once
    sweep_team: object = None                # KO sweep insertion index (None = not a sweep member)
    sweep_role: str = "guard"
    shield_angle_width: float = math.radians(78)   # riot-shield coverage half-angle


@component
@dataclass(slots=True)
class M3Door:
    """Mission 3 data of a ``core.interactions.Door`` (old ``door.m3_*`` attributes)."""
    cell_door: bool = False                  # the shot-open cell door (locked until forced)
    forced_open: bool = False
    shot_hits: int = 0
    required_shots: int = 6
    archive_access: bool = False             # Archives: the access-controlled door
    ko_breach: bool = False                  # Kill Order: breach door (locked until the sweep)
    ko_beat_gate: object = None              # Kill Order: wave index that opens this gate (None = not a gate)
    bcast_gate: bool = False                 # Broadcast Wing gate
    vostral_vault: bool = False              # Archives: Vostral vault door
    kill_order_exit: bool = False            # Archives: exit toward the Kill Order wing
