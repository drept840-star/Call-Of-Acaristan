"""Pack review images for remote viewing: prints one JSON line per image
{name, b64 JPEG}.  python tools/m5_view_export.py [--q 88] [--w 0] spec...
spec = path[@x,y,w,h][*zoom]   (crop in source px, then nearest-zoom).
Glob patterns allowed in path."""
import base64
import glob
import io
import json
import sys

from PIL import Image

args = sys.argv[1:]
q, maxw = 88, 0
specs = []
i = 0
while i < len(args):
    if args[i] == "--q":
        q = int(args[i + 1]); i += 2; continue
    if args[i] == "--w":
        maxw = int(args[i + 1]); i += 2; continue
    specs.append(args[i]); i += 1
for spec in specs:
    zoom = 1
    if "*" in spec.rsplit("@", 1)[-1] and not spec.endswith(".png") and not spec.endswith(".jpg"):
        spec, z = spec.rsplit("*", 1); zoom = int(z)
    crop = None
    if "@" in spec:
        spec, c = spec.rsplit("@", 1); crop = tuple(int(v) for v in c.split(","))
    paths = sorted(glob.glob(spec)) or [spec]
    if "%" in spec:                       # dir%0.5 -> the png at that fraction of the take
        d, fr = spec.rsplit("%", 1)
        pngs = sorted(glob.glob(d + "/*.png"))
        paths = [pngs[min(len(pngs) - 1, int(float(f) * len(pngs)))] for f in fr.split(",")]
    for p in paths:
        im = Image.open(p).convert("RGB")
        if crop:
            x, y, w, h = crop
            im = im.crop((x, y, x + w, y + h))
        if zoom > 1:
            im = im.resize((im.width * zoom, im.height * zoom), Image.NEAREST)
        if maxw and im.width > maxw:
            im = im.resize((maxw, int(im.height * maxw / im.width)), Image.LANCZOS)
        b = io.BytesIO()
        im.save(b, "JPEG", quality=q)
        print(json.dumps({"name": p.replace("\\", "/").split("/")[-1] + ("@%s" % (crop,) if crop else "") + ("x%d" % zoom if zoom > 1 else ""),
                          "b64": base64.b64encode(b.getvalue()).decode()}))
