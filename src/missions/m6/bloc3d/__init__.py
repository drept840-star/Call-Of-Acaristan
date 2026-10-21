"""bloc3d - the Bloc around the M6 yard and station, built from boxes.

Panel blocks, smokestacks, a radio mast, a water tower, watchtowers and wire,
plus Cyrillic signage drawn in a 5x7 pixel font: every piece is axis-aligned
boxes added to a static mesh, so it bakes with the set and costs nothing per
frame. Lamp builders return their lamp positions for the caller's halo
sprites (sprites are not baked).
"""
from .colours import (BEACON_RED, LETTER_CREAM, NEON_RED, PROP_RED,  # noqa: F401
                      WINDOW_COLD, WINDOW_DARK, WINDOW_WARM, dim)
from .font import GLYPH_H, GLYPH_W, GLYPHS, layout, width  # noqa: F401
from .signs import banner, billboard, board, letters, star  # noqa: F401
from .blocks import panel_block, roof_sign_pos  # noqa: F401
from .stacks import radio_mast, smokestack, water_tower  # noqa: F401
from .tower import fence_run, watchtower  # noqa: F401
