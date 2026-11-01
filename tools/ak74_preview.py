"""AK-74 preview - renders the code-authored weapon so it can be eyeballed.

    python tools/ak74_preview.py                 # turntable + a soldier holding it
    python tools/ak74_preview.py --compare       # also: new vs the imported asset
    python tools/ak74_preview.py --finish poly   # rebuild in memory, no rebake
    python tools/ak74_preview.py --gl            # render on the GL backend too

Writes outputs/ak74/*.png.  Faces are submitted single-sided on purpose: a
wound-back quad then lights as a black hole, so the preview doubles as the
normal-orientation check for tools/ae_build_ak74.py.
"""
import argparse
import json
import math
import os
import sys

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))
sys.path.insert(0, os.path.join(ROOT, "tools"))
os.chdir(ROOT)

import pygame  # noqa: E402

OUTDIR = os.path.join("outputs", "ak74")
# gun-space centre of interest: the gun runs z -0.31..0.63, y -0.19..0.10
CENTRE = (0.0, -0.02, 0.16)

# name, size, eye, target, fov
VIEWS = (
    ("side_right", (1000, 320), (2.40, 0.00, 0.16), CENTRE, 26.0),
    ("side_left", (1000, 320), (-2.40, 0.00, 0.16), CENTRE, 26.0),
    ("three_quarter", (900, 460), (1.35, 0.42, 1.30), CENTRE, 30.0),
    ("three_quarter_low", (900, 460), (1.10, -0.30, 1.20), CENTRE, 30.0),
    ("top", (900, 560), (0.10, 1.90, 0.06), CENTRE, 30.0),
    ("muzzle", (620, 520), (0.28, 0.10, 2.10), (0.0, 0.0, 0.30), 26.0),
    ("stock", (620, 520), (-0.30, 0.06, -1.55), (0.0, -0.02, -0.10), 26.0),
)


def _from_bake(name="ak74"):
    """Baked ae.mesh/1 asset -> (verts, faces, meta)."""
    from game.render3d_bridge import MESHES_DIR
    with open(os.path.join(MESHES_DIR, "%s.mesh.json" % name), encoding="utf-8") as fh:
        d = json.load(fh)
    return ([tuple(v) for v in d["verts"]],
            [(tuple(f[0]), tuple(f[1]), 2, False, None, False) for f in d["faces"]],
            d["meta"])


def _from_source(finish, length=0.940):
    """Run the generator in memory (no rebake) -> the same triple."""
    import ae_build_ak74 as B
    import ae_import_k93d as K
    verts, tris, meta = B.build(finish, length)
    out_v, out_f = K._cluster(verts, tris, 0.004)
    return ([tuple(v) for v in out_v],
            [(tuple(f[0]), tuple(f[1]), 2, False, None, False) for f in out_f],
            meta)


def _offset(item, dx=0.0, dy=0.0, dz=0.0):
    verts, faces, meta = item
    return ([(x + dx, y + dy, z + dz) for x, y, z in verts], faces, meta)


def _ascii(surf, bg=(28, 30, 36), cols=148, luma=False):
    """Silhouette -> characters, so the profile can be read without an image
    viewer.  Cells are ~2:1 tall, hence the /2 on the row count."""
    rows = max(8, int(surf.get_height() * cols / surf.get_width() / 2.0))
    s = pygame.transform.scale(surf, (cols, rows))
    px = pygame.surfarray.array3d(s).transpose(1, 0, 2).astype(int)
    out = []
    ramp = " .:-=+*#%@"
    for y in range(rows):
        line = []
        for x in range(cols):
            r, g, b = px[y, x]
            if max(abs(r - bg[0]), abs(g - bg[1]), abs(b - bg[2])) <= 6:
                line.append(" ")
            elif luma:
                lum = (0.299 * r + 0.587 * g + 0.114 * b) / 255.0
                line.append(ramp[min(len(ramp) - 1, int(lum * len(ramp)))])
            else:
                line.append("#")
        out.append("".join(line).rstrip())
    return "\n".join(out)


