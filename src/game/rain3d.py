"""World-space 2.5D rain for top-down 3D views (Walk, M1, M4, M5).

Replaces flat 2D screen-space streaks in 2.5D with a world-locked 3D drop
lattice around the camera's ground focus:
  * three depth/weight bands with perspective foreshortening and tapered tips
  * illumination from nearby lamps, fires, headlights and flashlight/searchlight cones
  * synchronized ground impact ripples, splash crowns and double-ring puddle hits
  * sightline + roof-plane occlusion so interiors stay dry and walls clip drops
  * batched GPU line-quads on GLRenderer; clean RGB add_line3d fallback on software
"""
import math

from core.config import TILE_SIZE
from game.topdown3d import K

FX_LAYER = 6
RAIN_LAYER = 5
GROUND_LAYER = 1

_CELL_M = 2.0
_FALL_H = 10.5
_SPLASH_DUR = 0.30
_HEX = tuple((math.cos(i * math.tau / 6.0), math.sin(i * math.tau / 6.0)) for i in range(6))


def _quality():
    try:
        from game.render3d_bridge import quality_3d
        return int(quality_3d())
    except Exception:
        return 2


def _reduced_motion():
    try:
        from core.state import STATE
        return bool(getattr(STATE, "reduced_motion", False))
    except Exception:
        return False


def step_rain_drops(drops, speed_mul=1.0, rng=None):
    """Advance legacy 2D ``rain_drops`` without drawing, keeping RNG/replay parity."""
    if not drops:
        return
    from core.config import SCENE_BOT, SCENE_TOP, WIDTH
    from engine.core import LEGACY_RNG
    rng = rng or LEGACY_RNG
    for i, (x, y, spd) in enumerate(drops):
        ey = y + int(spd * speed_mul)
        drops[i] = (x - 1, ey, spd)
        if ey > SCENE_BOT:
            drops[i] = (rng.randint(0, WIDTH), SCENE_TOP - rng.randint(0, 40), spd)


def _mist_sprite(col, radius_m, intensity):
    """Subtle GPU-batched damp mist glow beneath outdoor streetlamps."""
    def draw(s, sx, sy, scale, z):
        pass

    draw._gl_spec = {
        "kind": "halo",
        "col": (min(255, int(col[0])), min(255, int(col[1])), min(255, int(col[2]))),
        "radius_m": float(radius_m),
        "max_px": 140.0,
        "power": 2.6,
        "peak": float(intensity),
        "hdr": 1.0,
    }
    draw.bounds_m = (radius_m, radius_m)
    draw.bounds_cap_px = (140, 140)
    return draw


def _pack_lights(lights, fx, fz):
    """Pre-pack nearby point/spot light dicts into tight tuples for the drop loop."""
    packed = []
    max_d2 = 30.0 * 30.0
    for lt in lights or ():
        pos = lt.get("pos")
        if pos is None:
            continue
        lx, ly, lz = pos
        dx, dz = lx - fx, lz - fz
        if dx * dx + dz * dz > max_d2:
            continue
        rng = float(lt.get("range", 4.5))
        if rng <= 0.2:
            continue
        col = lt.get("color", (200, 210, 230))
        inten = float(lt.get("intensity", 1.0))
        # Skip the tiny shoulder-rim fill over Biribel so rain doesn't halo on him.
        if rng < 2.6 and col[0] < 180 and col[2] > 230 and lt.get("kind") != "spot":
            continue
        inv_r2 = 1.0 / (rng * rng)
        if lt.get("kind") == "spot" and "dir" in lt:
            d = lt["dir"]
            dn = math.sqrt(d[0] * d[0] + d[1] * d[1] + d[2] * d[2]) or 1.0
            packed.append((
                True, lx, ly, lz,
                float(col[0]), float(col[1]), float(col[2]),
                inv_r2, min(1.8, inten * 0.95),
                d[0] / dn, d[1] / dn, d[2] / dn, float(lt.get("cone", 0.85)),
            ))
        else:
            packed.append((
                False, lx, ly, lz,
                float(col[0]), float(col[1]), float(col[2]),
                inv_r2, min(1.6, inten * 0.85),
            ))
    return tuple(packed)


