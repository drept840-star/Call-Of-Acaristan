"""Authored M5 ending set and distance-driven actor blocking.

No app or mission imports: the owning film passes its renderer/FX helpers.
"""
import math
from engine3d.core import (box, quad_xz, m_apply, rot_y, v_add, v_cross, v_dot, v_lerp,
                           v_mul, v_norm, v_sub)

MARU_PORTAL_X = 10.3
ROOF_DOOR_Z = 4.65
AIM_PITCH = 14.0
STAIR_RUN = .28
STAIR_DROP = .24
STAIR_COUNT = 8


def beat(t, start, length):
    k = max(0.0, min(1.0, (t - start) / length))
    return k * k * (3 - 2 * k)


def travel(t, start, duration):
    """Integrated trapezoidal speed: short acceleration, steady steps, stop."""
    u = max(0.0, min(1.0, (t - start) / duration))
    a = 0.12
    if u < a:
        d = u * u / (2 * a)
    elif u > 1 - a:
        d = 1 - a - (1 - u) ** 2 / (2 * a)
    else:
        d = u - a / 2
    return d / (1 - a)


def move_weight(t, start, duration):
    """Gait fades with the same acceleration/deceleration as travel()."""
    u = max(0.0, min(1.0, (t - start) / duration))
    return min(1.0, u / .12, (1.0 - u) / .12)


def maru_block(t):
    # Two straight legs separated by a planted turn at the doorway axis.
    along = 5.9 * travel(t, 100, 3000)
    inward = 3.8 * travel(t, 3500, 1850)
    return (4.4 + along, 0.0, .6 - inward), along + inward


def maru_yaw(t):
    return 90 + 90 * beat(t, 3100, 400)


def maru_move_weight(t):
    return max(move_weight(t, 100, 3000), move_weight(t, 3500, 1850))


def stair_height(distance):
    """Tread tops shared by the set and actor, relative to the roof."""
    first_edge = ROOF_DOOR_Z + .5 - STAIR_RUN / 2
    step = max(0, min(STAIR_COUNT - 1, math.floor((distance - first_edge) / STAIR_RUN)))
    return -step * STAIR_DROP


def ucilev_block(t, sniper, initial_yaw):
    sx, sy, sz = sniper
    approach = 4.10 * travel(t, 650, 2650)
    inside = 3.05 * travel(t, 4300, 1900)
    d = approach + inside
    turn = beat(t, 50, 550)
    signed = (0 - initial_yaw + 180) % 360 - 180
    yaw = initial_yaw + signed * turn
    # Reach arrives just BEFORE the leaf starts swinging (anticipation), holds
    # on the handle through the open, and lets go as he steps through.
    reach = beat(t, 3300, 300) * (1 - beat(t, 4300, 500))
    # The hut leads downstairs, not into a visible dead-end wall.
    return (sx, sy + stair_height(d), sz + d), yaw, d, reach


def stride(d, amp=1.0):
    # Distance-driven walk: one full cycle (2 steps) per 1.35 m, like the
    # M5 finale Maru gait. Knees flex in quadrature (cos) so the bend peaks
    # mid-swing when the leg passes through, not at full back extension -
    # the old sin-phased version bent the stance leg under load and swung
    # the leg through straight, which read as hurt/dragging.
    ph = d * math.tau / 1.35
    s = math.sin(ph)
    c = math.cos(ph)
    return dict(spine=4, body_r=0.8 * s * amp,
                lhip_p=26 * s * amp, rhip_p=-26 * s * amp,
                lkn=8 + 34 * max(0.0, -c) * amp,
                rkn=8 + 34 * max(0.0, c) * amp,
                lift=0.03 * abs(s) * amp)


def solve_hand(hum, pose, side, target):
    """Analytic two-link IK in the rig's placement coordinates (no draw calls)."""
    places, joints, _, _ = hum.placements(pose, rifle_on=False)
    shoulder = next(o for slot, key, m, o, ground, fb in places if slot == (4 if side == 'l' else 10))
    S = next(m for slot, key, m, o, ground, fb in places if slot == 1)
    sc2 = sum(S[i] ** 2 for i in (0, 3, 6))
    delta = tuple(a - b for a, b in zip(target, shoulder))
    x, y, z = (sum(S[j * 3 + i] * delta[j] for j in range(3)) / sc2 for i in range(3))
    ln2 = x*x + y*y + z*z
    elbow = math.acos(max(-0.985, min(0.999, (ln2 - .30**2 - .31**2) / (2*.30*.31))))
    # Right trigger hand can rise above the shoulder with the elbow below it.
    # Choose that folded branch rather than rotating the whole arm upside-down.
    q = -math.hypot(x, y) if y > 0 else math.hypot(x, y)
    pitch = math.atan2(z, q) - math.atan2(.31*math.sin(elbow), .30+.31*math.cos(elbow))
    roll = math.atan2(-x, -y) if q >= 0 else math.atan2(x, y)
    roll *= -1 if side == 'r' else 1
    return dict(pose, **{side+'sh_p': math.degrees(pitch), side+'sh_r': math.degrees(roll),
                         side+'el': math.degrees(elbow)})


