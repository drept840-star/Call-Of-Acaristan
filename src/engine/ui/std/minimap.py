"""MiniMap - the corner minimap panel.

Body moved verbatim from ``src/ui/hud.py`` (A-009): the only changes are the
three injected names (``WIDTH`` / ``HEIGHT`` / ``font_terminal_small`` read from
the ``Theme``) and the optional ``theme`` argument of ``__init__``. The legacy
name in ``src/ui/hud.py`` is a subclass shim that pins the game theme, so every
call site keeps its old signature.
"""
from __future__ import annotations

import math

import pygame

from engine.text import T

from ..theme import Theme

__all__ = ["MiniMap"]


class MiniMap:
    def __init__(self, map_data, tile_size=64, palette="m2", *, theme=None):
        self._theme = theme or Theme()
        self.tile_size = tile_size
        self._palette = palette if palette in ("m1", "m2", "m3", "m4", "m6", "walk") else "m2"
        self.map_w = len(map_data[0])
        self.map_h = len(map_data)
        self.world_w = self.map_w * tile_size
        self.world_h = self.map_h * tile_size
        self.minimap_w = 160
        self.minimap_h = 160
        # Uniform scale + letterbox: independent scale_x/scale_y squashed
        # non-square maps (walk is 46x12, M2 is 70x80) so the panel read as
        # abstract blobs rather than a mini map. One scale preserves aspect;
        # the map is centered and the bars stay panel background.
        self.scale = min(self.minimap_w / self.world_w,
                         self.minimap_h / self.world_h)
        self.map_pw = self.world_w * self.scale
        self.map_ph = self.world_h * self.scale
        self.map_ox = (self.minimap_w - self.map_pw) / 2.0
        self.map_oy = (self.minimap_h - self.map_ph) / 2.0
        # Kept for backwards compat (nothing outside hud.py reads these,
        # but external probes might). Both axes share the uniform scale.
        self.scale_x = self.scale
        self.scale_y = self.scale
        self.margin = 10
        self.x = self._theme.width - self.minimap_w - self.margin
        self.y = self.margin
        self.static_surface = self._build_static_surface(map_data)

    def _w2m(self, wx, wy):
        """World px -> panel px (letterboxed)."""
        return (self.map_ox + wx * self.scale,
                self.map_oy + wy * self.scale)

    def _clamp_panel(self, mx, my, inset=3):
        return (max(inset, min(self.minimap_w - inset, mx)),
                max(inset, min(self.minimap_h - inset, my)))
    def _build_static_surface(self, map_data):
        surf = pygame.Surface((self.minimap_w, self.minimap_h), pygame.SRCALPHA)
        surf.fill((10, 10, 12, 220))

        # Tile colors are sourced from the actual renderers, not invented.
        # The old palette used light "readable" tones (road (78,82,86),
        # khaki verges, teal ditch, blue interiors) that match NOTHING in
        # the world - M2 renders every walkable tile as one dark asphalt
        # slab, so the minimap showed zones and rooms that don't exist.
        #
        # Sources (sampled/verified, hardcoded here to avoid import cycles -
        # missions.m2/m3 import this module, so hud can't import them):
        #  m2: _m2_ground_surface base (34,36,37) covers EVERY walkable tile
        #      (".gOdsXTP" all blit that one slab); walls _WALL_BODY
        #      (72,70,64); barriers are jersey concrete, gradient (60..94),
        #      avg ~(80,78,70).
        #  m3: missions.m3.systems._TILE_BASE verbatim; D = reinforced
        #      prison-door frame avg (48,50,56).
        #  m1: warehouse band rows 11-20 = FLOOR_TILE avg (43,40,36), slum
        #      = SLUM_FLOOR avg (31,29,28) (see _render_m1_bg); C walls
        #      cycle the sampled container avgs by (col+row)%4 exactly like
        #      the renderer; W = WAREHOUSE_WALL avg (48,45,43);
        #      D = BAY_DOOR_BASE (55,52,48).
        #  walk: dock containers + slum floor.
        #
        # family_of returns (key, color): the key drives seam outlines, so
        # same-family tiles of different tints (container walls) never get
        # false seams between them.
        _M2_GROUND = (34, 36, 37)
        _M2_WALL = (72, 70, 64)
        _M2_BARRIER = (80, 78, 70)
        _M2_DOOR = (90, 88, 80)
        _M3_BASE = {
            ".": (32, 33, 33), "g": (40, 36, 32), "O": (29, 36, 38),
            "L": (36, 46, 48), "Y": (48, 48, 44), "M": (34, 36, 34),
            "K": (45, 48, 52), "E": (33, 34, 34), "P": (32, 33, 33),
            "X": (29, 38, 32), "C": (54, 54, 52), "B": (60, 50, 40),
            "S": (60, 90, 100),
        }
        _M3_DOOR = (48, 50, 56)
        # m4: night curfew city (The Aftermath). Solid building blocks with a
        # carved asphalt-lattice street grid; wet-blue station interiors.
        # Sampled from m4/draw.py's M4_TILE_BASE so the panel matches exactly
        # what the world renders (streets read as lanes between dark blocks).
        _M4_BASE = {
            ".": (30, 31, 34), "d": (40, 41, 45), "a": (26, 27, 30),
            "g": (34, 33, 30),
            "R": (40, 42, 48), "O": (29, 34, 40), "L": (34, 40, 46),
            "E": (30, 31, 34), "M": (30, 31, 34), "P": (30, 31, 34), "X": (28, 36, 34),
            "C": (44, 46, 52), "B": (64, 58, 48), "S": (56, 84, 96),
        }
        _M4_DOOR = (52, 54, 62)
        # m6: freezing border night. Sampled from missions/m6/draw.py's tile
        # table: snow ground, concrete walls, rail steel and the platform edge.
        _M6_BASE = {
            ".": (26, 30, 36), "g": (39, 46, 55), "O": (46, 52, 59),
            "K": (42, 52, 58), "L": (47, 51, 57), "Y": (92, 78, 50),
            "M": (36, 46, 52), "E": (26, 30, 36), "S": (50, 68, 78),
        }
        _M6_DOOR = (78, 70, 54)
        _M1_WH = (43, 40, 36)
        _M1_SLUM = (31, 29, 28)
        _M1_CONTAINERS = ((80, 45, 39), (40, 55, 74),
                          (70, 55, 39), (55, 54, 57))
        _M1_WHWALL = (48, 45, 43)
        _M1_DOOR = (55, 52, 48)

        def family_of(tile, col, row):
            pal = self._palette
            if tile == "B":
                if pal == "m3":
                    return ("barrier", (60, 50, 40))
                if pal == "m4":
                    return ("barrier", (64, 58, 48))
                if pal == "m6":
                    return ("barrier", (66, 58, 46))
                return ("barrier", _M2_BARRIER)
            if tile == "D":
                if pal == "m3":
                    return ("door", _M3_DOOR)
                if pal == "m4":
                    return ("door", _M4_DOOR)
                if pal == "m6":
                    return ("door", _M6_DOOR)
                if pal == "m2":
                    return ("door", _M2_DOOR)
                return ("door", _M1_DOOR)
            if tile in ("C", "W"):
                if pal in ("m1", "walk"):
                    if tile == "W":
                        return ("wall", _M1_WHWALL)
                    # Same (col+row)%4 cycle as _render_m1_bg, so the
                    # red/blue/rust/grey container pattern matches.
                    return ("wall", _M1_CONTAINERS[(col + row) % 4])
                if pal == "m3":
                    return ("wall", (54, 54, 52))
                if pal == "m4":
                    return ("wall", (58, 60, 66))
                if pal == "m6":
                    return ("wall", (54, 61, 70) if tile == "C" else (64, 71, 79))
                return ("wall", _M2_WALL)
            if pal == "m2":
                # One slab for the whole corridor - ditch, service road and
                # interiors included. That IS what the renderer draws.
                return ("ground", _M2_GROUND)
            if pal == "m3":
                # P/V/N are spawn markers on corridor floor; the entity
                # itself draws on the minimap.
                if tile in ("P", "V", "N"):
                    return (".", _M3_BASE["."])
                return (tile, _M3_BASE.get(tile, _M3_BASE["."]))
            if pal == "m4":
                # Same marker convention as m3: spawn/prop chars are floor.
                if tile in ("P", "V", "N", "T", "J", "E", "M"):
                    return (".", _M4_BASE["."])
                return (tile, _M4_BASE.get(tile, _M4_BASE["."]))
            if pal == "m6":
                if tile in ("P", "V", "N", "T", "J", "E", "X"):
                    return (".", _M6_BASE["."])
                return (tile, _M6_BASE.get(tile, _M6_BASE["."]))
            # m1 / walk floor: warehouse band vs slum (m1), slum (walk).
            # K/V/N/P/E/X spawn markers render as their ground band.
            if pal == "m1" and 11 <= row <= 20:
                return ("wh", _M1_WH)
            return ("slum", _M1_SLUM)

        def grain(col, row):
            # Deterministic per-tile brightness wobble, -4..+4. Kept small on
            # purpose: at 2px per tile a wider swing stops reading as surface
            # texture and starts reading as per-tile noise/dither.
            h = ((col * 73856093) ^ (row * 19349663)) & 0xFFFFFFFF
            return ((h >> 5) % 9) - 4

        # Pass 1 - per-tile colour WITH grain. The ±4 wobble mirrors the
        # renderers' own slab noise (M2's is literally %9-4); this surface
        # is built once so it costs nothing per frame.
        grid = []
        for row_idx, row in enumerate(map_data):
            line = []
            for col_idx, tile in enumerate(row):
                key, fam = family_of(tile, col_idx, row_idx)
                if key in ("wall", "door", "barrier"):
                    line.append((key, fam))   # structure stays crisp; no grain
                    continue
                d = grain(col_idx, row_idx)
                line.append((key, tuple(max(0, min(255, v + d)) for v in fam)))
            grid.append(line)

        tile_px = self.tile_size * self.scale
        for row_idx, row in enumerate(map_data):
            for col_idx, tile in enumerate(row):
                key, col = grid[row_idx][col_idx]
                px = int(self.map_ox + col_idx * tile_px)
                py = int(self.map_oy + row_idx * tile_px)
                # ceil, not int-truncate: at 70x80 tiles in a 160px panel a
                # column advances ~2px, so a truncated tile left a
                # sub-pixel gap that rounded into a black stripe down the
                # whole map. Overdrawing by the ceil remainder closes the
                # seams so the terrain reads as continuous ground.
                pw = max(1, int(math.ceil(tile_px)))
                ph = max(1, int(math.ceil(tile_px)))
                surf.fill(col, pygame.Rect(px, py, pw, ph))

                if key in ("wall", "door", "barrier"):
                    continue
                # Pass 2 - trace a darker seam wherever the ground family
                # changes (M3 rooms, M1 warehouse/slum band), so distinct
                # areas read as shapes instead of bleeding into each other.
                # M2 is one slab, so no seams fire there - correctly.
                _k, fam = family_of(tile, col_idx, row_idx)
                edge = tuple(max(0, v - 18) for v in fam)
                right = row[col_idx + 1] if col_idx + 1 < len(row) else None
                below = (map_data[row_idx + 1][col_idx]
                         if row_idx + 1 < len(map_data) else None)
                if right is not None and family_of(right, col_idx + 1, row_idx)[0] != key:
                    pygame.draw.line(surf, edge,
                                     (px + pw - 1, py), (px + pw - 1, py + ph - 1))
                if below is not None and family_of(below, col_idx, row_idx + 1)[0] != key:
                    pygame.draw.line(surf, edge,
                                     (px, py + ph - 1), (px + pw - 1, py + ph - 1))
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
        # ── Camera viewport - this is what makes it read as a *mini map*:
        # the white box shows which slice of the map is on screen. Uses the
        # camera_x/y the callers already pass (previously ignored).
        try:
            if camera_x is not None and camera_y is not None:
                rx = self.map_ox + camera_x * self.scale
                ry = self.map_oy + camera_y * self.scale
                rw = self._theme.width * self.scale
                rh = self._theme.height * self.scale
                vx0 = max(self.map_ox, rx)
                vy0 = max(self.map_oy, ry)
                vx1 = min(self.map_ox + self.map_pw, rx + rw)
                vy1 = min(self.map_oy + self.map_ph, ry + rh)
                if vx1 > vx0 + 2 and vy1 > vy0 + 2:
                    pygame.draw.rect(panel, (220, 220, 210),
                                     (int(vx0), int(vy0),
                                      max(2, int(vx1 - vx0)),
                                      max(2, int(vy1 - vy0))), 1)
        except Exception:
            pass
        # Enemies under, player on top (was reversed - a guard standing on
        # the player buried the green dot).
        for e in enemies:
            ex, ey = self._w2m(e.rect.centerx, e.rect.centery)
            ex, ey = self._clamp_panel(ex, ey, inset=2)
            pygame.draw.circle(panel, (220, 60, 60), (int(ex), int(ey)), 2)
        px, py = self._w2m(player.rect.centerx, player.rect.centery)
        px, py = self._clamp_panel(px, py, inset=3)
        px, py = int(px), int(py)
        pygame.draw.circle(panel, (80, 220, 100), (px, py), 3)
        angle = player.angle
        dir_len = 6
        dx = int(math.cos(angle) * dir_len)
        dy = int(math.sin(angle) * dir_len)
        pygame.draw.line(panel, (80, 220, 100), (px, py), (px + dx, py + dy), 2)

        # ── Service-door marker + directional arrow ──
        # Shown after all cell-block guards are dead so the player can find the
        # exit. Clamp the marker to the panel edge if it's off-screen, and draw
        # an arrow from the player toward it.
        if service_door_pos:
            tx, ty = self._w2m(service_door_pos[0], service_door_pos[1])
            # Keep the target marker inside the panel so the arrow always reads.
            tx_c, ty_c = self._clamp_panel(tx, ty, inset=6)
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
            kx, ky = self._w2m(smg_pos[0], smg_pos[1])
            kx, ky = self._clamp_panel(kx, ky, inset=4)
            kx, ky = int(kx), int(ky)
            smg_col = (150, 210, 255)
            pygame.draw.rect(panel, smg_col, (kx - 3, ky - 2, 6, 4), 1)
            pygame.draw.rect(panel, (220, 245, 255), (kx - 3, ky - 2, 6, 4))
        if notebook_pos:
            nx, ny = self._w2m(notebook_pos[0], notebook_pos[1])
            nx, ny = self._clamp_panel(nx, ny, inset=4)
            nx, ny = int(nx), int(ny)
            pygame.draw.rect(panel, (255, 220, 100), (nx - 3, ny - 3, 6, 6))
            pygame.draw.rect(panel, (255, 255, 255), (nx - 3, ny - 3, 6, 6), 1)
        if exfil_pos:
            ex, ey = self._w2m(exfil_pos[0], exfil_pos[1])
            ex, ey = self._clamp_panel(ex, ey, inset=5)
            ex, ey = int(ex), int(ey)
            pygame.draw.circle(panel, (80, 220, 100), (ex, ey), 4, 1)
        if volkov_pos:
            vx, vy = self._w2m(volkov_pos[0], volkov_pos[1])
            vx, vy = self._clamp_panel(vx, vy, inset=4)
            vx, vy = int(vx), int(vy)
            pygame.draw.circle(panel, (255, 160, 60), (vx, vy), 3)
        if commander_pos:
            cx, cy = self._w2m(commander_pos[0], commander_pos[1])
            cx, cy = self._clamp_panel(cx, cy, inset=4)
            cx, cy = int(cx), int(cy)
            pygame.draw.circle(panel, (255, 160, 60), (cx, cy), 3)
        # IPA truck - the central objective in M2's inspect phase. Drawn as
        # a filled orange square so it stands out from the floor zones.
        if ipa_truck_pos:
            tx, ty = self._w2m(ipa_truck_pos[0], ipa_truck_pos[1])
            tx, ty = self._clamp_panel(tx, ty, inset=4)
            tx, ty = int(tx), int(ty)
            pygame.draw.rect(panel, (220, 130, 60), (tx - 3, ty - 3, 6, 6))
            pygame.draw.rect(panel, (255, 220, 160), (tx - 3, ty - 3, 6, 6), 1)
        # Tanker - drawn hollow while intact, removed by the caller after the
        # blast (just pass None once STATE.mission2_tanker_rect is gone).
        if tanker_pos:
            tx, ty = self._w2m(tanker_pos[0], tanker_pos[1])
            tx, ty = self._clamp_panel(tx, ty, inset=5)
            tx, ty = int(tx), int(ty)
            pygame.draw.rect(panel, (255, 90, 50), (tx - 4, ty - 3, 8, 6), 1)
        # Shelter / safe zone - drawn as a small blue house icon (square body
        # + triangular roof) so the player can find the bunker during the
        # tanker countdown. Mission 2 passes shelter_pos=SAFE_ZONE during
        # STAGE_TANKER and STAGE_RUN; other stages pass None and the icon
        # doesn't render. The blue color matches the in-world "RUN HERE"
        # marker (C_VASILE = 100, 160, 220) for consistency.
        if shelter_pos:
            sx, sy = self._w2m(shelter_pos[0], shelter_pos[1])
            sx, sy = self._clamp_panel(sx, sy, inset=5)
            sx, sy = int(sx), int(sy)
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
        # Map-area frame: separates letterbox bars from actual terrain on
        # non-square maps (walk/M1/M2) so the bars don't read as void.
        try:
            pygame.draw.rect(panel, (40, 42, 44),
                             (int(self.map_ox), int(self.map_oy),
                              max(2, int(self.map_pw)), max(2, int(self.map_ph))), 1)
        except Exception:
            pass
        # North glyph: tiny up-tick + N in the top-left corner. Gives the
        # panel map orientation at a glance; sits on the border so it never
        # covers terrain on square maps for more than a pixel or two.
        try:
            pygame.draw.polygon(panel, (200, 200, 190),
                                [(7, 4), (10, 10), (4, 10)])
            n_surf = self._theme.font_terminal_small.render(T("hud.minimap_north"), True, (200, 200, 190))
            panel.blit(n_surf, (12, 3))
        except Exception:
            pass
        pygame.draw.rect(panel, (90, 75, 45), (0, 0, self.minimap_w, self.minimap_h), 2)
        pygame.draw.rect(
            panel, (55, 45, 28), (1, 1, self.minimap_w - 2, self.minimap_h - 2), 1
        )
        surface.blit(panel, (self.x, self.y))
