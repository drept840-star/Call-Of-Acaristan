"""Split from cutscenes.py - see cutscenes.py (shim) for the map."""
# cutscenes package
# ------------------------------------------------------------

"""Cutscene visuals and dialogue: character drawings, scene backgrounds, shot lists."""
import math
import random
import pygame
from core.config import (HEIGHT, LETTER_H, WIDTH, draw_scanlines, draw_vignette, font_terminal_small)

from cutscenes.cast import draw_biribel, draw_volkov
from cutscenes.figure_kit import draw_character as _fk_draw
from cutscenes.m3cell import CB_BG, CB_SKIN, CB_SKIN_SHADE, CB_SPLINTER, CB_SPLINTER_HI, CB_METAL, CB_METAL_DARK, CB_METAL_EDGE
from core.hands import grip_hand as _core_grip_hand


def _pt(cx, cy, dx, dy, angle, scale):
    dx *= scale
    dy *= scale
    cos_a = math.cos(angle)
    sin_a = math.sin(angle)
    return (int(cx + dx * cos_a - dy * sin_a),
            int(cy + dx * sin_a + dy * cos_a))

# Per-shot frame durations.
# Desperate → Triumphant arc. Total ~11.6 s at 60 fps.
#   Shot 1 (Strain):  exhausted, trembling, near defeat       - 4.0 s
#   Shot 2 (Crack):   cathartic release                       - 2.2 s
#   Shot 3 (Grab):    determined recognition                  - 2.4 s
#   Shot 4 (Ready):   cold resolve                            - 3.0 s
CB_SHOT1_DUR = 240
CB_SHOT2_DUR = 132
CB_SHOT3_DUR = 144
CB_SHOT4_DUR = 180
# Global cutscene clock phase boundaries (contiguous timeline).
CB_SHOT1 = 0
CB_SHOT2 = CB_SHOT1 + CB_SHOT1_DUR
CB_SHOT3 = CB_SHOT2 + CB_SHOT2_DUR
CB_SHOT4 = CB_SHOT3 + CB_SHOT3_DUR
CB_END   = CB_SHOT4 + CB_SHOT4_DUR

# ── Cinematic continuity constants (kept for the future rewrite) ────
# Keep the chair anchored on-screen across all 4 shots so the framing
# feels stable (the camera "doesn't move" mid-break, the chair does).
# Floor line sits at 78% of the screen height; the chair seat sits one
# leg-length above that. The broken leg lands at a fixed floor offset
# from the chair, and shots 3 & 4 read that same position so the leg
# the player sees being grabbed is the same leg they saw flying off.
CB_FLOOR_FRAC          = 0.78
CB_CHAIR_SCALE         = 1.05
# Where the broken-off front-right leg comes to rest on the floor,
# measured as a pixel offset from the chair's centre column.
CB_BROKEN_LEG_DX       = -110   # to the player's left, away from the chair
CB_BROKEN_LEG_DY_BELOW = 28     # below the floor line (lying flat)
CB_BROKEN_LEG_LEN      = 150
CB_BROKEN_LEG_W        = 14
CB_BROKEN_LEG_ANGLE    = -12    # degrees, slight tilt as it landed


def _cb_frame(surface, t, t_max):
    """Base background fill + ease-in/out. Returns the eased opacity (0..1).

    The actual cell is composited separately by _cb_composite_cell (so
    every shot is recognizably the SAME cell); this just primes the
    surface and gives the caller a fade factor.
    """
    surface.fill(CB_BG)
    edge = 12
    if t < edge:
        op = t / edge
    elif t > t_max - edge:
        op = max(0.0, (t_max - t) / edge)
    else:
        op = 1.0
    return op


def _cb_composite_cell(surface, cell_surf, cx, cy, zoom=1.0, pan=(0, 0)):
    """Blit the pre-rendered live cell (`cell_surf`, a WIDTHÃ-HEIGHT frame
    of the real tilemap cell + _draw_cell_room) onto `surface`, zoomed
    around the screen-space chair center (cx, cy) and optionally panned.

    This is what makes every shot the SAME cell at a different focal
    length - the camera "travels" (tight → wider → floor → standing)
    instead of jumping between unrelated invented rooms. `cell_surf` is a
    static buffer rendered once per frame by the mission3 dispatcher, so
    the smoothscale here is one transform per frame on a static surface
    (acceptable; not in a hot inner loop over entities).
    """
    if cell_surf is None:
        return
    zx, zy = pan
    if zoom == 1.0 and pan == (0, 0):
        surface.blit(cell_surf, (0, 0))
        return
    # Scale the cell buffer by `zoom`, then blit so (cx,cy) stays anchored
    # at the same screen point (a "zoom into the chair" effect).
    w0, h0 = cell_surf.get_size()
    sw, sh = max(1, int(w0 * zoom)), max(1, int(h0 * zoom))
    scaled = pygame.transform.smoothscale(cell_surf, (sw, sh))
    # Position so that the chair point (cx, cy) in the original maps to
    # (cx + zx, cy + zy) on screen after scaling.
    dest_x = int(cx + zx - cx * zoom)
    dest_y = int(cy + zy - cy * zoom)
    surface.blit(scaled, (dest_x, dest_y))


def _cb_tube_flicker(surface, cx, cy, t, base_alpha=70):
    """Chair-break fluorescent flash removed.

    This used to draw the bright overhead glow/flash that washed out the
    chair-leg cutscene. Keep this as a no-op so existing shot code can still
    call it without reintroducing the white screen.
    """
    return

def _draw_bloom_circle(surface, color, center, radius, alpha=40, steps=8):
    """Draw a soft light bloom using layered surfaces."""
    r, g, b = color[:3]
    for i in range(steps):
        ratio = 1.0 - (i / steps)
        current_rad = int(radius * (i / steps + 1.0))
        current_alpha = int(alpha * (ratio ** 2))
        if current_alpha <= 0: continue
        s = pygame.Surface((current_rad * 2, current_rad * 2), pygame.SRCALPHA)
        pygame.draw.circle(s, (r, g, b, current_alpha), (current_rad, current_rad), current_rad)
        surface.blit(s, (center[0] - current_rad, center[1] - current_rad), special_flags=pygame.BLEND_RGB_ADD)

def _cb_get_camera_drift(t):
    """Simulate handheld camera movement."""
    dx = math.sin(t * 0.031) * 2.2 + math.sin(t * 0.013) * 1.5
    dy = math.cos(t * 0.027) * 1.8 + math.sin(t * 0.009) * 1.2
    return dx, dy

