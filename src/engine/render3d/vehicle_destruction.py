"""Shared 3D vehicle destruction physics, authored profiles, and rendering.

Provides one engine-level system for every destructible vehicle in the game
(cars, jeeps, cargo trucks, gun trucks, AA searchlight trucks, fuel tankers,
gunships, and tractors).  Pure ``engine.render3d``: imports only stdlib,
``pygame``, ``numpy``, and ``engine3d.*`` (RPE6 boundaries E1/E3).  Uses
``engine.render3d.blast_sprites`` for procedural cached fireball/flash sprites;
game-side hosts may pass an optional ``fx`` adapter (e.g. ``game.vehicle_fx``)
to render persistent flames/smoke/embers through ``cutscenes.fire3d``.
"""
from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass
import math
import random
from typing import Callable, Optional, Sequence

import pygame

from engine3d.core import (
    M_IDENT,
    Mesh,
    box,
    clamp,
    disc_xz,
    m_apply,
    m_mul,
    mix_col,
    prism,
    rot_x,
    rot_y,
    rot_z,
)
from engine3d.particles import DKIND_SCORCH
from . import blast_sprites

__all__ = [
    "PartSpec",
    "CookoffSpec",
    "FireMount",
    "VehicleDestructionProfile",
    "VEHICLE_PROFILES",
    "get_vehicle_profile",
    "PartBody",
    "VehicleDestruction",
    "VehicleDestructionManager",
]

Vec3 = tuple[float, float, float]
Color3 = tuple[int, int, int]


@dataclass(frozen=True)
class PartSpec:
    """Authored launch recipe for one detached 3D vehicle component."""

    shape: str
    offset: Vec3
    dir_local: Vec3
    speed: tuple[float, float]
    up_boost: tuple[float, float]
    spin: tuple[float, float]
    hot: bool = False
    smoking: bool = False
    use_paint: bool = False
    life: float = 12.0


@dataclass(frozen=True)
class FireMount:
    """Persistent fire/smoke emitter anchored in a wreck's local space."""

    offset: Vec3
    size: float = 1.0
    heat: float = 1.15
    smoky: bool = True
    embers: bool = True
    bed: bool = False


@dataclass(frozen=True)
class CookoffSpec:
    """Delayed secondary detonation inside a burning wreck."""

    delay_s: float
    offset: Vec3
    radius: float
    n_sparks: int = 16
    tracer_burst: bool = False


@dataclass(frozen=True)
class VehicleDestructionProfile:
    """Complete destruction choreography & breakup profile per vehicle kind."""

    kind: str
    blast_radius: float
    scorch_radius: float
    flash_dur: float
    fireball_dur: float
    fireball_lobes: int
    fire_life: float
    jolt_vy: float
    jolt_pitch: float
    jolt_roll: float
    sag_y: float
    shockwave_r: float
    shockwave_dur: float
    parts: tuple[PartSpec, ...]
    fire_mounts: tuple[FireMount, ...]
    cookoffs: tuple[CookoffSpec, ...]


def _ease(u: float) -> float:
    u = clamp(u, 0.0, 1.0)
    return u * u * (3.0 - 2.0 * u)


def _rot_matrix(yaw: float, pitch: float, roll: float):
    return m_mul(rot_y(yaw), m_mul(rot_x(-pitch), rot_z(roll)))


def _xf_local(local: Vec3, pos: Vec3, yaw: float, pitch: float = 0.0, roll: float = 0.0) -> Vec3:
    rx, ry, rz = m_apply(_rot_matrix(yaw, pitch, roll), local)
    return (pos[0] + rx, pos[1] + ry, pos[2] + rz)


def _normalize(v: Vec3) -> Vec3:
    m = math.sqrt(v[0] * v[0] + v[1] * v[1] + v[2] * v[2])
    if m < 1e-6:
        return (0.0, 1.0, 0.0)
    return (v[0] / m, v[1] / m, v[2] / m)


# ── Bounded LRU caches for procedural part meshes & fallback sprites ────────

_PART_MESH_CACHE: OrderedDict = OrderedDict()
_FALLBACK_SURF_CACHE: OrderedDict = OrderedDict()


def _lru_get(cache: OrderedDict, key):
    val = cache.get(key)
    if val is not None:
        cache.move_to_end(key)
    return val


def _lru_put(cache: OrderedDict, key, val, cap: int):
    if len(cache) >= cap:
        cache.popitem(last=False)
    cache[key] = val
    return val


def _scorch_col(paint: Optional[Color3], k: float = 0.62) -> Color3:
    base = paint if paint is not None else (54, 58, 52)
    return mix_col(base, (26, 22, 20), k)


def _build_part_mesh(shape: str, paint: Optional[Color3], hot: bool) -> Mesh:
    key = (shape, paint, bool(hot))
    hit = _lru_get(_PART_MESH_CACHE, key)
    if hit is not None:
        return hit

    m = Mesh()
    steel = (52, 54, 58)
    char = (28, 24, 22)
    rust = (88, 46, 30)
    rubber = (20, 20, 22)
    rim = (92, 94, 98)
    skin = _scorch_col(paint, 0.45) if paint is not None else (64, 68, 56)
    ember = (128, 48, 22)
    glass = (128, 152, 168)

    if shape == "hood":
        m.add(box(1.42, 0.06, 1.08, skin, center=(0.0, 0.0, 0.0),
                  cols={"bottom": char, "top": mix_col(skin, char, 0.25)}))
        m.add(box(0.32, 0.04, 0.96, mix_col(skin, rust, 0.35), center=(0.0, 0.04, 0.0)))
        m.add(box(1.44, 0.07, 0.08, steel, center=(0.0, -0.02, 0.52)))
    elif shape == "door":
        m.add(box(0.08, 0.56, 0.96, skin, center=(0.0, -0.14, 0.0),
                  cols={"left": char, "right": skin}))
        m.add(box(0.06, 0.38, 0.07, steel, center=(0.0, 0.30, 0.44)))
        m.add(box(0.06, 0.38, 0.07, steel, center=(0.0, 0.30, -0.44)))
        m.add(box(0.06, 0.06, 0.94, skin, center=(0.0, 0.48, 0.0)))
        m.add(box(0.10, 0.05, 0.16, steel, center=(0.02, 0.06, -0.22)))
    elif shape == "trunk":
        m.add(box(1.36, 0.06, 0.86, skin, center=(0.0, 0.0, 0.0), cols={"bottom": char}))
        m.add(box(1.36, 0.14, 0.06, skin, center=(0.0, -0.05, -0.41)))
    elif shape in ("wheel", "heavy_wheel"):
        rad = 0.46 if shape == "heavy_wheel" else 0.35
        wid = 0.30 if shape == "heavy_wheel" else 0.22
        oct_pts = [(math.cos(i * math.tau / 8.0) * rad, math.sin(i * math.tau / 8.0) * rad)
                   for i in range(8)]
        tire = prism(oct_pts, wid, rubber, z0=-wid * 0.5)
        m.add(tire, rot_y(90.0), (0.0, 0.0, 0.0))
        hub_pts = [(math.cos(i * math.tau / 8.0) * rad * 0.52,
                    math.sin(i * math.tau / 8.0) * rad * 0.52) for i in range(8)]
        hub = prism(hub_pts, wid + 0.03, rim, z0=-(wid + 0.03) * 0.5)
        m.add(hub, rot_y(90.0), (0.0, 0.0, 0.0))
    elif shape == "bumper":
        m.add(box(1.76, 0.14, 0.16, steel, center=(0.0, 0.0, 0.0)))
        for sx in (-0.86, 0.86):
            m.add(box(0.10, 0.14, 0.28, char, center=(sx, 0.0, -0.08)))
    elif shape == "roof_panel":
        m.add(box(1.42, 0.06, 1.32, skin, center=(0.0, 0.0, 0.0), cols={"bottom": char}))
        m.add(box(1.32, 0.04, 0.12, char, center=(0.0, 0.04, 0.35)))
    elif shape == "glass_shard":
        m.add(box(0.32, 0.02, 0.24, glass, center=(0.0, 0.0, 0.0)))
    elif shape == "truck_slat":
        wood = (78, 56, 36)
        m.add(box(0.08, 0.18, 1.55, wood, center=(0.0, 0.0, 0.0)))
        m.add(box(0.10, 0.20, 0.08, steel, center=(0.0, 0.0, -0.55)))
        m.add(box(0.10, 0.20, 0.08, steel, center=(0.0, 0.0, 0.55)))
    elif shape == "tailgate":
        m.add(box(2.05, 0.68, 0.10, mix_col((68, 76, 56), char, 0.45), center=(0.0, 0.0, 0.0)))
        for sx in (-0.85, 0.0, 0.85):
            m.add(box(0.08, 0.66, 0.12, steel, center=(sx, 0.0, 0.0)))
    elif shape == "aa_turret":
        # Recognizable twin-barrel AA mount + housing + searchlight shroud
        m.add(box(0.95, 0.52, 1.10, (54, 60, 48), center=(0.0, 0.0, 0.0)))
        m.add(box(1.02, 0.14, 1.16, char, center=(0.0, -0.26, 0.0)))
        for sx in (-0.22, 0.22):
            m.add(box(0.10, 0.10, 1.55, (38, 42, 46), center=(sx, 0.14, 0.86)))
        m.add(box(0.46, 0.46, 0.42, (44, 48, 54), center=(0.0, 0.48, 0.16)))
        m.add(box(0.34, 0.34, 0.06, (88, 92, 98), center=(0.0, 0.48, 0.38)))
    elif shape == "tanker_cap":
        cap_pts = [(math.cos(a) * 0.96, math.sin(a) * 0.96)
                   for a in [math.pi / 8.0 + i * math.pi / 4.0 for i in range(8)]]
        m.add(prism(cap_pts, 0.32, (82, 34, 28), z0=-0.16))
        m.add(box(0.85, 0.28, 0.36, (176, 168, 152), center=(0.0, 0.0, 0.0)))
    elif shape == "tanker_rib":
        m.add(box(0.92, 0.10, 1.18, (88, 40, 32), center=(0.0, 0.0, 0.0), cols={"bottom": char}))
        m.add(box(0.94, 0.11, 0.28, (186, 178, 164), center=(0.0, 0.01, 0.0)))
    elif shape == "rotor_blade":
        m.add(box(0.24, 0.04, 2.95, (42, 44, 46), center=(0.0, 0.0, 0.0)))
        m.add(box(0.25, 0.045, 0.26, (214, 176, 46), center=(0.0, 0.0, 1.32)))
        m.add(box(0.30, 0.08, 0.28, steel, center=(0.0, 0.0, -1.36)))
    elif shape == "tail_boom":
        m.add(box(0.34, 0.36, 2.25, (48, 52, 46), center=(0.0, 0.0, 0.0), cols={"front": char}))
        m.add(box(0.10, 0.85, 0.48, (48, 52, 46), center=(0.0, 0.42, -0.88)))
        m.add(box(1.15, 0.06, 0.34, (132, 42, 34), center=(0.0, 0.08, -0.78)))
    elif shape == "rocket_pod":
        pod_pts = [(math.cos(i * math.tau / 6.0) * 0.22, math.sin(i * math.tau / 6.0) * 0.22)
                   for i in range(6)]
        m.add(prism(pod_pts, 1.15, (52, 56, 48), z0=-0.57))
        m.add(box(0.30, 0.30, 0.08, char, center=(0.0, 0.0, 0.56)))
    elif shape == "hull_panel":
        m.add(box(0.96, 0.07, 0.84, skin, center=(0.0, 0.0, 0.0), cols={"bottom": char}))
        m.add(box(0.90, 0.09, 0.10, rust, center=(0.0, 0.01, 0.24)))
    elif shape == "exhaust_stack":
        m.add(box(0.14, 1.15, 0.14, steel, center=(0.0, 0.0, 0.0)))
        m.add(box(0.24, 0.44, 0.24, rust, center=(0.0, -0.15, 0.0)))
    elif shape == "jerrycan":
        m.add(box(0.24, 0.46, 0.34, (148, 42, 32), center=(0.0, 0.0, 0.0)))
        m.add(box(0.10, 0.08, 0.18, steel, center=(0.0, 0.25, 0.04)))
    else:
        m.add(box(0.45, 0.10, 0.45, char, center=(0.0, 0.0, 0.0)))

    if hot:
        hot_faces = []
        for f in m.faces:
            c = f[1]
            if isinstance(c, tuple) and len(c) >= 3:
                hc = mix_col(c, ember, 0.28)
            else:
                hc = ember
            hot_faces.append((f[0], hc, f[2], f[3], True, *f[5:]))
        m.faces = hot_faces

    return _lru_put(_PART_MESH_CACHE, key, m, 192)


