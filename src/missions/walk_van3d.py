"""Walking sim: the KRAP extraction van as a real 3D model.

Renders assets/3D/krap_van.glb (tools/ae_import_krap_van.py ->
game/content/meshes/krap_van.mesh.json) with engine3d from a fixed, nearly
orthographic camera tilted PITCH degrees off the ground, so the roof, the south
flank with its lettering and the cab read in 3D while the sprite still sits on
the 2D walk map's collision rect (nose east).

The van idles, so each lamp state (dark / lit) is rendered once at SS x
resolution, keyed to alpha and smoothscaled down. Live bits (lamp glow,
exhaust, boarding cue) stay in walking_sim and use the projected anchor points
exposed here.  ``get()`` returns None when the asset or renderer is
unavailable (or ACA_ART=legacy|off); the caller then keeps the painted 2D van.
"""
import math
import os

import pygame

PX_PER_M = 23.4          # 168 px nose to tail = the 7.18 m model
SS = 2                   # render supersampling
CANVAS = (300, 230)      # final sprite size in px
PITCH = 62.0             # camera elevation above the ground plane, degrees
DIST = 45.0              # camera distance: long lens ~ orthographic
KEY = (255, 0, 255)
FRINGE = (12, 14, 18)    # RGB under transparent pixels so smoothscale edges stay dark

_cache = {}


class Van3D:
    __slots__ = ("images", "shadow", "origin", "shadow_off", "head", "tail", "rear",
                 "exhaust", "cue", "bbox", "backend")


def _lamp_color(group, lit):
    if group == 1:
        return (255, 246, 208) if lit else (150, 146, 124)
    return (255, 70, 56) if lit else (92, 24, 22)


def _build():
    from engine3d import Renderer, Mesh
    from game.render3d_bridge import load_mesh_asset

    verts, faces = load_mesh_asset("krap_van")
    vv = [tuple(v) for v in verts]
    body = Mesh()
    body.verts = vv
    lamps = []
    for idx, col, grp in faces:
        if grp in (1, 2):
            lamps.append((tuple(idx), grp))
        else:
            body.faces.append((tuple(idx), tuple(col), 3 if grp == 9 else 2, False, False))

    w, h = CANVAS[0] * SS, CANVAS[1] * SS
    r = Renderer(w, h, fog=(14, 16, 22), fog_start=900.0, fog_end=1400.0)
    r.light.dir = (-0.35, 0.85, -0.38)
    r.light.ambient, r.light.diffuse, r.light.sky = 0.66, 0.55, 0.08
    r.light.tint = (0.86, 0.93, 1.08)
    r.bake(body, tag="krap-van")

    target = (0.0, 0.9, 0.0)
    p = math.radians(PITCH)
    cam = (target[0], target[1] + DIST * math.sin(p), target[2] - DIST * math.cos(p))
    focal = PX_PER_M * SS * DIST
    fov = math.degrees(2 * math.atan((w / 2) / focal))
    r.set_camera(cam, target, fov)

    def proj(pt):
        q = r.project(pt)
        return (q[0] / SS, q[1] / SS)

    ground = proj((0.0, 0.0, 0.0))     # sprite anchor: ground centre of the van

    def rel(pt):
        q = proj(pt)
        return (q[0] - ground[0], q[1] - ground[1])

    def centroids(group):
        acc = {-1: [0, 0, 0, 0], 1: [0, 0, 0, 0]}
        for idx, grp in lamps:
            if grp != group:
                continue
            for i in idx:
                x, y, z = vv[i]
                a = acc[-1 if z < 0 else 1]
                a[0] += x; a[1] += y; a[2] += z; a[3] += 1
        return [rel((a[0] / a[3], a[1] / a[3], a[2] / a[3])) for a in acc.values() if a[3]]

    van = Van3D()
    van.backend = getattr(r, "backend", "?")
    van.head = centroids(1)
    van.tail = centroids(2)
    van.rear = rel((-3.7, 1.0, 0.0))
    van.exhaust = rel((-3.5, 0.35, -0.6))
    van.cue = rel((-5.2, 2.2, 0.0))
    van.origin = (-ground[0], -ground[1])      # blit offset from the ground anchor

    import numpy as np
    images = {}
    bbox = None
    for lit in (False, True):
        surf = pygame.Surface((w, h))
        surf.fill(KEY)
        lf = [(idx, _lamp_color(g, lit), 2, False, None, lit) for idx, g in lamps]
        r.begin()
        r.add_static()
        r.add_dynamic(vv, lf)
        r.flush(surf)
        rgb = pygame.surfarray.array3d(surf)
        bg = (rgb[:, :, 0] == KEY[0]) & (rgb[:, :, 1] == KEY[1]) & (rgb[:, :, 2] == KEY[2])
        rgb[bg] = FRINGE
        out = pygame.Surface((w, h), pygame.SRCALPHA)
        pygame.surfarray.blit_array(out, rgb)
        pygame.surfarray.pixels_alpha(out)[:] = np.where(bg, 0, 255).astype(np.uint8)
        img = pygame.transform.smoothscale(out, CANVAS).convert_alpha()
        images[lit] = img
        bbox = img.get_bounding_rect(min_alpha=8) if bbox is None else bbox.union(img.get_bounding_rect(min_alpha=8))
    van.images = images
    van.bbox = bbox
    if hasattr(r, "release"):
        r.release()

    # Soft ground shadow, offset down-right like the container shadows.
    sh = pygame.Surface((196, 84), pygame.SRCALPHA)
    pygame.draw.ellipse(sh, (0, 0, 0, 70), (0, 0, 196, 84))
    pygame.draw.ellipse(sh, (0, 0, 0, 80), (10, 10, 176, 62))
    van.shadow = sh
    van.shadow_off = (-98 + 8, -42 + 10)
    return van


def get():
    """Baked Van3D, or None (asset/renderer missing, or the 2D-only art switch)."""
    if "van" in _cache:
        return _cache["van"]
    van = None
    if os.environ.get("ACA_ART", "").strip().lower() not in ("legacy", "off"):
        try:
            van = _build()
        except Exception as exc:  # any renderer/asset failure -> keep the painted van
            print("walk_van3d: 3D van unavailable (%s: %s)" % (type(exc).__name__, exc))
            van = None
    _cache["van"] = van
    return van


def warm():
    """Bake now (call while a transition covers the screen)."""
    return get()
