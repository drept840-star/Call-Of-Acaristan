"""GPU HDR bloom, grading, 2.5D lightmap, Bayer dither and crisp upscale (Phase 1).

Runs completely inside the GL context and performs one final readback at the
target display resolution, replacing CPU apply_lut, CPU grade3d lightmaps,
CPU vignette/grain, and CPU present_crisp 2x upscales.
"""
from collections import OrderedDict
import math

import numpy as np
import pygame

__all__ = ["PostPipeline"]

_FULL_VERT = """#version 330
in vec2 in_pos;
out vec2 v_uv;
void main() {
    v_uv = in_pos * 0.5 + 0.5;
    gl_Position = vec4(in_pos, 0.0, 1.0);
}
"""

_MRT_CLEAR_FRAG = """#version 330
uniform vec4 u_color;
layout(location = 0) out vec4 f_color;
layout(location = 1) out vec4 f_aux;
layout(location = 2) out float f_pdepth;
void main() {
    f_color = u_color;
    f_aux = vec4(0.5, 0.5, 1.0, 0.0);
    f_pdepth = 1000.0;
}
"""

_DEPTH_CLEAR_FRAG = """#version 330
void main() {
    gl_FragDepth = 1.0;
}
"""

_BG_UPLOAD_FRAG = """#version 330
in vec2 v_uv;
uniform sampler2D u_bg;
uniform bool u_raw;
layout(location = 0) out vec4 f_color;
layout(location = 1) out vec4 f_aux;
layout(location = 2) out float f_pdepth;
void main() {
    // u_raw: texture holds the surface's own top-down BGRX bytes
    vec4 c = texture(u_bg, u_raw ? vec2(v_uv.x, 1.0 - v_uv.y) : v_uv);
    f_color = u_raw ? vec4(c.bgr, 1.0) : c;
    f_aux = vec4(0.5, 0.5, 1.0, 0.0);
    f_pdepth = 1000.0;
}
"""

_BRIGHT_FRAG = """#version 330
in vec2 v_uv;
uniform sampler2D u_src;
uniform float u_knee;
uniform float u_cap;
out vec4 f_color;
void main() {
    vec3 c = texture(u_src, v_uv).rgb;
    float luma = dot(c, vec3(0.2126, 0.7152, 0.0722));
    float excess = max(0.0, luma - u_knee);
    float w = excess / max(luma, 1e-4);
    vec3 outc = min(vec3(u_cap), c * w * 1.35);
    f_color = vec4(outc, 1.0);
}
"""

_BLUR_FRAG = """#version 330
in vec2 v_uv;
uniform sampler2D u_src;
uniform vec2 u_step;
out vec4 f_color;
void main() {
    vec3 sum = texture(u_src, v_uv).rgb * 0.227027;
    sum += texture(u_src, v_uv + u_step * 1.384615).rgb * 0.316216;
    sum += texture(u_src, v_uv - u_step * 1.384615).rgb * 0.316216;
    sum += texture(u_src, v_uv + u_step * 3.230769).rgb * 0.070270;
    sum += texture(u_src, v_uv - u_step * 3.230769).rgb * 0.070270;
    f_color = vec4(sum, 1.0);
}
"""

_LM_QUAD_VERT = """#version 330
in vec2 in_corner;      // -1..1
in vec4 in_rect;        // cx, cy, rx, ry in 0..1 UV space
in vec4 in_col;         // rgb (0..2+), kind (0=pool, 1=glow, 2=reflect, 3=cone)
in vec4 in_cone;        // cos_a, sin_a, reach_uv, body_uv
out vec2 v_q;
flat out vec4 v_col;
flat out vec4 v_cone;
void main() {
    vec2 uv = in_rect.xy + in_corner * in_rect.zw;
    gl_Position = vec4(uv * 2.0 - 1.0, 0.0, 1.0);
    v_q = in_corner;
    v_col = in_col;
    v_cone = in_cone;
}
"""

_LM_QUAD_FRAG = """#version 330
in vec2 v_q;
flat in vec4 v_col;
flat in vec4 v_cone;
out vec4 f_color;
void main() {
    int kind = int(v_col.a + 0.5);
    if (kind == 3) {
        // Directional flashlight cone
        vec2 p = v_q * v_cone.z;
        float fwd = p.x * v_cone.x + p.y * v_cone.y;
        float lat = -p.x * v_cone.y + p.y * v_cone.x;
        float dist = length(p);
        float cone_r = dist / max(1e-3, v_cone.z);
        float ang_r = abs(lat) / max(2.5, fwd * 0.48 + 2.5);
        float ci = (fwd > -1.5 && cone_r < 1.0 && ang_r < 1.0)
            ? 0.86 * pow(max(0.0, 1.0 - cone_r), 1.3) * pow(max(0.0, 1.0 - ang_r * ang_r), 1.6)
            : 0.0;
        float br = dist / 12.0;
        float bi = br < 1.0 ? 0.34 * pow(max(0.0, 1.0 - br * br), 1.6) : 0.0;
        float tot = max(ci, bi);
        if (tot <= 0.005) discard;
        f_color = vec4(v_col.rgb * tot, 0.0);
        return;
    }
    float d2 = dot(v_q, v_q);
    if (d2 >= 1.0) discard;
    float f = 0.0;
    if (kind == 1) {
        f = clamp(0.38 * exp(-d2 * 3.0) * (1.0 - d2) + 0.72 * exp(-d2 * 16.0), 0.0, 1.0);
    } else if (kind == 2) {
        float ripple = 0.56 + 0.44 * sin((v_q.y * 64.0 + 64.0) * 0.72 + (v_q.x * 64.0 + 64.0) * 0.14);
        f = ripple * exp(-v_q.x * v_q.x * 3.8) * pow(1.0 - d2, 1.35);
    } else {
        f = exp(-d2 * 2.1) * pow(1.0 - d2, 1.35);
    }
    f_color = vec4(v_col.rgb * f, 0.0);
}
"""

