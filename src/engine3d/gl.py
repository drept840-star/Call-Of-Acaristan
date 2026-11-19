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
from collections import OrderedDict
import math
import os
import sys

import numpy as np
import pygame

from . import textures as _tex
from .core import SoftwareRenderer, v_cross, v_norm
from .rig import PART_FB, SLOTS
from .textures import Tex
from .gl_post import PostPipeline
from .gl_sprites import DecalPass, ParticlePass, SkyPass, SpriteBatch

__all__ = ["GLRenderer", "Renderer", "gl_available", "gl_info"]

# Depth layering: layer L (0..7) maps to [(7-L)/8, (8-L)/8). Higher = nearer.
_LAYER_SLOTS = 8.0
_VERT_FLOATS = 21          # pos3 col3 nrm3 flags4(shade,fog,double,layer) dbias1 tint4 uv2 tex1
_RIG_FLOATS = 15           # pos3 col3 nrm3 flags4 fb1 slot1
_N_SLOTS = len(SLOTS)
_TEX_UNIT = 7              # engine3d.textures layers (texture array); unit 0 is the colour target
_SH_UNIT = 6               # sun shadow map (set_sun_shadow)
_SPOT0_UNIT = 8            # dynamic spotlight shadow map 0
_SPOT1_UNIT = 9            # dynamic spotlight shadow map 1
_EXTRA0_UNIT = 10          # per-stage extra texture 0 (M6 top map)
_EXTRA1_UNIT = 11          # per-stage extra texture 1 (M6 ground map)
_EXTRA2_UNIT = 12          # per-stage extra texture 2 (M6 props atlas)
_PL_UNIT = 13              # (64, 4) RGBA32F packed local lights data texture
MAX_LIGHTS = 64
SPOT_MAP = 512
SPRITE_REACH_M = 3.5       # how far (metres) a sprite callback may paint from its anchor
# Light callbacks (fn.light) are world objects at their lamp's depth, not
# painter-layer decals: they encode against the world layer so walls, the
# carriage and actors occlude them per pixel.  ``_LIGHT_BIAS_M`` clears the
# fixture's own emissive head without letting a wall 1 m in front pass.
_WORLD_LAYER = 2
_LIGHT_BIAS_M = 0.35
_LIGHT_EASE_MS = 80.0


_UNSET = object()
_PROBE_DX = np.tile(np.array((-3, 0, 3), dtype=np.int64), 3)      # 3x3 light-anchor probe
_PROBE_DY = np.repeat(np.array((-3, 0, 3), dtype=np.int64), 3)


def _same(a, b):
    """Uniform value unchanged?  Arrays compare element-wise and have no single
    truth value, so they count as changed."""
    try:
        return bool(a == b)
    except Exception:
        return False


_PHYS8_LUT = None


def _phys8(raw, h, w):
    """Physical depth (f16, bottom-up rows) -> top-down 0..254 bytes at 255/64 m.
    One gather through a table of every f16 bit pattern: the same bytes as
    clip(round(d * 255 / 64), 0, 254) for a fraction of the cost."""
    global _PHYS8_LUT
    if _PHYS8_LUT is None:
        d = np.arange(65536, dtype=np.uint16).view(np.float16).astype(np.float32)
        with np.errstate(invalid="ignore"):
            _PHYS8_LUT = np.clip(np.round(d * (255.0 / 64.0)), 0, 254).astype(np.uint8)
    return _PHYS8_LUT[np.frombuffer(raw, dtype=np.uint16).reshape(h, w)[::-1]]


def _now_ms():
    """Game clock for light-visibility easing (0 if the engine is absent)."""
    try:
        from engine.core import now_ms
        return int(now_ms())
    except Exception:
        return 0

