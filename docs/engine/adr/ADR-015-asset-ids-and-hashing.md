# ADR-015: Asset ids, manifests, bake hashing and the fallback chain

Status: accepted (Phase 3) · Date: 2026-10-14

Numbering note: this is the master prompt's mandatory "005 asset ids and hashing" ADR. The number 005 was already taken by `ADR-005-frame-coherent-wall-clock.md` in Phase 1, so the file carries the next free number in the series; the content is the §6.5 decision.

## Context
- §6.5 asks for one asset registry with stable ids, a manifest per content pack, deterministic bakes of the procedural sprite modules, content hashing so a stale bake fails CI, hot reload in dev, and lint checks (alpha fringe, palette, light direction, text fit).
- The repository already had a working prototype for Mission 5: `src/art/m5/` (20 modules, 125 variants, `render(variant, scale)`), `tools/bake_m5_sprites.py`, `assets/sprites/m5/*.png`, a `get()` with the chain *baked PNG → live render → None*, and a smoke check that re-rendered all 125 variants and byte-compared them (slow, but exact). The second tier (`engine.assets.artpack` sheets built by `tools/sprites/*`) has its own byte-identical rebuild check.
- Converting the M1–M4 procedural draw calls to baked blits is a different kind of change (not bit-identical by construction - pre-composited straight alpha rounds differently), so the pipeline had to be built and proven on the existing pack *without* touching mission pixels.

## Decision
1. **Ids and manifests.** An asset id is `<pack>/<name>` (`m5/armband`); a variant is an integer, or a name resolved through the manifest's `variant_names` / the module's `VARIANT_NAMES` (`"m5/inspect_art:tram"` is also accepted by `get`). Each pack declares its assets in `src/game/content/<pack>/manifest.json`, schema `ae.manifest/1` (`engine.assets.load_manifest` validates: kinds `image|sprite_def|sheet|font|sound|music|data|layer`, id prefix, module/path presence, unique ids, resolvable fallbacks). Rendered kinds (`sprite_def`, `layer`) name a module with `render(variant, scale)` and `VARIANTS`; the baked file pattern defaults to `<baked_dir>/<name>_<variant>.png`.
2. **Registry chain.** `AssetRegistry.get(id, variant, scale, baked=True, default=PLACEHOLDER)` resolves **baked file → live render → declared `fallback` → placeholder** (dev: magenta checker + one warning per id on the `assets` log channel; release: transparent). Callers that keep a procedural fallback pass `default=None` and get `None`, exactly the legacy `art.m5.get` contract (R: never delete procedural fallbacks). Baked loading mirrors the legacy loader to the pixel (`image.load`, `convert_alpha()` only when a display exists, nearest `transform.scale(int(w*s), int(h*s))`). Results are cached per `(id, variant, scale, baked)`; `invalidate(id)` drops entries; `acquire(pack, owner)/release(owner)/unload_pack` give loading scenes ref-counted packs.
3. **Hashing.** `tools/ae_bake.py` writes `assets/baked/<pack>/.bakeinfo.json` (`ae.bakeinfo/1`) with, per asset, a **source hash** = sha256(tool version + module source + the source of every in-package module it imports transitively + any module named in its `BAKE_DEPS` + the pack palette file) and, per variant, the RGBA **pixel hash** and size. `--check` recomputes the source hashes (no rendering), verifies every baked file exists, then re-renders a deterministic 10 % sample (every 10th `(id, variant)`) and byte-compares RGBA with the file. Stale, missing or mismatched → exit 1 (CI row "asset bake check + lint"). Package `__init__` files are deliberately *not* hashed (editing the registry wrapper must not stale 125 bakes). Bakes are deterministic: all sprite modules use `random.Random(fixed seed)` and the kit's bitmap font; a re-bake of the m5 pack reproduced all 125 PNGs byte-for-byte.
4. **Hot reload.** `AssetWatcher` (stdlib polling, 500 ms) maps every asset to its module file + baked files; a change calls `registry.reload(id)`, which **re-executes the module from source** (not `importlib.reload`, whose `.pyc` mtime stamp misses same-second edits), drops the cache entries and emits `AssetReloaded(id, reason)` on the registry's bus. The game enables it with `ACARISTAN_HOT_RELOAD=1` (`app.py`, off by default).
5. **Lint is advisory and opt-in where taste is involved.** Alpha fringe runs on every variant (tag `shadow` opts out an intentional soft shadow); palette distance only for assets tagged `palette` (the pack palette `palette.json` is the ten `_kit` constants - most sprites mix/shade on purpose, so it is not a default); light direction only for `lit` (upper-left must read brighter, the `_kit.bevel` convention); text fit for modules declaring `TEXT_BOXES`. Warnings never fail the gate unless `--strict`; they are triaged into BUGS.md.
6. **Ownership move with a shim.** The pack lives at `src/game/art/m5/` (game-owned content; the engine never imports it). `src/art/m5/__init__.py` stays as a compatibility shim (A-008) that re-exports the API and aliases every submodule in `sys.modules` (`art.m5.bale is game.art.m5.bale`), so the 30+ historical import forms keep working and hot reload stays coherent. Baked files moved to `assets/baked/m5/` (the §6.5 location).

