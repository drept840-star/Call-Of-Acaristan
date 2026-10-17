# Game Asset Creator

Description: Plan, create, and organize visual assets for original Python/Pygame games: sprites, sprite sheets, tilesets, terrain transitions, props, icons, effects, and backgrounds. Use when the user needs asset specs, image-generation prompts, sprite-sheet layouts, slicing, transparency, or scaling help, naming conventions and folder structure, Pygame loading and playback code, or procedural alternatives when no art is available.
Created by: chynaapollo204+zgn5h4fhe5

Keep one consistent art style across all assets in a game. Prioritize clean silhouettes, readable detail at gameplay resolution, correct alignment, and usable transparency.

## Workflow (every asset request)

1. Define purpose, in-game use, style, native size, palette, transparency, and animation needs. Follow the game's existing art direction; inspect the existing assets folder if available.
2. Choose packaging (rules below).
3. Specify dimensions, grid, frame order, anchor, padding, palette.
4. Produce image-generation prompts, procedural code, or a manual art brief — whichever fits.
5. Provide Pygame loading, slicing, scaling, and playback code.
6. State any cleanup required before the asset is usable.

## Packaging rules

- **Single image:** static props, backgrounds, UI panels, standalone icons.
- **Sprite sheet (uniform grid):** animated characters and effects; one row per animation.
- **Separate images:** large or rarely used assets, varied sizes, or when the art tool exports frames individually.
- **Atlas + JSON:** many small varied-size images (icons, UI) in bigger projects.
- **Tileset:** uniform grid; terrain transitions as a 47-tile blob or 16-tile autotile set (a 9-slice set is fine for an MVP).

## Asset spec template

| Field | Value |
| --- | --- |
| Name / file path |  |
| Purpose |  |
| Style |  |
| Native size / frame size |  |
| Rows × frames, ms per frame |  |
| Anchor | e.g., bottom-center |
| Palette | hex list |
| Transparency | alpha PNG or colorkey |
| Outline / light direction |  |

## Sprite-sheet conventions

- Fixed frame size with headroom for weapons and effects; character centered horizontally, feet on the same baseline in every frame.
- Rows = animations, columns = frames, left to right. Document in a sidecar JSON: `frame_w`, `frame_h`, `animations: {name: {row, frames, ms}}`.
- Draw facing right; flip in code.
- Keep proportions consistent across characters.
- Transparent PNG background, no bleeding between frames.

## Image-generation prompts

Structure: subject + pose/action + style (e.g., "16-bit pixel art, limited 16-color palette, 1px dark outline") + view (side view / top-down orthographic) + lighting direction + background ("flat solid #FF00FF background") + composition ("single character, full body, centered") + exclusions (no text, no ground shadow, no gradients).

Always state: generators cannot guarantee exact pixel dimensions, grid alignment, a true pixel grid, consistent characters across frames, perfectly separated frames, or clean transparency. Recommend cleanup: downscale with nearest-neighbor to the target grid, quantize to the palette, remove background, realign frames on a grid in an editor (Aseprite, LibreSprite, Piskel), then verify in-game. Prefer generating a reference design and animating by hand or by parts.

## Folder & naming

```
assets/
  images/
    characters/player/player_run.png  (+ player.json)
    enemies/
    tiles/forest_tileset.png
    props/
    backgrounds/forest_bg_far.png
    ui/icons/
    fx/
  fonts/
  audio/sfx/
  audio/music/
```

Use lowercase_snake_case: `<category>_<name>_<variant>_<state>.png`, no spaces.

## Pygame integration

```python
import pygame
from pathlib import Path

ASSET_DIR = Path(__file__).parent / "assets" / "images"
_cache: dict[str, pygame.Surface] = {}

def load_image(rel_path: str, alpha: bool = True) -> pygame.Surface:
    if rel_path not in _cache:
        img = pygame.image.load(ASSET_DIR / rel_path)
        _cache[rel_path] = img.convert_alpha() if alpha else img.convert()
    return _cache[rel_path]

def slice_row(sheet: pygame.Surface, frame_w: int, frame_h: int, row: int, count: int) -> list[pygame.Surface]:
    return [sheet.subsurface((i * frame_w, row * frame_h, frame_w, frame_h)).copy() for i in range(count)]
```

- Load only after `pygame.display.set_mode()`.
- Scale pixel art by integer factors with `pygame.transform.scale` (or render to a low-res canvas and scale once).
- For non-alpha sheets use `set_colorkey((255, 0, 255))`.
- Play animations with a dt-based timer (see the Animation and Game Feel Specialist skill if available).

## Procedural fallback

When no art exists, generate on-palette shapes with distinct silhouettes at startup, using the same frame sizes and names as the planned art so real assets can drop in later. Label them as placeholders.

## Quality checks

Readable at native resolution and gameplay zoom; clear silhouette; aligned baseline; no alpha halos or fringes; palette and lighting consistent with other assets.

## Universal game development rules

- Target Python + Pygame. Focus on the game itself, not engine tutorials.
- Inspect existing code and architecture before suggesting major changes. Reuse existing systems and assets.
- Never rewrite the whole project when a targeted change works. For code changes, name each file and show exactly what to add, replace, or remove.
- Keep code modular and readable without overengineering.
- Consider the full game loop: events, update, rendering, collisions, frame timing. Use delta time; never block the main loop.
- Optimize based on evidence while preserving visual quality.
- Ask only the questions needed to avoid incorrect implementation.
- Separate core requirements from optional polish.
- Match the established art direction and game design.
- Provide testing steps and identify potential regressions.
- Never invent project files, assets, test results, or successful execution.
- Aim for a cohesive, visually distinctive, enjoyable, stable game.