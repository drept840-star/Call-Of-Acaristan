"""m8duty_crowd.py - 42 unique Acaristan citizens for the M8 Duty epilogue.

Replaces the 5-cast recycled crowd in Capital Square with individually distinct,
grounded Eastern-bloc civilians (varied ages, genders, coats, knitwear, gilets,
headwear, facial features, builds, and standing poses). Rigs are built lazily
once and cached with unique ``_gl_spec_key`` tags for zero per-frame allocation.
"""
import math

__all__ = ["CROWD_COUNT", "crowd_specs", "crowd_members", "draw_crowd",
           "draw_maru_with_crutches"]

CROWD_COUNT = 42

# Grounded autumn/winter Eastern European dawn palettes
_SKINS = (
    (196, 158, 128),  # 0 fair warm
    (184, 146, 118),  # 1 medium olive
    (208, 174, 146),  # 2 pale winter
    (172, 134, 106),  # 3 weathered tan
    (190, 150, 122),  # 4 rosy medium
    (164, 126, 98),   # 5 sun-worn worker
    (202, 166, 138),  # 6 soft light
    (178, 142, 116),  # 7 tired sallow
    (188, 148, 114),  # 8 warm ochre
    (168, 136, 112),  # 9 elder pale-tan
)

_HAIRS = (
    (28, 24, 22),     # 0 jet dark
    (52, 38, 30),     # 1 espresso brown
    (84, 56, 38),     # 2 warm chestnut
    (112, 82, 54),    # 3 light walnut
    (96, 82, 66),     # 4 ash brown
    (142, 118, 82),   # 5 sandy dark blond
    (118, 56, 36),    # 6 muted auburn
    (108, 106, 102),  # 7 salt-and-pepper
    (148, 146, 142),  # 8 pewter grey
    (192, 190, 184),  # 9 silver-white
)

_IRISES = (
    (46, 34, 26),     # 0 dark brown
    (68, 52, 34),     # 1 hazel
    (48, 66, 86),     # 2 slate blue
    (52, 74, 58),     # 3 muted green
    (54, 58, 64),     # 4 charcoal grey
    (78, 54, 32),     # 5 amber brown
    (62, 78, 92),     # 6 steel blue
)

_COATS = (
    (46, 48, 54),     # 0 charcoal wool
    (34, 44, 66),     # 1 deep navy
    (132, 102, 70),   # 2 camel / tobacco
    (96, 40, 46),     # 3 oxblood burgundy
    (44, 66, 52),     # 4 forest wool
    (66, 80, 96),     # 5 slate blue-grey
    (68, 48, 38),     # 6 espresso brown
    (138, 106, 56),   # 7 muted ochre
    (78, 48, 68),     # 8 aubergine plum
    (124, 114, 98),   # 9 stone trench
    (116, 60, 44),    # 10 muted rust
    (76, 82, 58),     # 11 moss drab
    (136, 132, 124),  # 12 heathered oatmeal
    (44, 76, 80),     # 13 dark petrol
    (96, 72, 54),     # 14 chestnut tweed
    (56, 64, 48),     # 15 dark olive
    (64, 92, 96),     # 16 dusty teal
    (62, 62, 66),     # 17 warm graphite
)

_PANTS = (
    (36, 38, 44),     # 0 charcoal wool
    (28, 36, 52),     # 1 dark navy
    (52, 66, 88),     # 2 worn indigo denim
    (82, 76, 66),     # 3 taupe twill
    (48, 38, 32),     # 4 espresso trouser
    (58, 62, 68),     # 5 slate grey
    (44, 48, 38),     # 6 dark olive work
    (26, 26, 30),     # 7 black wool
    (70, 72, 74),     # 8 heather grey
    (94, 84, 68),     # 9 muted khaki
)

_SHOES = (
    (20, 20, 24),     # 0 black leather
    (44, 30, 22),     # 1 dark brown leather
    (58, 28, 26),     # 2 oxblood boot
    (32, 34, 38),     # 3 charcoal work boot
    (64, 52, 42),     # 4 worn suede
    (42, 44, 50),     # 5 dark grey sneaker
    (36, 40, 46),     # 6 slate shoe
)

