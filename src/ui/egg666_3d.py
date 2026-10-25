"""egg666_3d.py - the Mission 1 safe-keypad "666" Easter egg as a lit 3D scene.

Entering 666 on the safe keypad cuts to black and plays a nine second scare
in the engine's own PS2 look: ``engine3d.Renderer`` (GL), pixel textures from
assets/tex3d, the M6 grade and crisp present.  The only light is a failing
lamp, a flashlight and the demon's red eyes; the demon is the game's blocky
character language made wrong.  The beat sheet lives in ``egg666_dir``, the
geometry in ``egg666_build``, the halos and the PS2 grade in ``egg666_fx``,
the screen effects in ``egg666_post`` and the sound in ``egg666_audio``; this
module wires them together.

``hud.py`` is a thin caller: ``available()`` and ``begin(seed, size)`` at the
trigger, ``frame(screen, f)`` every frame, ``stop()`` when it is over.  Any
failure returns False and the caller falls back to the old 2D scare.  Set
``ACA_EGG666_3D=0`` to force the 2D scare.  No import-time side effects, and
nothing here touches the save file.
"""
import math
import os
import random

import numpy as np
import pygame

from engine3d.core import Light, M_IDENT, m_apply, m_mul, rot_y
from engine3d.gl import Renderer, gl_available
from ui import egg666_build as B
from ui import egg666_dir as D
from ui import egg666_fx as FX
from ui.egg666_post import Post

TOTAL = D.TOTAL
RES = 0.64                       # internal frame, as the M6 PS2 scenes
LIGHT_GAIN = 2.3                 # local lights are multiplied by the surface colour
EYE_LIGHT = 0.8
_NAMES = [p[0] for p in B.PARTS]
HEAD = _NAMES.index("head")
_E = None                        # the running scare (None = idle)


def available():
    """True when the 3D scare can run here: not switched off, quality tier
    above 0 and a GL context."""
    if os.environ.get("ACA_EGG666_3D", "").strip().lower() in ("0", "off", "false", "no", "2d"):
        return False
    try:
        from game.render3d_bridge import quality_3d  # lazy: settings bridge
        return quality_3d() > 0 and bool(gl_available())
    except Exception:
        return False


def active():
    return _E is not None


def demon_bed_level(f):
    return D.demon_bed_level(f)


