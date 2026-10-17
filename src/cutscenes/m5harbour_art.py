"""Authored blocky harbour art for M5; canonical people and motion stay intact.
All details are editable engine3d meshes, not pasted screenshots. Practical
spill/contact shadows are baked world-space colour; no claim of ray tracing.
"""
from functools import lru_cache
import math
import random
import pygame
from engine3d import Mesh,box,prism,quad_xz,v_add,v_mul,v_cross,v_norm
from core.config import resource_path

PALETTE={'brick':(87,58,46),'mortar':(39,43,43),'stone':(87,96,92),
         'steel':(43,62,66),'iron':(24,36,40),'roof':(46,58,64),
         'warm':(226,164,83),'glass':(23,48,58)}

def colour(c,amount):return tuple(max(0,min(255,int(v+amount))) for v in c)

def spill(pos,base):
    """Practical lamps tint nearby actual surfaces before directional baking."""
    x,y,z=pos
    lights=((-5.45,2.75,-2.7,2.4,1.0),(-8.8,2.65,-2.7,1.8,.70),
            (4.7,2.3,-6.85,2.5,.45),(-5.4,6.3,25.9,2.7,.55))
    strength=0
    for lx,ly,lz,r,gain in lights:
        d=((x-lx)**2+(z-lz)**2+((y-ly)*.62)**2)/r**2
        strength+=math.exp(-d*1.2)*gain
    return tuple(min(255,int(base[i]+(104,57,17)[i]*strength)) for i in range(3))


def plane(m,o,u,v,w,h,c,em=False):
    p1=v_add(o,v_mul(u,w));p2=v_add(p1,v_mul(v,h));p3=v_add(o,v_mul(v,h))
    # Double-sided for tiny signs/decals; always on the actual surface plane.
    m.face((o,p3,p2,p1),c,2,True,em)


def masonry(axis,at,a0,a1,y0,y1,seed=0,base=None,cell=.55,reverse=False):
    """Cell-centred mortar and brick faces replace (not overlap) large wall faces.
    This avoids the reference painter's coplanar-average-depth checkerboard.
    """
    rng=random.Random(seed);base=base or PALETTE['brick'];m=Mesh()
    rows=max(1,round((y1-y0)/.22));rh=(y1-y0)/rows
    for row in range(rows):
        y=y0+row*rh;offset=cell*.5*(row%2);a=a0-offset
        while a<a1:
            lo=max(a0,a);hi=min(a1,a+cell);w=hi-lo
            if w>.018:
                c=colour(base,rng.randrange(-7,8));hh=rh-.018
                if axis=='x':o=(at,y,lo);u=(0,0,1);n=(1,0,0)
                elif reverse:o=(hi,y,at);u=(-1,0,0);n=(0,0,1)
                else:o=(lo,y,at);u=(1,0,0);n=(0,0,-1)
                center=v_add(o,v_add(v_mul(u,w/2),(0,rh/2,0)))
                plane(m,o,u,(0,1,0),w,rh,spill(center,colour(c,-17)))
                face_o=v_add(o,v_add(v_mul(u,.009),v_add((0,.009,0),v_mul(n,.012))))
                plane(m,face_o,u,(0,1,0),w-.018,hh,spill(center,c))
            a+=cell
    return m


# Maru's exit: a steel service door in the south alley wall, warm room behind.
DOOR_X0,DOOR_X1,DOOR_H,DOOR_Z=-9.52,-8.54,2.18,-4.2
DOOR_HINGE=(DOOR_X0,0.0,-4.20)
_ROOM_WARM=(150,96,55)


def door_room():
    """A closed service room, continuously joined to Maru's doorway."""
    m = Mesh()
    cx = (DOOR_X0 + DOOR_X1) / 2

    # Door frame and threshold.
    for x in (DOOR_X0 - .05, DOOR_X1 + .05):
        m.add(box(
            .10, DOOR_H + .08, .30, (52, 58, 56),
            center=(x, (DOOR_H + .08) / 2, DOOR_Z),
        ))

    m.add(box(
        DOOR_X1 - DOOR_X0 + .20, .10, .30, (52, 58, 56),
        center=(cx, DOOR_H + .05, DOOR_Z),
    ))
    m.add(box(
        DOOR_X1 - DOOR_X0 + .10, .06, .36, (78, 82, 72),
        center=(cx, -.03, DOOR_Z),
    ))

    # Complete floor, back wall, side walls and ceiling.
    x0, x1 = -10.85, -7.35
    back, front, h = -7.45, DOOR_Z, 2.85

    m.add(floor(x0, back, x1, front, .002, 710))

    m.add(box(
        x1 - x0 + .32, h, .20, (109, 77, 51),
        center=((x0 + x1) / 2, h / 2, back - .10),
        seg=.55,
    ))

    for x in (x0 - .10, x1 + .10):
        m.add(box(
            .20, h, front - back, (99, 74, 54),
            center=(x, h / 2, (back + front) / 2),
            seg=.55,
        ))

    m.add(box(
        x1 - x0 + .40, .18, front - back + .20, (69, 61, 48),
        center=((x0 + x1) / 2, h + .09, (back + front) / 2),
        seg=.65,
    ))

    # Furnishings stay outside Maru's walking path.
    m.add(box(
        1.65, .08, .40, (71, 53, 37),
        center=(cx, 1.35, back + .32),
    ))

    for x in (cx - .55, cx, cx + .55):
        m.add(box(
            .36, .32, .30, (117, 90, 57),
            center=(x, 1.55, back + .32),
        ))

    m.add(box(
        .012, .45, .012, (31, 33, 30),
        center=(cx, 2.60, -5.75),
    ))
    m.add(box(
        .12, .14, .12, (255, 211, 143),
        center=(cx, 2.32, -5.75),
        emissive=True,
    ))
    m.add(box(
        .50, 1.10, .40, (57, 64, 57),
        center=(x1 - .40, .55, -6.55),
    ))

    return m
