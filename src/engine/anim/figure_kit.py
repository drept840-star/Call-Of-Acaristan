"""figure_kit.py - one cast renderer in the "Balaceanu Arrest" house style.

Why this exists
---------------
``m4aftermath`` (the Balaceanu arrest) reads as drawn because its people are
built from *faces and tailoring*, not primitives: angular skull/jaw polygons
with a key-light plane and a rim line, brows/eyelids/nose/nasolabial creases,
lapels + collar + tie, articulated 2-bone limbs with a lit edge and shaded
plane, hands with cuffs, and a ground shadow. ``cast.draw_*`` and
``m3cell._m3_draw_balaceanu`` were circle-head + rectangle-limb sprites; this
kit replaces them so every cutscene that uses the cast inherits the arrest look
without touching the shot code.

Public API
----------
    draw_character(surface, who, cx, foot_y, scale=1.0, facing_right=True,
                   silhouette=False, t=0, fear=0, smile=0, blink=0,
                   look=None, moving=0, prop=None, prop_label=None,
                   label_font=None, *, seated=False, reach=None, bow=0,
                   wardrobe=None)

``who``: biribel | vasile | volkov | commander | fisherman | balaceanu |
         president | maru | bodi | alex | ucilev | ipa | krap | civilian.  The last three are the extras
         (IPA agents/guards/marksmen, KRAP squad members, street civilians)
         so crowds and enemies in cutscenes share the house style instead of
         circle-head primitives.  Figure heights match the legacy sprites (see HEIGHT),
so shot layouts do not move.  Coordinates are authored in "arrest units"
(foot at y=0, head centre at y=-258) and multiplied by ``k``; everything is
hard-edged 1x line art like the arrest (no smoothscale blur).

Staging options (keyword-only):
    seated    - hips drop onto a seat (front view, knees forward); the upper
                body, arms and head move down with them.
    reach     - ((dx, dy), (dx, dy)) wrist targets in *screen pixels*
                relative to (cx, foot_y), screen-left arm first.  Used for
                restrained wrists, grips and grabs; elbows are solved.
    bow       - 0..1, head drops and lids get heavy (restrained/defeated).
    arms      - False skips the default arms + hands (callers draw their own,
                e.g. the M4 armed poses).
    wardrobe  - dict of SPECS overrides (e.g. a prison jumpsuit) so the face
                and build stay the cast member's while the clothes change.
"""
import math

import pygame
from engine.core import now_ms as _now_ms  # RPE6 B-001 timebase

# RPE6 Phase 2 (A-006): moved verbatim from cutscenes/figure_kit.py except for the injection points marked RPE6.
__all__ = ["SPECS", "HEIGHT", "REF_H", "KRAP_UNIFORM", "KRAP_BLUE", "draw_character"]

# RPE6: the KRAP palette used to be read from core.config (C_KRAP_UNIFORM / C_KRAP_BLUE);
# the engine copy owns the values and tests/unit/test_engine_shims.py pins them to config.
KRAP_UNIFORM = _KRAP_UNI = (55, 65, 80)
KRAP_BLUE = _KRAP_BLUE = (35, 65, 110)

REF_H = _REF_H = 296.0  # arrest figure: foot (0) -> top of hair (-296)


# ── colour helpers ──────────────────────────────────────────────────────
def _mix(a, b, t):
    return tuple(max(0, min(255, round(a[i] + (b[i] - a[i]) * t))) for i in range(3))


def _dark(c, t=.3):
    return _mix(c, (4, 6, 10), t)


def _lite(c, t=.25):
    return _mix(c, (255, 244, 225), t)