def _silhouette(surf, bg):
    """Non-background pixel stats: bounding box and fill, in surface pixels."""
    import numpy as np
    a = pygame.surfarray.array3d(surf).transpose(1, 0, 2).astype(np.int16)
    mask = (np.abs(a - np.array(bg, dtype=np.int16)).max(axis=2) > 6)
    ys, xs = np.nonzero(mask)
    if not len(xs):
        return None
    return dict(x0=int(xs.min()), x1=int(xs.max()), y0=int(ys.min()), y1=int(ys.max()),
                w=int(xs.max() - xs.min() + 1), h=int(ys.max() - ys.min() + 1),
                fill=float(mask.mean()), count=int(mask.sum()))


def _check_winding(items, backend="software"):
    """Compare a single-sided against a double-sided render of each mesh.

    ``ae_build_ak74`` writes outward normals by construction (profiles run CCW
    from +z), so a wound-back quad gets *culled* when single-sided and the
    silhouette loses a piece.  Comparing the masks catches that.  Comparing
    colours does not: a closed solid always shades differently once its
    interior and far-side faces are submitted too, so the imported ``akrifle``
    rides along as the baseline for how much colour diff is just the renderer.
    ``array3d`` is indexed [x, y], hence the transposes."""
    import numpy as np
    eye, tgt, fov, w, h, bg = (2.40, 0.00, 0.16), CENTRE, 26.0, 1000, 320, (28, 30, 36)
    bgv = np.array(bg, dtype=np.int16)
    bad = 0
    for label, item in items:
        verts, faces, meta = item
        dbl = [(i, c, l, True, u, e) for i, c, l, _d, u, e in faces]
        a = pygame.surfarray.array3d(_shot(w, h, [(verts, faces, None)], eye, tgt, fov,
                                           bg=bg, backend=backend)).transpose(1, 0, 2).astype(np.int16)
        b = pygame.surfarray.array3d(_shot(w, h, [(verts, dbl, None)], eye, tgt, fov,
                                           bg=bg, backend=backend)).transpose(1, 0, 2).astype(np.int16)
        ma = np.abs(a - bgv).max(axis=2) > 6
        mb = np.abs(b - bgv).max(axis=2) > 6
        lost = int((mb & ~ma).sum())      # coverage only the culled pass had
        gained = int((ma & ~mb).sum())
        shade = float((np.abs(a - b).max(axis=2) > 8).mean())
        bad += lost
        print("  %-20s silhouette %5d px | lost single-sided %4d | extra %4d "
              "| shading diff %.2f%% -> %s"
              % (label, int(ma.sum()), lost, gained, shade * 100,
                 "OK" if lost == 0 else "CHECK (back-facing quads)"))
        if lost:
            ys, xs = np.nonzero(mb & ~ma)
            focal = (w / 2.0) / math.tan(math.radians(fov) / 2.0)
            z_of = lambda px: CENTRE[2] + (px - w / 2.0) * 2.40 / focal
            print("       holes over z %+.3f .. %+.3f m   (gun runs %+.3f .. %+.3f)"
                  % (z_of(xs.min()), z_of(xs.max()), meta["butt"][2], meta["muzzle"][2]))
    return bad


def _shot(w, h, items, eye, tgt, fov=28.0, bg=(28, 30, 36),
          light=(0.58, 0.72, 0.40), backend="software"):
    from engine3d.core import Light, SoftwareRenderer
    from engine3d.gl import GLRenderer
    cls = GLRenderer if backend == "gl" else SoftwareRenderer
    try:
        r = cls(w, h, fog=(38, 40, 46), fog_start=90.0, fog_end=260.0)
    except Exception as exc:                      # no GPU -> software
        if cls is SoftwareRenderer:
            raise
        print("  (%s unavailable: %s)" % (backend, exc))
        r = SoftwareRenderer(w, h, fog=(38, 40, 46), fog_start=90.0, fog_end=260.0)
    r.light = Light(direction=light, ambient=0.46, diffuse=0.58, sky=0.06)
    r.set_camera(eye, tgt, fov)
    r.surface.fill(bg)
    r.begin()
    r.add_static()
    for verts, faces, _meta in items:
        r.add_dynamic(verts, faces)
    r.flush(r.surface)
    return r.surface.copy()