def _build_wreck_core_mesh(kind: str) -> Mesh:
    """Charred interior rubble + glowing ember ribs overlaid on a wrecked hull."""
    key = ("wreck_core", kind)
    hit = _lru_get(_PART_MESH_CACHE, key)
    if hit is not None:
        return hit

    m = Mesh()
    char = (20, 18, 17)
    ash = (38, 34, 32)
    soot = (28, 24, 22)
    coal = (138, 42, 16)
    hot = (196, 76, 24)

    if kind in ("car", "jeep", "tractor"):
        # Exposed charred engine block + glowing radiator coals + interior frame ribs
        m.add(box(0.74, 0.34, 0.82, char, center=(0.0, 0.84, 1.18)))
        m.add(box(0.38, 0.08, 0.40, coal, center=(0.0, 0.99, 1.18), emissive=True))
        m.add(box(0.46, 0.06, 0.10, hot, center=(0.0, 0.78, 1.60), emissive=True))
        for rz in (-0.35, 0.25):
            m.add(box(1.18, 0.08, 0.09, ash, center=(0.0, 1.14, rz)))
        m.add(box(0.86, 0.06, 1.02, soot, center=(0.0, 0.74, 0.05)))
        m.add(box(0.32, 0.04, 0.42, coal, center=(0.08, 0.77, 0.12), emissive=True))
    elif kind in ("truck", "gun_truck", "aa_truck"):
        # Exposed forward engine + charred dark bed + recessed smoldering ember fissures
        m.add(box(0.88, 0.42, 0.95, char, center=(0.0, 1.02, 1.85)))
        m.add(box(0.42, 0.08, 0.46, coal, center=(0.0, 1.21, 1.85), emissive=True))
        m.add(box(1.62, 0.10, 2.38, char, center=(0.0, 1.28, -1.05)))
        m.add(box(1.12, 0.14, 1.40, soot, center=(-0.10, 1.34, -0.95)))
        for rz in (-1.9, -1.1, -0.3):
            m.add(box(1.78, 0.12, 0.12, char, center=(0.0, 1.48, rz)))
        # Subtle broken ember cracks tucked inside blackened wreckage (no flat neon debug slab)
        for ex, ez, ew, ed, col in (
            (-0.26, -0.78, 0.34, 0.48, coal),
            (0.24, -1.32, 0.28, 0.42, coal),
            (0.02, -1.04, 0.18, 0.26, hot),
        ):
            m.add(box(ew, 0.04, ed, col, center=(ex, 1.41, ez), emissive=True))
        if kind == "aa_truck":
            m.add(disc_xz(0.0, -0.55, 0.66, 1.54, char, n=10, layer=2))
            m.add(disc_xz(0.0, -0.55, 0.34, 1.56, coal, n=8, layer=2))
    elif kind == "tanker":
        m.add(box(1.48, 0.16, 3.65, char, center=(0.0, 1.24, -0.45)))
        m.add(box(0.68, 0.06, 2.40, coal, center=(0.0, 1.33, -0.45), emissive=True))
        for rz in (-2.0, -1.2, -0.4, 0.4, 1.1):
            for sx in (-0.82, 0.82):
                m.add(box(0.14, 0.92, 0.14, char, center=(sx, 1.62, rz)))
            m.add(box(1.76, 0.12, 0.14, ash, center=(0.0, 2.08, rz)))
    elif kind in ("gunship", "gunship_air"):
        # Shattered rotor hub stump + burning avionics/cabin core
        m.add(box(0.42, 0.56, 0.42, char, center=(0.0, 2.48, 0.15)))
        m.add(box(0.95, 0.14, 1.85, coal, center=(0.0, 0.86, 0.65), emissive=True))
        m.add(box(0.62, 0.18, 0.68, hot, center=(0.0, 1.98, 0.15), emissive=True))
        for rz in (-0.4, 0.7, 1.6):
            m.add(box(1.38, 0.10, 0.10, ash, center=(0.0, 1.82, rz)))

    return _lru_put(_PART_MESH_CACHE, key, m, 192)


# ── Authored vehicle destruction profiles ───────────────────────────────────

