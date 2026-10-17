# Tutorial: add a mission (RPE6)

Build a complete, playable mission — one level, two enemy types, one
dialogue, one 3D cutscene, one inspect shot, a HUD plate — **without
editing anything under `src/engine/`**. Mission 0
(`src/missions/m0/` + the `mission0.*` files under
`src/game/content/`) was built by
following this document; `tools/ae_mission0_check.py` proves it plays
start to finish and that the engine tree is untouched.

## 0. Scaffold

```bash
python tools/ae_new_mission.py mission0 --package m0 --title "Mission 0 - Depot"
```

This creates (and refuses to overwrite):

Content lives where the existing loaders look (ids are file stems):

| File | What it is |
|---|---|
| `src/game/content/levels/mission0.depot.level.json` | `ae.level/1` grid + objects + triggers (id `mission0.depot`) |
| `src/game/content/dialogue/mission0.briefing.dlg.json` | `ae.dialogue/1` conversation (id `mission0.briefing`) |
| `src/game/content/timelines/mission0.outro.timeline.json` | `ae.timeline/1` outro shot list (id `mission0.outro`) |
| `src/game/content/sets/mission0.depot.set3d.json` | `ae.set3d/1` set for the 3D shot (id `mission0.depot`) |
| `src/missions/m0/enemy_types.json` | enemy-type table + objective/HUD strings (host-local data) |
| `src/missions/m0/__init__.py` | the host: start/update/draw + cutscene renderers |

Then do the three wiring edits the scaffolder prints (§5 below).

## 1. The level (`ae.level/1`)

`layers.floor` is a list of equal-length strings, one char per tile
(64 px). Mission 0's host treats `#` as solid and `=` as the exit zone;
your own host decides which chars are solid — the *data* only carries
the grid, `objects` (`{id, kind, tile, props}`) and `triggers`
(`{id, kind, rect}` in tiles). Author grids with `core/mapbuilder.py`
or by hand; keep rows equal length. Validate any time:

```bash
python tools/ae_validate.py        # every content file, all schemas
```

Useful object kinds by convention: `spawn` (`props.who` =
`player`/`enemy`), `inspect` (an interactable point). Enemy spawns
carry `props.type`, a key into your enemy-type table (§2).

## 2. Enemy types

Legacy missions share the `entities.enemy_ai.Enemy` brain; a *type* is
a stat block your host applies at spawn. Put the table in
`src/missions/m0/enemy_types.json`:

```json
"enemy_types": {
  "sentinel": {"hp": 200, "speed": 2.0, "sight_mul": 1.0},
  "charger":  {"hp": 90,  "speed": 3.4, "sight_mul": 1.35}
}
```

Spawn: `e = Enemy(x, y); e.hp = t["hp"]; e.speed = t["speed"]; e.sight_mul = t["sight_mul"]`.
Different tuning on the shared brain is the legacy pattern; brand-new
behaviours would be a game-side system around it, never an engine edit.

## 3. The dialogue (`ae.dialogue/1`)

A node graph: `start`, `speakers`, `nodes {id: {speaker, text, next}}`.
Play it with `engine.dialogue.DialogueRunner` over
`game.dialogues.dialogue(id)`; your host implements the six-method
`DialogueHost` protocol (flags/vars/text resolution). Draw the current
line with the legacy dialogue box (`cutscenes.draw_dialogue_box`) so
the look matches the campaign. Advance on the `advance` action
(Space/Enter). All rendered text must stay in the covered glyph set —
`tools/ae_text_check.py` runs in CI.

## 4. The cutscene (`ae.timeline/1` + `ae.set3d/1`)

The outro is a shot list whose `scene` ids name renderers. Two of
Mission 0's are its own, registered at import:

```python
from core.cutscene_registry import register_scene_renderer
register_scene_renderer("m0_inspect", _draw_inspect)   # fn(surface, t_ms)
register_scene_renderer("m0_depot3d", _draw_depot3d)
```

