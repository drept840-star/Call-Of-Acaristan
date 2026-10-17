"""portraits.py - radio caller-ID portraits (polish pass T6b).

24x24 pixel-art busts, one per radio speaker, shown by ``ui.radio`` inside
the radio's caller-ID screen at an integer scale (2x at 1000x700, nearest
neighbour only).

Faces are DERIVED, not hand-drawn: ``cutscenes/figure_kit.SPECS`` is the
source of truth (the 3D rigs read the same table through
``cutscenes.cast3d.spec3d``). Every face is built per pixel on one fixed
24 px template (polish pass T6c - replaces the old 8x render + majority-vote
reduction, which smeared the shading into blotches): a five-step skin ramp
with upper-left key light and a cool rim, one hair mass per ``hair_style``,
then brows (``brow``), eyes (``iris``), jaw (``jaw``), stubble, beard, scar,
cigarette and headgear (cap / hat / beanie / scarf) switched by the spec; the
bust is tailored from the spec's wardrobe. Change a cast member in SPECS and
re-run this script - the portrait follows. Check with
``tools/sprites/portrait_refs.py`` (2D head | portrait). Organisations and
machines (narrator, PA, intercepts, system) get an insignia instead.

Frames (sheet ``spr_portraits``, anchor = top-left):
  <speaker key>   e.g. vasile, biribel, krap_command, ipa_dispatch, ...
  unknown         generic caller (used for speakers without a key)

    python tools/sprites/portraits.py [--preview] [--out DIR]
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import kit  # noqa: E402
import palette as P  # noqa: E402

FAMILY = "portraits"
SIZE = 24

METAL = (58, 62, 66)
METAL_HI = (120, 126, 130)


class C:
    """Tiny pixel canvas: p() point, r() rect, span() inclusive row run."""

    def __init__(self):
        self.s = kit.new(SIZE, SIZE)

    def p(self, x, y, c):
        if 0 <= x < SIZE and 0 <= y < SIZE:
            self.s.set_at((x, y), (*c[:3], 255))

    def r(self, x, y, w, h, c):
        self.s.fill((*c[:3], 255), (x, y, w, h))

    def span(self, y, x0, x1, c):
        self.r(x0, y, x1 - x0 + 1, 1, c)

    def get(self, x, y):
        return self.s.get_at((x, y))


# head silhouette rows: y -> (x0, x1)
HEAD = {4: (9, 14), 5: (8, 15), 6: (7, 16), 7: (7, 16), 8: (7, 16), 9: (7, 16),
        10: (7, 16), 11: (7, 16), 12: (7, 16), 13: (8, 15), 14: (8, 15), 15: (9, 14)}
KID_HEAD = {6: (9, 14), 7: (8, 15), 8: (7, 16), 9: (7, 16), 10: (7, 16), 11: (7, 16),
            12: (7, 16), 13: (7, 16), 14: (8, 15), 15: (9, 14), 16: (10, 13)}


def torso(c, coat, narrow=False, top=18):
    R = P.ramp(coat)
    rows = {top: (6, 17), top + 1: (4, 19)} if not narrow else {top: (7, 16), top + 1: (6, 17)}
    for y in range(top + 2, SIZE):
        rows[y] = (2, 21) if not narrow else (4, 19)
    for y, (x0, x1) in rows.items():
        c.span(y, x0, x1, R[2])
        c.span(y, x0, x0 + 2, R[3])           # key light from the upper left
        c.span(y, x1 - 2, x1, R[1])
    c.span(top, rows[top][0] + 1, rows[top][1] - 1, R[3])   # shoulder ridge
    return R


def neck(c, skin, top=15, bottom=18):
    S = P.ramp(skin)
    c.r(10, top, 4, bottom - top + 1, S[1])
    c.r(10, top, 4, 1, S[0])                    # chin shadow


def head(c, skin, shape=HEAD, ears=True):
    S = P.ramp(skin)
    for y, (x0, x1) in shape.items():
        c.span(y, x0, x1, S[2])
        c.p(x0, y, S[3])
        c.p(x1, y, S[1])
        if x1 - 1 > x0:
            c.p(x1 - 1, y, S[1] if y > min(shape) + 2 else S[2])
    if ears:
        ey = 9 if shape is HEAD else 10
        for y in range(ey, ey + 3):
            c.p(6, y, S[2])
            c.p(17, y, S[1])
        c.p(6, ey + 1, S[1])
    return S


def headset(c, side_mic=True):
    band = METAL
    c.span(2, 8, 15, band)
    c.p(7, 3, band)
    c.p(16, 3, band)
    c.p(6, 4, band)
    c.p(17, 4, band)
    c.span(2, 9, 12, METAL_HI)
    for y in range(5, 8):
        c.p(6, y, band)
    c.r(4, 8, 3, 4, METAL)                      # ear cup (left side of frame)
    c.p(4, 8, METAL_HI)
    c.p(5, 8, METAL_HI)
    c.r(17, 8, 2, 4, P.shade(METAL, 0.7))
    if side_mic:                                # boom to the mouth
        c.p(6, 12, METAL)
        c.p(7, 13, METAL)
        c.p(8, 14, METAL)
        c.p(9, 14, (30, 30, 32))
        c.p(9, 15, (30, 30, 32))


def finish(c):
    return kit.outline(c.s)


# -- the cast: derived from the cutscene cast sheet --------------------------
# Source of truth: src/cutscenes/figure_kit.py SPECS (2D cutscenes; the 3D
# rigs derive from the same table via cutscenes.cast3d.spec3d). Colours and
# feature switches come from the spec; placement comes from the pixel
# template below. M2 squad faces follow missions/m2/sniper3d.SPECS; the
# walking-sim extras follow walking_sim.
SCLERA = (219, 203, 173)
_FK = None


def _figure_kit():
    """cutscenes.figure_kit loaded by path (the generator runs without src/)."""
    global _FK
    if _FK is None:
        import importlib.util
        root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        src = os.path.join(root, "src")
        if src not in sys.path:          # figure_kit imports engine.core (RPE6 B-001)
            sys.path.insert(0, src)
        path = os.path.join(root, "src", "cutscenes", "figure_kit.py")
        spec = importlib.util.spec_from_file_location("_portrait_figure_kit", path)
        _FK = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(_FK)
    return _FK


def mix(a, b, t):
    return tuple(max(0, min(255, round(a[i] + (b[i] - a[i]) * t))) for i in range(3))


def dark(c, t=.3):
    return mix(c, (4, 6, 10), t)


def lite(c, t=.25):
    return mix(c, (255, 244, 225), t)


# M2 squad (missions/m2/sniper3d.SPECS) and walking-sim extras, laid over a
# figure_kit base so they share its face build.
KRAP_JACKET, KRAP_VEST = (55, 65, 80), (44, 50, 50)
SQUAD = {
    "gabi": dict(skin=(196, 156, 122), hair=(58, 38, 28), accent=(220, 175, 70), stubble=True),
    "seby": dict(skin=(178, 138, 108), hair=(30, 26, 22), accent=(85, 170, 225), stubble=False,
                 beanie=(38, 42, 50)),
    "darius": dict(skin=(150, 112, 86), hair=(18, 16, 15), accent=(110, 220, 145), stubble=False,
                   straps=(54, 62, 46)),
}
OLD_WOMAN = dict(skin=(185, 155, 128), scarf=(60, 55, 50), coat=(78, 64, 52), lapel=(60, 50, 40),
                 shirt=(110, 100, 88), stubble=False, long_coat=False, brow=2, jaw=.92)
HUNGRY_KID = dict(skin=(190, 160, 130), hair=(75, 60, 48), coat=(135, 128, 102),
                  lapel=(85, 78, 62), shirt=(85, 78, 62), stubble=False, long_coat=False,
                  brow=2, jaw=.9, kid=True, rim=(170, 150, 120))


def portrait_spec(key):
    """Portrait key -> figure_kit-style spec (copied, safe to edit)."""
    S = _figure_kit().SPECS
    base = {"krap_command": "krap", "ipa_dispatch": "ipa", "old_squadmate": "krap",
            "gabi": "krap", "seby": "krap", "darius": "krap",
            "old_woman": "civilian", "hungry_kid": "civilian"}.get(key, key)
    spec = dict(S[base])
    if key in SQUAD:
        spec.update(coat=KRAP_JACKET, lapel=dark(KRAP_JACKET, .25), vest=KRAP_VEST,
                    patch=None, **SQUAD[key])
    elif key == "old_squadmate":    # retired KRAP vet: greyed crop, same field tunic
        spec.update(hair=(150, 146, 140), jaw=1.0, brow=2)
    elif key == "old_woman":
        spec.update(OLD_WOMAN)
    elif key == "hungry_kid":
        spec.update(HUNGRY_KID)
    return spec


# -- pixel template ----------------------------------------------------------
# Everything below is placed per pixel on a fixed 24 px grid (no supersample /
# reduction pass: that is what made the old faces blotchy). Light comes from
# the upper left, a cool rim from the right. Each feature reads one SPECS
# field, so a cast change in figure_kit still flows straight into the frame.
BROW_Y, EYE_Y, MOUTH_Y = 8, 9, 13


def face_rows(spec):
    """Face silhouette y -> (x0, x1); the jaw rows follow SPECS ``jaw``.

    A full, rounded 12 px skull (top at row 3) with fleshy cheeks and a chin
    that never narrows below 4 px, so even lean ``jaw`` values read as a
    lean face, not a bare skull.
    """
    rows = {3: (8, 15), 4: (7, 16)}
    for y in range(5, 12):
        rows[y] = (6, 17)
    jaw = spec.get("jaw", 1.0)
    if jaw >= 1.03:                                   # square / heavy
        rows.update({12: (6, 17), 13: (7, 16), 14: (7, 16), 15: (9, 14)})
    elif jaw >= .97:
        rows.update({12: (6, 17), 13: (7, 16), 14: (8, 15), 15: (9, 14)})
    elif jaw >= .92:
        rows.update({12: (7, 16), 13: (7, 16), 14: (8, 15), 15: (10, 13)})
    else:                                             # lean
        rows.update({12: (7, 16), 13: (8, 15), 14: (9, 14), 15: (10, 13)})
    return rows


def _spans(c, rows, col):
    for y, spans in rows.items():
        for x0, x1 in spans:
            c.span(y, x0, x1, col)


def _mask(rows):
    return {(x, y) for y, spans in rows.items() for x0, x1 in spans for x in range(x0, x1 + 1)}


def _shade_mass(c, pts, R, lit=(), hi=()):
    """Flat ramp shading of a pixel mass: lit left edge, shaded right/bottom."""
    for x, y in pts:
        c.p(x, y, R[2])
    for x, y in pts:
        if (x - 1, y) not in pts:
            c.p(x, y, R[3])
        if (x + 1, y) not in pts or (x + 2, y) not in pts:
            c.p(x, y, R[1])
        if (x, y + 1) not in pts and (x + 1, y) in pts and (x - 1, y) in pts:
            c.p(x, y, R[1])
    for x, y in lit:
        if (x, y) in pts:
            c.p(x, y, R[3])
    for x, y in hi:
        if (x, y) in pts:
            c.p(x, y, R[4])


# hair masses, authored as 24-column pixel maps (row -> string). Key:
#   '#' hair base (auto-shaded: shade on the right / under-edge, lit on the left)
#   '+' lit   '*' highlight (sheen, light from the upper left)
#   '-' strand / clump separation   '=' deepest shadow
# Every style sits ON the skull with 1 px of volume past the head outline and
# a shaped hairline, so it reads as hair rather than a painted-on helmet.
HAIR_MAPS = {
    "crop": {
        1: ".........######.........",
        2: ".......*++######-.......",
        3: "......+*+#-##-##-#......",
        4: ".....++#-##-##-##-#.....",
        5: ".....+######-#####-.....",
        6: ".....##+.........##.....",
        7: ".....##..........##.....",
        8: ".....#............#.....",
    },
    "curly": {
        0: "........#..##..#........",
        1: "......##.####.###.......",
        2: ".....+*##+*##+##-#......",
        3: "....+*+#-##+#-##-##.....",
        4: "....+#-##+##-#+##-#-....",
        5: "....##+#-##-##-##-##....",
        6: "....#-##.#.##.#.#-##....",
        7: "....##............##....",
        8: ".....#............#.....",
    },
    "swept": {
        1: ".........*+####.........",
        2: ".......*++#####-#.......",
        3: "......+*+####-####-.....",
        4: ".....+*+####-####-##....",
        5: ".....#+...#####-###.....",
        6: ".....#.......####-#.....",
        7: ".....##.........-##.....",
        8: ".....#............#.....",
    },
    "slick": {
        1: "..........####..........",
        2: "........+**+###-........",
        3: "......+*++-####-##......",
        4: ".....+*+-####-####-.....",
        5: ".....#+-####-#####-.....",
        6: ".....##..........##.....",
        7: ".....#............#.....",
    },
    "shag": {
        0: ".........#.##.##........",
        1: ".......#*##+###-#.......",
        2: "......+*##+*###-##......",
        3: ".....+*+##-##+##-##.....",
        4: "....+*##-##+##-###-#....",
        5: "....+##-###-###-###-....",
        6: "....##-#.-#.#-#.#-##....",
        7: "....##..#.......#.##....",
        8: "....##............##....",
        9: "....+#............#-....",
        10: ".....#............#.....",
        11: ".....-............-.....",
    },
    "fringe": {
        1: ".........######.........",
        2: ".......+*######-#.......",
        3: "......+*+########-......",
        4: ".....+*+#########-#.....",
        5: ".....+##-#-##-#-###.....",
        6: ".....#-#-##-#-##-##.....",
        7: ".....##.-#.#-.#.-##.....",
        8: ".....#............#.....",
    },
    "spiky": {
        0: "........#..#..#..#......",
        1: ".......##.###.###.......",
        2: "......+*##+##-##-#......",
        3: ".....+*+#-##-##-##-.....",
        4: ".....+#-##-##-##-#-.....",
        5: ".....##-#.##.#.-###.....",
        6: ".....##...........#.....",
        7: ".....#............#.....",
    },
    "mop": {
        0: ".........######.........",
        1: ".......#########-.......",
        2: ".....+**+####+###-#.....",
        3: "....+*+##-###-###-##....",
        4: "....+##-###-###-###-....",
        5: "....##-###-###-####-....",
        6: "....#-#-##-#.-##-#-#....",
        7: "....##.-#..#...#.-##....",
        8: "....-#............#-....",
        9: ".....#............#.....",
    },
    "bald_white": {
        6: ".....+#..........#-.....",
        7: ".....+#..........#-.....",
        8: ".....##..........##.....",
        9: ".....#............#.....",
        10: ".....-............-.....",
    },
}
SKULL = {2: [(10, 13)]}                         # bare scalp for bald / covered heads


def _hair_pts(hs):
    """Style -> {(x, y): mark} from the pixel map."""
    return {(x, y): ch for y, row in HAIR_MAPS[hs].items() for x, ch in enumerate(row) if ch != "."}


def head_px(c, spec, dy=0):
    """Skin mass (face, ears, neck) with a five-step ramp; returns the mask."""
    skin = spec["skin"]
    S = P.ramp(skin)
    S[2] = tuple(skin)                         # exact SPECS skin survives (smoke likeness check)
    rows = {y + dy: [r] for y, r in face_rows(spec).items()}
    if spec.get("hair_style") in ("bald_white", "none") or spec.get("cap") or spec.get("hat"):
        rows.update({y + dy: s for y, s in SKULL.items()})
    face = _mask(rows)
    # neck first so the chin casts onto it
    for y in range(16 + dy, 18):
        c.span(y, 10, 13, S[1])
        c.p(10, y, S[2])
    c.span(16 + dy, 10, 13, mix(S[0], S[1], .4))
    _shade_mass(c, face, S)
    # sculpt: soft forehead + cheek light on the key side, a gentle jaw shade
    # on the far side (no hollow-cheek diagonal - that is what read as a skull)
    for x, y in ((7, 6), (8, 6), (7, 7), (7, 10), (8, 11), (10, 14)):
        if (x, y + dy) in face:
            c.p(x, y + dy, S[3])
    c.p(8, 5 + dy, S[4])
    c.p(9, 4 + dy, S[3])
    for x, y in ((16, 12), (15, 14), (14, 15)):
        if (x, y + dy) in face:
            c.p(x, y + dy, mix(S[1], S[2], .4))
    for y in range(9 + dy, 12 + dy):             # ears
        c.p(5, y, S[2])
        c.p(18, y, S[1])
    c.p(5, 10 + dy, S[1])
    c.p(18, 10 + dy, S[0])
    return S, face


def hair_px(c, spec, dy=0, S=None, face=None):
    """Hair from HAIR_MAPS: ramp-shaded clumps, sheen, and a cast shadow on
    the forehead under the hairline (the bit that seats hair on the head)."""
    hs = spec.get("hair_style")
    if hs not in HAIR_MAPS or spec.get("beanie") or spec.get("scarf"):
        return None
    marks = {(x, y + dy): ch for (x, y), ch in _hair_pts(hs).items()}
    if spec.get("cap") or spec.get("hat"):      # only the sideburns show under headgear
        marks = {(x, y): ch for (x, y), ch in marks.items() if y >= 6 + dy}
    pts = set(marks)
    R = P.ramp(spec["hair"], contrast=1.3 if sum(spec["hair"]) < 120 else 1.05)
    R[2] = tuple(spec["hair"])
    for (x, y), ch in marks.items():
        col = R[2]
        if ch == "#":
            if (x + 1, y) not in pts:
                col = R[0] if y >= 5 + dy else R[1]
            elif (x + 2, y) not in pts or (x, y + 1) not in pts:
                col = R[1]
            elif (x - 1, y) not in pts:
                col = R[3]
        else:
            col = {"+": R[3], "*": R[4], "-": R[1], "=": R[0]}[ch]
        c.p(x, y, col)
    if S is not None and face is not None:      # hairline shadow on the skin
        for x, y in pts:
            if (x, y + 1) in face and (x, y + 1) not in pts:
                c.p(x, y + 1, mix(S[1], S[2], .35) if x < 12 else S[1])
    return pts


def headgear_px(c, spec, dy=0):
    """Peaked cap, flat hat, beanie, headscarf - all off SPECS colours."""
    if spec.get("cap"):
        crown, band, visor = (19, 29, 46), (129, 133, 126), (12, 14, 20)
        R = P.ramp(crown)
        pts = _mask({1: [(8, 15)], 2: [(6, 17)], 3: [(5, 18)], 4: [(5, 18)]})
        _shade_mass(c, pts, R, [(7, 2), (8, 2), (9, 1), (6, 3)], [(8, 1)])
        c.span(5, 5, 18, band)
        c.p(5, 5, lite(band, .25))
        c.p(18, 5, dark(band, .3))
        c.span(6, 5, 18, visor)
        c.p(6, 6, lite(visor, .2))
        c.span(7, 7, 16, mix(spec["skin"], (30, 20, 30), .45))          # visor shadow
        c.p(11, 3, (190, 160, 90))
        c.p(12, 3, P.GOLD_HI)
        c.p(11, 2, P.GOLD_LO)
        c.p(12, 2, (190, 160, 90))
    if spec.get("hat"):
        h = spec["hat"]
        R = P.ramp(h)
        R[2] = tuple(h)
        pts = _mask({1: [(8, 15)], 2: [(7, 16)], 3: [(6, 17)], 4: [(6, 17)]})
        _shade_mass(c, pts, R, [(8, 2), (9, 2), (7, 3)], [(9, 1)])
        c.span(5, 4, 19, dark(h, .35))
        c.span(5, 4, 8, dark(h, .2))
        c.span(6, 7, 16, mix(spec["skin"], (30, 20, 30), .4))
    if spec.get("beanie"):
        b = spec["beanie"]
        R = P.ramp(b)
        pts = _mask({1: [(9, 14)], 2: [(7, 16)], 3: [(6, 17)], 4: [(5, 18)]})
        _shade_mass(c, pts, R, [(8, 2), (7, 3), (9, 1), (6, 4)], [(8, 2)])
        for x in range(5, 19):
            c.p(x, 5, R[1] if x % 2 else R[2])
            c.p(x, 6, R[0] if x % 2 else R[1])
        c.p(5, 5, R[3])
        c.p(5, 6, R[2])
    if spec.get("scarf"):
        s = spec["scarf"]
        R = P.ramp(s)
        rows = {2: [(8, 15)], 3: [(6, 17)], 4: [(5, 18)], 5: [(5, 18)], 6: [(5, 7), (16, 18)]}
        for y in range(7, 15):
            rows[y] = [(5, 7), (16, 18)]
        rows[14] = [(6, 8), (15, 17)]
        rows[15] = [(7, 9), (14, 16)]
        rows[16] = [(9, 14)]
        pts = _mask(rows)
        _shade_mass(c, pts, R, [(7, 3), (8, 3), (6, 4), (6, 8)], [(8, 3)])
        for x, y in ((9, 4), (12, 4), (15, 4), (6, 10), (17, 10)):    # cloth folds
            c.p(x, y, R[1])
        c.r(11, 16, 2, 2, R[1])                                         # knot
        c.p(11, 16, R[3])
        c.span(6, 8, 15, mix(spec["skin"], (30, 20, 30), .3))


def features_px(c, spec, S, face, dy=0):
    """Brows, eyes, nose, mouth, beard, stubble, scar, cigarette, rim."""
    skin, hair, hs = spec["skin"], spec["hair"], spec.get("hair_style")
    by, ey, my = BROW_Y + dy, EYE_Y + dy, MOUTH_Y + dy
    bw = spec.get("brow", 2)
    bc = dark(hair, .15) if hs != "bald_white" else (190, 190, 185)
    if spec.get("scarf"):
        bc = mix(skin, (40, 30, 25), .55)
    for x0, x1 in ((8, 10), (13, 15)):
        for x in range(x0, x1 + 1):
            outer = x == (x0 if x0 < 12 else x1)
            if bw >= 3 or not outer:
                c.p(x, by, bc if not outer else mix(bc, S[1], .35))
    if bw >= 4:                                     # heavy brows: frown pixels
        c.p(10, by, dark(bc, .3))
        c.p(13, by, dark(bc, .3))
    lid = mix(skin, (30, 15, 15), .6)
    sclera = mix(SCLERA, skin, .3)
    for x in (9, 13):
        c.p(x, ey, sclera if bw < 4 else mix(sclera, lid, .45))
        c.p(x + 1, ey, spec["iris"])
    c.p(8, ey, mix(S[2], lid, .15))                 # lid corner (soft, not a socket)
    c.p(15, ey, mix(S[1], S[2], .5))
    # nose: lit bridge, shadow cast to the right
    c.p(11, ey + 1, S[3])
    c.p(12, ey + 1, S[2])
    c.p(12, ey + 2, S[1])
    c.p(13, ey + 2, mix(S[1], S[0], .5))
    c.p(11, ey + 2, S[2])
    # mouth
    lip = mix(skin, (40, 20, 25), .55)
    c.span(my, 10, 12, lip)
    c.p(13, my, mix(skin, (40, 20, 25), .35))
    c.p(11, my + 1, S[3])
    if spec.get("stubble"):
        sc = mix(skin, (16, 14, 14), .32)
        for x, y in ((9, 12), (13, 12), (8, 13), (15, 13), (9, 14), (14, 14), (10, 15), (12, 15),
                     (13, 14)):
            if (x, y + dy) in face:
                c.p(x, y + dy, mix(sc, tuple(c.get(x, y + dy))[:3], .45))
    if spec.get("beard"):
        b = spec["beard"]
        R = P.ramp(b)
        R[2] = tuple(b)
        rows = {10 + dy: [(6, 6), (17, 17)], 11 + dy: [(6, 7), (16, 17)], 12 + dy: [(6, 17)],
                13 + dy: [(6, 9), (14, 17)], 14 + dy: [(7, 16)], 15 + dy: [(8, 15)],
                16 + dy: [(9, 14)], 17 + dy: [(10, 13)]}
        pts = _mask(rows)
        _shade_mass(c, pts, R, [(8, 14 + dy), (9, 15 + dy)], [(8, 12 + dy)])
        c.span(my, 10, 13, dark(b, .45))
        for x, y in ((10, 15), (13, 15), (11, 16), (12, 14)):
            c.p(x, y + dy, R[1])
    if spec.get("scar"):
        for x, y in ((8, 6), (9, 7), (9, 8), (10, 11), (10, 12)):
            c.p(x, y + dy, lite(skin, .22))
        for x, y in ((9, 6), (10, 7), (11, 12)):
            c.p(x, y + dy, dark(skin, .3))
    if spec.get("cig"):
        c.p(13, my, (196, 140, 80))
        c.p(14, my, (232, 230, 222))
        c.p(15, my + 1, (232, 230, 222))
        c.p(16, my + 1, (255, 96, 30))
        c.p(16, my, (255, 170, 90))
    # rim light: cool (or the spec's own) edge on the shaded side
    rim = spec.get("rim", (137, 168, 191) if not spec.get("president") else (248, 202, 128))
    for y in range(6 + dy, 9 + dy):              # short temple glint, not a cheek line
        xs = [x for x, yy in face if yy == y]
        if xs and not spec.get("scarf"):
            c.p(max(xs), y, mix(rim, S[1], .8))


# -- 2D-sampled face (polish pass T6d) ---------------------------------------
# The cutscene face (cutscenes.figure_kit._face) is replayed through a
# recording pen and its geometry - skull/jaw outline, key-light and shade
# planes, neck, ear, every hair polygon, beard and headgear - is rasterised
# straight onto the 24 px grid by pixel-centre coverage (no supersampled
# colour averaging, so no blotches). The fine features (lids, irises, nose,
# creases, mouth, stubble) collapse below one pixel at this size, so they are
# re-placed per pixel at the SAME 2D coordinates through the same mapping.
# Result: the 3/4 view, ear, angular jaw, tired heavy-lidded eyes and the
# actual hair shapes of the cutscenes, at portrait scale.
FU = 4.5                      # 2D face units per portrait pixel
FX0, FY0 = 12.0, 9.3          # portrait pixel position of face unit (0, 0)


def fpx(x, y, dy=0):
    """2D face units -> portrait pixel cell."""
    return int((x / FU) + FX0), int((y / FU) + FY0 + dy)


class _RecPen:
    """Stand-in for figure_kit._Pen that records primitives in face units."""

    def __init__(self):
        self.ops, self.ox, self.oy, self.k = [], 0.0, 0.0, 1.0
        import pygame
        self.s = pygame.Surface((4, 4))          # stubble rects land here (ignored)

    def p(self, x, y, light=False):
        return (0, 0)

    def w(self, v):
        return 1

    def poly(self, col, pts, light=False):
        self.ops.append(("poly", tuple(col[:3]), [(x + self.ox, y + self.oy) for x, y in pts]))

    def line(self, col, pts, width=1, light=False):
        self.ops.append(("line", tuple(col[:3]), [(x + self.ox, y + self.oy) for x, y in pts], width))

    def ell(self, col, x0, y0, x1, y1, width=0):
        self.ops.append(("ell", tuple(col[:3]), (x0, y0, x1, y1)))

    def circ(self, col, x, y, r, width=0):
        self.ops.append(("circ", tuple(col[:3]), (x, y, r)))


def _inside(pts, x, y):
    n, hit = len(pts), False
    for i in range(n):
        x1, y1 = pts[i]
        x2, y2 = pts[(i + 1) % n]
        if (y1 > y) != (y2 > y) and x < x1 + (y - y1) * (x2 - x1) / (y2 - y1):
            hit = not hit
    return hit


_SUB = [((i + .5) / 4, (j + .5) / 4) for i in range(4) for j in range(4)]


def _cover(test, dy, thresh=.5):
    """Cells whose 4x4 sub-samples pass ``test(ux, uy)`` at least ``thresh``."""
    cells = set()
    for py in range(SIZE):
        for px in range(SIZE):
            hits = sum(test((px + sx - FX0) * FU, (py + sy - FY0 - dy) * FU) for sx, sy in _SUB)
            if hits >= thresh * len(_SUB):
                cells.add((px, py))
    return cells


def _line_cells(pts, dy):
    cells = []
    for (x1, y1), (x2, y2) in zip(pts, pts[1:]):
        n = max(2, int(max(abs(x2 - x1), abs(y2 - y1)) / FU * 4) + 1)
        for i in range(n + 1):
            t = i / n
            c_ = fpx(x1 + (x2 - x1) * t, y1 + (y2 - y1) * t, dy)
            if c_ not in cells:
                cells.append(c_)
    return cells


def _record_face(spec):
    fk = _figure_kit()
    pen = _RecPen()
    sp = dict(spec)
    if sp.get("beanie") or sp.get("scarf"):    # portrait-only headgear: no 2D hair under it
        sp["hair_style"] = "none"
    sp.pop("cap", None) if sp.get("beanie") else None
    fk._face(pen, sp, 0, 0, look=.8, cig=False)
    return pen.ops


HEAD_TOP, CHIN_ROW, FU_MIN = 1.0, 17.4, 4.6   # crown leaves a row for the outline


def _fit_frame(ops):
    """Scale/offset so the tallest point (hair, curls, cap crown) sits inside
    the frame with room for the outline, and the chin stays above the collar.
    Big hair (mop, shag) gets a slightly smaller head instead of a cropped one."""
    global FU, FY0
    top = 0.0
    for op in ops:
        if op[0] == "poly":
            top = min(top, min(y for _, y in op[2]))
        elif op[0] == "circ":
            top = min(top, op[2][1] - op[2][2])
    chin = 34.0
    FU = max(FU_MIN, (chin - top) / (CHIN_ROW - HEAD_TOP))
    FY0 = HEAD_TOP - top / FU


def face_2d(c, spec, dy=0):
    """Head, hair and face sampled from the 2D cutscene face. Returns (S, face)."""
    skin = tuple(spec["skin"])
    S = P.ramp(skin)
    S[2] = skin
    hair = tuple(spec["hair"])
    R = P.ramp(hair, contrast=1.3 if sum(hair) < 120 else 1.05)
    R[2] = hair
    fk = _figure_kit()
    shade2d, light2d = fk._mix(skin, (60, 30, 30), .38), fk._lite(skin, .22)
    neck2d = fk._mix(skin, (40, 20, 20), .5)
    ops = _record_face(spec)
    _fit_frame(ops)
    # colour map: 2D flat tones -> portrait ramps (exact SPECS skin/hair survive)
    cmap = {skin: S[2], shade2d: mix(shade2d, S[1], .3), light2d: mix(light2d, S[3], .4),
            neck2d: mix(neck2d, S[0], .3), hair: R[2]}
    geo_cols = {hair}
    for key in ("beard", "hat", "bandana"):
        if spec.get(key):
            geo_cols |= {tuple(spec[key])}
    cap_cols = {(19, 29, 46), (129, 133, 126), (12, 14, 20), (190, 160, 90)}
    if spec.get("cap"):
        geo_cols |= cap_cols
    if spec.get("hat"):
        geo_cols |= {fk._dark(tuple(spec["hat"]), .35)}
    face, hair_px_, phase = set(), set(), "geo"
    for op in ops:
        kind, col = op[0], op[1]
        if kind == "ell":                         # the ear closes the geometry pass
            x0, y0, x1, y1 = op[2]
            cx_, cy_, rx, ry = (x0 + x1) / 2, (y0 + y1) / 2, abs(x1 - x0) / 2, abs(y1 - y0) / 2
            cells = _cover(lambda ux, uy: ((ux - cx_) / rx) ** 2 + ((uy - cy_) / ry) ** 2 <= 1, dy, .4)
            xmin = min(p_[0] for p_ in cells) if cells else 0
            for x, y in cells:
                if (x, y) not in hair_px_ and (x, y) not in face:
                    c.p(x, y, mix(col, S[1], .35) if x == xmin else mix(col, skin, .4))
            for x, y in cells:
                face.add((x, y))
            phase = "feat"
            continue
        if phase == "feat" and col not in geo_cols:
            continue                              # fine features are re-placed below
        is_hair = col == hair or (col in cap_cols and spec.get("cap"))
        if kind == "poly":
            pts = op[2]
            cells = _cover(lambda ux, uy: _inside(pts, ux, uy), dy)
        elif kind == "circ":
            x_, y_, r_ = op[2]
            cells = _cover(lambda ux, uy: (ux - x_) ** 2 + (uy - y_) ** 2 <= r_ * r_, dy, .45)
        else:                                     # line: 1 px stroke
            cells = _line_cells(op[2], dy)
            if col == fk._lite(hair, .35) or col == fk._lite(hair, .45) or col == fk._lite(hair, .3) \
                    or col == fk._lite(hair, .4):
                for x, y in cells:
                    if (x, y) in hair_px_:
                        c.p(x, y, R[3])
                continue
            if col == fk._dark(hair, .35) or col == fk._dark(hair, .3):
                for x, y in cells:
                    if (x, y) in hair_px_:
                        c.p(x, y, R[1])
                continue
        out = cmap.get(col, col)
        for x, y in cells:
            if 0 <= x < SIZE and 0 <= y < SIZE:
                c.p(x, y, out)
                if col in (skin, shade2d, light2d):
                    face.add((x, y))
                    hair_px_.discard((x, y))
                if col == hair:
                    hair_px_.add((x, y))
    # drop stray single hair pixels (sub-pixel tips that survived sampling)
    for x, y in sorted(hair_px_):
        if not any((x + ax, y + ay) in hair_px_ for ax, ay in ((1, 0), (-1, 0), (0, 1))):
            c.s.set_at((x, y), (0, 0, 0, 0))
            hair_px_.discard((x, y))
    # hair volume: shade the far side and the under-edge, sheen on the crown,
    # clump breaks along the hairline so the mass reads as hair, not a cap
    for x, y in hair_px_:
        if (x, y + 1) in face and (x, y + 1) not in hair_px_ and x % 3 == 1 \
                and tuple(c.get(x, y))[:3] == R[2]:
            c.p(x, y, R[1])
    for x, y in hair_px_:
        if (x + 1, y) not in hair_px_ or (x, y + 1) not in hair_px_ and (x, y + 1) in face:
            if tuple(c.get(x, y))[:3] == R[2]:
                c.p(x, y, R[1])
        if (x, y - 1) not in hair_px_ and x <= 11 and tuple(c.get(x, y))[:3] == R[2]:
            c.p(x, y, R[3])
    for x, y in face:                             # hairline shadow on the skin
        if (x, y - 1) in hair_px_ and (x, y) not in hair_px_:
            c.p(x, y, mix(tuple(c.get(x, y))[:3], S[0], .35))
    face -= hair_px_
    return S, face


def features_2d(c, spec, S, face, dy=0):
    """Lids, eyes, nose, creases, mouth, stubble, scar, cig, rim - each at its
    2D face coordinate, drawn as the pixel cluster that reads at 24 px."""
    fk = _figure_kit()
    skin, hair, hs = tuple(spec["skin"]), spec["hair"], spec.get("hair_style")

    def put(x, y, col, only_face=True):
        cx_, cy_ = fpx(x, y, dy)
        if not only_face or (cx_, cy_) in face:
            c.p(cx_, cy_, col)

    def tone(x, y, col, t):
        cx_, cy_ = fpx(x, y, dy)
        if (cx_, cy_) in face:
            c.p(cx_, cy_, mix(tuple(c.get(cx_, cy_))[:3], col, t))

    bw = spec.get("brow", 2)
    bc = fk._dark(hair, .1) if hs != "bald_white" else (190, 190, 185)
    lid = fk._mix(skin, (30, 15, 15), .65)
    sclera = (219, 203, 173)
    # brows: 2D y -10 (one row above the lid), weight from ``brow``
    for x0 in (-19, 7):
        for i, x in enumerate(range(x0, x0 + 12, 5)):
            outer = (i == 0 and x0 < 0) or (i == 2 and x0 > 0)
            if bw >= 3 or not outer:
                put(x, -12, bc if not outer else mix(bc, S[2], .35))
    if bw >= 4:
        put(-8, -12, fk._dark(bc, .3))
        put(7, -12, fk._dark(bc, .3))
    # eyes: heavy upper lid across the eye, sclera + iris under it (2D y -4 / -3)
    for ex in (-13, 13):
        for dx in (-5, 0, 5):
            put(ex + dx, -7, lid)
        put(ex - 5, -2, mix(sclera, skin, .45))
        put(ex, -2, sclera)
        put(ex + 5, -2, mix(sclera, skin, .2))
        put(ex + 2, -2, spec["iris"])            # looking toward frame right, as in the cutscenes
    # under-eye fatigue + nose (lit bridge, shadow, nostril) + cheek crease
    for x in (-15, -10):
        tone(x, 3, (90, 40, 50), .25)
    for x in (10, 16):
        tone(x, 3, (60, 30, 40), .3)
    put(-1, 0, S[3])
    put(-2, 5, S[3])
    put(3, 0, mix(S[1], S[2], .4))
    put(3, 5, S[1])
    put(1, 10, fk._mix(skin, (60, 30, 30), .5))
    put(6, 10, mix(S[1], S[0], .5))
    tone(-9, 17, (70, 30, 40), .4)
    # mouth (2D y 21-22) and lower-lip light
    if not spec.get("beard"):
        for x in (-9, -4, 1, 6):
            put(x, 21, fk._mix(skin, (40, 20, 25), .6))
        put(11, 22, fk._mix(skin, (40, 20, 25), .4))
        tone(0, 27, (255, 240, 220), .18)
    else:
        for x in (-6, 0, 6):
            put(x, 23, fk._dark(tuple(spec["beard"]), .45), False)
    if spec.get("stubble"):
        sc = fk._mix(skin, (12, 10, 10), .55)
        for sx, sy in fk._STUBBLE:
            tone(sx, sy, sc, .4)
    if spec.get("scar"):
        for x, y in ((-15, -24), (-12, -17), (-9, -12), (-6, -3), (-4, 6)):
            put(x, y, fk._lite(skin, .32))
        for x, y in ((-11, -24), (-8, -17), (-5, -8)):
            put(x, y, fk._dark(skin, .35))
    if spec.get("cig"):
        cx_, cy_ = fpx(11, 22, dy)
        c.p(cx_, cy_, (196, 140, 80))
        c.p(cx_ + 1, cy_, (232, 230, 222))
        c.p(cx_ + 2, cy_ + 1, (232, 230, 222))
        c.p(cx_ + 3, cy_ + 1, (255, 96, 30))
        c.p(cx_ + 3, cy_, (255, 170, 90))
    # rim light: the 2D rim stroke down the shaded cheek, kept soft
    rim = tuple(spec.get("rim", (137, 168, 191) if not spec.get("president") else (248, 202, 128)))
    for x, y in _line_cells([(23, -15), (24, 9), (17, 24)], dy):
        row = [p_ for p_ in face if p_[1] == y]
        if row and not spec.get("scarf"):
            xm = max(p_[0] for p_ in row)
            c.p(xm, y, mix(tuple(c.get(xm, y))[:3], rim, .2))


def bust(c, spec):
    """Shoulders + tailoring at portrait scale, key light from the left."""
    coat = spec["coat"]
    R = P.ramp(coat, contrast=1.2)
    R[2] = tuple(coat)
    wide = 1 if spec.get("bulk", 1) >= 1.08 else 0
    kid = spec.get("kid")
    rows = {18: (6, 17), 19: (4 - wide, 19 + wide), 20: (3 - wide, 20 + wide)}
    for y in range(21, SIZE):
        rows[y] = (2 - wide, 21 + wide)
    if kid:
        rows = {y: (x0 + 2, x1 - 2) for y, (x0, x1) in rows.items()}
    for y, (x0, x1) in rows.items():
        c.span(y, x0, x1, coat)
        c.span(y, x0, x0 + 1, R[3])
        c.span(y, x1 - 1, x1, R[1])
        c.p(x1, y, R[0])
    c.span(18, rows[18][0] + 1, rows[18][1] - 2, R[3])                 # shoulder ridge
    c.span(19, rows[19][0] + 1, rows[19][0] + 3, R[4])
    for y in range(21, SIZE):                                          # sleeve seams
        c.p(rows[y][0] + 2, y, R[1])
        c.p(rows[y][1] - 3, y, R[0])
    hood = spec.get("neck") == "hood"
    if hood:                                                          # hood bunched behind the neck
        hc = lite(coat, .12)
        c.span(17, 8, 15, hc)
        c.span(18, 7, 16, hc)
        c.p(8, 17, lite(coat, .25))
        c.r(10, 18, 4, 1, dark(coat, .25))
        st = spec.get("strings")
        if st:
            for x in (10, 13):
                c.r(x, 19, 1, 3, st)
                c.p(x, 21, lite(st, .3))
    else:
        lapel, shirt = spec.get("lapel", dark(coat, .25)), spec.get("shirt", coat)
        c.p(9, 17, lapel)                                             # collar hugging the neck
        c.p(14, 17, dark(lapel, .2))
        for y in range(18, SIZE):
            half = max(0, 2 - (y - 18) // 2)
            x0, x1 = 12 - half - 1, 11 + half + 1
            if y >= 22 and not spec.get("tie"):
                x0, x1 = 11, 12
            c.span(y, x0, x1, shirt)
            c.p(x0, y, dark(shirt, .2) if y == 18 else shirt)
            c.p(x0 - 1, y, lite(lapel, .15))
            c.p(x1 + 1, y, dark(lapel, .15))
            if spec.get("long_coat") and y <= 19:                     # collar stands up
                c.p(x0 - 2, y - 1, lapel)
                c.p(x1 + 2, y - 1, dark(lapel, .2))
        if spec.get("vest"):
            v = spec["vest"]
            for y in range(20, SIZE):
                c.span(y, 7, 9, v)
                c.span(y, 14, 16, dark(v, .15))
            c.span(20, 7, 9, lite(v, .2))
        if spec.get("tie"):
            t = spec["tie"]
            c.r(11, 18, 2, 1, dark(t, .2))
            c.r(11, 19, 2, SIZE - 19, t)
            c.p(11, 19, lite(t, .25))
            c.p(12, 21, dark(t, .25))
    if spec.get("epaulets"):
        e = spec["epaulets"]
        c.span(19, rows[19][0] + 1, rows[19][0] + 3, lite(e, .2))
        c.span(19, rows[19][1] - 3, rows[19][1] - 1, dark(e, .2))
    if spec.get("buttons") and not hood:
        for y in (21, 23):
            c.p(14, y, spec["buttons"])
    if spec.get("medal"):
        c.p(7, 21, spec["medal"])
        c.p(7, 22, lite(spec["medal"], .3))
    if spec.get("patch"):
        c.r(16, 21, 2, 2, spec["patch"])
        c.p(16, 21, lite(spec["patch"], .3))
    straps = spec.get("straps")
    if straps:
        for y in range(19, SIZE):
            c.p(6, y, straps)
            c.p(17, y, straps)
    # Keep the small chest identifiers that make the shared 2D/3D cast
    # recognisable at radio scale. At 24 px a sparse, high-contrast mark
    # reads better than a miniature texture.
    plaid = spec.get("plaid")
    if plaid and not hood:
        for y in (20, 22):
            c.p(7, y, plaid)
            c.p(16, y, plaid)
        for x in (8, 15):
            c.p(x, 21, plaid)
    print_spec = spec.get("print")
    if print_spec and not hood:
        kind, col = print_spec
        if kind == "stripe":
            c.span(21, 8, 15, col)
            c.span(22, 9, 14, dark(col, .18))
        elif kind == "drip":
            c.span(21, 8, 15, col)
            for x, ln in ((9, 2), (11, 3), (13, 2), (15, 1)):
                c.r(x, 22, 1, ln, col)
    armband = spec.get("armband")
    if armband:
        c.span(22, rows[22][0], rows[22][0] + 2, armband)
        c.span(22, rows[22][1] - 2, rows[22][1], armband)
    if spec.get("accent"):
        c.p(rows[20][0] + 2, 20, spec["accent"])
    rim = spec.get("rim", (137, 168, 191) if not spec.get("president") else (248, 202, 128))
    c.p(rows[19][1], 19, mix(rim, R[1], .5))                          # rim on the far shoulder
    c.p(rows[20][1], 20, mix(rim, R[1], .65))
    return c


def face_portrait(key):
    spec = portrait_spec(key)
    dy = 1 if spec.get("kid") else 0
    c = C()
    bust(c, spec)
    S, face = face_2d(c, spec, dy)
    features_2d(c, spec, S, face, dy)
    if spec.get("beanie") or spec.get("scarf"):   # portrait-only headgear (no 2D version)
        headgear_px(c, spec, dy)
    return finish(c)


FACES = ("biribel", "vasile", "volkov", "commander", "fisherman", "balaceanu", "president",
         "maru", "bodi", "alex", "ucilev", "krap_command", "ipa_dispatch", "old_squadmate",
         "gabi", "seby", "darius", "old_woman", "hungry_kid")


def unknown():
    """Generic caller: shadowed head with a headset - identity withheld."""
    spec = dict(skin=(78, 82, 88), hair=(40, 42, 46), hair_style="crop", coat=(54, 58, 62),
                lapel=(40, 43, 47), shirt=(44, 47, 51), jaw=1.0, brow=2, iris=(30, 32, 36),
                rim=(120, 140, 160))
    c = C()
    bust(c, spec)
    S, face = face_2d(c, spec)
    for ex in (-13, 13):                         # eyes lost in shadow
        for dx in (-5, 0, 5):
            for ey in (-7, -2):
                x, y = fpx(ex + dx, ey)
                c.p(x, y, (40, 42, 46))
    headset(c)
    return finish(c)

# -- insignia (no face) -------------------------------------------------------
def disc(c, col, rim):
    for y in range(2, 22):
        dy = y - 11.5
        half = int((100 - dy * dy) ** 0.5) if dy * dy < 100 else 0
        if half:
            c.span(y, 12 - half, 11 + half, col)
            c.p(12 - half, y, rim)
            c.p(11 + half, y, rim)
    c.span(2, 9, 14, rim)
    c.span(21, 9, 14, rim)


def narrator():
    """Ribbon microphone on a stand."""
    c = C()
    M = P.ramp((150, 150, 156))
    c.r(9, 3, 6, 11, M[2])
    c.r(9, 3, 2, 11, M[3])
    c.r(14, 3, 1, 11, M[1])
    for y in range(4, 13, 2):
        c.span(y, 10, 13, M[0])
    c.span(2, 10, 13, M[2])
    c.span(14, 10, 13, M[1])
    c.r(11, 15, 2, 5, M[1])
    c.span(20, 7, 16, M[2])
    c.span(21, 6, 17, M[1])
    c.p(6, 7, P.BRASS)
    c.p(17, 7, P.BRASS)
    return finish(c)


def pa_system():
    """Horn loudspeaker on a pole with sound arcs."""
    c = C()
    H = P.ramp((170, 170, 160))
    rows = {7: (4, 6), 8: (4, 8), 9: (4, 10), 10: (4, 12), 11: (4, 13), 12: (4, 13), 13: (4, 12),
            14: (4, 10), 15: (4, 8), 16: (4, 6)}
    for y, (x0, x1) in rows.items():
        c.span(y, x0, x1, H[2])
        c.p(x1, y, H[4])
        c.p(x0, y, H[1])
    c.r(2, 10, 2, 4, H[0])
    c.r(3, 17, 2, 7, H[0])
    for r, col in ((3, (230, 70, 70)), (6, (200, 60, 60))):
        for y in range(12 - r, 12 + r):
            c.p(15 + r - abs(y - 11) // 2, y, col)
    return finish(c)


def intercept():
    """Satellite dish + waveform: an eavesdropped transmission."""
    c = C()
    D = P.ramp((150, 170, 190))
    for y, (x0, x1) in {3: (5, 7), 4: (4, 9), 5: (4, 11), 6: (4, 12), 7: (5, 13), 8: (6, 13),
                        9: (7, 12), 10: (9, 11)}.items():
        c.span(y, x0, x1, D[2])
        c.p(x0, y, D[3])
    c.p(12, 4, D[4])
    c.p(13, 3, D[4])
    c.r(8, 11, 2, 5, D[1])
    c.span(16, 5, 12, D[1])
    wave = (2, 1, 0, 2, 4, 1, 3, 0, 2, 4, 1, 2)
    for i, h in enumerate(wave):
        x = 10 + i
        if x < 23:
            c.r(x, 19 - h, 1, 1 + h * 2, (110, 230, 140))
    return finish(c)


def radio_tower():
    """Lattice mast with broadcast rings."""
    c = C()
    T = P.ramp((150, 156, 166))
    for y in range(5, 22):
        w = (y - 5) // 3
        c.p(11 - w, y, T[2])
        c.p(12 + w, y, T[1])
        if y % 3 == 0:
            c.span(y, 11 - w, 12 + w, T[1])
    c.p(11, 4, (230, 60, 50))
    c.p(12, 4, (230, 60, 50))
    for r, col in ((4, (200, 220, 240)), (7, (140, 160, 190))):
        c.p(11 - r, 5, col)
        c.p(12 + r, 5, col)
        if r > 4:
            c.p(10 - r, 4, col)
            c.p(13 + r, 4, col)
        c.p(11 - r + 1, 3, col)
        c.p(12 + r - 1, 3, col)
    c.span(22, 6, 17, T[0])
    return finish(c)


def system():
    """Terminal: CRT monitor with a prompt."""
    c = C()
    B = P.ramp(P.CASE_BEIGE)
    c.r(3, 3, 18, 14, B[2])
    c.r(3, 3, 18, 1, B[3])
    c.r(20, 3, 1, 14, B[1])
    c.r(5, 5, 14, 10, P.CRT_GLASS)
    c.span(7, 7, 9, P.PHOSPHOR)
    c.span(9, 7, 13, P.PHOSPHOR)
    c.span(11, 7, 8, P.PHOSPHOR_HI)
    c.r(9, 11, 2, 1, P.PHOSPHOR_HI)
    c.r(9, 17, 6, 2, B[1])
    c.span(19, 5, 18, B[2])
    c.span(20, 4, 19, B[1])
    return finish(c)


def loyalist_comms():
    """Loyalist net: red shield with a white tower and two stars."""
    c = C()
    red = P.ramp((200, 70, 60))
    for y in range(3, 20):
        half = 8 if y < 13 else max(1, 8 - (y - 12))
        c.span(y, 12 - half, 11 + half, red[2])
        c.p(12 - half, y, red[3])
        c.p(11 + half, y, red[1])
    c.span(3, 4, 19, red[4])
    W = (230, 222, 200)
    c.r(10, 7, 4, 9, W)
    c.span(6, 9, 14, W)
    c.p(9, 5, W)
    c.p(11, 5, W)
    c.p(14, 5, W)
    c.p(11, 10, red[0])
    c.p(12, 10, red[0])
    for x in (6, 17):
        c.p(x, 9, P.GOLD_HI)
        c.p(x - 1, 9, P.BRASS)
        c.p(x + 1, 9, P.BRASS)
        c.p(x, 8, P.BRASS)
        c.p(x, 10, P.BRASS)
    return finish(c)


CAST = tuple((k, None) for k in FACES) + (
    ("unknown", unknown), ("narrator", narrator), ("pa_system", pa_system),
    ("intercept", intercept), ("radio", radio_tower), ("system", system),
    ("loyalist_comms", loyalist_comms),
)


def build():
    sh = kit.Sheet("spr_portraits", FAMILY)
    sh.meta = {"size": SIZE, "display_scale": 2,
               "note": "radio caller-ID busts; ui.radio maps speakers to keys"}
    for key, fn in CAST:
        img = fn() if fn else face_portrait(key)
        sh.add(key, img, (0, 0), kind="emblem" if fn in EMBLEMS else "face")
    return [sh]


EMBLEMS = (narrator, pa_system, intercept, radio_tower, system, loyalist_comms)


if __name__ == "__main__":
    sys.exit(kit.run(FAMILY, build))
