
"""Character appearance: the cosmetic catalog, the appearance value object,
and the single validator that both the save file and the network use.

KEEP THIS MODULE DEPENDENCY-FREE (stdlib only, no pygame). It is imported by
three places that must never form a cycle:

  * entities.player   - the renderer, which resolves an appearance into RGB
  * net.protocol      - the wire validator, which cleans a peer's appearance
  * missions.arena    - the headless rules, which price and identify items

Same reason core.mapbuilder and core.user_settings stay pygame-free.

THE SECURITY SHAPE OF THIS DATA IS THE POINT. An appearance is a bundle of
catalog *identifiers*, never colours. There is no field anywhere - on disk or
on the wire - that can carry an RGB triple, so a hostile peer cannot paint
itself in arbitrary colours, cannot smuggle a huge payload as a colour, and
cannot make a sprite unreadable-by-design. Unknown identifiers collapse to
the free default. That is why cosmetics can ship before the relay-side
authentication the multiplayer roadmap asks for.

BASE_ROLES and GUN_BASE are the literal values lifted verbatim out of
entities/player.py's draw(). They are the legacy look. A palette or finish
whose override dict is empty therefore renders byte-identically to the sprite
that shipped before customization existed, which is what makes that refactor
provable rather than merely plausible - see tools/smoke_test.py
appearance_default_is_legacy and tools/avatar_parity.py.
"""

# ── Identifiers ─────────────────────────────────────────────────────────

GUN_KEYS = ("os12", "k9", "pistol")
"""The three guns an appearance carries a finish for."""

FINISH_KEY_BY_RIG = {
    # ArenaView/campaign set Player.rig_weapon to these strings; map them to
    # the gun key used in the finish table.
    "pistol": "pistol",
    "os12": "os12",
    "k9_smg": "k9",
}

ID_MAX = 32
"""Longest identifier we will read. Anything longer is junk, not a name."""

APPEARANCE_MAX_KEYS = 8
"""A canonical appearance has three keys. A bundle with more than this many
keys is an attempt at junk, so it is rejected whole before any value of it is
read."""

DEFAULT_PALETTE = "pal_olive"
DEFAULT_HEAD = "head_kevlar"
DEFAULT_FINISH_ID = "%s_standard"

# ── The legacy look, as data ────────────────────────────────────────────

BASE_ROLES = {
    # entities/player.py draw() literals, by name. The line numbers are where
    # the value came from, so a future edit to the sprite has to be made here
    # too or the two will drift apart.
    "uniform": (60, 70, 50),        # core.config.C_PLAYER_UNIFORM; :354 :488 :495
    "skin": (210, 180, 140),        # core.config.C_PLAYER_SKIN;   :502 :859
    "helmet": (30, 35, 28),         # :848
    "helmet_arc": (50, 58, 42),     # :851
    "helmet_rim": (44, 50, 38),     # new: only the added head gear reads this
    "eyes": (30, 20, 10),           # :863
    "kevlar": (50, 52, 56),         # :367
    "kevlar_edge": (28, 30, 32),    # :368
    "kevlar_line": (25, 27, 30),    # :374
    "kevlar_ridge": (38, 40, 44),   # :386
}

# No palette may touch these. Skintone is not a costume choice: letting a
# "colour scheme" recolor the face would let cosmetics encode a racial read of
# the character, and a shop full of "lighter" and "darker" faces is not a shop
# anyone wants to maintain. The key stays in the resolved map so that a later,
# explicit, separately-priced face tier can be added without touching the
# renderer.
NON_PALETTE_ROLES = ("skin",)

