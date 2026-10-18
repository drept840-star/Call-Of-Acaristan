"""outfits.py - Biribel's Mission 5 kit, as data (one source of truth).

M5 story: KRAP is folded into the Presidential Guard and Biribel is forced
into the President's black at the ``m5x_change`` intro beat. From then on he
wears it in every M5 view: 3D cutscenes (cast3d.humanoid3d overrides), 2D
fallbacks / portraits (figure_kit wardrobe overrides) and the top-down
gameplay sprite (appearance role overlay). Outside M5 nothing changes.

IDENTITY MARKER (readability rule - he must never read as a Guard enemy):
he keeps the KRAP-blue patch. In the change beat he tears it off the old
vest and presses it onto the new black one, and he leaves the Guard helmet
on the bench. So:
  * 3D / 2D / portrait: bare curly head (every Guard wears a helmet or a
    black beret) + a bright KRAP-blue chest patch where Guards carry red.
  * Gameplay: a KRAP-blue shoulder yoke across BOTH shoulders. Guard
    troopers only have a short red band on one sleeve. The yoke is a
    different SHAPE as well as a different hue, and GAMEPLAY_MARK is much
    lighter than the Guard red (luma ~150 vs ~65), so it separates in
    grayscale too.

Dependency-free on purpose (no pygame, no game imports): cutscenes, the
player sprite and missions all import it without creating cycles.
"""

OUTFIT_KRAP = "krap"
OUTFIT_GUARD = "guard"
OUTFITS = (OUTFIT_KRAP, OUTFIT_GUARD)

M5_MISSION_KEY = "MISSION5"       # mirrors missions.m5.meta.MISSION5_KEY
M6_MISSION_KEY = "MISSION6"       # after the change: Guard black is his uniform

# ── THE Guard kit palette (single source of truth; every view below reads it) ──
# Neutral blacks on purpose: R≈G≈B. A blue-leaning "black" (the old gameplay
# uniform was (50, 51, 58)) turns navy under the M5 night ambient, which is
# blue-dominant outdoors - that is how Biribel ended up reading KRAP blue.
GUARD_KIT = {
    "black": (26, 26, 28),       # jacket / coat / beret
    "lapel": (19, 19, 21),
    "shirt": (44, 44, 46),
    "vest": (38, 38, 41),
    "pants": (30, 30, 32),
    "armband": (176, 36, 36),    # the decree armband he was issued (red, not blue)
    "mark": (70, 118, 196),      # the kept KRAP patch: lifted blue, reads on black
}
GUARD_BLACK = GUARD_KIT["black"]
GUARD_VEST = GUARD_KIT["vest"]
GUARD_PANTS = GUARD_KIT["pants"]
GUARD_ARMBAND = GUARD_KIT["armband"]
KRAP_MARK = GUARD_KIT["mark"]

# ── 3D (cast3d.humanoid3d overrides) ──
# "krap_armband": the decree/squadmate look - own kit, Guard armband only.
# The Guard entry overrides EVERY cloth key spec3d copies from figure_kit
# (jacket, vest, pants, lapel, shirt) so nothing of the old kit leaks through.
BIRIBEL_3D = {
    OUTFIT_KRAP: {},
    "krap_armband": {"armband": GUARD_ARMBAND},
    OUTFIT_GUARD: {"jacket": GUARD_BLACK, "vest": GUARD_VEST, "pants": GUARD_PANTS,
                   "lapel": GUARD_KIT["lapel"], "shirt": GUARD_KIT["shirt"],
                   "armband": GUARD_ARMBAND, "accent": KRAP_MARK, "pouches": True},
}

# ── 2D (figure_kit wardrobe overrides; SPECS keys) ──
BIRIBEL_2D = {
    OUTFIT_KRAP: {},
    "krap_armband": {"armband": GUARD_ARMBAND},
    OUTFIT_GUARD: {"coat": GUARD_BLACK, "lapel": GUARD_KIT["lapel"], "shirt": GUARD_KIT["shirt"],
                   "vest": GUARD_VEST, "trousers": GUARD_PANTS,
                   "armband": GUARD_ARMBAND, "patch": KRAP_MARK},
}

