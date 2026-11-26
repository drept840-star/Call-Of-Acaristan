"""Native-resolution (1920x804) minimal tactical HUD & anti-aliased PSO-1 optic.

Rendered in ``render.py`` AFTER the 2x upscale so crosshair lines, hitmarkers,
ammo/heat readouts, and the circular PSO-1 sniper scope bezel are razor-sharp.
"""
from __future__ import annotations

import math

import numpy as np
import pygame

import common as C

BONE = (234, 229, 218)
ASH = (156, 152, 144)
AMBER = (242, 142, 48)
CRIMSON = (212, 52, 42)
TEAL = (118, 214, 172)
PANEL_BG = (10, 12, 16, 178)
PANEL_BD = (196, 188, 172, 110)

_SCOPE_CACHE: dict[tuple[int, int], tuple[pygame.Surface, pygame.Surface, pygame.Surface]] = {}


def _clamp(v: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return lo if v < lo else hi if v > hi else v


def _draw_tactical_panel(cv: pygame.Surface, rect: pygame.Rect, accent=AMBER) -> None:
    box_s = pygame.Surface(rect.size, pygame.SRCALPHA)
    box_s.fill(PANEL_BG)
    pygame.draw.rect(box_s, PANEL_BD, box_s.get_rect(), 1)
    # Subtle top catchlight
    pygame.draw.line(box_s, (230, 224, 210, 62), (2, 1), (rect.w - 3, 1), 1)
    # KRAPNET corner brackets
    L = 12
    c = (*accent, 235)
    w, h = rect.w - 1, rect.h - 1
    for (x0, y0, dx, dy) in ((0, 0, 1, 1), (w, 0, -1, 1), (0, h, 1, -1), (w, h, -1, -1)):
        pygame.draw.line(box_s, c, (x0, y0), (x0 + dx * L, y0), 2)
        pygame.draw.line(box_s, c, (x0, y0), (x0, y0 + dy * L), 2)
    cv.blit(box_s, rect.topleft)


def _draw_crosshair(cv: pygame.Surface, cx: int, cy: int, *, spread: float = 14.0,
                    hit_k: float = 0.0, ring: bool = False, alpha: int = 235) -> None:
    if alpha <= 8:
        return
    s = pygame.Surface((160, 160), pygame.SRCALPHA)
    hc = 80
    col = (242, 238, 226, alpha)
    shd = (8, 10, 14, min(220, alpha))
    g = int(max(6.0, min(46.0, spread)))
    if ring:
        pygame.draw.circle(s, shd, (hc, hc), g + 1, 3)
        pygame.draw.circle(s, col, (hc, hc), g, 2)
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            pygame.draw.line(s, col, (hc + dx * (g - 4), hc + dy * (g - 4)),
                             (hc + dx * (g + 6), hc + dy * (g + 6)), 2)
    else:
        ln = 12
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            p0 = (hc + dx * g, hc + dy * g)
            p1 = (hc + dx * (g + ln), hc + dy * (g + ln))
            pygame.draw.line(s, shd, p0, p1, 4)
            pygame.draw.line(s, col, p0, p1, 2)
    pygame.draw.rect(s, (248, 198, 96, alpha), (hc - 1, hc - 1, 3, 3))
    if hit_k > 0.02:
        ha = int(255 * _clamp(hit_k))
        hc_col = (255, 108, 62, ha)
        r0, r1 = 6, 17
        for sx in (-1, 1):
            for sy in (-1, 1):
                pygame.draw.line(s, (10, 10, 12, ha), (hc + sx * r0, hc + sy * r0),
                                 (hc + sx * r1, hc + sy * r1), 4)
                pygame.draw.line(s, hc_col, (hc + sx * r0, hc + sy * r0),
                                 (hc + sx * r1, hc + sy * r1), 2)
    cv.blit(s, (cx - hc, cy - hc))


def draw_tactical_hud(cv: pygame.Surface, bar_y: int, pw: int, ph: int, *,
                      weapon: str, caliber: str, ammo: int, mag: int, reserve: int,
                      hp: int = 86, obj: str = "", recoil: float = 0.0,
                      hit_k: float = 0.0, shotgun: bool = False,
                      dmg_side: float = 0.0, cx_off: int = 0, cy_off: int = 0) -> None:
    """Minimal authentic third-person / turret gameplay HUD."""
    cx = pw // 2 + cx_off
    cy = bar_y + ph // 2 + cy_off
    spread = (22.0 if shotgun else 12.0) + recoil * (18.0 if shotgun else 14.0)
    _draw_crosshair(cv, cx, cy, spread=spread, hit_k=hit_k, ring=shotgun)

    # Subtle directional incoming-fire arc on hit
    if dmg_side > 0.02:
        arc_s = pygame.Surface((260, 260), pygame.SRCALPHA)
        a = int(175 * _clamp(dmg_side))
        pygame.draw.arc(arc_s, (232, 48, 38, a), (14, 14, 232, 232), -0.55, 0.55, 5)
        cv.blit(arc_s, (cx - 130, cy - 130))

    # Top-left compact objective banner
    if obj:
        f_lbl = C.font("mono", 15)
        f_obj = C.font("oswald", 24)
        t_lbl = f_lbl.render("OBJECTIVE", True, AMBER)
        t_obj = f_obj.render(obj, True, BONE)
        w = max(t_lbl.get_width(), t_obj.get_width()) + 34
        rect = pygame.Rect(44, bar_y + 28, w, 62)
        _draw_tactical_panel(cv, rect, accent=AMBER)
        cv.blit(t_lbl, (rect.x + 16, rect.y + 8))
        cv.blit(t_obj, (rect.x + 16, rect.y + 26))

    # Bottom-left minimal HP bar
    hp_rect = pygame.Rect(44, bar_y + ph - 82, 224, 54)
    _draw_tactical_panel(cv, hp_rect, accent=BONE)
    f_m = C.font("mono", 15)
    cv.blit(f_m.render("VITALS", True, ASH), (hp_rect.x + 14, hp_rect.y + 8))
    cv.blit(f_m.render(f"{hp:02d}%", True, BONE), (hp_rect.right - 52, hp_rect.y + 8))
    bar_r = pygame.Rect(hp_rect.x + 14, hp_rect.y + 32, hp_rect.w - 28, 10)
    pygame.draw.rect(cv, (28, 32, 38), bar_r)
    fill_w = int(bar_r.w * _clamp(hp / 100.0))
    fill_c = TEAL if hp > 45 else CRIMSON
    pygame.draw.rect(cv, fill_c, (bar_r.x, bar_r.y, fill_w, bar_r.h))

    # Bottom-right minimal weapon & live ammo readout
    wpn_rect = pygame.Rect(pw - 294, bar_y + ph - 98, 250, 70)
    _draw_tactical_panel(cv, wpn_rect, accent=AMBER)
    cv.blit(C.font("oswald", 24).render(weapon, True, BONE), (wpn_rect.x + 16, wpn_rect.y + 8))
    cv.blit(C.font("mono", 14).render(caliber, True, AMBER), (wpn_rect.x + 16, wpn_rect.y + 40))
    ammo_s = C.font("oswald", 34).render(f"{ammo:02d}", True, BONE if ammo > 4 else CRIMSON)
    res_s = C.font("mono", 16).render(f"/ {reserve:03d}", True, ASH)
    cv.blit(ammo_s, (wpn_rect.right - 118, wpn_rect.y + 14))
    cv.blit(res_s, (wpn_rect.right - 70, wpn_rect.y + 30))


def draw_flight_hud(cv: pygame.Surface, bar_y: int, pw: int, ph: int, *,
                    heat: float, flares: int, heading_deg: float, ads_k: float,
                    hit_k: float = 0.0, obj: str = "INTERCEPT CONVOY",
                    lock_norm: tuple[float, float] | None = None) -> None:
    """Minimal authentic Last Flight door-gunner HUD (compass tape, heat, flares, lock)."""
    cx = pw // 2
    cy = bar_y + ph // 2
    # Fade hip crosshair smoothly out as RMB ADS centers the physical reflex optic
    ch_alpha = int(230 * _clamp(1.0 - (ads_k - 0.18) / 0.45))
    _draw_crosshair(cv, cx, cy, spread=16.0 + heat * 12.0, hit_k=hit_k, alpha=ch_alpha)
    if ch_alpha <= 8 and hit_k > 0.02:
        _draw_crosshair(cv, cx, cy, spread=12.0, hit_k=hit_k, alpha=0)

    # Top compass tape
    tape_w = 420
    tape_r = pygame.Rect(cx - tape_w // 2, bar_y + 22, tape_w, 34)
    tape_s = pygame.Surface(tape_r.size, pygame.SRCALPHA)
    tape_s.fill((10, 12, 16, 155))
    pygame.draw.line(tape_s, (*AMBER, 170), (0, tape_r.h - 1), (tape_w, tape_r.h - 1), 1)
    f_sm = C.font("mono", 13)
    for deg in range(-90, 91, 15):
        hdg = int(round((heading_deg + deg) % 360))
        x = tape_w // 2 + int(deg * 3.0)
        if 8 < x < tape_w - 8:
            major = (hdg % 45 == 0)
            pygame.draw.line(tape_s, (226, 222, 212, 200 if major else 110),
                             (x, 22 if major else 26), (x, 32), 2 if major else 1)
            if major:
                lbl = {0: "N", 45: "NE", 90: "E", 135: "SE", 180: "S",
                       225: "SW", 270: "W", 315: "NW"}.get(hdg, f"{hdg:03d}")
                ts = f_sm.render(lbl, True, AMBER if lbl in ("N", "E") else BONE)
                tape_s.blit(ts, (x - ts.get_width() // 2, 4))
    # Center lubber tick
    pygame.draw.polygon(tape_s, AMBER, [(tape_w // 2, 33), (tape_w // 2 - 5, 25), (tape_w // 2 + 5, 25)])
    cv.blit(tape_s, tape_r.topleft)

    # Target acquisition diamond (if target locked)
    if lock_norm is not None:
        lx = int(lock_norm[0] * pw)
        ly = bar_y + int(lock_norm[1] * ph)
        d = 18
        pts = [(lx, ly - d), (lx + d, ly), (lx, ly + d), (lx - d, ly)]
        pygame.draw.polygon(cv, AMBER, pts, 2)
        tag = C.font("mono", 13).render("TANKER // PRIORITY", True, AMBER)
        cv.blit(tag, (lx + 22, ly - 8))

    # Top-left objective tag
    f_lbl = C.font("mono", 14)
    f_obj = C.font("oswald", 22)
    t_lbl = f_lbl.render("DOOR GUNNER // AIRBORNE", True, AMBER)
    t_obj = f_obj.render(obj, True, BONE)
    o_rect = pygame.Rect(44, bar_y + 26, max(t_lbl.get_width(), t_obj.get_width()) + 32, 58)
    _draw_tactical_panel(cv, o_rect, accent=AMBER)
    cv.blit(t_lbl, (o_rect.x + 15, o_rect.y + 7))
    cv.blit(t_obj, (o_rect.x + 15, o_rect.y + 24))

    # Bottom-right LMG thermal gauge + countermeasure flares
    r_rect = pygame.Rect(pw - 310, bar_y + ph - 98, 266, 70)
    _draw_tactical_panel(cv, r_rect, accent=CRIMSON if heat > 0.72 else AMBER)
    cv.blit(C.font("oswald", 22).render("TACTICAL LMG", True, BONE), (r_rect.x + 15, r_rect.y + 8))
    cv.blit(C.font("mono", 14).render(f"FLARES [{flares}]", True, TEAL), (r_rect.right - 102, r_rect.y + 12))
    bar_r = pygame.Rect(r_rect.x + 15, r_rect.y + 42, r_rect.w - 30, 12)
    pygame.draw.rect(cv, (26, 28, 34), bar_r)
    hw = int(bar_r.w * _clamp(heat))
    hcol = (242, 168, 56) if heat < 0.65 else (238, 68, 42)
    pygame.draw.rect(cv, hcol, (bar_r.x, bar_r.y, hw, bar_r.h))
    cv.blit(C.font("mono", 12).render("THERMAL", True, ASH), (r_rect.x + 15, r_rect.y + 54))


def _build_scope_layers(pw: int, ph: int) -> tuple[pygame.Surface, pygame.Surface, pygame.Surface]:
    """Build cached native-resolution anti-aliased PSO-1 optical mask, bezel & reticle."""
    key = (pw, ph)
    hit = _SCOPE_CACHE.get(key)
    if hit is not None:
        return hit

    cx, cy = pw // 2, ph // 2
    rad = int(ph * 0.445)

    # 1. Smooth anti-aliased circular alpha mask (inside lens = 255, outside = 0)
    yy, xx = np.ogrid[0:ph, 0:pw]
    dist_px = np.sqrt((xx - cx) ** 2 + (yy - cy) ** 2).astype(np.float32)
    lens_alpha = np.clip((rad - dist_px) * 0.75 + 0.5, 0.0, 1.0)
    mask_surf = pygame.Surface((pw, ph), pygame.SRCALPHA)
    mask_surf.fill((0, 0, 0, 0))
    pa = pygame.surfarray.pixels_alpha(mask_surf)
    pa[:] = (lens_alpha.T * 255.0).astype(np.uint8)
    del pa

    # 2. Smooth optical housing bezel + inner ocular vignette + subtle anti-reflective coating ring
    bezel_surf = pygame.Surface((pw, ph), pygame.SRCALPHA)
    r_in = float(rad)
    r_out = float(rad + 36)
    # Dark outer tube ring (rad .. rad+36) with smooth AA edges
    outer_ring = np.clip((dist_px - (r_in - 1.5)) / 2.5, 0.0, 1.0) * np.clip(((r_out + 1.5) - dist_px) / 2.5, 0.0, 1.0)
    # Inner ocular edge falloff inside lens (0.68..1.0 * rad)
    norm_r = dist_px / r_in
    inner_vig = np.clip((norm_r - 0.66) / 0.34, 0.0, 1.0) ** 2.2 * (dist_px <= r_in)
    # Subtle metallic chamfer glint at rad+3..rad+7
    chamfer = np.exp(-((dist_px - (r_in + 4.5)) / 2.2) ** 2) * 0.42
    # Subtle coated-glass cyan/green rim glint at rad-3..rad
    coating = np.exp(-((dist_px - (r_in - 3.5)) / 3.0) ** 2) * 0.16 * (dist_px <= r_in)

    total_a = np.clip(np.maximum(outer_ring * 0.99, inner_vig * 0.84) + chamfer * 0.5 + coating, 0.0, 1.0)
    rgb = np.zeros((ph, pw, 3), dtype=np.float32)
    # Tube metal colour + chamfer highlight + glass tint
    rgb[..., 0] = 10.0 * outer_ring + 58.0 * chamfer + 36.0 * coating
    rgb[..., 1] = 12.0 * outer_ring + 64.0 * chamfer + 78.0 * coating
    rgb[..., 2] = 15.0 * outer_ring + 76.0 * chamfer + 92.0 * coating

    b3 = pygame.surfarray.pixels3d(bezel_surf)
    b3[:] = np.clip(rgb.transpose(1, 0, 2), 0, 255).astype(np.uint8)
    del b3
    ba = pygame.surfarray.pixels_alpha(bezel_surf)
    ba[:] = (total_a.T * 255.0).astype(np.uint8)
    del ba

    # Elevation & windage turret silhouettes (anti-aliased at native 1920x804)
    pygame.draw.rect(bezel_surf, (10, 12, 15, 252), (cx - 34, cy - rad - 68, 68, 38), border_radius=8)
    pygame.draw.rect(bezel_surf, (38, 44, 54, 210), (cx - 34, cy - rad - 68, 68, 38), 2, border_radius=8)
    pygame.draw.rect(bezel_surf, (10, 12, 15, 252), (cx + rad + 28, cy - 34, 38, 68), border_radius=8)
    pygame.draw.rect(bezel_surf, (38, 44, 54, 210), (cx + rad + 28, cy - 34, 38, 68), 2, border_radius=8)

    # 3. Crisp illuminated PSO-1 etched reticle (visible pale-amber etch + dark core + glowing chevron)
    ret_surf = pygame.Surface((pw, ph), pygame.SRCALPHA)
    etch_glow = (212, 124, 58, 120)
    etch_line = (224, 156, 86, 205)
    post_dark = (14, 16, 20, 240)
    chev_glow = (255, 86, 48, 150)
    chev_core = (255, 194, 118, 255)

    thick = int(rad * 0.44)
    gap = 20

    # Outer heavy stadia posts (dark metal with subtle amber outline for dark snow readability)
    for (p0, p1) in (
        ((cx - rad, cy), (cx - thick, cy)),
        ((cx + thick, cy), (cx + rad, cy)),
        ((cx, cy + int(rad * 0.40)), (cx, cy + rad)),
    ):
        pygame.draw.line(ret_surf, etch_glow, p0, p1, 6)
        pygame.draw.line(ret_surf, post_dark, p0, p1, 4)

    # Fine illuminated crosshair hairs
    for (p0, p1) in (
        ((cx - thick, cy), (cx - gap, cy)),
        ((cx + gap, cy), (cx + thick, cy)),
        ((cx, cy - rad), (cx, cy - gap)),
        ((cx, cy + gap + 2), (cx, cy + int(rad * 0.40))),
    ):
        pygame.draw.line(ret_surf, etch_glow, p0, p1, 3)
        pygame.draw.line(ret_surf, etch_line, p0, p1, 1)

    # Windage mil ticks
    for i in range(1, 7):
        step = int(rad * 0.068 * i)
        tick = 11 if i % 2 == 0 else 6
        for sx in (-1, 1):
            pygame.draw.line(ret_surf, etch_glow, (cx + sx * step, cy - tick), (cx + sx * step, cy + tick), 3)
            pygame.draw.line(ret_surf, etch_line, (cx + sx * step, cy - tick), (cx + sx * step, cy + tick), 1)

    # Drop chevrons
    for ci, dy in enumerate((34, 68, 106)):
        w = 10 - ci * 2
        pts = [(cx - w, cy + dy + w), (cx, cy + dy), (cx + w, cy + dy + w)]
        pygame.draw.lines(ret_surf, etch_glow, False, pts, 3)
        pygame.draw.lines(ret_surf, etch_line, False, pts, 1)

    # Stadiametric 1.7m rangefinder curve (bottom-left quadrant)
    rf_x0, rf_y0 = cx - int(rad * 0.46), cy + int(rad * 0.36)
    pygame.draw.line(ret_surf, etch_line, (rf_x0, rf_y0), (rf_x0 + 116, rf_y0), 2)
    pts_rf = [(rf_x0 + int(k * 18), rf_y0 - int(58.0 / (1.0 + k * 0.42))) for k in range(7)]
    pygame.draw.lines(ret_surf, etch_glow, False, pts_rf, 4)
    pygame.draw.lines(ret_surf, etch_line, False, pts_rf, 2)

    # Primary illuminated PSO-1 center chevron
    ch = 13
    c_pts = [(cx - ch, cy + ch), (cx, cy), (cx + ch, cy + ch)]
    pygame.draw.lines(ret_surf, chev_glow, False, c_pts, 6)
    pygame.draw.lines(ret_surf, chev_core, False, c_pts, 2)
    pygame.draw.circle(ret_surf, (255, 244, 212, 255), (cx, cy), 2)

    # Subtle optics telemetry readout inside bottom edge of bezel
    lbl = C.font("mono", 15).render("PSO-1 // 4.0X  ZERO 200M", True, (220, 152, 86))
    lbl.set_alpha(155)
    ret_surf.blit(lbl, (cx - lbl.get_width() // 2, cy + rad - 44))

    _SCOPE_CACHE[key] = (mask_surf, bezel_surf, ret_surf)
    return _SCOPE_CACHE[key]


def composite_pso1_scope(cv: pygame.Surface, periph_full: pygame.Surface,
                         scope_full: pygame.Surface, bar_y: int, pw: int, ph: int, *,
                         recoil_y: int = 0, flash_k: float = 0.0) -> None:
    """Composite blurred 1x periphery + crisp zoomed optic at native 1920x804."""
    mask_surf, bezel_surf, ret_surf = _build_scope_layers(pw, ph)
    band = pygame.Surface((pw, ph))
    band.blit(periph_full, (0, 0))

    # Mask zoomed scope cleanly with AA circular alpha
    lens = scope_full.convert_alpha()
    pa = pygame.surfarray.pixels_alpha(lens)
    ma = pygame.surfarray.array_alpha(mask_surf)
    pa[:] = ma
    del pa
    band.blit(lens, (0, recoil_y))
    band.blit(bezel_surf, (0, recoil_y))
    band.blit(ret_surf, (0, recoil_y))

    # Brief hot muzzle bloom on the trigger-pull frame right before cut to pure black
    if flash_k > 0.01:
        fl = pygame.Surface((pw, ph))
        v = int(215 * _clamp(flash_k))
        fl.fill((v, int(v * 0.88), int(v * 0.68)))
        band.blit(fl, (0, 0), special_flags=pygame.BLEND_RGB_ADD)

    cv.blit(band, (0, bar_y))
