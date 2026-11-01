"""RPE6 trailer, Mission 7 cut: the 80 s engine trailer with Fallow Ground in it.

    python tools/trailer_rpe6/render_m7.py --at 40 48 56   stills -> outputs/trailer_rpe6_m7/stills/
    python tools/trailer_rpe6/render_m7.py --sheet         one still per shot + _sheet.jpg
    python tools/trailer_rpe6/render_m7.py                 full 80 s MP4 (1920x1080, 30 fps, score)

Same score, cut points and set pieces as render.py, so the music still lands.
The M6 combat beat, its reload and four story-trailer worlds give way to the
live M7 raid (orchard gate, the trucks, the burning barn, the Fallow 12
reload) and the M7 films (the dawn drop-off, the convoy, the east gate).
The raid runs headless with the HUD off and nobody on our side taking damage.
"""
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import render as R  # noqa: E402  (sets up paths, SDL, the engine)
import pygame  # noqa: E402

C = R.C
R.OUT_DIR = os.path.join(R.ROOT, "outputs", "trailer_rpe6_m7")
lerp, smooth, wrap = R.lerp, R.smooth, R.wrap
RAID_FOV = 1.18                     # the raid's 640x448 framing, widened for 2.39:1


# --- the M7 raid, driven headless ----------------------------------------------
_RAID = {}


