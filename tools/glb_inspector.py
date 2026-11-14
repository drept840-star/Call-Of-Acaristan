#!/usr/bin/env python3
"""GLB Inspector - desktop viewer for .glb / .gltf files.

Shows the node tree, exact world/local bounds, transforms, materials and colours
(base factors, texture palettes, vertex colours) without dumping vertex arrays,
next to an orbitable preview. Click a node in the list or in the viewport.

Run:   python tools/glb_inspector.py [model.glb]
Check: python tools/glb_inspector.py --selftest
Drop a file on the window, or press O to open one.
"""
import base64
import io
import json
import math
import os
import re
import struct
import sys
import tempfile
from collections import defaultdict
from urllib.parse import unquote

import numpy as np
import pygame

COMP = {5120: np.int8, 5121: np.uint8, 5122: np.int16, 5123: np.uint16, 5125: np.uint32, 5126: np.float32}
NCOMP = {"SCALAR": 1, "VEC2": 2, "VEC3": 3, "VEC4": 4, "MAT2": 4, "MAT3": 9, "MAT4": 16}
MODES = {0: "POINTS", 1: "LINES", 2: "LINE_LOOP", 3: "LINE_STRIP", 4: "TRIANGLES", 5: "TRIANGLE_STRIP", 6: "TRIANGLE_FAN"}


# ---------------------------------------------------------------- math helpers

def quat_mat(q):
    x, y, z, w = q
    return np.array([
        [1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w), 0],
        [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w), 0],
        [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y), 0],
        [0, 0, 0, 1]], dtype=np.float64)


def quat_euler_deg(q):
    x, y, z, w = q
    ex = math.atan2(2 * (w * x + y * z), 1 - 2 * (x * x + y * y))
    ey = math.asin(max(-1.0, min(1.0, 2 * (w * y - z * x))))
    ez = math.atan2(2 * (w * z + x * y), 1 - 2 * (y * y + z * z))
    return [math.degrees(v) for v in (ex, ey, ez)]


def local_matrix(n):
    if "matrix" in n:
        return np.array(n["matrix"], np.float64).reshape(4, 4).T
    t = np.eye(4)
    t[:3, 3] = n.get("translation", [0, 0, 0])
    s = np.diag(list(n.get("scale", [1, 1, 1])) + [1.0])
    return t @ quat_mat(n.get("rotation", [0, 0, 0, 1])) @ s


def perspective(fovy, aspect, near, far):
    t = 1 / math.tan(fovy / 2)
    return np.array([[t / aspect, 0, 0, 0], [0, t, 0, 0],
                     [0, 0, (far + near) / (near - far), 2 * far * near / (near - far)], [0, 0, -1, 0]])


def look_at(eye, tgt, up=(0, 1, 0)):
    f = tgt - eye
    f = f / np.linalg.norm(f)
    s = np.cross(f, up)
    s = s / np.linalg.norm(s)
    u = np.cross(s, f)
    m = np.eye(4)
    m[0, :3], m[1, :3], m[2, :3] = s, u, -f
    m[:3, 3] = -m[:3, :3] @ eye
    return m


def gl_mat(m):
    return m.T.astype("f4").tobytes()  # GL wants column-major


def lin2srgb(c):
    c = max(0.0, min(1.0, float(c)))
    return c * 12.92 if c <= 0.0031308 else 1.055 * c ** (1 / 2.4) - 0.055


def hex_lin(f):
    """Linear factor -> sRGB hex, the same hex Blender's colour picker shows."""
    return "#%02X%02X%02X" % tuple(round(lin2srgb(x) * 255) for x in f[:3])


def to_srgb8(c):
    c = np.clip(c, 0, 1)
    rgb = np.where(c[:, :3] <= 0.0031308, c[:, :3] * 12.92, 1.055 * np.power(c[:, :3], 1 / 2.4) - 0.055)
    return (np.hstack([rgb, c[:, 3:4]]) * 255 + 0.5).astype(np.uint8)


