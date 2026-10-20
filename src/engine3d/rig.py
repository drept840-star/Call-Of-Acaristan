"""Low-poly humanoid rig: boxes on a joint hierarchy, posed by angle dicts.

Pose keys (degrees unless noted) - anything missing falls back to NEUTRAL:
  spine, spine_r, twist      torso lean fwd / side lean / twist
  head_p, head_y             nod down / turn
  lsh_p, lsh_r, lel          left shoulder raise fwd / out, elbow bend
  rsh_p, rsh_r, rel          right ...
  lhip_p, lhip_r, lkn        left thigh raise fwd / out, knee bend
  rhip_p, rhip_r, rkn
  lank, rank                 ankle point (+ = toes away from the shin); lying
                             bodies need it or the heel props them off the floor
  body_p, body_r             whole-body pitch (+fwd, 90 = face down) / roll
  lift                       metres above auto ground contact (jumps/dives)
  rifle_p, rifle_y           rifle pitch (+ = muzzle down) / yaw vs body
"""
import math

from .core import (M_IDENT, Mesh, _orient_outward, box, lerp, m_apply, m_mul,
                   rot_x, rot_y, rot_z, v_add)

__all__ = ["NEUTRAL", "POSES", "EXPRESSIONS", "blend", "Humanoid", "rifle_mesh",
           "os12_mesh", "pose_run", "pose_drag", "pose_crawl", "SLOTS", "PART_FB",
           "solve_look", "mouth_flap"]

NEUTRAL = dict(spine=3, spine_r=0, twist=0, head_p=0, head_y=0,
               lsh_p=8, lsh_r=8, lel=12, rsh_p=8, rsh_r=8, rel=12,
               lhip_p=0, lhip_r=2, lkn=2, rhip_p=0, rhip_r=2, rkn=2,
               lank=0, rank=0, body_p=0, body_r=0, lift=0.0, rifle_p=60, rifle_y=0)

POSES = {
    "stand": dict(),
    "ready": dict(spine=6, lsh_p=48, lsh_r=6, lel=62, rsh_p=22, rsh_r=14, rel=58, rifle_p=28,
                  lhip_p=4, rhip_p=-3, lkn=6, rkn=4),
    "aim": dict(spine=8, head_p=6, lsh_p=78, lsh_r=4, lel=34, rsh_p=58, rsh_r=30, rel=88,
                rifle_p=2, lhip_p=8, rhip_p=-6, lkn=10, rkn=6),
    "radio": dict(spine=4, head_p=4, head_y=-12, lsh_p=40, lsh_r=60, lel=150,
                  rsh_p=22, rsh_r=14, rel=58, rifle_p=30),
    "talk_turn": dict(spine=5, head_y=-20, twist=-14, lsh_p=40, lsh_r=60, lel=148,
                      rsh_p=20, rsh_r=14, rel=56, rifle_p=32, lhip_p=4, rkn=6),
    "crouch": dict(spine=34, head_p=-18, lhip_p=96, lkn=128, rhip_p=84, rkn=132,
                   lsh_p=40, lel=70, rsh_p=30, rsh_r=16, rel=72, rifle_p=40),
    "cover": dict(spine=22, head_p=-6, lhip_p=104, lkn=140, rhip_p=-6, rkn=112, rhip_r=10,
                  lsh_p=34, lsh_r=12, lel=96, rsh_p=26, rsh_r=18, rel=88, rifle_p=70),
    "cover_tight": dict(spine=38, head_p=22, lhip_p=118, lkn=150, rhip_p=110, rkn=150,
                        lsh_p=70, lsh_r=6, lel=128, rsh_p=66, rsh_r=6, rel=130, rifle_p=70),
    "kneel": dict(spine=14, lhip_p=88, lkn=92, rhip_p=-8, rkn=104, lsh_p=34, lel=60,
                  rsh_p=26, rsh_r=14, rel=64, rifle_p=40),
    "kneel_over": dict(spine=52, head_p=24, lhip_p=96, lkn=100, rhip_p=-4, rkn=100,
                       lsh_p=74, lsh_r=10, lel=30, rsh_p=72, rsh_r=10, rel=30, rifle_p=90),
    "dive": dict(body_p=62, spine=10, lhip_p=-12, lkn=40, rhip_p=10, rkn=30, lsh_p=150,
                 lel=20, rsh_p=140, rel=30, lift=0.25, rifle_p=0),
    "prone": dict(body_p=88, spine=-6, head_p=-34, lhip_p=-4, lkn=6, rhip_p=4, rhip_r=12,
                  rkn=18, lsh_p=150, lsh_r=18, lel=70, rsh_p=140, rsh_r=24, rel=70, rifle_p=0),
    # Lying poses are solved so the torso rests on the floor: a bent elbow or
    # a heel under the body props it up and it reads as floating.
    "dead_back": dict(body_p=-88, body_r=4, spine=0, head_p=-4, head_y=20, lsh_p=-18,
                      lsh_r=62, lel=24, rsh_p=40, rsh_r=40, rel=50, lhip_p=10, lhip_r=10,
                      lkn=18, rhip_p=4, rhip_r=16, rkn=10),
    "dead_front": dict(body_p=89, spine=3, head_p=-26, head_y=70, lsh_p=-12, lsh_r=70, lel=44,
                       rsh_p=-20, rsh_r=24, rel=20, lhip_p=-6, lhip_r=12, lkn=30, rhip_p=4,
                       rhip_r=4, rkn=10),
    "dead_side": dict(body_p=12, body_r=84, spine=4, head_p=40, head_y=-30, lsh_p=6,
                      lsh_r=175, lel=30, rsh_p=90, rsh_r=6, rel=20, lhip_p=30, lhip_r=0,
                      lkn=80, rhip_p=30, rkn=60),
    "slump": dict(spine=70, head_p=40, lhip_p=96, lkn=150, rhip_p=96, rkn=150, lsh_p=10,
                  lsh_r=4, lel=20, rsh_p=8, rsh_r=6, rel=20, rifle_p=90),
    "reach_radio": dict(body_p=72, spine=-10, head_p=-40, lsh_p=170, lsh_r=10, lel=10,
                        rsh_p=95, rsh_r=40, rel=80, lhip_p=40, lkn=90, rhip_p=10, rkn=40,
                        rhip_r=14),
    "mayday": dict(body_p=66, spine=-14, head_p=-46, head_y=-18, lsh_p=110, lsh_r=70, lel=150,
                   rsh_p=150, rsh_r=20, rel=40, lhip_p=40, lkn=90, rhip_p=10, rkn=40,
                   rhip_r=14),
    "drag": dict(spine=40, head_p=-30, lsh_p=70, lsh_r=4, lel=20, rsh_p=70, rsh_r=4, rel=20,
                 lhip_p=60, lkn=90, rhip_p=40, rkn=70),
    "carried": dict(body_p=-70, spine=-12, head_p=-46, head_y=20, lsh_p=170, lsh_r=10, lel=4,
                    rsh_p=170, rsh_r=10, rel=6, lhip_p=6, lkn=14, rhip_p=-2, rkn=8),
}


# Face expressions (P11 step 8): parametric deltas over the neutral face
# built from each cast spec - brow lift/tilt, eye height, mouth width,
# corner curve (+ smile / - frown) and a resting mouth opening. Hosts add
# animated mouth_open on top while a character speaks (dialogue data).
EXPRESSIONS = {
    "neutral":   dict(brow_y=0.0, brow_tilt=0.0, eye_h=1.0, mouth_w=1.0,
                      mouth_curve=0.0, mouth_open=0.0),
    "smile":     dict(brow_y=0.002, brow_tilt=-7.0, eye_h=0.8, mouth_w=1.18,
                      mouth_curve=0.009, mouth_open=0.0),
    "grin":      dict(brow_y=0.003, brow_tilt=-8.0, eye_h=0.78, mouth_w=1.25,
                      mouth_curve=0.008, mouth_open=0.35),
    "angry":     dict(brow_y=-0.008, brow_tilt=22.0, eye_h=0.78, mouth_w=0.9,
                      mouth_curve=-0.005, mouth_open=0.0),
    "stern":     dict(brow_y=-0.004, brow_tilt=10.0, eye_h=0.9, mouth_w=0.92,
                      mouth_curve=-0.003, mouth_open=0.0),
    "sad":       dict(brow_y=0.004, brow_tilt=-13.0, eye_h=0.88, mouth_w=0.9,
                      mouth_curve=-0.006, mouth_open=0.0),
    "surprised": dict(brow_y=0.012, brow_tilt=-5.0, eye_h=1.3, mouth_w=0.8,
                      mouth_curve=0.0, mouth_open=0.55),
    "worried":   dict(brow_y=0.006, brow_tilt=-11.0, eye_h=1.05, mouth_w=0.95,
                      mouth_curve=-0.004, mouth_open=0.12),
}


