"""Mission 8 Duty - Phase 6: The Ridge (first-person scope finale).

Biribel lies on the frozen ridge above the evacuation pad: Retardovici's
downed helicopter, a few Guards, a rescue bird on its way in.

1. Ucilev steps in front of the President; he has to go first.  One round,
   slow motion: he drops to his knees and gets his line.
2. Retardovici takes a Guard radio, on Biribel's channel, crouched behind the
   wreck: four lines.  Then he stands.  The game waits for the shot.
3. The shot, slow motion, scope recoil.  The scene hands off to the epilogue.

Scope: mouse aims, wheel / RMB cycles zoom, hold SHIFT to hold breath
(limited, then the sway comes back worse), wind and drop are real.  If the
rescue bird lands and lifts with him, the ridge restarts.
"""
import math
import random

import pygame

from core.config import HEIGHT, WIDTH, audio, draw_vignette, font_terminal, font_terminal_small
from core.state import STATE
from cutscenes import m6fx3d as _fx
from cutscenes import m6world3d as _w
from engine3d import POSES, blend, clamp
from missions.m6 import hud3d as H
from missions.m7 import raid3d as R
from missions.m7 import raid_brain as RB
from missions.m7 import raid_hud as RH
from missions.m8.revenge import chase_set as CS

PAD = (CS.road_x(2300.0) + 70.0, 0.0, 2300.0)
EYE = (PAD[0] - 95.0, 30.0, PAD[2] - 60.0)
ZOOMS = (16.0, 7.0, 3.6)
MUZZLE_V = 820.0
G = 9.81
BOLT_S = 1.3
BREATH_S = 4.0
RESCUE_S = 48.0
SLOWMO = 0.25
LINE_S = 3.8
RADIO_LINES = (
    "You know what he did on Route 12. You don't know what he did tonight.",
    "Who told you the mansion's weak points? Who turned off my cameras?",
    "Who do you think gave me to you?",
    "Tomorrow he sits in my chair. And you put him there.",
)
UCILEV_LINE = "Now you know what it's like to follow orders."


def _off(dx, dz):
    return (PAD[0] + dx, 0.0, PAD[2] + dz)


def _yaw_to(a, b):
    return R._yaw(b[0] - a[0], b[2] - a[2])


PRES_AT = _off(2.6, -1.0)
_U_DIR = (EYE[0] - PRES_AT[0], EYE[2] - PRES_AT[2])
_U_LEN = math.hypot(*_U_DIR)
UCILEV_AT = (PRES_AT[0] + _U_DIR[0] / _U_LEN * 1.1, 0.0, PRES_AT[2] + _U_DIR[1] / _U_LEN * 1.1)
GUARDS = (_off(-4.0, 3.0), _off(6.5, 2.0), _off(1.0, 6.5))
RESCUE_FROM = _off(160.0, 260.0)
RESCUE_PAD = _off(9.0, 9.0)


