
"""Shared camera and bullet helpers.

This module exists to stop mission.py and mission2.py from each rolling their
own per-frame camera, shake-update, bullet/wall collision, and bullet render
code. The two missions had drifted on every one of these axes:

  - Camera lerp factor (0.15 vs 0.14 / 0.38 / smoothstep)
  - Camera first-frame snap (M1 lerps from (0,0); M2 snaps)
  - Camera map-bounds clamp (M1 had none; M2 clamps)
  - Camera recoil kick (M1 dropped it; M2 applied it)
  - Bullet/wall collision (M1 point-sample AABB; M2 swept clipline)
  - Bullet render (M1 had glow halo; M2 did not)

All of those now live here. Both missions call ``update_camera`` once per
frame and ``draw_bullets`` once per render.
"""
import math
from engine.core import LEGACY_RNG as _rng_legacy  # RPE6 R6: named 'legacy' rng stream
import engine.render2d as _cam2d  # RPE6 P6-M4: follow/clamp/shake math is engine-owned (public facade)

import pygame

from core.config import WIDTH, HEIGHT, TILE_SIZE, C_BULLET, bullet_glow
from core.state import STATE
from core.user_settings import SETTINGS  # RPE6 P9: live accessibility values


# ── Camera tuning constants ─────────────────────────────────────────────
# One place to tune the whole game's camera feel. Mission code must use
# these instead of inline lerp literals so the feel can't drift again.
CAM_EASE_GAMEPLAY = 0.15   # default follow ease (M1, M3)
CAM_EASE_M2 = 0.14         # M2 gameplay - deliberately weightier than M1
CAM_EASE_FOCUS = 0.38      # cutscene focus pulls (snappy)
CAM_EASE_WALK = 0.15       # walking-sim follow (was 0.10 - felt sluggish)
CAM_EASE_M3_BREACH_TRACK = 0.22  # M3 Volkov-breach tight track
CAM_DEADZONE_PX = 16.0     # follow deadzone half-size (gameplay follow only -
                           # focus pulls and sniper anchors need exact arrival)
CAM_LOOKAHEAD_PX = 48.0    # aim-direction lookahead for shooter missions
CAM_LOOKAHEAD_WALK_PX = 40.0  # movement-direction lookahead for the walk sim
CAM_SHAKE_DECAY = 1        # shake amplitude decay per frame
CAM_KICK_DECAY = 0.82      # recoil kick exponential decay per frame


def _decay_shake_kick():
    """Advance screen shake + recoil kick one frame.

    Returns (sx, sy, kx, ky) - the render offsets for this frame, already
    reduced-motion gated. Stored kick always decays so it can't pile up.
    """
    if getattr(STATE, "reduced_motion", False):
        STATE.screen_shake = 0
        sx = sy = 0
        kx = ky = 0.0
    else:
        if STATE.screen_shake > 0:
            # RPE6 P9: accessibility shake scale (SETTINGS, live; 1.0 = legacy).
            # Magnitude stays an int: it bounds randint draws (identity at 1.0).
            _shake = int(round(STATE.screen_shake * float(getattr(SETTINGS, "shake_scale", 1.0))))
            sx, sy = _cam2d.legacy_shake(_shake, _rng_legacy)   # RPE6 P6-M4: engine math
            STATE.screen_shake = max(0, STATE.screen_shake - CAM_SHAKE_DECAY)
        else:
            sx = sy = 0
        kx, ky = STATE.cam_kick_x, STATE.cam_kick_y
    STATE.cam_kick_x *= CAM_KICK_DECAY
    STATE.cam_kick_y *= CAM_KICK_DECAY
    return sx, sy, kx, ky


def _clamp_to_map(x, y, map_w, map_h):
    """Clamp a camera top-left into [0, map_px - screen]. No-op without bounds."""
    if map_w is not None and map_h is not None:
        x, y = _cam2d.clamp_top_left(x, y, map_w * TILE_SIZE, map_h * TILE_SIZE, WIDTH, HEIGHT)  # RPE6 P6-M4
    return x, y


