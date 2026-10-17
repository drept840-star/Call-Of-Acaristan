
"""Player character: movement, drawing, weapon rig."""
import math
import os
from engine.core import LEGACY_RNG as _rng_legacy  # RPE6 R6: named 'legacy' rng stream
import time
import pygame

from engine.render2d import SurfacePen as _SurfacePen, pen_or_surface as _pen_or_surface  # RPE6 B-033 (facade only, E4)

from core.config import (
    TILE_SIZE, audio,
)
from core import appearance as _appearance
from core import outfits as _outfits
from entities import adornments as _adornments, weapon_rig as _weapon_rig
from core.surfaces import material_at, footstep_prefix
# Module-level STATE import. Required by resolve_melee() below (it reads
# STATE.melee_damage via getattr). Previously this import was missing - the
# original code relied on a lazy `from state import STATE` inside Player
# methods (e.g. barrel_tip), but resolve_melee() is a module-level function
# that references STATE directly, causing a NameError on the first melee
# attack. No circular-import risk: state.py only imports pygame.
from core.state import STATE
from engine.core import now_s as _now_s  # RPE6 B-001 timebase

_player_shadow = pygame.Surface((36, 18), pygame.SRCALPHA)
pygame.draw.ellipse(_player_shadow, (0, 0, 0, 55), (0, 0, 36, 18))


def _frozen():
    """ACA_FREEZE=1 pins the time-driven breathing term.

    Same switch core.lighting already honors. Without it draw() reads
    time.time(), so two renders of the same pose two milliseconds apart are
    not the same image, and nothing can prove that a color refactor preserved
    the sprite. See tools/avatar_parity.py.
    """
    return os.environ.get("ACA_FREEZE", "") == "1"


def _debug_rig_env():
    """ACA_DEBUG_RIG=1 draws the rig anchors over every Player sprite."""
    return os.environ.get("ACA_DEBUG_RIG", "") == "1"


def _draw_rig_debug(surface, an, pen=None):
    """Body anchor (white), shoulders (yellow), hand targets (green), weapon
    grip (magenta) and the arm/aim direction - polish pass Task 4 overlay."""
    pen = pen if pen is not None else _SurfacePen(surface)
    pt = lambda p: (int(round(p[0])), int(round(p[1])))  # noqa: E731
    pen.circle( (255, 255, 255), pt(an["body"]), 2)
    for k in ("shoulder_l", "shoulder_r"):
        pen.circle( (255, 220, 40), pt(an[k]), 2)
        pen.line( (120, 110, 40), pt(an[k]), pt(an["hand_l" if k[-1] == "l" else "hand_r"]), 1)
    for k in ("hand_l", "hand_r"):
        pen.circle( (60, 255, 90), pt(an[k]), 2)
    g = an["grip"]
    pen.circle( (255, 60, 220), pt(g), 2)
    dx, dy = an["arm_dir"]
    pen.line( (255, 60, 220), pt(g), pt((g[0] + dx * 10, g[1] + dy * 10)), 1)


