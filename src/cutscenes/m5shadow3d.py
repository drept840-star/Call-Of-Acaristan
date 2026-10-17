"""The rebuilt M5 finale: one fresh 3D set, actor clock and camera language.

NOT a wrapper around m5martial3d/m5ending3d. Uses the engine and canon cast,
but all blocking, weapon choreography, camera paths and set geometry are new.
Software fallback remains real 3D. Drawing never mutates campaign state.
"""
from functools import lru_cache
import math

import pygame
from engine3d import (Renderer, SoftwareRenderer, Mesh, Light, box, prism,
                      quad_xz, rot_y, rot_x, m_apply, m_mul, v_add, v_sub,
                      v_lerp, v_norm, v_cross, v_dot, M_IDENT)
from cutscenes.cast3d import humanoid3d
from cutscenes.m5harbour_art import DOOR_X0, DOOR_X1
from core.config import WIDTH, HEIGHT, SCENE_TOP, SCENE_BOT, resource_path
from core.outfits import biribel_3d, OUTFIT_GUARD
from missions.m5.finale_script import LINES, CUTS, DURATION_MS

TOP, BOT = 112, 588
RW, RH = 1200, 572
BIRI = (0.0, 0.0, 0.0)
UC = (-2.0, 5.0, 26.4)
_MARU_START = (-2.7, 0.0, -2.7)
_cache = {}
ENV_LIGHT = Light(direction=(-.45,.8,-.5),ambient=.48,diffuse=.55,sky=.13,tint=(1.02,1.02,.96))
STANCE = 0.56   # walk duty factor: with feet offset half a cycle this keeps
                # ~12% double support and no flight phase (0.25 read as a
                # bouncing run: both feet airborne half the cycle)


def k(t,start,duration):
    p=max(0.0,min(1.0,(float(t)-start)/duration))
    return p*p*p*(p*(p*6-15)+10)


def mix(a,b,p):return a+(b-a)*p


def yaw_to(a,b):return math.degrees(math.atan2(b[0]-a[0],b[2]-a[2]))


def yaw_mix(a,b,p):return a+((b-a+180)%360-180)*p


def travel(t,start,duration):
    """Integrated smooth start/stop, steady middle: distance drives the gait."""
    p=max(0.0,min(1.0,(t-start)/duration));a=.16
    if p<a:q=p*p/(2*a)
    elif p>1-a:q=1-a-(1-p)*(1-p)/(2*a)
    else:q=p-a/2
    return q/(1-a)


def reduced_motion():
    from core.state import STATE  # lazy: draw reads a setting, never writes it
    return bool(getattr(STATE,'reduced_motion',False))


def _transform(mesh, matrix=M_IDENT, origin=(0,0,0)):
    """Small new dynamic accessory, through the PUBLIC renderer mesh API."""
    verts=[v_add(origin,m_apply(matrix,p)) for p in mesh.verts]
    faces=[(idx,col,layer,ds,None,em) for idx,col,layer,ds,em in mesh.faces]
    return verts,faces


def _dynamic(r,mesh,m=M_IDENT,origin=(0,0,0),bias=0.0):
    v,f=_transform(mesh,m,origin);r.add_dynamic(v,f,bias=bias)


@lru_cache(maxsize=1)
def _sniper():
    """Compact detailed marksman rifle. Origin=dominant grip, +z=muzzle."""
    m=Mesh();steel=(75,84,83);dark=(24,32,34);rim=(152,152,128)
    m.add(box(.065,.085,.38,steel,center=(0,.01,.105),cols={'top':rim,'left':(64,78,80),'bottom':(32,44,47)}))
    m.add(box(.045,.065,.31,dark,center=(0,.005,-.22),cols={'top':(79,89,78),'left':(43,55,54)}))
    m.add(box(.064,.14,.042,(39,47,49),center=(0,-.03,-.36)))
    m.add(box(.045,.13,.07,(30,37,41),center=(0,-.075,.115)))
    m.add(box(.054,.06,.22,(49,61,63),center=(0,.007,.36)))
    for z in (.30,.34,.38,.42):m.add(box(.058,.007,.012,rim,center=(0,.039,z)))
    m.add(box(.022,.022,.42,dark,center=(0,.01,.68)))
    m.add(box(.042,.044,.16,(42,53,59),center=(0,.01,.96)))
    m.add(box(.043,.008,.012,rim,center=(0,.024,1.04)))
    # Scope mount and a faceted tube; no giant featureless black brick.
    for z in (.05,.20):m.add(box(.03,.037,.025,dark,center=(0,.074,z)))
    tube=prism([(-.031,.097),(-.024,.073),(.024,.073),(.031,.097),(.022,.121),(-.022,.121)],.23,(28,36,41),z0=.01)
    m.add(tube)
    m.add(box(.052,.046,.036,(68,83,91),center=(0,.098,.25)))
    m.add(box(.034,.022,.003,(80,125,132),center=(0,.099,.270),emissive=True))
    m.add(box(.020,.042,.024,dark,center=(.038,.106,.13)))
    m.add(box(.009,.027,.058,rim,center=(.038,.018,.09)))
    return m


def _fit_weapon(hum,foregrip):
    """Instance-owned weapon fit: butt-to-grip length and support-hand point."""
    hum._stock=-min(v[2] for v in hum._rifle.verts)
    hum._foregrip=foregrip

@lru_cache(maxsize=1)
def actors():
    b=humanoid3d('biribel',rifle='rifle',**biribel_3d(OUTFIT_GUARD))
    compact=Mesh()
    compact.add(box(.065,.09,.25,(64,77,78),center=(0,.01,.10),cols={'top':(132,145,128),'left':(87,100,95),'bottom':(27,42,46)}))
    compact.add(box(.035,.034,.19,(28,41,49),center=(0,.012,.32)))
    compact.add(box(.048,.05,.10,(83,100,102),center=(0,.013,.43)))
    compact.add(box(.037,.20,.065,(29,41,48),center=(0,-.10,.10)))
    compact.add(box(.035,.065,.20,(34,44,49),center=(0,.006,-.15)))
    for z in (.05,.10,.15):compact.add(box(.067,.009,.012,(143,151,134),center=(0,.06,z)))
    b._rifle=compact
    _fit_weapon(b,(0,-.040,.30))
    u = humanoid3d('ucilev', rifle='sniper')
    u._rifle = _sniper()
    _fit_weapon(u, (0, -.058, .27))
    m=humanoid3d('maru',rifle=None)
    return b,u,m
_CHEST=dict(front=.19,back=-.16,bottom=-.08,top=.06,width=.78)

def _body(hum,places):
    """-> (to_local, to_world, half_width, shoulder_height) for the torso."""
    S=_torso(places)
    org=next(o for slot,key,M,o,gr,fb in places if slot==1)
    sc2=hum._scale*hum._scale
    def local(p):
        d=v_sub(p,org)
        return tuple(sum(S[j*3+i]*d[j] for j in range(3))/sc2 for i in range(3))
    def world(q):return v_add(org,m_apply(S,q))
    sh=local(next(o for slot,key,M,o,gr,fb in places if slot==10))
    return local,world,abs(sh[0])*_CHEST['width'],sh[1]