def door_leaf(open_k):
    """Door leaf swung into the room; open_k 0 = shut, 1 = ~105 deg."""
    a=math.radians(105*open_k);w=DOOR_X1-DOOR_X0;hx,_,hz=DOOR_HINGE
    ux,uz=math.cos(a),-math.sin(a)          # along the leaf, hinge -> latch
    nx,nz=math.sin(a),math.cos(a)           # leaf normal, alley side
    m=Mesh()
    def quad(s0,s1,y0,y1,off,c):
        m.face(tuple((hx+ux*s+nx*off,y,hz+uz*s+nz*off)
                     for s,y in ((s0,y0),(s1,y0),(s1,y1),(s0,y1))),c,2,True)
    quad(.01,w-.01,.02,DOOR_H-.02,.025,(58,70,68))      # alley face
    quad(.01,w-.01,.02,DOOR_H-.02,-.025,(96,74,52))     # room face, warm-lit
    quad(.15,w-.12,1.0,1.06,.032,(120,122,104))         # push bar
    quad(.05,w-.05,.05,.32,.030,(76,86,82))             # kick plate
    quad(w-.16,w-.10,1.02,1.16,.034,(150,146,118))      # handle
    return m


def door_spill(open_k):
    """Warm light wedge on the alley floor through the opening (no ray tracing)."""
    m=Mesh()
    if open_k<=.02:return m
    k=min(1.0,open_k*1.4)
    w0,w1=DOOR_X0+.04,DOOR_X1-.04;z0=-4.06;z1=-4.06+1.9*k
    for i,(a,b,amt) in enumerate(((0,.35,1.0),(.35,.7,.62),(.7,1.0,.30))):
        za,zb=z0+(z1-z0)*a,z0+(z1-z0)*b
        spread=lambda f:.35*f
        c=tuple(int(base+(warm-base)*amt*k) for base,warm in zip((52,60,58),(176,122,70)))
        m.face(((w0-spread(a),.016,za),(w1+spread(a),.016,za),(w1+spread(b),.016,zb),(w0-spread(b),.016,zb)),c,2,True)
    # Bright core of the doorway itself (the lit room's glow on the threshold).
    m.face(((w0,.02,-4.06),(w1,.02,-4.06),(w1,.02,-4.18),(w0,.02,-4.18)),(214,158,96),2,True,True)
    return m


@lru_cache(maxsize=32)
def lettering(text,width):
    """Merge horizontal glyph runs into shallow world-space geometry."""
    try:font=pygame.font.Font(resource_path('assets/fonts/IBMPlexMono-Regular.ttf'),28)
    except (OSError,pygame.error):font=pygame.font.SysFont('monospace',28)
    surf=font.render(text,False,(255,255,255),(0,0,0));scale=width/max(1,surf.get_width());runs=[]
    for y in range(surf.get_height()):
        x=0
        while x<surf.get_width():
            if surf.get_at((x,y))[0]<128:x+=1;continue
            start=x
            while x<surf.get_width() and surf.get_at((x,y))[0]>=128:x+=1
            runs.append((start*scale,(surf.get_height()-y-1)*scale,(x-start)*scale,scale))
    return runs,surf.get_height()*scale


def text_mesh(text,o,u,width,c=(192,192,162)):
    m=Mesh();runs,h=lettering(text,width)
    for x,y,w,dy in runs:plane(m,v_add(o,v_add(v_mul(u,x),(0,y,0))),u,(0,1,0),w,dy,c)
    return m


def window_z(x,y,z,w,h,warm=False,seed=0):
    m=Mesh();frame=PALETTE['steel'];iron=PALETTE['iron']
    m.add(box(w+.14,h+.13,.08,iron,center=(x,y,z),skip=('front','back',)))
    # Several panes, with one dim unlit pane to avoid a uniform checkerboard.
    for ix in (-1,1):
        for iy in (-1,1):
            c=(183,133,68) if warm and (ix+iy+seed)%4 else (23,45,51)
            if not warm:c=(31+seed%6,55+seed%8,65+seed%5)
            m.add(box(w*.45,h*.46,.015,c,center=(x+ix*w*.25,y+iy*h*.25,z-.050),emissive=warm and c[0]>100,skip=('back','top','bottom','left','right')))
    for xx in (-w/2,0,w/2):m.add(box(.035,h+.055,.07,frame,center=(x+xx,y,z-.062)))
    for yy in (-h/2,0,h/2):m.add(box(w+.06,.032,.07,frame,center=(x,y+yy,z-.062)))
    m.add(box(w+.23,.07,.21,(96,106,103),center=(x,y-h/2-.07,z-.07)))
    return m


def puddle(x,z,w,d,y,seed=0,base=(68,88,94)):
    rng=random.Random(seed);m=Mesh()
    pts=((x-w*.46,y,z-d*.30),(x-w*.23,y,z-d*.54),(x+w*.32,y,z-d*.47),
         (x+w*.52,y,z-d*.06),(x+w*.31,y,z+d*.44),(x-w*.35,y,z+d*.40))
    m.face(pts,base,0,True)
    # Broken reflections follow the wet patch, not screen coordinates.
    for i in range(4):
        zz=z-d*.20+i*d*.14;xx=x-w*.27+rng.random()*w*.12
        m.add(quad_xz(xx,zz,xx+w*(.3+rng.random()*.25),zz+.012,y+.003,colour(base,13+i%2*5)))
    return m


def floor(x0,z0,x1,z1,y,seed=0,roof=False):
    rng=random.Random(seed);m=Mesh();size=1.55 if roof else 1.65
    base=PALETTE['roof'] if roof else (61,72,72)
    z=z0
    while z<z1:
        x=x0
        while x<x1:
            xx=min(x1,x+size);zz=min(z1,z+size*.72)
            c=spill(((x+xx)/2,y,(z+zz)/2),colour(base,rng.randrange(-4,5)))
            # Paired quads share a centre, so averaging cannot alternate the layers.
            m.add(quad_xz(x,z,xx,zz,y,colour(c,-9)))
            m.add(quad_xz(x+.012,z+.012,xx-.012,zz-.012,y+.006,c))
            x+=size
        z+=size*.72
    return m


