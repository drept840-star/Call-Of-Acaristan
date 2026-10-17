"""Split from cutscenes.py - see cutscenes.py (shim) for the map."""
# cutscenes package
# ------------------------------------------------------------

"""Cutscene visuals and dialogue: character drawings, scene backgrounds, shot lists."""
import math
import random
from engine.core import LEGACY_RNG as _rng_legacy  # RPE6 R6: named 'legacy' rng stream
import pygame
from core.config import (C_KRAP_BLUE, C_KRAP_UNIFORM, C_ORANGE, C_WHITE, HEIGHT, LETTER_H, SCENE_BOT, SCENE_TOP, WIDTH, draw_sky_gradient, font_dialogue, font_speaker, font_terminal, font_terminal_small, font_title)

from cutscenes.cast import draw_biribel, draw_civilian
from cutscenes.route12 import draw_biribel_blackout, draw_factory, draw_ipa_radio_chatter, draw_krap_door_kickin, draw_mag_graffiti, draw_oil_rig, draw_propaganda_poster, draw_route12_aftermath, draw_route12_black, draw_route12_broadcast, draw_route12_checkpoint, draw_route12_files, draw_route12_mag_alert, draw_route12_tanker, draw_van_exterior, draw_van_handoff, draw_van_interior, GROUND_Y, _draw_vertical_gradient, _draw_light_cone
from core.cutscene_registry import scene_renderer as _scene_renderer
from cutscenes.m5mid3d import draw_m5x
from engine.core import now_ms as _now_ms  # RPE6 B-001 timebase
from engine.ui import dialogue_box as _dialogue_box  # RPE6 Phase 4 (A-009): shared cutscene box
from ui.hud import THEME as _hud_theme  # RPE6 Phase 4 (A-009): the one game theme


