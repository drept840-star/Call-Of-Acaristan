"""engine3d.gl - GPU backend for the low-poly renderer (ModernGL).

Drop-in replacement for ``SoftwareRenderer``: same camera, bake, add_* and
flush API, same PS1 look, but rasterised on the graphics card.

How it fits into a normal (non-OpenGL) pygame game
    A hidden, standalone OpenGL 3.3 context renders into an off-screen
    framebuffer at the cinematic's internal resolution. Each flush uploads
    the target Surface (sky etc. already painted by the caller), draws the
    geometry, and reads the pixels back into that Surface. The pygame window
    and every 2D system stay untouched; post FX (blur, rain, vignette,
    letterbox) keep working on the Surface exactly as before.

Painter semantics, reproduced with a depth buffer
    The software renderer sorts by ``layer * 1e6 - depth - bias``: a higher
    layer always paints over a lower one, and inside a layer the nearer face
    wins. Here every layer owns its own slice of the depth range (higher
    layer = nearer slice), so a single depth-tested pass gives the same
    ordering - with per-pixel accuracy instead of per-face sorting (no more
    popping or vanishing eyes).

    Sprites (pygame draw callbacks) are composited on the CPU after the read
    back, back-to-front, and masked against the depth buffer so geometry in
    front still hides them. Callbacks keep their exact blend modes.

Characters
    ``add_humanoid`` skins rig.Humanoid on the GPU: each actor's meshes are
    uploaded once, and posing only sends 17 bone matrices per frame. Python
    no longer transforms hundreds of vertices per actor, which is what makes
    crowds (mansion, helicopter chase) affordable.

Selecting the backend
    ``engine3d.Renderer(...)`` picks GL when available and falls back to the
    software renderer otherwise. Force one with the environment variable
    ``ACARISTAN_RENDERER=gl|software`` (default ``auto``).
"""
import math
import os
import sys

import numpy as np
import pygame

from .core import SoftwareRenderer
from .rig import PART_FB, SLOTS

__all__ = ["GLRenderer", "Renderer", "gl_available", "gl_info"]

# Depth layering: layer L (0..7) maps to [(7-L)/8, (8-L)/8). Higher = nearer.
_LAYER_SLOTS = 8.0
_VERT_FLOATS = 18          # pos3 col3 nrm3 flags4(shade,fog,double,layer) dbias1 tint4
_RIG_FLOATS = 15           # pos3 col3 nrm3 flags4 fb1 slot1
_N_SLOTS = len(SLOTS)
SPRITE_REACH_M = 3.5       # how far (metres) a sprite callback may paint from its anchor

_VERT_COMMON = """
uniform vec3 u_cam, u_right, u_up, u_fwd;
uniform float u_focal, u_hw, u_hh, u_near, u_far;
uniform bool u_snap;
out vec3 v_world;
out float v_z;
flat out vec3 v_col;
flat out vec3 v_nrm;
flat out vec4 v_flags;
flat out float v_dbias;
flat out vec4 v_tint;

vec4 project(vec3 w) {
    vec3 d = w - u_cam;
    float x = dot(d, u_right), y = dot(d, u_up), z = dot(d, u_fwd);
    v_world = w;
    v_z = z;
    float F = u_far, N = u_near;
    vec4 clip = vec4(x * u_focal / u_hw, y * u_focal / u_hh, (z * (F + N) - 2.0 * F * N) / (F - N), z);
    if (u_snap && z > N) {              // PS1 vertex jitter: snap to the pixel grid
        vec2 ndc = clip.xy / clip.w;
        ndc = floor(ndc * vec2(u_hw, u_hh) + 0.5) / vec2(u_hw, u_hh);
        clip.xy = ndc * clip.w;
    }
    return clip;
}
"""

VERT_WORLD = "#version 330\n" + _VERT_COMMON + """
in vec3 in_pos; in vec3 in_col; in vec3 in_nrm; in vec4 in_flags; in float in_dbias; in vec4 in_tint;
void main() {
    v_col = in_col; v_nrm = in_nrm; v_flags = in_flags; v_dbias = in_dbias; v_tint = in_tint;
    gl_Position = project(in_pos);
}
"""

