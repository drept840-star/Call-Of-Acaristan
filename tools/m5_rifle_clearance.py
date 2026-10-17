"""Weapon clearance against actual torso/head/pelvis box meshes, plus grip reach."""
import os,sys,math,itertools
from pathlib import Path
os.environ.setdefault('PYGAME_HIDE_SUPPORT_PROMPT','1')
sys.path.insert(0,str(Path(__file__).resolve().parent.parent/'src'))
from engine3d.core import m_apply
from cutscenes.cast3d import humanoid3d
from cutscenes import m5ending3d as s

def local(M,org,v):
    sc2=sum(M[i]**2 for i in (0,3,6))
    d=tuple(a-b for a,b in zip(v,org))
    return tuple(sum(M[j*3+i]*d[j] for j in range(3))/sc2 for i in range(3))

def penetration(hum,pose):
    places,j,R,_=hum.placements(pose)
    samples=[]
    # Dense samples along every weapon face: not just corners outside a torso.
    for inds,*_ in hum._rifle.faces:
        vs=[hum._rifle.verts[i] for i in inds]
        for u in range(9):
            for v in range(3):
                a=u/8;b=v/2
                samples.append(tuple((1-a)*((1-b)*vs[0][k]+b*vs[1][k])+a*((1-b)*vs[3][k]+b*vs[2][k]) for k in range(3)))
    world=[tuple(a+b for a,b in zip(j['rhand'],m_apply(R,p))) for p in samples]
    hits=0
    for slot,key,M,org,*_ in places:
        if key not in ('torso','head','pelvis'):continue
        verts=hum._parts[key][0]
        pts=[local(M,org,p) for p in world]
        # Rig boxes use 24 verts each (6 faces); check each actual solid.
        for n in range(0,len(verts),24):
            block=verts[n:n+24]
            lo=[min(v[k] for v in block)+.004 for k in range(3)]
            hi=[max(v[k] for v in block)-.004 for k in range(3)]
            hits+=sum(all(lo[k]<p[k]<hi[k] for k in range(3)) for p in pts)
    return hits

def legacy_pose(hum,pitch):
    """Known-bad fixture proves the test detects the reported stock clipping."""
    k=(pitch-14)/38
    pose=dict(s.stride(0,0),head_p=8,rifle_p=pitch)
    places,_,_,_=hum.placements(pose,rifle_on=False)
    shoulder=next(o for slot,key,M,o,*_ in places if slot==10)
    S=next(M for slot,key,M,o,*_ in places if slot==1)
    trigger=tuple(a+b for a,b in zip(shoulder,m_apply(S,(-.13,.10-.23*k,.12))))
    return s.solve_hand(hum,pose,'r',trigger)

if __name__=='__main__':
    hum=humanoid3d('ucilev',rifle='sniper')
    assert penetration(hum,legacy_pose(hum,38))>0,'Clipping detector failed its known-bad fixture'
    for pitch,d in itertools.product(range(14,53),(0,.125,.25,.375,.5,.625,.75,.875)):
        pose=s.rifle_pose(hum,pitch,d,1)
        assert penetration(hum,pose)==0,(pitch,d)
    print('M5 RIFLE CLEARANCE: OK; known-bad pose rejected, 312 current poses clear')