def update_camera(target, map_w=None, map_h=None, focus_factor=None,
                  handheld_jitter_timer=None, factor_fn=None,
                  deadzone_px=0.0, lookahead=None, apply_final_clamp=True):
    """Per-frame camera update with shake, recoil kick, lerp, and clamp.

    Args:
        target: (x, y) world position the camera should follow (usually the
            player's rect center, possibly adjusted for cutscene focus).
        map_w, map_h: Optional map dimensions in tiles. If provided, the
            *desired* camera position is clamped to ``[0, map_w*TILE_SIZE - WIDTH]``
            and the same for y BEFORE the lerp. Pass these to prevent the camera
            from running past the map edge into black void.
        focus_factor: Optional constant lerp override (0..1) for cutscene
            focus pulls. None means use the default ease (CAM_EASE_GAMEPLAY).
        factor_fn: Optional callable ``(dx, dy, dist) -> float`` that computes
            a per-frame lerp factor from the offset to the target. Used by M2's
            sniper stage for distance-scaled smoothstep easing. Overrides
            ``focus_factor`` if provided.
        handheld_jitter_timer: Optional int. When non-None and non-zero, adds
            a subtle handheld sway using sin/cos of this timer - used by M2's
            sniper stage for tension. Pass None for steady cam.
        deadzone_px: Optional follow deadzone half-size in px. While the
            desired position stays within this range of the current camera,
            the camera holds still (kills micro-jitter from the lerp tail).
            Gameplay follow only - leave 0 for focus pulls / sniper anchors,
            which need exact arrival on composed shots.
        lookahead: Optional (x, y) world offset added to the desired position
            before clamping - e.g. aim-direction * CAM_LOOKAHEAD_PX so the
            player sees more of what they're aiming at. Gameplay follow only.
        apply_final_clamp: When True (default) the returned render position is
            clamped to the map, so shake/kick cannot expose void at an edge.
            Set False when the caller does its own clamp and needs the raw
            shake/kick delta intact. This matters for maps SMALLER than the
            viewport (the multiplayer arena's Crossfire): the map bound there
            is 0, so this final clamp flattens every shake to nothing.

    Returns:
        (fcx, fcy) - the final render camera position with shake and kick
        applied DIRECTLY (not smoothed by the follow lerp).

    Design note on shake / kick:
        Earlier versions baked ``sx``, ``sy``, ``cam_kick_x``, ``cam_kick_y``
        into ``desired_x`` / ``desired_y`` and then lerped ``STATE.camera_x``
        toward desired at 0.15/frame. That smoothed the shake and kick into
        a barely-visible drift: a ``shake(13)`` pistol shot produced only
        ~2 pixels of visible jitter per frame. The fix is to compute the
        player-follow position via lerp (so the camera still tracks the
        player smoothly) and then add shake + kick DIRECTLY to the returned
        render position. This restores the snappy, "punchy" feel of M1's
        pre-refactor shake.

    Side effects:
        Mutates STATE.camera_x, STATE.camera_y (player-follow position only),
        STATE.screen_shake (decays toward 0), STATE.cam_kick_x/y (decays
        toward 0).
    """
    tx, ty = target

    # ── Screen shake + recoil kick decay (max-clamp semantics upstream) ──
    # Computed per frame as fresh offsets, applied directly to the returned
    # render position below (never smoothed by the follow lerp).
    sx, sy, kick_x, kick_y = _decay_shake_kick()

    # ── Desired position is the PLAYER-FOLLOW target plus lookahead ──
    # Shake and kick are NOT baked in here - that was the bug that made
    # recoil feel mushy. They're applied directly to the render return.
    look_x, look_y = lookahead if lookahead else (0.0, 0.0)
    desired_x = tx - WIDTH // 2 + look_x
    desired_y = ty - HEIGHT // 2 + look_y

    # ── Map-bounds clamp on the *desired* position (M2's approach) ──
    desired_x, desired_y = _clamp_to_map(desired_x, desired_y, map_w, map_h)

    # ── First-frame snap: avoids the camera swooping in from (0,0) ──
    if not getattr(STATE, "camera_initialized", False):
        STATE.camera_x = desired_x
        STATE.camera_y = desired_y
        STATE.camera_initialized = True
    else:
        # ── Follow deadzone: hold still inside the deadzone (engine math, RPE6 P6-M4) ──
        desired_x, desired_y = _cam2d.deadzone_hold(STATE.camera_x, STATE.camera_y, desired_x, desired_y,
                                                    deadzone_px)
        # ── Lerp toward desired position (player follow only) ──
        dx = desired_x - STATE.camera_x
        dy = desired_y - STATE.camera_y
        if factor_fn is not None:
            dist = math.hypot(dx, dy)
            if dist < 1.0:
                STATE.camera_x = desired_x
                STATE.camera_y = desired_y
            else:
                factor = factor_fn(dx, dy, dist)
                STATE.camera_x += dx * factor
                STATE.camera_y += dy * factor
        else:
            ease = CAM_EASE_GAMEPLAY if focus_factor is None else focus_factor
            STATE.camera_x += dx * ease
            STATE.camera_y += dy * ease

    # ── Apply shake + kick DIRECTLY to the render return ──
    # This is the key fix: by adding them after the lerp, we avoid the
    # smoothing that was making recoil feel mushy. The render position can
    # jitter by the full shake amplitude each frame, and the kick punches
    # the camera in the opposite direction of the shot immediately.
    render_x = STATE.camera_x + kick_x + sx
    render_y = STATE.camera_y + kick_y + sy

    # ── Handheld jitter (optional, for high-tension stages) ──
    if handheld_jitter_timer is not None and handheld_jitter_timer > 0:
        if not getattr(STATE, "reduced_motion", False):
            render_x += math.sin(handheld_jitter_timer * 0.13) * 0.8
            render_y += math.cos(handheld_jitter_timer * 0.17) * 0.6

    # ── Clamp the render position too ──
    # Shake/kick/jitter are applied after the desired-clamp, so near map
    # edges they could expose map void. Clamping the final position keeps
    # the frame inside the map (shake gets clipped asymmetrically at the
    # very edge - standard and far less visible than void). Callers that do
    # their own clamp (and must keep the shake delta, e.g. the arena on a
    # sub-viewport map) pass apply_final_clamp=False.
    if apply_final_clamp:
        render_x, render_y = _clamp_to_map(render_x, render_y, map_w, map_h)

    return render_x, render_y


