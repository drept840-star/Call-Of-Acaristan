"""Deterministic M5 preview suite. python tools/m5_encounter_review.py [capture|test|export OFFSET]
PNG frames are full delivery resolution; JPEGs and manifests are portable review copies.
"""
import os, sys, json, pathlib, io, base64, zipfile, random
ROOT = pathlib.Path(__file__).resolve().parents[1]
os.environ.setdefault('SDL_VIDEODRIVER', 'dummy')
os.environ.setdefault('SDL_AUDIODRIVER', 'dummy')
os.environ.setdefault('ACARISTAN_RENDERER', 'software')
os.environ['ACARISTAN_CUTSCENE3D'] = '1'
OUT = ROOT / 'previews' / 'm5_encounter_review'

def export(offset):
    data = base64.b64encode((OUT / 'review.zip').read_bytes()).decode()
    print(data[offset:offset + 200000])

if len(sys.argv) > 1 and sys.argv[1] == 'export':
    export(int(sys.argv[2])); sys.exit(0)

sys.path.insert(0, str(ROOT / 'src'))
import pygame
pygame.init()
from core.config import WIDTH, HEIGHT, TILE_SIZE, screen, LETTER_H
from core.state import STATE
from missions.m5 import flow, quarter, systems, world, draw, meta
from cutscenes import engine, m5mid3d, m5martial3d
import game.world as _gw  # RPE6 Phase 5 (D4)
from missions.m5.components import M5Guard as _M5Guard


def _m5g(e):
    return _gw.ensure(e, _M5Guard)



def fresh():
    random.seed(42)
    flow.start_mission5_quarter_checkpoint()
    STATE.player.rect.center = world._tile_world(30, 14)
    STATE.player_dead = False
    STATE.bullets.clear()
    return quarter._faces()


def test():
    faces = fresh()
    assert len(faces) == 2 and all(_m5g(e).passive for e in faces)
    pos = STATE.player.rect.center
    before = quarter._S['convoy']
    flow._update_stage(None)
    assert STATE.request_m5_cutscene == 'old_faces', STATE.request_m5_cutscene
    assert STATE.mission5_stage == meta.STAGE_QUARTER
    count = quarter._S['convoy']
    assert count == before + 1
    for _ in range(1000):
        systems.game_update(pygame.key.get_pressed())
    assert quarter._S['convoy'] == count and STATE.player.rect.center == pos
    flow.on_m5_cutscene_done('old_faces')
    for _ in range(1000):
        quarter._update_faces(*pos)
    assert STATE.request_m5_cutscene is None
    assert quarter._S['faces_spoken'] == {'KOVAC', 'SANDU'}
    # Walk away and re-enter; still no replay.
    STATE.player.rect.center = world._tile_world(24, 15)
    quarter.update()
    STATE.player.rect.center = pos
    quarter.update()
    assert STATE.request_m5_cutscene is None
    assert all(_m5g(e).passive for e in faces)
    assert sum(e.hp > 0 and not _m5g(e).passive for e in STATE.enemies) == 5
    # Arrival is not allowed to replace an unplayed encounter.
    fresh(); STATE.player.rect.center = world._printworks_door_pos()
    flow._update_stage(None)
    assert STATE.request_m5_cutscene == 'old_faces' and STATE.mission5_stage == meta.STAGE_QUARTER
    flow.on_m5_cutscene_done('old_faces'); flow._update_stage(None)
    assert STATE.mission5_stage == meta.STAGE_PRINTWORKS and STATE.request_m5_cutscene == 'arrival'
    # Fresh checkpoint = fresh encounter, but casualties/violence don't get a friendly take.
    faces = fresh(); STATE.m5_guard_kills = 4
    quarter._update_faces(*STATE.player.rect.center)
    assert not STATE.request_m5_cutscene
    assert any(not _m5g(e).passive for e in faces)
    faces = fresh(); faces[0].hp = 0
    quarter._update_faces(*STATE.player.rect.center)
    assert not STATE.request_m5_cutscene
    faces = fresh(); faces[0].m5_hp0 = faces[0].hp; faces[0].hp -= 1
    quarter._update_faces(*STATE.player.rect.center)
    assert not STATE.request_m5_cutscene and not _m5g(faces[0]).passive
    faces = fresh(); quarter._provoke_faces_by_noise(*STATE.player.rect.center)
    quarter._update_faces(*STATE.player.rect.center)
    assert not STATE.request_m5_cutscene and all(not _m5g(e).passive for e in faces)
    fresh(); STATE.bullets.append(dict(owner='enemy', x=STATE.player.rect.centerx, y=STATE.player.rect.centery))
    quarter._update_faces(*STATE.player.rect.center)
    assert not STATE.request_m5_cutscene
    fresh(); STATE.walls.append(pygame.Rect(29*TILE_SIZE, 0, 10, 30*TILE_SIZE))
    # A wall between the camera approach and the cast must suppress the trigger.
    STATE.player.rect.center = world._tile_world(28, 15)
    quarter._update_faces(*STATE.player.rect.center)
    assert not STATE.request_m5_cutscene
    print('M5 ENCOUNTER TEST: OK (repeat, handoff, timer, fresh run, kills, casualty, damage, noise, bullets, wall)')


