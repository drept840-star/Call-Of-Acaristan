"""YouTube thumbnails (1280x720) composed from real trailer frames.

    python tools/trailer3d/thumbnail.py      -> outputs/trailer3d/thumbnail_A.png / _B.png
"""
import os
import sys

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import common as C  # noqa: E402
import pygame  # noqa: E402
import render  # noqa: E402
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont  # noqa: E402

W, H = 1280, 720
ORANGE = C.ORANGE
RED = (206, 32, 28)
INK = (240, 236, 226)
FONT = os.path.join(C.FONT_DIR, "Oswald.ttf")
MONO = os.path.join(C.FONT_DIR, "IBMPlexMono-Bold.ttf")


def oswald(size, weight=b"Bold"):
    f = ImageFont.truetype(FONT, size)
    f.set_variation_by_name(weight)
    return f


def grab(tr, T):
    cv = tr.frame(T, int(T * C.FPS))
    return Image.frombytes("RGB", cv.get_size(), pygame.image.tobytes(cv, "RGB"))


def band(img):
    """Letterboxed picture area of a 1920x1080 frame."""
    return img.crop((0, C.BAR, img.width, img.height - C.BAR))


def crop16x9(img, cx, cy=None, zoom=1.0):
    h = img.height / zoom
    w = h * 16 / 9
    cy = img.height / 2 if cy is None else cy
    x0 = min(max(cx - w / 2, 0), img.width - w)
    y0 = min(max(cy - h / 2, 0), img.height - h)
    return img.crop((int(x0), int(y0), int(x0 + w), int(y0 + h))).resize((W, H), Image.LANCZOS)


def punch(img, b=1.45, c=1.2, s=1.25):
    img = ImageEnhance.Brightness(img).enhance(b)
    img = ImageEnhance.Contrast(img).enhance(c)
    return ImageEnhance.Color(img).enhance(s)


def side_shade(img, left=True, strength=230, width=0.62):
    g = Image.new("L", (W, 1))
    for x in range(W):
        u = x / W if left else 1 - x / W
        g.putpixel((x, 0), int(strength * max(0.0, 1 - u / width) ** 1.4))
    g = g.resize((W, H))
    black = Image.new("RGB", (W, H), (0, 0, 0))
    return Image.composite(black, img, g)


def vignette(img, k=170):
    m = Image.new("L", (W, H), 0)
    d = ImageDraw.Draw(m)
    d.ellipse((-W * 0.15, -H * 0.25, W * 1.15, H * 1.25), fill=255)
    m = m.filter(ImageFilter.GaussianBlur(120))
    m = m.point(lambda v: 255 - int((255 - v) * k / 255))
    return Image.composite(img, Image.new("RGB", (W, H), (0, 0, 0)), m)


def text_shadow(base, xy, txt, font, fill, shadow=14, spacing=0, anchor="la", stroke=0):
    sh = Image.new("L", base.size, 0)
    ImageDraw.Draw(sh).text(xy, txt, font=font, fill=255, anchor=anchor, stroke_width=stroke + 6)
    sh = sh.filter(ImageFilter.GaussianBlur(shadow))
    base.paste(Image.new("RGB", base.size, (0, 0, 0)), (0, 0), sh.point(lambda v: min(255, v * 2)))
    ImageDraw.Draw(base).text(xy, txt, font=font, fill=fill, anchor=anchor,
                              stroke_width=stroke, stroke_fill=(0, 0, 0))