GUN_BASE = {
    # One entry per distinct literal in the corresponding draw block.
    "os12": {                        # player.py:509-682
        "receiver": (38, 36, 32),      # :531
        "cover": (58, 56, 52),         # :539
        "cover_edge": (22, 20, 18),    # :540
        "wood": (110, 70, 40),         # :548 :651 :674
        "wood_edge": (75, 48, 28),     # :549 :655 :679
        "barrel": (70, 68, 64),        # :557
        "muzzle": (50, 48, 44),        # :564 :663
        "groove": (35, 33, 30),        # :568 :573
        "bore": (8, 8, 10),            # :578
        "front_sight": (45, 43, 40),   # :584
        "mag": (28, 27, 24),           # :635
        "mag_edge": (16, 15, 13),      # :636
        "mag_ridge": (20, 19, 17),     # :643
    },
    "k9": {                          # player.py:684-781
        "receiver": (22, 25, 25),        # :710
        "receiver_edge": (72, 88, 82),   # :711
        "receiver_shine": (105, 126, 116),  # :712
        "can": (36, 40, 40),           # :723
        "can_shine": (96, 112, 104),   # :724
        "bore": (6, 8, 8),             # :727
        "stock": (62, 70, 66),         # :734
        "stock_knob": (38, 44, 42),    # :735
        "grip": (28, 30, 30),          # :742
        "grip_shine": (92, 100, 96),   # :743
        "mag": (20, 22, 22),           # :778
        "mag_edge": (76, 88, 82),      # :779
        "mag_line": (36, 40, 38),      # :780
    },
    "pistol": {                      # player.py:783-843
        "frame": (24, 25, 27),         # :805
        "slide": (52, 55, 58),         # :813
        "slide_edge": (12, 13, 15),    # :814
        "barrel": (70, 74, 78),        # :820
        "bore": (8, 8, 10),            # :823
        "grip": (18, 19, 20),          # :831 :838
        "optic": (180, 35, 35),        # :843
    },
}

# ── Catalog ─────────────────────────────────────────────────────────────
# Every entry is {name, price, desc} plus the colour overrides it grants.
# Price 0 means free, which means owned from the first run.

PALETTES = {
    "pal_olive": {
        "name": "Olive Drab", "price": 0,
        "desc": "Standard IPA field issue. What you start in.",
        "roles": {},
    },
    "pal_coyote": {
        "name": "Coyote Tan", "price": 120,
        "desc": "Dust-coloured rig for the southern districts.",
        "roles": {
            "uniform": (122, 102, 72), "helmet": (74, 60, 42),
            "helmet_arc": (100, 84, 60), "helmet_rim": (88, 72, 50),
            "eyes": (40, 28, 18), "kevlar": (78, 66, 48),
            "kevlar_edge": (48, 40, 28), "kevlar_line": (42, 35, 25),
            "kevlar_ridge": (60, 50, 36),
        },
    },
    "pal_krap": {
        "name": "KRAP Slate", "price": 150,
        "desc": "Enemy issue. Wearing it is a statement.",
        "roles": {
            "uniform": (55, 65, 80), "helmet": (26, 32, 42),
            "helmet_arc": (44, 54, 70), "helmet_rim": (38, 46, 60),
            "eyes": (16, 20, 26), "kevlar": (44, 50, 62),
            "kevlar_edge": (24, 28, 36), "kevlar_line": (20, 24, 30),
            "kevlar_ridge": (34, 40, 50),
        },
    },
    "pal_winter": {
        "name": "Winterfall", "price": 180,
        "desc": "Pale over-whites for the northern yards.",
        "roles": {
            "uniform": (180, 188, 196), "helmet": (96, 102, 110),
            "helmet_arc": (140, 148, 158), "helmet_rim": (120, 128, 138),
            "eyes": (28, 30, 34), "kevlar": (120, 126, 132),
            "kevlar_edge": (70, 74, 80), "kevlar_line": (62, 66, 72),
            "kevlar_ridge": (96, 102, 110),
        },
    },
    "pal_noir": {
        "name": "Noir", "price": 220,
        "desc": "Unmarked black. Quietly not regulation.",
        "roles": {
            "uniform": (34, 36, 40), "helmet": (18, 19, 22),
            "helmet_arc": (40, 42, 48), "helmet_rim": (30, 32, 36),
            "eyes": (12, 12, 14), "kevlar": (26, 28, 32),
            "kevlar_edge": (12, 13, 15), "kevlar_line": (10, 11, 13),
            "kevlar_ridge": (20, 22, 26),
        },
    },
    "pal_rust": {
        "name": "Rust Plate", "price": 260,
        "desc": "Oxidised red-brown off the foundry weld-line.",
        "roles": {
            "uniform": (110, 58, 40), "helmet": (62, 32, 24),
            "helmet_arc": (92, 50, 36), "helmet_rim": (78, 42, 30),
            "eyes": (30, 14, 10), "kevlar": (74, 42, 34),
            "kevlar_edge": (44, 24, 18), "kevlar_line": (38, 20, 16),
            "kevlar_ridge": (58, 32, 26),
        },
    },
    "pal_jungle": {
        "name": "Jungle Breakup", "price": 300,
        "desc": "Deep green with a darker shell plate.",
        "roles": {
            "uniform": (46, 72, 44), "helmet": (24, 40, 24),
            "helmet_arc": (40, 62, 38), "helmet_rim": (34, 52, 32),
            "eyes": (18, 22, 14), "kevlar": (36, 52, 36),
            "kevlar_edge": (20, 30, 20), "kevlar_line": (16, 26, 16),
            "kevlar_ridge": (28, 42, 28),
        },
    },
    "pal_parade": {
        "name": "Parade Dress", "price": 380,
        "desc": "Dress navy with a gilt crest. Loud on purpose.",
        "roles": {
            "uniform": (28, 44, 86), "helmet": (16, 24, 44),
            "helmet_arc": (150, 128, 52), "helmet_rim": (176, 152, 72),
            "eyes": (10, 12, 20), "kevlar": (22, 34, 64),
            "kevlar_edge": (10, 16, 30), "kevlar_line": (8, 14, 26),
            "kevlar_ridge": (60, 52, 30),
        },
    },
}

