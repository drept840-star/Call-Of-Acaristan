
"""Head gear, as a registry keyed by catalog id.

Lifted out of Player.draw() so adding a hat is one function and one catalog
line, not another branch inside a 680-line method.

draw_kevlar() is the original head block verbatim - the same circle radius,
the same arc sweep, the same face offset, the same eye angles. That matters
twice: it is what lets the avatar-parity test pass for the default appearance,
and it means every other entry here is measured against a silhouette players
already recognise rather than against an ideal.

Draw order is load-bearing. Player.draw() calls this AFTER the arms and the
gun, so the head overlaps the barrel - where a hat drawn earlier disappears
under an arm, which reads as a rendering bug rather than a missing item.
"""
import math
import pygame

from engine.render2d import SurfacePen as _SurfacePen  # RPE6 B-033: Pen sink (facade only, E4)


def _shade(rgb, amt):
    """A darker version of a colour, for outlines.

    Gear is drawn on a head that is itself a dark blob on a dark torso, so at
    the sprite's real size the only thing that separates a beret from a helmet
    is a hard edge. Outlining against the item's own colour keeps that edge
    correct for every palette instead of pinning one fixed near-black that
    vanishes under Noir.
    """
    return tuple(max(0, int(v) - amt) for v in rgb[:3])


def _ring(pen, c, color, radius, width=1):
    pen.circle( color, (int(c["head_x"]), int(c["head_y"])),
                       radius, width)


def _shell(pen, c, rk, radius=None):
    """The issued helmet: a filled circle plus a forward arc highlight."""
    r = radius if radius is not None else 9
    pen.circle( rk["helmet"], (int(c["head_x"]), int(c["head_y"])), r)
    pen.arc(
        rk["helmet_arc"],
        (int(c["head_x"] - r), int(c["head_y"] - r), r * 2, r * 2),
        c["a"] - 0.8,
        c["a"] + 0.8,
        2,
    )
    return r


def _face(pen, c, rk):
    """The exposed face and the two eyes, at the original offsets."""
    face_x = c["head_x"] + c["d_x"] * 3
    face_y = c["head_y"] + c["d_y"] * 3
    pen.circle( rk["skin"], (int(face_x), int(face_y)), 5)
    for ang_off in (-0.25, 0.25):
        ex = face_x + math.cos(c["a"] + ang_off) * 3
        ey = face_y + math.sin(c["a"] + ang_off) * 3
        pen.circle( rk["eyes"], (int(ex), int(ey)), 1 + c["blinking"])
    return face_x, face_y


def _facing(pen, c, radius, pts, color, width=0):
    """Draw a polygon given in head-local (forward, lateral) coordinates.

    Every hat needs a brim, a band or a flap at some distance out of the head
    along the facing direction. Working in (forward, lateral) of the aim vector
    rather than absolute x/y is what keeps the gear attached to the head as the
    character turns. Each point is scaled by *radius*, so one set of numbers
    describes a hat at any head size.
    """
    d_x, d_y = c["d_x"], c["d_y"]
    p_x, p_y = -d_y, d_x
    hx, hy = c["head_x"], c["head_y"]
    poly = [(hx + d_x * (radius * fa) + p_x * (radius * fc),
             hy + d_y * (radius * fa) + p_y * (radius * fc))
            for fa, fc in pts]
    pen.polygon( color, poly, width)


def draw_kevlar(pen, c, rk):
    """The original helmet + face + eyes, unchanged."""
    _shell(pen, c, rk)
    _face(pen, c, rk)


def draw_peaked_cap(pen, c, rk):
    """Officer's cover: a low fabric crown and a stiff peak over the brow."""
    r = 8
    crown = rk["uniform"]
    pen.circle( crown, (int(c["head_x"]), int(c["head_y"])), r)
    _ring(pen, c, _shade(crown, 30), r)
    # Band across the crown in the helmet tone, so a cap cut from the same
    # cloth as the uniform still separates from the shoulders behind it.
    pen.line( rk["helmet"],
        (c["head_x"] - p_x(c, r * 0.9), c["head_y"] - p_y(c, r * 0.9)),
        (c["head_x"] + p_x(c, r * 0.9), c["head_y"] + p_y(c, r * 0.9)), 3,
    )
    # The peak is the whole read: a hard wedge thrown well past the head
    # circle. Anything subtler disappears at 32px.
    _facing(pen, c, r, [(0.25, -1.0), (1.8, -0.55), (1.8, 0.55), (0.25, 1.0)],
            _shade(rk["helmet"], 8))
    _face(pen, c, rk)


