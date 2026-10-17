"""Shared helpers for baked world layers (``game.art.<pack>.<name>`` adapter modules).

Two layer flavours exist:

* **chunk layers** - a mission's ``core.staticlayer`` bake callback (``_bake_mN_static``)
  rendered once over the whole map (``render_callback_layer``). The baked PNG replaces the
  runtime chunk cache; the callback stays in the mission module as bake source and as the
  live fallback. Opaque, world-sized.
* **camera layers** - a single camera-space painter rendered into a transparent layer with
  ``engine.assets.bake_camera_layer`` (see ``game.art.m3.cell_details``).

Adapters expose ``VARIANTS``/``VARIANT_NAMES``, ``render(variant, scale)``, optionally
``variant_for_state()`` (runtime variant pick; ``None`` = not representable -> caller falls
back to its procedural path), ``bake_setup(variant)`` (tools only) and ``BAKED_ONLY``.
"""
import pygame

__all__ = ["render_callback_layer", "map_world_size", "state_flags_variant"]


def render_callback_layer(bake_cb, world_size, chunk=512, fill=(0, 0, 0)):
    """Bake a ``core.staticlayer`` callback over ``world_size`` with the baking flag raised,
    exactly like the runtime chunk cache does (opaque chunks, camera at chunk corners)."""
    from core import staticlayer                    # lazy: game code, bake/fallback time only
    from engine.assets import bake_chunk_layer
    staticlayer.set_baking(True)
    try:
        return bake_chunk_layer(bake_cb, world_size=world_size, chunk=chunk, fill=fill)
    finally:
        staticlayer.set_baking(False)


def map_world_size(grid, tile):
    """Pixel size of a ``list[str]`` tile map."""
    mh = len(grid)
    mw = len(grid[0]) if mh else 0
    return (mw * tile, mh * tile)


def state_flags_variant(table, names):
    """Index of the current STATE flag tuple in ``table`` (tuples of bools), or ``None``."""
    from core.state import STATE                    # lazy
    key = tuple(bool(getattr(STATE, n, False)) for n in names)
    try:
        return table.index(key)
    except ValueError:
        return None


def scaled(surface, scale):
    if scale == 1:
        return surface
    w, h = surface.get_size()
    return pygame.transform.scale(surface, (int(w * scale), int(h * scale)))