_SSAO_FRAG = """#version 330
in vec2 v_uv;
uniform sampler2D u_pdepth;
uniform sampler2D u_aux;
uniform float u_focal, u_hw, u_hh;
uniform int u_taps;
out vec4 f_color;

float hash12(vec2 p) {
    vec3 p3 = fract(p.xyx * 0.1031);
    p3 += dot(p3, p3.yzx + 33.33);
    return fract((p3.x + p3.y) * p3.z);
}

void main() {
    float d = texture(u_pdepth, v_uv).r;
    if (d >= 900.0) {
        f_color = vec4(1.0);
        return;
    }
    vec4 aux = texture(u_aux, v_uv);
    if (aux.a > 0.90) {
        f_color = vec4(1.0);
        return;
    }
    vec3 n = normalize(aux.rgb * 2.0 - 1.0);
    vec2 ndc = v_uv * 2.0 - 1.0;
    vec3 P = vec3(ndc.x * (u_hw / u_focal) * d, ndc.y * (u_hh / u_focal) * d, d);
    vec3 up_v = abs(n.y) < 0.9 ? vec3(0.0, 1.0, 0.0) : vec3(1.0, 0.0, 0.0);
    vec3 T = normalize(cross(up_v, n));
    vec3 B = cross(n, T);
    float rad = clamp(0.42 + d * 0.022, 0.42, 1.05);
    float bias = 0.035 + 0.0022 * d;
    float rot = hash12(gl_FragCoord.xy) * 6.283185;
    float occ = 0.0;
    for (int i = 0; i < 12; i++) {
        if (i >= u_taps) break;
        float fi = float(i) + 0.5;
        float ang = fi * 2.399963 + rot;
        float rr = sqrt(fi / float(u_taps));
        float hz = mix(0.22, 0.92, fract(fi * 0.618034));
        vec3 hdir = normalize(vec3(cos(ang) * rr, sin(ang) * rr, hz));
        vec3 sdir = T * hdir.x + B * hdir.y + n * hdir.z;
        vec3 S = P + sdir * (rad * (0.25 + 0.75 * rr));
        if (S.z <= 0.1) continue;
        vec2 suv = vec2((S.x / S.z) * (u_focal / u_hw) * 0.5 + 0.5,
                        (S.y / S.z) * (u_focal / u_hh) * 0.5 + 0.5);
        if (any(lessThan(suv, vec2(0.0))) || any(greaterThan(suv, vec2(1.0)))) continue;
        float sd = texture(u_pdepth, suv).r;
        float rc = smoothstep(0.0, 1.0, rad / max(0.05, abs(P.z - sd)));
        occ += (sd < S.z - bias ? 1.0 : 0.0) * rc;
    }
    float ao = pow(clamp(1.0 - occ / float(max(1, u_taps)), 0.0, 1.0), 1.45);
    f_color = vec4(ao, ao, ao, 1.0);
}
"""

_SSAO_BLUR_FRAG = """#version 330
in vec2 v_uv;
uniform sampler2D u_ssao;
uniform sampler2D u_pdepth;
uniform sampler2D u_aux;
uniform vec2 u_texel;
out vec4 f_color;
void main() {
    float d0 = texture(u_pdepth, v_uv).r;
    if (d0 >= 900.0) {
        f_color = vec4(1.0);
        return;
    }
    vec3 n0 = normalize(texture(u_aux, v_uv).rgb * 2.0 - 1.0);
    float sum = 0.0, wsum = 0.0;
    for (int y = -1; y <= 1; y++) {
        for (int x = -1; x <= 1; x++) {
            vec2 uv = clamp(v_uv + vec2(float(x), float(y)) * u_texel, vec2(0.0), vec2(1.0));
            float d = texture(u_pdepth, uv).r;
            vec3 n = normalize(texture(u_aux, uv).rgb * 2.0 - 1.0);
            float w = exp(-abs(d - d0) * 2.8) * pow(max(0.0, dot(n, n0)), 4.0);
            w = max(0.001, w);
            sum += texture(u_ssao, uv).r * w;
            wsum += w;
        }
    }
    float ao = sum / max(1e-4, wsum);
    f_color = vec4(ao, ao, ao, 1.0);
}
"""

