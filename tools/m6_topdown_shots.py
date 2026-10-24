"""Top-down M6 review stills (customs / no-man's-land / rail yard).

    python tools/m6_topdown_shots.py [OUT_DIR] [stage ...] [--guards] [--mid] [--exit]

For every stage this writes two PNGs:

  <stage>_map.png    the whole baked map (ground + walls + props), 1 image px
                     per game px, so a wall seam or a prop silhouette can be
                     checked at a glance.
  <stage>_frame.png  one real gameplay frame through ``m6.game_draw`` with the
                     player standing at the stage spawn (lighting, snow, HUD).
  <stage>_guards.png (--guards) the same frame with three Guards posted in
                     front of the player - the hostile readability check.
  <stage>_mid.png    (--mid) the arena centre with three Guards, camera kept
                     inside the map - the frame a fight is actually played in,
                     with a bandage and an ammo pickup on the floor.
  <stage>_exit_locked.png / <stage>_exit_open.png  (--exit) the exit plate with
                     two Guards left, then with the arena cleared.

Visual-review tool, not a CI gate.
"""
import os
import sys

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
os.environ.setdefault("ACARISTAN_RENDERER", "software")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

import pygame  # noqa: E402

pygame.init()

# Floor tile (col, row) at the middle of each arena, for --mid frames.
_MID = {"customs": (15, 10), "noman": (20, 8), "rail": (22, 11)}


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("-")]
    guards = "--guards" in sys.argv
    mid = "--mid" in sys.argv
    exit_ = "--exit" in sys.argv
    out = args[0] if args else os.path.join(ROOT, "shots", "m6_topdown")
    os.makedirs(out, exist_ok=True)

    from core.state import STATE
    from core import config as _cfg
    from missions import m6
    from missions.m6 import decor as _decor
    from missions.m6 import maps as _maps
    from missions.m6 import meta as _meta

    _cfg.screen
    stages = [s for s in args[1:] if s in _meta.STAGES] or [
        _meta.STAGE_CUSTOMS, _meta.STAGE_NOMAN, _meta.STAGE_RAIL]

    for stage in stages:
        m6.start_m6()
        start = {
            _meta.STAGE_CUSTOMS: m6.start_mission6_customs_checkpoint,
            _meta.STAGE_NOMAN: m6.start_mission6_noman_checkpoint,
            _meta.STAGE_RAIL: m6.start_mission6_rail_checkpoint,
        }[stage]
        start()
        _maps.bind_stage(stage)
        STATE.mission6_stage = stage
        _decor.build_decor(stage)

        # Whole map, ground + every prop row, no camera.
        grid = _maps.grid_for(stage)
        w, h = len(grid[0]) * _decor.T, len(grid) * _decor.T
        whole = pygame.Surface((w, h))
        whole.fill((10, 12, 16))
        _decor.draw_ground(whole, 0, 0, stage)
        for row in _decor._prop_rows(stage):
            whole.blit(row["surf"], (row["x"], row["y"]))
        pygame.image.save(whole, os.path.join(out, "%s_map.png" % stage))

        # One gameplay frame from the stage spawn.
        spawn = _meta.STAGE_SPAWNS[stage]
        STATE.player.rect.center = (spawn[0] * _decor.T + _decor.T // 2,
                                    spawn[1] * _decor.T + _decor.T // 2)
        STATE.camera_x = max(0, STATE.player.rect.centerx - _cfg.WIDTH // 2)
        STATE.camera_y = max(0, STATE.player.rect.centery - _cfg.HEIGHT // 2)
        m6.game_draw(STATE.camera_x, STATE.camera_y)
        surf = pygame.display.get_surface()
        if surf is not None:
            pygame.image.save(surf, os.path.join(out, "%s_frame.png" % stage))

        if guards:
            from missions.m6 import world as _world
            from missions.m6 import combat as _combat
            STATE.enemies.clear()
            px, py = STATE.player.rect.center
            for i, (dx, dy, kind) in enumerate((
                    (-150, -140, "guard"), (-40, -190, "marksman"),
                    (120, -120, "raider"))):
                e = _world._spawn_guard(px + dx, py + dy, stage, aware=True)
                _combat.apply_role(e, kind)
            m6.game_draw(STATE.camera_x, STATE.camera_y)
            surf = pygame.display.get_surface()
            if surf is not None:
                pygame.image.save(surf, os.path.join(out, "%s_guards.png" % stage))
        if mid:
            # Arena centre, camera clamped inside the map, with the three
            # posted Guards: the frame a player actually fights in.
            from missions.m6 import world as _world
            from missions.m6 import combat as _combat
            c, r = _MID[stage]
            STATE.player.rect.center = (c * _decor.T + _decor.T // 2,
                                        r * _decor.T + _decor.T // 2)
            STATE.camera_x = max(0, min(STATE.player.rect.centerx - _cfg.WIDTH // 2,
                                        w - _cfg.WIDTH))
            STATE.camera_y = max(0, min(STATE.player.rect.centery - _cfg.HEIGHT // 2,
                                        h - _cfg.HEIGHT))
            STATE.enemies.clear()
            px, py = STATE.player.rect.center
            for dx, dy, kind in ((-150, -90, "guard"), (110, -140, "marksman"),
                                 (190, 60, "raider")):
                e = _world._spawn_guard(px + dx, py + dy, stage, aware=True)
                _combat.apply_role(e, kind)
            STATE.pickups = [(px - 70, py + 80, "bandage"), (px + 60, py + 90, "ammo")]
            m6.game_draw(STATE.camera_x, STATE.camera_y)
            STATE.pickups = []
            surf = pygame.display.get_surface()
            if surf is not None:
                pygame.image.save(surf, os.path.join(out, "%s_mid.png" % stage))
        if exit_:
            # The exit, locked (two Guards left) and then open (arena clear).
            from missions.m6 import world as _world
            from missions.m6 import combat as _combat
            from missions.m6 import flow as _flow
            ax, ay = _flow._anchor_pos(stage)
            STATE.player.rect.center = (int(ax), int(ay) + 70)
            STATE.camera_x = max(0, min(STATE.player.rect.centerx - _cfg.WIDTH // 2,
                                        w - _cfg.WIDTH))
            STATE.camera_y = max(0, min(STATE.player.rect.centery - _cfg.HEIGHT // 2,
                                        h - _cfg.HEIGHT))
            STATE.enemies.clear()
            for dx in (-170, 150):
                _combat.apply_role(_world._spawn_guard(
                    STATE.player.rect.centerx + dx, STATE.player.rect.centery + 40,
                    stage, aware=True), "guard")
            for tag in ("locked", "open"):
                m6.game_draw(STATE.camera_x, STATE.camera_y)
                surf = pygame.display.get_surface()
                if surf is not None:
                    pygame.image.save(surf, os.path.join(out, "%s_exit_%s.png" % (stage, tag)))
                STATE.enemies.clear()
                _combat.spend_waves()
        print("wrote", stage)


if __name__ == "__main__":
    main()
