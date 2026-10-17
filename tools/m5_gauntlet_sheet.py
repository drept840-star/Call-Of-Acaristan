"""Compact WebP contact sheet for remote VLM review.

python tools/m5_gauntlet_sheet.py TILE_W name1 name2[@x,y,w,h] ...
Reads PNGs from tools/m5_r2_shots/, tiles 2 columns, prints base64 WebP
between B64START/B64END markers (labels each tile with its name).
"""
import base64
import io
import os
import sys

from PIL import Image, ImageDraw

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SHOTS = os.path.join(ROOT, "tools", "m5_r2_shots")


def main():
    tw = int(sys.argv[1])
    names = sys.argv[2:]
    q = int(os.environ.get("M5_Q", "55"))
    cols = 2 if len(names) > 1 else 1
    th = int(tw * float(os.environ.get("M5_AR", "0.7")))
    film = os.environ.get("M5_CROP")          # e.g. 0,88,1000,454 applied to every tile
    if film:
        names = [n if "@" in n else n + "@" + film for n in names]
    rows = (len(names) + cols - 1) // cols
    sheet = Image.new("RGB", (tw * cols, th * rows))
    d = ImageDraw.Draw(sheet)
    for i, n in enumerate(names):
        crop = None
        if "@" in n:
            n, c = n.split("@")
            x, y, w, h = [int(v) for v in c.split(",")]
            crop = (x, y, x + w, y + h)
        img = Image.open(os.path.join(SHOTS, n + ".png")).convert("RGB")
        if crop:
            img = img.crop(crop)
        img = img.resize((tw, th), Image.LANCZOS)
        ox, oy = (i % cols) * tw, (i // cols) * th
        sheet.paste(img, (ox, oy))
        d.rectangle((ox, oy, ox + 8 * len(n) + 6, oy + 14), fill=(0, 0, 0))
        d.text((ox + 3, oy + 2), n, fill=(255, 255, 0))
    b = io.BytesIO()
    sheet.save(b, "WEBP", quality=q, method=6)
    # leading pad keeps remote tool-result previews cheap (preview = first ~19k chars)
    print(" " * int(os.environ.get("M5_PAD", "19000")) + "B64START" + base64.b64encode(b.getvalue()).decode() + "B64END")


if __name__ == "__main__":
    main()
