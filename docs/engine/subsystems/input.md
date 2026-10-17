# Subsystem: `engine.input` (Phase 9, ADR-020)

Action mapping: `ActionMap` binds semantic actions (move, advance,
interact, …) to keys/buttons, with `DEFAULT_ACTIONS` the identity
mapping the game shipped with for a decade.

```
engine.input
  model.py           ActionMap, DEFAULT_ACTIONS, validate
src/game/input_adapter.py
                     applies the map at the one pressed-state snapshot in app.py:
                     remapping/rebinding/gamepad rewrite that snapshot, so every
                     call site keeps reading keys exactly as before
```

Identity by default is the parity guarantee: with no user bindings,
the snapshot is bit-identical to raw `pygame.key.get_pressed()`, which
is why the golden/loop/replay oracles never noticed the kernel
arrive. Rebinding UI lives game-side; the kernel only validates and
resolves maps.