# ── cast sheet ──────────────────────────────────────────────────────────
# height = pixel height of the legacy sprite at scale 1.0 so layouts hold.
SPECS = {
    "biribel": dict(
        height=254, bulk=1.0, skin=(190, 150, 116), hair=(25, 30, 28), hair_style="curly",
        stubble=True, jaw=.86, brow=3, iris=(35, 45, 55),
        coat=(40, 50, 45), lapel=(31, 38, 34), shirt=(96, 100, 92), tie=None,
        trousers=(30, 35, 40), shoes=(12, 12, 14), long_coat=False,
        vest=(28, 35, 30), patch=_KRAP_BLUE, belt=(14, 16, 18), glove=None),
    "vasile": dict(
        height=262, bulk=1.04, skin=(184, 150, 122), hair=(62, 52, 46), hair_style="crop",
        stubble=False, jaw=1.0, brow=2, iris=(40, 50, 70), cig=True,
        coat=_KRAP_UNI, lapel=_dark(_KRAP_UNI, .25), shirt=(190, 190, 180), tie=_KRAP_BLUE,
        trousers=(35, 42, 55), shoes=(15, 15, 18), long_coat=False,
        buttons=(200, 180, 80), epaulets=(200, 180, 80), belt=(14, 18, 26), glove=None),
    "volkov": dict(
        height=264, bulk=1.05, skin=(120, 92, 78), hair=(10, 8, 9), hair_style="slick",
        stubble=True, jaw=.95, brow=4, iris=(190, 62, 42), cig=True, scar=True,
        coat=(20, 20, 28), lapel=(11, 11, 17), shirt=(60, 56, 58), tie=None,
        trousers=(18, 18, 24), shoes=(12, 10, 10), long_coat=True,
        rim=(255, 130, 60), belt=None, glove=(10, 10, 14)),
    "commander": dict(
        height=270, bulk=1.1, skin=(178, 144, 118), hair=(15, 12, 10), hair_style="crop",
        stubble=False, jaw=1.05, brow=4, iris=(25, 30, 35), cap=True,
        coat=(36, 38, 46), lapel=(24, 26, 33), shirt=(200, 192, 176), tie=(140, 20, 20),
        trousers=(20, 22, 28), shoes=(10, 10, 12), long_coat=False,
        buttons=(190, 160, 90), epaulets=(190, 160, 90), medal=(160, 30, 30),
        belt=(12, 14, 20), glove=None),
    "fisherman": dict(
        height=227, bulk=1.02, skin=(168, 134, 108), hair=(206, 206, 198), hair_style="bald_white",
        stubble=False, beard=(205, 205, 198), jaw=1.0, brow=2, iris=(40, 34, 30), hat=(60, 55, 45),
        coat=(90, 80, 50), lapel=(70, 62, 40), shirt=(150, 140, 120), tie=None,
        trousers=(50, 45, 38), shoes=(25, 20, 16), long_coat=True, belt=None,
        glove=None, stoop=6),
    "balaceanu": dict(
        height=276, bulk=1.0, skin=(198, 154, 115), hair=(40, 29, 29), hair_style="swept",
        stubble=False, jaw=1.0, brow=2, iris=(22, 25, 28),
        coat=(49, 38, 37), lapel=(98, 73, 65), shirt=(217, 203, 178), tie=(135, 31, 28),
        trousers=(19, 23, 33), shoes=(8, 10, 17), long_coat=False,
        buttons=(156, 113, 74), belt=None, glove=None, medal=(156, 113, 74)),
    "president": dict(
        height=296, bulk=1.0, skin=(207, 168, 127), hair=(40, 29, 29), hair_style="swept",
        stubble=False, jaw=1.0, brow=2, iris=(22, 25, 28), president=True,
        coat=(31, 40, 61), lapel=(80, 81, 90), shirt=(217, 203, 178), tie=(174, 40, 42),
        trousers=(19, 23, 33), shoes=(8, 10, 17), long_coat=False,
        buttons=(230, 200, 120), belt=None, glove=None, medal=(230, 200, 120)),
    # Maru (MAG): messy brown hair with a swept fringe, fair skin, heavier
    # build; plain black hoodie, backpack straps, dark trousers, no glasses.
    "maru": dict(
        height=244, bulk=1.04, skin=(224, 188, 162), hair=(96, 64, 40), hair_style="shag",
        stubble=False, jaw=1.04, brow=2, iris=(62, 46, 34),
        coat=(26, 28, 34), lapel=(18, 19, 24), shirt=(18, 19, 24), tie=None,
        trousers=(24, 25, 30), shoes=(34, 34, 38), sole=(150, 150, 146), long_coat=False,
        neck="hood", strings=(70, 72, 80), straps=(12, 12, 14), pack=(20, 21, 26),
        cuff_col=(20, 22, 27), belt=None, glove=None),
    # Bodi (farmer, M7-M8): straight dark hair with a full fringe, slim; open
    # work flannel over a black tee with a green drip print, jeans, rubber boots.
    "bodi": dict(
        height=250, bulk=.92, skin=(228, 192, 168), hair=(32, 25, 22), hair_style="fringe",
        stubble=False, jaw=.96, brow=3, iris=(56, 40, 30),
        coat=(104, 64, 44), lapel=(80, 48, 34), shirt=(20, 20, 22), tie=None,
        trousers=(60, 72, 96), shoes=(40, 54, 38), boots_h=.62, long_coat=False,
        neck="open", inner=(20, 20, 22), print=("drip", (74, 188, 72)), plaid=(62, 36, 26),
        cuff_col=(84, 50, 34), belt=None, glove=None),
    # Alex (MAG runner, M8 mansion ally): short spiky brown hair, tan skin;
    # bright blue sports hoodie with a red chest band, black belt, ripped jeans.
    "alex": dict(
        height=236, bulk=.95, skin=(198, 150, 112), hair=(84, 56, 34), hair_style="spiky",
        stubble=False, jaw=.94, brow=2, iris=(52, 36, 26),
        coat=(34, 64, 176), lapel=(26, 48, 140), shirt=(26, 48, 140), tie=None,
        trousers=(54, 88, 156), shoes=(214, 214, 208), sole=(150, 40, 40), rips=(176, 196, 224),
        long_coat=False, neck="hood", hem=-112, strings=(220, 222, 230),
        print=("stripe", (220, 72, 84)), cuff_col=(28, 54, 150),
        belt=(14, 14, 16), glove=None),
    # Ucilev Nadgob Ierdna (M5-M7): Presidential Guard black + red armband,
    # thick curly mop with a fringe, heavy brows, round face.
    "ucilev": dict(
        height=266, bulk=1.08, skin=(214, 172, 146), hair=(22, 18, 16), hair_style="mop",
        stubble=False, jaw=1.08, brow=5, iris=(58, 36, 24),
        coat=(24, 25, 29), lapel=(16, 17, 20), shirt=(62, 62, 68), tie=None,
        trousers=(28, 29, 33), shoes=(10, 10, 11), long_coat=False,
        vest=(36, 37, 42), armband=(180, 40, 40), belt=(12, 12, 14), glove=(18, 18, 20)),
    # ── extras (m4aftermath._guard palette for the IPA) ──
    "ipa": dict(
        height=262, bulk=1.06, skin=(186, 146, 112), hair=(30, 24, 22), hair_style="crop",
        stubble=False, jaw=1.02, brow=3, iris=(24, 28, 32), cap=True,
        coat=(27, 40, 58), lapel=(19, 29, 46), shirt=(91, 102, 110), tie=(19, 29, 46),
        trousers=(16, 25, 39), shoes=(7, 11, 18), long_coat=False,
        buttons=(174, 155, 106), belt=(12, 18, 28), glove=(25, 30, 34)),
    "krap": dict(
        height=258, bulk=1.04, skin=(176, 140, 112), hair=(34, 28, 24), hair_style="crop",
        stubble=True, jaw=.98, brow=3, iris=(38, 44, 52),
        # darker field tunic so Krap no longer reads as a Vasile clone
        coat=(40, 48, 40), lapel=(28, 34, 28), shirt=(120, 116, 100), tie=None,
        trousers=(35, 42, 55), shoes=(14, 14, 16), long_coat=False,
        patch=_KRAP_BLUE, belt=(14, 18, 26), glove=(24, 26, 28)),
    "civilian": dict(
        height=244, bulk=.98, skin=(172, 138, 112), hair=(46, 38, 32), hair_style="crop",
        stubble=True, jaw=.96, brow=2, iris=(40, 36, 32),
        coat=(64, 58, 48), lapel=(50, 45, 38), shirt=(130, 122, 104), tie=None,
        trousers=(44, 40, 36), shoes=(22, 18, 16), long_coat=True, belt=None,
        glove=None),
}
HEIGHT = {k: v["height"] for k, v in SPECS.items()}