- **Inspect shot** (`m0_inspect`): a close-up plate — draw the object
  large, add a caption. Keep it data-light: the shot dict carries
  `text`/`speaker` like every other shot.
- **3D shot** (`m0_depot3d`): build the set from data with
  `game.render3d_bridge.set_prims("mission0.depot")`, feed the
  meshes to an `engine3d.Renderer` (see `cutscenes/m5martial3d._rend`
  for the pool pattern; a module-level single renderer is fine at this
  size), set the camera, render into an offscreen buffer, blit it into
  the letterbox band. Sets use `box`/`quad_xz`/`sprite3d` nodes;
  `tools/ae_set3d_check.py` validates them.

Trigger playback through the app's existing pattern: the host keeps a
module-level request flag and exposes `take_outro_request()` (reads +
clears it — do NOT add fields to `STATE`, §10); `app` consumes it with
`start_cutscene(shots, "MISSION_COMPLETE")` and transitions to
`CUTSCENE` (the same three lines every pickup cutscene uses).

## 5. Wiring (the only shared-code edits, all game-side)

1. `core/game_core.py`: `_is_mission0_active()` next to the other
   `_is_missionN_active()` helpers, a `start_mission0()` forwarder, and
   one branch each in `_mission_update()` / `game_draw()` (M0 draws as
   one `CustomDraw`, like M1–M4).
2. `app.py`: a `--dev-mission0` branch in `_apply_dev_args`, and the
   outro-request consumption in `_GameState.update` (mirror the
   `request_seby_pickup_cutscene` block).
3. `core/dev_jumps.py`: `"m0": ("--dev-mission0", "Mission 0 - ...")`.

## 6. The host contract

`missions/m0/__init__.py` provides:

- `start_mission0(preserve_timer=False)` — reset STATE slice, build
  walls/spawns from the level, `STATE.active_mission = "MISSION0"`,
  begin the briefing dialogue.
- `game_update(keys)` — a tiny phase machine (`briefing` → `play` →
  `done`): advance dialogue, move the player with axis-separated
  collision against `STATE.walls`, step enemies
  (`e.update(px, py, walls, bullets, particles)`), test the exit
  trigger, set the outro request. Movement *is* the one thing you
  write by hand; copy the axis-collision shape from any mission.
- `game_draw(surface, cx, cy)` — painter passed to the render host:
  floor/walls by grid char, exit zone, enemies and player as simple
  figures, then the HUD plate (`engine.ui.std` objective banner +
  health bar) and the dialogue box while briefing.

Keep STATE writes to fields your host owns (`m0_*` + the shared
slots every mission uses: `player`, `enemies`, `walls`, `bullets`,
`particles`, `active_mission`).

## 7. Prove it

```bash
python tools/ae_mission0_check.py   # AE MISSION0: OK
python tools/ae_ci.py               # mission-0 row green
```

The check boots the mission headless, walks the player to the exit on
the grid path, asserts the briefing was consumed and the outro was
requested, renders every outro shot (inspect + 3D included), and
verifies the `src/engine/` tree hash against the value recorded before
Mission 0 existed — the zero-engine-diffs proof (D2).

## Pitfalls (learned building Mission 0)

- `Enemy.update` wants `(px, py, walls, bullets, particles)` — the
  lists must be the STATE lists, or hits go nowhere.
- Shot renderers registered by id must be *imported* before the
  cutscene plays; importing your mission package in `game_core` covers
  it (the registry pattern is A-003).
- `game.timelines.shots()` returns fresh dicts; mutating them is safe.
- Content ids are file stems in each loader's own directory:
  `mission0.outro` → `content/timelines/mission0.outro.timeline.json`,
  `mission0.briefing` → `content/dialogue/mission0.briefing.dlg.json`,
  `mission0.depot` → `content/levels/...` *and* `content/sets/...`
  (the same stem may name both a level and a set; the loaders don't
  collide because their directories differ).
