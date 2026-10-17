"""cast3d.py - 3D (engine3d.Humanoid) looks derived from the 2D cast sheet.

``figure_kit.SPECS`` is the single source of truth for what a cast member
looks like. This module translates a 2D spec into a ``Humanoid`` spec so the
3D rig (M2 sniper, M8 mansion/sniper finale, cast sheets) always matches the
cutscene drawings: same skin/hair/iris colours, hair style, tailoring (shirt,
lapels, tie, buttons, epaulets, medal), long coats, glasses, head bandana,
armband, satchel, cigarette, scar and relative height.

    from cutscenes.cast3d import spec3d, humanoid3d
    hum = humanoid3d("ucilev", rifle="sniper")
    spec = spec3d("vasile", jacket=(30, 30, 30))   # overrides win

Change a look in ``figure_kit.SPECS`` and both renderers follow.
"""
from .figure_kit import SPECS as SPECS_2D

__all__ = ["spec3d", "humanoid3d", "CAST3D_ALIASES"]

_BASE_H = 258.0          # 2D height that maps to Humanoid scale 1.0
_CAP_COL = (19, 29, 46)  # figure_kit draws every peaked cap in this navy
_BUCKLE = (174, 155, 106)
_HAIR = {"curly": "curly", "crop": "crop", "slick": "slick", "swept": "swept",
         "mop": "mop", "messy": "mop", "bald_white": "bald",
         "shag": "shag", "fringe": "fringe", "spiky": "spiky"}
# story names -> figure_kit keys
CAST3D_ALIASES = {"retardovici": "president"}


def _head_w(jaw):
    return 1.0 + max(0.0, jaw - 1.0) * 1.5 + min(0.0, jaw - 1.0) * 0.4


def spec3d(who, **overrides):
    """2D figure_kit spec (or a spec dict) -> Humanoid spec dict."""
    if isinstance(who, dict):
        fk = who
    else:
        fk = SPECS_2D[CAST3D_ALIASES.get(who, who)]
    coat = fk["coat"]
    vest = fk.get("vest")
    out = dict(
        skin=fk["skin"], hair=fk["hair"], jacket=coat, vest=vest,
        pants=fk["trousers"], boots=fk["shoes"], glove=fk.get("glove"),
        accent=fk.get("patch"), iris=fk.get("iris"), ears=True,
        brow_t=fk.get("brow", 2), head_w=_head_w(fk.get("jaw", 1.0)),
        hair_style=_HAIR.get(fk.get("hair_style"), "crop"),
        scale=fk.get("height", _BASE_H) / _BASE_H, bulk=fk.get("bulk", 1.0),
        belt=fk.get("belt"), buckle=_BUCKLE if fk.get("belt") else None,
        stubble_t=.18, pouches=bool(vest), armband=fk.get("armband") or coat, cuff=fk.get("shirt") if vest is None and not fk.get("long_coat") else None,
    )
    neck = fk.get("neck")    # casual wear (hoodie / tee / open shirt): no tailoring decals
    tailoring = () if neck else ("buttons", "epaulets", "medal", "tie", "lapel", "shirt")
    for k in ("stubble", "beard", "cig", "scar", "glasses", "bandana",
              "satchel", "hat") + tailoring:
        if fk.get(k):
            out[k] = fk[k]
    if neck:
        out["cuff"] = None
        if neck == "hood":
            out["hoodie"] = True
        if neck == "open":
            out["inner"] = fk.get("inner", fk["shirt"])
        for k in ("strings", "straps", "sleeves", "print", "plaid", "boots_h", "rips", "sole"):
            if fk.get(k):
                out[k] = fk[k]
        if fk.get("pack"):
            out["backpack"] = fk["pack"]
    elif fk.get("sole"):
        out["sole"] = fk["sole"]
    if fk.get("cap"):
        out["cap"] = _CAP_COL
    if fk.get("long_coat"):
        out["long_coat"] = coat
        out["coat_len"] = 0.56 if fk.get("height", _BASE_H) < 250 else 0.42
    out.update(overrides)
    return out


def humanoid3d(who, **overrides):
    """-> engine3d.Humanoid built from the 2D spec (+ overrides, e.g. rifle=)."""
    from engine3d import Humanoid  # lazy: keep cutscenes importable without the 3D stack
    return Humanoid(spec3d(who, **overrides))