class _Egg:
    def __init__(self, seed, size, sound):
        self.plan = D.make_plan(seed)
        w, h = size
        self.bw, self.bh = max(160, int(w * RES) // 2 * 2), max(120, int(h * RES) // 2 * 2)
        r = self.r = Renderer(self.bw, self.bh, fog=(0, 0, 0), fog_start=7.0, fog_end=20.0)
        if r.backend != "gl":
            raise RuntimeError("the 3D scare needs the GL renderer")
        try:
            self._build(r, seed, size, sound)
        except Exception:
            r.release()                    # a half-built scare keeps no GPU objects
            raise

    def _build(self, r, seed, size, sound):
        r.light = Light(direction=(0.0, 1.0, 0.0), ambient=0.035, diffuse=0.0, sky=0.0)
        r.light_cap, r.light_albedo, r.light_gain = 8, True, LIGHT_GAIN
        self.buf = pygame.Surface((self.bw, self.bh))
        self.last = pygame.Surface(size)
        self.last_f = -2
        self.post = Post(self.bw, self.bh)
        self.room = B.pack_mesh(B.build_room())
        marks, phase, gain = B.build_marks(seed)
        self.m_base = B.pack_mesh(marks)
        self.m_phase = np.repeat(phase, 6)
        self.m_gain = np.repeat(gain, 6)[:, None]
        body, bulb = B.build_lamp()
        self.l_body, self.l_bulb = B.pack_mesh(body), B.pack_mesh(bulb)
        self.d_base, self.d_spans = B.pack_parts(B.build_demon())
        self.parent = [_NAMES.index(p[1]) if p[1] else -1 for p in B.PARTS]
        self.off = [p[2] for p in B.PARTS]
        self.keys = [p[3] for p in B.PARTS]
        self.cu = self._close_up()
        self.fired, self.prev_lamp, self.last_buzz = set(), 0.0, -9
        self.audio = None
        self._warm()
        if sound:
            try:
                from ui import egg666_audio
                egg666_audio.hush()
                egg666_audio.begin()
                self.audio = egg666_audio
            except Exception as exc:
                print("egg666: no sound (%s)" % (exc,))

    def _warm(self):
        """Draw a lit frame and a close-up off screen, so the first real flicker
        pays for no shader, atlas or table (the scare opens in black)."""
        self.post.warm()
        scratch = pygame.Surface(self.last.get_size())
        for f in (50, 150, 396):
            _frame(self, scratch, f)
        self.fired, self.prev_lamp, self.last_buzz, self.last_f = set(), 0.0, -9, -2

    # -- skeleton -----------------------------------------------------------------
    def fk(self, P):
        """Pose -> [(M, O)] per part: a 3x3 row-major matrix and the joint's world position."""
        out = []
        for i, par in enumerate(self.parent):
            kx, ky, kz = self.keys[i]
            rx, ry, rz = (P[kx] if kx else 0.0), (P[ky] if ky else 0.0), (P[kz] if kz else 0.0)
            R = B.rot(rx, ry, rz) if (rx or ry or rz) else M_IDENT
            if par < 0:
                out.append((m_mul(rot_y(P["yaw"]), R), (P["x"], B.ROOT_Y + P["dy"], P["z"])))
            else:
                pm, po = out[par]
                o = m_apply(pm, self.off[i])
                out.append((m_mul(pm, R), (po[0] + o[0], po[1] + o[1], po[2] + o[2])))
        return out

    def _close_up(self):
        """The face centre and where it looks, at the hard cut (the camera's anchor)."""
        M, O = self.fk(D.pose(D.CUT_F, self.plan))[HEAD]
        c, f = m_apply(M, (0.0, 0.10, -0.12)), m_apply(M, (0.0, 0.0, -1.0))
        return (O[0] + c[0], O[1] + c[1], O[2] + c[2]), f

    # -- per-frame rows ------------------------------------------------------------
    def demon_rows(self, fk, eye_k):
        base, rows = self.d_base, self.d_base.copy()
        for i, (a, b) in enumerate(self.d_spans):
            M, O = fk[i]
            Mt = np.array(M, dtype=np.float32).reshape(3, 3).T
            rows[a:b, 0:3] = base[a:b, 0:3] @ Mt + np.array(O, dtype=np.float32)
            rows[a:b, 6:9] = base[a:b, 6:9] @ Mt
        for j, pair in enumerate(B.EYE_PAIRS):
            a, b = self.d_spans[B.EYE_FIRST + j]
            rows[a:b, 3:6] = base[a:b, 3:6] * eye_k[pair]
        return rows

    def marks_rows(self, f, k, hb):
        rows = self.m_base.copy()
        wave = 0.60 + 0.40 * np.sin(self.m_phase * 3.0 - f * 0.16)
        rows[:, 3:6] = np.minimum(self.m_base[:, 3:6] * ((k * (1.0 + 0.6 * hb) * wave)[:, None] * self.m_gain), 255.0)
        return rows

    def lamp_rows(self, f, k):
        rx, rz = D.lamp_swing(f, self.plan)
        R = B.rot(rx, 0.0, rz)
        Rt = np.array(R, dtype=np.float32).reshape(3, 3).T
        anchor = np.array(B.LAMP_ANCHOR, dtype=np.float32)
        out = []
        for base in (self.l_body, self.l_bulb):
            rows = base.copy()
            rows[:, 0:3] = base[:, 0:3] @ Rt + anchor
            rows[:, 6:9] = base[:, 6:9] @ Rt
            out.append(rows)
        out[1][:, 3:6] = np.array((255.0, 238.0, 190.0), dtype=np.float32) * (0.10 + 0.90 * k)
        d = m_apply(R, (0.0, -B.LAMP_LEN - 0.16, 0.0))
        return out, (B.LAMP_ANCHOR[0] + d[0], B.LAMP_ANCHOR[1] + d[1], B.LAMP_ANCHOR[2] + d[2])


def _vec_sub(a, b):
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def _norm(v):
    n = math.sqrt(v[0] * v[0] + v[1] * v[1] + v[2] * v[2]) or 1.0
    return (v[0] / n, v[1] / n, v[2] / n)


def _lights(E, f, fk, lamp_k, bulb, eye_k, mk, cam, fl):
    L = []
    if lamp_k > 0.02:
        L.append(dict(pos=bulb, color=(255, 176, 104), intensity=2.0 * lamp_k, range=10.5, kind="point"))
    hm, ho = fk[HEAD]
    cd = math.sqrt(sum(v * v for v in _vec_sub(ho, cam)))
    near = 0.35 + 0.65 * min(1.0, max(0.0, (cd - 0.7) / 1.8))      # the face stays dark up close
    for pair in range(3):
        if eye_k[pair] > 0.02:
            p = m_apply(hm, B.PAIR_CENTRE[pair])
            L.append(dict(pos=(ho[0] + p[0], ho[1] + p[1], ho[2] + p[2]), color=(255, 30, 14),
                          intensity=EYE_LIGHT * near * eye_k[pair], range=1.9 if cd > 1.5 else 1.1, kind="point"))
    if mk > 0.02:
        L.append(dict(pos=(B.CIRCLE[0], 0.22, B.CIRCLE[1]), color=(205, 24, 12), intensity=0.7 * mk,
                      range=4.2, kind="point"))
    if fl > 0.02:
        L.append(dict(pos=cam, color=(214, 224, 250), intensity=0.8 * fl, range=2.4, kind="spot",
                      dir=_norm(_vec_sub(E.cu[0], cam)), cone=math.cos(math.radians(24.0))))
    return L


def _sound(E, f, lamp_k, fk, cam):
    """The beat sheet's cues.  Silence is the rule: a sound plays only where listed."""
    A = E.audio
    if A is None:
        return
    plan = E.plan
    once = lambda key, cond: cond and key not in E.fired and not E.fired.add(key)
    hx, hy, hz = fk[HEAD][1]
    dx, dy, dz = hx - cam[0], hy - cam[1], hz - cam[2]
    dist = math.sqrt(dx * dx + dy * dy + dz * dz)
    pan = max(-1.0, min(1.0, dx / max(1.2, dist) * 1.3))
    near = max(0.0, min(1.0, 1.0 - (dist - 1.0) / 6.0))
    if f >= D.BLACK_F:
        if once("end", True):
            A.stop()
        return
    if lamp_k > 0.0 and E.prev_lamp <= 0.0 and f - E.last_buzz >= 3 and f < D.CUT_F:
        A.one_shot("egg666_buzz", 0.30 + 0.40 * lamp_k, 0.3)
        E.last_buzz = f
    E.prev_lamp = lamp_k
    for i in range(2, 6):                                    # it steps nearer in the dark
        if once(("step", i), f >= plan.wins[i][0] - 10 and f < D.CUT_F):
            sx = plan.stations[i]["x"]
            A.one_shot("egg666_thud", 0.18 + 0.45 * max(0.0, 1.0 - plan.stations[i]["z"] / 8.0), sx / 5.0)
    if f >= D.QUIET_F:
        if once("quiet", True):
            A.stop()                                         # dead quiet before the lunge
    else:
        A.bed("egg666_drone", 0.30 * D.ramp(f, D.DRONE_F, 250) + 0.30 * D.ramp(f, 300, D.CUT_F))
        A.bed("egg666_breath", (0.10 + 0.55 * near) * D.ramp(f, D.BREATH_F, D.BREATH_F + 30), pan)
    for b in D.BEATS:
        if once(("hb", b), b <= f < b + 6):
            A.one_shot("egg666_heart", D.lerp(0.45, 0.95, D.ramp(b, 240, D.QUIET_F)), pan)
    if once("crack", f >= D.CRACK_F - 1 and f < D.CUT_F):
        A.one_shot("egg666_crack", 0.9, pan)
    if once("groan", f >= D.GROAN_F and f < D.CUT_F):
        A.one_shot("egg666_groan", 0.8, pan)
    if once("sting", f >= D.LUNGE_F):
        A.one_shot("egg666_sting", 1.0, 0.0)
        A.one_shot("egg666_thud", 1.0, 0.0)


def _frame(E, screen, f):
    plan = E.plan
    f = max(0, min(TOTAL - 1, int(f)))
    calm = 0.35 if FX.reduced_motion() else 1.0
    P = D.pose(f, plan)
    lg, fwd = P["lunge"], E.cu[1]
    P["x"] += fwd[0] * lg
    P["z"] += fwd[2] * lg
    P["dy"] += fwd[1] * lg
    fk = E.fk(P)
    lamp_k = D.lamp(f, plan) * (1.0 if FX.flash_scale() >= 1.0 else 0.7)
    eye_k = D.eyes(f, plan, lamp_k)
    mk = D.marks(f, lamp_k)
    fl = D.flashlight(f, plan)
    cam, tgt, fov, roll = D.camera(f, plan, E.cu, calm)
    _sound(E, f, lamp_k, fk, cam)
    flash = D.flash_rgb(f, FX.flash_scale())
    dark = (f >= D.BLACK_F or (lamp_k <= 0.0 and mk <= 0.0 and fl <= 0.0 and f < D.CUT_F
                               and max(eye_k) <= 0.0))
    if dark:
        screen.fill((0, 0, 0))
        E.last_f = f
        return
    if (D.LUNGE_F + 10 <= f < D.BLACK_F and E.last_f == f - 1 and D.h01(plan.seed, f // 2, 9) < 0.25):
        screen.blit(E.last, (0, 0))                          # a dropped frame: the picture sticks
        E.last_f = f
        return
    r, buf, P_ = E.r, E.buf, E.post
    buf.fill((0, 0, 0))
    r.set_camera(cam, tgt, fov, roll)
    rows, bulb = E.lamp_rows(f, lamp_k)
    r.set_lights(_lights(E, f, fk, lamp_k, bulb, eye_k, mk, cam, fl))
    r.add_packed(E.room)
    r.add_packed(E.marks_rows(f, mk, D.pulse(f)))
    r.add_packed(rows[0])
    r.add_packed(rows[1])
    if D.station(f, plan) >= 1 or f >= D.CUT_F:
        r.add_packed(E.demon_rows(fk, eye_k))
    t_ms = f * 1000.0 / 60.0
    if lamp_k > 0.03:
        r.add_sprite(bulb, FX.glow(FX.WARM, 1.3, t_ms, seed=3, core=FX.WARM_CORE,
                                     intensity=min(1.0, lamp_k), max_px=64), layer=FX.FX_LAYER)
    for j, pair in enumerate(B.EYE_PAIRS):
        e = eye_k[pair]
        if e > 0.03:
            pos = fk[B.EYE_FIRST + j][1]
            near = _vec_sub(pos, cam)
            d2 = near[0] * near[0] + near[1] * near[1] + near[2] * near[2]
            close = d2 < 2.5
            if d2 < 0.09:
                continue                                      # inside the face: no halo
            r.add_sprite(pos, FX.glow((255, 36, 20), (0.11, 0.08, 0.07)[pair] * (0.8 + 0.4 * e), t_ms,
                                        pulse=0.2, flicker=0.15, seed=j + 1, core=(255, 170, 140),
                                        intensity=min(1.0, e), max_px=64 if close else 24),
                         layer=FX.FX_LAYER)
    r.flush(buf)
    q = D.post(f, plan)
    if calm < 1.0:
        q.update(tears=0, roll=0, barrel=q["barrel"] // 2, chroma=q["chroma"] // 2)
    if q["barrel"]:
        P_.barrel(buf, q["barrel"])
    P_.vignette(buf, q["vig"])
    if lamp_k > 0.0 or f >= D.CUT_F or max(eye_k) > 0.0:
        FX.grade(buf)                                 # the dark gaps stay true black
    P_.chroma(buf, q["chroma"])
    P_.tear(buf, random.Random(plan.seed * 7919 + f), q["tears"], q["tear_amp"])
    P_.roll(buf, q["roll"])
    P_.grain(buf, q["grain"], f)
    P_.flash(buf, flash)
    if q["squeeze"] is not None:
        P_.crt_off(buf, q["squeeze"])
    FX.present(buf, screen)
    if f >= D.LUNGE_F + 8:
        E.last.blit(screen, (0, 0))
    E.last_f = f


def begin(seed, size, sound=True):
    """Build the scene.  False = the 3D scare is unavailable; use the 2D one."""
    global _E
    stop()
    if not available():
        return False
    try:
        _E = _Egg(seed, size, sound)
        return True
    except Exception as exc:
        print("egg666: 3D scare unavailable, using the 2D one (%s)" % (exc,))
        stop()
        return False


def frame(screen, f):
    """Draw frame ``f`` (0..TOTAL-1) full screen.  False = it failed and has
    shut itself down; the caller falls back to the 2D scare."""
    if _E is None:
        return False
    try:
        _frame(_E, screen, f)
        return True
    except Exception as exc:
        print("egg666: 3D scare failed, falling back to 2D (%s)" % (exc,))
        stop()
        return False


def stop():
    """Free the GPU objects and cut the sound.  Safe to call any time."""
    global _E
    E, _E = _E, None
    if E is None:
        return
    if E.audio is not None:
        E.audio.stop()
    try:
        E.r.release()
    except Exception:
        pass