_ATMOS_FRAG = """#version 330
in vec2 v_uv;
uniform sampler2D u_hdr;
uniform sampler2D u_aux;
uniform sampler2D u_pdepth;
uniform sampler2D u_ssao;
uniform sampler2D u_pl_tex;
uniform vec3 u_cam, u_right, u_up, u_fwd;
uniform float u_focal, u_hw, u_hh;
uniform float u_ssao_str, u_wet, u_marble, u_time;
uniform int u_ssr_steps, u_pl_n;
uniform vec3 u_sky_col, u_hf_col;
uniform vec4 u_hf_params; // density, base_y, falloff, max_opacity
out vec4 f_color;

float hash12(vec2 p) {
    vec3 p3 = fract(p.xyx * 0.1031);
    p3 += dot(p3, p3.yzx + 33.33);
    return fract((p3.x + p3.y) * p3.z);
}

void main() {
    vec4 base = texture(u_hdr, v_uv);
    float d = texture(u_pdepth, v_uv).r;
    if (d >= 900.0) {
        f_color = base;
        return;
    }
    vec4 aux = texture(u_aux, v_uv);
    float mat = aux.a;
    vec3 vn = normalize(aux.rgb * 2.0 - 1.0);
    vec2 ndc = v_uv * 2.0 - 1.0;
    vec3 P = vec3(ndc.x * (u_hw / u_focal) * d, ndc.y * (u_hh / u_focal) * d, d);
    vec3 W = u_cam + u_right * P.x + u_up * P.y + u_fwd * P.z;
    vec3 col = base.rgb;

    if (u_ssao_str > 0.01 && mat < 0.90) {
        float ao = texture(u_ssao, v_uv).r;
        float str = (mat > 0.65 && mat < 0.85) ? u_ssao_str * 0.42 : u_ssao_str;
        col *= mix(1.0, ao, str);
    }

    bool is_refl = (mat > 0.38 && mat < 0.62);
    if (is_refl && (u_wet > 0.02 || u_marble > 0.02)) {
        vec3 wn = normalize(u_right * vn.x + u_up * vn.y + u_fwd * vn.z);
        float pud = 0.0;
        if (u_wet > 0.02) {
            float n1 = sin(W.x * 0.43 + sin(W.z * 0.35)) * 0.5 + 0.5;
            float n2 = cos(W.z * 0.59 - sin(W.x * 0.51)) * 0.5 + 0.5;
            pud = smoothstep(0.46, 0.74, (n1 * 0.55 + n2 * 0.45) * (0.65 + 0.35 * u_wet));
        }
        float refl_w = max(u_marble * 0.44, pud * u_wet * 0.76 + u_wet * 0.14);
        vec3 Nw = wn;
        if (u_wet > 0.10 && pud > 0.05) {
            float rip = sin(W.x * 9.5 + u_time * 4.2) * cos(W.z * 9.5 - u_time * 3.7);
            Nw = normalize(wn + vec3(rip * 0.032 * pud, 0.0, -rip * 0.032 * pud));
        }
        vec3 Nv = normalize(vec3(dot(Nw, u_right), dot(Nw, u_up), dot(Nw, u_fwd)));
        vec3 V = normalize(P);
        vec3 R = reflect(V, Nv);
        vec3 ssr_col = vec3(0.0);
        float ssr_hit = 0.0;
        if (u_ssr_steps > 0 && refl_w > 0.08 && R.z > -0.82) {
            float step_m = clamp(d * 0.045, 0.22, 0.72);
            float jit = hash12(gl_FragCoord.xy);
            vec3 ray = P + R * (step_m * (0.35 + 0.65 * jit));
            for (int s = 0; s < 12; s++) {
                if (s >= u_ssr_steps || ray.z <= 0.15) break;
                vec2 ruv = vec2((ray.x / ray.z) * (u_focal / u_hw) * 0.5 + 0.5,
                                (ray.y / ray.z) * (u_focal / u_hh) * 0.5 + 0.5);
                if (any(lessThan(ruv, vec2(0.01))) || any(greaterThan(ruv, vec2(0.99)))) break;
                float sd = texture(u_pdepth, ruv).r;
                float diff = ray.z - sd;
                if (diff > 0.02 && diff < step_m * 2.2 && sd < 900.0) {
                    float edge = smoothstep(0.01, 0.10, min(min(ruv.x, 1.0 - ruv.x), min(ruv.y, 1.0 - ruv.y)));
                    ssr_col = texture(u_hdr, ruv).rgb;
                    ssr_hit = edge * (1.0 - float(s) / float(u_ssr_steps + 1));
                    break;
                }
                ray += R * step_m;
                step_m *= 1.12;
            }
        }
        vec3 spec_col = vec3(0.0);
        vec3 Vw = normalize(u_cam - W);
        vec3 Rw = reflect(-Vw, Nw);
        for (int i = 0; i < 64; i++) {
            if (i >= u_pl_n) break;
            vec4 p0 = texelFetch(u_pl_tex, ivec2(i, 0), 0);
            vec4 c0 = texelFetch(u_pl_tex, ivec2(i, 1), 0);
            vec4 d0 = texelFetch(u_pl_tex, ivec2(i, 2), 0);
            vec3 lv = p0.xyz - W;
            float ld = length(lv);
            float rng = p0.w * 1.45;
            if (ld >= rng || ld < 0.05) continue;
            vec3 L = lv / ld;
            float fall = pow(max(0.0, 1.0 - ld / rng), 1.8) * c0.w;
            if (d0.w > -0.5) {
                float ca = dot(-L, d0.xyz);
                if (ca <= d0.w) continue;
                fall *= min(1.0, (ca - d0.w) / 0.12);
            }
            float sp = pow(max(0.0, dot(Rw, L)), mix(22.0, 68.0, max(pud, u_marble)));
            spec_col += (c0.rgb / 255.0) * (sp * fall * 0.90);
        }
        col *= (1.0 - 0.28 * pud * u_wet);
        float fres = mix(0.20, 0.72, pow(1.0 - max(0.0, dot(Vw, Nw)), 2.4));
        vec3 env = mix(u_sky_col * 0.32, ssr_col, ssr_hit);
        col += (env * fres + spec_col) * refl_w;
    }

    if (u_hf_params.x > 0.001) {
        float dens = u_hf_params.x;
        float y0 = u_hf_params.y;
        float H = max(0.2, u_hf_params.z);
        float cap = u_hf_params.w;
        float y_top = y0 + H * 4.5;
        float ray_len = length(P);
        float layer_frac = (u_cam.y > y_top)
            ? clamp((y_top - W.y) / max(0.25, u_cam.y - W.y), 0.0, 1.0)
            : 1.0;
        float h_fac = exp(-max(0.0, W.y - y0) / H);
        float hf = min(cap, 1.0 - exp(-dens * ray_len * layer_frac * h_fac));
        col = mix(col, u_hf_col, hf);
    }
    f_color = vec4(col, base.a);
}
"""

_FINAL_FRAG = """#version 330
in vec2 v_uv;
uniform sampler2D u_hdr;
uniform sampler2D u_b0, u_b1, u_b2;
uniform sampler2D u_lm, u_gbloom;
uniform sampler2D u_lut;
uniform sampler2D u_aux;
uniform vec2 u_src_size, u_dst_size;
uniform float u_bloom, u_rolloff, u_distortion, u_gamma, u_vignette;
uniform int u_vig_mode, u_bloom_levels;
uniform float u_grain, u_grain_seed, u_dither_step, u_scanlines;
uniform bool u_lut_on, u_lm_on, u_alpha, u_rb;
uniform float u_char_lift;
uniform vec3 u_lift;
out vec4 f_color;

const float BAYER[16] = float[16](0., 8., 2., 10., 12., 4., 14., 6., 3., 11., 1., 9., 15., 7., 13., 5.);

float hash12(vec2 p) {
    vec3 p3 = fract(vec3(p.xyx) * 0.1031);
    p3 += dot(p3, p3.yzx + 33.33);
    return fract((p3.x + p3.y) * p3.z);
}

vec2 sharp_uv(vec2 uv) {
    if (abs(u_src_size.x - u_dst_size.x) < 0.5 && abs(u_src_size.y - u_dst_size.y) < 0.5) {
        return uv;
    }
    vec2 scale = max(vec2(1.0), u_dst_size / u_src_size);
    vec2 p = uv * u_src_size - 0.5;
    vec2 texel = floor(p);
    vec2 f = p - texel;
    vec2 ff = clamp((f - 0.5) * scale + 0.5, 0.0, 1.0);
    return (texel + 0.5 + ff) / u_src_size;
}

void main() {
    // u_rb: write top-down BGRX so the CPU can read straight into a surface
    vec2 uv = u_rb ? vec2(v_uv.x, 1.0 - v_uv.y) : v_uv;
    vec2 fc = u_rb ? vec2(gl_FragCoord.x, u_dst_size.y - gl_FragCoord.y) : gl_FragCoord.xy;
    if (abs(u_distortion) > 0.002) {
        vec2 r = uv * 2.0 - 1.0;
        float r2 = dot(r, r);
        uv = clamp((r * (1.0 + u_distortion * r2)) * 0.5 + 0.5, 0.0, 1.0);
    }
    vec2 suv = sharp_uv(uv);
    vec4 base = texture(u_hdr, suv);
    vec3 col = base.rgb;

    if (u_bloom > 0.001) {
        vec3 b = texture(u_b0, uv).rgb * 0.50;
        if (u_bloom_levels >= 2) b += texture(u_b1, uv).rgb * 0.35;
        if (u_bloom_levels >= 3) b += texture(u_b2, uv).rgb * 0.25;
        col += b * u_bloom;
    }

    if (u_rolloff > 0.5) {
        vec3 ex = max(col - 0.94, vec3(0.0));
        col = min(col, vec3(0.94)) + ex / (1.0 + ex * 1.6);
    }
    col = clamp(col, 0.0, 1.0);

    if (u_lm_on) {
        vec3 lm = clamp(texture(u_lm, uv).rgb, 0.0, 1.0);
        vec3 gb = texture(u_gbloom, uv).rgb;
        if (u_char_lift > 0.01) {
            float mat = texture(u_aux, uv).a;
            if (mat > 0.65 && mat < 0.85) {
                lm = min(vec3(1.0), lm * (1.0 + u_char_lift));
            }
        }
        col = clamp(col * lm + gb + u_lift, 0.0, 1.0);
    }

    if (abs(u_gamma - 1.0) > 0.001) {
        col = pow(col, vec3(u_gamma));
    }

    if (u_lut_on) {
        col = vec3(
            texture(u_lut, vec2((col.r * 255.0 + 0.5) / 256.0, 0.5)).r,
            texture(u_lut, vec2((col.g * 255.0 + 0.5) / 256.0, 0.5)).g,
            texture(u_lut, vec2((col.b * 255.0 + 0.5) / 256.0, 0.5)).b
        );
    }

    if (u_vignette > 0.005) {
        vec2 r = (uv - 0.5) * 2.0;
        if (u_vig_mode == 2) {
            float v = max(0.0, 1.0 - u_vignette * pow(0.55 * r.x * r.x + 0.45 * r.y * r.y, 1.2));
            col *= v;
        } else {
            float d = length(r);
            float a = clamp((d - 0.62) / 0.55, 0.0, 1.0);
            col *= (1.0 - a * a * u_vignette);
        }
    }

    if (u_grain > 0.005) {
        vec2 cell = floor(fc * 0.5);
        float rnd = hash12(cell + vec2(u_grain_seed, u_grain_seed * 0.37));
        float delta = (rnd < 0.333 ? -1.0 : (rnd > 0.666 ? 1.0 : 0.0)) * (28.0 / 255.0) * u_grain;
        col = clamp(col + delta, 0.0, 1.0);
    }

    if (u_scanlines > 0.005) {
        if ((int(fc.y) & 1) == 1) col *= (1.0 - u_scanlines);
    }

    if (u_dither_step > 0.5) {
        ivec2 p = ivec2(fc) & 3;
        float off = (BAYER[p.y * 4 + p.x] + 0.5) / 16.0 - 0.5;
        vec3 q = floor((col * 255.0 + off * u_dither_step) / u_dither_step + 0.5) * u_dither_step;
        col = clamp(q / 255.0, 0.0, 1.0);
    }

    // X byte 0 = what the old frombytes+blit left; M6 compares whole packed pixels
    f_color = u_rb ? vec4(col.bgr, 0.0) : vec4(col, u_alpha ? base.a : 1.0);
}
"""

