# Subsystem: `engine.settings` (Phase 9, ADR-020)

Typed, layered settings: `defaults < file < env (ACARISTAN_*) < CLI`,
resolved per field with a typed schema.

```
engine.settings
  model.py           Field + BOOL/INT/FLOAT/STR/ENUM types, coerce, resolve, env_layer
  (facade)           Settings - the resolved, observable value set
src/core/settings_store.py + user_settings.py
                     the legacy flat-JSON store, kept as a client of this kernel
                     (file format and API unchanged)
```

Semantics that matter: an invalid higher-layer value falls back to
the field default, *not* to the lower layer's value; INT rejects
bools. Resolution emits `SettingsChanged` on the event bus, and the
accessibility consumers subscribe live — flash reduction (caps the
mid17 breach white-out via `m5fx3d.cap_flash` + per-source caps),
shake scale (applies to cutscene handheld too), text speed, and —
through `engine.input` — gamepad/rebinding.