# Per-caller tally of follow_gameplay / follow_step calls. Read by the smoke
# test to prove every mission's gameplay camera goes through the shared
# helper (polish pass T3). Cheap: one dict increment per frame.
FOLLOW_CALLS = {}


def _count(who):
    FOLLOW_CALLS[who] = FOLLOW_CALLS.get(who, 0) + 1


def aim_lookahead(aim_angle, lookahead_px=CAM_LOOKAHEAD_PX):
    """World-space lookahead offset along the aim direction (None -> None)."""
    if aim_angle is None or not lookahead_px:
        return None
    return (math.cos(aim_angle) * lookahead_px, math.sin(aim_angle) * lookahead_px)


def follow_step(cur_x, cur_y, desired_x, desired_y, *, ease=CAM_EASE_GAMEPLAY,
                deadzone_px=CAM_DEADZONE_PX, who="follow_step"):
    """One frame of deadzone + ease toward a desired top-left. Pure math for
    cameras that keep their own position (the walking sim's walk_camera_x);
    update_camera() applies the identical rule to STATE.camera_x/y."""
    _count(who)
    desired_x, desired_y = _cam2d.deadzone_hold(cur_x, cur_y, desired_x, desired_y, deadzone_px)  # RPE6 P6-M4
    return _cam2d.ease_toward(cur_x, cur_y, desired_x, desired_y, ease)


