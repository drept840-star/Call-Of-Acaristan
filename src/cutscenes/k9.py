"""K-9 armory pickup: one continuous, deterministic, software-safe take.

The three legacy scene names address adjacent sections of the same clock.
No gameplay state, input, audio, or global RNG is touched by drawing. Art is
procedural, matching the campaign's editable sprite/illustration pipeline.
"""
from functools import lru_cache
import math
import random

import pygame
from core.config import WIDTH, HEIGHT, SCENE_TOP, SCENE_BOT, font_terminal, font_terminal_small
from engine.text import T as _T  # RPE6 Phase 4 text table

WALL_MS = 850
GRAB_MS = 2150
READY_MS = 1800
TOTAL_MS = WALL_MS + GRAB_MS + READY_MS


def _clamp(v):
    return max(0.0, min(1.0, float(v)))


def _ease(v):
    v = _clamp(v)
    return v * v * v * (v * (v * 6 - 15) + 10)


def _lerp(a, b, p):
    return a + (b - a) * p


def _mix(a, b, p):
    return (_lerp(a[0], b[0], p), _lerp(a[1], b[1], p))


def _local(point, pose):
    """Same pivot/rotation for weapon, fingers, controls, and contact points."""
    x, y, scale, angle = pose
    rad = math.radians(angle)
    ca, sa = math.cos(rad), math.sin(rad)
    px, py = point
    return (x + scale * (px * ca + py * sa),
            y + scale * (-px * sa + py * ca))


def _pose(ms):
    g = ms - WALL_MS
    # Nothing leaves the rack until BOTH hands have made contact at 560 ms.
    lift = _ease((g - 610) / 410)
    approach = _ease((g - 980) / 900)
    ready = max(0.0, g - GRAB_MS)
    lower = _ease((ready - 1380) / 420)
    recoil = 0.0
    if 990 < ready < 1160:
        q = (ready - 990) / 170
        recoil = math.sin(q * math.pi * 3) * math.exp(-q * 4) * 2
    return (500 + 16 * approach + 16 * lower,
            321 - 33 * lift + 127 * approach + 42 * lower + recoil,
            1.25 + 0.55 * approach,
            6.0 * lift - 13.0 * approach - 3.0 * lower)