_SHIRTS = (
    (186, 180, 166),  # 0 warm cream
    (148, 162, 176),  # 1 pale blue
    (158, 152, 140),  # 2 oatmeal knit
    (62, 64, 70),     # 3 charcoal turtleneck
    (112, 56, 60),    # 4 muted burgundy knit
    (116, 126, 108),  # 5 sage knit
    (128, 126, 124),  # 6 warm grey
    (156, 128, 78),   # 7 muted mustard
)

_TIES = (
    (34, 48, 76),     # 0 navy
    (104, 36, 40),    # 1 burgundy
    (40, 68, 52),     # 2 forest
    (52, 54, 60),     # 3 charcoal
    (114, 58, 38),    # 4 rust
    (62, 76, 92),     # 5 slate
)

_GLASSES = (
    (28, 28, 34),     # 0 dark horn
    (82, 58, 40),     # 1 tortoiseshell
    (118, 122, 128),  # 2 steel wire
    (64, 48, 36),     # 3 bronze wire
)

_HAT_COLS = {
    "beret": ((54, 36, 44), (38, 48, 62), (48, 66, 52), (76, 42, 46), (56, 54, 58)),
    "bandana": ((136, 104, 58), (94, 46, 54), (62, 78, 92), (78, 86, 64), (118, 72, 54)),
    "beanie": ((48, 56, 44), (86, 42, 46), (42, 46, 56), (92, 74, 52), (62, 64, 68)),
    "cap": ((56, 54, 50), (44, 48, 56), (72, 58, 46), (48, 56, 48)),
    "hat": ((44, 44, 48), (68, 54, 44), (58, 60, 52), (50, 44, 52)),
}

_SATCHELS = ((76, 52, 36), (62, 68, 54), (44, 46, 52), (96, 68, 44))
_PACKS = (
    ((46, 54, 64), (28, 32, 38)),
    ((58, 62, 48), (34, 38, 30)),
    ((74, 44, 44), (42, 26, 26)),
    ((66, 56, 46), (38, 32, 26)),
)


def _mix_col(a, b, t):
    return tuple(max(0, min(255, int(a[k] + (b[k] - a[k]) * t))) for k in range(3))


def _build_poses():
    """12 joint-safe, non-clipping crowd stances watching the courthouse steps."""
    from engine3d import POSES
    base = POSES["stand"]
    return (
        # 0: relaxed natural stand
        dict(base, spine=2, lsh_p=6, lsh_r=8, lel=14, rsh_p=8, rsh_r=8, rel=16, lhip_p=3, lkn=4),
        # 1: hands clasped in front of waist
        dict(base, spine=3, lsh_p=18, lsh_r=5, lsh_y=28, lel=62, rsh_p=18, rsh_r=5, rsh_y=-28, rel=62),
        # 2: arms folded loosely across chest
        dict(base, spine=2, lsh_p=24, lsh_r=7, lsh_y=42, lel=92, rsh_p=20, rsh_r=7, rsh_y=-42, rel=88),
        # 3: hands clasped behind back (elder/official stance)
        dict(base, spine=5, lsh_p=-12, lsh_r=8, lel=20, rsh_p=-12, rsh_r=8, rel=20, head_p=-2),
        # 4: right hand tucked near hip/pocket, left relaxed
        dict(base, spine=2, spine_r=-1.5, lsh_p=8, lsh_r=8, lel=16, rsh_p=-6, rsh_r=14, rsh_y=-20, rel=46, rhip_p=4, rkn=5),
        # 5: left hand tucked near hip/pocket, right relaxed
        dict(base, spine=2, spine_r=1.5, lsh_p=-6, lsh_r=14, lsh_y=20, rel=16, lel=46, rsh_p=8, rsh_r=8, lhip_p=4, lkn=5),
        # 6: thoughtful hand raised near collar/chin
        dict(base, spine=3, head_p=3, lsh_p=10, lsh_r=8, lel=22, rsh_p=40, rsh_r=8, rsh_y=-24, rel=104),
        # 7: left hand holding satchel strap / lapel
        dict(base, spine=2, lsh_p=26, lsh_r=7, lsh_y=18, lel=82, rsh_p=6, rsh_r=8, rel=14),
        # 8: subtle elder stoop, hands low in front
        dict(base, spine=10, head_p=-6, lsh_p=16, lsh_r=6, lsh_y=20, lel=44, rsh_p=16, rsh_r=6, rsh_y=-20, rel=44, lkn=6, rkn=6),
        # 9: attentive head-up listening posture
        dict(base, spine=-1, head_p=-5, head_y=4, lsh_p=6, lsh_r=9, lel=12, rsh_p=6, rsh_r=9, rel=12),
        # 10: slight turn toward neighbor / podium
        dict(base, spine=3, twist=-6, head_y=10, lsh_p=12, lsh_r=8, lel=26, rsh_p=6, rsh_r=9, rel=14),
        # 11: broad-shouldered braced stand
        dict(base, spine=4, lhip_r=5, rhip_r=5, lsh_p=10, lsh_r=11, lel=24, rsh_p=10, rsh_r=11, rel=24),
    )