VERT_RIG = "#version 330\n" + _VERT_COMMON + """
in vec3 in_pos; in vec3 in_col; in vec3 in_nrm; in vec4 in_flags; in float in_fb; in float in_slot;
uniform mat4 u_bones[%d];
uniform vec4 u_rtint;
uniform float u_rbias;
void main() {
    mat4 B = u_bones[int(in_slot + 0.5)];
    vec3 w = (B * vec4(in_pos, 1.0)).xyz;
    v_col = in_col; v_flags = in_flags; v_tint = u_rtint;
    v_nrm = normalize(mat3(B) * in_nrm);   // bones may carry Humanoid scale
    v_dbias = u_rbias - in_fb;
    gl_Position = project(w);
}
""" % _N_SLOTS

FRAG = """#version 330
in vec3 v_world;
in float v_z;
flat in vec3 v_col;
flat in vec3 v_nrm;
flat in vec4 v_flags;     // shade, fog, double_sided, layer
flat in float v_dbias;
flat in vec4 v_tint;
uniform vec3 u_cam;
uniform vec3 u_ldir, u_ltint;
uniform float u_amb, u_dif, u_sky;
uniform vec3 u_fog;
uniform float u_fog_start, u_fog_end, u_far;
uniform int u_split_mode;  // 0 all, 1 far only, 2 near only
uniform float u_split;
uniform bool u_dither;
uniform vec4 u_pl_pos[8];  // xyz + range (Phase 11 step 2 local lights)
uniform vec4 u_pl_col[8];  // rgb (0-255) + intensity
uniform vec4 u_pl_dir[8];  // spot dir + cone cos in w (w < -0.5 = point)
uniform int u_pl_n;
uniform float u_pl_mod;    // 0 = add the light colour (legacy), 1 = light * surface albedo
uniform float u_pl_gain;   // strength of the albedo-modulated mode
out vec4 f_color;

const float BAYER[16] = float[16](0., 8., 2., 10., 12., 4., 14., 6., 3., 11., 1., 9., 15., 7., 13., 5.);

void main() {
    float layer = v_flags.w;
    if (u_split_mode == 1 && !(v_z > u_split || layer < 0.5)) discard;
    if (u_split_mode == 2 &&  (v_z > u_split || layer < 0.5)) discard;
    vec3 n = v_nrm;
    float facing = dot(n, u_cam - v_world);
    if (facing <= 0.0 && v_flags.z < 0.5) discard;
    vec3 col = v_col;
    if (v_flags.x > 0.5) {                      // per-frame flat lighting (dynamic meshes)
        vec3 n2 = facing > 0.0 ? n : -n;
        float k = u_amb + u_dif * max(0.0, dot(n2, u_ldir)) + u_sky * n2.y;
        col = min(vec3(255.0), floor(col * k * u_ltint));
        for (int i = 0; i < 8; i++) {           // local point/spot lights
            if (i >= u_pl_n) break;
            vec3 dv = u_pl_pos[i].xyz - v_world;
            float d = length(dv);
            float rng = u_pl_pos[i].w;
            if (d >= rng || d < 0.001) continue;
            float fall = pow(1.0 - d / rng, 2.0) * u_pl_col[i].w;
            if (u_pl_dir[i].w > -0.5) {
                float ca = dot(-dv / d, u_pl_dir[i].xyz);
                if (ca <= u_pl_dir[i].w) continue;
                fall *= min(1.0, (ca - u_pl_dir[i].w) / 0.12);
            }
            float nd = dot(n2, dv / d);
            if (nd <= 0.0) continue;
            if (u_pl_mod > 0.5)
                col += v_col * (u_pl_col[i].rgb / 255.0) * (fall * nd * u_pl_gain);
            else
                col += u_pl_col[i].rgb * (fall * nd);
        }
        col = min(vec3(255.0), col);
    }
    if (v_flags.y > 0.5) {                      // not emissive
        if (v_tint.w > 0.0) col = floor(col + (v_tint.rgb - col) * v_tint.w);
        if (v_z > u_fog_start) {
            float k = min(1.0, (v_z - u_fog_start) / (u_fog_end - u_fog_start));
            col = floor(col + (u_fog - col) * k);
        }
    }
    if (u_dither) {                             // PS1 15-bit colour + ordered dither
        ivec2 p = ivec2(gl_FragCoord.xy) & 3;
        col = clamp(floor((col + (BAYER[p.y * 4 + p.x] / 16.0 - 0.5) * 8.0) / 8.0) * 8.0, 0.0, 255.0);
    }
    float lin = clamp((v_z + v_dbias) / u_far, 0.0, 1.0) * 0.999;
    float slot = clamp(floor(layer + 0.5), 0.0, 7.0);
    gl_FragDepth = ((7.0 - slot) + lin) / 8.0;
    f_color = vec4(col / 255.0, 1.0);
}
"""

