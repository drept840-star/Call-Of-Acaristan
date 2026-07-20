# ------------------------------------------------------------
# ui_hud.py
# ------------------------------------------------------------

# ------------------------------------------------------------
# ui_hud.py
# ------------------------------------------------------------

"""HUD overlays: minimap, safe keypad, notebook inspection, desk notes."""
import math
import random
import pygame
_last_note_tick_key = None
from config import (
    WIDTH, HEIGHT, TILE_SIZE, FLOOR_TILE_SIZE,
    C_WHITE, C_ORANGE, C_TERMINAL, C_KRAP_BLUE, C_GREY,
    C_BG_GAME, LETTER_H, SCENE_TOP, SCENE_BOT,
    font_terminal, font_terminal_small, font_speaker,
    font_btn, font_prompt, font_dialogue, font_title, screen,
    CONTAINER_TILE_RED, CONTAINER_TILE_BLUE, CONTAINER_TILE_RUST, CONTAINER_TILE_GREY,
    audio, get_scaled_mouse,
)
from state import STATE
class MiniMap:
    def __init__(self, map_data, tile_size=64):
        self.tile_size = tile_size
        self.map_w = len(map_data[0])
        self.map_h = len(map_data)
        self.world_w = self.map_w * tile_size
        self.world_h = self.map_h * tile_size
        self.minimap_w = 160
        self.minimap_h = 160
        self.scale_x = self.minimap_w / self.world_w
        self.scale_y = self.minimap_h / self.world_h
        self.margin = 10
        self.x = WIDTH - self.minimap_w - self.margin
        self.y = self.margin
        self.static_surface = self._build_static_surface(map_data)
    def _build_static_surface(self, map_data):
        surf = pygame.Surface((self.minimap_w, self.minimap_h), pygame.SRCALPHA)
        surf.fill((10, 10, 12, 220))

        # Per-tile colors. Sourced from mission2.py's tile_base palette +
        # mission1's wall/door convention so the minimap visually matches the
        # main renderer instead of looking like a black void.
        #
        # Floor zones (lower brightness — these are the "ground" the player
        # walks on, so they should read as background, not structure).
        floor_color = {
            ".": (32, 33, 33),   # wet asphalt / highway
            "g": (40, 36, 32),   # muddy shoulder
            "d": (29, 35, 34),   # drainage ditch
            "s": (34, 37, 35),   # service road
            "O": (29, 36, 38),   # interior / control sector
            "K": (45, 48, 52),   # kitchen / utility
            "L": (34, 42, 44),   # laundry
            "Y": (45, 45, 42),   # exercise yard
            "M": (31, 34, 32),   # maintenance
            "E": (29, 48, 36),   # service exit / exit zone
            "X": (29, 38, 32),   # exfil pad
            "T": (50, 40, 32),   # tanker footprint (dark amber)
        }
        # Solid structure (walls + barriers + cover) — brighter so it pops
        # against the floor and gives the minimap actual shape.
        wall_color = (78, 75, 70)    # C — perimeter + building walls
        door_color = (110, 95, 70)   # D — doors (was unreachable before)
        barrier_color = (92, 82, 70) # B — barriers / cover
        interior_wall_color = (60, 58, 55)

        for row_idx, row in enumerate(map_data):
            for col_idx, tile in enumerate(row):
                px = int(col_idx * self.tile_size * self.scale_x)
                py = int(row_idx * self.tile_size * self.scale_y)
                pw = max(1, int(self.tile_size * self.scale_x))
                ph = max(1, int(self.tile_size * self.scale_y))
                if tile in ("C", "W"):
                    pygame.draw.rect(surf, wall_color, (px, py, pw, ph))
                elif tile == "D":
                    pygame.draw.rect(surf, door_color, (px, py, pw, ph))
                elif tile == "B":
                    pygame.draw.rect(surf, barrier_color, (px, py, pw, ph))
                elif tile == "T":
                    pygame.draw.rect(surf, floor_color["T"], (px, py, pw, ph))
                elif tile in floor_color:
                    pygame.draw.rect(surf, floor_color[tile], (px, py, pw, ph))
                # "P", "E", "K", "V", "N" etc. are entity spawn markers —
                # they live on floor tiles and don't need their own minimap
                # representation (the entity itself draws on the minimap).
        return surf
    def draw(
        self,
        surface,
        player,
        enemies,
        camera_x,
        camera_y,
        notebook_pos=None,
        exfil_pos=None,
        volkov_pos=None,
        commander_pos=None,
        ipa_truck_pos=None,
        tanker_pos=None,
        shelter_pos=None,
        service_door_pos=None,
        smg_pos=None,
    ):
        if player is None:
            return
        panel = self.static_surface.copy()
        px = int(player.rect.centerx * self.scale_x)
        py = int(player.rect.centery * self.scale_y)
        pygame.draw.circle(panel, (80, 220, 100), (px, py), 3)
        angle = player.angle
        dir_len = 6
        dx = int(math.cos(angle) * dir_len)
        dy = int(math.sin(angle) * dir_len)
        pygame.draw.line(panel, (80, 220, 100), (px, py), (px + dx, py + dy), 2)
        for e in enemies:
            ex = int(e.rect.centerx * self.scale_x)
            ey = int(e.rect.centery * self.scale_y)
            pygame.draw.circle(panel, (220, 60, 60), (ex, ey), 2)

        # ── Service-door marker + directional arrow ──
        # Shown after all cell-block guards are dead so the player can find the
        # exit. Clamp the marker to the panel edge if it's off-screen, and draw
        # an arrow from the player toward it.
        if service_door_pos:
            tx = int(service_door_pos[0] * self.scale_x)
            ty = int(service_door_pos[1] * self.scale_y)
            # Keep the target marker inside the panel so the arrow always reads.
            tx_c = max(4, min(self.minimap_w - 4, tx))
            ty_c = max(4, min(self.minimap_h - 4, ty))
            # Marker: hollow green diamond (exit).
            door_col = (80, 230, 120)
            pygame.draw.polygon(panel, door_col, [
                (tx_c, ty_c - 5), (tx_c + 5, ty_c),
                (tx_c, ty_c + 5), (tx_c - 5, ty_c),
            ], 1)
            pygame.draw.polygon(panel, (200, 255, 210), [
                (tx_c, ty_c - 5), (tx_c + 5, ty_c),
                (tx_c, ty_c + 5), (tx_c - 5, ty_c),
            ])
            # Arrow from player to door.
            adx = tx_c - px
            ady = ty_c - py
            dist = math.hypot(adx, ady)
            if dist > 1:
                ux = adx / dist
                uy = ady / dist
                # Arrow point sits a bit short of the door marker.
                ax, ay = tx_c - int(ux * 9), ty_c - int(uy * 9)
                pygame.draw.line(panel, door_col, (px, py), (ax, ay), 2)
                # Arrowhead.
                left = (ax - int(ux * 6) - int(uy * 4), ay - int(uy * 6) + int(ux * 4))
                right = (ax - int(ux * 6) + int(uy * 4), ay - int(uy * 6) - int(ux * 4))
                pygame.draw.polygon(panel, door_col, [(ax, ay), left, right])

        # ── K-9 SMG marker ──
        # Shown (cyan) until the player picks up the K-9; pass smg_pos=None
        # once acquired to unmark it.
        if smg_pos:
            kx = int(smg_pos[0] * self.scale_x)
            ky = int(smg_pos[1] * self.scale_y)
            kx = max(3, min(self.minimap_w - 3, kx))
            ky = max(3, min(self.minimap_h - 3, ky))
            smg_col = (150, 210, 255)
            pygame.draw.rect(panel, smg_col, (kx - 3, ky - 2, 6, 4), 1)
            pygame.draw.rect(panel, (220, 245, 255), (kx - 3, ky - 2, 6, 4))
        if notebook_pos:
            nx = int(notebook_pos[0] * self.scale_x)
            ny = int(notebook_pos[1] * self.scale_y)
            pygame.draw.rect(panel, (255, 220, 100), (nx - 3, ny - 3, 6, 6))
            pygame.draw.rect(panel, (255, 255, 255), (nx - 3, ny - 3, 6, 6), 1)
        if exfil_pos:
            ex = int(exfil_pos[0] * self.scale_x)
            ey = int(exfil_pos[1] * self.scale_y)
            pygame.draw.circle(panel, (80, 220, 100), (ex, ey), 4, 1)
        if volkov_pos:
            vx = int(volkov_pos[0] * self.scale_x)
            vy = int(volkov_pos[1] * self.scale_y)
            pygame.draw.circle(panel, (255, 160, 60), (vx, vy), 3)
        if commander_pos:
            cx = int(commander_pos[0] * self.scale_x)
            cy = int(commander_pos[1] * self.scale_y)
            pygame.draw.circle(panel, (255, 160, 60), (cx, cy), 3)
        # IPA truck — the central objective in M2's inspect phase. Drawn as
        # a filled orange square so it stands out from the floor zones.
        if ipa_truck_pos:
            tx = int(ipa_truck_pos[0] * self.scale_x)
            ty = int(ipa_truck_pos[1] * self.scale_y)
            pygame.draw.rect(panel, (220, 130, 60), (tx - 3, ty - 3, 6, 6))
            pygame.draw.rect(panel, (255, 220, 160), (tx - 3, ty - 3, 6, 6), 1)
        # Tanker — drawn hollow while intact, removed by the caller after the
        # blast (just pass None once STATE.mission2_tanker_rect is gone).
        if tanker_pos:
            tx = int(tanker_pos[0] * self.scale_x)
            ty = int(tanker_pos[1] * self.scale_y)
            pygame.draw.rect(panel, (255, 90, 50), (tx - 4, ty - 3, 8, 6), 1)
        # Shelter / safe zone — drawn as a small blue house icon (square body
        # + triangular roof) so the player can find the bunker during the
        # tanker countdown. Mission 2 passes shelter_pos=SAFE_ZONE during
        # STAGE_TANKER and STAGE_RUN; other stages pass None and the icon
        # doesn't render. The blue color matches the in-world "RUN HERE"
        # marker (C_VASILE = 100, 160, 220) for consistency.
        if shelter_pos:
            sx = int(shelter_pos[0] * self.scale_x)
            sy = int(shelter_pos[1] * self.scale_y)
            shelter_col = (100, 160, 220)
            # House body (4x4 square)
            pygame.draw.rect(panel, shelter_col, (sx - 2, sy - 1, 4, 4))
            # Roof (triangle on top)
            pygame.draw.polygon(panel, shelter_col, [
                (sx - 3, sy - 1), (sx + 3, sy - 1), (sx, sy - 4),
            ])
            # White outline for visibility against dark minimap bg
            pygame.draw.rect(panel, (255, 255, 255), (sx - 2, sy - 1, 4, 4), 1)
            pygame.draw.polygon(panel, (255, 255, 255), [
                (sx - 3, sy - 1), (sx + 3, sy - 1), (sx, sy - 4),
            ], 1)
        pygame.draw.rect(panel, (90, 75, 45), (0, 0, self.minimap_w, self.minimap_h), 2)
        pygame.draw.rect(
            panel, (55, 45, 28), (1, 1, self.minimap_w - 2, self.minimap_h - 2), 1
        )
        surface.blit(panel, (self.x, self.y))
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
    if (pygame.time.get_ticks() // 600) % 2 == 0:
        prompt = font_prompt.render("[ SPACE ] close", True, (160, 145, 100))
        screen.blit(prompt, (WIDTH // 2 - prompt.get_width() // 2, HEIGHT // 2 + 210))
    lbl = font_terminal_small.render("crumpled scrap", True, (95, 82, 58))
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
        shade = random.randint(-3, 3)
        c = max(0, min(255, 32 + shade))
        pygame.draw.line(paper, (c, c - 2, c - 4), (0, row), (panel_w, row))
    screen.blit(paper, (panel_x, panel_y))
    pygame.draw.rect(screen, (80, 70, 50), (panel_x, panel_y, panel_w, panel_h), 2)
    header = font_speaker.render("FIELD NOTE", True, C_ORANGE)
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
    if (pygame.time.get_ticks() // 600) % 2 == 0:
        prompt = font_prompt.render("[ SPACE ] close", True, (160, 145, 100))
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
        shade = random.randint(-3, 3)
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
    stamp_txt = font_speaker.render("CLASSIFIED", True, (180, 30, 30, stamp_alpha))
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
        "OPERATION BLACK NOTEBOOK // FIELD INTELLIGENCE DOSSIER // EYES ONLY",
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
    map_hdr = font_terminal_small.render("[ OPERATIONAL MAP ]", True, (160, 130, 60))
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
    tgt_hdr = font_terminal_small.render("[ TARGET PHOTO ]", True, (160, 130, 60))
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
    photo_lbl = font_terminal_small.render("SEBASTIAN VOLKOV", True, (200, 180, 100))
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
    ev_hdr = font_terminal_small.render("[ EVIDENCE LOG ]", True, (160, 130, 60))
    screen.blit(ev_hdr, (rx, ry))
    pygame.draw.line(
        screen, (80, 65, 35), (rx, ry + 16), (panel_x + panel_w - 20, ry + 16), 1
    )
    ry += 24
    evidence = [
        ("ITEM", "Black notebook, leather, unmarked"),
        ("CONTENTS", "FuegoTech serial registry"),
        ("SERIALS", "FT-7742 FT-7743 FT-7744 FT-7745"),
        ("CROSS-REF", "IPA procurement #8841\u20138844"),
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
    q1 = font_terminal_small.render('"The fire burns both ways."', True, (140, 120, 80))
    q2 = font_terminal_small.render("\u2014 Cmdr.", True, (110, 95, 60))
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
        "KRAP INTELLIGENCE DIVISION // FIELD COPY \u2014 DO NOT DUPLICATE",
        True,
        (80, 70, 45),
    )
    screen.blit(
        footer,
        (panel_x + panel_w // 2 - footer.get_width() // 2, panel_y + panel_h - 26),
    )
    if (pygame.time.get_ticks() // 600) % 2 == 0:
        prompt = font_prompt.render("[ SPACE ] close", True, (160, 145, 100))
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
                snd = pygame.mixer.Sound(path)
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
    STATE.safe_666_seed = random.randint(1, 999999)
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

    # Central apparition — elongated mask, pinhole eyes, crooked mouth.
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
            s_txt = rng.choice(["666", "VI VI VI", "ƧƧƧ", "†", "††"])
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

    sub = font_terminal.render("SECURE CONSOLE BREACH // ACCESS LEVEL 6", True, (120, 0, 0))
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
    ticks = pygame.time.get_ticks()
    overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
    overlay.fill((0, 0, 0, 200))
    screen.blit(overlay, (0, 0))
    panel_w, panel_h = 340, 360
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
    led_lbl = font_terminal_small.render("PWR", True, (110, 115, 120))
    screen.blit(led_lbl, (panel_x + panel_w - 62, panel_y + 10))
    
    status_lbl = font_terminal_small.render(
        "SECURE CONSOLE - ACCESS LEVEL 1", True, (110, 115, 120)
    )
    screen.blit(status_lbl, (panel_x + 16, panel_y + 8))
    pygame.draw.line(
        screen,
        (35, 40, 45),
        (panel_x + 10, panel_y + 24),
        (panel_x + panel_w - 10, panel_y + 24),
        1,
    )
    header = font_speaker.render("SAFE KEYPAD", True, C_ORANGE)
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
    btn_w, btn_h = 64, 44
    gap = 10
    start_x = panel_x + (panel_w - (3 * btn_w + 2 * gap)) // 2
    btn_y_start = display_y + display_h + 16
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
    hint = font_terminal_small.render("[ESC] cancel", True, (120, 110, 90))
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


def draw_gameplay_crosshair():
    """Draw the player-aim crosshair at the current mouse position.

    Reads from the shared SETTINGS singleton:
      - SETTINGS.show_crosshair  — toggle
      - SETTINGS.crosshair_size  — 3/6/10 px half-extent
      - SETTINGS.colorblind_mode — recolors the reticle for accessibility

    Safe to call every frame; bails out instantly if disabled.
    """
    from user_settings import SETTINGS
    if not SETTINGS.show_crosshair:
        return
    if STATE.player_dead:
        return
    # Suppress while UI overlays own the mouse (keypad, notes, etc.)
    if STATE.safe_keypad_active or STATE.active_read_note:
        return

    # Pick a color that survives common colorblind modes.
    cb = SETTINGS.colorblind_mode
    if cb == "protanopia":
        col = (90, 180, 255)   # blue reads well for red-deficient vision
    elif cb == "deuteranopia":
        col = (255, 220, 80)   # yellow
    elif cb == "tritanopia":
        col = (255, 120, 120)  # pinkish-red
    else:
        col = C_WHITE

    cx, cy = get_scaled_mouse()
    size = max(3, int(SETTINGS.crosshair_size))
    gap = max(2, size // 2)
    arm = size + gap + 2

    # Center dot
    pygame.draw.rect(screen, col, (cx - 1, cy - 1, 2, 2))
    # Four arms
    pygame.draw.line(screen, col, (cx - arm, cy), (cx - gap, cy), 1)
    pygame.draw.line(screen, col, (cx + gap, cy), (cx + arm, cy), 1)
    pygame.draw.line(screen, col, (cx, cy - arm), (cx, cy - gap), 1)
    pygame.draw.line(screen, col, (cx, cy + gap), (cx, cy + arm), 1)


# ─────────────────────────────────────────────────────────────
# Shared HUD layout helpers — used by both mission.py and mission2.py.
# ─────────────────────────────────────────────────────────────
# These two pieces had drifted between missions:
#   - Objective panel: M1 width=450 at (20, LETTER_H+10); M2 width=620 same anchor.
#     M1 stored the "OBJECTIVE:" prefix in the variable; M2 prepended it at render.
#   - Pinned radio text: M1 stacked ALL pinned messages at bottom-left; M2 stacked
#     only the last 2 at top-right.
# We unify on: panel width=520 (compromise), prefix prepended at render,
# radio text rendered at bottom-left (M1's position) and capped to last 4
# (compromise: M1's "show all" could overflow; M2's "last 2" dropped too much).

OBJECTIVE_PANEL_WIDTH = 520
OBJECTIVE_PANEL_HEIGHT = 30
PINNED_RADIO_MAX_VISIBLE = 4


def draw_objective_panel(surface, text, x=20, y=None):
    """Draw the OBJECTIVE banner at the top of the screen.

    Long objectives are wrapped inside the panel instead of overflowing across
    the map. Keeps older short objectives as the same one-line banner.
    """
    if y is None:
        y = LETTER_H + 10

    panel_w = min(WIDTH - x - 20, max(OBJECTIVE_PANEL_WIDTH, 620))
    pad_x = 10
    line_gap = 3
    max_text_w = panel_w - pad_x * 2

    full = "OBJECTIVE: " + str(text)
    words = full.split(" ")
    lines = []
    cur = ""
    for word in words:
        test = word if not cur else cur + " " + word
        if font_prompt.size(test)[0] <= max_text_w:
            cur = test
        else:
            if cur:
                lines.append(cur)
                cur = word
            else:
                # Extremely long single token: trim defensively.
                trimmed = word
                while trimmed and font_prompt.size(trimmed + "…")[0] > max_text_w:
                    trimmed = trimmed[:-1]
                lines.append(trimmed + "…")
                cur = ""
    if cur:
        lines.append(cur)

    # Don't let an objective panel become a paragraph. Mission code should keep
    # text concise; this clamps the UI to two readable lines.
    if len(lines) > 2:
        second = lines[1]
        while second and font_prompt.size(second + "…")[0] > max_text_w:
            second = second[:-1]
        lines = [lines[0], second + "…"]

    line_h = font_prompt.get_height()
    panel_h = max(OBJECTIVE_PANEL_HEIGHT, 14 + len(lines) * line_h + (len(lines) - 1) * line_gap)
    bg = pygame.Surface((panel_w, panel_h), pygame.SRCALPHA)
    pygame.draw.rect(bg, (0, 0, 0, 150), (0, 0, panel_w, panel_h))
    pygame.draw.line(bg, C_KRAP_BLUE, (0, 0), (0, panel_h), 3)
    surface.blit(bg, (x, y))

    for i, line in enumerate(lines):
        obj_surf = font_prompt.render(line, True, C_WHITE)
        surface.blit(obj_surf, (x + pad_x, y + 7 + i * (line_h + line_gap)))


def draw_pinned_radio(surface, pinned_texts, x=20):
    """Render pinned radio chatter at the bottom-left of the screen.

    Args:
        surface: target Surface.
        pinned_texts: list of floating-text tuples (any iterable of length>=6
            where index 2 is the message string and index 3 is the RGB color
            and index 4 is the remaining life in frames). Already filtered to
            ``ft[5] == "pin"`` by the caller.
        x: left edge. Default 20.

    Renders up to ``PINNED_RADIO_MAX_VISIBLE`` most recent messages, stacked
    upward from ``HEIGHT - 260`` (so newer messages appear at the top of the
    stack and older ones scroll down and out).

    Long messages are word-wrapped to fit within ``WIDTH - x - 20`` pixels so
    they never overflow the right edge of the screen.
    """
    if not pinned_texts:
        return
    visible = list(pinned_texts)[-PINNED_RADIO_MAX_VISIBLE:]
    base_y = HEIGHT - 260
    max_width = WIDTH - x - 20  # 20px right margin
    for i, ft in enumerate(visible):
        alpha = min(255, ft[4] * 3)
        color = ft[3]
        message = ft[2]

        # ── Word-wrap the message to fit within max_width ──
        # Splits on spaces; accumulates words until adding the next would
        # exceed max_width, then starts a new line.
        words = message.split(' ')
        lines = []
        current_line = ""
        for word in words:
            test = current_line + (" " if current_line else "") + word
            test_w = font_terminal_small.size(test)[0]
            if test_w > max_width and current_line:
                lines.append(current_line)
                current_line = word
            else:
                current_line = test
        if current_line:
            lines.append(current_line)

        # Render each line and stack vertically.
        line_h = font_terminal_small.get_height()
        total_h = len(lines) * line_h + 6
        bg = pygame.Surface((max_width + 16, total_h), pygame.SRCALPHA)
        pygame.draw.rect(bg, (0, 0, 0, min(180, alpha)), bg.get_rect())
        pygame.draw.line(
            bg,
            (color[0], color[1], color[2], min(200, alpha)),
            (0, 0),
            (0, bg.get_height()),
            3,
        )
        for li, line in enumerate(lines):
            txt_surf = font_terminal_small.render(line, True, color)
            faded = pygame.Surface(txt_surf.get_size(), pygame.SRCALPHA)
            faded.blit(txt_surf, (0, 0))
            faded.set_alpha(alpha)
            bg.blit(faded, (8, 3 + li * line_h))

        row_y = base_y + i * (total_h + 8)
        surface.blit(bg, (x, row_y - 3))