HEADGEARS = {
    "head_kevlar": {
        "name": "Kevlar Lid", "price": 0,
        "desc": "The issued shell. The original silhouette.",
    },
    "head_peaked_cap": {
        "name": "Peaked Cap", "price": 180,
        "desc": "Officer's cover with a stiff peak.",
    },
    "head_beret": {
        "name": "Beret", "price": 220,
        "desc": "Pulled to one side. No helmet at all.",
    },
    "head_balaclava": {
        "name": "Balaclava", "price": 260,
        "desc": "Wool over the whole head, eyes left out.",
    },
    "head_goggles": {
        "name": "Ballistic Goggles", "price": 320,
        "desc": "Shell plus a strap band and two lenses.",
    },
    "head_heavy_helmet": {
        "name": "Heavy Helmet", "price": 420,
        "desc": "The big one. Rim, and a night-vision mount.",
    },
}

FINISHES = {
    # ── OS 12 ──
    "os12_standard": {"name": "Issue", "price": 0, "gun": "os12",
                      "desc": "Wood and worn steel, as it left the rack.",
                      "roles": {}},
    "os12_woodland": {"name": "Woodland Cerakote", "price": 140, "gun": "os12",
                      "desc": "Green receiver, original wood furniture.",
                      "roles": {"receiver": (40, 46, 34), "cover": (56, 64, 48),
                                "cover_edge": (20, 24, 18), "mag": (30, 34, 26),
                                "mag_edge": (16, 19, 14), "mag_ridge": (22, 26, 20)}},
    "os12_blued": {"name": "Blued Steel", "price": 180, "gun": "os12",
                   "desc": "Deep gunsteel blue across the works.",
                   "roles": {"receiver": (30, 34, 44), "cover": (52, 58, 70),
                             "cover_edge": (14, 17, 22), "barrel": (48, 54, 66),
                             "muzzle": (36, 40, 50), "groove": (24, 28, 36),
                             "front_sight": (40, 46, 58), "bore": (6, 7, 10),
                             "mag": (26, 30, 38), "mag_edge": (12, 14, 18),
                             "mag_ridge": (18, 21, 26)}},
    "os12_sandpoly": {"name": "Sand Poly", "price": 240, "gun": "os12",
                      "desc": "Desert polymer furniture and receiver.",
                      "roles": {"receiver": (168, 150, 110), "cover": (190, 172, 132),
                                "cover_edge": (120, 104, 72), "wood": (176, 158, 118),
                                "wood_edge": (128, 110, 78), "barrel": (150, 134, 100),
                                "muzzle": (132, 116, 84), "groove": (110, 96, 68),
                                "mag": (160, 142, 104), "mag_edge": (112, 98, 70),
                                "mag_ridge": (140, 124, 90)}},
    "os12_crimson": {"name": "Crimson", "price": 320, "gun": "os12",
                     "desc": "Blood-red furniture over a dark receiver.",
                     "roles": {"receiver": (96, 24, 28), "cover": (128, 34, 38),
                               "cover_edge": (52, 12, 16), "wood": (70, 20, 22),
                               "wood_edge": (44, 12, 14), "mag": (78, 20, 24),
                               "mag_edge": (40, 10, 12), "mag_ridge": (60, 16, 18)}},
    "os12_goldleaf": {"name": "Gold Leaf", "price": 600, "gun": "os12",
                      "desc": "Gilt lockup. Purely decorative, purely expensive.",
                      "roles": {"receiver": (168, 128, 42), "cover": (206, 168, 66),
                                "cover_edge": (110, 84, 26), "wood": (140, 104, 36),
                                "wood_edge": (96, 70, 22), "barrel": (184, 146, 54),
                                "muzzle": (150, 116, 38), "groove": (110, 84, 26),
                                "front_sight": (196, 158, 60), "mag": (158, 120, 40),
                                "mag_edge": (98, 74, 22), "mag_ridge": (128, 98, 32)}},
    # ── K-9 ──
    "k9_standard": {"name": "Issue", "price": 0, "gun": "k9",
                    "desc": "Suppressed black, as the unit issues it.",
                    "roles": {}},
    "k9_arctic": {"name": "Arctic White", "price": 160, "gun": "k9",
                  "desc": "Pale winter coating over the whole PDW.",
                  "roles": {"receiver": (200, 206, 214), "receiver_edge": (232, 238, 246),
                            "receiver_shine": (250, 252, 255), "can": (176, 182, 190),
                            "can_shine": (226, 232, 240), "stock": (150, 156, 164),
                            "stock_knob": (120, 126, 134), "grip": (128, 134, 142),
                            "grip_shine": (196, 202, 210), "mag": (140, 146, 154),
                            "mag_edge": (186, 192, 200), "mag_line": (160, 166, 174)}},
    "k9_gunmetal": {"name": "Gunmetal", "price": 180, "gun": "k9",
                    "desc": "Cool grey with a bright edge highlight.",
                    "roles": {"receiver": (52, 56, 62), "receiver_edge": (92, 98, 106),
                              "receiver_shine": (128, 136, 146), "can": (60, 64, 70),
                              "can_shine": (104, 110, 118), "grip": (46, 50, 56),
                              "grip_shine": (98, 104, 112), "mag": (44, 48, 54),
                              "mag_edge": (88, 94, 102), "mag_line": (66, 70, 76)}},
    "k9_olivepoly": {"name": "Olive Poly", "price": 240, "gun": "k9",
                     "desc": "Green polymer, matched to an Olive Drab rig.",
                     "roles": {"receiver": (72, 82, 58), "receiver_edge": (108, 122, 86),
                               "receiver_shine": (140, 154, 112), "can": (66, 76, 54),
                               "can_shine": (100, 114, 80), "stock": (78, 88, 62),
                               "stock_knob": (52, 60, 42), "grip": (58, 68, 46),
                               "grip_shine": (96, 108, 78), "mag": (54, 64, 44),
                               "mag_edge": (92, 104, 74), "mag_line": (70, 80, 56)}},
    "k9_vandal": {"name": "Vandal", "price": 320, "gun": "k9",
                  "desc": "Red slash over bare black.",
                  "roles": {"receiver": (140, 28, 44), "receiver_edge": (196, 52, 68),
                            "receiver_shine": (226, 96, 110), "can": (34, 34, 38),
                            "can_shine": (150, 40, 54), "grip": (28, 28, 32),
                            "grip_shine": (186, 64, 78), "mag": (30, 30, 34),
                            "mag_edge": (166, 52, 66), "mag_line": (96, 40, 50)}},
    "k9_goldleaf": {"name": "Gold Leaf", "price": 600, "gun": "k9",
                    "desc": "Gilt PDW. The expensive way to be seen.",
                    "roles": {"receiver": (150, 112, 34), "receiver_edge": (208, 168, 62),
                              "receiver_shine": (238, 206, 110), "can": (128, 94, 26),
                              "can_shine": (196, 156, 52), "stock": (140, 102, 32),
                              "stock_knob": (102, 74, 20), "grip": (118, 86, 24),
                              "grip_shine": (188, 150, 50), "mag": (132, 98, 28),
                              "mag_edge": (200, 160, 56), "mag_line": (160, 124, 38)}},
    # ── Pistol ──
    "pistol_standard": {"name": "Issue", "price": 0, "gun": "pistol",
                        "desc": "The service sidearm, matte and worn.",
                        "roles": {}},
    "pistol_parkerized": {"name": "Parkerized", "price": 120, "gun": "pistol",
                          "desc": "Grey phosphate finish, no glare.",
                          "roles": {"frame": (52, 56, 60), "slide": (84, 88, 94),
                                    "slide_edge": (34, 37, 41), "barrel": (96, 100, 106),
                                    "grip": (40, 42, 46)}},
    "pistol_stainless": {"name": "Stainless", "price": 170, "gun": "pistol",
                         "desc": "Bright polished slide.",
                         "roles": {"frame": (140, 146, 154), "slide": (196, 202, 210),
                                   "slide_edge": (104, 110, 118), "barrel": (216, 222, 230),
                                   "grip": (120, 126, 134)}},
    "pistol_brasso": {"name": "Brass Frame", "price": 240, "gun": "pistol",
                      "desc": "Warm metal over the whole frame.",
                      "roles": {"frame": (150, 116, 44), "slide": (198, 164, 72),
                                "slide_edge": (104, 78, 26), "barrel": (214, 182, 96),
                                "grip": (120, 92, 32)}},
    "pistol_redline": {"name": "Redline", "price": 300, "gun": "pistol",
                       "desc": "Black frame, red slide, hot optic.",
                       "roles": {"frame": (26, 26, 30), "slide": (150, 30, 40),
                                 "slide_edge": (60, 12, 18), "barrel": (40, 42, 48),
                                 "grip": (20, 20, 24), "optic": (255, 60, 60)}},
    "pistol_goldleaf": {"name": "Gold Leaf", "price": 600, "gun": "pistol",
                        "desc": "Fully gilt. Matches nothing, goes with anything.",
                        "roles": {"frame": (148, 110, 32), "slide": (212, 172, 62),
                                  "slide_edge": (108, 80, 22), "barrel": (232, 198, 86),
                                  "grip": (120, 88, 26), "optic": (255, 214, 92)}},
}