class _Pen:
    """Maps arrest-unit coordinates to the surface (scale + mirror + origin).
    Light stays on the figure's left whichever way it faces (``light=True``
    skips the mirror), so mirrored actors keep one consistent key light."""

    def __init__(self, surf, cx, foot, k, facing_right):
        self.s, self.cx, self.fy, self.k = surf, cx, foot, k
        self.f = 1 if facing_right else -1
        self.ox = self.oy = 0.0

    def p(self, x, y, light=False):
        f = 1 if light else self.f
        return (round(self.cx + (x + self.ox) * self.k * f),
                round(self.fy + (y + self.oy) * self.k))

    def w(self, v):
        return max(1, round(v * self.k))

    def poly(self, col, pts, light=False):
        pygame.draw.polygon(self.s, col, [self.p(x, y, light) for x, y in pts])

    def line(self, col, pts, width=1, light=False):
        pygame.draw.lines(self.s, col, False, [self.p(x, y, light) for x, y in pts], self.w(width))

    def ell(self, col, x0, y0, x1, y1, width=0):
        a, b = self.p(x0, y0), self.p(x1, y1)
        r = pygame.Rect(min(a[0], b[0]), min(a[1], b[1]), max(1, abs(b[0] - a[0])), max(1, abs(b[1] - a[1])))
        pygame.draw.ellipse(self.s, col, r, width)

    def circ(self, col, x, y, r, width=0):
        pygame.draw.circle(self.s, col, self.p(x, y), self.w(r), width)


# ── face ────────────────────────────────────────────────────────────────
_STUBBLE = [(-15, 20), (-9, 25), (-3, 28), (4, 29), (10, 26), (15, 21), (-19, 14), (19, 15),
            (-12, 17), (-6, 20), (0, 24), (6, 23), (12, 18), (-17, 24), (16, 25), (-1, 31)]