def stamp(base, cx, cy, txt="SOLD", size=120, angle=9):
    f = oswald(size, b"Bold")
    l, t, r, b = f.getbbox(txt)
    pad = size // 6
    im = Image.new("RGBA", (r - l + pad * 4, b - t + pad * 4), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rectangle((pad, pad, im.width - pad, im.height - pad), outline=RED + (255,), width=max(6, size // 14))
    d.text((im.width // 2, im.height // 2), txt, font=f, fill=RED + (255,), anchor="mm")
    # worn ink
    import random
    rnd = random.Random(7)
    a = im.split()[3]
    ad = ImageDraw.Draw(a)
    for _ in range(260):
        x, y = rnd.randrange(im.width), rnd.randrange(im.height)
        ad.ellipse((x, y, x + rnd.randint(1, 4), y + rnd.randint(1, 4)), fill=0)
    im.putalpha(a)
    im = im.rotate(angle, resample=Image.BICUBIC, expand=True)
    base.paste(im, (int(cx - im.width / 2), int(cy - im.height / 2)), im)


def brand(base, x, y, size=34):
    """Small icon + CALL OF ACARISTAN tag."""
    icon = Image.open(os.path.join(C.ART, "trailer_icon.png")).convert("RGBA")
    s = int(size * 1.9)
    icon = icon.resize((s, int(icon.height * s / icon.width)), Image.LANCZOS)
    base.paste(icon, (x, y - icon.height // 2), icon)
    f = oswald(size, b"SemiBold")
    tx = x + s + 14
    text_shadow(base, (tx, y), "CALL OF ACARISTAN", f, INK, shadow=8, anchor="lm")


def scope_disc(src, cx, cy, r, out_r):
    """Cut the circular scope view out of a Scopes frame."""
    disc = src.crop((cx - r, cy - r, cx + r, cy + r)).resize((out_r * 2, out_r * 2), Image.LANCZOS)
    m = Image.new("L", disc.size, 0)
    ImageDraw.Draw(m).ellipse((0, 0, out_r * 2 - 1, out_r * 2 - 1), fill=255)
    rgba = disc.convert("RGBA")
    rgba.putalpha(m)
    return rgba


def variant_a(tr):
    img = band(grab(tr, 17.0))
    img = img.filter(ImageFilter.MedianFilter(3))
    img = punch(crop16x9(img, cx=715, zoom=1.0), b=1.6, c=1.2, s=1.2)
    img = side_shade(img, left=True, strength=235, width=0.6)
    img = vignette(img)
    d = ImageDraw.Draw(img)
    d.rectangle((0, 0, W, 8), fill=ORANGE)
    text_shadow(img, (60, 70), "IT WAS", oswald(150), INK)
    text_shadow(img, (60, 240), "A SALE.", oswald(190), ORANGE)
    stamp(img, 300, 560, "SOLD", size=96, angle=8)
    brand(img, 62, 668, size=30)
    return img


def variant_b(tr):
    bg = band(grab(tr, 64.0))
    img = punch(crop16x9(bg, cx=1120, cy=330, zoom=1.0), b=1.6, c=1.15, s=1.1)
    img = img.filter(ImageFilter.GaussianBlur(4))
    img = side_shade(img, left=True, strength=245, width=0.75)
    img = vignette(img)
    sc = grab(tr, 69.5)
    disc = scope_disc(sc, cx=568, cy=528, r=322, out_r=230)
    glow = Image.new("L", (W, H), 0)
    gx, gy = 330, 380
    ImageDraw.Draw(glow).ellipse((gx - 250, gy - 250, gx + 250, gy + 250), fill=255)
    glow = glow.filter(ImageFilter.GaussianBlur(30))
    img.paste(Image.new("RGB", (W, H), ORANGE), (0, 0), glow.point(lambda v: v // 2))
    ring = ImageDraw.Draw(img)
    ring.ellipse((gx - 238, gy - 238, gx + 238, gy + 238), fill=(10, 10, 10))
    img.paste(disc, (gx - 230, gy - 230), disc)
    ring.ellipse((gx - 233, gy - 233, gx + 233, gy + 233), outline=(20, 20, 20), width=8)
    text_shadow(img, (W - 50, 120), "SOME ORDERS", oswald(104), INK, anchor="ra")
    text_shadow(img, (W - 50, 250), "YOU FINISH.", oswald(130), ORANGE, anchor="ra")
    brand(img, 700, 668, size=30)
    d = ImageDraw.Draw(img)
    d.rectangle((0, H - 8, W, H), fill=ORANGE)
    return img


def main():
    tr = render.Trailer()
    out = render.OUT_DIR
    for name, fn in (("A", variant_a), ("B", variant_b)):
        p = os.path.join(out, "thumbnail_%s.png" % name)
        fn(tr).save(p, optimize=True)
        print("->", p, os.path.getsize(p) // 1024, "KB")


if __name__ == "__main__":
    main()