def rifle_pose(hum, pitch, d=0.0, moving=0.0, t=None):
    """Bladed stance: stock outside the chest, both grips reachable.

    The previous shoulder-relative grip buried the butt through his vest.
    Trigger is forward of the body; the left shoulder turns toward the
    fore-end. Keep this clearance through the entire lowering motion.
    ``t`` adds a marksman's hold micro-motion - the rifle is never dead still
    over a 240 m lane, and a frozen gun reads as a stuck prop.
    """
    hold_p = hold_y = 0.0
    if t is not None:
        hold_p = math.sin(t * 0.0016) * 0.55 + math.sin(t * 0.0041 + 1.0) * 0.22
        hold_y = math.sin(t * 0.0011 + 0.6) * 0.7 + math.sin(t * 0.0035) * 0.25
    k = max(0.0, min(1.0, (pitch-AIM_PITCH)/(52-AIM_PITCH)))
    pose = dict(stride(d, moving), twist=55, head_y=-55, head_p=4, rifle_p=pitch + hold_p,
                rifle_y=hold_y)
    trigger = (.20, .56-.25*k, .38)
    pose = solve_hand(hum, pose, 'r', trigger)
    _, joints, R, _ = hum.placements(pose)
    target = tuple(a+b for a,b in zip(joints['rhand'], m_apply(R, (0, -.025, .24))))
    return solve_hand(hum, pose, 'l', target)


def patrol_carry(hum, d=0.0, moving=0.0):
    """Muzzle-down carry across the chest, both hands solved onto the gun.

    The reveal's lowered rifle floated over the vest with the trigger hand
    off the grip and the muzzle near his own chin. Patrol carry keeps the
    muzzle at the deck, the stock clear of the body, and a hand on every
    piece of furniture for the whole walk off the roof. ``lag_*`` is a
    pendulum on the carry: the gun swings a couple of degrees behind the
    stride instead of being welded to the spine.
    """
    ph = d * math.tau / 0.95
    lag_p = (math.sin(ph * 0.5) * 2.4 + math.sin(ph * 0.83 + 1.3) * 1.2) * moving
    lag_y = (math.sin(ph * 0.43 + 0.7) * 3.0 + math.sin(ph * 0.71) * 1.5) * moving
    pose = dict(stride(d, moving), twist=18, head_y=-6, head_p=3,
                rifle_p=50 + lag_p, rifle_y=-36 + lag_y)
    grip = (0.26, 0.46, 0.22)   # tuned: slanted across the chest, stock clear (_carry_tune)
    pose = solve_hand(hum, pose, 'r', grip)
    _, joints, R, _ = hum.placements(pose)
    guard = tuple(a + b for a, b in zip(joints['rhand'], m_apply(R, (0, -0.03, 0.34))))
    return solve_hand(hum, pose, 'l', guard)


def reveal_pose(hum, t):
    """Production lowering motion: preserve contact, not just endpoint poses.

    Interpolated joint angles do not preserve a two-hand grip. Re-solve the
    support arm against the moving weapon after blending and head acting.
    """
    from engine3d.rig import blend
    lift = beat(t, 900, 2200)
    lower = beat(t, 3400, 2600)
    pitch = (AIM_PITCH + (25 - AIM_PITCH) * lift) * (1 - lower) + 52 * lower
    fold = beat(t, 5200, 1600)
    pose = blend(rifle_pose(hum, pitch), patrol_carry(hum), fold)
    look = beat(t, 2600, 1200) * (1 - beat(t, 5600, 1200))
    away = beat(t, 5600, 1600)
    pose['head_p'] = pose.get('head_p', 0) * (1 - look) - 7 * look
    pose['head_y'] = pose.get('head_y', 0) * (1 - away) + 26 * away
    _, joints, R, _ = hum.placements(pose)
    grip = (0, -.025 - .005 * fold, .24 + .10 * fold)
    target = tuple(a+b for a,b in zip(joints['rhand'], m_apply(R, grip)))
    return solve_hand(hum, pose, 'l', target)


def radio_pose(hum, pose):
    """Place the receiver by this actor's ear, not in a generic arm pose."""
    places, _, _, _ = hum.placements(pose, rifle_on=False)
    _, _, H, neck, _, _ = next(p for p in places if p[0] == 2)
    ear = tuple(a + b for a, b in zip(neck, m_apply(H, (-.17, .12, .02))))
    return solve_hand(hum, pose, 'l', (ear[0], ear[1] - .06, ear[2]))


def door_reach(hum, pose, pos, yaw, target, weight):
    """Reach for the roof door. The previous version drove ONLY the left arm
    angles, which reads as a stick rotating from the shoulder - so the torso
    now leans and twists toward the handle and the head glances down at it,
    all on the same eased envelope as the hand (no pop in or out)."""
    if weight <= 0:
        return pose
    out = dict(pose)
    for k,v in (('spine',4.0),('twist',6.0),('head_p',4.0)):
        out[k]=pose.get(k,0)+v*weight
    _,joints,_,_=hum.placements(out,rifle_on=False)
    _,_,root=hum.pose_world(out,pos,yaw,rifle_on=False)
    local=m_apply(rot_y(-yaw),v_sub(target,root))
    # Anticipation/eased hand path, then a delayed wrist roll onto the lever.
    local=v_lerp(joints['lhand'],local,weight)
    out=solve_hand(hum,out,'l',local)
    out['lwr_p']=-12*weight
    out['lwr_r']=8*weight*weight
    return out


def door_handle(sx, sy, front, door):
    """World position of the handle riding the swinging leaf (roof_set's panel
    geometry). Let the solver chase this while the leaf opens and the hand
    stays on the hardware instead of teleporting to a fixed point."""
    R = rot_y(90.0 * door)
    hinge = (sx + .69, sy, front - .08)
    return v_add(hinge, m_apply(R, (-1.15, 1.26, -0.07)))