VEHICLE_PROFILES: dict[str, VehicleDestructionProfile] = {
    "car": VehicleDestructionProfile(
        kind="car",
        blast_radius=4.8,
        scorch_radius=3.5,
        flash_dur=0.34,
        fireball_dur=1.45,
        fireball_lobes=5,
        fire_life=28.0,
        jolt_vy=2.6,
        jolt_pitch=-6.5,
        jolt_roll=4.5,
        sag_y=0.14,
        shockwave_r=7.2,
        shockwave_dur=0.42,
        parts=(
            PartSpec("hood", (0.0, 1.15, 1.25), (0.08, 1.0, 0.45), (4.0, 7.5), (4.8, 7.8), (220.0, 420.0), True, True, True, 12.0),
            PartSpec("trunk", (0.0, 1.10, -1.35), (-0.1, 0.9, -0.55), (3.5, 6.8), (4.0, 6.5), (200.0, 380.0), False, False, True, 12.0),
            PartSpec("door", (-0.88, 0.82, 0.10), (-1.0, 0.65, 0.15), (4.5, 8.2), (2.4, 4.8), (240.0, 440.0), False, True, True, 13.0),
            PartSpec("door", (0.88, 0.82, 0.10), (1.0, 0.68, -0.10), (4.5, 8.2), (2.4, 4.8), (240.0, 440.0), False, False, True, 13.0),
            PartSpec("roof_panel", (0.0, 1.48, -0.05), (0.2, 1.0, -0.2), (2.8, 5.2), (4.4, 7.2), (180.0, 340.0), True, True, True, 12.0),
            PartSpec("bumper", (0.0, 0.55, 1.95), (0.15, 0.45, 1.0), (5.0, 8.5), (2.0, 3.8), (190.0, 360.0), False, False, False, 11.0),
            PartSpec("wheel", (-0.86, 0.36, 1.15), (-0.95, 0.48, 0.35), (5.5, 9.2), (2.2, 4.4), (320.0, 580.0), False, False, False, 13.0),
            PartSpec("wheel", (0.86, 0.36, -1.10), (0.95, 0.45, -0.35), (5.2, 8.8), (2.0, 4.2), (320.0, 560.0), False, False, False, 13.0),
            PartSpec("glass_shard", (-0.35, 1.25, 0.65), (-0.45, 0.9, 0.6), (4.2, 7.8), (2.5, 5.0), (420.0, 720.0), False, False, False, 6.0),
            PartSpec("glass_shard", (0.35, 1.25, 0.65), (0.45, 0.9, 0.5), (4.2, 7.8), (2.5, 5.0), (420.0, 720.0), False, False, False, 6.0),
        ),
        fire_mounts=(
            FireMount((0.0, 0.92, 1.18), size=0.95, heat=1.25, smoky=True, embers=True, bed=True),
            FireMount((0.0, 1.05, -0.15), size=0.78, heat=1.10, smoky=True, embers=False, bed=False),
        ),
        cookoffs=(
            CookoffSpec(0.62, (0.0, 0.75, -0.95), radius=3.6, n_sparks=16, tracer_burst=False),
        ),
    ),
    "jeep": VehicleDestructionProfile(
        kind="jeep",
        blast_radius=5.0,
        scorch_radius=3.6,
        flash_dur=0.32,
        fireball_dur=1.40,
        fireball_lobes=5,
        fire_life=24.0,
        jolt_vy=2.8,
        jolt_pitch=-6.0,
        jolt_roll=5.5,
        sag_y=0.14,
        shockwave_r=7.5,
        shockwave_dur=0.40,
        parts=(
            PartSpec("hood", (0.0, 1.12, 1.25), (0.12, 1.0, 0.35), (4.2, 8.0), (4.5, 7.6), (220.0, 420.0), True, True, True, 11.0),
            PartSpec("roof_panel", (0.0, 1.62, -0.15), (-0.25, 1.0, -0.25), (3.4, 6.2), (4.6, 7.4), (190.0, 360.0), False, True, True, 11.0),
            PartSpec("bumper", (0.0, 0.54, 1.98), (0.0, 0.4, 1.0), (4.8, 8.6), (2.0, 3.8), (180.0, 340.0), False, False, False, 10.0),
            PartSpec("wheel", (-0.88, 0.40, 1.18), (-1.0, 0.50, 0.25), (5.5, 9.6), (2.2, 4.4), (340.0, 620.0), False, False, False, 12.0),
            PartSpec("wheel", (0.88, 0.40, -1.18), (1.0, 0.45, -0.30), (5.2, 9.2), (2.0, 4.2), (340.0, 600.0), False, False, False, 12.0),
            PartSpec("jerrycan", (-0.68, 0.96, -1.55), (-0.75, 0.95, -0.80), (5.0, 9.2), (3.8, 6.8), (360.0, 640.0), True, True, False, 10.0),
            PartSpec("glass_shard", (-0.30, 1.32, 0.55), (-0.3, 0.9, 0.65), (4.0, 7.5), (2.5, 4.5), (440.0, 760.0), False, False, False, 6.0),
            PartSpec("glass_shard", (0.30, 1.32, 0.55), (0.3, 0.9, 0.65), (4.0, 7.5), (2.5, 4.5), (440.0, 760.0), False, False, False, 6.0),
        ),
        fire_mounts=(
            FireMount((0.0, 0.98, 1.10), size=1.05, heat=1.20, smoky=True, embers=True, bed=True),
            FireMount((0.0, 0.95, -0.85), size=0.82, heat=1.05, smoky=True, embers=False, bed=False),
        ),
        cookoffs=(
            CookoffSpec(0.52, (0.0, 0.85, -1.10), radius=3.5, n_sparks=14, tracer_burst=False),
        ),
    ),
    "truck": VehicleDestructionProfile(
        kind="truck",
        blast_radius=6.2,
        scorch_radius=4.4,
        flash_dur=0.36,
        fireball_dur=1.65,
        fireball_lobes=5,
        fire_life=30.0,
        jolt_vy=2.4,
        jolt_pitch=-5.0,
        jolt_roll=-4.0,
        sag_y=0.16,
        shockwave_r=9.6,
        shockwave_dur=0.48,
        parts=(
            PartSpec("hood", (0.0, 1.45, 2.05), (0.15, 0.95, 0.65), (4.4, 8.2), (4.6, 7.8), (210.0, 390.0), True, True, True, 13.0),
            PartSpec("door", (-1.08, 1.38, 1.15), (-1.0, 0.55, 0.15), (4.6, 8.4), (2.4, 4.8), (220.0, 420.0), False, True, True, 13.0),
            PartSpec("door", (1.08, 1.38, 1.15), (1.0, 0.55, -0.10), (4.6, 8.4), (2.4, 4.8), (220.0, 420.0), False, False, True, 13.0),
            PartSpec("tailgate", (0.0, 1.48, -2.85), (0.05, 0.45, -1.0), (5.2, 8.8), (2.6, 4.6), (180.0, 340.0), False, False, False, 13.0),
            PartSpec("truck_slat", (-1.05, 1.72, -1.20), (-0.95, 0.72, -0.20), (4.8, 8.5), (3.2, 5.8), (280.0, 520.0), True, True, False, 12.0),
            PartSpec("truck_slat", (1.05, 1.72, -1.45), (0.95, 0.72, -0.35), (4.8, 8.5), (3.2, 5.8), (280.0, 520.0), False, False, False, 12.0),
            PartSpec("truck_slat", (0.0, 1.85, -2.05), (-0.25, 0.95, -0.65), (4.2, 7.6), (4.0, 6.8), (300.0, 540.0), True, False, False, 12.0),
            PartSpec("heavy_wheel", (-1.08, 0.48, -1.75), (-1.0, 0.42, -0.25), (5.0, 8.5), (2.0, 4.0), (300.0, 520.0), False, False, False, 14.0),
            PartSpec("heavy_wheel", (1.08, 0.48, 1.75), (1.0, 0.42, 0.25), (5.0, 8.5), (2.0, 4.0), (300.0, 520.0), False, False, False, 14.0),
            PartSpec("bumper", (0.0, 0.62, 2.85), (0.1, 0.35, 1.0), (5.0, 8.2), (1.8, 3.6), (180.0, 320.0), False, False, False, 12.0),
        ),
        fire_mounts=(
            FireMount((0.0, 1.15, 1.75), size=1.18, heat=1.28, smoky=True, embers=True, bed=True),
            FireMount((0.0, 1.42, -1.05), size=1.35, heat=1.20, smoky=True, embers=True, bed=False),
        ),
        cookoffs=(
            CookoffSpec(0.58, (0.0, 1.25, -0.90), radius=4.8, n_sparks=20, tracer_burst=True),
        ),
    ),
    "gun_truck": VehicleDestructionProfile(
        kind="gun_truck",
        blast_radius=6.4,
        scorch_radius=4.5,
        flash_dur=0.36,
        fireball_dur=1.65,
        fireball_lobes=5,
        fire_life=26.0,
        jolt_vy=2.5,
        jolt_pitch=-5.0,
        jolt_roll=4.5,
        sag_y=0.16,
        shockwave_r=10.0,
        shockwave_dur=0.46,
        parts=(
            PartSpec("hood", (0.0, 1.45, 2.05), (0.15, 0.95, 0.55), (4.6, 8.4), (4.8, 8.0), (220.0, 410.0), True, True, True, 12.0),
            PartSpec("door", (-1.08, 1.38, 1.15), (-1.0, 0.58, 0.15), (4.8, 8.6), (2.6, 5.0), (240.0, 440.0), False, True, True, 12.0),
            PartSpec("door", (1.08, 1.38, 1.15), (1.0, 0.58, -0.15), (4.8, 8.6), (2.6, 5.0), (240.0, 440.0), False, False, True, 12.0),
            PartSpec("truck_slat", (-1.02, 1.72, -1.10), (-0.95, 0.78, -0.15), (5.0, 8.8), (3.4, 6.2), (280.0, 520.0), True, True, False, 11.0),
            PartSpec("truck_slat", (1.02, 1.72, -1.10), (0.95, 0.78, -0.25), (5.0, 8.8), (3.4, 6.2), (280.0, 520.0), True, False, False, 11.0),
            PartSpec("hull_panel", (0.0, 1.95, -0.85), (0.1, 1.0, -0.35), (4.2, 7.6), (5.4, 8.4), (260.0, 460.0), True, True, True, 11.0),
            PartSpec("heavy_wheel", (-1.08, 0.48, -1.70), (-1.0, 0.45, -0.20), (5.2, 9.0), (2.2, 4.2), (320.0, 560.0), False, False, False, 12.0),
            PartSpec("heavy_wheel", (1.08, 0.48, 1.70), (1.0, 0.45, 0.20), (5.2, 9.0), (2.2, 4.2), (320.0, 560.0), False, False, False, 12.0),
            PartSpec("jerrycan", (0.82, 1.42, -2.10), (0.80, 0.90, -0.65), (5.4, 9.4), (4.2, 7.2), (380.0, 660.0), True, True, False, 10.0),
        ),
        fire_mounts=(
            FireMount((0.0, 1.15, 1.75), size=1.15, heat=1.25, smoky=True, embers=True, bed=True),
            FireMount((0.0, 1.50, -0.90), size=1.25, heat=1.25, smoky=True, embers=True, bed=False),
        ),
        cookoffs=(
            CookoffSpec(0.45, (0.0, 1.35, -0.85), radius=4.4, n_sparks=18, tracer_burst=True),
            CookoffSpec(0.92, (0.0, 1.25, -1.25), radius=3.8, n_sparks=14, tracer_burst=True),
        ),
    ),
    "aa_truck": VehicleDestructionProfile(
        kind="aa_truck",
        blast_radius=6.8,
        scorch_radius=4.8,
        flash_dur=0.38,
        fireball_dur=1.75,
        fireball_lobes=6,
        fire_life=24.0,
        jolt_vy=3.2,
        jolt_pitch=-6.5,
        jolt_roll=6.0,
        sag_y=0.18,
        shockwave_r=11.0,
        shockwave_dur=0.48,
        parts=(
            # Signature AA turret pops straight up off the pintle ring and tumbles!
            PartSpec("aa_turret", (0.0, 2.25, -0.55), (0.18, 1.0, -0.18), (4.2, 7.0), (11.0, 15.0), (260.0, 480.0), True, True, False, 13.0),
            PartSpec("hood", (0.0, 1.45, 2.05), (-0.15, 0.95, 0.65), (4.8, 8.6), (4.8, 8.0), (240.0, 420.0), True, True, True, 12.0),
            PartSpec("door", (-1.08, 1.38, 1.15), (-1.0, 0.58, 0.2), (4.8, 8.6), (2.6, 5.0), (250.0, 450.0), False, True, True, 12.0),
            PartSpec("door", (1.08, 1.38, 1.15), (1.0, 0.58, -0.2), (4.8, 8.6), (2.6, 5.0), (250.0, 450.0), False, False, True, 12.0),
            PartSpec("hull_panel", (-0.98, 1.65, -0.95), (-0.95, 0.82, -0.3), (5.2, 9.2), (3.8, 6.8), (280.0, 520.0), True, False, True, 11.0),
            PartSpec("hull_panel", (0.98, 1.65, -0.95), (0.95, 0.82, -0.3), (5.2, 9.2), (3.8, 6.8), (280.0, 520.0), True, False, True, 11.0),
            PartSpec("heavy_wheel", (-1.08, 0.48, -1.70), (-1.0, 0.46, -0.25), (5.4, 9.4), (2.2, 4.4), (340.0, 580.0), False, False, False, 12.0),
            PartSpec("heavy_wheel", (1.08, 0.48, 1.70), (1.0, 0.46, 0.25), (5.4, 9.4), (2.2, 4.4), (340.0, 580.0), False, False, False, 12.0),
        ),
        fire_mounts=(
            FireMount((0.0, 1.55, -0.55), size=1.45, heat=1.30, smoky=True, embers=True, bed=True),
            FireMount((0.0, 1.15, 1.75), size=1.05, heat=1.18, smoky=True, embers=False, bed=False),
        ),
        cookoffs=(
            CookoffSpec(0.45, (0.0, 1.65, -0.55), radius=5.0, n_sparks=22, tracer_burst=True),
            CookoffSpec(0.95, (0.0, 1.50, -0.75), radius=4.2, n_sparks=16, tracer_burst=True),
        ),
    ),
    "tanker": VehicleDestructionProfile(
        kind="tanker",
        blast_radius=8.5,
        scorch_radius=6.2,
        flash_dur=0.45,
        fireball_dur=2.25,
        fireball_lobes=6,
        fire_life=28.0,
        jolt_vy=2.9,
        jolt_pitch=-5.5,
        jolt_roll=5.0,
        sag_y=0.18,
        shockwave_r=14.0,
        shockwave_dur=0.58,
        parts=(
            PartSpec("tanker_cap", (0.0, 1.95, 1.20), (0.05, 0.85, 1.0), (7.5, 12.0), (5.5, 9.0), (200.0, 380.0), True, True, False, 13.0),
            PartSpec("tanker_cap", (0.0, 1.95, -2.95), (-0.05, 0.80, -1.0), (7.5, 12.0), (5.0, 8.5), (200.0, 380.0), True, True, False, 13.0),
            PartSpec("tanker_rib", (-0.85, 2.15, -0.35), (-1.0, 0.92, 0.25), (6.5, 11.2), (5.2, 9.0), (260.0, 480.0), True, True, False, 12.0),
            PartSpec("tanker_rib", (0.85, 2.15, -0.35), (1.0, 0.92, 0.25), (6.5, 11.2), (5.2, 9.0), (260.0, 480.0), True, True, False, 12.0),
            PartSpec("tanker_rib", (-0.85, 2.15, -1.55), (-1.0, 0.88, -0.35), (6.2, 10.8), (4.8, 8.5), (260.0, 480.0), True, False, False, 12.0),
            PartSpec("tanker_rib", (0.85, 2.15, -1.55), (1.0, 0.88, -0.35), (6.2, 10.8), (4.8, 8.5), (260.0, 480.0), True, False, False, 12.0),
            PartSpec("roof_panel", (0.0, 2.45, 2.05), (0.15, 1.0, 0.45), (5.2, 8.8), (6.5, 10.2), (240.0, 440.0), True, True, False, 12.0),
            PartSpec("heavy_wheel", (-1.10, 0.48, -1.95), (-1.0, 0.45, -0.25), (5.8, 9.6), (2.4, 4.6), (340.0, 580.0), False, False, False, 13.0),
            PartSpec("heavy_wheel", (1.10, 0.48, 1.75), (1.0, 0.45, 0.25), (5.8, 9.6), (2.4, 4.6), (340.0, 580.0), False, False, False, 13.0),
            PartSpec("bumper", (0.0, 0.62, 2.95), (0.0, 0.35, 1.0), (5.8, 9.4), (2.0, 4.0), (190.0, 350.0), False, False, False, 12.0),
        ),
        fire_mounts=(
            FireMount((0.0, 1.65, -0.55), size=2.05, heat=1.55, smoky=True, embers=True, bed=True),
            FireMount((-0.55, 1.45, -1.85), size=1.45, heat=1.35, smoky=True, embers=True, bed=False),
            FireMount((0.45, 1.35, 1.45), size=1.30, heat=1.25, smoky=True, embers=False, bed=False),
        ),
        cookoffs=(
            CookoffSpec(0.72, (0.0, 1.75, -0.65), radius=7.4, n_sparks=28, tracer_burst=False),
        ),
    ),
    "gunship": VehicleDestructionProfile(
        kind="gunship",
        blast_radius=7.8,
        scorch_radius=5.8,
        flash_dur=0.42,
        fireball_dur=2.10,
        fireball_lobes=6,
        fire_life=28.0,
        jolt_vy=0.0,
        jolt_pitch=0.0,
        jolt_roll=0.0,
        sag_y=0.0,
        shockwave_r=12.0,
        shockwave_dur=0.52,
        parts=(
            PartSpec("rotor_blade", (0.0, 2.75, 0.35), (0.92, 0.48, 0.38), (7.0, 11.5), (3.8, 6.8), (380.0, 680.0), False, True, False, 13.0),
            PartSpec("rotor_blade", (0.0, 2.75, -0.15), (-0.95, 0.50, -0.25), (7.0, 11.5), (3.8, 6.8), (380.0, 680.0), False, False, False, 13.0),
            PartSpec("rotor_blade", (0.0, 2.75, 0.10), (0.15, 0.58, -0.98), (6.5, 10.5), (4.2, 7.2), (360.0, 640.0), True, False, False, 13.0),
            PartSpec("tail_boom", (0.0, 1.45, -2.95), (-0.35, 0.72, -0.95), (5.5, 9.2), (4.0, 7.0), (160.0, 320.0), True, True, False, 14.0),
            PartSpec("rocket_pod", (-1.15, 0.88, 0.95), (-1.0, 0.65, 0.35), (5.5, 9.4), (3.4, 6.2), (260.0, 480.0), True, True, False, 12.0),
            PartSpec("rocket_pod", (1.15, 0.88, 0.95), (1.0, 0.65, 0.35), (5.5, 9.4), (3.4, 6.2), (260.0, 480.0), False, False, False, 12.0),
            PartSpec("hull_panel", (-0.75, 1.45, 0.65), (-0.85, 0.90, 0.25), (5.0, 8.6), (4.5, 7.5), (260.0, 460.0), True, False, False, 11.0),
            PartSpec("hull_panel", (0.75, 1.45, 0.65), (0.85, 0.90, -0.20), (5.0, 8.6), (4.5, 7.5), (260.0, 460.0), True, False, False, 11.0),
            PartSpec("glass_shard", (-0.35, 1.35, 2.85), (-0.4, 0.75, 0.9), (5.0, 8.5), (2.5, 4.5), (480.0, 780.0), False, False, False, 6.0),
            PartSpec("glass_shard", (0.35, 1.35, 2.85), (0.4, 0.75, 0.9), (5.0, 8.5), (2.5, 4.5), (480.0, 780.0), False, False, False, 6.0),
        ),
        fire_mounts=(
            FireMount((0.0, 1.85, 0.25), size=1.75, heat=1.35, smoky=True, embers=True, bed=True),
            FireMount((0.0, 1.05, 1.35), size=1.35, heat=1.25, smoky=True, embers=True, bed=False),
            FireMount((0.0, 1.30, -1.45), size=1.15, heat=1.15, smoky=True, embers=False, bed=False),
        ),
        cookoffs=(
            CookoffSpec(0.65, (0.0, 1.25, 0.45), radius=6.2, n_sparks=26, tracer_burst=True),
        ),
    ),
    "gunship_air": VehicleDestructionProfile(
        kind="gunship_air",
        blast_radius=5.2,
        scorch_radius=0.0,
        flash_dur=0.34,
        fireball_dur=1.25,
        fireball_lobes=4,
        fire_life=2.5,
        jolt_vy=0.0,
        jolt_pitch=0.0,
        jolt_roll=0.0,
        sag_y=0.0,
        shockwave_r=0.0,
        shockwave_dur=0.0,
        parts=(
            PartSpec("rotor_blade", (0.0, 1.35, 0.0), (0.85, 0.40, -0.35), (6.0, 10.0), (2.0, 4.5), (380.0, 660.0), True, True, False, 8.0),
            PartSpec("rocket_pod", (-1.10, -0.25, 0.55), (-1.0, -0.15, 0.20), (4.5, 8.0), (1.5, 3.5), (260.0, 480.0), True, True, False, 8.0),
            PartSpec("hull_panel", (0.70, 0.20, -0.50), (0.90, 0.45, -0.45), (4.5, 8.0), (2.5, 5.0), (280.0, 500.0), True, False, False, 8.0),
            PartSpec("hull_panel", (-0.65, 0.30, -0.90), (-0.85, 0.35, -0.55), (4.2, 7.6), (2.2, 4.5), (280.0, 500.0), False, True, False, 8.0),
            PartSpec("glass_shard", (0.0, 0.15, 1.65), (0.25, 0.35, 0.90), (4.0, 7.2), (1.5, 3.5), (450.0, 760.0), False, False, False, 5.0),
        ),
        fire_mounts=(),
        cookoffs=(),
    ),
    "tractor": VehicleDestructionProfile(
        kind="tractor",
        blast_radius=4.6,
        scorch_radius=3.2,
        flash_dur=0.32,
        fireball_dur=1.35,
        fireball_lobes=4,
        fire_life=20.0,
        jolt_vy=0.0,
        jolt_pitch=0.0,
        jolt_roll=0.0,
        sag_y=0.0,
        shockwave_r=6.8,
        shockwave_dur=0.40,
        parts=(
            PartSpec("hood", (0.0, 1.35, 1.05), (0.15, 1.0, 0.45), (3.8, 7.2), (4.5, 7.2), (220.0, 400.0), True, True, False, 10.0),
            PartSpec("exhaust_stack", (-0.37, 2.25, 1.10), (-0.65, 1.0, 0.15), (4.0, 7.5), (6.5, 9.8), (280.0, 520.0), True, True, False, 10.0),
            PartSpec("roof_panel", (0.0, 2.35, -0.35), (0.1, 1.0, -0.45), (3.2, 5.8), (4.4, 7.2), (180.0, 340.0), False, True, False, 10.0),
            PartSpec("heavy_wheel", (-0.95, 0.65, -0.85), (-1.0, 0.45, -0.20), (4.5, 7.8), (2.2, 4.0), (280.0, 480.0), False, False, False, 11.0),
            PartSpec("heavy_wheel", (0.95, 0.65, -0.85), (1.0, 0.45, -0.20), (4.5, 7.8), (2.2, 4.0), (280.0, 480.0), False, False, False, 11.0),
        ),
        fire_mounts=(
            FireMount((0.0, 1.25, 1.05), size=1.10, heat=1.20, smoky=True, embers=True, bed=True),
        ),
        cookoffs=(),
    ),
}

