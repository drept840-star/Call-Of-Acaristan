# create-beautiful-pygame-graphics

Description: Write or upgrade PyGame (pygame / pygame-ce) code that has polished, good-looking visuals: game graphics, particles, glow and bloom, trails, screen shake, generative art and demos, menus and UI, and smooth eased animation. Use when the user asks to make a PyGame game or demo look better or more polished, add visual effects or juice, build a PyGame menu or HUD, make PyGame animations smoother, or review existing PyGame rendering code. Produces either a complete runnable script or targeted improvements to the user's code.
Created by: chynaapollo204+zgn5h4fhe5

## Goal

Produce PyGame visuals that look intentional and polished while staying smooth (60 FPS) on ordinary hardware.

## Inputs

- The request: a new scene/game/demo **or** existing code to improve.
- Optional: visual style (neon, pixel art, minimal, pastel…), resolution, target FPS. If no style is given, pick one that fits the subject and state it in one line.

## Workflow

1. Decide the mode:
    - **New**: write one complete, runnable `.py` file.
    - **Improve**: read the user's code, keep its structure and game logic, and change only rendering/feel. Explain each change briefly.
2. Choose a palette first: 1 background tone, 1–2 main colors, 1 accent. Define them as constants at the top. Never use pure `(255,0,0)`-style defaults.
3. Build the frame in layers: background (gradient/vignette) → world → effects (additive glow, particles) → UI → post (fade/flash/shake offset).
4. Add motion with delta time and easing (see toolkit). Nothing should snap; lerp positions, colors, scale.
5. Add "juice" where it fits: particles on events, brief flash/shake on impacts, hover/press feedback on UI.
6. Check performance rules (below) before returning.
7. If the computer is available, run the script headlessly for a few frames (`SDL_VIDEODRIVER=dummy`) and save a screenshot to verify it runs and looks right; show it if possible.

## Base template

Start new scripts from this skeleton.

```python
import math, random, sys
import pygame

W, H = 1280, 720
BG_TOP, BG_BOTTOM = (12, 10, 28), (40, 18, 60)
ACCENT = (255, 90, 170)

pygame.init()
screen = pygame.display.set_mode((W, H), pygame.SCALED, vsync=1)
pygame.display.set_caption("Demo")
clock = pygame.time.Clock()

def vertical_gradient(size, top, bottom):
    s = pygame.Surface((1, 2), 0, 32)
    s.set_at((0, 0), top); s.set_at((0, 1), bottom)
    return pygame.transform.smoothscale(s, size).convert()

background = vertical_gradient((W, H), BG_TOP, BG_BOTTOM)

while True:
    dt = min(clock.tick(60) / 1000, 0.05)  # seconds, clamped
    for e in pygame.event.get():
        if e.type == pygame.QUIT or (e.type == pygame.KEYDOWN and e.key == pygame.K_ESCAPE):
            pygame.quit(); sys.exit()
    # update(dt)
    screen.blit(background, (0, 0))
    # draw()
    pygame.display.flip()
```

## Visual toolkit

**Additive glow (cached).** Pre-multiply color into a black surface, then blit with `BLEND_RGB_ADD`. Overlapping glows brighten naturally.

```python
_glow = {}
def glow(radius, color):
    key = (radius, color)
    if key not in _glow:
        s = pygame.Surface((radius * 2, radius * 2))
        for r in range(radius, 0, -1):
            t = (1 - r / radius) ** 2
            pygame.draw.circle(s, [int(c * t) for c in color], (radius, radius), r)
        _glow[key] = s.convert()
    return _glow[key]
# screen.blit(glow(40, ACCENT), (x - 40, y - 40), special_flags=pygame.BLEND_RGB_ADD)
```

**Particles.** Keep in a plain list; update with dt, drag, gravity, fade by life; remove dead ones.

