"""YouTube thumbnail for the 2.5D announcement (1280x720).

    python tools/trailer_25d/thumbnail.py

Left: the flat game in black and white. Right: the 2.5D game in colour. The
President presents the extra half in front, with the KRAP-red +0.5D stamp.
Writes trailers/announce_25d/thumbnail.png (and thumbnail.jpg under 2 MB),
plus one 1080x1920 cover per short in trailers/announce_25d/shorts/.
"""
import math
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import render as R  # noqa: E402
import pygame  # noqa: E402
import cv2  # noqa: E402

TW, TH = 1280, 720
KEY = (255, 0, 255)


def president(w, h):
    """Waist-up President, one hand on the DEPTH lever, the other up: "behold"."""
    import engine3d
    lt = R.C.light((-0.5, 0.8, -0.7), 0.55, 0.9, sky=0.08, tint=(1.05, 0.98, 0.9))
    r = engine3d.Renderer(w, h, fog=KEY, fog_start=40, fog_end=60)
    r.light = lt
    hm = R.S.hum("president")
    hm.set_expression("grin", mouth_open=0.6)
    yaw, pos, lever = 188.0, (0.0, 0.0, 0.0), 0.35
    lv = (0.62, 0.0, -0.42)
    g = R.S.m_apply(R.S.rot_x(R.S.lerp(-30, 58, lever)), (0.0, 0.56, 0.0))
    grip = (lv[0] + g[0], 1.0 + g[1], lv[2] + g[2])
    p = R.S.pose("stand", head_y=-10, head_p=-4, spine=-3)
    sh = R.S.shoulder_world(hm, p, pos, yaw, "r")
    d = R.S.m_apply(R.S.rot_y(yaw), (0.38, 0.4, 0.22))
    up = (sh[0] + d[0], sh[1] + d[1], sh[2] + d[2])
    p = R.S.hands(hm, p, pos, yaw, 0.0, world={"r": (up, 1.0), "l": (grip, 1.0)})
    r.set_camera((-0.2, 1.55, -3.05), (0.22, 1.38, 0.0), 42)
    r.surface.fill(KEY)
    r.begin()
    r.add_humanoid(hm, p, pos, yaw, rifle_on=False)
    v, f = R.S.P.dyn_faces(R.S.lever_mesh(lever), None, lv)
    r.add_dynamic(v, f)
    r.flush(r.surface)
    a = np.frombuffer(pygame.image.tobytes(r.surface, "RGB"), np.uint8).reshape(h, w, 3).astype(np.int16)
    key = (a[..., 0] > 150) & (a[..., 2] > 150) & (a[..., 1] < 110)   # key colour and its blended rim
    rgba = np.dstack([a.astype(np.uint8), np.where(key, 0, 255).astype(np.uint8)])
    return pygame.image.frombytes(rgba.tobytes(), (w, h), "RGBA")


def bw(surf):
    a = np.frombuffer(pygame.image.tobytes(surf, "RGB"), np.uint8).reshape(surf.get_height(), surf.get_width(), 3)
    y = a.astype(np.float32) @ R.LUMA
    y = np.clip(255.0 * (y / 255.0) ** 0.7 * 1.05, 0, 255).astype(np.uint8)
    return pygame.image.frombytes(np.stack([y] * 3, -1).tobytes(), surf.get_size(), "RGB")


SW, SH = 1080, 1920
NAVY = (16, 18, 30)