# 42 curated citizens:
# (arch, demo, coat_i, pants_i, shoe_i, skin_i, hair_i, hstyle, headwear, facial,
#  glass_i, acc, pose_i, expr, scale, bulk, head_w)
# demo: "wy" young woman, "wm" adult woman, "wo" older woman,
#       "my" young man,   "mm" adult man,   "mo" older man
# Even indices stand on the left (-X, visible behind Biribel/Maru/Bodi/Alex);
# odd indices stand on the right (+X). Adjacent slots never share coat color.
_ROSTER = (
    # --- Row 0 (front) ---
    ("overcoat", "wm", 3,  0, 0, 2, 1, "crop",   ("beret", 4),   None,      0, "satchel0", 1, "neutral", 0.93, 0.86, 0.91),  # 0  L0
    ("overcoat", "mm", 1,  0, 0, 1, 0, "swept",  None,           "stubble", None, None,    0, "stern",   1.02, 1.04, 1.02),  # 1  R0
    ("overcoat", "mo", 5,  7, 0, 9, 8, "swept",  None,           "moust",   None, None,    3, "stern",   0.99, 1.04, 1.03),  # 2  L1
    ("trench",   "wm", 9,  4, 1, 0, 2, "fringe", None,           None,      1, "satchel1", 7, "worried", 0.94, 0.87, 0.90),  # 3  R1
    ("gilet",    "wy", 13, 2, 4, 6, 6, "fringe", None,           None,      None, "satchel0", 7, "neutral", 0.91, 0.84, 0.89),  # 4  L2
    ("flannel",  "mm", 10, 6, 3, 3, 1, "crop",   ("beanie", 2),  "stubble", None, "boots", 2, "neutral", 1.03, 1.08, 1.05),  # 5  R2
    ("knit",     "mm", 6,  6, 3, 5, 2, "crop",   ("beanie", 0),  "stubble", None, "boots", 2, "stern",   1.04, 1.09, 1.06),  # 6  L3
    ("blazer",   "mo", 0,  5, 0, 7, 9, "bald",   ("hat", 1),     "beard",   2, None,       8, "sad",     0.95, 1.01, 1.02),  # 7  R3
    ("overcoat", "wo", 8,  7, 1, 9, 9, "crop",   ("bandana", 0), None,      None, None,    8, "worried", 0.89, 0.88, 0.92),  # 8  L4
    ("blazer",   "mm", 14, 1, 1, 4, 4, "slick",  None,           "moust",   3, "satchel2", 4, "neutral", 1.01, 0.99, 0.98),  # 9  R4
    # --- Row 1 ---
    ("knit",     "my", 12, 0, 5, 0, 1, "curly",  None,           None,      None, "pack0", 0, "neutral", 0.97, 0.94, 0.96),  # 10 L5
    ("overcoat", "wm", 7,  4, 2, 8, 2, "swept",  ("beret", 0),   None,      None, "boots", 1, "smile",   0.92, 0.86, 0.90),  # 11 R5
    ("trench",   "wm", 2,  7, 1, 4, 1, "ponytail", None,         None,      1, "satchel3", 6, "neutral", 0.94, 0.87, 0.91),  # 12 L6
    ("hoodie",   "wy", 16, 2, 5, 2, 5, "shag",   None,           None,      None, "pack1", 5, "neutral", 0.90, 0.84, 0.89),  # 13 R6
    ("blazer",   "mm", 1,  5, 0, 1, 4, "slick",  None,           None,      2, None,       4, "stern",   1.02, 1.01, 1.00),  # 14 L7
    ("flannel",  "mm", 3,  0, 3, 5, 0, "crop",   ("cap", 0),     "moust",   None, "boots", 11, "stern",  1.05, 1.11, 1.08),  # 15 R7
    ("overcoat", "mo", 11, 3, 1, 3, 7, "crop",   ("hat", 0),     "beard",   None, None,    3, "sad",     0.96, 1.03, 1.04),  # 16 L8
    ("gilet",    "my", 12, 1, 5, 6, 3, "spiky",  None,           None,      None, "sole",  9, "neutral", 0.98, 0.95, 0.97),  # 17 R8
    ("hoodie",   "wy", 4,  8, 5, 2, 5, "shag",   None,           None,      None, "sole",  2, "worried", 0.91, 0.84, 0.88),  # 18 L9
    ("overcoat", "wo", 15, 7, 0, 9, 8, "crop",   ("bandana", 1), None,      0, None,       8, "neutral", 0.88, 0.89, 0.92),  # 19 R9
    # --- Row 2 ---
    ("overcoat", "mm", 0,  1, 0, 7, 0, "mop",    None,           "stubble", None, None,    11, "stern",  1.05, 1.08, 1.06),  # 20 L10
    ("overcoat", "wm", 4,  0, 2, 0, 6, "ponytail", ("beret", 1), None,      None, "satchel1", 1, "neutral", 0.93, 0.86, 0.90),  # 21 R10
    ("gilet",    "mm", 10, 2, 3, 8, 2, "crop",   ("cap", 1),     "moust",   None, "boots", 5, "neutral", 1.00, 1.06, 1.04),  # 22 L11
    ("knit",     "mm", 6,  9, 4, 3, 7, "crop",   None,           "beard",   None, None,    10, "stern",  1.01, 1.10, 1.07),  # 23 R11
    ("hoodie",   "my", 7,  0, 5, 1, 0, "spiky",  None,           None,      None, "pack2", 9, "neutral", 0.96, 0.93, 0.95),  # 24 L12
    ("blazer",   "wm", 17, 7, 0, 6, 1, "swept",  None,           None,      2, "satchel2", 6, "stern",   0.95, 0.88, 0.91),  # 25 R12
    ("blazer",   "mo", 14, 4, 1, 9, 8, "bald",   None,           "moust",   3, None,       3, "sad",     0.97, 1.02, 1.03),  # 26 L13
    ("trench",   "wo", 2,  3, 1, 7, 9, "crop",   ("bandana", 2), None,      None, None,    8, "worried", 0.87, 0.87, 0.91),  # 27 R13
    ("trench",   "wm", 9,  5, 6, 4, 3, "ponytail", None,         None,      None, "boots", 1, "smile",   0.94, 0.86, 0.90),  # 28 L14
    ("hoodie",   "my", 13, 2, 5, 4, 4, "mop",    None,           None,      None, "pack3", 4, "neutral", 0.99, 0.96, 0.97),  # 29 R14
    # --- Row 3 ---
    ("flannel",  "mm", 15, 6, 3, 5, 1, "crop",   ("beanie", 1),  "stubble", None, "cig",   10, "stern",  1.03, 1.07, 1.04),  # 30 L15
    ("overcoat", "wo", 8,  0, 0, 2, 9, "crop",   ("beret", 2),   None,      1, None,       1, "sad",     0.89, 0.88, 0.92),  # 31 R15
    ("overcoat", "wy", 16, 7, 6, 6, 2, "fringe", None,           None,      None, "satchel0", 9, "neutral", 0.92, 0.83, 0.89),  # 32 L16
    ("gilet",    "mm", 11, 4, 3, 8, 0, "curly",  None,           "stubble", None, "boots", 11, "neutral", 1.04, 1.12, 1.08),  # 33 R16
    ("blazer",   "mo", 17, 0, 0, 9, 9, "crop",   ("hat", 2),     None,      0, None,       3, "stern",   0.98, 1.00, 1.01),  # 34 L17
    ("overcoat", "mm", 5,  1, 0, 1, 2, "swept",  None,           "moust",   None, "cig",   4, "neutral", 1.06, 1.05, 1.03),  # 35 R17
    ("gilet",    "wm", 3,  8, 4, 0, 1, "ponytail", None,         None,      None, "pack0", 7, "neutral", 0.93, 0.87, 0.90),  # 36 L18
    ("knit",     "wy", 1,  3, 6, 2, 6, "shag",   ("beanie", 3),  None,      None, "sole",  5, "smile",   0.90, 0.84, 0.88),  # 37 R18
    ("knit",     "mo", 5,  4, 1, 7, 8, "crop",   ("cap", 2),     "beard",   None, None,    8, "worried", 0.95, 1.04, 1.05),  # 38 L19
    ("flannel",  "mm", 10, 2, 3, 5, 3, "crop",   None,           "stubble", None, "boots", 2, "stern",   1.02, 1.06, 1.04),  # 39 R19
    # --- Row 4 (rear pair) ---
    ("overcoat", "wo", 2,  4, 1, 9, 9, "crop",   ("bandana", 3), None,      None, None,    8, "neutral", 0.88, 0.89, 0.93),  # 40 L20
    ("overcoat", "mo", 0,  5, 0, 3, 7, "crop",   ("hat", 3),     "moust",   2, None,       3, "stern",   1.00, 1.06, 1.05),  # 41 R20
)