```python
class Particle:
    __slots__ = ("x", "y", "vx", "vy", "life", "max_life", "size", "color")
    def __init__(self, x, y, color):
        a, sp = random.uniform(0, math.tau), random.uniform(60, 260)
        self.x, self.y = x, y
        self.vx, self.vy = math.cos(a) * sp, math.sin(a) * sp
        self.life = self.max_life = random.uniform(0.4, 1.0)
        self.size, self.color = random.randint(3, 8), color
    def update(self, dt):
        self.vx *= 0.98 ** (dt * 60); self.vy = self.vy * 0.98 ** (dt * 60) + 300 * dt
        self.x += self.vx * dt; self.y += self.vy * dt
        self.life -= dt
        return self.life > 0
    def draw(self, surf):
        t = self.life / self.max_life
        r = max(1, int(self.size * t))
        surf.blit(glow(r * 3, self.color), (self.x - r * 3, self.y - r * 3),
                  special_flags=pygame.BLEND_RGB_ADD)
# particles = [p for p in particles if p.update(dt)]
```

**Easing / smoothing.**

```python
def lerp(a, b, t): return a + (b - a) * t
def ease_out_cubic(t): return 1 - (1 - t) ** 3
def ease_in_out_sine(t): return -(math.cos(math.pi * t) - 1) / 2
def damp(cur, target, speed, dt): return lerp(cur, target, 1 - math.exp(-speed * dt))  # frame-rate independent
```

**Other effects**

- **Trails / motion blur:** draw to a persistent surface and each frame blit a black surface with `set_alpha(30–60)` over it instead of clearing.
- **Screen shake:** `trauma` value decays over time; offset = `trauma**2 * max_offset * random(-1,1)`; render the world to a surface and blit it at the offset.
- **Hit flash:** fill a white surface, `set_alpha(int(255 * flash))`, decay `flash` quickly.
- **Vignette:** pre-render once (radial dark edges on an SRCALPHA surface) and blit last.
- **Soft shadows:** draw the shape in black at alpha ~80, offset (4, 6), optionally `smoothscale` down then up to blur.
- **Smooth shapes:** use `pygame.draw.aacircle` / `aaline` (pygame-ce) or draw at 2× on an offscreen surface and `smoothscale` down.
- **Pixel art:** render to a small surface (e.g. 320×180) and `pygame.transform.scale` (not smoothscale) to the window; keep integer positions.

**Menus and UI**

- Rounded rects: `pygame.draw.rect(surf, color, rect, border_radius=12)`.
- Buttons store a `hover` value 0→1 that is `damp`-ed toward the target; use it to lerp color, scale and glow.
- Cache rendered text (`font.render` once per string), always antialias, and use `pygame.font.Font(None, size)` or `SysFont` with a fallback so it runs everywhere.
- Fade or slide between screens over 0.2–0.4 s with ease-out.

**Generative art / demos**

- Drive everything from time `t` with sin/cos, Perlin-like noise (sum of sines if no noise library), and HSV palettes via `pygame.Color.hsva`.
- Combine trails + additive glow for the classic "beautiful" look. Add a key to save a screenshot (`pygame.image.save`).

## Performance rules

- Call `.convert()` / `.convert_alpha()` on every loaded or generated surface.
- Never create Surfaces, fonts or text renders inside the per-frame loop unless cached.
- Use delta time for all motion; clamp `dt`.
- Cap particles (e.g. 1500); reuse cached glow sprites.
- Prefer pygame-ce if available (`pip install pygame-ce`); code should still work on classic pygame — avoid ce-only calls or guard them with `hasattr`.

## Output format

- **New:** one-line style choice → one complete code block (single file, no external assets unless provided) → short "Controls" list → 2–3 tweak ideas (constants to change).
- **Improve:** bullet list of visual changes and why → full updated file (or clearly marked replaced functions if the file is large).

## Edge cases

- No assets provided: generate everything procedurally.
- User on low-end machine or web (pygbag): reduce particles, avoid per-pixel loops, keep `async` main loop for pygbag.
- Pixel art requested: disable smoothscale and additive bloom unless asked.
- Existing code uses fixed per-frame movement: convert to dt-based without changing gameplay speed at 60 FPS.