def _face(pen, spec, hx, hy, *, fear=0, smile=0, look=0, blink=0, cig=True):
    """Angular face with key/rim light (port of m4aftermath._face)."""
    pen.ox, pen.oy = hx, hy
    skin = spec["skin"]
    shade, light = _mix(skin, (60, 30, 30), .38), _lite(skin, .22)
    jaw = spec.get("jaw", 1.0)
    lo = lambda x: x * jaw
    P = pen.poly
    L = pen.line
    P(_mix(skin, (40, 20, 20), .5), [(-12, 26), (12, 26), (14, 43), (-14, 43)])          # neck
    outline = [(-26, -18), (-20, -31), (-5, -36), (17, -31), (26, -20), (25, 12),
               (lo(18), 27 + fear * 2), (lo(4), 34 + fear * 2), (lo(-15), 28), (lo(-25), 9)]
    P(skin, outline)
    P(shade, [(8, -31), (26, -20), (25, 12), (lo(18), 27), (lo(4), 34), (8, 15), (14, 2)], light=True)
    P(light, [(-24, -17), (-15, -27), (-12, -5), (-20, 10), (-24, 8)], light=True)
    # hair
    hair, hs = spec["hair"], spec["hair_style"]
    if hs == "swept":
        P(hair, [(-26, -5), (-29, -23), (-19, -34), (-5, -38), (17, -33), (26, -23), (26, -8),
                 (20, -21), (10, -26), (-2, -29), (-18, -22), (-20, -5)])
        L(_lite(hair, .45), [(-23, -27), (-13, -33), (3, -33)], 2)
    elif hs in ("crop", "curly"):
        P(hair, [(-26, -2), (-28, -23), (-19, -34), (-5, -38), (17, -33), (27, -23), (26, -2),
                 (22, -14), (12, -22), (-2, -23), (-16, -20), (-22, -8)])
        if hs == "curly":
            for k_, ox in enumerate((-20, -13, -6, 1, 8, 15, 22)):
                pen.circ(hair, ox, -31 + (k_ % 2) * 3 + abs(ox) * .18, 5.5)
            for ox in (-17, -4, 9):
                pen.line(_lite(hair, .35), [(ox - 3, -34), (ox + 1, -36)], 1)
        else:
            L(_lite(hair, .35), [(-18, -33), (-3, -37), (12, -34)], 2)
    elif hs == "mop":
        # thick, uneven curly mop: crop base, a ring of curls, fringe over the brow
        P(hair, [(-27, -4), (-30, -24), (-20, -37), (-5, -41), (18, -36), (29, -24), (27, -4),
                 (22, -16), (12, -22), (-2, -23), (-16, -20), (-22, -8)])
        for k_, (ox, oy, rr) in enumerate(((-24, -30, 6.5), (-16, -38, 7), (-6, -42, 7.5), (5, -41, 7),
                                           (15, -38, 7), (24, -31, 6.5), (28, -20, 5.5), (-28, -18, 5.5))):
            pen.circ(hair, ox, oy, rr)
        for fx, fl, tilt in ((-18, 12, -3), (-9, 16, 2), (1, 14, -2), (11, 15, 3), (19, 10, 1)):
            P(hair, [(fx - 5, -24), (fx + 5, -24), (fx + 2 + tilt, -24 + fl), (fx - 2 + tilt, -24 + fl - 2)])
        for ox in (-15, -2, 11):
            pen.line(_lite(hair, .3), [(ox - 3, -38), (ox + 2, -40)], 1)
    elif hs == "shag":
        # Maru: thick, messy brown hair with a heavy fringe swept to one side
        P(hair, [(-27, 0), (-30, -22), (-23, -38), (-7, -45), (11, -44), (25, -35), (30, -20),
                 (28, -2), (24, -12), (16, -22), (0, -24), (-16, -20), (-22, -8)])
        for x0, x1, tip in ((-24, -12, (-20, -11)), (-15, -2, (-8, -13)), (-5, 8, (4, -15)),
                            (5, 18, (16, -16)), (14, 27, (25, -12))):
            P(hair, [(x0, -26), (x1, -27), tip])
        for ox, oy in ((-24, -36), (-10, -45), (6, -46), (21, -40)):
            P(hair, [(ox - 6, oy + 4), (ox, oy - 4), (ox + 7, oy + 3)])
        hl = _lite(hair, .35)
        L(hl, [(-20, -35), (-6, -41), (10, -40)], 2)
        L(hl, [(-11, -24), (-4, -16)], 1)
        L(hl, [(8, -25), (15, -18)], 1)
        L(_dark(hair, .35), [(-2, -25), (3, -16)], 1)
    elif hs == "fringe":
        # Bodi: straight, dense dark hair, full fringe cut just above the brows
        P(hair, [(-27, -1), (-29, -24), (-20, -37), (-4, -41), (15, -38), (27, -27), (28, -1),
                 (24, -6), (23, -16), (14, -15), (4, -14), (-6, -15), (-16, -14), (-23, -12), (-24, -4)])
        for fx in (-17, -7, 3, 13):
            P(hair, [(fx - 4, -16), (fx + 5, -16), (fx + 1, -11)])
        L(_lite(hair, .3), [(-19, -32), (-4, -37), (13, -34)], 2)
        L(_dark(hair, .3), [(-12, -26), (-10, -16)], 1)
        L(_dark(hair, .3), [(6, -27), (8, -16)], 1)
    elif hs == "spiky":
        # Alex: short textured cut, tips pushed up and forward
        P(hair, [(-26, -4), (-28, -23), (-19, -34), (-5, -38), (17, -34), (27, -23), (26, -4),
                 (22, -16), (12, -22), (-2, -24), (-16, -21), (-22, -9)])
        for k_, ox in enumerate((-22, -14, -6, 2, 10, 18, 24)):
            h_ = 9 + (k_ % 3) * 3
            P(hair, [(ox - 5, -31 + abs(ox) * .12), (ox + 1 + k_ % 2 * 2, -31 - h_ + abs(ox) * .2),
                     (ox + 5, -31 + abs(ox) * .12)])
        for fx in (-12, -2, 8):
            P(hair, [(fx - 5, -24), (fx + 6, -26), (fx + 3, -18)])
        L(_lite(hair, .4), [(-16, -36), (-4, -41), (10, -38)], 1)
    elif hs == "slick":
        P(hair, [(-26, -2), (-29, -24), (-19, -35), (-4, -39), (18, -34), (27, -23), (26, -4),
                 (21, -20), (8, -27), (-4, -27), (-18, -20), (-22, -2)])
        L(_lite(hair, .3), [(-20, -30), (-6, -35), (10, -33)], 1)
    elif hs == "bald_white":
        for sgn in (-1, 1):
            P(hair, [(sgn * 26, -6), (sgn * 28, -16), (sgn * 22, -22), (sgn * 20, -8), (sgn * 23, 6)])
        L(_lite(skin, .3), [(-12, -30), (0, -34), (12, -30)], 2)
    # ears, under-eye fatigue, nasolabial crease
    pen.ell(_mix(skin, (150, 70, 60), .35), -31, -3, -23, 13)
    L(_dark(skin, .5), [(-26, 1), (-25, 9)], 1)
    L(_mix(skin, (90, 40, 50), .3), [(-17, 6), (-7, 7)], 1)
    L(_mix(skin, (60, 30, 40), .45), [(9, 6), (18, 5)], 1)
    # brows (weight = brow), eyes
    bw = spec.get("brow", 2)
    bc = _dark(hair, .1) if hs != "bald_white" else (190, 190, 185)
    L(bc, [(-19, -10), (-8, -10 - fear * 5)], bw)
    L(bc, [(7, -10 - fear * 4), (18, -9 + smile * 2)], bw)
    eye_h = max(0.4, (3 + fear * 2) * (1 - blink))
    for x in (-13, 13):
        P((219, 203, 173), [(x - 5, -3), (x, -3 - eye_h), (x + 5, -3), (x, -2 + eye_h)])
        pen.circ(spec["iris"], x + look * 2, -3, 1.8)
        L(_mix(skin, (30, 15, 15), .65), [(x - 5, -4), (x + 5, -4)], 1)
    if spec.get("scar"):
        L(_lite(skin, .15), [(-15, -27), (-9, -12), (-4, 6)], 1)
        L(_dark(skin, .35), [(-14, -27), (-8, -12), (-3, 6)], 1)
    # nose, brow ridge highlight, cheek line
    L(_mix(skin, (60, 30, 30), .5), [(1, -6), (-2, 9), (5, 11)], 1.4)
    L(_lite(skin, .3), [(-2, -5), (-4, 6)], 1)
    L(_mix(skin, (70, 30, 40), .45), [(-7, 14), (-11, 22)], 1)
    if spec.get("stubble"):
        sc = _mix(skin, (12, 10, 10), .55)
        for sx, sy in _STUBBLE:
            pygame.draw.rect(pen.s, sc, (*pen.p(sx, sy), pen.w(1.6), pen.w(1.6)))
    if spec.get("beard"):
        P(spec["beard"], [(-24, 6), (-26, 18), (-14, 34), (0, 41), (14, 34), (25, 18), (24, 6),
                          (16, 17), (0, 21), (-16, 17)])
        L(_dark(spec["beard"], .4), [(-10, 25), (0, 26 + fear * 3), (11, 25)], 1)
    else:
        L(_mix(skin, (40, 20, 25), .6), [(-10, 22), (0, 21 + fear * 3), (11, 22 - smile * 4)], 1.6)
        if fear > .5:
            L(_mix(skin, (40, 20, 25), .55), [(-3, 24), (5, 24)], 1)
        L(_mix(skin, (90, 50, 40), .3), [(-5, 28), (5, 28)], 1)
    if cig and spec.get("cig"):
        # tucked into the mouth corner, drooping (was flat and pointing up)
        L(_mix(skin, (60, 20, 20), .5), [(8, 21), (11, 23)], 2.2)          # lip pinch
        L((196, 140, 80), [(10, 22.5), (13.5, 23.6)], 2)                    # filter
        L((232, 230, 222), [(13.5, 23.6), (23, 26.6)], 2)                   # paper
        L((120, 114, 108), [(23, 26.6), (24.6, 27.1)], 2)                   # ash
        pen.circ((255, 96, 30) if int(_now_ms() / 350) % 2 == 0 else (150, 50, 25), 25.4, 27.3, 1.5)
    rim = spec.get("rim", (137, 168, 191) if not spec.get("president") else (248, 202, 128))
    L(rim, [(23, -15), (24, 9), (17, 24)], 1, light=True)
    if fear > .65:
        L((184, 193, 189), [(-22, -13), (-23, -6)], 1)
    if spec.get("glasses"):
        gc = spec["glasses"]
        for x in (-13, 13):
            pen.circ(gc, x, -3, 7, 1)
            L((205, 214, 208), [(x - 3, -6), (x - 1, -7)], 1)
        L(gc, [(-6, -4), (6, -4)], 1)
    # headgear last so it sits over the hairline
    if spec.get("bandana"):
        bc = spec["bandana"]
        P(bc, [(-28, -10), (-29, -26), (-19, -37), (-4, -40), (17, -36), (28, -26), (28, -10),
               (16, -16), (0, -18), (-16, -16)])
        L(_lite(bc, .3), [(-24, -27), (-8, -35), (10, -33)], 2)
        L(_dark(bc, .35), [(-28, -11), (-16, -17), (0, -19), (16, -17), (28, -11)], 1)
        P(_dark(bc, .15), [(26, -20), (36, -14), (34, -4), (29, -12)])          # knot tails
        P(_dark(bc, .25), [(27, -16), (40, -6), (37, 2), (30, -8)])
    if spec.get("cap"):
        P((19, 29, 46), [(-29, -22), (-23, -44), (23, -44), (29, -22)])
        L((129, 133, 126), [(-28, -22), (29, -22)], 2)
        P((12, 14, 20), [(-27, -22), (31, -22), (30, -16), (-27, -16)])
        pen.circ((190, 160, 90), 0, -33, 3)
    if spec.get("hat"):
        P(spec["hat"], [(-30, -24), (-26, -40), (26, -40), (30, -24)])
        P(_dark(spec["hat"], .35), [(-33, -23), (33, -23), (31, -18), (-33, -18)])
    pen.ox = pen.oy = 0.0