@lru_cache(maxsize=1)
def _background():
    """Cached physical armory: cool concrete, stamped steel, warm task light."""
    s = pygame.Surface((WIDTH, HEIGHT))
    s.fill((5, 8, 10))
    for y in range(SCENE_TOP, SCENE_BOT):
        p = (y - SCENE_TOP) / (SCENE_BOT - SCENE_TOP)
        pygame.draw.line(s, (int(22 - 10 * p), int(29 - 10 * p), int(32 - 11 * p)), (0, y), (WIDTH, y))
    rng = random.Random(907)
    for _ in range(6000):
        x, y = rng.randrange(WIDTH), rng.randrange(SCENE_TOP, SCENE_BOT)
        c = rng.choice([(25, 32, 34), (15, 21, 24), (30, 36, 36)])
        s.set_at((x, y), c)
    for x in (152, 846):
        pygame.draw.line(s, (6, 12, 15), (x, SCENE_TOP), (x, SCENE_BOT), 3)
        pygame.draw.line(s, (34, 41, 42), (x + 4, SCENE_TOP), (x + 4, SCENE_BOT), 1)
    pygame.draw.line(s, (7, 13, 17), (0, 482), (WIDTH, 482), 3)
    # Peripheral lockers, not distracting repeated weapons.
    for x in (-72, 871):
        pygame.draw.rect(s, (11, 19, 24), (x, 177, 193, 418), border_radius=3)
        pygame.draw.rect(s, (38, 48, 51), (x, 177, 193, 418), 2, border_radius=3)
        for y in range(207, 259, 8):
            pygame.draw.line(s, (5, 11, 15), (x + 23, y), (x + 164, y), 3)
            pygame.draw.line(s, (44, 51, 51), (x + 23, y + 3), (x + 164, y + 3))
        pygame.draw.rect(s, (51, 56, 53), (x + 138, 367, 6, 31), border_radius=2)
        pygame.draw.circle(s, (9, 14, 16), (x + 141, 408), 4)
    # Light falloff is behind the rack and gun, never fake bloom on controls.
    light = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
    for r in range(380, 25, -14):
        a = int(2 + 7 * (1 - r / 380))
        pygame.draw.ellipse(light, (226, 195, 120, a), (500 - r, 149 - r * .38, r * 2, r * 1.5))
    s.blit(light, (0, 0))
    # Rack dimensions align with the mounted weapon and all clip locations.
    rack = pygame.Rect(216, 179, 568, 300)
    pygame.draw.rect(s, (4, 8, 11), rack.move(8, 13).inflate(8, 6), border_radius=5)
    pygame.draw.rect(s, (49, 59, 59), rack, border_radius=4)
    pygame.draw.rect(s, (12, 20, 24), rack.inflate(-8, -8), border_radius=2)
    pygame.draw.rect(s, (69, 76, 69), (221, 183, 558, 3))
    for y in range(226, 451, 21):
        for x in range(242, 767, 22):
            pygame.draw.circle(s, (6, 12, 16), (x, y), 2)
            s.set_at((x, y + 2), (34, 43, 45))
    for y in (275, 381):
        pygame.draw.rect(s, (30, 40, 42), (240, y, 520, 5))
        pygame.draw.line(s, (56, 64, 62), (240, y), (760, y))
    for x in (229, 771):
        for y in (192, 465):
            pygame.draw.circle(s, (89, 92, 78), (x, y), 4)
            pygame.draw.line(s, (12, 21, 25), (x - 2, y + 1), (x + 2, y - 1), 2)
    plate = pygame.Rect(240, 194, 189, 25)
    pygame.draw.rect(s, (39, 45, 43), plate, border_radius=2)
    label = font_terminal_small.render(_T("k9.ipa_armory_07"), True, (169, 179, 158))
    s.blit(label, (plate.x + 10, plate.y + 6))
    for x in (681, 708, 735):
        pygame.draw.line(s, (151, 126, 67), (x, 203), (x + 11, 215), 4)
    # Fluorescent task light: dimensional casing and a contained warm core.
    pygame.draw.rect(s, (8, 12, 15), (327, 126, 346, 32), border_radius=5)
    pygame.draw.rect(s, (85, 88, 75), (337, 129, 326, 21), border_radius=3)
    pygame.draw.rect(s, (202, 204, 157), (346, 134, 308, 8), border_radius=3)
    pygame.draw.line(s, (237, 232, 187), (351, 135), (649, 135), 2)
    for x in (362, 638):
        pygame.draw.rect(s, (40, 49, 48), (x, 128, 7, 23))
    # Physical shelf and modest inventory plate.
    pygame.draw.polygon(s, (44, 51, 49), [(201, 492), (797, 492), (821, 507), (179, 507)])
    pygame.draw.rect(s, (15, 24, 27), (179, 507, 642, 22))
    pygame.draw.line(s, (84, 85, 68), (180, 507), (820, 507), 2)
    return s


@lru_cache(maxsize=1)
def _background_soft():
    """Subtle focus pull: the rack recedes as the held weapon approaches."""
    base = _background().copy()
    _hooks(base, TOTAL_MS)
    small = pygame.transform.smoothscale(base, (250, 175))
    soft = pygame.transform.smoothscale(small, (WIDTH, HEIGHT))
    grade = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
    grade.fill((3, 10, 16, 42))
    soft.blit(grade, (0, 0))
    return soft