def draw_beret(pen, c, rk):
    """Beret: no shell at all - a soft blob flopped over to one side."""
    r = 8
    body = rk["uniform"]
    # Deliberately asymmetric and wider than the head. A symmetric hat would
    # be a circle, and a circle is what the free helmet already is.
    _facing(pen, c, r, [(0.35, -1.15), (0.1, 1.35), (-0.75, 1.45),
                            (-1.15, 0.5), (-0.85, -0.95), (0.0, -1.3)], body)
    _facing(pen, c, r, [(0.35, -1.15), (0.1, 1.35), (-0.75, 1.45),
                            (-1.15, 0.5), (-0.85, -0.95), (0.0, -1.3)],
            _shade(body, 30), 1)
    # Brow band, pushed forward so the mass of the beret sits behind it.
    pen.line( rk["helmet_rim"],
        (c["head_x"] - p_x(c, r * 0.95) + c["d_x"] * 2.5,
         c["head_y"] - p_y(c, r * 0.95) + c["d_y"] * 2.5),
        (c["head_x"] + p_x(c, r * 0.95) + c["d_x"] * 2.5,
         c["head_y"] + p_y(c, r * 0.95) + c["d_y"] * 2.5), 2,
    )
    _face(pen, c, rk)


def draw_balaclava(pen, c, rk):
    """Wool over the whole head. A dark eye band, and nothing of the shell."""
    r = 9
    cloth = rk["uniform"]
    pen.circle( cloth, (int(c["head_x"]), int(c["head_y"])), r)
    _ring(pen, c, _shade(cloth, 30), r)
    # The band across the eyes is the silhouette. Without the helmet's arc
    # highlight the head would just read as a slightly bigger torso.
    pen.line( _shade(cloth, 34),
        (c["head_x"] - p_x(c, r) + c["d_x"] * 2,
         c["head_y"] - p_y(c, r) + c["d_y"] * 2),
        (c["head_x"] + p_x(c, r) + c["d_x"] * 2,
         c["head_y"] + p_y(c, r) + c["d_y"] * 2), 4,
    )
    # Face opening: the skin circle shrinks to a slit, so the character still
    # reads as a person and not as a ball of wool.
    face_x = c["head_x"] + c["d_x"] * 3
    face_y = c["head_y"] + c["d_y"] * 3
    pen.circle( rk["skin"], (int(face_x), int(face_y)), 3)
    for ang_off in (-0.25, 0.25):
        ex = face_x + math.cos(c["a"] + ang_off) * 2
        ey = face_y + math.sin(c["a"] + ang_off) * 2
        pen.circle( rk["eyes"], (int(ex), int(ey)), 1 + c["blinking"])


def draw_goggles(pen, c, rk):
    """The issued shell plus a strap band and two lit lenses."""
    r = _shell(pen, c, rk)
    pen.line( rk["helmet_rim"],
        (c["head_x"] - p_x(c, r), c["head_y"] - p_y(c, r)),
        (c["head_x"] + p_x(c, r), c["head_y"] + p_y(c, r)), 3,
    )
    face_x = c["head_x"] + c["d_x"] * 3
    face_y = c["head_y"] + c["d_y"] * 3
    pen.circle( rk["skin"], (int(face_x), int(face_y)), 5)
    # Lenses are the one item here allowed a bright, palette-independent
    # colour: glass is the same glass under every uniform, and the glare is
    # what makes this hat readable from across a map.
    lens = (96, 158, 196)
    for ang_off in (-0.25, 0.25):
        ex = face_x + math.cos(c["a"] + ang_off) * 3
        ey = face_y + math.sin(c["a"] + ang_off) * 3
        pen.circle( lens, (int(ex), int(ey)), 3 + c["blinking"])
        pen.circle( _shade(lens, 55), (int(ex), int(ey)),
                           3 + c["blinking"], 1)