def _lit_at(x, y, z, packed):
    """Evaluate accumulated light colour and brightness boost (0..1) at (x, y, z)."""
    if not packed:
        return 108.0, 128.0, 162.0, 0.0
    ar = ag = ab = boost = 0.0
    for lt in packed:
        dx, dy, dz = x - lt[1], y - lt[2], z - lt[3]
        d2 = dx * dx + dy * dy + dz * dz
        w = 1.0 - d2 * lt[7]
        if w <= 0.0:
            continue
        if lt[0]:
            dist = math.sqrt(d2) or 1.0
            dp = (dx * lt[9] + dy * lt[10] + dz * lt[11]) / dist
            cone = lt[12]
            if dp <= cone:
                continue
            w *= min(1.0, (dp - cone) / max(0.05, 1.0 - cone))
        k = w * w * lt[8]
        ar += lt[4] * k
        ag += lt[5] * k
        ab += lt[6] * k
        boost += k
    if boost <= 0.01:
        return 108.0, 128.0, 162.0, 0.0
    b = min(1.0, boost)
    inv = 1.0 / max(1e-4, boost)
    lr = ar * inv
    lg = ag * inv
    lb = ab * inv
    # Mix base cool rain slate toward the local practical light colour.
    mix_k = min(0.88, b * 0.85)
    return (
        108.0 + (lr - 108.0) * mix_k,
        128.0 + (lg - 128.0) * mix_k,
        162.0 + (lb - 162.0) * mix_k,
        b,
    )


