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

__all__ = ["spec3d", "humanoid3d", "third_person_rifle", "rifle_asset", "ak74_asset",
           "weapon_asset", "RIFLE_ASSETS", "CAST3D_ALIASES"]

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


_RIFLE_CACHE = {}
# Baked ae.mesh/1 weapons a spec may name directly. All share one gun-space
# frame: +z is the muzzle and the origin is the right hand on the pistol grip,
# so they drop into ``Humanoid._rifle`` without a transform.
RIFLE_ASSETS = ("akrifle", "ak74")


def weapon_asset(name):
    """(mesh, muzzle) of a baked ae.mesh/1 weapon in RIFLE_ASSETS, grip at the
    hand joint and +z muzzle; (None, None) if the asset is missing or corrupt.
    Loaded once and shared: the rig only ever reads the mesh."""
    if name not in _RIFLE_CACHE:
        out = (None, None)
        try:
            import json
            import os
            from engine3d.core import Mesh
            from game.render3d_bridge import MESHES_DIR
            with open(os.path.join(MESHES_DIR, "%s.mesh.json" % name), encoding="utf-8") as fh:
                data = json.load(fh)
            if data.get("schema") == "ae.mesh/1":
                m = Mesh()
                m.verts = [tuple(float(c) for c in v) for v in data["verts"]]
                m.faces = [(tuple(f[0]), tuple(f[1]), 2, True, False) for f in data["faces"]]
                out = (m, tuple(float(c) for c in data["meta"]["muzzle"]))
        except Exception:
            pass
        _RIFLE_CACHE[name] = out
    return _RIFLE_CACHE[name]


def rifle_asset():
    """(mesh, muzzle) of the shared Guard rifle (tools/ae_import_akrifle.py)."""
    return weapon_asset("akrifle")


def ak74_asset():
    """(mesh, muzzle) of the code-authored AK-74 (tools/ae_build_ak74.py)."""
    return weapon_asset("ak74")


def _attach(hum, name):
    """Put the baked weapon ``name`` on ``hum`` as its rig rifle."""
    mesh, muzzle = weapon_asset(name)
    if mesh is None:
        return hum          # missing asset -> the procedural rifle stays
    hum._rifle = mesh
    hum._weapon = name
    hum._muzzle_z = muzzle[2]
    # GL caches rig templates by spec repr; each gun needs its own, or it
    # reuses the procedural box-rifle VBO.
    hum._gl_spec_key = repr(sorted((getattr(hum, "spec", None) or {}).items())) + "|" + name
    return hum


def third_person_rifle(hum):
    """Swap a plain ``rifle`` rig's box gun for the shared AK asset and return it.

    A spec may also name a baked weapon directly (``rifle="ak74"``).  Anything
    else is left alone: sniper / os12 / shotgun / k9 (and any rig that already
    carries a custom ``_weapon``) keep their own mesh.  Missing asset -> the
    procedural rifle stays, so every scene still renders.
    """
    spec = getattr(hum, "spec", None) or {}
    want = spec.get("rifle")
    if getattr(hum, "_weapon", None) or want not in ("rifle",) + RIFLE_ASSETS:
        return hum
    return _attach(hum, want if want in RIFLE_ASSETS else "akrifle")


def humanoid3d(who, **overrides):
    """-> engine3d.Humanoid built from the 2D spec (+ overrides, e.g. rifle=)."""
    from engine3d import Humanoid  # lazy: keep cutscenes importable without the 3D stack
    return third_person_rifle(Humanoid(spec3d(who, **overrides)))