# ── secondary animation: idle life and blinking ──────────────────────────
def idle_pose(t, amp=1.0, seed=0):
    """Breathing, weight shift, posture settle. The secondary motion that
    keeps a standing actor from reading as a mannequin; rates sit far below
    the walk cycle so it never fights the primary action."""
    b = math.sin(t * 0.0021 + seed * 1.7)            # breath, ~3 s
    w = math.sin(t * 0.00061 + seed * 2.9)           # weight shift, ~10 s
    s = math.sin(t * 0.00097 + seed * 0.6)           # posture settle
    return dict(spine=1.5 * b * amp, spine_r=0.8 * w * amp,
                twist=1.2 * s * amp, head_p=0.7 * b * amp + 0.3 * s * amp,
                head_y=1.5 * w * amp, body_r=0.55 * w * amp)


def blink_at(t, seed=0):
    """0..1 eyelid closure: one quick blink every 3.4-5.2 s, offset per actor
    so a crowd never blinks in unison."""
    period = 3400.0 + 900.0 * (seed % 3)
    age = (t + seed * 1300.0) % period
    if age < 150.0:
        return math.sin(math.pi * age / 150.0) ** 0.8
    return 0.0


def add_blink_lids(r, hum, pose, pos, yaw, amount, rifle_on=False):
    """Billboarded skin lids over the eyes (the rig has no lid joints and no
    wrist/finger bones, so blinking is the one feature worth faking exactly).
    Only drawn while the head faces the camera; parked a hair in front of the
    eye plane and depth-biased so the painter keeps them over the face."""
    if amount <= 0.03:
        return
    places, _joints, root = hum.pose_world(pose, pos, yaw, rifle_on=rifle_on)
    hp = next((p for p in places if p[0] == 2), None)          # the head place
    if hp is None:
        return
    M, neck = hp[2], hp[3]
    # placements are BODY-LOCAL (only joints come back in world space), so the
    # head origin needs the pose_world root translation to reach the actor.
    neck = v_add(neck, root)
    to_cam = v_norm(v_sub(r.cam, neck))
    if v_dot(m_apply(M, (0.0, 0.0, 1.0)), to_cam) < 0.45:      # back of the head
        return
    up = m_apply(M, (0.0, 1.0, 0.0))
    up = v_norm(v_sub(up, v_mul(to_cam, v_dot(up, to_cam))))
    right = v_norm(v_cross(up, to_cam))
    skin = hum.spec.get("skin", (200, 170, 140))
    col = tuple(int(c * 0.88) for c in skin)                   # lids read darker
    hw, hh = 0.026, 0.017 * amount
    for side in (-1, 1):
        eye = v_add(neck, m_apply(M, (0.048 * side, 0.148, 0.122)))
        d = v_norm(v_sub(r.cam, eye))
        c = v_add(eye, v_mul(d, 0.013))
        quad = [v_add(c, v_add(v_mul(right, sx * hw), v_mul(up, sy * hh)))
                for sx, sy in ((1, 1), (-1, 1), (-1, -1), (1, -1))]
        # Negative bias wins the painter sort (the face decals carry +0.09 fb,
        # so the lid needs to ride a hair NIGHTER than the eye it covers).
        # NOT emissive: the scene light shades the lid exactly like the face
        # it lands on, so a closed eye reads as skin, not a bright patch.
        r.add_dynamic(quad, [((0, 1, 2), col, 2, 1, d, False),
                             ((0, 2, 3), col, 2, 1, d, False)], bias=-0.12)


# ── held props the rig cannot carry ──────────────────────────────────────
def _xform(mesh, B, origin):
    """Rigid-place a mesh: world = origin + B * local (B row-major 3x3)."""
    out = type(mesh)()
    out.verts = [v_add(origin, m_apply(B, v)) for v in mesh.verts]
    out.faces = mesh.faces
    return out


def handset_frame(hum, pose, pos, yaw):
    """Shared palm/receiver frame; receiver sits OUTSIDE the gripping fist."""
    places, joints, root = hum.pose_world(pose, pos, yaw, rifle_on=False)
    hp = next(q for q in places if q[0] == 2)
    M = hp[2]
    # Outside the left palm by 6 cm; not centred inside the skin box.
    origin = v_add(joints['lhand'], m_apply(M, (-.065, 0, .008)))
    return M, origin


def draw_handset(r, hum, pose, pos, yaw, t, base=None):
    B, origin = handset_frame(hum, pose, pos, yaw)
    for w,h,d,col,cy in ((.055,.060,.070,(52,50,47),.070),
                         (.035,.110,.044,(21,21,24),0),
                         (.055,.050,.075,(52,50,47),-.070)):
        m = _xform(box(w,h,d,col,center=(0,cy,0)),B,origin)
        r.add_dynamic(m.verts,[(f[0],f[1],f[2],f[3],None,f[4]) for f in m.faces])
    if base is not None:
        a = v_add(origin,m_apply(B,(0,-.10,0)))
        mid = v_add(v_lerp(a,base,.5),(0,-.20,0))
        prev = a
        for i in range(1,13):
            u=i/12
            p=v_add(v_add(v_mul(a,(1-u)**2),v_mul(mid,2*(1-u)*u)),v_mul(base,u*u))
            r.add_line3d(prev,p,(28,28,32),1,layer=2)
            prev=p