def emit(r, v, tm, lights=(), outdoor_sky=None, outdoor_ground=None,
         roof_occlude=None, puddle_fn=None, mist_lamps=(),
         intensity=1.0, seed=0):
    """Queue 3D world-space rain streaks, ground ripples, splashes and lamp mist."""
    q = _quality()
    if q <= 0 or intensity <= 0.0:
        return
    rm = _reduced_motion()
    t_s = tm * 0.001

    fx, fz = v.tgt[0], v.tgt[2]
    cam = r.cam
    cx, cy, cz = cam[0], cam[1], cam[2]
    rt, up, fw = r.right, r.up, r.fwd
    hw, hh = r.w * 0.5, r.h * 0.5
    foc = r.focal
    near = getattr(r, "NEAR", 0.06)
    max_x, max_y = r.w + 32.0, r.h + 32.0

    def proj(px, py, pz):
        dx, dy, dz = px - cx, py - cy, pz - cz
        pcz = dx * fw[0] + dy * fw[1] + dz * fw[2]
        if pcz <= near:
            return None
        inv = foc / pcz
        return (
            hw + (dx * rt[0] + dy * rt[1] + dz * rt[2]) * inv,
            hh - (dx * up[0] + dy * up[1] + dz * up[2]) * inv,
        )

    # Subtle wind gusting (locked calm under reduced_motion).
    if rm:
        wx, wz = -0.28, -0.09
    else:
        wx = -0.32 + 0.07 * math.sin(t_s * 0.55) + 0.03 * math.sin(t_s * 1.37)
        wz = -0.10 + 0.025 * math.cos(t_s * 0.43)

    packed_lights = _pack_lights(lights, fx, fz)
    use_gl = hasattr(r, "add_lines3d")
    rain_segs = []
    ground_segs = []

    gx0 = math.floor((fx - 15.0) / _CELL_M)
    gx1 = math.floor((fx + 15.0) / _CELL_M)
    gz0 = math.floor((fz - 10.0) / _CELL_M)
    gz1 = math.floor((fz + 15.0) / _CELL_M)
    density = (1.0 if q >= 2 else 0.58) * min(1.3, intensity)

    for gz in range(gz0, gz1 + 1):
        for gx in range(gx0, gx1 + 1):
            h0 = ((gx * 73856093) ^ (gz * 19349663) ^ (seed * 83492791)) & 0xFFFFFFFF
            # Tier-0 far mist drop + Tier-1/2 primary drop per cell.
            n_drops = 2 if (q >= 2 and (h0 & 3) != 0) else 1
            if q == 1 and (h0 & 7) < 3:
                continue
            for k in range(n_drops):
                if k == 1 and density < 0.75 and (h0 & 1):
                    continue
                h = ((h0 + k * 2654435761) * 1597334677) & 0xFFFFFFFF
                u = (h & 0xFFFF) / 65536.0
                vv = ((h >> 16) & 0xFFFF) / 65536.0
                ix = (gx + u) * _CELL_M
                iz = (gz + vv) * _CELL_M

                if k == 1:
                    tier = 0
                    spd = 10.8 + ((h >> 8) & 15) * 0.14
                elif (h & 7) == 0:
                    tier = 2
                    spd = 15.6 + ((h >> 8) & 15) * 0.22
                else:
                    tier = 1
                    spd = 13.2 + ((h >> 8) & 15) * 0.18

                sp_h = spd * _SPLASH_DUR
                cyc = _FALL_H + sp_h
                off = ((h >> 12) & 0xFFF) / 4096.0
                phase = (t_s * spd + off * cyc) % cyc

                if phase < _FALL_H:
                    y = _FALL_H - phase
                    x = ix - wx * y
                    z = iz - wz * y

                    # Sightline indoor exclusion: never draw drops over interior floors.
                    if outdoor_sky is not None and y < cy - 1.5:
                        tg = cy / (cy - y)
                        if not outdoor_sky(cx + (x - cx) * tg, cz + (z - cz) * tg):
                            continue
                    # Roof-plane occlusion behind uncut ~3 m buildings.
                    if roof_occlude is not None and y < 2.8 and cy > 3.5:
                        tr = (cy - 3.0) / (cy - y)
                        if roof_occlude(cx + (x - cx) * tr, cz + (z - cz) * tr):
                            continue

                    ln = min((0.40 if tier == 0 else 0.62 if tier == 1 else 0.86), y + 0.08)
                    if ln <= 0.06:
                        continue
                    tx, ty, tz = x - wx * ln, y + ln, z - wz * ln
                    cr, cg, cb, lb = _lit_at(x, y, z, packed_lights)

                    if use_gl:
                        # add_lines3d takes WORLD-space endpoints; proj() is only
                        # used here for the off-screen / near-plane cull.
                        head_w, tail_w = (x, y, z), (tx, ty, tz)
                        p_head = proj(*head_w)
                        p_tail = proj(*tail_w)
                        if p_head is None or p_tail is None:
                            continue
                        hx, hy = p_head
                        tx2, ty2 = p_tail
                        if (hx < -32.0 and tx2 < -32.0) or (hx > max_x and tx2 > max_x):
                            continue
                        if (hy < -32.0 and ty2 < -32.0) or (hy > max_y and ty2 > max_y):
                            continue
                        base_a = 44 if tier == 0 else (78 if tier == 1 else 108)
                        alpha = min(205, int(base_a + lb * 96.0))
                        ir, ig, ib = min(255, int(cr)), min(255, int(cg)), min(255, int(cb))
                        if tier == 0:
                            rain_segs.append((tail_w, head_w, (ir, ig, ib, alpha), 0.9))
                        else:
                            # Taper split is interpolated in world space; the
                            # renderer projects each sub-segment itself.
                            mid_w = (tail_w[0] + (head_w[0] - tail_w[0]) * 0.45,
                                     tail_w[1] + (head_w[1] - tail_w[1]) * 0.45,
                                     tail_w[2] + (head_w[2] - tail_w[2]) * 0.45)
                            w_head = 1.15 if tier == 1 else 1.45
                            rain_segs.append((tail_w, mid_w, (ir, ig, ib, int(alpha * 0.40)), 0.85))
                            rain_segs.append((mid_w, head_w, (ir, ig, ib, alpha), w_head))
                            if lb > 0.35:
                                glint_w = (tail_w[0] + (head_w[0] - tail_w[0]) * 0.78,
                                           tail_w[1] + (head_w[1] - tail_w[1]) * 0.78,
                                           tail_w[2] + (head_w[2] - tail_w[2]) * 0.78)
                                gr = min(255, int(ir * 1.15 + 24))
                                gg = min(255, int(ig * 1.15 + 24))
                                gb = min(255, int(ib * 1.15 + 24))
                                rain_segs.append((glint_w, head_w, (gr, gg, gb, min(225, alpha + 30)), w_head + 0.15))
                    else:
                        k_sw = 0.28 + lb * 0.55 if tier > 0 else 0.18 + lb * 0.35
                        col_sw = (
                            max(0, min(255, int(36 + (cr - 36) * k_sw))),
                            max(0, min(255, int(44 + (cg - 44) * k_sw))),
                            max(0, min(255, int(58 + (cb - 58) * k_sw))),
                        )
                        r.add_line3d((tx, ty, tz), (x, y, z), col_sw, 1, layer=RAIN_LAYER)
                elif tier >= 1:
                    if outdoor_ground is not None and not outdoor_ground(ix, iz):
                        continue
                    su = (phase - _FALL_H) / sp_h
                    in_pud = bool(puddle_fn(ix, iz)) if puddle_fn is not None else False
                    cr, cg, cb, lb = _lit_at(ix, 0.08, iz, packed_lights)
                    eu = 1.0 - (1.0 - su) * (1.0 - su)
                    rad = 0.045 + (0.28 if in_pud else 0.18) * eu
                    ra = int((122 if in_pud else 68) * ((1.0 - su) ** 1.45) * (0.72 + 0.55 * lb))
                    if ra > 8:
                        rr, rg, rb = min(255, int(cr * 1.05 + 18)), min(255, int(cg * 1.05 + 18)), min(255, int(cb * 1.05 + 22))
                        if use_gl:
                            pts = []
                            ok = True
                            for hx_u, hz_u in _HEX:
                                wp = (ix + hx_u * rad, 0.025, iz + hz_u * rad * 0.86)
                                if proj(*wp) is None:
                                    ok = False
                                    break
                                pts.append(wp)
                            if ok:
                                rcol = (rr, rg, rb, ra)
                                for i in range(6):
                                    ground_segs.append((pts[i], pts[(i + 1) % 6], rcol, 1.05 if in_pud else 0.9))
                                if in_pud and su > 0.25:
                                    su2 = (su - 0.25) / 0.75
                                    rad2 = 0.03 + 0.16 * (1.0 - (1.0 - su2) ** 2)
                                    ra2 = int(88 * ((1.0 - su2) ** 1.5) * (0.72 + 0.55 * lb))
                                    if ra2 > 8:
                                        pts2 = [(ix + hx_u * rad2, 0.025, iz + hz_u * rad2 * 0.86) for hx_u, hz_u in _HEX]
                                        if all(proj(*p) is not None for p in pts2):
                                            rcol2 = (rr, rg, rb, ra2)
                                            for i in range(6):
                                                ground_segs.append((pts2[i], pts2[(i + 1) % 6], rcol2, 0.9))
                                # Subtle specular shimmer tick on puddle hits near light.
                                if in_pud and lb > 0.15 and su < 0.5:
                                    w0, w1 = (ix - 0.11, 0.028, iz), (ix + 0.11, 0.028, iz)
                                    if proj(*w0) is not None and proj(*w1) is not None:
                                        ground_segs.append((w0, w1, (min(255, rr + 24), min(255, rg + 24), min(255, rb + 24), min(160, ra + 24)), 1.1))
                        else:
                            k_r = (0.35 if in_pud else 0.22) * (1.0 - su)
                            rcol_sw = (
                                max(0, min(255, int(34 + (rr - 34) * k_r))),
                                max(0, min(255, int(40 + (rg - 40) * k_r))),
                                max(0, min(255, int(52 + (rb - 52) * k_r))),
                            )
                            for i in range(6):
                                x0, z0 = _HEX[i]
                                x1, z1 = _HEX[(i + 1) % 6]
                                r.add_line3d((ix + x0 * rad, 0.025, iz + z0 * rad * 0.86),
                                             (ix + x1 * rad, 0.025, iz + z1 * rad * 0.86),
                                             rcol_sw, 1, layer=GROUND_LAYER)
                    # Upward micro splash crown right at impact.
                    if su < 0.28 and (in_pud or (h & 3) == 0):
                        cu = su / 0.28
                        ca = int((145 if in_pud else 105) * (1.0 - cu) * (0.7 + 0.6 * lb))
                        if ca > 10:
                            sh = 0.095 * math.sin(cu * math.pi)
                            sp_r = 0.065 * cu + 0.02
                            sr = min(255, int(cr * 1.1 + 22))
                            sg = min(255, int(cg * 1.1 + 22))
                            sb = min(255, int(cb * 1.1 + 26))
                            if use_gl:
                                base_w = (ix, 0.025, iz)
                                if proj(*base_w) is not None:
                                    scol = (sr, sg, sb, ca)
                                    for ang_i in (0.4, 2.5, 4.6):
                                        tip_w = (ix + math.cos(ang_i) * sp_r, 0.025 + sh, iz + math.sin(ang_i) * sp_r)
                                        if proj(*tip_w) is not None:
                                            ground_segs.append((base_w, tip_w, scol, 1.0))

    if use_gl:
        if ground_segs:
            r.add_lines3d(ground_segs, layer=GROUND_LAYER, depth_test=True)
        if rain_segs:
            r.add_lines3d(rain_segs, layer=RAIN_LAYER, depth_test=True)

    # Subtle humid rain-spray halo beneath the nearest outdoor streetlamps (GL High quality).
    if use_gl and q >= 2 and mist_lamps:
        shown = 0
        for head, col in mist_lamps:
            dx, dz = head[0] - fx, head[2] - fz
            if dx * dx + dz * dz > 19.0 * 19.0:
                continue
            r.add_sprite((head[0], max(0.8, head[1] - 1.15), head[2]),
                         _mist_sprite(col, 2.2, 0.068), layer=FX_LAYER)
            shown += 1
            if shown >= 5:
                break
