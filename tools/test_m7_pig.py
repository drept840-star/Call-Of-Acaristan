"""Focused geometry and raid gait regression checks; run from the project root."""
import math
import os
import random
import sys
from pathlib import Path
from types import SimpleNamespace

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import pygame
from cutscenes.m7pig3d import FRAMES, STRIDE, STANCE, foot_target, pig_pose, walking_frame
from engine3d.core import SoftwareRenderer
from missions.m7.raid3d import RaidScene


class World:
    pig_at = None
    blocked = False

    def move(self, x, z, dx, dz, r):
        assert self.pig_at is None
        return (x, z) if self.blocked else (x + dx, z + dz)


def main():
    pygame.init()
    standing = pig_pose()
    poses = [pig_pose(i) for i in range(FRAMES)]
    assert len({id(p) for p in poses}) == FRAMES
    assert pig_pose(0) is poses[0]
    assert all(len(p.verts) == len(standing.verts) for p in poses)
    assert poses[0].verts != poses[FRAMES // 2].verts
    assert walking_frame(0) == walking_frame(STRIDE) == 0
    assert walking_frame(STRIDE / 2) == FRAMES // 2
    assert all(math.isfinite(v) for p in poses for vertex in p.verts for v in vertex)
    # In stance the planted foot must stay still in world space as the body moves.
    for offset in (0.0, 0.25, 0.5, 0.75):
        t1 = (0.10 - offset) % 1.0
        t2 = (0.20 - offset) % 1.0
        x1, h1 = foot_target(t1, offset)
        x2, h2 = foot_target(t2, offset)
        assert h1 == h2 == 0.0
        assert abs((x1 + 0.1 * STRIDE) - (x2 + 0.2 * STRIDE)) < 1e-9
    assert foot_target(STANCE + (1.0 - STANCE) / 2, 0.0)[1] > 0.07
    assert abs(foot_target(1.0, 0.0)[0] - foot_target(0.0, 0.0)[0]) < 1e-9

    world = World()
    pig = dict(x=0., z=0., tx=2., tz=0., yaw=0., mode='walk', gait=0.,
               scared=False, shy_t=-9., next=100., stuck=0., dead=False, fell_at=0.)
    scene = SimpleNamespace(pig=pig, world=world, px=10., pz=10., t=0.,
                            fire=SimpleNamespace(lit=False), _pig_rng=random.Random(47))
    RaidScene._pig_update(scene, 0.5)
    assert abs(pig['x'] - 0.3) < 1e-6 and abs(pig['gait'] - 0.3) < 1e-6
    assert world.pig_at == (pig['x'], pig['z'])
    world.blocked = True
    distance = pig['gait']
    RaidScene._pig_update(scene, 0.1)
    assert pig['gait'] == distance  # no skating when blocked
    pig.update(tx=pig['x'], tz=pig['z'], mode='walk')
    RaidScene._pig_update(scene, 0.1)  # exact arrival must not divide by zero
    assert pig['mode'] == 'graze'

    # Both poses must make it through the real software renderer and differ.
    renderer = SoftwareRenderer(320, 240, fog_start=100, fog_end=200)
    renderer.set_camera((1.8, 1.1, -2.5), (0, 0.35, 0), 32)
    images = []
    for pose in (poses[0], poses[4]):
        renderer.begin()
        faces = [(f[0], f[1], f[2], f[3], None, f[4]) for f in pose.faces]
        renderer.add_dynamic(pose.verts, faces)
        surface = pygame.Surface((320, 240))
        surface.fill((85, 94, 92))
        renderer.flush(surface)
        images.append(pygame.image.tobytes(surface, 'RGB'))
    assert images[0] != images[1]
    print('M7 PIG TEST: OK')


if __name__ == '__main__':
    main()
