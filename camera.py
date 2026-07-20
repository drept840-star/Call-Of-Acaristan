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
import random
import pygame

from config import WIDTH, HEIGHT, TILE_SIZE, C_BULLET, bullet_glow
from state import STATE


def update_camera(target, map_w=None, map_h=None, focus_factor=None,
                  handheld_jitter_timer=None, factor_fn=None):
    """Per-frame camera update with shake, recoil kick, lerp, and clamp.

    Args:
        target: (x, y) world position the camera should follow (usually the
            player's rect center, possibly adjusted for cutscene focus).
        map_w, map_h: Optional map dimensions in tiles. If provided, the
            *desired* camera position is clamped to ``[0, map_w*TILE_SIZE - WIDTH]``
            and the same for y BEFORE the lerp. Pass these to prevent the camera
            from running past the map edge into black void.
        focus_factor: Optional constant lerp override (0..1) for cutscene
            focus pulls. None means use the default ease (0.15).
        factor_fn: Optional callable ``(dx, dy, dist) -> float`` that computes
            a per-frame lerp factor from the offset to the target. Used by M2's
            sniper stage for distance-scaled smoothstep easing. Overrides
            ``focus_factor`` if provided.
        handheld_jitter_timer: Optional int. When non-None and non-zero, adds
            a subtle handheld sway using sin/cos of this timer — used by M2's
            sniper stage for tension. Pass None for steady cam.

    Returns:
        (fcx, fcy) — the final render camera position with shake and kick
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

    # ── Screen shake update (max-clamp semantics, never direct assignment) ──
    # Computed per frame as a fresh random offset, then applied directly to
    # the returned render position below.
    sx = sy = 0
    if getattr(STATE, "reduced_motion", False):
        STATE.screen_shake = 0
    elif STATE.screen_shake > 0:
        sx = random.randint(-STATE.screen_shake, STATE.screen_shake)
        sy = random.randint(-STATE.screen_shake, STATE.screen_shake)
        STATE.screen_shake = max(0, STATE.screen_shake - 1)

    # ── Recoil kick decay (set by weapons.handle_shoot on every shot) ──
    # The kick value itself decays exponentially; the current value is added
    # directly to the returned render position below.
    STATE.cam_kick_x *= 0.82
    STATE.cam_kick_y *= 0.82

    # ── Desired position is the PLAYER-FOLLOW target only ──
    # Shake and kick are NOT baked in here — that was the bug that made
    # recoil feel mushy. They're applied directly to the render return.
    desired_x = tx - WIDTH // 2
    desired_y = ty - HEIGHT // 2

    # ── Map-bounds clamp on the *desired* position (M2's approach) ──
    if map_w is not None and map_h is not None:
        max_x = max(0, map_w * TILE_SIZE - WIDTH)
        max_y = max(0, map_h * TILE_SIZE - HEIGHT)
        desired_x = max(0, min(max_x, desired_x))
        desired_y = max(0, min(max_y, desired_y))

    # ── First-frame snap: avoids the camera swooping in from (0,0) ──
    if not getattr(STATE, "camera_initialized", False):
        STATE.camera_x = desired_x
        STATE.camera_y = desired_y
        STATE.camera_initialized = True
    else:
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
            ease = 0.15 if focus_factor is None else focus_factor
            STATE.camera_x += dx * ease
            STATE.camera_y += dy * ease

    # ── Apply shake + kick DIRECTLY to the render return ──
    # This is the key fix: by adding them after the lerp, we avoid the
    # smoothing that was making recoil feel mushy. The render position can
    # jitter by the full shake amplitude each frame, and the kick punches
    # the camera in the opposite direction of the shot immediately.
    render_x = STATE.camera_x + STATE.cam_kick_x + sx
    render_y = STATE.camera_y + STATE.cam_kick_y + sy

    # ── Handheld jitter (optional, for high-tension stages) ──
    if handheld_jitter_timer is not None and handheld_jitter_timer > 0:
        if not getattr(STATE, "reduced_motion", False):
            render_x += math.sin(handheld_jitter_timer * 0.13) * 0.8
            render_y += math.cos(handheld_jitter_timer * 0.17) * 0.6

    return render_x, render_y


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
            # frame — it spawned there (enemy gun pos inside cover) and is
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