def capture():
    from PIL import Image
    OUT.mkdir(parents=True, exist_ok=True)
    manifest = []
    def save(label, **info):
        name = f'{len(manifest):03d}_{label}'
        pygame.image.save(screen, str(OUT / (name + '.png')))
        Image.open(OUT / (name + '.png')).convert('RGB').save(OUT / (name + '.jpg'), quality=82)
        manifest.append(dict(file=name + '.jpg', **info))
    groups = [('intro', meta.mission5_intro_shots)] + list(meta.M5_MID_CUTSCENES.items()) + [('ending', meta.mission5_ending_shots)]
    for group, shots in groups:
        for i, shot in enumerate(shots):
            for frac in (0.08, 0.5, 0.92):
                t = int(shot['min_ms'] * frac)
                engine.draw_cutscene_scene(screen, shot, t)
                pygame.draw.rect(screen, (0,0,0), (0,0,WIDTH,LETTER_H))
                pygame.draw.rect(screen, (0,0,0), (0,HEIGHT-LETTER_H,WIDTH,LETTER_H))
                engine.reset_dialogue_slide()
                if shot['scene'] == 'title_card':
                    engine.draw_typewriter_title(screen, shot['text'].split('\n'), len(shot['text']))
                elif shot.get('text'):
                    engine.draw_dialogue_box(screen, shot.get('speaker',''), shot['text'], len(shot['text']), len(shot['text']))
                if m5martial3d._cache.get('err'):
                    raise RuntimeError(m5martial3d._cache['err'])
                save(f'{group}_{i}_{t}', kind='cutscene', scene=shot['scene'], t=t)
    for i, shot in enumerate(meta.M5_MID_CUTSCENES['old_faces']):
        for frac in (0.08, 0.5, 0.92):
            t = int(shot['min_ms']*frac)
            m5mid3d.draw_m5x_2d(shot['scene'], screen, t)
            pygame.draw.rect(screen,(0,0,0),(0,0,WIDTH,LETTER_H))
            pygame.draw.rect(screen,(0,0,0),(0,HEIGHT-LETTER_H,WIDTH,LETTER_H))
            engine.draw_dialogue_box(screen,shot['speaker'],shot['text'],len(shot['text']),len(shot['text']))
            save(f'fallback_{i}_{t}',kind='fallback',scene=shot['scene'],t=t)
    # Stage snapshots use the real game_draw and camera clamp, not synthetic art.
    flow.start_m5()
    def gameplay(label, pos):
        STATE.player.rect.center = tuple(map(int,pos))
        STATE.dt = 1/60
        flow._snap_camera_safe()
        draw.game_draw(int(STATE.camera_x),int(STATE.camera_y))
        save(label,kind='gameplay',stage=STATE.mission5_stage)
    for c,r in ((4,11),(20,8),(24,5)):
        gameplay(f'hq_{c}_{r}',world._tile_world(c,r))
    flow._enter_quarter()
    for c,r in ((6,15),(9,15),(17,15),(24,15),(29,15),(31,13),(33,15),(16,24)):
        gameplay(f'quarter_{c}_{r}',world._tile_world(c,r))
    gameplay('before_encounter',world._tile_world(30,14))
    flow._update_stage(None)
    assert STATE.request_m5_cutscene == 'old_faces'
    flow.on_m5_cutscene_done('old_faces')
    gameplay('after_encounter',STATE.player.rect.center)
    flow._enter_printworks()
    gameplay('print_entry',STATE.player.rect.center)
    gameplay('print_maru',world._maru_office_pos())
    flow._start_maru_dialogue(); flow.on_m5_cutscene_done('maru')
    for tick in (0,30,90):
        for _ in range(tick):
            systems.game_update(pygame.key.get_pressed())
        gameplay(f'raid_{tick}',world._maru_office_pos())
    flow._enter_tunnel()
    for c,r in ((3,6),(10,6),(20,6)):
        gameplay(f'tunnel_{c}_{r}',world._tile_world(c,r))
    (OUT/'manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
    with zipfile.ZipFile(OUT/'review.zip','w',zipfile.ZIP_DEFLATED) as z:
        for entry in manifest: z.write(OUT/entry['file'],entry['file'])
        z.write(OUT/'manifest.json','manifest.json')
    print(f'PREVIEW SUITE: OK; {len(manifest)} full-resolution frames; archive bytes={(OUT/"review.zip").stat().st_size}')

if __name__ == '__main__':
    mode = sys.argv[1] if len(sys.argv)>1 else 'test'
    if mode == 'test': test()
    elif mode == 'capture': capture()
    else: raise ValueError(mode)