class RidgeScene:
    set_paused = R.RaidScene.set_paused
    _grab = R.RaidScene._grab
    _snd = R.RaidScene._snd
    say = R.RaidScene.say

    def __init__(self):
        self._active = False
        self.paused = False
        self.done = False
        self.result = None
        self.audio = None
        self.t = 0.0
        self._setup()

    def begin(self):
        self.t = 0.0
        self.done = False
        self.result = None
        self._active = True
        self.paused = False
        STATE.m8_ridge_active = True
        try:
            from .. import m8_audio as _m8_audio
            self.audio = _m8_audio.instance(audio)
            self.audio.warm()
        except Exception:
            self.audio = None
        self._setup()
        self._grab(True)

    def active(self):
        return self._active

    def finish(self, result="win"):
        if self.done:
            return False
        self.done = True
        self.result = result
        self._active = False
        STATE.m8_ridge_active = False
        self._grab(False)
        if self.audio is not None:
            try:
                self.audio.stop_loops()
            except Exception:
                pass
        from .. import flow as _flow
        return _flow.on_ridge_done(result)

    def _setup(self):
        self.rng = random.Random()
        self.yaw = _yaw_to(EYE, PRES_AT) - 6.0
        self.pitch = math.degrees(math.atan2(-(EYE[1] - 1.2), math.hypot(PRES_AT[0] - EYE[0],
                                                                          PRES_AT[2] - EYE[2]))) + 2.0
        self.zoom_i = 1
        self.breath = BREATH_S
        self.holding = False
        self.winded = 0.0
        self.last_shot = -9.0
        self.kick = 0.0
        self.phase = "ucilev"
        self.phase_start = 0.0
        self.u_down_t = 0.0
        self.phase_t = 0.0
        self.line_i = 0
        self.rescue = RESCUE_S
        self.fail_t = -1.0
        self.wind = self.rng.choice((-1.0, 1.0)) * self.rng.uniform(2.0, 5.5)
        self.guards = [dict(x=g[0], y=0.0, z=g[2], alive=True, dead_t=-9.0, yaw=_yaw_to(g, EYE))
                       for g in GUARDS]
        self.lines = []
        self.impacts = []
        self.hit_mark = -9.0
        self.slow_until = -1.0
        self.say("", "Ucilev steps in front of the President. He knows where you are. He doesn't hide.", 4.0)

    # --- the world -------------------------------------------------------------

    def fov(self):
        return ZOOMS[self.zoom_i]

    def sway(self):
        """Scope drift in degrees (yaw, pitch); breath-hold steadies it."""
        amp = (0.10 + 0.05 * self.zoom_i) * (0.15 if self.holding else 1.0) * (1.0 + 1.6 * self.winded)
        t = self.t
        return (amp * (math.sin(t * 0.9) + 0.5 * math.sin(t * 2.3 + 1.0)),
                amp * 0.8 * (math.sin(t * 1.3 + 2.0) + 0.4 * math.sin(t * 3.1)))

    def view_dir(self):
        sy, sp = self.sway()
        return R._fwd(self.yaw + sy, self.pitch + sp + self.kick)

    def rescue_pos(self):
        k = clamp(1.0 - self.rescue / RESCUE_S, 0.0, 1.0)
        e = R._ease(k)
        p = tuple(RESCUE_FROM[i] + (RESCUE_PAD[i] - RESCUE_FROM[i]) * e for i in range(3))
        alt = 60.0 * (1.0 - e) ** 1.4
        if self.fail_t >= 0.0:
            alt = (self.t - self.fail_t) * 4.0
        return (p[0], p[1] + alt, p[2])

    def pres_pose(self):
        if self.phase == "pres_down":
            k = clamp((self.t - self.phase_start) / 1.4, 0.0, 1.0)
            return blend("stand", "dead_back", k)
        if self.phase in ("ucilev", "u_down", "radio"):
            return dict(POSES["kneel"], rsh_p=110.0, rel=95.0)        # crouched, radio up
        return dict(POSES["stand"], rsh_p=110.0, rel=95.0)

    def ucilev_pose(self):
        if self.phase == "ucilev":
            return dict(POSES["stand"], lsh_r=22.0, rsh_r=22.0)         # arms out, covering
        k = clamp((self.t - self.u_down_t) / 1.2, 0.0, 1.0)
        if self.phase in ("u_down",):
            return blend("stand", "kneel", k)
        k2 = clamp((self.t - self.u_down_t - 5.0) / 1.0, 0.0, 1.0)
        return blend("kneel", "dead_front", k2)

    def targets(self):
        """(name, centre, radius, is_head) the round can hit."""
        out = []
        if self.phase == "ucilev":
            u = UCILEV_AT
            out += [("ucilev", (u[0], 1.62, u[2]), 0.16, True), ("ucilev", (u[0], 1.15, u[2]), 0.36, False)]
        if self.phase == "wait":
            p = PRES_AT
            out += [("pres", (p[0], 1.6, p[2]), 0.16, True), ("pres", (p[0], 1.12, p[2]), 0.36, False)]
        for i, g in enumerate(self.guards):
            if g["alive"]:
                out += [("g%d" % i, (g["x"], 1.6, g["z"]), 0.16, True), ("g%d" % i, (g["x"], 1.12, g["z"]), 0.36, False)]
        return out

    # --- update ----------------------------------------------------------------

    def _set_phase(self, name):
        self.phase = name
        self.phase_start = self.t
        self.phase_t = 0.0

    def update(self, keys=None):
        if not self._active or self.paused:
            return
        raw = clamp(float(getattr(STATE, "dt", 1.0 / 60.0)), 0.0, 0.05)
        dt = raw * (SLOWMO if self.t < self.slow_until else 1.0)
        self.t += dt
        self.phase_t += dt
        self._snd("bed", "ridge")
        self._snd("update", raw)
        k = keys if keys is not None else pygame.key.get_pressed()
        try:
            want = bool(k[pygame.K_LSHIFT] or k[pygame.K_RSHIFT])
        except Exception:
            want = False
        self.holding = want and self.breath > 0.0 and self.winded <= 0.0
        if self.holding:
            self.breath = max(0.0, self.breath - raw)
            if self.breath <= 0.0:
                self.winded = 3.0
        else:
            self.winded = max(0.0, self.winded - raw)
            self.breath = min(BREATH_S, self.breath + raw * 0.8)
        self.kick = max(0.0, self.kick - raw * 6.0)
        if self.fail_t >= 0.0:
            if self.t - self.fail_t > 4.0:
                self._setup()
            return
        if self.phase in ("ucilev", "wait"):
            self.rescue -= raw
            if self.rescue <= 0.0:
                self.fail_t = self.t
                self.say("", "The rescue bird is down and up again - with him aboard.", 3.6)
                return
        if self.phase == "u_down":
            if self.phase_t > 1.3 and self.line_i == 0:
                self.line_i = 1
                self.say("UCILEV", UCILEV_LINE, 3.4)
            if self.t >= self.slow_until and self.phase_t > 2.0:
                self._set_phase("radio")
                self.line_i = 0
        elif self.phase == "radio":
            n = int(self.phase_t / LINE_S)
            while self.line_i <= n and self.line_i < len(RADIO_LINES):
                self.say("RETARDOVICI", RADIO_LINES[self.line_i], LINE_S)
                self._snd("pa_squelch")
                self.line_i += 1
            if self.phase_t >= LINE_S * len(RADIO_LINES):
                self._set_phase("wait")
                self.say("", "He stands up.", 2.4)
        elif self.phase == "pres_down":
            if self.t >= self.slow_until and self.phase_t > 1.0:
                self.finish("win")
        if self.impacts:
            self.impacts = [x for x in self.impacts if self.t - x[0] < 1.0]

    def fire(self):
        if self.t - self.last_shot < BOLT_S or self.phase in ("u_down", "pres_down") or self.fail_t >= 0.0:
            return None
        self.last_shot = self.t
        o = EYE
        d = self.view_dir()
        self.kick = 2.2                          # recoil after the round leaves
        self._snd("sniper_shot", 0.0, 10.0)
        best, hit = 1e9, None
        for name, c, rad, head in self.targets():
            dist = math.dist(o, c)
            tof = dist / MUZZLE_V
            # the round falls and drifts on the way: test against where the aim must have been
            aim_c = (c[0] - self.wind * tof * 0.9 * math.cos(math.radians(self.yaw)),
                     c[1] + 0.5 * G * tof * tof,
                     c[2] + self.wind * tof * 0.9 * math.sin(math.radians(self.yaw)))
            h = RB._ray_sphere(o, d, aim_c, rad)
            if h is not None and h < best:
                best, hit = h, (name, head)
        g_hit = -o[1] / d[1] if d[1] < -1e-6 else 600.0
        if hit is None:
            end = (o[0] + d[0] * g_hit, 0.05, o[2] + d[2] * g_hit)
            self.impacts.append((self.t, end))
            if self.phase == "ucilev":
                self.say("", "Snow kicks up at his feet. Ucilev does not move.", 2.4)
            return "miss"
        self.hit_mark = self.t
        name = hit[0]
        if name == "ucilev":
            self.u_down_t = self.t
            self.slow_until = self.t + 2.0
            self._set_phase("u_down")
            self.line_i = 0
            self._snd("headshot", 100.0)
        elif name == "pres":
            self.slow_until = self.t + 1.5
            self._set_phase("pres_down")
            self._snd("headshot", 100.0)
        else:
            g = self.guards[int(name[1:])]
            g["alive"] = False
            g["dead_t"] = self.t
            self._snd("enemy_down", 100.0)
        return name

    # --- input -----------------------------------------------------------------

    def handle_event(self, event):
        if not self._active or self.paused:
            return
        if event.type == pygame.MOUSEMOTION:
            dx, dy = event.rel
            s = 0.02 * self.fov() / ZOOMS[0] * 4.0
            self.yaw = (self.yaw + dx * s) % 360.0
            self.pitch = clamp(self.pitch - dy * s, -40.0, 10.0)
        elif event.type == pygame.MOUSEBUTTONDOWN:
            if event.button == 1:
                self.fire()
            elif event.button == 3:
                self.zoom_i = (self.zoom_i + 1) % len(ZOOMS)
        elif event.type == pygame.MOUSEWHEEL and event.y:
            self.zoom_i = int(clamp(self.zoom_i + (1 if event.y > 0 else -1), 0, len(ZOOMS) - 1))

    # --- draw ------------------------------------------------------------------

    def draw(self, surface):
        if not self._active:
            return
        tm = self.t * 1000.0
        d = self.view_dir()
        tgt = (EYE[0] + d[0] * 50.0, EYE[1] + d[1] * 50.0, EYE[2] + d[2] * 50.0)
        r = CS.frame(EYE, tgt, self.fov(), t=int(tm), look="night", lights=_pad_lights())
        r.fog_end = 520.0
        del _w.LAST[:]
        CS.put_helicopter(r, _off(-1.5, 0.5), 64.0, 4.0, 11.0, 0.0, 0.0, burned=True)
        r.add_sprite(_off(-3.0, 1.2), _fx.glow((255, 130, 60), 1.8, int(tm), flicker=0.7, seed=5),
                     layer=_fx.FX_LAYER)
        for lx, lz in ((-8, -8), (8, -8), (-8, 10), (10, 10)):
            r.add_sprite(_off(lx, lz), _fx.beacon((255, 210, 140), 0.3, int(tm)), layer=_fx.FX_LAYER)
        _w.actor(r, "president", self.pres_pose(), PRES_AT, _yaw_to(PRES_AT, EYE), int(tm),
                 seed=12, amp=0.0 if self.phase == "pres_down" else 0.2, expression="angry")
        _w.actor(r, "ucilev", self.ucilev_pose(), UCILEV_AT, _yaw_to(UCILEV_AT, EYE), int(tm),
                 seed=34, amp=0.15, expression="stern")
        for i, g in enumerate(self.guards):
            pose = dict(POSES["ready"]) if g["alive"] else dict(POSES["dead_back"])
            _w.actor(r, ("guard", "rifle"), pose, (g["x"], 0.0, g["z"]), g["yaw"], int(tm),
                     seed=300 + i, amp=0.3, rifle_on=g["alive"], flags=("os12",))
        rp = self.rescue_pos()
        CS.put_helicopter(r, rp, _yaw_to(rp, PAD) if self.fail_t < 0.0 else 30.0, -4.0, 0.0,
                          (tm * 1.5) % 360.0, (tm * 2.4) % 360.0)
        r.add_sprite((rp[0], rp[1] - 0.4, rp[2]), _fx.glow((240, 244, 255), 1.2, int(tm), pulse=0.3),
                     layer=_fx.FX_LAYER)
        for t0, p in self.impacts:
            if self.t - t0 < 0.5:
                r.add_sprite(p, _fx.powder(int((self.t - t0) * 1000.0), seed=3, spread_m=0.6,
                                           col=(230, 236, 244)), layer=_fx.FX_LAYER)
        CS.present(r, surface)
        self._scope(surface)
        self._hud(surface)

    def _scope(self, surface):
        cx, cy = WIDTH // 2, HEIGHT // 2
        rad = int(HEIGHT * 0.44)
        mask = _mask(rad)
        surface.blit(mask, (0, 0))
        col = (12, 12, 12)
        pygame.draw.line(surface, col, (cx - rad, cy), (cx - 8, cy), 2)
        pygame.draw.line(surface, col, (cx + 8, cy), (cx + rad, cy), 2)
        pygame.draw.line(surface, col, (cx, cy - rad), (cx, cy - 8), 2)
        pygame.draw.line(surface, col, (cx, cy + 8), (cx, cy + rad), 1)
        for i in range(1, 6):
            step = int(rad * 0.09 * i)
            pygame.draw.line(surface, col, (cx - 5, cy + step), (cx + 5, cy + step), 1)
            pygame.draw.circle(surface, col, (cx - step, cy), 2)
            pygame.draw.circle(surface, col, (cx + step, cy), 2)
        pygame.draw.circle(surface, (210, 40, 30), (cx, cy), 2)
        pygame.draw.circle(surface, (8, 8, 8), (cx, cy), rad, 6)

    def _hud(self, surface):
        cx, cy = WIDTH // 2, HEIGHT // 2
        if self.fail_t >= 0.0:
            k = clamp((self.t - self.fail_t - 1.5) / 2.0, 0.0, 1.0)
            surface.blit(_get_veil(int(255 * k)), (0, 0))
            img = font_terminal.render("HE GOT AWAY  -  AGAIN FROM THE RIDGE", True, (220, 200, 190))
            surface.blit(img, img.get_rect(center=(cx, cy)))
            RH.callouts(surface, self)
            return
        if self.phase == "pres_down":
            k = clamp((self.t - self.phase_start - 0.6) / 0.8, 0.0, 1.0)
            if k > 0.0:
                surface.blit(_get_veil(int(255 * k)), (0, 0))
            return
        head = {"ucilev": "Take Ucilev", "u_down": "", "radio": "Listen",
                "wait": "Shoot anyway"}.get(self.phase, "")
        if head:
            H.objective(surface, head)
        x, y = 28, HEIGHT - 96
        rng = math.dist(EYE, PRES_AT)
        H._text(surface, font_terminal_small, "RANGE %d M   ZOOM x%d" % (rng, int(round(64.0 / self.fov()))),
                H.TEXT, (x, y))
        arrow = ">" * int(abs(self.wind)) if self.wind > 0 else "<" * int(abs(self.wind))
        H._text(surface, font_terminal_small, "WIND %.1f M/S %s" % (abs(self.wind), arrow), H.TEXT, (x, y + 22))
        H._text(surface, font_terminal_small, "BREATH [SHIFT]", H.DANGER if self.winded > 0 else H.TEXT,
                (x, y + 44))
        H._bar(surface, x + 150, y + 51, 140, self.breath / BREATH_S, H.ACCENT, h=6)
        if self.phase in ("ucilev", "wait"):
            H._text(surface, font_terminal_small, "RESCUE BIRD  %d S" % int(math.ceil(self.rescue)),
                    H.DANGER if self.rescue < 12 else H.TEXT, (WIDTH - 28, HEIGHT - 96), "topright")
        if self.t - self.last_shot < BOLT_S:
            H._text(surface, font_terminal_small, "BOLT", H.TEXT, (cx, cy + 40), "midtop")
        RH.callouts(surface, self)