def roof_column():
    """A stairwell corner pier, not a freestanding foreground obstruction."""
    m = Mesh()
    x, z = 2.20, ROOF_EXIT_Z
    concrete = (72, 82, 79)

    # Attached directly to the stairwell's right-front corner.
    m.add(box(
        .30, 2.55, .38, concrete,
        center=(x, 6.275, z),
        seg=.45,
    ))

    m.add(box(
        .38, .16, .46, (54, 64, 62),
        center=(x, 5.08, z),
    ))

    m.add(box(
        .38, .12, .46, (113, 120, 109),
        center=(x, 7.55, z),
    ))

    for y in (5.65, 6.30, 6.95):
        m.add(box(
            .305, .018, .018, (52, 63, 63),
            center=(x, y, z - .198),
        ))

    return m


@lru_cache(maxsize=1)
def scene_meshes():
    M=[];add=M.append;iron=PALETTE['iron'];steel=PALETTE['steel'];stone=PALETTE['stone']
    # NEAR QUAY: material-defined slabs, masonry face, fender and bollard assemblies.
    add(floor(-10,-13,10,4,0,503))
    # Below-deck structure belongs to the terrain depth layer.
    # Its land-facing underside must not draw over the paving.
    add(box(
        20, .6, .46, (39, 50, 53),
        center=(0, -.29, 4.0),
        seg=1.0,
        layer=0,
        skip=('front', 'bottom'),
    ))
    add(box(20,.075,.54,(132,136,120),center=(0,.018,4.0),seg=1.4))
    for x in range(-9,10,2):
        add(box(.014,.08,.55,(48,64,65),center=(x,.041,4.0)))
    for x in (-7,-4,4,8):
        m=Mesh();m.add(box(.44,.08,.50,(65,73,72),center=(x,.045,3.32)))
        m.add(prism([(-.14,0),(-.14,.20),(-.10,.28),(.10,.28),(.14,.20),(.14,0)],.24,(45,54,54),z0=-.12),t=(x,.08,3.32))
        m.add(box(.42,.065,.27,(97,107,100),center=(x,.30,3.32)))
        for xx in (-.17,.17):m.add(box(.03,.02,.03,(148,139,111),center=(x+xx,.098,3.15)))
        add(m)
        # Hanging rubber fender below the quay, facets kept deliberately blocky.
        # Below-deck fender: expose only its outward, river-facing surface.
        add(box(
            .60, .65, .18, (14, 25, 29),
            center=(x, -.57, 4.28),
            layer=0,
            skip=('front', 'left', 'right', 'top', 'bottom'),
        ))

        for xx in (-.24, .24):
            # Hanging chain below the edge.
            add(box(
                .065, .92, .05, (64, 64, 48),
                center=(x + xx, -.34, 4.37),
                layer=0,
                skip=('front', 'left', 'right', 'top', 'bottom'),
            ))

            # Only the small above-deck attachment uses the object layer.
            add(box(
                .065, .12, .05, (64, 64, 48),
                center=(x + xx, .06, 4.37),
            ))
    # Door wall follows original opening; service passage now has visual depth.
    for z,length in ((-4.85,1.7),(1.25,5.9)):
        add(box(.44,3.5,length,PALETTE['mortar'],center=(-6.05,1.75,z),seg=.9,skip=('right',)))
        add(masonry('x',-5.822,z-length/2,z+length/2,.2,3.3,seed=int((z+10)*10)))
        add(box(.53,.12,length,(112,112,93),center=(-6.05,3.46,z),seg=1))
    add(box(.46,1.08,2.65,PALETTE['mortar'],center=(-6.05,2.98,-2.7),seg=.7,skip=('right',)))
    add(masonry('x',-5.817,-4.025,-1.375,2.49,3.48,901))
    for z in (-4.04,-1.36):add(box(.28,2.44,.24,(91,94,83),center=(-5.91,1.22,z)))
    add(box(.48,.16,2.98,(117,117,97),center=(-5.98,2.47,-2.7)))
    add(box(.46,.065,2.86,(44,55,54),center=(-5.78,2.36,-2.7)))
    add(floor(-13,-4.0,-6,-1.4,0,515))
    # Passage keeps going left, with a visible turn beyond the character path.
    # South alley wall, cut for Maru's exit door (DOOR_X0..DOOR_X1, DOOR_H).
    x0,x1=DOOR_X0-.05,DOOR_X1+.05
    add(box(x0+12.35,3.0,.25,(41,47,42),center=((x0-12.35)/2,1.5,-4.2),seg=.9,skip=('back',)))
    add(box(-5.85-x1,3.0,.25,(41,47,42),center=((x1-5.85)/2,1.5,-4.2),seg=.9,skip=('back',)))
    add(box(x1-x0,3.0-DOOR_H,.25,(41,47,42),center=((x0+x1)/2,(3.0+DOOR_H)/2,-4.2),skip=('back',)))
    add(box(3.5,3.0,.25,(45,49,41),center=(-7.8,1.5,-1.20),seg=.8))
    add(masonry('z',-4.055,-12.35,x0,0,3.0,511,base=(62,62,47),reverse=True))
    add(masonry('z',-4.055,x1,-6.0,0,3.0,512,base=(62,62,47),reverse=True))
    add(masonry('z',-4.055,x0,x1,DOOR_H+.08,3.0,513,base=(62,62,47),reverse=True))
    add(door_room())
    for x in (-7.5,-10.4):
        add(box(.11,2.6,.11,(71,78,66),center=(x,1.3,-3.94)))
        add(box(.12,.12,2.4,(71,78,66),center=(x,2.64,-2.7)))
    add(box(.80,.10,.26,iron,center=(-8.8,2.74,-2.7)))
    add(box(.61,.035,.18,(237,175,86),center=(-8.8,2.69,-2.7),emissive=True))
    # Gate mounted at the north jamb, parked flat against the yard-side wall.
    # The opening stays clear; the leaf no longer projects into the quay.
    for z in (-3.98, -1.70):
        add(box(
            .14, 2.38, .14, steel,
            center=(-5.76, 1.19, z),
            seg=.55,
        ))

        # Mounting plates connect the frame to the masonry.
        for y in (.35, 1.95):
            add(box(
                .24, .18, .18, (63, 72, 67),
                center=(-5.83, y, z),
            ))

    add(box(
        .14, .10, 2.42, steel,
        center=(-5.76, 2.34, -2.84),
        seg=.55,
    ))

    # Full-size leaf opened 180 degrees along the existing brick facade.
    gx, za, zb = -5.63, -1.70, .40

    for z in (
        za,
        za + .525,
        za + 1.05,
        za + 1.575,
        zb,
    ):
        add(box(
            .065, 2.10, .065, (65, 78, 71),
            center=(gx, 1.17, z),
            seg=.55,
        ))

    for y in (.12, 1.12, 2.22):
        add(box(
            .075, .075, zb - za + .065, (74, 86, 78),
            center=(gx, y, (za + zb) / 2),
            seg=.55,
        ))

    brace = Mesh()
    brace.face(
        (
            (gx + .04, .18, za + .07),
            (gx + .04, .18, za + .17),
            (gx + .04, 2.16, zb - .07),
            (gx + .04, 2.16, zb - .17),
        ),
        (85, 95, 82),
        2,
        True,
    )
    add(brace)

    # Hinges visibly connect the open leaf to the northern jamb.
    for y in (.38, 1.96):
        add(box(
            .24, .12, .14, (118, 112, 84),
            center=(-5.73, y, za),
        ))

    # Retaining catch holds the leaf flat against the wall.
    add(box(
        .28, .12, .12, (112, 110, 84),
        center=(-5.71, 1.12, zb - .10),
    ))
    # Physical fixture with brackets; warm spill is in surrounding material cells.
    add(box(.25,.18,.86,iron,center=(-5.66,2.79,-2.7)))
    add(box(.018,.095,.67,(246,189,105),center=(-5.525,2.75,-2.7),emissive=True))
    for z in (-3.06,-2.34):add(box(.30,.04,.045,steel,center=(-5.72,2.94,z)))
    # Service identifier; proper glyphs on a real plaque, no fake text.
    # Above the open gate, rather than hidden behind its bars.
    add(box(
        .17, .38, 1.42, (25, 37, 39),
        center=(-5.735, 2.70, -.12),
        seg=.05,
    ))

    add(text_mesh(
        'RIVER 03',
        (-5.615, 2.64, -.70),
        (0, 0, 1),
        1.16,
        (183, 184, 141),
    ))
    # Striped barrier end and conduit down wall.
    add(box(.07,2.66,.07,iron,center=(-5.74,1.36,2.68)))
    for y in (.42,1.52,2.56):add(box(.10,.055,.10,(101,101,82),center=(-5.72,y,2.68)))
    add(box(.16,.35,.26,(63,71,65),center=(-5.65,1.33,2.68)))
    # Rear loading-house: fills previously empty close-shot backgrounds.
    add(box(13.0,5.1,.60,PALETTE['mortar'],center=(.3,2.55,-7.30),seg=1.2,skip=('back',)))
    add(masonry('z',-6.988,-6.2,6.8,0,5.03,507,base=(67,51,43),cell=.62,reverse=True))
    for x in (-4.8,-1.3,2.2,5.5):
        # Back-side view: flip windows to face the near quay.
        w=window_z(0,0,0,1.5,1.18,warm=x in (-4.8,5.5),seed=round(x*2))
        from engine3d import rot_y
        add(Mesh().add(w,m=rot_y(180),t=(x,3.36,-6.94)))
        add(box(.13,4.7,.15,(84,78,63),center=(x-1.55,2.35,-6.90)))
    # Recessed loading shutter and lintel/canopy rather than a featureless wall.
    add(box(2.30,2.6,.15,(23,36,40),center=(1.0,1.3,-6.84)))
    for y in (.25,.52,.79,1.06,1.33,1.6,1.87,2.14,2.41):add(box(2.12,.032,.045,(56,71,71),center=(1.0,y,-6.739)))
    add(box(3.1,.10,1.1,(40,57,59),center=(1.0,2.80,-6.43)))
    add(box(3.2,.075,.12,(137,138,109),center=(1.0,2.76,-5.87)))
    add(box(.28,.18,.46,(33,45,43),center=(4.7,2.40,-6.77)))
    add(box(.26,.11,.018,(219,150,70),center=(4.7,2.33,-6.66),emissive=True))
    # Floor drains, restrained puddles and patched asphalt.
    for x,z,w,d in ((-3.7,1.4,1.4,.7),(2.1,.7,1.1,.40),(4.8,-3.6,1.6,.9),(-4.9,-.5,.7,.6)):
        add(puddle(x,z,w,d,.011,int((x+10)*17)))
    for z in (.52,.66,.80,.94,1.08):add(box(.47,.016,.03,(14,27,31),center=(-4.6,.013,z)))
    add(box(.54,.026,.74,(38,54,55),center=(-4.6,-.005,.80),skip=('top',)))
    # Pallet and small stacked cargo outside both actors' movement corridor.
    for x in (5.35,5.78,6.21):add(box(.13,.13,1.04,(73,60,43),center=(x,.07,-3.92)))
    for z in (-4.36,-4.13,-3.90,-3.67,-3.44):add(box(1.15,.07,.14,(111,90,57),center=(5.78,.16,z)))
    for x,y,z in ((5.78,.66,-3.94),(5.90,1.41,-3.93)):
        add(box(.93,.75,.76,(68,76,59),center=(x,y,z)))
        for yy in (y-.29,y+.29):add(box(.95,.055,.78,(117,117,89),center=(x,yy,z)))
        for xx in (x-.34,x+.34):add(box(.035,.72,.782,(37,54,50),center=(xx,y,z)))
    # Opposite bank warehouse: brick skin, glazed bays, foundation and roof cap.
    add(box(18,5.1,7,(37,48,52),center=(0,2.4,28.2),seg=1.6,skip=('front','top',)))
    add(masonry('z',24.64,-9,9,.1,4.93,517,base=(66,56,48),cell=.86))
    add(box(18,.19,.30,(121,118,96),center=(0,4.76,24.56),seg=1.4))
    for x in (-7.2,-3.8,-.4,3.0,6.4):
        add(window_z(x,2.74,24.58,1.30,1.85,warm=x in (-7.2,3.0),seed=round(x*3)))
        add(box(.22,4.55,.30,(81,81,67),center=(x+1.60,2.37,24.57),seg=.9))
        add(box(.45,.09,.43,(120,113,88),center=(x+1.6,.13,24.58)))
    add(roof_with_stair_opening())
    # Coping stones, joints, weather streaks on actual parapet faces.
    add(box(18,.57,.28,(49,61,65),center=(0,5.28,25.10),seg=1.3))
    for x in range(-9,9):
        add(box(.965,.09,.41,(113,122,113),center=(x+.5,5.59,25.10)))
        add(box(.94,.47,.012,(71+(x%3)*4,82+(x%3)*3,82),center=(x+.5,5.28,24.954)))
        if x%3==0:add(box(.065,.38,.018,(39,54,60),center=(x+.22,5.25,24.942)))
    add(roof_column())
    add(box(6.0,2.7,.36,(36,47,49),center=(5.1,6.35,30.4),seg=.9,skip=('front',)))
    add(masonry('z',30.208,2.1,8.1,5.0,7.64,559,base=(64,64,51),cell=.65))
    add(box(6.1,.10,.48,(96,110,105),center=(5.1,7.74,30.4)))
    # Rooftop plant: fan louvres and pipework, clear of the rifle withdrawal.
    add(box(1.3,.47,.80,(59,74,71),center=(-5,5.24,28.8)))
    for z in (28.49,28.62,28.75,28.88,29.01):add(box(1.12,.026,.044,(122,130,115),center=(-5,5.49,z)))
    add(box(.11,2.5,.11,(83,104,103),center=(3.1,6.25,30.15)))
    add(box(1.2,.12,.12,(89,106,103),center=(3.65,7.48,30.15)))
    for y in (5.2,6.1,7.1):add(box(.17,.05,.17,(138,131,95),center=(3.1,y,30.15)))
    add(puddle(-3.5,28.8,2.6,.63,5.012,593,base=(70,92,99)))
    add(box(.09,1.25,.09,steel,center=(-5.45,5.63,26.0)))
    add(box(.27,.22,.24,iron,center=(-5.45,6.27,26.0)))
    add(box(.018,.11,.18,(236,172,83),center=(-5.294,6.24,26.0),emissive=True))
    # Designed skyline: warehouses, tiers, cornices, windows, rooftop equipment.
    rng=random.Random(571)
    for i,(x,z,w,h) in enumerate(((-20,47,5.6,8.2),(-13,42,4.4,10.4),(-7.3,47,4.8,8.1),
            (-1.6,45,4.6,11.3),(4.0,49,5.7,9.5),(10.6,44,4.6,12.3),(17,48,6.5,8.9),
            (-26.5,50,6.0,10.0),(-33,55,7.0,12.0),(-39,60,7.5,9.0),
            (24,46,5.0,9.0),(30.5,52,6.5,11.0),(38,57,7.5,8.5),(45,62,8.0,10.5))):
        bcol=((45,49,48),(48,43,40),(41,52,55))[i%3]
        add(box(w,h,4.5,bcol,center=(x,h/2-1,z),seg=2.0))
        for y in (2.5,4.4,6.3,8.2):
            if y>h-1:continue
            add(box(w+.13,.10,4.7,colour(bcol,16),center=(x,y+.7,z)))
            for xx in (-w*.30,0,w*.30):
                add(window_z(x+xx,y,z-2.27,.65,.98,warm=rng.random()<.23,seed=i+round(y)))
        add(box(w+.3,.18,4.75,colour(bcol,24),center=(x,h-1,z)))
        add(box(.85,.75,.75,(27,40,45),center=(x-w*.25,h-.54,z+.35)))
        add(box(.40,1.55,.44,(64,63,51),center=(x+w*.25,h-.32,z+.7)))
    # Far silos and one restrained industrial tower, not random cubes.
    for x in (-28,-25.8):
        add(box(1.5,8.7,1.8,(33,47,52),center=(x,3.35,54),seg=2))
        for y in (1,3,5,7):add(box(1.54,.05,1.84,(57,66,66),center=(x,y,54)))
    # Baked diagonal grounding beneath fixtures/cargo, all in world space.
    add(quad_xz(5.35,-4.44,6.6,-2.65,.008,(24,38,41)))
    add(quad_xz(-5.9,28.42,-4.05,30.05,5.008,(27,40,48)))
    # Indexed vertices reduce CPU transform work without changing one polygon.
    result=[]
    for part in M:
        verts=[];index={};remap={}
        for i,v in enumerate(part.verts):
            if v not in index:index[v]=len(verts);verts.append(v)
            remap[i]=index[v]
        faces=[(tuple(remap[i] for i in inds),c,layer,ds,em) for inds,c,layer,ds,em in part.faces]
        result.append(Mesh(verts,faces))
    return tuple(result)


