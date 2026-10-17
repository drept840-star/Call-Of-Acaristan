"""engine.world - entities, components, systems ("ECS-lite", RPE6 §6.4). Facade only; logic lives in the owner modules."""
from __future__ import annotations

from ._component import component, component_type, component_types, fields_of, from_dict, is_component, schema, to_dict
from .entity import EntityId, World, WorldError
from .prefab import PREFAB_SCHEMA, PrefabLibrary, load_prefabs
from .std import (
    AIBrain, Collider, Faction, Health, HitFlash, Label, LegacyRef, Lifetime, Sprite, Tags, Transform, Velocity, WalkCycle,
)
from .system import PHASES, POST, PRE, RENDER_SUBMIT, SIM, FunctionSystem, Scheduler, System

__all__ = [
    # kernel
    "EntityId", "World", "WorldError",
    "component", "component_type", "component_types", "fields_of", "from_dict", "is_component", "schema", "to_dict",
    "PHASES", "PRE", "SIM", "POST", "RENDER_SUBMIT", "System", "FunctionSystem", "Scheduler",
    "PREFAB_SCHEMA", "PrefabLibrary", "load_prefabs",
    # standard components
    "Transform", "Velocity", "Collider", "Health", "Faction", "Tags", "Label", "Sprite",
    "WalkCycle", "HitFlash", "AIBrain", "Lifetime", "LegacyRef",
]
