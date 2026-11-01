"""Mission 7 beat 2: Bodi's escaped goat.

Replaces the old chores (generator, water, feed); defensive preparation
is unchanged.

The farm keeps columns 0..14 and an orchard extends east to column 23,
so this beat scrolls. Everything east of the ditch is cut from the world
(and the camera is stopped at the ditch) until Bodi reaches his last
outbound waypoint, then a short cinematic reveals it.

Gameplay coordinates are world pixels; the camera is render-only.

Controls:
    WASD / arrows       Walk
    Shift               Move carefully near the goat
    E                   Interact / advance dialogue
    Hold E              Grip the fence post during repair
    A / D, arrows       Counter the post's lean while repairing
    Space / Enter       Advance dialogue
    Space / Enter       Cinch the wire (repair step 2)

There is no failure:
    Startling the goat only moves it a little farther away.
    Losing balance or releasing E pauses repair progress without
    resetting it.
"""

import math
import random

import pygame

from core.config import HEIGHT, WIDTH, font_prompt
from core.state import STATE
from engine.core import now_ms

from . import maps as M


T = M.TILE
OX, OY = M.ORIGIN

WORLD_COLS = 24
WORLD_ROWS = M.ROWS

WALK_SPEED = 180.0
CAREFUL_SPEED = 65.0
BODI_SPEED = 105.0
GOAT_SPEED = 100.0
SPOOK_SPEED = 105.0

# Repair, step 1: set the post. Seconds of steady holding needed.
SET_S = 2.2
POST_SAFE_LEAN = 0.24
POST_TILT_PX = 9.0
CENTER_BAND = 0.10        # lean inside this sets the post faster

# Gusts (telegraphed, then a short push).
GUST_FORCE = 4.4
GUST_WARN_S = 0.9
GUST_BLOW_S = 0.7

# Repair, step 2: wrap the wire.
WRAPS = 3
WRAP_GOOD = 0.22          # half-width of the green zone (marker is -1..1)
WRAP_PERFECT = 0.08
WRAP_ASSIST = 0.10        # extra width after two misses in a row

# Repair presentation.
REPAIR_FINISH_MS = 650
REPAIR_ANIM_FPS = 12.0
REPAIR_SPRITE_CACHE_LIMIT = 256

YARD_GATE = (14, 5)
BROKEN_FENCE = (13, 6)

POST = pygame.Vector2(13.5 * T, 6.0 * T)
DITCH_GOAT = pygame.Vector2(20.6 * T, 5.5 * T)
OVERLOOK = pygame.Vector2(7.5 * T, 8.1 * T)

OUTBOUND = (
    (7.5, 4.5),
    (9.5, 4.5),
    (11.5, 4.5),
    (11.5, 5.5),
    (14.5, 5.5),
    (16.3, 5.5),
    (17.5, 4.5),
    (18.5, 4.5),
)

FLANK = (
    (18.5, 5.5),
    (20.0, 5.5),
    (20.3, 6.5),
)

HOMEWARD = (
    (20.0, 5.5),
    (18.0, 5.5),
    (16.0, 5.5),
    (14.5, 5.5),
    (13.5, 5.5),
    (13.5, 6.5),
    (12.8, 8.0),
)

TO_OVERLOOK = (
    (13.5, 5.5),
    (11.5, 5.5),
    (11.5, 4.5),
    (7.5, 4.5),
    (7.5, 7.6),
    (7.5, 8.1),
)

TREES = (
    (15.8, 2.0),
    (17.3, 2.0),
    (18.5, 2.2),
    (21.0, 2.1),
    (22.5, 2.0),
    (16.0, 7.7),
    (17.5, 8.0),
    (21.2, 8.0),
    (22.5, 7.7),
)

DITCH_X = int(19.2 * T)
DITCH_W = int(0.55 * T)

# Nothing east of this is shown (and the camera never scrolls past it)
# until the reveal.
CUT_X = DITCH_X

# Reveal cinematic timing (seconds) and look.
REVEAL_BARS_S = 0.9          # letterbox bars slide in
REVEAL_PAN_S = 2.8           # camera glides to the goat
REVEAL_WIPE_DELAY = 0.4      # wipe starts a beat after the pan
REVEAL_WIPE_S = 2.6          # time for the wipe to cross the cut area
REVEAL_HOLD_MIN_S = 0.8      # minimum hold once Bodi has spoken
REVEAL_RETURN_S = 1.8        # camera eases back to the player
REVEAL_BAR_H = 64
REVEAL_FADE_W = 160          # soft fog edge on the wipe
REVEAL_GLOW_W = 140          # warm light band on the wipe
REVEAL_MOTE_RATE = 60.0      # light motes per second along the edge
REVEAL_CAPTION = "EAST ORCHARD"

TREE_CANVAS = (96, 96)
TREE_ANCHOR = (44, 78)
TREE_SCALE = 2

TRACK_LINES = {
    1: [
        ("BODI", "There. Hoofprints. And half a potato plant."),
        ("BIRIBEL", "You can tell which goat?"),
        ("BODI", "The one that isn't in the pen."),
    ],
    3: [
        ("BODI", "Well's there. Don't leave the bucket on the edge."),
        ("BIRIBEL", "Wasn't planning to."),
        ("BODI", "Nobody ever is."),
    ],
    5: [
        (
            "BODI",
            "Road runs below the orchard. You hear engines "
            "before you see anything.",
        ),
        ("BIRIBEL", "Useful."),
        ("BODI", "Usually just means someone's bringing a bill."),
    ],
}

OBJECTIVES = {
    "outbound": "FOLLOW BODI - LOOK FOR HOOFPRINTS",
    "reveal": "",
    "approach": "APPROACH FROM THE NORTH - HOLD SHIFT",
    "herd": "STAY WITH THE GOAT - GUIDE HER HOME",
    "repair": "RETURN TO THE BROKEN POST",
    "repairing": "HOLD E TO GRIP - A / D TO STEADY THE POST",
    "repair_talk": "TALK WITH BODI",
    "overlook": "WALK WITH BODI - STAY OR HEAD BACK",
    "bike": "LISTEN",
}

GOAT_COLOR = (226, 220, 206)

TREE_PALETTES = (
    (
        (28, 43, 28),
        (39, 59, 34),
        (50, 76, 39),
        (64, 91, 45),
        (80, 107, 52),
        (101, 124, 63),
        (125, 143, 78),
    ),
    (
        (30, 43, 27),
        (44, 59, 32),
        (57, 75, 37),
        (72, 91, 42),
        (89, 106, 49),
        (110, 123, 61),
        (133, 142, 77),
    ),
    (
        (25, 43, 31),
        (35, 60, 38),
        (45, 77, 44),
        (58, 93, 49),
        (73, 109, 56),
        (94, 126, 68),
        (116, 144, 83),
    ),
)

TREE_BARK = (
    (43, 34, 27),
    (65, 46, 32),
    (87, 61, 40),
    (111, 79, 48),
    (137, 101, 62),
)

TREE_FRUIT = (
    (
        (102, 48, 32),
        (157, 75, 43),
        (198, 112, 60),
        (227, 156, 87),
    ),
    (
        (104, 82, 34),
        (162, 128, 48),
        (199, 165, 68),
        (224, 195, 108),
    ),
)


def vec(tile):
    return pygame.Vector2(tile[0] * T, tile[1] * T)


def pixel(point):
    return round(point[0]), round(point[1])


def clamp01(value):
    return max(0.0, min(1.0, value))


def smoothstep(value):
    value = clamp01(value)
    return clamp01(value * value * (3.0 - 2.0 * value))


def smootherstep(value):
    """Ken Perlin's quintic ease: zero velocity and acceleration at
    both ends, which is what makes camera moves feel filmed.

    The result is clamped because float rounding can push it a hair
    outside 0..1, and Vector2.lerp rejects that.
    """
    value = clamp01(value)
    return clamp01(
        value * value * value * (value * (value * 6.0 - 15.0) + 10.0)
    )


def facing(delta, fallback="d"):
    if delta.length_squared() < 0.01:
        return fallback
    if abs(delta.x) > abs(delta.y):
        return "r" if delta.x > 0 else "l"
    return "d" if delta.y > 0 else "u"


def approach(position, target, speed, dt):
    delta = target - position
    distance = delta.length()

    if distance <= speed * dt:
        position.update(target)
        return True

    if distance:
        position += delta / distance * speed * dt

    return False