def _stack(surfs, gap=8, bg=(18, 19, 23)):
    w = max(s.get_width() for s in surfs)
    h = sum(s.get_height() for s in surfs) + gap * (len(surfs) - 1)
    out = pygame.Surface((w, h))
    out.fill(bg)
    y = 0
    for s in surfs:
        out.blit(s, ((w - s.get_width()) // 2, y))
        y += s.get_height() + gap
    return out


def _turntable(item, backend):
    shots = []
    for name, size, eye, tgt, fov in VIEWS:
        surf = _shot(size[0], size[1], [item], eye, tgt, fov, backend=backend)
        shots.append((name, surf))
        print("  %-18s %dx%d" % (name, size[0], size[1]))
    return shots


def _held(item, meta, backend, mesh=None):
    """A soldier carrying it, through the real cast3d + engine3d.hold path.

    ``mesh`` overrides the rig rifle so an in-memory ``--finish`` build can be
    held without rebaking the asset."""
    from cutscenes.cast3d import humanoid3d
    from engine3d import POSES
    from engine3d.core import Light, SoftwareRenderer, quad_xz
    from engine3d.gl import GLRenderer
    from engine3d.hold import hold_cached, hold_report

    ground = quad_xz(-2.5, -2.5, 2.5, 2.5, 0.0, (44, 46, 52), layer=0)
    gfaces = [(f[0], f[1], f[2], f[3], None, f[4]) for f in ground.faces]
    out = []
    # (name, body pose, hold mode, yaw, eye).  Hold modes are not poses: "port"
    # is a way of carrying the gun, so it rides on the neutral stand pose.
    for name, pose_name, mode, yaw, eye in (
            ("aim", "aim", "aim", 0.55, (1.9, 1.05, 2.5)),
            ("ready", "ready", "ready", -0.45, (-2.0, 0.95, 2.3)),
            ("port", "stand", "port", 0.20, (0.2, 1.05, -2.9)),
            ("carry", "stand", "carry", -0.85, (2.2, 0.95, -1.8))):
        hum = humanoid3d("krap", rifle="ak74")
        if getattr(hum, "_weapon", None) != "ak74":
            raise SystemExit("AK74 PREVIEW: FAIL (cast3d did not attach rifle='ak74')")
        if mesh is not None:
            hum._rifle = mesh
        pose = hold_cached(hum, dict(POSES[pose_name]), "ak74", mode)
        rep = hold_report(hum, pose, (0.0, 0.0, 0.0), 0.0, "ak74")
        print("  hold %-6s support gap %s m   arm clash %.3f m   rifle in body %.3f m"
              % (mode, "n/a" if rep["support"] is None else "%.3f" % rep["support"],
                 rep["arm"], rep["rifle"] or 0.0))
        cls = GLRenderer if backend == "gl" else SoftwareRenderer
        try:
            r = cls(760, 620, fog=(38, 40, 46), fog_start=90.0, fog_end=260.0)
        except Exception as exc:
            if cls is SoftwareRenderer:
                raise
            print("  (%s unavailable: %s)" % (backend, exc))
            r = SoftwareRenderer(760, 620, fog=(38, 40, 46), fog_start=90.0, fog_end=260.0)
        r.light = Light(direction=(0.50, 0.74, 0.44), ambient=0.46, diffuse=0.58, sky=0.06)
        r.set_camera(eye, (0.0, 0.95, 0.0), 34.0)
        r.surface.fill((28, 30, 36))
        r.begin()
        r.add_static()
        r.add_dynamic(ground.verts, gfaces)
        r.add_humanoid(hum, pose, (0.0, 0.0, 0.0), yaw, rifle_on=True)
        r.flush(r.surface)
        out.append(("held_" + mode, r.surface.copy()))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--finish", default=None, choices=("wood", "plum", "poly"),
                    help="rebuild in memory from the generator instead of the bake")
    ap.add_argument("--length", type=float, default=0.940)
    ap.add_argument("--compare", action="store_true",
                    help="also render the imported akrifle asset for comparison")
    ap.add_argument("--gl", action="store_true", help="render on the GL backend too")
    ap.add_argument("--no-held", action="store_true", help="skip the soldier shots")
    ap.add_argument("--ascii", action="store_true",
                    help="print the side profile as characters (no image viewer needed)")
    ap.add_argument("--ascii-cols", type=int, default=148,
                    help="width of the --ascii dump (also written to outputs/ak74/profile.txt)")
    ap.add_argument("--winding", action="store_true",
                    help="diff a single-sided against a double-sided render")
    args = ap.parse_args()

    pygame.init()
    pygame.display.set_mode((320, 200))
    os.makedirs(OUTDIR, exist_ok=True)

    item = (_from_source(args.finish, args.length) if args.finish else _from_bake("ak74"))
    verts, faces, meta = item
    print("AK74 PREVIEW: %d tris / %d verts  (%s)"
          % (len(faces), len(verts), "finish " + args.finish if args.finish else "baked asset"))
    print("  muzzle %s  butt %s  guard %s  fore %s"
          % (meta["muzzle"], meta["butt"], meta["guard"], meta["fore"]))

    # Silhouette check: the gun-space extremes the generator claims, against
    # what the rasteriser actually covers.  A part built inside-out or offset
    # shows up here before anyone looks at a PNG.
    xs = [v[0] for v in verts]; ys = [v[1] for v in verts]; zs = [v[2] for v in verts]
    print("  extents (m): x %+.3f..%+.3f  y %+.3f..%+.3f  z %+.3f..%+.3f"
          % (min(xs), max(xs), min(ys), max(ys), min(zs), max(zs)))
    print("  overall length %.3f m   profile height %.3f m   ratio %.2f"
          % (max(zs) - min(zs), max(ys) - min(ys),
             (max(zs) - min(zs)) / max(1e-6, max(ys) - min(ys))))
    if args.winding:
        pairs = [("ak74 (authored)", item)]
        try:
            pairs.append(("akrifle (imported)", _from_bake("akrifle")))
        except Exception:
            pass
        _check_winding(pairs)
    if args.ascii:
        bg = (28, 30, 36)
        surf = _shot(1000, 320, [item], (2.40, 0.00, 0.16), CENTRE, 26.0, bg=bg)
        sil = _silhouette(surf, bg)
        print("  side silhouette: %dx%d px at (%d,%d), %.2f%% of frame, ratio %.2f"
              % (sil["w"], sil["h"], sil["x0"], sil["y0"], sil["fill"] * 100,
                 sil["w"] / max(1, sil["h"])))
        art = _ascii(surf, bg, cols=args.ascii_cols)
        path = os.path.join(OUTDIR, "profile.txt")
        with open(path, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(art + "\n")
        print(art)
        print("  ->", path)

    backends = ["software", "gl"] if args.gl else ["software"]
    hold_mesh = None
    if args.finish:
        from engine3d.core import Mesh
        hold_mesh = Mesh()
        hold_mesh.verts = [tuple(v) for v in verts]
        hold_mesh.faces = [(tuple(f[0]), tuple(f[1]), 2, False, False) for f in faces]
    for backend in backends:
        tag = "" if backend == "software" else "_gl"
        print("backend:", backend)
        for name, surf in _turntable(item, backend):
            pygame.image.save(surf, os.path.join(OUTDIR, "%s%s.png" % (name, tag)))
        if not args.no_held:
            for name, surf in _held(item, meta, backend, hold_mesh):
                pygame.image.save(surf, os.path.join(OUTDIR, "%s%s.png" % (name, tag)))
        if args.compare:
            old = _from_bake("akrifle")
            pair, labels = [], ("ak74 (authored, top)", "akrifle (imported, bottom)")
            for label, it in zip(labels, (item, old)):
                pair.append(_shot(1000, 320, [it], (2.40, 0.00, 0.16), CENTRE, 26.0,
                                  backend=backend))
                print("  compare:", label)
            pygame.image.save(_stack(pair), os.path.join(OUTDIR, "compare_profile%s.png" % tag))
        print("  ->", OUTDIR)
    return 0


if __name__ == "__main__":
    sys.exit(main())