@lru_cache(maxsize=1)
def _weapon():
    """Editable 2.5D compact SMG, drawn at 2x for clean small components.

    Local pivot is (0,0). Long axis is x; stock left, muzzle right. A real
    top bevel, handguard, trigger guard, action slot and recessed magazine
    replace the single rounded rectangle in the original illustration.
    """
    u = 2
    s = pygame.Surface((800, 340), pygame.SRCALPHA)
    ox, oy = 400, 92
    def P(x, y): return (round(ox + x * u), round(oy + y * u))
    def poly(c, pts, width=0): pygame.draw.polygon(s, c, [P(*v) for v in pts], width * u)
    def line(c, a, b, w=1): pygame.draw.line(s, c, P(*a), P(*b), max(1, w * u))
    def rect(c, x, y, w, h, edge=0, radius=0):
        pygame.draw.rect(s, c, (*P(x, y), round(w*u), round(h*u)), edge*u, border_radius=radius*u)
    def circ(c, x, y, r): pygame.draw.circle(s, c, P(x,y), round(r*u))
    outline=(7,12,15); metal=(45,56,60)
    # Wire stock with a proper folded buttplate and hinge.
    for a,b in [((-99,-2),(-162,6)),((-99,15),(-162,29))]:
        line(outline,a,b,6); line((77,88,88),a,b,3);line((139,148,132),a,(b[0],b[1]-1))
    poly(outline,[(-165,1),(-156,3),(-151,29),(-159,35),(-167,30)])
    poly((44,55,58),[(-164,4),(-159,5),(-154,28),(-160,31),(-164,27)])
    for y in (9,15,21):line((101,112,110),(-164,y),(-158,y-2))
    # Magazine under receiver. Witness holes are dark recesses, not gold LEDs.
    poly(outline,[(-28,20),(0,20),(5,111),(-21,113),(-28,104)])
    poly((33,43,48),[(-25,23),(-3,23),(2,107),(-19,109),(-24,102)])
    poly((63,76,77),[(-25,23),(-19,24),(-13,109),(-19,109),(-24,102)])
    line((108,119,110),(-24,24),(-3,24))
    for y in range(36,98,10):
        line((17,28,33),(-16,y),(-5,y-1),2)
        circ((6,15,21),-8,y-2,1)
    poly((12,22,28),[(-23,105),(4,103),(7,114),(-21,118),(-26,115)])
    line((101,110,100),(-23,105),(4,103))
    # Grip and trigger guard, offset from the magazine.
    poly(outline,[(-91,17),(-57,19),(-66,77),(-94,78),(-102,68)])
    poly((31,43,47),[(-88,24),(-63,25),(-72,73),(-91,73),(-97,66)])
    poly((58,70,71),[(-88,24),(-81,25),(-88,72),(-91,73),(-97,66)])
    for y in range(36,68,6):line((11,23,29),(-91,y),(-71,y),2)
    poly((56,67,67),[(-57,22),(-35,22),(-32,46),(-57,47),(-65,39)])
    poly((6,14,19),[(-54,26),(-40,26),(-38,41),(-55,42),(-59,37)])
    line((154,155,131),(-51,25),(-49,35),2)
    # Receiver: dark face, warm upper bevel and cool extruded underside.
    poly(outline,[(-107,-24),(36,-24),(49,-14),(49,18),(36,28),(-103,28),(-111,16),(-111,-16)])
    poly(metal,[(-104,-19),(35,-19),(43,-11),(43,16),(32,23),(-101,23),(-106,13),(-106,-12)])
    poly((91,107,105),[(-104,-19),(35,-19),(43,-11),(-96,-10),(-106,-12)])
    poly((24,36,42),[(-106,13),(43,13),(43,16),(32,23),(-101,23)])
    line((183,191,165),(-102,-19),(34,-19))
    line((63,80,81),(-97,2),(31,2))
    # Recessed port and moving charging handle slot.
    rect((7,16,21),-46,-9,54,15,radius=2)
    rect((18,28,31),-43,-7,47,10,radius=1)
    line((108,124,118),(-42,5),(2,5))
    rect((8,19,24),-91,0,30,4,radius=1)
    for x,y in [(-96,-2),(28,7),(-35,15)]:
        circ((10,21,26),x,y,3);circ((111,125,115),x-1,y-1,1)
    # Selector, serial engraving, bracket. No futuristic glow.
    circ((10,21,24),-76,12,4)
    line((164,166,137),(-76,12),(-66,8),2)
    circ((172,136,73),-79,5,1)
    label=font_terminal_small.render(_T("k9.k_9"),True,(181,193,172))
    s.blit(label,P(15,-8))
    for x in range(2,23,3):line((91,110,110),(x,12),(x,15))
    # Front shroud and integral suppressor: side, top and muzzle ellipses.
    poly(outline,[(40,-17),(88,-17),(94,-10),(94,14),(86,22),(41,22)])
    poly((37,51,57),[(45,-13),(87,-13),(89,-8),(89,13),(84,18),(45,18)])
    poly((95,111,108),[(45,-13),(87,-13),(89,-8),(45,-5)])
    for x in range(51,85,8):
        line((7,19,25),(x,-1),(x,11),3)
        line((67,84,85),(x+2,-1),(x+2,11))
    rect((11,22,28),87,-12,13,27,radius=2)
    rect((58,71,73),97,-15,67,28,radius=7)
    rect((96,110,105),99,-13,62,5,radius=2)
    rect((26,39,46),99,6,64,7,radius=2)
    for x in (101,105,151):line((25,39,46),(x,-10),(x,10),2)
    pygame.draw.ellipse(s,(110,120,109),(*P(157,-14),20*u,28*u))
    pygame.draw.ellipse(s,(18,30,37),(*P(160,-11),14*u,22*u))
    pygame.draw.ellipse(s,(4,11,17),(*P(164,-7),7*u,14*u))
    line((172,181,151),(105,-12),(150,-12))
    # Low-profile sights and segmented top rail.
    for x in range(-88,42,8):rect((102,117,109),x,-23,5,4)
    poly(outline,[(-95,-22),(-92,-33),(-80,-33),(-77,-22)])
    line((113,130,118),(-91,-30),(-82,-30),2)
    poly(outline,[(74,-15),(76,-29),(83,-29),(88,-15)])
    line((137,150,130),(79,-27),(81,-27),2)
    # Controlled scuffing on metal rather than animated random grain.
    rng=random.Random(909)
    for _ in range(36):
        x,y=rng.randint(-99,31),rng.randint(-15,18)
        if -48<x<11 and -10<y<8:continue
        line((79,94,93),(x,y),(x+rng.randint(1,3),y))
    return s