def _chest_ellipse(w,margin):
    zc=(_CHEST['front']+_CHEST['back'])/2
    return zc,w+margin,(_CHEST['front']-_CHEST['back'])/2+margin

def _inside(q,w,top,margin):
    """Penetration depth (0 = clear, ->1 = at the core) of a torso-local point."""
    x,y,z=q
    if not _CHEST['bottom']-margin<=y<=top+_CHEST['top']+margin:return 0.0
    zc,hx,hz=_chest_ellipse(w,margin)
    return max(0.0,1-((x/hx)**2+((z-zc)/hz)**2))

def _push_out(q,w,top,margin):
    """Move a torso-local point radially onto the inflated chest surface."""
    if _inside(q,w,top,margin)<=0:return q
    x,y,z=q;zc,hx,hz=_chest_ellipse(w,margin)
    ex,ez=x/hx,(z-zc)/hz;e=math.hypot(ex,ez)
    if e<1e-4:ex,ez,e=0.0,1.0,1.0
    return (hx*ex/e,y,zc+hz*ez/e)

def _arm_clash(hum,pose,side):
    """How deeply this arm's elbow, forearm and hand sit inside the torso."""
    places,j,_,_=hum.placements(pose,False)
    local,_,w,top=_body(hum,places)
    slot=4 if side=='l' else 10
    U=next(M for s,key,M,o,gr,fb in places if s==slot)
    sh=next(o for s,key,M,o,gr,fb in places if s==slot)
    elbow=v_add(sh,m_apply(U,(0,-.30,0)))
    hand=j.get(side+'hand',elbow)
    return (_inside(local(elbow),w,top,.02)
            +_inside(local(v_lerp(elbow,hand,.5)),w,top,.03)
            +_inside(local(hand),w,top,.045))

def _torso(places):
    return next(M for slot,key,M,org,gr,fb in places if slot==1)


def _solve(hum,pose,side,target,clamp=False,margin=.045):
    """Fresh two-link IK, solved in torso coordinates (not interpolated poses).
    The hand target is first pushed clear of the torso; then both elbow branches
    are scored on joint limits AND on whether the arm passes through the body.
    clamp=True extends the arm fully toward an out-of-reach target instead of raising.
    """
    places,joints,_,_=hum.placements(pose,rifle_on=False)
    local,world,w,top=_body(hum,places)
    target=world(_push_out(local(target),w,top,margin))
    S=_torso(places)
    shoulder=next(org for slot,key,M,org,gr,fb in places if slot==(4 if side=='l' else 10))
    scale=hum._scale;delta=v_sub(target,shoulder)
    q=tuple(sum(S[j*3+i]*delta[j] for j in range(3))/(scale*scale) for i in range(3))
    x,y,z=q;distance=math.sqrt(x*x+y*y+z*z)
    if distance>.609:
        if not clamp:raise ValueError('Unreachable '+side+' hand target: '+str(distance))
        f=.600/distance;x,y,z=x*f,y*f,z*f;distance=.600
    elbow=math.acos(max(-.995,min(.999,(distance*distance-.30*.30-.31*.31)/(2*.30*.31))))
    a=.30+.31*math.cos(elbow);b=.31*math.sin(elbow)
    best=None
    for sign in (-1,1):
        lateral=sign*math.hypot(x,y)
        pitch=math.atan2(z,-lateral)-math.atan2(b,a)
        roll=math.atan2(x,-y) if sign<0 else math.atan2(-x,y)
        if side=='l':roll=-roll
        pitch=math.degrees(pitch);roll=math.degrees(roll)
        score=abs(roll)*.5+max(0,abs(roll)-80)*5+max(0,pitch-145)*5+max(0,-pitch-25)*5
        cand=dict(pose,**{side+'sh_p':pitch,side+'sh_r':roll,side+'el':math.degrees(elbow)})
        score+=400*_arm_clash(hum,cand,side)
        if best is None or score<best[0]:best=(score,cand)
    return best[1]

def aim_angles(src,src_yaw,dst):
    """Body-relative (yaw, pitch) from src to dst. Pitch is +down, like rifle_p."""
    dx,dy,dz=v_sub(dst,src)
    yaw=(math.degrees(math.atan2(dx,dz))-src_yaw+180)%360-180
    pitch=-math.degrees(math.atan2(dy,math.hypot(dx,dz)))
    return yaw,pitch

LASER_ON=7100
LASER_OFF=29600   # thumb on the switch: after the dot has left him, before the drop
LOWER_DIP=(28000,1300)            # "Not tonight": the muzzle eases a tenth
LOWER_DROP=(LASER_OFF+150,1800)   # dot off, then the real lowering; done before the turn

# Scripted lightning (the thunder cues in finale_script trail these by
# ~0.75 s, a far storm heard late): over Maru run, the beat before
# "Not tonight", and the withdrawal. Pure function of the authored
# clock - deterministic seek, no rng, no state.
BOLTS=(4300,26850,33800)

def _bolt(t):
    """Lightning intensity 0..1: an instant main strike and a weaker echo."""
    fl=0.0
    for t0 in BOLTS:
        d=float(t)-t0
        if 0<=d<460:
            fl=max(fl,1.0-d/200.0,.55*max(0.0,1.0-abs(d-260)/130.0))
    return fl

def _flash_scale():
    """Peak flash scale under flash-reduction (m5fx3d precedent: 0.35)."""
    try:
        from core.user_settings import SETTINGS  # lazy: settings are live
        return 0.35 if SETTINGS.flash_reduction else 1.0
    except Exception:
        return 1.0

def _frame_light(t):
    """ENV_LIGHT, lifted cool and bright while a bolt is up. Returns the
    shared ENV_LIGHT object itself outside strikes, so un-struck frames
    are shaded exactly as before."""
    fl=_bolt(t)*_flash_scale()
    if fl<=0:return ENV_LIGHT
    return Light(direction=(-.45,.8,-.5),ambient=.48+.34*fl,
                 diffuse=.55+.22*fl,sky=.13,
                 tint=(1.02-.10*fl,1.02,0.96+.24*fl))

def _fade(t):
    """Master fade alpha: in from near-black over the first beat, out to
    full black across the last two seconds (full exactly at the cut)."""
    return max(int(96*(1-k(t,0,1100))),int(255*k(t,40000,2000)))

def _laser_hit(o,d,chest,n,half_w=.19):
    """Trace the BARREL ray. Biribel first (a card through his chest facing the
    shooter, chest down to the boots), then the yard. -> (point, on_body)."""
    den=v_dot(d,n)
    if den<-1e-6:
        s=v_dot(v_sub(chest,o),n)/den
        if s>0:
            p=(o[0]+d[0]*s,o[1]+d[1]*s,o[2]+d[2]*s)
            side=v_norm(v_cross((0,1,0),n))
            rel=v_sub(p,chest)
            w=half_w if rel[1]>-.42 else .13          # torso, then legs
            if abs(v_dot(rel,side))<=w and -chest[1]<=rel[1]<=.16:
                return p,True
    if d[1]<-1e-6:                                    # off him: onto the yard
        s=-o[1]/d[1]
        return (o[0]+d[0]*s,.012,o[2]+d[2]*s),False
    return None,False


