# ------------------------------------------------------------
# cutscenes.py
# ------------------------------------------------------------

# ------------------------------------------------------------
# cutscenes.py
# ------------------------------------------------------------

# cutscenes.py
# ------------------------------------------------------------

"""Cutscene visuals and dialogue: character drawings, scene backgrounds, shot lists."""
import math
import random
import pygame
from config import *
def draw_volkov(surface, cx, foot_y, scale=1.0, facing_right=True):
    d = int(facing_right) * 2 - 1
    s = scale
    head_r = int(28 * s)
    torso_h = int(110 * s)
    torso_w = int(60 * s)
    leg_h = int(90 * s)
    leg_w = int(22 * s)
    arm_w = int(16 * s)
    arm_h = int(90 * s)
    foot_l = (cx - int(18 * s), foot_y)
    foot_r = (cx + int(18 * s), foot_y)
    hip_y = foot_y - leg_h
    sho_y = hip_y - torso_h
    head_y = sho_y - head_r - int(8 * s)
    shadow = pygame.Surface((int(80 * s), int(16 * s)), pygame.SRCALPHA)
    shadow.fill((0, 0, 0, 60))
    surface.blit(shadow, (cx - int(40 * s), foot_y - int(8 * s)))
    leg_col = (18, 18, 24)
    for lx in (cx - int(18 * s), cx + int(18 * s)):
        pygame.draw.rect(surface, leg_col, (lx - leg_w // 2, hip_y, leg_w, leg_h))
    shoe_col = (12, 10, 10)
    pygame.draw.ellipse(
        surface,
        shoe_col,
        (foot_l[0] - int(14 * s), foot_y - int(8 * s), int(28 * s), int(16 * s)),
    )
    pygame.draw.ellipse(
        surface,
        shoe_col,
        (foot_r[0] - int(14 * s), foot_y - int(8 * s), int(28 * s), int(16 * s)),
    )
    coat_col = (14, 14, 20)
    rim_col = (255, 110, 40)
    rim_pts = [
        (cx - int(torso_w // 2 + 4) * d, sho_y),
        (cx + int(torso_w // 2 + 4) * d, sho_y),
        (cx + int(torso_w // 2 + 8) * d, hip_y),
        (cx - int(torso_w // 2 + 8) * d, hip_y),
    ]
    pygame.draw.polygon(
        surface,
        (int(rim_col[0] * 0.4), int(rim_col[1] * 0.4), int(rim_col[2] * 0.4)),
        rim_pts,
    )
    coat_pts = [
        (cx - torso_w // 2, sho_y),
        (cx + torso_w // 2, sho_y),
        (cx + torso_w // 2 + int(6 * s), hip_y),
        (cx - torso_w // 2 - int(6 * s), hip_y),
    ]
    pygame.draw.polygon(surface, coat_col, coat_pts)
    pygame.draw.line(
        surface,
        (30, 28, 32),
        (cx, sho_y),
        (cx - int(8 * s) * d, sho_y + int(40 * s)),
        int(3 * s),
    )
    arm_side_x = cx + int(torso_w // 2) * d
    back_arm_x = cx - int(torso_w // 2) * d
    pygame.draw.rect(
        surface, (18, 18, 24), (back_arm_x - arm_w // 2, sho_y, arm_w, arm_h)
    )
    pygame.draw.rect(
        surface, (18, 18, 24), (arm_side_x - arm_w // 2, sho_y, arm_w, arm_h)
    )
    pygame.draw.circle(
        surface,
        (int(rim_col[0] * 0.6), int(rim_col[1] * 0.3), int(rim_col[2] * 0.1)),
        (cx + int(rim_col[0] * 0.01 * d), head_y),
        head_r + int(5 * s),
    )
    skin_col = (42, 36, 32)
    pygame.draw.circle(surface, skin_col, (cx, head_y), head_r)
    pygame.draw.arc(
        surface,
        (8, 6, 6),
        (cx - head_r, head_y - head_r, head_r * 2, head_r * 2),
        0,
        math.pi,
        int(head_r * 0.45),
    )
    eye_x = cx + int(10 * s) * d
    eye_y = head_y - int(4 * s)
    pygame.draw.circle(surface, (100, 35, 35), (eye_x, eye_y), int(4 * s))
    pygame.draw.circle(
        surface, (180, 60, 40), (eye_x + int(1 * s) * d, eye_y - int(1 * s)), int(2 * s)
    )
    cig_x = cx + int(16 * s) * d
    cig_y = head_y + int(10 * s)
    pygame.draw.line(
        surface,
        (200, 200, 200),
        (cig_x, cig_y),
        (cig_x + int(10 * s) * d, cig_y - int(2 * s)),
        int(2 * s),
    )
    if int(pygame.time.get_ticks() / 350) % 2 == 0:
        pygame.draw.circle(
            surface,
            (255, 80, 20),
            (cig_x + int(10 * s) * d, cig_y - int(2 * s)),
            int(3 * s),
        )
    ember = pygame.Surface((int(12 * s), int(12 * s)), pygame.SRCALPHA)
    pygame.draw.circle(ember, (255, 100, 30, 60), (int(6 * s), int(6 * s)), int(6 * s))
    surface.blit(ember, (cig_x + int(4 * s) * d, cig_y - int(8 * s)))
def draw_vasile(surface, cx, foot_y, scale=1.0, facing_right=True):
    d = int(facing_right) * 2 - 1
    s = scale
    head_r = int(25 * s)
    torso_h = int(112 * s)
    torso_w = int(62 * s)
    leg_h = int(92 * s)
    leg_w = int(22 * s)
    hip_y = foot_y - leg_h
    sho_y = hip_y - torso_h
    head_y = sho_y - head_r - int(8 * s)
    shadow = pygame.Surface((int(80 * s), int(16 * s)), pygame.SRCALPHA)
    shadow.fill((0, 0, 0, 60))
    surface.blit(shadow, (cx - int(40 * s), foot_y - int(8 * s)))
    leg_col = (35, 42, 55)
    for lx in (cx - int(18 * s), cx + int(18 * s)):
        pygame.draw.rect(surface, leg_col, (lx - leg_w // 2, hip_y, leg_w, leg_h))
    pygame.draw.ellipse(
        surface,
        (15, 15, 18),
        (cx - int(30 * s), foot_y - int(8 * s), int(28 * s), int(14 * s)),
    )
    pygame.draw.ellipse(
        surface,
        (15, 15, 18),
        (cx + int(2 * s), foot_y - int(8 * s), int(28 * s), int(14 * s)),
    )
    uni_col = C_KRAP_UNIFORM
    coat_pts = [
        (cx - torso_w // 2, sho_y),
        (cx + torso_w // 2, sho_y),
        (cx + torso_w // 2 + int(5 * s), hip_y),
        (cx - torso_w // 2 - int(5 * s), hip_y),
    ]
    pygame.draw.polygon(surface, uni_col, coat_pts)
    pygame.draw.line(
        surface,
        C_KRAP_BLUE,
        (cx - int(20 * s), sho_y + int(20 * s)),
        (cx + int(20 * s), sho_y + int(20 * s)),
        int(3 * s),
    )
    for i in range(3):
        px = cx + int((torso_w // 2 - 6 - i * 5) * s)
        pygame.draw.circle(
            surface, (200, 180, 80), (px, sho_y + int(8 * s)), int(2 * s)
        )
    arm_col = uni_col
    pygame.draw.rect(
        surface,
        arm_col,
        (cx - int(torso_w // 2) * d - int(8 * s), sho_y, int(16 * s), int(95 * s)),
    )
    pygame.draw.rect(
        surface,
        arm_col,
        (cx + int(torso_w // 2) * d - int(8 * s), sho_y, int(16 * s), int(95 * s)),
    )
    pygame.draw.circle(surface, (180, 155, 130), (cx, head_y), head_r)
    pygame.draw.arc(
        surface,
        (60, 50, 45),
        (cx - head_r, head_y - head_r, head_r * 2, head_r * 2),
        math.pi * 0.2,
        math.pi * 0.8,
        3,
    )
    cig_x = cx + int(14 * s) * d
    cig_y = head_y + int(8 * s)
    pygame.draw.line(
        surface,
        (220, 220, 220),
        (cig_x, cig_y),
        (cig_x + int(8 * s) * d, cig_y - int(1 * s)),
        int(2 * s),
    )
    if int(pygame.time.get_ticks() / 350) % 2 == 0:
        pygame.draw.circle(
            surface,
            (255, 80, 20),
            (cig_x + int(8 * s) * d, cig_y - int(1 * s)),
            int(2 * s),
        )
    eye_x = cx + int(8 * s) * d
    eye_y = head_y - int(3 * s)
    pygame.draw.circle(surface, (40, 50, 70), (eye_x, eye_y), int(2 * s))
def draw_biribel(
    surface, cx, foot_y, scale=1.0, facing_right=True, in_silhouette=False
):
    d = int(facing_right) * 2 - 1
    s = scale
    head_r = int(24 * s)
    torso_h = int(108 * s)
    torso_w = int(58 * s)
    leg_h = int(90 * s)
    leg_w = int(22 * s)
    hip_y = foot_y - leg_h
    sho_y = hip_y - torso_h
    head_y = sho_y - head_r - int(8 * s)
    shadow = pygame.Surface((int(80 * s), int(16 * s)), pygame.SRCALPHA)
    shadow.fill((0, 0, 0, 60))
    surface.blit(shadow, (cx - int(40 * s), foot_y - int(8 * s)))
    if in_silhouette:
        for lx in (cx - int(15 * s), cx + int(15 * s)):
            pygame.draw.rect(
                surface, (8, 8, 12), (lx - leg_w // 2, hip_y, leg_w, leg_h)
            )
        coat_pts = [
            (cx - torso_w // 2, sho_y),
            (cx + torso_w // 2, sho_y),
            (cx + torso_w // 2 + int(4 * s), hip_y),
            (cx - torso_w // 2 - int(4 * s), hip_y),
        ]
        pygame.draw.polygon(surface, (8, 8, 12), coat_pts)
        pygame.draw.rect(
            surface,
            (5, 5, 8),
            (cx - int(22 * s), sho_y + int(10 * s), int(44 * s), int(60 * s)),
        )
        pygame.draw.circle(surface, (8, 8, 12), (cx, head_y), head_r)
        pygame.draw.arc(
            surface,
            (3, 3, 6),
            (
                cx - head_r - int(3 * s),
                head_y - head_r - int(2 * s),
                (head_r + int(3 * s)) * 2,
                head_r + int(6 * s),
            ),
            0,
            math.pi,
            int(head_r * 0.5),
        )
        return
    leg_col = (30, 35, 40)
    for lx in (cx - int(15 * s), cx + int(15 * s)):
        pygame.draw.rect(surface, leg_col, (lx - leg_w // 2, hip_y, leg_w, leg_h))
    for lx in (cx - int(15 * s), cx + int(15 * s)):
        pygame.draw.rect(
            surface,
            (15, 18, 22),
            (lx - leg_w // 2, hip_y + int(40 * s), leg_w, int(14 * s)),
        )
    pygame.draw.ellipse(
        surface,
        (12, 12, 14),
        (cx - int(28 * s), foot_y - int(8 * s), int(26 * s), int(14 * s)),
    )
    pygame.draw.ellipse(
        surface,
        (12, 12, 14),
        (cx + int(2 * s), foot_y - int(8 * s), int(26 * s), int(14 * s)),
    )
    uni_col = (40, 50, 45)
    coat_pts = [
        (cx - torso_w // 2, sho_y),
        (cx + torso_w // 2, sho_y),
        (cx + torso_w // 2 + int(4 * s), hip_y),
        (cx - torso_w // 2 - int(4 * s), hip_y),
    ]
    pygame.draw.polygon(surface, uni_col, coat_pts)
    vest_col = (28, 35, 30)
    pygame.draw.rect(
        surface,
        vest_col,
        (cx - int(24 * s), sho_y + int(15 * s), int(48 * s), int(55 * s)),
    )
    for i in range(3):
        px = cx - int(20 * s) + i * int(14 * s)
        pygame.draw.rect(
            surface, (20, 25, 22), (px, sho_y + int(30 * s), int(10 * s), int(18 * s))
        )
        pygame.draw.line(
            surface,
            (15, 18, 16),
            (px, sho_y + int(30 * s)),
            (px + int(10 * s), sho_y + int(30 * s)),
            1,
        )
    pygame.draw.rect(
        surface,
        C_KRAP_BLUE,
        (cx + int(8 * s) * d, sho_y + int(18 * s), int(10 * s), int(8 * s)),
    )
    pygame.draw.rect(
        surface,
        (200, 200, 200),
        (cx + int(8 * s) * d, sho_y + int(18 * s), int(10 * s), int(8 * s)),
        1,
    )
    arm_col = uni_col
    pygame.draw.rect(
        surface,
        arm_col,
        (cx - int(torso_w // 2) * d - int(7 * s), sho_y, int(14 * s), int(90 * s)),
    )
    pygame.draw.rect(
        surface,
        arm_col,
        (cx + int(torso_w // 2) * d - int(7 * s), sho_y, int(14 * s), int(90 * s)),
    )
    pygame.draw.circle(surface, (190, 165, 140), (cx, head_y), head_r)
    pygame.draw.arc(
        surface,
        (25, 30, 28),
        (
            cx - head_r - int(2 * s),
            head_y - head_r - int(2 * s),
            (head_r + int(2 * s)) * 2,
            head_r + int(4 * s),
        ),
        0,
        math.pi,
        int(head_r * 0.5),
    )
    pygame.draw.ellipse(
        surface,
        (25, 30, 28),
        (
            cx - head_r - int(2 * s),
            head_y - int(6 * s),
            (head_r + int(2 * s)) * 2,
            int(8 * s),
        ),
    )
    eye_x = cx + int(8 * s) * d
    eye_y = head_y - int(2 * s)
    pygame.draw.circle(surface, (35, 45, 55), (eye_x, eye_y), int(2 * s))
    pygame.draw.arc(
        surface,
        (130, 105, 85),
        (
            cx - head_r + int(2 * s),
            head_y + int(2 * s),
            head_r * 2 - int(4 * s),
            head_r,
        ),
        math.pi * 1.1,
        math.pi * 1.9,
        2,
    )
def draw_old_fisherman(surface, cx, foot_y, scale=1.0, facing_right=True):
    d = int(facing_right) * 2 - 1
    s = scale
    head_r = int(22 * s)
    torso_h = int(95 * s)
    torso_w = int(54 * s)
    leg_h = int(80 * s)
    leg_w = int(20 * s)
    hip_y = foot_y - leg_h
    sho_y = hip_y - torso_h
    head_y = sho_y - head_r - int(8 * s)
    shadow = pygame.Surface((int(70 * s), int(14 * s)), pygame.SRCALPHA)
    shadow.fill((0, 0, 0, 55))
    surface.blit(shadow, (cx - int(35 * s), foot_y - int(7 * s)))
    leg_col = (50, 45, 38)
    for lx in (cx - int(14 * s), cx + int(14 * s)):
        pygame.draw.rect(surface, leg_col, (lx - leg_w // 2, hip_y, leg_w, leg_h))
    pygame.draw.ellipse(
        surface,
        (25, 20, 16),
        (cx - int(26 * s), foot_y - int(7 * s), int(24 * s), int(12 * s)),
    )
    pygame.draw.ellipse(
        surface,
        (25, 20, 16),
        (cx + int(2 * s), foot_y - int(7 * s), int(24 * s), int(12 * s)),
    )
    coat_col = (90, 80, 50)
    coat_pts = [
        (cx - torso_w // 2 - int(4 * s), sho_y),
        (cx + torso_w // 2 + int(4 * s), sho_y),
        (cx + torso_w // 2 + int(10 * s), hip_y),
        (cx - torso_w // 2 - int(10 * s), hip_y),
    ]
    pygame.draw.polygon(surface, coat_col, coat_pts)
    pygame.draw.line(
        surface,
        (110, 100, 65),
        (cx - int(15 * s), sho_y + int(10 * s)),
        (cx - int(20 * s), hip_y - int(10 * s)),
        2,
    )
    pygame.draw.line(
        surface,
        (110, 100, 65),
        (cx + int(15 * s), sho_y + int(10 * s)),
        (cx + int(20 * s), hip_y - int(10 * s)),
        2,
    )
    pygame.draw.rect(
        surface,
        coat_col,
        (
            cx - int(torso_w // 2) - int(6 * s),
            sho_y + int(5 * s),
            int(14 * s),
            int(85 * s),
        ),
    )
    pygame.draw.rect(
        surface,
        coat_col,
        (
            cx + int(torso_w // 2) - int(6 * s),
            sho_y + int(5 * s),
            int(14 * s),
            int(85 * s),
        ),
    )
    pygame.draw.circle(surface, (170, 140, 115), (cx, head_y), head_r)
    pygame.draw.arc(
        surface,
        (200, 200, 195),
        (cx - head_r, head_y - int(2 * s), head_r * 2, head_r + int(6 * s)),
        math.pi,
        math.pi * 2,
        int(head_r * 0.7),
    )
    pygame.draw.ellipse(
        surface,
        (60, 55, 45),
        (
            cx - head_r - int(6 * s),
            head_y - int(18 * s),
            (head_r + int(6 * s)) * 2,
            int(14 * s),
        ),
    )
    pygame.draw.rect(
        surface,
        (60, 55, 45),
        (
            cx - head_r - int(2 * s),
            head_y - int(16 * s),
            (head_r + int(2 * s)) * 2,
            int(10 * s),
        ),
    )
    eye_x = cx + int(7 * s) * d
    eye_y = head_y - int(2 * s)
    pygame.draw.line(
        surface,
        (30, 25, 20),
        (eye_x - int(2 * s), eye_y),
        (eye_x + int(2 * s), eye_y),
        int(2 * s),
    )
def draw_commander(surface, cx, foot_y, scale=1.0, facing_right=True):
    d = int(facing_right) * 2 - 1
    s = scale
    head_r = int(26 * s)
    torso_h = int(115 * s)
    torso_w = int(65 * s)
    leg_h = int(95 * s)
    leg_w = int(24 * s)
    hip_y = foot_y - leg_h
    sho_y = hip_y - torso_h
    head_y = sho_y - head_r - int(8 * s)
    shadow = pygame.Surface((int(80 * s), int(16 * s)), pygame.SRCALPHA)
    shadow.fill((0, 0, 0, 60))
    surface.blit(shadow, (cx - int(40 * s), foot_y - int(8 * s)))
    leg_col = (20, 22, 28)
    for lx in (cx - int(18 * s), cx + int(18 * s)):
        pygame.draw.rect(surface, leg_col, (lx - leg_w // 2, hip_y, leg_w, leg_h))
    pygame.draw.ellipse(
        surface,
        (10, 10, 12),
        (cx - int(30 * s), foot_y - int(8 * s), int(28 * s), int(14 * s)),
    )
    pygame.draw.ellipse(
        surface,
        (10, 10, 12),
        (cx + int(2 * s), foot_y - int(8 * s), int(28 * s), int(14 * s)),
    )
    uni_col = (30, 32, 38)
    coat_pts = [
        (cx - torso_w // 2, sho_y),
        (cx + torso_w // 2, sho_y),
        (cx + torso_w // 2 + int(5 * s), hip_y),
        (cx - torso_w // 2 - int(5 * s), hip_y),
    ]
    pygame.draw.polygon(surface, uni_col, coat_pts)
    pygame.draw.rect(
        surface,
        (160, 30, 30),
        (
            cx + int(torso_w // 2 - 8) * d - int(8 * s),
            sho_y + int(20 * s),
            int(16 * s),
            int(20 * s),
        ),
    )
    pygame.draw.polygon(
        surface,
        (140, 20, 20),
        [
            (cx - int(4 * s), sho_y + int(2 * s)),
            (cx + int(4 * s), sho_y + int(2 * s)),
            (cx + int(3 * s), sho_y + int(60 * s)),
            (cx - int(3 * s), sho_y + int(60 * s)),
        ],
    )
    arm_col = uni_col
    pygame.draw.rect(
        surface,
        arm_col,
        (cx - int(torso_w // 2) * d - int(8 * s), sho_y, int(16 * s), int(95 * s)),
    )
    pygame.draw.rect(
        surface,
        arm_col,
        (cx + int(torso_w // 2) * d - int(8 * s), sho_y, int(16 * s), int(95 * s)),
    )
    pygame.draw.circle(surface, (175, 145, 120), (cx, head_y), head_r)
    pygame.draw.arc(
        surface,
        (15, 12, 10),
        (cx - head_r, head_y - head_r, head_r * 2, head_r * 2),
        0,
        math.pi,
        int(head_r * 0.5),
    )
    pygame.draw.ellipse(
        surface,
        (15, 12, 10),
        (cx - head_r, head_y - int(8 * s), head_r * 2, int(10 * s)),
    )
    eye_x = cx + int(10 * s) * d
    eye_y = head_y - int(3 * s)
    pygame.draw.circle(surface, (25, 30, 35), (eye_x, eye_y), int(3 * s))
# ─────────────────────────────────────────────
# SCENE DRAWERS
# ─────────────────────────────────────────────
def draw_factory(surface, t):
    ground_y = SCENE_BOT - 60
    draw_sky_gradient(surface, (18, 20, 26), (28, 24, 22))
    fac_left = 150
    fac_right = 850
    fac_top = SCENE_TOP + 80
    fac_h = ground_y - fac_top
    pygame.draw.rect(
        surface, (22, 26, 32), (fac_left, fac_top, fac_right - fac_left, fac_h)
    )
    for i in range(fac_left, fac_right, 12):
        shade = 28 + (i % 24 > 12) * 4
        pygame.draw.line(
            surface, (shade, shade + 2, shade + 6), (i, fac_top), (i, ground_y), 1
        )
    for wx in range(fac_left + 40, fac_right - 40, 90):
        for wy_off in range(0, 3):
            wy = fac_top + 30 + wy_off * 70
            is_lit = (wx // 90 + wy_off) % 3 != 0
            win_c = (55, 50, 32) if is_lit else (18, 20, 24)
            pygame.draw.rect(surface, win_c, (wx, wy, 50, 45))
            pygame.draw.rect(surface, (18, 20, 26), (wx, wy, 50, 45), 2)
            if is_lit:
                glow = pygame.Surface((54, 49), pygame.SRCALPHA)
                glow.fill((60, 55, 30, 25))
                surface.blit(glow, (wx - 2, wy - 2))
    for chx, chh in [(620, 130), (680, 160), (750, 110)]:
        pygame.draw.rect(surface, (26, 28, 34), (chx, fac_top - chh, 28, chh))
        for pi in range(4):
            poff = (t // 20 + pi * 15) % 80
            palpha = max(0, 70 - poff)
            pr = 15 + pi * 4
            psurf = pygame.Surface((pr * 2, pr * 2), pygame.SRCALPHA)
            pygame.draw.circle(psurf, (35, 38, 44, palpha), (pr, pr), pr)
            surface.blit(psurf, (chx + 14 - pr, fac_top - chh - 20 - poff))
    pygame.draw.rect(surface, (15, 16, 18), (0, ground_y, WIDTH, SCENE_BOT - ground_y))
def draw_oil_rig(surface, x, ground_y, t, scale=1.0, burning=False, lights_only=False):
    s = scale
    base_w = int(120 * s)
    base_h = int(20 * s)
    deck_y = ground_y - int(60 * s)
    tower_h = int(100 * s)
    tx = x
    ty = deck_y - tower_h
    if not lights_only:
        leg_col = (45, 48, 55)
        deck_col = (60, 65, 75)
        tower_col = (55, 60, 70)
        for lx in (-base_w // 2 + 10, base_w // 2 - 10):
            pygame.draw.line(
                surface,
                leg_col,
                (x + lx, deck_y + base_h),
                (x + lx, ground_y + 20),
                int(4 * s),
            )
        pygame.draw.rect(surface, deck_col, (x - base_w // 2, deck_y, base_w, base_h))
        pygame.draw.line(
            surface, tower_col, (tx - int(20 * s), deck_y), (tx, ty), int(3 * s)
        )
        pygame.draw.line(
            surface, tower_col, (tx + int(20 * s), deck_y), (tx, ty), int(3 * s)
        )
        for i in range(4):
            ratio = i / 4.0
            ly = deck_y - int(tower_h * ratio)
            lw = int(20 * s * (1 - ratio))
            pygame.draw.line(
                surface, tower_col, (tx - lw, ly), (tx + lw, ly), int(2 * s)
            )
        pygame.draw.circle(surface, (120, 100, 80), (tx, ty), int(4 * s))
    else:
        if (t // 18) % 2 == 0:
            pygame.draw.circle(surface, (255, 50, 50), (tx, ty), int(6 * s))
            beacon_glow = pygame.Surface((int(36 * s), int(36 * s)), pygame.SRCALPHA)
            pygame.draw.circle(
                beacon_glow, (255, 50, 50, 75), (int(18 * s), int(18 * s)), int(18 * s)
            )
            surface.blit(beacon_glow, (tx - int(18 * s), ty - int(18 * s)))
        for lx_off in range(-base_w // 2 + 15, base_w // 2 - 10, int(25 * s)):
            pygame.draw.circle(
                surface,
                (255, 200, 100),
                (x + lx_off, deck_y + base_h // 2),
                int(2.5 * s),
            )
            deck_glow = pygame.Surface((int(12 * s), int(12 * s)), pygame.SRCALPHA)
            pygame.draw.circle(
                deck_glow, (255, 200, 100, 50), (int(6 * s), int(6 * s)), int(6 * s)
            )
            surface.blit(
                deck_glow, (x + lx_off - int(6 * s), deck_y + base_h // 2 - int(6 * s))
            )
        spot_surf = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        beam_len = 220 * s
        phase_offset = x * 0.13
        beam_angle = math.sin(t * 0.02 + phase_offset) * 0.5 - math.pi / 2
        end_cx = x + math.cos(beam_angle) * beam_len
        end_cy = deck_y + math.sin(beam_angle) * beam_len
        perp_angle = beam_angle + math.pi / 2
        cone_half_w = 30 * s
        bx1 = end_cx - math.cos(perp_angle) * cone_half_w
        by1 = end_cy - math.sin(perp_angle) * cone_half_w
        bx2 = end_cx + math.cos(perp_angle) * cone_half_w
        by2 = end_cy + math.sin(perp_angle) * cone_half_w
        pygame.draw.polygon(
            spot_surf, (255, 255, 220, 20), [(x, deck_y), (bx1, by1), (bx2, by2)]
        )
        surface.blit(spot_surf, (0, 0))
        if burning:
            fire_x = x + int(math.sin(t * 0.01) * 5)
            fire_y = deck_y - int(5 * s)
            for ri, (rc, ra) in enumerate([(255, 180), (220, 130), (160, 80)]):
                rr = max(2, int((15 - ri * 4) * s))
                pygame.draw.circle(
                    surface,
                    (rc, max(0, 80 - ri * 20), 10, ra),
                    (fire_x, fire_y - ri * int(5 * s)),
                    rr,
                )
            for pi in range(5):
                poff = (t // 15 + pi * 12) % 80
                palpha = max(0, 100 - poff)
                pr = int((10 + pi * 3) * s)
                psurf = pygame.Surface((pr * 2, pr * 2), pygame.SRCALPHA)
                pygame.draw.circle(psurf, (40, 40, 45, palpha), (pr, pr), pr)
                surface.blit(
                    psurf,
                    (fire_x - pr + random.randint(-3, 3), deck_y - int(40 * s) - poff),
                )
def draw_propaganda_poster(surface, x, y, w, h, defaced=False):
    pygame.draw.rect(surface, (200, 180, 140), (x, y, w, h))
    pygame.draw.rect(surface, (60, 50, 40), (x, y, w, h), 2)
    face_x = x + w // 2
    face_y = y + h // 3
    face_r = min(w, h) // 6
    pygame.draw.circle(surface, (40, 30, 25), (face_x, face_y), face_r)
    pygame.draw.rect(
        surface, (40, 30, 25), (face_x - face_r, face_y, face_r * 2, face_r * 2)
    )
    for i in range(3):
        ty = y + h * 2 // 3 + i * 8
        pygame.draw.rect(surface, (60, 50, 40), (x + 10, ty, w - 20, 4))
    pygame.draw.rect(surface, (160, 30, 30), (x, y, w, 12))
    if defaced:
        pygame.draw.circle(
            surface, (15, 15, 15), (face_x - 4, face_y - 2), face_r + 2, 3
        )
        pygame.draw.line(
            surface, (15, 15, 15), (x + 4, y + 4), (x + w - 4, y + h - 4), 3
        )
        tag = font_terminal_small.render("MARU", True, (15, 15, 15))
        surface.blit(tag, (x + w // 2 - tag.get_width() // 2, y + h - 18))
def draw_mag_graffiti(surface, x, y, scale=1.0):
    s = scale
    pts = [
        (x, y - int(8 * s)),
        (x - int(6 * s), y - int(12 * s)),
        (x - int(10 * s), y - int(2 * s)),
        (x - int(8 * s), y + int(8 * s)),
        (x, y + int(12 * s)),
        (x + int(8 * s), y + int(8 * s)),
        (x + int(10 * s), y - int(2 * s)),
        (x + int(6 * s), y - int(12 * s)),
    ]
    pygame.draw.polygon(surface, (15, 15, 15), pts)
    pygame.draw.circle(
        surface, (180, 30, 30), (x - int(3 * s), y - int(2 * s)), int(1 * s)
    )
    pygame.draw.circle(
        surface, (180, 30, 30), (x + int(3 * s), y - int(2 * s)), int(1 * s)
    )
def draw_van_exterior(surface, t):
    """Simple cinematic exterior shot before the van briefing."""
    draw_sky_gradient(surface, (10, 12, 18), (24, 18, 22))
    road_y = SCENE_BOT - 150
    # Distant slum silhouettes
    rng = random.Random(91)
    for bx in range(-20, WIDTH + 40, 56):
        bh = rng.randint(30, 105)
        col = rng.choice([(13, 15, 20), (16, 17, 22), (18, 16, 18)])
        pygame.draw.rect(surface, col, (bx, road_y - bh, 48, bh))
        if rng.random() > 0.45:
            pygame.draw.rect(surface, (150, 115, 60), (bx + 16, road_y - bh + 16, 5, 6))
    # Wet road
    pygame.draw.rect(surface, (10, 12, 15), (0, road_y, WIDTH, SCENE_BOT - road_y))
    for y in range(road_y + 16, SCENE_BOT, 24):
        pygame.draw.line(surface, (22, 28, 36), (0, y), (WIDTH, y), 1)
    # Reflections
    for i in range(12):
        rx = (i * 97 + int(t * 0.08)) % WIDTH
        rw = 30 + (i % 3) * 20
        col = [(40, 75, 110), (90, 65, 45), (120, 45, 35)][i % 3]
        refl = pygame.Surface((rw, 8), pygame.SRCALPHA)
        pygame.draw.ellipse(refl, (*col, 35), (0, 0, rw, 8))
        surface.blit(refl, (rx, road_y + 25 + (i % 5) * 16))
    # Van side silhouette
    van_x = WIDTH // 2 - 170 + int(math.sin(t * 0.004) * 2)
    van_y = road_y - 58
    # Shadow
    shadow = pygame.Surface((350, 55), pygame.SRCALPHA)
    pygame.draw.ellipse(shadow, (0, 0, 0, 105), (0, 10, 350, 36))
    surface.blit(shadow, (van_x - 18, van_y + 45))
    # Body
    pygame.draw.rect(surface, (15, 17, 20), (van_x, van_y, 310, 72), border_radius=5)
    pygame.draw.rect(surface, (40, 46, 54), (van_x, van_y, 310, 72), 2, border_radius=5)
    # Cab slope / hood
    pygame.draw.polygon(
        surface,
        (18, 22, 27),
        [
            (van_x + 230, van_y),
            (van_x + 290, van_y + 12),
            (van_x + 310, van_y + 45),
            (van_x + 230, van_y + 45),
        ],
    )
    pygame.draw.polygon(
        surface,
        (42, 48, 56),
        [
            (van_x + 230, van_y),
            (van_x + 290, van_y + 12),
            (van_x + 310, van_y + 45),
            (van_x + 230, van_y + 45),
        ],
        1,
    )
    # Windows
    pygame.draw.rect(surface, (22, 34, 46), (van_x + 236, van_y + 10, 42, 26), border_radius=2)
    pygame.draw.rect(surface, (18, 28, 38), (van_x + 90, van_y + 12, 48, 24), border_radius=2)
    pygame.draw.line(surface, (80, 100, 120), (van_x + 240, van_y + 13), (van_x + 272, van_y + 13), 1)
    # KRAP stripe
    pygame.draw.rect(surface, C_KRAP_BLUE, (van_x + 24, van_y + 22, 185, 7))
    pygame.draw.rect(surface, (220, 220, 225), (van_x + 24, van_y + 30, 185, 2))
    krap = font_terminal_small.render("KRAP", True, (190, 210, 230))
    surface.blit(krap, (van_x + 38, van_y + 40))
    # Lights
    pygame.draw.rect(surface, (190, 40, 35), (van_x - 4, van_y + 28, 6, 14))
    pygame.draw.ellipse(surface, (220, 210, 140), (van_x + 304, van_y + 24, 12, 10))
    # Wheels
    for wx in (van_x + 62, van_x + 235):
        pygame.draw.circle(surface, (4, 5, 7), (wx, van_y + 72), 22)
        pygame.draw.circle(surface, (36, 40, 45), (wx, van_y + 72), 10)
        pygame.draw.circle(surface, (15, 16, 18), (wx, van_y + 72), 4)
    # Light beam
    beam = pygame.Surface((250, 70), pygame.SRCALPHA)
    pygame.draw.polygon(beam, (220, 210, 150, 25), [(0, 25), (235, 0), (235, 55), (0, 38)])
    surface.blit(beam, (van_x + 306, van_y + 12))
    # Foreground rain
    rain_layer = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
    rng_r = random.Random(44)
    for i in range(90):
        rx = (rng_r.randint(0, WIDTH) + int(t * 1.9)) % WIDTH
        ry = SCENE_TOP + ((rng_r.randint(0, SCENE_H) + int(t * 5.0)) % SCENE_H)
        pygame.draw.line(rain_layer, (135, 155, 190, rng_r.randint(25, 65)), (rx, ry), (rx - 5, ry + 20), 1)
    surface.blit(rain_layer, (0, 0))
    # Caption-style location tag
    tag = font_location_sub.render("ACARISTAN CITY — SLUM DISTRICT", True, (130, 150, 170))
    bg = pygame.Surface((tag.get_width() + 24, tag.get_height() + 10), pygame.SRCALPHA)
    bg.fill((0, 0, 0, 150))
    surface.blit(bg, (42, SCENE_TOP + 24))
    surface.blit(tag, (54, SCENE_TOP + 29))
def draw_van_interior(surface, t):
    """Cinematic but still simple/pixel-style KRAP van interior."""
    surface.fill((8, 8, 10))
    # Rear wall gradient
    for y in range(SCENE_TOP, SCENE_BOT):
        p = (y - SCENE_TOP) / max(1, SCENE_H)
        r = int(17 + p * 10)
        g = int(13 + p * 7)
        b = int(14 + p * 8)
        pygame.draw.line(surface, (r, g, b), (0, y), (WIDTH, y))
    # Metal wall panel lines
    for x in range(80, WIDTH - 80, 96):
        pygame.draw.line(surface, (26, 22, 24), (x, SCENE_TOP + 10), (x, SCENE_BOT - 90), 1)
    for y in range(SCENE_TOP + 50, SCENE_BOT - 90, 48):
        pygame.draw.line(surface, (22, 18, 20), (40, y), (WIDTH - 40, y), 1)
    # Rear door seams
    pygame.draw.line(surface, (36, 30, 32), (WIDTH // 2, SCENE_TOP + 20), (WIDTH // 2, SCENE_BOT - 92), 2)
    pygame.draw.rect(surface, (28, 24, 26), (60, SCENE_TOP + 40, WIDTH - 120, SCENE_H - 155), 2)
    # Overhead red cabin light, softer and less empty
    lamp_x = WIDTH // 2 - 95
    lamp_y = SCENE_TOP + 28
    pygame.draw.rect(surface, (145, 28, 30), (lamp_x, lamp_y, 190, 7))
    glow = pygame.Surface((360, 120), pygame.SRCALPHA)
    for r in range(160, 0, -8):
        a = int(20 * (1 - r / 160))
        pygame.draw.ellipse(glow, (180, 30, 35, a), (180 - r, 45 - r // 3, r * 2, r))
    surface.blit(glow, (WIDTH // 2 - 180, SCENE_TOP + 0))
    # Right window with moving city/rain outside
    win_x = WIDTH - 310
    win_y = SCENE_TOP + 70
    win_w = 220
    win_h = 180
    pygame.draw.rect(surface, (7, 9, 13), (win_x, win_y, win_w, win_h))
    pygame.draw.rect(surface, (42, 34, 32), (win_x - 6, win_y - 6, win_w + 12, win_h + 12), 5)
    # Passing colored lights
    for i in range(16):
        lx = win_x + ((i * 41 + int(t * 0.7)) % win_w)
        ly = win_y + 20 + (i * 23) % (win_h - 40)
        col = [(150, 80, 55), (80, 95, 130), (170, 130, 55)][i % 3]
        pygame.draw.rect(surface, col, (lx, ly, 22, 4))
    # Window rain
    for i in range(18):
        rx = win_x + ((i * 29 + int(t * 1.1)) % win_w)
        ry = win_y + ((i * 47 + int(t * 2.8)) % win_h)
        pygame.draw.line(surface, (140, 150, 175), (rx, ry), (rx - 2, ry + 18), 1)
    # Tactical map board / route chart
    board_x = WIDTH - 560
    board_y = SCENE_TOP + 82
    board_w = 170
    board_h = 140
    pygame.draw.rect(surface, (12, 14, 18), (board_x, board_y, board_w, board_h))
    pygame.draw.rect(surface, (45, 38, 32), (board_x, board_y, board_w, board_h), 3)
    # Route lines
    route_cols = [(120, 70, 60), (95, 105, 135), (130, 95, 45)]
    pts = [
        (board_x + 22, board_y + 100),
        (board_x + 48, board_y + 82),
        (board_x + 68, board_y + 92),
        (board_x + 96, board_y + 58),
        (board_x + 120, board_y + 66),
        (board_x + 140, board_y + 32),
    ]
    for i in range(len(pts) - 1):
        pygame.draw.line(surface, route_cols[i % len(route_cols)], pts[i], pts[i + 1], 3)
    pygame.draw.circle(surface, C_ORANGE, pts[-1], 4)
    pygame.draw.rect(surface, (70, 50, 30), (board_x + board_w - 5, board_y + 80, 14, 5))
    # Floor / foreground
    floor_y = SCENE_BOT - 95
    pygame.draw.rect(surface, (10, 10, 12), (0, floor_y, WIDTH, SCENE_BOT - floor_y))
    for sx in range(0, WIDTH, 32):
        pygame.draw.line(surface, (18, 18, 20), (sx, floor_y), (sx + 12, SCENE_BOT), 1)
    # Benches
    pygame.draw.rect(surface, (18, 16, 16), (40, floor_y - 35, 260, 48), border_radius=4)
    pygame.draw.rect(surface, (28, 24, 22), (40, floor_y - 35, 260, 8), border_radius=3)
    pygame.draw.rect(surface, (18, 16, 16), (WIDTH - 360, floor_y - 35, 300, 48), border_radius=4)
    pygame.draw.rect(surface, (28, 24, 22), (WIDTH - 360, floor_y - 35, 300, 8), border_radius=3)
    # Gear crates
    pygame.draw.rect(surface, (55, 58, 48), (325, floor_y - 52, 86, 46), border_radius=3)
    pygame.draw.rect(surface, (85, 88, 72), (325, floor_y - 52, 86, 46), 2, border_radius=3)
    krap = font_terminal_small.render("KRAP", True, C_KRAP_BLUE)
    surface.blit(krap, (350, floor_y - 38))
    pygame.draw.rect(surface, (70, 54, 38), (430, floor_y - 44, 72, 38), border_radius=2)
    pygame.draw.rect(surface, (45, 32, 22), (430, floor_y - 44, 72, 38), 2, border_radius=2)
    # Character rim-light zones
    vasile_glow = pygame.Surface((160, 220), pygame.SRCALPHA)
    pygame.draw.ellipse(vasile_glow, (100, 160, 220, 28), (0, 20, 160, 180))
    surface.blit(vasile_glow, (75, floor_y - 215))
    biribel_glow = pygame.Surface((180, 240), pygame.SRCALPHA)
    pygame.draw.ellipse(biribel_glow, (180, 190, 200, 18), (0, 20, 180, 200))
    surface.blit(biribel_glow, (WIDTH // 2 + 50, floor_y - 230))
    # Characters larger and better staged
    draw_vasile(surface, 160, floor_y + 2, scale=0.72, facing_right=True)
    draw_biribel(surface, WIDTH // 2 + 150, floor_y + 2, scale=0.76, facing_right=False, in_silhouette=True)
    # Foreground silhouettes: radio / rifle case, gives cramped depth
    pygame.draw.rect(surface, (5, 6, 8), (WIDTH // 2 - 70, SCENE_BOT - 112, 140, 28), border_radius=3)
    pygame.draw.line(surface, (12, 14, 16), (WIDTH // 2 - 52, SCENE_BOT - 98), (WIDTH // 2 + 50, SCENE_BOT - 98), 3)
    pygame.draw.circle(surface, (18, 20, 24), (WIDTH // 2 + 58, SCENE_BOT - 98), 6)
    # Subtle red wash
    red_glow = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
    red_glow.fill((60, 10, 12, 22))
    surface.blit(red_glow, (0, 0))
# ── Handoff insert-shot helpers (van cutscene) ──
def _ease_cutscene(t):
    t = max(0.0, min(1.0, t))
    return 1.0 - (1.0 - t) ** 3
def _lerp_cutscene(a, b, t):
    return a + (b - a) * t
def _ca(v):
    """Clamp an alpha value to the valid pygame range 0..255."""
    return max(0, min(255, int(v)))
def _draw_handoff_pistol(surface, cx, cy, scale=1.0, angle=-8):
    s = scale
    w, h = int(150 * s), int(80 * s)
    gun = pygame.Surface((w, h), pygame.SRCALPHA)
    def R(x, y, ww, hh):
        return pygame.Rect(int(x * s), int(y * s), int(ww * s), int(hh * s))
    pygame.draw.rect(gun, (52, 56, 62), R(32, 24, 72, 15), border_radius=int(3 * s))
    pygame.draw.rect(gun, (18, 20, 24), R(32, 24, 72, 15), int(2 * s), border_radius=int(3 * s))
    pygame.draw.rect(gun, (70, 74, 80), R(98, 28, 24, 7), border_radius=int(2 * s))
    pygame.draw.circle(gun, (8, 8, 10), (int(123 * s), int(31 * s)), int(4 * s))
    pygame.draw.rect(gun, (28, 30, 34), R(36, 38, 58, 13), border_radius=int(3 * s))
    grip_pts = [(int(48 * s), int(48 * s)), (int(74 * s), int(48 * s)),
                (int(82 * s), int(73 * s)), (int(56 * s), int(75 * s))]
    pygame.draw.polygon(gun, (22, 23, 25), grip_pts)
    pygame.draw.polygon(gun, (10, 11, 13), grip_pts, int(1 * s))
    pygame.draw.circle(gun, (16, 17, 19), (int(83 * s), int(49 * s)), int(8 * s), int(2 * s))
    pygame.draw.line(gun, (105, 112, 120), (int(38 * s), int(27 * s)), (int(93 * s), int(27 * s)), int(1 * s))
    pygame.draw.circle(gun, (180, 35, 35), (int(82 * s), int(22 * s)), int(2 * s))
    rot = pygame.transform.rotate(gun, angle)
    rect = rot.get_rect(center=(int(cx), int(cy)))
    surface.blit(rot, rect)
def _draw_handoff_molotov(surface, cx, cy, scale=1.0, angle=0):
    """Unlit molotov: glass bottle, amber fuel, rag stuffed in the neck."""
    s = scale
    w, h = int(64 * s), int(150 * s)
    bottle = pygame.Surface((w, h), pygame.SRCALPHA)
    bx = w // 2
    rag_col = (196, 178, 130)
    rag_dark = (150, 132, 92)
    pygame.draw.polygon(bottle, rag_col, [
        (bx - int(4 * s), int(18 * s)),
        (bx - int(16 * s), int(34 * s)),
        (bx - int(11 * s), int(40 * s)),
        (bx - int(1 * s), int(26 * s)),
    ])
    pygame.draw.line(bottle, rag_dark,
                     (bx - int(6 * s), int(22 * s)),
                     (bx - int(14 * s), int(36 * s)), max(1, int(1 * s)))
    pygame.draw.ellipse(bottle, rag_col,
                        (bx - int(8 * s), int(10 * s), int(16 * s), int(12 * s)))
    pygame.draw.ellipse(bottle, rag_dark,
                        (bx - int(8 * s), int(10 * s), int(16 * s), int(12 * s)), max(1, int(1 * s)))
    glass = (96, 66, 30)
    glass_dark = (52, 36, 18)
    pygame.draw.rect(bottle, glass_dark,
                     (bx - int(7 * s), int(18 * s), int(14 * s), int(26 * s)),
                     border_radius=int(3 * s))
    pygame.draw.rect(bottle, glass,
                     (bx - int(5 * s), int(20 * s), int(10 * s), int(23 * s)),
                     border_radius=int(3 * s))
    pygame.draw.polygon(bottle, glass_dark, [
        (bx - int(7 * s), int(42 * s)),
        (bx + int(7 * s), int(42 * s)),
        (bx + int(20 * s), int(62 * s)),
        (bx - int(20 * s), int(62 * s)),
    ])
    pygame.draw.polygon(bottle, glass, [
        (bx - int(5 * s), int(44 * s)),
        (bx + int(5 * s), int(44 * s)),
        (bx + int(17 * s), int(62 * s)),
        (bx - int(17 * s), int(62 * s)),
    ])
    body_rect = pygame.Rect(bx - int(20 * s), int(60 * s), int(40 * s), int(78 * s))
    pygame.draw.rect(bottle, glass_dark, body_rect, border_radius=int(8 * s))
    inner = body_rect.inflate(int(-6 * s), int(-6 * s))
    pygame.draw.rect(bottle, glass, inner, border_radius=int(7 * s))
    fuel_h = int(inner.height * 0.65)
    fuel_rect = pygame.Rect(inner.x, inner.bottom - fuel_h, inner.width, fuel_h)
    pygame.draw.rect(bottle, (212, 116, 30), fuel_rect, border_radius=int(6 * s))
    pygame.draw.rect(bottle, (245, 160, 55),
                     (fuel_rect.x, fuel_rect.y, fuel_rect.width, int(4 * s)))
    pygame.draw.line(bottle, (255, 220, 160),
                     (inner.x + int(4 * s), inner.y + int(6 * s)),
                     (inner.x + int(4 * s), inner.bottom - int(8 * s)), max(1, int(2 * s)))
    pygame.draw.rect(bottle, (60, 60, 64),
                     (bx - int(7 * s), int(30 * s), int(14 * s), int(5 * s)))
    rot = pygame.transform.rotate(bottle, angle)
    rect = rot.get_rect(center=(int(cx), int(cy)))
    surface.blit(rot, rect)
def draw_van_handoff(surface, t, item="weapon"):
    draw_van_interior(surface, t)
    dim = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
    dim.fill((0, 0, 0, 105))
    surface.blit(dim, (0, 0))
    panel_w = 650
    panel_h = 355
    panel_x = WIDTH // 2 - panel_w // 2
    panel_y = SCENE_TOP + 42
    panel = pygame.Rect(panel_x, panel_y, panel_w, panel_h)
    shadow = pygame.Surface((panel_w + 28, panel_h + 28), pygame.SRCALPHA)
    pygame.draw.rect(shadow, (0, 0, 0, 145), shadow.get_rect(), border_radius=8)
    surface.blit(shadow, (panel_x + 14, panel_y + 14))
    pygame.draw.rect(surface, (9, 10, 13), panel, border_radius=6)
    pygame.draw.rect(surface, (52, 62, 74), panel, 2, border_radius=6)
    pygame.draw.rect(surface, C_KRAP_BLUE, (panel_x, panel_y, 5, panel_h), border_radius=4)
    for x in range(panel_x + 35, panel.right - 35, 80):
        pygame.draw.line(surface, (22, 24, 29), (x, panel_y + 10), (x, panel.bottom - 10), 1)
    for y in range(panel_y + 45, panel.bottom - 20, 42):
        pygame.draw.line(surface, (18, 20, 25), (panel_x + 15, y), (panel.right - 15, y), 1)
    label = "LOADOUT TRANSFER // SERVICE SIDEARM" if item == "weapon" else "LOADOUT TRANSFER // INCENDIARY PACKAGE"
    tag = font_terminal_small.render(label, True, (110, 150, 180))
    surface.blit(tag, (panel_x + 18, panel_y + 12))
    rec = font_terminal_small.render("REC", True, (220, 55, 45))
    surface.blit(rec, (panel.right - rec.get_width() - 22, panel_y + 12))
    if (pygame.time.get_ticks() // 400) % 2 == 0:
        pygame.draw.circle(surface, (220, 55, 45), (panel.right - rec.get_width() - 34, panel_y + 19), 4)
    table_y = panel_y + 250
    table_pts = [(panel_x + 110, table_y), (panel.right - 110, table_y),
                 (panel.right - 55, panel.bottom - 28), (panel_x + 55, panel.bottom - 28)]
    pygame.draw.polygon(surface, (48, 36, 24), table_pts)
    pygame.draw.polygon(surface, (80, 60, 38), table_pts, 2)
    for yy in range(table_y + 18, panel.bottom - 35, 22):
        pygame.draw.line(surface, (35, 25, 17), (panel_x + 75, yy), (panel.right - 75, yy), 1)
    crate_lbl = font_terminal_small.render("KRAP FIELD KIT", True, (130, 110, 80))
    if item == "weapon":
        surface.blit(crate_lbl, (WIDTH // 2 - crate_lbl.get_width() // 2, panel.bottom - 58))
    p = _ease_cutscene((t - 250) / 1100.0)
    idle = math.sin(t * 0.006) * 2
    if item == "weapon":
        hand_y = panel_y + 202 + idle
        left_start = (panel_x + 90, panel_y + 190)
        right_start = (panel.right - 90, panel_y + 206)
        left_hand_x = _lerp_cutscene(panel_x + 230, WIDTH // 2 - 35, p)
        left_hand_y = _lerp_cutscene(panel_y + 190, hand_y, p)
        right_hand_x = _lerp_cutscene(panel.right - 205, WIDTH // 2 + 38, p)
        right_hand_y = _lerp_cutscene(panel_y + 215, hand_y + 5, p)
        glow = pygame.Surface((300, 210), pygame.SRCALPHA)
        for r in range(130, 0, -8):
            a = int(22 * (1 - r / 130))
            pygame.draw.ellipse(glow, (120, 160, 220, a), (150 - r, 105 - r // 2, r * 2, r))
        surface.blit(glow, (WIDTH // 2 - 150, panel_y + 95))
        pygame.draw.line(surface, C_KRAP_UNIFORM, left_start, (left_hand_x, left_hand_y), 22)
        pygame.draw.line(surface, (25, 30, 38), left_start, (left_hand_x, left_hand_y), 3)
        pygame.draw.circle(surface, (178, 150, 125), (int(left_hand_x), int(left_hand_y)), 15)
        pygame.draw.circle(surface, (70, 82, 100), (int(left_hand_x - 6), int(left_hand_y + 3)), 7)
        biribel_sleeve = (45, 55, 48)
        pygame.draw.line(surface, biribel_sleeve, right_start, (right_hand_x, right_hand_y), 22)
        pygame.draw.line(surface, (24, 30, 26), right_start, (right_hand_x, right_hand_y), 3)
        pygame.draw.circle(surface, (54, 44, 36), (int(right_hand_x), int(right_hand_y)), 16)
        pygame.draw.circle(surface, (170, 140, 112), (int(right_hand_x - 4), int(right_hand_y + 1)), 7)
        item_x = _lerp_cutscene(left_hand_x, WIDTH // 2, 0.55)
        item_y = hand_y - 20
        _draw_handoff_pistol(surface, item_x, item_y, scale=1.3, angle=-8)
        small = font_terminal_small.render("9MM SIDEARM // 12-RD MAG", True, (150, 165, 175))
        surface.blit(small, (WIDTH // 2 - small.get_width() // 2, panel_y + 292))
    else:
        # ── MOLOTOVS: crate slides across the table toward Biribel ──
        crate_w, crate_h = 190, 86
        crate_start_x = panel_x + 175
        crate_end_x = WIDTH // 2 + 30
        crate_x = _lerp_cutscene(crate_start_x, crate_end_x, p)
        crate_y = table_y - 14 + idle * 0.5
        shad = pygame.Surface((crate_w + 30, 26), pygame.SRCALPHA)
        pygame.draw.ellipse(shad, (0, 0, 0, 110), shad.get_rect())
        surface.blit(shad, (int(crate_x - crate_w // 2 - 15), int(crate_y + crate_h - 28)))
        crate_rect = pygame.Rect(int(crate_x - crate_w // 2), int(crate_y), crate_w, crate_h)
        pygame.draw.rect(surface, (84, 58, 32), crate_rect, border_radius=4)
        pygame.draw.rect(surface, (46, 30, 16), crate_rect, 3, border_radius=4)
        interior = crate_rect.inflate(-18, -18)
        interior.y -= 6
        pygame.draw.rect(surface, (26, 18, 12), interior, border_radius=3)
        for px2 in range(crate_rect.x + 28, crate_rect.right - 16, 38):
            pygame.draw.line(surface, (58, 38, 20),
                             (px2, crate_rect.y + 4), (px2, crate_rect.bottom - 4), 2)
        stencil = font_terminal_small.render("FLAMMABLE", True, (160, 60, 40))
        surface.blit(stencil, (crate_rect.centerx - stencil.get_width() // 2,
                               crate_rect.bottom - 22))
        _draw_handoff_molotov(surface, crate_rect.centerx - 34, crate_rect.y - 26,
                              scale=0.62, angle=-12)
        _draw_handoff_molotov(surface, crate_rect.centerx + 34, crate_rect.y - 24,
                              scale=0.62, angle=10)
        glow = pygame.Surface((280, 180), pygame.SRCALPHA)
        for r in range(115, 0, -8):
            a = int(16 * (1 - r / 115))
            pygame.draw.ellipse(glow, (235, 170, 90, a), (140 - r, 90 - r // 2, r * 2, r))
        surface.blit(glow, (int(crate_rect.centerx - 140), int(crate_rect.y - 95)))
        push_x = crate_rect.x - 6
        push_y = crate_rect.centery - 6
        left_start = (panel_x + 80, panel_y + 195)
        pygame.draw.line(surface, C_KRAP_UNIFORM, left_start, (push_x, push_y), 22)
        pygame.draw.line(surface, (25, 30, 38), left_start, (push_x, push_y), 3)
        pygame.draw.circle(surface, (178, 150, 125), (int(push_x), int(push_y)), 14)
        reach_p = _ease_cutscene((p - 0.55) / 0.45)
        if reach_p > 0:
            right_start = (panel.right - 80, panel_y + 210)
            reach_x = _lerp_cutscene(panel.right - 190, crate_rect.right + 4, reach_p)
            reach_y = _lerp_cutscene(panel_y + 215, crate_rect.centery - 2, reach_p)
            biribel_sleeve = (45, 55, 48)
            pygame.draw.line(surface, biribel_sleeve, right_start, (reach_x, reach_y), 22)
            pygame.draw.line(surface, (24, 30, 26), right_start, (reach_x, reach_y), 3)
            pygame.draw.circle(surface, (54, 44, 36), (int(reach_x), int(reach_y)), 15)
            pygame.draw.circle(surface, (170, 140, 112),
                               (int(reach_x - 4), int(reach_y + 1)), 7)
        small = font_terminal_small.render(
            "2x MOLOTOV // UNLIT — FIELD EXPEDIENT", True, (190, 135, 80))
        surface.blit(small, (WIDTH // 2 - small.get_width() // 2, panel_y + 18 + 24))
    scan = pygame.Surface((panel_w, panel_h), pygame.SRCALPHA)
    for sy in range(0, panel_h, 4):
        pygame.draw.line(scan, (0, 0, 0, 22), (0, sy), (panel_w, sy))
    surface.blit(scan, (panel_x, panel_y))
    pygame.draw.line(surface, (80, 95, 110), (panel_x + 12, panel_y + 34), (panel.right - 12, panel_y + 34), 1)
# ─────────────────────────────────────────────
# CUTSCENE 1 — THE WORLD
# ─────────────────────────────────────────────
GROUND_Y = SCENE_BOT - 55
PAL_RAINY = [(26, 30, 38), (22, 28, 36)]

def draw_route12_black(surface, t):
    surface.fill((2, 3, 6))
    rng = random.Random(int(t // 80))
    for _ in range(45):
        x = rng.randint(0, WIDTH - 1)
        y = rng.randint(SCENE_TOP, SCENE_BOT - 1)
        shade = rng.randint(8, 28)
        surface.set_at((x, y), (shade, shade, shade + 4))
    pulse = int(35 + math.sin(t * 0.006) * 20)
    glow = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
    pygame.draw.circle(glow, (40, 80, 120, pulse), (WIDTH // 2, HEIGHT // 2), 220)
    surface.blit(glow, (0, 0))
    tag = font_terminal.render("KRAP FIELD AUDIO // ROUTE 12", True, (75, 125, 165))
    surface.blit(tag, (WIDTH // 2 - tag.get_width() // 2, SCENE_TOP + 210))
    sub = font_terminal_small.render("RAIN AUDIO // FILE ROOM STATIC // NO LIVE SIGNAL", True, (90, 90, 95))
    surface.blit(sub, (WIDTH // 2 - sub.get_width() // 2, SCENE_TOP + 244))


def draw_route12_files(surface, t):
    """Vasile studies the recovered Route 12 file.

    Cleaner spacing pass: the close-up now uses three separated document zones
    instead of stacking every clue on top of the main security order.
    """
    def ease01(v):
        v = max(0.0, min(1.0, v))
        return v * v * (3 - 2 * v)

    push = ease01((t - 1350) / 1100.0)
    finger_t = ease01((t - 2450) / 850.0)
    flicker = 0.78 + 0.22 * math.sin(t * 0.009)

    # ── Base van interior, without default characters.
    surface.fill((7, 8, 10))
    for y in range(SCENE_TOP, SCENE_BOT):
        p = (y - SCENE_TOP) / max(1, SCENE_H)
        pygame.draw.line(
            surface,
            (int(13 + p * 9), int(11 + p * 6), int(13 + p * 7)),
            (0, y),
            (WIDTH, y),
        )
    for x in range(80, WIDTH - 80, 96):
        pygame.draw.line(surface, (25, 22, 24), (x, SCENE_TOP + 10), (x, SCENE_BOT - 92), 1)
    for y in range(SCENE_TOP + 50, SCENE_BOT - 90, 48):
        pygame.draw.line(surface, (21, 18, 20), (40, y), (WIDTH - 40, y), 1)

    floor_y = SCENE_BOT - 95
    pygame.draw.rect(surface, (10, 10, 12), (0, floor_y, WIDTH, SCENE_BOT - floor_y))
    pygame.draw.rect(surface, (145, 28, 30), (WIDTH // 2 - 95, SCENE_TOP + 28, 190, 7))
    red_glow = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
    pygame.draw.circle(red_glow, (130, 20, 24, 28), (WIDTH // 2, SCENE_TOP + 76), 210)
    surface.blit(red_glow, (0, 0))

    # Subdued right-side route monitor.
    win = pygame.Rect(WIDTH - 300, SCENE_TOP + 78, 210, 165)
    pygame.draw.rect(surface, (7, 9, 13), win)
    pygame.draw.rect(surface, (48, 39, 34), win.inflate(12, 12), 4)
    for i in range(12):
        lx = win.x + 12 + ((i * 31 + int(t * 0.35)) % (win.w - 24))
        ly = win.y + 24 + (i * 21) % (win.h - 48)
        pygame.draw.rect(surface, [(150, 80, 55), (80, 95, 130), (170, 130, 55)][i % 3], (lx, ly, 26, 4))

    # ── Wide shot: Vasile and folder.
    lamp = pygame.Surface((360, 360), pygame.SRCALPHA)
    pygame.draw.circle(lamp, (85, 145, 210, int(48 * (1 - push * 0.35))), (180, 180), 170)
    surface.blit(lamp, (42, SCENE_TOP + 112))
    draw_vasile(surface, 185, floor_y + 2, scale=0.72, facing_right=True)

    table = pygame.Rect(315, floor_y - 74, 278, 70)
    pygame.draw.rect(surface, (0, 0, 0), table.move(8, 8), border_radius=4)
    pygame.draw.rect(surface, (34, 25, 18), table, border_radius=4)
    pygame.draw.rect(surface, (74, 55, 35), table, 2, border_radius=4)
    folder_x, folder_y = table.x + 28, table.y + 10
    folder_pts = [
        (folder_x, folder_y + 12),
        (folder_x + 88, folder_y),
        (folder_x + 214, folder_y + 14),
        (folder_x + 204, folder_y + 52),
        (folder_x + 8, folder_y + 54),
    ]
    pygame.draw.polygon(surface, (150, 118, 62), folder_pts)
    pygame.draw.polygon(surface, (95, 72, 38), folder_pts, 2)
    for i, off in enumerate((0, 9, 18)):
        pygame.draw.rect(surface, (204, 196, 160), (folder_x + 30 + off, folder_y + 8 + off // 3, 112, 44), border_radius=2)
        pygame.draw.rect(surface, (95, 83, 60), (folder_x + 30 + off, folder_y + 8 + off // 3, 112, 44), 1, border_radius=2)
        pygame.draw.line(surface, (120, 104, 76), (folder_x + 40 + off, folder_y + 24 + off // 3), (folder_x + 124 + off, folder_y + 24 + off // 3), 1)
        pygame.draw.line(surface, (120, 104, 76), (folder_x + 40 + off, folder_y + 34 + off // 3), (folder_x + 114 + off, folder_y + 34 + off // 3), 1)
    tag = font_terminal_small.render("RECOVERED FROM VOLKOV WAREHOUSE", True, (125, 145, 155))
    tag.set_alpha(int(230 * (1 - push * 0.55)))
    surface.blit(tag, (table.x + 18, table.y - 24))

    # ── Close-up layer: spaced physical documents on a desk.
    close = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
    dim = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
    dim.fill((0, 0, 0, int(135 * push)))
    close.blit(dim, (0, 0))

    desk = pygame.Rect(86, SCENE_TOP + 34, WIDTH - 172, 402)
    pygame.draw.rect(close, (22, 15, 10, int(245 * push)), desk, border_radius=8)
    pygame.draw.rect(close, (70, 48, 28, int(210 * push)), desk, 2, border_radius=8)
    for yy in range(desk.y + 34, desk.bottom - 20, 42):
        pygame.draw.line(close, (34, 24, 16, int(120 * push)), (desk.x + 18, yy), (desk.right - 18, yy), 1)

    # Folder backing, slightly larger but visually quiet.
    folder = pygame.Rect(desk.x + 40, desk.y + 42, desk.w - 80, desk.h - 78)
    folder_shape = [
        (folder.x, folder.y + 36),
        (folder.x + 132, folder.y),
        (folder.right - 22, folder.y + 25),
        (folder.right, folder.bottom - 20),
        (folder.x + 24, folder.bottom),
    ]
    pygame.draw.polygon(close, (145, 111, 58, int(236 * push)), folder_shape)
    pygame.draw.polygon(close, (88, 66, 36, int(210 * push)), folder_shape, 2)
    tab = font_terminal_small.render("ROUTE 12 / CHECKPOINT 12", True, (56, 42, 24))
    tab.set_alpha(int(230 * push))
    close.blit(tab, (folder.x + 34, folder.y + 14))

    def draw_paper(rect, title, rows, stamp=None, stamp_col=(170, 38, 32), paper_col=(213, 205, 176), angle=0, title_size="terminal"):
        paper = pygame.Surface((rect.w, rect.h), pygame.SRCALPHA)
        pygame.draw.rect(paper, paper_col, paper.get_rect(), border_radius=3)
        pygame.draw.rect(paper, (95, 80, 58), paper.get_rect(), 2, border_radius=3)
        pygame.draw.rect(paper, (188, 181, 152), (0, 0, rect.w, 34), border_radius=3)
        title_font = font_terminal if title_size == "terminal" else font_terminal_small
        title_s = title_font.render(title, True, (45, 37, 28))
        paper.blit(title_s, (14, 8 if title_size == "terminal" else 10))
        y = 50
        for label, value, col in rows:
            lab = font_terminal_small.render(label, True, (78, 68, 52))
            val_font = font_prompt if rect.w > 300 else font_terminal_small
            val = val_font.render(value, True, col)
            paper.blit(lab, (18, y + 3))
            paper.blit(val, (130 if rect.w < 330 else 146, y))
            pygame.draw.line(paper, (160, 148, 112), (16, y + 24), (rect.w - 18, y + 24), 1)
            y += 32
        for yy in range(y + 4, rect.h - 18, 15):
            pygame.draw.line(paper, (170, 158, 120), (18, yy), (rect.w - 20, yy), 1)
        if stamp:
            st = font_terminal.render(stamp, True, stamp_col)
            st = pygame.transform.rotate(st, -7)
            st.set_alpha(205)
            paper.blit(st, (rect.w - st.get_width() - 14, rect.h - st.get_height() - 12))
        paper.set_alpha(int(255 * push))
        if angle:
            rot = pygame.transform.rotate(paper, angle)
            close.blit(rot, rot.get_rect(center=rect.center))
        else:
            close.blit(paper, rect)

    # Layout zones:
    #   left top  = checkpoint photo
    #   left bottom = IPA manifest
    #   right = security order
    #   bottom center = field note, not covering key rows.
    photo = pygame.Rect(desk.x + 74, desk.y + 74, 250, 140)
    draw_paper(photo, "PHOTO // CHECKPOINT", [], paper_col=(198, 192, 166), title_size="small")
    pygame.draw.rect(close, (20, 23, 25, int(255 * push)), (photo.x + 20, photo.y + 42, photo.w - 40, 70))
    pygame.draw.rect(close, (55, 65, 66, int(255 * push)), (photo.x + 42, photo.y + 65, 50, 36))
    pygame.draw.rect(close, (55, 65, 66, int(255 * push)), (photo.x + 128, photo.y + 58, 54, 43))
    pygame.draw.line(close, (155, 60, 45, int(255 * push)), (photo.x + 44, photo.y + 101), (photo.x + 90, photo.y + 66), 2)
    pygame.draw.circle(close, (185, 45, 35, int(255 * push)), (photo.right - 22, photo.y + 22), 5)

    manifest = pygame.Rect(desk.x + 74, desk.y + 252, 275, 105)
    draw_paper(
        manifest,
        "IPA TRUCK MANIFEST",
        [("DEST", "CHECKPOINT 12", (40, 46, 48)), ("CLEAR", "BALACEANU OFFICE", (190, 55, 42))],
        paper_col=(207, 196, 158),
        angle=-1,
        title_size="small",
    )

    main_doc = pygame.Rect(desk.x + 490, desk.y + 70, 395, 285)
    draw_paper(
        main_doc,
        "SECURITY ORDER",
        [
            ("ROUTE", "12 / CHECKPOINT 12", (40, 46, 48)),
            ("STATUS", "PRE-MARKED UNSTABLE", (42, 85, 105)),
            ("PUBLIC", "MAG BOMBING", (40, 46, 48)),
            ("AUTH", "IPA / BALACEANU", (190, 55, 42)),
            ("DECREE", "DRAFTED 02:14", (190, 55, 42)),
            ("REPORT", "FILED 03:27", (40, 46, 48)),
        ],
        stamp="BEFORE ATTACK",
    )
    highlight = pygame.Surface((main_doc.w - 34, 56), pygame.SRCALPHA)
    highlight.fill((170, 42, 32, int(34 * push * flicker)))
    close.blit(highlight, (main_doc.x + 17, main_doc.y + 208))

    note = pygame.Rect(desk.x + 360, desk.y + 292, 220, 92)
    draw_paper(
        note,
        "FIELD NOTE",
        [("PAINT", "AFTER BLAST", (40, 46, 48)), ("CLAIM", "NONE", (190, 55, 42))],
        stamp="NOT MAG?",
        paper_col=(224, 211, 166),
        angle=2,
        title_size="small",
    )

    # Thin evidence strings — routed around text-heavy areas.
    line_col = (185, 68, 45, int(220 * push))
    connections = [
        ((photo.right - 8, photo.centery + 12), (main_doc.x + 18, main_doc.y + 70)),
        ((manifest.right - 6, manifest.y + 34), (main_doc.x + 18, main_doc.y + 214)),
        ((note.right - 8, note.y + 34), (main_doc.x + 18, main_doc.y + 172)),
    ]
    for a, b in connections:
        pygame.draw.line(close, line_col, a, b, 2)
        pygame.draw.circle(close, line_col, a, 4)
        pygame.draw.circle(close, line_col, b, 4)

    # Vasile's finger points at the timestamp conflict without covering it.
    start_x, start_y = desk.x + 210, desk.bottom + 48
    target_x, target_y = main_doc.x + 250, main_doc.y + 250
    fx = start_x + (target_x - start_x) * finger_t
    fy = start_y + (target_y - start_y) * finger_t
    if push > 0.35:
        hand = pygame.Surface((220, 130), pygame.SRCALPHA)
        hx, hy = 28, 72
        pygame.draw.polygon(hand, (0, 0, 0, int(72 * push)), [(hx + 8, hy + 8), (hx + 150, hy - 26), (hx + 164, hy - 10), (hx + 22, hy + 22)])
        pygame.draw.line(hand, (82, 95, 122, int(230 * push)), (hx, hy + 24), (hx + 110, hy - 8), 19)
        pygame.draw.line(hand, (215, 176, 132, int(255 * push)), (hx + 92, hy - 6), (hx + 176, hy - 30), 12)
        pygame.draw.circle(hand, (225, 186, 142, int(255 * push)), (hx + 179, hy - 31), 8)
        hand = pygame.transform.rotate(hand, -6)
        close.blit(hand, (fx - 52, fy - 18))
        pygame.draw.circle(close, (255, 210, 110, int(105 * push * flicker)), (int(target_x), int(target_y)), 18, 2)

    scan_y = desk.y + 28 + int((t * 0.075) % max(1, desk.h - 56))
    scan = pygame.Surface((desk.w, 3), pygame.SRCALPHA)
    scan.fill((95, 180, 225, int(36 * push)))
    close.blit(scan, (desk.x, scan_y))
    cap = font_terminal_small.render("Vasile's finger stops on the timestamps.", True, (135, 155, 165))
    cap.set_alpha(int(255 * push))
    close.blit(cap, (desk.x + 26, desk.bottom + 12))

    surface.blit(close, (0, 0))


def draw_route12_mag_alert(surface, t):
    """Official Route 12 public-release bulletin.

    Spacing-focused version: one readable main form, side notes outside the form,
    no stamps/text overlapping critical fields.
    """
    # Dark briefing wall.
    surface.fill((18, 17, 16))
    for y in range(SCENE_TOP, SCENE_BOT, 36):
        pygame.draw.rect(surface, (27, 24, 21), (0, y, WIDTH, 28))
        pygame.draw.line(surface, (9, 8, 7), (0, y + 28), (WIDTH, y + 28), 1)

    # Soft red emergency light behind the board.
    glow = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
    pulse = int(28 + math.sin(t * 0.005) * 10)
    pygame.draw.circle(glow, (175, 30, 24, pulse), (WIDTH // 2, SCENE_TOP + 215), 340)
    surface.blit(glow, (0, 0))

    # Wide backing board so sticky notes can live OUTSIDE the main sheet.
    board = pygame.Rect(WIDTH // 2 - 425, SCENE_TOP + 34, 850, 390)
    pygame.draw.rect(surface, (54, 39, 27), board, border_radius=7)
    pygame.draw.rect(surface, (115, 82, 45), board, 3, border_radius=7)
    pygame.draw.rect(surface, (30, 22, 15), board.inflate(-28, -28), 1, border_radius=4)

    # Main paper: centered and tall enough to separate fields from lower evidence.
    paper = pygame.Rect(WIDTH // 2 - 265, SCENE_TOP + 58, 530, 330)
    shadow = pygame.Surface((paper.w + 22, paper.h + 22), pygame.SRCALPHA)
    shadow.fill((0, 0, 0, 95))
    surface.blit(shadow, (paper.x + 11, paper.y + 13))
    pygame.draw.rect(surface, (196, 186, 142), paper, border_radius=2)
    pygame.draw.rect(surface, (78, 60, 38), paper, 3, border_radius=2)

    # Header strip.
    header = pygame.Rect(paper.x, paper.y, paper.w, 48)
    pygame.draw.rect(surface, (154, 28, 24), header)
    pygame.draw.rect(surface, (86, 18, 16), (header.x, header.bottom - 5, header.w, 5))
    hdr = font_speaker.render("EMERGENCY SECURITY ALERT", True, (246, 226, 196))
    surface.blit(hdr, (header.centerx - hdr.get_width() // 2, header.y + 10))
    for px in (paper.x + 20, paper.right - 20):
        pygame.draw.circle(surface, (88, 48, 24), (px + 2, paper.y + 22), 7)
        pygame.draw.circle(surface, (202, 126, 62), (px, paper.y + 20), 7)

    # Official form fields, with large vertical spacing and no stamp overlap.
    form_x = paper.x + 42
    form_y = paper.y + 76
    label_col = (75, 59, 42)
    value_col = (43, 36, 28)
    warning_col = (132, 28, 24)
    rows = [
        ("INCIDENT", "ROUTE 12 / CHECKPOINT 12", value_col),
        ("PUBLIC LABEL", "SUSPECTED MAG BOMBING", warning_col),
        ("SOURCE", "IPA CIVIL SECURITY DESK", value_col),
        ("STATUS", "UNVERIFIED — FIELD REVIEW PENDING", warning_col),
    ]
    for i, (label, value, col) in enumerate(rows):
        y = form_y + i * 44
        lab = font_terminal_small.render(label, True, label_col)
        val_font = font_terminal if len(value) < 29 else font_prompt
        val = val_font.render(value, True, col)
        surface.blit(lab, (form_x, y + 6))
        surface.blit(val, (form_x + 145, y))
        pygame.draw.line(surface, (126, 108, 78), (form_x, y + 30), (paper.right - 42, y + 30), 1)

    # Highlight only the suspicious status row, not the whole document.
    hi = pygame.Surface((paper.w - 84, 32), pygame.SRCALPHA)
    hi.fill((190, 38, 26, 26))
    surface.blit(hi, (form_x, form_y + 3 * 44 - 3))

    # Lower evidence row. Everything here is below the fields.
    evidence_y = paper.y + 250
    photo = pygame.Rect(paper.x + 44, evidence_y, 132, 48)
    pygame.draw.rect(surface, (22, 23, 22), photo)
    pygame.draw.rect(surface, (96, 80, 58), photo, 2)
    tag = font_terminal.render("MAG", True, (15, 15, 14))
    tag = pygame.transform.rotate(tag, -7)
    tag.set_alpha(170)
    surface.blit(tag, (photo.x + 36, photo.y + 9))
    photo_lbl = font_terminal_small.render("ATTACHED PHOTO / UNVERIFIED", True, (70, 58, 42))
    surface.blit(photo_lbl, (photo.x, photo.bottom + 5))

    # Small stamp in its own lower-right area, not on top of form fields.
    stamp_box = pygame.Rect(paper.right - 200, evidence_y - 4, 160, 60)
    pygame.draw.rect(surface, (0, 0, 0, 28), stamp_box)
    pygame.draw.rect(surface, (130, 28, 24), stamp_box, 1)
    stamp = font_terminal.render("SUSPECTED MAG", True, (140, 26, 22))
    stamp = pygame.transform.rotate(stamp, -5)
    stamp.set_alpha(178)
    surface.blit(stamp, (stamp_box.centerx - stamp.get_width() // 2, stamp_box.y + 7))
    bomb = font_terminal_small.render("BOMBING", True, (140, 26, 22))
    bomb = pygame.transform.rotate(bomb, -5)
    bomb.set_alpha(172)
    surface.blit(bomb, (stamp_box.centerx - bomb.get_width() // 2, stamp_box.y + 36))

    # Footer at the very bottom, separate from photo and stamp.
    footer = pygame.Rect(paper.x + 34, paper.bottom - 28, paper.w - 68, 20)
    pygame.draw.rect(surface, (0, 0, 0, 34), footer)
    footer_txt = font_terminal_small.render("PUBLIC RELEASE PREPARED  //  FIELD VERIFICATION PENDING", True, (72, 48, 32))
    surface.blit(footer_txt, (footer.centerx - footer_txt.get_width() // 2, footer.y + 4))

    # Side notes: outside the paper, so they cannot cover form fields.
    note1 = pygame.Rect(board.x + 36, board.y + 70, 112, 66)
    pygame.draw.rect(surface, (178, 162, 114), note1, border_radius=2)
    pygame.draw.rect(surface, (84, 64, 38), note1, 1, border_radius=2)
    n1 = font_terminal_small.render("NO CLAIM", True, (100, 36, 28))
    n2 = font_terminal_small.render("SIGNAL", True, (100, 36, 28))
    surface.blit(n1, (note1.x + 16, note1.y + 16))
    surface.blit(n2, (note1.x + 25, note1.y + 38))

    note2 = pygame.Rect(board.right - 152, board.bottom - 106, 116, 60)
    pygame.draw.rect(surface, (154, 132, 92), note2, border_radius=2)
    pygame.draw.rect(surface, (84, 64, 38), note2, 1, border_radius=2)
    n3 = font_terminal_small.render("RELEASE", True, (72, 48, 32))
    n4 = font_terminal_small.render("QUEUED", True, (125, 36, 28))
    surface.blit(n3, (note2.x + 28, note2.y + 14))
    surface.blit(n4, (note2.x + 30, note2.y + 34))

    # Very subtle broadcast glitch. Global scanlines still draw later.
    if int(t // 260) % 2 == 0:
        pygame.draw.rect(surface, (255, 255, 255, 12), (paper.x, paper.y + 54, paper.w, 2))


def _draw_route12_checkpoint_base(surface, t, tanker=False):
    """Cinematic Route 12 checkpoint plate; all major visuals stay above dialogue."""
    draw_sky_gradient(surface, (8, 12, 18), (28, 28, 30))
    horizon_y = SCENE_TOP + 96
    road_y = SCENE_TOP + 300
    pygame.draw.rect(surface, (16, 18, 20), (0, horizon_y, WIDTH, SCENE_BOT - horizon_y))
    # Distant tree/building silhouettes.
    rng = random.Random(212)
    for x in range(-20, WIDTH + 60, 56):
        h = rng.randint(30, 90)
        pygame.draw.rect(surface, (10, 12, 14), (x, road_y - h - 58, 44, h))
    # Highway surface.
    pygame.draw.rect(surface, (30, 31, 32), (0, road_y, WIDTH, 210))
    pygame.draw.rect(surface, (23, 24, 25), (0, road_y + 86, WIDTH, 38))
    for x in range(-80 + int((t * 0.012) % 150), WIDTH + 150, 150):
        pygame.draw.rect(surface, (154, 136, 60), (x, road_y + 102, 72, 5))
    # Toll booths / checkpoint lanes with perspective spacing.
    booth_specs = [(120, road_y - 106, 104, 128), (330, road_y - 78, 92, 112), (590, road_y - 72, 92, 108), (790, road_y - 96, 104, 126)]
    for i, (bx, by, bw, bh) in enumerate(booth_specs):
        pygame.draw.rect(surface, (37, 44, 48), (bx + 5, by + 8, bw, bh))
        pygame.draw.rect(surface, (59, 68, 72), (bx, by, bw, bh))
        pygame.draw.rect(surface, (102, 112, 118), (bx, by, bw, bh), 2)
        pygame.draw.rect(surface, (8, 12, 15), (bx + 16, by + 24, bw - 32, 36))
        pygame.draw.line(surface, (138, 43, 34), (bx + 4, by + bh - 6), (bx + bw - 4, by + 16), 4)
        if i == 1:
            pygame.draw.circle(surface, (255, 110, 35), (bx + bw - 10, by + 12), 5)
    # Burned KRAP flag in a clear upper-left composition.
    pole_x = 88
    pygame.draw.line(surface, (55, 55, 58), (pole_x, road_y - 150), (pole_x, road_y + 20), 5)
    flag = [(pole_x, road_y - 148), (pole_x + 94, road_y - 138), (pole_x + 76, road_y - 96), (pole_x, road_y - 104)]
    pygame.draw.polygon(surface, C_KRAP_BLUE, flag)
    pygame.draw.polygon(surface, (8, 8, 8), [(pole_x + 66, road_y - 135), (pole_x + 94, road_y - 138), (pole_x + 76, road_y - 96), (pole_x + 58, road_y - 101)])
    # Foreground wrecks and evidence silhouette.
    wrecks = [(230, road_y + 74, 112, 40, (35, 32, 30)), (660, road_y + 78, 132, 42, (45, 38, 34))]
    for wx, wy, ww, wh, col in wrecks:
        pygame.draw.rect(surface, col, (wx, wy, ww, wh), border_radius=5)
        pygame.draw.rect(surface, (82, 65, 50), (wx, wy, ww, wh), 2, border_radius=5)
        pygame.draw.circle(surface, (10, 10, 10), (wx + 18, wy + wh), 9)
        pygame.draw.circle(surface, (10, 10, 10), (wx + ww - 18, wy + wh), 9)
    # Smoke columns kept semi-transparent.
    for i in range(10):
        sx = rng.randint(80, 900)
        sy = road_y - rng.randint(20, 150)
        drift = math.sin(t * 0.0014 + i) * 16
        for r in range(46, 10, -9):
            sm = pygame.Surface((r * 2, r * 2), pygame.SRCALPHA)
            pygame.draw.circle(sm, (45, 45, 45, max(10, 42 - r // 2)), (r, r), r)
            surface.blit(sm, (sx + drift - r, sy - i * 8 - r))
    if tanker:
        tank = pygame.Rect(WIDTH // 2 - 132, road_y + 20, 264, 72)
        pygame.draw.ellipse(surface, (0, 0, 0, 90), (tank.x - 20, tank.y + 30, tank.w + 40, 72))
        pygame.draw.rect(surface, (80, 74, 62), tank, border_radius=24)
        pygame.draw.rect(surface, (155, 42, 32), (tank.x + 18, tank.centery - 10, tank.w - 36, 20))
        pygame.draw.rect(surface, (132, 124, 98), tank, 2, border_radius=24)
        for sx in range(tank.x + 34, tank.right - 20, 46):
            pygame.draw.line(surface, (42, 45, 48), (sx, tank.y + 10), (sx, tank.bottom - 10), 3)
        leak = pygame.Surface((160, 42), pygame.SRCALPHA)
        pygame.draw.ellipse(leak, (45, 38, 25, 125), (0, 0, 160, 42))
        surface.blit(leak, (tank.right - 28, tank.bottom - 6))
        warn = font_terminal.render("LEAKING FUEL", True, (255, 120, 50))
        surface.blit(warn, (tank.centerx - warn.get_width() // 2, tank.y - 34))
    else:
        label = font_terminal.render("CHECKPOINT 12 // SUSPECTED MAG BOMBING", True, (170, 145, 90))
        surface.blit(label, (WIDTH // 2 - label.get_width() // 2, road_y - 34))


def draw_route12_checkpoint(surface, t):
    """Mission 2 intro checkpoint hero shot.

    Goal: one readable cinematic image, not a flat row of booths. The important
    stuff stays above the dialogue box: burned KRAP flag, ruined checkpoint,
    headlights/squad entering, and the suspicious MAG label.
    """
    draw_sky_gradient(surface, (7, 11, 17), (25, 28, 31))
    top = SCENE_TOP
    bot = SCENE_BOT
    horizon_y = top + 118
    road_near_y = bot - 88
    road_far_y = top + 300

    # Distant skyline / tree line, low contrast so it doesn't fight the action.
    pygame.draw.rect(surface, (11, 14, 17), (0, horizon_y, WIDTH, bot - horizon_y))
    rng = random.Random(1212)
    for x in range(-30, WIDTH + 40, 42):
        h = rng.randint(38, 118)
        col = rng.choice([(9, 11, 14), (12, 13, 16), (14, 13, 15)])
        pygame.draw.rect(surface, col, (x, road_far_y - h, 34, h))
        if rng.random() > 0.78:
            pygame.draw.rect(surface, (95, 65, 38), (x + 12, road_far_y - h + 16, 5, 7))

    # Highway in perspective.
    pygame.draw.polygon(
        surface,
        (28, 30, 31),
        [(-110, bot), (WIDTH + 110, bot), (760, road_far_y), (240, road_far_y)],
    )
    pygame.draw.polygon(
        surface,
        (20, 22, 23),
        [(0, bot), (210, bot), (375, road_far_y), (255, road_far_y)],
    )
    pygame.draw.polygon(
        surface,
        (20, 22, 23),
        [(WIDTH, bot), (WIDTH - 210, bot), (625, road_far_y), (745, road_far_y)],
    )
    # Perspective lane marks.
    for i in range(7):
        p = i / 6
        y = road_far_y + p * (road_near_y - road_far_y)
        w = 52 + p * 62
        gap = 60 + p * 100
        x_center = WIDTH // 2
        col = (145, 132, 66)
        pygame.draw.rect(surface, col, (x_center - gap - w, y, w, 5))
        pygame.draw.rect(surface, col, (x_center + gap, y, w, 5))

    # Checkpoint gantry/sign: makes the place identifiable immediately.
    gantry_y = top + 165
    pygame.draw.line(surface, (46, 54, 58), (122, gantry_y), (878, gantry_y), 6)
    pygame.draw.line(surface, (18, 22, 25), (122, gantry_y + 5), (878, gantry_y + 5), 3)
    for gx in (145, 855):
        pygame.draw.rect(surface, (35, 42, 45), (gx - 5, gantry_y, 10, 244))
        pygame.draw.rect(surface, (16, 18, 20), (gx - 2, gantry_y + 8, 4, 232))
    sign = pygame.Rect(WIDTH // 2 - 240, gantry_y - 50, 480, 42)
    pygame.draw.rect(surface, (12, 15, 18), sign, border_radius=3)
    pygame.draw.rect(surface, (70, 83, 88), sign, 2, border_radius=3)
    sign_txt = font_terminal.render("CHECKPOINT 12  //  ROUTE 12", True, (195, 190, 150))
    surface.blit(sign_txt, (sign.centerx - sign_txt.get_width() // 2, sign.y + 10))
    alert = font_terminal_small.render("PUBLIC LABEL: SUSPECTED MAG BOMBING", True, (176, 132, 58))
    surface.blit(alert, (sign.centerx - alert.get_width() // 2, sign.bottom + 10))

    # Toll booths, varied and damaged instead of repeated boxes.
    booths = [
        (185, road_far_y - 42, 110, 132, True),
        (382, road_far_y - 16, 92, 112, False),
        (565, road_far_y - 18, 96, 116, True),
        (748, road_far_y - 40, 108, 130, False),
    ]
    for i, (bx, by, bw, bh, broken) in enumerate(booths):
        pygame.draw.rect(surface, (21, 24, 27), (bx + 8, by + 10, bw, bh))
        pygame.draw.rect(surface, (53, 63, 66), (bx, by, bw, bh))
        pygame.draw.rect(surface, (98, 108, 112), (bx, by, bw, bh), 2)
        pygame.draw.rect(surface, (5, 9, 12), (bx + 16, by + 28, bw - 32, 34))
        if broken:
            pygame.draw.line(surface, (140, 42, 34), (bx + 4, by + bh - 8), (bx + bw - 5, by + 20), 4)
            pygame.draw.polygon(surface, (16, 18, 20), [(bx + bw - 28, by), (bx + bw, by + 8), (bx + bw - 8, by + 35)])
        if i == 1:
            pygame.draw.circle(surface, (235, 92, 34), (bx + bw - 10, by + 12), 5)
            glow = pygame.Surface((46, 46), pygame.SRCALPHA)
            pygame.draw.circle(glow, (235, 92, 34, 65), (23, 23), 20)
            surface.blit(glow, (bx + bw - 33, by - 11))

    # Burned KRAP flag: left focal anchor.
    pole_x = 85
    pygame.draw.line(surface, (55, 58, 60), (pole_x, road_far_y - 160), (pole_x, road_far_y + 112), 5)
    flag = [(pole_x, road_far_y - 158), (pole_x + 108, road_far_y - 144), (pole_x + 82, road_far_y - 92), (pole_x, road_far_y - 104)]
    pygame.draw.polygon(surface, C_KRAP_BLUE, flag)
    pygame.draw.polygon(surface, (5, 5, 6), [(pole_x + 76, road_far_y - 139), (pole_x + 108, road_far_y - 144), (pole_x + 82, road_far_y - 92), (pole_x + 60, road_far_y - 98)])

    # Wrecks/abandoned cars in foreground.
    for wx, wy, ww, wh, col in [
        (245, road_near_y - 68, 120, 44, (52, 42, 34)),
        (655, road_near_y - 58, 138, 48, (62, 48, 38)),
    ]:
        pygame.draw.rect(surface, (0, 0, 0), (wx + 5, wy + 8, ww, wh), border_radius=5)
        pygame.draw.rect(surface, col, (wx, wy, ww, wh), border_radius=5)
        pygame.draw.rect(surface, (105, 82, 58), (wx, wy, ww, wh), 2, border_radius=5)
        pygame.draw.circle(surface, (8, 8, 9), (wx + 18, wy + wh), 10)
        pygame.draw.circle(surface, (8, 8, 9), (wx + ww - 18, wy + wh), 10)

    # KRAP van/headlights entering from screen-left, implying the squad arrival.
    van_x, van_y = 35, road_near_y - 78
    pygame.draw.rect(surface, (22, 29, 38), (van_x, van_y, 132, 54), border_radius=5)
    pygame.draw.rect(surface, C_KRAP_BLUE, (van_x + 14, van_y + 14, 72, 8))
    pygame.draw.rect(surface, (195, 205, 205), (van_x + 14, van_y + 24, 72, 2))
    pygame.draw.rect(surface, (7, 10, 13), (van_x + 92, van_y + 10, 30, 24), border_radius=2)
    for ly in (van_y + 18, van_y + 34):
        beam = pygame.Surface((360, 80), pygame.SRCALPHA)
        pygame.draw.polygon(beam, (210, 210, 145, 28), [(0, 20), (340, -10), (340, 58), (0, 36)])
        surface.blit(beam, (van_x + 124, ly - 20))
        pygame.draw.circle(surface, (230, 220, 140), (van_x + 126, ly), 5)

    # Small squad silhouettes staged above the dialogue box.
    squad_y = road_near_y - 78
    for i, sx in enumerate((430, 458, 486, 520)):
        pygame.draw.ellipse(surface, (0, 0, 0, 70), (sx - 12, squad_y + 13, 24, 8))
        body_col = C_PLAYER_UNIFORM if i == 0 else C_KRAP_UNIFORM
        pygame.draw.rect(surface, body_col, (sx - 7, squad_y - 8, 14, 22), border_radius=3)
        pygame.draw.circle(surface, C_PLAYER_SKIN, (sx, squad_y - 14), 7)
        pygame.draw.line(surface, (18, 18, 20), (sx + 7, squad_y - 2), (sx + 26, squad_y - 10), 3)

    # Smoke, sparks, and subtle warning lights.
    rng = random.Random(902)
    for i in range(12):
        sx = rng.randint(130, 880)
        sy = road_far_y - rng.randint(12, 118)
        drift = math.sin(t * 0.0016 + i) * 18
        for r in range(48, 10, -9):
            sm = pygame.Surface((r * 2, r * 2), pygame.SRCALPHA)
            pygame.draw.circle(sm, (45, 45, 45, max(10, 44 - r // 2)), (r, r), r)
            surface.blit(sm, (sx + drift - r, sy - i * 7 - r))
    if int(t / 250) % 2 == 0:
        pygame.draw.circle(surface, (255, 90, 35), (402, road_far_y - 4), 4)
        pygame.draw.circle(surface, (255, 90, 35), (665, road_far_y + 12), 3)

    # A low fog band gives depth and separates the scene from dialogue UI.
    fog = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
    for i in range(80):
        a = int(36 * (i / 80))
        pygame.draw.line(fog, (18, 22, 26, a), (0, road_near_y - 30 + i), (WIDTH, road_near_y - 30 + i))
    surface.blit(fog, (0, 0))


def draw_route12_tanker(surface, t):
    _draw_route12_checkpoint_base(surface, t, tanker=True)


def draw_route12_broadcast(surface, t):
    """Readable TV-broadcast cutscene for the Route 12 frame-up."""
    # TV studio / emergency broadcast background. Make this bright enough that it
    # never reads as an empty black screen behind the dialogue box.
    draw_sky_gradient(surface, (24, 18, 18), (62, 42, 34))
    stage_y = SCENE_TOP + 82
    pygame.draw.rect(surface, (42, 25, 22), (0, stage_y, WIDTH, SCENE_BOT - stage_y))
    # Broadcast monitor glow.
    glow = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
    pygame.draw.circle(glow, (160, 45, 35, 55), (WIDTH // 2, SCENE_TOP + 265), 360)
    pygame.draw.circle(glow, (255, 190, 90, 34), (WIDTH // 2, SCENE_TOP + 210), 250)
    surface.blit(glow, (0, 0))
    # Flags / pillars.
    for x in (80, 185, WIDTH - 255, WIDTH - 150):
        pygame.draw.rect(surface, (35, 42, 62), (x, stage_y + 18, 46, 395))
        pygame.draw.rect(surface, C_KRAP_BLUE, (x + 6, stage_y + 24, 14, 360))
        pygame.draw.rect(surface, (140, 35, 30), (x + 24, stage_y + 24, 14, 360))
    # Large red broadcast header.
    header = pygame.Rect(120, SCENE_TOP + 42, WIDTH - 240, 54)
    pygame.draw.rect(surface, (92, 17, 15), header, border_radius=4)
    pygame.draw.rect(surface, (210, 70, 45), header, 2, border_radius=4)
    htxt = font_speaker.render("ACARISTAN STATE ADDRESS — ROUTE 12", True, (255, 230, 205))
    surface.blit(htxt, (header.centerx - htxt.get_width() // 2, header.y + 12))
    # Podium higher in the frame so it is visible above the dialogue UI.
    podium_y = SCENE_TOP + 430
    pygame.draw.rect(surface, (82, 60, 46), (WIDTH // 2 - 230, podium_y - 120, 460, 130), border_radius=7)
    pygame.draw.rect(surface, (155, 122, 82), (WIDTH // 2 - 230, podium_y - 120, 460, 130), 3, border_radius=7)
    seal = pygame.Rect(WIDTH // 2 - 78, podium_y - 96, 156, 58)
    pygame.draw.rect(surface, (35, 28, 24), seal, border_radius=4)
    seal_txt = font_terminal.render("IPA / STATE", True, (230, 205, 150))
    surface.blit(seal_txt, (seal.centerx - seal_txt.get_width() // 2, seal.y + 18))
    # President and Balaceanu are now large readable figures, not tiny silhouettes.
    figures = [
        (WIDTH // 2 - 115, (30, 36, 55), (185, 35, 34), "PRESIDENT\nRETARDOVICI"),
        (WIDTH // 2 + 130, (46, 31, 26), (130, 35, 28), "BALACEANU"),
    ]
    for cx, suit_col, tie_col, name in figures:
        # Shadow
        pygame.draw.ellipse(surface, (0, 0, 0, 90), (cx - 54, podium_y - 22, 108, 24))
        # Body/head
        pygame.draw.rect(surface, suit_col, (cx - 46, podium_y - 215, 92, 142), border_radius=10)
        pygame.draw.rect(surface, (16, 18, 22), (cx - 46, podium_y - 215, 92, 142), 2, border_radius=10)
        pygame.draw.circle(surface, (202, 164, 126), (cx, podium_y - 246), 36)
        pygame.draw.arc(surface, (42, 28, 20), (cx - 35, podium_y - 281, 70, 70), math.pi, math.tau, 8)
        pygame.draw.polygon(surface, tie_col, [(cx - 10, podium_y - 198), (cx + 10, podium_y - 198), (cx, podium_y - 110)])
        pygame.draw.circle(surface, (18, 18, 18), (cx - 12, podium_y - 250), 3)
        pygame.draw.circle(surface, (18, 18, 18), (cx + 12, podium_y - 250), 3)
        pygame.draw.line(surface, (70, 35, 30), (cx - 12, podium_y - 229), (cx + 12, podium_y - 229), 2)
        # Microphones
        for mx in (-18, 18):
            pygame.draw.line(surface, (10, 10, 12), (cx + mx, podium_y - 80), (cx + mx // 2, podium_y - 128), 3)
            pygame.draw.circle(surface, (8, 8, 10), (cx + mx // 2, podium_y - 130), 7)
        for j, line in enumerate(name.split("\n")):
            nt = font_terminal_small.render(line, True, (240, 220, 190))
            surface.blit(nt, (cx - nt.get_width() // 2, podium_y - 58 + j * 15))
    # Lower-third is high enough not to be hidden by the game's dialogue box.
    chy = pygame.Rect(0, SCENE_BOT - 95, WIDTH, 42)
    pygame.draw.rect(surface, (115, 18, 16), chy)
    pygame.draw.line(surface, (245, 120, 70), (0, chy.y), (WIDTH, chy.y), 2)
    txt = font_terminal.render("BREAKING: KRAP BLAMED FOR ROUTE 12 DISASTER", True, (255, 235, 210))
    surface.blit(txt, (WIDTH // 2 - txt.get_width() // 2, chy.y + 10))
    # TV scan bands/noise.
    for y in range(0, HEIGHT, 5):
        pygame.draw.line(surface, (0, 0, 0, 28), (0, y), (WIDTH, y))
    if int(t // 90) % 2 == 0:
        pygame.draw.rect(surface, (255, 255, 255, 18), (0, SCENE_TOP + 120, WIDTH, 3))


def draw_ipa_radio_chatter(surface, t):
    """M2 ending shot: IPA dispatch radio ordering Biribel's capture.

    A cold blue IPA dispatch console. The text reads out as a single
    urgent transmission, with status indicators (REC, AUTHORIZATION
    CODE, etc.) framing the message. No camera motion -- this is a
    static "we are hearing them on the radio" shot.
    """
    # Cold IPA-blue ambient.
    _draw_vertical_gradient(surface, 0, 0, WIDTH, HEIGHT, (4, 8, 14), (2, 4, 8))
    # Subtle scanline noise.
    rng = random.Random(t // 3)
    for _ in range(40):
        sx = rng.randint(0, WIDTH - 1)
        sy = rng.randint(0, HEIGHT - 1)
        v = rng.randint(8, 28)
        surface.set_at((sx, sy), (v, v + 4, v + 8))

    # Dispatch console (large, centered).
    panel_w, panel_h = 720, 320
    panel_x = WIDTH // 2 - panel_w // 2
    panel_y = HEIGHT // 2 - panel_h // 2 + 10
    # Outer bezel.
    pygame.draw.rect(surface, (12, 18, 24),
                     (panel_x - 10, panel_y - 10, panel_w + 20, panel_h + 20),
                     border_radius=4)
    pygame.draw.rect(surface, (30, 50, 65),
                     (panel_x - 10, panel_y - 10, panel_w + 20, panel_h + 20),
                     2, border_radius=4)
    # Screen inset (the dispatch display).
    pygame.draw.rect(surface, (6, 12, 20),
                     (panel_x, panel_y, panel_w, panel_h))
    pygame.draw.rect(surface, (22, 40, 55),
                     (panel_x, panel_y, panel_w, panel_h), 1)
    # Scanlines (every 2px on the display).
    for sy in range(panel_y + 2, panel_y + panel_h - 2, 2):
        pygame.draw.line(surface, (8, 14, 22),
                         (panel_x + 2, sy), (panel_x + panel_w - 2, sy), 1)

    # Top status bar: IPA DISPATCH | REC.
    bar_y = panel_y + 4
    pygame.draw.rect(surface, (28, 50, 70),
                     (panel_x + 4, bar_y, panel_w - 8, 18))
    head = font_speaker.render("IPA DISPATCH  \u00b7  CHANNEL 7", True, (180, 220, 240))
    surface.blit(head, (panel_x + 14, bar_y + 2))
    rec_pulse = 0.5 + 0.5 * math.sin(t * 0.4)
    if rec_pulse > 0.4:
        rec_dot = font_terminal_small.render("\u25cf REC", True, (220, 50, 50))
        surface.blit(rec_dot, (panel_x + panel_w - rec_dot.get_width() - 14, bar_y + 4))

    # Main message (centered on the dispatch display).
    msg_y = panel_y + 60
    # Hand-set as two lines so the dispatch reads as a real radio order.
    line1 = font_dialogue.render("All units. The KRAP operator is the primary suspect.",
                                 True, (200, 230, 245))
    line2 = font_dialogue.render("Bring him in. Authorization IPA-Code Omega.",
                                 True, (220, 240, 255))
    surface.blit(line1, (panel_x + panel_w // 2 - line1.get_width() // 2, msg_y))
    surface.blit(line2, (panel_x + panel_w // 2 - line2.get_width() // 2, msg_y + 40))

    # Bottom status: a classification bar (red -- "FLAGGED TARGET").
    foot_y = panel_y + panel_h - 30
    pygame.draw.rect(surface, (110, 30, 30),
                     (panel_x + 4, foot_y, panel_w - 8, 22))
    foot = font_terminal_small.render(
        "FLAGGED TARGET  \u00b7  KRAP OPERATOR  \u00b7  ACUTE",
        True, (240, 220, 200),
    )
    surface.blit(foot, (panel_x + panel_w // 2 - foot.get_width() // 2,
                         foot_y + 5))

    # A second red ALERT banner below the panel (urgent framing).
    alert_y = panel_y + panel_h + 30
    alert = font_terminal_small.render(
        "\u26a0  PRIORITY ALPHA  \u00b7  ALL FIELD UNITS  \u26a0",
        True, (220, 80, 80),
    )
    alert.set_alpha(int(180 + 60 * math.sin(t * 0.3)))
    surface.blit(alert, (WIDTH // 2 - alert.get_width() // 2, alert_y))


def draw_krap_door_kickin(surface, t):
    """M2 ending shot: KRAP safehouse door being kicked in. Visual only.

    Sequence (driven by t):
      0-1.5s   Closed door, faint blue lights flashing outside the frame
      1.5-3s   Door splinters inward, blue lights wash in
      3-4.5s   Silhouettes pour in (IPA boots the door), hands grab Biribel
      4.5-6s   Fades to black (the screen goes dark as he's taken)

    No dialogue. The visuals tell the story. Vasile's voice (from the
    next shot) does the emotional work.
    """
    # Phase 0-1.5s: closed door. Phases 1.5-3s: door breaks. 3-4.5s:
    # silhouettes rush in. 4.5-6s: black.
    phase = min(1.0, t / 360.0)  # 6s shot, normalize to 0..1

    # Dim warm apartment behind the door.
    _draw_vertical_gradient(surface, 0, 0, WIDTH, HEIGHT, (12, 10, 8), (4, 3, 3))

    # A wood door in the center (large, takes up ~half the screen).
    door_w, door_h = 280, 480
    door_x = WIDTH // 2 - door_w // 2
    door_y = HEIGHT // 2 - door_h // 2 + 20
    if phase < 0.25:
        # Door intact.
        pygame.draw.rect(surface, (44, 28, 16), (door_x, door_y, door_w, door_h))
        # Wood grain.
        for gy in range(door_y, door_y + door_h, 12):
            rng = random.Random(gy * 7)
            c = 50 + rng.randint(-6, 6)
            pygame.draw.line(surface, (c, int(c * 0.6), int(c * 0.3)),
                             (door_x, gy), (door_x + door_w, gy), 1)
        # Door panels (two rectangles).
        pygame.draw.rect(surface, (28, 18, 10),
                         (door_x + 24, door_y + 30, door_w - 48, door_h // 2 - 50),
                         border_radius=2)
        pygame.draw.rect(surface, (28, 18, 10),
                         (door_x + 24, door_y + door_h // 2 + 20,
                          door_w - 48, door_h // 2 - 50),
                         border_radius=2)
        # Door handle.
        pygame.draw.circle(surface, (180, 150, 90),
                           (door_x + door_w - 30, door_y + door_h // 2), 6)
    elif phase < 0.5:
        # Door splinters inward.
        splinter_t = (phase - 0.25) / 0.25  # 0..1
        # Splinter lines (cracks spreading).
        for i in range(8):
            rng = random.Random(i * 13)
            sx = door_x + rng.randint(20, door_w - 20)
            sy = door_y + rng.randint(20, door_h - 20)
            ex = door_x + rng.randint(0, door_w)
            ey = door_y + rng.randint(0, door_h)
            pygame.draw.line(surface, (10, 6, 4),
                             (sx, sy), (ex, ey), 2)
        # Door swung inward (now at an angle).
        swing = int(splinter_t * 35)
        door_pts = [
            (door_x, door_y),
            (door_x + door_w, door_y),
            (door_x + door_w - swing, door_y + door_h),
            (door_x + swing, door_y + door_h),
        ]
        pygame.draw.polygon(surface, (44, 28, 16), door_pts)
        # Bright blue light floods through the gap.
        gap_pts = [
            (door_x + door_w - swing, door_y),
            (door_x + door_w, door_y),
            (door_x + door_w, door_y + door_h),
            (door_x + door_w - swing, door_y + door_h),
        ]
        light = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        pygame.draw.polygon(light, (40, 90, 180, int(200 * splinter_t)), gap_pts)
        surface.blit(light, (0, 0))
    else:
        # Door is open / gone. Blue light fills the frame.
        blue_t = min(1.0, (phase - 0.5) / 0.4)
        _draw_light_cone(surface, WIDTH // 2, HEIGHT // 2 + 40, 500,
                         (60, 110, 200), alpha=int(160 * blue_t))
        # Silhouettes rushing in (IPA, 4 of them, from the door).
        ipa_count = 4
        for i in range(ipa_count):
            sx = door_x + 30 + i * 60 + (i % 2) * 20
            sy = HEIGHT - 60 - i * 5
            # Body silhouette (taller than the door frame).
            pygame.draw.polygon(surface, (3, 5, 8), [
                (sx - 24, sy + 100),
                (sx + 24, sy + 100),
                (sx + 30, sy + 200),
                (sx - 30, sy + 200),
            ])
            pygame.draw.circle(surface, (3, 5, 8), (sx, sy + 84), 16)
            # IPA collar / insignia (a thin bright strip).
            pygame.draw.rect(surface, (160, 200, 230),
                             (sx - 6, sy + 110, 12, 4))
        # One silhouette on the left is grabbing Biribel (a smaller
        # silhouette in front, being pulled).
        bx, by = door_x + 40, HEIGHT - 90
        pygame.draw.polygon(surface, (8, 6, 10), [
            (bx - 18, by), (bx + 18, by),
            (bx + 22, by + 70), (bx - 22, by + 70),
        ])
        pygame.draw.circle(surface, (10, 8, 12), (bx, by - 14), 12)
        # Hands grabbing him (the IPA silhouette's arms extending).
        pygame.draw.line(surface, (3, 5, 8),
                         (bx + 18, by + 10), (sx + 24, sy + 110), 4)
        pygame.draw.line(surface, (3, 5, 8),
                         (bx + 18, by + 20), (sx + 24, sy + 130), 4)
        # Last phase: fade to black.
        if phase > 0.85:
            fade = (phase - 0.85) / 0.15
            black = pygame.Surface((WIDTH, HEIGHT))
            black.fill((0, 0, 0))
            black.set_alpha(int(255 * fade))
            surface.blit(black, (0, 0))

    # IPA blue lights flashing on the walls (always present, pulses).
    light_pulse = 0.6 + 0.4 * math.sin(t * 0.3)
    _draw_light_cone(surface, WIDTH // 2 + 100, HEIGHT // 2, 200,
                     (40, 80, 160), alpha=int(60 * light_pulse))


def draw_biribel_blackout(surface, t):
    """M2 ending shot: Vasile's voice fades as Biribel is dragged away.

    Black screen with a small radio showing the dying signal. The
    dialogue text fades in and out as Vasile's voice breaks up.
    Mirrors the M2 cutscene aesthetic (no camera transform -- this
    is a clean cinematic beat, not an interactive intro shot).
    """
    # Pure black.
    surface.fill((2, 2, 3))

    # Small radio device at the bottom-left.
    radio_x, radio_y = 100, HEIGHT - 200
    pygame.draw.rect(surface, (22, 22, 26),
                     (radio_x, radio_y, 130, 70), border_radius=4)
    pygame.draw.rect(surface, (45, 45, 50),
                     (radio_x, radio_y, 130, 70), 2, border_radius=4)
    # Speaker grille.
    for gy in range(radio_y + 10, radio_y + 42, 5):
        for gx in range(radio_x + 10, radio_x + 70, 5):
            pygame.draw.circle(surface, (8, 8, 10), (gx, gy), 1)
    # Frequency window (LCD strip).
    pygame.draw.rect(surface, (40, 60, 30), (radio_x + 78, radio_y + 10, 44, 16))
    freq = font_terminal_small.render("87.5", True, (110, 200, 130))
    surface.blit(freq, (radio_x + 84, radio_y + 12))
    # Tuning knob.
    pygame.draw.circle(surface, (35, 35, 40), (radio_x + 100, radio_y + 50), 10)
    pygame.draw.line(surface, (90, 90, 95),
                     (radio_x + 100, radio_y + 50),
                     (radio_x + 100 + int(math.cos(t * 0.06) * 6),
                      radio_y + 50 + int(math.sin(t * 0.06) * 6)), 1)
    # LED.
    led_pulse = 0.4 + 0.6 * math.sin(t * 0.15)  # pulse slows as signal dies
    led_color = (int(80 + 100 * led_pulse), int(15 + 20 * led_pulse),
                 int(15 + 20 * led_pulse))
    pygame.draw.circle(surface, led_color, (radio_x + 118, radio_y + 14), 3)
    _draw_light_cone(surface, radio_x + 118, radio_y + 14, 50,
                     (200, 40, 40), alpha=int(40 * led_pulse))

    # Waveform (the dying signal).
    wave_x = radio_x + 10
    wave_y = radio_y - 28
    wave_w, wave_h = 120, 22
    pygame.draw.rect(surface, (12, 18, 14),
                     (wave_x - 2, wave_y - 2, wave_w + 4, wave_h + 4))
    pygame.draw.rect(surface, (35, 50, 38),
                     (wave_x - 2, wave_y - 2, wave_w + 4, wave_h + 4), 1)
    # Amplitude decays over time (the signal is dying).
    amp = max(0.1, 0.9 - (t / 240.0))
    pts = []
    for i in range(wave_w):
        n = (math.sin(t * 0.4 + i * 0.5) * 0.4
             + math.sin(t * 0.7 + i * 0.9) * 0.3
             + (random.Random(t // 3 + i).random() - 0.5) * 0.5)
        py = wave_y + wave_h // 2 + int(n * amp * (wave_h // 2 - 2))
        pts.append((wave_x + i, py))
    if len(pts) > 1:
        pygame.draw.lines(surface, (110, 200, 130), False, pts, 1)
    pygame.draw.line(surface, (40, 60, 45),
                     (wave_x, wave_y + wave_h // 2),
                     (wave_x + wave_w, wave_y + wave_h // 2), 1)
    # Signal label.
    wave_lbl = font_terminal_small.render(
        "RX  \u00b7  CH 7  \u00b7  NO SIGNAL", True, (80, 120, 90))
    surface.blit(wave_lbl, (wave_x, wave_y - 18))
    # Callsign.
    callsign = font_terminal_small.render(
        "VASILE  \u00b7  KRAP FIELD UNIT", True, (70, 100, 80))
    surface.blit(callsign, (wave_x, wave_y + wave_h + 2))


def draw_route12_aftermath(surface, t):
    _draw_route12_checkpoint_base(surface, t, tanker=True)
    fire = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
    for i in range(16):
        x = 90 + i * 58 + math.sin(t * 0.003 + i) * 16
        y = GROUND_Y - 80 + (i % 3) * 18
        pygame.draw.circle(fire, (255, 95, 25, 58), (int(x), int(y)), 44)
        pygame.draw.circle(fire, (255, 190, 70, 70), (int(x), int(y + 10)), 20)
    surface.blit(fire, (0, 0))
    draw_biribel(surface, WIDTH // 2 + 25, GROUND_Y + 8, scale=0.82, facing_right=False, in_silhouette=True)


# ─────────────────────────────────────
# Mission 3 — Stabilization Center scene renderers
# ─────────────────────────────────────
# Four procedural scenes for the M3 intro cutscene. Purely visual — no
# new art assets needed. All reuse the existing character renderers
# (draw_biribel, draw_volkov), the light-cone helper, and gradient tools.


def _m3_clamp01(v):
    return max(0.0, min(1.0, float(v)))


def _m3_smooth(v):
    v = _m3_clamp01(v)
    return v * v * (3.0 - 2.0 * v)


def _m3_noise(surface, seed, count=80, alpha=26, region=None):
    """Deterministic dust/grime pass.

    The old M3 intro used live random jitter in a few shots, which made the
    image shimmer like a generated placeholder. These specks are seeded, so the
    scene feels filmed rather than regenerated every frame.
    """
    rng = random.Random(seed)
    if region is None:
        x0, y0, w, h = 0, SCENE_TOP, WIDTH, SCENE_BOT - SCENE_TOP
    else:
        x0, y0, w, h = region
    for _ in range(count):
        x = x0 + rng.randint(0, max(1, w - 1))
        y = y0 + rng.randint(0, max(1, h - 1))
        r = rng.randint(1, 2)
        v = rng.randint(20, 50)
        pygame.draw.circle(surface, (v, v, v + 3, alpha), (x, y), r)


def _m3_soft_light(surface, center, radius, color, alpha, elliptical=0.65, blend=True):
    """Disabled visible wash overlays for the M3 intro.

    The scene art already has enough contrast from the monitor/tube sprites.
    Big red/blue glow washes made the compositions unreadable, so this helper
    intentionally avoids drawing any large visible shape. Kept as a no-op seam
    so the scene code can stay simple and future lighting can be reintroduced
    in a more controlled way.
    """
    return


def _m3_draw_fluorescent(surface, x, y, w, t, glow_alpha=52):
    """Institutional fluorescent tube.

    No large bloom overlays: keep the shot readable by limiting glow to a
    tight halo immediately around the fixture.
    """
    flicker = 0.86 + 0.10 * math.sin(t * 0.011) + 0.04 * math.sin(t * 0.037)
    flicker = max(0.55, min(1.0, flicker))

    # Tight fixture halo only. This gives the tube intensity without throwing
    # a giant blue rectangle across the scene.
    tight = pygame.Surface((w + 84, 62), pygame.SRCALPHA)
    for i in range(7):
        a = int(glow_alpha * flicker * (1.0 - i / 7.0) * 0.16)
        if a <= 0:
            continue
        rect = pygame.Rect(42 - i * 4, 26 - i * 2, w + i * 8, 9 + i * 4)
        pygame.draw.rect(tight, (185, 205, 215, a), rect, border_radius=7)
    # Normal alpha blit — additive blending ignores alpha on some pygame
    # backends and made this read as another bright overlay block.
    surface.blit(tight, (x - 42, y - 26))

    pygame.draw.rect(surface, (18, 18, 18), (x - 8, y - 8, w + 16, 22), border_radius=3)
    pygame.draw.rect(surface, (65, 70, 72), (x - 4, y - 5, w + 8, 16), 1, border_radius=3)
    tube_col = (int(180 * flicker), int(195 * flicker), int(202 * flicker))
    pygame.draw.rect(surface, tube_col, (x, y, w, 9), border_radius=5)
    pygame.draw.line(surface, (245, 250, 240), (x + 8, y + 2), (x + w - 8, y + 2), 2)
    for cap_x in (x - 12, x + w + 2):
        pygame.draw.rect(surface, (44, 44, 42), (cap_x, y - 2, 12, 13), border_radius=2)


def _m3_draw_seated_biribel(surface, cx, seat_y, scale=1.0, rim=(130, 150, 155)):
    """Restrained Biribel for the M3 intro wide shot.

    The first pass looked like a normal seated silhouette. This version makes
    the restraint read immediately even behind the dialogue panel: tall chair
    back, chest harness, bolted arm rails, oversized cuffs, and taut chains.
    """
    s = scale
    ix = lambda v: int(round(v))

    # Ground shadow / bolted chair footprint.
    pygame.draw.ellipse(surface, (0, 0, 0, 110), (ix(cx - 98*s), ix(seat_y + 38*s), ix(196*s), ix(34*s)))

    frame = (29, 30, 30)
    frame_dark = (10, 10, 11)
    frame_hi = (78, 80, 76)
    strap = (72, 78, 78)
    strap_dark = (22, 24, 24)
    cuff_col = (118, 120, 112)
    cuff_hi = (185, 188, 176)

    # Tall interrogation-chair back. Draw it before the body so it reads as a
    # device, not a normal office chair.
    back = pygame.Rect(ix(cx - 62*s), ix(seat_y - 142*s), ix(124*s), ix(176*s))
    pygame.draw.rect(surface, (0, 0, 0, 95), back.move(ix(8*s), ix(9*s)), border_radius=ix(10*s))
    pygame.draw.rect(surface, frame_dark, back, border_radius=ix(10*s))
    pygame.draw.rect(surface, frame_hi, back, 2, border_radius=ix(10*s))
    # Padded vertical slats / welded seams.
    for off in (-34, 0, 34):
        pygame.draw.line(surface, (38, 40, 40), (ix(cx + off*s), back.y + ix(14*s)), (ix(cx + off*s), back.bottom - ix(12*s)), max(1, ix(2*s)))
    # Head brace behind the skull.
    brace = pygame.Rect(ix(cx - 46*s), ix(seat_y - 132*s), ix(92*s), ix(34*s))
    pygame.draw.rect(surface, (20, 21, 21), brace, border_radius=ix(7*s))
    pygame.draw.rect(surface, (84, 86, 82), brace, 1, border_radius=ix(7*s))

    # Seat and bolted arm rails.
    seat = pygame.Rect(ix(cx - 66*s), ix(seat_y + 12*s), ix(132*s), ix(33*s))
    pygame.draw.rect(surface, frame, seat, border_radius=ix(6*s))
    pygame.draw.rect(surface, frame_hi, seat, 1, border_radius=ix(6*s))

    rail_y = seat_y - 4*s
    for side in (-1, 1):
        rail = pygame.Rect(ix(cx + side*42*s), ix(rail_y - 10*s), ix(side*126*s), ix(22*s))
        if rail.w < 0:
            rail.x += rail.w
            rail.w = -rail.w
        pygame.draw.rect(surface, (0, 0, 0, 80), rail.move(ix(4*s), ix(5*s)), border_radius=ix(5*s))
        pygame.draw.rect(surface, frame, rail, border_radius=ix(5*s))
        pygame.draw.rect(surface, frame_hi, rail, 1, border_radius=ix(5*s))
        # Anchor plate at the far end.
        plate = pygame.Rect(0, 0, ix(30*s), ix(28*s))
        plate.center = (ix(cx + side*162*s), ix(rail_y))
        pygame.draw.rect(surface, (24, 24, 23), plate, border_radius=ix(4*s))
        pygame.draw.rect(surface, (93, 90, 82), plate, 1, border_radius=ix(4*s))
        pygame.draw.circle(surface, (120, 116, 104), (plate.centerx, plate.centery), max(2, ix(3*s)))

    # Hunched body, locked against the chair.
    body = [
        (ix(cx - 42*s), ix(seat_y - 68*s)),
        (ix(cx + 42*s), ix(seat_y - 68*s)),
        (ix(cx + 51*s), ix(seat_y + 19*s)),
        (ix(cx - 51*s), ix(seat_y + 19*s)),
    ]
    pygame.draw.polygon(surface, (7, 8, 10), body)
    pygame.draw.line(surface, rim, (ix(cx + 41*s), ix(seat_y - 62*s)), (ix(cx + 48*s), ix(seat_y + 12*s)), max(1, ix(2*s)))

    # Chest harness: two diagonals + a horizontal belt. This is the main cue
    # that he is strapped down, and it sits above the dialogue box.
    pygame.draw.line(surface, strap, (ix(cx - 44*s), ix(seat_y - 58*s)), (ix(cx + 43*s), ix(seat_y + 9*s)), max(3, ix(7*s)))
    pygame.draw.line(surface, strap_dark, (ix(cx - 44*s), ix(seat_y - 58*s)), (ix(cx + 43*s), ix(seat_y + 9*s)), max(1, ix(2*s)))
    pygame.draw.line(surface, strap, (ix(cx + 44*s), ix(seat_y - 58*s)), (ix(cx - 43*s), ix(seat_y + 9*s)), max(3, ix(7*s)))
    pygame.draw.line(surface, strap_dark, (ix(cx + 44*s), ix(seat_y - 58*s)), (ix(cx - 43*s), ix(seat_y + 9*s)), max(1, ix(2*s)))
    belt = pygame.Rect(ix(cx - 56*s), ix(seat_y - 24*s), ix(112*s), ix(15*s))
    pygame.draw.rect(surface, strap, belt, border_radius=ix(3*s))
    pygame.draw.rect(surface, strap_dark, belt, 1, border_radius=ix(3*s))
    buckle = pygame.Rect(0, 0, ix(20*s), ix(15*s))
    buckle.center = belt.center
    pygame.draw.rect(surface, cuff_hi, buckle, 1, border_radius=ix(2*s))

    # Bowed head and neck shadow. A normal upright head read too relaxed.
    head_y = seat_y - 96*s
    pygame.draw.circle(surface, (13, 12, 12), (ix(cx), ix(head_y)), ix(27*s))
    pygame.draw.ellipse(surface, (34, 28, 24), (ix(cx - 26*s), ix(head_y - 27*s), ix(52*s), ix(30*s)))
    pygame.draw.arc(surface, rim, (ix(cx - 31*s), ix(head_y - 24*s), ix(62*s), ix(58*s)), math.pi * 0.08, math.pi * 0.92, max(1, ix(2*s)))
    # Chin down / face mostly in shadow.
    pygame.draw.arc(surface, (76, 58, 48), (ix(cx - 17*s), ix(head_y - 3*s), ix(34*s), ix(22*s)), 0, math.pi, max(1, ix(2*s)))

    # Arms are not posed casually — they are pinned to rails, palms down.
    for side in (-1, 1):
        shoulder = (ix(cx + side * 37*s), ix(seat_y - 51*s))
        elbow = (ix(cx + side * 83*s), ix(seat_y - 26*s))
        wrist = (ix(cx + side * 136*s), ix(rail_y - 1*s))
        pygame.draw.line(surface, (6, 7, 8), shoulder, elbow, max(5, ix(13*s)))
        pygame.draw.line(surface, (6, 7, 8), elbow, wrist, max(5, ix(13*s)))
        pygame.draw.line(surface, (35, 37, 38), shoulder, elbow, max(1, ix(3*s)))
        pygame.draw.line(surface, (35, 37, 38), elbow, wrist, max(1, ix(3*s)))

        # Large rectangular wrist cuff, bright enough to read in the dark.
        cuff = pygame.Rect(0, 0, ix(42*s), ix(17*s))
        cuff.center = wrist
        pygame.draw.rect(surface, (0, 0, 0, 90), cuff.move(ix(2*s), ix(3*s)), border_radius=ix(4*s))
        pygame.draw.rect(surface, cuff_col, cuff, border_radius=ix(4*s))
        pygame.draw.rect(surface, cuff_hi, cuff, 2, border_radius=ix(4*s))
        pygame.draw.line(surface, (48, 48, 45), (cuff.x + ix(6*s), cuff.centery), (cuff.right - ix(6*s), cuff.centery), max(1, ix(2*s)))

        # Taut chain from cuff to anchor plate.
        anchor = (ix(cx + side * 164*s), ix(rail_y))
        for j in range(4):
            q = (j + 0.5) / 4
            lx = wrist[0] + (anchor[0] - wrist[0]) * q
            ly = wrist[1] + (anchor[1] - wrist[1]) * q
            link = pygame.Rect(ix(lx - 5*s), ix(ly - 4*s), ix(10*s), ix(8*s))
            pygame.draw.ellipse(surface, (45, 45, 44), link, max(1, ix(2*s)))
            pygame.draw.ellipse(surface, (132, 128, 116), link, 1)

    # Foot shackles barely peek above the lower caption on some shots; useful
    # in full-screen and harmless when hidden.
    for side in (-1, 1):
        ankle = pygame.Rect(0, 0, ix(31*s), ix(11*s))
        ankle.center = (ix(cx + side*29*s), ix(seat_y + 53*s))
        pygame.draw.rect(surface, cuff_col, ankle, border_radius=ix(3*s))
        pygame.draw.rect(surface, cuff_hi, ankle, 1, border_radius=ix(3*s))



def _m3_draw_balaceanu(surface, cx, foot_y, scale=1.0, facing_left=True):
    """Simple but specific Balaceanu figure: tailored suit, red tie, rigid posture."""
    s = scale
    d = -1 if facing_left else 1
    pygame.draw.ellipse(surface, (0, 0, 0, 85), (int(cx - 42*s), int(foot_y - 9*s), int(84*s), int(18*s)))
    # Legs / shoes.
    pygame.draw.rect(surface, (17, 17, 20), (int(cx - 23*s), int(foot_y - 92*s), int(18*s), int(92*s)))
    pygame.draw.rect(surface, (17, 17, 20), (int(cx + 5*s), int(foot_y - 92*s), int(18*s), int(92*s)))
    pygame.draw.ellipse(surface, (9, 8, 8), (int(cx - 36*s), int(foot_y - 8*s), int(36*s), int(12*s)))
    pygame.draw.ellipse(surface, (9, 8, 8), (int(cx + 4*s), int(foot_y - 8*s), int(36*s), int(12*s)))
    # Suit.
    pygame.draw.polygon(surface, (34, 28, 27), [
        (int(cx - 46*s), int(foot_y - 212*s)),
        (int(cx + 46*s), int(foot_y - 212*s)),
        (int(cx + 36*s), int(foot_y - 88*s)),
        (int(cx - 36*s), int(foot_y - 88*s)),
    ])
    pygame.draw.line(surface, (78, 54, 46), (int(cx - 39*s), int(foot_y - 204*s)), (int(cx - 30*s), int(foot_y - 96*s)), max(1, int(2*s)))
    pygame.draw.line(surface, (78, 54, 46), (int(cx + 39*s), int(foot_y - 204*s)), (int(cx + 30*s), int(foot_y - 96*s)), max(1, int(2*s)))
    pygame.draw.polygon(surface, (135, 31, 28), [(int(cx - 8*s), int(foot_y - 192*s)), (int(cx + 8*s), int(foot_y - 192*s)), (int(cx), int(foot_y - 102*s))])
    # One hand holds a folder/tablet.
    arm_end = (int(cx + d * 62*s), int(foot_y - 136*s))
    pygame.draw.line(surface, (28, 24, 23), (int(cx + d * 38*s), int(foot_y - 188*s)), arm_end, int(13*s))
    folder = pygame.Rect(0, 0, int(54*s), int(74*s))
    folder.center = (arm_end[0] + int(d * 18*s), arm_end[1] + int(7*s))
    pygame.draw.rect(surface, (68, 52, 36), folder, border_radius=3)
    pygame.draw.rect(surface, (130, 42, 36), folder, 2, border_radius=3)
    label = font_terminal_small.render("VOSTRAL", True, (205, 170, 120))
    label = pygame.transform.smoothscale(label, (max(1, int(label.get_width()*0.65*s)), max(1, int(label.get_height()*0.65*s))))
    surface.blit(label, (folder.centerx - label.get_width()//2, folder.y + int(11*s)))
    # Head.
    pygame.draw.circle(surface, (190, 146, 108), (int(cx), int(foot_y - 246*s)), int(30*s))
    pygame.draw.arc(surface, (35, 24, 20), (int(cx - 30*s), int(foot_y - 276*s), int(60*s), int(54*s)), math.pi, math.tau, int(6*s))
    pygame.draw.circle(surface, (12, 12, 12), (int(cx - 10*s), int(foot_y - 250*s)), max(1, int(2*s)))
    pygame.draw.circle(surface, (12, 12, 12), (int(cx + 10*s), int(foot_y - 250*s)), max(1, int(2*s)))
    pygame.draw.line(surface, (70, 28, 25), (int(cx - 11*s), int(foot_y - 232*s)), (int(cx + 12*s), int(foot_y - 232*s)), max(1, int(2*s)))


def _draw_cell_ceiling(surface, t):
    """Biribel's POV waking up: a real cell ceiling, not an abstract glow."""
    surface.fill((3, 4, 5))
    sec = t / 1000.0
    focus = _m3_smooth(t / 2200.0)

    # Eye opening is intentionally slow and uncomfortable; the previous 60 ms
    # blink made the shot read like a placeholder flash.
    eye_open = 0.10 + 0.90 * _m3_smooth((t - 180) / 1500.0)
    if 760 < t < 1040:
        eye_open *= 0.68  # one involuntary blink
    eye_open = _m3_clamp01(eye_open)

    sway_x = int(math.sin(sec * 0.9) * (5 - 3 * focus))
    sway_y = int(math.sin(sec * 0.63 + 1.7) * (4 - 2 * focus))

    # Concrete ceiling slab with perspective seams.
    top = SCENE_TOP - 20 + sway_y
    bot = SCENE_BOT + 40 + sway_y
    for y in range(top, bot):
        p = (y - top) / max(1, bot - top)
        shade = int(10 + p * 24)
        pygame.draw.line(surface, (shade, shade + 1, shade + 4), (0, y), (WIDTH, y))

    van_x = WIDTH // 2 + sway_x
    for i, x in enumerate((-420, -250, -95, 55, 220, 390)):
        pygame.draw.line(surface, (18, 19, 22), (van_x + x, SCENE_TOP - 20), (van_x + int(x * 1.35), SCENE_BOT + 60), 1)
    for y in (SCENE_TOP + 55, SCENE_TOP + 145, SCENE_TOP + 248, SCENE_TOP + 365, SCENE_TOP + 500):
        pygame.draw.line(surface, (17, 18, 21), (0, y + sway_y), (WIDTH, y + sway_y + int((y - SCENE_TOP) * 0.02)), 1)

    # Old water stains and cracks. Deterministic: no AI-jitter shimmer.
    stain = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
    rng = random.Random(3091)
    for _ in range(16):
        x = rng.randint(80, WIDTH - 80) + sway_x // 2
        y = rng.randint(SCENE_TOP + 30, SCENE_BOT - 90) + sway_y // 2
        w = rng.randint(45, 140)
        h = rng.randint(10, 38)
        pygame.draw.ellipse(stain, (5, 7, 8, rng.randint(25, 54)), (x - w // 2, y - h // 2, w, h))
    cracks = [
        [(WIDTH//2 - 230, SCENE_TOP + 110), (WIDTH//2 - 170, SCENE_TOP + 147), (WIDTH//2 - 130, SCENE_TOP + 210), (WIDTH//2 - 78, SCENE_TOP + 234)],
        [(WIDTH//2 + 130, SCENE_TOP + 330), (WIDTH//2 + 190, SCENE_TOP + 372), (WIDTH//2 + 216, SCENE_TOP + 444)],
        [(WIDTH//2 + 265, SCENE_TOP + 120), (WIDTH//2 + 245, SCENE_TOP + 180), (WIDTH//2 + 275, SCENE_TOP + 235)],
    ]
    crack_a = int(40 + 80 * focus)
    for pts in cracks:
        pts = [(x + sway_x // 2, y + sway_y // 2) for x, y in pts]
        pygame.draw.lines(stain, (4, 5, 6, crack_a), False, pts, 2)
        for x, y in pts[1:-1]:
            pygame.draw.line(stain, (4, 5, 6, crack_a // 2), (x, y), (x + rng.randint(-28, 28), y + rng.randint(14, 38)), 1)
    surface.blit(stain, (0, 0))

    # Security camera / sprinkler: small institutional details sell the room.
    pygame.draw.circle(surface, (19, 21, 23), (WIDTH - 168 + sway_x//3, SCENE_TOP + 92 + sway_y//3), 26)
    pygame.draw.circle(surface, (8, 9, 10), (WIDTH - 168 + sway_x//3, SCENE_TOP + 92 + sway_y//3), 14)
    if int(t // 680) % 2 == 0:
        pygame.draw.circle(surface, (170, 22, 18), (WIDTH - 158 + sway_x//3, SCENE_TOP + 82 + sway_y//3), 3)

    _m3_draw_fluorescent(surface, WIDTH // 2 - 155 + sway_x, SCENE_TOP + 190 + sway_y, 310, t, glow_alpha=64)

    # Unfocused double-image fades out instead of per-frame random blur.
    if focus < 0.75:
        ghost = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        _m3_draw_fluorescent(ghost, WIDTH // 2 - 154 + sway_x + 10, SCENE_TOP + 190 + sway_y - 6, 310, t + 90, glow_alpha=25)
        ghost.set_alpha(int(90 * (1.0 - focus)))
        surface.blit(ghost, (0, 0))

    # Eyelid mask: hard black with a soft inner edge.
    bar_h = int((HEIGHT * 0.50) * (1.0 - eye_open))
    if bar_h > 0:
        pygame.draw.rect(surface, (0, 0, 0), (0, 0, WIDTH, bar_h))
        pygame.draw.rect(surface, (0, 0, 0), (0, HEIGHT - bar_h, WIDTH, bar_h))
        soft = pygame.Surface((WIDTH, 34), pygame.SRCALPHA)
        for i in range(34):
            a = int(150 * (1 - i / 34))
            pygame.draw.line(soft, (0, 0, 0, a), (0, i), (WIDTH, i))
        surface.blit(soft, (0, bar_h - 2))
        surface.blit(pygame.transform.flip(soft, False, True), (0, HEIGHT - bar_h - 32))


def _draw_cell_restraints(surface, t):
    """Close-up of the restraint chair: clinical, physical, and quiet.

    The old version reused chair-break language (sparks, CRITICAL overlays), so
    the intro looked like the later action cutscene. This shot should feel like
    waking up strapped to state property, not already breaking out.
    """
    surface.fill((5, 6, 7))
    sec = t / 1000.0
    settle = _m3_smooth(t / 1400.0)

    # Cold concrete and floor-to-wall split.
    wall_h = SCENE_TOP + 320
    for y in range(SCENE_TOP, SCENE_BOT):
        p = (y - SCENE_TOP) / max(1, SCENE_BOT - SCENE_TOP)
        col = (int(9 + p * 12), int(10 + p * 12), int(12 + p * 14))
        pygame.draw.line(surface, col, (0, y), (WIDTH, y))
    pygame.draw.line(surface, (28, 30, 31), (0, wall_h), (WIDTH, wall_h), 2)
    for x in range(-40, WIDTH + 80, 92):
        pygame.draw.line(surface, (16, 17, 19), (x, SCENE_TOP), (x + 58, wall_h), 1)
    _m3_noise(surface, 5531, 130, alpha=20)

    # No broad red/blue light overlays here. The cuffs, hands, chair arms and
    # background must stay readable; the monitor glow is handled by the actual
    # monitor prop in the following room shot.

    cx = WIDTH // 2
    cy = SCENE_TOP + 382
    trem = math.sin(sec * 8.4) * (1.0 + 1.2 * settle)

    # Metal chair arms / instrument table-like composition.
    for side in (-1, 1):
        rail_x = cx + side * 172
        rail = pygame.Rect(0, 0, 310, 54)
        rail.center = (rail_x, cy + 18)
        pygame.draw.rect(surface, (0, 0, 0, 85), rail.move(7, 9), border_radius=10)
        pygame.draw.rect(surface, (31, 31, 30), rail, border_radius=10)
        pygame.draw.rect(surface, (75, 72, 66), rail, 2, border_radius=10)
        pygame.draw.line(surface, (95, 92, 84), (rail.x + 12, rail.y + 8), (rail.right - 12, rail.y + 8), 1)
        for bx in (rail.x + 36, rail.right - 36):
            pygame.draw.circle(surface, (88, 84, 75), (bx, rail.centery), 7)
            pygame.draw.circle(surface, (18, 17, 16), (bx, rail.centery), 3)
        # Serial stencil.
        st = font_terminal_small.render("IPA-SC / RESTRAINT CHAIR 03", True, (72, 78, 76))
        if side == -1:
            surface.blit(st, (rail.x + 18, rail.y + 34))

    skin = (188, 148, 116)
    skin_dark = (105, 73, 55)
    skin_hi = (226, 194, 158)

    for side in (-1, 1):
        wrist_x = cx + side * 152 + trem * side
        wrist_y = cy - 8 + math.sin(sec * 6.1 + side) * 0.8
        elbow_x = cx + side * 275
        elbow_y = HEIGHT + 78
        # Forearm emerges from the bottom edge.
        arm_pts = [
            (int(elbow_x - side * 42), elbow_y),
            (int(elbow_x + side * 24), elbow_y),
            (int(wrist_x + side * 26), int(wrist_y + 35)),
            (int(wrist_x - side * 31), int(wrist_y + 35)),
        ]
        pygame.draw.polygon(surface, skin_dark, arm_pts)
        inner = [
            (int(elbow_x - side * 29), elbow_y),
            (int(elbow_x + side * 17), elbow_y),
            (int(wrist_x + side * 16), int(wrist_y + 31)),
            (int(wrist_x - side * 20), int(wrist_y + 31)),
        ]
        pygame.draw.polygon(surface, skin, inner)
        pygame.draw.line(surface, skin_hi, (int(wrist_x - side * 12), int(wrist_y + 42)), (int(elbow_x - side * 18), int(elbow_y - 70)), 2)
        # Red cuff marks under the steel.
        chafe = pygame.Surface((84, 30), pygame.SRCALPHA)
        pygame.draw.ellipse(chafe, (142, 28, 24, 112), chafe.get_rect())
        surface.blit(chafe, (int(wrist_x - 42), int(wrist_y + 11)))
        # Hand, fingers curled because straps are tight.
        hand_y = wrist_y - 24
        pygame.draw.ellipse(surface, skin, (int(wrist_x - 33), int(hand_y - 8), 66, 42))
        pygame.draw.ellipse(surface, skin_dark, (int(wrist_x - 33), int(hand_y - 8), 66, 42), 2)
        for i in range(4):
            fx = wrist_x - 23 + i * 15
            finger_len = 32 + int(2 * math.sin(sec * 5.0 + i + side))
            pygame.draw.line(surface, skin_dark, (int(fx), int(hand_y + 18)), (int(fx), int(hand_y + 18 - finger_len)), 7)
            pygame.draw.line(surface, skin, (int(fx), int(hand_y + 18)), (int(fx), int(hand_y + 18 - finger_len)), 5)
            pygame.draw.circle(surface, skin_hi, (int(fx), int(hand_y + 11)), 5)
        # Cuff and short chain to chair rail.
        cuff = pygame.Rect(0, 0, 104, 35)
        cuff.center = (int(wrist_x), int(wrist_y + 30))
        pygame.draw.rect(surface, (19, 20, 22), cuff, border_radius=8)
        pygame.draw.rect(surface, (104, 101, 93), cuff, 3, border_radius=8)
        pygame.draw.line(surface, (151, 142, 120), (cuff.x + 12, cuff.y + 8), (cuff.right - 12, cuff.y + 8), 1)
        anchor = (int(wrist_x + side * 86), int(wrist_y + 30))
        for j in range(5):
            q = (j + 0.5) / 5
            lx = wrist_x + side * 48 + (anchor[0] - (wrist_x + side * 48)) * q
            ly = wrist_y + 30 + (anchor[1] - (wrist_y + 30)) * q
            link = pygame.Rect(int(lx - 7), int(ly - 5), 14, 10)
            pygame.draw.ellipse(surface, (45, 45, 45), link, 3)
            pygame.draw.ellipse(surface, (112, 108, 96), link, 1)
        pygame.draw.circle(surface, (78, 74, 66), anchor, 13)
        pygame.draw.circle(surface, (20, 18, 16), anchor, 5)

    _m3_draw_fluorescent(surface, WIDTH // 2 - 96, SCENE_TOP + 42, 192, t, glow_alpha=28)
    _m3_soft_light(surface, (cx, cy - 110), 360, (170, 190, 200), 18)


def _draw_interrogation_room(surface, t):
    """Wide interrogation composition: room, chair, Balaceanu, monitor."""
    surface.fill((3, 3, 4))
    sec = t / 1000.0
    push = _m3_smooth(t / 3600.0)
    cam_x = int(-18 * push)
    cam_y = int(6 * math.sin(sec * 0.55))

    # Back wall and floor, muted institutional colors.
    horizon = SCENE_TOP + 330 + cam_y
    for y in range(SCENE_TOP, SCENE_BOT):
        if y < horizon:
            p = (y - SCENE_TOP) / max(1, horizon - SCENE_TOP)
            col = (int(9 + p * 18), int(10 + p * 18), int(12 + p * 17))
        else:
            p = (y - horizon) / max(1, SCENE_BOT - horizon)
            col = (int(18 + p * 20), int(18 + p * 20), int(19 + p * 19))
        pygame.draw.line(surface, col, (0, y), (WIDTH, y))
    pygame.draw.line(surface, (36, 38, 39), (0, horizon), (WIDTH, horizon), 2)
    # Tile perspective.
    for x in range(-120, WIDTH + 120, 92):
        pygame.draw.line(surface, (24, 25, 26), (WIDTH // 2, horizon), (x + cam_x, SCENE_BOT), 1)
    for i in range(9):
        yy = horizon + int((i / 9.0) ** 1.7 * (SCENE_BOT - horizon))
        pygame.draw.line(surface, (25, 26, 27), (0, yy), (WIDTH, yy), 1)

    # Observation window / black mirror.
    win = pygame.Rect(WIDTH // 2 - 410 + cam_x, SCENE_TOP + 92 + cam_y, 310, 128)
    pygame.draw.rect(surface, (5, 7, 9), win, border_radius=3)
    pygame.draw.rect(surface, (54, 60, 62), win, 2, border_radius=3)
    pygame.draw.line(surface, (80, 86, 88), (win.x + 20, win.y + 12), (win.right - 28, win.y + 12), 1)
    if int(t // 700) % 2 == 0:
        pygame.draw.circle(surface, (130, 20, 18), (win.right - 24, win.y + 22), 4)
    obs = font_terminal_small.render("OBSERVATION / REC", True, (88, 92, 92))
    surface.blit(obs, (win.x + 18, win.y + win.h - 25))

    # Broadcast monitor on the back wall.
    mon = pygame.Rect(WIDTH // 2 + 100 + cam_x, SCENE_TOP + 64 + cam_y, 270, 160)
    _m3_soft_light(surface, mon.center, 230, (110, 18, 16), 42)
    pygame.draw.rect(surface, (12, 5, 5), mon.inflate(18, 18), border_radius=5)
    pygame.draw.rect(surface, (100, 18, 16), mon, border_radius=4)
    pygame.draw.rect(surface, (230, 78, 48), mon, 2, border_radius=4)
    # Monitor image: podium silhouette and countdown, not just an abstract blob.
    pygame.draw.rect(surface, (28, 7, 7), (mon.x + 16, mon.y + 18, mon.w - 32, mon.h - 36))
    pygame.draw.circle(surface, (18, 2, 2), (mon.centerx, mon.y + 64), 32)
    pygame.draw.rect(surface, (18, 2, 2), (mon.centerx - 58, mon.y + 94, 116, 42), border_radius=4)
    txt = font_terminal_small.render("STATE ADDRESS 22:00", True, (245, 180, 120))
    surface.blit(txt, (mon.centerx - txt.get_width() // 2, mon.y + 12))
    for sy in range(mon.y + 22, mon.bottom - 12, 5):
        pygame.draw.line(surface, (55, 8, 8), (mon.x + 10, sy), (mon.right - 10, sy), 1)

    # Hanging light pools the table and chair, leaving corners dead.
    _m3_draw_fluorescent(surface, WIDTH // 2 - 132 + cam_x, SCENE_TOP + 28 + cam_y, 264, t, glow_alpha=50)
    _m3_soft_light(surface, (WIDTH // 2 - 40 + cam_x, SCENE_TOP + 365 + cam_y), 420, (160, 178, 180), 28)

    # Table between them.
    # Keep the interrogation blocking above the bottom dialogue box.
    # The caption panel starts around the lower third, so all story-critical
    # props/characters live in the upper safe area.
    table_y = SCENE_TOP + 300 + cam_y
    pygame.draw.ellipse(surface, (0, 0, 0, 92), (WIDTH // 2 - 250 + cam_x, table_y + 22, 500, 42))
    pygame.draw.rect(surface, (30, 29, 27), (WIDTH // 2 - 220 + cam_x, table_y - 12, 440, 54), border_radius=8)
    pygame.draw.line(surface, (76, 70, 60), (WIDTH // 2 - 204 + cam_x, table_y - 6), (WIDTH // 2 + 204 + cam_x, table_y - 6), 2)
    # Folder as visual hook for Vostral.
    folder = pygame.Rect(WIDTH // 2 + 46 + cam_x, table_y - 42, 122, 74)
    pygame.draw.rect(surface, (72, 54, 34), folder, border_radius=4)
    pygame.draw.rect(surface, (150, 45, 36), folder, 2, border_radius=4)
    tag = font_terminal.render("VOSTRAL", True, (220, 174, 104))
    surface.blit(tag, (folder.centerx - tag.get_width() // 2, folder.y + 20))
    stamp = font_terminal_small.render("SEALED", True, (170, 45, 40))
    surface.blit(stamp, (folder.centerx - stamp.get_width() // 2, folder.y + 48))

    # Biribel restrained left; Balaceanu right, standing too composed.
    _m3_draw_seated_biribel(surface, WIDTH // 2 - 270 + cam_x, SCENE_TOP + 342 + cam_y, scale=0.88, rim=(118, 142, 148))
    _m3_draw_balaceanu(surface, WIDTH // 2 + 310 + cam_x, SCENE_TOP + 456 + cam_y, scale=0.72, facing_left=True)

    # Foreground darkness as if camera is peeking from the corner/through glass.
    fg = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
    pygame.draw.rect(fg, (0, 0, 0, 90), (0, SCENE_TOP, 82, SCENE_BOT - SCENE_TOP))
    pygame.draw.rect(fg, (0, 0, 0, 70), (WIDTH - 64, SCENE_TOP, 64, SCENE_BOT - SCENE_TOP))
    pygame.draw.line(fg, (120, 120, 120, 26), (86, SCENE_TOP), (86, SCENE_BOT), 2)
    surface.blit(fg, (0, 0))
    _m3_noise(surface, 9910, 70, alpha=12)


def _draw_monitor_broadcast(surface, t):
    """CRT close-up of the state broadcast setup.

    Still displays the plot information, but as a broadcast image with a face,
    podium, lower-third and countdown instead of a flat generated text card.
    """
    surface.fill((5, 1, 1))
    sec = t / 1000.0

    # CRT body.
    # Place the CRT in the visual safe area above the dialogue box.
    # The bottom caption covers roughly y=506+, so the whole monitor sits above it.
    bezel = pygame.Rect(130, SCENE_TOP + 22, WIDTH - 260, 360)
    pygame.draw.rect(surface, (7, 7, 8), bezel.inflate(42, 42), border_radius=28)
    pygame.draw.rect(surface, (28, 22, 21), bezel.inflate(28, 28), border_radius=24)
    pygame.draw.rect(surface, (85, 72, 60), bezel.inflate(28, 28), 2, border_radius=24)
    screen_rect = bezel
    pygame.draw.rect(surface, (20, 5, 5), screen_rect, border_radius=18)

    # Render the TV picture to a separate surface so we can curve/scan it a bit.
    tv = pygame.Surface((screen_rect.w, screen_rect.h), pygame.SRCALPHA)
    tv.fill((28, 6, 6))
    for y in range(tv.get_height()):
        p = y / max(1, tv.get_height())
        pygame.draw.line(tv, (int(36 + p * 25), int(8 + p * 8), int(8 + p * 6)), (0, y), (tv.get_width(), y))
    # Studio background.
    header = pygame.Rect(34, 24, tv.get_width() - 68, 46)
    pygame.draw.rect(tv, (108, 18, 16), header, border_radius=4)
    h = font_terminal.render("ACARISTAN STATE ADDRESS", True, (255, 224, 190))
    tv.blit(h, (header.centerx - h.get_width() // 2, header.y + 12))
    for x in (70, 132, tv.get_width() - 178, tv.get_width() - 116):
        pygame.draw.rect(tv, (32, 36, 48), (x, 84, 36, tv.get_height() - 132))
        pygame.draw.rect(tv, (132, 30, 26), (x + 20, 90, 8, tv.get_height() - 150))
        pygame.draw.rect(tv, (34, 58, 100), (x + 7, 90, 8, tv.get_height() - 150))
    # Balaceanu at podium.
    podium_y = tv.get_height() - 70
    pygame.draw.rect(tv, (76, 54, 42), (tv.get_width()//2 - 170, podium_y - 88, 340, 110), border_radius=7)
    pygame.draw.rect(tv, (150, 110, 78), (tv.get_width()//2 - 170, podium_y - 88, 340, 110), 2, border_radius=7)
    seal = pygame.Rect(tv.get_width()//2 - 62, podium_y - 70, 124, 42)
    pygame.draw.rect(tv, (32, 24, 20), seal, border_radius=4)
    s_txt = font_terminal_small.render("IPA / STATE", True, (230, 205, 155))
    tv.blit(s_txt, (seal.centerx - s_txt.get_width()//2, seal.y + 12))
    # Figure.
    bx = tv.get_width() // 2
    pygame.draw.rect(tv, (42, 30, 28), (bx - 48, podium_y - 225, 96, 144), border_radius=10)
    pygame.draw.circle(tv, (198, 154, 116), (bx, podium_y - 254), 36)
    pygame.draw.arc(tv, (36, 24, 20), (bx - 36, podium_y - 289, 72, 62), math.pi, math.tau, 8)
    pygame.draw.polygon(tv, (140, 28, 25), [(bx - 10, podium_y - 205), (bx + 10, podium_y - 205), (bx, podium_y - 104)])
    pygame.draw.circle(tv, (14, 14, 14), (bx - 13, podium_y - 258), 3)
    pygame.draw.circle(tv, (14, 14, 14), (bx + 13, podium_y - 258), 3)
    pygame.draw.line(tv, (70, 28, 24), (bx - 12, podium_y - 236), (bx + 12, podium_y - 236), 2)
    for mx in (-22, 22):
        pygame.draw.line(tv, (8, 8, 9), (bx + mx, podium_y - 62), (bx + mx//2, podium_y - 120), 3)
        pygame.draw.circle(tv, (8, 8, 9), (bx + mx//2, podium_y - 122), 7)
    # Lower third / subject.
    lower = pygame.Rect(0, tv.get_height() - 58, tv.get_width(), 46)
    pygame.draw.rect(tv, (112, 12, 12), lower)
    pygame.draw.line(tv, (235, 105, 58), (0, lower.y), (tv.get_width(), lower.y), 2)
    lt = font_terminal.render("ROUTE 12 PERPETRATOR: BIRIBEL / KRAP OPERATIVE", True, (255, 226, 195))
    tv.blit(lt, (tv.get_width()//2 - lt.get_width()//2, lower.y + 11))
    # Countdown block.
    cd = pygame.Rect(tv.get_width() - 156, 82, 112, 58)
    pygame.draw.rect(tv, (18, 6, 6), cd, border_radius=4)
    pygame.draw.rect(tv, (210, 72, 46), cd, 2, border_radius=4)
    live = font_terminal_small.render("LIVE AT", True, (230, 180, 140))
    clock = font_speaker.render("22:00", True, (255, 220, 170))
    tv.blit(live, (cd.centerx - live.get_width()//2, cd.y + 7))
    tv.blit(clock, (cd.centerx - clock.get_width()//2, cd.y + 25))

    # TV interference: deterministic rows plus occasional horizontal tear.
    for y in range(0, tv.get_height(), 4):
        pygame.draw.line(tv, (0, 0, 0, 55), (0, y), (tv.get_width(), y), 1)
    rng = random.Random(int(t // 110))
    if rng.random() < 0.55:
        tear_y = rng.randint(80, tv.get_height() - 90)
        tear_h = rng.randint(2, 8)
        offset = rng.randint(-18, 18)
        strip = tv.subsurface((0, tear_y, tv.get_width(), tear_h)).copy()
        pygame.draw.rect(tv, (20, 4, 4), (0, tear_y, tv.get_width(), tear_h))
        tv.blit(strip, (offset, tear_y))
    # Slight pulse/roll bar.
    bar_y = int((sec * 58) % max(1, tv.get_height()))
    pygame.draw.rect(tv, (255, 255, 255, 18), (0, bar_y, tv.get_width(), 3))

    # Blit with a small curved-screen inset illusion.
    surface.blit(tv, screen_rect.topleft)
    pygame.draw.rect(surface, (180, 140, 105), screen_rect, 3, border_radius=18)
    _m3_soft_light(surface, screen_rect.center, 430, (145, 30, 22), 32)

    # CRT glass reflection.
    glass = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
    pygame.draw.line(glass, (255, 220, 180, 32), (screen_rect.x + 74, screen_rect.y + 28), (screen_rect.x + 260, screen_rect.y + 12), 4)
    pygame.draw.line(glass, (255, 220, 180, 18), (screen_rect.right - 250, screen_rect.y + 50), (screen_rect.right - 88, screen_rect.y + 32), 3)
    surface.blit(glass, (0, 0), special_flags=pygame.BLEND_RGBA_ADD)

def _draw_volkov_in_cell(surface, t):
    """Volkov entering from the detention corridor.

    Staged in four visual beats:

    Beat 1 (0.0 - 0.8s): Empty corridor shot. Distant footsteps implied
    by camera framing. Player reads "there is a hallway out there."

    Beat 2 (0.8 - 1.6s): Silhouette visible through the door viewport
    before it opens. Keypad light changes red -> green. Lock disengages.

    Beat 3 (1.6 - 2.8s): Door slides open with weight - light floods in
    from corridor. Volkov stands in threshold, backlit, not yet moving.

    Beat 4 (2.8s+): Volkov walks in. Cigarette ember. Name tag fades in.
    """
    sec = t / 1000.0

    surface.fill((2, 2, 4))

    for y in range(SCENE_TOP, SCENE_BOT):
        p = (y - SCENE_TOP) / max(1, SCENE_BOT - SCENE_TOP)
        r = int(6 + p * 8)
        g = int(6 + p * 8)
        b = int(8 + p * 10)
        pygame.draw.line(surface, (r, g, b), (0, y), (WIDTH, y))

    floor_y = SCENE_BOT - 80

    for y in range(floor_y, SCENE_BOT):
        p = (y - floor_y) / max(1, SCENE_BOT - floor_y)
        shade = int(8 + p * 10)
        pygame.draw.line(surface, (shade, shade, shade + 2), (0, y), (WIDTH, y))

    refl = pygame.Surface((WIDTH, SCENE_BOT - floor_y), pygame.SRCALPHA)
    for y in range(SCENE_BOT - floor_y):
        a = max(0, int(30 * (1 - y / (SCENE_BOT - floor_y))))
        pygame.draw.line(refl, (40, 55, 80, a), (0, y), (WIDTH, y))
    surface.blit(refl, (0, floor_y))

    rng_wall = random.Random(77)
    for x in range(0, WIDTH, 88):
        pygame.draw.line(surface, (14, 14, 17), (x, SCENE_TOP + 20), (x, floor_y), 1)
    for y in range(SCENE_TOP + 40, floor_y, 52):
        pygame.draw.line(surface, (13, 13, 16), (0, y), (WIDTH, y), 1)

    for _ in range(6):
        sx = rng_wall.randint(40, WIDTH - 40)
        sy = rng_wall.randint(SCENE_TOP + 20, floor_y - 30)
        sw = rng_wall.randint(3, 10)
        sh = rng_wall.randint(20, 80)
        stain = pygame.Surface((sw, sh), pygame.SRCALPHA)
        for i in range(sh):
            a = max(0, int(18 * (1 - i / sh)))
            pygame.draw.line(stain, (20, 30, 45, a), (0, i), (sw, i))
        surface.blit(stain, (sx, sy))

    flicker = 0.85 + 0.15 * math.sin(sec * 12.3)
    tube_y = SCENE_TOP + 18
    pygame.draw.rect(surface, (22, 22, 20), (WIDTH // 2 - 80, tube_y, 160, 7))
    tube_col = (int(175 * flicker), int(180 * flicker), int(160 * flicker))
    pygame.draw.rect(surface, tube_col, (WIDTH // 2 - 76, tube_y + 1, 152, 5))

    cone = pygame.Surface((360, 240), pygame.SRCALPHA)
    for i in range(18):
        r = max(0, 160 - i * 9)
        a = max(0, int(18 * (1 - i / 18) * flicker))
        pygame.draw.ellipse(cone, (210, 215, 190, a), (180 - r, 120 - r // 2, r * 2, r))
    surface.blit(cone, (WIDTH // 2 - 180, tube_y + 6))

    door_left = WIDTH // 2 + 168
    door_top = SCENE_TOP + 55
    door_w = 164
    door_h = floor_y - door_top + 14

    pygame.draw.rect(surface, (28, 26, 22), (door_left, door_top, door_w, door_h))

    vanish_x = door_left + door_w // 2
    vanish_y = door_top + door_h // 2
    for cx, cy in [(door_left, door_top), (door_left + door_w, door_top),
                   (door_left, door_top + door_h), (door_left + door_w, door_top + door_h)]:
        pygame.draw.line(surface, (38, 36, 30), (cx, cy), (vanish_x, vanish_y), 1)

    pygame.draw.line(surface, (42, 40, 34),
                     (door_left + 8, floor_y - 12),
                     (door_left + door_w - 8, floor_y - 12), 2)

    cor_light_x = door_left + door_w // 2
    cor_light_y = door_top + 18
    cor_glow = pygame.Surface((door_w + 40, door_h + 20), pygame.SRCALPHA)
    for i in range(12):
        r = int((door_w // 2) * (1 - i / 12))
        a = max(0, int(35 * (1 - i / 12)))
        pygame.draw.ellipse(cor_glow, (220, 200, 160, a),
                            (door_w // 2 + 20 - r, i * 8, r * 2, r))
    surface.blit(cor_glow, (door_left - 20, door_top))

    frame_thick = 14
    pygame.draw.rect(surface, (32, 34, 38),
                     (door_left - frame_thick, door_top - frame_thick,
                      door_w + frame_thick * 2, frame_thick))
    pygame.draw.rect(surface, (32, 34, 38),
                     (door_left - frame_thick, door_top - frame_thick,
                      frame_thick, door_h + frame_thick))
    pygame.draw.rect(surface, (32, 34, 38),
                     (door_left + door_w, door_top - frame_thick,
                      frame_thick, door_h + frame_thick))
    pygame.draw.line(surface, (52, 56, 62),
                     (door_left - frame_thick, door_top - frame_thick),
                     (door_left - frame_thick, door_top + door_h), 1)
    pygame.draw.line(surface, (52, 56, 62),
                     (door_left - frame_thick, door_top - frame_thick),
                     (door_left + door_w + frame_thick, door_top - frame_thick), 1)

    kp_x = door_left - frame_thick - 28
    kp_y = door_top + 90
    pygame.draw.rect(surface, (10, 14, 18), (kp_x, kp_y, 22, 52), border_radius=3)
    pygame.draw.rect(surface, (55, 65, 75), (kp_x, kp_y, 22, 52), 1, border_radius=3)
    for ky in range(2):
        for kx in range(3):
            pygame.draw.rect(surface, (22, 30, 38),
                             (kp_x + 3 + kx * 6, kp_y + 6 + ky * 8, 4, 5), border_radius=1)

    access_t = max(0.0, min(1.0, (sec - 0.65) / 0.25))
    if access_t < 1.0:
        blink = (int(sec * 4)) % 2 == 0
        led_col = (220, 50, 40) if blink else (120, 20, 16)
    else:
        led_col = (60, 230, 100)
    pygame.draw.circle(surface, led_col, (kp_x + 11, kp_y + 38), 3)
    glow_r = 8
    glow = pygame.Surface((glow_r * 2, glow_r * 2), pygame.SRCALPHA)
    pygame.draw.circle(glow, (*led_col, 60), (glow_r, glow_r), glow_r)
    surface.blit(glow, (kp_x + 11 - glow_r, kp_y + 38 - glow_r))

    if access_t >= 1.0:
        access_surf = font_terminal_small.render("ACCESS GRANTED", True, (80, 220, 110))
        surface.blit(access_surf, (kp_x - access_surf.get_width() + 22, kp_y - 16))
        id_surf = font_terminal_small.render("VOLKOV / AUTH-DELTA", True, (60, 160, 85))
        surface.blit(id_surf, (kp_x - id_surf.get_width() + 22, kp_y - 30))
    else:
        locked_surf = font_terminal_small.render("CELL 03 // SECURED", True, (180, 60, 50))
        surface.blit(locked_surf, (kp_x - locked_surf.get_width() + 22, kp_y - 16))

    if 0.4 < sec < 1.6:
        vp_alpha = max(0.0, min(1.0, (sec - 0.4) / 0.35))
        vp_fade = min(1.0, max(0.0, (1.6 - sec) / 0.25)) if sec > 1.35 else 1.0
        vp = pygame.Rect(door_left + 20, door_top + 38, 60, 28)
        pygame.draw.rect(surface, (4, 6, 8), vp)
        pygame.draw.rect(surface, (70, 80, 90), vp, 1)
        for bx in range(vp.x + 8, vp.right - 4, 10):
            pygame.draw.line(surface, (60, 70, 82), (bx, vp.y + 2), (bx, vp.bottom - 2), 1)
        if vp_alpha > 0.2:
            fig_a = int(200 * vp_alpha * vp_fade)
            fig = pygame.Surface((vp.w, vp.h), pygame.SRCALPHA)
            pygame.draw.circle(fig, (0, 0, 0, fig_a), (vp.w // 2, vp.h // 2 - 4), 6)
            pygame.draw.ellipse(fig, (0, 0, 0, fig_a), (4, vp.h // 2, vp.w - 8, vp.h // 2))
            surface.blit(fig, (vp.x, vp.y))
        if sec > 0.75 and vp_alpha > 0.5:
            ember_pulse = 0.5 + 0.5 * math.sin(sec * 8)
            ember_a = int(150 * vp_alpha * vp_fade * ember_pulse)
            ember_surf = pygame.Surface((20, 20), pygame.SRCALPHA)
            pygame.draw.circle(ember_surf, (255, 90, 25, ember_a), (10, 10), 6)
            surface.blit(ember_surf, (vp.x + vp.w // 2 + 8, vp.centery - 6))

    open_t = max(0.0, min(1.0, (sec - 1.2) / 0.75))
    open_ease = 1.0 - (1.0 - open_t) ** 3
    door_slide = int(door_w * open_ease)

    if open_t < 1.0:
        panel_rect = pygame.Rect(door_left - door_slide, door_top, door_w, door_h)
        pygame.draw.rect(surface, (52, 62, 74), panel_rect, border_radius=2)
        pygame.draw.rect(surface, (22, 28, 36), panel_rect, 2, border_radius=2)
        for i in range(5):
            rx = panel_rect.x + 16 + i * 28
            if rx < panel_rect.right - 8:
                pygame.draw.line(surface, (28, 35, 45),
                                 (rx, panel_rect.y + 8), (rx, panel_rect.bottom - 8), 3)
                pygame.draw.line(surface, (95, 112, 132),
                                 (rx - 1, panel_rect.y + 8), (rx - 1, panel_rect.bottom - 8), 1)
        handle_y = panel_rect.centery
        pygame.draw.rect(surface, (40, 50, 62),
                         (panel_rect.right - 18, handle_y - 20, 10, 40), border_radius=3)
        pygame.draw.rect(surface, (80, 95, 110),
                         (panel_rect.right - 18, handle_y - 20, 10, 40), 1, border_radius=3)

    if open_t > 0.05:
        spill_w = int((door_w + 200) * open_ease)
        spill_h = door_h + 60
        spill_surf = pygame.Surface((spill_w, spill_h), pygame.SRCALPHA)
        for i in range(spill_h):
            dist_from_door = abs(i - spill_h // 2) / (spill_h // 2)
            a = int(55 * open_ease * (1 - dist_from_door ** 2))
            if a > 0:
                pygame.draw.line(spill_surf, (220, 205, 165, a), (0, i), (spill_w, i))
        surface.blit(spill_surf, (door_left - spill_w + door_w, door_top - 30))

    if 1.2 < sec < 3.5:
        mote_rng = random.Random(int(sec * 20))
        mote_alpha = int(min(1.0, (sec - 1.2) / 0.4) * 120 * open_ease)
        for _ in range(12):
            mx = door_left + mote_rng.randint(-80, 40)
            my = door_top + mote_rng.randint(20, door_h - 20)
            ms = mote_rng.randint(1, 2)
            mote = pygame.Surface((ms * 4, ms * 4), pygame.SRCALPHA)
            pygame.draw.circle(mote, (220, 210, 180, mote_alpha), (ms * 2, ms * 2), ms)
            surface.blit(mote, (mx, my))

    threshold_t = max(0.0, min(1.0, (sec - 1.8) / 0.5))

    if sec > 1.8 and open_t > 0.6:
        vol_x = door_left + door_w // 2 + 10
        vol_y = floor_y
        halo_a = int(80 * threshold_t * open_ease)
        halo = pygame.Surface((180, 320), pygame.SRCALPHA)
        pygame.draw.ellipse(halo, (235, 215, 165, halo_a), (0, 0, 180, 320))
        surface.blit(halo, (vol_x - 90, vol_y - 300))
        draw_volkov(surface, vol_x, vol_y, scale=0.74 + 0.08 * threshold_t, facing_right=False)

    walk_t = max(0.0, min(1.0, (sec - 2.6) / 1.2))
    walk_ease = 1.0 - (1.0 - walk_t) ** 2

    if sec > 2.6 and open_t > 0.7:
        start_x = door_left + door_w // 2 + 10
        end_x = door_left + door_w // 2 - 55
        vol_x = int(start_x + (end_x - start_x) * walk_ease)
        start_y = floor_y
        end_y = floor_y - 4
        vol_y = int(start_y + (end_y - start_y) * walk_ease)
        halo_a = int(80 * (1.0 - walk_ease * 0.7) * open_ease)
        halo = pygame.Surface((180, 320), pygame.SRCALPHA)
        pygame.draw.ellipse(halo, (235, 215, 165, halo_a), (0, 0, 180, 320))
        surface.blit(halo, (vol_x - 70, vol_y - 300))
        shadow_a = int(70 * walk_ease)
        shadow = pygame.Surface((60, 16), pygame.SRCALPHA)
        pygame.draw.ellipse(shadow, (0, 0, 0, shadow_a), shadow.get_rect())
        surface.blit(shadow, (vol_x - 30, vol_y - 6))
        draw_volkov(surface, vol_x, vol_y, scale=0.82, facing_right=False)

        name_a = int(255 * min(1.0, (sec - 3.0) / 0.6))
        if name_a > 0:
            name_surf = font_terminal.render("VOLKOV", True, C_VOLKOV)
            name_surf.set_alpha(name_a)
            surface.blit(name_surf, (vol_x - name_surf.get_width() // 2, vol_y - 220))
            role_a = int(200 * min(1.0, (sec - 3.3) / 0.5))
            if role_a > 0:
                role_surf = font_terminal_small.render("IPA LOGISTICS - S. VOLKOV", True, (180, 120, 70))
                role_surf.set_alpha(role_a)
                surface.blit(role_surf, (vol_x - role_surf.get_width() // 2, vol_y - 196))

    chair_cx = WIDTH // 2 - 170
    chair_cy = floor_y
    ch_shad = pygame.Surface((80, 18), pygame.SRCALPHA)
    pygame.draw.ellipse(ch_shad, (0, 0, 0, 100), ch_shad.get_rect())
    surface.blit(ch_shad, (chair_cx - 40, chair_cy - 8))
    for cx_off in (-16, 16):
        pygame.draw.line(surface, (25, 25, 28),
                         (chair_cx + cx_off, chair_cy - 6),
                         (chair_cx + cx_off, chair_cy - 72), 3)
    pygame.draw.rect(surface, (22, 22, 26),
                     (chair_cx - 28, chair_cy - 76, 56, 12), border_radius=2)
    pygame.draw.rect(surface, (20, 20, 24),
                     (chair_cx - 26, chair_cy - 132, 52, 58), border_radius=2)
    pygame.draw.rect(surface, (30, 30, 35),
                     (chair_cx - 26, chair_cy - 132, 52, 58), 1, border_radius=2)
    pygame.draw.ellipse(surface, (8, 9, 11), (chair_cx - 20, chair_cy - 126, 40, 56))
    pygame.draw.circle(surface, (10, 11, 13), (chair_cx - 6, chair_cy - 138), 12)
    pygame.draw.rect(surface, (7, 8, 10),
                     (chair_cx - 28, chair_cy - 82, 12, 34), border_radius=2)
    pygame.draw.rect(surface, (7, 8, 10),
                     (chair_cx + 16, chair_cy - 82, 12, 34), border_radius=2)

    draw_vignette(surface, strength=210)
    draw_scanlines(surface)
    draw_letterbox(surface)


# ─────────────────────────────────────────────
# Chair-break cutscene shots (Mission 3 — the post-breach moment).
# ─────────────────────────────────────────────
# A four-shot, wordless, auto-timed cinematic that REPLACES the old
# shake-overlay chair-break. The in-cell state mutations (chair broken,
# player armed, weapon granted, objective update) still fire from
# mission3._update_chair_break_anim at the Crack shot; only the
# presentation changes — the action is now SHOWN rather than implied.
#
# Each shot is a pure pygame.draw function (rect / polygon / ellipse /
# line / circle / arc) plus the shared helpers above. They take the
# PER-SHOT frame counter `t` (resets each shot) and are deterministic in
# `t` so the transition fades stay clean.
#
# Palette: sourced VERBATIM from mission3._draw_cell_details so the
# cutscene's chair/cuffs/splinters are pixel-identical to the in-game
# cell. The interrogation chair is METAL (dark gunmetal), not wood —
# earlier revisions used invented warm-wood tones (120,90,60) which made
# the shots look like a different game. These are the real values:
#   seat_col (42,40,36)  seat_dark (28,26,24)  seat_edge (60,56,50)
#   splinter_col (50,42,34)
#   chain (100,96,88)    chain_dark (60,56,50) cuff (130,124,112)
#   bolt (76,72,64)
CB_METAL       = (42, 40, 36)
CB_METAL_DARK  = (28, 26, 24)
CB_METAL_EDGE  = (60, 56, 50)
CB_SPLINTER    = (50, 42, 34)
CB_SPLINTER_HI = (74, 64, 52)
CB_CHAIN       = (100, 96, 88)
CB_CHAIN_DARK  = (60, 56, 50)
CB_CUFF        = (130, 124, 112)
CB_BOLT        = (76, 72, 64)
CB_SKIN        = (202, 172, 142)
CB_SKIN_SHADE  = (148, 118, 92)
CB_DUST        = (96, 88, 76)
# Cold overhead fluorescent — the ONLY light after the breach (the monitor
# is off, so there is NO red wash). Matches _draw_cell_atmosphere's tube.
CB_TUBE_COL    = (210, 215, 190)
CB_BG          = (8, 9, 11)

def _pt(cx, cy, dx, dy, angle, scale):
    dx *= scale
    dy *= scale
    cos_a = math.cos(angle)
    sin_a = math.sin(angle)
    return (int(cx + dx * cos_a - dy * sin_a),
            int(cy + dx * sin_a + dy * cos_a))

# Per-shot frame durations.
# Desperate → Triumphant arc. Total ~11.6 s at 60 fps.
#   Shot 1 (Strain):  exhausted, trembling, near defeat       — 4.0 s
#   Shot 2 (Crack):   cathartic release                       — 2.2 s
#   Shot 3 (Grab):    determined recognition                  — 2.4 s
#   Shot 4 (Ready):   cold resolve                            — 3.0 s
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
    """Blit the pre-rendered live cell (`cell_surf`, a WIDTH×HEIGHT frame
    of the real tilemap cell + _draw_cell_room) onto `surface`, zoomed
    around the screen-space chair center (cx, cy) and optionally panned.

    This is what makes every shot the SAME cell at a different focal
    length — the camera "travels" (tight → wider → floor → standing)
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
    center stays bright. Kept light — heavy vignette crushed earlier revs.
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
    like the game — a dark void with motivated lighting, not a tilemap room.

    This is what makes the cutscene a STANDALONE cinematic, not a gameplay
    overlay: the background is custom-drawn for the cutscene, not a
    screenshot of the game.

    shot_id:
      "strain" — tight close-up: dark void + single light cone on chair area
      "crack"  — medium shot: dark floor + chair stump at center
      "grab"   — floor close-up: dark surface + leg lying on it
      "ready"  — medium-full: dark void + standing silhouette backdrop
    """
    # Base: pure dark void (NOT the game's dark grey tile floor).
    # Slightly cooler than CB_BG to match the cinematic grade.
    surface.fill((6, 8, 12))

    if shot_id == "strain":
        # Dark concrete floor + faint wall behind the chair.
        # Must be VISIBLE — not pure black. The floor/wall give spatial
        # context: "this chair is in a room."
        # Floor: dark grey concrete, bright enough to see
        floor_col = (45, 48, 52)
        for y in range(HEIGHT):
            p = y / HEIGHT
            mid_dist = abs(p - 0.45) * 2
            v = int(floor_col[0] * (1.0 - mid_dist * 0.25))
            pygame.draw.line(surface, (v, v + 2, v + 4), (0, y), (WIDTH, y))
        # Wall strip behind the backrest (lighter than floor — reads as wall)
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
        # at center. The floor is just a dark surface — no grid, no drain,
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
        # no furniture — just darkness + the silhouette.
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
# CHAIR BREAK CUTSCENE — Rewritten with proper backgrounds & chair
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
    instead of guessing from the magnitude — otherwise the first second of a
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
    # Body in deep shadow behind the chair.
    torso = pygame.Surface((190, 210), pygame.SRCALPHA)
    pygame.draw.ellipse(torso, (9, 10, 12, 245), (65, 4, 60, 64))
    pygame.draw.polygon(torso, (13, 18, 16, 245),
                        [(48, 72), (142, 72), (162, 192), (28, 192)])
    pygame.draw.line(torso, (32, 42, 36, 180), (95, 82), (95, 180), 2)
    surface.blit(torso, (int(cx - 95), int(seat_y - 190)))

    # Arms pull out and down, the wrists fighting the cuffs.
    pull = _cb_smooth(yank)
    trem = math.sin(t * 0.35) * 5 * pull
    left_elbow = (int(cx - 45), int(seat_y - 82 + trem))
    right_elbow = (int(cx + 45), int(seat_y - 82 - trem))
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


def _draw_cb_strain(surface, t_value, *args, clock_is_ms=False, **kwargs):
    """Shot 1 — EXTREME CLOSE-UP: Wrist straining against the cuff.
    Focuses on anatomy, taut chains, and the metal beginning to fail.
    """
    t = _cb_time_to_frames(t_value, clock_is_ms)
    p = _cb_clamp(t / float(CB_SHOT1_DUR))
    yank = _cb_smooth(p)

    # Violent, high-frequency camera shake tied to the physical effort
    shake_amt = 1.0 + 8.0 * yank + abs(math.sin(t * 0.4)) * 3.0 * yank
    sx, sy = _cb_camera_shake(t, shake_amt, decay=0.8 + 0.2 * yank)
    cx = WIDTH // 2 + int(sx)
    cy = HEIGHT // 2 + int(sy)

    # ── Background: Dark out-of-focus void ──
    surface.fill((8, 9, 11))
    _cb_tube_flicker(surface, cx - 100, cy - 150, t, base_alpha=95)

    # Tremor applied to the flesh and chains, but NOT the heavy steel armrest
    # (until the very end when the steel itself starts giving way)
    tremor_x = int(math.sin(t * 1.8) * 3.0 * yank)
    tremor_y = int(math.cos(t * 2.1) * 2.0 * yank)

    # ── 1. The Steel Armrest (Macro Scale) ──
    # A massive slab of dark, scarred metal angling down the screen
    armrest_w = 220
    armrest_x = cx - armrest_w // 2
    armrest_y = cy - 200

    # Base steel
    pygame.draw.rect(surface, (32, 30, 28), (armrest_x, armrest_y, armrest_w, 600), border_radius=8)
    # Beveled edge highlights
    pygame.draw.line(surface, (60, 58, 54), (armrest_x + 4, armrest_y), (armrest_x + 4, armrest_y + 600), 3)
    pygame.draw.line(surface, (18, 16, 14), (armrest_x + armrest_w - 4, armrest_y), (armrest_x + armrest_w - 4, armrest_y + 600), 3)

    # Scratches and gouges in the metal
    rng = random.Random(42)
    for _ in range(35):
        gx = armrest_x + rng.randint(10, armrest_w - 20)
        gy = armrest_y + rng.randint(0, 550)
        pygame.draw.line(surface, (15, 14, 13), (gx, gy), (gx + rng.randint(-15, 15), gy + rng.randint(10, 30)), 2)
        pygame.draw.line(surface, (45, 42, 38), (gx+1, gy), (gx + 1 + rng.randint(-15, 15), gy + rng.randint(10, 30)), 1)

    # ── 2. The Forearm & Hand ──
    arm_x = cx + tremor_x
    arm_y = cy + tremor_y
    skin_base = (196, 158, 128)
    skin_shade = (148, 112, 88)
    skin_deep = (90, 60, 45)

    # Forearm coming from bottom left
    arm_pts = [
        (arm_x - 140, arm_y + 400), # Bottom left (elbow offscreen)
        (arm_x + 60, arm_y + 400),  # Bottom right
        (arm_x + 85, arm_y + 20),   # Right wrist
        (arm_x - 75, arm_y + 20),   # Left wrist
    ]
    pygame.draw.polygon(surface, skin_base, arm_pts)
    pygame.draw.polygon(surface, skin_shade, arm_pts, 8)

    # Arm shading / 3D volume
    pygame.draw.polygon(surface, skin_deep, [(arm_x + 60, arm_y + 400), (arm_x + 85, arm_y + 20), (arm_x + 55, arm_y + 20), (arm_x + 20, arm_y + 400)])

    # Taut muscles / Tendons popping (alpha scales with yank)
    tendon_alpha = int(200 * yank)
    if tendon_alpha > 0:
        tendon_surf = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        skin_hi = (220, 190, 160)
        # Center tendon
        pygame.draw.line(tendon_surf, (*skin_hi, tendon_alpha), (arm_x, arm_y + 30), (arm_x - 20, arm_y + 250), 12)
        pygame.draw.line(tendon_surf, (*skin_shade, tendon_alpha), (arm_x + 8, arm_y + 30), (arm_x - 12, arm_y + 250), 6)
        # Vein (bluish)
        pygame.draw.line(tendon_surf, (110, 130, 140, int(tendon_alpha*0.8)), (arm_x - 40, arm_y + 40), (arm_x - 10, arm_y + 180), 4)
        surface.blit(tendon_surf, (0, 0))

    # Hand gripping the top edge of the armrest (fingers curled tightly)
    grip_y = arm_y - 120
    pygame.draw.rect(surface, skin_base, (arm_x - 70, grip_y, 150, 140), border_radius=20)

    # White knuckles (color shifts from skin to pale white/yellow as yank increases)
    knuckle_r = int(skin_base[0] + (240 - skin_base[0]) * yank)
    knuckle_g = int(skin_base[1] + (230 - skin_base[1]) * yank)
    knuckle_b = int(skin_base[2] + (210 - skin_base[2]) * yank)
    knuckle_col = (knuckle_r, knuckle_g, knuckle_b)

    for i in range(4):
        kx = arm_x - 50 + i * 35
        # Fingers curling over
        pygame.draw.line(surface, skin_shade, (kx, grip_y + 20), (kx, grip_y - 40), 22)
        pygame.draw.line(surface, skin_base, (kx, grip_y + 20), (kx, grip_y - 40), 16)
        # The popping knuckles
        pygame.draw.circle(surface, knuckle_col, (kx, grip_y + 15), 16)
        pygame.draw.circle(surface, skin_shade, (kx, grip_y + 15), 16, 2)

    # ── 3. The Restraint Cuff ──
    # A massive, rusty steel clamp biting into the wrist
    cuff_y = arm_y + 20
    cuff_h = 80
    pygame.draw.rect(surface, (20, 22, 24), (arm_x - 100, cuff_y, 210, cuff_h), border_radius=15)
    pygame.draw.rect(surface, (10, 11, 12), (arm_x - 100, cuff_y, 210, cuff_h), 4, border_radius=15)

    # Cuff rust and texture
    for _ in range(40):
        rx = arm_x - 90 + rng.randint(0, 190)
        ry = cuff_y + rng.randint(5, cuff_h - 5)
        pygame.draw.circle(surface, (80, 45, 25), (rx, ry), rng.randint(2, 6))

    # Raw, chafed skin where the cuff digs in (Redness increases with yank)
    chafe_alpha = int(180 * yank)
    if chafe_alpha > 0:
        chafe = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        pygame.draw.ellipse(chafe, (180, 20, 20, chafe_alpha), (arm_x - 85, cuff_y - 15, 180, 30))
        pygame.draw.ellipse(chafe, (180, 20, 20, chafe_alpha), (arm_x - 85, cuff_y + cuff_h - 15, 180, 30))
        surface.blit(chafe, (0, 0))

    # ── 4. The Taut Chain & Snapping Bolt ──
    # Anchor bracket on the right side of the armrest
    bolt_base_x = armrest_x + armrest_w - 20
    bolt_base_y = cuff_y + 40

    # As yank increases, the bolt visually bends and pulls OUT of the metal
    bolt_pull_x = int(12 * yank)
    bolt_pull_y = int(-18 * yank)
    anchor_x = bolt_base_x + bolt_pull_x + tremor_x
    anchor_y = bolt_base_y + bolt_pull_y + tremor_y

    # Stress fracture in the steel armrest growing from the bolt hole
    if p > 0.2:
        crack_len = int(140 * ((p - 0.2) / 0.8))
        pygame.draw.line(surface, (10, 8, 6), (bolt_base_x, bolt_base_y), (bolt_base_x - crack_len, bolt_base_y + int(crack_len * 0.8)), 4)
        pygame.draw.line(surface, (80, 75, 70), (bolt_base_x, bolt_base_y), (bolt_base_x - crack_len, bolt_base_y + int(crack_len * 0.8)), 1)

        # Branching cracks
        if p > 0.5:
            pygame.draw.line(surface, (10, 8, 6), (bolt_base_x - 40, bolt_base_y + 32), (bolt_base_x - 30 - crack_len//2, bolt_base_y + 80), 2)

    # The heavy bolt pulling out
    pygame.draw.line(surface, (100, 95, 90), (bolt_base_x, bolt_base_y), (anchor_x, anchor_y), 18)
    pygame.draw.circle(surface, (60, 58, 55), (anchor_x, anchor_y), 16)
    pygame.draw.circle(surface, (30, 28, 25), (anchor_x, anchor_y), 8)

    # The Chain connecting cuff to anchor (pulled absolutely straight)
    chain_start_x = arm_x + 105
    chain_start_y = cuff_y + cuff_h // 2

    # Draw 4 thick links under extreme tension
    num_links = 4
    for i in range(num_links):
        lt = i / float(num_links)
        link_x = chain_start_x + (anchor_x - chain_start_x) * lt
        link_y = chain_start_y + (anchor_y - chain_start_y) * lt

        # Links vibrate wildly with the tremor
        vib_x = int(math.sin(t * 3.0 + i) * 4.0 * yank)
        vib_y = int(math.cos(t * 3.5 + i) * 4.0 * yank)

        pygame.draw.ellipse(surface, (40, 42, 45), (link_x - 15 + vib_x, link_y - 25 + vib_y, 30, 50), 8)
        pygame.draw.ellipse(surface, (90, 95, 100), (link_x - 15 + vib_x, link_y - 25 + vib_y, 30, 50), 2)

    # ── 5. Micro-Sparks & Dust (The metal screaming) ──
    if yank > 0.5:
        # Dust flaking from the crack
        for _ in range(int(8 * yank)):
            dx = bolt_base_x + rng.randint(-40, 10)
            dy = bolt_base_y + rng.randint(-10, 40)
            pygame.draw.circle(surface, (120, 110, 100), (dx, dy + int((t*5)%30)), rng.randint(1, 3))

        # Hard friction sparks from the bolt tearing the steel
        if (t % 4) < 2:
            spark_x = bolt_base_x + rng.randint(-5, 5)
            spark_y = bolt_base_y + rng.randint(-5, 5)
            pygame.draw.line(surface, (255, 200, 100), (spark_x, spark_y), (spark_x - rng.randint(10, 40), spark_y - rng.randint(10, 40)), 3)
            pygame.draw.line(surface, (255, 255, 255), (spark_x, spark_y), (spark_x - rng.randint(5, 20), spark_y - rng.randint(5, 20)), 1)

    _cb_finish(surface, t, "RESTRAINT STRESS: CRITICAL")


def _draw_cb_crack(surface, t_value, *args, clock_is_ms=False, **kwargs):
    """Shot 2 — The leg tears free. Metal shards, directed blast, motion smear."""
    t = _cb_time_to_frames(t_value, clock_is_ms)
    p = _cb_clamp(t / float(CB_SHOT2_DUR))
    break_p = _cb_ease_out_cubic_m2((t - 12.0) / 70.0)
    impact = 1.0 - _cb_clamp((t - 8.0) / 38.0)

    sx, sy = _cb_camera_shake(t, amount=16.0, decay=max(0.15, impact))
    cx = WIDTH // 2 + int(sx)
    seat_y = 320 + int(sy)
    floor_y = seat_y + int(145 * 1.02) + int(18 * 1.02)

    _cb_cinematic_bg(surface, cx, seat_y, "crack", t=t, op=1.0)
    _cb_tube_flicker(surface, cx, 118, t, base_alpha=115)

    # --- Biribel lunging free ---
    lunge = _cb_ease_out_cubic_m2((t - 8.0) / 70.0)
    body_cx = cx - int(35 * lunge)
    body_y = seat_y - int(142 + 24 * lunge)
    pygame.draw.ellipse(surface, (8, 9, 11), (body_cx - 28, body_y - 20, 56, 58))
    pygame.draw.polygon(surface, (10, 13, 13), [
        (body_cx - 44, body_y + 38), (body_cx + 36, body_y + 28),
        (body_cx + 62, body_y + 150), (body_cx - 64, body_y + 152),
    ])

    # Arms snapping free — motion smear trails
    for arm_side, base_ox, base_oy, end_ox, end_oy in [
        (-1, -30, 80, -110 - int(24 * lunge), 110 - int(18 * lunge)),
        (1,   28, 78,  115 + int(26 * lunge),  98 - int(10 * lunge)),
    ]:
        # Smear trail: draw 4 ghost positions fading backward
        for ghost_i in range(4):
            ghost_t = max(0.0, lunge - ghost_i * 0.08)
            ghost_lunge = _cb_ease_out_cubic_m2(ghost_t)
            ghost_end_ox = (110 + int(26 * ghost_lunge)) * arm_side
            ghost_end_oy = 98 - int(10 * ghost_lunge)
            ghost_a = max(0, 45 - ghost_i * 12)
            smear_surf = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
            pygame.draw.line(smear_surf,
                             (C_PLAYER_UNIFORM[0], C_PLAYER_UNIFORM[1], C_PLAYER_UNIFORM[2], ghost_a),
                             (body_cx + int(22 * arm_side), body_y + 78),
                             (body_cx + ghost_end_ox, body_y + ghost_end_oy), 6)
            surface.blit(smear_surf, (0, 0))

        # Solid arm
        _cb_draw_forearm(surface,
                         (body_cx + int(22 * arm_side), body_y + 78),
                         (body_cx + end_ox, body_y + end_oy),
                         sleeve=True, alpha=230)

    # --- The chair (still in frame, now missing the front-right leg) ---
    _draw_interrogation_chair(surface, cx, seat_y, scale=1.02,
                              broken_leg=break_p > 0.02,
                              break_progress=break_p,
                              yank=1.0, t=t)

    # --- Flying leg trajectory ---
    if break_p > 0.08:
        fly = _cb_ease_out_cubic_m2((break_p - 0.08) / 0.92)
        leg_x = cx - 26 - 170 * fly
        leg_y = floor_y - 70 * math.sin(fly * math.pi) + 20 * fly
        leg_ang = -78 + 150 * fly + math.sin(t * 0.2) * 10

        # Motion blur trail behind the flying leg
        trail_surf = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        for trail_i in range(5):
            trail_fly = max(0.0, fly - trail_i * 0.06)
            trail_leg_x = cx - 26 - 170 * trail_fly
            trail_leg_y = floor_y - 70 * math.sin(trail_fly * math.pi) + 20 * trail_fly
            trail_a = max(0, 55 - trail_i * 12)
            trail_len = CB_BROKEN_LEG_LEN - trail_i * 8
            _cb_draw_metal_leg(trail_surf,
                               (int(trail_leg_x), int(trail_leg_y)),
                               length=max(20, trail_len),
                               width=CB_BROKEN_LEG_W,
                               angle_deg=leg_ang, jagged=True,
                               glow=False, alpha=trail_a)
        surface.blit(trail_surf, (0, 0))

        _cb_draw_metal_leg(surface, (leg_x, leg_y),
                           length=CB_BROKEN_LEG_LEN, width=CB_BROKEN_LEG_W,
                           angle_deg=leg_ang, jagged=True, glow=True)

    # --- DIRECTED metal shard debris ---
    # Shards spray in a cone FROM the break point TOWARD lower-left (where the leg flew)
    _cb_draw_debris_burst(surface,
                          (cx + int(72 * 1.02), seat_y + int(112 * 1.02)),
                          t, break_p, count=58, metal=True)

    # Extra directional shards — long thin lines radiating outward
    if break_p > 0.05:
        shard_rng = random.Random(7722)
        for i in range(14):
            shard_angle_base = math.radians(-150 + i * 22)  # cone facing lower-left
            shard_angle = shard_angle_base + shard_rng.uniform(-0.3, 0.3)
            shard_speed = shard_rng.uniform(40, 140)
            shard_age = max(0, break_p - shard_rng.uniform(0, 0.08))
            if shard_age <= 0:
                continue
            shard_x = cx + 72 + math.cos(shard_angle) * shard_speed * shard_age
            shard_y = seat_y + 112 + math.sin(shard_angle) * shard_speed * shard_age
            shard_len = shard_rng.randint(8, 28)
            shard_a = max(0, int(200 * (1.0 - shard_age / 0.9)))
            shard_surf = pygame.Surface((shard_len + 4, 4), pygame.SRCALPHA)
            pygame.draw.line(shard_surf,
                             (*random.choice([(96, 96, 92), (62, 60, 56), (138, 128, 105)]), shard_a),
                             (2, 2), (shard_len + 2, 2), 2)
            rot_shard = pygame.transform.rotate(shard_surf, -math.degrees(shard_angle))
            surface.blit(rot_shard, (int(shard_x - rot_shard.get_width() // 2),
                                     int(shard_y - rot_shard.get_height() // 2)))

    # Dust cloud — billows outward from break point, not a perfect circle
    if break_p > 0.05:
        dust_age = min(1.0, (p - 0.05) / 0.42)
        dust_fade = max(0.0, 1.0 - _cb_clamp((p - 0.42) / 0.55))
        dust_a = int(120 * dust_age * dust_fade)
        if dust_a > 0:
            dust = pygame.Surface((460, 280), pygame.SRCALPHA)
            rng = random.Random(1201)
            for _ in range(80):
                dx = rng.randint(-200, 60)   # biased left (toward where leg went)
                dy = rng.randint(-60, 140)   # biased down
                rr = rng.randint(8, 30)
                a = max(0, int(dust_a * (1 - abs(dx) / 260) * rng.uniform(0.5, 1.0)))
                pygame.draw.circle(dust, (118, 112, 100, a),
                                   (230 + dx, 120 + dy), rr)
            surface.blit(dust, (int(cx + 72 - 230), int(seat_y + 112 - 120)))

    _cb_draw_flash(surface, 38 * impact)
    _cb_finish(surface, t, "CHAIR LEG SEVERED")


def _draw_cb_grab(surface, t_value, *args, clock_is_ms=False, **kwargs):
    """Shot 3 — Hand closes around the broken leg. Fixed finger curl."""
    t = _cb_time_to_frames(t_value, clock_is_ms)
    p = _cb_clamp(t / float(CB_SHOT3_DUR))
    reach = _cb_smooth((t - 14.0) / 76.0)
    grip = _cb_smooth((t - 82.0) / 40.0)

    sx, sy = _cb_camera_shake(t, amount=2.0, decay=1.0 - grip * 0.4)
    _cb_cinematic_bg(surface, WIDTH // 2, HEIGHT // 2, "grab", t=t, op=1.0)
    _cb_tube_flicker(surface, WIDTH // 2 - 60, 110, t, base_alpha=75)

    # --- The leg lying on the floor ---
    leg_center = (int(WIDTH // 2 - 115 + sx), int(392 + sy))
    _cb_draw_metal_leg(surface, leg_center,
                       length=CB_BROKEN_LEG_LEN, width=CB_BROKEN_LEG_W,
                       angle_deg=CB_BROKEN_LEG_ANGLE, jagged=True, glow=True)

    # Floor shadow under the leg
    shadow = pygame.Surface((260, 48), pygame.SRCALPHA)
    pygame.draw.ellipse(shadow, (0, 0, 0, 95), (0, 8, 260, 28))
    surface.blit(shadow, (leg_center[0] - 130, leg_center[1] + 14))

    # --- Left support hand (enters early, stabilises the leg) ---
    wrist_x = int(WIDTH + 70 + (leg_center[0] + 48 - (WIDTH + 70)) * reach)
    wrist_y = int(472 + (leg_center[1] + 2 - 472) * reach)
    elbow = (int(wrist_x + 120 - 30 * reach), int(wrist_y + 42 + 12 * math.sin(t * 0.06)))
    _cb_draw_forearm(surface, elbow, (wrist_x, wrist_y), sleeve=True, alpha=245)

    # --- RIGHT HAND — the grabbing hand with proper finger curl ---
    # The hand enters from below-right and closes around the tube.
    # grip: 0 = hand open approaching, 1 = fingers fully curled around tube

    # Right hand entry trajectory
    rh_start = (int(WIDTH + 140), int(HEIGHT - 30))
    rh_end = (leg_center[0] - 20, leg_center[1] - 6)  # grips the tube mid-section
    rh_x = int(rh_start[0] + (rh_end[0] - rh_start[0]) * reach)
    rh_y = int(rh_start[1] + (rh_end[1] - rh_start[1]) * reach)

    # Forearm sleeve from off-screen right
    forearm_start = (int(rh_x + 110), int(rh_y + 55))
    _cb_draw_forearm(surface, forearm_start, (rh_x, rh_y), sleeve=True, alpha=245)

    # --- FINGER CURL GEOMETRY ---
    # The tube runs at CB_BROKEN_LEG_ANGLE degrees.
    # Fingers must curl AROUND it — their tips point BEHIND the tube
    # from the viewer's perspective (top-down-ish 3/4 angle).
    #
    # We model the tube as a cylinder:
    #   - near_side: the surface facing the camera (top of tube)
    #   - far_side: the surface away from camera (bottom of tube)
    # The palm rests on the near_side. Fingers wrap over and grip the far_side.
    # The thumb braces on the near_side from below.

    tube_angle_rad = math.radians(CB_BROKEN_LEG_ANGLE)
    tube_dx = math.cos(tube_angle_rad)
    tube_dy = math.sin(tube_angle_rad)
    # Perpendicular to tube (points "over" the tube toward far side)
    perp_dx = -tube_dy
    perp_dy = tube_dx

    tube_r = CB_BROKEN_LEG_W / 2  # tube radius in pixels

    # Palm rests centered on the near face of the tube
    palm_cx = float(rh_x)
    palm_cy = float(rh_y)

    # How open/closed the grip is:
    # 0 = fingers straight (approaching), 1 = fully curled around tube
    curl = grip  # 0..1

    # --- PALM ---
    palm_w = 28
    palm_h = 16
    palm_pts = [
        (palm_cx - tube_dx * palm_w * 0.5 - perp_dx * palm_h * 0.3,
         palm_cy - tube_dy * palm_w * 0.5 - perp_dy * palm_h * 0.3),
        (palm_cx + tube_dx * palm_w * 0.5 - perp_dx * palm_h * 0.3,
         palm_cy + tube_dy * palm_w * 0.5 - perp_dy * palm_h * 0.3),
        (palm_cx + tube_dx * palm_w * 0.5 + perp_dx * palm_h * 0.7,
         palm_cy + tube_dy * palm_w * 0.5 + perp_dy * palm_h * 0.7),
        (palm_cx - tube_dx * palm_w * 0.5 + perp_dx * palm_h * 0.7,
         palm_cy - tube_dy * palm_w * 0.5 + perp_dy * palm_h * 0.7),
    ]
    pygame.draw.polygon(surface, CB_SKIN, [(int(x), int(y)) for x, y in palm_pts])
    pygame.draw.polygon(surface, CB_SKIN_SHADE, [(int(x), int(y)) for x, y in palm_pts], 1)

    # Shadow on the palm where the tube rests against it
    shadow_strip_pts = [
        (palm_cx - tube_dx * tube_r - perp_dx * 2, palm_cy - tube_dy * tube_r - perp_dy * 2),
        (palm_cx + tube_dx * tube_r - perp_dx * 2, palm_cy + tube_dy * tube_r - perp_dy * 2),
        (palm_cx + tube_dx * tube_r + perp_dx * 5, palm_cy + tube_dy * tube_r + perp_dy * 5),
        (palm_cx - tube_dx * tube_r + perp_dx * 5, palm_cy - tube_dy * tube_r + perp_dy * 5),
    ]
    shadow_surf = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
    pygame.draw.polygon(shadow_surf, (*CB_SKIN_SHADE, 80),
                        [(int(x), int(y)) for x, y in shadow_strip_pts])
    surface.blit(shadow_surf, (0, 0))

    # --- FOUR FINGERS wrapping around the tube ---
    # Each finger:
    #   base: at palm edge on near side, spaced along the tube axis
    #   segment 1: goes perpendicular across the near face of the tube
    #   segment 2: curls around the far side (behind tube from camera)
    #   tip: rests on far side or just peeks out
    # The curl angle drives how much they wrap.

    finger_offsets = [-10, -3, 4, 11]  # offset along tube axis from palm center
    finger_thick = [4, 5, 5, 4]        # index is thinnest, middle/ring are thicker

    for fi, (foff, fthick) in enumerate(zip(finger_offsets, finger_thick)):
        # Base of this finger at the near palm edge
        base_x = palm_cx + tube_dx * foff - perp_dx * palm_h * 0.3
        base_y = palm_cy + tube_dy * foff - perp_dy * palm_h * 0.3

        # Segment 1: crosses the near face (always visible from camera)
        # Goes from base, over the tube top, toward far side
        seg1_len = tube_r * 1.2 + 4  # slightly longer than radius so it grips
        seg1_end_x = base_x + perp_dx * seg1_len
        seg1_end_y = base_y + perp_dy * seg1_len

        # Segment 2: the curl — rotates based on curl progress
        # At curl=0: points straight (parallel to perp, continuing over)
        # At curl=1: bends back toward the near side (finger tip points down)
        curl_angle = math.radians(curl * 195)  # 0 = straight over, 195 = fully wrapped
        # Rotation in the plane perpendicular to the tube axis
        seg2_local_x = math.cos(curl_angle - math.pi / 2)  # starts going over tube
        seg2_local_y = math.sin(curl_angle - math.pi / 2)
        # Convert to screen space
        seg2_screen_dx = perp_dx * seg2_local_x + tube_dx * seg2_local_y
        seg2_screen_dy = perp_dy * seg2_local_x + tube_dy * seg2_local_y

        seg2_len = 14 - fi * 1.2  # index finger shortest, ring longest
        seg2_end_x = seg1_end_x + seg2_screen_dx * seg2_len
        seg2_end_y = seg1_end_y + seg2_screen_dy * seg2_len

        # Tip — short knuckle segment
        tip_curl = math.radians(curl * 80)
        tip_dir_x = seg2_screen_dx * math.cos(tip_curl) - seg2_screen_dy * math.sin(tip_curl)
        tip_dir_y = seg2_screen_dx * math.sin(tip_curl) + seg2_screen_dy * math.cos(tip_curl)
        tip_len = 8
        tip_end_x = seg2_end_x + tip_dir_x * tip_len
        tip_end_y = seg2_end_y + tip_dir_y * tip_len

        # Draw the three segments with knuckle shading
        # Segment 1 (most lit — facing camera on near side)
        seg1_col = CB_SKIN
        pygame.draw.line(surface, CB_SKIN_SHADE,
                         (int(base_x + 1), int(base_y + 1)),
                         (int(seg1_end_x + 1), int(seg1_end_y + 1)), fthick + 1)
        pygame.draw.line(surface, seg1_col,
                         (int(base_x), int(base_y)),
                         (int(seg1_end_x), int(seg1_end_y)), fthick)

        # Knuckle 1 (near edge of tube — catches light from above)
        k1_x = int(base_x + perp_dx * tube_r)
        k1_y = int(base_y + perp_dy * tube_r)
        pygame.draw.circle(surface, (CB_SKIN[0] + 15, CB_SKIN[1] + 12, CB_SKIN[2] + 8),
                           (k1_x, k1_y), max(2, fthick // 2 + 1))

        # Segment 2 (wrapping around — partially in shadow, partially lit)
        # Blend color from skin toward shade as we go around
        seg2_blend = curl  # 0=lit, 1=darker
        seg2_col = (
            int(CB_SKIN[0] * (1 - seg2_blend * 0.4)),
            int(CB_SKIN[1] * (1 - seg2_blend * 0.35)),
            int(CB_SKIN[2] * (1 - seg2_blend * 0.3)),
        )
        pygame.draw.line(surface, CB_SKIN_SHADE,
                         (int(seg1_end_x + 1), int(seg1_end_y + 1)),
                         (int(seg2_end_x + 1), int(seg2_end_y + 1)), fthick)
        pygame.draw.line(surface, seg2_col,
                         (int(seg1_end_x), int(seg1_end_y)),
                         (int(seg2_end_x), int(seg2_end_y)), max(2, fthick - 1))

        # Knuckle 2 (far side of tube — in shadow)
        k2_x = int(seg1_end_x + seg2_screen_dx * seg2_len * 0.5)
        k2_y = int(seg1_end_y + seg2_screen_dy * seg2_len * 0.5)
        pygame.draw.circle(surface, CB_SKIN_SHADE,
                           (k2_x, k2_y), max(2, fthick // 2))

        # Tip segment (darkest — on far side, in full shadow)
        tip_col = CB_SKIN_SHADE
        if curl > 0.2:
            pygame.draw.line(surface, (CB_SKIN_SHADE[0] - 10, CB_SKIN_SHADE[1] - 8, CB_SKIN_SHADE[2] - 6),
                             (int(seg2_end_x + 1), int(seg2_end_y + 1)),
                             (int(tip_end_x + 1), int(tip_end_y + 1)), max(2, fthick - 1))
            pygame.draw.line(surface, tip_col,
                             (int(seg2_end_x), int(seg2_end_y)),
                             (int(tip_end_x), int(tip_end_y)), max(2, fthick - 1))

            # Fingertip nail — tiny bright crescent on the very end
            nail_x = int(tip_end_x)
            nail_y = int(tip_end_y)
            nail_col = (CB_SKIN[0] - 20, CB_SKIN[1] - 25, CB_SKIN[2] - 30)
            pygame.draw.circle(surface, nail_col, (nail_x, nail_y), max(1, fthick // 2 - 1))

    # --- THUMB opposing the fingers ---
    # Thumb base is below/beside the palm on the near side
    # It doesn't wrap around — it braces against the tube from the far side
    thumb_base_x = palm_cx - tube_dx * 14 + perp_dx * palm_h * 0.5
    thumb_base_y = palm_cy - tube_dy * 14 + perp_dy * palm_h * 0.5

    # Thumb first segment: goes slightly across tube (shorter than fingers)
    thumb_seg1_end_x = thumb_base_x + perp_dx * (tube_r * 0.8)
    thumb_seg1_end_y = thumb_base_y + perp_dy * (tube_r * 0.8)

    # Thumb tip: curls toward fingers (opposing grip)
    # At grip=0: sticks out, at grip=1: presses against tube
    thumb_curl = math.radians(grip * 110)
    thumb_tip_dx = perp_dx * math.cos(thumb_curl) + tube_dx * math.sin(thumb_curl)
    thumb_tip_dy = perp_dy * math.cos(thumb_curl) + tube_dy * math.sin(thumb_curl)
    thumb_tip_end_x = thumb_seg1_end_x + thumb_tip_dx * 12
    thumb_tip_end_y = thumb_seg1_end_y + thumb_tip_dy * 12

    # Draw thumb — slightly thicker than fingers
    pygame.draw.line(surface, CB_SKIN_SHADE,
                     (int(thumb_base_x + 1), int(thumb_base_y + 1)),
                     (int(thumb_seg1_end_x + 1), int(thumb_seg1_end_y + 1)), 7)
    pygame.draw.line(surface, CB_SKIN,
                     (int(thumb_base_x), int(thumb_base_y)),
                     (int(thumb_seg1_end_x), int(thumb_seg1_end_y)), 6)

    # Thumb knuckle
    pygame.draw.circle(surface, (CB_SKIN[0] + 10, CB_SKIN[1] + 8, CB_SKIN[2] + 5),
                       (int(thumb_seg1_end_x), int(thumb_seg1_end_y)), 4)

    # Thumb tip
    if grip > 0.1:
        pygame.draw.line(surface, CB_SKIN_SHADE,
                         (int(thumb_seg1_end_x + 1), int(thumb_seg1_end_y + 1)),
                         (int(thumb_tip_end_x + 1), int(thumb_tip_end_y + 1)), 6)
        pygame.draw.line(surface, CB_SKIN,
                         (int(thumb_seg1_end_x), int(thumb_seg1_end_y)),
                         (int(thumb_tip_end_x), int(thumb_tip_end_y)), 5)
        # Thumbnail
        pygame.draw.circle(surface, (CB_SKIN[0] - 15, CB_SKIN[1] - 18, CB_SKIN[2] - 22),
                           (int(thumb_tip_end_x), int(thumb_tip_end_y)), 3)

    # --- Contact pressure indent where thumb presses the tube ---
    if grip > 0.4:
        indent_a = int(80 * (grip - 0.4) / 0.6)
        indent = pygame.Surface((20, 14), pygame.SRCALPHA)
        pygame.draw.ellipse(indent, (CB_SKIN_SHADE[0], CB_SKIN_SHADE[1], CB_SKIN_SHADE[2], indent_a),
                            (0, 0, 20, 14))
        surface.blit(indent, (int(thumb_tip_end_x - 10), int(thumb_tip_end_y - 7)))

    # --- Grip glint when fully closed ---
    if grip > 0.6:
        glint_a = int(120 * (grip - 0.6) / 0.4 * (0.5 + 0.5 * math.sin(t * 0.5)))
        if glint_a > 0:
            _cb_draw_shiv_spark(surface,
                                leg_center[0] - 18, leg_center[1] - 10,
                                (grip - 0.6) / 0.4)

    # Small metal glint where the fingers contact the tube surface
    if grip > 0.25:
        contact_a = int(70 * (grip - 0.25) / 0.75)
        contact_surf = pygame.Surface((18, 6), pygame.SRCALPHA)
        pygame.draw.ellipse(contact_surf, (200, 210, 215, contact_a), contact_surf.get_rect())
        surface.blit(contact_surf, (int(palm_cx + perp_dx * tube_r - 9),
                                    int(palm_cy + perp_dy * tube_r - 3)))

    _cb_finish(surface, t, "IMPROVISED WEAPON LOCATED")


def _cb_draw_ready_biribel(surface, cx, foot_y, p, t):
    """Standing silhouette, one hand hefting the chair leg."""
    # Backlit body.
    draw_biribel(surface, int(cx), int(foot_y), scale=1.12,
                 facing_right=True, in_silhouette=True)
    # Subtle rim lights on shoulders/head.
    pygame.draw.arc(surface, (115, 140, 150),
                    (int(cx - 36), int(foot_y - 300), 72, 56),
                    math.pi * 0.05, math.pi * 0.95, 2)
    pygame.draw.line(surface, (84, 105, 112),
                     (int(cx + 32), int(foot_y - 224)),
                     (int(cx + 50), int(foot_y - 120)), 2)

    # Raising arm and weapon.
    lift = _cb_smooth(p)
    hand = (int(cx + 55), int(foot_y - 160 - 72 * lift))
    elbow = (int(cx + 18), int(foot_y - 116 - 30 * lift))
    _cb_draw_forearm(surface, elbow, hand, sleeve=True, alpha=240)
    angle = -62 - 10 * lift + math.sin(t * 0.05) * 1.5
    leg_center = (hand[0] + int(52 * math.cos(math.radians(angle))),
                  hand[1] + int(52 * math.sin(math.radians(angle))))
    _cb_draw_metal_leg(surface, leg_center, length=165, width=13,
                       angle_deg=angle, jagged=True, glow=True)
    # Off-hand steadies the lower part of the pipe.
    off_hand = (int(cx + 6), int(foot_y - 132))
    _cb_draw_forearm(surface, (int(cx - 28), int(foot_y - 118)), off_hand,
                     sleeve=True, alpha=210)


def _draw_cb_ready(surface, t_value, *args, clock_is_ms=False, **kwargs):
    """Shot 4 — resolve: Biribel stands with the chair leg ready."""
    t = _cb_time_to_frames(t_value, clock_is_ms)
    p = _cb_clamp(t / float(CB_SHOT4_DUR))
    rise = _cb_smooth((t - 10.0) / 88.0)
    sx, sy = _cb_camera_shake(t, amount=1.4, decay=1.0)
    cx = WIDTH // 2 - 34 + int(sx)
    foot_y = HEIGHT - 118 + int(sy)

    _cb_cinematic_bg(surface, WIDTH // 2, HEIGHT // 2, "ready", t=t, op=1.0)

    # Breached doorway / Volkov silhouette to the right, so the shot connects
    # to the preceding interrogation scene and the gameplay objective.
    door_x = WIDTH // 2 + 245
    door_y = LETTER_H + 86
    door_w, door_h = 150, 355
    pygame.draw.rect(surface, (18, 20, 22), (door_x - 10, door_y - 8, door_w + 20, door_h + 16))
    pygame.draw.rect(surface, (50, 48, 42), (door_x, door_y, door_w, door_h))
    spill = pygame.Surface((360, 430), pygame.SRCALPHA)
    for yy in range(430):
        a = int(max(0, 65 * (1 - yy / 430)))
        pygame.draw.line(spill, (220, 210, 180, a), (0, yy), (360, yy))
    surface.blit(spill, (door_x - 140, door_y))
    draw_volkov(surface, door_x + door_w // 2, HEIGHT - 118,
                scale=0.78, facing_right=False)

    # Biribel rises from crouch to full ready pose.
    crouch_offset = int((1.0 - rise) * 52)
    _cb_draw_ready_biribel(surface, cx, foot_y + crouch_offset, rise, t)

    # Cold light from above and a final weapon glint.
    _cb_tube_flicker(surface, int(cx), 118, t, base_alpha=105)
    if rise > 0.72:
        glint_alpha = int(65 * (0.5 + 0.5 * math.sin(t * 0.38)))
        _cb_draw_flash(surface, glint_alpha * 0.05)

    _cb_finish(surface, t, "CHAIR LEG ACQUIRED")


def _draw_k9_pickup_bg(surface, t):
    """Clean first-person armory backdrop for the K-9 pickup.

    No big glow/glitch/AI-looking effects. Just a wall rack, bolts, hooks, and
    dim armory lighting.
    """
    surface.fill((7, 9, 9))
    # Plain armory wall.
    for y in range(SCENE_TOP, SCENE_BOT):
        p = (y - SCENE_TOP) / max(1, SCENE_BOT - SCENE_TOP)
        pygame.draw.line(surface, (int(13 + p * 15), int(17 + p * 15), int(17 + p * 14)), (0, y), (WIDTH, y))
    # Large concrete panels, not tiny busy grid.
    for x in range(80, WIDTH, 160):
        pygame.draw.line(surface, (18, 24, 24), (x, SCENE_TOP), (x, SCENE_BOT), 1)
    for y in range(SCENE_TOP + 70, SCENE_BOT, 92):
        pygame.draw.line(surface, (18, 24, 24), (70, y), (WIDTH - 70, y), 1)

    rack = pygame.Rect(WIDTH // 2 - 245, SCENE_TOP + 105, 490, 230)
    pygame.draw.rect(surface, (10, 14, 14), rack, border_radius=5)
    pygame.draw.rect(surface, (58, 72, 68), rack, 2, border_radius=5)
    pygame.draw.line(surface, (92, 105, 96), (rack.x + 18, rack.y + 36), (rack.right - 18, rack.y + 36), 2)
    pygame.draw.line(surface, (38, 50, 46), (rack.x + 24, rack.y + 88), (rack.right - 24, rack.y + 88), 2)
    pygame.draw.line(surface, (38, 50, 46), (rack.x + 24, rack.y + 142), (rack.right - 24, rack.y + 142), 2)
    title = font_terminal_small.render("ARMORY RACK // K-9", True, (118, 155, 136))
    surface.blit(title, (rack.x + 20, rack.y + 13))
    # Bolts / peg holes.
    for bx in (rack.x + 18, rack.right - 18):
        for by in (rack.y + 16, rack.bottom - 16):
            pygame.draw.circle(surface, (66, 72, 66), (bx, by), 3)
            pygame.draw.circle(surface, (18, 20, 18), (bx, by), 1)
    return rack


def _draw_k9_smg_fp(surface, cx, cy, t, held=False, scale=1.0):
    """Compact first-person K-9 drawing.

    Short receiver, short integral suppressor, collapsed wire stock, straight
    stick mag. Avoids the previous long LMG-looking silhouette.
    """
    s = scale
    def S(v): return int(v * s)

    # Coordinates in rack/screen space.
    rec = pygame.Rect(cx - S(86), cy - S(18), S(130), S(36))
    # Receiver body.
    pygame.draw.rect(surface, (21, 25, 25), rec, border_radius=S(6))
    pygame.draw.rect(surface, (82, 100, 94), rec, 2, border_radius=S(6))
    pygame.draw.line(surface, (126, 148, 138), (rec.x + S(12), rec.y + S(7)), (rec.right - S(16), rec.y + S(7)), max(1, S(2)))
    # Ejection/safety detail.
    pygame.draw.rect(surface, (10, 13, 13), (rec.x + S(48), rec.y + S(14), S(26), S(9)), border_radius=S(2))
    pygame.draw.circle(surface, (65, 160, 105), (rec.x + S(23), rec.y + S(19)), max(2, S(3)))

    # Short suppressor.
    sup = pygame.Rect(rec.right - S(5), cy - S(10), S(62), S(20))
    pygame.draw.rect(surface, (34, 40, 40), sup, border_radius=S(8))
    pygame.draw.rect(surface, (100, 116, 108), sup, 1, border_radius=S(8))
    pygame.draw.circle(surface, (5, 7, 7), (sup.right, cy), max(3, S(6)))

    # Straight magazine, shorter.
    mag = pygame.Rect(cx - S(16), cy + S(18), S(22), S(70))
    pygame.draw.rect(surface, (16, 19, 19), mag, border_radius=S(3))
    pygame.draw.rect(surface, (82, 96, 88), mag, 2, border_radius=S(3))
    for row in range(7):
        yy = mag.y + S(10) + row * S(8)
        pygame.draw.circle(surface, (190, 160, 58), (mag.x + S(7), yy), max(1, S(2)))
        pygame.draw.circle(surface, (190, 160, 58), (mag.x + S(15), yy), max(1, S(2)))
    pygame.draw.rect(surface, (10, 12, 12), (mag.x, mag.bottom - S(7), mag.w, S(8)), border_radius=S(2))

    # Collapsed wire stock.
    pygame.draw.line(surface, (65, 74, 70), (rec.x + S(5), cy + S(8)), (rec.x - S(48), cy + S(25)), max(1, S(3)))
    pygame.draw.line(surface, (42, 48, 46), (rec.x + S(5), cy - S(5)), (rec.x - S(48), cy + S(12)), max(1, S(2)))
    pygame.draw.circle(surface, (45, 52, 50), (rec.x - S(48), cy + S(25)), max(2, S(4)))

    # Pistol grip.
    grip = [(cx - S(62), cy + S(16)), (cx - S(38), cy + S(16)),
            (cx - S(45), cy + S(64)), (cx - S(68), cy + S(64))]
    pygame.draw.polygon(surface, (18, 21, 21), grip)
    pygame.draw.polygon(surface, (78, 88, 84), grip, 2)

    # Label on receiver, small and grounded.
    label = font_terminal_small.render("K-9", True, (150, 210, 185))
    surface.blit(label, (cx - label.get_width() // 2 + S(15), cy - S(6)))

    if held:
        # Forearms/hands, simple and clean. No giant arms/effects.
        skin = (176, 132, 100)
        sleeve = (52, 60, 56)
        pygame.draw.line(surface, sleeve, (cx - S(54), cy + S(72)), (cx - S(120), HEIGHT + S(30)), S(22))
        pygame.draw.line(surface, sleeve, (cx + S(48), cy + S(36)), (cx + S(120), HEIGHT + S(30)), S(20))
        pygame.draw.circle(surface, skin, (cx - S(54), cy + S(62)), S(13))
        pygame.draw.circle(surface, skin, (cx + S(46), cy + S(28)), S(12))


def _draw_k9_wall_stand(surface, t):
    rack = _draw_k9_pickup_bg(surface, t)
    cx = rack.centerx
    cy = rack.centery + 8
    _draw_k9_smg_fp(surface, cx, cy, t, held=False, scale=1.0)
    # Plain hooks over the weapon.
    for hx in (cx - 70, cx + 72):
        pygame.draw.line(surface, (140, 138, 120), (hx, cy - 45), (hx, cy - 8), 3)
        pygame.draw.arc(surface, (140, 138, 120), (hx - 11, cy - 13, 22, 20), 0, math.pi, 2)
    cap = font_terminal.render("K-9 SUPPRESSED SMG", True, (150, 220, 190))
    surface.blit(cap, (WIDTH // 2 - cap.get_width() // 2, SCENE_BOT - 90))


def _draw_k9_firstperson_grab(surface, t):
    rack = _draw_k9_pickup_bg(surface, t)
    p = min(1.0, max(0.0, t / 1100.0))
    # Smooth pull off the hooks and slightly down toward camera.
    lift = p * p * (3 - 2 * p)
    cx = rack.centerx
    cy = rack.centery + 8 + int(22 * lift)
    # Empty silhouette behind weapon.
    pygame.draw.rect(surface, (5, 7, 7), (rack.centerx - 105, rack.centery - 32, 210, 65), border_radius=5)
    _draw_k9_smg_fp(surface, cx, cy, t, held=True, scale=1.0 + 0.08 * lift)
    txt = font_terminal_small.render("UNHOOK", True, (115, 160, 135))
    surface.blit(txt, (WIDTH // 2 - txt.get_width() // 2, SCENE_BOT - 76))


def _draw_k9_ready_check(surface, t):
    """Final K-9 pickup beat: clean ready check.

    The old version drew the weapon with its default two hands, then added a
    charging-handle hand and a mag-slap hand on top. That produced four random
    tan circles. This version draws exactly two hands: support hand on the magwell
    and action hand on the charging handle.
    """
    _draw_k9_pickup_bg(surface, t)
    p = min(1.0, max(0.0, t / 1200.0))
    cx = WIDTH // 2
    cy = SCENE_TOP + 270

    # Draw only the gun. Hands are placed deliberately below.
    _draw_k9_smg_fp(surface, cx, cy, t, held=False, scale=1.08)

    skin = (176, 132, 100)
    sleeve = (52, 60, 56)

    # Support hand: locked around the magazine well / front of receiver.
    support_hand = (cx - 18, cy + 58)
    pygame.draw.line(surface, sleeve,
                     (support_hand[0] - 58, HEIGHT + 34),
                     (support_hand[0] - 5, support_hand[1] + 10), 22)
    pygame.draw.circle(surface, skin, support_hand, 13)
    # Fingers wrapping the magwell.
    for off in (-5, 0, 5):
        pygame.draw.line(surface, (135, 96, 72),
                         (support_hand[0] + off, support_hand[1] - 7),
                         (support_hand[0] + off + 2, support_hand[1] + 8), 2)

    # Action hand: pulls the charging handle, then returns.
    pull = int(24 * max(0.0, 1.0 - abs(p - 0.42) / 0.22))
    handle_start = (cx + 29, cy - 22)
    handle_end = (cx + 29 - pull, cy - 22)
    pygame.draw.line(surface, (118, 130, 124), handle_start, handle_end, 5)
    action_hand = (handle_end[0] - 6, handle_end[1] + 2)
    pygame.draw.line(surface, sleeve,
                     (action_hand[0] + 78, HEIGHT + 34),
                     (action_hand[0] + 8, action_hand[1] + 10), 20)
    pygame.draw.circle(surface, skin, action_hand, 12)
    pygame.draw.circle(surface, (120, 80, 58), (action_hand[0] - 3, action_hand[1] + 2), 2)

    # Mechanical feedback instead of extra hand blobs.
    if 0.56 < p < 0.78:
        lock_p = (p - 0.56) / 0.22
        tick_x = cx + 6
        tick_y = cy + 22
        pygame.draw.line(surface, (150, 170, 150),
                         (tick_x - 10, tick_y),
                         (tick_x + int(18 * lock_p), tick_y), 2)
        pygame.draw.circle(surface, (80, 160, 110), (tick_x + int(18 * lock_p), tick_y), 2)

    txt = font_terminal.render("K-9 READY", True, (150, 220, 190))
    surface.blit(txt, (WIDTH // 2 - txt.get_width() // 2, SCENE_BOT - 86))


def _draw_m3_volkov_radio_call(surface, t):
    """Transition beat: Volkov throws Biribel's radio and Biribel catches it.

    Clear staging:
      1. Volkov yells from the service doorway.
      2. The radio flies across the frame.
      3. Biribel's hands rise into frame and catch it near the end.

    The next shot is the close-up power-on insert.
    """
    surface.fill((4, 5, 6))
    cx = WIDTH // 2
    floor_y = SCENE_BOT - 78

    # Service corridor / door backdrop.
    for y in range(SCENE_TOP, SCENE_BOT):
        pbg = (y - SCENE_TOP) / max(1, SCENE_BOT - SCENE_TOP)
        pygame.draw.line(surface, (int(7 + pbg * 18), int(9 + pbg * 20), int(10 + pbg * 18)), (0, y), (WIDTH, y))
    pygame.draw.polygon(surface, (16, 19, 20), [(0, floor_y), (WIDTH, floor_y), (WIDTH, SCENE_BOT), (0, SCENE_BOT)])
    for x in range(0, WIDTH, 110):
        pygame.draw.line(surface, (23, 27, 27), (x, floor_y), (x + 50, SCENE_BOT), 1)

    # Backlit doorway with Volkov.
    door = pygame.Rect(cx - 320, SCENE_TOP + 76, 230, 360)
    pygame.draw.rect(surface, (4, 5, 6), door.inflate(24, 24), border_radius=5)
    pygame.draw.rect(surface, (52, 78, 70), door, border_radius=3)
    pygame.draw.rect(surface, (115, 170, 145), door, 2, border_radius=3)
    spill = pygame.Surface((340, 260), pygame.SRCALPHA)
    pygame.draw.polygon(spill, (90, 140, 120, 34), [(120, 0), (220, 0), (340, 260), (0, 260)])
    surface.blit(spill, (door.centerx - 170, door.bottom - 20))
    draw_volkov(surface, door.centerx - 12, floor_y + 16, scale=0.62, facing_right=True)

    # Throw origin. Do NOT draw a custom arm here: the base Volkov sprite
    # already has arms, and the extra cutscene-only arm read as a detached hand.
    # The radio begins near his silhouette and immediately becomes the focus.
    throw_origin = (door.centerx + 58, floor_y - 142)
    # Tiny dark motion wedge from his hand area, connected enough to imply a toss
    # without adding a separate limb.
    pygame.draw.line(surface, (18, 18, 24),
                     (door.centerx + 16, floor_y - 145),
                     (throw_origin[0], throw_origin[1]), 5)

    # Shout marks near Volkov's head.
    for i in range(3):
        pygame.draw.arc(surface, (210, 170, 90, 118 - i * 32),
                        (door.centerx + 28 + i * 12, floor_y - 198 - i * 8, 92 + i * 20, 62 + i * 12),
                        -0.55, 0.42, 2)

    # Throw path: radio travels to Biribel's hands, then stays caught for the
    # rest of the shot. The catch happens early enough that the dialogue beat
    # clearly shows Biribel receiving it, not just watching it fly by.
    p = min(1.0, max(0.0, t / 1150.0))
    flight = min(1.0, p / 0.70)
    ease = 1.0 - (1.0 - flight) * (1.0 - flight)
    start_x, start_y = throw_origin[0] + 14, throw_origin[1] - 8
    catch_x, catch_y = cx + 190, floor_y - 125
    arc = math.sin(flight * math.pi) * 38
    radio_cx = start_x + (catch_x - start_x) * ease
    radio_cy = start_y + (catch_y - start_y) * ease - arc

    catch_p = min(1.0, max(0.0, (p - 0.34) / 0.30))
    caught = catch_p >= 1.0
    # Once caught, lock the radio between Biribel's hands.
    if caught:
        radio_cx = catch_x
        radio_cy = catch_y
    tilt = (-20 + 42 * flight) * (1.0 - 0.85 * catch_p)

    # Helper for tapered first-person forearms.
    def forearm(shoulder, wrist, col, hi=None, w0=20, w1=8):
        sx, sy = shoulder
        wx, wy = wrist
        dx, dy = wx - sx, wy - sy
        dist = max(1.0, math.hypot(dx, dy))
        px, py = -dy / dist, dx / dist
        poly = [
            (sx + px * w0, sy + py * w0),
            (sx - px * w0, sy - py * w0),
            (wx - px * w1, wy - py * w1),
            (wx + px * w1, wy + py * w1),
        ]
        pygame.draw.polygon(surface, col, poly)
        pygame.draw.polygon(surface, (8, 9, 9), poly, 1)
        if hi:
            pygame.draw.line(surface, hi, (sx + px * w0 * 0.35, sy + py * w0 * 0.35),
                             (wx + px * w1 * 0.25, wy + py * w1 * 0.25), 1)

    # Biribel's hands enter and catch. They are absent early, so it reads as a
    # throw first, catch second.
    skin = (176, 132, 100)
    sleeve = (58, 68, 52)
    left_hand = (radio_cx - 36, radio_cy + 24)
    right_hand = (radio_cx + 38, radio_cy + 20)
    if catch_p > 0.02:
        # Hands move in from below/right and clamp around the radio.
        def lerp(a, b, q): return a + (b - a) * q
        q = catch_p * catch_p * (3 - 2 * catch_p)
        lh = (lerp(WIDTH - 260, left_hand[0], q), lerp(HEIGHT + 28, left_hand[1], q))
        rh = (lerp(WIDTH - 105, right_hand[0], q), lerp(HEIGHT + 30, right_hand[1], q))
        forearm((WIDTH - 330, HEIGHT + 50), lh, sleeve, (94, 108, 80), 24, 10)
        forearm((WIDTH + 45, HEIGHT + 54), rh, sleeve, (94, 108, 80), 24, 10)
        pygame.draw.circle(surface, skin, (int(lh[0]), int(lh[1])), 14)
        pygame.draw.circle(surface, skin, (int(rh[0]), int(rh[1])), 14)
        if caught:
            # Small catch impact ticks at the wrists — not a magic effect, just
            # a readable punctuation that the device has landed in his hands.
            for hx, hy, sgn in ((lh[0], lh[1], -1), (rh[0], rh[1], 1)):
                pygame.draw.line(surface, (170, 205, 160),
                                 (int(hx + sgn * 10), int(hy - 10)),
                                 (int(hx + sgn * 20), int(hy - 18)), 2)
                pygame.draw.line(surface, (120, 150, 120),
                                 (int(hx + sgn * 7), int(hy + 5)),
                                 (int(hx + sgn * 17), int(hy + 10)), 1)

    # Motion ghosts only before catch.
    if not caught and flight < 0.92:
        for i, back in enumerate((0.16, 0.08)):
            pp = max(0.0, flight - back)
            ee = 1.0 - (1.0 - pp) * (1.0 - pp)
            tx = start_x + (catch_x - start_x) * ee
            ty = start_y + (catch_y - start_y) * ee - math.sin(pp * math.pi) * 38
            ghost = pygame.Surface((70, 42), pygame.SRCALPHA)
            pygame.draw.rect(ghost, (70, 105, 94, 42 - i * 14), (8, 10, 52, 24), border_radius=4)
            ghost = pygame.transform.rotate(ghost, tilt - 6 * i)
            surface.blit(ghost, (int(tx - ghost.get_width() // 2), int(ty - ghost.get_height() // 2)))

    # Radio body.
    radio_s = pygame.Surface((104, 64), pygame.SRCALPHA)
    body = pygame.Rect(20, 14, 62, 36)
    pygame.draw.rect(radio_s, (17, 22, 22), body, border_radius=5)
    pygame.draw.rect(radio_s, (92, 118, 106), body, 2, border_radius=5)
    pygame.draw.rect(radio_s, (6, 10, 10), (body.x + 10, body.y + 10, 29, 12), border_radius=2)
    pygame.draw.circle(radio_s, (80, 220, 130), (body.right - 10, body.y + 11), 3)
    pygame.draw.circle(radio_s, (30, 36, 34), (body.right - 15, body.bottom - 10), 5)
    pygame.draw.line(radio_s, (105, 112, 104), (body.x + 13, body.y), (body.x + 4, body.y - 28), 3)
    pygame.draw.line(radio_s, (45, 52, 50), (body.x + 11, body.y), (body.x + 2, body.y - 28), 1)
    radio_s = pygame.transform.rotate(radio_s, tilt)
    surface.blit(radio_s, (int(radio_cx - radio_s.get_width() // 2), int(radio_cy - radio_s.get_height() // 2)))

    # Fingers over radio once caught, making the catch explicit.
    if catch_p > 0.78:
        for hand_pt, side in ((left_hand, -1), (right_hand, 1)):
            for i in range(4):
                fx = hand_pt[0] + side * (i * 4 - 5)
                fy = hand_pt[1] - 7 + (i % 2)
                pygame.draw.line(surface, (132, 92, 66), (fx, fy), (fx + side * 12, fy - 8), 2)
        tag = font_terminal_small.render("CAUGHT", True, (145, 210, 175))
        surface.blit(tag, (int(catch_x - tag.get_width() // 2), int(catch_y + 46)))
    else:
        tag = font_terminal_small.render("RADIO!", True, (200, 160, 90))
        surface.blit(tag, (cx - tag.get_width() // 2, SCENE_BOT - 86))


def _draw_m3_radio_recovered(surface, t):
    """Close first-person insert: Biribel catches and powers on the radio."""
    surface.fill((5, 7, 8))
    cx = WIDTH // 2
    cy = HEIGHT // 2 + 10
    # Metal table/floor plane, understated.
    for y in range(SCENE_TOP, SCENE_BOT):
        p = (y - SCENE_TOP) / max(1, SCENE_BOT - SCENE_TOP)
        pygame.draw.line(surface, (int(8 + p*18), int(12 + p*22), int(13 + p*22)), (0, y), (WIDTH, y))
    # Hands holding radio.
    skin = (176, 132, 100)
    sleeve = (58, 68, 52)
    pygame.draw.line(surface, sleeve, (cx - 210, HEIGHT + 35), (cx - 78, cy + 58), 34)
    pygame.draw.line(surface, sleeve, (cx + 210, HEIGHT + 35), (cx + 78, cy + 58), 34)
    pygame.draw.circle(surface, skin, (cx - 78, cy + 50), 24)
    pygame.draw.circle(surface, skin, (cx + 78, cy + 50), 24)
    # Radio body.
    radio = pygame.Rect(cx - 96, cy - 58, 192, 126)
    pygame.draw.rect(surface, (18, 24, 24), radio, border_radius=8)
    pygame.draw.rect(surface, (92, 116, 106), radio, 3, border_radius=8)
    pygame.draw.rect(surface, (6, 10, 10), (radio.x + 22, radio.y + 22, 88, 34), border_radius=3)
    pygame.draw.line(surface, (72, 82, 76), (radio.x + 130, radio.y + 8), (radio.x + 155, radio.y - 68), 4)
    for i in range(3):
        pygame.draw.circle(surface, (34, 40, 38), (radio.x + 136 + i*16, radio.y + 82), 7)
        pygame.draw.circle(surface, (100, 116, 104), (radio.x + 136 + i*16, radio.y + 82), 7, 1)
    # Screen boots up.
    boot = min(1.0, max(0.0, (t - 350) / 750.0))
    if boot > 0:
        glow = pygame.Surface((92, 34), pygame.SRCALPHA)
        glow.fill((80, 220, 130, int(50 + 120 * boot)))
        surface.blit(glow, (radio.x + 20, radio.y + 22), special_flags=pygame.BLEND_RGBA_ADD)
        wave_x = radio.x + 28
        wave_y = radio.y + 38
        pts = []
        for i in range(64):
            yy = wave_y + math.sin((i * 0.35) + t * 0.018) * (5 + 4 * boot)
            pts.append((wave_x + i, yy))
        if len(pts) > 1:
            pygame.draw.lines(surface, (120, 255, 170), False, pts, 2)
    text = font_terminal.render("KRAP FIELD RADIO", True, (145, 220, 175))
    surface.blit(text, (cx - text.get_width()//2, radio.bottom + 34))
    sub = font_terminal_small.render("SIGNAL: WEAK / RELAY REQUIRED", True, (90, 135, 115))
    surface.blit(sub, (cx - sub.get_width()//2, radio.bottom + 62))



def _draw_m3_service_door_transition(surface, t):
    """Transition shot: leaving the cell block through the service door."""
    surface.fill((5, 6, 7))
    # Long service corridor, centered perspective.
    cx = WIDTH // 2
    top_y = SCENE_TOP + 40
    bot_y = SCENE_BOT - 40
    # Back wall / receding floor.
    for y in range(SCENE_TOP, SCENE_BOT):
        p = (y - SCENE_TOP) / max(1, SCENE_BOT - SCENE_TOP)
        pygame.draw.line(surface, (int(8 + p*20), int(10 + p*22), int(12 + p*20)), (0, y), (WIDTH, y))
    # Perspective walls.
    van_y = SCENE_TOP + 125
    pygame.draw.polygon(surface, (12, 14, 15), [(0, SCENE_TOP), (cx - 90, van_y), (cx - 180, bot_y), (0, SCENE_BOT)])
    pygame.draw.polygon(surface, (12, 14, 15), [(WIDTH, SCENE_TOP), (cx + 90, van_y), (cx + 180, bot_y), (WIDTH, SCENE_BOT)])
    pygame.draw.polygon(surface, (20, 23, 24), [(cx - 90, van_y), (cx + 90, van_y), (cx + 180, bot_y), (cx - 180, bot_y)])
    # Floor seams.
    for i in range(9):
        y = van_y + i * 46
        pygame.draw.line(surface, (34, 38, 38), (cx - 90 - i*12, y), (cx + 90 + i*12, y), 1)
    for side in (-1, 1):
        pygame.draw.line(surface, (45, 50, 48), (cx + side*42, van_y), (cx + side*190, bot_y), 2)
    # Door frame behind player, closing.
    door_w = 230
    door_h = 240
    door_x = cx - door_w // 2
    door_y = SCENE_TOP + 95
    close_p = min(1.0, t / 1450.0)
    pygame.draw.rect(surface, (5, 5, 6), (door_x - 18, door_y - 18, door_w + 36, door_h + 36), border_radius=4)
    left_w = int((door_w // 2) * close_p)
    right_w = left_w
    pygame.draw.rect(surface, (42, 48, 50), (door_x, door_y, left_w, door_h))
    pygame.draw.rect(surface, (42, 48, 50), (door_x + door_w - right_w, door_y, right_w, door_h))
    pygame.draw.rect(surface, (90, 100, 98), (door_x, door_y, door_w, door_h), 2)
    # Narrow light slit as it closes.
    slit_w = max(2, int(door_w * (1.0 - close_p)))
    pygame.draw.rect(surface, (120, 170, 150), (cx - slit_w//2, door_y + 12, slit_w, door_h - 24))
    # Simple first-person weapon silhouette low frame.
    pygame.draw.line(surface, (14, 16, 16), (cx - 100, SCENE_BOT - 40), (cx + 20, SCENE_BOT - 82), 10)
    pygame.draw.line(surface, (55, 66, 62), (cx - 94, SCENE_BOT - 44), (cx + 15, SCENE_BOT - 80), 2)
    label = font_terminal.render("SERVICE DOOR // CELL BLOCK SEALED", True, (110, 150, 135))
    surface.blit(label, (cx - label.get_width() // 2, SCENE_BOT - 100))


def _draw_m3_comms_wing_reveal(surface, t):
    """Transition shot: first reveal of the Comms Wing."""
    surface.fill((4, 8, 9))
    # Static comms room panel, no AI-like effects.
    for y in range(SCENE_TOP, SCENE_BOT):
        p = (y - SCENE_TOP) / max(1, SCENE_BOT - SCENE_TOP)
        pygame.draw.line(surface, (int(6 + p*16), int(12 + p*24), int(13 + p*24)), (0, y), (WIDTH, y))
    # Server racks left/right.
    for side in (-1, 1):
        rack_x = WIDTH // 2 + side * 270 - 70
        rack_y = SCENE_TOP + 90
        pygame.draw.rect(surface, (12, 18, 20), (rack_x, rack_y, 140, 330), border_radius=6)
        pygame.draw.rect(surface, (60, 85, 82), (rack_x, rack_y, 140, 330), 2, border_radius=6)
        for yy in range(rack_y + 24, rack_y + 300, 24):
            pygame.draw.line(surface, (32, 48, 48), (rack_x + 10, yy), (rack_x + 130, yy), 1)
            if (yy // 24) % 3 == 0:
                pygame.draw.circle(surface, (80, 220, 130), (rack_x + 118, yy + 8), 2)
    # Main relay console.
    panel = pygame.Rect(WIDTH//2 - 210, SCENE_TOP + 155, 420, 190)
    pygame.draw.ellipse(surface, (0, 0, 0, 100), (panel.x - 20, panel.bottom - 5, panel.w + 40, 34))
    pygame.draw.rect(surface, (24, 36, 36), panel, border_radius=7)
    pygame.draw.rect(surface, (82, 120, 112), panel, 2, border_radius=7)
    header = font_terminal.render("COMMS RELAY", True, (135, 220, 190))
    surface.blit(header, (panel.centerx - header.get_width()//2, panel.y + 18))
    # Antenna dish icon and wave display.
    pygame.draw.circle(surface, (12, 18, 18), (panel.centerx, panel.y + 105), 38)
    pygame.draw.arc(surface, (120, 210, 175), (panel.centerx - 52, panel.y + 53, 104, 104), math.pi*0.15, math.pi*0.85, 3)
    pygame.draw.line(surface, (120, 210, 175), (panel.centerx, panel.y + 105), (panel.centerx + 48, panel.y + 84), 3)
    for i in range(4):
        r = 55 + i*22
        pygame.draw.arc(surface, (70, 130, 115), (panel.centerx - r, panel.y + 105 - r, r*2, r*2), -0.6, 0.6, 1)
    # Fluorescent strip above.
    pygame.draw.rect(surface, (44, 54, 52), (WIDTH//2 - 160, SCENE_TOP + 55, 320, 12), border_radius=3)
    pygame.draw.rect(surface, (170, 210, 190), (WIDTH//2 - 150, SCENE_TOP + 58, 300, 6), border_radius=3)
    caption = font_terminal_small.render("RELAY ACCESS REQUIRED", True, (110, 150, 135))
    surface.blit(caption, (WIDTH//2 - caption.get_width()//2, panel.bottom + 22))


def _draw_m3_volkov_gives_mags(surface, t):
    """First-person close-up: Biribel's own cupped hands wait at the bottom
    of frame while Volkov's arm reaches in from the top-right and tosses two
    spare magazines down into them — one per hand, well separated.

    Pacing fix: the spoken line now plays FIRST (shot 1) over Biribel's empty
    waiting hands. Only for shot 2 does Volkov's arm sweep in from off-screen,
    arc the two mags home AFTER the line is done, and retract once they're
    caught — so the handoff no longer races the dialogue. The catch is a clean
    finger-curl + soft amber rim instead of a stray tick.
    """
    surface.fill((4, 5, 6))
    cx = WIDTH // 2
    floor_y = SCENE_BOT - 30

    # Dim close-up backdrop with a soft vignette.
    for y in range(SCENE_TOP, SCENE_BOT):
        p = (y - SCENE_TOP) / max(1, SCENE_BOT - SCENE_TOP)
        pygame.draw.line(surface, (int(8 + p * 12), int(11 + p * 16), int(12 + p * 14)), (0, y), (WIDTH, y))
    pygame.draw.polygon(surface, (13, 16, 17), [(0, floor_y), (WIDTH, floor_y), (WIDTH, SCENE_BOT), (0, SCENE_BOT)])
    vig = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
    for i in range(60):
        a = max(0, 70 - i)
        pygame.draw.rect(vig, (0, 0, 0, a), (i, i, WIDTH - 2 * i, HEIGHT - 2 * i), 1)
    surface.blit(vig, (0, 0))

    skin = (176, 132, 100)
    sleeve = (58, 68, 52)

    # Helper for a tapered forearm.
    def forearm(shoulder, wrist, col, hi=None, w0=28, w1=12):
        sx, sy = shoulder
        wx, wy = wrist
        dx, dy = wx - sx, wy - sy
        dist = max(1.0, math.hypot(dx, dy))
        px, py = -dy / dist, dx / dist
        poly = [
            (sx + px * w0, sy + py * w0),
            (sx - px * w0, sy - py * w0),
            (wx - px * w1, wy - py * w1),
            (wx + px * w1, wy + py * w1),
        ]
        pygame.draw.polygon(surface, col, poly)
        pygame.draw.polygon(surface, (8, 9, 9), poly, 1)
        if hi:
            pygame.draw.line(surface, hi, (sx + px * w0 * 0.35, sy + py * w0 * 0.35),
                             (wx + px * w1 * 0.25, wy + py * w1 * 0.25), 1)

    # ── Timing (ms, cumulative since cutscene start) ──
    SHOT1_END = 2400          # the spoken line plays over shot 1
    ARM_IN = 320              # arm sweep-in duration
    ARM_OUT = 300             # arm retract duration
    ARM_RETRACT_AT = 4000     # once both mags are caught, pull back
    arm_in = max(0.0, min(1.0, (t - SHOT1_END) / ARM_IN))
    arm_out = max(0.0, min(1.0, (t - ARM_RETRACT_AT) / ARM_OUT))
    arm_vis = arm_in * (1.0 - arm_out)   # 0 -> 1 (swept in) -> 0 (retracted)

    # Biribel's two cupped hands, clearly separated at the bottom. They rise
    # into frame during the first beat and simply wait empty through shot 1.
    hand_lx, hand_ly = cx - 110, floor_y - 34
    hand_rx, hand_ry = cx + 110, floor_y - 34
    q = max(0.0, min(1.0, t / 420.0))
    q = q * q * (3 - 2 * q)
    for hx, hy in ((hand_lx, hand_ly), (hand_rx, hand_ry)):
        forearm((hx, HEIGHT + 40), (hx, hy + 14), sleeve, (94, 108, 80), 30, 13)
        pygame.draw.ellipse(surface, (60, 70, 54), (hx - 30, hy - 4, 60, 40))
        pygame.draw.ellipse(surface, skin, (hx - 23, hy - 9, 46, 30))
        pygame.draw.ellipse(surface, (150, 110, 82), (hx - 23, hy - 9, 46, 30), 2)

    # Volkov's arm exists ONLY during shot 2: it sweeps in from off-screen
    # top-right to the release point, opens to drop the mags, then retracts.
    toss_x, toss_y = WIDTH - 150, SCENE_TOP + 78
    if arm_vis > 0.001:
        ax = _lerp_cutscene(WIDTH + 90, toss_x, arm_vis)
        ay = _lerp_cutscene(SCENE_TOP - 70, toss_y, arm_vis)
        forearm((WIDTH + 120, SCENE_TOP - 90), (ax, ay), sleeve, (94, 108, 80), 28, 12)
        released = arm_in >= 1.0 and arm_out <= 0.0
        hand_r = 17
        pygame.draw.circle(surface, skin, (int(ax), int(ay)), hand_r)
        pygame.draw.circle(surface, (150, 110, 82), (int(ax), int(ay)), hand_r, 1)
        if released:
            # Splayed fingers as he lets the mags go.
            for k in range(-2, 3):
                fx = ax + k * 6
                pygame.draw.line(surface, skin, (int(fx), int(ay + hand_r - 2)),
                                 (int(fx), int(ay + hand_r + 8)), 3)

    # Larger magazine sprite.
    MAG_W, MAG_H = 26, 54

    def draw_mag(x, y, angle):
        s = pygame.Surface((MAG_W, MAG_H), pygame.SRCALPHA)
        pygame.draw.rect(s, (26, 28, 33), (0, 0, MAG_W, MAG_H), border_radius=4)
        # curved grip base (amber)
        pygame.draw.rect(s, (208, 162, 92), (3, MAG_H - 14, MAG_W - 6, 11), border_radius=3)
        # ribbed body lines
        for ry in range(8, MAG_H - 16, 9):
            pygame.draw.line(s, (120, 122, 132), (4, ry), (MAG_W - 4, ry), 1)
        # top lip
        pygame.draw.rect(s, (150, 150, 160), (3, 3, MAG_W - 6, 5), border_radius=2)
        s = pygame.transform.rotate(s, angle)
        surface.blit(s, (int(x) - s.get_width() // 2, int(y) - s.get_height() // 2))

    # Each mag arcs from Volkov's hand into its OWN hand, delayed so they
    # never overlap in flight or on landing. Both launches happen AFTER the
    # line is finished (t >= SHOT1_END), so the handoff reads clean.
    def mag_traj(tx, ty, delay, dur=880):
        p = min(1.0, max(0.0, (t - delay) / dur))
        if p <= 0.0:
            return None
        flight = min(1.0, p / 0.72)
        ease = 1.0 - (1.0 - flight) * (1.0 - flight)
        arc = math.sin(flight * math.pi) * 70
        x = toss_x + (tx - toss_x) * ease
        y = toss_y + (ty - toss_y) * ease - arc
        caught = p >= 0.9
        return x, y, caught

    mags = [
        (hand_lx, hand_ly - 6, 2760, -16),   # left hand, slight tilt
        (hand_rx, hand_ry - 6, 3080, 16),    # right hand, delayed, opposite tilt
    ]
    for tx, ty, delay, tilt in mags:
        res = mag_traj(tx, ty, delay)
        if res is None:
            continue
        x, y, caught = res
        # Faint motion ghost trailing behind the mag in flight.
        if not caught:
            gp = min(1.0, max(0.0, (t - delay - 90) / 880.0))
            if gp > 0:
                gf = min(1.0, gp / 0.72)
                ge = 1.0 - (1.0 - gf) * (1.0 - gf)
                gx = toss_x + (tx - toss_x) * ge
                gy = toss_y + (ty - toss_y) * ge - math.sin(gf * math.pi) * 70
                ghost = pygame.Surface((MAG_W, MAG_H), pygame.SRCALPHA)
                pygame.draw.rect(ghost, (60, 60, 70, 80), (0, 0, MAG_W, MAG_H), border_radius=4)
                ghost = pygame.transform.rotate(ghost, tilt)
                surface.blit(ghost, (int(gx) - ghost.get_width() // 2, int(gy) - ghost.get_height() // 2))
        draw_mag(x, y, tilt)
        if caught:
            # Clean catch: Biribel's fingers curl over the mag top + soft amber rim.
            top_y = y - MAG_H / 2
            for k in range(-1, 2):
                fx = x + k * 9
                pygame.draw.line(surface, skin, (int(fx), int(top_y + 4)),
                                 (int(fx), int(top_y - 6)), 3)
            rim = pygame.Surface((MAG_W + 8, MAG_H + 8), pygame.SRCALPHA)
            pygame.draw.rect(rim, (208, 162, 92, 90), (3, 3, MAG_W + 2, MAG_H + 2), border_radius=6)
            rim = pygame.transform.rotate(rim, tilt)
            surface.blit(rim, (int(x) - rim.get_width() // 2, int(y) - rim.get_height() // 2))


def _draw_vent_shaft(surface, t):
    """Ventilation shaft — dark corrugated metal tunnel, dust motes, forward crawl."""
    surface.fill((6, 6, 8))
    cx, cy = WIDTH // 2, HEIGHT // 2

    # Corrugated tunnel walls — perspective lines converging to center.
    for i in range(20):
        y_off = i * 28
        shrink = 0.3 + 0.7 * (i / 20)
        lw = int(WIDTH * shrink)
        left = cx - lw // 2
        right = cx + lw // 2
        top = cy - 120 + y_off
        col = (18 + i, 18 + i, 20 + i)
        # Top corrugation.
        pygame.draw.line(surface, col, (left, top), (right, top), 2)
        # Side ribs.
        if i % 3 == 0:
            rib_col = (28, 28, 30)
            pygame.draw.line(surface, rib_col, (left, top), (left, top + 26), 1)
            pygame.draw.line(surface, rib_col, (right, top), (right, top + 26), 1)

    # Dust motes drifting forward.
    rng = random.Random(int(t * 0.01))
    for _ in range(12):
        mx = rng.randint(100, WIDTH - 100)
        my = rng.randint(80, HEIGHT - 80)
        ms = 1 + rng.random() * 1.5
        pygame.draw.circle(surface, (60, 58, 52), (int(mx), int(my)), int(ms))

    # Faint light ahead — the exit glow at the tunnel end.
    glow_r = 60 + int(8 * math.sin(t * 0.03))
    glow = pygame.Surface((glow_r * 2, glow_r * 2), pygame.SRCALPHA)
    for r in range(glow_r, 0, -4):
        a = max(0, int(18 * (1 - r / glow_r)))
        pygame.draw.circle(glow, (80, 90, 70, a), (glow_r, glow_r), r)
    surface.blit(glow, (cx - glow_r, cy - glow_r - 60), special_flags=pygame.BLEND_ADD)

    # Forward motion blur streaks.
    for _ in range(6):
        sx = rng.randint(120, WIDTH - 120)
        sy = rng.randint(100, HEIGHT - 100)
        slen = rng.randint(20, 50)
        pygame.draw.line(surface, (30, 30, 34), (sx, sy), (sx, sy + slen), 1)


def _draw_vent_exit(surface, t):
    """Looking out from the vent grate into the Stabilization Center kitchen."""
    import math
    import random

    # 1. Background / Back Wall (institutional pale green/gray tiles)
    wall_col = (45, 52, 48)
    wall_dark = (30, 35, 32)
    surface.fill(wall_col)

    # Tile grid on the back wall
    tile_size = 40
    for tx in range(0, WIDTH, tile_size):
        pygame.draw.line(surface, wall_dark, (tx, 0), (tx, HEIGHT), 1)
    for ty in range(0, HEIGHT, tile_size):
        pygame.draw.line(surface, wall_dark, (0, ty), (WIDTH, ty), 1)

    # 2. Stainless steel shelving on the back wall
    shelf_y = int(HEIGHT * 0.35)
    shelf_col = (85, 90, 95)
    shelf_hi = (130, 135, 140)
    shelf_dark = (50, 55, 60)
    pygame.draw.rect(surface, shelf_col, (80, shelf_y, WIDTH - 160, 12))
    pygame.draw.line(surface, shelf_hi, (80, shelf_y), (WIDTH - 80, shelf_y), 2)
    pygame.draw.line(surface, shelf_dark, (80, shelf_y + 12), (WIDTH - 80, shelf_y + 12), 2)

    # Pots and institutional trays on the shelf
    rng = random.Random(99)
    for px in range(100, WIDTH - 100, 70):
        if rng.random() > 0.3:
            pw = rng.randint(30, 50)
            ph = rng.randint(20, 35)
            pygame.draw.rect(surface, (65, 70, 75), (px, shelf_y - ph, pw, ph), border_radius=2)
            pygame.draw.rect(surface, shelf_hi, (px, shelf_y - ph, pw, ph), 1, border_radius=2)
            pygame.draw.rect(surface, (40, 45, 50), (px + pw//2 - 10, shelf_y - ph - 4, 20, 4), border_radius=1)

    # 3. Hanging rack with pots (center)
    rack_y = int(HEIGHT * 0.15)
    pygame.draw.line(surface, (40, 45, 50), (250, rack_y), (WIDTH - 250, rack_y), 4)
    for hx in range(280, WIDTH - 280, 90):
        pygame.draw.line(surface, (60, 65, 70), (hx, rack_y), (hx, rack_y + 40), 2)
        pygame.draw.ellipse(surface, (55, 60, 65), (hx - 25, rack_y + 40, 50, 35))
        pygame.draw.ellipse(surface, shelf_hi, (hx - 25, rack_y + 40, 50, 35), 1)
        pygame.draw.line(surface, (40, 45, 50), (hx + 25, rack_y + 50), (hx + 45, rack_y + 45), 3)

    # 4. Industrial stove / prep table (lower half)
    table_y = int(HEIGHT * 0.65)
    table_w = 500
    table_x = WIDTH // 2 - table_w // 2
    pygame.draw.rect(surface, shelf_col, (table_x, table_y, table_w, 20), border_radius=2)
    pygame.draw.line(surface, shelf_hi, (table_x, table_y), (table_x + table_w, table_y), 2)
    pygame.draw.rect(surface, (70, 75, 80), (table_x, table_y + 20, table_w, 150))
    pygame.draw.line(surface, shelf_dark, (table_x, table_y + 170), (table_x + table_w, table_y + 170), 2)
    
    # Oven doors
    for ox in range(table_x + 20, table_x + table_w - 20, 120):
        pygame.draw.rect(surface, (55, 60, 65), (ox, table_y + 40, 100, 110), border_radius=4)
        pygame.draw.rect(surface, shelf_dark, (ox, table_y + 40, 100, 110), 2, border_radius=4)
        pygame.draw.rect(surface, shelf_hi, (ox + 10, table_y + 50, 80, 6), border_radius=2)
        pygame.draw.rect(surface, (15, 18, 20), (ox + 20, table_y + 70, 60, 40), border_radius=2)
        pygame.draw.rect(surface, (30, 35, 40), (ox + 20, table_y + 70, 60, 40), 1, border_radius=2)

    # 5. Overhead fluorescent light (flickering)
    light_cx = WIDTH // 2
    light_cy = int(HEIGHT * 0.05)
    flicker = 0.85 + 0.15 * math.sin(t * 0.2)
    light_col = (int(230 * flicker), int(240 * flicker), int(220 * flicker))
    pygame.draw.rect(surface, (60, 65, 70), (light_cx - 100, light_cy, 200, 16), border_radius=2)
    pygame.draw.rect(surface, light_col, (light_cx - 95, light_cy + 4, 190, 8), border_radius=2)
    
    # Light cone (additive blend)
    cone = pygame.Surface((400, 500), pygame.SRCALPHA)
    pygame.draw.polygon(cone, (*light_col, 25), [
        (200 - 95, 0), (200 + 95, 0),
        (350, 500), (50, 500)
    ])
    surface.blit(cone, (light_cx - 200, light_cy + 16), special_flags=pygame.BLEND_RGBA_ADD)

    # 6. The vent grate frame (foreground, framing the whole view)
    frame_col = (12, 14, 16)
    frame_hi = (35, 38, 42)
    frame_w = 50

    # Thick borders
    pygame.draw.rect(surface, frame_col, (0, 0, WIDTH, frame_w))
    pygame.draw.rect(surface, frame_col, (0, HEIGHT - frame_w, WIDTH, frame_w))
    pygame.draw.rect(surface, frame_col, (0, 0, frame_w, HEIGHT))
    pygame.draw.rect(surface, frame_col, (WIDTH - frame_w, 0, frame_w, HEIGHT))

    # Inner bevels
    pygame.draw.line(surface, frame_hi, (frame_w, frame_w), (WIDTH - frame_w, frame_w), 2)
    pygame.draw.line(surface, frame_hi, (frame_w, HEIGHT - frame_w), (WIDTH - frame_w, HEIGHT - frame_w), 2)
    pygame.draw.line(surface, frame_hi, (frame_w, frame_w), (frame_w, HEIGHT - frame_w), 2)
    pygame.draw.line(surface, frame_hi, (WIDTH - frame_w, frame_w), (WIDTH - frame_w, HEIGHT - frame_w), 2)

    # Grate slats (horizontal and vertical bars crossing the view)
    slat_col = (18, 20, 22)
    slat_hi = (40, 45, 50)

    # Horizontal slats
    for sy in range(frame_w, HEIGHT - frame_w, 70):
        pygame.draw.rect(surface, slat_col, (frame_w, sy, WIDTH - frame_w * 2, 10))
        pygame.draw.line(surface, slat_hi, (frame_w, sy), (WIDTH - frame_w, sy), 1)
        pygame.draw.line(surface, (5, 6, 8), (frame_w, sy + 10), (WIDTH - frame_w, sy + 10), 1)

    # Vertical slats
    for sx in range(frame_w, WIDTH - frame_w, 90):
        pygame.draw.rect(surface, slat_col, (sx, frame_w, 10, HEIGHT - frame_w * 2))
        pygame.draw.line(surface, slat_hi, (sx, frame_w), (sx, HEIGHT - frame_w), 1)
        pygame.draw.line(surface, (5, 6, 8), (sx + 10, frame_w), (sx + 10, HEIGHT - frame_w), 1)

    # Screws in the corners of the frame
    screw_col = (50, 55, 60)
    for cx, cy in [(25, 25), (WIDTH - 25, 25), (25, HEIGHT - 25), (WIDTH - 25, HEIGHT - 25)]:
        pygame.draw.circle(surface, screw_col, (cx, cy), 8)
        pygame.draw.circle(surface, (20, 22, 25), (cx, cy), 8, 1)
        pygame.draw.line(surface, (15, 16, 18), (cx - 4, cy), (cx + 4, cy), 2)
        pygame.draw.line(surface, (15, 16, 18), (cx, cy - 4), (cx, cy + 4), 2)

    # Dust motes / kitchen steam floating in the light cone
    rng2 = random.Random(int(t * 0.5))
    for _ in range(15):
        mx = rng2.randint(light_cx - 150, light_cx + 150)
        my = rng2.randint(light_cy + 50, HEIGHT - 100)
        mr = rng2.randint(1, 3)
        alpha = rng2.randint(40, 100)
        dust = pygame.Surface((mr*4, mr*4), pygame.SRCALPHA)
        pygame.draw.circle(dust, (220, 230, 210, alpha), (mr*2, mr*2), mr)
        surface.blit(dust, (mx, my), special_flags=pygame.BLEND_RGBA_ADD)


def draw_cutscene_scene(surface, shot, t):
    scene = shot["scene"]
    surface.fill(shot.get("lighting", (20, 24, 30)))
    if scene == "ocean_wide":
        draw_sky_gradient(surface, (50, 35, 30), (85, 55, 40))
        ocean_y = SCENE_TOP + 200
        pygame.draw.rect(
            surface, (25, 28, 35), (0, ocean_y, WIDTH, SCENE_BOT - ocean_y)
        )
        for wy in range(ocean_y + 10, SCENE_BOT, 18):
            for wx in range(0, WIDTH, 25):
                offset = int(math.sin((wx + t * 0.5) * 0.02) * 3)
                pygame.draw.line(
                    surface, (35, 38, 45), (wx, wy + offset), (wx + 12, wy + offset), 1
                )
        sun_x = WIDTH // 2 + 100
        sun_y = ocean_y - 30
        for r in range(40, 0, -3):
            a = max(0, 80 - r * 2)
            sun_surf = pygame.Surface((r * 2, r * 2), pygame.SRCALPHA)
            pygame.draw.circle(sun_surf, (255, 150, 80, a), (r, r), r)
            surface.blit(sun_surf, (sun_x - r, sun_y - r))
        pygame.draw.circle(surface, (255, 180, 120), (sun_x, sun_y), 22)
        for i in range(8):
            ry = sun_y + 20 + i * 15
            rw = 20 + i * 8
            refl = pygame.Surface((rw, 4), pygame.SRCALPHA)
            refl.fill((255, 150, 80, max(0, 80 - i * 8)))
            surface.blit(refl, (sun_x - rw // 2, ry))
        draw_oil_rig(surface, 150, ocean_y, t, scale=0.6, burning=True)
        draw_oil_rig(surface, 350, ocean_y, t, scale=0.5, burning=False)
        draw_oil_rig(surface, 750, ocean_y, t, scale=0.55, burning=False)
    elif scene == "city_skyline":
        draw_sky_gradient(surface, (28, 22, 32), (45, 30, 35))
        slum_y = GROUND_Y - 80
        pygame.draw.rect(surface, (20, 18, 20), (0, slum_y, WIDTH, SCENE_BOT - slum_y))
        rng = random.Random(7)
        for sx in range(0, WIDTH, 35):
            stack_h = rng.randint(2, 5)
            for sl in range(stack_h):
                cy = slum_y - sl * 22
                col_choices = [(58, 38, 34), (38, 42, 50), (54, 46, 38), (46, 46, 48)]
                col = rng.choice(col_choices)
                pygame.draw.rect(surface, col, (sx, cy - 22, 32, 22))
                pygame.draw.rect(
                    surface,
                    (max(0, col[0] - 15), max(0, col[1] - 15), max(0, col[2] - 15)),
                    (sx, cy - 22, 32, 22),
                    1,
                )
                if rng.random() > 0.6:
                    pygame.draw.rect(surface, (200, 160, 80), (sx + 12, cy - 14, 4, 6))
        for tx, th, tc in [
            (150, 280, (45, 50, 60)),
            (320, 350, (50, 55, 65)),
            (520, 320, (45, 50, 60)),
            (720, 380, (50, 55, 65)),
            (880, 290, (45, 50, 60)),
        ]:
            ty = slum_y - th
            pygame.draw.rect(surface, tc, (tx, ty, 60, th))
            pygame.draw.rect(
                surface, (tc[0] + 10, tc[1] + 10, tc[2] + 10), (tx, ty, 60, 6)
            )
            for wy in range(ty + 20, slum_y - 10, 25):
                for wx in range(tx + 8, tx + 52, 18):
                    if rng.random() > 0.5:
                        pygame.draw.rect(surface, (180, 200, 240), (wx, wy, 8, 10))
                        glow = pygame.Surface((14, 16), pygame.SRCALPHA)
                        glow.fill((180, 200, 240, 25))
                        surface.blit(glow, (wx - 3, wy - 3))
            pygame.draw.circle(surface, (200, 50, 30), (tx + 30, ty + 12), 4)
    elif scene == "ipa_poster":
        surface.fill((25, 22, 20))
        rng = random.Random(11)
        for by in range(SCENE_TOP, SCENE_BOT, 20):
            for bx in range(-(by // 20 % 2) * 30, WIDTH + 30, 60):
                shade = rng.randint(-8, 8)
                col = (60 + shade, 50 + shade, 42 + shade)
                pygame.draw.rect(surface, col, (bx, by, 58, 18))
                pygame.draw.line(
                    surface, (20, 18, 16), (bx, by + 18), (bx + 58, by + 18), 1
                )
                pygame.draw.line(
                    surface, (20, 18, 16), (bx + 58, by), (bx + 58, by + 18), 1
                )
        poster_w, poster_h = 380, 460
        poster_x = WIDTH // 2 - poster_w // 2
        poster_y = SCENE_TOP + 50
        draw_propaganda_poster(
            surface, poster_x, poster_y, poster_w, poster_h, defaced=False
        )
        big_text = font_speaker.render("STABILITY", True, (40, 30, 25))
        surface.blit(
            big_text,
            (
                poster_x + poster_w // 2 - big_text.get_width() // 2,
                poster_y + poster_h - 100,
            ),
        )
        sub = font_terminal.render("PROSPERITY  ●  ACARISTAN", True, (60, 45, 40))
        surface.blit(
            sub,
            (poster_x + poster_w // 2 - sub.get_width() // 2, poster_y + poster_h - 60),
        )
        ipa = font_terminal_small.render("— IPA —", True, (160, 30, 30))
        surface.blit(
            ipa,
            (poster_x + poster_w // 2 - ipa.get_width() // 2, poster_y + poster_h - 30),
        )
    elif scene == "mag_graffiti":
        surface.fill((35, 32, 30))
        for cy in range(SCENE_TOP, SCENE_BOT, 8):
            shade = -6 if (cy // 8) % 2 == 0 else 6
            pygame.draw.line(
                surface, (60 + shade, 50 + shade, 45 + shade), (0, cy), (WIDTH, cy), 2
            )
        rng = random.Random(23)
        for _ in range(20):
            rx = rng.randint(0, WIDTH)
            ry = rng.randint(SCENE_TOP, SCENE_BOT)
            rw = rng.randint(20, 60)
            rh = rng.randint(15, 40)
            rust = pygame.Surface((rw, rh), pygame.SRCALPHA)
            rust.fill((90, 50, 30, 50))
            surface.blit(rust, (rx, ry))
        center_x = WIDTH // 2
        center_y = (SCENE_TOP + SCENE_BOT) // 2
        for _ in range(80):
            dx = rng.randint(-90, 90)
            dy = rng.randint(-90, 90)
            if math.hypot(dx, dy) < 100:
                pygame.draw.circle(
                    surface,
                    (15, 15, 15),
                    (center_x + dx, center_y + dy),
                    rng.randint(1, 2),
                )
        draw_mag_graffiti(surface, center_x, center_y, scale=6.0)
        tag = font_speaker.render("MARU SEES YOU", True, (15, 15, 15))
        surface.blit(tag, (center_x - tag.get_width() // 2, center_y + 90))
        for _ in range(10):
            dx = rng.randint(-100, 100)
            pygame.draw.line(
                surface,
                (15, 15, 15),
                (center_x + dx, center_y + 95),
                (center_x + dx, center_y + 95 + rng.randint(10, 40)),
                2,
            )
    elif scene == "krap_convoy":
        draw_sky_gradient(surface, (60, 50, 45), (90, 70, 55))
        pygame.draw.rect(
            surface, (60, 50, 35), (0, GROUND_Y, WIDTH, SCENE_BOT - GROUND_Y)
        )
        for dx in range(50, WIDTH, 130):
            pygame.draw.line(
                surface, (30, 28, 32), (dx, GROUND_Y), (dx, GROUND_Y - 40), 2
            )
            pygame.draw.line(
                surface,
                (30, 28, 32),
                (dx - 6, GROUND_Y - 35),
                (dx + 6, GROUND_Y - 35),
                2,
            )
        road_y = GROUND_Y - 10
        pygame.draw.rect(surface, (30, 28, 30), (0, road_y, WIDTH, 70))
        for lx in range(0, WIDTH, 60):
            pygame.draw.rect(surface, (200, 190, 100), (lx + 10, road_y + 30, 30, 4))
        for i, (cx_t, cy_t) in enumerate(
            [(150, road_y + 5), (380, road_y + 5), (620, road_y + 5)]
        ):
            pygame.draw.rect(surface, (45, 55, 70), (cx_t, cy_t, 60, 35))
            pygame.draw.rect(surface, (35, 45, 60), (cx_t, cy_t, 60, 35), 2)
            pygame.draw.rect(surface, (50, 60, 75), (cx_t + 60, cy_t - 10, 100, 45))
            pygame.draw.rect(surface, (30, 40, 55), (cx_t + 60, cy_t - 10, 100, 45), 2)
            pygame.draw.rect(surface, C_KRAP_BLUE, (cx_t + 70, cy_t - 5, 30, 8))
            pygame.draw.line(
                surface,
                (240, 240, 240),
                (cx_t + 70, cy_t - 1),
                (cx_t + 100, cy_t - 1),
                2,
            )
            pygame.draw.circle(surface, (15, 15, 18), (cx_t + 15, cy_t + 35), 10)
            pygame.draw.circle(surface, (15, 15, 18), (cx_t + 45, cy_t + 35), 10)
            pygame.draw.circle(surface, (15, 15, 18), (cx_t + 90, cy_t + 35), 10)
            pygame.draw.circle(surface, (15, 15, 18), (cx_t + 140, cy_t + 35), 10)
        for cx_p in (50, 90, 850, 920):
            pygame.draw.rect(surface, (60, 55, 45), (cx_p - 4, GROUND_Y - 30, 8, 30))
            pygame.draw.circle(surface, (170, 140, 115), (cx_p, GROUND_Y - 36), 5)
    elif scene == "krap_patch":
        surface.fill((25, 25, 28))
        for _ in range(200):
            x = random.randint(0, WIDTH)
            y = random.randint(SCENE_TOP, SCENE_BOT)
            v = random.randint(-5, 5)
            base = C_KRAP_UNIFORM
            c = (base[0] + v, base[1] + v, base[2] + v)
            pygame.draw.rect(surface, c, (x, y, 3, 3))
        patch_x, patch_y = 100, SCENE_TOP + 100
        patch_w, patch_h = 280, 280
        pygame.draw.rect(surface, C_KRAP_BLUE, (patch_x, patch_y, patch_w, patch_h))
        pygame.draw.rect(
            surface, (240, 240, 240), (patch_x, patch_y, patch_w, patch_h), 6
        )
        krap_text = font_title.render("KRAP", True, (240, 240, 240))
        surface.blit(
            krap_text,
            (patch_x + patch_w // 2 - krap_text.get_width() // 2, patch_y + 60),
        )
        sub1 = font_terminal_small.render("KOALIȚIA REGIONALĂ", True, (240, 240, 240))
        surface.blit(
            sub1, (patch_x + patch_w // 2 - sub1.get_width() // 2, patch_y + 160)
        )
        sub2 = font_terminal_small.render("DE APĂRARE ȘI PACE", True, (240, 240, 240))
        surface.blit(
            sub2, (patch_x + patch_w // 2 - sub2.get_width() // 2, patch_y + 180)
        )
        pygame.draw.arc(
            surface,
            (240, 240, 240),
            (patch_x + 30, patch_y + 210, patch_w - 60, 50),
            0,
            math.pi,
            3,
        )
        crate_x = WIDTH - 320
        crate_y = SCENE_TOP + 150
        crate_w = 240
        crate_h = 180
        pygame.draw.rect(surface, (90, 75, 50), (crate_x, crate_y, crate_w, crate_h))
        pygame.draw.rect(surface, (60, 50, 35), (crate_x, crate_y, crate_w, crate_h), 4)
        for py in range(crate_y, crate_y + crate_h, 30):
            pygame.draw.line(
                surface, (60, 50, 35), (crate_x, py), (crate_x + crate_w, py), 2
            )
        fl_text = font_speaker.render("FuegoTech", True, (200, 50, 30))
        surface.blit(
            fl_text, (crate_x + crate_w // 2 - fl_text.get_width() // 2, crate_y + 40)
        )
        sn = font_terminal_small.render("S/N: FT-4471-K", True, (40, 30, 25))
        surface.blit(sn, (crate_x + 30, crate_y + crate_h - 30))
        stamp = font_terminal_small.render("PROPERTY OF: IPA", True, (160, 30, 30))
        surface.blit(stamp, (crate_x + 30, crate_y + crate_h - 50))
    elif scene == "route12_black":
        draw_route12_black(surface, t)
    elif scene == "route12_files":
        draw_route12_files(surface, t)
    elif scene == "route12_mag_alert":
        draw_route12_mag_alert(surface, t)
    elif scene == "route12_checkpoint":
        draw_route12_checkpoint(surface, t)
    elif scene == "route12_tanker":
        draw_route12_tanker(surface, t)
    elif scene == "route12_broadcast":
        draw_route12_broadcast(surface, t)
    elif scene == "ipa_radio_chatter":
        draw_ipa_radio_chatter(surface, t)
    elif scene == "krap_door_kickin":
        draw_krap_door_kickin(surface, t)
    elif scene == "biribel_blackout":
        draw_biribel_blackout(surface, t)
    elif scene == "route12_aftermath":
        draw_route12_aftermath(surface, t)
    elif scene == "biribel_arrival":
        draw_sky_gradient(surface, (15, 18, 28), (28, 22, 28))
        skyline_y = GROUND_Y - 30
        rng = random.Random(13)
        for tx_b in range(0, WIDTH, 50):
            th = rng.randint(40, 140)
            pygame.draw.rect(surface, (15, 15, 22), (tx_b, skyline_y - th, 45, th))
            for wy_b in range(skyline_y - th + 10, skyline_y - 5, 18):
                if rng.random() > 0.5:
                    pygame.draw.rect(surface, (200, 160, 80), (tx_b + 8, wy_b, 4, 6))
        pygame.draw.rect(
            surface, (10, 12, 16), (0, GROUND_Y, WIDTH, SCENE_BOT - GROUND_Y)
        )
        for lx in (200, 450, 700):
            refl = pygame.Surface((30, 60), pygame.SRCALPHA)
            refl.fill((200, 160, 100, 25))
            surface.blit(refl, (lx, GROUND_Y))
        draw_biribel(
            surface,
            WIDTH // 2 + 80,
            GROUND_Y,
            scale=0.95,
            facing_right=False,
            in_silhouette=True,
        )
        shadow_pts = [
            (WIDTH // 2 + 60, GROUND_Y),
            (WIDTH // 2 + 100, GROUND_Y),
            (WIDTH // 2 - 60, GROUND_Y + 30),
            (WIDTH // 2 - 100, GROUND_Y + 30),
        ]
        shadow_surf = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        pygame.draw.polygon(shadow_surf, (0, 0, 0, 80), shadow_pts)
        surface.blit(shadow_surf, (0, 0))
    elif scene == "title_card":
        surface.fill((5, 5, 8))
    elif scene == "van_exterior":
        draw_van_exterior(surface, t)
    elif scene == "van_interior":
        draw_van_interior(surface, t)
    elif scene == "van_volkov_photo":
        draw_van_interior(surface, t)
        dim = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        dim.fill((0, 0, 0, 70))
        surface.blit(dim, (0, 0))
        draw_volkov_dossier_overlay(surface, t)
    elif scene == "van_handoff_weapon":
        draw_van_handoff(surface, t, item="weapon")
    elif scene == "van_handoff_molotovs":
        draw_van_handoff(surface, t, item="molotovs")
    elif scene == "factory_exterior":
        draw_factory(surface, t)
    elif scene in ("seby_pickup_body", "seby_pickup_reach", "seby_pickup_raise"):
        from mission2 import draw_route12_seby_pickup
        draw_route12_seby_pickup(surface, shot, t)
    # ── Mission 3 — The Vostral (Stabilization Center) ──
    elif scene == "cell_ceiling":
        _draw_cell_ceiling(surface, t)
    elif scene == "cell_restraints":
        _draw_cell_restraints(surface, t)
    elif scene == "interrogation_room":
        _draw_interrogation_room(surface, t)
    elif scene == "monitor_broadcast":
        _draw_monitor_broadcast(surface, t)
    elif scene == "k9_wall_stand":
        _draw_k9_wall_stand(surface, t)
    elif scene == "k9_firstperson_grab":
        _draw_k9_firstperson_grab(surface, t)
    elif scene == "k9_ready_check":
        _draw_k9_ready_check(surface, t)
    elif scene == "m3_service_door_transition":
        _draw_m3_service_door_transition(surface, t)
    elif scene == "m3_volkov_radio_call":
        _draw_m3_volkov_radio_call(surface, t)
    elif scene == "m3_radio_recovered":
        _draw_m3_radio_recovered(surface, t)
    elif scene == "m3_comms_wing_reveal":
        _draw_m3_comms_wing_reveal(surface, t)
    elif scene == "m3_volkov_gives_mags":
        _draw_m3_volkov_gives_mags(surface, t)
    elif scene == "volkov_in_cell":
        _draw_volkov_in_cell(surface, t)
    elif scene == "cb_strain":
        _draw_cb_strain(surface, t, clock_is_ms=True)
    elif scene == "cb_crack":
        _draw_cb_crack(surface, t, clock_is_ms=True)
    elif scene == "cb_grab":
        _draw_cb_grab(surface, t, clock_is_ms=True)
    elif scene == "cb_ready":
        _draw_cb_ready(surface, t, clock_is_ms=True)
    elif scene == "vent_shaft":
        _draw_vent_shaft(surface, t)
    elif scene == "vent_exit":
        _draw_vent_exit(surface, t)
def draw_typewriter_title(surface, lines, char_idx_total):
    """Title card with proper sizing & spacing."""
    title_font = pygame.font.SysFont("Impact", 56)
    line_h = 72
    total_h = len(lines) * line_h
    start_y = HEIGHT // 2 - total_h // 2
    cum = 0
    for i, line in enumerate(lines):
        cur_count = max(0, min(len(line), char_idx_total - cum))
        partial = line[:cur_count]
        if partial:
            surf = title_font.render(partial, True, (210, 210, 210))
            x = WIDTH // 2 - surf.get_width() // 2
            y = start_y + i * line_h
            shadow = title_font.render(partial, True, (0, 0, 0))
            surface.blit(shadow, (x + 3, y + 3))
            surface.blit(surf, (x, y))
            if cur_count < len(line) and (pygame.time.get_ticks() // 250) % 2 == 0:
                cursor_x = x + surf.get_width() + 6
                pygame.draw.rect(
                    surface, (210, 210, 210), (cursor_x, y + 12, 10, line_h - 24)
                )
        cum += len(line)
# ─────────────────────────────────────────────
# DIALOGUE BOX
# ─────────────────────────────────────────────
SPEAKER_COLORS = {
    "NARRATOR": C_NARRATOR,
    "COMMAND": C_COMMAND,
    "VASILE": C_VASILE,
    "CAPTAIN VASILE": C_VASILE,
    "BIRIBEL": C_BIRIBEL,
    "VOLKOV": C_VOLKOV,
    "OLD FISHERMAN": C_FISHERMAN,
    "FISHERMAN": C_FISHERMAN,
    "COMMANDER": C_ORANGE,
    "RADIO VOICE": C_COMMAND,
    "RADIO": C_COMMAND,
}
_dialogue_box_slide = 0.0
def reset_dialogue_slide():
    global _dialogue_box_slide
    _dialogue_box_slide = 0.0
def draw_dialogue_box(surface, speaker, text, char_idx, total_len, can_continue=True):
    global _dialogue_box_slide
    visible_text = text[:char_idx]
    paragraphs = visible_text.split("\n")
    box_w = WIDTH - 120
    inner_w = box_w - 52
    final_lines = []
    for para in paragraphs:
        if not para.strip():
            final_lines.append("")
            continue
        words = para.split(" ")
        line = ""
        for word in words:
            test = line + word + " "
            if font_dialogue.size(test)[0] < inner_w:
                line = test
            else:
                if line:
                    final_lines.append(line.rstrip())
                while word and font_dialogue.size(word)[0] > inner_w:
                    word = word[:-1]
                line = word + " "
        if line:
            final_lines.append(line.rstrip())
    full_paragraphs = text.split("\n")
    full_lines = []
    for para in full_paragraphs:
        if not para.strip():
            full_lines.append("")
            continue
        words = para.split(" ")
        line = ""
        for word in words:
            test = line + word + " "
            if font_dialogue.size(test)[0] < inner_w:
                line = test
            else:
                if line:
                    full_lines.append(line.rstrip())
                line = word + " "
        if line:
            full_lines.append(line.rstrip())
    num_lines = max(1, len(full_lines))
    line_h = 30
    header_h = 36
    bottom_pad = 24
    box_h = header_h + num_lines * line_h + bottom_pad
    box_y = HEIGHT - LETTER_H - box_h - 14
    box_x = 60
    box_rect = pygame.Rect(box_x, box_y, box_w, box_h)
    # ── Slide up animation ──
    if char_idx < 8:
        _dialogue_box_slide = min(12.0, _dialogue_box_slide + 1.0)
    else:
        _dialogue_box_slide = max(0.0, _dialogue_box_slide - 1.0)
    slide_offset = int(_dialogue_box_slide)
    panel = pygame.Surface((box_rect.width, box_rect.height), pygame.SRCALPHA)
    pygame.draw.rect(panel, (0, 0, 0, 205), panel.get_rect())
    accent = SPEAKER_COLORS.get(speaker.upper(), C_ORANGE)
    pygame.draw.rect(panel, (*accent, 255), (0, 0, 4, box_rect.height))
    pygame.draw.rect(panel, (4, 6, 9, 230), (4, 0, box_rect.width - 4, header_h))
    surface.blit(panel, (box_rect.x, box_rect.y + slide_offset))
    if speaker:
        spk_alpha = min(255, max(150, char_idx * 20))
        spk_surf = font_speaker.render(speaker.upper(), True, accent)
        spk_surf.set_alpha(spk_alpha)
        surface.blit(spk_surf, (box_rect.x + 24, box_rect.y + 5 + slide_offset))
    for i, line in enumerate(final_lines[:num_lines]):
        if line:
            line_alpha = min(255, max(0, char_idx * 8 - i * 40))
            surf = font_dialogue.render(line, True, C_WHITE)
            surf.set_alpha(line_alpha)
            surface.blit(
                surf, (box_rect.x + 24, box_rect.y + header_h + 8 + i * line_h + slide_offset)
            )
    if char_idx >= total_len:
        continue_alpha = int(140 + math.sin(pygame.time.get_ticks() * 0.004) * 60)
        prompt_text = "▼ SPACE TO CONTINUE" if can_continue else "◆ ANALYZING FILE..."
        cont = font_terminal_small.render(
            prompt_text,
            True,
            (accent[0] // 2, accent[1] // 2, accent[2] // 2),
        )
        cont.set_alpha(continue_alpha)
        surface.blit(
            cont, (box_rect.right - cont.get_width() - 22, box_rect.bottom - 20 + slide_offset)
        )
    pygame.draw.line(
        surface,
        accent,
        (box_rect.x + 4, box_rect.y + header_h + slide_offset),
        (box_rect.right, box_rect.y + header_h + slide_offset),
        1,
    )
def draw_volkov_dossier_overlay(surface, t):
    """Briefing tablet/dossier overlay. Clean, readable, not glossy."""
    tab_w = 460
    tab_h = 285
    tab_x = WIDTH // 2 - tab_w // 2
    tab_y = SCENE_TOP + 88
    # Drop shadow
    shadow = pygame.Surface((tab_w + 24, tab_h + 24), pygame.SRCALPHA)
    shadow.fill((0, 0, 0, 120))
    surface.blit(shadow, (tab_x + 12, tab_y + 12))
    # Tablet body
    pygame.draw.rect(surface, (10, 12, 15), (tab_x - 10, tab_y - 10, tab_w + 20, tab_h + 20), border_radius=4)
    pygame.draw.rect(surface, (45, 50, 58), (tab_x - 10, tab_y - 10, tab_w + 20, tab_h + 20), 2, border_radius=4)
    pygame.draw.rect(surface, (18, 22, 25), (tab_x, tab_y, tab_w, tab_h))
    # Header
    pygame.draw.rect(surface, (8, 12, 18), (tab_x, tab_y, tab_w, 34))
    pygame.draw.rect(surface, C_KRAP_BLUE, (tab_x, tab_y, 5, 34))
    hdr = font_terminal.render("KRAP INTEL DOSSIER // ACTIVE TARGET", True, (140, 185, 220))
    surface.blit(hdr, (tab_x + 16, tab_y + 7))
    # Photo frame
    photo_x = tab_x + 24
    photo_y = tab_y + 54
    photo_w = 150
    photo_h = 195
    pygame.draw.rect(surface, (28, 25, 22), (photo_x, photo_y, photo_w, photo_h))
    pygame.draw.rect(surface, (75, 70, 62), (photo_x, photo_y, photo_w, photo_h), 2)
    # Volkov portrait, still stylized
    face_cx = photo_x + photo_w // 2
    face_cy = photo_y + 66
    pygame.draw.circle(surface, (42, 36, 32), (face_cx, face_cy), 33)
    pygame.draw.arc(surface, (8, 6, 6), (face_cx - 34, face_cy - 34, 68, 68), 0, math.pi, 12)
    pygame.draw.circle(surface, (120, 38, 34), (face_cx - 10, face_cy - 4), 3)
    pygame.draw.circle(surface, (120, 38, 34), (face_cx + 10, face_cy - 4), 3)
    pygame.draw.arc(surface, (18, 16, 14), (face_cx - 24, face_cy + 2, 48, 26), math.pi * 1.15, math.pi * 1.85, 2)
    pygame.draw.polygon(
        surface,
        (14, 14, 20),
        [
            (photo_x + 25, photo_y + photo_h - 62),
            (photo_x + photo_w - 25, photo_y + photo_h - 62),
            (photo_x + photo_w - 8, photo_y + photo_h),
            (photo_x + 8, photo_y + photo_h),
        ],
    )
    # Photo noise
    noise = pygame.Surface((photo_w, photo_h), pygame.SRCALPHA)
    rng = random.Random(12 + int(t // 8))
    for _ in range(140):
        nx = rng.randint(0, photo_w - 1)
        ny = rng.randint(0, photo_h - 1)
        v = rng.randint(20, 70)
        noise.set_at((nx, ny), (v, v, v, 45))
    surface.blit(noise, (photo_x, photo_y))
    # Info column
    info_x = tab_x + 200
    info_y = tab_y + 58
    rows = [
        ("NAME", "SEBASTIAN VOLKOV", C_WHITE),
        ("AFFILIATION", "IPA LOGISTICS", (210, 120, 100)),
        ("STATUS", "ACTIVE", (80, 220, 110)),
        ("PRIORITY", "HIGH", (230, 80, 65)),
        ("LAST SEEN", "SLUM WAREHOUSE", (210, 190, 130)),
        ("ROE", "CAPTURE ALIVE", C_KRAP_BLUE),
    ]
    for i, (k, v, col) in enumerate(rows):
        y = info_y + i * 29
        ks = font_terminal_small.render(k, True, (95, 110, 125))
        vs = font_terminal.render(v, True, col)
        surface.blit(ks, (info_x, y))
        surface.blit(vs, (info_x, y + 11))
    # Bottom warning
    pygame.draw.line(surface, (45, 50, 58), (tab_x + 20, tab_y + tab_h - 38), (tab_x + tab_w - 20, tab_y + tab_h - 38), 1)
    warn = font_terminal_small.render("WARNING: TARGET CONNECTED TO FUEGOTECH SERIAL REGISTRY", True, C_ORANGE)
    surface.blit(warn, (tab_x + 24, tab_y + tab_h - 27))
    # Tiny scanline flicker
    if (pygame.time.get_ticks() // 120) % 2 == 0:
        gy = tab_y + 40 + (pygame.time.get_ticks() // 7) % (tab_h - 50)
        pygame.draw.line(surface, (180, 220, 255, 45), (tab_x, gy), (tab_x + tab_w, gy), 1)
# ─────────────────────────────────────────────
# CUTSCENE SHOT LISTS
# ─────────────────────────────────────────────
cutscene1_shots = [
    {
        "scene": "ocean_wide",
        "speaker": "NARRATOR",
        "text": "The Kilemeno Ocean. Once a fishing route.\nNow a graveyard of derricks and broken treaties.",
        "lighting": (30, 25, 30),
    },
    {
        "scene": "city_skyline",
        "speaker": "NARRATOR",
        "text": "Acaristan. A nation in name only.\nThe ground beneath it is worth more than the people standing on it.",
        "lighting": (28, 22, 30),
    },
    {
        "scene": "ipa_poster",
        "speaker": "NARRATOR",
        "text": "The IPA promises rebuilding.\nTheir oil flows. Their guns sell.\nTheir hands are clean — for the cameras.",
        "lighting": (25, 22, 20),
    },
    {
        "scene": "mag_graffiti",
        "speaker": "NARRATOR",
        "text": "MAG promises freedom.\nThey bomb checkpoints. They bury their dead in unmarked steppes.\nThe state calls them terrorists. The poor call them family.",
        "lighting": (35, 32, 30),
    },
    {
        "scene": "krap_convoy",
        "speaker": "NARRATOR",
        "text": "And then there is KRAP.\nKoaliția Regională de Apărare și Pace.\nPeacekeepers, they call themselves.",
        "lighting": (60, 50, 45),
    },
    {
        "scene": "krap_patch",
        "speaker": "NARRATOR",
        "text": "They keep the highways open.\nThey keep the oil moving.\nThey keep the questions unasked.",
        "lighting": (25, 25, 28),
    },
    {
        "scene": "biribel_arrival",
        "speaker": "NARRATOR",
        "text": "Today, one of their operators arrives.\nHe has been told this is a stabilization assignment.\nHe has not been told the truth.",
        "lighting": (15, 18, 28),
    },
    {
        "scene": "title_card",
        "speaker": "",
        "text": "ACARISTAN CITY\nOPERATION: BLACK NOTEBOOK\nDAY 1",
        "lighting": (5, 5, 8),
    },
]
cutscene_shots = cutscene1_shots
cutscene2_shots = [
    {
        "scene": "van_exterior",
        "speaker": "NARRATOR",
        "text": "The KRAP van cut east through the rain.\nInside, Captain Vasile finally opened the file.",
        "lighting": (10, 12, 18),
    },
    {
        "scene": "van_interior",
        "speaker": "CAPTAIN VASILE",
        "text": "Welcome to Acaristan, Biribel.\nHope you enjoyed the scenery.",
        "lighting": (15, 12, 14),
    },
    {
        "scene": "van_volkov_photo",
        "speaker": "CAPTAIN VASILE",
        "text": "Sebastian Volkov. IPA affiliate.\nWe've been tracking him for six months.\nTonight he's making a handoff in the slum district.",
        "lighting": (15, 12, 14),
    },
    {
        "scene": "van_volkov_photo",
        "speaker": "CAPTAIN VASILE",
        "text": "Your job: get in, capture him alive, get out.\nHe knows names. We want those names.",
        "lighting": (15, 12, 14),
    },
    {
        "scene": "van_interior",
        "speaker": "BIRIBEL",
        "text": "And if he runs?",
        "lighting": (15, 12, 14),
    },
    {
        "scene": "van_interior",
        "speaker": "CAPTAIN VASILE",
        "text": "He won't get far.\nBut if he does, bring back anything he leaves behind.\nPaper, drives, a notebook — anything.",
        "lighting": (15, 12, 14),
    },
    {
        "scene": "van_handoff_weapon",
        "speaker": "CAPTAIN VASILE",
        "text": "Here. Standard sidearm.\nKeep it holstered until you have no choice.",
        "lighting": (15, 12, 14),
    },
    {
        "scene": "van_handoff_molotovs",
        "speaker": "CAPTAIN VASILE",
        "text": "And take these: two molotovs.\nUgly tools, but they clear alleys fast.",
        "lighting": (15, 12, 14),
    },
    {
        "scene": "van_interior",
        "speaker": "CAPTAIN VASILE",
        "text": "Comms on channel 4. Don't die.\nI hate paperwork.",
        "lighting": (15, 12, 14),
    },
]



def _draw_vertical_gradient(surface, x, y, w, h, top_color, bottom_color):
    """Draw a vertical gradient rectangle."""
    for i in range(h):
        t = i / max(1, h - 1)
        r = int(top_color[0] * (1 - t) + bottom_color[0] * t)
        g = int(top_color[1] * (1 - t) + bottom_color[1] * t)
        b = int(top_color[2] * (1 - t) + bottom_color[2] * t)
        pygame.draw.line(surface, (r, g, b), (x, y + i), (x + w, y + i))




def _draw_light_cone(surface, lx, ly, radius, color, alpha=80):
    """Draw a radial light cone — a soft glow centered at (lx, ly).

    Used for the fluorescent overhead, the bare bulb in the cell, etc.
    Clamps the color channels + alpha to valid ranges to avoid
    "invalid color argument" crashes from flicker math producing
    out-of-range values.
    """
    # Clamp color channels to 0-255.
    r = max(0, min(255, int(color[0])))
    g = max(0, min(255, int(color[1])))
    b = max(0, min(255, int(color[2])))
    a = max(0, min(255, int(alpha)))
    if a <= 0 or radius <= 0:
        return
    glow = pygame.Surface((radius * 2, radius * 2), pygame.SRCALPHA)
    steps = 20
    for i in range(steps):
        t = i / steps
        rad = int(radius * (1 - t * 0.6))
        aa = int(a * (1 - t) ** 2)
        if aa > 0 and rad > 0:
            pygame.draw.circle(glow, (r, g, b, aa), (radius, radius), rad)
    surface.blit(glow, (lx - radius, ly - radius))