# ── body ────────────────────────────────────────────────────────────────
def _hand(pen, skin, glove, x, y, dirx):
    col = glove or skin
    pen.ell(col, x - 6, y - 3, x + 6, y + 13)
    pen.line(_dark(col, .25), [(x + dirx * 5, y), (x + dirx * 7, y + 8)], 2)  # thumb side
    pen.line(_lite(col, .2), [(x - dirx * 3, y + 1), (x - dirx * 4, y + 10)], 1)


_SEAT_DROP = 55  # seated: hips fall from y=-104 to y=-49 (arrest units)


def _reach_units(pen, reach):
    """Screen-pixel wrist offsets -> arrest units keyed by arrest-space side."""
    if not reach:
        return {}
    out = {}
    for dx, dy in reach:
        x = dx * pen.f / pen.k
        y = dy / pen.k - pen.oy
        out[1 if x >= 0 else -1] = (x, y)
    return out


def _torso_x(X, hy, y, hem, flare, side):
    """Torso edge at height y (the coat trapezoid, shoulder -> hem)."""
    y0, y1 = hy + 46, hem
    f = 0.0 if y1 == y0 else max(0.0, min(1.0, (y - y0) / (y1 - y0)))
    return side * X(47 + (37 + flare - 47) * f)


def _print(pen, spec, X, hy, half):
    """Chest graphic. ``half`` = usable half-width (arrest units)."""
    pr = spec.get("print")
    if not pr:
        return
    kind, col = pr[0], pr[1]
    if kind == "drip":   # dripping horror-font band (Bodi's tee)
        y0 = hy + 74
        w = half
        pen.poly(col, [(-w, y0), (w, y0 - 3), (w, y0 + 9), (-w, y0 + 11)])
        for i, (dx, ln) in enumerate(((-.85, 9), (-.55, 17), (-.3, 7), (-.05, 22), (.2, 10),
                                      (.45, 19), (.72, 8), (.9, 13))):
            x = dx * w
            pen.poly(col, [(x - 2.4, y0 + 8), (x + 2.4, y0 + 8), (x + 1.5, y0 + 8 + ln), (x - 1.5, y0 + 8 + ln)])
            pen.circ(col, x, y0 + 9 + ln, 2.2)
        dk = _dark(col, .55)
        for gx in (-.7, -.35, 0, .35, .7):
            pen.line(dk, [(gx * w - 2, y0 + 2), (gx * w + 2, y0 + 7)], 1)
    elif kind == "stripe":  # sports-hoodie chest wordmark: small 3-bar mark + red band
        white = pr[2] if len(pr) > 2 else (236, 236, 232)
        y0 = hy + 100
        for i in range(3):
            x = -5 + i * 3.6
            pen.poly(white, [(x, y0 - 4 - i * 2), (x + 2.4, y0 - 4 - i * 2), (x + 2.4, y0 - 1), (x, y0 - 1)])
        pen.poly(col, [(-half, y0 + 3), (half, y0 + 3), (half, y0 + 13), (-half, y0 + 13)])
        pen.line(_lite(col, .35), [(-half, y0 + 4), (half, y0 + 4)], 1)
        for i in range(6):
            x = -half + 4 + i * (2 * half - 8) / 5.0
            pen.line(_dark(col, .45), [(x, y0 + 5), (x, y0 + 11)], 1)
        pen.line(white, [(-half * .7, y0 + 18), (half * .7, y0 + 18)], 2)


