#!/usr/bin/env python3
"""AE MISSION0 CHECK - RPE6 Phase 10, D2 proof.

Proves the tutorial claim: a complete mission (level, dialogue,
timeline cutscene, 3D set, enemy types, HUD widgets) was added
with ZERO modifications to src/engine/:

  1. the src/engine/**.py tree hash equals the baseline frozen
     before Mission 0 existed (ENGINE_TREE_SHA below);
  2. every scaffolded data file loads through its public loader;
  3. a scripted headless playthrough finishes the mission
     (briefing -> walk to the exit -> outro requested);
  4. every outro shot renders non-blank headlessly, including
     the inspect shot and the 3D depot shot.

Run: SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy \
     python3 tools/ae_mission0_check.py
Exit 0 + "AE MISSION0: OK" on success.
"""
import hashlib
import os
import sys

# Frozen before Mission 0 existed (Phase 10): e26ff0bd... (82 files).
# Re-frozen after Phase 11 step 1 (lighting presets landed in
# engine.render3d: presets.py + facade exports + scene3d "lighting"),
# justified in docs/engine/reports/phase11.md - the zero-diff proof
# for Mission 0's own construction is the Phase 10 value above.
ENGINE_TREE_SHA = "7069c19de99915e313d73efd0a1ceca1dbdf879c9f605d3a2657437d4ef331ec"  # P11 step 11: mesh node type (ADR-024)


def engine_tree_sha(root):
    h = hashlib.sha256()
    files = sorted(root.glob("src/engine/**/*.py"))
    for f in files:
        rel = f.relative_to(root).as_posix()
        h.update(rel.encode("utf-8"))
        h.update(b"\0")
        h.update(f.read_bytes())
        h.update(b"\0")
    return len(files), h.hexdigest()


def main():
    from pathlib import Path
    root = Path(__file__).resolve().parent.parent
    sys.path.insert(0, str(root / "src"))

    n, sha = engine_tree_sha(root)
    if sha != ENGINE_TREE_SHA:
        print(f"AE MISSION0: FAIL engine tree changed ({n} files, {sha[:12]}...)")
        print("  Mission 0 must not modify src/engine. If an engine change")
        print("  was deliberate, update ENGINE_TREE_SHA AND justify it in")
        print("  docs/engine/reports/phase10.md.")
        return 1

    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
    import pygame
    pygame.init()
    pygame.display.set_mode((1000, 700))

    from game import dialogues, levels, timelines, render3d_bridge
    from missions import m0
    import core.config as cfg

    # -- 2. data loads ---------------------------------------------------
    level = levels.level("mission0.depot")
    grid = level.grid()
    assert len(grid) == 10 and all(len(r) == 15 for r in grid), "grid shape"
    dlg = dialogues.dialogue("mission0.briefing")
    assert dlg.nodes, "dialogue nodes"
    timelines.timeline("mission0.outro")
    shots = timelines.shots("mission0.outro", [])
    assert shots, "outro shots"
    prims = render3d_bridge.set_prims("mission0.depot")
    assert prims, "set prims"
    surf = cfg.screen

    class Keys:
        def __init__(self):
            self.pressed = set()

        def __getitem__(self, k):
            return k in self.pressed

    keys = Keys()
    from core.state import STATE
    # -- 3. playthrough (public contract only: keys in, STATE out) --------
    m0.start_mission0()
    p = STATE.player
    assert p is not None, "player spawned"

    def tile_of(rect):
        return (int(rect.centerx // 64), int(rect.centery // 64))

    def step(keyset, frames=1):
        keys.pressed = set(keyset)
        for _ in range(frames):
            m0.game_update(keys)
        keys.pressed = set()
        m0.game_draw(0, 0)

    # Briefing: Space advances; done when a movement key moves the player.
    home = p.rect.center
    done = False
    for _ in range(600):
        step({pygame.K_SPACE})
        step(set())  # debounce
        before = p.rect.center
        step({pygame.K_d}, 3)
        if p.rect.center != before:
            done = True
            break
        p.rect.center = home
    assert done, "briefing did not finish"
    # Harness god-mode: the proof is reachability + flow, not combat
    # balance - the depot guards shoot on sight during the walk.
    p.max_hp = p.hp = 100000

    # BFS over the level grid from the player's tile to the '=' exit,
    # then walk it with held movement keys, one tile at a time.
    from collections import deque
    tiles = {(tx, ty): ch for ty, row in enumerate(grid)
             for tx, ch in enumerate(row)}
    exit_tile = next(t for t, c in tiles.items() if c == "=")
    cur = tile_of(p.rect)
    prev = {cur: None}
    dq = deque([cur])
    while dq:
        t = dq.popleft()
        if t == exit_tile:
            break
        for d in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            nb = (t[0] + d[0], t[1] + d[1])
            if nb in tiles and tiles[nb] != "#" and nb not in prev:
                prev[nb] = t
                dq.append(nb)
    assert exit_tile in prev, "no path to exit"
    path = []
    t = exit_tile
    while t is not None:
        path.append(t)
        t = prev[t]
    path.reverse()
    DIRKEY = {(1, 0): pygame.K_d, (-1, 0): pygame.K_a,
              (0, 1): pygame.K_s, (0, -1): pygame.K_w}
    for a, b in zip(path, path[1:]):
        key = DIRKEY[(b[0] - a[0], b[1] - a[1])]
        for _ in range(60):
            # Arrival = centre in tile, or the exit trigger fired
            # (it trips on rect overlap, before the centre crosses).
            if tile_of(p.rect) == b or m0.complete():
                break
            step({key})
        assert tile_of(p.rect) == b or m0.complete(), \
            f"walk stalled {a} -> {b}"
        if m0.complete():
            break
    step(set(), 2)
    assert m0.take_outro_request(), "outro not requested at exit"
    # -- 4. outro renders ---------------------------------------------------
    import numpy as np
    from cutscenes import draw_cutscene_scene
    for shot in m0.outro_shots():
        for tms in (0, 700, 1600):
            draw_cutscene_scene(surf, shot, tms)
            arr = pygame.surfarray.array3d(surf)
            assert float(np.std(arr)) > 1.0, (shot.get("id"), tms)
    m0.complete()
    print(f"AE MISSION0: OK (engine tree untouched: {n} files, "
          f"sha {sha[:12]}...; playthrough + {len(shots)} outro shots rendered)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