_VERT_COMMON = """
uniform vec3 u_cam, u_right, u_up, u_fwd;
uniform float u_focal, u_hw, u_hh, u_near, u_far;
uniform bool u_snap;
uniform bool u_ortho;              // sun shadow pass: orthographic from the light
uniform float u_ohw, u_ohh;        // its half extents, metres
uniform float u_uvs;               // texel scale this frame (tex_scale): < 1 = bigger texels
out vec3 v_world;
out float v_z;
flat out vec3 v_col;
flat out vec3 v_nrm;
flat out vec4 v_flags;
flat out float v_dbias;
flat out vec4 v_tint;
out vec2 v_uv;             // texture tiles, world-space (textures.py)
flat out float v_tex;      // texture layer, < 0 = untextured

vec4 project(vec3 w) {
    vec3 d = w - u_cam;
    float x = dot(d, u_right), y = dot(d, u_up), z = dot(d, u_fwd);
    v_world = w;
    v_z = z;
    float F = u_far, N = u_near;
    if (u_ortho) return vec4(x / u_ohw, y / u_ohh, z / F * 2.0 - 1.0, 1.0);
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
in vec2 in_uv; in float in_tex;
void main() {
    v_col = in_col; v_nrm = in_nrm; v_flags = in_flags; v_dbias = in_dbias; v_tint = in_tint;
    v_uv = (in_tex < -1.5) ? in_uv : (in_uv * u_uvs); v_tex = in_tex;
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
    v_uv = vec2(0.0); v_tex = -1.0;      // characters stay flat
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
in vec2 v_uv;
flat in float v_tex;
uniform sampler2DArray u_tex;   // texel / the texture's mean (textures.py)
uniform sampler2D u_extra0, u_extra1, u_extra2;
uniform sampler2D u_pl_tex;     // (64, 4) RGBA32F local lights
uniform vec3 u_cam;
uniform vec3 u_right, u_up, u_fwd;
uniform vec3 u_ldir, u_ltint;
uniform float u_amb, u_dif, u_sky;
uniform float u_char;      // 1 = rigged character: wrapped key, camera fill, rim (core.Light.char_k)
uniform float u_cpop;      // top-down readability: top light + stronger rim on rigs (char_pop)
uniform vec3 u_fog;
uniform float u_fog_start, u_fog_end, u_far;
uniform int u_split_mode;  // 0 all, 1 far only, 2 near only
uniform float u_split;
uniform bool u_dither;
uniform ivec4 u_tile_mask[96]; // 12x8 screen tiles, 4x16-bit light masks = 64 lights
uniform vec2 u_tile_inv;       // (12/w, 8/h)
uniform int u_pl_n;
uniform sampler2DShadow u_spot_tex0, u_spot_tex1;
uniform vec3 u_spot_cam[2], u_spot_right[2], u_spot_up[2], u_spot_fwd[2];
uniform float u_spot_tan[2], u_spot_near[2], u_spot_far[2];
uniform float u_pl_mod;    // 0 = add the light colour (legacy), 1 = light * surface albedo
uniform float u_pl_gain;   // strength of the albedo-modulated mode
uniform vec4 u_pool_pos[32];  // lamp pools (set_pools): lamp head xyz + radius
uniform vec4 u_pool_col[32];  // rim rgb (0-255) + intensity
uniform vec3 u_pool_hot[32];  // rgb (0-255) at the pool's centre
uniform int u_pool_n;
uniform float u_glit[32];     // glitter per texture layer (textures.glitter)
uniform float u_glit_k;       // the scene's glitter, 0 = none
uniform float u_refl[32];     // surface reflectivity per texture layer
uniform float u_wet, u_marble;
uniform float u_depth_alpha;  // 1 = pack physical depth into alpha (opaque target)
uniform bool u_sh_pass;       // writing the sun shadow map: depth only
uniform bool u_sh_on;         // receiving the sun shadow (set_sun_shadow)
uniform sampler2DShadow u_sh_tex;
uniform vec3 u_sh_cam, u_sh_right, u_sh_up, u_sh_fwd;
uniform float u_sh_half, u_sh_far, u_sh_k, u_sh_texel;
uniform vec3 u_sh_col;        // multiplier at full shadow
uniform float u_hdr_emissive; // > 1.0 in HDR mode for bright emissives/flashes
layout(location = 0) out vec4 f_color;
layout(location = 1) out vec4 f_aux;
layout(location = 2) out float f_pdepth;

const float BAYER[16] = float[16](0., 8., 2., 10., 12., 4., 14., 6., 3., 11., 1., 9., 15., 7., 13., 5.);
const float TEX_SIZE = 64.0;  // textures.SIZE

float hash12(vec2 p) {
    vec3 p3 = fract(p.xyx * 0.1031);
    p3 += dot(p3, p3.yzx + 33.33);
    return fract((p3.x + p3.y) * p3.z);
}

float spot_shadow(int slot, vec3 wpos, vec3 n2) {
    vec3 d = wpos + n2 * 0.05 - u_spot_cam[slot];
    float z = dot(d, u_spot_fwd[slot]);
    float N = u_spot_near[slot], F = u_spot_far[slot];
    if (z <= N || z >= F) return 1.0;
    float t = u_spot_tan[slot] * z;
    vec2 uv = vec2(dot(d, u_spot_right[slot]), dot(d, u_spot_up[slot])) / t * 0.5 + 0.5;
    if (any(lessThan(uv, vec2(0.0))) || any(greaterThan(uv, vec2(1.0)))) return 1.0;
    float zb = max(N + 0.001, z - 0.06);
    float ref = 0.5 + 0.5 * ((F + N) - 2.0 * F * N / zb) / (F - N);
    return (slot == 0) ? texture(u_spot_tex0, vec3(uv, ref)) : texture(u_spot_tex1, vec3(uv, ref));
}

void main() {
    // sampled before any discard or branch so the mip choice has its derivatives
    // (a half-mip bias toward the sharper level: PS2-crisp, still no sparkle)
    vec3 texel = texture(u_tex, vec3(v_uv, max(v_tex, 0.0)), -0.5).rgb;
    vec3 ex0 = texture(u_extra0, v_uv).rgb;
    vec3 ex1 = texture(u_extra1, v_uv).rgb;
    vec3 ex2 = texture(u_extra2, v_uv).rgb;
    if (u_sh_pass) {                            // emissive faces (glows, beams) cast nothing
        if (v_flags.y < 0.5) discard;
        gl_FragDepth = gl_FragCoord.z;
        f_color = vec4(0.0);
        f_aux = vec4(0.5, 0.5, 1.0, 0.0);
        f_pdepth = 1000.0;
        return;
    }
    vec2 tc = v_uv * TEX_SIZE;                      // texel coordinates
    float tpp = max(fwidth(tc.x), fwidth(tc.y));    // texels under one pixel
    float layer = v_flags.w;
    if (u_split_mode == 1 && !(v_z > u_split || layer < 0.5)) discard;
    if (u_split_mode == 2 &&  (v_z > u_split || layer < 0.5)) discard;
    vec3 n = v_nrm;
    float facing = dot(n, u_cam - v_world);
    if (facing <= 0.0 && v_flags.z < 0.5) discard;
    vec3 alb = v_col;
    if (v_tex < -1.5) {
        int eslot = int(-v_tex - 1.25);
        alb = ((eslot == 0) ? ex0 : ((eslot == 1) ? ex1 : ex2)) * 255.0;
    } else if (v_tex >= 0.0) {
        alb = v_col * texel;
    }
    vec3 col = alb;
    vec3 n2 = facing > 0.0 ? n : -n;
    float hdr_cap = u_hdr_emissive > 1.01 ? 420.0 : 255.0;
    if (v_flags.x > 0.5) {                      // per-frame flat lighting (dynamic meshes)
        float k = u_amb + u_dif * max(0.0, dot(n2, u_ldir)) + u_sky * n2.y;
        float rim = 0.0;
        if (u_char > 0.5) {
            float ndv = max(0.0, dot(n2, normalize(u_cam - v_world)));
            k = u_amb + u_dif * 1.12 * max(0.0, (dot(n2, u_ldir) + 0.2) / 1.2) + u_sky * n2.y + 0.12 * ndv;
            rim = 0.7 * (1.0 + u_cpop) * pow(1.0 - ndv, 3.0);
            k += u_cpop * 0.32 * max(0.0, n2.y);
        }
        col = min(vec3(255.0), floor(col * (k + rim) * u_ltint));
    } else if (v_flags.y > 0.5 && (u_pool_n > 0 || u_glit_k > 0.0)) {
        // Baked faces: lamp pools and snow glitter. A pool warms by the
        // surface's brightness, not its hue, so blue-white snow under a
        // sodium lamp goes cream at the centre and amber at the rim.
        vec3 V = normalize(u_cam - v_world);
        float lum = dot(alb, vec3(0.299, 0.587, 0.114)) / 255.0;
        // Glitter: a few texels hold a tilted facet that flashes when it
        // mirrors the key or a lamp into the lens. One or two pixels at the
        // texel's centre, world-locked, gone where a pixel spans a texel.
        vec3 fac = vec3(0.0);
        float g = v_tex >= 0.0 ? u_glit[int(v_tex + 0.5)] * u_glit_k : 0.0;
        if (g > 0.0 && n2.y > 0.5) {
            vec2 cell = floor(tc);
            if (hash12(cell) < 0.10 * g) {
                vec2 sub = abs(fract(tc) - 0.5) / max(tpp, 1e-4);
                float pt = step(max(sub.x, sub.y), 0.7) * clamp(2.2 - 1.6 * tpp, 0.0, 1.0);
                fac = normalize(vec3(hash12(cell + 7.31) - 0.5, 0.6,
                                     hash12(cell + 13.7) - 0.5)) * pt;
            }
        }
        vec3 add = 200.0 * u_ltint * smoothstep(0.975, 0.995, dot(fac, normalize(u_ldir + V)));
        for (int i = 0; i < 32; i++) {
            if (i >= u_pool_n) break;
            vec3 dv = u_pool_pos[i].xyz - v_world;
            float f = 1.0 - length(dv.xz) / u_pool_pos[i].w;
            if (f <= 0.0 || dv.y <= 0.0) continue;
            vec3 L = normalize(dv);
            float nd = dot(n2, L);
            if (nd <= 0.0) continue;
            float k = f * f * u_pool_col[i].w;
            vec3 pc = mix(u_pool_col[i].rgb, u_pool_hot[i], f * f);
            add += pc * (lum * k * nd);
            add += pc * (min(1.0, 2.0 * k) * smoothstep(0.975, 0.995, dot(fac, normalize(L + V))));
        }
        col = min(vec3(hdr_cap), col + add);
    }
    if (v_flags.y > 0.5 && u_pl_n > 0) {
        ivec2 tile = clamp(ivec2(gl_FragCoord.xy * u_tile_inv), ivec2(0), ivec2(11, 7));
        ivec4 mask = u_tile_mask[tile.y * 12 + tile.x];
        vec3 ladd = vec3(0.0);
        bool use_mod = (u_pl_mod > 0.5) || (v_flags.x < 0.5);
        float lgain = (v_flags.x < 0.5 && u_pl_mod <= 0.5) ? 1.15 : u_pl_gain;
        for (int w = 0; w < 4; w++) {
            int bits = mask[w];
            if (bits == 0) continue;
            for (int b = 0; b < 16; b++) {
                if ((bits & (1 << b)) == 0) continue;
                int i = w * 16 + b;
                if (i >= u_pl_n) break;
                vec4 p0 = texelFetch(u_pl_tex, ivec2(i, 0), 0);
                vec4 c0 = texelFetch(u_pl_tex, ivec2(i, 1), 0);
                vec4 d0 = texelFetch(u_pl_tex, ivec2(i, 2), 0);
                vec4 s0 = texelFetch(u_pl_tex, ivec2(i, 3), 0);
                vec3 dv = p0.xyz - v_world;
                float d = length(dv);
                float rng = p0.w;
                if (d >= rng || d < 0.001) continue;
                float fall = pow(1.0 - d / rng, 2.0) * c0.w;
                if (d0.w > -0.5) {
                    float ca = dot(-dv / d, d0.xyz);
                    if (ca <= d0.w) continue;
                    fall *= min(1.0, (ca - d0.w) / 0.12);
                }
                float nd = dot(n2, dv / d);
                if (nd <= 0.0) continue;
                int sh = int(floor(s0.x + 0.5));
                float lit_s = (sh == 0) ? spot_shadow(0, v_world, n2)
                            : ((sh == 1) ? spot_shadow(1, v_world, n2) : 1.0);
                if (lit_s <= 0.001) continue;
                if (use_mod)
                    ladd += alb * (c0.rgb / 255.0) * (fall * nd * lgain * lit_s);
                else
                    ladd += c0.rgb * (fall * nd * lit_s);
            }
        }
        col = min(vec3(hdr_cap), col + ladd);
    }
    if (v_flags.y > 0.5) {                      // not emissive
        // Sun shadow map, hardware 2x2 PCF. Only faces turned to the sun
        // receive: the rest keep the key light (top-down suns sit behind the
        // set, so camera-facing walls and fronts would all go dark).
        float nl = dot(n2, -u_sh_fwd);
        if (u_sh_on && nl > 0.0) {
            vec3 d = v_world + n2 * (1.5 * u_sh_texel) - u_sh_cam;
            vec2 uv = vec2(dot(d, u_sh_right), dot(d, u_sh_up)) / u_sh_half * 0.5 + 0.5;
            if (all(greaterThan(uv, vec2(0.0))) && all(lessThan(uv, vec2(1.0)))) {
                float lit = texture(u_sh_tex, vec3(uv, (dot(d, u_sh_fwd) - 0.02) / u_sh_far));
                col = floor(col * mix(vec3(1.0), u_sh_col, u_sh_k * (1.0 - lit) * smoothstep(0.0, 0.25, nl)));
            }
        }
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
    vec3 hdr_col = col / 255.0;
    if (v_flags.y < 0.5 && u_hdr_emissive > 1.01) {
        float mx = max(hdr_col.r, max(hdr_col.g, hdr_col.b));
        hdr_col *= mix(1.0, u_hdr_emissive, smoothstep(0.55, 0.95, mx));
    }
    f_color = vec4(hdr_col, 1.0);
    vec3 vn = vec3(dot(n2, u_right), dot(n2, u_up), dot(n2, u_fwd));
    float mat_id = 0.25;
    if (v_flags.y < 0.5) {
        mat_id = 1.0;
    } else if (u_char > 0.5) {
        mat_id = 0.75;
    } else if (n2.y > 0.80) {
        float rtex = v_tex >= 0.0 ? u_refl[int(v_tex + 0.5)] : (v_tex < -1.5 ? 0.55 : 0.25);
        if (u_marble > 0.05 || (u_wet > 0.02 && rtex > 0.05)) mat_id = 0.50;
    }
    f_aux = vec4(vn * 0.5 + 0.5, mat_id);
    f_pdepth = max(0.0, v_z + v_dbias);
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
        self._atlas = None
        self._atlas_ver = -1
        self._uni = {}

    def uniforms(self, prog):
        """``{name: [Uniform, last value]}`` for one program, built once:
        ``name in prog`` walks every member and ``prog[name]`` makes a new
        wrapper on each call, which was ~0.3 ms of every frame."""
        d = self._uni.get(id(prog))
        if d is None:
            import moderngl
            d = {}
            for name in prog:
                m = prog[name]
                if isinstance(m, moderngl.Uniform):
                    d[name] = [m, _UNSET]
            self._uni[id(prog)] = d
        return d

    def atlas(self):
        """engine3d.textures's layers as one texture array, re-uploaded when a
        texture is added. Nearest texels, nearest mip: crisp up close, no
        sparkle on far snow."""
        ver = _tex.version()
        if self._atlas is None or self._atlas_ver != ver:
            import moderngl
            arr = _tex.stack()
            if arr is None:
                rgba = np.ones((1, 1, 1, 4), dtype=np.float16)
            else:
                n, h, w, _ = arr.shape
                rgba = np.ones((n, h, w, 4), dtype=np.float16)
                rgba[..., :3] = arr
            if self._atlas is not None:
                self._atlas.release()
            n, h, w, _ = rgba.shape
            # GL_RGBA16F is OpenGL 3.3 color-renderable; GL_RGB16F is not, which
            # can cause glGenerateMipmap to leave mip levels >= 1 black.
            t = self.ctx.texture_array((w, h, n), 4, rgba.tobytes(), dtype="f2")
            t.build_mipmaps()
            t.filter = (moderngl.NEAREST_MIPMAP_NEAREST, moderngl.NEAREST)
            self._atlas, self._atlas_ver = t, ver
        return self._atlas


# ── geometry packing ────────────────────────────────────────────────────
def _cross3(a, b):
    """Row-wise cross product of (n, 3) arrays.  ``np.cross`` costs ~30 us of
    axis bookkeeping per call, and the packers call it per mesh, every frame."""
    out = np.empty_like(a)
    out[:, 0] = a[:, 1] * b[:, 2] - a[:, 2] * b[:, 1]
    out[:, 1] = a[:, 2] * b[:, 0] - a[:, 0] * b[:, 2]
    out[:, 2] = a[:, 0] * b[:, 1] - a[:, 1] * b[:, 0]
    return out


def _unit(a):
    """Normalise (n, 3) rows in place (zero rows stay zero)."""
    ln = np.sqrt(np.einsum("ij,ij->i", a, a))
    ln[ln == 0] = 1.0
    a /= ln[:, None]
    return a


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
    f_tex = np.full(nf, -1.0); f_uvk = np.zeros(nf)
    exp_uv = []
    ext = tri.extend
    for k, face in enumerate(faces):
        idx = face[0]
        n = len(idx)
        a = idx[0]
        for j in range(1, n - 1):
            ext((a, idx[j], idx[j + 1]))
        f_ntri[k] = n - 2
        f_i3[k] = idx[0], idx[1], idx[2]
        col = f_col[k] = face[1]
        if type(col) is Tex:
            f_tex[k] = col.tex
            f_uvk[k] = col.uvk
        f6 = face[6] if len(face) > 6 else None
        f7 = face[7] if len(face) > 7 else None
        uv_tag = f7 if (isinstance(f7, tuple) and len(f7) == 3 and f7[0] == "uv") else (
            f6 if (isinstance(f6, tuple) and len(f6) == 3 and f6[0] == "uv") else None
        )
        if uv_tag is not None:
            f_tex[k] = float(uv_tag[1])
            uvs = uv_tag[2]
            for j in range(1, n - 1):
                exp_uv.extend((uvs[0], uvs[j], uvs[j + 1]))
        else:
            for j in range(1, n - 1):
                exp_uv.extend(((0.0, 0.0), (0.0, 0.0), (0.0, 0.0)))
        em = face[5]
        f_flags[k] = (0.0 if (prelit or em) else 1.0, 0.0 if em else 1.0,
                      1.0 if face[3] else 0.0, float(face[2]))
        fb = f6 if (len(face) > 6 and uv_tag is not f6) else 0.0
        f_db[k] = bias - fb
        nrm = face[4]
        if nrm is not None:
            f_nrm[k] = nrm
            has_n[k] = True
    if not tri:
        return None
    if not has_n.all():
        a = V[f_i3[:, 0]]; b = V[f_i3[:, 1]]; c = V[f_i3[:, 2]]
        cr = _unit(_cross3(b - a, c - a))
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
    out[:, 18:20] = 0.0
    out[:, 20] = f_tex[rep]
    exp_sel = f_tex < -1.5
    if exp_sel.any():
        erows = exp_sel[rep]
        out[erows, 18:20] = np.asarray(exp_uv, dtype=np.float32)[erows]
    sel = f_tex >= 0.0
    if sel.any():
        T, B = _tex_frame(V, f_i3, f_nrm, sel)
        rows = sel[rep]
        fr = rep[rows]
        P = V[np.asarray(tri, dtype=np.int64)[rows]]
        k = f_uvk[fr]
        out[rows, 18] = np.einsum("ij,ij->i", P, T[fr]) * k
        out[rows, 19] = -np.einsum("ij,ij->i", P, B[fr]) * k   # image top = up the wall
    return out


def _tex_frame(V, f_i3, f_nrm, sel):
    """Per-face tiling axes (T, B) for the faces in ``sel`` (zero elsewhere).

    Walls and slopes: T runs level along the face, B up it, so bricks and
    planks stay level whatever way the wall turns. Floors and ceilings follow
    their first edge, snapped to a world axis when it is within ~14 degrees:
    ground pieces line up with each other and a turned crate keeps its planks.
    Every face of a plane gets the same axes, so a subdivided slab tiles
    without seams."""
    nf = len(f_nrm)
    T = np.zeros((nf, 3)); B = np.zeros((nf, 3))
    n = f_nrm[sel]
    b = np.array([0.0, 1.0, 0.0]) - n * n[:, 1:2]
    t = _cross3(n, b)
    flat = np.abs(n[:, 1]) > 0.9
    if flat.any():
        i3 = f_i3[sel][flat]
        e = V[i3[:, 1]] - V[i3[:, 0]]
        e[:, 1] = 0.0
        _unit(e)
        e[np.abs(e[:, 0]) > 0.97] = (1.0, 0.0, 0.0)
        e[np.abs(e[:, 2]) > 0.97] = (0.0, 0.0, 1.0)
        t[flat] = e
        b[flat] = np.stack((e[:, 2], np.zeros(len(e)), -e[:, 0]), axis=1)   # up x e
    _unit(t)
    _unit(b)
    T[sel] = t
    B[sel] = b
    return T, B


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
        self.hdr = False                  # HDR emissives + bloom enabled by 3D/2.5D hosts
        ctx = self.ctx
        self._color = ctx.texture((w, h), 4, dtype="f2")
        self._aux = ctx.texture((w, h), 4)
        self._aux.filter = (self.ctx.NEAREST, self.ctx.NEAREST)
        self._aux.repeat_x = self._aux.repeat_y = False
        self._pdepth = ctx.texture((w, h), 1, dtype="f2")
        self._pdepth.filter = (self.ctx.NEAREST, self.ctx.NEAREST)
        self._pdepth.repeat_x = self._pdepth.repeat_y = False
        self._depth = ctx.depth_texture((w, h))
        self._fbo = ctx.framebuffer(color_attachments=[self._color, self._aux, self._pdepth],
                                    depth_attachment=self._depth)
        self._color_fbo = ctx.framebuffer(color_attachments=[self._color],
                                          depth_attachment=self._depth)
        self._sky = SkyPass(ctx)
        self._sprites = SpriteBatch(ctx)
        self._part_batch = ParticlePass(ctx)
        self._decals_batch = DecalPass(ctx)
        self._post = PostPipeline(ctx)
        self._static_vbo = None
        self._static_vao = None
        self._static_sig = None
        self._static_ranges = []
        self._static_runs = None
        self._dyn_vbo = ctx.buffer(reserve=1 << 20, dynamic=True)
        self._dyn_vao = self._vao(self.progs.world, self._dyn_vbo, rig=False)
        self._dyn_cat = None              # staging array for _draw_dyn
        self._dyn_bounds = []
        self._rigs = {}                   # spec key -> (hum, vbo, vao, n)
        self._light_vis = {}              # quantised anchor -> (eased v, ms)
        self._light_tmp_s = None          # reusable (W, H) additive buffer
        self._light_mask_s = None         # reusable (W, H) occlusion mask
        self._comp_buf = None             # reusable (W, H) sprite-occlusion backup
        self._bones_buf = np.zeros((_N_SLOTS, 4, 4), dtype=np.float32)
        self._vis_frame = 0
        self._res = OrderedDict()         # id(rows) -> (rows, vbo, vao, n, center, rad)
        self._sh_tex = ctx.depth_texture((1, 1))   # sun shadow map, sized on first use
        self._sh_fbo = None
        self._spot_tex = [ctx.depth_texture((1, 1)), ctx.depth_texture((1, 1))]
        self._spot_fbo = [None, None]
        self._spot_active = []
        self._pl_tex = ctx.texture((MAX_LIGHTS, 4), 4, dtype="f4")
        self._pl_tex.filter = (ctx.NEAREST, ctx.NEAREST)
        self._pl_tex.repeat_x = self._pl_tex.repeat_y = False
        self._pl_buf = np.zeros((4, MAX_LIGHTS, 4), dtype=np.float32)
        self._dummy1 = ctx.texture((1, 1), 4, b"\xff\xff\xff\xff")
        self._extra = [None, None, None]
        self._active_color_fbo = self._color_fbo
        self._active_color_tex = self._color
        self.stats = {}
        self.begin()

    def _vao(self, prog, vbo, rig):
        if rig:
            fmt = "3f 3f 3f 4f 1f 1f"
            names = ["in_pos", "in_col", "in_nrm", "in_flags", "in_fb", "in_slot"]
        else:
            fmt = "3f 3f 3f 4f 1f 4f 2f 1f"
            names = ["in_pos", "in_col", "in_nrm", "in_flags", "in_dbias", "in_tint", "in_uv", "in_tex"]
        return self.ctx.vertex_array(prog, [(vbo, fmt, *names)])

    # scene --------------------------------------------------------------
    def invalidate_static(self):
        """Call after editing baked objects' geometry in place."""
        self._static_sig = None

    def resize(self, w, h):
        """Re-target the off-screen frame without touching the scene.

        The projection is resolution independent (``focal`` follows ``w``), so
        a resolution change is just new colour/depth textures: the static VBO,
        the rig templates and every baked mesh stay valid.  Rebuilding the
        renderer instead - which is what a scale change used to do - re-packs
        the whole set (~150 ms) and risks the ``id()``-keyed bake caches.
        """
        w, h = int(w), int(h)
        if not super().resize(w, h):
            return False
        old = (getattr(self, "_fbo", None), getattr(self, "_color_fbo", None),
               getattr(self, "_color", None), getattr(self, "_aux", None),
               getattr(self, "_pdepth", None), getattr(self, "_depth", None))
        self._color = self.ctx.texture((w, h), 4, dtype="f2")
        self._aux = self.ctx.texture((w, h), 4)
        self._aux.filter = (self.ctx.NEAREST, self.ctx.NEAREST)
        self._aux.repeat_x = self._aux.repeat_y = False
        self._pdepth = self.ctx.texture((w, h), 1, dtype="f2")
        self._pdepth.filter = (self.ctx.NEAREST, self.ctx.NEAREST)
        self._pdepth.repeat_x = self._pdepth.repeat_y = False
        self._depth = self.ctx.depth_texture((w, h))
        self._fbo = self.ctx.framebuffer(color_attachments=[self._color, self._aux, self._pdepth],
                                         depth_attachment=self._depth)
        self._color_fbo = self.ctx.framebuffer(color_attachments=[self._color],
                                               depth_attachment=self._depth)
        for obj in old:          # release explicitly: no driver-side churn
            try:
                if obj is not None:
                    obj.release()
            except Exception:
                pass
        self._dyn_cat = None          # staging array is sized to the queue
        self._light_vis.clear()
        self._light_tmp_s = None
        self._light_mask_s = None
        self._comp_buf = None
        return True

    def _sync_static(self):
        objs = self.objs
        sig = (len(objs), id(objs[0]) if objs else 0, id(objs[-1]) if objs else 0)
        if sig == self._static_sig:
            return
        chunks, ranges, first = [], [], 0
        centers, radii, obj_idx = [], [], []
        CELL = 32.0
        for oi, o in enumerate(objs):
            faces = [(f[0], f[1], f[2], f[3], f[4], f[5]) for f in o.faces]
            arr = _pack_faces(o.verts, faces, prelit=True)
            n = 0 if arr is None else len(arr)
            if not n:
                continue
            if o.radius > CELL and len(o.faces) >= 48 and n >= 144 and n % 3 == 0:
                tris = arr.reshape(-1, 3, _VERT_FLOATS)
                cx = np.floor(tris[:, :, 0].mean(axis=1) / CELL).astype(np.int64)
                cz = np.floor(tris[:, :, 2].mean(axis=1) / CELL).astype(np.int64)
                keys = ((cx + (1 << 20)) << 21) | (cz + (1 << 20))
                order = np.argsort(keys, kind="mergesort")
                skeys = keys[order]
                tris_s = tris[order]
                arr = tris_s.reshape(-1, _VERT_FLOATS)
                splits = np.flatnonzero(skeys[1:] != skeys[:-1]) + 1
                starts = np.concatenate(([0], splits))
                ends = np.concatenate((splits, [len(tris_s)]))
                for s, e in zip(starts.tolist(), ends.tolist()):
                    pts = tris_s[s:e, :, 0:3].reshape(-1, 3)
                    lo, hi = pts.min(axis=0), pts.max(axis=0)
                    cc = (lo + hi) * 0.5
                    d = pts - cc
                    rad = float(math.sqrt(float((d * d).sum(axis=1).max())))
                    ranges.append((first + s * 3, (e - s) * 3))
                    centers.append(cc)
                    radii.append(rad)
                    obj_idx.append(oi)
            else:
                ranges.append((first, n))
                centers.append(o.center)
                radii.append(o.radius)
                obj_idx.append(oi)
            chunks.append(arr)
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
        self._sc_starts = np.asarray([a for a, _ in ranges], dtype=np.int64)
        self._sc_counts = np.asarray([n for _, n in ranges], dtype=np.int64)
        self._sc_centers = np.asarray(centers, dtype=np.float32).reshape(-1, 3)
        self._sc_radii = np.asarray(radii, dtype=np.float32)
        self._sc_obj_idx = np.asarray(obj_idx, dtype=np.int64)
        self._static_sig = sig

    def set_sky(self, spec):
        """Queue GPU sky parameters for the next render pass."""
        self._sky_spec = spec

    def begin(self):
        self._sun = None          # set_sun_shadow: this frame only
        self.char_pop = 0.0       # rig readability boost, this frame only (top-down hosts)
        self.tex_scale = 1.0      # texture tiling scale, this frame only (top-down: bigger texels)
        self.wetness = 0.0
        self.marble_refl = 0.0
        self.height_fog = None
        self.actor_log = []       # humanoid positions this frame (shared cast shadows)
        self._items = []          # sprites + lines: (key, kind, data)
        self._dyn = []            # packed float32 chunks
        self._dyn_bounds = []
        self._res_draw = []       # resident chunk entries queued this frame
        self._rig_draws = []      # (rig_entry, bones bytes, tint, bias)
        self._particles = []
        self._decals = []
        self._spot_active = []
        self._want_static = False
        if not hasattr(self, "_sky_spec"):
            self._sky_spec = None
        self._overlay_deferred = False
        self._cull_stats = {"static": 0, "res": 0, "rigs": 0, "items": 0, "lights": 0}

    def add_static(self):
        self._want_static = True

    def set_extra_textures(self, *entries):
        """Upload up to 3 ``(key, surface)`` RGB textures for ``v_tex = -2..-4``."""
        import moderngl
        for i in range(min(3, len(entries))):
            item = entries[i]
            if item is None:
                continue
            key, surf = item
            cur = self._extra[i]
            if cur is not None and cur[0] == key:
                continue
            if cur is not None:
                try:
                    cur[1].release()
                except Exception:
                    pass
            w, h = surf.get_size()
            raw = pygame.image.tobytes(surf, "RGB", False)
            tex = self.ctx.texture((w, h), 3, raw)
            tex.filter = (moderngl.NEAREST, moderngl.NEAREST)
            tex.repeat_x = tex.repeat_y = False
            self._extra[i] = (key, tex)

    SUN_MAP = 2048

    def set_sun_shadow(self, travel, center, half, k=0.6, col=(0.12, 0.15, 0.32)):
        """Real cast shadows for this frame: everything queued (set, props,
        rigs) is drawn into a SUN_MAP depth map from a sun shining along
        ``travel`` over a ``2*half`` metre square round ``center``, and every
        lit face under it is scaled toward ``col`` by ``k``. Cleared by
        ``begin``. Returns True (the software renderer returns False)."""
        f = v_norm(travel)
        rt = v_norm(v_cross(f, (0.0, 0.0, 1.0)))
        up = v_cross(rt, f)
        D = 40.0
        tx = 2.0 * half / self.SUN_MAP
        # snap the square to whole texels so edges do not crawl as the camera moves
        a = math.floor((center[0] * rt[0] + center[1] * rt[1] + center[2] * rt[2]) / tx) * tx
        b = math.floor((center[0] * up[0] + center[1] * up[1] + center[2] * up[2]) / tx) * tx
        c = center[0] * f[0] + center[1] * f[1] + center[2] * f[2]
        o = tuple(rt[i] * a + up[i] * b + f[i] * (c - D) for i in range(3))
        self._sun = {"u_sh_cam": o, "u_sh_right": rt, "u_sh_up": up, "u_sh_fwd": f,
                     "u_sh_half": float(half), "u_sh_far": 2.0 * D, "u_sh_texel": tx,
                     "u_sh_k": float(k), "u_sh_col": tuple(float(x) for x in col)}
        return True

    def add_dynamic(self, wverts, faces, bias=0.0, tint=None, bounds=None):
        if bounds is None and getattr(self, "frustum_cull", True) and len(wverts) >= 12:
            xs = [v[0] for v in wverts]
            ys = [v[1] for v in wverts]
            zs = [v[2] for v in wverts]
            cx, cy, cz = (min(xs) + max(xs)) * 0.5, (min(ys) + max(ys)) * 0.5, (min(zs) + max(zs)) * 0.5
            rad = math.sqrt(max((v[0] - cx) ** 2 + (v[1] - cy) ** 2 + (v[2] - cz) ** 2 for v in wverts))
            bounds = ((cx, cy, cz), rad)
        arr = _pack_faces(wverts, faces, prelit=False, bias=bias, tint=tint)
        if arr is not None:
            self._dyn.append(arr)
            self._dyn_bounds.append(bounds)

    def add_packed(self, arr, bounds=None):
        """Queue rows already in the dynamic vertex layout (see ``pack``).

        For meshes that only move rigidly: pack once, then transform the
        position/normal columns per frame instead of re-packing in Python."""
        if arr is not None and len(arr):
            self._dyn.append(arr)
            self._dyn_bounds.append(bounds)

    def add_resident(self, arr, bounds=None):
        """Queue packed rows that are identical every frame (the memoized live
        set).  They go to a buffer of their own once and are only drawn
        afterwards; ``add_packed`` would copy and re-send them each frame,
        which is ~10 MB for the yard's set."""
        if arr is None or not len(arr):
            return
        key = id(arr)
        ent = self._res.get(key)
        if ent is not None:
            self._res.move_to_end(key)
        else:
            if bounds is None:
                pts = arr[:, 0:3]
                lo, hi = pts.min(axis=0), pts.max(axis=0)
                cc = (float((lo[0] + hi[0]) * 0.5), float((lo[1] + hi[1]) * 0.5), float((lo[2] + hi[2]) * 0.5))
                d = pts - np.asarray(cc, dtype=pts.dtype)
                rad = float(math.sqrt(float((d * d).sum(axis=1).max())))
            else:
                cc, rad = bounds
            vbo = self.ctx.buffer(np.ascontiguousarray(arr, dtype=np.float32))
            ent = (arr, vbo, self._vao(self.progs.world, vbo, rig=False), len(arr), cc, rad)
            self._res[key] = ent
            live = {id(e[0]) for e in self._res_draw} | {key}
            if len(self._res) > 128:
                for rk in list(self._res):
                    if len(self._res) <= 128:
                        break
                    if rk not in live:
                        _a, old_vbo, old_vao, _n, _c, _r = self._res.pop(rk)
                        old_vao.release()
                        old_vbo.release()
        self._res_draw.append(ent)

    @staticmethod
    def pack(wverts, faces, bias=0.0, tint=None):
        """``add_dynamic``'s packing step on its own -> float32 rows or None.
        Columns 0:3 are positions, 6:9 the (unit) face normals."""
        return _pack_faces(wverts, faces, prelit=False, bias=bias, tint=tint)

    def add_humanoid(self, hum, pose, pos, yaw, rifle_on=True, bias=0.0, tint=None,
                     shadow=None):
        places, joints, (px, py, pz) = hum.pose_world(pose, pos, yaw, rifle_on=rifle_on)
        self.actor_log.append(tuple(pos))
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
        bones = getattr(self, "_bones_buf", None)
        if bones is None:
            bones = self._bones_buf = np.zeros((_N_SLOTS, 4, 4), dtype=np.float32)
        else:
            bones.fill(0.0)   # zero = hidden slot
        for slot, _key, M, org, _g, _fb in places:
            b = bones[slot]
            # column-major mat4: b[col][row]
            b[0, 0], b[1, 0], b[2, 0] = M[0], M[1], M[2]
            b[0, 1], b[1, 1], b[2, 1] = M[3], M[4], M[5]
            b[0, 2], b[1, 2], b[2, 2] = M[6], M[7], M[8]
            b[3, 0], b[3, 1], b[3, 2], b[3, 3] = org[0] + px, org[1] + py, org[2] + pz, 1.0
        t = (0.0, 0.0, 0.0, 0.0) if tint is None else (*tint[0], float(tint[1]))
        rc = (float(pos[0]), float(pos[1]) + 0.9, float(pos[2]))
        self._rig_draws.append((entry, bones.tobytes(), t, float(bias), rc, 1.85))
        sl, sb = shadow if shadow else (None, 0.0)
        self.add_blob_shadow((pos[0], pos[1] + 0.02, pos[2]), 0.34, 0.30, 0.40,
                             layer=sl, bias=sb)
        return joints

    def add_sprite(self, pos, draw_fn, layer=2, bias=0.0):
        if getattr(self, "frustum_cull", True):
            bm = getattr(draw_fn, "bounds_m", None)
            sr = (max(bm[0], bm[1]) + 0.5) if bm is not None else 8.5
            if not self.visible_frustum(
                pos, sr, self.cam, self.right, self.up, self.fwd,
                self.NEAR, self.fog_end + 120.0, self.tan_h, self.tan_v,
            ):
                self._cull_stats["items"] += 1
                return
        p = self.project(pos)
        if p is None:
            return
        sx, sy, z = p
        anchor = tuple(pos) if getattr(draw_fn, "light", False) else None
        self._items.append((layer * 1e6 - z - bias, "sprite",
                            (draw_fn, sx, sy, self.focal / z, z, layer,
                             z + bias, anchor)))

    def add_blob_shadow(self, pos, rx, rz, strength=0.35, layer=None, bias=0.0):
        # The software implementation queues a (key, callable, args) item,
        # which _composite cannot read; queue the same disc as a GL sprite
        # item (layer 1: just above ground) so it depth-composites like
        # any sprite. Without this, every humanoid on the GL backend fed
        # a callable into _composite's line branch and crashed the flush.
        if getattr(self, "frustum_cull", True) and not self.visible_sphere(pos, max(rx, rz) + 0.15):
            self._cull_stats["items"] += 1
            return
        item = self._blob_item(pos, rx, rz, strength)
        if item is None:
            return
        draw, c = item
        _bx, _by, wpx, hpx = draw.bounds
        draw._gl_spec = {
            "kind": "blob",
            "col": (0.0, 0.0, 0.0),
            "rx_px": float(wpx),
            "ry_px": float(hpx),
            "strength": float(strength),
        }
        lay = 1 if layer is None else layer
        self._items.append((lay * 1e6 - c[2] - bias, "sprite",
                            (draw, c[0], c[1], self.focal / c[2], c[2], lay, c[2] + bias)))

    def add_line3d(self, a, b, col, width=1, layer=3):
        if getattr(self, "frustum_cull", True):
            mid = ((a[0] + b[0]) * 0.5, (a[1] + b[1]) * 0.5, (a[2] + b[2]) * 0.5)
            r_m = 0.5 * math.sqrt((b[0] - a[0]) ** 2 + (b[1] - a[1]) ** 2 + (b[2] - a[2]) ** 2) + 0.1
            if not self.visible_sphere(mid, r_m):
                self._cull_stats["items"] += 1
                return
        from .core import _clip_near
        pa, pb = self.to_cam(a), self.to_cam(b)
        if pa[2] < self.NEAR and pb[2] < self.NEAR:
            return
        pts = _clip_near([pa, pb], self.NEAR, closed=False)
        if len(pts) < 2:
            return
        scr = [(self.w / 2 + x / z * self.focal, self.h / 2 - y / z * self.focal) for x, y, z in pts]
        self._items.append((layer * 1e6, "line", (col, width, scr, layer)))

    def add_lines3d(self, segs, layer=4, depth_test=True):
        """Queue many world-space segments as one composite item.

        Snow uses ~120 one-pixel lines a frame; compositing each as its own
        item paid the depth test and surface-lock overhead per flake.
        ``depth_test=False`` for scenery drawn above every world layer."""
        from .core import _clip_near
        out = []
        cull = getattr(self, "frustum_cull", True)
        near, far = self.NEAR, self.fog_end + 120.0
        th, tv = self.tan_h, self.tan_v
        for a, b, col, width in segs:
            pa, pb = self.to_cam(a), self.to_cam(b)
            if pa[2] < near and pb[2] < near:
                continue
            if cull:
                if pa[2] > far and pb[2] > far:
                    continue
                mz = max(pa[2], pb[2], near)
                if (pa[0] > mz * th and pb[0] > mz * th) or (pa[0] < -mz * th and pb[0] < -mz * th):
                    continue
                if (pa[1] > mz * tv and pb[1] > mz * tv) or (pa[1] < -mz * tv and pb[1] < -mz * tv):
                    continue
            pts = _clip_near([pa, pb], self.NEAR, closed=False)
            if len(pts) < 2:
                continue
            p0 = (self.w / 2 + pts[0][0] / pts[0][2] * self.focal,
                  self.h / 2 - pts[0][1] / pts[0][2] * self.focal)
            p1 = (self.w / 2 + pts[1][0] / pts[1][2] * self.focal,
                  self.h / 2 - pts[1][1] / pts[1][2] * self.focal)
            out.append((p0, p1, col, width))
        if out:
            self._items.append((layer * 1e6, "lines",
                                (out, layer, depth_test)))

    # drawing ------------------------------------------------------------
    @property
    def _far(self):
        return self.fog_end + 400.0

    @staticmethod
    def _quality():
        try:
            from core.user_settings import SETTINGS
            return int(SETTINGS.quality_3d)
        except Exception:
            return 2

    def _select_spot_shadows(self, lights):
        q = self._quality()
        if not getattr(self, "spot_shadows", True) or q <= 0:
            return []
        max_spots = 2 if q >= 2 else 1
        cands = []
        for idx, L in enumerate(lights):
            is_spot = L.get("kind") == "spot"
            sh_flag = bool(L.get("shadow", False))
            if not (sh_flag or (is_spot and float(L.get("intensity", 1.0)) >= 0.6 and float(L.get("range", 6.0)) >= 4.0)):
                continue
            dx = L["pos"][0] - self.cam[0]
            dy = L["pos"][1] - self.cam[1]
            dz = L["pos"][2] - self.cam[2]
            score = (1000.0 if sh_flag else 0.0) + float(L.get("intensity", 1.0)) * 40.0 - math.sqrt(dx * dx + dy * dy + dz * dz)
            cands.append((score, idx, L))
        cands.sort(key=lambda x: -x[0])
        return [(idx, L) for _, idx, L in cands[:max_spots]]

    def _upload_lights(self, lights):
        if getattr(self, "frustum_cull", True) and lights:
            vis_lights = [
                L for L in lights
                if self.visible_sphere(L["pos"], float(L.get("range", 6.0)))
            ]
            self._cull_stats["lights"] += len(lights) - len(vis_lights)
        else:
            vis_lights = lights
        cap = max(1, min(MAX_LIGHTS, int(getattr(self, "light_cap", MAX_LIGHTS))))
        ls = vis_lights[:cap]
        n = len(ls)
        self._spot_active = self._select_spot_shadows(ls)
        sh_map = {idx: slot for slot, (idx, _L) in enumerate(self._spot_active)}

        buf = self._pl_buf
        buf.fill(0.0)
        buf[2, :, 3] = -1.0
        buf[3, :, 0] = -1.0
        for i, L in enumerate(ls):
            p = L["pos"]
            c = L["color"]
            buf[0, i] = (p[0], p[1], p[2], float(L.get("range", 6.0)))
            buf[1, i] = (float(c[0]), float(c[1]), float(c[2]), float(L.get("intensity", 1.0)))
            if L.get("kind") == "spot":
                d = L["dir"]
                buf[2, i] = (d[0], d[1], d[2], float(L.get("cone", 0.7)))
            if i in sh_map:
                buf[3, i, 0] = float(sh_map[i])
        self._pl_tex.write(buf.tobytes())
        self._n_pl_cur = n

        # Bin up to 64 lights into a 12x8 screen-space tile bitmask (4x16-bit ints/tile)
        tiles = np.zeros((96, 4), dtype=np.int32)
        W, H = float(self.w), float(self.h)
        hw, hh = W * 0.5, H * 0.5
        foc = float(self.focal)
        cam = self.cam
        rt, up, fw = self.right, self.up, self.fwd
        near = self.NEAR
        for i, L in enumerate(ls):
            px, py, pz = L["pos"]
            dx, dy, dz = px - cam[0], py - cam[1], pz - cam[2]
            cz = dx * fw[0] + dy * fw[1] + dz * fw[2]
            rng = float(L.get("range", 6.0))
            if cz + rng < near:
                continue
            if cz - rng <= near:
                tx0, tx1, ty0, ty1 = 0, 11, 0, 7
            else:
                cx = dx * rt[0] + dy * rt[1] + dz * rt[2]
                cy = dx * up[0] + dy * up[1] + dz * up[2]
                sx_c = hw + (cx / cz) * foc
                gy_c = hh + (cy / cz) * foc
                rad_px = rng * foc / max(near, cz - rng) * 1.18
                tx0 = max(0, int((sx_c - rad_px) * 12.0 / W))
                tx1 = min(11, int((sx_c + rad_px) * 12.0 / W))
                ty0 = max(0, int((gy_c - rad_px) * 8.0 / H))
                ty1 = min(7, int((gy_c + rad_px) * 8.0 / H))
            if tx0 > tx1 or ty0 > ty1:
                continue
            bank = i >> 4
            bit = 1 << (i & 15)
            for ty in range(ty0, ty1 + 1):
                row_off = ty * 12
                for tx in range(tx0, tx1 + 1):
                    tiles[row_off + tx, bank] |= bit
        self._tile_masks = [tuple(int(v) for v in row) for row in tiles]
        self._spot_uniforms = self._build_spot_uniforms()

    def _build_spot_uniforms(self):
        cam = [(0.0, 0.0, 0.0), (0.0, 0.0, 0.0)]
        rt = [(1.0, 0.0, 0.0), (1.0, 0.0, 0.0)]
        up = [(0.0, 1.0, 0.0), (0.0, 1.0, 0.0)]
        fw = [(0.0, 0.0, 1.0), (0.0, 0.0, 1.0)]
        tan_h = [1.0, 1.0]
        near = [0.25, 0.25]
        far = [10.0, 10.0]
        for slot, (_idx, L) in enumerate(self._spot_active):
            d = v_norm(L.get("shadow_dir") or L["dir"])
            ref_up = (0.0, 0.0, 1.0) if abs(d[1]) > 0.9 else (0.0, 1.0, 0.0)
            r_v = v_norm(v_cross(ref_up, d))
            u_v = v_cross(d, r_v)
            cone = max(0.15, min(0.98, float(L.get("shadow_cone", L.get("cone", 0.7)))))
            th = math.tan(math.acos(cone))
            cam[slot] = tuple(float(v) for v in L["pos"])
            rt[slot] = tuple(float(v) for v in r_v)
            up[slot] = tuple(float(v) for v in u_v)
            fw[slot] = tuple(float(v) for v in d)
            tan_h[slot] = float(th)
            near[slot] = 0.25
            far[slot] = max(2.0, float(L.get("range", 8.0)))
        return {
            "u_spot_cam": cam, "u_spot_right": rt, "u_spot_up": up, "u_spot_fwd": fw,
            "u_spot_tan": tan_h, "u_spot_near": near, "u_spot_far": far,
        }

    def _set_uniforms(self, prog, split_mode, split):
        L = self.light
        n_pl = getattr(self, "_n_pl_cur", 0)
        raw_pools = self.pools
        if getattr(self, "frustum_cull", True) and raw_pools:
            pools = [P for P in raw_pools if self.visible_sphere(P["pos"], float(P.get("range", 6.0)))][:32]
        else:
            pools = raw_pools[:32]
        n_po = len(pools)
        u = {
            "u_cam": self.cam, "u_right": self.right, "u_up": self.up, "u_fwd": self.fwd,
            "u_focal": self.focal, "u_hw": self.w / 2, "u_hh": self.h / 2,
            "u_near": self.NEAR, "u_far": self._far, "u_snap": bool(self.ps1_snap),
            "u_ldir": L.dir, "u_ltint": L.tint, "u_amb": L.ambient, "u_dif": L.diffuse,
            "u_sky": L.sky, "u_fog": self.fog, "u_fog_start": self.fog_start,
            "u_fog_end": self.fog_end, "u_split_mode": split_mode, "u_split": float(split),
            "u_dither": bool(self.dither), "u_tex": _TEX_UNIT,
            "u_extra0": _EXTRA0_UNIT, "u_extra1": _EXTRA1_UNIT, "u_extra2": _EXTRA2_UNIT,
            "u_pl_tex": _PL_UNIT,
            "u_tile_inv": (12.0 / max(1.0, float(self.w)), 8.0 / max(1.0, float(self.h))),
            "u_tile_mask": getattr(self, "_tile_masks", [(0, 0, 0, 0)] * 96),
            "u_pl_n": n_pl,
            "u_pl_mod": 1.0 if getattr(self, "light_albedo", False) else 0.0,
            "u_pl_gain": float(getattr(self, "light_gain", 1.0)),
            "u_pool_n": n_po,
            "u_pool_pos": [tuple(P["pos"]) + (float(P.get("range", 6.0)),) for P in pools]
                          + [(0.0, 0.0, 0.0, 1.0)] * (32 - n_po),
            "u_pool_col": [tuple(float(c) for c in P["color"]) + (float(P.get("intensity", 1.0)),)
                           for P in pools] + [(0.0, 0.0, 0.0, 0.0)] * (32 - n_po),
            "u_pool_hot": [tuple(float(c) for c in P.get("hot", P["color"])) for P in pools]
                          + [(0.0, 0.0, 0.0)] * (32 - n_po),
            "u_glit": (list(_tex.glitter()) + [0.0] * 32)[:32],
            "u_glit_k": float(self.glitter),
            "u_refl": (list(_tex.reflectivity()) + [0.0] * 32)[:32],
            "u_wet": float(getattr(self, "wetness", 0.0)),
            "u_marble": float(getattr(self, "marble_refl", 0.0)),
            "u_depth_alpha": float(getattr(self, "_depth_alpha", 0.0)),
            "u_ortho": False, "u_ohw": 1.0, "u_ohh": 1.0, "u_sh_pass": False,
            "u_sh_on": self._sun is not None, "u_sh_tex": _SH_UNIT,
            "u_spot_tex0": _SPOT0_UNIT, "u_spot_tex1": _SPOT1_UNIT,
            "u_cpop": float(self.char_pop),
            "u_right": tuple(self.right), "u_up": tuple(self.up), "u_fwd": tuple(self.fwd),
            "u_hdr_emissive": 1.65 if getattr(self, "hdr", False) else 1.0,
            "u_uvs": float(self.tex_scale),
        }
        su = getattr(self, "_spot_uniforms", None)
        if su:
            u.update(su)
        if self._sun is not None:
            u.update(self._sun)
        self._put(prog, u)

    def _put(self, prog, u):
        cache = self.progs.uniforms(prog)
        for k, v in u.items():
            ent = cache.get(k)
            if ent is not None and not _same(ent[1], v):
                ent[0].value = v
                ent[1] = v

    def _pass_cull_fn(self, pass_kind, spot_slot=0):
        if not getattr(self, "frustum_cull", True):
            return None
        if pass_kind == "sun" and self._sun is not None:
            s = self._sun
            return lambda c, r, s=s: self.visible_ortho(
                c, r, s["u_sh_cam"], s["u_sh_right"], s["u_sh_up"], s["u_sh_fwd"],
                s["u_sh_half"], s["u_sh_half"], s["u_sh_far"],
            )
        if pass_kind == "spot":
            su = self._spot_uniforms
            cam = su["u_spot_cam"][spot_slot]
            rt = su["u_spot_right"][spot_slot]
            up = su["u_spot_up"][spot_slot]
            fw = su["u_spot_fwd"][spot_slot]
            near = su["u_spot_near"][spot_slot]
            far = su["u_spot_far"][spot_slot]
            th = su["u_spot_tan"][spot_slot]
            return lambda c, r, cam=cam, rt=rt, up=up, fw=fw, near=near, far=far, th=th: self.visible_frustum(
                c, r, cam, rt, up, fw, near, far, th, th,
            )
        return self.visible_sphere

    def _draw_dyn(self, upload=True, cull_fn=None):
        """Upload + draw the queued packed rows; returns triangles drawn.
        ``upload=False`` redraws what the last upload sent (sun pass first)."""
        if not self._dyn:
            return 0
        import moderngl
        if not upload:
            self._dyn_vao.render(moderngl.TRIANGLES, vertices=self._dyn_n)
            return self._dyn_n // 3
        chunks = self._dyn
        if getattr(self, "frustum_cull", True) and getattr(self, "_dyn_bounds", None):
            bounds = self._dyn_bounds
            if self._sun is None and not self._spot_active and cull_fn is not None:
                chunks = [c for c, b in zip(chunks, bounds) if b is None or cull_fn(b[0], b[1])]
            elif len(bounds) == len(chunks) and any(b is not None for b in bounds):
                fns = [self.visible_sphere]
                if self._sun is not None:
                    fns.append(self._pass_cull_fn("sun"))
                for sl in range(len(self._spot_active)):
                    fns.append(self._pass_cull_fn("spot", sl))
                chunks = [c for c, b in zip(chunks, bounds)
                          if b is None or any(fn(b[0], b[1]) for fn in fns if fn is not None)]
            if not chunks:
                self._dyn_n = 0
                return 0
        if len(chunks) == 1:
            data = chunks[0]
        else:
            # Into one reusable staging array instead of ``np.concatenate``
            # plus a ``tobytes`` copy: the scenes queue 30-80 small chunks a
            # frame (actors, props, FX), and that was two full copies of the
            # whole dynamic buffer per pass, twice a frame in the train scene.
            rows = sum(c.shape[0] for c in chunks)
            width = chunks[0].shape[1]
            buf = self._dyn_cat
            if buf is None or buf.shape[0] < rows or buf.shape[1] != width:
                buf = np.empty((rows, width), dtype=np.float32)
                self._dyn_cat = buf
            off = 0
            for c in chunks:
                n = c.shape[0]
                buf[off:off + n] = c
                off += n
            data = buf[:rows]
        if not data.flags["C_CONTIGUOUS"]:
            data = np.ascontiguousarray(data)
        nbytes = data.nbytes
        if nbytes > self._dyn_vbo.size:
            # read the size BEFORE release: a released moderngl buffer is an
            # InvalidObject and .size raised on the first oversized frame
            grow = max(nbytes, self._dyn_vbo.size * 2)
            self._dyn_vao.release()
            self._dyn_vbo.release()
            self._dyn_vbo = self.ctx.buffer(reserve=grow, dynamic=True)
            self._dyn_vao = self._vao(self.progs.world, self._dyn_vbo, rig=False)
        self._dyn_vbo.write(data)          # moderngl takes the array itself
        self._dyn_n = len(data)
        self._dyn_vao.render(moderngl.TRIANGLES, vertices=len(data))
        return len(data) // 3

    def _draw_resident(self, cull_fn=None, track=False):
        import moderngl
        ntri = 0
        for _rows, _vbo, vao, n, c, rad in self._res_draw:
            if cull_fn is not None and not cull_fn(c, rad):
                if track:
                    self._cull_stats["res"] += 1
                continue
            vao.render(moderngl.TRIANGLES, vertices=n)
            ntri += n // 3
        return ntri

    def _draw_rigs(self, split_mode=0, split=0.0, over=None, cull_fn=None, track=False):
        if not self._rig_draws:
            return 0
        import moderngl
        rig = self.progs.rig
        self._set_uniforms(rig, split_mode, split)
        if over:
            self._put(rig, over)
        rig["u_char"].value = 1.0
        bones = rig["u_bones"]
        ntri = 0
        for (hum, vbo, vao, n), bb, tint, bias, rc, rrad in self._rig_draws:
            if cull_fn is not None and not cull_fn(rc, rrad):
                if track:
                    self._cull_stats["rigs"] += 1
                continue
            bones.write(bb)
            rig["u_rtint"].value = tint
            rig["u_rbias"].value = bias
            vao.render(moderngl.TRIANGLES, vertices=n)
            ntri += n // 3
        return ntri

    def _visible_static_runs(self, pass_kind, spot_slot=0):
        objs = self.objs
        n_chunks = len(self._sc_starts)
        if not n_chunks:
            return ()
        vis_obj = np.fromiter((o.visible for o in objs), dtype=bool, count=len(objs))
        keep = vis_obj[self._sc_obj_idx] & (self._sc_counts > 0)
        if getattr(self, "frustum_cull", True):
            c = self._sc_centers
            r = self._sc_radii
            if pass_kind == "sun" and self._sun is not None:
                s = self._sun
                d = c - np.asarray(s["u_sh_cam"], dtype=np.float32)
                z = d @ np.asarray(s["u_sh_fwd"], dtype=np.float32)
                x = d @ np.asarray(s["u_sh_right"], dtype=np.float32)
                y = d @ np.asarray(s["u_sh_up"], dtype=np.float32)
                hw = float(s["u_sh_half"])
                keep &= (z + r >= 0.0) & (z - r <= float(s["u_sh_far"]))
                keep &= (np.abs(x) <= hw + r) & (np.abs(y) <= hw + r)
            else:
                if pass_kind == "spot":
                    su = self._spot_uniforms
                    cam = su["u_spot_cam"][spot_slot]
                    rt = su["u_spot_right"][spot_slot]
                    up = su["u_spot_up"][spot_slot]
                    fw = su["u_spot_fwd"][spot_slot]
                    near = float(su["u_spot_near"][spot_slot])
                    far = float(su["u_spot_far"][spot_slot])
                    th = tv = float(su["u_spot_tan"][spot_slot])
                else:
                    cam, rt, up, fw = self.cam, self.right, self.up, self.fwd
                    near, far = self.NEAR, self.fog_end + 60.0
                    th, tv = self.tan_h, self.tan_v
                d = c - np.asarray(cam, dtype=np.float32)
                z = d @ np.asarray(fw, dtype=np.float32)
                x = d @ np.asarray(rt, dtype=np.float32)
                y = d @ np.asarray(up, dtype=np.float32)
                kh = math.sqrt(1.0 + th * th)
                kv = math.sqrt(1.0 + tv * tv)
                keep &= (z + r >= near) & (z - r <= far)
                keep &= (np.abs(x) - z * th <= r * kh) & (np.abs(y) - z * tv <= r * kv)
        if pass_kind == "main":
            self._cull_stats["static"] += int(n_chunks - int(keep.sum()))
        idx = np.flatnonzero(keep)
        if not len(idx):
            return ()
        starts = self._sc_starts[idx].tolist()
        counts = self._sc_counts[idx].tolist()
        runs = []
        ra, rn = starts[0], counts[0]
        for a, n in zip(starts[1:], counts[1:]):
            if ra + rn == a:
                rn += n
            else:
                runs.append((ra, rn))
                ra, rn = a, n
        runs.append((ra, rn))
        return runs

    def _draw_geometry(self, split_mode=0, split=0.0, upload=True, over=None,
                       pass_kind="main", spot_slot=0):
        """Static set, resident chunks, dynamic rows, rigs (world program
        uniforms already set); returns triangles drawn."""
        import moderngl
        ntri = 0
        if self._want_static and self.objs:
            self._sync_static()
            if self._static_vao is not None:
                runs = self._visible_static_runs(pass_kind, spot_slot)
                for a, n in runs:
                    self._static_vao.render(moderngl.TRIANGLES, vertices=n, first=a)
                    ntri += n // 3
        cull_fn = self._pass_cull_fn(pass_kind, spot_slot)
        is_main = (pass_kind == "main")
        ntri += self._draw_resident(cull_fn=cull_fn, track=is_main)
        ntri += self._draw_dyn(upload, cull_fn=cull_fn)
        ntri += self._draw_rigs(split_mode, split, over, cull_fn=cull_fn, track=is_main)
        return ntri

    def _sun_pass(self):
        """Depth of everything queued, seen from the sun (set_sun_shadow)."""
        import moderngl
        S = self.SUN_MAP
        if self._sh_fbo is None:
            self._sh_tex.release()
            self._sh_tex = self.ctx.depth_texture((S, S))
            self._sh_tex.filter = (moderngl.LINEAR, moderngl.LINEAR)   # 2x2 PCF
            self._sh_tex.repeat_x = self._sh_tex.repeat_y = False
            self._sh_fbo = self.ctx.framebuffer(depth_attachment=self._sh_tex)
            self._sh_tex.use(location=_SH_UNIT)
        sun = self._sun
        over = {"u_cam": sun["u_sh_cam"], "u_right": sun["u_sh_right"], "u_up": sun["u_sh_up"],
                "u_fwd": sun["u_sh_fwd"], "u_far": sun["u_sh_far"], "u_ortho": True,
                "u_ohw": sun["u_sh_half"], "u_ohh": sun["u_sh_half"], "u_snap": False,
                "u_sh_pass": True, "u_sh_on": False}
        self._sh_fbo.use()
        self._sh_fbo.clear(depth=1.0)
        world = self.progs.world
        self._set_uniforms(world, 0, 0.0)
        self._put(world, over)
        self._draw_geometry(upload=True, over=over, pass_kind="sun")

    def _spot_pass(self, slot, upload):
        import moderngl
        S = SPOT_MAP
        if self._spot_fbo[slot] is None:
            self._spot_tex[slot].release()
            t = self._spot_tex[slot] = self.ctx.depth_texture((S, S))
            t.filter = (moderngl.LINEAR, moderngl.LINEAR)
            t.repeat_x = t.repeat_y = False
            self._spot_fbo[slot] = self.ctx.framebuffer(depth_attachment=t)
            t.use(location=_SPOT0_UNIT + slot)
        su = self._spot_uniforms
        focal = (S * 0.5) / max(0.05, su["u_spot_tan"][slot])
        over = {
            "u_cam": su["u_spot_cam"][slot], "u_right": su["u_spot_right"][slot],
            "u_up": su["u_spot_up"][slot], "u_fwd": su["u_spot_fwd"][slot],
            "u_focal": float(focal), "u_hw": S * 0.5, "u_hh": S * 0.5,
            "u_near": su["u_spot_near"][slot], "u_far": su["u_spot_far"][slot],
            "u_ortho": False, "u_snap": False, "u_sh_pass": True, "u_sh_on": False,
        }
        self._spot_fbo[slot].use()
        self._spot_fbo[slot].clear(depth=1.0)
        world = self.progs.world
        self._set_uniforms(world, 0, 0.0)
        self._put(world, over)
        self._draw_geometry(upload=upload, over=over, pass_kind="spot", spot_slot=slot)

    def _render_into_fbo(self, surface, split_mode=0, split=0.0, items=None, bg=None):
        """Render sky/bg, sun shadow, geometry, and GPU sprites/lines into _fbo.
        Returns (ntri, cpu_items, alpha)."""
        import moderngl
        ctx = self.ctx
        self._static_runs = None
        w, h = self.w, self.h
        if surface.get_size() != (w, h):
            raise ValueError("GLRenderer target must be %dx%d" % (w, h))
        alpha = bool(surface.get_flags() & pygame.SRCALPHA)
        self._depth_alpha = 0.0 if alpha else 1.0
        self._upload_lights(self.lights)
        sky = getattr(self, "_sky_spec", None)
        self._sky_spec = None
        if sky is not None and not alpha:
            self._sky.render(self, self._fbo, self._color_fbo, sky)
            self._post.clear_depth(self._fbo)
        elif bg is not None and not alpha:
            self._post.clear_mrt(self._fbo, (bg[0] / 255.0, bg[1] / 255.0, bg[2] / 255.0, 1.0))
        elif alpha:
            self._post.clear_mrt(self._fbo, (0.0, 0.0, 0.0, 0.0))
        else:
            self._post.upload_bg(self._fbo, surface)
        ctx.color_mask = (True, True, True, True)
        ctx.depth_mask = True
        ctx.depth_func = "<"
        ctx.enable(moderngl.DEPTH_TEST)
        self.progs.atlas().use(location=_TEX_UNIT)
        self._sh_tex.use(location=_SH_UNIT)
        self._spot_tex[0].use(location=_SPOT0_UNIT)
        self._spot_tex[1].use(location=_SPOT1_UNIT)
        for i, unit in enumerate((_EXTRA0_UNIT, _EXTRA1_UNIT, _EXTRA2_UNIT)):
            ent = self._extra[i]
            (ent[1] if ent is not None else self._dummy1).use(location=unit)
        self._pl_tex.use(location=_PL_UNIT)
        ctx.disable(moderngl.CULL_FACE | moderngl.BLEND)
        uploaded = False
        if self._sun is not None:
            self._sun_pass()
            uploaded = True
        for slot in range(len(self._spot_active)):
            self._spot_pass(slot, upload=not uploaded)
            uploaded = True
        self._fbo.use()
        ctx.viewport = (0, 0, w, h)
        world = self.progs.world
        self._set_uniforms(world, split_mode, split)
        ntri = self._draw_geometry(split_mode, split, upload=not uploaded)
        if self._decals:
            self._decals_batch.render(self, self._color_fbo, self._pdepth, self._decals)
            self._fbo.use()
        atmos_used = (not alpha and split_mode == 0 and self._post.apply_atmos(self, self._n_pl_cur))
        self._active_color_fbo = self._post._atmos_fbo if atmos_used else self._color_fbo
        self._active_color_tex = self._post._atmos_tex if atmos_used else self._color
        items = self._items if items is None else items
        gpu_items, cpu_items = self._sprites.partition(items)
        if gpu_items:
            self._sprites.render(self, self._active_color_fbo, self._pdepth, gpu_items, overlay=False)
        if self._particles:
            self._part_batch.render(self, self._active_color_fbo, self._pdepth, self._particles)
        self._fbo.use()
        self.stats = {
            "tris": ntri, "items": len(items), "actors": len(self._rig_draws),
            "culled_static": self._cull_stats["static"],
            "culled_res": self._cull_stats["res"],
            "culled_rigs": self._cull_stats["rigs"],
            "culled_items": self._cull_stats["items"],
            "culled_lights": self._cull_stats["lights"],
        }
        return ntri, cpu_items, alpha

    def _render(self, surface, split_mode=0, split=0.0, items=None, bg=None):
        """Render the frame into the HDR FBO, resolve through GPU post, then
        composite any unbatched Python callbacks onto the target surface."""
        w, h = self.w, self.h
        _ntri, cpu_items, alpha = self._render_into_fbo(surface, split_mode, split, items, bg)
        post = {"bloom": 0.20, "bloom_knee": 1.02} if (getattr(self, "hdr", False) and not alpha) else None
        self._post.render_to(self, surface, post=post, read_size=(w, h))
        if cpu_items:
            need_depth = alpha
            if not need_depth:
                for _k, kind, d in cpu_items:
                    if kind == "lines":
                        if d[2]:
                            need_depth = True
                            break
                    elif kind != "sprite" or (not getattr(d[0], "light", False) and not getattr(d[0], "phys_occ", False)) or d[6] >= 60.0:
                        need_depth = True
                        break
            depth = (np.frombuffer(self._depth.read(alignment=1), dtype=np.float32).reshape(h, w)[::-1]
                     if need_depth else None)
            phys8 = None
            if not alpha:
                phys8 = _phys8(self._pdepth.read(alignment=1), h, w)
            self._composite(surface, cpu_items, depth, alpha, phys8)

    def flush_to(self, target_surface, *, bg=None, post=None, resolve=True):
        """Render into the HDR FBO and optionally run full GPU post + crisp
        upscale with one single readback into ``target_surface``."""
        w, h = self.w, self.h
        self._deferred_overlay = None
        _ntri, cpu_items, _alpha = self._render_into_fbo(self.surface, 0, 0.0, None, bg)
        if not resolve and not cpu_items:
            self._overlay_deferred = True
            self.begin()
            return
        if cpu_items:
            self._post.render_to(self, self.surface, post=None, read_size=(w, h))
            need_depth = any(
                (kind == "lines" and d[2]) or (
                    kind == "sprite" and ((not getattr(d[0], "light", False) and not getattr(d[0], "phys_occ", False)) or d[6] >= 60.0)
                )
                for _k, kind, d in cpu_items
            )
            depth = (np.frombuffer(self._depth.read(alignment=1), dtype=np.float32).reshape(h, w)[::-1]
                     if need_depth else None)
            phys8 = _phys8(self._pdepth.read(alignment=1), h, w)
            self._composite(self.surface, cpu_items, depth, False, phys8)
            self._post.upload_bg(self._fbo, self.surface)
            self._active_color_fbo = self._color_fbo
            self._active_color_tex = self._color
            if not resolve:
                self._overlay_deferred = True
                self.begin()
                return
            self._post.render_to(self, target_surface, post=dict(post or {}, bloom=0.0))
        else:
            self._post.render_to(self, target_surface, post=post)
        self.begin()

    def present_to(self, target_surface, *, post=None):
        """Resolve the live HDR FBO through GPU post-FX + crisp upscale."""
        self._post.render_to(self, target_surface, post=post)
        deferred = getattr(self, "_deferred_overlay", None)
        if deferred:
            kx = target_surface.get_width() / float(self.w)
            ky = target_surface.get_height() / float(self.h)
            for _key, kind, d in sorted(deferred, key=lambda it: it[0]):
                if kind == "sprite":
                    fn, sx, sy, scale, z = d[:5]
                    fn(target_surface, sx * kx, sy * ky, scale * kx, z)
                elif kind == "line":
                    col, width, scr, _layer = d
                    if len(scr) >= 2:
                        pygame.draw.line(target_surface, col,
                                         (scr[0][0] * kx, scr[0][1] * ky),
                                         (scr[1][0] * kx, scr[1][1] * ky), width)
                elif kind == "lines":
                    for p0, p1, col, width in d[0]:
                        pygame.draw.line(target_surface, col,
                                         (p0[0] * kx, p0[1] * ky),
                                         (p1[0] * kx, p1[1] * ky), width)
            self._deferred_overlay = None
        self._overlay_deferred = False

    def flush_overlay(self, surface, bounds=None, into_fbo=False):
        """Flush a near overlay (the held viewmodel) over *surface*.

        ``into_fbo=True`` keeps the overlay in the HDR FBO for a later single
        ``present_to`` resolve; the legacy path reads only ``bounds`` back.
        """
        import moderngl
        w, h = self.w, self.h
        ctx = self.ctx
        self._depth_alpha = 0.0       # overlay alpha is real transparency
        if into_fbo:
            target_fbo = getattr(self, "_active_color_fbo", self._color_fbo)
            self._post.clear_depth(self._fbo)
            target_fbo.use()
            ctx.color_mask = (True, True, True, True)
            ctx.depth_mask = True
            ctx.depth_func = "<"
            ctx.enable(moderngl.DEPTH_TEST)
            self.progs.atlas().use(location=_TEX_UNIT)
            self._pl_tex.use(location=_PL_UNIT)
            ctx.disable(moderngl.CULL_FACE | moderngl.BLEND)
            self._set_uniforms(self.progs.world, 0, 0.0)
            ntri = self._draw_dyn() + self._draw_rigs()
            gpu_items, cpu_items = self._sprites.partition(self._items)
            if gpu_items:
                self._sprites.render(self, target_fbo, self._pdepth, gpu_items, overlay=True)
                target_fbo.use()
            # Python callbacks cannot paint inside the HDR FBO: defer them to
            # present_to, which draws them onto the resolved target surface.
            self._deferred_overlay = cpu_items
            self.stats = {"tris": ntri, "items": len(self._items), "actors": len(self._rig_draws)}
            self.begin()
            return None, None

        self._post.clear_mrt(self._fbo, (0.0, 0.0, 0.0, 0.0))
        ctx.enable(moderngl.DEPTH_TEST)
        self.progs.atlas().use(location=_TEX_UNIT)
        ctx.disable(moderngl.CULL_FACE | moderngl.BLEND)
        self._set_uniforms(self.progs.world, 0, 0.0)
        ntri = self._draw_dyn() + self._draw_rigs()
        rect = self._clamp_rect(bounds, w, h)
        if rect is None:
            x, y, rw, rh = 0, 0, w, h
        else:
            x, y, rw, rh = rect
        # Read only the requested viewport from the RGBA16F colour attachment.
        raw = self._color_fbo.read(viewport=(x, h - y - rh, rw, rh),
                                   components=4, alignment=1, dtype="f2")
        f16 = np.frombuffer(raw, dtype=np.float16).reshape(rh, rw, 4)
        px = np.clip(np.round(f16.astype(np.float32) * 255.0), 0, 255).astype(np.uint8).tobytes()
        image = pygame.image.frombytes(px, (rw, rh), "RGBA", True)
        cover = self._alpha_cover(px, rw, rh, x, y)
        surface.blit(image, (x, y))
        items = sorted(self._items, key=lambda it: it[0])
        for _key, kind, d in items:
            if kind == "sprite":
                fn, sx, sy, scale, _z = d[:5]
                fn(surface, sx, sy, scale, _z)
            elif kind == "lines":
                for p0, p1, col, width in d[0]:
                    pygame.draw.line(surface, col, p0, p1, width)
            elif kind == "line":
                col, width, scr, _layer = d
                if len(scr) >= 2:
                    pygame.draw.line(surface, col, scr[0], scr[1], width)
        self.stats = {"tris": ntri, "items": len(items), "actors": len(self._rig_draws)}
        self.begin()
        return cover, rect

    @staticmethod
    def _alpha_cover(px, w, h, ox, oy):
        """Screen box of the non-transparent overlay pixels (top-left origin)."""
        a = np.frombuffer(px, dtype=np.uint8).reshape(h, w, 4)[:, :, 3]
        # first/last set column and row: two short any() reductions, not an
        # index array per lit pixel (np.nonzero was ~0.4 ms for a held gun)
        cols = np.flatnonzero(a.any(axis=0))
        if not len(cols):
            return None
        rows = np.flatnonzero(a.any(axis=1))
        x0, x1, y0, y1 = int(cols[0]), int(cols[-1]), int(rows[0]), int(rows[-1])
        return ox + x0, oy + int(h - 1 - y1), x1 - x0 + 1, y1 - y0 + 1

    @staticmethod
    def _clamp_rect(bounds, w, h):
        if bounds is None:
            return None
        x, y, rw, rh = (int(v) for v in bounds)
        x0, y0 = max(0, x), max(0, y)
        x1, y1 = min(w, x + rw), min(h, y + rh)
        if x1 <= x0 or y1 <= y0:
            return None
        return x0, y0, x1 - x0, y1 - y0

    def _enc(self, layer, z):
        slot = min(7.0, max(0.0, float(int(layer + 0.5))))
        lin = min(1.0, max(0.0, z / self._far)) * 0.999
        return ((7.0 - slot) + lin) / 8.0

    def _light_bias(self):
        return (_LIGHT_BIAS_M / self._far) * 0.999 / 8.0

    def _light_anchor_vis(self, anchor, sx, sy, enc, depth):
        """Visible fraction of a light's anchor (0..1), eased over ~80 ms.

        A lamp behind a wall reads zero and is skipped entirely, so no halo
        bleeds round a corner; one half-hidden by a pole dims instead of
        popping.  The 0.35 m bias clears the fixture's own emissive box but
        still lets a wall a metre nearer occlude it.
        """
        H, W = depth.shape
        ix, iy = int(sx), int(sy)
        limit = enc - self._light_bias()
        seen = lit = 0
        for dy in (-3, 0, 3):
            y = iy + dy
            if y < 0 or y >= H:
                continue
            for dx in (-3, 0, 3):
                x = ix + dx
                if 0 <= x < W:
                    seen += 1
                    if depth[y, x] >= limit:
                        lit += 1
        return self._ease_light(anchor, lit / float(seen) if seen else 1.0)

    def _light_targets(self, items, depth, phys8):
        """Raw visible fraction of every light's anchor, keyed by item index:
        the 3x3 depth probe of ``_light_anchor_vis`` for the whole frame in one
        numpy pass per depth source (50 lights was ~0.6 ms of Python)."""
        bias = self._light_bias()
        groups = ([], [])                    # phys8 lights, float-depth lights
        for n, (_key, kind, d) in enumerate(items):
            if kind != "sprite" or not getattr(d[0], "light", False):
                continue
            zeff = d[6]
            if phys8 is not None and zeff < 60.0:
                lim = int(max(0, min(254, round((zeff - 0.45) * 255.0 / 64.0))))
                groups[0].append((n, d[1], d[2], lim - bias))
            else:
                lim = self._enc(_WORLD_LAYER, zeff) - self._light_bias() - 1e-6
                groups[1].append((n, d[1], d[2], lim - bias))
        out = {}
        for src, g in zip((phys8, depth), groups):
            if not g:
                continue
            idx = [e[0] for e in g]
            xs = np.array([e[1] for e in g]).astype(np.int64)
            ys = np.array([e[2] for e in g]).astype(np.int64)
            thr = np.array([e[3] for e in g])
            if src.dtype == np.float32:
                thr = thr.astype(np.float32)
            H, W = src.shape
            X = xs[:, None] + _PROBE_DX
            Y = ys[:, None] + _PROBE_DY
            ok = (X >= 0) & (X < W) & (Y >= 0) & (Y < H)
            v = src[np.clip(Y, 0, H - 1), np.clip(X, 0, W - 1)]
            lit = (ok & (v >= thr[:, None])).sum(axis=1)
            seen = ok.sum(axis=1)
            frac = np.where(seen > 0, lit / np.maximum(seen, 1), 1.0).tolist()
            out.update(zip(idx, frac))
        return out

    def _ease_light(self, anchor, target, now=None):
        """Ease a light's visible fraction over ~80 ms (keyed per anchor)."""
        if anchor is None:
            return target
        key = (int(round(anchor[0] * 2.0)), int(round(anchor[1] * 2.0)),
               int(round(anchor[2] * 2.0)))
        if now is None:
            now = _now_ms()
        prev = self._light_vis.get(key)
        if prev is not None and now > 0 and 0 <= now - prev[1] < 400:
            k = min(1.0, max(0.0, (now - prev[1]) / _LIGHT_EASE_MS))
            target = prev[0] + (target - prev[0]) * k
        self._light_vis[key] = (target, now)
        self._vis_frame += 1
        if self._vis_frame % 256 == 0:
            cutoff = now - 400
            self._light_vis = {k: v for k, v in self._light_vis.items()
                               if v[1] >= cutoff}
        return target

    def _draw_scaled(self, surface, fn, sx, sy, scale, z, x0, y0, x1, y1, vis,
                     occ=None):
        """Draw an additive light into its own small box, mask the occluded
        pixels, then add it to the frame.

        Copying the background, drawing over it and restoring the occluded
        pixels was 3-4 ms of the train frame; a reusable mask is one blit.
        Only lights that actually cross geometry pay this.
        """
        w, h = max(1, x1 - x0), max(1, y1 - y0)
        tmp_full = getattr(self, "_light_tmp_s", None)
        if tmp_full is None or tmp_full.get_size() != (self.w, self.h):
            tmp_full = self._light_tmp_s = pygame.Surface((self.w, self.h))
        tmp = tmp_full.subsurface((0, 0, w, h))
        tmp.fill((0, 0, 0))
        fn(tmp, sx - x0, sy - y0, scale, z)
        if vis < 0.999:
            m = int(round(255 * max(0.0, min(1.0, vis))))
            tmp.fill((m, m, m), special_flags=pygame.BLEND_RGB_MULT)
        if occ is not None:
            mask_full = getattr(self, "_light_mask_s", None)
            if mask_full is None or mask_full.get_size() != (self.w, self.h):
                mask_full = self._light_mask_s = pygame.Surface((self.w, self.h))
            ma = pygame.surfarray.pixels3d(mask_full)
            sub_m = ma[:w, :h]
            sub_m.fill(255)
            sub_m[occ.T] = 0
            del sub_m, ma
            tmp.blit(mask_full, (0, 0), (0, 0, w, h), special_flags=pygame.BLEND_RGB_MULT)
        surface.blit(tmp, (x0, y0), special_flags=pygame.BLEND_RGB_ADD)

    def _composite(self, surface, items, depth, alpha, phys8=None):
        items = sorted(items, key=lambda it: it[0])
        W, H = self.w, self.h
        n_light = n_gate = n_copy = n_scale = n_cull = 0
        light_t = self._light_targets(items, depth, phys8)
        now = _now_ms() if light_t else 0
        for n, (_key, kind, d) in enumerate(items):
            light, vis, strict = False, 1.0, False
            occ_depth, limit = depth, 0.0
            if callable(kind):
                # Defensive: a software-format item (key, draw_fn, args)
                # that leaked into the GL queue still draws, exactly as
                # the software backend would run it (unoccluded), instead
                # of crashing the flush mid-cutscene.
                kind(surface, *d)
                continue
            if kind == "sprite":
                fn, sx, sy, scale, z, layer, zeff = d[:7]
                anchor = d[7] if len(d) > 7 else None
                light = bool(getattr(fn, "light", False))
                strict = bool(getattr(fn, "strict_occ", False))
                soft = light and bool(getattr(fn, "light_soft", False))
                phys_occ = bool(getattr(fn, "phys_occ", False))
                occ_bias = float(getattr(fn, "occ_bias", 0.45 if light else 0.18))
                vis = 1.0
                occ_depth, limit = depth, self._enc(layer, zeff) - 1e-6
                bm = None
                box = getattr(fn, "bounds", None)
                if box is not None:
                    # the callback declared its exact pixel box (blob shadows)
                    x0, y0 = box[0] - 1, box[1] - 1
                    x1, y1 = box[0] + box[2] + 1, box[1] + box[3] + 1
                else:
                    bm = getattr(fn, "bounds_m", None)
                    if bm is not None:
                        # callbacks that know their drawn size in metres: the
                        # generic 3.5 m reach tests 4-20x too many pixels for
                        # lamps, haze and motes.
                        capx, capy = getattr(fn, "bounds_cap_px", (300, 300))
                        rx = int(min(capx, max(2.0, scale * bm[0]))) + 2
                        ry = int(min(capy, max(2.0, scale * bm[1]))) + 2
                        x0, y0 = int(sx) - rx, int(sy) - ry
                        x1, y1 = int(sx) + rx + 1, int(sy) + ry + 1
                    else:
                        reach = int(min(300, max(8, scale * SPRITE_REACH_M)))
                        x0, y0 = int(sx) - reach, int(sy) - reach
                        x1, y1 = int(sx) + reach + 1, int(sy) + reach + 1
                if light or phys_occ:
                    if bm is not None and (x1 <= 0 or x0 >= W or y1 <= 0 or y0 >= H):
                        # a light whose declared box misses the frame paints
                        # nothing: skip its probe, its halo build and the draw
                        n_cull += 1
                        continue
                    if phys8 is not None and zeff < 60.0:
                        # physical depth: layer-independent, 64 m / 255 steps
                        limit = int(max(0, min(254, round(
                            (zeff - occ_bias) * 255.0 / 64.0))))
                        occ_depth = phys8
                    else:
                        # fallback: world-layer encoding (alpha targets / far)
                        limit = (self._enc(_WORLD_LAYER, zeff)
                                 - (self._light_bias() if light else 0.0) - 1e-6)
                    if light:
                        n_light += 1
                        tgt = light_t.get(n)
                        vis = (self._ease_light(anchor, tgt, now) if tgt is not None
                               else self._light_anchor_vis(anchor, sx, sy, limit,
                                                           occ_depth))
                        if vis <= 0.06:
                            n_gate += 1
                            continue
                        if vis >= 0.75:
                            vis = 1.0
                draw = lambda s, fn=fn, sx=sx, sy=sy, scale=scale, z=z: fn(s, sx, sy, scale, z)
            elif kind == "lines":
                segs, layer, depth_test = d
                enc = self._enc(layer, 0.0)
                occ_depth, limit = depth, enc - 1e-6
                if not segs:
                    continue
                pad = 2
                ax0 = ay0 = 1e9
                ax1 = ay1 = -1e9
                for p0, p1, _c, width in segs:
                    if width + 2 > pad:
                        pad = int(width) + 2
                    for px, py in (p0, p1):
                        if px < ax0: ax0 = px
                        if px > ax1: ax1 = px
                        if py < ay0: ay0 = py
                        if py > ay1: ay1 = py
                x0, x1 = int(ax0) - pad, int(ax1) + pad + 1
                y0, y1 = int(ay0) - pad, int(ay1) + pad + 1

                def draw(s, segs=segs):
                    for p0, p1, col, width in segs:
                        pygame.draw.line(s, col, p0, p1, width)
                if not depth_test:
                    draw(surface)
                    continue
            else:
                col, width, scr, layer = d
                enc = self._enc(layer, 0.0)
                occ_depth, limit = depth, enc - 1e-6
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
            if kind == "sprite":
                draw_occ = getattr(fn, "draw_depth", None)
                if draw_occ is not None:
                    draw_occ(surface, sx, sy, scale, z, occ_depth, limit)
                    continue
            # lights carry their own depth limit (physical, or the biased
            # fallback); other sprites still test against the layer slot
            if light and (soft or vis >= 0.999):
                # The anchor gate already cleared the fixture's line of
                # sight.  A fully visible light draws straight: per-pixel
                # masking is kept for a light something is crossing (a
                # guard past a lamp, a pole through a halo), which is the
                # case the mask actually changes.
                draw(surface)
                continue
            if not light and not strict and (x1 - x0) * (y1 - y0) <= 196:
                # particle-sized (a molotov is 200+ dots): one depth probe at
                # the centre instead of a masked box (<= 14x14 px); the mean was ~50 us each
                if not occ_depth[(y0 + y1) // 2, (x0 + x1) // 2] < limit:
                    draw(surface)
                continue
            occ = occ_depth[y0:y1, x0:x1] < limit
            frac = float(occ.mean()) if occ.size else 0.0
            if strict and frac >= 0.999:
                continue
            if frac <= (0.0 if strict else 0.12):
                # fully visible, or a couple of stray pixels: the restore
                # copy costs more than the two-pixel bleed it would hide
                if light and vis < 0.999:
                    self._draw_scaled(surface, fn, sx, sy, scale, z,
                                      x0, y0, x1, y1, vis)
                else:
                    draw(surface)
                continue
            if light:
                n_copy += 1
                if vis < 0.999:
                    n_scale += 1
                self._draw_scaled(surface, fn, sx, sy, scale, z,
                                  x0, y0, x1, y1, vis, occ)
                continue
            rect = pygame.Rect(x0, y0, x1 - x0, y1 - y0)
            if alpha:
                before = surface.subsurface(rect).copy()
                draw(surface)
                occ_t = occ.T
                dst = pygame.surfarray.pixels3d(surface)
                src = pygame.surfarray.pixels3d(before)
                np.copyto(dst[x0:x1, y0:y1], src, where=occ_t[:, :, None])
                del dst, src
                da = pygame.surfarray.pixels_alpha(surface)
                sa = pygame.surfarray.pixels_alpha(before)
                np.copyto(da[x0:x1, y0:y1], sa, where=occ_t)
                del da, sa
            else:
                rw, rh = x1 - x0, y1 - y0
                comp = getattr(self, "_comp_buf", None)
                if comp is None or comp.get_size() != (W, H):
                    comp = self._comp_buf = pygame.Surface((W, H), 0, surface)
                comp.blit(surface, (0, 0), rect)
                draw(surface)
                occ_t = occ.T
                dst = pygame.surfarray.pixels3d(surface)
                src = pygame.surfarray.pixels3d(comp)
                np.copyto(dst[x0:x1, y0:y1], src[:rw, :rh], where=occ_t[:, :, None])
                del dst, src
        self.stats["lights"] = n_light
        self.stats["lights_culled"] = n_cull
        self.stats["lights_gated"] = n_gate
        self.stats["light_copies"] = n_copy
        self.stats["light_scaled"] = n_scale

    def flush(self, surface=None, bg=None):
        self._deferred_overlay = None
        surface = surface or self.surface
        self._render(surface, bg=bg)
        self.begin()

    def _split_items(self, split_depth):
        far, near = [], []
        for it in self._items:
            if it[1] == "sprite":
                layer, depth = it[2][5], it[2][4]
            elif it[1] == "lines":
                layer, depth = it[2][1], 0.0
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
        for _rows, vbo, vao, _n, _c, _r in self._res.values():
            vao.release(); vbo.release()
        self._res.clear()
        for ent in self._extra:
            if ent is not None:
                ent[1].release()
        self._extra = [None, None, None]
        for o in (self._static_vao, self._static_vbo, self._dyn_vao, self._dyn_vbo,
                  self._fbo, self._color_fbo, self._color, self._aux, self._pdepth,
                  self._depth, self._sh_fbo, self._sh_tex,
                  *self._spot_fbo, *self._spot_tex, self._pl_tex, self._dummy1,
                  getattr(self, "_sky", None), getattr(self, "_sprites", None),
                  getattr(self, "_part_batch", None), getattr(self, "_decals_batch", None),
                  getattr(self, "_post", None)):
            if o is not None:
                o.release()
        self._static_vao = self._static_vbo = None
        self._comp_buf = self._light_tmp_s = self._light_mask_s = None


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