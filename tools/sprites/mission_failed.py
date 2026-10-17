"""Bespoke, entirely code-drawn mission-failure vignettes.

Six hand-composed procedural scenes, using the house palette and sprite kit.
No photographs, AI image sources, image imports, or network calls. All geometry,
material texture, light, and narrative props are authored below. Each scene is
160x125, exported at exactly 2x nearest-neighbour to native 320x250 UI frames.

python tools/sprites/mission_failed.py [--out DIR] [--preview]
"""
import argparse
import hashlib
import json
import math
from pathlib import Path
import random

import kit as K
import palette as P
import pygame as pg

ROOT = Path(__file__).resolve().parents[2]
KEYS = ("notebook", "route", "cells", "tower", "press", "maru_lost")
DARK = (10, 15, 21)


def poly(s, pts, c, edge=None):
    pg.draw.polygon(s, c, pts)
    if edge:
        pg.draw.lines(s, edge, True, pts, 1)


def line(s, a, b, c, w=1):
    pg.draw.line(s, c, a, b, w)


def rect(s, r, c, edge=None):
    pg.draw.rect(s, c, r)
    if edge:
        pg.draw.rect(s, edge, r, 1)


def base(top, bottom):
    s = K.new(160, 125)
    for y in range(125):
        s.fill(P.mix(top, bottom, (y//4)*4/124), (0, y, 160, 1))
    return s


def glow(s, at, radius, color, strength=.22):
    # Quantized, deterministic light on the environment, not a blurred photo.
    cx, cy = at
    for y in range(max(0, cy-radius), min(125, cy+radius)):
        for x in range(max(0, cx-radius), min(160, cx+radius)):
            d = math.hypot(x-cx, y-cy)/radius
            if d < 1:
                k = round((1-d)*6)/6*strength
                s.set_at((x, y), P.mix(s.get_at((x, y)), color, k))


def wear(s, pts, color, n, seed):
    mask = K.new(160, 125)
    poly(mask, pts, (255,255,255))
    rng = random.Random(seed)
    for _ in range(n):
        x, y = rng.randrange(160), rng.randrange(125)
        if mask.get_at((x,y))[3]:
            s.set_at((x,y), color)
            if rng.random() < .13 and x < 159 and mask.get_at((x+1,y))[3]:
                s.set_at((x+1,y), color)


def bolt(s, x, y, c=(133,139,131)):
    rect(s, (x-1,y-1,3,3), P.shade(c,.42))
    line(s, (x-1,y-1), (x+1,y-1), c)


def cable(s, points, c=(42,49,50), width=2):
    pg.draw.lines(s, DARK, False, [(x+1,y+1) for x,y in points], width+1)
    pg.draw.lines(s, c, False, points, width)
    for a,b in zip(points[::2],points[1::2]):
        line(s,a,b,P.mix(c,(140,164,165),.2))


def notebook():
    s=base((13,21,28),(38,32,29))
    # Rafters, corrugated walls, amber warehouse inspection lamp.
    for x in range(0,160,13): line(s,(x,0),(x,77),(28,36,40))
    for y in (13,39,65): line(s,(0,y),(160,y),(12,18,24),2)
    for x in (-20,47,114):
        poly(s,[(x,0),(x+4,0),(x+50,25),(x+44,25)],(45,48,46))
    rect(s,(119,25,29,39),(9,16,21),(42,49,49))
    for x in (123,136): rect(s,(x,29,8,13),(42,54,57))
    poly(s,[(18,16),(44,20),(113,102),(0,102)],(43,40,31))
    glow(s,(32,30),83,(224,162,78),.33)
    line(s,(26,0),(26,13),(92,86,64),2)
    poly(s,[(17,12),(32,12),(39,20),(10,20)],(64,70,65),(109,110,88))
    line(s,(13,20),(36,20),P.GOLD_HI,2)
    # Solid, perspectival crate, nail heads, end grain and banding.
    poly(s,[(9,83),(111,69),(153,97),(49,119)],(94,75,48),(132,105,64))
    poly(s,[(9,83),(49,119),(49,125),(9,102)],(47,41,33),(72,62,44))
    poly(s,[(49,119),(153,97),(153,125),(49,125)],(56,46,34),(91,72,46))
    for dx in (0,17,35,53,71):
        line(s,(19+dx,82-dx//7),(56+dx,113-dx//6),(46,40,31))
        line(s,(22+dx,84-dx//7),(53+dx,110-dx//6),(121,95,54))
    for x,y in ((16,88),(37,105),(64,117),(112,106),(143,99)): bolt(s,x,y,(123,111,80))
    poly(s,[(80,74),(87,73),(129,102),(122,104)],(54,58,56),(95,98,81))
    # Notebook: cast shadow, layered pages, rolled spine and leather wear.
    poly(s,[(35,59),(103,48),(137,85),(63,103)],(24,25,26))
    pages=[(38,57),(103,46),(132,81),(62,98)]
    poly(s,pages,(163,151,117),(72,68,57))
    for dy in (2,4,6): line(s,(63,91+dy),(130,77+dy),(91,89,72))
    cover=[(36,52),(103,41),(133,77),(61,94)]
    poly(s,cover,(28,34,38),(100,104,93))
    poly(s,[(36,52),(43,51),(68,91),(61,94)],(18,24,29),(61,70,70))
    line(s,(44,54),(101,45),(121,119,96))
    line(s,(101,45),(127,76),(66,77,76))
    line(s,(66,88),(128,76),(64,74,74))
    wear(s,cover,(47,56,57),800,101)
    # Embossed evidence plate and clasp. No generic notebook outline icon.
    poly(s,[(65,60),(90,56),(102,69),(77,75)],(65,66,55),(151,133,82))
    line(s,(72,63),(88,60),(185,163,102))
    line(s,(76,68),(94,64),(136,127,82))
    poly(s,[(96,48),(106,46),(113,54),(103,57)],(91,86,63),(160,145,91))
    bolt(s,105,51,P.BRASS)
    poly(s,[(91,87),(96,86),(105,105),(98,102),(96,109)],(133,45,42),(183,68,49))
    return s


def route():
    s=base((22,36,50),(39,58,64))
    # Layered treeline, receding road and the abandoned ambush truck.
    rng=random.Random(202)
    for i in range(21):
        x=i*9-7; y=rng.randrange(14,33)
        poly(s,[(x,y),(x-10,63),(x+10,63)],(19,33,43))
        line(s,(x,y+15),(x,67),(14,26,36))
    poly(s,[(86,43),(108,43),(160,125),(0,125)],(39,47,51))
    line(s,(85,43),(0,118),(99,114,115))
    for y,ww in ((54,2),(66,3),(83,5),(107,8)):
        x=94+(y-44)//5
        poly(s,[(x,y),(x+ww,y),(x+ww+3,y+7),(x+1,y+7)],(127,132,111))
    # Wheels, suspension, segmented cargo bay, charred cab.
    for x in (34,70):
        pg.draw.circle(s,(12,18,23),(x,65),8)
        pg.draw.circle(s,(57,65,65),(x,65),3)
        line(s,(x-4,60),(x+3,59),(71,82,81))
    rect(s,(22,50,58,12),(44,48,44),(13,20,26))
    poly(s,[(21,50),(27,37),(43,35),(49,48)],(70,76,63),(110,113,88))
    poly(s,[(28,38),(40,37),(45,46),(25,47)],(15,32,43),(97,119,119))
    rect(s,(46,33,40,23),(55,63,56),(108,110,85))
    for x in (48,59,70,81): line(s,(x,36),(x,53),(24,37,39),2)
    line(s,(48,42),(85,42),(102,104,78))
    rect(s,(18,51,8,8),(46,52,48)); rect(s,(18,52,3,2),(171,154,101))
    for i in range(5):
        pg.draw.ellipse(s,(33+i*2,44+i*2,52+i*2),(49+i*5,13-i*4,14,19))
    # Wet foreground reflection streaks and clipped rain, not noise everywhere.
    for _ in range(36):
        x,y=rng.randrange(160),rng.randrange(68,125)
        line(s,(x,y),(x+rng.randrange(3,13),y),(54,74,84))
    for _ in range(26):
        x,y=rng.randrange(160),rng.randrange(118)
        line(s,(x,y),(x-2,y+5),(77,101,114))
    # Detailed 3/4 field radio: steel side, handles, bezel, speaker mesh, knobs.
    poly(s,[(82,61),(140,55),(152,65),(147,112),(86,120),(77,111)],(14,24,29))
    poly(s,[(82,57),(137,52),(145,60),(89,66)],(99,112,101),(136,145,123))
    poly(s,[(137,52),(146,60),(145,108),(137,116)],(37,54,54),(78,96,91))
    rect(s,(81,61,57,52),(62,80,75),(112,130,116))
    K.inner_line(s,(84,64,51,46),(99,116,100),(29,45,47))
    rect(s,(87,68,26,13),(13,26,27),(129,137,105))
    K.text(s,"146",91,71,(131,172,130))
    for x in range(88,112,3):
        for y in range(87,105,3): rect(s,(x,y,2,1),(20,36,38))
    for x,y,r in ((123,73,5),(123,94,8)):
        pg.draw.circle(s,(27,42,44),(x,y),r+1)
        pg.draw.circle(s,(115,130,113),(x,y),r)
        pg.draw.circle(s,(50,66,64),(x,y),r-2)
        line(s,(x,y),(x+2,y-r+2),(201,202,153))
    for x,y in ((84,64),(134,64),(84,109),(134,109)): bolt(s,x,y,(160,168,139))
    cable(s,[(92,59),(88,52),(79,51),(73,57),(67,57)],(68,80,72),2)
    line(s,(132,55),(149,9),(127,147,145),2)
    line(s,(150,8),(150,5),(176,189,168),2)
    cable(s,[(82,105),(65,113),(51,109),(40,112),(28,105),(24,98)],(85,108,106),2)
    line(s,(24,98),(21,95),P.BRASS);line(s,(24,98),(26,94),P.RED)
    return s


def cells():
    s=base((19,33,33),(37,52,47))
    # Repeated nested apertures create institutional depth, not a flat bar icon.
    poly(s,[(0,0),(61,38),(61,91),(0,125)],(40,54,50))
    poly(s,[(160,0),(102,38),(102,91),(160,125)],(30,45,44))
    poly(s,[(0,125),(61,91),(102,91),(160,125)],(52,62,52))
    for y in (21,47,75,102):
        line(s,(0,y),(61,45+y//2),(18,35,36))
        line(s,(160,y),(102,45+y//2),(19,32,34))
    for x in (10,35,133,153): line(s,(x,0),(80+(x-80)//4,91),(30,45,43))
    for x,y,w,h in ((48,26,63,76),(59,38,40,56),(68,48,22,44)):
        rect(s,(x,y,w,h),(13,27,29),(71,91,77))
        rect(s,(x+3,y+3,w-6,h-3),(24,42,39),(16,31,31))
        for bx in range(x+9,x+w-4,11): line(s,(bx,y+5),(bx,y+h-4),(41,60,53))
    # Fluorescent housing, pipework and a torn wall notice.
    glow(s,(68,18),63,(130,185,132),.30)
    rect(s,(47,12,59,6),(23,39,40),(83,106,83))
    rect(s,(50,14,53,2),(171,205,147))
    line(s,(17,8),(17,67),(92,108,87),2)
    line(s,(17,67),(28,75),(72,89,74),2)
    poly(s,[(128,38),(143,41),(141,60),(133,57),(128,60)],(121,128,98))
    for y in (44,48,52): line(s,(132,y),(139,y+1),(53,70,60))
    # Fractured chair and loose chair-leg weapon on the floor.
    poly(s,[(36,96),(59,91),(77,101),(54,108)],(100,83,55),(143,121,77))
    line(s,(39,96),(32,113),(75,62,44),3)
    line(s,(70,101),(77,116),(70,58,42),3)
    line(s,(44,98),(38,81),(110,93,59),3)
    poly(s,[(86,108),(112,94),(115,97),(93,111),(92,114)],(144,118,72),(179,151,92))
    line(s,(110,96),(115,94),(207,178,112))
    # Foreground open gate, polished edges, rust, lockbox, deep floor shadows.
    for x in (8,25,135,152):
        line(s,(x+4,0),(x+4,125),(10,21,25),5)
        line(s,(x,0),(x,125),(69,89,77),3)
        line(s,(x-1,0),(x-1,125),(112,130,100))
        for y in (37,73,104): rect(s,(x,y,2,3),(92,65,44))
    for y in (35,87):
        rect(s,(0,y,31,4),(67,86,72),(97,113,87))
        rect(s,(130,y,30,4),(55,73,65),(85,102,79))
    rect(s,(16,58,17,19),(72,82,63),(125,131,93))
    pg.draw.circle(s,(12,26,28),(25,65),2);rect(s,(24,66,2,4),(12,26,28))
    return s


def tower():
    s=base((28,30,49),(67,67,79))
    # Curfew city: authored skyline, sparse lit windows and two searchlights.
    for pts in ([(70,77),(22,10),(29,9),(77,77)],[(76,77),(131,16),(137,18),(82,77)]):
        poly(s,pts,(89,88,100))
    skyline=[(0,54,17,39),(18,45,16,48),(36,60,18,33),(56,38,13,55),
             (71,55,21,38),(94,48,16,45),(113,61,17,32),(133,40,27,53)]
    for i,(x,y,w,h) in enumerate(skyline):
        rect(s,(x,y,w,h),(35+i%3*4,41+i%3*3,53+i%3*3))
        for xx in range(x+3,x+w-2,5):
            for yy in range(y+5,89,7):
                if (xx+yy)%4==0: rect(s,(xx,yy,2,2),(133,126,103))
    line(s,(62,38),(62,25),(35,42,55),2)
    # Roof parapet and foreground cabinet.
    poly(s,[(0,95),(160,80),(160,125),(0,125)],(30,37,46),(70,75,80))
    line(s,(0,99),(160,84),(15,24,34),3)
    for x in (25,65,110): line(s,(x,125),(x+18,92),(43,50,57))
    rect(s,(8,70,37,43),(49,59,64),(112,120,112))
    poly(s,[(8,70),(14,65),(50,65),(45,70)],(96,101,96),(132,136,116))
    poly(s,[(45,70),(50,65),(50,108),(45,113)],(26,40,48),(71,84,86))
    rect(s,(13,75,26,11),(19,30,38),(88,104,105))
    for yy in range(78,85,2): line(s,(16,yy),(35,yy),(43,62,69))
    for yy in range(91,106,3): line(s,(14,yy),(37,yy),(24,37,43))
    bolt(s,12,73);bolt(s,41,108)
    rect(s,(35,92,3,3),P.RED)
    # Steel lattice mast with directional panels, guy wires, dead feed cable.
    for a,b in (((112,19),(88,107)),((112,19),(136,102))): line(s,a,b,(139,150,145),2)
    for y in (39,55,71,87,103):
        half=int((y-19)*.28)
        line(s,(112-half,y),(112+half,y),(100,119,122))
        line(s,(112-half,y),(112+half-4,y-14),(62,84,96))
        line(s,(112+half,y),(112-half+4,y-14),(62,84,96))
    line(s,(108,29),(63,111),(80,93,104))
    line(s,(116,29),(155,104),(80,93,104))
    for x,y in ((102,25),(117,22),(110,37)):
        rect(s,(x,y,4,15),(107,121,124),(166,172,152))
        line(s,(x+2,y+3),(x+2,y+12),(56,78,90))
    line(s,(112,5),(112,21),(105,124,134))
    pg.draw.circle(s,(115,44,45),(112,10),2)
    cable(s,[(43,109),(64,113),(82,106),(93,112),(107,118),(121,113)],(80,99,104))
    for dx,c in ((-1,P.RED),(1,P.BRASS),(3,(153,164,159))): line(s,(121,113),(126+dx,109+dx),c)
    return s


def brick_wall(s, tint):
    for y in range(0,90,10):
        line(s,(0,y),(160,y),P.shade(tint,.65))
        for x in range(-12+(y//10%2)*12,160,24): line(s,(x,y),(x,y+10),P.shade(tint,.68))


def press():
    s=base((54,39,39),(24,28,33));brick_wall(s,(73,52,48))
    # Raid light through the back doorway, pipes, power switch, paper trail.
    rect(s,(117,20,31,68),(11,20,26),(115,91,72))
    rect(s,(123,25,23,61),(108,45,39),(184,84,59))
    poly(s,[(127,30),(145,25),(145,86),(127,90)],(42,27,29),(136,65,48))
    poly(s,[(123,85),(146,84),(160,125),(70,125)],(81,44,39))
    glow(s,(130,33),53,(227,75,52),.24)
    rect(s,(124,13,17,5),(106,44,38),(166,77,54));rect(s,(127,14,11,2),(238,133,83))
    line(s,(10,5),(10,40),(95,95,79),2);line(s,(10,40),(32,40),(84,89,77),2)
    rect(s,(14,42,13,19),(52,62,61),(105,111,94));rect(s,(18,47,5,6),P.VALVE_RED)
    # Press shadow / feet and 3/4 iron chassis.
    pg.draw.ellipse(s,(13,19,25),(24,96,103,20))
    for x in (32,93): rect(s,(x,96,9,16),(18,30,34),(65,74,70))
    poly(s,[(29,67),(99,62),(116,75),(110,103),(34,108)],(42,58,58),(110,120,105))
    poly(s,[(99,62),(116,75),(110,103),(99,97)],(28,43,49),(71,89,89))
    rect(s,(37,37,61,58),(63,80,75),(131,138,115))
    rect(s,(42,44,51,39),(14,28,34),(90,110,102))
    # Three stepped steel cylinders: layered strips read as round machined metal.
    for y in (46,58,70):
        rect(s,(43,y,49,9),(28,44,48),(101,123,118))
        line(s,(45,y+1),(90,y+1),(163,176,154))
        line(s,(45,y+3),(90,y+3),(91,113,109),2)
        line(s,(45,y+7),(90,y+7),(37,57,62))
        for x in (40,94): bolt(s,x,y+4,(162,163,123))
    # Continuous paper ribbon curling from the rollers onto the output tray.
    poly(s,[(48,77),(83,77),(85,89),(91,95),(49,99),(45,91)],(181,176,144),(220,210,166))
    line(s,(49,81),(82,81),(121,131,115))
    poly(s,[(31,98),(94,93),(105,100),(40,108)],(88,104,94),(151,155,123))
    for x,y in ((39,40),(96,40),(39,91),(96,91)): bolt(s,x,y,(163,169,132))
    # Flywheel with actual spokes and a crank; ink bottle and discarded proof.
    pg.draw.circle(s,(17,31,37),(109,83),13)
    pg.draw.circle(s,(119,133,118),(109,83),11,2)
    for angle in range(0,360,60):
        a=math.radians(angle);line(s,(109,83),(109+int(math.cos(a)*9),83+int(math.sin(a)*9)),(87,108,101),2)
    bolt(s,109,83,(176,174,128))
    cable(s,[(108,83),(116,89),(123,88)],(141,146,113),2)
    for pts in ([(112,111),(132,103),(149,110),(128,122)],[(61,117),(80,110),(94,117),(79,125)]):
        poly(s,pts,(179,170,135),(215,202,157))
    rect(s,(15,98,10,14),(14,27,31),(64,75,66));rect(s,(17,95,6,4),(91,95,76))
    return s


def maru_lost():
    s=base((26,31,35),(42,36,35))
    # Receding arched tunnel, brick courses following perspective.
    for x,y,w,h in ((49,7,108,115),(62,19,79,101),(74,31,55,84),(84,43,35,69)):
        pg.draw.rect(s,(18,25,30),(x,y,w,h),border_radius=w//2)
        pg.draw.rect(s,(65,58,52),(x,y,w,h),2,border_radius=w//2)
    for y in range(15,120,11):
        line(s,(0,y),(50,y+9),(55,54,48))
        for x in range((y//11%2)*12,50,24): line(s,(x,y),(x,y+10),(51,51,46))
    poly(s,[(55,104),(117,100),(160,125),(16,125)],(47,43,41))
    glow(s,(103,54),34,(184,62,47),.22)
    rect(s,(95,51,16,4),(133,52,40),(199,91,59));rect(s,(98,52,10,2),(243,151,95))
    for x,y,w in ((106,110,12),(113,117,22),(98,104,6)):
        line(s,(x,y),(x+w,y),(122,67,51))
        line(s,(x+3,y+2),(x+w-3,y+2),(83,51,46))
    # Empty chair, visible mortise joints and a weighty abandoned uniform coat.
    for x in (29,59):
        line(s,(x,55),(x+4,119),(82,77,58),3)
        line(s,(x-1,55),(x+3,116),(136,125,86))
    poly(s,[(24,87),(61,82),(73,94),(34,102)],(102,89,61),(164,143,93))
    line(s,(69,95),(73,120),(93,84,62),3)
    line(s,(37,101),(34,123),(92,83,59),3)
    poly(s,[(24,44),(39,38),(54,40),(63,51),(68,80),(57,87),(43,81),(34,91),(18,83)],(68,79,58),(120,131,86))
    poly(s,[(24,44),(39,38),(36,53),(30,58)],(111,119,76),(154,157,101))
    poly(s,[(39,38),(54,40),(46,54),(36,53)],(34,49,42),(102,115,76))
    poly(s,[(47,54),(55,45),(63,56),(68,80),(59,85)],(48,65,51),(87,105,66))
    line(s,(39,55),(43,80),(128,137,89))
    for y in (61,68,75): pg.draw.circle(s,(168,156,95),(42,y),1)
    rect(s,(23,62,11,10),(58,74,53),(112,127,80));line(s,(24,64),(33,64),(147,150,96))
    wear(s,[(24,48),(35,45),(43,82),(20,82)],(87,101,65),450,606)
    # Satchel buckles, strap and a single dropped paper on the escape route.
    poly(s,[(7,101),(31,98),(42,107),(38,123),(6,123)],(67,72,51),(122,125,82))
    poly(s,[(7,101),(31,98),(35,106),(9,110)],(94,100,63),(149,147,94))
    for x in (14,28): rect(s,(x,107,4,6),(156,141,84),(43,53,41))
    cable(s,[(9,100),(11,91),(24,87),(35,91),(36,101)],(124,128,85),2)
    poly(s,[(91,113),(116,106),(133,116),(108,125)],(175,166,137),(208,193,153))
    return s


PAINTERS=(notebook,route,cells,tower,press,maru_lost)


def build(out):
    K.init()
    out=Path(out);out.mkdir(parents=True,exist_ok=True)
    sheet=K.new(960,500)
    frames={}
    for i,(key,painter) in enumerate(zip(KEYS,PAINTERS)):
        tile=pg.transform.scale(painter(),(320,250))
        x,y=(i%3)*320,(i//3)*250
        sheet.blit(tile,(x,y))
        frames[key]={"rect":[x,y,320,250],"anchor":[0,0]}
    pg.image.save(sheet,str(out/'spr_mission_failed.png'))
    meta={"size":[960,500],"scale":1,"frames":frames,
          "source_kind":"procedural Python/pygame geometry only; no imported image sources",
          "authored_size":[160,125],"upscale":"2x nearest-neighbour",
          "source_sha256":hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    (out/'spr_mission_failed.json').write_text(json.dumps(meta,indent=2,sort_keys=True)+'\n',encoding='utf-8',newline='\n')
    print('MISSION FAILURE ART: OK (six bespoke procedural vignettes; no image inputs)')
    return sheet


if __name__=='__main__':
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--out',type=Path,default=ROOT/'assets/art')
    ap.add_argument('--preview',action='store_true')
    args=ap.parse_args();sheet=build(args.out)
    if args.preview:
        dst=ROOT/'previews/sprites';dst.mkdir(parents=True,exist_ok=True)
        pg.image.save(sheet,str(dst/'mission_failed.png'))
