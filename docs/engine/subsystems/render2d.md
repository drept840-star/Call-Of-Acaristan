# Subsystem: `engine.render2d` (Phases 2–3)

The 2D frame pipeline: missions submit drawables to a queue; the
queue sorts by layer (and y within Y_SORTED layers) and replays them.

```
engine.render2d
  queue.py           RenderQueue + RenderStats (draw counts per layer; devtools F3 reads these)
  drawables.py       Drawable + Rect/Ellipse/Arc/Line/Poly/Circle/Fill/Sprite/RotatedSprite/
                     Text/Surface/SurfaceBatch/Custom/Overlay/UiPass/StaticLayer drawables
  camera.py          Camera2D: clamp_top_left, deadzone_hold, ease_toward, legacy_shake
  pen.py             Pen protocol: SurfacePen (real) / RecordingPen (tests); pen_or_surface
  static.py          StaticLayer(s) - pre-rendered static geometry (bake + draw as one drawable)
  postfx.py          PostFX chain hooks
  util.py            soft shadows, lamp push, radial helpers, screen swap helpers
```

Layer order is fixed by `Layer`/`LAYER_NAMES` (WORLD < Y_SORTED <
SCREEN passes). Parity rules: drawables consume RNG at submit time,
never at draw; `CustomDraw` wraps the legacy mission painters (M1–M4
draw as one CustomDraw each); shake stays `int(round(...))` because
`randint` bounds are part of the oracle streams.
