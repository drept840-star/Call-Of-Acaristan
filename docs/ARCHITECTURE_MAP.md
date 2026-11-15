# ARCHITECTURE_MAP

Purpose: name the exact files to read/edit for a task in one pass. Paths are from the repo root; game code is under `src/` (imports are rooted there: `missions.m6.draw` = `src/missions/m6/draw.py`). Short forms: `engine/...`, `ui/...`, `core/...` = `src/<path>`; `mN/...` = `src/missions/mN/...`; `content/...` = `src/game/content/...`. Working rules (facades, shared state, renderer, sprite pipeline, story canon) are in `AGENTS.md`. Verified against disk on 2026-11-14 (branch `m8/the-call`); §8 3D asset inventory re-verified file-by-file; §9-§22 added from a full tree survey. On conflict, the code wins: re-grep the symbol.

Contents: 1 Runtime spine - 2 Engine API by file (2.1 shared 3D/cutscene/asset signatures + coordinate contracts) - 3 Game-side packages - 4 Call chains & shared ownership - 5 Weapon/item crosswalk - 6 One-shot file bundles - 7 Gotchas & gates - 8 3D assets inventory - 9 Main loop, FSM, event routing, film requests, 3D scene contract - 10 Mission catalogue - 11 Environment variables - 12 Dev affordances - 13 Persistent files - 14 Data formats - 15 assets/ map - 16 Multiplayer, launcher, builds - 17 More one-shot bundles - 18 CI gates and smoke test - 19 Glossary, doc index, known drift - 20 Source file index - 21 Tools index - 22 Tests index

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
- Face tuples differ: `Mesh.faces` = `(idx_tuple, colour, layer, double, emissive)` (5 items). `Renderer.add_dynamic` / `pack` want 6 items `(idx, colour, layer, double, None, emissive)`; convert like `m6world3d.add`: `[(f[0],f[1],f[2],f[3],None,f[4]) for f in m.faces]`. Layer = paint bucket (0 ground, 1 decal, 2 solid default, `FX_LAYER`=6 for glows/fx sprites in `m5fx3d`/`m6fx3d`).
- `Light(direction, ambient, diffuse, sky, tint)` is the key light (`m7world3d.LOOKS[k]["light"]` is its kwargs). Local lights are plain dicts for `set_lights`: `pos, color, intensity, range, kind='point'|'spot'` (spot adds `dir`, `cone` = cos of the half-angle); the strongest `cap=8` win. `set_pools` = ground lamp pools (`pos, range, color, intensity, hot`).
- `Renderer(w, h, fog, fog_start, fog_end, **kw)` (gl.py) returns `GLRenderer` when moderngl works, else `SoftwareRenderer`; same API. Film-host frame order (see `m7world3d.stage`): `set_lights` -> `set_camera(pos, target, fov, roll)` (hosts call `cam(...)`, which adds handheld drift) -> sky -> `begin()` -> bake static once -> per-frame `add_dynamic` / `add_packed` / `add_resident` / `add_humanoid` / `add_sprite` / `add_blob_shadow` / `add_line3d` -> `flush(surface)` -> grade / `present*` to the screen. `bake(mesh, m, t, tag)` is once-only static geometry (`invalidate_static()` after editing it in place). `pack(wverts, faces)` -> float32 rows (GL only, static method); replay with `add_packed` (re-sent every frame) or `add_resident` (uploaded once, identical every frame; the memoized set). `add_humanoid(...)` returns the joint dict.

**Humanoid rig (`engine3d/rig.py`)** - a pose is a dict of degrees; missing keys fall back to `NEUTRAL`. Build rigs with `Humanoid(spec)` (spec keys in the class docstring); `cutscenes.cast3d.humanoid3d(who, **overrides)` builds one from the 2D `figure_kit.SPECS`.
- Sign rules: `spine` lean forward, `spine_r` side lean, `twist`; `head_p` nod DOWN (+), `head_y` turn, `head_x` lateral shift in m (+ right); `lsh_p`/`rsh_p` shoulder raise FORWARD (+hip_p/+sh_p style), `lsh_r`/`rsh_r` raise OUT, `lsh_y`/`rsh_y` upper-arm roll (elbow swivel, set by `ik`), `lel`/`rel` elbow bend (+ = bend); `lhip_p`/`rhip_p` thigh raise FORWARD (+), `lhip_r`/`rhip_r` out, `lkn`/`rkn` knee bend (+ = shin swings back); `lank`/`rank` ankle point (+ = toes away from the shin; lying bodies need it or the heel props them off the floor); `body_p` whole-body pitch (+ forward, 90 = face down; `prone` 88, `dead_back` -88), `body_r` roll, `lift` metres above auto ground contact (jumps/dives), `rifle_p` (+ = muzzle DOWN) / `rifle_y` rifle vs body. Named poses are partial dicts: `POSES[name]`. `blend(a, b, t)` lerps two poses; `pose_run(phase, lean)`, `pose_drag`, `pose_crawl` are gait functions.
- `EXPRESSIONS` names via `h.set_expression(name, mouth_open)`; `solve_look(eye, target, body_yaw_deg)` -> `(head_y, head_p)` clamped yaw +-38, pitch -14 (up)..+30 (down), smoothing is the caller's; `mouth_flap(t_ms, seed)` -> 0..1 talking mouth. Key lists are in the auto block.
- `ik`: `solve_arm(hum, pose, pos, yaw, side, target, pole=None)` and `solve_leg(...)` return a NEW pose with the limb keys rewritten so the hand/ankle lands on a world `target` (`side` = `"l"`/`"r"`; out-of-reach straightens the limb). `solve_rifle_hold(hum, pose, pos, yaw, target, ...)` shoulders a long gun. `hold`: `hold_weapon(hum, pose, pos, yaw, weapon='rifle', mode='aim', aim=None)` -> pose, `weapon` in `GRIPS` keys, `mode` in `MODES` keys; `hold_cached(hum, pose, weapon, mode, aim=None, key=None)` is the per-frame version; `hold_frame` -> `(pose, origin, basis)` for guns drawn apart from the rig rifle. Gun space = (right, up, forward) metres, origin on the right hand, `+z` muzzle.
- `textures.tex(name, like=None, density=None, tint=False)`: a face colour that shows `assets/tex3d/<name>.png` (names in the auto block); `like=(r,g,b)` keeps that colour's brightness, `tint=True` keeps the colour and takes only the texture's light/dark, `density` (texels/m) counts on first use only, a missing texture returns `like` or grey. Software draws the average colour, GL multiplies the texels.

**`cutscenes/m6world3d.py` actor keys** - `hum(key, hd=False, wound=0, bloody=False, flags=())` caches one `Humanoid` per `(key, flags)`; `actor(r, key, pose, pos, yaw, t, seed=0, amp=1.0, rifle_on=False, expression=None, mouth=None, bias=0.0, hd=False, wound=0, bloody=False, shadow=None, flags=())` calls `hum`, adds breath/sway through `life_pose(pose, t, amp, seed)`, auto-flaps the mouth while that speaker talks, calls `r.add_humanoid` and appends to `LAST` (max 16 dicts `{key, joints, pos, yaw, pose, hd, flags, rifle}`, cleared by `rend()`; read it to put props on hands). `pos` = feet root (ground contact is solved), `yaw` degrees. `add(r, mesh, bias)` queues a `Mesh` (routes to bake / pack memo / `add_dynamic`). `rend()` -> `(renderer, surface)`.
- Key -> result. `("biribel", outfit)`: Biribel with `core.outfits.biribel_3d(outfit)` (`"krap"`, `"guard"` = `OUTFIT_GUARD`, `"krap_armband"`, or a `scene_outfit(...)` id); weapon flags work ONLY on this key and only when not `hd`: `"rifle"` (K9), `"lmg"`, `"shotgun"` (+`"nopump"`), `"ak74"`, `"os12"` (+`"nomag"`), plus `"cig_dropped"`; the gun draws only with `rifle_on=True`. `("guard", variant)`: train Guard (`guard_spec`), armed with the variant's rifle, flag `"os12"` swaps it. `("ally", name)`: named cast member WITH a gun (`m7rifle`; `os12` with the flag). Plain `"guard"`: third-person AK guard (`"os12"` swaps). `"ucilev"`: always the sniper rifle. `"president"`+`"bare_sleeve"` and `"maru"`+`"suit"` are look flags. Any other plain string (`"bodi"`, `"alex"`, `"vasile"`, `"volkov"`, `"commander"`, `"krap"`) = `humanoid3d(key)`: UNARMED (no `rifle` in its spec), flags ignored; for an armed Bodi use `("ally", "bodi")`. `SPECS` keys: `biribel vasile volkov commander fisherman balaceanu president maru bodi alex ucilev ipa krap civilian hungry_kid andrei_m` (`"retardovici"` aliases `president`).
- Motion kit: `path(points, smooth)` -> `route(d)` -> `(pos, yaw)`; `walk(hum, route, g, stride, speed, ground)` = planted-foot walk (`walk_stride` / `walk_span` size it, `walk_slip` audits); `sit_pose(hum, seat_y, upper=None)`; `reach(hum, pose, side, target, pos, yaw, pole)` = arm IK to a world point; `planted_pos(hum, pose, yaw, mid_xz, y)` -> root; `ankles` / `knees` = world joints. `m7world3d` has its own `sit_pose(**kw)`, `walk_pose(t, speed, tired)`, `stand_pose(**kw)` and `k(t, start, length)` (clamped smoothstep over milliseconds).

**M7/M8 3D set helpers** - `m7world3d.LOOKS` keys (auto block) are dicts `fog, fog_start, fog_end, light{direction,ambient,diffuse,sky,tint}, sky_top, sky_bot, sodium, stars`. `stage(look, t, eye, tgt, fov, lights=(), hh, seed, size, park, well_roof)` -> `(r, buf)` (lights + camera + sky + static bake, `begin()` already called); add actors, then `finish(surface, r, buf, seed, tag, t)` (flush + present + grade). Helpers return `Mesh`es: `tree(seed)`, `hay(n)`, `_fence(x0,z0,x1,z1,h,every,col,gap)` (gap in world coords), `_hedgerow(x0,z0,x1,z1,seed)`, `_bipyr(cx,cy,cz,r,up,dn,col,col2,n,moon)`, `_t(name, col, tint)` (M7 texture at ground/prop density). `chase_set` meshes face local `+z` forward (tractor, trailer, jeep, rocket, gun_truck) and are placed with `put(r, key, build, pos, yaw, pitch, roll)` (cached by `key`); `stratus(r, buf, t, pal)` paints cloud streaks; `frame(eye, tgt, fov, t, size, look, lights)` = camera + light + sky; `present(r, surface)`. FX: `m5fx3d.glow` and `m6fx3d.glow` share semantics (`max_px` default 200 vs 36); `night_sky(r, buf, t, top, bot, ...)` is `m5fx3d`; `m6fx3d.grade_cine(surface)` = cinematic grade, `present_crisp(src, dst)` = hard-pixel upscale (no return values). Glows/shafts are queued with `r.add_sprite(..., layer=FX_LAYER)` by the hosts.

**Mesh assets (`ae.mesh/1`, ADR-024)** - `game.render3d_bridge.load_mesh_asset(ref)` -> `(verts, faces)` raw lists from `M/<ref>.mesh.json`. Each face is `[idx, [r,g,b]]` (2 items: `k93d`, `akrifle`, `lmg`, `pistol`, `barrel`...) OR `[idx, [r,g,b], flag]` (3 items: `car_m2`, `tractor_m7`, `truck_m7`, `krap_van`, monitors, PCs, medkit; flag 1 = screen/emissive group, other ints = group ids); `idx` = 3 (tri) or 4 (quad) vertex indices. `mesh_for_prim(prim)` runs `for idx, col in faces`, so it only works for 2-item assets and raises `ValueError` on 3-item ones: for those use `game.scenery3d.prop(ref, screen=...)`, which reads `f[0], f[1], f[2]`. Mesh prim: `{"type":"mesh","ref":<id>,"pos":[x,y,z],"yaw":deg,"scale":s}` (yaw sign as `rot_y`). Budget: `tools/ae_import_mesh.py --budget` defaults to 1500 tris per prop (error above); authored importers cluster to their own budget (`k93d` 4042 faces, `truck_m7` 15052), so per-asset counts are in §8.1b / §8.2. `tools/ae_import_k93d.py` reads multi-node GLBs: `_gltf(path)` -> `(json, binbuf)`; `_acc(g, binbuf, i)` reads accessor `i`; `_scan(g, binbuf)` -> `(verts, tris, focus)` with node TRS/matrices applied from the identity root `I4` (tris = `(points, material, group, uv_rgb_hint)`); `_cluster(verts, tris, cell)` -> `(verts, faces)` vertex-clustered to `--cell` metres; output adds `meta` (`muzzle`, `sight`, magazine group) in gun space (+z muzzle, +y up, origin at the trigger).

Generated signatures (`-> ~T` = return type inferred from `return` statements, `# text` = first docstring sentence):

<!-- AUTO:sigs -->
**`engine3d/core.py`** (924 lines)
```
def lerp(a, b, t)
def clamp(v, lo=0.0, hi=1.0)
def smooth(t)
def ease_in_out(t)
def ease_out(t)
def ease_in(t)
def mix_col(a, b, t) -> ~tuple3
def v_add(a, b) -> ~tuple3
def v_sub(a, b) -> ~tuple3
def v_mul(a, s) -> ~tuple3
def v_dot(a, b)
def v_cross(a, b) -> ~tuple3
def v_len(a)
def v_norm(a) -> ~tuple3
def v_lerp(a, b, t) -> ~tuple3
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
    def __init__(self, w, h, fog=(96, 98, 104), fog_start=18.0, fog_end=210.0)
    def resize(self, w, h) -> ~bool
    def set_camera(self, pos, target, fov, roll=0.0)
    def to_cam(self, p) -> ~tuple3
    def project(self, p) -> ~tuple3
    def horizon_y(self)
    def visible_sphere(self, c, r) -> ~bool
    def bake(self, mesh, m=M_IDENT, t=(0.0, 0.0, 0.0), tag='')
    def begin(self)
    def set_texture(self, tex_id, arr) -> None
    def set_lights(self, lights, cap=8)  # Local lights for this frame
    def set_pools(self, pools, cap=32)  # Lamp pools for this frame
    def add_static(self)
    def add_dynamic(self, wverts, faces, bias=0.0, tint=None, char=False)  # faces
    def add_blob_shadow(self, pos, rx, rz, strength=0.35, layer=None, bias=0.0)  # Soft contact shadow
    def add_sprite(self, pos, draw_fn, layer=2, bias=0.0)  # draw_fn(surface, sx, sy, scale_px_per_m, z)
    def add_humanoid(self, hum, pose, pos, yaw, rifle_on=True, bias=0.0, tint=None, shadow=None)
    def add_line3d(self, a, b, col, width=1, layer=3)
    def flush(self, surface=None, bg=None)
    def flush_split(self, surface, split_depth, mid_fn)
    def flush_near_blur(self, surface, split_depth, blur_fn)
```
**`engine3d/gl.py`** (1380 lines)
```
def gl_available()
def gl_info() -> ~dict
class GLRenderer(SoftwareRenderer)
    def __init__(self, w, h, fog=(96, 98, 104), fog_start=18.0, fog_end=210.0, ps1_snap=False, dither=False)
    def invalidate_static(self)  # Call after editing baked objects' geometry in place
    def resize(self, w, h) -> ~bool
    def begin(self)
    def add_static(self)
    def add_dynamic(self, wverts, faces, bias=0.0, tint=None)
    def add_packed(self, arr)
    def add_resident(self, arr)
    def pack(wverts, faces, bias=0.0, tint=None)
    def add_humanoid(self, hum, pose, pos, yaw, rifle_on=True, bias=0.0, tint=None, shadow=None)
    def add_sprite(self, pos, draw_fn, layer=2, bias=0.0)
    def add_blob_shadow(self, pos, rx, rz, strength=0.35, layer=None, bias=0.0)
    def add_line3d(self, a, b, col, width=1, layer=3)
    def add_lines3d(self, segs, layer=4, depth_test=True)
    def flush_overlay(self, surface, bounds=None) -> ~tuple2
    def flush(self, surface=None, bg=None)
    def flush_split(self, surface, split_depth, mid_fn)
    def flush_near_blur(self, surface, split_depth, blur_fn)
    def release(self)
def Renderer(w, h, fog=(96, 98, 104), fog_start=18.0, fog_end=210.0, **kw) -> ~GLRenderer|SoftwareRenderer
```
**`engine3d/rig.py`** (1190 lines)
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
**`engine3d/hold.py`** (336 lines)
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
GRIPS keys: rifle sniper os12 k9 shotgun m7rifle akrifle ak74 lmg pistol
MODES keys: aim ready port carry one_hand pistol_aim pistol_ready
```
**`engine3d/textures.py`** (146 lines)
```
class Tex(tuple)
    def with_rgb(self, rgb) -> ~Tex
