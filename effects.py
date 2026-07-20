# ------------------------------------------------------------
# effects.py
# ------------------------------------------------------------

"""Visual effects: particles, casings, breach markers, blood decals."""
import math
import random
import pygame

from config import (
    TILE_SIZE, WIDTH, HEIGHT, LETTER_H,
    SCENE_TOP, SCENE_BOT, C_BLOOD, Particle, Casing, audio,
)
from state import STATE


_wall_shadow = pygame.Surface((TILE_SIZE + 8, TILE_SIZE + 8), pygame.SRCALPHA)
pygame.draw.rect(_wall_shadow, (0, 0, 0, 50), (4, 4, TILE_SIZE + 4, TILE_SIZE + 4))

_bullet_glow = pygame.Surface((16, 16), pygame.SRCALPHA)
pygame.draw.circle(_bullet_glow, (255, 200, 100, 60), (8, 8), 8)

_bay_door_shadow = pygame.Surface(
    (TILE_SIZE * 3 + 8, TILE_SIZE + 8), pygame.SRCALPHA
)
pygame.draw.rect(
    _bay_door_shadow, (0, 0, 0, 50),
    (4, 4, TILE_SIZE * 3 + 4, TILE_SIZE + 4),
)


def add_blood(x, y, life=120, size_range=(8, 16)):
    STATE.blood_decals.append([x, y, life, random.randint(*size_range)])


def spawn_particles(x, y, color, count=8):
    # Graphics → Particle Density scales every spawn site uniformly.
    # Density 0 still emits at least 1 particle so VFX never fully disappears.
    try:
        from user_settings import SETTINGS
        density = SETTINGS.particle_density
    except Exception:
        density = 1.0
    actual = max(1, int(round(count * density)))
    for _ in range(actual):
        STATE.particles.append(Particle(x, y, color))


def update_particles():
    for p in STATE.particles[:]:
        p.update()
        if p.life <= 0:
            STATE.particles.remove(p)


def update_casings(solid_walls):
    for c in STATE.casings[:]:
        c.update(solid_walls)
        if c.life <= 0:
            STATE.casings.remove(c)


def update_floating_texts():
    for ft in STATE.floating_texts[:]:
        if len(ft) < 6 or ft[5] != "pin":
            ft[1] -= 1.0
        ft[4] -= 1
        if ft[4] <= 0:
            STATE.floating_texts.remove(ft)


def update_breach_markers():
    for marker in STATE.breach_markers[:]:
        marker[2] -= 1
        if marker[2] <= 0:
            STATE.breach_markers.remove(marker)


def shake(amount):
    """Max-clamp screen shake trigger.

    Always use this — never write ``STATE.screen_shake = N`` directly. Direct
    assignment cancels any in-flight larger shake (e.g. a player hit at amp 6
    mid-breach would stomp the breach bang at amp 28). This helper preserves
    the larger value so smaller triggers never cause a visible stutter.
    """
    if amount > STATE.screen_shake:
        STATE.screen_shake = amount


def hit_stop(seconds):
    """Trigger a hit-stop freeze (AEGIS Pass F).

    Per references/game-design.md "Hit-Stop": on heavy strikes, pause the
    simulation for ~50 ms so the impact lands with weight. The freeze is
    gated in acaristan.py's main loop — when ``STATE.hit_stop_timer > 0``,
    ``gc.game_update(keys)`` is skipped, but rendering still runs (so the
    player sees the moment of impact frozen on screen).

    Always use this helper — never write ``STATE.hit_stop_timer = N``
    directly. The helper max-clamps so a smaller hit-stop cannot truncate
    a larger in-flight one (e.g. a 50 ms melee kill hit-stop should not
    be cut short by a follow-up 40 ms bullet impact). Use the same
    max-clamp discipline as ``shake()``.

    ``seconds`` is the freeze duration in seconds. Per AEGIS spec, ~0.05s
    (50 ms / 3 frames at 60 FPS) is the canonical value for heavy strikes;
    use ~0.08s for set-piece kills (sniper, blast). Callers should pass
    concrete values from settings/constants, not magic numbers.
    """
    if seconds > STATE.hit_stop_timer:
        STATE.hit_stop_timer = seconds


def burst(x, y, color, count=20, speed_mul=1.0, life_min=18, life_max=50, jitter=8):
    """Unified particle burst.

    Both missions previously had their own spawn loops: mission.py used raw
    ``Particle(x, y, color)`` (life 15-35, no jitter, no speed scaling) while
    mission2.py used a local ``_burst()`` helper (life 18-50, +/-8 px jitter,
    speed_mul). This function unifies the two on the M2 parameters (which
    produce the richer-looking burst). The user's ``SETTINGS.particle_density``
    setting is respected via the same scaling as ``spawn_particles``.
    """
    try:
        from user_settings import SETTINGS
        density = SETTINGS.particle_density
    except Exception:
        density = 1.0
    actual = max(1, int(round(count * density)))
    for _ in range(actual):
        jx = random.randint(-jitter, jitter) if jitter else 0
        jy = random.randint(-jitter, jitter) if jitter else 0
        p = Particle(x + jx, y + jy, color)
        p.dx *= speed_mul
        p.dy *= speed_mul
        p.life = random.randint(life_min, life_max)
        STATE.particles.append(p)


def flash(frames=15):
    STATE.gc_flash_timer = frames


def play_impact(name, source_pos, base_volume=0.4, listener=None):
    """Spatial audio for combat impacts.

    Both missions *should* use 3D positional audio for bullet impacts so the
    player can hear *where* the hit landed. mission.py did this; mission2.py
    regressed to flat ``audio.play()``. This helper restores the 3D path
    while gracefully degrading to flat playback when no listener is available
    (e.g. player is dead).
    """
    if listener is None:
        if STATE.player and not getattr(STATE, "player_dead", False):
            listener = (STATE.player.rect.centerx, STATE.player.rect.centery)
        else:
            audio.play(name, volume=base_volume)
            return
    audio.play_3d(name, source_pos, listener, base_volume=base_volume)


# ------------------------------------------------------------