class Player:
    debug_rig = False       # per-instance / dev-console toggle (see _debug_rig_env)

    # RPE6 Phase 5 (D4): declared with class-level defaults (an instance only carries the
    # attribute once set, so the replay state hash of the player object is unchanged).
    story_outfit = None   # outfit role set by the M5 draw ("coat", ...); None = default look
    _outfit_rk = None     # cache: ((look_key, outfit), roles) for the current outfit overlay

    def __init__(self, x, y, max_hp=100, appearance=None):
        self.rect = pygame.Rect(x, y, 32, 32)
        self.speed = 5
        self.angle = 0
        self.hp = max_hp
        self.max_hp = max_hp
        self.breathing = 0
        self.blink_timer = 0
        self.weapon_raised = False
        self.walk_cycle = 0.0
        self.was_moving = False
        self._step_timer = 0.0
        self._recoil_timer = 0
        self._recoil_offset = 0.0
        self._slide_timer = 0
        # ── Per-instance weapon rig (multiplayer) ───────────────────────
        # A mission picks the gun silhouette from the global
        # STATE.current_weapon, because a mission draws exactly one player.
        # A match draws several players holding different guns at once, so
        # the arena view sets this override per sprite. None means "read the
        # global", which leaves the whole campaign path byte-for-byte
        # unchanged -- the override only exists for the multiplayer case.
        self.rig_weapon = None
        # Same story for the weapon-swap animation. The campaign advances
        # STATE.weapon_swap_timer from its own per-mission update loop; an
        # arena has no such loop, so draw() advances this per-instance timer
        # when the arena arms it (see ArenaView.sync).
        self.swap_timer = 0
        self.swap_duration = 24
        # ── AEGIS i-frames (Pass E) ─────────────────────────────────
        # Per references/game-design.md "Invincibility Frames". After taking
        # any damage, the player is invincible for IFRAME_DURATION seconds
        # and the sprite blinks on/off at ~60ms windows so the player can
        # SEE that they were hit and that they are currently safe.
        # update_iframes(dt) must be called every frame from each mission's
        # game_update() to advance the timer + blink.
        self.invincible_timer = 0.0
        self.visible = True
        # IFRAME_DURATION is the total invincibility window in seconds.
        # 0.75s matches the AEGIS reference value and feels right for a
        # tactical shooter where the player needs time to reposition after
        # a hit. Tune via the constant below - never inline a magic number.
        self.IFRAME_DURATION = 0.75
        # BLINK_PERIOD_MS drives the sprite-flash cadence. 60ms ≈ 4 frames
        # at 60 FPS, so the sprite blinks ~8 times during the 0.75s window.
        self.BLINK_PERIOD_MS = 60
        # ── Cosmetic loadout ────────────────────────────────────────────
        # Resolved once here rather than per draw call: a match has up to eight
        # sprites on screen and the palette cannot change mid-frame. None is
        # the legacy look, so every existing Player(0, 0) site - campaign and
        # arena - keeps drawing exactly what it drew before.
        self.look = None
        self.set_appearance(appearance)

    def set_appearance(self, app):
        """Freeze *app* into the RGB roles this sprite draws with.

        Call on change only. The arena caches one Player per slot and reuses
        that slot as humans join and leave, so this has to be re-runnable on an
        existing sprite rather than only settable at construction; a sprite
        that kept the previous occupant's colours would be a cosmetic bug that
        reads as a cheat.
        """
        self.look = _appearance.normalize(app)
        self._rk = _appearance.resolve(self.look)
        self._rigs = self._rk["rigs"]
        self.look_key = _appearance.key_of(self.look)

    def take_damage(self, amount, force=False):
        """Apply damage to the player, respecting the i-frame window.

        Per AEGIS references/game-design.md. Returns True if damage was
        applied, False if blocked by i-frames. Callers may use the return
        value to decide whether to spawn blood particles / floating text
        / trigger hit-stop (a hit absorbed by i-frames should NOT produce
        a feedback burst, otherwise the player thinks they were hit).

        ``force=True`` bypasses i-frames - use ONLY for set-piece damage
        that the player cannot dodge and that the narrative requires to
        land (e.g. the Mission 2 sniper intro shot, the tanker blast
        during a scripted trigger). Tactical combat damage must always
        go through the default path so i-frames can do their job.
        """
        if not force and self.invincible_timer > 0:
            return False
        self.hp -= amount
        self.invincible_timer = self.IFRAME_DURATION
        # Force the first blink frame to be invisible so the hit is
        # immediately readable (otherwise the first 60ms shows the sprite
        # normally and the player doesn't realize i-frames started).
        self.visible = False
        return True

    def update_iframes(self, dt):
        """Advance the i-frame timer + sprite blink. Call every frame.

        Per AEGIS spec: visible = (int(timer_ms) // BLINK_PERIOD_MS) % 2 == 0.
        When the timer expires, visibility is restored to True.
        """
        if self.invincible_timer > 0:
            self.invincible_timer -= dt
            if self.invincible_timer <= 0:
                self.invincible_timer = 0.0
                self.visible = True
            else:
                # Blink: visible only on alternating ~BLINK_PERIOD_MS windows.
                timer_ms = int(self.invincible_timer * 1000)
                self.visible = (timer_ms // self.BLINK_PERIOD_MS) % 2 == 0
        else:
            self.visible = True

    def move(self, dx, dy, walls):
        ox, oy = self.rect.centerx, self.rect.centery
        self.rect.x += dx
        for wall in walls:
            if self.rect.colliderect(wall):
                if dx > 0:
                    self.rect.right = wall.left
                if dx < 0:
                    self.rect.left = wall.right
        self.rect.y += dy
        for wall in walls:
            if self.rect.colliderect(wall):
                if dy > 0:
                    self.rect.bottom = wall.top
                if dy < 0:
                    self.rect.top = wall.bottom
        # ── Footsteps: distance-based cadence, material-aware timbre ──
        moved = math.hypot(self.rect.centerx - ox, self.rect.centery - oy)
        if moved > 0.5:
            self._step_timer -= moved
            if self._step_timer <= 0:
                mat = material_at(self.rect.centerx, self.rect.centery,
                                  getattr(STATE, "active_mission", "MISSION1"))
                prefix, count = footstep_prefix(mat)
                audio.play_random(prefix, count, volume=0.55)
                self._step_timer = 34.0 + _rng_legacy.randint(0, 8)
        else:
            self._step_timer = min(self._step_timer, 6.0)

    def rig_weapon_name(self):
        """Which gun silhouette to draw: "pistol" / "os12" / "k9_smg".

        A per-instance override wins when set, so a multiplayer process can
        draw a player holding the OS-12 the same frame it draws one holding
        the pistol. With no override this falls straight back to the mission
        global, exactly as every existing call site already assumed.
        """
        override = getattr(self, "rig_weapon", None)
        if override:
            return override
        return getattr(STATE, "current_weapon", "pistol")

    def barrel_tip(self):
        """World-space muzzle position - matches the gun drawing proportions."""
        a = self.angle

        current_weapon = self.rig_weapon_name()
        if current_weapon == "os12":
            arm_len = 16
            grip_offset = 4
            gun_len = 26
            muzzle_extra = 3
        elif current_weapon == "k9_smg":
            arm_len = 16
            grip_offset = 4
            gun_len = 18
            muzzle_extra = 5  # compact suppressor
        else:
            arm_len = 16
            grip_offset = 4
            gun_len = 17
            muzzle_extra = 2

        reach = arm_len + grip_offset + gun_len + muzzle_extra
        return (
            self.rect.centerx + math.cos(a) * reach,
            self.rect.centery + math.sin(a) * reach,
        )

    def draw(
        self,
        surface,
        offset_x,
        offset_y,
        walls=(),
        reload_active=False,
        reload_progress=0.0,
        melee_active=False,
        melee_progress=0.0,
        no_gun=False,
        is_moving=False,
        pen=None,
    ):
        global STATE
        pen = _pen_or_surface(pen, surface)  # RPE6 B-033: Pen sink (default = immediate, pixel-identical)
        # Cosmetic roles, resolved at set_appearance(). Every colour in this
        # method reads through these names instead of a literal, which is the
        # whole customization surface. The values for the default appearance
        # are the literals this method used to contain - see
        # core.appearance.BASE_ROLES and tools/avatar_parity.py.
        rk = self._rk
        # Mission-scoped story outfit (M5: the President's black). Opt-in per
        # instance - only the M5 draw sets story_outfit, so shop/arena
        # previews (fresh Player(0, 0)s) never pick it up. Layered on top of
        # the resolved roles and cached per (look, outfit); the saved
        # appearance in self.look/self._rk is never touched.
        outfit = self.story_outfit
        mark = None
        if outfit:
            ck = self._outfit_rk
            if ck is None or ck[0] != (self.look_key, outfit):
                ck = ((self.look_key, outfit), _outfits.overlay_roles(rk, outfit))
                self._outfit_rk = ck
            rk = ck[1]
            mark = _outfits.GAMEPLAY_MARK
        u = rk["uniform"]
        skin = rk["skin"]
        draw_x = self.rect.centerx - offset_x
        draw_y = self.rect.centery - offset_y

        if is_moving and not self.was_moving:
            self.walk_cycle = 0.0
        self.was_moving = is_moving

        self.breathing = 0.0 if _frozen() else math.sin(_now_s() * 0.5) * 1.0
        draw_y += self.breathing

        # ── Walk bob ──
        if is_moving:
            self.walk_cycle += 0.12
        else:
            self.walk_cycle *= 0.85
        sway_offset = 0.0

        # ── Recoil ──
        if self._recoil_timer > 0:
            self._recoil_timer -= 1
            self._recoil_offset = -3.0 * (self._recoil_timer / 8.0)
        else:
            self._recoil_offset *= 0.8

        if self._slide_timer > 0:
            self._slide_timer -= 1
        self.blink_timer += 1
        blinking = 2 if (120 < self.blink_timer < 140) else 0
        if self.blink_timer > 140:
            self.blink_timer = 0
        a = self.angle
        d_x = math.cos(a)
        d_y = math.sin(a)
        perp_x = math.cos(a + math.pi / 2)
        perp_y = math.sin(a + math.pi / 2)

        arm_angle = a
        if is_moving:
            # Weapon hand lags behind direction changes
            arm_angle += sway_offset * 0.06
        if reload_active:
            p = reload_progress
            _cw_reload = self.rig_weapon_name()
            _is_os12_reload = _cw_reload == "os12"
            _is_k9_reload = _cw_reload == "k9_smg"

            if _is_os12_reload:
                # OS 12 mag-swap reload
                # 0.00–0.30: rifle tilts, mag drops
                # 0.30–0.60: held empty
                # 0.60–1.00: new mag rocks in, rifle returns
                if p < 0.30:
                    t = p / 0.30
                    arm_factor = 1.0 - t * 0.25
                    arm_angle = a + t * 0.45
                elif p < 0.60:
                    t = (p - 0.30) / 0.30
                    arm_factor = 0.75
                    tremor = math.sin(p * math.pi * 8) * 0.03
                    arm_angle = a + 0.45 + tremor
                else:
                    t = (p - 0.60) / 0.40
                    ease = 1.0 - (1.0 - t) * (1.0 - t)
                    arm_factor = 0.75 + ease * 0.25
                    arm_angle = a + (0.45 * (1.0 - ease))
            elif _is_k9_reload:
                # K-9 suppressed SMG reload - compact PDW tilts inward,
                # stick mag strips out, palm-slap seats the fresh mag, then
                # the muzzle snaps back up. More mechanical than the pistol,
                # less heavy than the OS-12.
                if p < 0.22:
                    t = p / 0.22
                    arm_factor = 1.0 - t * 0.38
                    arm_angle = a + t * 0.62
                elif p < 0.58:
                    t = (p - 0.22) / 0.36
                    arm_factor = 0.62
                    arm_angle = a + 0.62 + math.sin(t * math.pi * 2) * 0.035
                elif p < 0.78:
                    t = (p - 0.58) / 0.20
                    arm_factor = 0.62 + t * 0.20
                    arm_angle = a + 0.62 - t * 0.22
                else:
                    t = (p - 0.78) / 0.22
                    ease = 1.0 - (1.0 - t) * (1.0 - t)
                    arm_factor = 0.82 + ease * 0.18
                    arm_angle = a + 0.40 * (1.0 - ease)
            else:
                # Pistol reload (unchanged)
                if p < 0.25:
                    arm_factor = 1.0 - (p / 0.25) * 0.5
                elif p < 0.75:
                    arm_factor = 0.5
                    wobble = math.sin(p * math.pi * 4) * 0.08
                    arm_angle = a + wobble
                else:
                    t = (p - 0.75) / 0.25
                    arm_factor = 0.5 + t * 0.5
                    wobble = math.sin(p * math.pi * 4) * 0.08 * (1.0 - t)
                    arm_angle = a + wobble
        elif melee_active:
            p = melee_progress
            current_weapon_for_melee = self.rig_weapon_name()
            if current_weapon_for_melee == "k9_smg":
                # K-9 melee: a compact buttstroke / muzzle shove. It should
                # feel different from the pistol slap and from improvised melee:
                # pull the gun across the body, snap forward, then settle.
                if p < 0.22:
                    t = p / 0.22
                    arm_factor = 0.88
                    arm_angle = a + 0.58 * t
                elif p < 0.58:
                    t = (p - 0.22) / 0.36
                    punch = 1.0 - (1.0 - t) * (1.0 - t)
                    arm_factor = 0.88 + punch * 0.55
                    arm_angle = a + 0.58 - punch * 0.92
                else:
                    t = (p - 0.58) / 0.42
                    arm_factor = 1.43 - t * 0.43
                    arm_angle = a - 0.34 * (1.0 - t)
            else:
                if p < 0.25:
                    t = p / 0.25
                    arm_factor = 1.0 - t * 0.6
                    arm_angle = a - t * math.pi / 4
                elif p < 0.75:
                    t = (p - 0.25) / 0.5
                    arm_factor = 0.4 + t * 0.8
                    arm_angle = a - math.pi / 4 + t * (math.pi / 4 + math.pi / 3)
                else:
                    t = (p - 0.75) / 0.25
                    arm_factor = 1.2 - t * 0.2
                    arm_angle = a + math.pi / 3 - t * math.pi / 3
        else:
            arm_factor = 1.0

        pen.blit(_player_shadow, (int(draw_x - 18), int(draw_y - 6)))
        # ── AEGIS i-frame blink (Pass E) ─────────────────────────────
        # Per references/game-design.md. While invincible_timer > 0, the
        # sprite blinks on/off at ~60ms windows. The shadow is ALWAYS drawn
        # so the player can still read their position; only the body blinks.
        # All per-frame state above (breathing, walk_cycle, recoil, blink)
        # has already advanced by this point, so timing stays correct.
        if not self.visible:
            return
        body_w, body_h = 22, 14
        cos_b, sin_b = math.cos(a), math.sin(a)
        torso_pts = []
        for bx, by in [
            (-body_w // 2, -body_h // 2),
            (body_w // 2, -body_h // 2),
            (body_w // 2, body_h // 2),
            (-body_w // 2, body_h // 2),
        ]:
            rx = bx * cos_b - by * sin_b
            ry = bx * sin_b + by * cos_b
            torso_pts.append((draw_x + rx, draw_y + ry))
        pen.polygon( u, torso_pts)
        cloth_edge = rk.get("cloth_edge")
        if cloth_edge:
            pen.polygon( cloth_edge, torso_pts, 1)
        if self.max_hp > 100:
            kevlar_w, kevlar_h = 16, 12
            kevlar_pts = []
            for bx, by in [
                (-kevlar_w // 2, -kevlar_h // 2),
                (kevlar_w // 2, -kevlar_h // 2),
                (kevlar_w // 2, kevlar_h // 2),
                (-kevlar_w // 2, kevlar_h // 2),
            ]:
                rx = bx * cos_b - by * sin_b
                ry = bx * sin_b + by * cos_b
                kevlar_pts.append((draw_x + rx, draw_y + ry))
            pen.polygon( rk["kevlar"], kevlar_pts)
            pen.polygon( rk["kevlar_edge"], kevlar_pts, 1)
            for off in (-5, 5):
                sx1 = draw_x + perp_x * off - d_x * 5
                sy1 = draw_y + perp_y * off - d_y * 5
                sx2 = draw_x + perp_x * off + d_x * 5
                sy2 = draw_y + perp_y * off + d_y * 5
                pen.line( rk["kevlar_line"], (sx1, sy1), (sx2, sy2), 2)
            ridge_w, ridge_h = 8, 8
            ridge_pts = []
            for bx, by in [
                (-ridge_w // 2, -ridge_h // 2),
                (ridge_w // 2, -ridge_h // 2),
                (ridge_w // 2, ridge_h // 2),
                (-ridge_w // 2, ridge_h // 2),
            ]:
                rx = bx * cos_b - by * sin_b
                ry = bx * sin_b + by * cos_b
                ridge_pts.append((draw_x + rx, draw_y + ry))
            pen.polygon( rk["kevlar_ridge"], ridge_pts)
        # The spine highlight and the two vest straps are arithmetic shades of
        # the uniform, not palette entries of their own. Left as arithmetic on
        # purpose: a palette retint propagates to them for free, and the
        # default palette produces the identical expression the sprite used to
        # compute from the config constant.
        pen.line(
            (u[0] + 12, u[1] + 12, u[2] + 8),
            (draw_x - d_x * 5, draw_y - d_y * 5),
            (draw_x + d_x * 5, draw_y + d_y * 5),
            2,
        )
        for off in (-6, 6):
            vx1 = draw_x + perp_x * off - d_x * 3
            vy1 = draw_y + perp_y * off - d_y * 3
            vx2 = draw_x + perp_x * off + d_x * 3
            vy2 = draw_y + perp_y * off + d_y * 3
            pen.line(
                (u[0] - 8, u[1] - 5, u[2] - 3),
                (vx1, vy1),
                (vx2, vy2),
                2,
            )


        test_arm_len = int(16 * arm_factor)
        test_arm_dx = math.cos(arm_angle)
        test_arm_dy = math.sin(arm_angle)
        test_grip_x = draw_x + test_arm_dx * (test_arm_len + 4)
        test_grip_y = draw_y + test_arm_dy * (test_arm_len + 4)

        test_gun_end_x = test_grip_x + test_arm_dx * 16
        test_gun_end_y = test_grip_y + test_arm_dy * 16

        min_t = float("inf")
        if not no_gun and walls:
            for wall in walls:
                wr = pygame.Rect(
                    wall.x - offset_x, wall.y - offset_y, TILE_SIZE, TILE_SIZE
                )
                clipped = wr.clipline(
                    (test_grip_x, test_grip_y), (test_gun_end_x, test_gun_end_y)
                )
                if clipped:
                    ex, ey = clipped[0]
                    t = (ex - test_grip_x) * test_arm_dx + (
                        ey - test_grip_y
                    ) * test_arm_dy
                    if t < min_t:
                        min_t = t

        raise_factor = 0.0
        if not no_gun and min_t < 16:
            raise_factor = max(0.0, min(1.0, (16.0 - min_t) / 16.0))

        # ── Weapon swap animation: lower the gun fully at midpoint, raise back up ──
        # An ARMED per-instance timer (multiplayer) wins and is advanced here,
        # because no per-mission update loop exists to tick it. With none
        # armed this reads the campaign's global timer, whose countdown stays
        # the mission update's job -- so the two never fight over the clock.
        inst_timer = getattr(self, "swap_timer", 0)
        if inst_timer > 0:
            swap_timer = inst_timer
            swap_duration = getattr(self, "swap_duration", 24)
            self.swap_timer = inst_timer - 1
        else:
            swap_timer = getattr(STATE, "weapon_swap_timer", 0)
            swap_duration = getattr(STATE, "weapon_swap_duration", 24)
        if swap_timer > 0 and swap_duration > 0:
            # Progress: 0.0 -> 1.0 across the full swap
            progress = 1.0 - (swap_timer / swap_duration)
            # Triangle wave: 0 at start, 1 at midpoint, 0 at end
            if progress < 0.5:
                swap_factor = progress * 2.0          # lowering (0 -> 1)
            else:
                swap_factor = (1.0 - progress) * 2.0  # raising (1 -> 0)
            # Use the larger of the two so wall-lower still wins if both apply
            raise_factor = max(raise_factor, swap_factor)

        self.weapon_raised = raise_factor > 0.15

        arm_angle = arm_angle - raise_factor * (math.pi * 0.35)
        arm_factor = arm_factor * (1.0 - raise_factor * 0.4)

        arm_len = int(16 * arm_factor)
        arm_dx = math.cos(arm_angle)
        arm_dy = math.sin(arm_angle)
        arm_perp_x = math.cos(arm_angle + math.pi / 2)
        arm_perp_y = math.sin(arm_angle + math.pi / 2)

        ls_x = draw_x + perp_x * 12
        ls_y = draw_y + perp_y * 12
        rs_x = draw_x - perp_x * 12
        rs_y = draw_y - perp_y * 12
        hand_x = draw_x + arm_dx * arm_len
        hand_y = draw_y + arm_dy * arm_len
        # Sleeve rim (story outfits only - the saved/shop looks carry no
        # cloth_edge role, so their sprite is byte-identical). A near-black
        # sleeve on a near-black M5 floor vanishes and the skin grip + gun read
        # as floating off the body (polish Task 4); the 1 px rim keeps the arm
        # visibly connecting shoulder -> hands without changing the geometry.
        if cloth_edge:
            pen.line( cloth_edge, (ls_x, ls_y),
                             (hand_x - arm_perp_x * 3, hand_y - arm_perp_y * 3), 7)
            pen.line( cloth_edge, (rs_x, rs_y),
                             (hand_x + arm_perp_x * 3, hand_y + arm_perp_y * 3), 7)
        pen.line(
            u,
            (ls_x, ls_y),
            (hand_x - arm_perp_x * 3, hand_y - arm_perp_y * 3),
            5,
        )
        pen.line(
            u,
            (rs_x, rs_y),
            (hand_x + arm_perp_x * 3, hand_y + arm_perp_y * 3),
            5,
        )
        if mark:
            # identity yoke: a thin KRAP-blue bar on BOTH shoulders, over the
            # sleeve roots, from just outside the head/curls to the shoulder
            # point (never far past the torso, where it read as a crossbar).
            # Guard troopers carry only a short red band on one sleeve.
            # Deliberately thin, no shoulder discs: fat blue blobs read as a
            # blue uniform at 32 px.
            for sgn in (1, -1):
                pen.line( mark,
                    (draw_x + sgn * perp_x * 9, draw_y + sgn * perp_y * 9),
                    (draw_x + sgn * perp_x * 13, draw_y + sgn * perp_y * 13), 3)
        grip_x = draw_x + arm_dx * (arm_len + 4)
        grip_y = draw_y + arm_dy * (arm_len + 4)
        pen.circle( skin, (int(grip_x), int(grip_y)), 4)

        if not no_gun:
            # Rig geometry lives in entities/weapon_rig.py so the Outfitter can
            # draw a gun finish with no body attached. The values passed here
            # are exactly what the inline blocks used to close over.
            _weapon_rig.draw(surface, self.rig_weapon_name(), {
                "grip_x": grip_x, "grip_y": grip_y,
                "arm_dx": arm_dx, "arm_dy": arm_dy,
                "raise_factor": raise_factor,
                "reload_active": reload_active,
                "reload_progress": reload_progress,
            }, self._rigs, pen=pen)

        # Head last, so the shell overlaps the barrel the way it always did.
        _adornments.draw_head(
            surface,
            _adornments.head_context(draw_x, draw_y, d_x, d_y, a, blinking),
            rk, _outfits.gameplay_head(outfit, self.look["head"]), pen=pen,
        )

        # Rig anchors of THIS frame, in surface space: one shared record the
        # debug overlay, the weapon-grid tool and the smoke check all read, so
        # "is the gun in his hands" is measured on the numbers the draw used.
        self.rig_anchors = {
            "body": (draw_x, draw_y),
            "shoulder_l": (ls_x, ls_y), "shoulder_r": (rs_x, rs_y),
            "hand_l": (hand_x - arm_perp_x * 3, hand_y - arm_perp_y * 3),
            "hand_r": (hand_x + arm_perp_x * 3, hand_y + arm_perp_y * 3),
            "grip": (grip_x, grip_y), "arm_dir": (arm_dx, arm_dy),
        }
        if self.debug_rig or _debug_rig_env():
            _draw_rig_debug(surface, self.rig_anchors, pen=pen)


# ─────────────────────────────────────────────────────────────
# Melee resolver - shared between both missions.
# ─────────────────────────────────────────────────────────────
# Mission 1 originally rolled its own melee block (range 48, ±60° cone
# required, wall-LOS check, damage 80, shake 8, 8 particles).
# Mission 2 had its own (range 55, no cone, no LOS, damage 75, no shake,
# 12 particles). The two had drifted on every axis. This function is the
# single source of truth.

MELEE_RANGE = 52          # split the difference: 48 (M1) vs 55 (M2)
MELEE_DAMAGE = 78         # split: 80 (M1) vs 75 (M2)
MELEE_CONE_HALF_ANGLE = math.pi / 3   # ±60° - must face the enemy
MELEE_PARTICLE_COUNT = 10  # split: 8 (M1) vs 12 (M2)
MELEE_SHAKE = 8            # M1 had this; M2 lacked it. Always shake on hit.
# AEGIS Pass F: hit-stop duration (seconds) on a melee KILL. Per the AEGIS
# spec, 50ms is the canonical "heavy strike" freeze; a kill deserves the full
# 50ms because the player just ended a threat and the freeze gives them a
# beat to register the kill before the simulation resumes. Non-kill melee
# hits do NOT trigger hit-stop - that would make every melee swing feel
# sluggish. Only the killing blow gets the weight.
MELEE_KILL_HIT_STOP = 0.05


def resolve_melee(player, enemies, solid_walls, blood_color):
    """Resolve a melee swing on the closest enemy in range, in cone, in LOS.

    Returns the hit enemy (so the caller can do per-mission cleanup like
    keycard drops) or None.

    Caller is responsible for:
      - decrementing ``STATE.melee_timer`` and clearing ``STATE.melee_active``
      - setting ``STATE.melee_hit_done = True`` after a hit (and resetting
        it to False when the swing ends)
      - any per-mission flags (e.g. ``is_commander`` keycard drop)

    The caller invokes this only when ``not STATE.melee_hit_done`` and the
    swing has reached its hit frame (timer <= 10).
    """
    if player is None:
        return None
    px, py = player.rect.centerx, player.rect.centery
    nearest = None
    nearest_dist = float("inf")
    for e in enemies:
        dx = e.rect.centerx - px
        dy = e.rect.centery - py
        dist = math.hypot(dx, dy)
        if dist >= MELEE_RANGE:
            continue
        # Must be facing the enemy (±60° cone around player.angle).
        angle_to_enemy = math.atan2(dy, dx)
        diff = abs(angle_to_enemy - player.angle)
        if diff > math.pi:
            diff = 2 * math.pi - diff
        if diff > MELEE_CONE_HALF_ANGLE:
            continue
        # No wall between player and enemy.
        hit_wall = False
        for wall in solid_walls:
            if wall.clipline((px, py), (e.rect.centerx, e.rect.centery)):
                hit_wall = True
                break
        if hit_wall:
            continue
        if dist < nearest_dist:
            nearest = e
            nearest_dist = dist
    if nearest is None:
        return None

    # Capture HP before the hit so we can detect a kill below.
    hp_before = nearest.hp
    nearest.hp -= getattr(STATE, "melee_damage", MELEE_DAMAGE)
    # on_hit signature in Enemy: alerts and turns to face the attacker.
    nearest.on_hit(px, py)

    # Shared particle burst + shake (deferred import to avoid circular).
    from fx import effects
    effects.burst(nearest.rect.centerx, nearest.rect.centery,
                  blood_color, MELEE_PARTICLE_COUNT)
    effects.shake(MELEE_SHAKE)
    # AEGIS Pass F: 50ms hit-stop ONLY on a melee kill (hp was >0 before,
    # <=0 after). Non-kill hits don't freeze - keeps the swing snappy.
    if hp_before > 0 and nearest.hp <= 0:
        effects.hit_stop(MELEE_KILL_HIT_STOP)

    return nearest
