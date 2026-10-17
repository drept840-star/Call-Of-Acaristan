# Subsystem: `engine.ui` (Phase 4)

Shipped: 2026-10-15 · Report: `docs/engine/reports/phase4.md` · Evidence: `docs/engine/evidence/phase4_ui_20261015/`

## What it is

The widget kernel plus one module per standard widget. A widget draws onto a surface it is given and never
reads game state; the caller gathers the data. That is the property that let the missions delete their
duplicate HUD bodies without changing a pixel.

```
engine.ui            facade: Theme + the widgets (boundary rule E4: game code imports this, never std.<w>)
  theme.py           Theme(size, fonts, palette, viewport) - the only injected state
  std/<widget>.py    one widget per module, each with an explicit __all__
```

## Widget inventory (what each takes)

| widget | entry point | notes |
|---|---|---|
| `objective_banner` | `draw(surface, theme, text)` | wraps inside its own panel; self-fitting |
| `minimap` | `MiniMap(map_data, tile_size, palette, *, theme)` | class; palette names `m1…m4`, `walk`; `hud.minimap_north` is the `N` marker |
| `health_bar` | `draw(surface, theme, hp, max_hp, *, panel_bg)` | geometry knobs default to the M2–M5 look; M1 passes its own plain panel painter |
| `weapon_panel` | `draw(surface, theme, info, *, panel_bg, mag_icon)` | `WeaponInfo.from_state(STATE)` helper; `mag_icon(surface, mx, my, kind, rounds, cap, active)` keeps each mission's magazine art (that is the dedup, not a shared painter) |
| `hostiles` | `draw(surface, theme, n)` | M5 filters the enemy list before calling |
| `dialogue_box` | `draw(surface, theme, text, *, ...)` | slide state lives in the widget; `cutscenes/engine.py` keeps the A-009 shim |
| `bottle_hud` | `draw(surface, theme, count, cap, *, panel_bg, icon)` | M2 imports M1's `_draw_molotov_icon` as the icon painter |
| `crosshair` | `draw(...)`, `draw_combat(...)`, `color_for(mode, default=...)`, `COLORBLIND_COLORS` | no `Theme`: the colour policy comes from settings; missions keep their own gating |
| `prompt` | `draw(surface, sx, sy, text, col, *, font, y_off, icon, fallback_font, fill, rim, radius, pad, clamp, max_label_w)` | world-anchored tag (M3's body); M5 passes its chrome + `clamp=False`; `icon` is an already-resolved surface (the caller owns the art pack) |

Widgets that do not need a `Theme` say so in their docstring (`crosshair` = colour policy, `prompt` = the
two callers resolve fonts from different modules). That is a deliberate, documented exception to "every
widget takes a Theme", not an accident.

## Conventions

- **Purity**: no game imports, no `STATE`, no file access. Art is injected (`mag_icon`, `icon`,
  `panel_bg`). `engine.ui` may import `engine.text` (`T`) and pygame only.
- **A-009 shims**: `src/ui/hud.py` (and `cutscenes/engine.py` for the dialogue box) keep the legacy names
  so unmigrated callers and tests keep working: `THEME`, `MiniMap`, `draw_objective_panel`,
  `draw_pinned_radio`, `PINNED_RADIO_MAX_VISIBLE`, `draw_crosshair`, `draw_combat_reticle`, plus `THEME`
  in `ui/hud.py` as the single game-side theme object.
- **Shared chrome, injected content**: the dark-glass "status plate" both missions drew inline is
  `entities/art_cache.get_plate_bg(w, h)` (cached; locked to the legacy pixels by
  `tests/unit/test_art_cache.py`). `ui/system.py` and `ui/arena_view.py` share only the plate *fill*
  colour, not the chrome — recorded here so nobody "dedups" them later.
- **Self-fitting widgets**: anything whose column is not fixed must fit itself (prompt: fallback font →
  integer guard → `smoothscale` → viewport clamp; dialogue box and objective banner wrap). Those strings
  therefore do not need `FIT_SLOTS` entries in `tools/ae_text_check.py`.

## Deliberate mission-side HUD (exceptions)

| owner | what stays | why |
|---|---|---|
| M1 | 12-bullet trapezoid ammo panel + reload bar that replaces the MAGS line | a different design, not a parameter of `weapon_panel` |
| M2 | curved ammo/mag panel | same |
| M4 | hold-the-transmitter clock (content) | geometry/right-readout differ from M5's plate; chrome is shared |
| M5 | quarter HUD (convoy clock, HEAT pips, visibility chip) + raid plate | single-owner gameplay HUD with its own predicates |
| MP arena | name tag (`_draw_name_tag`) | single copy, no cross-mission duplicate |
| M5 | visibility chip (the "stealth indicator") | single copy; its strings are in the table |

## How to add or change a widget

1. New module under `src/engine/ui/std/` with **`__all__`** (the API snapshot fails without it).
2. Export it from `std/__init__.py` **and** `engine/ui/__init__.py` (both lists, alphabetical).
3. Add it to the A-009 shim if legacy callers must keep working.
4. `python tools/ae_api_snapshot.py record` then `check` (deliberate surface change).
5. Add a headless unit test in `tests/unit/test_engine_ui.py`; if it draws table strings, add `FIT_SLOTS`
   entries in `tools/ae_text_check.py`.
6. Gates: golden (`tools/ae_golden.py verify`), loop, `--md` census regen, full `tools/ae_ci.py`.