_mote_data = None
def _draw_dust_motes(surface, t):
    """Draw floating dust particles that catch the light."""
    global _mote_data
    if _mote_data is None:
        rng = random.Random(42)
        _mote_data = []
        for _ in range(30):
            _mote_data.append({
                "x": rng.randint(0, WIDTH), "y": rng.randint(0, HEIGHT),
                "speed": rng.uniform(0.2, 0.6), "size": rng.randint(1, 3),
                "phase": rng.uniform(0, math.pi * 2)
            })
    
    for m in _mote_data:
        mx = (m["x"] + t * m["speed"] * 0.2) % WIDTH
        my = (m["y"] + math.sin(t * 0.01 + m["phase"]) * 15) % HEIGHT
        # Motes only visible near the center of the frame (motivated lighting)
        dist_to_center = math.hypot(mx - WIDTH // 2, my - HEIGHT // 2)
        alpha = int(max(0, 40 * (1 - dist_to_center / 500)))
        if alpha > 0:
            pygame.draw.circle(surface, (200, 210, 220, alpha), (int(mx), int(my)), m["size"])

def _cb_vignette(surface, strength=110):
    """Mild periphery-darkening applied AFTER the subject so the lit
    center stays bright. Kept light - heavy vignette crushed earlier revs.
    """
    draw_vignette(surface, strength=strength)


# ── Pre-rendered film grain texture (deterministic, reused every frame) ──
# A subtle noise overlay that says "this is filmed, not live gameplay."
# Generated once at module load; _cb_cinematic_grade blits it with a low
# alpha every frame. The grain is what separates the cutscene look from
# the clean digital gameplay view.
_cb_grain_surf = None
def _cb_get_grain():
    global _cb_grain_surf
    if _cb_grain_surf is not None:
        return _cb_grain_surf
    import random as _r
    _cb_grain_surf = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
    rng = _r.Random(88)
    for _ in range(800):
        gx = rng.randint(0, WIDTH - 1)
        gy = rng.randint(0, HEIGHT - 1)
        a = rng.randint(8, 25)
        c = rng.choice([(a, a, a, a), (0, 0, 0, a)])
        _cb_grain_surf.set_at((gx, gy), c)
    return _cb_grain_surf


def _cb_cinematic_grade(surface, t=0):
    """Enhanced film-grade post-processing, with exposure kept under control."""
    # 1. Atmospheric Dust
    _draw_dust_motes(surface, t)

    # 2. Exposure safety: chair-break shots are dark scenes. If any lighting
    # pass gets too hot, pull it back before UI/dialogue is drawn.
    exposure = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
    exposure.fill((0, 0, 0, 92))
    surface.blit(exposure, (0, 0))

    # 3. Cool Film Tint
    tint = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
    tint.fill((15, 25, 45, 10))
    surface.blit(tint, (0, 0))

    # 4. Film Grain
    grain = _cb_get_grain()
    ox, oy = int(t * 0.9) % 8, int(t * 1.3) % 8
    surface.blit(grain, (ox, oy))
    surface.blit(grain, (ox - 4, oy - 3))

    # 5. Vignette
    draw_vignette(surface, strength=185)


def _cb_cinematic_bg(surface, cx, cy, shot_id, t=0, op=1.0):
    """Draw a bespoke cinematic background for each chair-break shot.

    Replaces _cb_composite_cell (which blitted the REAL game cell tilemap).
    Each shot now gets its own hand-drawn dark background that looks NOTHING
    like the game - a dark void with motivated lighting, not a tilemap room.

    This is what makes the cutscene a STANDALONE cinematic, not a gameplay
    overlay: the background is custom-drawn for the cutscene, not a
    screenshot of the game.

    shot_id:
      "strain" - tight close-up: dark void + single light cone on chair area
      "crack"  - medium shot: dark floor + chair stump at center
      "grab"   - floor close-up: dark surface + leg lying on it
      "ready"  - medium-full: dark void + standing silhouette backdrop
    """
    # Base: pure dark void (NOT the game's dark grey tile floor).
    # Slightly cooler than CB_BG to match the cinematic grade.
    surface.fill((6, 8, 12))

    if shot_id == "strain":
        # Dark concrete floor + faint wall behind the chair.
        # Must be VISIBLE - not pure black. The floor/wall give spatial
        # context: "this chair is in a room."
        # Floor: dark grey concrete, bright enough to see
        floor_col = (45, 48, 52)
        for y in range(HEIGHT):
            p = y / HEIGHT
            mid_dist = abs(p - 0.45) * 2
            v = int(floor_col[0] * (1.0 - mid_dist * 0.25))
            pygame.draw.line(surface, (v, v + 2, v + 4), (0, y), (WIDTH, y))
        # Wall strip behind the backrest (lighter than floor - reads as wall)
        wall_y = 0
        wall_h = int(HEIGHT * 0.35)
        wall_col = (38, 40, 46)
        pygame.draw.rect(surface, wall_col, (0, wall_y, WIDTH, wall_h))
        # Wall-floor seam line
        pygame.draw.line(surface, (55, 58, 62), (0, wall_h), (WIDTH, wall_h), 1)
        # Floor texture: deterministic concrete noise (visible specks)
        rng = random.Random(77)
        for _ in range(200):
            nx = rng.randint(0, WIDTH - 1)
            ny = rng.randint(wall_h, HEIGHT - 1)
            shade = rng.randint(35, 55)
            pygame.draw.circle(surface, (shade, shade + 1, shade + 2), (nx, ny), 1)
        # Wall texture: fewer, darker specks
        for _ in range(80):
            nx = rng.randint(0, WIDTH - 1)
            ny = rng.randint(0, wall_h - 1)
            shade = rng.randint(28, 42)
            pygame.draw.circle(surface, (shade, shade + 1, shade + 2), (nx, ny), 1)

    elif shot_id == "crack":
        # Dark floor (a subtle gradient, NOT tilemap tiles) with the chair
        # at center. The floor is just a dark surface - no grid, no drain,
        # no baseboards. The only detail is a subtle radial darkening from
        # the chair outward (like the floor is stained/scorched).
        # Floor gradient: slightly lighter near center, darker at edges.
        floor = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        for y in range(HEIGHT):
            p = y / HEIGHT
            # Subtle vertical gradient (darker at top/bottom, lighter mid)
            mid_dist = abs(p - 0.5) * 2
            v = int(14 * (1.0 - mid_dist * 0.6))
            pygame.draw.line(floor, (v, v + 2, v + 4, 255), (0, y), (WIDTH, y))
        surface.blit(floor, (0, 0))
        # Radial darkening around the chair (scorched floor from the impact)
        scorch = pygame.Surface((300, 300), pygame.SRCALPHA)
        for i in range(10):
            r = 140 - i * 12
            a = int(40 * (1 - i / 10))
            if a > 0 and r > 0:
                pygame.draw.circle(scorch, (8, 6, 4, a),
                                   (150, 150), r)
        surface.blit(scorch, (int(cx) - 150, int(cy) - 150))

    elif shot_id == "grab":
        # Floor close-up: a dark textured surface (NOT tiles). The camera
        # is looking down at the floor where the leg fell. Draw it as a
        # dark concrete surface with subtle noise, not a tilemap grid.
        floor = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        for y in range(HEIGHT):
            p = y / HEIGHT
            v = int(10 + p * 8)  # slightly lighter toward bottom (foreground)
            pygame.draw.line(floor, (v, v + 1, v + 3, 255), (0, y), (WIDTH, y))
        surface.blit(floor, (0, 0))
        # Subtle concrete texture (deterministic noise dots)
        rng = random.Random(42)
        for _ in range(120):
            nx = rng.randint(0, WIDTH - 1)
            ny = rng.randint(0, HEIGHT - 1)
            shade = rng.randint(8, 20)
            pygame.draw.circle(surface, (shade, shade + 1, shade + 2),
                               (nx, ny), 1)

    elif shot_id == "ready":
        # Dark void with a subtle floor gradient + a bright spot behind
        # where Biribel stands (the backlight source). No room, no walls,
        # no furniture - just darkness + the silhouette.
        # Floor gradient (very dark, just enough to ground the figure)
        floor = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        for y in range(HEIGHT):
            p = y / HEIGHT
            if p > 0.5:
                v = int(8 * (p - 0.5) * 2)
                pygame.draw.line(floor, (v, v + 1, v + 2, 255),
                                 (0, y), (WIDTH, y))
        surface.blit(floor, (0, 0))
        # Backlight glow behind the figure (cool, from the tube above)
        glow_r = 180
        glow = pygame.Surface((glow_r * 2, glow_r * 2), pygame.SRCALPHA)
        for i in range(10):
            r = int(glow_r * (1.0 - i / 10))
            a = int(20 * (1.0 - i / 10) ** 2 * op)
            if a > 0 and r > 0:
                pygame.draw.circle(glow, (30, 40, 55, a),
                                   (glow_r, glow_r), r)
        surface.blit(glow, (int(cx) - glow_r, int(cy) - glow_r - 80))


def _cb_letterbox(surface):
    """Cinematic letterbox bars with a subtle gradient edge.

    Upgraded from flat black rectangles to:
      - Thicker bars (LETTER_H + 4px gradient fade into the image)
      - A thin dark-blue border line at the inner edge (the "cinema frame")
      - A 4px gradient from pure black to transparent, softening the hard
        cutoff between bar and image
    """
    # Main bars (solid black).
    pygame.draw.rect(surface, (0, 0, 0), (0, 0, WIDTH, LETTER_H))
    pygame.draw.rect(surface, (0, 0, 0), (0, HEIGHT - LETTER_H, WIDTH, LETTER_H))

    # Gradient fade: 4px transition from black to image, top and bottom.
    for i in range(4):
        a = int(180 * (1 - i / 4))
        fade = pygame.Surface((WIDTH, 1), pygame.SRCALPHA)
        fade.fill((0, 0, 0, a))
        surface.blit(fade, (0, LETTER_H + i))
        surface.blit(fade, (0, HEIGHT - LETTER_H - i - 1))

    # Thin cinema-frame border line (dark blue, 1px) at the inner edge.
    frame_col = (12, 18, 28)
    pygame.draw.line(surface, frame_col, (0, LETTER_H), (WIDTH, LETTER_H), 1)
    pygame.draw.line(surface, frame_col, (0, HEIGHT - LETTER_H - 1), (WIDTH, HEIGHT - LETTER_H - 1), 1)


# ===================================================================
# CHAIR BREAK CUTSCENE - Rewritten with proper backgrounds & chair
# ===================================================================


def _draw_cell_wall(surface, x, y, w, h, rng, is_ceiling=False):
    """Draw a cell wall with concrete texture, stains, and pipes."""
    base = (28, 30, 34) if is_ceiling else (34, 36, 40)
    pygame.draw.rect(surface, base, (x, y, w, h))
    for sx in range(x, x + w, 80):
        shade = rng.randint(0, 6)
        pygame.draw.line(surface, (base[0] - shade, base[1] - shade, base[2] - shade),
                         (sx, y), (sx, y + h), 1)
    for _ in range(150):
        nx = x + rng.randint(0, max(1, w - 1))
        ny = y + rng.randint(0, max(1, h - 1))
        shade = rng.randint(-6, 6)
        c = tuple(max(0, min(255, base[i] + shade)) for i in range(3))
        pygame.draw.circle(surface, c, (nx, ny), rng.randint(1, 2))
    if is_ceiling:
        for py_off in range(0, h, max(1, int(h * 0.3))):
            pygame.draw.line(surface, (48, 50, 55), (x, y + py_off), (x + w, y + py_off), 4)
            pygame.draw.line(surface, (38, 40, 45), (x, y + py_off + 2), (x + w, y + py_off + 2), 2)
    # Water stains dripping down
    for _ in range(4):
        stain_x = x + rng.randint(20, w - 20)
        stain_bot = y + rng.randint(h // 4, h)
        stain_w = rng.randint(8, 25)
        stain_s = pygame.Surface((stain_w, stain_bot - y), pygame.SRCALPHA)
        for sy_off in range(stain_bot - y):
            frac = sy_off / max(1, stain_bot - y)
            a = int(20 * (1 - frac) ** 1.5)
            sw = int(stain_w * (0.5 + 0.5 * (1 - frac) ** 2))
            if sw > 0 and a > 0:
                pygame.draw.rect(stain_s, (20, 25, 35, a),
                                 ((stain_w - sw) // 2, sy_off, sw, 1))
        surface.blit(stain_s, (stain_x, y))


def _draw_cell_floor(surface, x, y, w, h, rng):
    """Draw a stained concrete floor with tile seams and drain grate."""
    base = (22, 24, 28)
    pygame.draw.rect(surface, base, (x, y, w, h))
    for tx in range(x, x + w, 64):
        pygame.draw.line(surface, (16, 18, 22), (tx, y), (tx, y + h), 1)
    for ty in range(y, y + h, 64):
        pygame.draw.line(surface, (16, 18, 22), (x, ty), (x + w, ty), 1)
    for _ in range(200):
        nx = x + rng.randint(0, max(1, w - 1))
        ny = y + rng.randint(0, max(1, h - 1))
        shade = rng.randint(-4, 4)
        c = tuple(max(0, min(255, base[i] + shade)) for i in range(3))
        pygame.draw.circle(surface, c, (nx, ny), rng.randint(1, 2))
    for _ in range(6):
        sx = x + rng.randint(10, w - 20)
        sy = y + rng.randint(10, h - 20)
        sw = rng.randint(20, 60)
        sh = rng.randint(10, 30)
        stain = pygame.Surface((sw, sh), pygame.SRCALPHA)
        stain.fill((10, 12, 16, rng.randint(20, 45)))
        surface.blit(stain, (sx, sy))
    # Drain grate (bottom-center)
    grate_x = x + w // 2 - 30
    grate_y = y + h - 20
    grate_w, grate_h = 60, 16
    pygame.draw.rect(surface, (40, 42, 46), (grate_x, grate_y, grate_w, grate_h),
                     border_radius=3)
    for gx in range(grate_x + 4, grate_x + grate_w, 8):
        pygame.draw.line(surface, (14, 16, 20), (gx, grate_y), (gx, grate_y + grate_h), 2)


def _draw_interrogation_chair(surface, cx, seat_y, scale=1.0, broken_leg=False,
                               break_progress=0.0, yank=0.0, t=0):
    """Draw a heavy, bolted-down interrogation chair with realistic detail.

    Features: welded steel frame, thick vinyl seat with compression wrinkles,
    metal armrests with chain anchors, four heavy tubular legs bolted to floor
    plates, and a slatted backrest with cross-bracing.
    """
    s = scale
    rng = random.Random(77 + int(t * 3))

    steel_dark = (32, 30, 28)
    steel_mid = (52, 49, 46)
    steel_light = (78, 74, 70)
    steel_highlight = (100, 96, 90)
    vinyl_base = (48, 42, 36)
    vinyl_dark = (36, 30, 24)
    vinyl_highlight = (62, 55, 48)
    rust = (85, 50, 30)
    bolt_col = (90, 85, 78)
    bolt_hi = (120, 115, 105)
    chain_col = (68, 65, 60)
    chain_hi = (95, 90, 85)

    seat_w = int(150 * s)
    seat_h = int(18 * s)
    back_h = int(100 * s)
    back_w = int(130 * s)
    leg_len = int(145 * s)
    leg_w = int(10 * s)
    arm_w = int(60 * s)
    arm_h = int(8 * s)

    seat_x = cx - seat_w // 2
    floor_y = seat_y + leg_len + seat_h

    # Floor bolt plates
    for px_off in (10, seat_w - 26):
        px = seat_x + int(px_off * s)
        py = floor_y - int(4 * s)
        plate_r = pygame.Rect(px, py, int(16 * s), int(8 * s))
        pygame.draw.rect(surface, steel_dark, plate_r, border_radius=int(2 * s))
        pygame.draw.rect(surface, steel_mid, plate_r, 1, border_radius=int(2 * s))
        for bx_off in (3, 10):
            pygame.draw.circle(surface, bolt_col, (px + int(bx_off * s), py + int(4 * s)), int(2 * s))
            pygame.draw.circle(surface, bolt_hi, (px + int(bx_off * s) - 1, py + int(3 * s)), int(1 * s))

    # Back legs
    for lx_off in (12, seat_w - 12 - leg_w):
        lx = seat_x + int(lx_off * s)
        pygame.draw.rect(surface, steel_dark, (lx, seat_y + seat_h, leg_w, leg_len), border_radius=int(2 * s))
        pygame.draw.line(surface, steel_mid, (lx + 2, seat_y + seat_h + 2), (lx + 2, floor_y - int(6 * s)), 1)

    # Backrest
    back_x = seat_x + (seat_w - back_w) // 2
    back_top = seat_y - back_h
    for ox in (0, back_w - leg_w):
        bx = back_x + ox
        pygame.draw.rect(surface, steel_dark, (bx, back_top, leg_w, back_h), border_radius=int(2 * s))
        pygame.draw.line(surface, steel_mid, (bx + 2, back_top + 2), (bx + 2, back_top + back_h - 2), 1)
    for i in range(5):
        slat_y = back_top + int(i * (back_h / 5)) + int(3 * s)
        slat_r = pygame.Rect(back_x + leg_w, slat_y, back_w - 2 * leg_w, int(8 * s))
        pygame.draw.rect(surface, vinyl_dark, slat_r, border_radius=int(1 * s))
        pygame.draw.rect(surface, vinyl_base, (slat_r.x + 1, slat_r.y + 1,
                                                slat_r.w - 2, slat_r.h - 2), border_radius=int(1 * s))
        pygame.draw.line(surface, vinyl_highlight, (slat_r.x + 4, slat_r.centery),
                         (slat_r.right - 4, slat_r.centery), 1)
    brace_y = back_top + back_h // 2
    pygame.draw.line(surface, steel_mid, (back_x, brace_y), (back_x + back_w, brace_y), int(2 * s))

    # Front left leg
    fl_x = seat_x + int(8 * s)
    pygame.draw.rect(surface, steel_mid, (fl_x, seat_y + seat_h, leg_w, leg_len), border_radius=int(2 * s))
    pygame.draw.line(surface, steel_highlight, (fl_x + 2, seat_y + seat_h + 2),
                     (fl_x + 2, floor_y - int(6 * s)), 1)

    # Front right leg (the one that breaks)
    fr_x = seat_x + int((seat_w - 8) * s) - leg_w
    if not broken_leg:
        pygame.draw.rect(surface, steel_mid, (fr_x, seat_y + seat_h, leg_w, leg_len), border_radius=int(2 * s))
        pygame.draw.line(surface, steel_highlight, (fr_x + 2, seat_y + seat_h + 2),
                         (fr_x + 2, floor_y - int(6 * s)), 1)
    else:
        angle = break_progress * 130
        dist_x = break_progress * 80 * s
        dist_y = break_progress * 20 + (break_progress ** 2) * 120
        leg_surf = pygame.Surface((int(leg_w + 8), int(leg_len + 10)), pygame.SRCALPHA)
        pygame.draw.rect(leg_surf, steel_mid, (4, 0, leg_w, leg_len), border_radius=int(2 * s))
        pygame.draw.line(leg_surf, steel_highlight, (6, 2), (6, leg_len - 4), 1)
        jagged = [(0, 0), (int(leg_w + 8), 0), (int(leg_w + 6), int(15 * s)),
                  (int(leg_w // 2), int(10 * s)), (2, int(18 * s))]
        pygame.draw.polygon(leg_surf, steel_light, jagged)
        rot_leg = pygame.transform.rotate(leg_surf, -angle)
        surface.blit(rot_leg, (int(fr_x + dist_x - rot_leg.get_width() // 2),
                                int(seat_y + seat_h + dist_y)))

    # Seat
    seat_r = pygame.Rect(seat_x, seat_y, seat_w, seat_h)
    pygame.draw.rect(surface, steel_dark, seat_r, border_radius=int(4 * s))
    cushion_r = pygame.Rect(seat_x + int(4 * s), seat_y + int(2 * s),
                             seat_w - int(8 * s), seat_h - int(4 * s))
    pygame.draw.rect(surface, vinyl_dark, cushion_r, border_radius=int(3 * s))
    pygame.draw.rect(surface, vinyl_base, (cushion_r.x + 1, cushion_r.y + 1,
                                            cushion_r.w - 2, cushion_r.h - 2), border_radius=int(2 * s))
    comp_w = int(seat_w * 0.5)
    comp_x = cx - comp_w // 2
    pygame.draw.ellipse(surface, vinyl_dark, (comp_x, seat_y + int(3 * s), comp_w, seat_h - int(6 * s)))
    for sy_off in (int(5 * s), int(11 * s)):
        pygame.draw.line(surface, vinyl_highlight,
                         (seat_x + int(8 * s), seat_y + sy_off),
                         (seat_x + seat_w - int(8 * s), seat_y + sy_off), 1)
    pygame.draw.line(surface, steel_highlight,
                     (seat_x + int(6 * s), seat_y),
                     (seat_x + seat_w - int(6 * s), seat_y), int(2 * s))
    for _ in range(4):
        rx = seat_x + rng.randint(10, seat_w - 10)
        ry = seat_y + rng.randint(2, seat_h - 2)
        rs = rng.randint(2, int(5 * s))
        pygame.draw.circle(surface, rust, (int(rx), int(ry)), int(rs))

    # Armrests
    for side in (-1, 1):
        ax = cx + side * int((seat_w // 2 + 10) * s)
        pygame.draw.rect(surface, steel_dark,
                         (ax - int(3 * s), seat_y - int(50 * s), int(6 * s), int(55 * s)),
                         border_radius=int(2 * s))
        arm_r = pygame.Rect(ax - int(arm_w // 2), seat_y - int(50 * s), arm_w, arm_h)
        pygame.draw.rect(surface, steel_mid, arm_r, border_radius=int(3 * s))
        pygame.draw.line(surface, steel_highlight,
                         (arm_r.x + 2, arm_r.y + int(2 * s)),
                         (arm_r.right - 2, arm_r.y + int(2 * s)), 1)
        anchor_x = ax
        anchor_y = seat_y - int(40 * s)
        pygame.draw.circle(surface, chain_col, (int(anchor_x), int(anchor_y)), int(6 * s), 2)
        pygame.draw.circle(surface, chain_hi, (int(anchor_x - 1), int(anchor_y - 1)), int(2 * s))

    # Chains when yanked
    if yank > 0.1:
        chain_yank = yank * 15 * s
        for side in (-1, 1):
            anchor_x = cx + side * int((seat_w // 2 + 10) * s)
            anchor_y = seat_y - int(40 * s)
            wrist_x = anchor_x + side * int(40 * s + chain_yank)
            wrist_y = seat_y + int(30 * s) - int(chain_yank * 0.5)
            num_links = 5
            for i in range(num_links):
                p = i / num_links
                link_x = anchor_x + (wrist_x - anchor_x) * p
                link_y = anchor_y + (wrist_y - anchor_y) * p
                link_r = int(5 * s)
                pygame.draw.circle(surface, chain_col, (int(link_x), int(link_y)), link_r, 2)
                pygame.draw.circle(surface, chain_hi,
                                   (int(link_x - 1), int(link_y - 1)), int(2 * s))
            cuff_w = int(20 * s)
            cuff_h = int(14 * s)
            cuff_r = pygame.Rect(int(wrist_x - cuff_w // 2), int(wrist_y - cuff_h // 2),
                                  cuff_w, cuff_h)
            pygame.draw.rect(surface, steel_dark, cuff_r, border_radius=int(3 * s))
            pygame.draw.rect(surface, steel_mid, cuff_r, 1, border_radius=int(3 * s))
            for cx_off in (int(3 * s), cuff_w - int(5 * s)):
                pygame.draw.circle(surface, bolt_col,
                                   (int(cuff_r.x + cx_off), int(cuff_r.centery)), int(2 * s))




def _cb_clamp(v, lo=0.0, hi=1.0):
    return max(lo, min(hi, v))


def _cb_smooth(v):
    """Smoothstep easing for the chair-break shots."""
    v = _cb_clamp(v)
    return v * v * (3.0 - 2.0 * v)


def _cb_ease_out(v):
    v = _cb_clamp(v)
    return 1.0 - (1.0 - v) ** 3


def _cb_ease_out_cubic_m2(v):
    """Cubic ease-out used by the chair-break shots for snappier impact."""
    v = _cb_clamp(v)
    return 1.0 - (1.0 - v) ** 3


def _cb_time_to_frames(t_value, clock_is_ms=False):
    """Convert a chair-break shot clock to 60 FPS frame units.

    The real cutscene dispatcher passes milliseconds. The legacy Mission 3
    inspection renderer passes frame counts directly. Make the unit explicit
    instead of guessing from the magnitude - otherwise the first second of a
    real shot would be mistaken for legacy frame values.
    """
    return float(t_value) * 0.06 if clock_is_ms else float(t_value)


def _cb_camera_shake(t, amount=4.0, decay=1.0):
    """Deterministic handheld/shake offset; no random flicker between frames."""
    a = amount * decay
    return (
        math.sin(t * 0.037) * a + math.sin(t * 0.091) * a * 0.35,
        math.cos(t * 0.043) * a + math.sin(t * 0.067) * a * 0.30,
    )


def _cb_surface_alpha_blit(surface, draw_fn, alpha=255):
    """Draw translucent construction geometry onto a temporary layer."""
    layer = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
    draw_fn(layer)
    if alpha < 255:
        layer.set_alpha(max(0, min(255, int(alpha))))
    surface.blit(layer, (0, 0))


def _cb_draw_metal_leg(surface, center, length=150, width=14, angle_deg=-12,
                       alpha=255, jagged=True, glow=False):
    """Draw the broken interrogation-chair leg as a heavy steel tube.

    It is intentionally metal, not wood: the in-game chair sprite is a bolted
    dark-gunmetal interrogation chair, so the improvised weapon has to read as
    a snapped tubular chair leg.
    """
    def _draw(layer):
        cx, cy = center
        a = math.radians(angle_deg)
        ux, uy = math.cos(a), math.sin(a)
        px, py = -uy, ux
        half = length / 2.0
        hw = width / 2.0
        p1 = (cx - ux * half + px * hw, cy - uy * half + py * hw)
        p2 = (cx + ux * half + px * hw, cy + uy * half + py * hw)
        p3 = (cx + ux * half - px * hw, cy + uy * half - py * hw)
        p4 = (cx - ux * half - px * hw, cy - uy * half - py * hw)
        body = [(int(x), int(y)) for x, y in (p1, p2, p3, p4)]
        if glow:
            for g in range(9, 0, -3):
                gp1 = (cx - ux * half + px * (hw + g), cy - uy * half + py * (hw + g))
                gp2 = (cx + ux * half + px * (hw + g), cy + uy * half + py * (hw + g))
                gp3 = (cx + ux * half - px * (hw + g), cy + uy * half - py * (hw + g))
                gp4 = (cx - ux * half - px * (hw + g), cy - uy * half - py * (hw + g))
                pygame.draw.polygon(layer, (170, 190, 210, 8),
                                    [(int(x), int(y)) for x, y in (gp1, gp2, gp3, gp4)])
        pygame.draw.polygon(layer, (44, 45, 46, 255), body)
        pygame.draw.polygon(layer, (12, 13, 15, 255), body, 2)
        # Long cold highlight along one side.
        h1 = (int(cx - ux * (half - 8) + px * (hw * 0.35)),
              int(cy - uy * (half - 8) + py * (hw * 0.35)))
        h2 = (int(cx + ux * (half - 8) + px * (hw * 0.35)),
              int(cy + uy * (half - 8) + py * (hw * 0.35)))
        pygame.draw.line(layer, (96, 100, 104, 230), h1, h2, max(1, width // 4))
        # Hollow open end.
        end_c = (int(cx + ux * half), int(cy + uy * half))
        pygame.draw.circle(layer, (18, 19, 21), end_c, max(3, width // 2))
        pygame.draw.circle(layer, (82, 86, 90), end_c, max(3, width // 2), 1)
        # Jagged snapped end.
        if jagged:
            base_x = cx - ux * half
            base_y = cy - uy * half
            teeth = []
            for i, off in enumerate((-hw, -hw * 0.35, 0, hw * 0.42, hw)):
                bite = 0 if i in (0, 4) else (8 + (i % 2) * 7)
                teeth.append((int(base_x + px * off + ux * bite),
                              int(base_y + py * off + uy * bite)))
            teeth.append((int(base_x - ux * 7 + px * hw), int(base_y - uy * 7 + py * hw)))
            teeth.append((int(base_x - ux * 5 - px * hw), int(base_y - uy * 5 - py * hw)))
            pygame.draw.polygon(layer, (88, 84, 78, 255), teeth)
            pygame.draw.line(layer, (150, 145, 132, 230), teeth[1], teeth[3], 1)
    _cb_surface_alpha_blit(surface, _draw, alpha)


def _cb_draw_shiv_spark(surface, x, y, t):
    """Brief additive glint at the grip point during the grab shot.

    Drawn with pre-multiplied RGB on a black surface + BLEND_RGB_ADD so it
    reads as a real light flash rather than an opaque blob. t is 0..1.
    """
    fade = max(0.0, 1.0 - t)
    size = 24
    spark = pygame.Surface((size * 2, size * 2))
    spark.fill((0, 0, 0))
    cx = cy = size
    core_r = max(2, int(3 + 4 * fade))
    core_v = int(225 * fade)
    pygame.draw.circle(spark, (core_v, core_v, min(255, core_v + 18)), (cx, cy), core_r)
    halo_v = int(85 * fade)
    pygame.draw.circle(spark, (halo_v, halo_v, min(255, halo_v + 12)), (cx, cy), core_r + 4)
    surface.blit(spark, (int(x - size), int(y - size)),
                 special_flags=pygame.BLEND_RGB_ADD)


def _cb_draw_chain_between(surface, start, end, links=7, alpha=255, taut=1.0):
    """Draw chunky oval chain links between two points."""
    sx, sy = start
    ex, ey = end
    dx, dy = ex - sx, ey - sy
    ang = math.atan2(dy, dx)
    dist = max(1.0, math.hypot(dx, dy))
    nx, ny = -math.sin(ang), math.cos(ang)

    def _draw(layer):
        for i in range(links):
            q = (i + 0.5) / links
            sag = math.sin(q * math.pi) * (1.0 - taut) * 16
            x = sx + dx * q + nx * sag
            y = sy + dy * q + ny * sag
            r = pygame.Rect(int(x - 8), int(y - 5), 16, 10)
            pygame.draw.ellipse(layer, (58, 58, 56, 255), r, 2)
            pygame.draw.ellipse(layer, (136, 132, 122, 210), r.inflate(-4, -4), 1)
    _cb_surface_alpha_blit(surface, _draw, alpha)


def _cb_draw_forearm(surface, elbow, wrist, skin=CB_SKIN, sleeve=False, alpha=255):
    """Thick forearm line with a wrist/hand ellipse."""
    def _draw(layer):
        col = (skin[0], skin[1], skin[2], 255)
        shade = (CB_SKIN_SHADE[0], CB_SKIN_SHADE[1], CB_SKIN_SHADE[2], 255)
        if sleeve:
            pygame.draw.line(layer, (28, 34, 32, 255), elbow, wrist, 22)
            pygame.draw.line(layer, (16, 20, 18, 255), elbow, wrist, 3)
        else:
            pygame.draw.line(layer, shade, elbow, wrist, 19)
            pygame.draw.line(layer, col, elbow, wrist, 13)
        pygame.draw.circle(layer, col, wrist, 11)
        pygame.draw.circle(layer, shade, (wrist[0] + 3, wrist[1] + 3), 5)
    _cb_surface_alpha_blit(surface, _draw, alpha)


def _cb_draw_cuff(surface, wrist, angle=0.0, alpha=255):
    """Draw a heavy metal cuff around a wrist."""
    def _draw(layer):
        wx, wy = wrist
        r = pygame.Rect(int(wx - 15), int(wy - 9), 30, 18)
        pygame.draw.ellipse(layer, (22, 23, 24, 255), r)
        pygame.draw.ellipse(layer, (126, 122, 112, 255), r, 3)
        pygame.draw.ellipse(layer, (66, 64, 60, 255), r.inflate(-8, -6), 1)
        pygame.draw.circle(layer, (150, 145, 132, 255), (int(wx + 10), int(wy)), 2)
    _cb_surface_alpha_blit(surface, _draw, alpha)


def _cb_draw_biribel_seated_close(surface, cx, seat_y, yank=0.0, t=0):
    """Biribel's torso/arms in the restraint close-up."""
    # Arms pull out and down, the wrists fighting the cuffs.
    pull = _cb_smooth(yank)
    trem = math.sin(t * 0.35) * 5 * pull
    left_elbow = (int(cx - 45), int(seat_y - 82 + trem))
    right_elbow = (int(cx + 45), int(seat_y - 82 - trem))

    # Body in deep shadow behind the chair: the cast-sheet Biribel, seated,
    # upper arms out to the elbows (the forearms below carry the cuffs).
    foot = seat_y + 49
    _fk_draw(surface, "biribel", cx, foot, 1.165, facing_right=True, silhouette=True,
             seated=True, bow=0.5, fear=pull,
             reach=((left_elbow[0] - cx, left_elbow[1] - foot),
                    (right_elbow[0] - cx, right_elbow[1] - foot)))
    left_wrist = (int(cx - 132 - 22 * pull), int(seat_y - 46 - 8 * pull))
    right_wrist = (int(cx + 132 + 22 * pull), int(seat_y - 46 + 8 * pull))
    _cb_draw_forearm(surface, left_elbow, left_wrist)
    _cb_draw_forearm(surface, right_elbow, right_wrist)
    _cb_draw_cuff(surface, left_wrist)
    _cb_draw_cuff(surface, right_wrist)
    _cb_draw_chain_between(surface, (int(cx - 88), int(seat_y - 50)), left_wrist,
                           links=6, taut=0.95 + 0.05 * pull)
    _cb_draw_chain_between(surface, (int(cx + 88), int(seat_y - 50)), right_wrist,
                           links=6, taut=0.95 + 0.05 * pull)


def _cb_draw_stress_lines(surface, cx, cy, t, intensity=1.0):
    """Little white/orange impact ticks around the stressed chair joint."""
    rng = random.Random(300 + int(t // 45))
    count = int(10 * intensity)
    for _ in range(count):
        a = rng.uniform(-math.pi, math.pi)
        r1 = rng.randint(22, 48)
        r2 = r1 + rng.randint(8, 20)
        p1 = (int(cx + math.cos(a) * r1), int(cy + math.sin(a) * r1))
        p2 = (int(cx + math.cos(a) * r2), int(cy + math.sin(a) * r2))
        col = rng.choice([(210, 220, 215), (180, 145, 90), (120, 125, 130)])
        pygame.draw.line(surface, col, p1, p2, 1)


def _cb_draw_debris_burst(surface, origin, t, progress, count=42, metal=True):
    """Deterministic shards flying from the chair-break point."""
    rng = random.Random(913)
    ox, oy = origin
    for i in range(count):
        ang = rng.uniform(-math.pi, math.pi)
        speed = rng.uniform(40, 260)
        life = _cb_clamp(progress * 1.35 - i * 0.006)
        if life <= 0:
            continue
        x = ox + math.cos(ang) * speed * life
        y = oy + math.sin(ang) * speed * life + 90 * life * life
        ln = rng.randint(5, 20)
        rot = ang + life * rng.uniform(-3.0, 3.0)
        col = rng.choice([(96, 96, 92), (62, 60, 56), (138, 128, 105)]) if metal else CB_SPLINTER_HI
        alpha = int(255 * (1.0 - _cb_clamp((life - 0.7) / 0.3)))
        if alpha <= 0:
            continue
        shard = pygame.Surface((ln + 8, 8), pygame.SRCALPHA)
        pygame.draw.line(shard, (*col, alpha), (4, 4), (4 + ln, 4), rng.randint(1, 3))
        rot_s = pygame.transform.rotate(shard, -math.degrees(rot))
        surface.blit(rot_s, (int(x - rot_s.get_width() // 2), int(y - rot_s.get_height() // 2)))


def _cb_draw_flash(surface, alpha):
    """Chair-break flash removed entirely."""
    return


def _cb_finish(surface, t, label=None):
    """Shared chair-break post-process pass."""
    _cb_cinematic_grade(surface, t)
    draw_scanlines(surface)
    _cb_letterbox(surface)
    if label:
        # Small in-world-style caption, high enough not to fight the dialogue box.
        txt = font_terminal_small.render(label, True, (155, 170, 170))
        bg = pygame.Surface((txt.get_width() + 24, txt.get_height() + 10), pygame.SRCALPHA)
        bg.fill((0, 0, 0, 145))
        pygame.draw.rect(bg, (45, 60, 68), bg.get_rect(), 1)
        surface.blit(bg, (WIDTH - bg.get_width() - 28, LETTER_H + 18))
        surface.blit(txt, (WIDTH - bg.get_width() - 16, LETTER_H + 23))


SLEEVE = (88, 64, 46)
SLEEVE_D = (56, 42, 32)


def _cb2_lerp(a, b, u):
    return a + (b - a) * u


def _cb2_capsule(s, p1, p2, w, col):
    pygame.draw.line(s, col, (int(p1[0]), int(p1[1])), (int(p2[0]), int(p2[1])), max(1, int(round(w))))
    r = int(round(w / 2))
    pygame.draw.circle(s, col, (int(round(p1[0])), int(round(p1[1]))), r)
    pygame.draw.circle(s, col, (int(round(p2[0])), int(round(p2[1]))), r)



def _cb2_stage(s, t, light=1.0, floor_y=None, pool=(500, 600)):
    fy = floor_y or int(HEIGHT * CB_FLOOR_FRAC)
    for y in range(0, HEIGHT, 4):
        g = 10 + int(12 * (y / HEIGHT))
        pygame.draw.rect(s, (g, g + 1, g + 3), (0, y, WIDTH, 4))
    rng = random.Random(77)
    for _ in range(40):                                    # grime streaks
        x = rng.randrange(0, WIDTH); y = rng.randrange(0, fy)
        a = rng.randrange(10, 34)
        gr = pygame.Surface((rng.randrange(2, 5), rng.randrange(20, 90)), pygame.SRCALPHA)
        gr.fill((0, 0, 0, a)); s.blit(gr, (x, y))
    for sx in (250, 500, 750):                             # wall panel seams
        pygame.draw.line(s, (6, 7, 8), (sx, 0), (sx, fy), 1)
    pygame.draw.line(s, (30, 32, 34), (0, fy - 2), (WIDTH, fy - 2), 2)   # skirting
    pygame.draw.rect(s, (23, 24, 25), (0, fy, WIDTH, HEIGHT - fy))            # floor
    pygame.draw.polygon(s, (17, 18, 19), [(140, HEIGHT), (330, fy), (670, fy), (860, HEIGHT)])
    # door with lit slit
    pygame.draw.rect(s, (33, 35, 37), (830, fy - 366, 118, 366))
    pygame.draw.rect(s, (48, 50, 52), (830, fy - 366, 118, 366), 2)
    slit = pygame.Surface((52, 16), pygame.SRCALPHA)
    slit.fill((168, 148, 104, 150)); s.blit(slit, (863, fy - 250))
    glow = pygame.Surface((120, 60), pygame.SRCALPHA)
    pygame.draw.ellipse(glow, (168, 148, 104, 26), glow.get_rect()); s.blit(glow, (829, fy - 272))
    # overhead bulb + cone
    fl = light * (0.86 if (math.sin(t * 0.9) > 0.94 or math.sin(t * 0.23) > 0.985) else 1.0)
    cone = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
    pygame.draw.polygon(cone, (214, 204, 172, int(20 * fl)), [(472, 34), (528, 34), (770, fy), (230, fy)])
    pygame.draw.polygon(cone, (224, 214, 182, int(16 * fl)), [(482, 34), (518, 34), (660, fy), (340, fy)])
    pygame.draw.ellipse(cone, (215, 205, 175, int(34 * fl)), (pool[0] - 250, pool[1] - 52, 500, 104))
    s.blit(cone, (0, 0))
    pygame.draw.line(s, (70, 70, 66), (500, 0), (500, 22), 2)
    pygame.draw.circle(s, (235, 228, 200), (500, 28), 7)
    bl = pygame.Surface((90, 90), pygame.SRCALPHA)
    pygame.draw.circle(bl, (235, 228, 200, int(50 * fl)), (45, 45), 42)
    pygame.draw.circle(bl, (250, 244, 216, int(150 * fl)), (45, 45), 14)
    s.blit(bl, (455, -17))
    # dust motes in the cone
    mr = random.Random(5)
    for i in range(26):
        mx = mr.randrange(300, 700); my0 = mr.randrange(60, fy)
        sp = 0.15 + mr.random() * 0.3
        my = (my0 + t * sp * 6) % fy + 40
        if my < fy:
            a = int(26 + 30 * mr.random())
            s.set_at((int(mx + math.sin(t * 0.05 + i) * 6), int(my)), (140, 136, 120))
    _cb_vignette(s)


def _cb2_rot(cx, cy, pts, deg):
    a = math.radians(deg); ca, sa = math.cos(a), math.sin(a)
    return [(cx + x * ca - y * sa, cy + x * sa + y * ca) for x, y in pts]


def _cb2_chair(s, cx, fy, sc, tilt=0.0, broken=False):
    P = lambda dx, dy: _cb2_rot(cx, fy, [(dx * sc, dy * sc)], tilt)[0]
    # rear legs (depth pair, darker)
    for dx, col, wdt in ((-30, CB_METAL_DARK, 8), (46, CB_METAL_DARK, 8)):
        _cb2_capsule(s, P(dx + 12, 0), P(dx + 16, -92), wdt * sc, col)
    # brace
    pygame.draw.line(s, CB_METAL_DARK, P(-30, -38), P(46, -38), max(1, int(4 * sc)))
    # front + near-rear legs
    if broken:
        _cb2_capsule(s, P(-40, -92), P(-42, -64), 10 * sc, CB_METAL)
        teeth = [(-47, -64), (-44, -56), (-41, -64), (-38, -55), (-35, -63)]
        pygame.draw.polygon(s, CB_METAL_EDGE, [P(*q) for q in teeth])
        pygame.draw.circle(s, CB_METAL_EDGE, P(-41, -66), int(3 * sc))
    else:
        _cb2_capsule(s, P(-40, 0), P(-42, -92), 10 * sc, CB_METAL)
        pygame.draw.line(s, CB_METAL_EDGE, P(-44, -6), P(-45, -88), max(1, int(2 * sc)))
    _cb2_capsule(s, P(36, 0), P(40, -92), 10 * sc, CB_METAL)
    pygame.draw.line(s, CB_METAL_EDGE, P(32, -6), P(36, -88), max(1, int(2 * sc)))
    # seat pad + frame
    seat = [P(-58, -92), P(50, -92), P(52, -104), P(-56, -104)]
    pygame.draw.polygon(s, CB_METAL_DARK, [P(-58, -88), P(50, -88), P(50, -92), P(-58, -92)])
    pygame.draw.polygon(s, (38, 35, 31), seat)
    pygame.draw.line(s, (72, 68, 58), P(-54, -103), P(48, -103), max(1, int(2 * sc)))
    # backrest post + slat ends
    _cb2_capsule(s, P(44, -100), P(56, -196), 8 * sc, CB_METAL)
    for dy in (-120, -150, -180):
        pygame.draw.rect(s, (34, 31, 27), pygame.Rect(P(38, dy - 5), (int(20 * sc), int(10 * sc))))
        pygame.draw.line(s, (66, 62, 52), P(38, dy - 4), P(58, dy - 4), 1)


def _cb2_leg(s, center, length, width, angle, jag=True, sc=1.0, hero=False):
    cx, cy = center
    body_c = (74, 70, 62) if hero else CB_METAL
    edge_c = (122, 116, 102) if hero else CB_METAL_EDGE
    dark_c = (40, 38, 34) if hero else CB_METAL_DARK
    a = math.radians(angle); ux, uy = math.cos(a), math.sin(a)
    px, py = -uy, ux
    hl, hw = length / 2 * sc, width / 2 * sc
    body = [(cx - ux * hl + px * hw, cy - uy * hl + py * hw),
            (cx + ux * hl + px * hw, cy + uy * hl + py * hw),
            (cx + ux * hl - px * hw, cy + uy * hl - py * hw),
            (cx - ux * hl - px * hw, cy - uy * hl - py * hw)]
    pygame.draw.polygon(s, body_c, body)
    pygame.draw.line(s, edge_c, body[0], body[1], max(1, int(2 * sc)))
    pygame.draw.line(s, dark_c, body[3], body[2], max(1, int(2 * sc)))
    pygame.draw.line(s, edge_c, (_cb2_lerp(body[0][0], body[3][0], 0.35), _cb2_lerp(body[0][1], body[3][1], 0.35)),
                     (_cb2_lerp(body[1][0], body[2][0], 0.35), _cb2_lerp(body[1][1], body[2][1], 0.35)), 1)
    rng = random.Random(9)
    for _ in range(5):
        q = rng.uniform(-0.8, 0.8)
        gx, gy = cx + ux * hl * q, cy + uy * hl * q
        s.set_at((int(gx), int(gy)), CB_SPLINTER)
        s.set_at((int(gx) + 1, int(gy) + 1), CB_SPLINTER_HI)
    if jag:
        teeth = []
        for i in range(4):
            f = -hw + i * (hw * 2 / 3)
            teeth.append((cx - ux * hl + px * f - ux * 7 * sc, cy - uy * hl + py * f - uy * 7 * sc))
            teeth.append((cx - ux * hl + px * (f + hw / 1.5), cy - uy * hl + py * (f + hw / 1.5)))
        pygame.draw.polygon(s, edge_c, teeth)
    else:
        pygame.draw.ellipse(s, edge_c, (int(cx - ux * hl - 4), int(cy - uy * hl - 4), 8, 8), 2)


def _cb2_grip(s, wrist, axis_deg, side, sc, curl=1.0, yank=0.0, cuff=True,
              chain_dir=None, grip_d=26):
    """Fist wrapped on a tube - delegates to the shared core.hands model."""
    _core_grip_hand(s, wrist, axis=axis_deg, mirror=side, sc=sc, curl=curl,
                    yank=yank, grip_d=grip_d, cuff=cuff, chain_dir=chain_dir)


def _cb2_forearm(s, elbow, wrist, sc=1.0):
    """Tapered sleeve polygon (no pipe elbows)."""
    dx, dy = wrist[0] - elbow[0], wrist[1] - elbow[1]
    d = math.hypot(dx, dy) or 1
    px, py = -dy / d, dx / d
    w0, w1 = 15 * sc, 9 * sc
    quad = [(elbow[0] + px * w0, elbow[1] + py * w0),
            (wrist[0] + px * w1, wrist[1] + py * w1),
            (wrist[0] - px * w1, wrist[1] - py * w1),
            (elbow[0] - px * w0, elbow[1] - py * w0)]
    pygame.draw.polygon(s, SLEEVE_D, quad)
    pygame.draw.polygon(s, SLEEVE, [(_cb2_lerp(q[0], (elbow[0] + wrist[0]) / 2, 0.18),
                                    _cb2_lerp(q[1], (elbow[1] + wrist[1]) / 2, 0.18)) for q in quad])
    pygame.draw.line(s, SLEEVE_D, (wrist[0] - px * w1, wrist[1] - py * w1),
                     (wrist[0] + px * w1, wrist[1] + py * w1), 2)


def _cb2_debris(s, origin, t, count=16, t0=4):
    tt = max(0, t - t0)
    rng = random.Random(31)
    for i in range(count):
        ang = rng.uniform(-math.pi, 0) + rng.uniform(-0.4, 0.4)
        sp = rng.uniform(2.2, 6.5)
        vx, vy = math.cos(ang) * sp, math.sin(ang) * sp
        x = origin[0] + vx * tt
        y = origin[1] + vy * tt + 0.16 * tt * tt
        if y > HEIGHT - 90: y = HEIGHT - 90 - (y - (HEIGHT - 90)) * 0.3
        rot_d = rng.uniform(0, 360) + tt * rng.uniform(-14, 14)
        col = [CB_METAL_EDGE, CB_SPLINTER, CB_SPLINTER_HI, CB_METAL][i % 4]
        ln = rng.uniform(4, 9)
        a = math.radians(rot_d)
        pygame.draw.line(s, col, (x - math.cos(a) * ln, y - math.sin(a) * ln),
                         (x + math.cos(a) * ln, y + math.sin(a) * ln), 2)


def _cb2_wisp(s, x, y, t, t0, sc=1.0):
    tt = max(0, t - t0)
    if tt == 0: return
    a = max(0, 46 - tt * 0.7)
    w = pygame.Surface((int(90 * sc), int(46 * sc)), pygame.SRCALPHA)
    pygame.draw.ellipse(w, (120, 118, 110, int(a)), (0, int(10 - tt * 0.25), int(90 * sc), int(30 * sc)))
    pygame.draw.ellipse(w, (140, 138, 128, int(a * 0.6)), (int(18 * sc), int(4 - tt * 0.35), int(50 * sc), int(20 * sc)))
    s.blit(w, (int(x - 45 * sc), int(y - 23 * sc)))


def _cb2_stress(s, x, y, t, inten):
    if inten <= 0.02: return
    rng = random.Random(12)
    for i in range(4):
        a = rng.uniform(0, math.tau)
        l = rng.uniform(8, 20) * inten
        flick = 0.5 + 0.5 * math.sin(t * 0.9 + i * 2.1)
        c = int(40 + 80 * flick * inten)
        pygame.draw.line(s, (c, c - 6, c - 14), (x + math.cos(a) * 6, y + math.sin(a) * 6),
                         (x + math.cos(a) * (6 + l), y + math.sin(a) * (6 + l)), 1)


def _draw_cb_strain(surface, t_value, *args, clock_is_ms=False, **kwargs):
    t = _cb_time_to_frames(t_value, clock_is_ms)
    s = surface
    p = _cb_clamp(t / CB_SHOT1_DUR)
    yank = _cb_smooth(p)
    spike = 1.6 if t > CB_SHOT1_DUR - 12 else 1.0
    sx, sy = _cb_camera_shake(t, (1.2 + 5.0 * yank + abs(math.sin(t * 0.4)) * 2.0 * yank) * spike)
    s.fill(CB_BG)
    _cb2_stage(s, t, light=1.0, floor_y=700, pool=(500, 660))
    cx, fy, sc = 560 + sx * 0.6, 660 + sy * 0.6, 2.3
    tilt = -(2.0 + 3.2 * yank) + math.sin(t * 0.13) * 1.1 * yank
    _cb2_chair(s, cx, fy, sc, tilt, broken=False)
    _cb2_capsule(s, (cx - 44 * sc, fy - 92 * sc), (cx - 45 * sc, fy - 2), 10 * sc, (74, 70, 62))
    pygame.draw.line(s, (122, 116, 102), (cx - 48 * sc, fy - 92 * sc), (cx - 49 * sc, fy - 4), 3)
    # hands gripping the near-front leg
    legx = cx - 41 * sc * 0.98
    gy1, gy2 = 470 + sy * 0.4, 545 + sy * 0.4
    tr1 = math.sin(t * 1.9) * 2.2 * yank * spike
    tr2 = math.cos(t * 2.3) * 2.0 * yank * spike
    _cb2_forearm(s, (legx - 240, gy1 + 235), (legx - 30 + tr1, gy1 + 6), 1.5)
    _cb2_forearm(s, (legx - 255, gy2 + 220), (legx - 34 + tr2, gy2 + 4), 1.5)
    _cb2_grip(s, (legx - 2 + tr1, gy1), 86, 1, 1.6, curl=1.0, yank=yank,
              chain_dir=(legx - 46, (gy1 + gy2) / 2), grip_d=24)
    _cb2_grip(s, (legx + 4 + tr2, gy2), 94, 1, 1.6, curl=1.0, yank=yank * 0.85,
              cuff=False, grip_d=24)
    # chain between the two cuffs, taut and buzzing
    jx = math.sin(t * 1.3) * 1.6 * yank
    for k in range(5):
        u = (k + 1) / 6
        lx, ly = _cb2_lerp(legx - 26, legx - 28, u) + jx, _cb2_lerp(gy1 + 8, gy2 - 4, u)
        pygame.draw.ellipse(s, CB_METAL_DARK, (int(lx - 6), int(ly - 4), 12, 8), 3)
        pygame.draw.ellipse(s, CB_METAL_EDGE, (int(lx - 6), int(ly - 4), 12, 8), 1)
    # stress at the leg/seat joint + growing hairline cracks
    jx2, jy2 = cx - 42 * sc, fy - 96 * sc
    _cb2_stress(s, jx2, jy2, t, yank)
    for i, ln in enumerate((6, 10, 14)):
        if p > 0.25 + i * 0.22:
            pygame.draw.line(s, (16, 15, 14), (jx2 + 2, jy2 + 8 + i * 26),
                             (jx2 + 7, jy2 + 16 + i * 26), 1)
    # dust shaken loose from the seat edge
    rng = random.Random(3)
    for i in range(9):
        dx0 = rng.uniform(-50, 40)
        cyc = (t * 1.8 + i * 41) % 150
        if cyc < 120 * yank + 10:
            px_, py_ = jx2 + dx0 + math.sin(i * 9) * 4, jy2 + 6 + cyc
            al = max(0, 90 - cyc)
            s.set_at((int(px_), int(py_)), (110 + al // 3, 105 + al // 3, 95 + al // 3))
    _cb_vignette(s)
    _cb_letterbox(s)


def _draw_cb_crack(surface, t_value, *args, clock_is_ms=False, **kwargs):
    t = _cb_time_to_frames(t_value, clock_is_ms)
    s = surface
    p = _cb_clamp(t / CB_SHOT2_DUR)
    sx, sy = _cb_camera_shake(t, 9.0 * math.exp(-t / 22))
    s.fill(CB_BG)
    _cb2_stage(s, t, floor_y=520, pool=(520, 512))
    cx, fy, sc = 560 + sx * 0.5, 520 + sy * 0.5, 1.35
    recoil = 6.0 + 3.5 * math.exp(-t / 16) + math.sin(t * 0.5) * 0.6 * math.exp(-t / 40)
    _cb2_chair(s, cx, fy, sc, -recoil, broken=(t >= 4))
    joint = _cb2_rot(cx, fy, [(-42 * sc, -92 * sc)], -recoil)[0]
    land = (cx + CB_BROKEN_LEG_DX * 1.28, fy - 8)
    lpos = None
    if t < 4:
        lpos = (joint[0], joint[1] + 46 * sc)
        _cb2_leg(s, lpos, CB_BROKEN_LEG_LEN, CB_BROKEN_LEG_W, 88, sc=1.15)
    else:
        u = _cb_clamp((t - 4) / 46)
        e = _cb_ease_out(u)
        lx, ly = _cb2_lerp(joint[0], land[0], e), _cb2_lerp(joint[1] + 40, land[1], e) - math.sin(math.pi * u) * 90
        ang = _cb2_lerp(88, CB_BROKEN_LEG_ANGLE, e) - 300 * u
        if u >= 1.0:
            bt = t - 50
            if bt > 0: ly -= abs(math.sin(bt * 0.28)) * 7 * math.exp(-bt / 18)
        lpos = (lx, ly)
        _cb2_leg(s, lpos, CB_BROKEN_LEG_LEN, CB_BROKEN_LEG_W, ang, sc=1.15, hero=True)
        if u >= 1.0:
            _cb2_wisp(s, land[0], land[1] - 6, t, 50, 0.9)
    # the tearing hand rides the leg; the other hand recoils open and exits
    _cb2_grip(s, (lpos[0] + 6, lpos[1] - 4), 90, 1, 1.35, curl=1.0,
              yank=1.0 if t < 50 else 0.6, cuff=True, chain_dir=(lpos[0] - 44, lpos[1] + 40))
    if t < 30:
        ru = t / 30.0
        hx, hy = joint[0] - 60 - 130 * ru, joint[1] + 10 - 170 * ru
        _cb2_capsule(s, (hx - 50, hy + 90), (hx, hy + 18), 15, SLEEVE)
        _cb2_capsule(s, (hx, hy + 18), (hx, hy), 12, CB_SKIN)
        for i in range(4):
            a = math.radians(-90 + (i - 1.5) * 26 * (1 - ru * 0.4))
            _cb2_capsule(s, (hx, hy), (hx + math.cos(a) * 24, hy + math.sin(a) * 24), 6, CB_SKIN)
        pygame.draw.circle(s, CB_SKIN, (int(hx), int(hy)), 9)
    if t < 8:
        for i in range(12):
            a = i * math.tau / 12 + 0.3
            al = int(180 * (1 - t / 8))
            ln = 40 + 90 * (t / 8)
            pygame.draw.line(s, (160, 155, 140),
                             (joint[0] + math.cos(a) * 12, joint[1] + math.sin(a) * 12),
                             (joint[0] + math.cos(a) * ln, joint[1] + math.sin(a) * ln), 2)
    _cb2_debris(s, joint, t, t0=4)
    _cb2_wisp(s, joint[0], joint[1], t, 26, 1.1)
    _cb_vignette(s)
    _cb_letterbox(s)


def _draw_cb_grab(surface, t_value, *args, clock_is_ms=False, **kwargs):
    t = _cb_time_to_frames(t_value, clock_is_ms)
    s = surface
    p = _cb_clamp(t / CB_SHOT3_DUR)
    sx, sy = _cb_camera_shake(t, 2.0 * math.exp(-t / 30) + (0.9 if t > 124 else 0))
    s.fill(CB_BG)
    _cb2_stage(s, t, floor_y=560, pool=(470, 560))
    base = (430 + sx * 0.4, 470 + sy * 0.4)
    u3 = _cb_smooth(_cb_clamp((t - 84) / 40))
    u2 = _cb_smooth(_cb_clamp((t - 12) / 40))
    ang = _cb2_lerp(CB_BROKEN_LEG_ANGLE, -78, u3)
    cen = (_cb2_lerp(base[0], 520, u3), _cb2_lerp(base[1], 360, u3))
    scl = _cb2_lerp(1.15, 1.42, u3)
    _cb2_leg(s, cen, CB_BROKEN_LEG_LEN, CB_BROKEN_LEG_W, ang, sc=scl, hero=True)
    # dust shaken off the leg during the yank
    if 84 < t < 116:
        rng = random.Random(44)
        for i in range(10):
            cyc = (t - 84) * 2.2 + i * 13
            px_, py_ = cen[0] + rng.uniform(-40, 40), cen[1] + 20 + cyc
            if py_ < 560: s.set_at((int(px_), int(py_)), (105, 100, 90))
    # the hand that tore it off: planted, tightening, then lifting
    a = math.radians(ang)
    gx, gy = cen[0] + math.cos(a) * 34 * u3 + 10, cen[1] + math.sin(a) * 34 * u3 - 4
    tw = math.sin(t * 0.35) * 1.5 * (1 - u3)
    _cb2_forearm(s, (gx + 250, gy - 200 + tw), (gx + 24, gy - 12), 1.35)
    _cb2_grip(s, (gx + tw, gy), ang + 90, 1, 1.45, curl=1.0,
              yank=0.25 + 0.75 * u2, cuff=True, chain_dir=(gx + 40, gy + 46))
    _cb_vignette(s)
    _cb_letterbox(s)


def _draw_cb_ready(surface, t_value, *args, clock_is_ms=False, **kwargs):
    """Shot 4 - cold resolve: Biribel up on his feet, chair leg held like a
    club, wrecked chair behind him in the light pool.

    v2 staging: readable silhouette (shoulder capsules, tapered jumpsuit,
    real head with hair/face), the club gripped by the reference-model fist
    (knuckles to camera), hanging cuff chain between the wrists, key light
    from the bulb plus door-slit rim, breathe + head-raise beats, fade out.
    """
    t = _cb_time_to_frames(t_value, clock_is_ms)
    s = surface
    _cb2_stage(s, t, floor_y=546, pool=(470, 560))
    sx, sy = _cb_camera_shake(t, 0.7)

    # wrecked chair behind, tilted on the broken stump
    _cb2_chair(s, 700 + sx * 0.3, 546, 1.0, -8, broken=True)

    breathe = math.sin(t * 0.09) * 2
    nod = 4 * _cb_smooth(_cb_clamp((t - 40) / 30))
    bx, by = 440 + sx * 0.4, 560
    suit, suit_d = SLEEVE, SLEEVE_D
    skin = CB_SKIN
    ty = breathe
    wr_r = (bx + 42, by - 152 + ty)   # right fist on the club
    wr_l = (bx - 28, by - 110 + ty)   # left wrist hangs, chain to the right

    # ── Biribel: the cast-sheet figure (figure_kit) in the prison jumpsuit.
    # Face/build/hair are his canonical ones; only the wardrobe changes.
    # The head raises out of the bow on the resolve beat (nod 0 -> 4).
    _fk_draw(s, "biribel", bx, by, 0.84, facing_right=True,
             t=t * 1000.0 / 60.0, bow=0.6 * (1 - nod / 4.0), look=0.4,
             reach=((wr_l[0] - bx, wr_l[1] - by), (wr_r[0] - bx, wr_r[1] - by)),
             wardrobe=dict(coat=suit, lapel=suit_d, shirt=suit_d, tie=None, vest=None,
                           patch=None, trousers=suit, belt=suit_d, long_coat=False))

    # ── the club: tapered leg, jagged break at the top ──
    # A chair leg is ~seat-height, not a greatsword: keep it ~45% of his
    # torso+head so the club reads as the same object the chair lost.
    club_top = (bx + 48, by - 180 + breathe * 0.5)
    club_bot = (bx + 38, by - 122)
    dx, dy = club_bot[0] - club_top[0], club_bot[1] - club_top[1]
    dl = math.hypot(dx, dy) or 1
    ux, uy = dx / dl, dy / dl
    px, py = -uy, ux
    hw_t, hw_b = 6.5, 5.0
    body = [(club_top[0] + px * hw_t, club_top[1] + py * hw_t),
            (club_bot[0] + px * hw_b, club_bot[1] + py * hw_b),
            (club_bot[0] - px * hw_b, club_bot[1] - py * hw_b),
            (club_top[0] - px * hw_t, club_top[1] - py * hw_t)]
    pygame.draw.polygon(s, (74, 70, 62), body)
    pygame.draw.line(s, (122, 116, 102), body[0], body[1], 2)
    pygame.draw.line(s, (40, 38, 34), body[3], body[2], 2)
    teeth = []
    for i in range(4):  # jagged break at the top
        f = -hw_t + i * (hw_t * 2 / 3)
        teeth.append((club_top[0] + px * f - ux * 8, club_top[1] + py * f - uy * 8))
        teeth.append((club_top[0] + px * (f + hw_t / 1.5), club_top[1] + py * (f + hw_t / 1.5)))
    pygame.draw.polygon(s, (122, 116, 102), teeth)
    pygame.draw.ellipse(s, (52, 48, 42), (int(club_bot[0] - 7), int(club_bot[1] - 4), 14, 8))

    # ── reference-model fist on the club (arm comes from the cast figure) ──
    _core_grip_hand(s, wr_r, axis=-80, mirror=1, sc=1.0, curl=1.0, yank=0.35,
                    cuff=True, grip_d=16)

    # ── left wrist cuff; chain sags between the wrists ──
    pygame.draw.circle(s, skin, (int(wr_l[0]), int(wr_l[1] + 5)), 6)
    pygame.draw.line(s, CB_METAL_DARK, (wr_l[0] - 6, wr_l[1]), (wr_l[0] + 6, wr_l[1]), 7)
    pygame.draw.line(s, CB_METAL_EDGE, (wr_l[0] - 6, wr_l[1] - 3), (wr_l[0] + 6, wr_l[1] - 3), 1)
    for k in range(5):
        u = (k + 1) / 6
        lx = _cb2_lerp(wr_l[0], wr_r[0], u)
        ly = _cb2_lerp(wr_l[1], wr_r[1], u) + math.sin(u * math.pi) * 18
        r = pygame.Rect(int(lx - 4), int(ly - 3), 8, 6)
        pygame.draw.ellipse(s, CB_METAL_DARK, r, 2)
        pygame.draw.ellipse(s, CB_METAL_EDGE, r, 1)

    # door-slit rim on his left edge + bulb key light on the shoulders
    pygame.draw.line(s, (150, 132, 96), (bx - 24, by - 166 + ty), (bx - 19, by - 114), 1)
    key = pygame.Surface((220, 120), pygame.SRCALPHA)
    pygame.draw.ellipse(key, (215, 205, 175, 26), (0, 0, 220, 120))
    s.blit(key, (int(bx - 110), int(by - 230 + ty)))

    if t > 150:
        a = int(255 * _cb_clamp((t - 150) / 30))
        fk = pygame.Surface((WIDTH, HEIGHT))
        fk.fill((0, 0, 0))
        fk.set_alpha(a)
        s.blit(fk, (0, 0))
    _cb_finish(s, t)


# RPE6 Phase 2 (A-003 take registry): the cutscene scene ids this module owns.
# cutscenes.engine.draw_cutscene_scene finds them through core.cutscene_registry
# instead of importing this module by name (boundary rule 4 / W1).
from core.cutscene_registry import register_scene_renderers as _register_takes  # noqa: E402
import functools  # noqa: E402

_register_takes({
    "cb_strain": functools.partial(_draw_cb_strain, clock_is_ms=True),
    "cb_crack": functools.partial(_draw_cb_crack, clock_is_ms=True),
    "cb_grab": functools.partial(_draw_cb_grab, clock_is_ms=True),
    "cb_ready": functools.partial(_draw_cb_ready, clock_is_ms=True),
})