@lru_cache(maxsize=1)
def water_base():
    m=Mesh();rng=random.Random(590)
    for z in range(4,25,2):
        for x in range(-32,33,4):
            c=colour((18,35,43),rng.randrange(-3,4))
            m.add(quad_xz(x,z+.2,x+4,z+2.2,-.82,c))
    return m


def water_mesh(t,motion=True):
    """Broken warm window reflections and cool current lines, in river space."""
    if not motion:t=0
    m=Mesh()
    for row in range(27):
        z=4.5+row*.72
        for i in range(8):
            phase=i*1.7+row*.9+t*.00055
            x=-18+i*5+math.sin(phase)*.16;w=.42+((row*11+i*7)%13)*.075
            c=(30+row%3*2,48+row%3*3,56+row%3*3)
            m.add(quad_xz(x,z,x+w,z+.018,-.805,c))
    # Reflections under the warehouse's warm bays. Not a perfect mirror strip.
    for cx in (-7.2,3.0):
        for row in range(22):
            z=12.2+row*.54;fade=(row+1)/22
            xx=cx+math.sin(row*1.5+t*.0007)*.12
            w=.10+.45*fade+.14*math.sin(row*.7+t*.0004)
            c=(int(43+74*fade),int(44+32*fade),int(33+6*fade))
            m.add(quad_xz(xx-w/2,z,xx+w/2,z+.024+fade*.025,-.800,c))
    return m