def mouth_flap(t_ms: int, seed: int = 0) -> float:
    """Deterministic talking mouth opening 0..1 (closed-form, seeded)."""
    ph = (t_ms + seed * 137) % 360
    v = math.sin(ph * 0.11) * 0.5 + math.sin(ph * 0.043 + 1.7) * 0.5
    return max(0.0, min(1.0, 0.25 + v * 0.75))


def solve_look(eye, target, body_yaw_deg: float):
    """Clamped head yaw/pitch (degrees) aiming the head at ``target``.

    Yaw clamps to +-38 deg, pitch to -14 (up) .. +30 (down); returns
    (head_y, head_p) pose values. Smoothing is the caller's job.
    """
    dx, dy, dz = (target[0] - eye[0], target[1] - eye[1], target[2] - eye[2])
    dist_xz = math.hypot(dx, dz)
    if dist_xz < 1e-6 and abs(dy) < 1e-6:
        return 0.0, 0.0
    want_yaw = math.degrees(math.atan2(dx, dz)) - body_yaw_deg
    want_yaw = (want_yaw + 180.0) % 360.0 - 180.0
    want_pitch = math.degrees(math.atan2(-dy, max(dist_xz, 1e-6)))
    return (max(-38.0, min(38.0, want_yaw)),
            max(-14.0, min(30.0, want_pitch)))


def blend(a, b, t):
    if isinstance(a, str):
        a = POSES[a]
    if isinstance(b, str):
        b = POSES[b]
    out = {}
    for k, d in NEUTRAL.items():
        out[k] = lerp(a.get(k, d), b.get(k, d), t)
    return out


def pose_run(phase, lean=16):
    s = math.sin(phase)
    c = math.cos(phase)
    return dict(spine=lean, head_p=-8, lhip_p=40 * s + 10, rhip_p=-40 * s + 10,
                lkn=20 + 60 * max(0.0, -c), rkn=20 + 60 * max(0.0, c),
                lsh_p=-30 * s + 20, lel=80, rsh_p=30 * s + 20, rel=80, rsh_r=12, lsh_r=8,
                lift=0.05 * abs(s), rifle_p=50)


def pose_drag(phase):
    s = math.sin(phase)
    return dict(spine=42, head_p=-34, lsh_p=72, lsh_r=6, lel=18, rsh_p=72, rsh_r=6, rel=18,
                lhip_p=62 + 16 * s, lkn=96 + 12 * s, rhip_p=50 - 16 * s, rkn=86 - 12 * s)


def pose_crawl(phase):
    s = math.sin(phase)
    return dict(body_p=86, spine=-6, head_p=-36, lsh_p=150 + 20 * s, lsh_r=24, lel=70 - 30 * s,
                rsh_p=150 - 20 * s, rsh_r=24, rel=70 + 30 * s, lhip_p=10 + 25 * s, lhip_r=18,
                lkn=40 + 30 * s, rhip_p=10 - 25 * s, rhip_r=18, rkn=40 - 30 * s, rifle_p=0)


def rifle_mesh(col=(26, 28, 30), scope=False, accent=(60, 62, 58)):
    from .core import Mesh
    m = Mesh()
    m.add(box(0.06, 0.09, 0.52, col, center=(0, 0, 0.14)))
    m.add(box(0.03, 0.03, 0.36, (18, 18, 20), center=(0, 0.015, 0.58)))
    m.add(box(0.055, 0.12, 0.24, accent, center=(0, -0.025, -0.22)))
    m.add(box(0.045, 0.15, 0.07, col, center=(0, -0.1, 0.16)))
    if scope:
        m.add(box(0.045, 0.055, 0.22, (14, 14, 16), center=(0, 0.08, 0.12)))
    return m


def os12_mesh():
    """OS-12 'Tiss' (OTs-12): compact AKS-74U-pattern carbine - stubby barrel
    with a fat cylindrical muzzle can, slim dark handguard, AK receiver with a
    ribbed dust cover and rear-sight block, curved steel mag, polymer pistol
    grip and a side-folding skeleton stock (shown extended).
    Same frame as rifle_mesh(): +z = muzzle, origin = right hand."""
    from .core import Mesh
    m = Mesh()
    steel, dark, poly, wood = (40, 42, 45), (20, 21, 23), (30, 26, 22), (58, 40, 26)

    def ob(w, h, d, col, c, rx=0.0):
        m.add(box(w, h, d, col), m=rot_x(rx), t=c)

    # receiver + dust cover (ribbed) + rear trunnion
    ob(0.050, 0.075, 0.30, steel, (0, -0.005, 0.06))
    ob(0.046, 0.022, 0.27, dark, (0, 0.042, 0.05))
    for i in range(4):
        ob(0.048, 0.006, 0.012, steel, (0, 0.054, -0.04 + i * 0.05))
    ob(0.030, 0.030, 0.045, dark, (0, 0.050, 0.205))        # rear sight / hinge block
    ob(0.008, 0.016, 0.10, steel, (0.029, 0.010, 0.06))     # selector lever (right side)
    # handguard: lower polymer + upper gas-tube cover
    ob(0.056, 0.050, 0.15, poly, (0, -0.010, 0.29))
    ob(0.040, 0.026, 0.15, dark, (0, 0.034, 0.29))
    # front trunnion, short barrel, front sight, big muzzle can
    ob(0.034, 0.040, 0.040, steel, (0, 0.005, 0.385))
    ob(0.024, 0.024, 0.08, dark, (0, 0.005, 0.44))
    ob(0.012, 0.046, 0.014, dark, (0, 0.040, 0.405))
    ob(0.050, 0.050, 0.15, dark, (0, 0.005, 0.555))
    ob(0.056, 0.056, 0.020, steel, (0, 0.005, 0.49))
    ob(0.054, 0.054, 0.012, steel, (0, 0.005, 0.632))
    # curved magazine (3 segments sweeping forward)
    ob(0.032, 0.070, 0.070, steel, (0, -0.075, 0.135), rx=-6)
    ob(0.032, 0.070, 0.068, steel, (0, -0.138, 0.152), rx=-18)
    ob(0.032, 0.066, 0.064, steel, (0, -0.196, 0.180), rx=-32)
    # trigger guard + pistol grip
    ob(0.012, 0.010, 0.08, dark, (0, -0.062, 0.045))
    ob(0.038, 0.115, 0.052, poly, (0, -0.095, -0.005), rx=16)
    # side-folding skeleton stock, extended
    ob(0.016, 0.016, 0.26, steel, (0, 0.022, -0.21))
    ob(0.016, 0.016, 0.27, steel, (0, -0.046, -0.215), rx=-9)
    ob(0.026, 0.135, 0.030, steel, (0, -0.020, -0.345))
    ob(0.030, 0.140, 0.012, dark, (0, -0.020, -0.362))
    return m


def cbox(w, h, d, col, center=(0.0, 0.0, 0.0), cols=None, bevel=0.02, skip=(),
         emissive=False, layer=2):
    """Box with its four vertical edges chamfered: an octagonal prism along y.

    Same side names as ``core.box`` (front = -z, back = +z, left = -x,
    right = +x, top, bottom) plus ``chamfer`` for the four bevel facets.  The
    bottom cap is exactly the box's bottom, so swapping a ``box`` for a
    ``cbox`` never moves a part's lowest vertex (ground contact is unchanged).
    """
    cx, cy, cz = center
    hx, hz = w / 2.0, d / 2.0
    b = max(0.0, min(bevel, hx * 0.9, hz * 0.9))
    cols = cols or {}
    y0, y1 = cy - h / 2.0, cy + h / 2.0
    prof = [(-hx + b, -hz), (hx - b, -hz), (hx, -hz + b), (hx, hz - b),
            (hx - b, hz), (-hx + b, hz), (-hx, hz - b), (-hx, -hz + b)]
    names = ("front", "chamfer", "right", "chamfer", "back", "chamfer",
             "left", "chamfer")
    m = Mesh()
    for i, name in enumerate(names):
        if name in skip:
            continue
        (xa, za), (xb, zb) = prof[i], prof[(i + 1) % 8]
        m.face([(cx + xa, y0, cz + za), (cx + xb, y0, cz + zb),
                (cx + xb, y1, cz + zb), (cx + xa, y1, cz + za)],
               cols.get(name, col), layer, False, emissive)
    if "top" not in skip:
        m.face([(cx + x, y1, cz + z) for x, z in prof],
               cols.get("top", col), layer, False, emissive)
    if "bottom" not in skip:
        m.face([(cx + x, y0, cz + z) for x, z in prof],
               cols.get("bottom", col), layer, False, emissive)
    return _orient_outward(m)