## Alternatives considered
- Keep the full 125-variant re-render in the smoke test: exact but ~7 s per run and it only covered m5; the hash + sample check is <1 s per pack and generalises. The sample is deterministic so a failure reproduces.
- Hash the baked PNG bytes instead of RGBA pixels: PNG encoders differ between pygame/SDL_image builds (owner machine vs sandbox), pixels do not.
- `importlib.reload` for hot reload: rejected after it silently kept stale code in the unit test (same-second edit, same size).
- Atlases: §6.5 says optional/off by default; not built. The registry's cache key already leaves room for a sheet-backed `Surface` subsurface.

## Consequences
- Good: one pipeline for every future pack (`tools/ae_bake.py` discovers `src/game/content/*/manifest.json`); D5 holds (0 raw loads outside `engine/assets`: `load_image/load_sound/load_music` are the chokepoints); the `art.m5` prototype is retired into the registry with pixel parity (golden 353/353); hot reload is testable headlessly.
- Bad / deliberate: the ≥ 80 % procedural-draw conversion for M1–M4 was **not** attempted in this phase (3,992 `pygame.draw` call sites in M1–M4, converted share 0.7–1.9 %, `docs/engine/audit/draw_census.md`); each conversion changes pixels and needs its own re-baselined goldens with before/after proof, mission by mission. The lint palette check with the 10-colour kit palette flags almost everything (67 warnings with `--lint-all`), which is why it is opt-in.
- Follow-ups: conversions ranked by the census (`_draw_archives_wing_details` 202 calls, `_draw_garden` 84, `_game_draw_inner` 91, ...); `BAKE_DEPS` is a manual declaration - a renamed painter module silently drops out of the hash (mitigated by the 10 % sample); `inspect_art` layers depend on `missions.m5` painters (game-owned, declared via `BAKE_DEPS`).

## Verification
- `python tools/ae_bake.py --check --lint` → `AE BAKE: OK` (checked 20, sampled 13, 2 advisory fringe warnings).
- `python -m unittest tests.unit.test_assets_registry` (20 tests: schema errors, chain, cache, ref-counts, bake determinism, stale/mismatch detection, hot reload with `AssetReloaded`, loaders, pose cache, D5 guard, shim identity).
- Full gate `/tmp/ci_phase3.txt`; golden 353/353 bit-identical after the move.

## Addendum 2026-10-14 — world layers (`kind: layer`) and the two conversion tiers

- **Tier A (chunk callback → baked world layer).** Every `_bake_mN_*(surf, ox, oy)` callback that the
  runtime chunk cache (`core/staticlayer.py`) used is rendered offline by
  `game.art._layers.render_callback_layer` (512-px tiles, `staticlayer.set_baking(True)`, black fill) into
  one opaque RGB PNG per STATE variant. Because the same callback paints both the runtime chunks and the
  bake, the file is bit-identical to the live chunk path — `tools/ae_layer_parity.py` proves it per variant.
  Adapters declare `VARIANTS`, `variant_for_state()` (None → fall back to the chunk path for unknown
  flag combinations), `bake_setup(variant)` (tools only: start the checkpoint and set the flags) and
  `BAKED_ONLY = True` (a missing file never triggers a 20 s live render at runtime).