def _casual_front(pen, spec, X, hy, top, hem, flare):
    """Hoodie / tee / open shirt chest, drawn over the coat trapezoid."""
    coat = spec["coat"]
    neck = spec["neck"]
    if spec.get("plaid"):              # flannel check: clip the lines to the trapezoid
        pc = spec["plaid"]
        y = hy + 56
        while y < hem - 4:
            pen.line(pc, [(_torso_x(X, hy, y, hem, flare, -1) + 2, y), (_torso_x(X, hy, y, hem, flare, 1) - 2, y)], 2)
            y += 19
        for vx in (-34, -20, 20, 34):
            yb = hem - 2
            pen.line(pc, [(X(vx * .9), top + 6), (X(vx * .82), yb)], 2)
        pen.line(_lite(pc, .5), [(_torso_x(X, hy, hy + 66, hem, flare, -1) + 2, hy + 66),
                                 (_torso_x(X, hy, hy + 66, hem, flare, 1) - 2, hy + 66)], 1)
    if neck == "hood":
        # hood bunched behind the neck + drawstrings + kangaroo pocket + ribbed hem
        hc = _dark(coat, .15)
        pen.poly(hc, [(X(-31), hy + 47), (X(-27), hy + 31), (X(-13), hy + 23), (X(13), hy + 23),
                      (X(27), hy + 31), (X(31), hy + 47), (X(16), hy + 40), (0, hy + 44), (X(-16), hy + 40)])
        pen.line(_lite(coat, .25), [(X(-27), hy + 32), (X(-13), hy + 24), (X(13), hy + 24)], 2, light=True)
        pen.line(_dark(coat, .45), [(X(-16), hy + 41), (0, hy + 45), (X(16), hy + 41)], 2)
        sc = spec.get("strings", _lite(coat, .5))
        for sx in (-6, 6):
            pen.line(sc, [(sx, hy + 44), (sx * 1.2, hy + 84)], 2)
            pen.circ(sc, sx * 1.2, hy + 86, 2)
        _print(pen, spec, X, hy, X(20))
        py0, py1 = hem - 46, hem - 6
        pen.line(_dark(coat, .38), [(X(-30), py1), (X(-23), py0), (X(23), py0), (X(30), py1)], 2)
        pen.line(_lite(coat, .14), [(X(-22), py0 + 2), (X(22), py0 + 2)], 1)
        pen.poly(_dark(coat, .2), [(_torso_x(X, hy, hem - 9, hem, flare, -1), hem - 9),
                                   (_torso_x(X, hy, hem - 9, hem, flare, 1), hem - 9),
                                   (_torso_x(X, hy, hem, hem, flare, 1), hem), (_torso_x(X, hy, hem, hem, flare, -1), hem)])
    elif neck == "crew":
        pen.poly(_dark(coat, .35), [(X(-15), hy + 35), (X(15), hy + 35), (X(10), hy + 45), (X(-10), hy + 45)])
        _print(pen, spec, X, hy, X(26))
    elif neck == "open":
        inner = spec.get("inner", spec["shirt"])
        pen.poly(inner, [(X(-15), hy + 35), (X(15), hy + 35), (X(18), hem), (X(-18), hem)])
        pen.poly(_dark(inner, .35), [(X(-11), hy + 35), (X(11), hy + 35), (X(7), hy + 43), (X(-7), hy + 43)])
        _print(pen, spec, X, hy, X(13))
        for side in (-1, 1):          # shirt fronts + collar points
            pen.line(_dark(coat, .3), [(X(side * 15), hy + 40), (X(side * 18), hem)], 2)
            pen.line(_lite(coat, .25), [(X(side * 17), hy + 44), (X(side * 20), hem)], 1)
            pen.poly(coat, [(X(side * 12), hy + 33), (X(side * 27), hy + 36), (X(side * 17), hy + 58)])
            pen.line(_dark(coat, .35), [(X(side * 12), hy + 33), (X(side * 17), hy + 58)], 1)