def _spec_for(idx, entry):
    (arch, demo, coat_i, pants_i, shoe_i, skin_i, hair_i, hstyle,
     headwear, facial, glass_i, acc, _pose_i, expr, scale, bulk, head_w) = entry
    is_woman = demo.startswith("w")
    is_old = demo.endswith("o")
    coat = _COATS[coat_i]
    pants = _PANTS[pants_i]
    boots = _SHOES[shoe_i]
    skin = _SKINS[skin_i]
    hair = _HAIRS[hair_i]
    iris = _IRISES[(idx * 3 + skin_i) % len(_IRISES)]
    shirt = _SHIRTS[(idx * 5 + coat_i) % len(_SHIRTS)]

    ponytail = (hstyle == "ponytail")
    rig_style = "swept" if ponytail else hstyle
    if headwear is not None and headwear[0] in ("beanie", "cap", "hat") and rig_style in ("mop", "messy"):
        rig_style = "crop"

    spec = dict(
        skin=skin,
        hair=hair,
        jacket=coat,
        vest=None,
        pants=pants,
        boots=boots,
        glove=None,
        accent=None,
        armband=None,
        iris=iris,
        ears=True,
        brow_t=1 if is_woman else (2 + (idx % 3)),
        head_w=head_w,
        hair_style=rig_style,
        scale=scale,
        bulk=bulk,
        belt=None,
        pouches=False,
        expression=expr,
    )
    if ponytail:
        spec["ponytail"] = True
    if headwear is not None:
        hkind, hci = headwear
        pal = _HAT_COLS[hkind]
        spec[hkind] = pal[hci % len(pal)]
    if is_old:
        spec["creases"] = (110, 84, 70)
    if not is_woman:
        if facial == "beard":
            spec["beard"] = _mix_col(hair, (22, 20, 18), 0.12)
        elif facial == "moust":
            spec["moustache"] = _mix_col(hair, (20, 18, 16), 0.14)
            spec["moustache_h"] = 0.020 + (idx % 3) * 0.003
        elif facial == "stubble":
            spec["stubble"] = True
            spec["stubble_t"] = 0.16 + (idx % 3) * 0.04
    if glass_i is not None:
        spec["glasses"] = _GLASSES[glass_i % len(_GLASSES)]

    belt_col = (26, 22, 20) if (idx % 2 == 0) else (44, 32, 24)
    buckle_col = (158, 142, 98)

    if arch == "overcoat":
        spec["long_coat"] = coat
        spec["coat_len"] = 0.44 + (0.08 if is_woman else 0.02) + (idx % 3) * 0.02
        spec["shirt"] = shirt
        spec["lapel"] = _mix_col(coat, (14, 14, 18), 0.28)
        spec["buttons"] = _mix_col(coat, (18, 16, 16), 0.45)
        if not is_woman and idx % 3 == 0:
            spec["tie"] = _TIES[(idx + coat_i) % len(_TIES)]
    elif arch == "trench":
        spec["long_coat"] = coat
        spec["coat_len"] = 0.48 if is_woman else 0.42
        spec["shirt"] = shirt
        spec["lapel"] = _mix_col(coat, (18, 16, 16), 0.24)
        spec["belt"] = _mix_col(coat, (12, 12, 14), 0.35)
        spec["buckle"] = buckle_col
    elif arch == "blazer":
        spec["shirt"] = shirt
        spec["lapel"] = _mix_col(coat, (14, 14, 18), 0.26)
        spec["buttons"] = (144, 128, 92) if is_old else _mix_col(coat, (10, 10, 14), 0.42)
        spec["cuff"] = shirt
        spec["belt"] = belt_col
        spec["buckle"] = buckle_col
        if not is_woman:
            spec["tie"] = _TIES[(idx * 2 + coat_i) % len(_TIES)]
    elif arch == "gilet":
        # Sleeves/base knit in contrasting shirt tone; outer padded bodywarmer in coat tone
        spec["jacket"] = shirt
        spec["vest"] = coat
        spec["pouches"] = False
        spec["accent"] = None
        spec["belt"] = belt_col
    elif arch == "hoodie":
        spec["hoodie"] = True
        spec["strings"] = _mix_col(coat, (226, 224, 218), 0.55)
    elif arch == "flannel":
        spec["inner"] = _SHIRTS[3] if (idx % 2 == 0) else _SHIRTS[0]
        spec["plaid"] = _mix_col(coat, (16, 14, 14), 0.42)
        spec["belt"] = belt_col
    else:  # "knit"
        spec["crew"] = True
        spec["belt"] = belt_col

    if acc == "boots":
        spec["boots_h"] = 0.50 + (0.08 if is_woman else 0.02)
    elif acc == "sole":
        spec["sole"] = (188, 186, 178)
    elif acc == "cig" and not is_woman:
        spec["cig"] = True
    elif acc and acc.startswith("satchel"):
        spec["satchel"] = _SATCHELS[int(acc[-1]) % len(_SATCHELS)]
    elif acc and acc.startswith("pack"):
        pack_col, strap_col = _PACKS[int(acc[-1]) % len(_PACKS)]
        spec["backpack"] = pack_col
        spec["straps"] = strap_col

    return spec


