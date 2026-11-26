"""GPU sky pass and sprite/line batching for GLRenderer (Phase 1).

Renders horizon-locked night/dawn skies, procedural additive halos/shafts,
blob shadows, cached pygame Surface sprites, and anti-aliased line quads
directly inside the active HDR FBO, eliminating CPU sky repaints, sky uploads,
and GPU->CPU depth readbacks on frames without custom Python callbacks.
"""
from collections import OrderedDict
import math
import random

import numpy as np
import pygame

__all__ = ["SkyPass", "SpriteBatch", "ParticlePass", "DecalPass"]

_PDEPTH_UNIT = 5
_SURF_UNIT = 4

_SKY_VERT = """#version 330
in vec2 in_pos;
void main() {
    gl_Position = vec4(in_pos, 0.0, 1.0);
}
"""

_SKY_FRAG = """#version 330
uniform vec2 u_res;
uniform float u_hy, u_yaw, u_px_deg, u_t;
uniform vec3 u_top, u_bot;
uniform vec4 u_sodium, u_mist, u_moon;
uniform int u_clouds;
layout(location = 0) out vec4 f_color;
layout(location = 1) out vec4 f_aux;
layout(location = 2) out float f_pdepth;

float ellipse_k(vec2 p, vec2 c, vec2 rad) {
    vec2 d = (p - c) / max(rad, vec2(1.0));
    float r = length(d);
    if (r >= 1.0) return 0.0;
    float f = 1.0 - r;
    return pow(f, 2.0) + 0.04 * f;
}

void main() {
    float y_py = u_res.y - gl_FragCoord.y;
    float hy = clamp(u_hy, -u_res.y, u_res.y * 2.0);
    float y_area = clamp(floor(u_res.y * 1.8) - hy, 0.0, 2.0 * u_res.y);
    float f = clamp((y_area + y_py - u_res.y * 0.2) / max(1.0, u_res.y * 1.6), 0.0, 1.0);
    vec3 col = mix(u_top, u_bot, pow(f, 0.8));
    vec2 p = vec2(gl_FragCoord.x, y_py);

    if (u_moon.z > 0.5 && hy > 10.0) {
        float daz = mod(u_moon.x - u_yaw + 180.0, 360.0) - 180.0;
        vec2 mp = vec2(u_res.x * 0.5 + daz * u_px_deg, hy - u_moon.y * u_px_deg);
        float hrad = max(12.0, u_px_deg * 4.0);
        col += vec3(0.235, 0.259, 0.314) * ellipse_k(p, mp, vec2(hrad));
        float r_disc = max(2.0, u_px_deg * 0.55);
        if (length(p - mp) <= r_disc) {
            col = vec3(0.839, 0.863, 0.886);
        }
    }

    for (int i = 0; i < 8; i++) {
        if (i >= u_clouds) break;
        float fi = float(i);
        float cw = u_res.x * (0.45 + 0.12 * fi);
        float ch = max(6.0, u_res.y * (0.05 + 0.02 * fi));
        float drift = u_t * 0.004 * (1.0 + 0.4 * fi);
        float span = u_res.x + cw;
        float x = mod(fi * u_res.x * 0.37 + drift - u_yaw * u_px_deg * (0.9 + 0.05 * fi), span) - cw;
        float y = hy - u_res.y * (0.12 + 0.11 * fi);
        vec2 c = vec2(x + cw * 0.5, y + ch * 0.5);
        vec2 d = (p - c) / max(vec2(cw * 0.5, ch * 0.5), vec2(1.0));
        float rr = length(d);
        if (rr < 1.0) {
            float a = (rr < 0.4 ? 0.35 : (rr < 0.65 ? 0.28 : (rr < 0.85 ? 0.18 : 0.10)));
            col = mix(col, vec3(0.024, 0.031, 0.047), a);
        }
    }

    if (u_sodium.w > 0.5 && hy > -u_res.y && hy < u_res.y * 2.0) {
        col += u_sodium.rgb * ellipse_k(p, vec2(u_res.x * 0.5, hy), vec2(u_res.x * 0.7, max(8.0, u_res.y * 0.2)));
    }
    if (u_mist.w > 0.5 && hy > -20.0 && hy < u_res.y + 20.0) {
        col += u_mist.rgb * ellipse_k(p, vec2(u_res.x * 0.5, hy), vec2(u_res.x * 0.9, max(4.0, u_res.y * 0.05)));
    }

    f_color = vec4(col, 1.0);
    f_aux = vec4(0.5, 0.5, 1.0, 0.0);
    f_pdepth = 1000.0;
}
"""

_STAR_VERT = """#version 330
in vec2 in_pos;
in float in_b;
uniform vec2 u_res;
out float v_b;
void main() {
    float nx = (in_pos.x / u_res.x) * 2.0 - 1.0;
    float ny = 1.0 - (in_pos.y / u_res.y) * 2.0;
    gl_Position = vec4(nx, ny, 0.0, 1.0);
    gl_PointSize = 1.0;
    v_b = in_b;
}
"""

_STAR_FRAG = """#version 330
in float v_b;
out vec4 f_color;
void main() {
    f_color = vec4(v_b, v_b, min(1.0, v_b * 1.12), 1.0);
}
"""

_LINE_VERT = """#version 330
in vec2 in_pos;
in vec4 in_col;
in float in_depth;
out vec4 v_col;
void main() {
    gl_Position = vec4(in_pos, in_depth * 2.0 - 1.0, 1.0);
    v_col = in_col;
}
"""

_LINE_FRAG = """#version 330
in vec4 v_col;
out vec4 f_color;
void main() {
    f_color = v_col;
}
"""