class Humanoid:
    """spec keys: skin hair jacket vest pants boots accent glove
    extras: ponytail stubble beanie pack helmet ghillie rifle (None|'rifle'|'os12'|'sniper')
            hair_style (crop|curly|slick|swept|mop/messy|shag|fringe|spiky|bald) brows ('thick') brow_t (1-5)
            bandana (head cloth w/ knot + tails) mask (lower-face cloth) armband glasses
            beret cap hat moustache beard eyes iris (adds sclera) ears scar cig
            head_w (head width scale)  scale (overall height, 1.0 = 258 2D units)
            detail ('hd': chamfered limbs, split coat panels, hands, boots, brow/cheek/chin)
            wound (1-3: exit wound on the chest + back entry, spreading stain)
            blood_hands (True: red glove/wrist)
            bulk (torso width)  vest=None -> tailored chest: shirt lapel tie buttons
            medal epaulets  long_coat coat_len  belt (None = no belt) buckle pouches
            satchel cuff.  casual: hoodie strings backpack straps sleeves('short')
            inner (open-shirt tee) print(('drip'|'stripe', col[, white])) plaid
            boots_h rips sole; hair_style also shag|fringe|spiky.
            cutscenes.cast3d builds these from figure_kit.SPECS."""

    def __init__(self, spec):
        self.spec = spec
        self._expression = str(spec.get("expression", "neutral"))
        self._mouth_open = float(spec.get("mouth_open", 0.0) or 0.0)
        self._parts = None
        self._rifle = None
        if spec.get("rifle"):
            kind = spec["rifle"]
            if kind == "sniper":
                from .core import Mesh
                m = rifle_mesh(scope=True)
                m.add(box(0.03, 0.03, 0.55, (14, 14, 16), center=(0, 0.015, 0.95)))
                self._rifle = m
            else:
                self._rifle = os12_mesh() if kind == "os12" else rifle_mesh()
        self._build_parts()

    def _face_parts(self):
        """Face + face2 decal meshes for the current expression/mouth.

        Colours and features come from the cast spec; EXPRESSIONS deltas
        move brows/eyes/mouth (P11 step 8). Rebuilt by set_expression().
        """
        s = self.spec
        skin, hair = s["skin"], s["hair"]
        flat = ("front", "left", "right", "top", "bottom")
        exp = EXPRESSIONS.get(self._expression, EXPRESSIONS["neutral"])
        open_h = max(0.0, min(1.0, exp["mouth_open"] + self._mouth_open))
        eye = s.get("eyes", (22, 18, 16))
        # Face details are flat decals on the face plane (front side only, so
        # they cull from behind) drawn with a small depth bias. As full boxes
        # they tied with the skull in the painter sort and one eye would
        # vanish whenever the head turned.
        hw = s.get("head_w", 1.0)
        bt = s.get("brow_t")
        thick = s.get("brows") == "thick"
        brow = hair if (thick or bt) else mix(hair, skin, .3)
        if bt:
            bw, bh = 0.058, 0.008 + 0.0035 * bt
        else:
            bw, bh = (0.062, 0.024) if thick else (0.05, 0.014)
        face, face2 = [], []        # face2 = details on top (iris, glasses, scar...)
        eh = exp["eye_h"]
        if s.get("iris"):        # 2D-style eye: sclera + coloured iris
            for exx in (-0.048, 0.048):
                face.append(box(0.046, 0.026 * eh, 0.004, s.get("sclera", (222, 214, 196)),
                                center=(exx, 0.148, 0.122), skip=flat))
                face2 += [box(0.022, 0.026 * eh, 0.004, s["iris"], center=(exx, 0.148, 0.1235), skip=flat),
                          box(0.046, 0.007, 0.004, mix(skin, (0, 0, 0), .35),
                              center=(exx, 0.164, 0.1235), skip=flat)]
        else:
            face += [box(0.04, 0.03 * eh, 0.004, eye, center=(-0.048, 0.148, 0.122), skip=flat),
                     box(0.04, 0.03 * eh, 0.004, eye, center=(0.048, 0.148, 0.122), skip=flat)]
        for bx in (-0.05, 0.05):
            bm = Mesh()
            bm.add(box(bw, bh, 0.004, brow, skip=flat),
                   m=rot_z(-exp["brow_tilt"] if bx < 0 else exp["brow_tilt"]),
                   t=(bx, 0.18 + exp["brow_y"], 0.122))
            face.append(bm)
        masked = s.get("mask")
        if not masked:
            mc = mix(skin, (60, 20, 20), .35)
            curve, mw = exp["mouth_curve"], 0.07 * exp["mouth_w"]
            if curve == 0.0 and open_h <= 0.001:
                face.append(box(0.07, 0.014, 0.004, mc, center=(0, 0.06, 0.122), skip=flat))
            else:
                face.append(box(mw * 0.52, 0.011, 0.004, mc,
                                center=(0, 0.06, 0.122), skip=flat))
                for sx_ in (-1, 1):
                    face.append(box(mw * 0.3, 0.009, 0.004, mc,
                                    center=(sx_ * mw * 0.38, 0.06 + curve, 0.122),
                                    skip=flat))
                if open_h > 0.001:
                    face.append(box(mw * 0.55, 0.006 + 0.026 * open_h, 0.004,
                                    (52, 22, 20), center=(0, 0.055, 0.1215),
                                    skip=flat))
        if s.get("glasses"):
            gc = s["glasses"]
            gz = 0.1248
            for gx in (-0.048, 0.048):
                face2 += [box(0.058, 0.008, 0.004, gc, center=(gx, 0.17, gz), skip=flat),
                         box(0.058, 0.008, 0.004, gc, center=(gx, 0.126, gz), skip=flat),
                         box(0.008, 0.05, 0.004, gc, center=(gx - 0.027, 0.148, gz), skip=flat),
                         box(0.008, 0.05, 0.004, gc, center=(gx + 0.027, 0.148, gz), skip=flat)]
            face2.append(box(0.02, 0.006, 0.004, gc, center=(0, 0.16, gz), skip=flat))
        if s.get("scar"):
            m = Mesh()
            m.add(box(0.01, 0.13, 0.004, mix(skin, (70, 30, 30), .4), skip=flat),
                  m=rot_z(-24), t=(0.045, 0.16, 0.1242))
            face2.append(m)
        if s.get("moustache"):
            face2.append(box(0.085, 0.022, 0.004, s["moustache"], center=(0, 0.078, 0.1222), skip=flat))
        if s.get("creases"):        # age: forehead line, nasolabial folds, eye bags
            # Soft, skin-toned creases: at cutscene resolution hard dark lines
            # read as a box drawn around the mouth, so keep them subtle.
            cc = mix(skin, s["creases"], .55)
            face2.append(box(0.09, 0.005, 0.004, cc, center=(0, 0.214, 0.1232), skip=flat))
            for sx_ in (-1, 1):
                m = Mesh()
                m.add(box(0.005, 0.034, 0.004, cc, skip=flat), m=rot_z(sx_ * -22),
                      t=(sx_ * 0.052, 0.094, 0.1232))
                face2.append(m)
                face2.append(box(0.03, 0.005, 0.004, mix(skin, cc, .6),
                                 center=(sx_ * 0.048, 0.13, 0.1232), skip=flat))
        if s.get("beard"):
            face.append(box(0.19, 0.1, 0.003, s["beard"], center=(0, 0.04, 0.1212), skip=flat))
        elif s.get("stubble") and not masked:
            # shadow along the jaw/chin only (a full rectangle read as a box
            # drawn around the mouth), and kept close to the skin tone
            st = mix(skin, hair, min(.3, s.get("stubble_t", .22)))
            face.append(box(0.17, 0.03, 0.003, st, center=(0, 0.022, 0.121), skip=flat))
            face.append(box(0.08, 0.016, 0.003, st, center=(0, 0.082, 0.121), skip=flat))
        if s.get("cig") and not s.get("cig_dropped"):
            # Held in the mouth corner and pointing forward/down, so it reads as
            # *in* the lips from the front instead of floating beside the cheek.
            # Clamped in the mouth *corner* (mouth line spans x=+-0.035 at
            # y=0.06), drooping 12 deg and yawed 18 deg outward - the old one
            # sat on the centre line right under the nose. Butt is buried in
            # the lip (z<0.12); positions are butt + dir * distance. It lives
            # in face2 so the depth bias keeps it in front of the skull box
            # (in 'head' the painter sort hid the paper in 3/4 views).
            m = Mesh()
            cm = m_mul(rot_y(18), rot_x(12))
            m.add(box(0.0145, 0.0145, 0.016, (196, 140, 80)), m=cm, t=(0.0364, 0.0563, 0.1254))
            m.add(box(0.0115, 0.0115, 0.056, (236, 232, 222)), m=cm, t=(0.0473, 0.0488, 0.1589))
            m.add(box(0.0135, 0.0135, 0.006, (120, 114, 108)), m=cm, t=(0.0567, 0.0424, 0.1878))
            m.add(box(0.014, 0.014, 0.006, (255, 120, 40), emissive=True), m=cm,
                  t=(0.0585, 0.0412, 0.1933))
            face2.append(m)
            face2.append(box(0.02, 0.016, 0.004, mix(skin, (60, 20, 20), .55),
                             center=(0.033, 0.058, 0.1236), skip=flat))
        return face, face2, masked

    @staticmethod
    def _flatten(meshes):
        verts, faces = [], []
        for m in meshes:
            base = len(verts)
            verts.extend(m.verts)
            for idx, col, layer, ds, em in m.faces:
                faces.append((tuple(i + base for i in idx), col, layer, ds, em))
        return verts, faces

    def set_expression(self, name=None, mouth_open=None) -> None:
        """Switch face expression / talking mouth (P11 step 8).

        Rebuilds only the face decal parts; body templates are untouched.
        """
        if name is not None:
            self._expression = str(name)
        if mouth_open is not None:
            self._mouth_open = max(0.0, min(1.0, float(mouth_open)))
        face, face2, _masked = self._face_parts()
        self._parts["face"] = self._flatten(face)
        self._parts["face2"] = self._flatten(face2)
        self._uniq = None  # ground-contact cache follows the templates

    # mesh pieces in their joint frames ----------------------------------
    def _build_parts(self):
        s = self.spec
        self._scale = float(s.get("scale", 1.0))
        skin, hair = s["skin"], s["hair"]
        jac, vest, pants, boots = s["jacket"], s.get("vest"), s["pants"], s["boots"]
        suit = vest is None                      # tailored chest: no plate carrier
        if suit:
            vest = jac
        glove = s.get("glove") or skin
        acc = s.get("accent", vest)
        flat = ("front", "left", "right", "top", "bottom")   # decal: +z face only
        hd = s.get("detail") == "hd"

        def lb(w, h, d, col, center=(0.0, 0.0, 0.0), bv=0.03, **kw):
            """Limb/body block: chamfered in HD, the plain box otherwise."""
            if hd:
                return cbox(w, h, d, col, center=center, bevel=bv, **kw)
            return box(w, h, d, col, center=center, **kw)

        P = {}
        belt = s.get("belt", (20, 20, 22))
        P["pelvis"] = [lb(0.34, 0.18, 0.22, pants, center=(0, 0.0, 0), bv=0.03)]
        if belt:
            P["pelvis"].append(box(0.36, 0.05, 0.24, belt, center=(0, 0.07, 0)))
            if s.get("buckle"):
                P["pelvis"].append(box(0.05, 0.035, 0.01, s["buckle"], center=(0, 0.07, 0.123)))
        coat = s.get("long_coat")
        if coat:
            P["pelvis"].append(lb(0.37, 0.21, 0.25, coat, center=(0, 0.01, 0), bv=0.045))
            if hd:
                # flap pockets on the coat front + a slim cloth belt seam
                fl = mix(coat, (150, 168, 200), .10)
                for sx_ in (-1, 1):
                    P["pelvis"].append(box(0.10, 0.022, 0.012, fl, center=(sx_ * 0.1, -0.035, 0.128)))
                    P["pelvis"].append(box(0.09, 0.05, 0.006, mix(coat, (0, 0, 0), .22),
                                           center=(sx_ * 0.1, -0.065, 0.127)))
        if s.get("satchel"):
            sc_ = s["satchel"]
            P["pelvis"] += [box(0.07, 0.2, 0.24, sc_, center=(0.215, -0.04, 0.03)),
                            box(0.075, 0.07, 0.245, mix(sc_, (0, 0, 0), .25), center=(0.217, 0.03, 0.03))]
        nw = float(s.get("bulk", 0.9 if s.get("narrow") else 1.0))
        self._sh = 0.25 * nw
        # HD: the shoulder line catches the key light - a cooler, lighter top face
        sh_top = {"top": mix(jac, (150, 170, 205), .16)} if hd else None
        torso = [lb(0.40 * nw, 0.52, 0.24, jac, center=(0, 0.30, 0), bv=0.035, cols=sh_top)]
        if suit:
            torso.append(lb(0.42 * nw, 0.40, 0.28, jac, center=(0, 0.36, 0.0), bv=0.04,
                            cols=sh_top))
        else:
            torso.append(lb(0.44 * nw, 0.34, 0.30, vest, center=(0, 0.34, 0.0), bv=0.04,
                            cols={"back": vest}))
        if acc and not suit:
            torso.append(box(0.12, 0.08, 0.04, acc, center=(-0.1, 0.42, 0.16)))
        torso.append(box(0.11, 0.08, 0.11, skin, center=(0, 0.6, 0)))
        if hd and (suit or coat):
            # turned-up collar: a raised back panel and two front flaps
            cl = mix(jac, (150, 170, 205), .10)
            torso.append(box(0.24 * nw, 0.075, 0.07, cl, center=(0, 0.618, -0.085)))
            for sx_ in (-1, 1):
                cm_ = Mesh()
                cm_.add(box(0.05, 0.1, 0.06, cl), m=rot_z(sx_ * -14),
                        t=(sx_ * 0.085 * nw, 0.6, 0.07))
                torso.append(cm_)
        if s.get("pouches") and not suit:
            pc = mix(vest, (0, 0, 0), .3)
            for px_ in (-0.09, 0.0, 0.09):
                torso.append(box(0.075, 0.1, 0.04, pc, center=(px_ * nw, 0.24, 0.165)))
        if s.get("epaulets"):
            for sx_ in (-1, 1):
                torso.append(box(0.085, 0.018, 0.1, s["epaulets"],
                                 center=(sx_ * 0.175 * nw, 0.562, 0)))
        if s.get("pack"):
            torso.append(box(0.30, 0.38, 0.15, s["pack"], center=(0, 0.34, -0.22)))
            torso.append(box(0.02, 0.55, 0.02, (20, 20, 20), center=(0.11, 0.78, -0.25)))
        if s.get("ghillie"):
            torso.append(box(0.5, 0.2, 0.34, s["ghillie"], center=(0, 0.5, 0)))
        if s.get("hoodie"):           # hood bunched around the back of the neck
            hc = mix(jac, (0, 0, 0), .15)
            torso.append(box(0.27 * nw, 0.1, 0.11, hc, center=(0, 0.6, -0.085)))
            for sx_ in (-1, 1):
                torso.append(box(0.06, 0.07, 0.17, hc, center=(sx_ * 0.1 * nw, 0.585, -0.02)))
            torso.append(box(0.42 * nw, 0.05, 0.25, mix(jac, (0, 0, 0), .22), center=(0, 0.065, 0)))
        if s.get("backpack"):
            bp = s["backpack"]
            torso += [box(0.30 * nw, 0.36, 0.13, bp, center=(0, 0.34, -0.19)),
                      box(0.24 * nw, 0.12, 0.05, mix(bp, (0, 0, 0), .25), center=(0, 0.24, -0.27))]
        P["torso"] = torso
        # chest decals (shirt V, lapels, tie, buttons, medal, satchel strap) -
        # flat +z quads on the jacket front, drawn with a depth bias like the face
        # Three decal layers (separate parts, each with more depth bias) so the
        # software painter keeps shirt < lapels < tie even with the body turned.
        chest = ([], [], [])
        fz = 0.142 if suit else 0.152

        def deco(w, h, col, c, z, rz=0.0, lay=0):
            m = Mesh()
            m.add(box(w, h, 0.004, col, skip=flat), m=rot_z(rz), t=(c[0], c[1], z))
            chest[lay].append(m)

        if suit and (s.get("shirt") or s.get("lapel")):
            sh_c = s.get("shirt") or mix(jac, (255, 255, 255), .5)
            deco(0.12, 0.05, sh_c, (0, 0.535), fz)
            deco(0.08, 0.06, sh_c, (0, 0.48), fz)
            deco(0.04, 0.05, sh_c, (0, 0.425), fz)
            if s.get("lapel"):
                for sx_ in (-1, 1):
                    deco(0.04, 0.24, s["lapel"], (sx_ * 0.062, 0.46), fz + 0.0012, rz=sx_ * 20, lay=1)
            if s.get("tie"):
                deco(0.032, 0.2, s["tie"], (0, 0.43), fz + 0.0024, lay=2)
                deco(0.042, 0.03, mix(s["tie"], (0, 0, 0), .2), (0, 0.537), fz + 0.0036, lay=2)
        if s.get("buttons"):
            for by in ((0.3, 0.24, 0.18) if suit else (0.13,)):
                deco(0.02, 0.02, s["buttons"], (0, by), fz + 0.0012, lay=1)
        if s.get("medal"):
            deco(0.035, 0.045, s["medal"], (0.105 * nw, 0.45), fz + 0.0024, lay=2)
        if s.get("satchel"):
            deco(0.032, 0.5, mix(s["satchel"], (0, 0, 0), .2), (0.01, 0.33), fz + 0.0048, rz=38, lay=2)
        if s.get("plaid"):            # flannel check on the jacket front
            for py_ in (0.5, 0.4, 0.3, 0.2, 0.1):
                deco(0.43 * nw, 0.014, s["plaid"], (0, py_), fz)
            for px_ in (-0.15, -0.075, 0.075, 0.15):
                deco(0.014, 0.5, s["plaid"], (px_ * nw, 0.31), fz)
        if s.get("inner"):            # open shirt: tee panel down the middle
            deco(0.13, 0.5, s["inner"], (0, 0.31), fz + 0.0012, lay=1)
        if s.get("hoodie"):
            deco(0.25 * nw, 0.12, mix(jac, (0, 0, 0), .2), (0, 0.17), fz)
            deco(0.23 * nw, 0.10, jac, (0, 0.165), fz + 0.0012, lay=1)
            stc = s.get("strings", mix(jac, (255, 255, 255), .5))
            for sx_ in (-1, 1):
                deco(0.01, 0.12, stc, (sx_ * 0.03, 0.49), fz + 0.0024, lay=2)
        pr = s.get("print")
        if pr:
            kind, pc = pr[0], pr[1]
            if kind == "drip":
                w = 0.11 if s.get("inner") else 0.17
                deco(w, 0.03, pc, (0, 0.44), fz + 0.0024, lay=2)
                for dx_, ln in ((-.4, .05), (-.25, .08), (-.1, .035), (.05, .1), (.2, .045), (.35, .07)):
                    deco(0.011, ln, pc, (dx_ * w * 2, 0.425 - ln / 2), fz + 0.0024, lay=2)
            elif kind == "stripe":
                wc = pr[2] if len(pr) > 2 else (236, 236, 232)
                deco(0.2 * nw, 0.034, pc, (0, 0.33), fz + 0.0024, lay=2)
                deco(0.13 * nw, 0.008, wc, (0, 0.3), fz + 0.0024, lay=2)
                for i_ in range(3):
                    deco(0.009, 0.014 + i_ * 0.008, wc, (-0.012 + i_ * 0.012, 0.37 + i_ * 0.004), fz + 0.0024, lay=2)
        if s.get("straps"):
            for sx_ in (-1, 1):
                deco(0.034, 0.44, s["straps"], (sx_ * 0.095 * nw, 0.36), fz + 0.0036, rz=sx_ * 4, lay=2)
                deco(0.03, 0.02, (120, 120, 124), (sx_ * 0.097 * nw, 0.4), fz + 0.0048, lay=2)
        wound = int(s.get("wound") or 0)
        if wound:
            # Exit wound on the chest (+z, the face that ends up skyward once he
            # is down) and the entry on the back (-z).  Three discrete stages
            # (each its own cached rig template), so the stain can spread
            # without rebuilding anything per frame.
            blood, clot, wet = (82, 8, 13), (40, 5, 9), (112, 20, 22)

            def deco_back(w, h, col, c, z, lay=1):
                m_ = Mesh()
                m_.add(box(w, h, 0.004, col, skip=("back", "left", "right", "top", "bottom")),
                       t=(c[0], c[1], -z))
                chest[lay].append(m_)

            bz = fz + 0.0036
            if wound == 1:
                deco(0.07, 0.08, blood, (0.045, 0.40), bz, rz=12, lay=1)
                deco(0.032, 0.036, clot, (0.05, 0.395), bz + 0.0012, lay=2)
                deco(0.014, 0.014, wet, (-0.02, 0.33), bz + 0.0012, lay=2)
                deco_back(0.05, 0.05, blood, (-0.03, 0.45), bz, lay=1)
                deco_back(0.02, 0.02, clot, (-0.03, 0.45), bz + 0.0012, lay=2)
            elif wound == 2:
                deco(0.13, 0.17, blood, (0.04, 0.37), bz, rz=8, lay=1)
                deco(0.05, 0.06, clot, (0.05, 0.385), bz + 0.0012, lay=2)
                for dx_, ln in ((-0.02, 0.09), (0.05, 0.12), (0.11, 0.07)):
                    deco(0.016, ln, blood, (dx_, 0.28 - ln / 2), bz + 0.0012, lay=2)
                deco(0.022, 0.022, wet, (0.01, 0.40), bz + 0.0024, lay=2)
                deco_back(0.10, 0.11, blood, (-0.03, 0.44), bz, lay=1)
                deco_back(0.028, 0.028, clot, (-0.03, 0.45), bz + 0.0012, lay=2)
            else:
                deco(0.17, 0.23, blood, (0.03, 0.34), bz, rz=6, lay=1)
                deco(0.12, 0.15, mix(blood, clot, .35), (0.02, 0.20), bz + 0.0012, lay=1)
                deco(0.07, 0.08, clot, (0.05, 0.39), bz + 0.0024, lay=2)
                for dx_, ln in ((-0.06, 0.14), (0.0, 0.10), (0.08, 0.16), (0.13, 0.08)):
                    deco(0.018, ln, blood, (dx_, 0.14 - ln / 2), bz + 0.0024, lay=2)
                deco(0.026, 0.026, wet, (0.0, 0.42), bz + 0.0036, lay=2)
                deco_back(0.16, 0.19, blood, (-0.02, 0.40), bz, lay=1)
                deco_back(0.034, 0.034, clot, (-0.03, 0.45), bz + 0.0012, lay=2)
            if s.get("handprint"):
                # A bloody palm pressed on the coat beside the wound: palm, four
                # fingers fanned up, a thumb out to the side.
                hp = (150, 22, 24)
                hz = bz + 0.0052
                deco(0.07, 0.075, hp, (-0.075, 0.27), hz, rz=-14, lay=2)
                for i_, (fx_, fl_) in enumerate(((-0.105, 0.05), (-0.088, 0.062),
                                                 (-0.07, 0.066), (-0.052, 0.056))):
                    deco(0.013, fl_, hp, (fx_, 0.305 + fl_ / 2), hz, rz=-14 + (i_ - 1.5) * 8, lay=2)
                deco(0.014, 0.045, hp, (-0.035, 0.285), hz, rz=-60, lay=2)
        P["chest"], P["chest2"], P["chest3"] = chest
        face, face2, masked = self._face_parts()
        P["face"], P["face2"] = face, face2
        hw = s.get("head_w", 1.0)
        head = [box(0.20 * hw, 0.24, 0.22, skin, center=(0, 0.13, 0.01)),
                box(0.035, 0.06, 0.035, mix(skin, (0, 0, 0), .12), center=(0, 0.11, 0.13))]
        if s.get("ears"):
            for sx_ in (-1, 1):
                head.append(box(0.024, 0.055, 0.045, mix(skin, (40, 10, 10), .12),
                                center=(sx_ * (0.1 * hw + 0.01), 0.135, 0.0)))
        if masked:
            head.append(box(0.208 * hw, 0.095, 0.228, masked, center=(0, 0.055, 0.012)))
        style = s.get("hair_style")
        H_ = []
        if s.get("beret"):
            H_.append(box(0.235 * hw, 0.06, 0.25, s["beret"], center=(0.01, 0.272, -0.005)))
            H_.append(box(0.1, 0.05, 0.2, s["beret"], center=(0.075 * hw, 0.25, -0.01)))
            H_.append(box(0.21 * hw, 0.13, 0.05, hair, center=(0, 0.16, -0.105)))
        elif s.get("bandana"):
            # cloth tied over the crown: forehead band, knot + two tails at the back
            bc = s["bandana"]
            dk = mix(bc, (0, 0, 0), .2)
            H_ += [box(0.228 * hw, 0.085, 0.252, bc, center=(0, 0.262, -0.004)),
                   box(0.214 * hw, 0.05, 0.236, bc, center=(0, 0.205, 0.0)),
                   box(0.21 * hw, 0.12, 0.05, hair, center=(0, 0.14, -0.105)),
                   box(0.06, 0.055, 0.05, dk, center=(0.03, 0.215, -0.13))]
            for rz, tx in ((14, 0.0), (-10, 0.055)):
                m = Mesh()
                m.add(box(0.045, 0.15, 0.016, dk), m=m_mul(rot_z(rz), rot_x(-18)),
                      t=(tx, 0.15, -0.15))
                H_.append(m)
        elif style in ("messy", "mop"):
            # thick, curly mop: volume on top, uneven tufts, a fringe falling over the brow
            H_.append(box(0.235 * hw, 0.085, 0.25, hair, center=(0, 0.27, -0.005)))
            H_.append(box(0.225 * hw, 0.2, 0.06, hair, center=(0, 0.17, -0.11)))
            for tx, ty, tz, tw in ((-0.07, 0.325, 0.03, 0.07), (0.02, 0.335, -0.02, 0.08),
                                   (0.08, 0.32, 0.05, 0.06), (-0.03, 0.33, 0.08, 0.06),
                                   (0.05, 0.315, -0.08, 0.07), (-0.09, 0.31, -0.06, 0.06)):
                H_.append(box(tw, 0.05, tw, hair, center=(tx * hw, ty, tz)))
            for fx, fh, fz_ in ((-0.07, 0.05, 0.118), (-0.02, 0.064, 0.124),
                                (0.035, 0.056, 0.121), (0.08, 0.04, 0.117)):
                H_.append(box(0.055, fh, 0.03, hair, center=(fx * hw, 0.262 - fh / 2, fz_)))
            for side in (-1, 1):
                H_.append(box(0.025, 0.12, 0.16, hair, center=(side * 0.112 * hw, 0.2, -0.02)))
        elif s.get("helmet"):
            H_.append(box(0.25, 0.11, 0.27, s["helmet"], center=(0, 0.26, 0)))
        elif s.get("beanie"):
            H_.append(box(0.225, 0.11, 0.245, s["beanie"], center=(0, 0.255, -0.005)))
        elif s.get("cap"):
            cc = s["cap"]
            H_ += [box(0.235 * hw, 0.075, 0.26, cc, center=(0, 0.282, 0.0)),
                   box(0.218 * hw, 0.03, 0.236, mix(cc, (0, 0, 0), .35), center=(0, 0.24, 0.0)),
                   box(0.19 * hw, 0.014, 0.08, mix(cc, (0, 0, 0), .5), center=(0, 0.232, 0.15)),
                   box(0.21 * hw, 0.13, 0.05, hair, center=(0, 0.16, -0.105))]
        elif s.get("hat"):
            hc = s["hat"]
            H_ += [box(0.34 * hw, 0.016, 0.36, mix(hc, (0, 0, 0), .2), center=(0, 0.25, 0.0)),
                   box(0.22 * hw, 0.09, 0.24, hc, center=(0, 0.3, 0.0)),
                   box(0.21 * hw, 0.1, 0.05, hair, center=(0, 0.15, -0.105))]
        elif style == "shag":
            # messy brown mop with a heavy fringe swept to one side
            H_.append(box(0.232 * hw, 0.08, 0.252, hair, center=(0, 0.27, -0.004)))
            H_.append(box(0.222 * hw, 0.2, 0.06, hair, center=(0, 0.17, -0.11)))
            for tx, ty, tz, tw in ((-0.07, 0.318, 0.02, 0.07), (0.03, 0.326, -0.01, 0.08),
                                   (0.08, 0.31, 0.06, 0.06), (-0.04, 0.315, -0.08, 0.07)):
                H_.append(box(tw, 0.04, tw, hair, center=(tx * hw, ty, tz)))
            for fx, fh, rz in ((-0.07, 0.05, -18), (-0.025, 0.07, -22), (0.025, 0.075, -24), (0.07, 0.06, -20)):
                m = Mesh()
                m.add(box(0.06, fh, 0.03, hair), m=rot_z(rz), t=(fx * hw, 0.262 - fh / 2, 0.121))
                H_.append(m)
            for side in (-1, 1):
                H_.append(box(0.028, 0.14, 0.17, hair, center=(side * 0.113 * hw, 0.2, -0.02)))
        elif style == "fringe":
            # dense straight hair, full fringe cut just above the brows
            H_.append(box(0.23 * hw, 0.075, 0.25, hair, center=(0, 0.268, -0.004)))
            H_.append(box(0.222 * hw, 0.2, 0.06, hair, center=(0, 0.17, -0.11)))
            H_.append(box(0.216 * hw, 0.06, 0.03, hair, center=(0, 0.232, 0.121)))
            for side in (-1, 1):
                H_.append(box(0.028, 0.13, 0.19, hair, center=(side * 0.112 * hw, 0.205, -0.005)))
        elif style == "spiky":
            # short textured cut, tips pushed up
            H_.append(box(0.216 * hw, 0.06, 0.244, hair, center=(0, 0.258, -0.004)))
            H_.append(box(0.21 * hw, 0.16, 0.05, hair, center=(0, 0.17, -0.106)))
            for tx, tz, th in ((-0.07, 0.08, 0.05), (0.0, 0.09, 0.06), (0.07, 0.07, 0.045),
                               (-0.05, 0.0, 0.055), (0.04, 0.0, 0.05), (-0.02, -0.08, 0.04), (0.06, -0.08, 0.04)):
                m = Mesh()
                m.add(box(0.035, th, 0.035, hair), m=rot_x(18), t=(tx * hw, 0.285 + th / 2 - 0.01, tz))
                H_.append(m)
            for side in (-1, 1):
                H_.append(box(0.02, 0.07, 0.13, hair, center=(side * 0.106 * hw, 0.22, -0.03)))
        elif style == "curly":
            # short tight curls: low cap with a scatter of small tufts
            H_.append(box(0.218 * hw, 0.06, 0.244, hair, center=(0, 0.258, -0.004)))
            H_.append(box(0.214 * hw, 0.17, 0.05, hair, center=(0, 0.17, -0.106)))
            for tx, tz in ((-0.07, 0.07), (0.0, 0.085), (0.065, 0.06), (-0.05, -0.02),
                           (0.04, -0.03), (-0.01, -0.08), (0.07, -0.08)):
                H_.append(box(0.05, 0.035, 0.05, hair, center=(tx * hw, 0.295, tz)))
            for side in (-1, 1):
                H_.append(box(0.02, 0.08, 0.13, hair, center=(side * 0.106 * hw, 0.215, -0.03)))
        elif style == "slick":
            # combed straight back: flat glossy top, longer at the nape
            hl = mix(hair, (200, 200, 210), .22)
            H_.append(box(0.214 * hw, 0.055, 0.25, hair, center=(0, 0.258, -0.01), cols={"top": hl}))
            H_.append(box(0.212 * hw, 0.22, 0.055, hair, center=(0, 0.15, -0.108)))
            H_.append(box(0.2 * hw, 0.035, 0.03, hair, center=(0, 0.245, 0.11)))
            for side in (-1, 1):
                H_.append(box(0.02, 0.09, 0.15, hair, center=(side * 0.106 * hw, 0.21, -0.035)))
        elif style == "swept":
            # side-parted, swept up at the front (statesman)
            H_.append(box(0.218 * hw, 0.065, 0.246, hair, center=(0, 0.262, -0.004)))
            H_.append(box(0.212 * hw, 0.18, 0.05, hair, center=(0, 0.17, -0.106)))
            m = Mesh()
            m.add(box(0.15 * hw, 0.05, 0.1, hair), m=rot_x(-12), t=(0.025 * hw, 0.295, 0.07))
            H_.append(m)
            H_.append(box(0.06 * hw, 0.04, 0.2, hair, center=(-0.08 * hw, 0.285, 0.0)))
            for side in (-1, 1):
                H_.append(box(0.018, 0.07, 0.13, hair, center=(side * 0.106 * hw, 0.22, -0.03)))
        elif style == "bald":
            for side in (-1, 1):
                H_.append(box(0.02, 0.07, 0.14, hair, center=(side * 0.106 * hw, 0.17, -0.04)))
            H_.append(box(0.21 * hw, 0.09, 0.04, hair, center=(0, 0.14, -0.103)))
        else:
            H_.append(box(0.215 * hw, 0.07, 0.24, hair, center=(0, 0.255, -0.005)))
            H_.append(box(0.21 * hw, 0.17, 0.05, hair, center=(0, 0.17, -0.105)))
        if style != "bald" and not s.get("hood"):
            # nape: the back-hair blocks stop ~0.085 up a skull that starts at
            # 0.01, which read as a wide skin band from behind (M5 gauntlet N08).
            # A short faded layer brings the hairline down to the neck.
            H_.append(box(0.198 * hw, 0.06, 0.03, mix(hair, skin, .3), center=(0, 0.062, -0.1)))
        head += H_
        if s.get("ponytail"):
            head.append(box(0.07, 0.24, 0.07, hair, center=(0, 0.1, -0.16)))
            head.append(box(0.03, 0.16, 0.16, hair, center=(-0.108, 0.17, -0.02)))
            head.append(box(0.03, 0.16, 0.16, hair, center=(0.108, 0.17, -0.02)))
        if s.get("hood"):
            head.append(box(0.25, 0.3, 0.27, s["hood"], center=(0, 0.15, -0.02),
                            cols={"back": (10, 10, 10)}))
        if hd and not s.get("hood") and not masked:
            # face planes the side key can model: brow ridge, cheekbones, chin.
            # All stay a hair off the decal plane (the decals carry a depth bias).
            sk_d = mix(skin, (0, 0, 0), .16)
            head.append(box(0.176 * hw, 0.02, 0.028, sk_d, center=(0, 0.206, 0.124)))
            for sx_ in (-1, 1):
                head.append(box(0.03, 0.04, 0.028, mix(skin, (255, 226, 205), .07),
                                center=(sx_ * 0.076 * hw, 0.106, 0.122)))
            head.append(box(0.074 * hw, 0.03, 0.026, mix(skin, (0, 0, 0), .06),
                            center=(0, 0.028, 0.122)))
        P["head"] = head
        short = s.get("sleeves") == "short"
        if short:
            P["uarm"] = [box(0.125, 0.16, 0.135, jac, center=(0, -0.075, 0)),
                         box(0.1, 0.17, 0.105, skin, center=(0, -0.22, 0))]
        else:
            P["uarm"] = [lb(0.115, 0.31, 0.125, jac, center=(0, -0.15, 0), bv=0.03)]
        if s.get("armband"):
            # cloth band hugging the sleeve (3 mm proud). The old 1.12x box stood
            # ~1 cm off every side and read as a floating red brick (M5 N10).
            ac = s["armband"]
            P["uarm_acc"] = [box(0.121, 0.07, 0.131, ac, center=(0, -0.08, 0),
                                 cols={"top": mix(ac, jac, .5), "bottom": mix(ac, (0, 0, 0), .45)})]
        else:
            P["uarm_acc"] = [box(0.12, 0.06, 0.13, acc or jac, center=(0, -0.08, 0))]
        cuff = s.get("cuff")
        P["farm"] = [lb(0.1, 0.27, 0.105, skin if short else jac, center=(0, -0.135, 0), bv=0.025)]
        if s.get("blood_hands"):
            glove = mix(glove, (96, 12, 14), .8)
        # M5 draws optional articulated palms at the wrist; legacy rigs and
        # GPU slots remain unchanged. Never draw two overlapping fists.
        if not s.get("articulated_hands"):
            if hd:
                # palm, curled fingers and a thumb; the fingers end where the
                # old fist did, so a hand resting on the ground sits the same.
                P["farm"] += [lb(0.082, 0.06, 0.095, glove, center=(0, -0.305, 0.0), bv=0.02),
                              box(0.084, 0.036, 0.034, mix(glove, (255, 255, 255), .07),
                                  center=(0, -0.337, 0.042)),
                              box(0.026, 0.045, 0.04, glove, center=(0, -0.30, 0.05))]
            else:
                P["farm"].append(box(0.085, 0.09, 0.095, glove, center=(0, -0.31, 0.0)))
        if cuff:
            P["farm"].append(box(0.09, 0.02, 0.1, cuff, center=(0, -0.262, 0.0)))
        if s.get("blood_hands"):      # blood up the wrist
            P["farm"].append(box(0.108, 0.05, 0.113, (88, 11, 14), center=(0, -0.245, 0.0)))
        P["thigh"] = [lb(0.16, 0.45, 0.17, pants, center=(0, -0.225, 0), bv=0.035)]
        if coat:
            ln = float(s.get("coat_len", 0.42))
            if hd:
                # front and back panels (the back flares past the hem) and a
                # darker hem band: the skirt moves as two cloths, not one tube
                hem = mix(coat, (0, 0, 0), .30)
                P["thigh"] += [
                    lb(0.19, ln, 0.11, coat, center=(0, -ln / 2 + 0.02, 0.045), bv=0.02),
                    lb(0.2, ln + 0.026, 0.11, mix(coat, (0, 0, 0), .10),
                       center=(0, (0.006 - ln) / 2, -0.045), bv=0.02),
                    box(0.198, 0.022, 0.116, hem, center=(0, -ln + 0.031, 0.045)),
                    box(0.208, 0.022, 0.116, hem, center=(0, -ln + 0.001, -0.045))]
            else:
                P["thigh"].append(box(0.19, ln, 0.2, coat, center=(0, -ln / 2 + 0.02, 0)))
        P["shin"] = [lb(0.135, 0.45, 0.145, pants, center=(0, -0.225, 0), bv=0.03)]
        if s.get("boots_h"):          # rubber boots: shaft up the shin
            bh = 0.45 * float(s["boots_h"])
            P["shin"] += [box(0.15, bh, 0.16, boots, center=(0, -0.45 + bh / 2, 0)),
                          box(0.156, 0.02, 0.166, mix(boots, (255, 255, 255), .2), center=(0, -0.45 + bh, 0))]
        elif hd:
            # trouser break: the cuff falls over the top of the boot
            P["shin"].append(box(0.148, 0.05, 0.158, mix(pants, (110, 120, 140), .07),
                                 center=(0, -0.425, 0)))
        if s.get("rips"):             # worn-through knees
            P["shin"] += [box(0.07, 0.012, 0.004, s["rips"], center=(0, y_, 0.0745), skip=flat)
                          for y_ in (-0.03, -0.06, -0.15)]
        if hd:
            # boot body (top flush with the old foot, bottom 1 cm up), a
            # separate sole that owns the old lowest vertex, toe cap and heel
            P["foot"] = [lb(0.125, 0.09, 0.26, boots, center=(0, -0.045, 0.05), bv=0.03),
                         box(0.13, 0.022, 0.268, s.get("sole") or mix(boots, (0, 0, 0), .55),
                             center=(0, -0.089, 0.05)),
                         box(0.118, 0.05, 0.075, mix(boots, (95, 100, 112), .14),
                             center=(0, -0.062, 0.155)),
                         box(0.12, 0.05, 0.05, mix(boots, (0, 0, 0), .30),
                             center=(0, -0.062, -0.07))]
        else:
            P["foot"] = [box(0.125, 0.10, 0.26, boots, center=(0, -0.05, 0.05))]
            if s.get("sole"):
                P["foot"].append(box(0.13, 0.025, 0.265, s["sole"], center=(0, -0.088, 0.05)))
        # flatten each part list into (verts, faces) templates
        self._parts = {k: self._flatten(meshes) for k, meshes in P.items()}

    # posing ----------------------------------------------------------------
    def placements(self, pose, rifle_on=True):
        """Pose the skeleton without touching vertices.

        -> (places, joints, rifle_m, lift)
        places: [(slot, part_key, M, origin, ground, fb)] in draw order, where
        slot is the stable index used by GPU skinning (see SLOTS). joints are
        body-local (before ground contact and world translation)."""
        p = dict(NEUTRAL)
        p.update(pose)
        B = m_mul(rot_y(0.0), m_mul(rot_x(p["body_p"]), rot_z(p["body_r"])))
        return self._placements(p, B, rifle_on)

    def _placements(self, p, B, rifle_on):
        B0 = B
        sc = self._scale
        if sc != 1.0:
            B = tuple(x * sc for x in B)
        S = m_mul(B, m_mul(rot_y(p["twist"]), m_mul(rot_x(p["spine"]), rot_z(p["spine_r"]))))
        H = m_mul(S, m_mul(rot_y(p["head_y"]), rot_x(p["head_p"])))
        neck = m_apply(S, (0, 0.62, 0))
        places = []
        joints = {}
        o = (0.0, 0.0, 0.0)
        places.append((0, "pelvis", B, o, True, 0.0))
        places.append((1, "torso", S, o, True, 0.0))
        places.append((2, "head", H, neck, True, 0.0))
        if not self.spec.get("hood"):
            places.append((3, "face", H, neck, False, PART_FB["face"]))
            if self._parts["face2"][1]:
                places.append((18, "face2", H, neck, False, PART_FB["face2"]))
        for slot, key in ((17, "chest"), (19, "chest2"), (20, "chest3")):
            if self._parts[key][1]:
                places.append((slot, key, S, o, False, PART_FB[key]))
        joints["head"] = v_add(neck, m_apply(H, (0, 0.14, 0.02)))
        joints["chest"] = m_apply(S, (0, 0.36, 0.08))
        joints["pelvis"] = o
        for side, sx, base in (("l", -1, 4), ("r", 1, 10)):
            sh = m_apply(S, (self._sh * sx, 0.5, 0))
            U = m_mul(
                S,
                m_mul(
                    rot_z(p[side + "sh_r"] * sx),
                    m_mul(
                        rot_x(-p[side + "sh_p"]),
                        rot_y(p.get(side + "sh_y", 0.0)),
                    ),
                ),
            )
            places.append((base, "uarm", U, sh, True, 0.0))
            if side == "l":
                places.append((base + 1, "uarm_acc", U, sh, True, PART_FB["uarm_acc"]))
            el = v_add(sh, m_apply(U, (0, -0.30, 0)))
            F = m_mul(U, rot_x(-p[side + "el"]))
            places.append((base + 2, "farm", F, el, True, 0.0))
            joints[side + "hand"] = v_add(el, m_apply(F, (0, -0.31, 0)))
            hip = m_apply(B, (0.1 * sx, -0.04, 0))
            T = m_mul(B, m_mul(rot_z(p[side + "hip_r"] * sx), rot_x(-p[side + "hip_p"])))
            places.append((base + 3, "thigh", T, hip, True, 0.0))
            kn = v_add(hip, m_apply(T, (0, -0.45, 0)))
            K = m_mul(T, rot_x(p[side + "kn"]))
            places.append((base + 4, "shin", K, kn, True, 0.0))
            an = v_add(kn, m_apply(K, (0, -0.45, 0)))
            Fo = m_mul(K, rot_x(p[side + "hip_p"] - p[side + "kn"] + p[side + "ank"]))
            places.append((base + 5, "foot", Fo, an, True, 0.0))
        rifle_m = None
        if self._rifle is not None and rifle_on:
            R = m_mul(B0, m_mul(rot_y(p["rifle_y"]), rot_x(p["rifle_p"])))
            hand = joints["rhand"]
            places.append((16, "rifle", R, hand, False, 0.0))
            joints["muzzle"] = v_add(hand, m_apply(R, (0, 0.015, 0.78)))
            rifle_m = R
        return places, joints, rifle_m, p["lift"]

    def pose_world(self, pose, pos, yaw, rifle_on=True):
        """Skeleton-only posing for GPU skinning (engine3d.gl).

        -> (places, joints) with joints in world space exactly as build()
        returns them. Ground contact uses each part's unique vertices, so the
        result matches build() without transforming the whole mesh."""
        p = dict(NEUTRAL)
        p.update(pose)
        B = m_mul(rot_y(yaw), m_mul(rot_x(p["body_p"]), rot_z(p["body_r"])))
        places, joints, rifle_m, lift = self._placements(p, B, rifle_on)
        uniq = self._unique_verts()
        miny = 1e9
        for _slot, key, M, org, ground, _fb in places:
            if not ground:
                continue
            m3, m4, m5 = M[3], M[4], M[5]
            oy = org[1]
            for (x, y, z) in uniq[key]:
                q = m3 * x + m4 * y + m5 * z + oy
                if q < miny:
                    miny = q
        dy = -miny + lift
        px, py, pz = pos
        py += dy
        for k, v in list(joints.items()):
            joints[k] = (v[0] + px, v[1] + py, v[2] + pz)
        joints["rifle_m"] = rifle_m
        return places, joints, (px, py, pz)

    def _unique_verts(self):
        u = getattr(self, "_uniq", None)
        if u is None:
            u = {k: list(dict.fromkeys(v)) for k, (v, _f) in self._parts.items()}
            self._uniq = u
        return u

    def build(self, pose, pos, yaw, rifle_on=True, extra=None):
        """-> (world_verts, faces, joints) faces ready for Renderer.add_dynamic.
        joints: dict of world positions (head, rhand, lhand, pelvis, chest, muzzle)."""
        p = dict(NEUTRAL)
        p.update(pose)
        B = m_mul(rot_y(yaw), m_mul(rot_x(p["body_p"]), rot_z(p["body_r"])))
        places, joints, rifle_m, lift = self._placements(p, B, rifle_on)
        out_v, out_f = [], []
        ground_v = []
        for _slot, key, M, origin, ground, fb in places:
            if key == "rifle":
                base = len(out_v)
                for v in self._rifle.verts:
                    q = m_apply(M, v)
                    out_v.append((q[0] + origin[0], q[1] + origin[1], q[2] + origin[2]))
                for idx, col, layer, ds, em in self._rifle.faces:
                    out_f.append((tuple(i + base for i in idx), col, layer, ds, None, em))
                continue
            verts, faces = self._parts[key]
            base = len(out_v)
            for v in verts:
                q = m_apply(M, v)
                out_v.append((q[0] + origin[0], q[1] + origin[1], q[2] + origin[2]))
            if ground:
                ground_v.append((base, len(out_v)))
            for idx, col, layer, ds, em in faces:
                out_f.append((tuple(i + base for i in idx), col, layer, ds, None, em, fb))
        # ground contact: lowest body vertex sits on y = 0, plus lift
        miny = min(out_v[i][1] for a, b in ground_v for i in range(a, b))
        dy = -miny + lift
        px, py, pz = pos
        py += dy
        out_v = [(x + px, y + py, z + pz) for x, y, z in out_v]
        for k, v in list(joints.items()):
            joints[k] = (v[0] + px, v[1] + py, v[2] + pz)
        joints["rifle_m"] = rifle_m
        return out_v, out_f, joints


# GPU skinning slot table: slot -> part key (see Humanoid._placements).
SLOTS = ("pelvis", "torso", "head", "face",
         "uarm", "uarm_acc", "farm", "thigh", "shin", "foot",
         "uarm", None, "farm", "thigh", "shin", "foot",
         "rifle", "chest", "face2", "chest2", "chest3")
# depth bias (metres) for decal parts; both backends read this
PART_FB = {"face": 0.09, "face2": 0.1, "chest": 0.05, "chest2": 0.06, "chest3": 0.07,
           "uarm_acc": 0.015}


def mix(a, b, t):
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))