def top_colors(rgba, k=8):
    """(unique count, [(hex, alpha, count)]) for an Nx4 uint8 array."""
    if len(rgba) > 1_000_000:  # shortcut: sampled past 1M px, exact counts would need the full sort
        rgba = rgba[:: len(rgba) // 1_000_000 + 1]
    v = rgba.astype(np.uint32)
    key = (v[:, 0] << 24) | (v[:, 1] << 16) | (v[:, 2] << 8) | v[:, 3]
    u, cnt = np.unique(key, return_counts=True)
    order = np.argsort(-cnt)[:k]
    top = [("#%06X" % (int(x) >> 8), int(x) & 255, int(n)) for x, n in zip(u[order], cnt[order])]
    return len(u), top


def bounds_dict(mn, mx):
    return {"size": mx - mn, "center": (mn + mx) / 2, "min": mn, "max": mx}


def clean(o):
    """numpy -> plain lists, floats rounded to 6 places (for JSON and display)."""
    if isinstance(o, dict):
        return {k: clean(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [clean(v) for v in o]
    if isinstance(o, np.ndarray):
        return clean(o.tolist())
    if isinstance(o, (float, np.floating)):
        return round(float(o), 6)
    if isinstance(o, np.integer):
        return int(o)
    return o


def triangulate(idx, mode):
    if mode == 4:
        return idx[: len(idx) // 3 * 3]
    if mode == 5:
        k = np.arange(max(0, len(idx) - 2))
        return np.stack([idx[k], idx[k + 1], idx[k + 2]], 1).ravel()
    if mode == 6:
        k = np.arange(1, max(1, len(idx) - 1))
        return np.stack([np.full_like(k, idx[0]) if len(idx) else k, idx[k], idx[k + 1]], 1).ravel()
    return None  # points/lines: counted, not drawn


# ---------------------------------------------------------------- glTF model

class Model:
    def __init__(self, path):
        self.path = path
        self.base = os.path.dirname(os.path.abspath(path))
        with open(path, "rb") as f:
            raw = f.read()
        self.file_size = len(raw)
        self.bin = None
        if raw[:4] == b"glTF":
            version, length = struct.unpack_from("<II", raw, 4)
            self.container = f"GLB v{version}"
            off, self.j = 12, None
            while off + 8 <= len(raw):
                clen, ctype = struct.unpack_from("<II", raw, off)
                data = raw[off + 8: off + 8 + clen]
                if ctype == 0x4E4F534A:
                    self.j = json.loads(data.decode("utf-8"))
                elif ctype == 0x004E4942 and self.bin is None:
                    self.bin = data
                off += 8 + clen
            if self.j is None:
                raise ValueError("GLB has no JSON chunk")
        else:
            self.container = "glTF (JSON)"
            self.j = json.loads(raw.decode("utf-8-sig"))
        j = self.j
        self._acc = {}
        self.buffers = [self._uri(b["uri"]) if "uri" in b else (self.bin or b"") for b in j.get("buffers", [])]
        self.nodes = j.get("nodes", [])
        self.parent = [None] * len(self.nodes)
        for i, n in enumerate(self.nodes):
            for c in n.get("children", []):
                self.parent[c] = i
        scenes = j.get("scenes", [])
        self.scene = j.get("scene", 0)
        self.roots = scenes[self.scene].get("nodes", []) if scenes else [i for i, p in enumerate(self.parent) if p is None]
        self.joints = {jn for s in j.get("skins", []) for jn in s.get("joints", [])}

        self.world = self._world({})
        self.images = [self._image(k, im) for k, im in enumerate(j.get("images", []))]
        self.prims = {mi: [self._prim(mi, pi) for pi in range(len(m.get("primitives", [])))]
                      for mi, m in enumerate(j.get("meshes", []))}

        self.wb = {}  # node -> world AABB of its own mesh
        for i, M in self.world.items():
            pts = [p["pos"] for p in self.prims.get(self.nodes[i].get("mesh"), []) if len(p["pos"])]
            if pts:
                P = np.vstack(pts).astype(np.float64) @ M[:3, :3].T + M[:3, 3]
                self.wb[i] = (P.min(0), P.max(0))
        self.tb = {}  # node -> world AABB of node + descendants
        for r in self.roots:
            self._subtree(r)
        boxes = [self.tb[r] for r in self.roots if r in self.tb]
        self.bounds = (np.min([b[0] for b in boxes], 0), np.max([b[1] for b in boxes], 0)) if boxes else None

    def _world(self, over):
        """node -> world matrix; over = {node: {"translation"|"rotation"|"scale": value}} from an animation."""
        world, stack = {}, [(r, np.eye(4)) for r in self.roots]
        while stack:
            i, pm = stack.pop()
            world[i] = pm @ local_matrix({**self.nodes[i], **over[i]} if i in over else self.nodes[i])
            stack += [(c, world[i]) for c in self.nodes[i].get("children", [])]
        return world

    # -- animation
    def anim_dur(self, ai):
        a = self.j["animations"][ai]
        return max((float(self.accessor(s["input"]).max()) for s in a.get("samplers", [])), default=0.0)

    def sample(self, s, t, rot):
        times = self.accessor(s["input"]).ravel()
        vals = self.accessor(s["output"]).astype(np.float64)
        interp = s.get("interpolation", "LINEAR")
        if interp == "CUBICSPLINE":  # shortcut: tangents ignored, keys sampled linearly; fine for previews
            vals = vals[1::3]
        if t <= times[0] or len(times) == 1:
            return vals[0]
        if t >= times[-1]:
            return vals[len(times) - 1]
        k = int(np.searchsorted(times, t)) - 1
        if interp == "STEP":
            return vals[k]
        u = (t - times[k]) / max(times[k + 1] - times[k], 1e-9)
        a, b = vals[k], vals[k + 1]
        if rot:  # nlerp along the short arc
            b = -b if np.dot(a, b) < 0 else b
            q = a * (1 - u) + b * u
            return q / np.linalg.norm(q)
        return a * (1 - u) + b * u

    def pose(self, ai, t):
        """World matrices for animation ai at time t (node TRS only; skins and morph weights not applied)."""
        a, over = self.j["animations"][ai], defaultdict(dict)
        for ch in a.get("channels", []):
            tg = ch["target"]
            if "node" in tg and tg.get("path") in ("translation", "rotation", "scale"):
                over[tg["node"]][tg["path"]] = self.sample(a["samplers"][ch["sampler"]], t, tg["path"] == "rotation")
        return self._world(over)

    # -- raw data access
    def _uri(self, uri):
        if uri.startswith("data:"):
            return base64.b64decode(uri.split(",", 1)[1])
        with open(os.path.join(self.base, unquote(uri)), "rb") as f:
            return f.read()

    def _view(self, i):
        bv = self.j["bufferViews"][i]
        o = bv.get("byteOffset", 0)
        return memoryview(self.buffers[bv["buffer"]])[o: o + bv["byteLength"]], bv.get("byteStride")

    def accessor(self, i):
        if i in self._acc:
            return self._acc[i]
        a = self.j["accessors"][i]
        dt, n, count = np.dtype(COMP[a["componentType"]]), NCOMP[a["type"]], a["count"]
        if "bufferView" in a:
            data, stride = self._view(a["bufferView"])
            arr = np.ndarray((count, n), dt, buffer=data, offset=a.get("byteOffset", 0),
                             strides=(stride or dt.itemsize * n, dt.itemsize)).copy()
        else:
            arr = np.zeros((count, n), dt)
        sp = a.get("sparse")
        if sp:
            ii, iv = sp["indices"], sp["values"]
            d, _ = self._view(ii["bufferView"])
            idx = np.frombuffer(d, COMP[ii["componentType"]], sp["count"], ii.get("byteOffset", 0))
            d, _ = self._view(iv["bufferView"])
            arr[idx] = np.frombuffer(d, dt, sp["count"] * n, iv.get("byteOffset", 0)).reshape(-1, n)
        if a.get("normalized") and dt.kind in "iu":
            arr = np.maximum(arr.astype(np.float32) / np.iinfo(dt).max, -1.0)
        self._acc[i] = arr
        return arr

    def _image(self, k, im):
        info = {"name": im.get("name") or os.path.basename(unquote(im.get("uri", ""))) or f"image {k}",
                "mime": im.get("mimeType", "?"), "rgba": None, "err": None}
        try:
            data = bytes(self._view(im["bufferView"])[0]) if "bufferView" in im else self._uri(im["uri"])
            info["bytes"] = len(data)
            s = pygame.image.load(io.BytesIO(data))
            info["size"] = s.get_size()
            info["rgba"] = pygame.image.tobytes(s, "RGBA")
            px = np.frombuffer(info["rgba"], np.uint8).reshape(-1, 4)
            info["avg"] = px.mean(0)
            info["unique"], info["top"] = top_colors(px)
        except Exception as e:  # a broken texture must not stop the inspection
            info["err"] = str(e)
        return info

    def _prim(self, mi, pi):
        p = self.j["meshes"][mi]["primitives"][pi]
        at = p.get("attributes", {})
        mode = p.get("mode", 4)
        d = {"mode": MODES.get(mode, str(mode)), "material": p.get("material"), "attributes": sorted(at),
             "targets": len(p.get("targets", [])), "vbo": None, "pos": np.zeros((0, 3), np.float32),
             "tris": 0, "verts": 0}
        if "POSITION" not in at:
            return d
        pos = self.accessor(at["POSITION"])[:, :3].astype(np.float32)
        idx = self.accessor(p["indices"]).ravel().astype(np.int64) if "indices" in p else np.arange(len(pos))
        tri = triangulate(idx, mode)
        d.update(pos=pos, verts=len(pos), tris=0 if tri is None else len(tri) // 3, indices=len(idx))
        col = None
        if "COLOR_0" in at:
            col = self.accessor(at["COLOR_0"]).astype(np.float32)
            if col.shape[1] == 3:
                col = np.hstack([col, np.ones((len(col), 1), np.float32)])
            d["vcolors"] = top_colors(to_srgb8(col))
        if tri is not None and len(tri):
            P = pos[tri]
            if "NORMAL" in at:
                N = self.accessor(at["NORMAL"])[:, :3].astype(np.float32)[tri]
            else:
                a, b, c = P[0::3], P[1::3], P[2::3]
                fn = np.cross(b - a, c - a)
                fn /= np.maximum(np.linalg.norm(fn, axis=1, keepdims=True), 1e-12)
                N = np.repeat(fn, 3, 0)
            UV = self.accessor(at["TEXCOORD_0"])[:, :2].astype(np.float32)[tri] if "TEXCOORD_0" in at \
                else np.zeros((len(tri), 2), np.float32)
            C = col[tri] if col is not None else np.ones((len(tri), 4), np.float32)
            d["vbo"] = np.hstack([P, N, UV, C]).astype(np.float32)
        return d

    def _subtree(self, i):
        boxes = [self.wb[i]] if i in self.wb else []
        for c in self.nodes[i].get("children", []):
            b = self._subtree(c)
            if b:
                boxes.append(b)
        if boxes:
            self.tb[i] = (np.min([b[0] for b in boxes], 0), np.max([b[1] for b in boxes], 0))
        return self.tb.get(i)

    # -- reports (shared by the UI, Copy and Export)
    def name(self, i):
        return self.nodes[i].get("name") or f"node {i}"

    def tex_image(self, ti):
        t = self.j.get("textures", [])[ti]
        src = t.get("source")
        for e in t.get("extensions", {}).values():
            src = e.get("source", src)
        return src, t.get("sampler")

    def mat_label(self, mi):
        if mi is None:
            return "default (white)"
        m = self.j["materials"][mi]
        f = m.get("pbrMetallicRoughness", {}).get("baseColorFactor", [1, 1, 1, 1])
        return f"{mi} {m.get('name', '')}  {hex_lin(f)}"

    def summary(self):
        j, a = self.j, self.j.get("asset", {})
        drawn = [(i, p) for i in self.world for p in self.prims.get(self.nodes[i].get("mesh"), [])]
        s = {"file": os.path.basename(self.path), "file_bytes": self.file_size, "container": self.container,
             "gltf_version": a.get("version"), "generator": a.get("generator", "-"),
             "scene": f"{self.scene} of {len(j.get('scenes', []))}",
             "counts": {k: len(j.get(k, [])) for k in ("nodes", "meshes", "materials", "textures", "images",
                                                        "skins", "animations", "cameras")},
             "drawn": {"triangles": sum(p["tris"] for _, p in drawn), "vertices": sum(p["verts"] for _, p in drawn),
                       "draw_calls": len(drawn)}}
        if self.bounds:
            s["scene_bounds_m"] = bounds_dict(*self.bounds)
        for k in ("extensionsUsed", "extensionsRequired"):
            if k in j:
                s[k] = j[k]
        return clean(s)

    def prim_report(self, p):
        r = {"mode": p["mode"], "vertices": p["verts"], "triangles": p["tris"], "material": self.mat_label(p["material"]),
             "attributes": ", ".join(p["attributes"])}
        if p["targets"]:
            r["morph_targets"] = p["targets"]
        if p["verts"]:
            r["local_bounds"] = bounds_dict(p["pos"].min(0), p["pos"].max(0))
        if "vcolors" in p:
            u, top = p["vcolors"]
            r["vertex_colors"] = {"unique": u, "top": [f"{h} a{al}  x{n}" for h, al, n in top]}
        return r

    def node_report(self, i):
        n = self.nodes[i]
        r = {"name": self.name(i), "index": i,
             "parent": None if self.parent[i] is None else f"{self.parent[i]} {self.name(self.parent[i])}",
             "children": len(n.get("children", []))}
        if i in self.wb:
            r["world_bounds"] = bounds_dict(*self.wb[i])
        if i in self.tb and n.get("children"):
            r["subtree_bounds"] = bounds_dict(*self.tb[i])
        if "matrix" in n:
            r["matrix"] = n["matrix"]
        else:
            q = n.get("rotation", [0, 0, 0, 1])
            r.update(translation=n.get("translation", [0, 0, 0]), rotation_xyzw=q,
                     rotation_euler_deg=quat_euler_deg(q), scale=n.get("scale", [1, 1, 1]))
        if i in self.world:
            r["world_position"] = self.world[i][:3, 3]
        if "mesh" in n:
            mesh = self.j["meshes"][n["mesh"]]
            r["mesh"] = {"index": n["mesh"], "name": mesh.get("name", ""),
                         "primitives": [self.prim_report(p) for p in self.prims[n["mesh"]]]}
        if i in self.joints:
            r["skin_joint"] = True
        for k in ("camera", "skin", "weights", "extensions", "extras"):
            if k in n:
                r[k] = n[k]
        return clean(r)

    def material_report(self, mi):
        m = self.j["materials"][mi]
        pbr = m.get("pbrMetallicRoughness", {})
        f = pbr.get("baseColorFactor", [1, 1, 1, 1])
        r = {"base_color": f"{hex_lin(f)} a{f[3]:.3f}", "base_color_linear": f,
             "metallic": pbr.get("metallicFactor", 1.0), "roughness": pbr.get("roughnessFactor", 1.0)}
        if any(m.get("emissiveFactor", [0, 0, 0])):
            r["emissive"] = hex_lin(m["emissiveFactor"])
            r["emissive_linear"] = m["emissiveFactor"]
        r["alpha_mode"] = m.get("alphaMode", "OPAQUE")
        if r["alpha_mode"] == "MASK":
            r["alpha_cutoff"] = m.get("alphaCutoff", 0.5)
        r["double_sided"] = m.get("doubleSided", False)
        if "baseColorTexture" in pbr:
            ti = pbr["baseColorTexture"]["index"]
            src, smp = self.tex_image(ti)
            t = {"texture": ti, "uv_set": pbr["baseColorTexture"].get("texCoord", 0)}
            if src is not None:
                t.update(self.image_report(src))
            if smp is not None:
                s = self.j["samplers"][smp]
                t["filter"] = "nearest" if s.get("magFilter") == 9728 else "linear"
            r["base_texture"] = t
        others = {k: m[k]["index"] for k in ("normalTexture", "occlusionTexture", "emissiveTexture") if k in m}
        if "metallicRoughnessTexture" in pbr:
            others["metallicRoughnessTexture"] = pbr["metallicRoughnessTexture"]["index"]
        if others:
            r["other_textures"] = others
        if "extensions" in m:
            r["extensions"] = m["extensions"]
        r["used_by_nodes"] = [i for i in self.world if any(p["material"] == mi for p in self.prims.get(self.nodes[i].get("mesh"), []))]
        return clean(r)

    def image_report(self, k):
        im = self.images[k]
        r = {"image": k, "name": im["name"], "mime": im["mime"]}
        if im["err"]:
            r["error"] = im["err"]
            return r
        r.update(size=f"{im['size'][0]} x {im['size'][1]}", bytes=im["bytes"],
                 average=f"#%02X%02X%02X" % tuple(int(x + 0.5) for x in im["avg"][:3]),
                 unique_colors=im["unique"], top_colors=[f"{h} a{a}  x{n}" for h, a, n in im["top"]])
        return r

    def animation_report(self):
        out = []
        for k, a in enumerate(self.j.get("animations", [])):
            ins = {s["input"] for s in a.get("samplers", [])}
            dur = max((self.j["accessors"][i].get("max", [0])[0] for i in ins), default=0)
            out.append({"name": a.get("name") or f"animation {k}", "channels": len(a.get("channels", [])),
                        "duration_s": dur})
        return clean(out)

    def brief(self):
        """Compact text: materials with colours/textures, node tree with per-primitive world AABBs."""
        s, out = self.summary(), []
        f3 = lambda v: ", ".join(f"{x:.4f}" for x in v)
        size = " x ".join(f"{x:.4f}" for x in s["scene_bounds_m"]["size"]) if "scene_bounds_m" in s else "-"
        out.append(f"=== {s['file']}  {s['counts']['nodes']} nodes, {s['drawn']['triangles']} tris, size {size} m")
        out.append("materials (base = sRGB hex + linear factor; tex = image, mean RGB 0-255)")
        for k, m in enumerate(self.j.get("materials", [])):
            pbr = m.get("pbrMetallicRoughness", {})
            f = pbr.get("baseColorFactor", [1, 1, 1, 1])
            line = f"  m{k} {m.get('name', '')!r} base {hex_lin(f)} ({', '.join(f'{x:.3f}' for x in f)})"
            if "baseColorTexture" in pbr:
                src, _ = self.tex_image(pbr["baseColorTexture"]["index"])
                im = self.images[src] if src is not None else None
                if im and im["rgba"] is not None:
                    a = im["avg"]
                    line += (f"  tex i{src} {im['size'][0]}x{im['size'][1]} mean({a[0]:.1f}, {a[1]:.1f}, {a[2]:.1f})"
                             f" {self.image_report(src)['average']}")
                else:
                    line += f"  tex i{src} unreadable"
            out.append(line)
        out.append("nodes (n=node p=primitive m=material t=tris; lo/hi = world AABB in metres)")

        def walk(i, d):
            n, pad = self.nodes[i], "  " * (d + 1)
            label = f"n{i} {self.name(i)!r}"
            prims = self.prims.get(n.get("mesh"), [])
            if not prims:
                out.append(pad + label)
            M = self.world[i]
            for pi, p in enumerate(prims):
                b = ""
                if len(p["pos"]):
                    P = p["pos"].astype(np.float64) @ M[:3, :3].T + M[:3, 3]
                    b = f"  lo({f3(P.min(0))}) hi({f3(P.max(0))})"
                head = pad + (label if pi == 0 else " " * len(label))
                out.append(f"{head} p{pi} m{p['material']} {p['tris']}t{b}")
            for c in n.get("children", []):
                walk(c, d + 1)
        for r in self.roots:
            walk(r, 0)
        return "\n".join(out)

    def report(self):
        return {"summary": self.summary(), "nodes": [self.node_report(i) for i in range(len(self.nodes))],
                "materials": [self.material_report(i) for i in range(len(self.j.get("materials", [])))],
                "images": [self.image_report(i) for i in range(len(self.images))],
                "animations": self.animation_report()}


# ---------------------------------------------------------------- report -> display lines

BG = (22, 24, 29)
VIEW_BG = (34, 37, 44)
PANEL = (28, 31, 37)
PANEL2 = (40, 44, 53)
PANEL3 = (52, 57, 68)
LINE = (55, 60, 72)
TEXT = (222, 226, 234)
DIM = (135, 142, 156)
HEAD = (130, 175, 230)
ACC = (255, 176, 64)
RED = (255, 110, 100)
GREEN = (120, 220, 140)
KIND = {"mesh": (110, 190, 255), "joint": (200, 140, 255), "camera": GREEN, "empty": (120, 124, 134)}
HEX = re.compile(r"#([0-9A-F]{6})")


def fmt(v):
    if isinstance(v, bool) or v is None:
        return str(v)
    if isinstance(v, float):
        return f"{v:.4f}"
    return str(v)


def to_lines(obj, depth=0, key=None, out=None):
    """Nested report -> [(text, colour, click)] with short number rows, no raw arrays."""
    out = [] if out is None else out
    pad, lab = "  " * depth, "" if key is None else f"{key}: "
    if isinstance(obj, dict):
        if key is not None:
            out.append((pad + str(key), HEAD, None))
        for k, v in obj.items():
            to_lines(v, depth + (key is not None), k, out)
    elif isinstance(obj, list) and obj and all(isinstance(x, (int, float)) and not isinstance(x, bool) for x in obj):
        cells = [f"{x: .4f}" if isinstance(x, float) else str(x) for x in obj]
        per = 4 if any(isinstance(x, float) for x in obj) else 10  # wrap so rows fit the panel
        for k in range(0, len(cells), per):
            out.append(((pad + lab if k == 0 else " " * len(pad + lab)) + "  ".join(cells[k:k + per]), TEXT, None))
    elif isinstance(obj, list):
        out.append((pad + lab + ("[]" if not obj else f"({len(obj)})"), HEAD if obj else DIM, None))
        for n, v in enumerate(obj):
            to_lines(v, depth + 1, f"[{n}]", out)
    else:
        out.append((pad + lab + fmt(obj), TEXT, None))
    return out


# ---------------------------------------------------------------- app

VS = """#version 330
uniform mat4 u_mvp; uniform mat3 u_nmat;
in vec3 in_pos; in vec3 in_nrm; in vec2 in_uv; in vec4 in_col;
out vec3 v_n; out vec2 v_uv; out vec4 v_c;
void main() { gl_Position = u_mvp * vec4(in_pos, 1.0); v_n = u_nmat * in_nrm; v_uv = in_uv; v_c = in_col; }
"""
FS = """#version 330
uniform sampler2D u_tex; uniform vec4 u_base; uniform float u_cut; uniform float u_blend;
uniform float u_lit; uniform vec3 u_light; uniform vec4 u_tint; uniform vec3 u_pick; uniform bool u_picking;
in vec3 v_n; in vec2 v_uv; in vec4 v_c; out vec4 f;
void main() {
    if (u_picking) { f = vec4(u_pick, 1.0); return; }
    vec4 t = texture(u_tex, v_uv);
    vec4 c = u_base * v_c * vec4(pow(t.rgb, vec3(2.2)), t.a);
    if (c.a < u_cut) discard;
    float d = abs(dot(normalize(v_n), u_light));
    vec3 rgb = pow(c.rgb * mix(1.0, 0.28 + 0.85 * d, u_lit), vec3(1.0 / 2.2));
    f = vec4(mix(rgb, u_tint.rgb, u_tint.a), mix(1.0, c.a, u_blend));
}
"""
LVS = "#version 330\nuniform mat4 u_mvp; in vec3 in_pos; void main() { gl_Position = u_mvp * vec4(in_pos, 1.0); }"
LFS = "#version 330\nuniform vec4 u_color; out vec4 f; void main() { f = u_color; }"
QVS = "#version 330\nin vec2 in_pos; out vec2 uv; void main() { uv = in_pos * 0.5 + 0.5; gl_Position = vec4(in_pos, 0.0, 1.0); }"
QFS = "#version 330\nuniform sampler2D t; in vec2 uv; out vec4 f; void main() { f = texture(t, uv); }"

TOGGLES = ("Lit", "Tex", "Wire", "Bounds", "Grid")
TOGGLE_KEYS = {pygame.K_l: "Lit", pygame.K_t: "Tex", pygame.K_w: "Wire", pygame.K_b: "Bounds", pygame.K_g: "Grid"}


def make_icon(size=256):
    """App icon: shaded cube in bounds brackets under a magnifier, on a gradient tile.
    Drawn at 4x and scaled down, since pygame shapes have no anti-aliasing."""
    S, n = 4, 1024
    P = lambda *pts: [(x * S, y * S) for x, y in pts]
    s = pygame.Surface((n, n), pygame.SRCALPHA)
    tile = pygame.Surface((n, n), pygame.SRCALPHA)
    for y in range(n):
        t = y / n
        tile.fill((int(46 - 26 * t), int(52 - 30 * t), int(68 - 38 * t), 255), (0, y, n, 1))
    mask = pygame.Surface((n, n), pygame.SRCALPHA)
    pygame.draw.rect(mask, (255, 255, 255, 255), (6 * S, 6 * S, 244 * S, 244 * S), border_radius=56 * S)
    tile.blit(mask, (0, 0), special_flags=pygame.BLEND_RGBA_MIN)
    s.blit(tile, (0, 0))
    pygame.draw.rect(s, (86, 96, 120), (6 * S, 6 * S, 244 * S, 244 * S), 3 * S, border_radius=56 * S)
    detail = size > 32
    if detail:  # bounds brackets
        for (x, y), (dx, dy) in (((28, 26), (1, 1)), ((196, 26), (-1, 1)), ((28, 212), (1, -1))):
            pygame.draw.lines(s, (255, 176, 64), False, P((x + 24 * dx, y), (x, y), (x, y + 24 * dy)), 6 * S)
    faces = ((P((112, 44), (182, 82), (112, 120), (42, 82)), (255, 192, 96)),
             (P((42, 82), (112, 120), (112, 200), (42, 162)), (96, 176, 255)),
             (P((112, 120), (182, 82), (182, 162), (112, 200)), (46, 100, 178)))
    for pts, col in faces:
        pygame.draw.polygon(s, col, pts)
    pygame.draw.polygon(s, (255, 222, 160), P((112, 44), (182, 82), (112, 120), (42, 82)), 2 * S)
    for pts, _ in faces:
        pygame.draw.polygon(s, (14, 16, 22), pts, 4 * S)
    if detail:
        for p in P((112, 44), (182, 82), (42, 82), (112, 120), (112, 200), (42, 162), (182, 162)):
            pygame.draw.circle(s, (255, 255, 255), p, 6 * S)
    lens, rad = (170, 170), 40  # magnifier
    shadow = pygame.Surface((n, n), pygame.SRCALPHA)
    pygame.draw.circle(shadow, (0, 0, 0, 110), ((lens[0] + 5) * S, (lens[1] + 6) * S), (rad + 8) * S, 14 * S)
    pygame.draw.line(shadow, (0, 0, 0, 110), *P((204, 208), (226, 230)), 22 * S)
    s.blit(shadow, (0, 0))
    glass = pygame.Surface((n, n), pygame.SRCALPHA)
    pygame.draw.circle(glass, (190, 220, 255, 80), (lens[0] * S, lens[1] * S), rad * S)
    pygame.draw.arc(glass, (255, 255, 255, 150), pygame.Rect(P((lens[0] - 30, lens[1] - 30))[0], (60 * S, 60 * S)),
                    1.9, 3.0, 5 * S)
    s.blit(glass, (0, 0))
    a, b = P((200, 200), (222, 222))
    pygame.draw.line(s, (255, 176, 64), a, b, 20 * S)
    pygame.draw.circle(s, (255, 176, 64), b, 10 * S)
    pygame.draw.circle(s, (236, 240, 248), (lens[0] * S, lens[1] * S), (rad + 6) * S, 12 * S)
    return pygame.transform.smoothscale(s, (size, size))


def write_ico(path, sizes=(256, 64, 48, 32, 16)):
    """Multi-size .ico with PNG-compressed entries (no Pillow needed)."""
    pngs = []
    for n in sizes:
        buf = io.BytesIO()
        pygame.image.save(make_icon(n), buf, "icon.png")
        pngs.append(buf.getvalue())
    off = 6 + 16 * len(sizes)
    head = struct.pack("<HHH", 0, 1, len(sizes))
    for n, png in zip(sizes, pngs):
        head += struct.pack("<BBBBHHII", n % 256, n % 256, 0, 0, 1, 32, len(png), off)
        off += len(png)
    with open(path, "wb") as f:
        f.write(head + b"".join(pngs))


def box_lines(mn, mx):
    c = [np.array([x, y, z]) for x in (mn[0], mx[0]) for y in (mn[1], mx[1]) for z in (mn[2], mx[2])]
    e = [(0, 1), (2, 3), (4, 5), (6, 7), (0, 2), (1, 3), (4, 6), (5, 7), (0, 4), (1, 5), (2, 6), (3, 7)]
    return np.array([c[k] for a in e for k in a], np.float32)


def nmat_bytes(M):
    try:
        n = np.linalg.inv(M[:3, :3]).T
    except np.linalg.LinAlgError:
        n = np.eye(3)
    return n.T.astype("f4").tobytes()


def file_header(k, n, path):
    """Header line that separates files in a multi-file copy."""
    try:
        rel = os.path.relpath(path)
    except ValueError:  # other drive on Windows
        rel = os.path.abspath(path)
    return f"##### FILE {k + 1}/{n}: {os.path.basename(path)}  ({rel})"


RECENT = os.path.join(os.environ.get("APPDATA") or os.path.expanduser("~"), "GLBInspector", "recent.json")
# per-file state, swapped in and out when switching between open files
PER_DOC = ("model", "gl_objs", "draws", "texs", "sel", "sel_mat", "collapsed", "scroll", "yaw", "pitch", "dist",
           "target", "summary_lines", "mat_lines", "img_lines", "anim_lines", "raw_lines", "detail_cache", "grid",
           "grid_step", "anim")
# (label, file name, yaw, pitch); yaw 0 = camera on +Z looking at -Z (glTF front)
SHOT_VIEWS = (("Front (+Z)", "front", 0.0, 0.0), ("Back (-Z)", "back", math.pi, 0.0),
              ("Right (+X)", "right", math.pi / 2, 0.0), ("Left (-X)", "left", -math.pi / 2, 0.0),
              ("Top (+Y)", "top", 0.0, 1.5703), ("Bottom (-Y)", "bottom", 0.0, -1.5703),
              ("3/4 front-right", "front_right", math.pi / 4, 0.5), ("3/4 back-left", "back_left", -3 * math.pi / 4, 0.5))
VIEWS = {pygame.K_1: (0.0, 0.0), pygame.K_KP1: (0.0, 0.0), pygame.K_3: (math.pi / 2, 0.0),
         pygame.K_KP3: (math.pi / 2, 0.0), pygame.K_7: (0.0, 1.5703), pygame.K_KP7: (0.0, 1.5703),
         pygame.K_0: (0.7, 0.35), pygame.K_KP0: (0.7, 0.35)}


class App:
    PW = 430  # side panel width

    def __init__(self, path=None):
        import moderngl
        self.mgl = moderngl
        pygame.init()
        for a, v in ((pygame.GL_CONTEXT_MAJOR_VERSION, 3), (pygame.GL_CONTEXT_MINOR_VERSION, 3),
                     (pygame.GL_CONTEXT_PROFILE_MASK, pygame.GL_CONTEXT_PROFILE_CORE),
                     (pygame.GL_MULTISAMPLEBUFFERS, 1), (pygame.GL_MULTISAMPLESAMPLES, 4)):
            pygame.display.gl_set_attribute(a, v)
        flags = pygame.OPENGL | pygame.DOUBLEBUF | pygame.RESIZABLE
        try:
            pygame.display.set_mode((1440, 860), flags)
        except pygame.error:  # no MSAA on this GPU
            pygame.display.gl_set_attribute(pygame.GL_MULTISAMPLEBUFFERS, 0)
            pygame.display.gl_set_attribute(pygame.GL_MULTISAMPLESAMPLES, 0)
            pygame.display.set_mode((1440, 860), flags)
        pygame.display.set_caption("GLB Inspector")
        pygame.display.set_icon(make_icon(64))
        pygame.key.set_repeat(300, 40)
        ctx = self.ctx = moderngl.create_context()
        self.prog = ctx.program(vertex_shader=VS, fragment_shader=FS)
        self.lprog = ctx.program(vertex_shader=LVS, fragment_shader=LFS)
        self.qprog = ctx.program(vertex_shader=QVS, fragment_shader=QFS)
        self.prog["u_tex"].value = 0
        self.qprog["t"].value = 0
        quad = ctx.buffer(np.array([-1, -1, 1, -1, -1, 1, 1, 1], "f4").tobytes())
        self.qvao = ctx.vertex_array(self.qprog, [(quad, "2f", "in_pos")])
        self.lvbo = ctx.buffer(reserve=1 << 20, dynamic=True)
        self.lvao = ctx.vertex_array(self.lprog, [(self.lvbo, "3f", "in_pos")])
        self.white = ctx.texture((1, 1), 4, b"\xff\xff\xff\xff")
        self.font = pygame.font.SysFont("segoeui", 15)
        self.bold = pygame.font.SysFont("segoeui", 15, bold=True)
        self.big = pygame.font.SysFont("segoeui", 20, bold=True)
        self.mono = pygame.font.SysFont("consolas", 14)
        self._tc = {}
        self.model = None
        self.gl_objs, self.draws, self.texs = [], [], {}
        self.sel = self.sel_mat = self.hover = None
        self.collapsed, self.rows, self.reveal = set(), [], False
        self.tab = "Nodes"
        self.scroll = defaultdict(int)
        self.opts = {"Lit": True, "Tex": True, "Wire": False, "Bounds": True, "Grid": True}
        self.yaw, self.pitch, self.dist, self.target = 0.7, 0.35, 5.0, np.zeros(3)
        self.drag = self.down = None
        self.toast = ("Drop a .glb on the window or press O", 0, DIM)
        self.hits, self.panes = [], {}
        self.mouse = (0, 0)
        self.last_pick = 0
        self.size = None
        self.docs, self.cur = [], 0
        self.anim = {"clip": None, "t": 0.0, "play": False}
        self.scrub_rect = None
        self.show_recent = self.popup_was = False
        try:
            with open(RECENT, encoding="utf-8") as f:
                self.recent = [p for p in json.load(f) if isinstance(p, str)][:10]
        except (OSError, ValueError):
            self.recent = []
        self._resize()
        for p in path or []:
            self.load(p)

    # -- setup
    def _resize(self):
        W, H = pygame.display.get_window_size()
        if (W, H) == self.size:
            return
        self.size = (W, H)
        self.ui = pygame.Surface((W, H), pygame.SRCALPHA)
        if hasattr(self, "ui_tex"):
            for o in (self.ui_tex, self.pick_fbo):
                o.release()
        self.ui_tex = self.ctx.texture((W, H), 4)
        self.ui_tex.filter = (self.mgl.NEAREST, self.mgl.NEAREST)
        vw = max(1, W - self.PW)
        self.pick_fbo = self.ctx.framebuffer(self.ctx.renderbuffer((vw, H)), self.ctx.depth_renderbuffer((vw, H)))

    def say(self, msg, col=TEXT):
        self.toast = (msg, pygame.time.get_ticks() + 2500, col)

    # -- open files
    def stash(self):
        if self.model is not None:
            self.docs[self.cur] = {k: getattr(self, k) for k in PER_DOC}

    def restore(self, k):
        self.cur = k
        for a, v in self.docs[k].items():
            setattr(self, a, v)
        self.hover = None
        pygame.display.set_caption(f"GLB Inspector - {os.path.basename(self.model.path)}")

    def switch(self, k):
        if k != self.cur and 0 <= k < len(self.docs):
            self.stash()
            self.restore(k)

    def close(self, k):
        self.stash()
        for o in self.docs.pop(k)["gl_objs"]:
            o.release()
        if self.docs:
            self.restore(min(k, len(self.docs) - 1))
        else:
            self.model, self.draws, self.gl_objs, self.sel, self.sel_mat, self.hover = None, [], [], None, None, None
            pygame.display.set_caption("GLB Inspector")

    def remember(self, path):
        p = os.path.abspath(path)
        self.recent = [p] + [r for r in self.recent if os.path.normcase(r) != os.path.normcase(p)][:9]
        try:
            os.makedirs(os.path.dirname(RECENT), exist_ok=True)
            with open(RECENT, "w", encoding="utf-8") as f:
                json.dump(self.recent, f, indent=1)
        except OSError:
            pass  # recent list is a convenience; never block loading

    def load(self, path):
        """Open a file as a new tab, or reload it in place if it is already open."""
        try:
            m = Model(path)
        except Exception as e:
            self.say(f"Could not load {os.path.basename(path)}: {e}", RED)
            return
        self.stash()
        ap = os.path.normcase(os.path.abspath(path))
        slot = next((n for n, d in enumerate(self.docs) if os.path.normcase(os.path.abspath(d["model"].path)) == ap), None)
        if slot is None:
            self.docs.append(None)
            slot = len(self.docs) - 1
        else:
            for o in self.docs[slot]["gl_objs"]:
                o.release()
        self.cur = slot
        self.gl_objs, self.draws, self.texs = [], [], {}
        self.model = m
        self.sel = self.sel_mat = self.hover = None
        self.collapsed, self.scroll = set(), defaultdict(int)
        self.yaw, self.pitch = 0.7, 0.35
        self.anim = {"clip": None, "t": 0.0, "play": False}
        ctx = self.ctx
        for k, im in enumerate(m.images):
            if im["rgba"] is not None:
                self.texs[k] = ctx.texture(im["size"], 4, im["rgba"])
                self.gl_objs.append(self.texs[k])
        vaos = {}
        for i, M in m.world.items():
            mi = m.nodes[i].get("mesh")
            for pi, p in enumerate(m.prims.get(mi, [])):
                if p["vbo"] is None:
                    continue
                if (mi, pi) not in vaos:
                    vbo = ctx.buffer(p["vbo"].tobytes())
                    vaos[mi, pi] = ctx.vertex_array(self.prog, [(vbo, "3f 3f 2f 4f", "in_pos", "in_nrm", "in_uv", "in_col")])
                    self.gl_objs += [vbo, vaos[mi, pi]]
                self.draws.append({"node": i, "vao": vaos[mi, pi], "mat": p["material"], "M": M, "pos": p["pos"],
                                   "nmat": nmat_bytes(M), **self.mat_params(p["material"])})
        self.draws.sort(key=lambda d: d["blend"])  # shortcut: blended draws last, not depth-sorted
        self.build_grid()
        self.frame()
        self.summary_lines = to_lines(m.summary())
        self.mat_lines = [(f"MATERIAL {k}  {mat.get('name', '')}", to_lines(m.material_report(k), 1))
                          for k, mat in enumerate(m.j.get("materials", []))]
        self.img_lines = [to_lines(m.image_report(k), 1) for k in range(len(m.images))]
        self.anim_lines = to_lines(m.animation_report())
        raw = json.dumps(m.j, indent=2).splitlines()
        self.raw_lines = [(s, DIM if s.strip() in "{}[]," else TEXT, None) for s in raw[:20000]]
        self.detail_cache = {}
        self.docs[slot] = {a: getattr(self, a) for a in PER_DOC}
        self.remember(path)
        pygame.display.set_caption(f"GLB Inspector - {os.path.basename(path)}")
        s = m.summary()
        self.say(f"Loaded {s['file']}: {s['counts']['nodes']} nodes, {s['drawn']['triangles']} tris", GREEN)

    # -- animation
    def set_clip(self, clip):
        self.anim.update(clip=clip, t=0.0, play=clip is not None and self.anim["play"])
        self.apply_pose()

    def next_clip(self):
        n = len(self.model.j.get("animations", []))
        c = self.anim["clip"]
        self.set_clip(0 if c is None else (c + 1 if c + 1 < n else None))

    def play(self):
        if self.anim["clip"] is None:
            self.set_clip(0)
        self.anim["play"] = not self.anim["play"]

    def apply_pose(self):
        a = self.anim
        world = self.model.world if a["clip"] is None else self.model.pose(a["clip"], a["t"])
        for d in self.draws:
            d["M"] = world[d["node"]]
            d["nmat"] = nmat_bytes(d["M"])

    def sel_box(self):
        """World AABB of the selected subtree, in the current animation pose."""
        m = self.model
        if self.anim["clip"] is None:
            return m.tb.get(self.sel)
        sub, st = set(), [self.sel]
        while st:
            i = st.pop()
            sub.add(i)
            st += m.nodes[i].get("children", [])
        pts = [d["pos"].astype(np.float64) @ d["M"][:3, :3].T + d["M"][:3, 3] for d in self.draws if d["node"] in sub]
        if not pts:
            return None
        P = np.vstack(pts)
        return P.min(0), P.max(0)

    def scrub(self, x):
        r, a = self.scrub_rect, self.anim
        if r is None or a["clip"] is None:
            return
        a["t"] = max(0.0, min(1.0, (x - r.x) / r.w)) * self.model.anim_dur(a["clip"])
        self.apply_pose()

    def mat_params(self, mi):
        mat = self.model.j["materials"][mi] if mi is not None else {}
        pbr = mat.get("pbrMetallicRoughness", {})
        tex = None
        if "baseColorTexture" in pbr:
            src, smp = self.model.tex_image(pbr["baseColorTexture"]["index"])
            tex = self.texs.get(src)
            if tex is not None:
                s = self.model.j["samplers"][smp] if smp is not None else {}
                nearest = s.get("magFilter") == 9728
                tex.filter = (self.mgl.NEAREST, self.mgl.NEAREST) if nearest else (self.mgl.LINEAR, self.mgl.LINEAR)
        mode = mat.get("alphaMode", "OPAQUE")
        return {"base": tuple(pbr.get("baseColorFactor", [1, 1, 1, 1])), "tex": tex,
                "cut": mat.get("alphaCutoff", 0.5) if mode == "MASK" else -1.0, "blend": mode == "BLEND"}

    def build_grid(self):
        b = self.model.bounds
        if b is None:
            self.grid, self.grid_step = np.zeros((0, 3), np.float32), 1.0
            return
        size = float(max(b[1] - b[0])) or 1.0
        step = 10 ** round(math.log10(size / 8))
        n = min(60, int(size / step) + 4)
        cx, cz, y = round((b[0][0] + b[1][0]) / 2 / step) * step, round((b[0][2] + b[1][2]) / 2 / step) * step, b[0][1]
        pts = []
        for k in range(-n, n + 1):
            pts += [(cx + k * step, y, cz - n * step), (cx + k * step, y, cz + n * step),
                    (cx - n * step, y, cz + k * step), (cx + n * step, y, cz + k * step)]
        self.grid, self.grid_step = np.array(pts, np.float32), step

    # -- camera
    def frame(self, node=None):
        b = self.model.tb.get(node) if node is not None else self.model.bounds
        if b is None:
            return
        self.target = (b[0] + b[1]) / 2
        r = max(float(np.linalg.norm(b[1] - b[0])) / 2, 1e-3)
        self.dist = r / math.sin(math.radians(22.5)) * 1.05

    def eye(self):
        cp = math.cos(self.pitch)
        return self.target + self.dist * np.array([cp * math.sin(self.yaw), math.sin(self.pitch), cp * math.cos(self.yaw)])

    def viewproj(self, aspect=None):
        W, H = self.size
        proj = perspective(math.radians(45), aspect or (W - self.PW) / H, self.dist * 0.01, self.dist * 100)
        return proj @ look_at(self.eye(), self.target)

    # -- selection
    def select(self, i, reveal=True):
        self.sel, self.sel_mat = i, None
        if i is not None and reveal:
            p = self.model.parent[i]
            while p is not None:
                self.collapsed.discard(p)
                p = self.model.parent[p]
            self.reveal = True

    def pick(self, mx, my):
        """Node under the mouse via an ID render, or None."""
        if not self.draws or mx < self.PW:
            return None
        W, H = self.size
        vp = self.viewproj()
        self.pick_fbo.use()
        self.ctx.clear(0, 0, 0, 0)
        self.ctx.enable(self.mgl.DEPTH_TEST)
        self.prog["u_picking"].value = True
        for k, d in enumerate(self.draws, 1):
            self.prog["u_mvp"].write(gl_mat(vp @ d["M"]))
            self.prog["u_pick"].value = ((k & 255) / 255, ((k >> 8) & 255) / 255, ((k >> 16) & 255) / 255)
            d["vao"].render()
        self.prog["u_picking"].value = False
        px = self.pick_fbo.read(viewport=(mx - self.PW, H - 1 - my, 1, 1), components=4)
        self.ctx.screen.use()
        k = px[0] | (px[1] << 8) | (px[2] << 16)
        return self.draws[k - 1]["node"] if 0 < k <= len(self.draws) else None

    # -- actions
    @staticmethod
    def dialog(name, **kw):
        import tkinter as tk
        from tkinter import filedialog
        root = tk.Tk()
        root.withdraw()
        root.attributes("-topmost", True)
        p = getattr(filedialog, name)(parent=root, **kw)
        root.destroy()
        return p

    def ask_open(self):
        start = os.path.join("assets", "3D") if os.path.isdir(os.path.join("assets", "3D")) else os.getcwd()
        for p in self.dialog("askopenfilenames", initialdir=start, title="Open 3D model(s)",
                             filetypes=[("glTF models", "*.glb *.gltf"), ("All files", "*.*")]) or ():
            self.load(p)

    def copy(self):
        """Every open file's brief under a FILE header, each followed by that file's selected node/material JSON."""
        if self.model is None:
            return
        self.stash()
        parts, picked = [], 0
        for k, d in enumerate(self.docs):
            m, text = d["model"], d["model"].brief()
            if d["sel"] is not None:
                text += f"\n\nselected node n{d['sel']}:\n" + json.dumps(m.node_report(d["sel"]), indent=2)
                picked += 1
            elif d["sel_mat"] is not None:
                text += f"\n\nselected material m{d['sel_mat']}:\n" + json.dumps(m.material_report(d["sel_mat"]), indent=2)
                picked += 1
            parts.append(file_header(k, len(self.docs), m.path) + "\n" + text)
        n = len(self.docs)
        what = (f"{n} files" if n > 1 else os.path.basename(self.model.path)) + (f" + {picked} selection(s)" if picked else "")
        try:
            pygame.scrap.put_text("\n\n".join(parts))
            self.say(f"Copied {what}", GREEN)
        except Exception as e:
            self.say(f"Clipboard failed: {e}", RED)

    def export(self):
        if self.model is None:
            return
        base = os.path.splitext(os.path.basename(self.model.path))[0]
        p = self.dialog("asksaveasfilename", initialfile=f"{base}.inspect.json", defaultextension=".json",
                        filetypes=[("JSON", "*.json")])
        if p:
            with open(p, "w", encoding="utf-8") as f:
                json.dump(self.model.report(), f, indent=1)
            self.say(f"Exported report to {os.path.basename(p)}", GREEN)

    def ask_shot(self):
        """Render the standard views to <name>.png (labelled sheet) and <name>/<view>.png (one file each)."""
        if self.model is None:
            return
        base = os.path.splitext(os.path.basename(self.model.path))[0]
        path = self.dialog("asksaveasfilename", initialfile=f"{base}_views.png", defaultextension=".png",
                           filetypes=[("PNG image", "*.png")])
        if not path:
            return
        try:
            n = self.shoot_views(path)
            self.say(f"Saved {n} views: {os.path.basename(path)} + folder {os.path.splitext(os.path.basename(path))[0]}", GREEN)
        except Exception as e:
            self.say(f"Screenshot failed: {e}", RED)

    def shoot_views(self, path, N=2048, out=1024, tile=512):
        """Frames the selection (or whole model) from each SHOT_VIEWS angle in an offscreen buffer."""
        ctx, m = self.ctx, self.model
        tex = ctx.texture((N, N), 4)
        depth = ctx.depth_renderbuffer((N, N))
        fbo = ctx.framebuffer(tex, depth)
        cam = (self.yaw, self.pitch, self.dist, self.target)
        folder = os.path.splitext(path)[0]
        os.makedirs(folder, exist_ok=True)
        shots = []
        try:
            for label, fname, yaw, pitch in SHOT_VIEWS:
                self.yaw, self.pitch = yaw, pitch
                self.frame(self.sel)
                self.dist *= 0.8  # frame() fits the bounding sphere; tighter for stills
                fbo.use()
                ctx.viewport = (0, 0, N, N)
                ctx.clear(*(c / 255 for c in VIEW_BG), 1.0)
                self.draw_scene(self.viewproj(1.0), clean=True)
                img = pygame.transform.smoothscale(pygame.image.frombytes(fbo.read(components=3), (N, N), "RGB", True),
                                                   (out, out))
                pygame.image.save(img, os.path.join(folder, fname + ".png"))
                shots.append((label, pygame.transform.smoothscale(img, (tile, tile))))
        finally:
            self.yaw, self.pitch, self.dist, self.target = cam
            ctx.screen.use()
            for o in (fbo, tex, depth):
                o.release()
        cols, lab, head = 4, 30, 40
        rows = (len(shots) + cols - 1) // cols
        sheet = pygame.Surface((cols * tile, head + rows * (tile + lab)))
        sheet.fill(BG)
        what = os.path.basename(m.path) + (f"  -  framed on {m.name(self.sel)}" if self.sel is not None else "")
        b = m.tb.get(self.sel) if self.sel is not None else m.bounds
        if b is not None:
            sz = b[1] - b[0]
            what += f"  -  {sz[0]:.4f} x {sz[1]:.4f} x {sz[2]:.4f} m"
        sheet.blit(self.big.render(what, True, ACC), (12, 8))
        for k, (label, img) in enumerate(shots):
            x, y = k % cols * tile, head + k // cols * (tile + lab)
            sheet.blit(self.bold.render(label, True, TEXT), (x + 10, y + 5))
            sheet.blit(img, (x, y + lab))
            pygame.draw.rect(sheet, LINE, (x, y + lab, tile, tile), 1)
        pygame.image.save(sheet, path)
        return len(shots)

    def set_view(self, yaw, pitch, flip):
        self.yaw, self.pitch = (yaw + math.pi, -pitch) if flip else (yaw, pitch)

    def toggle(self, k):
        self.opts[k] = not self.opts[k]

    # -- UI primitives
    def txt(self, s, x, y, col=TEXT, font=None):
        font = font or self.font
        key = (s, col, id(font))
        surf = self._tc.get(key)
        if surf is None:
            if len(self._tc) > 4000:
                self._tc.clear()
            surf = self._tc[key] = font.render(s, True, col)
        self.ui.blit(surf, (x, y))
        return surf.get_width()

    def button(self, rect, label, fn, active=False):
        rect = pygame.Rect(rect)
        hov = rect.collidepoint(self.mouse)
        col = (110, 80, 35) if active else (PANEL3 if hov else PANEL2)
        pygame.draw.rect(self.ui, col, rect, border_radius=6)
        if active:
            pygame.draw.rect(self.ui, ACC, rect, 1, border_radius=6)
        w = self.font.size(label)[0]
        self.txt(label, rect.centerx - w // 2, rect.y + (rect.h - 20) // 2, ACC if active else TEXT)
        self.hits.append((rect, fn))

    def pane(self, key, rect, lines, lh=18):
        """Scrollable line list; '#RRGGBB' in a line gets a colour swatch in the gutter."""
        self.panes[key] = rect
        over = max(0, len(lines) * lh - rect.h)
        s = self.scroll[key] = max(0, min(self.scroll[key], over))
        self.ui.set_clip(rect)
        first = s // lh
        for n in range(first, min(len(lines), first + rect.h // lh + 2)):
            text, col, fn = lines[n]
            y = rect.y + n * lh - s
            if fn:
                r = pygame.Rect(rect.x, y, rect.w, lh).clip(rect)
                if r.collidepoint(self.mouse):
                    pygame.draw.rect(self.ui, PANEL2, r)
                self.hits.append((r, fn))
            h = HEX.search(text)
            if h:
                c = pygame.Color("#" + h.group(1))
                pygame.draw.rect(self.ui, c, (rect.x + 2, y + 3, 12, 12))
                pygame.draw.rect(self.ui, LINE, (rect.x + 2, y + 3, 12, 12), 1)
            self.txt(text, rect.x + 20, y, col, self.mono)
        self.ui.set_clip(None)
        if over:
            bar = max(20, rect.h * rect.h // (rect.h + over))
            pygame.draw.rect(self.ui, PANEL3, (rect.right - 5, rect.y + (rect.h - bar) * s // over, 4, bar), border_radius=2)

    # -- panels
    def draw_panel(self):
        W, H = self.size
        PW, ui, m = self.PW, self.ui, self.model
        pygame.draw.rect(ui, PANEL, (0, 0, PW, H))
        pygame.draw.line(ui, LINE, (PW - 1, 0), (PW - 1, H))
        self.txt("GLB Inspector", 16, 12, ACC, self.big)
        btns = (("Open", self.ask_open), ("Recent", lambda: setattr(self, "show_recent", not self.popup_was)),
                ("Copy", self.copy), ("Export", self.export))
        for k, (lab, fn) in enumerate(btns):
            self.button((PW - 268 + k * 65, 12, 60, 28), lab, fn, lab == "Recent" and self.show_recent)
        y = 50
        if m is None:
            self.txt("No model loaded.", 16, y, DIM)
            self.txt("Drop .glb / .gltf files on the window, or click Open.", 16, y + 22, DIM)
            self.txt("You can open several files; Copy takes them all.", 16, y + 44, DIM)
            if self.recent:
                self.txt("Recent", 16, y + 82, HEAD, self.bold)
                self.recent_list(pygame.Rect(8, y + 106, PW - 16, 0))
            if self.show_recent:
                self.recent_popup()
            return
        # one chip per open file; click to switch, x to close
        cw = min(170, (PW - 16) // len(self.docs) - 4)
        for k, d in enumerate(self.docs):
            r = pygame.Rect(8 + k * (cw + 4), y, cw, 26)
            on = k == self.cur
            pygame.draw.rect(ui, (90, 66, 30) if on else (PANEL3 if r.collidepoint(self.mouse) else PANEL2), r, border_radius=5)
            name = os.path.basename(d["model"].path)
            while len(name) > 4 and self.font.size(name)[0] > cw - 30:
                name = name[:-2]
            if name != os.path.basename(d["model"].path):
                name = name[:-1] + "..."
            self.hits.append((r, lambda k=k: self.switch(k)))
            self.txt(name, r.x + 8, r.y + 3, ACC if on else TEXT)
            xr = pygame.Rect(r.right - 20, r.y + 4, 16, 18)
            self.txt("x", xr.x + 4, xr.y - 1, RED if xr.collidepoint(self.mouse) else DIM)
            self.hits.append((xr, lambda k=k: self.close(k)))
        y += 34
        self.pane("summary", pygame.Rect(8, y, PW - 16, 140), self.summary_lines, 17)
        y += 148
        pygame.draw.line(ui, LINE, (0, y), (PW, y))
        tx = 10
        for t in ("Nodes", "Materials", "Raw JSON"):
            w = self.font.size(t)[0] + 24
            self.button((tx, y + 8, w, 28), t, lambda t=t: setattr(self, "tab", t), self.tab == t)
            tx += w + 6
        y += 44
        body = pygame.Rect(8, y, PW - 16, H - y - 8)
        if self.tab == "Nodes":
            th = int(body.h * 0.42)
            self.draw_tree(pygame.Rect(body.x, body.y, body.w, th))
            dy = body.y + th + 6
            pygame.draw.line(ui, LINE, (0, dy), (PW, dy))
            if self.sel is None:
                self.txt("Select a node in the list or the viewport.", 16, dy + 10, DIM)
            else:
                if self.sel not in self.detail_cache:
                    self.detail_cache[self.sel] = to_lines(m.node_report(self.sel))
                self.pane(("detail", self.sel), pygame.Rect(body.x, dy + 6, body.w, body.bottom - dy - 6),
                          self.detail_cache[self.sel])
        elif self.tab == "Materials":
            lines = []
            for k, (head, body_lines) in enumerate(self.mat_lines):
                lines.append((head, ACC if k == self.sel_mat else HEAD, lambda k=k: self.pick_mat(k)))
                lines += body_lines + [("", TEXT, None)]
            if not self.mat_lines:
                lines.append(("No materials (everything draws white).", DIM, None))
            for k, il in enumerate(self.img_lines):
                lines += [(f"IMAGE {k}", HEAD, None)] + il + [("", TEXT, None)]
            if self.anim_lines and self.model.j.get("animations"):
                lines += [("ANIMATIONS", HEAD, None)] + self.anim_lines
            self.pane("materials", body, lines)
        else:
            self.pane("raw", body, self.raw_lines, 17)
        if self.show_recent:
            self.recent_popup()

    def recent_list(self, rect):
        """Clickable rows of recent files from rect.topleft."""
        lh = 22
        for n, p in enumerate(self.recent):
            r = pygame.Rect(rect.x, rect.y + n * lh, rect.w, lh)
            ok = os.path.isfile(p)
            if ok and r.collidepoint(self.mouse):
                pygame.draw.rect(self.ui, PANEL3, r, border_radius=4)
            w = self.txt(os.path.basename(p), r.x + 8, r.y + 2, TEXT if ok else DIM)
            folder = os.path.basename(os.path.dirname(p)) + ("" if ok else "  (missing)")
            self.txt(folder, min(r.x + 16 + w, r.right - 8 - self.font.size(folder)[0]), r.y + 2, DIM)
            if ok:
                self.hits.append((r, lambda p=p: self.load(p)))

    def recent_popup(self):
        r = pygame.Rect(self.PW - 268 + 65, 44, 330, max(1, len(self.recent)) * 22 + 12)
        pygame.draw.rect(self.ui, PANEL, r, border_radius=6)
        pygame.draw.rect(self.ui, LINE, r, 1, border_radius=6)
        self.hits.append((r, lambda: setattr(self, "show_recent", True)))  # clicks on the popup's gaps keep it open
        if self.recent:
            self.recent_list(r.inflate(-8, -12))
        else:
            self.txt("No recent files yet.", r.x + 12, r.y + 6, DIM)

    def pick_mat(self, k):
        self.sel, self.sel_mat = None, (None if self.sel_mat == k else k)

    def draw_tree(self, rect):
        m, rows = self.model, []

        def walk(i, d):
            rows.append((i, d))
            if i not in self.collapsed:
                for c in m.nodes[i].get("children", []):
                    walk(c, d + 1)
        for r in m.roots:
            walk(r, 0)
        self.rows = [i for i, _ in rows]
        lh = 21
        if self.reveal and self.sel in self.rows:
            k = self.rows.index(self.sel)
            s = self.scroll["tree"]
            if not s <= k * lh <= s + rect.h - lh:
                self.scroll["tree"] = k * lh - rect.h // 2
            self.reveal = False
        self.panes["tree"] = rect
        over = max(0, len(rows) * lh - rect.h)
        s = self.scroll["tree"] = max(0, min(self.scroll["tree"], over))
        self.ui.set_clip(rect)
        for n in range(s // lh, min(len(rows), s // lh + rect.h // lh + 2)):
            i, d = rows[n]
            node = m.nodes[i]
            y = rect.y + n * lh - s
            r = pygame.Rect(rect.x, y, rect.w, lh).clip(rect)
            if i == self.sel:
                pygame.draw.rect(self.ui, (90, 66, 30), r, border_radius=4)
            elif i == self.hover or r.collidepoint(self.mouse):
                pygame.draw.rect(self.ui, PANEL2, r, border_radius=4)
            x = rect.x + 4 + d * 14
            kids = node.get("children")
            self.hits.append((r, lambda i=i: self.select(None if self.sel == i else i, False)))
            if kids:  # arrow hit goes after the row hit so it wins
                tri = [(x + 2, y + 6), (x + 10, y + 6), (x + 6, y + 13)] if i not in self.collapsed \
                    else [(x + 3, y + 5), (x + 10, y + 10), (x + 3, y + 15)]
                pygame.draw.polygon(self.ui, DIM, tri)
                self.hits.append((pygame.Rect(x - 2, y, 16, lh).clip(rect),
                                  lambda i=i: setattr(self, "collapsed", self.collapsed ^ {i})))
            kind = "mesh" if "mesh" in node else "joint" if i in m.joints else "camera" if "camera" in node else "empty"
            pygame.draw.rect(self.ui, KIND[kind], (x + 16, y + 6, 9, 9), border_radius=2)
            self.txt(m.name(i), x + 31, y + 1, ACC if i == self.sel else TEXT)
            info = f"{sum(p['tris'] for p in m.prims[node['mesh']])} tris" if kind == "mesh" else \
                f"{len(kids)} child" + ("ren" if len(kids) != 1 else "") if kids else ""
            if info:
                w = self.font.size(info)[0]
                self.txt(info, rect.right - w - 10, y + 1, DIM)
        self.ui.set_clip(None)
        if over:
            bar = max(20, rect.h * rect.h // (rect.h + over))
            pygame.draw.rect(self.ui, PANEL3, (rect.right - 5, rect.y + (rect.h - bar) * s // over, 4, bar), border_radius=2)

    def draw_overlay(self):
        W, H = self.size
        PW, m = self.PW, self.model
        bx = W - 10
        for k in reversed(TOGGLES):
            w = self.font.size(k)[0] + 22
            bx -= w + 6
            self.button((bx, 10, w, 28), k, lambda k=k: self.toggle(k), self.opts[k])
        self.button((bx - 62, 10, 56, 28), "Shot", self.ask_shot)
        self.scrub_rect = None
        anims = m.j.get("animations", []) if m is not None else []
        if anims:
            self.draw_anim_bar(anims)
        if m is None:
            msg = "Drop a .glb here"
            w = self.big.size(msg)[0]
            self.txt(msg, PW + (W - PW - w) // 2, H // 2 - 30, DIM, self.big)
            w = self.font.size("or press O to browse")[0]
            self.txt("or press O to browse", PW + (W - PW - w) // 2, H // 2, DIM)
        else:
            if self.sel is not None:
                b = self.sel_box()
                self.txt(m.name(self.sel), PW + 14, 12, ACC, self.bold)
                if b is not None:
                    sz = b[1] - b[0]
                    self.txt(f"{sz[0]:.4f} x {sz[1]:.4f} x {sz[2]:.4f} m  (world AABB)", PW + 14, 32, TEXT)
            elif self.sel_mat is not None:
                self.txt(f"Material {m.mat_label(self.sel_mat)}", PW + 14, 12, ACC, self.bold)
            elif m.bounds is not None:
                sz = m.bounds[1] - m.bounds[0]
                self.txt(f"Scene  {sz[0]:.4f} x {sz[1]:.4f} x {sz[2]:.4f} m", PW + 14, 12, TEXT, self.bold)
            if self.hover is not None and not self.drag:
                self.txt(m.name(self.hover), self.mouse[0] + 14, self.mouse[1] + 10, (255, 255, 255), self.bold)
        hint = ("LMB orbit/select  RMB pan  wheel zoom  F frame  Esc clear  LTWBG toggles  1/3/7 views (Ctrl flips)"
                "  0 reset  P shot  Tab next file  Space play")
        if m is not None and self.opts["Grid"]:
            hint += f"  grid {self.grid_step:g} m"
        self.txt(hint, PW + 14, H - 26, DIM)
        msg, until, col = self.toast
        if msg and (until == 0 or pygame.time.get_ticks() < until):
            w = self.font.size(msg)[0]
            r = pygame.Rect(0, 0, w + 28, 32)
            r.midbottom = (PW + (W - PW) // 2, H - (76 if anims else 40))
            pygame.draw.rect(self.ui, PANEL, r, border_radius=8)
            pygame.draw.rect(self.ui, col, r, 1, border_radius=8)
            self.txt(msg, r.x + 14, r.y + 6, col)

    def draw_anim_bar(self, anims):
        W, H = self.size
        a = self.anim
        c = a["clip"]
        bar = pygame.Rect(self.PW + 10, H - 66, W - self.PW - 20, 34)
        pygame.draw.rect(self.ui, PANEL, bar, border_radius=8)
        name = "Rest pose" if c is None else f"{c + 1}/{len(anims)} {(anims[c].get('name') or f'animation {c}')[:28]}"
        cw = min(260, self.font.size(name)[0] + 24)
        self.button((bar.x + 4, bar.y + 3, cw, 28), name, self.next_clip, c is not None)
        self.button((bar.x + cw + 10, bar.y + 3, 64, 28), "Pause" if a["play"] else "Play", self.play, a["play"])
        dur = self.model.anim_dur(c) if c is not None else 0.0
        label = f"{a['t']:.2f} / {dur:.2f} s"
        lw = self.font.size("000.00 / 000.00 s")[0]
        r = pygame.Rect(bar.x + cw + 86, bar.y + 13, bar.w - cw - 104 - lw, 8)
        if r.w < 40:
            return
        self.scrub_rect = r
        pygame.draw.rect(self.ui, PANEL3, r, border_radius=4)
        if dur > 0:
            fx = r.x + int(r.w * a["t"] / dur)
            pygame.draw.rect(self.ui, ACC, (r.x, r.y, fx - r.x, r.h), border_radius=4)
            pygame.draw.circle(self.ui, (255, 255, 255), (fx, r.centery), 7)
        self.hits.append((r.inflate(0, 20), self.start_scrub))
        self.txt(label, r.right + 12, bar.y + 7, TEXT)

    def start_scrub(self):
        if self.anim["clip"] is None:
            self.set_clip(0)
        self.anim["play"] = False
        self.drag = "scrub"
        self.scrub(self.mouse[0])

    # -- rendering
    def lines(self, vp, pts, color):
        if len(pts):
            self.lvbo.write(pts.astype("f4").tobytes())
            self.lprog["u_mvp"].write(gl_mat(vp))
            self.lprog["u_color"].value = color
            self.lvao.render(self.mgl.LINES, vertices=len(pts))

    def draw_scene(self, vp, clean=False):
        """Model, grid, wireframe, axes and bounds into the bound framebuffer; clean = no tints/axes/boxes."""
        ctx, mgl, m = self.ctx, self.mgl, self.model
        ctx.enable(mgl.DEPTH_TEST | mgl.BLEND)
        ctx.blend_func = mgl.SRC_ALPHA, mgl.ONE_MINUS_SRC_ALPHA
        ctx.depth_func = "<="
        light = self.eye() - self.target + np.array([0, self.dist * 0.6, 0])
        p = self.prog
        p["u_light"].value = tuple(light / np.linalg.norm(light))
        p["u_lit"].value = 1.0 if self.opts["Lit"] else 0.0
        p["u_picking"].value = False
        if self.opts["Grid"] and self.pitch >= 0:  # from below the grid would cover the model
            self.lines(vp, self.grid, (0.32, 0.35, 0.42, 1))
        for d in self.draws:
            p["u_mvp"].write(gl_mat(vp @ d["M"]))
            p["u_nmat"].write(d["nmat"])
            p["u_base"].value = d["base"]
            p["u_cut"].value = d["cut"]
            p["u_blend"].value = 1.0 if d["blend"] else 0.0
            if clean:
                p["u_tint"].value = (0, 0, 0, 0)
            elif d["node"] == self.sel or (self.sel_mat is not None and d["mat"] == self.sel_mat):
                p["u_tint"].value = (1.0, 0.69, 0.25, 0.35)
            elif d["node"] == self.hover:
                p["u_tint"].value = (1, 1, 1, 0.12)
            else:
                p["u_tint"].value = (0, 0, 0, 0)
            (d["tex"] if d["tex"] is not None and self.opts["Tex"] else self.white).use(0)
            d["vao"].render()
        if self.opts["Wire"]:
            ctx.wireframe = True
            p["u_tint"].value = (0.05, 0.05, 0.06, 0.85)
            for d in self.draws:
                p["u_mvp"].write(gl_mat(vp @ d["M"]))
                d["vao"].render()
            ctx.wireframe = False
        ctx.disable(mgl.DEPTH_TEST)
        if clean:
            return
        s = (m.bounds[1] - m.bounds[0]).max() * 0.15 if m.bounds is not None else 1
        for axis, col in ((0, (0.95, 0.35, 0.35, 1)), (1, (0.4, 0.9, 0.4, 1)), (2, (0.4, 0.6, 1, 1))):
            e = np.zeros(3)
            e[axis] = s
            self.lines(vp, np.array([[0, 0, 0], e], np.float32), col)
        if self.opts["Bounds"]:
            b = self.sel_box() if self.sel is not None else None
            if b is not None:
                self.lines(vp, box_lines(*b), (1, 0.69, 0.25, 1))
            elif m.bounds is not None:
                self.lines(vp, box_lines(*m.bounds), (0.6, 0.63, 0.7, 0.5))

    def render(self):
        ctx, mgl = self.ctx, self.mgl
        W, H = self.size
        ctx.viewport = (0, 0, W, H)
        ctx.clear(*(c / 255 for c in BG))
        m = self.model
        if m is not None:
            ctx.viewport = ctx.scissor = (self.PW, 0, W - self.PW, H)
            ctx.clear(*(c / 255 for c in VIEW_BG))
            ctx.scissor = None
            self.draw_scene(self.viewproj())
        ctx.viewport = (0, 0, W, H)
        ctx.enable(mgl.BLEND)
        ctx.blend_func = mgl.SRC_ALPHA, mgl.ONE_MINUS_SRC_ALPHA
        self.ui_tex.write(pygame.image.tobytes(self.ui, "RGBA", True))
        self.ui_tex.use(0)
        self.qvao.render(mgl.TRIANGLE_STRIP)

    # -- loop
    def run(self):
        clock, dt = pygame.time.Clock(), 0
        while True:
            self._resize()
            W, H = self.size
            self.mouse = pygame.mouse.get_pos()
            for e in pygame.event.get():
                if e.type == pygame.QUIT:
                    return
                if e.type == pygame.DROPFILE:
                    self.load(e.file)
                elif e.type == pygame.MOUSEBUTTONDOWN and e.button in (1, 2, 3):
                    if e.button == 1:
                        hit = next((fn for r, fn in reversed(self.hits) if r.collidepoint(e.pos)), None)
                        self.popup_was, self.show_recent = self.show_recent, False  # any click closes the popup
                        if hit:
                            hit()
                            continue
                    if e.pos[0] >= self.PW and self.model is not None:
                        self.drag, self.down = ("orbit" if e.button == 1 else "pan"), e.pos
                elif e.type == pygame.MOUSEBUTTONUP:
                    if e.button == 1 and self.drag == "orbit" and math.dist(e.pos, self.down) < 4:
                        self.select(self.pick(*e.pos))
                        self.tab = "Nodes"
                    self.drag = None
                elif e.type == pygame.MOUSEMOTION and self.drag:
                    dx, dy = e.rel
                    if self.drag == "scrub":
                        self.scrub(e.pos[0])
                    elif self.drag == "orbit":
                        self.yaw -= dx * 0.008
                        self.pitch = max(-1.55, min(1.55, self.pitch + dy * 0.008))
                    else:
                        f = self.target - self.eye()
                        f /= np.linalg.norm(f)
                        right = np.cross(f, (0, 1, 0))
                        right /= np.linalg.norm(right)
                        up = np.cross(right, f)
                        k = self.dist * 0.0012
                        self.target = self.target - right * dx * k + up * dy * k
                elif e.type == pygame.MOUSEWHEEL:
                    pane = next((k for k, r in self.panes.items() if r.collidepoint(self.mouse)), None)
                    if pane is not None:
                        self.scroll[pane] -= e.y * 54
                    elif self.mouse[0] >= self.PW:
                        self.dist *= 0.88 ** e.y
                elif e.type == pygame.KEYDOWN:
                    self.key(e)
            now = pygame.time.get_ticks()
            a = self.anim
            if self.model is not None and a["play"] and a["clip"] is not None:
                dur = self.model.anim_dur(a["clip"])
                a["t"] = (a["t"] + dt / 1000) % dur if dur > 0 else 0.0
                self.apply_pose()
            if self.model is not None and not self.drag and now - self.last_pick > 60:
                self.last_pick = now
                self.hover = self.pick(*self.mouse) if self.mouse[0] >= self.PW else None
            self.hits, self.panes = [], {}
            self.ui.fill((0, 0, 0, 0))
            self.draw_panel()
            self.draw_overlay()
            self.render()
            pygame.display.flip()
            dt = clock.tick(60)

    def key(self, e):
        ctrl = e.mod & pygame.KMOD_CTRL
        if e.key == pygame.K_o:
            self.ask_open()
        elif self.model is None:
            return
        elif e.key == pygame.K_c and ctrl:
            self.copy()
        elif e.key == pygame.K_s and ctrl:
            self.export()
        elif e.key == pygame.K_w and ctrl:
            self.close(self.cur)
        elif e.key == pygame.K_TAB and len(self.docs) > 1:
            self.switch((self.cur + (-1 if e.mod & pygame.KMOD_SHIFT else 1)) % len(self.docs))
        elif e.key == pygame.K_p:
            self.ask_shot()
        elif e.key in VIEWS:
            self.set_view(*VIEWS[e.key], bool(ctrl))
        elif e.key == pygame.K_SPACE and self.model.j.get("animations"):
            self.play()
        elif e.key == pygame.K_f:
            self.frame(self.sel)
        elif e.key == pygame.K_ESCAPE:
            self.sel = self.sel_mat = None
        elif e.key in TOGGLE_KEYS:
            self.toggle(TOGGLE_KEYS[e.key])
        elif e.key in (pygame.K_UP, pygame.K_DOWN) and self.rows:
            k = self.rows.index(self.sel) if self.sel in self.rows else -1
            k = max(0, min(len(self.rows) - 1, k + (1 if e.key == pygame.K_DOWN else -1)))
            self.select(self.rows[k])
            self.tab = "Nodes"
        elif e.key in (pygame.K_LEFT, pygame.K_RIGHT) and self.sel is not None:
            (self.collapsed.add if e.key == pygame.K_LEFT else self.collapsed.discard)(self.sel)


# ---------------------------------------------------------------- self-check

def selftest():
    pos = np.array([[0, 0, 0], [1, 0, 0], [0, 2, 0]], np.float32).tobytes()
    col = np.array([[1, 0, 0, 1]] * 3, np.float32).tobytes()
    times = np.array([0, 1], np.float32).tobytes()
    moves = np.array([[1, 0, 0], [3, 0, 0]], np.float32).tobytes()
    blob = pos + col + times + moves
    j = {"asset": {"version": "2.0"}, "scene": 0, "scenes": [{"nodes": [0]}],
         "nodes": [{"name": "root", "translation": [1, 0, 0], "children": [1]},
                   {"name": "tri", "mesh": 0, "scale": [2, 2, 2]}],
         "meshes": [{"primitives": [{"attributes": {"POSITION": 0, "COLOR_0": 1}, "material": 0}]}],
         "materials": [{"name": "grey", "pbrMetallicRoughness": {"baseColorFactor": [0.5, 0.5, 0.5, 1]}}],
         "buffers": [{"byteLength": len(blob)}],
         "bufferViews": [{"buffer": 0, "byteOffset": 0, "byteLength": 36},
                         {"buffer": 0, "byteOffset": 36, "byteLength": 48},
                         {"buffer": 0, "byteOffset": 84, "byteLength": 8},
                         {"buffer": 0, "byteOffset": 92, "byteLength": 24}],
         "accessors": [{"bufferView": 0, "componentType": 5126, "count": 3, "type": "VEC3"},
                       {"bufferView": 1, "componentType": 5126, "count": 3, "type": "VEC4"},
                       {"bufferView": 2, "componentType": 5126, "count": 2, "type": "SCALAR", "min": [0], "max": [1]},
                       {"bufferView": 3, "componentType": 5126, "count": 2, "type": "VEC3"}],
         "animations": [{"name": "slide", "samplers": [{"input": 2, "output": 3}],
                         "channels": [{"sampler": 0, "target": {"node": 0, "path": "translation"}}]}]}
    js = json.dumps(j).encode()
    js += b" " * (-len(js) % 4)
    glb = (struct.pack("<III", 0x46546C67, 2, 28 + len(js) + len(blob)) + struct.pack("<II", len(js), 0x4E4F534A)
           + js + struct.pack("<II", len(blob), 0x004E4942) + blob)
    path = os.path.join(tempfile.mkdtemp(), "t.glb")
    with open(path, "wb") as f:
        f.write(glb)
    m = Model(path)
    assert np.allclose(m.wb[1][0], [1, 0, 0]) and np.allclose(m.wb[1][1], [3, 4, 0]), m.wb
    assert np.allclose(m.tb[0][1], [3, 4, 0]) and m.prims[0][0]["tris"] == 1
    assert m.prims[0][0]["vcolors"][1][0][0] == "#FF0000"
    assert m.material_report(0)["base_color"].startswith("#BCBCBC")
    json.dumps(m.report())
    assert m.anim_dur(0) == 1.0
    assert np.allclose(m.pose(0, 0.5)[1][:3, 3], [2, 0, 0]) and np.allclose(m.pose(0, 9)[0][:3, 3], [3, 0, 0])
    q = m.sample({"input": 2, "output": 3}, 0.25, False)
    assert np.allclose(q, [1.5, 0, 0]), q
    assert file_header(1, 3, path).startswith("##### FILE 2/3: t.glb")
    print("SELFTEST OK")


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        selftest()
    elif "--brief" in sys.argv:  # python tools/glb_inspector.py --brief a.glb b.glb
        files = [p for p in sys.argv[1:] if not p.startswith("-")]
        print("\n\n".join(file_header(k, len(files), p) + "\n" + Model(p).brief() for k, p in enumerate(files)))
    elif "--write-icon" in sys.argv:  # regenerates tools/glb_inspector.ico for the exe build
        write_ico(os.path.join(os.path.dirname(os.path.abspath(__file__)), "glb_inspector.ico"))
    else:
        App([a for a in sys.argv[1:] if not a.startswith("-")]).run()