def draw_palms(r, hum, pose, pos, yaw):
    """M5 opt-in articulated wrists; legacy rigs keep their baked fists."""
    if not hum.spec.get('articulated_hands'):
        return
    from engine3d.core import m_mul, rot_x, rot_z
    places,joints,root=hum.pose_world(pose,pos,yaw,rifle_on=False)
    for side,slot in (('l',6),('r',12)):
        q=next(p for p in places if p[0]==slot)
        F=q[2]
        wrist=v_add(v_add(q[3],root),m_apply(F,(0,-.267,0)))
        M=m_mul(F,m_mul(rot_x(pose.get(side+'wr_p',0)),rot_z(pose.get(side+'wr_r',0))))
        col=hum.spec.get('glove') or hum.spec.get('skin',(190,154,122))
        palm=_xform(box(.078,.080,.080,col,center=(0,-.043,0)),M,wrist)
        r.add_dynamic(palm.verts,[(f[0],f[1],f[2],f[3],None,f[4]) for f in palm.faces])


def rain_surface(x,z):
    """Only exposed, horizontal collision surfaces of the ending set."""
    if -14 <= x <= 24 and -1.1 <= z <= 2.35:
        return .012
    # Roof footprint, excluding the covered stair hut and stair aperture.
    if -20 <= x <= -12 and 35.9 <= z <= 45.9:
        if -17.75 < x < -14.25 and z > 41.35:
            return None
        return 9.212
    return None


def wet_ground(r,t):
    """Rough wet sheen on the floor plane, not camera-facing light stickers.

    Flat-shaded renderer has no PBR roughness channel. Narrow broken patches
    approximate high roughness: dim sky reflection and warm practical streaks.
    """
    for x,z,y,width,length,col in ((2.6,.4,.018,.7,1.8,(65,53,38)),
                                  (10.3,.0,.020,.55,.8,(57,50,40)),
                                  (-16,40.1,9.223,.5,1.2,(56,53,46)),
                                  (4,-.5,.018,1.2,.7,(42,48,55)),
                                  (-18,38,9.223,1.0,.7,(44,49,56))):
        for i in range(7):
            zz=z+i*length/7
            dx=math.sin(i*2.7)*width*.25
            m=quad_xz(x-width/2+dx,zz,x+width/2+dx,zz+length/18,y,col,layer=2)
            r.add_dynamic(m.verts,[(f[0],f[1],f[2],f[3],None,f[4]) for f in m.faces])


def rifle_sling(r, hum, pose, pos, yaw, col=(30, 30, 33)):
    """A strap from the left shoulder to the stock: the gun is carried, not
    welded to the hand. Sags under its own weight between the two anchors."""
    places, joints, root = hum.pose_world(pose, pos, yaw, rifle_on=True)
    sh = next((p for p in places if p[0] == 4), None)              # left shoulder
    R = joints.get("rifle_m")
    if sh is None or R is None:
        return
    shoulder = v_add(sh[3], root)                                  # world space
    stock = v_add(joints["rhand"], m_apply(R, (0.0, -0.02, -0.46)))
    mid = v_lerp(shoulder, stock, 0.5)
    mid = (mid[0], mid[1] - 0.05, mid[2])
    for p, q in ((shoulder, mid), (mid, stock)):
        r.add_line3d(p, q, col, 2, layer=4)


_MASONRY = {}


def masonry(r, add, x0, x1, y0, y1, z, col, holes=()):
    """Visible staggered brick courses, cached as one mesh (both backends)."""
    from engine3d.core import Mesh
    key = (x0,x1,y0,y1,z,col,holes)
    m = _MASONRY.get(key)
    if m is None:
        m = box(x1-x0,y1-y0,.28,(37,35,33),center=((x0+x1)/2,(y0+y1)/2,z-.14),seg=1,skip=('back',))
        row = 0
        y = y0
        while y < y1:
            x = x0 - (.21 if row%2 else 0)
            while x < x1:
                a,b = max(x0,x+.012),min(x1,x+.412)
                c,d = y+.010,min(y1,y+.170)
                if b>a and d>c:
                    v = ((row*7+int(x*11))%7-3)*3
                    rgb = tuple(max(0,min(255,q+v)) for q in col)
                    xa,xb,ya,yb=max(x0,x),min(x1,x+.43),y,min(y1,y+.18)
                    # Non-overlapping coplanar patches. A large backing face
                    # sorted over smaller bricks in the software painter.
                    patches=((a,b,c,d,rgb),(xa,xb,ya,c,(37,35,33)),
                             (xa,xb,d,yb,(37,35,33)),(xa,a,c,d,(37,35,33)),
                             (b,xb,c,d,(37,35,33)))
                    for a0,b0,c0,d0,color in patches:
                        if b0>a0 and d0>c0:
                            rects=[(a0,b0,c0,d0)]
                            for hx0,hx1,hy0,hy1 in holes:
                                nxt=[]
                                for ax,bx,cy,dy in rects:
                                    lx,rx,ly,ry=max(ax,hx0),min(bx,hx1),max(cy,hy0),min(dy,hy1)
                                    if rx<=lx or ry<=ly:
                                        nxt.append((ax,bx,cy,dy))
                                    else:
                                        nxt.extend(q for q in ((ax,lx,cy,dy),(rx,bx,cy,dy),
                                                               (lx,rx,cy,ly),(lx,rx,ry,dy))
                                                   if q[1]>q[0] and q[3]>q[2])
                                rects=nxt
                            for ax,bx,cy,dy in rects:
                                m.face([(bx,cy,z+.008),(bx,dy,z+.008),(ax,dy,z+.008),(ax,cy,z+.008)],color,2)
                x += .43
            y += .18
            row += 1
        _MASONRY[key] = m
    add(r,m)


