"""engine.render2d - one way to put pixels on screen during gameplay (RPE6 §6.6).

Phase 2 promoted the generic gameplay-render utilities from ``core.render_util``;
Phase 6 adds the sorted ``RenderQueue`` with the fixed layer table, the drawables
(``SurfaceDraw``, ``SpriteDraw``, ``RotatedSpriteDraw``, ``TextDraw``, primitives and the
counted ``CustomDraw`` escape hatch), ``Camera2D``, chunked ``StaticLayers`` and the
``PostFX`` plate cache. Everything is one import deep::

    from engine.render2d import RenderQueue, Layer, SurfaceDraw, CustomDraw

The engine never imports game code; the game's instance lives in ``game.render``.
"""
from __future__ import annotations

from .camera import Camera2D, clamp_top_left, deadzone_hold, ease_toward, legacy_shake
from .drawables import (SCREEN, WORLD, CircleDraw, CustomDraw, Drawable, FillDraw, LineDraw, PolyDraw, RectDraw, EllipseDraw, ArcDraw,
                        RotatedSpriteDraw, RotationCache, SpriteDraw, SurfaceDraw, SurfaceBatchDraw, TextDraw, UiPassDraw)
from .pen import RecordingPen, SurfacePen, pen_or_surface
from .postfx import OverlayDraw, PostFX
from .queue import LAYER_NAMES, Y_SORTED, Layer, RenderQueue, RenderStats
from .static import StaticLayer, StaticLayerDraw, StaticLayers
from .util import add_radial, doors_anim_sig, push_lamps, screen_visible, soft_shadow, soft_shadow_surface, swap_screen

__all__ = [
    "Camera2D", "clamp_top_left", "deadzone_hold", "ease_toward", "legacy_shake", "CircleDraw", "CustomDraw", "Drawable", "FillDraw", "LAYER_NAMES", "Layer", "LineDraw", "OverlayDraw",
    "PolyDraw", "PostFX", "RecordingPen", "SurfacePen", "pen_or_surface", "RectDraw", "EllipseDraw", "ArcDraw", "RenderQueue", "RenderStats", "RotatedSpriteDraw", "RotationCache", "SCREEN",
    "SpriteDraw", "StaticLayer", "StaticLayerDraw", "StaticLayers", "SurfaceDraw", "SurfaceBatchDraw", "TextDraw", "UiPassDraw", "WORLD", "Y_SORTED",
    "add_radial", "doors_anim_sig", "push_lamps", "screen_visible", "soft_shadow", "soft_shadow_surface", "swap_screen",
]