_ARM_REACH = .600   # < .30 + .31: the elbow never locks straight (sin(bend) > 0)


def _weapon_arm(hum, pose, side, target):
    """Exact two-bone IK with an elbow swivel; never move a reachable grip target.

    Never raises: a cutscene frame must not take the game down (the 16:04
    crash reports were exactly this solver throwing mid-film). An out-of-reach
    target is clamped along the shoulder ray and the hand falls short by the
    overshoot; the caller keeps grips inside shared reach so this is a guard,
    not a path the choreography relies on.
    """
    places, _, _, _ = hum.placements(pose, False)
    local, _, _, _ = _body(hum, places)

    slot = 4 if side == 'l' else 10
    shoulder = local(
        next(o for s, key, M, o, gr, fb in places if s == slot)
    )
    target = local(target)

    delta = v_sub(target, shoulder)
    distance = math.sqrt(v_dot(delta, delta))

    if distance < .011:
        # Hand on the shoulder joint: no direction to solve along.
        delta = (0.0, -.011, 0.0)
        distance = .011
    elif distance > _ARM_REACH:
        f = _ARM_REACH / distance
        delta = tuple(c * f for c in delta)
        distance = _ARM_REACH
    target = v_add(shoulder, delta)

    axis = tuple(c / distance for c in delta)
    along = (.30**2 - .31**2 + distance**2) / (2 * distance)
    height = math.sqrt(max(0.0, .30**2 - along**2))

    bend = math.degrees(math.acos(max(-1.0, min(
        1.0,
        (distance**2 - .30**2 - .31**2) / (2 * .30 * .31),
    ))))

    sx = -1 if side == 'l' else 1

    # Fixed outward/front pole prevents elbow flips during lowering. If the
    # arm happens to point straight down the pole, fall back to the next one.
    for pole in ((sx, -.4, 1.2), (sx * .8, .2, -1.0), (0.0, -1.0, 0.0)):
        dot = v_dot(pole, axis)
        normal = tuple(pole[i] - dot * axis[i] for i in range(3))
        norm = math.sqrt(v_dot(normal, normal))
        if norm >= 1e-7:
            break

    elbow = tuple(
        shoulder[i] + along * axis[i] + height * normal[i] / norm
        for i in range(3)
    )

    upper = tuple(
        (elbow[i] - shoulder[i]) / .30 for i in range(3)
    )
    fore = tuple(
        (target[i] - elbow[i]) / .31 for i in range(3)
    )

    cy = tuple(-c for c in upper)
    cb = math.cos(math.radians(bend))
    sb = math.sin(math.radians(bend))
    cz = tuple((fore[i] + cb * cy[i]) / sb for i in range(3))

    # U = Rz(roll) Rx(-pitch) Ry(swivel).
    # The swivel rotates the elbow plane without moving the upper-arm axis.
    pitch = math.degrees(math.asin(
        max(-1.0, min(1.0, upper[2]))
    ))
    roll = math.degrees(math.atan2(upper[0], -upper[1]))

    rr = math.radians(roll)
    pp = math.radians(pitch)

    bx = (math.cos(rr), math.sin(rr), 0)
    bz = (
        -math.sin(rr) * math.sin(pp),
        math.cos(rr) * math.sin(pp),
        math.cos(pp),
    )

    swivel = math.degrees(math.atan2(
        v_dot(bx, cz),
        v_dot(bz, cz),
    ))

    return dict(pose, **{
        side + 'sh_p': pitch,
        side + 'sh_r': roll / sx,
        side + 'sh_y': swivel,
        side + 'el': bend,
    })

def _two_handed_pose(hum, pose, lower):
    """Both hands on the weapon, for every actor and every lowering frame.

    lower=0: butt in the shoulder pocket, trigger hand `hum._stock` ahead of it
    (aimed). lower=1: front-of-body carry. In between, the grip blends and the
    WHOLE weapon is moved into the shared reach of both arms (the hands are
    never clamped independently: that is what detaches a support hand). The
    trigger hand is solved exactly, then the support hand onto `hum._foregrip`
    in the rifle frame, so support == rhand + R * foregrip to solver precision.
    """
    places, _, R, _ = hum.placements(pose)
    local, world, w, top = _body(hum, places)
    S = _torso(places)

    shoulder = next(
        o for s, key, M, o, gr, fb in places if s == 10
    )

    pocket = v_add(
        shoulder,
        m_apply(S, (-.05, -.06, .07)),
    )
    pocket = world(_push_out(local(pocket), w, top, .012))

    aimed = local(v_add(
        pocket,
        m_apply(R, (0, 0, hum._stock)),
    ))

    carry = (-.04, .38, .28)
    grip_local = v_lerp(aimed, carry, k(lower, 0, .85))

    # Move the whole rifle into both arms' shared reach.
    # Never clamp the hands independently: that breaks their grips.
    offset = local(v_add(
        world((0, 0, 0)),
        m_apply(R, hum._foregrip),
    ))

    right = local(shoulder)
    left = local(next(
        o for s, key, M, o, gr, fb in places if s == 4
    ))
    support_center = v_sub(left, offset)

    # Keep both hands forward of the chest, including hand thickness.
    front = max(.26, .26 - offset[2])

    for _ in range(24):
        for center in (right, support_center):
            delta = v_sub(grip_local, center)
            distance = math.sqrt(v_dot(delta, delta))

            if distance > .595:
                grip_local = v_add(
                    center,
                    tuple(c * .595 / distance for c in delta),
                )

        grip_local = (
            grip_local[0],
            grip_local[1],
            max(front, grip_local[2]),
        )

    grip = world(grip_local)
    pose = _weapon_arm(hum, pose, 'r', grip)

    _, joints, R, _ = hum.placements(pose)
    support = v_add(
        joints['rhand'],
        m_apply(R, hum._foregrip),
    )

    return _weapon_arm(hum, pose, 'l', support)


def armed_pose(hum, t, lower=0.0, breath=.5,
               aim=(0.0, 0.0), look=(0.0, 0.0)):
    motion = (
        0.0 if reduced_motion()
        else math.sin(t * .0015) * .22 * breath
    )

    pose = dict(
        spine=2,
        lhip_r=4, rhip_r=4,
        lkn=4, rkn=4,
        body_r=motion,
        head_y=max(-75.0, min(75.0, look[0])),
        head_p=max(-35.0, min(40.0, look[1])),
        rifle_y=max(-55.0, min(20.0, aim[0])),
        rifle_p=mix(aim[1], 57, lower),
    )

    # One solver for the K9 and the long rifle: the clamped per-hand path left
    # Biribel's support hand ~20 cm off his foregrip (and threw mid-film).
    return _two_handed_pose(hum, pose, max(0.0, min(1.0, lower)))