def draw_heavy_helmet(pen, c, rk):
    """The big one: a deeper shell, a rim ring, and a night-vision mount."""
    r = _shell(pen, c, rk, radius=11)
    _ring(pen, c, _shade(rk["helmet"], 26), r)
    pen.arc( rk["helmet_rim"],
        (int(c["head_x"] - r - 1), int(c["head_y"] - r - 1), (r + 1) * 2, (r + 1) * 2),
        c["a"] - 1.15, c["a"] + 1.15, 2,
    )
    # NVG mount on the brow. Drawn even with nothing mounted, because the
    # bracket sticking out past the shell is what sells the weight class.
    _facing(pen, c, r, [(0.85, -0.5), (1.4, -0.5), (1.4, 0.5), (0.85, 0.5)],
            rk["kevlar"])
    _facing(pen, c, r, [(0.85, -0.5), (1.4, -0.5), (1.4, 0.5), (0.85, 0.5)],
            _shade(rk["kevlar"], 24), 1)
    _face(pen, c, rk)


def p_x(c, amt):
    """Lateral (perpendicular-to-facing) offset in screen x."""
    return math.cos(c["a"] + math.pi / 2) * amt


def p_y(c, amt):
    """Lateral offset in screen y."""
    return math.sin(c["a"] + math.pi / 2) * amt


def draw_bare_curly(pen, c, rk):
    """No gear: Biribel's own curly dark hair (story outfits only, not a shop
    item). M5 Guard troopers all wear a black beret or a helmet, so a bare
    head is the gameplay half of his identity marker - same as the 3D/2D
    cutscene rig (core.outfits docstring)."""
    hair = rk.get("hair", (25, 30, 28))
    curl = tuple(min(255, v + 16) for v in hair[:3])
    hx = c["head_x"] - c["d_x"] * 1
    hy = c["head_y"] - c["d_y"] * 1
    pen.circle( hair, (int(hx), int(hy)), 7)
    # curls: small bumps round the crown/back so it never reads as a cap
    for fa, fc in ((-0.6, -0.75), (-0.95, 0.0), (-0.6, 0.75), (0.1, -0.95), (0.1, 0.95)):
        cx = hx + c["d_x"] * 6 * fa + p_x(c, 6 * fc)
        cy = hy + c["d_y"] * 6 * fa + p_y(c, 6 * fc)
        pen.circle( curl, (int(cx), int(cy)), 2)
    _face(pen, c, rk)


# Catalog id -> draw fn. Unknown ids fall through to kevlar in draw_head(), so
# a peer running a newer catalog than this one still gets a head.
# "head_bare_curly" is story-only (core.outfits.GAMEPLAY_HEAD): no catalog row.
HEADS = {
    "head_bare_curly": draw_bare_curly,
    "head_kevlar": draw_kevlar,
    "head_peaked_cap": draw_peaked_cap,
    "head_beret": draw_beret,
    "head_balaclava": draw_balaclava,
    "head_goggles": draw_goggles,
    "head_heavy_helmet": draw_heavy_helmet,
}


def head_context(draw_x, draw_y, d_x, d_y, a, blinking):
    """Everything a head needs to place itself, as one dict.

    head_x/head_y are the same two lines the original block computed inline
    (centre plus two pixels along the facing), kept here so the offset stays a
    single definition for every hat.
    """
    return {"draw_x": draw_x, "draw_y": draw_y, "d_x": d_x, "d_y": d_y, "a": a,
            "blinking": blinking, "head_x": draw_x + d_x * 2,
            "head_y": draw_y + d_y * 2}


def draw_head(surface, c, rk, head_id, pen=None):
    """Draw the gear for *head_id*. Never raises on an unknown id."""
    HEADS.get(head_id, draw_kevlar)(pen if pen is not None else _SurfacePen(surface), c, rk)
