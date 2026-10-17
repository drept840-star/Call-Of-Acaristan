# Subsystem: `engine.assets` (Phases 3, 6)

Art packs: manifest-declared sprites baked deterministically from
procedural painters, loaded through a registry with hot reload.

```
engine.assets
  manifest.py        MANIFEST_SCHEMA, AssetDef, Manifest, load_manifest
  registry.py        AssetRegistry + AssetReloaded event + PLACEHOLDER
  bake.py            bake_pack/check_pack/lint_pack, BakeSurface, pixel_hash/source_hash
  layerbake.py       bake_camera_layer/bake_chunk_layer/probe_layer/screen_emulation
  loaders.py         load_image/load_sound/load_music, configure_loaders
  watch.py           AssetWatcher (dev-time file watching)
tools/ae_bake.py     game-side driver: --check (staleness), --pack <mission>, --lint
src/game/art/        the per-mission painters the packs bake from
```

Rules: any painter-module edit — even non-visual — trips the bake
staleness check (SysFont painters are machine-dependent), so repack
and let the goldens prove the pixels; never delete the procedural
fallback at an artpack call site; regenerated PNG/JSON are committed
together with the generator change.