def _draw_cutscene_scene_raw(surface, shot, t):
    scene = shot["scene"]
    t += shot.get("scene_time_offset_ms", 0)
    surface.fill(shot.get("lighting", (20, 24, 30)))
    renderer = _scene_renderer(scene)   # mission-registered takes (core.cutscene_registry)
    if renderer is not None:
        renderer(surface, t)
    elif scene == "ocean_wide":
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
        big_text = font_speaker.render(_T("engine.stability"), True, (40, 30, 25))
        surface.blit(
            big_text,
            (
                poster_x + poster_w // 2 - big_text.get_width() // 2,
                poster_y + poster_h - 100,
            ),
        )
        sub = font_terminal.render(_T("engine.prosperity_acaristan"), True, (60, 45, 40))
        surface.blit(
            sub,
            (poster_x + poster_w // 2 - sub.get_width() // 2, poster_y + poster_h - 60),
        )
        ipa = font_terminal_small.render(_T("engine.ipa"), True, (160, 30, 30))
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
        tag = font_speaker.render(_T("engine.maru_sees_you"), True, (15, 15, 15))
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
        # Roadside civilians watching the convoy: cast-sheet extras.
        for cx_p, face_r in ((50, True), (90, True), (850, False), (920, False)):
            draw_civilian(surface, cx_p, GROUND_Y, scale=0.17, facing_right=face_r)
    elif scene == "krap_patch":
        surface.fill((25, 25, 28))
        for _ in range(200):
            x = _rng_legacy.randint(0, WIDTH)
            y = _rng_legacy.randint(SCENE_TOP, SCENE_BOT)
            v = _rng_legacy.randint(-5, 5)
            base = C_KRAP_UNIFORM
            c = (base[0] + v, base[1] + v, base[2] + v)
            pygame.draw.rect(surface, c, (x, y, 3, 3))
        patch_x, patch_y = 100, SCENE_TOP + 100
        patch_w, patch_h = 280, 280
        pygame.draw.rect(surface, C_KRAP_BLUE, (patch_x, patch_y, patch_w, patch_h))
        pygame.draw.rect(
            surface, (240, 240, 240), (patch_x, patch_y, patch_w, patch_h), 6
        )
        krap_text = font_title.render(_T("engine.krap"), True, (240, 240, 240))
        surface.blit(
            krap_text,
            (patch_x + patch_w // 2 - krap_text.get_width() // 2, patch_y + 60),
        )
        sub1 = font_terminal_small.render(_T("engine.koali_ia_regional"), True, (240, 240, 240))
        surface.blit(
            sub1, (patch_x + patch_w // 2 - sub1.get_width() // 2, patch_y + 160)
        )
        sub2 = font_terminal_small.render(_T("engine.de_ap_rare_i_pace"), True, (240, 240, 240))
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
        fl_text = font_speaker.render(_T("engine.fuegotech"), True, (200, 50, 30))
        surface.blit(
            fl_text, (crate_x + crate_w // 2 - fl_text.get_width() // 2, crate_y + 40)
        )
        sn = font_terminal_small.render(_T("engine.s_n_ft_4471_k"), True, (40, 30, 25))
        surface.blit(sn, (crate_x + 30, crate_y + crate_h - 30))
        stamp = font_terminal_small.render(_T("engine.property_of_ipa"), True, (160, 30, 30))
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
        from missions.m2 import draw_route12_seby_pickup
        draw_route12_seby_pickup(surface, shot, t)
    # ── Mission 3 - The Vostral (Stabilization Center) ──
    elif scene.startswith("m5x_"):
        draw_m5x(scene, surface, t)   # round 2: M5 mid-mission takes (3D, 2D fallback)

def draw_cutscene_scene(surface, shot, t):
    """Dispatch one shot, then apply its cinematic post stack (P11 step 5)."""
    from core.cutscene_registry import set_current_shot
    set_current_shot(shot)
    _draw_cutscene_scene_raw(surface, shot, t)
    post = shot.get("post") if isinstance(shot, dict) else None
    if post:
        from cutscenes.post3d import apply_post  # lazy: numpy stack
        dur = int(shot.get("duration_ms") or shot.get("min_ms") or 0)
        apply_post(surface, post, t, str(shot.get("scene", "")), dur)

def draw_typewriter_title(surface, lines, char_idx_total):
    """Title card with proper sizing & spacing.

    Long single-line captions (e.g. the M3 ending) are word-wrapped to fit
    the screen: wrapping only re-splits on spaces, so the typewriter
    reveal count stays aligned with the original text.
    """
    title_font = pygame.font.SysFont("Impact", 56)
    max_w = WIDTH - 160
    wrapped = []
    for para in lines:
        words = para.split(" ")
        line = ""
        for word in words:
            test = (line + " " + word).strip()
            if title_font.size(test)[0] <= max_w or not line:
                line = test
            else:
                wrapped.append(line)
                line = word
        wrapped.append(line)
    lines = wrapped
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
            if cur_count < len(line) and (_now_ms() // 250) % 2 == 0:
                cursor_x = x + surf.get_width() + 6
                pygame.draw.rect(
                    surface, (210, 210, 210), (cursor_x, y + 12, 10, line_h - 24)
                )
        cum += len(line)
# ─────────────────────────────────────────────
# DIALOGUE BOX (A-009 shim -> engine.ui.std.dialogue_box)
# ─────────────────────────────────────────────
# Shared speaker accents (core.config.SPEAKER_COLORS; also used by ui/radio.py
# and handed to the shared widget through the game theme).
from core.config import SPEAKER_COLORS  # noqa: E402,F811
from engine.text import T as _T  # RPE6 Phase 4 text table


def reset_dialogue_slide():
    """A-009 shim: the slide state is owned by ``engine.ui.std.dialogue_box``."""
    _dialogue_box.reset_slide()


def draw_dialogue_box(surface, speaker, text, char_idx, total_len, can_continue=True,
                      show_speaker=False):
    """A-009 shim: the box body moved verbatim to ``engine.ui.std.dialogue_box``.

    ``can_continue=None`` draws no prompt (timeline-owned lines, M5 shadow
    finale); ``show_speaker`` opts into the name tab - see the widget docstring.
    """
    _dialogue_box.draw(surface, _hud_theme, speaker, text, char_idx, total_len,
                       can_continue=can_continue, show_speaker=show_speaker)
def draw_cinematic_subtitle(surface, speaker, text, char_idx=None,
                            band=(HEIGHT - LETTER_H, HEIGHT)):
    """Film subtitle, centred in the bottom letterbox band.

    Must be drawn AFTER draw_letterbox (the band is painted black by it); the
    M5 finale calls it from m5shadow3d.draw_controls for that reason. The
    picture stays clear of text ("subtitles are separate from the 3D film
    area"). One font; the speaker is an inline accent-coloured prefix - the
    radio/off-screen convention - not a header strip (polish pass T8). The
    block is laid out from the FULL text so it never jumps while typing.
    """
    if not text and not speaker:
        return
    body_font = font_dialogue
    accent = SPEAKER_COLORS.get((speaker or "").upper(), C_ORANGE)
    prefix = (speaker.upper() + "  ") if speaker else ""
    pw = body_font.size(prefix)[0] if prefix else 0
    max_width = WIDTH - 120

    def wrap(s):
        lines = []
        for para in s.split("\n"):
            cur = ""
            for word in para.split(" "):
                test = (cur + " " + word) if cur else word
                limit = max_width - (pw if not lines else 0)
                if body_font.size(test)[0] <= limit or not cur:
                    cur = test
                else:
                    lines.append(cur)
                    cur = word
            lines.append(cur)
        return lines

    full_lines = wrap(text)
    line_h = body_font.get_linesize()
    top, bottom = band
    y = top + max(2, (bottom - top - len(full_lines) * line_h) // 2)

    # Typewriter over the spoken text only; the speaker prefix is always shown.
    remaining = len(text) if char_idx is None else max(0, min(len(text), char_idx))
    for i, line in enumerate(full_lines):
        x = (WIDTH - body_font.size(line)[0] - (pw if i == 0 else 0)) // 2
        if i == 0 and prefix:
            surface.blit(body_font.render(prefix.rstrip(), True, accent), (x, y))
            x += pw
        part = line[:max(0, remaining)]
        remaining -= len(line) + 1
        if part:
            surface.blit(body_font.render(part, True, (240, 242, 240)), (x, y))
        y += line_h


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
    hdr = font_terminal.render(_T("engine.krap_intel_dossier_active_target"), True, (140, 185, 220))
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
    warn = font_terminal_small.render(_T("engine.warning_target_connected_to_fueg"), True, C_ORANGE)
    surface.blit(warn, (tab_x + 24, tab_y + tab_h - 27))
    # Tiny scanline flicker
    if (_now_ms() // 120) % 2 == 0:
        gy = tab_y + 40 + (_now_ms() // 7) % (tab_h - 50)
        pygame.draw.line(surface, (180, 220, 255, 45), (tab_x, gy), (tab_x + tab_w, gy), 1)
# ─────────────────────────────────────────────
# CUTSCENE SHOT LISTS
# ─────────────────────────────────────────────
import game.timelines as _timelines  # RPE6 P8: timeline data access
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
        "text": "The IPA promises rebuilding.\nTheir oil flows. Their guns sell.\nTheir hands are clean - for the cameras.",
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
        "text": "And then there is KRAP.\nKoaliția Regională de Apărare Și Pace.\nPeacekeepers, they call themselves.",
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
cutscene1_shots = _timelines.shots("core.cutscene1", cutscene1_shots)  # RPE6 P8: timeline data
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
        "text": "He won't get far.\nBut if he does, bring back anything he leaves behind.\nPaper, drives, a notebook - anything.",
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
cutscene2_shots = _timelines.shots("core.cutscene2", cutscene2_shots)  # RPE6 P8: timeline data
