#!/usr/bin/env python3
"""AE IMPORT DOG - the Mission 7 guard dog (assets/3D/dawg.glb) and its clips.

    python tools/ae_import_dog.py [--scale 0.40] [--fps 20]

Reuses the GLB walker from tools/ae_import_k93d.py. The dog is rigid parts on a
node hierarchy (Body, Neck, Head, Jaw, legs, knees, Tail, ears, eyes), animated
by four node-TRS clips: Idle, Run, Bite, Death. Each clip is sampled at --fps
and baked to one 3x4 matrix per part per frame, so the game only multiplies.

Output: src/game/content/meshes/dog_m7.rig.json, in the dog frame the M7 raid
expects: +x forward (the GLB snout is +z), +y up, rest-pose paws on y = 0.
Faces: [indices, colour, emissive] (the unlit eye material glows).
"""
import argparse
import json
import math
import os

import ae_import_k93d as K

ROOT = K.ROOT
SRC = os.path.join(ROOT, "assets", "3D", "dawg.glb")
OUT = os.path.join(ROOT, "src", "game", "content", "meshes", "dog_m7.rig.json")
LOOPS = ("Idle", "Run", "Bite")


def _srgb(c):
    c = max(0.0, min(1.0, c))
    return c * 12.92 if c <= 0.0031308 else 1.055 * c ** (1 / 2.4) - 0.055


def _sample(times, vals, t, rot):
    if t <= times[0]:
        return list(vals[0])
    for k in range(1, len(times)):
        if t <= times[k]:
            a, b = vals[k - 1], vals[k]
            u = (t - times[k - 1]) / max(1e-9, times[k] - times[k - 1])
            if rot and sum(x * y for x, y in zip(a, b)) < 0:
                b = [-x for x in b]
            out = [x + (y - x) * u for x, y in zip(a, b)]
            if rot:
                n = math.sqrt(sum(x * x for x in out)) or 1.0
                out = [x / n for x in out]
            return out
    return list(vals[-1])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scale", type=float, default=0.40)
    ap.add_argument("--fps", type=float, default=20.0)
    args = ap.parse_args()

    g, binbuf = K._gltf(SRC)
    nodes = g["nodes"]
    parent = {}
    for i, nd in enumerate(nodes):
        for ch in nd.get("children", []):
            parent[ch] = i

    def local(i, pose):
        nd = nodes[i]
        if i not in pose and "matrix" in nd:
            return nd["matrix"]
        trs = dict(nd)
        trs.update(pose.get(i, {}))
        return K._mul(K._mul(K._trs({"translation": trs.get("translation", [0, 0, 0])}),
                             K._trs({"rotation": trs.get("rotation", [0, 0, 0, 1])})),
                      K._trs({"scale": trs.get("scale", [1, 1, 1])}))

    def world(i, pose, memo):
        if i not in memo:
            m = local(i, pose)
            memo[i] = K._mul(world(parent[i], pose, memo), m) if i in parent else m
        return memo[i]

    cols, glow = [], []
    for m in g.get("materials", []):
        f = m.get("pbrMetallicRoughness", {}).get("baseColorFactor", [1, 1, 1, 1])
        cols.append([int(round(_srgb(c) * 255)) for c in f[:3]])
        glow.append("KHR_materials_unlit" in m.get("extensions", {}))

    parts, owners = [], []
    for i, nd in enumerate(nodes):
        if "mesh" not in nd:
            continue
        for pr in g["meshes"][nd["mesh"]]["primitives"]:
            pos = K._acc(g, binbuf, pr["attributes"]["POSITION"])
            idx = [k[0] for k in K._acc(g, binbuf, pr["indices"])]
            mat = pr.get("material", 0)
            parts.append({
                "verts": [[round(c, 4) for c in p] for p in pos],
                "faces": [[idx[k:k + 3], cols[mat], glow[mat]] for k in range(0, len(idx) - 2, 3)],
            })
            owners.append(i)

    rest = {}
    y0 = min(K._xf(world(i, {}, rest), p)[1] for i, pt in zip(owners, parts) for p in pt["verts"])
    sc = args.scale

    def baked(pose):
        memo, out = {}, []
        for i in owners:
            m = world(i, pose, memo)
            # GLB snout is +z: game x = z, game z = -x (a proper rotation, no mirror).
            rows = ((m[2], m[6], m[10], m[14]), (m[1], m[5], m[9], m[13] - y0),
                    (-m[0], -m[4], -m[8], -m[12]))
            out.append([round(v * sc, 4) for row in rows for v in row])
        return out

    clips = {}
    for a in g.get("animations", []):
        chans = []
        for c in a["channels"]:
            s = a["samplers"][c["sampler"]]
            chans.append((c["target"]["node"], c["target"]["path"],
                          [t[0] for t in K._acc(g, binbuf, s["input"])],
                          K._acc(g, binbuf, s["output"])))
        dur = max(ch[2][-1] for ch in chans)
        loop = a["name"] in LOOPS
        n = max(12, int(round(dur * args.fps)))
        frames = []
        for f in range(n if loop else n + 1):
            t = dur * f / n
            pose = {}
            for node, path, times, vals in chans:
                pose.setdefault(node, {})[path] = _sample(times, vals, t, path == "rotation")
            frames.append(baked(pose))
        clips[a["name"]] = {"dur": round(dur, 4), "loop": loop, "frames": frames}

    data = {
        "schema": "ae.rig/1",
        "id": "dog_m7",
        "source": os.path.basename(SRC),
        "meta": {"scale": sc, "fps": args.fps},
        "parts": parts,
        "clips": clips,
    }
    with open(OUT, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(data, fh, separators=(",", ":"))
        fh.write("\n")
    print("AE IMPORT DOG: %d parts, %d tris" % (len(parts), sum(len(p["faces"]) for p in parts)))
    for name, c in clips.items():
        print("  %-6s %.2fs  %d frames%s" % (name, c["dur"], len(c["frames"]), "  loop" if c["loop"] else ""))
    print("  ->", os.path.relpath(OUT, ROOT), "%.0f KB" % (os.path.getsize(OUT) / 1024))


if __name__ == "__main__":
    main()
