"""Static layers of the Mission 5 "[E] look" first-person shots (canvas
CW x CH = 1.3x screen). One variant per shot, in KEYS order. The painters
are the existing pygame-only set painters in missions.m5.inspect_art /
inspect_art_street (all English text); this module freezes them into baked
PNGs so inspect_fpv blits instead of repainting ~80 draw calls per shot.
Per-frame motion (CRT flicker, smoke, sway) stays live in the *_dyn painters."""
import pygame

KEYS = ("notice", "hq_tv", "portrait", "paint", "shop_tv", "tram")
VARIANTS = len(KEYS)
# The painters live in missions.m5 (gameplay-owned); name them so ae_bake hashes their source too.
BAKE_DEPS = ("missions.m5.inspect_art", "missions.m5.inspect_art_street")


def _painter(key):
    from missions.m5 import inspect_art as a
    from missions.m5 import inspect_art_street as st
    return {"notice": a.notice_static, "hq_tv": a.tv_static, "portrait": a.portrait_static,
            "paint": st.paint_static, "shop_tv": st.shop_static, "tram": st.tram_static}[key]


def render(variant=0, scale=1):
    from game.art.m5 import _kit as K
    from missions.m5 import inspect_art as a
    key = KEYS[int(variant) % VARIANTS]
    s = pygame.Surface((a.CW, a.CH))
    _painter(key)(s)
    out = pygame.Surface((a.CW, a.CH), pygame.SRCALPHA)
    out.blit(s, (0, 0))
    return K.scaled(out, scale)