def crowd_specs():
    """Return the list of 42 unique Humanoid spec dicts (no GL/renderer side effects)."""
    return [_spec_for(i, row) for i, row in enumerate(_ROSTER)]


_CACHE = []
_MARU_POSE_CACHE = {}


def crowd_members():
    """Lazily build and cache the 42 ``(Humanoid, pose, amp)`` tuples."""
    if not _CACHE:
        from engine3d import Humanoid
        poses = _build_poses()
        for i, entry in enumerate(_ROSTER):
            spec = _spec_for(i, entry)
            hum = Humanoid(spec)
            hum._gl_spec_key = "m8d_crowd_%02d" % i
            pose = poses[entry[12] % len(poses)]
            amp = 0.11 + (i % 5) * 0.024
            _CACHE.append((hum, pose, amp))
    return _CACHE


def draw_crowd(r, t, ch, vas_at, crowd_z):
    """Queue all 42 unique citizens in Capital Square facing Vasile's podium."""
    from cutscenes import m6world3d as _w
    members = crowd_members()
    ti = int(t)
    for i, (hum, pose, amp) in enumerate(members):
        side = -1.0 if i % 2 == 0 else 1.0
        lane = i // 2
        row = lane // 5
        col = lane % 5
        jx = math.sin(i * 2.31) * 0.42
        jz = math.cos(i * 1.73) * 0.35
        x = ch[0] + side * (4.3 + col * 1.65) + jx
        z = crowd_z + 0.5 - row * 1.35 + jz
        yaw = math.degrees(math.atan2(vas_at[0] - x, vas_at[2] - z)) + math.sin(i * 3.1) * 7.0
        live = _w.life_pose(pose, ti, amp=amp, seed=500 + i)
        r.add_humanoid(hum, live, (x, 0.08, z), yaw, rifle_on=False)


