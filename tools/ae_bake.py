"""ae_bake - bake / check / lint content packs (RPE6 Phase 3, §6.5).

    python tools/ae_bake.py [--pack m5] [--check] [--lint] [--lint-all] [--sheet out.png] [--only id,id]

Default (no flags): bake every rendered asset of the selected packs to
``assets/baked/<pack>/`` and write ``.bakeinfo.json`` (content hashes).
``--check``   recompute the hashes, verify every baked file exists and
              re-render a deterministic 10 % sample (pixel byte-compare);
              exit 1 on stale/missing/mismatch. Never writes.
``--lint``    alpha fringe on every variant, palette distance for assets tagged
              ``palette``, light direction for ``lit``, text fit for modules
              with ``TEXT_BOXES``. Warnings are advisory (exit 0) unless
              ``--strict``. ``--lint-all`` runs palette+light on every asset
              regardless of tags (triage numbers for BUGS.md).
``--sheet``   contact sheet PNG for the pack (default off; CI writes to build/).
Packs are discovered as ``src/game/content/*/manifest.json``.
"""
from __future__ import annotations

import argparse
import glob
import os
import sys
from pathlib import Path

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))


def discover(pack: str | None) -> list[str]:
    paths = sorted(glob.glob(str(ROOT / "src" / "game" / "content" / "*" / "manifest.json")))
    if pack:
        paths = [p for p in paths if Path(p).parent.name == pack]
    return paths


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--pack")
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--lint", action="store_true")
    ap.add_argument("--lint-all", action="store_true")
    ap.add_argument("--strict", action="store_true", help="lint warnings fail the run")
    ap.add_argument("--sheet", help="contact sheet output path")
    ap.add_argument("--only", help="comma-separated asset ids to bake")
    ap.add_argument("-q", "--quiet", action="store_true")
    args = ap.parse_args(argv)

    import pygame
    pygame.init()
    from engine.assets import bake_pack, check_pack, contact_sheet, lint_pack, load_manifest
    from engine.assets.manifest import AssetDef  # tools may reach owner modules (lint E4 exempts tools)

    manifests = discover(args.pack)
    if not manifests:
        print("ae_bake: no manifests found" + (f" for pack {args.pack!r}" if args.pack else ""))
        return 2
    rc = 0
    say = (lambda *a: None) if args.quiet else print
    tot = {"packs": 0, "baked": 0, "checked": 0, "sampled": 0, "stale": 0, "missing": 0, "mismatched": 0,
           "errors": 0, "lint_warnings": 0}
    for mp in manifests:
        m = load_manifest(mp)
        if args.lint_all:
            m.assets = {k: AssetDef(**{**v.__dict__, "tags": tuple(set(v.tags) | {"palette", "lit"})}) for k, v in m.assets.items()}
        did = False
        if args.check:
            did = True
            rep = check_pack(m, str(ROOT))
            print(rep.summary())
            for line in rep.stale + rep.missing + rep.mismatched + rep.errors:
                print("  ", line)
            for k in ("checked", "sampled"):
                tot[k] += getattr(rep, k)
            for k in ("stale", "missing", "mismatched", "errors"):
                tot[k] += len(getattr(rep, k))
            if not rep.ok:
                rc = 1
        if args.lint or args.lint_all:
            did = True
            lrep = lint_pack(m, str(ROOT))
            print(lrep.summary())
            for w in lrep.warnings:
                print("  WARN", w)
            tot["lint_warnings"] += len(lrep.warnings)
            if args.strict and lrep.warnings:
                rc = 1
        if args.sheet:
            did = True
            out = args.sheet if len(manifests) == 1 else str(Path(args.sheet).with_name(f"{m.pack}_{Path(args.sheet).name}"))
            n = contact_sheet(m, str(ROOT), out)
            print(f"sheet {out} ({n} tiles)")
        if not did:
            only = set(args.only.split(",")) if args.only else None
            rep = bake_pack(m, str(ROOT), only=only, verbose=say)
            print(rep.summary())
            for line in rep.errors:
                print("  ", line)
            tot["baked"] += rep.baked
            tot["errors"] += len(rep.errors)
            if not rep.ok:
                rc = 1
        tot["packs"] += 1
    print("AE BAKE SUMMARY: " + " ".join(f"{k}={v}" for k, v in tot.items()))
    print("AE BAKE: " + ("OK" if rc == 0 else "FAIL"))
    return rc


if __name__ == "__main__":
    sys.exit(main())
