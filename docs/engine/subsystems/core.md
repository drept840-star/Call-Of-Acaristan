# Subsystem: `engine.core` (Phases 1–2, 9)

The foundation kernel: process boot, deterministic time, events,
seeded randomness, service location, logging, profiling.

```
engine.core          facade (E4: game code imports this, never the submodules)
  app.py             App - fixed-step loop shell (the game still drives its own loop in app.py)
  clock.py           Clock - wall/sim timebase; now_ms/now_s; pin_wall/unpin_wall for harnesses
  timebase.py        DEFAULT_HZ / DEFAULT_MAX_STEPS fixed-step policy
  events.py          EventBus + Subscription (SettingsChanged etc. ride this)
  rng.py             RngStreams - named seeded streams; derive_seed; LEGACY_RNG marker
  services.py        Services registry + ServiceMissing (explicit DI, no globals)
  settings.py        the core.Settings schema object settings/ builds on
  errors.py          AEError / AssetError / SchemaError / TimelineError hierarchy
  log.py             Log + get_log + write_crash_report
  profiling.py       Profiler (frame samples; game/devtools.py is the in-game face)
  mathx.py           clamp/lerp/inv_lerp/smoothstep/easings/lerp_angle
  config.py          DEFAULTS / ENV_MAP / LEGACY constants
```

Rules that bite: RNG draws must come from a named stream (draw-time
consumption only — never inside a drawable's draw); harnesses pin the
wall clock (`pin_wall`) or replay comparisons drift; no import-time
side effects anywhere in the kernel.