def _norm3(v):
    ln = math.sqrt(v[0] * v[0] + v[1] * v[1] + v[2] * v[2])
    if ln < 1e-6:
        return (0.0, 1.0, 0.0)
    return (v[0] / ln, v[1] / ln, v[2] / ln)


def _basis_from_xy(x_hint, y_vec):
    """Left-handed det=+1 orthonormal 3x3 basis with exact +Y along ``y_vec``."""
    from engine3d.core import v_cross, v_dot
    Y = _norm3(y_vec)
    d = v_dot(x_hint, Y)
    xp = (x_hint[0] - Y[0] * d, x_hint[1] - Y[1] * d, x_hint[2] - Y[2] * d)
    if xp[0] * xp[0] + xp[1] * xp[1] + xp[2] * xp[2] < 1e-8:
        alt = (0.0, 0.0, 1.0) if abs(Y[0]) > 0.9 else (1.0, 0.0, 0.0)
        d = v_dot(alt, Y)
        xp = (alt[0] - Y[0] * d, alt[1] - Y[1] * d, alt[2] - Y[2] * d)
    X = _norm3(xp)
    Z = v_cross(X, Y)
    return (X[0], Y[0], Z[0], X[1], Y[1], Z[1], X[2], Y[2], Z[2])


def _add_strut(mesh, p0, p1, wx, wz, col, x_hint):
    """Add a shaded 3D box strut running from ``p0`` to ``p1``."""
    from engine3d import box
    dv = (p1[0] - p0[0], p1[1] - p0[1], p1[2] - p0[2])
    ln = math.sqrt(dv[0] * dv[0] + dv[1] * dv[1] + dv[2] * dv[2])
    if ln < 1e-4:
        return
    mid = ((p0[0] + p1[0]) * 0.5, (p0[1] + p1[1]) * 0.5, (p0[2] + p1[2]) * 0.5)
    mesh.add(box(wx, ln, wz, col), m=_basis_from_xy(x_hint, dv), t=mid)


