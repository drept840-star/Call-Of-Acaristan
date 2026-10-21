"""engine.collision - solid-world queries for gameplay (RPE6 §6.9).

``BoxWorld`` answers line of sight, rays and body overlap against a set of
axis-aligned boxes (3D sets: crates, wagons, walls). ``GridNav`` is A* on a
walkability grid sampled from any ``walkable(x, z)`` test, with straight-line
path smoothing and a path cache keyed on (start cell, goal cell, version).

Pure Python, no pygame, no side effects on import.
"""
from .boxes import BoxWorld, ray_aabb
from .nav import GridNav

__all__ = ["BoxWorld", "GridNav", "ray_aabb"]
