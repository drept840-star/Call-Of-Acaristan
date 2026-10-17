# Subsystem: `engine.lighting` (Phase 3)

Light compositing for the 2D pipeline: an offscreen light buffer is
multiplied over the world pass.

```
engine.lighting
  buffer.py          LightBuffer + bloom_sprite/falloff_sprite sprite factories,
                     enabled()/frozen() switches (oracle harnesses freeze it)
  lightmap.py        LightMap + LightMapDraw - baked static lightmaps submitted
                     to the render queue like any drawable
```

Missions declare lights in level data (`lights` layer entries) and
dynamic sources at submit time; the kernel owns falloff shapes and
the composite. Because lighting multiplies final pixels, any change
here is a golden-visible change — the 373-frame set is the review.