def _leg(foot_z,foot_y):
    """Two-link leg IK in rig space (thigh = shin = .45). -> hip_p, knee (deg)."""
    r=min(.897,math.hypot(foot_y,foot_z))
    knee=math.acos(max(-1,min(1,(r*r-2*.45*.45)/(2*.45*.45))))
    return math.degrees(math.atan2(foot_z,-foot_y)+knee*.5),math.degrees(knee)


def _straight(dist):
    return (0.0,0.0,dist),0.0


def gait(distance,stride,scale=1.0,speed=1.4,style='walk',route=_straight,pelvis_on=True):
    """Distance-driven walk with world-planted feet. -> (pose, pelvis_yaw_offset).

    `route(d) -> (ground pos, yaw deg)` is the path the body follows; `stride` =
    world metres per full cycle (two steps). Each contact is laid on the route
    itself (so feet step AROUND turns), held fixed in WORLD space for STANCE of
    the cycle, then swung to the next contact with knee flex and toe clearance.
    Every frame both legs are solved by IK from those world targets, so pelvis
    yaw, turns and stops never slide a planted foot. Pelvis vaults over the
    stance leg (bob = auto ground contact), rolls toward it and yaws with the
    leading leg; torso counter-rotates, head stabilises, arms swing opposite.
    style 'guard_arm': Maru - right arm clutched to the body, hunched, a pain
    hitch on every right-foot contact (the left hand is solved afterwards).
    """
    s=stride
    amp=max(0.0,min(1.0,speed/1.35))
    reach=STANCE*s/2
    ph_l=(distance/s)%1.0
    pelvis=-2.2*amp*math.cos(2*math.pi*(ph_l-.02)) if pelvis_on else 0.0
    pos,yaw=route(distance);yaw+=pelvis
    cy,sy=math.cos(math.radians(yaw)),math.sin(math.radians(yaw))
    pose=dict(lift=0)
    fwd={}
    phases={}
    for side,offset,lat in (('l',0.0,-1),('r',.5,1)):
        c=distance/s+offset;n=math.floor(c);ph=c-n;phases[side]=ph
        def plant(nn):
            p,yw=route((nn-offset)*s+reach+.03*scale)
            a=math.radians(yw);w=(.1+.012)*scale*lat

            ground_y = p[1]
            if route is _uc_exit_route:
                from cutscenes.m5harbour_art import (
                    STAIR_START_Z,
                    STAIR_END_Z,
                    STAIR_COUNT,
                    STAIR_RUN,
                    STAIR_RISE,
                    STAIR_BOTTOM_Y,
                )

                if STAIR_START_Z <= p[2] < STAIR_END_Z:
                    step = min(
                        STAIR_COUNT,
                        int((p[2] - STAIR_START_Z) / STAIR_RUN) + 1,
                    )
                    ground_y = 5.0 - step * STAIR_RISE
                elif p[2] >= STAIR_END_Z:
                    ground_y = STAIR_BOTTOM_Y

            return (
                p[0]+w*math.cos(a),
                ground_y,
                p[2]-w*math.sin(a),
            )

        if ph<STANCE:
            fx,ground_y,fzw=plant(n);q=ph/STANCE
            fy=-(.858+.022*math.sin(math.pi*q)*amp)  # straighter mid-stance -> vault
        else:
            q=(ph-STANCE)/(1-STANCE);e=q*q*(3-2*q)
            a0,a1=plant(n),plant(n+1)

            fx=mix(a0[0],a1[0],e)
            ground_y=mix(a0[1],a1[1],e)
            fzw=mix(a0[2],a1[2],e)
            fy=-.858+(.048+.018*amp)*math.sin(math.pi*min(1,q*1.1))  # ~5 cm toe clearance, not a march step

        fy+=(ground_y-pos[1])/scale
        dx,dz=fx-pos[0],fzw-pos[2]
        lx=(dx*cy-dz*sy)/scale;lz=(dx*sy+dz*cy)/scale   # world -> rig space
        hip,knee=_leg(lz,fy)
        pose[side+'hip_p']=hip;pose[side+'kn']=knee
        out=max(-.12,min(.20,(lx-lat*.1)*lat/.86))
        pose[side+'hip_r']=math.degrees(math.asin(out))
        fwd[side]=max(-1.0,min(1.0,lz/max(1e-6,reach/scale)))  # -1 back .. +1 front
    # +1 = left single support (ph_l ~.30), -1 = right single support (ph_l ~.80).
    sway=math.cos(2*math.pi*(phases['l']-.30))
    pose['body_r']=0.0
    pose['spine_r']=-1.6*sway*amp
    pose['twist']=-pelvis*1.7                      # shoulders counter-rotate
    pose['head_y']=-(pelvis+pose['twist'])         # gaze stays on the path
    pose['head_p']=0
    pose['spine']=4+2*amp
    for side,other in (('l','r'),('r','l')):
        pose[side+'sh_p']=10+19*amp*fwd[other]       # arm opposite to its leg
        pose[side+'sh_r']=7
        pose[side+'el']=16+14*amp*max(0.0,fwd[other])
    if style=='guard_arm':
        hitch=math.exp(-((phases['r'])/.10)**2)+math.exp(-((1-phases['r'])/.10)**2)
        pose.update(spine=11+3.5*hitch*amp,head_p=5-2.5*hitch*amp,twist=pose['twist']*.6,body_r=pose['body_r']*1.3)
    return pose,pelvis


def guard_left_hand(hum,pose):
    """Maru's wounded arm: right hand solved onto (not into) her stomach, then
    the left hand clamps the top of that forearm. Both arms are IK-solved."""
    places,_,_,_=hum.placements(pose,False)
    local,world,w,top=_body(hum,places)
    side=1.0 if local(next(o for s,key,M,o,gr,fb in places if s==10))[0]>0 else -1.0
    clutch=world((side*.07,top*.50,_CHEST['front']+.05))
    try:pose=_solve(hum,pose,'r',clutch,clamp=True,margin=.05)
    except ValueError:pass
    places,j,_,_=hum.placements(pose,False)
    U=next(M for slot,key,M,org,gr,fb in places if slot==10)
    sh=next(org for slot,key,M,org,gr,fb in places if slot==10)
    S=_torso(places)
    elbow=v_add(sh,m_apply(U,(0,-.30,0)))
    target=v_add(v_lerp(j['rhand'],elbow,.42),m_apply(S,(0,.03,.07)))
    try:return _solve(hum,pose,'l',target,clamp=True,margin=.08)
    except ValueError:return pose

def _maru_route():
    pts=[(-3.6,-2.7)]
    pts.append((_DX+_R,-2.7))
    for i in range(1,13):              # quarter arc: heading -x -> heading -z
        a=math.pi/2*i/12
        pts.append((_DX+_R-_R*math.sin(a),-2.7-_R+_R*math.cos(a)))
    pts+=[(_DX,-4.02),(_DX,-5.3)]
    cum=[0.0]
    for a,b in zip(pts,pts[1:]):cum.append(cum[-1]+math.hypot(b[0]-a[0],b[1]-a[1]))
    return pts,cum


# Maru's exit: yard -> service passage -> door in the alley's south wall.
_DX=(DOOR_X0+DOOR_X1)/2
_R=.62
_ROUTE,_CUM=_maru_route()