_KIND_ALIASES = {
    "aa": "aa_truck",
    "blocker": "jeep",
    "heli": "gunship",
    "helicopter": "gunship",
    "vip_heli": "gunship_air",
}


def get_vehicle_profile(kind: str) -> VehicleDestructionProfile:
    """Resolve a vehicle kind or alias to its authored destruction profile."""
    k = _KIND_ALIASES.get(kind, kind)
    return VEHICLE_PROFILES.get(k, VEHICLE_PROFILES["car"])


# ── Built-in standalone sprite fallbacks (used only if fx adapter is None) ─

def _radial_surface(size_px: int, inner_col: Color3, outer_col: Color3, alpha: int) -> pygame.Surface:
    key = ("rad", size_px, inner_col, outer_col, alpha // 8 * 8)
    hit = _lru_get(_FALLBACK_SURF_CACHE, key)
    if hit is not None:
        return hit
    s = pygame.Surface((size_px, size_px), pygame.SRCALPHA)
    c = size_px // 2
    for step in range(5, 0, -1):
        u = step / 5.0
        r = max(1, int(c * u))
        col = mix_col(inner_col, outer_col, u)
        a = int(key[4] * (1.0 - 0.72 * u * u))
        pygame.draw.circle(s, (*col, clamp(a, 0, 255)), (c, c), r)
    return _lru_put(_FALLBACK_SURF_CACHE, key, s, 96)


def _fallback_sprite(rad_m: float, inner: Color3, outer: Color3, alpha: int, max_px: int = 128):
    def draw(surf, sx, sy, scale, z):
        px = max(4, min(max_px, int(rad_m * scale)))
        img = _radial_surface(px * 2, inner, outer, alpha)
        surf.blit(img, (int(sx - px), int(sy - px)))
    draw.bounds_m = (rad_m * 1.1, rad_m * 1.1)
    draw.bounds_cap_px = (max_px * 2, max_px * 2)
    return draw


# ── Simulation bodies & manager ─────────────────────────────────────────────

class PartBody:
    """One detached, tumbling 3D vehicle component with floor bounce & settle."""

    __slots__ = (
        "pos", "vel", "rot", "ang_vel", "shape", "paint",
        "hot", "smoking", "age", "life", "bounces", "settled", "smoke_acc",
    )

    def __init__(
        self,
        pos: Vec3,
        vel: Vec3,
        rot: Vec3,
        ang_vel: Vec3,
        shape: str,
        paint: Optional[Color3],
        hot: bool,
        smoking: bool,
        life: float,
    ) -> None:
        self.pos = [float(pos[0]), float(pos[1]), float(pos[2])]
        self.vel = [float(vel[0]), float(vel[1]), float(vel[2])]
        self.rot = [float(rot[0]), float(rot[1]), float(rot[2])]
        self.ang_vel = [float(ang_vel[0]), float(ang_vel[1]), float(ang_vel[2])]
        self.shape = shape
        self.paint = paint
        self.hot = bool(hot)
        self.smoking = bool(smoking)
        self.age = 0.0
        self.life = float(life)
        self.bounces = 0
        self.settled = False
        self.smoke_acc = 0.0

    def step(self, dt: float, floor_y: float) -> bool:
        """Advance ballistic motion; return False once expired."""
        self.age += dt
        if self.age >= self.life:
            return False
        if self.settled:
            return True

        self.vel[1] -= 9.8 * dt
        self.pos[0] += self.vel[0] * dt
        self.pos[1] += self.vel[1] * dt
        self.pos[2] += self.vel[2] * dt
        self.rot[0] = (self.rot[0] + self.ang_vel[0] * dt) % 360.0
        self.rot[1] = (self.rot[1] + self.ang_vel[1] * dt) % 360.0
        self.rot[2] = (self.rot[2] + self.ang_vel[2] * dt) % 360.0

        ground = floor_y + 0.06
        if self.pos[1] <= ground and self.vel[1] < 0.0:
            self.pos[1] = ground
            if self.bounces < 2 and abs(self.vel[1]) > 1.8:
                self.bounces += 1
                self.vel[1] = -self.vel[1] * 0.34
                self.vel[0] *= 0.52
                self.vel[2] *= 0.52
                self.ang_vel[0] *= 0.55
                self.ang_vel[1] *= 0.55
                self.ang_vel[2] *= 0.55
            else:
                self.vel[0] = self.vel[1] = self.vel[2] = 0.0
                self.ang_vel[0] = self.ang_vel[1] = self.ang_vel[2] = 0.0
                self.settled = True
        return True


class VehicleDestruction:
    """Active destruction event + persistent burning wreck state for one vehicle."""

    __slots__ = (
        "kind", "profile", "pos", "yaw", "pitch", "roll", "paint",
        "age", "seed", "tag", "follow", "scorch_pos", "on_cookoff",
        "cookoff_fired", "cookoff_events", "jolt_dir", "_fb_lobes",
    )

    def __init__(
        self,
        kind: str,
        profile: VehicleDestructionProfile,
        pos: Vec3,
        yaw: float,
        pitch: float,
        roll: float,
        paint: Optional[Color3],
        seed: int,
        tag,
        follow: bool,
        scorch_pos: Optional[Vec3],
        on_cookoff: Optional[Callable] = None,
    ) -> None:
        self.kind = kind
        self.profile = profile
        self.pos = [float(pos[0]), float(pos[1]), float(pos[2])]
        self.yaw = float(yaw)
        self.pitch = float(pitch)
        self.roll = float(roll)
        self.paint = paint
        self.age = 0.0
        self.seed = int(seed)
        self.tag = tag
        self.follow = bool(follow)
        self.scorch_pos = scorch_pos
        self.on_cookoff = on_cookoff
        self.cookoff_fired = [False] * len(profile.cookoffs)
        self.cookoff_events: list[tuple[float, Vec3, CookoffSpec]] = []
        self.jolt_dir = 1.0 if (self.seed % 2 == 0) else -1.0
        lobes = []
        for i in range(profile.fireball_lobes + 3):
            lrng = random.Random(self.seed * 7 + i)
            if i == 0:
                ldir = (0.0, 1.0, 0.0)
                di = 0.0
            else:
                ang = lrng.uniform(0.0, math.tau)
                h = lrng.uniform(0.45, 0.95)
                ldir = _normalize((math.cos(ang) * h, lrng.uniform(0.35, 1.0), math.sin(ang) * h))
                di = 0.02 * i
            dur_i = profile.fireball_dur * lrng.uniform(1.25, 1.6)
            r0 = lrng.uniform(1.15, 1.65) * (profile.blast_radius / 4.2)
            lobes.append((ldir, di, dur_i, r0, (self.seed + i) % 3, 1.0 if i == 0 else 0.75))
        self._fb_lobes = tuple(lobes)

    def hull_transform(self) -> tuple[float, float, float]:
        """Return ``(dy, dpitch, droll)`` hull hop-and-sag for stationary wrecks."""
        if self.follow:
            return (0.0, 0.0, 0.0)
        p = self.profile
        sag = -p.sag_y
        if p.jolt_vy <= 0.0 and sag == 0.0:
            return (0.0, 0.0, 0.0)
        dur = 0.46
        if self.age >= dur:
            return (sag, p.jolt_pitch * 0.28, self.jolt_dir * p.jolt_roll * 0.42)
        u = clamp(self.age / dur, 0.0, 1.0)
        hop = math.sin(u * math.pi) * (p.jolt_vy * 0.075)
        dy = hop + sag * _ease(u)
        imp = math.sin(u * math.pi)
        dp = p.jolt_pitch * (0.28 * _ease(u) + 0.72 * imp)
        dr = self.jolt_dir * p.jolt_roll * (0.42 * _ease(u) + 0.58 * imp)
        return (dy, dp, dr)

    def world_pos(self) -> Vec3:
        dy, _, _ = self.hull_transform()
        return (self.pos[0], self.pos[1] + dy, self.pos[2])

    def world_pose(self) -> tuple[Vec3, float, float, float]:
        dy, dp, dr = self.hull_transform()
        return (
            (self.pos[0], self.pos[1] + dy, self.pos[2]),
            self.yaw,
            self.pitch + dp,
            self.roll + dr,
        )


class VehicleDestructionManager:
    """Owns all active vehicle explosions, flying 3D parts, smoke, scorches, and fires."""

    def __init__(
        self,
        *,
        seed: int = 1,
        fx=None,
        max_active: int = 12,
        max_parts: int = 96,
        max_puffs: int = 96,
    ) -> None:
        blast_sprites.prewarm()
        self._seed = int(seed)
        self._rng = random.Random(self._seed)
        self._fx = fx
        self._max_active = int(max_active)
        self._max_parts = int(max_parts)
        self._max_puffs = int(max_puffs)
        self.events: list[VehicleDestruction] = []
        self.parts: list[PartBody] = []
        self.puffs: list[dict] = []
        self.scorches: list[tuple[Vec3, float]] = []
        self._by_tag: dict = {}

    def clear(self) -> None:
        """Reset all tracked wrecks, parts, puffs, and scorches."""
        self.events.clear()
        self.parts.clear()
        self.puffs.clear()
        self.scorches.clear()
        self._by_tag.clear()

    def has_tag(self, tag) -> bool:
        """True if ``tag`` currently maps to an active destruction entry."""
        return tag is not None and tag in self._by_tag

    def sync_pose(self, tag, pos: Vec3, yaw: float = 0.0, pitch: float = 0.0, roll: float = 0.0) -> None:
        """Update a moving/skidding wreck's world pose."""
        vd = self._by_tag.get(tag)
        if vd is None:
            return
        vd.pos[0] = float(pos[0])
        vd.pos[1] = float(pos[1])
        vd.pos[2] = float(pos[2])
        vd.yaw = float(yaw)
        vd.pitch = float(pitch)
        vd.roll = float(roll)

    def hull_transform(self, tag) -> tuple[float, float, float]:
        """Return ``(dy, dpitch, droll)`` hull hop-and-sag for ``tag``."""
        vd = self._by_tag.get(tag)
        if vd is None:
            return (0.0, 0.0, 0.0)
        return vd.hull_transform()

    def trigger(
        self,
        kind: str,
        pos: Vec3,
        *,
        yaw: float = 0.0,
        pitch: float = 0.0,
        roll: float = 0.0,
        vel: Vec3 = (0.0, 0.0, 0.0),
        paint: Optional[Color3] = None,
        seed: Optional[int] = None,
        tag=None,
        follow: bool = False,
        floor_fn: Optional[Callable[[float, float], float]] = None,
        on_cookoff: Optional[Callable] = None,
    ) -> VehicleDestruction:
        """Trigger a vehicle-specific 3D destruction sequence at ``pos``."""
        profile = get_vehicle_profile(kind)
        ev_seed = self._seed + len(self.events) * 31 if seed is None else int(seed)
        rng = random.Random(ev_seed)

        scorch_pos: Optional[Vec3] = None
        if profile.scorch_radius > 0.0:
            gy = float(floor_fn(pos[0], pos[2])) if floor_fn is not None else float(pos[1])
            scorch_pos = (float(pos[0]), gy, float(pos[2]))
            self.scorches.append((scorch_pos, profile.scorch_radius))
            if len(self.scorches) > 24:
                del self.scorches[:-24]

        vd = VehicleDestruction(
            kind=profile.kind,
            profile=profile,
            pos=pos,
            yaw=yaw,
            pitch=pitch,
            roll=roll,
            paint=paint,
            seed=ev_seed,
            tag=tag,
            follow=follow,
            scorch_pos=scorch_pos,
            on_cookoff=on_cookoff,
        )
        if tag is not None and tag in self._by_tag:
            old = self._by_tag[tag]
            if old in self.events:
                self.events.remove(old)
        self.events.append(vd)
        if tag is not None:
            self._by_tag[tag] = vd
        while len(self.events) > self._max_active:
            dropped = self.events.pop(0)
            if dropped.tag is not None and self._by_tag.get(dropped.tag) is dropped:
                self._by_tag.pop(dropped.tag, None)

        rot_m = _rot_matrix(yaw, pitch, roll)
        for pspec in profile.parts:
            wpos = _xf_local(pspec.offset, pos, yaw, pitch, roll)
            ldir = _normalize((
                pspec.dir_local[0] + rng.uniform(-0.24, 0.24),
                max(0.15, pspec.dir_local[1] + rng.uniform(-0.14, 0.24)),
                pspec.dir_local[2] + rng.uniform(-0.24, 0.24),
            ))
            wdir = m_apply(rot_m, ldir)
            spd = rng.uniform(pspec.speed[0], pspec.speed[1])
            up = rng.uniform(pspec.up_boost[0], pspec.up_boost[1])
            pvel = (
                float(vel[0]) + wdir[0] * spd,
                max(0.5, float(vel[1]) * 0.4) + wdir[1] * spd + up,
                float(vel[2]) + wdir[2] * spd,
            )
            ang = (
                rng.choice((-1.0, 1.0)) * rng.uniform(pspec.spin[0], pspec.spin[1]),
                rng.choice((-1.0, 1.0)) * rng.uniform(pspec.spin[0], pspec.spin[1]),
                rng.choice((-1.0, 1.0)) * rng.uniform(pspec.spin[0], pspec.spin[1]),
            )
            self.parts.append(PartBody(
                pos=wpos,
                vel=pvel,
                rot=(rng.uniform(0.0, 360.0), yaw + rng.uniform(-25.0, 25.0), rng.uniform(0.0, 360.0)),
                ang_vel=ang,
                shape=pspec.shape,
                paint=paint if pspec.use_paint else None,
                hot=pspec.hot,
                smoking=pspec.smoking,
                life=pspec.life,
            ))

        if len(self.parts) > self._max_parts:
            del self.parts[:-self._max_parts]

        self._spawn_puff_burst(pos, profile.blast_radius, ev_seed, ring=True)
        return vd

    def _spawn_puff_burst(self, pos: Vec3, rad: float, seed: int, ring: bool = False) -> None:
        rng = random.Random(seed + 17)
        sc = clamp(rad / 5.0, 0.65, 1.8)
        if ring:
            for i in range(8):
                ang = (i / 8.0) * math.tau + rng.uniform(-0.25, 0.25)
                spd = rng.uniform(3.8, 6.2) * sc
                self.puffs.append(dict(
                    age=-0.02 * i,
                    dur=rng.uniform(1.5, 2.3),
                    x=pos[0] + math.cos(ang) * 0.50,
                    y=pos[1] + 0.25,
                    z=pos[2] + math.sin(ang) * 0.50,
                    vx=math.cos(ang) * spd,
                    vy=rng.uniform(0.3, 0.8),
                    vz=math.sin(ang) * spd,
                    lift=0.25,
                    r0=0.60 * sc,
                    r1=2.45 * sc,
                    alpha=176,
                    warm=0,
                    shade=(128, 110, 86),
                    seed=(seed + i) % 6,
                ))
        col_count = 8 if ring else 6
        col_shade = (40, 38, 40) if ring else (44, 44, 48)
        for i in range(col_count):
            ang = (i / float(col_count)) * math.tau + rng.uniform(-0.25, 0.25)
            spd = rng.uniform(0.7, 2.2) * sc
            self.puffs.append(dict(
                age=-(0.35 + 0.12 * i) if ring else -0.025 * i,
                dur=rng.uniform(3.5, 5.0),
                x=pos[0] + math.cos(ang) * 0.45,
                y=pos[1] + rng.uniform(0.7, 1.5),
                z=pos[2] + math.sin(ang) * 0.45,
                vx=math.cos(ang) * spd,
                vy=rng.uniform(2.0, 3.6) * sc,
                vz=math.sin(ang) * spd,
                lift=1.25,
                r0=0.90 * sc,
                r1=3.60 * sc,
                alpha=200,
                warm=2,
                shade=col_shade,
                seed=(seed + i) % 6,
            ))
        if len(self.puffs) > self._max_puffs:
            del self.puffs[:-self._max_puffs]

    def update(self, dt: float, *, floor_fn: Optional[Callable[[float, float], float]] = None) -> None:
        """Step all active destructions, detached 3D parts, smoke puffs, and cook-offs."""
        dt = clamp(float(dt), 0.0, 0.05)
        if dt <= 0.0:
            return

        keep_events: list[VehicleDestruction] = []
        for vd in self.events:
            vd.age += dt
            for idx, ck in enumerate(vd.profile.cookoffs):
                if not vd.cookoff_fired[idx] and vd.age >= ck.delay_s:
                    vd.cookoff_fired[idx] = True
                    wpos = _xf_local(ck.offset, vd.world_pos(), vd.yaw, vd.pitch, vd.roll)
                    vd.cookoff_events.append((vd.age, wpos, ck))
                    self._spawn_puff_burst(wpos, ck.radius, vd.seed + idx * 41, ring=False)
                    if vd.on_cookoff is not None:
                        vd.on_cookoff(vd, ck)
            max_life = max(
                vd.profile.fire_life,
                vd.profile.fireball_dur * 1.7 + 0.3,
                max((c.delay_s + 1.8 for c in vd.profile.cookoffs), default=0.0),
            )
            if vd.age < max_life:
                keep_events.append(vd)
            elif vd.tag is not None and self._by_tag.get(vd.tag) is vd:
                self._by_tag.pop(vd.tag, None)
        self.events = keep_events

        keep_parts: list[PartBody] = []
        for pb in self.parts:
            fy = float(floor_fn(pb.pos[0], pb.pos[2])) if floor_fn is not None else 0.0
            if pb.step(dt, fy):
                if pb.smoking and not pb.settled and pb.age < 2.2:
                    pb.smoke_acc += 9.5 * dt
                    if pb.smoke_acc >= 1.0 and len(self.puffs) < self._max_puffs:
                        pb.smoke_acc -= 1.0
                        self.puffs.append(dict(
                            age=0.0,
                            dur=1.4,
                            x=pb.pos[0],
                            y=pb.pos[1],
                            z=pb.pos[2],
                            vx=pb.vel[0] * 0.12,
                            vy=0.85,
                            vz=pb.vel[2] * 0.12,
                            lift=0.65,
                            r0=0.22,
                            r1=0.88,
                            alpha=128,
                            warm=1 if pb.hot and pb.age < 0.7 else 0,
                            shade=(44, 44, 48),
                            seed=int(abs(pb.pos[0]) * 7 + abs(pb.pos[2]) * 11) % 6,
                        ))
                keep_parts.append(pb)
        self.parts = keep_parts

        drag = math.exp(-dt * 1.7)
        keep_puffs: list[dict] = []
        for pf in self.puffs:
            pf["age"] += dt
            if pf["age"] >= pf["dur"]:
                continue
            if pf["age"] >= 0.0:
                pf["vx"] *= drag
                pf["vz"] *= drag
                pf["vy"] = pf["vy"] * math.exp(-dt * 0.8) + pf["lift"] * dt
                pf["x"] += pf["vx"] * dt
                pf["y"] += pf["vy"] * dt
                pf["z"] += pf["vz"] * dt
            keep_puffs.append(pf)
        self.puffs = keep_puffs[-self._max_puffs:]

    def active_lights(self, cap: int = 6) -> list[dict]:
        """Return dynamic point lights for flashes, cook-offs, and burning wrecks."""
        out: list[dict] = []
        for vd in self.events:
            p = vd.profile
            wpos = vd.world_pos()
            if vd.age < p.fireball_dur:
                sp = math.exp(-vd.age * 6.0)
                glow = max(0.0, 1.0 - vd.age / max(0.1, p.fireball_dur))
                out.append({
                    "pos": (wpos[0], wpos[1] + 1.3, wpos[2]),
                    "color": (255, 208, 128) if vd.age < 0.25 else (255, 136, 48),
                    "intensity": 2.9 * sp + 1.2 * glow,
                    "range": max(11.0, p.blast_radius * 2.6 + 8.0 * sp),
                })
            elif p.fire_mounts and vd.age < p.fire_life:
                fade = clamp(1.0 - max(0.0, vd.age - p.fire_life * 0.7) / max(0.5, p.fire_life * 0.3), 0.15, 1.0)
                fl = 0.82 + 0.18 * math.sin(vd.age * 16.0 + vd.seed)
                out.append({
                    "pos": (wpos[0], wpos[1] + 1.25, wpos[2]),
                    "color": (255, 134, 46),
                    "intensity": 1.25 * fl * fade,
                    "range": max(9.5, p.blast_radius * 1.9),
                })
            for t0, cpos, ck in vd.cookoff_events:
                cage = vd.age - t0
                if 0.0 <= cage < 1.0:
                    sp = math.exp(-cage * 7.0)
                    out.append({
                        "pos": (cpos[0], cpos[1] + 0.8, cpos[2]),
                        "color": (255, 206, 118),
                        "intensity": 2.6 * sp,
                        "range": ck.radius * 2.5,
                    })
        return out[:cap]

    def draw(self, r, tm: float, *, fx=None, flash_reduction: bool = False) -> None:
        """Render scorch decals, shockwaves, wreck cores, detached parts, fire, and smoke."""
        fx_mod = fx if fx is not None else self._fx
        fx_layer = getattr(fx_mod, "fx_layer", 6) if fx_mod is not None else 6
        use_gpu = getattr(r, "backend", "") == "gl"

        # 1. Scorch decals on the ground
        if self.scorches:
            if use_gpu:
                import numpy as np
                rows = []
                for spos, srad in self.scorches:
                    sx, sy, sz = spos[0], spos[1] + 0.025, spos[2]
                    if r.visible_sphere((sx, sy, sz), srad + 0.3):
                        rows.append((sx, sy, sz, srad, 0.0, 0.086, 0.074, 0.074, 0.90, float(DKIND_SCORCH), 0.0))
                if rows:
                    r.add_decals(np.asarray(rows, dtype=np.float32))
            else:
                sm = Mesh()
                for spos, srad in self.scorches:
                    sx, sy, sz = spos[0], spos[1] + 0.022, spos[2]
                    if r.visible_sphere((sx, sy, sz), srad + 0.3):
                        sm.add(disc_xz(sx, sz, srad, sy, (24, 21, 20), n=12, layer=1))
                if sm.faces:
                    r.add_dynamic(sm.verts, [(f[0], f[1], f[2], f[3], None, f[4], *f[5:]) for f in sm.faces])

        # 2. Wreck interior ember/char overlays + detached 3D vehicle parts
        batch = Mesh()
        for vd in self.events:
            p = vd.profile
            if p.fire_mounts and vd.age < p.fire_life:
                wpos, wyaw, wpitch, wroll = vd.world_pose()
                if r.visible_sphere(wpos, 5.5):
                    core = _build_wreck_core_mesh(vd.kind)
                    if core.faces:
                        batch.add(core, _rot_matrix(wyaw, wpitch, wroll), wpos)

        for pb in self.parts:
            ppos = (pb.pos[0], pb.pos[1], pb.pos[2])
            if not r.visible_sphere(ppos, 2.2):
                continue
            hot_now = pb.hot and pb.age < 1.15
            pmesh = _build_part_mesh(pb.shape, pb.paint, hot_now)
            rmat = m_mul(rot_y(pb.rot[1]), m_mul(rot_x(pb.rot[0]), rot_z(pb.rot[2])))
            batch.add(pmesh, rmat, ppos)

        if batch.faces:
            r.add_dynamic(
                batch.verts,
                [(f[0], f[1], f[2], f[3], None, f[4], *f[5:]) for f in batch.faces],
            )

        # 3. Smoke puffs (from initial blast, trailing parts, and cook-offs)
        for pf in self.puffs:
            age = pf["age"]
            if age < 0.0 or age >= pf["dur"]:
                continue
            ppos = (pf["x"], pf["y"], pf["z"])
            if not r.visible_sphere(ppos, pf["r1"] + 0.5):
                continue
            u = age / pf["dur"]
            alpha = int(pf["alpha"] * clamp(age / 0.14, 0.0, 1.0) * ((1.0 - u) ** 1.25)) // 8 * 8
            if alpha < 8:
                continue
            rad_m = pf["r0"] + (pf["r1"] - pf["r0"]) * math.sqrt(u)
            warmth = max(0, min(4, int(pf["warm"] * (1.0 - u * 2.1))))
            r.add_sprite(
                ppos,
                self._smoke_fn(fx_mod, warmth, pf["seed"], rad_m, alpha, pf.get("shade", (44, 44, 48))),
                layer=2,
            )

        # 4. Per-event flashes, fireballs, shrapnel streaks, persistent fire, cook-offs
        for vd in self.events:
            p = vd.profile
            wpos, wyaw, wpitch, wroll = vd.world_pose()
            if not r.visible_sphere(wpos, max(6.0, p.blast_radius + 4.0)):
                continue
            age = vd.age
            sc = clamp(p.blast_radius / 4.2, 0.65, 2.1)

            # Initial flash + ground flash spill (phys_occ sprites, no hard ground cut)
            fdur = p.flash_dur * (0.72 if flash_reduction else 1.0)
            if age < fdur:
                fk = (1.0 - age / max(1e-3, fdur)) ** 1.7
                frad = p.blast_radius * (0.55 + 0.9 * age / max(1e-3, fdur)) * (0.7 if flash_reduction else 1.0)
                fk_eff = fk * (0.5 if flash_reduction else 1.0)
                r.add_sprite((wpos[0], wpos[1] + 0.9, wpos[2]), blast_sprites.flash_sprite(frad, fk_eff), layer=fx_layer)

            if age < 0.6:
                ground_y = vd.scorch_pos[1] if vd.scorch_pos is not None else wpos[1]
                g_rad = p.blast_radius * 0.9 * (0.4 + 0.6 * min(1.0, age * 4.0))
                g_k = ((1.0 - age / 0.6) ** 1.4) * (0.55 if flash_reduction else 1.0)
                r.add_sprite(
                    (wpos[0], ground_y + 0.05, wpos[2]),
                    blast_sprites.ground_flash_sprite(g_rad, g_k),
                    layer=fx_layer,
                )

            # Multi-lobe billowing fireball cooling into dark smoke
            for ldir, di, dur_i, r0, variant, u_scale in vd._fb_lobes:
                la = age - di
                if la < 0.0 or la >= dur_i:
                    continue
                g = 1.0 - math.exp(-la * 7.0)
                rad = r0 * (0.35 + 0.85 * g) + 0.25 * la
                spread_m = g * p.blast_radius * 0.24
                fpos = (
                    wpos[0] + ldir[0] * spread_m,
                    wpos[1] + 0.6 + 0.9 * la + 0.55 * (min(la, 1.5) ** 2) + ldir[1] * spread_m,
                    wpos[2] + ldir[2] * spread_m,
                )
                u = clamp(la / max(1e-3, p.fireball_dur * u_scale), 0.0, 1.0)
                alpha_k = 1.0 - _ease(clamp((la - 0.65 * dur_i) / max(1e-3, 0.35 * dur_i), 0.0, 1.0))
                r.add_sprite(fpos, blast_sprites.fireball_sprite(rad, u, variant, alpha_k), layer=2)

            # Rising ember column + ballistic hot shrapnel streaks
            if age < 1.45:
                self._emit_shrapnel_streaks(r, wpos, age, 1.45, vd.seed, sc, 10)
                embers_fn = getattr(fx_mod, "embers", None)
                if callable(embers_fn):
                    r.add_sprite(
                        wpos,
                        embers_fn(tm, seed=vd.seed + 9, spread_m=1.4 * sc,
                                  height_m=3.4 * sc, n=14, heat=max(0.2, 1.3 - age * 0.8)),
                        layer=2,
                    )

            # Persistent anchored fires on the wreck's engine / cabin / bed / mast (ramp up after fireball)
            if p.fire_mounts and age < p.fire_life:
                grow = _ease(clamp((age - p.fireball_dur * 0.45) / 0.9, 0.0, 1.0))
                fade = clamp(1.0 - max(0.0, age - p.fire_life * 0.72) / max(0.5, p.fire_life * 0.28), 0.0, 1.0)
                if grow >= 0.02 and fade > 0.05:
                    for midx, fm in enumerate(p.fire_mounts):
                        mpos = _xf_local(fm.offset, wpos, wyaw, wpitch, wroll)
                        self._emit_fire(
                            fx_mod, r, mpos, tm, vd.seed + 101 + midx * 19,
                            fm.size * (0.45 + 0.55 * fade) * (0.25 + 0.75 * grow),
                            fm.heat * (0.4 + 0.6 * fade) * (0.5 + 0.5 * grow),
                            smoky=fm.smoky, embers=fm.embers, bed=fm.bed,
                        )

            # Secondary delayed cook-off blasts & tracer bursts
            for cidx, (t0, cpos, ck) in enumerate(vd.cookoff_events):
                cage = age - t0
                if not (0.0 <= cage < 1.35):
                    continue
                if cage < 0.28:
                    fk = (1.0 - cage / 0.28) ** 1.6
                    r.add_sprite(
                        (cpos[0], cpos[1] + 0.5, cpos[2]),
                        blast_sprites.flash_sprite(
                            ck.radius * (0.45 + cage * 1.4),
                            fk * (0.5 if flash_reduction else 1.0),
                        ),
                        layer=fx_layer,
                    )
                if cage < 1.1:
                    for j in range(3):
                        crng = random.Random(vd.seed + 300 + cidx * 29 + j)
                        c_ang = crng.uniform(0.0, math.tau)
                        c_h = crng.uniform(0.35, 0.85)
                        c_dir = _normalize((math.cos(c_ang) * c_h, crng.uniform(0.45, 1.0), math.sin(c_ang) * c_h))
                        cg = 1.0 - math.exp(-cage * 7.0)
                        c_rad = ck.radius * 0.30 * (0.4 + 0.8 * cg)
                        c_spread = cg * ck.radius * 0.26
                        c_fpos = (
                            cpos[0] + c_dir[0] * c_spread,
                            cpos[1] + 0.4 + 0.7 * cage + c_dir[1] * c_spread,
                            cpos[2] + c_dir[2] * c_spread,
                        )
                        c_alpha = 1.0 - _ease(clamp((cage - 0.70) / 0.40, 0.0, 1.0))
                        r.add_sprite(
                            c_fpos,
                            blast_sprites.fireball_sprite(c_rad, cage / 1.1, (vd.seed + cidx + j) % 3, c_alpha),
                            layer=2,
                        )
                self._emit_shrapnel_streaks(
                    r, cpos, cage, 1.15, vd.seed + 300 + cidx * 29,
                    clamp(ck.radius / 3.8, 0.7, 1.6), ck.n_sparks, tracer=ck.tracer_burst,
                )

    def _emit_shrapnel_streaks(
        self,
        r,
        origin: Vec3,
        age: float,
        dur: float,
        seed: int,
        sc: float,
        count: int,
        tracer: bool = False,
    ) -> None:
        ox, oy, oz = origin
        for i in range(count):
            ang = i * 2.399963 + seed * 0.37
            spd = (4.2 + (i % 5) * 1.35) * sc * (1.45 if tracer else 1.0)
            vx, vz = math.cos(ang) * spd, math.sin(ang) * spd
            vy = (4.8 + (i % 6) * 1.05) * sc * (1.35 if tracer else 1.0)
            py = oy + 0.35 + vy * age - 4.9 * age * age
            if py <= 0.05:
                continue
            ta = max(0.0, age - 0.045)
            ty = max(0.05, oy + 0.35 + vy * ta - 4.9 * ta * ta)
            hot = max(0.0, 1.0 - age / dur)
            col = (int(150 + 105 * hot), int(64 + 170 * hot), int(28 + 110 * hot))
            r.add_line3d(
                (ox + vx * ta, ty, oz + vz * ta),
                (ox + vx * age, py, oz + vz * age),
                col, 2 if (i % 3 == 0 or tracer) else 1, layer=2,
            )

    def _emit_fire(self, fx_mod, r, pos: Vec3, tm: float, seed: int, size: float, heat: float, *,
                   smoky: bool, embers: bool, bed: bool) -> None:
        emit_fn = getattr(fx_mod, "emit_fire", None)
        if callable(emit_fn):
            emit_fn(
                r, pos, tm, seed=seed, size=size, heat=heat,
                smoky=smoky, embers=embers, bed=bed, glow=False, layer=2,
            )
            return
        r.add_sprite(
            pos,
            _fallback_sprite(max(0.35, size * 0.9), (255, 240, 160), (240, 88, 22), 210, 96),
            layer=2,
        )

    def _smoke_fn(self, fx_mod, warmth: int, seed: int, rad_m: float, alpha: int, shade: Color3 = (44, 44, 48)):
        puff_fn = getattr(fx_mod, "smoke_puff", None)
        if callable(puff_fn):
            def draw(s, sx, sy, scale, z):
                rad = max(3, min(88, int(rad_m * scale)))
                if rad < 3:
                    return
                surf = puff_fn(warmth, seed % 6, rad, alpha, shade_col=shade)
                s.blit(surf, (int(sx - rad), int(sy - rad)))
            draw.bounds_m = (rad_m * 1.15, rad_m * 1.15)
            draw.bounds_cap_px = (176, 176)
            return draw
        inner = (160, 96, 56) if warmth > 0 else shade
        return _fallback_sprite(rad_m, inner, shade, alpha, 88)

    def _glow_fn(self, fx_mod, col: Color3, rad_m: float, tm: float, core: Color3, intensity: float, max_px: int):
        glow_fn = getattr(fx_mod, "glow", None)
        if callable(glow_fn):
            return glow_fn(col, rad_m, int(tm), core=core, intensity=intensity, max_px=max_px)
        return _fallback_sprite(rad_m, core, col, clamp(int(180 * intensity), 24, 240), max_px)