def _hull(points):
    pts=sorted(set(points))
    if len(pts)<3:return pts
    def cross(o,a,b):return (a[0]-o[0])*(b[1]-o[1])-(a[1]-o[1])*(b[0]-o[0])
    lo=[];hi=[]
    for p in pts:
        while len(lo)>1 and cross(lo[-2],lo[-1],p)<=0:lo.pop()
        lo.append(p)
    for p in reversed(pts):
        while len(hi)>1 and cross(hi[-2],hi[-1],p)<=0:hi.pop()
        hi.append(p)
    return lo[:-1]+hi[:-1]


def actor_shadow(hum,pose,pos,yaw,rifle=True):
    """Projected posed-mesh silhouettes: real ground coordinates, not a sprite.
    A two-tone penumbra is deliberately stylized, not a shadow-map claim.
    """
    from engine3d import m_apply
    places,_,root=hum.pose_world(pose,pos,yaw,rifle)
    m=Mesh();floor_y=pos[1]
    for slot,key,M,org,ground,fb in places:
        if key in ('chest','chest2','chest3','face','face2','uarm_acc'):continue
        verts=hum._rifle.verts if key=='rifle' else hum._parts[key][0]
        projected=[]
        for v in verts:
            x,y,z=v_add(root,v_add(org,m_apply(M,v)));height=max(0,y-floor_y)
            projected.append((x+.44*height,z+.48*height))
        h=_hull(projected)
        if len(h)<3:continue
        cx=sum(x for x,z in h)/len(h);cz=sum(z for x,z in h)/len(h)
        for scale,col,layer,dy in ((1.045,(35,46,47),.21,.012),(1.0,(23,34,37),.22,.016)):
            poly=[(cx+(x-cx)*scale,floor_y+dy,cz+(z-cz)*scale) for x,z in h]
            m.face(poly,col,layer,True,True)
    return m