def tex(name, like=None, density=None, tint=False) -> ~Tex  # The colour a face takes to show texture ``name``
def version()  # Bumps whenever a texture is added
def glitter()  # Glitter strength per layer, in layer order
def stack()
tex names (assets/tex3d): ballast bone boxcar brick concrete crate m6_palette m7_bark m7_barnboard m7_dirt m7_furrow m7_grass m7_hay m7_leaf m7_plank m7_plaster m7_stone m7_stubble m7_tile m7_tin m7_track metal_rib pavement rust scorch sleeper snow snow_trod steel vault
```
**`cutscenes/m6world3d.py`** (2664 lines)
```
def rend(w=RW, h=RH)
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
def night(r, buf, t, top=(5, 8, 15), bot=(18, 26, 42), stars=55, moon=False, sodium=(44, 30, 20), seed=0, star_cut=0.45)
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
**`cutscenes/m7world3d.py`** (3150 lines)
```
def _t(name, col, tint=False)  # M7 texture at ground or prop density
def _bipyr(cx, cy, cz, r, up, dn, col, col2=None, n=6, moon=False)
def _fence(x0, z0, x1, z1, h=1.15, every=2.4, col=None, gap=None)
def ground() -> ~list
def hills()
def house(lit=False, burn=False)
def barn(burn=False, lamp=False)
def house_ruin()  # Bodi's house after the fire
def barn_ruin()  # Bodi's barn after the fire
def hay(n=3)
def shed()
def well(roof=True)
def well_roof()
def well_frame()  # Posts and crossbeam only
def well_bucket()
def tree(seed=0)
def contact(size, col=None)
def orchard()
def tractor(lit=False)
def motorcycle(lit=False)
def pig()
def field_dressing()
def poles()
def yard_dressing()
def skyline(lit)
def _hedgerow(x0, z0, x1, z1, seed=0)
def outer_dressing()
def landscape_dressing(look)
def old_orchard()
def poplars()
def crest_woods()
def road_dressing(lit)
def build_static(r, look, park=None, well_roof=True)
def setup(r, look)
def sky(r, buf, t, look, seed=0)
def pool(col, radius_m, intensity=0.3, squash=0.5)
def raid_fx(r, t, lit=True)
def wires(r)
def raid_pools(extra=())
def grade_raid(surface)
def stage(look, t, eye, tgt, fov, lights=(), hh=0.006, seed=0, size=None, park=None, well_roof=True) -> ~tuple2
def finish(surface, r, buf, seed, tag, t)
def mist(r, t, seed=0, n=9, intensity=0.1)
def sun(r, t, pos=(96.0, 9.0, -14.0))
def flame_mesh(pos, t, seed=0, size=1.0, heat=1.0, cam=None)
def smoke(t, seed=0, size_m=2.0)
def fire(r, pos, t, seed=0, size=1.0, smoky=True, layer=_fx.FX_LAYER)
def wall_fire(r, x, y, wall_z, t, seed=0, size=1.0, smoky=False, layer=_fx.FX_LAYER)
def burn_fx(r, t, grow=1.0, layer=_fx.FX_LAYER)
def burn_lights(t=0, boost=0.0) -> ~list
def burn_roof(r, fall)  # Burnt barn roof
def sparks(t, t0, seed=0, n=46, speed=7.0, life=2.6)
def mix(a, b, u)
def sit_pose(**kw)
def walk_pose(t, speed=1.0, tired=0.0)
def stand_pose(**kw)
def k(t, start, length)
LOOKS keys: dawn night raid burn
```
**`cutscenes/m5fx3d.py`** (535 lines)
```
def reduced_motion() -> ~bool
def shake_scale()  # RPE6 P9
def flash_scale()  # RPE6 P9
def glow(col, radius_m, t=0, pulse=0.0, flicker=0.0, seed=0, core=None, intensity=1.0, max_px=200)
def sodium_lamp(t, seed=0, radius_m=2.2, intensity=0.85)  # Street lamp
def window_glow(col, w_m, h_m, intensity=0.55, t=0, flicker=0.0, seed=0)
def crt_bloom(t, col=(120, 160, 220), w_m=0.6, h_m=0.45, intensity=0.6, seed=0)  # Cathode-ray bloom
def scope_glint(strength, col=(255, 236, 210))  # Lens glint off an optic
def wet_reflection(col, t, seed=0, length_m=2.4, width_m=0.35, intensity=0.5)  # Light smeared on wet ground/water
def dust_motes(t, seed=0, count=26, spread_m=(1.6, 1.4), col=(150, 140, 120))
def cap_flash(surface, knee=170, slope=0.25)  # RPE6 P9
def flash(age_ms, col=(255, 236, 200), radius_m=3.0, dur_ms=420)  # Blast / muzzle flash
def sparks(seed, age_ms, col=(255, 200, 120), n=18, speed_m=4.0, dur_ms=700)
def light_shaft(col, height_m=5.0, top_m=0.9, bot_m=2.1, t=0, seed=0, intensity=0.34, tilt=0.1)
def haze(col, radius_m=3.0, t=0, seed=0, intensity=0.16)  # Low ground fog
def glint(col, radius_m=0.35, t=0, seed=0, intensity=0.8, rate=1.0)  # Small shimmering highlight
def cig_smoke(t, seed=0, drift=(0.12, -0.5), intensity=0.3, life_ms=2600)  # A lit cigarette's wisp
def rain3d(r, t, seed=0, n_near=70, n_far=150, lights=(), col=(96, 104, 120), wind=(0.35, 0.1), ground=0.0, splashes=10, layer=FX_LAYER, near_d0=1.2, near_ln=0.5, surf...
def night_sky(r, buf, t, top, bot, *, stars=60, moon=False, clouds=4, sodium=None, mist=(26, 30, 40), seed=0, star_cut=0.0)
def handheld(t, amp, seed=0) -> ~tuple3  # Breathing-camera offset (m)
def shake(t, t_hit, dur_ms, amp) -> ~tuple4  # Decaying impact shake -> (dx, dy, roll_deg, px)
def set_cam(r, t, eye, tgt, fov, hh=0.0, seed=0, roll=0.0, shk=None)
```
**`cutscenes/m6fx3d.py`** (535 lines)
```
def glow(col, radius_m, t=0, pulse=0.0, flicker=0.0, seed=0, core=None, intensity=1.0, max_px=36)
def beacon(col, radius_m=0.35, t=0, period_ms=1500.0, phase=0.0, intensity=1.0, seed=0)  # Aviation / IFF lamp
def sodium_lamp(t, seed=0, radius_m=2.2, intensity=0.85)  # Yard or street lamp
def window_glow(col, w_m, h_m, intensity=0.55, t=0, flicker=0.0, seed=0, rim=False)  # A lit window, screen or doorway
def crt_bloom(t, col=(120, 160, 220), w_m=0.6, h_m=0.45, intensity=0.6, seed=0)
def flash(age_ms, col=(255, 236, 200), radius_m=3.0, dur_ms=420)  # Muzzle or blast flash
def haze(col, radius_m=3.0, t=0, seed=0, intensity=0.16)  # Low lit fog round a light
def light_shaft(col, height_m=5.0, top_m=0.9, bot_m=2.1, t=0, seed=0, intensity=0.34, tilt=0.1)
def powder(t, seed=0, spread_m=3.0, intensity=0.5, col=(188, 200, 220), puffs=14)  # Rotor wash on powder snow
def dither_lut(chan, np)
def ink(chan, np)
def apply_lut(surface, lut, np)  # Run a ``dither_lut`` table over the buffer
def present_crisp(src, dst)
def grade_cine(surface)
```
**`missions/m8/revenge/chase_set.py`** (2370 lines)
```
def road_x(z)
def road_yaw(z)
def ditch_y(z)  # The ditch jump
def ditch_pitch(z)  # Nose-up degrees for a body on the track at ``z``
def surface_y(x, z)
def tractor()  # Bodi's tractor, local forward +z
def trailer()
def toolbox_base()
def toolbox_lid()
def toolbox()  # Combined closed toolbox
def lmg_body()
def lmg_can()
def lmg_cover()
def lmg_yoke(h)
def jeep(col=GUARD_PAINT)  # A Guard car (car_m2 repainted), local forward +z
def wheeled(key)
def put_wheeled(r, key, pos, yaw=0.0, pitch=0.0, odo=0.0, roll=0.0)
def helicopter_parts()
def put_helicopter(r, pos, yaw, pitch, roll, main_spin, tail_spin, burned=False)
def rocket()
def gun_truck()
def barrier_arm()
def train()
def stratus(r, buf, t, pal=DAWN_CLOUDS)
def renderer()  # (renderer, None, 0, wreck spots), built on first use
def wrecks()
def frame(eye, tgt, fov, t=0, size=None, look='dawn', lights=())
def put(r, key, build, pos, yaw=0.0, pitch=0.0, roll=0.0)
def present(r, surface)
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
**`tools/ae_import_k93d.py`** (326 lines)
```
def _gltf(path) -> ~tuple2
def _acc(g, binbuf, i)
def _scan(g, binbuf) -> ~tuple3  # World-space triangles
def _cluster(verts, tris, cell) -> ~tuple2
def main()
```
**`tools/ae_import_mesh.py`** (210 lines)
```
def load_gltf(path) -> ~tuple2
def load_obj(path, mtl_colours) -> ~tuple2
def main()
```
Signature notation: `-> ~T` = return type inferred from the `return` statements (no annotation in source); `# text` = first docstring sentence.
<!-- /AUTO:sigs -->

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
- `src/game/save_adapter.py` (`capture` + restore): engine snapshot of `STATE`; `src/game/render3d_bridge.py`, `input_adapter.py`: boundary adapters (allowed).
- `src/game/topdown3d.py`: 2.5D top-down host (`CAMS`, `View`, `mouse_world`, `put`, `cast_shadows`) for M1-M6 `draw3d`, `missions/walk3d.py` and the MP arena (`ui/arena_view3d.py`).
- Cast look: owner `engine/anim/figure_kit.py` `SPECS`. `cutscenes/figure_kit.py` is a deprecated re-export (A-006). 3D cast: `cutscenes/cast3d.py` `spec3d` `humanoid3d` `weapon_asset` `rifle_asset` `ak74_asset` `third_person_rifle`.
- Core legacy: `core/state.py` `STATE` (weapon attrs live here), `core/save_system.py`, `core/mission_meta.py` (`meta_for`, `fail_text`), `core/cutscene_registry.py` (`register_scene_renderer`, `scene_renderer`), `core/dev_jumps.py` `DEV_JUMPS`, `core/artpack.py` (sprite-sheet access).
- 2D HUD shared: `ui/hud.py` (`THEME`, `MiniMap`, `draw_objective_panel`, `draw_pinned_radio`, `draw_combat_reticle`), `entities/art_cache.py` `get_panel_bg` (panel background passed to every widget).

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
- `WeaponInfo.from_state` knows only `k9_smg`, `os12`, else pistol (`SIDEARM`). Shotgun info is built explicitly by the 3D HUDs.

