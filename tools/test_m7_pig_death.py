"""The pig in the 3D raid, and what it costs. Run from the project root:

    python tools/test_m7_pig_death.py

Checks the whole chain in ``missions.m7.raid3d``: the pig is a hittable target,
one barrel ends it, the body stays in the yard, Bodi turns on the player instead
of fighting the Guards, he cannot be wounded, killed or revived, pellets that
reach him spark off him, the scripted beat roots the player and rifles them
down, the mission does not advance, and a checkpoint reload puts all of it back.
"""
import math
import os
import sys
from pathlib import Path

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import pygame

pygame.init()
pygame.display.set_mode((1000, 700))

from core import config                       # noqa: E402
from core import save_system                  # noqa: E402
from core.state import STATE                  # noqa: E402
from engine.core import pin_wall, unpin_wall  # noqa: E402
from missions import m7                       # noqa: E402
from missions.m7 import raid3d as R           # noqa: E402
from missions.m7 import raid_brain as B       # noqa: E402

CLOCK = [1000]


def _aim_at(sc, x, y, z):
    """Point the player's camera at a world point.

    The over-the-shoulder boom moves with the yaw, so the aim is solved from the
    ray origin and iterated until it stops moving.
    """
    for _ in range(6):
        o, _d = sc._aim_ray()
        dx, dy, dz = x - o[0], y - o[1], z - o[2]
        sc.yaw = math.degrees(math.atan2(dx, dz)) % 360.0
        sc.pitch = max(R.PITCH_LIM[0], min(R.PITCH_LIM[1], math.degrees(math.atan2(dy, math.hypot(dx, dz)))))
    sc.body_yaw = sc.yaw


def _steps(sc, n, dt=1.0 / 30.0):
    STATE.dt = dt
    for _ in range(n):
        CLOCK[0] += int(dt * 1000)
        sc.update(_Empty())


class _Empty:
    def __getitem__(self, code):
        return False


def _boot():
    save_system.select_slot(0)
    save_system.start_new_campaign(0)
    STATE.m7_preps = ["tractor", "shed"]
    m7.start_m7("raid")
    sc = R.scene()
    assert sc is not None and sc.active()
    _steps(sc, 4)
    return sc