class GoatRescue:
    def __init__(self, farm):
        self.farm = farm
        self.time = self.last_time = now_ms()
        self.phase = "outbound"
        self.finished = False

        self.bodi = vec(M.BODI_TILE)
        self.bodi_face = "d"
        self.bodi_step = 0.0
        self.bodi_moving = False

        self.goat = DITCH_GOAT.copy()
        self.goat_right = False
        self.goat_moving = False
        self.flee_target = None
        self.flee_count = 0
        self.calm_time = 0.0

        self.route_index = 0
        self.flank_index = 0
        self.track_spoken = set()
        self.player_speed = 0.0

        self.repair_stage = "set"        # "set" -> "wrap"
        self.set_time = 0.0
        self.wraps_done = 0
        self.repair_perfect = 0
        self.wrap_phase = 0.0
        self.wrap_target = 0.0
        self.wrap_misses = 0
        self.wrap_cooldown = 0.0
        self.wrap_flash = 0.0
        self.wrap_result = ""
        self.prev_cinch = True
        self.gust_state = "idle"         # idle / warn / blow
        self.gust_timer = 1.6
        self.gust_dir = 1
        self.repair_callout = ("", 0)

        self.repaired = False
        self.post_lean = 0.62
        self.post_velocity = 0.0
        self.repair_clock = 0.0
        self.repair_work_clock = 0.0
        self.repair_gripping = False
        self.repair_stable = False
        self.repair_bodi_ready = False
        self.repair_particles = []
        self.repair_particle_clock = 0.0
        self.repair_rng = random.Random(0xB0D1)
        self.repair_finish_time = None

        # Repair animation resources. Sprites are generated lazily and
        # reused; static scenery is never rebuilt for animation.
        self.repair_sprite_cache = {}
        self.repair_base_cache = {}
        self.repair_player_stance = None
        self.repair_bodi_stance = None

        self.overlook_time = 0.0
        self.overlook_spoken = False

        # The area east of the ditch stays cut until the reveal ends.
        self.ditch_revealed = False
        self.reveal_stage = "pan"        # pan -> hold -> return
        self.reveal_clock = 0.0
        self.reveal_stage_t = 0.0
        self.reveal_wipe = 0.0           # eased 0..1 wipe progress
        self.reveal_bars = 0.0           # letterbox + vignette amount
        self.reveal_caption = 0.0
        self.reveal_cam_from = pygame.Vector2()
        self.reveal_bleated = False
        self.reveal_motes = []
        self.reveal_mote_acc = 0.0
        self.reveal_rng = random.Random(0xA11CE)

        self.lines = []
        self.line_t0 = self.time
        self.line_until = self.time
        self.tick_n = 0

        self.toast = ("", 0)
        self.prev_adv = False

        self.world_size = (
            WORLD_COLS * T,
            WORLD_ROWS * T,
        )
        self.camera = pygame.Vector2()

        grid = [list(row) for row in farm._S["grid"]]
        for col, row in (YARD_GATE, BROKEN_FENCE):
            grid[row][col] = "."

        self.grid = ["".join(row) for row in grid]
        farm._S["grid"] = self.grid

        # Keep visual fence connectivity separate from collision.
        visual_grid = [list(row) for row in self.grid]
        col, row = BROKEN_FENCE
        visual_grid[row][col] = "f"
        self.fence_grid = [
            "".join(row) for row in visual_grid
        ]

        self.static = self._build_static()
        self.tree_sprites = self._build_tree_sprites()
        self.frame = pygame.Surface(self.world_size)
        self.farm_layer = pygame.Surface((WIDTH, HEIGHT))
        self.animal_layer = pygame.Surface(
            (WIDTH, HEIGHT), pygame.SRCALPHA
        )

        self._build_reveal_assets()
        self._rebuild_walls()

        # The escape (and Bodi's first three lines about it) plays as the
        # chores-complete film; this beat starts with the walk out.
        self.say(
            (
                "BODI",
                "Come on. Bring yourself. I'll bring the wire.",
            ),
        )

        self.camera.update(self._camera_target())

    # -- dialogue ----------------------------------------------------------

    def say(self, *lines):
        was_empty = not self.lines
        self.lines.extend(lines)

        if was_empty and self.lines:
            self._start_line()

    def _start_line(self):
        self.line_t0 = self.time
        self.tick_n = 0
        self.line_until = self.time + max(
            4200,
            2200 + len(self.lines[0][1]) * 65,
        )

    def _next_line(self):
        if not self.lines:
            return

        self.lines.pop(0)
        if self.lines:
            self._start_line()

    def advance_dialogue(self):
        if not self.lines:
            return False

        text = self.lines[0][1]

        if (
            (self.time - self.line_t0) // self.farm.CHAR_MS
            < len(text)
        ):
            self.line_t0 = (
                self.time
                - len(text) * self.farm.CHAR_MS
                - 1
            )
        else:
            self._next_line()

        return True

    def notify(self, text, ms=3200):
        self.toast = (text, self.time + ms)

    # -- scenery -----------------------------------------------------------

    def _build_static(self):
        surface = pygame.Surface(self.world_size)
        surface.blit(
            self.farm._build_static(
                self.grid,
                self.farm.CHORES,
                fence_grid=self.fence_grid,
                skip_fence={BROKEN_FENCE},
            ),
            (0, 0),
        )

        for row in range(WORLD_ROWS):
            for col in range(M.COLS, WORLD_COLS):
                tile = self.farm._ground_tile(
                    "grass",
                    (col * 3 + row * 5) % 6,
                )
                surface.blit(tile, (col * T, row * T))

        road = pygame.Rect(
            M.COLS * T,
            (WORLD_ROWS - 1) * T + 10,
            (WORLD_COLS - M.COLS) * T,
            T - 20,
        )
        surface.fill(M.TRACK[1], road)
        surface.fill(M.TRACK[0], road.inflate(0, -8))

        for y in (road.y + 12, road.bottom - 18):
            surface.fill(
                M.TRACK[1],
                (road.x, y, road.w, 6),
            )

        path = M.DIRT[0]
        surface.fill(path, (15 * T, 5 * T, 8 * T, T))
        surface.fill(path, (17 * T, 4 * T, 2 * T, 2 * T))

        ditch = pygame.Rect(
            DITCH_X, 2 * T, DITCH_W, 6 * T
        )
        surface.fill((71, 66, 49), ditch)
        surface.fill(
            (109, 119, 98),
            ditch.inflate(-12, 0),
        )

        ford = pygame.Rect(
            ditch.x - 6,
            5 * T,
            ditch.w + 12,
            T,
        )
        surface.fill((143, 133, 103), ford)

        for i in range(7):
            pygame.draw.ellipse(
                surface,
                (169, 161, 128),
                (
                    ford.x
                    + 5
                    + (i * 11) % max(1, ford.w - 12),
                    ford.y + 8 + (i * 17) % 43,
                    9,
                    5,
                ),
            )

        trail = (
            (13.5, 5.6),
            (14.5, 5.5),
            (15.5, 5.5),
            (16.3, 5.5),
            (17.2, 5.0),
            (18.1, 4.5),
            (18.8, 4.8),
            (20.0, 5.5),
        )

        for index, tile in enumerate(trail):
            point = vec(tile)

            for offset in (-5, 5):
                pygame.draw.ellipse(
                    surface,
                    (75, 63, 44),
                    (
                        int(point.x) + offset,
                        int(point.y),
                        4,
                        7,
                    ),
                )

            if index % 2 == 0:
                self._draw_chewed_plant(
                    surface,
                    point + pygame.Vector2(-12, 18),
                )

        return surface

    def _build_tree_sprites(self):
        trees = []
        width = TREE_CANVAS[0] * TREE_SCALE
        height = TREE_CANVAS[1] * TREE_SCALE

        anchor = pygame.Vector2(
            TREE_ANCHOR[0] * TREE_SCALE,
            TREE_ANCHOR[1] * TREE_SCALE,
        )

        for tile in TREES:
            base = vec(tile)
            image = pygame.Surface(
                (width, height), pygame.SRCALPHA
            )
            self._draw_tree(
                image,
                anchor,
                seed_point=base,
            )

            trees.append(
                (
                    base.y,
                    image,
                    (
                        round(base.x - anchor.x),
                        round(base.y - anchor.y),
                    ),
                )
            )

        return trees

    def _draw_tree(self, surface, point, seed_point=None):
        """Draw a detailed pixel-art tree at its trunk base."""
        x, y = pixel(point)

        if seed_point is None:
            seed_point = point

        seed_x, seed_y = pixel(seed_point)
        seed = (
            (seed_x * 73856093)
            ^ (seed_y * 19349663)
            ^ 0x5F3759DF
        ) & 0xFFFFFFFF

        rng = random.Random(seed)

        foliage = TREE_PALETTES[
            rng.randrange(len(TREE_PALETTES))
        ]
        bark = TREE_BARK
        fruit = TREE_FRUIT[
            rng.randrange(len(TREE_FRUIT))
        ]

        width, height = TREE_CANVAS
        cx, base = TREE_ANCHOR

        tree = pygame.Surface(
            (width, height), pygame.SRCALPHA
        )

        lean = rng.randint(-2, 2)
        crown_x = cx + lean
        crown_y = base - 32 + rng.randint(-2, 1)

        shadow = pygame.Surface(
            (width, height), pygame.SRCALPHA
        )

        for rect, alpha in (
            ((cx - 22, base - 6, 54, 17), 15),
            ((cx - 18, base - 5, 45, 14), 19),
            ((cx - 13, base - 3, 34, 10), 24),
        ):
            shade = pygame.Surface(
                (width, height), pygame.SRCALPHA
            )
            pygame.draw.ellipse(
                shade,
                (16, 24, 15, alpha),
                rect,
            )
            shadow.blit(shade, (0, 0))

        tree.blit(shadow, (0, 0))

        pygame.draw.ellipse(
            tree,
            (73, 72, 43),
            (cx - 9, base - 3, 19, 8),
        )
        pygame.draw.ellipse(
            tree,
            (91, 85, 49),
            (cx - 7, base - 2, 14, 5),
        )

        for _ in range(13):
            lx = cx + rng.randint(-19, 23)
            ly = base + rng.randint(-3, 7)
            color = rng.choice(
                (
                    (92, 91, 44),
                    (116, 105, 51),
                    (135, 113, 59),
                    (67, 83, 40),
                )
            )
            tree.fill(color, (lx, ly, 2, 1))

        roots = (
            ((cx - 2, base - 5), (cx - 10, base + 3)),
            ((cx + 2, base - 5), (cx + 10, base + 3)),
            ((cx, base - 4), (cx + 2, base + 6)),
        )

        for start, end in roots:
            pygame.draw.line(
                tree, bark[0], start, end, 4
            )
            pygame.draw.line(
                tree, bark[2], start, end, 2
            )

        pygame.draw.line(
            tree,
            bark[3],
            (cx - 3, base - 3),
            (cx - 8, base + 2),
            1,
        )

        trunk_top = (cx + lean, base - 27)

        pygame.draw.polygon(
            tree,
            bark[0],
            (
                (cx - 6, base + 2),
                (cx - 4, base - 10),
                (trunk_top[0] - 3, trunk_top[1]),
                (trunk_top[0] + 3, trunk_top[1]),
                (cx + 4, base - 11),
                (cx + 6, base + 2),
            ),
        )
        pygame.draw.polygon(
            tree,
            bark[2],
            (
                (cx - 4, base + 1),
                (cx - 2, base - 11),
                (trunk_top[0] - 2, trunk_top[1]),
                (trunk_top[0] + 1, trunk_top[1]),
                (cx + 2, base - 10),
                (cx + 4, base + 1),
            ),
        )

        pygame.draw.line(
            tree,
            bark[3],
            (cx - 3, base - 1),
            (cx - 1 + lean, base - 24),
            2,
        )
        pygame.draw.line(
            tree,
            bark[1],
            (cx + 2, base),
            (cx + lean + 1, base - 22),
            2,
        )

        for start, end, thickness in (
            ((cx, base - 15), (cx - 13, base - 30), 5),
            (
                (cx + lean, base - 20),
                (cx + 13, base - 34),
                4,
            ),
            (
                (cx + lean, base - 23),
                (cx - 2, base - 39),
                4,
            ),
        ):
            pygame.draw.line(
                tree,
                bark[0],
                start,
                end,
                thickness + 2,
            )
            pygame.draw.line(
                tree,
                bark[2],
                start,
                end,
                thickness,
            )
            pygame.draw.line(
                tree,
                bark[3],
                (start[0] - 1, start[1]),
                (end[0] - 1, end[1]),
                1,
            )

        for _ in range(12):
            bx = cx + rng.randint(-2, 2)
            by = base - rng.randint(2, 20)

            pygame.draw.line(
                tree,
                rng.choice(
                    (bark[0], bark[1], bark[3])
                ),
                (bx, by),
                (
                    bx + rng.choice((-1, 0, 1)),
                    by + rng.randint(2, 4),
                ),
                1,
            )

        pygame.draw.ellipse(
            tree,
            bark[0],
            (cx - 1, base - 12, 3, 5),
        )
        tree.fill(
            bark[3],
            (cx - 1, base - 12, 1, 2),
        )

        lobes = (
            (-16, 6, 12),
            (-6, 12, 13),
            (9, 11, 13),
            (20, 3, 11),
            (18, -9, 11),
            (8, -16, 12),
            (-6, -17, 12),
            (-19, -7, 11),
            (-4, -2, 16),
            (9, -1, 14),
        )

        lobes = [
            (
                crown_x + dx + rng.randint(-2, 2),
                crown_y + dy + rng.randint(-1, 1),
                radius + rng.randint(-1, 1),
            )
            for dx, dy, radius in lobes
        ]

        silhouette = pygame.Surface(
            (width, height), pygame.SRCALPHA
        )

        for lx, ly, radius in lobes:
            pygame.draw.circle(
                silhouette,
                foliage[0],
                (lx, ly),
                radius + 1,
            )

        tree.blit(silhouette, (0, 0))

        for index, (lx, ly, radius) in enumerate(lobes):
            shade_index = 2 if ly > crown_y + 5 else 3

            if lx < crown_x and ly < crown_y:
                shade_index = 4

            pygame.draw.circle(
                tree,
                foliage[shade_index],
                (lx, ly),
                max(2, radius - 1),
            )
            pygame.draw.ellipse(
                tree,
                foliage[max(1, shade_index - 1)],
                (
                    lx - radius + 2,
                    ly + radius // 3,
                    radius * 2 - 4,
                    max(3, radius // 2),
                ),
            )

            if index >= 4:
                pygame.draw.ellipse(
                    tree,
                    foliage[min(5, shade_index + 1)],
                    (
                        lx - radius + 3,
                        ly - radius + 3,
                        max(4, radius + 2),
                        max(3, radius - 2),
                    ),
                )

        crown_mask = pygame.mask.from_surface(silhouette)

        def inside_crown(px, py, margin=0):
            if not (
                margin <= px < width - margin
                and margin <= py < height - margin
            ):
                return False

            samples = (
                (px, py),
                (px - margin, py),
                (px + margin, py),
                (px, py - margin),
                (px, py + margin),
            )

            return all(
                crown_mask.get_at(sample)
                for sample in samples
            )

        for _ in range(105):
            lx = crown_x + rng.randint(-30, 29)
            ly = crown_y + rng.randint(-27, 25)

            if not inside_crown(lx, ly, 3):
                continue

            light = (
                (crown_x - lx) * 0.45
                + (crown_y - ly) * 0.7
            )

            shade_index = 3

            if light > 10:
                shade_index = 5
            elif light > 1:
                shade_index = 4
            elif light < -10:
                shade_index = 2

            shade_index = max(
                1,
                min(
                    6,
                    shade_index
                    + rng.choice((-1, 0, 0, 0, 1)),
                ),
            )

            leaf_w = rng.randint(3, 6)

            tree.fill(
                foliage[shade_index],
                (lx - 2, ly, leaf_w, 2),
            )
            tree.fill(
                foliage[shade_index],
                (
                    lx - 1,
                    ly - 1,
                    max(2, leaf_w - 2),
                    1,
                ),
            )

            if (
                shade_index >= 4
                and rng.randrange(3) == 0
            ):
                tree.fill(
                    foliage[min(6, shade_index + 1)],
                    (lx - 1, ly - 1, 2, 1),
                )

        for dx, dy in (
            (-13, 7),
            (4, 13),
            (15, 3),
            (-3, -1),
        ):
            lx = crown_x + dx
            ly = crown_y + dy

            if inside_crown(lx, ly, 3):
                tree.fill(
                    foliage[1],
                    (lx - 2, ly, 5, 1),
                )
                tree.fill(
                    foliage[2],
                    (lx, ly + 1, 4, 1),
                )

        fruit_points = []
        desired_fruit = rng.randint(5, 8)

        for _ in range(100):
            if len(fruit_points) >= desired_fruit:
                break

            fx = crown_x + rng.randint(-23, 23)
            fy = crown_y + rng.randint(-13, 19)

            if not inside_crown(fx, fy, 4):
                continue

            if any(
                (fx - px) ** 2 + (fy - py) ** 2 < 65
                for px, py in fruit_points
            ):
                continue

            fruit_points.append((fx, fy))

            tree.fill(
                foliage[0],
                (fx - 1, fy + 1, 4, 4),
            )
            tree.fill(fruit[0], (fx - 1, fy, 4, 4))
            tree.fill(fruit[1], (fx - 1, fy, 3, 3))
            tree.fill(fruit[2], (fx - 1, fy, 2, 2))
            tree.fill(fruit[3], (fx - 1, fy, 1, 1))
            tree.fill(bark[0], (fx, fy - 2, 1, 2))
            tree.fill(
                foliage[5],
                (fx + 1, fy - 2, 2, 1),
            )

        for dx in (-10, -7, 7, 10):
            gy = base + rng.randint(1, 4)

            pygame.draw.line(
                tree,
                (57, 77, 38),
                (cx + dx, gy),
                (
                    cx + dx + rng.choice((-2, 2)),
                    gy - rng.randint(2, 4),
                ),
                1,
            )

        image = pygame.transform.scale(
            tree,
            (
                width * TREE_SCALE,
                height * TREE_SCALE,
            ),
        )
        surface.blit(
            image,
            (
                x - cx * TREE_SCALE,
                y - base * TREE_SCALE,
            ),
        )

    def _draw_chewed_plant(self, surface, point):
        x, y = pixel(point)

        for dx, dy in (
            (-5, 2),
            (2, -4),
            (6, 3),
        ):
            pygame.draw.line(
                surface,
                (58, 85, 42),
                (x, y + 7),
                (x + dx, y + dy),
                3,
            )

        surface.fill(
            (174, 155, 99),
            (x - 2, y + 5, 5, 4),
        )

    def _rebuild_walls(self):
        walls = [
            pygame.Rect(
                col * T,
                row * T,
                T,
                T,
            )
            for row, cells in enumerate(self.grid)
            for col, cell in enumerate(cells)
            if cell in M.SOLID
        ]

        self.tree_colliders = []

        for tile in TREES:
            point = vec(tile)
            trunk = pygame.Rect(
                round(point.x) - 10,
                round(point.y) - 8,
                20,
                16,
            )
            self.tree_colliders.append(trunk)
            walls.append(trunk)

        walls.append(
            pygame.Rect(
                DITCH_X,
                2 * T,
                DITCH_W,
                3 * T,
            )
        )
        walls.append(
            pygame.Rect(
                DITCH_X,
                6 * T,
                DITCH_W,
                2 * T,
            )
        )

        # Until the reveal, a full-height barrier closes the ford too.
        if not self.ditch_revealed:
            walls.append(
                pygame.Rect(
                    CUT_X - 12,
                    0,
                    12 + DITCH_W,
                    self.world_size[1],
                )
            )

        if self.repaired:
            col, row = BROKEN_FENCE
            walls.append(
                pygame.Rect(
                    col * T,
                    row * T,
                    T,
                    T,
                )
            )

        STATE.walls = self.walls = walls

    # -- movement ----------------------------------------------------------

    def _player_feet(self, rect):
        width = min(16, rect.w)
        height = min(10, rect.h)

        return pygame.Rect(
            rect.centerx - width // 2,
            rect.bottom - height,
            width,
            height,
        )

    def _move_player_axis(self, rect, pos, amount, axis):
        if not amount:
            return

        if axis == "x":
            pos.x += amount
            rect.x = round(pos.x)
        else:
            pos.y += amount
            rect.y = round(pos.y)

        feet = self._player_feet(rect)
        hits = [
            wall
            for wall in self.walls
            if feet.colliderect(wall)
        ]

        if not hits:
            return

        if axis == "x":
            if amount > 0:
                edge = min(wall.left for wall in hits)
                rect.x += edge - feet.right
            else:
                edge = max(wall.right for wall in hits)
                rect.x += edge - feet.left

            pos.x = rect.x
        else:
            if amount > 0:
                edge = min(wall.top for wall in hits)
                rect.y += edge - feet.bottom
            else:
                edge = max(wall.bottom for wall in hits)
                rect.y += edge - feet.top

            pos.y = rect.y

    def _repair_finishing(self):
        return (
            self.repair_finish_time is not None
            and self.time - self.repair_finish_time
            < REPAIR_FINISH_MS
        )

    def _repair_actor_active(self):
        return (
            self.phase == "repairing"
            or self._repair_finishing()
        )

    def _move_player(self, keys, dt):
        down = self.farm._down

        dx = int(
            down(keys, pygame.K_d)
            or down(keys, pygame.K_RIGHT)
        )
        dx -= int(
            down(keys, pygame.K_a)
            or down(keys, pygame.K_LEFT)
        )

        dy = int(
            down(keys, pygame.K_s)
            or down(keys, pygame.K_DOWN)
        )
        dy -= int(
            down(keys, pygame.K_w)
            or down(keys, pygame.K_UP)
        )

        direction = pygame.Vector2(dx, dy)

        if direction.length_squared() > 1:
            direction.normalize_ip()

        # Input is locked during the repair pose and the reveal.
        if self._repair_actor_active() or self.phase == "reveal":
            direction.update(0, 0)

        careful = (
            down(keys, pygame.K_LSHIFT)
            or down(keys, pygame.K_RSHIFT)
        )
        speed = CAREFUL_SPEED if careful else WALK_SPEED

        S = self.farm._S
        rect = STATE.player.rect
        pos = S["pos"]

        if (
            abs(rect.x - round(pos.x)) > 1
            or abs(rect.y - round(pos.y)) > 1
        ):
            pos.update(rect.topleft)

        old = pygame.Vector2(rect.center)
        movement = direction * speed * dt

        steps = max(
            1,
            math.ceil(movement.length() / 5),
        )
        movement /= steps

        for _ in range(steps):
            self._move_player_axis(
                rect, pos, movement.x, "x"
            )
            self._move_player_axis(
                rect, pos, movement.y, "y"
            )

        rect.clamp_ip(
            pygame.Rect((0, 0), self.world_size)
        )
        pos.update(rect.topleft)

        travelled = pygame.Vector2(
            rect.center
        ).distance_to(old)

        S["moving"] = travelled > 0.1
        self.player_speed = travelled / dt if dt else 0.0

        if direction.length_squared():
            S["face"] = facing(direction, S["face"])
            STATE.player.angle = math.atan2(
                direction.y,
                direction.x,
            )

        if travelled:
            S["step"] += travelled * 0.0733
            phase = int(S["step"] / math.pi)

            if phase != S["step_ph"]:
                S["step_ph"] = phase
                self.farm._snd().step(phase)

    def _player(self):
        return pygame.Vector2(
            STATE.player.rect.center
        )

    def _walk_bodi(
        self,
        target,
        dt,
        wait_for_player=True,
    ):
        if (
            wait_for_player
            and self.bodi.distance_to(self._player()) > 150
        ):
            self.bodi_moving = False
            return False

        self.bodi_face = facing(
            target - self.bodi,
            self.bodi_face,
        )

        old = self.bodi.copy()
        arrived = approach(
            self.bodi,
            target,
            BODI_SPEED,
            dt,
        )

        travelled = self.bodi.distance_to(old)
        self.bodi_moving = travelled > 0.1
        self.bodi_step += travelled * 0.0733

        return arrived

    def _walk_goat(self, target, speed, dt):
        old = self.goat.copy()

        if abs(target.x - self.goat.x) > 0.1:
            self.goat_right = target.x > self.goat.x

        arrived = approach(
            self.goat,
            target,
            speed,
            dt,
        )
        self.goat_moving = (
            self.goat.distance_to(old) > 0.1
        )

        return arrived

    # -- repair staging ----------------------------------------------------

    def _place_player_for_repair(self):
        """Put both actors close enough to visibly handle the post."""
        base, _, _ = self._post_geometry()
        col, row = BROKEN_FENCE

        center_x = col * T + T / 2
        center_y = row * T + T / 2

        # Both stances stay inside the currently open fence tile.
        side_offset = min(22.0, T * 0.30)
        feet_y = min(
            (row + 1) * T - 4,
            center_y + 22,
        )

        desired = pygame.Vector2(
            center_x - side_offset,
            feet_y,
        )

        rect = STATE.player.rect
        candidate = rect.copy()
        candidate.centerx = round(desired.x)
        candidate.bottom = round(desired.y + 2)

        # Test the same small foot collider used for normal movement.
        feet = self._player_feet(candidate)

        if not any(
            feet.colliderect(wall)
            for wall in self.walls
        ):
            rect.topleft = candidate.topleft
            self.farm._S["pos"].update(rect.topleft)

        self.repair_player_stance = pygame.Vector2(
            rect.centerx,
            rect.bottom - 2,
        )

        # Bodi's position is stored 14 pixels above his draw anchor.
        self.repair_bodi_stance = pygame.Vector2(
            center_x + side_offset,
            feet_y - 14,
        )

        self.farm._S["face"] = "r"
        self.farm._S["moving"] = False
        self.player_speed = 0.0

        # Keep the interaction centered on the visible post.
        self.repair_focus = base.copy()

    def _release_player_after_repair(self):
        """Move the player's feet out of the newly solid fence tile."""
        rect = STATE.player.rect
        feet = self._player_feet(rect)

        if any(
            feet.colliderect(wall)
            for wall in self.walls
        ):
            self.farm._teleport((13.5, 5.4))

    # -- interaction -------------------------------------------------------

    def _near_hay(self):
        hay = M.POINTS["hay"]

        return (
            not self.farm._S["crate"]
            and self._player().distance_to(
                vec(hay["at"])
            ) <= hay["reach"]
        )

    def _near_post(self):
        base, _, _ = self._post_geometry()

        return (
            self.phase == "repair"
            and (
                self._player().distance_to(POST) < 85
                or self._player().distance_to(base) < 85
            )
        )

    def interact(self):
        if self.finished:
            return True

        self.time = now_ms()

        if self.phase == "repairing":
            return True

        if self._repair_finishing():
            return True

        if self.lines:
            return self.advance_dialogue()

        if self.phase == "reveal":
            return True

        if self._near_post():
            self.phase = "repairing"
            self.post_velocity = 0.0
            self.repair_gripping = False
            self.repair_stable = False
            self.prev_cinch = True

            self._place_player_for_repair()

            self.notify(
                "Hold E to grip. A / D steady the post. "
                "Space cinches the wire.",
                6500,
            )
            return True

        if self._near_hay():
            self.farm._S["crate"] = True
            STATE.m7_crate = True

            self.farm._snd().hay()
            self.farm._snd().crate()

            self.say(
                (
                    "",
                    "Under the hay: a crate of rifle magazines.",
                ),
                (
                    "",
                    "Behind it, a photograph. Bodi and Maru "
                    "in uniform, years younger.",
                ),
            )
            return True

        return False

    # -- phases ------------------------------------------------------------

    def _update_outbound(self, dt):
        if self.route_index >= len(OUTBOUND):
            self.bodi_moving = False

            if self.lines:
                return

            self._begin_reveal()
            return

        if self._walk_bodi(
            vec(OUTBOUND[self.route_index]),
            dt,
        ):
            index = self.route_index

            if (
                index in TRACK_LINES
                and index not in self.track_spoken
            ):
                self.track_spoken.add(index)
                self.say(*TRACK_LINES[index])

            if not self.lines:
                self.route_index += 1

    def _update_approach(self, dt):
        if self.flank_index < len(FLANK):
            if self._walk_bodi(
                vec(FLANK[self.flank_index]),
                dt,
                wait_for_player=False,
            ):
                self.flank_index += 1
        else:
            self.bodi_moving = False
            self.bodi_face = "u"

        if self.flee_target is not None:
            if self._walk_goat(
                self.flee_target,
                145.0,
                dt,
            ):
                self.flee_target = None
            return

        self.goat_moving = False
        player = self._player()
        distance = player.distance_to(self.goat)

        if (
            distance < 125
            and self.player_speed > SPOOK_SPEED
        ):
            self.calm_time = 0.0
            self.flee_count += 1

            self.flee_target = vec(
                (
                    21.4 + 0.35 * (self.flee_count % 2),
                    4.5 + 0.35 * (self.flee_count % 3),
                )
            )

            self.farm._snd().goat()
            self.notify(
                "She shies away. Give her room, then go slowly."
            )

            if self.flee_count == 1:
                self.say(
                    (
                        "BODI",
                        "Easy. You're asking her, not arresting her.",
                    ),
                )

            return

        calm = (
            distance < 85
            and player.y < self.goat.y - 10
            and self.player_speed <= SPOOK_SPEED
            and self.flank_index >= len(FLANK)
            and not self.lines
        )

        self.calm_time = (
            self.calm_time + dt
            if calm
            else max(0.0, self.calm_time - dt)
        )

        if self.calm_time >= 1.2:
            self.phase = "herd"
            self.route_index = 0

            self.say(
                (
                    "BODI",
                    "That's it. Keep her between us.",
                ),
                (
                    "BIRIBEL",
                    "Does she do this often?",
                ),
                (
                    "BODI",
                    "Often enough to know the way back.",
                ),
            )

    def _update_herd(self, dt):
        if self.route_index >= len(HOMEWARD):
            self.phase = "repair"
            self.goat_moving = False

            self.say(
                (
                    "BODI",
                    "Hold that post straight. I'll wrap the wire.",
                ),
            )
            return

        if self._player().distance_to(self.goat) > 185:
            self.goat_moving = False
            self.bodi_moving = False
            return

        if self._walk_goat(
            vec(HOMEWARD[self.route_index]),
            GOAT_SPEED,
            dt,
        ):
            self.route_index += 1

        follow = min(
            max(0, self.route_index - 1),
            len(HOMEWARD) - 1,
        )

        self._walk_bodi(
            vec(HOMEWARD[follow]),
            dt,
            wait_for_player=False,
        )

    # -- reveal cinematic --------------------------------------------------

    def _build_reveal_assets(self):
        """Pre-render the reveal's gradients so drawing stays cheap."""
        height = self.world_size[1]
        border = tuple(M.SKY_EDGE)[:3]

        # Fog: border colour fading from clear (west) to solid (east).
        fog = pygame.Surface(
            (REVEAL_FADE_W, height), pygame.SRCALPHA
        )
        for x in range(REVEAL_FADE_W):
            k = x / (REVEAL_FADE_W - 1)
            alpha = round(255 * smoothstep(k))
            pygame.draw.line(
                fog, (*border, alpha), (x, 0), (x, height - 1)
            )
        self.reveal_fog = fog

        # Glow: warm band, additive, dark at both ends.
        glow = pygame.Surface((REVEAL_GLOW_W, height))
        glow.fill((0, 0, 0))
        for x in range(REVEAL_GLOW_W):
            k = x / (REVEAL_GLOW_W - 1)
            level = math.sin(math.pi * k ** 1.6)
            pygame.draw.line(
                glow,
                (
                    round(118 * level),
                    round(92 * level),
                    round(46 * level),
                ),
                (x, 0),
                (x, height - 1),
            )
        self.reveal_glow = glow

        # Vignette: tiny radial map smooth-scaled to the screen.
        small_w, small_h = 48, 27
        small = pygame.Surface(
            (small_w, small_h), pygame.SRCALPHA
        )
        for y in range(small_h):
            for x in range(small_w):
                dx = (x + 0.5) / small_w * 2.0 - 1.0
                dy = (y + 0.5) / small_h * 2.0 - 1.0
                d = math.hypot(dx, dy) / math.sqrt(2.0)
                alpha = round(200 * smoothstep((d - 0.35) / 0.65))
                small.set_at((x, y), (6, 8, 6, alpha))
        self.reveal_vignette = pygame.transform.smoothscale(
            small, (WIDTH, HEIGHT)
        )

    def _begin_reveal(self):
        self.phase = "reveal"
        self.reveal_stage = "pan"
        self.reveal_clock = 0.0
        self.reveal_stage_t = 0.0
        self.reveal_cam_from = self.camera.copy()
        self.bodi_face = "r"
        self.bodi_moving = False

    def _reveal_edge(self):
        """World x of the wipe's leading edge."""
        return CUT_X + (
            self.world_size[0] + REVEAL_FADE_W - CUT_X
        ) * self.reveal_wipe

    def _spawn_reveal_mote(self, edge):
        rng = self.reveal_rng
        life = rng.uniform(1.0, 2.2)

        self.reveal_motes.append(
            {
                "pos": pygame.Vector2(
                    edge - rng.uniform(0, 90),
                    rng.uniform(T * 0.5, self.world_size[1] - T * 0.5),
                ),
                "vel": pygame.Vector2(
                    rng.uniform(-6, 14),
                    rng.uniform(-26, -6),
                ),
                "life": life,
                "max": life,
                "size": rng.choice((2, 2, 3)),
                "phase": rng.uniform(0, math.tau),
            }
        )

    def _update_reveal_motes(self, dt):
        alive = []

        for mote in self.reveal_motes:
            mote["life"] -= dt

            if mote["life"] <= 0:
                continue

            mote["pos"] += mote["vel"] * dt
            mote["pos"].x += (
                math.sin(mote["life"] * 5.0 + mote["phase"]) * 8.0 * dt
            )
            alive.append(mote)

        self.reveal_motes = alive

    def _update_reveal(self, dt):
        self.bodi_moving = False
        self.goat_moving = False
        self.reveal_clock += dt
        clock = self.reveal_clock

        self.reveal_wipe = smootherstep(
            (clock - REVEAL_WIPE_DELAY) / REVEAL_WIPE_S
        )

        if 0.0 < self.reveal_wipe < 1.0:
            self.reveal_mote_acc += dt * REVEAL_MOTE_RATE
            edge = self._reveal_edge()

            while self.reveal_mote_acc >= 1.0:
                self.reveal_mote_acc -= 1.0
                self._spawn_reveal_mote(edge)

        # She bleats the moment the light reaches her.
        if (
            not self.reveal_bleated
            and self._reveal_edge() >= self.goat.x + 20
        ):
            self.reveal_bleated = True
            self.farm._snd().goat()

        vista = self._camera_target(
            focus=self.goat, open_world=True
        )

        if self.reveal_stage == "pan":
            self.reveal_bars = smootherstep(clock / REVEAL_BARS_S)
            self.camera.update(
                self.reveal_cam_from.lerp(
                    vista, smootherstep(clock / REVEAL_PAN_S)
                )
            )

            if clock >= REVEAL_PAN_S and self.reveal_wipe >= 1.0:
                self.reveal_stage = "hold"
                self.reveal_stage_t = 0.0
                self.say(
                    (
                        "BODI",
                        "There she is. Other side of the ditch.",
                    ),
                )

        elif self.reveal_stage == "hold":
            self.reveal_stage_t += dt
            t = self.reveal_stage_t

            self.reveal_bars = 1.0
            self.reveal_caption = smoothstep(t / 0.9)

            # Slow handheld-style drift, eased in so there is no jump.
            drift = smoothstep(t / 1.0)
            sway = pygame.Vector2(
                math.sin(t * 0.9) * 2.0,
                math.sin(t * 0.65 + 1.0) * 1.2,
            ) * drift
            self.camera.update(vista + sway)

            if not self.lines and t >= REVEAL_HOLD_MIN_S:
                self.reveal_stage = "return"
                self.reveal_stage_t = 0.0
                self.reveal_cam_from = self.camera.copy()

        else:
            self.reveal_stage_t += dt
            a = clamp01(self.reveal_stage_t / REVEAL_RETURN_S)
            e = smootherstep(a)

            target = self._camera_target(open_world=True)
            self.camera.update(self.reveal_cam_from.lerp(target, e))

            self.reveal_bars = 1.0 - e
            self.reveal_caption = max(0.0, 1.0 - a * 3.0)

            if a >= 1.0:
                self._finish_reveal()

    def _finish_reveal(self):
        self.ditch_revealed = True
        self.reveal_wipe = 1.0
        self.reveal_bars = 0.0
        self.reveal_caption = 0.0
        self._rebuild_walls()

        self.phase = "approach"

        self.say(
            (
                "BODI",
                "Take the shallow crossing. Come at her "
                "from the north. I'll go around below.",
            ),
            (
                "BODI",
                "Slowly. She's got nowhere important to be.",
            ),
        )
        self.notify(
            "Hold Shift to approach carefully.",
            6500,
        )

    # -- repair minigame ---------------------------------------------------

    def _repair_progress(self):
        """Overall 0..1 progress across both steps."""
        if self.repaired:
            return 1.0

        set_part = min(1.0, self.set_time / SET_S) * 0.45
        wrap_part = min(1.0, self.wraps_done / WRAPS) * 0.55
        return set_part + wrap_part

    def _callout(self, text, ms=1500):
        self.repair_callout = (text, self.time + ms)

    def _wrap_marker(self):
        """Triangle wave in -1..1."""
        p = self.wrap_phase % 2.0
        return (p if p < 1.0 else 2.0 - p) * 2.0 - 1.0

    def _update_gusts(self, dt, strength):
        """Telegraphed gusts. Returns the push on the post."""
        self.gust_timer -= dt

        if self.gust_state == "idle":
            if self.gust_timer <= 0:
                self.gust_state = "warn"
                self.gust_timer = GUST_WARN_S
                self.gust_dir = self.repair_rng.choice((-1, 1))
                side = "right" if self.gust_dir > 0 else "left"
                self._callout(f"Gust - she'll push {side}!", 1300)

        elif self.gust_state == "warn":
            if self.gust_timer <= 0:
                self.gust_state = "blow"
                self.gust_timer = GUST_BLOW_S

        else:
            if self.gust_timer <= 0:
                self.gust_state = "idle"
                self.gust_timer = self.repair_rng.uniform(1.8, 3.0)
                return 0.0

            t = 1.0 - self.gust_timer / GUST_BLOW_S
            return (
                self.gust_dir
                * GUST_FORCE
                * math.sin(math.pi * t)
                * strength
            )

        return 0.0

    def _cinch(self):
        error = abs(self._wrap_marker() - self.wrap_target)
        good = WRAP_GOOD + (
            WRAP_ASSIST if self.wrap_misses >= 2 else 0.0
        )

        self.wrap_cooldown = 0.3
        self.wrap_flash = 0.5

        if error > good:
            # A slip only jolts the post. Nothing is lost.
            self.wrap_misses += 1
            self.wrap_result = "miss"
            self.post_velocity += self.repair_rng.choice((-1, 1)) * 0.55
            self._callout("Slipped. Again.", 1000)
            return

        self.wrap_misses = 0
        self.wraps_done += 1

        if error <= WRAP_PERFECT:
            self.wrap_result = "perfect"
            self.repair_perfect += 1
            self._callout("Clean.", 900)
            self._spawn_repair_particles(8)
        else:
            self.wrap_result = "good"
            self._callout("Good. Hold it.", 900)
            self._spawn_repair_particles(4)

        self.farm._snd().fence_creak()
        self.wrap_target = self.repair_rng.uniform(-0.55, 0.55)

    def _finish_repair(self):
        self.repaired = True
        self.post_lean = 0.0
        self.post_velocity = 0.0
        self.repair_gripping = False
        self.repair_stable = False
        self.repair_finish_time = self.time
        self.phase = "repair_talk"

        self._spawn_repair_particles(10)
        self.farm._snd().fence_creak()

        if self.repair_perfect >= WRAPS:
            opener = (
                "BODI",
                "Three clean wraps. Maru would've needed five "
                "and an argument.",
            )
        elif self.repair_perfect:
            opener = (
                "BODI",
                "There. Try getting through that, you little thief.",
            )
        else:
            opener = (
                "BODI",
                "Ugly. But it'll hold. Try getting through that, "
                "you little thief.",
            )

        # Collision is restored after the finishing pose ends.
        self.say(
            opener,
            ("BIRIBEL", "Bodi. Why did you agree to shelter me?"),
            ("BODI", "Maru asked. He's my cousin."),
            ("BIRIBEL", "He never mentioned family."),
            (
                "BODI",
                "He wouldn't. Family's the one thing he keeps "
                "off the radio.",
            ),
        )

    def _objective_text(self):
        if self.phase == "repairing" and self.repair_stage == "wrap":
            return "SPACE TO CINCH - KEEP THE POST STEADY"
        return OBJECTIVES.get(self.phase, "")

    def _update_repair(self, keys, dt):
        target = (
            self.repair_bodi_stance
            if self.repair_bodi_stance is not None
            else vec((13.9, 5.6))
        )

        self.repair_bodi_ready = self._walk_bodi(
            target, dt, wait_for_player=False
        )

        if self.repair_bodi_ready:
            self.bodi_face = "l"

        self.goat_moving = False
        self.repair_gripping = False
        self.repair_stable = False
        self.wrap_flash = max(0.0, self.wrap_flash - dt)
        self.wrap_cooldown = max(0.0, self.wrap_cooldown - dt)

        if self.phase != "repairing":
            return

        down = self.farm._down
        self.repair_clock += dt
        self.repair_gripping = down(keys, pygame.K_e)

        left = down(keys, pygame.K_a) or down(keys, pygame.K_LEFT)
        right = down(keys, pygame.K_d) or down(keys, pygame.K_RIGHT)
        steering = int(right) - int(left)

        cinch_down = (
            down(keys, pygame.K_SPACE) or down(keys, pygame.K_RETURN)
        )
        cinch_pressed = cinch_down and not self.prev_cinch
        self.prev_cinch = cinch_down

        wrap_stage = self.repair_stage == "wrap"
        progress = self._repair_progress()

        # Gentle background sway; the gusts are the real challenge.
        disturbance = (
            math.sin(self.repair_clock * 1.9) * 1.25
            + math.sin(self.repair_clock * 3.4 + 0.8) * 0.42
        ) * 0.6 + 0.2
        disturbance *= 1.0 - progress * 0.35

        gust = 0.0
        if self.repair_bodi_ready:
            gust = self._update_gusts(
                dt, 0.5 if wrap_stage else 1.0
            )

        if self.repair_gripping:
            acceleration = (
                disturbance
                + gust
                + steering * 3.8
                + self.post_lean * 0.35
            )
            damping = 2.8
        else:
            acceleration = (
                disturbance * 0.25
                + gust * 0.25
                + (0.62 - self.post_lean) * 2.4
            )
            damping = 2.6

        steps = max(1, math.ceil(dt / (1.0 / 120.0)))
        step_dt = dt / steps

        for _ in range(steps):
            self.post_velocity += acceleration * step_dt
            self.post_velocity *= math.exp(-damping * step_dt)
            self.post_lean += self.post_velocity * step_dt

            if self.post_lean > 1.0:
                self.post_lean = 1.0
                self.post_velocity = min(0.0, self.post_velocity)
            elif self.post_lean < -1.0:
                self.post_lean = -1.0
                self.post_velocity = max(0.0, self.post_velocity)

        self.repair_stable = (
            self.repair_gripping
            and abs(self.post_lean) <= POST_SAFE_LEAN
        )
        working = self.repair_stable and self.repair_bodi_ready

        if working:
            self.repair_work_clock += dt
            self.repair_particle_clock += dt

            while self.repair_particle_clock >= 0.16:
                self.repair_particle_clock -= 0.16
                self._spawn_repair_particles(
                    1 if wrap_stage else 2
                )
        else:
            self.repair_particle_clock = 0.0

        if not wrap_stage:
            # Step 1: dead-center holding sets the post faster.
            if working:
                centered = max(
                    0.0,
                    1.0 - abs(self.post_lean) / CENTER_BAND,
                )
                self.set_time += dt * (1.0 + 0.8 * centered)

            if self.set_time >= SET_S:
                self.set_time = SET_S
                self.repair_stage = "wrap"
                self.wrap_phase = 0.0
                self.wrap_target = self.repair_rng.uniform(-0.55, 0.55)
                self._callout("Hold her. Wire's going on.", 1800)
                self._spawn_repair_particles(6)
                self.farm._snd().fence_creak()
            return

        # Step 2: the marker only moves while the post is steady.
        if working:
            self.wrap_phase += dt * (0.85 + 0.2 * self.wraps_done)

        if cinch_pressed and working and self.wrap_cooldown <= 0:
            self._cinch()

        if self.wraps_done >= WRAPS:
            self._finish_repair()

    def _spawn_repair_particles(self, count):
        base, top, _ = self._post_geometry()
        origin = base.lerp(top, 0.58)

        for _ in range(count):
            self.repair_particles.append(
                {
                    "pos": origin + pygame.Vector2(
                        self.repair_rng.uniform(-4, 4),
                        self.repair_rng.uniform(-3, 3),
                    ),
                    "vel": pygame.Vector2(
                        self.repair_rng.uniform(-22, 22),
                        self.repair_rng.uniform(-32, -9),
                    ),
                    "life": self.repair_rng.uniform(
                        0.25, 0.55
                    ),
                    "color": self.repair_rng.choice(
                        (
                            (156, 121, 75),
                            (189, 153, 96),
                            (113, 94, 65),
                        )
                    ),
                }
            )

    def _update_repair_particles(self, dt):
        alive = []

        for particle in self.repair_particles:
            particle["life"] -= dt

            if particle["life"] <= 0:
                continue

            particle["vel"].y += 85.0 * dt
            particle["pos"] += particle["vel"] * dt
            alive.append(particle)

        self.repair_particles = alive

    def _update_overlook(self, dt):
        if self.route_index < len(TO_OVERLOOK):
            if self._walk_bodi(
                vec(TO_OVERLOOK[self.route_index]),
                dt,
            ):
                self.route_index += 1
            return

        self.bodi_moving = False
        self.bodi_face = "d"
        distance = self._player().distance_to(OVERLOOK)

        if not self.overlook_spoken:
            if distance < 100:
                self.overlook_time += dt

                if self.overlook_time >= 2.5:
                    self.overlook_spoken = True
                    self.say(
                        (
                            "BODI",
                            "It's quiet up here. People from the city "
                            "always think that means nothing's happening.",
                        ),
                    )
            elif distance > 260:
                self._start_bike()

            return

        if not self.lines:
            self._start_bike()

    def _start_bike(self):
        self.phase = "bike"

        self.say(
            (
                "",
                "A dirt bike winds up somewhere below the orchard.",
            ),
            (
                "BODI",
                "That's not a tractor.",
            ),
        )

    def update(self, keys):
        if self.finished or keys is None:
            return (0, 0)

        self.time = now_ms()
        dt = max(
            0.0,
            min(
                0.05,
                (self.time - self.last_time) / 1000.0,
            ),
        )
        self.last_time = self.time
        self.farm._S["now"] = self.time

        down = self.farm._down
        advance = (
            down(keys, pygame.K_SPACE)
            or down(keys, pygame.K_RETURN)
        )

        if advance and not self.prev_adv:
            self.advance_dialogue()

        self.prev_adv = advance

        if self.lines and self.time >= self.line_until:
            self._next_line()

        # Once the short finishing animation ends, restore collision
        # and safely return the player to the north side.
        if (
            self.repaired
            and self.repair_finish_time is not None
            and not self._repair_finishing()
        ):
            self._rebuild_walls()
            self._release_player_after_repair()
            self.repair_finish_time = None

        self._move_player(keys, dt)
        self._update_repair_particles(dt)
        self._update_reveal_motes(dt)

        if self.phase == "outbound":
            self._update_outbound(dt)

        elif self.phase == "reveal":
            self._update_reveal(dt)

        elif self.phase == "approach":
            self._update_approach(dt)

        elif self.phase == "herd":
            self._update_herd(dt)

        elif self.phase in ("repair", "repairing"):
            self._update_repair(keys, dt)

        elif self.phase == "repair_talk":
            if not self.lines and not self._repair_finishing():
                self.phase = "overlook"
                self.route_index = 0

        elif self.phase == "overlook":
            self._update_overlook(dt)

        elif self.phase == "bike" and not self.lines:
            self.finished = True
            self.farm._finish()
            return (0, 0)

        # The reveal drives the camera itself.
        if self.phase != "reveal":
            self._update_camera(dt)

        self.farm._wildlife(self.time)

        return (0, 0)

    # -- camera ------------------------------------------------------------

    def _camera_target(self, focus=None, open_world=None):
        """Camera position that frames `focus` (default: the player).

        Until the reveal, the right limit is the ditch line, so the
        camera never scrolls toward the cut area.
        """
        if open_world is None:
            open_world = self.ditch_revealed

        point = (
            self._player()
            if focus is None
            else pygame.Vector2(focus)
        )

        target = point - pygame.Vector2(
            WIDTH / 2,
            HEIGHT / 2,
        )

        right_limit = (
            self.world_size[0] if open_world else CUT_X
        )
        low = -OX
        high = max(low, right_limit - WIDTH + OX)

        target.x = max(low, min(high, target.x))

        if self.world_size[1] + 2 * OY <= HEIGHT:
            target.y = -(
                HEIGHT - self.world_size[1]
            ) / 2
        else:
            target.y = max(
                -OY,
                min(
                    self.world_size[1] - HEIGHT + OY,
                    target.y,
                ),
            )

        return target

    def _update_camera(self, dt):
        self.camera += (
            self._camera_target() - self.camera
        ) * min(1.0, dt * 8.0)

    # -- fence drawing -----------------------------------------------------

    def _post_geometry(self):
        """Use the same small square post as the farm fence."""
        col, row = BROKEN_FENCE
        cx = col * T + T // 2
        cy = row * T + T // 2

        lean = 0.0 if self.repaired else self.post_lean

        base = pygame.Vector2(cx, cy + 8)
        top = pygame.Vector2(
            cx + lean * POST_TILT_PX,
            cy - 8,
        )

        axis = top - base
        side = pygame.Vector2(
            -axis.y, axis.x
        ).normalize() * 5.0

        return base, top, side

    def _draw_fence_ground(self):
        base, _, _ = self._post_geometry()
        bx, by = pixel(base)

        pygame.draw.ellipse(
            self.frame,
            (65, 59, 40),
            (bx - 10, by - 3, 22, 6),
        )
        pygame.draw.ellipse(
            self.frame,
            (112, 91, 58),
            (bx - 6, by - 2, 12, 4),
        )

        if not self.repaired:
            pygame.draw.line(
                self.frame,
                M.WOOD_D,
                (bx - 23, by + 3),
                (bx - 12, by + 6),
                4,
            )
            pygame.draw.line(
                self.frame,
                M.WOOD,
                (bx - 23, by + 2),
                (bx - 12, by + 5),
                2,
            )

            coil = pygame.Rect(
                bx + 15,
                by - 2,
                12,
                7,
            )
            pygame.draw.ellipse(
                self.frame,
                M.METAL_D,
                coil,
                2,
            )
            pygame.draw.ellipse(
                self.frame,
                M.METAL,
                coil.move(0, -1),
                1,
            )

    def _draw_repaired_fence(self):
        col, row = BROKEN_FENCE

        if self.repaired:
            self.farm._fence(
                self.frame,
                self.fence_grid,
                col,
                row,
            )
            return

        cx = col * T + T // 2
        cy = row * T + T // 2

        progress = self._repair_progress()

        base, top, _ = self._post_geometry()
        tilt = self.post_lean * POST_TILT_PX

        joint = pygame.Vector2(
            cx + tilt * 0.45,
            cy,
        )

        def linked(c, r):
            return (
                0 <= r < len(self.fence_grid)
                and 0 <= c < len(self.fence_grid[r])
                and self.fence_grid[r][c] in "#f"
            )

        def rail(a, b, vertical=False):
            a = pygame.Vector2(a)
            b = pygame.Vector2(b)

            shadow_offset = pygame.Vector2(3, 8)
            highlight_offset = pygame.Vector2(0, -4)
            body_offset = pygame.Vector2(0, -1)

            if vertical:
                shadow_offset.update(8, 3)
                highlight_offset.update(-4, 0)
                body_offset.update(-1, 0)

            pygame.draw.line(
                self.frame,
                (55, 44, 28),
                pixel(a + shadow_offset),
                pixel(b + shadow_offset),
                6,
            )
            pygame.draw.line(
                self.frame,
                M.WOOD_D,
                pixel(a),
                pixel(b),
                10,
            )
            pygame.draw.line(
                self.frame,
                M.WOOD,
                pixel(a + body_offset),
                pixel(b + body_offset),
                7,
            )
            pygame.draw.line(
                self.frame,
                M.WOOD_L,
                pixel(a + highlight_offset),
                pixel(b + highlight_offset),
                2,
            )

        for dx, dy in (
            (1, 0),
            (-1, 0),
            (0, 1),
            (0, -1),
        ):
            if not linked(col + dx, row + dy):
                continue

            edge = pygame.Vector2(
                cx + dx * T / 2,
                cy + dy * T / 2,
            )
            loose_joint = joint + pygame.Vector2(
                dx * 3 * (1.0 - progress),
                11 * (1.0 - progress),
            )

            rail(
                edge,
                loose_joint,
                vertical=bool(dy),
            )

        corners = (
            base + pygame.Vector2(-7, 0),
            top + pygame.Vector2(-7, 0),
            top + pygame.Vector2(7, 0),
            base + pygame.Vector2(7, 0),
        )
        pygame.draw.polygon(
            self.frame,
            M.INK,
            [pixel(point) for point in corners],
        )

        inner = (
            base + pygame.Vector2(-5, -2),
            top + pygame.Vector2(-5, 2),
            top + pygame.Vector2(5, 2),
            base + pygame.Vector2(5, -2),
        )
        pygame.draw.polygon(
            self.frame,
            M.WOOD,
            [pixel(point) for point in inner],
        )

        pygame.draw.line(
            self.frame,
            M.WOOD_L,
            pixel(top + pygame.Vector2(-4, 3)),
            pixel(top + pygame.Vector2(4, 3)),
            3,
        )
        pygame.draw.line(
            self.frame,
            M.WOOD_D,
            pixel(
                top.lerp(base, 0.45)
                + pygame.Vector2(3, 0)
            ),
            pixel(base + pygame.Vector2(3, -2)),
            3,
        )

        if self.wraps_done > 0:
            binding = top.lerp(base, 0.55)

            for index in range(min(3, self.wraps_done)):
                by = round(binding.y) - 2 + index * 2
                pygame.draw.line(
                    self.frame,
                    M.METAL_D,
                    (round(binding.x) - 5, by),
                    (round(binding.x) + 5, by),
                    1,
                )

        fastener = top.lerp(base, 0.5)
        self.frame.fill(
            M.METAL_D,
            (
                round(fastener.x) - 1,
                round(fastener.y) - 1,
                2,
                2,
            ),
        )

    # -- animated repair sprites ------------------------------------------

    def _repair_working(self):
        return (
            self.phase == "repairing"
            and self.repair_gripping
            and self.repair_stable
            and self.repair_bodi_ready
        )

    def _repair_hand_targets(self, look):
        """World-space hand positions shared by sprites and tools."""
        base, top, _ = self._post_geometry()
        joint = base.lerp(top, 0.56)

        finishing = self._repair_finishing()

        if look == "biribel":
            if self.repair_gripping or finishing:
                # Hands remain attached to the post as it leans.
                effort = math.sin(
                    self.repair_clock * 13.0
                ) * (
                    0.6 if not self.repair_stable else 0.2
                )

                return (
                    joint + pygame.Vector2(-5, -5 + effort),
                    joint + pygame.Vector2(-5, 4 + effort),
                )

            # Released pose: hands draw back toward the body.
            rect = STATE.player.rect
            feet = pygame.Vector2(
                rect.centerx,
                rect.bottom - 2,
            )

            return (
                feet + pygame.Vector2(10, -24),
                feet + pygame.Vector2(12, -16),
            )

        clock = self.repair_work_clock

        if finishing:
            elapsed = (
                self.time - self.repair_finish_time
            ) / REPAIR_FINISH_MS
            pull = math.sin(
                min(1.0, elapsed) * math.pi
            )

            return (
                joint + pygame.Vector2(4, -3),
                joint + pygame.Vector2(
                    6 + pull * 8,
                    3 - pull * 3,
                ),
            )

        if self._repair_working():
            angle = clock * math.tau * 2.1

            return (
                joint + pygame.Vector2(
                    4,
                    -3 + math.sin(angle) * 1.5,
                ),
                joint + pygame.Vector2(
                    5 + math.cos(angle) * 5,
                    3 + math.sin(angle) * 4,
                ),
            )

        # Bodi waits with the wire held close to the joint.
        breath = math.sin(self.time * 0.003) * 0.5

        return (
            joint + pygame.Vector2(5, -2 + breath),
            joint + pygame.Vector2(10, 6 + breath),
        )

    def _repair_base(self, look, face, blink):
        """Reuse the existing character's head, boots and palette."""
        key = (look, face, blink)
        cached = self.repair_base_cache.get(key)

        if cached is not None:
            return cached

        farm = self.farm

        original = farm._fig_frame(
            look,
            face,
            -1,
            0,
            blink,
            False,
            False,
        )

        native = pygame.transform.scale(
            original,
            (farm.FW, farm.FH),
        )

        self.repair_base_cache[key] = native
        return native

    def _repair_actor_sprite(
        self,
        look,
        face,
        feet,
        hand_targets,
    ):
        """Build a pixel pose with articulated sleeves and hands."""
        farm = self.farm
        scale = farm.PX
        cx = farm.FCX

        working = self._repair_working()
        finishing = self._repair_finishing()

        blink = (
            (
                self.time
                + farm._LOOK_PHASE.get(look, 0)
            ) % 3700
        ) < 120

        native_hands = []

        for target in hand_targets:
            local = pygame.Vector2(
                cx + (target.x - feet.x) / scale,
                farm.FBASE
                + (target.y - feet.y) / scale,
            )

            local.x = max(
                2, min(farm.FW - 3, local.x)
            )
            local.y = max(
                2, min(farm.FH - 3, local.y)
            )

            native_hands.append(pixel(local))

        anim_frame = (
            int(
                self.repair_work_clock
                * REPAIR_ANIM_FPS
            ) % 8
            if working
            else 0
        )

        if finishing:
            anim_frame = 8 + min(
                3,
                int(
                    (self.time - self.repair_finish_time)
                    / max(1, REPAIR_FINISH_MS / 4)
                ),
            )

        key = (
            look,
            face,
            blink,
            tuple(native_hands),
            anim_frame,
            self.repair_gripping,
            working,
            finishing,
        )

        cached = self.repair_sprite_cache.get(key)
        if cached is not None:
            return cached

        if (
            len(self.repair_sprite_cache)
            >= REPAIR_SPRITE_CACHE_LIMIT
        ):
            self.repair_sprite_cache.clear()

        p = farm._pal(look)
        canvas = self._repair_base(
            look, face, blink
        ).copy()

        clear = (0, 0, 0, 0)

        # Remove the original hanging sleeves and hands.
        canvas.fill(
            clear,
            (cx - 8, 10, 4, 9),
        )
        canvas.fill(
            clear,
            (cx + 4, 10, 5, 9),
        )

        # Rebuild the torso beneath the new bent arms.
        torso_x = cx - 4
        torso_y = 11

        canvas.fill(
            p["torso"],
            (torso_x, torso_y, 8, 7),
        )
        canvas.fill(
            p["torso_l"],
            (torso_x, torso_y, 7, 1),
        )
        canvas.fill(
            p["torso_l"],
            (torso_x, torso_y + 1, 1, 4),
        )
        canvas.fill(
            p["torso_d"],
            (cx + 3, torso_y + 1, 1, 6),
        )

        if look == "bodi":
            apron = farm._tone(p["torso"], 0.6)
            apron_x = cx - 3 if face == "l" else cx

            canvas.fill(
                apron,
                (apron_x, torso_y + 1, 3, 4),
            )

        canvas.fill(
            farm._BELT,
            (torso_x, torso_y + 5, 8, 1),
        )
        canvas.fill(
            p["torso_d"],
            (torso_x, torso_y + 6, 8, 1),
        )

        buckle_x = cx - 3 if face == "l" else cx + 2
        canvas.fill(
            farm._BUCKLE,
            (buckle_x, torso_y + 5, 1, 1),
        )

        sign = -1 if face == "l" else 1

        far_shoulder = pygame.Vector2(
            cx - sign * 2,
            torso_y + 1,
        )
        near_shoulder = pygame.Vector2(
            cx + sign,
            torso_y + 2,
        )

        def arm(shoulder, hand, near):
            hand = pygame.Vector2(hand)

            elbow = shoulder.lerp(hand, 0.48)
            elbow.y += 2 if near else 1

            if working and look == "bodi":
                elbow.y += (
                    1 if anim_frame % 4 < 2 else 0
                )

            sleeve = (
                p["arm"] if near else p["arm_d"]
            )

            pygame.draw.line(
                canvas,
                p["arm_d"],
                pixel(shoulder),
                pixel(elbow),
                3,
            )
            pygame.draw.line(
                canvas,
                sleeve,
                pixel(shoulder),
                pixel(elbow),
                2,
            )
            pygame.draw.line(
                canvas,
                sleeve,
                pixel(elbow),
                pixel(hand),
                2,
            )

            if near:
                canvas.fill(
                    p["arm_l"],
                    (
                        round(shoulder.x),
                        round(shoulder.y),
                        1,
                        2,
                    ),
                )

            canvas.fill(
                p["skin_d"],
                (
                    round(hand.x) - 1,
                    round(hand.y),
                    3,
                    2,
                ),
            )
            canvas.fill(
                p["skin"],
                (
                    round(hand.x) - 1,
                    round(hand.y),
                    2,
                    1,
                ),
            )

            if near and p.get("patch"):
                patch_at = shoulder.lerp(elbow, 0.35)
                canvas.fill(
                    p["patch"],
                    (
                        round(patch_at.x),
                        round(patch_at.y),
                        2,
                        2,
                    ),
                )

        arm(far_shoulder, native_hands[0], False)
        arm(near_shoulder, native_hands[1], True)

        image = farm._ink_scaled(canvas)
        self.repair_sprite_cache[key] = image
        return image

    def _draw_repair_actor(self, look, x, y):
        farm = self.farm
        feet = pygame.Vector2(x, y)
        face = "r" if look == "biribel" else "l"
        hands = self._repair_hand_targets(look)

        image = self._repair_actor_sprite(
            look,
            face,
            feet,
            hands,
        )

        self.frame.blit(
            farm._drop_shadow(12, 4),
            (round(x) - 12, round(y) - 5),
        )
        self.frame.blit(
            image,
            (
                round(x) - farm.FCX * farm.PX,
                round(y) - farm.FBASE * farm.PX,
            ),
        )

        if look == "bodi":
            self._draw_repair_tool(hands)

    def _draw_repair_tool(self, hands):
        """Pliers and loose binding follow Bodi's working hand."""
        if not self.repair_bodi_ready:
            return

        fixed, moving = hands
        base, top, _ = self._post_geometry()
        joint = base.lerp(top, 0.56)

        working = self._repair_working()
        finishing = self._repair_finishing()

        # Short loose wire from the post to the tool.
        bend = joint.lerp(moving, 0.5)
        bend.y += (
            2
            + math.sin(
                self.repair_work_clock * 11
            ) * (2 if working else 0.5)
        )

        pygame.draw.lines(
            self.frame,
            M.INK,
            False,
            (
                pixel(joint),
                pixel(bend),
                pixel(moving),
            ),
            3,
        )
        pygame.draw.lines(
            self.frame,
            M.METAL,
            False,
            (
                pixel(joint),
                pixel(bend),
                pixel(moving),
            ),
            1,
        )

        angle = -0.8

        if working:
            angle += math.sin(
                self.repair_work_clock * 13.0
            ) * 0.7
        elif finishing:
            angle -= 0.4

        axis = pygame.Vector2(
            math.cos(angle),
            math.sin(angle),
        )
        side = pygame.Vector2(-axis.y, axis.x)

        pivot = moving + pygame.Vector2(1, 0)
        jaw = pivot - axis * 5

        opening = (
            1.0
            + (
                0.5
                + 0.5 * math.sin(
                    self.repair_work_clock * 16.0
                )
            ) * 2.0
            if working
            else 2.0
        )

        for sign in (-1, 1):
            handle_end = (
                pivot
                + axis * 7
                + side * opening * sign
            )
            jaw_end = jaw + side * sign * 2

            pygame.draw.line(
                self.frame,
                M.INK,
                pixel(jaw_end),
                pixel(handle_end),
                4,
            )
            pygame.draw.line(
                self.frame,
                M.METAL,
                pixel(jaw_end),
                pixel(pivot),
                2,
            )
            pygame.draw.line(
                self.frame,
                (132, 66, 43),
                pixel(pivot),
                pixel(handle_end),
                2,
            )

        self.frame.fill(
            (204, 207, 184),
            (
                round(pivot.x) - 1,
                round(pivot.y) - 1,
                2,
                2,
            ),
        )

        # Small periodic metal glint rather than a spark effect.
        if (
            working
            and int(self.repair_work_clock * 12) % 8 == 0
        ):
            gx, gy = pixel(jaw)

            pygame.draw.line(
                self.frame,
                (236, 233, 195),
                (gx - 2, gy),
                (gx + 2, gy),
                1,
            )
            pygame.draw.line(
                self.frame,
                (236, 233, 195),
                (gx, gy - 2),
                (gx, gy + 2),
                1,
            )

    # -- world drawing -----------------------------------------------------

    def _draw_farm_changes(self):
        farm = self.farm
        layer = self.farm_layer

        area = pygame.Rect(
            0,
            0,
            M.COLS * T,
            M.ROWS * T,
        )

        layer.blit(
            self.static,
            M.ORIGIN,
            area,
        )

        farm._draw_generator(layer, self.time)
        farm._draw_tractor(layer, self.time)
        farm._draw_trough(layer)
        farm._draw_hay(layer)

        self.frame.blit(
            layer,
            (0, 0),
            area.move(M.ORIGIN),
        )

    def _prompt(self, surface, point, text):
        from engine.ui import prompt

        x, y = point - self.camera

        prompt.draw(
            surface,
            round(x),
            round(y),
            text,
            (236, 228, 196),
            font=font_prompt,
        )

    def _draw_sorted_world(self):
        farm = self.farm
        S = farm._S
        rect = STATE.player.rect

        fence_depth = (
            BROKEN_FENCE[1] * T + T // 2
        )
        repair_pose = self._repair_actor_active()

        jobs = [
            (
                self.bodi.y + 14,
                "person",
                (
                    self.bodi.x,
                    self.bodi.y + 14,
                    self.bodi_face,
                    self.bodi_step,
                    "bodi",
                    self.bodi_moving,
                ),
            ),
            (
                rect.bottom - 2,
                "person",
                (
                    rect.centerx,
                    rect.bottom - 2,
                    S["face"],
                    S["step"],
                    "biribel",
                    S["moving"],
                ),
            ),
            (
                self.goat.y + 6,
                "goat",
                (),
            ),
            (
                fence_depth,
                "fence",
                (),
            ),
        ]

        for depth, image, position in self.tree_sprites:
            jobs.append(
                (
                    depth,
                    "tree",
                    (image, position),
                )
            )

        for depth, function, args in farm._animal_jobs(
            self.time
        )[1:]:
            jobs.append(
                (
                    depth - OY,
                    "farm_animal",
                    (function, args),
                )
            )

        for particle in self.repair_particles:
            jobs.append(
                (
                    fence_depth + 30,
                    "repair_particle",
                    (particle,),
                )
            )

        for _, kind, args in sorted(
            jobs,
            key=lambda job: job[0],
        ):
            if kind == "tree":
                image, position = args
                self.frame.blit(image, position)

            elif kind == "person":
                x, y, face, step, look, moving = args

                animated_repair = (
                    repair_pose
                    and (
                        look == "biribel"
                        or (
                            look == "bodi"
                            and self.repair_bodi_ready
                        )
                    )
                )

                if animated_repair:
                    self._draw_repair_actor(
                        look,
                        x,
                        y,
                    )
                else:
                    farm._figure(
                        self.frame,
                        round(x),
                        round(y),
                        face,
                        step,
                        look,
                        moving=moving,
                    )

            elif kind == "goat":
                farm._goat(
                    self.frame,
                    round(self.goat.x),
                    round(self.goat.y),
                    GOAT_COLOR,
                    self.goat_right,
                    (self.time // 170) % 2,
                    self.goat_moving,
                    not self.goat_moving,
                )

            elif kind == "fence":
                self._draw_repaired_fence()

            elif kind == "farm_animal":
                self.animal_layer.fill(
                    (0, 0, 0, 0)
                )

                function, animal_args = args
                function(
                    self.animal_layer,
                    *animal_args
                )

                self.frame.blit(
                    self.animal_layer,
                    (-OX, -OY),
                )

            elif kind == "repair_particle":
                particle = args[0]
                px, py = pixel(particle["pos"])

                self.frame.fill(
                    particle["color"],
                    (px, py, 2, 2),
                )

    # -- reveal drawing ----------------------------------------------------

    def _draw_reveal_motes(self):
        for mote in self.reveal_motes:
            fade = min(
                1.0,
                mote["life"] / 0.6,
                (mote["max"] - mote["life"]) / 0.3,
            )
            level = clamp01(fade) * 0.85

            if level <= 0.0:
                continue

            x, y = pixel(mote["pos"])
            self.frame.fill(
                (
                    round(255 * level),
                    round(226 * level),
                    round(150 * level),
                ),
                (x, y, mote["size"], mote["size"]),
                special_flags=pygame.BLEND_RGB_ADD,
            )

    def _draw_reveal_cover(self):
        """Hide everything east of the ditch, then wipe it away."""
        if self.ditch_revealed:
            return

        width, height = self.world_size

        if self.reveal_wipe <= 0.0:
            self.frame.fill(
                M.SKY_EDGE,
                (CUT_X, 0, width - CUT_X, height),
            )
            return

        edge = round(self._reveal_edge())
        fade = max(
            1,
            round(
                REVEAL_FADE_W
                * smoothstep(self.reveal_wipe * 6.0)
            ),
        )

        if edge < width:
            self.frame.fill(
                M.SKY_EDGE,
                (edge, 0, width - edge, height),
            )

        self.frame.blit(
            pygame.transform.scale(
                self.reveal_fog, (fade, height)
            ),
            (edge - fade, 0),
        )
        self.frame.blit(
            self.reveal_glow,
            (edge - REVEAL_GLOW_W, 0),
            special_flags=pygame.BLEND_RGB_ADD,
        )

    def _draw_reveal_overlay(self, surface):
        """Screen-space polish: vignette, warm bloom, bars, caption."""
        if self.phase != "reveal":
            return

        bars = self.reveal_bars

        if bars > 0.0:
            self.reveal_vignette.set_alpha(round(255 * bars))
            surface.blit(self.reveal_vignette, (0, 0))

        # Warm bloom that peaks while the wipe crosses the screen.
        tint = round(16 * math.sin(math.pi * self.reveal_wipe))

        if tint > 0:
            surface.fill(
                (tint, round(tint * 0.8), round(tint * 0.45)),
                special_flags=pygame.BLEND_RGB_ADD,
            )

        bar_h = round(REVEAL_BAR_H * bars)

        if bar_h > 0:
            surface.fill((8, 8, 7), (0, 0, WIDTH, bar_h))
            surface.fill(
                (8, 8, 7), (0, HEIGHT - bar_h, WIDTH, bar_h)
            )

        k = self.reveal_caption

        if k > 0.0:
            text = font_prompt.render(
                REVEAL_CAPTION, True, (236, 228, 196)
            )
            text.set_alpha(round(255 * k))

            x = WIDTH // 2 - text.get_width() // 2
            y = REVEAL_BAR_H // 2 - text.get_height() // 2 - 3
            surface.blit(text, (x, y))

            rule = round(text.get_width() * 1.4 * k)
            rule_y = y + text.get_height() + 3
            pygame.draw.line(
                surface,
                (151, 133, 91),
                (WIDTH // 2 - rule // 2, rule_y),
                (WIDTH // 2 + rule // 2, rule_y),
                1,
            )

    # -- repair interface --------------------------------------------------

    def _draw_repair_ui(self, surface):
        center_x = WIDTH // 2
        panel_width = min(440, WIDTH - 24)
        panel = pygame.Rect(
            center_x - panel_width // 2, 72, panel_width, 164
        )

        shadow = pygame.Surface(panel.size, pygame.SRCALPHA)
        shadow.fill((15, 18, 14, 225))
        surface.blit(shadow, panel.topleft)
        pygame.draw.rect(surface, (151, 133, 91), panel, 2)
        pygame.draw.rect(
            surface, (69, 68, 49), panel.inflate(-6, -6), 1
        )

        wrap_stage = self.repair_stage == "wrap"

        def centered_text(text, y, color):
            image = font_prompt.render(text, True, color)
            available = panel.w - 16

            if image.get_width() > available:
                scale = available / image.get_width()
                image = pygame.transform.scale(
                    image,
                    (
                        available,
                        max(1, round(image.get_height() * scale)),
                    ),
                )

            surface.blit(
                image,
                (center_x - image.get_width() // 2, y),
            )

        centered_text(
            "STEP 2 OF 2 - WRAP THE WIRE"
            if wrap_stage
            else "STEP 1 OF 2 - SET THE POST",
            panel.y + 8,
            (173, 169, 143),
        )

        warm, green = (232, 185, 123), (190, 216, 151)
        neutral = (236, 228, 196)

        if not self.repair_gripping:
            label, color = "HOLD E TO GRIP THE POST", neutral
        elif not self.repair_bodi_ready:
            label, color = "KEEP IT STEADY - BODI IS COMING", neutral
        elif not self.repair_stable:
            label, color = "A / D OR ARROWS - COUNTER THE LEAN", warm
        elif wrap_stage:
            label, color = "SPACE - CINCH WHEN THE MARKER IS GREEN", green
        elif abs(self.post_lean) < CENTER_BAND:
            label, color = "DEAD CENTER - SETTING FASTER", green
        else:
            label, color = "STEADY - BODI IS SETTING THE POST", green

        centered_text(label, panel.y + 26, color)

        # Lean track
        track_width = min(320, panel.w - 110)
        track = pygame.Rect(
            center_x - track_width // 2, panel.y + 54, track_width, 16
        )
        surface.fill((65, 53, 40), track)

        extent = track.w / 2 - 4
        safe_half = round(extent * POST_SAFE_LEAN)
        center_half = round(extent * CENTER_BAND)

        surface.fill(
            (91, 130, 71) if self.repair_stable else (62, 92, 53),
            (center_x - safe_half, track.y, safe_half * 2, track.h),
        )
        surface.fill(
            (120, 168, 92),
            (center_x - center_half, track.y, center_half * 2, track.h),
        )
        pygame.draw.line(
            surface,
            (169, 192, 132),
            (center_x, track.y),
            (center_x, track.bottom - 1),
            1,
        )
        pygame.draw.rect(surface, (139, 126, 91), track, 1)

        marker_x = center_x + round(self.post_lean * extent)
        marker_color = (
            (225, 237, 179) if self.repair_stable else (232, 173, 107)
        )
        pygame.draw.polygon(
            surface,
            marker_color,
            (
                (marker_x - 5, track.y - 7),
                (marker_x + 5, track.y - 7),
                (marker_x, track.y - 1),
            ),
        )
        pygame.draw.rect(
            surface,
            marker_color,
            (marker_x - 2, track.y - 1, 4, track.h + 4),
        )

        # Gust telegraph: chevrons at the side the wind pushes toward.
        if self.gust_state != "idle" and self.repair_bodi_ready:
            blowing = self.gust_state == "blow"
            if blowing or int(self.repair_clock * 10) % 2 == 0:
                d = self.gust_dir
                chevron = (232, 185, 123) if blowing else (205, 200, 160)
                edge = track.right + 10 if d > 0 else track.left - 10
                cy = track.centery

                for i in range(3):
                    x = edge + d * i * 9
                    pygame.draw.polygon(
                        surface,
                        chevron,
                        (
                            (x, cy - 6),
                            (x, cy + 6),
                            (x + d * 7, cy),
                        ),
                    )

        centered_text(
            "A / LEFT          D / RIGHT",
            panel.y + 74,
            (173, 169, 143),
        )

        # Step section: set-progress bar, or the cinch timing bar.
        section = pygame.Rect(track.x, panel.y + 94, track.w, 16)
        surface.fill((65, 53, 40), section)

        if wrap_stage:
            sext = section.w / 2 - 4
            good = WRAP_GOOD + (
                WRAP_ASSIST if self.wrap_misses >= 2 else 0.0
            )
            tx = center_x + round(self.wrap_target * sext)
            gh = round(good * sext)
            ph = round(WRAP_PERFECT * sext)

            surface.fill(
                (62, 92, 53), (tx - gh, section.y, gh * 2, section.h)
            )
            surface.fill(
                (120, 168, 92), (tx - ph, section.y, ph * 2, section.h)
            )

            border = (139, 126, 91)
            if self.wrap_flash > 0:
                border = {
                    "perfect": (225, 237, 179),
                    "good": (169, 192, 132),
                    "miss": (214, 96, 74),
                }.get(self.wrap_result, border)
            pygame.draw.rect(
                surface,
                border,
                section,
                2 if self.wrap_flash > 0 else 1,
            )

            mx = center_x + round(self._wrap_marker() * sext)
            pygame.draw.rect(
                surface,
                (236, 228, 196)
                if self.repair_stable
                else (150, 145, 125),
                (mx - 2, section.y - 3, 4, section.h + 6),
            )
        else:
            fill = round(section.w * min(1.0, self.set_time / SET_S))
            if fill:
                surface.fill(
                    (110, 150, 84), (section.x, section.y, fill, section.h)
                )
            pygame.draw.rect(surface, (139, 126, 91), section, 1)

        # Overall progress + wrap pips
        bar = pygame.Rect(track.x, panel.y + 124, track.w - 70, 10)
        surface.fill((58, 54, 41), bar)

        fill_width = round(bar.w * self._repair_progress())
        if fill_width:
            surface.fill(
                (165, 151, 91), (bar.x, bar.y, fill_width, bar.h)
            )
            surface.fill(
                (204, 191, 126), (bar.x, bar.y, fill_width, 2)
            )
        pygame.draw.rect(surface, (123, 114, 79), bar, 1)

        for i in range(WRAPS):
            pip = (bar.right + 22 + i * 20, bar.centery)
            if i < self.wraps_done:
                pygame.draw.circle(surface, (204, 191, 126), pip, 6)
            pygame.draw.circle(surface, (123, 114, 79), pip, 6, 1)

        text, until = self.repair_callout
        if text and self.time < until:
            centered_text(f"BODI: {text}", panel.y + 142, (232, 205, 150))
        else:
            centered_text(
                "Progress is saved when you let go.",
                panel.y + 142,
                (181, 176, 153),
            )

    # -- presentation ------------------------------------------------------

    def draw(self, surface):
        from cutscenes.engine import draw_dialogue_box
        from ui import hud

        farm = self.farm
        self.time = now_ms()
        farm._S["now"] = self.time

        self.frame.blit(
            self.static,
            (0, 0),
        )
        self._draw_farm_changes()
        self._draw_fence_ground()
        self._draw_sorted_world()
        self._draw_reveal_motes()
        self._draw_reveal_cover()

        surface.fill(M.SKY_EDGE)
        surface.blit(
            self.frame,
            (
                -round(self.camera.x),
                -round(self.camera.y),
            ),
        )

        # The reveal is a clean cinematic: no HUD, no prompts.
        if self.phase != "reveal":
            hud.draw_objective_panel(
                surface,
                self._objective_text(),
                x=20,
                y=16,
            )

            if not self.lines:
                if self._near_post():
                    self._prompt(
                        surface,
                        POST,
                        "[E] HOLD THE POST",
                    )
                elif self._near_hay():
                    self._prompt(
                        surface,
                        vec(M.POINTS["hay"]["at"]),
                        "[E] SEARCH THE HAY",
                    )

        if self.phase == "repairing":
            self._draw_repair_ui(surface)

        self._draw_reveal_overlay(surface)

        if self.lines:
            who, line = self.lines[0]

            count = max(
                0,
                min(
                    len(line),
                    (self.time - self.line_t0)
                    // farm.CHAR_MS,
                ),
            )

            if count // 3 > self.tick_n // 3:
                farm._snd().dialogue_tick()

            self.tick_n = count

            draw_dialogue_box(
                surface,
                who,
                line,
                count,
                len(line),
                can_continue=count >= len(line),
                show_speaker=bool(who),
            )
        else:
            text, until = self.toast

            if (
                text
                and self.time < until
                and self.phase != "repairing"
            ):
                farm._draw_toast(surface, text)