### 4.2 3D HUDs (M6 yard/train, M7 raid, M8 trap/kill/chase)
```
missions/m7/raid_hud.py draw          -> U.weapon(..., cw="fallow12", label="FALLOW 12", caliber="12GA", kind="shell", reload_ms=132)
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
- Editing `_panel_mag_icon` or `yard_hud.weapon` changes M6 2D, M6 yard, M6 train, M7 raid, M8 trap at once.

### 4.3 Cross-mission 3D scene reuse
- `missions/m8/revenge/trap3d.py` `TrapScene` borrows methods from `missions/m7/raid3d.py` `RaidScene` by class-attribute assignment: `_grab set_paused _snd say tracer hp hp_max _aim_ray _player_pose _guard_pose _ally_pose _cover_pose _project`, `_ground_move = RaidScene._move`, and calls `RaidScene.handle_event(self, event)`. `_draw_fx` is NOT borrowed: `TrapScene._draw_fx` draws its own layer-2 tracer ribbons (the raid's layer-3 lines painted over Biribel in OTS cameras). It imports `MAG, RESERVE0, RELOAD_S` from raid3d and uses `raid_world` (`truck`, `put`, `_ray_box`). Renaming/changing a `RaidScene` method or attribute it touches breaks M8.
- `trap3d` also uses `chase3d` (`_f_hash`, `_f_unit`) and `set3d` (`MAP_X0..`, `tile`, `_glyph`, `CATWALK_Z`, `DECK_X`).
- `cutscenes/m6world3d.py` is the shared 3D cast/set host (`hum(key, hd, wound, bloody, flags)`, `actor(r, key, pose, pos, yaw, t, ...)`, `add(r, m, bias)`, `life_pose`, `LAST`, `_gun_mesh`). Importers: every `missions/mN/draw3d.py`, `m3/wings3d.py`, `m6/train3d.py`, `m7/raid3d.py`, `m7/raid_world.py`, all `m8/revenge/*3d.py` + `beats.py` + `chase_set.py`, `cutscenes/{intro3d,m3broadcast3d,m3ko3d,m3staging,m6films,m6fx3d,m7films,m7world3d,m8films}.py`, `game/topdown3d.py`, `ui/arena_view3d.py`, `ui/mp3d.py`, `missions/walk3d.py`. Treat `hum()` flags and `actor()` signature as a cross-repo contract. Flag `"nopump"` (with `"shotgun"`) builds `shotgun_mesh(with_pump=False)` under GL key `|shotgun_nopump`; raid3d/trap3d use it and draw `shotgun_pump_mesh()` themselves so the pump slides.
- `cutscenes/m6fx3d.py` (fx), `cutscenes/death3d.py` (death) are shared by raid3d/trap3d. `cutscenes/m7world3d.py` = M7 farm set (raid3d).
- 3D holds: `engine3d/hold.py` `hold_cached`/`hold_weapon` with a `GRIPS` key; the weapon key comes from `hum._weapon` or `spec["rifle"]` (`weapon_of`).

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
- VO: `audio/voice.py` `play_line(speaker, text, radio=)` -> `find_line` matches text -> `VO_xxx` id in `audio/voice_manifest.py` -> file in `assets/voice`. Callers: `app.py`, `ui/radio.py`, `ui/speechbox.py`, `core/interactions.py`, mission flow/systems files. New line: `VO_xxx` row + `KNOWN_MISSING_AUDIO`, never `VOICE_ORDER`.
- Radio UI: `ui/radio.py` (`PORTRAIT_KEYS`, portraits from `spr_portraits` built by `tools/sprites/portraits.py`), fonts `ui/pixfont.py`.

### 4.7 Cutscenes
```
2D/legacy shots: missions/mN/meta.py -> game/timelines.shots(id, legacy) -> content/timelines/<id>.timeline.json
                 -> app.start_cutscene(shots, after_state) -> CutscenePlayer -> cutscenes/engine.py (+ registered renderers, core/cutscene_registry.py)
3D films:        cutscenes/m6films.py, m7films.py, m8films.py (+ meta.M8_SCENES, m8/revenge/beats.py fallback) -> m6world3d / post3d / weather3d
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
| LMG | `"lmg"`; hold cache key `"m8lmg"` | `content/meshes/lmg.mesh.json` (`tools/ae_import_lmg.py`) via `m6world3d._gun_mesh("lmg")`; `GRIPS["lmg"]` | none; HUD text `"LMG %d / %d"` in `chase3d.py` | `m8/revenge/chase3d.py` `GUN="lmg"`, `MAG=100`, `RELOAD_S=4.2` | M8 tractor chase |
| Molotov / bottle | `STATE` bottles; `handle_throw_bottle` | `content/meshes/molotov.mesh.json` in `missions/m1/draw3d.py` | `engine/ui/std/bottle_hud.py`; icon `game/art/m1/molotov_icon.py` | `entities/weapons.py` `handle_throw_bottle` `spawn_molotov_fire` `update_molotovs` `FireZone` | M1, M2 |
| Chair leg / shiv (melee) | `STATE.mission3_weapon` `"chair_leg"`/`"shiv"` | - | `game/art/m3/weapon_icon.py` | `entities/weapons.py handle_melee` (timer/damage table) | M3 breakout |
| Vehicles 3D | `truck_m7` `tractor_m7` `krap_van` `m3_van` `car_m2` | `content/meshes/*.mesh.json` (`tools/ae_import_{truck,tractor,krap_van,m3_van,car}.py`); `raid_world.truck()` | 2D: `spr_vehicles` via `core/artpack.vehicle(key)` | `m8/revenge/chase3d.py` (`HULL`, `SPEED`) | M7 raid, M8 chase/trap |

Weapon switching 2D: `entities/weapons.py switch_weapon` (pistol<->k9_smg or pistol<->os12). 3D trap: `trap3d._switch_weapon` (shotgun<->rifle, `[Q]`).

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
- Edit: `m7/` `raid3d.py` (module constants + `RaidScene`); `m8/revenge/` `trap3d.py` (`WPN_SPECS`, `_switch_weapon`, `_sync_weapon_attrs`, `BORE_LOCAL`), `chase3d.py`; `m6/` `yard3d.py`, `train3d.py`.
- Check: changing a `RaidScene` method changes `TrapScene` (4.3); `m7/` `raid_hud.py`, `m8/revenge/` `trap_hud.py` HUD `reload_ms` literals must match `RELOAD_MS` intent.
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
- 3D films: `cutscenes/` `m6films.py`, `m7films.py`, `m8films.py`; `m8/` `meta.py` `M8_SCENES`.
- Verify: `python tools/ae_timeline_check.py`, `python tools/smoke_test.py --only <mission>`.

**UI strings / menus**
- Edit: `content/strings/` `en.json`; callers `T("...")` in `ui/` `*.py` or `engine/ui/std/` `*.py`. Menus `ui/` `main.py`; settings/pause `system.py`; layout helpers `kit.py`.
- Verify: `python tools/ae_text_check.py` (fit + placeholders).

**Mission stage / checkpoint**
- Edit: `mN/` `flow.py` (stage + `set_slot_progress`), `meta.py`; `core/` `game_core.py` (`start_missionN_*`), `dev_jumps.py` `DEV_JUMPS`; root `app.py` `_SlotSelectState` resume table (+ `M*_RESUME` after-states).
- Check: `ui/` `mission_failed.py` `checkpoint_label`; `core/` `mission_meta.py`.
- Verify: `python tools/smoke_test.py --only mN`, `python -m compileall -q src`.

**New spoken line**: `audio/` `voice_manifest.py` (row + `KNOWN_MISSING_AUDIO`); caller text in `content/timelines/`, `content/dialogue/` or `mN/` `flow.py`. Canon: `docs/` `LORE.md`, `MISSION*_PLOT.md`.

## 7. Gotchas & gates per subsystem

**Art bake precedence**
- `AssetRegistry.get` loads the baked PNG before calling `render()`. Editing `src/game/art/mN/*.py` changes nothing in-game until `python tools/ae_bake.py --pack mN` rewrites `assets/baked/mN/`. `tools/build_all_sprites.py` rebakes only m5.
- `--check` fails on stale hashes; commit baked PNGs with the generator change.
- `game/content/m5/manifest.json` declares `m5/mag_icon` with `"variants": 6`, while `mag_icon.py` has `VARIANTS = 9` and `assets/baked/m5/` holds `mag_icon_0..8.png` (shell = 6-8). Check bake output count after edits.

**Callback contract**: `weapon_panel.draw(..., mag_icon=fn)` calls `fn(surface, mx, my, kind, rounds, cap, active)`: exactly 7 positional args, kinds `"stick"`/`"box"`/`"shell"`, 4 slots at `x+14+i*34`. Extra args (`reload_prog`, `incoming`) go through a closure (`yard_hud.weapon._icon`). Implementations: `m3/systems._draw_m3_mag_icon`, `m4/draw._draw_m4_mag_icon`, `m5/draw._draw_m5_mag_icon`, `m6/draw._panel_mag_icon`.

**Engine API**: any change to a `src/engine/**` public name or signature -> `python tools/ae_api_snapshot.py record` and commit `tests/api/engine_api.json`; `check` runs in `tools/ae_ci.py`. Every engine module needs `__all__`. Boundary: `python tools/check_boundaries.py` (engine never imports game code).

**Strings**: every static `T("key")` must exist in `en.json`; placeholders must match kwargs; values must fit their widget slot. Gate: `python tools/ae_text_check.py` (`--strict` fails unused keys).

**`_GameState_` AST rule**: `tools/m5_finale_cut_check.py` and `tools/m5_shadow_check.py` exec only the `_GameState_`/`_MissionCompleteState` class bodies from `src/app.py`. Helpers called from those methods must be on the class or imported inside the function, never new module-level functions.

**Shared mutable state**: read rebound globals as `import <owner> as _o; _o.name`, never `from owner import name` (AGENTS.md).

**HUD naming traps**: `WeaponInfo.from_state` never yields the shotgun; the 3D HUDs pass `cw="fallow12"`. OS-12 caliber is `"12GA"` in `from_state` but `"5.56X45"` in M8 `trap_hud`/`WPN_SPECS`. `RELOAD_MS` keys are HUD ids (`k9_smg`, `os12`, `fallow12`), not rig keys (`k9`, `shotgun`).

**3D**: never bypass `train3d._renderer()`/`buffer_size()` in M6 scenes; `ACA_M6_AUTO` stays opt-in; no per-frame allocation. `ACA_TD_2D=1` / `ACA_MP_2D=1` force 2D views.

**2.5D frame cost**: hosts that `buf.fill(VOID)` and draw nothing into `buf` before the flush call `r.flush(buf, bg=VOID)`, so GL clears the FBO instead of uploading the buffer (~4 ms with the upload sync; software ignores `bg`). M6 paints snow into `buf` first, so it must not pass `bg`. `td.put` caches packed placements per `(mesh, pos, yaw, roll, pitch)`; `td.cast_shadows` draws one sprite with an exact `bounds` box and `strict_occ=True` (without it the composite's <=12 % shortcut paints shadows over guards). Budget on a quiet PC: M1 render ~10 ms, locked 60 fps. Before trusting a slow timing, check for background CPU/GPU load; a uniform 2-5x slowdown across all sections is the machine, not the code.

**3D asset wiring**: 3 `assets/3D/*.glb` are read at runtime with no bake (§8.1 `R`): `m8/revenge/chase_set.py` `_load_heli_raw()`/`_load_rocket_raw()` -> `_load_glb()`, `cutscenes/m7world3d.py` `_scrambler_asset()` -> `_load_glb_surface()`; a missing GLB silently degrades to procedural geometry. `pig.mesh.json` is baked but unwired (live pig = procedural `cutscenes/m7pig3d.py`). `tools/ae_import_check.py` is an import-side-effect checker, not a mesh importer.

**Time**: gameplay/UI/draw read `engine.core.now_ms()`/`now_s()` only.

**Line endings**: LF/UTF-8 no BOM; scripted edits on Windows can write CRLF -> `python tools/ae_normalize.py --changed`.

**Gates**
- Fast loop: `python -m compileall -q src`, `python tools/smoke_test.py --only <area>` (`--list` names slow checks).
- Handoff: `python tools/smoke_test.py --fast` (full run for MP/sprites/M4 siege) -> `SMOKE TEST: OK`.
- Engine/data/API: `python tools/ae_ci.py --quick` or full `python tools/ae_ci.py` -> `AE CI: OK`. Known independent failures: mission4_stage_transitions, mission4_cinematic_arrest, mission5_shadow_finale geometry, mission5_harbour_art choreography.
- Content: `tools/ae_bake.py --check`, `tools/ae_text_check.py`, `tools/ae_timeline_check.py`, `tools/ae_dialogue_check.py`, `tools/ae_level_check.py`, `tools/ae_set3d_check.py`, `tools/ae_hold_check.py`.

## 8. 3D assets inventory (disk-verified)

Aliases: `A/` = `assets/3D/`, `M/` = `src/game/content/meshes/`, `C/` = `src/game/content/`, `T/` = `tools/`, `WP` = `T/ae_import_workstation_props.py`. Status: **B** baked via importer -> `M/<id>.mesh.json` (or `.rig.json`); **R** GLB/PNG read directly at runtime (no bake); **S** source-only / unimported. `A/` is flat (no subdirectories): 38 files = 33 `.glb`, 2 `.png`, 1 `.blend`, 1 `.blend1`, 1 stray `.pdf`. `M/` = 24 `.mesh.json` + 1 `.rig.json`. Baked ids below are the `M/` file stems.

### 8.1 `A/` - every source file + status
| `A/` file | St | Importer / caller -> baked id |
|---|---|---|
| `IPA-army-truck.glb` | B | `T/ae_import_truck.py` -> ? (auto: set baked id) |
| `K93D.glb` | B | `T/ae_import_k93d.py` -> `k93d` (+ emits `K93D_reticle.png`) |
| `K93D_reticle.png` | R | emitted by `T/ae_import_k93d.py`; loaded by `m6/train3d.py` `_reticle_image()` |
| `M3van.glb` | B | `T/ae_import_m3_van.py` -> `m3_van` |
| `M7Rifle.glb` | B | `T/ae_import_m7rifle.py` -> `m7rifle` |
| `Suppressed_Pistol.glb` | S | no importer/caller (comment only in `T/ae_export_ak74_glb.py`) |
| `TractorM7.glb` | B | `T/ae_import_tractor.py` -> `tractor_m7` |
| `ak-style-rifle.glb` | B | `T/ae_import_akrifle.py` -> `akrifle`; source-space ref for `T/ae_export_ak74_glb.py` |
| `ak74-style-rifle.glb` | S | export artifact of `T/ae_export_ak74_glb.py`; `ak74` is code-built by `T/ae_build_ak74.py`, never imported |
| `army-helicopter-ipa.glb` | R | `m8/revenge/chase_set.py` `_load_heli_raw()` -> `_load_glb()`; no baked `army-helicopter-ipa` |
| `dawg.glb` | B | `T/ae_import_dog.py` -> `dog_m7.rig.json` |
| `farm-ammo-crate-bare.glb` | S | unimported, no runtime caller |
| `hay.glb` | S | unimported, no runtime caller |
| `krap_van.glb` | B | `T/ae_import_krap_van.py` -> `krap_van` |
| `krap_van.png` | B | `T/ae_import_krap_van.py` -> ? (auto: set baked id) |
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
| `moneystack.glb` | S | unimported, no runtime caller |
| `pistol_lowpoly.blend` | S | Blender source for `pistol_lowpoly.glb`; never imported |
| `pistol_lowpoly.blend1` | S | Blender backup (`.blend1`); never imported |
| `pistol_lowpoly.glb` | B | `T/ae_import_pistol.py` -> `pistol` |
| `scrambler125.glb` | R | `cutscenes/m7world3d.py` `_scrambler_asset()` -> `_load_glb_surface()`, used by `motorcycle()` |
| `soviet_pc_tall.glb` | B | `WP` -> `pc_tall` |
| `soviet_pc_zarya_pk86.glb` | B | `WP` -> `pc_zarya` |
| `tactical_lmg(white).glb` | S | unimported, no runtime caller |
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
| `M3van.glb` | 2906 | 3.10x3.44x5.65 | 0.00,1.76,0.01 | 0.04 | mat0 #465048, mat1 #222724, mat2 #343a36, mat3 #171a17, mat4 #315863, mat5 #fff0b5 (+3) |
| `M7Rifle.glb` | 3556 | 13.86x4.51x1.26 | 1.69,-1.03,0.18 | -3.29 | mat0 #4a4538, mat1 #0e0e10, mat2 #b39b6e, mat3 #1d1f22 |
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
| `molotov.mesh.json` | `low-poly-molotov.glb` | `m1/draw3d.py` `_molotov` |
| `monitor_crt.mesh.json` | `low_poly_crt_monitor.glb` | `game/scenery3d.py` `prop()`/`workstation()`; `m2/draw3d.py`, `m3/wings3d.py`, `m3/draw3d.py`, `m5/draw3d.py` |
| `monitor_lcd.mesh.json` | `lowpoly_retro_lcd_monitor.glb` | `game/scenery3d.py` `prop()`/`workstation()`; `m3/wings3d.py`, `m5/draw3d.py` |
| `pc_tall.mesh.json` | `soviet_pc_tall.glb` | `game/scenery3d.py` `workstation()`; `m2/draw3d.py`, `m3/wings3d.py`, `m5/draw3d.py` |
| `pc_zarya.mesh.json` | `soviet_pc_zarya_pk86.glb` | `game/scenery3d.py` `workstation()`; `m2/draw3d.py`, `m3/wings3d.py` |
| `pig.mesh.json` | `low_poly_pig.glb` | **unused**: live pig is procedural `cutscenes/m7pig3d.py` (`pig_pose`, `pig_dead`, `pig_flat`) |
| `pill_bottle.mesh.json` | `low-poly-pill-bottle.glb` | `game/scenery3d.py` `medical_supplies()` |
| `pistol.mesh.json` | `pistol_lowpoly.glb` | `ui/mp3d.py` `pistol_mesh()` |
| `telephone_base.mesh.json` | `telephone-base-balanced-jet.glb` | `m8/revenge/epilogue3d.py` `telephone_base_mesh()` / `command_room()` |
| `telephone_handset.mesh.json` | `telephone-handset-balanced-jet.glb` | `m8/revenge/epilogue3d.py` `telephone_handset_mesh()`; `cutscenes/m8films.py` `heli_retardovici()` |
| `tractor_m7.mesh.json` | `TractorM7.glb` | `m7/raid_world.py` `_shape()`/`tractor_at()`; `cutscenes/m7world3d.py` `_tractor_asset()` |
| `truck_m7.mesh.json` | `IPA-army-truck.glb` | `m7/raid_world.py` `truck()`/`truck_at()`; `m1/draw3d.py` `_truck`; `m8/revenge/trap_world.py` |

All `M/*.mesh.json` are `ae.mesh/1`. Runtime entry: `game/render3d_bridge.py` `load_mesh_asset(ref)` / `MESHES_DIR` / `mesh_for_prim()`; `game/scenery3d.py` `prop()`/`display()` cache with procedural fallback. `tools/smoke_test.py` asserts the `k93d`, `akrifle` bakes and the reticle PNG.

### 8.3 `assets/tex3d/` + `C/` set/texture/preset ids
**`assets/tex3d/`** (32 flat files; drawn by `tools/tex3d_draw.py` / `tools/tex3d_draw_m7.py`; read by `engine3d/textures.py`, `m6/decor.py`, `cutscenes/ps2mat.py`):
- 30 `.png`: `ballast bone boxcar brick concrete crate m6_palette m7_bark m7_barnboard m7_dirt m7_furrow m7_grass m7_hay m7_leaf m7_plank m7_plaster m7_stone m7_stubble m7_tile m7_tin m7_track metal_rib pavement rust scorch sleeper snow snow_trod steel vault`
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
| `CREDITS` | `_CreditsState` | End credits after M8's CALL OF ACARISTAN card; hands to MISSION_COMPLETE (auto) |
| `BRIEFING` | `_BriefingState` | mission briefing (`BRIEFING_DURATION = 360`) |
| `WALK` | `_WalkState` | walking sim (`missions/walking_sim.py`) |
| `GAME` | `_GameState_` | all mission gameplay -> `core/game_core.game_update/game_draw` |
| `NOTEBOOK_INSPECT` | `_NotebookInspectState` | M1 notebook close-up (`ui/hud.draw_notebook_inspection`) |
| `PAUSED` | `_PausedState` | pause menu (`ui/system.draw_pause_menu`) |
| `DEATH` | `_DeathState` | death screen / Black Ledger death (`ui/system`) |
| `MISSION_COMPLETE` | `_MissionCompleteState` | report card + campaign save |
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
- `CutscenePlayer` (`app.py`) owns timing, `KO_CUT_CUES`, VO cues (`fired_cues`), fades; `_CutsceneState` resolves after-states (`M5_RESUME` .. `M8_RESUME`, `MISSIONn_COMPLETE`, `MISSION_COMPLETE`, `GAME`).
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
| M4 | `MISSION4` THE CAPITAL - 48H CURFEW (The Aftermath) | street, station, tower (`start_mission4_{station,tower}_checkpoint`) | `apc components draw3d escort fortify siege` | `levels/m4.{street,station}`, `dialogue/m4.liaison`, `timelines/m4.{intro,ending,arrest_beats}`; art `game/art/m4` | `--dev-mission4[-game,-intro,-station,-tower]` |
| M5 | `MISSION5` THE CAPITAL - EMERGENCY RULE (Martial Law) | hq, quarter, printworks, tunnel (`start_mission5_*_checkpoint`) | `components decor decor_interior decor_paint draw3d finale_audio finale_script inspect_art inspect_art_street inspect_fpv quarter render tram_wreck water`; cutscenes `m5*` | `levels/m5.{hq,quarter,print,tunnel}`, `dialogue/m5.maru`, `timelines/m5.{intro,ending}`, `sets/m5.vasile_office`; art `game/art/m5` | `--dev-mission5[-game,-hq,-printworks,-tunnel,-intro,-ending]` |
| M6 | `MISSION6` THE BORDER - WHITEOUT | `STAGES = customs, noman, rail, boxcar, train`; checkpoints customs/noman/rail/train; yard fight after Volkov's death; finale cutscene-only | `combat hud3d m6_audio palette3d perf stealth train3d yard3d yard_brain yard_dress yard_hud draw3d bloc3d/`; cutscenes `m6films m6world3d m6fx3d` | shot tables in `m6/meta.py`; `assets/tex3d/*` | `--dev-mission6[-game,-rail,-boxcar,-train,-shootout,-yard,-heli,-crossing,-ending,-3d]` |
| M7 | `MISSION7` FALLOW GROUND | `STAGES = arrival, chores, runner, prep, raidin, raid, finale, choice`; `start_mission7_stage/raid/outro` | `farmyard goat_rescue minigames colonel raid3d raid_brain raid_hud raid_world choice maps m7_audio`; cutscenes `m7films m7runner m7goat m7world3d m7pig3d m7palette3d` | `levels/m7.farm`, `timelines/m7.*` (6), `M7_SCENES`; `assets/tex3d/m7_*` | `--dev-mission7[-arrival,-chores,-runner,-prep,-raid,-raid-w2,-raid-w3,-raid-prepped,-finale,-choice,-outro]` |
| M8 | `MISSION8` THE CALL | route `STATE.m8_route` (written by M7 `choice`): revenge = `meet trap gantry friends kill descent chase epilogue` (`FIGHT_STAGES = trap, gantry`); duty = one placeholder beat; `start_mission8_stage(stage, route)` | `m8_audio`; `revenge/{set3d,trap3d,trap_world,trap_brain,trap_hud,kill3d,chase3d,chase_set,epilogue3d,beats}`; `duty/` reserved; cutscenes `m8films` | `timelines/m8.{meet,friends,descent,heli,epilogue}`, `M8_SCENES` | `--dev-mission8[-trap,-gantry,-friends,-kill,-chase,-heli,-ending]` |

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
| `ACA_M6_RAIL_25D=1` | use the 2.5D painter on the M6 rail stage (default fast 2D) | `m6/draw.py` |
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
| `ACA_UPDATE_URL` / `ACA_GITHUB_REPO` / `ACA_DEV=1` | updater source override / launcher dev mode | `launcher/updater.py`, `launcher/window.py` |
| `ACA_FROM_LAUNCHER=1` | set by the launcher on the child game process | `launcher/window.py` |
| `SDL_VIDEODRIVER=dummy`, `SDL_AUDIODRIVER=dummy` | headless (smoke test and tools set these) | tools |

## 12. Dev affordances

- **CLI** (`app._apply_dev_args`, table `core/dev_jumps.DEV_JUMPS`: name -> (`--dev-*` flag, description)): `--dev-<target>` and short aliases (`--m3-kill-order`, `--m6-yard`, ...), `--jump <name>`, `--list-jumps`, `--continue`, `--dev-slot-select`, `--dev-safe`/`--safe`, `--dev-mp-host`/`--dev-mp-join` with `--mp-map --mp-players --mp-port`, `--trailer-bot`/`--trailer-act` (`src/tools/trailer_bot.py`), `--dev-audio-parade`.
- **Hotkeys** - global: `F11` fullscreen, `F12` level editor (`core/level_editor.py`, gameplay only; saves `maps/*.map`, never loaded), backquote console (`core/console.py`). Devtools (`game/devtools.py`): `F3` overlay (frame/sim/draw ms, scene stack, cache line), `F4` collision view, `F5` level view, `F6` timeline view, `F7` skip cutscene. GAME: `F9` jump to exfil (M1), `V` melee, `M` minimap.
- **Console commands** (`app._console_*`): events tail, `timeline play <id> [t_ms]`, heat, reload, skip cutscene.
- **GUI panel**: `python tools/dev_panel.py` (clickable mission jumps).
- **Headless capture**: per-mission `tools/mN_td3d_shots.py`, `m6_shots.py`, `m8_chase_shots.py`, `render_*.py`; `tools/ae_loop.py` drives the real main loop headless.

### 12.1 Dev jump targets (auto)

From `core/dev_jumps.DEV_JUMPS`; use as `--jump <target>` or the listed flag.

<!-- AUTO:devjumps -->
| target | flag | what |
|---|---|---|
| `m0` | `--dev-mission0` | Mission 0 - Depot (tutorial mission, playable) |
| `m1` | `--dev-m1` | Mission 1 opening handoff (dropoff radio cut, then playable) |
| `m1-game` | `--dev-m1-game` | Mission 1 warehouse from the start (playable, no cutscene) |
| `m1-safe` | `--dev-safe` | Mission 1 at the notebook safe keypad (code 742) |
| `walk` | `--dev-walk` | Walking sim harbor exploration from the start |
| `walk-after` | `--dev-walk-after` | Walking sim harbor right after the rig-strike cutscene (van ready) |
| `m2` | `--dev-mission2` | Mission 2 intro cutscene |
| `m2-game` | `--dev-mission2-game` | Mission 2 gameplay from the start |
| `m2-sniper` | `--dev-mission2-sniper` | Mission 2 Route 12 sniper ambush |
| `m2-after-sniper` | `--dev-mission2-after-sniper` | Mission 2 right after the sniper fight |
| `m2-flank` | `--dev-mission2-flank` | Mission 2 flank cutscene / phase |
| `m2-truck` | `--dev-mission2-truck` | Mission 2 truck stage |
| `m2-evidence` | `--dev-mission2-evidence` | Mission 2 evidence-completion cinematic |
| `m3` | `--dev-mission3` | Mission 3 intro cutscene |
| `m3-game` | `--dev-mission3-game` | Mission 3 breakout gameplay (post-breach, chair leg) |
| `m3-comms` | `--dev-mission3-comms` | Mission 3 comms wing (via service transition cutscene) |
| `m3-archives` | `--dev-mission3-archives` | Mission 3 archives wing checkpoint |
| `m3-kill-order` | `--dev-mission3-kill-order` | Mission 3 kill-order ground floor (+ KO intro cutscene) |
| `m3-ledger` | `--dev-mission3-ledger` | Mission 3 black ledger debug |
| `m3-vostral` | `--dev-mission3-vostral-cutscene` | Mission 3 Vostral acquisition cinematic |
| `m3-archives-cutscene` | `--dev-mission3-archives-cutscene` | Mission 3 comms-to-archives transition cutscene |
| `m3-broadcast-transition` | `--dev-mission3-broadcast-transition` | Mission 3 kill-order-to-broadcast transition cutscene |
| `m3-broadcast` | `--dev-mission3-broadcast` | Mission 3 broadcast wing checkpoint (Slice 6 gauntlet) |
| `m3-upload` | `--dev-mission3-upload` | Mission 3 at the station PC, upload OS already open |
| `m4` | `--dev-mission4` | Mission 4 intro cutscene |
| `m4-game` | `--dev-mission4-game` | Mission 4 aftermath street gameplay from the start |
| `m4-station` | `--dev-mission4-station` | Mission 4 radio-station interior checkpoint |
| `m4-tower` | `--dev-mission4-tower` | Mission 4 transmitter hold (siege checkpoint) |
| `m5` | `--dev-mission5` | Mission 5 intro bulletin cutscene |
| `m5-hq` | `--dev-mission5-hq` | Mission 5 Guard HQ walking sim (Vasile's office) |
| `m5-game` | `--dev-mission5-game` | Mission 5 Lower Quarter gameplay (HQ skipped) |
| `m5-printworks` | `--dev-mission5-printworks` | Mission 5 MAG print works (find Maru, then the raid) |
| `m5-tunnel` | `--dev-mission5-tunnel` | Mission 5 basement tunnel escort (deepest resume point) |
| `m5-ending` | `--dev-mission5-ending` | Mission 5 final cutscene (shadow finale at the river) |
| `m6` | `--dev-mission6` | Mission 6 intro cutscene |
| `m6-game` | `--dev-mission6-game` | Mission 6 top-down gameplay from customs (no intro) |
| `m6-crossing` | `--dev-mission6-crossing` | Mission 6 top-down no-man's-land crossing |
| `m6-rail` | `--dev-mission6-rail` | Mission 6 top-down rail yard |
| `m6-boxcar` | `--dev-mission6-boxcar` | Mission 6 rail yard at Volkov's boxcar (E starts the 3D talk) |
| `m6-train` | `--dev-mission6-train` | Mission 6 train checkpoint |
| `m6-3d` | `--dev-mission6-3d` | Mission 6 interactive 3D train scene (shootout) |
| `m6-shootout` | `--dev-mission6-shootout` | Mission 6 interactive 3D train scene (shootout) |
| `m6-yard` | `--dev-mission6-yard` | Mission 6 straight into the 'Who is Ucilev?' yard fight |
| `m6-ending` | `--dev-mission6-ending` | Mission 6 ending cutscene |
| `m6-heli` | `--dev-mission6-heli` | Mission 6 ending from the helicopter finale |
| `m7` | `--dev-mission7` | Mission 7 Fallow Ground from the top (arrival film) |
| `m7-arrival` | `--dev-mission7-arrival` | Mission 7 drop-off film, then the chores |
| `m7-chores` | `--dev-mission7-chores` | Mission 7 top-down farm chores |
| `m7-runner` | `--dev-mission7-runner` | Mission 7 Alex-on-the-bike film |
| `m7-prep` | `--dev-mission7-prep` | Mission 7 top-down prep (pick 2 of 3) |
| `m7-raid` | `--dev-mission7-raid` | Mission 7 3D raid, no preps (--m7-preps=tractor,shed,loft --m7-cp=1/2) |
| `m7-raid-prepped` | `--dev-mission7-raid-prepped` | Mission 7 3D raid with all three preps |
| `m7-raid-w2` | `--dev-mission7-raid-w2` | Mission 7 3D raid from checkpoint 1 (orchard cleared, trucks next) |
| `m7-raid-w3` | `--dev-mission7-raid-w3` | Mission 7 3D raid from checkpoint 2 (trucks cleared, barn fire next) |
| `m7-finale` | `--dev-mission7-finale` | Mission 7 burning-farm night film |
| `m7-choice` | `--dev-mission7-choice` | Mission 7 radio choice (sets the Mission 8 route) |
| `m7-outro` | `--dev-mission7-outro` | Mission 7 outro film, route defaults to duty |
| `m8` | `--dev-mission8` | Mission 8 The Call, Revenge route from the top (meet beat) |
| `m8-trap` | `--dev-mission8-trap` | Mission 8 3D trap fight on Route 12 (--m8-cp=1/2/3) |
| `m8-gantry` | `--dev-mission8-gantry` | Mission 8 3D gantry climb to Vasile |
| `m8-friends` | `--dev-mission8-friends` | Mission 8 catwalk beat with Vasile |
| `m8-kill` | `--dev-mission8-kill` | Mission 8 standoff on the catwalk, one shot |
| `m8-chase` | `--dev-mission8-chase` | Mission 8 tractor chase (--m8-cp=1/2/3/4) |
| `m8-heli` | `--dev-mission8-heli` | Mission 8 tractor chase helicopter mini-boss |
| `m8-ending` | `--dev-mission8-ending` | Mission 8 chase ending at the crossing (last jeep down) |
| `m8-epilogue` | `--dev-mission8-epilogue` | Mission 8 epilogue films (State TV, Commander, funeral) |
| `m8-credits` | `--dev-mission8-credits` | Mission 8 end credits |
| `trailer-m1` | `--dev-m1-game` | Trailer Act I warehouse take (bot: breach/molotov) |
| `trailer-m2-killbox` | `--dev-mission2-game` | Trailer Act II killbox take (bot: OS-12 hold + flank) |
| `trailer-m2-evidence` | `--dev-mission2-evidence` | Trailer Act II evidence take (bot: control building) |
| `trailer-m3-breakout` | `--dev-mission3-game` | Trailer Act III breakout take (bot: shiv/sidearm) |
| `trailer-m3-comms` | `--dev-mission3-comms` | Trailer Act III relay take (bot: power->auth->tune, Volkov cover) |
| `slot-select` | `--dev-slot-select` | Save-slot screen directly (add --continue for CONTINUE variant) |
| `audio-parade` | `--dev-audio-parade` | Comms wing with verbose sound logging (volume tuning) |
| `mp-host` | `--dev-mp-host` | Multiplayer arena panel, hosting on --mp-port (default 27017) |
| `mp-join` | `--dev-mp-join` | Multiplayer arena panel, joining --mp-join ADDR (host:port) |
<!-- /AUTO:devjumps -->

## 13. Persistent files (repo root, resolved from `Path(__file__).parents[2]`)

| File | Owner | Content |
|---|---|---|
| `save_data[SUFFIX].json` | `core/save_system.py` | `current_slot` + 3 slots (`progress` "m1".."m8", `checkpoint`, flags, mission-complete records); `set_slot_progress`, `set_slot_flags`, `save_mission_complete` |
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
| `assets/music/` | 14 | `ost/` (album, `tools/build_ost.py` from `tools/ost/`), `trailer/`, `newtrailer/` |
| `assets/voice/` | ~728 | per-speaker folders + `VO_xxx.ogg/.wav`, `_radio_cache` (`tools/build_radio_cache.py`); index `src/audio/voice_manifest.py` |
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

**Launcher / updater** - doc `docs/LAUNCHER.md`. `launcher.py` (`--demo-update`, `--check-only`) -> `src/launcher/window.py` `LauncherApp`/`run_launcher` -> `launch_game_process`; `src/launcher/updater.py` (manifest check, sha256 integrity, downgrade guard). Publish: `tools/publish_update.py`.

**Builds** - `build.bat`, `tools/build_windows.py` (PyInstaller `--onedir`), `tools/ae_package.py` (zip, `ae.package/1`), `tools/itch_push.py` (butler), `tools/zip_project.py`, `tools/slim_tree.py` (dry-run cleanup), `tools/overlay_cleanup.py`. `Launch Game.bat` runs the game.

## 17. More one-shot bundles

**New mission** - `python tools/ae_new_mission.py` scaffolds an RPE6 host (M0 is the reference); follow `docs/engine/tutorial_add_mission.md`. Wire: `core/game_core.py` (import, `_is_missionN_active`, `start_missionN*`, update/draw routing, restart), `core/mission_meta.py`, `core/dev_jumps.py`, `app.py` slot resume + after-states, `ui/mission_failed.py`, `content/strings/en.json`. Verify `python tools/ae_mission0_check.py` (pattern), `smoke --only <mission>`.

**New 3D gameplay scene** - copy the contract in 9.7 (module API + STATE active flag + `force_finish` fault path); route events in `app._GameState_.handle_event` (9.5) and resume in `_PausedState`; renderer via `engine3d.Renderer`, cast via `cutscenes/m6world3d.hum/actor`; HUD via `m6/yard_hud.py` + `m6/hud3d.py`. Add a `--dev-*` jump.

**New film / mid-mission cut** - builder function in `cutscenes/m7films.py` / `m8films.py` (or `m6films.py`), register in `m7/meta.M7_SCENES` / `m8/meta.M8_SCENES` / `m6/meta.M6_MID_CUTSCENES` / `m5/meta.M5_MID_CUTSCENES`, shot list in `content/timelines/<id>.timeline.json`, request from flow (`take_cutscene_request` or `STATE.request_mN_cutscene`). Verify `ae_timeline_check.py`, headless stills (`tools/m8_descent_shots.py`-style).

**Settings option** - `core/settings_store.py` (default + persist), `core/user_settings.py` (live), `app._current_settings_dict` / `handle_settings_event`, `ui/system.draw_settings`, label in `en.json`; typed field in `engine/settings/model.py` if it is an engine setting. Verify `smoke --only settings`, `ae_text_check.py`.

**Key binding / gamepad** - `engine/input/model.DEFAULT_ACTIONS` (`move_* fire interact reload sprint advance skip`), `game/input_adapter.py` (persist in `settings["bindings"]`). Many sites still read raw `K_*`; the adapter forces canonical keys down.

**Cosmetic / Outfitter item** - `core/appearance.py` catalog (price, kind, label), `entities/adornments.py` (2D head gear draw), `ui/mp3d.py` (3D rig + portrait), `ui/shop.py`. Verify `smoke --only outfitter,appearance,cosmetic`.

**Multiplayer gameplay rule** - `missions/arena.py` (sim + rules), `net/protocol.py` (wire fields; keep `normalize_*`), `net/match.py`; never trust client data (validate in `core/appearance.normalize`). Verify `smoke --only mp,arena,match` (full run, not `--fast`), `tools/mp_net_soak.py`.

**Import a 3D model** - drop GLB in `assets/3D/` (pre-commit hook adds an `(auto)` row to §8.1), write `tools/ae_import_<name>.py` (reuse `ae_import_k93d._gltf/_scan/_cluster`) or use `tools/ae_import_mesh.py`, output `content/meshes/<id>.mesh.json`, consume via `render3d_bridge.load_mesh_asset` or `game/scenery3d.prop` with a procedural fallback; fill §8.2.

**Level geometry (2D maps)** - mission `maps.py`/`map.py` via `core/mapbuilder.MapBuilder` (AGENTS.md map contract), then `python tools/ae_level_export.py` to refresh `content/levels/*.level.json`; `ae_level_check.py` must stay OK.

**Enemy brain (3D)** - `engine/ai` (bt, senses, cover, squad) + per-scene brains `m6/yard_brain.py`, `m7/raid_brain.py`, `m8/revenge/trap_brain.py`; tests `tests/unit/test_engine_ai.py`.

**Music / SFX** - SFX: `audio/audio.py` registry + `audio.play(name)`; mission banks (`m1_audio`, `m6_audio`, `m7_audio`, `m8_audio`, `m5/finale_audio`) synthesise PCM and `warm()` at load; gameplay OST mixing `core/score.py`; zone ambience `core/ambience.py`; footsteps `core/surfaces.py`. Never synthesise during a fight (M6 rule).

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
- **2.5D** - top-down rules drawn by `engine3d` (`game/topdown3d.py`, `missions/mN/draw3d.py`); 2D path stays as fallback.

Docs worth knowing (`docs/`): story `LORE.md`, `MISSION3..8_PLOT.md`, `MISSION3_KILL_ORDER.md`, `FIXES_STORIES.md`; plans `MASTER_ACTION_PLAN.md`, `M4_OVERHAUL_PLAN.md`, `MISSION5_BUILD_PLAN.md`, `M5_FINALE_REBUILD_PLAN.md`, `M6_HALOS_AND_ENDING_PLAN.md`, `M6_TOPDOWN_ART_BRIEF.md`, `M1_REWORK_HANDOFF.md`, `PLAN_1..4_*.md`, `TRAILER3D_PLAN.md`, `OIL_RIG_BOMBING_CUTSCENE.md`; perf `M6_3D_PERF.md`; audits `AUDIT_T1..T8_*.md`; systems `KRAPNET_MULTIPLAYER.md`, `LAUNCHER.md`, `README_ENV_SETUP.md`; log `worklog.md`; engine `docs/engine/{STATUS,ARCHITECTURE,ADAPTERS,BUGS,CHANGELOG,AUDIT}.md`, `subsystems/<kernel>.md` (one per engine package), `adr/`, `tutorial_add_mission.md`. Graph: `src/graphify-out/GRAPH_REPORT.md`.

**Known doc drift** (code wins): `AGENTS.md` says Mission 8 is not implemented (the Revenge route is playable; Duty is a placeholder) and its repository layout lists only `m1`-`m3`; its sprite-pipeline note points at `src/art/m5/_kit.py` (now `src/game/art/m5/_kit.py`, which `tools/sprites/kit.py` reads). Comments in `core/outfits.py` and `entities/art_cache.py` still cite `art/m5/...` paths. `src/art/m5/*.py` (other than `__init__.py`) are stale tracked copies that never run.

## 20. Every source file (`src/`, generated from module docstrings)

Format: `file` lines - first docstring sentence (or public names). Content data under `src/game/content/` is in §14 and §8. Maintained by `python tools/sync_arch_map.py` (line counts, new/removed files; hand-edited descriptions are kept). Monolith slices: §20.1; slice bundles: `python tools/ai_bundle.py path:start-end`.

**`src/`**

- `app.py` 4804 - Public: `handle_settings_event`, `trigger_transition`, `CutscenePlayer`, `start_cutscene`, `apply_display_mode`, `draw_slot_select_screen`, `start_briefing`, `finish_briefing`

**`src/art/`**

- `__init__.py` 1 - Hand-authored pixel-art sprites (pygame-only, no game imports).

**`src/art/m5/`**

- `__init__.py` 24 - Shim (A-008): aliases every `art.m5.<name>` in `sys.modules` to `game.art.m5.<name>`.
- `_kit.py` + 20 sprite modules: **stale tracked copies, never executed** (the shim aliases win). Edit `src/game/art/m5/`.

**`src/audio/`**

- `__init__.py` 1 - audio package.
- `audio.py` 3454 - Public: `AudioManager`
- `mixlock.py` 63 - Pause/resume for the mixer without the alt-tab deadlock.
- `voice.py` 863 - Voice-over playback for Call of Acaristan.
- `voice_manifest.py` 545 - Generated from voice_lines.xlsx - (VO ID, speaker, line) for every voiced line.

**`src/core/`**

- `__init__.py` 1 - core package.
- `ambience.py` 183 - zone-driven world ambience layers.
- `appearance.py` 583 - Character appearance: the cosmetic catalog, the appearance value object, and the single validator that both the save...
- `artpack.py` 31 - core.artpack - deprecated path (RPE6 Phase 2, A-006).
- `camera.py` 341 - Shared camera and bullet helpers.
- `config.py` 905 - Public: `resource_path`, `windowed_size`, `make_grain`, `draw_sky_gradient`, `draw_building`, `draw_cityscape`, `draw_rain`, `rain_drawables`
- `console.py` 343 - Public: `Console`
- `cutscene_registry.py` 60 - Cutscene scene renderers registered by scene id (RPE6 D1, boundary rule 4).
- `dev_jumps.py` 160 - registry of dev jump targets.
- `fixedstep.py` 432 - Fixed-timestep accumulator, for making the simulation host-independent.
- `font_coverage.py` 60 - Font glyph coverage - the fontTools half of §6.13 (dev/audit only).
- `frame_pacer.py` 64 - Frame pacing for the 60 Hz fixed-step loop: `Pacer.wait()` once per frame in `app._legacy_frame`; whole steps per frame, 60/30 fps lock (bug-333).
- `fsm.py` 171 - Finite State Machine infrastructure for Acaristan.
- `game_core.py` 591 - Proxy facade that delegates to split modules.
- `hands.py` 299 - Canonical hand renderers - the reference-anatomy model (dorsal view).
- `interactions.py` 692 - Player interactions with the world: doors, safe, NPCs, alarms.
- `json_store.py` 41 - Shared atomic JSON persistence helpers for save_data.json / settings.json.
- `level_editor.py` 224 - Public: `LevelEditor`
- `lighting.py` 20 - core.lighting - deprecated path (RPE6 Phase 2, A-006).
- `mapbuilder.py` 143 - Shared tilemap authoring helper (pure python, no pygame).
- `mission_meta.py` 106 - Per-mission display metadata (operation name + failure-screen copy).
- `outfits.py` 161 - Biribel's Mission 5 kit, as data (one source of truth).
- `profile_store.py` 234 - The global profile: Acaribucks wallet, owned cosmetics, equipped loadout.
- `props.py` 378 - shared set-dressing prop painters.
- `render_util.py` 17 - core.render_util - deprecated path (RPE6 Phase 2, A-006).
- `save_system.py` 289 - 3-slot JSON save system for campaign progress.
- `scene_mirror.py` 70 - RPE6 ADAPTER A-005: mirror the legacy GameStateManager onto an engine SceneStack.
- `score.py` 139 - the OST under quiet gameplay.
- `settings_store.py` 179 - Settings store - persistent JSON-backed user preferences.
- `state.py` 481 - Central game state singleton.
- `staticlayer.py` 109 - chunked bake of the static world (phase 0).
- `surfaces.py` 59 - floor-material zones for footstep timbre selection.
- `user_settings.py` 112 - Live user settings - shared across all gameplay modules.

**`src/cutscenes/`**

- `__init__.py` 46 - Package cutscenes - re-export facade.
- `cast.py` 112 - cutscene cast sprites.
- `cast3d.py` 156 - 3D (engine3d.Humanoid) looks derived from the 2D cast sheet.
- `chair.py` 1296 - Split part. (no docstring)
- `death3d.py` 124 - Gameplay death falls for 3D guards (Mission 7 raid, Mission 6 yard).
- `engine.py` 692 - Split part. Public: `draw_cutscene_scene`, `draw_typewriter_title`, `reset_dialogue_slide`, `draw_dialogue_box`, `draw_cinematic_subtitle`, `draw_film_caption`, `draw_volkov_dossier_overlay`
- `figure_kit.py` 11 - cutscenes.figure_kit - deprecated path (RPE6 Phase 2, A-006): the kit is ``engine.anim``.
- `intro3d.py` 1135 - engine3d takes for the opening narration (``core.cutscene1``).
- `k9.py` 390 - K-9 armory pickup: one continuous, deterministic, software-safe take.
- `m3broadcast.py` 810 - Mission 3 - Kill Order -> Broadcast transition cinematic (Slice 5 -> 6).
- `m3broadcast3d.py` 456 - Seekable 3D bridge from the loading dock to the state television studio.
- `m3cell.py` 916 - Split part. (no docstring)
- `m3cell_balaceanu_patch.py` 7 - (no docstring)
- `m3ending.py` 373 - Mission 3 finale cutscene (the Vostral read live on air).
- `m3ko.py` 674 - Mission 3 - Kill Order transition cinematic (Slice 5 cutscene rehaul, v2).
- `m3ko3d.py` 425 - Kill Order intro: directed 3D breach, stairs, cover and empty-dock preview.
- `m3ops.py` 1194 - Split part. (no docstring)
- `m3staging.py` 386 - M3 service-exit bridge: one 3D set, four directed camera setups.
- `m4aftermath.py` 741 - Mission 4 finale + intro cutscene art (The Aftermath).
- `m5decal.py` 108 - Sprite -> wall decal mesh for the M5 3D cutscenes.
- `m5ending3d.py` 708 - Authored M5 ending set and distance-driven actor blocking.
- `m5fx3d.py` 535 - FX kit for the Mission 5 3D cutscenes (m5martial3d / m5mid3d).
- `m5harbour_art.py` 1038 - Authored blocky harbour art for M5; canonical people and motion stay intact.
- `m5martial.py` 693 - Mission 5 intro + ending cutscene art (Martial Law).
- `m5martial3d.py` 1232 - W7: true-3D (engine3d) takes of every Mission 5 cutscene.
- `m5mid3d.py` 1986 - Mission 5 mid-mission cutscenes (round 2).
- `m5shadow3d.py` 1209 - The rebuilt M5 finale: one fresh 3D set, actor clock and camera language.
- `m5studio.py` 149 - the state-TV studio shared by the M5 bulletin's 3D take (m5martial3d._bulletin) and its 2D fallback (m5martial._draw_...
- `m6films.py` 3218 - engine3d takes and 2D fallbacks for every Mission 6 film.
- `m6fx3d.py` 535 - the Mission 6 FX kit: late-PS2 night light, smoke and haze.
- `m6world3d.py` 2664 - engine3d sets and actor kit for the Mission 6 films.
- `m7films.py` 252 - Mission 7 films: the dawn drop-off (beat 1), the raid lead-in (beat 5) and the burning farm (beat 6).
- `m7goat.py` 980 - Mission 7 bridge: the wire was never mended, and Bodi's goat gets out.
- `m7palette3d.py` 91 - The 2D top-down M7 farm palette, for the 3D farm (raid and films).
- `m7pig3d.py` 281 - Bodi's low-poly pig and distance-driven, cached walk poses.
- `m7runner.py` 1355 - Mission 7 beat 3: Alex arrives with the mansion plan and a sketch of the farm.
- `m7world3d.py` 3150 - Mission 7 farm: shared 3D builder for the drop-off, finale and raid.
- `m8films.py` 1112 - Mission 8 Revenge films: the meet at Route 12, Old Friends on the catwalk, and the epilogue.
- `oil_rig_3d.py` 136 - True-3D Oil Rig Bombing cutscene (engine3d).
- `post3d.py` 192 - Cinematic post stack for cutscene shots (RPE6 Phase 11 step 5).
- `ps2mat.py` 98 - PS2 pixel textures for sets authored in flat colour.
- `route12.py` 1791 - Split part. Public: `draw_factory`, `draw_oil_rig`, `draw_propaganda_poster`, `draw_mag_graffiti`, `draw_van_exterior`, `draw_van_interior`, `draw_van_handoff`, `draw_route12_black`
- `van3d.py` 439 - engine3d take of the KRAP van establishing shot (scene ``van_exterior``).
- `weather3d.py` 152 - Data-driven weather & atmosphere for 3D sets (RPE6 Phase 11 step 6).

**`src/engine/`**

- `__init__.py` 9 - Retardovici Pulse Engine 6 Gold (RPE6): the Call of Acaristan engine.

**`src/engine/ai/`**

- `__init__.py` 27 - engine.ai - enemy brains: behaviour trees, senses, squads and cover.
- `bt.py` 275 - engine.ai.bt - a small behaviour tree runtime.
- `cover.py` 143 - engine.ai.cover - cover spots around solid boxes, and picking one.
- `senses.py` 131 - engine.ai.senses - what an agent knows about its target.
- `squad.py` 91 - engine.ai.squad - what a group of agents shares.

**`src/engine/anim/`**

- `__init__.py` 12 - engine.anim - animation (RPE6).
- `figure_kit.py` 1754 - shared cast renderer in the "Balaceanu Arrest" house style.
- `pose_cache.py` 50 - Pose cache: render-once surfaces for parameterised procedural bodies.

**`src/engine/assets/`**

- `__init__.py` 39 - engine.assets - asset access (RPE6).
- `_artpack.py` 288 - loaded-sprite registry with procedural fallback.
- `_sprites.py` 44 - tiny cached PNG loader with graceful fallback.
- `bake.py` 414 - Deterministic bake + content hashing + lint for rendered assets (§6.5).
- `layerbake.py` 286 - Bake camera-space procedural painters into world layers (Phase 3 conversion kit).
- `loaders.py` 54 - Raw file loaders: the only place in the codebase that may call ``pygame.image.load`` / ``pygame.mixer.Sound`` on game...
- `manifest.py` 125 - Content-pack manifests (§6.5): ``ae.manifest/1``.
- `registry.py` 356 - AssetRegistry (§6.5): stable ids, the fallback chain, caching, ref-counts, reload.
- `watch.py` 70 - Hot reload for development (§6.5): poll the files behind loaded assets and call ``AssetRegistry.reload`` when one cha...

**`src/engine/collision/`**

- `__init__.py` 16 - engine.collision - solid-world queries for gameplay (RPE6 §6.9).
- `boxes.py` 112 - engine.collision.boxes - ray, segment and body queries against AABBs.
- `mesh.py` 181 - engine.collision.mesh - exact hitboxes from a mesh's own triangles.
- `nav.py` 188 - engine.collision.nav - A* on a walkability grid (RPE6 §6.9 ``GridGraph``).

**`src/engine/core/`**

- `__init__.py` 23 - engine.core: kernel services (clock, rng, events, log, config, services, errors, app).
- `app.py` 139 - App: explicit boot / run / shutdown (§6.1).
- `clock.py` 117 - Fixed-step simulation clock (master prompt §6.1, ADR-004).
- `config.py` 67 - Layered settings: defaults < JSON file < environment < CLI overrides (§6.1).
- `errors.py` 53 - Engine exceptions with context, and the crash-report writer (§6.1, §6.23).
- `events.py` 73 - Typed event bus (§6.3).
- `log.py` 62 - Structured logging with channels, a ring buffer and warn-once (§6.23).
- `mathx.py` 41 - Small math helpers (lerp/ease/angles/clamp).
- `profiling.py` 31 - Scoped timers (§6.22).
- `rng.py` 63 - Named, seeded random streams (R6, §6.1).
- `services.py` 39 - Explicit service registry (§6.1): no magic globals, clear errors.
- `timebase.py` 67 - Game-time accessors for legacy code (RPE6 ADAPTER A-004, BUGS B-001).

**`src/engine/dialogue/`**

- `__init__.py` 28 - engine.dialogue - data-driven dialogue (RPE6 §6.14, Phase 7).
- `model.py` 139 - dialogue.model - the .dlg.json model and static validation (RPE6 §6.14).
- `runner.py` 153 - dialogue.runner - DialogueRunner: walk a .dlg.json graph, emit lines (RPE6 §6.14).

**`src/engine/input/`**

- `__init__.py` 12 - engine.input - action maps over raw device state (RPE6 §6.10, Phase 9).
- `model.py` 110 - input.model - action maps and pressed-state remapping (RPE6 §6.10, Phase 9).

**`src/engine/level/`**

- `__init__.py` 24 - engine.level - data-driven levels (RPE6 §6.16, Phase 7).
- `model.py` 146 - level.model - the .level.json model, validation and (de)serialisation (RPE6 §6.16).
- `tiled.py` 89 - level.tiled - Tiled JSON (.tmj) importer (RPE6 §6.16).

**`src/engine/lighting/`**

- `__init__.py` 8 - engine.lighting - 2D light map (RPE6).
- `buffer.py` 282 - lighting.buffer - half-res light buffer: grade, motivated pools, dust (engine side).
- `lightmap.py` 114 - lighting.lightmap - multiplicative 2D light map (RPE6 Phase 6, §6.6 lighting integration).

**`src/engine/render2d/`**

- `__init__.py` 29 - engine.render2d - one way to put pixels on screen during gameplay (RPE6 §6.6).
- `camera.py` 159 - render2d.camera - Camera2D: follow, dead-zone, look-ahead, bounds, trauma shake, zoom (RPE6 §6.6).
- `drawables.py` 465 - render2d.drawables - the things a RenderQueue draws (RPE6 §6.6, Phase 6).
- `pen.py` 109 - render2d.pen - a drawing sink for procedural painters (RPE6 Phase 6, B-033).
- `postfx.py` 154 - render2d.postfx - full-screen post effects as cached surfaces + parameters (RPE6 §6.6).
- `queue.py` 185 - render2d.queue - the sorted render queue and its layer table (RPE6 §6.6, Phase 6).
- `static.py` 141 - render2d.static - StaticLayers: chunked bakes of floor/decor painters (RPE6 §6.6).
- `util.py` 135 - render2d.util - shared gameplay-render helpers (engine side).

**`src/engine/render3d/`**

- `__init__.py` 21 - engine.render3d - declarative 3D sets (RPE6 §6.7, Phase 8).
- `presets.py` 153 - render3d.presets - named 3D lighting moods (RPE6 §6.7 step 1, Phase 11).
- `scene3d.py` 317 - render3d.scene3d - declarative 3D sets (RPE6 §6.7, Phase 8).

**`src/engine/save/`**

- `__init__.py` 13 - engine.save - snapshots and determinism hashing (RPE6 §6.17, Phase 9).
- `snapshot.py` 76 - save.snapshot - the ae.save/1 snapshot model (RPE6 §6.17, Phase 9).
- `statehash.py` 43 - save.statehash - stable world hashing for determinism checks (RPE6 §6.17).

**`src/engine/scene/`**

- `__init__.py` 9 - engine.scene - explicit scene stack (RPE6 §6.2).
- `cutscene.py` 126 - CutsceneScene: a linear sequence of timed shots (§6.2, Phase 2 form).
- `inspect.py` 55 - InspectScene: a first-person look at an object that freezes gameplay (§6.2).
- `scene.py` 74 - Scene: one screen of the game with an explicit lifecycle (§6.2).
- `stack.py` 257 - SceneStack: the explicit replacement for stage flags and mode switches (§6.2).

**`src/engine/settings/`**

- `__init__.py` 13 - engine.settings - typed, layered user settings (RPE6 §6.18, Phase 9).
- `model.py` 175 - settings.model - typed, layered settings (RPE6 §6.18, Phase 9).

**`src/engine/text/`**

- `__init__.py` 29 - engine.text - string tables, the font registry and text layout (§6.12/§6.13).
- `fonts.py` 90 - Font registry and the glyph verdict (§6.13).
- `layout.py` 116 - Text layout: measure, wrap, fit, ellipsis (§6.12).
- `strings.py` 89 - String tables (§6.13): keys -> English, ``T()`` with fallbacks.

**`src/engine/timeline/`**

- `__init__.py` 25 - engine.timeline - data-driven cutscene timelines (RPE6 §6.15, Phase 8).
- `expr.py` 109 - timeline.expr - the tiny safe expression evaluator (RPE6 §6.7/§6.15).
- `model.py` 165 - timeline.model - the .timeline.json model and static validation (RPE6 §6.15).
- `player.py` 166 - timeline.player - deterministic sampling of a Timeline at any t (RPE6 §6.15).

**`src/engine/ui/`**

- `__init__.py` 25 - engine.ui - the widget kernel and the standard widgets (§6.12, Phase 4).
- `theme.py` 101 - Theme: the fonts, colours and viewport metrics widgets draw with (§6.12).

**`src/engine/ui/std/`**

- `__init__.py` 13 - Standard widgets, extracted from what the missions already draw (§6.12).
- `bottle_hud.py` 44 - BottleHud - the molotov counter strip (M1 + M2; the bodies were identical).
- `crosshair.py` 67 - Crosshair - the aim reticle shapes (four-arm reticle; combat ring + arms).
- `dialogue_box.py` 166 - DialogueBox: the shared cutscene dialogue box (A6.11, Phase 4).
- `health_bar.py` 57 - HealthBar - the HP strip (panel + "HP" label + ratio bar).
- `hostiles.py` 30 - Hostiles - the HOSTILES counter box.
- `minimap.py` 420 - MiniMap - the corner minimap panel.
- `objective_banner.py` 93 - ObjectiveBanner - the OBJECTIVE panel.
- `prompt.py` 71 - prompt - the world-anchored interaction tag ("[E] ...") drawn over a spot.
- `weapon_panel.py` 125 - WeaponPanel (MagIcons) - the 84px magazine-icon weapon panel.

**`src/engine/world/`**

- `__init__.py` 21 - engine.world - entities, components, systems ("ECS-lite", RPE6 §6.4).
- `_component.py` 125 - engine.world._component - ``@component`` dataclasses and the schema registry (RPE6 §6.4, A.1).
- `entity.py` 227 - engine.world.entity - ``EntityId`` and ``World`` storage (RPE6 §6.4).
- `prefab.py` 134 - engine.world.prefab - data-defined entity templates with inheritance (RPE6 §6.4, B.4).
- `std.py` 164 - engine.world.std - standard components (RPE6 §6.4).
- `system.py` 145 - engine.world.system - ``System`` base, phases and the ``Scheduler`` (RPE6 §6.4, A.1).

**`src/engine3d/`**

- `__init__.py` 14 - engine3d - tiny flat-shaded low-poly software renderer for pygame.
- `core.py` 924 - Core of the low-poly renderer: math, meshes, camera, painter renderer.
- `gl.py` 1380 - engine3d.gl - GPU backend for the low-poly renderer (ModernGL).
- `hold.py` 336 - Weapon holds and arm-vs-body safety for the box rig (engine3d.rig.Humanoid).
- `ik.py` 294 - Analytic two-bone IK for the box rig (engine3d.rig.Humanoid).
- `rig.py` 1190 - Low-poly humanoid rig: boxes on a joint hierarchy, posed by angle dicts.
- `textures.py` 146 - engine3d.textures - pixel textures on world faces.

**`src/entities/`**

- `__init__.py` 1 - entities package.
- `adornments.py` 249 - Head gear, as a registry keyed by catalog id.
- `art_cache.py` 424 - Centralized procedural surface cache for Call of Acaristan.
- `corpse.py` 560 - Enemy death corpses - bodies that fall instead of vanishing.
- `death_anim.py` 502 - Death animation - Option B (Standard).
- `enemy_ai.py` 1018 - Public: `Enemy`, `enemy_hear_shot`
- `fallen.py` 356 - A fallen body for a player, drawn in the same visual language as enemies.
- `player.py` 738 - Player character: movement, drawing, weapon rig.
- `sprite_lib.py` 11 - entities.sprite_lib - deprecated path (RPE6 Phase 2, A-006): see ``engine.assets.sprites``.
- `weapon_rig.py` 456 - The three weapon rigs, as drawable-on-call functions.
- `weapons.py` 818 - Player weapons: pistol, melee, molotov cocktails, fire zones.

**`src/fx/`**

- `__init__.py` 1 - fx package.
- `effects.py` 156 - Visual effects: particles, casings, breach markers, blood decals.

**`src/game/`**

- `__init__.py` 3 - Game-owned content (RPE6 Phase 3): art packs under ``game.art`` and pack manifests under ``game/content/<pack>/``.
- `devtools.py` 352 - RPE6 Phase 10 (§6.19): in-game debug tools.
- `dialogues.py` 84 - game.dialogues - mission conversation access (RPE6 Phase 7).
- `input_adapter.py` 144 - RPE6 Phase 9: game-side input adapter (rebinding + gamepad).
- `levels.py` 48 - game.levels - level-data access for the missions (RPE6 §6.16, Phase 7).
- `render3d_bridge.py` 679 - game.render3d_bridge - apply ae.set3d/1 data to a live 3D renderer (RPE6 Phase 8).
- `save_adapter.py` 392 - RPE6 Phase 9: game-side adapter between live state and ``engine.save``.
- `scenery3d.py` 92 - Cached office and medical scenery, baked offline from the source GLBs.
- `timelines.py` 74 - game.timelines - cutscene shot-list access (RPE6 Phase 8).
- `topdown3d.py` 513 - Shared 2.5D host for the top-down game: camera, sim<->world mapping, aim.

**`src/game/art/`**

- `__init__.py` 3 - Hand-authored pixel-art packs (pygame-only).
- `_layers.py` 54 - Shared helpers for baked world layers (``game.art.<pack>.<name>`` adapter modules).
- `_pack.py` 109 - Per-pack registry wrappers for game code (``game.art.<pack>``).

**`src/game/art/m1/`**

- `__init__.py` 23 - Mission 1 asset pack: baked world layers (and props) of the mission dressing.
- `exfil_truck.py` 20 - Mission 1 parked KRAP exfil flatbed (shadow, bed, crates, cab, headlights, wheels, KRAP label), baked from ``missions...
- `molotov_icon.py` 20 - HUD Molotov icon (0 active = lit bottle, 1 spent = grey bottle), baked from ``missions.m1.draw._paint_molotov_icon``...
- `pickup_icon.py` 20 - Mission 1 ground-pickup icons (0 magazine, 1 keycard, 2 bandage, 3 bottle), baked from ``missions.m1.draw._paint_m1_p...
- `world_static.py` 29 - Mission 1 static world (office floor grid, container / warehouse walls, desk bodies, bay label, dressing) baked from...

**`src/game/art/m2/`**

- `__init__.py` 23 - Mission 2 asset pack: baked world layers (and props) of the mission dressing.
- `nest_bits.py` 22 - Pieces of the abandoned Route 12 sniper nest (0 scuff ellipse 48x24, 1 brass casing 8x6, 2 left-behind rifle 40x12),...
- `prop_icon.py` 25 - Mission 2 clue / evidence prop icons at world scale (PROP_WORLD_SCALE), baked from ``missions.m2.draw._paint_prop_ico...
- `world_static.py` 33 - Mission 2 static world (road / terrain tiles, static dressing, structure walls, control facade, gantry, shelter, gard...

**`src/game/art/m3/`**

- `__init__.py` 23 - Mission 3 asset pack: baked world layers of the prison dressing (and later props).
- `archives_static.py` 39 - Archives Wing static world baked from ``missions.m3.draw._bake_m3_archives`` (live fallback).
- `broadcast_static.py` 26 - Broadcast Wing static world baked from ``missions.m3.draw._bake_m3_broadcast`` (live fallback).
- `camera_body.py` 19 - Mission 3 security-camera mount + smoked dome (0 idle, 1 alerted = opaque dome), baked from ``missions.m3.systems._pa...
- `cell_details.py` 25 - Biribel's cell dressing (cot, chair, sink, drain, stains, tally marks, conduit) as a baked world layer.
- `cell_door_blown.py` 21 - Mission 3 interrogation-cell door after the C4 breach has settled: jambs, the two door tiles, blast hole, scorch, cra...
- `cellblock_static.py` 45 - Cell-block map static world (floors, exterior ground, background dressing, corridor / guard room / armory / service-w...
- `comms_static.py` 26 - Comms Wing static world baked from ``missions.m3.draw._bake_m3_comms`` (live fallback).
- `door_tile.py` 25 - Reinforced prison door tile of Mission 3 (frame + leaf / open inner + padlock / LED) in its two rest states, baked fr...
- `kitchen.py` 30 - Prison kitchen / utility room of the cell block (floor tiles, backsplash, shelves, fixtures, grime) as a baked world...
- `ko_static.py` 42 - Kill Order ground-floor static world (floors, exterior ground, set dressing: stairwell, dock crane, crates, mezzanine...
- `pickup_icon.py` 20 - Mission 3 ground-pickup markers (0 looted sidearm, 1 bandage), baked from ``missions.m3.draw._paint_m3_pickup_icon``...
- `wall_monitor.py` 24 - Interrogation-cell wall monitor (Mission 3), baked from ``missions.m3.draw._paint_wall_monitor_part`` (live fallback).
- `weapon_icon.py` 20 - Mission 3 HUD weapon icons (shiv, chair leg, K-9 SMG, looted sidearm, generic), baked from ``missions.m3.systems._pai...

**`src/game/art/m4/`**

- `__init__.py` 23 - Mission 4 asset pack: baked world layers (and props) of the mission dressing.
- `mag_icon.py` 25 - Mission 4 HUD magazine icons, baked from ``missions.m4.draw._paint_m4_mag_icon`` (live fallback).
- `world_static.py` 42 - Mission 4 static world (floor + walls, buildings, roofs, window grids, storefronts, ground dressing) baked from ``mis...

**`src/game/art/m5/`**

- `__init__.py` 79 - Mission 5 sprite pack (owner module; ``art.m5`` is the compatibility shim).
- `_kit.py` 128 - Shared pixel-art kit for the Mission 5 sprites.
- `armband.py` 21 - The black Guard armband pinned to the depot notice board (25 x 8 px, 0.5 x 0.16 m): black cloth with a red stripe, fo...
- `bale.py` 52 - Strapped newspaper bundles seen from above (Print Works stacks/pallets).
- `calendar.py` 24 - Safehouse wall calendar (24 x 32 px, 0.6 x 0.8 m): red 1991 header, month grid, one day ringed in red, nail at the top.
- `district_map.py` 34 - Vasile's district map (52 x 36 px, 1.3 x 0.9 m): street grid, the river, the Lower Quarter ringed in red, "SECTOR 4"...
- `guard_banner.py` 44 - Presidential Guard banner (36 x 57 px, 1.2 x 1.9 m): brass rod, black cloth with folds lit from the left, gold eagle,...
- `guard_plate.py` 15 - Lit red Guard notice plate over the Print Works door (36 x 20 px, 0.9 x 0.5 m).
- `hq_locker.py` 29 - Guard HQ steel locker (26 x 44 px, top-down gameplay prop).
- `inspect_art.py` 30 - Static layers of the Mission 5 "[E] look" first-person shots (canvas CW x CH = 1.3x screen).
- `m5_guard.py` 62 - Presidential Guard trooper, top-down gameplay sprite (96 x 96, figure centred at (48, 48), facing +x).
- `mag.py` 30 - Maru's thrown magazines (gameplay).
- `mag_icon.py` 126 - HUD magazine-icon shells (weapon panel).
- `maru.py` 29 - Maru, top-down gameplay sprite (84 x 84, anchor (42, 48) = feet/centre): the figure_kit cast look - black hoodie, pis...
- `plate.py` 23 - HUD status plate (convoy / raid clock), 340 x 46: dark glass, steel rim with a lit top edge (upper-left key light), e...
- `portrait_frame.py` 31 - Official portrait of President Retardovici in a gilt frame (30 x 30 px, 1.0 x 1.0 m).
- `posters.py` 128 - Wall posters of the Lower Quarter (32 x 44 px, 0.64 x 0.88 m in the 3D sets).
- `presidential_crest.py` 64 - State crests (40 x 40 px).
- `press.py` 51 - Print Works offset press, top-down (154 x 64).
- `printworks_sign.py` 24 - "MAG PRINT WORKS" enamel sign over the Print Works (96 x 14 px, 8.4 x 1.3 m).
- `tram_wreck.py` 20 - Burnt-out tram on the quarter junction (static decor).
- `wall_posters.py` 64 - Top-down wall posters for the gameplay maps (the wall is seen as its front band).

**`src/game/content/`**

- `__init__.py` 1 - Pack manifests (``ae.manifest/1``) and palettes, one folder per pack. (auto)

**`src/game/render/`**

- `__init__.py` 72 - game.render - the game's ``engine.render2d`` instance: queue + static layers + post-FX + camera (RPE6 Phase 6).
- `adapters.py` 62 - Drawable adapters for shared legacy classes (RPE6 Phase 6, ADR-017).
- `host.py` 78 - game.render.host - the game's render2d instance and the hosted gameplay frame (RPE6 §6.6, Phase 6).

**`src/game/world/`**

- `__init__.py` 158 - game.world - the game's ``engine.world`` instance: World + Scheduler + legacy roster (RPE6 Phase 5).
- `legacy.py` 491 - game.world.legacy - strangler bridge between the pre-ECS objects and ``engine.world`` (RPE6 §6.4 step 1).

**`src/launcher/`**

- `__init__.py` 80 - Pre-game KRAPNET Launcher and in-place auto-updater package.
- `updater.py` 1312 - Update checker and in-place patcher for Call of Acaristan.
- `window.py` 1250 - KRAPNET Pre-Game Launcher window (Pygame) for Call of Acaristan.

**`src/missions/`**

- `__init__.py` 1 - missions package.
- `arena.py` 1742 - Multiplayer arena maps and the deathmatch rules.
- `walk3d.py` 536 - Walking sim in 2.5D: the harbour alley drawn in 3D over the 2D rules.
- `walk_fp.py` 1164 - First-person reward cinematics for the walking sim.
- `walk_van3d.py` 152 - Walking sim: the KRAP extraction van as a real 3D model.
- `walking_attack3d.py` 903 - True 3D oil-rig strike cinematic, rendered by the game's engine3d.
- `walking_sim.py` 3549 - Walking sim section: slum exploration, NPCs, firefight overlook panorama.

**`src/missions/m0/`**

- `__init__.py` 371 - Mission 0 - Depot - thin host generated by tools/ae_new_mission.py (RPE6 P10).

**`src/missions/m1/`**

- `__init__.py` 42 - Package missions/m1 - re-export facade.
- `draw.py` 2450 - Split part. Public: `game_draw`, `submit_frame`
- `draw3d.py` 1887 - Mission 1 in 2.5D: the warehouse frame drawn in 3D over the 2D rules.
- `escape3d.py` 320 - Mission 1 escape cut (timeline m1.escape) in 3D.
- `grade3d.py` 138 - Mission 1 night grade for the 2.5D frame: a screen-space light map.
- `hotwire.py` 144 - Split part. Public: `handle_hotwire_press`, `handle_hotwire_click`
- `m1_audio.py` 100 - Mission 1 music hook: two looped stems (infiltrate / combat), crossfaded over 1.5 s when the alarm flips STATE.firefi...
- `main.py` 362 - Split part. Public: `start_mission`
- `map.py` 175 - Mission 1 map - authored with core.MapBuilder, baked to list[str].
- `meta.py` 96 - Mission 1 cutscene data (RPE6 Phase 8 + WP2: the cut as ae.timeline/1).
- `roles.py` 233 - Mission 1 breach roles (WP7): rusher / cover / flanker per wave enemy, and CIOCAN's shoulder charge.
- `stealth.py` 431 - Mission 1 stealth (rework WP5, plan section d).
- `update.py` 1226 - Split part. Public: `debug_jump_to_exfil`, `standoff_commander`, `game_update`

**`src/missions/m2/`**

- `__init__.py` 54 - Package missions/m2 - re-export facade.
- `components.py` 19 - Mission 2 entity components (RPE6 Phase 5, D4).
- `draw.py` 8110 - Split part. Public: `draw_route12_seby_pickup`, `clamp_alpha`, `game_draw`, `get_mission2_overview`, `get_opening_cinematic`, `get_squadmate_death_cutscene`, `get_mission_phases`, `get_mission2_zones`
- `draw3d.py` 1516 - Mission 2 in 2.5D: Route 12 drawn in 3D over the 2D rules.
- `meta.py` 701 - Split part. Public: `get_zone_for_world_pos`
- `sniper.py` 1979 - Split part. Public: `grant_seby_os12`
- `sniper3d.py` 1225 - Mission 2 - "Route 12 Kill-Box": the sniper ambush as a low-poly 3D film.
- `sniper3d_set.py` 274 - Route 12 toll plaza, built for the low-poly sniper cinematic.
- `starts.py` 597 - Split part. Public: `start_mission2`, `start_mission2_sniper`, `start_mission2_after_sniper`, `start_mission2_flank`, `start_mission2_truck`, `start_mission2_checkpoint`, `start_mission2_evidence_debug`
- `update.py` 1259 - Split part. Public: `handle_interact`, `blocks_player_actions`, `debug_jump_to_evidence`, `game_update`
- `world.py` 900 - Split part. (no docstring)

**`src/missions/m3/`**

- `__init__.py` 100 - Package missions/m3 - re-export facade.
- `components.py` 53 - Mission 3 entity components (RPE6 Phase 5, D4).
- `draw.py` 8355 - Split part. Public: `draw_archives_transition_cinematic`, `draw_vostral_pickup_cinematic`, `game_draw`, `solid_walls_view`
- `draw3d.py` 1376 - Mission 3 in 2.5D: the five playable maps drawn in 3D over the 2D rules.
- `flow.py` 1936 - Split part. Public: `start_mission3`, `start_mission3_breakout_checkpoint`, `start_mission3_comms_checkpoint`, `start_mission3_archives_checkpoint`, `start_mission3_kill_order_checkpoint`, `start_mission3_broadcast_checkpoint`, `start_mission3_upload_checkpoint`
- `interrog.py` 636 - Split part. (no docstring)
- `maps.py` 836 - Split part. (no docstring)
- `meta.py` 566 - Split part. (no docstring)
- `sweep.py` 1100 - Slice 5b-5d: the Kill Order sweep director, overwatch pin, Volkov extraction window and dock holdout.
- `systems.py` 4178 - Split part. Public: `game_update`, `is_crafting_active`, `grant_k9_smg`, `start_black_ledger_debug`, `handle_interact`, `start_crafting`, `handle_crafting_event`, `handle_event`
- `wings3d.py` 733 - Mission 3 wings in 2.5D: the comms wing, the archives, the kill order floor and the broadcast studio, for ``draw3d``.
- `world.py` 2345 - Split part. (no docstring)

**`src/missions/m4/`**

- `__init__.py` 103 - Mission 4: The Aftermath - the world after the broadcast.
- `apc.py` 143 - Mission 4 wave 5: the APC ram.
- `components.py` 26 - Mission 4 entity components (RPE6 Phase 5, D4).
- `draw.py` 2868 - Split part. Public: `game_draw`
- `draw3d.py` 1415 - Mission 4 in 2.5D: the curfew street and the radio station in 3D.
- `escort.py` 150 - Mission 4 escort: Vasile, the KRAP comms cache and the supply pool.
- `flow.py` 788 - Split part. Public: `handle_dialogue_event`, `start_m4`, `start_mission4_station_checkpoint`, `start_mission4_tower_checkpoint`, `handle_interact`
- `fortify.py` 219 - Mission 4 fortify: barricade sites, the build / upgrade / repair holds.
- `maps.py` 447 - Split part. Public: `zone_at`, `zone_label`
- `meta.py` 314 - Mission 4 - part module.
- `siege.py` 683 - Mission 4 siege: five waves on the station while the arrest airs.
- `systems.py` 453 - Split part. Public: `game_update`
- `world.py` 833 - Split part. Public: `friendly_npcs`, `barricade_blocks_shots`, `fail_mission`

**`src/missions/m5/`**

- `__init__.py` 73 - Mission 5: Martial Law - the capital under emergency rule.
- `components.py` 29 - Mission 5 entity components (RPE6 Phase 5, D4).
- `decor.py` 380 - Mission 5 set dressing, lighting and inspectables (round 2).
- `decor_interior.py` 432 - Mission 5 interior set dressing (gauntlet pass).
- `decor_paint.py` 416 - Mission 5 static set dressing painters (round 2).
- `draw.py` 1391 - Mission 5 - part module.
- `draw3d.py` 1746 - Mission 5 in 2.5D: Guard HQ, the Lower Quarter, the print works and the tunnel in 3D.
- `finale_audio.py` 264 - Mission 5 sound design and cutscene-owned playback.
- `finale_script.py` 43 - M5 rebuilt finale: immutable script/timing shared by renderer and player.
- `flow.py` 612 - Mission 5 - part module.
- `inspect_art.py` 370 - painters for the Mission 5 first-person inspect shots.
- `inspect_art_street.py` 253 - storeroom + Lower Quarter inspect shots (paint tins, shop TV through the shutter, the burned tram).
- `inspect_fpv.py` 232 - Mission 5 "[E] look": a short first-person look at the thing instead of a radio line.
- `maps.py` 270 - Mission 5 - part module.
- `meta.py` 265 - Mission 5 - part module.
- `quarter.py` 527 - Lower Quarter systems (round 2): turns 'run and gun' into a run with choices.
- `render.py` 119 - Mission 5 - part module.
- `systems.py` 366 - Mission 5 - part module.
- `tram_wreck.py` 531 - M5 Lower Quarter: the burning tram wreck (top-down).
- `water.py` 103 - M5 shallow floodwater: one connected, world-space surface, never tile stamps.
- `world.py` 762 - Mission 5 - part module.

**`src/missions/m6/`**

- `__init__.py` 57 - Mission 6: Whiteout - re-export facade (load order = parts order).
- `combat.py` 848 - Mission 6 - loud combat arenas for the three top-down stages.
- `decor.py` 2603 - Mission 6 - stage decor, ground art and night lighting.
- `draw.py` 687 - Mission 6 gameplay renderer.
- `draw3d.py` 1194 - Mission 6 in 2.5D: the customs post, no-man's-land and the rail yard.
- `flow.py` 395 - Mission 6 - stage ladder, checkpoints and the ending handoff.
- `hud3d.py` 262 - Mission 6 3D HUD: minimal tactical, shared by the train shootout and the yard fight.
- `m6_audio.py` 678 - Mission 6 sound design: film stems, foley and the interactive-train bed.
- `maps.py` 296 - Authored map layer for Mission 6 - three distinct playable spaces.
- `meta.py` 314 - Mission 6 metadata, stage constants and authored cutscene timelines.
- `palette3d.py` 40 - The 2D top-down M6 palette, for the 3D yard and train.
- `perf.py` 386 - M6 3D scene performance governor (train scene + rail-yard fight).
- `stealth.py` 441 - Mission 6 - tower searchlights for no-man's-land and the rail yard.
- `systems.py` 316 - Mission 6 - per-frame gameplay pipeline.
- `train3d.py` 5346 - Mission 6 - the interactive 3D train scene (``docs/MISSION6_PLOT.md``).
- `world.py` 423 - Mission 6 - world construction, Guard spawns and shared helpers.
- `yard3d.py` 1931 - Mission 6 - "Who is Ucilev?": the third-person fight after Volkov's death.
- `yard_brain.py` 604 - Mission 6 yard - the Guard brains (engine.ai on the "Who is Ucilev?" fight).
- `yard_dress.py` 304 - Mission 6 yard - the clutter that makes the walled yard look lived in.
- `yard_hud.py` 179 - Mission 6 yard - the 2D top-down game's HUD, brought into the 3D fight.

**`src/missions/m6/bloc3d/`**

- `__init__.py` 15 - bloc3d - the Bloc around the M6 yard and station, built from boxes.
- `blocks.py` 204 - Prefab Soviet panel blocks for the Bloc district.
- `colours.py` 39 - Phase-5 colours for the Bloc landmarks and signage.
- `font.py` 108 - A 5x7 pixel font for the Cyrillic signage on the Bloc.
- `signs.py` 172 - Cyrillic signage for the Bloc: rooftop letters, boards, stars, billboards, banners.
- `stacks.py` 134 - Industrial silhouettes on the skyline: chimneys, a radio mast, a water tower.
- `tower.py` 139 - Watchtowers and wire fences for the Bloc yards.

**`src/missions/m7/`**

- `__init__.py` 9 - Mission 7: Fallow Ground - re-export facade (load order = parts order).
- `choice.py` 616 - Mission 7 beat 7 - Two Channels: Vasile's offer, Maru's reply, then the choice.
- `colonel.py` 228 - Colonel Paie: the scarecrow easter egg on Bodi's farm.
- `draw.py` 38 - Mission 7 - placeholder frame: title, stage label and the advance hint.
- `farmyard.py` 2603 - Mission 7 top-down farmyard.
- `flow.py` 168 - Mission 7 - stage ladder, checkpoints and the outro handoff (skeleton).
- `goat_rescue.py` 3715 - Mission 7 beat 2: Bodi's escaped goat.
- `m7_audio.py` 733 - Mission 7 sound design: the farm day, the night raid, the ending receiver.
- `maps.py` 112 - Mission 7 top-down farm: tile grid, palette and interaction points (beats 2 and 4).
- `meta.py` 106 - Mission 7 metadata and stage constants: Fallow Ground (skeleton).
- `minigames.py` 894 - Mission 7 farm minigames.
- `raid3d.py` 2186 - Mission 7 beat 5 - the raid: a third-person fight for Bodi's yard at night.
- `raid_brain.py` 649 - Mission 7 raid AI: the Guard sweep (riflemen, a dog, a truck gunner), the trucks, and the two allies, Bodi and Alex.
- `raid_hud.py` 150 - Mission 7 raid HUD: the top-down game's panels (via the M6 yard HUD helpers), a north-up farm minimap, speaker-colour...
- `raid_world.py` 697 - Mission 7 raid world: collision boxes, line of sight, the barn fire and the props.
- `systems.py` 34 - Mission 7 - per-frame update, dispatched by stage (placeholder stages: ENTER advances).

**`src/missions/m8/`**

- `__init__.py` 9 - Mission 8: The Call - re-export facade (load order = parts order).
- `draw.py` 28 - Mission 8 - frame: a 3D scene, or the stage's 3D beat.
- `flow.py` 201 - Mission 8 - stage ladder, checkpoints and the outro handoff.
- `m8_audio.py` 897 - Mission 8 sound design: Route 12, the catwalk, the chase.
- `meta.py` 205 - Mission 8 metadata: identity, the two stage ladders and the beat scripts.
- `systems.py` 36 - Mission 8 - per-frame update, dispatched by stage: a 3D scene, or a beat.

**`src/missions/m8/duty/`**

- `__init__.py` 3 - Mission 8 Duty route ("Head of State"): reserved.

**`src/missions/m8/revenge/`**

- `__init__.py` 3 - Mission 8 Revenge route: the Route 12 set (``set3d``), the trap and gantry fight (``trap3d`` over ``trap_world`` / ``...
- `beats.py` 170 - Mission 8 - 3D beats: the stage's lines as caption plates over the Route 12 set.
- `chase3d.py` 5996 - Mission 8 Revenge - phase 6: the tractor chase to the Kim Kim crossing.
- `chase_set.py` 2370 - Mission 8 Revenge - the tractor chase set: the back roads from Route 12 to the Kim Kim rail crossing, baked once.
- `epilogue3d.py` 637 - Mission 8 Revenge - phase 7: the epilogue, one 3D shot per line.
- `kill3d.py` 953 - Mission 8: Vasile's last moment on the Route 12 gantry.
- `set3d.py` 860 - Mission 8 Revenge - Route 12 in 3D, shared by the trap fight, the kill and the meet.
- `trap3d.py` 2338 - Mission 8 Revenge - phases 2 and 3: the Trap and the Gantry, one third-person scene.
- `trap_brain.py` 888 - Mission 8 Revenge - trap AI: Guard riflemen, breachers, elevated overwatch snipers, the interactive Guard truck and B...
- `trap_hud.py` 215 - Mission 8 Revenge - trap HUD: the raid's panels, tactical radar markers and callouts on a north-up Route 12 minimap d...
- `trap_world.py` 286 - Mission 8 Revenge - blocking solids, 3D sight lines and interactive hazards of the Route 12 set for the trap fight.

**`src/net/`**

- `__init__.py` 21 - net - multiplayer relay client.
- `client.py` 472 - Game-side client for the KRAPNET master server.
- `discovery.py` 50 - LAN auto-discovery for the master server.
- `match.py` 469 - A multiplayer match session: authoritative host + interpolating clients.
- `playit_agent.py` 220 - Bundled playit.gg agent for hosts without their own playit install.
- `portmap.py` 718 - Automatic router port forwarding (UPnP IGD + NAT-PMP), stdlib only.
- `protocol.py` 1554 - Wire protocol for the Acaristan multiplayer master server.
- `roomcode.py` 133 - Short, game-branded room codes for direct arena matches.
- `tcp_tunnel.py` 346 - Public raw-TCP tunnels for arena matches.
- `telemetry.py` 137 - Lightweight client-side telemetry for arena matches.
- `udp_transport.py` 45 - Small, bounded helpers for the real-time match datagram channel.

**`src/tools/`**

- `input_recorder.py` 61 - Dev-only gameplay input recorder (RPE6 Phase 0, replay baselines).
- `ko_playability_audit.py` 561 - Kill Order (Mission 3 Phase 5) playability audit - headless.
- `trailer_bot.py` 201 - Trailer bot - deterministic operator driver for cinematic capture.

**`src/ui/`**

- `__init__.py` 91 - Package ui - re-export facade.
- `arena_view.py` 1859 - Renderer for multiplayer arena matches.
- `arena_view3d.py` 569 - 2.5D renderer for multiplayer arena matches.
- `credits.py` 491 - End credits sequence displayed after Mission 8's Call of Acaristan title card. (auto)
- `credits_football.py` 2324 - Credits background football match (Biribel vs Bodi): simulation, animations and 3D pitch. (auto)
- `egg666_3d.py` 361 - the Mission 1 safe-keypad "666" Easter egg as a lit 3D scene.
- `egg666_audio.py` 279 - procedural sound for the 3D "666" scare.
- `egg666_build.py` 340 - geometry for the 3D "666" scare: the vault, the ritual marks, the hanging lamp and the demon.
- `egg666_dir.py` 330 - the director of the 3D "666" scare: what happens at which frame.
- `egg666_fx.py` 138 - light halos, the PS2 grade and the crisp present for the 3D "666" scare.
- `egg666_post.py` 127 - screen effects for the 3D "666" scare.
- `hud.py` 1475 - HUD overlays: minimap, safe keypad, notebook inspection, desk notes.
- `kit.py` 206 - KRAPNET terminal style kit shared by the main menu and its sub-screens.
- `main.py` 990 - Split part. Public: `draw_menu_background`, `draw_menu`, `draw_menu_cursor`, `slot_panel_clicked`, `handle_menu_keydown`, `consume_keyboard_trigger`, `reset_keyboard_selection`
- `match_screen.py` 4881 - The in-game arena match: entry panel plus the live match runtime.
- `mission_failed.py` 322 - Mission-specific failure terminals with bespoke procedural illustrations.
- `mp.py` 3411 - Split part. Public: `update_server_browser_animation`, `switch_mp_tab`, `open_dm`, `close_dm`, `send_dm_message`, `update_dm_state`, `draw_connections_panel`, `scroll_server_list`
- `mp3d.py` 343 - 3D kit for multiplayer: soldier rigs, guns and Outfitter portraits.
- `multiplayer_style.py` 375 - Read-only KRAPNET presentation.
- `pixfont.py` 349 - Pixel bitmap fonts for the radio UI (polish pass T6b).
- `radio.py` 772 - Radio transmission widget (polish pass T6, field-radio restyle T6b).
- `shop.py` 624 - The Outfitter - spend Acaribucks on the loadout you play the arena in.
- `speechbox.py` 346 - Speech box: the one in-person dialogue box and film caption for the game.
- `system.py` 1580 - Split part. Public: `draw_settings`, `draw_pause_menu`, `reset_death_animation`, `draw_death_screen`, `draw_black_ledger_death_screen`, `black_ledger_death_buttons_ready`, `draw_black_ledger_death_buttons`
- `upload_os.py` 3138 - Upload OS - a retro CRT terminal operating system for the evidence upload.
- `widgets.py` 320 - Split part. Public: `note_hover`, `consume_hover`, `clipboard_text`, `ModernButton`
### 20.1 Monolith Anchor Table (files > 1,000 lines)
<!-- AUTO:anchors -->
Line ranges (generated) for the monoliths; give `tools/ai_bundle.py path:start-end` the slice you need.

- `app.py` (4804): 1-521 header/imports; 522-545 def trigger_transition; 546-965 class CutscenePlayer; 966-1930 def draw_slot_select_screen; 1931-2175 class _BootIntroState; 2176-2313 class _EngineIntroState; 2314-2381 class _MenuState; 2382-2574 class _SlotSelectState; 2575-2755 class _MultiplayerState; 2756-2808 class _SettingsState; 2809-2844 class _ShopState; 2845-3264 class _CutsceneState; 3265-3321 class _CreditsState; 3322-3341 class _BriefingState; 3342-3398 class _WalkState; 3399-3907 class _GameState_; 3908-3926 class _NotebookInspectState; 3927-3982 class _PausedState; 3983-4098 class _DeathState; 4099-4504 class _MissionCompleteState; 4505-4748 def _legacy_frame; 4749-4804 class _LegacyGameScene
- `cutscenes/m6world3d.py` (2664): 1-77 header/imports; 78-345 plumbing; 346-392 film grade; 393-706 actors; 707-1116 motion kit; 1117-1165 def head_stats; 1166-1249 particles; 1250-1268 sky / light helpers; 1269-1630 insertion sets; 1631-2143 the valley run (intro chase); 2144-2294 boxcar interior; 2295-2664 rail platform / terminal / office
- `cutscenes/m7world3d.py` (3150): 1-358 header/imports; 359-794 M8 ruin: Bodi's farm the morning after the fire ; 795-1238 def _tractor_asset; 1239-1665 def motorcycle; 1666-2077 def _landscape_water_tower; 2078-2509 def _south_y; 2510-2926 def _sag; 2927-3150 def burn_fx
- `missions/m8/revenge/chase_set.py` (2370): 1-150 header/imports; 151-562 meshes; 563-589 def _xf; 590-1043 the Guard gunship; 1044-1293 def _rot_rt; 1294-1695 the baked set; 1696-2113 def _verge_trees; 2114-2370 def _zones
- `missions/m2/draw.py` (8110): 1-454 header/imports; 455-549 def _draw_car_burn_overlay; 550-951 Generated vehicle sprites (Polish T7); 952-1277 def _draw_tanker_dynamic; 1278-1744 Generated story-prop sprites (Polish T7); 1745-2184 def _draw_sebi_body_fpv; 2185-2779 def _draw_fpv_hands_inspect; 2780-3198 def _prop_icon_variant; 3199-3879 def _draw_shelter_live; 3880-4503 def _draw_interactables; 4504-5048 def _draw_card; 5049-5517 def _draw_packet_document; 5518-5958 def _draw_hud; 5959-6552 def _draw_dead_air_overlay; 6553-6631 def _draw_blackout_overlay; 6632-6768 Static bake + lighting fixtures (Mission 3 pipel; 6769-7226 Deterministic per-tile noise; 7227-7632 def _bake_m2_static; 7633-8110 def get_ending_cinematic
- `missions/m3/draw.py` (8355): 1-182 header/imports; 183-613 static-layer bake + lighting fixtures (graphics ; 614-1028 exterior ground: world-space dressing; 1029-1456 def _draw_guard_room_details; 1457-1880 def _draw_laundry_room_details; 1881-2368 def _draw_exit_zone_details; 2369-2806 def _draw_comms_map_polish; 2807-3777 def _draw_m3_enemy_type_overlay; 3778-4192 def _draw_archives_map_polish; 4193-4618 def _vp_hand_xform; 4619-5035 Slice 5: Kill Order ground-floor draw path; 5036-5287 def _draw_bcast_station_pc; 5288-5693 bound-hand POV palette (v2 art pass); 5694-6115 def game_draw; 6116-6568 def _draw_m3_pickup; 6569-7061 def _draw_cell_details; 7062-7496 def _draw_cell_details_live; 7497-7906 def _draw_kitchen_details; 7907-8355 def _paint_cell_door_blown
- `audio/audio.py` (3454): 1-124 header/imports; 125-240 New Powerful DSP Helpers for 16-Bit DOS Style So; 241-242 Upgraded DOS/16-Bit Sound Generators; 243-665 v2 organic DSP helpers (SFX audit pass); 666-765 def _gen_footstep; 766-1184 Overhaul: surface-specific footsteps, NPC feet, ; 1185-1651 def _gen_pa_chime; 1652-2055 def _gen_ambient_drone; 2056-2256 def _gen_molotov_throw; 2257-2540 Cinematic procedural sounds; 2541-2759 Trailer overhaul (docs/PLAN_3_AUDIO.md) - ADDITI; 2760-2776 Audio Manager; 2777-2895 Upload OS CRT sounds; 2896-3454 class AudioManager
- `ui/match_screen.py` (4881): 1-203 header/imports; 204-214 Identity; 215-298 In-match chat; 299-502 class Wire; 503-614 class Peer; 615-1113 class MatchScreen; 1114-3153 starting a match; 3154-4881 panel input
<!-- /AUTO:anchors -->

## 21. Tools index (`tools/`, generated from module docstrings)

Scratch probes (`tools/_*.py`, about 23 `_m8_*` files) are skipped: they are throwaway capture scripts, not gates.

**`tools/`**

- `ae_api_snapshot.py` 175 - public API snapshot of ``src/engine`` (RPE6 Phase 2 gate).
- `ae_audit.py` 490 - RPE6 Phase 0 audit: static census of src/ and tools/ (read-only, stdlib only).
- `ae_bake.py` 112 - ae_bake - bake / check / lint content packs (RPE6 Phase 3, §6.5).
- `ae_bench.py` 148 - frame budget bench (RPE6 §6.22; Phase 6 exit evidence).
- `ae_bench3d.py` 108 - AE BENCH3D - 3D frame budget bench (RPE6 Phase 11 exit evidence).
- `ae_build_ak74.py` 651 - AE BUILD AK74 - the AK-74 (6P20) authored in code, with no GLB source.
- `ae_ci.py` 213 - RPE6 one-command CI (D10).
- `ae_d4_gate.py` 141 - D4 grep gate: no attribute stuffing on entity objects (RPE6 §2 D4, §6.4 acceptance).
- `ae_d4_replay_compat.py` 125 - proof that moving entity data into components kept behaviour (RPE6 Phase 5).
- `ae_d6_gate.py` 153 - D6 gate: one 2D render path (RPE6 §2 D6, §6.6; Phase 6).
- `ae_dialogue_check.py` 84 - ae_dialogue_check - Phase 7 dialogue gate: validate + data == legacy tables.
- `ae_dialogue_export.py` 91 - ae_dialogue_export - write the legacy conversation tables as ae.dialogue/1 data.
- `ae_draw_audit.py` 164 - ae_draw_audit - procedural-draw census per mission (RPE6 Phase 3, P3-M3).
- `ae_dump_components.py` 106 - component census of a running mission stage (RPE6 §6.4 acceptance).
- `ae_engine3d_parity.py` 80 - AE ENGINE3D PARITY - software-backend determinism evidence.
- `ae_export_ak74_glb.py` 473 - AE EXPORT AK74 GLB - the code-authored AK-74 written back out as a GLB source.
- `ae_flash_check.py` 61 - ae_flash_check - Phase 9 exit evidence: flash reduction caps the breach white-out.
- `ae_gauntlet.py` 112 - AE GAUNTLET - render everything once at offsets nobody tested.
- `ae_global_names.py` 130 - ae_global_names - unresolved global references in src (Phase 4 gate, A-001).
- `ae_golden.py` 550 - RPE6 golden-image harness (master prompt §9).
- `ae_hold_check.py` 139 - Weapon hold + arm self-collision gate for the 3D cutscenes.
- `ae_hud_census.py` 177 - ae_hud_census - HUD duplication census across missions (Phase 4 prep).
- `ae_import_akrifle.py` 113 - AE IMPORT AKRIFLE - the Guard/shared third-person rifle (assets/3D/ak-style-rifle.glb).
- `ae_import_car.py` 104 - AE IMPORT CAR - the Mission 2 civilian car (assets/3D/low-poly-car_green.glb).
- `ae_import_check.py` 105 - RPE6 import side-effect check (R7, §6.1 acceptance).
- `ae_import_dog.py` 151 - AE IMPORT DOG - the Mission 7 guard dog (assets/3D/dawg.glb) and its clips.
- `ae_import_k93d.py` 326 - AE IMPORT K93D - the first authored 3D weapon asset (assets/3D/K93D.glb).
- `ae_import_krap_van.py` 200 - AE IMPORT KRAP VAN - the KRAP van (assets/3D/krap_van.glb).
- `ae_import_lmg.py` 116 - AE IMPORT LMG - Biribel's light machine gun in the M8 tractor chase (assets/3D/light_machine_gun.glb).
- `ae_import_m3_van.py` 109 - AE IMPORT M3 VAN - Volkov's armoured van (assets/3D/M3van.glb).
- `ae_import_m7rifle.py` 111 - AE IMPORT M7RIFLE - the allies' rifle in Mission 7 (assets/3D/M7Rifle.glb).
- `ae_import_mesh.py` 210 - AE IMPORT MESH - Blender/glTF/OBJ -> ae.mesh/1 asset (ADR-024).
- `ae_import_molotov.py` 118 - AE IMPORT MOLOTOV - the thrown molotov cocktail (assets/3D/low-poly-molotov.glb).
- `ae_import_pig.py` 85 - AE IMPORT PIG - the low-poly pig (assets/3D/low_poly_pig.glb).
- `ae_import_pistol.py` 95 - AE IMPORT PISTOL - the multiplayer service pistol (assets/3D/pistol_lowpoly.glb).
- `ae_import_tractor.py` 99 - AE IMPORT TRACTOR - the Mission 7 tractor asset (assets/3D/TractorM7.glb).
- `ae_import_truck.py` 106 - AE IMPORT TRUCK - the Mission 7 Guard truck (assets/3D/IPA-army-truck.glb).
- `ae_import_workstation_props.py` 98 - Bake the six office/medical GLBs; no source model is loaded during play.
- `ae_layer_parity.py` 93 - Parity oracle for baked *chunk* layers (``game.art.<pack>.<name>`` adapters with ``bake_setup``): re-runs the mission...
- `ae_layer_probe.py` 173 - ae_layer_probe - can this camera-space painter become a baked world layer?
- `ae_level_check.py` 66 - validator: level JSON == legacy generator output (RPE6 P7).
- `ae_level_export.py` 102 - export the legacy mission grids to .level.json (RPE6 P7-M2).
- `ae_loop.py` 637 - RPE6 loop probe: drive the REAL app.py main loop headless and hash every frame.
- `ae_migrate_time.py` 156 - RPE6 B-001: move legacy wall-clock reads onto the engine timebase.
- `ae_mission0_check.py` 188 - AE MISSION0 CHECK - RPE6 Phase 10, D2 proof.
- `ae_narrow_star.py` 114 - ae_narrow_star - rewrite ``from core.config import *`` into explicit imports (A-001, Phase 4).
- `ae_new_mission.py` 462 - scaffold a new RPE6 mission (Phase 10, §7/D2).
- `ae_normalize.py` 263 - RPE6 Phase 0 item 7: line-ending / encoding normalisation with proofs (R14, B-003).
- `ae_package.py` 99 - AE PACKAGE - build the distributable game zip.
- `ae_proof3d.py` 158 - AE PROOF3D - render the fixed Phase 11 proof scenes to PNGs.
- `ae_proof_sheet.py` 78 - AE PROOF SHEET - side-by-side before/after sheet for Phase 11 steps.
- `ae_reexport_check.py` 103 - ae_reexport_check - who pulls star-imported names THROUGH another module?
- `ae_replay.py` 293 - RPE6 replay baseline + determinism check (master prompt §6.17, Phase 0 item 9, D8).
- `ae_replay_check.py` 88 - RPE6 Phase 9 exit tool: engine-save snapshots reproduce replay state.
- `ae_set3d_check.py` 64 - ae_set3d_check - Phase 8 set gate: validate + build every .set3d.json.
- `ae_star_imports.py` 140 - ae_star_imports - inventory of ``from core.config import *`` users (A-001 prep, Phase 4).
- `ae_text_check.py` 351 - string-table validation and text fit (RPE6 Phase 4, 6.13).
- `ae_textures_gen.py` 91 - AE TEXTURES GEN - deterministic palette textures (RPE6 Phase 11 step 9).
- `ae_timeline_check.py` 114 - ae_timeline_check - Phase 8 timeline gate: validate + data == legacy tables.
- `ae_timeline_edit.py` 93 - ae_timeline_edit - the Phase 8 camera/track key editor (CLI form).
- `ae_timeline_export.py` 103 - ae_timeline_export - write the legacy cutscene shot lists as ae.timeline/1 data.
- `ae_validate.py` 73 - AE VALIDATE - load every game data file through its public loader.
- `ak74_preview.py` 326 - AK-74 preview - renders the code-authored weapon so it can be eyeballed.
- `assemble_final_trailer.py` 811 - Post-production assembler for CALL OF ACARISTAN.
- `bake_m5_sprites.py` 16 - Compatibility wrapper: the Mission 5 bake moved to the generic pipeline.
- `build_all_sprites.py` 54 - Rebuild every generated art asset in one go (Polish T7).
- `build_code_pdf.py` 1197 - build_code_pdf.py High-Density Archival Monolith GUI & CLI.
- `build_code_txt.py` 309 - build_code_txt.py Selective TXT code bundle (.py, .bat, .json, .md, configs...): pick files, pick folder, get TXT onl...
- `build_ost.py` 62 - Render the Call of Acaristan OST (tools/ost/album.py).
- `build_ost_videos.py` 222 - Render the OST music videos: one seamless 3D loop per album track.
- `build_radio_cache.py` 63 - Pre-build the radio-FX voice cache (assets/voice/_radio_cache).
- `build_sfx_stem.py` 520 - render trailer_sfx_stem.wav from captured foley logs.
- `build_windows.py` 102 - Build the Windows game as a PyInstaller --onedir bundle (no admin needed).
- `cast_lineup.py` 91 - 3D cast line-up: python tools/cast_lineup.py [body/face] [out.jpg] [key ...]
- `cast_sheet.py` 154 - Cast sheets: the 2D cutscene figures (figure_kit) beside their 3D rigs.
- `check_boundaries.py` 148 - RPE6 boundary lint (master prompt §5.3, D1).
- `convert_voice_ogg.py` 62 - Convert assets/voice/**/*.wav to OGG Vorbis in place (RPE6 housekeeping, 2026-10-14).
- `debug_stem.py` 32 - Standalone timing run of mp_trailer_assemble.render_foley_stem.
- `dev_panel.py` 1439 - clickable dev control panel for jumping into missions.
- `download_bore.py` 25 - Fetch the pinned official Windows x64 bore release for PyInstaller builds.
- `download_playit.py` 25 - Fetch the pinned official playit.gg agent (playitd) for PyInstaller builds.
- `egg666_shots.py` 85 - Headless shots of the 3D "666" scare.
- `engine3d_check.py` 118 - GPU vs software renderer check on the real M2 ambush film.
- `export_m5_audio.py` 46 - Export the exact procedural M5 mix for audition; no app launch/saves.
- `finale_compare.py` 59 - Side-by-side probe: M2 ambush film (sniper3d) vs M5 finale (m5shadow3d).
- `finale_gait_check.py` 46 - M5 finale gait check: Maru timing, footstep contact times, world foot drift.
- `finale_probe.py` 52 - Render M5 finale frames (optionally from custom cameras) into a JPEG contact sheet.
- `gen_barrel_obj.py` 70 - Generate assets/import/barrel.obj - a low-poly barrel (10 sides, bulged profile, two metal bands) as the Step-11 impo...
- `golden.py` 125 - golden-image regression gate for the reworked renderer.
- `itch_push.py` 94 - Push a built game to itch.io with butler (the official itch upload CLI).
- `k9_pickup_check.py` 142 - Headless regression checks and optional preview for the K-9 pickup.
- `m1_hall_probe.py` 118 - Diagnostic probe: can the player actually cross commander K's hall (rows 21-25)?
- `m1_td3d_shots.py` 57 - Render Mission 1 top-down frames in 2.5D (and 2D with ACA_TD_2D=1).
- `m2_fire_probe.py` 113 - Time Mission 2 frames after the tanker blast (fire cost probe).
- `m2_td3d_shots.py` 80 - Render Mission 2 top-down frames in 2.5D (and 2D with ACA_TD_2D=1).
- `m3_broadcast_preview.py` 36 - Capture the M3 broadcast bridge, including action endpoints and long holds.
- `m3_ko_preview.py` 33 - Capture Kill Order's four directed 3D shots on either backend.
- `m3_staging_preview.py` 39 - Capture M3's service bridge: python tools/m3_staging_preview.py [--backend software].
- `m3_td3d_shots.py` 83 - Render Mission 3 frames in 2.5D (and 2D with ACA_TD_2D=1).
- `m4_gameplay_video.py` 452 - Record a bot-played Mission 4 gameplay video (2.5D) to MP4.
- `m4_intro_patch.py` 61 - Replace the M4 intro shot-list table in missions/m4/meta.py.
- `m4_probe.py` 24 - Probe the audio sound registry for names the M4 intro might reuse.
- `m4_td3d_shots.py` 110 - Render Mission 4 frames in 2.5D (and 2D with ACA_TD_2D=1).
- `m5_cinematic_polish_check.py` 76 - Regression evidence for the M5 noir polish; safe isolated preview only.
- `m5_contact_sheets.py` 52 - Build labelled contact sheets + automatic frame stats from previews/m5_encounter_review.
- `m5_cut_check.py` 32 - Round-2 M5 cutscene check: renders every m5x_ take (3D, then 2D fallback).
- `m5_draw_audit.py` 14 - Compatibility wrapper: the per-mission draw census is tools/ae_draw_audit.py.
- `m5_dump.py` 18 - (no docstring)
- `m5_encounter_review.py` 173 - Deterministic M5 preview suite.
- `m5_ending_stage_check.py` 184 - Ending staging/weapon regressions and native-size visual probes; safe saves.
- `m5_feedback_check.py` 170 - Focused M5 feedback regressions and visual evidence, without touching saves.
- `m5_finale_cut_check.py` 121 - Focused check for retiring the M5 finale without losing campaign completion.
- `m5_fx_check.py` 68 - M5 FX checks: reduced motion zeroes handheld/shake/roll; 2D fallback still works.
- `m5_gauntlet_cycle.py` 169 - M5 visual gauntlet - one full cutscene render cycle at delivery resolution.
- `m5_gauntlet_sheet.py` 51 - Compact WebP contact sheet for remote VLM review.
- `m5_gauntlet_shots.py` 124 - M5 gauntlet: render every Mission 5 surface we review (top-down stages, sprite close-ups, every 3D cutscene take + 2D...
- `m5_harbour_art_check.py` 59 - M5 harbour pass guard: the cubical cast and the choreography are pinned, art is validated.
- `m5_laser_stair_check.py` 58 - M5 laser integration and stair landing regression, both renderer backends.
- `m5_probe.py` 54 - render M5 cutscene frames headless for visual review.
- `m5_r2_check.py` 62 - Round-2 M5 headless check: builds stages, draws a few frames, saves PNGs.
- `m5_rifle_clearance.py` 55 - Weapon clearance against actual torso/head/pelvis box meshes, plus grip reach.
- `m5_shadow_check.py` 280 - Fresh M5 3D finale: geometry, timing, actual app player and save handoff.
- `m5_sheet.py` 42 - Contact sheet for review: python tools/m5_sheet.py out.jpg name1 name2 ...
- `m5_shots.py` 66 - M5 3D cutscene stills + timing: python tools/m5_shots.py OUT_DIR [scene_prefix]
- `m5_sprite_review.py` 45 - Montage of selected baked M5 sprites for review.
- `m5_stair_room_check.py` 73 - Regression: interiors cover the frame and both stair actors remain visible.
- `m5_td3d_shots.py` 55 - Render Mission 5 frames in 2.5D (and 2D with ACA_TD_2D=1).
- `m5_topdown_frame.py` 55 - Render one M5 top-down frame (the quarter night) as the house-style target.
- `m5_view_export.py` 47 - Pack review images for remote viewing: prints one JSON line per image {name, b64 JPEG}.
- `m6_ammo_check.py` 80 - Focused headless regression for the M6 K-9 supply ladder.
- `m6_bench.py` 181 - M6 3D scene frame bench + profile (diagnostic, not a CI gate).
- `m6_diag.py` 180 - One-command M6 3D performance diagnostic - run this on the stuttering PC.
- `m6_halo_sheet.py` 120 - B8 tuning sheet: one M6 sodium lamp at 5/15/40/80 m, four depth cases.
- `m6_hitch.py` 163 - Hitch hunter for the M6 3D scenes.
- `m6_layout_probe.py` 93 - M6 layout probe: every authored coordinate must land on open floor.
- `m6_loop_probe.py` 126 - Whole-game frame-interval probe for a dev-booted M6 scene.
- `m6_melee_strip.py` 82 - Melee parity check: render one M6 K-9 swing frame by frame.
- `m6_phases.py` 107 - Phase-level timing of the M6 train / yard draw (GL path).
- `m6_prof.py` 66 - (no docstring)
- `m6_shots.py` 416 - M6 3D film + interactive train stills.
- `m6_snow_probe.py` 113 - Customs snow probe (dev only, not a CI gate).
- `m6_td3d_shots.py` 53 - Render Mission 6 frames in 2.5D (and 2D with ACA_TD_2D=1).
- `m6_topdown_shots.py` 156 - Top-down M6 review stills (customs / no-man's-land / rail yard).
- `m7_prof.py` 87 - Profile the Mission 7 raid frame headless.
- `m7_route_probe.py` 28 - Collision and safe-dismount regression for the Mission 7 tractor.
- `m8_chase_diff.py` 25 - Compare consecutive chase frames: how much does the background actually change?
- `m8_chase_shots.py` 61 - Render the M8 tractor chase at points along the route, for eyeballing the set.
- `m8_descent_shots.py` 92 - Render the M8 descent film frames and the first chase frame, and check the handoff.
- `make_art_pack.py` 1249 - author assets/art/*.png (phases 1, 2, 4 art).
- `make_short_branded.py` 217 - branded 9:16 vertical Short from the final master.
- `make_short_clean.py` 101 - 9:16 vertical Short from the final master.
- `make_station_sprites.py` 144 - author the hero-interactable sprites.
- `map_assets3d.py` 213 - Keep docs/ARCHITECTURE_MAP.md section 8.1 in sync with assets/3D/.
- `mp_arena_duo.py` 101 - Launch TWO full game windows already sitting in the multiplayer arena.
- `mp_bot.py` 132 - Headless fake player, for testing multiplayer on ONE PC.
- `mp_choreo_probe.py` 269 - gate the MP trailer fight headlessly before capturing.
- `mp_host.py` 285 - Self-hosted KRAPNET server for Call of Acaristan.
- `mp_host_main.py` 23 - PyInstaller entry point for the self-hosted lobby EXE.
- `mp_join.py` 196 - Join a friend's Call of Acaristan lobby and chat.
- `mp_match.py` 429 - Play a real multiplayer arena match.
- `mp_net_soak.py` 572 - Headless arena network test with optional TCP and UDP impairment.
- `mp_remaster.py` 36 - Re-master audio only: reuse the kept premix.wav, re-run normalise + mux.
- `mp_server.py` 533 - Standalone KRAPNET master server for Call of Acaristan.
- `mp_trailer_assemble.py` 852 - post-production assembler for the MULTIPLAYER announcement trailer.
- `mp_trailer_assemble_tiktok.py` 867 - 9:16 TikTok cut of the multiplayer announcement.
- `mp_trailer_capture.py` 2002 - REAL multiplayer arena footage for the announcement trailer.
- `oilrig_preview.py` 120 - Off-screen preview of the oil-rig strike cinematic (missions.walking_attack3d).
- `overlay_cleanup.py` 69 - Tidy a project root after pasting the slim overlay zip over an older checkout.
- `patch_m7_raidin.py` 103 - One-shot data patch for the M7 raid-in film caption - run from the repo root:
- `preflight_bot_test.py` 68 - Offline pre-flight: exercise GridNav + ArenaBot + foley payloads against a bare ArenaSim (no sockets, no capture) to...
- `preview_mission_failed.py` 166 - Render/test all failure terminals; --show opens a safe, save-free gallery.
- `publish_update.py` 226 - Publish an update package and manifest for the Call of Acaristan Launcher.
- `record_fresh_action.py` 1007 - clean standalone combat capture.
- `render_ko_video.py` 324 - Headless cinematic trailer bot, PLAN_2 cut.
- `render_m4_ending.py` 205 - Render the real M4 cutscene player safely, without importing app's loop.
- `render_m5_ending.py` 66 - Render M5 with the production cutscene player, using the safe M4 capture kit.
- `render_m5_shadow.py` 75 - Capture the production M5 finale at 30 fps with native ambience/foley.
- `render_m5_stair.py` 82 - Export the complete updated M5 stair shot with its production sound cues.
- `render_m7_feedback.py` 193 - Render review shots for the Mission 7 feedback pass (software renderer).
- `render_m7_previews.py` 36 - (no docstring)
- `render_trailer.py` 762 - 75-90s MP4 game trailer (headless real gameplay).
- `render_trailer_v2.py` 626 - cinematic finish wrapper over render_trailer.py.
- `shot_fail_screens.py` 35 - Polish pass T9 evidence: render the Mission Failed screen for M1-M5.
- `shot_m5x.py` 57 - Polish pass evidence helper: render M5X 3D cutscene frames to PNG.
- `shot_outfit.py` 134 - Polish pass Task 5 evidence: Biribel's M5 Guard kit in every view.
- `shot_radio.py` 207 - Polish pass Task 6 evidence: the radio transmission widget in every mission.
- `shot_speechbox.py` 137 - Evidence shots for the shared speech box (``ui.speechbox``).
- `shot_weapon_grid.py` 108 - Polish pass Task 4: weapon-attachment verification grid.
- `slim_tree.py` 222 - remove dead weight from the project root (dry run by default).
- `smoke_test.py` 12723 - Public: `EmptyKeys`, `run_check`, `run_import_check`, `clear_screen`, `check_menu_draw`, `check_settings_draw`, `check_multiplayer_opens_on_server_browser`, `check_host_is_taught_how_to_host`
- `test_m7_pig.py` 83 - Focused geometry and raid gait regression checks; run from the project root.
- `test_m7_pig_death.py` 185 - The pig in the 3D raid, and what it costs.
- `test_multiplayer_ui.py` 88 - Small presentation regression suite; no live networking or external service.
- `test_oilrig_collapse.py` 137 - Geometry and effect regressions for the rig collapse repair.
- `test_tcp_tunnel.py` 79 - Fast stdlib-only tunnel regression tests (no pygame or internet required).
- `tex3d_draw.py` 510 - Draws the M6 3D pixel textures (assets/tex3d/<name>.png) from the 2D palette.
- `tex3d_draw_m7.py` 397 - Draws the M7 farm 3D pixel textures (assets/tex3d/m7_<name>.png) from the 2D farm palette (src/cutscenes/m7palette3d....
- `van3d_shot.py` 26 - Render the 3D van_exterior take to PNGs: python tools/van3d_shot.py [t_ms ...]
- `view_cast3d.py` 119 - Interactive 3D character viewer (defaults to andrei_m).
- `voice_audit.py` 545 - Voice-line audit (polish pass T1).
- `walk_fp_shots.py` 81 - Render stills of the walking-sim first-person reward cutscenes.
- `walk_probe.py` 142 - framed shots + draw-cost probe for the walking sim.
- `walk_td3d_shots.py` 50 - Render walking-sim frames in 2.5D (and 2D with ACA_TD_2D=1).
- `zip_project.py` 470 - Zip this project into a single archive, optionally uploading it to Pixeldrain.

**`tools/ost/`**

- `album.py` 982 - Call of Acaristan - Original Soundtrack.
- `mv.py` 1297 - OST music videos: one short, loopable 3D scene per album track (engine3d, GL).
- `synth.py` 875 - Small numpy synth for the Call of Acaristan OST.

**`tools/sprites/`**

- `compare_shots.py` 47 - stitch T7 before/after shots side by side.
- `fx.py` 174 - Mission 2 tanker-blast aftermath as sprites (Polish T7).
- `inventory.py` 212 - Procedural-art inventory (Polish Task 7, step 1).
- `kit.py` 241 - shared machinery for the tools/sprites/<family>.py generators.
- `m1_street.py` 399 - Mission 1 street band furniture (WP4) as authored sprites.
- `mission_failed.py` 392 - Bespoke, entirely code-drawn mission-failure vignettes.
- `palette.py` 121 - the locked house palette shared by every tools/sprites generator.
- `portrait_refs.py` 79 - check the radio portraits against the cutscene cast.
- `portraits.py` 1156 - radio caller-ID portraits (polish pass T6b).
- `props.py` 278 - Mission 2 story props + the upload terminal as sprites (Polish T7).
- `t7_probe.py` 155 - before/after shots + draw-time probe for Polish T7.
- `vehicles.py` 463 - Mission 2 road vehicles as authored sprite sheets (Polish T7).

**`tools/trailer3d/`**

- `common.py` 401 - Shared trailer helpers: renderer setup, camera keys, 2D light/rain/grain FX, letterbox + text.
- `music_cut.py` 125 - Cut 'Shell Ghost' (Soundridemusic) to the 80 s trailer timeline.
- `props3d.py` 352 - Low-poly trailer props built from engine3d boxes/prisms (y up, metres).
- `render.py` 142 - Render the cinematic trailer.
- `sfx.py` 301 - Synthesised sound design for the cinematic trailer, laid onto the music+VO mix.
- `shots.py` 1367 - The trailer's shots.
- `thumbnail.py` 176 - YouTube thumbnails (1280x720) composed from real trailer frames.
- `vertical.py` 235 - 9:16 TikTok / YouTube Shorts / Reels cut of the cinematic trailer.
- `vo_mix.py` 202 - Place the trailer narration on the 80 s music cut and mix it.

**`tools/trailer_25d/`**

- `capture.py` 74 - Gameplay clips for the 2.5D announcement trailer (TVA 1 broadcast).
- `capture_m4.py` 17 - Mission 4 2.5D clip for the announcement trailer: the m4_gameplay_video bot run with its captions and title cards swi...
- `capture_mp.py` 53 - Multiplayer arena clip (2.5D) for the announcement trailer.
- `capture_tilt.py` 64 - The switch shot: one continuous M1 bot run that starts in the flat 2D view, flips to 2.5D and tilts the camera from s...
- `capture_wave.py` 66 - The switch shot, recorded twice per tick: one M3 bot run drawn in the flat 2D view and in 2.5D on the same sim frame,...
- `render.py` 1195 - TVA 1 broadcast: the 2.5D announcement trailer.
- `sets.py` 724 - 3D sets for the TVA 1 broadcast: studio desk, palace podium with the depth lever, the block flat, the neighbour's win...
- `shorts.py` 353 - Four vertical shorts (1080x1920, 30 fps) cut from the 2.5D announcement.
- `thumbnail.py` 183 - YouTube thumbnail for the 2.5D announcement (1280x720).

**`tools/trailer_rpe6/`**

- `dark.py` 573 - Dark story trailer for Call of Acaristan, cut to "Dark Cello Horror Trailer Music".
- `dark_films.py` 618 - New staged scenes for the dark trailer, built on the Mission 7 farm set.
- `dark_short.py` 304 - Vertical 1080x1920 Short of the dark trailer, and thumbnails for both.
- `render.py` 1098 - RPE6 engine trailer for Call of Acaristan: the engine and the game, no story.
- `render_m7.py` 311 - RPE6 trailer, Mission 7 cut: the 80 s engine trailer with Fallow Ground in it.
- `score.py` 160 - Sound for the RPE6 trailer: "Shell Ghost" (Soundridemusic), placed so its first hit lands on the voxel logo, under sy...
- `shorts.py` 573 - Vertical 1080x1920 cuts of the RPE6 trailer for TikTok / YouTube Shorts.

## 22. Tests index (`tests/`)

Run `python -m unittest discover -s tests/unit -t .` (or `pytest tests/unit`). Baselines are listed in §18.

**`tests/`**

- `__init__.py` 0 - (no docstring)

**`tests/unit/`**

- `__init__.py` 0 - (no docstring)
- `_helpers.py` 22 - Shared test setup: put ``src`` on sys.path and keep SDL headless.
- `_path.py` 7 - (no docstring)
- `test_anim_props.py` 63 - Phase 11 step 10: flicker is a deterministic closed form; set fields written as timeline expressions animate with the...
- `test_app_boot_crash.py` 128 - engine.core.App: headless boot, service wiring, crash report (§6.1 acceptance).
- `test_art_cache.py` 45 - art_cache.get_plate_bg: the shared M4/M5 "status plate" chrome.
- `test_assets_registry.py` 368 - engine.assets Phase 3: manifest schema, registry chain + cache + ref-counts, bake/check hashing, lint, hot reload (wa...
- `test_bloc3d.py` 179 - Phase 5: the Bloc landmarks and Cyrillic signage build sane boxes.
- `test_cast_shadows.py` 58 - Phase 11 step 7 (ADR-023): baked cast shadows - occluded faces darken, open faces do not, quality 0 disables the bake.
- `test_clock.py` 172 - engine.core.Clock: fixed-step semantics, identity with the legacy FixedStepClock (ADR-004).
- `test_devtools.py` 100 - RPE6 Phase 10 (§6.19): debug overlay / inspector data builders + console commands.
- `test_egg666.py` 268 - Tests for the 3D "666" safe-keypad scare (ui/egg666_*.py).
- `test_engine_ai.py` 253 - engine.ai: behaviour tree preemption and memory, sight reaction and forgetting, noise muffling, squad radio/tokens/cl...
- `test_engine_boot.py` 72 - App.boot display ownership (ADAPTER A-001).
- `test_engine_collision.py` 150 - engine.collision: box rays and segments agree with brute force, and grid nav routes round walls, through gaps and nev...
- `test_engine_collision_mesh.py` 79 - engine.collision.mesh: hitboxes follow the mesh's triangles, not a box around it, and a placed mesh uses the renderer...
- `test_engine_core.py` 177 - Unit tests for engine.core (stdlib unittest; run: python -m unittest discover -s tests/unit -t .).
- `test_engine_dialogue_box.py` 89 - engine.ui.std.dialogue_box (Phase 4): theme injection, slide ownership.
- `test_engine_level_dialogue.py` 144 - engine.level + engine.dialogue kernels: load/validate, Tiled import, runner conditions/effects (RPE6 Phase 7).
- `test_engine_render2d.py` 310 - engine.render2d kernel: queue order, drawables, rotation cache, camera, static chunks, post-FX parity (RPE6 Phase 6).
- `test_engine_settings_save_input.py` 142 - engine.settings / engine.save / engine.input kernels (RPE6 Phase 9).
- `test_engine_shims.py` 72 - A-006 shims: the legacy paths re-export the engine implementations unchanged.
- `test_engine_text.py` 213 - engine.text Phase 4: string tables + `T()`, font registry + glyph coverage, layout (measure/wrap/ellipsize/check_fit/...
- `test_engine_timeline_set3d.py` 98 - engine.timeline + engine.render3d kernels: expressions, sampling, set building (RPE6 Phase 8).
- `test_engine_ui.py` 142 - engine.ui Phase 4: Theme + the standard widgets, drawn headless.
- `test_engine_world.py` 233 - engine.world kernel: registry, storage, views, queries, scheduler phases, prefabs (RPE6 Phase 5).
- `test_events_log_services.py` 140 - engine.core: EventBus (§6.3), Log (§6.23), Services and Settings (§6.1).
- `test_faces3d.py` 78 - Phase 11 step 8: expressions rebuild only the face, mouth flap is a deterministic closed form, look-at clamps, mouth...
- `test_frame_pacer.py` 62 - core.frame_pacer: whole fixed steps per frame, rate drop on slow frames, never below 30 fps, lone spikes keep the rate.
- `test_game_dialogues.py` 74 - game.dialogues converter: node chain -> legacy beat dicts (RPE6 Phase 7).
- `test_game_world_bridge.py` 228 - game.world bridge (RPE6 Phase 5, D4): ensure/get, roster reset + removed-tag policy, WalkCycle.advance.
- `test_gl_composite.py` 113 - GL renderer item-queue regression (owner-hardware crash, M5 finale).
- `test_hold.py` 71 - Public: `HoldTests`
- `test_ik.py` 124 - engine3d.ik: analytic arm/leg IK and the shouldered rifle hold land on their targets as measured by the rig's own for...
- `test_m3_broadcast3d.py` 95 - Broadcast bridge framing, settled blocking, registry routing and seeking.
- `test_m3_door_orientation.py` 49 - M3's visual door panels follow the wall, including every double leaf.
- `test_m3_ko3d.py` 229 - Kill Order 3D routing, seekable action, stair support and cover geometry.
- `test_m3_molotov_gate.py` 48 - M3 must not create un-simulated molotovs from the shared input handler.
- `test_m3_staging.py` 180 - M3's first 3D bridge: deterministic seeking, prop contact and fallback.
- `test_m5_ending.py` 179 - M5 finale regressions.
- `test_m5_finale_audio.py` 220 - Focused M5 sound/lifecycle regressions, without starting app or saves.
- `test_m6_campaign.py` 1089 - Mission 6 campaign regressions.
- `test_m7_campaign.py` 353 - Mission 7 campaign regressions.
- `test_m8_chase_gun.py` 327 - The mounted LMG must never pass through Biribel in the tractor chase.
- `test_m8_chase_scenery.py` 62 - The trailer's rearward view must change as the tractor crosses four regions.
- `test_m8_chase_traffic.py` 230 - The tractor chase traffic must be solid, enter from off-camera, and swerve around wrecks only when the steering limit...
- `test_m8_trap_mechanics.py` 129 - M8 trap scene: the plaza fight's new mechanics.
- `test_mathx_profiling.py` 51 - engine.core.mathx and Profiler.
- `test_mesh_import.py` 134 - Phase 11 step 11 (ADR-024): the importer converts OBJ/glTF into ae.mesh/1 with palette snapping + triangle budget; th...
- `test_phase1_rng_imports.py` 58 - Phase 1 checks: legacy rng stream (R6) and m3 import side effects (B-010).
- `test_post3d.py` 79 - RPE6 Phase 11 step 5: cinematic post stack (cutscenes.post3d).
- `test_presets.py` 71 - RPE6 Phase 11 step 1: lighting preset resolution (engine.render3d).
- `test_render3d_p11.py` 57 - RPE6 Phase 11: local lights, contact shadows, baked AO (data -> bridge).
- `test_render_adapters.py` 259 - Phase 6 peel-off twins are pixel-identical to the legacy painters they replace (RPE6, ADR-017).
- `test_rng.py` 85 - engine.core.rng: named streams are independent, seeded, snapshot-able (R6, B-002).
- `test_scene_mirror.py` 104 - core.scene_mirror (A-005): the legacy FSM replayed onto an engine SceneStack.
- `test_scene_stack.py` 161 - engine.scene: lifecycle, overlay/passthrough dispatch, deferred mutations, trace (§6.2).
- `test_scene_types.py` 152 - engine.scene.CutsceneScene / InspectScene (§6.2) and the mirror's scene factory (A-007).
- `test_scenery3d.py` 101 - Imported scenery budgets, grounded placement, live displays and fallbacks.
- `test_textures3d.py` 85 - Phase 11 step 9: palette textures load through the bridge, UV payloads attach at quality >= 1 only, and pass through...
- `test_timeline_edit_scene.py` 58 - Phase 8 tooling surface: ae_timeline_edit round-trip + CutsceneScene.from_timeline.
- `test_voice_timing.py` 163 - Voice clip timing must not depend on SDL's decoded length (asset diet, 2026-10-14).
- `test_weather3d.py` 76 - Phase 11 step 6: weather is a closed-form, seeded, quality-gated function of (prims, t) - same inputs, same sprite ca...
