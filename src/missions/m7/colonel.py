# src/missions/m7/colonel.py
"""Colonel Paie: the scarecrow easter egg on Bodi's farm.

Drawn as a real pixel sprite (character grid + palette) and scaled with
nearest-neighbour, so it matches the game's pixel art: chunky pixels,
1-pixel dark outlines, flat shading.

Lore: "Paie" is Romanian for straw. The medals are paper (a Vostral
reference), and the forms in his pocket echo Decree 47.
"""
import pygame

# ---------------------------------------------------------------- tuning
PX = 2              # screen pixels per art pixel (matches player and house)
GLINT_PERIOD_MS = 2400
GLINT_LEN_MS = 220

# ---------------------------------------------------------------- dialogue
# (speaker | None, text). None = narration. farmyard's adapter handles case.
STAGES = [
    # 0: first look
    [
        (None, "An old coat, three sizes too big, hangs off a fence post. "
               "Red armband. A flour-sack cap."),
        (None, "Down the front, a row of medals: bottle caps, cardboard, "
               "a chocolate wrapper."),
        ("Bodi", "Don't salute. It goes to his head."),
    ],
    # 1: the medals
    [
        ("Biribel", "Paper."),
        ("Bodi", "Cardboard, mostly. The foil ones were chocolate. "
                 "You'd know about paper medals."),
        ("Bodi", "Crows respect a medal. They never ask for the paperwork."),
    ],
    # 2: the pocket
    [
        (None, "A pocket stuffed with paper. FORM 47-C: TRANSFER OF "
               "STRATEGIC PRIVATE HOLDING. Every signature line is empty."),
        ("Bodi", "They send the forms before they send the men. This lot "
                 "came with the notice for the lower field. Good stuffing."),
        ("Biribel", "Somebody built a whole war out of blank forms once."),
        ("Bodi", "Mine are at least keeping something warm."),
    ],
    # 3: the name, and the keepsake
    [
        (None, "A tag pinned inside the collar: Colonel Paie. Twelve years "
               "at his post. Never retreated, never fought. "
               "Spotless record."),
        ("Bodi", "Three soldiers have stood on that porch this month. Each "
                 "one guessed who he looks like. Don't be the fourth."),
        ("Bodi", "Here. Don't say I never gave you a medal."),
    ],
]

IDLE = [
    "You salute. The cap slips an inch. A crow laughs somewhere.",
    "Colonel Paie holds the line. The line is a vegetable patch.",
    "The paper medals rustle. Nobody checks them.",
]

# ---------------------------------------------------------------- sprite
PALETTE = {
    "K": (24, 18, 20),        # outline
    "c": (140, 92, 58),       # coat
    "l": (172, 120, 78),      # coat light
    "C": (102, 66, 44),       # coat dark
    "S": (224, 216, 198),     # sack light
    "s": (198, 188, 168),     # sack
    "d": (152, 142, 126),     # sack shade
    "h": (122, 82, 52),       # cap
    "H": (178, 136, 94),      # cap brim
    "r": (190, 52, 44),       # armband / ribbon red
    "R": (138, 36, 34),       # red shade
    "b": (60, 110, 170),      # ribbon blue
    "w": (238, 232, 216),     # paper medal
    "G": (226, 176, 64),      # gold medal (glints)
    "g": (208, 160, 52),      # brass button
    "y": (208, 176, 86),      # straw
    "Y": (160, 130, 60),      # straw shade
    "p": (126, 88, 56),       # post
    "P": (92, 62, 40),        # post shade
    "x": (20, 10, 0, 70),     # shadow (alpha)
    "k": (38, 36, 48),        # crow
    "o": (220, 150, 50),      # crow beak and feet
}
GLINT_COLOR = (255, 242, 176)


def _body(inner):
    """Coat row: 8 inner pixels framed by outline, padded to 20 wide."""
    return ".....K" + inner + "K....."