@lru_cache(maxsize=96)
def _weapon_transform(scale, angle):
    base = _weapon()
    sized = pygame.transform.smoothscale(base,(round(base.get_width()*scale/2), round(base.get_height()*scale/2)))
    return pygame.transform.rotate(sized,angle)


def _draw_weapon(s, pose):
    x,y,scale,angle=pose
    # Source pivot is (400,92), NOT the centre of the image. Padding must not
    # shift the gun by half its magazine height when it rotates.
    img=_weapon_transform(round(scale,3),round(angle,2))
    mid=_local((0,39),pose)
    s.blit(img,img.get_rect(center=(round(mid[0]),round(mid[1]))))


def _sleeve(s, start, end, width, cool=False):
    dx,dy=end[0]-start[0],end[1]-start[1]
    length=max(1,math.hypot(dx,dy));nx,ny=-dy/length,dx/length
    def pt(p,off):return(p[0]+nx*off,p[1]+ny*off)
    pts=[pt(start,width*.5),pt(start,-width*.5),pt(end,-width*.27),pt(end,width*.27)]
    pygame.draw.polygon(s,(6,13,18),[pt(start,width*.55),pt(start,-width*.55),pt(end,-width*.32),pt(end,width*.32)])
    pygame.draw.polygon(s,(40,53,56) if cool else (56,63,55),pts)
    pygame.draw.polygon(s,(68,80,77) if cool else (90,95,73),[pts[0],pts[3],pt(end,width*.12),pt(start,width*.22)])
    # Broad cloth folds and wrist cuff. Far thicker than the old cable sleeves.
    for p in (.48,.66,.82):
        c=_mix(start,end,p);w=width*(.5-.23*p)
        pygame.draw.line(s,(22,36,40),pt(c,-w),pt(c,w*.6),3)
        pygame.draw.line(s,(72,83,76),pt((c[0]+3,c[1]-3),-w*.75),pt((c[0]+3,c[1]-3),w*.5))
    cuff=_mix(start,end,.95)
    pygame.draw.line(s,(15,26,31),pt(cuff,-width*.29),pt(cuff,width*.29),9)
    pygame.draw.line(s,(112,119,95),pt(cuff,-width*.25),pt(cuff,width*.25),2)


def _glove(s, pos, size, angle, support=False, open_amount=0):
    """Connected palm, curled fingers and thumb; full-size cuff attachment."""
    cx,cy=pos
    rad=math.radians(angle);ca,sa=math.cos(rad),math.sin(rad)
    def p(x,y):return(cx+size*(x*ca+y*sa),cy+size*(-x*sa+y*ca))
    def poly(c,pts,w=0):pygame.draw.polygon(s,c,[p(*v) for v in pts],w)
    def line(c,a,b,w=1):pygame.draw.line(s,c,p(*a),p(*b),w)
    shape=[(-17,14),(-18,-8),(-12,-21),(10,-21),(18,-8),(17,18),(9,26),(-10,26)]
    poly((5,13,18),shape)
    poly((46,58,58),[(x*.9,y*.9) for x,y in shape])
    poly((78,87,75),[(-15,-7),(-10,-18),(8,-18),(15,-6),(10,4),(-10,3)])
    poly((30,45,49),[(-14,8),(13,9),(12,18),(7,23),(-9,22)])
    for i in range(4):
        x=-11+i*6
        poly((118,125,98),[(x,-15),(x+4,-15),(x+4,-8),(x,-9)])
        line((21,37,43),(x-1,-16),(x-1,-3),2)
    side=-1 if support else 1
    # Fingers visibly wrap onto the contact surface, index stays off trigger.
    for i in range(3):
        y=-2+i*6
        end=side*(22+open_amount*12)
        line((9,22,29),(side*12,y),(end,y-3),7)
        line((99,111,96),(side*13,y-2),(end,y-4),2)
    poly((20,35,40),[(-side*10,0),(-side*25,5),(-side*23,14),(-side*11,18)])
    line((124,131,102),(-side*13,2),(-side*22,7),2)
    line((124,131,102),(-10,19),(8,20),2)