# Logical seal of the world shell: every rectangle a below-horizon ray must be able
# to land on. The first two document the authored set; the rest are world_shell().
# tools/m5_shadow_check.py ray-tests against this table, so art and test cannot drift.
SHELL_SEAL=(
    (-10,-13,10,4,0.0),          # quay deck (floor(...,503) in scene_meshes)
    (-32,4.2,36,26.2,-0.82),     # river slab (water_base)
    (-300,-300,300,-13,-0.06),   # south apron
    (-300,-13,-10,4.2,-0.06),    # west apron strip
    (10,-13,300,4.2,-0.06),      # east apron strip
    (-300,4.2,-32,26.2,-0.85),   # river extension west
    (36,4.2,300,26.2,-0.85),     # river extension east
    (-300,24.4,300,300,-0.02),   # far-bank ground
)

# Vertical seal faces, as (z, x0, x1, y0, y1): shallow rays thread between the far
# ground's south rim and the river's north edge, and only a wall face catches them.
SHELL_WALLS=(
    (24.28,-120,40,-1.6,0.12),   # far-bank embankment, front face
)


def _banded(xb,zb,y,base,rng,jit,practical=False):
    """Ground strip split into depth bands and x columns. The renderer fogs each
    face from its mean depth, so one giant quad would band; bands keep consecutive
    centroid depths ~10 m apart inside the fog zone and grow past it."""
    m=Mesh()
    for i in range(len(zb)-1):
        for j in range(len(xb)-1):
            c=colour(base,rng.randrange(-jit,jit+1))
            if practical:
                c=spill(((xb[j]+xb[j+1])/2,y,(zb[i]+zb[i+1])/2),c)
            m.add(quad_xz(xb[j],zb[i],xb[j+1],zb[i+1],y,c))
    return m


@lru_cache(maxsize=1)
def world_shell():
    """Sealing terrain around the authored set so no finale camera sees an edge.
    Layer-0 banded ground plus a layer-2 embankment and deck kerbs; every tone sits
    close to the renderer fog so the shell's own rim at +/-300 m (past fog_end)
    dissolves into haze. Nothing here is coplanar with the deck (y=0), the river
    (y=-0.82) or the warehouse roof (y=5): the painter sort and the projected actor
    shadows depend on that."""
    M=[];add=M.append
    asphalt=colour((61,72,72),-10)
    # Quad sizes stay modest on purpose: a face that straddles the camera plane
    # survives near-clipping as a frame-wide polygon and cannot be sphere-culled.
    add(_banded((-300,-40,-10,10,40,300),(-300,-125,-95,-65,-45,-30,-20,-13),
                -0.06,asphalt,random.Random(601),3,True))
    add(_banded((-300,-95,-65,-45,-30,-18,-10),(-13,-4.5,4.2),
                -0.06,asphalt,random.Random(602),3,True))
    add(_banded((10,22,45,300),(-13,-4.5,4.2),
                -0.06,asphalt,random.Random(602),3,True))
    river=random.Random(603)
    for zb in ((4.2,14,20),(20,26.2)):
        add(_banded((-300,-105,-70,-48,-32),zb,-0.85,(18,35,43),river,3))
        add(_banded((36,48,70,105,300),zb,-0.85,(18,35,43),river,3))
    add(_banded((-300,-70,-35,-14,14,35,70,300),
                (24.4,28.5,33,38,44,51,59,68,79,92,110,135,300),
                -0.02,(40,50,54),random.Random(605),4,True))
    # Far-bank embankment: the vertical face the water-to-ground step needs, or the
    # ground's south rim would show a sliver of river behind it. The wings seal the
    # same step far off axis, where one segment each is enough.
    add(box(160,1.72,.24,(39,50,53),center=(-40,-.74,24.40),seg=5,
            skip=('back','bottom','left','right'),cols={'top':(51,62,65)}))
    # Deck retaining kerbs over the deck/apron junction; the west gap is exactly the
    # service-passage opening, and the east run stops short of the quay coping.
    kerb=colour(PALETTE['stone'],-34)
    for w,d,cx,cz in ((20.0,.22,0,-13.11),(.22,9.0,-10.11,-8.5),
                      (.22,5.4,-10.11,1.0),(.22,16.7,10.11,-4.65)):
        add(box(w,.24,d,kerb,center=(cx,-.02,cz),seg=2.5,skip=('bottom',),
                cols={'top':(61,70,66)}))
    return tuple(M)