# Quad sprite shader: kind 0 = halo, 1 = shaft, 2 = blob
_SPRITE_VERT = """#version 330
in vec2 in_corner;          // -1..1
in vec4 in_rect;            // sx, sy, rx, ry (px, top-left origin)
in vec4 in_col;             // rgb (0..1) + hdr
in vec4 in_core;            // rgb (0..1) + core_boost
in vec4 in_params;          // power, peak, core_r, rim
in vec4 in_occ;             // depth_enc, occ_limit_m, flags (light + 2*soft + 4*kind), hard_blob
uniform vec2 u_res;
uniform sampler2D u_pdepth;
out vec2 v_q;
out vec2 v_uv;
flat out vec4 v_col;
flat out vec4 v_core;
flat out vec4 v_params;
flat out vec4 v_occ;
flat out float v_vis;

void main() {
    vec2 px = in_rect.xy + in_corner * in_rect.zw;
    vec2 ndc = vec2((px.x / u_res.x) * 2.0 - 1.0, 1.0 - (px.y / u_res.y) * 2.0);
    int flags = int(in_occ.z + 0.5);
    bool is_light = (flags & 1) != 0;
    float vis = 1.0;
    if (is_light) {
        float seen = 0.0;
        float lit = 0.0;
        float lim = in_occ.y;
        for (int dy = -3; dy <= 3; dy += 3) {
            for (int dx = -3; dx <= 3; dx += 3) {
                vec2 ap = in_rect.xy + vec2(float(dx), float(dy));
                if (ap.x >= 0.0 && ap.x < u_res.x && ap.y >= 0.0 && ap.y < u_res.y) {
                    vec2 auv = vec2(ap.x / u_res.x, 1.0 - ap.y / u_res.y);
                    seen += 1.0;
                    if (texture(u_pdepth, auv).r >= lim) lit += 1.0;
                }
            }
        }
        vis = seen > 0.0 ? lit / seen : 1.0;
        if (vis >= 0.75) vis = 1.0;
    }
    gl_Position = vec4(ndc, in_occ.x * 2.0 - 1.0, 1.0);
    v_q = in_corner;
    v_uv = ndc * 0.5 + 0.5;
    v_col = in_col;
    v_core = in_core;
    v_params = in_params;
    v_occ = in_occ;
    v_vis = vis;
}
"""

_SPRITE_FRAG = """#version 330
in vec2 v_q;
in vec2 v_uv;
flat in vec4 v_col;
flat in vec4 v_core;
flat in vec4 v_params;
flat in vec4 v_occ;
flat in float v_vis;
uniform sampler2D u_pdepth;
out vec4 f_color;

const float BAYER[16] = float[16](0., 8., 2., 10., 12., 4., 14., 6., 3., 11., 1., 9., 15., 7., 13., 5.);

void main() {
    int flags = int(v_occ.z + 0.5);
    bool is_light = (flags & 1) != 0;
    bool is_soft = (flags & 2) != 0;
    int kind = (flags >> 2) & 3;
    if (is_light && v_vis <= 0.06) discard;
    if (is_light && !is_soft) {
        if (texture(u_pdepth, v_uv).r < v_occ.y) discard;
    }

    if (kind == 2) {
        // Blob shadow or hard blood disc
        float d = dot(v_q, v_q);
        if (d >= 1.0) discard;
        float a = v_occ.w > 0.5 ? 1.0 : pow(1.0 - d, 1.6) * v_params.y;
        f_color = vec4(v_col.rgb, a);
        return;
    }

    if (kind == 1) {
        // Tapered volumetric light shaft: v_q.y in [-1, 1] top -> bottom
        float ay = clamp(v_q.y * 0.5 + 0.5, 0.0, 1.0);
        float halfw = mix(v_params.z, 1.0, ay);
        float across = pow(clamp(1.0 - abs(v_q.x) / max(0.02, halfw), 0.0, 1.0), 1.5);
        float down = 1.0 - 0.45 * ay;
        float inten = v_params.y * across * down * v_vis;
        if (inten <= 0.002) discard;
        f_color = vec4(v_col.rgb * inten * v_col.a, 0.0);
        return;
    }

    // Kind 0: radial / squircle halo
    float power = max(0.5, v_params.x);
    float rr = pow(pow(abs(v_q.x), power) + pow(abs(v_q.y), power), 1.0 / power);
    if (rr >= 1.06) discard;
    float inten;
    if (v_params.w > 0.5) {
        float edge = clamp((1.06 - rr) / 0.22, 0.0, 1.0);
        float fill = pow(clamp(rr / 0.88, 0.0, 1.0), 2.0);
        inten = v_params.y * edge * (0.45 + 0.55 * fill);
    } else {
        float f = clamp(1.0 - rr, 0.0, 1.0);
        inten = v_params.y * (pow(f, power) + 0.04 * f * step(0.0, -v_core.a));
    }
    vec3 rgb = v_col.rgb * inten;
    if (v_core.a > 0.001 && rr < v_params.z) {
        float cf = pow(clamp(1.0 - rr / max(0.02, v_params.z), 0.0, 1.0), 1.5);
        rgb += v_core.rgb * (v_core.a * cf);
    }
    ivec2 bp = ivec2(gl_FragCoord.xy) & 3;
    float dither = (BAYER[bp.y * 4 + bp.x] / 16.0 - 0.5) * (0.7 / 255.0);
    rgb = max(vec3(0.0), rgb * v_col.a * v_vis + dither);
    f_color = vec4(rgb, 0.0);
}
"""

_SURF_VERT = """#version 330
in vec2 in_pos;     // NDC
in vec2 in_uv;
uniform float u_depth;
out vec2 v_uv;
void main() {
    gl_Position = vec4(in_pos, u_depth * 2.0 - 1.0, 1.0);
    v_uv = in_uv;
}
"""

