# A-001 star-import narrowing (Phase 4, 2026-10-15)

`from core.config import *` is gone from the tree: **51 sites in 51 files** rewritten to
explicit imports by `tools/ae_narrow_star.py`. Parity-neutral by construction - the same
names, bound to the same objects, in the same place; nothing about the game changed.
Backups of every touched file live in `build/ae_narrow_star/backup/`.

## Why this needed per-batch gates

The first two analysis passes were unsound (BUGS B-019):

1. **Scope bug** - names bound *anywhere* in a file were subtracted from what the file
   needs from the star, so a function-local `screen` hid a module-global use.
   Caught by golden after batch 2: the M2 cuts died with `NameError: WIDTH` / `screen`
   (10 shots). The corrected pass also pre-cleared `grain_frame, grain_idx, screen`
   in `app.py` (the menu would have crashed) and 5 names in `m2/draw.py`.
2. **Conditional-export bug** - `exported_names` only saw top-level statements, so
   `core.config`'s `bg_image = ...` (inside an `if`/`else`) could never be listed.
   Caught by the loop probe after batch 3: the boot segment died with
   `NameError: bg_image` at `ui/main.py:18`.

Fix: both passes are now `symtable`-based (`global_names`, `exported_names` in
`tools/ae_star_imports.py`). All 51 files were restored from backup and re-narrowed
from the corrected plans; the plan diffs are in `plan_diffs.txt`.

## Gates

- Per batch: `compileall` + golden verify + replay check; batch 3 added the loop probe.
- Final: golden **373/373**, replay **5/5**, loop **7/7**, full `AE CI: OK`.
- New permanent CI rows (`tools/ae_ci.py`):
  - `import hygiene` - `tools/ae_narrow_star.py --verify` = 0 star sites left;
  - `global names` - `tools/ae_global_names.py`, a new independent verifier: every
    global a file reads must be bound in it, imported, star-provided or a builtin -
    **0 unresolved globals** in 265 files (package facades skipped: relative stars
    cannot be resolved statically; `src/cutscenes/m3cell_balaceanu_patch.py` is a
    known non-module - an applied patch fragment, skipped by name and printed).
- `tools/ae_reexport_check.py` (new): who pulls a star name *through* another module -
  1 real risk found and fixed at the source before the rewrite (`m3/sweep.py` imported
  `C_VASILE` via `m3/meta.py`'s star; it now imports from `core.config`).

## Files here

- `plan_diffs.txt` - old plans vs corrected plans (the exact names the bugs dropped).
- `caught_by_gates.txt` - the failing golden/loop outputs that caught each bug.
- `final_checks.txt` - tool outputs + suite results + CI summary after the final apply.