KIND_BY_PREFIX = (("pal_", "palette"), ("head_", "head"))

FREE_ITEM_IDS = tuple(
    [DEFAULT_PALETTE, DEFAULT_HEAD]
    + [DEFAULT_FINISH_ID % g for g in GUN_KEYS]
)
"""Owned from the first run. Kept in sync with the DEFAULT_* identifiers by
hand deliberately: three constants and a comprehension beats a registry that
has to be built before it can be read."""


def default_appearance():
    """A fresh copy of the default appearance.

    Returned new every call because callers mutate the nested finish dict, and
    a shared module-level default would let one caller repaint everyone else's
    default.
    """
    return {
        "palette": DEFAULT_PALETTE,
        "head": DEFAULT_HEAD,
        "finish": dict((g, DEFAULT_FINISH_ID % g) for g in GUN_KEYS),
    }


DEFAULT = default_appearance()


# ── Identity helpers ────────────────────────────────────────────────────

def item_kind(item_id):
    """'palette' | 'head' | 'finish' | 'os12' | 'k9' | 'pistol' | None.

    A finish's kind is its gun, so the shop can filter a tab by kind without a
    second index.
    """
    if not isinstance(item_id, str):
        return None
    for prefix, kind in KIND_BY_PREFIX:
        if item_id.startswith(prefix):
            return kind
    if item_id in FINISHES:
        return FINISHES[item_id]["gun"]
    return None