def sq(surf, cx, cy=540, side=1080):
    """Square crop of a 1920x1080 frame, scaled to the cover's picture box."""
    x = max(0, min(R.OW - side, cx - side // 2))
    y = max(0, min(R.OH - side, cy - side // 2))
    return pygame.transform.scale(surf.subsurface((x, y, side, side)), (SW, SW))


def cover(name, pic, top, lines, stamp_lines, at=(800, 1170)):
    s = pygame.Surface((SW, SH))
    s.fill(NAVY)
    for y in range(0, SH, 6):                                  # CRT lines
        pygame.draw.line(s, (12, 13, 22), (0, y), (SW, y), 2)
    live = R.text("LIVE", "oswald", 54, (255, 255, 255))
    box = live.get_rect(topleft=(60, 70)).inflate(30, 10)
    pygame.draw.rect(s, R.RED, box)
    s.blit(live, live.get_rect(center=box.center))
    hd = R.text("TVA 1 - PROGRAMUL NATIONAL", "oswald", 54, R.GOLD)
    s.blit(hd, hd.get_rect(midleft=(box.right + 24, box.centery)))
    sub = R.text(top, "oswald", 46, (200, 200, 210))
    s.blit(sub, sub.get_rect(topleft=(60, box.bottom + 24)))
    py = 300
    s.blit(pic, (0, py))
    pygame.draw.rect(s, R.GOLD, (0, py, SW, SW), 8)
    st = pygame.Surface((SW, SH), pygame.SRCALPHA)
    R.stamp(st, 1.0, stamp_lines, at, angle=11, scale=1.25)
    s.blit(st, (0, 0))
    y = py + SW + 130
    for ln in lines:
        R.extruded(s, ln, 150, (SW // 2, y), 12, (255, 255, 255), (200, 40, 40))
        y += 165
    t = R.text("CALL OF ACARISTAN - NOW IN 2.5D", "oswald", 58, R.GOLD, outline=4)
    s.blit(t, t.get_rect(midbottom=(SW // 2, SH - 70)))
    out = os.path.join(R.OUT, "shorts", "thumb_%s.png" % name)
    pygame.image.save(s, out)
    a = np.frombuffer(pygame.image.tobytes(s, "RGB"), np.uint8).reshape(SH, SW, 3)
    cv2.imwrite(out[:-4] + ".jpg", cv2.cvtColor(a, cv2.COLOR_RGB2BGR), [cv2.IMWRITE_JPEG_QUALITY, 92])
    print("wrote", out)


def split_ba():
    """Top half the flat 2D game in black and white, bottom half 2.5D in colour."""
    pic = pygame.Surface((SW, SW))
    for i, (src, t) in enumerate((("m2_2d", 6.0), ("m2_3d", 6.0))):
        f = R.clip(src).frame(t, size=(R.OW, R.OH), zoom=1.2, pop=(i == 1))
        f = pygame.transform.scale(f.subsurface((0, 60, R.OW, 960)), (SW, SW // 2))
        pic.blit(bw(f) if i == 0 else f, (0, i * SW // 2))
        lab = R.text("BEFORE" if i == 0 else "AFTER", "oswald", 90, (255, 255, 255), outline=5)
        pic.blit(lab, (40, i * SW // 2 + 24))
    pygame.draw.line(pic, R.GOLD, (0, SW // 2), (SW, SW // 2), 10)
    return pic


def shorts():
    cover("01_the_lever", sq(R.up3(R.palace.render(1.0, shot="front", flourish=1.0)), 870),
          "THE PALACE, 19:59", ["HE PULLED", "THE LEVER"], ["+0.5D"])
    cover("02_citizen_instructions", sq(R.up3(R.studio.render(2.0, cam="close", reach=1.0, deep=True)), 1180),
          "RULES FOR VIEWERS", ["DO NOT TOUCH", "THE SCREEN"], ["RULE 1"], at=(250, 1180))
    cover("03_before_after", split_ba(), "DECREE No. 2.5", ["SAME REPUBLIC", "EXTRA HALF"], ["+0.5D"], at=(830, 840))
    cover("04_balaceanu", sq(R.up3(R.press.render(1.0, shot="close", chest=0.2)), 960, 560),
          "PRESS CONFERENCE", ["HE INVENTED", "DEPTH"], ["UNVERIFIED"])


def main():
    pygame.init()
    pygame.display.set_mode((64, 64))
    R.OVERLAYS["on"] = False
    # background: flat grey 2D on the left, the 2.5D game in colour on the right
    left = bw(R.clip("m2_2d").frame(6.0, size=(TW, TH), zoom=1.3))
    right = R.clip("m2_3d").frame(6.0, size=(TW, TH), zoom=1.5, pop=True)
    s = right.copy()
    cut = [(0, 0), (520, 0), (400, TH), (0, TH)]
    mask = pygame.Surface((TW, TH), pygame.SRCALPHA)
    pygame.draw.polygon(mask, (255, 255, 255, 255), cut)
    lm = left.convert_alpha()
    lm.blit(mask, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
    s.blit(lm, (0, 0))
    dim = pygame.Surface((TW, TH), pygame.SRCALPHA)           # text side goes dark
    pygame.draw.polygon(dim, (0, 0, 0, 238), cut)
    s.blit(dim, (0, 0))
    # state-poster sunburst behind the President
    rays = pygame.Surface((TW, TH), pygame.SRCALPHA)
    cx, cy = 900, 300
    for i in range(16):
        a0 = i * math.tau / 16
        pts = [(cx, cy), (cx + 1600 * math.cos(a0), cy + 1600 * math.sin(a0)),
               (cx + 1600 * math.cos(a0 + math.tau / 32), cy + 1600 * math.sin(a0 + math.tau / 32))]
        pygame.draw.polygon(rays, (200, 30, 30, 120), pts)
    rm = pygame.Surface((TW, TH), pygame.SRCALPHA)
    pygame.draw.polygon(rm, (255, 255, 255, 255), [(520, 0), (TW, 0), (TW, TH), (400, TH)])
    rays.blit(rm, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
    s.blit(rays, (0, 0))
    pygame.draw.line(s, R.GOLD, (520, 0), (400, TH), 10)
    pres = president(760, 760)
    s.blit(pres, (540, -30))
    bug = R.text("LIVE", "oswald", 40, (255, 255, 255))
    box = bug.get_rect(topleft=(36, 30)).inflate(24, 8)
    pygame.draw.rect(s, R.RED, box)
    s.blit(bug, bug.get_rect(center=box.center))
    hd = R.text("TVA 1", "oswald", 44, R.GOLD, outline=3)
    s.blit(hd, hd.get_rect(midleft=(box.right + 16, box.centery)))
    ni = R.text("NOW IN", "oswald", 96, (235, 235, 235), outline=5)
    s.blit(ni, ni.get_rect(midleft=(44, 210)))
    R.extruded(s, "2.5D", 250, (230, 395), 14, (255, 255, 255), (200, 40, 40))
    st = pygame.Surface((TW, TH), pygame.SRCALPHA)
    R.stamp(st, 1.0, ["DECREE No. 2.5"], (1075, 655), angle=-6, scale=0.6, paper=True)
    s.blit(st, (0, 0))
    t = R.text("CALL OF ACARISTAN", "oswald", 54, R.GOLD, outline=4)
    s.blit(t, t.get_rect(midleft=(44, 610)))
    out = os.path.join(R.OUT, "thumbnail.png")
    pygame.image.save(s, out)
    a = np.frombuffer(pygame.image.tobytes(s, "RGB"), np.uint8).reshape(TH, TW, 3)
    cv2.imwrite(out[:-4] + ".jpg", cv2.cvtColor(a, cv2.COLOR_RGB2BGR), [cv2.IMWRITE_JPEG_QUALITY, 92])
    print("wrote", out)
    shorts()


if __name__ == "__main__":
    main()
