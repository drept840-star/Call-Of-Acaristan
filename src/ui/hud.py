"""HUD overlays: minimap, safe keypad, notebook inspection, desk notes."""
import math
import random
from engine.core import LEGACY_RNG as _rng_legacy  # RPE6 R6: named 'legacy' rng stream
import pygame
from engine.assets import load_sound as _load_sound  # RPE6 D5: raw loads via engine.assets
from engine.core import now_ms as _now_ms  # RPE6 B-001 timebase
_last_note_tick_key = None
from core.config import (
    WIDTH, HEIGHT, TILE_SIZE, FLOOR_TILE_SIZE,
    C_WHITE, C_ORANGE, C_TERMINAL, C_KRAP_BLUE, C_GREY,
    C_BG_GAME, LETTER_H, SCENE_TOP, SCENE_BOT, SPEAKER_COLORS,
    font_terminal, font_terminal_small, font_speaker,
    font_btn, font_prompt, font_dialogue, font_title, screen,
    CONTAINER_TILE_RED, CONTAINER_TILE_BLUE, CONTAINER_TILE_RUST, CONTAINER_TILE_GREY,
    audio, get_scaled_mouse,
)
from core.state import STATE
from engine.ui import minimap as _minimap

_MiniMap = _minimap.MiniMap

# RPE6 Phase 4 (A-009): the shared HUD widgets live in engine.ui.std now; this
# module keeps their legacy names and builds the one theme for them from
# core.config (the engine itself never imports game config).
from engine.ui import Theme as _Theme
from engine.ui import crosshair as _crosshair
from engine.ui import objective_banner as _objective_banner
from engine.text import T as _T  # RPE6 Phase 4 text table

THEME = _Theme(
    size=(WIDTH, HEIGHT), letter_h=LETTER_H, tile_size=TILE_SIZE,
    font_prompt=font_prompt, font_terminal=font_terminal,
    font_terminal_small=font_terminal_small, font_dialogue=font_dialogue,
    font_speaker=font_speaker, font_title=font_title, font_btn=font_btn,
    c_white=C_WHITE, c_grey=C_GREY, c_orange=C_ORANGE, c_terminal=C_TERMINAL,
    c_krap_blue=C_KRAP_BLUE, speaker_colors=SPEAKER_COLORS,
)


class MiniMap(_MiniMap):
    """A-009 shim: the widget lives in ``engine.ui.std.minimap``; this subclass
    pins the game theme so every existing call site keeps its signature."""

    def __init__(self, map_data, tile_size=64, palette="m2"):
        super().__init__(map_data, tile_size, palette, theme=THEME)