def _hands(ms,pose):
    g=ms-WALL_MS
    reach_d=_ease((g-40)/490)
    reach_s=_ease((g-145)/415)
    ready=max(0,g-GRAB_MS)
    dominant=_local((-78,53),pose)
    support=_local((68,28),pose)
    # Support releases the fore-end, checks the action, and returns. Exactly
    # two hands: the dominant grip never disappears during the ready check.
    to_handle=_ease((ready-200)/360)
    return_grip=_ease((ready-1070)/360)
    pull=_ease((ready-590)/300)*(1-_ease((ready-980)/90))
    check=_local((-18-32*pull,-11),pose)
    support=_mix(support,check,to_handle*(1-return_grip))
    d_start=(280,HEIGHT+70);s_start=(885,HEIGHT+80)
    d_pos=_mix(d_start,dominant,reach_d)
    s_pos=_mix(s_start,support,reach_s)
    return (d_start,d_pos,reach_d),(s_start,s_pos,reach_s),pull


def _hooks(s,ms,front=False):
    g=ms-WALL_MS
    lift=_ease((g-610)/410)
    for x in (390,593):
        # Fixed wall clips stay on the rack after the weapon is taken.
        if not front:
            pygame.draw.rect(s,(21,33,38),(x-9,274,18,42),border_radius=3)
            pygame.draw.circle(s,(129,136,115),(x,281),3)
            pygame.draw.line(s,(63,78,77),(x,288),(x,321),6)
            pygame.draw.line(s,(167,173,139),(x-2,289),(x-2,321),2)
        elif lift<.5:
            pygame.draw.arc(s,(163,171,142),(x-10,312,20,15),math.pi,math.pi*2,4)


def _draw(s,ms):
    ms=max(0,min(TOTAL_MS,float(ms)))
    previous_clip=s.get_clip()
    s.set_clip(previous_clip.clip(pygame.Rect(0,SCENE_TOP,WIDTH,SCENE_BOT-SCENE_TOP)))
    try:
        s.blit(_background(),(0,0))
        _hooks(s,ms)
        focus=_ease((ms-WALL_MS-1030)/720)
        if focus:
            soft=_background_soft()
            soft.set_alpha(round(205*focus))
            s.blit(soft,(0,0))
        # Deterministic, low-contrast motes in the task light. No global RNG.
        for i in range(13):
            x=330+(i*83)%350+math.sin(ms*.0007+i)*6
            y=162+(i*47+ms*.007)%292
            pygame.draw.circle(s,(76,81,66),(round(x),round(y)),1)
        pose=_pose(ms)
        d,support,pull=_hands(ms,pose)
        # Sleeves behind the gun, curled fingers in front: no intersecting arms.
        for hand,cool in ((d,False),(support,True)):
            start,end,reach=hand
            if reach>.005:_sleeve(s,start,end,88 if not cool else 94,cool)
        _draw_weapon(s,pose)
        # Charging handle uses the same rigid transform as the gun.
        a=_local((-18-32*pull,-9),pose);b=_local((-18-32*pull,-17),pose)
        pygame.draw.line(s,(12,24,30),a,b,7)
        pygame.draw.line(s,(167,176,151),a,b,3)
        _hooks(s,ms,True)
        for hand,is_support in ((d,False),(support,True)):
            start,end,reach=hand
            if reach>.005:
                _glove(s,end,1.0+(.33*(pose[2]-1.25)/.55),pose[3]-8 if not is_support else pose[3]+18,is_support,1-reach)
        # Reward read arrives only after the action is back in battery.
        ready=ms-WALL_MS-GRAB_MS
        a=round(255*_ease((ready-1260)/200))
        if a:
            title=font_terminal.render(_T("k9.k_9_acquired"),True,(219,224,195));title.set_alpha(a)
            sub=font_terminal_small.render(_T("k9.suppressed_smg_24_rounds_2_spare"),True,(172,187,179));sub.set_alpha(a)
            s.blit(title,(58,SCENE_TOP+40));s.blit(sub,(58,SCENE_TOP+70))
    finally:
        s.set_clip(previous_clip)


def draw_wall(s,t):
    _draw(s,min(WALL_MS,max(0,t)))


def draw_grab(s,t):
    _draw(s,WALL_MS+min(GRAB_MS,max(0,t)))


def draw_ready(s,t):
    _draw(s,WALL_MS+GRAB_MS+min(READY_MS,max(0,t)))
