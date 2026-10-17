# Subsystem: `engine.save` (Phase 9, ADR-020)

World snapshots: `ae.save/1` serialised state + a comparable hash.

```
engine.save
  snapshot.py        canonical dumps/loads (deep-copy in and out; $tuple/$set tags),
                     from_dict validates and raises; validate() returns the error list
  statehash.py       statehash() with QUANTUM = 1e-4 float quantisation - hashes
                     compare across machines, raw floats do not
src/game/save_adapter.py
                     captures at M5 checkpoints alongside the legacy save; the legacy
                     respawn flow stays authoritative (dead entities skipped on restore,
                     uncleanable values void only their own dict, restored component-first)
```

Proof obligation: `tools/ae_replay_check.py` (D8) replays one input
segment per mission from a restored snapshot and demands an identical
`statehash`. Compare `getstate()`-style hashes, never monkeypatched
RNG internals; warm up lazy first-frame initialisation before capture
or the streams appear offset.
