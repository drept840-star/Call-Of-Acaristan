"""M5 harbour pass guard: the cubical cast and the choreography are pinned, art is validated.

EXPECTED_MOTION pins the AST of the four choreography functions in
cutscenes/m5shadow3d.py so a graphics/art change cannot silently move the
blocking. Re-pin it ONLY after an intentional choreography change that passes
tools/m5_shadow_check.py (two-hand contact, planted feet, column clearance,
head-safe framing, lowering order): regenerate with
    python -c "import ast,hashlib;from pathlib import Path;t=ast.parse(Path('src/cutscenes/m5shadow3d.py').read_text());print({n.name:hashlib.sha256(ast.dump(n,include_attributes=False).encode()).hexdigest() for n in t.body if isinstance(n,ast.FunctionDef) and n.name in ('armed_pose','walking_pose','state_at','_camera')})"
Last re-pin: 2026-10-13, two-handed weapon solver for both actors, stair
descent exit route, two-stage lowering, withdrawal shot to UC_RETREAT_END.
"""
import ast
import hashlib
import json
from pathlib import Path
import os
import sys
os.environ.setdefault('SDL_VIDEODRIVER','dummy');os.environ.setdefault('SDL_AUDIODRIVER','dummy')
os.environ.setdefault('PYGAME_HIDE_SUPPORT_PROMPT','1')
ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT/'src'))
import pygame
from cutscenes import m5shadow3d as film,m5harbour_art as art
EXPECTED_BODIES = ['3cd6ec6c36a36e87f38a1d52a693326016190f318366165bf3ac4e701431f87c', '61971aed955ba844735441b89ef5d589d6becbd70674ae1784cbdd859ccc0e25', '36b9a90dfa724a0a1aa1c50f030f979cfc9ad8a37f6ca4c0f93e1a1954ac5cb7']
EXPECTED_MOTION = {'armed_pose': '64b453dbd25c1c0a6c786e25073a896f29eed1cc31383c112728c0464541e5af', 'walking_pose': 'd2fc2372f9d4b4ce2dc3f83dc66ed67261caf7167e8286f216c2c4c4249b9e58', 'state_at': '8f28face79ecdeeee968af7e887581027103b130de5f7b75d794f7e3e93c7691', '_camera': '297dc08a677f1881adfd1bb6c1d018fb41bbbf221325084f2dbb0e31b9001410'}

def body_hash(h):
    data={}
    for name,(verts,faces) in sorted(h._parts.items()):
        if name=='rifle':continue
        data[name]=([[round(v,8) for v in p] for p in verts],faces)
    return hashlib.sha256(json.dumps(data,sort_keys=True).encode()).hexdigest()

def check():
    pygame.init()
    assert [body_hash(h) for h in film.actors()]==EXPECTED_BODIES,'Canonical cubic people changed'
    tree=ast.parse((ROOT/'src/cutscenes/m5shadow3d.py').read_text())
    actual={n.name:hashlib.sha256(ast.dump(n,include_attributes=False).encode()).hexdigest() for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in EXPECTED_MOTION}
    assert actual==EXPECTED_MOTION,'Choreography changed: '+', '.join(k for k in EXPECTED_MOTION if actual.get(k)!=EXPECTED_MOTION[k])+' (if intentional and m5_shadow_check passes, re-pin EXPECTED_MOTION; see module docstring)'
    assert film.RW>=1000 and film.RH>=476,'Picture still undersampled'
    assert all(art.lettering(text,1)[0] for text in ('RIVER 03',))
    assert art.spill((-5.4,0,-2.7),(60,70,70))[0]>art.spill((8,0,2),(60,70,70))[0]+15,'No warm practical spill'
    assert art.water_mesh(0,False).verts==art.water_mesh(15000,False).verts,'Reduced-motion water still animates'
    assert art.water_mesh(0,True).verts!=art.water_mesh(15000,True).verts,'River is frozen'
    # Every generated face references valid geometry; no random unseeded build.
    parts=tuple(art.scene_meshes())+tuple(art.world_shell())
    for mesh in parts:
        assert mesh.verts and mesh.faces
        for inds,c,layer,ds,em in mesh.faces:
            assert len(inds)>=3 and all(0<=i<len(mesh.verts) for i in inds)
            assert all(0<=v<=255 for v in c)
    # Repeating the SAME frame and seeking from another shot must not alter lighting.
    s=pygame.Surface((1000,700));s.fill((0,0,0))
    def frame(t):film.draw(s,t,True);return pygame.image.tobytes(s,'RGB')
    for t in (1500,10700,19500,33800,37000):
        a=frame(t);assert a==frame(t),'Previous-frame light leaked into river'
        frame(15500);assert a==frame(t),'Out-of-order seek changed art'
    print('M5 HARBOUR ART: OK (cubic bodies/faces and choreography unchanged; practical spill, water, meshes, supersampling, deterministic lighting)')
if __name__=='__main__':check()