def raid_mod():
    if not _RAID:
        R.game("yard")                      # the M6 stack first: the mission load order
        from missions import m7  # noqa: F401
        from missions.m7 import raid3d as RD
        from cutscenes import m6world3d as _w
        RD.RES = (R.PW // 2, R.PH // 2)     # crisp x2 into the picture
        RD.HUD = type("NoHud", (), {"draw": staticmethod(lambda surface, sc: None)})
        RD.draw_vignette = lambda surface: None
        _RAID.update(RD=RD, w=_w, surf=pygame.Surface((R.PW, R.PH)))
    return _RAID["RD"]


class RaidShot(R.Shot):
    cp = 0                          # checkpoint: 0 orchard, 1 trucks, 2 the north and the fire
    preps = ("shed", "loft")
    preroll = 10.0
    pos = yaw = None
    bursts = None                   # (a, b) local windows the trigger is held; None = never
    rate = 0.2
    fov_k = RAID_FOV

    def setup(self):
        self.disp = None

    def stage(self, sc):
        pass

    def drive(self, sc, lt):
        sc.mag = sc.MAG
        g = self.target(sc)
        if self.bursts is not None:
            sc.aiming = lt > -0.4
            sc.firing = g is not None and any(a <= lt < b for a, b in self.bursts)
            self.aim(sc, g)
        return R.Keys()

    def cam(self, sc, lt):
        eye, tgt, fov, d = type(sc).camera(sc)
        return eye, tgt, fov * self.fov_k, d

    def target(self, sc):
        best, bd = None, 1e9
        for e in sc.brain.enemies:
            if not (e["alive"] and e["live"]):
                continue
            dx, dz = e["x"] - sc.px, e["z"] - sc.pz
            d = math.hypot(dx, dz)
            if d < 1.5 or d > 30:
                continue
            s = abs(wrap(math.degrees(math.atan2(dx, dz)) - sc.yaw)) + d * 0.8
            if s < bd:
                best, bd = e, s
        return best

    def aim(self, sc, e, rate=None):
        if e is None:
            return
        eye = type(sc).camera(sc)[0]
        tgt = (e["x"], e["y"] + (0.6 if e["kind"] == "dog" else 1.2), e["z"])
        d = [tgt[i] - eye[i] for i in range(3)]
        yaw = math.degrees(math.atan2(d[0], d[2]))
        pitch = math.degrees(math.atan2(d[1], math.hypot(d[0], d[2])))
        k = self.rate if rate is None else rate
        sc.yaw += wrap(yaw - sc.yaw) * k
        sc.pitch += (pitch - sc.pitch) * k

    def reset(self):
        from core.state import STATE
        RD = raid_mod()
        STATE.m7_preps = list(self.preps)
        STATE.m7_raid_cp = self.cp
        RD._SCENE = None
        sc = self.sc = RD.scene()
        sc.begin()
        sc.audio = None
        sc._grab(False)
        sc.finish = lambda result="win": False
        sc.hurt_player = lambda dmg, src=None: None
        sc.brain._damage = lambda name, dmg, src: None
        sc.say = lambda who, text, dur=3.0: None
        if self.pos is not None:
            sc.px, sc.pz = self.pos
        if self.yaw is not None:
            sc.yaw = sc.body_yaw = self.yaw
        self.stage(sc)
        self.last_fire = sc.last_fire
        self.hp = {}
        self.disp = -self.preroll
        while self.disp < -1e-9:
            self.tick()

    def tick(self):
        from core.state import STATE
        sc, lt = self.sc, self.disp
        keys = self.drive(sc, lt)
        STATE.dt = 1.0 / 60.0
        sc.update(keys)
        if lt >= 0:
            if sc.last_fire != self.last_fire:
                R.EVENTS.append((self.start + lt, "shot"))
            if any(e["hp"] < self.hp.get(id(e), e["hp"]) for e in sc.brain.enemies):
                R.EVENTS.append((self.start + lt, "hit"))
        self.last_fire = sc.last_fire
        self.hp = {id(e): e["hp"] for e in sc.brain.enemies}
        self.disp += 1.0 / 60.0

    def picture(self, lt, T, n):
        if self.disp is None or lt < self.disp - 0.05:
            self.reset()
        while self.disp <= lt + 1e-9:
            self.tick()
        cam = self.cam(self.sc, lt)
        self.sc.camera = lambda c=cam: c
        try:
            self.sc.draw(_RAID["surf"])
        finally:
            del self.sc.camera
        return _RAID["surf"]


def orbit(sc, ang, R_, up, fwd=0.35):
    """A camera ``R_`` metres from the player's head, ``ang`` degrees off his back."""
    RD = _RAID["RD"]
    f, rg = RD._fwd(sc.yaw, 0.0), RD._right(sc.yaw)
    h = (sc.px, RD.EYE_H, sc.pz)
    ca, sa = math.cos(math.radians(ang)), math.sin(math.radians(ang))
    eye = (h[0] - (f[0] * ca - rg[0] * sa) * R_, h[1] + up, h[2] - (f[2] * ca - rg[2] * sa) * R_)
    return eye, (h[0] + f[0] * fwd, h[1] - 0.15, h[2] + f[2] * fwd)


class Orchard(RaidShot):
    """Wave 1: riflemen out of the orchard, the Fallow 12 answering."""
    line = ("MISSION 7 // FALLOW GROUND", 0.3, 3.4)
    cp, preroll, pos = 0, 12.5, (9.0, -0.6)
    bursts = ((0.25, 3.6),)


class Reload(RaidShot):
    """Shells in one at a time, close on the hands."""
    cap = ("HAND-BUILT ANIMATION", "pump, shells, recoil, every frame posed in code", 0.25, 2.0)
    cp, preroll, pos = 0, 16.0, (9.0, -0.6)

    def stage(self, sc):
        sc.mag = 2

    def drive(self, sc, lt):
        sc.aiming = sc.firing = False
        if lt >= -0.05 and not sc.reloading:
            sc.mag, sc.reserve = 2, 24
            sc._begin_reload()
        self.aim(sc, self.target(sc), 0.05)
        return R.Keys()

    def cam(self, sc, lt):
        # front quarter, gun side, easing in on the hands
        u = smooth(lt / (self.end - self.start))
        f = _RAID["RD"]._fwd(sc.yaw, 0.0)
        d, s = lerp(4.2, 3.5, u), lerp(2.2, 1.8, u)
        eye = (sc.px + f[0] * d + f[2] * s, 1.6, sc.pz + f[2] * d - f[0] * s)
        return eye, (sc.px + f[0] * 0.3, 1.25, sc.pz + f[2] * 0.3), 56.0, 3.8


class Trucks(RaidShot):
    """Wave 2: the trucks come up the track, lights first."""
    cap = ("VEHICLES", "trucks drive the track, drop the squad, light the road", 0.3, 2.9)
    cp, preroll = 1, 9.0
    bursts = ((1.4, 3.2),)

    def cam(self, sc, lt):
        u = smooth(lt / (self.end - self.start))
        eye, _tgt = orbit(sc, lerp(-24.0, -12.0, u), lerp(4.6, 3.8, u), lerp(1.2, 0.6, u))
        RD = _RAID["RD"]
        f = RD._fwd(sc.yaw, 0.0)
        return eye, (sc.px + f[0] * 12.0, 1.0, sc.pz + f[2] * 12.0), 60.0, 4.0


class Barn(RaidShot):
    """Wave 3: the north sweep with the barn on fire behind them."""
    cap = ("FIRE", "it spreads, it lights the yard, it burns", 0.2, 1.8)
    cp, preroll = 2, 17.0
    bursts = ((0.4, 2.0),)

    def cam(self, sc, lt):
        # from behind his left shoulder toward the burning barn (x 12-16, z 4-14)
        u = smooth(lt / (self.end - self.start))
        eye = (sc.px - lerp(4.2, 3.4, u), lerp(2.0, 1.7, u), sc.pz - lerp(3.6, 3.0, u))
        return eye, (13.0, 2.6, 8.0), 62.0, 3.4


class North(RaidShot):
    """Wave 3, closer: stand and fire into the sweep."""
    cp, preroll = 2, 13.0
    bursts = ((0.05, 2.4),)


# --- the M7 films ------------------------------------------------------------------
class Film(R.Shot):
    """An M7 film scene rendered as the game plays it, location tag off, cut to 2.39:1."""
    name, skip = "dropoff_lift", 0.0
    module = "m7films"

    def setup(self):
        import importlib
        raid_mod()
        from core.config import HEIGHT, WIDTH
        from cutscenes import m7world3d as F
        if not getattr(F.finish, "_untagged", False):
            orig = F.finish

            def finish(surface, r, buf, seed, tag, t):
                orig(surface, r, buf, seed, "", t)
            finish._untagged = True
            F.finish = finish
        self.fn = getattr(importlib.import_module("cutscenes." + self.module), self.name)
        self.surf = pygame.Surface((WIDTH, HEIGHT))
        w = _RAID["w"]
        h = min(w.FILM_H, int(WIDTH * R.PH / R.PW))
        cw = min(WIDTH, int(h * R.PW / R.PH))
        self.crop = ((WIDTH - cw) // 2, w.SAFE_TOP + (w.FILM_H - h) // 2, cw, h)
        self.pic = pygame.Surface((R.PW, R.PH))

    def picture(self, lt, T, n):
        self.surf.fill((0, 0, 0))
        self.fn(self.surf, (lt + self.skip) * 1000.0)
        pygame.transform.smoothscale(self.surf.subsurface(self.crop), (R.PW, R.PH), self.pic)
        return self.pic


# --- title: the M7 line under the wordmark -------------------------------------------
class Title(R.Title):
    def overlay(self, cv, lt, T):
        super().overlay(cv, lt, T)
        k = R.fade_in_out(lt, 0.9, self.END_AT - 0.3, 0.5, 0.4)
        if k > 0:
            s = R.spaced("NEW: MISSION 7 - FALLOW GROUND", C.font("oswald", 40), R.INK, 8)
            s.set_alpha(int(255 * k))
            cv.blit(s, (R.OUT_W // 2 - s.get_width() // 2, R.OUT_H // 2 + 160))


def build():
    W_ = R.World
    return [
        R.Boot(0.0, 6.0),
        R.VoxelLogo(6.0, 10.65),
        R.Assembly(10.65, 18.6),
        R.Run(18.6, 22.0),
        R.Aim(22.0, 25.2),
        Film(25.2, 28.45, name="dropoff_lift", skip=0.4,
             cap=("WEATHER3D", "dawn mist, low sun, rotor wash, per set", 0.3, 2.9)),
        R.YardWide(28.45, 32.05),
        R.YardPlay(32.05, 34.11),
        R.TrainFP(34.11, 39.25),
        Orchard(39.25, 43.0),
        Reload(43.0, 45.25),
        Film(45.25, 47.6, name="raidin_road", skip=1.0,
             cap=("TIMELINE CUTSCENES", "keyed cameras, rigs and lights", 0.2, 2.1)),
        Trucks(47.6, 50.8),
        W_(50.8, 52.6, name="Mansion", skip=0.0,
           cap=("ONE SIM, TWO BACKENDS", "OpenGL, or software when there is no GPU", 0.2, 1.6)),
        Film(52.6, 53.95, name="raidin_yard", skip=1.5),
        W_(53.95, 55.35, name="Gunship", skip=0.0,
           cap=("DETERMINISTIC", "seeded simulation, replayable runs", 0.1, 1.2)),
        Barn(55.35, 57.4),
        W_(57.4, 59.3, name="Cockpit", skip=0.0,
           cap=("DIALOGUE GRAPHS", ".dlg.json, walked by the runner", 0.2, 1.7)),
        R.K9Turn(59.3, 62.0),
        R.FireLow(62.0, 64.6),
        North(64.6, 66.95),
        R.SlowMo(66.95, 68.55),
        R.Breath(68.55, 71.3),
        Title(71.3, R.TOTAL),
    ]


if __name__ == "__main__":
    R.build = build
    if "--out" not in sys.argv:
        sys.argv += ["--out", os.path.join(R.OUT_DIR, "rpe6_m7_trailer.mp4")]
    R.main()
