"""Record a bot-played Mission 4 gameplay video (2.5D) to MP4.

    python tools/m4_gameplay_video.py [OUT.mp4]

Visual-review tool, not a CI gate. A scripted Biribel plays the overhaul:
the street escort, the fortify prep (barricades, the Maru meet, the jammer)
and three siege beats (wave 1, the wave 4 breach, the wave 5 APC). The sim
runs at 60 ticks per second on a pinned clock; every second tick goes to an
ffmpeg rawvideo pipe, so the clip plays in real time at 30 fps. The bot is
kept alive (health top-ups) so the run never stalls on a death screen.
"""
import math
import os
import shutil
import subprocess
import sys
import tempfile

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))
os.chdir(ROOT)

import pygame  # noqa: E402

pygame.init()

_SCRATCH = tempfile.mkdtemp(prefix="m4video_")
from core import save_system as _sv  # noqa: E402
from core import settings_store as _st  # noqa: E402
_sv.SAVE_FILE = os.path.join(_SCRATCH, "save_data.json")
_st.SAVE_FILE = os.path.join(_SCRATCH, "settings.json")

from core import config as _cfg  # noqa: E402
from core.state import STATE  # noqa: E402
from engine.core import timebase  # noqa: E402
from game import topdown3d  # noqa: E402

FPS_SIM = 60
FPS_OUT = 30
T = _cfg.TILE_SIZE
W, H = _cfg.WIDTH, _cfg.HEIGHT