SPRITE = [
    ".......KKKKKK.......",   # 0  cap top
    "......KhhhhhhK......",   # 1  crown
    ".....KHHHHHHHHK.....",   # 2  brim
    "......KKKKKKKK......",   # 3
    "......KSSsssdK......",   # 4  sack head
    "......KSKssKdK......",   # 5  eyes
    "......KSssssdK......",   # 6
    "......KsKsKsdK......",   # 7  stitched mouth
    ".......KyYyYK.......",   # 8  rope at the neck
    ".....KKKKKKKKKK.....",   # 9  shoulders
    "..KKKKKKKKKKKKKKKK..",   # 10 arm top
    "yyKlrrcccccccccccKyy",   # 11 arms + red armband (left)
    "YyKCrRCCCCCCCCCCCKyY",   # 12
    "..KKKKcCKccKCcKKKK..",   # 13 arm bottom + collar
    _body("cbrbrccC"),        # 14 medal ribbons
    _body("cwGwGccC"),        # 15 medals (paper, gold, paper, gold)
    _body("lcccccCC"),        # 16
    _body("lcccgcCC"),        # 17 brass button
    _body("lccccwwC"),        # 18 forms poking out of the pocket
    _body("lcccgKKC"),        # 19 pocket line
    _body("CCCCCCCC"),        # 20 hem
    ".....KKKKKKKKKK.....",   # 21
    "........KpPK........",   # 22 post
    "........KpPK........",   # 23
    "........KpPK........",   # 24
    "......xxKpPKxx......",   # 25 base + shadow
    "....xxxxxxxxxxxx....",   # 26
    "......xxxxxxxx......",   # 27
]
FOOT_ROW = 26      # post meets the ground at the bottom edge of row 25
CENTER_COL = 10    # post centre (art px)

CROW = [
    "..kk..",
    ".kwkk.",
    "okkkkk",
    ".kkkk.",
    "..o.o.",
]
CROW_POS = (14, 5)   # art px; feet land on the right arm


def _paint(surface, rows, ox, oy, glint):
    for y, row in enumerate(rows):
        for x, ch in enumerate(row):
            if ch == ".":
                continue
            if ch == "G" and glint:
                col = GLINT_COLOR
            else:
                col = PALETTE.get(ch)
            if col is not None:
                surface.set_at((ox + x, oy + y), col)


_CACHE = {}


def _sprite(glint, crow):
    key = (glint, crow, PX)
    surf = _CACHE.get(key)
    if surf is None:
        w, h = len(SPRITE[0]), len(SPRITE)
        small = pygame.Surface((w, h), pygame.SRCALPHA)
        _paint(small, SPRITE, 0, 0, glint)
        if crow:
            _paint(small, CROW, CROW_POS[0], CROW_POS[1], glint)
        surf = pygame.transform.scale(small, (w * PX, h * PX))
        _CACHE[key] = surf
    return surf


# ---------------------------------------------------------------- class
class ColonelPaie:
    def __init__(self, M, say_lines, toast):
        self.M = M
        self._say = say_lines
        self._toast = toast
        tx, ty = M.COLONEL_TILE
        self.foot = (int(tx * M.TILE), int(ty * M.TILE))
        self.stage = 0
        self.idle_i = 0
        self.crow_gone = False

    # ---- geometry (map pixels unless noted)
    @property
    def sort_y(self):
        return self.M.ORIGIN[1] + self.foot[1]

    def map_rect(self):
        # small collision box around the post, sized for PX = 2
        fx, fy = self.foot
        return pygame.Rect(fx - 6, fy - 6, 12, 6)

    def screen_rect(self):
        r = self.map_rect()
        r.move_ip(*self.M.ORIGIN)
        return r

    # ---- interaction
    def interact(self):
        if self.stage < len(STAGES):
            lines = STAGES[self.stage]
            last = self.stage == len(STAGES) - 1
            self.stage += 1
            self.crow_gone = True
            if last:
                try:
                    self._say(lines, after=self._give_button)
                except TypeError:
                    self._say(lines)
                    self._give_button()
            else:
                self._say(lines)
        else:
            self._toast(IDLE[self.idle_i % len(IDLE)])
            self.idle_i += 1

    def _give_button(self):
        from . import farmyard  # lazy: reuse farmyard's STATE, no import-path guess
        farmyard.STATE.m7_colonel_button = True
        self._toast("Brass button acquired.")

    # ---- drawing
    def draw(self, surface):
        ox, oy = self.M.ORIGIN
        fx, fy = self.foot
        t = pygame.time.get_ticks()
        glint = (t % GLINT_PERIOD_MS) < GLINT_LEN_MS
        img = _sprite(glint, not self.crow_gone)
        x = int(ox + fx - CENTER_COL * PX)
        y = int(oy + fy - FOOT_ROW * PX)
        surface.blit(img, (x, y))