def _maru_crutch_pose(m_hum, pos, yaw):
    """Cached natural forearm-crutch pose in Maru's local yaw frame."""
    key = (round(pos[0], 3), round(pos[1], 3), round(pos[2], 3), round(yaw, 2))
    got = _MARU_POSE_CACHE.get(key)
    if got is not None:
        return got
    from engine3d import POSES
    from engine3d.core import m_apply, rot_y, v_add
    from engine3d.hold import POLES, solve_arm_safe
    ry = rot_y(yaw)
    # Subtle weight shift off Maru's injured right leg into the crutches
    pose = dict(
        POSES["stand"],
        spine=4.0, spine_r=-2.0,
        lhip_p=2.0, lkn=4.0, lhip_r=3.0,
        rhip_p=11.0, rkn=18.0, rank=10.0, rhip_r=5.0,
    )
    for side_s, sgn in (("l", -1.0), ("r", 1.0)):
        grip_w = v_add(pos, m_apply(ry, (sgn * 0.295, 0.915, 0.155)))
        pole_w = m_apply(ry, (sgn * 0.26, -0.32, -0.92))
        pose = solve_arm_safe(m_hum, pose, pos, yaw, side_s, grip_w,
                              poles=(pole_w,) + POLES, margin=0.024)
    _MARU_POSE_CACHE[key] = pose
    return pose