MARU_STOP=_CUM[-2]                     # threshold of the doorway
MARU_SPEED=1.45
_K=round((MARU_STOP/1.35-.05)*2)   # ~1.35 m cycle at 1.45 m/s: a hurried walk, not a scurry
MARU_STRIDE=MARU_STOP/(_K/2+.05)       # stop lands in double support, both feet down
MARU_T_STOP=MARU_STOP/MARU_SPEED+.225   # constant pace, .45 s settle into the stop
MARU_T_GO=MARU_T_STOP+.95               # the look back
MARU_T_IN=MARU_T_GO+1.05
DOOR_OPEN=(MARU_T_STOP-.95,.75)
DOOR_SHUT=(MARU_T_IN-.15,.55)
MARU_GONE = DOOR_SHUT[0] + DOOR_SHUT[1] + .12


def maru_distance(t_s):
    if t_s<=MARU_T_STOP-.45:return MARU_SPEED*t_s
    if t_s<=MARU_T_STOP:
        a=.45;tau=t_s-(MARU_T_STOP-a);v=MARU_SPEED*(MARU_T_STOP-a)
        return v+MARU_SPEED*(tau-tau*tau/(2*a))
    if t_s<=MARU_T_GO:return MARU_STOP
    return MARU_STOP+(_CUM[-1]-MARU_STOP)*travel(t_s*1000,MARU_T_GO*1000,(MARU_T_IN-MARU_T_GO)*1000)


def maru_speed(t_s):
    return (maru_distance(t_s+.02)-maru_distance(max(0,t_s-.02)))/.04 if t_s>0 else MARU_SPEED



def maru_route(dist):
    """Ground point + smoothed heading (tangent over +-.3 m: no 7.5 deg facets)."""
    p=route_at(dist)[0]
    a,b=route_at(dist-.3)[0],route_at(dist+.3)[0]
    if dist>_CUM[-1]-.3 or dist<.3:return p,route_at(dist)[1]
    return p,math.degrees(math.atan2(b[0]-a[0],b[2]-a[2]))


def route_at(dist):
    dist=max(0.0,min(_CUM[-1],dist))
    for i in range(len(_CUM)-1):
        if dist<=_CUM[i+1] or i==len(_CUM)-2:
            a,b=_ROUTE[i],_ROUTE[i+1];seg=max(1e-6,_CUM[i+1]-_CUM[i]);u=(dist-_CUM[i])/seg
            return (a[0]+(b[0]-a[0])*u,0.0,a[1]+(b[1]-a[1])*u),math.degrees(math.atan2(b[0]-a[0],b[1]-a[1]))


def door_open_k(t):
    t/=1000.0
    o=k(t*1000,DOOR_OPEN[0]*1000,DOOR_OPEN[1]*1000)
    return o*(1-k(t*1000,DOOR_SHUT[0]*1000,DOOR_SHUT[1]*1000))


def maru_pose(m,t):
    """-> pose, world pos, yaw for Maru at film time t (ms)."""
    ts=t/1000.0
    dist=maru_distance(ts)
    pos,yaw=maru_route(dist)
    pose,pelvis=gait(dist,MARU_STRIDE,m._scale,maru_speed(ts),'guard_arm',maru_route)
    # The look back: torso and head swing toward Biribel; planted feet stay put.
    look=k(t,MARU_T_STOP*1000-150,330)*(1-k(t,MARU_T_GO*1000-260,300))
    if look>0:
        pose['twist']=mix(pose['twist'],-34,look)
        pose['head_y']=mix(pose['head_y'],-62,look)
        pose['head_p']=mix(pose['head_p'],-2,look)
        pose['spine']=mix(pose['spine'],7,look)
    return guard_left_hand(m,pose),pos,yaw+pelvis


UC_RETREAT_START = 32300
UC_RETREAT_DURATION = 4800
UC_RETREAT_END = UC_RETREAT_START + UC_RETREAT_DURATION
UC_WITHDRAWAL_SHOT_END = UC_RETREAT_END + 900


def _uc_points():
    from cutscenes.m5harbour_art import (
        ROOF_EXIT_X,
        ROOF_EXIT_Z,
        STAIR_START_Z,
        STAIR_END_Z,
        STAIR_BOTTOM_Y,
    )

    return (
        UC,
        (-.55, 5.0, 27.60),
        (ROOF_EXIT_X, 5.0, ROOF_EXIT_Z - .40),
        (ROOF_EXIT_X, 5.0, STAIR_START_Z),
        (ROOF_EXIT_X, STAIR_BOTTOM_Y, STAIR_END_Z),
        (ROOF_EXIT_X, STAIR_BOTTOM_Y, 31.52),
    )


def _uc_length():
    pts = _uc_points()
    return sum(math.dist(a, b) for a, b in zip(pts, pts[1:]))


def _uc_exit_route(distance):
    points = _uc_points()
    lengths = [
        math.dist(a, b)
        for a, b in zip(points, points[1:])
    ]
    total = sum(lengths)

    def sample(d):
        d = max(0.0, min(total, d))
        for a, b, length in zip(points, points[1:], lengths):
            if d <= length:
                return v_lerp(a, b, d / length)
            d -= length
        return points[-1]

    position = sample(distance)
    before = sample(distance - .22)
    after = sample(distance + .22)

    return position, yaw_to(before, after)


def _uc_dim(retreat):
    """Interior lighting changes, without artificially fading him away."""
    from cutscenes.m5harbour_art import ROOF_EXIT_Z

    position, _ = _uc_exit_route(retreat)
    return .35 * k(position[2], ROOF_EXIT_Z, 1.50)

UC_STRIDE = .78   # short steps keep the stair descent within leg reach


def walking_pose(distance, t=0, wounded=False, scale=1.0):
    """Plant Ucilev's feet along the same route his body follows."""
    return gait(
        distance,
        UC_STRIDE,
        scale,
        1.35,
        route=_uc_exit_route,
        pelvis_on=False,
    )[0]

def state_at(t):
    t = max(0, min(DURATION_MS, float(t)))
    biri_yaw = yaw_mix(
        180, yaw_to(BIRI, UC) + 40, k(t, 7050, 2100),
    )
    lower = (
        .10 * k(t, *LOWER_DIP)
        + .90 * k(t, *LOWER_DROP)
    )
    # Descent runs to the stair landing before the cut back to Biribel.
    retreat = _uc_length() * travel(
        t, UC_RETREAT_START, UC_RETREAT_DURATION,
    )
    u_pos, route_yaw = _uc_exit_route(retreat)
    u_yaw = yaw_mix(
        yaw_to(UC, BIRI) + 40, route_yaw, k(t, 31700, 950),
    )
    return dict(
        t=t,
        biri_yaw=biri_yaw,
        door=door_open_k(t),
        maru_visible=t < MARU_GONE * 1000,
        uc_pos=u_pos,
        uc_yaw=u_yaw,
        uc_distance=retreat,
        lower=lower,
        # He stays rendered down the stairs; the enclosing walls
        # obscure him as he descends, so there is no visibility cutoff.
        uc_visible=9600 <= t,
    )