def window(r,add,x,y,z,w=1.2,h=1.5,lit=False):
    trim = (100,94,78)
    add(r,box(w+.16,h+.16,.13,trim,center=(x,y,z)))
    add(r,box(w,h,.04,(145,116,73) if lit else (28,48,59),center=(x,y,z+.08),emissive=lit))
    for dx in (-w/2,0,w/2):
        add(r,box(.055,h,.09,(58,66,63),center=(x+dx,y,z+.12)))
    add(r,box(w,.055,.09,(58,66,63),center=(x,y,z+.12)))
    add(r,box(w+.32,.14,.36,trim,center=(x,y-h/2-.13,z+.08)))


def quay_destination(r, t, add, spr, fx):
    """An open warehouse door in the escape shot, not a hidden box mouth.

    Camera sees the same entrance Maru actually crosses. Interior floor,
    lintel, jambs, open leaf and lights establish a traversable destination.
    Nearby brick/loading-bay details also stay readable behind Biribel.
    """
    from cutscenes import m5decal
    stone = (112,101,80)
    z = -1.25
    # Warehouse frontage with a real 1.44 m aperture at x=10.3.
    for x0,x1,y0,y1 in ((7.8,9.58,0,6),(11.02,14.8,0,6),(9.58,11.02,2.65,6)):
        masonry(r,add,x0,x1,y0,y1,z,(83,57,43),
                    holes=tuple((x-.61,x+.61,3.645,5.255) for x in (8.7,10.8,13.4)))
    for x in (9.53,11.07):
        add(r,box(.14,2.7,.35,stone,center=(x,1.35,z+.03)))
    add(r,box(1.75,.16,.38,stone,center=(10.3,2.68,z+.05)))
    add(r,box(7.3,.22,.55,stone,center=(11.3,6.0,z)))
    for x in (8.7,10.8,13.4):
        window(r,add,x,4.45,z+.08,w=1.05,h=1.45,lit=x==13.4)
    # Hollow, lit vestibule extends inward; no solid box across the opening.
    for x in (9.42,11.18):
        add(r,box(.18,2.65,4.4,(77,72,56),center=(x,1.325,-3.35),seg=1))
    add(r,box(1.95,.15,4.4,(49,48,41),center=(10.3,2.78,-3.35),seg=1))
    # The vestibule opens into a working storeroom, not a blank dead end.
    # Shelves stay outside the central 1.1 m walking/camera aisle.
    for x in (7.9,12.7):
        add(r,box(.22,3.4,5.8,(77,72,56),center=(x,1.7,-8.3),seg=1))
    add(r,box(5.0,3.4,.22,(73,77,62),center=(10.3,1.7,-11.2),seg=1))
    add(r,box(5.0,.16,5.8,(49,48,41),center=(10.3,3.45,-8.3),seg=1))
    add(r,quad_xz(7.95,-11.1,12.65,-5.5,.014,(91,78,55),seg=.6,layer=2))
    add(r,quad_xz(9.5,-5.55,11.1,-1.05,.014,(91,78,55),seg=.6,layer=2))
    # Entry shelving and electrical service: visible before Maru enters.
    for z1 in (-3.2,-4.6):
        for y in (.18,.85,1.52,2.19):
            add(r,box(.28,.06,.9,(60,69,66),center=(10.94,y,z1)))
        for dz in (-.43,.43):
            add(r,box(.035,2.3,.035,(83,89,78),center=(10.94,1.15,z1+dz)))
        for y in (.4,1.05,1.72):
            add(r,box(.21,.38,.46,(128,92,53),center=(10.94,y,z1)))
            add(r,box(.215,.045,.47,(59,50,36),center=(10.94,y+.09,z1)))
    add(r,box(.09,.58,.42,(72,86,84),center=(9.58,1.5,-2.8)))
    add(r,box(.035,1.3,.035,(103,109,95),center=(9.60,2.3,-2.8)))
    for z1 in (-2.0,-3.0,-4.0,-5.0):
        add(r,box(1.55,.005,.018,(58,57,47),center=(10.3,.023,z1)))
    # Storage racks, boxed supplies and pallets give the destination purpose.
    for x in (8.6,12.0):
        for z1 in (-6.5,-8.5,-10.3):
            for dz in (-.65,.65):
                for dx in (-.32,.32):
                    add(r,box(.05,2.6,.05,(64,82,78),center=(x+dx,1.3,z1+dz)))
            for y in (.2,1.0,1.8):
                add(r,box(.8,.075,1.4,(83,90,75),center=(x,y,z1)))
                for dz in (-.36,.36):
                    add(r,box(.6,.48,.56,(118,86,53),center=(x,y+.29,z1+dz)))
                    add(r,box(.055,.485,.565,(172,139,83),center=(x,y+.29,z1+dz)))
    for x in (9.1,11.5):
        add(r,box(.8,.14,.7,(110,83,49),center=(x,.08,-10.4)))
        add(r,box(.65,.55,.6,(97,113,105),center=(x,.42,-10.4)))
    for z1 in (-6.4,-9.3):
        add(r,box(.75,.08,.24,(239,202,139),center=(10.3,3.28,z1),emissive=True))
        spr(r,(10.3,3.2,z1),fx.glow((225,184,110),.85,intensity=.45))
    for z1 in (-2.8,-4.9):
        add(r,box(.5,.09,.18,(240,192,111),center=(10.3,2.56,z1),emissive=True))
        spr(r,(10.3,2.55,z1+.05),fx.glow((226,170,90),.65,intensity=.5))
    # Open steel leaf along the right jamb, handle and visible threshold.
    add(r,box(.08,2.58,1.43,(45,70,69),center=(11.1,1.29,-1.95)))
    add(r,box(.14,.08,.12,(167,157,129),center=(11.01,1.25,-2.35)))
    add(r,box(1.65,.06,.45,stone,center=(10.3,.015,-1.22)))
    add(r,box(.55,.22,.24,(220,177,108),center=(10.3,3.02,z+.17),emissive=True))
    spr(r,(10.3,3.0,z+.25),fx.glow((213,157,82),1.05,intensity=.5))
    spr(r,(10.3,.025,-.7),fx.wet_reflection((193,142,74),t,21,2.1,.95,.25))
    # Frontage props anchor this side of the world to the quay.
    add(r,box(.12,5.8,.12,(58,72,68),center=(14.35,2.9,z+.19)))
    for i in range(3):
        add(r,box(.7,.52,.65,(103,78,47),center=(12.1+i*.77,.26,z+.65)))
        for y in (.1,.4):
            add(r,box(.73,.06,.69,(46,43,34),center=(12.1+i*.77,y,z+.65)))
    m5decal.add(r,'posters',3,(8.65,1.75,z+.045),(.56,.78),facing='+z')
    # Near loading bay: reverse shot sees shutter/pipe; scope sees warm window.
    masonry(r,add,-5.0,5.8,0,5.8,-3.8,(93,62,46),
                holes=((-3.125,-.775,.2,2.9),(1.12,2.88,1.17,2.83),
                       (-4.63,-3.27,3.62,5.08),(-.28,1.08,3.62,5.08)))
    add(r,box(10.8,.36,.5,(103,95,79),center=(.4,.18,-3.68),seg=1))
    add(r,box(2.35,2.7,.15,(30,58,62),center=(-1.95,1.55,-3.56)))
    for i in range(13):
        add(r,box(2.30,.055,.045,(58,89,89),center=(-1.95,.32+i*.19,-3.46)))
    add(r,box(2.55,.16,.34,stone,center=(-1.95,2.99,-3.48)))
    window(r,add,2.0,2.0,-3.57,w=1.6,h=1.5,lit=True)
    window(r,add,-3.95,4.35,-3.66,w=1.2,h=1.3)
    window(r,add,.4,4.35,-3.66,w=1.2,h=1.3)
    add(r,box(.09,5.6,.11,(49,73,72),center=(.15,2.8,-3.43)))
    add(r,box(.32,.58,.12,(95,105,94),center=(.15,1.38,-3.34)))
    add(r,box(.32,.16,.25,(228,179,98),center=(-2.0,3.38,-3.40),emissive=True))
    spr(r,(-2.0,3.38,-3.27),fx.glow((220,163,81),.8,intensity=.4))
    m5decal.add(r,'posters',1,(.86,1.60,-3.50),(.57,.8),facing='+z')
    for x in range(-12,15,2):
        add(r,box(.025,.01,10.5,(52,52,49),center=(x,.008,-2.65)))