def draw_maru_with_crutches(r, t, pos, yaw):
    """Draw Maru with shaded 3D aluminum forearm crutches locked to his live hands/elbows."""
    from cutscenes import m6world3d as _w
    from engine3d import Mesh, box
    from engine3d.core import m_apply, rot_y, v_add

    m_hum = _w.hum("maru")
    base_pose = _maru_crutch_pose(m_hum, pos, yaw)
    live_pose = _w.life_pose(base_pose, int(t), amp=0.035, seed=71)
    places, joints, root_off = m_hum.pose_world(live_pose, pos, yaw, rifle_on=False)
    r.add_humanoid(m_hum, live_pose, pos, yaw, rifle_on=False)

    elbows = {}
    for slot, _key, _m, org, _g, _fb in places:
        if slot == 6:
            elbows["l"] = v_add(org, root_off)
        elif slot == 12:
            elbows["r"] = v_add(org, root_off)

    ry = rot_y(yaw)
    right_v = m_apply(ry, (1.0, 0.0, 0.0))
    fwd_v = m_apply(ry, (0.0, 0.0, 1.0))

    alu_hi = (178, 184, 194)
    alu_lo = (142, 148, 158)
    rubber = (24, 26, 30)
    grip_c = (30, 32, 36)
    cuff_c = (40, 44, 52)
    trim_c = (64, 70, 78)
    pin_c = (182, 162, 108)

    crutches = Mesh()
    ground_y = pos[1]

    for side_s, sgn in (("l", -1.0), ("r", 1.0)):
        hand = joints.get(side_s + "hand")
        elbow = elbows.get(side_s)
        if hand is None or elbow is None:
            continue
        out_v = (right_v[0] * sgn, 0.0, right_v[2] * sgn)

        # Planted rubber ferrule foot slightly forward & outward for a stable stance
        tip = (hand[0] + out_v[0] * 0.070 + fwd_v[0] * 0.085,
               ground_y,
               hand[2] + out_v[2] * 0.070 + fwd_v[2] * 0.085)
        # Front-outer grip junction cleanly ahead of the knuckles
        junc = (hand[0] + fwd_v[0] * 0.056 + out_v[0] * 0.032,
                hand[1] + 0.008,
                hand[2] + fwd_v[2] * 0.056 + out_v[2] * 0.032)
        shaft_axis = _norm3((junc[0] - tip[0], junc[1] - tip[1], junc[2] - tip[2]))

        # Flush ground rubber ferrule + collar
        crutches.add(box(0.050, 0.036, 0.050, rubber), m=ry, t=(tip[0], ground_y + 0.018, tip[2]))
        fer_top = (tip[0] + shaft_axis[0] * 0.036, tip[1] + shaft_axis[1] * 0.036, tip[2] + shaft_axis[2] * 0.036)
        fer_col = (tip[0] + shaft_axis[0] * 0.064, tip[1] + shaft_axis[1] * 0.064, tip[2] + shaft_axis[2] * 0.064)
        _add_strut(crutches, fer_top, fer_col, 0.034, 0.034, trim_c, right_v)

        # Telescoping lower tube, lock collar with brass pin, upper main shaft
        mid = (tip[0] + (junc[0] - tip[0]) * 0.44,
               tip[1] + (junc[1] - tip[1]) * 0.44,
               tip[2] + (junc[2] - tip[2]) * 0.44)
        _add_strut(crutches, fer_col, mid, 0.022, 0.022, alu_lo, right_v)
        col_a = (mid[0] - shaft_axis[0] * 0.026, mid[1] - shaft_axis[1] * 0.026, mid[2] - shaft_axis[2] * 0.026)
        col_b = (mid[0] + shaft_axis[0] * 0.026, mid[1] + shaft_axis[1] * 0.026, mid[2] + shaft_axis[2] * 0.026)
        _add_strut(crutches, col_a, col_b, 0.034, 0.034, cuff_c, right_v)
        crutches.add(box(0.012, 0.012, 0.012, pin_c), m=ry,
                     t=(mid[0] + out_v[0] * 0.018, mid[1], mid[2] + out_v[2] * 0.018))
        _add_strut(crutches, col_b, junc, 0.028, 0.028, alu_hi, right_v)

        # Horizontal ergonomic rubber handle passing directly through Maru's fist
        grip_back = (hand[0] - fwd_v[0] * 0.058, hand[1] + 0.004, hand[2] - fwd_v[2] * 0.058)
        grip_front = (junc[0] + fwd_v[0] * 0.014, junc[1], junc[2] + fwd_v[2] * 0.014)
        _add_strut(crutches, grip_back, grip_front, 0.034, 0.034, grip_c, right_v)
        crutches.add(box(0.040, 0.044, 0.038, cuff_c), m=ry, t=junc)

        # Upper forearm strut rising outside the wrist to the 3D U-shaped cuff
        fa = (elbow[0] - hand[0], elbow[1] - hand[1], elbow[2] - hand[2])
        cuff_c_pt = (hand[0] + fa[0] * 0.62, hand[1] + fa[1] * 0.62, hand[2] + fa[2] * 0.62)
        cuff_m = _basis_from_xy(right_v, fa)
        cuff_mount = v_add(cuff_c_pt, m_apply(cuff_m, (sgn * 0.058, -0.010, -0.010)))
        _add_strut(crutches, junc, cuff_mount, 0.024, 0.024, alu_hi, right_v)

        # Open-front 3D polymer forearm U-cuff hugging Maru's sleeve
        crutches.add(box(0.122, 0.082, 0.016, cuff_c), m=cuff_m,
                     t=v_add(cuff_c_pt, m_apply(cuff_m, (0.0, 0.0, -0.056))))
        crutches.add(box(0.016, 0.082, 0.114, cuff_c), m=cuff_m,
                     t=v_add(cuff_c_pt, m_apply(cuff_m, (sgn * 0.056, 0.0, -0.006))))
        crutches.add(box(0.016, 0.082, 0.084, cuff_c), m=cuff_m,
                     t=v_add(cuff_c_pt, m_apply(cuff_m, (-sgn * 0.056, 0.0, -0.020))))
        crutches.add(box(0.022, 0.026, 0.028, alu_lo), m=cuff_m,
                     t=v_add(cuff_c_pt, m_apply(cuff_m, (sgn * 0.062, -0.010, -0.010))))

    if crutches.faces:
        r.add_dynamic(crutches.verts,
                      [(f[0], f[1], f[2], f[3], None, f[4]) for f in crutches.faces])
