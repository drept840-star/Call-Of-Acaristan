"""engine.assets - asset access (RPE6).

Tiers:
* ``artpack`` / ``sprites`` - the loaded-art tier (PNG tiles, icons, 9-slices, pose cache,
  sprite sheets with procedural fallbacks; Phase 2). Hosts call ``artpack.configure(resolver)``.
* manifest/registry/bake/watch - the content-pack pipeline (Phase 3, §6.5): ``load_manifest``
  (schema ``ae.manifest/1``), ``AssetRegistry`` (baked → live render → fallback → placeholder,
  caching, ref-counts, ``reload`` + ``AssetReloaded``), ``bake_pack``/``check_pack``/``lint_pack``/
  ``contact_sheet`` (deterministic bake, ``.bakeinfo.json`` content hashes), ``AssetWatcher``.
* ``load_image`` / ``load_sound`` / ``load_music`` - the only sanctioned raw loaders (D5).
* layerbake - ``bake_camera_layer``/``layer_bounds``/``probe_layer``: turn a legacy camera-space painter
  into a baked world layer and measure its parity against the live painter.

``artpack`` and ``sprites`` are namespaces (owner modules ``_artpack``/``_sprites``); game code
imports everything from this facade only.
"""
from __future__ import annotations

from . import _artpack as artpack
from . import _sprites as sprites
from .bake import (BakeReport, LintReport, bake_pack, check_pack, contact_sheet, lint_pack,
                   pixel_hash, source_hash)
from .layerbake import BakeSurface, bake_camera_layer, bake_chunk_layer, layer_bounds, probe_layer, screen_emulation
from .loaders import load_image, load_music, load_sound
from .loaders import configure as configure_loaders
from .manifest import SCHEMA as MANIFEST_SCHEMA
from .manifest import AssetDef, Manifest, load_manifest
from .registry import PLACEHOLDER, AssetRegistry, AssetReloaded
from .watch import AssetWatcher

__all__ = [
    "artpack", "sprites",
    "MANIFEST_SCHEMA", "AssetDef", "Manifest", "load_manifest",
    "AssetRegistry", "AssetReloaded", "PLACEHOLDER", "AssetWatcher",
    "BakeReport", "LintReport", "bake_pack", "check_pack", "lint_pack", "contact_sheet",
    "pixel_hash", "source_hash",
    "BakeSurface", "bake_camera_layer", "bake_chunk_layer", "layer_bounds", "probe_layer", "screen_emulation",
    "load_image", "load_sound", "load_music", "configure_loaders",
]
