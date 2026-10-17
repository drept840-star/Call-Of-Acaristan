
"""Renderer for multiplayer arena matches.

Separate from ``missions/arena.py`` on purpose. That module is the
authoritative rules and must stay headless so a whole match can be tested
without a display; this one only draws. Mixing them would mean the tests
needed pygame, which is exactly the coupling that makes netcode hard to
verify.

Remote players are drawn by reusing the real ``Player`` sprite and its real
``draw()``. A hand-rolled representation for remote players would be a
second thing to keep in sync with the single-player art forever, and would
drift within a week. Instead each remote player gets one persistent
``Player`` instance that is *posed* from the interpolated snapshot:

  - position and angle come from the snapshot, so motion is smooth
  - walk cycle, recoil and breathing live on the local Player instance and
    keep animating on their own between snapshots

That split is the whole trick. The snapshot says *where*; the sprite
decides *how it looks getting there*.

Tile art comes from ``core.artpack`` so arenas match the rest of the game.
"""
import math

import pygame

from core.config import TILE_SIZE, MUZZLE_FLASH, C_BULLET, bullet_glow
from core import appearance
from core import artpack
from core.state import STATE
from entities import fallen as _fallen
from entities.player import Player
from net import protocol as P
from missions import arena as AR
from engine.text import T as _T  # RPE6 Phase 4 text table

# ── shooting feel constants ──
# Every arena gun carries its own kick/shake (see missions/arena.WEAPONS),
# taken from the same weapon in entities/weapons.py, so the OS-12 kicks like
# the rifle and the K-9 like the SMG. These two are the PISTOL's cam_kick
# and shake(18), used only as the fallback when a shot arrives without a
# weapon id (e.g. an older caller or a test).
RECOIL_KICK_PX = 20.0
SHAKE_AMOUNT = 18
RECOIL_SPRITE_PX = -3.0
HIT_CONFIRM_FRAMES = 10
# Local bolts: fake projectiles that fly from the muzzle to the recorded
# hitscan impact point. An instant full-ray line read as a laser string
# spanning the room while the trigger was held; a short static dash was
# barely visible inside the muzzle flash. A bolt in flight reads as a
# discrete shot, like the campaign's bullets.
BOLT_FLIGHT_FRAMES = 6
# Trail length behind a bolt, matching the campaign bullet's single-frame
# motion streak (~24px at pistol velocity).
BOLT_TRAIL_PX = 26.0
# Max length of a REMOTE player's tracer dash. The arena is hitscan, so the
# traced ``dist`` is the full ray length (up to WEAPON_RANGE, 520 px);
# drawing all of it is a laser string across the room. The local player's
# own shots fly as bolts (above); another player's shots stay a short dash
# with the end dot marking the true impact point.
TRACER_LEN_PX = 64.0
# A floating marker is removed after this many update_feel() ticks even if
# its alpha somehow never reaches zero. The client used to never call
# update_feel() at all, so a "HIT" spawned there stayed in the world
# forever; an age cap is the belt to that braces.
FLOATER_MAX_FRAMES = 90
FLOATER_MAX_ACTIVE = 12
# Barrel reach in px, matching Player.barrel_tip() for the default weapon
# (arm 16 + grip 4 + gun 17 + muzzle 2). Kept as a literal rather than a
# call to barrel_tip() because the flash must not depend on the sprite
# having been posed with a weapon yet.
PISTOL_REACH_PX = 39.0

# ── per-player weapon rig ──
# The wire carries a small weapon id; the shared Player sprite branches on
# one of "pistol"/"os12"/"k9_smg". Anything unrecognised falls back to the
# pistol, so a hostile or newer id can never leave a player gun-less.
_RIG_BY_WPN = {P.WPN_OS12: "os12", P.WPN_K9: "k9_smg"}
_DEFAULT_RIG = "pistol"
# Reach per rig, mirroring Player.barrel_tip()'s arm+grip+gun+muzzle sum:
# pistol 16+4+17+2, OS-12 16+4+26+3, K-9 16+4+18+5. Used to put the muzzle
# flash and the start of a bolt at the end of THIS player's gun.
_REACH_BY_RIG = {"pistol": PISTOL_REACH_PX, "os12": 49.0, "k9_smg": 43.0}


def rig_for_weapon(weapon):
    """Wire weapon id -> the sprite rig name Player.draw() branches on."""
    return _RIG_BY_WPN.get(weapon, _DEFAULT_RIG)


def reach_for_view(v):
    """Barrel reach in px for a posed sprite, by its current rig."""
    return _REACH_BY_RIG.get(getattr(v, "rig_weapon", None), PISTOL_REACH_PX)
# How many rendered frames a muzzle flash lingers after the snapshot flag
# says a player fired. Snapshot snapshots only carry the flag for the ~4
# sim ticks the host sets it, which at 20 Hz can be a single packet, so the
# view stretches it into a short, readable flash.
MUZZLE_FRAMES = 4

# ── Arena audio ─────────────────────────────────────────────────────────
# The arena used to play exactly one sound: the gunshot. A whole firefight
# was therefore a single undifferentiated noise with no report of where
# anything came from, no confirmation that your own shot landed, no click
# when the magazine ran dry, and no pickup chime. Every generator named here
# is already live in the campaign (audio/audio.py builds all of them at
# startup), so this is plumbing, not new content.
#
# Remote gunfire goes through play_3d, which pans and attenuates by distance.
# That is the single biggest readability win available here: in an eight-way
# deathmatch on a symmetric map, colour only tells you a shot happened, and
# hearing it come from your left is what tells you which side to turn.
GUNSHOT_VOLUME = 0.7
REMOTE_GUNSHOT_VOLUME = 0.55
# Past this a shot is reported as a distant crack rather than a close report.
GUNSHOT_FAR_PX = 640.0
# Past this it is not worth playing at all: at 1400 px the arena is over, and
# a full-volume gunshot from the far corner is noise that hides the fight in
# front of the player.
GUNSHOT_AUDIBLE_PX = 1400.0
# Volume for one-shot cues. Kept well under the gunshot so a pile-up of
# impacts cannot drown out the thing the player is actually listening for.
IMPACT_VOLUME = 0.4
HIT_TICK_VOLUME = 0.4
PICKUP_VOLUME = 0.5
RELOAD_VOLUME = 0.45
EMPTY_CLICK_VOLUME = 0.5
KILL_TICK_VOLUME = 0.5
DAMAGE_TAKEN_VOLUME = 0.45
DEATH_VOLUME = 0.6
ROUND_END_VOLUME = 0.55

# Arena tile chars mapped onto the game's existing art codes. '#' draws
# with the warehouse concrete wall and '.' with the warehouse floor, so an
# arena looks consistent with M1 without needing new assets.
_WALL_CODE = "C"
_FLOOR_CODE = "."

# Margin colour, for when the map is smaller than the viewport (Crossfire is
# only 640x640). The arena draws no tiles there, and because the game never
# clears the frame the previous screen showed through - the menu's green
# background around the map, like felt around a card table. Filling first
# makes the margin a deliberate dark void, and a thin edge line frames the
# play area so it reads as intentional.
VOID_COLOR = (7, 9, 12)
VOID_EDGE = (32, 38, 48)

# Palette so you can tell yourself from everyone else at a glance in a
# crowded fight. Keyed by player id, so a player keeps their colour for
# the whole match, on both machines.
LOCAL_COLOR = (120, 220, 255)
REMOTE_COLORS = (
    (255, 140, 140),
    (255, 200, 90),
    (150, 255, 160),
    (220, 150, 255),
    (255, 160, 220),
    (160, 200, 255),
    (255, 220, 120),
    (140, 255, 230),
)


# Crate edge length, in px. 22 reads as a box you could walk behind (a
# player is ~20 wide) without swallowing the tile it stands on.
CRATE_SIZE = 22

# Shadow surfaces are cached: building an SRCALPHA ellipse per pickup per
# frame is the kind of cost that only shows up once eight crates are on
# screen and the frame budget is already spoken for.
_SHADOWS = {}