_EAST_MASONRY = {}


def east_quay(r, t, add, spr, fx):
    """Close the east-facing tracking sightline with real connected geometry.

    The old quay stopped at x=14: tracking at 2200..3100 ms looked straight
    off that edge. This is a waterfront loading court, not a camera backdrop.
    """
    from engine3d.core import Mesh
    add(r,quad_xz(14,-8,26,2.6,0,(28,28,34),seg=2))
    add(r,box(12,.25,.3,(44,44,50),center=(20,.05,2.75)))
    for x in (18,22,26):
        add(r,box(.06,.9,.06,(56,58,62),center=(x,.45,2.48)))
    add(r,box(12,.06,.06,(64,66,70),center=(20,.88,2.48)))
    # Continue the frontage beyond the formerly visible end of the set.
    masonry(r,add,14.8,24,0,6,-1.25,(83,57,43))
    for x in (16.3,19.2,22.1):
        window(r,add,x,4.45,-1.17,w=1.05,h=1.45,lit=x==19.2)
    add(r,box(9.3,.22,.55,(112,101,80),center=(19.4,6,-1.25)))
    # West-facing terminal warehouse: rotate authored brickwork by -90 deg.
    def west(rr,m):
        key=id(m)
        out=_EAST_MASONRY.get(key)
        if out is None:
            out=Mesh()
            out.verts=[(24-v[2],v[1],.8+v[0]) for v in m.verts]
            out.faces=list(m.faces)
            _EAST_MASONRY[key]=out
        add(rr,out)
    masonry(r,west,-5.8,1.4,0,8,0,(92,63,45))
    add(r,box(.5,.22,7.5,(112,101,80),center=(23.94,8.02,-1.4)))
    # Roller door, corrugations, pilasters, upper windows, drain and bay lamp.
    add(r,box(.10,2.7,2.45,(34,67,70),center=(23.91,1.4,.25)))
    for i in range(14):
        add(r,box(.055,.04,2.4,(68,98,96),center=(23.84,.15+i*.19,.25)))
    for z in (-1.06,1.56):
        add(r,box(.24,3.1,.17,(127,113,89),center=(23.82,1.55,z)))
    add(r,box(.26,.18,2.95,(127,113,89),center=(23.82,3.0,.25)))
    for z in (-4,-1.8,.5):
        add(r,box(.12,1.55,1.22,(103,98,82),center=(23.82,5.2,z)))
        add(r,box(.04,1.37,1.04,(151,119,75) if z==-1.8 else (28,48,59),
                    center=(23.74,5.2,z),emissive=z==-1.8))
        for dz in (-.52,0,.52):
            add(r,box(.06,1.4,.05,(58,66,63),center=(23.70,5.2,z+dz)))
        add(r,box(.07,.05,1.12,(58,66,63),center=(23.70,5.2,z)))
    add(r,box(.12,7.5,.12,(58,72,68),center=(23.69,3.75,1.9)))
    add(r,box(.22,.2,.6,(230,180,100),center=(23.64,3.45,.25),emissive=True))
    spr(r,(23.50,3.45,.25),fx.glow((222,162,79),1.0,intensity=.45))
    spr(r,(22.9,.025,.25),fx.wet_reflection((193,142,74),t,71,2.2,.7,.22))
    for x,z in ((17,-.65),(20,-.65)):
        add(r,box(.7,.6,.65,(105,80,49),center=(x,.3,z)))
    # A downstream bridge and its piers break the exposed river horizon.
    add(r,box(4,.42,31.6,(63,66,67),center=(42,3.2,18.7),seg=2))
    for z in (4,18.7,33.4):
        add(r,box(2.2,4.1,1.3,(47,51,54),center=(42,1.45,z)))
    for x in (40.1,43.9):
        add(r,box(.08,.08,31.6,(85,89,86),center=(x,4.0,18.7)))
        for z in range(4,35,3):
            add(r,box(.06,.85,.06,(71,77,76),center=(x,3.65,z)))
    for z in (7,23,33):
        add(r,box(.09,3.0,.09,(51,59,61),center=(41,4.8,z)))
        add(r,box(.32,.18,.26,(222,180,110),center=(41,6.35,z),emissive=True))
        spr(r,(40.8,6.35,z),fx.glow((205,156,92),.8,intensity=.3))