ROOF_EXIT_X = .725
ROOF_EXIT_Z = 29.05

STAIR_X0 = .12
STAIR_X1 = 1.33
STAIR_START_Z = ROOF_EXIT_Z + .30   # just behind the door wall (back face at 29.16)
STAIR_COUNT = 11
STAIR_RUN = .19
STAIR_RISE = .23          # was .20 -> STAIR_BOTTOM_Y = 2.47
STAIR_END_Z = STAIR_START_Z + STAIR_COUNT * STAIR_RUN    # 31.44
STAIR_BOTTOM_Y = 5.0 - STAIR_COUNT * STAIR_RISE          # 2.80
STAIR_LANDING_END = 31.60   # past the roof opening, under the slab


def stair_height(z):
    """Continuous foot/body guide along the physical staircase."""
    progress = max(
        0.0,
        min(float(STAIR_COUNT), (z - STAIR_START_Z) / STAIR_RUN),
    )
    return 5.0 - progress * STAIR_RISE


def roof_with_stair_opening():
    """Solid warehouse roof, with a real opening over the stairs."""
    m = Mesh()
    hole_end = 31.35
    rectangles = (
        (-9, 24.7, STAIR_X0, 31.7),
        (STAIR_X1, 24.7, 9, 31.7),
        (STAIR_X0, 24.7, STAIR_X1, STAIR_START_Z),
        (STAIR_X0, hole_end, STAIR_X1, 31.7),
    )

    for seed, (x0, z0, x1, z1) in enumerate(rectangles, 550):
        # Opaque structural roof. Its top sits below the paving,
        # avoiding coplanar faces and leaving the stairwell open.
        # The landing ceiling is thicker: it beats the painter depth
        # tie with Ucilev's hair on the final descent frames.
        thick = seed == 553
        m.add(box(
            x1 - x0,
            .39 if thick else .20,
            z1 - z0,
            (46, 58, 64),
            center=((x0 + x1) / 2, 4.795 if thick else 4.89, (z0 + z1) / 2),
            seg=1.0,
        ))
        m.add(floor(x0, z0, x1, z1, 5.0, seed, True))

    return m


def stair_mesh():
    """Solid stairs inside a closed shaft, open only at the roof entrance."""
    m = Mesh()
    width = STAIR_X1 - STAIR_X0
    cx = (STAIR_X0 + STAIR_X1) / 2
    base_y = STAIR_BOTTOM_Y - .20
    landing_end = STAIR_LANDING_END
    shaft_depth = landing_end - STAIR_START_Z

    # Solid treads. Small faces help the painter renderer sort them.
    for i in range(STAIR_COUNT):
        z0 = STAIR_START_Z + i * STAIR_RUN
        top = 5.0 - (i + 1) * STAIR_RISE
        height = top - base_y

        m.add(box(
            width, height, STAIR_RUN,
            (76, 84, 78),
            center=(
                cx,
                base_y + height / 2,
                z0 + STAIR_RUN / 2,
            ),
            seg=.20,
            cols={'top': (108, 115, 103)},
        ))

    # Bottom landing.
    m.add(box(
        width, .20, landing_end - STAIR_END_Z,
        (83, 91, 82),
        center=(
            cx,
            STAIR_BOTTOM_Y - .10,
            (STAIR_END_Z + landing_end) / 2,
        ),
        seg=.20,
    ))

    # Continuous side walls, joined to the rooftop enclosure at y=5.
    for x in (STAIR_X0 - .06, STAIR_X1 + .06):
        m.add(box(
            .12, 5.0 - base_y, shaft_depth,
            (55, 62, 56),
            center=(
                x,
                (5.0 + base_y) / 2,
                (STAIR_START_Z + landing_end) / 2,
            ),
            seg=.20,
        ))

    # Close the lower rear opening: the existing rooftop back wall
    # starts at y=5 and does not enclose this part of the shaft.
    m.add(box(
        width + .24, 5.0 - base_y, .10,
        (55, 62, 56),
        center=(
            cx,
            (5.0 + base_y) / 2,
            landing_end + .05,
        ),
        seg=.20,
    ))

    # Opaque underside, without covering the stair entrance.
    # Solid shaft bottom, overlapping the surrounding wall bases.
    m.add(box(
        width + .24,
        .16,
        shaft_depth + .12,
        (46, 53, 49),
        center=(
            cx,
            base_y - .04,
            (STAIR_START_Z + landing_end) / 2,
        ),
        seg=.20,
    ))

    # Seal the shaft beneath the rooftop entrance.
    # The doorway above roof level stays open.
    # The first tread begins behind this wall.
    front_thickness = .12
    m.add(box(
        width + .24,
        5.0 - base_y,
        front_thickness,
        (55, 62, 56),
        center=(
            cx,
            (5.0 + base_y) / 2,
            STAIR_START_Z - front_thickness / 2,
        ),
        seg=.20,
    ))

    return m