- **Per-frame bits inside callbacks** (LED blinks, scan lines, stage captions) are guarded by
  `staticlayer.baking()` and redrawn by `_draw_<x>_live()` right after the static blit. The old chunk cache
  had frozen them at bake time; un-freezing is a deliberate behaviour change recorded per mission
  (`tests/loop/baseline_v4`, B-017 note).
- **Tier B (per-frame painter → camera layer / sprite).** Static painters that draw straight to `screen`
  with `(cam_x, cam_y)` are baked through `bake_camera_layer` (transparent RGBA, cropped to
  `layer_bounds`, `BakeSurface` composites straight-alpha draws exactly) and blitted at their original
  z-position; dynamic parts are split into `_<name>_live()`. `tools/ae_layer_probe.py` is the oracle
  (EXACT / max Δ1 for stacked translucency).
- **Memory.** Layers stay whole PNGs (palette PNGs rejected: 1.8–7.4 k colours per layer). The registry
  keeps opaque layers 24-bit and evicts least-recently-used layer surfaces past `layer_budget_bytes`
  (160 MB; M2 = 70 MB resident). Chunk-file storage is the fallback plan if a platform needs less.
- **Determinism rules learned.** `ae_bake.py` pins `PYTHONHASHSEED=0` and the wall clock (100 s); bake
  callbacks must not use `hash()`-seeded RNGs (B-017) or read the clock outside a `baking()` guard.

## Addendum 2026-10-14 (2) — `sprite_def` for per-frame painters, and the exactness rule

- **Pattern.** A per-frame painter `_draw_x(surface, x, y, state…)` is split into `_paint_x(...)` (pure,
  explicit state, no clock / STATE reads) and a thin `_draw_x` that computes the state, picks the variant,
  blits `Pack.get("x", variant)` at the painter's anchor and otherwise calls `_paint_x` (fallback). Dynamic
  bits (blinking LEDs, pulsing glows, cursors, swing animations, damage overlays) are either drawn live after
  the blit or keep the whole painter procedural for that state (`_draw_m3_door_tile` while swinging).
  Adapters: `VARIANTS`, `VARIANT_NAMES`, `SIZE`, `render(variant, scale)` calling the `_paint_*` with the
  painter's anchor inside the canvas; manifest `kind: sprite_def`.
- **Exactness rule (pygame `ALPHA_BLEND`).** An RGBA source over a destination pixel with `dA == 255` uses
  the same integer formula as a blit onto an RGB screen; over `dA == 0` the source is copied verbatim; only
  `0 < dA < 255` differs. Hence a sprite built on a transparent canvas is bit-identical to the live draw iff
  every translucent draw lands on canvas pixels that are fully opaque or still untouched — opaque primitives
  anywhere, one translucent layer per pixel. Where two translucent draws would stack on bare canvas (M1 exfil
  headlight glow over the soft ground shadow, M2 pickup halos, M3 monitor glow) the later one is drawn live.
  Opaque canvases (`m3/door_tile`, layers) have no such constraint.
- **Re-ordering live bits after the sprite** is allowed only when nothing drawn later by the painter overlaps
  them; checked per case (`docs/engine/evidence/tierB/*_sprite_parity.txt` compares painter vs sprite+live on noise backgrounds at
  two clock phases, and the loop / goldens cover the in-game frames).
- **Layer z-order emulation** (neighbour cells inside `m3/cellblock_static`): a live element drawn over a
  baked layer must re-apply everything the painters drew over it afterwards (tube stains + the cell-1
  graffiti over the light tube; paper scraps over the flies). The overlays were enumerated by rendering
  painter-with vs painter-without the element in one harness and listing the residual pixels.