def follow_gameplay(target, map_w=None, map_h=None, *, aim_angle=None,
                    ease=CAM_EASE_GAMEPLAY, lookahead_px=CAM_LOOKAHEAD_PX,
                    deadzone_px=CAM_DEADZONE_PX, lookahead=None, who="gameplay",
                    **overrides):
    """THE gameplay follow camera (M1, M3, M4, M5; M2 and the arena via
    overrides). Same lag, deadzone and aim lookahead everywhere:

    - ``aim_angle`` (radians) -> lookahead of ``lookahead_px`` along the aim;
      pass ``lookahead=(x, y)`` instead for a custom offset, or
      ``aim_angle=None`` for none (dead player, cinematic holds).
    - ``ease`` / ``deadzone_px`` default to the shared gameplay constants.
    - ``**overrides`` go straight to update_camera (``factor_fn``,
      ``handheld_jitter_timer``, ``apply_final_clamp``) - special cases are
      explicit overrides, never forked follow code.

    The first call after reset_camera_state() snaps (lookahead included), so
    stage swaps don't lurch. Returns update_camera's render position.
    """
    _count(who)
    if lookahead is None:
        lookahead = aim_lookahead(aim_angle, lookahead_px)
    return update_camera(target, map_w=map_w, map_h=map_h, focus_factor=ease,
                         deadzone_px=deadzone_px, lookahead=lookahead, **overrides)


def snap_gameplay(target, map_w=None, map_h=None, *, aim_angle=None, who="snap", **kw):
    """Hard-snap the follow camera onto ``target`` (world swap / checkpoint).
    Equivalent to reset_camera_state() + one follow_gameplay() frame."""
    reset_camera_state()
    return follow_gameplay(target, map_w, map_h, aim_angle=aim_angle, who=who, **kw)


def tick_camera_fx(map_w=None, map_h=None):
    """Decay shake/kick and return the render camera WITHOUT moving follow.

    For frozen-frame paths (cinematics, fullscreen OS, note-read) that skip
    the follow lerp. Without this, shake triggered on those paths sits
    un-decayed and fires late when control resumes; with it, shake plays
    (or decays) on time and the returned position stays shake-accurate.
    """
    sx, sy, kick_x, kick_y = _decay_shake_kick()
    render_x = STATE.camera_x + kick_x + sx
    render_y = STATE.camera_y + kick_y + sy
    return _clamp_to_map(render_x, render_y, map_w, map_h)


def reset_camera_state():
    """Clear the camera_initialized flag so the next update_camera snaps."""
    STATE.camera_initialized = False
    STATE.cam_kick_x = 0.0
    STATE.cam_kick_y = 0.0


def collide_bullet_walls(b, solid_walls):
    """Swept bullet-vs-wall collision.

    Uses ``wall.clipline(prev_pos, cur_pos)`` so that fast bullets (24 px/frame
    and up) cannot tunnel through thin walls. Returns True if the bullet hit
    a wall; the caller is responsible for spawning impact particles / sounds.

    Important: a bullet that SPAWNS inside a wall (e.g. an enemy whose gun
    position is inside a cover rect) and moves outward is NOT counted as a
    wall hit. Only bullets that cross from outside a wall into it register.
    Without this exception, enemies standing behind cover fire bullets that
    are absorbed instantly and never reach the player.
    """
    for wall in solid_walls:
        if wall.clipline((b["prev_x"], b["prev_y"]), (b["x"], b["y"])):
            # Skip if the bullet was already inside this wall on the previous
            # frame - it spawned there (enemy gun pos inside cover) and is
            # moving outward, not entering the wall from outside.
            if not wall.collidepoint(b["prev_x"], b["prev_y"]):
                return True
    return False


def draw_bullets(surface, bullets, cam_x, cam_y, with_glow=True):
    """Render bullets with optional glow halo, motion trail, and sharp core.

    The glow halo is the soft yellow 16x16 surface from config.bullet_glow.
    Both missions now render it; previously M2 skipped it, making M2 bullets
    look like crisp dots while M1's looked like glowing tracers.
    """
    for b in bullets:
        bx = int(b["x"] - cam_x)
        by = int(b["y"] - cam_y)
        if with_glow:
            surface.blit(bullet_glow, (bx - 8, by - 8))
        pygame.draw.circle(surface, C_BULLET, (bx, by), 2)
        prev_x = b.get("prev_x", b["x"] - b["dx"]) - cam_x
        prev_y = b.get("prev_y", b["y"] - b["dy"]) - cam_y
        pygame.draw.line(
            surface, (255, 220, 140),
            (bx, by), (prev_x, prev_y), 2,
        )