@lru_cache(maxsize=1)
def finale_connections():
    """Connected alley walls, warehouse boundaries and an actual roof exit."""
    parts = []
    add = parts.append
    wall = (47, 54, 51)
    stone = (98, 106, 96)

    # Close the gap between the service wall and rear loading house.
    # Both ends overlap existing walls, leaving no exposed background slit.
    add(box(
        .44, 5.1, 1.70,
        PALETTE['mortar'],
        center=(-6.05, 2.55, -6.50),
        seg=.55,
    ))

    # Brick-facing return, matching the rear loading-house material.
    add(masonry(
        'x',
        -5.817,
        -7.35,
        -5.65,
        0,
        5.03,
        714,
        base=(67, 51, 43),
    ))

    # Continuous coping over the new wall connection.
    add(box(
        .53, .12, 1.78,
        stone,
        center=(-6.05, 5.10, -6.50),
        seg=.55,
    ))

    # Close the west end and missing north side of Maru's alley.
    add(box(
        .30, 3.6, 3.30, wall,
        center=(-12.50, 1.8, -2.65), seg=.65,
    ))
    add(box(
        2.80, 3.6, .28, wall,
        center=(-10.95, 1.8, -1.20), seg=.65,
    ))
    add(masonry(
        'z', -1.355, -12.35, -9.55, 0, 3.55, 711,
        base=(65, 60, 48),
    ))

    # Join the alley paving to the doorway.
    add(floor(-12.35, -4.08, -6.0, -4.0, 0, 712))

    # Warehouse side returns give the quay a proper perimeter.
    add(box(
        .40, 5.2, 8.0, wall,
        center=(-12.55, 2.6, -8.2), seg=1.0,
    ))
    add(box(
        .40, 5.2, 16.8, wall,
        center=(10.30, 2.6, -4.6), seg=1.0,
    ))
    add(masonry(
        'x', 10.085, -13.0, 3.8, .12, 5.12, 713,
        base=(66, 55, 46),
    ))

    for x, depth, z in (
        (-12.55, 8.0, -8.2),
        (10.30, 16.8, -4.6),
    ):
        add(box(
            .62, .14, depth, stone,
            center=(x, 5.23, z), seg=1.0,
        ))

    # Rear and side parapets: the roof is no longer an open-edged platform.
    add(box(
        18.0, .66, .24, wall,
        center=(0, 5.33, 31.80), seg=1.0,
    ))
    add(box(
        18.1, .09, .36, stone,
        center=(0, 5.70, 31.80), seg=1.0,
    ))

    for x in (-9.0, 9.0):
        add(box(
            .24, .66, 6.60, wall,
            center=(x, 5.33, 28.50), seg=1.0,
        ))
        add(box(
            .36, .09, 6.70, stone,
            center=(x, 5.70, 28.50), seg=1.0,
        ))

    # Rooftop stair-access building, connected to the existing plant wall.
    x0, x1 = -.60, 2.10
    z0, z1 = ROOF_EXIT_Z, 31.35
    y0, y1 = 5.0, 7.55
    d0, d1, door_top = .20, 1.25, 7.18
    shell = (61, 65, 57)

    # Front wall is genuinely cut around the doorway.
    for a, b in ((x0, d0), (d1, x1)):
        add(box(
            b - a, y1 - y0, .22, shell,
            center=((a + b) / 2, (y0 + y1) / 2, z0),
            seg=.45,
        ))

    add(box(
        d1 - d0, y1 - door_top, .22, shell,
        center=(ROOF_EXIT_X, (door_top + y1) / 2, z0),
        seg=.45,
    ))

    for x in (x0 - .10, x1 + .10):
        add(box(
            .20, y1 - y0, z1 - z0, shell,
            center=(x, (y0 + y1) / 2, (z0 + z1) / 2),
            seg=.55,
        ))

    add(box(
        x1 - x0 + .40, y1 - y0, .20, (64, 59, 48),
        center=((x0 + x1) / 2, (y0 + y1) / 2, z1),
        seg=.55,
    ))
    add(box(
        x1 - x0 + .50, .16, z1 - z0 + .35, stone,
        center=((x0 + x1) / 2, y1 + .08, (z0 + z1) / 2),
        seg=.55,
    ))

    # Open door sits along the inside wall, clear of Ucilev's path.
    add(box(
        .055, 2.14, 1.02, (43, 57, 53),
        center=(d0 + .04, 6.07, z0 + .58),
        seg=.4,
    ))

    # Steel portal tied to the masonry opening.
    for x in (d0, d1):
        add(box(
            .09, 2.22, .16, (43, 57, 53),
            center=(x, 6.11, z0 - .07),
            seg=.45,
        ))

    add(box(
        d1 - d0 + .10, .10, .16, (43, 57, 53),
        center=(ROOF_EXIT_X, 7.18, z0 - .07),
        seg=.45,
    ))

    # Low threshold, flush with the rooftop landing.
    add(box(
        d1 - d0 + .10, .035, .36, (100, 108, 96),
        center=(ROOF_EXIT_X, 5.0175, z0),
        seg=.45,
    ))

    # Exterior light beside the entrance.
    add(box(
        .24, .26, .18, (24, 36, 40),
        center=(1.65, 6.99, z0 - .18),
    ))

    add(box(
        .18, .15, .025, (239, 185, 106),
        center=(1.65, 6.99, z0 - .285),
        emissive=True,
    ))

    # Interior landing light.
    add(box(
        .12, .12, .65, (231, 184, 116),
        center=(ROOF_EXIT_X, 7.30, z0 + 1.30),
        emissive=True,
    ))

    # The stairwell must read as a lit interior through the doorway, not a
    # black slot: a warm lamp panel on the back wall (visible from the
    # roof cameras) and its spill pooled on the landing inside the door.
    add(box(
        .46, .30, .04, (240, 196, 116),
        center=(ROOF_EXIT_X, 6.62, z1 - .13),
        emissive=True,
    ))
    add(quad_xz(
        ROOF_EXIT_X - .50, z0 + .06, ROOF_EXIT_X + .50, z0 + .27,
        5.03, (88, 64, 32), emissive=True,
    ))

    # Exterior detail so the bulkhead's flat front is not a bare plane in
    # close-up: a louvred vent and a conduit run beside the door.
    add(box(
        .52, .42, .05, (28, 36, 38),
        center=(1.68, 6.35, z0 - .13),
    ))
    for vy in (6.24, 6.35, 6.46):
        add(box(
            .46, .03, .02, (56, 64, 60),
            center=(1.68, vy, z0 - .155),
        ))
    add(box(
        .07, 2.50, .07, (52, 60, 58),
        center=(2.02, 6.25, z0 - .15),
    ))

    add(stair_mesh())

    return tuple(parts)