_QUAD = np.array((-1.0, -1.0, 1.0, -1.0, -1.0, 1.0, 1.0, 1.0), dtype=np.float32)
_CORNERS = np.array(((-1.0, -1.0), (1.0, -1.0), (-1.0, 1.0),
                     (1.0, -1.0), (1.0, 1.0), (-1.0, 1.0)), dtype=np.float32)


def _raw_bgrx(s):
    """True when the surface's bytes are tight top-down BGRX (no per-pixel alpha)."""
    return (s.get_bitsize() == 32 and not s.get_flags() & pygame.SRCALPHA
            and s.get_pitch() == s.get_width() * 4
            and s.get_masks()[:3] == (0xFF0000, 0xFF00, 0xFF))


def _quality():
    try:
        from core.user_settings import SETTINGS
        return int(SETTINGS.quality_3d)
    except Exception:
        return 2


def _flash_scale():
    try:
        from core.user_settings import SETTINGS
        return 0.35 if SETTINGS.flash_reduction else 1.0
    except Exception:
        return 1.0


def _film_grain_on():
    try:
        from core.user_settings import SETTINGS
        return bool(SETTINGS.film_grain)
    except Exception:
        return True


class PostPipeline:
    """GPU HDR bloom, 2.5D lightmap, LUT grading, dither and crisp upscale."""

    def __init__(self, ctx):
        self.ctx = ctx
        self._clear_prog = ctx.program(vertex_shader=_FULL_VERT, fragment_shader=_MRT_CLEAR_FRAG)
        self._dclear_prog = ctx.program(vertex_shader=_FULL_VERT, fragment_shader=_DEPTH_CLEAR_FRAG)
        self._bg_prog = ctx.program(vertex_shader=_FULL_VERT, fragment_shader=_BG_UPLOAD_FRAG)
        self._bright_prog = ctx.program(vertex_shader=_FULL_VERT, fragment_shader=_BRIGHT_FRAG)
        self._blur_prog = ctx.program(vertex_shader=_FULL_VERT, fragment_shader=_BLUR_FRAG)
        self._lm_prog = ctx.program(vertex_shader=_LM_QUAD_VERT, fragment_shader=_LM_QUAD_FRAG)
        self._ssao_prog = ctx.program(vertex_shader=_FULL_VERT, fragment_shader=_SSAO_FRAG)
        self._ssao_blur_prog = ctx.program(vertex_shader=_FULL_VERT, fragment_shader=_SSAO_BLUR_FRAG)
        self._atmos_prog = ctx.program(vertex_shader=_FULL_VERT, fragment_shader=_ATMOS_FRAG)
        self._final_prog = ctx.program(vertex_shader=_FULL_VERT, fragment_shader=_FINAL_FRAG)

        self._quad_vbo = ctx.buffer(_QUAD.tobytes())
        self._clear_vao = ctx.vertex_array(self._clear_prog, [(self._quad_vbo, "2f", "in_pos")])
        self._dclear_vao = ctx.vertex_array(self._dclear_prog, [(self._quad_vbo, "2f", "in_pos")])
        self._bg_vao = ctx.vertex_array(self._bg_prog, [(self._quad_vbo, "2f", "in_pos")])
        self._bright_vao = ctx.vertex_array(self._bright_prog, [(self._quad_vbo, "2f", "in_pos")])
        self._blur_vao = ctx.vertex_array(self._blur_prog, [(self._quad_vbo, "2f", "in_pos")])
        self._ssao_vao = ctx.vertex_array(self._ssao_prog, [(self._quad_vbo, "2f", "in_pos")])
        self._ssao_blur_vao = ctx.vertex_array(self._ssao_blur_prog, [(self._quad_vbo, "2f", "in_pos")])
        self._atmos_vao = ctx.vertex_array(self._atmos_prog, [(self._quad_vbo, "2f", "in_pos")])
        self._final_vao = ctx.vertex_array(self._final_prog, [(self._quad_vbo, "2f", "in_pos")])
        try:
            ctx.depth_func = "1"
            self._depth_always = "1"
        except Exception:
            self._depth_always = ">="
        ctx.depth_func = "<"

        self._lm_vbo = ctx.buffer(reserve=1 << 16, dynamic=True)
        self._lm_vao = ctx.vertex_array(
            self._lm_prog, [(self._lm_vbo, "2f 4f 4f 4f", "in_corner", "in_rect", "in_col", "in_cone")]
        )

        self._bloom_size = None
        self._bloom_lvls = []
        self._present_size = None
        self._present_tex = None
        self._present_fbo = None
        self._lm_size = None
        self._lm_tex = self._lm_fbo = None
        self._gb_tex = self._gb_fbo = None
        self._bg_size = None
        self._bg_tex = None
        self._luts = OrderedDict()
        self._dummy_tex = ctx.texture((1, 1), 4, b"\x00\x00\x00\xff")
        self._white_tex = ctx.texture((1, 1), 4, b"\xff\xff\xff\xff")
        self._atmos_sig = None
        self._ssao_tex = self._ssao_fbo = None
        self._ssao_blur_tex = self._ssao_blur_fbo = None
        self._atmos_tex = self._atmos_fbo = None
        self._aux_tex = None

    def clear_mrt(self, mrt_fbo, col4):
        import moderngl
        ctx = self.ctx
        mrt_fbo.use()
        ctx.color_mask = (True, True, True, True)
        ctx.disable(moderngl.DEPTH_TEST | moderngl.BLEND | moderngl.CULL_FACE)
        self._clear_prog["u_color"].value = tuple(float(x) for x in col4)
        self._clear_vao.render(moderngl.TRIANGLE_STRIP)
        self.clear_depth(mrt_fbo)

    def clear_depth(self, fbo):
        import moderngl
        ctx = self.ctx
        fbo.use()
        ctx.color_mask = (False, False, False, False)
        ctx.depth_mask = True
        ctx.enable(moderngl.DEPTH_TEST)
        ctx.depth_func = self._depth_always
        ctx.disable(moderngl.BLEND | moderngl.CULL_FACE)
        self._dclear_vao.render(moderngl.TRIANGLE_STRIP)
        ctx.color_mask = (True, True, True, True)
        ctx.depth_func = "<"

    def upload_bg(self, mrt_fbo, surface):
        import moderngl
        ctx = self.ctx
        w, h = surface.get_size()
        if self._bg_size != (w, h):
            if self._bg_tex is not None:
                self._bg_tex.release()
            self._bg_tex = ctx.texture((w, h), 4)
            self._bg_tex.filter = (moderngl.NEAREST, moderngl.NEAREST)
            self._bg_size = (w, h)
        raw = _raw_bgrx(surface)
        if raw:
            self._bg_tex.write(surface.get_view("1"))
        else:
            self._bg_tex.write(pygame.image.tobytes(surface, "RGBA", True))
        mrt_fbo.use()
        ctx.color_mask = (True, True, True, True)
        self._bg_tex.use(location=1)
        self._bg_prog["u_bg"].value = 1
        self._bg_prog["u_raw"].value = raw
        ctx.disable(moderngl.DEPTH_TEST | moderngl.BLEND | moderngl.CULL_FACE)
        self._bg_vao.render(moderngl.TRIANGLE_STRIP)
        self.clear_depth(mrt_fbo)

    def _ensure_bloom(self, w, h):
        if self._bloom_size == (w, h) and self._bloom_lvls:
            return
        import moderngl
        self._drop_bloom()
        ctx = self.ctx
        lvls = []
        lw, lh = max(8, w // 2), max(8, h // 2)
        for _ in range(3):
            ta = ctx.texture((lw, lh), 4, dtype="f2")
            tb = ctx.texture((lw, lh), 4, dtype="f2")
            for t in (ta, tb):
                t.filter = (moderngl.LINEAR, moderngl.LINEAR)
                t.repeat_x = t.repeat_y = False
            fa = ctx.framebuffer(color_attachments=[ta])
            fb = ctx.framebuffer(color_attachments=[tb])
            lvls.append((lw, lh, ta, fa, tb, fb))
            lw, lh = max(4, lw // 2), max(4, lh // 2)
        self._bloom_lvls = lvls
        self._bloom_size = (w, h)

    def _drop_bloom(self):
        for _lw, _lh, ta, fa, tb, fb in self._bloom_lvls:
            for o in (fa, fb, ta, tb):
                try:
                    o.release()
                except Exception:
                    pass
        self._bloom_lvls = []
        self._bloom_size = None

    def _drop_atmos(self):
        for o in (self._ssao_fbo, self._ssao_tex, self._ssao_blur_fbo,
                  self._ssao_blur_tex, self._atmos_fbo, self._atmos_tex):
            if o is not None:
                try:
                    o.release()
                except Exception:
                    pass
        self._ssao_tex = self._ssao_fbo = None
        self._ssao_blur_tex = self._ssao_blur_fbo = None
        self._atmos_tex = self._atmos_fbo = None
        self._atmos_sig = None

    def _ensure_atmos(self, w, h, depth_tex):
        sig = (w, h, id(depth_tex))
        if self._atmos_sig == sig and self._atmos_fbo is not None:
            return
        import moderngl
        self._drop_atmos()
        ctx = self.ctx
        hw, hh = max(8, w // 2), max(8, h // 2)
        self._ssao_tex = ctx.texture((hw, hh), 4)
        self._ssao_blur_tex = ctx.texture((hw, hh), 4)
        for t in (self._ssao_tex, self._ssao_blur_tex):
            t.filter = (moderngl.LINEAR, moderngl.LINEAR)
            t.repeat_x = t.repeat_y = False
        self._ssao_fbo = ctx.framebuffer(color_attachments=[self._ssao_tex])
        self._ssao_blur_fbo = ctx.framebuffer(color_attachments=[self._ssao_blur_tex])
        self._atmos_tex = ctx.texture((w, h), 4, dtype="f2")
        self._atmos_tex.filter = (moderngl.LINEAR, moderngl.LINEAR)
        self._atmos_tex.repeat_x = self._atmos_tex.repeat_y = False
        self._atmos_fbo = ctx.framebuffer(color_attachments=[self._atmos_tex],
                                          depth_attachment=depth_tex)
        self._atmos_sig = sig

    def apply_atmos(self, r, n_pl=0):
        """Run half-res SSAO + wet reflections + height fog into ``_atmos_fbo``.
        Returns True when ``_atmos_tex`` / ``_atmos_fbo`` is populated."""
        q = _quality()
        if q <= 0:
            return False
        ssao_on = bool(getattr(r, "ssao", True))
        wet = float(getattr(r, "wetness", 0.0))
        marble = float(getattr(r, "marble_refl", 0.0))
        hf = getattr(r, "height_fog", None)
        if not ssao_on and wet <= 0.01 and marble <= 0.01 and not hf:
            return False
        import moderngl
        ctx = self.ctx
        self._ensure_atmos(r.w, r.h, r._depth)
        ctx.color_mask = (True, True, True, True)
        ctx.disable(moderngl.DEPTH_TEST | moderngl.BLEND | moderngl.CULL_FACE)

        if ssao_on:
            self._ssao_fbo.use()
            r._pdepth.use(location=0)
            r._aux.use(location=1)
            sp = self._ssao_prog
            sp["u_pdepth"].value = 0
            sp["u_aux"].value = 1
            sp["u_focal"].value = float(r.focal)
            sp["u_hw"].value = float(r.w * 0.5)
            sp["u_hh"].value = float(r.h * 0.5)
            sp["u_taps"].value = 12 if q >= 2 else 6
            self._ssao_vao.render(moderngl.TRIANGLE_STRIP)

            self._ssao_blur_fbo.use()
            self._ssao_tex.use(location=0)
            r._pdepth.use(location=1)
            r._aux.use(location=2)
            bp = self._ssao_blur_prog
            bp["u_ssao"].value = 0
            bp["u_pdepth"].value = 1
            bp["u_aux"].value = 2
            bp["u_texel"].value = (1.0 / max(1, r.w // 2), 1.0 / max(1, r.h // 2))
            self._ssao_blur_vao.render(moderngl.TRIANGLE_STRIP)
            self._ssao_blur_tex.use(location=3)
        else:
            self._white_tex.use(location=3)

        self._atmos_fbo.use()
        r._color.use(location=0)
        r._aux.use(location=1)
        r._pdepth.use(location=2)
        r._pl_tex.use(location=4)
        ap = self._atmos_prog
        ap["u_hdr"].value = 0
        ap["u_aux"].value = 1
        ap["u_pdepth"].value = 2
        ap["u_ssao"].value = 3
        ap["u_pl_tex"].value = 4
        ap["u_cam"].value = tuple(r.cam)
        ap["u_right"].value = tuple(r.right)
        ap["u_up"].value = tuple(r.up)
        ap["u_fwd"].value = tuple(r.fwd)
        ap["u_focal"].value = float(r.focal)
        ap["u_hw"].value = float(r.w * 0.5)
        ap["u_hh"].value = float(r.h * 0.5)
        ap["u_ssao_str"].value = 0.52 if ssao_on else 0.0
        ap["u_wet"].value = wet
        ap["u_marble"].value = marble
        try:
            from engine.core import now_s
            ap["u_time"].value = float(now_s())
        except Exception:
            ap["u_time"].value = 0.0
        ap["u_ssr_steps"].value = 12 if q >= 2 else 0
        ap["u_pl_n"].value = int(n_pl)
        fog = getattr(r, "fog", (18, 22, 34))
        ap["u_sky_col"].value = (fog[0] / 255.0, fog[1] / 255.0, fog[2] / 255.0)
        if hf:
            dens, base_y, falloff, hcol = hf
            ap["u_hf_params"].value = (float(dens), float(base_y), float(falloff), 0.72)
            ap["u_hf_col"].value = (hcol[0] / 255.0, hcol[1] / 255.0, hcol[2] / 255.0)
        else:
            ap["u_hf_params"].value = (0.0, 0.0, 1.0, 0.0)
            ap["u_hf_col"].value = (0.0, 0.0, 0.0)
        self._atmos_vao.render(moderngl.TRIANGLE_STRIP)
        return True

    def _ensure_present(self, w, h):
        if self._present_size == (w, h) and self._present_fbo is not None:
            return
        import moderngl
        for o in (self._present_fbo, self._present_tex):
            if o is not None:
                try:
                    o.release()
                except Exception:
                    pass
        self._present_tex = self.ctx.texture((w, h), 4)
        self._present_tex.filter = (moderngl.LINEAR, moderngl.LINEAR)
        self._present_fbo = self.ctx.framebuffer(color_attachments=[self._present_tex])
        self._present_size = (w, h)

    def _ensure_lm(self, w, h):
        hw, hh = max(16, w // 2), max(16, h // 2)
        if self._lm_size == (hw, hh) and self._lm_fbo is not None:
            return
        import moderngl
        for o in (self._lm_fbo, self._lm_tex, self._gb_fbo, self._gb_tex):
            if o is not None:
                try:
                    o.release()
                except Exception:
                    pass
        self._lm_tex = self.ctx.texture((hw, hh), 4)
        self._gb_tex = self.ctx.texture((hw, hh), 4, dtype="f2")
        for t in (self._lm_tex, self._gb_tex):
            t.filter = (moderngl.LINEAR, moderngl.LINEAR)
            t.repeat_x = t.repeat_y = False
        self._lm_fbo = self.ctx.framebuffer(color_attachments=[self._lm_tex])
        self._gb_fbo = self.ctx.framebuffer(color_attachments=[self._gb_tex])
        self._lm_size = (hw, hh)

    def _lut_tex(self, lut_arr):
        raw = np.ascontiguousarray(lut_arr, dtype=np.uint8)
        key = (raw.shape, hash(raw.tobytes()))
        tex = self._luts.get(key)
        if tex is not None:
            self._luts.move_to_end(key)
            return tex
        import moderngl
        # Expected shape (3, 256) -> transpose to (256, 3) RGB row
        rgb = np.ascontiguousarray(raw.T)
        tex = self.ctx.texture((256, 1), 3, rgb.tobytes())
        tex.filter = (moderngl.LINEAR, moderngl.LINEAR)
        tex.repeat_x = tex.repeat_y = False
        if len(self._luts) >= 32:
            _k, old = self._luts.popitem(last=False)
            try:
                old.release()
            except Exception:
                pass
        self._luts[key] = tex
        return tex

    def _run_bloom(self, hdr_tex, w, h, knee, levels):
        import moderngl
        ctx = self.ctx
        self._ensure_bloom(w, h)
        ctx.disable(moderngl.DEPTH_TEST | moderngl.BLEND | moderngl.CULL_FACE)
        lw, lh, ta0, fa0, tb0, fb0 = self._bloom_lvls[0]
        fa0.use()
        hdr_tex.use(location=0)
        self._bright_prog["u_src"].value = 0
        self._bright_prog["u_knee"].value = float(knee)
        self._bright_prog["u_cap"].value = 3.0 * _flash_scale()
        self._bright_vao.render(moderngl.TRIANGLE_STRIP)

        src_tex = ta0
        for i in range(levels):
            lw, lh, ta, fa, tb, fb = self._bloom_lvls[i]
            fb.use()
            # The horizontal blur must sample the PREVIOUS level's result, not
            # this level's ta (which is the vertical-blur write target and is
            # still uninitialised on the first frame). For i == 0 the two are
            # the same texture; for i >= 1 reading ta leaks whatever GPU memory
            # the texture was allocated over into the bloom -> pink frames.
            src_tex.use(location=0)
            self._blur_prog["u_src"].value = 0
            self._blur_prog["u_step"].value = (1.0 / lw, 0.0)
            self._blur_vao.render(moderngl.TRIANGLE_STRIP)
            fa.use()
            tb.use(location=0)
            self._blur_prog["u_step"].value = (0.0, 1.0 / lh)
            self._blur_vao.render(moderngl.TRIANGLE_STRIP)
            src_tex = ta

    def _render_grade3d(self, v, lights, ambient, dst_size):
        import moderngl
        from missions.m1.grade3d import lift_of
        ctx = self.ctx
        dw, dh = dst_size
        self._ensure_lm(dw, dh)
        lm_rows, gb_rows = [], []

        def add_quad(rows, cx, cy, qw, qh, col, k, kind, cone=(0.0, 0.0, 0.0, 0.0)):
            if qw < 4.0 or qh < 4.0:
                return
            if cx + qw * 0.5 < 0 or cx - qw * 0.5 > dw or cy + qh * 0.5 < 0 or cy - qh * 0.5 > dh:
                return
            rows.append((
                cx / dw, 1.0 - cy / dh, (qw * 0.5) / dw, (qh * 0.5) / dh,
                col[0] * k / 255.0, col[1] * k / 255.0, col[2] * k / 255.0, float(kind),
                cone[0], cone[1], cone[2], cone[3],
            ))

        for item in lights:
            kind = item[0]
            if kind == "cone":
                _, pos, ang, col, reach_m, k = item
                x, _y, z = pos
                c = v.screen((x, 0.0, z))
                tip = v.screen((x + math.cos(ang) * reach_m, 0.0, z - math.sin(ang) * reach_m))
                if c is None or tip is None:
                    continue
                sr = math.hypot(tip[0] - c[0], tip[1] - c[1])
                if sr > 10.0:
                    sa = math.atan2(tip[1] - c[1], tip[0] - c[0])
                    add_quad(lm_rows, c[0], c[1], sr * 2.1, sr * 2.1, col, k, 3,
                             cone=(math.cos(sa), -math.sin(sa), sr, 12.0))
                continue
            _, pos, col, rad, k = item
            x, y, z = pos
            if kind == "pool":
                c = v.screen((x, 0.0, z))
                ex = v.screen((x + rad, 0.0, z))
                n, s = v.screen((x, 0.0, z + rad)), v.screen((x, 0.0, z - rad))
                if c is None or ex is None or n is None or s is None:
                    continue
                w = min(abs(ex[0] - c[0]) * 2.0, dw * 2.0)
                h = min(abs(s[1] - n[1]), dh * 2.0)
                add_quad(lm_rows, c[0], (n[1] + s[1]) * 0.5, w, h, col, k, 0)
                continue
            if kind == "fire":
                c = v.screen(pos)
                ex = v.screen((x + rad, y, z))
                if c is None or ex is None:
                    continue
                r_px = abs(ex[0] - c[0])
                add_quad(lm_rows, c[0], c[1], min(r_px * 3.0, dw * 2.0), min(r_px * 2.6, dh * 2.0),
                         col, k * 0.72, 0)
                hk = min(1.35, max(0.90, k * 1.15))
                add_quad(lm_rows, c[0], c[1], min(r_px * 1.15, dw * 2.0), min(r_px * 1.15, dh * 2.0),
                         (255, 250, 232), hk, 0)
                add_quad(gb_rows, c[0], c[1], min(r_px * 1.55, dw * 2.0), min(r_px * 1.45, dh * 2.0),
                         col, k * 0.36, 1)
                add_quad(gb_rows, c[0], c[1], min(r_px * 0.65, dw * 2.0), min(r_px * 0.65, dh * 2.0),
                         (255, 210, 118), k * 0.20, 1)
                continue
            c = v.screen(pos)
            ex = v.screen((x + rad, y, z))
            if c is None or ex is None:
                continue
            r_px = abs(ex[0] - c[0])
            if kind == "glow":
                add_quad(lm_rows, c[0], c[1], min(r_px * 2.0, dw * 2.0), min(r_px * 2.0, dh * 2.0),
                         col, k, 0)
                add_quad(gb_rows, c[0], c[1], min(r_px * 1.15, dw * 2.0), min(r_px * 1.15, dh * 2.0),
                         col, k * 0.46, 1)
            elif kind == "reflect":
                g = v.screen((x, 0.0, z))
                if g is not None:
                    add_quad(gb_rows, g[0], g[1] + r_px * 1.4,
                             min(r_px * 0.78, dw * 2.0), min(r_px * 3.4, dh * 2.0), col, k, 2)

        def draw_batch(fbo, clear_rgb, rows):
            fbo.use()
            fbo.clear(clear_rgb[0], clear_rgb[1], clear_rgb[2], 1.0)
            if not rows:
                return
            n = len(rows)
            arr = np.empty((n * 6, 14), dtype=np.float32)
            arr[:, 0:2] = np.tile(_CORNERS, (n, 1))
            for i, row in enumerate(rows):
                arr[i * 6:(i + 1) * 6, 2:14] = row
            if arr.nbytes > self._lm_vbo.size:
                self._lm_vao.release()
                self._lm_vbo.release()
                self._lm_vbo = ctx.buffer(reserve=max(arr.nbytes, self._lm_vbo.size * 2), dynamic=True)
                self._lm_vao = ctx.vertex_array(
                    self._lm_prog, [(self._lm_vbo, "2f 4f 4f 4f", "in_corner", "in_rect", "in_col", "in_cone")]
                )
            self._lm_vbo.write(arr)
            ctx.disable(moderngl.DEPTH_TEST | moderngl.CULL_FACE)
            ctx.enable(moderngl.BLEND)
            ctx.blend_func = (moderngl.ONE, moderngl.ONE)
            self._lm_vao.render(moderngl.TRIANGLES, vertices=n * 6)

        draw_batch(self._lm_fbo, (ambient[0] / 255.0, ambient[1] / 255.0, ambient[2] / 255.0), lm_rows)
        draw_batch(self._gb_fbo, (0.0, 0.0, 0.0), gb_rows)
        ctx.disable(moderngl.BLEND)
        lift = lift_of(ambient)
        return (lift[0] / 255.0, lift[1] / 255.0, lift[2] / 255.0)

    def _draw_final(self, fbo, post, read_size, alpha=False, rb=False):
        """Run the final grade/dither shader into ``fbo`` without reading back."""
        import moderngl
        ctx = self.ctx
        post = post or {}
        dw, dh = read_size
        q = _quality()

        bloom_str = float(post.get("bloom", 0.0)) if q > 0 else 0.0
        if bloom_str > 0.0 and _flash_scale() < 0.9:
            bloom_str = min(bloom_str, 0.35)
        bloom_lvls = 3 if q >= 2 else (2 if q == 1 else 0)
        if bloom_str > 0.005 and bloom_lvls > 0:
            self._run_bloom(self._color_tex, read_size[0], read_size[1],
                            post.get("bloom_knee", 1.0), bloom_lvls)
        else:
            bloom_lvls = 0

        lm_on = False
        lift = (0.0, 0.0, 0.0)
        g3d = post.get("grade3d")
        if g3d is not None:
            v, lights, ambient = g3d
            lift = self._render_grade3d(v, lights, ambient, (dw, dh))
            lm_on = True

        lut_arr = post.get("lut")
        lut_on = lut_arr is not None

        fbo.use()
        ctx.color_mask = (True, True, True, True)
        ctx.disable(moderngl.DEPTH_TEST | moderngl.BLEND | moderngl.CULL_FACE)
        tex = self._color_tex
        tex.filter = (moderngl.LINEAR, moderngl.LINEAR)
        tex.repeat_x = tex.repeat_y = False
        tex.use(location=0)
        fp = self._final_prog
        fp["u_hdr"].value = 0

        if bloom_str > 0.005 and bloom_lvls > 0:
            self._bloom_lvls[0][2].use(location=1)
            self._bloom_lvls[1][2].use(location=2)
            self._bloom_lvls[2][2].use(location=3)
        else:
            self._dummy_tex.use(location=1)
            self._dummy_tex.use(location=2)
            self._dummy_tex.use(location=3)
        fp["u_b0"].value = 1
        fp["u_b1"].value = 2
        fp["u_b2"].value = 3

        if lm_on:
            self._lm_tex.use(location=4)
            self._gb_tex.use(location=5)
        else:
            self._dummy_tex.use(location=4)
            self._dummy_tex.use(location=5)
        fp["u_lm"].value = 4
        fp["u_gbloom"].value = 5

        if lut_on:
            self._lut_tex(lut_arr).use(location=6)
        else:
            self._dummy_tex.use(location=6)
        fp["u_lut"].value = 6

        if getattr(self, "_aux_tex", None) is not None:
            self._aux_tex.use(location=7)
        else:
            self._dummy_tex.use(location=7)
        fp["u_aux"].value = 7
        fp["u_char_lift"].value = float(post.get("char_lift", 0.0))

        sw, sh = self._src_size
        fp["u_src_size"].value = (float(sw), float(sh))
        fp["u_dst_size"].value = (float(dw), float(dh))
        fp["u_bloom"].value = bloom_str if bloom_lvls > 0 else 0.0
        fp["u_bloom_levels"].value = bloom_lvls
        fp["u_rolloff"].value = 1.0 if (self._hdr or post.get("hdr_rolloff") or bloom_str > 0.005) else 0.0
        fp["u_distortion"].value = float(post.get("distortion", 0.0)) if q >= 2 else 0.0
        fp["u_gamma"].value = float(post.get("gamma", 1.0))
        fp["u_vignette"].value = float(post.get("vignette", 0.0))
        fp["u_vig_mode"].value = int(post.get("vig_mode", 1))
        grain = float(post.get("grain", 0.0))
        if grain > 0.0 and not _film_grain_on():
            grain = 0.0
        fp["u_grain"].value = grain
        fp["u_grain_seed"].value = float(int(post.get("grain_seed", 0)) & 0xFFFF)
        fp["u_dither_step"].value = float(post.get("dither_step", 0.0))
        fp["u_scanlines"].value = float(post.get("scanlines", 0.0))
        fp["u_lut_on"].value = lut_on
        fp["u_lm_on"].value = lm_on
        fp["u_lift"].value = lift
        fp["u_alpha"].value = alpha
        fp["u_rb"].value = rb
        self._final_vao.render(moderngl.TRIANGLE_STRIP)

    def bind_source(self, color_tex, src_size, hdr, aux_tex=None):
        """Bind the renderer's HDR colour attachment for this resolve."""
        self._color_tex = color_tex
        self._src_size = tuple(src_size)
        self._hdr = bool(hdr)
        self._aux_tex = aux_tex

    def render_to(self, r, target_surface, post=None, read_size=None):
        """Run HDR bloom, grade, lightmap, dither, and crisp upscale -> target_surface."""
        import moderngl
        ctx = self.ctx
        post = post or {}
        dw, dh = read_size or target_surface.get_size()
        alpha = bool(target_surface.get_flags() & pygame.SRCALPHA)
        src_tex = getattr(r, "_active_color_tex", None) or r._color
        self.bind_source(src_tex, (r.w, r.h), getattr(r, "hdr", False), getattr(r, "_aux", None))
        self._ensure_present(dw, dh)
        if not alpha and (dw, dh) == target_surface.get_size() and _raw_bgrx(target_surface):
            self._draw_final(self._present_fbo, post, (dw, dh), False, rb=True)
            self._present_fbo.read_into(target_surface.get_view("1"), components=4, alignment=1)
            return
        self._draw_final(self._present_fbo, post, (dw, dh), alpha)
        px = self._present_fbo.read(components=4, alignment=1)
        if alpha:
            img = pygame.image.frombytes(px, (dw, dh), "RGBA", True)
            target_surface.fill((0, 0, 0, 0))
            target_surface.blit(img, (0, 0), special_flags=pygame.BLEND_RGBA_ADD)
        else:
            target_surface.blit(pygame.image.frombytes(px, (dw, dh), "RGBX", True), (0, 0))

    def render_alpha_to_fbo(self, fbo, post, read_size, alpha=True):
        """Draw the final pass with real alpha into ``fbo`` (no readback)."""
        self._draw_final(fbo, post, tuple(read_size), alpha)

    def release(self):
        self._drop_bloom()
        self._drop_atmos()
        for o in (self._present_fbo, self._present_tex, self._lm_fbo, self._lm_tex,
                  self._gb_fbo, self._gb_tex, self._bg_tex, self._dummy_tex,
                  self._white_tex, self._ssao_vao, self._ssao_blur_vao, self._atmos_vao,
                  self._clear_vao, self._dclear_vao, self._bg_vao, self._bright_vao,
                  self._blur_vao, self._final_vao, self._lm_vao, self._quad_vbo, self._lm_vbo):
            if o is not None:
                try:
                    o.release()
                except Exception:
                    pass
        for tex in self._luts.values():
            try:
                tex.release()
            except Exception:
                pass
        self._luts.clear()