# ARCHITECTURE_MAP

Purpose: name the exact files and live contracts to read/edit for a task in one pass. Paths are from the repo root; game code is under `src/` (imports are rooted there: `missions.m6.draw` = `src/missions/m6/draw.py`). Short forms: `engine/...`, `ui/...`, `core/...` = `src/<path>`; `mN/...` = `src/missions/mN/...`; `content/...` = `src/game/content/...`. Working rules (facades, shared state, renderer, sprite pipeline, story canon) are in `AGENTS.md`. **Slimmed 2026-11-20:** historical patch notes -> `docs/worklog.md`; the per-file source/tools/tests catalogs and dev-jump table -> `docs/FILE_INDEX.md` (both generated / appended by `tools/sync_arch_map.py`). On conflict, the code wins: re-grep the symbol.

Contents: 1 Runtime spine - 2 Engine API by file (2.1 shared 3D/cutscene signatures + coordinate contracts) - 3 Game-side packages - 4 Call chains & shared ownership - 5 Weapon/item crosswalk - 6 One-shot bundles - 7 Gotchas & gates - 8 3D assets inventory - 9 Main loop, FSM, event routing, 3D scene contract - 10 Mission catalogue - 11 Environment variables - 12 Dev affordances - 13 Persistent files - 14 Data formats - 15 assets/ map - 16 Multiplayer, launcher, builds - 17 More one-shot bundles - 18 CI gates - 19 Glossary, doc index, known drift - 20 Monolith anchors. Full per-file source / tools / tests index + dev-jump table: `docs/FILE_INDEX.md`.

---

## 1. Runtime spine

```
acaristan.py -> import app (src/app.py, runs on import)
  app.py  GameStateManager (core/fsm.py) states: _BootIntroState _EngineIntroState _MenuState _SlotSelectState
          _MultiplayerState _SettingsState _ShopState _CutsceneState _CreditsState
          _BriefingState _WalkState _GameState_ _NotebookInspectState _PausedState
          _DeathState _MissionCompleteState
    _GameState_.update -> core/game_core.game_update(keys) -> missions.mN.game_update   (dispatch by _is_missionN_active)
    _GameState_.draw   -> core/game_core.game_draw(cx, cy) -> missions.mN.game_draw
    start_* entry points: core/game_core.py start_mission{0..8}, start_missionN_<stage>_checkpoint,
                          start_mission7_stage/raid/outro, start_mission8_stage(stage, route)
    cutscenes: app.start_cutscene(shots, after_state) -> CutscenePlayer -> _CutsceneState
```
- Mission packages: `src/missions/mN/__init__.py` is a re-export facade; import order there = load order. Never put logic in it.
- Facade load orders: m1 `map stealth main hotwire update draw` - m2 `meta world starts sniper update draw` - m3 `meta maps world flow interrog systems draw` - m4/m5 `meta maps world flow systems draw` - m6 `meta maps decor stealth world flow systems draw` - m7/m8 `meta flow systems draw`.
- `missions/m8` is imported by `core/game_core.py` but kept out of `_MODULES`; reach it through `start_mission8*`.

## 2. Engine API by file (`src/engine/`, pure, no game imports)

Public names are snapshotted in `tests/api/engine_api.json` (see 7). Packages re-export through `__init__.py` `__all__`.

| File | Key symbols |
|---|---|
| `engine/core/timebase.py` | `now_ms` `now_s` `pin_wall` `unpin_wall` (game time; never `pygame.time.get_ticks`) |
| `engine/core/{app,clock,config,events,log,rng,services,errors,mathx,profiling}.py` | `App` `Clock` `Settings` `EventBus`/`Subscription` `get_log` `derive_seed`/`RngStreams` `Services` `AEError`/`write_crash_report` `clamp lerp smoothstep` `Profiler` |
| `engine/ui/theme.py` | `Theme` (fonts + colours passed to every widget) |
| `engine/ui/std/weapon_panel.py` | `WeaponInfo` (+`from_state(STATE)`), `draw(surface, theme, info, *, panel_bg, mag_icon, x, y, panel_h, reload_label_dx)`, `RELOAD_MS`, `PANEL_W/H` |
| `engine/ui/std/health_bar.py` | `draw` |
| `engine/ui/std/hostiles.py` | `draw` (HOSTILES box) |
| `engine/ui/std/objective_banner.py` | `draw` |
| `engine/ui/std/minimap.py` | `MiniMap` (subclassed by `ui/hud.py` `MiniMap`) |
| `engine/ui/std/crosshair.py` | `color_for` `draw` `draw_combat` |
| `engine/ui/std/prompt.py` | `draw` `build` (key-cap interaction prompt) |
| `engine/ui/std/bottle_hud.py` | `draw` (M1/M2 molotov count) |
| `engine/ui/std/dialogue_box.py` | `reset_slide` `slide` `draw` (cutscene box; used by `cutscenes/engine.py`) |
| `engine/text/strings.py` | `T(key, **kw)` `load_strings` `table` `missing_keys` `marker`; `DEFAULT_TABLE` = `src/game/content/strings/en.json` |
| `engine/text/layout.py` | `measure` `wrap_lines` `ellipsize` `fits` `check_fit` `draw_line` |
| `engine/text/fonts.py` | `font_dir` `load_face` `missing_glyphs` |
| `engine/assets/registry.py` | `AssetRegistry` (`get(id, variant, scale, baked=True)`: baked PNG -> live `render()` -> declared fallback -> placeholder), `AssetReloaded` |
| `engine/assets/manifest.py` | `AssetDef` `Manifest` `load_manifest` (`ae.manifest/1`) |
| `engine/assets/bake.py` | `bake_pack` `check_pack` `lint_pack` `source_hash` `contact_sheet` (driven by `tools/ae_bake.py`) |
| `engine/assets/layerbake.py` | `bake_camera_layer` `bake_chunk_layer` `BakeSurface` (baked world layers) |
| `engine/assets/_artpack.py` | `frame` `frame_anchor` `blit_frame` `vehicle` `prop` `tile` `wall` `icon` `sheet` (backend of `core/artpack.py`) |
| `engine/assets/{loaders,_sprites,watch}.py` | `load_image` `load_sound` `load_music`; `get_sprite`; `AssetWatcher` |
| `engine/scene/{scene,stack,cutscene,inspect}.py` | `Scene` `SceneStack` `CutsceneScene` `InspectScene` |
| `engine/timeline/{model,player,expr}.py` | `Timeline` `load_timeline` `from_dict` `validate`; `TimelinePlayer` `Sample`; `evaluate` `check` |
| `engine/dialogue/{model,runner}.py` | `Dialogue` `load_dialogue`; `DialogueRunner` `DialogueHost` `eval_condition` |
| `engine/render2d/drawables.py` | `Drawable` `DrawContext` `SurfaceDraw` `SpriteDraw` `TextDraw` `RectDraw` `UiPassDraw` `CustomDraw` ... |
| `engine/render2d/{queue,static,pen,camera,postfx,util}.py` | `RenderQueue` `Layer`; `StaticLayers`; `SurfacePen` `RecordingPen` `pen_or_surface`; `Camera2D` `clamp_top_left`; `vignette scanlines letterbox grain color_grade PostFX`; `screen_visible soft_shadow add_radial` |
| `engine/render3d/{scene3d,presets}.py` | `Scene3D` `load_set3d` (`ae.set3d/1` data only, no renderer); `load_preset` `resolve` `blend` |
| `engine/render3d/blast_sprites.py` | `fireball_sprite` `flash_sprite` `ground_flash_sprite` `prewarm` (procedural cached fireball/flash sprites for `vehicle_destruction`) |
| `engine/render3d/vehicle_destruction.py` | `VehicleDestructionManager` (`prewarm()` in `__init__`) `VehicleDestruction` `PartBody` `VEHICLE_PROFILES` `get_vehicle_profile` (3D vehicle breakup/fireball/dust-skirt/cookoff; `phys_occ` flashes, delayed fire mounts, no shockwave line ring) |
| `engine/anim/figure_kit.py` | `SPECS` (cast look table, owner), `draw_character` `draw_prop`; `engine/anim/pose_cache.py` `PoseCache` |
| `engine/ai/{bt,cover,senses,squad}.py` | BT nodes `Tree Selector Sequence Action ...`; `build_spots pick`; `Sight NoiseBus`; `Squad` |
| `engine/collision/{boxes,mesh,nav}.py` | `BoxWorld ray_aabb`; `MeshCollider`; `GridNav` |
| `engine/world/*` | `World` `PrefabLibrary` `System` `Scheduler`, std components `Transform Velocity Collider Health ...` |
| `engine/{level,input,save,settings,lighting}/*` | `Level from_tiled`; `ActionMap`; `snapshot dumps/loads` `statehash`; settings `resolve env_layer`; `LightBuffer LightMap` |

Not in `src/engine/` (no API snapshot): `src/engine3d/` renderer - `core.py` (software, `Mesh` `box`), `gl.py` (ModernGL), `rig.py` (`Humanoid` `POSES` `EXPRESSIONS` `rifle_mesh` `os12_mesh` `shotgun_mesh(with_pump=True)` `shotgun_pump_mesh`), `hold.py` (`GRIPS` `MODES` `hold_weapon` `hold_frame` `hold_cached` `weapon_of`), `ik.py`, `textures.py`. Create renderers via `engine3d.Renderer(...)`.

## 2.1 Shared 3D / Cutscene / Asset API Signatures & Coordinate Contracts

Goal: an AI with only 1-5 target files should not need `engine3d/*`, `m6world3d.py`, `m7world3d.py`, `m5fx3d.py`, `m6fx3d.py`, `render3d_bridge.py` or `ae_import_k93d.py` just to read signatures. The signature block at the end is AST-generated by `tools/sync_arch_map.py` (never edit by hand); the contracts around it are hand-written from the same sources.

