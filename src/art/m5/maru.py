"""Maru, top-down gameplay sprite (84 x 84, anchor (42, 48) = feet/centre):
the figure_kit cast look - black hoodie, pistol in the good arm, wounded arm
in a white sling. Baked in 36 headings (10 degree steps) x 2 hit-strobe
skins. Variant = heading_index * 2 + strobe.

The figure itself is composed by the shared figure_kit rig (pygame only), via
missions.m5.draw._draw_maru_figure, so the cutscene and gameplay Maru stay
one character; this module turns it into fixed, bakeable frames."""
import math

from art.m5 import _kit as K

HEADINGS = 36
VARIANTS = HEADINGS * 2
W, H = 84, 84
ANCHOR = (42, 48)


def variant_for(angle, flash):
    b = int(round(angle / (2 * math.pi) * HEADINGS)) % HEADINGS
    return b * 2 + (int(flash) % 2)


def render(variant=0, scale=1):
    from missions.m5.draw import _draw_maru_figure
    b, strobe = divmod(int(variant) % VARIANTS, 2)
    s = K.new(W, H)
    _draw_maru_figure(s, ANCHOR[0], ANCHOR[1], b * 2 * math.pi / HEADINGS, strobe)
    return K.scaled(s, scale)