def _pickup_shadow(width):
    """A cached soft ground ellipse, keyed by width."""
    surf = _SHADOWS.get(width)
    if surf is None:
        h = max(2, width // 3)
        surf = pygame.Surface((width, h), pygame.SRCALPHA)
        pygame.draw.ellipse(surf, (0, 0, 0, 95), (0, 0, width, h))
        _SHADOWS[width] = surf
    return surf


def _mix(a, b, t):
    """Blend two RGB triples; t=0 is *a*, t=1 is *b*."""
    return (int(a[0] + (b[0] - a[0]) * t),
            int(a[1] + (b[1] - a[1]) * t),
            int(a[2] + (b[2] - a[2]) * t))


def color_for(player_id, local_id):
    if player_id == local_id:
        return LOCAL_COLOR
    return REMOTE_COLORS[player_id % len(REMOTE_COLORS)]


# Kill-feed rows carry two names plus a weapon tag, so each name is clipped
# before layout. Without this a pair of 16-character handles pushes the row
# past the screen edge and the killer's name -- the half anyone actually
# reads -- is the part that falls off.
KILLFEED_NAME_CHARS = 12


def _fit(text, max_chars):
    """Truncate *text* to *max_chars*, with an ellipsis when it was cut.

    Character-count clipping rather than pixel measurement: these strings are
    already length-capped at the protocol boundary, so this only ever trims
    the last couple of characters, and doing it by count keeps the call sites
    free of font lookups inside a per-frame draw.
    """
    text = str(text)
    if max_chars <= 0 or len(text) <= max_chars:
        return text
    if max_chars <= 3:
        return text[:max_chars]
    return text[:max_chars - 3] + "..."


def _fit_px(text, font, max_w):
    """Truncate *text* to *max_w* pixels, with an ellipsis when cut.

    Needed where the space is SHARED with other right-aligned columns of
    measured width. Clipping by character count cannot see the rank and K-D
    that are already sitting at the far right, so a long handle runs straight
    into them -- which is how "BIRIBEL2/5" appears on one line.
    """
    text = str(text)
    if max_w <= 0:
        return ""
    if font.size(text)[0] <= max_w:
        return text
    ell = "..."
    trimmed = text
    while trimmed and font.size(trimmed + ell)[0] > max_w:
        trimmed = trimmed[:-1]
    return (trimmed + ell) if trimmed else ""



class _PoseMeta:
    """What a posed sprite currently shows (per player slot). Kept beside the sprite instead of
    as ad hoc ``_arena_*`` attributes on the shared ``Player`` type (RPE6 D4)."""
    __slots__ = ("look", "weapon", "state", "reload", "reload_total", "muzzle")

    def __init__(self):
        self.look = None      # appearance key applied to the sprite
        self.weapon = None    # last weapon shown (None = never sighted)
        self.state = None     # last entity state shown
        self.reload = 0       # local reload clock (frames left)
        self.reload_total = 1
        self.muzzle = 0       # muzzle-flash frames left

class ArenaView(object):
    """Camera, tile painting and remote-player sprites for one match."""

    def __init__(self, map_name="yard"):
        # _views must exist before set_map(), which clears it: set_map is
        # also the public way to switch maps at runtime.
        self._views = {}
        self._view_meta = {}   # pid -> _PoseMeta (what the posed sprite currently shows; D4: not stuffed on Player)
        self.cam_x = 0
        self.cam_y = 0
        self._cam_init = False
        # The host's sim tick, used to decide whether a pickup has respawned.
        # Updated from the match state each frame; 0 before the first packet,
        # which makes every pickup visible on frame one.
        self._host_tick = 0
        # player_id -> team, for team-mode name tags. Populated from the
        # host's match state.
        self._teams = {}
        # player_id -> display name, from the host's match state. Keyed by
        # str(id) because that is how the rules packet carries it. Empty until
        # the first packet arrives, which is why name_for() falls back to the
        # slot label instead of rendering an empty tag.
        self._names = {}
        # player_id -> fallen body + how many frames it has been lying there.
        # Built on the frame a player is first seen dead, dropped again the
        # moment they are alive or gone: a corpse that outlives its death would
        # stack a second body under the respawned player.
        self._corpses = {}
        self._corpse_age = {}
        # player_ids currently awaiting respawn, handed in by MatchScreen from
        # its locally-ticked countdown. See sync() for why this drives corpses
        # instead of the entity state bit.
        self._respawn_waiting = ()
        # player_id -> cosmetic loadout, from the host's match state. Same
        # str-keyed shape and the same "empty until the first packet" caveat as
        # _names, which is why look_for() answers with the default rather than
        # with nothing.
        self._looks = {}
        # Where the local player is, for positioning remote gunfire. Refreshed
        # in sync() from the local entity, so it needs no argument threading.
        self._listener = (0.0, 0.0)
        # player_id -> True while that player is mid-reload. Watched as a
        # RISING EDGE: playing reload on every frame of a reload would be one
        # click per frame for a single magazine swap.
        self._reload_prev = {}
        # player_id -> seconds of respawn left, published by the host. Only
        # read during draw(); set in draw() from the HUD kwargs.
        self._respawn_remote = {}
        # Local-only shooting feel. _local_id is set in draw() each frame
        # from the caller's argument rather than stored at construction, so
        # the same view can be reused if the local id ever changes.
        self._local_id = 0
        self._bolts = []
        self._hit_confirm = 0
        self._floaters = []
        # Cosmetic clock, in frames. Drives the crate bob and halo. Lives
        # here rather than in draw() so it advances exactly once per frame
        # no matter how many crates are drawn.
        self._anim_t = 0
        self.set_map(map_name)

    def set_map(self, map_name):
        self.map_name = map_name if map_name in AR.ARENAS else "yard"
        self.map_rows = AR.ARENAS[self.map_name]
        self.cols, self.rows = AR.map_size(self.map_rows)
        self.map_w = self.cols * TILE_SIZE
        self.map_h = self.rows * TILE_SIZE
        self.walls = AR.build_walls(self.map_rows)
        # Changing map invalidates every posed sprite: they were built for
        # the old geometry and must not appear on the new one for a frame.
        self._views.clear()
        self._view_meta.clear()
        # A map change also ends every death in progress: a body from the old
        # arena would be drawn at coordinates that mean nothing here.
        self._corpses.clear()
        self._corpse_age.clear()
        self._cam_init = False
        # Same for shot feedback: in-flight bolts belong to the old map.
        self._bolts = []
        self._hit_confirm = 0
        self._floaters = []

    def update_camera(self, world, local_id, view_w, view_h):
        """Camera follows the local player, using the game's shared camera.

        This deliberately calls ``core.camera.update_camera`` rather than
        doing its own lerp. The missions' camera is a tuned part of the
        game's feel -- it carries the follow deadzone, the aim lookahead,
        screen shake and recoil kick. A private lerp here looks almost
        right while silently dropping all four, which is why arena gunfire
        felt dead compared with the campaign: shots that kick the camera in
        M1 moved nothing at all here.

        Conventions kept identical to the missions:
          - the camera is the top-left of the viewport in world space, and
            entity draw calls receive it directly (``Player.draw`` computes
            its own screen pos as ``centerx - offset_x``, so a screen-centred
            camera would shift every sprite half a viewport off to the left)
          - the deadzone and lookahead are gameplay-only, so both are on
        """
        from core.camera import (update_camera, CAM_DEADZONE_PX,
                                 CAM_LOOKAHEAD_PX)
        from core.config import WIDTH, HEIGHT

        focus = None
        aim = None
        if world:
            me = world.get(local_id)
            if me is None:
                # Before our own entity arrives, track whoever is nearest
                # the middle of the screen. Jumping to player 0 instead
                # would whip the camera across the map on every join.
                mid_x, mid_y = self.map_w / 2.0, self.map_h / 2.0
                me = min(world.values(),
                         key=lambda e: (e[2] - mid_x) ** 2 + (e[3] - mid_y) ** 2)
            focus = (me[2], me[3])
            aim = me[4]

        if focus is None:
            if not self._cam_init:
                self.cam_x = max(0.0, (self.map_w - WIDTH) / 2.0)
                self.cam_y = max(0.0, (self.map_h - HEIGHT) / 2.0)
                self._cam_init = True
            return self.cam_x, self.cam_y

        # Aim lookahead: bias the view toward where the barrel points, so
        # you can see what you are shooting at. Only once the camera has
        # settled, or the first frame would start off-centre and slide in.
        lookahead = (0.0, 0.0)
        if aim is not None and self._cam_init:
            la = math.radians(aim)
            lookahead = (math.cos(la) * CAM_LOOKAHEAD_PX,
                         math.sin(la) * CAM_LOOKAHEAD_PX)

        # Shake/kick offset for this frame, kept OUT of the follow position
        # so the map clamp/centring below cannot swallow it.
        eff_x = eff_y = 0.0
        if self._cam_init:
            # apply_final_clamp=False: ask core for follow + shake/kick with
            # the map clamp left to us. Its own final clamp flattens shake to
            # zero whenever the map is smaller than the viewport (the bound
            # is 0), which is exactly Crossfire - the arena would otherwise
            # have no screen shake or recoil kick at all on the small map.
            fcx, fcy = update_camera(
                focus, map_w=self.cols, map_h=self.rows,
                deadzone_px=CAM_DEADZONE_PX, lookahead=lookahead,
                apply_final_clamp=False)
            # update_camera keeps STATE.camera_x/y as the un-shaken follow
            # position and returns follow + shake + kick, so the difference
            # is the cosmetic effect for this frame.
            base_x, base_y = STATE.camera_x, STATE.camera_y
            eff_x, eff_y = fcx - base_x, fcy - base_y
            # update_camera works in the fixed game resolution; rescale to
            # the actual surface so a resized window does not show more or
            # less of the map than the gameplay camera would.
            sx = view_w / float(WIDTH)
            sy = view_h / float(HEIGHT)
            self.cam_x = base_x * sx
            self.cam_y = base_y * sy
            eff_x *= sx
            eff_y *= sy
        else:
            # Snap on the first frame, like the missions do. Lerping in from
            # (0,0) makes the map slide in from the top-left on every join.
            self.cam_x = focus[0] - view_w / 2.0
            self.cam_y = focus[1] - view_h / 2.0
            self._cam_init = True

        # Clamp the FOLLOW position to the map, exactly like
        # core.camera.update_camera. When the map is narrower than the
        # viewport there is nothing to scroll, so centre it with a negative
        # offset rather than pinning to 0 and leaving a black bar down one
        # side. The shake/kick delta is added afterwards and (on a sub-
        # viewport map) deliberately not re-clamped, or there would be
        # nothing left to see.
        max_x = self.map_w - view_w
        max_y = self.map_h - view_h
        if max_x <= 0:
            self.cam_x = max_x / 2.0 + eff_x
        else:
            self.cam_x = max(0.0, min(float(max_x), self.cam_x + eff_x))
        if max_y <= 0:
            self.cam_y = max_y / 2.0 + eff_y
        else:
            self.cam_y = max(0.0, min(float(max_y), self.cam_y + eff_y))
        return self.cam_x, self.cam_y

    def apply_recoil_kick(self, aim_degrees, amount):
        """Fire the shared camera's recoil kick for a local shot.

        The kick is stored in STATE and applied by the next update_camera
        call, which is what gives the gun weight. Only ever called for the
        LOCAL player: kicking the screen because somebody else shot is
        disorienting, and in M1 the kick is a first-person effect of your
        own trigger pull.
        """
        from core.state import STATE
        ang = math.radians(aim_degrees)
        STATE.cam_kick_x = -math.cos(ang) * amount
        STATE.cam_kick_y = -math.sin(ang) * amount

    def _visible_tiles(self, view_w, view_h):
        """Tile range that can touch the viewport, culled to the view."""
        c0 = max(0, int(self.cam_x // TILE_SIZE))
        c1 = min(self.cols, int((self.cam_x + view_w) // TILE_SIZE) + 1)
        r0 = max(0, int(self.cam_y // TILE_SIZE))
        r1 = min(self.rows, int((self.cam_y + view_h) // TILE_SIZE) + 1)
        return c0, c1, r0, r1

    def draw_tiles(self, surface):
        vw, vh = surface.get_width(), surface.get_height()
        c0, c1, r0, r1 = self._visible_tiles(vw, vh)
        for r in range(r0, r1):
            row = self.map_rows[r]
            for c in range(c0, c1):
                if c >= len(row):
                    continue
                ch = row[c]
                x = int(c * TILE_SIZE - self.cam_x)
                y = int(r * TILE_SIZE - self.cam_y)
                if ch == "#":
                    art = artpack.wall(_WALL_CODE, c, r)
                    if art is not None:
                        surface.blit(art, (x, y))
                    else:
                        pygame.draw.rect(surface, (58, 62, 74),
                                         (x, y, TILE_SIZE, TILE_SIZE))
                    continue
                art = artpack.tile(_FLOOR_CODE, c, r)
                if art is not None:
                    surface.blit(art, (x, y))
                else:
                    pygame.draw.rect(surface, (24, 25, 31),
                                     (x, y, TILE_SIZE, TILE_SIZE))
                # Spawn markers are a faint outline rather than a solid
                # block, so they never hide a player standing on one.
                if ch in AR.SPAWN_TILES:
                    pygame.draw.circle(
                        surface, (70, 80, 96),
                        (x + TILE_SIZE // 2, y + TILE_SIZE // 2), 7, 1)

    def draw_pickups(self, surface, live=None):
        """Draw pickups. ``live`` is the host's [(x,y,kind,value,ready_at)].

        When the host has sent its pickup state, that is authoritative: a pack
        somebody just took is hidden immediately rather than sitting there
        looking collectable. Before the first packet arrives we fall back to
        the map tiles, so nothing is missing on the very first frame.

        A crate that is still on its respawn timer is drawn as a ghost rather
        than skipped entirely: a spot you know a gun comes back to is worth
        crossing the map for, and an empty tile tells you nothing.
        """
        vw, vh = surface.get_width(), surface.get_height()
        items = (live if live is not None
                 else [(px, py, kind, value, 0)
                       for (px, py, kind, value) in AR.pickups(self.map_rows)])
        for (px, py, kind, value, ready_at) in items:
            x = int(px - self.cam_x)
            y = int(py - self.cam_y)
            if not (-24 < x < vw + 24 and -30 < y < vh + 24):
                continue
            if live is not None and ready_at > self._host_tick:
                self._draw_pickup_respawn(surface, x, y, ready_at)
                continue
            if kind == "health":
                col = (90, 230, 130)
            elif kind == "armour":
                col = (110, 170, 255)
            else:
                col = {P.WPN_OS12: (235, 150, 70),
                       P.WPN_K9: (200, 120, 235)}.get(value, (200, 200, 200))
            self._draw_crate(surface, x, y, col, kind, value,
                               wx=px, wy=py)

    # ── crate art ──────────────────────────────────────────────────────
    # A pickup is the one piece of loot the player has to CROSS THE MAP for,
    # so it has to be legible at a glance from across the arena: it was a
    # 14px outlined square, which read as a HUD artefact rather than as a
    # thing lying on the floor. Everything below is drawn relative to the
    # crate's centre, so the bob never moves it off its tile.

    def _draw_crate(self, surface, cx, cy, col, kind, value,
                    wx=None, wy=None):
        """One wooden crate, lit from the top-left, bobbing on its own beat."""
        # A phase taken from the crate's own position: a row of crates that
        # heaved in lockstep would look like one animated sprite stamped
        # four times, which is worse than not animating at all.
        # World-anchored: wx/wy are the map-space pickup coords, so the
        # phase is stable while the camera moves. Deriving it from the
        # screen-space cx/cy made every animation term (bob, shine, halo,
        # twinkle) jump by ~0.7-1.9 rad per pixel of camera travel.
        if wx is None:
            wx = cx
        if wy is None:
            wy = cy
        phase = int(wx) * 0.7 + int(wy) * 1.1
        t = self._anim_t
        bob = int(round(math.sin(t * 0.055 + phase) * 3.0))
        half = CRATE_SIZE // 2
        box = pygame.Rect(cx - half, cy - half + bob, CRATE_SIZE, CRATE_SIZE)
        mid = box.centery

        # Ground shadow. It stays on the floor while the crate bobs, and it
        # tightens as the crate rises -- the one cue that reads the hop as
        # leaving the ground rather than sliding on it. Two sizes, both
        # cached, so the shrink costs nothing per frame.
        shadow = _pickup_shadow(CRATE_SIZE + 6 if bob <= 0 else CRATE_SIZE + 1)
        surface.blit(shadow, (cx - shadow.get_width() // 2, cy + half - 3))

        # Body: a lid lighter than the front, and a dark underside, which is
        # what makes a flat square read as a box with volume.
        pygame.draw.rect(surface, (92, 63, 37), box)
        pygame.draw.rect(surface, (126, 88, 52), (box.x, box.y, box.w, 5))
        pygame.draw.rect(surface, (58, 39, 22),
                         (box.x, box.bottom - 4, box.w, 4))
        # Plank seams, inset so they never touch the border and thicken it.
        for i in (1, 2):
            sy = box.y + i * (CRATE_SIZE // 3)
            pygame.draw.line(surface, (68, 45, 26),
                             (box.x + 3, sy), (box.right - 4, sy), 1)
        # Metal corner brackets in the pickup's own colour: the fastest way
        # to tell a weapon crate from a medpack at the edge of the screen.
        for bx, by in ((box.left + 1, box.top + 1),
                       (box.right - 5, box.top + 1),
                       (box.left + 1, box.bottom - 5),
                       (box.right - 5, box.bottom - 5)):
            pygame.draw.rect(surface, col, (bx, by, 4, 4))
        # A slow shine that sweeps down the lid, drifting by the crate's own
        # phase so a field of them shimmers instead of blinking in unison.
        sweep = (t * 0.018 + phase * 0.11) % 1.0
        gy = box.y + int(sweep * box.h)
        if box.top <= gy <= box.bottom - 1:
            pygame.draw.line(surface, _mix(col, (255, 255, 255), 0.55),
                             (box.x + 3, gy), (box.right - 3, gy), 1)
        # A dark seam keeps the silhouette intact over a light floor.
        pygame.draw.rect(surface, (22, 15, 9), box, 1)

        self._draw_crate_glyph(surface, cx, mid, col, kind, value)

        # Halo: two rings breathing out of step, marking these as things you
        # can take rather than scenery. Brighter and wider than a flat ring
        # so the eye catches a crate across the arena -- but still mixed well
        # down, or a bright ring on every crate fights the players for
        # attention.
        pulse = 0.5 + 0.5 * math.sin(t * 0.09 + phase)
        pygame.draw.circle(surface, _mix(col, (30, 34, 42), 0.42),
                           (cx, mid), half + 4 + int(round(pulse * 3)), 1)
        counter = 0.5 + 0.5 * math.sin(t * 0.09 + phase + math.pi)
        pygame.draw.circle(surface, _mix(col, (30, 34, 42), 0.66),
                           (cx, mid), half + 1 + int(round(counter * 2)), 1)

        # A brief twinkle on the upper-left corner: even a crate you are not
        # standing next to advertises that it can be picked up.
        tw = math.sin(t * 0.05 + phase * 1.7)
        if tw > 0.72:
            arm = 1 + int((tw - 0.72) / 0.28 * 3)
            tx, ty = box.left + 4, box.top + 3
            pygame.draw.line(surface, (255, 248, 220),
                             (tx - arm, ty), (tx + arm, ty), 1)
            pygame.draw.line(surface, (255, 248, 220),
                             (tx, ty - arm), (tx, ty + arm), 1)

    def _draw_crate_glyph(self, surface, cx, cy, col, kind, value):
        """The stencilled mark on the crate: what is actually inside."""
        plate = pygame.Rect(cx - 7, cy - 7, 14, 14)
        pygame.draw.rect(surface, (32, 23, 14), plate)
        pygame.draw.rect(surface, _mix(col, (32, 23, 14), 0.35), plate, 1)
        if kind == "health":
            # A cross, and nothing else: it must never read as a gun.
            pygame.draw.rect(surface, (236, 248, 242), (cx - 5, cy - 1, 10, 3))
            pygame.draw.rect(surface, (236, 248, 242), (cx - 1, cy - 5, 3, 10))
            return
        if kind == "armour":
            # A shield: flat top, swept point.
            pygame.draw.polygon(surface, (222, 236, 255),
                                [(cx - 5, cy - 5), (cx + 5, cy - 5),
                                 (cx + 5, cy + 1), (cx, cy + 6),
                                 (cx - 5, cy + 1)])
            return
        # Weapon crates get a silhouette, sized to the gun inside: long for
        # the rifle, short and thin for the SMG.
        barrel = 11 if value == P.WPN_OS12 else 8
        pygame.draw.rect(surface, (222, 228, 238),
                         (cx - barrel // 2, cy - 3, barrel, 3))
        pygame.draw.rect(surface, (222, 228, 238),
                         (cx - barrel // 2 + 1, cy + 1, 3, 4))
        # A coloured sight pin, the one bright note on an otherwise grey gun.
        pygame.draw.rect(surface, col, (cx + barrel // 2 - 2, cy - 5, 2, 2))

    def _draw_pickup_respawn(self, surface, cx, cy, ready_at):
        """Ghost frame + refill arc for a crate that has been taken."""
        half = CRATE_SIZE // 2
        box = pygame.Rect(cx - half, cy - half, CRATE_SIZE, CRATE_SIZE)
        # Corner ticks only: a full outline would read as a live crate that
        # had failed to draw its contents.
        for ox, oy, sx, sy in ((box.left, box.top, 1, 1),
                               (box.right, box.top, -1, 1),
                               (box.left, box.bottom, 1, -1),
                               (box.right, box.bottom, -1, -1)):
            pygame.draw.line(surface, (84, 90, 102), (ox, oy),
                             (ox + sx * 6, oy), 1)
            pygame.draw.line(surface, (84, 90, 102), (ox, oy),
                             (ox, oy + sy * 6), 1)
        total = max(1, int(getattr(AR, "PICKUP_RESPAWN_TICKS", 720)))
        frac = 1.0 - min(1.0, max(0, int(ready_at) - int(self._host_tick))
                         / float(total))
        if frac <= 0.02:
            return
        r = half + 5
        try:
            pygame.draw.arc(surface, (120, 128, 144),
                            pygame.Rect(cx - r, cy - r, r * 2, r * 2),
                            -math.pi / 2,
                            -math.pi / 2 + frac * math.pi * 2, 2)
        except (ValueError, TypeError):
            # An arc with a zero sweep raises on some SDL builds; a crate
            # with no progress ring is still a perfectly readable crate.
            pass

    # ── players ──

    def _pose(self, pid):
        """Get (creating if needed) the sprite used to draw player ``pid``.

        The loadout is re-applied here on change, not only at creation. These
        sprites are cached per SLOT and a slot outlives its player, so a peer
        that is removed and replaced would otherwise go on wearing the hat the
        stranger who bought it was wearing.
        """
        v = self._views.get(pid)
        if v is None:
            v = Player(0, 0)
            v.angle = 0.0
            self._views[pid] = v
            self._view_meta[pid] = _PoseMeta()
        meta = self._view_meta.setdefault(pid, _PoseMeta())
        look = self.look_for(pid)
        key = appearance.key_of(look)
        if meta.look != key:
            v.set_appearance(look)
            meta.look = key
        return v

    # ── shooting feel ──
    #
    # These are the local player's eyes only. Everything here is cosmetic
    # and derives from the host's authoritative "a shot happened" event, so
    # two machines can never disagree about it -- and nothing in here feeds
    # back into the sim.
    #
    # The feel is copied from M1's pistol: recoil on the sprite, a recoil
    # kick on the camera, screen shake, an ejected casing, and a tracer.
    # Without these the arena reads as instant, silent and weightless next
    # to the campaign, which is exactly the complaint that prompted this.

    def name_for(self, player_id):
        """This player's display name, or their slot label.

        Every name-bearing surface goes through here, so a peer that never
        named itself (an older client, the headless tools, a hostile peer
        sending junk) shows "P3" rather than nothing. The fallback is derived
        from the slot id, so it is stable for the whole match and matches the
        P%d convention used in the lobby roster.
        """
        try:
            key = str(int(player_id))
        except (TypeError, ValueError):
            return P.DEFAULT_PLAYER_NAME
        return self._names.get(key) or P.default_name(player_id)

    def look_for(self, player_id):
        """This player's cosmetic loadout, or the free default.

        The twin of name_for(), including the reason it exists: the table is
        empty for the whole first moment of a match, and a peer on a client
        that predates cosmetics never sends one. Both of those have to draw a
        person, not raise. Normalized on the way out so an identifier from a
        newer or a hostile catalog cannot reach the renderer.
        """
        try:
            key = str(int(player_id))
        except (TypeError, ValueError):
            return appearance.DEFAULT
        return appearance.normalize(self._looks.get(key))

    def confirm_hit(self, wx, wy):
        """Authoritative hit confirmation at a world point.

        Driven by the host's EV_HIT event rather than a local re-trace, so
        the marker only ever appears for a shot that actually connected.

        Particles only, deliberately. on_local_shot already raised the
        "HIT" floater for this same shot, and doing it in both places put
        three or four of them stacked on the corpse.

        The tick is here rather than in on_local_shot for the same reason:
        on_local_shot fires on the trigger pull and the sound says "you hit
        something" about a shot whose outcome the client does not yet know.
        """
        from core.config import audio
        from fx.effects import spawn_particles
        spawn_particles(wx, wy, (200, 30, 30), count=10)
        self._hit_confirm = max(self._hit_confirm, HIT_CONFIRM_FRAMES)
        audio.play("bullet_snap", volume=HIT_TICK_VOLUME)

    def on_local_kill(self):
        """You killed somebody. A short crack, distinct from a hit tick."""
        from core.config import audio
        audio.play("bullet_snap", volume=KILL_TICK_VOLUME)

    def on_local_death(self):
        """You died. A body hit, so it never reads as a kill you scored."""
        from core.config import audio
        audio.play("melee_hit", volume=DEATH_VOLUME)

    def on_empty_click(self):
        """The trigger was pulled on a dry magazine and the host refused."""
        from core.config import audio
        audio.play("empty_click", volume=EMPTY_CLICK_VOLUME)

    def on_round_end(self):
        """The round resolved. One sting, on the host and on every client."""
        from core.config import audio
        audio.play("mission_complete", volume=ROUND_END_VOLUME)

    def spawn_damage_number(self, wx, wy, amount):
        """Float the damage you took. White is normal, red is a big hit."""
        if amount <= 0:
            return
        from core.config import audio
        col = (255, 90, 80) if amount >= 40 else (255, 225, 225)
        # [world_x, world_y, alpha, text, colour, age]
        self._floaters.append([wx, wy - 18.0, 255.0, str(int(amount)), col, 0])
        if len(self._floaters) > FLOATER_MAX_ACTIVE:
            del self._floaters[0]
        # An incoming thud. Distinct from the impact you HEAR when you shoot
        # something, so being shot at is audible even with your eyes on
        # another part of the map.
        audio.play("bullet_impact_enemy", volume=DAMAGE_TAKEN_VOLUME)

    def on_pickup(self, wx, wy, value):
        """Flash where a pickup was taken, so a contested health pack is
        visible feedback rather than a silent stat change."""
        from core.config import audio
        from fx.effects import spawn_particles
        spawn_particles(wx, wy, (120, 255, 180), count=8)
        audio.play("pickup", volume=PICKUP_VOLUME)

    def on_local_shot(self, x, y, angle_deg, dist, hit_player, weapon=None):
        """React to the local player firing. Called once per shot fired.

        ``weapon`` is the firing gun's wire id; it selects that gun's own
        camera kick and screen shake so an OS-12 burst shoves the view like
        the campaign's rifle instead of like the pistol. Omitting it falls
        back to the pistol's values, which keeps callers that predate this
        (and the unit test) working.
        """
        from core.config import Casing, audio
        from fx.effects import shake, spawn_particles
        rad = math.radians(angle_deg)

        # Gunshot, at the same level as the M1 pistol. The arena previously
        # fired in total silence, which is most of why it did not feel like
        # the campaign.
        audio.play("gunshot", volume=GUNSHOT_VOLUME)

        # Camera kick and screen shake for THIS gun, from the same table the
        # sim uses. Aiming right kicks the view left, which sells the weight.
        stats = AR.weapon_stats(weapon) if weapon is not None else None
        kick = stats["kick"] if stats else RECOIL_KICK_PX
        shake_amount = stats["shake"] if stats else SHAKE_AMOUNT
        self.apply_recoil_kick(angle_deg, kick)
        shake(shake_amount)

        # Sprite recoil: the real Player animates this itself between
        # snapshots, exactly as it does in the campaign.
        me = self._pose(self._local_id)
        me._recoil_timer = 8
        me._recoil_offset = -RECOIL_SPRITE_PX
        me._slide_timer = 3
        reach = reach_for_view(me)

        # Casing ejected to the shooter's right, as in the campaign.
        eject = rad + math.pi / 2.0
        bx = x + math.cos(rad) * 22
        by = y + math.sin(rad) * 22
        STATE.casings.append(Casing(bx, by, eject))

        # Hit feedback stays synchronous with the trigger pull (snappy beats
        # synced - the smoke test pins this: a hit must confirm on the SAME
        # call, with no update_feel() in between).
        ex = x + math.cos(rad) * dist
        ey = y + math.sin(rad) * dist
        if hit_player:
            spawn_particles(ex, ey, (200, 30, 30), count=10)
            self._hit_confirm = HIT_CONFIRM_FRAMES
            # [world_x, world_y, alpha, text, colour, age]
            self._floaters.append([ex, ey - 12.0, 255.0, "HIT",
                                   (255, 220, 120), 0])
            if len(self._floaters) > FLOATER_MAX_ACTIVE:
                del self._floaters[0]

        # Bolt: a fake projectile that flies from the muzzle to the recorded
        # impact point over BOLT_FLIGHT_FRAMES. Hitscan damage is instant,
        # but drawing the flight makes each trigger pull read as a discrete
        # shot (like the campaign's bullets) instead of a static line. The
        # miss puff is deferred to arrival (see _advance_bolts) so cause and
        # effect stay glued together.
        mx = x + math.cos(rad) * reach
        my = y + math.sin(rad) * reach
        travel = max(0.0, dist - reach)
        if travel <= 0.0:
            if not hit_player:
                spawn_particles(mx, my, (190, 180, 160), count=6)
        else:
            self._bolts.append({"x": mx, "y": my,
                                "dx": math.cos(rad), "dy": math.sin(rad),
                                "travel": travel, "t": 0,
                                "life": BOLT_FLIGHT_FRAMES,
                                "hit": hit_player})

    def on_remote_shot(self, pid, x, y, angle_deg, dist, hit_player):
        """React to a remote player firing. Spawns in-flight bolt, casing,
        positioned sound and hit particles, without local camera kick."""
        from core.config import Casing, audio
        from fx.effects import spawn_particles
        rad = math.radians(angle_deg)

        # Positioned, not flat. The whole point of hearing somebody else fire
        # is working out where they are, and play_3d gives both the pan and
        # the falloff for free. Beyond GUNSHOT_AUDIBLE_PX it plays nothing at
        # all rather than at a volume that is pure noise from that range.
        span = math.hypot(x - self._listener[0], y - self._listener[1])
        if span <= GUNSHOT_AUDIBLE_PX:
            name = "gunshot_distant" if span > GUNSHOT_FAR_PX else "gunshot"
            audio.play_3d(name, (x, y), self._listener,
                          max_dist=GUNSHOT_AUDIBLE_PX,
                          base_volume=REMOTE_GUNSHOT_VOLUME)

        p = self._pose(pid)
        p._recoil_timer = 8
        p._recoil_offset = -RECOIL_SPRITE_PX
        p._slide_timer = 3
        reach = reach_for_view(p)

        eject = rad + math.pi / 2.0
        bx = x + math.cos(rad) * 22
        by = y + math.sin(rad) * 22
        STATE.casings.append(Casing(bx, by, eject))

        ex = x + math.cos(rad) * dist
        ey = y + math.sin(rad) * dist
        if hit_player:
            spawn_particles(ex, ey, (200, 30, 30), count=10)

        mx = x + math.cos(rad) * reach
        my = y + math.sin(rad) * reach
        travel = max(0.0, dist - reach)
        if travel <= 0.0:
            if not hit_player:
                spawn_particles(mx, my, (190, 180, 160), count=6)
        else:
            self._bolts.append({"x": mx, "y": my,
                                "dx": math.cos(rad), "dy": math.sin(rad),
                                "travel": travel, "t": 0,
                                "life": BOLT_FLIGHT_FRAMES,
                                "hit": hit_player})

    def update_feel(self):
        """Advance the local-only cosmetic timers. Once per frame.

        Must be driven on BOTH the host and the client. The client skipped
        it, so its own hit markers never faded and hung in the world.
        """
        from fx import effects  # lazy: fx package loads later
        self._anim_t += 1
        if self._hit_confirm > 0:
            self._hit_confirm -= 1
        for f in self._floaters[:]:
            f[1] -= 1.0
            f[2] -= 4
            f[5] = f[5] + 1 if len(f) > 5 else 0     # age, for the hard cap
            if f[2] <= 0 or f[5] > FLOATER_MAX_FRAMES:
                self._floaters.remove(f)
        # Impact puffs and ejected casings from on_local_shot() live in the
        # shared STATE lists. The match loop never runs the campaign's
        # particle pass, so without this they accumulate forever (and, per
        # draw_fx below, a local shot had no visible impact at all).
        effects.update_particles()
        effects.update_casings(self.walls)
        self._advance_bolts()

    def _advance_bolts(self):
        """Fly local bolts one frame; the impact lands on arrival."""
        from core.config import audio
        for b in self._bolts[:]:
            b["t"] += 1
            if b["t"] >= b["life"]:
                ex = b["x"] + b["dx"] * b["travel"]
                ey = b["y"] + b["dy"] * b["travel"]
                # The impact sound is tied to the impact PUFF, not to the
                # trigger pull. Playing it on the pull would put a wall
                # thud under every shot, including the ones that hit, and
                # the two would drift apart as the bolt flight time changed.
                audio.play("bullet_impact_enemy" if b["hit"]
                           else "concrete_impact", volume=IMPACT_VOLUME)
                if not b["hit"]:
                    from fx.effects import spawn_particles  # lazy: fx loads later
                    spawn_particles(ex, ey, (190, 180, 160), count=6)
                self._bolts.remove(b)

    def _draw_bolts(self, surface):
        """In-flight bolts, drawn like the campaign's bullets: soft glow,
        sharp core, and a short trail behind the direction of travel."""
        for b in self._bolts:
            f = min(1.0, b["t"] / float(max(1, b["life"])))
            px = b["x"] + b["dx"] * b["travel"] * f
            py = b["y"] + b["dy"] * b["travel"] * f
            sx, sy = px - self.cam_x, py - self.cam_y
            back = min(b["travel"] * f, BOLT_TRAIL_PX)
            pygame.draw.line(surface, (255, 220, 140),
                             (sx, sy),
                             (sx - b["dx"] * back, sy - b["dy"] * back), 2)
            surface.blit(bullet_glow, (int(sx - 8), int(sy - 8)))
            pygame.draw.circle(surface, C_BULLET, (int(sx), int(sy)), 2)

    def draw_fx(self, surface):
        """Impact puffs and ejected casings from local shots.

        Rendered in world space like everything else; the mission draw
        passes use the identical ``.draw(surface, cam_x, cam_y)`` calls.
        """
        for p in STATE.particles:
            p.draw(surface, self.cam_x, self.cam_y)
        for c in STATE.casings:
            c.draw(surface, self.cam_x, self.cam_y)
        self._draw_bolts(surface)

    def _draw_feel(self, surface):
        """Hit confirm and floating HIT text. Drawn on top."""
        # (The local shot itself now flies as a bolt in the world layer via
        # draw_fx, so there is no static tracer line here anymore.)

        # Hit confirm: a red flash around the standard reticle, so a landed
        # shot reads instantly without having to look at the health bar.
        # The reticle itself is ui.hud.draw_gameplay_crosshair() -- this is
        # only the flash on top of it, and it must use the SAME scaled mouse
        # position or it sits offset from the crosshair at non-default
        # resolutions.
        if self._hit_confirm > 0:
            from ui.hud import get_scaled_mouse  # lazy: ui.hud loads later
            cx, cy = get_scaled_mouse()
            r = 7
            for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1)):
                pygame.draw.line(surface, (255, 70, 70), (cx + dx * r, cy + dy * r),
                                 (cx + dx * (r + 5), cy + dy * (r + 5)), 2)

        font = _small_font()
        for f in self._floaters:
            fx, fy, alpha, text, col = f[0], f[1], f[2], f[3], f[4]
            if alpha <= 0:
                continue
            surf = font.render(text, True, col)
            surface.blit(surf, (int(fx - self.cam_x - surf.get_width() // 2),
                                int(fy - self.cam_y)))

    def advance_corpses(self):
        """Age every fallen body by one frame. Call once per update().

        Timed off the game's frame clock rather than off drawing, because a
        topple measured in draw calls runs at whatever rate something happens to
        paint: a paused or overlaid frame skips the arena draw and the body
        freezes mid-fall, then lurches when it resumes. Aging here keeps the fall
        at its intended ~0.37s regardless of how often anything is blitted.
        """
        for pid, body in self._corpses.items():
            age = self._corpse_age.get(pid, 0) + 1
            self._corpse_age[pid] = age
            body.t = age

    def sync(self, world):
        """Pose every sprite from the interpolated snapshot.

        Called once per rendered frame with the output of
        ``MatchSession.sample_world()``. Returns {id: (player, entity)} so
        the caller can draw names and health bars against the same data.
        """
        live = set(world.keys()) if world else set()
        # Forget sprites for players who left, so a joiner does not inherit
        # a stale walk cycle or HP from whoever held that slot last match.
        for pid in [p for p in self._views if p not in live]:
            del self._views[pid]
        # Corpses follow the same lifetime as the slot's sprite: a departed
        # player must not leave a body standing in their place forever.
        for table in (self._corpses, self._corpse_age):
            for pid in [p for p in table if p not in live]:
                del table[pid]
        # Death is tracked through the respawn countdown, NOT through the
        # entity's state bit. The interpolated world only carries PS_DEAD in the
        # ~2 Hz packet, so between packets the flag reverts and a corpse keyed on
        # it would be created and destroyed several times a second -- which looks
        # like a body strobing on the floor. _respawn is seeded from that packet
        # and then ticked down locally every frame, so it stays true across the
        # whole gap and clears exactly when the player comes back.
        waiting = set(self._respawn_waiting or ())
        for pid in list(self._corpses):
            if pid not in waiting:
                self._corpses.pop(pid, None)
                self._corpse_age.pop(pid, None)
        for pid in [p for p in self._reload_prev if p not in live]:
            del self._reload_prev[pid]
        # Listener position for positioned remote audio. Taken from the local
        # entity, which is the interpolated one, so a remote shot is panned
        # against roughly where the player is standing rather than where they
        # were a packet ago.
        me_ent = (world or {}).get(self._local_id)
        if me_ent is not None:
            self._listener = (me_ent[2], me_ent[3])
        out = {}
        for pid, ent in (world or {}).items():
            v = self._pose(pid)
            # Snap the rect to the interpolated position. This is the one
            # place a snapshot value becomes pixels.
            v.rect.centerx = int(round(ent[2]))
            v.rect.centery = int(round(ent[3]))
            # Take the short way round so a player crossing north does not
            # spin 350 degrees in one frame.
            cur = v.angle
            # Snapshots carry DEGREES (the wire format wraps 0..360);
            # Player.angle is in RADIANS, because draw() feeds it straight
            # to math.cos/math.sin. Converting here rather than changing the
            # wire format keeps the readable degrees on the network.
            d = (ent[4] - math.degrees(cur)) % 360.0
            if d > 180.0:
                d -= 360.0
            v.angle = (cur + math.radians(d)) % (2 * math.pi)
            v.hp = max(0, min(100, ent[5]))
            v.invincible_timer = 0.75 if (ent[8] & P.F_INVULNERABLE) else 0.0
            # ── per-player weapon rig ──────────────────────────────────
            # The shared sprite picks its gun silhouette from the mission
            # global STATE.current_weapon, which in a match is whatever the
            # last campaign left there -- so every player drew the SAME gun,
            # and a real switch (2/3/Q) changed nothing on screen. Drive the
            # sprite from THIS player's entity instead, and arm the sprite's
            # swap animation when the gun actually changes.
            wpn = ent[7] if len(ent) > 7 else P.WPN_PISTOL
            meta = self._view_meta.setdefault(pid, _PoseMeta())
            prev = meta.weapon
            # Only a genuine mid-life switch animates: the first sighting of
            # a player must not, and neither must the forced pistol you come
            # back holding after a death (that would swap-dance on respawn).
            if (prev is not None and prev != wpn
                    and meta.state != P.PS_DEAD
                    and ent[6] != P.PS_DEAD):
                v.swap_timer = getattr(v, "swap_duration", 24)
            meta.weapon = wpn
            meta.state = ent[6]
            v.rig_weapon = rig_for_weapon(wpn)
            # Reload animation. The entity says only "reloading"; the sprite
            # walks its arm through a 0..1 progress, and the arena never
            # passed one, so a reload was frozen on its first frame. Run a
            # local clock for the weapon's reload length and feed that in.
            if ent[6] == P.PS_RELOADING:
                if meta.reload <= 0:
                    total = max(1, int(AR.weapon_stats(wpn)["reload"]))
                    meta.reload = total
                    meta.reload_total = total
                    # Sound on the rising edge ONLY, and only for a reload
                    # that began after this view was already watching that
                    # player. `pid in _reload_prev` is the part that matters:
                    # without it a player who joins mid-reload clicks a
                    # magazine swap for the first time anybody sees them,
                    # which is noise rather than feedback.
                    if self._reload_prev.get(pid) is False:
                        from core.config import audio  # lazy: config pulls audio
                        audio.play("reload", volume=RELOAD_VOLUME)
                else:
                    meta.reload -= 1
            else:
                meta.reload = 0
            self._reload_prev[pid] = (ent[6] == P.PS_RELOADING)
            # Muzzle flash: the snapshot only carries F_FIRING for the few
            # ticks the host has the muzzle up, so turn it into a short
            # per-render timer here. Otherwise a 20 Hz packet that catches a
            # single tick makes the flash a one-frame blink.
            meta.muzzle = (MUZZLE_FRAMES if (ent[8] & P.F_FIRING)
                           else max(0, meta.muzzle - 1))
            out[pid] = (v, ent)
        return out

    def draw_players(self, surface, posed, local_id):
        """Draw every posed player, then name tags and health bars.

        Ordered by y so a player lower on the screen overlaps one above
        them, which is what sells a top-down view as a 3D space.
        """
        vw, vh = surface.get_width(), surface.get_height()
        for pid in sorted(posed.keys(),
                          key=lambda p: posed[p][0].rect.centery):
            v, ent = posed[pid]
            x = int(v.rect.centerx - self.cam_x)
            y = int(v.rect.centery - self.cam_y)
            if not (-40 < x < vw + 40 and -40 < y < vh + 40):
                continue
            dead = (ent[6] == P.PS_DEAD
                    or pid in (self._respawn_waiting or ()))
            moving = ent[6] == P.PS_MOVING
            reloading = ent[6] == P.PS_RELOADING
            if dead:
                # A fallen body instead of the live sprite with a red X over it.
                # The X said "this entity is in a state you cannot act on"; a
                # corpse says who died, where they fell, which way they were
                # looking and what they were carrying -- all information a player
                # actually uses to decide whether to push that corridor.
                self._draw_corpse(surface, pid, v, ent)
                continue
            # Progress for the reload arm animation, from the local clock
            # sync() runs. 0..1 across the magazine swap.
            meta = self._view_meta.setdefault(pid, _PoseMeta())
            total = max(1, meta.reload_total)
            reload_progress = (1.0 - meta.reload / float(total)) if reloading else 0.0
            # Reuse the real sprite: real walk cycle, real breathing, real
            # recoil. The camera goes in as fcx/fcy exactly as the missions
            # pass it, because Player.draw subtracts it itself.
            v.draw(surface, int(self.cam_x), int(self.cam_y),
                   walls=(), reload_active=reloading,
                   reload_progress=reload_progress,
                   melee_active=ent[6] == P.PS_MELEE,
                   is_moving=moving)
            # Muzzle flash, matching the campaign's: the shared 80x80
            # MUZZLE_FLASH sprite centred on the barrel tip. Drawn for every
            # player (local and remote) so you can see who is shooting.
            if meta.muzzle > 0:
                reach = reach_for_view(v)
                tip_x = x + math.cos(v.angle) * reach
                tip_y = y + math.sin(v.angle) * reach
                surface.blit(MUZZLE_FLASH, (int(tip_x - 40), int(tip_y - 40)))
            self._draw_tag(surface, x, y, pid, local_id, v, ent, dead)

    def _draw_corpse(self, surface, pid, v, ent):
        """Draw one dead player as a fallen body, aged since they died.

        The body is built ONCE, on the first frame this player is seen dead, and
        then only advanced. That matters: the sprawl pose is chosen from a seed
        at construction, so rebuilding per frame would re-roll it and the corpse
        would visibly vibrate between three different poses at 60fps.

        It also means the fall animates from wherever they were standing, because
        the angle and position captured at construction are the last ones the
        snapshot reported before the death flag arrived.
        """
        wx, wy = ent[2], ent[3]
        angle = ent[4]
        rig = getattr(v, "rig_weapon", None) or "pistol"
        body = self._corpses.get(pid)
        if body is None:
            # Built once, on the first frame this player is seen dead. The
            # sprawl pose comes from a seed chosen here, so rebuilding per
            # frame would re-roll it and the corpse would visibly vibrate
            # between three poses at 60fps -- and its position must be frozen
            # too, because the interpolated buffer keeps nudging a dead entity
            # and a sliding body reads as a teleporting one.
            body = _fallen.FallenBody(
                wx, wy, angle, v._rk, v.look.get("head") or "head_kevlar",
                rig, seed=(pid * 2654435761 + int(self._host_tick)) & 0x7FFFFFFF)
            self._corpses[pid] = body
            self._corpse_age[pid] = 0
        elif body.head_id != v.look.get("head") or body.rig_name != rig:
            # A slot reused by a different human (or the same human after they
            # changed loadout) must not inherit the previous occupant's corpse.
            body = _fallen.FallenBody(
                wx, wy, angle, v._rk, v.look.get("head") or "head_kevlar",
                rig, seed=(pid * 2654435761 + int(self._host_tick)) & 0x7FFFFFFF)
            self._corpses[pid] = body
            self._corpse_age[pid] = 0
        body.t = self._corpse_age.get(pid, 0)
        body.draw(surface, self.cam_x, self.cam_y)
        # Tags still belong on a corpse: whose body this is, and how long until
        # they are back up.
        x = int(wx - self.cam_x)
        y = int(wy - self.cam_y)
        self._draw_tag(surface, x, y, pid, self._local_id, v, ent, True)

    def _draw_tag(self, surface, x, y, pid, local_id, v, ent, dead):
        col = color_for(pid, local_id)
        if dead:
            # No red X any more. It was the only signal that a sprite was a
            # corpse, so it had to sit right on the body; now that a dead player
            # is drawn as a fallen body with their own blood and dropped gun, the
            # X just scribbled over the thing that already says "dead" and made
            # the corpse unreadable. The name tag and countdown below still carry
            # who and when.
            # The local corpse gets no tag either. The camera follows it, so
            # the tag lands directly under the ELIMINATED plate, half-hidden
            # behind the one card that matters.
            if pid != local_id:
                self._draw_name_tag(surface, x, y, pid, col, dimmed=True)
                self._draw_remote_respawn(surface, x, y, pid, col)
            return
        bw = 26
        pygame.draw.rect(surface, (18, 18, 22),
                         (x - bw // 2 - 1, y + 19, bw + 2, 6))
        fill = max(0, min(bw, int(bw * v.hp / 100.0)))
        hp_col = ((90, 230, 130) if v.hp > 50 else
                  (240, 200, 80) if v.hp > 25 else (235, 90, 80))
        pygame.draw.rect(surface, hp_col, (x - bw // 2, y + 20, fill, 4))
        # Spawn protection reads as a ring, so you know not to shoot.
        if ent[8] & P.F_INVULNERABLE:
            pygame.draw.circle(surface, (150, 210, 255), (x, y), 19, 1)
        self._draw_name_tag(surface, x, y, pid, col)

    def _draw_name_tag(self, surface, x, y, pid, col, dimmed=False):
        """The player's name above their head, on a backing plate.

        This label used to not exist, which is the whole reason a match was
        eight anonymous colour swatches: colour answers "who is that", but
        only a name answers "is that the person I just shot", and in a TDM
        match "which side is that on".

        The plate is not decoration. On a bright floor tile an unbacked name
        vanishes, and a name that cannot be read is the same as no name at
        all. It is drawn in the player's own colour so the two cues agree.
        """
        try:
            font = _small_font()
            team = self._teams.get(str(pid))
            tag = AR.TEAM_NAMES.get(team, "") if team is not None else ""
            name = self.name_for(pid)
            ink = (150, 158, 172) if dimmed else (242, 246, 252)
            label = font.render(name, True, ink)
            side = font.render(tag, True, ink) if tag else None
            w = label.get_width() + (6 + side.get_width() if side else 0)
            h = label.get_height()
            lift = 38 if pid == getattr(self, "_local_id", None) else 31
            plate = pygame.Rect(x - w // 2 - 5, y - lift, w + 10, h + 2)
            bg = pygame.Surface((plate.w, plate.h), pygame.SRCALPHA)
            bg.fill((8, 10, 14, 120 if dimmed else 175))
            surface.blit(bg, plate.topleft)
            pygame.draw.rect(surface, col if not dimmed else (90, 80, 80),
                             plate, 1)
            surface.blit(label, (plate.x + 5, plate.y + 1))
            if side is not None:
                surface.blit(side, (plate.x + 5 + label.get_width() + 6,
                                    plate.y + 1))
        except Exception:
            # A tag is never worth taking a frame down for.
            pass

    def _draw_remote_respawn(self, surface, x, y, pid, col):
        """A remote player's respawn countdown, under their corpse.

        Knowing that the player who just killed you is back in two seconds is
        real information and the only way to use it is to reposition. It goes
        on the corpse rather than on a card, so a fight with several players
        down stays readable as one screen.

        Only remote players: the local one already has the full plate, and two
        surfaces showing the same countdown is worse than one.
        """
        left = (self._respawn_remote or {}).get(pid)
        if not left or left <= 0:
            return
        try:
            font = _small_font()
            secs = max(1, int(math.ceil(float(left) - 0.0001)))
            label = font.render("BACK IN %d" % secs, True, (200, 170, 170))
            plate = pygame.Rect(x - label.get_width() // 2 - 5, y + 8,
                                label.get_width() + 10,
                                label.get_height() + 2)
            bg = pygame.Surface((plate.w, plate.h), pygame.SRCALPHA)
            bg.fill((8, 10, 14, 120))
            surface.blit(bg, plate.topleft)
            pygame.draw.rect(surface, (90, 80, 80), plate, 1)
            surface.blit(label, (plate.x + 5, plate.y + 1))
        except Exception:
            pass

    def draw_hud(self, surface, world, local_id, scoreboard, map_name,
                   mode="FFA", clock=None, team_scores=None,
                   killfeed=(), local_weapon=None, local_ammo=None,
                   local_armour=None, pickups=None, local_carry=None,
                   score_limit=None, phase="playing", respawn=None,
                   respawn_killer=None):
        """Scoreboard strip, round clock, kill feed, and the local loadout.

        KRAP-terminal dossier readout (v2): 30px bar, left dossier text
        with orange rule, center LIVE + clock/team plate, right fixed-width
        score chips (no layout jitter), killfeed on backing plates below.
        Dead players render dimmed (read from ``world`` entity states).

        ``pickups`` is accepted and ignored here: draw() consumes it for the
        map itself. It is passed through **hud so that a caller can hand the
        same dict to draw() without having to strip the key first -- which it
        otherwise would have to, forever, for every non-HUD field.
        """
        try:
            font = _term_font()
            bold = _term_font_bold()
        except Exception:
            return
        w = surface.get_width()
        BAR_H = 30
        pygame.draw.rect(surface, (12, 13, 17), (0, 0, w, BAR_H), 0)
        pygame.draw.line(surface, (46, 50, 62), (0, BAR_H), (w, BAR_H))
        # -- left: dossier plate --
        mode_txt = bold.render(mode, True, (255, 150, 60))
        rest = "// %s" % map_name.upper()
        if score_limit:
            try:
                rest += " // FIRST TO %d" % int(score_limit)
            except (TypeError, ValueError):
                pass
        rest_txt = font.render(rest, True, (150, 160, 180))
        surface.blit(mode_txt, (10, 7))
        surface.blit(rest_txt, (10 + mode_txt.get_width() + 8, 7))
        pygame.draw.line(surface, (255, 150, 60), (10, 25),
                         (10 + mode_txt.get_width() + 8 + rest_txt.get_width(),
                          25), 1)
        # Persistent squad plate. World tags vanish the moment a teammate
        # walks off-camera; a TDM fight still needs to know who is on your
        # side and which colour they wear.
        if str(mode).upper() == AR.MODE_TDM and self._teams:
            try:
                raw_team = self._teams.get(str(local_id),
                                           self._teams.get(local_id))
                try:
                    my_team = int(raw_team)
                except (TypeError, ValueError):
                    my_team = raw_team
                if my_team not in (None, AR.TEAM_NONE):
                    mates = []
                    for key, team in self._teams.items():
                        if str(key) == str(local_id):
                            continue
                        try:
                            if int(team) != int(my_team):
                                continue
                            mates.append(self.name_for(int(key)))
                        except (TypeError, ValueError):
                            continue
                    side = AR.TEAM_NAMES.get(my_team, "TEAM")
                    body = "%s  ·  %s" % (self.name_for(local_id), side)
                    if mates:
                        body += "   with  " + " + ".join(mates)
                    plate_txt = font.render(body, True, (230, 235, 245))
                    pr = pygame.Rect(8, BAR_H + 6,
                                     plate_txt.get_width() + 16, 20)
                    pygame.draw.rect(surface, (12, 13, 17), pr)
                    pygame.draw.rect(surface, (255, 150, 60), pr, 1)
                    surface.blit(plate_txt, (pr.x + 8, pr.y + 3))
            except Exception:
                pass
        # -- center: LIVE + clock/team plate --
        center_txt = None
        if team_scores:
            a = team_scores.get("0", 0)
            b = team_scores.get("1", 0)
            center_txt = bold.render("IPA %d : %d KRAP" % (a, b), True,
                                     (200, 205, 220))
        elif clock is not None:
            secs = max(0, int(clock) // 60)
            center_txt = bold.render("%d:%02d" % (secs // 60, secs % 60), True,
                                     (200, 205, 220))
        if center_txt is not None:
            cw = center_txt.get_width()
            plate = pygame.Rect(w // 2 - cw // 2 - 10, 4, cw + 20, 22)
            pygame.draw.rect(surface, (16, 19, 26), plate)
            pygame.draw.rect(surface, (46, 50, 62), plate, 1)
            surface.blit(center_txt, (w // 2 - cw // 2, 7))
        # -- right: the local player's own standing --
        # This used to be a six-row rank column, right-aligned in the bar. A
        # name on each row made it 54px wider, and at 1000px the column then
        # overlapped BOTH the mode dossier on the left and the clock/team
        # plate in the middle -- three pieces of information fighting over one
        # 30px strip.
        #
        # So the bar keeps only the one number a player actually needs while
        # fighting: how THEY are doing. The full ranked list is on the pause
        # card, where there is room for it and where a player goes when they
        # actually want to read the table.
        #
        # Falls back to the leader when the local player has no row yet (their
        # first half-second in the match), so the slot is never blank while a
        # number exists.
        CHIP_W = 190
        rows = list(scoreboard or [])
        mine_row = None
        rank = 0
        for i, row in enumerate(rows):
            try:
                if row[0] == local_id:
                    mine_row, rank = row, i
                    break
            except (IndexError, TypeError):
                continue
        if mine_row is None and rows:
            mine_row, rank = rows[0], 0
        if mine_row is not None:
            chip = pygame.Rect(w - 10 - CHIP_W, 4, CHIP_W, 22)
            col = color_for(local_id, local_id)
            try:
                ent = (world or {}).get(local_id)
                dead = ent is not None and ent[6] == P.PS_DEAD
            except (IndexError, TypeError):
                dead = False
            if dead:
                col = (90, 95, 108)
            pygame.draw.rect(surface, (16, 19, 26), chip)
            pygame.draw.rect(surface, (46, 50, 62) if dead else col, chip, 1)
            pre = font.render(_T("arena.you"), True, col)
            kd = bold.render("%d-%d" % (mine_row[1], mine_row[2]), True, col)
            place = font.render("%d/%d" % (rank + 1, len(rows)), True, col)
            # Three fixed columns: YOU, then the name in whatever is left, then
            # the rank and K-D pinned to the right. All measured BEFORE the
            # name is clipped, so the name can never grow into them.
            name_x = chip.x + 6 + pre.get_width() + 6
            right_x = chip.right - 8 - kd.get_width() - 6 - place.get_width()
            nm = font.render(_fit_px(self.name_for(local_id), font,
                                     right_x - 6 - name_x), True, col)
            surface.blit(pre, (chip.x + 6, 7))
            surface.blit(nm, (name_x, 7))
            surface.blit(place, (right_x + kd.get_width() + 6, 7))
            surface.blit(kd, (chip.right - 8 - kd.get_width(), 7))
        self._draw_killfeed(surface, killfeed, local_id, top=BAR_H + 10)
        # Drawn last so it is the last thing on the HUD: while you are dead
        # this is the only thing that matters, and it must never sit under a
        # score chip or a kill-feed row.
        self._draw_respawn(surface, respawn, local_id, respawn_killer)
        self._draw_loadout(surface, local_weapon, local_ammo, local_armour,
                           world, local_id, local_carry)

    def _draw_respawn(self, surface, respawn, local_id=0, killer=None):
        """The dead player's waiting plate: a countdown, and who did it.

        Death used to be exactly one dimmed sprite -- no clock, no
        attribution -- so by the time the player registered the kill it was
        already over. This is the beat that makes a death legible: how long
        until you are back, and who to watch for.

        Only the LOCAL plate occupies the screen. Everyone else's countdown
        rides above their own corpse through _draw_tag, so a corpse stays
        readable as information without this card covering the fight that is
        still going on around it.
        """
        if not respawn:
            return
        try:
            # `not mine` and not `mine > 0` on purpose. A caller that hands us
            # an expired timer must get no plate at all -- drawing
            # "ELIMINATED / 1" for a player who is already back is worse than
            # drawing nothing, because it looks like the game has frozen.
            mine = respawn.get(local_id)
            if not mine or mine <= 0:
                return
            bold = _term_font_bold()
            term = _term_font()
        except Exception:
            return
        w, h = surface.get_width(), surface.get_height()
        cx = w // 2
        # Sits above centre, not on it. The camera follows the local player,
        # so a dead player's own corpse is dead centre -- and a card centred
        # on the screen covers the one thing the player may still want to see
        # (where they died, and who is still walking around down there).
        cy = h // 2 - 70
        plate = pygame.Rect(cx - 190, cy - 70, 380, 132)
        bg = pygame.Surface(plate.size, pygame.SRCALPHA)
        bg.fill((8, 10, 14, 210))
        surface.blit(bg, plate.topleft)
        pygame.draw.rect(surface, (150, 60, 60), plate, 2)
        head = bold.render(_T("arena.eliminated"), True, (235, 90, 80))
        surface.blit(head, (cx - head.get_width() // 2, plate.y + 12))
        # Round UP, and only ever show a whole number: a timer that reads
        # "respawning in 0" for 300 ms looks stuck.
        secs = max(1, int(math.ceil(float(mine) - 0.0001)))
        num = bold.render(str(secs), True, (255, 205, 110))
        surface.blit(num, (cx - num.get_width() // 2, plate.y + 36))
        if killer is not None:
            sub = term.render("RESPAWNING  ·  TAKEN BY %s"
                              % _fit(self.name_for(killer), 20),
                              True, (170, 180, 200))
            surface.blit(sub, (cx - sub.get_width() // 2, plate.y + 74))
        hint = term.render(_T("arena.enter_chat"), True, (110, 120, 134))
        surface.blit(hint, (cx - hint.get_width() // 2, plate.bottom - 22))

    def _draw_weapon_strip(self, surface, x, y, weapon, carry):
        """The number-key row above the loadout: what you can switch to.

        Switching only exists in a match if you know it exists, and the
        honest answer changes constantly -- the shotgun is not yours until
        you walk over it. So the strip shows every slot, dims the ones the
        host would refuse, and marks the one you are holding.
        """
        try:
            font = _small_font()
        except Exception:
            return
        owned = set(carry) if carry else None
        slots = ((1, P.WPN_PISTOL), (2, P.WPN_OS12), (3, P.WPN_K9))
        cx = x + 2
        for num, wid in slots:
            name = AR.weapon_stats(wid)["name"]
            label = "%d %s" % (num, name)
            # Unknown carry (before the host's first packet) is shown as
            # available rather than locked: a greyed-out pistol on frame one
            # would look like a bug.
            locked = owned is not None and wid not in owned
            current = wid == weapon
            col = _weapon_slot_color(current, locked)
            if current:
                # The held weapon gets a lit plate and a bright, bold label:
                # which gun you are actually firing must not depend on
                # reading a colour, and must never look greyed out.
                txt = _bold_font().render(label, True, col)
                pad = pygame.Rect(cx - 3, y - 2, txt.get_width() + 6,
                                  txt.get_height() + 4)
                pygame.draw.rect(surface, (52, 39, 18), pad)
                pygame.draw.rect(surface, (255, 150, 20), pad, 1)
            else:
                txt = font.render(label, True, col)
            surface.blit(txt, (cx, y))
            cx += txt.get_width() + 10
        # The cycle key is only advertised once cycling would do anything.
        if owned and len(owned) > 1:
            hint = font.render(_T("arena.q"), True, (120, 128, 142))
            surface.blit(hint, (cx, y))
            pygame.draw.rect(surface, (58, 64, 76),
                             (cx - 3, y - 2, hint.get_width() + 6,
                              hint.get_height() + 4), 1)

    def _draw_killfeed(self, surface, rows, local_id=0, top=30):
        """Killfeed rows on backing plates, newest on top.

        NAMES, not colour swatches. This row used to be two `##` blocks in the
        killer's and victim's colours with an orange `>` between, which told a
        player that a kill had happened and nothing about who was involved --
        so the feed was decoration. With names it is the fastest way to learn
        who on the map is dangerous, which is the whole reason it is on
        screen at all. Weapon tag stays dimmed behind them.

        Names are clipped to KILLFEED_NAME_CHARS so two 16-character handles
        plus the weapon tag cannot grow a row wider than the screen.
        """
        if not rows:
            return
        try:
            font = _term_font()
            bold = _term_font_bold()
        except Exception:
            return
        sw = surface.get_width()
        y = top
        for row in reversed(list(rows)[-5:]):
            age, killer, victim, weapon = row[0], row[1], row[2], row[3]
            # Fade out over the last second so it never just vanishes.
            alpha = 255 if age < 240 else int(255 * max(0.0, (300 - age) / 60.0))
            if alpha <= 0:
                continue
            wname = P.WPN_NAMES.get(weapon, "")
            kcol = color_for(killer, local_id)
            vcol = color_for(victim, local_id)
            kname = self.name_for(killer)
            vname = self.name_for(victim)
            if killer == victim:
                # Suicide reads as one red name, never as a frag you scored on
                # somebody. Two identical names with a `>` between them looked
                # exactly like a legitimate kill.
                kcol = vcol = (235, 90, 80)
                vname = "%s (SUICIDE)" % kname
            ksw = bold.render(_fit(kname, KILLFEED_NAME_CHARS), True, kcol)
            mid = bold.render(_T("arena.text"), True, (255, 150, 60))
            vsw = bold.render(_fit(vname, KILLFEED_NAME_CHARS), True, vcol)
            wtxt = font.render("[%s]" % wname, True, (150, 160, 180))
            total = (ksw.get_width() + mid.get_width() + vsw.get_width()
                     + 6 + wtxt.get_width() + 16)
            chip = pygame.Rect(sw - 10 - total, y, total, 20)
            bg = pygame.Surface((chip.w, chip.h), pygame.SRCALPHA)
            bg.fill((10, 12, 16, 200))
            surface.blit(bg, chip.topleft)
            pygame.draw.rect(surface, (40, 44, 56), chip, 1)
            for part in (ksw, mid, vsw, wtxt):
                part.set_alpha(max(0, min(255, alpha)))
            cx = chip.x + 8
            surface.blit(ksw, (cx, y + 3))
            cx += ksw.get_width()
            surface.blit(mid, (cx, y + 3))
            cx += mid.get_width()
            surface.blit(vsw, (cx, y + 3))
            cx += vsw.get_width() + 6
            surface.blit(wtxt, (cx, y + 3))
            y += 24

    def _draw_loadout(self, surface, weapon, ammo, armour, world, local_id,
                      carry=None):
        """Bottom-left: weapon strip, weapon name, magazine, armour pip."""
        if weapon is None:
            return
        try:
            font = _small_font()
        except Exception:
            return
        stats = AR.weapon_stats(weapon)
        sw, sh = surface.get_width(), surface.get_height()
        x, y = 12, sh - 34
        self._draw_weapon_strip(surface, x - 6, y - 30, weapon, carry)
        pygame.draw.rect(surface, (12, 13, 17), (x - 6, y - 6, 176, 30))
        name = font.render(stats["name"], True, (210, 215, 230))
        surface.blit(name, (x, y))
        if ammo is not None:
            col = (255, 200, 90) if ammo == 0 else (170, 175, 195)
            mag = font.render("%d/%d" % (ammo, stats["mag"]), True, col)
            surface.blit(mag, (x + 74, y))
        if armour:
            pip = font.render("ARM %d" % armour, True, (110, 170, 255))
            surface.blit(pip, (x + 74, y + 13))
        if world and local_id in world:
            hp = max(0, min(100, world[local_id][5]))
            base = surface.get_height() - 26
            pygame.draw.rect(surface, (12, 13, 17), (8, base, 150, 18))
            fill = int(134 * hp / 100.0)
            col = ((90, 230, 130) if hp > 50 else
                   (240, 200, 80) if hp > 25 else (235, 90, 80))
            pygame.draw.rect(surface, col, (11, base + 3, fill, 12))
            lbl = font.render("HP %d" % hp, True, (230, 235, 245))
            surface.blit(lbl, (16, base + 3))

    def draw(self, surface, world, local_id, scoreboard=(), **hud):
        """One call draws the whole frame, keeping callers trivial.

        Extra HUD state (mode, clock, team scores, kill feed, local loadout)
        arrives as keywords so the call site can pass whatever the host last
        reported without this function needing to know where it came from.
        """
        self._local_id = local_id
        # Everyone's respawn countdown, for the corpses' "BACK IN n" tags.
        # Taken here rather than threaded into draw_players() because
        # draw_players() walks every sprite in y-order and has no business
        # knowing about match rules.
        self._respawn_remote = hud.get("respawn") or {}
        self.update_camera(world, local_id,
                           surface.get_width(), surface.get_height())
        # Fill the frame before anything else. On a map smaller than the
        # viewport the tiles leave margins, and without this the previous
        # screen bled through there (the menu background around the map).
        surface.fill(VOID_COLOR)
        self.draw_tiles(surface)
        self.draw_pickups(surface, hud.get("pickups"))
        # Frame the play area so the void margin reads as a deliberate
        # border rather than an unfinished edge.
        pygame.draw.rect(surface, VOID_EDGE,
                         (int(-self.cam_x), int(-self.cam_y),
                          self.map_w, self.map_h), 1)
        posed = self.sync(world)
        self.draw_players(surface, posed, local_id)
        self.draw_fx(surface)
        self.draw_hud(surface, world, local_id, scoreboard, self.map_name,
                      **hud)
        # The reticle is drawn HERE rather than by the main loop's
        # ui.hud.draw_crosshair(). That one returns early unless the state
        # is GAME/WALK and the OS pointer is visible, neither of which holds
        # during a match -- so routing the arena through it draws nothing.
        # draw_combat_reticle() is the shared shape M3 uses, while still
        # honoring show_crosshair / crosshair_size / colorblind_mode.
        #
        # require_player=False: its default gate reads STATE.player, which is
        # a mission concept and is always None in multiplayer, so leaving it
        # on suppressed the reticle entirely. Liveness comes from the snapshot
        # instead, since the local player must still lose their reticle while
        # dead and awaiting respawn.
        from ui.hud import draw_combat_reticle  # lazy: ui.hud loads later
        me = world.get(local_id) if world else None
        # aim_frozen suppresses the reticle during the pre-game lobby and the
        # start countdown. The local entity is ALIVE in both -- the host seats
        # you and snapshots you before the sim runs -- so the liveness test
        # alone happily draws an aiming reticle over a MATCH LOBBY panel that has
        # no aimable anything in it. Input is already refused in those phases;
        # the crosshair was the last thing still pretending otherwise.
        aiming = (me is not None and me[6] != P.PS_DEAD
                  and not getattr(self, "aim_frozen", False))
        if aiming:
            draw_combat_reticle(surface, require_player=False)
        # Shot feedback goes on top of everything, including the HUD and the
        # reticle, so a tracer is never hidden behind a health bar and the
        # hit flash reads as part of the crosshair.
        self._draw_feel(surface)
        return posed


_FONT = None
_BOLD_FONT = None
_TERM_FONT = None
_TERM_FONT_BOLD = None


def _small_font():
    """Lazily built tag font. Cached: building one per frame is slow."""
    global _FONT
    if _FONT is None:
        try:
            _FONT = pygame.font.Font(None, 17)
        except Exception:
            _FONT = pygame.font.Font(pygame.font.get_default_font(), 14)
    return _FONT


def _bold_font():
    """Bold variant of the tag font, for the held-weapon slot."""
    global _BOLD_FONT
    if _BOLD_FONT is None:
        try:
            _BOLD_FONT = pygame.font.Font(None, 17)
        except Exception:
            _BOLD_FONT = pygame.font.Font(pygame.font.get_default_font(), 14)
        _BOLD_FONT.set_bold(True)
    return _BOLD_FONT


def _term_font():
    """Monospace terminal font for the KRAP-dossier scoreboard/killfeed.

    Matches the campaign's terminal look (Consolas, like font_terminal in
    core.config). Falls back to the default font headless so audits and
    smoke tests never raise inside the render loop.
    """
    global _TERM_FONT
    if _TERM_FONT is None:
        try:
            _TERM_FONT = pygame.font.SysFont("Consolas", 15)
        except Exception:
            _TERM_FONT = pygame.font.Font(pygame.font.get_default_font(), 14)
    return _TERM_FONT


def _term_font_bold():
    """Bold monospace for names/scores that must pop off the plate."""
    global _TERM_FONT_BOLD
    if _TERM_FONT_BOLD is None:
        try:
            _TERM_FONT_BOLD = pygame.font.SysFont("Consolas", 15, bold=True)
        except Exception:
            _TERM_FONT_BOLD = _term_font()
    return _TERM_FONT_BOLD


def _weapon_slot_color(current, locked):
    """Label colour for one slot in the number-key weapon strip.

    The HELD weapon must be the brightest thing in the strip. It used to be
    drawn near-black on its plate, which read as "greyed out" -- players
    could not tell which gun they were actually holding. Now it is warm
    amber: brighter than an available (unlocked) slot, with the locked slots
    dimmest of all so the hierarchy is unambiguous.
    """
    if current:
        return (255, 205, 110)
    if locked:
        return (74, 80, 92)
    return (176, 184, 198)