# ── gameplay (core.appearance role overlay; skin is never touched) ──
# Every palette role is listed (helmet/eyes too: the shop palettes recolour
# them, and an unlisted role used to keep the SAVED look - e.g. KRAP Slate's
# blue helmet arc). Any role added later inherits GAMEPLAY_FALLBACK, never
# the saved palette. Values are a touch lifted over GUARD_KIT so the sprite
# still separates from dark floors at ~32 px.
GAMEPLAY_ROLES = {
    OUTFIT_GUARD: {"uniform": (40, 40, 43), "helmet": (24, 24, 26),
                   "helmet_arc": (40, 40, 43), "helmet_rim": (30, 30, 32),
                   "eyes": (24, 18, 14), "kevlar": (32, 32, 35),
                   "kevlar_edge": (60, 60, 64), "kevlar_line": (22, 22, 24),
                   "kevlar_ridge": (42, 42, 45),
                   # 1 px rim on torso + sleeves (player.draw reads it only when
                   # present): black cloth must not vanish on black M5 floors,
                   # or the hands + gun float off the body (polish Task 4)
                   "cloth_edge": (68, 68, 72),
                   "hair": (25, 30, 28)},      # figure_kit SPECS["biribel"]["hair"]
}
GAMEPLAY_FALLBACK = {OUTFIT_GUARD: GUARD_BLACK}
# Bare curly head - never the saved helmet, and NOT a black beret: every M5
# Guard trooper sprite wears the black beret (missions/m5/draw.py C_M5_BERET,
# art/m5/m5_guard.py), so a beret would make him read as an enemy. Matches
# the bare head of the 3D/2D cutscene rig. (entities.adornments draw id)
GAMEPLAY_HEAD = {OUTFIT_GUARD: "head_bare_curly"}
# lifted further than KRAP_MARK: at ~32 px top-down it must out-value the
# Guard red (luma ~150 vs ~65) or it vanishes in grayscale
GAMEPLAY_MARK = (104, 158, 236)

# Scenes that play BEFORE the change keep his own kit (the change is forced,
# not chosen). m5x_change handles both looks itself; every other M5 scene
# with Biribel in it is after the change.
_PRE_CHANGE = {"m5_safehouse_tv": OUTFIT_KRAP, "m5x_decree": "krap_armband",
               "m5x_squadmate": "krap_armband"}


def scene_outfit(scene):
    """Outfit Biribel wears in an M5 cutscene ``scene``."""
    return _PRE_CHANGE.get(scene, OUTFIT_GUARD)


def biribel_3d(outfit):
    return dict(BIRIBEL_3D.get(outfit, BIRIBEL_3D[OUTFIT_KRAP]))


def biribel_2d(outfit):
    return dict(BIRIBEL_2D.get(outfit, BIRIBEL_2D[OUTFIT_KRAP]))


def gameplay_outfit(state):
    """The outfit the player sprite should wear right now.

    Guard black from Mission 5's change onward (M5 and M6).  Anything else
    (other missions, menus, multiplayer) -> None = the saved look."""
    mission = getattr(state, "active_mission", None)
    if mission == M6_MISSION_KEY:
        return OUTFIT_GUARD
    if mission != M5_MISSION_KEY:
        return None
    o = getattr(state, "m5_outfit", OUTFIT_KRAP)
    return o if o in GAMEPLAY_ROLES else None


def overlay_roles(rk, outfit):
    """Resolved appearance roles ``rk`` with the outfit's roles on top.
    Returns a NEW dict; the saved/resolved appearance is never mutated."""
    over = GAMEPLAY_ROLES.get(outfit)
    if not over:
        return rk
    fallback = tuple(GAMEPLAY_FALLBACK.get(outfit, GUARD_BLACK))
    out = dict(rk)
    for role, val in rk.items():
        if role == "skin" or role in over:
            continue
        if _is_rgb(val):          # an unknown colour role: black, not the saved palette
            out[role] = fallback
    for role, rgb in over.items():
        if role != "skin":
            out[role] = tuple(rgb)
    return out


def gameplay_head(outfit, saved_head):
    """Headgear id the sprite draws: the outfit's (Guard: black beret) or the
    saved choice when no story outfit is active."""
    return GAMEPLAY_HEAD.get(outfit, saved_head) if outfit else saved_head


def _is_rgb(val):
    return (isinstance(val, tuple) and len(val) == 3
            and all(isinstance(c, int) for c in val))
