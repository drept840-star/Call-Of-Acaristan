"""The 2D top-down M6 palette, for the 3D yard and train.

Sampled from gameplay frames of every 2D M6 stage (customs, no-man's-land,
rail yard, boxcar, train).  ``assets/tex3d/m6.gpl`` is the same set as a GIMP
palette, for painting the 3D textures.

The 2D night is blue-black slate with rust and amber in it: nine pixels in
ten sit under luma 30, the shadows carry only a little blue, the mids go rust
and the lamps go amber.  The 3D scenes were brighter, with saturated blue
shadows and peach lamps, which is most of why they read as a stock render.
"""

INK = (7, 8, 11)               # the 2D black: never true black
NIGHT = (12, 15, 20)
SLATE_DEEP = (16, 19, 25)
SLATE = (23, 29, 39)
SLATE_MID = (29, 36, 47)
SLATE_HI = (62, 76, 97)
STEEL = (89, 99, 114)
EMBER = (43, 32, 26)           # warm near-black: the sky over a lit town
RUST = (90, 51, 33)
RUST_HI = (111, 68, 41)
AMBER = (187, 133, 58)         # sodium lamp as the 2D draws it
LAMP_PALE = (174, 161, 105)
LAMP_CORE = (184, 181, 149)
SNOW = (198, 210, 226)         # decor._SNOW
SNOW_DIM = (168, 182, 202)     # decor._SNOW_DIM


def full(col):
    """``col`` scaled so its brightest channel is 255: a palette swatch as a
    light colour (lights carry their strength in ``intensity``)."""
    k = 255.0 / max(col)
    return tuple(min(255, int(round(c * k))) for c in col)


SODIUM = full(AMBER)           # (255, 181, 79): the key lamps
SODIUM_PALE = full(LAMP_PALE)  # (255, 236, 154): a lamp's hot side
LAMP_WHITE = full(LAMP_CORE)   # (255, 251, 206): headlights, bare bulbs
COLD_RIM = (136, 162, 206)     # SLATE_HI lifted: moonlight off the snow