def price_of(item_id):
    """Catalog price, or None when the id is not in any catalog."""
    if not isinstance(item_id, str):
        return None
    for table in (PALETTES, HEADGEARS, FINISHES):
        if item_id in table:
            return int(table[item_id]["price"])
    return None


def item_label(item_id):
    """Display name, or the id itself when unknown."""
    for table in (PALETTES, HEADGEARS, FINISHES):
        if item_id in table:
            return table[item_id]["name"]
    return str(item_id)


def item_desc(item_id):
    for table in (PALETTES, HEADGEARS, FINISHES):
        if item_id in table:
            return table[item_id]["desc"]
    return ""


def is_known(item_id):
    return (item_id in PALETTES or item_id in HEADGEARS
            or item_id in FINISHES)


# ── The single validator ────────────────────────────────────────────────

def make(palette=None, head=None, finish=None):
    """Build a normalized appearance from three loose inputs."""
    raw = {"palette": palette, "head": head, "finish": finish}
    return normalize(raw)


def normalize(raw):
    """Coerce anything into a valid appearance. NEVER RAISES.

    One validator serves both callers - the save file and the network - because
    the second rule set would be the first one that drifts. The contract:
    anything we do not recognise becomes the free default for that slot, and a
    bundle that is malformed at the top level is rejected whole rather than
    picked apart.
    """
    try:
        if not isinstance(raw, dict):
            return default_appearance()
        # Reject junk before reading any of its values: a peer that sends a
        # thousand keys is not being inspected, it is being refused.
        if len(raw) > APPEARANCE_MAX_KEYS:
            return default_appearance()

        out = default_appearance()

        pal = _known_id(raw.get("palette"), PALETTES, DEFAULT_PALETTE)
        out["palette"] = pal

        head = _known_id(raw.get("head"), HEADGEARS, DEFAULT_HEAD)
        out["head"] = head

        fin = raw.get("finish")
        if isinstance(fin, dict) and len(fin) <= len(GUN_KEYS):
            for gun in GUN_KEYS:
                want = DEFAULT_FINISH_ID % gun
                fid = _known_id(fin.get(gun), FINISHES, want)
                # A finish bought for the wrong gun is a junk value, not a
                # legal one: os12_blued cannot be worn on the K-9.
                if fid != want and FINISHES[fid]["gun"] != gun:
                    fid = want
                out["finish"][gun] = fid
        return out
    except Exception:
        # Nothing in here is allowed to take a match, a save load, or a render
        # down with it. Same rule the protocol validators follow.
        return default_appearance()