# ── shared context ──────────────────────────────────────────────────────
_CTX = None
_CTX_ERR = None


def _context():
    """One hidden GL 3.3 context per process, created on first use."""
    global _CTX, _CTX_ERR
    if _CTX is not None or _CTX_ERR is not None:
        return _CTX
    try:
        import moderngl
        try:
            _CTX = moderngl.create_standalone_context(require=330)
        except Exception:
            if not sys.platform.startswith("linux"):
                raise
            _CTX = moderngl.create_standalone_context(require=330, backend="egl")
    except Exception as e:  # no driver / too old / moderngl missing
        _CTX_ERR = e
        _CTX = None
    return _CTX


def gl_available():
    return _context() is not None


def gl_info():
    ctx = _context()
    if ctx is None:
        return {"available": False, "error": repr(_CTX_ERR)}
    i = ctx.info
    return {"available": True, "vendor": i.get("GL_VENDOR"), "renderer": i.get("GL_RENDERER"),
            "version": i.get("GL_VERSION")}


class _Programs:
    """Compiled shaders + reusable buffers, shared by every GLRenderer."""
    _inst = None

    @classmethod
    def get(cls, ctx):
        if cls._inst is None:
            cls._inst = cls(ctx)
        return cls._inst

    def __init__(self, ctx):
        self.ctx = ctx
        self.world = ctx.program(vertex_shader=VERT_WORLD, fragment_shader=FRAG)
        self.rig = ctx.program(vertex_shader=VERT_RIG, fragment_shader=FRAG)


# ── geometry packing ────────────────────────────────────────────────────
def _pack_faces(verts, faces, prelit, bias=0.0, tint=None):
    """(verts, faces) in engine3d format -> float32 [n_tri*3, _VERT_FLOATS].

    faces: (idx, col, layer, double, nrm|None, emissive[, fb]).
    prelit=True: colours already lit (static Obj) - no per-frame shading."""
    if not faces or not verts:
        return None
    V = np.asarray(verts, dtype=np.float64)
    tri = []
    nf = len(faces)
    f_col = np.empty((nf, 3)); f_flags = np.empty((nf, 4)); f_db = np.empty(nf)
    f_ntri = np.empty(nf, dtype=np.int64)
    f_i3 = np.empty((nf, 3), dtype=np.int64)
    f_nrm = np.zeros((nf, 3)); has_n = np.zeros(nf, dtype=bool)
    ext = tri.extend
    for k, face in enumerate(faces):
        idx = face[0]
        n = len(idx)
        a = idx[0]
        for j in range(1, n - 1):
            ext((a, idx[j], idx[j + 1]))
        f_ntri[k] = n - 2
        f_i3[k] = idx[0], idx[1], idx[2]
        f_col[k] = face[1]
        em = face[5]
        f_flags[k] = (0.0 if (prelit or em) else 1.0, 0.0 if em else 1.0,
                      1.0 if face[3] else 0.0, float(face[2]))
        fb = face[6] if len(face) > 6 else 0.0
        f_db[k] = bias - fb
        nrm = face[4]
        if nrm is not None:
            f_nrm[k] = nrm
            has_n[k] = True
    if not tri:
        return None
    if not has_n.all():
        a = V[f_i3[:, 0]]; b = V[f_i3[:, 1]]; c = V[f_i3[:, 2]]
        cr = np.cross(b - a, c - a)
        ln = np.linalg.norm(cr, axis=1)
        ln[ln == 0] = 1.0
        cr /= ln[:, None]
        f_nrm[~has_n] = cr[~has_n]
    rep = np.repeat(np.arange(nf), f_ntri * 3)
    out = np.empty((len(tri), _VERT_FLOATS), dtype=np.float32)
    out[:, 0:3] = V[np.asarray(tri, dtype=np.int64)]
    out[:, 3:6] = f_col[rep]
    out[:, 6:9] = f_nrm[rep]
    out[:, 9:13] = f_flags[rep]
    out[:, 13] = f_db[rep]
    if tint is not None:
        out[:, 14:17] = tint[0]
        out[:, 17] = tint[1]
    else:
        out[:, 14:18] = 0.0
    return out