_SURF_FRAG = """#version 330
in vec2 v_uv;
uniform sampler2D u_tex;
uniform float u_add;
out vec4 f_color;
void main() {
    vec4 c = texture(u_tex, v_uv);
    if (u_add > 0.5) {
        f_color = vec4(c.rgb * c.a, 0.0);
    } else {
        if (c.a <= 0.01) discard;
        f_color = c;
    }
}
"""
_PART_VERT = """#version 330
in vec2 in_corner;
in vec3 in_pos;
in vec3 in_vel;
in vec4 in_col;
in vec4 in_meta;   // size_m, kind, u_age, seed
uniform vec3 u_cam, u_right, u_up, u_fwd;
uniform vec2 u_res;
uniform float u_focal, u_near, u_far;
out vec2 v_q;
out vec2 v_uv;
out float v_z;
flat out vec4 v_col;
flat out vec4 v_meta;
void main() {
    vec3 d = in_pos - u_cam;
    float x = dot(d, u_right), y = dot(d, u_up), z = dot(d, u_fwd);
    if (z <= u_near) {
        gl_Position = vec4(2.0, 2.0, 2.0, 1.0);
        v_q = vec2(0.0); v_uv = vec2(0.0); v_z = -1.0; v_col = vec4(0.0); v_meta = vec4(0.0);
        return;
    }
    float sx = u_res.x * 0.5 + (x / z) * u_focal;
    float sy = u_res.y * 0.5 - (y / z) * u_focal;
    float px_r = max(1.0, in_meta.x * (u_focal / z));
    int kind = int(in_meta.y + 0.5);
    vec2 off;
    if (kind == 1 || kind == 4) {
        // Velocity-stretched streak for sparks and embers
        vec2 sv = vec2(dot(in_vel, u_right), -dot(in_vel, u_up)) * (u_focal / z) * 0.032;
        float sl = length(sv);
        vec2 dir = sl > 0.5 ? (sv / sl) : vec2(1.0, 0.0);
        vec2 perp = vec2(-dir.y, dir.x);
        float len = max(px_r, min(28.0, sl + px_r));
        off = dir * (in_corner.x * len) + perp * (in_corner.y * max(1.0, px_r * 0.55));
    } else if (kind == 2) {
        // Spinning brass casing
        float a = in_meta.w + in_meta.z * 20.0;
        float ca = cos(a), sa = sin(a);
        vec2 c = vec2(in_corner.x * 1.4, in_corner.y * 0.55) * max(1.4, px_r);
        off = vec2(c.x * ca - c.y * sa, c.x * sa + c.y * ca);
    } else {
        off = in_corner * px_r;
    }
    vec2 p = vec2(sx, sy) + off;
    vec2 ndc = vec2((p.x / u_res.x) * 2.0 - 1.0, 1.0 - (p.y / u_res.y) * 2.0);
    float slot = (kind == 1 || kind == 4) ? 6.0 : 3.0;
    float lin = clamp(z / u_far, 0.0, 1.0) * 0.999;
    float depth = ((7.0 - slot) + lin) / 8.0;
    gl_Position = vec4(ndc, depth * 2.0 - 1.0, 1.0);
    v_q = in_corner;
    v_uv = ndc * 0.5 + 0.5;
    v_z = z;
    v_col = in_col;
    v_meta = in_meta;
}
"""

_PART_FRAG = """#version 330
in vec2 v_q;
in vec2 v_uv;
in float v_z;
flat in vec4 v_col;
flat in vec4 v_meta;
uniform sampler2D u_pdepth;
uniform float u_hdr_scale;
uniform int u_mode; // 0 = alpha (smoke/dust/casing/debris), 1 = additive (spark/ember)
out vec4 f_color;
void main() {
    if (v_z <= 0.0) discard;
    int kind = int(v_meta.y + 0.5);
    bool is_add = (kind == 1 || kind == 4);
    if ((u_mode == 1) != is_add) discard;

    float sd = texture(u_pdepth, v_uv).r;
    if (sd < v_z - 0.08) discard;
    float soft = clamp((sd - v_z + 0.08) / max(0.12, v_meta.x * 1.4), 0.0, 1.0);

    float d2 = dot(v_q, v_q);
    if (kind == 2 || kind == 5) {
        if (max(abs(v_q.x), abs(v_q.y)) > 1.0) discard;
        float shade = 0.78 + 0.22 * (1.0 - v_q.y);
        f_color = vec4(v_col.rgb * shade, v_col.a * soft);
        return;
    }
    if (d2 >= 1.0) discard;
    if (is_add) {
        float core = exp(-d2 * 4.5);
        vec3 rgb = v_col.rgb * (core * v_col.a * u_hdr_scale * soft);
        f_color = vec4(rgb, 0.0);
    } else {
        float ang = atan(v_q.y, v_q.x);
        float lobe = 0.88 + 0.12 * sin(ang * 3.0 + v_meta.w);
        float f = clamp(1.0 - d2 / lobe, 0.0, 1.0);
        float a = pow(f, 1.65) * v_col.a * soft;
        if (a <= 0.005) discard;
        f_color = vec4(v_col.rgb, a);
    }
}
"""

_DECAL_VERT = """#version 330
in vec2 in_corner;
in vec3 in_pos;
in vec2 in_meta;   // radius_m, yaw_rad
in vec4 in_col;
in vec2 in_extra;  // kind, wet
uniform vec3 u_cam, u_right, u_up, u_fwd;
uniform float u_focal, u_hw, u_hh, u_near, u_far;
out vec2 v_q;
out vec2 v_uv;
out float v_z;
flat out vec4 v_col;
flat out vec2 v_extra;
flat out float v_yaw;
void main() {
    float c = cos(in_meta.y), s = sin(in_meta.y);
    vec2 rot = vec2(in_corner.x * c - in_corner.y * s,
                    in_corner.x * s + in_corner.y * c) * in_meta.x;
    vec3 w = in_pos + vec3(rot.x, 0.0, rot.y);
    vec3 d = w - u_cam;
    float x = dot(d, u_right), y = dot(d, u_up), z = dot(d, u_fwd);
    v_z = z;
    v_q = in_corner;
    v_col = in_col;
    v_extra = in_extra;
    v_yaw = in_meta.y;
    if (z <= u_near) {
        gl_Position = vec4(0.0, 0.0, -2.0, 1.0);
        v_uv = vec2(0.0);
        return;
    }
    vec4 clip = vec4(x * u_focal / u_hw, y * u_focal / u_hh,
                     (z * (u_far + u_near) - 2.0 * u_far * u_near) / (u_far - u_near), z);
    gl_Position = clip;
    v_uv = (clip.xy / clip.w) * 0.5 + 0.5;
}
"""

