"""engine.collision - solid-world queries for gameplay (RPE6 §6.9).

``BoxWorld`` answers line of sight, rays and body overlap against a set of
axis-aligned boxes (3D sets: crates, wagons, walls). ``MeshCollider`` and
``Placement`` do the same against an imported mesh's own triangles, so a
prop's hitbox is its exact shape, not a cube around it. ``GridNav`` is A* on a
walkability grid sampled from any ``walkable(x, z)`` test, with straight-line
path smoothing and a path cache keyed on (start cell, goal cell, version).

Pure Python, no pygame, no side effects on import.
"""
from .boxes import BoxWorld, ray_aabb
from .mesh import MeshCollider, Placement
from .nav import GridNav

__all__ = ["BoxWorld", "GridNav", "MeshCollider", "Placement", "ray_aabb"]