**Axes, units, winding (`engine3d/core.py`)**
- Left-handed, metres: `+X` right, `+Y` up, `+Z` forward (into the screen for an un-rotated camera). Matrices are 9-tuples (3x3 row-major): `m_mul(a, b)`, `m_apply(m, v)`.
- `rot_x(deg)`: `+deg` tips `+y` toward `+z` (torso leans forward). `rot_y(deg)`: yaw, `+deg` turns `+z` toward `+x` (clockwise seen from above; yaw 0 faces `+Z`, yaw 90 faces `+X`). `rot_z(deg)`: `+deg` swings a hanging limb (`-y`) out toward `+x`.
- Winding: a face's outward normal is `(b-a) x (c-a)` in the left-handed space. `box`, `prism`, `quad_xz`, `disc_xz` (all return a `Mesh`) already orient outward; only hand-written `Mesh.face(pts, col)` needs care (`double=True` = two-sided).
- `box(w,h,d,col,center=)` axis-aligned; `prism(profile,depth,col,z0)` extrudes a convex 2D `[(x,y)..]` along `+z`; `quad_xz(x0,z0,x1,z1,y,col)` upward ground rectangle (layer 0); `disc_xz(cx,cz,r,y,col,n=9)` upward disc (layer 1). `col` is an `(r,g,b)` or a `Tex` (`engine3d.tex(name,...)`, an RGB tuple subclass).
- Face tuples differ: `Mesh.faces` starts as `(idx_tuple, colour, layer, double_sided, emissive)` (5 items) but `Mesh.add` now preserves any extra tail items (e.g. M6's optional fb + `("uv", slot, uvs)` payload at elements 5/6). `Renderer.add_dynamic` / `pack` want 6+ items `(idx, colour, layer, double, nrm_or_None, emissive[, fb[, uv_tag]])`; convert like `m6world3d.add`: `[(f[0],f[1],f[2],f[3],None,f[4]) for f in m.faces]`, or forward the tail with `[(f[0],f[1],f[2],f[3],None,f[4],*f[5:]) ...]` as `topdown3d.put` does for M6. GL `_pack_faces` accepts the `("uv", slot, uvs)` tag at element 6 OR 7. Layer = paint bucket (0 ground, 1 decal, 2 solid default, `FX_LAYER`=6 for glows/fx sprites in `m5fx3d`/`m6fx3d`).
- `Light(direction, ambient, diffuse, sky, tint)` is the key light (`m7world3d.LOOKS[k]["light"]` is its kwargs). Local lights are plain dicts for `set_lights`: `pos, color, intensity, range, kind='point'|'spot'` (spot adds `dir`, `cone` = cos of the half-angle); the strongest `cap=8` win. `set_pools` = ground lamp pools (`pos, range, color, intensity, hot`).
- `Renderer(w, h, fog, fog_start, fog_end, **kw)` (gl.py) returns `GLRenderer` when moderngl works, else `SoftwareRenderer`; same API. Film-host frame order (see `m7world3d.stage`): `set_lights` -> `set_camera(pos, target, fov, roll)` (hosts call `cam(...)`, which adds handheld drift) -> sky -> `begin()` -> bake static once -> per-frame `add_dynamic` / `add_packed` / `add_resident` / `add_humanoid` / `add_sprite` / `add_blob_shadow` / `add_line3d` -> `flush(surface)` -> grade / `present*` to the screen. `bake(mesh, m, t, tag)` is once-only static geometry (`invalidate_static()` after editing it in place). `pack(wverts, faces)` -> float32 rows (GL only, static method); replay with `add_packed` (re-sent every frame) or `add_resident` (uploaded once, identical every frame; the memoized set). `add_humanoid(...)` returns the joint dict.

**Humanoid rig (`engine3d/rig.py`)** - a pose is a dict of degrees; missing keys fall back to `NEUTRAL`. Build rigs with `Humanoid(spec)` (spec keys in the class docstring); `cutscenes.cast3d.humanoid3d(who, **overrides)` builds one from the 2D `figure_kit.SPECS`.
- Sign rules: `spine` lean forward, `spine_r` side lean, `twist`; `head_p` nod DOWN (+), `head_y` turn, `head_x` lateral shift in m (+ right); `lsh_p`/`rsh_p` shoulder raise FORWARD (+hip_p/+sh_p style), `lsh_r`/`rsh_r` raise OUT, `lsh_y`/`rsh_y` upper-arm roll (elbow swivel, set by `ik`), `lel`/`rel` elbow bend (+ = bend); `lhip_p`/`rhip_p` thigh raise FORWARD (+), `lhip_r`/`rhip_r` out, `lkn`/`rkn` knee bend (+ = shin swings back); `lank`/`rank` ankle point (+ = toes away from the shin; lying bodies need it or the heel props them off the floor); `body_p` whole-body pitch (+ forward, 90 = face down; `prone` 88, `dead_back` -88), `body_r` roll, `lift` metres above auto ground contact (jumps/dives), `rifle_p` (+ = muzzle DOWN) / `rifle_y` rifle vs body. Named poses are partial dicts: `POSES[name]`. `blend(a, b, t)` lerps two poses; `pose_run(phase, lean)`, `pose_drag`, `pose_crawl` are gait functions.
- `EXPRESSIONS` names via `h.set_expression(name, mouth_open)`; `solve_look(eye, target, body_yaw_deg)` -> `(head_y, head_p)` clamped yaw +-38, pitch -14 (up)..+30 (down), smoothing is the caller's; `mouth_flap(t_ms, seed)` -> 0..1 talking mouth. Key lists are in the auto block.
- `ik`: `solve_arm(hum, pose, pos, yaw, side, target, pole=None)` and `solve_leg(...)` return a NEW pose with the limb keys rewritten so the hand/ankle lands on a world `target` (`side` = `"l"`/`"r"`; out-of-reach straightens the limb). `solve_rifle_hold(hum, pose, pos, yaw, target, ...)` shoulders a long gun. `hold`: `hold_weapon(hum, pose, pos, yaw, weapon='rifle', mode='aim', aim=None)` -> pose, `weapon` in `GRIPS` keys, `mode` in `MODES` keys; `hold_cached(hum, pose, weapon, mode, aim=None, key=None)` is the per-frame version; `hold_frame` -> `(pose, origin, basis)` for guns drawn apart from the rig rifle. Gun space = (right, up, forward) metres, origin on the right hand, `+z` muzzle.
- `textures.tex(name, like=None, density=None, tint=False)`: a face colour that shows `assets/tex3d/<name>.png` (names in the auto block); `like=(r,g,b)` keeps that colour's brightness, `tint=True` keeps the colour and takes only the texture's light/dark, `density` (texels/m) counts on first use only, a missing texture returns `like` or grey. Software draws the average colour, GL multiplies the texels.

**`cutscenes/m6world3d.py` actor keys** - `hum(key, hd=False, wound=0, bloody=False, flags=())` caches one `Humanoid` per `(key, flags)`; `actor(r, key, pose, pos, yaw, t, seed=0, amp=1.0, rifle_on=False, expression=None, mouth=None, bias=0.0, hd=False, wound=0, bloody=False, shadow=None, flags=())` calls `hum`, adds breath/sway through `life_pose(pose, t, amp, seed)`, auto-flaps the mouth while that speaker talks, calls `r.add_humanoid` and appends to `LAST` (max 16 dicts `{key, joints, pos, yaw, pose, hd, flags, rifle}`, cleared by `rend()`; read it to put props on hands). `pos` = feet root (ground contact is solved), `yaw` degrees. `add(r, mesh, bias)` queues a `Mesh` (routes to bake / pack memo / `add_dynamic`). `rend()` -> `(renderer, surface)`.
- Key -> result. `("biribel", outfit)`: Biribel with `core.outfits.biribel_3d(outfit)` (`"krap"`, `"guard"` = `OUTFIT_GUARD`, `"krap_armband"`, or a `scene_outfit(...)` id); weapon flags work ONLY on this key and only when not `hd`: `"rifle"` (K9), `"lmg"`, `"shotgun"` (+`"nopump"`), `"ak74"`, `"os12"` (+`"nomag"`), `"sniper_rifle"` (baked bolt-action from `tools/ae_import_sniper.py`, `GRIPS["sniper_rifle"]`; falls back to `rifle_mesh(scope=True)`/`GRIPS["sniper"]` if the asset is missing), plus `"cig_dropped"`; the gun draws only with `rifle_on=True`. `("guard", variant)`: train Guard (`guard_spec`), armed with the variant's rifle, flag `"os12"` swaps it. `("ally", name)`: named cast member WITH a gun (`m7rifle`; `os12` with the flag). Plain `"guard"`: third-person AK guard (`"os12"` swaps). `"ucilev"`: always the sniper rifle. `"president"`+`"bare_sleeve"` and `"maru"`+`"suit"` are look flags. Any other plain string (`"bodi"`, `"alex"`, `"vasile"`, `"volkov"`, `"commander"`, `"krap"`) = `humanoid3d(key)`: UNARMED (no `rifle` in its spec), flags ignored; for an armed Bodi use `("ally", "bodi")`. `SPECS` keys: `biribel vasile volkov commander fisherman balaceanu president maru bodi alex ucilev ipa krap civilian hungry_kid andrei_m` (`"retardovici"` aliases `president`).
- Motion kit: `path(points, smooth)` -> `route(d)` -> `(pos, yaw)`; `walk(hum, route, g, stride, speed, ground)` = planted-foot walk (`walk_stride` / `walk_span` size it, `walk_slip` audits); `sit_pose(hum, seat_y, upper=None)`; `reach(hum, pose, side, target, pos, yaw, pole)` = arm IK to a world point; `planted_pos(hum, pose, yaw, mid_xz, y)` -> root; `ankles` / `knees` = world joints. `m7world3d` has its own `sit_pose(**kw)`, `walk_pose(t, speed, tired)`, `stand_pose(**kw)` and `k(t, start, length)` (clamped smoothstep over milliseconds).

**M7/M8 3D set helpers** - `m7world3d.LOOKS` keys (auto block) are dicts `fog, fog_start, fog_end, light{direction,ambient,diffuse,sky,tint}, sky_top, sky_bot, sodium, stars`. `stage(look, t, eye, tgt, fov, lights=(), hh, seed, size, park, well_roof)` -> `(r, buf)` (lights + camera + sky + static bake, `begin()` already called); add actors, then `finish(surface, r, buf, seed, tag, t)` (flush + present + grade). Helpers return `Mesh`es: `tree(seed)`, `hay(n)`, `_fence(x0,z0,x1,z1,h,every,col,gap)` (gap in world coords), `_hedgerow(x0,z0,x1,z1,seed)`, `_bipyr(cx,cy,cz,r,up,dn,col,col2,n,moon)`, `_t(name, col, tint)` (M7 texture at ground/prop density). `chase_set` meshes face local `+z` forward (tractor, trailer, jeep, rocket, gun_truck) and are placed with `put(r, key, build, pos, yaw, pitch, roll)` (cached by `key`); `stratus(r, buf, t, pal)` paints cloud streaks; `frame(eye, tgt, fov, t, size, look, lights)` = camera + light + sky; `present(r, surface)`. FX: `m5fx3d.glow` and `m6fx3d.glow` share semantics (`max_px` default 200 vs 36); `night_sky(r, buf, t, top, bot, ...)` is `m5fx3d`; `m6fx3d.grade_cine(surface)` = cinematic grade, `present_crisp(src, dst)` = hard-pixel upscale (no return values). Glows/shafts are queued with `r.add_sprite(..., layer=FX_LAYER)` by the hosts.

**Mesh assets (`ae.mesh/1`, ADR-024)** - `game.render3d_bridge.load_mesh_asset(ref)` -> `(verts, faces)` raw lists from `M/<ref>.mesh.json`. Each face is `[idx, [r,g,b]]` (2 items: `k93d`, `akrifle`, `lmg`, `pistol`, `barrel`...) OR `[idx, [r,g,b], flag]` (3 items: `car_m2`, `tractor_m7`, `truck_m7`, `krap_van`, monitors, PCs, medkit; flag 1 = screen/emissive group, other ints = group ids); `idx` = 3 (tri) or 4 (quad) vertex indices. `mesh_for_prim(prim)` runs `for idx, col in faces`, so it only works for 2-item assets and raises `ValueError` on 3-item ones: for those use `game.scenery3d.prop(ref, screen=...)`, which reads `f[0], f[1], f[2]`. Mesh prim: `{"type":"mesh","ref":<id>,"pos":[x,y,z],"yaw":deg,"scale":s}` (yaw sign as `rot_y`). Budget: `tools/ae_import_mesh.py --budget` defaults to 1500 tris per prop (error above); authored importers cluster to their own budget (`k93d` 4042 faces, `truck_m7` 15052), so per-asset counts are in §8.1b / §8.2. `tools/ae_import_k93d.py` reads multi-node GLBs: `_gltf(path)` -> `(json, binbuf)`; `_acc(g, binbuf, i)` reads accessor `i`; `_scan(g, binbuf)` -> `(verts, tris, focus)` with node TRS/matrices applied from the identity root `I4` (tris = `(points, material, group, uv_rgb_hint)`); `_cluster(verts, tris, cell)` -> `(verts, faces)` vertex-clustered to `--cell` metres; output adds `meta` (`muzzle`, `sight`, magazine group) in gun space (+z muzzle, +y up, origin at the trigger). `tools/ae_import_sniper.py` reuses the same reader for `lowpoly_sniper_rifle.glb` (already +z muzzle/+y up/+x right), scales it to `--length` with the origin on the pistol grip and writes `meta` (`muzzle`/`butt`/`guard`/`fore`) mirrored by `engine3d.hold.GRIPS["sniper_rifle"]`.

Generated signatures (`-> ~T` = return type inferred from `return` statements, `# text` = first docstring sentence):

<!-- AUTO:sigs -->
**`engine3d/core.py`** (1042 lines)
```
def v_cross(a, b) -> ~tuple3
def m_mul(a, b) -> ~tuple9
def m_apply(m, v) -> ~tuple3
def rot_x(deg) -> ~tuple9  # +deg tips +y toward +z (a torso leaning forward)
def rot_y(deg) -> ~tuple9  # Yaw
def rot_z(deg) -> ~tuple9  # +deg swings a hanging limb (-y) out toward +x
class Mesh
    def __init__(self, verts=None, faces=None)
    def add(self, other, m=M_IDENT, t=(0.0, 0.0, 0.0))
    def face(self, pts, col, layer=2, double=False, emissive=False)
def box(w, h, d, col, center=(0.0, 0.0, 0.0), cols=None, seg=None, layer=2, emissive=False, skip=())
def prism(profile, depth, col, z0=0.0, cols=None, layer=2, seg=None)
def quad_xz(x0, z0, x1, z1, y, col, layer=0, seg=None, colfn=None, emissive=False)  # Upward-facing ground rectangle
def disc_xz(cx, cz, r, y, col, n=9, layer=1, wobble=None)
class Obj
    def __init__(self, mesh, light, m=M_IDENT, t=(0.0, 0.0, 0.0), tag='')
class Light
    def __init__(self, direction=(-0.45, 0.78, -0.42), ambient=0.42, diffuse=0.62, sky=0.1, tint=(1.0, 0.98, 0.95))
    def shade_char(self, col, n, v)  # Rigged characters
    def shade(self, col, n) -> ~tuple3
class SoftwareRenderer
    def set_sky(self, spec)
    def __init__(self, w, h, fog=(96, 98, 104), fog_start=18.0, fog_end=210.0)
    def resize(self, w, h) -> ~bool
    def set_camera(self, pos, target, fov, roll=0.0)
    def to_cam(self, p) -> ~tuple3
    def project(self, p) -> ~tuple3
    def horizon_y(self)
    def visible_sphere(self, c, r)
    def visible_frustum(self, c, r, cam, right, up, fwd, near, far, tan_h, tan_v) -> ~bool
    def visible_ortho(self, c, r, cam, right, up, fwd, half_w, half_h, far) -> ~bool
    def bake(self, mesh, m=M_IDENT, t=(0.0, 0.0, 0.0), tag='')
    def begin(self)
    def set_texture(self, tex_id, arr) -> None
    def set_extra_textures(self, *entries)
    def add_particles(self, arr)
    def add_decals(self, arr)
    def set_lights(self, lights, cap=64)  # Local lights for this frame
    def set_pools(self, pools, cap=32)  # Lamp pools for this frame
    def add_static(self)
    def add_dynamic(self, wverts, faces, bias=0.0, tint=None, char=False)  # faces
    def set_sun_shadow(self, travel, center, half, k=0.6, col=(0.12, 0.15, 0.32)) -> ~bool
    def add_blob_shadow(self, pos, rx, rz, strength=0.35, layer=None, bias=0.0)  # Soft contact shadow
    def add_sprite(self, pos, draw_fn, layer=2, bias=0.0)  # draw_fn(surface, sx, sy, scale_px_per_m, z)
    def add_humanoid(self, hum, pose, pos, yaw, rifle_on=True, bias=0.0, tint=None, shadow=None)
    def add_line3d(self, a, b, col, width=1, layer=3)
    def flush(self, surface=None, bg=None)
    def flush_split(self, surface, split_depth, mid_fn)
    def flush_near_blur(self, surface, split_depth, blur_fn)
```
**`engine3d/gl.py`** (2195 lines)
```
def gl_available()
def gl_info() -> ~dict
class GLRenderer(SoftwareRenderer)
    def __init__(self, w, h, fog=(96, 98, 104), fog_start=18.0, fog_end=210.0, ps1_snap=False, dither=False)
    def invalidate_static(self)  # Call after editing baked objects' geometry in place
    def resize(self, w, h) -> ~bool
    def set_sky(self, spec)  # Queue GPU sky parameters for the next render pass
    def begin(self)
    def add_static(self)
    def set_extra_textures(self, *entries)
    def set_sun_shadow(self, travel, center, half, k=0.6, col=(0.12, 0.15, 0.32)) -> ~bool  # Real cast shadows for this frame
    def add_dynamic(self, wverts, faces, bias=0.0, tint=None, bounds=None)
    def add_packed(self, arr, bounds=None)
    def add_resident(self, arr, bounds=None)
    def pack(wverts, faces, bias=0.0, tint=None)
    def add_humanoid(self, hum, pose, pos, yaw, rifle_on=True, bias=0.0, tint=None, shadow=None)
    def add_sprite(self, pos, draw_fn, layer=2, bias=0.0)
    def add_blob_shadow(self, pos, rx, rz, strength=0.35, layer=None, bias=0.0)
    def add_line3d(self, a, b, col, width=1, layer=3)
    def add_lines3d(self, segs, layer=4, depth_test=True)
    def flush_to(self, target_surface, *, bg=None, post=None, resolve=True)
    def present_to(self, target_surface, *, post=None)
    def flush_overlay(self, surface, bounds=None, into_fbo=False) -> ~tuple2
    def flush(self, surface=None, bg=None)
    def flush_split(self, surface, split_depth, mid_fn)
    def flush_near_blur(self, surface, split_depth, blur_fn)
    def release(self)
def Renderer(w, h, fog=(96, 98, 104), fog_start=18.0, fog_end=210.0, **kw) -> ~GLRenderer|SoftwareRenderer
```
**`engine3d/rig.py`** (1394 lines)
```
def mouth_flap(t_ms: int, seed: int=0) -> float
def solve_look(eye, target, body_yaw_deg: float) -> ~tuple2
def blend(a, b, t)
def pose_run(phase, lean=16)  # Gait cycle
def pose_drag(phase)
def pose_crawl(phase)
def rifle_mesh(col=(26, 28, 30), scope=False, accent=(60, 62, 58))
def os12_mag_mesh()
def os12_mesh(with_mag=True)  # OS-12 'Tiss' (OTs-12)
def shotgun_pump_mesh()
def shotgun_mesh(with_pump=True)
def cbox(w, h, d, col, center=(0.0, 0.0, 0.0), cols=None, bevel=0.02, skip=(), emissive=False, layer=2)
class Humanoid
    def __init__(self, spec)
    def set_expression(self, name=None, mouth_open=None) -> None  # Switch face expression / talking mouth (P11 step 8)
    def placements(self, pose, rifle_on=True)  # Pose the skeleton without touching vertices
    def ragdoll_nodes(self, pose, pos, yaw) -> ~dict
    def places_from_nodes(self, nodes, floor_y=None, head_yaw=0.0, rifle_m=None) -> ~tuple2
    def pose_world(self, pose, pos, yaw, rifle_on=True) -> ~tuple3  # Skeleton-only posing for GPU skinning (engine3d.gl)
    def build(self, pose, pos, yaw, rifle_on=True, extra=None) -> ~tuple3
def mix(a, b, t)
NEUTRAL keys: spine spine_r twist head_p head_y head_x lsh_p lsh_r lel rsh_p rsh_r rel lsh_y rsh_y lhip_p lhip_r lkn rhip_p rhip_r rkn lank rank body_p body_r lift rifle_p rifle_y
POSES keys: stand ready aim radio talk_turn crouch cover cover_tight kneel kneel_over dive prone dead_back dead_front dead_side slump reach_radio mayday drag carried
EXPRESSIONS keys: neutral smile grin angry stern sad surprised worried closed
SLOTS = ('pelvis', 'torso', 'head', 'face', 'uarm', 'uarm_acc', 'farm', 'thigh', 'shin', 'foot', 'uarm', None, 'farm', 'thigh', 'shin', 'foot', 'rifle', 'chest', 'face2', 'chest2', 'chest3')
```
**`engine3d/ik.py`** (294 lines)
```
def shoulder_world(hum, pose, pos, yaw, side) -> ~tuple3
def solve_arm(hum, pose, pos, yaw, side, target, pole=None)
def solve_leg(hum, pose, pos, yaw, side, target)
def solve_rifle_hold(hum, pose, pos, yaw, target, fore=0.3, pocket=(-0.05, -0.03, 0.05), weld=None, support_pole=(-0.6, -1.0, 0.1), grip_pole=(1.0, -0.5, -0.4), look=T...
def rifle_hold_gaps(hum, pose, pos, yaw, fore=0.3, pocket=(-0.05, -0.03, 0.05), weld=(0.08, 0.01, 0.07))
```
**`engine3d/hold.py`** (346 lines)
```
def body_volumes(hum, pose, pos, yaw)  # -> {name
def push_out(vols, p, margin=0.03)
def arm_clash(hum, pose, pos, yaw, side, margin=0.0)
def solve_arm_safe(hum, pose, pos, yaw, side, target, poles=None, margin=0.02)
def weapon_of(hum)
def hold_frame(hum, pose, pos, yaw, weapon='rifle', mode='aim', aim=None) -> ~tuple3  # -> (pose, origin, basis)
def hold_weapon(hum, pose, pos, yaw, weapon='rifle', mode='aim', aim=None)
def hold_report(hum, pose, pos, yaw, weapon='rifle')
def hold_cached(hum, pose, weapon, mode, aim=None, key=None)  # hold_weapon for per-frame callers
POLES = ((0.8, -1.0, -0.1), (0.6, -1.0, -0.7), (-0.4, -1.0, 0.15), (1.0, -0.2, 0.0))
GRIPS keys: rifle sniper os12 k9 shotgun m7rifle akrifle ak74 lmg sniper_rifle pistol
MODES keys: aim ready port carry one_hand pistol_aim pistol_ready
```
**`engine3d/textures.py`** (164 lines)
```
class Tex(tuple)
    def with_rgb(self, rgb) -> ~Tex
def tex(name, like=None, density=None, tint=False) -> ~Tex  # The colour a face takes to show texture ``name``
def version()  # Bumps whenever a texture is added
def glitter()  # Glitter strength per layer, in layer order
def reflectivity()  # Reflectivity base per layer, in layer order
def stack()
tex names (assets/tex3d): ashlar ballast bone boxcar brick concrete crate m6_palette m7_bark m7_barnboard m7_dirt m7_furrow m7_grass m7_gravel m7_hay m7_leaf m7_plank m7_plaster m7_stone m7_stubble m7_tile m7_tin m7_track metal_rib pavement rust scorch sleeper snow snow_trod steel stucco vault
```
**`cutscenes/m6world3d.py`** (2721 lines)
```
def rend(w=RW, h=RH, hdr=True)
def present(surface, buf, x=0, w=WIDTH)  # Gamma-grade the small buffer before the upscale
def rend_ps2() -> ~tuple2
def present_ps2(surface, buf, x=0, w=WIDTH)
def film_xy(p, x0=0, w=WIDTH, rw=RW) -> ~tuple2
def project_xy(r, p, x0=0, w=WIDTH)
def cam(r, t, eye, tgt, fov, hh=0.0, seed=0, roll=0.0, shk=None)
def add(r, m, bias=0.0)
def drop_renderer_caches()
def pack_memo(r, key)
def pack_memo_end(ok=True)  # Close a memo frame
def pack_memo_ready(r, key)
def pack_memo_replay(r)
def static_scene(r, key) -> ~bool
def static_end(r, ok=True)  # Close a static batch opened by ``static_scene``
def yaw_to(src, dst)
def current_shot()
def speaker()
def talking(who)
def grade(surface, gamma=0.82, vig=0.4)
def finish(surface, seed, tag='', col=(120, 190, 220), t=0, ps2=False)
def guard_spec(kind='rifle') -> ~tuple2
def hum(key, hd=False, wound=0, bloody=False, flags=())  # Humanoid for ``key``
def life_pose(pose, t, amp=1.0, seed=0)
def actor(r, key, pose, pos, yaw, t, seed=0, amp=1.0, rifle_on=False, expression=None, mouth=None, bias=0.0, hd=False, wound=0, bloody=False, shadow=None, flags=())
def air_actor(r, key, pose, pos, yaw, t, seed=0, expression=None, mouth=0.0, tint=None)  # Un-grounded actor (falling/tumbling)
def ease5(t, start, length)
def travel(t, start, duration)  # 0..1 distance
def yaw_mix(a, b, p)
def leg_ik(foot_z, foot_y) -> ~tuple2  # Two-link leg in rig space (hip -> ankle)
def path(points, smooth=0.3)
def walk_stride(length, nominal=0.62)
def walk_span(length, stride) -> ~tuple2  # Gait parameter range
def walk(hum, route, g, stride, speed=1.2, ground=None) -> ~tuple3
def walk_slip(hum, route, stride, speed=1.0, samples=200)
def sit_pose(hum, seat_y, upper=None)  # Seated legs
def ankles(hum, pose, pos, yaw)  # World ankle points of a posed actor -> {"l"
def knees(hum, pose, pos, yaw)  # World knee points (shin origins) -> {"l"
def planted_pos(hum, pose, yaw, mid_xz, y=0.0) -> ~tuple3  # Root that puts the ankle midpoint on ``mid_xz``
def reach(hum, pose, side, target, pos, yaw, pole=None)
def solids(set_key)
def penetration(hum, pose, pos, yaw, boxes, parts=_BODY)
def head_stats(surface, r=None, full=False) -> ~list
def flake_sprite(r, p0, p1, col)  # Queue one flake streak p0 -> p1 as a sprite
def snow3d(r, t, seed=0, n=130, spread=18.0, height=14.0, speed=1.5, col=SNOW, near=0.0, skip=None, depth=False)
def breath(pos, t, seed=0, intensity=0.22)  # Cold-air breath
def night(r, buf, t, top=(5, 8, 15), bot=(18, 26, 42), stars=55, moon=False, sodium=(44, 30, 20), seed=0, star_cut=0.45, gpu=False)
def warm_lamp(r, pos, t, seed=0, radius_m=1.6, col=WARM, intensity=0.9)  # One practical = one core + one halo
def height_at(x, z)  # Ground height of the insertion valley
def terrain(r, t, lights=True)  # Snow ridge above the border
def hills(r, t, lights=True)
def capital(r, t, dz=0.0, dx=0.0)  # Distant skyline
def dark_hills(r)
def border_compound(r, t, warm=1.0)  # The customs post seen from the hills
def crossing_far(r, t, warm=1.0)  # Kim Kim seen from the ridge, north of the compound
def run_x(z)  # River centreline x at ``z``
def run_dx(z)  # dx/dz of the centreline
def run_ddx(z)
def run_height(x, z)  # Valley floor
def run_valley(r, t)  # The frozen river valley
def heli_xform(pos, yaw, bank=0.0, pitch=0.0, scale=1.0)  # Local airframe point -> world
def heli_pilot()
def heli_solids(pos, yaw, bank=0.0, pitch=0.0, scale=1.0)
def helicopter(r, t, pos, yaw=-18.0, rotor_speed=1.0, lit=True, scale=1.0, door=True, bank=0.0, pitch=0.0, blur=1.0, pilot=True) -> ~dict
def boxcar_interior(r, t, lantern=1.0, door_open=1.0, snow=1.0, glow=1.1)  # Interior set
def train_body(r, tx)  # The waiting carriage alone, shifted by ``tx``
def rail_platform(r, t, train=True, snow=1.0, train_offset=0.0)
def window_snow3d(r, t, center, hw, hh, seed=0, n=46)
def terminal_office(r, t, lamp=1.0, radio=True, crt=True, handset=True, voice=0.0) -> ~tuple3
def vasile_office(r, t)  # The empty office
LAST = []
```
**`game/render3d_bridge.py`** (679 lines)
```
def load_mesh_asset(ref: str)
def mesh_for_prim(prim)
def load_texture(tex_id: str)
def push_textures(r, prims) -> None  # Register a set's textures on a software renderer (GL
def dynamic_faces(mesh) -> list
def presets() -> dict  # The ae.lighting3d/1 preset library (Phase 11 step 1)
def set_lighting(set_id: str, blend=None) -> dict
def use_legacy() -> bool
def flicker_at(seed: float, t_ms: float) -> float  # Deterministic bulb flicker 0.15..1.0 (P11 step 10)
def set_prims(set_id: str, params=None) -> list  # Ordered renderer primitives for ``set_id`` (e.g
def build_mesh(prim)
def render_scale_3d() -> float
def render_size_3d(base_w: int=480, base_h: int=270) -> tuple
def quality_3d() -> int
def emit_lights(r, prims) -> None
def shadow_prims(prims) -> list
def emit_shadows(r, prims) -> None
def bake_cast_shadows(pairs, prims) -> None  # ADR-023
def humanoid_meshes(prim, t: int=0) -> ~tuple2
def apply_set(r, prims, *, add, dec, spr, decal_add, fx, t: int=0) -> None
SETS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'content', 'sets')
PRESETS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'content', 'lighting3d')
TEXTURES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'content', 'textures')
MESHES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'content', 'meshes')
```
**`game/scenery3d.py`** (92 lines)
```
def prop(ref, screen=(48, 116, 88))
def display(ref, colour)  # Procedural screen-only mesh
def workstation(pc='pc_zarya', monitor='monitor_crt', live=False)
def workstation_display(pc, monitor, colour)
def medical_supplies()
```
Signature notation: `-> ~T` = return type inferred from the `return` statements (no annotation in source); `# text` = first docstring sentence.
<!-- /AUTO:sigs -->

`_CONTRAST = {"concrete":0.55, "stucco":0.30, "ashlar":0.55}` scales pattern light/dark before tint; `stucco` (fine fbm grain + hairline cracks, monumental plaster) and `ashlar` (staggered coursed stone blocks) are drawn by `tools/tex3d_draw.py` and replace `m7_plaster`/`m7_stone` on the M8 Duty courthouse/city facades AND Retardovici's estate (`mansion_set` shell/hall/terrace/grounds/fountain; `mansion_env` flagstones/road shoulders/cottages/substation/gatehouse) - the farm tiles read as mould blotches at monumental scale.

---

## 3. Game-side packages (non-obvious owners)

- `src/game/art/_pack.py` `Pack(name)`: `get` `variants` `module` `baked_path` `sprite_dir` `blit_layer`; all packs share one `AssetRegistry` (`shared_registry`). `src/game/art/_layers.py`: `render_callback_layer` `state_flags_variant`.
- Art packs (each module exposes `render(variant=0, scale=1)` + `VARIANTS`; world layers also `bake_setup` `runtime_callback`, some `variant_for_state`):
  - `game/art/m1`: `exfil_truck` `molotov_icon` `pickup_icon` `world_static`
  - `game/art/m2`: `nest_bits` `prop_icon` `world_static`
  - `game/art/m3`: `archives_static` `broadcast_static` `camera_body` `cell_details` `cell_door_blown` `cellblock_static` `comms_static` `door_tile` `kitchen` `ko_static` `pickup_icon` `wall_monitor` `weapon_icon`
  - `game/art/m4`: `mag_icon` `world_static`
  - `game/art/m5` (own `__init__` with `get` `registry` `ASSETS` `DECALS`, not `Pack`): `armband bale calendar district_map guard_banner guard_plate hq_locker inspect_art m5_guard mag mag_icon maru plate portrait_frame posters presidential_crest press printworks_sign tram_wreck wall_posters`; helpers `_kit.py`.
  - `src/art/m5/__init__.py` = shim aliasing `game.art.m5` (`from art import m5` still used, e.g. `missions/m6/draw.py`). Edit `game/art/m5`.
- Manifests: `src/game/content/m{1..5}/manifest.json` (asset ids `mN/<module>`). Baked output: `assets/baked/m{1..5}/<name>_<variant>.png` + `.bakeinfo.json`.
- `src/game/timelines.py` (`shots`, `timeline`, `save_timeline`): `game/content/timelines/*.timeline.json` -> legacy shot dicts for `app.CutscenePlayer`. `ACA_TL_SRC=legacy` = in-code tables.
- `src/game/dialogues.py`, `levels.py`: same pattern for `content/dialogue/*.dlg.json`, `content/levels`.
- `src/game/save_adapter.py` (`capture` + restore): engine snapshot of `STATE`; `src/game/render3d_bridge.py`, `input_adapter.py`, `vehicle_fx.py` (`default_vehicle_fx`): boundary adapters (allowed).
- Shared 3D vehicle destruction (`engine.render3d.VehicleDestructionManager` + `game.vehicle_fx.default_vehicle_fx`): one pure-engine system owns vehicle-specific profiles (`car`, `jeep`, `truck`, `gun_truck`, `aa_truck`, `tanker`, `gunship`, `gunship_air`, `tractor`), momentum-inheriting 3D detached parts (`PartBody` with floor bounce & settle), stationary hull hop-and-sag (`hull_transform`), charred/ember interior cores, ground scorch decals, shockwave rings, anchored `fire3d` flames, and delayed secondary cook-offs across `m8/duty/flight3d`, `m8/revenge/chase3d`, `m8/revenge/trap3d`, and `m8/duty/mansion3d`.
- `src/game/topdown3d.py`: 2.5D top-down host (`CAMS`, `View`, `mouse_world`, `put`, `cast_shadows`) for M1-M6 `draw3d`, `missions/walk3d.py` and the MP arena (`ui/arena_view3d.py`). `Cam.res` defaults to the 1000x700 canvas (no upscale; `m6fx3d.present_crisp` is a plain blit when sizes match; arena `RES` too). On GL, `cast_shadows` calls `r.set_sun_shadow` along `SHADOW_DIR` over `SUN_HALF` m round the view focus and sets `r.char_pop = CHAR_POP` (top light + rim on rigs) and `r.tex_scale = TEX_SCALE` (GL `u_uvs` multiplies every world UV: 1/3 = 3x bigger texels, the chunky pixel look of the 3D missions; both reset to neutral in `GLRenderer.begin`); the 2D hull shadows are the software fallback. `missions/m1/draw3d._gait(key, x, y, angle, lean)` is the shared top-down leg pose (phase from ground distance via `_motion`'s 4-slot cache, breathing idle via `m6world3d.life_pose`, stride blended over `engine3d.pose_run`); `_body` (M1-M6) and the M3/M5 `_unarmed` use it.
- `src/missions/m6/draw3d.py` (M6 2.5D for all four top-down stages - customs, no-man's-land, rail, boxcar; `_stage()` folds boxcar into rail so the handoff frame reuses the rail atlas. The post-train yard fight is the separate `yard3d` 3D host): `render_world` -> `_decode` -> `_cast_mask` -> `_shaded_floor` -> `_light`. The CPU per-pixel passes scale with `Cam.res` (1000x700 is 2.4x the 640x448 they were built at), so they work only on `nf`, the flat indices of pixels the GL pass touched (~30% of the frame): `_decode` returns `(nf, lin, other)` with `lin`/`other` per `nf` pixel, `_shaded_floor(buf, floor2, nf, where)` and `_light(..., nf, lin, ...)` take them; bare floor is one `np.take` of the lit crop. All gathers/scatters use packed uint32 1-D arrays (no `(N, 3)` channel views). Output is bit-exact to the full-frame version (in-process A/B on the same buffer).
- 2.5D/3D perf invariants: GPU post uses a BGRX fast readback for M6 `_decode` and raw `upload_bg`; static runs merge once/frame into `_static_runs`; depth f16->u8 uses a 65536-entry LUT (`gl._phys8`). GL `_composite` has a per-point `fn.draw_depth` path (fire/sparks set `phys_occ`), reuses `_comp_buf`/`_bones_buf`, and reads GPU depth only when items need it. All caches are bounded LRUs (never destructive `.clear()`): `_POOLS` (192 entries AND 128 MB), `_FLAMES`/`_POOLS` in `m1/draw3d` (evict oldest 128), `_blob_cache` (96). `m6/draw3d` works only on `nf` (GL-touched pixels), bit-exact to the full frame; `engine/collision/mesh.py` precomputes triangle edges and clips rays to a local AABB.
- Fire system (`cutscenes/fire3d.py`) — one procedural source for all fire: `emit_fire`/`emit_wall_fire` for 3D (`m7world3d.fire`/`wall_fire`, `oil_rig_3d`, `walking_attack3d`, `m8/revenge/trap3d` blasts/truck fires) and 2.5D (`m1/draw3d._fire` with `tilt_25d=True`, called by M1–M6 `draw3d`); `ember_bed_sprite` replaces `_fuel_pool_at` across M1–M6; `emit_smoke`/`smoke_puff_surface` replace the old polygon smoke; `_soft_halo` is reused by M6's `_m6_fire_grad`. Flames carry `phys_occ=True`/`draw_depth` so `GLRenderer._composite` does per-pixel physical-depth occlusion instead of the light-anchor kill; `grade3d.apply` handles the new `("fire", pos, col, rad, k)` tuple (warm amber spill into the lightmap, cream core, two bloom passes) so multiply-grading no longer crushes fire, and M6 `_light` bakes warm fire spill directly. M4/M5 burning-car/tram flashes also emit `fire` grade lights.
- GPU pipeline invariants: `GLRenderer` MRT FBO (RGBA16F colour + `f_aux` view-normal/material + `f_pdepth` metres); `gl_sprites.SkyPass`/`SpriteBatch` + `gl_post.PostPipeline` -> ONE readback, hosts use `flush_to`/`present_to`, software keeps `flush`. `m6world3d.rend(w, h, hdr=...)` scopes HDR per call: M1/M5 True, M2/M3/M4/M6/walk3d/arena False (M6 also clears `dither`/`ps1_snap`) - leaking HDR corrupts `K_TOP..K_PTOP` and stops M6 `_decode()` swapping in wall/roof/container textures. GPU skies need `buf is r.surface`; depth clear uses `depth_func="1"` (fallback `">="`); `_run_bloom` MUST sample the previous level's result, never its own `ta` (the pink Print Works bug).
- GPU bloom chain (`engine3d/gl_post.py:_run_bloom`): the bright pass fills level 0's `ta`; each level's horizontal blur MUST sample the previous level's result (`src_tex`), never that level's own `ta` (the vertical-blur write target, uninitialised on the first frame). Reading `ta` for levels >= 1 leaks whatever GPU memory the f2 texture was allocated over — after an m5x 3D cutscene that is magenta frame data, so M5 Print Works rendered as a pink rainbow. Level 0 happened to work because `ta == src_tex`. Only hosts that actually apply bloom (print works; quarter forces `bloom=0.0` when CPU items exist) were affected.
- GPU/wetness per-frame state: `GLRenderer.begin()` resets `char_pop`, `tex_scale`, `marble_refl` and `height_fog` to neutral; `resize` uses `self.ctx.NEAREST`; frustum culling opts out with `r.frustum_cull=False`. SSAO/SSR/height-fog live in `gl_post._ATMOS_FRAG`, 64 tiled lights + 2 spot-shadow maps in `_upload_lights`/`_spot_pass`; M8 Mansion sets `r.marble_refl` indoors (0.34) only.
- Animation/collision invariants: `engine/anim/{springs,rig3d}.py` + `engine/collision/{nav,boxes,mesh,physics}.py` are pure (no pygame/game imports, boundary E3). `locomotion_pose` is velocity-coupled with a positive sprint-only `lift` (walks stay planted); `_leg_swing` folds the knee on the thigh's forward angular velocity; 2.5D keeps `pose_run` via `_motion`'s 4-slot `[x, y, phase, speed]` cache (no `STATE.dt`). `MultiFloorNav` caches string-pulled waypoints, static neighbours and a `_blocked` bytearray that MUST invalidate together; `slide_capsule` handles steps/ledges; ragdoll ground friction applies ONCE per step, not per constraint iteration.
- Death/ragdoll invariants: `cutscenes/death3d.Fall` seeds `engine.collision.physics.RagdollBody` via `Humanoid.ragdoll_nodes`/`places_from_nodes` (15 world nodes, no auto-grounding shift), drives hit-context reactions with active muscle tone, and drops the rifle as a rigid body; all four 3D worlds pass `world.box_world` + `ragdoll_boxes()`. `physics.RagdollBody` caps node velocity, settles on post-solver displacement and latches rest only when grounded and slow. The four scenes call `Fall(...)` unchanged - a change there reaches every 3D death.
- M8 Mansion nav/fragment invariants: `mansion_world.nav()` is one `MultiFloorNav` synced to doors/cars/helicopter; `mansion_brain` throttles A* behind `nav_at` and skips nav across locked doors. `_LOS_STATIC_BW` rejects static blockers in `los3d()`; short `ray_hit()` probes use `_STATIC_BW.ray()`. **Known edge case (kept verbatim):** `BoxWorld.ray()` returns the first hit, so a ray starting inside a box drops the t=0 hit - a short downward probe can return a farther hit than the legacy scan; `los3d()` itself is equivalent.
- 3D culling invariants: `r.frustum_cull=False` opts out; GL splits baked objects >32 m/48 faces into 32 m XZ slices and culls per pass, keeps resident chunks in a 128-entry LRU, and `pack_memo_end` splits memos into 24 m chunks. `GLRenderer.add_resident()`'s LRU `live` set MUST include the just-added key (`| {key}`) or a frame queueing >128 chunks evicts the VAO it just created and crashes.
- Cast look: owner `engine/anim/figure_kit.py` `SPECS`. `cutscenes/figure_kit.py` is a deprecated re-export (A-006). 3D cast: `cutscenes/cast3d.py` `spec3d` `humanoid3d` `weapon_asset` `rifle_asset` `ak74_asset` `third_person_rifle`.
- Core legacy: `core/state.py` `STATE` (weapon attrs live here), `core/save_system.py`, `core/mission_meta.py` (`meta_for`, `fail_text`), `core/cutscene_registry.py` (`register_scene_renderer`, `scene_renderer`), `core/dev_jumps.py` `DEV_JUMPS`, `core/artpack.py` (sprite-sheet access).
- 2D HUD shared: `ui/hud.py` (`THEME`, `MiniMap`, `draw_objective_panel`, `draw_pinned_radio`, `draw_combat_reticle`), `entities/art_cache.py` `get_panel_bg` (panel background passed to every widget).
- Tactical HUD shared (M1–M6): `ui/tactical_hud.py` is the single source of truth for `HUD_MARGIN=18`, `PANEL_GAP=6`, `TACTICAL_THEME` (an `engine.ui.Theme` with `extra["tactical_hud"]=True`), `draw_tactical_corners`, `tactical_panel_bg` (cached dark panel) and `place_minimap` (18px top-right). M1–M5 gameplay HUDs import it lazily inside their draw functions; `m6/hud_ui.py` re-exports `HUD_MARGIN/PANEL_GAP/M6_THEME/m6_panel_bg` from it. `Theme.panel()` draws the corner brackets + top catchlight only when `theme.extra["tactical_hud"]` is set (default themes unchanged). `game/topdown3d.py` `add_player_rim` is the shared cool-rim / optional GL spot helper used by `walk3d`, the arena and M1–M5 `draw3d`. The shared `missions/m1/grade3d.py` grade now also handles `"glow"` (optical bloom), `"reflect"` (wet-ripple streak) and `"cone"` (6-tuple directional flashlight) light tuples for all 2.5D scenes.
- Shared 2.5D rain (`game/rain3d.py`): world-locked 3D drop lattice around `View.tgt` for Walk/M1/M4/M5 — NOT `cutscenes/m6fx3d.rain3d`, which is the separate 3D-film helper. `emit(r, v, tm, lights, outdoor_sky, outdoor_ground, roof_occlude, puddle_fn, mist_lamps, intensity, seed)` hashes world cells into three deterministic depth bands (no camera swim), tints streaks from nearby point/spot lights (lamps, fires, headlights, Biribel's torch, M5 searchlight) and batches tapered dual-segment streaks + ground ripples/splash crowns/puddle double-rings into two GL `add_lines3d` calls on `RAIN_LAYER=5` / `GROUND_LAYER=1` (hardware-depth-occluded); software falls back to RGB `add_line3d`. Quality comes from `game.render3d_bridge.quality_3d()` (0 disables) and `reduced_motion` locks the wind. Each host supplies sightline/roof/ground predicates, so M1's warehouse interior (rows 10..29) and M4/M5 buildings stay dry. `step_rain_drops(drops, speed_mul, rng)` advances legacy drops with the same RNG order as `core.config.draw_rain`; the 2.5D submit paths call it (M1 with its seeded `_m1_rain_rng`) so replay hashes stay identical, and M1's drop-off films skip their 2D pass when a 3D take drew (`_dropoff_post(..., rain=not drawn)`).

## 4. Cross-module call chains & shared ownership

### 4.1 2D HUD weapon panel (M3-M6)
```
missions/m3/systems.py  _hud_weapon_panel.draw(..., mag_icon=_draw_m3_mag_icon, panel_h=92)   (game.art.m3)
missions/m4/draw.py     draw(WeaponInfo.from_state(STATE), mag_icon=_draw_m4_mag_icon)        -> _m4art.get("mag_icon", ...)  game/art/m4/mag_icon.py
missions/m5/draw.py     draw(WeaponInfo.from_state(STATE), mag_icon=_draw_m5_mag_icon)        -> _m5art("mag_icon", ...)      game/art/m5/mag_icon.py
missions/m6/draw.py     _draw_hud -> draw(WeaponInfo.from_state(STATE), mag_icon=_panel_mag_icon)
  all -> engine/ui/std/weapon_panel.py draw: layout, labels via T("hud.mags"/"hud.shells"/"hud.reloading"), reload bar from RELOAD_MS
```
- Same files also call `health_bar.draw` and `hostiles.draw`. M1/M2 HUD (`missions/m1/draw.py`, `m2/draw.py`): `bottle_hud`, `crosshair`, `health_bar` from `engine.ui`; no weapon panel.
- Tactical skin call chain (M1–M6): every gameplay HUD passes `TACTICAL_THEME` from `ui/tactical_hud.py` to `engine.ui.std` widgets (`health_bar`, `weapon_panel`, `hostiles`, `objective_banner`, `bottle_hud`) and draws backdrops with `tactical_panel_bg`; `m1/draw.py` also routes its HP/bottle panel factories through it. `place_minimap` re-themes and re-anchors the 18px top-right minimap in M1/M2/M3/M4/M5. Changing the margins, bracket length/thickness or panel fill there updates all six missions at once.
- `WeaponInfo.from_state` knows only `k9_smg`, `os12`, else pistol (`SIDEARM`). Shotgun info is built explicitly by the 3D HUDs.

### 4.2 3D HUDs (M6 yard/train, M7 raid, M8 trap/kill/chase, M8 Duty mansion/flight/ridge)
```
missions/m7/raid_hud.py draw          -> U.weapon(..., cw="fallow12", label="FALLOW 12", caliber="12GA", kind="shell", reload_ms=132)
missions/m8/duty/mansion_hud.py draw  -> U.weapon(...) (two calls: shotgun / rifle) + U.objective/hostiles/prompt/reticle, RH.hold_bar, H.marker/crosshair/damage_arcs
missions/m8/revenge/trap_hud.py draw  -> U.weapon(... fallow12 ...) or (cw="os12", label="OS-12", caliber="5.56X45", kind="stick", reload_ms=90)
missions/m6/yard3d.py  YardScene._draw_hud()     -> U.weapon(... K-9 defaults ...)
missions/m6/train3d.py TrainScene._draw_vitals() -> U.weapon(...)
  U = missions/m6/yard_hud.py weapon() -> builds WeaponInfo(reserve=, reload_prog=) -> engine/ui/std/weapon_panel.draw(mag_icon=_icon)
     _icon -> (lazy) missions/m6/draw.py _panel_mag_icon(..., reload_prog, incoming)
         kind "shell" -> _draw_fallow_icon (procedural, m6/draw.py)
         kind "stick" -> art.m5.get("mag_icon", 0 + state) -> game/art/m5/mag_icon.py (baked assets/baked/m5/mag_icon_*.png) + witness-hole overlay
         else / art missing -> _draw_mag_icon (procedural, centred)
  H = missions/m6/hud3d.py: _text _bar crosshair damage_arcs marker minimap ammo vitals diamond (3D-only bits)
```
- `yard_hud` also owns `objective` `hostiles` `minimap`/`build_minimap` `reticle` `prompt` `OBJECTIVE_COL`; all reuse `ui/hud.py` + `engine.ui`.
- `trap_hud` reuses `missions/m7/raid_hud.py` (`SPEAKER`, `bodi_clock`). `chase3d.py` uses `U.objective/hostiles/prompt/reticle` + `H.crosshair/damage_arcs` but draws its own `"LMG %d / %d"` text (no weapon panel). `kill3d.py` uses only `U.reticle`.
- Duty: `flight3d.py` and `ridge3d.py` draw their own panels from `H._text/_bar/crosshair/damage_arcs/objective` + `RH.callouts` (no weapon panel).
- Editing `_panel_mag_icon` or `yard_hud.weapon` changes M6 2D, M6 yard, M6 train, M7 raid, M8 trap and M8 mansion at once.

### 4.3 Cross-mission 3D scene reuse
- `missions/m8/revenge/trap3d.py` `TrapScene` borrows methods from `missions/m7/raid3d.py` `RaidScene` by class-attribute assignment: `_grab set_paused _snd say tracer hp hp_max _aim_ray _player_pose _guard_pose _ally_pose _cover_pose _project`, `_ground_move = RaidScene._move`, `_update_wall_k = RaidScene._update_wall_k`, and calls `RaidScene.handle_event(self, event)`. `TrapScene` overrides `_wall_probe_dist` to add `self.world.props` (`RW._ray_box`) to the raid's world-ray probe. `_draw_fx` is NOT borrowed: `TrapScene._draw_fx` draws its own layer-2 tracer ribbons (the raid's layer-3 lines painted over Biribel in OTS cameras). It imports `MAG, RESERVE0, RELOAD_S` from raid3d and uses `raid_world` (`truck`, `put`, `_ray_box`). `on_truck_crash` delegates the truck blast/fireball/puffs exclusively to `veh_fx` (`VehicleDestructionManager`, no longer adding its own `blasts` entry). Renaming/changing a `RaidScene` method or attribute it touches breaks M8.
- Shared 3D vehicle explosions (`engine/render3d/vehicle_destruction.py` + `blast_sprites.py`, used by M8 `trap3d`/`chase3d`/`flight3d`/`mansion3d`): `VehicleDestructionManager.__init__` calls `blast_sprites.prewarm()`; `draw()` replaces the old `fire3d` flame-lobe fireball and `add_line3d` shockwave ring with `blast_sprites.fireball_sprite` / `flash_sprite` / `ground_flash_sprite` (`phys_occ=True`), delays `fire_mounts` ramp-up past the fireball, emits a tan dust skirt before dark column smoke, and tones down hot debris meshes (`ember` mix 0.28).
- `trap3d` also uses `chase3d` (`_f_hash`, `_f_unit`) and `set3d` (`MAP_X0..`, `tile`, `_glyph`, `CATWALK_Z`, `DECK_X`).
- M8 Duty borrows the same way. `duty/mansion3d.py` `MansionScene` takes `RaidScene` `_grab set_paused _snd say tracer hp hp_max _aim_ray _player_pose _guard_pose _project`, `_ground_move = RaidScene._move`, `_wall_probe_dist = RaidScene._wall_probe_dist` and `_update_wall_k = RaidScene._update_wall_k`; it imports `raid_world`, `chase3d`, `chase_set` and `trap3d`. `flight3d.py` takes `set_paused _grab _snd say` plus `_draw_fx = TrapScene._draw_fx`; `ridge3d.py` takes `set_paused _grab _snd say`. `mansion_brain.py` builds on `m7/raid_brain`; `mansion_world.py` on `raid_world` + `revenge/trap_world`. So a `RaidScene` change now reaches the raid, the trap and three Duty scenes, and a `TrapScene._draw_fx` change reaches the flight.
- Maru's gunship is shared runtime GLB geometry, not a baked mesh: `chase_set.maru_gunship_parts()` caches `(fuselage, tail_boom, main_rotor, tail_rotor, info)` from `assets/3D/maru_gunship.glb`, split via `_load_glb(path, return_paths=True)` on the root node name (`heli_fuselage`/`heli_tail_boom`/`main_rotor`/`tail_rotor`); `chase_set.put_maru_gunship(..., tail_on=, main_on=, burned=)` submits it with optional severed boom/rotor and charred variants. the films' `_gunship` still reads `info["floor_y"]=0.574`, `pintle_top`, `pilot_seat`, `roof_beacon` and passes `-hroll` because `CS._xf`/`_rot_rt` use `rot_z(+roll)` while `FX.heli_matrix` uses `rot_z(-roll)`; the **first-person** `flight_fx.gunner_eye`/`draw_cabin_and_gun` now read the GLB too, through `chase_set.maru_gunship_fpv_parts()` (the sightline-clipped fuselage, same real boom/rotors) submitted with `put_maru_gunship(..., fpv=True)` - see the 2026-11-21 FPV-GLB bullet in §7. `FlightScene._warm()` prewarms `CS.maru_gunship_fpv_parts()`; the duty films' `_gunship` uses the same submit with `tail_on=False` for the spin/crash and `main_on=False` for the wreck. The procedural `flight_fx.cabin_mesh`/`rotor_mesh` remain the missing-asset fallback only.
- Wall-tuck / revive / Duty live contracts: all four walkable 3D fights probe `RaidScene._wall_probe_dist()` (two shoulder-height rays) and gate fire at `wall_k > 0.65`; `RaidScene._wall_down_hold`/`apply_wall_down` tuck the gun near cover (Yard uses `_gun_frame` instead). `cutscenes/revive3d.py` (`REV`) owns `scene.hold` only while a revive is active, so scene-owned holds (M7 beam lift, M8 ladder climb) survive. `mansion_brain.in_security_room()` is the single interior-bounds test shared by Andrei's intro gate and `mansion3d._fire`'s `can_hit_andrei`; `mansion_world` shares `MultiFloorNav` + `slide_capsule` with the other 3D worlds. Ally aim tracking is eased via `_aim_track` in raid/trap/mansion brains (fire needs `err < 14 deg` and `ALLY_RAISE`).
- M8 Duty set/portrait invariants: `duty/mansion_props.py` owns the cached door/furniture meshes; `president_portrait(w, h, paint)` bakes a flat 2D `figure_kit.draw_character("president", ...)` state portrait at the TRUE w/h aspect (`pw x 96`) into a gilt frame, and its canvas quads MUST wind for a `-Z` front face (with `double=False`, a `+Z` normal is 100% backface-culled by both backends). `mansion_set._portrait()` adds it with `rot_y(0)` for `face=-1`; the two Grand Hall back-wall portraits sit at `x=+/-4.1` on the piers clear of `STAIR_X=3.0`. The study `[E]` kick opens hinged leaves over `KICK_DUR` (`study_open_u` feeds `draw_dynamic_props`) - never an instant open.
- `duty/mansion_set.py` is Retardovici's estate, reused from `revenge/epilogue3d` (funeral house) + `cutscenes/m7world3d` + `game/scenery3d`. Hall marble (checker floor, stair treads) is tinted `concrete` (`textures.tex(..., tint=True)`), not `m7_stone` cobbles, which crawled at grazing angles. `_portrait` only builds for +z/-z walls; the hall side-wall portraits are built facing +z and turned with `rot_y(-90*s)`. Consumers: `mansion3d`, `mansion_world`, `mansion_brain`, `mansion_hud`, `flight3d` and `cutscenes/m8dutyfilms.py`. Props `ammo_crate`/`moneystack` (`content/meshes/`, from `tools/ae_import_duty_props.py`) load here; `tactical_lmg` loads in `m8dutyfilms`. All 7 `CRATE_SPOTS` are dynamic: `mansion_set._crate_parts()` splits `ammo_crate` into a hollowed base + back-hinged lid (battens/latches) + loot contents, `crate_lid_angle(open_u)` gives the two-stage lid physics (latch pop -> 106 deg swing -> 100 deg settle), and `draw_dynamic_props(crates=[(open_u, loot_u), ...])` draws them per frame (`loot_u < 0` hides loot; closed crates get a pulse glow, open trays a reveal glow). `mansion3d` feeds `crate_anims`/`crates_taken`, pops latch sparks + `pickup` at 0.12 s, and `crate_act` drives a torso-twist + `engine3d.hold.solve_arm_safe` left-hand IK reach (lip -> tray -> chest) cancelled by fire/aim/sprint/reload/swap or 2.6 m of drift.
- M8 Duty Grand Hall staircase (`mansion_set._interior_hall`): `_sloped_wedge(x0,x1,z0,z1,y_bot,y_top0,y_top1,col,layer=2)` builds an axis-aligned 6-quad `Mesh` with a sloped top (winding: left face -X, right +X, top +Y, bottom -Y, z0 face -Z, z1 face +Z). The 22 treads (z 18..26, y `GF`..`FF`) sit on one full-width marble_b wedge and are separate riser (marble_b) + 0.05 m tread (marble_a) boxes instead of full-height zebra blocks; the carpet is a continuous riser+tread red runner with 0.30 m gold side borders at x=+/-1.75. Each side gets a second sloped cheek wedge under the balusters at x=+/-`STAIR_X`..+/-`STAIR_X+0.36` (matching `mansion_world`'s solid colliders), a TRIM stringer cap, 15 intermediate balusters (k=1..15 of 16), and a GOLD rail at `mid_y+0.90` (was +0.95) so it meets the upper landing `_balustrade` rail at `FF+0.90`; stone+GOLD newel posts anchor both the bottom (`STAIR_Z0`) and the top (`STAIR_Z1=26.0`, previously missing).
- M8 Duty Grand Hall staircase hitboxes (`mansion_world._static`, `ray_hit`, `los3d`): the STATIC side used to be one flat `GF..FF+1.0` (0.8..6.2 m) box per side from z 18..26 - an invisible wall above the sloped rail that blocked bullets, LOS, the camera boom and `_wall_probe_dist` (`wall_k`). It is now 16 sloped cheek boxes per side (`GF..yb+0.14`, tracking the rail rise), 16 sloped handrail boxes (`ya+0.82..yb+0.97`), 15 individual balusters at segment starts (`k>0`, x `cx+/-0.07`, y `ya+0.06..ya+0.90`) so shots pass between them, and bottom/top newel posts matching `mansion_set` (`GF..GF+1.35` / `FF..FF+1.29`). Walking is untouched: `_STATIC_BW` and `FLOORS`' smooth ramp (`surface_y`, `slide_capsule`, `STEP=0.6`) still own traversal - the step boxes exist only for rays. `_STAIR_RAY_BOXES` = 22 boxes ([-STAIR_X,+STAIR_X] x [18,26], y `GF..GF+(i+1)*dy`) feed `_STAIR_RAY_BW` for `segment_blocked` in both `los3d` branches and `_stair_ray_hit(o,d,best)` (AABB-prefiltered, `_ray_box` per box) in both `ray_hit` branches. `_stair_ray_hit` is defined before `_ray_box` but resolved at call time (fine).
- M8 Duty Last Flight + Liftoff/Crash overhaul (2026-11-21): new `duty/flight_set.py` bakes the 4-zone night aerial chase corridor (`z=-160..4600 m`: Curfew Boulevard, M4 Broadcast Plaza + 88 m tower, Route 12 Highway + toll gantry, Northern Ridge pines) with `corridor_x`/`corridor_yaw`/`surface_y`/`roof_spots`/`draw_corridor_fx`; `flight_fx.py` adds `fpv_gunship_mesh()` (sightline-clean open bay), dark gunmetal `tactical_lmg_mesh`, `_gunner_hands_mesh`, 3D steel pintle bars, and `draw_vip_helicopter()`; `flight3d.py` uses `FS` for cp 1..4 at `HELI_V=34.0`, exports `START_HPOS/START_HYAW/START_HPITCH/START_HROLL/START_AIM_YAW/START_AIM_PITCH` for `liftoff_maru` match-cut, physical decoy flare homing, searchlight glare, 360-deg threat compass HUD, and Ucilev front-arc boss duel. `m8duty_sets.py` seals `crash_forest` with a 3rd pine ring + berm; `m8dutyfilms.py` moves nav lights to tail tips, reframes `liftoff_study`/`liftoff_window`/`liftoff_maru` and `crash_spin`/`crash_black` (2200 ms)/`crash_fire`/`crash_better`; `m8_audio.py` adds `m8_flare`/`m8_klaxon`.
- M8 Duty Capital Square / Forest crash + Ridge overhaul (2026-11-20): new `cutscenes/m8duty_sets.py` (341 lines) caches static Meshes - `courthouse_square()` (160x160 m paved square, boulevard, ministries, 6-column Palace of Justice on `E.FUNERAL` at (150,0,600)), `courthouse_lights()`, `crash_forest(center)` (82 dark spruces in two rings r=7.6..24.5 m + 36 low evergreen shrubs; slimmer 7-tier `_pine_tree` with `m7_bark`/`m7_leaf` textures, clear wreck/camera wedges and a dense outer skirt that blocks horizon leaks, snapped rotor blades lying flat, a short grounded shin strut, dark needle floor + torn earth; the old 6-tier khaki pyramids let bright grass and the road show through), `ridge_forest(pad, eye)` (42 pines + crags, sightline kept clear). `E.FUNERAL` is a 2-tuple `(x, z)`; this module normalises it to 3-tuple `CH = (E.FUNERAL[0], 0.0, E.FUNERAL[1])` and every unpack uses `fx, fz = CH[0], CH[2]`. `cutscenes/m8dutyfilms.py` (718 lines): crash split into `crash_fire`/`crash_promise`/`crash_better` (shared `_crash_set` sets a dark `Light(ambient=0.11, diffuse=0.18, sky=0.08)`; the wreck is the shared `maru_gunship.glb` with boom + rotor removed, `crash_spin` strips only the boom; `_crash_actors` now hands off the baked sniper rifle instead of OS-12: `O_start`/`R_start` lock to Maru's actual rhand while he leans to extend it, Biribel leans in so his right hand reaches the pistol grip (<= `ARM_REACH` = 0.58 m), and during `pull_u` the world-space `_draw_sniper_world` interpolates straight to `b_final`'s `pose_world()` (`O_end`/`R_end`) pinned to Biribel's live rhand and fore, handing off seamlessly to `hold_cached(..., "ready")` at `handoff_u >= 1.0` (no mid-air lift/snap); Maru faces 225° on the mossy log, Biribel kneels SE at 48°, `crash_fire` uses a 3/4 open-side cam at fov 50 so neither blocks the other, `crash_promise` a reverse front-3/4 at fov 44 with tgt_y 0.90 and headroom, `crash_better` a reverse push onto Maru's face at fov 40); `_HULL_CRASH_AT` is `(CRASH_AT[0]+2.60, 0, CRASH_AT[2]+5.60)` and `crash_forest`'s pine exclusion box follows it; `crash_better` now aims at Maru's live `pose_world()[1]['head']` (body_p/-46, head_p/-16, head_y/-18) instead of a fixed point, and `crash_promise` uses a flatter, lower eye; `_crash_actors` returns its Maru pose; a full 16-camera framing pass pulled the approach/liftoff/epilogue cams inside fog_start=36 with every subject projected inside x 0.20..0.84, y 0.14..0.88), epilogue `inauguration`/`vasile_speech`/`crowd`/`eyes`/`biribel_vo`/`title_card` all share `_crowd` (42 mixed civilians, crutches IK); `liftoff_maru` adds a steel pintle stanchion and smoother run/leap gait. `meta.M8_SCENES` gains `m8d_crash_promise`/`m8d_crash_better`; timeline `m8.d_crash` uses them. `duty/ridge3d.py` (564 lines) drops `raid_hud` and uses `ui.speechbox.draw_caption` via `_set_caption` (typewriter + pauses), `_letterbox`, `body_hit`/`shot` SFX, and `audio.fade_out_music(40)` on the presidential kill; `flow.music_tick` returns early while `phase == "pres_down"` so only wind remains.
- M8 Duty asset/framing pass (2026-11-21; **supersedes the camera/handoff numbers in the two bullets below**): both Last Flight and the Liftoff/Crash films now submit `maru_gunship.glb` through `CS.put_maru_gunship` (see §4.3); `flight_fx.gunner_eye` sits at `floor_y+0.92` and leans onto the forward doorway threshold via `lx = 1.04*tanh(3.2*sin(rr))`, `lz = 0.40+cos(rr)*0.24` (the old `+0.16` mullion offset is gone), `draw_cabin_and_gun` takes `hpitch/hroll` and passes `-hroll` for `CS._xf` polarity, and the LMG pintle starts at `(0,1.26,0)`. Liftoff: `liftoff_study` heli `(hx+0.6u, hy+1.9+0.95u, hz+2.2+1.8u)` with tgt `(bx+0.4, hy+1.9+0.25*min(1,0.25u), bz+1.2)`, eye dir `(0.35,0.06,0.93)` / vspan 4.4 / fov 62; `liftoff_window` is now a 3/4 front-port climbing shot: eye `(-6.2+0.35u,0.78,3.3-0.25u)` -> tgt `(-0.24,1.24,0.58)` at fov 46 plus a warm cabin dome light; `_vip_open_body` clips port-wall triangles to a recessed doorway (`z -0.08..1.42`, `y 0.56..2.16`) with `_clip_poly_plane`/`_subtract_door_rect` (no centroid-drop hull wedges across the hole), seals a dark interior box behind it, adds a rail-mounted slid-aft white door panel with a recessed window and flush trim, and Retardovici squats at local `(-0.44,0.55,0.68)` via `_vip_pose()` (cached deep squat verified against `Humanoid.build` vertices: min_y 0.550 / max_y 1.913) below the roof eave (the old cut to `y=2.45` tore the roof and leaked sky); `liftoff_maru` hovers cleanly OUTSIDE the east rail (`TERRACE` x=+9.0, z 36..52) at `(12.4,hy+0.25,hz-0.5)` from `(18.0,hy+1.4,hz+3.5)`, `gyaw=205-40u-10climb`, jump door local `(0.98,0.58,0.28)` at yaw 165 (starboard door faces Biribel), run to `x=8.1` with a 1.50 m arc, `p_in` through `heli_matrix`, cabin whip `(-0.55,1.72,-0.45)` -> `(1.40,1.35,3.40)`, LMG at `pintle_top[1]+0.04` with `gpitch/-groll`. Last Flight Route 12 sightlines: `_heli_pos` road x is `road_x(z)-8.5+4.5*sin(rt*0.22)`, `_heli_yaw = road_yaw-28` (port crab) while `mount_yaw` stays `road_yaw`, air streaks use `flow_yaw=road_yaw` not body yaw; `_rocket_plume_mesh` length/radius 1.28..1.76 / 0.13 and tail/nose glows are larger (max_px 48/20, intensity 1.85/1.15), smoke puffs `0.34+1.65*sqrt(u)`. Crash: `crash_spin` drops only the tail boom and burns at `tail_root = hpos + hmat*(0,1.80,-1.35)`; the grounded wreck keeps fuselage only and both fires are `hmat`-placed. `_crash_actors` takes `body_p/head_p/head_y`, lowers Maru's right-hand target (`max(0.56, sh.y+0.06)`), uses `R_start=rot_y(118)*rot_x(-8)` with grip offset `fore[2]*0.72`, `grab_u` from 0.10, `l_local` from `fore[2]*0.45`, and eases `O_draw` from `O_cur` to the live rhand over the first 0.35 of `pull_u`; `crash_better` targets Maru's live head joint (vspan 0.66, fov 36) and `crash_promise` uses eye dir `(-0.86,-0.04,-0.35)` at vspan `1.28-0.10u`; `_fire_lights` are dimmer (11.5 m / 5.5 m ranges).
- M8 Duty LMG ADS pass (2026-11-21; **supersedes the `flight_fx`/`flight3d` ADS mount numbers above**): `flight_fx.tactical_lmg_mesh()` strips the solid rear-sight plate faces (`z ~ -0.05`) from `tactical_lmg`, restores the center front sight post with a pale-tritium tip (`y=0.137, z=0.545`), and mounts an open-window reflex optic (`SIGHT_Y=0.160, OPTIC_Z=0.045`) on the top rail while leaving `tactical_lmg.mesh.json` and `m8dutyfilms.py` untouched. `flight_fx.lmg_xform()` is the single shared gun-mount helper returning `(basis, at, tip, ads_k)`: `fwd_off 0.78->0.49`, `rg_off 0.225->0.0`, `up_off -0.255->-SIGHT_Y`, `toe_yaw -5->0`, `toe_pitch 4.5->0`, `cant 3.5->0`, with damped ADS kick (`kick_p * (1-0.62*ads_k)`, `kick_z * (1-0.35*ads_k)`). `draw_cabin_and_gun()` projects a cached pixel-exact `_reticle_surface` sprite at `(0, SIGHT_Y, OPTIC_Z)` for `ads_k > 0.30` and tones down ADS muzzle flash; `gunner_eye()` reduces rotor vibration `1-0.78*ads_k`. `flight3d.py` uses `ADS_UP=12.0`/`ADS_DOWN=8.0` and eased `FX._ease(self.ads)` consistently across FOV (`62->38`), mouse sensitivity (`0.105->0.052`), spread (`0.34->0.10` + `0.56->0.22*heat`), shake, `_hud()` crosshair (`lines=(ads_k < 0.45)`, keeping hit markers; hint `RMB ADS`), and `_fire()` spawns tracers from `lmg_xform(...)[2]` (`BORE_LOCAL`).
- M8 Duty Liftoff cinematic overhaul (2026-11-21; **supersedes the Liftoff numbers in the bullets below**): `mansion_set.frame(..., roll=0.0)` accepts optional camera roll; `m8_audio.FILM["m8d_liftoff_study"]` now plays `("flight", "f_heli")` so rotors/score run unbroken from helipad into Last Flight. `cutscenes/m8dutyfilms.py`: shared `_handheld` (gated on `SETTINGS.reduced_motion`), `_rotor_wash`, `_air_streaks`, `_heli_nav_lights` (aft of doorway + nose searchlight haze cone), `_gunship_lights`. `_vip_open_body` upgrades the cabin interior with dark mahogany/brass panelling, burgundy leather VIP bench + backrest, vertical steel aft-jamb grab-rail, overhead warm sconce and forward cockpit avionics; `_vip_base_pose`/`_vip_pose(t)` seat Retardovici on the bench (`feet (-0.28,0.55,0.62)`, verified `max_y <= 2.01 < 2.14` lintel) with left hand IK-locked to the grab-rail (`solve_arm_safe`) and animated right-arm gestures (`grin` -> `angry`), plus a cockpit pilot in `_draw_vip_open`. `liftoff_study`: physical `locomotion_pose` sprint + smooth blend to upward `hold_weapon(..., aim=pos)` tracking, 3-round OS-12 burst (`2350/2520/2690 ms`) with muzzle flash, tracers and skid ricochet sparks, Bodi emerging behind Biribel, low-angle camera keeping both Biribel and full VIP chopper in frame. `liftoff_window`: elevated 3/4-port aerial camera looking slightly down past the doorway so lit estate/city recede below, moody controlled cabin key + moonlight rim + strobe spill. `liftoff_maru`: flare-in hover with nose spotlight + Bodi/Alex on terrace, Biribel `locomotion_pose` sprint along `z=hz-1.10` + athletic balustrade vault (`arc=1.24`, `t=2350..3350`), then unobstructed whip (`whip_u` settles by `4330 ms`) directly into exact `FlightScene` cp=0 `gunner_eye` (`hpos=(17.53,9.5,43.95)`, `gyaw=116`, `gpitch=-3`, `groll=8`, `fov=62`, `aim 206/-14`) behind `FX.tactical_lmg_mesh` + articulated pintle arm for a seamless `cut_to_play` match cut. `m8.d_liftoff.timeline.json` syncs sprint steps, 3-shot burst + ricochet, vault cloth, cabin landing thud and `rifle_handle`; `tools/m8_duty_film_shots.py` uses timeline durations `(4000, 4600, 4600)`.
- M8 Duty Shot 1-3 screenshot pass (2026-11-21; **supersedes the camera/mount numbers in the two bullets above**): `m8dutyfilms._vip_open_body` clips every port-wall GLB triangle against `z -0.08..1.42 / y 0.56..2.16` with `_clip_poly_plane`/`_subtract_door_rect` (four disjoint pieces per spanning triangle, face tails preserved) instead of dropping whole faces, so no hull wedge crosses the doorway; sealed cabin box 1.56x1.70x1.96 with the roof cap at y 2.20, two rail struts (y 2.10/0.56) + slid-aft panel with recessed window, Retardovici squats at `(-0.44,0.55,0.68)` via cached `_vip_pose()` (start `lhip_p=112/lkn=134/lank=0`, `rhip_p=106/rkn=130/rank=0`, spine 38, head_p -22; a load-time loop tightens hips/knees/spine/head until `max_y <= 1.94` against real `Humanoid.build` verts - resolves at 116/138/41/-24, min_y 0.550 / max_y 1.913, 22.7 cm under the 2.14 lintel; the old "~1.76 m" estimate used the generic rig, not the 2.276 m president rig); `liftoff_window` eye `(-6.2+0.35u,0.78,3.3-0.25u)` -> tgt `(-0.24,1.24,0.58)`; `liftoff_maru` approach `eye_ext (-1.4..2.2, hy+2.45..2.50, hz-4.4..-3.6)` and `tgt_ext` offsets `-1.2/+0.5` / `+1.4/+1.05`. Shot 2: estate poplars move from `x=+-15.0, z=40.0+6k` to `x=+-26.5, z=40.5+6k` in `mansion_set._grounds_estate` and their mulch discs in `mansion_env.build_yard_detail`, clearing the east-corridor view. Shot 3: `flight3d._heli_tilt` estate roll/pitch 14/-4 -> 8/-3, `flight_fx.gunner_eye` leans forward (`ly=fy+0.92`, `lz=0.40+cos(rr)*0.24`) so the aft starboard rocket pod and rotor tip clear the 62-deg FOV; LMG mount `fwd_off=0.78-0.06*ads`, `rg_off=0.225-0.120*ads`, `up_off=-0.255+0.030*ads`, toe-in `-5+2*ads` / `4.5-0.5*ads`, bore z 0.735; the separate `ammo_pouch` submit is gone (its fourth brass link box floated through the receiver, while `tactical_lmg.mesh.json` already has its own ammo box and belt). Estate plaster/stone in `mansion_set` (shell/hall/terrace/grounds/fountain) and `mansion_env` (flagstones/shoulders/cottages/substation/gatehouse) now use the `stucco`/`ashlar` tex3d pair, not `m7_plaster`/`m7_stone`.
- M8 Duty Last Flight night-corridor / encounter overhaul (2026-11-21; **supersedes the scenery and combat numbers in the bullets above**): `duty/flight_set.py` is rebuilt at `RES=(720,504)`, `FOG=(9,13,24)` start 85 / end 420 with `ambient=0.20 diffuse=0.52 sky=0.10` and bloom `0.38/0.84`; `surface_y` returns flat `0.0` for `z<=2240`, rising embankments on Route 12 and a steeper canyon north of 3360. `_ribbon`/`_curve_beam` bake curve-following XZ strips and yaw/pitch-aligned kerbs, medians and guardrails (no stair-stepping); the four zones gain 3-tier 4-sided blocks with lit stairwells/balconies, tram catenary portals and cross-streets, a colonnaded Broadcast Plaza + cross-braced 88 m tower, a divided Route 12 toll plaza with charred wrecks, multi-tier spruces/rock crags, searchlight puffs in `draw_corridor_fx`, and up to 10 local lights / 18 pools in `frame`. `flight_fx.py`: FPV now submits the real GLB via `CS.put_maru_gunship(r, hpos, hyaw, hpitch, -hroll, ...)` plus `_maru_interior_accents` (emissive gauges, pintle collar), Maru at `info["pilot_seat"]` and a roof beacon; new `tanker_mesh`/`draw_tanker` and `draw_flak_bursts` (incandescent snap + smoke), 5-lobe tanker fireballs and progressive smoking/burning stages on vehicles, AA trucks and Ucilev (gated on `phase`/`light_on`/`hit_t`). `flight3d.py`: new `"tanker"` target (`HP 46`, `SPHERE (1.6,2.8)`) with 16.5 m chain detonation; `FIRE_GAP=1/13.8`, `HEAT_SHOT=0.0142`, `HEAT_COOL=0.42`, `FLARES=5`, `ROCKET_V=34`; road rocket closure `HELI_V+26`, road altitude `FS.surface_y + ALT`; `TAIL_HP_MAX=380` with two 3-stage damage callouts and evasive bank (`retardovici_roll`); Ucilev is a 2-phase duel (`UCILEV_HP_MAX=780`, `UCILEV_P2_HP=420`, `UCILEV_FLOOR_HP=180`, `phase`/`light_on` fields, spotlight-break boom, aggressive close passes, double missile launch), `flak_bursts` + `m8_audio.flak_pop()` from AA trucks, `_lights()` adds a warm GLB-cabin dome fill. `m8_audio.SINGLES` gains `m8_flak` (+ `_flak_pop`/`shot_pcm("m8_flak")`), warmed at scene entry. **Match-cut caveat:** `m8dutyfilms.liftoff_maru` still draws the procedural `flight_fx.fpv_gunship_mesh()` cabin and old Maru seat offset `(-0.46,0.20,1.68)` for `whip_u>=0.85` while flight now uses the GLB + `pilot_seat`; camera/aim still match (both call `gunner_eye`), but the cabin/actor pop at the cut wants a live eyeball.
- M8 Duty flight sightline / rocket-readability pass (2026-11-21; **supersedes the FPV mesh, boulevard setback and rocket numbers in the bullets above**): the first-person views no longer draw the heavy closed `maru_gunship.glb` - `flight_fx.draw_cabin_and_gun()` submits `fpv_gunship_mesh()` + `rotor_mesh()` (`FPV_ROTOR_HUB=(0,2.54,0.35)`) with `gunner_eye()` centred at local y=1.56 and a 360-deg clear sightline; sills <=0.18, port console <=0.94, canopy roof y=2.34, stub wings/rocket pods moved aft to z=-0.58, and the tail beacon submit is gone. Local anchors `FPV_PINTLE_TOP=(0,1.07,0)` / `FPV_PILOT_SEAT=(-0.46,0.20,1.68)` replace the GLB info dict in the FPV path; `m8dutyfilms.liftoff_maru` uses the same anchors once `whip_u >= 0.85` so the match-cut frame is identical. `flight_set._build_corridor`: Tier-1 streetfront blocks set back to `22.5 + w*0.5` (sidewalks `+-13 m`, heights 14.0..22.5 m), Tier-2 to `52/54 + sw*0.5`, Tier-3 to `98 + dw*0.5`, rooftop RPG spawns only on 13..25 m roofs, pine bands `(18,34,56)`; tall 26..68 m skyline slabs stay in Tiers 2-3. `flight3d`: `ROCKET_V=18`, `ROCKET_CLOSE_ROAD=24`, `ALT=24`, road weave `corridor_x(z)+5.5*sin(rt*0.36)` at `alt_base=29` for cp 1-2, yaw `corridor_yaw-10+5*sin(rt*0.36)`, roll `10*cos(rt*0.36)`, aim straight down the boulevard (`gy=0`, `gp=-5`), `retardovici_pos` at `alt_base+3.2`. New `_can_launch_rocket(src, air_launched=)` gates launches to the front hemisphere (>=68 m ahead ground / >=28 m air on roads, +-78 deg cone; >=26 m and +-85 deg elsewhere) and rockets that pass `hp.z-4` lose lock instead of chasing from behind. Closing speed is controlled in the helicopter's moving frame (`hvel + dir*v_close`, ~20/24 m/s road, 18 m/s air/estate) with a loft arc and a `0.85 s` telegraph; shootdown sphere 2.2 -> 2.8 m, `"rocket_f"` callout replaces `"rocket_b"`, and off-screen chevrons project the rocket vector onto the camera right/up basis. `flight_fx.draw_rocket` now renders the previously-unused `rk["trail"]` as a tapered glowing `add_line3d` ribbon plus a bright head-on motor/nose flare and denser high-contrast smoke (`shade_col=(204,206,218)`).
- M8 Duty FPV real-GLB sightlines + world-space rocket physics (2026-11-21; **supersedes the FPV mesh and rocket numbers in the bullets above**): `chase_set.maru_gunship_fpv_parts()` caches a sightline-clipped FPV fuselage of `assets/3D/maru_gunship.glb` (reuses the full boom/rotors and `info`); it drops the eye-level `cabin_b_pillar_*`, `quarter_mullion_*`, `a_pillar_*`, `windshield_center_mullion` and `rocket_pod_*`/`rocket_tube_*`/`weapon_pylon_*` leaves, clips `bulkhead_*`/`cabin_aft_wall_*`/`aft_stern_bulkhead_cap`/`sliding_door_*`/`aft_boom_severed_*` to `y<=1.04` with Sutherland-Hodgman `_clip_poly_y_le`, and makes `avionics_*` emissive at night (3008 -> 2188 faces, 72 emissive). `put_maru_gunship(..., fpv=True)` submits it under a separate `maru_fuse_fpv[_burnt]` cache key while the cutscenes keep the full unclipped hull; `flight_fx.draw_cabin_and_gun` passes `-hroll` (CS `_xf` uses `rot_z(+roll)`, `FX.heli_matrix` `rot_z(-roll)`), seats Maru on `info["pilot_seat"]`, anchors the pintle at `info["pintle_top"]`, adds the GLB roof beacon, and uses `info["floor_y"]` for damage sparks/cabin fill; `gunner_eye` sits at `floor_y+1.06 = 1.634` (clear of the 1.22 instrument hood and 2.18 roof rim, Maru on port). `m8dutyfilms.liftoff_maru` calls `_gunship(..., fpv=(whip_u>=0.85))` at the whip and the LMG park/play pintle uses `ginfo["pintle_top"]` on both sides of the cut. Rocket physics: `flight3d` drops the `hvel` addition and the upward loft - `dir = normalize(vel)` and `p += dir*min(d, v_world*dt)`, so smoke/contrails trail behind the nose back to the launcher. Lead-intercept follow-up (2026-11-21; **supersedes the speeds/gates below**): `ROCKET_V=22` (estate), `ROCKET_ROAD_V=28`, `ROCKET_AIR_V=26`, `ROCKET_DMG=18` (were 16/22/22/14 - pure pursuit at 14/8 m/s had no intercept solution against the 34 m/s heli; current speeds close in 1.4-2.6 s); `_heli_vel()` finite-differences `_heli_pos()` (backward diff at a section end) and `_rocket_intercept(p, tgt, vh, s)` solves `|(tgt-p)+vh*t| = s*t`, lifting `s` to `1.12*s_min+1` when the discriminant is negative. `_fire_rocket` and `_ucilev_kill_shot` seed `dir` from it; `_rockets_update` re-solves each tick (turn `9.0*dt`, ramp `0.65..1.0`, tail speed `28`), keeping `rk["dir"]` aligned to the world path. Road gate `dz > 90/58 m` (ground/air), relaxed to `>= 60/36 m` once a `rk_tele` windup has begun, `dist_xz <= 180 m` ground / `220 m` air, `abs(rel_fwd) <= 72 deg`; rpg/aa stay active out to 185 m; missed road rockets drop lock at `hp.z-2`. `e["rk_tele"]`, separate from bullet `tele`, stops aa/gunship rocket windups from re-rolling `rng.random()` or aborting on the launch-range re-check. Decoy flares inherit `0.78*HELI_V` forward momentum and decoyed rockets lay trail/puffs as they curve into them. Probe: full/fpv 3008/2188 faces, 72 emissive, cp=0/1/4 plus 3 whip frames rendered headless.
- M8 Duty rocket-difficulty + night-canyon readability pass (2026-11-21; **supersedes the rocket/combat and corridor numbers above**): `flight3d` shrinks the rocket hit sphere to `0.90 m` (was 2.8) and removes the free `-0.14` barrel cooling on rocket kills; rockets are harder to swat from afar with speeds `22/28/26` (estate/road/air), `ROCKET_DMG=18`, ground launches capped at `dist_xz <= 180 m` (air 220 m, rpg/aa active range 185 m), and the HUD lock diamond/range text only drawn inside `105 m` (7/1 px instead of 9/2) - beyond that track the flame/contrail visually. `flight_fx.draw_rocket` shrinks the motor flare (radius 2.35->1.65, `max_px` 72->42) and seeker glow (1.15->0.78, `max_px` 38->22). Flight altitude drops into the canyon (`alt_base=21.0` cp1-2, `ALT=19.5` cp3-4, dive 9->6, bob 2.8->2.0, `gp=-6.5`, Retardovici +2.5/1.8), `height_fog` softens to `(0.0028, 0.0, 2.2, FS.FOG)` and `wetness=0.48`. `flight_set`: `FOG=(12,17,30)` / start 130 / end 560, `Light(ambient=0.34, diffuse=0.62, sky=0.18, tint=(0.74,0.84,1.0))` and brighter pavement/ashlar/grass/asphalt albedos lift the cine-curve black crush; `_nearest_lamps(focus, cap=18/22)` samples 55 m ahead along the actual aim direction (26 lights / 28 pools caps, intensity 1.20/1.75, range 30/14.5) instead of around the heli; cross-streets extend to `+-180 m` with sidewalks, five sodium lamps per side and flanking tier-2 blocks; tier-1 spacing tightens to 23-27.5 m with kiosks/storefront signs, tier-4 outer towers at `x=+-138..195 m` up to 86 m, denser zone-2 infill, nine barricades and Route 12 valley ridges. `_add_building` computes `seed_h` once at function top (the supplied storefront-sign hunk used it before its old definition - moved up). Bake probe: 108991 faces / 187 lamps / 444 beacons / 130 roofs; cp=0/1/2/4 render clean.
- M8 Duty Overhaul — 4-Phase Master Plan (2026-11-21; **supersedes the FPV hull slice, camera/gun hierarchy, flight paths, horizon/corridor density, rocket kinematics and Duty transition fades above**):
  1. **Phase 1 — Grounded Starboard Door-Gunner Rig & Flight Choreography**: `chase_set.maru_gunship_fpv_parts()` keeps the cabin roof, overhead ribs, port fuselage wall, rear engine bulkhead, and A/B cockpit pillars intact (`_MARU_FPV_DROP` removes only the center-aisle pintle nodes, `sliding_door_*_stbd`, and starboard weapon pod/pylon; zero `y<=1.04` wall clipping); `put_maru_gunship(..., fpv=True)` disables hard solid `main_rotor` mesh (`main_on and not fpv`) while the intact ceiling/lintel hides the mast. `flight_fx.py`: `PINTLE_PIVOT_LOCAL=(0.94,1.22,0.30)`, `TRUNNION_LOCAL=(0,-0.055,0.180)`, `AMMO_FEED_LOCAL=(0.64,0.85,0.56)`, `FEED_TRAY_LOCAL=(-0.038,0.035,0.120)`, `EJECT_PORT_LOCAL=(0.045,0.025,0.095)`; wired `_maru_interior_accents(info)` (sealed port cabin wall, starboard doorway ceiling lintel & padded jambs, yellow/black caution sill stripes, rigid floor-to-trunnion steel pintle stanchion post, bolted olive ammo box, emissive cockpit dash gauges, warm amber bay lamp), `_pintle_yoke_mesh()`, and 7-segment catenary `_draw_ammo_belt()`; reversed gun/camera hierarchy so `lmg_xform` locks the LMG trunnion to `pivot_w` (`gun_at = pivot_w - basis*TRUNNION_LOCAL`) and `gunner_eye` positions Biribel's eye behind the stock/receiver (`back 0.56->0.44`, aligning to `(0,SIGHT_Y,OPTIC_Z)` on RMB ADS). `flight3d.py`: clamped starboard firing arc `REL_YAW_LIM=(8.0,152.0)`, `PITCH_LIM=(-62.0,20.0)` with soft stop damping in `_clamp_gy()` and stop ticks on the top compass tape; re-choreographed `cp=0` to a monotonic clockwise pylon orbit (`START_A_DEG=104.0`, `LAWN_C=(0,0,-18.0)`, `LAWN_R=38.5`), `cp=1..4` to west-flank port-crabbed flight (`corridor_x(z)-10.0`, `corridor_yaw(z)-33.0`), and `cp=4` Ucilev to `+20..+108 deg` starboard-forward passes.
  2. **Phase 2 — 360° Horizon Sealing & Full-Corridor Environmental Rebuild**: `mansion_env.py` widens `_plain` to `+-380 m` and adds a 360° outer forest + capital skyline glow ring (`r=186..216 m`). `flight_set.py` sets `FOG_START=100.0`, `FOG_END=375.0`, widens `_ribbon` ground planes to `x=+-460 m`, adds camera-anchored 360° horizon silhouette rings (`_urban_horizon_ring` + `_mountain_horizon_ring` cross-faded at `z=1880..2380` via `draw_horizon_ring(r, hpos)`), and rebuilds Zones 1–4 (deep `+-260 m` cross-streets, stranded trams, stalled convoys, zero-gap Broadcast Plaza with bunkers/guy-wired 88 m tower/microwave dishes, gradual industrial & rail-yard transition `z=1980..2240`, Route 12 Carpathian foothills + parallel railway + 4 landmarks at `z=2420,2680,2920,3160`, and steep `+45..95 m` Northern Ridge Gorge with 6 spruce bands, snow-dusted crags, and valley mist).
  3. **Phase 3 — Physical 2-Stage Rockets & Flight Combat Feel**: replaced discriminant speed-warp `_rocket_intercept` and `hp.z-2` pop-out deletion with real 2-stage missile kinematics (`phase="boost"|"cruise"|"ballistic"|"decoyed"`, `kind="rpg"|"sam"`, `ROCKET_BOOST_V=18.0`, `ROCKET_RPG_V=52.0`, `ROCKET_SAM_V=60.0`, `SAM_TURN_DEG_S=62.0`, `ROCKET_TELE_S=1.0`, `_rocket_lead_point` + `_rotate_dir_bounded`), launch backblast flash + rising white exhaust column (`draw_launch_backblasts`), `0.6 m`-sampled 32-segment contrails, `1.35..1.50 m` range-scaled shootdown sphere, `1.2 s` physical doorway flyby misses (`"ballistic"`), and HUD acquisition diamond (`<130 m` full readout, faint acquisition on launch).
  4. **Phase 4 — Seamless, Non-Fade Transitions Across All of M8 Duty**: `app.py` supports `"hard_cut_in": true` on `_m8_film_pending()` (`gsm.transition("CUTSCENE")` instead of `trigger_transition`); `m8dutyfilms._finish_full` renders full-frame match-cuts with smoothly retracting letterbox bars for `approach_gate -> mansion3d cp=0` and `liftoff_maru -> flight3d cp=0` (using the exact Phase-1 intact cabin + fixed-trunnion pintle LMG); `flight3d` replaces the `cp=0 -> cp=1` navy veil and `_setup(1)` reset with a live 3D low-cloud bank traversal (`_advance_section(1)`, preserving aim/heat/flares), spawns Ucilev on a choreographed canyon dive-in at `cp=3 -> cp=4`, and hard-cuts from the spinning cabin into `crash_spin -> crash_black` tree-impact smash-cut; `ridge3d` adds a live `1.3 s` rifle-shouldering iris-scope entry (`INTRO_S=1.3`) and holds `1.8 s` in cold wind silence on `pres_down` before snapping into `d_epilogue`'s State TV CRT power-on scanline flash (`_crt_power_on`).
- M8 Duty Ucilev boss overhaul (2026-11-22; **supersedes the Ucilev phase/gorge numbers above**): `duty/flight3d.py` (`SECTIONS[4]` extended to `z=3360..5400` at `UCILEV_V=28.0` plus a C1-continuous clockwise basin orbit of radius `UCILEV_ORBIT_R=46.0` past `z=5400`, zero stall; `_spawn_ucilev`, `_ucilev_spheres`, `_on_ucilev_subsys_break`, `_save_ucilev_checkpoint`, `_update_ucilev`, `_ucilev_combat`): 3-phase destructible subsystems (`UCILEV_SUB_HP`: `spotlight` 1100 -> `pod_l`/`pod_r` 950 each -> `turbine` 550; `UCILEV_ANCHORS` matched to `CS._xf`, `1.25x` weakpoint crit vs `0.35x` armored hull spill, `1.35 s` stagger protection + micro hit-stop, zero `UCILEV_FLOOR_HP` stall), ace maneuver state machine (`dive`/`stalk`/`spotlight_sweep`/`sam_hover` -> `strafe_arc`/`pod_salvo`/`canyon_pass` -> `close_duel`/`cliff_feint`/`ram_pass` -> `1.45 s` `climax` blowout fakeout -> `_ucilev_kill_shot` with `bypass_dz=True`), Maru evasive banking (`_evade_roll`, `_evade_y`), weakpoint lock brackets, 3-segment boss phase bar and `cp_toast` checkpoint banner in `_hud`. Subsystem break checkpoints: destroying `spotlight`, `pod_l`, or `pod_r` snapshots phase/subs/`sec_t` to `STATE.m8_ucilev_cp` (declared in `core/state.py` `STATE.reset()`, cleared in `finish()`, `flow.on_flight_done()`, or active `cp < 4`), restores mid-fight directly in starboard view with full hull/flares on death (`hurt_hull` ignores hits once `climax_t >= 0`), and offsets the `82 s` fallback timer by `_ucilev_cp_sec_t`. `duty/flight_fx.py`: `cs_matrix` (`rot_y * rot_x(-pitch) * rot_z(+roll)` matching `CS._xf`), cached `_ucilev_trim_mesh` / `_ucilev_spotlight_mesh` / `_ucilev_pod_mesh` / `_ucilev_turbine_core_mesh`, shared `draw_ucilev_fx()` (also used by `cutscenes/m8dutyfilms.py` `crash_spin` at `upos=(18,26,34)->(-2,33,56)` so Ucilev leaves the battle burning), and `draw_gorge_snow()`. `duty/flight_set.py`: extends Zone 4 to `z=5800` with a widened alpine basin at `z=5280..5550` and 4 baked landmarks (`z=3460` Retardovici crash clearing, `z=3820` 34 m-high Iron Gorge trestle bridge, `z=4280` relay bunker + searchlight, `z=4780` gorge power pylons). `m8_audio.py` + `flow.py`: adds `m8_rotor_pass` / `m8_subsys_boom` (`rotor_pass`/`subsys_boom`) and `"flight_boss"` volume swell when `cp >= 4`. Unit test: `tests/unit/test_m8_ucilev_boss.py` (6 tests).
- M8 Duty Ridge sniping overhaul (2026-11-23; **supersedes the ridge `SLOWMO`/scope/snow notes above**): `cutscenes/m8duty_sets.py` (`ridge_forest`, `_snow_pine`, `_tripod_light`) adds the crash gouge/scorch trench & snow berms leading to the downed helicopter, pad markings, sheared rotor/cowling wreckage, sandbag cover, crates, field radio box, 4 physical tripod floodlights at `((-8,-8),(8,-8),(-8,10),(10,10))`, emergency flares, snow-capped granite outcrops, and a foreground sniper cliff ledge (`d_fwd = 0.4 m`, `y_rel = -0.95 m`, cleanly below all scope zoom cones) framing the `46 deg` intro (`ridge_frame` ambient `0.34`, diffuse `0.58`). `missions/m8/duty/ridge3d.py` (`RidgeScene`): `_intro_rifle_mesh` uses `cast3d.weapon_asset("sniper_rifle")` with `rifle_mesh(scope=True)` fallback; `fire()` resolves the target synchronously for caller compatibility while launching a visible 3D round (`FLIGHT_S=0.22`, `FLIGHT_KILL_S=0.26`) with parabolic gravity/wind curve, golden tracer, and post-impact vapor wake (`_draw_bullet`, `_bullet_pos`), delaying hitstop (`0.055 s`), punchy slow-mo (`SLOWMO=0.45`, `0.38..0.42` game-s instead of `0.25x` over `2.0 s`), and death reaction until bullet arrival (`_resolve_bullet`); `hit_mark` drives a real-time `0.32 s` tactical X hit-confirmation marker in `_scope` alongside cached ocular lens vignette (`_mask`); impacts trigger `_spawn_gore` (3D ballistic blood droplets + exit streaks, `_blood_mist_sprite` aerosol bursts, `hd=True, wound=3, bloody=True` + `"head_wound"` rig decals, expanding `_pool_mesh` crimson snow pools, permanent `snow_stains`, and tumbling dropped rifle / blinking Guard radio via `_draw_dropped_props`) and multi-stage collapses (`ucilev_spot` low-ready rifle -> snap -> buckle -> knee drop -> last words -> forward slump; `pres_spot` crouch holding radio -> stand -> snap -> stagger back -> flat snow collapse); ground misses compute real drop/wind intersection (`_ground_impact`), snapping near-boot misses in `"ucilev"` (`dist_u <= 7.5`) and spawning `_snow_geyser_sprite` + `snow_chunks` clods + dark snow craters.
- M8 Duty Northern Ridge Gorge / live 1x peripheral scope overhaul (2026-11-23; **supersedes the ridge set/scope numbers above**): `cutscenes/m8duty_sets.py` adds `_clamp`, `_ridge_height(x,z,pad,eye)` and `_ridge_terrain_mesh(pad,eye)` - a triangulated Carpathian gorge replacing the flat snow slab (flat `r<=18 m` evac clearing, `eye[1]-0.85` m granite spur dropping `<= -46 deg`, +18..+68 m walls, transverse highway bed at `fwd~154 m`, secondary crash clearing at `fwd 70 / lat -46`, two 360-deg horizon rings at `r=215/268 m`). `ridge_forest` grounds crags/spruces on `_ridge_height`, clears an angular sight cone `abs(d_lat) >= max(14.0, 0.28*d_fwd + 6.0)`, builds the gorge highway + guardrails/sodium lamps, 3 power pylons, a flank crash scar and a grounded sniper perch (shooting mat + spruce-log rest) under EYE; fog/light unify with Last Flight Zone 4 (`FOG=(12,17,30)`, 75..360 m, ambient 0.26, diffuse 0.56) and `ridge_frame(..., roll=0.0)` forwards camera roll. `missions/m8/duty/ridge3d.py`: `ZOOMS=(18.0,8.0,3.8)`, `PERIPH_FOV=54.0`, first-frame `zoom_i=0` aimed at Ucilev via `_setup`; `RidgeScene._populate_world(r,tm,ie,peripheral=False)` (all world submits, bullet gated to the scope pass) plus `RidgeScene._draw_ridge_snow` (reduced-motion-aware `add_line3d` streaks) feed two `DS.ridge_frame` passes per frame in `draw()` - a 54 deg 1x peripheral pass (quarter-res `smoothscale` defocus + `_get_periph_tint` nocturnal multiply, cached in `_SCOPE_SURFS`; GL live, software throttled via `_periph_state`) composited under a crisp circular lens (`_lens_alpha`/`_blit_circular_lens`) from the magnified pass. Cached `_perch_gun_mesh` (barrel/suppressor/bipod) submits to the periphery after the intro; the optic gets `_housing(rad)` (elevation/windage turrets, gunmetal bezel, cheek shadow, AR sheen), with `_mask` kept as a compatibility alias. Lighting adds a parked `gun_truck` with headlights, distant Maru crash fire/haze and 4 extra `_PAD_LIGHTS` entries; muzzle flash honours `flash_reduction`, sway honours `reduced_motion`, scope radius is `HEIGHT*0.42`, HUD ZOOM divisor 72.0 plus an early control-hint line. Caveat: the supplied `_PAD_LIGHTS` snippet needed `tuple(...)` around its generator or import raised `TypeError`.
- M8 Duty Ridge visual-correctness pass (2026-11-23; **supersedes the gorge numbers above**): driven by the 4-frame contact sheet, `m8duty_sets.py` reworks `_ridge_height` into a smooth V-shaped funnel (curved road `fwd=152+14*sin(lat*0.018+0.4)`, uniform 12 m heightfield grid instead of coarse 22 m quads, valley-floor drifts), simplifies the apron to `disc_xz` octagons and the crash skid to flat scorch (no white curb boxes), builds the road from 18 ribbon quads + `_wire_span` guardrails, 3 `_gorge_pylon`s with sagging transmission lines and beacons, a grounded foreground perch (`fwd 2..3.6 m`, `y_rel -0.60..-1.18 m`) with timber rail and crags, and 132 wall spruces; fog `(10,14,24)` 52..250 m, ambient 0.17 / diffuse 0.42, and `ridge_frame(..., pools=())` now forwards ground pools. `ridge3d.py`: intro GLB lens recolored to coated glass, `_perch_gun_mesh` lowered onto the log, VIP wreck moved to `_off(9.4,-3.6)` yaw 225 with rising smoke and headlight haze, tripods/flares moved clear of the targets, `_pad_pools()` warm ground pools, numpy-based `_get_periph_tint`/`_lens_alpha` (no banding/steps), a 2-stage defocus and an authentic PSO-1 reticle (amber chevron, drop ticks, stadiametric arc); the cheek-weld polygon was removed from `_housing`. Caveat: the owner's snippets again needed the earlier `tuple(...)` and 3-tuple-unpack fixes, both preserved.
- M8 Duty Ridge v3 framing cleanup (2026-11-23; **supersedes the v2 perch/periphery numbers above**): from the second contact sheet, `m8duty_sets.py` drops the flat shelf/log and builds an organic jagged granite firing notch (three `_bipyr` sill stones at `y_rel=-1.56`, `z=2.4..2.5`; flanking crag clusters and leaning spruce bough tufts at `+-20..26 deg`, inside the 54 deg periphery but outside the scope tube), unifies the snow albedo (no `(ix+iz)%2` checkerboard), rebuilds `_gorge_pylon` as a four-leg A-frame lattice with ring braces and a beacon, and moves the front tripod to `(-7.8,-2.0)`. `ridge3d.py`: x4 start yaw `-1.8 -> +0.6` deg so the burning chopper stays in frame, shorter/dimmer snow streaks, intro rifle raised (`off_l y -0.14`), front tripod light moved to `(-7.8,-2.0)` and the eye-side fill to `fwd*2.6 / y+0.9 / intensity 1.25`, and a brighter numpy peripheral tint (`k = 0.78 - 0.36*smoothstep`; RGB 214/228/252) so the outside flanks read as night ridge instead of near-black. Re-shoot: `_shots/ridge_overhaul_v3.png` (all four frames OK).

- M8 Duty Ridge sniper-hold / hitbox / ballistics fix (2026-11-23; **supersedes the v3 target/bullet notes above**): `ridge3d.py` adds `_recolor_sniper_face` (amber GLB lens -> coated glass, khaki stock -> dark walnut) shared by the intro and world weapon; `ucilev_spot` drops the hardcoded arm angles, and `draw()` solves `hold_frame(..., weapon="sniper_rifle", mode="ready")` on `_w.life_pose`'d Ucilev, submits the baked mesh at `(r_orig, r_basis)` with `rifle_on=False`, and spawns the dropped rifle from the live hand transform (`_u_gun_xform`). `targets()` now stacks head/chest/pelvis/legs spheres for Ucilev, Retardovici and Guards (no gap from y=0 to 0.79 m). `_bullet_pos` follows `p_aim` linearly with quadratic `u^2` drop/drift instead of the inverted `4u(1-u)` arc; `fire()` drops the `k_pull` teleport and duplicate impact kick, distinguishes `near_feet` vs `past_body` misses and keeps the hit point at the true ballistic height. `_snow_geyser_sprite` is a small 0.62 s kickup on depth-sorted layer 2. Re-shoot: `_shots/ridge_overhaul_v4.png` (hold, clean snow miss, tracer, chest hit + dropped rifle).

- M8 Duty epilogue Maru crutches tail restored (2026-11-24): `cutscenes/m8duty_crowd.py` `draw_maru_with_crutches` was truncated after `cuff_m = _basis_from_xy(right_v, fa)`, so the forearm strut, the three open-front U-cuff boxes + mount block and the final `r.add_dynamic(...)` submit never existed - the crutches never rendered (queued-delta 0). Restored `cuff_mount`, `_add_strut(junc -> cuff_mount, alu_hi)`, the cuff geometry and the dynamic submit with `[(f[0],f[1],f[2],f[3],None,f[4]) for f in crutches.faces]`. Probe reports `CRUTCHES QUEUED OK, delta= 1`; `m8_duty_film_shots --only epilogue` and `smoke --only m8` OK. `m8duty_crowd` is imported directly by `m8dutyfilms`, not re-exported by the `cutscenes` facade.

- M8 Duty ending-film cinematography pass (2026-11-20): `cutscenes/m8dutyfilms.py` `_eye(tgt, dirv, vspan, fov)` places the eye at `tgt - dirv*d` where **`dirv` is the view direction (eye->target)**, NOT target->eye; `d = vspan*FILM[0]/(2*FILM[1]*tan(fov/2))` because engine fov is horizontal and the letterbox buffer is ~2.2:1 (vertical span `0.912*d*tan(fov/2)`). Every shot picks its vertical span in metres (face 0.6-0.8, medium 1.3, two-shot 1.6, wide 3.4+) instead of guessing distance. Crash cams sit on the correct side of the Maru(225°)/Biribel(48°) facing axis and offset perpendicular so neither actor blocks the other: `crash_fire` SE-above two-shot `dirv(-0.58,-0.15,0.80)`, `crash_promise` east front-3/4 on Biribel `(-0.92,-0.13,-0.20)` (clear of Maru to the north), `crash_better` SE on Maru's **reclined head** at `_MARU_CRASH_AT+(0.51,0.85,0.43)` (probe `Humanoid.pose_world()[1]['head']`; his chest is NOT his head) `dirv(-0.80,-0.10,0.60)` vspan 0.60 - a SW/front cam lands on top of kneeling Biribel. `crash_spin` end eye stays inside the cleared south corridor (`|x-c|<8.5`, eye x `c-6.0`); `c-8.5` sat on the corridor boundary inside a pine bough (black frame). Liftoff: `liftoff_study` reframed on Biribel at the balustrade (vspan 3.4, heli passes overhead); `liftoff_maru` approach base raised to `hy+0.9` (was `hy-2.2`, hidden behind the terrace balustrade), `gyaw=-90+45u-10climb` (ends ~-53° so the port side faces the mansion W-SW), starboard door `rot_y(-45)`, cabin-whip lands on a vista `cab_tgt` local `(-4.2,0.7,-2.4)`; `liftoff_window` now uses `_vip_open_body()` + `_draw_vip_open()`: the closed VIP GLB has **no door node**, so a doorway is cut by dropping every body face with ANY vertex in the port rect `x<-0.55, 0.5<y<2.45, -0.2<z<1.6` (a centroid test leaves large GLB triangles spanning/blocking the hole) masked by frame boxes, and Retardovici stands in the sill at local `(-0.92,0.55,0.70)`; camera is a full-figure port-side door shot in hull-local coords via `CS._xf`, lit only by `_heli_lights` (an extra close key blew him out to a cream mannequin). Epilogue `biribel_vo` camera moved to Biribel's FRONT (`BIRI_AT+(1.1,1.62,+3.4)`, he faces the courthouse/north so a south cam showed crowd backs). `m8duty_sets.py` courthouse/city facades use new `stucco`/`ashlar` tiles (below) instead of `m7_plaster`/`m7_stone` (mould blotches); `_pine_tree` 6 tiers; `crash_forest` south corridor widened to 8.5 m for trees AND shrubs. Probe: `tools/m8_duty_film_shots.py` renders every Duty film at 25/60/95% of its timeline into `_shots/<out>/sheet_{liftoff,crash,epilogue}.png` (`--software`, `--only=`).
- `cutscenes/m6world3d.py` is the shared 3D cast/set host (`hum(key, hd, wound, bloody, flags)`, `actor(r, key, pose, pos, yaw, t, ...)`, `add(r, m, bias)`, `life_pose`, `LAST`, `_gun_mesh`). Importers: every `missions/mN/draw3d.py`, `m3/wings3d.py`, `m6/train3d.py`, `m7/raid3d.py`, `m7/raid_world.py`, all `m8/revenge/*3d.py` + `beats.py` + `chase_set.py`, `m8/duty/{mansion3d,flight3d,ridge3d}.py`, `cutscenes/{intro3d,m3broadcast3d,m3ko3d,m3staging,m6films,m6fx3d,m7films,m7world3d,m8films,m8dutyfilms}.py`, `game/topdown3d.py`, `ui/arena_view3d.py`, `ui/mp3d.py`, `ui/mission_complete_3d.py`, `missions/walk3d.py`. Treat `hum()` flags and `actor()` signature as a cross-repo contract. Flag `"nopump"` (with `"shotgun"`) builds `shotgun_mesh(with_pump=False)` under GL key `|shotgun_nopump`; raid3d/trap3d use it and draw `shotgun_pump_mesh()` themselves so the pump slides.
- `cutscenes/m6fx3d.py` (fx), `cutscenes/death3d.py` (death) are shared by raid3d/trap3d. `cutscenes/m7world3d.py` = M7 farm set (raid3d).
- 3D holds: `engine3d/hold.py` `hold_cached`/`hold_weapon` with a `GRIPS` key; the weapon key comes from `hum._weapon` or `spec["rifle"]` (`weapon_of`). `hold_cached` uses an LRU `OrderedDict` (cap 1024, never full-clear mid-fight) and `solve_arm_safe` reuses fixed torso volumes across pole trials; per-frame callers with animated spine/twist/stagger (`m6/train3d.py`, `m6/yard3d.py`, `ui/mp3d.py`) solve once on `POSES["ready"]` (pre-warmed at scene load; `game/topdown3d.armed` also calls `mp3d.warm()` on first use) and graft `_HOLD_KEYS` + `spine`/`twist` offsets instead of passing per-frame blended poses into `hold_cached`.
- M5 mid-cutscene sets (`cutscenes/m5mid3d.py`) now share the 2.5D Lower Quarter look: `_qt(name, col, k)` caches `engine3d.textures.tex(..., tint=True)`, `_pave_tex`/`_conc_tex` add per-tile noise, and `_framed_window`, `_quarter_block`, `_mag_van_3d`, `_paper_bales_3d` build framed windows, grime-banded multi-storey blocks, the MAG panel van and strapped paper bales. `_faces_set(r, t)` rebuilds the East Checkpoint (Kovac & Sandu) as a continuous avenue with jersey barriers/sandbags leaving the north lane open and MAG Print Works down the cross-street; `_street_set` uses the same helpers so `_arrival_wide`/`_arrival_door` no longer show a black void at the edges. `cutscenes/ps2mat.py::_class` classifies dark low-saturation cool colours as `"asphalt"` (`_material`: `pavement` on flat faces, `concrete` elsewhere) instead of leaving them untextured. Note `quad_xz(colfn=...)` receives grid indices `(i, j)`, not world coordinates (the legacy `wet` lambda convention), so noise is per sub-tile rather than world-locked. `_street_set`'s avenue now runs x=-64..32 (kerbs, lane dashes, tram rails to -58, streetlamps at -13.2/-26.5/-40) with a Quarter block chain out to x=-58 and opposite-side blocks behind the camera, so `_arrival_wide` Angle 1 (low follow, fov 72, left edge ~x=-52 at the z=10 plane) no longer exposes void; the corner blade sign carries three emissive lettering bars. `_faces_set` caps the cross-street ends at x=±22 (blocks 608/609) so looking left/right down z=18..22 never shows void either.

### 4.4 Art, sprite and bake precedence
```
Code-authored pack art:  src/game/art/mN/<asset>.py render()
  declared in src/game/content/mN/manifest.json
  baked by   python tools/ae_bake.py --pack mN  -> assets/baked/mN/<asset>_<v>.png + .bakeinfo.json
  runtime    game.art.mN.get(name, v) -> engine/assets/registry.AssetRegistry.get: BAKED PNG FIRST, live render() second
Sheet art:  tools/sprites/<family>.py (palette.py, kit.py) -> assets/art/spr_<name>.png/.json
  rebuild    python tools/build_all_sprites.py  (make_art_pack.py, ae_bake.py --pack m5, vehicles, props, fx, portraits, mission_failed, m1_street)
  runtime    core/artpack.py -> engine/assets/_artpack.py (vehicle/prop/fx/frame/blit_frame); None under ACA_ART=legacy|off
3D meshes:  tools/ae_import_<name>.py / tools/ae_build_ak74.py -> src/game/content/meshes/<name>.mesh.json (full inventory §8)
Callers keep a procedural fallback for every baked/sheet asset; never delete it.
```

### 4.5 Strings and text
`T("key")` (`engine/text/strings.py`) -> `src/game/content/strings/en.json`. Missing key renders `[[key]]`. Placeholder names must match the call kwargs (`hud.mags` -> `n=`). Gate: `tools/ae_text_check.py`.

### 4.6 Audio and voice
- SFX/music: `core.config.audio` (`audio/audio.py` `AudioManager`) - `audio.play("reload", volume=)`. Per-mission banks: `missions/m1/m1_audio.py`, `m6/m6_audio.py` (`M6TrainAudio.warm()`), `m7/m7_audio.py`, `m8/m8_audio.py`, `m5/finale_audio.py`.
- OST roster (`tools/ost/album.py`, 20 tracks, baked by `python tools/build_ost.py <n>...` into `assets/music/ost/` + `build/ost/`): 01 Call of Acaristan, 02 Black Notebook, 03 Quiet on Route 12, 04 The Vostral, 05 Curfew Dawn, 06 Not Tonight, 07 Whiteout, 08 I Chose the Many, 09 Fallow Ground, 10 Head of State, 11 Old Friends, 12 Gabi, Seby, Darius, 13 Wet Concrete (early/mid combat WALK/M0-M3 + M8 trap), 14 After Hours (M5 curfew + M0 depot), 15 Cold Iron (M6 combat/insertion), 16 Mending Wire (M7 farm daytime), 17 Cold Marble (M8 Duty approach/mansion), 18 To the Crossing (M8 Revenge chase/gunship), 19 Paper Trail (debrief, BRIEFING, MISSION_COMPLETE, M6 boxcar/radio films, M7 burning finale), 20 Dust on the Road (M7 prep, 7/4 G minor — begins on the `m7_runner_shotgun`/`m7_runner_gun` shot via `m7/flow.film_music` and carries into `STAGE_PREP`). `core/score.py` holds mission-keyed `CALM`/`TENSE` dicts (`TENSE_DEFAULT` fallback): M0/M5 calm uses 14, M6 tense uses 15, M4/M5 tense keeps 06. `m7_audio.MUSIC["farm"]`=16, `["prep"]`=20, `["finale"]`=19; `m8_audio.MUSIC` approach/mansion=17, trap=13, chase=18, flight=10; `m8/flow.STAGE_MUSIC` d_approach→approach, liftoff/crash→flight. `_CutsceneState` routes M6 insertion films to 15/07/19 by `shot["scene"]`, `_BriefingState`/`_MissionCompleteState` play 19 on entry and fade on exit; `_keep_music_for_credits` preserves M8's title theme into CREDITS. Tracks 13-19 were rebuilt from the ground up with no reused grooves/progressions/motifs from 01-12: 13 is 5/4 (118 BPM, C#m), 14 slow 4/4 noir (68 BPM, F#m), 15 6/8 compound (168 BPM, Bm), 16 3/4 folk (86 BPM, G), 17 dark 4/4 march (98 BPM, G#m), 18 4/4 motorik (142 BPM, Fm -> Gm), 19 minimal 4/4 chamber (70 BPM, Dm/Dorian). Filenames are unchanged, so no score/app/m7/m8 rewiring was needed.
- VO: `audio/voice.py` `warm()` (called at boot in `app.py` when the mixer is live so the first combat radio line never scans disk mid-frame) + `play_line(speaker, text, radio=)` -> `find_line` matches text -> `VO_xxx` id in `audio/voice_manifest.py` -> file in `assets/voice`. Callers: `app.py`, `ui/radio.py`, `ui/speechbox.py`, `core/interactions.py`, mission flow/systems files. New line: `VO_xxx` row + `KNOWN_MISSING_AUDIO`, never `VOICE_ORDER`. `app.py` `_CutsceneState.update` fires VO on blank-speaker shots too: `sp = shot.get("speaker") or ""`, then `voice.find_line("NARRATOR", shot["text"])` gates a `play_line(sp or "NARRATOR", ...)`; `scene == "title_card"` stays silent.
- Batch recording: `tools/vo_batch.py` (`status`/`make-refs`/`pack [--redo-bodi]`/`split`/`ingest`/`sync-manifest`/`colab-pack`/`colab-import`) packs missing rows (incl. `00_NARRATOR`) into AI Studio scripts under `build/vo_batches/` or a Colab kit `build/vo_colab_kit.zip`, stitches ~25-30 s voice-replication refs into `build/vo_batches/refs/<SPEAKER>_ref.wav`, picks 1-2 clean takes + exact transcripts for Colab voice cloning (`BAKED_SCREAMS` excluded), splits exported WAVs by silence islands + duration DP into `assets/voice/<Speaker>/VO_xxx.ogg|.wav`, and removes installed IDs from `KNOWN_MISSING_AUDIO` only. `ingest` sorts unrenamed `Generated Audio ...wav` drops by `voice._file_order_key` and assigns them to that speaker's missing IDs in order (`--start`, `--align` for retakes), moving consumed files to `_done/<VO_ID>__<name>`. Uses `voice._speech_units`/`_scan_files`/`has_file`/`_align`/`_duration`; optional numpy, ffmpeg only for Vorbis encode/decode with a `pygame.mixer` decode fallback when ffmpeg is absent.
- Radio UI: `ui/radio.py` (`PORTRAIT_KEYS`, portraits from `spr_portraits` built by `tools/sprites/portraits.py`), fonts `ui/pixfont.py`.

### 4.7 Cutscenes
```
2D/legacy shots: missions/mN/meta.py -> game/timelines.shots(id, legacy) -> content/timelines/<id>.timeline.json
                 -> app.start_cutscene(shots, after_state) -> CutscenePlayer -> cutscenes/engine.py (+ registered renderers, core/cutscene_registry.py)
Hybrid 3D takes: cutscenes/intro3d.py (7 opening narration shots: intro_ocean/city/poster/graffiti/convoy/checkpoint [articulated rolling-wheel FuegoTech semi-tanker]/arrival),
                 cutscenes/van3d.py (van_exterior + van_interior/van_volkov_photo/van_handoff_weapon [pistol.mesh.json]/van_handoff_molotovs [molotov.mesh.json]), cutscenes/m2route12_3d.py (route12_checkpoint/aftermath/broadcast, krap_door_kickin, seby_pickup_*),
                 cutscenes/m3intro3d.py (cell_ceiling/restraints, interrogation_room, monitor_broadcast), cutscenes/m3ending3d.py (m3_end_*, m3_bcast_fail_studio/pa),
                 cutscenes/m4aftermath3d.py (m4_street_curfew, m4_city_curfew, m4_arrest_screen, m4_maru_silhouette, m4_roof_dawn), cutscenes/m7goat3d.py (m7_goat_* on m7world3d farmyard).
                 All respect ACARISTAN_CUTSCENE3D=0 to fall back to the 2D takes in route12.py/m3cell.py/m3ending.py/m3broadcast.py/m4aftermath.py/m7goat.py.
                 2D inserts/dossiers/UI/mechanical beats live in route12.py (route12_black/files/mag_alert, ipa_radio_chatter, biribel_blackout), engine.py (draw_volkov_dossier_overlay),
                 chair.py, k9.py, m3ops.py (vent_shaft/exit, m3_volkov_gives_mags), m3broadcast.py (m3_bcast_fail_retry), m3/draw.py (vostral/archives), missions/m0/__init__.py (_draw_inspect).
3D films:        cutscenes/m6films.py, m7films.py, m8films.py (+ meta.M8_SCENES, m8/revenge/beats.py fallback) -> m6world3d / post3d / weather3d
                 M8 Duty: cutscenes/m8dutyfilms.py, keyed "m8d_*" in meta.M8_SCENES; shot lists content/timelines/m8.d_{approach,liftoff,crash,epilogue}.timeline.json
Mission end:     MISSION_COMPLETE -> ui/mission_complete.py (case dossier, FORM KR-47) + ui/mission_complete_3d.py (live engine3d diorama); preview tools/preview_mission_complete.py
After-states:    M5_RESUME, M6_RESUME, M7_RESUME, M8_RESUME, MISSIONn_COMPLETE handled in app.py _CutsceneState
```

### 4.8 Save / checkpoint
```
missions/mN/flow.py  set_slot_progress("mN", checkpoint=stage)   (m1/main.py, m4/flow.py, m5/flow.py, m6/flow.py, m7/flow.py, m8/flow.py, walking_sim.py)
  -> core/save_system.py (slots JSON; set_slot_progress, set_slot_flags, save_mission_complete)
Resume: app.py _SlotSelectState (progress == "m8"/"m7"/"m6"/... + slot["checkpoint"]) -> core/game_core.start_missionN_* / start_mission7_stage / start_mission8_stage
Dev:    core/dev_jumps.py DEV_JUMPS + app._apply_dev_args (--dev-* flags)
Engine snapshot (replays/tests): game/save_adapter.py capture -> engine/save
```

## 5. Weapon / vehicle / item ID crosswalk

| In-game label | IDs | 3D mesh/rig + hold key | 2D rig / HUD icon kind | Stats/logic | Where used |
|---|---|---|---|---|---|
| SIDEARM / pistol (9MM) | `"pistol"` (`STATE.current_weapon`) | `content/meshes/pistol.mesh.json` via `ui/mp3d.py pistol_mesh`; `GRIPS["pistol"]` | `entities/weapon_rig.py draw_pistol` (`RIGS["pistol"]`, fallback rig); kind `box` | `entities/weapons.py` (reload 60 frames; `STATE.ammo_in_mag/mag_size/spare_mags`) | M1-M6 2D, MP arena |
| K-9 SMG (9MM-S) | `"k9_smg"`; rig key `"k9"` | `content/meshes/k93d.mesh.json` (`tools/ae_import_k93d.py`), loaded in `m6/train3d.py`, `m6/yard3d.py`, `ui/mp3d.py`; `m6world3d._k9_rig_mesh`; `GRIPS["k9"]` | `weapon_rig.draw_k9`; kind `stick` -> `game/art/m5/mag_icon.py` v0-2 | `entities/weapons.py` (reload 72, `k9_*` attrs); `m6/yard3d.py` `MAG, RESERVE = 30, 150`, `RELOAD_S = 1.6`; `RELOAD_MS["k9_smg"]=72` | M5/M6 2D, M6 yard/train 3D |
| OS-12 | `"os12"` (2D + 3D flag) | `engine3d/rig.py os12_mesh`; flag `"os12"` in `m6world3d.hum`; `GRIPS["os12"]` (= rifle grips + stock butt) | `weapon_rig.draw_os12`; kind `stick` | `entities/weapons.py` (reload 90, `os12_*` attrs); `m8/revenge/trap3d.py WPN_SPECS["rifle"]` (mag 30, reload 1.45 s); `RELOAD_MS["os12"]=90` | M2 (`grant_seby_os12`) on, M8 trap (`weapon == "rifle"`), allies/guards in films |
| FALLOW 12 (12GA shotgun) | `"shotgun"` (3D rig/flag, trap `self.weapon`), `"fallow12"` (HUD `cw`) | `engine3d/rig.py shotgun_mesh` (`spec["rifle"]="shotgun"` or flag `"shotgun"`; `+"nopump"` = no fore-end, pump drawn by `shotgun_pump_mesh` in raid3d/trap3d); `GRIPS["shotgun"]` | `weapon_rig.draw_shotgun` (`RIGS["shotgun"]`); kind `shell` -> `m6/draw._draw_fallow_icon` (procedural); `mag_icon.py` v6-8 baked shell | `m7/raid3d.py` `MAG=6`, `RESERVE0=24`, `RESERVE_CAP=36`, `RELOAD_S=2.2`, `PELLETS=8`, `FIRE_GAP`; `trap3d.WPN_SPECS["shotgun"]`; `RELOAD_MS["fallow12"]=132` | M7 raid, M8 trap |
| M7 allies' rifle | `"m7rifle"` | `content/meshes/m7rifle.mesh.json` (`tools/ae_import_m7rifle.py`) via `m6world3d._m7rifle_mesh`; `GRIPS["m7rifle"]` | none | - | `("ally", who)` actors without `os12` flag (Alex etc.); NOT the player's gun |
| Guard rifle (AK) | `"akrifle"` | `content/meshes/akrifle.mesh.json` (`tools/ae_import_akrifle.py`) via `cast3d.rifle_asset` / `third_person_rifle`; `GRIPS["akrifle"]` | 2D enemies: procedural line gun in `entities/enemy_ai.py` | enemy AI per mission | default 3D guard (`key == "guard"` without `os12`), M3 KO film |
| AK-74 | `"ak74"` | `content/meshes/ak74.mesh.json` (`tools/ae_build_ak74.py`) via `cast3d.ak74_asset`; flag `"ak74"`; `GRIPS["ak74"]` | none | - | Biribel/cast films flagged `ak74` |
| Generic rig rifle / sniper | `"rifle"`, `"sniper"` | `engine3d/rig.py rifle_mesh` (`scope=True` for sniper); `GRIPS["rifle"/"sniper"]` | - | `missions/m2/sniper.py`, `sniper3d.py` | Ucilev (`rifle="sniper"`), M2 nest |
| Imported sniper rifle (suppressed bolt-action) | `"sniper_rifle"` (film flag/rig key) | `content/meshes/sniper_rifle.mesh.json` (`tools/ae_import_sniper.py`, bakes `assets/3D/lowpoly_sniper_rifle.glb`) via `cast3d.weapon_asset`; `m6world3d.hum(flags=("sniper_rifle",))` sets `_rifle/_weapon/_muzzle_z/_gl_spec_key`, procedural `rifle_mesh(scope=True)` fallback; `GRIPS["sniper_rifle"]` (mirrors mesh meta `butt/guard/fore`) | none | `cutscenes/m8dutyfilms._crash_actors`: world-space `_draw_sniper_world` handoff pinned to live `rhand`/fore via `hold_cached(..., "ready")` and `_interp_rot` | M8 Duty crash films (`crash_fire`/`crash_promise`/`crash_better`) |
| LMG | `"lmg"`; hold cache key `"m8lmg"` | `content/meshes/lmg.mesh.json` (`tools/ae_import_lmg.py`) via `m6world3d._gun_mesh("lmg")`; `GRIPS["lmg"]` | none; HUD text `"LMG %d / %d"` in `chase3d.py` | `m8/revenge/chase3d.py` `GUN="lmg"`, `MAG=100`, `RELOAD_S=4.2` | M8 tractor chase |
| TACTICAL LMG (Duty door gun) | `"tactical_lmg"` | `content/meshes/tactical_lmg.mesh.json` (`tools/ae_import_duty_props.py`) via `cutscenes/m8dutyfilms._tactical_lmg` | none; flight HUD text | `m8/duty/flight3d.py` | M8 Duty Last Flight (door gunner) + Duty films |
| Duty loadout (OS-12 + FALLOW 12) | `"rifle"` (label OS-12, `5.56X45`, stick, mag 30) / `"shotgun"` (FALLOW 12, `12GA`, shell, mag 6) | `hum(flags=("shotgun","nopump"))` as in raid3d | `yard_hud.weapon` via `mansion_hud` | `m8/duty/mansion3d.py` `WPN_SPECS`, `WPN_ORDER` | M8 Duty mansion fight; same keys as `trap3d` `WPN_SPECS` (`"rifle"`, `"shotgun"`), separate stats |
| Molotov / bottle | `STATE` bottles; `handle_throw_bottle` | `content/meshes/molotov.mesh.json` in `missions/m1/draw3d.py` | `engine/ui/std/bottle_hud.py`; icon `game/art/m1/molotov_icon.py` | `entities/weapons.py` `handle_throw_bottle` `spawn_molotov_fire` `update_molotovs` `FireZone` | M1, M2 |
| Chair leg / shiv (melee) | `STATE.mission3_weapon` `"chair_leg"`/`"shiv"` | - | `game/art/m3/weapon_icon.py` | `entities/weapons.py handle_melee` (timer/damage table) | M3 breakout |
| Vehicles 3D | `truck_m7` `tractor_m7` `krap_van` `m3_van` `car_m2` | `content/meshes/*.mesh.json` (`tools/ae_import_{truck,tractor,krap_van,m3_van,car}.py`); `raid_world.truck()` | 2D: `spr_vehicles` via `core/artpack.vehicle(key)` | `m8/revenge/chase3d.py` (`HULL`, `SPEED`) | M7 raid, M8 chase/trap |

Weapon switching 2D: `entities/weapons.py switch_weapon` (pistol<->k9_smg or pistol<->os12). 3D trap: `trap3d._switch_weapon` (shotgun<->rifle, `[Q]`). Duty mansion: `mansion3d._switch_weapon` reuses `trap3d.SWAP_S`/`T._swap_pose`/`R.SG_BLADE_YAW` blending (draw_weapon switches at `swap_u >= 0.5`, `_swap_snd_at` fires `rifle_handle` mid-swap).

## 6. One-shot file bundles (task -> exact files)

Edit = change; Check = shared callers to keep working; Verify = command. Paths are grouped by folder: `engine/ ui/ core/ game/ entities/ audio/ cutscenes/ engine3d/ mN/ content/` = `src/<path>` (short forms in the header); `tools/ assets/ docs/` = repo root. Add the filename(s) after each folder prefix.

**2D HUD widget (health/hostiles/objective/minimap/prompt)**
- Edit: `engine/ui/std/` `<widget>.py`; `content/strings/` `en.json`.
- Check: `ui/` `hud.py`, `arena_view.py`; `m{1..6}/` `draw.py`; `m3/` `systems.py`; `m6/` `yard_hud.py`; `m0/` `__init__.py`.
- Verify: `python tools/ae_api_snapshot.py check` (if signature/`__all__` changed), `python tools/ae_text_check.py`, `python tools/smoke_test.py --fast`.

**2D/3D weapon panel or mag icons (any mission)**
- Edit: `engine/ui/std/` `weapon_panel.py` (layout, `RELOAD_MS`, `WeaponInfo`); `m6/` `draw.py` (`_panel_mag_icon`, `_draw_fallow_icon`, `_draw_mag_icon`), `yard_hud.py` (`weapon`); `game/art/m5/` `mag_icon.py` (baked shells).
- Per-mission label/kind: `m7/` `raid_hud.py`; `m8/revenge/` `trap_hud.py`; `m6/` `yard3d.py`, `train3d.py`.
- Check: `m3/` `systems.py` `_draw_m3_mag_icon`; `m4/` `draw.py` `_draw_m4_mag_icon`; `m5/` `draw.py` `_draw_m5_mag_icon`; `game/art/m4/` `mag_icon.py` - all receive the 7-arg callback.
- Rebake after art edit: `python tools/ae_bake.py --pack m5` (m4: `--pack m4`). Verify: `python tools/ae_bake.py --pack m5 --check`, `python tools/ae_text_check.py`, `python tools/smoke_test.py --only m6,m7,m8`.

**3D gameplay weapon stats / reload / firing**
- Edit: `m7/` `raid3d.py` (module constants + `RaidScene`); `m8/revenge/` `trap3d.py` (`WPN_SPECS`, `_switch_weapon`, `_sync_weapon_attrs`, `BORE_LOCAL`), `chase3d.py`; `m8/duty/` `mansion3d.py` (`_switch_weapon`, `_sync_weapon_attrs`, `_begin_reload`), `flight3d.py`, `ridge3d.py`; `m6/` `yard3d.py`, `train3d.py`.
- Check: changing a `RaidScene` method changes `TrapScene` and the Duty scenes (4.3); `m7/` `raid_hud.py`, `m8/revenge/` `trap_hud.py` HUD `reload_ms` literals must match `RELOAD_MS` intent.
- Verify: `python tools/smoke_test.py --only m7,m8` (or `m6_train`).

**2D weapon / enemy AI**
- Edit: `entities/` `weapons.py`, `weapon_rig.py` (`RIGS`), `enemy_ai.py` (`Enemy`, `enemy_hear_shot`), `player.py`; `m0/` `__init__.py`; mission `world.py`/`systems.py`.
- Check: `engine/ui/std/` `weapon_panel.py` `WeaponInfo.from_state` (STATE attr names); `ui/` `arena_view.py` `rig_for_weapon` (MP).
- Verify: `python tools/smoke_test.py --fast`.

**3D character pose / hold / gun on body**
- Edit: `engine3d/` `hold.py` (`GRIPS`, `MODES`), `rig.py` (`POSES`, gun meshes, `Humanoid`); `cutscenes/` `m6world3d.py` (`hum` flags), `cast3d.py` (`spec3d`, `weapon_asset`).
- Look: `engine/anim/` `figure_kit.py` `SPECS` (also drives 2D cutscenes and `tools/sprites/portraits.py`; rerun portraits after a look change). Keep the blocky box look.
- Verify: `python tools/ae_hold_check.py`, `python tools/engine3d_check.py`, `python -m pytest tests/unit/test_faces3d.py`, `python tools/cast_sheet.py` (visual).

**Baked art / sprite sheets**
- Pack art: `game/art/mN/` `<asset>.py` + `content/mN/` `manifest.json` -> `python tools/ae_bake.py --pack mN`; commit `assets/baked/mN/*`.
- Sheet art: `tools/sprites/` `<family>.py` (+ `palette.py`, `kit.py`) -> `python tools/build_all_sprites.py`; commit `assets/art/spr_*.png` + `.json`.
- 3D meshes: `tools/ae_import_*.py` -> `content/meshes/<id>.mesh.json` - full sources/consumers in §8.
- Verify: `python tools/ae_bake.py --check`, `python tools/smoke_test.py --only sprite_pipeline`.

**Cutscene / timeline**
- 2D: `content/timelines/` `<id>.timeline.json`; `cutscenes/` `<mission file>.py`; `mN/` `meta.py` or root `app.py`. Tool: `tools/` `ae_timeline_edit.py`.
- THE CALL trailer v2 tooling overhaul (2026-11-24; `tools/trailer_call/`, no `src/` changes): new native-resolution `hud.py` (1920x804 tactical panels, recoil/hitmarker crosshair, anti-aliased PSO-1 mask/bezel/reticle and `composite_pso1_scope`); `scenes.py` rebuilt with the beige lamp-square fix (`W6.terrain(lights=False)` + soft pools), charred WIN_LIT masks and warm-underlit smoke, red chest IFF-dot removal, hedge-clear moonlit estate, `FFX.tactical_lmg_mesh`, collapsed burnt truck chassis, dynamic red/blue strobes, four real gameplay sequences (`gp_mansion_ots`, `gp_chase_lmg`, `gp_door_gunner`, `gp_checkpoint_ots`), eight brand-new flash shots + `climax_surge`, and dual-pass `render_scope_passes`; `render.py` adds TPDF-dithered filmic grade with shadow toe, multiplicative fades, native-HUD gameplay shots, the PSO scope shot, a clean CTA title card and `FLASH_HITS` restricted to live-action drops; `score.py` adds sidechain ducking plus diegetic foley recipes (fire crackle, snow/wet footsteps, two-tone siren, ricochet, shotgun + pump, spark zap, sniper crack into the title sub-drop); `vertical.py` synced to 43.2 s / 18 bars with the new scene names and CTA. The three known in-game bug sites (`m6world3d` lamp quads, `m7world3d` WIN_LIT, `chase_set` static lightbar) are documented only, not modified.
- THE CALL trailer visual/audio polish pass (2026-11-24; `src/engine/render3d/vehicle_destruction.py` + `tools/trailer_call/{scenes,render,score}.py`): `_build_wreck_core_mesh` replaces the giant emissive amber bed plate with charred steel, a soot sheet and small recessed ember cracks (same public API, also benefits in-game wrecks). `scenes.py` adds `_s3_frame` (no harsh stratus sky line), `_toll_sign_mesh` (blocky white "ROUTE 12 - VAMA" on the gantry) and `_flat_dead_pose` (flattened ankles, no vertical boots); separates patrol/roadblock sightlines, darkens the estate to five warm rooms, builds explicit billowing smoke plumes at the barn, moves vehicles onto clear stretches, adds jeep swerve/roll/impact sparks/fire in `gp_chase_lmg`, cover-crouched guards at the checkpoint, a single-IK `flash_01`, door-breach `flash_02`, front-3/4 `flash_04`, a non-repeating `climax_surge` beat 2 and a walking/scanning scope sentry with lag-tracked aim. `render.py` drops estate_gate expo 0.92 -> 0.80; `score.py` removes the sine-sweep ricochet chirp, adds four rifle + four LMG + three impact takes, distance-appropriate footstep modes, a -16.5 dB low-passed consonant siren, warmer fire and a -1.8 dB upper-mid duck over the climax montage. Gates: compileall, normalize, api snapshot +0/-0, smoke `--only m8`, `sync_arch_map --check` OK; `check_boundaries` still the documented E4 x2 / W1 89 baseline.
- THE CALL trailer placement/combat correctness pass (2026-11-25; `tools/trailer_call/scenes.py` only): `_open_s3_pos` snaps guards to the nearest clear 3x3 `.` tile away from booths, barriers, CARS, SANDBAGS and TANKER; `convoy_boom` truck moved to `(-32, 0, 10.5)` clear of `CARS[1]`; `ember_barn` guard 2 moved off the courtyard well. `city_hover` drops the camera-tethered yellow laser for fixed-world flak and short ballistic tracer bolts from forward-only gunners plus AA fire toward the burst. `rocket_streak` now flies a quadratic Bezier intercept from `t_launch=0.10` to `t_hit=1.62`, with the gunship evading + four timed decoy flares, the lead flare consumed in a 3D fireball/flak blast, blast light and camera jolt, and `SHOT_EVENTS` updated (flare 0.82/1.02/1.22, explosion 1.62). `flash_08` replaced by a Broadcast Plaza night strike (lit colonnade, exploding AA truck, banking gunship) with rotor/explosion events. Gates: compileall, normalize, `render.py --at` on 29.8/52.0/54.4/61.1/61.75/71.55 OK, `--sheet` 31/31 OK, `sync_arch_map --check` OK.
- M8 Revenge kill hijack cinematography (2026-11-25; new `missions/m8/revenge/kill_cine.py` + `kill3d.py`): the post-trigger assassination now cuts through `impact` / `grate` / `walkup` / `finisher` / `witness` on chest and groin branches, headshot drops straight to `witness`, and hesitation hands off to `bodi`; every branch ends on the shot name `"witness"` so `check_mission8_vertical_slice` (which asserts `shot == "witness"` and `shots == 1`) exercises all cuts with no scene switch or renderer reload. `kill_cine` owns branch tracks with limb lag, impact micro-slowmo, Biribel's Fallow 12 pump-rack walk-up via `engine.anim` gait/mask poses, a finisher camera locked to Vasile's live `pose_world()["head"]`, Bodi's upward OS-12 hold and reduced-motion-aware drift; `kill3d` delegates performance/camera/faces to it and adds `_lights`, `_play_single`, `_trigger_finisher` and `_draw_bodi`. Lifecycle and `on_kill_done("shot")` unchanged.
- M8 Revenge kill-cut framing & input lock (2026-11-25; `kill_cine.py` + `kill3d.py`): MOUSEMOTION and the reticle are now gated on `can_fire()` so Biribel cannot swivel during Vasile's Maru speech; `AIM_YAW` 16 -> 12, `AIM_PITCH` 24 -> 20 and his root swivel damped to `0.35 * yaw_off`. Camera angles re-shot from `_shots/kill3d_cine_check.png`: `grate` tracks Vasile's live head joint for headroom, `walkup` sits south of the catwalk above the handrail for an unobstructed pump-rack two-shot, `finisher` backs off 14 cm, `bodi` pulls back to a low-wide muzzle-connected framing, `impact` gets a longer slow-mo flash window. All branches still end on `"witness"`.
- 3D films: `cutscenes/` `m6films.py`, `m7films.py`, `m8films.py`, `m8dutyfilms.py`; `m8/` `meta.py` `M8_SCENES`.
- Verify: `python tools/ae_timeline_check.py`, `python tools/smoke_test.py --only <mission>`.

**Mission complete screen**
- Edit: `ui/` `mission_complete.py` (dossier layout, buttons), `mission_complete_3d.py` (per-mission diorama); `content/strings/` `en.json`; `core/` `mission_meta.py` (titles).
- Check: root `app.py` `_MissionCompleteState` (imports `ui.mission_complete` inside methods: AST rule in §7); `core/` `save_system.py` `save_mission_complete`.
- Verify: `python -m pytest tests/unit/test_mission_complete_ui.py`, `python tools/preview_mission_complete.py` (visual), `python tools/ae_text_check.py`.

**M8 Duty route (mansion / flight / ridge)**
- Edit: `m8/duty/` `mansion3d.py` + `mansion_set.py`, `mansion_world.py`, `mansion_brain.py`, `mansion_hud.py`; `flight3d.py`; `ridge3d.py`; films `cutscenes/` `m8dutyfilms.py`; ladder `m8/` `meta.py` (`DUTY_STAGES`, `STAGE_LABELS`, `M8_SCENES` `m8d_*`), `flow.py`, `systems.py`.
- Check: borrowed `RaidScene`/`TrapScene` methods (4.3); `m8/revenge/` `epilogue3d.py` (funeral house shared with `mansion_set`), `chase_set.py` (helicopter); `ui/` `mission_failed.py` `checkpoint_label`.
- Andrei M.'s death: beat times `ANDREI_SHOT_S`/`ANDREI_HIT_S`/`ANDREI_ZAP_S` live in `mansion_brain.py` (`_andrei_update`: tracer, `on_andrei_rack_hit`, zap sparks, banter); `andrei_timings("player")` uses `(1.50, 2.95, 3.55, 4.15)` and `trigger_andrei_death` records `shot_yaw`/`had_gun`/`shot_pos`. `mansion3d._andrei_death_anim(age, cause, hit_zone, shot_yaw, had_gun)` keys the pose to them (shot -> eased turn to 90 + single-jolt/4-stride backpedal over `ANDREI_RACK_DX` into the middle `ANDREI_RACK_AT` rack -> pinned shake -> slides down to a legs-flat sit at `ANDREI_SIT_S` -> tips onto his side on the floor by `ANDREI_DOWN_S`; rig auto-grounds the lowest vertex, so bent knees would hold his seat off the floor). `_draw_andrei` keeps the pistol in hand until the impact (braced `_held` in intro, forearm-aligned on misfire), then `_dropped_pistol_xform()` drops it ballistically to rest on `GF + 0.032`; blood/char decals use `hum.pose_world()` slots S/H, and floor puddles are player-shot only.
- Verify: `python tools/smoke_test.py --only m8`; play via `--dev-mission8-duty`, `-mansion` (`--m8-cp=0..4`, also `-hall`/`-study`/`-helipad`), `-liftoff`, `-flight` (`--m8-cp=0..4`, also `-flight-road`/`-flight-tail`/`-flight-ucilev`), `-crash`, `-ridge`, `-duty-epilogue`. Full target list: `python acaristan.py --list-jumps`; generated table in `docs/FILE_INDEX.md` §12. Plot: `docs/` `MISSION8_PLOT.md`.

**UI strings / menus**
- Edit: `content/strings/` `en.json`; callers `T("...")` in `ui/` `*.py` or `engine/ui/std/` `*.py`. Menus `ui/` `main.py`; settings/pause `system.py`; layout helpers `kit.py`.
- Verify: `python tools/ae_text_check.py` (fit + placeholders).

**Mission stage / checkpoint**
- Edit: `mN/` `flow.py` (stage + `set_slot_progress`), `meta.py`; `core/` `game_core.py` (`start_missionN_*`), `dev_jumps.py` `DEV_JUMPS`; root `app.py` `_SlotSelectState` resume table (+ `M*_RESUME` after-states).
- Check: `ui/` `mission_failed.py` `checkpoint_label`; `core/` `mission_meta.py`.
- Verify: `python tools/smoke_test.py --only mN`, `python -m compileall -q src`.

**New spoken line**: `audio/` `voice_manifest.py` (row + `KNOWN_MISSING_AUDIO`); caller text in `content/timelines/`, `content/dialogue/` or `mN/` `flow.py`. Canon: `docs/` `LORE.md`, `MISSION*_PLOT.md`.

**Blank-speaker cutscene narration / late-registered VO lines**
- Edit: `app.py` `_CutsceneState.update` (blank `speaker` -> `voice.find_line("NARRATOR", ...)` -> `play_line("NARRATOR", ...)`; `scene == "title_card"` excluded); `audio/` `voice_manifest.py` `VO_456..VO_482` (14 Narrator + 13 M0/M4/M7/M8 character lines in `VOICE_LINES` + `KNOWN_MISSING_AUDIO`, never `VOICE_ORDER`).
- Check: `audio/voice.py` `find_line`/`_norm`; timeline/dialogue text must normalize to the manifest row or no take plays. Non-narrator system text and title cards stay silent.
- Verify: `python tools/voice_audit.py --check`, `python tools/smoke_test.py --fast`, `python tools/vo_batch.py status` (481 lines / 178 recorded / 303 missing).

**VO batch recording / auto-splitting (AI Studio, no CUDA/PyTorch)**
- Edit: `tools/` `vo_batch.py` (`GROUP_SPECS`, `SPEAKER_TO_GROUP` incl. `NARRATOR`, `PAUSE_RULE`, `status`/`make-refs`/`pack --redo-bodi`/`split`/`sync-manifest`); `audio/` `voice_manifest.py` (`KNOWN_MISSING_AUDIO` only, never `VOICE_LINES`/`VOICE_ORDER`).
- Check: `audio/` `voice.py` (`_speech_units`, `_scan_files`, `has_file`, `_files`); `tools/` `build_radio_cache.py`, `voice_audit.py`. Flow: `build/vo_batches/refs/<SPEAKER>_ref.wav` (replication refs) + `build/vo_batches/scripts/<GROUP>_NN.txt` -> downloaded WAV in `build/vo_batches/audio/<BATCH_ID>.wav` -> `assets/voice/<Speaker>/VO_xxx.ogg` (`.wav` fallback without ffmpeg; pygame decode fallback for source files).
- Verify: `python -m compileall -q tools/vo_batch.py`, `python tools/ae_normalize.py --changed`, `python tools/vo_batch.py make-refs`, `python tools/vo_batch.py pack --redo-bodi`, `python tools/vo_batch.py status`, `python tools/vo_batch.py split --dry-run`, `python tools/voice_audit.py --check`, `python tools/smoke_test.py --only voice`.

**Colab Qwen3-TTS pipeline (free T4 GPU, voice cloning + VoiceDesign)**
- Edit: `tools/` `vo_batch.py` (`colab-pack`/`colab-import`, `DESIGN_ANCHORS`, `BAKED_SCREAMS`, `_build_existing_ref`); `tools/` `vo_colab_qwen3.ipynb` (5 cells: GPU/pip check, kit upload, VoiceDesign anchors, clone generation with resumable backup zip, download).
- Check: `build/vo_colab_kit.zip` holds `jobs.json` + `refs/<GROUP>.wav` (currently 8 `clone_existing` groups built from clean takes with exact transcripts, 14 `design` groups with `instruct`/`anchor_text`; 303 jobs). `colab-import` maps `VO_xxx.wav` from `vo_generated.zip` through `_group_for`/`_folder_and_style`, trims via `_find_islands`, writes `.ogg`/`.wav`, then auto-runs `cmd_sync_manifest` unless `--no-sync`.
- Verify: `python -m json.tool tools/vo_colab_qwen3.ipynb`, `python tools/vo_batch.py colab-pack`; after Colab: `python tools/vo_batch.py colab-import <zip>`, `python tools/build_radio_cache.py`, `python tools/voice_audit.py --check`, `python tools/smoke_test.py --only voice`.

**AI Studio unrenamed-drop ingest**
- Edit: `tools/` `vo_batch.py` `cmd_ingest` + `ingest` parser (`--start`, `--align`, `--dry-run`, `--keep`, `--format`, `--no-sync`); `build/missing_lines.txt`/`.csv` are the owner's exported checklist (generated artifacts, not tracked code).
- Check: `audio/voice.py` `_file_order_key` (timestamp in filename, `(1)`/`(2)` copy order), `_duration`, `_align`, `_speech_units`; `cmd_ingest` filters by speaker/group, matches files oldest-first to that speaker's missing IDs, flags duration outliers `[CHECK]`, and moves consumed downloads to `<drop>/_done/<VO_ID>__<name>` unless `--keep`.
- Verify: `python tools/vo_batch.py ingest NARRATOR build/vo_drop/NARRATOR --dry-run`, then without `--dry-run`, `python tools/build_radio_cache.py`, `python tools/voice_audit.py --check`.

## 7. Gotchas & gates per subsystem

**Inventory / pickups** - in every 2D mission a pickup at full (bandage at full HP, mag with full pouches, molotov at cap) stays on the ground; M1/M2 hotwire "not yet" uses its own flag so an early `[E]` does not eat Vasile's tutorial line. Never consume a pickup the player cannot use.

**Art bake precedence**
- `AssetRegistry.get` loads the baked PNG before calling `render()`. Editing `src/game/art/mN/*.py` changes nothing in-game until `python tools/ae_bake.py --pack mN` rewrites `assets/baked/mN/`. `tools/build_all_sprites.py` rebakes only m5.
- `--check` fails on stale hashes; commit baked PNGs with the generator change.
- `game/content/m5/manifest.json` declares `m5/mag_icon` with `"variants": 6`, while `mag_icon.py` has `VARIANTS = 9` and `assets/baked/m5/` holds `mag_icon_0..8.png` (shell = 6-8). Check bake output count after edits.

**Callback contract**: `weapon_panel.draw(..., mag_icon=fn)` calls `fn(surface, mx, my, kind, rounds, cap, active)`: exactly 7 positional args, kinds `"stick"`/`"box"`/`"shell"`, 4 slots at `x+14+i*34`. Extra args (`reload_prog`, `incoming`) go through a closure (`yard_hud.weapon._icon`). Implementations: `m3/systems._draw_m3_mag_icon`, `m4/draw._draw_m4_mag_icon`, `m5/draw._draw_m5_mag_icon`, `m6/draw._panel_mag_icon`.

**Engine API**: any change to a `src/engine/**` public name or signature -> `python tools/ae_api_snapshot.py record` and commit `tests/api/engine_api.json`; `check` runs in `tools/ae_ci.py`. Every engine module needs `__all__`. Boundary: `python tools/check_boundaries.py` (engine never imports game code).

**Strings**: every static `T("key")` must exist in `en.json`; placeholders must match kwargs; values must fit their widget slot. Gate: `python tools/ae_text_check.py` (`--strict` fails unused keys).

**`_GameState_` AST rule**: `tools/m5_finale_cut_check.py` and `tools/m5_shadow_check.py` exec only the `_GameState_`/`_MissionCompleteState` class bodies from `src/app.py`. Helpers called from those methods must be on the class or imported inside the function, never new module-level functions. Their stand-in `audio` namespaces (`m5_shadow_check` `aud=`, and `tools/smoke_test.py::check_mission4_cinematic_arrest`'s `"audio": SimpleNamespace(...)`) must mirror every `audio.*` call those bodies make: they carry inert `fade_out_music`/`play_music`/`music_name` stubs for `_CutsceneState`'s music-bed handover (a new `audio.<method>()` call there needs the stub, or both checks die with `AttributeError`); cue assertions stay exact because the stubs record nothing.

**Shared mutable state**: read rebound globals as `import <owner> as _o; _o.name`, never `from owner import name` (AGENTS.md).

**HUD naming traps**: `WeaponInfo.from_state` never yields the shotgun; the 3D HUDs pass `cw="fallow12"`. OS-12 caliber is `"12GA"` in `from_state` but `"5.56X45"` in M8 `trap_hud`/`WPN_SPECS`. `RELOAD_MS` keys are HUD ids (`k9_smg`, `os12`, `fallow12`), not rig keys (`k9`, `shotgun`).

**3D**: never bypass `train3d._renderer()`/`buffer_size()` in M6 scenes; `ACA_M6_AUTO` stays opt-in; no per-frame allocation. `ACA_TD_2D=1` / `ACA_MP_2D=1` force 2D views.

**2.5D frame cost**: hosts that `buf.fill(VOID)` and draw nothing into `buf` before the flush call `r.flush(buf, bg=VOID)`, so GL clears the FBO instead of uploading the buffer (~4 ms with the upload sync; software ignores `bg`). M6 paints snow into `buf` first, so it must not pass `bg`. `td.put` caches packed placements per `(mesh, pos, yaw, roll, pitch)`; GL sun shadows: `GLRenderer._sun_pass` redraws all queued geometry into a 2048 depth map (`_SH_UNIT` 6, ortho `u_ortho` in `project`, `u_sh_pass` depth-only, emissive faces skipped), dynamic rows are uploaded once per `_render` (`_draw_dyn(upload=False)` in the colour pass); only sun-facing faces receive (`nl > 0`), so camera-facing walls and fronts keep the key light. Software fallback: `td.cast_shadows` draws one sprite with an exact `bounds` box and `strict_occ=True` (without it the composite's <=12 % shortcut paints shadows over guards). Budget on a quiet PC: M1 render ~10 ms, locked 60 fps. Before trusting a slow timing, check for background CPU/GPU load; a uniform 2-5x slowdown across all sections is the machine, not the code.

**3D asset wiring**: 4 `assets/3D/*.glb` are read at runtime with no bake (§8.1 `R`): `m8/revenge/chase_set.py` `_load_heli_raw()`/`_load_rocket_raw()` -> `_load_glb()`, the same reader's `return_paths=True` mode for `maru_gunship_parts()` (per-node paths let one GLB be split into fuselage / tail boom / main rotor / tail rotor), `cutscenes/m7world3d.py` `_scrambler_asset()` -> `_load_glb_surface()`; a missing GLB silently degrades to procedural geometry. `pig.mesh.json` is baked but unwired (live pig = procedural `cutscenes/m7pig3d.py`). `tools/ae_import_check.py` is an import-side-effect checker, not a mesh importer.

**Time**: gameplay/UI/draw read `engine.core.now_ms()`/`now_s()` only.

**Line endings**: LF/UTF-8 no BOM; scripted edits on Windows can write CRLF -> `python tools/ae_normalize.py --changed`.

**Gates**
- Fast loop: `python -m compileall -q src`, `python tools/smoke_test.py --only <area>` (`--list` names slow checks).
- Handoff: `python tools/smoke_test.py --fast` (full run for MP/sprites/M4 siege) -> `SMOKE TEST: OK`.
- Engine/data/API: `python tools/ae_ci.py --quick` or full `python tools/ae_ci.py` -> `AE CI: OK` (`d6` currently fails on pre-existing M1/M3/M4 direct-draw counts above ratchet baseline: `313/306`, `1921/1912`, `439/399`; all other quick gates and full `smoke_test.py` pass).
- Content: `tools/ae_bake.py --check`, `tools/ae_text_check.py`, `tools/ae_timeline_check.py`, `tools/ae_dialogue_check.py`, `tools/ae_level_check.py`, `tools/ae_set3d_check.py`, `tools/ae_hold_check.py`.

## 8. 3D assets inventory (disk-verified)

Aliases: `A/` = `assets/3D/`, `M/` = `src/game/content/meshes/`, `C/` = `src/game/content/`, `T/` = `tools/`, `WP` = `T/ae_import_workstation_props.py`. Status: **B** baked via importer -> `M/<id>.mesh.json` (or `.rig.json`); **R** GLB/PNG read directly at runtime (no bake); **S** source-only / unimported. `A/` is flat (no subdirectories): 40 files = 35 `.glb`, 2 `.png`, 1 `.blend`, 1 `.blend1`, 1 stray `.pdf`. `M/` = 24 `.mesh.json` + 1 `.rig.json`. Baked ids below are the `M/` file stems.

### 8.1 `A/` - every source file + status
| `A/` file | St | Importer / caller -> baked id |
|---|---|---|
| `IPA-army-truck.glb` | B | `T/ae_import_truck.py` -> `M/truck_m7` |
| `K93D.glb` | B | `T/ae_import_k93d.py` -> `k93d` (+ emits `K93D_reticle.png`) |
| `K93D_reticle.png` | R | emitted by `T/ae_import_k93d.py`; loaded by `m6/train3d.py` `_reticle_image()` |
| `M3van.glb` | B | `T/ae_import_m3_van.py` -> `m3_van` |
| `M7Rifle.glb` | B | `T/ae_import_m7rifle.py` -> `m7rifle` |
| `Suppressed_Pistol.glb` | B | `T/ae_import_duty_props.py` -> `M/suppressed_pistol` (unwired) |
| `TractorM7.glb` | B | `T/ae_import_tractor.py` -> `tractor_m7` |
| `ak-style-rifle.glb` | B | `T/ae_import_akrifle.py` -> `akrifle`; source-space ref for `T/ae_export_ak74_glb.py` |
| `ak74-style-rifle.glb` | S | export artifact of `T/ae_export_ak74_glb.py`; `ak74` is code-built by `T/ae_build_ak74.py`, never imported |
| `army-helicopter-ipa.glb` | R | `m8/revenge/chase_set.py` `_load_heli_raw()` -> `_load_glb()`; no baked `army-helicopter-ipa` |
| `dawg.glb` | B | `T/ae_import_dog.py` -> `dog_m7.rig.json` |
| `farm-ammo-crate-bare.glb` | B | `T/ae_import_duty_props.py` -> `M/ammo_crate` |
| `hay.glb` | S | unimported, no runtime caller |
| `krap_van.glb` | B | `T/ae_import_krap_van.py` -> `krap_van` |
| `krap_van.png` | B | `T/ae_import_krap_van.py` reference image; baked mesh is `M/krap_van` (from `krap_van.glb`) |
| `light_machine_gun.glb` | B | `T/ae_import_lmg.py` -> `lmg` |
| `low-poly-car_green.glb` | B | `T/ae_import_car.py` -> `car_m2` |
| `low-poly-molotov.glb` | B | `T/ae_import_molotov.py` -> `molotov` |
| `low-poly-pill-bottle.glb` | B | `WP` -> `pill_bottle` |
| `low_poly_crt_monitor.glb` | B | `WP` -> `monitor_crt` |
| `low_poly_football.glb` | B | `T/ae_import_football.py` -> `football` |
| `low_poly_goal_post.glb` | B | `T/ae_import_football.py` -> `goal_post` |
| `low_poly_medkit.glb` | B | `WP` -> `medkit` |
| `low_poly_pig.glb` | B | `T/ae_import_pig.py` -> `pig` (no runtime consumer, §8.2) |
| `lowpoly-guy-dragan.glb` | S | unimported, no runtime caller |
| `lowpoly-missile-12s-black.glb` | R | `m8/revenge/chase_set.py` `_load_rocket_raw()` -> `_load_glb()`; no baked `lowpoly-missile-12s-black` |
| `lowpoly_retro_lcd_monitor.glb` | B | `WP` -> `monitor_lcd` |
| `lowpoly_sniper_rifle.glb` | B | `T/ae_import_sniper.py` -> `sniper_rifle` (+ meta `butt`/`guard`/`fore` mirrored in `engine3d.hold.GRIPS["sniper_rifle"]`) |
| `maru_gunship.glb` | R | `m8/revenge/chase_set.py` `maru_gunship_parts()` -> `_load_glb(..., return_paths=True)` split by root node (`heli_fuselage`/`heli_tail_boom`/`main_rotor`/`tail_rotor`) -> `put_maru_gunship()`; `maru_gunship_fpv_parts()` re-clips the same faces for the FPV path (drops pillars/mullions/pods, clips rear walls to `y<=1.04`, lights `avionics_*`) -> `put_maru_gunship(..., fpv=True)`; consumers `m8/duty/flight_fx.py` + `cutscenes/m8dutyfilms.py`; no bake (fallback = `flight_fx.cabin_mesh()`/`rotor_mesh()`) |
| `moneystack.glb` | B | `T/ae_import_duty_props.py` -> `M/moneystack` |
| `pistol_lowpoly.blend` | S | Blender source for `pistol_lowpoly.glb`; never imported |
| `pistol_lowpoly.blend1` | S | Blender backup (`.blend1`); never imported |
| `pistol_lowpoly.glb` | B | `T/ae_import_pistol.py` -> `pistol` |
| `scrambler125.glb` | R | `cutscenes/m7world3d.py` `_scrambler_asset()` -> `_load_glb_surface()`, used by `motorcycle()` |
| `soviet_pc_tall.glb` | B | `WP` -> `pc_tall` |
| `soviet_pc_zarya_pk86.glb` | B | `WP` -> `pc_zarya` |
| `tactical_lmg(white).glb` | B | `T/ae_import_duty_props.py` -> `M/tactical_lmg` |
| `telephone-base-balanced-jet.glb` | B | `T/ae_import_telephone.py` -> `telephone_base` |
| `telephone-handset-balanced-jet.glb` | B | `T/ae_import_telephone.py` -> `telephone_handset` |

`A/` also holds one stray non-3D file: `Evaluare Națională clasa a VIII-a - limba română - EN_VIII_2027_Limba_si_literatura_romana_var_model.pdf` (0 refs). `WP.ASSETS` bakes exactly 6 props: `pc_zarya`, `pc_tall`, `monitor_crt`, `monitor_lcd`, `medkit`, `pill_bottle`. Most `T/ae_import_*.py` reuse `T/ae_import_k93d.py`'s `_gltf/_scan/_cluster` GLB reader; `T/ae_import_mesh.py` is the generic `.glb/.gltf/.obj` -> `ae.mesh/1` entry; `T/ae_import_check.py` is a side-effect checker, not an importer.

### 8.1b GLB geometry specs (auto)

Generated by `tools/sync_arch_map.py` from each GLB's JSON chunk (no GLB inspection command needed). Rows stay out of §8.1 so `tools/map_assets3d.py` is unaffected.

<!-- AUTO:glb -->
| `A/` glb | tris | size WxHxD m | AABB centre x,y,z | min y | materials (name base colour) |
|---|---|---|---|---|---|
| `ak-style-rifle.glb` | 3032 | 5.99x2.18x0.51 | 0.00,1.09,-0.00 | 0.00 | mat0 #30353c, mat1 #181c22, mat2 #78401f, mat3 #492616 |
| `ak74-style-rifle.glb` | 6560 | 6.68x2.70x0.83 | -0.30,-0.58,0.14 | -1.93 | Gunmetal #303944, Dark steel #151b23, Polished steel #596370, Recesses and rubber #07090c, Wood #9b4723, Bakelite #713824 |
| `army-helicopter-ipa.glb` | 1348 | 10.38x3.47x11.55 | 0.00,1.74,-0.54 | -0.00 | MAT_Army_VertexColor -, MAT_Canopy_Glass #ffffff, MAT_IPA_Markings tex |
| `dawg.glb` | 321 | 1.15x3.28x3.89 | 0.00,1.64,0.45 | -0.00 | DarkFur #1e1e1e, TanFur #b87333, Collar #800000, Metal #cccccc, Eyes #ff3333, Teeth - skins=0 anims=4 |
| `farm-ammo-crate-bare.glb` | 1150 | 2.88x1.57x1.69 | 0.00,0.78,0.00 | -0.00 | mat0 #3f3524, mat1 #8b7150, mat2 #9a8260, mat3 #7d6547, mat4 #876f4f, mat5 #584631 (+6) |
| `hay.glb` | 4588 | 1.82x0.95x1.09 | 0.00,0.45,0.00 | -0.02 | mat0 tex, mat1 #655132, mat2 - |
| `IPA-army-truck.glb` | 17662 | 6.75x4.00x2.83 | 0.21,2.00,0.00 | 0.01 | mat0 #242923, mat1 #74796b, mat2 #171a18, mat3 #35412a, mat4 #53613a, mat5 #222622 (+10) |
| `K93D.glb` | 51786 | 0.29x1.24x3.03 | -0.01,-0.00,0.19 | -0.62 | Upper_Anodized_Alloy tex, Nitride_Barrel_Steel #1e242d, Machined_Titanium_Accent #475569, Lower_Carbon_Polymer tex, Magazine_Molded_Polymer #dbe2ec+tex, Stippled_Overmold_Grip #1a1e24 (+2) |
| `krap_van.glb` | 2978 | 7.18x4.40x3.15 | 0.15,2.20,0.00 | -0.00 | mat0 #5d6268, mat1 #404247, mat2 #51555a, mat3 #848a91, mat4 #323538, mat5 #5f889f (+6) skins=0 anims=1 |
| `light_machine_gun.glb` | 3424 | 6.82x2.66x1.68 | 0.27,0.09,0.00 | -1.24 | mat0 #363e46, mat1 #171d24, mat2 #59634a, mat3 #8c968e, mat4 #222722 |
| `low-poly-car_green.glb` | 1384 | 4.37x1.62x2.13 | -0.01,0.81,0.00 | 0.00 | mat0 #609785, mat1 #303743, mat2 #233c50, mat3 #c5d0d8, mat4 #fff2c8, mat5 #ffb33b (+3) |
| `low-poly-molotov.glb` | 422 | 1.55x4.17x1.15 | 0.21,2.16,0.00 | 0.08 | mat0 #376c36, mat1 #244c29, mat2 #998c76, mat3 #d8bc80, mat4 #704734, mat5 #d8cbb0 (+2) |
| `low-poly-pill-bottle.glb` | 324 | 1.51x3.46x1.32 | 0.00,0.02,0.01 | -1.72 | Bottle polymer #dcad6a, Screw cap #f7f5ef, Paper label #f7f5ef, Label ink #799f94 |
| `low_poly_crt_monitor.glb` | 354 | 5.20x5.64x5.15 | 0.00,2.87,0.02 | 0.05 | mat0 #d8cfc0, mat1 #c4b8a5, mat2 #3a3a3a, mat3 #0a2a1a, mat4 #ffffff, mat5 #cc3333 (+3) |
| `low_poly_football.glb` | 540 | 0.44x0.44x0.44 | 0.00,0.00,0.00 | -0.22 | Football_White #f4f6f8, Football_Black #1a1d24, Football_Seam #262b35 |
| `low_poly_goal_post.glb` | 1168 | 4.96x2.28x1.74 | 0.00,1.14,-0.79 | -0.00 | Goal_Paint_White #f8fafc, Goal_Steel_Silver #cbd5e1, Goal_Anchor_Dark #334155, Goal_Net_Cord #e2e8f0 |
| `low_poly_medkit.glb` | 160 | 3.65x3.08x1.50 | 0.00,0.21,0.00 | -1.33 | mat0 #d90429, mat1 #2b2d42, mat2 #edf2f4, mat3 #8d99ae |
| `low_poly_pig.glb` | 1010 | 3.89x2.34x1.83 | 0.17,1.16,0.02 | -0.00 | mat0 #f4a3b4, mat1 #e07b93, mat2 #6b4a2b, mat3 #f08aa0, mat4 #7a3445, mat5 #1a1a1a (+2) |
| `lowpoly-guy-dragan.glb` | 3200 | 0.68x1.89x0.44 | 0.00,0.94,0.05 | -0.00 | mat0 #345578, mat1 tex, mat2 #e6a189, mat3 -, mat4 #df8e7c, mat5 #f8fafc (+12) skins=0 anims=4 |
| `lowpoly-missile-12s-black.glb` | 672 | 0.28x0.28x1.81 | 0.00,0.00,0.00 | -0.14 | Mat_DarkMetal #2b303a, Mat_Warhead #1f232a, Mat_Body #262b33, Mat_Motor_Band #991b1b, Mat_HE_Band #f59e0b, Mat_Nose #111317 (+3) |
| `lowpoly_retro_lcd_monitor.glb` | 468 | 5.60x4.90x2.55 | 0.00,2.45,-0.35 | -0.00 | mat0 #cfcdc4, mat1 #1f2126, mat2 tex, mat3 #2a4a9a, mat4 #7d7f84, mat5 #a4a298 (+1) |
| `lowpoly_sniper_rifle.glb` | 1304 | 0.10x0.29x1.36 | 0.01,0.01,0.25 | -0.14 | Mat_Primary #b39870, Mat_Metal #3d3832, Mat_Bore #07080a, Mat_Secondary #342d26, Mat_Accent #cab28b, Mat_Lens #f59e0b |
| `M3van.glb` | 2906 | 3.10x3.44x5.65 | 0.00,1.76,0.01 | 0.04 | mat0 #465048, mat1 #222724, mat2 #343a36, mat3 #171a17, mat4 #315863, mat5 #fff0b5 (+3) |
| `M7Rifle.glb` | 3556 | 13.86x4.51x1.26 | 1.69,-1.03,0.18 | -3.29 | mat0 #4a4538, mat1 #0e0e10, mat2 #b39b6e, mat3 #1d1f22 |
| `maru_gunship.glb` | 3924 | 10.39x3.58x12.39 | 0.00,1.79,-0.75 | 0.00 | mat0 #222528, mat1 #343c32, mat2 #181a1d, mat3 #3f483b, mat4 #a6822c, mat5 #1c1e20 (+6) |
| `moneystack.glb` | 532 | 0.16x0.08x0.07 | 0.00,0.04,-0.00 | -0.00 | note #7a7870, edge #686662, ink #282a2e, ink_soft #565450, band #5e4226, seal #a48050 |
| `pistol_lowpoly.glb` | 2836 | 0.23x0.17x0.04 | -0.00,-0.02,0.00 | -0.10 | Pistol_Slide #353538, Pistol_Dark #0d0d0d, Pistol_Frame #3c3c3e, Pistol_Barrel #616163, Pistol_Dot #edede7, Pistol_Grip #242427 (+1) |
| `scrambler125.glb` | 3028 | 0.72x1.22x1.93 | 0.00,0.61,0.00 | 0.00 | Tire_Rubber #17181b, Silver_Alloy #9ea2a6, Frame_Black #18191c, Body_Orange #d2641c, Number_Plate #d6d0c0, Seat_Black #1d1e22 (+6) |
| `soviet_pc_tall.glb` | 3434 | 1.03x2.04x2.18 | 0.00,1.02,-0.00 | 0.00 | mat0 #d9d0b4, mat1 #b4aa8c, mat2 #161616, mat3 #cfcfcf, mat4 tex, mat5 #b3121b (+2) |
| `soviet_pc_zarya_pk86.glb` | 14854 | 0.46x0.16x0.45 | 0.00,0.08,0.01 | -0.00 | mat0 #111112, mat1 #34383a, mat2 tex, mat3 #0b0b0c, mat4 tex, mat5 #a6a8a8 (+30) |
| `Suppressed_Pistol.glb` | 51248 | 4.87x2.07x0.54 | 0.00,0.00,0.00 | -1.04 | Graphite satin metal #3b414a, Matte charcoal frame #242930, Satin edge accents #49515b, Dark cosmetic recesses #0c1015, Sight accent #c1c9bd, Textured graphite grip #151a20 (+2) |
| `tactical_lmg(white).glb` | 5292 | 13.41x3.91x1.76 | 0.95,-0.39,-0.01 | -2.35 | Receiver_Metal #9ca3af, Dark_Steel #374151, Bright_Steel #777e87, Grip_Rubber #121316, Tactical_Polymer #e5e7eb, Ammo_Brass #d4af37 (+1) |
| `telephone-base-balanced-jet.glb` | 1008 | 0.14x0.11x0.27 | 0.00,0.06,-0.04 | -0.00 | mat0 #1e2128, mat1 #121418, mat2 #d8dde6, mat3 tex, mat4 #d8dde6, mat5 #f3f6fa (+2) |
| `telephone-handset-balanced-jet.glb` | 428 | 0.15x0.23x0.23 | -0.01,-0.01,-0.00 | -0.12 | mat0 #1e2128, mat1 tex, mat2 #121418 |
| `TractorM7.glb` | 3840 | 2.73x2.87x4.15 | 0.00,1.43,-0.01 | -0.00 | mat0 #205b32, mat1 #328443, mat2 #479d4c, mat3 #354243, mat4 #667274, mat5 #fff3c7 (+5) |

AABB is in glTF space (Y up, +Z toward the viewer, right-handed) after node transforms, before any importer re-axis; `min y` is the grounding offset (0 = sits on y=0). Importers (`T/ae_import_*`) re-axis to engine3d (left-handed, +Z forward).
<!-- /AUTO:glb -->

### 8.2 `M/` - every baked file + where used
| `M/` file | source | used by |
|---|---|---|
| `ak74.mesh.json` | code `T/ae_build_ak74.py` (no GLB) | `cutscenes/cast3d.py` `weapon_asset`/`ak74_asset`/`third_person_rifle`; `m6world3d.py` `hum(flags=("ak74",))`; `engine3d/hold.py` `GRIPS["ak74"]` |
| `akrifle.mesh.json` | `ak-style-rifle.glb` | `cutscenes/cast3d.py` `rifle_asset`/`third_person_rifle`; `cutscenes/m3ko3d.py` `hold_weapon(...,"akrifle")`; `engine3d/hold.py` |
| `ammo_crate.mesh.json` | `farm-ammo-crate-bare.glb` (`T/ae_import_duty_props.py`) | `m8/duty/mansion_set.py` |
| `barrel.mesh.json` | `assets/import/barrel.obj` (`T/gen_barrel_obj.py` -> `T/ae_import_mesh.py`) | `C/sets/mission0.yard.set3d.json` `{"type":"mesh","ref":"barrel"}` -> `game/render3d_bridge.py` `mesh_for_prim()` via `m0/__init__.py` `set_prims()`; NOT `trap3d.py` `_barrel_mesh()` (procedural) |
| `car_m2.mesh.json` | `low-poly-car_green.glb` | `m2/draw3d.py` `_car_mesh`; `m4/draw3d.py` `_car_mesh`; `m8/revenge/chase_set.py` `_asset("car_m2")` (`jeep`, `_wrecks`); `m8/revenge/set3d.py` `_wreck` |
| `dog_m7.rig.json` | `dawg.glb` (only `ae.rig/1`) | `m7/raid_world.py` `_dog_rig()`, `dog()`, `dog_clip_s()` |
| `football.mesh.json` | `low_poly_football.glb` | `ui/credits.py` (`_FootballScene`) |
| `goal_post.mesh.json` | `low_poly_goal_post.glb` | `ui/credits.py` (`_FootballScene`) |
| `k93d.mesh.json` | `K93D.glb` | `m6/yard3d.py` `_k9_asset`; `m6/train3d.py` `_viewmodel_asset`; `ui/mp3d.py` `_k9_mesh`; `m6world3d.py` `_k9_rig_mesh` |
| `krap_van.mesh.json` | `krap_van.glb` | `missions/walk3d.py`, `walk_van3d.py`; `cutscenes/van3d.py`; `m1/draw3d.py` `_krap_van_mesh` |
| `lmg.mesh.json` | `light_machine_gun.glb` | `m6world3d.py` `_gun_mesh("lmg")`/`hum`; `m8/revenge/chase_set.py` `_lmg_split`; `engine3d/hold.py` |
| `m3_van.mesh.json` | `M3van.glb` | `m3/wings3d.py` `_van`; `cutscenes/m3ko3d.py` |
| `m7rifle.mesh.json` | `M7Rifle.glb` | `m6world3d.py` `_m7rifle_mesh()`/`_gun_mesh("m7rifle")`; `engine3d/hold.py` |
| `medkit.mesh.json` | `low_poly_medkit.glb` | `game/scenery3d.py` `prop()`/`medical_supplies()`; `m1/draw3d.py` `_pickup_mesh`; `cutscenes/m7world3d.py` |
| `molotov.mesh.json` | `low-poly-molotov.glb` | `m1/draw3d.py` `_molotov`; `cutscenes/van3d.py` `_molotov_asset` |
| `moneystack.mesh.json` | `moneystack.glb` (`T/ae_import_duty_props.py`) | `m8/duty/mansion_set.py` |
| `monitor_crt.mesh.json` | `low_poly_crt_monitor.glb` | `game/scenery3d.py` `prop()`/`workstation()`; `m2/draw3d.py`, `m3/wings3d.py`, `m3/draw3d.py`, `m5/draw3d.py` |
| `monitor_lcd.mesh.json` | `lowpoly_retro_lcd_monitor.glb` | `game/scenery3d.py` `prop()`/`workstation()`; `m3/wings3d.py`, `m5/draw3d.py` |
| `pc_tall.mesh.json` | `soviet_pc_tall.glb` | `game/scenery3d.py` `workstation()`; `m2/draw3d.py`, `m3/wings3d.py`, `m5/draw3d.py` |
| `pc_zarya.mesh.json` | `soviet_pc_zarya_pk86.glb` | `game/scenery3d.py` `workstation()`; `m2/draw3d.py`, `m3/wings3d.py` |
| `pig.mesh.json` | `low_poly_pig.glb` | **unused**: live pig is procedural `cutscenes/m7pig3d.py` (`pig_pose`, `pig_dead`, `pig_flat`) |
| `pill_bottle.mesh.json` | `low-poly-pill-bottle.glb` | `game/scenery3d.py` `medical_supplies()` |
| `pistol.mesh.json` | `pistol_lowpoly.glb` | `ui/mp3d.py` `pistol_mesh()`; `cutscenes/van3d.py` `_pistol_mesh()` |
| `sniper_rifle.mesh.json` | `T/ae_import_sniper.py` (`assets/3D/lowpoly_sniper_rifle.glb`) | `cutscenes/cast3d.py` `weapon_asset`/`RIFLE_ASSETS`; `cutscenes/m6world3d.py` `hum(flags=("sniper_rifle",))`; `cutscenes/m8dutyfilms.py` `_sniper_prop`/`_draw_sniper_world`/`_crash_actors`; `engine3d/hold.py` `GRIPS["sniper_rifle"]` |
| `suppressed_pistol.mesh.json` | `Suppressed_Pistol.glb` (`T/ae_import_duty_props.py`) | unreferenced (baked, not wired yet) |
| `tactical_lmg.mesh.json` | `tactical_lmg(white).glb` (`T/ae_import_duty_props.py`) | `cutscenes/m8dutyfilms.py` `_tactical_lmg`; `m8/duty/flight3d.py` (door gun, via `_tactical_lmg`) |
| `telephone_base.mesh.json` | `telephone-base-balanced-jet.glb` | `m8/revenge/epilogue3d.py` `telephone_base_mesh()` / `command_room()` |
| `telephone_handset.mesh.json` | `telephone-handset-balanced-jet.glb` | `m8/revenge/epilogue3d.py` `telephone_handset_mesh()`; `cutscenes/m8films.py` `heli_retardovici()` |
| `tractor_m7.mesh.json` | `TractorM7.glb` | `m7/raid_world.py` `_shape()`/`tractor_at()`; `cutscenes/m7world3d.py` `_tractor_asset()` |
| `truck_m7.mesh.json` | `IPA-army-truck.glb` | `m7/raid_world.py` `truck()`/`truck_at()`; `m1/draw3d.py` `_truck`; `m8/revenge/trap_world.py`; `m8/duty/mansion3d.py` (via `raid_world`) |

All `M/*.mesh.json` are `ae.mesh/1`. Runtime entry: `game/render3d_bridge.py` `load_mesh_asset(ref)` / `MESHES_DIR` / `mesh_for_prim()`; `game/scenery3d.py` `prop()`/`display()` cache with procedural fallback. `tools/smoke_test.py` asserts the `k93d`, `akrifle` bakes and the reticle PNG.

### 8.3 `assets/tex3d/` + `C/` set/texture/preset ids
**`assets/tex3d/`** (35 flat files; drawn by `tools/tex3d_draw.py` / `tools/tex3d_draw_m7.py`; read by `engine3d/textures.py`, `m6/decor.py`, `cutscenes/ps2mat.py`):
- 33 `.png`: `ashlar ballast bone boxcar brick concrete crate m6_palette m7_bark m7_barnboard m7_dirt m7_furrow m7_grass m7_gravel m7_hay m7_leaf m7_plank m7_plaster m7_stone m7_stubble m7_tile m7_tin m7_track metal_rib pavement rust scorch sleeper snow snow_trod steel stucco vault`
- 2 palettes: `m6.gpl`, `m7.gpl` (mirrored by `m6/palette3d.py`, `cutscenes/m7palette3d.py`).

**`C/` ids** (loader `game/render3d_bridge.py`: `SETS_DIR` `PRESETS_DIR` `TEXTURES_DIR` `MESHES_DIR`; gate `tools/ae_set3d_check.py`):
- `C/sets/` 3 `ae.set3d/1`: `mission0.depot`, `mission0.yard`, `m5/vasile_office` (file `m5.vasile_office.set3d.json` - id uses `/`, file `.`).
- `C/lighting3d/` 6 `ae.lighting3d/1` presets: `day_interior`, `exterior_night_rain`, `exterior_overcast`, `night_interior`, `office_day`, `rainy_street`.
- `C/textures/` 3 `ae.texture/1`: `asphalt`, `concrete`, `wood_crate` (generated by `tools/ae_textures_gen.py`).
- `C/grades/` 3 `ae.grade/1`: `cold_blue`, `faded_stock`, `night_warm` (loaded by `cutscenes/post3d.py`).

---

## 9. Main loop, FSM and input routing (in depth)

### 9.1 Boot
```
acaristan.py              sys.path += src/ ; import app
src/app.py (import time)  settings load -> display -> asset/audio init -> FSM registration
                          gsm.add(...) for the 15 states below -> gsm.transition("BOOT_INTRO") -> _apply_dev_args()
                          _rpe6_config._engine_app.run_scene(_LegacyGameScene())      (RPE6 A-002: whole game = one engine scene)
_LegacyGameScene          owns engine SceneStack mirrored from gsm (core/scene_mirror.FsmSceneMirror, A-005);
                          CUTSCENE mirrored as engine CutsceneScene (A-007), M5 "[E] look" as InspectScene
```
`launcher.py` (repo root) is a separate entry: KRAPNET launcher + updater (`src/launcher/`), which spawns the game with `ACA_FROM_LAUNCHER=1` (§16).

### 9.2 One frame (`app._legacy_frame`)
1. `dt = min(_pacer.wait(), MAX_DT=0.05)` (`core/frame_pacer.Pacer`: sleeps to an absolute deadline and returns whole 1/60 s steps, locked at 60 or 30 fps with hysteresis; an overrun returns its real duration); `frame_ms = clock.tick()` (no cap, wall time only); `STATE.dt = dt`; `_cut_watch()`; devtools frame sample.
2. Input: `get_scaled_mouse()`; `keys = pygame.key.get_pressed()` wrapped by `game/input_adapter.apply(keys)` (rebinds + gamepad; identity at defaults).
3. `audio.update()`; `interactions.pump_radio(gsm.current_name, gsm.transitioning)` (radio director; only GAME/WALK may speak).
4. Cursor visibility (`ui/main.CURSOR_ARROW_STATES` draw their own arrow; GAME/WALK draw a reticle).
5. Events: global keys (F11 fullscreen, F12 level editor, backquote console, devtools F3-F7), then `gsm.current.handle_event(event)`.
6. Fixed-step sim: `for _ in engine_clock.advance(dt): gsm.current.update(engine_clock.dt)` (engine `Clock`, ADR-004; MP arena: `core/fixedstep` from the same `dt`); then `set_ambience()`. No render interpolation, so a frame must span a whole number of steps or motion judders: never pace with `clock.tick(60)` (it waits 16 ms and drops a step every ~25 frames).
7. Render: `gsm.current.render(screen)` -> `console.draw` -> `_devtools.draw` -> transition fade -> `_present_frame()` (scaling/post) -> `pygame.display.flip()` -> `clock.feed_wall(frame_ms)`.
- Hang watchdog: `HANG_WATCH_S = 10` (`_hang_watch`). Hot reload: `ACARISTAN_HOT_RELOAD=1` polls sprite packs every 500 ms.

### 9.3 FSM states (`core/fsm.py` `GameStateManager`, classes in `src/app.py`)
| `name` | class | role |
|---|---|---|
| `BOOT_INTRO` | `_BootIntroState` | studio/boot intro |
| `ENGINE_INTRO` | `_EngineIntroState` | RPE6 engine logo |
| `MENU` | `_MenuState` | main menu (`ui/main.py`) |
| `SLOT_SELECT` | `_SlotSelectState` | 3 save slots; resume table -> `core/game_core.start_*` |
| `MULTIPLAYER` | `_MultiplayerState` | KRAPNET browser/lobby/match (`ui/mp.py`, `ui/match_screen.py`) |
| `SETTINGS` | `_SettingsState` | settings (`ui/system.draw_settings`, `app.handle_settings_event`) |
| `SHOP` | `_ShopState` | Outfitter (`ui/shop.py`) |
| `CUTSCENE` | `_CutsceneState` | plays `CutscenePlayer`; after-state dispatch |
| `CREDITS` | `_CreditsState` | End credits after M8's CALL OF ACARISTAN card; hands to MISSION_COMPLETE (`ui/credits.py`, football background `ui/credits_football.py`) |
| `BRIEFING` | `_BriefingState` | mission briefing (`BRIEFING_DURATION = 360`) |
| `WALK` | `_WalkState` | walking sim (`missions/walking_sim.py`) |
| `GAME` | `_GameState_` | all mission gameplay -> `core/game_core.game_update/game_draw` |
| `NOTEBOOK_INSPECT` | `_NotebookInspectState` | M1 notebook close-up (`ui/hud.draw_notebook_inspection`) |
| `PAUSED` | `_PausedState` | pause menu (`ui/system.draw_pause_menu`) |
| `DEATH` | `_DeathState` | death screen / Black Ledger death (`ui/system`) |
| `MISSION_COMPLETE` | `_MissionCompleteState` | physical KRAP case dossier (`ui/mission_complete.py`) + campaign save |
Menu music plays in `MENU_MUSIC_STATES = {MENU, SLOT_SELECT, SETTINGS, SHOP, MULTIPLAYER}` (`assets/music/ost/01_call_of_acaristan.mp3`).

### 9.4 Mission dispatch (`core/game_core.py`)
- Proxy facade: `_MODULES = [cutscenes, walking_sim, m1..m7, hud, weapons, interactions, effects]`; module `__getattr__` resolves `gc.<name>` by searching STATE first, then these modules (`_MODULE_FIRST_NAMES` = walking-sim globals that win over STATE). `m8` and `m0` are imported but not in `_MODULES`.
- Active mission = `STATE.active_mission` (`"MISSION0".."MISSION8"`, default `"MISSION1"`); predicates `_is_missionN_active()`.
- `game_update(keys)` / `game_draw(cx, cy)` route in order M0, M5, M8, M7, M6, M4, M3, M2, else M1/walking sim.
- Death restart (`restart` path in game_core): deepest checkpoint wins (M2 `mission2_checkpoint_reached`, M3 broadcast > kill order > ..., M5 deepest of hq/quarter/printworks/tunnel).
- Hosts around the legacy loop: `game/world` (engine.world PRE / SIM+POST / RENDER_SUBMIT, Phase 5) and `game/render` (render2d queue, Phase 6).

### 9.5 GAME-state event routing priority (`_GameState_.handle_event`)
First match owns the event:
1. M5 `inspect_active()` -> `m5.handle_inspect_event`.
2. M5 typewriter dialogue (`STATE.m5_dialogue_active`) -> `m5.handle_dialogue_event` (ESC pauses).
3. M7 raid (`STATE.m7_raid_active`) -> `m7/raid3d.handle_event` (ESC -> `set_paused(True)` + PAUSED).
4. M8 3D scenes (`STATE.m8_trap_active` / `m8_kill_active` / `m8_chase_active`) -> `m8/flow.scene_event` (ESC -> `scene_pause(True)`).
5. M8 beats: ESC pauses; ENTER is polled by `revenge/beats.py`.
6. M6 yard (`STATE.m6_yard_active`) -> `m6/yard3d.handle_event`; M6 train (`STATE.m6_train_active`) -> `m6/train3d`.
7. Legacy keys: `V` melee (`gc.handle_melee`), `M` minimap toggle, `F9` `gc.debug_jump_to_exfil`, `ESC` PAUSED; plus mission `handle_interact`, crafting, upload OS, keypad.
- Resuming from PAUSED calls `set_paused(False)` / `scene_pause(False)` on the same scene.

### 9.6 Cutscene request -> film -> after-state
Missions never call `start_cutscene` directly; they set a request and `_GameState_.update` (app.py ~3640-3720) drains one per frame, in this order:
```
request_mission6_ending            -> M6 ending films
m0.take_outro_request()            -> start_cutscene(m0.outro_shots(), "MISSION_COMPLETE")
m7.take_outro_request()            -> M7 outro
m8.take_outro_request()            -> M8 outro
m7.take_cutscene_request()         -> m7.film_shots(key)  -> after "M7_RESUME" -> m7.on_cutscene_done
m8.take_cutscene_request()         -> m8.film_shots(key)  -> after "M8_RESUME" -> m8.on_cutscene_done
STATE.request_m5_cutscene          -> m5/meta.M5_MID_CUTSCENES[key] -> "M5_RESUME"
STATE.request_m6_cutscene          -> m6/meta.M6_MID_CUTSCENES[key] -> "M6_RESUME"
request_seby_pickup / k9_pickup / vostral_pickup / volkov_mags   -> after "GAME"
request_escape_cutscene            -> after "MISSION_COMPLETE" (no fades)
request_chair_break_cutscene ...   (M3)
```
- Film keys map to builder functions: `m7/meta.M7_SCENES` / `m8/meta.M8_SCENES` = `{scene_id: (module_in_cutscenes, function)}` (e.g. `"m8_epi_casket": ("m8films", "epi_casket")`).
- `CutscenePlayer` (`app.py`) owns timing, `KO_CUT_CUES`, VO cues (`fired_cues`), fades (`hard_cut` skips shot-to-shot fade; `hard_cut_in` on shot 0 skips `GAME -> CUTSCENE` fade; `cut_to_play` on the final shot skips `CUTSCENE -> GAME` fade); `_CutsceneState` resolves after-states (`M5_RESUME` .. `M8_RESUME`, `MISSIONn_COMPLETE`, `MISSION_COMPLETE`, `GAME`).
- Trace: `ACA_CUTSCENE_TRACE=1` appends one line per cutscene event (`app._cut_trace`).

### 9.7 3D gameplay scene contract (M6 train/yard, M7 raid, M8 trap/kill/chase)
Module-level API (one live scene object per module): `scene()`, `begin(...)`, `active()`, `update(keys)`, `draw(surface)`, `handle_event(event)`, `set_paused(bool)`, `abort()`, `force_finish(reason)` (`m6/train3d` also `skip`, `result`, `reset`; `m6/yard3d` lacks `abort`).
- Active flags on STATE (`m6_train_active`, `m6_yard_active`, `m7_raid_active`, `m8_trap_active`, `m8_kill_active`, `m8_chase_active`) gate event routing (9.5).
- Completion callbacks back into flow: M6 `flow.on_train_done` / `on_yard_done`; M7 `flow.on_raid_done`; M8 `flow.on_trap_done` / `on_gantry_reached` / `on_kill_done` / `on_chase_done`.
- Fault policy: an exception in `update` prints the traceback and calls `force_finish("fallback")` (see `m7/systems.game_update`) so the mission never soft-locks. Keep that wrapper when adding a scene.
- M8: `m8/flow.live_scene()` returns whichever scene owns input; `music_tick` steers the score from the scene phase.

## 10. Mission catalogue

Operation names come from `core/mission_meta.py` (`meta_for`, `fail_text`, `radio_channel`). Every mission package has a `meta.py` (ids, stage constants, shot tables) and is reached through `core/game_core.start_*`.

| Mission | `STATE.active_mission` / operation | Stages / checkpoints (entry) | Package parts beyond the facade order | Data | Dev flag examples |
|---|---|---|---|---|---|
| M0 Depot | `MISSION0` - tutorial (D2 proof, scaffolded by `tools/ae_new_mission.py`) | one stage; `start_mission0` | thin host `m0/__init__.py` (`set_prims`, `outro_shots`, `take_outro_request`); also owns enemy types | `levels/mission0.depot`, `sets/mission0.{depot,yard}`, `dialogue/mission0.briefing`, `timelines/mission0.outro` | `--dev-mission0`, `--m0` |
| Walking sim | WALK state | harbour alley -> oil-rig strike -> van | `walking_sim.py`, `walk3d.py`, `walk_fp.py`, `walk_van3d.py`, `walking_attack3d.py`; `cutscenes/oil_rig_3d.py` | `timelines/core.cutscene1/2` | `--dev-walk`, `--dev-walk-after` |
| M1 | `MISSION1` WAREHOUSE RAID - BLACK NOTEBOOK | `start_mission` (warehouse); safe keypad 742 / egg 666 | `draw3d escape3d grade3d roles m1_audio meta` | `levels/m1.warehouse`, `dialogue/m1.radio`, `m1.standoff`, `timelines/m1.dropoff`, `m1.escape`; art `game/art/m1` | `--dev-m1`, `--dev-m1-game`, `--dev-safe` |
| M2 | `MISSION2` THE FRAME-UP - ROUTE 12 | `start_mission2`, `_sniper`, `_after_sniper`, `_flank`, `_truck`, `_checkpoint`, `_evidence_debug` | `components draw3d sniper3d sniper3d_set` | `levels/m2.city`, `timelines/m2.intro/ending/seby_pickup`; art `game/art/m2` | `--dev-mission2[-game,-sniper,-after-sniper,-flank,-truck,-evidence]` |
| M3 | `MISSION3` THE STABILIZATION CENTER - THE VOSTRAL | breakout, comms, archives, kill_order, broadcast, upload (`start_mission3_*_checkpoint`) | `components sweep wings3d draw3d`; `ui/upload_os.py`; cutscenes `m3*` | `levels/m3.{cell,comms,archives,kill_order,broadcast}`, 12 `timelines/m3.*`; art `game/art/m3` | `--dev-mission3[-comms,-archives,-kill-order,-broadcast,-upload,-ledger,...]` |
| M4 | `MISSION4` THE CAPITAL - 48H CURFEW (The Aftermath) | street, station, tower (`start_mission4_{station,tower}_checkpoint`); enterable SE corner shop on the street stage | `apc components draw3d escort fortify siege` | `levels/m4.{street,station}`, `dialogue/m4.liaison`, `timelines/m4.{intro,ending,arrest_beats}`; art `game/art/m4` | `--dev-mission4[-game,-intro,-station,-tower]` |
| M5 | `MISSION5` THE CAPITAL - EMERGENCY RULE (Martial Law) | hq, quarter, printworks, tunnel (`start_mission5_*_checkpoint`) | `components decor decor_interior decor_paint draw3d finale_audio finale_script inspect_art inspect_art_street inspect_fpv quarter render tram_wreck water`; cutscenes `m5*` | `levels/m5.{hq,quarter,print,tunnel}`, `dialogue/m5.maru`, `timelines/m5.{intro,ending}`, `sets/m5.vasile_office`; art `game/art/m5` | `--dev-mission5[-game,-hq,-printworks,-tunnel,-intro,-ending]` |
| M6 | `MISSION6` THE BORDER - WHITEOUT | `STAGES = customs, noman, rail, boxcar, train`; checkpoints customs/noman/rail/train; yard fight after Volkov's death; finale cutscene-only | `combat hud3d m6_audio palette3d perf stealth train3d yard3d yard_brain yard_dress yard_hud draw3d bloc3d/`; cutscenes `m6films m6world3d m6fx3d` | shot tables in `m6/meta.py`; `assets/tex3d/*` | `--dev-mission6[-game,-rail,-boxcar,-train,-shootout,-yard,-heli,-crossing,-ending,-3d]` |
| M7 | `MISSION7` FALLOW GROUND | `STAGES = arrival, chores, runner, prep, raidin, raid, finale, choice`; `start_mission7_stage/raid/outro` | `farmyard goat_rescue minigames colonel raid3d raid_brain raid_hud raid_world choice maps m7_audio`; cutscenes `m7films m7runner m7goat m7world3d m7pig3d m7palette3d` | `levels/m7.farm`, `timelines/m7.*` (6), `M7_SCENES`; `assets/tex3d/m7_*` | `--dev-mission7[-arrival,-chores,-runner,-prep,-raid,-raid-w2,-raid-w3,-raid-prepped,-finale,-choice,-outro]` |
| M8 | `MISSION8` THE CALL | route `STATE.m8_route` (written by M7 `choice`): revenge = `meet trap gantry friends kill descent chase epilogue` (`FIGHT_STAGES = trap, gantry`); duty ("HEAD OF STATE") = `d_approach mansion liftoff flight crash ridge d_epilogue` (playable: mansion, flight, ridge); `start_mission8_stage(stage, route)` | `m8_audio`; `revenge/{set3d,trap3d,trap_world,trap_brain,trap_hud,kill3d,chase3d,chase_set,epilogue3d,beats}`; `duty/{mansion3d,mansion_set,mansion_world,mansion_brain,mansion_hud,flight3d,ridge3d}`; cutscenes `m8films`, `m8dutyfilms` | `timelines/m8.{meet,friends,descent,heli,epilogue}`, `m8.d_{approach,liftoff,crash,epilogue}`, `M8_SCENES` | `--dev-mission8[-trap,-gantry,-friends,-kill,-chase,-heli,-ending,-duty,-mansion,-liftoff]` |

Full flag list: `python acaristan.py --list-jumps` (`core/dev_jumps.DEV_JUMPS`, 70+ targets; `--jump <name>`), or the GUI `python tools/dev_panel.py`.

## 11. Environment variables

| Variable | Effect | Read in |
|---|---|---|
| `ACARISTAN_RENDERER=gl\|software` | force 3D backend (default: GL, silent software fallback) | `engine3d/gl.py` `Renderer` |
| `ACARISTAN_CUTSCENE3D=0` | 2D fallbacks for every 3D cutscene take | `cutscenes/engine.py`, `m3broadcast3d.py`, film hosts |
| `ACARISTAN_HOT_RELOAD=1` | poll + hot-reload sprite packs every 500 ms | `app._rpe6_hot_reload` |
| `ACARISTAN_SHAKE_SCALE=<0-100>` | env layer for the shake setting | `engine/settings/model.py` |
| `ACA_TD_2D=1` | 2D top-down view instead of 2.5D (M1-M5, walk) | `game/topdown3d.py` |
| `ACA_MP_2D=1` | 2D multiplayer arena view | `ui/arena_view3d.py`, `ui/mp3d.py` |
| `ACA_M6_RAIL_25D=0` | force the M6 rail stage back to the fast 2D painter (rail/boxcar are 2.5D by default, like customs and no-man's-land) | `m6/draw.py` |
| `ACA_M6_AUTO=1` | opt-in adaptive M6 3D resolution (keep off) | `m6/perf.py` |
| `ACA_M6_RES=<scale>` / `ACA_M6_DRS=0` | force M6 internal scale / disable governor | `m6/perf.py` |
| `ACA_M6_DEBUG=1` / `ACA_M6_HUD=1` / `ACA_M6_HITCHLOG=1` | print scale + medians / ms strip / spikes to `build/m6_hitches.log` | `m6/perf.py` |
| `ACA_FREEZE=1` | pin time-driven terms (goldens, parity, smoke) | `engine/lighting/buffer.py`, `m6/perf.py` |
| `ACA_ART=legacy\|off` | every art-pack getter returns None (procedural fallback) | `engine/assets/_artpack.py` |
| `ACA_STATIC=off` | bypass the chunked static-world bake | `core/staticlayer.py` |
| `ACA_TL_SRC` / `ACA_DLG_SRC` / `ACA_LEVEL_SRC` / `ACA_SET_SRC` `=legacy` | use in-code tables instead of `content/` data | `game/timelines.py`, `dialogues.py`, `levels.py`, `render3d_bridge.py` |
| `ACA_SAVE_SUFFIX=<s>` | `save_data<s>.json`, `settings<s>.json`, `profile<s>.json` (two processes side by side; `ae_ci` uses `_aeci_<key>`) | `core/save_system.py`, `settings_store.py`, `profile_store.py` |
| `ACA_SEED=<int>` | engine settings seed | `engine/core/config.py` |
| `ACA_RECORD_INPUT=<file.json>` | record gameplay input (replay baselines) | `src/tools/input_recorder.py` |
| `ACA_CUTSCENE_TRACE=1` | cutscene event trace | `app._cut_trace` |
| `ACA_WORLD_DEBUG=1` | read-only world guard during RENDER_SUBMIT | `game/world/__init__.py` |
| `ACA_DEBUG_RIG=1` | draw 2D rig anchors over every Player | `entities/player.py` |
| `ACA_EGG666_3D=0` | force the 2D "666" safe scare | `ui/egg666_3d.py` |
| `ACA_MP_HOST` / `ACA_MP_PORT` | relay/master address override | `ui/mp.py` |
| `ACA_MP_DEV_TOKEN` / `ACA_MP_ALLOW_SKEW=1` | pin join token (`tools/mp_arena_duo.py`) / seat mixed builds | `ui/match_screen.py` |
| `ACA_UPDATE_URL` / `ACA_GITHUB_REPO` / `ACA_DEV=1` / `ACA_RELEASE=1` | updater source override / force dev hotkeys on (`ACA_DEV=1`) or off (`ACA_RELEASE=1`; frozen defaults off) | `launcher/updater.py`, `launcher/window.py`, `core/dev_jumps.py`, `app.py` |
| `ACA_FROM_LAUNCHER=1` | set by the launcher on the child game process | `launcher/window.py` |
| `SDL_VIDEODRIVER=dummy`, `SDL_AUDIODRIVER=dummy` | headless (smoke test and tools set these) | tools |

## 12. Dev affordances

- **CLI** (`app._apply_dev_args`, table `core/dev_jumps.DEV_JUMPS`: name -> (`--dev-*` flag, description)): `--dev-<target>` and short aliases (`--m3-kill-order`, `--m6-yard`, ...), `--jump <name>`, `--list-jumps`, `--continue`, `--dev-slot-select`, `--dev-safe`/`--safe`, `--dev-mp-host`/`--dev-mp-join` with `--mp-map --mp-players --mp-port`, `--trailer-bot`/`--trailer-act` (`src/tools/trailer_bot.py`), `--dev-audio-parade`.
- **Hotkeys** - global: `F11` fullscreen (always active); gated behind `core.dev_jumps.is_dev_mode()` (on from source unless `ACA_RELEASE=1`, off in frozen builds unless `ACA_DEV=1` or `--dev*`/`--jump`): `F12` level editor (`core/level_editor.py`, gameplay only; saves `maps/*.map`, never loaded), backquote console (`core/console.py`), devtools (`game/devtools.py`: `F3` overlay, `F4` collision view, `F5` level view, `F6` timeline view, `F7` skip cutscene), GAME `F9` jump to exfil (M1). Gameplay: `V` melee (checks both `mission3_weapon` and `current_weapon == "k9_smg"`), `M` minimap.
- **Console commands** (`app._console_*`): events tail, `timeline play <id> [t_ms]`, heat, reload, skip cutscene.
- **GUI panel**: `python tools/dev_panel.py` (clickable mission jumps).
- **Headless capture**: per-mission `tools/mN_td3d_shots.py`, `m6_shots.py`, `m8_chase_shots.py`, `render_*.py`; `tools/ae_loop.py` drives the real main loop headless.
- **Cinematic trailers**: `tools/trailer_call/{scenes,score,render,vertical}.py` ("THE CALL" spoiler-safe 90 s 2.39:1 GL cinematic + procedural 100 BPM OST-motif score + 42 s 9:16 vertical Short + thumbnails -> `outputs/trailer_call/`; flags `--sheet`, `--at`, `--from/--to`, `--music`, `--cta`, `--thumbs`); earlier trailers in `tools/trailer_rpe6/`, `tools/trailer3d/`, `tools/trailer_25d/`.

### 12.1 Dev jump targets (auto)

From `core/dev_jumps.DEV_JUMPS`; use as `--jump <target>` or the listed flag. Pattern: `--dev-missionN` / `--dev-missionN-<stage>` start a mission or stage; `--list-jumps` enumerates targets; non-obvious ones include `--m8-cp=0/1/2` (Duty mansion checkpoint), `--m7-preps` and the `--trailer-*` / `--mp-*` switches. Full generated table: `docs/FILE_INDEX.md` §12.1.

## 13. Persistent files (repo root, resolved from `Path(__file__).parents[2]`)

| File | Owner | Content |
|---|---|---|
| `save_data[SUFFIX].json` | `core/save_system.py` | `current_slot` + 3 slots (`progress` "m1".."m8" cleared on `save_mission_complete`, `checkpoint`, flags, mission-complete records); `set_slot_progress` (also M2 `shelter`, M4 `station`/`tower`, M5 `quarter`/`printworks`/`tunnel`), `set_slot_flags`, `save_mission_complete`; `app._SlotSelectState` resumes M2 `shelter` before `MISSION_1` |
| `settings[SUFFIX].json` | `core/settings_store.py` (+ `core/user_settings.py` live copy) | display, audio, accessibility (reduced motion, flash, shake), `quality_3d`, `bindings`, player name, playit address |
| `profile[SUFFIX].json` | `core/profile_store.py` | Acaribucks wallet, owned cosmetics, equipped loadout (validated by `core/appearance.py`; a hand-edited file cannot grant items) |
| `version.json`, `launcher_config.json` | `src/launcher/` | installed version, update source |
All writes go through `core/json_store.atomic_write` / `load_with_backup`. `*_p1`/`*_p2` variants come from two-window MP testing. Engine snapshots (`ae.save/1`) are separate: `game/save_adapter.capture/restore` for replays and tests only.

## 14. Data formats (`src/game/content/`)

| Schema | Files | Engine kernel | Game access | Gate | Legacy switch |
|---|---|---|---|---|---|
| `ae.timeline/1` | `timelines/*.timeline.json` (35) | `engine/timeline` | `game/timelines.shots(id, legacy)` | `ae_timeline_check.py` | `ACA_TL_SRC=legacy` |
| `ae.dialogue/1` | `dialogue/*.dlg.json` (5) | `engine/dialogue` | `game/dialogues.py` | `ae_dialogue_check.py` | `ACA_DLG_SRC=legacy` |
| `ae.level/1` | `levels/*.level.json` (15) | `engine/level` (+ Tiled `.tmj` import) | `game/levels.grid/level` | `ae_level_check.py` | `ACA_LEVEL_SRC=legacy` |
| `ae.set3d/1` | `sets/*.set3d.json` (3) | `engine/render3d/scene3d` | `game/render3d_bridge.py` | `ae_set3d_check.py` | `ACA_SET_SRC=legacy` |
| `ae.lighting3d/1` | `lighting3d/*.preset.json` (6) | `engine/render3d/presets` | `render3d_bridge.presets/set_lighting` | `ae_validate.py` | - |
| `ae.texture/1` | `textures/*.texture.json` (3) | - | `render3d_bridge.load_texture/push_textures` | `ae_validate.py` | - |
| `ae.grade/1` | `grades/*.grade.json` (3) | - | `cutscenes/post3d.apply_grade` | `ae_validate.py` | - |
| `ae.mesh/1`, `ae.rig/1` | `meshes/*.mesh.json` (20), `dog_m7.rig.json` | - | `render3d_bridge.load_mesh_asset`, `game/scenery3d.py` | smoke + `test_mesh_import` | procedural fallback per caller |
| `ae.manifest/1` (+ `ae.bakeinfo/1`) | `m{1..5}/manifest.json`; `m5/palette.json` | `engine/assets/manifest` | `game/art/_pack.py`, `game/art/m5` | `ae_bake.py --check --lint` | `ACA_ART=legacy` |
| strings | `strings/en.json` | `engine/text/strings.T` | `T("key")` everywhere | `ae_text_check.py` | missing key renders `[[key]]` |
| `ae.prefab/1` | (engine world prefabs) | `engine/world/prefab.py` | `game/world` | unit tests | - |
| `ae.save/1` | in-memory snapshots | `engine/save` | `game/save_adapter.py` | `ae_replay_check.py` | - |
Converters from in-code tables: `tools/ae_timeline_export.py`, `ae_dialogue_export.py`, `ae_level_export.py`; editor: `ae_timeline_edit.py`. `tools/ae_validate.py` loads every data file through its public loader.

## 15. `assets/` map

| Folder | Files | What / producer / reader |
|---|---|---|
| `assets/3D/` | 33 | GLB sources (§8.1); importers `tools/ae_import_*.py` |
| `assets/art/` | ~120 | generated sheets `spr_*.png/.json` (`tools/sprites/*`, `build_all_sprites.py`) + legacy art (`make_art_pack.py`, `make_station_sprites.py`); read via `core/artpack` -> `engine/assets/_artpack.py` |
| `assets/baked/m1..m5/` | ~254 | `ae_bake.py` output `<asset>_<v>.png` + `.bakeinfo.json`; read by `AssetRegistry` before live `render()` |
| `assets/sprites/` | ~127 | loose PNG sprites (`m5/`, station sprites) via `engine/assets/_sprites.get_sprite` |
| `assets/tex3d/` | 32 | 3D pixel textures + `m6.gpl`/`m7.gpl` (§8.3) |
| `assets/import/` | 1 | `barrel.obj` (`tools/gen_barrel_obj.py`) |
| `assets/fonts/` | 4 | IBM Plex Mono (Regular/SemiBold/Bold), Oswald (`engine/text/fonts.py`); radio uses bitmap `ui/pixfont.py` |
| `assets/music/` | 22 | `ost/` (20 tracks from `tools/ost/album.py` via `tools/build_ost.py`), `trailer/`, `newtrailer/` |
| `assets/voice/` | ~728 | per-speaker folders + `VO_xxx.ogg/.wav`, `_radio_cache` (`tools/build_radio_cache.py`); index `src/audio/voice_manifest.py`; batch recording/splitting `tools/vo_batch.py` |
| `assets/bin/` | 6 | `bore.exe`, `playitd.exe` + licences/versions (`tools/download_bore.py`, `download_playit.py`) for MP tunnels |
Loose SFX (e.g. `assets/alarm.mp3`) sit at `assets/` root and are registered by `audio/audio.py` (optional sounds log "Loaded optional sound ..." at import).

## 16. Multiplayer, launcher and distribution

**Multiplayer stack (KRAPNET)** - design doc `docs/KRAPNET_MULTIPLAYER.md`.
```
UI          ui/mp.py (server browser, DMs, connect bar) -> ui/match_screen.MatchScreen (entry panel + live match)
            ui/multiplayer_style.py (read-only presentation), ui/shop.py (Outfitter), ui/arena_view.py / arena_view3d.py / mp3d.py (render)
Sim         missions/arena.py: maps (build_walls, spawn_points, pickups), Deathmatch rules, ArenaSim, Predictor, hitscan, compute_payout
Session     net/match.MatchSession (authoritative host + interpolating clients, SNAPSHOT_HZ = 20), net/udp_transport (datagrams), TCP fallback
Master      net/client.MPRelayClient <-> tools/mp_server.py (DEFAULT_MASTER_PORT 27015, LAN discovery 27016 via net/discovery); direct matches DEFAULT_PORT 27017
Wire        net/protocol.py (encode/decode, checksum, snapshots, name/colour sanitising)
Reachability net/portmap (UPnP IGD + NAT-PMP), net/tcp_tunnel (bore/ngrok), net/playit_agent (playit.gg), net/roomcode (short codes)
Profile     core/appearance.py (catalog + one validator for save and wire), core/profile_store.py (wallet), entities/adornments.py (head gear)
Telemetry   net/telemetry.NetworkTelemetry
```
Test kit: `tools/mp_arena_duo.py` (two windows), `mp_bot.py`, `mp_match.py`, `mp_join.py`, `mp_host.py` (+ `mp_host_main.py` EXE entry), `mp_net_soak.py` (impairment), `preflight_bot_test.py`, `test_tcp_tunnel.py`, `test_multiplayer_ui.py`; smoke `--only mp` / `arena` / `match` / `udp` / `client`.

**Launcher / updater** - doc `docs/LAUNCHER.md`. `launcher.py` (`--demo-update`, `--check-only`) -> `src/launcher/window.py` `LauncherApp`/`run_launcher` -> `launch_game_process`; `src/launcher/updater.py` (manifest check, sha256 integrity, downgrade guard; preserves `save_data*.json`, `settings*.json`, `profile*.json`, `profiles.json`, `launcher_config.json`). `acaristan.py` sets CWD to `ROOT` and falls back to `%LOCALAPPDATA%/CallOfAcaristan/crash.txt`; `audio/voice.py` skips `*_matches.txt` when frozen and falls back to `%LOCALAPPDATA%/CallOfAcaristan/radio_cache`. Publish: `tools/publish_update.py`.

**Builds** - `build.bat`, `tools/build_windows.py` (PyInstaller `--onedir` via `build/_assets_stage`, excluding non-runtime `.pdf`/`.blend`/`.blend1`/`*_matches.txt`/`_RETAKES`/`TRAILER`/`ANNOUNCE_25D`/`graphify-out`/`m3cell_balaceanu_patch.py` and duplicate voice `.wav` beside `.ogg`), `tools/ae_package.py` (zip, `ae.package/1`, same non-runtime filters), `tools/itch_push.py` (butler), `tools/zip_project.py`, `tools/slim_tree.py` (dry-run cleanup), `tools/overlay_cleanup.py`. `Launch Game.bat` runs the game.

## 17. More one-shot bundles

**New mission** - `python tools/ae_new_mission.py` scaffolds an RPE6 host (M0 is the reference); follow `docs/engine/tutorial_add_mission.md`. Wire: `core/game_core.py` (import, `_is_missionN_active`, `start_missionN*`, update/draw routing, restart), `core/mission_meta.py`, `core/dev_jumps.py`, `app.py` slot resume + after-states, `ui/mission_failed.py`, `ui/mission_complete.py`, `content/strings/en.json`. Verify `python tools/ae_mission0_check.py` (pattern), `smoke --only <mission>`.

**New 3D gameplay scene** - copy the contract in 9.7 (module API + STATE active flag + `force_finish` fault path); route events in `app._GameState_.handle_event` (9.5) and resume in `_PausedState`; renderer via `engine3d.Renderer`, cast via `cutscenes/m6world3d.hum/actor`; HUD via `m6/yard_hud.py` + `m6/hud3d.py`. Add a `--dev-*` jump.

**New film / mid-mission cut** - builder function in `cutscenes/m7films.py` / `m8films.py` (or `m6films.py`), register in `m7/meta.M7_SCENES` / `m8/meta.M8_SCENES` / `m6/meta.M6_MID_CUTSCENES` / `m5/meta.M5_MID_CUTSCENES`, shot list in `content/timelines/<id>.timeline.json`, request from flow (`take_cutscene_request` or `STATE.request_mN_cutscene`). Verify `ae_timeline_check.py`, headless stills (`tools/m8_descent_shots.py`-style).

**Settings option** - `core/settings_store.py` (default + persist), `core/user_settings.py` (live), `app._current_settings_dict` / `handle_settings_event`, `ui/system.draw_settings`, label in `en.json`; typed field in `engine/settings/model.py` if it is an engine setting. Verify `smoke --only settings`, `ae_text_check.py`.

**Key binding / gamepad** - `engine/input/model.DEFAULT_ACTIONS` (`move_* fire interact reload sprint advance skip`), `game/input_adapter.py` (persist in `settings["bindings"]`). Many sites still read raw `K_*`; the adapter forces canonical keys down.

**Cosmetic / Outfitter item** - `core/appearance.py` catalog (price, kind, label), `entities/adornments.py` (2D head gear draw), `ui/mp3d.py` (3D rig + portrait), `ui/shop.py`. Verify `smoke --only outfitter,appearance,cosmetic`.

**Multiplayer gameplay rule** - `missions/arena.py` (sim + rules), `net/protocol.py` (wire fields; keep `normalize_*`), `net/match.py`; never trust client data (validate in `core/appearance.normalize`). Verify `smoke --only mp,arena,match` (full run, not `--fast`), `tools/mp_net_soak.py`.

**Import a 3D model** - drop GLB in `assets/3D/` (pre-commit hook adds an `(auto)` row to §8.1), write `tools/ae_import_<name>.py` (reuse `ae_import_k93d._gltf/_scan/_cluster`) or use `tools/ae_import_mesh.py`, output `content/meshes/<id>.mesh.json`, consume via `render3d_bridge.load_mesh_asset` or `game/scenery3d.prop` with a procedural fallback; fill §8.2.

**Level geometry (2D maps)** - mission `maps.py`/`map.py` via `core/mapbuilder.MapBuilder` (AGENTS.md map contract), then `python tools/ae_level_export.py` to refresh `content/levels/*.level.json`; `ae_level_check.py` must stay OK.

**Enemy brain (3D)** - `engine/ai` (bt, senses, cover, squad) + per-scene brains `m6/yard_brain.py`, `m7/raid_brain.py`, `m8/revenge/trap_brain.py`, `m8/duty/mansion_brain.py`; tests `tests/unit/test_engine_ai.py`. Each brain's `spheres()` returns the standing Guard's hit spheres. **Index 0 = chest, index 1 = head** - keep that order: M6 `yard3d` decides a headshot with `zi == 1` and `yard_brain.suppress()` reads `spheres(g)[0][0]` (chest height); M7/M8 scenes instead trust the third tuple item (`is_head`). Standing riflemen now carry four spheres (chest ~1.14 m r~0.46, head 1.62 m r0.25, pelvis ~0.72 m r0.35, shin/ankle ~0.30 m r0.32) so low shots land; `hide_low`/flat-on-snow Guards keep their reduced sets. **Truck gunners keep only chest+head** (`e.get("truck") is not None`) in M7 raid / M8 trap so rounds cannot pierce the truck bed to reach their legs; M8 Mansion has no truck gunners.

**Music / SFX** - SFX: `audio/audio.py` registry + `audio.play(name)`; mission banks (`m1_audio`, `m6_audio`, `m7_audio`, `m8_audio`, `m5/finale_audio`) synthesise PCM and `warm()` at load; gameplay OST mixing `core/score.py` (20-track, mission-keyed calm/tense score); zone ambience `core/ambience.py`; footsteps `core/surfaces.py`. Never synthesise during a fight (M6 rule).

## 18. CI gates (`tools/ae_ci.py`)

`python tools/ae_ci.py [--quick] [--skip a,b] [--jobs N] [--serial] [--force]`; logs in `build/ae_ci/<key>.log`; each gate runs with `ACA_SAVE_SUFFIX=_aeci_<key>`; `bench`/`bench3d` run first and alone. `--quick` skips the slow ones (marked *).

| key | command | pass line |
|---|---|---|
| `compileall` | `python -m compileall -q src tools` | exit 0 |
| `boundaries` | `tools/check_boundaries.py` | `BOUNDARIES: OK` |
| `imports` | `tools/ae_import_check.py` | `IMPORT CHECK: OK` |
| `star` | `tools/ae_narrow_star.py --verify` | `AE NARROW: OK` |
| `globals` | `tools/ae_global_names.py` | `AE GLOBAL NAMES: OK` |
| `text` | `tools/ae_text_check.py` | `AE TEXT: OK` |
| `api` | `tools/ae_api_snapshot.py check` | `AE API: OK` |
| `d4` | `tools/ae_d4_gate.py` (no attribute stuffing on entities) | `AE D4: OK` |
| `d6` | `tools/ae_d6_gate.py` (one 2D render path, custom-draw ratchet) | `AE D6: OK` |
| `level` / `dialogue` / `timeline` / `set3d` | `tools/ae_<x>_check.py` | `AE LEVEL/DIALOGUE/TIMELINE/SET3D: OK` |
| `unit` | `python -m unittest discover -s tests/unit -t .` | `OK` |
| `bake` | `tools/ae_bake.py --check --lint` | `AE BAKE: OK` |
| `smoke`* | `tools/smoke_test.py` | `SMOKE TEST: OK` |
| `golden`* | `tools/ae_golden.py verify` | `AE GOLDEN: OK` |
| `replay`* / `replaycheck`* | `tools/ae_replay.py check` / `ae_replay_check.py` | `AE REPLAY: OK` / `AE REPLAY-CHECK: OK` |
| `flash`* | `tools/ae_flash_check.py` | `AE FLASH: OK` |
| `dump`* | `tools/ae_dump_components.py --seg m5 --seconds 1` | `AE DUMP: OK` |
| `loop`* | `tools/ae_loop.py check` | `AE LOOP: OK` |
| `bench`* / `bench3d`* | `tools/ae_bench.py --check-budget` / `ae_bench3d.py --check-budget` | `AE BENCH BUDGET: OK` / `... office3d: OK` |
| scene bench (diagnostic) | `tools/ae_bench_scenes.py all --frames=90` | `AE BENCH SCENES <scene> avg=... (fps)` |
| `validate`* | `tools/ae_validate.py` | `AE VALIDATE: OK` |
| `engine3d`* | `tools/ae_engine3d_parity.py` | `AE ENGINE3D PARITY: OK` |
| `mission0`* | `tools/ae_mission0_check.py` | `AE MISSION0: OK` |
| `holds`* | `tools/ae_hold_check.py` | `AE HOLD: OK` |

**Smoke test** (`tools/smoke_test.py`, ~12.7k lines, 172 `check_*` functions): `--only a,b` takes name substrings/globs (`m8`, `m6_train`, `mp`, `sprite_pipeline`, `map_assets3d`), `--fast` skips slow ones, `--list` prints the slow names (MP network, `m6_train_*`, `m7_goat_rescue`, `m7_tractor_minigame`, `mission4_wave_director`, `sprite_pipeline`, ...). Largest groups: `mission5_*` 15, `m1_*` 14, `mission4_*` 10, `mission3_*` 9, `m7_*` 8, `m6_*` 7, `arena_*` 7.

**Other test data**: `tests/api/engine_api.json` (API snapshot), `tests/golden/baseline_v0` (+ `_verify/` = last verify output, not a baseline), `tests/replay/baseline_v0..2`, `tests/loop/baseline_v0..6`, `tests/data/m5_scene_trace.txt`. Git hook `.githooks/pre-commit` runs `tools/map_assets3d.py` and stages this file when §8.1 changes.

## 19. Glossary and doc index

- **STATE** - `core/state.py` singleton; `reset()` groups: entities, camera/FX, combat/inventory, M3 crafting, M3 Black Ledger, mission flow, per-mission blocks M2-M7, death animation, M1 pacing, interactables, stats, walking sim. Later missions add attributes with `getattr(STATE, name, default)`.
- **RPE6** - Retardovici Pulse Engine 6 Gold, the `src/engine/` migration. Plan of record `docs/engine/STATUS.md`; master spec `docs/engine/ENGINE_MASTER_PROMPT.md` (the `§6.x` numbers in docstrings refer to it). **A-xxx** = adapters (`docs/engine/ADAPTERS.md`; e.g. A-002 legacy loop as one scene, A-004 timebase, A-005 FSM mirror, A-006 deprecated re-export shims, A-008 `art.m5` shim). **B-xxx** = engine bug log (`docs/engine/BUGS.md`). **ADR-xxx** = `docs/engine/adr/` (004 fixed timestep, 014 scene stack, 017 render queue order, 019 timeline/set3d data, 023 cast shadows, 024 mesh import). **D1-D10** = engine deliverables/gates (D4 components, D6 one render path, D10 one-command CI). **R-rules**: R3 engine never imports game, R6 named RNG streams, R7 no import side effects, R14 line endings. Phases 0-11 track the migration.
- **Facade** - mission/ui/cutscenes `__init__.py` that only re-exports parts; `_LIVE_STATE` + PEP 562 `__getattr__` expose rebound globals read-only.
- **Bake** - `ae_bake.py` turns code-authored `render()` into PNGs; the PNG wins at runtime.
- **2.5D** - top-down rules drawn by `engine3d` (`game/topdown3d.py`, `missions/mN/draw3d.py`); 2D path stays as fallback. World-space rain comes from `game/rain3d.py` in the rainy hosts (walk/M1/M4/M5), with `step_rain_drops` keeping replay RNG parity.

Docs worth knowing (`docs/`): this map (live architecture + contracts only); `FILE_INDEX.md` (generated per-file source / tools / tests + dev-jump catalog); `worklog.md` (historical patch notes moved out of this map). Story: `LORE.md`, `MISSION3..8_PLOT.md`, `FIXES_STORIES.md`; plans `MASTER_ACTION_PLAN.md`, `M4_OVERHAUL_PLAN.md`, `M6_TOPDOWN_ART_BRIEF.md` (all point-in-time); systems `KRAPNET_MULTIPLAYER.md`, `LAUNCHER.md`; engine `docs/engine/{STATUS,ADAPTERS,BUGS}.md`, `adr/`, `subsystems/<kernel>.md`. Graph: `src/graphify-out/GRAPH_REPORT.md`.

**Known doc drift** (code wins): both M8 routes are playable (Revenge in full; Duty with the mansion, flight and ridge scenes). Plans and reports under `docs/` are point-in-time and may still call Duty a placeholder. `src/art/m5/*.py` (other than `__init__.py`) are stale tracked copies that never run.

## 20. Monolith anchors

For `tools/ai_bundle.py` line-range slicing (`ai_bundle.py path:start-end`). The per-file source docstrings, tools index and tests index are now in `docs/FILE_INDEX.md` (generated by `tools/sync_arch_map.py`).

### 20.1 Monolith Anchor Table (files > 1,000 lines)
<!-- AUTO:anchors -->
Line ranges (generated) for the monoliths; give `tools/ai_bundle.py path:start-end` the slice you need.

- `app.py` (4795): 1-523 header/imports; 524-547 def trigger_transition; 548-967 class CutscenePlayer; 968-1994 def draw_slot_select_screen; 1995-2239 class _BootIntroState; 2240-2377 class _EngineIntroState; 2378-2445 class _MenuState; 2446-2650 class _SlotSelectState; 2651-2831 class _MultiplayerState; 2832-2884 class _SettingsState; 2885-2920 class _ShopState; 2921-3369 class _CutsceneState; 3370-3426 class _CreditsState; 3427-3450 class _BriefingState; 3451-3507 class _WalkState; 3508-4028 class _GameState_; 4029-4047 class _NotebookInspectState; 4048-4103 class _PausedState; 4104-4219 class _DeathState; 4220-4719 class _MissionCompleteState; 4720-4739 def _rpe6_hot_reload; 4740-4795 class _LegacyGameScene
- `cutscenes/m6world3d.py` (2721): 1-77 header/imports; 78-370 plumbing; 371-417 film grade; 418-747 actors; 748-1169 motion kit; 1170-1218 def head_stats; 1219-1305 particles; 1306-1325 sky / light helpers; 1326-1687 insertion sets; 1688-2200 the valley run (intro chase); 2201-2351 boxcar interior; 2352-2721 rail platform / terminal / office
- `cutscenes/m7world3d.py` (3281): 1-360 header/imports; 361-796 M8 ruin: Bodi's farm the morning after the fire ; 797-1243 def _tractor_asset; 1244-1670 def motorcycle; 1671-2082 def _landscape_water_tower; 2083-2536 def _south_y; 2537-2964 def _sag; 2965-3281 def _smoke_img
- `missions/m8/revenge/chase_set.py` (2548): 1-151 header/imports; 152-563 meshes; 564-590 def _xf; 591-1047 the Guard gunship; 1048-1435 def _rot_rt; 1436-1837 the baked set; 1838-2249 def _verge_trees; 2250-2548 def _zone_border_fence
- `missions/m2/draw.py` (8096): 1-454 header/imports; 455-549 def _draw_car_burn_overlay; 550-951 Generated vehicle sprites (Polish T7); 952-1277 def _draw_tanker_dynamic; 1278-1744 Generated story-prop sprites (Polish T7); 1745-2184 def _draw_sebi_body_fpv; 2185-2779 def _draw_fpv_hands_inspect; 2780-3198 def _prop_icon_variant; 3199-3879 def _draw_shelter_live; 3880-4503 def _draw_interactables; 4504-5048 def _draw_card; 5049-5507 def _draw_packet_document; 5508-5942 def _draw_hud; 5943-6536 def _draw_dead_air_overlay; 6537-6615 def _draw_blackout_overlay; 6616-6752 Static bake + lighting fixtures (Mission 3 pipel; 6753-7210 Deterministic per-tile noise; 7211-7611 def _bake_m2_static; 7612-8096 def get_mission2_clue_defs
- `missions/m3/draw.py` (8367): 1-182 header/imports; 183-615 static-layer bake + lighting fixtures (graphics ; 616-1030 exterior ground: world-space dressing; 1031-1458 def _draw_guard_room_details; 1459-1882 def _draw_laundry_room_details; 1883-2370 def _draw_exit_zone_details; 2371-2808 def _draw_comms_map_polish; 2809-3779 def _draw_m3_enemy_type_overlay; 3780-4194 def _draw_archives_map_polish; 4195-4626 def _vp_hand_xform; 4627-5043 Slice 5: Kill Order ground-floor draw path; 5044-5295 def _draw_bcast_station_pc; 5296-5703 bound-hand POV palette (v2 art pass); 5704-6127 def game_draw; 6128-6580 def _draw_m3_pickup; 6581-7073 def _draw_cell_details; 7074-7508 def _draw_cell_details_live; 7509-7918 def _draw_kitchen_details; 7919-8367 def _paint_cell_door_blown
- `audio/audio.py` (3454): 1-124 header/imports; 125-240 New Powerful DSP Helpers for 16-Bit DOS Style So; 241-242 Upgraded DOS/16-Bit Sound Generators; 243-665 v2 organic DSP helpers (SFX audit pass); 666-765 def _gen_footstep; 766-1184 Overhaul: surface-specific footsteps, NPC feet, ; 1185-1651 def _gen_pa_chime; 1652-2055 def _gen_ambient_drone; 2056-2256 def _gen_molotov_throw; 2257-2540 Cinematic procedural sounds; 2541-2759 Trailer overhaul (docs/PLAN_3_AUDIO.md) - ADDITI; 2760-2776 Audio Manager; 2777-2895 Upload OS CRT sounds; 2896-3454 class AudioManager
- `ui/match_screen.py` (4881): 1-203 header/imports; 204-214 Identity; 215-298 In-match chat; 299-502 class Wire; 503-614 class Peer; 615-1113 class MatchScreen; 1114-3153 starting a match; 3154-4881 panel input
<!-- /AUTO:anchors -->