def bank(r, t, add, spr, fx):
    """A continuous embankment and authored warehouse silhouettes, not random blocks."""
    add(r, box(95,1.3,3,(32,36,40), center=(0,-.1,34), seg=4))
    add(r, box(95,.16,3.2,(54,58,59), center=(0,.64,34), seg=4))
    buildings = [(-32,10,8,(39,35,37)), (-6,12,12,(34,38,44)),
                 (9,12,7,(45,37,35)), (24,14,10,(33,37,42))]
    for bx,w,h,col in buildings:
        add(r, box(w,h,8,col, center=(bx,h/2+.65,45), seg=2))
        add(r, box(w+.25,.3,8.2,(52,52,51), center=(bx,h+.7,45), seg=2))
        for j in range(int(w/2)):
            x=bx-w/2+1+j*2
            add(r, box(.15,h,.08,(49,45,42), center=(x-1,h/2+.65,40.96)))
            for floor in range(1,int(h/2.2)):
                y=1.2+floor*2.15
                lit=(j+floor+int(bx))%5==0
                c=(112,94,65) if lit else (18,25,32)
                add(r, box(.8,1.1,.05,c, center=(x,y,40.94), emissive=lit))
                add(r, box(.95,.1,.16,(59,55,49), center=(x,y-.6,40.9)))
        add(r, box(.65,2,.65,(36,35,38), center=(bx+w*.27,h+1.55,46.2)))
        spr(r, (bx,-.56,37), fx.wet_reflection((96,82,62), t, int(bx)+50, 3.5, .65, .12))
    # Older residential blocks behind the sniper roof give it an urban horizon.
    for bx,w,h,z in ((-21,13,17,61),(-8,9,20,66)):
        add(r, box(w,h,7,(36,39,43),center=(bx,h/2,z),seg=2))
        add(r, box(w+.3,.35,7.3,(56,56,53),center=(bx,h,z)))
        for floor in range(2,int(h/2.4)):
            for j in range(int(w/2)):
                x=bx-w/2+1+j*2
                lit=(floor*3+j)%7==0
                add(r, box(.72,1.05,.04,(106,91,69) if lit else (18,25,32),
                            center=(x,floor*2.4,z-3.52),emissive=lit))
    # Side streets complete the horizon when coverage turns east/west.
    # Fixed world coordinates are shared by the river, roof and radio takes.
    for bx,z,w,h in ((-42,48,10,15),(38,44,12,16),(-35,68,9,23),(37,70,13,21)):
        add(r,box(w,h,9,(34,39,43),center=(bx,h/2,z),seg=2))
        add(r,box(w+.3,.3,9.3,(58,57,53),center=(bx,h+.1,z)))
        for floor in range(1,int(h/2.3)):
            for j in range(int(w/2)):
                x=bx-w/2+1+j*2
                lit=(floor+j)%6==0
                add(r,box(.85,1.15,.06,(126,104,70) if lit else (18,29,38),
                            center=(x,floor*2.3,z-4.55),emissive=lit))
    for i,h in enumerate((13,18,16,22,17,14,20,15,18)):
        x=-55+i*13
        add(r, box(11,h,7,(20,26,35), center=(x,h/2,77), seg=4))
        add(r, box(11.3,.28,7.3,(32,39,48), center=(x,h+.1,77)))


