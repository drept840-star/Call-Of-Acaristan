"""Burnt-out tram on the quarter junction (static decor). One variant at the
wreck's map footprint plus a 24 px margin on every side for the soft drop
shadow; the "PROVOCATEURS" spray tag is English. The painter lives in
missions.m5.tram_wreck._wreck_sprite (pygame only, imports core.config
alone); this module freezes it into a bakeable sprite so the quarter's
static layer just blits a PNG."""
VARIANTS = 1
MARGIN = 24


def size():
    from missions.m5.tram_wreck import RECT
    return RECT.w + 2 * MARGIN, RECT.h + 2 * MARGIN


def render(variant=0, scale=1):
    from game.art.m5 import _kit as K
    from missions.m5.tram_wreck import RECT, _wreck_sprite
    spr, _m = _wreck_sprite(RECT.w, RECT.h)
    return K.scaled(spr, scale)