def _camera(t):
    """One harbour, with dialogue coverage on one side of the action axis."""
    ground_eye = (2.30, 1.72, 4.15)
    ground_target = v_add(BIRI, (0, 1.28, 0))

    # This position stays on the same side of the Biribel-Ucilev axis
    # as the ground dialogue cameras.
    roof_eye = (-.40, 6.55, 21.10)
    roof_target = v_add(UC, (0, 1.20, 0))

    if t < 3000:
        q = k(t, 0, 3000)
        return (
            v_lerp(
                (5.5, 2.5, -6.5),
                (4.9, 2.25, -6.1),
                q,
            ),
            (-1.9, 1.08, -1.75),
            55,
            'escape',
        )

    if t < 6200:
        q = k(t, 3000, 3200)
        eye = v_lerp(
            (-4.55, 1.60, -1.95),
            (-5.35, 1.55, -2.20),
            q,
        )
        pos, _ = maru_route(maru_distance(t / 1000.0))

        return (
            eye,
            v_add(pos, (0, .95, 0)),
            56,
            'alley',
        )

    if t < 9600:
        return ground_eye, ground_target, 40, 'threat'

    if t < 11800:
        # Establish the opposite-bank roof before cutting closer.
        return (
            (.15, 1.65, .65),
            roof_target,
            mix(26, 16, k(t, 9600, 2000)),
            'discovery',
        )

    if 13900 <= t < 17700 or 23000 <= t < 26700:
        # Identical position, framing and background on each return.
        return ground_eye, ground_target, 40, 'biribel'

    if t < 31600:
        # Identical roof coverage across all Ucilev dialogue shots.
        return roof_eye, roof_target, 46, 'ucilev'

    if t < UC_WITHDRAWAL_SHOT_END:
        # Follow the descent, then tilt up to the entrance while he
        # stays on the landing: he drops out of frame, geometry
        # provides the occlusion.
        from cutscenes.m5harbour_art import ROOF_EXIT_X, STAIR_START_Z
        q = k(t, 31600, 800)

        u_pos, _ = _uc_exit_route(
            _uc_length() * travel(
                t, UC_RETREAT_START, UC_RETREAT_DURATION,
            )
        )

        chase = v_add(u_pos, (0, 1.15, 0))
        target = v_lerp(roof_target, chase, q)
        target = v_lerp(
            target,
            (ROOF_EXIT_X, 6.60, STAIR_START_Z),
            k(t, UC_RETREAT_END, 900),
        )

        return (
            roof_eye,
            target,
            mix(46, 38, k(t, 31600, 3300)),
            'withdrawal',
        )

    # Same ground background as the earlier Biribel shots.
    return ground_eye, ground_target, 40, 'radio'


def _scene_mesh():
    from cutscenes.m5harbour_art import scene_meshes, finale_connections
    return scene_meshes() + finale_connections()


def _renderer(software=False):
    key='software' if software else 'auto'
    if key not in _cache:
        cls=SoftwareRenderer if software else Renderer
        r=cls(RW,RH,fog=(26,38,44),fog_start=32,fog_end=100)
        r.light=ENV_LIGHT
        for i,mesh in enumerate(_scene_mesh()):r.bake(mesh,tag='shadow_set_'+str(i))
        from cutscenes.m5harbour_art import water_base, world_shell
        r.bake(water_base(),tag='shadow_water_base')
        for i,wm in enumerate(world_shell()):r.bake(wm,tag='shadow_shell_'+str(i))
        _cache[key]=(r,pygame.Surface((RW,RH)))
    return _cache[key]


@lru_cache(maxsize=1)
def _radio_mesh():
    m=Mesh();m.add(box(.058,.10,.029,(45,57,65)))
    m.add(box(.043,.036,.005,(131,157,153),center=(0,.019,.017)))
    for y in (-.03,-.019,-.008):m.add(box(.042,.003,.006,(12,25,34),center=(0,y,.016)))
    m.add(box(.006,.11,.006,(27,38,45),center=(.023,.091,0)))
    return m


def _radio(r,hum,pose,pos,yaw,t,who):
    places,j,root=hum.pose_world(pose,pos,yaw)
    S=next(M for slot,key,M,org,gr,fb in places if slot==1)
    origin=v_add(root,m_apply(S,(-.125,.51,.167)))
    _dynamic(r,_radio_mesh(),S,origin)
    live=any(on<=t<off and sp==who for on,off,sp,txt in LINES)
    if live:
        led=box(.007,.007,.007,(218,177,90),emissive=True)
        _dynamic(r,led,S,v_add(origin,m_apply(S,(.013,.038,.019))))


def _water(r,t):
    from cutscenes.m5harbour_art import water_mesh
    _dynamic(r,water_mesh(t,motion=not reduced_motion()))


def _sky(buf, r, t):
    """Sky colour follows world elevation, not screen-space framing."""
    fog = r.fog
    zenith = (8, 16, 27)
    half_h = RH * .5

    for y in range(RH):
        # Centre-column camera ray, expressed in world coordinates.
        sy = (half_h - (y + .5)) / r.focal
        ray_y = r.fwd[1] + r.up[1] * sy
        elevation = ray_y / math.sqrt(1.0 + sy * sy)

        if elevation >= 0:
            p = max(0.0, min(1.0, elevation / .45))

            colour = tuple(
                round(mix(fog[i], zenith[i], p))
                for i in range(3)
            )
        else:
            # Consistent haze below the horizon across all shots.
            p = max(0.0, min(1.0, -elevation / .55))

            colour = tuple(
                round(fog[i] - (3, 4, 6)[i] * p)
                for i in range(3)
            )

        pygame.draw.line(
            buf,
            colour,
            (0, y),
            (RW, y),
        )