def _body(pen, spec, t, moving, prop, prop_label, label_font, seated=False, reach=None, arms=True):
    bulk = spec["bulk"]
    X = lambda x: x * bulk
    step = math.sin(t * .009) * moving
    breath = math.sin(t * .0023) * 1.4 * (1 - moving)
    hy = -258 + breath + spec.get("stoop", 0)
    skin, coat = spec["skin"], spec["coat"]
    long_coat = spec["long_coat"]
    hem = spec.get("hem", -60 if long_coat else -95)
    neck = spec.get("neck")          # None (tailored) | "hood" | "crew" | "open"
    # legs (hip → knee → shoe), shaded outer edge + shoe ellipse
    for side in (-1, 1):
        if seated:  # front view: short foreshortened thigh, shin straight down
            hip, knee, shoe = (X(side * 15), -104 + _SEAT_DROP), (X(side * 23), -42), (X(side * 21), 0)
        else:
            hip, knee, shoe = (X(side * 15), -104), (X(side * 17) + step * side * 7, -49), (X(side * 18) - step * side * 13, 0)
        pen.line(spec["trousers"], [hip, knee, shoe], 19 * bulk)
        pen.line(_lite(spec["trousers"], .22), [(hip[0] - 7, hip[1]), (knee[0] - 7, knee[1])], 2, light=True)
        if spec.get("rips"):          # worn-through knees
            for dy_ in (-6, 0, 5):
                pen.line(spec["rips"], [(knee[0] - 6, knee[1] + dy_), (knee[0] + 5, knee[1] + dy_ + 1)], 1)
            pen.line(spec["rips"], [(knee[0] - 3, knee[1] + 22), (knee[0] + 4, knee[1] + 23)], 1)
        if spec.get("boots_h"):       # rubber boot shafts up the shin
            top = (shoe[0] + (knee[0] - shoe[0]) * spec["boots_h"], shoe[1] + (knee[1] - shoe[1]) * spec["boots_h"])
            pen.line(spec["shoes"], [top, (shoe[0], shoe[1] - 2)], 22 * bulk)
            pen.line(_lite(spec["shoes"], .3), [(top[0] - 10 * bulk, top[1]), (top[0] + 10 * bulk, top[1])], 2)
            pen.line(_lite(spec["shoes"], .18), [(top[0] - 8, top[1] + 3), (shoe[0] - 8, shoe[1] - 6)], 1, light=True)
        pen.ell(spec["shoes"], shoe[0] - 15, shoe[1] - 4, shoe[0] + 19, shoe[1] + 5)
        pen.line(_lite(spec["shoes"], .3), [(shoe[0] - 9, shoe[1] - 2), (shoe[0] + 8, shoe[1] - 2)], 1)
        if spec.get("sole"):
            pen.line(spec["sole"], [(shoe[0] - 14, shoe[1] + 3), (shoe[0] + 18, shoe[1] + 3)], 2)
    # torso (seated: everything above the hips rides down with them)
    if seated:
        pen.oy = _SEAT_DROP
    top = hy + 33
    torso = [(X(-47), hy + 43), (X(-25), top), (X(24), top), (X(47), hy + 46)]
    flare = 9 if long_coat else 0
    torso += [(X(37 + flare), hem), (X(-37 - flare), hem)]
    pen.poly(coat, torso)
    pen.poly(_dark(coat, .28), [(X(14), hy + 36), (X(47), hy + 46), (X(37 + flare), hem), (X(18), hem)], light=True)
    pen.line(spec.get("rim") or _lite(coat, .3), [(X(-46), hy + 49), (X(-37 - flare), hem)], 2, light=True)
    if spec.get("rim"):
        pen.line(spec["rim"], [(X(46), hy + 50), (X(37 + flare), hem)], 2, light=True)
    if neck:
        _casual_front(pen, spec, X, hy, top, hem, flare)
    # lapels / shirt / tie
    if not neck:
        pen.poly(spec["lapel"], [(X(-21), hy + 37), (0, hy + 73), (X(21), hy + 37)])
    if spec.get("vest"):
        pen.poly(spec["vest"], [(X(-26), hy + 50), (X(26), hy + 50), (X(24), hy + 118), (X(-24), hy + 118)])
        for i in range(3):
            px = X(-21 + i * 14.5)
            pen.poly(_dark(spec["vest"], .4), [(px, hy + 86), (px + 11, hy + 86), (px + 11, hy + 106), (px, hy + 106)])
            pen.line(_lite(spec["vest"], .2), [(px, hy + 86), (px + 11, hy + 86)], 1)
            pen.circ((90, 98, 90), px + 5.5, hy + 91, 1.2)
    if not neck:
        pen.poly(spec["shirt"], [(X(-14), hy + 35), (0, hy + 51), (X(14), hy + 35)])
    if spec.get("tie"):
        pen.poly(spec["tie"], [(-5, hy + 48), (5, hy + 48), (7, hy + 100), (0, hy + 112), (-6, hy + 101)])
        pen.line(_lite(spec["tie"], .3), [(-2, hy + 56), (-2, hy + 98)], 1)
    for side in (-1, 1) if not neck else ():
        pen.line(_lite(spec["lapel"], .25), [(X(side * 23), hy + 37), (X(side * 31), hy + 70), (X(side * 9), hy + 92)], 2)
    if spec.get("buttons"):
        for i in range(3):
            pen.circ(spec["buttons"], 0 if spec.get("tie") else 4, hy + 112 + i * 14, 2.4)
    if spec.get("epaulets"):
        for side in (-1, 1):
            pen.poly(spec["epaulets"], [(X(side * 36), hy + 44), (X(side * 52), hy + 47), (X(side * 50), hy + 52), (X(side * 34), hy + 49)])
    if spec.get("medal"):
        pen.circ(spec["medal"], X(-24), hy + 70, 3.4)
        pen.line(_lite(spec["medal"], .2), [(X(-24), hy + 66), (X(-24), hy + 62)], 1)
    if spec.get("patch"):
        pen.poly(spec["patch"], [(X(10), hy + 62), (X(26), hy + 62), (X(26), hy + 72), (X(10), hy + 72)])
        pen.line((205, 205, 200), [(X(10), hy + 62), (X(26), hy + 62), (X(26), hy + 72), (X(10), hy + 72), (X(10), hy + 62)], 1)
    if spec.get("belt"):
        by = -112
        pen.poly(spec["belt"], [(X(-37), by), (X(37), by), (X(36), by + 9), (X(-36), by + 9)])
        pen.poly((174, 155, 106), [(-5, by + 2), (5, by + 2), (5, by + 8), (-5, by + 8)])
    if long_coat:  # centre seam + hem highlight
        pen.line(_dark(coat, .5), [(0, hy + 112), (0, hem)], 1)
        pen.line(_lite(coat, .2), [(X(-46), hem), (X(46), hem)], 1)
    # arms: 2-bone limbs, lit outer edge, cuff, hand
    glove = spec.get("glove")
    targets = _reach_units(pen, reach)
    for side in (-1, 1) if arms else ():
        sh, el = (X(side * 40), hy + 51), (X(side * 50), -171)
        wr = (X(side * 44), -145)
        hold = prop and side == 1
        if hold:
            el, wr = (X(52), -150), (X(70), -150)
        if side in targets:  # solve the elbow: bend outward and down
            wr = targets[side]
            mx, my = (sh[0] + wr[0]) / 2, (sh[1] + wr[1]) / 2
            el = (mx + side * 14, my + 12)
        if spec.get("sleeves") == "short":     # tee: bare arms, sleeve to mid upper arm
            sl = (sh[0] + (el[0] - sh[0]) * .55, sh[1] + (el[1] - sh[1]) * .55)
            pen.line(skin, [sh, el, wr], 13 * bulk)
            pen.line(_lite(skin, .2), [(el[0] - side * 5, el[1]), (wr[0] - side * 4, wr[1])], 1, light=True)
            pen.line(coat, [sh, sl], 18 * bulk)
            pen.line(_dark(coat, .3), [(sl[0] - 8 * bulk, sl[1]), (sl[0] + 8 * bulk, sl[1])], 2)
        else:
            pen.line(coat, [sh, el, wr], 16 * bulk)
            pen.line(_lite(coat, .22), [(sh[0] - side * 5, sh[1]), (el[0] - side * 6, el[1]), (wr[0] - side * 5, wr[1])], 1, light=True)
            cuff = spec.get("cuff_col", spec["shirt"])
            pen.line(cuff, [(el[0] + (wr[0] - el[0]) * .8, el[1] + (wr[1] - el[1]) * .8), wr], 17 * bulk * .8)
            if spec.get("plaid"):
                for f_ in (.3, .62):
                    a_ = (sh[0] + (el[0] - sh[0]) * f_, sh[1] + (el[1] - sh[1]) * f_)
                    pen.line(spec["plaid"], [(a_[0] - 8 * bulk, a_[1]), (a_[0] + 8 * bulk, a_[1] + 1)], 2)
        _hand(pen, skin, glove, wr[0], wr[1], side)
    if arms and spec.get("armband"):  # screen-left upper arm, like the M4 seam idiom
        sh, el = (X(-40), hy + 51), (X(-50), -171)
        a0 = (sh[0] + (el[0] - sh[0]) * .38, sh[1] + (el[1] - sh[1]) * .38)
        a1 = (sh[0] + (el[0] - sh[0]) * .62, sh[1] + (el[1] - sh[1]) * .62)
        pen.line(spec["armband"], [a0, a1], 17 * bulk)
        pen.line(_lite(spec["armband"], .25), [(a0[0] - 6, a0[1]), (a1[0] - 6, a1[1])], 1, light=True)
    if spec.get("satchel"):
        sc = spec["satchel"]
        pen.line(_dark(sc, .2), [(X(-26), hy + 40), (X(30), -110)], 3)
        pen.poly(sc, [(X(22), -122), (X(50), -122), (X(52), -86), (X(24), -86)])
        pen.poly(_dark(sc, .35), [(X(22), -122), (X(50), -122), (X(50), -110), (X(22), -110)])
        pen.circ((170, 150, 100), X(36), -112, 2)
    if spec.get("straps"):            # backpack straps over both shoulders
        stc = spec["straps"]
        for side in (-1, 1):
            pen.line(stc, [(X(side * 24), hy + 38), (X(side * 27), hy + 80), (X(side * 30), hy + 128)], 6)
            pen.line(_lite(stc, .25), [(X(side * 24) - 2, hy + 40), (X(side * 27) - 2, hy + 80)], 1, light=True)
            pen.poly((120, 120, 124), [(X(side * 27) - 4, hy + 92), (X(side * 27) + 4, hy + 92),
                                        (X(side * 27) + 4, hy + 98), (X(side * 27) - 4, hy + 98)])
    if prop == "folder":
        fx, fy = X(80), -158
        pen.poly((68, 52, 36), [(fx - 18, fy - 36), (fx + 18, fy - 36), (fx + 18, fy + 38), (fx - 18, fy + 38)])
        pen.line((130, 42, 36), [(fx - 18, fy - 36), (fx + 18, fy - 36), (fx + 18, fy + 38), (fx - 18, fy + 38), (fx - 18, fy - 36)], 2)
        if prop_label and label_font:
            lab = label_font.render(prop_label, True, (205, 170, 120))
            lab = pygame.transform.smoothscale(lab, (max(1, round(lab.get_width() * .65 * pen.k)), max(1, round(lab.get_height() * .65 * pen.k))))
            pen.s.blit(lab, (pen.p(fx, fy - 24)[0] - lab.get_width() // 2, pen.p(fx, fy - 24)[1]))
        _hand(pen, skin, glove, X(70), -150, 1)
    pen.oy = 0.0
    return hy + (_SEAT_DROP if seated else 0)


def draw_character(surface, who, cx, foot_y, scale=1.0, facing_right=True, silhouette=False,
                   t=0, fear=0, smile=0, blink=0, look=None, moving=0,
                   prop=None, prop_label=None, label_font=None, *, seated=False, reach=None,
                   bow=0, wardrobe=None, arms=True):
    spec = SPECS[who]
    if wardrobe:
        spec = {**spec, **wardrobe}
    k = scale * spec["height"] / _REF_H
    if silhouette:  # same pose, flattened to the usual near-black cutout
        half = 130 * k
        if reach:
            half = max(half, max(abs(dx) for dx, _ in reach) + 30 * k)
        w, h = int(half * 2) + 24, int(330 * k) + 24
        tmp = pygame.Surface((w, h), pygame.SRCALPHA)
        draw_character(tmp, who, w // 2, h - 12, scale, facing_right, False, t, fear, smile, blink,
                       look, moving, prop, prop_label, label_font, seated=seated, reach=reach,
                       bow=bow, wardrobe=wardrobe, arms=arms)
        tmp.fill((16, 18, 24, 255), special_flags=pygame.BLEND_RGBA_MULT)
        surface.blit(tmp, (int(cx - w // 2), int(foot_y - h + 12)))
        return
    pen = _Pen(surface, int(cx), int(foot_y), k, facing_right)
    # ground shadow (alpha, like the legacy sprites)
    sw, sh = max(2, int(104 * k)), max(2, int(16 * k))
    sh_s = pygame.Surface((sw, sh), pygame.SRCALPHA)
    pygame.draw.ellipse(sh_s, (0, 0, 0, 80), (0, 0, sw, sh))
    surface.blit(sh_s, (int(cx - sw / 2), int(foot_y - sh * .6)))
    hy = _body(pen, spec, t, moving, prop, prop_label, label_font, seated=seated, reach=reach, arms=arms)
    if look is None:
        look = 1 if facing_right else -1
    lean = 0
    if bow:
        hy += 12 * bow
        blink = max(blink, .55 * bow)
    _face(pen, spec, lean, hy, fear=fear, smile=smile, look=look * (1 if facing_right else -1) * .8,
          blink=blink)