_MASKS = {}
_VEIL = [None]
_PAD_LIGHTS = tuple(
    {"pos": (PAD[0] + x, 5.0, PAD[2] + z), "color": (255, 214, 160), "intensity": 0.9, "range": 18.0}
    for x, z in ((-6.0, -6.0), (8.0, 8.0))
)


def _get_veil(alpha):
    v = _VEIL[0]
    if v is None:
        v = _VEIL[0] = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
    v.fill((0, 0, 0, alpha))
    return v


def _mask(rad):
    m = _MASKS.get(rad)
    if m is None:
        m = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        m.fill((0, 0, 0, 255))
        pygame.draw.circle(m, (0, 0, 0, 0), (WIDTH // 2, HEIGHT // 2), rad)
        _MASKS[rad] = m
    return m


def _pad_lights():
    return _PAD_LIGHTS


_SCENE = None


def scene():
    global _SCENE
    if _SCENE is None:
        _SCENE = RidgeScene()
    return _SCENE


def begin():
    return scene().begin()


def active():
    return _SCENE is not None and _SCENE.active()


def update(keys=None):
    return scene().update(keys)


def draw(surface):
    return scene().draw(surface)


def handle_event(event):
    return scene().handle_event(event)


def set_paused(paused):
    if _SCENE is not None:
        _SCENE.set_paused(paused)


def abort():
    if _SCENE is not None and _SCENE.active():
        _SCENE._active = False
        _SCENE.paused = False
        STATE.m8_ridge_active = False
        _SCENE._grab(False)
        if _SCENE.audio is not None:
            try:
                _SCENE.audio.stop_loops()
            except Exception:
                pass


def force_finish(reason="fallback"):
    if _SCENE is not None:
        return _SCENE.finish(reason)
    return False