def _rig_template(hum):
    """Bind-pose vertex buffer for one Humanoid: every slot's part mesh."""
    rows = []
    for slot, key in enumerate(SLOTS):
        if key is None:
            continue
        if key == "rifle":
            if hum._rifle is None:
                continue
            verts = hum._rifle.verts
            faces = [(i, c, l, d, e, 0.0) for i, c, l, d, e in hum._rifle.faces]
        else:
            verts, f0 = hum._parts[key]
            fb = PART_FB.get(key, 0.0)
            faces = [(i, c, l, d, e, fb) for i, c, l, d, e in f0]
        for idx, col, layer, ds, em, fb in faces:
            a, b, c = verts[idx[0]], verts[idx[1]], verts[idx[2]]
            u = (b[0] - a[0], b[1] - a[1], b[2] - a[2]); w = (c[0] - a[0], c[1] - a[1], c[2] - a[2])
            nx, ny, nz = u[1] * w[2] - u[2] * w[1], u[2] * w[0] - u[0] * w[2], u[0] * w[1] - u[1] * w[0]
            ln = math.sqrt(nx * nx + ny * ny + nz * nz) or 1.0
            nrm = (nx / ln, ny / ln, nz / ln)
            flags = (0.0 if em else 1.0, 0.0 if em else 1.0, 1.0 if ds else 0.0, float(layer))
            for j in range(1, len(idx) - 1):
                for vi in (idx[0], idx[j], idx[j + 1]):
                    rows.append((*verts[vi], *col, *nrm, *flags, fb, float(slot)))
    return np.asarray(rows, dtype=np.float32)