_DECAL_FRAG = """#version 330
in vec2 v_q;
in vec2 v_uv;
in float v_z;
flat in vec4 v_col;
flat in vec2 v_extra;
flat in float v_yaw;
uniform sampler2D u_pdepth;
out vec4 f_color;
void main() {
    if (v_z <= 0.05) discard;
    float sd = texture(u_pdepth, v_uv).r;
    if (sd >= 900.0 || abs(v_z - sd) > 0.25) discard;
    float ang = atan(v_q.y, v_q.x);
    int kind = int(v_extra.x + 0.5);
    float wobble;
    if (kind == 0) {
        wobble = 0.78 + 0.11 * sin(ang * 3.0 + v_yaw * 2.7)
               + 0.07 * cos(ang * 5.0 - v_yaw * 4.1)
               + 0.04 * sin(ang * 7.0 + v_yaw * 1.9);
    } else {
        wobble = 0.86 + 0.14 * sin(ang * 4.0 + v_yaw * 3.0) * cos(ang * 3.0 - v_yaw);
    }
    float r = length(v_q) / wobble;
    if (r >= 1.0) discard;
    float edge = smoothstep(1.0, kind == 0 ? 0.88 : 0.25, r);
    vec3 rgb = v_col.rgb;
    if (kind == 0) rgb *= mix(0.68, 0.96, smoothstep(0.0, 0.65, r)) * mix(1.0, 0.72, smoothstep(0.75, 0.98, r));
    float a = v_col.a * edge;
    if (a <= 0.01) discard;
    f_color = vec4(rgb, a);
}
"""

_CORNERS = np.array(((-1.0, -1.0), (1.0, -1.0), (-1.0, 1.0),
                     (1.0, -1.0), (1.0, 1.0), (-1.0, 1.0)), dtype=np.float32)


class SkyPass:
    """Horizon-locked GPU night/dawn sky."""

    def __init__(self, ctx):
        self.ctx = ctx
        self._prog = ctx.program(vertex_shader=_SKY_VERT, fragment_shader=_SKY_FRAG)
        self._star_prog = ctx.program(vertex_shader=_STAR_VERT, fragment_shader=_STAR_FRAG)
        quad = np.array((-1.0, -1.0, 1.0, -1.0, -1.0, 1.0, 1.0, 1.0), dtype=np.float32)
        self._vbo = ctx.buffer(quad.tobytes())
        self._vao = ctx.vertex_array(self._prog, [(self._vbo, "2f", "in_pos")])
        self._star_vbo = ctx.buffer(reserve=4096, dynamic=True)
        self._star_vao = ctx.vertex_array(self._star_prog, [(self._star_vbo, "2f 1f", "in_pos", "in_b")])
        self._star_cache = {}

    def _stars(self, seed, count, star_cut):
        key = (int(seed), int(count), float(star_cut))
        pts = self._star_cache.get(key)
        if pts is None:
            rng = random.Random(int(seed) + 404)
            out = []
            for i in range(int(count)):
                az, el, tw = rng.uniform(-180, 180), rng.uniform(0.04, 1.0), rng.random()
                if rng.random() < star_cut:
                    continue
                out.append((i, az, el, tw))
            if len(self._star_cache) > 16:
                self._star_cache.clear()
            pts = self._star_cache[key] = tuple(out)
        return pts

    def render(self, r, mrt_fbo, color_fbo, spec):
        import moderngl
        ctx = self.ctx
        w, h = r.w, r.h
        hy = float(r.horizon_y())
        yaw = math.degrees(math.atan2(r.fwd[0], r.fwd[2]))
        px_deg = w / max(1.0, float(r.fov))
        top = spec["top"]
        bot = spec["bot"]
        sod = spec.get("sodium")
        mist = spec.get("mist")
        moon = spec.get("moon")
        t = float(spec.get("t", 0.0))

        mrt_fbo.use()
        ctx.color_mask = (True, True, True, True)
        ctx.disable(moderngl.DEPTH_TEST | moderngl.BLEND | moderngl.CULL_FACE)
        p = self._prog
        p["u_res"].value = (float(w), float(h))
        p["u_hy"].value = hy
        p["u_yaw"].value = yaw
        p["u_px_deg"].value = px_deg
        p["u_t"].value = t
        p["u_top"].value = (top[0] / 255.0, top[1] / 255.0, top[2] / 255.0)
        p["u_bot"].value = (bot[0] / 255.0, bot[1] / 255.0, bot[2] / 255.0)
        p["u_sodium"].value = ((sod[0] / 255.0, sod[1] / 255.0, sod[2] / 255.0, 1.0)
                               if sod is not None else (0.0, 0.0, 0.0, 0.0))
        p["u_mist"].value = ((mist[0] / 255.0, mist[1] / 255.0, mist[2] / 255.0, 1.0)
                             if mist is not None else (0.0, 0.0, 0.0, 0.0))
        p["u_moon"].value = ((float(moon[0]), float(moon[1]), 1.0, 0.0)
                             if moon else (0.0, 0.0, 0.0, 0.0))
        p["u_clouds"].value = min(8, int(spec.get("clouds", 0)))
        self._vao.render(moderngl.TRIANGLE_STRIP)

        stars = int(spec.get("stars", 0))
        star_cut = float(spec.get("star_cut", 0.0))
        if stars > 0 and star_cut < 1.0 and hy > 4.0:
            rows = []
            h_span = min(hy, float(h)) * 0.98
            for i, az, el, tw in self._stars(spec.get("seed", 0), stars, star_cut):
                sx = w * 0.5 + ((az - yaw + 180.0) % 360.0 - 180.0) * px_deg
                sy = hy - el * h_span
                if 0.0 <= sx < w and 0.0 <= sy < hy - 3.0:
                    b = ((60.0 + 120.0 * tw) * (0.55 + 0.45 * math.sin(t * 0.0017 + i))) / 255.0
                    rows.append((sx + 0.5, sy + 0.5, b))
            if rows:
                arr = np.asarray(rows, dtype=np.float32)
                if arr.nbytes > self._star_vbo.size:
                    self._star_vao.release()
                    self._star_vbo.release()
                    self._star_vbo = ctx.buffer(reserve=arr.nbytes * 2, dynamic=True)
                    self._star_vao = ctx.vertex_array(self._star_prog, [(self._star_vbo, "2f 1f", "in_pos", "in_b")])
                self._star_vbo.write(arr)
                color_fbo.use()
                self._star_prog["u_res"].value = (float(w), float(h))
                self._star_vao.render(moderngl.POINTS, vertices=len(rows))
        mrt_fbo.use()

    def release(self):
        for o in (self._vao, self._vbo, self._star_vao, self._star_vbo):
            try:
                o.release()
            except Exception:
                pass