def _draw_dirty_hand_text(surface, text, x, y, font, color, seed=0, alpha=120, jitter=2, angle=0):
    rng = random.Random(seed)
    cx = x
    for i, ch in enumerate(text):
        if ch == " ":
            cx += font.size(" ")[0] + rng.randint(2, 6)
            continue
        ch_surf = font.render(ch, True, color).convert_alpha()
        ch_surf.set_alpha(max(0, min(255, alpha + rng.randint(-45, 25))))
        rot = pygame.transform.rotate(ch_surf, angle + rng.uniform(-9, 9))
        rx = cx + rng.randint(-jitter, jitter)
        ry = y + rng.randint(-jitter, jitter)
        surface.blit(rot, (rx, ry))
        if rng.random() < 0.65:
            ghost = font.render(ch, True, color).convert_alpha()
            ghost.set_alpha(max(0, alpha // 3))
            ghost = pygame.transform.rotate(ghost, angle + rng.uniform(-14, 14))
            surface.blit(ghost, (rx + rng.randint(-3, 3), ry + rng.randint(-2, 3)))
        cx += font.size(ch)[0] + rng.randint(-2, 3)
def _draw_crumpled_safe_scrap():
    overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
    overlay.fill((0, 0, 0, 215))
    screen.blit(overlay, (0, 0))
    rng = random.Random(742)
    paper_w, paper_h = 460, 330
    paper = pygame.Surface((paper_w, paper_h), pygame.SRCALPHA)
    pts = [
        (28, 18), (90, 5), (158, 16), (236, 8), (315, 20), (404, 10), (444, 38),
        (433, 92), (452, 148), (430, 205), (445, 286), (388, 317), (316, 306),
        (244, 326), (173, 308), (98, 321), (28, 292), (15, 230), (30, 166),
        (10, 96),
    ]
    shadow = pygame.Surface((paper_w + 40, paper_h + 40), pygame.SRCALPHA)
    pygame.draw.polygon(shadow, (0, 0, 0, 120), [(x + 20, y + 22) for x, y in pts])
    shadow_rot = pygame.transform.rotate(shadow, -4)
    shadow_rect = shadow_rot.get_rect(center=(WIDTH // 2 + 10, HEIGHT // 2 + 12))
    screen.blit(shadow_rot, shadow_rect)
    pygame.draw.polygon(paper, (177, 160, 118), pts)
    pygame.draw.polygon(paper, (92, 73, 45), pts, 2)
    for _ in range(900):
        x = rng.randint(10, paper_w - 12)
        y = rng.randint(8, paper_h - 10)
        if rng.random() < 0.75:
            col = rng.choice([
                (120, 96, 58, 35), (70, 55, 35, 28),
                (210, 196, 150, 18), (35, 28, 20, 20),
            ])
            paper.set_at((x, y), col)
    for _ in range(12):
        sx = rng.randint(45, paper_w - 80)
        sy = rng.randint(35, paper_h - 70)
        sw = rng.randint(30, 110)
        sh = rng.randint(18, 70)
        stain = pygame.Surface((sw, sh), pygame.SRCALPHA)
        pygame.draw.ellipse(stain, rng.choice([
            (45, 32, 20, 45), (78, 51, 22, 38), (20, 20, 18, 35),
        ]), stain.get_rect())
        paper.blit(stain, (sx, sy))
    facets = [
        [(40, 30), (180, 42), (95, 150)],
        [(190, 20), (315, 45), (250, 145)],
        [(320, 38), (430, 70), (365, 180)],
        [(32, 175), (120, 150), (75, 285)],
        [(150, 170), (265, 150), (220, 310)],
        [(275, 165), (420, 210), (335, 300)],
    ]
    for i, fpts in enumerate(facets):
        col = (255, 240, 180, 18) if i % 2 == 0 else (20, 12, 8, 35)
        pygame.draw.polygon(paper, col, fpts)
    fold_lines = [
        ((35, 76), (430, 58), 38), ((54, 145), (432, 132), 62),
        ((34, 220), (428, 205), 45), ((112, 20), (122, 310), 50),
        ((248, 18), (230, 320), 65), ((365, 35), (318, 304), 55),
        ((38, 285), (440, 40), 32), ((30, 44), (420, 292), 30),
    ]
    for (a, b, alpha) in fold_lines:
        pygame.draw.line(paper, (42, 31, 19, alpha), a, b, 4)
        pygame.draw.line(paper, (225, 210, 160, max(15, alpha // 2)),
                         (a[0] + 2, a[1] - 2), (b[0] + 2, b[1] - 2), 1)
    hand_font_big = pygame.font.SysFont("Comic Sans MS", 35, bold=True)
    hand_font_mid = pygame.font.SysFont("Comic Sans MS", 25, bold=True)
    hand_font_small = pygame.font.SysFont("Comic Sans MS", 18, bold=True)
    ink = (37, 31, 25)
    _draw_dirty_hand_text(paper, "dont forget", 72, 72, hand_font_small, ink,
                          seed=12, alpha=55, jitter=3, angle=-6)
    _draw_dirty_hand_text(paper, "7", 122, 132, hand_font_big, ink,
                          seed=1, alpha=95, jitter=5, angle=-10)
    _draw_dirty_hand_text(paper, "4", 210, 126, hand_font_big, ink,
                          seed=2, alpha=62, jitter=7, angle=7)
    _draw_dirty_hand_text(paper, "2", 306, 138, hand_font_big, ink,
                          seed=3, alpha=78, jitter=6, angle=-4)
    _draw_dirty_hand_text(paper, "7  ?  2", 120, 182, hand_font_mid, ink,
                          seed=4, alpha=48, jitter=7, angle=3)
    _draw_dirty_hand_text(paper, "last three", 80, 244, hand_font_small, ink,
                          seed=5, alpha=45, jitter=3, angle=-3)
    for _ in range(34):
        x1 = rng.randint(90, 360)
        y1 = rng.randint(115, 210)
        x2 = x1 + rng.randint(-55, 80)
        y2 = y1 + rng.randint(-10, 18)
        pygame.draw.line(paper, rng.choice([
            (20, 14, 8, 65), (70, 45, 20, 55), (120, 96, 58, 45),
        ]), (x1, y1), (x2, y2), rng.randint(2, 6))
    fold = pygame.Surface((paper_w, paper_h), pygame.SRCALPHA)
    pygame.draw.polygon(fold, (18, 12, 8, 80),
                        [(155, 105), (292, 92), (278, 230), (140, 246)])
    pygame.draw.line(fold, (235, 215, 160, 45), (160, 105), (145, 245), 2)
    paper.blit(fold, (0, 0))
    for _ in range(18):
        hx = rng.randint(35, paper_w - 40)
        hy = rng.randint(30, paper_h - 30)
        if rng.random() < 0.45:
            pygame.draw.line(paper, (65, 45, 28, 90),
                             (hx, hy), (hx + rng.randint(-20, 25), hy + rng.randint(-7, 9)),
                             rng.randint(1, 3))
    for _ in range(85):
        edge = rng.choice(["top", "bottom", "left", "right"])
        if edge == "top":
            x, y = rng.randint(25, paper_w - 25), rng.randint(8, 35)
        elif edge == "bottom":
            x, y = rng.randint(25, paper_w - 25), rng.randint(paper_h - 38, paper_h - 8)
        elif edge == "left":
            x, y = rng.randint(8, 38), rng.randint(25, paper_h - 25)
        else:
            x, y = rng.randint(paper_w - 40, paper_w - 8), rng.randint(25, paper_h - 25)
        pygame.draw.circle(paper, (35, 24, 15, rng.randint(25, 80)), (x, y), rng.randint(1, 5))
    paper_rot = pygame.transform.rotate(paper, -4)
    paper_rect = paper_rot.get_rect(center=(WIDTH // 2, HEIGHT // 2 - 12))
    screen.blit(paper_rot, paper_rect)
    if (_now_ms() // 600) % 2 == 0:
        prompt = font_prompt.render(_T("hud.space_close"), True, (160, 145, 100))
        screen.blit(prompt, (WIDTH // 2 - prompt.get_width() // 2, HEIGHT // 2 + 210))
    lbl = font_terminal_small.render(_T("hud.crumpled_scrap"), True, (95, 82, 58))
    screen.blit(lbl, (WIDTH // 2 - lbl.get_width() // 2, HEIGHT // 2 - 218))
def _schedule_text_ticks(text, start_delay=0, step=2, volume=0.08, max_ticks=42):
    tick_i = 0
    for ch in text:
        if ch and not ch.isspace():
            if tick_i < max_ticks and (tick_i % 2 == 0 or ch in ".!?"):
                audio.schedule(start_delay + tick_i * step, "type_tick", volume=volume)
            tick_i += 1
def _play_ui_type_tick(volume=0.095):
    try:
        audio.play("type_tick", volume=volume)
    except Exception:
        pass
def draw_desk_note():
    global _last_note_tick_key
    if not STATE.active_read_note:
        _last_note_tick_key = None
        return
    if _last_note_tick_key != STATE.active_read_note:
        _last_note_tick_key = STATE.active_read_note
        _schedule_text_ticks(str(STATE.active_read_note).replace("__CRUMPLED_SAFE_SCRAP__", "crumpled scrap"), start_delay=0, step=2, volume=0.075, max_ticks=38)
    if STATE.active_read_note == "__CRUMPLED_SAFE_SCRAP__":
        _draw_crumpled_safe_scrap()
        return
    overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
    overlay.fill((0, 0, 0, 200))
    screen.blit(overlay, (0, 0))
    panel_w, panel_h = 500, 280
    panel_x = (WIDTH - panel_w) // 2
    panel_y = (HEIGHT - panel_h) // 2
    paper = pygame.Surface((panel_w, panel_h))
    paper.fill((32, 28, 22))
    for row in range(0, panel_h, 3):
        shade = _rng_legacy.randint(-3, 3)
        c = max(0, min(255, 32 + shade))
        pygame.draw.line(paper, (c, c - 2, c - 4), (0, row), (panel_w, row))
    screen.blit(paper, (panel_x, panel_y))
    pygame.draw.rect(screen, (80, 70, 50), (panel_x, panel_y, panel_w, panel_h), 2)
    header = font_speaker.render(_T("hud.field_note"), True, C_ORANGE)
    screen.blit(header, (panel_x + 16, panel_y + 12))
    pygame.draw.line(
        screen,
        (80, 65, 35),
        (panel_x + 16, panel_y + 42),
        (panel_x + panel_w - 16, panel_y + 42),
        1,
    )
    lines = STATE.active_read_note.split("\n")
    y = panel_y + 56
    for line in lines:
        surf = font_terminal.render(line, True, C_WHITE)
        screen.blit(surf, (panel_x + 20, y))
        y += 28
    if (_now_ms() // 600) % 2 == 0:
        prompt = font_prompt.render(_T("hud.space_close"), True, (160, 145, 100))
        screen.blit(
            prompt,
            (panel_x + panel_w // 2 - prompt.get_width() // 2, panel_y + panel_h - 28),
        )
_notebook_inspect_timer = 0
def reset_notebook_inspect():
    global _notebook_inspect_timer
    _notebook_inspect_timer = 0
def draw_notebook_inspection():
    global _notebook_inspect_timer
    _notebook_inspect_timer += 1
    # ── Dark overlay fades in ──
    overlay_alpha = min(210, _notebook_inspect_timer * 8)
    overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
    overlay.fill((0, 0, 0, overlay_alpha))
    screen.blit(overlay, (0, 0))
    # ── Notebook slides/zooms in ──
    slide_progress = min(1.0, _notebook_inspect_timer / 20.0)
    ease = 1.0 - (1.0 - slide_progress) ** 2
    # ── Bounce settle at end ──
    if slide_progress >= 0.85:
        b_t = (slide_progress - 0.85) / 0.15
        bounce_os = -math.sin(b_t * math.pi * 2) * 5 * (1.0 - b_t)
    else:
        bounce_os = 0
    slide_offset = int((1.0 - ease) * 60 + bounce_os)
    panel_w, panel_h = 780, 520
    panel_x = (WIDTH - panel_w) // 2
    panel_y = (HEIGHT - panel_h) // 2
    # ── Panel rendered with slide offset ──
    paper = pygame.Surface((panel_w, panel_h))
    paper.fill((28, 24, 18))
    for row in range(0, panel_h, 3):
        shade = _rng_legacy.randint(-3, 3)
        c = max(0, min(255, 28 + shade))
        pygame.draw.line(paper, (c, c - 2, c - 4), (0, row), (panel_w, row))
    screen.blit(paper, (panel_x, panel_y + slide_offset))
    pygame.draw.rect(screen, (90, 75, 45), (panel_x, panel_y + slide_offset, panel_w, panel_h), 2)
    pygame.draw.rect(
        screen, (55, 45, 28), (panel_x + 5, panel_y + 5 + slide_offset, panel_w - 10, panel_h - 10), 1
    )
    # ── Classified stamp appears after delay ──
    stamp_alpha = min(255, max(0, _notebook_inspect_timer - 30) * 12)
    stamp_surf = pygame.Surface((180, 60), pygame.SRCALPHA)
    stamp_txt = font_speaker.render(_T("hud.classified"), True, (180, 30, 30, stamp_alpha))
    stamp_surf.blit(stamp_txt, (0, 10))
    pygame.draw.rect(
        stamp_surf,
        (180, 30, 30, stamp_alpha),
        (0, 8, stamp_txt.get_width() + 4, stamp_txt.get_height() + 4),
        2,
    )
    rotated = pygame.transform.rotate(stamp_surf, -18)
    screen.blit(rotated, (panel_x + panel_w - 190, panel_y + 8 + slide_offset))
    pygame.draw.rect(screen, (20, 16, 10), (panel_x, panel_y, panel_w, 44))
    pygame.draw.line(
        screen,
        (90, 75, 45),
        (panel_x, panel_y + 44),
        (panel_x + panel_w, panel_y + 44),
        1,
    )
    header_lbl = font_terminal_small.render(
        _T("hud.operation_black_notebook_field_i"),
        True,
        (120, 100, 60),
    )
    screen.blit(header_lbl, (panel_x + 16, panel_y + 14))
    col_div = panel_x + panel_w // 2 - 10
    pygame.draw.line(
        screen,
        (55, 45, 30),
        (col_div, panel_y + 52),
        (col_div, panel_y + panel_h - 40),
        1,
    )
    lx = panel_x + 20
    ly = panel_y + 58
    map_hdr = font_terminal_small.render(_T("hud.operational_map"), True, (160, 130, 60))
    screen.blit(map_hdr, (lx, ly))
    pygame.draw.line(screen, (80, 65, 35), (lx, ly + 16), (col_div - 20, ly + 16), 1)
    ly += 24
    map_lines = [
        ("IPA safehouses", "7 marked", (200, 80, 80)),
        ("KRAP checkpoints", "12 marked", (80, 120, 200)),
        ("MAG supply routes", "sewers", (80, 160, 80)),
        ("Volkov handoff", "WAREHOUSE DISTRICT", (220, 180, 60)),
        ("Exfil route", "STAIR \u2192 BAY DOOR", (160, 140, 200)),
    ]
    for label, value, vcol in map_lines:
        lbl_s = font_terminal_small.render(label, True, (140, 130, 110))
        val_s = font_terminal_small.render(value, True, vcol)
        screen.blit(lbl_s, (lx + 8, ly))
        screen.blit(val_s, (lx + 8 + lbl_s.get_width() + 6, ly))
        ly += 19
    ly += 12
    tgt_hdr = font_terminal_small.render(_T("hud.target_photo"), True, (160, 130, 60))
    screen.blit(tgt_hdr, (lx, ly))
    pygame.draw.line(screen, (80, 65, 35), (lx, ly + 16), (col_div - 20, ly + 16), 1)
    ly += 24
    photo_w, photo_h = 90, 110
    photo_x, photo_y = lx + 8, ly
    pygame.draw.rect(screen, (18, 16, 14), (photo_x, photo_y, photo_w, photo_h))
    pygame.draw.rect(screen, (50, 45, 38), (photo_x, photo_y, photo_w, photo_h), 1)
    pygame.draw.circle(screen, (42, 38, 32), (photo_x + photo_w // 2, photo_y + 32), 22)
    pygame.draw.ellipse(screen, (38, 34, 28), (photo_x + 14, photo_y + 52, 62, 55))
    if not hasattr(draw_notebook_inspection, "_photo_noise"):
        noise_surf = pygame.Surface((photo_w, photo_h), pygame.SRCALPHA)
        rng = random.Random(42)
        for _ in range(200):
            gx = rng.randint(0, photo_w - 1)
            gy = rng.randint(0, photo_h - 1)
            v = rng.randint(30, 70)
            noise_surf.set_at((gx, gy), (v, v, v, 255))
        draw_notebook_inspection._photo_noise = noise_surf
    screen.blit(draw_notebook_inspection._photo_noise, (photo_x, photo_y))
    photo_lbl = font_terminal_small.render(_T("hud.sebastian_volkov"), True, (200, 180, 100))
    screen.blit(photo_lbl, (photo_x + photo_w + 10, photo_y + 4))
    target_details = [
        ("Affiliation", "IPA"),
        ("Role", "Logistics coord."),
        ("Last seen", "Slum dist. 22:47"),
        ("Status", "AT LARGE"),
    ]
    ty2 = photo_y + 24
    for k, v in target_details:
        ks = font_terminal_small.render(k + ": ", True, (110, 105, 90))
        vs = font_terminal_small.render(v, True, (200, 195, 175))
        screen.blit(ks, (photo_x + photo_w + 10, ty2))
        screen.blit(vs, (photo_x + photo_w + 10, ty2 + 14))
        ty2 += 34
    rx = col_div + 20
    ry = panel_y + 58
    ev_hdr = font_terminal_small.render(_T("hud.evidence_log"), True, (160, 130, 60))
    screen.blit(ev_hdr, (rx, ry))
    pygame.draw.line(
        screen, (80, 65, 35), (rx, ry + 16), (panel_x + panel_w - 20, ry + 16), 1
    )
    ry += 24
    evidence = [
        ("ITEM", "Black notebook, leather, unmarked"),
        ("CONTENTS", "FuegoTech serial registry"),
        ("SERIALS", "FT-7742 FT-7743 FT-7744 FT-7745"),
        ("CROSS-REF", "IPA procurement #8841-8844"),
        ("MFG", "FuegoTech Ind., Kilemene Sector"),
        ("STATUS", "RECOVERED"),
    ]
    for key, val in evidence:
        ks = font_terminal_small.render(key, True, (110, 105, 90))
        screen.blit(ks, (rx + 8, ry))
        if key == "STATUS":
            vcol2 = (80, 220, 100)
        elif key == "SERIALS":
            vcol2 = (220, 160, 60)
        else:
            vcol2 = (190, 185, 165)
        vs = font_terminal_small.render(val, True, vcol2)
        screen.blit(vs, (rx + 16, ry + 15))
        ry += 38
    ry += 4
    pygame.draw.line(screen, (70, 60, 35), (rx, ry), (panel_x + panel_w - 20, ry), 1)
    ry += 10
    q1 = font_terminal_small.render(_T("hud.the_fire_burns_both_ways"), True, (140, 120, 80))
    q2 = font_terminal_small.render(_T("hud.cmdr"), True, (110, 95, 60))
    screen.blit(q1, (rx + 8, ry))
    screen.blit(q2, (rx + 8, ry + 18))
    pygame.draw.line(
        screen,
        (55, 45, 28),
        (panel_x + 10, panel_y + panel_h - 34),
        (panel_x + panel_w - 10, panel_y + panel_h - 34),
        1,
    )
    footer = font_terminal_small.render(
        _T("hud.krap_intelligence_division_field"),
        True,
        (80, 70, 45),
    )
    screen.blit(
        footer,
        (panel_x + panel_w // 2 - footer.get_width() // 2, panel_y + panel_h - 26),
    )
    if (_now_ms() // 600) % 2 == 0:
        prompt = font_prompt.render(_T("hud.space_close"), True, (160, 145, 100))
        screen.blit(
            prompt,
            (panel_x + panel_w // 2 - prompt.get_width() // 2, panel_y + panel_h + 14),
        )
def _safe_666_asset_candidates():
    """Candidate locations for user-provided assets/demon.mp3.

    User's local project root may be named "First Try"; support both running
    from that root and from this code folder.
    """
    import os
    here = os.path.dirname(os.path.abspath(__file__))
    cwd = os.path.abspath(".")
    parent = os.path.dirname(here)
    return [
        os.path.join(here, "assets", "demon.mp3"),
        os.path.join(cwd, "assets", "demon.mp3"),
        os.path.join(cwd, "First Try", "assets", "demon.mp3"),
        os.path.join(cwd, "First try", "assets", "demon.mp3"),
        os.path.join(here, "First Try", "assets", "demon.mp3"),
        os.path.join(here, "First try", "assets", "demon.mp3"),
        os.path.join(parent, "First Try", "assets", "demon.mp3"),
        os.path.join(parent, "First try", "assets", "demon.mp3"),
        "assets/demon.mp3",
        "First Try/assets/demon.mp3",
        "First try/assets/demon.mp3",
    ]


def _play_safe_666_demon_noise():
    """Loop demon.mp3 if present; fall back to procedural layers."""
    import os
    try:
        # Stop music so demon.mp3 owns the scare soundscape.
        try:
            pygame.mixer.music.stop()
        except Exception:
            pass
        for path in _safe_666_asset_candidates():
            if path and os.path.exists(path):
                snd = _load_sound(path)
                ch = snd.play(loops=-1)
                if ch:
                    ch.set_volume(1.0)
                STATE.safe_666_demon_sound = snd
                STATE.safe_666_demon_channel = ch
                return True
    except Exception as e:
        print(f"demon.mp3 play failed: {e}")
    return False


def _stop_safe_666_demon_noise():
    """Cut off the easter egg noise before the fake crash dialog appears."""
    try:
        ch = getattr(STATE, "safe_666_demon_channel", None)
        if ch:
            ch.stop()
    except Exception:
        pass
    try:
        snd = getattr(STATE, "safe_666_demon_sound", None)
        if snd:
            snd.stop()
    except Exception:
        pass
    try:
        pygame.mixer.music.stop()
    except Exception:
        pass
    try:
        audio.stop_all()
    except Exception:
        pass
    STATE.safe_666_demon_channel = None
    STATE.safe_666_demon_sound = None


def _safe_666_window_tamper(t, total_t):
    """Subtle OS-window tampering for the 666 scare.

    Low intensity by design: corrupt the title and drift the window a few pixels
    if pygame exposes an SDL2 Window. This is creepier than another loud flash,
    but should not be violent or disruptive.
    """
    # Caption corruption.
    try:
        original = getattr(STATE, "safe_666_original_caption", "Call of Acaristan")
        sequence = [
            (0, original),
            (36, "Call of Acaristan - 666"),
            (88, "SAFE ACCESS GRANTED"),
            (132, "DO NOT ACKNOWLEDGE"),
            (184, "Call of Acaristan (not responding)"),
            (260, "FATAL ERROR 0x00000666"),
            (330, "DON'T LOOK BEHIND YOU"),
        ]
        title = sequence[0][1]
        for frame, candidate in sequence:
            if t >= frame:
                title = candidate
        if (t // 9) % 11 == 0 and t > 70:
            title = title.replace("A", "4").replace("O", "0")
        pygame.display.set_caption(title)
    except Exception:
        pass

    # Small window drift / breathing. Works only when pygame._sdl2 is present.
    try:
        if not hasattr(STATE, "safe_666_window_base_pos"):
            from pygame._sdl2.video import Window
            win = Window.from_display_module()
            STATE.safe_666_window_ref = win
            STATE.safe_666_window_base_pos = tuple(win.position)
        win = getattr(STATE, "safe_666_window_ref", None)
        base = getattr(STATE, "safe_666_window_base_pos", None)
        if win is not None and base is not None:
            # Breathe by only a handful of pixels.
            amp = 2 + min(4, max(0, (t - 100) // 90))
            ox = int(math.sin(t * 0.16) * amp)
            oy = int(math.sin(t * 0.11 + 1.7) * (amp - 1))
            # Occasional wrong-feeling 1-frame nudge.
            if (t % 77) in (0, 1):
                ox += 3
                oy -= 2
            win.position = (base[0] + ox, base[1] + oy)

            # Very subtle OS-window opacity pulse. This affects the actual
            # application window on SDL2 platforms, but never touches desktop
            # settings, files, wallpaper, etc.
            try:
                if not hasattr(STATE, "safe_666_window_base_opacity"):
                    STATE.safe_666_window_base_opacity = float(getattr(win, "opacity", 1.0) or 1.0)
                base_opacity = float(getattr(STATE, "safe_666_window_base_opacity", 1.0))
                dip = 0.035 + 0.025 * (0.5 + 0.5 * math.sin(t * 0.09))
                if (t % 103) in (0, 1, 2):
                    dip += 0.05
                win.opacity = max(0.86, min(1.0, base_opacity - dip))
            except Exception:
                pass
    except Exception:
        pass


def _draw_safe_666_error_glyphs(t, rng):
    """Quiet terminal error text around the edges of the 666 screen."""
    lines = [
        "SAFE_MEMORY_READ: FAILED",
        "USER CONFIRMED: 666",
        "ACCESS LEVEL 6 ACCEPTED",
        "PROCESS OWNER: UNKNOWN",
        "DO NOT ACKNOWLEDGE",
        "WINDOW HANDLE: COMPROMISED",
    ]
    base_x = 22
    base_y = SCENE_TOP + 8
    for i, line in enumerate(lines[:4]):
        if t < 28 + i * 18:
            continue
        txt = font_terminal_small.render(line, True, (105, 0, 0))
        txt.set_alpha(65 + int(35 * math.sin(t * 0.05 + i)))
        screen.blit(txt, (base_x + rng.randint(-1, 1), base_y + i * 17 + rng.randint(-1, 1)))
    # Right-side readout.
    for i, line in enumerate(lines[4:]):
        if t < 120 + i * 28:
            continue
        txt = font_terminal_small.render(line, True, (95, 0, 0))
        txt.set_alpha(75)
        screen.blit(txt, (WIDTH - txt.get_width() - 28 + rng.randint(-1, 1), SCENE_BOT - 54 + i * 17))


def _safe_666_fake_crash():
    """Show an error window, stop audio, then terminate the game."""
    if getattr(STATE, "safe_666_crashed", False):
        return True
    STATE.safe_666_crashed = True
    STATE.safe_666_active = False
    STATE.safe_666_timer = 0
    _stop_safe_666_demon_noise()
    try:
        pygame.display.set_caption("Call of Acaristan - Fatal Error")
    except Exception:
        pass
    # Restore opacity before showing the native OS error dialog.
    try:
        win = getattr(STATE, "safe_666_window_ref", None)
        if win is not None:
            win.opacity = float(getattr(STATE, "safe_666_window_base_opacity", 1.0) or 1.0)
    except Exception:
        pass

    message = (
        "FATAL ERROR 0x00000666\n\n"
        "SECURE CONSOLE BREACH DETECTED\n"
        "Forbidden access key accepted.\n\n"
        "Process terminated to protect campaign state."
    )
    # Prefer SDL's native message box; fall back to tkinter if unavailable.
    try:
        pygame.display.message_box(
            "Call of Acaristan - Fatal Error",
            message,
            "error",
            buttons=("CLOSE",),
            return_button=0,
            escape_button=0,
        )
    except Exception:
        try:
            import tkinter as tk
            from tkinter import messagebox
            root = tk.Tk()
            root.withdraw()
            messagebox.showerror("Call of Acaristan - Fatal Error", message)
            root.destroy()
        except Exception as e:
            print(message)
            print(f"Error dialog failed: {e}")
    pygame.quit()
    raise SystemExit("FATAL ERROR 0x00000666")


def _trigger_safe_666_easter_egg():
    """Mission 1 creepy safe-code easter egg for entering 666."""
    STATE.safe_keypad_active = False
    STATE.safe_keypad_code = ""
    STATE.safe_666_active = True
    # 6.5 seconds at 60fps: long enough to sit with the player before the fake crash.
    STATE.safe_666_timer = 390
    STATE.safe_666_seed = _rng_legacy.randint(1, 999999)
    STATE.safe_666_total_timer = STATE.safe_666_timer
    STATE.safe_666_crashed = False
    try:
        STATE.safe_666_original_caption = pygame.display.get_caption()[0] or "Call of Acaristan"
    except Exception:
        STATE.safe_666_original_caption = "Call of Acaristan"
    if hasattr(STATE, "safe_666_window_base_pos"):
        try:
            del STATE.safe_666_window_base_pos
        except Exception:
            pass
    if hasattr(STATE, "safe_666_window_ref"):
        try:
            del STATE.safe_666_window_ref
        except Exception:
            pass
    pygame.mouse.set_visible(False)

    used_external = _play_safe_666_demon_noise()

    # Loud layered sting. demon.mp3 supplies the bed; procedural hits punctuate it.
    try:
        audio.play("explosion", volume=1.0)
        audio.play("alarm", volume=0.85 if used_external else 1.0)
        audio.play("terminal_glitch", volume=1.0)
        audio.play("glass_shatter", volume=0.85)
        audio.play("heartbeat", volume=0.95)
        if hasattr(audio, "schedule"):
            audio.schedule(22, "terminal_glitch", volume=1.0)
            audio.schedule(45, "heartbeat", volume=1.0)
            audio.schedule(68, "explosion", volume=0.55)
            audio.schedule(96, "glass_shatter", volume=0.65)
            audio.schedule(128, "terminal_glitch", volume=0.9)
            audio.schedule(210, "heartbeat", volume=1.0)
            audio.schedule(280, "terminal_glitch", volume=1.0)
    except Exception:
        pass


def _submit_safe_keypad_code():
    """Handle ENTER on the safe keypad, including the 666 easter egg."""
    if STATE.safe_keypad_code == "666":
        _trigger_safe_666_easter_egg()
        return
    if STATE.safe_keypad_callback:
        STATE.safe_keypad_callback(STATE.safe_keypad_code == STATE.safe_keypad_target)
    STATE.safe_keypad_active = False
    pygame.mouse.set_visible(False)


def _draw_safe_666_easter_egg():
    if not getattr(STATE, "safe_666_active", False):
        return False

    timer = int(getattr(STATE, "safe_666_timer", 0))
    if timer <= 0:
        _safe_666_fake_crash()
        return True

    STATE.safe_666_timer = timer - 1
    total_t = int(getattr(STATE, "safe_666_total_timer", 390) or 390)
    t = total_t - timer
    rng = random.Random(getattr(STATE, "safe_666_seed", 666) + t // 2)
    _safe_666_window_tamper(t, total_t)

    screen.fill((0, 0, 0))
    flash = max(0, 150 - t * 5)
    if flash > 0:
        red = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        red.fill((180, 0, 0, flash))
        screen.blit(red, (0, 0))

    # VHS/CRT tearing.
    for _ in range(22):
        y = rng.randint(0, HEIGHT - 1)
        h = rng.randint(1, 7)
        a = rng.randint(18, 85)
        col = rng.choice([(120, 0, 0, a), (255, 255, 255, a // 3), (20, 0, 0, a)])
        pygame.draw.rect(screen, col, (rng.randint(-60, 60), y, WIDTH + 120, h))

    # Central apparition - elongated mask, pinhole eyes, crooked mouth.
    # The previous round face looked cartoony; this is intentionally asymmetrical
    # and too tall, with a jaw that hangs lower than it should.
    cx = WIDTH // 2 + rng.randint(-5, 5)
    cy = HEIGHT // 2 - 28 + rng.randint(-4, 4)
    pulse = 0.5 + 0.5 * math.sin(t * 0.23)
    jump = 1.0 + (0.045 if 54 < (t % 80) < 60 else 0.0)

    # Body/shoulder silhouette receding into black.
    body = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
    pygame.draw.polygon(body, (5, 0, 0, 235), [
        (cx - 120, cy + 88), (cx + 118, cy + 84),
        (cx + 205, HEIGHT + 40), (cx - 215, HEIGHT + 40),
    ])
    pygame.draw.ellipse(body, (30, 0, 0, 70), (cx - 210, cy + 72, 420, 170))
    screen.blit(body, (0, 0))

    # Occult mark behind the apparition: inverted pentagram + ritual ring.
    # Drawn before the face so it feels embedded in the image, not like UI text.
    sig = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
    ring_r = int(150 + pulse * 10)
    pygame.draw.circle(sig, (120, 0, 0, 105), (cx, cy + 8), ring_r, 2)
    pygame.draw.circle(sig, (55, 0, 0, 90), (cx, cy + 8), ring_r - 22, 1)
    # Inverted pentagram: one point down, two points up.
    pts = []
    for i in range(5):
        ang = math.pi / 2 + i * (math.tau / 5.0)
        pts.append((
            cx + math.cos(ang) * (ring_r - 26),
            cy + 8 + math.sin(ang) * (ring_r - 26),
        ))
    for a_i, b_i in ((0, 2), (2, 4), (4, 1), (1, 3), (3, 0)):
        pygame.draw.line(sig, (170, 0, 0, 115), pts[a_i], pts[b_i], 2)
        pygame.draw.line(sig, (35, 0, 0, 160), (pts[a_i][0] + 2, pts[a_i][1] + 2), (pts[b_i][0] + 2, pts[b_i][1] + 2), 1)
    # Sixes around the ring, subtle and jittered.
    for i, txt in enumerate(("VI", "VI", "VI", "666")):
        ang = -math.pi / 2 + i * math.tau / 4.0 + (0.04 * math.sin(t * 0.07 + i))
        rr = ring_r + (18 if txt == "666" else 7)
        tx2 = cx + math.cos(ang) * rr
        ty2 = cy + 8 + math.sin(ang) * rr
        s = font_terminal.render(txt, True, (150, 0, 0))
        s.set_alpha(130 if txt == "666" else 85)
        s = pygame.transform.rotate(s, -math.degrees(ang) + 90)
        sig.blit(s, (int(tx2 - s.get_width() / 2), int(ty2 - s.get_height() / 2)))
    screen.blit(sig, (0, 0), special_flags=pygame.BLEND_RGBA_ADD)

    # Irregular mask/skull shape.
    w = int(150 * jump + pulse * 12)
    h = int(238 * jump + pulse * 10)
    top = cy - h // 2
    bot = cy + h // 2
    mask_pts = [
        (cx - int(w * 0.25) + rng.randint(-3, 2), top + 2),
        (cx + int(w * 0.23) + rng.randint(-2, 3), top + 4),
        (cx + int(w * 0.44) + rng.randint(-2, 3), cy - 58),
        (cx + int(w * 0.38) + rng.randint(-4, 2), cy + 26),
        (cx + int(w * 0.18) + rng.randint(-2, 3), bot - 6),
        (cx + rng.randint(-3, 3), bot + 18),
        (cx - int(w * 0.22) + rng.randint(-3, 3), bot - 4),
        (cx - int(w * 0.42) + rng.randint(-3, 3), cy + 20),
        (cx - int(w * 0.47) + rng.randint(-2, 4), cy - 62),
    ]
    pygame.draw.polygon(screen, (9, 0, 0), mask_pts)
    pygame.draw.polygon(screen, (95, 0, 0), mask_pts, 2)
    pygame.draw.polygon(screen, (25, 0, 0), [(x + 7, y + 5) for x, y in mask_pts], 1)

    # Horns: black, curved silhouettes with red rim. This pushes the image from
    # generic monster-face into explicitly demonic/satanic iconography.
    left_horn = [
        (cx - 38, top + 12),
        (cx - 96 + rng.randint(-3, 3), top - 56 + rng.randint(-4, 4)),
        (cx - 62, top + 30),
    ]
    right_horn = [
        (cx + 38, top + 12),
        (cx + 96 + rng.randint(-3, 3), top - 56 + rng.randint(-4, 4)),
        (cx + 62, top + 30),
    ]
    for horn in (left_horn, right_horn):
        pygame.draw.polygon(screen, (4, 0, 0), horn)
        pygame.draw.line(screen, (140, 0, 0), horn[0], horn[1], 2)
        pygame.draw.line(screen, (60, 0, 0), horn[1], horn[2], 1)

    # Inverted cross carved into the forehead.
    cross_y = cy - 92
    pygame.draw.line(screen, (165, 0, 0), (cx, cross_y - 5), (cx, cross_y + 42), 3)
    pygame.draw.line(screen, (165, 0, 0), (cx - 18, cross_y + 26), (cx + 18, cross_y + 26), 3)
    pygame.draw.line(screen, (0, 0, 0), (cx + 3, cross_y - 3), (cx + 3, cross_y + 43), 1)
    pygame.draw.line(screen, (0, 0, 0), (cx - 16, cross_y + 29), (cx + 20, cross_y + 29), 1)

    # Cracks / cuts on the mask.
    crack_rng = random.Random(6660 + getattr(STATE, "safe_666_seed", 666))
    for _ in range(13):
        sx = cx + crack_rng.randint(-58, 58)
        sy = cy + crack_rng.randint(-85, 92)
        if abs(sx - cx) / max(1, w / 2) + abs(sy - cy) / max(1, h / 2) > 1.25:
            continue
        ex = sx + crack_rng.randint(-32, 32)
        ey = sy + crack_rng.randint(8, 42)
        pygame.draw.line(screen, (0, 0, 0), (sx, sy), (ex, ey), crack_rng.choice([1, 1, 2]))
        if crack_rng.random() < 0.45:
            pygame.draw.line(screen, (80, 0, 0), (sx, sy), (sx + (ex-sx)//2, sy + (ey-sy)//2), 1)

    # Eye sockets: black slits with tiny red pinpoints, not big cartoon eyes.
    eye_glow = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
    eye_col = (255, 18 + int(45 * pulse), 12)
    for side, skew in [(-1, -8), (1, 5)]:
        ex = cx + side * 46 + rng.randint(-2, 2)
        ey = cy - 42 + side * 2 + rng.randint(-1, 1)
        socket = [
            (ex - 36, ey - 10), (ex + 22, ey - 14 + skew // 4),
            (ex + 34, ey - 3), (ex + 16, ey + 9),
            (ex - 30, ey + 7),
        ]
        pygame.draw.polygon(screen, (0, 0, 0), socket)
        pygame.draw.polygon(screen, (72, 0, 0), socket, 1)
        # tiny glowing pupil deep in the socket
        px = ex + side * 4 + rng.randint(-1, 1)
        py = ey - 1 + rng.randint(-1, 1)
        pygame.draw.circle(eye_glow, (255, 0, 0, 70), (px, py), 15)
        pygame.draw.circle(screen, eye_col, (px, py), 4)
        pygame.draw.circle(screen, (255, 190, 160), (px, py), 1)
    screen.blit(eye_glow, (0, 0), special_flags=pygame.BLEND_RGBA_ADD)

    # Nose absence / vertical hollow.
    pygame.draw.polygon(screen, (0, 0, 0), [
        (cx - 8, cy - 12), (cx + 8, cy - 10),
        (cx + 4, cy + 28), (cx - 12, cy + 26),
    ])

    # Mouth: too-wide, crooked slit with uneven triangular teeth.
    mouth_y = cy + 72 + rng.randint(-2, 2)
    mouth_left = cx - 82 + rng.randint(-2, 2)
    mouth_right = cx + 86 + rng.randint(-2, 2)
    pygame.draw.line(screen, (210, 0, 0), (mouth_left, mouth_y), (mouth_right, mouth_y - 5), 3)
    pygame.draw.line(screen, (0, 0, 0), (mouth_left + 4, mouth_y + 5), (mouth_right - 4, mouth_y), 12)
    teeth_rng = random.Random(666 + t // 3)
    x = mouth_left + 10
    while x < mouth_right - 8:
        tw = teeth_rng.randint(5, 9)
        th = teeth_rng.randint(15, 32)
        top_tooth = teeth_rng.random() < 0.55
        if top_tooth:
            pts = [(x, mouth_y + 1), (x + tw, mouth_y), (x + tw // 2, mouth_y + th)]
        else:
            pts = [(x, mouth_y + 6), (x + tw, mouth_y + 5), (x + tw // 2, mouth_y - th // 2)]
        pygame.draw.polygon(screen, (205, 198, 168), pts)
        pygame.draw.polygon(screen, (48, 42, 35), pts, 1)
        x += tw + teeth_rng.randint(4, 8)

    # A subliminal one-frame-ish closer duplicate every so often.
    if (t % 47) in (0, 1):
        pygame.draw.polygon(screen, (160, 0, 0), [(int(cx + (x-cx)*1.08), int(cy + (y-cy)*1.08)) for x, y in mask_pts], 2)

    # Blood/ink drips from eyes and mouth; very dark so it does not become
    # cartoony, but it gives the image a ritual-horror texture.
    drip = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
    drip_rng = random.Random(getattr(STATE, "safe_666_seed", 666) + 9000)
    for ex in (cx - 46, cx + 47):
        for i in range(5):
            dx = ex + drip_rng.randint(-14, 14)
            length = drip_rng.randint(34, 112)
            sway = int(math.sin(t * 0.05 + i) * 4)
            pygame.draw.line(drip, (120, 0, 0, 150), (dx, cy - 28), (dx + sway, cy - 28 + length), 2)
            pygame.draw.circle(drip, (70, 0, 0, 160), (dx + sway, cy - 28 + length), drip_rng.randint(2, 4))
    for i in range(9):
        dx = mouth_left + 15 + i * 18 + drip_rng.randint(-5, 5)
        length = drip_rng.randint(26, 95)
        pygame.draw.line(drip, (105, 0, 0, 135), (dx, mouth_y + 7), (dx + drip_rng.randint(-4, 4), mouth_y + 7 + length), 2)
    screen.blit(drip, (0, 0))

    # Hands/claws at the screen edges, like something is pressing against the
    # display. These are silhouettes, not UI ornaments.
    claw = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
    for side in (-1, 1):
        base_x = 20 if side < 0 else WIDTH - 20
        for i in range(6):
            fy = SCENE_TOP + 54 + i * 64 + rng.randint(-12, 12)
            reach = rng.randint(28, 64)
            x0 = base_x
            x1 = base_x + side * reach
            pygame.draw.line(claw, (6, 0, 0, 220), (x0, fy), (x1, fy + rng.randint(-16, 16)), 7)
            tip = (x1, fy + rng.randint(-16, 16))
            pygame.draw.polygon(claw, (95, 0, 0, 160), [
                tip,
                (tip[0] - side * 14, tip[1] - 5),
                (tip[0] - side * 10, tip[1] + 8),
            ])
    screen.blit(claw, (0, 0))

    # Scratched numbers / crosses in the background. They flicker and never sit
    # quite still, which feels more cursed than static labels.
    for i in range(10):
        if rng.random() < 0.75:
            s_txt = rng.choice(["666", "VI VI VI", "SSS", "†", "††"])
            small = font_terminal.render(s_txt, True, (115, 0, 0))
            small.set_alpha(rng.randint(45, 115))
            if rng.random() < 0.45:
                small = pygame.transform.rotate(small, rng.choice([-12, -7, 8, 15, 180]))
            screen.blit(small, (rng.randint(40, WIDTH - 160), rng.randint(SCENE_TOP + 20, SCENE_BOT - 60)))

    # Jumpscare frames: sudden too-close flashes of eyes/teeth. Kept brief so it
    # shocks without becoming the normal screen state.
    jumpscare = (26 <= t <= 32) or (82 <= t <= 87) or (146 <= t <= 151)
    if jumpscare:
        js = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        js.fill((0, 0, 0, 230))
        jx = WIDTH // 2 + rng.randint(-18, 18)
        jy = HEIGHT // 2 + rng.randint(-10, 10)
        for side in (-1, 1):
            ex = jx + side * 170
            ey = jy - 86 + rng.randint(-6, 6)
            pygame.draw.polygon(js, (0, 0, 0, 255), [(ex - 118, ey - 30), (ex + 118, ey - 42), (ex + 96, ey + 36), (ex - 102, ey + 28)])
            pygame.draw.polygon(js, (255, 0, 0, 235), [(ex - 72, ey - 10), (ex + 58, ey - 18), (ex + 42, ey + 12), (ex - 55, ey + 16)])
            pygame.draw.circle(js, (255, 210, 180, 240), (ex + side * 8, ey), 5)
        my = jy + 128
        pygame.draw.rect(js, (0, 0, 0, 255), (jx - 275, my - 28, 550, 82))
        for i in range(24):
            txx = jx - 250 + i * 22 + rng.randint(-4, 4)
            th = rng.randint(34, 78)
            if i % 2 == 0:
                pts = [(txx, my - 26), (txx + 18, my - 24), (txx + 8, my + th)]
            else:
                pts = [(txx, my + 50), (txx + 18, my + 48), (txx + 8, my - th // 2)]
            pygame.draw.polygon(js, (220, 215, 185, 245), pts)
            pygame.draw.polygon(js, (45, 0, 0, 255), pts, 1)
        screen.blit(js, (0, 0))
        pygame.draw.rect(screen, (255, 255, 255), (0, HEIGHT // 2 + rng.randint(-30, 30), WIDTH, rng.randint(3, 9)))
        pygame.draw.rect(screen, (180, 0, 0), (0, HEIGHT // 2 + rng.randint(-45, 45), WIDTH, rng.randint(2, 6)))

    # Tiny fake diagnostic text makes it feel like the program itself is being
    # tampered with, without adding harsh effects.
    _draw_safe_666_error_glyphs(t, rng)

    # Text stutter.
    msg = "DO NOT USE THAT CODE"
    if (t // 6) % 2 == 0:
        msg = "YOU WERE WARNED"
    if t > 130:
        msg = "666"
    title = font_title.render(msg, True, (230, 20, 20))
    shadow = font_title.render(msg, True, (0, 0, 0))
    tx = WIDTH // 2 - title.get_width() // 2 + rng.randint(-3, 3)
    ty = SCENE_TOP + 36 + rng.randint(-2, 2)
    screen.blit(shadow, (tx + 4, ty + 4))
    screen.blit(title, (tx, ty))

    sub = font_terminal.render(_T("hud.secure_console_breach_access_lev"), True, (120, 0, 0))
    screen.blit(sub, (WIDTH // 2 - sub.get_width() // 2, HEIGHT - LETTER_H - 48))

    if timer < 18:
        fade = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        fade.fill((0, 0, 0, int(255 * (1 - timer / 18))))
        screen.blit(fade, (0, 0))
    return True


def draw_safe_keypad():
    if _draw_safe_666_easter_egg():
        return
    if not STATE.safe_keypad_active:
        return
    ticks = _now_ms()
    overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
    overlay.fill((0, 0, 0, 200))
    screen.blit(overlay, (0, 0))
    panel_w, panel_h = 340, 380
    panel_x = (WIDTH - panel_w) // 2
    panel_y = (HEIGHT - panel_h) // 2
    paper = pygame.Surface((panel_w, panel_h))
    paper.fill((20, 22, 26))
    for row in range(0, panel_h, 4):
        pygame.draw.line(paper, (14, 16, 18), (0, row), (panel_w, row), 1)
    screen.blit(paper, (panel_x, panel_y))
    pygame.draw.rect(screen, C_ORANGE, (panel_x, panel_y, panel_w, panel_h), 2)
    pygame.draw.rect(
        screen, (35, 40, 45), (panel_x + 3, panel_y + 3, panel_w - 6, panel_h - 6), 1
    )
    # Silver Corner Screws with small dark grooves (mechanical detailing)
    for sx, sy in [
        (panel_x + 12, panel_y + 12),
        (panel_x + panel_w - 12, panel_y + 12),
        (panel_x + 12, panel_y + panel_h - 12),
        (panel_x + panel_w - 12, panel_y + panel_h - 12),
    ]:
        pygame.draw.circle(screen, (90, 95, 100), (sx, sy), 5)
        pygame.draw.circle(screen, (50, 52, 55), (sx, sy), 5, 1)
        pygame.draw.line(screen, (40, 42, 45), (sx - 3, sy - 1), (sx + 3, sy + 1), 1)
        
    # Blinking status LED (Green for power/ready)
    led_color = (50, 255, 100) if (ticks // 400) % 2 == 0 else (15, 80, 30)
    pygame.draw.circle(screen, led_color, (panel_x + panel_w - 32, panel_y + 16), 4)
    # LED label
    led_lbl = font_terminal_small.render(_T("hud.pwr"), True, (110, 115, 120))
    screen.blit(led_lbl, (panel_x + panel_w - 62, panel_y + 10))
    
    status_lbl = font_terminal_small.render(
        _T("hud.secure_console_access_level_1"), True, (110, 115, 120)
    )
    screen.blit(status_lbl, (panel_x + 16, panel_y + 8))
    pygame.draw.line(
        screen,
        (35, 40, 45),
        (panel_x + 10, panel_y + 24),
        (panel_x + panel_w - 10, panel_y + 24),
        1,
    )
    header = font_speaker.render(_T("hud.safe_keypad"), True, C_ORANGE)
    screen.blit(
        header, (panel_x + panel_w // 2 - header.get_width() // 2, panel_y + 28)
    )
    display_x = panel_x + 30
    display_y = panel_y + 64
    display_w = panel_w - 60
    display_h = 42
    # CRT Green background screen
    pygame.draw.rect(screen, (5, 24, 10), (display_x, display_y, display_w, display_h))
    pygame.draw.rect(
        screen, (50, 180, 100), (display_x, display_y, display_w, display_h), 1
    )
    # Draw scanlines specifically on the keypad LCD screen
    for sy in range(2, display_h, 3):
        line_y = display_y + sy
        pygame.draw.line(screen, (10, 38, 15), (display_x + 1, line_y), (display_x + display_w - 2, line_y), 1)
        
    # Pulsing cursor "_" in terminal text
    blink_cursor = "_" if (ticks // 350) % 2 == 0 else " "
    code_display = (
        STATE.safe_keypad_code + blink_cursor if len(STATE.safe_keypad_code) < 6 else STATE.safe_keypad_code
    )
    code_surf = font_terminal.render(code_display, True, (65, 255, 160))
    text_x = display_x + (display_w - code_surf.get_width()) // 2
    text_y = display_y + (display_h - code_surf.get_height()) // 2
    screen.blit(code_surf, (text_x, text_y))
    # Clue hint strip: once Biribel has read ANY desk note in the warehouse,
    # the console shows the rule in plain words under the display. Before
    # that the strip stays blank so the notes are still worth finding.
    if any(d.get("read") for d in getattr(STATE, "desks", []) or []):
        hint_surf = font_terminal_small.render(
            _T("hud.hint_last_3_7742"), True, (220, 160, 60))
        screen.blit(hint_surf, (
            panel_x + panel_w // 2 - hint_surf.get_width() // 2,
            display_y + display_h + 5))
    btn_w, btn_h = 64, 44
    gap = 10
    start_x = panel_x + (panel_w - (3 * btn_w + 2 * gap)) // 2
    btn_y_start = display_y + display_h + 30
    _keypad_buttons_ref = []
    keys_7_9 = [("7", 0), ("8", 1), ("9", 2)]
    keys_4_6 = [("4", 0), ("5", 1), ("6", 2)]
    keys_1_3 = [("1", 0), ("2", 1), ("3", 2)]
    keys_bksp_0_ent = [("DEL", 0), ("0", 1), ("ENT", 2)]
    mouse_pos = get_scaled_mouse()
    rows = [keys_7_9, keys_4_6, keys_1_3, keys_bksp_0_ent]
    for ri, row in enumerate(rows):
        for label, col in row:
            bx = start_x + col * (btn_w + gap)
            by = btn_y_start + ri * (btn_h + gap)
            rect = pygame.Rect(bx, by, btn_w, btn_h)
            hover = rect.collidepoint(mouse_pos)
            bg_color = (48, 52, 58) if hover else (26, 28, 32)
            outline_color = C_ORANGE if hover else (70, 75, 80)
            pygame.draw.rect(screen, bg_color, rect, border_radius=3)
            pygame.draw.rect(screen, outline_color, rect, 1, border_radius=3)
            text_color = C_WHITE if hover else (180, 190, 200)
            lbl = (
                font_terminal_small.render(label, True, text_color)
                if len(label) > 1
                else font_terminal.render(label, True, text_color)
            )
            lbl_x = bx + (btn_w - lbl.get_width()) // 2
            lbl_y = by + (btn_h - lbl.get_height()) // 2
            screen.blit(lbl, (lbl_x, lbl_y))
            _keypad_buttons_ref.append((rect, label))
    handle_keypad_click._buttons = _keypad_buttons_ref
    hint = font_terminal_small.render(_T("hud.esc_cancel"), True, (120, 110, 90))
    screen.blit(
        hint, (panel_x + panel_w // 2 - hint.get_width() // 2, panel_y + panel_h - 22)
    )
def handle_keypad_click(pos):
    if not STATE.safe_keypad_active:
        return
    buttons = getattr(handle_keypad_click, "_buttons", [])
    for rect, label in buttons:
        if rect.collidepoint(pos):
            if label == "ENT":
                _play_ui_type_tick(0.09)
                _submit_safe_keypad_code()
            elif label == "DEL":
                if len(STATE.safe_keypad_code) > 0:
                    STATE.safe_keypad_code = STATE.safe_keypad_code[:-1]
                    _play_ui_type_tick(0.09)
            elif len(STATE.safe_keypad_code) < 6:
                STATE.safe_keypad_code += label
                _play_ui_type_tick(0.10)
def handle_keypad_keypress(key):
    if not STATE.safe_keypad_active:
        return
    if key == pygame.K_RETURN or key == pygame.K_KP_ENTER:
        _play_ui_type_tick(0.09)
        _submit_safe_keypad_code()
    elif key == pygame.K_BACKSPACE:
        if len(STATE.safe_keypad_code) > 0:
            STATE.safe_keypad_code = STATE.safe_keypad_code[:-1]
            _play_ui_type_tick(0.09)
    elif pygame.K_0 <= key <= pygame.K_9:
        if len(STATE.safe_keypad_code) < 6:
            STATE.safe_keypad_code += chr(key)
            _play_ui_type_tick(0.10)
    elif pygame.K_KP0 <= key <= pygame.K_KP9:
        if len(STATE.safe_keypad_code) < 6:
            STATE.safe_keypad_code += chr(key - pygame.K_KP0 + ord("0"))
            _play_ui_type_tick(0.10)


def _crosshair_color():
    """Pick a reticle color that survives common colorblind modes."""
    from core.user_settings import SETTINGS
    return _crosshair.color_for(SETTINGS.colorblind_mode, default=C_WHITE)


# The reticle is an AIMING aid, so it belongs to the states where you aim.
# Everything else is a pointer-driven screen and gets the custom arrow instead
# (ui.main.draw_menu_cursor) or nothing at all (cinematics, boot bumper).
#
# Keep this in step with _CURSOR_ARROW_STATES in ui/main.py: the two sets are
# disjoint and together they decide which of the two cursors a state shows.
# Note the missions draw their own orange combat reticle during GAME/WALK
# (m1/draw.py, m2/draw.py, walking_sim.py); this shared reticle is the
# fallback, and only actually paints when the OS pointer is visible - see
# rule 3 below, which is what stops it double-drawing over those.
_CROSSHAIR_AIM_STATES = frozenset({"GAME", "WALK"})


def draw_crosshair(surface=None, state_name=None):
    """Draw the player-aim reticle, for aiming states only.

    Single call site: the main loop, after the state's own render pass and
    before the dev tools / transition fade (see acaristan.py).

    Menus and overlays deliberately get NO reticle - they use the custom arrow
    cursor instead (ui.main.draw_menu_cursor). An aim reticle and a pointer
    arrow on the same screen just read as two competing cursors.

    Rules, in order:
      1. SETTINGS.show_crosshair must be on (Gameplay tab → Crosshair).
      2. Dead players get nothing.
      3. Only GAME / WALK are aiming states.
      4. The OS pointer must be visible. Gameplay hides it, which is what keeps
         this fallback reticle from double-drawing over the per-mission combat
         reticles (m1/m2/walking_sim) - they are the ones you normally see. It
         also covers overlays that stash the mouse (safe keypad, notes, intel
         cards). Exceptions where the pointer is visible during GAME, e.g. the
         level editor, do get it.
      5. Safe-keypad / read-note overlays suppress it explicitly.
      6. Mid-transition and during the upload-OS the reticle is skipped - the
         fade blacks the screen out anyway, and suppressing it also stops the
         per-shot `crosshair_kick` decay from draining behind a fade.

    Safe to call every frame on any state; bails out instantly if disabled.
    """
    from core.user_settings import SETTINGS

    if surface is None:
        surface = screen

    if not SETTINGS.show_crosshair:
        return
    if STATE.player_dead:
        return
    if not pygame.mouse.get_visible():
        return
    # Suppress while UI overlays own the mouse (keypad, notes, etc.)
    if STATE.safe_keypad_active or STATE.active_read_note:
        return

    if state_name is None:
        import app as _app
        state_name = getattr(getattr(_app, "gsm", None), "current_name", "")

    if state_name not in _CROSSHAIR_AIM_STATES:
        return

    import app as _app
    if getattr(_app, "gsm", None) is not None and _app.gsm.transitioning:
        return
    if state_name == "GAME":
        try:
            from ui import upload_os
            if upload_os.is_upload_os_active():
                return
        except ImportError:
            pass

    col = _crosshair_color()
    cx, cy = get_scaled_mouse()
    size = max(3, int(SETTINGS.crosshair_size))
    # Crosshair kick: arms spread briefly after each shot (set in
    # weapons.handle_shoot) so the trigger pull reads on the reticle.
    kick = max(0, int(getattr(STATE, "crosshair_kick", 0)))
    _crosshair.draw(surface, cx, cy, size=size, color=col, kick=kick)
    if kick > 0:
        STATE.crosshair_kick = max(0, kick - 1)


def draw_gameplay_crosshair(surface=None, state_name="GAME"):
    """Live-play reticle. Thin alias for draw_crosshair().

    Kept because per-mission reticles (m1/m2/walking_sim) reference it by name
    in their own comments, and external callers used it as the "in gameplay"
    entry point.
    """
    draw_crosshair(surface, state_name if state_name else "GAME")


def draw_combat_reticle(surface=None, require_player=True):
    """Orange combat reticle for mission renderers (M3 uses this).

    The shape lives in ``engine.ui.std.crosshair``; M1/M2/walking_sim used to
    inline their own copies of this exact shape and now call the same widget
    (each keeps its own gating conditions). Honors SETTINGS.show_crosshair,
    crosshair_size and colorblind_mode like the others. Skips dead/missing
    players.

    Unlike draw_crosshair() above, this paints regardless of OS-pointer
    visibility - mission renderers call it during gameplay when the pointer
    is hidden, which is exactly when draw_crosshair() bails to avoid
    double-drawing over them.

    ``require_player`` gates the reticle on ``STATE.player``/``STATE.player_dead``.
    That is a MISSION concept: the multiplayer arena has no ``STATE.player``
    (it is always None there), so leaving it on made the arena call return
    early every frame and draw no crosshair at all. The arena passes False
    and supplies its own liveness check from the snapshot.
    """
    from core.user_settings import SETTINGS

    if surface is None:
        surface = screen
    try:
        if not SETTINGS.show_crosshair:
            return
    except Exception:
        pass
    if require_player and (STATE.player is None or STATE.player_dead):
        return
    try:
        cb = SETTINGS.colorblind_mode
    except Exception:
        cb = "none"
    col = _crosshair.color_for(cb, default=C_ORANGE)
    try:
        size = max(3, int(SETTINGS.crosshair_size))
    except Exception:
        size = 6
    ch_x, ch_y = get_scaled_mouse()
    _crosshair.draw_combat(surface, ch_x, ch_y, size=size, color=col)


# ─────────────────────────────────────────────────────────────
# Shared HUD layout helpers - used by both mission.py and mission2.py.
# ─────────────────────────────────────────────────────────────
# These two pieces had drifted between missions:
#   - Objective panel: M1 width=450 at (20, LETTER_H+10); M2 width=620 same anchor.
#     M1 stored the "OBJECTIVE:" prefix in the variable; M2 prepended it at render.
#   - Pinned radio text: M1 stacked ALL pinned messages at bottom-left; M2 stacked
#     only the last 2 at top-right.
# We unify on: panel width=520 (compromise), prefix prepended at render,
# radio text rendered at bottom-left (M1's position) and capped to last 4
# (compromise: M1's "show all" could overflow; M2's "last 2" dropped too much).

# Phase 4 (A-009): the panel constants moved to engine.ui.std.objective_banner
# (DEFAULT_PANEL_WIDTH / DEFAULT_PANEL_HEIGHT).
PINNED_RADIO_MAX_VISIBLE = 2


def draw_objective_panel(surface, text, x=20, y=None):
    """Draw the OBJECTIVE banner at the top of the screen.

    Body moved to ``engine.ui.std.objective_banner`` (A-009 shim); long
    objectives still wrap inside the panel instead of overflowing the map.
    """
    return _objective_banner.draw(surface, text, THEME, x=x, y=y)


def draw_pinned_radio(surface, pinned_texts=None, x=20):
    """Draw the radio transmission widget (polish pass T6).

    Kept under its old name so every mission HUD keeps one call site. Radio
    lines are no longer floating-text "pin" entries: the widget reads the
    live line from the radio director (core.interactions.live_line) and
    runs on the pause-aware radio clock. ``pinned_texts`` and ``x`` are
    accepted for back-compat and ignored.
    """
    from ui.radio import draw_radio
    return draw_radio(surface)
