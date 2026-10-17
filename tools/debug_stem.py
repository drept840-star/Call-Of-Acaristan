#!/usr/bin/env python3
"""Standalone timing run of mp_trailer_assemble.render_foley_stem."""
import sys, time, importlib
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
t0 = time.time()

import mp_trailer_assemble as A
print(f"import assembler: {time.time()-t0:.2f}s")

# instrument: wrap FS functions after import inside render_foley_stem by
# monkey-patching time around asset reads — simpler: just call and watch
from pathlib import Path
import tempfile

work = Path(tempfile.mkdtemp(prefix="stem_dbg_"))

# patch: add prints inside the function via profile of key suspects
import cProfile, pstats, io

t1 = time.time()
pr = cProfile.Profile()
pr.enable()
out = A.render_foley_stem(work)
pr.disable()
print(f"render_foley_stem: {time.time()-t1:.2f}s -> {out}")

s = io.StringIO()
ps = pstats.Stats(pr, stream=s).sort_stats("cumulative")
ps.print_stats(18)
print(s.getvalue())