class SpriteBatch:
    """GPU line-quad and procedural/surface sprite renderer."""

    def __init__(self, ctx):
        self.ctx = ctx
        self._line_prog = ctx.program(vertex_shader=_LINE_VERT, fragment_shader=_LINE_FRAG)
        self._line_vbo = ctx.buffer(reserve=1 << 18, dynamic=True)
        self._line_vao = ctx.vertex_array(self._line_prog, [(self._line_vbo, "2f 4f 1f", "in_pos", "in_col", "in_depth")])

        self._spr_prog = ctx.program(vertex_shader=_SPRITE_VERT, fragment_shader=_SPRITE_FRAG)
        self._spr_vbo = ctx.buffer(reserve=1 << 19, dynamic=True)
        self._spr_vao = ctx.vertex_array(
            self._spr_prog,
            [(self._spr_vbo, "2f 4f 4f 4f 4f 4f", "in_corner", "in_rect", "in_col", "in_core", "in_params", "in_occ")],
        )

        self._surf_prog = ctx.program(vertex_shader=_SURF_VERT, fragment_shader=_SURF_FRAG)
        self._surf_vbo = ctx.buffer(reserve=256, dynamic=True)
        self._surf_vao = ctx.vertex_array(self._surf_prog, [(self._surf_vbo, "2f 2f", "in_pos", "in_uv")])
        self._surf_cache = OrderedDict()

    @staticmethod
    def partition(items):
        """Split renderer items into (gpu_items, cpu_items)."""
        gpu, cpu = [], []
        for it in items:
            _k, kind, d = it
            if callable(kind):
                cpu.append(it)
            elif kind in ("line", "lines"):
                gpu.append(it)
            elif kind == "sprite":
                fn = d[0]
                if (getattr(fn, "_gl_spec", None) is not None
                        or getattr(fn, "_gl_surf", None) is not None
                        or getattr(fn, "_gl_lines", None) is not None):
                    gpu.append(it)
                else:
                    cpu.append(it)
            else:
                cpu.append(it)
        return gpu, cpu

    def _surf_tex(self, key, surf):
        ent = self._surf_cache.get(key)
        if ent is not None and ent[0] == surf.get_size():
            self._surf_cache.move_to_end(key)
            return ent[1]
        if ent is not None:
            try:
                ent[1].release()
            except Exception:
                pass
            del self._surf_cache[key]
        import moderngl
        w, h = surf.get_size()
        raw = pygame.image.tobytes(surf, "RGBA", True)
        tex = self.ctx.texture((w, h), 4, raw)
        tex.filter = (moderngl.LINEAR, moderngl.LINEAR)
        tex.repeat_x = tex.repeat_y = False
        if len(self._surf_cache) >= 256:
            _k, (_sz, old) = self._surf_cache.popitem(last=False)
            try:
                old.release()
            except Exception:
                pass
        self._surf_cache[key] = (surf.get_size(), tex)
        return tex

    def _emit_line_quads(self, w, h, segs, depth_enc):
        rows = []
        hw, hh = w * 0.5, h * 0.5
        for p0, p1, col, width in segs:
            x0, y0 = p0[0], p0[1]
            x1, y1 = p1[0], p1[1]
            dx, dy = x1 - x0, y1 - y0
            ln = math.hypot(dx, dy)
            if ln < 1e-4:
                nx, ny = 0.0, max(0.5, width * 0.5)
            else:
                rad = max(0.5, float(width) * 0.5)
                nx, ny = -dy / ln * rad, dx / ln * rad
            r_ = col[0] / 255.0
            g_ = col[1] / 255.0
            b_ = col[2] / 255.0
            a_ = (col[3] / 255.0) if len(col) > 3 else 1.0
            ax, ay = (x0 + nx) / hw - 1.0, 1.0 - (y0 + ny) / hh
            bx, by = (x0 - nx) / hw - 1.0, 1.0 - (y0 - ny) / hh
            cx, cy = (x1 + nx) / hw - 1.0, 1.0 - (y1 + ny) / hh
            dx2, dy2 = (x1 - nx) / hw - 1.0, 1.0 - (y1 - ny) / hh
            rows.extend((
                (ax, ay, r_, g_, b_, a_, depth_enc),
                (bx, by, r_, g_, b_, a_, depth_enc),
                (cx, cy, r_, g_, b_, a_, depth_enc),
                (bx, by, r_, g_, b_, a_, depth_enc),
                (dx2, dy2, r_, g_, b_, a_, depth_enc),
                (cx, cy, r_, g_, b_, a_, depth_enc),
            ))
        return rows

    def _draw_line_rows(self, rows, depth_test):
        if not rows:
            return
        import moderngl
        ctx = self.ctx
        arr = np.asarray(rows, dtype=np.float32)
        if arr.nbytes > self._line_vbo.size:
            self._line_vao.release()
            self._line_vbo.release()
            self._line_vbo = ctx.buffer(reserve=max(arr.nbytes, self._line_vbo.size * 2), dynamic=True)
            self._line_vao = ctx.vertex_array(self._line_prog, [(self._line_vbo, "2f 4f 1f", "in_pos", "in_col", "in_depth")])
        self._line_vbo.write(arr)
        if depth_test:
            ctx.enable(moderngl.DEPTH_TEST)
            ctx.depth_func = "<="
        else:
            ctx.disable(moderngl.DEPTH_TEST)
        ctx.depth_mask = False
        ctx.enable(moderngl.BLEND)
        ctx.blend_func = (moderngl.SRC_ALPHA, moderngl.ONE_MINUS_SRC_ALPHA, moderngl.ZERO, moderngl.ONE)
        self._line_vao.render(moderngl.TRIANGLES, vertices=len(rows))

    def _draw_quad_batch(self, r, pdepth_tex, batch, additive):
        if not batch:
            return
        import moderngl
        ctx = self.ctx
        pdepth_tex.use(location=_PDEPTH_UNIT)
        self._spr_prog["u_res"].value = (float(r.w), float(r.h))
        self._spr_prog["u_pdepth"].value = _PDEPTH_UNIT
        n = len(batch)
        arr = np.empty((n * 6, 22), dtype=np.float32)
        arr[:, 0:2] = np.tile(_CORNERS, (n, 1))
        for i, row in enumerate(batch):
            arr[i * 6:(i + 1) * 6, 2:22] = row
        if arr.nbytes > self._spr_vbo.size:
            self._spr_vao.release()
            self._spr_vbo.release()
            self._spr_vbo = ctx.buffer(reserve=max(arr.nbytes, self._spr_vbo.size * 2), dynamic=True)
            self._spr_vao = ctx.vertex_array(
                self._spr_prog,
                [(self._spr_vbo, "2f 4f 4f 4f 4f 4f",
                  "in_corner", "in_rect", "in_col", "in_core", "in_params", "in_occ")],
            )
        self._spr_vbo.write(arr)
        ctx.enable(moderngl.DEPTH_TEST)
        ctx.depth_func = "<="
        ctx.depth_mask = False
        ctx.enable(moderngl.BLEND)
        if additive:
            ctx.blend_func = (moderngl.ONE, moderngl.ONE, moderngl.ZERO, moderngl.ONE)
        else:
            ctx.blend_func = (moderngl.SRC_ALPHA, moderngl.ONE_MINUS_SRC_ALPHA, moderngl.ZERO, moderngl.ONE)
        self._spr_vao.render(moderngl.TRIANGLES, vertices=n * 6)

    def _draw_surface_quad(self, r, key, surf, x_px, y_px, w_px, h_px, additive, depth_enc, depth_test=True):
        import moderngl
        ctx = self.ctx
        tex = self._surf_tex(key, surf)
        tex.use(location=_SURF_UNIT)
        hw, hh = r.w * 0.5, r.h * 0.5
        x0, x1 = x_px / hw - 1.0, (x_px + w_px) / hw - 1.0
        y0, y1 = 1.0 - y_px / hh, 1.0 - (y_px + h_px) / hh
        verts = np.array((
            x0, y0, 0.0, 1.0,
            x1, y0, 1.0, 1.0,
            x0, y1, 0.0, 0.0,
            x1, y1, 1.0, 0.0,
        ), dtype=np.float32)
        self._surf_vbo.write(verts)
        self._surf_prog["u_tex"].value = _SURF_UNIT
        self._surf_prog["u_depth"].value = depth_enc
        self._surf_prog["u_add"].value = 1.0 if additive else 0.0
        if depth_test:
            ctx.enable(moderngl.DEPTH_TEST)
            ctx.depth_func = "<="
        else:
            ctx.disable(moderngl.DEPTH_TEST)
        ctx.depth_mask = False
        ctx.enable(moderngl.BLEND)
        if additive:
            ctx.blend_func = (moderngl.ONE, moderngl.ONE, moderngl.ZERO, moderngl.ONE)
        else:
            ctx.blend_func = (moderngl.SRC_ALPHA, moderngl.ONE_MINUS_SRC_ALPHA, moderngl.ZERO, moderngl.ONE)
        self._surf_vao.render(moderngl.TRIANGLE_STRIP, vertices=4)

    def render(self, r, color_fbo, pdepth_tex, gpu_items, overlay=False):
        if not gpu_items:
            return
        import moderngl
        ctx = self.ctx
        color_fbo.use()
        w, h = r.w, r.h
        hdr_scale = 1.0 if not getattr(r, "hdr", False) else 1.35
        items = sorted(gpu_items, key=lambda it: it[0])

        line_depth_rows, line_nodepth_rows = [], []
        alpha_quads, add_quads = [], []

        for _key, kind, d in items:
            if kind == "line":
                col, width, scr, layer = d
                if len(scr) >= 2:
                    enc = r._enc(layer, 0.0) - 1e-6
                    segs = [(scr[0], scr[1], col, width)]
                    if overlay:
                        line_nodepth_rows.extend(self._emit_line_quads(w, h, segs, enc))
                    else:
                        line_depth_rows.extend(self._emit_line_quads(w, h, segs, enc))
                continue
            if kind == "lines":
                segs, layer, depth_test = d
                if segs:
                    enc = r._enc(layer, 0.0) - 1e-6
                    target = line_nodepth_rows if (overlay or not depth_test) else line_depth_rows
                    target.extend(self._emit_line_quads(w, h, segs, enc))
                continue

            fn, sx, sy, scale, z, layer, zeff = d[:7]
            enc = r._enc(layer, zeff) - 1e-6

            lines_fn = getattr(fn, "_gl_lines", None)
            if lines_fn is not None:
                segs = lines_fn(sx, sy, scale, z)
                if segs:
                    line_depth_rows.extend(self._emit_line_quads(w, h, segs, enc))
                continue

            surf_fn = getattr(fn, "_gl_surf", None)
            if surf_fn is not None:
                # Flush queued batches before ordered surface draw
                if alpha_quads:
                    self._draw_quad_batch(r, pdepth_tex, alpha_quads, False)
                    alpha_quads.clear()
                if add_quads:
                    self._draw_quad_batch(r, pdepth_tex, add_quads, True)
                    add_quads.clear()
                entries = surf_fn(sx, sy, scale, z)
                if entries:
                    for key_s, surf, x0, y0, wp, hp, additive in entries:
                        if wp > 0 and hp > 0:
                            self._draw_surface_quad(r, key_s, surf, x0, y0, wp, hp, additive, enc,
                                                    depth_test=not overlay)
                continue

            spec = getattr(fn, "_gl_spec", None)
            if spec is None:
                continue
            skind = spec["kind"]
            is_light = bool(getattr(fn, "light", False))
            is_soft = bool(getattr(fn, "light_soft", False))
            occ_bias = float(getattr(fn, "occ_bias", 0.45 if is_light else 0.18))
            occ_lim = max(0.0, float(zeff) - occ_bias)

            if skind == "blob":
                if not getattr(r, "blob_shadows", True) and not spec.get("hard"):
                    continue
                if "rx_px" in spec:
                    rx = max(2.0, float(spec["rx_px"]) * 0.5)
                    ry = max(1.5, float(spec["ry_px"]) * 0.5)
                else:
                    rx = max(1.0, float(spec["rx_m"]) * scale)
                    ry = max(1.0, float(spec["ry_m"]) * scale)
                if sx + rx < 0 or sx - rx > w or sy + ry < 0 or sy - ry > h:
                    continue
                col = spec.get("col", (0.0, 0.0, 0.0))
                strength = float(spec.get("strength", 0.35))
                hard = 1.0 if spec.get("hard") else 0.0
                row = (
                    float(sx), float(sy), float(rx), float(ry),
                    col[0], col[1], col[2], 1.0,
                    0.0, 0.0, 0.0, 0.0,
                    2.0, strength, 0.0, 0.0,
                    enc, occ_lim, float((2 << 2) | (2 if is_soft else 0) | (1 if is_light else 0)), hard,
                )
                alpha_quads.append(row)
                continue

            if skind == "shaft":
                sh = float(spec["height_m"]) * scale
                wbot = min(260.0, float(spec["bot_m"]) * scale)
                wtop = min(260.0, float(spec["top_m"]) * scale)
                if sh < 6.0 or wbot < 2.0:
                    continue
                cy = sy + sh * 0.5
                cx = sx + float(spec.get("sway_m", 0.0)) * scale * 0.5
                if cx + wbot < 0 or cx - wbot > w or cy + sh * 0.5 < 0 or cy - sh * 0.5 > h:
                    continue
                col = spec["col"]
                row = (
                    float(cx), float(cy), float(wbot), float(sh * 0.5),
                    col[0] / 255.0, col[1] / 255.0, col[2] / 255.0, hdr_scale,
                    0.0, 0.0, 0.0, 0.0,
                    1.0, 0.55, max(0.02, wtop / max(1.0, wbot)), 0.0,
                    enc, occ_lim, float((1 << 2) | (2 if is_soft else 0) | (1 if is_light else 0)), 0.0,
                )
                add_quads.append(row)
                continue

            # Halo
            inten = float(spec.get("intensity", 1.0))
            if inten <= 0.02:
                continue
            far_fade = spec.get("far_fade")
            air = 1.0
            if far_fade is not None:
                air = max(0.0, min(1.0, (far_fade - z) / float(spec.get("far_span", 20.0))))
            rad_m = float(spec.get("radius_m", 0.0))
            squash = float(spec.get("squash", 1.0))
            max_px = float(spec.get("max_px", 260.0))
            if "rx_m" in spec:
                rx = min(max_px, max(1.5, float(spec["rx_m"]) * scale))
                ry = min(float(spec.get("max_py", max_px)), max(1.5, float(spec["ry_m"]) * scale))
            else:
                rx = min(max_px, max(1.5, rad_m * scale))
                ry = min(float(spec.get("max_py", max_px)), max(1.5, rx * squash))
            if sx + rx < 0 or sx - rx > w or sy + ry < 0 or sy - ry > h:
                continue
            col = spec["col"]
            core = spec.get("core")
            peak = float(spec.get("peak", 1.0)) * inten * air
            core_boost = float(spec.get("core_boost", 0.0)) * inten
            if peak <= 0.01 and core_boost <= 0.01:
                continue
            hdr = float(spec.get("hdr", 1.0)) * (hdr_scale if getattr(r, "hdr", False) else 1.0)
            power = float(spec.get("power", 2.0))
            core_r = float(spec.get("core_r", 0.2))
            rim = 1.0 if spec.get("rim") else 0.0
            glow_tail = 1.0 if spec.get("m5_tail") else -1.0
            row = (
                float(sx), float(sy), float(rx), float(ry),
                col[0] / 255.0, col[1] / 255.0, col[2] / 255.0, hdr,
                (core[0] / 255.0 if core else 0.0),
                (core[1] / 255.0 if core else 0.0),
                (core[2] / 255.0 if core else 0.0),
                (core_boost if core else glow_tail),
                power, peak, core_r, rim,
                enc, occ_lim, float((2 if (is_soft or overlay) else 0) | (1 if is_light else 0)), 0.0,
            )
            add_quads.append(row)

        if alpha_quads:
            self._draw_quad_batch(r, pdepth_tex, alpha_quads, False)
        if add_quads:
            self._draw_quad_batch(r, pdepth_tex, add_quads, True)
        if line_depth_rows:
            self._draw_line_rows(line_depth_rows, depth_test=True)
        if line_nodepth_rows:
            self._draw_line_rows(line_nodepth_rows, depth_test=False)

        ctx.disable(moderngl.BLEND)
        ctx.depth_mask = True
        ctx.depth_func = "<"

    def release(self):
        for o in (self._line_vao, self._line_vbo, self._spr_vao, self._spr_vbo,
                  self._surf_vao, self._surf_vbo):
            try:
                o.release()
            except Exception:
                pass
        for _k, (_sz, tex) in self._surf_cache.items():
            try:
                tex.release()
            except Exception:
                pass
        self._surf_cache.clear()