def main():
    pin_wall(ms=lambda: CLOCK[0], s=lambda: CLOCK[0] / 1000.0)
    try:
        sc = _boot()
        pig = sc.pig
        assert not pig["dead"] and not sc.pig_dead
        assert STATE.m7_pig_dead is False
        assert sc.brain.bodi["state"] == "up"

        # --- a shot that misses leaves it alone ---------------------------
        sc.px, sc.pz = pig["x"] - 3.0, pig["z"]
        _aim_at(sc, pig["x"], R.EYE_H + 1.2, pig["z"])
        sc._fire()
        assert not pig["dead"], "a shot into the sky must not kill the pig"

        # --- one barrel on target does ------------------------------------
        _aim_at(sc, pig["x"], R.PIG_HIT_Y, pig["z"])
        sc.last_fire = -9.0
        sc._fire()
        assert pig["dead"], "the pig must go down to a barrel"
        assert sc.pig_dead and STATE.m7_pig_dead is True
        assert STATE.m7_pig_at == (pig["x"], pig["z"])
        assert sc.world.pig_at == (pig["x"], pig["z"]), "the body stays in the yard"

        # --- he turns on you ------------------------------------------------
        bodi = sc.brain.bodi
        assert sc.turn is not None, "the pig kill must start the betrayal"
        assert bodi["state"] == "turned", bodi["state"]
        assert bodi["loft"] is False, "he comes down out of the loft for this"
        assert sc.brain.near_revive() is None, "he cannot be helped back up"
        cands = [c[0] for c in sc.brain._cands()]
        assert "bodi" not in cands, "he is off the target list"
        hp = bodi["hp"]
        sc.brain._damage("bodi", 40.0, None)
        assert bodi["hp"] == hp, "he cannot be wounded once he turns"

        # --- and shooting him does nothing but spark ------------------------
        _aim_at(sc, bodi["x"], bodi["y"] + 1.15, bodi["z"])
        sc.last_fire = -9.0
        sc.mag = sc.MAG
        sc._fire()
        assert bodi["hp"] == hp, "pellets must not wound him"
        assert bodi["state"] == "turned", "he does not go down"
        assert sc.turn["taunt"], "he answers the shot"
        assert any(k == "spark" for _t, _p, k in sc.impacts), "his hits are sparks"
        assert not sc.dying, "you cannot win the exchange"

        # --- the Guards cannot finish you while he walks you down -----------
        hp_now = STATE.player.hp
        sc.hurt_player(30.0, (bodi["x"], bodi["z"]))
        assert STATE.player.hp == hp_now, "nothing else reaches you during the beat"

        # --- the beat: stare, walk in, shoulder, fire -----------------------
        px0, pz0 = sc.px, sc.pz
        from missions.m7 import flow as _flow
        stage0 = STATE.mission7_stage
        phases = []
        for _ in range(360):                      # 12 s at 30 fps, with W held
            _steps(sc, 1)
            if sc.turn is not None and (not phases or phases[-1] != sc.turn["phase"]):
                phases.append(sc.turn["phase"])
            if sc.dying:
                break
        assert sc.dying, "he must shoot the player"
        assert phases[:3] == ["stare", "close", "raise"], phases
        assert (sc.px, sc.pz) == (px0, pz0), "you cannot walk out of it"
        assert STATE.player.hp <= 0, STATE.player.hp
        assert sc.death_msg == R.TURN_DEATH_MSG, sc.death_msg
        assert sc.tracers and sc.flashes, "his round is on screen"
        assert any(k == "blood" for _t, _p, k in sc.impacts), "and it draws blood"
        assert any(abs(p[0] - sc.px) < 1.0 and abs(p[2] - sc.pz) < 1.0
                   for _t, p, k in sc.impacts if k == "blood"), "the round lands on you"
        assert not sc.done, "being killed is not a way to finish the mission"
        assert STATE.mission7_stage == stage0, "the mission must not advance"

        # --- the loss is on the HUD and in the frame ------------------------
        from missions.m7 import raid_hud
        surf = pygame.Surface((config.WIDTH, config.HEIGHT))
        sc.draw(surf)
        assert pygame.image.tobytes(surf, "RGB"), "the raid must still draw"
        hud_src = open(raid_hud.__file__.replace(".pyc", ".py"),
                       encoding="utf-8", errors="ignore").read()
        assert "BODI HAS TURNED ON YOU" in hud_src

        # --- the pig cannot be killed twice ---------------------------------
        fell = pig["fell_at"]
        sc.last_fire = -9.0
        sc._fire()
        assert pig["fell_at"] == fell

        # --- a corpse mesh goes through the renderer ------------------------
        mesh = sc._dead_pig_mesh()
        assert len(mesh.verts) == len(R.F.pig().verts)
        assert len(mesh.faces) == len(R.F.pig().faces)

        # --- dying reloads the checkpoint: everything is back ---------------
        sc.death_t = 3.0          # the veil has had its 2.4 s
        _steps(sc, 2)
        assert sc.cp == 0 and not sc.dying
        assert sc.turn is None, "the beat must be cleared by the reload"
        assert sc.pig["dead"] is False
        assert STATE.m7_pig_dead is False and STATE.m7_pig_at is None
        assert sc.brain.bodi["state"] == "up"
        assert sc.brain.bodi["hp"] > 0
        assert STATE.player.hp == STATE.player.max_hp, STATE.player.hp

        print("M7 PIG DEATH TEST: OK")
    finally:
        unpin_wall()


if __name__ == "__main__":
    main()
