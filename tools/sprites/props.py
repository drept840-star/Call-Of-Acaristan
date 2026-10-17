"""props.py - Mission 2 story props + the upload terminal as sprites (Polish T7).

Replaces the static parts of ``missions/m2/draw.py::_draw_story_prop`` and
``_draw_upload_computer``. Animated bits that depend on live state stay
procedural on top of the sprite (spark bursts, flare glow, glint flashes,
charred-prop ember pulses); the upload terminal's phosphor pulse, cursor
blink and LEDs are baked as 8 frames (4 pulse levels x cursor on/off).

Anchor = the prop's world position (the procedural code's (sx, sy)):
blit at (sx - ax, sy - ay).

    python tools/sprites/props.py [--preview] [--out DIR]
"""
import math
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import kit  # noqa: E402
import palette as P  # noqa: E402
import pygame  # noqa: E402

FAMILY = "props"
PULSES = (0.0, 0.33, 0.67, 1.0)


def _frame(w, h):
    return kit.new(w, h), w // 2, h // 2


def cone(charred=False):
    s, cx, cy = _frame(40, 44)
    if charred:
        kit.ellipse_shadow(s, (cx - 15, cy + 2, 34, 12))
        b = kit.new(40, 44)
        C = [(18, 14, 12), (30, 24, 20), (44, 36, 30), (60, 50, 42)]
        pygame.draw.ellipse(b, C[1], (cx - 16, cy - 4, 32, 12))     # melted puddle of cone
        pygame.draw.ellipse(b, C[2], (cx - 12, cy - 3, 22, 7))
        b.fill(C[3], (cx - 9, cy - 3, 10, 1))
        kit.rrect(b, C[0], (cx - 15, cy + 6, 30, 5), 1)
        b.fill(C[2], (cx - 14, cy + 6, 28, 1))
        s.blit(kit.outline(b, (8, 6, 5)), (0, 0))
        return s, (cx, cy)
    kit.ellipse_shadow(s, (cx - 14, cy + 9, 34, 10))
    b = kit.new(40, 44)
    O = P.ramp(P.CONE_ORANGE)
    kit.rrect(b, P.ramp((92, 62, 38))[2], (cx - 15, cy + 10, 30, 6), 1)       # rubber base
    b.fill(P.ramp((92, 62, 38))[3], (cx - 14, cy + 10, 28, 1))
    b.fill(P.ramp((92, 62, 38))[1], (cx - 14, cy + 15, 28, 1))
    pygame.draw.polygon(b, O[3], [(cx, cy - 17), (cx - 12, cy + 12), (cx, cy + 12)])   # lit left face
    pygame.draw.polygon(b, O[1], [(cx, cy - 17), (cx + 12, cy + 12), (cx, cy + 12)])   # shaded right face
    pygame.draw.line(b, O[4], (cx - 1, cy - 15), (cx - 6, cy + 2))
    for y, wdt in ((cy - 4, 6), (cy + 3, 9)):                                         # reflective bands
        b.fill((248, 226, 160), (cx - wdt, y, wdt, 3))
        b.fill((196, 176, 120), (cx, y, wdt, 3))
    s.blit(kit.outline(b), (0, 0))
    return s, (cx, cy)


def barrel(charred=False):
    s, cx, cy = _frame(40, 48)
    kit.ellipse_shadow(s, (cx - 12, cy + 10, 32, 12))
    b = kit.new(40, 48)
    if charred:
        C = [(14, 11, 9), (22, 18, 15), (34, 28, 23), (50, 42, 34)]
        kit.rrect(b, C[1], (cx - 13, cy - 15, 26, 30), 5)
        kit.rrect(b, C[2], (cx - 12, cy - 15, 8, 29), 3)
        for y0, y1 in ((cy - 4, cy - 2), (cy + 6, cy + 4)):
            pygame.draw.line(b, C[0], (cx - 12, y0), (cx + 12, y1), 2)
        pygame.draw.ellipse(b, C[0], (cx - 11, cy - 17, 22, 7))
        b.fill(C[3], (cx - 6, cy - 17, 8, 1))
        s.blit(kit.outline(b, (8, 6, 5)), (0, 0))
        return s, (cx, cy)
    R = P.ramp(P.BARREL_RUST)
    kit.rrect(b, R[2], (cx - 13, cy - 15, 26, 32), 5)
    b.fill(R[3], (cx - 11, cy - 14, 7, 30))           # lit left of the drum
    b.fill(R[4], (cx - 9, cy - 13, 2, 28))
    b.fill(R[1], (cx + 6, cy - 14, 6, 30))            # shade right
    b.fill(R[0], (cx + 10, cy - 12, 2, 26))
    for hy in (cy - 5, cy + 7):                        # rolling hoops
        b.fill(R[0], (cx - 12, hy, 24, 2))
        b.fill(R[4], (cx - 12, hy + 2, 24, 1))
    pygame.draw.ellipse(b, R[3], (cx - 13, cy - 19, 26, 8))   # lid
    pygame.draw.ellipse(b, R[1], (cx - 9, cy - 18, 18, 6), 1)
    b.fill(R[0], (cx + 6, cy - 16, 2, 2))             # bung
    b.fill(P.shade(R[2], 0.8), (cx - 8, cy - 11, 1, 24))   # weld seam
    s.blit(kit.outline(b), (0, 0))
    return s, (cx, cy)


