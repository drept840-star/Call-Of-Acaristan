"""Cached office and medical scenery, baked offline from the source GLBs.

All objects are grounded at y=0, centred in x/z, and face +z. Missing or
invalid assets return None so scene owners retain their procedural fallback.
No renderer, pygame or game state is touched at import time.
"""
from functools import lru_cache


@lru_cache(maxsize=128)
def prop(ref, screen=(48, 116, 88)):
    """Shared immutable mesh; screen=None leaves a dark, non-emissive screen."""
    from engine3d import Mesh
    from game.render3d_bridge import load_mesh_asset
    try:
        verts, faces = load_mesh_asset(ref)
        m = Mesh()
        m.verts = [tuple(v) for v in verts]
        m.faces = [(tuple(f[0]), tuple(screen) if len(f) > 2 and f[2] == 1 and screen is not None else tuple(f[1]),
                    2, True, bool(len(f) > 2 and f[2] == 1 and screen is not None)) for f in faces]
        if not m.verts or not m.faces:
            return None
        return m
    except (OSError, ValueError, KeyError, TypeError, IndexError):
        return None


@lru_cache(maxsize=96)
def display(ref, colour):
    """Procedural screen-only mesh: state colour, never baked into the shell."""
    from engine3d import Mesh
    source = prop(ref, None)
    if source is None:
        return None
    from game.render3d_bridge import load_mesh_asset
    _, faces = load_mesh_asset(ref)
    m = Mesh()
    m.verts = [(x, y, z + 0.001) for x, y, z in source.verts]
    m.faces = [(tuple(f[0]), colour, 2, True, True) for f in faces if len(f) > 2 and f[2] == 1]
    return m


@lru_cache(maxsize=16)
def workstation(pc="pc_zarya", monitor="monitor_crt", live=False):
    """Equipment only (not the desk), with a keyboard; grounded on desktop.

The tall tower rests on the same desktop as a compact security workstation.
Scene owners place this assembly on their existing solid furniture footprint.
"""
    from engine3d import Mesh, box
    cpu, screen = prop(pc), prop(monitor, None if live else (48, 116, 88))
    if cpu is None or screen is None:
        return None
    m = Mesh()
    if pc == "pc_zarya":
        m.add(cpu)
        m.add(screen, t=(0.0, 0.165, 0.0))
    else:
        m.add(cpu, t=(0.34, 0.0, 0.0))
        m.add(screen, t=(-0.12, 0.0, 0.0))
    m.add(box(0.4, 0.025, 0.14, (138, 132, 110), center=(-0.06, 0.0125, 0.34)))
    for row in range(3):
        m.add(box(0.34, 0.004, 0.018, (64, 62, 54), center=(-0.06, 0.027, 0.30 + row * 0.035)))
    return m


@lru_cache(maxsize=96)
def workstation_display(pc, monitor, colour):
    """Screen at precisely the same offset as workstation(live=True)."""
    from engine3d import Mesh
    screen = display(monitor, colour)
    if screen is None or workstation(pc, monitor, True) is None:
        return None
    m = Mesh()
    m.add(screen, t=(0.0, 0.165, 0.0) if pc == "pc_zarya" else (-0.12, 0.0, 0.0))
    return m


def medical_supplies():
    """A case and two bottles, for a shelf/table (no new pickup mechanics)."""
    from engine3d import Mesh, box
    m = Mesh()
    case, bottle = prop("medkit"), prop("pill_bottle")
    if case is None:
        case = box(0.36, 0.22, 0.16, (180, 38, 42), center=(0, 0.11, 0))
        case.add(box(0.06, 0.14, 0.012, (230, 226, 210), center=(0, 0.11, 0.086)))
        case.add(box(0.14, 0.05, 0.012, (230, 226, 210), center=(0, 0.11, 0.087)))
    m.add(case, t=(-0.12, 0, 0))
    for x, z in ((0.19, 0.0), (0.29, 0.025)):
        item = bottle if bottle is not None else box(0.06, 0.14, 0.06, (174, 112, 54), center=(0, 0.07, 0))
        m.add(item, t=(x, 0, z))
    return m