class ParticlePass:
    """Hardware-instanced particle renderer tested against physical depth."""

    def __init__(self, ctx):
        self.ctx = ctx
        self._prog = ctx.program(vertex_shader=_PART_VERT, fragment_shader=_PART_FRAG)
        quad = np.array((-1.0, -1.0, 1.0, -1.0, -1.0, 1.0, 1.0, 1.0), dtype=np.float32)
        self._qbo = ctx.buffer(quad.tobytes())
        self._ibo = ctx.buffer(reserve=1 << 17, dynamic=True)
        self._vao = ctx.vertex_array(
            self._prog,
            [
                (self._qbo, "2f", "in_corner"),
                (self._ibo, "3f 3f 4f 4f/i", "in_pos", "in_vel", "in_col", "in_meta"),
            ],
        )

    def render(self, r, color_fbo, pdepth_tex, chunks):
        if not chunks:
            return
        import moderngl
        data = chunks[0] if len(chunks) == 1 else np.concatenate(chunks, axis=0)
        if not len(data):
            return
        if not data.flags["C_CONTIGUOUS"]:
            data = np.ascontiguousarray(data, dtype=np.float32)
        if data.nbytes > self._ibo.size:
            old_size = self._ibo.size
            self._vao.release()
            self._ibo.release()
            self._ibo = self.ctx.buffer(reserve=max(data.nbytes, old_size * 2), dynamic=True)
            self._vao = self.ctx.vertex_array(
                self._prog,
                [
                    (self._qbo, "2f", "in_corner"),
                    (self._ibo, "3f 3f 4f 4f/i", "in_pos", "in_vel", "in_col", "in_meta"),
                ],
            )
        self._ibo.write(data)
        ctx = self.ctx
        color_fbo.use()
        pdepth_tex.use(location=_PDEPTH_UNIT)
        p = self._prog
        p["u_cam"].value = tuple(r.cam)
        p["u_right"].value = tuple(r.right)
        p["u_up"].value = tuple(r.up)
        p["u_fwd"].value = tuple(r.fwd)
        p["u_res"].value = (float(r.w), float(r.h))
        p["u_focal"].value = float(r.focal)
        p["u_near"].value = float(r.NEAR)
        p["u_far"].value = float(r._far)
        p["u_pdepth"].value = _PDEPTH_UNIT
        p["u_hdr_scale"].value = 1.65 if getattr(r, "hdr", False) else 1.0

        ctx.disable(moderngl.DEPTH_TEST | moderngl.CULL_FACE)
        ctx.depth_mask = False
        ctx.enable(moderngl.BLEND)
        n = len(data)
        # Alpha pass (smoke, dust, casings, debris)
        p["u_mode"].value = 0
        ctx.blend_func = (moderngl.SRC_ALPHA, moderngl.ONE_MINUS_SRC_ALPHA, moderngl.ZERO, moderngl.ONE)
        self._vao.render(moderngl.TRIANGLE_STRIP, vertices=4, instances=n)
        # Additive pass (sparks, embers)
        p["u_mode"].value = 1
        ctx.blend_func = (moderngl.ONE, moderngl.ONE, moderngl.ZERO, moderngl.ONE)
        self._vao.render(moderngl.TRIANGLE_STRIP, vertices=4, instances=n)
        ctx.disable(moderngl.BLEND)
        ctx.depth_mask = True

    def release(self):
        for o in (self._vao, self._qbo, self._ibo):
            try:
                o.release()
            except Exception:
                pass