def _known_id(value, table, fallback):
    """Truncate, then test membership in the catalog.

    Membership rather than shape or range: an identifier is valid if and only
    if we sell it. That is what makes an arbitrary colour unrepresentable.
    """
    if not isinstance(value, str):
        return fallback
    value = value[:ID_MAX]
    return value if value in table else fallback


# ── Resolution ──────────────────────────────────────────────────────────

def key_of(app):
    """A cheap canonical string for an appearance.

    Used as the "has this sprite's look changed?" comparison by the arena view,
    which caches one Player per slot and reuses those slots as humans join and
    leave. Comparing dicts is O(n) and awkward to store; this is one str.
    """
    a = normalize(app)
    f = a["finish"]
    return "%s|%s|%s|%s|%s" % (a["palette"], a["head"],
                               f["os12"], f["k9"], f["pistol"])


def resolve(app):
    """Turn an appearance into the RGB role maps the renderer reads.

    Returns {"palette", "head", "finish", "rigs": {gun: {role: rgb}}}. The top
    level carries the resolved body roles; "rigs" carries one merged dict per
    gun. Values are plain tuples so nothing here needs pygame.
    """
    a = normalize(app)
    roles = dict(BASE_ROLES)
    # A palette declares only what it changes. An empty override map - which
    # is exactly pal_olive, the legacy look - therefore yields BASE_ROLES
    # untouched, and the sprite is the one that shipped before this existed.
    for role, rgb in PALETTES[a["palette"]]["roles"].items():
        if role in NON_PALETTE_ROLES:
            continue          # enforced here, not merely documented
        roles[role] = tuple(rgb)

    rigs = {}
    for gun in GUN_KEYS:
        merged = dict(GUN_BASE[gun])
        for role, rgb in FINISHES[a["finish"][gun]]["roles"].items():
            if role in merged:
                merged[role] = tuple(rgb)
        rigs[gun] = merged

    return {"palette": a["palette"], "head": a["head"],
            "finish": a["finish"], "rigs": rigs, **roles}


def catalog_rows(kind):
    """[(item_id, entry)] for one shop tab, cheapest first, defaults marked.

    kind is 'palette', 'head', or a gun key.
    """
    if kind == "palette":
        table, defaults = PALETTES, (DEFAULT_PALETTE,)
    elif kind == "head":
        table, defaults = HEADGEARS, (DEFAULT_HEAD,)
    else:
        table = dict((i, e) for i, e in FINISHES.items() if e["gun"] == kind)
        defaults = (DEFAULT_FINISH_ID % kind,)
    rows = sorted(table.items(), key=lambda kv: (kv[1]["price"], kv[0]))
    return [(i, e, i in defaults) for i, e in rows]
