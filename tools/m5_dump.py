import os, sys
os.environ['SDL_VIDEODRIVER'] = 'dummy'; os.environ['SDL_AUDIODRIVER'] = 'dummy'
sys.path.insert(0, 'src')
import io, contextlib
buf = io.StringIO()
with contextlib.redirect_stdout(buf):
    import pygame; pygame.init()
    from core.config import *
    import missions.m5 as m5
    from missions.m5 import maps, meta
print('T', TILE_SIZE)
for n in ('MISSION5_HQ_MAP', 'MISSION5_QUARTER_MAP', 'MISSION5_PRINT_MAP'):
    g = getattr(maps, n); print(n, len(g[0]), len(g))
    print('   ' + ''.join(str(i % 10) for i in range(len(g[0]))))
    for i, r in enumerate(g):
        print('%2d ' % i + r)
print(meta.QUARTER_GUARDS)
print(meta.HQ_NPCS)