CLOCK = [0]
timebase.pin_wall(ms=lambda: CLOCK[0] * 1000 // FPS_SIM, s=lambda: CLOCK[0] / float(FPS_SIM))
pygame.time.get_ticks = lambda: CLOCK[0] * 1000 // FPS_SIM

AIM = [0.0, 0.0]
topdown3d.mouse_world = lambda h=0.0: (AIM[0], AIM[1])


class Keys:
    def __init__(self):
        self.down = set()

    def __getitem__(self, k):
        return k in self.down


KEYS = Keys()


def _ffmpeg():
    for cand in (os.environ.get("FFMPEG"), shutil.which("ffmpeg"), "C:/ffmpeg/bin/ffmpeg.exe"):
        if cand and os.path.exists(cand):
            return cand
    import imageio_ffmpeg
    return imageio_ffmpeg.get_ffmpeg_exe()


class Recorder:
    def __init__(self, out):
        self.frames = 0
        self.caption = None
        self.proc = subprocess.Popen(
            [_ffmpeg(), "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", "%dx%d" % (W, H),
             "-r", str(FPS_OUT), "-i", "-", "-an", "-c:v", "libx264", "-pix_fmt", "yuv420p",
             "-crf", "17", "-preset", "medium", "-movflags", "+faststart", out],
            stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        from ui import pixfont
        self.big = pixfont.font("R7", 4, bold=True)
        self.small = pixfont.font("R7", 2)

    def set_caption(self, title, sub, frames=210):
        self.caption = [title, sub, frames, frames]

    def _draw_caption(self, surf):
        if not self.caption:
            return
        title, sub, left, total = self.caption
        age = total - left
        a = min(1.0, age / 12.0, left / 18.0)
        tw = max(self.big.size(title)[0], self.small.size(sub)[0]) + 48
        x0, y0 = (W - tw) // 2, 170
        box = pygame.Surface((tw, 82), pygame.SRCALPHA)
        box.fill((8, 10, 14, int(190 * a)))
        pygame.draw.rect(box, (196, 160, 70, int(255 * a)), (0, 78, tw, 4))
        surf.blit(box, (x0, y0))
        for f, text, dy, col in ((self.big, title, 12, (236, 222, 190)),
                                 (self.small, sub, 56, (170, 176, 186))):
            img = f.render(text, color=col)
            img.set_alpha(int(255 * a))
            surf.blit(img, ((W - img.get_width()) // 2, y0 + dy))
        self.caption[2] -= 1
        if self.caption[2] <= 0:
            self.caption = None

    def feed(self):
        self._draw_caption(_cfg.screen)
        self.proc.stdin.write(pygame.image.tobytes(_cfg.screen, "RGB"))
        self.frames += 1

    def card(self, title, sub, frames=60):
        """Black title card between beats."""
        for i in range(frames):
            _cfg.screen.fill((6, 7, 10))
            a = min(1.0, i / 10.0, (frames - i) / 10.0)
            for f, text, y, col in ((self.big, title, H // 2 - 40, (236, 222, 190)),
                                    (self.small, sub, H // 2 + 16, (170, 176, 186))):
                img = f.render(text, color=col)
                img.set_alpha(int(255 * a))
                _cfg.screen.blit(img, ((W - img.get_width()) // 2, y))
            self.proc.stdin.write(pygame.image.tobytes(_cfg.screen, "RGB"))
            self.frames += 1

    def close(self):
        self.proc.stdin.close()
        self.proc.wait()


# ─────────────────────────────────────────────
# Bot
# ─────────────────────────────────────────────
class Bot:
    def __init__(self, m4, rec):
        self.m4 = m4
        self.rec = rec
        self.path = []
        self.goal = None
        self.stuck = 0
        self.last = None
        self.cam = None
        self.target = None
        self.retarget = 0

    # movement
    def go(self, tile):
        from missions.m4 import world
        if tile != self.goal or not self.path:
            px, py = STATE.player.rect.center
            self.path = world._ally_find_path(px, py, tile, world._solid_walls()) or [world._tile_world(*tile)]
            self.goal = tile
            self.stuck = 0

    def arrived(self, tile, tol=10):
        from missions.m4 import world
        gx, gy = world._tile_world(*tile)
        px, py = STATE.player.rect.center
        return math.hypot(gx - px, gy - py) <= tol

    def _steer(self):
        for k in (pygame.K_w, pygame.K_a, pygame.K_s, pygame.K_d):
            KEYS.down.discard(k)
        if not self.path:
            return
        px, py = STATE.player.rect.center
        wx, wy = self.path[0]
        dx, dy = wx - px, wy - py
        if math.hypot(dx, dy) < 6:
            self.path.pop(0)
            if not self.path:
                return
            wx, wy = self.path[0]
            dx, dy = wx - px, wy - py
        if dx > 3:
            KEYS.down.add(pygame.K_d)
        elif dx < -3:
            KEYS.down.add(pygame.K_a)
        if dy > 3:
            KEYS.down.add(pygame.K_s)
        elif dy < -3:
            KEYS.down.add(pygame.K_w)
        if self.last == (px, py):
            self.stuck += 1
            if self.stuck > 40 and self.goal:
                g, self.goal = self.goal, None
                self.go(g)
        else:
            self.stuck = 0
        self.last = (px, py)

    def stop(self):
        self.path = []
        self.goal = None

    # combat
    def _visible(self, rng):
        from missions.m4 import world
        px, py = STATE.player.rect.center
        sw = world._shot_walls()
        out = []
        for e in STATE.enemies:
            if e.hp <= 0:
                continue
            ex, ey = e.rect.center
            d = math.hypot(ex - px, ey - py)
            if d > rng or any(w.clipline(px, py, ex, ey) for w in sw):
                continue
            out.append((d, e))
        out.sort(key=lambda t: t[0])
        return [e for _d, e in out]

    def _combat(self, look):
        from entities import weapons
        px, py = STATE.player.rect.center
        self.retarget -= 1
        if self.retarget <= 0 or self.target is None or self.target.hp <= 0:
            vis = self._visible(560)
            self.target = vis[0] if vis else None
            self.retarget = 12
        if self.target is not None:
            ex, ey = self.target.rect.center
            # ease the aim onto the target so the turn reads on screen
            AIM[0] += (ex - AIM[0]) * 0.35
            AIM[1] += (ey - AIM[1]) * 0.35
            if math.hypot(AIM[0] - ex, AIM[1] - ey) < 40 and CLOCK[0] % 7 == 0:
                weapons.handle_shoot()
                mag = "k9_ammo_in_mag" if STATE.current_weapon == "k9_smg" else "ammo_in_mag"
                if getattr(STATE, mag, 1) <= 0 and not getattr(STATE, "reloading", False):
                    weapons.start_reload()
        else:
            if look is None and self.path:
                look = self.path[min(2, len(self.path) - 1)]
            if look is not None:
                lx, ly = look
                AIM[0] += (lx - AIM[0]) * 0.12
                AIM[1] += (ly - AIM[1]) * 0.12

    # one sim tick
    def tick(self, look=None, shoot=True, record=True):
        p = STATE.player
        if p.hp < p.max_hp * 0.45:
            p.hp = p.max_hp
        STATE.player_dead = False
        STATE.request_death_screen = False
        for k in ("k9_spare_mags", "spare_mags"):
            if getattr(STATE, k, 0) < 2:
                setattr(STATE, k, 3)
        STATE.m4_fail_reason = None
        STATE.m4_fail_timer = 0
        from missions.m4 import escort
        v = escort.vasile()
        if v and not v.get("dead"):
            if v.get("downed", 0) > 0:
                v["downed"] = 0
            v["hp"] = max(v["hp"], v["max_hp"] // 2)
        self._steer()
        if shoot:
            self._combat(look)
        elif look is not None:
            AIM[0] += (look[0] - AIM[0]) * 0.15
            AIM[1] += (look[1] - AIM[1]) * 0.15
        STATE.dt = 1.0 / FPS_SIM
        from core import interactions
        interactions.pump_radio("GAME", False)
        cam = self.m4.game_update(KEYS)
        if cam is not None:
            self.cam = cam
        CLOCK[0] += 1
        if record and CLOCK[0] % (FPS_SIM // FPS_OUT) == 0 and self.cam is not None:
            self.m4.game_draw(*self.cam)
            self.rec.feed()
        pygame.event.pump()

    def walk(self, tile, limit=1800, **kw):
        tol = kw.pop("tol", 10)
        self.go(tile)
        for _ in range(limit):
            if self.arrived(tile, tol):
                break
            if not self.path:
                self.go(tile)
            self.tick(**kw)
        self.stop()

    def idle(self, n, **kw):
        self.stop()
        for _ in range(n):
            self.tick(**kw)


# ─────────────────────────────────────────────
# Beats
# ─────────────────────────────────────────────
def beat_escort(bot):
    m4 = bot.m4
    from missions.m4 import escort, world
    from missions.m4.meta import PLAYER_START_TILE
    m4.start_m4(preserve_timer=True)
    STATE.active_mission = "MISSION4"
    STATE.player.rect.center = world._tile_world(*PLAYER_START_TILE)
    AIM[0], AIM[1] = STATE.player.rect.centerx + 200, STATE.player.rect.centery
    bot.rec.card("MISSION 4 - THE AFTERMATH", "2.5D overhaul - bot playthrough", 75)
    bot.rec.set_caption("ESCORT", "Get Vasile and the cache across the street")
    dx, dy = world._street_door_pos()
    door = (int(dx) // T, int(dy) // T)
    budget = 60 * 75
    bot.go(door)
    while budget > 0 and STATE.mission4_stage == m4.STAGE_ESCORT:
        budget -= 1
        v = escort.vasile()
        px, py = STATE.player.rect.center
        far = v and math.hypot(v["x"] - px, v["y"] - py) > 230
        if far:
            bot.stop()
            bot.tick(look=(v["x"], v["y"]))
            continue
        if not bot.path:
            bot.go(door)
        bot.tick()
    print("escort done, stage", STATE.mission4_stage, "frames", bot.rec.frames)
    if STATE.mission4_stage == m4.STAGE_ESCORT:
        v = escort.vasile()
        v["x"], v["y"] = dx - 20, dy
        STATE.player.rect.center = (dx, dy)
        bot.tick()


def beat_fortify(bot):
    m4 = bot.m4
    from missions.m4 import world, fortify
    from missions.m4.meta import LIAISON_TILE, JAMMER_TILE
    bot.rec.set_caption("FORTIFY", "Barricade the station: hold E at doors and windows")
    STATE.m4_supply = max(getattr(STATE, "m4_supply", 0), 24)
    px, py = STATE.player.rect.center
    sites = sorted(STATE.m4_sites, key=lambda s: math.hypot(s[0] * T - px, s[1] * T - py))[:4]
    for c, r, kind in sites:
        bot.walk((c, r), limit=900)
        sx, sy = fortify.site_center(c, r)
        for hold in range(2 if kind == "door" else 1):
            KEYS.down.add(pygame.K_e)
            for _ in range(80):
                bot.tick(look=(sx, sy), shoot=False)
            KEYS.down.discard(pygame.K_e)
            bot.idle(8, look=(sx, sy), shoot=False)
    bot.walk(LIAISON_TILE, limit=900, shoot=False)
    bot.rec.set_caption("THE MEET", "Maru, the liaison, and the radio station's offer", 180)
    for _ in range(30):
        bot.tick(shoot=False)
        if STATE.m4_dialogue_active:
            break
    enter = pygame.event.Event(pygame.KEYDOWN, key=pygame.K_RETURN)
    n = 0
    while STATE.m4_dialogue_active and n < 4000:
        if n % 75 == 74:
            m4.handle_dialogue_event(enter)
        bot.tick(shoot=False, record=(n < 900 or n % 6 == 0))
        n += 1
    print("meet done", STATE.m4_dialogue_done, "frames", bot.rec.frames)
    jx, jy = world._jammer_pos()
    bot.walk(JAMMER_TILE, limit=1200, shoot=False, tol=30)
    bot.rec.set_caption("THE JAMMER", "Plant it on the rack - loyalist comms go dark")
    bot.idle(20, look=(jx, jy - 40), shoot=False)
    m4.handle_interact()
    for _ in range(60 * 12):
        bot.tick(look=(jx, jy + 300), shoot=False)
        if STATE.mission4_stage == m4.STAGE_SIEGE and STATE.m4_siege_t >= 0:
            break
    print("siege armed, stage", STATE.mission4_stage, "t", STATE.m4_siege_t)


def _clear_enemies():
    from missions.m4 import siege
    dead = set(id(e) for e in siege.alive())
    STATE.enemies = [e for e in STATE.enemies if id(e) not in dead]


def _hold_point(bot, spot, frames, leash=7):
    """Fight around a spot: shoot what is in sight, otherwise close on the
    nearest loyalist (never more than `leash` tiles from the spot), otherwise
    walk back to the spot."""
    from missions.m4 import siege
    sx, sy = bot.m4._tile_world(*spot)
    for i in range(frames):
        if bot._visible(420):
            bot.stop()
        elif i % 30 == 0:
            px, py = STATE.player.rect.center
            near = [e for e in siege.alive()
                    if math.hypot(e.rect.centerx - sx, e.rect.centery - sy) < leash * T]
            if near:
                e = min(near, key=lambda e: math.hypot(e.rect.centerx - px, e.rect.centery - py))
                bot.go((e.rect.centerx // T, e.rect.centery // T))
            elif not bot.arrived(spot, 40):
                bot.go(spot)
            else:
                bot.stop()
        bot.tick()


def beat_siege(bot):
    m4 = bot.m4
    from missions.m4 import siege, fortify
    bot.rec.set_caption("SIEGE - WAVE 1", "Hold the transmitter until the broadcast is out")
    _hold_point(bot, (17, 16), 60 * 30, leash=9)

    _clear_enemies()
    for c, r, kind in STATE.m4_sites:
        fortify._place((c, r), "plate" if kind == "door" else "boards")
    STATE.m4_siege_t = siege.WAVES[3]["start"] + 900 - 150
    bot.rec.card("WAVE 4", "They bring charges", 50)
    bot.rec.set_caption("SIEGE - WAVE 4", "The weak wall goes up")
    STATE.player.rect.center = bot.m4._tile_world(25, 11)
    bot.idle(150, look=bot.m4._tile_world(29, 11))
    _hold_point(bot, (25, 11), 60 * 24)

    _clear_enemies()
    for c, r, kind in STATE.m4_sites:
        fortify._place((c, r), "plate" if kind == "door" else "boards")
    STATE.m4_siege_t = siege.WAVES[4]["start"] + 300 - 90
    bot.rec.card("WAVE 5", "The armour arrives", 50)
    bot.rec.set_caption("SIEGE - WAVE 5", "The APC rams the main door")
    # the APC drives in on row 26 and hits the main door ~500 ticks after the
    # jump; watch it from the forecourt's west edge, then fall back inside
    STATE.player.rect.center = bot.m4._tile_world(13, 23)
    bot.idle(620, look=bot.m4._tile_world(18, 25))
    bot.walk((17, 19), limit=300)
    _hold_point(bot, (17, 19), 60 * 18, leash=5)
    print("siege beat done, wave", STATE.m4_wave, "t", STATE.m4_siege_t)


def main():
    out = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, "trailers", "m4_overhaul", "m4_gameplay.mp4")
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    from missions import m4
    rec = Recorder(out)
    bot = Bot(m4, rec)
    try:
        beat_escort(bot)
        beat_fortify(bot)
        beat_siege(bot)
        rec.card("CALL OF ACARISTAN", "Mission 4 - The Aftermath", 75)
    finally:
        rec.close()
        timebase.unpin_wall()
    print("wrote %s (%d frames, %.1f s)" % (out, rec.frames, rec.frames / float(FPS_OUT)))


if __name__ == "__main__":
    main()