def roof_set(r, t, sniper, door, add, spr, fx):
    sx,sy,sz=sniper
    add(r, box(8,sy+.6,10,(31,31,36), center=(sx,sy/2-.3,sz+3.9), seg=2, skip=('top',)))
    hole_front = sz + ROOF_DOOR_Z + .5
    for x0,z0,x1,z1 in ((sx-4,sz-1.1,sx-.82,sz+8.9),
                          (sx+.82,sz-1.1,sx+4,sz+8.9),
                          (sx-.82,sz-1.1,sx+.82,hole_front),
                          (sx-.82,sz+7.6,sx+.82,sz+8.9)):
        add(r, quad_xz(x0,z0,x1,z1,sy+.012,(40,42,45),seg=.8,layer=2))
    for i in range(STAIR_COUNT):
        z = hole_front + i * STAIR_RUN
        y = sy - i * STAIR_DROP
        add(r, box(1.55,.12,STAIR_RUN,(52,53,49),center=(sx,y-.06,z)))
    for x in (-3.2,-1.6,1.6,3.2):
        add(r, box(.02,.014,9.8,(55,56,56), center=(sx+x,sy+.02,sz+3.9)))
    for x in (-4,4):
        add(r, box(.28,.65,10,(56,54,51), center=(sx+x,sy+.325,sz+3.9),seg=2))
    add(r, box(8,.45,.28,(57,54,50), center=(sx,sy+.225,sz-1.1),seg=2))
    front=sz+ROOF_DOOR_Z
    # Hollow stair-hut: jambs and lintel leave a 1.4 x 2.45 m clear aperture.
    for x in (-1.22,1.22):
        add(r, box(1.0,3.05,.32,(49,46,42), center=(sx+x,sy+1.525,front),seg=1))
        add(r, box(.24,3.05,3.1,(44,43,42), center=(sx+x*1.36,sy+1.525,front+1.45),seg=1))
    add(r, box(3.4,.6,.36,(64,60,52), center=(sx,sy+2.75,front)))
    add(r, box(3.65,.22,3.45,(67,64,56), center=(sx,sy+3.15,front+1.45)))
    add(r, box(3.4,3.05,.24,(18,22,26), center=(sx,sy+1.525,front+2.95)))
    for x in (-.73,.73):
        add(r, box(.09,2.48,.11,(89,86,75), center=(sx+x,sy+1.24,front-.18)))
    add(r, box(1.55,.1,.42,(73,71,63), center=(sx,sy+.035,front)))
    # Hinged panel rotates into the opening. No glowing card over a solid box.
    R=rot_y(90*door)
    hinge=(sx+.69,sy,front-.08)
    panel=box(1.38,2.44,.065,(41,51,54),center=(-.69,1.22,0))
    for w,h,d,c,p in [(1.22,.08,.025,(74,82,81),(-.69,2.27,-.045)),
                      (.14,.045,.055,(133,127,109),(-1.15,1.26,-.07))]:
        panel.add(box(w,h,d,c,center=p))
    verts=[tuple(a+b for a,b in zip(m_apply(R,v),hinge)) for v in panel.verts]
    r.add_dynamic(verts, [(f[0],f[1],f[2],f[3],None,f[4]) for f in panel.faces])
    add(r, box(.3,.14,.15,(226,187,120), center=(sx,sy+2.62,front-.22),emissive=True))
    spr(r, (sx,sy+2.62,front-.26),fx.glow((210,167,99),.9,intensity=.42))
    # Caged bulb inside the hut: motivates the doorway spill from outside and
    # keeps the interior take (camera looks out through the door) lit.
    add(r, box(.12,.09,.12,(255,226,170), center=(sx+.95,sy+2.25,front+1.15),emissive=True))
    spr(r, (sx+.95,sy+2.25,front+1.1),fx.glow((255,206,140),.8,intensity=.5))
    # The spill LIGHTS the set: a haze volume hanging under the bulb, a lit
    # deck patch inside the hut, and a warm pool on the roof outside the
    # aperture where the light actually lands (a floating halo alone reads as
    # an unmotivated sticker). Kept under the highlight so the actor stepping
    # through stays a readable silhouette, not a white-out.
    add(r, quad_xz(sx-1.05, front-0.05, sx+1.05, front+1.6, sy+.008,
                   (40, 28, 14), seg=.6, emissive=True))
    add(r, quad_xz(sx-1.15, front-1.75, sx+1.15, front-0.10, sy+.012,
                   (30, 21, 10), seg=.6, emissive=True))
    spr(r, (sx+.95, sy+2.05, front+1.15), fx.light_shaft((255, 206, 140), 2.05, .35, 1.1,
                                                         t, 7, intensity=.26))
    spr(r, (sx+.95, sy+1.55, front+1.15), fx.haze((255, 206, 140), 1.1, t, 7, intensity=.11))
    spr(r, (sx, sy+0.75, front-.45), fx.haze((226, 170, 90), 1.1, t, 8, intensity=.07))
    spr(r, (sx, sy+.03, front-.4), fx.wet_reflection((181,135,79),t,32,2.2,.65,.18))
    for x,z in ((-2.75,2.7),(2.7,6.8)):
        add(r, box(.9,.7,1.15,(45,48,50), center=(sx+x,sy+.35,sz+z)))
        add(r, box(1.1,.13,1.35,(64,65,63), center=(sx+x,sy+.76,sz+z)))
    for row in range(3):
        for col in range(3):
            add(r, box(.9,1.2,.04,(48,48,43) if (row+col)%4==0 else (17,24,29),
                        center=(sx-2.4+col*2.4,sy-2-row*2.2,sz-1.12)))
    add(r, box(.07,3.5,.07,(57,61,65),center=(sx+3.1,sy+1.75,sz+5.7)))
    add(r, box(.12,.12,.12,(162,40,35),center=(sx+3.1,sy+3.5,sz+5.7),emissive=True))