# ── renderer ────────────────────────────────────────────────────────────
class GLRenderer(SoftwareRenderer):
    """GPU rasteriser with the SoftwareRenderer API. See module docstring."""
    backend = "gl"

    def __init__(self, w, h, fog=(96, 98, 104), fog_start=18.0, fog_end=210.0,
                 ps1_snap=False, dither=False):
        self.ctx = _context()
        if self.ctx is None:
            raise RuntimeError("OpenGL 3.3 unavailable: %r" % (_CTX_ERR,))
        self.progs = _Programs.get(self.ctx)
        super().__init__(w, h, fog=fog, fog_start=fog_start, fog_end=fog_end)
        self.ps1_snap = ps1_snap          # PS1 vertex jitter (off = matches software)
        self.dither = dither              # PS1 15-bit dither (off = matches software)
        ctx = self.ctx
        self._color = ctx.texture((w, h), 4)
        self._depth = ctx.depth_texture((w, h))
        self._fbo = ctx.framebuffer(color_attachments=[self._color], depth_attachment=self._depth)
        self._static_vbo = None
        self._static_vao = None
        self._static_sig = None
        self._static_ranges = []
        self._dyn_vbo = ctx.buffer(reserve=1 << 20, dynamic=True)
        self._dyn_vao = self._vao(self.progs.world, self._dyn_vbo, rig=False)
        self._rigs = {}                   # spec key -> (hum, vbo, vao, n)
        self.stats = {}
        self.begin()

    def _vao(self, prog, vbo, rig):
        if rig:
            fmt = "3f 3f 3f 4f 1f 1f"
            names = ["in_pos", "in_col", "in_nrm", "in_flags", "in_fb", "in_slot"]
        else:
            fmt = "3f 3f 3f 4f 1f 4f"
            names = ["in_pos", "in_col", "in_nrm", "in_flags", "in_dbias", "in_tint"]
        return self.ctx.vertex_array(prog, [(vbo, fmt, *names)])

    # scene --------------------------------------------------------------
    def invalidate_static(self):
        """Call after editing baked objects' geometry in place."""
        self._static_sig = None

    def _sync_static(self):
        objs = self.objs
        sig = (len(objs), id(objs[0]) if objs else 0, id(objs[-1]) if objs else 0)
        if sig == self._static_sig:
            return
        chunks, ranges, first = [], [], 0
        for o in objs:
            faces = [(f[0], f[1], f[2], f[3], f[4], f[5]) for f in o.faces]
            arr = _pack_faces(o.verts, faces, prelit=True)
            n = 0 if arr is None else len(arr)
            if n:
                chunks.append(arr)
            ranges.append((first, n))
            first += n
        if self._static_vbo is not None:
            self._static_vao.release()
            self._static_vbo.release()
            self._static_vbo = self._static_vao = None
        if chunks:
            data = np.concatenate(chunks)
            self._static_vbo = self.ctx.buffer(data.tobytes())
            self._static_vao = self._vao(self.progs.world, self._static_vbo, rig=False)
        self._static_ranges = ranges
        self._static_sig = sig

    def begin(self):
        self._items = []          # sprites + lines: (key, kind, data)
        self._dyn = []            # packed float32 chunks
        self._rig_draws = []      # (rig_entry, bones bytes, tint, bias)
        self._want_static = False

    def add_static(self):
        self._want_static = True

    def add_dynamic(self, wverts, faces, bias=0.0, tint=None):
        arr = _pack_faces(wverts, faces, prelit=False, bias=bias, tint=tint)
        if arr is not None:
            self._dyn.append(arr)

    def add_humanoid(self, hum, pose, pos, yaw, rifle_on=True, bias=0.0, tint=None,
                     shadow=None):
        places, joints, (px, py, pz) = hum.pose_world(pose, pos, yaw, rifle_on=rifle_on)
        spec_key = getattr(hum, "_gl_spec_key", None)
        if spec_key is None:  # actors with the same spec share one GPU mesh
            spec_key = hum._gl_spec_key = repr(sorted(hum.spec.items()))
        # The face decal is baked into the rig template, so a mid-scene
        # expression change needs its own template.  Mouth motion is left out
        # of the key on purpose: talking would rebuild the VBO every frame.
        key = (spec_key, getattr(hum, "_expression", "neutral"))
        entry = self._rigs.get(key)
        if entry is None:
            data = _rig_template(hum)
            vbo = self.ctx.buffer(data.tobytes())
            entry = (hum, vbo, self._vao(self.progs.rig, vbo, rig=True), len(data))
            self._rigs[key] = entry
        bones = np.zeros((_N_SLOTS, 4, 4), dtype=np.float32)   # zero = hidden slot
        for slot, _key, M, org, _g, _fb in places:
            b = bones[slot]
            # column-major mat4: b[col][row]
            b[0, 0], b[1, 0], b[2, 0] = M[0], M[1], M[2]
            b[0, 1], b[1, 1], b[2, 1] = M[3], M[4], M[5]
            b[0, 2], b[1, 2], b[2, 2] = M[6], M[7], M[8]
            b[3, 0], b[3, 1], b[3, 2], b[3, 3] = org[0] + px, org[1] + py, org[2] + pz, 1.0
        t = (0.0, 0.0, 0.0, 0.0) if tint is None else (*tint[0], float(tint[1]))
        self._rig_draws.append((entry, bones.tobytes(), t, float(bias)))
        sl, sb = shadow if shadow else (None, 0.0)
        self.add_blob_shadow((pos[0], pos[1] + 0.02, pos[2]), 0.34, 0.30, 0.40,
                             layer=sl, bias=sb)
        return joints

    def add_sprite(self, pos, draw_fn, layer=2, bias=0.0):
        p = self.project(pos)
        if p is None:
            return
        sx, sy, z = p
        self._items.append((layer * 1e6 - z - bias, "sprite",
                            (draw_fn, sx, sy, self.focal / z, z, layer, z + bias)))

    def add_blob_shadow(self, pos, rx, rz, strength=0.35, layer=None, bias=0.0):
        # The software implementation queues a (key, callable, args) item,
        # which _composite cannot read; queue the same disc as a GL sprite
        # item (layer 1: just above ground) so it depth-composites like
        # any sprite. Without this, every humanoid on the GL backend fed
        # a callable into _composite's line branch and crashed the flush.
        item = self._blob_item(pos, rx, rz, strength)
        if item is None:
            return
        draw, c = item
        lay = 1 if layer is None else layer
        self._items.append((lay * 1e6 - c[2], "sprite",
                            (draw, c[0], c[1], self.focal / c[2], c[2], lay, c[2] + bias)))

    def add_line3d(self, a, b, col, width=1, layer=3):
        from .core import _clip_near
        pa, pb = self.to_cam(a), self.to_cam(b)
        if pa[2] < self.NEAR and pb[2] < self.NEAR:
            return
        pts = _clip_near([pa, pb], self.NEAR, closed=False)
        if len(pts) < 2:
            return
        scr = [(self.w / 2 + x / z * self.focal, self.h / 2 - y / z * self.focal) for x, y, z in pts]
        self._items.append((layer * 1e6, "line", (col, width, scr, layer)))

    # drawing ------------------------------------------------------------
    @property
    def _far(self):
        return self.fog_end + 400.0

    def _set_uniforms(self, prog, split_mode, split):
        L = self.light
        # The shader holds 8 local lights; scenes opt in above the historic 4
        # through ``light_cap`` (the train does), everyone else keeps 4.
        cap = max(1, min(8, int(getattr(self, "light_cap", 4))))
        lights = self.lights[:cap]
        n_pl = len(lights)
        u = {
            "u_cam": self.cam, "u_right": self.right, "u_up": self.up, "u_fwd": self.fwd,
            "u_focal": self.focal, "u_hw": self.w / 2, "u_hh": self.h / 2,
            "u_near": self.NEAR, "u_far": self._far, "u_snap": bool(self.ps1_snap),
            "u_ldir": L.dir, "u_ltint": L.tint, "u_amb": L.ambient, "u_dif": L.diffuse,
            "u_sky": L.sky, "u_fog": self.fog, "u_fog_start": self.fog_start,
            "u_fog_end": self.fog_end, "u_split_mode": split_mode, "u_split": float(split),
            "u_dither": bool(self.dither),
            "u_pl_n": n_pl,
            "u_pl_mod": 1.0 if getattr(self, "light_albedo", False) else 0.0,
            "u_pl_gain": float(getattr(self, "light_gain", 1.0)),
            "u_pl_pos": [tuple(L["pos"]) + (float(L.get("range", 6.0)),)
                         for L in lights] + [(0.0, 0.0, 0.0, 1.0)] * (8 - n_pl),
            "u_pl_col": [tuple(float(c) for c in L["color"]) + (float(L.get("intensity", 1.0)),)
                         for L in lights] + [(0.0, 0.0, 0.0, 0.0)] * (8 - n_pl),
            "u_pl_dir": [(tuple(L["dir"]) + (float(L.get("cone", 0.7)),)) if L.get("kind") == "spot"
                         else (0.0, 0.0, 0.0, -1.0) for L in lights]
                        + [(0.0, 0.0, 0.0, -1.0)] * (8 - n_pl),
        }
        for k, v in u.items():
            if k in prog:
                prog[k].value = v

    def _render(self, surface, split_mode=0, split=0.0, items=None):
        """Upload surface -> draw geometry -> read back -> composite sprites."""
        import moderngl
        ctx = self.ctx
        w, h = self.w, self.h
        if surface.get_size() != (w, h):
            raise ValueError("GLRenderer target must be %dx%d" % (w, h))
        alpha = bool(surface.get_flags() & pygame.SRCALPHA)
        self._fbo.use()
        self._fbo.clear(depth=1.0)
        self._color.write(pygame.image.tobytes(surface, "RGBA", True))
        ctx.enable(moderngl.DEPTH_TEST)
        ctx.disable(moderngl.CULL_FACE | moderngl.BLEND)
        ntri = 0
        world = self.progs.world
        self._set_uniforms(world, split_mode, split)
        if self._want_static and self.objs:
            self._sync_static()
            if self._static_vao is not None:
                run_a = run_n = 0
                for o, (a, n) in zip(self.objs, self._static_ranges):
                    if not n:
                        continue
                    if o.visible:
                        if run_n and run_a + run_n == a:
                            run_n += n
                        else:
                            if run_n:
                                self._static_vao.render(moderngl.TRIANGLES, vertices=run_n, first=run_a)
                                ntri += run_n // 3
                            run_a, run_n = a, n
                if run_n:
                    self._static_vao.render(moderngl.TRIANGLES, vertices=run_n, first=run_a)
                    ntri += run_n // 3
        if self._dyn:
            data = self._dyn[0] if len(self._dyn) == 1 else np.concatenate(self._dyn)
            nbytes = data.nbytes
            if nbytes > self._dyn_vbo.size:
                # read the size BEFORE release: a released moderngl buffer is an
                # InvalidObject and .size raised on the first oversized frame
                grow = max(nbytes, self._dyn_vbo.size * 2)
                self._dyn_vao.release()
                self._dyn_vbo.release()
                self._dyn_vbo = ctx.buffer(reserve=grow, dynamic=True)
                self._dyn_vao = self._vao(world, self._dyn_vbo, rig=False)
            self._dyn_vbo.write(data.tobytes())
            self._dyn_vao.render(moderngl.TRIANGLES, vertices=len(data))
            ntri += len(data) // 3
        if self._rig_draws:
            rig = self.progs.rig
            self._set_uniforms(rig, split_mode, split)
            bones = rig["u_bones"]
            for (hum, vbo, vao, n), bb, tint, bias in self._rig_draws:
                bones.write(bb)
                rig["u_rtint"].value = tint
                rig["u_rbias"].value = bias
                vao.render(moderngl.TRIANGLES, vertices=n)
                ntri += n // 3
        # read back
        px = self._fbo.read(components=4, alignment=1)
        img = pygame.image.frombytes(px, (w, h), "RGBA", True)
        if alpha:
            surface.fill((0, 0, 0, 0))
            surface.blit(img, (0, 0), special_flags=pygame.BLEND_RGBA_ADD)
        else:
            surface.blit(img, (0, 0))
        items = self._items if items is None else items
        if items:
            depth = np.frombuffer(self._depth.read(alignment=1), dtype=np.float32).reshape(h, w)[::-1]
            self._composite(surface, items, depth, alpha)
        self.stats = {"tris": ntri, "items": len(items), "actors": len(self._rig_draws)}

    def _enc(self, layer, z):
        slot = min(7.0, max(0.0, float(int(layer + 0.5))))
        lin = min(1.0, max(0.0, z / self._far)) * 0.999
        return ((7.0 - slot) + lin) / 8.0

    def _composite(self, surface, items, depth, alpha):
        items = sorted(items, key=lambda it: it[0])
        W, H = self.w, self.h
        for _key, kind, d in items:
            if callable(kind):
                # Defensive: a software-format item (key, draw_fn, args)
                # that leaked into the GL queue still draws, exactly as
                # the software backend would run it (unoccluded), instead
                # of crashing the flush mid-cutscene.
                kind(surface, *d)
                continue
            if kind == "sprite":
                fn, sx, sy, scale, z, layer, zeff = d
                enc = self._enc(layer, zeff)
                reach = int(min(300, max(8, scale * SPRITE_REACH_M)))
                x0, y0 = int(sx) - reach, int(sy) - reach
                x1, y1 = int(sx) + reach + 1, int(sy) + reach + 1
                draw = lambda s, fn=fn, sx=sx, sy=sy, scale=scale, z=z: fn(s, sx, sy, scale, z)
            else:
                col, width, scr, layer = d
                enc = self._enc(layer, 0.0)
                if len(scr) < 2:
                    continue          # degenerate line: nothing to draw
                (ax, ay), (bx, by) = scr[0], scr[1]
                pad = int(width) + 2
                x0, x1 = int(min(ax, bx)) - pad, int(max(ax, bx)) + pad + 1
                y0, y1 = int(min(ay, by)) - pad, int(max(ay, by)) + pad + 1
                draw = lambda s, col=col, scr=scr, width=width: pygame.draw.line(s, col, scr[0], scr[1], width)
            x0, y0 = max(0, x0), max(0, y0)
            x1, y1 = min(W, x1), min(H, y1)
            if x1 <= x0 or y1 <= y0:
                draw(surface)                      # off-screen anchor: nothing to occlude
                continue
            occ = depth[y0:y1, x0:x1] < enc - 1e-6
            if not occ.any():
                draw(surface)
                continue
            rect = pygame.Rect(x0, y0, x1 - x0, y1 - y0)
            before = surface.subsurface(rect).copy()
            draw(surface)
            occ_t = occ.T
            dst = pygame.surfarray.pixels3d(surface)
            src = pygame.surfarray.pixels3d(before)
            dst[x0:x1, y0:y1][occ_t] = src[occ_t]
            del dst, src
            if alpha:
                da = pygame.surfarray.pixels_alpha(surface)
                sa = pygame.surfarray.pixels_alpha(before)
                da[x0:x1, y0:y1][occ_t] = sa[occ_t]
                del da, sa

    def flush(self, surface=None):
        surface = surface or self.surface
        self._render(surface)
        self.begin()

    def _split_items(self, split_depth):
        far, near = [], []
        for it in self._items:
            if it[1] == "sprite":
                layer, depth = it[2][5], it[2][4]
            else:
                layer, depth = it[2][3], 0.0
            (far if depth > split_depth or layer == 0 else near).append(it)
        return far, near

    def flush_split(self, surface, split_depth, mid_fn):
        far, near = self._split_items(split_depth)
        self._render(surface, 1, split_depth, far)
        mid_fn(surface)
        self._render(surface, 2, split_depth, near)
        self.begin()

    def flush_near_blur(self, surface, split_depth, blur_fn):
        far, near = self._split_items(split_depth)
        self._render(surface, 1, split_depth, far)
        tmp = pygame.Surface(surface.get_size(), pygame.SRCALPHA)
        tmp.fill((0, 0, 0, 0))
        self._render(tmp, 2, split_depth, near)
        surface.blit(blur_fn(tmp), (0, 0))
        self.begin()

    def release(self):
        for _h, vbo, vao, _n in self._rigs.values():
            vao.release(); vbo.release()
        self._rigs.clear()
        for o in (self._static_vao, self._static_vbo, self._dyn_vao, self._dyn_vbo,
                  self._fbo, self._color, self._depth):
            if o is not None:
                o.release()
        self._static_vao = self._static_vbo = None


_WARNED = False


def Renderer(w, h, fog=(96, 98, 104), fog_start=18.0, fog_end=210.0, **kw):
    """Backend-selecting constructor (keeps the old ``Renderer(...)`` call sites).

    ACARISTAN_RENDERER=auto (default) | gl | software."""
    global _WARNED
    mode = os.environ.get("ACARISTAN_RENDERER", "auto").strip().lower()
    if mode != "software":
        try:
            return GLRenderer(w, h, fog=fog, fog_start=fog_start, fog_end=fog_end, **kw)
        except Exception as e:
            if mode == "gl":
                raise
            if not _WARNED:
                print("engine3d: GPU renderer unavailable, using software (%s)" % (e,))
                _WARNED = True
    kw.pop("ps1_snap", None); kw.pop("dither", None)
    return SoftwareRenderer(w, h, fog=fog, fog_start=fog_start, fog_end=fog_end)