class DecalPass:
    """Hardware-instanced ground decal renderer (blood, scorch, impacts)."""

    def __init__(self, ctx):
        self.ctx = ctx
        self._prog = ctx.program(vertex_shader=_DECAL_VERT, fragment_shader=_DECAL_FRAG)
        quad = np.array((-1.0, -1.0, 1.0, -1.0, -1.0, 1.0, 1.0, 1.0), dtype=np.float32)
        self._qbo = ctx.buffer(quad.tobytes())
        self._ibo = ctx.buffer(reserve=1 << 16, dynamic=True)
        self._vao = ctx.vertex_array(
            self._prog,
            [
                (self._qbo, "2f", "in_corner"),
                (self._ibo, "3f 2f 4f 2f/i", "in_pos", "in_meta", "in_col", "in_extra"),
            ],
        )

    def render(self, r, color_fbo, pdepth_tex, chunks):
        if not chunks:
            return
        import moderngl
        data = chunks[0] if len(chunks) == 1 else np.concatenate(chunks, axis=0)
        if not len(data):
            return
        if not data.flags["C_CONTIGUOUS"]:
            data = np.ascontiguousarray(data, dtype=np.float32)
        if data.nbytes > self._ibo.size:
            old_size = self._ibo.size
            self._vao.release()
            self._ibo.release()
            self._ibo = self.ctx.buffer(reserve=max(data.nbytes, old_size * 2), dynamic=True)
            self._vao = self.ctx.vertex_array(
                self._prog,
                [
                    (self._qbo, "2f", "in_corner"),
                    (self._ibo, "3f 2f 4f 2f/i", "in_pos", "in_meta", "in_col", "in_extra"),
                ],
            )
        self._ibo.write(data)
        ctx = self.ctx
        color_fbo.use()
        pdepth_tex.use(location=_PDEPTH_UNIT)
        p = self._prog
        p["u_cam"].value = tuple(r.cam)
        p["u_right"].value = tuple(r.right)
        p["u_up"].value = tuple(r.up)
        p["u_fwd"].value = tuple(r.fwd)
        p["u_focal"].value = float(r.focal)
        p["u_hw"].value = float(r.w * 0.5)
        p["u_hh"].value = float(r.h * 0.5)
        p["u_near"].value = float(r.NEAR)
        p["u_far"].value = float(r._far)
        p["u_pdepth"].value = _PDEPTH_UNIT
        ctx.disable(moderngl.DEPTH_TEST | moderngl.CULL_FACE)
        ctx.depth_mask = False
        ctx.enable(moderngl.BLEND)
        ctx.blend_func = (moderngl.SRC_ALPHA, moderngl.ONE_MINUS_SRC_ALPHA, moderngl.ZERO, moderngl.ONE)
        self._vao.render(moderngl.TRIANGLE_STRIP, vertices=4, instances=len(data))
        ctx.disable(moderngl.BLEND)
        ctx.depth_mask = True

    def release(self):
        for o in (self._vao, self._qbo, self._ibo):
            try:
                o.release()
            except Exception:
                pass