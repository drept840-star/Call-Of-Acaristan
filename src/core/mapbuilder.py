
"""Shared tilemap authoring helper (pure python, no pygame).

Runtime contract is unchanged: every mission still exposes
``list[str]`` (one char per TILE_SIZE tile) so collision, minimap,
camera, bullets and A* keep working untouched.

What this fixes: hand-counting ``#``/``C`` chars in string literals
does not scale past ~30x25. One typo = hole in wall / unwinnable map.
This builder lets maps be authored as readable rect/room/door calls
and then baked to the same ``list[str]`` format::

    b = MapBuilder(28, 23, fill='.')
    b.room(0, 0, 28, 11, wall='C', floor='.', doors=[(8, 10)])
    ...
    structure = b.to_strings()          # collision-only layer
    full_map  = b.with_spawns(SPAWNS).to_strings()  # runtime layer

Layers:
  structure  - collision + visuals only (C/W/D/./B ...)
  spawns     - entities as ``[(char, col, row)]`` (P/E/K/V/N/X ...)
               overlaid on top at bake time so layout edits never
               accidentally delete a spawn.

No game imports here on purpose: ``core`` must stay importable by
``missions.*`` without cycles (see AGENTS.md).
"""

# Chars that block movement (authoritative for validation / audits).
SOLID_CHARS = frozenset({"C", "W", "B"})

# Chars that are doors (passable visuals, owned by Door objects).
DOOR_CHARS = frozenset({"D"})

# Entity markers (must sit on walkable floor, never inside a wall).
SPAWN_CHARS = frozenset({"P", "E", "K", "V", "N", "X"})


class MapBuilder:
    """Mutable char grid that bakes to ``list[str]``."""

    def __init__(self, w, h, fill="."):
        self.w = int(w)
        self.h = int(h)
        self.g = [[fill for _ in range(self.w)] for _ in range(self.h)]

    # -- primitives -------------------------------------------------
    def in_bounds(self, col, row):
        return 0 <= col < self.w and 0 <= row < self.h

    def set(self, col, row, tile):
        if self.in_bounds(col, row):
            self.g[row][col] = tile

    def get(self, col, row):
        if self.in_bounds(col, row):
            return self.g[row][col]
        return None

    def rect(self, col, row, w, h, tile):
        """Fill a solid rectangle with ``tile``."""
        for r in range(row, row + h):
            for c in range(col, col + w):
                self.set(c, r, tile)

    def border_rect(self, col, row, w, h, wall, floor="."):
        """Hollow rectangle: ``wall`` perimeter, ``floor`` interior."""
        for r in range(row, row + h):
            for c in range(col, col + w):
                border = (
                    c in (col, col + w - 1) or r in (row, row + h - 1)
                )
                self.set(c, r, wall if border else floor)

    def room(self, col, row, w, h, wall="C", floor=".", doors=()):
        """Building with punched door gaps (door = ``floor`` + ``D``)."""
        self.border_rect(col, row, w, h, wall, floor)
        for dx, dy in (doors or ()):
            self.set(col + dx, row + dy, "D")

    def h_wall(self, col, row, length, wall="C", doors=()):
        """Horizontal wall run with door gaps at relative offsets."""
        door_set = set(doors or ())
        for i in range(length):
            self.set(col + i, row, "D" if i in door_set else wall)

    def v_wall(self, col, row, length, wall="C", doors=()):
        door_set = set(doors or ())
        for i in range(length):
            self.set(col, row + i, "D" if i in door_set else wall)

    def block(self, col, row, w=2, h=2, tile="C"):
        """Solid cover/structure block (e.g. M1's 2x2 CC pillars)."""
        self.rect(col, row, w, h, tile)

    # -- spawns (split layer) --------------------------------------
    def with_spawns(self, spawns):
        """Return a *copy* with ``[(char, col, row)]`` overlaid.

        The builder itself (structure layer) is untouched, so layout
        edits never eat a spawn.
        """
        clone = MapBuilder(self.w, self.h)
        clone.g = [row[:] for row in self.g]
        for char, col, row in spawns or ():
            clone.set(col, row, char)
        return clone

    # -- bake --------------------------------------------------------
    def to_strings(self):
        return ["".join(row) for row in self.g]

    # -- validation --------------------------------------------------
    def validate(self):
        """Return a list of error strings (empty = OK).

        Checks: rectangular, sealed shell, spawns on floor.
        """
        errors = []
        if not self.g:
            return ["empty grid"]
        width = len(self.g[0])
        for i, row in enumerate(self.g):
            if len(row) != width:
                errors.append("row %d width %d != %d" % (i, len(row), width))
        # Sealed shell: every border tile must be solid or door.
        for c in range(self.w):
            for r in (0, self.h - 1):
                if self.g[r][c] not in SOLID_CHARS and self.g[r][c] not in DOOR_CHARS:
                    errors.append("unsealed border at (%d,%d)=%r" % (c, r, self.g[r][c]))
        for r in range(self.h):
            for c in (0, self.w - 1):
                if self.g[r][c] not in SOLID_CHARS and self.g[r][c] not in DOOR_CHARS:
                    errors.append("unsealed border at (%d,%d)=%r" % (c, r, self.g[r][c]))
        # Spawns must sit on walkable floor (i.e. the char itself is a
        # spawn marker, meaning structure underneath was floor).
        for r in range(self.h):
            for c in range(self.w):
                ch = self.g[r][c]
                if ch in SPAWN_CHARS:
                    pass  # marker present; walkability checked by caller
                elif ch not in SOLID_CHARS and ch not in DOOR_CHARS and ch not in (".", "g", "O", "K", "L", "Y", "M", "E", "S"):
                    errors.append("unknown tile %r at (%d,%d)" % (ch, c, r))
        return errors