def _actors(r,st):
    b,u,m=actors();t=st['t']
    by,bp=aim_angles(BIRI,st['biri_yaw'],st['uc_pos'])
    seen=k(t,7050,1200)
    blower=mix(mix(.55,.05,k(t,9000,1100)),.45,k(t,33600,1500))
    bpose=armed_pose(b,t,blower,.9,aim=(by*seen,bp*seen),look=(by*seen,mix(2,bp,seen)))
    radio=k(t,35000,750)*(1-k(t,38200,1000))
    bpose['head_y']+=-8*k(t,35000,1000)+8*k(t,39500,1300)
    bpose['head_p']=mix(bpose['head_p'],12,radio)
    from cutscenes.m5harbour_art import actor_shadow, door_leaf, door_spill
    _dynamic(r,actor_shadow(b,bpose,BIRI,st['biri_yaw']))
    _dynamic(r,door_leaf(st['door']))
    _dynamic(r,door_spill(st['door']))
    if st['maru_visible']:
        mpose,mpos,myaw=maru_pose(m,t)
        _dynamic(r,actor_shadow(m,mpose,mpos,myaw,False))
    r.light=Light(direction=(-.65,.5,-.8),ambient=.65,diffuse=.55,sky=.08,tint=(1.11,1.03,.94))
    r.add_humanoid(b,bpose,BIRI,st['biri_yaw'])
    _radio(r,b,bpose,BIRI,st['biri_yaw'],t,'BIRIBEL')
    if st['maru_visible']:
        warm=st['door']*max(0.0,1-abs(route_at(maru_distance(t/1000))[0][2]+4.0)/1.6)
        cool,hot=(35,49,61),(190,128,72)
        col=tuple(int(mix(c,h,warm)) for c,h in zip(cool,hot))
        r.add_humanoid(m,mpose,mpos,myaw,rifle_on=False,tint=(col,mix(.12,.16,warm)))
        places,jm,root=m.pose_world(mpose,mpos,myaw,False)
        F=next(M for slot,key,M,org,gr,fb in places if slot==12)
        _dynamic(r,box(.091,.095,.10,(174,181,173)),F,jm['rhand'])
    places,j,root=b.pose_world(bpose,BIRI,st['biri_yaw'])
    S=_torso(places)
    back=math.cos(math.radians(st['biri_yaw']))<0
    chest=v_add(root,m_apply(S,(.09,.26,-.158 if back else .196)))

    hold=1-k(t,31700,950)
    def aim_from(src):
        uy,up=aim_angles(src,st['uc_yaw'],chest)
        nerve=0 if reduced_motion() else k(t,26700,1200)*(1-k(t,LASER_OFF,200))
        uy+=nerve*.05*math.sin(t*.0071);up+=nerve*.04*math.sin(t*.0093+1.3)
        return armed_pose(u,t,st['lower'],.28,aim=(uy*hold,up*hold),look=(uy*hold,up*hold))
    upose=aim_from(st['uc_pos'])
    _,ju0,_=u.pose_world(upose,st['uc_pos'],st['uc_yaw'])
    if ju0.get('muzzle') is not None:
        upose=aim_from(ju0['muzzle'])
    if st['uc_distance']>0:
        walk=walking_pose(st['uc_distance'],scale=u._scale)
        for name in (
            'lhip_p','rhip_p',
            'lhip_r','rhip_r',
            'lkn','rkn',
            'lift',
        ):upose[name]=walk[name]
    if st['uc_visible']:
        _dynamic(r,actor_shadow(u,upose,st['uc_pos'],st['uc_yaw']))
        dim = _uc_dim(st['uc_distance'])
        r.light = Light(
            direction=(-.4, .6, -.8),
            ambient=mix(.65, .16, dim),
            diffuse=mix(.58, .10, dim),
            sky=.06,
            tint=(mix(.94, .55, dim), mix(1.04, .62, dim), mix(1.13, .72, dim)),
        )
        ju=r.add_humanoid(u,upose,st['uc_pos'],st['uc_yaw'])
        _radio(r,u,upose,st['uc_pos'],st['uc_yaw'],t,'UCILEV')
    else:
        places,ju,root=u.pose_world(upose,st['uc_pos'],st['uc_yaw'])
    r.light=_frame_light(st['t'])
    mu=ju.get('muzzle');R=ju.get('rifle_m')
    dot=muzzle=None;power=k(t,LASER_ON,600)*(1-k(t,LASER_OFF,70))
    if power>0 and mu is not None and R is not None:
        d=v_norm(m_apply(R,(0,0,1)))
        muzzle=(mu[0]+d[0]*.26,mu[1]+d[1]*.26,mu[2]+d[2]*.26)
        n=v_norm((st['uc_pos'][0]-BIRI[0],0,st['uc_pos'][2]-BIRI[2]))
        dot,on_body=_laser_hit(muzzle,d,chest,n)
        if dot is not None:
            if on_body:_dynamic(r,box(.045,.034,.006,(242,62,42),emissive=True),S,dot,bias=-.06)
            else:_dynamic(r,box(.05,.004,.05,(242,62,42),emissive=True),M_IDENT,dot,bias=-.06)
    return dot,muzzle,power

def _grade():
    # Extremely restrained edge falloff. It never replaces actual 3D lighting.
    s=pygame.Surface((WIDTH,BOT-TOP),pygame.SRCALPHA)
    for x in range(0,70,2):
        a=round(18*(1-x/70)**2)
        pygame.draw.line(s,(0,5,12,a),(x,0),(x,BOT-TOP))
        pygame.draw.line(s,(0,5,12,a),(WIDTH-x-1,0),(WIDTH-x-1,BOT-TOP))
    return s


@lru_cache(maxsize=1)
def _fonts():
    path=resource_path('assets/fonts/IBMPlexMono-Regular.ttf')
    try:return pygame.font.Font(path,22),pygame.font.Font(path,13),pygame.font.Font(path,28)
    except (OSError,pygame.error):return pygame.font.SysFont('monospace',22),pygame.font.SysFont('monospace',13),pygame.font.SysFont('monospace',28)


def _subtitle(s,t):
    """Timeline-owned lines as a film subtitle in the bottom letterbox band.

    Shared renderer (``cutscenes.engine.draw_cinematic_subtitle``: font_dialogue,
    SPEAKER_COLORS accent, typewriter) so the finale reads like the rest of the
    game, but in the black band under the picture, never over faces or hands.
    The app paints the letterbox AFTER the scene, so this runs from
    ``draw_controls`` (post-letterbox), not from ``draw``. Lines auto-advance on
    the authored clock; ESC/ENTER are the only controls.
    """
    from cutscenes.engine import draw_cinematic_subtitle  # lazy: engine lazily imports this film
    for on,off,who,text in LINES:
        if on <= t < off:
            char_idx = min(len(text), max(0, int((t - on) / 50)))   # 50 ms per character
            draw_cinematic_subtitle(s, who, text, char_idx)
            break


def _clip_seg(r,a,b):
    """World segment a->b -> two WINDOW pixel points, near-plane clipped."""
    ca,cb=r.to_cam(a),r.to_cam(b);near=r.NEAR
    if ca[2]<=near and cb[2]<=near:return None

    def win_cam(c):
        return ((RW/2+c[0]/c[2]*r.focal)/RW*WIDTH,
                TOP+(RH/2-c[1]/c[2]*r.focal)/RH*(BOT-TOP))

    def win_world(p,c):
        q=r.project(p)
        if q is None:return win_cam(c)
        return (q[0]/RW*WIDTH,TOP+q[1]/RH*(BOT-TOP))

    if ca[2]<=near:
        f=(near-ca[2])/(cb[2]-ca[2]);ca=(ca[0]+(cb[0]-ca[0])*f,ca[1]+(cb[1]-ca[1])*f,near)
        return win_cam(ca),win_world(b,cb)
    if cb[2]<=near:
        f=(near-cb[2])/(ca[2]-cb[2]);cb=(cb[0]+(ca[0]-cb[0])*f,cb[1]+(ca[1]-cb[1])*f,near)
        return win_world(a,ca),win_cam(cb)
    return win_world(a,ca),win_world(b,cb)

