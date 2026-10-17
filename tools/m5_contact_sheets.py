"""Build labelled contact sheets + automatic frame stats from previews/m5_encounter_review.
Usage: python tools/m5_contact_sheets.py [cols rows cellw]
Output: previews/m5_encounter_review/sheets/sheet_XX.jpg + stats.json
"""
import sys, json, pathlib
from PIL import Image, ImageDraw, ImageFont, ImageStat, ImageChops

ROOT = pathlib.Path(__file__).resolve().parents[1]
SRC = ROOT / 'previews' / 'm5_encounter_review'
OUT = SRC / 'sheets'
OUT.mkdir(exist_ok=True)
cols = int(sys.argv[1]) if len(sys.argv) > 1 else 4
rows = int(sys.argv[2]) if len(sys.argv) > 2 else 3
cellw = int(sys.argv[3]) if len(sys.argv) > 3 else 480

frames = sorted(SRC.glob('[0-9][0-9][0-9]_*.jpg'))
first = Image.open(frames[0])
cellh = int(cellw * first.height / first.width)
lab = 16
try:
    font = ImageFont.truetype('arial.ttf', 13)
except Exception:
    font = ImageFont.load_default()

stats = []
prev = None
for f in frames:
    im = Image.open(f).convert('RGB')
    g = im.convert('L')
    st = ImageStat.Stat(g)
    small = g.resize((64, 36))
    diff = None
    if prev is not None:
        diff = round(ImageStat.Stat(ImageChops.difference(small, prev)).mean[0], 2)
    prev = small
    stats.append(dict(file=f.name, mean=round(st.mean[0], 1), std=round(st.stddev[0], 1), diff_prev=diff))
(OUT / 'stats.json').write_text(json.dumps(stats, indent=1))

per = cols * rows
n_sheets = (len(frames) + per - 1) // per
for s in range(n_sheets):
    chunk = frames[s * per:(s + 1) * per]
    sheet = Image.new('RGB', (cols * cellw, rows * (cellh + lab)), (24, 24, 28))
    d = ImageDraw.Draw(sheet)
    for i, f in enumerate(chunk):
        x, y = (i % cols) * cellw, (i // cols) * (cellh + lab)
        im = Image.open(f).convert('RGB').resize((cellw - 2, cellh), Image.LANCZOS)
        sheet.paste(im, (x + 1, y + lab))
        d.text((x + 3, y + 1), f.stem, fill=(255, 220, 120), font=font)
    sheet.save(OUT / f'sheet_{s:02d}.jpg', quality=80)
print('frames', len(frames), 'sheets', n_sheets, 'cell', cellw, cellh)
print('size', first.size)