def sign(charred=False):
    s, cx, cy = _frame(64, 56)
    oy = 4
    if charred:
        kit.ellipse_shadow(s, (cx - 22, cy + 8, 44, 12))
        b = kit.new(64, 56)
        pygame.draw.line(b, (35, 30, 25), (cx - 4, cy + 12), (cx + 6, cy - 6), 3)
        kit.rrect(b, (28, 24, 20), (cx - 18, cy - 4, 38, 16), 1)
        b.fill((45, 38, 32), (cx - 17, cy - 4, 36, 1))
        pygame.draw.ellipse(b, (14, 11, 9), (cx - 8, cy - 1, 20, 9))
        s.blit(kit.outline(b, (8, 6, 5)), (0, 0))
        return s, (cx, cy)
    kit.ellipse_shadow(s, (cx - 20, cy + 11, 40, 10))
    b = kit.new(64, 56)
    pygame.draw.line(b, (80, 80, 72), (cx - 10, cy + 14), (cx + 12, cy - 16), 3)
    pygame.draw.line(b, (124, 124, 112), (cx - 11, cy + 13), (cx + 11, cy - 17), 1)
    S = P.ramp(P.SIGN_STEEL)
    px, py, pw, ph = cx - 26, cy - 25, 42, 18
    b.fill(S[2], (px, py, pw, ph))
    b.fill(S[3], (px, py, pw, ph // 2))
    b.fill((150, 150, 125), (px, py, pw, 2))           # reflective rim
    b.fill((150, 150, 125), (px, py, 2, ph))
    b.fill(P.shade((150, 150, 125), 0.7), (px, py + ph - 2, pw, 2))
    b.fill(P.shade((150, 150, 125), 0.7), (px + pw - 2, py, 2, ph))
    b.fill((190, 190, 160), (px + 3, py + 3, pw - 7, 1))
    kit.text(b, "12", cx - 5 - kit.text_w("12") // 2, py + 6, (210, 210, 178))
    s.blit(kit.outline(b), (0, 0))
    return s, (cx, cy)


def broken_camera():
    s, cx, cy = _frame(64, 52)
    kit.shadow(s, (cx - 16, cy - 9, 32, 18), r=3, alpha=(60, 30))
    b = kit.new(64, 52)
    B = P.ramp((40, 44, 46))
    pygame.draw.line(b, (80, 84, 82), (cx - 14, cy - 8), (cx - 28, cy - 24), 2)     # snapped mount
    pygame.draw.line(b, (125, 40, 35), (cx - 12, cy + 2), (cx - 25, cy + 12), 2)    # torn red lead
    kit.rrect(b, B[2], (cx - 16, cy - 9, 32, 18), 3)
    kit.inner_line(b, (cx - 15, cy - 9, 30, 18), B[3], B[1])
    b.fill(B[4], (cx - 13, cy - 9, 18, 1))
    for i in range(4):
        b.fill(B[1], (cx - 12 + i * 3, cy - 4, 1, 9))  # vents
    pygame.draw.circle(b, (5, 7, 8), (cx + 8, cy), 7)
    pygame.draw.circle(b, (40, 52, 60), (cx + 8, cy), 7, 1)
    pygame.draw.line(b, (120, 140, 150), (cx + 4, cy - 3), (cx + 11, cy + 3))          # cracked lens
    b.set_at((cx + 6, cy - 3), (170, 190, 200))
    s.blit(kit.outline(b), (0, 0))
    return s, (cx, cy)


def spark_box():
    s, cx, cy = _frame(44, 48)
    kit.shadow(s, (cx - 14, cy - 16, 28, 32), r=3, alpha=(60, 30))
    b = kit.new(44, 48)
    B = P.ramp((52, 56, 50))
    kit.rrect(b, B[2], (cx - 14, cy - 16, 28, 32), 3)
    b.fill(B[3], (cx - 13, cy - 15, 9, 30))
    b.fill(B[4], (cx - 13, cy - 15, 1, 30))
    b.fill(B[1], (cx + 8, cy - 15, 5, 30))
    b.fill(B[0], (cx + 2, cy - 14, 1, 28))                     # door seam
    b.fill(B[4], (cx + 3, cy - 14, 1, 28))
    b.fill((120, 104, 40), (cx - 11, cy + 6, 14, 4))           # hazard label
    b.fill((30, 30, 26), (cx - 11, cy + 9, 14, 1))
    for x in range(cx - 10, cx + 3, 4):
        b.fill((30, 30, 26), (x, cy + 6, 2, 3))
    b.fill((180, 60, 40), (cx - 9, cy - 11, 3, 3))            # dead status lamp
    b.set_at((cx - 9, cy - 11), (230, 120, 90))
    s.blit(kit.outline(b), (0, 0))
    return s, (cx, cy)


def puddle():
    s, cx, cy = _frame(88, 46)
    ox, oy = cx - 42, cy - 21
    pts = [(10, 22), (20, 10), (40, 5), (62, 9), (76, 18), (70, 30), (48, 36), (24, 33)]
    pygame.draw.polygon(s, (22, 32, 42, 120), [(ox + x, oy + y) for x, y in pts])
    pygame.draw.polygon(s, (60, 76, 92, 80), [(ox + x, oy + y) for x, y in pts], 1)
    inner = [(20, 22), (28, 14), (44, 10), (60, 14), (66, 20), (56, 28), (38, 30)]
    pygame.draw.polygon(s, (16, 24, 34, 140), [(ox + x, oy + y) for x, y in inner])
    for (x1, y1, x2, a) in ((26, 16, 44, 110), (50, 20, 62, 80)):   # sky reflection streaks
        s.fill((150, 172, 190, a), (ox + x1, oy + y1, x2 - x1, 1))
    return s, (cx, cy)


def puddle_scorch():
    s, cx, cy = _frame(100, 54)
    pygame.draw.ellipse(s, (8, 6, 5, 140), (cx - 48, cy - 25, 96, 50), 4)
    return s, (cx, cy)


def soot():
    s, cx, cy = _frame(100, 64)
    pygame.draw.ellipse(s, (8, 7, 6, 110), (cx - 48, cy - 30, 95, 60))
    pygame.draw.ellipse(s, (8, 7, 6, 60), (cx - 36, cy - 22, 70, 44))
    pygame.draw.ellipse(s, (55, 42, 28, 50), (cx - 38, cy - 22, 76, 42), 2)
    return s, (cx, cy)


def flare():
    s, cx, cy = _frame(32, 16)
    b = kit.new(32, 16)
    R = P.ramp((95, 35, 25))
    kit.rrect(b, R[2], (cx - 10, cy - 3, 20, 6), 2)
    b.fill(R[3], (cx - 9, cy - 3, 18, 1))
    b.fill(R[1], (cx - 9, cy + 2, 18, 1))
    b.fill(P.CREAM, (cx - 4, cy - 2, 3, 4))           # paper band
    s.blit(kit.outline(b), (0, 0))
    return s, (cx, cy)


def upload_pc(pulse, cursor):
    W, H = 60, 52
    s = kit.new(W, H)
    sx, sy = 24, 26
    led = 0.5 + 0.5 * math.sin(pulse * 5.0)
    B = P.ramp(P.CASE_BEIGE)
    OUT = (78, 70, 50)
    kit.shadow(s, (sx - 18, sy - 19, 36 + 12, 36), r=3, alpha=(60, 30))
    b = kit.new(W, H)
    # tower (right): slim, vents, power LED
    tx, ty = sx + 17, sy - 17
    kit.rrect(b, B[2], (tx, ty, 10, 28), 1)
    b.fill(B[3], (tx + 1, ty + 1, 1, 26))
    b.fill(B[1], (tx + 8, ty + 1, 1, 26))
    b.fill((50, 48, 42), (tx + 2, ty + 3, 6, 2))
    for i in range(3):
        b.fill(B[1], (tx + 2, ty + 8 + i * 2, 6, 1))
    led_c = P.clamp((80 + 120 * led, 220 + 35 * led, 80 + 40 * led))
    b.fill(led_c, (tx + 4, ty + 23, 2, 2))
    # monitor
    mx, my = sx - 18, sy - 19
    kit.rrect(b, B[1], (mx + 2, my + 3, 36, 28), 3)
    kit.rrect(b, B[2], (mx, my, 36, 26), 3)
    b.fill(B[4], (mx + 2, my + 1, 32, 1))
    b.fill(B[3], (mx + 1, my + 2, 1, 22))
    bz = (mx + 4, my + 4, 28, 17)
    kit.rrect(b, (40, 38, 30), bz, 2)
    gx, gy, gw, gh = bz[0] + 1, bz[1] + 1, bz[2] - 2, bz[3] - 2
    phos = P.mix(P.CRT_GLASS, P.PHOSPHOR, 0.45 + 0.4 * pulse)
    b.fill(phos, (gx, gy, gw, gh))
    b.fill(P.mix(phos, P.PHOSPHOR_HI, 0.35 + 0.25 * pulse), (gx + 1, gy + gh // 4, gw - 2, gh // 2))
    for ly in range(gy, gy + gh, 2):
        b.fill(P.mix(phos, (40, 110, 60), 0.6), (gx, ly, gw, 1))
    b.set_at((gx, gy), P.mix(phos, (230, 255, 235), 0.5))    # glass glint upper-left
    b.set_at((gx + 1, gy), P.mix(phos, (230, 255, 235), 0.3))
    if cursor:
        b.fill(P.PHOSPHOR_HI, (gx + 2, gy + gh - 4, 2, 2))
    b.fill(led_c, (bz[0] + bz[2] - 2, bz[1] + bz[3] + 2, 1, 1))
    # keyboard (trapezoid, two key rows + spacebar)
    ky = sy + 11
    pts = [(sx - 14, ky), (sx + 14, ky), (sx + 17, ky + 8), (sx - 17, ky + 8)]
    pygame.draw.polygon(b, B[1], pts)
    pygame.draw.polygon(b, B[2], [(sx - 13, ky + 1), (sx + 13, ky + 1), (sx + 15, ky + 6), (sx - 15, ky + 6)])
    for k in range(6):
        kx = sx - 12 + k * 4 + 1
        b.fill((78, 72, 58), (kx, ky + 2, 3, 2))
        b.fill((158, 150, 122), (kx, ky + 2, 3, 1))
    b.fill((78, 72, 58), (sx - 7, ky + 5, 14, 2))
    b.fill((158, 150, 122), (sx - 7, ky + 5, 14, 1))
    pygame.draw.lines(b, (45, 42, 35), False, [(mx + 35, my + 16), (tx - 1, ty + 13), (tx + 1, ty + 14)], 1)
    b = kit.outline(b, OUT)
    s.blit(b, (0, 0))
    return s, (sx, sy)


def build():
    sh = kit.Sheet("spr_props_m2", FAMILY, max_w=512)
    sh.meta = {"anchor": "prop world position (procedural sx, sy)",
               "upload_pc": {"frames": "upload_pc_<pulse 0..3>_<cursor 0|1>",
                             "pulse_from": "0.5+0.5*sin(t_ms*0.005)", "cursor_period_ms": 1000}}
    for key, fn in (("cone", lambda: cone(False)), ("cone_charred", lambda: cone(True)),
                    ("barrel", lambda: barrel(False)), ("barrel_charred", lambda: barrel(True)),
                    ("sign", lambda: sign(False)), ("sign_charred", lambda: sign(True)),
                    ("broken_camera", broken_camera), ("spark_box", spark_box),
                    ("puddle", puddle), ("puddle_scorch", puddle_scorch), ("soot", soot),
                    ("flare", flare)):
        surf, anc = fn()
        sh.add(key, surf, anc)
    for i, p in enumerate(PULSES):
        for c in (0, 1):
            surf, anc = upload_pc(p, c)
            sh.add("upload_pc_%d_%d" % (i, c), surf, anc, pulse=p, cursor=bool(c), duration_ms=500)
    return [sh]


if __name__ == "__main__":
    sys.exit(kit.run(FAMILY, build))