def _laser_sight(s,r,dot,muzzle,t,power=None):
    """A real sniper laser over the upscaled frame: beam + hot impact core.

    Screen space AFTER the smoothscale (a centimetre-scale emissive patch alone
    blurs into a stray pixel). The beam is the 3D muzzle->mark segment, near
    clipped, so it streaks in from off-frame when the shooter is behind the
    lens and lands right on near and far framings alike. Depth-scaled impact
    mark; skipped off-frame/behind camera. Pure function of (dot,muzzle,t):
    the film stays deterministic.
    """
    lay=pygame.Surface((WIDTH,BOT-TOP),pygame.SRCALPHA)
    pulse=.7+.3*math.sin(t*.012)
    # ── beam: muzzle -> mark, layered glow tapering to a hot core ──
    if muzzle is not None:
        # Fades up with the reveal and down as Ucilev lowers the rifle.
        fade=power
        seg=_clip_seg(r,muzzle,dot) if fade>0 else None
        if seg is not None:
            (x0,y0),(x1,y1)=seg;y0-=TOP;y1-=TOP
            flick=.82+.18*math.sin(t*.05);a=int(150*fade*flick)
            for w,col in ((9,(255,52,38,a//5)),(5,(255,74,52,int(a*.42))),
                          (2,(255,132,96,int(a*.72))),(1,(255,226,202,min(255,int(a*1.4))))):
                if col[3]>0:pygame.draw.line(lay,col,(x0,y0),(x1,y1),w)
            # A continuous optical sight, not animated projectile beads.
            # Rain/haze makes the narrow red shaft visible; the hot core
            # remains attached to the rifle and its target.
            # Muzzle bloom so the beam reads as emitted, not pasted on.
            ma=int(95*fade)
            pygame.draw.circle(lay,(255,118,88,ma),(int(x0),int(y0)),4)
            pygame.draw.circle(lay,(255,232,206,min(255,ma*2)),(int(x0),int(y0)),2)
    # ── impact mark: halo + ring + hot core, only while it faces the lens ──
    p=r.project(dot);core=None
    if p is not None:
        sc=min(1.5,max(.55,4.0/max(.5,p[2])))
        sx=int(p[0]/RW*WIDTH);sy=int(TOP+p[1]/RH*(BOT-TOP))
        if 0<=sx<WIDTH and TOP<=sy<BOT:
            a=int(110*pulse*power);lx,ly=sx,sy-TOP
            # Stepped falloff (bright centre, soft edge): one flat disc read as
            # dim as the background here, the stack reads as bloom without
            # additive blowout (the _ko_glow rationale).
            for rr,aa in ((16,a//3),(11,a*2//3),(7,a)):
                pygame.draw.circle(lay,(255,50,32,aa),(lx,ly),round(rr*sc))
            pygame.draw.circle(lay,(255,90,60,a),(lx,ly),round(8*sc),2)
            core=(sx,sy,sc)
    s.blit(lay,(0,TOP))
    if core is not None and power>.5:
        sx,sy,sc=core
        pygame.draw.circle(s,(255,60,40),(sx,sy),max(3,round(5*sc)))
        pygame.draw.circle(s,(255,215,180),(sx,sy),max(1,round(2*sc)))


def _rain(s,t,view):
    if reduced_motion():return
    # Sparse deterministic screen-projected drizzle, NOT giant foreground streaks.
    # Rendered only inside the film; critical faces/hands remain clear.
    film=s.subsurface((0,TOP,WIDTH,BOT-TOP));overlay=pygame.Surface(film.get_size(),pygame.SRCALPHA)
    for i in range(74):
        x=(i*197+math.sin(i*1.4)*49-t*.021)%WIDTH
        y=(i*73+t*(.13+(i%4)*.012))%(BOT-TOP)
        a=22 if view in ('ucilev','biribel','radio') else 34
        pygame.draw.line(overlay,(113,152,173,a),(x,y),(x-2,y+5+(i%3)),1)
    film.blit(overlay,(0,0))


def prepare():
    """Warm static 3D, cast and typography before the app starts its clock."""
    _renderer();actors();_fonts();_grade()


def draw(s,t,force_software=False):
    """Production frame with clamped clock and stable software fallback."""
    st=state_at(t);t=st['t'];r,buf=_renderer(force_software)
    eye,target,fov,view=_camera(t)
    # Tiny camera breathing only; reduced motion gets the exact authored path.
    if not reduced_motion():eye=v_add(eye,(math.sin(t*.0008)*.006,math.sin(t*.0011)*.004,0))
    r.set_camera(eye,target,fov)
    # Lightning lifts the fog itself, so sky (which derives from r.fog),
    # distance haze and the struck light all move together; the cached
    # renderer gets its base fog back before the frame ends.
    fl=_bolt(t)*_flash_scale()
    base_fog=r.fog
    if fl>0:r.fog=tuple(round(mix(c,hot,fl)) for c,hot in zip(base_fog,(126,144,158)))
    _sky(buf,r,t);r.begin();r.add_static();r.light=_frame_light(t);_water(r,t);dot,muzzle,power=_actors(r,st)
    r.flush(buf);r.fog=base_fog
    clip=s.get_clip();s.set_clip(clip.clip(pygame.Rect(0,SCENE_TOP,WIDTH,SCENE_BOT-SCENE_TOP)))
    try:
        s.fill((0,0,0));s.blit(pygame.transform.smoothscale(buf,(WIDTH,BOT-TOP)),(0,TOP))
        if fl>0:
            veil=pygame.Surface((WIDTH,BOT-TOP),pygame.SRCALPHA)
            veil.fill((186,203,222,int(54*fl)));s.blit(veil,(0,TOP))
        if dot is not None:_laser_sight(s,r,dot,muzzle,t,power)
        _rain(s,t,view);s.blit(_grade(),(0,TOP))
        fade=_fade(t)
        if fade>0:
            veil=pygame.Surface((WIDTH,BOT-TOP),pygame.SRCALPHA)
            veil.fill((0,0,0,fade));s.blit(veil,(0,TOP))
    finally:s.set_clip(clip)
    # Subtitles are NOT drawn here: the app letterboxes after the scene, so
    # they go through draw_controls (see _subtitle).


def draw_controls(s,paused=False,confirm=False,t=None):
    """Post-letterbox layer: subtitle in the bottom band, hint in the top band."""
    if t is not None:_subtitle(s,t)
    font,small,big=_fonts()
    label='ESC PAUSE   |   ENTER SKIP'
    if paused:label='ESC RESUME   |   ENTER SKIP'
    # Top band keeps the bottom band free for two-line subtitles.
    img=small.render(label,True,(115,138,152));s.blit(img,(WIDTH-img.get_width()-26,SCENE_TOP-img.get_height()-16))
    if paused or confirm:
        veil=pygame.Surface((WIDTH,HEIGHT),pygame.SRCALPHA);veil.fill((2,8,16,165));s.blit(veil,(0,0))
        title='SKIP FINALE?' if confirm else 'PAUSED'
        img=big.render(title,True,(235,239,231));s.blit(img,((WIDTH-img.get_width())//2,HEIGHT//2-28))
        text='ENTER TO SKIP  /  ESC TO KEEP WATCHING' if confirm else 'ESC TO RESUME'
        img=small.render(text,True,(177,199,208));s.blit(img,((WIDTH-img.get_width())//2,HEIGHT//2+22))
